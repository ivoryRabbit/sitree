"""Live-mode tests: LiveSession ops, LiveHub fan-out, server wiring. No browser."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sitree.live.hub import LiveHub
from sitree.live.session import LiveSession
from sitree.schema import AddEdgeOp, AddNodeOp, CurrentOp, VisitEvent, VisitOp
from sitree.server import create_app


def _ev(url: str, *, referrer: str | None = None, links: list[str] | None = None) -> VisitEvent:
    return VisitEvent(url=url, at=datetime(2026, 5, 30, 12, 0, 0), referrer=referrer, links=links or [])


# --- LiveSession ---------------------------------------------------------------


def test_first_visit_adds_node_and_marks_current() -> None:
    s = LiveSession(root="https://x.com")
    ops = s.visit(_ev("https://x.com/"))
    kinds = [type(o) for o in ops]
    assert AddNodeOp in kinds and VisitOp in kinds and CurrentOp in kinds

    snap = s.snapshot()
    assert len(snap.nodes) == 1
    assert snap.nodes[0].state == "current"
    assert snap.nodes[0].visit_count == 1


def test_navigation_creates_edge_from_previous_page() -> None:
    s = LiveSession(root="https://x.com")
    s.visit(_ev("https://x.com/"))
    ops = s.visit(_ev("https://x.com/product/42"))

    assert any(isinstance(o, AddEdgeOp) for o in ops)
    edge = next(o for o in ops if isinstance(o, AddEdgeOp)).edge
    assert edge.source == "/"
    assert edge.target == "/product/{id}"  # templatize_one collapses the id

    snap = s.snapshot()
    states = {n.template: n.state for n in snap.nodes}
    assert states["/product/{id}"] == "current"
    assert states["/"] == "visited"  # previous current demoted


def test_referrer_overrides_previous_page_for_edge() -> None:
    s = LiveSession(root="https://x.com")
    s.visit(_ev("https://x.com/"))
    s.visit(_ev("https://x.com/a"))
    ops = s.visit(_ev("https://x.com/b", referrer="https://x.com/"))
    edge = next(o for o in ops if isinstance(o, AddEdgeOp)).edge
    assert (edge.source, edge.target) == ("/", "/b")


def test_discovered_links_added_as_dashed_nodes() -> None:
    s = LiveSession(root="https://x.com")
    ops = s.visit(_ev("https://x.com/", links=["https://x.com/about", "https://x.com/contact"]))
    new_nodes = {o.node.template: o.node for o in ops if isinstance(o, AddNodeOp)}
    assert new_nodes["/about"].state == "discovered"
    assert new_nodes["/contact"].state == "discovered"

    # Visiting a discovered node promotes it to current.
    s.visit(_ev("https://x.com/about"))
    states = {n.template: n.state for n in s.snapshot().nodes}
    assert states["/about"] == "current"


def test_revisiting_increments_count_without_duplicate_node() -> None:
    s = LiveSession(root="https://x.com")
    s.visit(_ev("https://x.com/p/1"))
    s.visit(_ev("https://x.com/other"))
    s.visit(_ev("https://x.com/p/2"))  # same template /p/{id}

    nodes = {n.template: n for n in s.snapshot().nodes}
    assert nodes["/p/{id}"].visit_count == 2
    assert set(nodes["/p/{id}"].url_samples) == {"https://x.com/p/1", "https://x.com/p/2"}


# --- LiveHub -------------------------------------------------------------------


def test_hub_fans_out_to_all_subscribers() -> None:
    hub = LiveHub()
    a, b = hub.subscribe(), hub.subscribe()
    assert hub.subscriber_count == 2

    ops = [CurrentOp(template="/")]
    asyncio.run(hub.publish(ops))
    assert a.get_nowait() is ops
    assert b.get_nowait() is ops


def test_hub_publish_empty_is_noop() -> None:
    hub = LiveHub()
    q = hub.subscribe()
    asyncio.run(hub.publish([]))
    assert q.empty()


def test_hub_unsubscribe() -> None:
    hub = LiveHub()
    q = hub.subscribe()
    hub.unsubscribe(q)
    assert hub.subscriber_count == 0


# --- server wiring -------------------------------------------------------------


def test_api_graph_uses_dynamic_provider() -> None:
    s = LiveSession(root="https://x.com")
    s.visit(_ev("https://x.com/"))
    client = TestClient(create_app(graph_provider=s.snapshot, hub=LiveHub()))
    body = client.get("/api/graph").json()
    assert body["root"] == "https://x.com"
    assert body["nodes"][0]["template"] == "/"


def test_live_ws_closes_without_hub() -> None:
    client = TestClient(create_app(graph=None))
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/live") as ws:
            ws.receive_text()
