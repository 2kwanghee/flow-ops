# Flow-Ops 파이프라인 원테이크 셋업

> **이 파일을 Claude Code에 전달하면 자동으로 파이프라인이 구축됩니다.**
>
> 사용법: Claude Code에서 이 파일을 읽고 "파이프라인 구축해줘"라고 요청하세요.

---

## 소스 저장소

```
FLOW_OPS_REPO=https://github.com/2kwanghee/flow-ops.git
```

---

## Claude Code 실행 지침

아래 단계를 **순서대로** 실행하라. 각 단계가 완료되면 사용자에게 진행 상황을 알린다.

### Step 1: flow-ops 소스 다운로드

```bash
# /tmp에 클론 (이미 있으면 pull)
if [ -d /tmp/flow-ops ]; then
  cd /tmp/flow-ops && git pull
else
  git clone https://github.com/2kwanghee/flow-ops.git /tmp/flow-ops
fi
```

### Step 2: 설치 스크립트 실행

현재 프로젝트 루트에서 실행한다:

```bash
cd <현재 프로젝트 루트>
bash /tmp/flow-ops/scripts/install-pipeline.sh
```

이 스크립트가 자동으로 수행하는 작업:
- `scripts/` — 자동화 Python/Shell 스크립트 17개 복사
- `.claude/` — 권한, Hook, 스킬 13개 복사 (API 키는 빈 값으로)
- `.github/workflows/` — CI/CD 3개 복사
- `.ralph/PROMPT.md` — 자율 개발 프롬프트 템플릿 생성
- `docs/` — 가이드 문서 복사
- `.gitignore` — 런타임 파일 제외 항목 추가

### Step 3: API 키 설정

사용자에게 다음 정보를 요청한다:

```
파이프라인 설정에 필요한 정보를 알려주세요:

1. [필수] Linear API Key
   → Linear Settings → API → Personal API keys에서 발급
   → https://linear.app/settings/api

2. [필수] Linear Team ID
   → 아래 명령으로 확인하거나 Linear Settings에서 확인
   → 제가 API Key를 받으면 자동으로 조회합니다

3. [선택] OpenAI API Key (AI Fix Plan + PR 코드 리뷰용)
4. [선택] Gemini API Key (AI 코드 비평용)
5. [선택] Telegram Bot Token + Chat ID (알림용)
```

사용자에게서 받은 키를 `.claude/settings.json`의 `env` 섹션에 설정한다:

```json
{
  "env": {
    "LINEAR_API_KEY": "<사용자 입력>",
    "LINEAR_TEAM_ID": "<UUID — 아래 Step 4에서 자동 조회>"
  }
}
```

**주의**: API 키가 담긴 파일 내용을 대화에 출력하지 않는다.

### Step 4: Linear Team ID 조회 및 워크플로우 상태 생성

Linear API Key를 받으면 Team UUID를 자동 조회한다:

```python
# Team UUID 조회
import json
from urllib.request import Request, urlopen

api_key = "<LINEAR_API_KEY>"
query = '{ teams { nodes { id name key } } }'
data = json.dumps({'query': query}).encode()
req = Request('https://api.linear.app/graphql', data=data, method='POST')
req.add_header('Authorization', api_key)
req.add_header('Content-Type', 'application/json')
with urlopen(req) as resp:
    result = json.loads(resp.read())
# result['data']['teams']['nodes']에서 팀 목록 확인
```

Team UUID를 `.claude/settings.json`의 `LINEAR_TEAM_ID`에 설정한다.

그 다음, 워크플로우 상태를 확인하고 **Queued**와 **Confirm**이 없으면 생성한다:

```python
# 기존 상태 확인
LINEAR_API_KEY=<key> LINEAR_TEAM_ID=<uuid> python3 scripts/linear_tracker.py list
```

```python
# Queued 상태 생성 (없는 경우)
mutation = '''
mutation($teamId: String!, $name: String!, $type: String!) {
    workflowStateCreate(input: { teamId: $teamId, name: $name, type: $type, color: "#95a2b3" }) {
        workflowState { id name type }
    }
}
'''
# Queued → type: "unstarted"
# Confirm → type: "started"
```

### Step 5: GitHub CLI 인증

```bash
gh auth status
```

인증되어 있지 않으면 사용자에게 안내한다:

```
GitHub CLI 인증이 필요합니다. 다음 명령을 실행해주세요:
  gh auth login
  → GitHub.com → HTTPS → Login with a web browser
```

gh CLI가 설치되어 있지 않으면:

```bash
# Ubuntu/WSL
sudo apt install gh
# 또는
conda install -c conda-forge gh
```

### Step 6: ngrok 설치 (Webhook용)

```bash
# 이미 설치되어 있는지 확인
which ngrok || [ -f ~/bin/ngrok ]
```

없으면 설치한다:

```bash
mkdir -p ~/bin
curl -sSL -o /tmp/ngrok.zip https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.zip
python3 -c "import zipfile; zipfile.ZipFile('/tmp/ngrok.zip').extractall('$HOME/bin')"
chmod +x ~/bin/ngrok
```

