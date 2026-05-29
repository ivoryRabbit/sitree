# URL Normalization & Template Inference

sitree에서 **그래프 품질을 좌우하는 가장 중요한 단계**. 잘못하면 같은 페이지가 수백 노드로 분열되거나, 다른 페이지가 한 노드로 뭉친다.

## 두 단계로 나눠 생각

1. **정규화(normalization)** — *결정적*. 같은 페이지를 같은 문자열로
2. **템플릿화(templatization)** — *통계적/휴리스틱*. 같은 "종류"의 페이지를 한 노드로

## 정규화 규칙 (결정적)

- scheme 소문자 (`HTTPS://` → `https://`)
- host 소문자, IDN punycode 정규화
- 기본 포트 제거 (`:80`, `:443`)
- 경로의 `.`·`..` 해석
- 중복 슬래시 압축 (`//` → `/`) — 단 scheme 직후는 보존
- **trailing slash**: 한 가지로 통일 (sitree 기본: path가 빈 문자열이면 `/`, 아니면 trailing slash 제거)
- **fragment(`#...`) 제거** — 같은 페이지의 앵커이지 별 페이지가 아님 (SPA 라우터는 예외 — 아래)
- 쿼리스트링: 키 알파벳 정렬, 빈 값(`?a=`) 제거 여부는 사이트별 — 기본은 보존
- percent-encoding 정규화 (RFC 3986 — unreserved 문자는 디코드)

### SPA 해시 라우팅 예외

`example.com/#/users/42` 같은 hash routing은 fragment를 살려야 페이지가 구별됨. 휴리스틱: fragment가 `/`로 시작하면 path 취급.

## 트래킹/세션 파라미터 블랙리스트

다음 키는 정규화 단계에서 **제거**한다 (기본 블랙리스트):

```
utm_source, utm_medium, utm_campaign, utm_term, utm_content,
gclid, fbclid, mc_cid, mc_eid, _ga, _gl,
ref, referrer, source,
sessionid, sid, phpsessid, jsessionid,
sort, order, view, layout  # 표현 변경만, 페이지 정체성 X
```

주의: `sort`/`view` 같은 건 사이트마다 다르다 — 옵션으로 끌 수 있게.

## 템플릿화 (통계적)

여러 URL을 보고 "같은 종류"로 묶는 단계. 두 가지 시그널:

### 1. Path 세그먼트 카디널리티

같은 부모 path 아래 자식 세그먼트가 **N개 이상**이고, 그 세그먼트가 숫자/UUID/slug 형태면 `{id}`로 치환.

```
/product/123
/product/456
/product/789  ──► /product/{id}
...
```

휴리스틱 임계: 같은 path prefix에 자식 ≥ 5개 + 형식 일치 (전부 정수, 전부 UUID, 전부 slug-case 등).

### 2. 쿼리 파라미터: 정체성 vs 변형

| 종류 | 예시 | 처리 |
|---|---|---|
| **정체성** (페이지를 바꿈) | `?id=`, `?slug=`, `?category=`, `?article=` | 값을 `*`로 치환해 템플릿에 포함 |
| **변형** (같은 페이지의 표현 변경) | `?sort=`, `?view=`, `?page=`, `?lang=` | 정규화 단계에서 제거하거나 메타로 별도 보관 |
| **트래킹** | `utm_*`, `gclid` | 제거 |

휴리스틱:
- 초기 화이트리스트(`id`, `slug`, `page`, `category`, `q`) 제공
- 카디널리티: 한 path 안에서 어떤 키의 distinct 값이 ≥ 5이고, 그 키가 빠지면 본문이 크게 다르면 → 정체성
- 본문 차이 측정은 비쌈 → MVP는 화이트리스트 + 자동 추론은 Phase 2

### 페이지네이션 다루기

`?page=1`, `?page=2`, … 는 보통 한 PLP의 변형. 템플릿 단계에서 `?page` 키는 변형 처리 → 모두 같은 노드. 단, **노드 메타에 페이지 범위는 기록**해서 "이 PLP는 페이지 20개까지 존재" 같은 정보를 잃지 않게.

## 자료구조

`url_normalize.py`에서 두 함수 export:

```python
def normalize(url: str, base: str | None = None) -> str: ...
def templatize(urls: list[str], options: TemplateOptions) -> dict[str, str]:
    """url → template 매핑."""
```

`templatize`는 배치 함수 — 카디널리티를 보려면 전체 URL을 함께 봐야 하기 때문.

## 테스트가 중요

이 모듈은 **가장 결정적인 로직**이라 단위 테스트 비중을 가장 높게. fixture는 실제 사이트 URL 리스트(books.toscrape.com, docs.python.org)를 저장해 회귀 테스트.
