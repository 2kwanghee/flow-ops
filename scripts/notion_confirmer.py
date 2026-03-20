#!/usr/bin/env python3
"""Notion Confirm 상태 태스크를 main 브랜치에 머지.

사용자가 Notion에서 Done → Confirm으로 변경한 태스크의 코드를
해당 태스크 브랜치에서 main으로 머지하고 커밋을 확정한다.

Usage:
  # Confirm 레코드 조회 → 브랜치 머지 → main 커밋 확정
  python3 scripts/notion_confirmer.py

  # 건조 실행
  python3 scripts/notion_confirmer.py --dry-run

Exit codes:
  0 — 정상 (Confirm 처리 완료 또는 없음)
  1 — 에러

Cron:
  0 12 * * 1-5  python3 /mnt/c/sales-manager/scripts/notion_confirmer.py >> logs/confirmer.log 2>&1
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..")


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
        return None


def fetch_confirmed_tasks(api_key: str, db_id: str) -> list[dict]:
    """Fetch all records with status 'Confirm'."""
    body = {
        "filter": {
            "property": "상태",
            "status": {"equals": "Confirm"},
        },
        "sorts": [
            {"property": "우선순위", "direction": "ascending"},
        ],
    }
    result = notion_request(api_key, "POST", f"/databases/{db_id}/query", body)
    if not result:
        return []
    return result.get("results", [])


def extract_task_info(page: dict) -> dict:
    """Extract task information from a Notion page."""
    props = page["properties"]

    title_arr = props.get("작업 이름", {}).get("title", [])
    title = title_arr[0]["text"]["content"] if title_arr else "Untitled"

    page_id = page["id"]
    page_id_short = page_id.replace("-", "")[:8]
    branch = f"ralph/task-{page_id_short}"

    return {
        "page_id": page_id,
        "page_id_short": page_id_short,
        "title": title,
        "branch": branch,
    }


def git_run(*args: str) -> tuple[int, str]:
    """Run a git command and return (exit_code, output)."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True,
        cwd=PROJECT_DIR,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def branch_exists(branch: str) -> bool:
    """Check if a git branch exists."""
    code, _ = git_run("rev-parse", "--verify", branch)
    return code == 0


def get_branch_commits(branch: str, base: str = "main") -> str:
    """Get commit log for a branch relative to base."""
    _, output = git_run("log", "--oneline", f"{base}..{branch}")
    return output


def merge_branch(branch: str) -> tuple[bool, str]:
    """Merge a branch into current branch (main)."""
    code, output = git_run("merge", branch, "--no-ff",
                           "-m", f"merge: {branch} (Notion Confirm)")
    return code == 0, output


def delete_branch(branch: str):
    """Delete a local branch."""
    git_run("branch", "-d", branch)


def update_notion_confirmed(api_key: str, page_id: str):
    """Update Notion page: set 처리일시 to now after confirm merge."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "properties": {
            "처리일시": {"date": {"start": now}},
        }
    }
    notion_request(api_key, "PATCH", f"/pages/{page_id}", payload)


def send_telegram(message: str):
    """Send Telegram notification."""
    try:
        subprocess.run(
            ["python3", os.path.join(PROJECT_DIR, "scripts", "telegram_notify.py"),
             "--message", message],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
    except Exception:
        pass


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Notion Confirm → main 머지")
    parser.add_argument("--dry-run", action="store_true", help="조회만 수행, 머지 없음")
    args = parser.parse_args()

    api_key, db_id = get_env()

    # 1. Confirm 상태 레코드 조회
    pages = fetch_confirmed_tasks(api_key, db_id)
    if not pages:
        print("EMPTY: Confirm 레코드 없음.")
        return

    tasks = [extract_task_info(page) for page in pages]
    print(f"FOUND: {len(tasks)}개 Confirm 레코드 발견")

    # 2. main 브랜치로 이동
    current_code, current_branch = git_run("symbolic-ref", "--short", "HEAD")
    if current_branch != "main":
        code, _ = git_run("checkout", "main")
        if code != 0:
            print("ERROR: main 브랜치 체크아웃 실패", file=sys.stderr)
            sys.exit(1)

    merged_tasks = []
    skipped_tasks = []

    for task in tasks:
        print(f"\n── {task['title']} ──")
        print(f"   브랜치: {task['branch']}")

        # 브랜치 존재 확인
        if not branch_exists(task["branch"]):
            print(f"   SKIP: 브랜치 없음 ({task['branch']})")
            skipped_tasks.append(task)
            continue

        # 브랜치 커밋 확인
        commits = get_branch_commits(task["branch"])
        if not commits:
            print(f"   SKIP: 머지할 커밋 없음")
            skipped_tasks.append(task)
            continue

        print(f"   커밋 목록:")
        for line in commits.split("\n"):
            print(f"     {line}")

        if args.dry_run:
            print(f"   [DRY-RUN] 머지 대상 확인됨")
            continue

        # 머지 실행
        success, output = merge_branch(task["branch"])
        if success:
            print(f"   MERGED: main에 머지 완료")
            # 브랜치 삭제
            delete_branch(task["branch"])
            print(f"   DELETED: 브랜치 삭제됨")
            # Notion 처리일시 업데이트
            update_notion_confirmed(api_key, task["page_id"])
            merged_tasks.append(task)
        else:
            print(f"   ERROR: 머지 실패 — {output}")
            # 머지 충돌 시 abort
            git_run("merge", "--abort")
            skipped_tasks.append(task)

    # 3. 결과 요약
    print(f"\n{'='*40}")
    print(f"SUMMARY: 머지 {len(merged_tasks)}건, 스킵 {len(skipped_tasks)}건")

    if args.dry_run:
        print("[DRY-RUN] 실제 머지는 수행되지 않았습니다.")
        return

    # 4. Telegram 보고
    if merged_tasks:
        titles = "\n".join(f"  - {t['title']}" for t in merged_tasks)
        msg = f"Confirm 머지 완료 ({len(merged_tasks)}건)\n{titles}"
        if skipped_tasks:
            skip_titles = "\n".join(f"  - {t['title']}" for t in skipped_tasks)
            msg += f"\n\n스킵 ({len(skipped_tasks)}건)\n{skip_titles}"
        send_telegram(msg)

    # 원래 브랜치로 복귀 (main에서 작업했으므로 유지)
    print("\nDONE: Confirm 처리 완료.")


if __name__ == "__main__":
    main()
