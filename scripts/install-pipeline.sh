#!/usr/bin/env bash
# ============================================================
# Flow-Ops 자동화 파이프라인 원테이크 설치
#
# 사용법:
#   cd /path/to/my-project
#   bash /tmp/flow-ops/scripts/install-pipeline.sh
#
# 이 스크립트는 flow-ops 레포에서 필요한 파일만 추출하여
# 대상 프로젝트에 파이프라인을 구축한다.
# ============================================================
set -euo pipefail

FLOW_OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$(pwd)"

if [ "$FLOW_OPS_DIR" = "$TARGET_DIR" ]; then
  echo "ERROR: 대상 프로젝트 디렉토리에서 실행하세요."
  echo "  cd /path/to/my-project && bash $0"
  exit 1
fi

echo "======================================="
echo "  Flow-Ops 파이프라인 설치"
echo "======================================="
echo "  소스: $FLOW_OPS_DIR"
echo "  대상: $TARGET_DIR"
echo ""

# ── Step 1: 디렉토리 생성 ──
echo "[1/7] 디렉토리 생성..."
mkdir -p \
  "$TARGET_DIR/scripts" \
  "$TARGET_DIR/.claude/hooks" \
  "$TARGET_DIR/.claude/skills/log-work" \
  "$TARGET_DIR/.claude/skills/prd-to-linear" \
  "$TARGET_DIR/.claude/skills/run-pipeline" \
  "$TARGET_DIR/.claude/skills/ralph-loop" \
  "$TARGET_DIR/.claude/skills/ai-critique/scripts" \
  "$TARGET_DIR/.claude/skills/fullstack" \
  "$TARGET_DIR/.claude/skills/uiux" \
  "$TARGET_DIR/.claude/skills/tdd-smart-coding" \
  "$TARGET_DIR/.claude/skills/daily-close" \
  "$TARGET_DIR/.claude/skills/setup" \
  "$TARGET_DIR/.claude/skills/merge-worktree" \
  "$TARGET_DIR/.claude/skills/verify-implementation" \
  "$TARGET_DIR/.claude/skills/manage-skills" \
  "$TARGET_DIR/.claude/agents" \
  "$TARGET_DIR/.ralph/tasks" \
  "$TARGET_DIR/.github/workflows" \
  "$TARGET_DIR/logs" \
  "$TARGET_DIR/docs/rules"
echo "  OK"

# ── Step 2: Python 스크립트 복사 (수정 불필요 — API 범용) ──
echo "[2/7] Python 스크립트 복사..."
PYTHON_SCRIPTS=(
  linear_client.py
  linear_watcher.py
  linear_reporter.py
  linear_confirmer.py
  linear_tracker.py
  auto_pr_creator.py
  fix_plan_generator.py
  gpt_pr_review.py
  telegram_notify.py
  webhook_server.py
)
for f in "${PYTHON_SCRIPTS[@]}"; do
  if [ -f "$FLOW_OPS_DIR/scripts/$f" ]; then
    cp "$FLOW_OPS_DIR/scripts/$f" "$TARGET_DIR/scripts/$f"
    echo "  + scripts/$f"
  fi
done

# ── Step 3: Shell 스크립트 복사 ──
echo "[3/7] Shell 스크립트 복사..."
SHELL_SCRIPTS=(
  auto_dev_pipeline.sh
  ralph-loop.sh
  ralph-stop-hook.sh
  start-webhook.sh
  stop-webhook.sh
  bootstrap-automation.sh
  install-pipeline.sh
)
for f in "${SHELL_SCRIPTS[@]}"; do
  if [ -f "$FLOW_OPS_DIR/scripts/$f" ]; then
    cp "$FLOW_OPS_DIR/scripts/$f" "$TARGET_DIR/scripts/$f"
    echo "  + scripts/$f"
  fi
done
chmod +x "$TARGET_DIR/scripts/"*.sh 2>/dev/null || true

# ── Step 4: Claude Code 설정 복사 ──
echo "[4/7] Claude Code 설정 복사..."

# settings.json — API 키 제거, 권한/Hook만 복사
python3 -c "
import json
with open('$FLOW_OPS_DIR/.claude/settings.json') as f:
    cfg = json.load(f)

