#!/usr/bin/env python3
"""Linear Webhook 수신 서버.

Linear에서 이슈 상태가 Queued로 변경되면 auto_dev_pipeline.sh를 자동 트리거한다.

Usage:
  python3 scripts/webhook_server.py                    # 기본 포트 9876
  python3 scripts/webhook_server.py --port 8080        # 포트 지정
  python3 scripts/webhook_server.py --dry-run           # 파이프라인 실행 안 함 (로그만)

Linear Webhook 설정:
  1. Linear Settings → API → Webhooks → New webhook
  2. URL: http://<서버IP>:9876/webhook/linear
  3. Events: "Issue" 체크
  4. 저장 후 Signing Secret을 WEBHOOK_SECRET 환경변수에 설정

보안:
  - WEBHOOK_SECRET 설정 시 Linear 서명 검증
  - /health 엔드포인트로 상태 확인 가능
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))
from linear_client import PROJECT_DIR

# ── 설정 ──
DEFAULT_PORT = 9876
DRY_RUN = False
WEBHOOK_SECRET = None

# 중복 실행 방지
_pipeline_lock = threading.Lock()
_last_trigger_time = 0
MIN_TRIGGER_INTERVAL = 30  # 최소 30초 간격


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Linear webhook 서명 검증."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def trigger_pipeline():
    """auto_dev_pipeline.sh를 백그라운드로 실행."""
    global _last_trigger_time

    if not _pipeline_lock.acquire(blocking=False):
        log("SKIP: 파이프라인 이미 실행 중")
        return

    try:
        now = time.time()
        if now - _last_trigger_time < MIN_TRIGGER_INTERVAL:
            log(f"SKIP: 최소 간격 미도달 ({MIN_TRIGGER_INTERVAL}초)")
            return

        _last_trigger_time = now
        pipeline_path = os.path.join(PROJECT_DIR, "scripts", "auto_dev_pipeline.sh")

        if DRY_RUN:
            log("DRY-RUN: 파이프라인 트리거 (실행 안 함)")
            return

        log("TRIGGER: auto_dev_pipeline.sh 실행 시작")

        # 로그 파일
        log_dir = os.path.join(PROJECT_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

        with open(log_file, "w") as lf:
            proc = subprocess.Popen(
                ["bash", pipeline_path],
                stdout=lf, stderr=subprocess.STDOUT,
                cwd=PROJECT_DIR,
            )

        log(f"STARTED: PID {proc.pid}, 로그: {log_file}")

    finally:
        _pipeline_lock.release()


def trigger_confirmer():
    """linear_confirmer.py를 백그라운드로 실행."""
    confirmer_path = os.path.join(PROJECT_DIR, "scripts", "linear_confirmer.py")

    if DRY_RUN:
        log("DRY-RUN: confirmer 트리거 (실행 안 함)")
        return

    log("TRIGGER: linear_confirmer.py 실행 시작")

    log_dir = os.path.join(PROJECT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "confirmer.log")

    with open(log_file, "a") as lf:
        lf.write(f"\n--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        lf.flush()
        proc = subprocess.Popen(
            ["python3", confirmer_path],
            stdout=lf, stderr=subprocess.STDOUT,
            cwd=PROJECT_DIR,
        )

    log(f"STARTED: confirmer PID {proc.pid}, 로그: {log_file}")


class WebhookHandler(BaseHTTPRequestHandler):
    """Linear Webhook HTTP 핸들러."""

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "dry_run": DRY_RUN})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/webhook/linear":
            self._respond(404, {"error": "not found"})
            return

        # Body 읽기
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._respond(400, {"error": "empty body"})
            return

        body = self.rfile.read(content_length)

        # 서명 검증
        if WEBHOOK_SECRET:
            signature = self.headers.get("Linear-Signature", "")
            if not verify_signature(body, signature, WEBHOOK_SECRET):
                log("REJECTED: 서명 검증 실패")
                self._respond(401, {"error": "invalid signature"})
                return

        # JSON 파싱
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid json"})
            return

        # 이벤트 처리
        self._handle_event(payload)
        self._respond(200, {"ok": True})

    def _handle_event(self, payload: dict):
        """Linear webhook 이벤트 처리."""
        action = payload.get("action")
        event_type = payload.get("type")
        data = payload.get("data", {})

        # Issue 이벤트만 처리
        if event_type != "Issue":
            log(f"IGNORE: type={event_type}, action={action}")
            return

        identifier = data.get("identifier", "?")
        title = data.get("title", "?")
        state = data.get("state", {})
        state_name = state.get("name", "?") if isinstance(state, dict) else "?"

        log(f"EVENT: {action} {identifier} '{title}' → {state_name}")

        # 상태별 트리거
        if state_name == "Queued" and action in ("update", "create"):
            log(f"QUEUED: {identifier} — 파이프라인 트리거")
            thread = threading.Thread(target=trigger_pipeline, daemon=True)
            thread.start()
        elif state_name == "Confirm" and action == "update":
            log(f"CONFIRM: {identifier} — confirmer 트리거")
            thread = threading.Thread(target=trigger_confirmer, daemon=True)
            thread.start()
        else:
            log(f"SKIP: {identifier} 상태={state_name}")

    def _respond(self, status: int, body: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format, *args):
        """기본 로그 억제 (자체 로그 사용)."""
        pass


def load_env():
    """Load webhook secret from .env or env vars."""
    global WEBHOOK_SECRET

    secret = os.getenv("WEBHOOK_SECRET")
    if secret:
        WEBHOOK_SECRET = secret
        return

    env_path = os.path.join(PROJECT_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("WEBHOOK_SECRET="):
                    WEBHOOK_SECRET = line.split("=", 1)[1].strip()
                    return


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Linear Webhook 수신 서버")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"포트 (기본: {DEFAULT_PORT})")
    parser.add_argument("--dry-run", action="store_true", help="파이프라인 실행 안 함 (로그만)")
    args = parser.parse_args()

    global DRY_RUN
    DRY_RUN = args.dry_run

    load_env()

    server = HTTPServer(("0.0.0.0", args.port), WebhookHandler)
    log(f"Linear Webhook 서버 시작: http://0.0.0.0:{args.port}")
    log(f"  Webhook URL: http://<서버IP>:{args.port}/webhook/linear")
    log(f"  Health check: http://localhost:{args.port}/health")
    log(f"  서명 검증: {'활성' if WEBHOOK_SECRET else '비활성 (WEBHOOK_SECRET 미설정)'}")
    log(f"  Dry-run: {DRY_RUN}")
    log("")
    log("Linear Settings → API → Webhooks 에서 위 URL을 등록하세요.")
    log("Ctrl+C로 종료")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("서버 종료")
        server.server_close()


if __name__ == "__main__":
    main()
