"""Shared fixtures."""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture
def mock_transport() -> httpx.MockTransport:
    """A configurable MockTransport. Override per test by patching .handler."""
    return httpx.MockTransport(lambda req: httpx.Response(404))


@pytest.fixture
def sample_html() -> str:
    return """
    <html><head><title>Example</title></head>
    <body>
      <a href="/about">About</a>
      <a href="/products/42">Product 42</a>
      <a href="https://other.example.com/x">External</a>
      <a href="mailto:noone@example.com">Mail</a>
      <a href="#anchor">Anchor</a>
      <a href="?utm_source=ad">Tracking-only</a>
    </body></html>
    """
