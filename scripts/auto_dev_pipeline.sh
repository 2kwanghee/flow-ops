#!/usr/bin/env bash
# 자동 기능 개발 파이프라인 (v4 — Linear + tmux + git worktree 병렬 실행)
#
# 워크플로우:
#   1. Linear Queued 이슈 감지 → 태스크별 fix_plan 생성
#   2. 태스크마다 git worktree + tmux 세션으로 Claude 병렬 실행
#   3. 완료 시 Linear 상태 → Done (main 머지 안 함)
#   4. 사용자가 Linear에서 Confirm으로 변경 → 정오 cron이 main 머지
#
# 사용법:
#   bash scripts/auto_dev_pipeline.sh
#   bash scripts/auto_dev_pipeline.sh --max-turns 5        # 시연용 (짧은 루프)
#   bash scripts/auto_dev_pipeline.sh --max-iterations 50
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# 모듈 토글 로드
source "$PROJECT_DIR/scripts/pipeline_config.sh" 2>/dev/null || true

LOCK_FILE=".ralph/.pipeline_lock"
TASK_MAPPING=".ralph/.task_mapping.json"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# ── 파라미터 ──
MAX_ITERATIONS=30
MAX_TURNS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-iterations)
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    --max-turns)
      MAX_TURNS="$2"
      shift 2
      ;;
    *)
      echo "$LOG_PREFIX 알 수 없는 옵션: $1"
      exit 1
      ;;
  esac
done

# ── 중복 실행 방지 ──
if [ -f "$LOCK_FILE" ]; then
  LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
  if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    echo "$LOG_PREFIX SKIP: 이전 파이프라인 실행 중 (PID: $LOCK_PID)"
    exit 0
  else
    echo "$LOG_PREFIX WARN: 잔류 lock 파일 제거 (PID: $LOCK_PID 종료됨)"
    rm -f "$LOCK_FILE"
  fi
fi

echo $$ > "$LOCK_FILE"

