# TODO - 자동화 워크플로우 개선 (Gap 분석 기반)
> 생성일: 2026-03-20
> 상태: 완료

## 목표
목표 아키텍처와 현재 구현 사이의 Gap을 메우는 개선 작업. 7개 Gap을 Phase별로 구현.

## Phase 1 — 파이프라인 뒷단 연결
- [x] Gap 3: 자동 PR 생성 (`scripts/auto_pr_creator.py`)
  - [x] `gh pr create` 기반 자동 PR 생성 스크립트
  - [x] `auto_dev_pipeline.sh`에 PR 생성 단계 추가
  - [x] `.claude/settings.json`에 git push 권한 추가
- [x] Gap 1A: PRD → Linear 스킬
  - [x] `.claude/skills/prd-to-linear/SKILL.md` 신규 생성
  - [x] `scripts/linear_tracker.py`에 Queued/Confirm 상태 옵션 추가

## Phase 2 — CI/CD 기반 구축
- [x] Gap 4: GitHub Actions CI/CD (`.github/workflows/ci.yml`)
- [x] Gap 2: ChatGPT FC Fix Plan 생성 (`scripts/fix_plan_generator.py`)
  - [x] `linear_watcher.py`에 `--use-gpt-plan` 옵션

## Phase 3 — 자동화 완성
- [x] Gap 5: ChatGPT PR 코드 리뷰
  - [x] `.github/workflows/ai-review.yml`
  - [x] `scripts/gpt_pr_review.py`
- [x] Gap 6: 자동 머지 & 배포
  - [x] `linear_confirmer.py` → `gh pr merge` 전환 (PR 존재 시 squash-merge, 없으면 기존 방식 fallback)
  - [x] `.github/workflows/post-merge.yml`

## Phase 4 — 장기
- [ ] Gap 7: SubAgent (Claude Code API 발전 대기)
- [ ] Gap 1B: MCP 서버 도입

## 현재 진행 상황
Phase 1~3 구현 완료. Phase 4는 장기 과제.

## 메모
- PR이 뒷단 전체의 연결 허브 → Gap 3 최우선 ✓
- GitHub Secrets 설정 필요: OPENAI_API_KEY, LINEAR_API_KEY, LINEAR_TEAM_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
- Branch protection 설정 필요: main에 "Require status checks" 활성화
- `gh auth login` 인증 필요
