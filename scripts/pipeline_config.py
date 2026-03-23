#!/usr/bin/env python3
"""Flow-Ops 파이프라인 모듈 토글 설정 로더 (Python용).

사용법:
    from pipeline_config import is_enabled, check_enabled

    if is_enabled("FLOWOPS_TELEGRAM"):
        send_notification()

    # 비활성 시 스크립트 자체를 종료
    check_enabled("FLOWOPS_AUTO_PR", "PR 자동 생성")
"""

import os
import sys

_PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..")
_env_loaded = False


def _load_env():
    """Load FLOWOPS_* settings from .env file."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True

    env_path = os.path.join(_PROJECT_DIR, ".env")
    if not os.path.exists(env_path):
        return

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if key.startswith("FLOWOPS_"):
                # .env 값은 환경변수보다 낮은 우선순위
                # 환경변수가 이미 설정되어 있으면 .env 값을 덮어쓰지 않음
                if key not in os.environ:
                    os.environ[key] = value


def is_enabled(key: str) -> bool:
    """Check if a module toggle is enabled.

    Returns True if:
      - The key is not set (default: enabled)
      - The value is "true", "1", "on", "yes"
    Returns False if:
      - The value is "false", "0", "off", "no"
    """
    _load_env()
    value = os.environ.get(key, "").strip().lower()

    if not value:
        return True  # 기본값: 활성화

    return value not in ("false", "0", "off", "no")


def check_enabled(key: str, label: str):
    """Check if module is enabled. Exit with 0 if disabled.

    Usage:
        check_enabled("FLOWOPS_AUTO_PR", "PR 자동 생성")
        # 비활성 시 여기서 exit(0)
    """
    if not is_enabled(key):
        print(f"[SKIP] {label} 비활성화됨 ({key}=false)")
        sys.exit(0)
