import { describe, it, expect } from 'vitest';
import { applyLiveOp, applyLiveOps } from './live';
import type { SiteGraph, Node, LiveOp } from '../types';

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

function emptyGraph(): SiteGraph {
	return { root: 'https://x.com', nodes: [], edges: [], meta: null };
}

describe('applyLiveOp', () => {
	it('add_node appends, and is idempotent by template', () => {
		const g = emptyGraph();
		applyLiveOp(g, { op: 'add_node', node: node('/') });
		applyLiveOp(g, { op: 'add_node', node: node('/') });
		expect(g.nodes).toHaveLength(1);
	});

	it('add_edge appends, and is idempotent by endpoints', () => {
		const g = emptyGraph();
		const edge = { source: '/', target: '/a', anchor_texts: [], count: 1, position: 'other' as const };
		applyLiveOp(g, { op: 'add_edge', edge });
		applyLiveOp(g, { op: 'add_edge', edge });
		expect(g.edges).toHaveLength(1);
	});

	it('visit marks the node visited and bumps the count', () => {
		const g: SiteGraph = { ...emptyGraph(), nodes: [node('/p/{id}')] };
		applyLiveOp(g, { op: 'visit', template: '/p/{id}', url: 'https://x.com/p/1', at: '2026-05-30T00:00:00' });
		expect(g.nodes[0].state).toBe('visited');
		expect(g.nodes[0].visit_count).toBe(1);
		expect(g.nodes[0].url_samples).toContain('https://x.com/p/1');
	});

	it('current sets one node current and demotes the prior current', () => {
		const g: SiteGraph = {
			...emptyGraph(),
			nodes: [node('/', { state: 'current' }), node('/a', { state: 'visited' })]
		};
		applyLiveOp(g, { op: 'current', template: '/a' });
		const states = Object.fromEntries(g.nodes.map((n) => [n.template, n.state]));
		expect(states['/a']).toBe('current');
		expect(states['/']).toBe('visited');
	});
});

describe('applyLiveOps', () => {
	it('folds a typical visit batch into the graph', () => {
		const g = emptyGraph();
		const batch: LiveOp[] = [
			{ op: 'add_node', node: node('/', { state: 'current' }) },
			{ op: 'visit', template: '/', url: 'https://x.com/', at: '2026-05-30T00:00:00' },
			{ op: 'current', template: '/' }
		];
		applyLiveOps(g, batch);
		expect(g.nodes).toHaveLength(1);
		expect(g.nodes[0].state).toBe('current');
		expect(g.nodes[0].visit_count).toBe(1);
	});
});
