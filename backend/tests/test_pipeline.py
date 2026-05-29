"""Pipeline graph-assembly tests (no network)."""

from __future__ import annotations

from sitree.core.crawler import CrawlConfig, FetchResult
from sitree.pipeline import _build_graph


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
