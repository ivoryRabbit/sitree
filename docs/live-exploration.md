# Live Exploration Mode — Feasibility

> **상태**: 설계 단계. 구현 전 아래 4가지 캡처 방식 중 하나를 선택해야 함.

## 원하는 동작 (UX 정의)

1. 사용자가 sitree 대시보드(웹)를 띄워둠
2. 사용자가 자기 브라우저에서 대상 사이트를 자유롭게 탐색
3. 대시보드의 트리 그래프가 **실시간으로** 반응:
   - **방문한 적 있는 노드**: 실선 테두리
   - **방문 안 한 노드**(링크로만 발견됨): 점선 테두리
   - **현재 보고 있는 페이지**: 배경 강조 + 펄스 애니메이션
   - **새 페이지가 발견되면**: 노드/엣지가 그래프에 즉시 추가

## 시스템 구성요소

```
   [사용자 브라우저]  ──(이벤트)──►  [sitree 백엔드]  ──(WS push)──►  [Svelte 대시보드]
        ▲                                │
        │                                ├─► 동시에 백그라운드 크롤러가
        │                                │   해당 URL의 링크 확장 (옵션)
        └────────────────────────────────┘
```

- WebSocket으로 백엔드 → 프런트에 그래프 패치(JSON Patch 또는 자체 op) 푸시 — **기술적으로 단순**
- 핵심 난이도는 **"사용자가 어디를 보고 있는지" 캡처하는 방법**

## 캡처 방식 4가지 비교

| 방식 | 사용자 UX | 구현 난이도 | 권한·보안 | 어떤 사이트도 가능? |
|---|---|---|---|---|
| **A. 브라우저 확장** | 평소 쓰던 Chrome/Firefox 그대로 + 확장 한 번 설치 | 중 (확장 + permissions + 메시징) | host_permissions 필요. 사용자가 설치 시 명시적 동의 | ✅ |
| **B. CDP 연결 (디버그 모드 Chrome)** | Chrome을 `--remote-debugging-port`로 켜야 함. 보조 명령어로 wrap 가능 | 낮음 | localhost 디버그 포트만 사용. cert 설치 X | ✅ |
| **C. Playwright 런처** | sitree가 띄워준 Chromium 창에서 브라우징 (평소 프로필 아님) | 매우 낮음 | 격리 프로필이라 사용자 쿠키/북마크 분리 | ✅ |
| **D. HTTPS 프록시 (mitmproxy)** | 시스템 프록시 + 루트 CA 설치 | 높음 | **루트 CA 설치 필요** — 보안적으로 부담 큼 | ✅ |

### A. 브라우저 확장 — *가장 UX 좋음, MVP로는 무거움*

- content script가 `document.location` + `<a href>` 목록을 sitree 백엔드에 WS로 전송
- background script가 탭 전환·뒤로가기까지 추적
- 장점: 평소 환경에서 그대로. 인증된 영역도 자연스럽게 따라옴 (사용자 세션 그대로)
- 단점: Chrome/Firefox 각각 빌드, Web Store 배포 X면 개발자 모드 로드 안내 필요
- **구현 포인트**: `chrome.webNavigation.onCompleted` 이벤트 → URL 송신. 페이지 로드 후 `document.querySelectorAll('a[href]')`도 같이

### B. CDP — *프로토타입 우선이라면 베스트* ⭐

- 사용자가 평소 Chrome을 `--remote-debugging-port=9222`로 한 번 켬 (sitree CLI가 helper로 띄워줌)
- 백엔드가 CDP에 attach → `Page.frameNavigated`, `Network.responseReceived`, `Runtime.evaluate`로 링크 수집
- 장점:
  - 확장 빌드/배포 없음
  - 평소 Chrome 프로필(로그인 세션 포함) 그대로 사용 가능
  - 같은 코드로 Playwright 모드(C)도 지원 가능 — 두 모드가 같은 인터페이스
- 단점:
  - 디버그 포트로 켠 Chrome은 다른 디버거가 붙을 수 있음(localhost 한정이라 위험도 낮음)
  - 일반 사용자에게는 "왜 이렇게 Chrome 켜야 하나요" 진입장벽
