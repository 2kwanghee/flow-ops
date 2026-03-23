# Flow-Ops 서버 배포 및 운영 가이드

> 이 문서는 Flow-Ops 자동화 파이프라인 서버를 **설치, 구동, 운영**하는 방법을 다룹니다.
> 초기 환경 설정(API 키, Linear 연동)은 [docs/setupClaude.md](setupClaude.md)를 참조하세요.

---

## 1. 소스 코드 다운로드

### Git 저장소

```
https://github.com/2kwanghee/flow-ops.git
```

### 클론

```bash
git clone https://github.com/2kwanghee/flow-ops.git
cd flow-ops
```

### 기존 프로젝트에 파이프라인 설치

이미 개발 중인 프로젝트에 파이프라인만 추가하려면:

```bash
# 방법 1: 설치 스크립트 (권장)
git clone https://github.com/2kwanghee/flow-ops.git /tmp/flow-ops
cd /path/to/my-project
bash /tmp/flow-ops/scripts/install-pipeline.sh

# 방법 2: 부트스트랩
cd /path/to/my-project
bash /path/to/flow-ops/scripts/bootstrap-automation.sh
```

설치 스크립트가 자동으로 수행하는 작업:
- `scripts/` — Python 스크립트 10개 + Shell 스크립트 7개 복사
- `.claude/` — 권한, Hook, 스킬 13개 복사 (API 키는 빈 값)
- `.github/workflows/` — CI/CD 3개 복사
- `.ralph/PROMPT.md` — 자율 개발 프롬프트 템플릿 생성
- `docs/` — 가이드 문서 복사
- `.gitignore` — 런타임 파일 제외 항목 추가

---

## 2. 사전 요구사항

### 필수 도구

| 도구 | 버전 | 용도 | 설치 |
|------|------|------|------|
| Python | 3.12+ | 자동화 스크립트 | https://python.org |
| Git | 2.40+ | 버전 관리 + worktree | 기본 설치 |
| Claude Code | 최신 | AI 코딩 에이전트 | `npm i -g @anthropic-ai/claude-code` |
| tmux | - | 병렬 세션 관리 | `sudo apt install tmux` |
| GitHub CLI (gh) | - | PR 자동 생성 | `sudo apt install gh` |

### 선택 도구

| 도구 | 용도 | 설치 |
|------|------|------|
| ngrok | Webhook 터널링 (로컬 PC용) | 아래 설치 가이드 참조 |
| jq | `/ai-critique` 스킬 | `sudo apt install jq` |

### Python 의존성

```bash
pip install requests python-dotenv
```

> 자동화 스크립트 전용 의존성입니다. 프로젝트 개발 의존성과 별개입니다.

---

## 3. 환경 설정

### .env 파일 생성

```bash
cp .env.example .env
```

### 필수 환경변수

`.env` 파일을 열어 다음 값을 설정합니다:

```env
# Linear 연동 (필수)
LINEAR_API_KEY=<Linear Personal API Key>
LINEAR_TEAM_ID=<Team UUID>

# Webhook 보안 (권장)
WEBHOOK_SECRET=<Linear webhook signing secret>
```

### 선택 환경변수

```env
# OpenAI — AI Fix Plan + PR 리뷰
OPENAI_API_KEY=<OpenAI API Key>

# Gemini — AI 코드 비평
GEMINI_API_KEY=<Gemini API Key>

# Telegram 알림
TELEGRAM_BOT_TOKEN=<Bot Token>
TELEGRAM_CHAT_ID=<Chat ID>
```

### 모듈 ON/OFF

각 자동화 모듈을 개별적으로 비활성화할 수 있습니다 (기본: 모두 ON):

