"""Spectrum graph schema v2 — the six-tier ladder T0..T5 (decision D-014).

Every tier is derived from the raster floorplan through the Tesseract2 pipeline
(free tiers) or manual annotation over it (paid tiers). Strict refinement: each
tier is a deterministic forgetting of the one above (levels.py).

  T0: space nodes (rooms, corridor mains, transitions) — untyped, centroid only;
      undirected connectivity edges (doors contracted away)
  T1: + node.kind in {room, corridor, transition} + semantic text label (CRAFT)
  T2: + door NODES (kind='door', label = subtype: exit / room-room /
      room-corridor / corridor-corridor door)
  T3: + measured numeric node attributes (area, eq_radius, inradius,
      n_subnodes, n_doors) — Tesseract's own measurements, surfaced
  T4: + edge delta in {both, forward, backward} (access direction/restriction;
      MANUAL annotation)
  T5: + containment forest over {corridor-cluster, zone, wing} hierarchy nodes
      with attribute blocks (MANUAL annotation)

Hot/crowded/thermal annotations are prediction targets or oracle-skyline
material — NEVER representation content (leakage; plan §5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

SPACE_KINDS = ("room", "door", "corridor", "transition")
HIERARCHY_KINDS = ("corridor-cluster", "zone", "wing")
EDGE_DELTAS = ("both", "forward", "backward")

# numeric measurement attrs allowed on SPACE nodes at T3+ (Tesseract-derived)
MEASURE_ATTR_KEYS = ("area_px", "eq_radius", "inradius", "n_subnodes", "n_doors")

# Containment rank: parent rank must strictly exceed child rank (T5 forest).
CONTAINMENT_RANK = {
    "room": 0,
    "door": 0,
    "corridor": 0,
    "transition": 0,
    "corridor-cluster": 1,
    "zone": 2,
    "wing": 3,
}


@dataclass
class Node:
    id: str
    kind: Optional[str] = None  # T1+ for spaces; 'door' T2+; hierarchy kinds T5
    area: Optional[float] = None  # T3+ (a measured attribute, not geometry-free)
    centroid: Optional[tuple[float, float]] = None  # allowed at every tier
    label: Optional[str] = None  # T1+ semantic text label
    attrs: dict[str, Any] = field(default_factory=dict)  # T3+ measures; T5 zone blocks

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "area": self.area,
            "centroid": list(self.centroid) if self.centroid is not None else None,
            "label": self.label,
            "attrs": dict(self.attrs),
        }

    @staticmethod
    def from_dict(d: dict) -> "Node":
        c = d.get("centroid")
        return Node(
            id=d["id"],
            kind=d.get("kind"),
            area=d.get("area"),
            centroid=tuple(c) if c is not None else None,
            label=d.get("label"),
            attrs=dict(d.get("attrs", {})),
        )


@dataclass
class Edge:
    u: str
    v: str
    delta: Optional[str] = None  # T4+; 'forward' means traversal u->v only

    def key(self) -> tuple:
        """Canonical identity of the underlying undirected edge."""
        return (min(self.u, self.v), max(self.u, self.v))

    def to_dict(self) -> dict:
        return {"u": self.u, "v": self.v, "delta": self.delta}

    @staticmethod
    def from_dict(d: dict) -> "Edge":
        return Edge(u=d["u"], v=d["v"], delta=d.get("delta"))


@dataclass
class SpectrumGraph:
    level: int
    building_id: str
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    containment: dict[str, str] = field(default_factory=dict)  # child_id -> parent_id
    meta: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ helpers
    def space_nodes(self) -> dict[str, Node]:
        return {
            nid: n for nid, n in self.nodes.items() if n.kind not in HIERARCHY_KINDS
        }

    def hierarchy_nodes(self) -> dict[str, Node]:
        return {nid: n for nid, n in self.nodes.items() if n.kind in HIERARCHY_KINDS}

    def neighbors(self, nid: str) -> list[str]:
        out = []
        for e in self.edges:
            if e.u == nid:
                out.append(e.v)
            elif e.v == nid:
                out.append(e.u)
        return out

    def ancestor_of_kind(self, nid: str, kind: str) -> Optional[str]:
        """Walk the containment forest upward to the first ancestor of `kind`."""
        seen = set()
        cur = self.containment.get(nid)
        while cur is not None and cur not in seen:
            seen.add(cur)
            node = self.nodes.get(cur)
            if node is not None and node.kind == kind:
                return cur
            cur = self.containment.get(cur)
        return None

    # ---------------------------------------------------------------- canonical
    def canonical_dict(self) -> dict:
        """Deterministic serialization for equality checks and hashing."""
        return {
            "schema_version": _schema_version(),
            "level": self.level,
            "building_id": self.building_id,
            "nodes": [self.nodes[k].to_dict() for k in sorted(self.nodes)],
            "edges": sorted(
                (e.to_dict() for e in self.edges),
                key=lambda d: (
                    min(d["u"], d["v"]),
                    max(d["u"], d["v"]),
                    str(d["delta"]),
                    d["u"],  # orientation last so undirected duplicates sort stably
                ),
            ),
            "containment": {k: self.containment[k] for k in sorted(self.containment)},
            "meta": self.meta,
        }

    def structurally_equal(self, other: "SpectrumGraph") -> bool:
        a, b = self.canonical_dict(), other.canonical_dict()
        a["meta"], b["meta"] = None, None
        return a == b


def _schema_version() -> str:
    from topospec import SCHEMA_VERSION

    return SCHEMA_VERSION
