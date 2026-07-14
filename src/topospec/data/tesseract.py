"""Tesseract2 navigable-graph JSON → SpectrumGraph R2 (user directive; plan §3.3).

Tesseract2 (github.com/YaqoobAnsari/Tesseract2 — the plan's R1 lineage, our own
toolchain) parses annotated floorplan rasters with CRAFT text detection + Faster
R-CNN door detection and emits a navigation graph JSON (`*_post_pruning.json` /
`*_final_graph.json` with edges): rooms with geometry, room-interior subnodes,
corridor waypoint meshes, TYPED door nodes (exit / room-to-corridor r2c /
room-to-room r2r / corridor-to-corridor c2c), and outside connectors.

This adapter contracts the navigation graph into the spectrum's space graph:

  room_N               -> room node (area px^2, centroid, inradius attrs dropped)
  room_N_subnode_M     -> contracted into parent room (navigation waypoints)
  corridor_* mesh      -> connected components of the corridor-corridor subgraph,
                          one corridor space node per component
  *_door_N             -> door node (R1+); edge tau='door' on its space links
  transition nodes     -> stairs/elevators: space nodes (kind 'room', label kept)
                          — vertical circulation matters for Y_egress
  corridor-room edge   -> direct open passage: space-space edge tau='corridor-link'
  outside_* nodes      -> dropped; doors touching outside get label 'exit door'
                          (fresh post_pruning exports fold outside away — feed
                          pre_pruning if exit labels are needed)

Output level is R2 (kinds + labels + edge taus are all known); R1/R0 come from
forget(). Direction (R3) and containment (R4) are NOT derivable from Tesseract2
output — those stay with the annotation lane. Positions/areas are in image
pixels (px_per_m unknown); meta records provenance.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from topospec.graphs.schema import Edge, Node, SpectrumGraph
from topospec.graphs.validate import validate_graph


class TesseractGraphError(ValueError):
    pass


def load_graph_json(path: str | Path) -> dict:
    g = json.loads(Path(path).read_text())
    if "nodes" not in g or "edges" not in g:
        raise TesseractGraphError(f"{path}: expected keys nodes/edges")
    if not g["edges"]:
        raise TesseractGraphError(
            f"{path}: no edges — use the *_post_pruning.json / full navigation "
            "export, not the summary *_final_graph.json"
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


def to_spectrum_graph(
    tess: dict, building_id: str, source: str = ""
) -> SpectrumGraph:
    """Contract one Tesseract2 navigation graph into a SpectrumGraph at R2."""
    tnodes = {n["id"]: n for n in tess["nodes"]}

    # ---- space contraction maps ------------------------------------------------
    # rooms: subnodes -> parent room id
    space_of: dict[str, str] = {}
    rooms: dict[str, dict] = {}
    for nid, n in tnodes.items():
        if n["type"] != "room":
            continue
        if n.get("is_subnode"):
            parent = n.get("parent_room_id")
            if parent is None or parent not in tnodes:
                raise TesseractGraphError(f"subnode {nid}: missing parent_room_id")
            space_of[nid] = parent
        else:
            rooms[nid] = n
            space_of[nid] = nid

    # transitions (stairs/elevators): standalone space nodes
    transitions = {nid: n for nid, n in tnodes.items() if n["type"] == "transition"}
    for nid in transitions:
        space_of[nid] = nid

    # corridors: connected components of the corridor-corridor subgraph
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

    # ---- build nodes -------------------------------------------------------------
    nodes: dict[str, Node] = {}
    for rid, n in rooms.items():
        cen = n.get("room_centroid_xy") or n.get("position") or (0.0, 0.0)
        nodes[rid] = Node(
            id=rid,
            kind="room",
            area=float(n["room_area_px"]) if n.get("room_area_px") else None,
            centroid=(float(cen[0]), float(cen[1])),
            label=str(n["label"]) if n.get("label") else None,
        )
    comp_positions: dict[int, list] = {}
    for nid, comp in corridor_comp.items():
        comp_positions.setdefault(comp, []).append(tnodes[nid]["position"])
    for comp, positions in sorted(comp_positions.items()):
        arr = np.asarray(positions, dtype=float)
        nodes[f"c{comp:03d}"] = Node(
            id=f"c{comp:03d}",
            kind="corridor",
            area=None,
            centroid=(float(arr[:, 0].mean()), float(arr[:, 1].mean())),
            label="corridor",
        )
    for tid, n in transitions.items():
        pos = n.get("position") or (0.0, 0.0)
        nodes[tid] = Node(
            id=tid,
            kind="room",  # schema space kinds are room|door|corridor; label says what it is
            area=None,
            centroid=(float(pos[0]), float(pos[1])),
            label=str(n.get("label") or "transition (stairs/elevator)"),
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
        if ts == "room" and tt == "room":
            # subnode<->parent / subnode<->subnode links contract away; a
            # room-room edge across DIFFERENT spaces would be an open passage
            a, b = space_of[s], space_of[t]
            if a == b:
                continue
            key = (min(a, b), max(a, b))
            edges.setdefault(key, Edge(u=key[0], v=key[1], tau="corridor-link"))
            continue
        if "door" in (ts, tt) and ts != tt:
            door_id = s if ts == "door" else t
            other = t if ts == "door" else s
            sp = space_of.get(other)
            if sp is None:
                continue
            key = (min(door_id, sp), max(door_id, sp))
            edges.setdefault(key, Edge(u=key[0], v=key[1], tau="door"))
            continue
        if {"corridor", "room"} == {ts, tt}:
            a, b = space_of[s], space_of[t]
            key = (min(a, b), max(a, b))
            edges.setdefault(key, Edge(u=key[0], v=key[1], tau="corridor-link"))

    for did in exit_doors:
        if did in nodes:
            nodes[did].label = "exit door"

    # drop doors that ended up with no edges (e.g. only outside links on both sides)
    connected = {e.u for e in edges.values()} | {e.v for e in edges.values()}
    for did in list(doors):
        if did in nodes and did not in connected:
            del nodes[did]

    g = SpectrumGraph(
        level=2,
        building_id=building_id,
        nodes=nodes,
        edges=list(edges.values()),
        containment={},
        meta={
            "source": "topospec.data.tesseract",
            "pipeline": "Tesseract2 (github.com/YaqoobAnsari/Tesseract2)",
            "source_json": source,
            "units": "image pixels (px_per_m unknown)",
            "n_rooms": len(rooms),
            "n_corridor_components": n_comp,
            "n_doors": len(doors),
            "n_exit_doors": len(exit_doors),
            "n_subnodes_contracted": sum(
                1 for n in tnodes.values() if n.get("is_subnode")
            ),
            "n_outside_dropped": len(outside),
        },
    )
    validate_graph(g)
    return g


def build_r2(json_path: str | Path, building_id: str | None = None) -> SpectrumGraph:
    """One-call convenience: load a Tesseract2 export and adapt it to R2."""
    path = Path(json_path)
    tess = load_graph_json(path)
    bid = building_id or f"tess:{path.stem.replace(' ', '_')}"
    return to_spectrum_graph(tess, bid, source=str(path))
