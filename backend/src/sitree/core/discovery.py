"""Seed URL pool: robots.txt + sitemap.xml + seed page links.

Public API:
    - fetch_robots(origin, client) -> RobotsInfo
    - fetch_sitemap(url, client) -> list[str]
    - discover(seed_url, client) -> DiscoveryResult
"""

from __future__ import annotations

import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

import httpx

from sitree.core.crawler import Link, extract_links
from sitree.core.url_normalize import normalize

USER_AGENT = "sitree"

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass
class RobotsInfo:
    """Parsed robots.txt facts. Empty if robots.txt was missing or unparseable."""

    sitemaps: list[str] = field(default_factory=list)
    crawl_delay: float | None = None
    _parser: urllib.robotparser.RobotFileParser | None = None

    def can_fetch(self, url: str, user_agent: str = USER_AGENT) -> bool:
        if self._parser is None:
            return True
        return self._parser.can_fetch(user_agent, url)


@dataclass
class DiscoveryResult:
    robots: RobotsInfo
    sitemap_urls: list[str]
    seed_links: list[Link]  # links found on the seed page, with anchor/position

    @property
    def initial_urls(self) -> list[Link]:
        """Frontier seeds as Links. Sitemap URLs carry no anchor; seed-page links
        keep theirs so seed→child edges (nav/footer/…) get proper metadata. When a
        URL appears in both, the seed-page anchor/position upgrades the bare entry."""
        index: dict[str, Link] = {}
        order: list[str] = []
        for link in [*(Link(url=u) for u in self.sitemap_urls), *self.seed_links]:
            existing = index.get(link.url)
            if existing is None:
                index[link.url] = link
                order.append(link.url)
            elif not existing.anchor_text and link.anchor_text:
                index[link.url] = link
        return [index[u] for u in order]


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


async def fetch_robots(origin: str, client: httpx.AsyncClient) -> RobotsInfo:
    url = origin.rstrip("/") + "/robots.txt"
    try:
        response = await client.get(url)
    except httpx.HTTPError:
        return RobotsInfo()
    if response.status_code >= 400:
        return RobotsInfo()

    text = response.text
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())

    sitemaps: list[str] = []
    crawl_delay: float | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "sitemap" and value:
            sitemaps.append(value)
        elif key == "crawl-delay" and value:
            try:
                crawl_delay = float(value)
            except ValueError:
                pass

    return RobotsInfo(sitemaps=sitemaps, crawl_delay=crawl_delay, _parser=parser)


async def fetch_sitemap(url: str, client: httpx.AsyncClient, *, max_depth: int = 2) -> list[str]:
    """Fetch a sitemap.xml or sitemap index. Returns all <loc> URLs.

    `max_depth` caps recursive sitemap-index expansion to avoid loops.
    """
    if max_depth < 0:
        return []
    try:
        response = await client.get(url)
    except httpx.HTTPError:
        return []
    if response.status_code >= 400 or not response.text.strip():
        return []

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        return []

    tag = root.tag.split("}", 1)[-1]
    locs = [el.text.strip() for el in root.iter() if el.tag.split("}", 1)[-1] == "loc" and el.text]

    if tag == "sitemapindex":
        out: list[str] = []
        for child_url in locs:
            out.extend(await fetch_sitemap(child_url, client, max_depth=max_depth - 1))
        return out
    return locs


async def discover(seed_url: str, client: httpx.AsyncClient) -> DiscoveryResult:
    """Build an initial URL pool for the given seed."""
    seed = normalize(seed_url)
    origin = _origin(seed)

    robots = await fetch_robots(origin, client)

    sitemap_candidates = robots.sitemaps or [f"{origin}/sitemap.xml"]
    sitemap_urls: list[str] = []
    for sm in sitemap_candidates:
        sitemap_urls.extend(await fetch_sitemap(sm, client))
    sitemap_urls = [normalize(u) for u in sitemap_urls]

    seed_links: list[Link] = []
    try:
        seed_response = await client.get(seed, follow_redirects=True)
        if seed_response.status_code < 400 and "html" in seed_response.headers.get("content-type", "").lower():
            seed_links = extract_links(seed_response.text, str(seed_response.url))
    except httpx.HTTPError:
        pass

    if seed not in sitemap_urls and not any(link.url == seed for link in seed_links):
        seed_links.insert(0, Link(url=seed))

    return DiscoveryResult(robots=robots, sitemap_urls=sitemap_urls, seed_links=seed_links)
