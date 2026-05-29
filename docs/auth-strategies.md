# Authentication Strategies

sitree는 **자동 로그인을 시도하지 않는다.** 사용자가 이미 가진 세션을 받아 그 자격으로 크롤할 뿐. OAuth/2FA/CAPTCHA 돌파는 범위 밖.

## 1. 쿠키 헤더 주입 (가장 단순)

브라우저 DevTools → Application → Cookies에서 복사한 문자열을 그대로:

```bash
sitree crawl https://app.example.com \
  --cookies "session=abc123; auth_token=xyz"
```

httpx에 그대로 헤더로 추가:

```python
client = httpx.AsyncClient(headers={"Cookie": cookie_str})
```

장점: 빠르고 명확.
단점: 만료 시 갱신 안 됨. HttpOnly 쿠키도 사용자가 직접 추출해야 함.

## 2. Playwright `storage_state.json` (권장)

브라우저에서 한번 로그인 한 뒤 상태 스냅샷을 JSON으로 추출:

```python
# 한 번만 실행 (수동 로그인 후)
ctx = await browser.new_context()
page = await ctx.new_page()
await page.goto("https://app.example.com/login")
input("로그인 후 Enter…")
await ctx.storage_state(path="state.json")
```

이후 크롤 시:

```bash
sitree crawl https://app.example.com --storage-state state.json
```

장점: 쿠키 + localStorage + sessionStorage 모두 보존. SPA 인증과 호환.
단점: Playwright 모드에서만 작동 → 정적 fetch 경로도 동일 쿠키를 추출해 같이 적용해야 함.

sitree의 `auth.py`는 storage_state를 읽어 (a) Playwright 컨텍스트에 넘기고 (b) 도메인 쿠키만 추출해 httpx 클라이언트에도 주입한다.

## 3. HTTP Basic Auth

`--basic user:pass` 옵션. 헤더 `Authorization: Basic <b64>` 자동 부착.

## 인증 영역 한정 크롤

`--auth-zone-only`: 익명으로 한번, 인증으로 한번 크롤한 뒤 **인증에서만 나타나는 노드/엣지**를 별도 리포트로. 보안 리뷰·내부 도구 매핑에 유용.

## 보안 고려사항

- `storage_state.json`, 쿠키 문자열은 **자격증명**과 동급. `.gitignore`에 패턴 추가 (`*.storage-state.json`, `cookies.txt`)
- sitree 자체는 이 파일들을 디스크에 새로 쓰지 않는다 (사용자가 준 경로만 읽음)
- 크롤 로그/리포트에 쿠키·토큰을 노출하지 않도록 마스킹
- 캐시 디렉터리 권한은 700 권장 (Phase 2 LLM 캐시도 마찬가지)

## 안 하는 것들

- 폼 로그인 자동화 (필드 탐지·자동 입력)
- OAuth 흐름 자동 완료
- 2FA 코드 자동 입력
- CAPTCHA 우회

이런 동작은 사이트 ToS 위반 가능성이 높고, sitree의 정직성 원칙과 어긋난다.
