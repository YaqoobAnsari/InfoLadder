"""Tesseract2 adapter (user directive; plan §3.3): navigation JSON -> R2 graph."""

from pathlib import Path

import pytest

from topospec.data.tesseract import (
    TesseractGraphError,
    build_r2,
    load_graph_json,
    to_spectrum_graph,
)
from topospec.graphs.levels import forget
from topospec.graphs.validate import validate_graph

FIXTURE = Path(__file__).parent / "fixtures" / "tesseract" / "FF_part_2up_post_pruning.json"


@pytest.fixture(scope="module")
def graph():
    return build_r2(FIXTURE)


def test_validates_at_r2(graph):
    assert graph.level == 2
    assert validate_graph(graph)


def test_space_contraction(graph):
    """35 main rooms survive; 90 subnodes and 471 corridor waypoints contract."""
    rooms = [n for n in graph.nodes.values() if n.kind == "room"]
    corridors = [n for n in graph.nodes.values() if n.kind == "corridor"]
    assert len(rooms) == 35
    assert 1 <= len(corridors) <= 5  # 471 waypoints -> few corridor components
    assert graph.meta["n_subnodes_contracted"] == 90


def test_doors_present_and_typed(graph):
    doors = {nid: n for nid, n in graph.nodes.items() if n.kind == "door"}
    assert len(doors) >= 30  # 43 detected; a few outside-only ones may drop
    assert any(n.label == "exit door" for n in doors.values())
    # every door edge is tau='door'; space-space passages are 'corridor-link'
    door_ids = set(doors)
    for e in graph.edges:
        if e.u in door_ids or e.v in door_ids:
            assert e.tau == "door"
        else:
            assert e.tau == "corridor-link"


def test_no_outside_nodes(graph):
    assert graph.meta["n_outside_dropped"] == 43
    assert all(n.kind in ("room", "corridor", "door") for n in graph.nodes.values())


def test_rooms_carry_geometry(graph):
    rooms = [n for n in graph.nodes.values() if n.kind == "room"]
    assert all(n.centroid is not None for n in rooms)
    assert sum(1 for n in rooms if n.area and n.area > 0) >= 30


def test_forgetting_chain(graph):
    g0 = forget(graph, 0)
    assert validate_graph(g0)
    # doors contract away; rooms + corridor spaces remain, connectivity survives
    assert len(g0.nodes) == sum(
        1 for n in graph.nodes.values() if n.kind in ("room", "corridor")
    )
    assert len(g0.edges) > 0


def test_rejects_summary_export(tmp_path):
    p = tmp_path / "summary.json"
    p.write_text('{"nodes": [{"id": "room_1", "type": "room", "position": [0, 0]}], "edges": []}')
    with pytest.raises(TesseractGraphError, match="no edges"):
        load_graph_json(p)


def test_connectivity_is_meaningful(graph):
    """Most rooms must reach a corridor through a door (navigable building)."""
    import networkx as nx

    nxg = nx.Graph()
    for e in graph.edges:
        nxg.add_edge(e.u, e.v)
    corridor_ids = [nid for nid, n in graph.nodes.items() if n.kind == "corridor"]
    room_ids = [nid for nid, n in graph.nodes.items() if n.kind == "room" and nid in nxg]
    reachable = sum(
        1 for r in room_ids if any(nx.has_path(nxg, r, c) for c in corridor_ids if c in nxg)
    )
    assert reachable >= 0.8 * len(room_ids)


def test_provenance_stamped(graph):
    meta = graph.meta
    assert meta["source"] == "topospec.data.tesseract"
    assert "Tesseract2" in meta["pipeline"]
    assert meta["n_doors"] == 43
