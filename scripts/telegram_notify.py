#!/usr/bin/env python3
"""Telegram notification sender for Ralph Loop completion reports.

Usage:
  # 간단 메시지
  python3 telegram_notify.py --message "작업 완료!"

  # Ralph Loop 완료 보고 (fix_plan.md 기반 자동 요약)
  python3 telegram_notify.py --ralph-report

  # Ralph Loop 완료 보고 + 추가 정보
  python3 telegram_notify.py --ralph-report --iterations 5 --test-result "82 passed"

  # 파이프라인 상세 완료 보고 (.pipeline_result.json 기반)
  python3 telegram_notify.py --pipeline-report --iterations 5 --test-result "82 passed"
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TELEGRAM_API = "https://api.telegram.org"


def get_env():
    """Load Telegram credentials from .env file (priority) or env vars."""
    token = None
    chat_id = None

    # .env 파일을 항상 우선 읽는다
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "TELEGRAM_BOT_TOKEN":
                    token = v
                elif k == "TELEGRAM_CHAT_ID":
                    chat_id = v

    # .env에 없으면 환경변수에서 읽는다
    if not token:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not chat_id:
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required.", file=sys.stderr)
        sys.exit(1)

    return token, chat_id


def send_message(token: str, chat_id: str, text: str) -> dict:
    """Send a message via Telegram Bot API."""
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        err_body = e.read().decode()
        print(f"Telegram API Error ({e.code}): {err_body}", file=sys.stderr)
        sys.exit(1)


def parse_fix_plan() -> dict:
    """Parse fix_plan.md to extract completion summary."""
    fix_plan_path = os.path.join(os.path.dirname(__file__), "..", ".ralph", "fix_plan.md")
    if not os.path.exists(fix_plan_path):
        return {"total": 0, "done": 0, "incomplete": 0, "sections": {}}

    with open(fix_plan_path) as f:
        content = f.read()

    sections = {}
    for priority in ["P1", "P2", "P3"]:
        done = len(re.findall(rf"^- \[x\].*", content, re.MULTILINE))
        incomplete = len(re.findall(rf"^- \[ \].*", content, re.MULTILINE))

        # Extract section-specific counts
        pattern = rf"## {priority}:.*?(?=## |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            section = match.group()
            s_done = len(re.findall(r"^- \[x\]", section, re.MULTILINE))
            s_incomplete = len(re.findall(r"^- \[ \]", section, re.MULTILINE))
            sections[priority] = {"done": s_done, "incomplete": s_incomplete}

    total_done = sum(s["done"] for s in sections.values())
    total_incomplete = sum(s["incomplete"] for s in sections.values())

    return {
        "total": total_done + total_incomplete,
        "done": total_done,
        "incomplete": total_incomplete,
        "sections": sections,
    }


def parse_fix_plan_detailed() -> dict:
    """Parse fix_plan.md to extract detailed per-item info."""
    fix_plan_path = os.path.join(os.path.dirname(__file__), "..", ".ralph", "fix_plan.md")
    if not os.path.exists(fix_plan_path):
        return {"items": [], "sections": {}}

    with open(fix_plan_path) as f:
        content = f.read()

    items = []
    current_priority = "P0"
    pattern = r"^- \[([ x!])\] \*\*(.+?)\*\*(.*)$"

    for line in content.split("\n"):
        # 우선순위 섹션 헤더
        p_match = re.match(r"^## (P[123]):", line)
        if p_match:
            current_priority = p_match.group(1)
            continue

        # 태스크 항목
        match = re.match(pattern, line)
        if match:
            marker = match.group(1)
            title = match.group(2).strip()
            status = "done" if marker == "x" else ("skipped" if marker == "!" else "incomplete")
            items.append({
                "priority": current_priority,
                "title": title,
                "status": status,
            })

    return {"items": items}


def get_changed_files_summary() -> str:
    """Get summary of changed files from git."""
    project_dir = os.path.join(os.path.dirname(__file__), "..")
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD~5", "HEAD"],
            capture_output=True, text=True, cwd=project_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            # 마지막 줄이 summary line
            return lines[-1].strip() if lines else ""
    except Exception:
        pass
    return ""


def get_recent_commits(n: int = 5) -> list[str]:
    """Get recent commit messages."""
    project_dir = os.path.join(os.path.dirname(__file__), "..")
    try:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{n}"],
            capture_output=True, text=True, cwd=project_dir,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    except Exception:
        pass
    return []


def build_ralph_report(iterations: str | None = None, test_result: str | None = None) -> str:
    """Build a detailed Ralph Loop completion report."""
    plan = parse_fix_plan()
    detailed = parse_fix_plan_detailed()
    today = date.today().isoformat()

    lines = []
    lines.append("*🤖 Ralph Loop 완료 보고*")
    lines.append(f"📅 {today}")
    lines.append("")

    # 작업 항목별 상세 현황
    lines.append("*📋 작업 상세*")
    for item in detailed["items"]:
        if item["status"] == "done":
            emoji = "✅"
        elif item["status"] == "skipped":
            emoji = "⚠️"
        else:
            emoji = "❌"
        lines.append(f"  {emoji} [{item['priority']}] {item['title']}")
    lines.append("")

    # 통계
    done = sum(1 for i in detailed["items"] if i["status"] == "done")
    total = len(detailed["items"])
    lines.append(f"*📊 진행률: {done}/{total}*")

    if iterations:
        lines.append(f"🔄 반복: {iterations}회")

    if test_result:
        lines.append(f"🧪 테스트: {test_result}")

    # 변경 파일 요약
    file_summary = get_changed_files_summary()
    if file_summary:
        lines.append(f"📁 변경: {file_summary}")

    # 최근 커밋
    commits = get_recent_commits(5)
    if commits:
        lines.append("")
        lines.append("*🔨 주요 커밋*")
        for c in commits:
            lines.append(f"  • {c}")

    lines.append("")
    if plan["incomplete"] == 0 and total > 0:
        lines.append("🎉 *모든 작업 완료!*")
    elif plan["incomplete"] > 0:
        lines.append(f"⏳ 미완료 {plan['incomplete']}개 남음")

    return "\n".join(lines)


def cmd_message(args):
    """Send a simple message."""
    token, chat_id = get_env()
    result = send_message(token, chat_id, args.message)
    if result.get("ok"):
        print("SENT: Message delivered successfully.")
    else:
        print(f"FAILED: {result}", file=sys.stderr)
        sys.exit(1)


def cmd_ralph_report(args):
    """Send a Ralph Loop completion report."""
    token, chat_id = get_env()
    text = build_ralph_report(
        iterations=args.iterations,
        test_result=args.test_result,
    )
    result = send_message(token, chat_id, text)
    if result.get("ok"):
        print("SENT: Ralph report delivered successfully.")
    else:
        print(f"FAILED: {result}", file=sys.stderr)
        sys.exit(1)


def build_pipeline_report(iterations: str | None = None, test_result: str | None = None) -> str:
    """Build a detailed pipeline completion report from .pipeline_result.json."""
    result_path = os.path.join(os.path.dirname(__file__), "..", ".ralph", ".pipeline_result.json")
    today = date.today().isoformat()

    lines = []
    lines.append("*🚀 자동 개발 파이프라인 완료*")
    lines.append(f"📅 {today}")
    lines.append("")

    # .pipeline_result.json이 있으면 상세 정보 사용
    if os.path.exists(result_path):
        with open(result_path) as f:
            data = json.load(f)

        tasks = data.get("tasks", {})
        done_count = data.get("done_count", 0)
        fail_count = data.get("fail_count", 0)

        lines.append("*📋 요구사항 처리 결과*")
        for title, info in tasks.items():
            priority = info.get("priority", "P2")
            status = info.get("status", "incomplete")
            details = info.get("details", [])

            if status == "done":
                emoji = "✅"
                status_text = "완료"
            elif status == "skipped":
                emoji = "⚠️"
                status_text = "건너뜀"
            else:
                emoji = "❌"
                status_text = "미완료"

            lines.append(f"  {emoji} *[{priority}] {title}* — {status_text}")

            # 구현 상세 (최대 3줄)
            for detail in details[:3]:
                lines.append(f"      └ {detail}")

        lines.append("")
        lines.append(f"*📊 결과: 완료 {done_count}건 / 실패 {fail_count}건*")
    else:
        # fallback: fix_plan.md 기반
        detailed = parse_fix_plan_detailed()
        lines.append("*📋 작업 상세*")
        for item in detailed["items"]:
            if item["status"] == "done":
                emoji = "✅"
            elif item["status"] == "skipped":
                emoji = "⚠️"
            else:
                emoji = "❌"
            lines.append(f"  {emoji} [{item['priority']}] {item['title']}")

        done = sum(1 for i in detailed["items"] if i["status"] == "done")
        total = len(detailed["items"])
        lines.append(f"\n*📊 진행률: {done}/{total}*")

    if iterations:
        lines.append(f"🔄 반복: {iterations}회")

    if test_result:
        lines.append(f"🧪 테스트: {test_result}")

    # 변경 파일 요약
    file_summary = get_changed_files_summary()
    if file_summary:
        lines.append(f"📁 변경: {file_summary}")

    # 최근 커밋
    commits = get_recent_commits(5)
    if commits:
        lines.append("")
        lines.append("*🔨 주요 커밋*")
        for c in commits:
            lines.append(f"  • {c}")

    # 최종 상태
    has_failures = False
    if os.path.exists(result_path):
        with open(result_path) as f2:
            d = json.load(f2)
        has_failures = d.get("fail_count", 0) > 0
        fc = d.get("fail_count", 0)

    lines.append("")
    if has_failures:
        lines.append(f"⏳ 실패 {fc}건 — Backlog로 이동됨")
    else:
        lines.append("🎉 *모든 요구사항 처리 완료!*")

    return "\n".join(lines)


def cmd_pipeline_report(args):
    """Send a pipeline completion report."""
    token, chat_id = get_env()
    text = build_pipeline_report(
        iterations=args.iterations,
        test_result=args.test_result,
    )
    result = send_message(token, chat_id, text)
    if result.get("ok"):
        print("SENT: Pipeline report delivered successfully.")
    else:
        print(f"FAILED: {result}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Telegram notification for Ralph Loop")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--message", help="Send a simple text message")
    group.add_argument("--ralph-report", action="store_true", help="Send Ralph Loop completion report")
    group.add_argument("--pipeline-report", action="store_true", help="Send pipeline completion report (detailed)")

    parser.add_argument("--iterations", help="Number of iterations completed")
    parser.add_argument("--test-result", help="Test result summary")

    args = parser.parse_args()

    if args.message:
        cmd_message(args)
    elif args.ralph_report:
        cmd_ralph_report(args)
    elif args.pipeline_report:
        cmd_pipeline_report(args)


if __name__ == "__main__":
    main()
