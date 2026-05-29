"""Authentication injection. NEVER automates login — only injects what user supplies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AuthConfig:
    cookies: str | None = None
    storage_state_path: Path | None = None
    basic_auth: tuple[str, str] | None = None


def load(config: AuthConfig) -> dict[str, str]:
    """Return headers/cookies dict to attach to httpx. Phase 3."""
    raise NotImplementedError
