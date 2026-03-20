#!/usr/bin/env python3
"""Notion daily log & task tracker for Sales Manager project.

Subcommands:
  log     - Create a daily work log entry
  task    - Create a future task entry
  list    - Query existing entries (filter by status)
  update  - Update status of an existing entry
"""

import argparse
import json
import os
import sys
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import HTTPError

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"


def get_env():
    """Load credentials from .env file (priority) or env vars."""
    api_key = None
    db_id = None

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
                if k == "NOTION_API_KEY":
                    api_key = v
                elif k == "NOTION_DATABASE_ID":
                    db_id = v

    # .env에 없으면 환경변수에서 읽는다
    if not api_key:
        api_key = os.getenv("NOTION_API_KEY")
    if not db_id:
        db_id = os.getenv("NOTION_DATABASE_ID")

    if not api_key or not db_id:
        print("Error: NOTION_API_KEY and NOTION_DATABASE_ID required.", file=sys.stderr)
        sys.exit(1)

    return api_key, db_id


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
        sys.exit(1)


def build_blocks(text: str, heading: str = "요청사항") -> list[dict]:
    """Build structured Notion page body: heading + content paragraph."""
    blocks = [
        {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": heading}}],
            },
        },
    ]
    content = text.strip()
    if content:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": content[:2000]}}],
            },
        })
    return blocks


# ── log ──────────────────────────────────────────────────────────────────

def cmd_log(args, api_key, db_id):
    """Create a daily work log entry."""
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    properties = {
        "작업 이름": {"title": [{"text": {"content": args.title}}]},
        "마감일": {"date": {"start": args.date}},
        "결과보고": {"rich_text": [{"text": {"content": args.summary[:2000]}}]},
        "상태": {"status": {"name": "Done"}},
    }
    if tags:
        properties["작업 유형"] = {"multi_select": [{"name": t} for t in tags]}

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": build_blocks(args.summary, heading="결과보고"),
    }

    result = notion_request(api_key, "POST", "/pages", payload)
    page_url = result.get("url", "")
    print(f"LOG_CREATED: {page_url}")
    return page_url


# ── task ─────────────────────────────────────────────────────────────────

def cmd_task(args, api_key, db_id):
    """Create a future task entry."""
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    properties = {
        "작업 이름": {"title": [{"text": {"content": args.title}}]},
        "마감일": {"date": {"start": args.date}},
        "요청사항": {"rich_text": [{"text": {"content": args.summary[:2000]}}]},
        "상태": {"status": {"name": args.status}},
    }
    if tags:
        properties["작업 유형"] = {"multi_select": [{"name": t} for t in tags]}

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": build_blocks(args.summary, heading="요청사항"),
    }

    result = notion_request(api_key, "POST", "/pages", payload)
    page_url = result.get("url", "")
    print(f"TASK_CREATED: {page_url}")
    return page_url


# ── list ─────────────────────────────────────────────────────────────────

def cmd_list(args, api_key, db_id):
    """Query entries from the Notion database."""
    filters = []

    if args.status:
        filters.append({
            "property": "상태",
            "status": {"equals": args.status}
        })

    body = {"sorts": [{"property": "마감일", "direction": "descending"}]}
    if len(filters) == 1:
        body["filter"] = filters[0]
    elif len(filters) > 1:
        body["filter"] = {"and": filters}

    result = notion_request(api_key, "POST", f"/databases/{db_id}/query", body)
    pages = result.get("results", [])

    if not pages:
        print("No entries found.")
        return

    for page in pages:
        props = page["properties"]
        title = props.get("작업 이름", {}).get("title", [{}])
        title_text = title[0].get("text", {}).get("content", "Untitled") if title else "Untitled"
        status = props.get("상태", {}).get("status", {})
        status_name = status.get("name", "-") if status else "-"
        date_prop = props.get("마감일", {}).get("date", {})
        date_str = date_prop.get("start", "-") if date_prop else "-"
        page_id = page["id"]

        print(f"[{status_name}] {date_str} | {title_text} | id:{page_id}")


# ── update ───────────────────────────────────────────────────────────────

def cmd_update(args, api_key, _db_id):
    """Update the status of an existing entry."""
    payload = {
        "properties": {
            "상태": {"status": {"name": args.status}}
        }
    }

    result = notion_request(api_key, "PATCH", f"/pages/{args.page_id}", payload)
    page_url = result.get("url", "")
    print(f"UPDATED: {page_url}")


# ── main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Notion daily log & task tracker")
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
    p_task.add_argument("--status", default="Todo", choices=["Todo", "In progress", "Backlog"])
    p_task.add_argument("--date", default=str(date.today()))

    # list
    p_list = sub.add_parser("list", help="Query entries")
    p_list.add_argument("--status", default="", help="Filter by status (Done/In Progress/Todo/Backlog)")

    # update
    p_update = sub.add_parser("update", help="Update entry status")
    p_update.add_argument("--page-id", required=True)
    p_update.add_argument("--status", required=True, choices=["Done", "In progress", "Todo", "Backlog"])

    args = parser.parse_args()
    api_key, db_id = get_env()

    if args.command == "log":
        cmd_log(args, api_key, db_id)
    elif args.command == "task":
        cmd_task(args, api_key, db_id)
    elif args.command == "list":
        cmd_list(args, api_key, db_id)
    elif args.command == "update":
        cmd_update(args, api_key, db_id)


if __name__ == "__main__":
    main()
