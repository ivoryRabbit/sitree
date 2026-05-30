"""LiveSession: fold a stream of VisitEvents into an incremental SiteGraph and
emit the LiveOps that describe each change. Pure and synchronous — the transport
(WebSocket) and the capture (Playwright) live elsewhere.
"""

from __future__ import annotations

from sitree.core.url_normalize import normalize, templatize_one
from sitree.schema import (
    AddEdgeOp,
    AddNodeOp,
    CurrentOp,
    Edge,
    LiveOp,
    Node,
    SiteGraph,
    VisitEvent,
    VisitOp,
)


class LiveSession:
    """Accumulates live navigation into a graph. `visit()` returns the ops to
    broadcast; `snapshot()` returns the full graph for newly-connected clients."""

    def __init__(self, root: str) -> None:
        self.root = root
        self._nodes: dict[str, Node] = {}
        self._edges: dict[tuple[str, str], Edge] = {}
        self._current: str | None = None

    def visit(self, event: VisitEvent) -> list[LiveOp]:
        ops: list[LiveOp] = []
        url = normalize(event.url)
        template = templatize_one(url)

        node = self._nodes.get(template)
        if node is None:
            node = Node(template=template, url_samples=[url], state="visited")
            self._nodes[template] = node
            ops.append(AddNodeOp(node=node))
        elif url not in node.url_samples:
            node.url_samples.append(url)
        node.visit_count += 1
        node.last_visited_at = event.at

        # Navigation edge: from the referrer if known, else the previous page.
        source = self._current
        if event.referrer:
            source = templatize_one(normalize(event.referrer))
        ops += self._ensure_edge(source, template)

        # Discovered (not-yet-visited) links from the current page.
        for href in event.links:
            ops += self._add_discovered(template, href)

        # Current-page transition.
        if self._current and self._current != template:
            prev = self._nodes.get(self._current)
            if prev is not None and prev.state == "current":
                prev.state = "visited"
        node.state = "current"
        self._current = template

        ops.append(VisitOp(template=template, url=url, at=event.at))
        ops.append(CurrentOp(template=template))
        return ops

    def _ensure_edge(self, source: str | None, target: str) -> list[LiveOp]:
        if not source or source == target:
            return []
        ops: list[LiveOp] = []
        if source not in self._nodes:
            src = Node(template=source, state="discovered")
            self._nodes[source] = src
            ops.append(AddNodeOp(node=src))
        key = (source, target)
        if key not in self._edges:
            edge = Edge(source=source, target=target)
            self._edges[key] = edge
            ops.append(AddEdgeOp(edge=edge))
        return ops

    def _add_discovered(self, current: str, href: str) -> list[LiveOp]:
        try:
            href_norm = normalize(href)
        except Exception:
            return []
        template = templatize_one(href_norm)
        ops: list[LiveOp] = []
        if template not in self._nodes:
            node = Node(template=template, url_samples=[href_norm], state="discovered")
            self._nodes[template] = node
            ops.append(AddNodeOp(node=node))
        ops += self._ensure_edge(current, template)
        return ops

    def snapshot(self) -> SiteGraph:
        return SiteGraph(
            root=self.root,
            nodes=list(self._nodes.values()),
            edges=list(self._edges.values()),
        )
