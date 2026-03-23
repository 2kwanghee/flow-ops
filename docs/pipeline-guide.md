# 자동화 파이프라인 가이드

> 이 문서는 flow-ops 자동화 파이프라인의 **전체 아키텍처, 실행 방법, 트리거 방식**을 설명합니다.
> 초기 셋업은 `docs/setupClaude.md`를 참조하세요.

---

## 전체 아키텍처

```
                        ┌─────────────────────┐
                        │   PRD / 요구사항      │
                        └─────────┬───────────┘
                                  ↓
                        ┌─────────────────────┐
                        │  /prd-to-linear     │  Claude Code 스킬
                        │  (태스크 분해+등록)   │  또는 수동 등록
                        └─────────┬───────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────┐먀
│                     Linear (Queued)                          │
└──────────┬──────────────────────────────────┬────────────────┘
           │                                  │
    ┌──────┴──────┐                    ┌──────┴──────┐
    │  Webhook    │                    │  수동 실행   │
    │  (즉시)     │                    │ /run-pipeline│
    └──────┬──────┘                    └──────┬──────┘
           └──────────────┬───────────────────┘
                          ↓
              ┌───────────────────────┐
              │ auto_dev_pipeline.sh  │
              │ (오케스트레이터)        │
              └───────────┬───────────┘
                          ↓
         ┌────────────────┼────────────────┐
         ↓                ↓                ↓
   ┌───────────┐   ┌───────────┐   ┌───────────┐
   │ tmux +    │   │ tmux +    │   │ tmux +    │   태스크별 병렬
   │ worktree  │   │ worktree  │   │ worktree  │
   │ Claude    │   │ Claude    │   │ Claude    │
   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
         │                │                │
         └────────────────┼────────────────┘
                          ↓
              ┌───────────────────────┐
              │ linear_reporter.py    │  Linear 결과 보고
              │ auto_pr_creator.py    │  자동 PR 생성
              └───────────┬───────────┘
                          ↓
              ┌───────────────────────┐
              │ GitHub Actions        │
              │ ├─ CI (pytest+ruff)   │  자동 테스트/린트
              │ ├─ AI Review (GPT)    │  자동 코드 리뷰
              │ └─ auto-merge         │  CI 통과 시 머지
              └───────────┬───────────┘
                          ↓
              ┌───────────────────────┐
              │ post-merge.yml        │
              │ Linear → Done         │  이슈 자동 완료
              │ Telegram 알림         │
              └───────────────────────┘
```

---

## 트리거 방식 (2가지)

### 1. Webhook — 실시간 자동 트리거

Linear에서 이슈 상태가 **Queued**로 바뀌는 순간 파이프라인이 자동 실행됩니다.

#### 시작 방법

```bash
# 서버 시작 (백그라운드)
nohup python3 scripts/webhook_server.py > logs/webhook.log 2>&1 &

# ngrok 터널 (로컬 PC에서 실행 시)
nohup ~/bin/ngrok http 9876 > logs/ngrok.log 2>&1 &

# 공개 URL 확인
curl -s http://localhost:4040/api/tunnels | python3 -c "
import json,sys
for t in json.load(sys.stdin)['tunnels']:
    print(t['public_url'])
"
```

#### Linear Webhook 등록

1. **Linear Settings → API → Webhooks → New webhook**
2. URL: `https://<ngrok-url>/webhook/linear`
3. 데이터 변경 이벤트: **Issues** 체크
4. 저장

#### 보안 (선택)

`.env`에 `WEBHOOK_SECRET`을 설정하면 Linear 서명 검증이 활성화됩니다:
```env
WEBHOOK_SECRET=<Linear webhook signing secret>
```

#### 동작 흐름

```
Linear 이슈 상태 → Queued
    ↓ (HTTP POST, 즉시)
webhook_server.py (포트 9876)
    ↓ (Queued 이벤트만 필터링)
auto_dev_pipeline.sh 백그라운드 실행
```

- Queued가 아닌 이벤트는 무시
- 30초 간격 제한으로 중복 트리거 방지
- lock 파일로 파이프라인 중복 실행 방지

