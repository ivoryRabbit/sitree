"""Phase 6 capture: attach to a user's already-running Chrome over CDP.

The user starts Chrome with --remote-debugging-port (see `sitree live --capture
cdp` guidance); sitree connects with Playwright's connect_over_cdp and observes
their real navigation — real profile, real login sessions. Same VisitEvent
stream as the launcher bridge, so the graph/WS code is identical.
"""

from __future__ import annotations

import asyncio

from sitree.live.playwright_bridge import OnEvent, observe_page


class CdpLiveBridge:
    def __init__(self, *, endpoint: str = "http://localhost:9222") -> None:
        self._endpoint = endpoint

    async def run(self, seed_url: str, on_event: OnEvent) -> None:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(self._endpoint)
            # Use the existing default context/page if present; else open one.
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            closed = await observe_page(page, on_event)
            # Don't force-navigate the user's tab unless it's blank.
            if seed_url and (not page.url or page.url == "about:blank"):
                await page.goto(seed_url)
            await closed.wait()


def cdp_help(endpoint: str = "http://localhost:9222") -> str:
    """User guidance for starting Chrome with remote debugging enabled."""
    port = endpoint.rsplit(":", 1)[-1]
    return (
        "To use --capture cdp, start Chrome with remote debugging first:\n"
        "  macOS:   /Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
        f"--remote-debugging-port={port} --user-data-dir=/tmp/sitree-chrome\n"
        f"  Linux:   google-chrome --remote-debugging-port={port} --user-data-dir=/tmp/sitree-chrome\n"
        f"  Windows: chrome.exe --remote-debugging-port={port} --user-data-dir=%TEMP%\\sitree-chrome\n"
        f"Then run: sitree live <url> --capture cdp\n"
        "(A separate --user-data-dir avoids clashing with your normal Chrome session.)"
    )


# Kept for symmetry with PlaywrightLiveBridge; CDP attach has no extra teardown.
async def _noop() -> None:  # pragma: no cover
    await asyncio.sleep(0)
