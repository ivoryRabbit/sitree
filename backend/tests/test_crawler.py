"""Crawler tests using httpx.MockTransport — no real network."""

from __future__ import annotations

import httpx
import pytest

from sitree.core.crawler import CrawlConfig, crawl, extract_links, fetch, looks_like_js_shell


def test_extract_links_filters_non_http_and_normalizes(sample_html: str) -> None:
    urls = [link.url for link in extract_links(sample_html, base_url="https://example.com/")]
    # mailto/anchor/javascript are filtered; remaining absolute + normalized
    assert "https://example.com/about" in urls
    assert "https://example.com/products/42" in urls
    assert "https://other.example.com/x" in urls
    # tracking-only query becomes empty query under normalize
    assert "https://example.com/" in urls
    # mailto and # filtered out
    assert not any(u.startswith("mailto:") for u in urls)
    assert not any("#" in u for u in urls)


def test_extract_links_dedupes() -> None:
    html = '<a href="/x">1</a><a href="/x">2</a><a href="/x?utm_source=a">3</a>'
    links = extract_links(html, "https://example.com/")
    # All three resolve to the same normalized URL
    assert [link.url for link in links] == ["https://example.com/x"]


def test_extract_links_captures_anchor_and_position() -> None:
    html = """
    <html><body>
      <nav><a href="/home">Home</a></nav>
      <header><a href="/login">Sign in</a></header>
      <main><a href="/product/1">  Cool Widget  </a></main>
      <article><a href="/post/1">Read more</a></article>
      <footer><a href="/about">About</a></footer>
      <a href="/loose">Loose</a>
    </body></html>
    """
    by_url = {link.url: link for link in extract_links(html, "https://x.com/")}

    assert by_url["https://x.com/home"].position == "nav"
    assert by_url["https://x.com/login"].position == "nav"  # header grouped with nav
    assert by_url["https://x.com/product/1"].position == "main"
    assert by_url["https://x.com/post/1"].position == "main"  # article grouped with main
    assert by_url["https://x.com/about"].position == "footer"
    assert by_url["https://x.com/loose"].position == "other"
    # anchor text is trimmed
    assert by_url["https://x.com/product/1"].anchor_text == "Cool Widget"


