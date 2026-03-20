# Ralph Loop 가이드

> Claude Code 자율 반복 개발 루프 — 실무 사용 가이드

---

## 1. 동작 원리

```
Claude 작업 수행 → 완료 시도 (Stop)
                      │
               Stop Hook 검증
              ┌───────┴───────┐
           미충족            충족
              │               │
         재투입 (계속)    종료 허용 + Telegram 보고
```

**핵심**: 컨텍스트는 리셋되지만 파일(코드)은 유지된다. 매 iteration마다 fix_plan.md를 읽고 미완료 항목을 이어서 처리한다.

### Stop Hook 검증 순서

1. fix_plan.md P1 → P2 → P3 미완료 항목 확인
2. pytest 전체 통과 여부
3. ruff check 에러 0 여부
4. 모두 충족 시 종료 허용

---

## 2. 파일 구조

```
sales-manager/
├── .claude/settings.json       ← 권한 + Stop Hook 설정
├── .ralph/
│   ├── PROMPT.md               ← 마스터 프롬프트 (루프에 주입)
│   ├── fix_plan.md             ← 작업 큐 (우선순위별 체크리스트)
│   └── .iteration_count        ← 자동 생성, 반복 카운터
├── scripts/
│   ├── ralph-loop.sh           ← 실행 스크립트
│   ├── ralph-stop-hook.sh      ← 완료 조건 검증 Hook
│   └── telegram_notify.py      ← 완료 알림 전송
└── CLAUDE.md
```

---

## 3. 사용법

### 3.1 사전 준비

```bash
# DB 실행 확인
docker compose up -d db

# 테스트/린트 현재 상태 확인
cd backend && .venv/bin/python -m pytest --tb=no -q
.venv/bin/ruff check .
```

### 3.2 fix_plan.md 작성

```markdown
## P1: 최우선
- [ ] conftest.py 작성
- [ ] test_auth.py 작성

## P2: 핵심 도메인
- [ ] Contact 모델 + API + 테스트

## P3: 코드 품질
- [ ] ruff 전체 통과
```

| 마크 | 의미 |
|------|------|
| `- [ ]` | 미완료 |
| `- [x]` | 완료 |
| `- [!]` | 건너뜀 (사유 기록 필수) |

### 3.3 실행

```bash
# 포그라운드
bash scripts/ralph-loop.sh

# 백그라운드 (오버나이트)
nohup bash scripts/ralph-loop.sh > ralph-session.log 2>&1 &

# max-iterations 지정 (기본 30)
bash scripts/ralph-loop.sh --max-iterations 50
```

### 3.4 중지

```bash
# 포그라운드: Ctrl+C
# 백그라운드:
kill $(pgrep -f ralph-loop)
```

---

## 4. 프롬프트 작성법

### 필수 4요소

1. **수행할 작업** — 구체적으로
2. **수행 순서** — 구현 → 테스트 → 수정 → 재테스트
3. **완료 조건** — 정량적 (pytest 통과, ruff 0 에러)
4. **금지 행위** — 테스트 삭제/skip 금지, 플레이스홀더 금지

### 예시

```
fix_plan.md를 읽고 미완료([ ]) 항목을 순서대로 완료해줘.

실행 순서:
1. 구현 코드 작성
2. pytest 실행
3. 실패 시: 에러 분석 → 구현 수정 → 재테스트
4. 테스트 삭제/skip 절대 금지

완료 조건:
- fix_plan.md 해당 우선순위 전체 [x]
- pytest 전체 통과
- ruff check 에러 0
```

---

## 5. 모니터링

### 정상 신호

- 테스트 통과 수가 점진적으로 증가
- fix_plan.md 체크항목이 줄어듦
- 커밋 메시지가 구체적

### 이상 신호 (즉시 확인)

- 같은 파일 반복 수정 + 테스트 계속 실패
- 테스트 삭제 또는 skip 처리
- 플레이스홀더/TODO 주석 남김

### 로그 확인

```bash
tail -f ralph-session.log
grep -i "error\|fail" ralph-session.log
```

---

## 6. max-iterations 기준

| 작업 규모 | 권장 값 | 예시 |
|-----------|---------|------|
| 단순 작업 | 5~10 | 단일 API 테스트 |
| 중간 작업 | 10~20 | API 엔드포인트 구현 |
| 대규모 작업 | 20~50 | 모듈 전체 구현 |

---

## 7. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 같은 작업 반복 | 완료 조건 모호 | PROMPT.md 구체화 |
| DB 연결 실패 | Docker DB 미실행 | `docker compose up -d db` |
| 마이그레이션 충돌 | 여러 모델 동시 추가 | "모델 추가 후 즉시 마이그레이션" 규칙 |
| max-iterations 도달 | 작업 범위 과대 | 작게 분할 후 재실행 |

---

## 8. 알림 연동

Ralph Loop 완료 시 **Telegram**으로 자동 보고가 전송된다.

- 정상 완료: 완료 항목 요약 + 테스트 결과 + iteration 수
- 강제 종료 (max-iterations): 미완료 항목 포함 보고

설정: `.env`의 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
