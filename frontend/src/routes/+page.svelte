<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import cytoscape from 'cytoscape';
	import type { Core } from 'cytoscape';
	import { toElements, stylesheet, defaultLayout, LABEL_COLORS } from '$lib/graph/cytoscape';
	import type { SiteGraph, Node } from '$lib/types';
	import example from '$lib/example.json';

	let container: HTMLDivElement;
	let selected: Node | null = $state(null);
	// Default to the bundled example so the page also works standalone (`npm run dev`).
	// When served by `sitree view`, the real graph is fetched from the backend below.
	let graph: SiteGraph = $state(example as unknown as SiteGraph);

	async function loadGraph(): Promise<SiteGraph> {
		try {
			const res = await fetch('/api/graph');
			if (res.ok) return (await res.json()) as SiteGraph;
		} catch {
			// No backend (standalone dev) — keep the bundled example.
		}
		return graph;
	}

	let cy: Core | undefined;

	onMount(async () => {
		graph = await loadGraph();

		cy = cytoscape({
			container,
			elements: toElements(graph),
			style: stylesheet,
			layout: defaultLayout
		});

		cy.on('tap', 'node', (evt) => {
			const id = evt.target.id();
			selected = graph.nodes.find((n) => n.template === id) ?? null;
		});

		cy.on('tap', (evt) => {
			if (evt.target === cy) selected = null;
		});
	});

	onDestroy(() => cy?.destroy());

	// Legend: counts per page-type label actually present in the graph,
	// ordered by the canonical LABEL_COLORS key order.
	const legend = $derived.by(() => {
		const counts = new Map<string, number>();
		for (const n of graph.nodes) {
			const key = n.label ?? 'Other';
			counts.set(key, (counts.get(key) ?? 0) + 1);
		}
		return Object.keys(LABEL_COLORS)
			.filter((k) => counts.has(k))
			.map((k) => ({ label: k, color: LABEL_COLORS[k], count: counts.get(k)! }));
	});
</script>

<header>
	<div class="title">
		<h1>sitree</h1>
		<p class="subtitle">{graph.root} — {graph.nodes.length} nodes / {graph.edges.length} edges</p>
	</div>
	<ul class="legend">
		{#each legend as item (item.label)}
			<li>
				<span class="swatch" style="background:{item.color}"></span>
				{item.label} <span class="count">{item.count}</span>
			</li>
		{/each}
	</ul>
</header>

<main>
	<div class="graph" bind:this={container}></div>

	{#if selected}
		<aside class="panel">
			<h2>{selected.template}</h2>
			<dl>
				<dt>label</dt><dd>{selected.label ?? '—'}</dd>
				<dt>state</dt><dd>{selected.state}</dd>
				<dt>depth</dt><dd>{selected.depth}</dd>
				<dt>visits</dt><dd>{selected.visit_count}</dd>
				<dt>samples</dt>
				<dd>
					<ul>
						{#each selected.url_samples.slice(0, 5) as u}
							<li><a href={u} target="_blank" rel="noreferrer">{u}</a></li>
						{/each}
					</ul>
				</dd>
			</dl>
		</aside>
	{/if}
</main>

<style>
	:global(body) {
		margin: 0;
		font-family: -apple-system, system-ui, sans-serif;
		background: #f8fafc;
	}
	header {
		padding: 0.75rem 1rem;
		border-bottom: 1px solid #e2e8f0;
		background: white;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}
	header h1 {
		margin: 0;
		font-size: 1.1rem;
	}
	.legend {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 0.85rem;
		font-size: 0.75rem;
		color: #475569;
	}
	.legend li {
		display: flex;
		align-items: center;
		gap: 0.3rem;
	}
	.swatch {
		width: 10px;
		height: 10px;
		border-radius: 2px;
		display: inline-block;
	}
	.legend .count {
		color: #94a3b8;
		font-variant-numeric: tabular-nums;
	}
	.subtitle {
		margin: 0.25rem 0 0;
		font-size: 0.8rem;
		color: #64748b;
	}
	main {
		display: grid;
		grid-template-columns: 1fr 320px;
		height: calc(100vh - 60px);
	}
	.graph {
		width: 100%;
		height: 100%;
		background: white;
	}
	.panel {
		padding: 1rem;
		border-left: 1px solid #e2e8f0;
		background: white;
		overflow-y: auto;
	}
	.panel h2 {
		margin: 0 0 0.75rem;
		font-size: 0.95rem;
		font-family: ui-monospace, monospace;
		word-break: break-all;
	}
	dl {
		margin: 0;
		display: grid;
		grid-template-columns: 70px 1fr;
		gap: 0.25rem 0.75rem;
		font-size: 0.85rem;
	}
	dt {
		color: #64748b;
	}
	dd {
		margin: 0;
		word-break: break-all;
	}
	ul {
		margin: 0;
		padding-left: 1rem;
	}
</style>