cleanup() {
  rm -f "$LOCK_FILE"
  # 비정상 종료 시 잔류 worktree 정리
  if [ -d "${WORKTREE_BASE:-}" ]; then
    for dir in "$WORKTREE_BASE"/*/; do
      [ -d "$dir" ] && git worktree remove "$dir" --force 2>/dev/null || true
    done
    rmdir "$WORKTREE_BASE" 2>/dev/null || true
  fi
  rm -f "${TASK_LIST_FILE:-}" 2>/dev/null || true
}
trap cleanup EXIT

echo "$LOG_PREFIX ======================================="
echo "$LOG_PREFIX   자동 개발 파이프라인 v4 시작"
echo "$LOG_PREFIX ======================================="

# ── Step 1: Linear 요구사항 감지 (태스크별 분리 모드) ──
if ! is_enabled "FLOWOPS_LINEAR_WATCHER" 2>/dev/null; then
  echo "$LOG_PREFIX SKIP: Linear Watcher 비활성화됨 (FLOWOPS_LINEAR_WATCHER=false)"
  echo "$LOG_PREFIX 수동으로 .ralph/tasks/ 에 fix_plan을 준비하세요."
  exit 0
fi

echo "$LOG_PREFIX [1/3] Linear 요구사항 감지 중 (per-task 모드)..."
WATCHER_OUTPUT=$(python3 scripts/linear_watcher.py --per-task 2>&1) || WATCHER_EXIT=$?
WATCHER_EXIT=${WATCHER_EXIT:-0}

echo "$WATCHER_OUTPUT"

if [ "$WATCHER_EXIT" -eq 2 ]; then
  echo "$LOG_PREFIX DONE: Queued 이슈 없음. 파이프라인 종료."
  exit 0
elif [ "$WATCHER_EXIT" -ne 0 ]; then
  echo "$LOG_PREFIX ERROR: linear_watcher.py 실행 실패 (exit: $WATCHER_EXIT)"
  python3 scripts/telegram_notify.py --message "파이프라인 에러: linear_watcher 실행 실패" 2>/dev/null || true
  exit 1
fi

# ── DB 확인 ──
if ! docker ps 2>/dev/null | grep -q salesmgr-db; then
  echo "$LOG_PREFIX  -> DB 미실행. 시작합니다..."
  docker compose up -d db
  sleep 10
fi

# ── Step 2: 태스크별 Claude 루프 병렬 실행 (tmux + git worktree) ──
echo ""
echo "$LOG_PREFIX [2/3] 태스크별 Claude 루프 병렬 실행..."

# 메인 브랜치 기억
MAIN_BRANCH="main"

# worktree 작업 디렉토리
WORKTREE_BASE="$PROJECT_DIR/.worktrees"
mkdir -p "$WORKTREE_BASE"

# task_mapping 존재 확인 및 백업
if [ ! -f "$TASK_MAPPING" ]; then
  echo "$LOG_PREFIX ERROR: $TASK_MAPPING 파일이 존재하지 않습니다."
  exit 1
fi
cp "$TASK_MAPPING" ".ralph/.task_mapping_full.json"

# 태스크 목록을 임시 파일로 추출 (subshell 문제 회피)
TASK_LIST_FILE=".ralph/.task_list.tmp"
python3 -c "
import json
with open('$TASK_MAPPING') as f:
    m = json.load(f)
with open('$TASK_LIST_FILE', 'w') as out:
    for title, meta in m.items():
        out.write(f\"{meta['identifier']}|{meta['issue_id']}|{meta['branch']}|{title}\n\")
print(f'TASKS: {len(m)}개')
"

TASK_COUNT=$(wc -l < "$TASK_LIST_FILE")
LAUNCHED=0

# Step 2a: 태스크별 tmux 세션 + git worktree 동시 시작
while IFS='|' read -r ISSUE_KEY ISSUE_ID BRANCH TITLE; do
  LAUNCHED=$((LAUNCHED + 1))
  echo ""
  echo "$LOG_PREFIX ── 태스크 $LAUNCHED/$TASK_COUNT: $TITLE ──"
  echo "$LOG_PREFIX    브랜치: $BRANCH"

  WORKTREE_DIR="$WORKTREE_BASE/$BRANCH"

  # git worktree로 독립 작업 디렉토리 생성
  git worktree add "$WORKTREE_DIR" -b "$BRANCH" "$MAIN_BRANCH" 2>/dev/null \
    || git worktree add "$WORKTREE_DIR" "$BRANCH" 2>/dev/null \
    || { echo "$LOG_PREFIX ERROR: worktree 생성 실패: $BRANCH"; continue; }

  # 태스크 파일 복사 (worktree 내부로)
  mkdir -p "$WORKTREE_DIR/.ralph"
  cp ".ralph/tasks/${ISSUE_KEY}.md" "$WORKTREE_DIR/.ralph/fix_plan.md" 2>/dev/null || {
    echo "$LOG_PREFIX ERROR: fix_plan 없음: .ralph/tasks/${ISSUE_KEY}.md"
    git worktree remove "$WORKTREE_DIR" --force 2>/dev/null || true
    continue
  }
  cp ".ralph/PROMPT.md" "$WORKTREE_DIR/.ralph/PROMPT.md" 2>/dev/null || true

  # 단일 태스크 task_mapping 생성 (worktree 내부)
  python3 -c "
import json
with open('.ralph/.task_mapping_full.json') as f:
    m = json.load(f)
for title, meta in m.items():
    if meta['identifier'] == '$ISSUE_KEY':
        single = {title: meta}
        with open('$WORKTREE_DIR/.ralph/.task_mapping.json', 'w') as out:
            json.dump(single, out, ensure_ascii=False, indent=2)
        break
"

  # Linear 상태 → In Progress
  python3 scripts/linear_tracker.py update --issue-id "$ISSUE_ID" --status "In Progress" 2>/dev/null || true

  # tmux 세션으로 Claude 병렬 실행
  SESSION_NAME="ralph-$ISSUE_KEY"
  tmux new-session -d -s "$SESSION_NAME" \
    "cd '$WORKTREE_DIR' && \
     export RALPH_MAX_ITERATIONS=$MAX_ITERATIONS && \
     rm -f .ralph/.iteration_count && \
     claude -p \"\$(cat .ralph/PROMPT.md)\" --dangerously-skip-permissions ${MAX_TURNS:+--max-turns $MAX_TURNS}; \
     cp '$WORKTREE_DIR/.ralph/fix_plan.md' '$PROJECT_DIR/.ralph/fix_plan.md' 2>/dev/null || true; \
     cd '$PROJECT_DIR' && python3 scripts/linear_reporter.py --task-id '$ISSUE_KEY' 2>&1 || true; \
     cd '$PROJECT_DIR' && python3 scripts/auto_pr_creator.py --branch '$BRANCH' --auto-merge 2>&1 || true; \
     echo '[DONE] $TITLE'" \
    || { echo "$LOG_PREFIX ERROR: tmux 세션 생성 실패: $SESSION_NAME"; continue; }

  echo "$LOG_PREFIX    tmux 세션 시작: $SESSION_NAME (max-turns: ${MAX_TURNS:-unlimited})"

done < "$TASK_LIST_FILE"

# Step 2b: 전체 세션 완료 대기
echo ""
echo "$LOG_PREFIX 병렬 실행 중... (tmux list-sessions로 모니터링 가능)"
echo "$LOG_PREFIX 개별 세션 접속: tmux attach -t ralph-XXXXXXXX"
while tmux list-sessions 2>/dev/null | grep -q "^ralph-"; do
  ACTIVE=$(tmux list-sessions 2>/dev/null | grep -c "^ralph-" || echo 0)
  echo "$LOG_PREFIX [$(date '+%H:%M:%S')] 대기 중... 활성 세션: ${ACTIVE}개"
  sleep 60
done

echo "$LOG_PREFIX 모든 tmux 세션 완료."

# Step 2c: worktree 정리
echo "$LOG_PREFIX worktree 정리 중..."
for dir in "$WORKTREE_BASE"/*/; do
  [ -d "$dir" ] && git worktree remove "$dir" --force 2>/dev/null || true
done
rmdir "$WORKTREE_BASE" 2>/dev/null || true

# 임시 파일 정리
rm -f "$TASK_LIST_FILE"

# task_mapping 복원 (Telegram 보고용 — 전체 버전)
cp ".ralph/.task_mapping_full.json" "$TASK_MAPPING"

# ── Step 3: Telegram 완료 보고 ──
echo ""
echo "$LOG_PREFIX [3/3] Telegram 완료 보고 전송..."

if is_enabled "FLOWOPS_TELEGRAM" 2>/dev/null; then
  # 테스트 결과
  if [ -d "$PROJECT_DIR/backend" ]; then
    cd "$PROJECT_DIR/backend"
    TEST_RESULT=$(.venv/bin/python -m pytest --tb=no -q 2>&1 | tail -1 || echo "테스트 실행 실패")
    cd "$PROJECT_DIR"
  else
    TEST_RESULT="backend 디렉토리 없음 (테스트 스킵)"
  fi

  python3 scripts/telegram_notify.py \
    --pipeline-report \
    --iterations "N/A" \
    --test-result "$TEST_RESULT" 2>/dev/null || true
else
  echo "$LOG_PREFIX SKIP: Telegram 알림 비활성화됨"
fi

# ── 잔류 데이터 정리 (Telegram 보고 후 수행) ──
rm -f "$TASK_MAPPING" ".ralph/.task_mapping_full.json" ".ralph/.pipeline_result.json"
rm -rf ".ralph/tasks"

echo ""
echo "$LOG_PREFIX ======================================="
echo "$LOG_PREFIX   파이프라인 완료: $(date '+%Y-%m-%d %H:%M:%S')"
echo "$LOG_PREFIX   각 태스크 브랜치에 작업 보존 — Confirm 대기"
echo "$LOG_PREFIX ======================================="
