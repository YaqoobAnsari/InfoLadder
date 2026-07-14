"""Spectrum graph schema — plan §4.1 and Appendix B.

A SpectrumGraph carries a `level` in 0..4 and only the structure that level licenses:

  R0: space nodes (area, centroid) + undirected connectivity edges
  R1: + door nodes, node.kind in {room, door, corridor}, semantic `label`
  R2: + edge.tau in {wall, door, corridor-link}
  R3: + edge.delta in {both, forward, backward} (direction is relative to (u, v))
  R4: + containment forest (child -> parent) over hierarchy nodes with kinds in
      {corridor-cluster, zone, wing}, which carry attribute blocks in `attrs`

Strict refinement (claim C1) is realized by the forgetting maps in levels.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

SPACE_KINDS = ("room", "door", "corridor")
HIERARCHY_KINDS = ("corridor-cluster", "zone", "wing")
EDGE_TAUS = ("wall", "door", "corridor-link")
EDGE_DELTAS = ("both", "forward", "backward")

# Containment rank: parent rank must strictly exceed child rank (plan App. B forest).
CONTAINMENT_RANK = {
    "room": 0,
    "door": 0,
    "corridor": 0,
    "corridor-cluster": 1,
    "zone": 2,
    "wing": 3,
}


@dataclass
class Node:
    id: str
    kind: Optional[str] = None  # R1+ for spaces; hierarchy kinds only at R4
    area: Optional[float] = None
    centroid: Optional[tuple[float, float]] = None
    label: Optional[str] = None  # R1+ semantic label
    attrs: dict[str, Any] = field(default_factory=dict)  # R4 zone/wing blocks

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
    tau: Optional[str] = None  # R2+
    delta: Optional[str] = None  # R3+; 'forward' means traversal u->v only

    def key(self) -> tuple:
        """Canonical identity of the underlying undirected edge."""
        return (min(self.u, self.v), max(self.u, self.v))

    def to_dict(self) -> dict:
        return {"u": self.u, "v": self.v, "tau": self.tau, "delta": self.delta}

    @staticmethod
    def from_dict(d: dict) -> "Edge":
        return Edge(u=d["u"], v=d["v"], tau=d.get("tau"), delta=d.get("delta"))


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
                    str(d["tau"]),
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
