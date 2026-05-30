"""Single-file static HTML report from a SiteGraph JSON.

Self-contained: the graph data is embedded inline and cytoscape is loaded from a
CDN, so the output is one shareable .html with no local server needed.
"""

from __future__ import annotations

import html
import json

from sitree.core.stats import compute_stats
from sitree.schema import SiteGraph, to_dict

_LABEL_COLORS = {
    "Home": "#2563eb",
    "Search": "#0891b2",
    "PLP": "#16a34a",
    "PDP": "#65a30d",
    "Article": "#9333ea",
    "Auth": "#dc2626",
    "Other": "#64748b",
}

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>sitree — {root}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.2/cytoscape.min.js"></script>
<style>
  body {{ margin:0; font-family:-apple-system,system-ui,sans-serif; background:#f8fafc; color:#0f172a; }}
  header {{ padding:.75rem 1rem; border-bottom:1px solid #e2e8f0; background:#fff; }}
  h1 {{ margin:0; font-size:1.1rem; }}
  .sub {{ margin:.25rem 0 0; font-size:.8rem; color:#64748b; }}
  main {{ display:grid; grid-template-columns:1fr 280px; height:calc(100vh - 58px); }}
  #cy {{ width:100%; height:100%; background:#fff; }}
  aside {{ padding:1rem; border-left:1px solid #e2e8f0; background:#fff; overflow-y:auto; font-size:.85rem; }}
  aside h2 {{ font-size:.8rem; text-transform:uppercase; letter-spacing:.05em; color:#64748b; margin:1rem 0 .4rem; }}
  aside h2:first-child {{ margin-top:0; }}
  .stat {{ display:flex; justify-content:space-between; padding:.15rem 0; }}
  .stat .v {{ font-variant-numeric:tabular-nums; font-weight:600; }}
  .row {{ display:flex; align-items:center; gap:.4rem; padding:.1rem 0; }}
  .swatch {{ width:10px; height:10px; border-radius:2px; }}
  .row .c {{ margin-left:auto; color:#94a3b8; font-variant-numeric:tabular-nums; }}
</style>
</head>
<body>
<header>
  <h1>sitree</h1>
  <p class="sub">{root} — {total_nodes} nodes / {total_edges} edges{ran}</p>
</header>
<main>
  <div id="cy"></div>
  <aside>
    <h2>Overview</h2>
    <div class="stat"><span>Nodes (templates)</span><span class="v">{total_nodes}</span></div>
    <div class="stat"><span>Edges</span><span class="v">{total_edges}</span></div>
    <div class="stat"><span>URL samples</span><span class="v">{total_url_samples}</span></div>
    <div class="stat"><span>Max depth</span><span class="v">{max_depth}</span></div>
    <div class="stat"><span>External links</span><span class="v">{external_links}</span></div>
    <h2>Page types</h2>
    {label_rows}
    <h2>Depth</h2>
    {depth_rows}
  </aside>
</main>
<script>
  const graph = {graph_json};
  const COLORS = {colors_json};
  const els = [];
  for (const n of graph.nodes) els.push({{ data: {{
    id: n.template, label: n.template,
    color: COLORS[n.label] || COLORS.Other,
    border: n.state === 'discovered' ? 'dashed' : 'solid'
  }} }});
  for (const e of graph.edges) els.push({{ data: {{
    id: e.source + '\\u2192' + e.target, source: e.source, target: e.target
  }} }});
  cytoscape({{
    container: document.getElementById('cy'),
    elements: els,
    style: [
      {{ selector: 'node', style: {{
        'background-color': 'data(color)', 'border-color': 'data(color)',
        'border-width': 2, 'border-style': 'data(border)', label: 'data(label)',
        'font-size': 9, 'text-valign': 'bottom', 'text-margin-y': 5,
        'text-wrap': 'wrap', 'text-max-width': '130px', width: 20, height: 20
      }} }},
      {{ selector: 'edge', style: {{
        width: 1, 'line-color': '#cbd5e1', 'target-arrow-color': '#cbd5e1',
        'target-arrow-shape': 'triangle', 'curve-style': 'bezier'
      }} }}
    ],
    layout: {{ name: 'breadthfirst', directed: true, padding: 24, spacingFactor: 1.2 }}
  }});
</script>
</body>
</html>
"""


def _bar_rows(counts: dict, *, colored: bool) -> str:
    rows = []
    for key, value in counts.items():
        label = html.escape(str(key))
        if colored:
            color = _LABEL_COLORS.get(str(key), "#64748b")
            swatch = f'<span class="swatch" style="background:{color}"></span>'
        else:
            swatch = ""
        rows.append(f'<div class="row">{swatch}<span>{label}</span><span class="c">{value}</span></div>')
    return "\n    ".join(rows) or '<div class="row"><span>—</span></div>'


def render_report(graph: SiteGraph) -> str:
    stats = compute_stats(graph)
    ran = ""
    if graph.meta is not None:
        ran = f" — crawled {html.escape(graph.meta.ran_at.isoformat(timespec='seconds'))}"
    return _TEMPLATE.format(
        root=html.escape(graph.root),
        ran=ran,
        total_nodes=stats.total_nodes,
        total_edges=stats.total_edges,
        total_url_samples=stats.total_url_samples,
        max_depth=stats.max_depth,
        external_links=stats.external_links,
        label_rows=_bar_rows(stats.by_label, colored=True),
        depth_rows=_bar_rows({f"depth {k}": v for k, v in stats.by_depth.items()}, colored=False),
        graph_json=json.dumps(to_dict(graph)),
        colors_json=json.dumps(_LABEL_COLORS),
    )
