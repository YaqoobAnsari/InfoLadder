"""Tesseract2 tier factory (D-011/D-014): navigation JSON -> T3..T0."""

from pathlib import Path

import pytest

from topospec.data.tesseract import (
    TesseractGraphError,
    build_t3,
    build_tiers,
    load_graph_json,
)
from topospec.graphs.validate import validate_graph

FIXTURE = Path(__file__).parent / "fixtures" / "tesseract" / "FF_part_2up_post_pruning.json"


@pytest.fixture(scope="module")
def t3():
    return build_t3(FIXTURE)


@pytest.fixture(scope="module")
def tiers():
    return build_tiers(FIXTURE)


def test_t3_validates(t3):
    assert t3.level == 3
    assert validate_graph(t3)


def test_space_contraction(t3):
    """35 main rooms survive; 90 subnodes and 471 corridor waypoints contract."""
    rooms = [n for n in t3.nodes.values() if n.kind == "room"]
    corridors = [n for n in t3.nodes.values() if n.kind == "corridor"]
    assert len(rooms) == 35
    assert 1 <= len(corridors) <= 5
    assert t3.meta["n_subnodes_contracted"] == 90


def test_t3_measures_present(t3):
    rooms = [n for n in t3.nodes.values() if n.kind == "room"]
    assert sum(1 for n in rooms if n.area and n.area > 0) >= 30
    assert all("n_subnodes" in n.attrs and "n_doors" in n.attrs for n in rooms)
    assert any(n.attrs["n_doors"] > 0 for n in rooms)
    corridors = [n for n in t3.nodes.values() if n.kind == "corridor"]
    assert all(n.attrs.get("n_subnodes", 0) > 0 for n in corridors)  # extent proxy


def test_doors_present_and_subtyped(t3):
    doors = {nid: n for nid, n in t3.nodes.items() if n.kind == "door"}
    assert len(doors) >= 30  # 43 detected; outside-only ones may drop
    assert any(n.label == "exit door" for n in doors.values())
    subtypes = {n.label for n in doors.values()}
    assert "room-corridor door" in subtypes


def test_all_tiers_validate_and_nest(tiers):
    assert set(tiers) == {0, 1, 2, 3}
    for lvl, g in tiers.items():
        assert g.level == lvl
        assert validate_graph(g)
    # T1 has no doors; T2 has the doors
    assert not any(n.kind == "door" for n in tiers[1].nodes.values())
    assert any(n.kind == "door" for n in tiers[2].nodes.values())
    # T0 untyped skeleton, same space count as T1
    assert all(n.kind is None for n in tiers[0].nodes.values())
    assert len(tiers[0].nodes) == len(tiers[1].nodes)
    assert len(tiers[0].edges) > 0


def test_connectivity_is_meaningful(tiers):
    """Most rooms must reach a corridor at T1 (doors contracted to direct edges)."""
    import networkx as nx

    g1 = tiers[1]
    nxg = nx.Graph()
    for e in g1.edges:
        nxg.add_edge(e.u, e.v)
    corridor_ids = [nid for nid, n in g1.nodes.items() if n.kind == "corridor"]
    room_ids = [nid for nid, n in g1.nodes.items() if n.kind == "room" and nid in nxg]
    reachable = sum(
        1 for r in room_ids if any(nx.has_path(nxg, r, c) for c in corridor_ids if c in nxg)
    )
    assert reachable >= 0.8 * len(room_ids)


def test_rejects_summary_export(tmp_path):
    p = tmp_path / "summary.json"
    p.write_text('{"nodes": [{"id": "room_1", "type": "room", "position": [0, 0]}], "edges": []}')
    with pytest.raises(TesseractGraphError, match="no edges"):
        load_graph_json(p)


def test_provenance_stamped(t3):
    meta = t3.meta
    assert meta["source"] == "topospec.data.tesseract"
    assert "Tesseract2" in meta["pipeline"]
    assert meta["n_doors"] == 43
