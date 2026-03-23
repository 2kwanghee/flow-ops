# TODO - 파이프라인 모듈별 ON/OFF 토글 설정
> 생성일: 2026-03-23
> 상태: 완료

## 목표
각 자동화 모듈을 .env에서 개별적으로 ON/OFF 할 수 있도록 구조 변경

## 작업 항목
- [x] `.env.example` 생성 — 모든 토글 설정 기본값 true
- [x] `scripts/pipeline_config.sh` — Shell 스크립트용 설정 로더
- [x] `scripts/pipeline_config.py` — Python 스크립트용 설정 로더
- [x] `commit-session.sh` — FLOWOPS_AUTO_COMMIT 토글 적용
- [x] `ralph-stop-hook.sh` — FLOWOPS_RALPH_STOP_HOOK 토글 적용
- [x] `ralph-loop.sh` — pipeline_config 로드
- [x] `auto_dev_pipeline.sh` — FLOWOPS_LINEAR_WATCHER, FLOWOPS_TELEGRAM 토글 적용
- [x] `linear_reporter.py` — FLOWOPS_LINEAR_REPORT 토글 적용
- [x] `auto_pr_creator.py` — FLOWOPS_AUTO_PR, FLOWOPS_AUTO_MERGE 토글 적용
- [x] `telegram_notify.py` — FLOWOPS_TELEGRAM 토글 적용
- [x] `linear_confirmer.py` — FLOWOPS_LINEAR_CONFIRM 토글 적용
- [x] `gpt_pr_review.py` — FLOWOPS_GPT_REVIEW 토글 적용
- [x] `linear_watcher.py` — FLOWOPS_LINEAR_WATCHER 토글 적용
- [x] `settings.json` UserPromptSubmit hook — FLOWOPS_TODO_REMINDER 토글 적용
- [x] 내부 Telegram 호출 부분 토글 적용 (stop-hook, auto_pr, linear_confirmer)
- [x] Python/Shell 설정 로더 단위 테스트 통과

## 현재 진행 상황
모든 작업 완료

## 메모
- `.env` 파일은 이미 `.gitignore`에 포함되어 있음
- 기본값은 모두 `true` (기존 동작 유지)
- 환경변수가 .env보다 우선순위 높음 (Python에서)
