"""Async crawler: httpx first, Playwright fallback when HTML looks like a JS shell.

Phase 1 currently implements only the static (httpx) path. JS fallback lands in Phase 3.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
from selectolax.parser import HTMLParser, Node

from sitree.core.url_normalize import normalize
from sitree.schema import EdgePosition


@dataclass
class CrawlConfig:
    max_depth: int = 5
    max_pages: int = 500
    concurrency: int = 4
    delay: float = 0.5
    timeout: float = 20.0
    same_origin_only: bool = True
    user_agent: str = "sitree/0.1 (+https://github.com/sitree/sitree)"
    respect_robots: bool = True


@dataclass
class Link:
    """A discovered outbound link, with the metadata sitree records on edges."""

    url: str
    anchor_text: str = ""
    position: EdgePosition = "other"


@dataclass
class _Pending:
    """A frontier entry: a URL plus the link metadata that led to it."""

    url: str
    depth: int
    referrer: str | None
    anchor_text: str = ""
    position: EdgePosition = "other"


@dataclass
class FetchResult:
    url: str
    status: int
    html: str
    discovered_links: list[Link]
    depth: int = 0
    # The link that led here (for edge building); set during the crawl.
    referrer: str | None = None
    anchor_text: str = ""
    position: EdgePosition = "other"


# Layout containers → canonical edge position. header is grouped with nav,
# article with main; anything else falls through to "other".
_POSITION_BY_TAG: dict[str, EdgePosition] = {
    "nav": "nav",
    "header": "nav",
    "footer": "footer",
    "main": "main",
    "article": "main",
}

_MAX_ANCHOR = 120


def _link_position(node: Node) -> EdgePosition:
    """Classify a link by its nearest layout-container ancestor."""
    cur = node.parent
    while cur is not None:
        position = _POSITION_BY_TAG.get(cur.tag)
        if position is not None:
            return position
        cur = cur.parent
    return "other"


def extract_links(html: str, base_url: str) -> list[Link]:
    """Extract outbound links with anchor text and DOM position.

    Deduped by normalized URL (first occurrence wins, keeping its anchor/position).
    """
    tree = HTMLParser(html)
    out: list[Link] = []
    seen: set[str] = set()
    for node in tree.css("a[href]"):
        href = node.attributes.get("href")
        if not href:
            continue
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        absolute = urljoin(base_url, href)
        try:
            normalized = normalize(absolute)
        except Exception:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        anchor = (node.text(strip=True) or "")[:_MAX_ANCHOR]
        out.append(Link(url=normalized, anchor_text=anchor, position=_link_position(node)))
    return out


async def fetch(url: str, client: httpx.AsyncClient) -> FetchResult:
    response = await client.get(url, follow_redirects=True)
    final_url = str(response.url)
    html = response.text if "html" in response.headers.get("content-type", "").lower() else ""
    links = extract_links(html, final_url) if html else []
    return FetchResult(
        url=normalize(final_url),
        status=response.status_code,
        html=html,
        discovered_links=links,
    )


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.scheme, pa.hostname, pa.port) == (pb.scheme, pb.hostname, pb.port)


async def crawl(
    seed: str,
    config: CrawlConfig | None = None,
    *,
    initial_urls: list[Link] | None = None,
    allowed: "callable[[str], bool] | None" = None,
    client: httpx.AsyncClient | None = None,
) -> list[FetchResult]:
    """BFS crawl from `seed`.

    Args:
        initial_urls: extra Links to seed the frontier (e.g., from sitemap/seed-page
            discovery). Seed-page Links carry anchor/position; sitemap ones don't.
        allowed: predicate to filter URLs (e.g., robots.txt). Defaults to allow-all.
        client: optional pre-configured AsyncClient (useful for tests with MockTransport).
            When omitted, a default client is created from `config`.
    """
    config = config or CrawlConfig()
    seed_norm = normalize(seed)
    allow_fn = allowed or (lambda _: True)

    frontier: deque[_Pending] = deque()
    seen: set[str] = set()

    def enqueue(
        url: str,
        depth: int,
        referrer: str | None,
        anchor_text: str = "",
        position: EdgePosition = "other",
    ) -> None:
        if url in seen:
            return
        if config.same_origin_only and not _same_origin(url, seed_norm):
            return
        if not allow_fn(url):
            return
        seen.add(url)
        frontier.append(_Pending(url, depth, referrer, anchor_text, position))

    enqueue(seed_norm, 0, None)
    for link in initial_urls or []:
        enqueue(normalize(link.url), 1, seed_norm, link.anchor_text, link.position)

    results: list[FetchResult] = []
    semaphore = asyncio.Semaphore(config.concurrency)

    async def worker(item: _Pending, c: httpx.AsyncClient) -> FetchResult | None:
        async with semaphore:
            if config.delay > 0:
                await asyncio.sleep(config.delay)
            try:
                result = await fetch(item.url, c)
            except httpx.HTTPError:
                return None
        result.depth = item.depth
        result.referrer = item.referrer
        result.anchor_text = item.anchor_text
        result.position = item.position
        return result

    async def _run(c: httpx.AsyncClient) -> None:
        while frontier and len(results) < config.max_pages:
            batch: list[_Pending] = []
            while frontier and len(batch) < config.concurrency and len(results) + len(batch) < config.max_pages:
                batch.append(frontier.popleft())

            batch_results = await asyncio.gather(*(worker(item, c) for item in batch))

            for result in batch_results:
                if result is None:
                    continue
                results.append(result)
                if result.depth >= config.max_depth:
                    continue
                for link in result.discovered_links:
                    enqueue(link.url, result.depth + 1, result.url, link.anchor_text, link.position)

    if client is not None:
        await _run(client)
    else:
        headers = {"User-Agent": config.user_agent}
        async with httpx.AsyncClient(headers=headers, timeout=config.timeout) as owned:
            await _run(owned)

    return results
