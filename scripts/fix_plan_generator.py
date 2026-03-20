#!/usr/bin/env python3
"""ChatGPT Function Calling으로 구조화된 Fix Plan 생성.

Linear 이슈 description + 코드베이스 맥락 → ChatGPT FC → 구조화된 fix_plan.md

Usage:
  python3 scripts/fix_plan_generator.py --title "제목" --description "설명"
  python3 scripts/fix_plan_generator.py --title "제목" --description "설명" --priority P1
  python3 scripts/fix_plan_generator.py --title "제목" --description "설명" --dry-run
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
    """Get OpenAI API key from env or .env file."""
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


def get_file_tree(max_depth: int = 3) -> str:
    """Get project file tree for context."""
    try:
        result = subprocess.run(
            ["find", ".", "-maxdepth", str(max_depth),
             "-not", "-path", "./.git/*",
             "-not", "-path", "./node_modules/*",
             "-not", "-path", "./.venv/*",
             "-not", "-path", "./__pycache__/*",
             "-not", "-path", "./.worktrees/*",
             "-type", "f"],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        if result.returncode == 0:
            files = result.stdout.strip().split("\n")
            # 주요 파일만 필터링
            important_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".yml", ".yaml", ".md", ".sh"}
            filtered = [f for f in files if any(f.endswith(ext) for ext in important_exts)]
            return "\n".join(sorted(filtered)[:100])  # 최대 100개
    except Exception:
        pass
    return ""


def get_module_summary() -> str:
    """Get brief summary of key modules."""
    summaries = []

    # Backend routes
    backend_routes = os.path.join(PROJECT_DIR, "backend", "app", "api")
    if os.path.isdir(backend_routes):
        try:
            result = subprocess.run(
                ["find", backend_routes, "-name", "*.py", "-not", "-name", "__init__.py"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                routes = [os.path.basename(f).replace(".py", "") for f in result.stdout.strip().split("\n") if f]
                if routes:
                    summaries.append(f"Backend API routes: {', '.join(routes)}")
        except Exception:
            pass

    # Frontend pages
    frontend_pages = os.path.join(PROJECT_DIR, "frontend", "src", "app")
    if os.path.isdir(frontend_pages):
        try:
            result = subprocess.run(
                ["find", frontend_pages, "-name", "page.tsx", "-o", "-name", "page.ts"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                pages = result.stdout.strip().split("\n")
                page_paths = [p.replace(frontend_pages, "").replace("/page.tsx", "").replace("/page.ts", "") or "/" for p in pages if p]
                if page_paths:
                    summaries.append(f"Frontend pages: {', '.join(page_paths)}")
        except Exception:
            pass

    return "\n".join(summaries)


def call_chatgpt_fc(api_key: str, title: str, description: str, priority: str, context: str) -> dict:
    """Call ChatGPT with Function Calling to generate structured fix plan."""
    tools = [{
        "type": "function",
        "function": {
            "name": "create_fix_plan",
            "description": "구현 계획을 구조화된 형태로 생성한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "approach": {
                        "type": "string",
                        "description": "전체적인 구현 접근 방식 (2-3문장)"
                    },
                    "files_to_modify": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "파일 경로"},
                                "action": {"type": "string", "enum": ["create", "modify", "delete"]},
                                "reason": {"type": "string", "description": "변경 이유"},
                            },
                            "required": ["path", "action", "reason"],
                        },
                        "description": "수정 대상 파일 목록"
                    },
                    "implementation_steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "구현 단계 목록 (순서대로)"
                    },
                    "test_cases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "필요한 테스트 케이스"
                    },
                    "risks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "잠재적 위험 요소"
                    },
                },
                "required": ["approach", "files_to_modify", "implementation_steps", "test_cases"],
            },
        },
    }]

    messages = [
        {
            "role": "system",
            "content": (
                "너는 시니어 풀스택 엔지니어다. "
                "주어진 요구사항과 코드베이스 맥락을 분석하여 구체적인 구현 계획을 생성한다. "
                "반드시 create_fix_plan 함수를 호출하여 구조화된 형태로 응답하라."
            ),
        },
        {
            "role": "user",
            "content": (
                f"## 요구사항\n"
                f"제목: {title}\n"
                f"우선순위: {priority}\n"
                f"설명:\n{description}\n\n"
                f"## 코드베이스 맥락\n{context}\n\n"
                f"이 요구사항의 구현 계획을 create_fix_plan 함수로 생성해줘."
            ),
        },
    ]

    payload = {
        "model": "gpt-4o",
        "messages": messages,
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": "create_fix_plan"}},
        "temperature": 0.3,
    }

    data = json.dumps(payload).encode("utf-8")
    req = Request("https://api.openai.com/v1/chat/completions", data=data, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
    except HTTPError as e:
        err_body = e.read().decode()
        print(f"OpenAI API Error ({e.code}): {err_body}", file=sys.stderr)
        return {}

    # FC 응답 파싱
    choices = result.get("choices", [])
    if not choices:
        return {}

    message = choices[0].get("message", {})
    tool_calls = message.get("tool_calls", [])
    if not tool_calls:
        return {}

    try:
        arguments = json.loads(tool_calls[0]["function"]["arguments"])
        return arguments
    except (json.JSONDecodeError, KeyError):
        return {}


def plan_to_fix_plan_md(title: str, priority: str, description: str, plan: dict) -> str:
    """Convert structured plan to fix_plan.md format."""
    lines = [
        "# Ralph Loop — 작업 큐 (Fix Plan)",
        "",
        "> Claude가 이 파일을 읽고 미완료(`- [ ]`) 항목을 처리한다.",
        "> 완료 시 `- [x]`로 표시하고 커밋한다.",
        "> `- [!]`는 건너뛴 항목 (사유 기록 필수).",
        "",
        "---",
        "",
        f"## {priority}: 기능 요구사항",
        "",
        f"- [ ] **{title}**",
        f"  > 요청사항: {description.split(chr(10))[0] if description else title}",
        "",
    ]

    # 구현 접근 방식
    approach = plan.get("approach", "")
    if approach:
        lines.append(f"### 구현 접근")
        lines.append(f"> {approach}")
        lines.append("")

    # 수정 대상 파일
    files = plan.get("files_to_modify", [])
    if files:
        lines.append("### 수정 대상 파일")
        for f in files:
            action_emoji = {"create": "+", "modify": "~", "delete": "-"}.get(f.get("action", "modify"), "~")
            lines.append(f"- [{action_emoji}] `{f['path']}` — {f.get('reason', '')}")
        lines.append("")

    # 구현 단계
    steps = plan.get("implementation_steps", [])
    if steps:
        lines.append("### 구현 단계")
        for i, step in enumerate(steps, 1):
            lines.append(f"  - [ ] {i}. {step}")
        lines.append("")

    # 테스트 케이스
    tests = plan.get("test_cases", [])
    if tests:
        lines.append("### 테스트 케이스")
        for test in tests:
            lines.append(f"  - [ ] {test}")
        lines.append("")

    # 위험 요소
    risks = plan.get("risks", [])
    if risks:
        lines.append("### 주의사항")
        for risk in risks:
            lines.append(f"- ⚠️ {risk}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 진행 로그",
        "",
        "> Ralph가 작업하면서 여기에 기록을 남긴다.",
        "",
        "| 시각 | 항목 | 상태 | 비고 |",
        "|------|------|------|------|",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="ChatGPT FC Fix Plan 생성기")
    parser.add_argument("--title", required=True, help="태스크 제목")
    parser.add_argument("--description", required=True, help="태스크 설명")
    parser.add_argument("--priority", default="P2", choices=["P1", "P2", "P3"])
    parser.add_argument("--output", help="출력 파일 경로 (기본: stdout)")
    parser.add_argument("--dry-run", action="store_true", help="GPT 호출 없이 맥락만 출력")
    args = parser.parse_args()

    # 코드베이스 맥락 수집
    file_tree = get_file_tree()
    module_summary = get_module_summary()
    context = f"### 파일 트리\n```\n{file_tree}\n```\n\n### 모듈 요약\n{module_summary}"

    if args.dry_run:
        print("[DRY-RUN] 코드베이스 맥락:")
        print(context)
        print(f"\n제목: {args.title}")
        print(f"설명: {args.description}")
        print(f"우선순위: {args.priority}")
        sys.exit(0)

    api_key = get_openai_key()

    print(f"ChatGPT FC 호출 중... (제목: {args.title})")
    plan = call_chatgpt_fc(api_key, args.title, args.description, args.priority, context)

    if not plan:
        print("WARN: ChatGPT FC 응답 실패. 기본 fix_plan으로 fallback.", file=sys.stderr)
        # fallback: 기본 형식
        fix_plan_content = "\n".join([
            "# Ralph Loop — 작업 큐 (Fix Plan)",
            "",
            "> Claude가 이 파일을 읽고 미완료(`- [ ]`) 항목을 처리한다.",
            "> 완료 시 `- [x]`로 표시하고 커밋한다.",
            "",
            "---",
            "",
            f"## {args.priority}: 기능 요구사항",
            "",
            f"- [ ] **{args.title}**",
            f"  > 요청사항: {args.description}",
            "",
            "---",
            "",
            "## 진행 로그",
            "",
            "> Ralph가 작업하면서 여기에 기록을 남긴다.",
            "",
            "| 시각 | 항목 | 상태 | 비고 |",
            "|------|------|------|------|",
        ])
    else:
        fix_plan_content = plan_to_fix_plan_md(args.title, args.priority, args.description, plan)
        print(f"FIX_PLAN 생성 완료:")
        print(f"  접근: {plan.get('approach', 'N/A')[:80]}")
        print(f"  수정파일: {len(plan.get('files_to_modify', []))}개")
        print(f"  구현단계: {len(plan.get('implementation_steps', []))}개")
        print(f"  테스트: {len(plan.get('test_cases', []))}개")

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(fix_plan_content)
        print(f"SAVED: {args.output}")
    else:
        print("\n" + fix_plan_content)


if __name__ == "__main__":
    main()
