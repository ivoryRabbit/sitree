# WORKFLOW.md

sitree의 **작업 계획 + 진행 기록**. 각 작업을 끝낼 때마다 이 파일에 결과를 누적합니다. 비전은 [PLAN.md](PLAN.md), 모듈 구조는 [ARCHITECTURE.md](ARCHITECTURE.md), 작업 규칙은 [CLAUDE.md](CLAUDE.md).

## 사용 규칙

- 작업 시작 시: 해당 항목을 `[ ]` → `[~]`(진행 중)으로 변경
- 작업 완료 시: `[x]`로 변경, 옆에 완료 날짜와 한 줄 메모 추가
- 막혔거나 결정이 필요해진 작업: `[!]`로 표시하고 **Open Questions**에 옮김
- 큰 결정(스택/방향 전환 등)은 **Decision Log**에 한 줄로 기록
- 예상치 못한 사이드 발견·일감은 해당 Phase의 "추가 작업"으로 append (작업 누락 방지)

## Status Legend

| 마크 | 의미 |
|---|---|
| `[ ]` | 미착수 |
| `[~]` | 진행 중 |
| `[x]` | 완료 |
| `[!]` | 블록/결정 대기 |
| `[-]` | 폐기 (이유 옆에 적기) |

---

## Phase 0 — Bootstrap & Scaffolding

> 레포 구조·문서·툴체인·테스트 환경

- [x] PLAN.md 작성 (원본 비전) — 2026-05-25
- [x] CLAUDE.md / ARCHITECTURE.md / WORKFLOW.md 초안 — 2026-05-25
- [x] `docs/` 도메인 지식 7편 (crawling-basics, url-normalization, politeness, js-rendering, auth, crawl4ai-internals, live-exploration) — 2026-05-25
- [x] 폴더 구조 `backend/` + `frontend/` + `extension/` + `examples/` 분리 — 2026-05-25
- [x] `backend/`: `uv init --package` (Python 3.12) + 의존성(httpx, networkx, typer, fastapi, uvicorn, websockets, selectolax, playwright, anthropic) — 2026-05-25
- [x] `frontend/`: SvelteKit minimal (TS) init — 2026-05-25. *Node 23.6.1 engine 경고 → `--engine-strict=false`로 우회 (Node 22 LTS 또는 24 전환 검토 필요)*
- [x] `.gitignore` (시크릿/캐시/빌드 제외) + git repo 초기화 — 2026-05-25
- [x] pytest 환경 설정 (`pytest`, `pytest-asyncio`, `pytest-cov`, `ruff` dev 의존성, `[tool.pytest.ini_options]` 추가) — 2026-05-25
- [x] CLI 동작 검증 (`sitree --help` → 4 subcommands 표시) — 2026-05-25

## Phase 1 — MVP 배치 크롤 (인증/AI 없음)

> URL 한 줄 입력 → JSON 산출까지

### 1.1 코어 모듈
- [x] `schema.py`: dataclass 정의 + `to_json`/`from_json` 라운드트립 — 2026-05-25. *typing.get_type_hints로 `from __future__ import annotations` 처리*
- [x] `core/url_normalize.py`:
  - [x] `normalize()` — scheme/host lowercase, default port drop, fragment 제거, tracking key 제거, query sort — 2026-05-25
  - [x] `templatize()` — path 세그먼트 카디널리티 기반 `{id}` 치환, 식별 쿼리 키 `*` 처리 — 2026-05-25
- [x] `core/graph.py`: GraphBuilder + 노드 머지(url_samples dedupe)/엣지 count 증가/`to_site_graph()` — 2026-05-25
- [x] `core/crawler.py`:
  - [x] `extract_links()` + `fetch()` (httpx.AsyncClient 주입 가능) — 2026-05-25
  - [x] `crawl()` BFS 본구현: frontier·동시성 cap(asyncio.Semaphore)·max_depth/max_pages·delay·same_origin 필터·`allowed` predicate·`client` 주입 — 2026-05-25. *`client` 파라미터 추가는 테스트 가능성 때문 — `httpx.AsyncClient`를 patch하면 AsyncMock이 깊이 들어가 깨지므로 의존성 주입이 훨씬 깔끔*
- [x] `core/discovery.py`: robots.txt(`urllib.robotparser`로 파싱) + sitemap.xml(sitemap-index 재귀, max_depth=2) + seed 페이지 링크 추출 → `DiscoveryResult` — 2026-05-25
- [x] CLI `crawl` 명령 wire-up: `pipeline.run_crawl_sync` → 실제 JSON 출력. discovery → BFS → 템플릿화 → GraphBuilder → `to_json()` 흐름 — 2026-05-25

