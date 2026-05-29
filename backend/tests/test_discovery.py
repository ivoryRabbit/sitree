"""Discovery tests with httpx.MockTransport (no real network)."""

from __future__ import annotations

import httpx
import pytest

from sitree.core.discovery import discover, fetch_robots, fetch_sitemap


def _transport(responses: dict[str, httpx.Response]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        key = f"{request.method} {request.url}"
        if key in responses:
            return responses[key]
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.fixture
def robots_text() -> str:
    return """
User-agent: *
Disallow: /admin/
Allow: /admin/public
Crawl-delay: 1.5
Sitemap: https://example.com/sitemap.xml
""".strip()


@pytest.fixture
def sitemap_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about</loc></url>
  <url><loc>https://example.com/products/1</loc></url>
</urlset>"""


@pytest.fixture
def sitemap_index_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>
</sitemapindex>"""


async def test_fetch_robots_parses_sitemap_and_delay(robots_text: str) -> None:
    transport = _transport({
        "GET https://example.com/robots.txt": httpx.Response(200, text=robots_text),
    })
    async with httpx.AsyncClient(transport=transport) as client:
        info = await fetch_robots("https://example.com", client)

    assert info.sitemaps == ["https://example.com/sitemap.xml"]
    assert info.crawl_delay == 1.5
    assert info.can_fetch("https://example.com/about") is True
    assert info.can_fetch("https://example.com/admin/secret") is False


async def test_fetch_robots_missing_returns_permissive() -> None:
    transport = _transport({})  # 404 for everything
    async with httpx.AsyncClient(transport=transport) as client:
        info = await fetch_robots("https://example.com", client)

    assert info.sitemaps == []
    assert info.crawl_delay is None
    assert info.can_fetch("https://example.com/anything") is True


async def test_fetch_sitemap_returns_locs(sitemap_xml: str) -> None:
    transport = _transport({
        "GET https://example.com/sitemap.xml": httpx.Response(200, text=sitemap_xml),
    })
    async with httpx.AsyncClient(transport=transport) as client:
        urls = await fetch_sitemap("https://example.com/sitemap.xml", client)

    assert urls == [
        "https://example.com/",
        "https://example.com/about",
        "https://example.com/products/1",
    ]


async def test_fetch_sitemap_recurses_into_index(sitemap_index_xml: str) -> None:
    leaf_1 = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/a</loc></url>
</urlset>"""
    leaf_2 = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/b</loc></url>
</urlset>"""
    transport = _transport({
        "GET https://example.com/sitemap.xml": httpx.Response(200, text=sitemap_index_xml),
        "GET https://example.com/sitemap-1.xml": httpx.Response(200, text=leaf_1),
        "GET https://example.com/sitemap-2.xml": httpx.Response(200, text=leaf_2),
    })
    async with httpx.AsyncClient(transport=transport) as client:
        urls = await fetch_sitemap("https://example.com/sitemap.xml", client)

    assert set(urls) == {"https://example.com/a", "https://example.com/b"}


async def test_fetch_sitemap_handles_404() -> None:
    transport = _transport({})
    async with httpx.AsyncClient(transport=transport) as client:
        urls = await fetch_sitemap("https://example.com/sitemap.xml", client)
    assert urls == []


async def test_discover_combines_robots_sitemap_seed(robots_text: str, sitemap_xml: str) -> None:
    home_html = '<html><body><a href="/about">A</a><a href="/contact">C</a></body></html>'
    transport = _transport({
        "GET https://example.com/robots.txt": httpx.Response(200, text=robots_text),
        "GET https://example.com/sitemap.xml": httpx.Response(200, text=sitemap_xml),
        "GET https://example.com/": httpx.Response(
            200, text=home_html, headers={"content-type": "text/html"}
        ),
    })
    async with httpx.AsyncClient(transport=transport) as client:
        result = await discover("https://example.com/", client)

    assert result.robots.crawl_delay == 1.5
    assert "https://example.com/about" in result.initial_urls
    assert "https://example.com/contact" in result.initial_urls
    assert "https://example.com/products/1" in result.initial_urls
    # initial_urls should be deduped
    assert len(result.initial_urls) == len(set(result.initial_urls))
