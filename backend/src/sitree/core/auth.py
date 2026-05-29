"""Authentication injection. NEVER automates login — only injects what the user
supplies (cookie header, Playwright storage_state, HTTP Basic). See
docs/auth-strategies.md.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit


@dataclass
class AuthConfig:
    cookies: str | None = None  # raw Cookie header, e.g. "session=abc; token=xyz"
    storage_state_path: Path | None = None  # Playwright storage_state.json
    basic_auth: tuple[str, str] | None = None  # (user, password)


@dataclass
class HttpAuth:
    """Resolved credentials to attach to an httpx client."""

    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.headers and not self.cookies


def parse_cookie_header(raw: str) -> dict[str, str]:
    """Parse a `k=v; k2=v2` Cookie header into a dict."""
    jar: SimpleCookie = SimpleCookie()
    jar.load(raw)
    return {key: morsel.value for key, morsel in jar.items()}


def load_storage_state(path: Path) -> dict:
    """Read a Playwright storage_state.json. Raises on malformed JSON."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cookies_from_storage_state(state: dict, *, host: str | None = None) -> dict[str, str]:
    """Extract name→value cookies from a storage_state, optionally limited to the
    cookies whose domain matches `host` (so we don't leak unrelated-domain cookies)."""
    out: dict[str, str] = {}
    for cookie in state.get("cookies", []):
        name, value = cookie.get("name"), cookie.get("value")
        if not name:
            continue
        if host is not None and not _domain_matches(cookie.get("domain", ""), host):
            continue
        out[name] = value or ""
    return out


def _domain_matches(cookie_domain: str, host: str) -> bool:
    cookie_domain = cookie_domain.lstrip(".").lower()
    host = host.lower()
    return bool(cookie_domain) and (host == cookie_domain or host.endswith("." + cookie_domain))


def to_http_auth(config: AuthConfig, *, seed_url: str | None = None) -> HttpAuth:
    """Resolve an AuthConfig into headers/cookies for httpx.

    storage_state cookies are filtered to the seed's host when `seed_url` is given.
    """
    auth = HttpAuth()
    if config.basic_auth is not None:
        user, password = config.basic_auth
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        auth.headers["Authorization"] = f"Basic {token}"
    if config.cookies:
        auth.cookies.update(parse_cookie_header(config.cookies))
    if config.storage_state_path is not None:
        host = urlsplit(seed_url).hostname if seed_url else None
        state = load_storage_state(config.storage_state_path)
        auth.cookies.update(cookies_from_storage_state(state, host=host))
    return auth


def parse_basic_auth(raw: str) -> tuple[str, str]:
    """Split a `user:password` string. Password may itself contain colons."""
    user, sep, password = raw.partition(":")
    if not sep:
        raise ValueError("expected 'user:password'")
    return user, password
