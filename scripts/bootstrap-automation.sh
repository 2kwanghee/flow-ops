#!/usr/bin/env bash
# ============================================================
# Claude Code 자동화 워크플로우 부트스트랩
#
# 사용법:
#   cd /path/to/new-project
#   bash /path/to/sales-manager/scripts/bootstrap-automation.sh
#
# 이 스크립트 하나로:
#   1. 자동화 파일 전부 복사
#   2. 하드코딩 경로 → 대상 프로젝트 경로로 자동 치환
#   3. 디렉토리 생성 + 실행 권한
#   4. .env 가이드 + Notion 연동 검증
# ============================================================
set -euo pipefail

# ── 경로 설정 ──
TEMPLATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$(pwd)"

# 자기 자신에게 복사하는 것 방지
if [ "$TEMPLATE_DIR" = "$TARGET_DIR" ]; then
  echo "ERROR: 대상 프로젝트 디렉토리에서 실행하세요."
  echo "  cd /path/to/new-project"
  echo "  bash $0"
  exit 1
fi

echo "======================================="
echo "  Claude Code 자동화 부트스트랩"
echo "======================================="
echo "  템플릿: $TEMPLATE_DIR"
echo "  대상:   $TARGET_DIR"
echo ""

# ── Step 1: 디렉토리 생성 ──
echo "[1/6] 디렉토리 생성..."
mkdir -p \
  "$TARGET_DIR/scripts" \
  "$TARGET_DIR/.claude/skills/setup" \
  "$TARGET_DIR/.claude/skills/log-work" \
  "$TARGET_DIR/.claude/skills/daily-close" \
  "$TARGET_DIR/.claude/skills/fullstack" \
  "$TARGET_DIR/.claude/skills/uiux" \
  "$TARGET_DIR/.claude/skills/ralph-loop" \
  "$TARGET_DIR/.ralph/tasks" \
  "$TARGET_DIR/logs" \
  "$TARGET_DIR/docs"
echo "  OK"

# ── Step 2: 자동화 스크립트 복사 ──
echo "[2/6] 자동화 파일 복사..."

# Python 스크립트 (수정 불필요 — Linear/Telegram API 범용)
for f in linear_client.py linear_watcher.py linear_reporter.py linear_confirmer.py linear_tracker.py telegram_notify.py; do
  if [ -f "$TEMPLATE_DIR/scripts/$f" ]; then
    cp "$TEMPLATE_DIR/scripts/$f" "$TARGET_DIR/scripts/$f"
    echo "  + scripts/$f"
  fi
done

# 셸 스크립트 (PROJECT_DIR 치환 필요)
for f in auto_dev_pipeline.sh ralph-loop.sh ralph-stop-hook.sh; do
  if [ -f "$TEMPLATE_DIR/scripts/$f" ]; then
    sed "s|PROJECT_DIR=\".*\"|PROJECT_DIR=\"\$(cd \"\$(dirname \"\${BASH_SOURCE[0]})/..\" \&\& pwd)\"|" \
      "$TEMPLATE_DIR/scripts/$f" > "$TARGET_DIR/scripts/$f"
    echo "  + scripts/$f (경로 치환됨)"
  fi
done

# 이 부트스트랩 스크립트 자체도 복사
cp "$TEMPLATE_DIR/scripts/bootstrap-automation.sh" "$TARGET_DIR/scripts/bootstrap-automation.sh"
echo "  + scripts/bootstrap-automation.sh"

