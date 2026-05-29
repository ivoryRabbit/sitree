# ARCHITECTURE.md

sitree의 모듈 구조와 데이터 흐름. 제품 비전은 [PLAN.md](PLAN.md), 진행 상황은 [WORKFLOW.md](WORKFLOW.md), 라이브 모드 설계는 [docs/live-exploration.md](docs/live-exploration.md).

## Top-level Layout

작업 영역을 명확히 분리:

```
sitree/
├── backend/                    # 파이썬 — 크롤·그래프·서버·CLI
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/sitree/
│   │   ├── __init__.py
│   │   ├── cli.py              # ⭐ typer entry point (sitree …)
│   │   ├── server.py           # FastAPI + WebSocket (live 모드)
│   │   ├── schema.py           # 그래프 JSON 스키마 (단일 소스)
│   │   ├── core/
│   │   │   ├── discovery.py
│   │   │   ├── crawler.py
│   │   │   ├── url_normalize.py
│   │   │   ├── graph.py
│   │   │   ├── classifier.py
│   │   │   └── auth.py
│   │   ├── live/               # 라이브 탐색 모드 (Phase 5+)
│   │   │   ├── bridge.py       # CaptureBridge 인터페이스
│   │   │   ├── playwright_bridge.py   # 방식 C
│   │   │   ├── cdp_bridge.py          # 방식 B
│   │   │   └── extension_bridge.py    # 방식 A (Phase 7+)
│   │   ├── report.py           # 정적 HTML 리포트 (옵션)
│   │   └── prompts/
│   │       └── page_classify.md
│   └── tests/
│
├── frontend/                   # SvelteKit — 시각화·대시보드
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   └── src/
│       ├── routes/
│       │   ├── +page.svelte           # 정적 리포트 뷰
│       │   └── live/+page.svelte      # 라이브 대시보드
│       └── lib/
│           ├── types.ts        # backend/schema.py의 TS 미러
│           ├── graph/          # cytoscape/d3 어댑터
│           ├── ws.ts           # WebSocket 클라이언트
│           └── components/
│
├── extension/                  # Phase 7+, 비어 있을 수 있음
│
├── docs/                       # 도메인 지식
├── examples/                   # 샘플 출력 JSON
├── PLAN.md / WORKFLOW.md / ARCHITECTURE.md / CLAUDE.md
└── .gitignore
```

`backend/`와 `frontend/`는 **각자의 패키지 매니저로 독립** — 백엔드는 uv, 프런트는 npm.

## 두 가지 동작 모드

### Mode 1: 배치 크롤 (CLI 우선, Phase 1~4)

```
   $ sitree crawl <url> -o out.json
            │
            ▼
   ┌──────────────────────────────────────────────────────────┐
   │  Discovery → Crawler → Normalize → Graph → Classifier    │
   └──────────────────────────────────────────────────────────┘
            │
            ▼
   out.json (schema.SiteGraph)
            │
            ▼
   $ sitree view out.json        # frontend 정적 빌드를 띄우고 JSON 로드
```

- CLI가 **1급 인터페이스**. URL 한 줄 입력으로 끝까지 돌아가야 함
- `-o`로 JSON 출력, `--report report.html`로 단일 HTML 출력(옵션)
- 프런트엔드 빌드는 백엔드 wheel에 포함되어 `sitree view`가 로컬에서 정적 서빙

### Mode 2: 라이브 탐색 (Phase 5+)

```
   $ sitree live <url>           # 또는 --capture cdp|playwright|extension
            │
            ▼
   ┌─────────────────────────┐
   │ FastAPI + Capture       │
   │ Bridge 실행, 대시보드   │
   │ URL 출력                │
   └────────┬────────────────┘
            │
            ▼
   [브라우저] ◄──CDP/WS──► [Bridge]
        │                     │
        │ (사용자 탐색)       │ (이벤트)
        │                     ▼
        │           Graph (incremental)
        │                     │
        │                     │ WS push
        ▼                     ▼
   [Svelte 대시보드: 실시간 트리]
```

