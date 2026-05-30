// Pure reducer for live-mode LiveOps. Mutates and returns the in-memory
// SiteGraph so the /live page can fold the WS op stream into graph state.

import type { SiteGraph, LiveOp } from '../types';

export function applyLiveOp(graph: SiteGraph, op: LiveOp): SiteGraph {
	switch (op.op) {
		case 'add_node': {
			if (!graph.nodes.some((n) => n.template === op.node.template)) {
				graph.nodes.push(op.node);
			}
			break;
		}
		case 'add_edge': {
			const exists = graph.edges.some(
				(e) => e.source === op.edge.source && e.target === op.edge.target
			);
			if (!exists) graph.edges.push(op.edge);
			break;
		}
		case 'visit': {
			const n = graph.nodes.find((x) => x.template === op.template);
			if (n) {
				n.state = 'visited';
				n.visit_count += 1;
				n.last_visited_at = op.at;
				if (!n.url_samples.includes(op.url)) n.url_samples.push(op.url);
			}
			break;
		}
		case 'current': {
			for (const n of graph.nodes) {
				if (n.template === op.template) n.state = 'current';
				else if (n.state === 'current') n.state = 'visited';
			}
			break;
		}
	}
	return graph;
}

export function applyLiveOps(graph: SiteGraph, ops: LiveOp[]): SiteGraph {
	for (const op of ops) applyLiveOp(graph, op);
	return graph;
}
