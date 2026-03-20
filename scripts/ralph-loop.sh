#!/usr/bin/env bash
# Ralph Loop 실행 스크립트
# 사용법:
#   bash scripts/ralph-loop.sh                        # 기본 (max 30 iterations)
#   bash scripts/ralph-loop.sh --max-iterations 50    # max 50 iterations
#   nohup bash scripts/ralph-loop.sh > ralph-session.log 2>&1 &  # 오버나이트
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]})/.." && pwd)"
cd "$PROJECT_DIR"

# ── 파라미터 파싱 ──
MAX_ITERATIONS=30
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-iterations)
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    *)
      echo "알 수 없는 옵션: $1"
      echo "사용법: bash scripts/ralph-loop.sh [--max-iterations N]"
      exit 1
      ;;
  esac
done

# Stop Hook에서 사용할 환경변수로 전달
export RALPH_MAX_ITERATIONS="$MAX_ITERATIONS"

echo "======================================="
echo "  Ralph Loop 시작: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  max-iterations: $MAX_ITERATIONS"
echo "======================================="

# ── 1. 사전 점검 ──
echo "[1/4] 사전 점검..."

# DB 확인
if ! docker ps 2>/dev/null | grep -q salesmgr-db; then
  echo "  -> DB 미실행. 시작합니다..."
  docker compose up -d db
  echo "  -> DB 헬스체크 대기 (10초)..."
  sleep 10
fi
echo "  V DB 실행 중"

# 기존 테스트 확인
echo "  -> 기존 테스트 실행..."
cd "$PROJECT_DIR/backend"
if .venv/bin/python -m pytest --tb=no -q 2>&1 | tail -1 | grep -q "passed"; then
  echo "  V 기존 테스트 통과"
else
  echo "  ! 기존 테스트 실패 -- Ralph가 수정할 예정"
fi
cd "$PROJECT_DIR"

# 필수 파일 확인
for f in .ralph/PROMPT.md .ralph/fix_plan.md .claude/settings.json; do
  if [ ! -f "$f" ]; then
    echo "  X 필수 파일 없음: $f"
    exit 1
  fi
done
echo "  V 필수 파일 확인 완료"

# fix_plan 현황
TOTAL=$(grep -c '^\- \[' .ralph/fix_plan.md || echo 0)
DONE=$(grep -c '^\- \[x\]' .ralph/fix_plan.md || echo 0)
echo "  -> fix_plan 현황: 완료 $DONE / $TOTAL"

# ── 2. Ralph 전용 브랜치 생성 ──
echo "[2/4] 브랜치 생성..."
BRANCH="ralph/overnight-$(date +%Y%m%d-%H%M)"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"
  echo "  V 브랜치: $BRANCH"
else
  echo "  ! Git 저장소가 아닙니다. 브랜치 생성 건너뜀"
fi

# ── 3. iteration 카운터 초기화 ──
rm -f .ralph/.iteration_count

# ── 4. Claude 자율 루프 실행 ──
echo "[3/4] Claude 자율 루프 실행..."
echo "  -> PROMPT: .ralph/PROMPT.md"
echo "  -> 작업 큐: .ralph/fix_plan.md"
echo "  -> max-iterations: $MAX_ITERATIONS"
echo ""

claude -p "$(cat .ralph/PROMPT.md)" \
  --dangerously-skip-permissions

# ── 5. 사후 검증 ──
echo ""
echo "======================================="
echo "  Ralph Loop 종료: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================="

echo "[4/4] 사후 검증..."

# iteration 횟수
if [ -f .ralph/.iteration_count ]; then
  ITER_COUNT=$(cat .ralph/.iteration_count)
  echo "  -> 총 iterations: $ITER_COUNT / $MAX_ITERATIONS"
  rm -f .ralph/.iteration_count
fi

# 커밋 이력
echo ""
echo "-- 최근 커밋 --"
git log --oneline -15 2>/dev/null || echo "(git 미사용)"

# 테스트 결과
echo ""
echo "-- 테스트 결과 --"
cd "$PROJECT_DIR/backend"
.venv/bin/python -m pytest --tb=short -q 2>&1 || true

# 린트 결과
echo ""
echo "-- 린트 결과 --"
.venv/bin/ruff check . 2>&1 | tail -5 || true

# fix_plan 상태
echo ""
echo "-- fix_plan.md 진행률 --"
cd "$PROJECT_DIR"
TOTAL=$(grep -c '^\- \[' .ralph/fix_plan.md || echo 0)
DONE=$(grep -c '^\- \[x\]' .ralph/fix_plan.md || echo 0)
SKIP=$(grep -c '^\- \[!\]' .ralph/fix_plan.md || echo 0)
echo "  완료: $DONE / $TOTAL (건너뜀: $SKIP)"

echo ""
echo "=== 다음 단계 ==="
echo "  1. git log 확인: git log --oneline $BRANCH"
echo "  2. 코드 리뷰: git diff main..$BRANCH --stat"
echo "  3. PR 생성: gh pr create --title \"Ralph: overnight $(date +%Y%m%d)\""
echo "  4. 이어하기: claude -p \"계속 진행하라.\" --continue"
