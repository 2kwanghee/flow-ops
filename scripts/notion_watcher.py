#!/usr/bin/env python3
"""Notion 요구사항 감지기 — Queued 상태 레코드를 fix_plan.md로 변환.

Usage:
  # 기존 모드: 전체 Queued → 단일 fix_plan.md → In progress
  python3 scripts/notion_watcher.py

  # 태스크별 분리 모드: 태스크별 개별 fix_plan 생성 (상태 미변경)
  python3 scripts/notion_watcher.py --per-task

  # 건조 실행
  python3 scripts/notion_watcher.py --dry-run

Exit codes:
  0 — Queued 레코드 발견, fix_plan.md 생성 완료
  1 — 에러
  2 — Queued 레코드 없음 (정상 종료)
"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..")
FIX_PLAN_PATH = os.path.join(PROJECT_DIR, ".ralph", "fix_plan.md")
TASK_MAPPING_PATH = os.path.join(PROJECT_DIR, ".ralph", ".task_mapping.json")
TASKS_DIR = os.path.join(PROJECT_DIR, ".ralph", "tasks")


def get_env():
    """Load credentials from .env file or env vars."""
    api_key = None
    db_id = None

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
                elif k == "NOTION_DATABASE_ID":
                    db_id = v

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


def fetch_queued_tasks(api_key: str, db_id: str) -> list[dict]:
    """Fetch all records with status 'Queued', sorted by priority."""
    body = {
        "filter": {
            "property": "상태",
            "status": {"equals": "Queued"},
        },
        "sorts": [
            {"property": "우선순위", "direction": "ascending"},
            {"property": "마감일", "direction": "ascending"},
        ],
    }
    result = notion_request(api_key, "POST", f"/databases/{db_id}/query", body)
    return result.get("results", [])


def extract_task_info(page: dict) -> dict:
    """Extract task information from a Notion page."""
    props = page["properties"]

    title_arr = props.get("작업 이름", {}).get("title", [])
    title = title_arr[0]["text"]["content"] if title_arr else "Untitled"

    desc_arr = props.get("요청사항", {}).get("rich_text", [])
    description = desc_arr[0]["text"]["content"] if desc_arr else ""

    # 페이지 본문(children)에서도 요청사항 읽기
    body_desc = ""
    try:
        page_id = page["id"]
        api_key = page.get("_api_key")  # 외부에서 주입
        if api_key:
            children_res = notion_request(api_key, "GET", f"/blocks/{page_id}/children")
            for block in children_res.get("results", []):
                if block["type"] == "paragraph":
                    texts = block.get("paragraph", {}).get("rich_text", [])
                    for t in texts:
                        body_desc += t.get("plain_text", "")
    except Exception:
        pass

    # 본문 내용이 있고 속성에 없으면 본문 사용
    if not description and body_desc:
        description = body_desc

    priority_obj = props.get("우선순위", {}).get("select")
    priority = priority_obj["name"] if priority_obj else "P2"

    types_arr = props.get("작업 유형", {}).get("multi_select", [])
    task_types = [t["name"] for t in types_arr]

    page_id_short = page["id"].replace("-", "")[:8]

    return {
        "page_id": page["id"],
        "page_id_short": page_id_short,
        "title": title,
        "description": description,
        "priority": priority,
        "task_types": task_types,
        "branch": f"ralph/task-{page_id_short}",
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
                lines.append(f"  > 요청사항: {task['description']}")
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


def update_status(api_key: str, page_id: str, status: str):
    """Update a Notion page status and set 처리일시."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "properties": {
            "상태": {"status": {"name": status}},
            "처리일시": {"date": {"start": now}},
        }
    }
    notion_request(api_key, "PATCH", f"/pages/{page_id}", payload)


def save_task_mapping(tasks: list[dict]):
    """Save task → Notion page ID mapping for later result reporting."""
    mapping = {}
    for task in tasks:
        mapping[task["title"]] = {
            "page_id": task["page_id"],
            "page_id_short": task["page_id_short"],
            "priority": task["priority"],
            "description": task["description"],
            "branch": task["branch"],
        }
    with open(TASK_MAPPING_PATH, "w") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Notion 요구사항 감지기")
    parser.add_argument("--dry-run", action="store_true", help="조회만 수행, 변경 없음")
    parser.add_argument("--per-task", action="store_true",
                        help="태스크별 개별 fix_plan 생성 (상태 미변경)")
    args = parser.parse_args()

    api_key, db_id = get_env()

    # 1. Queued 레코드 조회
    pages = fetch_queued_tasks(api_key, db_id)
    if not pages:
        print("EMPTY: Queued 레코드 없음.")
        sys.exit(2)

    # API key를 페이지에 주입 (본문 읽기용)
    for page in pages:
        page["_api_key"] = api_key

    # 2. 태스크 정보 추출
    tasks = [extract_task_info(page) for page in pages]
    print(f"FOUND: {len(tasks)}개 Queued 레코드 발견")
    for t in tasks:
        print(f"  [{t['priority']}] {t['title']} → {t['branch']}")

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
            task_file = os.path.join(TASKS_DIR, f"{task['page_id_short']}.md")
            with open(task_file, "w") as f:
                f.write(generate_single_task_fix_plan(task))
            print(f"CREATED: {task_file}")

        # task mapping 저장 (브랜치 정보 포함)
        save_task_mapping(tasks)
        print(f"CREATED: {TASK_MAPPING_PATH}")

        # 상태는 변경하지 않음 — 파이프라인이 개별 처리 시 변경
        print(f"\nREADY: {len(tasks)}개 태스크 개별 fix_plan 생성 완료.")
    else:
        # 기존 모드: 전체 fix_plan + 상태 변경
        fix_plan_content = generate_fix_plan(tasks)
        with open(FIX_PLAN_PATH, "w") as f:
            f.write(fix_plan_content)
        print(f"CREATED: {FIX_PLAN_PATH}")

        save_task_mapping(tasks)
        print(f"CREATED: {TASK_MAPPING_PATH}")

        for task in tasks:
            update_status(api_key, task["page_id"], "In progress")
            print(f"UPDATED: [{task['priority']}] {task['title']} → In progress")

        print(f"\nREADY: {len(tasks)}개 작업이 fix_plan.md에 등록되었습니다.")


if __name__ == "__main__":
    main()
