# Linear Issue Reference

## 이슈 필드 매핑

| 필드 | Linear 속성 | 설명 |
|------|-------------|------|
| 제목 | title | 이슈 제목 (간결하게) |
| 요청사항 | description | 상세 요구사항 (마크다운) |
| 결과보고 | comment | 완료 후 코멘트로 결과 기록 |
| 마감일 | dueDate | 작업 날짜 |
| 라벨 | labels | 태그 목록 |
| 상태 | state | Backlog / Todo / Queued / In Progress / Done / Confirm |
| 우선순위 | priority | 1(Urgent)=P1, 3(Medium)=P2, 4(Low)=P3 |
| 담당자 | assignee | 담당자 |

## 라벨 가이드

### 영역 라벨 (1개 필수)
- `backend` — FastAPI, SQLAlchemy, Alembic, Python
- `frontend` — Next.js, React, TypeScript, CSS
- `infra` — Docker, CI/CD, 환경설정
- `docs` — 문서, README, 가이드

### 유형 라벨 (1개 필수)
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
python3 scripts/linear_tracker.py log \
  --title "제목" --summary "내용" --tags "backend,feature" --date "YYYY-MM-DD"

# 태스크 등록
python3 scripts/linear_tracker.py task \
  --title "제목" --summary "내용" --tags "태그" --status "Todo" --date "YYYY-MM-DD"

# 목록 조회
python3 scripts/linear_tracker.py list --status "Todo"

# 상태 업데이트
python3 scripts/linear_tracker.py update \
  --issue-id "UUID" --status "Done"
```
