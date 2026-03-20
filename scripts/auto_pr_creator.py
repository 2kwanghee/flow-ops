#!/usr/bin/env python3
"""Ralph Loop 완료 후 자동 PR 생성.

태스크 브랜치에서 main으로의 PR을 gh CLI로 생성한다.
PR body에 Linear URL, fix_plan 결과, 테스트 요약을 포함.

Usage:
  python3 scripts/auto_pr_creator.py --branch ralph/OPS-123
  python3 scripts/auto_pr_creator.py --branch ralph/OPS-123 --auto-merge
  python3 scripts/auto_pr_creator.py --branch ralph/OPS-123 --dry-run
"""

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from linear_client import PROJECT_DIR

TASK_MAPPING_PATH = os.path.join(PROJECT_DIR, ".ralph", ".task_mapping.json")


def run_cmd(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run a command and return (exit_code, output)."""
    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        cwd=cwd or PROJECT_DIR,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


def check_gh_cli() -> bool:
    """Check if gh CLI is installed and authenticated."""
    code, _ = run_cmd(["gh", "auth", "status"])
    return code == 0


def get_branch_info(branch: str) -> dict:
    """Get branch metadata: commits, diff stats."""
    _, commits = run_cmd(["git", "log", "--oneline", f"main..{branch}"])
    _, diff_stat = run_cmd(["git", "diff", "--stat", f"main..{branch}"])
    _, diff_files = run_cmd(["git", "diff", "--name-only", f"main..{branch}"])
    return {
        "commits": commits,
        "diff_stat": diff_stat,
        "changed_files": [f for f in diff_files.split("\n") if f.strip()],
    }


def get_task_mapping(identifier: str) -> dict | None:
    """Load task mapping for a specific issue identifier."""
    if not os.path.exists(TASK_MAPPING_PATH):
        return None
    with open(TASK_MAPPING_PATH) as f:
        mapping = json.load(f)
    for title, meta in mapping.items():
        if meta.get("identifier") == identifier:
            return {**meta, "title": title}
    return None


def get_fix_plan_result(branch: str) -> str:
    """Read fix_plan.md from the worktree or main project."""
    # worktree 내부의 fix_plan 확인
    worktree_plan = os.path.join(PROJECT_DIR, ".worktrees", branch, ".ralph", "fix_plan.md")
    main_plan = os.path.join(PROJECT_DIR, ".ralph", "fix_plan.md")

    plan_path = worktree_plan if os.path.exists(worktree_plan) else main_plan
    if not os.path.exists(plan_path):
        return ""

    with open(plan_path) as f:
        content = f.read()

    # 완료/미완료 항목 추출
    done = re.findall(r"^- \[x\] \*\*(.+?)\*\*", content, re.MULTILINE)
    incomplete = re.findall(r"^- \[ \] \*\*(.+?)\*\*", content, re.MULTILINE)
    skipped = re.findall(r"^- \[!\] \*\*(.+?)\*\*", content, re.MULTILINE)

    lines = []
    for item in done:
        lines.append(f"- [x] {item}")
    for item in incomplete:
        lines.append(f"- [ ] {item}")
    for item in skipped:
        lines.append(f"- [!] {item}")

    return "\n".join(lines) if lines else ""


def get_test_summary() -> str:
    """Get test result summary."""
    backend_dir = os.path.join(PROJECT_DIR, "backend")
    if not os.path.isdir(backend_dir):
        return ""
    code, output = run_cmd(
        [".venv/bin/python", "-m", "pytest", "--tb=no", "-q"],
        cwd=backend_dir,
    )
    lines = output.strip().split("\n")
    return lines[-1] if lines else ""


def extract_identifier(branch: str) -> str:
    """Extract issue identifier from branch name (e.g., ralph/OPS-123 → OPS-123)."""
    parts = branch.split("/")
    return parts[-1] if len(parts) > 1 else branch


def build_pr_body(
    identifier: str,
    task_meta: dict | None,
    fix_plan_result: str,
    test_summary: str,
    branch_info: dict,
) -> str:
    """Build PR body with Linear link, fix plan results, and test summary."""
    lines = []

    # Linear 링크
    lines.append("## Linear Issue")
    if task_meta and task_meta.get("url"):
        lines.append(f"- [{identifier}]({task_meta['url']})")
    else:
        lines.append(f"- {identifier}")
    lines.append("")

    # 작업 요약
    if task_meta:
        lines.append("## Summary")
        lines.append(f"{task_meta.get('title', identifier)}")
        if task_meta.get("description"):
            desc = task_meta["description"]
            # 긴 description은 200자로 자름
            if len(desc) > 200:
                desc = desc[:200] + "..."
            lines.append(f"> {desc}")
        lines.append("")

    # Fix Plan 결과
    if fix_plan_result:
        lines.append("## Fix Plan Result")
        lines.append(fix_plan_result)
        lines.append("")

    # 테스트 결과
    if test_summary:
        lines.append("## Test Result")
        lines.append(f"```\n{test_summary}\n```")
        lines.append("")

    # 변경 파일 통계
    if branch_info.get("diff_stat"):
        lines.append("## Changes")
        lines.append(f"```\n{branch_info['diff_stat']}\n```")
        lines.append("")

    # 커밋 목록
    if branch_info.get("commits"):
        lines.append("## Commits")
        lines.append(f"```\n{branch_info['commits']}\n```")
        lines.append("")

    lines.append("---")
    lines.append("*Auto-generated by Ralph Loop pipeline*")

    return "\n".join(lines)


def push_branch(branch: str) -> bool:
    """Push branch to remote."""
    code, output = run_cmd(["git", "push", "-u", "origin", branch])
    if code != 0:
        print(f"ERROR: git push 실패: {output}", file=sys.stderr)
        return False
    print(f"PUSHED: {branch} → origin")
    return True


def create_pr(branch: str, title: str, body: str, auto_merge: bool = False) -> str | None:
    """Create a PR using gh CLI. Returns PR URL or None."""
    cmd = [
        "gh", "pr", "create",
        "--base", "main",
        "--head", branch,
        "--title", title,
        "--body", body,
    ]

    code, output = run_cmd(cmd)
    if code != 0:
        # PR이 이미 존재하는 경우
        if "already exists" in output.lower():
            print(f"SKIP: PR이 이미 존재합니다.")
            # 기존 PR URL 조회
            code2, url = run_cmd(["gh", "pr", "view", branch, "--json", "url", "-q", ".url"])
            return url if code2 == 0 else None
        print(f"ERROR: PR 생성 실패: {output}", file=sys.stderr)
        return None

    pr_url = output.strip()
    print(f"CREATED: {pr_url}")

    # auto-merge 설정
    if auto_merge:
        code, merge_output = run_cmd([
            "gh", "pr", "merge", branch,
            "--auto", "--squash",
        ])
        if code == 0:
            print(f"AUTO-MERGE: 활성화됨 (CI 통과 시 자동 머지)")
        else:
            print(f"WARN: auto-merge 설정 실패: {merge_output}")

    return pr_url


def main():
    parser = argparse.ArgumentParser(description="Ralph Loop 자동 PR 생성")
    parser.add_argument("--branch", required=True, help="PR 소스 브랜치 (e.g., ralph/OPS-123)")
    parser.add_argument("--auto-merge", action="store_true",
                        help="CI 통과 시 자동 squash-merge 설정")
    parser.add_argument("--dry-run", action="store_true", help="PR body만 출력, 실제 생성 안 함")
    args = parser.parse_args()

    branch = args.branch
    identifier = extract_identifier(branch)

    # gh CLI 확인
    if not args.dry_run and not check_gh_cli():
        print("ERROR: gh CLI 인증 필요. `gh auth login` 실행하세요.", file=sys.stderr)
        sys.exit(1)

    # 브랜치 정보 수집
    branch_info = get_branch_info(branch)
    if not branch_info["commits"]:
        print(f"SKIP: {branch}에 main 대비 커밋이 없음.")
        sys.exit(0)

    # 태스크 메타데이터
    task_meta = get_task_mapping(identifier)

    # Fix Plan 결과
    fix_plan_result = get_fix_plan_result(branch)

    # 테스트 요약
    test_summary = get_test_summary()

    # PR title
    pr_title = f"Ralph: {identifier}"
    if task_meta:
        pr_title = f"Ralph: {identifier} — {task_meta['title']}"
        # 70자 제한
        if len(pr_title) > 70:
            pr_title = pr_title[:67] + "..."

    # PR body
    pr_body = build_pr_body(identifier, task_meta, fix_plan_result, test_summary, branch_info)

    if args.dry_run:
        print(f"\n[DRY-RUN] PR 미리보기:")
        print(f"Title: {pr_title}")
        print(f"Base: main ← Head: {branch}")
        print(f"\nBody:\n{pr_body}")
        sys.exit(0)

    # Push
    if not push_branch(branch):
        sys.exit(1)

    # PR 생성
    pr_url = create_pr(branch, pr_title, pr_body, auto_merge=args.auto_merge)
    if pr_url:
        print(f"\nPR_URL: {pr_url}")

        # Telegram 알림
        try:
            subprocess.run(
                ["python3", os.path.join(PROJECT_DIR, "scripts", "telegram_notify.py"),
                 "--message", f"PR 생성됨: {pr_title}\n{pr_url}"],
                capture_output=True, text=True, cwd=PROJECT_DIR,
            )
        except Exception:
            pass
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
