#!/usr/bin/env python3
"""ChatGPT FC를 사용한 PR 코드 리뷰.

PR diff를 분석하여 버그, 보안, 성능, 설계 관점의 리뷰를 생성한다.
GitHub Actions 또는 로컬에서 실행 가능.

Usage:
  python3 scripts/gpt_pr_review.py --pr 42
  python3 scripts/gpt_pr_review.py --diff-file /tmp/pr.diff
  python3 scripts/gpt_pr_review.py --pr 42 --post-comment
"""

import argparse
import json
import os
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(__file__))
from linear_client import PROJECT_DIR


def get_openai_key() -> str:
    """Get OpenAI API key."""
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key

    env_path = os.path.join(PROJECT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip()

    print("Error: OPENAI_API_KEY required.", file=sys.stderr)
    sys.exit(1)


def get_pr_diff(pr_number: int) -> str:
    """Get PR diff using gh CLI."""
    result = subprocess.run(
        ["gh", "pr", "diff", str(pr_number)],
        capture_output=True, text=True, cwd=PROJECT_DIR,
    )
    if result.returncode != 0:
        print(f"Error: PR diff 가져오기 실패: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def get_pr_info(pr_number: int) -> dict:
    """Get PR metadata."""
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "title,body,headRefName,baseRefName,url"],
        capture_output=True, text=True, cwd=PROJECT_DIR,
    )
    if result.returncode != 0:
        return {}
    return json.loads(result.stdout)


def truncate_diff(diff: str, max_chars: int = 15000) -> str:
    """Truncate diff to fit within token limits."""
    if len(diff) <= max_chars:
        return diff
    # 앞부분 + 뒷부분 조합
    half = max_chars // 2
    return diff[:half] + "\n\n... (중간 생략) ...\n\n" + diff[-half:]