```env
FLOWOPS_AUTO_COMMIT=true     # 세션 종료 시 자동 커밋
FLOWOPS_RALPH_STOP_HOOK=true # Ralph 완료 조건 검증
FLOWOPS_LINEAR_WATCHER=true  # Queued 이슈 감지
FLOWOPS_LINEAR_REPORT=true   # Linear 결과 보고
FLOWOPS_LINEAR_CONFIRM=true  # Confirm 자동 머지
FLOWOPS_AUTO_PR=true         # PR 자동 생성
FLOWOPS_AUTO_MERGE=true      # PR 자동 머지
FLOWOPS_GPT_REVIEW=true      # ChatGPT 코드 리뷰
FLOWOPS_TELEGRAM=true        # Telegram 알림
FLOWOPS_TODO_REMINDER=true   # TODO.md 리마인더
```

### GitHub CLI 인증

```bash
gh auth login
# → GitHub.com → HTTPS → Login with a web browser
```

### 디렉토리 + 실행 권한

```bash
mkdir -p logs .ralph/tasks .claude/hooks
chmod +x scripts/*.sh .claude/hooks/*.sh
```

---

## 4. 서버 구동

### 4.1 Webhook 서버 (권장 — 실시간 트리거)

Linear에서 이슈 상태가 **Queued**로 바뀌면 파이프라인을 자동 실행하는 HTTP 서버입니다.

#### 한 번에 시작 (Webhook + ngrok)

```bash
bash scripts/start-webhook.sh
```

출력:
```
=======================================
  Webhook 준비 완료
=======================================
  ngrok URL:   https://xxxx.ngrok-free.app
  Webhook URL: https://xxxx.ngrok-free.app/webhook/linear
  Health:      https://xxxx.ngrok-free.app/health
=======================================
```

#### 개별 시작

```bash
# Webhook 서버만 시작 (포트 9876)
nohup python3 scripts/webhook_server.py > logs/webhook.log 2>&1 &

# 포트 변경
nohup python3 scripts/webhook_server.py --port 8080 > logs/webhook.log 2>&1 &

# 테스트 모드 (로그만, 파이프라인 실행 안 함)
python3 scripts/webhook_server.py --dry-run
```

#### ngrok 터널 (로컬 PC에서 실행 시)

외부에서 접근 가능한 URL을 생성합니다:

```bash
# ngrok 설치 (최초 1회)
mkdir -p ~/bin
curl -sSL -o /tmp/ngrok.zip https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.zip
python3 -c "import zipfile; zipfile.ZipFile('/tmp/ngrok.zip').extractall('$HOME/bin')"
chmod +x ~/bin/ngrok

# ngrok 인증 (최초 1회)
# https://dashboard.ngrok.com/get-started/your-authtoken 에서 토큰 발급
~/bin/ngrok config add-authtoken <YOUR_TOKEN>

# ngrok 시작
nohup ~/bin/ngrok http 9876 --log=stdout > logs/ngrok.log 2>&1 &

# 공개 URL 확인
curl -s http://localhost:4040/api/tunnels | python3 -c "
import json, sys
for t in json.load(sys.stdin)['tunnels']:
    if t['public_url'].startswith('https'):
        print(t['public_url'])
"
```

> ngrok 무료 플랜은 재시작 시 URL이 변경됩니다. 변경 시 Linear Webhook URL도 업데이트하세요.

#### 서버 종료

```bash
bash scripts/stop-webhook.sh
```

또는 개별 종료:

```bash
pkill -f "webhook_server.py"
pkill -f "ngrok http"
```

### 4.2 Linear Webhook 등록

1. **Linear Settings → API → Webhooks → New webhook**
2. URL: `https://<ngrok-url>/webhook/linear` (또는 서버 공인 IP)
3. 데이터 변경 이벤트: **Issues** 체크
4. 저장 후 **Signing Secret** 복사 → `.env`의 `WEBHOOK_SECRET`에 설정

```env
WEBHOOK_SECRET=<Linear webhook signing secret>
```

> Signing Secret 설정 시 HMAC-SHA256 기반 서명 검증이 활성화됩니다.