### 1.2 프런트엔드
- [x] `frontend/src/lib/types.ts`: `schema.py`의 TS 미러 (Node/Edge/SiteGraph + LiveOp 유니온) — 2026-05-25
- [x] `frontend/src/lib/graph/cytoscape.ts`: cytoscape.js 어댑터. 라벨별 색상, 상태별 border(dashed/solid), `current` 노드 강조 스타일 — 2026-05-25
- [x] `frontend/src/routes/+page.svelte`: JSON 정적 로드(`$lib/example.json`) + breadthfirst 트리 + 노드 클릭 시 메타 패널 — 2026-05-25. *Svelte 5 runes 모드라 `$state` 필수*
- [x] `frontend/src/lib/example.json`: 데모 데이터 (6 nodes / 6 edges, 모든 PageType 포함) — 2026-05-25
- [x] 빌드 검증: `npm run build` → 정적 산출물 OK, `svelte-check` 0 errors — 2026-05-25
- [x] CLI `sitree view <json>` — FastAPI가 프런트 정적 빌드 서빙 — 2026-05-29. *`server.create_app(graph)`: `/api/graph`(JSON) + `StaticFiles(html=True)` 마운트(API 라우트를 먼저 등록해 `/api/*` 우선). `serve()`가 uvicorn 실행 + `threading.Timer`로 브라우저 오픈. 스모크: 6노드 example.json → `/api/graph`·`/`·`_app/*.js` 모두 200*
- [x] `@sveltejs/adapter-static` 전환 — 2026-05-29. *SPA 모드(`+layout.ts`에 `ssr=false`, adapter `fallback: 'index.html'`). `+page.svelte`가 onMount에서 `/api/graph` fetch, 실패 시 번들 example.json 폴백 → 단일 빌드가 `npm run dev` 독립 실행과 `sitree view` 서빙 양쪽에서 동작. async onMount는 cleanup 반환이 무시되므로 `onDestroy`로 `cy.destroy()` 분리*
- [x] `sitree view` 스모크용 샘플로 `examples/example.json` 사용 — 2026-05-29. *단, `examples/*.json`은 .gitignore 정책(생성 산출물)이라 커밋 안 함. 데모 픽스처의 정본은 `frontend/src/lib/example.json`*

### 1.3 테스트
- [x] `tests/conftest.py` 공유 fixture — 2026-05-25
- [x] `test_url_normalize.py` (21건) — 2026-05-25
- [x] `test_schema.py` (4건, JSON 라운드트립) — 2026-05-25
- [x] `test_graph.py` (4건, 머지·count) — 2026-05-25
- [x] `test_crawler.py` (5건, httpx.MockTransport) — 2026-05-25
- [x] `test_cli.py` (7건, typer CliRunner) — 2026-05-25
- [x] **41 passed / 83% coverage** — 2026-05-25
- [x] `test_discovery.py` (6건): robots.txt 파싱(crawl-delay, sitemap, can_fetch), sitemap.xml + sitemap-index 재귀, discover() 통합 — 2026-05-25
- [x] `test_crawler.py` BFS 통합 (6건 추가): BFS 전체 도달, max_pages/max_depth 제한, same-origin 필터, allowed predicate, depth/referrer 할당 — 2026-05-25
- [x] `test_cli.py` 리팩토: `monkeypatch`로 `run_crawl_sync` stub → 네트워크 호출 0건 유지 — 2026-05-25. *진짜 example.com 때리던 회귀 차단*
- [x] **최종 53 passed / 82% coverage** — 2026-05-25

