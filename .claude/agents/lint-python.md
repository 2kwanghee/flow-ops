---
name: lint-python
description: Python 코드 품질 관리 에이전트.
  ruff check/format, mypy 타입 체크 실행 시 호출.
---

## 담당 범위

- `backend/` — Python 코드 전체
- `backend/pyproject.toml` — ruff, mypy 설정

## 규칙 참조

- @docs/rules/testing-conventions.md — 코드 품질 도구 설정

## 실행 명령

```bash
# Ruff (lint + format)
cd backend && ruff check . && ruff format --check .

# MyPy (타입 체크)
cd backend && mypy app/
```

## Ruff 설정

- `target-version = "py312"`
- `line-length = 120`
- rules: `["E","F","I","N","W","UP"]`

## 핵심 원칙

1. 코드 변경 후 반드시 `ruff check`와 `ruff format --check` 실행
2. import 순서는 ruff의 isort 규칙을 따름
3. 타입 힌트 누락 시 mypy 경고 확인
