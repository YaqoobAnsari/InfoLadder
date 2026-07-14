"""Tesseract2 navigation JSON → the T0..T3 free tiers (D-011, D-014; plan §3.3).

Tesseract2 (github.com/YaqoobAnsari/Tesseract2 — the user's own pipeline and the
tier engine of this project) parses annotated floorplan rasters (CRAFT text
detection + interpreter + Faster R-CNN doors) and emits navigation graph JSONs.

CONSUME `*_pre_pruning.json`: it carries ALL corridor_main nodes (post-pruning can
drop them) plus the `outside` connectors needed for exit-door marking.

Semantics of the source (dissected from Main.py + text_interpreter.py):
  * `room_{i}`          one per non-hall/na/transition TEXT bbox, in results order
  * `corridor_main_{i}` one per 'hall' TEXT bbox — the corridor IDENTITIES the
                        annotator drew; position = the Hall text location
  * `outside_main/_connect` from 'na' TEXT bboxes — outdoor regions
  * `stairs_/elevator_/transition_` from transition-alias texts
  * `corridor_connect_*` flood-fill waypoints along the corridor network
  * recognized text is NOT exported in the JSON; it lives in the interpreter
    sidecar `Results/Plots/interpreter_detect/<image>/room_labels.txt`, whose
    per-category ORDER matches the node numbering — so labels are joined
    deterministically (rooms get their numbers, corridor mains get 'hall').

Tier mapping:
  rooms                -> room nodes, label = recognized text (e.g. '1004')
  corridor mains       -> corridor space nodes AT THE HALL TEXT POSITIONS;
                          every corridor waypoint is assigned to its EUCLIDEAN-
                          nearest main ('Hall' texts are local hub identities —
                          user design intent; mesh-distance assignment lets one
                          main swallow a door-free wing). Territories that touch
                          in the mesh get a passage edge. If a plan has NO hall
                          text, waypoint components survive as fallback
                          'corridor (unlabeled)' spaces — never silently dropped.
  transitions          -> kind='transition', label stairs/elevator from node id
  doors                -> door nodes (T2+), label = subtype; T3 adds n_doors etc.
  outside_*            -> dropped as nodes; doors touching them = 'exit door'

Direction (T4) and containment (T5) remain manual tiers. Positions in image px.
"""

from __future__ import annotations

import json
import re
from collections import deque  # noqa: F401  (kept for fallback flood)
from pathlib import Path

import numpy as np

from topospec.graphs.levels import forget
from topospec.graphs.schema import Edge, Node, SpectrumGraph
from topospec.graphs.validate import validate_graph

FREE_TIERS = (0, 1, 2, 3)

# verbatim from Models/Interpreter/text_interpreter.py (interpret_bboxes)
TRANSITION_ALIASES = {
    "stairs": "stairs", "stair": "stairs", "staircase": "stairs",
    "elev": "elevator", "elevator": "elevator", "lift": "elevator",
}

_LABEL_LINE = re.compile(r"BBox \d+: \[(.*?)\], Text: (.*?), Confidence: ([0-9.]+)")


class TesseractGraphError(ValueError):
    pass


def load_graph_json(path: str | Path) -> dict:
    g = json.loads(Path(path).read_text())
    if "nodes" not in g or "edges" not in g:
        raise TesseractGraphError(f"{path}: expected keys nodes/edges")
    if not g["edges"]:
        raise TesseractGraphError(
            f"{path}: no edges — use the *_pre_pruning.json / *_post_pruning.json "
            "navigation export, not the summary *_final_graph.json"
        )
    return g


def sidecar_labels_path(export_path: str | Path) -> Path:
    """Derive .../Plots/interpreter_detect/<image>/room_labels.txt from a
    .../Json/<image>/<image>_*_pruning.json export path."""
    p = Path(export_path)
    image = p.parent.name
    return p.parent.parent.parent / "Plots" / "interpreter_detect" / image / "room_labels.txt"


