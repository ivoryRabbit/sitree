"""Phase 5 capture: sitree launches a Chromium window via Playwright and observes navigation."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sitree.schema import VisitEvent


class PlaywrightBridge:
    async def start(self, seed_url: str) -> None:
        raise NotImplementedError

    def events(self) -> AsyncIterator[VisitEvent]:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError
