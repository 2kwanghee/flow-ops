# Claude Code 자동화 워크플로우 셋업 가이드

> **이 문서는 프로젝트의 개발 아키텍처(언어, 프레임워크)와 무관합니다.**
> 어떤 기술 스택을 사용하든, 아래 자동화 워크플로우를 동일하게 적용할 수 있습니다.

---

## 개요

이 워크플로우는 다음 사이클을 자동화합니다:

```
Linear에 이슈 등록 (Queued)
       ↓
  AI가 자율적으로 코드 구현 (브랜치 격리)
       ↓
  자동 테스트/린트 검증 (Stop Hook)
       ↓
  결과를 Linear에 보고 (Done) + Telegram 알림
       ↓
  사용자가 코드 리뷰 후 승인 (Confirm)
       ↓
  자동으로 main 머지 + Telegram 알림
```

```
PRD 작성 → Claude Code 분석 → Linear 태스크 자동 등록 (Queued)
       ↓
  Webhook 즉시 감지 (또는 수동 실행)
       ↓
  AI가 자율적으로 코드 구현 (브랜치 격리, 병렬)
       ↓
  자동 테스트/린트 검증 (Stop Hook)
       ↓
  결과를 Linear에 보고 (Done) + 자동 PR 생성
       ↓
  GitHub Actions CI/CD + AI 코드 리뷰 (GPT)
       ↓
  자동 머지 & 배포 + Linear Done + Telegram 알림
```

**사용자가 할 일**: PRD 작성 또는 Linear에 이슈 등록 → (선택) 코드 리뷰
**AI가 할 일**: 태스크 분해 → 코드 구현 → 테스트 → PR → CI/CD → 머지

> 파이프라인 운영 상세는 `docs/pipeline-guide.md`를 참조하세요.

---

## 1. 사전 요구사항

### 1.1 필수 설치

| 도구 | 용도 | 설치 |
|------|------|------|
| **Claude Code** | AI 코딩 에이전트 | `npm install -g @anthropic-ai/claude-code` |
| **Python 3.12+** | 자동화 스크립트 실행 | https://python.org |
| **Git 2.40+** | 버전 관리 + 워크트리 | 기본 설치 |
| **tmux** | 병렬 세션 관리 | `sudo apt install tmux` |
| **jq** (선택) | AI 코드 비평 스킬용 | `apt install jq` |

### 1.2 필요 계정/토큰