### 4.3 Cron 스케줄 (Webhook 대안)

Webhook 대신 주기적으로 파이프라인을 실행할 수 있습니다:

```bash
crontab -e
```

```cron
# 업무시간 매시: Queued 이슈 자동 개발
0 9-18 * * 1-5 cd /path/to/project && bash scripts/auto_dev_pipeline.sh >> logs/pipeline.log 2>&1

# 매일 자정: 오버나이트 개발 (긴 반복)
0 0 * * * cd /path/to/project && bash scripts/auto_dev_pipeline.sh --max-iterations 50 >> logs/pipeline.log 2>&1

# 업무시간 정오: Confirm 이슈 → main 머지
0 12 * * 1-5 cd /path/to/project && python3 scripts/linear_confirmer.py >> logs/confirmer.log 2>&1
```

> WSL 환경: `sudo service cron start` 필요

---

## 5. 파이프라인 실행

### 자동 실행 (Webhook/Cron)

Linear에서 이슈를 **Queued** 상태로 변경하면 자동으로 파이프라인이 실행됩니다.

### 수동 실행

```bash
# 파이프라인 실행 (Queued 이슈 감지 → 자율 개발)
bash scripts/auto_dev_pipeline.sh

# 시연/테스트용 (짧은 루프)
bash scripts/auto_dev_pipeline.sh --max-turns 5

# 오버나이트 (긴 반복)
bash scripts/auto_dev_pipeline.sh --max-iterations 50
```

### Claude Code에서

```
/run-pipeline
```

### Ralph Loop (단일 태스크)

```bash
# fix_plan.md 작성 후
bash scripts/ralph-loop.sh
bash scripts/ralph-loop.sh --max-iterations 20
```

---

## 6. 모니터링

### 서버 상태 확인

```bash
# Webhook 서버 헬스체크
curl http://localhost:9876/health

# Webhook 로그 실시간 확인
tail -f logs/webhook.log

# ngrok 터널 상태
curl -s http://localhost:4040/api/tunnels | python3 -c "
import json, sys
data = json.load(sys.stdin)
for t in data.get('tunnels', []):
    print(f\"{t['proto']}: {t['public_url']} → {t['config']['addr']}\")
"
```

### 파이프라인 모니터링

```bash
# 활성 Claude 세션 목록
tmux list-sessions | grep "^ralph-"

# 특정 세션 접속 (실시간 로그)
tmux attach -t ralph-OPS-123

# 세션에서 나오기 (세션 유지)
# Ctrl+B, D

# 특정 세션 강제 종료
tmux kill-session -t ralph-OPS-123

# 파이프라인 실행 로그
tail -f logs/pipeline_*.log

# 파이프라인 락 확인
cat .ralph/.pipeline_lock 2>/dev/null && echo "파이프라인 실행 중" || echo "유휴"
```

### 프로세스 확인

```bash
# 실행 중인 서비스 확인
ps aux | grep -E "(webhook_server|ngrok|auto_dev_pipeline)" | grep -v grep
```

---

## 7. GitHub Actions (CI/CD)

PR 생성 시 GitHub에서 자동 실행되는 워크플로우입니다. 별도 서버 구동 불필요.

