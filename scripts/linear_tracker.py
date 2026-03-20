#!/usr/bin/env python3
"""Linear 작업 로그 & 태스크 트래커.

Subcommands:
  log     - 작업 로그 이슈 생성 (상태: Done)
  task    - 태스크 이슈 생성
  list    - 이슈 목록 조회 (상태 필터)
  update  - 이슈 상태 변경
"""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from linear_client import (
    get_env,
    linear_request,
    find_state_id,
    to_linear_priority,
    from_linear_priority,
)


# ── log ──────────────────────────────────────────────────────────────────

def cmd_log(args, api_key, team_id):
    """Create a daily work log entry (status: Done)."""
    labels = [t.strip() for t in args.tags.split(",") if t.strip()]

    state_id = find_state_id(api_key, team_id, "Done")
    if not state_id:
        print("Error: 'Done' 상태를 찾을 수 없음.", file=sys.stderr)
        sys.exit(1)

    # 라벨 ID 조회
    label_ids = _resolve_label_ids(api_key, team_id, labels) if labels else []

    description = args.summary[:10000]

    mutation = """
    mutation($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            issue { id identifier title url }
        }
    }
    """
    input_data = {
        "teamId": team_id,
        "title": args.title,
        "description": description,
        "stateId": state_id,
        "dueDate": args.date,
    }
    if label_ids:
        input_data["labelIds"] = label_ids

    data = linear_request(api_key, mutation, {"input": input_data})
    if data and data.get("issueCreate"):
        issue = data["issueCreate"]["issue"]
        print(f"LOG_CREATED: {issue['identifier']} {issue.get('url', '')}")
        return issue.get("url", "")
    return ""


# ── task ─────────────────────────────────────────────────────────────────

def cmd_task(args, api_key, team_id):
    """Create a future task entry."""
    labels = [t.strip() for t in args.tags.split(",") if t.strip()]

    state_id = find_state_id(api_key, team_id, args.status)
    if not state_id:
        print(f"Error: '{args.status}' 상태를 찾을 수 없음.", file=sys.stderr)
        sys.exit(1)

    label_ids = _resolve_label_ids(api_key, team_id, labels) if labels else []

    mutation = """
    mutation($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            issue { id identifier title url }
        }
    }
    """
    input_data = {
        "teamId": team_id,
        "title": args.title,
        "description": args.summary[:10000],
        "stateId": state_id,
        "dueDate": args.date,
    }
    if label_ids:
        input_data["labelIds"] = label_ids

    data = linear_request(api_key, mutation, {"input": input_data})
    if data and data.get("issueCreate"):
        issue = data["issueCreate"]["issue"]
        print(f"TASK_CREATED: {issue['identifier']} {issue.get('url', '')}")
        return issue.get("url", "")
    return ""


# ── list ─────────────────────────────────────────────────────────────────

def cmd_list(args, api_key, team_id):
    """Query issues from the Linear team."""
    if args.status:
        query = """
        query($teamId: ID!, $stateName: String!) {
            issues(
                filter: {
                    team: { id: { eq: $teamId } }
                    state: { name: { eq: $stateName } }
                }
                orderBy: updatedAt
                first: 50
            ) {
                nodes {
                    id identifier title priority dueDate
                    state { name }
                    labels { nodes { name } }
                }
            }
        }
        """
        data = linear_request(api_key, query, {
            "teamId": team_id,
            "stateName": args.status,
        })
    else:
        query = """
        query($teamId: ID!) {
            issues(
                filter: { team: { id: { eq: $teamId } } }
                orderBy: updatedAt
                first: 50
            ) {
                nodes {
                    id identifier title priority dueDate
                    state { name }
                    labels { nodes { name } }
                }
            }
        }
        """
        data = linear_request(api_key, query, {"teamId": team_id})

    if not data:
        print("No entries found.")
        return

    issues = data.get("issues", {}).get("nodes", [])
    if not issues:
        print("No entries found.")
        return

    for issue in issues:
        state_name = issue.get("state", {}).get("name", "-")
        due_date = issue.get("dueDate") or "-"
        priority = from_linear_priority(issue.get("priority", 0))
        identifier = issue["identifier"]
        title = issue["title"]
        issue_id = issue["id"]

        print(f"[{state_name}] {due_date} | {priority} {identifier} {title} | id:{issue_id}")


