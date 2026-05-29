# CLAUDE.md

이 파일은 Claude Code가 sitree 레포에서 작업할 때 참고하는 항상 로드되는 지침입니다. 다른 세션에서도 같은 컨텍스트로 작업을 이어가도록 유지합니다.

## 한 줄 요약

웹사이트의 페이지 간 링크 구조와 의미적 역할을 **트리/그래프로 시각화**하는 도구. CLI 우선, 추후 라이브 탐색 대시보드.

먼저 읽을 문서:
- [PLAN.md](PLAN.md) — 원본 비전
- [WORKFLOW.md](WORKFLOW.md) — **작업 체크리스트 + 진행 기록.** 세션 시작 시 현재 위치 파악, 작업할 때마다 갱신
- [ARCHITECTURE.md](ARCHITECTURE.md) — 모듈·데이터 흐름
- [docs/](docs/) — 도메인 지식 (특히 [live-exploration.md](docs/live-exploration.md))

## 기술 스택 (반드시 준수)

- **Python 3.12+** — 새 코드는 3.12 문법 사용 가능 (PEP 695 `type X = ...` 등)
- **uv** — 백엔드 패키지/가상환경. `pip`·`poetry` 직접 사용 금지. 의존성 추가는 `uv add`
- **SvelteKit** — 프런트. 결과는 정적 빌드(`build/`)로 떨어지고 백엔드가 서빙
- **벤치마킹**: [crawl4ai](https://github.com/unclecode/crawl4ai). 직접 의존하지 않고 디자인만 참고 — [docs/crawl4ai-internals.md](docs/crawl4ai-internals.md)
- **그래프**: NetworkX (백엔드), cytoscape.js (프런트). 직렬화는 JSON

PLAN.md의 `pyvis`는 더 이상 사용하지 않음.

## 디렉터리 — 백/프런트 분리

```
sitree/
├── backend/       # Python (uv). CLI · 크롤러 · 그래프 · 서버
│   ├── pyproject.toml
│   ├── src/sitree/
│   └── tests/
├── frontend/      # SvelteKit. 정적 뷰 + 라이브 대시보드
│   ├── package.json
│   └── src/
├── extension/     # 브라우저 확장 (Phase 7+, 비어있을 수 있음)
├── docs/          # 도메인 지식
├── examples/      # 샘플 출력 JSON
└── PLAN.md / WORKFLOW.md / ARCHITECTURE.md / CLAUDE.md
```

각 폴더에서 명령을 실행하는 게 기본 (e.g. `cd backend && uv run …`). 루트에서 둘 다 다루는 스크립트는 만들지 말 것 — 단순함 유지.

## CLI는 1급 시민

- 모든 기능은 **CLI에서 먼저 동작해야 함**. 대시보드는 그 결과의 뷰일 뿐
- 진입점: `sitree <subcommand>` (typer)
- 핵심 명령어:
  ```
  sitree crawl <url>          # 배치 크롤 → JSON
  sitree view <out.json>      # 정적 대시보드 서빙
  sitree live  <url>          # 라이브 탐색 모드 (Phase 5+)
  sitree report <out.json>    # 단일 HTML 리포트
  ```
- URL 인자는 **항상 첫 번째 위치 인자**. 옵션이 아님

## 작업 규칙

- 의존성은 `uv add` (backend) / `npm install` (frontend) — lockfile 두 개 모두 커밋
- 크롤러 외부 사이트 호출 기본값은 **공손함**: 동시성 ≤ 4, robots.txt 존중, 명시적 UA
- LLM 호출은 **URL 템플릿 그룹당 1회**. 페이지당 호출 추가 금지
- 인증 자동 돌파(OAuth/2FA/CAPTCHA) 코드 작성 금지 — 사용자가 주입한 쿠키/storage_state만 사용
- 라이브 모드의 시스템 프록시(mitmproxy) 사용 안 함 — 사용자 컴퓨터 보안 모델을 약화시킴
- 백/프런트 모두 단일 소스 스키마(`backend/src/sitree/schema.py` ↔ `frontend/src/lib/types.ts`)를 유지

## 자주 쓰는 명령어

```bash
# 백엔드 셋업
cd backend && uv sync

# 프런트 셋업
cd frontend && npm install

# 개발 (배치)
cd backend && uv run sitree crawl https://example.com -o ../examples/out.json
cd frontend && npm run dev

# 개발 (라이브, Phase 5+)
cd backend && uv run sitree live https://example.com   # 백엔드 + 캡처 브리지 + 대시보드 URL 출력

# 테스트
cd backend  && uv run pytest
cd frontend && npm test

# 프런트 빌드 (백엔드 wheel에 같이 포함)
cd frontend && npm run build
```

## 컨벤션

- 노드 식별자는 **정규화된 URL 템플릿**(`/product/{id}`). 실제 URL 샘플은 메타에
- 페이지 타입 enum (`Home/Search/PDP/PLP/Article/Auth/Other`)은 함부로 늘리지 말 것 — 확장 시 PLAN.md와 분류 프롬프트도 함께 업데이트
- 라이브 노드 상태: `discovered`(점선) / `visited`(실선) / `current`(배경 강조)
- 같은 이벤트 op 이름을 백/프런트가 공유 (`visit`, `add_node`, `add_edge`, `current`)

## 작업 진행 기록 — WORKFLOW.md 갱신은 의무

**모든 코딩 작업은 [WORKFLOW.md](WORKFLOW.md)에 기록한다.** 진행 상황·결정·새 발견 사항이 누락되면 다른 세션에서 컨텍스트가 끊긴다.

### 언제 갱신하나

| 시점 | 행동 |
|---|---|
| 세션 시작 시 | WORKFLOW.md의 Phase별 진행 상태 + Decision Log 최신 항목 확인 |
| 작업 시작 전 | 해당 체크박스를 `[ ]` → `[~]`(진행 중) |
| 작업 끝나자마자 | `[x]` + 완료 날짜(`YYYY-MM-DD`) + 한 줄 메모. 배치로 미루지 말 것 |
| 막힌 작업 | `[!]` 마크 후 **Open Questions**로 옮김 |
| 큰 결정 발생 | **Decision Log**에 한 줄 추가 (`날짜 — 결정 — 이유`) |
| 새 일감 발견 | 해당 Phase 하단에 체크박스 추가 |

### 메모 작성 규칙

- 한 줄, 무엇을 왜 했는지가 드러나게. 예: `*typing.get_type_hints로 PEP 563 처리*`
- WHAT은 코드/diff로 알 수 있으니 **WHY나 비자명한 결정 위주**로 적기
- 코드 위치 참조는 `file:line` 형태 권장
- 부정적 발견(`X 시도했는데 안 됨, 원인은 Y`)도 기록 — 미래의 자신이 같은 실험 반복 안 하게

### 절대 하지 말 것

- WORKFLOW.md를 보지 않고 작업 시작
- 여러 작업 끝낸 뒤 한꺼번에 체크 (어떤 게 언제 완료됐는지 흐려짐)
- 메모 없이 `[x]`만 체크 (결정 맥락 손실)

라이브 모드 캡처 방식 등 도메인 결정은 [docs/live-exploration.md](docs/live-exploration.md) 끝의 "결정해야 할 것" 섹션도 함께 참고.
