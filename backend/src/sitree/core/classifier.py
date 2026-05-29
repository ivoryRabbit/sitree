"""Two-stage page classifier: URL pattern heuristics + Claude per template group.

Stage 1 (`heuristic_label`) labels templates whose role is obvious from the URL.
Stage 2 sends each *remaining* (ambiguous) group to Claude — at most ONE call per
template group, never per page (see CLAUDE.md). LLM results are cached to disk so
re-runs skip the call entirely.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from sitree.schema import PageType

DEFAULT_MODEL = "claude-sonnet-4-6"

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "page_classify.md"
_VALID: tuple[PageType, ...] = ("Home", "Search", "PLP", "PDP", "Article", "Auth", "Other")

# A labeler turns one ambiguous group into a single PageType (one LLM call).
Labeler = Callable[["GroupInput"], Awaitable[PageType]]


@dataclass
class GroupInput:
    """One URL-template group handed to the classifier."""

    template: str
    sample_urls: list[str] = field(default_factory=list)
    title: str | None = None
    text_excerpt: str | None = None


# --- Stage 1: URL heuristics ---------------------------------------------------

_AUTH = re.compile(
    r"/(log[-_]?in|sign[-_]?in|sign[-_]?up|register|auth|account|settings|logout|password|profile)\b",
    re.I,
)
_SEARCH = re.compile(r"/(search|results)\b|[?&]q=", re.I)
_PDP = re.compile(r"/(product|products|item|items|p|dp|listing|listings)/\{id\}", re.I)
_ARTICLE = re.compile(r"/(blog|article|articles|news|posts?|story|stories|docs?)\b", re.I)
_PLP = re.compile(
    r"/(category|categories|collection|collections|catalog|products|shop|browse|list|tags?)\b", re.I
)


def heuristic_label(template: str) -> PageType | None:
    """Confident URL-only classification, or None if the role is ambiguous.

    Order matters: Auth/Search are checked before PDP/PLP, and PDP (which needs an
    `{id}` segment) before the broader PLP listing patterns.
    """
    path = template.split("?", 1)[0]
    if path in ("", "/"):
        return "Home"
    if _AUTH.search(template):
        return "Auth"
    if _SEARCH.search(template):
        return "Search"
    if _PDP.search(template):
        return "PDP"
    if _ARTICLE.search(template):
        return "Article"
    if _PLP.search(template):
        return "PLP"
    return None


# --- Stage 2: LLM labeler ------------------------------------------------------


def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _format_user(group: GroupInput) -> str:
    samples = ", ".join(group.sample_urls[:3]) or "(none)"
    return (
        f"URL template: {group.template}\n"
        f"Sample URLs: {samples}\n"
        f"Title: {group.title or '(none)'}\n"
        f"Text: {group.text_excerpt or '(none)'}"
    )


def coerce_label(text: str) -> PageType:
    """Map a model reply to a valid label. Exact match wins; else first label that
    appears in the text; else 'Other'. Robust to stray whitespace/punctuation.
    """
    cleaned = text.strip().strip(".`\"' ")
    for label in _VALID:
        if cleaned.lower() == label.lower():
            return label
    lowered = text.lower()
    for label in _VALID:
        if re.search(rf"\b{label.lower()}\b", lowered):
            return label
    return "Other"


def _extract_text(response: Any) -> str:
    parts = [getattr(b, "text", "") for b in getattr(response, "content", []) if getattr(b, "type", "") == "text"]
    return "".join(parts)


class AnthropicLabeler:
    """Default labeler backed by Claude. The system prompt is sent as a cached
    block so repeated per-group calls reuse it (prompt caching)."""

    def __init__(
        self, client: Any = None, *, model: str = DEFAULT_MODEL, system_prompt: str | None = None
    ) -> None:
        if client is None:
            import anthropic

            client = anthropic.AsyncAnthropic()
        self._client = client
        self._model = model
        self._system = system_prompt or load_system_prompt()

    async def __call__(self, group: GroupInput) -> PageType:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=16,
            system=[{"type": "text", "text": self._system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": _format_user(group)}],
        )
        return coerce_label(_extract_text(response))


# --- Disk cache ----------------------------------------------------------------


class LabelCache:
    """Persists template -> PageType across runs so LLM calls are made once."""

    def __init__(self, cache_dir: Path) -> None:
        self._path = cache_dir / "labels.json"
        self._data: dict[str, str] = {}
        self._dirty = False
        if self._path.exists():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data = loaded
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, template: str) -> PageType | None:
        value = self._data.get(template)
        return cast("PageType", value) if value in _VALID else None

    def set(self, template: str, label: PageType) -> None:
        self._data[template] = label
        self._dirty = True

    def flush(self) -> None:
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._dirty = False


# --- Orchestration -------------------------------------------------------------


async def classify_groups(
    groups: list[GroupInput],
    *,
    labeler: Labeler | None = None,
    cache_dir: Path | None = None,
) -> dict[str, PageType]:
    """Map template -> PageType. Heuristics first, then one LLM call per remaining
    group (cache hits skip the call). The labeler is constructed lazily only if a
    real LLM call is actually needed."""
    cache = LabelCache(cache_dir) if cache_dir is not None else None
    out: dict[str, PageType] = {}
    pending: list[GroupInput] = []

    for group in groups:
        label = heuristic_label(group.template)
        if label is not None:
            out[group.template] = label
            continue
        if cache is not None and (cached := cache.get(group.template)) is not None:
            out[group.template] = cached
            continue
        pending.append(group)

    if pending:
        if labeler is None:
            labeler = AnthropicLabeler()
        for group in pending:  # exactly one LLM call per ambiguous group
            label = await labeler(group)
            out[group.template] = label
            if cache is not None:
                cache.set(group.template, label)

    if cache is not None:
        cache.flush()
    return out