# ── update ───────────────────────────────────────────────────────────────

def cmd_update(args, api_key, team_id):
    """Update the state of an existing issue."""
    state_id = find_state_id(api_key, team_id, args.status)
    if not state_id:
        print(f"Error: '{args.status}' 상태를 찾을 수 없음.", file=sys.stderr)
        sys.exit(1)

    mutation = """
    mutation($issueId: String!, $stateId: String!) {
        issueUpdate(id: $issueId, input: { stateId: $stateId }) {
            issue { id identifier title url state { name } }
        }
    }
    """
    data = linear_request(api_key, mutation, {
        "issueId": args.issue_id,
        "stateId": state_id,
    })
    if data and data.get("issueUpdate"):
        issue = data["issueUpdate"]["issue"]
        print(f"UPDATED: {issue['identifier']} → {issue['state']['name']} {issue.get('url', '')}")


# ── 라벨 유틸 ────────────────────────────────────────────────────────────

def _resolve_label_ids(api_key: str, team_id: str, label_names: list[str]) -> list[str]:
    """Resolve label names to IDs, creating missing labels."""
    query = """
    query($teamId: String!) {
        team(id: $teamId) {
            labels { nodes { id name } }
        }
    }
    """
    data = linear_request(api_key, query, {"teamId": team_id})
    if not data or not data.get("team"):
        return []

    existing = {l["name"]: l["id"] for l in data["team"]["labels"]["nodes"]}
    ids = []

    for name in label_names:
        if name in existing:
            ids.append(existing[name])
        else:
            # 라벨 생성
            create_mutation = """
            mutation($teamId: String!, $name: String!) {
                issueLabelCreate(input: { teamId: $teamId, name: $name }) {
                    issueLabel { id name }
                }
            }
            """
            result = linear_request(api_key, create_mutation, {
                "teamId": team_id,
                "name": name,
            })
            if result and result.get("issueLabelCreate"):
                ids.append(result["issueLabelCreate"]["issueLabel"]["id"])

    return ids


# ── main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Linear 작업 로그 & 태스크 트래커")
    sub = parser.add_subparsers(dest="command", required=True)

    # log
    p_log = sub.add_parser("log", help="Create daily work log")
    p_log.add_argument("--title", required=True)
    p_log.add_argument("--summary", required=True)
    p_log.add_argument("--tags", default="")
    p_log.add_argument("--date", default=str(date.today()))

    # task
    p_task = sub.add_parser("task", help="Create future task")
    p_task.add_argument("--title", required=True)
    p_task.add_argument("--summary", required=True)
    p_task.add_argument("--tags", default="")
    p_task.add_argument("--status", default="Todo",
                        choices=["Todo", "In Progress", "Backlog", "Queued"])
    p_task.add_argument("--date", default=str(date.today()))

    # list
    p_list = sub.add_parser("list", help="Query issues")
    p_list.add_argument("--status", default="",
                        help="Filter by state (Done/In Progress/Todo/Backlog/Queued/Confirm)")

    # update
    p_update = sub.add_parser("update", help="Update issue state")
    p_update.add_argument("--issue-id", required=True, help="Linear issue UUID")
    p_update.add_argument("--status", required=True,
                          choices=["Done", "In Progress", "Todo", "Backlog", "Queued", "Confirm"])

    args = parser.parse_args()
    api_key, team_id = get_env()

    if args.command == "log":
        cmd_log(args, api_key, team_id)
    elif args.command == "task":
        cmd_task(args, api_key, team_id)
    elif args.command == "list":
        cmd_list(args, api_key, team_id)
    elif args.command == "update":
        cmd_update(args, api_key, team_id)


if __name__ == "__main__":
    main()
