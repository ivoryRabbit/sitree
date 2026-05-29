"""FastAPI server for `sitree view` and `sitree live`.

Routes:
  GET  /              - serves built frontend (static)
  GET  /api/graph     - current SiteGraph snapshot
  WS   /api/live      - real-time LiveOp stream
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="sitree")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
