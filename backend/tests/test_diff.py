"""auth_zone_diff tests."""

from __future__ import annotations

from sitree.core.diff import auth_zone_diff
from sitree.schema import Edge, Node, SiteGraph


def _g(templates: list[str], edges: list[tuple[str, str]]) -> SiteGraph:
    return SiteGraph(
        root="https://x.com",
        nodes=[Node(template=t) for t in templates],
        edges=[Edge(source=s, target=t) for s, t in edges],
    )


def test_keeps_nodes_only_present_when_authenticated() -> None:
    anon = _g(["/", "/about"], [("/", "/about")])
    authed = _g(["/", "/about", "/dashboard", "/settings"], [("/", "/about"), ("/", "/dashboard"), ("/dashboard", "/settings")])

    diff = auth_zone_diff(anon, authed)
    templates = {n.template for n in diff.nodes}
    # New auth-only nodes present; the public /about (no new edge) is dropped.
    assert "/dashboard" in templates
    assert "/settings" in templates
    assert "/about" not in templates


def test_new_edge_endpoints_pulled_in_for_renderability() -> None:
    # / and /about are both public, but the link /about -> /admin only appears authed.
    anon = _g(["/", "/about"], [("/", "/about")])
    authed = _g(["/", "/about", "/admin"], [("/", "/about"), ("/about", "/admin")])

    diff = auth_zone_diff(anon, authed)
    edges = {(e.source, e.target) for e in diff.edges}
    templates = {n.template for n in diff.nodes}
    assert ("/about", "/admin") in edges
    assert ("/", "/about") not in edges  # already visible anonymously
    # both endpoints kept so the edge renders, even though /about is public
    assert {"/about", "/admin"} <= templates


def test_identical_graphs_yield_empty_diff() -> None:
    g = _g(["/", "/a"], [("/", "/a")])
    diff = auth_zone_diff(g, _g(["/", "/a"], [("/", "/a")]))
    assert diff.nodes == []
    assert diff.edges == []


def test_diff_preserves_authed_node_labels() -> None:
    anon = _g(["/"], [])
    authed = SiteGraph(
        root="https://x.com",
        nodes=[Node(template="/"), Node(template="/dashboard", label="Other")],
        edges=[],
    )
    diff = auth_zone_diff(anon, authed)
    assert diff.nodes[0].template == "/dashboard"
    assert diff.nodes[0].label == "Other"
