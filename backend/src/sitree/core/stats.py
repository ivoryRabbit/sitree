"""Summary statistics over a SiteGraph: totals, page-type and depth breakdowns,
and external-link counts. Used by `sitree report` and the dashboard stats panel.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from sitree.schema import SiteGraph


@dataclass
class GraphStats:
    total_nodes: int = 0
    total_edges: int = 0
    total_url_samples: int = 0
    max_depth: int = 0
    external_links: int = 0
    by_label: dict[str, int] = field(default_factory=dict)
    by_depth: dict[int, int] = field(default_factory=dict)
    by_position: dict[str, int] = field(default_factory=dict)


def _host(url: str) -> str | None:
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def compute_stats(graph: SiteGraph) -> GraphStats:
    """Aggregate counts over the graph. External links = edges whose target's URL
    samples resolve to a different host than the root (best-effort; templated
    targets without samples are treated as internal)."""
    labels = Counter((n.label or "Unlabeled") for n in graph.nodes)
    depths = Counter(n.depth for n in graph.nodes)
    positions = Counter(e.position for e in graph.edges)

    root_host = _host(graph.root)
    samples_by_template = {n.template: n.url_samples for n in graph.nodes}
    external = 0
    for edge in graph.edges:
        samples = samples_by_template.get(edge.target, [])
        host = _host(samples[0]) if samples else None
        if root_host and host and host != root_host:
            external += 1

    return GraphStats(
        total_nodes=len(graph.nodes),
        total_edges=len(graph.edges),
        total_url_samples=sum(len(n.url_samples) for n in graph.nodes),
        max_depth=max((n.depth for n in graph.nodes), default=0),
        external_links=external,
        by_label=dict(sorted(labels.items())),
        by_depth=dict(sorted(depths.items())),
        by_position=dict(sorted(positions.items())),
    )
