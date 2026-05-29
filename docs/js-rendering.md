# JavaScript Rendering

정적 `GET`만으로는 본문이 비어 있는 페이지(SPA, 클라이언트 렌더링)를 다루는 방법.

## 언제 폴백할까

`httpx`로 받은 HTML이 "JS 셸"인지 판단하는 신호:

- 본문 텍스트 토큰 수 < 임계(예: 50 단어)
- `<a href>` 개수 < 임계(예: 3)
- 그러나 `<script>` 태그가 다수 + `id="root"`, `id="app"` 같은 마운트 노드 존재
- `text/html` Content-Type인데 본문 90%가 `<script>` 안

위 조건이 일정 비율 이상 충족되면 같은 URL을 Playwright로 재방문.

## Playwright 기본 사용

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    ctx = await browser.new_context(storage_state="state.json")  # 인증 시
    page = await ctx.new_page()
    await page.goto(url, wait_until="networkidle", timeout=20_000)
    html = await page.content()
    links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
```

### `wait_until` 옵션

| 값 | 의미 | 적합 |
|---|---|---|
| `load` | `load` 이벤트 | 정적 사이트 |
| `domcontentloaded` | DOM 트리 완성 | 빠르지만 비동기 데이터 누락 |
| `networkidle` | 네트워크 500ms 조용 | SPA 기본값. 단 SSE/롱폴링 사이트에선 타임아웃 |
| `commit` | 응답 헤더만 | 거의 안 씀 |

sitree는 `networkidle` 기본. 위험한 사이트엔 timeout 짧게.

## 무한 스크롤·지연 로딩

- 자동 스크롤: `page.evaluate("window.scrollTo(0, document.body.scrollHeight)")` 반복
- 단 sitree의 목표는 "페이지 간 링크 구조"이지 "모든 리스트 항목 추출"이 아님 — 무한 스크롤은 깊이 추구할 가치 낮음. 기본 OFF

## 리소스 차단

이미지·폰트·미디어 요청은 차단해서 속도/대역폭 절약:

```python
await page.route("**/*", lambda r: r.abort() if r.request.resource_type in {"image", "font", "media"} else r.continue_())
```

## 단점·주의

- Playwright는 정적 fetch 대비 **10–50배 느림**. 폴백은 신중하게
- 메모리 사용량이 큼 — 브라우저 컨텍스트 재사용 (페이지마다 새 컨텍스트 X)
- 일부 사이트는 headless 감지 → `playwright-stealth` 같은 우회는 sitree 범위 밖

## sitree의 단계적 적용

- Phase 1: Playwright 미사용. 정적 HTML만
- Phase 3: 자동 폴백 + `--render=always|auto|never` 옵션
