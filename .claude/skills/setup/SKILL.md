---
name: setup
description: 자동화 워크플로우 환경 셋업 (Linear → AI 자율개발 → 승인 → 머지 → Telegram 보고)
user-invocable: true
disable-model-invocation: true
---

# Setup 스킬

`docs/setupClaude.md`를 읽고, 이 프로젝트에 Linear 기반 AI 자율 개발 파이프라인을 셋업한다.

> **이 스킬은 프로젝트 개발환경(언어, 프레임워크, DB) 셋업이 아닙니다.**
> Linear 연동 + 자동화 스크립트 + Hook + Cron + Telegram 알림 환경만 구성합니다.

## 절차

반드시 `docs/setupClaude.md`를 먼저 읽은 후, 아래 단계를 순서대로 수행한다.

### Step 1: 사전 요구사항 확인

```bash
python3 --version   # >= 3.12
git --version       # >= 2.40
claude --version    # Claude Code 설치 확인
tmux -V             # 병렬 실행용
```

미설치 항목이 있으면 설치 명령을 안내하고 사용자에게 확인한다.

### Step 2: Python 의존성 + 디렉토리

```bash
pip install requests python-dotenv
mkdir -p logs .ralph/tasks .claude/hooks
chmod +x scripts/*.sh
chmod +x .claude/hooks/*.sh 2>/dev/null || true
```

### Step 3: 환경변수 (.env)

1. `.env.example`이 있으면 `.env`로 복사한다.
2. 아래 변수가 설정되어 있는지 확인하고, 없으면 사용자에게 안내한다:

| 변수 | 필수 | 안내 |
|------|------|------|
| `LINEAR_API_KEY` | O | "Linear Settings → API → Personal API keys에서 발급" |
| `LINEAR_TEAM_ID` | O | "Linear Settings → General → Team ID에서 확인" |
| `TELEGRAM_BOT_TOKEN` | 선택 | "Telegram 알림을 원하면 @BotFather에서 발급" |
| `TELEGRAM_CHAT_ID` | 선택 | "Telegram 알림을 원하면 @userinfobot에서 확인" |

- **절대 `.env`의 기존 값을 임의로 수정하지 않는다** (프로젝트 고유 변수가 있을 수 있음).
- 모듈 ON/OFF 설정(`FLOWOPS_*`)은 `.env.example`에 기본값이 정의되어 있다.

### Step 4: 검증

```bash
# Linear 연동
python3 scripts/linear_tracker.py list --status "Todo"

# Telegram (선택 — 변수 설정된 경우만)
python3 scripts/telegram_notify.py --message "셋업 테스트 완료"

# GitHub CLI
gh auth status
```

### Step 5: Hook 시스템 검증

`.claude/settings.json`을 읽고 3가지 Hook이 올바르게 설정되었는지 확인한다:

| Hook | 경로 | 확인 사항 |
|------|------|-----------|
| Stop (Ralph) | `bash ./scripts/ralph-stop-hook.sh` | 파일 존재 + 실행 권한 |
| Stop (커밋) | `"$CLAUDE_PROJECT_DIR"/.claude/hooks/commit-session.sh` | 파일 존재 + `async: true` |
| UserPromptSubmit | (인라인 echo) | 설정 존재 여부 |

### Step 6: Cron 등록 안내

Cron 스케줄 등록은 사용자가 직접 수행해야 한다. `docs/setupClaude.md` 섹션 7을 안내한다.

### Step 7: 결과 보고

```
== 자동화 워크플로우 셋업 결과 ==

[사전 요구사항]
  Python 3.12.x ........................ OK
  Git 2.x.x ........................... OK
  Claude Code .......................... OK
  tmux ................................. OK

[자동화 환경]
  Python 의존성 ........................ OK
  scripts/ 실행 권한 ................... OK
  logs/, .ralph/tasks/ 디렉토리 ........ OK

[Linear 연동]
  LINEAR_API_KEY ....................... OK
  LINEAR_TEAM_ID ....................... OK
  API 연결 테스트 ...................... OK

[Telegram 알림]
  TELEGRAM_BOT_TOKEN ................... OK / SKIP
  메시지 전송 테스트 ................... OK / SKIP

[Hook 시스템]
  Stop Hook (Ralph) .................... OK
  Stop Hook (세션 커밋) ................ OK
  UserPromptSubmit Hook ................ OK

[모듈 ON/OFF]
  → .env의 FLOWOPS_* 설정으로 개별 제어 가능
  → 기본값: 모두 활성화 (true)

[Cron 스케줄]
  → 수동 등록 필요 (docs/setupClaude.md 섹션 7 참조)

== 셋업 완료! ==
참고 문서:
  - docs/setupClaude.md  — 전체 셋업 가이드
  - docs/pipeline-guide.md — 파이프라인 운영 가이드
  - docs/skills.md       — 스킬 상세 가이드
```

## 주의사항

- 이 스킬은 **자동화 파이프라인 환경만** 셋업한다
- 프로젝트 개발환경(DB, 프레임워크 등)은 프로젝트별 README/가이드를 따른다
- `.env`에 이미 있는 프로젝트 고유 변수를 건드리지 않는다
- Cron 등록은 자동 실행하지 않고 안내만 한다
