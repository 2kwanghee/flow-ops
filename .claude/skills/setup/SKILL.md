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
```

미설치 항목이 있으면 설치 명령을 안내하고 사용자에게 확인한다.

### Step 2: Python 의존성 (자동화 스크립트용)

```bash
pip install requests python-dotenv
```

이 의존성은 자동화 스크립트(`linear_*.py`, `telegram_notify.py`) 실행에 필요하다.
프로젝트 개발 의존성과는 별개이다.

### Step 3: 디렉토리 + 권한

```bash
mkdir -p logs .ralph/tasks .claude/hooks
chmod +x scripts/*.sh
chmod +x .claude/hooks/*.sh 2>/dev/null || true
```

### Step 4: 환경변수 (.env)

1. `.env` 파일을 확인한다.
2. 아래 변수가 설정되어 있는지 확인하고, 없으면 사용자에게 안내한다:

| 변수 | 필수 | 안내 |
|------|------|------|
| `LINEAR_API_KEY` | O | "Linear Settings → API → Personal API keys에서 발급" |
| `LINEAR_TEAM_ID` | O | "Linear Settings → General → Team ID에서 확인" |
| `TELEGRAM_BOT_TOKEN` | 선택 | "Telegram 알림을 원하면 @BotFather에서 발급" |
| `TELEGRAM_CHAT_ID` | 선택 | "Telegram 알림을 원하면 @userinfobot에서 확인" |

- `.env` 파일이 없으면 `.env.example`이 있는지 확인하고 복사한다.
- `.env.example`도 없으면 위 변수만으로 `.env`를 생성한다.
- **절대 `.env`의 기존 값을 임의로 수정하지 않는다** (프로젝트 고유 변수가 있을 수 있음).

### Step 5: Linear 연동 검증

```bash
python3 scripts/linear_tracker.py list --status "Todo"
```

- 성공: 목록 출력 → 다음 단계
- 실패 (401): NOTION_API_KEY 확인 안내
- 실패 (404): NOTION_DATABASE_ID 확인 안내
- 실패 (400 property): Linear DB 속성 누락 → `docs/setupClaude.md` 섹션 2.1 안내

### Step 6: Telegram 검증 (선택)

TELEGRAM 변수가 설정된 경우에만:

```bash
python3 scripts/telegram_notify.py --message "셋업 테스트 완료"
```

미설정이면 "나중에 .env에 추가하면 활성화됩니다"로 안내하고 넘어간다.

### Step 7: Hook 시스템 검증

`.claude/settings.json`을 읽고 3가지 Hook이 올바르게 설정되었는지 확인한다:

**7-1. Stop Hook — Ralph Stop Hook**
- 경로: `bash ./scripts/ralph-stop-hook.sh`
- 확인: 파일 존재 + 실행 권한 (`chmod +x`)
- 상대 경로(`./scripts/...`) 사용 권장 (이식성)

**7-2. Stop Hook — 세션 커밋**
- 경로: `"$CLAUDE_PROJECT_DIR"/.claude/hooks/commit-session.sh`
- 확인: 파일 존재 + 실행 권한
- `async: true`, `timeout: 120` 설정 확인
- `$CLAUDE_PROJECT_DIR` 환경변수는 Claude Code가 자동 설정하므로 그대로 사용

**7-3. UserPromptSubmit Hook — TODO 리마인더**
- 인라인 echo 명령이 설정되어 있는지 확인
- 누락되어 있으면 `.claude/settings.json`에 추가 안내

하나라도 누락/오류가 있으면 수정 방법을 안내한다.

### Step 8: Cron 등록 안내

Cron 스케줄 등록은 사용자가 직접 수행해야 한다. 다음 내용을 안내한다:

```
crontab -e 로 아래 스케줄을 등록하세요:

# 업무시간 매시: Queued 태스크 자동 개발
0 9-18 * * 1-5 cd <PROJECT_ROOT> && bash scripts/auto_dev_pipeline.sh >> logs/pipeline.log 2>&1

# 매일 자정: 오버나이트 개발
0 0 * * * cd <PROJECT_ROOT> && bash scripts/auto_dev_pipeline.sh --max-iterations 50 >> logs/pipeline.log 2>&1

# 업무시간 정오: Confirm 태스크 → main 머지
0 12 * * 1-5 cd <PROJECT_ROOT> && python3 scripts/linear_confirmer.py >> logs/confirmer.log 2>&1

<PROJECT_ROOT>를 현재 프로젝트 경로로 교체하세요.
WSL이면 sudo service cron start 실행이 필요합니다.
```

Cron은 자동 실행하지 않고 안내만 한다 (사용자가 스케줄을 조정할 수 있도록).

### Step 9: 결과 보고

모든 단계 완료 후 아래 형태로 결과를 출력한다:

```
== 자동화 워크플로우 셋업 결과 ==

[사전 요구사항]
  Python 3.12.x ........................ OK
  Git 2.x.x ........................... OK
  Claude Code .......................... OK

[자동화 환경]
  Python 의존성 (requests, dotenv) ..... OK
  scripts/ 실행 권한 ................... OK
  .claude/hooks/ 실행 권한 ............. OK
  logs/ 디렉토리 ....................... OK
  .ralph/tasks/ 디렉토리 ............... OK

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

[Cron 스케줄]
  → 수동 등록 필요 (위 안내 참조)

== 셋업 완료! ==
워크플로우 사용법:
  1. Linear에 태스크 등록 → 상태를 "Queued"로 설정
  2. Cron이 자동 감지하여 Claude가 구현 (태스크별 브랜치 격리)
  3. 완료 후 Linear에서 코드 리뷰 (브랜치: ralph/task-XXXXXXXX)
  4. 승인 시 상태를 "Confirm"으로 변경 → 자동 main 머지

참고 문서:
  - docs/setupClaude.md  — 전체 파이프라인 가이드
  - docs/skills.md       — 스킬 상세 가이드
```

## 주의사항

- 이 스킬은 **자동화 파이프라인 환경만** 셋업한다
- 프로젝트 개발환경(DB, 프레임워크 등)은 프로젝트별 README/가이드를 따른다
- `.env`에 이미 있는 프로젝트 고유 변수를 건드리지 않는다
- Cron 등록은 자동 실행하지 않고 안내만 한다
- 새 프로젝트라면 `scripts/bootstrap-automation.sh` 사용을 먼저 안내한다
