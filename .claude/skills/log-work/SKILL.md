---
name: log-work
description: 코드 작업 완료 후 즉시 Linear에 작업 로그를 기록한다. 유의미한 코드 변경(기능 구현, 버그 수정, 리팩토링, 테스트 추가, 인프라 변경) 완료 시 자율적으로 호출한다.
disable-model-invocation: false
user-invocable: true
---

완료된 작업을 즉시 Linear에 기록하는 실시간 작업 로거이다.

이 스킬은 유의미한 작업 완료 후 자율적으로 호출해야 한다 — 사용자가 요청할 때까지 기다리지 않는다. 다음 상황에서 자동 호출한다:
- 코드 파일이 생성되거나 크게 수정됨
- 버그가 수정됨
- 기능이 구현됨
- 설정 또는 인프라 변경이 이루어짐
- 리팩토링이 완료됨
- 테스트가 추가되거나 업데이트됨

## Notion DB 속성

이슈 필드 매핑 및 라벨 가이드는 이 스킬 디렉토리의 `linear-reference.md`를 참조한다.

## Workflow

### Step 1: 방금 완료한 작업 요약

현재 대화에서 수행한 작업을 분석한다:
- 어떤 파일을 생성/수정/삭제했는가
- 어떤 문제를 해결했는가
- 어떤 기능을 구현했는가

$ARGUMENTS가 있으면 해당 내용을 포함한다.

### Step 2: 기존 태스크 확인

```bash
python3 scripts/linear_tracker.py list --status "Todo"
python3 scripts/linear_tracker.py list --status "In progress"
```

방금 완료한 작업이 기존 Todo/In progress 태스크에 해당하면 해당 태스크를 Done으로 업데이트한다:

```bash
python3 scripts/linear_tracker.py update \
  --issue-id "이슈ID" \
  --status "Done"
```

### Step 3: 작업 로그 등록

```bash
python3 scripts/linear_tracker.py log \
  --title "작업 요약 (간결하게)" \
  --summary "• 변경사항1
• 변경사항2
• 영향받은 파일: file1, file2" \
  --tags "적절한태그" \
  --date "$(date +%Y-%m-%d)"
```

### Step 4: 후속 과제 등록 (해당 시)

작업 중 발견한 추가 작업이 있으면 태스크로 등록한다 (기존 항목과 중복 확인 후):

```bash
python3 scripts/linear_tracker.py task \
  --title "과제 제목" \
  --summary "상세 설명" \
  --tags "태그" \
  --status "Todo" \
  --date "$(date +%Y-%m-%d)"
```

### Step 5: Telegram 알림 전송

Linear 기록이 완료되면 Telegram으로 결과를 알린다:

```bash
python3 scripts/telegram_notify.py \
  --message "📋 *작업 완료*
제목: 작업 제목
• 변경사항 요약 (1~3줄)
🔗 Notion URL"
```

### Step 6: 간결한 결과 보고

```
> Linear 기록 완료: [작업 제목] | [Linear URL]
> Telegram 알림 전송 완료
```

기존 태스크를 업데이트한 경우:
```
> 태스크 완료 처리: [태스크 제목]
```

## Rules

- 한국어로 작성한다
- 간결하게 — 사용자의 작업 흐름을 방해하지 않는다
- 사소한 변경(오타 수정, 포맷팅)은 기록하지 않는다
- 여러 작업을 한 번에 수행한 경우 하나의 로그로 통합한다
- 커밋 메시지 스타일로 제목을 작성한다 (동사로 시작: 구현, 수정, 추가, 리팩토링 등)

$ARGUMENTS
