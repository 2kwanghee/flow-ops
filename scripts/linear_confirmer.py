#!/usr/bin/env python3
"""Linear Confirm 상태 이슈를 main 브랜치에 머지.

Usage:
  python3 scripts/linear_confirmer.py
  python3 scripts/linear_confirmer.py --dry-run

Exit codes:
  0 — 정상 (Confirm 처리 완료 또는 없음)
  1 — 에러
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from linear_client import (
    get_env,
    linear_request,
    find_state_id,
    from_linear_priority,
    PROJECT_DIR,
)


def fetch_confirmed_issues(api_key: str, team_id: str) -> list[dict]:
    """Fetch all issues with state 'Confirm'."""
    query = """
    query($teamId: ID!) {
        issues(
            filter: {
                team: { id: { eq: $teamId } }
                state: { name: { eq: "Confirm" } }
            }
            orderBy: createdAt
        ) {
            nodes {
                id
                identifier
                title
                priority
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
    identifier = issue["identifier"]
    return {
        "issue_id": issue["id"],
        "identifier": identifier,
        "title": issue["title"],
        "branch": f"ralph/{identifier}",
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
    code, _ = git_run("rev-parse", "--verify", branch)
    return code == 0


def get_branch_commits(branch: str, base: str = "main") -> str:
    _, output = git_run("log", "--oneline", f"{base}..{branch}")
    return output


def merge_branch(branch: str) -> tuple[bool, str]:
    code, output = git_run("merge", branch, "--no-ff",
                           "-m", f"merge: {branch} (Linear Confirm)")
    return code == 0, output


def merge_pr(branch: str) -> tuple[bool, str]:
    """Merge PR via gh CLI (squash merge)."""
    result = subprocess.run(
        ["gh", "pr", "merge", branch, "--squash", "--delete-branch"],
        capture_output=True, text=True,
        cwd=PROJECT_DIR,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def has_open_pr(branch: str) -> bool:
    """Check if branch has an open PR."""
    result = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "state", "-q", ".state"],
        capture_output=True, text=True,
        cwd=PROJECT_DIR,
    )
    return result.returncode == 0 and result.stdout.strip() == "OPEN"


def delete_branch(branch: str):
    git_run("branch", "-d", branch)


def add_merge_comment(api_key: str, issue_id: str, branch: str):
    """Add a comment noting the merge to main."""
    mutation = """
    mutation($issueId: String!, $body: String!) {
        commentCreate(input: { issueId: $issueId, body: $body }) {
            comment { id }
        }
    }
    """
    linear_request(api_key, mutation, {
        "issueId": issue_id,
        "body": f"Confirmed and merged `{branch}` → `main`.",
    })


def send_telegram(message: str):
    from pipeline_config import is_enabled

    if not is_enabled("FLOWOPS_TELEGRAM"):
        return
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
    from pipeline_config import check_enabled

    check_enabled("FLOWOPS_LINEAR_CONFIRM", "Linear Confirm 자동 머지")

    parser = argparse.ArgumentParser(description="Linear Confirm → main 머지")
    parser.add_argument("--dry-run", action="store_true", help="조회만 수행, 머지 없음")
    args = parser.parse_args()

    api_key, team_id = get_env()

    # 1. Confirm 상태 이슈 조회
    issues = fetch_confirmed_issues(api_key, team_id)
    if not issues:
        print("EMPTY: Confirm 이슈 없음.")
        return

    tasks = [extract_task_info(issue) for issue in issues]
    print(f"FOUND: {len(tasks)}개 Confirm 이슈 발견")

    # 2. main 브랜치로 이동
    _, current_branch = git_run("symbolic-ref", "--short", "HEAD")
    if current_branch != "main":
        code, _ = git_run("checkout", "main")
        if code != 0:
            print("ERROR: main 브랜치 체크아웃 실패", file=sys.stderr)
            sys.exit(1)

    merged_tasks = []
    skipped_tasks = []

    for task in tasks:
        print(f"\n── {task['identifier']} {task['title']} ──")
        print(f"   브랜치: {task['branch']}")

        if not branch_exists(task["branch"]):
            print(f"   SKIP: 브랜치 없음 ({task['branch']})")
            skipped_tasks.append(task)
            continue

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

        # PR이 존재하면 gh pr merge, 없으면 로컬 git merge
        if has_open_pr(task["branch"]):
            success, output = merge_pr(task["branch"])
            if success:
                print(f"   MERGED (PR): squash-merge 완료")
                add_merge_comment(api_key, task["issue_id"], task["branch"])
                merged_tasks.append(task)
            else:
                print(f"   ERROR: PR 머지 실패 — {output}")
                skipped_tasks.append(task)
        else:
            # PR 미존재 시 기존 로컬 머지 방식
            success, output = merge_branch(task["branch"])
            if success:
                print(f"   MERGED (local): main에 머지 완료")
                delete_branch(task["branch"])
                print(f"   DELETED: 브랜치 삭제됨")
                add_merge_comment(api_key, task["issue_id"], task["branch"])
                merged_tasks.append(task)
            else:
                print(f"   ERROR: 머지 실패 — {output}")
                # 진행 중인 머지가 있을 때만 abort 시도
                abort_code, _ = git_run("merge", "--abort")
                if abort_code != 0:
                    print(f"   WARN: merge --abort 불필요 (진행 중인 머지 없음)")
                skipped_tasks.append(task)

    # 3. 결과 요약
    print(f"\n{'='*40}")
    print(f"SUMMARY: 머지 {len(merged_tasks)}건, 스킵 {len(skipped_tasks)}건")

    if args.dry_run:
        print("[DRY-RUN] 실제 머지는 수행되지 않았습니다.")
        return

    # 4. Telegram 보고
    if merged_tasks:
        titles = "\n".join(f"  - {t['identifier']} {t['title']}" for t in merged_tasks)
        msg = f"Confirm 머지 완료 ({len(merged_tasks)}건)\n{titles}"
        if skipped_tasks:
            skip_titles = "\n".join(f"  - {t['identifier']} {t['title']}" for t in skipped_tasks)
            msg += f"\n\n스킵 ({len(skipped_tasks)}건)\n{skip_titles}"
        send_telegram(msg)

    print("\nDONE: Confirm 처리 완료.")


if __name__ == "__main__":
    main()
