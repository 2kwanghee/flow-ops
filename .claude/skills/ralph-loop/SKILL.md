---
name: ralph-loop
description: Ralph Loop 자율 반복 개발 루프를 시작한다. fix_plan.md 기반으로 미완료 항목을 순서대로 구현하며, 완료 조건 충족 시까지 반복한다.
disable-model-invocation: true
user-invocable: true
---

# Ralph Loop — 자율 반복 개발 모드

> 상세 가이드: `${CLAUDE_SKILL_DIR}/ralph-guide.md`

## 작동 원리

"컨텍스트는 리셋, 코드는 유지" — 각 iteration에서 Claude는 새 컨텍스트로 시작하지만, 이전에 작성한 파일과 git 커밋은 그대로 유지된다.

Stop Hook(`scripts/ralph-stop-hook.sh`)이 Claude의 종료를 가로채서:
1. fix_plan.md 미완료 항목 존재 → 재주입 (루프 계속)
2. 테스트 실패 → 재주입
3. 린트 에러 → 재주입
4. 모든 조건 충족 → 종료 허용

## 실행 방법

```bash
# 포그라운드 실행
bash scripts/ralph-loop.sh

# 오버나이트 (백그라운드)
nohup bash scripts/ralph-loop.sh > ralph-session.log 2>&1 &

# max-iterations 지정 (기본: 30)
bash scripts/ralph-loop.sh --max-iterations 50
```

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `.ralph/PROMPT.md` | 마스터 프롬프트 (루프에 주입) |
| `.ralph/fix_plan.md` | 작업 큐 (우선순위별 체크리스트) |
| `scripts/ralph-loop.sh` | 실행 스크립트 |
| `scripts/ralph-stop-hook.sh` | 완료 조건 검증 Hook |
| `.claude/settings.json` | Hook 등록 + 권한 설정 |

## 완료 신호

- 모든 항목 완료 시: `<promise>DONE</promise>` 출력
- 해결 불가 시: `<promise>BLOCKED</promise>` + 사유 출력

## 긴급 중지

```bash
# Ctrl+C (포그라운드)
# 프로세스 종료 (백그라운드)
kill $(pgrep -f ralph-loop)
```

## 안전장치

1. `permissions.deny` — rm -rf, sudo, force push 차단
2. Stop Hook — 테스트/린트 미통과 시 재시도
3. max-iterations — 무한 루프 방지
4. 브랜치 격리 — ralph/* 브랜치에서만 작업
5. 연속 3회 동일 에러 시 항목 건너뛰기 (`[!]` 표시)

$ARGUMENTS
