"""CaptureBridge protocol — common interface for live exploration capture backends.

Implementations:
  - PlaywrightBridge (Phase 5): sitree launches Chromium
  - CdpBridge       (Phase 6): attach to user's Chrome via remote-debugging-port
  - ExtensionBridge (Phase 7+): receive events from a browser extension
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from sitree.schema import VisitEvent


class CaptureBridge(Protocol):
    async def start(self, seed_url: str) -> None: ...
    def events(self) -> AsyncIterator[VisitEvent]: ...
    async def stop(self) -> None: ...
