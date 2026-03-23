# Flow-Ops

Claude Code 기반 AI 자율 개발 자동화 파이프라인

```
Linear 이슈 등록 (Queued)
  → AI 자율 코드 구현 (브랜치 격리, 병렬)
  → 자동 테스트/린트 검증
  → PR 자동 생성 + AI 코드 리뷰
  → 승인 시 자동 머지
  → Telegram 알림
```

## 빠른 시작

```bash
# 1. 환경 설정
cp .env.example .env
# .env에 LINEAR_API_KEY, LINEAR_TEAM_ID 등 설정

# 2. 셋업 (Claude Code에서)
/setup

# 3. 파이프라인 실행
/run-pipeline
```

## 문서

| 문서 | 내용 |
|------|------|
| [docs/server-guide.md](docs/server-guide.md) | 서버 배포/운영 (설치, 구동, 모니터링, systemd) |
| [docs/setupClaude.md](docs/setupClaude.md) | 셋업 가이드 (환경 구성, Linear 연동, Hook, Cron) |
| [docs/pipeline-guide.md](docs/pipeline-guide.md) | 파이프라인 운영 가이드 (아키텍처, 실행 흐름) |
| [docs/setupPipeline.md](docs/setupPipeline.md) | 새 프로젝트에 파이프라인 자동 구축 (원테이크) |
| [docs/skills.md](docs/skills.md) | Claude Code 커스텀 스킬 상세 가이드 |

## 모듈 ON/OFF

각 자동화 모듈을 `.env`에서 개별 제어할 수 있습니다 (기본: 모두 ON).

```env
FLOWOPS_AUTO_COMMIT=true     # 세션 종료 시 자동 커밋
FLOWOPS_RALPH_STOP_HOOK=true # Ralph 완료 조건 검증
FLOWOPS_LINEAR_WATCHER=true  # Queued 이슈 감지
FLOWOPS_LINEAR_REPORT=true   # Linear 결과 보고
FLOWOPS_LINEAR_CONFIRM=true  # Confirm 자동 머지
FLOWOPS_AUTO_PR=true         # PR 자동 생성
FLOWOPS_AUTO_MERGE=true      # PR 자동 머지
FLOWOPS_GPT_REVIEW=true      # ChatGPT 코드 리뷰
FLOWOPS_TELEGRAM=true        # Telegram 알림
FLOWOPS_TODO_REMINDER=true   # TODO.md 리마인더
```

상세: [.env.example](.env.example) 참조
