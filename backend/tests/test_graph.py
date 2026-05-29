from sitree.core.graph import GraphBuilder


def test_basic_add_node_edge() -> None:
    b = GraphBuilder(root="https://example.com")
    b.add_node("/", depth=0)
    b.add_node("/about", depth=1)
    b.add_edge("/", "/about", anchor_texts=["About"], position="nav")

    g = b.to_site_graph()
    assert g.root == "https://example.com"
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert g.edges[0].position == "nav"


def test_adding_same_node_merges_url_samples() -> None:
    b = GraphBuilder(root="https://x.com")
    b.add_node("/p/{id}", url_samples=["https://x.com/p/1"])
    b.add_node("/p/{id}", url_samples=["https://x.com/p/2"])

    g = b.to_site_graph()
    assert len(g.nodes) == 1
    samples = set(g.nodes[0].url_samples)
    assert samples == {"https://x.com/p/1", "https://x.com/p/2"}


def test_merging_node_keeps_minimum_depth() -> None:
    # Same template reached at depth 0 (seed redirect) and depth 1 (deeper link):
    # depth means shortest distance from seed, so the shallower value must win
    # regardless of insertion order.
    b = GraphBuilder(root="https://x.com")
    b.add_node("/{id}", depth=1, url_samples=["https://x.com/3/"])
    b.add_node("/{id}", depth=0, url_samples=["https://x.com/3/"])
    assert b.to_site_graph().nodes[0].depth == 0

    b2 = GraphBuilder(root="https://x.com")
    b2.add_node("/{id}", depth=0)
    b2.add_node("/{id}", depth=2)
    assert b2.to_site_graph().nodes[0].depth == 0


def test_repeated_edge_increments_count() -> None:
    b = GraphBuilder(root="https://x.com")
    b.add_edge("/", "/a", anchor_texts=["A"])
    b.add_edge("/", "/a", anchor_texts=["A2"])
    b.add_edge("/", "/a")

    g = b.to_site_graph()
    assert len(g.edges) == 1
    assert g.edges[0].count == 3
    assert set(g.edges[0].anchor_texts) == {"A", "A2"}


def test_counts() -> None:
    b = GraphBuilder(root="x")
    b.add_node("/")
    b.add_node("/a")
    b.add_edge("/", "/a")
    assert b.node_count() == 2
    assert b.edge_count() == 1
