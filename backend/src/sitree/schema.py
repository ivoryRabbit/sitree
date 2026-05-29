from __future__ import annotations

import json
import types
import typing
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime
from typing import Any, Literal, get_args, get_origin

type PageType = Literal["Home", "Search", "PDP", "PLP", "Article", "Auth", "Other"]
type NodeState = Literal["discovered", "visited", "current"]
type EdgePosition = Literal["nav", "main", "footer", "other"]


@dataclass
class Node:
    template: str
    url_samples: list[str] = field(default_factory=list)
    depth: int = 0
    status_codes: list[int] = field(default_factory=list)
    label: PageType | None = None
    state: NodeState = "discovered"
    visit_count: int = 0
    last_visited_at: datetime | None = None


@dataclass
class Edge:
    source: str
    target: str
    anchor_texts: list[str] = field(default_factory=list)
    count: int = 1
    position: EdgePosition = "other"


@dataclass
class CrawlMeta:
    ran_at: datetime
    seed_url: str
    max_pages: int
    max_depth: int
    robots_respected: bool
    user_agent: str


@dataclass
class SiteGraph:
    root: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    meta: CrawlMeta | None = None


@dataclass
class VisitEvent:
    url: str
    at: datetime
    referrer: str | None = None


LiveOpKind = Literal["visit", "add_node", "add_edge", "current"]


# Live-mode op stream. Single source of truth, mirrored by frontend/src/lib/types.ts.
# The `op` discriminator field matches the TS union exactly.
@dataclass
class VisitOp:
    template: str
    url: str
    at: datetime
    op: Literal["visit"] = "visit"


@dataclass
class AddNodeOp:
    node: Node
    op: Literal["add_node"] = "add_node"


@dataclass
class AddEdgeOp:
    edge: Edge
    op: Literal["add_edge"] = "add_edge"


@dataclass
class CurrentOp:
    template: str
    op: Literal["current"] = "current"


type LiveOp = VisitOp | AddNodeOp | AddEdgeOp | CurrentOp


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return value


def to_dict(graph: SiteGraph) -> dict[str, Any]:
    return _to_jsonable(graph)


def to_json(graph: SiteGraph, *, indent: int | None = 2) -> str:
    return json.dumps(to_dict(graph), indent=indent, ensure_ascii=False)


def _coerce(annotation: Any, value: Any) -> Any:
    if value is None:
        return None
    if annotation is datetime:
        return datetime.fromisoformat(value)
    origin = get_origin(annotation)
    if origin is list:
        (inner,) = get_args(annotation)
        return [_coerce(inner, v) for v in value]
    if origin in (typing.Union, types.UnionType):
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        for arg in non_none:
            try:
                return _coerce(arg, value)
            except Exception:
                continue
        return value
    if is_dataclass(annotation) and isinstance(value, dict):
        hints = typing.get_type_hints(annotation)
        kwargs = {f.name: _coerce(hints[f.name], value[f.name]) for f in fields(annotation) if f.name in value}
        return annotation(**kwargs)
    return value


def from_dict(data: dict[str, Any]) -> SiteGraph:
    return _coerce(SiteGraph, data)


def from_json(text: str) -> SiteGraph:
    return from_dict(json.loads(text))
