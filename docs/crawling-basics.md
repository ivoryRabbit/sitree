# Crawling Basics

웹 크롤러의 기본 구조와 sitree가 채택하는 결정들.

## 크롤러의 기본 루프

```
seed URLs ──► frontier(큐) ──► fetcher ──► parser ──► link extractor
                  ▲                                          │
                  └──────────────── enqueue ◄────────────────┘
```

- **frontier**: 다음에 방문할 URL 큐. 중복 제거(seen set) 필수
- **fetcher**: HTTP 요청 실행. 재시도/타임아웃/리다이렉트 처리
- **parser**: HTML → DOM. sitree는 `selectolax` 사용 (CSS 셀렉터 빠름)
- **link extractor**: `<a href>`, `<link>`, 때로는 `<iframe src>` 추출 → 절대 URL로 변환 후 정규화 → frontier에 push

## 탐색 전략: BFS vs DFS

- **BFS (너비 우선)**: 깊이 균등하게 사이트 윤곽을 빠르게 본다. **sitree 기본값**
- **DFS (깊이 우선)**: 한 줄기를 끝까지 — 사이트 구조 분석엔 부적합 (한 카테고리에 매몰)
- **Priority queue**: 도메인별 라운드로빈, 사이트맵 우선 등으로 가중. 대형 사이트에선 필수

sitree는 단일 사이트가 주 타깃이라 단순 BFS + 동시성으로 충분.

## 제약 파라미터

| 파라미터 | 의미 | 기본값 |
|---|---|---|
| `max_depth` | seed에서 최대 깊이 | 5 |
| `max_pages` | 최대 페이지 수 | 500 |
| `concurrency` | 동시 요청 수 | 4 |
| `delay` | 요청 간 최소 지연(초) | 0.5 |
| `timeout` | 요청 타임아웃(초) | 20 |
| `same_origin_only` | 외부 도메인 따라가지 않음 | true |

## 상태 코드 다루기

- `2xx`: 정상. 본문 파싱
- `3xx`: redirect — 자동 따라가되 최종 URL 기준으로 정규화
- `4xx`: 노드로 기록하되 본문/링크 추출 스킵. `404`는 그래프상 "끊긴 링크" 표시에 유용
- `5xx`: 재시도(지수 백오프) 후 실패 시 메타에 기록
- `429`(Too Many Requests): `Retry-After` 헤더 존중. 동시성을 일시적으로 낮추기

## 동시성

- 단순 `asyncio.gather` 대신 `asyncio.Semaphore` 또는 워커 풀로 동시성 캡
- 도메인별 캡(`per-host concurrency`)은 단일 사이트 크롤이면 중요도 낮음
- httpx의 `AsyncClient` 한 인스턴스를 재사용 (연결 풀)

## 중복 제거

- 정규화된 **실제 URL** 단위로 seen set 유지 (템플릿화는 그래프 단계에서)
- 동일 URL이라도 redirect chain이 다르면 메타에 기록
- 해시 기반 content dedup은 sitree 범위 밖 (구조가 핵심이지 콘텐츠가 아님)

## 메모리 관리

- 1만 URL × HTML 평균 100KB = 1GB. **HTML은 메모리에 누적하지 않는다** — 파싱 직후 링크/메타만 남기고 버린다
- 대용량 사이트 대비: SQLite로 frontier·결과를 디스크 보관하는 옵션을 Phase 4에서 검토

## 흔한 함정

- **상대 URL 처리 누락** → `urljoin(base, href)` 항상 사용. `base`는 `<base href>`가 있으면 그쪽 우선
- **fragment(`#section`)을 별 페이지로 취급** → fragment는 정규화 시 제거
- **trailing slash 차이**(`/path` vs `/path/`)로 같은 페이지가 두 노드로 분리 → 정규화 단계에서 통일
- **무한 페이지네이션**(`?page=1..∞`) → depth/max_pages 제한 + 템플릿 단계에서 통합
- **세션 ID 쿼리**(`?sessionid=xxx`) → utm처럼 제거 대상 (`url-normalization.md` 참고)