#### 모니터링

```bash
# Webhook 로그
tail -f logs/webhook.log

# 상태 확인
curl http://localhost:9876/health
```

### 2. 수동 실행 — Claude Code 또는 CLI

#### Claude Code에서

```
/run-pipeline
```

또는 대화에서 "파이프라인 실행해", "Queued 이슈 처리해" 등으로 요청.

#### CLI에서

```bash
# 기본 실행
bash scripts/auto_dev_pipeline.sh

# 시연/테스트용 (짧은 루프)
bash scripts/auto_dev_pipeline.sh --max-turns 5

# 오버나이트 (긴 반복)
bash scripts/auto_dev_pipeline.sh --max-iterations 50
```

---

## 파이프라인 단계별 상세

### Step 1: 이슈 감지 — `linear_watcher.py`

```bash
python3 scripts/linear_watcher.py --per-task
```

- Linear에서 **Queued** 상태 이슈를 우선순위순으로 조회
- 태스크별 `fix_plan.md` 생성 → `.ralph/tasks/{ISSUE_KEY}.md`
- 태스크 매핑 저장 → `.ralph/.task_mapping.json`

**ChatGPT Fix Plan 옵션:**
```bash
python3 scripts/linear_watcher.py --per-task --use-gpt-plan
```
ChatGPT Function Calling으로 코드베이스 맥락을 포함한 구조화된 fix_plan을 생성합니다.
(수정 대상 파일, 구현 단계, 테스트 케이스 포함)

### Step 2: 병렬 실행 — tmux + git worktree

각 태스크마다:
1. `git worktree add` → 독립 작업 디렉토리 생성
2. fix_plan + PROMPT.md → worktree 내부 복사
3. Linear 상태 → **In Progress**
4. `tmux new-session` → Claude 자율 루프 백그라운드 실행

```bash
# 활성 세션 확인
tmux list-sessions | grep "^ralph-"

# 특정 세션 접속
tmux attach -t ralph-FLO-7

# 세션에서 나오기 (세션 유지)
Ctrl+B, D
```

### Step 3: 결과 보고 — `linear_reporter.py`

각 태스크 완료 후:
- fix_plan.md 완료 상태 파싱
- Linear 이슈에 결과 코멘트 추가 (구현 내역 + 커밋 + 테스트)
- 완료 → **Done**, 실패 → **Backlog**

### Step 4: PR 생성 — `auto_pr_creator.py`

```bash
python3 scripts/auto_pr_creator.py --branch ralph/FLO-7 --auto-merge
```

- `git push -u origin ralph/FLO-7`
- `gh pr create` — PR body에 Linear URL + fix_plan 결과 + 테스트 요약 + 변경 파일
- `--auto-merge` 시 CI 통과 후 자동 squash-merge 설정

### Step 5: CI/CD — GitHub Actions

PR 생성 시 자동 실행:

