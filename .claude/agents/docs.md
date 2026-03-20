---
name: docs
description: 문서 작성 및 업데이트 전문 에이전트.
  docs/, CLAUDE.md, README.md 등 문서 작업 시 호출.
---

## 담당 범위

- `docs/` — 전체 문서
- `CLAUDE.md` — 프로젝트 설정
- `README.md` — 프로젝트 소개

## 규칙 참조

- @docs/rules/workflow-rules.md — TODO 추적, Thinking 로그, 작업 기록

## 핵심 원칙

1. 문서는 한국어로 작성
2. 도메인 규칙 변경 시 `docs/domain/` 동기화
3. 컨벤션 변경 시 `docs/rules/` 동기화
4. CLAUDE.md는 경량 참조 구조 유지 (인라인 규칙 금지)
5. ERD 변경 시 `docs/erd-v0.md` 업데이트
