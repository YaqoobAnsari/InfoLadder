"""MSD loader (DATA-3): mapping correctness, level validity, refinement, zones.

The synthetic tests build a tiny MSD-shaped networkx graph in-code (no torch, no
pickle) so the mapping logic is exercised deterministically; the fixture test runs
the real shipped pickle end-to-end.
"""

import json

import networkx as nx
import pytest

from topospec.data.msd import (
    ROOM_NAMES,
    build_graphs,
    load_plan,
    plan_to_graph,
)
from topospec.graphs.levels import forget
from topospec.graphs.schema import CONTAINMENT_RANK
from topospec.graphs.validate import validate_graph

pytestmark = pytest.mark.skip(
    reason="MSD loader quarantined pending schema-v2 migration (D-014); its role "
    "moves to pipeline-validation source"
)

FIXTURE = "1068"


def _rt(name):  # room-type index for a room name
    return ROOM_NAMES.index(name)


def _msd_graph():
    """A 3-space MSD-shape plan: Bedroom -door- Corridor -passage- Bathroom,
    plus an entrance edge onto the corridor. Geometry is a unit square scaled."""
    g = nx.Graph()

    def sq(cx, cy, s):  # closed square ring of side s centered at (cx,cy)
        h = s / 2
        return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h), (cx - h, cy - h)]

    g.add_node(0, room_type=_rt("Bedroom"), geometry=sq(0, 0, 2.0), centroid=[0.0, 0.0])
    g.add_node(1, room_type=_rt("Corridor"), geometry=sq(3, 0, 2.0), centroid=[3.0, 0.0])
    g.add_node(2, room_type=_rt("Bathroom"), geometry=sq(6, 0, 2.0), centroid=[6.0, 0.0])
    g.add_node(3, room_type=_rt("Stairs"), geometry=sq(3, 4, 2.0), centroid=[3.0, 4.0])
    g.add_edge(0, 1, connectivity="door")
    g.add_edge(1, 2, connectivity="passage")
    g.add_edge(1, 3, connectivity="entrance")
    return g


@pytest.fixture(scope="module")
def g4():
    return plan_to_graph(_msd_graph(), "synthetic", zone_mode="category")


def test_r4_validates_and_maps_kinds_and_labels(g4):
    assert validate_graph(g4)
    assert g4.level == 4
    assert g4.building_id == "msd:synthetic"
    spaces = {n.id: n for n in g4.nodes.values() if n.kind in ("room", "corridor")}
    assert len(spaces) == 4
    assert spaces["a1"].kind == "corridor" and spaces["a1"].label == "Corridor"
    assert spaces["a0"].kind == "room" and spaces["a0"].label == "Bedroom"


def test_area_is_shoelace(g4):
    # 2.0-side square -> 4.0 m^2
    assert abs(g4.nodes["a0"].area - 4.0) < 1e-9


def test_tau_mapping(g4):
    r2 = forget(g4, 2)
    taus = {tuple(sorted((e.u, e.v))): e.tau for e in r2.edges}
    assert taus[("a0", "a1")] == "door"  # door
    assert taus[("a1", "a2")] == "corridor-link"  # passage
    assert taus[("a1", "a3")] == "door"  # entrance -> door


def test_room_nodes_have_no_attrs_so_r3_valid(g4):
    """Zone info must live only on zone nodes; forgetting to R3 must validate."""
    for n in g4.nodes.values():
        if n.kind in ("room", "corridor"):
            assert n.attrs == {}
    assert validate_graph(forget(g4, 3))


def test_zone_containment_forest(g4):
    zones = {nid: n for nid, n in g4.nodes.items() if n.kind == "zone"}
    assert zones  # Zone1 (bedroom), Zone2 (corridor), Zone3 (bath+stairs)
    for space_id, parent in g4.containment.items():
        assert parent in zones
        assert CONTAINMENT_RANK["zone"] > CONTAINMENT_RANK[g4.nodes[space_id].kind]
    # every space is contained
    spaces = {nid for nid, n in g4.nodes.items() if n.kind in ("room", "corridor")}
    assert spaces <= set(g4.containment)


