"""MSD (Modified Swiss Dwellings, ECCV 2024) loader — QUARANTINED (D-014).

Schema v2 changed the tier ladder (T0..T5, doors-as-nodes, no edge taus); this
loader still emits v1-shaped graphs and FAILS v2 validation. Its new role is
VALIDATION SOURCE (MSD ground truth vs the raster->Tesseract pipeline), not tier
factory; migration tracked in ROADMAP. Original docstring follows.


MSD ships, per floor plan, a `networkx.Graph` whose nodes are the room *areas*
(with polygon geometry, room type, centroid) and whose edges are ACCESS relations
(door / open passage / entrance). No room extraction is needed — this is the
richest zero-annotation lane in the plan (§2 Lane 5, §6 Phase A).

We build the richest level MSD supports and let `forget()` derive the rest:

  * spaces  -> room / corridor nodes (area m^2, centroid m, label = room type)
  * edges   -> tau: door|entrance -> 'door', passage -> 'corridor-link';
               delta = 'both' for every edge (MSD's access graph is UNDIRECTED,
               so R3 carries no direction beyond R2 — a documented limitation)
  * near-R4 -> a containment forest of zone nodes (see `zone_mode`) + zone attrs

Then R3/R2/R1/R0 = forget(R4). This keeps strict refinement (claim C1) true by
construction.

FORMAT / LEAKAGE NOTES (dissected from the 4TU v1 train split; see
docs/scout_reports/msd_2026-07-14.md):
  * `room_type`/`zoning_type` are INTEGER indices into ROOM_NAMES / ZONING_NAMES.
  * the shipped "zone" label is a DETERMINISTIC function of room type
    (ROOM_TO_ZONE below): a bedroom is always Zone1, a bathroom always Zone3, ...
    So a category-zone target leaks through the room-type label at every level.
    `zone_mode='apartment'` instead groups spaces into spatial units (access-graph
    components cut at entrance doors) — a grouping NOT recoverable from room type
    alone, i.e. genuinely R4-exclusive. DEFAULT is 'apartment' (decision D-012);
    'category' stays available as a documented positive-leakage control.
  * MSD ships no access DIRECTION and no per-apartment id in the graph.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from topospec.graphs.levels import forget
from topospec.graphs.schema import Edge, Node, SpectrumGraph
from topospec.graphs.serializers.json_io import save_graph
from topospec.graphs.validate import SchemaError, validate_graph

# node room_type / zoning_type are indices into these (MSD constants.py, verbatim)
ROOM_NAMES = [
    "Bedroom", "Livingroom", "Kitchen", "Dining", "Corridor", "Stairs",
    "Storeroom", "Bathroom", "Balcony", "Structure", "Door", "Entrance Door", "Window",
]
ZONING_NAMES = ["Zone1", "Zone2", "Zone3", "Zone4", "Structure", "Door", "Entrance Door", "Window"]
# room types 0..8 are the AREA classes; 9.. are structure/opening (never area nodes)
AREA_ROOM_TYPES = frozenset(range(9))
# functional-zone grouping shipped by MSD (constants.py ZONING_ROOMS), by room name
ROOM_TO_ZONE = {
    "Bedroom": "Zone1",
    "Livingroom": "Zone2", "Kitchen": "Zone2", "Dining": "Zone2", "Corridor": "Zone2",
    "Stairs": "Zone3", "Storeroom": "Zone3", "Bathroom": "Zone3",
    "Balcony": "Zone4",
}
ZONE_DESC = {
    "Zone1": "private (bedroom)",
    "Zone2": "living / circulation",
    "Zone3": "service (bath, stairs, storage)",
    "Zone4": "outdoor (balcony)",
}
# MSD edge 'connectivity' -> SpectrumGraph edge tau
CONNECTIVITY_TO_TAU = {"door": "door", "entrance": "door", "passage": "corridor-link"}


def _room_kind(room_name: str) -> str:
    return "corridor" if room_name == "Corridor" else "room"


def _shoelace_area(coords: list[tuple[float, float]]) -> float:
    """Polygon area (m^2) from an exterior ring via the shoelace formula."""
    n = len(coords)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def load_plan(pickle_path: str | Path):
    """Unpickle one MSD graph_out plan into a networkx.Graph."""
    with open(pickle_path, "rb") as f:
        return pickle.load(f)


class MsdPlanError(ValueError):
    """A plan that cannot be turned into a valid graph (logged as an exclusion)."""


def plan_to_graph(graph, native_id: str, zone_mode: str = "apartment") -> SpectrumGraph:
    """Build the richest (R4) SpectrumGraph from one MSD networkx plan (plan §4.1).

    `zone_mode`:
      'category'  -> one zone node per functional zone (Zone1..Zone4) present;
                     matches the shipped zone labels (DATA-3 default).
      'apartment' -> one zone node per spatial unit = connected component of the
                     access graph after cutting entrance-door edges.
    Raises MsdPlanError on plans we refuse to emit (caller logs the exclusion).
    """
    if zone_mode not in ("category", "apartment"):
        raise ValueError(f"zone_mode must be 'category'|'apartment', got {zone_mode!r}")

    # --- space nodes -------------------------------------------------------
    nodes: dict[str, Node] = {}
    key_to_id: dict[Any, str] = {}
    key_to_name: dict[Any, str] = {}
    for key, att in graph.nodes(data=True):
        rt = att.get("room_type")
        if rt is None or int(rt) not in AREA_ROOM_TYPES:
            raise MsdPlanError(f"node {key}: non-area room_type {rt!r}")
        name = ROOM_NAMES[int(rt)]
        geom = att.get("geometry") or []
        cen = att.get("centroid")
        if cen is None:
            raise MsdPlanError(f"node {key}: missing centroid")
        cx, cy = float(cen[0]), float(cen[1])
        nid = f"a{key}"
        key_to_id[key] = nid
        key_to_name[key] = name
        nodes[nid] = Node(
            id=nid,
            kind=_room_kind(name),
            area=_shoelace_area(list(geom)),
            centroid=(cx, cy),
            label=name,
        )
    if len(nodes) < 2:
        raise MsdPlanError(f"only {len(nodes)} area node(s)")

    # --- edges (undirected access; delta 'both') ---------------------------
    edges: dict[tuple, Edge] = {}
    for u, v, att in graph.edges(data=True):
        if u == v:
            continue
        tau = CONNECTIVITY_TO_TAU.get(att.get("connectivity"))
        if tau is None:
            raise MsdPlanError(f"edge ({u},{v}): unknown connectivity {att.get('connectivity')!r}")
        a, b = sorted((key_to_id[u], key_to_id[v]))
        # if a pair appears twice (e.g. passage + entrance), prefer the 'door' tau
        prev = edges.get((a, b))
        if prev is None or (prev.tau == "corridor-link" and tau == "door"):
            edges[(a, b)] = Edge(u=a, v=b, tau=tau, delta="both")
    if not edges:
        raise MsdPlanError("no access edges")

    # --- near-R4 zone containment forest -----------------------------------
    zone_nodes, containment = _build_zones(graph, nodes, key_to_id, key_to_name, zone_mode)
    nodes.update(zone_nodes)

    g = SpectrumGraph(
        level=4,
        building_id=f"msd:{native_id}",
        nodes=nodes,
        edges=list(edges.values()),
        containment=containment,
        meta={
            "source": "topospec.data.msd",
            "dataset": "MSD (Modified Swiss Dwellings) train v1",
            "native_id": native_id,
            "zone_mode": zone_mode,
            "n_spaces": len(key_to_id),
            "n_zones": len(zone_nodes),
            "units": "meters; area m^2",
            "notes": "access graph undirected -> all delta='both'; "
            "zone(category) is a deterministic function of room_type (leakage)",
        },
    )
    validate_graph(g)
    return g


def _build_zones(
    graph, space_nodes, key_to_id, key_to_name, zone_mode
) -> tuple[dict[str, Node], dict[str, str]]:
    """Group spaces into zone hierarchy nodes; return (zone_nodes, containment)."""
    groups: dict[str, list[Any]] = {}
    if zone_mode == "category":
        for key, name in key_to_name.items():
            groups.setdefault(ROOM_TO_ZONE[name], []).append(key)
        zid = lambda g: f"zone_{g}"  # noqa: E731
        zlabel = lambda g: g  # noqa: E731
    else:  # apartment: access-graph components after cutting entrance edges
        import networkx as nx

        sub = nx.Graph()
        sub.add_nodes_from(key_to_id)
        for u, v, att in graph.edges(data=True):
            if u != v and att.get("connectivity") != "entrance" and u in key_to_id and v in key_to_id:
                sub.add_edge(u, v)
        for i, comp in enumerate(sorted(nx.connected_components(sub), key=lambda c: min(map(str, c)))):
            groups[f"apt{i}"] = list(comp)
        zid = lambda g: f"zone_{g}"  # noqa: E731
        zlabel = lambda g: f"unit {g}"  # noqa: E731

    zone_nodes: dict[str, Node] = {}
    containment: dict[str, str] = {}
    for gname, keys in groups.items():
        members = [space_nodes[key_to_id[k]] for k in keys]
        total_area = float(sum(m.area or 0.0 for m in members))
        wsum = total_area or 1.0
        cx = sum((m.area or 0.0) * m.centroid[0] for m in members) / wsum
        cy = sum((m.area or 0.0) * m.centroid[1] for m in members) / wsum
        from collections import Counter

        rt_hist = dict(Counter(key_to_name[k] for k in keys))
        nid = zid(gname)
        zone_nodes[nid] = Node(
            id=nid,
            kind="zone",
            area=total_area,
            centroid=(cx, cy),
            label=zlabel(gname),
            attrs={
                "zone_group": gname,
                "description": ZONE_DESC.get(gname, "spatial unit"),
                "n_member_spaces": len(keys),
                "member_room_types": rt_hist,
                "total_area_m2": round(total_area, 3),
            },
        )
        for k in keys:
            containment[key_to_id[k]] = nid
    return zone_nodes, containment


def build_graphs(
    raw_dir: str | Path,
    out_dir: str | Path,
    zone_mode: str = "apartment",
    limit: int | None = None,
) -> list[SpectrumGraph]:
    """Build + persist validated SpectrumGraphs for every MSD plan in raw_dir.

    Reads `raw_dir/graph_out/<id>.pickle`, writes `out_dir/<id>.r{0..4}.json` (all
    levels, refinement-consistent) per building, logs skipped plans to
    `out_dir/exclusions.jsonl` with reasons. Returns the R4 graphs (plan §7, DATA-3).
    """
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    go_dir = raw_dir / "graph_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    excl_path = out_dir / "exclusions.jsonl"
    excl_lines: list[str] = []

    pickles = sorted(go_dir.glob("*.pickle"), key=lambda p: (len(p.stem), p.stem))
    if limit is not None:
        pickles = pickles[:limit]

    built: list[SpectrumGraph] = []
    for pk in pickles:
        native = pk.stem
        try:
            graph = load_plan(pk)
            g4 = plan_to_graph(graph, native, zone_mode=zone_mode)
        except (MsdPlanError, SchemaError, pickle.UnpicklingError, KeyError, ValueError) as exc:
            excl_lines.append(
                json.dumps({"native_id": native, "reason": type(exc).__name__, "detail": str(exc)[:300]})
            )
            continue
        for lvl in (4, 3, 2, 1, 0):
            gk = forget(g4, lvl) if lvl < 4 else g4
            validate_graph(gk)
            save_graph(gk, out_dir / f"{native}.r{lvl}.json")
        built.append(g4)

    excl_path.write_text("\n".join(excl_lines) + ("\n" if excl_lines else ""))
    return built
