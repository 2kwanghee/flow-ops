---
name: run-pipeline
description: Linear Queued 이슈를 감지하여 자동 개발 파이프라인을 즉시 실행한다. "파이프라인 실행", "Queued 이슈 처리해", "자동 개발 시작", "이슈 작업 시작" 등의 요청 시 사용.
disable-model-invocation: true
user-invocable: true
---

# 자동 개발 파이프라인 즉시 실행

Linear에 등록된 Queued 이슈를 감지하고 Claude 자율 루프로 자동 개발을 시작한다.

## Workflow

### Step 1: Queued 이슈 확인

```bash
python3 scripts/linear_watcher.py --per-task --dry-run
```

Queued 이슈가 없으면 사용자에게 알린다:
```
Queued 이슈가 없습니다. Linear에서 이슈 상태를 Queued로 설정하세요.
```

### Step 2: 실행 확인

발견된 이슈 목록을 보여주고 확인을 받는다:
```
## Queued 이슈 (N개)
1. [P1] OPS-123 — 태스크 제목
2. [P2] OPS-124 — 태스크 제목

파이프라인을 실행할까요? (각 이슈마다 독립 브랜치에서 Claude가 자율 작업)
```

`$ARGUMENTS`에 `--auto`가 있으면 확인 없이 바로 실행.

### Step 3: 파이프라인 실행

```bash
# 기본 실행 (max 30 iterations)
bash scripts/auto_dev_pipeline.sh

# 시연/테스트용 (짧은 루프)
bash scripts/auto_dev_pipeline.sh --max-turns 5
```

### Step 4: 결과 확인

파이프라인이 백그라운드(tmux)에서 실행되므로 모니터링 명령을 안내한다:
```
파이프라인이 시작되었습니다.

모니터링:
  tmux list-sessions | grep ralph    # 활성 세션 확인
  tmux attach -t ralph-OPS-123       # 특정 세션 접속

완료 후:
  - Linear 이슈 상태가 자동 업데이트됩니다 (Done/Backlog)
  - PR이 자동 생성됩니다
  - Telegram 알림이 전송됩니다
```

## Rules

- 파이프라인은 tmux에서 백그라운드 실행되므로 현재 세션을 차단하지 않음
- `--max-turns` 옵션으로 시연용 짧은 실행 가능
- 중복 실행 방지: lock 파일이 이미 있으면 실행하지 않음

$ARGUMENTS
