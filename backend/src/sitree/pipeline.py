"""Glue between discovery → crawler → graph → JSON. Used by the CLI `crawl` command."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import httpx
from selectolax.parser import HTMLParser

from sitree.core.auth import AuthConfig, to_http_auth
from sitree.core.classifier import (
    DEFAULT_MODEL,
    AnthropicLabeler,
    GroupInput,
    Labeler,
    classify_groups,
)
from sitree.core.crawler import CrawlConfig, FetchResult, crawl
from sitree.core.discovery import discover
from sitree.core.graph import GraphBuilder
from sitree.core.url_normalize import normalize, templatize
from sitree.schema import CrawlMeta, SiteGraph


@dataclass
class ClassifyConfig:
    """Opt-in AI labeling. When `enabled` is False the crawl stays offline."""

    enabled: bool = False
    model: str | None = None
    cache_dir: Path | None = None


async def run_crawl(
    seed: str,
    config: CrawlConfig,
    *,
    client: httpx.AsyncClient | None = None,
    auth: AuthConfig | None = None,
    classify: ClassifyConfig | None = None,
    labeler: Labeler | None = None,
) -> SiteGraph:
    """Full batch crawl: discovery → BFS → graph build → optional AI labeling.

    `auth` injects user-supplied credentials (cookies / storage_state / basic).
    `labeler` overrides the default Claude labeler (used in tests to avoid network).
    """
    if client is None:
        async with _build_client(config, auth, seed) as owned:
            return await run_crawl(
                seed, config, client=owned, classify=classify, labeler=labeler
            )

    discovery = await discover(seed, client)
    allowed = discovery.robots.can_fetch if config.respect_robots else None

    # Honor robots crawl-delay without mutating the caller's config object.
    crawl_delay = discovery.robots.crawl_delay
    if crawl_delay and crawl_delay > config.delay:
        config = replace(config, delay=crawl_delay)

    results = await crawl(
        seed, config, initial_urls=discovery.initial_urls, allowed=allowed, client=client
    )
    templates = _templatize_results(seed, results)
    graph = _build_graph(seed, results, config, templates)

    if classify is not None and classify.enabled:
        await _classify_graph(graph, results, templates, classify, labeler)

    return graph


def _build_client(
    config: CrawlConfig, auth: AuthConfig | None, seed: str
) -> httpx.AsyncClient:
    """Construct the crawl's httpx client, injecting user-supplied auth (if any)."""
    headers = {"User-Agent": config.user_agent}
    cookies: dict[str, str] = {}
    if auth is not None:
        resolved = to_http_auth(auth, seed_url=seed)
        headers.update(resolved.headers)
        cookies = resolved.cookies
    return httpx.AsyncClient(headers=headers, cookies=cookies, timeout=config.timeout)


def _templatize_results(seed: str, results: list[FetchResult]) -> dict[str, str]:
    """URL -> template, with the redirected-seed alias applied (see _build_graph)."""
    templates = templatize([r.url for r in results])
    seed_norm = normalize(seed)
    if seed_norm not in templates:
        root = next((r for r in results if r.referrer is None), None)
        if root is not None:
            templates[seed_norm] = templates.get(root.url, root.url)
    return templates


def _build_graph(
    seed: str,
    results: list[FetchResult],
    config: CrawlConfig,
    templates: dict[str, str] | None = None,
) -> SiteGraph:
    templates = templates if templates is not None else _templatize_results(seed, results)

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
            anchors = [r.anchor_text] if r.anchor_text else []
            builder.add_edge(src_tpl, tpl, anchor_texts=anchors, position=r.position)

    meta = CrawlMeta(
        ran_at=datetime.now(),
        seed_url=seed,
        max_pages=config.max_pages,
        max_depth=config.max_depth,
        robots_respected=config.respect_robots,
        user_agent=config.user_agent,
    )
    return builder.to_site_graph(meta=meta)


def _page_title(html: str) -> str | None:
    if not html:
        return None
    node = HTMLParser(html).css_first("title")
    text = node.text(strip=True) if node else None
    return text or None


async def _classify_graph(
    graph: SiteGraph,
    results: list[FetchResult],
    templates: dict[str, str],
    classify: ClassifyConfig,
    labeler: Labeler | None,
) -> None:
    """Assign node.label in place. One LLM call per ambiguous template group."""
    # First non-empty <title> per template becomes the representative.
    titles: dict[str, str] = {}
    for r in results:
        tpl = templates.get(r.url)
        if tpl and tpl not in titles:
            title = _page_title(r.html)
            if title:
                titles[tpl] = title

    groups = [
        GroupInput(template=n.template, sample_urls=n.url_samples[:3], title=titles.get(n.template))
        for n in graph.nodes
    ]
    if labeler is None:
        labeler = AnthropicLabeler(model=classify.model or DEFAULT_MODEL)

    labels = await classify_groups(groups, labeler=labeler, cache_dir=classify.cache_dir)
    for node in graph.nodes:
        if node.template in labels:
            node.label = labels[node.template]


def run_crawl_sync(
    seed: str,
    config: CrawlConfig,
    *,
    auth: AuthConfig | None = None,
    classify: ClassifyConfig | None = None,
) -> SiteGraph:
    return asyncio.run(run_crawl(seed, config, auth=auth, classify=classify))
