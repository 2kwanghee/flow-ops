#!/usr/bin/env python3
"""Linear 요구사항 감지기 — Queued 상태 이슈를 fix_plan.md로 변환.

Usage:
  python3 scripts/linear_watcher.py --per-task
  python3 scripts/linear_watcher.py --dry-run

Exit codes:
  0 — Queued 이슈 발견, fix_plan 생성 완료
  1 — 에러
  2 — Queued 이슈 없음 (정상 종료)
"""

import json
import os
import subprocess
import sys

# linear_client를 같은 디렉토리에서 import
sys.path.insert(0, os.path.dirname(__file__))
from linear_client import (
    get_env,
    linear_request,
    find_state_id,
    from_linear_priority,
    PROJECT_DIR,
)

FIX_PLAN_PATH = os.path.join(PROJECT_DIR, ".ralph", "fix_plan.md")
TASK_MAPPING_PATH = os.path.join(PROJECT_DIR, ".ralph", ".task_mapping.json")
TASKS_DIR = os.path.join(PROJECT_DIR, ".ralph", "tasks")


def fetch_queued_issues(api_key: str, team_id: str) -> list[dict]:
    """Fetch all issues with state 'Queued', sorted by priority."""
    query = """
    query($teamId: ID!) {
        issues(
            filter: {
                team: { id: { eq: $teamId } }
                state: { name: { eq: "Queued" } }
            }
            orderBy: priority
        ) {
            nodes {
                id
                identifier
                title
                description
                priority
                dueDate
                url
                labels { nodes { name } }
                state { id name }
            }
        }
    }
    """
    data = linear_request(api_key, query, {"teamId": team_id})
    if not data:
        return []
    return data.get("issues", {}).get("nodes", [])


def extract_task_info(issue: dict) -> dict:
    """Extract task information from a Linear issue."""
    identifier = issue["identifier"]  # e.g. "OPS-123"
    priority = from_linear_priority(issue.get("priority", 0))
    labels = [l["name"] for l in issue.get("labels", {}).get("nodes", [])]

    return {
        "issue_id": issue["id"],
        "identifier": identifier,
        "title": issue["title"],
        "description": issue.get("description") or "",
        "priority": priority,
        "labels": labels,
        "branch": f"ralph/{identifier}",
        "url": issue.get("url", ""),
    }


def generate_fix_plan(tasks: list[dict]) -> str:
    """Generate fix_plan.md content from task list."""
    lines = [
        "# Ralph Loop — 작업 큐 (Fix Plan)",
        "",
        "> Claude가 이 파일을 읽고 미완료(`- [ ]`) 항목을 순서대로 처리한다.",
        "> 완료 시 `- [x]`로 표시하고 커밋한다.",
        "> `- [!]`는 건너뛴 항목 (사유 기록 필수).",
        "",
        "---",
        "",
    ]

    grouped: dict[str, list[dict]] = {}
    for task in tasks:
        p = task["priority"]
        grouped.setdefault(p, []).append(task)

    for priority in ["P1", "P2", "P3"]:
        group = grouped.get(priority, [])
        if not group:
            continue

        lines.append(f"## {priority}: 기능 요구사항")
        lines.append("")

        for task in group:
            lines.append(f"- [ ] **{task['title']}**")
            if task["description"]:
                # description의 첫 줄만 요약으로 사용
                first_line = task["description"].split("\n")[0].strip()
                lines.append(f"  > 요청사항: {first_line}")
            lines.append("")

        lines.append("---")
        lines.append("")

    lines.append("## 진행 로그")
    lines.append("")
    lines.append("> Ralph가 작업하면서 여기에 기록을 남긴다.")
    lines.append("")
    lines.append("| 시각 | 항목 | 상태 | 비고 |")
    lines.append("|------|------|------|------|")

    return "\n".join(lines)