# Claude 스킬 — SKILL.md 및 참조 문서
copy_skill() {
  local skill_name="$1"
  local skill_dir="$TEMPLATE_DIR/.claude/skills/$skill_name"
  local target_skill_dir="$TARGET_DIR/.claude/skills/$skill_name"

  if [ -d "$skill_dir" ]; then
    for md in "$skill_dir"/*.md; do
      [ -f "$md" ] || continue
      local filename
      filename=$(basename "$md")
      # 절대 경로를 상대 경로로 치환
      sed "s|/mnt/c/sales-manager/scripts/|scripts/|g; s|/mnt/c/workspace/sales-manager/scripts/|scripts/|g" \
        "$md" > "$target_skill_dir/$filename"
    done
    echo "  + .claude/skills/$skill_name/"
  fi
}

for skill in setup log-work daily-close fullstack uiux ralph-loop; do
  copy_skill "$skill"
done

# .ralph/PROMPT.md (프로젝트별 수정 필요 — 템플릿으로 복사)
if [ -f "$TEMPLATE_DIR/.ralph/PROMPT.md" ]; then
  cp "$TEMPLATE_DIR/.ralph/PROMPT.md" "$TARGET_DIR/.ralph/PROMPT.md"
  echo "  + .ralph/PROMPT.md (프로젝트에 맞게 수정 필요)"
fi

# docs/setupClaude.md
if [ -f "$TEMPLATE_DIR/docs/setupClaude.md" ]; then
  cp "$TEMPLATE_DIR/docs/setupClaude.md" "$TARGET_DIR/docs/setupClaude.md"
  echo "  + docs/setupClaude.md"
fi

# .claude/settings.json — Stop Hook 경로를 상대 경로로 치환
if [ -f "$TEMPLATE_DIR/.claude/settings.json" ]; then
  sed 's|bash /mnt/c/sales-manager/scripts/|bash ./scripts/|g; s|bash /mnt/c/workspace/sales-manager/scripts/|bash ./scripts/|g' \
    "$TEMPLATE_DIR/.claude/settings.json" > "$TARGET_DIR/.claude/settings.json"
  echo "  + .claude/settings.json (Hook 경로 치환됨)"
fi

echo ""

# ── Step 3: 실행 권한 ──
echo "[3/6] 실행 권한 부여..."
chmod +x "$TARGET_DIR/scripts/"*.sh 2>/dev/null || true
echo "  OK"

# ── Step 4: .gitignore 업데이트 ──
echo "[4/6] .gitignore 업데이트..."
GITIGNORE_ENTRIES=(
  "# === 자동화 워크플로우 런타임 ==="
  ".ralph/tasks/"
  ".ralph/.pipeline_lock"
  ".ralph/.task_mapping.json"
  ".ralph/.task_mapping_full.json"
  ".ralph/.iteration_count"
  ".ralph/.pipeline_result.json"
  ".ralph/.task_list.tmp"
  "logs/"
  ".env"
)

GITIGNORE="$TARGET_DIR/.gitignore"
touch "$GITIGNORE"
ADDED=0
for entry in "${GITIGNORE_ENTRIES[@]}"; do
  if ! grep -qF "$entry" "$GITIGNORE" 2>/dev/null; then
    echo "$entry" >> "$GITIGNORE"
    ADDED=1
  fi
done
if [ "$ADDED" -eq 1 ]; then
  echo "  .gitignore에 자동화 런타임 항목 추가됨"
else
  echo "  .gitignore 이미 설정됨"
fi
echo ""

# ── Step 5: .env 가이드 ──
echo "[5/6] 환경변수 (.env) 확인..."
ENV_FILE="$TARGET_DIR/.env"

check_env_var() {
  local var_name="$1"
  local required="$2"
  if [ -f "$ENV_FILE" ] && grep -q "^${var_name}=" "$ENV_FILE" 2>/dev/null; then
    local val
    val=$(grep "^${var_name}=" "$ENV_FILE" | cut -d= -f2-)
    if [ -n "$val" ] && [ "$val" != "<토큰>" ] && [ "$val" != "<DB ID>" ] && [ "$val" != "<채팅 ID>" ]; then
      echo "  $var_name ..................... OK"
      return 0
    fi
  fi
  if [ "$required" = "필수" ]; then
    echo "  $var_name ..................... 미설정 ($required)"
  else
    echo "  $var_name ..................... 미설정 ($required)"
  fi
  return 1
}

LINEAR_OK=true
check_env_var "LINEAR_API_KEY" "필수" || LINEAR_OK=false
check_env_var "LINEAR_TEAM_ID" "필수" || LINEAR_OK=false
check_env_var "TELEGRAM_BOT_TOKEN" "선택" || true
check_env_var "TELEGRAM_CHAT_ID" "선택" || true

if [ "$LINEAR_OK" = false ]; then
  echo ""
  echo "  ⚠ Linear 환경변수가 필요합니다. .env에 추가하세요:"
  echo ""
  echo "    LINEAR_API_KEY=lin_api_xxxxx"
  echo "    LINEAR_TEAM_ID=<Team UUID>"
  echo ""
  echo "  발급처:"
  echo "    - API Key: Linear Settings → API → Personal API keys"
  echo "    - Team ID: Linear Settings → General → Team ID"
fi
echo ""

# ── Step 6: Linear 연동 검증 (가능한 경우) ──
echo "[6/6] Linear 연동 검증..."
if [ "$LINEAR_OK" = true ]; then
  cd "$TARGET_DIR"
  if python3 scripts/linear_tracker.py list --status "Todo" > /dev/null 2>&1; then
    echo "  Linear API 연결 .............. OK"
  else
    echo "  Linear API 연결 .............. FAIL"
    echo "  → LINEAR_API_KEY, LINEAR_TEAM_ID 확인 필요"
  fi
else
  echo "  SKIP (Linear 환경변수 미설정)"
fi

# ── 결과 요약 ──
echo ""
echo "======================================="
echo "  부트스트랩 완료!"
echo "======================================="
echo ""
echo "복사된 파일:"
echo "  scripts/          — 자동화 스크립트 (Python + Shell)"
echo "  .claude/          — Claude 권한, Hook, 스킬"
echo "  .ralph/           — 자율 개발 프롬프트"
echo "  docs/             — 셋업 가이드"
echo ""
echo "프로젝트별 수정 필요:"
echo "  .ralph/PROMPT.md            — 기술 스택, 테스트/린트 명령"
echo "  scripts/ralph-stop-hook.sh  — 테스트/린트 명령 (pytest→jest 등)"
echo "  .claude/settings.json       — allow에 프로젝트별 명령 추가"
echo ""
echo "남은 작업:"
if [ "$LINEAR_OK" = false ]; then
  echo "  1. .env에 LINEAR_API_KEY, LINEAR_TEAM_ID 추가"
  echo "  2. python3 scripts/linear_tracker.py list --status \"Todo\"  # 연동 확인"
  echo "  3. crontab -e  # Cron 스케줄 등록 (docs/setupClaude.md 섹션 5)"
else
  echo "  1. crontab -e  # Cron 스케줄 등록 (docs/setupClaude.md 섹션 5)"
fi
echo ""
echo "Cron 스케줄 (복사용):"
echo "  0 9-18 * * 1-5 cd $TARGET_DIR && bash scripts/auto_dev_pipeline.sh >> logs/pipeline.log 2>&1"
echo "  0 0 * * *      cd $TARGET_DIR && bash scripts/auto_dev_pipeline.sh --max-iterations 50 >> logs/pipeline.log 2>&1"
echo "  0 12 * * 1-5   cd $TARGET_DIR && python3 scripts/linear_confirmer.py >> logs/confirmer.log 2>&1"
