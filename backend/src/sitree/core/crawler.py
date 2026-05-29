"""Async crawler: httpx first, Playwright fallback when HTML looks like a JS shell.

Phase 1 currently implements only the static (httpx) path. JS fallback lands in Phase 3.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
from selectolax.parser import HTMLParser

from sitree.core.url_normalize import normalize


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
class FetchResult:
    url: str
    status: int
    html: str
    discovered_links: list[str]
    depth: int = 0
    referrer: str | None = None


def extract_links(html: str, base_url: str) -> list[str]:
    tree = HTMLParser(html)
    out: list[str] = []
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
        if normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
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
    initial_urls: list[str] | None = None,
    allowed: "callable[[str], bool] | None" = None,
    client: httpx.AsyncClient | None = None,
) -> list[FetchResult]:
    """BFS crawl from `seed`.

    Args:
        initial_urls: extra URLs to seed the frontier (e.g., from sitemap discovery).
        allowed: predicate to filter URLs (e.g., robots.txt). Defaults to allow-all.
        client: optional pre-configured AsyncClient (useful for tests with MockTransport).
            When omitted, a default client is created from `config`.
    """
    config = config or CrawlConfig()
    seed_norm = normalize(seed)
    allow_fn = allowed or (lambda _: True)

    frontier: deque[tuple[str, int, str | None]] = deque()
    seen: set[str] = set()

    def enqueue(url: str, depth: int, referrer: str | None) -> None:
        if url in seen:
            return
        if config.same_origin_only and not _same_origin(url, seed_norm):
            return
        if not allow_fn(url):
            return
        seen.add(url)
        frontier.append((url, depth, referrer))

    enqueue(seed_norm, 0, None)
    for u in initial_urls or []:
        enqueue(normalize(u), 1, seed_norm)

    results: list[FetchResult] = []
    semaphore = asyncio.Semaphore(config.concurrency)

    async def worker(url: str, depth: int, referrer: str | None, c: httpx.AsyncClient) -> FetchResult | None:
        async with semaphore:
            if config.delay > 0:
                await asyncio.sleep(config.delay)
            try:
                result = await fetch(url, c)
            except httpx.HTTPError:
                return None
        result.depth = depth
        result.referrer = referrer
        return result

    async def _run(c: httpx.AsyncClient) -> None:
        while frontier and len(results) < config.max_pages:
            batch: list[tuple[str, int, str | None]] = []
            while frontier and len(batch) < config.concurrency and len(results) + len(batch) < config.max_pages:
                batch.append(frontier.popleft())

            batch_results = await asyncio.gather(
                *(worker(u, d, r, c) for u, d, r in batch)
            )

            for result in batch_results:
                if result is None:
                    continue
                results.append(result)
                if result.depth >= config.max_depth:
                    continue
                for link in result.discovered_links:
                    enqueue(link, result.depth + 1, result.url)

    if client is not None:
        await _run(client)
    else:
        headers = {"User-Agent": config.user_agent}
        async with httpx.AsyncClient(headers=headers, timeout=config.timeout) as owned:
            await _run(owned)

    return results
