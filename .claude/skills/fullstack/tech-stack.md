# Tech Stack Reference

## Backend

| 기술 | 버전 | 용도 |
|------|------|------|
| Python | 3.12+ | 런타임 |
| FastAPI | latest | 웹 프레임워크 |
| SQLAlchemy | 2.x (async) | ORM |
| Pydantic | v2 | 데이터 검증/직렬화 |
| Alembic | latest | DB 마이그레이션 |
| asyncpg | latest | PostgreSQL 비동기 드라이버 |
| uv | latest | 패키지 매니저 |

### 디렉토리 컨벤션
- `app/models/` — SQLAlchemy ORM 모델 (DeclarativeBase, UUID PK)
- `app/routers/` — API 라우터 (routers/__init__.py에서 api_router에 등록)
- `app/schemas/` — Pydantic 요청/응답 스키마
- `app/core/` — 설정(config.py), DB 연결(database.py)

### 코딩 패턴
- async/await 기반 비동기 처리
- Depends()를 통한 의존성 주입
- from_attributes=True로 ORM → Pydantic 변환

## Frontend

| 기술 | 버전 | 용도 |
|------|------|------|
| Next.js | 15 | 프레임워크 (App Router) |
| React | 19 | UI 라이브러리 |
| TypeScript | 5.7 | 타입 시스템 |
| pnpm | 9.15.4 | 패키지 매니저 |
| lucide-react | latest | 아이콘 |

### 디렉토리 컨벤션
- `src/app/` — App Router 페이지/레이아웃
- `src/app/(auth)/` — 인증 관련 페이지 (login, signup)
- `src/app/(dashboard)/` — 대시보드 관련 페이지/컴포넌트
- `src/components/` — 공통 컴포넌트
- `src/lib/` — 유틸리티 (api.ts, types.ts, hooks)

### 스타일링
- CSS 변수 기반 커스텀 테마 (다크/라이트)
- 컴포넌트별 CSS 파일 (sidebar.css, calendar.css 등)
- Tailwind 미사용 (향후 도입 예정)

## Database

| 기술 | 버전 | 용도 |
|------|------|------|
| PostgreSQL | 16 | 메인 DB |
| Docker Compose | - | 로컬 DB 컨테이너 |

### 컨벤션
- UUID v4 PK
- created_at / updated_at 감사 컬럼
- soft delete (deleted_at)
- JSONB for custom_fields
