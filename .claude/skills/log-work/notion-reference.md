# Notion DB Reference

## DB 속성 매핑

| 속성명 | 타입 | 설명 |
|--------|------|------|
| 작업 이름 | title | 작업 제목 (간결하게) |
| 요청사항 | rich_text | 상세 요구사항 (파이프라인이 이 필드를 읽고 구현) |
| 결과보고 | rich_text | 완료 후 결과 기록 |
| 마감일 | date | 작업 날짜 |
| 작업 유형 | multi_select | 태그 목록 |
| 상태 | status | Backlog / Todo / In progress / Done / Queued / Confirm |
| 우선순위 | select | P1 / P2 / P3 |
| 처리일시 | date | 자동 파이프라인 처리 시간 |
| 담당자 | people | 담당자 |

## 태그 가이드

### 영역 태그 (1개 필수)
- `backend` — FastAPI, SQLAlchemy, Alembic, Python
- `frontend` — Next.js, React, TypeScript, CSS
- `infra` — Docker, CI/CD, 환경설정
- `docs` — 문서, README, 가이드

### 유형 태그 (1개 필수)
- `feature` — 새 기능 구현
- `bugfix` — 버그 수정
- `refactor` — 코드 리팩토링
- `test` — 테스트 추가/수정
- `style` — UI/UX, 스타일링
- `devtools` — 개발 도구, 스크립트
- `devops` — 배포, 파이프라인

## 스크립트 사용법

```bash
# 작업 로그 등록 (상태: Done)
python3 scripts/notion_tracker.py log \
  --title "제목" --summary "내용" --tags "backend,feature" --date "YYYY-MM-DD"

# 태스크 등록
python3 scripts/notion_tracker.py task \
  --title "제목" --summary "내용" --tags "태그" --status "Todo" --date "YYYY-MM-DD"

# 목록 조회
python3 scripts/notion_tracker.py list --status "Todo"

# 상태 업데이트
python3 scripts/notion_tracker.py update \
  --page-id "ID" --status "Done"
```
