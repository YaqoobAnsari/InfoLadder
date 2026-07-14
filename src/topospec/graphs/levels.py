"""Forgetting maps phi_k for the six-tier ladder T0..T5 (schema v2, D-014).

Every tier is a deterministic coarsening of the richest one: T_k = phi_k(T5).
Chain:
  T5 -> T4  drop containment forest + hierarchy nodes (+ their attr blocks)
  T4 -> T3  drop edge deltas (access direction)
  T3 -> T2  strip measured numeric attributes (area + attrs) from space nodes
  T2 -> T1  remove door nodes, reconnecting their space neighbors pairwise
  T1 -> T0  strip kinds and labels (untyped skeleton; centroids stay)

Invariants (tests/test_levels.py): determinism, idempotence, chain composition,
level-k output validity.
"""

from __future__ import annotations

import copy
import itertools

from topospec.graphs.schema import HIERARCHY_KINDS, Edge, SpectrumGraph


def forget(g: SpectrumGraph, to_level: int) -> SpectrumGraph:
    """Apply the forgetting chain from g.level down to `to_level`."""
    if not 0 <= to_level <= 5:
        raise ValueError(f"to_level must be in 0..5, got {to_level}")
    if to_level > g.level:
        raise ValueError(f"cannot forget upward: graph level {g.level} -> {to_level}")
    out = copy.deepcopy(g)
    steps = {
        5: _forget_5_to_4,
        4: _forget_4_to_3,
        3: _forget_3_to_2,
        2: _forget_2_to_1,
        1: _forget_1_to_0,
    }
    while out.level > to_level:
        out = steps[out.level](out)
    return out


def _forget_5_to_4(g: SpectrumGraph) -> SpectrumGraph:
    """Drop the containment forest, hierarchy nodes, and their attribute blocks."""
    g.nodes = {nid: n for nid, n in g.nodes.items() if n.kind not in HIERARCHY_KINDS}
    g.containment = {}
    g.level = 4
    return g


def _forget_4_to_3(g: SpectrumGraph) -> SpectrumGraph:
    """Drop access direction."""
    for e in g.edges:
        e.delta = None
    g.level = 3
    return g


def _forget_3_to_2(g: SpectrumGraph) -> SpectrumGraph:
    """Strip the measured numeric attributes (Tesseract's measurements)."""
    for n in g.nodes.values():
        n.area = None
        n.attrs = {}
    g.level = 2
    return g


def _forget_2_to_1(g: SpectrumGraph) -> SpectrumGraph:
    """Remove door nodes (reconnect their space neighbors pairwise).

    Deterministic and independent of iteration order: surviving edges are the
    union of (a) edges between non-door spaces and (b) the pairwise closure over
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
    g.level = 1
    return g


def _forget_1_to_0(g: SpectrumGraph) -> SpectrumGraph:
    """Strip semantics: untyped, unlabeled skeleton (centroids preserved)."""
    for n in g.nodes.values():
        n.kind = None
        n.label = None
    g.level = 0
    return g