| Workflow | 파일 | 트리거 | 역할 |
|----------|------|--------|------|
| CI | `.github/workflows/ci.yml` | PR 생성/업데이트 | pytest + ruff + pnpm lint + build |
| AI Review | `.github/workflows/ai-review.yml` | ralph/* PR 생성 | ChatGPT 코드 리뷰 → PR 코멘트 |
| Post-Merge | `.github/workflows/post-merge.yml` | main 머지 | Linear Done + Telegram 알림 |

### GitHub Secrets 설정

GitHub 리포지토리 Settings → Secrets and variables → Actions:

| Secret | 용도 | 필수 |
|--------|------|------|
| `OPENAI_API_KEY` | AI 코드 리뷰 | ai-review.yml 사용 시 |
| `LINEAR_API_KEY` | 머지 후 Linear 업데이트 | post-merge.yml 사용 시 |
| `LINEAR_TEAM_ID` | 머지 후 Linear 업데이트 | post-merge.yml 사용 시 |
| `TELEGRAM_BOT_TOKEN` | 머지 후 Telegram 알림 | 선택 |
| `TELEGRAM_CHAT_ID` | 머지 후 Telegram 알림 | 선택 |

### Branch Protection 설정 (권장)

Settings → Branches → main:
- [x] Require status checks to pass before merging
- [x] Require branches to be up to date before merging
- Status checks: `Backend (pytest + ruff)`, `Frontend (lint + build)`

---

## 8. 서비스 자동 시작 (systemd)

서버 재부팅 시 Webhook 서버를 자동으로 시작하려면 systemd 서비스를 등록합니다.

### 서비스 파일 생성

```bash
sudo tee /etc/systemd/system/flowops-webhook.service << EOF
[Unit]
Description=Flow-Ops Linear Webhook Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(which python3) $(pwd)/scripts/webhook_server.py
Restart=on-failure
RestartSec=10
Environment="PATH=$(dirname $(which python3)):$(dirname $(which git)):$(dirname $(which claude)):/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
EOF
```

### 서비스 등록 및 시작

```bash
sudo systemctl daemon-reload
sudo systemctl enable flowops-webhook
sudo systemctl start flowops-webhook
```

### 서비스 관리

```bash
sudo systemctl status flowops-webhook    # 상태 확인
sudo systemctl restart flowops-webhook   # 재시작
sudo systemctl stop flowops-webhook      # 중지
journalctl -u flowops-webhook -f         # 로그 실시간 확인
```

> systemd 사용 시 ngrok은 별도 서비스로 등록하거나, 고정 IP/도메인을 사용하세요.

### WSL 환경

WSL에서는 systemd 대신 `/etc/wsl.conf`에 시작 명령을 등록합니다:

```ini
[boot]
command=service cron start
```

Cron으로 시작 시 자동 실행:

```bash
@reboot cd /path/to/project && bash scripts/start-webhook.sh >> logs/startup.log 2>&1
```

---

## 9. 디렉토리 구조

```
flow-ops/
├── .env                              ← 환경변수 (Git 제외)
├── .env.example                      ← 환경변수 템플릿
├── scripts/
│   ├── webhook_server.py             ← Webhook 수신 서버 (포트 9876)
│   ├── start-webhook.sh              ← 서버 + ngrok 시작
│   ├── stop-webhook.sh               ← 서버 + ngrok 종료
│   ├── auto_dev_pipeline.sh          ← 파이프라인 오케스트레이터
│   ├── ralph-loop.sh                 ← Ralph 자율 루프
│   ├── ralph-stop-hook.sh            ← 완료 조건 검증 Hook
│   ├── pipeline_config.sh            ← 모듈 ON/OFF 설정 로더 (Shell)
│   ├── pipeline_config.py            ← 모듈 ON/OFF 설정 로더 (Python)
│   ├── linear_client.py              ← Linear API 클라이언트
│   ├── linear_watcher.py             ← Queued 이슈 감지
│   ├── linear_reporter.py            ← Linear 결과 보고
│   ├── linear_confirmer.py           ← Confirm 자동 머지
│   ├── linear_tracker.py             ← Linear CRUD
│   ├── auto_pr_creator.py            ← PR 자동 생성
│   ├── fix_plan_generator.py         ← ChatGPT Fix Plan 생성
│   ├── gpt_pr_review.py              ← ChatGPT 코드 리뷰
│   ├── telegram_notify.py            ← Telegram 알림
│   ├── install-pipeline.sh           ← 타 프로젝트에 설치
│   └── bootstrap-automation.sh       ← 타 프로젝트에 복사
├── .claude/
│   ├── settings.json                 ← 권한 + Hook + 환경변수
│   ├── hooks/
│   │   └── commit-session.sh         ← 세션 종료 시 자동 커밋
│   └── skills/                       ← 커스텀 스킬 13개
├── .github/workflows/
│   ├── ci.yml                        ← PR CI (테스트+린트)
│   ├── ai-review.yml                 ← ralph/* PR AI 리뷰
│   └── post-merge.yml                ← 머지 후 처리
├── .ralph/
│   ├── PROMPT.md                     ← Claude 자율 개발 프롬프트
│   ├── fix_plan.md                   ← 작업 큐 (런타임, Git 제외)
│   └── tasks/                        ← 태스크별 계획 (런타임, Git 제외)
├── docs/
│   ├── setupClaude.md                ← 셋업 가이드
│   ├── pipeline-guide.md             ← 파이프라인 운영 가이드
│   ├── server-guide.md               ← 이 문서
│   ├── skills.md                     ← 스킬 가이드
│   └── setupPipeline.md              ← 원테이크 설치 스크립트
└── logs/                             ← 실행 로그 (Git 제외)
```

---

## 10. 트러블슈팅

```
❌ Webhook 서버가 시작되지 않음
→ 포트 9876이 사용 중인지 확인: lsof -i :9876
→ 다른 포트 사용: python3 scripts/webhook_server.py --port 8080

❌ ngrok URL을 가져올 수 없음
→ ngrok 인증 확인: ~/bin/ngrok config check
→ ngrok 로그 확인: cat logs/ngrok.log
→ 수동 확인: curl -s http://localhost:4040/api/tunnels

❌ Linear Webhook이 트리거되지 않음
→ Linear Webhook URL이 최신인지 확인 (ngrok 재시작 시 변경됨)
→ 이벤트 "Issues"가 체크되어 있는지 확인
→ WEBHOOK_SECRET 불일치: .env와 Linear Webhook 설정의 Signing Secret 비교
→ Health check: curl https://<ngrok-url>/health

❌ 파이프라인이 중복 실행됨
→ .ralph/.pipeline_lock 파일의 PID 확인
→ 프로세스가 없으면 lock 파일 삭제: rm .ralph/.pipeline_lock

❌ tmux 세션이 바로 종료됨
→ tmux attach -t ralph-XXX로 접속하여 에러 확인
→ Claude CLI가 PATH에 있는지 확인: which claude
→ .env 파일 경로 확인

❌ Permission denied (scripts/*.sh)
→ chmod +x scripts/*.sh .claude/hooks/*.sh

❌ systemd 서비스가 시작 실패
→ journalctl -u flowops-webhook -n 50 으로 로그 확인
→ ExecStart 경로가 절대 경로인지 확인
→ User가 올바른지 확인
```

전체 트러블슈팅은 [docs/setupClaude.md](setupClaude.md) 섹션 13을 참조하세요.

---

## 11. 빠른 참조

```bash
# ── 서버 시작/종료 ──
bash scripts/start-webhook.sh       # Webhook + ngrok 시작
bash scripts/stop-webhook.sh        # 종료

# ── 상태 확인 ──
curl http://localhost:9876/health    # Webhook 서버 상태
tmux list-sessions | grep ralph      # Claude 세션 목록

# ── 파이프라인 실행 ──
bash scripts/auto_dev_pipeline.sh    # 수동 실행
bash scripts/ralph-loop.sh           # Ralph 단일 루프

# ── 로그 확인 ──
tail -f logs/webhook.log             # Webhook 로그
tail -f logs/pipeline_*.log          # 파이프라인 로그

# ── Confirm 머지 ──
python3 scripts/linear_confirmer.py  # Confirm → main 머지
```

---

*초기 셋업: [docs/setupClaude.md](setupClaude.md) | 파이프라인 운영: [docs/pipeline-guide.md](pipeline-guide.md) | 스킬: [docs/skills.md](skills.md)*
