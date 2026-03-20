---
name: prd-to-linear
description: PRD 마크다운 파일을 분석하여 Linear에 태스크를 자동 등록한다. "PRD 올려줘", "이 기획서 태스크로 분리해", "요구사항을 Linear에 등록해" 등의 요청 시 사용.
disable-model-invocation: false
user-invocable: true
---

# PRD → Linear 자동 등록

PRD(Product Requirements Document) 마크다운을 분석하여 구현 태스크로 분해하고 Linear에 Queued 상태로 등록한다.

이 스킬은 다음 상황에서 자율적으로 호출할 수 있다:
- 사용자가 PRD 파일을 제시하며 구현을 요청할 때
- 요구사항 문서가 있고 태스크 분리가 필요할 때

## Workflow

### Step 1: PRD 파일 읽기

`$ARGUMENTS`로 전달된 파일 경로 또는 현재 대화에서 제시된 PRD를 읽는다.

PRD가 없으면 사용자에게 파일 경로를 요청한다:
```
PRD 파일 경로를 알려주세요. (예: docs/prd-v2.md)
```

### Step 2: 태스크 분해

PRD를 분석하여 구현 가능한 태스크 단위로 분해한다.

**분해 기준:**
- 독립적으로 구현/테스트 가능한 단위
- 하나의 PR로 리뷰 가능한 크기
- 명확한 완료 조건(Done criteria)이 있을 것

**우선순위 기준:**
- P1(긴급): 핵심 기능, 다른 태스크의 전제 조건
- P2(일반): 주요 기능, 독립적 구현 가능
- P3(낮음): 개선사항, 문서화, 부가 기능

분해 결과를 사용자에게 먼저 보여주고 확인을 받는다:

```
## 태스크 분해 결과 (N개)

1. [P1] 태스크 제목 — 설명
2. [P2] 태스크 제목 — 설명
...

이대로 Linear에 등록할까요? (수정이 필요하면 말씀하세요)
```

### Step 3: Linear 등록

사용자 확인 후, 각 태스크를 Linear에 Queued 상태로 등록한다:

```bash
python3 scripts/linear_tracker.py task \
  --title "태스크 제목" \
  --summary "상세 설명 + Done criteria" \
  --tags "prd,기능영역" \
  --status "Queued" \
  --date "$(date +%Y-%m-%d)"
```

### Step 4: 결과 보고

```
## Linear 등록 완료

| # | 우선순위 | 태스크 | Linear |
|---|---------|--------|--------|
| 1 | P1 | 태스크 제목 | OPS-XXX |
| 2 | P2 | 태스크 제목 | OPS-XXX |

총 N개 태스크가 Queued 상태로 등록되었습니다.
파이프라인이 자동으로 감지하여 순차 처리합니다.
```

### Step 5: Telegram 알림

```bash
python3 scripts/telegram_notify.py \
  --message "📋 *PRD 태스크 등록 완료*
PRD: PRD 제목
등록: N개 태스크 (P1: X, P2: Y, P3: Z)
상태: Queued → 파이프라인 대기 중"
```

## Rules

- 한국어로 작성한다
- 태스크 제목은 동사로 시작 (구현, 추가, 수정, 설정 등)
- description에 Done criteria를 반드시 포함
- 등록 전 반드시 사용자 확인을 받는다
- PRD에 명시되지 않은 태스크는 추가하지 않는다

$ARGUMENTS
