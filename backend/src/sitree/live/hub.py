"""LiveHub: in-process fan-out of LiveOp batches to connected WebSocket clients."""

from __future__ import annotations

import asyncio

from sitree.schema import LiveOp


class LiveHub:
    """Each subscriber gets its own queue; publish() pushes an op batch to all.

    Queues are unbounded — live navigation is human-paced, so backpressure isn't a
    concern at MVP scale.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[list[LiveOp]]] = set()

    def subscribe(self) -> asyncio.Queue[list[LiveOp]]:
        queue: asyncio.Queue[list[LiveOp]] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[list[LiveOp]]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, ops: list[LiveOp]) -> None:
        if not ops:
            return
        for queue in list(self._subscribers):
            queue.put_nowait(ops)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
