// Mirror of backend/src/sitree/schema.py — keep in sync.

export type PageType =
  | 'Home'
  | 'Search'
  | 'PDP'
  | 'PLP'
  | 'Article'
  | 'Auth'
  | 'Other';

export type NodeState = 'discovered' | 'visited' | 'current';

export type EdgePosition = 'nav' | 'main' | 'footer' | 'other';

export interface Node {
	template: string;
	url_samples: string[];
	depth: number;
	status_codes: number[];
	label: PageType | null;
	state: NodeState;
	visit_count: number;
	last_visited_at: string | null; // ISO 8601
}

export interface Edge {
	source: string;
	target: string;
	anchor_texts: string[];
	count: number;
	position: EdgePosition;
}

export interface CrawlMeta {
	ran_at: string;
	seed_url: string;
	max_pages: number;
	max_depth: number;
	robots_respected: boolean;
	user_agent: string;
}

export interface SiteGraph {
	root: string;
	nodes: Node[];
	edges: Edge[];
	meta: CrawlMeta | null;
}

// Live mode op stream (Phase 5+)
export type LiveOp =
	| { op: 'visit'; template: string; url: string; at: string }
	| { op: 'add_node'; node: Node }
	| { op: 'add_edge'; edge: Edge }
	| { op: 'current'; template: string };
