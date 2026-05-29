"""Server tests via FastAPI TestClient — no uvicorn, no network."""

from __future__ import annotations

from fastapi.testclient import TestClient

from sitree.schema import Node, SiteGraph
from sitree.server import create_app


def _graph() -> SiteGraph:
    return SiteGraph(
        root="https://example.com",
        nodes=[Node(template="/", url_samples=["https://example.com/"], label="Home")],
        edges=[],
    )


def test_health_ok() -> None:
    client = TestClient(create_app())
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_graph_served_when_loaded() -> None:
    client = TestClient(create_app(_graph()))
    res = client.get("/api/graph")
    assert res.status_code == 200
    body = res.json()
    assert body["root"] == "https://example.com"
    assert body["nodes"][0]["template"] == "/"
    assert body["nodes"][0]["label"] == "Home"


def test_graph_404_when_no_graph() -> None:
    client = TestClient(create_app(None))
    res = client.get("/api/graph")
    assert res.status_code == 404


def test_static_mount_serves_index(tmp_path) -> None:
    (tmp_path / "index.html").write_text("<html>sitree</html>")
    client = TestClient(create_app(_graph(), static_dir=tmp_path))
    # API still wins over the catch-all static mount.
    assert client.get("/api/graph").status_code == 200
    # Root serves the built index.html.
    root = client.get("/")
    assert root.status_code == 200
    assert "sitree" in root.text
