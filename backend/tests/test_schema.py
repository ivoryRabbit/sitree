from datetime import datetime

from sitree.schema import (
    AddEdgeOp,
    AddNodeOp,
    CrawlMeta,
    CurrentOp,
    Edge,
    Node,
    SiteGraph,
    VisitOp,
    _to_jsonable,
    from_dict,
    from_json,
    to_dict,
    to_json,
)


def _sample_graph() -> SiteGraph:
    return SiteGraph(
        root="https://example.com",
        nodes=[
            Node(template="/", url_samples=["https://example.com/"], depth=0, label="Home"),
            Node(template="/product/{id}", url_samples=["https://example.com/product/1"], depth=1, label="PDP"),
        ],
        edges=[Edge(source="/", target="/product/{id}", anchor_texts=["product"], count=3, position="main")],
        meta=CrawlMeta(
            ran_at=datetime(2026, 5, 25, 10, 0, 0),
            seed_url="https://example.com",
            max_pages=100,
            max_depth=5,
            robots_respected=True,
            user_agent="sitree/0.1",
        ),
    )


def test_to_dict_shape() -> None:
    g = _sample_graph()
    d = to_dict(g)
    assert d["root"] == "https://example.com"
    assert len(d["nodes"]) == 2
    assert d["nodes"][0]["label"] == "Home"
    assert d["meta"]["ran_at"] == "2026-05-25T10:00:00"


def test_json_roundtrip_preserves_data() -> None:
    g = _sample_graph()
    text = to_json(g)
    g2 = from_json(text)
    assert g2.root == g.root
    assert len(g2.nodes) == 2
    assert g2.nodes[1].label == "PDP"
    assert g2.nodes[1].template == "/product/{id}"
    assert g2.edges[0].count == 3
    assert g2.meta is not None
    assert g2.meta.ran_at == datetime(2026, 5, 25, 10, 0, 0)


def test_from_dict_handles_missing_optionals() -> None:
    g = from_dict({"root": "https://x.com", "nodes": [], "edges": []})
    assert g.root == "https://x.com"
    assert g.meta is None


def test_node_defaults() -> None:
    n = Node(template="/")
    assert n.depth == 0
    assert n.state == "discovered"
    assert n.visit_count == 0
    assert n.last_visited_at is None


def test_live_ops_serialize_with_discriminator() -> None:
    # Matches the TS LiveOp union in frontend/src/lib/types.ts: each op carries an `op` tag.
    visit = _to_jsonable(VisitOp(template="/p/{id}", url="https://x.com/p/1", at=datetime(2026, 5, 29)))
    assert visit == {"template": "/p/{id}", "url": "https://x.com/p/1", "at": "2026-05-29T00:00:00", "op": "visit"}

    add_node = _to_jsonable(AddNodeOp(node=Node(template="/")))
    assert add_node["op"] == "add_node"
    assert add_node["node"]["template"] == "/"

    add_edge = _to_jsonable(AddEdgeOp(edge=Edge(source="/", target="/p/{id}")))
    assert add_edge["op"] == "add_edge"
    assert add_edge["edge"]["source"] == "/"

    assert _to_jsonable(CurrentOp(template="/")) == {"template": "/", "op": "current"}
