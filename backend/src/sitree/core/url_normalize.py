"""URL normalization and template inference.

See docs/url-normalization.md for the full algorithm.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_KEYS: frozenset[str] = frozenset(
    {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "gclid", "fbclid", "mc_cid", "mc_eid", "_ga", "_gl",
        "ref", "referrer", "source",
        "sessionid", "sid", "phpsessid", "jsessionid",
    }
)

IDENTITY_KEYS: frozenset[str] = frozenset({"id", "slug", "page", "category", "q"})

_NUMERIC = re.compile(r"^\d+$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){1,}$")
# Dotted version segments: 3.10, 2.7.18, v1.2 (docs/version-rooted trees).
_VERSION = re.compile(r"^v?\d+(?:\.\d+)+$", re.I)


def _looks_like_id(segment: str) -> bool:
    return bool(
        _NUMERIC.match(segment)
        or _UUID.match(segment)
        or _SLUG.match(segment)
        or _VERSION.match(segment)
    )


def normalize(url: str, base: str | None = None) -> str:
    """Deterministic URL normalization.

    - Resolves relative URLs against `base` if given
    - Lowercases scheme + host
    - Drops default ports (80/443)
    - Drops fragment
    - Removes tracking query keys (utm_*, gclid, …)
    - Sorts remaining query keys alphabetically
    - Collapses path to "/" when empty
    """
    if base is not None:
        url = urljoin(base, url)
    parts = urlsplit(url)

    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo += f":{parts.password}"
        netloc = f"{userinfo}@{netloc}"

    path = parts.path or "/"

    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in TRACKING_KEYS]
    pairs.sort()
    query = urlencode(pairs)

    return urlunsplit((scheme, netloc, path, query, ""))


@dataclass
class TemplateOptions:
    identity_keys: frozenset[str] = IDENTITY_KEYS
    drop_keys: frozenset[str] = TRACKING_KEYS
    min_group_size: int = 5
    extra_drop_keys: frozenset[str] = field(default_factory=frozenset)


def _segment_template(seg: str) -> str:
    return "{id}" if _looks_like_id(seg) else seg


def templatize(urls: list[str], options: TemplateOptions | None = None) -> dict[str, str]:
    """Map each normalized URL → template string.

    Strategy:
      1. Split path into segments. Segments that look like IDs (numeric/UUID/slug/
         dotted-version) become `{id}` in the template.
      2. To avoid over-eagerly templating low-cardinality segments, only collapse
         segments at positions where ≥ min_group_size distinct values appear
         under the same parent prefix.
      3. Query parameters: keep identity keys (with value blanked to `*`), drop
         the rest. (Tracking keys were already removed by normalize().)
    """
    opts = options or TemplateOptions()
    if not urls:
        return {}

    # Pass 1: collect path segments per position
    parsed = [(u, urlsplit(u)) for u in urls]
    seg_lists = [(u, [s for s in parts.path.split("/") if s], parts) for u, parts in parsed]

    # position-keyed cardinality, scoped by parent path so unrelated paths don't pollute
    # key: (parent_template_so_far, position_index) -> set of raw segments
    position_buckets: dict[tuple[str, int], set[str]] = defaultdict(set)
    for _, segs, _ in seg_lists:
        parent = ""
        for i, seg in enumerate(segs):
            position_buckets[(parent, i)].add(seg)
            parent = f"{parent}/{_segment_template(seg)}"

    # Pass 2: build template per URL
    out: dict[str, str] = {}
    for url, segs, parts in seg_lists:
        parent = ""
        templated_segs: list[str] = []
        for i, seg in enumerate(segs):
            distinct = position_buckets[(parent, i)]
            if _looks_like_id(seg) and len(distinct) >= opts.min_group_size:
                templated_segs.append("{id}")
            else:
                templated_segs.append(seg)
            parent = f"{parent}/{_segment_template(seg)}"

        path_t = "/" + "/".join(templated_segs) if templated_segs else "/"

        # Query: keep identity keys (blanked), drop others
        keep = sorted(
            k for k, _ in parse_qsl(parts.query, keep_blank_values=True)
            if k in opts.identity_keys and k not in opts.extra_drop_keys
        )
        if keep:
            query_t = "&".join(f"{k}=*" for k in keep)
            template = f"{path_t}?{query_t}"
        else:
            template = path_t

        out[url] = template

    return out
