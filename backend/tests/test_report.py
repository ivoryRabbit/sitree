"""render_report tests — output is a single self-contained HTML string."""

from __future__ import annotations

import json
import re
from datetime import datetime

from sitree.report import render_report
from sitree.schema import CrawlMeta, Edge, Node, SiteGraph


def _graph() -> SiteGraph:
    return SiteGraph(
        root="https://x.com",
        nodes=[
            Node(template="/", url_samples=["https://x.com/"], depth=0, label="Home"),
            Node(template="/p/{id}", url_samples=["https://x.com/p/1"], depth=1, label="PDP"),
        ],
        edges=[Edge(source="/", target="/p/{id}", anchor_texts=["x"], count=2, position="nav")],
        meta=CrawlMeta(
            ran_at=datetime(2026, 5, 30, 10, 0, 0),
            seed_url="https://x.com",
            max_pages=100,
            max_depth=5,
            robots_respected=True,
            user_agent="sitree/0.1",
        ),
    )


def test_report_is_single_self_contained_html() -> None:
    out = render_report(_graph())
    assert out.startswith("<!doctype html>")
    assert "</html>" in out.strip()
    # no local asset references — graph embedded, cytoscape from CDN
    assert "src=\"./" not in out and "href=\"./" not in out


def test_report_embeds_graph_and_stats() -> None:
    out = render_report(_graph())
    assert "https://x.com" in out
    assert "/p/{id}" in out
    assert "Home" in out and "PDP" in out
    # the embedded JS data block parses
    m = re.search(r"const graph = (\{.*?\});", out, re.DOTALL)
    assert m is not None
    data = json.loads(m.group(1))
    assert len(data["nodes"]) == 2
    assert data["root"] == "https://x.com"


def test_report_escapes_html_in_root() -> None:
    g = SiteGraph(root="https://x.com/<script>", nodes=[], edges=[])
    out = render_report(g)
    assert "<script>alert" not in out  # sanity
    assert "&lt;script&gt;" in out


def test_report_without_meta() -> None:
    g = SiteGraph(root="https://x.com", nodes=[Node(template="/")], edges=[])
    out = render_report(g)  # must not crash when meta is None
    assert "crawled" not in out
