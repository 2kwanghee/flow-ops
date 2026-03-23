# Claude Code 스킬 가이드

> 이 문서는 프로젝트에 등록된 모든 Claude Code 커스텀 스킬을 정리한 것입니다.
> 스킬 파일 위치: `.claude/skills/<스킬명>/SKILL.md`

---

## 스킬 목록 요약

| 스킬 | 호출 명령 | 용도 | 자율호출 |
|------|-----------|------|----------|
| fullstack | `/fullstack` | 시니어 풀스택 엔지니어 모드 | O |
| uiux | `/uiux` | UI/UX 전문 엔지니어 모드 | O |
| log-work | `/log-work` | Linear 작업 로그 자동 기록 | O |
| daily-close | `/daily-close` | 하루 마감 정리 | X |
| ai-critique | `/ai-critique` | 외부 AI 코드 비평 | X |
| tdd-smart-coding | `/tdd-smart-coding` | TDD 루프 개발 | X |
| ralph-loop | `/ralph-loop` | 자율 반복 개발 루프 | X |
| setup | `/setup` | 자동화 워크플로우 환경 셋업 | X |
| merge-worktree | `/merge-worktree` | 워크트리 브랜치 squash-merge | X |
| verify-implementation | `/verify-implementation` | 통합 검증 보고서 생성 | X |
| prd-to-linear | `/prd-to-linear` | PRD → Linear 태스크 자동 등록 | O |
| run-pipeline | `/run-pipeline` | 파이프라인 즉시 실행 | X |
| manage-skills | `/manage-skills` | 검증 스킬 관리 | X |

> **자율호출 O**: Claude가 조건 충족 시 사용자 요청 없이 자동 실행
> **자율호출 X**: 사용자가 `/명령`으로 직접 호출해야 실행

---

## 개발 모드 스킬

### fullstack — 시니어 풀스택 엔지니어 모드

FastAPI 백엔드 + Next.js 프론트엔드 코드 작업 시 자동 활성화된다.

**전문 영역:**
- Python/FastAPI, SQLAlchemy 2 (async), Pydantic v2, Alembic
- Next.js 15, React 19, TypeScript, pnpm
- PostgreSQL 16, Docker Compose

**작업 원칙:**
1. 코드를 먼저 읽고 기존 패턴을 파악
2. 요청된 것만 정확히 구현 (최소 변경 원칙)
3. 프로젝트 기존 컨벤션 준수
4. 비즈니스 로직 변경 시 테스트 동반
5. OWASP Top 10 보안 취약점 경계

**참조 파일:** `.claude/skills/fullstack/tech-stack.md`

---

### uiux — UI/UX 전문 엔지니어 모드

프론트엔드 UI 작업 시 자동 활성화된다.

**전문 영역:**
- 디자인 시스템 구축, 컴포넌트 아키텍처
- 접근성(WCAG 2.1 AA), 반응형 디자인
- CSS 변수 기반 커스텀 테마 (다크/라이트)

**작업 원칙:**
1. 사용자 경험 최우선
2. 컴포넌트 재사용성 (일관된 디자인 시스템)
3. 접근성 기본 보장 (키보드, 스크린리더, 색상 대비)
4. 모바일 → 태블릿 → 데스크탑 순서 설계
5. 번들 크기, 렌더링 성능, Core Web Vitals 고려

**참조 파일:** `.claude/skills/uiux/design-checklist.md`

---

### tdd-smart-coding — TDD 루프 개발

Red-Green-Refactor 사이클로 기능을 구현한다.

**사이클:**
1. **Red**: 실패하는 테스트 작성 → 실패 확인
2. **Green**: 테스트를 통과시키는 최소한의 코드 작성
3. **Refactor**: 코드 품질 개선 (테스트 통과 유지)
4. 린트 & 포맷 체크
5. 커밋 (작고 집중된 단위)
6. 다음 단위로 반복

**호출 예시:** `/tdd-smart-coding Contact 모델 CRUD API 구현`

**특징:**
- 프로젝트 설정 자동 감지 (패키지 매니저, 테스트 프레임워크, 린터)
- 기존 커밋 컨벤션 자동 파악 및 준수

---

## 기록 & 추적 스킬

### log-work — Linear 작업 로그 (자율호출)

유의미한 코드 변경 완료 후 자동으로 Linear에 기록한다.

**자동 호출 조건:**
- 코드 파일 생성/수정/삭제
- 버그 수정, 기능 구현, 리팩토링 완료
- 설정/인프라 변경, 테스트 추가

**워크플로우:**
1. 현재 대화에서 수행한 작업 요약
2. 기존 Todo/In progress 태스크 확인 → 해당 시 Done 업데이트
3. 작업 로그 등록 (`linear_tracker.py log`)
4. 후속 과제 등록 (해당 시)
5. Telegram 알림 전송

**참조 파일:** `.claude/skills/log-work/linear-reference.md`

---

### daily-close — 하루 마감 정리

하루 작업을 마감하고 종합 분석하여 Linear에 기록한다.

**워크플로우:**
1. Git log + 변경 파일 + 사용자 입력으로 오늘 작업 분석
2. 코드베이스 분석 → 이후 작업 과제 도출
3. Linear에 일일 로그 + 과제 등록
4. 결과 보고

**호출 예시:** `/daily-close` 또는 `/daily-close 오늘 인증 기능 완료`

---

## 품질 관리 스킬

### ai-critique — 외부 AI 코드 비평

GPT와 Gemini에 코드 리뷰를 요청하여 Claude가 놓칠 수 있는 문제를 잡는다.

