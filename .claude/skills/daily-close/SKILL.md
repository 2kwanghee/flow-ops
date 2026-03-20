---
name: daily-close
description: 하루 마감 시 git 로그, 변경 파일, 코드베이스를 종합 분석하여 Linear에 일일 작업 로그와 향후 과제를 일괄 등록한다.
disable-model-invocation: true
user-invocable: true
---

하루 작업을 마감하고, Linear에 기록하며, 추적 가능한 이후 과제를 생성하는 일일 마감 스킬이다.

## Linear 이슈 필드

`log-work` 스킬의 `linear-reference.md`에서 이슈 필드 상세를 참조한다.
- title, dueDate, description, labels, state (Backlog/Todo/In Progress/Done)

## Workflow

### Step 1: 오늘의 작업 분석

아래를 모두 확인하여 오늘 작업한 내용을 파악한다:

1. **Git log 확인** — 오늘 날짜의 커밋 목록
   ```bash
   git log --since="$(date +%Y-%m-%d) 00:00" --oneline --all 2>/dev/null || echo "No git history"
   ```

2. **변경된 파일 확인** — 오늘 수정된 파일 목록
   ```bash
   find . -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.json" -o -name "*.md" | head -200 | xargs ls -la --time-style=+%Y-%m-%d 2>/dev/null | grep "$(date +%Y-%m-%d)"
   ```

3. **사용자 직접 입력** — $ARGUMENTS에 포함된 내용

### Step 2: 코드베이스 분석 (이후 작업 도출)

현재 구현 상태를 분석하여 보수/추가 필요 사항을 도출한다:

1. **BACKLOG.md의 미완료 TODO** 확인
2. **Backend 분석**:
   - `backend/app/models/` — ERD 대비 미구현 모델
   - `backend/app/routers/` — 미구현 API 엔드포인트
   - `backend/tests/` — 테스트 커버리지 부족 영역
   - 코드 내 TODO/FIXME/HACK 주석
3. **Frontend 분석**:
   - `frontend/src/` — 미구현 페이지/컴포넌트
   - 하드코딩된 값, 임시 구현체
   - 코드 내 TODO/FIXME 주석
4. **Infra 분석**:
   - CI/CD 파이프라인 유무
   - 환경설정 누락 사항

### Step 3: Notion에 기록

#### 3-1. 기존 항목 확인 (중복 방지)

```bash
python3 ./scripts/linear_tracker.py list --status "Todo"
python3 ./scripts/linear_tracker.py list --status "In progress"
```

#### 3-2. 일일 작업 로그 등록

```bash
python3 ./scripts/linear_tracker.py log \
  --title "[YYYY-MM-DD] 작업 요약 제목" \
  --summary "• 작업1 내용
• 작업2 내용
• 작업3 내용" \
  --tags "tag1,tag2" \
  --date "YYYY-MM-DD"
```

#### 3-3. 이후 작업 과제 등록

분석에서 도출된 각 과제를 개별 태스크로 등록한다 (기존 항목과 중복되지 않는 것만):

```bash
python3 ./scripts/linear_tracker.py task \
  --title "과제 제목" \
  --summary "상세 설명 (무엇을, 왜, 어디서)" \
  --tags "backend,feature" \
  --status "Todo|Backlog" \
  --date "YYYY-MM-DD"
```

#### 3-4. 기존 태스크 상태 업데이트 (해당 시)

오늘 완료된 기존 태스크가 있다면 상태를 업데이트한다:

```bash
python3 ./scripts/linear_tracker.py update \
  --issue-id "이슈ID" \
  --status "Done"
```

### Step 4: 결과 보고

사용자에게 아래 형식으로 보고한다:

```
## 오늘의 작업 로그
- [작업 내용 bullet points]
- Notion: [페이지 URL]

## 등록된 이후 과제
| 과제 | 상태 | 태그 |
|------|------|------|
| ...  | Todo | ... |

## 현재 진행 상황
- Todo: N건
- In Progress: N건
- Done: N건
```

## Rules

- 한국어로 작성한다
- 작업 내용이 없으면 사용자에게 물어본다
- 이후 과제는 구체적이고 실행 가능한 단위로 쪼갠다 (예: "프론트엔드 개선" X -> "Contacts 목록 페이지 구현" O)
- 이미 Notion에 등록된 과제와 중복되지 않도록 기존 목록을 먼저 확인한다
- BACKLOG.md의 TODO 항목과 코드 분석 결과를 종합하여 과제를 도출한다

$ARGUMENTS
