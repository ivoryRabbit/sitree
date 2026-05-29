from __future__ import annotations

from pathlib import Path

import typer

from sitree.core.crawler import CrawlConfig
from sitree.pipeline import run_crawl_sync
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
    cookies: str | None = typer.Option(None, help='Cookie header string, e.g. "k=v; k2=v2".'),
    storage_state: Path | None = typer.Option(None, help="Playwright storage_state.json path."),
    cache: Path | None = typer.Option(None, help="Cache directory for LLM/HTTP results."),
) -> None:
    """Batch-crawl a site and emit a SiteGraph JSON."""
    config = CrawlConfig(
        max_depth=max_depth,
        max_pages=max_pages,
        concurrency=concurrency,
        respect_robots=respect_robots,
    )
    _ = cookies, storage_state, cache  # consumed in later phases
    typer.echo(f"[crawl] seed={url} max_pages={max_pages} max_depth={max_depth}")
    graph = run_crawl_sync(url, config)
    output.write_text(to_json(graph), encoding="utf-8")
    typer.echo(f"[crawl] wrote {output} ({len(graph.nodes)} nodes, {len(graph.edges)} edges)")


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
    _ = url, capture, port, auto_expand, storage_state
    _not_implemented("live", "Phase 5")


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
