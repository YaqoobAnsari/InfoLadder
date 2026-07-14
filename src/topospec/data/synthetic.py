"""Calibration families with planted targets on the T0..T5 ladder (D-014; plan §6 A0).

Targets are planted at a KNOWN tier by design, so the probing protocol can be
calibrated: the instrument passes only if the estimated I_V surface recovers each
planted saturation tier (paper Figure 2).

Planted targets (all binary, on room nodes):
  planted_degree  readable at T0+  y = 1[deg(node) >= 2] on the T0 skeleton
                  (positive control: pure connectivity; FIXED global threshold so
                  the target is fully extractable by structure-reading probes)
  planted_label   readable at T1+  y = 1[semantic label in {'office','meeting'}]
                  labels assigned iid, independent of geometry/connectivity
  planted_door    readable at T2+  y = 1[node has >= 1 incident 'room-room door']
                  door subtypes assigned iid, so y is invisible below T2
  planted_attr    readable at T3+  y = 1[n_subnodes >= 3]; n_subnodes drawn iid,
                  carried ONLY in the T3+ measured-attr block
  planted_delta   readable at T4+  y = 1[#out-restricted >= #in-restricted]
                  (node-relative orientation, matching probes/featurize.py)
  planted_zone    readable at T5   y = zone 'secret' bit; zones are random
                  (non-geometric) partitions; secrets BALANCED per building
                  (D-013: uneven base rates opened a control-leak channel)

Buildings are corridor-spine floorplans: corridor-main chain, rooms attached via
door nodes (subtyped), a couple of transitions (stairs), direct room-room passage
edges, containment rooms/corridors -> zones -> wings.
"""

from __future__ import annotations

import numpy as np

from topospec.graphs.schema import Edge, Node, SpectrumGraph

PLANTED_TARGETS = (
    "planted_degree",
    "planted_label",
    "planted_door",
    "planted_attr",
    "planted_delta",
    "planted_zone",
)

# The tier at which each planted target becomes readable (ground truth for A0).
PLANTED_SATURATION_LEVEL = {
    "planted_degree": 0,
    "planted_label": 1,
    "planted_door": 2,
    "planted_attr": 3,
    "planted_delta": 4,
    "planted_zone": 5,
}

ROOM_LABELS = ("office", "lab", "storage", "meeting")
DOOR_SUBTYPES = (
    "room-corridor door",
    "room-room door",
    "corridor-corridor door",
    "exit door",
)


