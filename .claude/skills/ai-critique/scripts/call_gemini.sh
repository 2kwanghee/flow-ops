#!/usr/bin/env bash
# Gemini API 호출 스크립트 - jq 기반 안전한 JSON 생성
set -euo pipefail

CODE_FILE="$1"
MODEL="${2:-gemini-2.0-flash}"

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "ERROR: GEMINI_API_KEY 환경변수가 설정되지 않았습니다." >&2
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

PROMPT="You are a senior code reviewer. Critically review the following code/output. Point out bugs, security issues, performance problems, design flaws, and suggest improvements. Be specific and constructive. Respond in Korean.

$CODE_CONTENT"

# jq로 안전하게 JSON 생성
PAYLOAD=$(jq -n \
  --arg prompt "$PROMPT" \
  '{
    contents: [{parts: [{text: $prompt}]}],
    generationConfig: {temperature: 0.3}
  }')

RESPONSE=$(curl -s -w "\n%{http_code}" \
  "https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${GEMINI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ne 200 ]; then
  echo "ERROR: Gemini API 호출 실패 (HTTP $HTTP_CODE)" >&2
  echo "$BODY" >&2
  exit 1
fi

echo "$BODY" | jq -r '.candidates[0].content.parts[0].text // "응답을 파싱할 수 없습니다."'
