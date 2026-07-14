"""Tier-aware validation for the T0..T5 ladder (schema v2, D-014).

Two layers:
  1. structural JSON-schema validation (graphs/schemas/t{k}.json, versioned
     toolkit artifacts);
  2. semantic invariants JSON Schema cannot express (containment forest shape,
     referential integrity, tier-licensed fields only).

`validate_graph` raises SchemaError with all violations collected, or returns True.
"""

from __future__ import annotations

import json
from importlib import resources

from topospec.graphs.schema import (
    CONTAINMENT_RANK,
    EDGE_DELTAS,
    HIERARCHY_KINDS,
    MEASURE_ATTR_KEYS,
    SPACE_KINDS,
    SpectrumGraph,
)


class SchemaError(ValueError):
    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__(
            "graph failed validation:\n" + "\n".join(f"  - {v}" for v in violations)
        )


def json_schema_for_level(level: int) -> dict:
    text = (
        resources.files("topospec.graphs")
        .joinpath(f"schemas/t{level}.json")
        .read_text()
    )
    return json.loads(text)


def validate_graph(g: SpectrumGraph, use_jsonschema: bool = True) -> bool:
    v: list[str] = []
    if g.level not in (0, 1, 2, 3, 4, 5):
        raise SchemaError([f"level {g.level} not in 0..5"])
    lvl = g.level

    node_ids = set(g.nodes.keys())
    for nid, n in g.nodes.items():
        if n.id != nid:
            v.append(f"node key {nid!r} != node.id {n.id!r}")
        if n.area is not None and n.area < 0:
            v.append(f"node {nid}: negative area")

    # --- node licensing per tier
    for nid, n in g.nodes.items():
        if lvl == 0:
            if n.kind is not None:
                v.append(f"T0 node {nid}: kind must be None, got {n.kind!r}")
            if n.label is not None:
                v.append(f"T0 node {nid}: label must be None")
        else:
            allowed: tuple[str, ...]
            if lvl == 1:
                allowed = ("room", "corridor", "transition")
            elif lvl < 5:
                allowed = SPACE_KINDS
            else:
                allowed = SPACE_KINDS + HIERARCHY_KINDS
            if n.kind not in allowed:
                v.append(f"T{lvl} node {nid}: kind {n.kind!r} not in {allowed}")
        # measured attributes are T3+ content
        if lvl < 3:
            if n.area is not None:
                v.append(f"T{lvl} node {nid}: area is a T3+ measured attribute")
            if n.attrs:
                v.append(f"T{lvl} node {nid}: attrs are T3+ content")
        else:
            if n.kind in HIERARCHY_KINDS:
                pass  # zone/wing blocks are free-form (T5-only kinds)
            else:
                bad = [k for k in n.attrs if k not in MEASURE_ATTR_KEYS]
                if bad:
                    v.append(
                        f"T{lvl} node {nid}: non-measure attr keys {bad} "
                        f"(allowed: {list(MEASURE_ATTR_KEYS)})"
                    )

    # --- edges
    seen_keys = set()
    for e in g.edges:
        if e.u not in node_ids or e.v not in node_ids:
            v.append(f"edge ({e.u},{e.v}): endpoint not in nodes")
            continue
        if e.u == e.v:
            v.append(f"edge ({e.u},{e.v}): self-loop")
        if e.key() in seen_keys:
            v.append(f"edge {e.key()}: duplicate undirected edge")
        seen_keys.add(e.key())
        for nid in (e.u, e.v):
            if g.nodes[nid].kind in HIERARCHY_KINDS:
                v.append(f"edge {e.key()}: touches hierarchy node {nid}")
        if lvl < 2:
            ku, kv = g.nodes[e.u].kind, g.nodes[e.v].kind
            if ku == "door" or kv == "door":
                v.append(f"T{lvl} edge {e.key()}: door nodes are T2+")
        if lvl < 4:
            if e.delta is not None:
                v.append(f"T{lvl} edge {e.key()}: delta is T4+")
        else:
            if e.delta not in EDGE_DELTAS:
                v.append(
                    f"T{lvl} edge {e.key()}: delta {e.delta!r} not in {EDGE_DELTAS}"
                )

    # door nodes themselves are T2+ regardless of edges
    if lvl < 2:
        for nid, n in g.nodes.items():
            if n.kind == "door":
                v.append(f"T{lvl} node {nid}: door nodes are T2+")

    # --- containment forest (T5 only)
    if lvl < 5:
        if g.containment:
            v.append(f"T{lvl}: containment is T5-only")
        for nid in g.hierarchy_nodes():
            v.append(f"T{lvl} node {nid}: hierarchy kinds are T5-only")
    else:
        for child, parent in g.containment.items():
            if child not in node_ids or parent not in node_ids:
                v.append(f"containment {child}->{parent}: unknown node")
                continue
            ck = g.nodes[child].kind
            pk = g.nodes[parent].kind
            if pk not in HIERARCHY_KINDS:
                v.append(f"containment {child}->{parent}: parent kind {pk!r} invalid")
            if (
                ck in CONTAINMENT_RANK
                and pk in CONTAINMENT_RANK
                and CONTAINMENT_RANK[pk] <= CONTAINMENT_RANK[ck]
            ):
                v.append(f"containment {child}->{parent}: rank({pk}) <= rank({ck})")
        for start in g.containment:
            seen = {start}
            cur = g.containment.get(start)
            while cur is not None:
                if cur in seen:
                    v.append(f"containment cycle through {cur}")
                    break
                seen.add(cur)
                cur = g.containment.get(cur)
        in_forest = set(g.containment) | set(g.containment.values())
        for hid in g.hierarchy_nodes():
            if hid not in in_forest:
                v.append(f"hierarchy node {hid} not in containment forest")

    if use_jsonschema:
        try:
            import jsonschema

            jsonschema.validate(g.canonical_dict(), json_schema_for_level(g.level))
        except jsonschema.ValidationError as exc:  # pragma: no cover - belt&braces
            v.append(f"jsonschema: {exc.message}")

    if v:
        raise SchemaError(v)
    return True
