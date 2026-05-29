# Website Hierarchy Analyzer — Plan

## Context

웹사이트의 페이지 간 링크 관계(A → B, A is referer of B)와 각 페이지의 **의미적 역할**(Home / Search / Product / Article 등)을 자동으로 파악해 정적 HTML 리포트로 시각화하는 CLI 도구.

**해결하려는 문제**
- 기존 SEO 크롤러(Screaming Frog, Sitebulb)는 강력하지만 GUI 중심·유료·SEO 관점이 강함
- Diffbot은 페이지 타입 분류는 잘 하지만 black-box 유료 API, 그래프 시각화는 별도
- AI 크롤러(Firecrawl, Crawl4AI, ScrapeGraphAI)는 "추출"에 초점, 사이트 **구조 자체의 의미적 지도화**는 빈자리

**의도된 결과물**
- URL 한 줄 입력 → 정적 HTML 리포트 (인터랙티브 그래프 + 페이지 타입 요약 + URL 템플릿 그룹)
- 인증 영역은 표준 패턴(쿠키/`storage_state` 주입)으로 *옵션* 지원, 자동 돌파는 시도하지 않음

---

## 기존 도구 레퍼런스 (구현 시 참고)

| 도구 | 참고 포인트 |
|---|---|
| Screaming Frog | 폼 로그인/쿠키 주입 UX, URL segmentation |
| Sitebulb | Crawl Map 시각화 인터랙션 |
| Diffbot Analyze API | 페이지 타입 카테고리 분류 체계 (article/product/list/discussion/...) |
| Crawl4AI / Firecrawl | Playwright 기반 LLM-친화 크롤 파이프라인 |
| Botify | URL 패턴 segmentation (PLP/PDP 자동 그룹) |

학술 키워드: *URL template mining*, *web page genre classification*, *sitemap inference*.

---

## 아키텍처

```
┌─────────────┐    ┌──────────────┐    ┌────────────────┐    ┌──────────────┐
│  Discovery  │ →  │   Crawler    │ →  │   Classifier   │ →  │   Reporter   │
│ sitemap.xml │    │ httpx +      │    │ URL template + │    │ NetworkX →   │
│ robots.txt  │    │ Playwright   │    │ LLM labeling   │    │ Pyvis HTML   │
└─────────────┘    └──────────────┘    └────────────────┘    └──────────────┘
```

**핵심 모듈**

- `discovery/` — `sitemap.xml`, `robots.txt`, seed URL에서 초기 URL 풀 구성
- `crawler/` — httpx (정적) + Playwright (JS 필요 시 자동 폴백). 동시성 제한, robots.txt 존중, rate limit
- `graph/` — NetworkX DiGraph. 노드: URL (정규화), 엣지: A→B(앵커 텍스트, 위치 메타). URL은 쿼리파라미터 템플릿화하여 노드 통합 (`/product?id=*`)
- `classifier/` — 2단계: (1) URL 패턴 마이닝으로 그룹핑 → (2) 그룹 대표 페이지를 Claude API로 라벨링 (페이지당 1회가 아니라 **그룹당 1회**로 비용 절감)
- `auth/` — 옵션. 쿠키 문자열, `storage_state.json`, HTTP Basic Auth 주입
- `report/` — Pyvis 인터랙티브 그래프 + Jinja2 템플릿 요약 페이지 → 단일 HTML 파일
- `cli/` — Typer 기반

---

## 기술 스택

- **Python 3.11+**
- 크롤: `httpx` + `playwright` (JS 페이지 자동 감지 후 폴백)
- 파싱: `selectolax` (lxml보다 빠름) 또는 `beautifulsoup4`
- 그래프: `networkx`
- 시각화: `pyvis` (D3 기반 인터랙티브 HTML, 단일 파일 출력)
- AI: `anthropic` SDK, 모델은 `claude-sonnet-4-6` (비용/품질 균형). Prompt caching 적극 활용 — 시스템 프롬프트(분류 스키마)는 cache breakpoint
- CLI: `typer`
- 패키징: `uv` (빠르고 lockfile)

---

## 파일 구조 (신규 레포)

