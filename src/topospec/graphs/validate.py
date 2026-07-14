"""Level-aware validation — plan Appendix B (machine-checkable schema per level).

Two layers:
  1. structural JSON-schema validation (graphs/schemas/*.json, versioned artifacts of
     the T5 toolkit claim);
  2. semantic invariants that JSON Schema cannot express (containment forest shape,
     referential integrity, level-licensed fields only).

`validate_graph` raises SchemaError with all violations collected, or returns True.
"""

from __future__ import annotations

import json
from importlib import resources

from topospec.graphs.schema import (
    CONTAINMENT_RANK,
    EDGE_DELTAS,
    EDGE_TAUS,
    HIERARCHY_KINDS,
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
        .joinpath(f"schemas/r{level}.json")
        .read_text()
    )
    return json.loads(text)


def validate_graph(g: SpectrumGraph, use_jsonschema: bool = True) -> bool:
    v: list[str] = []
    if g.level not in (0, 1, 2, 3, 4):
        raise SchemaError([f"level {g.level} not in 0..4"])

    node_ids = set(g.nodes.keys())
    for nid, n in g.nodes.items():
        if n.id != nid:
            v.append(f"node key {nid!r} != node.id {n.id!r}")
        if n.area is not None and n.area < 0:
            v.append(f"node {nid}: negative area")

    # --- kind licensing per level
    for nid, n in g.nodes.items():
        if g.level == 0:
            if n.kind is not None:
                v.append(f"R0 node {nid}: kind must be None, got {n.kind!r}")
            if n.label is not None:
                v.append(f"R0 node {nid}: label must be None")
            if n.attrs:
                v.append(f"R0 node {nid}: attrs must be empty")
        else:
            allowed = SPACE_KINDS if g.level < 4 else SPACE_KINDS + HIERARCHY_KINDS
            if n.kind not in allowed:
                v.append(f"R{g.level} node {nid}: kind {n.kind!r} not in {allowed}")
            if g.level < 4 and n.attrs:
                v.append(f"R{g.level} node {nid}: attribute blocks are R4-only")

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
        if g.level < 2:
            if e.tau is not None:
                v.append(f"R{g.level} edge {e.key()}: tau is R2+")
        else:
            if e.tau not in EDGE_TAUS:
                v.append(f"R{g.level} edge {e.key()}: tau {e.tau!r} not in {EDGE_TAUS}")
        if g.level < 3:
            if e.delta is not None:
                v.append(f"R{g.level} edge {e.key()}: delta is R3+")
        else:
            if e.delta not in EDGE_DELTAS:
                v.append(
                    f"R{g.level} edge {e.key()}: delta {e.delta!r} not in {EDGE_DELTAS}"
                )

    # --- containment forest (R4 only)
    if g.level < 4:
        if g.containment:
            v.append(f"R{g.level}: containment is R4-only")
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
                v.append(
                    f"containment {child}->{parent}: rank({pk}) <= rank({ck})"
                )
        # acyclicity / forest: each child has one parent by dict shape; check no cycles
        for start in g.containment:
            seen = {start}
            cur = g.containment.get(start)
            while cur is not None:
                if cur in seen:
                    v.append(f"containment cycle through {cur}")
                    break
                seen.add(cur)
                cur = g.containment.get(cur)
        # hierarchy nodes must be reachable as parents or children in the forest
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
