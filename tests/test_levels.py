"""Strict-refinement invariants for the T0..T5 ladder (claim C1; schema v2)."""

import numpy as np
import pytest

from topospec.graphs.levels import forget
from topospec.graphs.schema import HIERARCHY_KINDS
from topospec.graphs.validate import SchemaError, validate_graph


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4, 5])
def test_forget_outputs_validate_at_target_level(building, level):
    g = forget(building, level)
    assert g.level == level
    assert validate_graph(g)


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_forget_is_idempotent(building, level):
    once = forget(building, level)
    twice = forget(once, level)
    assert once.structurally_equal(twice)


def test_forget_is_deterministic(building):
    a = forget(building, 0)
    b = forget(building, 0)
    assert a.structurally_equal(b)


def test_forget_chain_equals_direct(building):
    """phi composition: forgetting 5->2 equals 5->4->3->2 (nestedness)."""
    direct = forget(building, 2)
    chained = forget(forget(forget(building, 4), 3), 2)
    assert direct.structurally_equal(chained)


def test_forget_upward_raises(building):
    g1 = forget(building, 1)
    with pytest.raises(ValueError):
        forget(g1, 3)


def test_t0_is_untyped_skeleton(building):
    g0 = forget(building, 0)
    assert all(n.kind is None and n.label is None and not n.attrs for n in g0.nodes.values())
    assert all(n.area is None for n in g0.nodes.values())
    assert all(e.delta is None for e in g0.edges)
    assert not g0.containment
    # centroids survive to T0 (spatial layout is preserved at every tier)
    assert sum(1 for n in g0.nodes.values() if n.centroid is not None) >= len(g0.nodes) - 2


def test_t1_adds_kinds_no_doors(building):
    g1 = forget(building, 1)
    kinds = {n.kind for n in g1.nodes.values()}
    assert kinds <= {"room", "corridor", "transition"}
    assert "door" not in kinds
    assert any(n.label for n in g1.nodes.values())


def test_t2_adds_door_nodes(building):
    g2 = forget(building, 2)
    doors = [n for n in g2.nodes.values() if n.kind == "door"]
    assert len(doors) > 0
    assert all(n.area is None and not n.attrs for n in g2.nodes.values())  # T3 content absent


def test_t3_adds_measures(building):
    g3 = forget(building, 3)
    rooms = [n for n in g3.nodes.values() if n.kind == "room"]
    assert all(n.area is not None for n in rooms)
    assert all("n_subnodes" in n.attrs for n in rooms)
    assert all(e.delta is None for e in g3.edges)  # T4 content absent


def test_door_contraction_preserves_connectivity(building):
    """Spaces reachable via a door at T2 stay connected at T1 (contraction)."""
    import networkx as nx

    def nxg(g):
        out = nx.Graph()
        for nid, n in g.nodes.items():
            if n.kind in HIERARCHY_KINDS:
                continue
            out.add_node(nid)
        for e in g.edges:
            out.add_edge(e.u, e.v)
        return out

    g2 = forget(building, 2)
    g1 = forget(building, 1)
    full = nxg(g2)
    contracted = nxg(g1)
    comps_full = {
        frozenset(c - {n for n in c if g2.nodes[n].kind == "door"})
        for c in nx.connected_components(full)
    }
    comps_contr = set(map(frozenset, nx.connected_components(contracted)))
    assert comps_full == comps_contr


def test_validate_rejects_tier_violations(building):
    g3 = forget(building, 3)
    g3.edges[0].delta = "forward"  # delta is T4+
    with pytest.raises(SchemaError):
        validate_graph(g3)

    g1 = forget(building, 1)
    next(iter(g1.nodes.values())).area = 5.0  # area is T3+
    with pytest.raises(SchemaError):
        validate_graph(g1)

    g0 = forget(building, 0)
    next(iter(g0.nodes.values())).kind = "room"  # kinds are T1+
    with pytest.raises(SchemaError):
        validate_graph(g0)


def test_validate_rejects_containment_rank_violation(building):
    zone = next(nid for nid, n in building.nodes.items() if n.kind == "zone")
    wing = next(nid for nid, n in building.nodes.items() if n.kind == "wing")
    building.containment[wing] = zone  # wing under zone: rank inversion
    with pytest.raises(SchemaError):
        validate_graph(building)


def test_json_roundtrip(building, tmp_path):
    from topospec.graphs.serializers.json_io import load_graph, save_graph

    for level in (0, 2, 3, 5):
        g = forget(building, level)
        path = tmp_path / f"t{level}.json"
        save_graph(g, path)
        g2 = load_graph(path)
        assert g.structurally_equal(g2)
        assert validate_graph(g2)


def test_corpus_generation_validates(corpus):
    assert len(corpus) == 16
    for g in corpus:
        assert validate_graph(g)
        rooms = [n for n in g.nodes.values() if n.kind == "room"]
        assert len(rooms) >= 16


def test_planted_labels_cover_all_rooms(building):
    from topospec.data.synthetic import PLANTED_TARGETS, planted_labels

    rooms = {nid for nid, n in building.nodes.items() if n.kind == "room"}
    for target in PLANTED_TARGETS:
        lab = planted_labels(building, target)
        assert set(lab) == rooms
        assert set(lab.values()) <= {0, 1}
        vals = np.array(list(lab.values()))
        assert 0 < vals.mean() < 1, f"{target} degenerate marginal {vals.mean()}"


def test_planted_zone_base_rate_balanced(rng):
    """Per-building zone-label marginals concentrate near 0.5 (D-013)."""
    from topospec.data.synthetic import generate_corpus, planted_labels

    marginals = []
    for g in generate_corpus(rng, n_buildings=30):
        lab = planted_labels(g, "planted_zone")
        marginals.append(np.mean(list(lab.values())))
    marginals = np.array(marginals)
    assert abs(marginals.mean() - 0.5) < 0.06
    assert marginals.std() < 0.18


def test_planted_saturation_map_covers_all_tiers():
    from topospec.data.synthetic import PLANTED_SATURATION_LEVEL

    assert sorted(PLANTED_SATURATION_LEVEL.values()) == [0, 1, 2, 3, 4, 5]