- **구현 포인트**: `pychrome`이나 `playwright`의 `connect_over_cdp("http://localhost:9222")`로 attach. 후자가 Playwright API 그대로라 편함

### C. Playwright 런처 — *MVP 최소 노력*

- `sitree explore <url>` → Playwright Chromium이 새 창으로 열림 → 사용자가 그 창에서 탐색
- 장점: 추가 설치 0, 사용자가 별도 설정 없음. **가장 빨리 동작하는 데모**를 만들 수 있음
- 단점:
  - 사용자의 평소 프로필이 아님 → 로그인 다시 해야 함 (storage_state로 주입은 가능)
  - "내 브라우저에서 돌아다니는 느낌"이 아님 — 별도 창. UX 가치 일부 손실
  - 사용자가 그 창을 닫으면 세션 끝

### D. mitmproxy — *비추천*

- 모든 HTTPS 트래픽을 sitree가 들여다보게 됨. 강력하지만 **루트 CA 설치 = 사용자 컴퓨터의 전체 보안 모델 약화**
- 사이트 구조 매핑 목적에는 과한 권한

## 권장안

| 우선순위 | 방식 | 이유 |
|---|---|---|
| **Phase 5 MVP** | **C. Playwright 런처** | 1주 안에 데모 가능. 핵심 가설(실시간 그래프 반응이 유용한가)을 빠르게 검증 |
| **Phase 6 정식** | **B. CDP attach** | 사용자가 평소 Chrome을 그대로 쓰면서 UX 손실 최소. Playwright connect_over_cdp로 C와 코드 공유 |
| **Phase 7+ 옵션** | **A. 브라우저 확장** | 정식 배포·다중 브라우저 지원 시점에 |

## 그래프 업데이트 프로토콜 (공통)

WebSocket으로 백엔드 → 프런트 push:

```json
// 페이지 방문 이벤트
{"op": "visit", "template": "/product/{id}", "url": "https://.../product/42", "at": "2026-05-25T10:00:00Z"}

// 새 노드 발견
{"op": "add_node", "node": { ...Node }}

// 새 엣지
{"op": "add_edge", "edge": { ...Edge }}

// 현재 페이지 변경
{"op": "current", "template": "/product/{id}"}
```

프런트는 이 op를 받아 상태 머신을 업데이트. 각 노드의 상태는:

```ts
type NodeState = 'discovered' | 'visited' | 'current';
// 점선         | 실선        | 배경 강조
```

## 백그라운드 확장 크롤

사용자가 페이지 P에 방문할 때 sitree가 동시에:
- P의 모든 `<a href>` 추출 → 신규 노드를 점선(discovered)으로 추가
- 옵션으로 P에서 한 hop 깊이까지 자동 fetch (사용자 진행 방향 예측)

이건 **공손함과 충돌** 가능 — 사용자 의도와 무관하게 사이트에 부하. 기본 OFF, `--auto-expand`로 명시적 ON.

## 기술 리스크·미해결

- **SPA 라우팅**: 클라이언트 사이드 URL 변경(`history.pushState`)을 어떻게 잡을까
  - A(확장): `history.pushState` 후킹 가능
  - B/C(CDP): `Page.frameNavigated`가 hash/pushState도 일부 캡처. 누락 시 `MutationObserver` 주입
- **빠른 탐색 시 이벤트 폭주**: WS 디바운싱·배칭 필요
- **그래프 노드 1만+에서의 프런트 성능**: cytoscape는 1만 ok, 5만+면 webgl 렌더러 검토
- **세션·인증**: B 방식은 사용자 평소 세션 그대로 → 인증 영역도 자연스럽게 매핑됨 (보너스)

## 결정해야 할 것 (사용자에게)

- 어떤 캡처 방식으로 시작할지 (위 권장: C → B 순)
- "백그라운드 자동 확장" 기본값을 OFF로 둘지
- 인증 영역 매핑을 1순위로 둘지 — 보안 리뷰·내부 도구 시각화 같은 유스케이스라면 B가 강점
