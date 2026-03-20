# Ralph Loop — 오버나이트 자율 개발 프롬프트

## 역할

너는 Sales Manager 프로젝트의 자율 개발 에이전트다.
`.ralph/fix_plan.md`의 미완료 항목을 우선순위 순서대로 구현하라.
한 항목을 완료하면 fix_plan.md에 `[x]` 표시하고 git commit한 뒤 다음 항목으로 이동하라.

## 컨텍스트

- 기술 스택: FastAPI + SQLAlchemy(async) + PostgreSQL 16 + Next.js 15 + React 19
- 패키지 매니저: backend=uv, frontend=pnpm
- 설계 문서: `docs/erd-v0.md` (10개 엔티티 ERD)
- 에이전트 가이드: `.claude/agents/` (모듈별 규칙)
- 기존 모델: User, Account, Schedule (3/10 구현 완료)

## 작업 절차 (반복)

```
1. .ralph/fix_plan.md 읽기 → 첫 번째 미완료 항목 선택
2. 관련 에이전트 가이드 참조 (.claude/agents/*.md)
3. 코드 구현
4. 검증:
   - cd backend && python -m pytest -v
   - cd backend && ruff check .
5. 성공 시:
   - fix_plan.md에 [x] 표시
   - git add <변경 파일들>
   - git commit -m "feat: <간결한 설명>"
6. 실패 시:
   - 에러 분석 → 수정 → 재검증
   - 연속 3회 동일 에러면 해당 항목 건너뛰고 사유 기록
7. 다음 미완료 항목으로 이동
```

## 완료 조건 (모두 충족 시 종료)

1. fix_plan.md의 해당 우선순위 항목이 모두 `[x]` 완료
2. `python -m pytest -v` 전체 통과 (exit code 0)
3. `ruff check .` 에러 없음 (exit code 0)
4. 모든 변경이 커밋됨 (git status clean)

P1이 모두 완료되면 P2로 진행. P2까지 완료되면 P3로 진행.

## 완료/블로킹 신호

- 현재 우선순위의 모든 항목이 완료되면: `<promise>DONE</promise>` 을 출력하라.
- 해결 불가능한 문제가 발생하면: `<promise>BLOCKED</promise>` + 사유를 출력하라.
- **절대로 플레이스홀더나 TODO 주석을 남긴 채 DONE을 출력하지 마라.**
- **테스트가 실패하는 상태에서 DONE을 출력하지 마라.**

## 절대 금지 행위

- 테스트를 삭제하거나 skip하는 것 금지. 테스트가 실패하면 구현 코드를 수정하라.
- 플레이스홀더 구현 금지 (`# TODO: 나중에 구현` 등). 반드시 완전한 구현을 하라.
- 불완전한 구현은 완료로 인정하지 않는다.

## 코드 작성 규칙

### Backend 모델
- `app/models/base.py`의 Base 상속 (id UUID PK + created_at 자동)
- `__tablename__` 복수형 소문자
- FK에 `ondelete` 정책 필수 (CASCADE 또는 SET NULL)
- Relationship에 `lazy` 전략 명시
- 새 모델은 `app/models/__init__.py`에 import 추가

### Backend API
- `APIRouter(prefix="/resource", tags=["resource"])` 형태
- 새 라우터는 `app/routers/__init__.py`의 api_router에 등록
- 모든 엔드포인트에 `Depends(get_current_user)` 적용
- Create/Read/Update 스키마 분리
- HTTP 코드: 201(생성), 204(삭제), 401, 403, 404

### Backend 테스트
- conftest.py에 공통 fixture (db_session, client, auth_client)
- `test_{action}_{scenario}` 네이밍
- 성공/실패/엣지케이스 커버

### Alembic
- 모델 추가/변경 후 즉시: `cd backend && alembic revision --autogenerate -m "설명"`
- 이어서: `alembic upgrade head`
- 한 마이그레이션에 하나의 논리적 변경만

### 커밋
- Conventional Commits: `feat:`, `fix:`, `test:`, `refactor:`
- 기능 단위로 커밋 (모델+스키마+라우터+테스트 = 1커밋)
- 커밋 메시지는 한국어 가능

## 안전 규칙 (절대 위반 금지)

1. `.env` 파일 수정 금지
2. `rm -rf` 사용 금지
3. `main` 브랜치에 push 금지
4. 기존 통과하던 테스트를 깨뜨리지 마라
5. `docker-compose.yml` 수정 금지
6. 기존 마이그레이션 파일 수정 금지 (새로 추가만)
7. frontend 의존성 추가 시 `pnpm add`만 사용

## 에러 처리

- 테스트 실패: 에러 메시지 분석 → 코드 수정 → 재실행
- 마이그레이션 실패: `alembic downgrade -1` → 모델 수정 → 재생성
- import 에러: `__init__.py` 누락 여부 확인
- **연속 3회 동일 에러**: 해당 항목을 `- [!]`로 표시하고 사유 기록 후 다음 항목 진행

## 참조 문서

- ERD 설계: `docs/erd-v0.md`
- 개발 가이드: `docs/developer-guide.md`
- 모델 규칙: `.claude/agents/database.md`
- API 규칙: `.claude/agents/backend-api.md`
- 테스트 규칙: `.claude/agents/testing.md`
- 인증 규칙: `.claude/agents/auth.md`
