from __future__ import annotations

from pathlib import Path

import typer

from sitree.core.auth import AuthConfig, parse_basic_auth
from sitree.core.crawler import CrawlConfig
from sitree.core.diff import auth_zone_diff
from sitree.pipeline import ClassifyConfig, run_crawl_sync
from sitree.schema import to_json

app = typer.Typer(
    name="sitree",
    help="Visualize a website's link structure as a tree/graph.",
    no_args_is_help=True,
)


def _not_implemented(command: str, phase: str) -> None:
    """Signal a planned-but-unimplemented command: clear message + non-zero exit.

    Returning exit 0 here would make scripts/automation treat the no-op as success.
    """
    typer.secho(
        f"[{command}] not yet implemented (planned for {phase}).",
        fg=typer.colors.YELLOW,
        err=True,
    )
    raise typer.Exit(code=1)


@app.command()
def crawl(
    url: str = typer.Argument(..., help="Seed URL to crawl."),
    output: Path = typer.Option(Path("out.json"), "-o", "--output", help="Output JSON path."),
    max_depth: int = typer.Option(5, help="Max crawl depth from seed."),
    max_pages: int = typer.Option(500, help="Max pages to crawl."),
    concurrency: int = typer.Option(4, help="Max concurrent requests."),
    respect_robots: bool = typer.Option(True, "--respect-robots/--ignore-robots"),
    render: str = typer.Option(
        "never", help="JS render fallback: never | auto | always (needs Playwright)."
    ),
    classify: bool = typer.Option(
        False, "--classify/--no-classify", help="AI-label page types (calls Claude per group)."
    ),
    model: str | None = typer.Option(None, help="Claude model for --classify."),
    cookies: str | None = typer.Option(None, help='Cookie header string, e.g. "k=v; k2=v2".'),
    storage_state: Path | None = typer.Option(
        None, exists=True, help="Playwright storage_state.json path."
    ),
    basic: str | None = typer.Option(None, help='HTTP Basic auth as "user:password".'),
    auth_zone_only: bool = typer.Option(
        False,
        "--auth-zone-only",
        help="Crawl anonymously and authenticated; emit only what auth reveals.",
    ),
    cache: Path | None = typer.Option(None, help="Cache directory for LLM label results."),
) -> None:
    """Batch-crawl a site and emit a SiteGraph JSON."""
    if render not in ("never", "auto", "always"):
        typer.secho(f"[crawl] invalid --render {render!r} (never|auto|always)", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    config = CrawlConfig(
        max_depth=max_depth,
        max_pages=max_pages,
        concurrency=concurrency,
        respect_robots=respect_robots,
        render_mode=render,  # type: ignore[arg-type]
    )
    classify_config = ClassifyConfig(enabled=classify, model=model, cache_dir=cache)
    auth_config = AuthConfig(
        cookies=cookies,
        storage_state_path=storage_state,
        basic_auth=parse_basic_auth(basic) if basic else None,
    )
    authed = any((cookies, storage_state, basic))

    if auth_zone_only and not authed:
        typer.secho(
            "[crawl] --auth-zone-only needs credentials (--cookies/--storage-state/--basic)",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    typer.echo(
        f"[crawl] seed={url} max_pages={max_pages} max_depth={max_depth} "
        f"classify={classify} auth={authed} auth_zone_only={auth_zone_only}"
    )

    if auth_zone_only:
        anon = run_crawl_sync(url, config)
        full = run_crawl_sync(url, config, auth=auth_config, classify=classify_config)
        graph = auth_zone_diff(anon, full)
        typer.echo(
            f"[crawl] auth zone: {len(graph.nodes)} nodes / {len(graph.edges)} edges "
            f"only visible authenticated (anon={len(anon.nodes)}, full={len(full.nodes)})"
        )
    else:
        graph = run_crawl_sync(url, config, auth=auth_config, classify=classify_config)

    output.write_text(to_json(graph), encoding="utf-8")
    labeled = sum(1 for n in graph.nodes if n.label is not None)
    suffix = f", {labeled} labeled" if classify else ""
    typer.echo(
        f"[crawl] wrote {output} ({len(graph.nodes)} nodes, {len(graph.edges)} edges{suffix})"
    )


@app.command()
def view(
    path: Path = typer.Argument(..., exists=True, help="SiteGraph JSON to view."),
    port: int = typer.Option(8765, help="Local port to serve the dashboard on."),
    host: str = typer.Option("127.0.0.1", help="Host/interface to bind."),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open a browser tab."),
) -> None:
    """Serve the static dashboard with the given JSON loaded."""
    from sitree import server
    from sitree.schema import from_json

    build = server.find_frontend_build()
    if build is None:
        typer.secho(
            "[view] frontend build not found — run: cd frontend && npm run build",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1)

    graph = from_json(path.read_text(encoding="utf-8"))
    url = f"http://{host}:{port}/"
    typer.echo(f"[view] serving {path} ({len(graph.nodes)} nodes) at {url}")
    server.serve(server.create_app(graph), host=host, port=port, open_url=url if open_browser else None)


@app.command()
def live(
    url: str = typer.Argument(..., help="Seed URL to start live exploration from."),
    capture: str = typer.Option("playwright", help="Capture bridge: playwright | cdp | extension."),
    port: int = typer.Option(8765, help="Local port for dashboard + WebSocket."),
    auto_expand: bool = typer.Option(False, help="Fetch links of visited pages in the background."),
    storage_state: Path | None = typer.Option(None, help="Playwright storage_state.json path."),
) -> None:
    """Start live exploration mode: open browser, watch the user's navigation, update graph in real time."""
    if capture != "playwright":
        typer.secho(
            f"[live] capture={capture!r} not yet implemented (Phase 6+); use 'playwright'.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1)
    if auto_expand:
        typer.secho("[live] --auto-expand not implemented yet; ignoring.", fg=typer.colors.YELLOW, err=True)

    from sitree.live.runner import run_live_sync

    dashboard = f"http://127.0.0.1:{port}/live"
    typer.echo(f"[live] seed={url} → opening Chromium; dashboard at {dashboard} (close the window to stop)")
    run_live_sync(url, port=port, storage_state=storage_state)


@app.command()
def report(
    path: Path = typer.Argument(..., exists=True, help="SiteGraph JSON."),
    output: Path = typer.Option(Path("report.html"), "-o", "--output", help="Output HTML path."),
) -> None:
    """Generate a single static HTML report from a SiteGraph JSON."""
    _ = path, output
    _not_implemented("report", "Phase 4")


if __name__ == "__main__":
    app()
