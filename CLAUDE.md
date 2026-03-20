# Flow-Ops — Claude Code 프로젝트 설정

## 프로젝트 개요
업무 자동화 워크플로우 시스템. 한국어로 소통.

## 규칙 참조
- @docs/rules/workflow-rules.md — TODO 추적, Thinking 로그, 작업 기록

## Skills

커스텀 스킬은 `.claude/skills/`에 정의되어 있습니다.

| 스킬 | 용도 | 자율호출 |
|------|------|----------|
| /fullstack | 시니어 풀스택 엔지니어 모드 (FastAPI + Next.js) | O |
| /uiux | UI/UX 전문 엔지니어 모드 (접근성, 반응형, 디자인 시스템) | O |
| /log-work | Linear 작업 로그 자동 기록 | O |
| /prd-to-linear | PRD 분석 → Linear 태스크 자동 등록 | O |
| /run-pipeline | Linear Queued 이슈 자동 개발 파이프라인 즉시 실행 | X |
| /daily-close | 하루 마감 정리 + Linear 일괄 등록 | X |
| /ai-critique | 외부 AI(GPT, Gemini) 코드 비평 | X |
| /tdd-smart-coding | TDD Red-Green-Refactor 루프 개발 | X |
| /ralph-loop | Ralph Loop 자율 반복 개발 | X |
| /setup | 자동화 워크플로우 환경 셋업 | X |
| /merge-worktree | 워크트리 브랜치 squash-merge | X |
| /verify-implementation | 모든 verify 스킬 순차 실행 통합 검증 | X |
| /manage-skills | 세션 변경사항 분석 및 검증 스킬 관리 | X |
