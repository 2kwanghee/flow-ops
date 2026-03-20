#!/usr/bin/env bash
# Webhook 서버 + ngrok 터널 시작
# 사용법: bash scripts/start-webhook.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
mkdir -p logs

# ── 기존 프로세스 정리 ──
pkill -f "webhook_server.py" 2>/dev/null || true
pkill -f "ngrok http" 2>/dev/null || true
sleep 1

# ── 1. Webhook 서버 시작 ──
nohup python3 scripts/webhook_server.py > logs/webhook.log 2>&1 &
WEBHOOK_PID=$!
echo "Webhook 서버 시작 (PID: $WEBHOOK_PID)"

# ── 2. ngrok 터널 시작 ──
NGROK_BIN="${HOME}/bin/ngrok"
if [ ! -f "$NGROK_BIN" ]; then
  NGROK_BIN=$(which ngrok 2>/dev/null || echo "")
  if [ -z "$NGROK_BIN" ]; then
    echo "ERROR: ngrok이 설치되어 있지 않습니다."
    echo "  curl -sSL -o /tmp/ngrok.zip https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.zip"
    echo "  python3 -c \"import zipfile; zipfile.ZipFile('/tmp/ngrok.zip').extractall('$HOME/bin')\""
    exit 1
  fi
fi

nohup "$NGROK_BIN" http 9876 --log=stdout > logs/ngrok.log 2>&1 &
NGROK_PID=$!
echo "ngrok 시작 (PID: $NGROK_PID)"
sleep 3

# ── 3. 공개 URL 확인 ──
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import json, sys
data = json.load(sys.stdin)
for t in data.get('tunnels', []):
    if t['public_url'].startswith('https'):
        print(t['public_url'])
        break
" 2>/dev/null || echo "")

if [ -z "$NGROK_URL" ]; then
  echo "WARN: ngrok URL을 가져올 수 없습니다. logs/ngrok.log를 확인하세요."
else
  WEBHOOK_URL="${NGROK_URL}/webhook/linear"
  echo ""
  echo "======================================="
  echo "  Webhook 준비 완료"
  echo "======================================="
  echo "  ngrok URL:   $NGROK_URL"
  echo "  Webhook URL: $WEBHOOK_URL"
  echo "  Health:      $NGROK_URL/health"
  echo ""
  echo "  Linear Webhook URL을 위 주소로 업데이트하세요:"
  echo "  Linear Settings → API → Webhooks → URL 수정"
  echo "======================================="

  # ── 4. Linear Webhook URL 자동 업데이트 시도 ──
  # Linear API로 기존 webhook URL을 업데이트 (향후 구현 가능)

  echo ""
  echo "모니터링:"
  echo "  tail -f logs/webhook.log"
  echo "  curl -s $NGROK_URL/health"
fi

echo ""
echo "종료: bash scripts/stop-webhook.sh"
