# Politeness & robots.txt

크롤러가 지켜야 할 매너. **법적/윤리적 이슈와 차단 회피 둘 다의 문제.**

## robots.txt

- 호스트 루트의 `/robots.txt`. 텍스트 포맷
- `User-agent: *` + `Disallow: /path` — 해당 path 이하 크롤 금지
- `Allow:` — 더 좁은 path는 예외적으로 허용 (Disallow 안에서 punching hole)
- `Crawl-delay: N` — 요청 사이 최소 N초 (구글은 무시하지만 sitree는 존중)
- `Sitemap: <url>` — sitemap 위치 힌트

파이썬: 표준 `urllib.robotparser`로 충분. 단점은 `Crawl-delay` 같은 비표준 디렉티브를 무시 — 필요하면 직접 파싱.

### sitree 기본값

- `--respect-robots` **기본 ON**. `--ignore-robots`로 해제 가능 (소유한 사이트 테스트용)
- robots에서 Disallow된 URL은 frontier에 넣지 않음 (방문 안 함)
- Disallow에 걸린 페이지는 그래프에 "disallowed" 메타로 노드만 남기는 옵션 (Phase 4)

## Rate Limiting

- **호스트당 동시성 캡** + **요청 간 지연**. 두 가지를 같이
- `429 Too Many Requests` 받으면:
  1. `Retry-After` 헤더가 있으면 그만큼 대기
  2. 없으면 지수 백오프 (1s, 2s, 4s, …)
  3. 동시성을 일시적으로 절반으로
- `503 Service Unavailable`도 비슷하게

## User-Agent

- **반드시 명시**. 비워두거나 기본 `python-httpx/x.y.z`는 매너 X
- 예: `sitree/0.1 (+https://github.com/<user>/sitree)` — 연락처/레포 링크 포함이 관례
- 대형 사이트 일부는 알려진 봇 UA 외엔 차단 — 이때는 평범한 브라우저 UA 흉내가 필요할 수 있으나, **이건 정책 위반일 수 있음**. sitree는 기본적으로 정직한 UA 사용

## ETag / If-Modified-Since

재크롤 시 변경된 페이지만 받으려면:
- 첫 크롤에서 `ETag`·`Last-Modified` 헤더 저장
- 다음 크롤에 `If-None-Match`·`If-Modified-Since`로 조건부 요청 → `304 Not Modified`면 본문 스킵

sitree Phase 4 이후 검토 (재실행 모드).

## 차단 회피 vs 윤리

크롤러 차단을 우회하는 기법(IP rotation, captcha solver, UA spoofing, 헤더 위장)은 sitree 범위 **밖**:

- 우리는 **사이트 구조를 이해**하려는 도구지, 사이트 방어를 뚫는 도구가 아님
- 인증 영역도 "사용자가 이미 가진 세션을 받는다"가 한계 — [auth-strategies.md](auth-strategies.md) 참고

## 법적 메모

- robots.txt는 법이 아니지만 **존중하는 것이 분쟁 시 방어선**이 됨
- 공개된 페이지라도 ToS에서 자동화 접근을 금지할 수 있음 — 본인 사이트나 명시적 허용이 있는 사이트만 대상으로 권장
- 개인정보·민감정보가 포함된 페이지는 노드 메타에서도 본문/제목 저장을 피할 것
