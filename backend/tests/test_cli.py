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

    def fake(seed: str, config: object, *, auth: object = None, classify: object = None) -> SiteGraph:
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


def test_crawl_classify_flag_off_by_default(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake(seed, config, *, auth=None, classify=None):
        captured["classify"] = classify
        captured["auth"] = auth
        return SiteGraph(root=seed)

    monkeypatch.setattr(cli_module, "run_crawl_sync", fake)
    out = tmp_path / "x.json"
    runner.invoke(app, ["crawl", "https://example.com", "-o", str(out)])
    assert captured["classify"].enabled is False

    runner.invoke(app, ["crawl", "https://example.com", "-o", str(out), "--classify", "--cache", str(tmp_path)])
    assert captured["classify"].enabled is True
    assert captured["classify"].cache_dir == tmp_path


def test_auth_zone_only_requires_credentials(stub_run_crawl, tmp_path) -> None:
    out = tmp_path / "x.json"
    result = runner.invoke(app, ["crawl", "https://example.com", "-o", str(out), "--auth-zone-only"])
    assert result.exit_code == 2
    assert "needs credentials" in result.output
    assert stub_run_crawl == []  # never crawled


def test_auth_zone_only_runs_two_crawls(stub_run_crawl, tmp_path) -> None:
    out = tmp_path / "x.json"
    result = runner.invoke(
        app,
        ["crawl", "https://example.com", "-o", str(out), "--auth-zone-only", "--cookies", "a=b"],
    )
    assert result.exit_code == 0, result.output
    assert len(stub_run_crawl) == 2  # anon + authenticated
    assert out.exists()


def test_live_rejects_unknown_capture() -> None:
    result = runner.invoke(app, ["live", "https://example.com", "--capture", "cdp"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.output


def test_live_invokes_runner_for_playwright(monkeypatch) -> None:
    import sitree.live.runner as runner_module

    captured: dict[str, object] = {}

    def fake_run_live_sync(seed, *, port=8765, storage_state=None, **kw):
        captured.update(seed=seed, port=port)

    monkeypatch.setattr(runner_module, "run_live_sync", fake_run_live_sync)
    result = runner.invoke(app, ["live", "https://example.com", "--port", "9100"])
    assert result.exit_code == 0, result.output
    assert captured == {"seed": "https://example.com", "port": 9100}


def test_view_requires_existing_file(tmp_path) -> None:
    result = runner.invoke(app, ["view", str(tmp_path / "missing.json")])
    assert result.exit_code != 0


def test_view_serves_graph(tmp_path, monkeypatch) -> None:
    import sitree.server as server_module

    served: dict[str, object] = {}

    def fake_serve(app_obj, *, host, port, open_url=None) -> None:
        served.update(host=host, port=port, open_url=open_url, app=app_obj)

    # Pretend a frontend build exists, and don't actually start uvicorn.
    monkeypatch.setattr(server_module, "find_frontend_build", lambda: tmp_path)
    monkeypatch.setattr(server_module, "serve", fake_serve)

    p = tmp_path / "graph.json"
    p.write_text('{"root": "https://x.com", "nodes": [], "edges": []}')
    result = runner.invoke(app, ["view", str(p), "--port", "9999", "--no-open"])

    assert result.exit_code == 0, result.output
    assert served["port"] == 9999
    assert served["open_url"] is None  # --no-open


def test_view_errors_without_frontend_build(tmp_path, monkeypatch) -> None:
    import sitree.server as server_module

    monkeypatch.setattr(server_module, "find_frontend_build", lambda: None)
    p = tmp_path / "graph.json"
    p.write_text('{"root": "x"}')
    result = runner.invoke(app, ["view", str(p)])
    assert result.exit_code == 1
    assert "frontend build not found" in result.output


def test_report_generates_html(tmp_path) -> None:
    graph_json = tmp_path / "g.json"
    graph_json.write_text(
        '{"root":"https://x.com","nodes":[{"template":"/","url_samples":["https://x.com/"]}],"edges":[]}'
    )
    out = tmp_path / "report.html"
    result = runner.invoke(app, ["report", str(graph_json), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_text().startswith("<!doctype html>")