def call_chatgpt_review(api_key: str, diff: str, pr_info: dict) -> dict:
    """Call ChatGPT FC for code review."""
    tools = [{
        "type": "function",
        "function": {
            "name": "submit_review",
            "description": "코드 리뷰 결과를 구조화된 형태로 제출한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "전체 리뷰 요약 (1-2문장)"
                    },
                    "verdict": {
                        "type": "string",
                        "enum": ["approve", "request_changes", "comment"],
                        "description": "리뷰 판정"
                    },
                    "bugs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string"},
                                "description": {"type": "string"},
                                "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                            },
                            "required": ["file", "description", "severity"],
                        },
                        "description": "발견된 버그"
                    },
                    "security": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string"},
                                "description": {"type": "string"},
                                "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                            },
                            "required": ["file", "description", "severity"],
                        },
                        "description": "보안 이슈"
                    },
                    "performance": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["file", "description"],
                        },
                        "description": "성능 이슈"
                    },
                    "design": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                            },
                            "required": ["description"],
                        },
                        "description": "설계 개선 제안"
                    },
                    "good_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "잘된 점"
                    },
                },
                "required": ["summary", "verdict", "bugs", "security"],
            },
        },
    }]

    title = pr_info.get("title", "")
    body = pr_info.get("body", "")[:500]

    messages = [
        {
            "role": "system",
            "content": (
                "너는 시니어 소프트웨어 엔지니어이자 코드 리뷰어다. "
                "PR diff를 분석하여 버그, 보안 취약점, 성능 이슈, 설계 문제를 찾아낸다. "
                "사소한 스타일 이슈보다 실질적인 문제에 집중한다. "
                "반드시 submit_review 함수를 호출하여 구조화된 형태로 응답하라. "
                "한국어로 작성한다."
            ),
        },
        {
            "role": "user",
            "content": (
                f"## PR 정보\n"
                f"제목: {title}\n"
                f"설명: {body}\n\n"
                f"## Diff\n```diff\n{truncate_diff(diff)}\n```\n\n"
                f"이 PR의 코드 리뷰를 submit_review 함수로 제출해줘."
            ),
        },
    ]

    payload = {
        "model": "gpt-4o",
        "messages": messages,
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": "submit_review"}},
        "temperature": 0.2,
    }

    data = json.dumps(payload).encode("utf-8")
    req = Request("https://api.openai.com/v1/chat/completions", data=data, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        err_body = e.read().decode()
        print(f"OpenAI API Error ({e.code}): {err_body}", file=sys.stderr)
        return {}

    choices = result.get("choices", [])
    if not choices:
        return {}

    message = choices[0].get("message", {})
    tool_calls = message.get("tool_calls", [])
    if not tool_calls:
        return {}

    try:
        return json.loads(tool_calls[0]["function"]["arguments"])
    except (json.JSONDecodeError, KeyError):
        return {}


def review_to_markdown(review: dict) -> str:
    """Convert review result to markdown comment."""
    lines = []
    verdict = review.get("verdict", "comment")
    verdict_emoji = {"approve": "✅", "request_changes": "❌", "comment": "💬"}.get(verdict, "💬")
    verdict_text = {"approve": "승인", "request_changes": "수정 요청", "comment": "코멘트"}.get(verdict, "코멘트")

    lines.append(f"## {verdict_emoji} AI 코드 리뷰 — {verdict_text}")
    lines.append("")
    lines.append(f"**요약:** {review.get('summary', 'N/A')}")
    lines.append("")

    # 버그
    bugs = review.get("bugs", [])
    if bugs:
        lines.append("### 🐛 버그")
        for bug in bugs:
            severity_emoji = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(bug.get("severity", "minor"), "🟡")
            file_ref = f"`{bug['file']}`" if bug.get("file") else ""
            lines.append(f"- {severity_emoji} {file_ref} {bug['description']}")
        lines.append("")

    # 보안
    security = review.get("security", [])
    if security:
        lines.append("### 🔒 보안")
        for sec in security:
            severity_emoji = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(sec.get("severity", "minor"), "🟡")
            file_ref = f"`{sec['file']}`" if sec.get("file") else ""
            lines.append(f"- {severity_emoji} {file_ref} {sec['description']}")
        lines.append("")

    # 성능
    performance = review.get("performance", [])
    if performance:
        lines.append("### ⚡ 성능")
        for perf in performance:
            file_ref = f"`{perf['file']}`" if perf.get("file") else ""
            lines.append(f"- {file_ref} {perf['description']}")
        lines.append("")

    # 설계
    design = review.get("design", [])
    if design:
        lines.append("### 🏗️ 설계")
        for d in design:
            lines.append(f"- {d['description']}")
        lines.append("")

    # 잘된 점
    good = review.get("good_points", [])
    if good:
        lines.append("### 👍 잘된 점")
        for g in good:
            lines.append(f"- {g}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by GPT-4o Code Review*")

    return "\n".join(lines)


def post_pr_comment(pr_number: int, comment: str):
    """Post a comment on a PR."""
    result = subprocess.run(
        ["gh", "pr", "comment", str(pr_number), "--body", comment],
        capture_output=True, text=True, cwd=PROJECT_DIR,
    )
    if result.returncode != 0:
        print(f"Error: PR 코멘트 게시 실패: {result.stderr}", file=sys.stderr)
        return False
    print(f"POSTED: PR #{pr_number}에 리뷰 코멘트 게시 완료")
    return True


def main():
    from pipeline_config import check_enabled

    check_enabled("FLOWOPS_GPT_REVIEW", "ChatGPT 코드 리뷰")

    parser = argparse.ArgumentParser(description="ChatGPT FC PR 코드 리뷰")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pr", type=int, help="PR 번호")
    group.add_argument("--diff-file", help="diff 파일 경로")

    parser.add_argument("--post-comment", action="store_true",
                        help="리뷰를 PR 코멘트로 게시")
    parser.add_argument("--output", help="리뷰 결과 파일로 저장")
    args = parser.parse_args()

    api_key = get_openai_key()

    # Diff 가져오기
    if args.pr:
        diff = get_pr_diff(args.pr)
        pr_info = get_pr_info(args.pr)
    else:
        with open(args.diff_file) as f:
            diff = f.read()
        pr_info = {}

    if not diff.strip():
        print("SKIP: diff가 비어 있음.")
        sys.exit(0)

    print(f"리뷰 중... (diff: {len(diff)} chars)")
    review = call_chatgpt_review(api_key, diff, pr_info)

    if not review:
        print("ERROR: ChatGPT 리뷰 응답 실패.", file=sys.stderr)
        sys.exit(1)

    markdown = review_to_markdown(review)

    # 결과 출력
    print(f"\nVerdict: {review.get('verdict', 'N/A')}")
    print(f"Bugs: {len(review.get('bugs', []))}")
    print(f"Security: {len(review.get('security', []))}")

    if args.output:
        with open(args.output, "w") as f:
            f.write(markdown)
        print(f"SAVED: {args.output}")
    else:
        print(f"\n{markdown}")

    # PR 코멘트 게시
    if args.post_comment and args.pr:
        post_pr_comment(args.pr, markdown)


if __name__ == "__main__":
    main()
