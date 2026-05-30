"""Wire the live capture bridge to the WS server: run both in one event loop.

The Playwright window streams VisitEvents → LiveSession folds them into the graph
→ LiveHub pushes the resulting LiveOps to the dashboard over WebSocket.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sitree.live.hub import LiveHub
from sitree.live.playwright_bridge import PlaywrightLiveBridge
from sitree.live.session import LiveSession
from sitree.schema import VisitEvent
from sitree.server import create_app


async def run_live(
    seed: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    storage_state: Path | None = None,
    headless: bool = False,
    open_dashboard: bool = True,
) -> None:
    import uvicorn

    session = LiveSession(root=seed)
    hub = LiveHub()
    app = create_app(graph_provider=session.snapshot, hub=hub)

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    bridge = PlaywrightLiveBridge(storage_state=storage_state, headless=headless)

    async def on_event(event: VisitEvent) -> None:
        await hub.publish(session.visit(event))

    server_task = asyncio.create_task(server.serve())
    if open_dashboard:
        _open_later(f"http://{host}:{port}/live")
    try:
        await bridge.run(seed, on_event)
    finally:
        server.should_exit = True
        await server_task


def _open_later(url: str, delay: float = 1.0) -> None:
    import threading
    import webbrowser

    threading.Timer(delay, lambda: webbrowser.open(url)).start()


def run_live_sync(
    seed: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    storage_state: Path | None = None,
    headless: bool = False,
    open_dashboard: bool = True,
) -> None:
    asyncio.run(
        run_live(
            seed,
            host=host,
            port=port,
            storage_state=storage_state,
            headless=headless,
            open_dashboard=open_dashboard,
        )
    )
