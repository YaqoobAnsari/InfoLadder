"""Forgetting maps phi_k realizing strict refinement — plan §4.1, §4.3.

Every level is a deterministic coarsening of the richest one: R_k = phi_k(R4).
Chain: forget_4_to_3 -> forget_3_to_2 -> forget_2_to_1 -> forget_1_to_0.

Design decision D-001 (docs/DECISIONS.md): R0 contains every *space* (rooms and
corridor spaces) as untyped nodes; R1 -> R0 removes door nodes (reconnecting their
endpoints pairwise) and strips kind/label semantics.

Invariants (tests/test_levels.py): determinism, idempotence, level-k output validity.
"""

from __future__ import annotations

import copy
import itertools

from topospec.graphs.schema import HIERARCHY_KINDS, Edge, SpectrumGraph


def forget(g: SpectrumGraph, to_level: int) -> SpectrumGraph:
    """Apply the forgetting chain from g.level down to `to_level` (plan §4.1)."""
    if not 0 <= to_level <= 4:
        raise ValueError(f"to_level must be in 0..4, got {to_level}")
    if to_level > g.level:
        raise ValueError(f"cannot forget upward: graph level {g.level} -> {to_level}")
    out = copy.deepcopy(g)
    steps = {4: _forget_4_to_3, 3: _forget_3_to_2, 2: _forget_2_to_1, 1: _forget_1_to_0}
    while out.level > to_level:
        out = steps[out.level](out)
    return out


def _forget_4_to_3(g: SpectrumGraph) -> SpectrumGraph:
    """Drop the containment forest, hierarchy nodes, and their attribute blocks."""
    g.nodes = {nid: n for nid, n in g.nodes.items() if n.kind not in HIERARCHY_KINDS}
    g.containment = {}
    g.level = 3
    return g


def _forget_3_to_2(g: SpectrumGraph) -> SpectrumGraph:
    """Drop access direction."""
    for e in g.edges:
        e.delta = None
    g.level = 2
    return g


def _forget_2_to_1(g: SpectrumGraph) -> SpectrumGraph:
    """Drop edge types."""
    for e in g.edges:
        e.tau = None
    g.level = 1
    return g


def _forget_1_to_0(g: SpectrumGraph) -> SpectrumGraph:
    """Remove door nodes (reconnect their space neighbors pairwise); strip semantics.

    Deterministic and independent of node iteration order: the surviving edge set is
    the union of (a) edges between non-door spaces and (b) the pairwise closure over
    each door's neighbors, deduplicated on undirected keys.
    """
    door_ids = {nid for nid, n in g.nodes.items() if n.kind == "door"}

    kept: dict[tuple, Edge] = {}
    for e in g.edges:
        if e.u in door_ids or e.v in door_ids:
            continue
        kept.setdefault(e.key(), Edge(u=min(e.u, e.v), v=max(e.u, e.v)))

    for d in sorted(door_ids):
        nbrs = sorted({x for x in g.neighbors(d) if x not in door_ids})
        for a, b in itertools.combinations(nbrs, 2):
            kept.setdefault((a, b), Edge(u=a, v=b))

    g.edges = [kept[k] for k in sorted(kept)]
    g.nodes = {nid: n for nid, n in g.nodes.items() if nid not in door_ids}
    for n in g.nodes.values():
        n.kind = None
        n.label = None
        n.attrs = {}
    g.level = 0
    return g