def generate_building(
    rng: np.random.Generator,
    building_id: str,
    n_rooms: int = 24,
    n_corridors: int = 4,
    n_zones: int = 4,
    n_wings: int = 2,
) -> SpectrumGraph:
    """Generate one synthetic building at T5 (validate_graph-clean)."""
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    containment: dict[str, str] = {}

    corridors = [f"c{i}" for i in range(n_corridors)]
    rooms = [f"r{i}" for i in range(n_rooms)]

    for i, cid in enumerate(corridors):
        nodes[cid] = Node(
            id=cid,
            kind="corridor",
            area=float(rng.uniform(15, 40)),
            centroid=(float(i * 10.0), 0.0),
            label="corridor",
            attrs=_measures(rng),
        )
    # corridor spine: door nodes between consecutive corridor mains
    for j, (a, b) in enumerate(zip(corridors, corridors[1:], strict=False)):
        did = f"cd{j}"
        nodes[did] = Node(id=did, kind="door", label="corridor-corridor door")
        edges.append(Edge(u=a, v=did))
        edges.append(Edge(u=did, v=b))

    # rooms attach to a corridor through a door node (subtype planted iid later)
    for j, rid in enumerate(rooms):
        c_idx = j % n_corridors
        side = 1.0 if (j // n_corridors) % 2 == 0 else -1.0
        nodes[rid] = Node(
            id=rid,
            kind="room",
            area=float(rng.uniform(8, 30)),
            centroid=(
                float(c_idx * 10.0 + rng.uniform(-3, 3)),
                float(side * (2 + j // (2 * n_corridors))),
            ),
            label=str(rng.choice(ROOM_LABELS)),
            attrs=_measures(rng),
        )
        did = f"d{j}"
        nodes[did] = Node(id=did, kind="door", label="room-corridor door")
        edges.append(Edge(u=rid, v=did))
        edges.append(Edge(u=did, v=corridors[c_idx]))

    # transitions: two stair cores hanging off the corridor ends
    for t, cid in enumerate((corridors[0], corridors[-1])):
        tid = f"t{t}"
        nodes[tid] = Node(
            id=tid,
            kind="transition",
            area=float(rng.uniform(6, 12)),
            centroid=(float((0 if t == 0 else (n_corridors - 1)) * 10.0), -3.0),
            label="stairs",
            attrs=_measures(rng),
        )
        edges.append(Edge(u=tid, v=cid))

    # extra room-room doors + a few direct passages (open connections, no door)
    n_extra = max(2, n_rooms // 6)
    existing = {e.key() for e in edges}
    for _ in range(n_extra):
        a, b = rng.choice(n_rooms, size=2, replace=False)
        ra, rb = rooms[min(a, b)], rooms[max(a, b)]
        did = f"rr{ra}_{rb}"
        if (ra, did) in existing or did in nodes:
            continue
        nodes[did] = Node(id=did, kind="door", label="room-room door")
        edges.append(Edge(u=ra, v=did))
        edges.append(Edge(u=did, v=rb))
    for _ in range(max(2, n_rooms // 6)):
        a, b = rng.choice(n_rooms, size=2, replace=False)
        e = Edge(u=rooms[min(a, b)], v=rooms[max(a, b)])
        if all(e.key() != k for k in (x.key() for x in edges)):
            edges.append(e)  # direct open passage

    # --- plant door subtypes: REASSIGN all door labels iid (independence)
    for n in nodes.values():
        if n.kind == "door":
            n.label = str(rng.choice(DOOR_SUBTYPES))

    # --- plant deltas: iid on all edges
    for e in edges:
        e.delta = str(rng.choice(["both", "forward", "backward"]))

    # --- containment: random (non-geometric) zone partition, zones -> wings
    zones = [f"z{i}" for i in range(n_zones)]
    wings = [f"w{i}" for i in range(n_wings)]
    # BALANCED zone secrets per building (D-013): uneven base rates open a
    # control-leak channel through building-identifying T5 features. The odd
    # leftover is randomized — a deterministic [i % 2] pool systematically
    # over-produces 0s for odd zone counts and biases the corpus marginal.
    secret_pool = [0, 1] * (n_zones // 2)
    if n_zones % 2:
        secret_pool.append(int(rng.integers(0, 2)))
    rng.shuffle(secret_pool)
    for zid, secret in zip(zones, secret_pool, strict=True):
        nodes[zid] = Node(
            id=zid,
            kind="zone",
            label="zone",
            attrs={"secret": int(secret), "zone_size": 0},
        )
    for wid in wings:
        nodes[wid] = Node(id=wid, kind="wing", label="wing", attrs={})
    wing_assign = [wings[i % n_wings] for i in range(n_zones)]
    rng.shuffle(wing_assign)
    for zid, wid in zip(zones, wing_assign, strict=True):
        containment[zid] = wid
    spaces = rooms + corridors + [f"t{t}" for t in range(2)]
    for sid in spaces:
        zid = str(rng.choice(zones))
        containment[sid] = zid
        nodes[zid].attrs["zone_size"] += 1

    g = SpectrumGraph(
        level=5,
        building_id=building_id,
        nodes=nodes,
        edges=edges,
        containment=containment,
        meta={"source": "topospec.data.synthetic", "family": "corridor-spine-v2"},
    )
    return g


def _measures(rng: np.random.Generator) -> dict:
    """T3 measured-attr block; n_subnodes is the planted_attr carrier (iid)."""
    return {
        "eq_radius": float(rng.uniform(1.0, 4.0)),
        "inradius": float(rng.uniform(0.5, 2.0)),
        "n_subnodes": int(rng.integers(0, 6)),
        "n_doors": 0,  # filled after door wiring if needed; kept simple
    }


def planted_labels(g: SpectrumGraph, target: str) -> dict[str, int]:
    """Ground-truth labels for room nodes of a T5 synthetic building."""
    if target not in PLANTED_TARGETS:
        raise ValueError(f"unknown planted target {target!r}; options {PLANTED_TARGETS}")
    rooms = [nid for nid, n in g.nodes.items() if n.kind == "room"]
    labels: dict[str, int] = {}

    if target == "planted_degree":
        from topospec.graphs.levels import forget

        g0 = forget(g, 0)  # define on the T0 skeleton so the target is tier-invariant
        deg = {nid: len(g0.neighbors(nid)) for nid in rooms}
        labels = {nid: int(deg[nid] >= 2) for nid in rooms}  # fixed global threshold

    elif target == "planted_label":
        for nid in rooms:
            labels[nid] = int(g.nodes[nid].label in ("office", "meeting"))

    elif target == "planted_door":
        for nid in rooms:
            has_rr = any(
                g.nodes[x].kind == "door" and g.nodes[x].label == "room-room door"
                for x in g.neighbors(nid)
            )
            labels[nid] = int(has_rr)

    elif target == "planted_attr":
        for nid in rooms:
            labels[nid] = int(g.nodes[nid].attrs.get("n_subnodes", 0) >= 3)

    elif target == "planted_delta":
        # node-relative orientation, matching probes/featurize.py delta_counts
        for nid in rooms:
            out_r = sum(
                1
                for e in g.edges
                if (e.u == nid and e.delta == "forward")
                or (e.v == nid and e.delta == "backward")
            )
            in_r = sum(
                1
                for e in g.edges
                if (e.u == nid and e.delta == "backward")
                or (e.v == nid and e.delta == "forward")
            )
            labels[nid] = int(out_r >= in_r)

    elif target == "planted_zone":
        for nid in rooms:
            zid = g.ancestor_of_kind(nid, "zone")
            if zid is None:
                raise ValueError(f"room {nid} has no zone ancestor")
            labels[nid] = int(g.nodes[zid].attrs["secret"])

    return labels


def generate_corpus(
    rng: np.random.Generator, n_buildings: int = 60, **kwargs
) -> list[SpectrumGraph]:
    """A corpus of synthetic T5 buildings (sizes jittered around the defaults)."""
    out = []
    for b in range(n_buildings):
        n_rooms = int(rng.integers(16, 36))
        g = generate_building(
            rng,
            building_id=f"syn:{b:04d}",
            n_rooms=n_rooms,
            n_corridors=int(rng.integers(3, 6)),
            n_zones=int(rng.integers(3, 6)),
            n_wings=2,
            **kwargs,
        )
        out.append(g)
    return out
