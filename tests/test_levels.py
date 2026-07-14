"""Strict-refinement invariants (claim C1; src/topospec/CLAUDE.md invariant 1)."""

import numpy as np
import pytest

from topospec.graphs.levels import forget
from topospec.graphs.schema import HIERARCHY_KINDS
from topospec.graphs.validate import SchemaError, validate_graph


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_forget_outputs_validate_at_target_level(building, level):
    g = forget(building, level)
    assert g.level == level
    assert validate_graph(g)


@pytest.mark.parametrize("level", [0, 1, 2, 3])
def test_forget_is_idempotent(building, level):
    once = forget(building, level)
    twice = forget(once, level)
    assert once.structurally_equal(twice)


def test_forget_is_deterministic(building):
    a = forget(building, 0)
    b = forget(building, 0)
    assert a.structurally_equal(b)


def test_forget_chain_equals_direct(building):
    """phi composition: forgetting 4->2 equals 4->3->2 (nestedness, plan §4.1)."""
    direct = forget(building, 2)
    chained = forget(forget(building, 3), 2)
    assert direct.structurally_equal(chained)


def test_forget_upward_raises(building):
    g1 = forget(building, 1)
    with pytest.raises(ValueError):
        forget(g1, 3)


def test_r0_has_no_semantics(building):
    g0 = forget(building, 0)
    assert all(n.kind is None and n.label is None and not n.attrs for n in g0.nodes.values())
    assert all(e.tau is None and e.delta is None for e in g0.edges)
    assert not g0.containment


def test_r0_drops_doors_but_preserves_spaces(building):
    g0 = forget(building, 0)
    spaces_r4 = {
        nid
        for nid, n in building.nodes.items()
        if n.kind in ("room", "corridor")
    }
    assert set(g0.nodes) == spaces_r4


def test_r0_connectivity_preserved_through_doors(building):
    """Rooms reachable via a door at R1 stay connected at R0 (contraction)."""
    import networkx as nx

    def nxg(g, skip_doors):
        out = nx.Graph()
        for nid, n in g.nodes.items():
            if n.kind in HIERARCHY_KINDS:
                continue
            out.add_node(nid)
        for e in g.edges:
            out.add_edge(e.u, e.v)
        return out

    g1 = forget(building, 1)
    g0 = forget(building, 0)
    full = nxg(g1, skip_doors=False)
    contracted = nxg(g0, skip_doors=True)
    comps_full = {
        frozenset(c - {n for n in c if g1.nodes[n].kind == "door"})
        for c in nx.connected_components(full)
    }
    comps_contr = set(map(frozenset, nx.connected_components(contracted)))
    assert comps_full == comps_contr


def test_validate_rejects_level_violations(building):
    g2 = forget(building, 2)
    g2.edges[0].delta = "forward"  # delta is R3+
    with pytest.raises(SchemaError):
        validate_graph(g2)

    g0 = forget(building, 0)
    g0.edges[0].tau = "wall"  # tau is R2+
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

    for level in (0, 2, 4):
        g = forget(building, level)
        path = tmp_path / f"r{level}.json"
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
        # non-degenerate marginals (both classes present in a 20-room building)
        vals = np.array(list(lab.values()))
        assert 0 < vals.mean() < 1


def test_planted_zone_base_rate_balanced(rng):
    """Per-building zone-label marginals must concentrate near 0.5 — uneven base
    rates opened a control-leak channel through R4 zone-size features (job 7207)."""
    from topospec.data.synthetic import generate_corpus, planted_labels

    marginals = []
    for g in generate_corpus(rng, n_buildings=30):
        lab = planted_labels(g, "planted_zone")
        marginals.append(np.mean(list(lab.values())))
    marginals = np.array(marginals)
    assert abs(marginals.mean() - 0.5) < 0.06
    assert marginals.std() < 0.18  # room-count jitter only, no zone-count skew