# env에서 API 키 제거 (대상 프로젝트에서 직접 설정)
clean_env = {}
for k, v in cfg.get('env', {}).items():
    if 'KEY' in k or 'TOKEN' in k or 'SECRET' in k or k == 'LINEAR_TEAM_ID':
        clean_env[k] = '<설정 필요>'
    else:
        clean_env[k] = v
cfg['env'] = clean_env

with open('$TARGET_DIR/.claude/settings.json', 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
"
echo "  + .claude/settings.json (API 키 제거됨 — 직접 설정 필요)"

# Hooks
for f in commit-session.sh load-recent-changes.sh; do
  if [ -f "$FLOW_OPS_DIR/.claude/hooks/$f" ]; then
    cp "$FLOW_OPS_DIR/.claude/hooks/$f" "$TARGET_DIR/.claude/hooks/$f"
    chmod +x "$TARGET_DIR/.claude/hooks/$f"
    echo "  + .claude/hooks/$f"
  fi
done

# Agents
for f in "$FLOW_OPS_DIR/.claude/agents/"*.md; do
  [ -f "$f" ] || continue
  cp "$f" "$TARGET_DIR/.claude/agents/$(basename "$f")"
done
echo "  + .claude/agents/"

# Skills — 전체 복사
copy_skill_dir() {
  local skill="$1"
  local src="$FLOW_OPS_DIR/.claude/skills/$skill"
  local dst="$TARGET_DIR/.claude/skills/$skill"
  if [ -d "$src" ]; then
    cp -r "$src/"* "$dst/" 2>/dev/null || true
    echo "  + .claude/skills/$skill/"
  fi
}
for skill in log-work prd-to-linear run-pipeline ralph-loop ai-critique fullstack uiux tdd-smart-coding daily-close setup merge-worktree verify-implementation manage-skills; do
  copy_skill_dir "$skill"
done

# ── Step 5: GitHub Actions 복사 ──
echo "[5/7] GitHub Actions 복사..."
for f in ci.yml ai-review.yml post-merge.yml; do
  if [ -f "$FLOW_OPS_DIR/.github/workflows/$f" ]; then
    cp "$FLOW_OPS_DIR/.github/workflows/$f" "$TARGET_DIR/.github/workflows/$f"
    echo "  + .github/workflows/$f"
  fi
done

# ── Step 6: 문서 + PROMPT 템플릿 복사 ──
echo "[6/7] 문서 및 템플릿 복사..."
for f in setupClaude.md pipeline-guide.md skills.md; do
  if [ -f "$FLOW_OPS_DIR/docs/$f" ]; then
    cp "$FLOW_OPS_DIR/docs/$f" "$TARGET_DIR/docs/$f"
    echo "  + docs/$f"
  fi
done
if [ -f "$FLOW_OPS_DIR/docs/rules/workflow-rules.md" ]; then
  cp "$FLOW_OPS_DIR/docs/rules/workflow-rules.md" "$TARGET_DIR/docs/rules/workflow-rules.md"
  echo "  + docs/rules/workflow-rules.md"
fi

# PROMPT.md 템플릿 생성 (프로젝트별 수정 필요)
if [ ! -f "$TARGET_DIR/.ralph/PROMPT.md" ]; then
  cat > "$TARGET_DIR/.ralph/PROMPT.md" << 'PROMPT_EOF'
# Ralph Loop — 자율 개발 프롬프트

## 역할

너는 이 프로젝트의 자율 개발 에이전트다.
`.ralph/fix_plan.md`의 미완료 항목을 우선순위 순서대로 구현하라.
한 항목을 완료하면 fix_plan.md에 `[x]` 표시하고 git commit한 뒤 다음 항목으로 이동하라.

## 컨텍스트

<!-- 프로젝트에 맞게 수정하세요 -->
- 기술 스택: (예: FastAPI + React, Django + Vue, Express + Next.js 등)
- 테스트 명령: (예: pytest, jest, go test)
- 린트 명령: (예: ruff check, eslint, golangci-lint)

## 작업 절차 (반복)

1. .ralph/fix_plan.md 읽기 → 첫 번째 미완료 항목 선택
2. 코드 구현
3. 검증 (테스트 + 린트)
4. 성공 시: fix_plan.md에 [x] 표시 + git commit
5. 실패 시: 에러 분석 → 수정 → 재검증 (3회 실패 시 [!] 표시 후 건너뜀)
6. 다음 미완료 항목으로 이동

## 완료/블로킹 신호

- 모든 항목 완료: `<promise>DONE</promise>`
- 해결 불가능: `<promise>BLOCKED</promise>` + 사유

## 안전 규칙

1. `.env` 파일 수정 금지
2. `rm -rf` 사용 금지
3. `main` 브랜치에 push 금지
4. 기존 통과하던 테스트를 깨뜨리지 마라
PROMPT_EOF
  echo "  + .ralph/PROMPT.md (템플릿 — 프로젝트에 맞게 수정 필요)"
else
  echo "  ~ .ralph/PROMPT.md (이미 존재 — 건너뜀)"
fi

# ── Step 7: .gitignore 업데이트 ──
echo "[7/7] .gitignore 업데이트..."
GITIGNORE="$TARGET_DIR/.gitignore"
touch "$GITIGNORE"

ENTRIES=(
  ""
  "# === Flow-Ops 파이프라인 런타임 ==="
  ".ralph/tasks/"
  ".ralph/fix_plan.md"
  ".ralph/.pipeline_lock"
  ".ralph/.task_mapping.json"
  ".ralph/.task_mapping_full.json"
  ".ralph/.iteration_count"
  ".ralph/.pipeline_result.json"
  ".ralph/.task_list.tmp"
  ".worktrees/"
  "logs/"
  ".env"
)
ADDED=0
for entry in "${ENTRIES[@]}"; do
  [ -z "$entry" ] && continue
  if ! grep -qF "$entry" "$GITIGNORE" 2>/dev/null; then
    echo "$entry" >> "$GITIGNORE"
    ADDED=1
  fi
done
[ "$ADDED" -eq 1 ] && echo "  .gitignore 항목 추가됨" || echo "  .gitignore 이미 설정됨"

# ── ngrok 설치 확인 ──
NGROK_BIN=""
if command -v ngrok &>/dev/null; then
  NGROK_BIN="ngrok"
elif [ -f "$HOME/bin/ngrok" ]; then
  NGROK_BIN="$HOME/bin/ngrok"
fi

# ── 결과 요약 ──
echo ""
echo "======================================="
echo "  설치 완료!"
echo "======================================="
echo ""
echo "설치된 구성요소:"
echo "  scripts/           — 자동화 스크립트 (Python 10개 + Shell 7개)"
echo "  .claude/           — 권한, Hook, 스킬 (13개)"
echo "  .github/workflows/ — CI/CD (3개)"
echo "  .ralph/            — 자율 개발 프롬프트"
echo "  docs/              — 가이드 문서"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  필수 설정 (아직 안 됨)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. .claude/settings.json의 env에 API 키 설정:"
echo "     LINEAR_API_KEY, LINEAR_TEAM_ID"
echo "     OPENAI_API_KEY (선택)"
echo "     GEMINI_API_KEY (선택)"
echo ""
echo "2. GitHub CLI 인증:"
echo "     gh auth login"
echo ""
echo "3. Linear 워크플로우 상태 확인 (Queued, Confirm 필요):"
echo "     LINEAR_API_KEY=<key> LINEAR_TEAM_ID=<id> python3 scripts/linear_tracker.py list"
echo ""
echo "4. .ralph/PROMPT.md 수정 (프로젝트 기술 스택에 맞게)"
echo ""
echo "5. scripts/ralph-stop-hook.sh 수정 (테스트/린트 명령)"
echo ""
if [ -z "$NGROK_BIN" ]; then
  echo "6. ngrok 설치 (Webhook 사용 시):"
  echo "     mkdir -p ~/bin"
  echo "     curl -sSL -o /tmp/ngrok.zip https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.zip"
  echo "     python3 -c \"import zipfile; zipfile.ZipFile('/tmp/ngrok.zip').extractall('$HOME/bin')\""
  echo "     chmod +x ~/bin/ngrok"
  echo "     ~/bin/ngrok config add-authtoken <YOUR_TOKEN>"
  echo ""
fi
echo "설정 완료 후 테스트:"
echo "  bash scripts/start-webhook.sh     # Webhook 서버 시작"
echo "  bash scripts/auto_dev_pipeline.sh  # 파이프라인 수동 실행"
