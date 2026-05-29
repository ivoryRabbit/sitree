"""NetworkX-backed graph builder. Produces schema.SiteGraph on serialize."""

from __future__ import annotations

from datetime import datetime

import networkx as nx

from sitree.schema import CrawlMeta, Edge, Node, SiteGraph


class GraphBuilder:
    def __init__(self, root: str) -> None:
        self.root = root
        self._g: nx.DiGraph = nx.DiGraph()

    def add_node(self, template: str, **attrs: object) -> None:
        if template in self._g:
            existing = self._g.nodes[template]
            # Merge url_samples (dedupe) and status_codes
            for key in ("url_samples", "status_codes"):
                if key in attrs:
                    merged = list({*existing.get(key, []), *attrs[key]})  # type: ignore[misc]
                    existing[key] = merged
            for k, v in attrs.items():
                if k not in ("url_samples", "status_codes"):
                    existing[k] = v
        else:
            self._g.add_node(template, **attrs)

    def add_edge(self, source: str, target: str, **attrs: object) -> None:
        if self._g.has_edge(source, target):
            existing = self._g.edges[source, target]
            existing["count"] = existing.get("count", 1) + 1
            new_anchors = attrs.get("anchor_texts", [])
            if new_anchors:
                existing["anchor_texts"] = list({*existing.get("anchor_texts", []), *new_anchors})  # type: ignore[misc]
        else:
            self._g.add_edge(source, target, **attrs)

    def node_count(self) -> int:
        return self._g.number_of_nodes()

    def edge_count(self) -> int:
        return self._g.number_of_edges()

    def to_site_graph(self, meta: CrawlMeta | None = None) -> SiteGraph:
        nodes = [
            Node(
                template=tpl,
                url_samples=data.get("url_samples", []),
                depth=data.get("depth", 0),
                status_codes=data.get("status_codes", []),
                label=data.get("label"),
                state=data.get("state", "discovered"),
                visit_count=data.get("visit_count", 0),
                last_visited_at=data.get("last_visited_at"),
            )
            for tpl, data in self._g.nodes(data=True)
        ]
        edges = [
            Edge(
                source=src,
                target=tgt,
                anchor_texts=data.get("anchor_texts", []),
                count=data.get("count", 1),
                position=data.get("position", "other"),
            )
            for src, tgt, data in self._g.edges(data=True)
        ]
        return SiteGraph(root=self.root, nodes=nodes, edges=edges, meta=meta)


def empty_meta(seed: str) -> CrawlMeta:
    return CrawlMeta(
        ran_at=datetime.now(),
        seed_url=seed,
        max_pages=0,
        max_depth=0,
        robots_respected=True,
        user_agent="sitree/0.1",
    )
