"""CLI surface tests via typer's CliRunner — no real crawling, just argument parsing."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

import sitree.cli as cli_module
from sitree.cli import app
from sitree.schema import SiteGraph

runner = CliRunner()


@pytest.fixture(autouse=True)
def stub_run_crawl(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, object]]:
    """Replace pipeline.run_crawl_sync so CLI tests never touch the network."""
    calls: list[tuple[str, object]] = []

    def fake(seed: str, config: object) -> SiteGraph:
        calls.append((seed, config))
        return SiteGraph(root=seed)

    monkeypatch.setattr(cli_module, "run_crawl_sync", fake)
    return calls


def test_top_level_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("crawl", "view", "live", "report"):
        assert cmd in result.stdout


def test_crawl_requires_url() -> None:
    result = runner.invoke(app, ["crawl"])
    assert result.exit_code != 0


def test_crawl_accepts_url_as_first_positional(stub_run_crawl, tmp_path) -> None:
    out = tmp_path / "out.json"
    result = runner.invoke(app, ["crawl", "https://example.com", "-o", str(out)])
    assert result.exit_code == 0, result.stdout
    assert "https://example.com" in result.stdout
    assert out.exists()
    assert stub_run_crawl[0][0] == "https://example.com"


def test_crawl_passes_options_to_config(stub_run_crawl, tmp_path) -> None:
    out = tmp_path / "x.json"
    result = runner.invoke(
        app,
        ["crawl", "https://example.com", "-o", str(out), "--max-depth", "3", "--ignore-robots"],
    )
    assert result.exit_code == 0, result.stdout
    seed, config = stub_run_crawl[0]
    assert seed == "https://example.com"
    assert config.max_depth == 3
    assert config.respect_robots is False


def test_live_not_implemented_exits_nonzero() -> None:
    # Planned command: must signal not-implemented rather than exit 0 silently.
    result = runner.invoke(app, ["live", "https://example.com"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.output


def test_view_requires_existing_file(tmp_path) -> None:
    result = runner.invoke(app, ["view", str(tmp_path / "missing.json")])
    assert result.exit_code != 0


def test_view_existing_file_not_implemented(tmp_path) -> None:
    # File exists (passes typer's exists=True), but the command itself is unimplemented.
    p = tmp_path / "graph.json"
    p.write_text('{"root": "x"}')
    result = runner.invoke(app, ["view", str(p)])
    assert result.exit_code == 1
    assert "not yet implemented" in result.output
