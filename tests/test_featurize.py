"""Interface enforcement per tier (schema v2) + feature layout."""

import copy

import numpy as np
import pytest

from topospec.graphs.levels import forget
from topospec.probes.featurize import (
    edge_feature_dim,
    feature_dim,
    featurize,
    zone_secret_column,
)


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4, 5])
def test_feature_dims_match_declaration(building, level):
    g = forget(building, level)
    fg = featurize(g, with_pe=True, n_pe=4)
    assert fg.x.shape == (len(fg.node_ids), feature_dim(level, with_pe=True, n_pe=4))
    assert fg.edge_attr.shape[1] == edge_feature_dim(level)


def test_feature_dims_strictly_increase_with_tier():
    dims = [feature_dim(k) for k in range(6)]
    assert dims == sorted(dims)
    assert len(set(dims)) == 6


def test_no_label_leak_below_t1(building):
    """T0 features must be invariant to semantic relabeling."""
    g_b = copy.deepcopy(building)
    for n in g_b.nodes.values():
        if n.kind == "room":
            n.label = "office"
    fa = featurize(forget(building, 0))
    fb = featurize(forget(g_b, 0))
    np.testing.assert_array_equal(fa.x, fb.x)


def test_no_door_subtype_leak_below_t2(building):
    """T1 features and structure invariant to door-subtype changes (doors absent)."""
    g_b = copy.deepcopy(building)
    for n in g_b.nodes.values():
        if n.kind == "door":
            n.label = "exit door"
    fa = featurize(forget(building, 1))
    fb = featurize(forget(g_b, 1))
    np.testing.assert_array_equal(fa.x, fb.x)
    np.testing.assert_array_equal(fa.edge_index, fb.edge_index)


def test_no_measure_leak_below_t3(building):
    g_b = copy.deepcopy(building)
    for n in g_b.nodes.values():
        if n.kind == "room":
            n.attrs = dict(n.attrs, n_subnodes=5)
            n.area = 999.0
    fa = featurize(forget(building, 2))
    fb = featurize(forget(g_b, 2))
    np.testing.assert_array_equal(fa.x, fb.x)


def test_no_delta_leak_below_t4(building):
    g_b = copy.deepcopy(building)
    for e in g_b.edges:
        e.delta = "forward"
    fa = featurize(forget(building, 3))
    fb = featurize(forget(g_b, 3))
    np.testing.assert_array_equal(fa.x, fb.x)
    np.testing.assert_array_equal(fa.edge_index, fb.edge_index)


def test_no_zone_leak_below_t5(building):
    g_b = copy.deepcopy(building)
    for n in g_b.nodes.values():
        if n.kind == "zone":
            n.attrs["secret"] = 1 - int(n.attrs["secret"])
    fa = featurize(forget(building, 4))
    fb = featurize(forget(g_b, 4))
    np.testing.assert_array_equal(fa.x, fb.x)


def test_direction_materialized_at_t4(building):
    g4 = forget(building, 4)
    fg = featurize(g4)
    n_both = sum(1 for e in g4.edges if e.delta == "both")
    n_restricted = len(g4.edges) - n_both
    assert fg.edge_index.shape[1] == 2 * n_both + n_restricted


def test_zone_secret_column_reads_planted_zone(building):
    from topospec.data.synthetic import planted_labels

    fg = featurize(building)  # T5
    lab = planted_labels(building, "planted_zone")
    col = zone_secret_column()
    for nid, y in lab.items():
        assert int(fg.x[fg.node_pos[nid], col] > 0.5) == y


def test_door_counts_present_at_t2(building):
    g2 = forget(building, 2)
    fg = featurize(g2)
    # door-count block starts after geom(2)+kind(4)+label(8) = 14; width 4
    block = fg.x[:, 14:18]
    room_rows = [fg.node_pos[nid] for nid, n in g2.nodes.items() if n.kind == "room"]
    assert block[room_rows].sum() > 0  # rooms see their incident doors


def test_featurize_is_deterministic(building):
    fa = featurize(building, with_pe=True)
    fb = featurize(building, with_pe=True)
    np.testing.assert_array_equal(fa.x, fb.x)
    np.testing.assert_array_equal(fa.edge_index, fb.edge_index)
