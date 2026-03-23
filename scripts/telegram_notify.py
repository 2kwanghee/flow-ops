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
from datetime import date, datetime
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
                k, v = k.strip(), v.strip().strip("\"'")
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
    now = datetime.now()

    done = sum(1 for i in detailed["items"] if i["status"] == "done")
    skipped = sum(1 for i in detailed["items"] if i["status"] == "skipped")
    incomplete = sum(1 for i in detailed["items"] if i["status"] == "incomplete")
    total = len(detailed["items"])

    # 결과 이모지
    if incomplete == 0 and total > 0:
        result_emoji = "🟢"
        result_text = "전체 완료"
    elif incomplete > 0 and done > 0:
        result_emoji = "🟡"
        result_text = "부분 완료"
    else:
        result_emoji = "🔴"
        result_text = "미완료"

    lines = []
    lines.append(f"{result_emoji} *Ralph Loop — {result_text}*")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🕐 {now.strftime('%Y-%m-%d %H:%M')}")
    if iterations:
        lines.append(f"🔄 반복 횟수: {iterations}회")
    lines.append("")

    # 작업 현황
    if detailed["items"]:
        lines.append("📋 *작업 현황*")
        lines.append("─────────────────")
        current_priority = None
        for item in detailed["items"]:
            if item["priority"] != current_priority:
                current_priority = item["priority"]
                lines.append(f"  *{current_priority}*")
            if item["status"] == "done":
                lines.append(f"    ✅ {item['title']}")
            elif item["status"] == "skipped":
                lines.append(f"    ⏭ {item['title']}")
            else:
                lines.append(f"    ❌ {item['title']}")
        lines.append("")

    # 요약 통계
    lines.append("📊 *결과 요약*")
    lines.append("─────────────────")
    lines.append(f"  완료: {done}건  |  미완료: {incomplete}건  |  스킵: {skipped}건")

    if test_result:
        lines.append(f"  테스트: {test_result}")

    file_summary = get_changed_files_summary()
    if file_summary:
        lines.append(f"  파일: {file_summary}")

    # 최근 커밋
    commits = get_recent_commits(5)
    if commits:
        lines.append("")
        lines.append("🔨 *주요 커밋*")
        lines.append("─────────────────")
        for c in commits:
            lines.append(f"  `{c}`")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

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


def load_task_mapping_for_report() -> dict:
    """Load task_mapping.json for enriching reports with issue metadata."""
    mapping_path = os.path.join(os.path.dirname(__file__), "..", ".ralph", ".task_mapping.json")
    if os.path.exists(mapping_path):
        with open(mapping_path) as f:
            return json.load(f)
    return {}


def build_pipeline_report(iterations: str | None = None, test_result: str | None = None) -> str:
    """Build a detailed pipeline completion report from .pipeline_result.json."""
    result_path = os.path.join(os.path.dirname(__file__), "..", ".ralph", ".pipeline_result.json")
    task_mapping = load_task_mapping_for_report()
    now = datetime.now()

    done_count = 0
    fail_count = 0
    task_lines = []

    # .pipeline_result.json이 있으면 상세 정보 사용
    if os.path.exists(result_path):
        with open(result_path) as f:
            data = json.load(f)

        tasks = data.get("tasks", {})
        done_count = data.get("done_count", 0)
        fail_count = data.get("fail_count", 0)

        for title, info in tasks.items():
            priority = info.get("priority", "P2")
            status = info.get("status", "incomplete")
            details = info.get("details", [])
            meta = task_mapping.get(title, {})
            identifier = meta.get("identifier", "")
            branch = meta.get("branch", "")

            if status == "done":
                emoji = "✅"
            elif status == "skipped":
                emoji = "⏭"
            else:
                emoji = "❌"

            # 이슈 ID + 제목
            id_prefix = f"`{identifier}` " if identifier else ""
            task_lines.append(f"  {emoji} {id_prefix}*{title}*")

            # 브랜치 정보
            if branch:
                task_lines.append(f"      📌 `{branch}`")

            # 구현 상세 (최대 3줄)
            for detail in details[:3]:
                task_lines.append(f"      └ {detail}")
    else:
        # fallback: fix_plan.md 기반
        detailed = parse_fix_plan_detailed()
        for item in detailed["items"]:
            if item["status"] == "done":
                emoji = "✅"
                done_count += 1
            elif item["status"] == "skipped":
                emoji = "⏭"
            else:
                emoji = "❌"
                fail_count += 1
            task_lines.append(f"  {emoji} *[{item['priority']}] {item['title']}*")

    total = done_count + fail_count

    # 결과 이모지
    if fail_count == 0 and total > 0:
        result_emoji = "🟢"
        result_text = "전체 성공"
    elif fail_count > 0 and done_count > 0:
        result_emoji = "🟡"
        result_text = "부분 성공"
    elif total == 0:
        result_emoji = "⚪"
        result_text = "처리 대상 없음"
    else:
        result_emoji = "🔴"
        result_text = "실패"

    lines = []
    lines.append(f"{result_emoji} *자동 개발 파이프라인 — {result_text}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🕐 {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 요구사항 처리 결과
    if task_lines:
        lines.append("📋 *요구사항 처리 결과*")
        lines.append("─────────────────")
        lines.extend(task_lines)
        lines.append("")

    # 요약 통계 블록
    lines.append("📊 *결과 요약*")
    lines.append("─────────────────")
    stat_parts = [f"완료: {done_count}건", f"실패: {fail_count}건"]
    lines.append(f"  {' | '.join(stat_parts)}")

    if iterations and iterations != "N/A":
        lines.append(f"  반복: {iterations}회")

    if test_result:
        lines.append(f"  테스트: {test_result}")

    file_summary = get_changed_files_summary()
    if file_summary:
        lines.append(f"  파일: {file_summary}")

    # 최근 커밋
    commits = get_recent_commits(5)
    if commits:
        lines.append("")
        lines.append("🔨 *주요 커밋*")
        lines.append("─────────────────")
        for c in commits:
            lines.append(f"  `{c}`")

    # 최종 상태
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    if fail_count > 0:
        lines.append(f"⏳ 실패 {fail_count}건 → Backlog 이동")
    elif total > 0:
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
    sys.path.insert(0, os.path.dirname(__file__))
    from pipeline_config import check_enabled

    check_enabled("FLOWOPS_TELEGRAM", "Telegram 알림")

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
