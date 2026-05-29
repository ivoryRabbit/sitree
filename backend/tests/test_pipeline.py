"""Pipeline graph-assembly tests (no network)."""

from __future__ import annotations

import httpx

from sitree.core.auth import AuthConfig
from sitree.core.classifier import GroupInput
from sitree.core.crawler import CrawlConfig, FetchResult
from sitree.pipeline import ClassifyConfig, _build_client, _build_graph, run_crawl


def _result(url: str, *, depth: int, referrer: str | None) -> FetchResult:
    return FetchResult(url=url, status=200, html="", discovered_links=[], depth=depth, referrer=referrer)


def test_build_graph_aliases_redirected_seed() -> None:
    # Seed https://x.com/ redirects to /3/; discovery-seeded children carry the
    # pre-redirect seed as referrer. The graph must NOT contain a phantom raw-URL
    # root node — those edges should originate from the real root template.
    results = [
        _result("https://x.com/3/", depth=0, referrer=None),  # seed after redirect
        _result("https://x.com/3/library/index.html", depth=1, referrer="https://x.com/"),
        _result("https://x.com/3/tutorial/index.html", depth=1, referrer="https://x.com/"),
    ]
    graph = _build_graph("https://x.com", results, CrawlConfig())

    templates = {n.template for n in graph.nodes}
    assert not any(t.startswith("http") for t in templates), f"phantom node present: {templates}"
    # No node should be left with zero url_samples (the phantom symptom).
    assert all(n.url_samples for n in graph.nodes)
    # The redirected seed's children connect to the real root template.
    root_tpl = next(n.template for n in graph.nodes if n.depth == 0)
    assert any(e.source == root_tpl for e in graph.edges)


async def test_run_crawl_applies_labels_when_classify_enabled() -> None:
    site = {
        "/": '<html><head><title>Home</title></head><body><a href="/about">About</a></body></html>',
        "/about": "<html><head><title>About us</title></head><body>about</body></html>",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = site.get(request.url.path)
        if body is None:
            return httpx.Response(404)
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    seen: list[GroupInput] = []

    async def fake_labeler(group: GroupInput):
        seen.append(group)
        return "Article"  # the only ambiguous template is /about

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        graph = await run_crawl(
            "https://example.com/",
            CrawlConfig(delay=0),
            client=client,
            classify=ClassifyConfig(enabled=True),
            labeler=fake_labeler,
        )

    by_tpl = {n.template: n for n in graph.nodes}
    assert by_tpl["/"].label == "Home"  # heuristic, no LLM
    assert by_tpl["/about"].label == "Article"  # via fake labeler
    # Representative title was threaded through to the group.
    assert [g.template for g in seen] == ["/about"]
    assert seen[0].title == "About us"


async def test_run_crawl_populates_edge_anchor_and_position() -> None:
    site = {
        "/": '<html><body><nav><a href="/about">About us</a></nav></body></html>',
        "/about": "<html><body>about</body></html>",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = site.get(request.url.path)
        return httpx.Response(404) if body is None else httpx.Response(
            200, text=body, headers={"content-type": "text/html"}
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        graph = await run_crawl("https://example.com/", CrawlConfig(delay=0), client=client)

    edge = next(e for e in graph.edges if e.target == "/about")
    assert edge.anchor_texts == ["About us"]
    assert edge.position == "nav"


async def test_build_client_injects_auth() -> None:
    auth = AuthConfig(cookies="session=abc", basic_auth=("u", "p"))
    async with _build_client(CrawlConfig(), auth, "https://x.com/") as client:
        assert client.headers["authorization"].startswith("Basic ")
        assert client.cookies.get("session") == "abc"
        assert client.headers["user-agent"].startswith("sitree/")


async def test_build_client_without_auth_has_no_cookies() -> None:
    async with _build_client(CrawlConfig(), None, "https://x.com/") as client:
        assert "authorization" not in client.headers
        assert len(client.cookies) == 0


async def test_run_crawl_no_classify_leaves_labels_none() -> None:
    site = {"/": "<html><head><title>Home</title></head><body>hi</body></html>"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=site["/"], headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        graph = await run_crawl("https://example.com/", CrawlConfig(delay=0), client=client)

    assert all(n.label is None for n in graph.nodes)