### 1.4 위생/정합 패스 (2026-05-29)
- [x] `schema.py`: LiveOp 실체 추가 (`VisitOp`/`AddNodeOp`/`AddEdgeOp`/`CurrentOp` + `type LiveOp`) — 2026-05-29. *ARCHITECTURE.md·types.ts는 LiveOp가 schema에 있다고 적었으나 실제론 `LiveOpKind` 리터럴만 있어 단일 소스 원칙이 깨져 있었음. `op` 디스크리미네이터로 TS 유니온과 1:1 매칭*
- [x] CLI `view`/`live`/`report` 미구현 명령 → stderr 경고 + `exit 1` (`_not_implemented` 헬퍼) — 2026-05-29. *기존엔 echo 후 exit 0이라 자동화가 no-op을 성공으로 오인. 테스트도 exit 1 기대로 갱신*
- [x] `pipeline.run_crawl`: robots crawl-delay 반영 시 `dataclasses.replace`로 복사 후 수정 — 2026-05-29. *전달받은 `config.delay`를 그 자리에서 변형해 호출자 객체에 부작용 있던 것 제거*
- [x] `.gitignore`에 `.coverage`/`.pytest_cache/` 추가, `pyproject` description 기본값 교체 — 2026-05-29
- [x] **54 passed / ruff clean** — 2026-05-29
- [x] `extract_links`가 anchor text·DOM 위치(nav/main/footer) 수집 → Edge 메타 채움 — 2026-05-30. *`extract_links` 반환을 `list[Link]`(url+anchor_text+position)로. `_link_position`이 가장 가까운 레이아웃 조상(nav/header→nav, footer→footer, main/article→main, else other) 판정. frontier `_Pending`이 메타를 날라 `FetchResult`에 incoming-link 메타 부착 → `_build_graph`가 엣지 `anchor_texts`/`position` 채움. **디스커버리도 시드 페이지 링크를 anchorless로 먼저 큐잉해 시드→자식(nav) 엣지가 비던 문제**를 발견 → `DiscoveryResult.initial_urls`를 `list[Link]`로 바꾸고, sitemap·seed 중복 시 앵커 있는 seed 링크로 업그레이드. 스모크: docs.python.org 46/46 엣지에 앵커, nav 21·other 25*
- [ ] 프런트엔드 테스트 부재 (`npm test`가 CLAUDE.md에 있으나 vitest 미설정) — **P2**

### 1.5 실사이트 스모크 (2026-05-30)
- [x] `sitree crawl https://docs.python.org --max-pages 50` → `sitree view`까지 풀 파이프라인 — 2026-05-30. *47노드/46엣지, 10초, robots 존중. view가 실데이터 서빙 확인(`/api/graph` 47노드, `/` 200)*
- [x] **버그 수정 ①: 시드 리다이렉트 → 유령 루트 노드.** `https://docs.python.org/`가 302→`/3/`. 디스커버리는 sitemap/seed-link의 referrer를 리다이렉트 *이전* 시드로 다는데 크롤 결과 URL엔 그게 없어 템플릿 조회 실패 → raw URL 폴백으로 samples 0개짜리 유령 루트 생성. `pipeline._build_graph`에서 `seed_norm`을 루트 결과 템플릿으로 별칭 처리 (`pipeline.py:40` 부근). 회귀 테스트 `test_pipeline.py`
- [x] **버그 수정 ②: 머지 시 depth 덮어쓰기.** 같은 템플릿이 depth 0(시드 리다이렉트 타깃)과 depth 1(디스커버리)로 두 번 크롤되면 `add_node`가 depth를 마지막 값으로 덮어써 depth-0 루트가 사라짐. depth는 시드 최단거리이므로 머지 시 `min` 유지로 변경 (`graph.py` add_node). 회귀 테스트 `test_graph.py::test_merging_node_keeps_minimum_depth`
- [x] **61 passed / ruff clean** — 2026-05-30
- [x] 버전 디렉터리 `/3.10`·`/3.11`을 `/{id}`로 그룹화 — 2026-05-30. *`_VERSION = ^v?\d+(\.\d+)+$`를 `_looks_like_id`에 추가. 파일명(`3.14.html`)은 `.html` 때문에 매칭 안 돼 올바르게 유지. docs.python.org: 노드 47→24, LLM행 모호 템플릿 46→23(절반). 테스트 3건(`test_url_normalize.py`)*

## Phase 2 — AI 라벨링

