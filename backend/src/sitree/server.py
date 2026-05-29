"""FastAPI server for `sitree view` and (later) `sitree live`.

Routes:
  GET  /api/health    - liveness probe
  GET  /api/graph     - current SiteGraph snapshot (JSON)
  GET  /              - built SvelteKit frontend (static), if available
  WS   /api/live      - real-time LiveOp stream (Phase 5+)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sitree.schema import SiteGraph, to_dict


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
    graph: SiteGraph | None = None, *, static_dir: Path | None = None
) -> FastAPI:
    """Build the FastAPI app. `graph` is served at /api/graph; the frontend build
    (if found) is mounted at /. API routes are registered before the static mount
    so /api/* always takes precedence over the catch-all.
    """
    app = FastAPI(title="sitree")
    graph_payload = to_dict(graph) if graph is not None else None

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/graph")
    async def get_graph() -> JSONResponse:
        if graph_payload is None:
            raise HTTPException(status_code=404, detail="no graph loaded")
        return JSONResponse(graph_payload)

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