| 항목 | 발급처 | 용도 |
|------|--------|------|
| **Linear API Key** | [Linear Settings → API](https://linear.app/settings/api) | Linear 이슈 읽기/쓰기 |
| **Linear Team ID** | [Linear Settings → General](https://linear.app/settings) | 대상 팀 지정 |
| **Claude Code 인증** | Anthropic 계정 또는 API 키 | AI 에이전트 실행 |
| **GitHub CLI (gh)** | `gh auth login` | 자동 PR 생성/머지 |
| **ngrok** (선택) | https://ngrok.com | Webhook 터널링 (로컬 PC 사용 시) |
| **Telegram Bot Token** (선택) | [@BotFather](https://t.me/BotFather) | 완료 알림 수신 |
| **Telegram Chat ID** (선택) | [@userinfobot](https://t.me/userinfobot) | 알림 대상 지정 |
| **OpenAI API Key** (선택) | OpenAI 계정 | Fix Plan 생성 + AI PR 리뷰 + `/ai-critique` 스킬 |
| **Gemini API Key** (선택) | Google AI Studio | `/ai-critique` 스킬 |

---

## 2. Linear 팀 구성

### 2.1 빌트인 필드

Linear 이슈에는 다음 빌트인 필드를 사용합니다:

| 필드 | Linear 타입 | 설명 |
|------|-------------|------|
| **title** | Title | 이슈 제목 (간결하게) |
| **description** | Markdown | 상세 요구사항 (AI가 읽고 구현) + 완료 후 결과보고 |
| **state** | Workflow state | 워크플로우 상태 (아래 옵션 필수) |
| **priority** | Priority | Urgent, High, Medium, Low, No priority |
| **dueDate** | Date | 마감일 |
| **labels** | Label | 분류 태그 |
| **assignee** | User | 담당자 |

### 2.2 상태(Workflow States) — 반드시 아래 6개 설정

| 상태 | 의미 | 전이 주체 |
|------|------|-----------|
| `Backlog` | 아이디어/미정 | 사용자 |
| `Todo` | 할 일 확정 | 사용자 |
| `Queued` | **자동개발 대기열** 등록 (커스텀 상태 추가 필요) | 사용자 |
| `In Progress` | AI가 작업 중 | 파이프라인 (자동) |
| `Done` | 개발 완료 (브랜치에 보존) | 파이프라인 (자동) |
| `Confirm` | 사용자 승인 → main 머지 대기 (커스텀 상태 추가 필요) | 사용자 |

### 2.3 상태 흐름

```
Backlog ──(수동)──→ Todo ──(수동)──→ Queued
                                       │
                                  [자동 감지]
                                       ↓
                                  In progress
                                       │
                                  [AI 작업 완료]
                                 ┌─────┴─────┐
                                 ↓           ↓
                               Done       Backlog
                          (브랜치 보존)  (실패/건너뜀)
                                 │
                            [사용자 리뷰]
                                 ↓
                              Confirm
                                 │
                            [자동 머지]
                                 ↓
                          main에 반영 완료
```

**핵심**: `Queued` → `Done`은 완전 자동. `Done` → `Confirm`은 반드시 사용자가 코드 리뷰 후 수동 전환.

### 2.4 Linear API Key 생성 + Team ID 찾기

1. [Linear Settings → API](https://linear.app/settings/api)에서 **Personal API Key** 생성
2. 생성된 API Key 복사 → `.env`의 `LINEAR_API_KEY`에 설정
3. [Linear Settings → General](https://linear.app/settings)에서 팀 선택
4. URL 또는 Settings에서 **Team ID** 확인 → `.env`의 `LINEAR_TEAM_ID`에 설정

---

## 3. 프로젝트에 자동화 적용

### 3.1 빠른 적용 — 부트스트랩 스크립트

이미 자동화가 구성된 프로젝트가 있으면, **한 명령으로** 새 프로젝트에 복사할 수 있습니다:

```bash
cd /path/to/new-project
bash /path/to/flow-ops/scripts/bootstrap-automation.sh
```

부트스트랩이 자동으로 수행하는 작업:
1. 자동화 스크립트 전체 복사 (Python + Shell)
2. 하드코딩 경로 → 상대 경로로 자동 치환
3. Claude 스킬 복사 (setup, log-work, daily-close, fullstack, uiux, ralph-loop)
4. 디렉토리 생성 + 실행 권한 부여
5. `.gitignore`에 런타임 파일 추가
6. `.env` 상태 확인 + Linear 연동 검증

부트스트랩 후 **프로젝트별 수정이 필요한 파일**은 섹션 8을 참조하세요.

### 3.2 디렉토리/파일 구조

```
프로젝트-루트/
├── .env                              ← 환경변수 (Git 제외)
├── .worktrees/                       ← 병렬 실행 시 worktree 디렉토리 (Git 제외, 자동 정리)
├── CLAUDE.md                         ← 프로젝트 지시문
├── .claude/
│   ├── settings.json                 ← 권한 + Hook 설정
│   ├── hooks/
│   │   ├── commit-session.sh         ← [Stop Hook] 세션 종료 시 WIP 자동 커밋
│   │   └── load-recent-changes.sh    ← [미래용] 세션 시작 시 컨텍스트 로딩
│   └── skills/
│       ├── setup/SKILL.md            ← 셋업 자동화 스킬
│       ├── log-work/                 ← Linear 작업 기록 스킬
│       ├── daily-close/              ← 하루 마감 정리 스킬
│       ├── fullstack/                ← 풀스택 개발 모드 스킬
│       ├── uiux/                     ← UI/UX 전문 모드 스킬
│       ├── tdd-smart-coding/         ← TDD 루프 개발 스킬
│       ├── ralph-loop/               ← 자율 반복 개발 스킬
│       ├── merge-worktree/           ← 워크트리 squash-merge 스킬
│       ├── ai-critique/              ← 외부 AI 코드 비평 스킬
│       ├── prd-to-linear/             ← PRD → Linear 태스크 자동 등록 스킬
│       ├── run-pipeline/             ← 파이프라인 즉시 실행 스킬
│       ├── verify-implementation/    ← 통합 검증 스킬
│       └── manage-skills/            ← 검증 스킬 관리 스킬
├── .github/
│   └── workflows/
│       ├── ci.yml                    ← PR 시 pytest+ruff+pnpm lint+build
│       ├── ai-review.yml             ← ralph/* PR 시 GPT 코드 리뷰
│       └── post-merge.yml            ← 머지 후 Linear Done + Telegram
├── scripts/
│   ├── auto_dev_pipeline.sh          ← 파이프라인 오케스트레이터
│   ├── webhook_server.py             ← Linear Webhook 수신 서버
│   ├── linear_watcher.py             ← Queued 태스크 감지
│   ├── linear_reporter.py            ← 결과 → Linear 보고
│   ├── linear_confirmer.py           ← Confirm → PR merge / 로컬 merge
│   ├── linear_tracker.py             ← Linear CRUD 유틸
│   ├── auto_pr_creator.py            ← 자동 PR 생성 (gh CLI)
│   ├── fix_plan_generator.py         ← ChatGPT FC Fix Plan 생성
│   ├── gpt_pr_review.py              ← ChatGPT FC PR 코드 리뷰
│   ├── telegram_notify.py            ← Telegram 알림
│   ├── ralph-stop-hook.sh            ← Claude 종료 조건 검증 Hook
│   └── bootstrap-automation.sh       ← 새 프로젝트 자동화 복사 스크립트
├── .ralph/
│   ├── PROMPT.md                     ← Claude 자율 개발 프롬프트
│   ├── fix_plan.md                   ← 현재 작업 큐 (런타임)
│   └── tasks/                        ← 태스크별 작업 계획 (런타임)
├── docs/
│   ├── setupClaude.md                ← 이 가이드
│   └── skills.md                     ← 스킬 상세 가이드
└── logs/                             ← 파이프라인 로그
```

### 3.3 환경변수 (.env)

```env
# ========================
# Linear 연동 (필수)
# ========================
LINEAR_API_KEY=<Linear Personal API Key>
LINEAR_TEAM_ID=<Team ID>

# ========================
# Telegram 알림 (선택)
# ========================
TELEGRAM_BOT_TOKEN=<BotFather 토큰>
TELEGRAM_CHAT_ID=<알림 받을 채팅 ID>

# ========================
# AI 코드 비평 (선택 — /ai-critique 스킬용)
# ========================
OPENAI_API_KEY=<OpenAI API 키>
GEMINI_API_KEY=<Gemini API 키>
```

> 프로젝트 고유 환경변수(DB, API 등)는 프로젝트의 `.env.example`을 참고하세요.

### 3.4 permissions 설정 (.claude/settings.json)

Claude가 실행할 수 있는 명령어를 제한합니다. 프로젝트에 맞게 `allow`를 조정하세요.

```jsonc
{
  "permissions": {
    "allow": [
      // === 공통 (모든 프로젝트) ===
      "Read", "Edit", "Write", "Glob", "Grep",
      "Bash(cd *)", "Bash(ls *)", "Bash(mkdir *)",
      "Bash(cat *)", "Bash(head *)", "Bash(tail *)", "Bash(wc *)",
      "Bash(git add *)", "Bash(git commit *)",
      "Bash(git status*)", "Bash(git log*)", "Bash(git diff*)",
      "Bash(git checkout -b *)", "Bash(git branch*)",

      // === 프로젝트별 추가 (예시) ===
      // Python: "Bash(python -m pytest*)", "Bash(ruff check*)"
      // Node: "Bash(pnpm *)", "Bash(npm test*)"
      // Go: "Bash(go test*)", "Bash(golangci-lint*)"
      // Docker: "Bash(docker ps*)", "Bash(docker compose up*)"
    ],
    "deny": [
      // === 절대 차단 (모든 프로젝트 공통) ===
      "Bash(rm -rf *)",
      "Bash(sudo *)",
      "Bash(git push origin main*)",
      "Bash(git push origin master*)",
      "Bash(git push --force*)",
      "Bash(git reset --hard*)",
      "Bash(docker rm *)",
      "Bash(docker rmi *)",
      "Bash(docker compose down*)"
    ]
  },
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ./scripts/ralph-stop-hook.sh"
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/commit-session.sh",
            "async": true,
            "timeout": 120
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo '[TODO] 작업 시작 전 TODO.md를 확인/생성하세요.' >&2"
          }
        ]
      }
    ]
  }
}
```

---

## 4. Hook 시스템

Claude Code Hook은 특정 이벤트에 반응하여 셸 명령을 자동 실행하는 메커니즘입니다.
이 프로젝트는 3가지 Hook을 사용합니다.

### 4.1 Stop Hook — Ralph Stop Hook (완료 조건 검증)

**파일**: `scripts/ralph-stop-hook.sh`
**트리거**: Claude가 작업 완료를 선언하고 종료를 시도할 때

Claude가 Stop을 시도하면 Hook이 다음을 순서대로 검증합니다:

| 순서 | 검증 항목 | 미충족 시 |
|------|-----------|-----------|
| 1 | iteration 카운터 (max-iterations 초과 여부) | 강제 종료 허용 (allow) |
| 2 | fix_plan.md 미완료 항목 (P1 → P2 → P3 순) | 루프 계속 (block) |
| 3 | 테스트 실행 (`pytest --tb=no -q`) | 수정 지시 (block) |
| 4 | 린트 실행 (`ruff check .`) | 수정 지시 (block) |
| — | **모든 조건 충족** | **종료 허용 (allow)** + Telegram 보고 |

**출력 형식**: `{"decision": "block|allow", "reason": "..."}`

> **프로젝트별 조정 필요**: `ralph-stop-hook.sh` 내의 테스트/린트 명령을 프로젝트에 맞게 수정
> - Python: `python -m pytest`, `ruff check .`
> - Node: `npm test`, `eslint .`
> - Go: `go test ./...`, `golangci-lint run`

### 4.2 Stop Hook — 세션 커밋 (자동 WIP 커밋)

**파일**: `.claude/hooks/commit-session.sh`
**트리거**: Claude 세션이 종료될 때 (비동기 실행, 120초 타임아웃)

세션 종료 시 자동으로 변경사항을 WIP 커밋합니다:

1. `git add -A`로 모든 변경 스테이징
2. 변경이 없으면 아무것도 하지 않음
3. diff를 Claude headless 모드(`claude -p`)에 전달하여 커밋 메시지 생성
4. Claude가 실패하면 `wip: update N files` 폴백 메시지 사용
5. `docs/CHANGELOG.md`가 있으면 `[Unreleased]` 섹션에 항목 추가

**커밋 메시지 형식**: `WIP(scope): short summary`

> 이 Hook은 `async: true`로 설정되어 세션 종료를 블로킹하지 않습니다.
> 워크트리 환경에서도 `git rev-parse --show-toplevel`로 올바른 루트를 찾습니다.

### 4.3 UserPromptSubmit Hook — TODO 리마인더

**트리거**: 사용자가 프롬프트를 제출할 때마다

작업 시작 전 `TODO.md`를 확인/생성하도록 리마인더를 표시합니다.
이 Hook은 stderr로 메시지를 출력하므로 Claude의 응답에는 영향을 주지 않습니다.

---

## 5. 파이프라인 아키텍처

> 파이프라인 상세 운영(트리거, 모니터링, 스크립트 참조 등)은 **[docs/pipeline-guide.md](pipeline-guide.md)**를 참조하세요.

### 5.1 PROMPT.md — Claude 자율 개발 프롬프트

`.ralph/PROMPT.md`는 Claude가 자율 루프에서 따르는 핵심 지시문입니다.

**프로젝트별 조정 필요한 부분**:
- 기술 스택 설명 (현재: FastAPI + SQLAlchemy + PostgreSQL + Next.js)
- 테스트/린트 명령 (현재: `pytest`, `ruff check`)
- 에이전트 가이드 경로 (현재: `.claude/agents/`)
- 프로젝트 고유 금지 규칙 (현재: `.env` 수정, Alembic 파일 수정 등)

### 5.2 태스크 격리 — 브랜치 전략

각 태스크는 Linear identifier (예: `OPS-123`)를 키로 사용합니다.
이 키 하나로 3가지 리소스가 1:1:1 매핑:

| 리소스 | 이름 규칙 |
|--------|-----------|
| Git 브랜치 | `ralph/OPS-123` |
| Fix Plan | `.ralph/tasks/OPS-123.md` |
| Linear 이슈 | `OPS-123` |

---

## 6. 스킬 시스템

커스텀 스킬 상세 사용법은 **[docs/skills.md](skills.md)**를 참조하세요.

---

## 7. 파이프라인 트리거

Webhook 또는 Cron으로 파이프라인을 트리거합니다.
상세 설정은 **[docs/pipeline-guide.md](pipeline-guide.md)**를 참조하세요.

### 7.1 Webhook (권장)

```bash
nohup python3 scripts/webhook_server.py > logs/webhook.log 2>&1 &
nohup ~/bin/ngrok http 9876 > logs/ngrok.log 2>&1 &
```

Linear Settings → API → Webhooks에 `https://<ngrok-url>/webhook/linear` 등록 (이벤트: Issues).

### 7.2 Cron (선택)

```bash
# 업무시간 매시: Queued 태스크 자동 개발
0 9-18 * * 1-5 cd <PROJECT_ROOT> && bash scripts/auto_dev_pipeline.sh >> logs/pipeline.log 2>&1

# 매일 자정: 오버나이트 개발
0 0 * * * cd <PROJECT_ROOT> && bash scripts/auto_dev_pipeline.sh --max-iterations 50 >> logs/pipeline.log 2>&1

# 업무시간 정오: Confirm → main 머지
0 12 * * 1-5 cd <PROJECT_ROOT> && python3 scripts/linear_confirmer.py >> logs/confirmer.log 2>&1
```

> WSL: `sudo service cron start` 필요. `<PROJECT_ROOT>`를 실제 경로로 교체.

---

## 8. 셋업 절차 (수동)

> **빠른 셋업**: Claude Code에서 `/setup` 스킬을 실행하면 아래 절차를 자동으로 수행합니다.

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env에 LINEAR_API_KEY, LINEAR_TEAM_ID 등 입력

# 2. Python 의존성 (자동화 스크립트용)
pip install requests python-dotenv

# 3. 디렉토리 + 권한
mkdir -p logs .ralph/tasks .claude/hooks
chmod +x scripts/*.sh .claude/hooks/*.sh

# 4. Linear 연동 검증
python3 scripts/linear_tracker.py list --status "Todo"

# 5. Telegram 검증 (선택)
python3 scripts/telegram_notify.py --message "셋업 테스트 완료"

# 6. GitHub CLI 인증
gh auth login

# 7. Hook 설정 확인 (.claude/settings.json에 3개 Hook 존재 확인)

# 8. Webhook 또는 Cron 등록 (섹션 7 참조)

# 9. 파이프라인 테스트
bash scripts/auto_dev_pipeline.sh
```

---

## 9. 검증 체크리스트

```
□ Linear API 연결 정상 (list 명령)
□ Linear에 8개 상태 존재 (Backlog, Todo, Queued, In Progress, Done, Confirm, Canceled, Duplicate)
□ .env 또는 settings.json에 LINEAR_API_KEY, LINEAR_TEAM_ID 설정됨
□ gh auth login 완료 (gh auth status로 확인)
□ scripts/*.sh 실행 권한 부여됨
□ .claude/hooks/*.sh 실행 권한 부여됨
□ logs/, .ralph/tasks/, .claude/hooks/ 디렉토리 생성됨
□ Stop Hook 경로가 올바름 (.claude/settings.json — 2개)
□ commit-session.sh가 async: true로 설정됨
□ UserPromptSubmit Hook 설정됨
□ Webhook 서버 동작 확인 (curl http://localhost:9876/health) 또는 Cron 등록
□ Telegram 메시지 수신 정상 (선택)
□ tmux 설치됨 (tmux -V)
□ ngrok 설치됨 (선택, 로컬 PC Webhook 사용 시)
□ GitHub Secrets 설정됨 (선택, CI/CD 사용 시)
□ Branch protection 설정됨 (선택, auto-merge 사용 시)
```

---

## 10. 새 프로젝트에 적용

> 새 프로젝트에 파이프라인을 자동 구축하려면 **[docs/setupPipeline.md](setupPipeline.md)**를 참조하세요.

**부트스트랩 (권장):**
```bash
cd /path/to/new-project
bash /path/to/flow-ops/scripts/bootstrap-automation.sh
```

**프로젝트별 수정 필요한 파일:**

| 파일 | 수정할 내용 |
|------|-----------|
| `.ralph/PROMPT.md` | 기술 스택, 테스트/린트 명령, 에이전트 경로 |
| `scripts/ralph-stop-hook.sh` | 테스트/린트 명령 (pytest→jest 등), 경로 |
| `.claude/settings.json` | `allow`에 프로젝트별 명령 추가 |
| `CLAUDE.md` | 프로젝트별 기술 스택, 코딩 규칙 |
| `.env` | API 키, 모듈 ON/OFF 설정 |

---

## 11. 모듈 ON/OFF 설정

각 자동화 모듈을 `.env`에서 개별적으로 활성화/비활성화할 수 있습니다.
설정이 없으면 기본값 `true` (모두 활성화).

```env
FLOWOPS_AUTO_COMMIT=true     # 세션 종료 시 자동 커밋
FLOWOPS_RALPH_STOP_HOOK=true # Ralph 완료 조건 검증 Hook
FLOWOPS_LINEAR_WATCHER=true  # Linear Queued 이슈 감지
FLOWOPS_LINEAR_REPORT=true   # Linear 결과 보고
FLOWOPS_LINEAR_CONFIRM=true  # Linear Confirm 자동 머지
FLOWOPS_AUTO_PR=true         # PR 자동 생성
FLOWOPS_AUTO_MERGE=true      # PR 자동 머지
FLOWOPS_GPT_REVIEW=true      # ChatGPT 코드 리뷰
FLOWOPS_TELEGRAM=true        # Telegram 알림
FLOWOPS_TODO_REMINDER=true   # TODO.md 리마인더
```

> 상세: [.env.example](../.env.example) 참조

---

## 12. 팀 동시 사용 시 주의사항

### 같은 Linear DB를 여러 명이 사용할 때

| 문제 | 해결 |
|------|------|
| 같은 Queued 태스크를 동시 처리 | **담당자(people) 필터링** 추가 권장 |
| 같은 브랜치명 충돌 | page_id 기반이므로 담당자 분리로 해결 |
| Cron 동시 실행 | PC별 Cron 시간 분산 (A: 정각, B: 30분) |

### Git에 포함/제외

| 항목                          | Git | 비고 |
|-----------------------------|-----|------|
| `scripts/*.py`, `*.sh`      | ✅ | 자동화 스크립트 (모든 PC 동일) |
| `.claude/settings.json`     | ✅ | 권한 + Hook (팀 공유) |
| `.claude/hooks/*.sh`        | ✅ | Hook 스크립트 (팀 공유) |
| `.claude/skills/`           | ✅ | 스킬 정의 (팀 공유) |
| `.ralph/PROMPT.md`          | ✅ | 자율 개발 프롬프트 (팀 공유) |
| `docs/setupClaude.md`       | ✅ | 이 가이드 (팀 공유) |
| `docs/skills.md`            | ✅ | 스킬 가이드 (팀 공유) |
| `.env`                      | ❌ | 시크릿 |
| `.worktrees/`               | ❌ | 병렬 실행 런타임 (자동 정리) |
| `.ralph/tasks/`             | ❌ | 런타임 작업 계획 |
| `.ralph/fix_plan.md`        | ❌ | 런타임 작업 큐 |
| `.ralph/.pipeline_lock`     | ❌ | 런타임 락 |
| `.ralph/.task_mapping.json` | ❌ | 런타임 매핑 |
| `.ralph/.iteration_count`   | ❌ | 런타임 카운터 |
| `logs/`                     | ❌ | 로그 |

---

## 13. 트러블슈팅

```
❌ Linear 401 Unauthorized / Authentication required
→ LINEAR_API_KEY 확인. Personal API Key가 유효한지 확인.

❌ Linear 403 Forbidden / Entity not found
→ LINEAR_TEAM_ID 확인. API Key 소유자가 해당 팀에 접근 권한이 있는지 확인.

❌ Linear GraphQL errors (field/query 에러)
→ Linear API 스키마 변경 여부 확인. linear_client.py의 쿼리가 최신인지 점검.

❌ Cron이 실행되지 않음
→ crontab -l 확인, PATH에 claude/python3 포함 확인, WSL이면 cron 서비스 시작.

❌ Stop Hook "Permission denied"
→ chmod +x scripts/ralph-stop-hook.sh .claude/hooks/commit-session.sh

❌ 파이프라인 중복 실행
→ .ralph/.pipeline_lock 파일의 PID 확인. 프로세스가 없으면 삭제.

❌ 머지 충돌 (confirmer)
→ 자동 abort 후 skip됨. 수동으로 충돌 해결 후 Confirm 재처리.

❌ Telegram 메시지 안 옴
→ TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 확인. 봇이 채팅방에 추가되었는지 확인.

❌ commit-session.sh 커밋 메시지가 "wip: update N files"만 나옴
→ claude CLI가 PATH에 있는지 확인. claude -p 명령이 실행 가능해야 함.

❌ UserPromptSubmit Hook 메시지가 안 보임
→ .claude/settings.json의 UserPromptSubmit 섹션 확인.

❌ tmux: command not found
→ sudo apt install tmux (WSL/Ubuntu)

❌ worktree 생성 실패 ("fatal: is already checked out")
→ 이전 파이프라인 비정상 종료로 worktree 잔류. git worktree list로 확인 후 git worktree remove <경로> --force

❌ tmux 세션이 바로 종료됨
→ tmux attach -t ralph-XXXXXXXX로 접속하여 에러 확인. Claude CLI PATH, .env 파일 경로 확인.

❌ .worktrees/ 디렉토리가 정리 안 됨
→ git worktree list로 잔류 worktree 확인 후 git worktree remove <경로> --force. 이후 rm -rf .worktrees/
```

---

*이 문서는 프로젝트 아키텍처와 독립적인 자동화 워크플로우 가이드입니다.*
*프로젝트별 기술 스택/코딩 규칙은 각 프로젝트의 CLAUDE.md에 정의합니다.*