def test_forget_chain_equals_direct_and_r0_strips(g4):
    assert forget(g4, 2).structurally_equal(forget(forget(g4, 3), 2))
    r0 = forget(g4, 0)
    assert all(n.kind is None and not n.attrs for n in r0.nodes.values())
    assert all(e.tau is None and e.delta is None for e in r0.edges)
    assert not r0.containment
    # spaces survive to R0; zone nodes do not
    assert set(r0.nodes) == {"a0", "a1", "a2", "a3"}


def test_all_levels_validate_and_json_roundtrip(g4, tmp_path):
    from topospec.graphs.serializers.json_io import load_graph, save_graph

    for lvl in (0, 1, 2, 3, 4):
        gk = forget(g4, lvl)
        assert validate_graph(gk)
        p = tmp_path / f"r{lvl}.json"
        save_graph(gk, p)
        assert gk.structurally_equal(load_graph(p))


def test_apartment_mode_cuts_entrance_edges():
    """Apartment = access component after removing entrance edges -> Stairs splits off."""
    g = plan_to_graph(_msd_graph(), "synthetic", zone_mode="apartment")
    # a3 (Stairs) is joined only by an entrance edge -> its own unit
    z_of = g.containment
    assert z_of["a3"] != z_of["a0"]
    assert z_of["a0"] == z_of["a1"] == z_of["a2"]


def test_too_few_areas_raises():
    from topospec.data.msd import MsdPlanError

    g = nx.Graph()
    g.add_node(0, room_type=_rt("Bedroom"), geometry=[(0, 0), (1, 0), (1, 1)], centroid=[0.5, 0.5])
    with pytest.raises(MsdPlanError):
        plan_to_graph(g, "tiny")


# --------------------------------------------------------------- real fixture
@pytest.fixture(scope="module")
def fixture_pickle():
    from pathlib import Path

    p = Path(__file__).parent / "fixtures" / "msd" / f"{FIXTURE}.pickle"
    if not p.exists():
        pytest.skip(f"fixture {p} not present")
    return p


def test_fixture_end_to_end(fixture_pickle):
    g4 = plan_to_graph(load_plan(fixture_pickle), FIXTURE, zone_mode="category")
    assert validate_graph(g4)
    spaces = [n for n in g4.nodes.values() if n.kind in ("room", "corridor")]
    assert len(spaces) == 15
    assert any(n.kind == "corridor" for n in spaces)
    assert {e.tau for e in forget(g4, 2).edges} == {"door", "corridor-link"}
    for lvl in (0, 1, 2, 3, 4):
        assert validate_graph(forget(g4, lvl))
    assert all(n.area is not None and n.area > 0 for n in spaces)


def test_build_graphs_writes_levels_and_logs_exclusions(fixture_pickle, tmp_path):
    import shutil

    raw = tmp_path / "raw"
    (raw / "graph_out").mkdir(parents=True)
    shutil.copy(fixture_pickle, raw / "graph_out" / f"{FIXTURE}.pickle")
    # a deliberately malformed plan -> must be excluded, not crash
    import pickle

    bad = nx.Graph()
    bad.add_node(0, room_type=_rt("Bedroom"), geometry=[(0, 0), (1, 0), (1, 1)], centroid=[0.0, 0.0])
    (raw / "graph_out" / "bad.pickle").write_bytes(pickle.dumps(bad))

    out = tmp_path / "derived"
    built = build_graphs(raw, out, zone_mode="category")
    assert len(built) == 1  # bad plan excluded
    for lvl in range(5):
        assert (out / f"{FIXTURE}.r{lvl}.json").exists()
    excl = [json.loads(x) for x in (out / "exclusions.jsonl").read_text().splitlines() if x.strip()]
    assert len(excl) == 1 and excl[0]["native_id"] == "bad"