- 사용자는 두 가지를 띄움: (1) 자기 브라우저(또는 sitree가 띄운 Chromium), (2) sitree 대시보드 탭
- 페이지 방문 이벤트 → 백엔드 그래프 업데이트 → WS로 프런트 push
- 노드 상태: `discovered`(점선) / `visited`(실선) / `current`(배경 강조)

캡처 방식 선택 근거는 [docs/live-exploration.md](docs/live-exploration.md).

## 핵심 모듈 책임

### `backend/src/sitree/cli.py`

`typer` 기반 진입점. 명령어:

```
sitree crawl <url>              # 배치 크롤 → JSON
sitree view <path.json>         # 정적 대시보드 서빙
sitree live <url>               # 라이브 모드 시작
sitree report <path.json> -o html
```

옵션(공통): `--max-depth`, `--max-pages`, `--concurrency`, `--cookies`, `--storage-state`, `--respect-robots/--ignore-robots`, `--cache <dir>`.

### `core/discovery.py`
sitemap.xml + robots.txt + seed → 초기 URL 큐.

### `core/crawler.py`
async 큐 기반. httpx 우선, JS 셸 감지 시 Playwright 폴백.

### `core/url_normalize.py`
정규화 + 템플릿 추론. [docs/url-normalization.md](docs/url-normalization.md).

### `core/graph.py`
`networkx.DiGraph` 래퍼. `to_json()` → `schema.SiteGraph`.

### `core/classifier.py`
URL 패턴 휴리스틱 + 모호 그룹만 Claude API (그룹당 1회).

### `core/auth.py`
쿠키/storage_state 주입만. [docs/auth-strategies.md](docs/auth-strategies.md).

### `live/bridge.py` (Phase 5+)
```python
class CaptureBridge(Protocol):
    async def start(self, seed_url: str) -> None: ...
    async def events(self) -> AsyncIterator[VisitEvent]: ...
    async def stop(self) -> None: ...
```

- `PlaywrightBridge`: sitree가 Chromium 런처. UX 단순
- `CdpBridge`: `playwright.connect_over_cdp("http://localhost:9222")`로 기존 Chrome attach. 사용자 평소 프로필 사용
- `ExtensionBridge`: 확장에서 WS로 들어오는 이벤트 수신

세 구현 모두 같은 `VisitEvent` 스트림을 내보내므로 그래프 업데이트 로직은 단일.

### `server.py`
FastAPI. 라우트:
- `GET /` — Svelte 빌드 정적 서빙
- `GET /api/graph` — 현재 그래프 스냅샷
- `WS /api/live` — 실시간 op 스트림

### `frontend/` (SvelteKit)
- 정적 뷰: `/` → `?data=out.json` 또는 빌드 시 임베드
- 라이브 뷰: `/live` → `ws://localhost:8765/api/live` 구독
- 그래프 엔진: **cytoscape.js** (계층/트리 레이아웃 강함). 5만+ 노드면 sigma.js로 전환 검토

## 데이터 흐름 (JSON 스키마)

`backend/src/sitree/schema.py`가 단일 소스:

```python
@dataclass
class Node:
    template: str                      # 예: "/product/{id}"
    label: PageType | None             # Home/Search/PDP/PLP/Article/Auth/Other
    url_samples: list[str]
    depth: int
    status_codes: list[int]
    state: NodeState = "discovered"    # live 모드에서만 의미
    visit_count: int = 0
    last_visited_at: datetime | None = None

@dataclass
class Edge:
    source: str                        # template
    target: str
    anchor_texts: list[str]
    count: int
    position: Literal["nav", "main", "footer", "other"]

@dataclass
class SiteGraph:
    root: str
    nodes: list[Node]
    edges: list[Edge]
    meta: CrawlMeta

# 라이브 전용 op
LiveOp = VisitOp | AddNodeOp | AddEdgeOp | CurrentOp
```

`frontend/src/lib/types.ts`가 이 정의를 그대로 미러링. 두 파일이 어긋나지 않도록 PR 체크리스트에 포함.

## 비목표

- 인증 자동화 (OAuth/2FA/CAPTCHA 돌파)
- 분산 크롤
- 컨텐츠 추출/임베딩
- 사용자 트래픽을 가로채는 시스템 프록시 (mitmproxy 등) — 라이브 모드에서도 사용 안 함
