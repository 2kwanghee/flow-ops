#!/usr/bin/env python3
"""Ralph Loop 완료 후 결과를 Linear 이슈에 보고.

Usage:
  python3 scripts/linear_reporter.py
  python3 scripts/linear_reporter.py --task-id OPS-123
  python3 scripts/linear_reporter.py --dry-run
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from linear_client import get_env, linear_request, find_state_id, PROJECT_DIR

TASK_MAPPING_PATH = os.path.join(PROJECT_DIR, ".ralph", ".task_mapping.json")
FIX_PLAN_PATH = os.path.join(PROJECT_DIR, ".ralph", "fix_plan.md")


def load_task_mapping() -> dict:
    """Load task → Linear issue ID mapping."""
    if not os.path.exists(TASK_MAPPING_PATH):
        print(f"Error: {TASK_MAPPING_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    with open(TASK_MAPPING_PATH) as f:
        return json.load(f)


def parse_fix_plan() -> dict[str, dict]:
    """Parse fix_plan.md to extract per-task results."""
    if not os.path.exists(FIX_PLAN_PATH):
        print(f"Error: {FIX_PLAN_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    with open(FIX_PLAN_PATH) as f:
        content = f.read()

    results = {}
    pattern = r"^- \[([ x!])\] \*\*(.+?)\*\*(.*)$"
    current_title = None
    current_status = None
    current_details = []

    for line in content.split("\n"):
        match = re.match(pattern, line)
        if match:
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
            detail = line.strip().lstrip("- ").strip()
            if detail:
                current_details.append(detail)

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
    status_label = {
        "done": "완료",
        "incomplete": "미완료",
        "skipped": "건너뜀",
    }

    lines = []
    lines.append(f"## 결과: {status_label.get(task_result['status'], '알수없음')}")
    lines.append("")

    if task_result["details"]:
        lines.append("### 구현 내역")
        for detail in task_result["details"]:
            lines.append(f"- {detail}")
        lines.append("")

    if git_summary:
        lines.append("### 관련 커밋")
        lines.append("```")
        for commit_line in git_summary.split("\n")[:5]:
            lines.append(commit_line)
        lines.append("```")
        lines.append("")

    if test_summary:
        lines.append(f"**테스트:** {test_summary}")

    return "\n".join(lines)


def update_issue_result(api_key: str, team_id: str, issue_id: str, report_text: str, status: str):
    """Update Linear issue: add comment with report and change state."""
    # 1. 코멘트로 결과 보고 추가
    comment_mutation = """
    mutation($issueId: String!, $body: String!) {
        commentCreate(input: { issueId: $issueId, body: $body }) {
            comment { id }
        }
    }
    """
    linear_request(api_key, comment_mutation, {
        "issueId": issue_id,
        "body": report_text[:10000],
    })

    # 2. 상태 변경 (Done 또는 Backlog)
    linear_status = "Done" if status == "done" else "Backlog"
    state_id = find_state_id(api_key, team_id, linear_status)
    if state_id:
        update_mutation = """
        mutation($issueId: String!, $stateId: String!) {
            issueUpdate(id: $issueId, input: { stateId: $stateId }) {
                issue { id identifier state { name } }
            }
        }
        """
        linear_request(api_key, update_mutation, {
            "issueId": issue_id,
            "stateId": state_id,
        })


def main():
    import argparse
    from pipeline_config import check_enabled

    check_enabled("FLOWOPS_LINEAR_REPORT", "Linear 결과 보고")

    parser = argparse.ArgumentParser(description="Ralph Loop 결과 Linear 보고")
    parser.add_argument("--dry-run", action="store_true", help="조회만 수행, 변경 없음")
    parser.add_argument("--task-id", help="특정 태스크만 리포트 (identifier, e.g. OPS-123)")
    args = parser.parse_args()

    api_key, team_id = get_env()
    mapping = load_task_mapping()

    # --task-id 지정 시 해당 태스크만 필터링
    if args.task_id:
        mapping = {
            title: meta for title, meta in mapping.items()
            if meta.get("identifier") == args.task_id
        }
        if not mapping:
            print(f"Error: task-id '{args.task_id}'에 해당하는 태스크 없음.", file=sys.stderr)
            sys.exit(1)

    plan_results = parse_fix_plan()

    git_summary = get_git_summary()
    test_summary = get_test_summary()

    done_count = 0
    fail_count = 0

    plan_results_stripped = {k.strip(): v for k, v in plan_results.items()}

    for title, meta in mapping.items():
        issue_id = meta["issue_id"]
        identifier = meta.get("identifier", "?")
        task_result = plan_results.get(title) or plan_results_stripped.get(title.strip())

        if not task_result:
            print(f"WARN: fix_plan.md에서 '{title}' 항목을 찾을 수 없음. incomplete 처리.")
            task_result = {"status": "incomplete", "details": ["fix_plan에서 항목을 찾을 수 없음"]}

        report_text = build_report_text(title, task_result, git_summary, test_summary)

        if args.dry_run:
            print(f"\n--- {identifier} {title} ({task_result['status']}) ---")
            print(f"Issue ID: {issue_id}")
            print(f"결과보고:\n{report_text}")
            continue

        update_issue_result(api_key, team_id, issue_id, report_text, task_result["status"])
        print(f"REPORTED: [{task_result['status']}] {identifier} {title}")
        if task_result["status"] == "done":
            done_count += 1
        else:
            fail_count += 1

    print(f"\nSUMMARY: 완료 {done_count}건, 미완료/실패 {fail_count}건")

    # 결과를 JSON으로 저장 (텔레그램 보고용)
    summary_path = os.path.join(PROJECT_DIR, ".ralph", ".pipeline_result.json")
    from datetime import datetime, timezone
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
