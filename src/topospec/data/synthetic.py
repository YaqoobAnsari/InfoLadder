"""Phase A0 synthetic families with planted targets — plan §6 Phase A0.

Targets are planted at a KNOWN level by design, so the probing protocol can be
calibrated: the instrument passes only if the estimated I_V surface recovers each
planted saturation level (paper Figure 2).

Planted targets (all binary, on room nodes):
  planted_degree  readable at R0+  y = 1[deg(node) >= 3] on the R0 skeleton
                  (positive control: pure connectivity, visible to GNN probes at R0;
                  FIXED threshold, building-independent, so the target is fully
                  extractable — a per-building threshold would be unknowable to the
                  probe and poison the control with irreducible error)
  planted_tau     readable at R2+  y = 1[#incident tau=door >= #incident tau=wall]
                  taus are assigned iid uniform, independent of geometry/connectivity,
                  so y is (near-)independent of degree -> invisible below R2
  planted_delta   readable at R3+  y = 1[#out-restricted >= #in-restricted] where
                  'out-restricted' is node-relative orientation ((u==n and forward) or
                  (v==n and backward)); deltas iid on edges; invisible below R3
  planted_zone    readable at R4   y = zone 'secret' bit, assigned iid per zone;
                  zones are random partitions (deliberately NOT geometric), so y is
                  invisible below R4; at R4 it is a parameter-free lookup (V0)

Buildings are corridor-spine floorplans: a chain of corridor spaces, rooms attached
via door nodes, wall-adjacency edges between geometric neighbors, containment
rooms/corridors -> zones -> wings.
"""

from __future__ import annotations

import numpy as np

from topospec.graphs.schema import Edge, Node, SpectrumGraph

PLANTED_TARGETS = ("planted_degree", "planted_tau", "planted_delta", "planted_zone")

# The level at which each planted target becomes readable (ground truth for A0).
PLANTED_SATURATION_LEVEL = {
    "planted_degree": 0,
    "planted_tau": 2,
    "planted_delta": 3,
    "planted_zone": 4,
}


def generate_building(
    rng: np.random.Generator,
    building_id: str,
    n_rooms: int = 24,
    n_corridors: int = 4,
    n_zones: int = 4,
    n_wings: int = 2,
) -> SpectrumGraph:
    """Generate one synthetic building at R4 (validate_graph-clean)."""
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
        )
    # corridor spine
    for a, b in zip(corridors, corridors[1:], strict=False):
        edges.append(Edge(u=a, v=b, tau="corridor-link", delta="both"))

    # rooms attach to a corridor through a door node; geometric neighbors share walls
    for j, rid in enumerate(rooms):
        c_idx = j % n_corridors
        side = 1.0 if (j // n_corridors) % 2 == 0 else -1.0
        nodes[rid] = Node(
            id=rid,
            kind="room",
            area=float(rng.uniform(8, 30)),
            centroid=(float(c_idx * 10.0 + rng.uniform(-3, 3)), float(side * (2 + j // (2 * n_corridors)))),
            label=str(rng.choice(["office", "lab", "storage", "meeting"])),
        )
        did = f"d{j}"
        nodes[did] = Node(id=did, kind="door", area=None, centroid=None, label="door")
        edges.append(Edge(u=rid, v=did, tau="door", delta="both"))
        edges.append(Edge(u=did, v=corridors[c_idx], tau="door", delta="both"))

    # wall adjacencies between consecutive rooms on the same corridor+side,
    # plus a random sprinkle of extra room-room door edges
    for j in range(n_rooms - n_corridors):
        if (j // n_corridors) % 2 == (j + n_corridors) // n_corridors % 2:
            pass  # sides handled by the sprinkle below; keep spine simple
        edges.append(Edge(u=rooms[j], v=rooms[j + n_corridors], tau="wall", delta="both"))
    n_extra = max(2, n_rooms // 6)
    for _ in range(n_extra):
        a, b = rng.choice(n_rooms, size=2, replace=False)
        e = Edge(u=rooms[min(a, b)], v=rooms[max(a, b)], tau="wall", delta="both")
        if all(e.key() != x.key() for x in edges):
            edges.append(e)

    # --- plant tau: REASSIGN all room-incident edge taus iid uniform (independence)
    for e in edges:
        ku = nodes[e.u].kind
        kv = nodes[e.v].kind
        if ku == "corridor" and kv == "corridor":
            continue  # keep spine as corridor-link
        e.tau = str(rng.choice(["wall", "door", "corridor-link"]))

    # --- plant delta: iid on all edges
    for e in edges:
        e.delta = str(rng.choice(["both", "forward", "backward"]))

    # --- containment: random (non-geometric) zone partition, zones -> wings
    zones = [f"z{i}" for i in range(n_zones)]
    wings = [f"w{i}" for i in range(n_wings)]
    # BALANCED zone secrets per building (half 0s, half 1s, shuffled): with iid
    # secrets, buildings get uneven label base-rates, and shuffled-label controls
    # can then extract the per-building base rate from building-identifying R4
    # features (zone sizes) — the full A0 run caught exactly this (+0.115 nats on
    # planted_zone_ctrl at R4, slurm job 7207). Balance kills the channel.
    secret_pool = [i % 2 for i in range(n_zones)]
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
    # round-robin then shuffle: every wing owns >=1 zone (validator: no orphan
    # hierarchy nodes), assignment still random
    wing_assign = [wings[i % n_wings] for i in range(n_zones)]
    rng.shuffle(wing_assign)
    for zid, wid in zip(zones, wing_assign, strict=True):
        containment[zid] = wid
    for sid in rooms + corridors:
        zid = str(rng.choice(zones))
        containment[sid] = zid
        nodes[zid].attrs["zone_size"] += 1

    g = SpectrumGraph(
        level=4,
        building_id=building_id,
        nodes=nodes,
        edges=edges,
        containment=containment,
        meta={"source": "topospec.data.synthetic", "family": "corridor-spine"},
    )
    return g


def planted_labels(g: SpectrumGraph, target: str) -> dict[str, int]:
    """Ground-truth labels for room nodes of an R4 synthetic building (plan §6 A0)."""
    if target not in PLANTED_TARGETS:
        raise ValueError(f"unknown planted target {target!r}; options {PLANTED_TARGETS}")
    rooms = [nid for nid, n in g.nodes.items() if n.kind == "room"]
    labels: dict[str, int] = {}

    if target == "planted_degree":
        from topospec.graphs.levels import forget

        g0 = forget(g, 0)  # define on the R0 skeleton so the target is level-invariant
        deg = {nid: len(g0.neighbors(nid)) for nid in rooms}
        labels = {nid: int(deg[nid] >= 3) for nid in rooms}  # fixed global threshold

    elif target == "planted_tau":
        for nid in rooms:
            n_door = sum(1 for e in g.edges if nid in (e.u, e.v) and e.tau == "door")
            n_wall = sum(1 for e in g.edges if nid in (e.u, e.v) and e.tau == "wall")
            labels[nid] = int(n_door >= n_wall)

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
    """A corpus of synthetic R4 buildings (sizes jittered around the defaults)."""
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