def load_text_labels(txt_path: str | Path) -> dict[str, str]:
    """Join recognized text to node ids by replaying the interpreter's
    categorization (order within each category defines the node numbering)."""
    labels: dict[str, str] = {}
    n_room = n_hall = 0
    for line in Path(txt_path).read_text().splitlines():
        m = _LABEL_LINE.match(line.strip())
        if not m:
            continue
        text = m.group(2).strip()
        low = text.lower()
        if low == "hall":
            n_hall += 1
            labels[f"corridor_main_{n_hall}"] = "hall"
        elif low == "na":
            continue  # outside regions: nodes are dropped anyway
        elif low in TRANSITION_ALIASES:
            continue  # transition node ids already carry stairs_/elevator_
        else:
            n_room += 1
            labels[f"room_{n_room}"] = text
    return labels


def _door_label(door_id: str) -> str:
    if door_id.startswith("exit_door"):
        return "exit door"
    if "2c_door" in door_id and door_id.startswith("c"):
        return "corridor-corridor door"
    if "2r_door" in door_id:
        return "room-room door"
    return "room-corridor door"


def _transition_label(node_id: str) -> str:
    if node_id.startswith("stairs"):
        return "stairs"
    if node_id.startswith("elevator"):
        return "elevator"
    return "transition"