async def test_fetch_uses_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(
                200,
                html='<html><body><a href="/about">About</a><a href="/p/1">P</a></body></html>',
                headers={"content-type": "text/html"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        result = await fetch("https://example.com/", client)

    assert result.status == 200
    assert result.url == "https://example.com/"
    assert {link.url for link in result.discovered_links} == {
        "https://example.com/about",
        "https://example.com/p/1",
    }


async def test_fetch_handles_non_html_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"k":"v"}', headers={"content-type": "application/json"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch("https://example.com/api", client)

    assert result.status == 200
    assert result.html == ""
    assert result.discovered_links == []


async def test_fetch_follows_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        if request.url.path == "/new":
            return httpx.Response(200, html="<html><body>ok</body></html>", headers={"content-type": "text/html"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        result = await fetch("https://example.com/old", client)

    assert result.url == "https://example.com/new"
    assert result.status == 200


@pytest.fixture
def sample_html() -> str:  # local override for test classes that don't pull conftest
    return """
    <html><body>
      <a href="/about">About</a>
      <a href="/products/42">Product 42</a>
      <a href="https://other.example.com/x">External</a>
      <a href="mailto:noone@example.com">Mail</a>
      <a href="#anchor">Anchor</a>
      <a href="?utm_source=ad">Tracking-only</a>
    </body></html>
    """


# --- BFS integration tests ---

_SITE: dict[str, str] = {
    "/": '<html><body><a href="/a">A</a><a href="/b">B</a></body></html>',
    "/a": '<html><body><a href="/a/1">A1</a><a href="/a/2">A2</a><a href="/">Home</a></body></html>',
    "/b": '<html><body><a href="/b/deep">Deep</a></body></html>',
    "/a/1": '<html><body>leaf</body></html>',
    "/a/2": '<html><body>leaf</body></html>',
    "/b/deep": '<html><body><a href="/b/deep/deeper">Deeper</a></body></html>',
    "/b/deep/deeper": '<html><body>leaf</body></html>',
}


def _site_handler(request: httpx.Request) -> httpx.Response:
    body = _SITE.get(request.url.path)
    if body is None:
        return httpx.Response(404)
    return httpx.Response(200, text=body, headers={"content-type": "text/html"})


@pytest.fixture
def fast_crawl_config() -> CrawlConfig:
    return CrawlConfig(delay=0, concurrency=2)


async def test_crawl_bfs_visits_all_reachable(fast_crawl_config: CrawlConfig) -> None:
    transport = httpx.MockTransport(_site_handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        results = await crawl("https://example.com/", fast_crawl_config, client=client)

    urls = {r.url for r in results}
    expected = {f"https://example.com{p}" for p in _SITE}
    assert urls == expected, f"missing: {expected - urls}, extra: {urls - expected}"


async def test_crawl_respects_max_pages(fast_crawl_config: CrawlConfig) -> None:
    fast_crawl_config.max_pages = 3
    transport = httpx.MockTransport(_site_handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        results = await crawl("https://example.com/", fast_crawl_config, client=client)

    assert len(results) <= 3


async def test_crawl_respects_max_depth(fast_crawl_config: CrawlConfig) -> None:
    fast_crawl_config.max_depth = 1  # seed=0, direct links=1, nothing deeper
    transport = httpx.MockTransport(_site_handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        results = await crawl("https://example.com/", fast_crawl_config, client=client)

    urls = {r.url for r in results}
    assert "https://example.com/" in urls
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls
    # depth-2 should be excluded
    assert "https://example.com/a/1" not in urls
    assert "https://example.com/b/deep" not in urls


async def test_crawl_same_origin_filter(fast_crawl_config: CrawlConfig) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com" and request.url.path == "/":
            return httpx.Response(
                200,
                text='<html><body><a href="https://other.com/x">External</a><a href="/local">L</a></body></html>',
                headers={"content-type": "text/html"},
            )
        if request.url.host == "example.com" and request.url.path == "/local":
            return httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"})
        raise AssertionError(f"unexpected request to {request.url}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        results = await crawl("https://example.com/", fast_crawl_config, client=client)

    urls = {r.url for r in results}
    assert "https://other.com/x" not in urls


async def test_crawl_allowed_predicate_blocks_urls(fast_crawl_config: CrawlConfig) -> None:
    transport = httpx.MockTransport(_site_handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        results = await crawl(
            "https://example.com/",
            fast_crawl_config,
            allowed=lambda u: "/b" not in u,
            client=client,
        )

    urls = {r.url for r in results}
    assert "https://example.com/b" not in urls
    assert "https://example.com/b/deep" not in urls
    assert "https://example.com/a" in urls


# --- JS render fallback ---


def test_looks_like_js_shell_detects_spa() -> None:
    shell = '<html><body><div id="root"></div><script src="/app.js"></script></body></html>'
    assert looks_like_js_shell(shell) is True


def test_looks_like_js_shell_false_for_content_page() -> None:
    rich = "<html><body>" + "<p>word</p>" * 60 + "</body></html>"
    assert looks_like_js_shell(rich) is False
    assert looks_like_js_shell("") is False


def test_looks_like_js_shell_false_when_links_present() -> None:
    # Sparse text but plenty of links → not a shell (it's a nav/index page).
    html = "<html><body>" + "".join(f'<a href="/{i}">x</a>' for i in range(5)) + "</body></html>"
    assert looks_like_js_shell(html) is False


async def test_crawl_renders_shell_pages_in_auto_mode() -> None:
    shell = '<html><body><div id="app"></div><script></script><script></script><script></script></body></html>'
    rendered = '<html><body><a href="/loaded">Loaded</a></body></html>'

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/":
            return httpx.Response(200, text=shell, headers={"content-type": "text/html"})
        return httpx.Response(200, text="<html><body>leaf</body></html>", headers={"content-type": "text/html"})

    rendered_urls: list[str] = []

    async def fake_render(url: str) -> str:
        rendered_urls.append(url)
        return rendered

    config = CrawlConfig(delay=0, render_mode="auto")
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        results = await crawl("https://example.com/", config, client=client, render=fake_render)

    urls = {r.url for r in results}
    # The link only present in the *rendered* HTML was discovered and crawled.
    assert "https://example.com/loaded" in urls
    assert rendered_urls == ["https://example.com/"]  # only the shell page rendered


async def test_crawl_never_mode_skips_render() -> None:
    shell = '<html><body><div id="app"></div><script></script><script></script><script></script></body></html>'
    calls: list[str] = []

    async def fake_render(url: str) -> str:
        calls.append(url)
        return "<html></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=shell, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        await crawl("https://example.com/", CrawlConfig(delay=0, render_mode="never"), client=client, render=fake_render)

    assert calls == []  # render_mode=never → renderer never invoked


async def test_crawl_assigns_depth_and_referrer(fast_crawl_config: CrawlConfig) -> None:
    fast_crawl_config.max_depth = 2
    transport = httpx.MockTransport(_site_handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
        results = await crawl("https://example.com/", fast_crawl_config, client=client)

    by_url = {r.url: r for r in results}
    assert by_url["https://example.com/"].depth == 0
    assert by_url["https://example.com/"].referrer is None
    assert by_url["https://example.com/a"].depth == 1
    assert by_url["https://example.com/a"].referrer == "https://example.com/"
