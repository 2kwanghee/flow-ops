#!/usr/bin/env bash
# Ralph Loop Stop Hook — 완료 조건 검증
# Claude가 Stop 시도할 때 실행됨.
# fix_plan.md의 미완료 항목, 테스트, 린트를 확인한다.
# 미충족 시 {"decision": "block", "reason": "..."} 출력 -> 루프 계속
# 충족 시 종료 허용

set -euo pipefail

# git worktree 환경에서도 올바른 프로젝트 루트 감지
PROJECT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || (cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd))"

# 모듈 토글 체크
source "$PROJECT_DIR/scripts/pipeline_config.sh" 2>/dev/null || true
if ! is_enabled "FLOWOPS_RALPH_STOP_HOOK" 2>/dev/null; then
  echo '{"decision": "allow", "reason": "Ralph Stop Hook 비활성화됨 (FLOWOPS_RALPH_STOP_HOOK=false)"}'
  exit 0
fi

FIX_PLAN="$PROJECT_DIR/.ralph/fix_plan.md"
STATE_FILE="$PROJECT_DIR/.ralph/.iteration_count"

# ── iteration 카운터 ──
if [ -f "$STATE_FILE" ]; then
  COUNT=$(cat "$STATE_FILE")
else
  COUNT=0
fi
COUNT=$((COUNT + 1))
echo "$COUNT" > "$STATE_FILE"

# max-iterations 확인 (환경변수로 전달, 기본 30)
MAX_ITER="${RALPH_MAX_ITERATIONS:-30}"
if [ "$COUNT" -gt "$MAX_ITER" ]; then
  if is_enabled "FLOWOPS_TELEGRAM" 2>/dev/null; then
    python3 "$PROJECT_DIR/scripts/telegram_notify.py" \
      --ralph-report \
      --iterations "${COUNT}/${MAX_ITER} (max 도달)" 2>/dev/null || true
  fi
  echo "{\"decision\": \"allow\", \"reason\": \"max-iterations($MAX_ITER) 도달. 강제 종료.\"}"
  exit 0
fi

# ── <promise>BLOCKED</promise> 감지 (stdin에서 Claude 출력 확인) ──
# Stop hook은 Claude 출력을 stdin으로 받지 않으므로, BLOCKED는 PROMPT.md 규칙으로 처리

# ── 우선순위별 미완료 항목 확인 ──
# P1 -> P2 -> P3 순서로 확인
for PRIORITY in "P1" "P2" "P3"; do
  # 해당 섹션의 미완료 항목 카운트
  NEXT_SECTION=""
  case "$PRIORITY" in
    P1) NEXT_SECTION="## P2:" ;;
    P2) NEXT_SECTION="## P3:" ;;
    P3) NEXT_SECTION="## 진행 로그" ;;  # P3 이후 섹션
  esac

  INCOMPLETE=$(sed -n "/^## ${PRIORITY}:/,/^${NEXT_SECTION}/p" "$FIX_PLAN" 2>/dev/null | grep -c '^\- \[ \]' || true)

  if [ "$INCOMPLETE" -gt 0 ]; then
    echo "{\"decision\": \"block\", \"reason\": \"[iteration ${COUNT}/${MAX_ITER}] fix_plan.md ${PRIORITY}에 미완료 항목 ${INCOMPLETE}개 남음. 계속 작업하라.\"}"
    exit 0
  fi
done

# ── 테스트 확인 ──
cd "$PROJECT_DIR/backend"
TEST_RESULT=$(.venv/bin/python -m pytest --tb=no -q 2>&1 | tail -1 || true)

if echo "$TEST_RESULT" | grep -q "failed"; then
  echo "{\"decision\": \"block\", \"reason\": \"[iteration ${COUNT}/${MAX_ITER}] 테스트 실패: $TEST_RESULT. 수정하라.\"}"
  exit 0
fi

# ── 린트 확인 ──
LINT_RESULT=$(.venv/bin/ruff check . 2>&1 | tail -1 || true)

if echo "$LINT_RESULT" | grep -qE "[0-9]+ error|Found [0-9]+"; then
  if ! echo "$LINT_RESULT" | grep -q "All checks passed"; then
    echo "{\"decision\": \"block\", \"reason\": \"[iteration ${COUNT}/${MAX_ITER}] 린트 에러: $LINT_RESULT. 수정하라.\"}"
    exit 0
  fi
fi

# ── 모든 조건 충족 -> 종료 허용 ──
# Telegram 상세 완료 보고 전송
if is_enabled "FLOWOPS_TELEGRAM" 2>/dev/null; then
  # 파이프라인 결과 파일이 있으면 상세 보고, 없으면 기본 보고
  if [ -f "$PROJECT_DIR/.ralph/.task_mapping.json" ]; then
    python3 "$PROJECT_DIR/scripts/telegram_notify.py" \
      --pipeline-report \
      --iterations "$COUNT" \
      --test-result "$TEST_RESULT" 2>/dev/null || true
  else
    python3 "$PROJECT_DIR/scripts/telegram_notify.py" \
      --ralph-report \
      --iterations "$COUNT" \
      --test-result "$TEST_RESULT" 2>/dev/null || true
  fi
fi

# iteration 카운터 정리
rm -f "$STATE_FILE"
echo "{\"decision\": \"allow\", \"reason\": \"[iteration ${COUNT}] 전체 완료. P1~P3 완료, 테스트 통과, 린트 통과.\"}"
exit 0
