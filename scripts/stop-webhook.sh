#!/usr/bin/env bash
# Webhook 서버 + ngrok 종료
# 사용법: bash scripts/stop-webhook.sh
pkill -f "webhook_server.py" 2>/dev/null && echo "Webhook 서버 종료" || echo "Webhook 서버 미실행"
pkill -f "ngrok http" 2>/dev/null && echo "ngrok 종료" || echo "ngrok 미실행"
