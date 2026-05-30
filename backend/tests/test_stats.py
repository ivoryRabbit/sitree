"""compute_stats tests."""

from __future__ import annotations

from sitree.core.stats import compute_stats
from sitree.schema import Edge, Node, SiteGraph


def _graph() -> SiteGraph:
    return SiteGraph(
        root="https://x.com",
        nodes=[
            Node(template="/", url_samples=["https://x.com/"], depth=0, label="Home"),
            Node(template="/p/{id}", url_samples=["https://x.com/p/1", "https://x.com/p/2"], depth=1, label="PDP"),
            Node(template="/ext", url_samples=["https://other.com/ext"], depth=1),  # external host
        ],
        edges=[
            Edge(source="/", target="/p/{id}", position="nav"),
            Edge(source="/", target="/ext", position="footer"),
        ],
    )


def test_totals_and_depth() -> None:
    s = compute_stats(_graph())
    assert s.total_nodes == 3
    assert s.total_edges == 2
    assert s.total_url_samples == 4
    assert s.max_depth == 1
    assert s.by_depth == {0: 1, 1: 2}


def test_label_breakdown_includes_unlabeled() -> None:
    s = compute_stats(_graph())
    assert s.by_label == {"Home": 1, "PDP": 1, "Unlabeled": 1}


def test_external_links_counted_by_target_host() -> None:
    s = compute_stats(_graph())
    # only /ext resolves to a different host
    assert s.external_links == 1


def test_position_breakdown() -> None:
    s = compute_stats(_graph())
    assert s.by_position == {"footer": 1, "nav": 1}


def test_empty_graph() -> None:
    s = compute_stats(SiteGraph(root="https://x.com"))
    assert s.total_nodes == 0
    assert s.max_depth == 0
    assert s.external_links == 0