**사전 요구사항:**
- `OPENAI_API_KEY` 또는 `GEMINI_API_KEY` 환경변수
- `jq` 설치

**워크플로우:**
1. 리뷰 대상 코드 수집
2. 민감 정보 확인 후 임시 파일 생성
3. GPT + Gemini 병렬 API 호출 (번들 스크립트 사용)
4. 공통 지적사항, 각 AI 고유 인사이트, 권장 조치 정리

**호출 예시:** `/ai-critique backend/app/routers/contacts.py`

**번들 스크립트:**
- `scripts/call_gpt.sh` — jq 기반 안전한 JSON 생성으로 GPT 호출
- `scripts/call_gemini.sh` — jq 기반 안전한 JSON 생성으로 Gemini 호출

---

### verify-implementation — 통합 검증

프로젝트에 등록된 모든 `verify-*` 스킬을 순차 실행하여 통합 검증 보고서를 생성한다.

**실행 시점:**
- 새 기능 구현 후
- PR 생성 전
- 코드 리뷰 중

**호출 예시:** `/verify-implementation` 또는 `/verify-implementation verify-api`

---

### manage-skills — 검증 스킬 관리

세션 변경사항을 분석하여 검증 스킬의 드리프트를 탐지하고 수정한다.

**탐지 대상:**
- 커버리지 누락 (어떤 verify 스킬에서도 참조하지 않는 변경 파일)
- 유효하지 않은 참조 (삭제/이동된 파일)
- 누락된 검사 (새 패턴/규칙)
- 오래된 값 (변경된 설정값)

**호출 예시:** `/manage-skills` 또는 `/manage-skills verify-api`

---

## 이슈 관리 스킬

### prd-to-linear — PRD → Linear 태스크 등록 (자율호출)

PRD 마크다운 파일을 분석하여 태스크를 자동 분해하고 Linear에 Queued 상태로 등록한다.

**워크플로우:**
1. PRD 파일 읽기 + 분석
2. 구현 태스크로 분해 (P1/P2/P3 우선순위)
3. 사용자 확인
4. Linear에 Queued 상태로 일괄 등록

**호출 예시:** `/prd-to-linear docs/prd-v2.md`

---

### run-pipeline — 파이프라인 즉시 실행

Linear Queued 이슈를 감지하고 자동 개발 파이프라인을 즉시 실행한다.

**호출 예시:** `/run-pipeline`

---

## 자동화 스킬

### ralph-loop — 자율 반복 개발 루프

`fix_plan.md` 기반으로 미완료 항목을 순서대로 구현하며, 완료 조건 충족 시까지 반복한다.

**동작 원리:** "컨텍스트는 리셋, 코드는 유지" — 각 iteration에서 Claude는 새 컨텍스트로 시작하지만, 이전에 작성한 파일과 git 커밋은 유지된다.

**완료 조건:**
1. fix_plan.md 모든 항목 완료
2. pytest 전체 통과
3. ruff check 에러 0

**핵심 파일:**
- `.ralph/PROMPT.md` — 마스터 프롬프트
- `.ralph/fix_plan.md` — 작업 큐 (우선순위별 체크리스트)
- `scripts/ralph-loop.sh` — 실행 스크립트
- `scripts/ralph-stop-hook.sh` — 완료 조건 검증 Hook

**안전장치:**
- `permissions.deny` — rm -rf, sudo, force push 차단
- max-iterations (기본 30) — 무한 루프 방지
- 연속 3회 동일 에러 시 항목 건너뛰기

**참조 파일:** `.claude/skills/ralph-loop/ralph-guide.md`

---

### setup — 자동화 워크플로우 환경 셋업

Linear 기반 AI 자율 개발 파이프라인을 셋업한다.

**셋업 대상:**
- Python 의존성 (requests, python-dotenv)
- Linear API 연동 검증
- Telegram 알림 설정 (선택)
- Stop Hook 경로 확인
- Cron 스케줄 등록 안내

**호출 예시:** `/setup`

> 이 스킬은 프로젝트 개발환경(언어, 프레임워크, DB) 셋업이 아니다. 자동화 파이프라인 환경만 구성한다.

---

## Git 작업 스킬

### merge-worktree — 워크트리 브랜치 squash-merge

현재 워크트리 브랜치를 대상 브랜치에 squash-merge하고, 구조화된 커밋 메시지를 작성한다.

**단계:**
1. 워크트리 및 클린 상태 검증
2. 커밋 히스토리, diff, 주요 파일 조사
3. 대상 브랜치 준비 (WIP 커밋 감지)
4. Squash 머지 실행
5. 커밋 메시지 작성 (conventional commit 형식)
6. 결과 검증 및 보고

**호출 예시:** `/merge-worktree` 또는 `/merge-worktree main`

---

## 참조 파일 목록

| 파일 | 소속 스킬 | 내용 |
|------|-----------|------|
| `fullstack/tech-stack.md` | fullstack | 기술 스택 상세 (버전, 디렉토리 컨벤션, 코딩 패턴) |
| `log-work/linear-reference.md` | log-work | Linear DB 속성 매핑, 태그 가이드, 스크립트 사용법 |
| `uiux/design-checklist.md` | uiux | UI/UX 디자인 점검 체크리스트 |
| `ralph-loop/ralph-guide.md` | ralph-loop | Ralph Loop 실무 사용 가이드 |
| `ai-critique/scripts/call_gpt.sh` | ai-critique | GPT API 호출 스크립트 (jq 기반) |
| `ai-critique/scripts/call_gemini.sh` | ai-critique | Gemini API 호출 스크립트 (jq 기반) |
