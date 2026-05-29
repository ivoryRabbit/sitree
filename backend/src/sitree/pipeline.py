"""Glue between discovery → crawler → graph → JSON. Used by the CLI `crawl` command."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime

import httpx

from sitree.core.crawler import CrawlConfig, FetchResult, crawl
from sitree.core.discovery import discover
from sitree.core.graph import GraphBuilder
from sitree.core.url_normalize import normalize, templatize
from sitree.schema import CrawlMeta, SiteGraph


async def run_crawl(
    seed: str, config: CrawlConfig, *, client: httpx.AsyncClient | None = None
) -> SiteGraph:
    """Full Phase 1 batch crawl: discovery → BFS → graph build."""
    if client is None:
        async with httpx.AsyncClient(
            headers={"User-Agent": config.user_agent}, timeout=config.timeout
        ) as owned:
            return await run_crawl(seed, config, client=owned)

    discovery = await discover(seed, client)
    allowed = discovery.robots.can_fetch if config.respect_robots else None

    # Honor robots crawl-delay without mutating the caller's config object.
    crawl_delay = discovery.robots.crawl_delay
    if crawl_delay and crawl_delay > config.delay:
        config = replace(config, delay=crawl_delay)

    results = await crawl(
        seed, config, initial_urls=discovery.initial_urls, allowed=allowed, client=client
    )
    return _build_graph(seed, results, config)


def _build_graph(seed: str, results: list[FetchResult], config: CrawlConfig) -> SiteGraph:
    urls = [r.url for r in results]
    templates = templatize(urls)

    # The seed can redirect (e.g. https://host/ -> https://host/3/). Discovery
    # seeds sitemap/seed-page URLs with the *pre-redirect* seed as their referrer,
    # which never appears as a crawled result. Without aliasing it to the root
    # result's template, its lookup falls back to the raw URL and creates a
    # phantom root node with no url_samples.
    seed_norm = normalize(seed)
    if seed_norm not in templates:
        root = next((r for r in results if r.referrer is None), None)
        if root is not None:
            templates[seed_norm] = templates.get(root.url, root.url)

    builder = GraphBuilder(root=seed)
    for r in results:
        tpl = templates.get(r.url, r.url)
        builder.add_node(
            tpl,
            url_samples=[r.url],
            depth=r.depth,
            status_codes=[r.status],
        )
        if r.referrer is None:
            continue
        src_tpl = templates.get(r.referrer, r.referrer)
        if src_tpl != tpl:
            builder.add_edge(src_tpl, tpl)

    meta = CrawlMeta(
        ran_at=datetime.now(),
        seed_url=seed,
        max_pages=config.max_pages,
        max_depth=config.max_depth,
        robots_respected=config.respect_robots,
        user_agent=config.user_agent,
    )
    return builder.to_site_graph(meta=meta)


def run_crawl_sync(seed: str, config: CrawlConfig) -> SiteGraph:
    return asyncio.run(run_crawl(seed, config))
