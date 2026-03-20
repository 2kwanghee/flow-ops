---
name: ai-critique
description: 외부 AI(GPT, Gemini)에 코드 리뷰를 요청합니다. 사용자가 "다른 AI한테도 리뷰 받아봐", "GPT한테 검토 시켜", "외부 리뷰", "AI critique" 등을 요청할 때 사용합니다. 구현 완료 후 품질 검증이 필요할 때 유용합니다.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Glob, Grep
---

# AI Critique - 외부 AI 코드 리뷰

GPT와 Gemini에 코드 리뷰를 요청하여 Claude가 놓칠 수 있는 문제를 잡아냅니다.

## 사전 조건 확인

1. **API 키 확인**: `OPENAI_API_KEY`와 `GEMINI_API_KEY` 환경변수 존재 여부를 먼저 확인한다.
   - 둘 다 없으면: "OPENAI_API_KEY 또는 GEMINI_API_KEY 환경변수를 설정하세요." 안내 후 중단
   - 하나만 있으면: 있는 API만 사용하여 진행
2. **jq 설치 확인**: `command -v jq`로 jq 설치 여부 확인. 없으면 설치 안내.

## 워크플로우

### Step 1: 리뷰 대상 수집
- `$ARGUMENTS`가 파일 경로이면 해당 파일을 읽음
- `$ARGUMENTS`가 없으면 현재 대화에서 가장 최근에 작성/수정한 코드를 대상으로 함
- **코드 크기 가이드**: 500줄을 초과하면 핵심 로직 부분만 발췌하여 전송. 전체 파일 대신 변경된 부분 또는 리뷰가 필요한 핵심 함수/클래스에 집중.

### Step 2: 임시 파일 준비
- 리뷰할 코드를 임시 파일에 저장: `TMPFILE=$(mktemp /tmp/ai-critique-XXXXXX.txt)`
- 민감 정보(API 키, 비밀번호, 토큰 등) 포함 여부를 확인하고, 발견 시 사용자에게 경고

### Step 3: 병렬 API 호출
번들된 스크립트를 사용하여 GPT와 Gemini를 **동시에** 호출한다:

```bash
# 병렬 실행
GPT_RESULT=$(bash ${CLAUDE_SKILL_DIR}/scripts/call_gpt.sh "$TMPFILE" 2>&1) &
GPT_PID=$!
GEMINI_RESULT=$(bash ${CLAUDE_SKILL_DIR}/scripts/call_gemini.sh "$TMPFILE" 2>&1) &
GEMINI_PID=$!

wait $GPT_PID
GPT_EXIT=$?
wait $GEMINI_PID
GEMINI_EXIT=$?
```

API 키가 하나만 있는 경우 해당 API만 호출한다.

### Step 4: 결과 정리 및 발표

```markdown
## GPT Critique
[GPT 피드백 내용 - 실패 시 에러 메시지 표시]

## Gemini Critique
[Gemini 피드백 내용 - 실패 시 에러 메시지 표시]

## 종합 분석
- **공통 지적사항**: 두 모델이 동시에 지적한 문제 (우선 처리 대상)
- **GPT만 지적**: GPT 고유 인사이트
- **Gemini만 지적**: Gemini 고유 인사이트
- **권장 조치**: 구체적인 수정 제안
```

### Step 5: 정리
- 임시 파일 삭제: `rm -f "$TMPFILE"`
- 유효한 지적사항이 있으면 구체적인 수정안 제시

## 에러 처리
- API 호출 실패 시: HTTP 상태 코드와 에러 메시지를 사용자에게 표시
- Rate limit(429) 시: "API 요청 한도 초과. 잠시 후 다시 시도하세요." 안내
- 타임아웃 시: curl에 `--max-time 60` 적용 (스크립트에 포함)

## 주의사항
- 코드에 민감 정보가 포함되어 있지 않은지 반드시 확인 후 전송
- 리뷰 응답은 한국어로 요청됨
- 모델 버전은 스크립트의 두 번째 인자로 변경 가능 (기본: gpt-4o, gemini-2.0-flash)

$ARGUMENTS
