---
name: merge-worktree
description: 현재 워크트리 브랜치를 메인 브랜치(또는 지정 브랜치)에 squash-merge한다. git 히스토리와 소스 코드를 분석하여 포괄적인 커밋 메시지를 작성한다.
argument-hint: "[target-branch]"
disable-model-invocation: true
---

# Merge Worktree

현재 워크트리 브랜치를 대상 브랜치에 squash-merge하고, 구조화된 커밋 메시지를 작성한다.

## 현재 컨텍스트

- Git 디렉토리: `!git rev-parse --git-dir`
- 현재 브랜치: `!git branch --show-current`
- 최근 커밋: `!git log --oneline -20`
- 워킹 트리 상태: `!git status --short`

## 실행 지침

아래 단계를 순서대로 정확히 따른다. 단계를 건너뛰지 않는다.

---

### Phase 1: 검증

1. **워크트리 확인**: `git rev-parse --git-dir` 출력에 `/worktrees/`가 포함되어야 한다. 포함되지 않으면 **즉시 중단**하고 안내한다:
   > "이 스킬은 git 워크트리 내에서 실행해야 합니다. 먼저 `/worktree`로 워크트리를 생성하세요."

2. **현재 브랜치 확인**: `git branch --show-current`로 워크트리 브랜치명을 가져온다.

3. **대상 브랜치 결정**:
   - `$ARGUMENTS`가 제공되면 해당 값을 대상 브랜치로 사용한다.
   - 없으면 기본 브랜치를 감지한다: `main` 존재 여부 확인, 없으면 `master` 확인. 둘 다 없으면 사용자에게 질문한다.

4. **원본 저장소 경로 확인**: `git rev-parse --git-common-dir`로 원본 저장소를 찾고, 그 상위 디렉토리를 원본 저장소 작업 디렉토리로 사용한다.

5. **클린 워킹 트리 확인**: `git status --porcelain` 실행. 커밋되지 않은 변경이 있으면 중단하고 커밋 또는 stash를 안내한다.

---

### Phase 2: 조사

가장 중요한 단계이다. 커밋 메시지를 작성하기 전에 변경 내용을 깊이 이해해야 한다.

1. **커밋 히스토리**: `git log --oneline <target>..HEAD`로 워크트리 브랜치의 모든 커밋을 확인한다.

2. **파일 변경 요약**: `git diff <target>...HEAD --stat`로 변경된 파일과 변경량을 파악한다.

3. **전체 diff**: `git diff <target>...HEAD`로 전체 diff를 읽고 주의 깊게 분석한다.

4. **주요 파일 읽기**: 가장 크게 변경된 파일(큰 diff, 새 파일, 삭제된 파일)은 Read 도구로 전체 컨텍스트를 파악한다 — diff 라인만이 아닌 전체를 이해한다.

5. **변경 분류**: 모든 변경을 다음 카테고리로 그룹화한다:
   - 기능 (새 기능)
   - 수정 (버그 수정)
   - 리팩토링 (동작 변경 없는 코드 재구성)
   - 테스트 (신규 또는 업데이트된 테스트)
   - 문서 (문서 변경)
   - 설정/잡무 (빌드, CI, 도구, 의존성)

6. **주요 타입 결정**: `feat`, `fix`, `refactor`, `docs`, `chore`, `test` 중 전체 작업을 가장 잘 대표하는 타입을 결정한다.

---

### Phase 3: 대상 브랜치 준비

1. **원본 저장소 경로** (Phase 1 step 4에서 확인한 경로)를 사용한다.

2. **대상 브랜치 상태 확인**: `git -C <original-repo-path> log --oneline -10 <target>`로 최근 커밋을 확인한다.

3. **임시 WIP 커밋 감지**: 대상 브랜치에 자동 생성된 WIP 커밋(`wip:`, `auto-commit`, `WIP`으로 시작하는 메시지)이 있으면 사용자에게 경고하고, 머지 전에 마지막 클린 커밋으로 리셋할지 묻는다.

4. **최신 상태 동기화** (리모트가 있는 경우): `git -C <original-repo-path> fetch origin <target> 2>/dev/null`로 대상 브랜치를 최신 상태로 유지한다. 리모트가 없어도 실패하지 않는다.

---

### Phase 4: Squash 머지

1. **대상 브랜치 체크아웃** (원본 저장소에서):
   ```
   git -C <original-repo-path> checkout <target>
   ```

2. **squash 머지 실행**:
   ```
   git -C <original-repo-path> merge --squash <worktree-branch>
   ```

3. **충돌 처리**: 머지 충돌 발생 시:
   - 충돌 파일 목록을 표시한다
   - 충돌 마커를 보여준다
   - **사용자에게 보고하고 중단한다** — 자동 해결을 시도하지 않는다
   - 원본 저장소에서 충돌을 해결한 뒤 다시 스킬을 실행하도록 안내한다

4. 머지가 성공하면(충돌 없음) Phase 5로 진행한다.

---

### Phase 5: 커밋 메시지 작성 및 커밋

Phase 2 조사 결과를 바탕으로, 아래 **정확한 구조**에 따라 커밋 메시지를 작성한다:

```
<type>: <concise summary in imperative mood, under 72 chars, no period>

<2-4 sentence paragraph explaining what was done and WHY. Focus on the
motivation and high-level approach, not implementation details.>

Changes:
- <grouped bullet points of what changed>
- <use sub-bullets for details within a group>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

**규칙:**
- `<type>`은 `feat`, `fix`, `refactor`, `docs`, `chore`, `test` 중 하나여야 한다
- 여러 타입에 걸치는 변경은 주요 타입을 사용한다
- 요약 라인: 명령형 ("add", "fix", "refactor"), 마침표 없음, 최대 72자
- 본문: *왜*와 *컨텍스트*를 설명한다 — 단순히 *무엇*만이 아닌
- Changes: 관련 항목을 그룹화하고, 가장 중요한 것을 먼저 배치한다
- 항상 `Co-Authored-By`로 끝낸다

**원본 저장소에서 heredoc을 사용하여 커밋한다:**
```bash
git -C <original-repo-path> commit -m "$(cat <<'EOF'
<your commit message here>
EOF
)"
```

---

### Phase 6: 검증

1. **커밋 확인**: `git -C <original-repo-path> log --oneline -3`를 실행하고 결과를 사용자에게 보여준다.

2. **결과 보고**: 사용자에게 다음을 안내한다:
   - 최종 커밋 해시
   - 커밋 요약 라인
   - 어떤 브랜치에 머지되었는지
   - 워크트리 브랜치가 아직 존재한다는 점 — 불필요하면 `git worktree remove <path>`로 삭제 가능
   - 리모트에 푸시하려면 `git push` 실행이 필요하다는 점

---

## 주의사항

- 사용자의 명시적 확인 없이 **force-push나 파괴적 git 작업을 하지 않는다**.
- **pre-commit 훅을 건너뛰지 않는다** (`--no-verify` 사용 금지).
- 어떤 단계에서든 예상치 못한 상황이 발생하면 추측하지 말고 **중단하고 설명한다**.
- 커밋 메시지 품질이 가장 중요하다 — Phase 2에서 충분한 시간을 들여 변경 내용을 깊이 이해한다.