def to_t3(
    tess: dict,
    building_id: str,
    source: str = "",
    text_labels: dict[str, str] | None = None,
) -> SpectrumGraph:
    """Contract one Tesseract2 navigation graph into the T3 tier graph."""
    text_labels = text_labels or {}
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

    # ---- corridor mesh: BFS-Voronoi assignment of waypoints to MAINS ------------
    corridor_ids = [nid for nid, n in tnodes.items() if n["type"] == "corridor"]
    mains = sorted(nid for nid in corridor_ids if nid.startswith("corridor_main"))
    corridor_adj: dict[str, list[tuple[str, float]]] = {nid: [] for nid in corridor_ids}
    for e in tess["edges"]:
        s, t = e["source"], e["target"]
        if s in corridor_adj and t in corridor_adj:
            w = float(e.get("weight") or e.get("distance") or 0.0)
            if w <= 0:  # fallback: euclidean between waypoint positions
                ps, pt = tnodes[s]["position"], tnodes[t]["position"]
                w = float(np.hypot(ps[0] - pt[0], ps[1] - pt[1])) or 1.0
            corridor_adj[s].append((t, w))
            corridor_adj[t].append((s, w))
    # SPATIAL assignment: each waypoint belongs to its euclidean-nearest hall
    # main. Rationale (user design intent): 'Hall' texts are LOCAL hub
    # identities the annotator placed; rooms must attach to their nearest hall.
    # Mesh-distance assignment fails here — corridor flood-fill can run
    # door-free around a whole wing (FF part 1upE: one L-shaped mesh, so one
    # main captured 1242/1328 waypoints while the physically-nearest halls
    # owned vestibule slivers).
    owner: dict[str, str] = {}
    if mains:
        main_pos = np.asarray([tnodes[m]["position"] for m in mains], dtype=float)
        for nid in corridor_ids:
            p = tnodes[nid]["position"]
            d2 = ((main_pos[:, 0] - p[0]) ** 2) + ((main_pos[:, 1] - p[1]) ** 2)
            owner[nid] = mains[int(np.argmin(d2))]
    # waypoint components with no main: fallback spaces, never silently dropped
    n_fallback = 0
    for start in sorted(corridor_ids):
        if start in owner:
            continue
        fid = f"corridor_unlabeled_{n_fallback}"
        n_fallback += 1
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in owner:
                continue
            owner[cur] = fid
            stack.extend(nb for nb, _w in corridor_adj[cur])
    for nid, own in owner.items():
        space_of[nid] = own

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
            label=text_labels.get(rid),
            attrs={
                "eq_radius": float(n.get("room_eq_radius") or 0.0),
                "inradius": float(n.get("room_inradius") or 0.0),
                "n_subnodes": int(n_subnodes_of.get(rid, 0)),
                "n_doors": 0,
            },
        )
    members: dict[str, int] = {}
    for nid, own in owner.items():
        members[own] = members.get(own, 0) + (0 if nid == own else 1)
    for cid in sorted(set(owner.values())):
        if cid in mains:
            pos = tnodes[cid]["position"]
            centroid = (float(pos[0]), float(pos[1]))  # the Hall TEXT location
            label = text_labels.get(cid, "hall")
        else:
            pts = np.asarray(
                [tnodes[nid]["position"] for nid, o in owner.items() if o == cid],
                dtype=float,
            )
            centroid = (float(pts[:, 0].mean()), float(pts[:, 1].mean()))
            label = "corridor (unlabeled)"
        nodes[cid] = Node(
            id=cid,
            kind="corridor",
            area=None,
            centroid=centroid,
            label=label,
            attrs={"n_subnodes": int(members.get(cid, 0)), "n_doors": 0},
        )
    for tid, n in transitions.items():
        pos = n.get("position") or (0.0, 0.0)
        nodes[tid] = Node(
            id=tid,
            kind="transition",
            area=None,
            centroid=(float(pos[0]), float(pos[1])),
            label=_transition_label(tid),
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

    def _link(a: str, b: str) -> None:
        if a == b:
            return
        key = (min(a, b), max(a, b))
        edges.setdefault(key, Edge(u=key[0], v=key[1]))

    for e in tess["edges"]:
        s, t = e["source"], e["target"]
        ts, tt = tnodes[s]["type"], tnodes[t]["type"]
        if ts == "outside" or tt == "outside":
            other = t if ts == "outside" else s
            if other in doors:
                exit_doors.add(other)
            continue
        if ts == "corridor" and tt == "corridor":
            # adjacency BETWEEN corridor territories = a real passage edge;
            # links inside one territory contract away
            _link(space_of[s], space_of[t])
            continue
        if "door" in (ts, tt) and ts != tt:
            door_id = s if ts == "door" else t
            other = t if ts == "door" else s
            sp = space_of.get(other)
            if sp is not None:
                _link(door_id, sp)
            continue
        a, b = space_of.get(s), space_of.get(t)
        if a is not None and b is not None:
            _link(a, b)

    for did in exit_doors:
        if did in nodes:
            nodes[did].label = "exit door"

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
            "n_corridor_mains": len(mains),
            "n_corridor_fallback_components": n_fallback,
            "n_transitions": len(transitions),
            "n_doors": len(doors),
            "n_exit_doors": len(exit_doors),
            "n_subnodes_contracted": sum(n_subnodes_of.values()),
            "n_waypoints_contracted": max(0, len(corridor_ids) - len(mains)),
            "n_outside_dropped": len(outside),
            "text_labels_joined": bool(text_labels),
        },
    )
    validate_graph(g)
    return g


def build_t3(
    json_path: str | Path,
    building_id: str | None = None,
    labels_txt: str | Path | None = None,
) -> SpectrumGraph:
    """Load a Tesseract2 export (+ interpreter text sidecar if found) -> T3."""
    path = Path(json_path)
    tess = load_graph_json(path)
    if labels_txt is None:
        candidate = sidecar_labels_path(path)
        labels_txt = candidate if candidate.exists() else None
    text_labels = load_text_labels(labels_txt) if labels_txt else {}
    bid = building_id or f"tess:{path.stem.replace(' ', '_')}"
    return to_t3(tess, bid, source=str(path), text_labels=text_labels)


def build_tiers(
    json_path: str | Path,
    building_id: str | None = None,
    labels_txt: str | Path | None = None,
) -> dict[int, SpectrumGraph]:
    """All four free tiers {3: T3, 2: T2, 1: T1, 0: T0} from one export."""
    g3 = build_t3(json_path, building_id, labels_txt)
    out = {3: g3}
    for lvl in (2, 1, 0):
        gk = forget(g3, lvl)
        validate_graph(gk)
        out[lvl] = gk
    return out
