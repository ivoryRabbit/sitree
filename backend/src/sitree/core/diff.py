"""Auth-zone diff: what shows up only when authenticated.

Crawl a site anonymously and again with credentials, then keep the nodes/edges
present in the authenticated graph but absent anonymously. Useful for security
review and internal-tool mapping (docs/auth-strategies.md).
"""

from __future__ import annotations

from sitree.schema import SiteGraph


def auth_zone_diff(anon: SiteGraph, authed: SiteGraph) -> SiteGraph:
    """Subgraph of `authed` containing what's NOT reachable anonymously.

    - nodes: templates in `authed` but not in `anon`
    - edges: (source, target) pairs in `authed` but not in `anon`
    - endpoint nodes of those new edges are pulled in (even if public) so the
      result renders as a valid graph; node labels/metadata come from `authed`.
    """
    anon_nodes = {n.template for n in anon.nodes}
    anon_edges = {(e.source, e.target) for e in anon.edges}

    new_edges = [e for e in authed.edges if (e.source, e.target) not in anon_edges]

    keep = {n.template for n in authed.nodes if n.template not in anon_nodes}
    for edge in new_edges:
        keep.add(edge.source)
        keep.add(edge.target)

    nodes = [n for n in authed.nodes if n.template in keep]
    return SiteGraph(root=authed.root, nodes=nodes, edges=new_edges, meta=authed.meta)
