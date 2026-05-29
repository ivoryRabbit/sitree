// Cytoscape adapter — converts SiteGraph (backend schema) into cytoscape elements
// and applies a consistent style for sitree's node states + labels.

import type { Core, ElementDefinition, StylesheetJson } from 'cytoscape';
import type { SiteGraph, NodeState, PageType } from '../types';

export const LABEL_COLORS: Record<string, string> = {
	Home: '#2563eb',
	Search: '#0891b2',
	PLP: '#16a34a',
	PDP: '#65a30d',
	Article: '#9333ea',
	Auth: '#dc2626',
	Other: '#64748b'
};

function nodeColor(label: PageType | null): string {
	return label ? LABEL_COLORS[label] ?? LABEL_COLORS.Other : LABEL_COLORS.Other;
}

function nodeBorderStyle(state: NodeState): string {
	return state === 'discovered' ? 'dashed' : 'solid';
}

export interface LegendEntry {
	label: string;
	color: string;
	count: number;
}

/** Page-type counts for labels actually present in the graph, in canonical order. */
export function legend(graph: SiteGraph): LegendEntry[] {
	const counts = new Map<string, number>();
	for (const n of graph.nodes) {
		const key = n.label ?? 'Other';
		counts.set(key, (counts.get(key) ?? 0) + 1);
	}
	return Object.keys(LABEL_COLORS)
		.filter((k) => counts.has(k))
		.map((k) => ({ label: k, color: LABEL_COLORS[k], count: counts.get(k)! }));
}

export function toElements(graph: SiteGraph): ElementDefinition[] {
	const nodes: ElementDefinition[] = graph.nodes.map((n) => ({
		data: {
			id: n.template,
			label: n.template,
			pageType: n.label ?? 'Other',
			state: n.state,
			depth: n.depth,
			urlSamples: n.url_samples,
			color: nodeColor(n.label),
			borderStyle: nodeBorderStyle(n.state),
			isCurrent: n.state === 'current' ? 1 : 0
		}
	}));

	const edges: ElementDefinition[] = graph.edges.map((e, i) => ({
		data: {
			id: `e${i}`,
			source: e.source,
			target: e.target,
			count: e.count,
			anchor: e.anchor_texts[0] ?? ''
		}
	}));

	return [...nodes, ...edges];
}

export const stylesheet: StylesheetJson = [
	{
		selector: 'node',
		style: {
			'background-color': 'data(color)',
			'border-color': 'data(color)',
			'border-width': 2,
			'border-style': 'data(borderStyle)' as unknown as 'solid',
			label: 'data(label)',
			color: '#0f172a',
			'font-size': 10,
			'text-valign': 'bottom',
			'text-margin-y': 6,
			'text-wrap': 'wrap',
			'text-max-width': '140px',
			width: 22,
			height: 22
		}
	},
	{
		selector: 'node[isCurrent = 1]',
		style: {
			'background-color': '#fde047',
			'border-color': '#ca8a04',
			width: 30,
			height: 30
		}
	},
	{
		selector: 'edge',
		style: {
			width: 'mapData(count, 1, 10, 1, 4)' as unknown as number,
			'line-color': '#cbd5e1',
			'target-arrow-color': '#cbd5e1',
			'target-arrow-shape': 'triangle',
			'curve-style': 'bezier'
		}
	}
];

export const defaultLayout = {
	name: 'breadthfirst',
	directed: true,
	padding: 24,
	spacingFactor: 1.2,
	animate: false
};

export type CytoscapeInstance = Core;
