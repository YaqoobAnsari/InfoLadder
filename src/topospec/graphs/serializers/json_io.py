"""Native JSON serialization (plan Appendix B: JSON is the native format)."""

from __future__ import annotations

import json
from pathlib import Path

from topospec.graphs.schema import Edge, Node, SpectrumGraph


def to_dict(g: SpectrumGraph) -> dict:
    return g.canonical_dict()


def from_dict(d: dict) -> SpectrumGraph:
    return SpectrumGraph(
        level=d["level"],
        building_id=d["building_id"],
        nodes={nd["id"]: Node.from_dict(nd) for nd in d["nodes"]},
        edges=[Edge.from_dict(ed) for ed in d["edges"]],
        containment=dict(d.get("containment", {})),
        meta=dict(d.get("meta", {})),
    )


def save_graph(g: SpectrumGraph, path: str | Path) -> None:
    Path(path).write_text(json.dumps(to_dict(g), indent=1, sort_keys=False) + "\n")


def load_graph(path: str | Path) -> SpectrumGraph:
    return from_dict(json.loads(Path(path).read_text()))
