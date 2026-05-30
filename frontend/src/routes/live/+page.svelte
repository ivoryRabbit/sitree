<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import cytoscape from 'cytoscape';
	import type { Core } from 'cytoscape';
	import {
		toElements,
		toNodeElement,
		toEdgeElement,
		edgeId,
		stylesheet,
		defaultLayout,
		legend
	} from '$lib/graph/cytoscape';
	import { applyLiveOps } from '$lib/graph/live';
	import type { SiteGraph, LiveOp } from '$lib/types';

	let container: HTMLDivElement;
	let graph: SiteGraph = $state({ root: '', nodes: [], edges: [], meta: null });
	let connected = $state(false);
	let cy: Core | undefined;
	let ws: WebSocket | undefined;

	const legendItems = $derived(legend(graph));

	function relayout() {
		cy?.layout(defaultLayout).run();
	}

	function applyToCy(ops: LiveOp[]) {
		if (!cy) return;
		let structureChanged = false;
		for (const op of ops) {
			if (op.op === 'add_node') {
				if (cy.getElementById(op.node.template).empty()) {
					cy.add(toNodeElement(op.node));
					structureChanged = true;
				}
			} else if (op.op === 'add_edge') {
				const id = edgeId(op.edge.source, op.edge.target);
				if (cy.getElementById(id).empty()) {
					cy.add(toEdgeElement(op.edge));
					structureChanged = true;
				}
			}
		}
		// Refresh node visuals (state/current) from the folded graph state.
		for (const n of graph.nodes) {
			const el = cy.getElementById(n.template);
			if (el.nonempty()) {
				el.data('borderStyle', n.state === 'discovered' ? 'dashed' : 'solid');
				el.data('isCurrent', n.state === 'current' ? 1 : 0);
			}
		}
		if (structureChanged) relayout();
	}

	function connect() {
		const proto = location.protocol === 'https:' ? 'wss' : 'ws';
		ws = new WebSocket(`${proto}://${location.host}/api/live`);
		ws.onopen = () => (connected = true);
		ws.onclose = () => (connected = false);
		ws.onmessage = (evt) => {
			const ops = JSON.parse(evt.data) as LiveOp[];
			graph = applyLiveOps(graph, ops);
			applyToCy(ops);
		};
	}

	onMount(async () => {
		try {
			const res = await fetch('/api/graph');
			if (res.ok) graph = (await res.json()) as SiteGraph;
		} catch {
			// no snapshot yet — start empty
		}
		cy = cytoscape({ container, elements: toElements(graph), style: stylesheet, layout: defaultLayout });
		connect();
	});

	onDestroy(() => {
		ws?.close();
		cy?.destroy();
	});
</script>

<header>
	<div class="title">
		<h1>sitree <span class="badge" class:on={connected}>{connected ? 'live' : 'offline'}</span></h1>
		<p class="subtitle">{graph.root || 'waiting for navigation…'} — {graph.nodes.length} nodes / {graph.edges.length} edges</p>
	</div>
	<ul class="legend">
		{#each legendItems as item (item.label)}
			<li><span class="swatch" style="background:{item.color}"></span>{item.label} <span class="count">{item.count}</span></li>
		{/each}
	</ul>
</header>

<main>
	<div class="graph" bind:this={container}></div>
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
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.badge {
		font-size: 0.65rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		padding: 0.1rem 0.4rem;
		border-radius: 999px;
		background: #e2e8f0;
		color: #64748b;
	}
	.badge.on {
		background: #dcfce7;
		color: #16a34a;
	}
	.subtitle {
		margin: 0.25rem 0 0;
		font-size: 0.8rem;
		color: #64748b;
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
	main {
		height: calc(100vh - 60px);
	}
	.graph {
		width: 100%;
		height: 100%;
		background: white;
	}
</style>
