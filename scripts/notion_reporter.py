#!/usr/bin/env python3
"""Ralph Loop 완료 후 결과를 Notion 레코드에 보고.

Usage:
  # fix_plan.md 파싱 → 각 Notion 레코드의 결과보고 필드 업데이트
  python3 scripts/notion_reporter.py

  # 건조 실행
  python3 scripts/notion_reporter.py --dry-run
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..")
FIX_PLAN_PATH = os.path.join(PROJECT_DIR, ".ralph", "fix_plan.md")
TASK_MAPPING_PATH = os.path.join(PROJECT_DIR, ".ralph", ".task_mapping.json")


def get_env():
    """Load credentials from .env file or env vars."""
    api_key = None
    env_path = os.path.join(PROJECT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "NOTION_API_KEY":
                    api_key = v
    if not api_key:
        api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        print("Error: NOTION_API_KEY required.", file=sys.stderr)
        sys.exit(1)
    return api_key


def notion_request(api_key: str, method: str, path: str, body: dict | None = None):
    """Make a request to the Notion API."""
    url = f"{NOTION_BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Notion-Version", NOTION_API_VERSION)

    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        err_body = e.read().decode()
        print(f"Notion API Error ({e.code}): {err_body}", file=sys.stderr)
        return None


def load_task_mapping() -> dict:
    """Load task → Notion page ID mapping."""
    if not os.path.exists(TASK_MAPPING_PATH):
        print(f"Error: {TASK_MAPPING_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    with open(TASK_MAPPING_PATH) as f:
        return json.load(f)


def parse_fix_plan() -> dict[str, dict]:
    """Parse fix_plan.md to extract per-task results.

    Returns:
        {task_title: {"status": "done"|"incomplete"|"skipped", "details": [str]}}
    """
    if not os.path.exists(FIX_PLAN_PATH):
        print(f"Error: {FIX_PLAN_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    with open(FIX_PLAN_PATH) as f:
        content = f.read()

    results = {}
    # 각 태스크 항목 파싱: - [x] **제목**, - [ ] **제목**, - [!] **제목**
    pattern = r"^- \[([ x!])\] \*\*(.+?)\*\*(.*)$"
    current_title = None
    current_status = None
    current_details = []

    for line in content.split("\n"):
        match = re.match(pattern, line)
        if match:
            # 이전 태스크 저장
            if current_title:
                results[current_title] = {
                    "status": current_status,
                    "details": current_details,
                }

            marker = match.group(1)
            current_title = match.group(2).strip()
            extra = match.group(3).strip()

            if marker == "x":
                current_status = "done"
            elif marker == "!":
                current_status = "skipped"
            else:
                current_status = "incomplete"

            current_details = []
            if extra:
                current_details.append(extra.lstrip("— -").strip())

        elif current_title and line.strip().startswith("- "):
            # 하위 항목
            detail = line.strip().lstrip("- ").strip()
            if detail:
                current_details.append(detail)

    # 마지막 태스크 저장
    if current_title:
        results[current_title] = {
            "status": current_status,
            "details": current_details,
        }

    return results


def get_git_summary() -> str:
    """Get recent commit summary for the report."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-10"],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def get_test_summary() -> str:
    """Get test result summary."""
    try:
        result = subprocess.run(
            [".venv/bin/python", "-m", "pytest", "--tb=no", "-q"],
            capture_output=True, text=True,
            cwd=os.path.join(PROJECT_DIR, "backend"),
        )
        lines = result.stdout.strip().split("\n")
        return lines[-1] if lines else ""
    except Exception:
        return ""


def build_report_text(title: str, task_result: dict, git_summary: str, test_summary: str) -> str:
    """Build detailed result report text for a single task."""
    status_emoji = {
        "done": "완료",
        "incomplete": "미완료",
        "skipped": "건너뜀",
    }

    lines = []
    lines.append(f"[{status_emoji.get(task_result['status'], '알수없음')}]")
    lines.append("")

    if task_result["details"]:
        lines.append("구현 내역:")
        for detail in task_result["details"]:
            lines.append(f"  - {detail}")
        lines.append("")

    if git_summary:
        lines.append("관련 커밋:")
        for commit_line in git_summary.split("\n")[:5]:
            lines.append(f"  {commit_line}")
        lines.append("")

    if test_summary:
        lines.append(f"테스트: {test_summary}")

    return "\n".join(lines)


def update_notion_result(api_key: str, page_id: str, report_text: str, status: str):
    """Update Notion page with result report and final status."""
    now = datetime.now(timezone.utc).isoformat()

    notion_status = "Done" if status == "done" else "Backlog"

    payload = {
        "properties": {
            "상태": {"status": {"name": notion_status}},
            "결과보고": {"rich_text": [{"text": {"content": report_text[:2000]}}]},
            "처리일시": {"date": {"start": now}},
        }
    }
    return notion_request(api_key, "PATCH", f"/pages/{page_id}", payload)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ralph Loop 결과 Notion 보고")
    parser.add_argument("--dry-run", action="store_true", help="조회만 수행, 변경 없음")
    parser.add_argument("--task-id", help="특정 태스크만 리포트 (page_id_short)")
    args = parser.parse_args()

    api_key = get_env()
    mapping = load_task_mapping()

    # --task-id 지정 시 해당 태스크만 필터링
    if args.task_id:
        mapping = {
            title: meta for title, meta in mapping.items()
            if meta.get("page_id_short") == args.task_id
        }
        if not mapping:
            print(f"Error: task-id '{args.task_id}'에 해당하는 태스크 없음.", file=sys.stderr)
            sys.exit(1)

    plan_results = parse_fix_plan()

    git_summary = get_git_summary()
    test_summary = get_test_summary()

    done_count = 0
    fail_count = 0

    # strip된 키로 plan_results 룩업 테이블 생성 (공백 차이 보정)
    plan_results_stripped = {k.strip(): v for k, v in plan_results.items()}

    for title, meta in mapping.items():
        page_id = meta["page_id"]
        task_result = plan_results.get(title) or plan_results_stripped.get(title.strip())

        if not task_result:
            print(f"WARN: fix_plan.md에서 '{title}' 항목을 찾을 수 없음. incomplete 처리.")
            task_result = {"status": "incomplete", "details": ["fix_plan에서 항목을 찾을 수 없음"]}

        report_text = build_report_text(title, task_result, git_summary, test_summary)

        if args.dry_run:
            print(f"\n--- {title} ({task_result['status']}) ---")
            print(f"Page ID: {page_id}")
            print(f"결과보고:\n{report_text}")
            continue

        result = update_notion_result(api_key, page_id, report_text, task_result["status"])
        if result:
            print(f"REPORTED: [{task_result['status']}] {title}")
            if task_result["status"] == "done":
                done_count += 1
            else:
                fail_count += 1
        else:
            print(f"FAILED: {title} 업데이트 실패")
            fail_count += 1

    print(f"\nSUMMARY: 완료 {done_count}건, 미완료/실패 {fail_count}건")

    # 결과를 JSON으로 저장 (텔레그램 보고용)
    summary_path = os.path.join(PROJECT_DIR, ".ralph", ".pipeline_result.json")
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tasks": {},
        "git_summary": git_summary,
        "test_summary": test_summary,
        "done_count": done_count,
        "fail_count": fail_count,
    }
    for title, meta in mapping.items():
        task_result = plan_results.get(title, {"status": "incomplete", "details": []})
        summary["tasks"][title] = {
            "priority": meta["priority"],
            "status": task_result["status"],
            "details": task_result["details"],
        }
    with open(summary_path, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"SAVED: {summary_path}")


if __name__ == "__main__":
    main()
