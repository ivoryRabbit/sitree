"""Classifier tests — no network. The LLM is replaced by a fake Labeler."""

from __future__ import annotations

import pytest

from sitree.core.classifier import (
    AnthropicLabeler,
    GroupInput,
    LabelCache,
    classify_groups,
    coerce_label,
    heuristic_label,
)


# --- Stage 1: heuristics -------------------------------------------------------


@pytest.mark.parametrize(
    "template,expected",
    [
        ("/", "Home"),
        ("", "Home"),
        ("/login", "Auth"),
        ("/sign-up", "Auth"),
        ("/account/settings", "Auth"),
        ("/search", "Search"),
        ("/results?q=*", "Search"),
        ("/product/{id}", "PDP"),
        ("/p/{id}", "PDP"),
        ("/blog/{id}", "Article"),
        ("/news", "Article"),
        ("/category/{id}", "PLP"),
        ("/collections", "PLP"),
    ],
)
def test_heuristic_label_confident_cases(template: str, expected: str) -> None:
    assert heuristic_label(template) == expected


@pytest.mark.parametrize("template", ["/about", "/{id}/foo.html", "/contact", "/x/y/z"])
def test_heuristic_label_ambiguous_returns_none(template: str) -> None:
    assert heuristic_label(template) is None


# --- label parsing -------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("PDP", "PDP"),
        ("  Article\n", "Article"),
        ("`Home`", "Home"),
        ("The label is Search.", "Search"),
        ("totally unknown", "Other"),
        ("", "Other"),
    ],
)
def test_coerce_label(text: str, expected: str) -> None:
    assert coerce_label(text) == expected


# --- Stage 2 orchestration -----------------------------------------------------


class CountingLabeler:
    """Fake Labeler: records calls, returns a fixed label."""

    def __init__(self, label: str = "Other") -> None:
        self.calls: list[str] = []
        self._label = label

    async def __call__(self, group: GroupInput) -> str:
        self.calls.append(group.template)
        return self._label


async def test_heuristic_groups_never_hit_the_llm() -> None:
    labeler = CountingLabeler("PDP")
    groups = [GroupInput("/"), GroupInput("/login"), GroupInput("/product/{id}")]
    out = await classify_groups(groups, labeler=labeler)
    assert out == {"/": "Home", "/login": "Auth", "/product/{id}": "PDP"}
    assert labeler.calls == []  # all resolved by heuristics


async def test_one_llm_call_per_ambiguous_group() -> None:
    labeler = CountingLabeler("Article")
    groups = [GroupInput("/about"), GroupInput("/team"), GroupInput("/")]
    out = await classify_groups(groups, labeler=labeler)
    # Two ambiguous templates -> exactly two calls, one each.
    assert sorted(labeler.calls) == ["/about", "/team"]
    assert out["/about"] == "Article" and out["/team"] == "Article"
    assert out["/"] == "Home"


async def test_cache_skips_llm_on_second_run(tmp_path) -> None:
    groups = [GroupInput("/about")]

    first = CountingLabeler("Article")
    out1 = await classify_groups(groups, labeler=first, cache_dir=tmp_path)
    assert first.calls == ["/about"]
    assert out1["/about"] == "Article"
    assert (tmp_path / "labels.json").exists()

    # Second run: cache hit -> no LLM call, same answer.
    second = CountingLabeler("Other")
    out2 = await classify_groups(groups, labeler=second, cache_dir=tmp_path)
    assert second.calls == []
    assert out2["/about"] == "Article"


def test_label_cache_ignores_invalid_entries(tmp_path) -> None:
    (tmp_path / "labels.json").write_text('{"/x": "NotALabel", "/y": "PDP"}')
    cache = LabelCache(tmp_path)
    assert cache.get("/x") is None
    assert cache.get("/y") == "PDP"


# --- AnthropicLabeler with a fake client (verifies request shape) --------------


class _Block:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)]


class FakeMessages:
    def __init__(self) -> None:
        self.last_kwargs: dict | None = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _Resp("PDP")


class FakeClient:
    def __init__(self) -> None:
        self.messages = FakeMessages()


async def test_anthropic_labeler_uses_prompt_caching_and_parses() -> None:
    client = FakeClient()
    labeler = AnthropicLabeler(client, model="claude-test", system_prompt="SYS")
    label = await labeler(GroupInput("/p/x", sample_urls=["https://x.com/p/x"], title="Widget"))

    assert label == "PDP"
    kw = client.messages.last_kwargs
    assert kw is not None
    assert kw["model"] == "claude-test"
    # system prompt sent as a cached block
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kw["system"][0]["text"] == "SYS"
    # group details reach the user message
    assert "/p/x" in kw["messages"][0]["content"]
    assert "Widget" in kw["messages"][0]["content"]
