---
name: lint-frontend
description: Frontend 코드 품질 관리 에이전트.
  ESLint, TypeScript 타입 체크 실행 시 호출.
---

## 담당 범위

- `frontend/` — 프론트엔드 코드 전체

## 규칙 참조

- @docs/rules/testing-conventions.md — 코드 품질 도구 설정
- @docs/rules/frontend-conventions.md — 프론트엔드 컨벤션

## 실행 명령

```bash
# ESLint
cd frontend && pnpm lint

# TypeScript 타입 체크
cd frontend && pnpm tsc --noEmit
```

## 핵심 원칙

1. 코드 변경 후 반드시 `pnpm lint` 실행
2. TypeScript strict mode 준수
3. `"use client"` 지시어 누락 확인
4. 사용하지 않는 import/변수 제거
