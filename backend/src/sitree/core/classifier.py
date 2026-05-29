"""Two-stage page classifier: URL pattern heuristics + Claude per template group."""

from __future__ import annotations

from sitree.schema import PageType


async def classify_groups(groups: dict[str, list[str]]) -> dict[str, PageType]:
    """Map template -> PageType. One LLM call per group max. Phase 2."""
    raise NotImplementedError
