import { describe, it, expect } from 'vitest';
import { toElements, legend, LABEL_COLORS } from './cytoscape';
import type { SiteGraph, Node, PageType, NodeState } from '../types';

function node(template: string, opts: Partial<Node> = {}): Node {
	return {
		template,
		url_samples: [],
		depth: 0,
		status_codes: [],
		label: null,
		state: 'discovered',
		visit_count: 0,
		last_visited_at: null,
		...opts
	};
}

function graph(nodes: Node[], edges: SiteGraph['edges'] = []): SiteGraph {
	return { root: 'https://x.com', nodes, edges, meta: null };
}

describe('toElements', () => {
	it('maps a node to a cytoscape element with id and label color', () => {
		const els = toElements(graph([node('/', { label: 'Home' })]));
		expect(els).toHaveLength(1);
		expect(els[0].data.id).toBe('/');
		expect(els[0].data.color).toBe(LABEL_COLORS.Home);
		expect(els[0].data.pageType).toBe('Home');
	});

	it('falls back to the Other color for an unlabeled node', () => {
		const els = toElements(graph([node('/x')]));
		expect(els[0].data.color).toBe(LABEL_COLORS.Other);
		expect(els[0].data.pageType).toBe('Other');
	});

	it('uses a dashed border for discovered and solid otherwise', () => {
		const els = toElements(
			graph([
				node('/a', { state: 'discovered' as NodeState }),
				node('/b', { state: 'visited' as NodeState })
			])
		);
		const byId = Object.fromEntries(els.map((e) => [e.data.id, e.data]));
		expect(byId['/a'].borderStyle).toBe('dashed');
		expect(byId['/b'].borderStyle).toBe('solid');
	});

	it('flags the current node', () => {
		const els = toElements(
			graph([node('/a', { state: 'current' as NodeState }), node('/b')])
		);
		const byId = Object.fromEntries(els.map((e) => [e.data.id, e.data]));
		expect(byId['/a'].isCurrent).toBe(1);
		expect(byId['/b'].isCurrent).toBe(0);
	});

	it('maps edges with a stable id, count and first anchor', () => {
		const els = toElements(
			graph(
				[node('/'), node('/about')],
				[{ source: '/', target: '/about', anchor_texts: ['About', 'About us'], count: 3, position: 'nav' }]
			)
		);
		const edge = els.find((e) => e.data.id === 'e0');
		expect(edge?.data.source).toBe('/');
		expect(edge?.data.target).toBe('/about');
		expect(edge?.data.count).toBe(3);
		expect(edge?.data.anchor).toBe('About');
	});

	it('handles an edge with no anchor text', () => {
		const els = toElements(
			graph([node('/'), node('/x')], [{ source: '/', target: '/x', anchor_texts: [], count: 1, position: 'other' }])
		);
		expect(els.find((e) => e.data.id === 'e0')?.data.anchor).toBe('');
	});
});

describe('legend', () => {
	it('counts labels present and orders them canonically', () => {
		const g = graph([
			node('/', { label: 'Home' }),
			node('/p/1', { label: 'PDP' as PageType }),
			node('/p/2', { label: 'PDP' as PageType }),
			node('/x') // null -> Other
		]);
		expect(legend(g)).toEqual([
			{ label: 'Home', color: LABEL_COLORS.Home, count: 1 },
			{ label: 'PDP', color: LABEL_COLORS.PDP, count: 2 },
			{ label: 'Other', color: LABEL_COLORS.Other, count: 1 }
		]);
	});

	it('omits labels with no nodes', () => {
		const labels = legend(graph([node('/', { label: 'Home' })])).map((e) => e.label);
		expect(labels).toEqual(['Home']);
		expect(labels).not.toContain('Search');
	});

	it('returns an empty array for an empty graph', () => {
		expect(legend(graph([]))).toEqual([]);
	});
});