| Workflow | 트리거 | 역할 |
|----------|--------|------|
| `ci.yml` | PR 생성/업데이트 | Backend pytest+ruff, Frontend pnpm lint+build |
| `ai-review.yml` | ralph/* PR 생성 | ChatGPT FC로 코드 리뷰 → PR 코멘트 |
| `post-merge.yml` | PR 머지 | Linear Done + Telegram 알림 |

### Step 6: 머지 — `linear_confirmer.py`

두 가지 머지 경로:

**A. 자동 (PR auto-merge)**
- CI + AI 리뷰 통과 → GitHub가 자동 squash-merge
- post-merge.yml → Linear Done + Telegram

**B. 수동 (사용자 리뷰 후)**
- 사용자가 Linear에서 **Confirm**으로 변경
- `linear_confirmer.py` 실행 → PR이 있으면 `gh pr merge --squash`, 없으면 로컬 `git merge`

---

## 이슈 등록 방법

### 방법 1: Claude Code 스킬 — `/prd-to-linear`

PRD 마크다운을 분석하여 태스크를 자동 분해 + Linear Queued 등록:

```
/prd-to-linear docs/prd-v2.md
```

1. PRD 파일 분석
2. 구현 태스크로 분해 (P1/P2/P3)
3. 사용자 확인
4. Linear에 Queued 상태로 일괄 등록

### 방법 2: Linear 웹 UI에서 수동 등록

1. Linear에서 이슈 생성
2. **title**: 구현할 기능/수정 사항 (간결하게)
3. **description**: AI가 읽고 구현할 상세 요구사항
4. **priority**: Urgent(P1), Medium(P2), Low(P3)
5. **state**: **Queued** 선택

### 방법 3: CLI

```bash
python3 scripts/linear_tracker.py task \
  --title "사용자 프로필 API 추가" \
  --summary "GET /api/users/{id} 엔드포인트 구현. 응답에 이름, 이메일, 가입일 포함." \
  --tags "backend,api" \
  --status "Queued"
```

---

## 로컬 검증 vs CI 검증

| 검증 주체 | 역할 | 시점 | 검증 항목 |
|-----------|------|------|-----------|
| `ralph-stop-hook.sh` | 빠른 피드백 (Claude 루프 내) | 매 iteration | fix_plan 완료 + pytest + ruff |
| GitHub Actions CI | 공식 게이트 (PR 머지 조건) | PR 생성/업데이트 | pytest + ruff + pnpm lint + build |
| AI Review (GPT) | 코드 품질 검증 | PR 생성 | 버그/보안/성능/설계 리뷰 |

---

## 전체 상태 흐름

```
Backlog ──(수동)──→ Todo ──(수동)──→ Queued
                                       │
                               ┌───────┴───────┐
                               │ Webhook 감지   │
                               │ 또는 수동 실행  │
                               └───────┬───────┘
                                       ↓
                                  In Progress
                                       │
                                  [Claude 자율 작업]
                                  [테스트/린트 검증]
                                 ┌─────┴─────┐
                                 ↓           ↓
                               Done       Backlog
                          (PR 자동 생성)  (실패/건너뜀)
                                 │
                          ┌──────┴──────┐
                          ↓             ↓
                    [CI 통과]      [사용자 리뷰]
                    [auto-merge]   [Confirm 전환]
                          ↓             ↓
                    main 반영      gh pr merge
                          │             │
                          └──────┬──────┘
                                 ↓
                          post-merge.yml
                          Linear → Done
                          Telegram 알림
```

---

## 스크립트 참조

| 스크립트 | 용도 | 실행 주체 |
|----------|------|-----------|
| `auto_dev_pipeline.sh` | 파이프라인 오케스트레이터 | Webhook / 수동 |
| `webhook_server.py` | Linear Webhook 수신 서버 | 상시 실행 데몬 |
| `linear_watcher.py` | Queued 이슈 감지 → fix_plan 생성 | 파이프라인 Step 1 |
| `fix_plan_generator.py` | ChatGPT FC로 구조화된 fix_plan 생성 | watcher (--use-gpt-plan) |
| `linear_reporter.py` | 결과 → Linear 보고 (Done/Backlog) | 파이프라인 Step 3 |
| `auto_pr_creator.py` | 자동 PR 생성 + auto-merge 설정 | 파이프라인 Step 4 |
| `gpt_pr_review.py` | ChatGPT FC PR 코드 리뷰 | GitHub Actions |
| `linear_confirmer.py` | Confirm → PR merge 또는 로컬 merge | 수동 / Cron |
| `linear_tracker.py` | Linear CRUD 유틸 | 스킬 / 수동 |
| `telegram_notify.py` | Telegram 알림 | 각 스크립트에서 호출 |
| `ralph-stop-hook.sh` | Claude 종료 조건 검증 | Stop Hook |

---

## 환경 설정

환경변수, GitHub Secrets, Branch Protection 설정은 **[docs/setupClaude.md](setupClaude.md)**를 참조하세요.

---

*초기 셋업: [docs/setupClaude.md](setupClaude.md) | 스킬 가이드: [docs/skills.md](skills.md)*