사용자에게 ngrok authtoken을 요청한다:

```
ngrok 인증이 필요합니다:
1. https://dashboard.ngrok.com/signup 에서 무료 가입
2. https://dashboard.ngrok.com/get-started/your-authtoken 에서 토큰 복사
3. 토큰을 알려주세요
```

토큰을 받으면:

```bash
~/bin/ngrok config add-authtoken <TOKEN>
```

### Step 7: PROMPT.md 커스터마이징

`.ralph/PROMPT.md`를 현재 프로젝트에 맞게 수정한다.

현재 프로젝트의 기술 스택을 파악하여 다음을 자동으로 수정:
- **기술 스택**: `package.json`, `requirements.txt`, `go.mod` 등에서 추론
- **테스트 명령**: pytest, jest, go test 등
- **린트 명령**: ruff, eslint, golangci-lint 등
- **디렉토리 구조**: 실제 프로젝트 구조 반영

### Step 8: ralph-stop-hook.sh 커스터마이징

`scripts/ralph-stop-hook.sh`의 테스트/린트 명령을 프로젝트에 맞게 수정한다.

검증 대상:
- 테스트 실행 명령 (pytest → jest 등)
- 린트 실행 명령 (ruff → eslint 등)
- 작업 디렉토리 경로 (backend/ → src/ 등)

### Step 9: GitHub Actions CI 커스터마이징

`.github/workflows/ci.yml`을 프로젝트에 맞게 수정한다.

현재 프로젝트 구조에 따라:
- backend job: Python 버전, 의존성 설치 명령, 테스트 명령
- frontend job: Node 버전, 패키지 매니저 (pnpm/npm/yarn), 빌드 명령
- 불필요한 job 제거 (backend만 있으면 frontend job 삭제, 그 반대도)

### Step 10: 검증

모든 설정이 완료되면 순서대로 검증한다:

```bash
# 1. Linear 연결
LINEAR_API_KEY=<key> LINEAR_TEAM_ID=<uuid> python3 scripts/linear_tracker.py list --status "Todo"

# 2. 워크플로우 상태 확인
# Backlog, Todo, Queued, In Progress, Done, Confirm이 모두 존재해야 함

# 3. Webhook 서버 테스트
python3 scripts/webhook_server.py --dry-run &
sleep 2
curl -s http://localhost:9876/health
kill %1

# 4. gh CLI
gh auth status
```

### Step 11: Webhook 시작 및 Linear 등록

```bash
# Webhook 서버 + ngrok 시작
bash scripts/start-webhook.sh
```

출력된 URL을 사용자에게 보여주고 Linear Webhook 등록을 안내한다:

```
Webhook 서버가 시작되었습니다.

Linear Webhook 등록 방법:
1. Linear Settings → API → Webhooks → New webhook
2. URL: <출력된 ngrok URL>/webhook/linear
3. 데이터 변경 이벤트: "Issues" 체크
4. 저장

등록 완료 후, Linear에서 이슈를 Queued 상태로 만들면
파이프라인이 자동으로 실행됩니다.
```

### Step 12: 최종 보고

사용자에게 설치 결과를 보고한다:

```markdown
## 파이프라인 설치 완료

### 설치된 구성요소
- 자동화 스크립트: scripts/ (17개)
- Claude 스킬: .claude/skills/ (13개)
- CI/CD: .github/workflows/ (3개)
- Webhook 서버: 실행 중

### 사용 방법

**이슈 등록 → 자동 개발:**
1. Linear에서 이슈 생성 (상태: Queued)
2. Webhook이 자동 감지 → Claude 자율 개발 시작
3. 완료 시 PR 자동 생성 → CI 통과 → 자동 머지

**Claude Code에서 직접:**
- `/prd-to-linear <파일>` — PRD → Linear 태스크 등록
- `/run-pipeline` — 파이프라인 즉시 실행
- `/log-work` — 작업 로그 기록

**수동 실행:**
- `bash scripts/start-webhook.sh` — Webhook 시작
- `bash scripts/stop-webhook.sh` — Webhook 종료
- `bash scripts/auto_dev_pipeline.sh` — 파이프라인 수동 실행

### 참고 문서
- `docs/pipeline-guide.md` — 파이프라인 상세 가이드
- `docs/setupClaude.md` — 전체 셋업 참조
```

---

## 트러블슈팅

| 문제 | 해결 |
|------|------|
| `LINEAR_API_KEY required` | `.claude/settings.json`의 env에 키 설정 확인 |
| `graphql error: String! vs ID!` | `team(id:)` → `String!`, `filter: team.id.eq` → `ID!` (스크립트 최신 버전 확인) |
| `gh: command not found` | `sudo apt install gh` 또는 https://cli.github.com |
| `ngrok: command not found` | Step 6 참조 |
| Webhook URL 변경 | ngrok 무료 플랜은 재시작 시 URL 변경됨 → Linear Webhook URL 업데이트 필요 |
| 파이프라인 중복 실행 | `.ralph/.pipeline_lock` 확인 → 프로세스 없으면 삭제 |
| Linear에 Queued 상태 없음 | Step 4에서 자동 생성됨 |