- [x] `core/classifier.py`: URL 패턴 휴리스틱 → 모호 그룹만 Claude 호출 (그룹당 1회) — 2026-05-30. *`heuristic_label()`(Home/Auth/Search/PDP/Article/PLP 정규식, 순서 중요) → `classify_groups()`가 휴리스틱·캐시 미스만 `Labeler`로. `Labeler = Callable[[GroupInput], Awaitable[PageType]]` 주입 가능 → 테스트는 fake로 네트워크 0건. `AnthropicLabeler`는 지연 생성(classify OFF면 API 키 불필요)*
- [x] Prompt caching 적용 (system = `prompts/page_classify.md`) — 2026-05-30. *system을 `cache_control: ephemeral` 블록으로 전송. 그룹마다 호출해도 system 재사용. 테스트가 요청 shape 검증*
- [x] LLM 결과 디스크 캐시 (`--cache` 디렉터리) — 2026-05-30. *`LabelCache` → `cache_dir/labels.json`. 휴리스틱 결과는 캐시 안 함(결정적). 무효 라벨은 무시. hit 시 LLM 스킵을 테스트로 검증*
- [x] 프런트: 라벨별 색상·범례 패널 — 2026-05-30. *`LABEL_COLORS` export, `+page.svelte` 헤더에 그래프에 실재하는 라벨만 카운트와 함께 `$derived`로 범례 렌더*
- [x] 테스트: LLM mock(fake Labeler + fake Anthropic client) + 캐시 hit/miss + 그룹당 1회 검증 — 2026-05-30. *`test_classifier.py`(휴리스틱/파싱/캐시/호출횟수/prompt-caching shape), `test_pipeline.py`(classify ON→라벨 적용·title 전달, OFF→None 유지). 92 passed*
- [x] CLI `crawl --classify/--no-classify`, `--model`, `--cache` wire-up (기본 OFF로 오프라인 크롤 유지) — 2026-05-30
- [x] (해결) docs.python.org 모호 템플릿 46→23: **P3 버전 템플릿화로 LLM 호출 수 절반 절감** — 2026-05-30. 버전 디렉터리가 `/{id}`로 묶이면서 그룹 수 자체가 감소

## Phase 3 — JS 렌더링 / 인증

- [ ] Playwright 자동 폴백 (JS 셸 감지 휴리스틱)
- [ ] `--cookies`, `--storage-state` 옵션
- [ ] `--auth-zone-only` (익명 vs 인증 diff 리포트)
- [ ] `auth.py` 구현 + 단위 테스트

## Phase 4 — Polish

- [ ] `--respect-robots/--ignore-robots`
- [ ] 동시성·rate-limit·delay 옵션
- [ ] 통계 패널 (총 URL/템플릿/깊이/외부 링크)
- [ ] `sitree report <json>` 단일 HTML 리포트

## Phase 5 — Live Exploration MVP (Playwright 런처)

> [docs/live-exploration.md](docs/live-exploration.md) 참고

- [ ] `server.py`: FastAPI + WS 엔드포인트 (`GET /api/graph`, `WS /api/live`)
- [ ] `live/playwright_bridge.py`: Chromium 런처 + 네비게이션 이벤트 수집
- [ ] `sitree live <url>` 동작: 브라우저 띄우고 대시보드 URL 출력
- [ ] `VisitEvent` → 그래프 증분 업데이트 → WS push
- [ ] 프런트 `/live`: WS 구독, 노드 상태(`discovered`/`visited`/`current`) 시각화
- [ ] SPA `history.pushState` 감지

## Phase 6 — Live: CDP attach

- [ ] `live/cdp_bridge.py` (`playwright.connect_over_cdp`)
- [ ] `sitree live --capture cdp` 옵션
- [ ] 사용자 Chrome을 디버그 포트로 켜는 helper/wrapper + 가이드 문서

## Phase 7+ — 브라우저 확장

- [ ] `extension/`: Chrome/Firefox 빌드
- [ ] `live/extension_bridge.py` (WS 수신)
- [ ] 정식 배포 준비

---

## Decision Log

> 새 결정은 위에서부터 쌓기. 형식: `YYYY-MM-DD — 결정 — 이유`

