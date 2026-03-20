#!/usr/bin/env bash
# GPT API 호출 스크립트 - jq 기반 안전한 JSON 생성
set -euo pipefail

CODE_FILE="$1"
MODEL="${2:-gpt-4o}"

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: OPENAI_API_KEY 환경변수가 설정되지 않았습니다." >&2
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "ERROR: jq가 설치되어 있지 않습니다. 'sudo apt install jq' 또는 'brew install jq'로 설치하세요." >&2
  exit 1
fi

if [ ! -f "$CODE_FILE" ]; then
  echo "ERROR: 파일을 찾을 수 없습니다: $CODE_FILE" >&2
  exit 1
fi

CODE_CONTENT=$(cat "$CODE_FILE")

SYSTEM_PROMPT="You are a senior code reviewer. Critically review the following code/output. Point out bugs, security issues, performance problems, design flaws, and suggest improvements. Be specific and constructive. Respond in Korean."

# jq로 안전하게 JSON 생성 (특수문자, 따옴표, 백슬래시 등 자동 이스케이프)
PAYLOAD=$(jq -n \
  --arg model "$MODEL" \
  --arg system "$SYSTEM_PROMPT" \
  --arg code "$CODE_CONTENT" \
  '{
    model: $model,
    messages: [
      {role: "system", content: $system},
      {role: "user", content: $code}
    ],
    temperature: 0.3
  }')

RESPONSE=$(curl -s -w "\n%{http_code}" \
  https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d "$PAYLOAD")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ne 200 ]; then
  echo "ERROR: GPT API 호출 실패 (HTTP $HTTP_CODE)" >&2
  echo "$BODY" >&2
  exit 1
fi

echo "$BODY" | jq -r '.choices[0].message.content // "응답을 파싱할 수 없습니다."'
