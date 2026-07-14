"""Tesseract2 navigation JSON → the T0..T3 free tiers (D-011, D-014; plan §3.3).

Tesseract2 (github.com/YaqoobAnsari/Tesseract2 — the user's own pipeline and the
tier engine of this project) parses annotated floorplan rasters with CRAFT text
detection + Faster R-CNN door detection and emits a navigation graph JSON
(`*_post_pruning.json`, or `*_pre_pruning.json` which additionally has `outside`
connectors): rooms with geometry stats, room-interior subnodes, corridor waypoint
meshes, TYPED door nodes (exit / r2c / r2r / c2c), and stairs/elevator transitions.

This factory contracts the navigation graph into the richest FREE tier, T3, and
`forget()` derives T2/T1/T0:

  room_N               -> room node; T3 measures: area (px^2), eq_radius,
                          inradius, n_subnodes, n_doors
  room_N_subnode_M     -> contracted into parent room; count -> n_subnodes
  corridor_* mesh      -> connected components of the corridor-corridor subgraph,
                          one corridor space node per component; waypoint count
                          -> n_subnodes (a corridor-extent proxy)
  transition nodes     -> kind='transition' (stairs/elevators)
  *_door_N             -> door node (T2+), label = subtype
  corridor-room edge   -> direct open passage (edge without a door node)
  outside_* nodes      -> dropped; doors touching outside get label 'exit door'
                          (only pre_pruning exports carry outside nodes)

Direction (T4) and containment (T5) are NOT derivable from Tesseract2 output —
those are the manual annotation tiers. Positions/areas are in image pixels.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from topospec.graphs.levels import forget
from topospec.graphs.schema import Edge, Node, SpectrumGraph
from topospec.graphs.validate import validate_graph

FREE_TIERS = (0, 1, 2, 3)


class TesseractGraphError(ValueError):
    pass


def load_graph_json(path: str | Path) -> dict:
    g = json.loads(Path(path).read_text())
    if "nodes" not in g or "edges" not in g:
        raise TesseractGraphError(f"{path}: expected keys nodes/edges")
    if not g["edges"]:
        raise TesseractGraphError(
            f"{path}: no edges — use the *_post_pruning.json / *_pre_pruning.json "
            "navigation export, not the summary *_final_graph.json"
        )
    return g


def _door_label(door_id: str) -> str:
    if door_id.startswith("exit_door"):
        return "exit door"
    if "2c_door" in door_id and door_id.startswith("c"):
        return "corridor-corridor door"
    if "2r_door" in door_id:
        return "room-room door"
    return "room-corridor door"


def to_t3(tess: dict, building_id: str, source: str = "") -> SpectrumGraph:
    """Contract one Tesseract2 navigation graph into the T3 tier graph."""
    tnodes = {n["id"]: n for n in tess["nodes"]}

    # ---- space contraction maps ------------------------------------------------
    space_of: dict[str, str] = {}
    rooms: dict[str, dict] = {}
    n_subnodes_of: dict[str, int] = {}
    for nid, n in tnodes.items():
        if n["type"] != "room":
            continue
        if n.get("is_subnode"):
            parent = n.get("parent_room_id")
            if parent is None or parent not in tnodes:
                raise TesseractGraphError(f"subnode {nid}: missing parent_room_id")
            space_of[nid] = parent
            n_subnodes_of[parent] = n_subnodes_of.get(parent, 0) + 1
        else:
            rooms[nid] = n
            space_of[nid] = nid

    transitions = {nid: n for nid, n in tnodes.items() if n["type"] == "transition"}
    for nid in transitions:
        space_of[nid] = nid

    corridor_ids = [nid for nid, n in tnodes.items() if n["type"] == "corridor"]
    corridor_adj: dict[str, list[str]] = {nid: [] for nid in corridor_ids}
    for e in tess["edges"]:
        s, t = e["source"], e["target"]
        if s in corridor_adj and t in corridor_adj:
            corridor_adj[s].append(t)
            corridor_adj[t].append(s)
    corridor_comp: dict[str, int] = {}
    n_comp = 0
    for start in sorted(corridor_ids):
        if start in corridor_comp:
            continue
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in corridor_comp:
                continue
            corridor_comp[cur] = n_comp
            stack.extend(x for x in corridor_adj[cur] if x not in corridor_comp)
        n_comp += 1
    for nid, comp in corridor_comp.items():
        space_of[nid] = f"c{comp:03d}"

    doors = {nid: n for nid, n in tnodes.items() if n["type"] == "door"}
    outside = {nid for nid, n in tnodes.items() if n["type"] == "outside"}

    # ---- nodes -------------------------------------------------------------------
    nodes: dict[str, Node] = {}
    for rid, n in rooms.items():
        cen = n.get("room_centroid_xy") or n.get("position") or (0.0, 0.0)
        nodes[rid] = Node(
            id=rid,
            kind="room",
            area=float(n["room_area_px"]) if n.get("room_area_px") else None,
            centroid=(float(cen[0]), float(cen[1])),
            label=str(n["label"]) if n.get("label") else None,
            attrs={
                "eq_radius": float(n.get("room_eq_radius") or 0.0),
                "inradius": float(n.get("room_inradius") or 0.0),
                "n_subnodes": int(n_subnodes_of.get(rid, 0)),
                "n_doors": 0,  # filled after edge construction
            },
        )
    comp_members: dict[int, list] = {}
    for nid, comp in corridor_comp.items():
        comp_members.setdefault(comp, []).append(tnodes[nid]["position"])
    for comp, positions in sorted(comp_members.items()):
        arr = np.asarray(positions, dtype=float)
        nodes[f"c{comp:03d}"] = Node(
            id=f"c{comp:03d}",
            kind="corridor",
            area=None,
            centroid=(float(arr[:, 0].mean()), float(arr[:, 1].mean())),
            label="corridor",
            attrs={"n_subnodes": len(positions), "n_doors": 0},
        )
    for tid, n in transitions.items():
        pos = n.get("position") or (0.0, 0.0)
        nodes[tid] = Node(
            id=tid,
            kind="transition",
            area=None,
            centroid=(float(pos[0]), float(pos[1])),
            label=str(n.get("label") or "stairs/elevator"),
            attrs={"n_doors": 0},
        )
    for did, n in doors.items():
        pos = n.get("position") or (0.0, 0.0)
        nodes[did] = Node(
            id=did,
            kind="door",
            area=None,
            centroid=(float(pos[0]), float(pos[1])),
            label=_door_label(did),
        )

    # ---- edges -------------------------------------------------------------------
    edges: dict[tuple, Edge] = {}
    exit_doors: set[str] = set()
    for e in tess["edges"]:
        s, t = e["source"], e["target"]
        ts, tt = tnodes[s]["type"], tnodes[t]["type"]
        if ts == "outside" or tt == "outside":
            other = t if ts == "outside" else s
            if other in doors:
                exit_doors.add(other)
            continue
        if ts == "corridor" and tt == "corridor":
            continue  # contracted inside a corridor component
        if "door" in (ts, tt) and ts != tt:
            door_id = s if ts == "door" else t
            other = t if ts == "door" else s
            sp = space_of.get(other)
            if sp is None:
                continue
            key = (min(door_id, sp), max(door_id, sp))
            edges.setdefault(key, Edge(u=key[0], v=key[1]))
            continue
        # space-space (room-room subnode links contract; cross-space = passage)
        a, b = space_of.get(s), space_of.get(t)
        if a is None or b is None or a == b:
            continue
        key = (min(a, b), max(a, b))
        edges.setdefault(key, Edge(u=key[0], v=key[1]))

    for did in exit_doors:
        if did in nodes:
            nodes[did].label = "exit door"

    # drop doors with no surviving edges; count doors per space
    connected = {e.u for e in edges.values()} | {e.v for e in edges.values()}
    for did in list(doors):
        if did in nodes and did not in connected:
            del nodes[did]
    for e in edges.values():
        for a, b in ((e.u, e.v), (e.v, e.u)):
            if nodes.get(b) is not None and nodes[b].kind == "door":
                if nodes.get(a) is not None and "n_doors" in nodes[a].attrs:
                    nodes[a].attrs["n_doors"] += 1

    g = SpectrumGraph(
        level=3,
        building_id=building_id,
        nodes=nodes,
        edges=list(edges.values()),
        containment={},
        meta={
            "source": "topospec.data.tesseract",
            "pipeline": "Tesseract2 (github.com/YaqoobAnsari/Tesseract2)",
            "source_json": source,
            "units": "image pixels",
            "n_rooms": len(rooms),
            "n_corridor_components": n_comp,
            "n_transitions": len(transitions),
            "n_doors": len(doors),
            "n_exit_doors": len(exit_doors),
            "n_subnodes_contracted": sum(n_subnodes_of.values()),
            "n_outside_dropped": len(outside),
        },
    )
    validate_graph(g)
    return g


def build_t3(json_path: str | Path, building_id: str | None = None) -> SpectrumGraph:
    """Load a Tesseract2 export and adapt it to the T3 tier."""
    path = Path(json_path)
    tess = load_graph_json(path)
    bid = building_id or f"tess:{path.stem.replace(' ', '_')}"
    return to_t3(tess, bid, source=str(path))


def build_tiers(
    json_path: str | Path, building_id: str | None = None
) -> dict[int, SpectrumGraph]:
    """All four free tiers {3: T3, 2: T2, 1: T1, 0: T0} from one export."""
    g3 = build_t3(json_path, building_id)
    out = {3: g3}
    for lvl in (2, 1, 0):
        gk = forget(g3, lvl)
        validate_graph(gk)
        out[lvl] = gk
    return out