- 2026-05-30 — **버전 세그먼트(`3.10`, `v2.1.3`)도 `{id}`로 템플릿화.** 버전-루트 docs 트리를 한 노드로 묶어 그래프 정돈 + 분류 LLM 호출 수 직접 절감. 파일명(`x.html`)은 매칭 안 되게 순수 점-숫자 패턴만
- 2026-05-30 — **디스커버리 `initial_urls`를 `list[str]`→`list[Link]`로.** 시드 페이지 링크의 anchor/position을 frontier까지 보존해야 시드→자식 엣지(주로 nav) 메타가 채워짐. sitemap(앵커 없음)과 seed 링크 중복 시 앵커 있는 쪽으로 업그레이드
- 2026-05-30 — **분류 LLM은 `Labeler` 콜러블로 추상화 + 지연 생성.** 휴리스틱으로 못 가르는 그룹만 호출, 그룹당 1회(CLAUDE 규칙). 주입 가능해 테스트는 네트워크 0건, `crawl --classify` OFF면 anthropic 클라이언트/키 불필요
- 2026-05-30 — **노드 머지 시 depth는 `min` 유지.** depth = 시드로부터 최단거리 의미. 시드 리다이렉트 타깃이 더 깊은 페이지에서도 링크될 때 덮어쓰기로 루트 깊이가 망가지던 것 수정
- 2026-05-29 — **프런트는 SPA(adapter-static fallback) + 런타임 `/api/graph` fetch.** 빌드 1개로 정적 데모(example 번들)와 `sitree view` 서빙을 모두 커버. 데이터를 빌드에 임베드하지 않아 임의 JSON을 띄울 수 있음
- 2026-05-29 — **미구현 CLI 명령은 exit 1 + stderr 경고.** echo 후 exit 0이면 스크립트/자동화가 no-op을 성공으로 오인. Phase 게이트는 종료 코드로 명시
- 2026-05-29 — **LiveOp를 schema.py의 단일 소스로 승격.** 라이브 op이 types.ts에만 있어 Phase 5에서 드리프트 위험. 지금 dataclass로 고정
- 2026-05-25 — **`crawl()`·`run_crawl()`이 `httpx.AsyncClient`를 주입받도록.** `unittest.mock.patch`로 `httpx.AsyncClient`를 패치하면 AsyncMock이 컨텍스트 매니저 안쪽까지 들어가 깨짐. 의존성 주입이 테스트에서도 본 코드에서도 더 명확
- 2026-05-25 — **`pipeline.py`로 discovery→crawl→graph 글루 분리.** CLI는 wire-up만 담당, 도메인 흐름은 별도 모듈
- 2026-05-25 — PROJECT.md를 **WORKFLOW.md로 개명**. 작업 단위 체크리스트 + 진행 기록 누적 용도로 재정의
- 2026-05-25 — 라이브 모드 캡처 방식: **Phase 5는 Playwright 런처(C)부터 시작.** CDP(B)는 Phase 6에서 같은 Bridge 인터페이스 위에 추가. mitmproxy(D)는 채택 안 함 (보안 부담)
- 2026-05-25 — 라이브 모드 백그라운드 자동 확장: **기본 OFF.** `--auto-expand`로 명시적 ON. 공손함 우선
- 2026-05-25 — 폴더 구조 **`backend/` + `frontend/`로 분리.** 루트에서 둘 다 다루는 스크립트는 만들지 않음
- 2026-05-25 — **CLI 1급 인터페이스 원칙.** URL은 항상 첫 위치 인자, 모든 기능은 CLI에서 먼저 동작
- 2026-05-25 — 시각화: Pyvis → **Svelte + cytoscape.js.** PLAN.md는 원본 비전 보존, 실제 구현은 Svelte
- 2026-05-25 — 그래프 라이브러리: **cytoscape.js 우세** (트리 레이아웃 강점). 5만+ 노드에서 한계 도달 시 sigma.js/WebGL 검토
- 2026-05-25 — 테스트 전략: 단위 + httpx.MockTransport. 실제 네트워크 호출은 테스트에서 0건

## Open Questions

> 결정되면 Decision Log로 옮기기

- **Node 버전**: 23.6.1은 SvelteKit 의존성과 비호환. Node 22 LTS 또는 24로 전환할지
- **인증 영역 우선 유스케이스**: 보안 리뷰·내부 도구 매핑을 1순위로 둘지 (둔다면 Phase 6 CDP attach가 강점)
- **URL 템플릿 자동 추론 전환 시점**: 현재 화이트리스트 + 카디널리티. 본문 차이 기반 추론은 비용 — 언제 도입할지
- **프런트 그래프 한계**: cytoscape 5만+ 노드 도달 시 sigma.js 전환 기준
- **`uv run sitree` vs venv activate**: 권장 워크플로 확정 필요 (CLAUDE.md "자주 쓰는 명령어" 갱신)
- **프런트 빌드 → 백엔드 wheel 번들링**: 현재 `find_frontend_build()`가 dev 트리(`../frontend/build`)를 찾음. 배포 시 빌드를 `sitree/static/`으로 복사하는 hatchling 빌드 훅 필요 (server.py는 이미 그 경로를 1순위로 탐색)

## 다음 단계 후보

> 사용자와 합의 후 다음 작업을 픽업

1. `sitree view <json>` 구현 — FastAPI + `adapter-static` 정적 서빙
2. 첫 git 커밋
3. 실제 사이트 스모크 테스트 (`sitree crawl https://docs.python.org --max-pages 50 -o ../examples/python-docs.json`)
4. Phase 2 진입: `classifier.py` URL 패턴 휴리스틱 → Claude API
5. (옵션) `simplify` 스킬로 변경 코드 리팩토
