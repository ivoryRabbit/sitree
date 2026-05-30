"""Phase 5 capture: sitree launches a Chromium window via Playwright and observes
the user's navigation, emitting a VisitEvent per page (incl. SPA pushState).

Playwright is imported lazily; this module is import-safe without a browser.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime

from sitree.schema import VisitEvent

OnEvent = Callable[[VisitEvent], Awaitable[None]]

# Wrap history.pushState/replaceState so client-side route changes (SPAs) also
# notify the backend via an exposed binding.
_PUSHSTATE_HOOK = """
(() => {
  const fire = () => { try { window.__sitree_nav(location.href); } catch (e) {} };
  const wrap = (fn) => function (...args) { const r = fn.apply(this, args); fire(); return r; };
  history.pushState = wrap(history.pushState);
  history.replaceState = wrap(history.replaceState);
  window.addEventListener('popstate', fire);
})();
"""


class PlaywrightLiveBridge:
    """Opens a Chromium window and streams VisitEvents to `on_event` until the
    user closes the window (or the browser disconnects)."""

    def __init__(
        self,
        *,
        storage_state: object | None = None,
        headless: bool = False,
        timeout: float = 20.0,
    ) -> None:
        self._storage_state = storage_state
        self._headless = headless
        self._timeout_ms = timeout * 1000

    async def run(self, seed_url: str, on_event: OnEvent) -> None:
        from playwright.async_api import async_playwright

        last_url: dict[str, str | None] = {"value": None}

        async def emit(url: str) -> None:
            if not url or url == last_url["value"]:
                return
            referrer = last_url["value"]
            last_url["value"] = url
            links: list[str] = []
            try:
                links = await page.eval_on_selector_all("a[href]", "els => els.map((e) => e.href)")
            except Exception:
                pass
            await on_event(VisitEvent(url=url, at=datetime.now(), referrer=referrer, links=links))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self._headless)
            ctx_kwargs: dict[str, object] = {}
            if self._storage_state is not None:
                ctx_kwargs["storage_state"] = str(self._storage_state)
            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()

            await page.expose_binding(
                "__sitree_nav", lambda _source, url: asyncio.create_task(emit(url))
            )
            await page.add_init_script(_PUSHSTATE_HOOK)
            page.on(
                "framenavigated",
                lambda frame: asyncio.create_task(emit(frame.url))
                if frame is page.main_frame
                else None,
            )

            closed = asyncio.Event()
            page.on("close", lambda: closed.set())
            browser.on("disconnected", lambda: closed.set())

            await page.goto(seed_url, timeout=self._timeout_ms)
            await closed.wait()