def generate_single_task_fix_plan(task: dict) -> str:
    """Generate fix_plan.md for a single task."""
    priority = task["priority"]
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
        f"- [ ] **{task['title']}**",
    ]
    if task["description"]:
        lines.append(f"  > 요청사항: {task['description']}")
    lines.extend([
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
    return "\n".join(lines)


def update_issue_state(api_key: str, team_id: str, issue_id: str, state_name: str):
    """Update a Linear issue's workflow state."""
    state_id = find_state_id(api_key, team_id, state_name)
    if not state_id:
        print(f"WARN: '{state_name}' 상태를 찾을 수 없음.", file=sys.stderr)
        return

    mutation = """
    mutation($issueId: String!, $stateId: String!) {
        issueUpdate(id: $issueId, input: { stateId: $stateId }) {
            issue { id identifier state { name } }
        }
    }
    """
    linear_request(api_key, mutation, {"issueId": issue_id, "stateId": state_id})


def save_task_mapping(tasks: list[dict]):
    """Save task → Linear issue ID mapping for later result reporting."""
    mapping = {}
    for task in tasks:
        mapping[task["title"]] = {
            "issue_id": task["issue_id"],
            "identifier": task["identifier"],
            "priority": task["priority"],
            "description": task["description"],
            "branch": task["branch"],
            "url": task.get("url", ""),
        }
    with open(TASK_MAPPING_PATH, "w") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Linear 요구사항 감지기")
    parser.add_argument("--dry-run", action="store_true", help="조회만 수행, 변경 없음")
    parser.add_argument("--per-task", action="store_true",
                        help="태스크별 개별 fix_plan 생성 (상태 미변경)")
    parser.add_argument("--use-gpt-plan", action="store_true",
                        help="ChatGPT FC로 구조화된 fix_plan 생성 (fallback: 기존 방식)")
    args = parser.parse_args()

    api_key, team_id = get_env()

    # 1. Queued 이슈 조회
    issues = fetch_queued_issues(api_key, team_id)
    if not issues:
        print("EMPTY: Queued 이슈 없음.")
        sys.exit(2)

    # 2. 태스크 정보 추출
    tasks = [extract_task_info(issue) for issue in issues]
    print(f"FOUND: {len(tasks)}개 Queued 이슈 발견")
    for t in tasks:
        print(f"  [{t['priority']}] {t['identifier']} {t['title']} → {t['branch']}")

    if args.dry_run:
        if args.per_task:
            for task in tasks:
                print(f"\n[DRY-RUN] {task['title']}:")
                print(generate_single_task_fix_plan(task))
        else:
            print("\n[DRY-RUN] fix_plan.md 미리보기:")
            print(generate_fix_plan(tasks))
        sys.exit(0)

    if args.per_task:
        # 태스크별 개별 fix_plan 생성
        os.makedirs(TASKS_DIR, exist_ok=True)
        for task in tasks:
            task_file = os.path.join(TASKS_DIR, f"{task['identifier']}.md")

            if args.use_gpt_plan:
                # ChatGPT FC로 구조화된 fix_plan 생성 시도
                try:
                    result = subprocess.run(
                        ["python3", os.path.join(os.path.dirname(__file__), "fix_plan_generator.py"),
                         "--title", task["title"],
                         "--description", task.get("description", ""),
                         "--priority", task["priority"],
                         "--output", task_file],
                        capture_output=True, text=True,
                        cwd=PROJECT_DIR,
                    )
                    if result.returncode == 0:
                        print(f"CREATED (GPT): {task_file}")
                        continue
                    else:
                        print(f"WARN: GPT plan 실패, fallback 사용: {result.stderr[:100]}")
                except Exception as e:
                    print(f"WARN: GPT plan 예외, fallback 사용: {e}")

            with open(task_file, "w") as f:
                f.write(generate_single_task_fix_plan(task))
            print(f"CREATED: {task_file}")

        save_task_mapping(tasks)
        print(f"CREATED: {TASK_MAPPING_PATH}")
        print(f"\nREADY: {len(tasks)}개 태스크 개별 fix_plan 생성 완료.")
    else:
        # 전체 fix_plan + 상태 변경
        fix_plan_content = generate_fix_plan(tasks)
        with open(FIX_PLAN_PATH, "w") as f:
            f.write(fix_plan_content)
        print(f"CREATED: {FIX_PLAN_PATH}")

        save_task_mapping(tasks)
        print(f"CREATED: {TASK_MAPPING_PATH}")

        for task in tasks:
            update_issue_state(api_key, team_id, task["issue_id"], "In Progress")
            print(f"UPDATED: [{task['priority']}] {task['identifier']} {task['title']} → In Progress")

        print(f"\nREADY: {len(tasks)}개 작업이 fix_plan.md에 등록되었습니다.")


if __name__ == "__main__":
    main()
