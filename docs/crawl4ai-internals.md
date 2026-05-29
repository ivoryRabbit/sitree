# crawl4ai — 동작 원리와 sitree가 차용할 부분

[crawl4ai](https://github.com/unclecode/crawl4ai)는 LLM 친화적 크롤링 파이프라인을 제공하는 오픈소스 라이브러리. sitree는 이 도구를 **벤치마킹 대상**으로 삼지만 직접 의존하지는 않을 가능성이 높다. 이유와 차용 포인트를 정리한다.

## crawl4ai의 핵심 구성

```
   ┌──────────────────────────────────────────────────────────┐
   │              AsyncWebCrawler (facade)                    │
   │  arun(url, config) / arun_many(urls, config)             │
   └─────────┬──────────────────────┬─────────────────────────┘
             │                      │
             ▼                      ▼
   ┌──────────────────┐   ┌───────────────────────────────┐
   │   Crawl Strategy │   │     Browser Strategy           │
   │ - BFS / DFS /    │   │ - Playwright (chromium)        │
   │   BestFirst      │   │ - 세션·쿠키·storage_state     │
   │ - filter / score │   │ - hooks: pre/post navigate     │
   └────────┬─────────┘   └────────┬──────────────────────┘
            │                      │
            ▼                      ▼
   ┌──────────────────────────────────────────────────────────┐
   │           Content Pipeline (per page)                    │
   │  raw HTML → cleaning → markdown → chunking →             │
   │  extraction(strategy: CSS / XPath / LLM / Cosine sim)   │
   └──────────────────────────────────────────────────────────┘
```

### 주요 컴포넌트

1. **AsyncWebCrawler** — 진입점. `async with` 컨텍스트에서 브라우저 라이프사이클 관리
2. **BrowserConfig** — Playwright 브라우저 옵션(헤드리스, UA, 프록시, viewport, storage_state, …)
3. **CrawlerRunConfig** — per-run 옵션(캐시 모드, 스크린샷, JS 코드 주입, wait_for 셀렉터, 추출 전략 등)
4. **Deep Crawl Strategies**:
   - `BFSDeepCrawlStrategy` — 너비 우선
   - `DFSDeepCrawlStrategy` — 깊이 우선
   - `BestFirstCrawlingStrategy` — 스코어 함수 기반 우선순위 큐
   - `FilterChain` + `URLPatternFilter`, `ContentTypeFilter`, `DomainFilter` 등으로 frontier 제한
5. **Extraction Strategies**:
   - `JsonCssExtractionStrategy` — CSS 셀렉터 → 구조화 JSON
   - `LLMExtractionStrategy` — LLM에 스키마 주고 추출
   - `CosineSimilarityStrategy` — 의미적 청킹
6. **Markdown Generator** — HTML → Markdown 변환 (LLM 입력으로 쓰기 좋게)
7. **Caching** — `CacheMode.ENABLED/BYPASS/READ_ONLY/WRITE_ONLY`. 디스크 기반(SQLite/파일)
8. **Hooks** — `on_browser_created`, `before_goto`, `after_goto`, `before_retrieve_html` 등 8단계 훅 — 자격증명 주입, 쿠키 조작, 동적 인터랙션에 활용

## 한 페이지를 처리하는 흐름

1. `arun(url)` 호출
2. 캐시 hit? → 캐시된 결과 반환 (선택된 `CacheMode`에 따라)
3. miss면 Playwright 페이지 열기 → before_goto 훅
4. `page.goto(url, wait_until=...)` → after_goto 훅
5. 필요 시 `js_code` 실행(스크롤·클릭 등), `wait_for` 셀렉터 대기
6. `page.content()`로 HTML 추출 → before_retrieve_html 훅
7. **HTML 정제** — 광고/스크립트/스타일 제거, 메인 컨텐츠 추정
8. **Markdown 변환** — LLM 친화 포맷
9. **링크 추출** — 내부/외부 분리, 메타데이터 부착
10. **Extraction strategy** 적용 → 구조화 데이터
11. `CrawlResult` 반환 (markdown, cleaned_html, links, media, extracted_content, screenshot, …)

## Deep Crawl 흐름

`AsyncWebCrawler.arun(url, config=CrawlerRunConfig(deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=2)))`

- 시작 URL 처리 → 결과의 internal links 수집
- FilterChain으로 거름
- frontier에 추가, BFS 순회
- per-page 결과를 async generator로 yield (스트리밍 모드)

## sitree가 **차용**할 것

- **async 파이프라인 + 훅 구조**: 정제·정규화 단계를 훅으로 분리하면 테스트하기 좋음
- **FilterChain 패턴**: 도메인/패턴/콘텐츠 타입 필터를 조립 가능한 체인으로
- **CacheMode**: 재실행 시 LLM 비용 절감과 직결. 디스크 캐시는 SQLite로 충분
- **결과 객체에 raw_html / links / metadata 분리**: 같은 형태로 `CrawlResult` 만들 예정
- **BFSDeepCrawlStrategy의 frontier 관리**: 동일 패턴

## sitree가 **안** 가져갈 것

- **Markdown 변환·LLM 추출**: 우리는 콘텐츠 추출이 아니라 구조 매핑. 본문은 분류기 입력으로만 짧게 사용
- **Best-first scoring**: 단일 사이트 BFS면 충분
- **CosineSimilarityStrategy**: 그래프 노드 라벨링에 임베딩까지 필요 없음 — URL 템플릿 그룹핑이 더 효과적
- **풀 Playwright 의존**: sitree는 httpx 우선, JS 필요 시에만 Playwright 폴백. crawl4ai는 항상 브라우저

## 직접 의존 vs 자체 구현 결정

| 옵션 | 장점 | 단점 |
|---|---|---|
| **crawl4ai 의존** | 빠른 부트스트랩, 검증된 정제·캐시 | 항상 브라우저, sitree에 안 쓰는 거대한 표면적, 우리 데이터 모델과의 어댑터 필요 |
| **참고만 하고 자체 구현** | sitree 모델에 딱 맞는 가벼운 코드, httpx 우선 경로 | 직접 구현 비용 |

**현재 방침: 참고만**. crawl4ai의 디자인을 인용하되 의존하지 않는다. Playwright 폴백 코드만 비슷한 모양을 갖게.

## 학습용 참고 자료

- 레포: https://github.com/unclecode/crawl4ai
- 핵심 파일들(읽어볼 만):
  - `crawl4ai/async_webcrawler.py` — 진입점
  - `crawl4ai/deep_crawling/bfs_strategy.py` — frontier 관리
  - `crawl4ai/content_filter_strategy.py` — HTML 정제 휴리스틱
  - `crawl4ai/extraction_strategy.py` — 추출 전략 패턴
- 공식 문서: https://docs.crawl4ai.com
