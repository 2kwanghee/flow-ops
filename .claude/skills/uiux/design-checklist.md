# UI/UX Design Checklist

모든 UI 구현 시 아래 항목을 점검한다.

## 시각적 일관성
- [ ] 기존 디자인 토큰(CSS 변수) 준수: 색상, 폰트, 간격
- [ ] 다크/라이트 테마 모두에서 정상 표시
- [ ] 기존 컴포넌트와 시각적 통일성 유지

## 인터랙션 상태
- [ ] idle — 기본 상태
- [ ] hover — 마우스 오버
- [ ] focus — 키보드 포커스 (outline 표시)
- [ ] active — 클릭/탭 중
- [ ] disabled — 비활성화
- [ ] loading — 로딩 중 (스피너/스켈레톤)
- [ ] error — 에러 상태 (메시지 표시)
- [ ] empty — 데이터 없음 (빈 상태 안내)

## 접근성 (a11y)
- [ ] 키보드만으로 모든 기능 사용 가능
- [ ] 스크린리더 호환 (aria-label, role, alt)
- [ ] 색상 대비 4.5:1 이상 (WCAG AA)
- [ ] 포커스 순서가 논리적
- [ ] 폼 입력에 연결된 label

## 반응형
- [ ] 모바일: 375px 이상
- [ ] 태블릿: 768px 이상
- [ ] 데스크탑: 1280px 이상
- [ ] 터치 타겟 최소 44x44px (모바일)

## 성능
- [ ] 불필요한 리렌더링 방지 (React.memo, useMemo, useCallback)
- [ ] 이미지 최적화 (next/image, lazy loading)
- [ ] 코드 스플리팅 (dynamic import)
- [ ] CSS-in-JS 대신 CSS 파일 사용 (현재 프로젝트 컨벤션)

## 현재 프로젝트 CSS 변수

```css
/* 다크 테마 */
--bg: #0f1117;
--fg: #e5e7eb;
--accent: #3b82f6;

/* 라이트 테마 */
--bg: #f8f9fb;
--fg: #1a1d2e;
```
