"""FastAPI server for `sitree view` and `sitree live`.

Routes:
  GET  /api/health    - liveness probe
  GET  /api/graph     - current SiteGraph snapshot (JSON)
  WS   /api/live      - real-time LiveOp stream (when a hub is wired)
  GET  /              - built SvelteKit frontend (static), if available
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sitree.live.hub import LiveHub
from sitree.schema import SiteGraph, to_dict, to_jsonable


def find_frontend_build() -> Path | None:
    """Locate the built SvelteKit static output.

    Checks the packaged location first (frontend copied next to this module when
    shipped in a wheel), then the dev-tree layout (<repo>/frontend/build).
    """
    candidates = [
        Path(__file__).resolve().parent / "static",
        Path(__file__).resolve().parents[3] / "frontend" / "build",
    ]
    for c in candidates:
        if (c / "index.html").is_file():
            return c
    return None


def create_app(
    graph: SiteGraph | None = None,
    *,
    static_dir: Path | None = None,
    graph_provider: Callable[[], SiteGraph] | None = None,
    hub: LiveHub | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    - `graph` (static) or `graph_provider` (dynamic, e.g. a LiveSession.snapshot)
      backs GET /api/graph.
    - `hub` enables the WS /api/live op stream.
    - the frontend build (if found) is mounted at /. API/WS routes are registered
      before the static mount so they take precedence over the catch-all.
    """
    app = FastAPI(title="sitree")

    def snapshot() -> SiteGraph | None:
        if graph_provider is not None:
            return graph_provider()
        return graph

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/graph")
    async def get_graph() -> JSONResponse:
        current = snapshot()
        if current is None:
            raise HTTPException(status_code=404, detail="no graph loaded")
        return JSONResponse(to_dict(current))

    @app.websocket("/api/live")
    async def live(ws: WebSocket) -> None:
        if hub is None:
            await ws.close(code=1011)
            return
        await ws.accept()
        queue = hub.subscribe()
        try:
            while True:
                ops = await queue.get()
                await ws.send_json([to_jsonable(op) for op in ops])
        except WebSocketDisconnect:
            pass
        finally:
            hub.unsubscribe(queue)

    build = static_dir or find_frontend_build()
    if build is not None:
        app.mount("/", StaticFiles(directory=build, html=True), name="static")

    return app


def serve(app: FastAPI, *, host: str, port: int, open_url: str | None = None) -> None:
    """Run the app with uvicorn (blocking). Optionally pop a browser tab once up."""
    import uvicorn

    if open_url is not None:
        import threading
        import webbrowser

        threading.Timer(1.0, lambda: webbrowser.open(open_url)).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")