```
site-hierarchy/
├── pyproject.toml
├── README.md
├── src/site_hierarchy/
│   ├── __init__.py
│   ├── cli.py              # typer entry point
│   ├── discovery.py        # sitemap/robots parsing
│   ├── crawler.py          # httpx + playwright fallback
│   ├── url_normalize.py    # 쿼리파라미터 템플릿화
│   ├── graph.py            # NetworkX wrapper
│   ├── classifier.py       # URL pattern + Claude labeling
│   ├── auth.py             # cookie/storage_state injection
│   ├── report/
│   │   ├── renderer.py     # pyvis + jinja2
│   │   └── template.html.j2
│   └── prompts/
│       └── page_classify.md
└── tests/
    └── ...
```

---

## 구현 단계

**Phase 1 — MVP (인증/AI 없이)**
1. CLI 스켈레톤 (`site-hierarchy crawl <url> -o report.html`)
2. sitemap.xml + robots.txt 파싱
3. httpx 기반 동시 크롤 (depth/페이지수 제한)
4. URL 정규화 + 쿼리파라미터 템플릿 추론 (동일 path에 다양한 쿼리값 → `?id=*`)
5. NetworkX 그래프 구성
6. Pyvis 단일 HTML 출력 — 노드는 URL 템플릿 단위, 호버 시 실제 URL 샘플

**Phase 2 — AI 라벨링**
7. URL 템플릿 그룹별 대표 페이지 1~3개의 텍스트/메타를 Claude에 전달 → 페이지 타입 라벨 (Home/Search/PDP/PLP/Article/Auth/Other 등 정해진 enum)
8. 라벨을 노드 색상/범례에 반영. 그룹당 1회 호출로 비용 최소화, prompt caching으로 시스템 프롬프트 재사용
9. 라벨 JSON 결과를 `--cache` 디렉터리에 저장 → 재실행 시 LLM 호출 스킵

**Phase 3 — JS / 인증**
10. 정적 fetch 결과가 빈약하면 Playwright로 자동 폴백
11. `--cookies "k=v; k2=v2"` 또는 `--storage-state path.json` 옵션
12. `--auth-zone-only` 옵션 — 인증된 영역만 별도 리포트

**Phase 4 — Polish**
13. robots.txt 존중, `--respect-robots/--ignore-robots`
14. 동시성/지연 옵션
15. 리포트에 통계 패널 (총 URL, 템플릿 수, 깊이 분포, 외부 링크)

MVP만으로도 의미 있는 결과물. Phase 2부터가 차별화 포인트.

---

## 핵심 구현 노트

- **URL 정규화**가 도구 품질을 좌우. 쿼리파라미터 중 어떤 게 "페이지 정체성"이고(예: `?id=`) 어떤 게 "변형"(예: `?utm_source=`, `?sort=`)인지 휴리스틱 필요. 초기엔 화이트리스트(id, slug, page, category) + 값 카디널리티 기반 자동 추론
- **그룹당 1회 LLM 호출** 원칙을 깨지 말 것. 1만 URL 사이트도 그룹은 보통 수십 개
- **Pyvis 출력은 단일 HTML 파일**이어야 함 (공유 편의). `notebook=False, cdn_resources='remote'`
- **인증을 자동화하지 않는다** — 사용자가 이미 가진 세션을 받는 것만 함. OAuth/2FA/CAPTCHA 우회 시도 금지

---

## 검증

1. **공개 사이트 스모크 테스트** — `site-hierarchy crawl https://docs.python.org -o out.html --max-pages 200` → 브라우저로 열어 그래프·라벨 확인
2. **이커머스 (PDP/PLP 분류 기대)** — 공개 데모 쇼핑몰(e.g., books.toscrape.com)에서 PDP 그룹·PLP 그룹이 다른 라벨/색상으로 분리되는지 확인
3. **인증 영역** — 사용자 본인 GitHub 같은 곳에 `storage_state.json` 추출해서 `--storage-state`로 주입 → 익명 크롤과 비교해 추가 노드(설정/대시보드 등) 등장 확인
4. **재현성** — 두 번째 실행에서 LLM 호출이 캐시되는지 (`--cache`)
5. **단위 테스트** — URL 정규화·템플릿 추론 (가장 결정적인 로직), sitemap 파싱

---

## 향후 확장 (out of scope, 메모용)

- 브라우저 확장(HAR import) 모드 — 사용자가 평소 브라우징한 흔적을 그래프로
- 페이지 변경 diff (시점 A vs B)
- 사이트맵 자동 생성 (역방향)
