"""Interface enforcement (src/topospec/CLAUDE.md invariant 2) + feature layout."""

import numpy as np
import pytest

from topospec.graphs.levels import forget
from topospec.probes.featurize import (
    edge_feature_dim,
    feature_dim,
    featurize,
    zone_secret_column,
)


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_feature_dims_match_declaration(building, level):
    g = forget(building, level)
    fg = featurize(g, with_pe=True, n_pe=4)
    assert fg.x.shape == (len(fg.node_ids), feature_dim(level, with_pe=True, n_pe=4))
    assert fg.edge_attr.shape[1] == edge_feature_dim(level)


def test_feature_dims_strictly_increase_with_level():
    dims = [feature_dim(k) for k in range(5)]
    assert dims == sorted(dims)
    assert len(set(dims)) == 5


def test_no_tau_leak_below_r2(building):
    """R0/R1 features must be invariant to edge-type re-assignment (plan §8)."""
    import copy

    g_a = copy.deepcopy(building)
    g_b = copy.deepcopy(building)
    for e in g_b.edges:
        e.tau = "wall" if e.tau != "wall" else "door"
    for level in (0, 1):
        fa = featurize(forget(g_a, level))
        fb = featurize(forget(g_b, level))
        np.testing.assert_array_equal(fa.x, fb.x)
        np.testing.assert_array_equal(fa.edge_attr, fb.edge_attr)


def test_no_delta_leak_below_r3(building):
    import copy

    g_b = copy.deepcopy(building)
    for e in g_b.edges:
        e.delta = "forward"
    fa = featurize(forget(building, 2))
    fb = featurize(forget(g_b, 2))
    np.testing.assert_array_equal(fa.x, fb.x)
    np.testing.assert_array_equal(fa.edge_attr, fb.edge_attr)
    np.testing.assert_array_equal(fa.edge_index, fb.edge_index)


def test_no_zone_leak_below_r4(building):
    import copy

    g_b = copy.deepcopy(building)
    for n in g_b.nodes.values():
        if n.kind == "zone":
            n.attrs["secret"] = 1 - int(n.attrs["secret"])
    fa = featurize(forget(building, 3))
    fb = featurize(forget(g_b, 3))
    np.testing.assert_array_equal(fa.x, fb.x)


def test_direction_materialized_at_r3(building):
    g3 = forget(building, 3)
    fg = featurize(g3)
    n_both = sum(1 for e in g3.edges if e.delta == "both")
    n_restricted = len(g3.edges) - n_both
    assert fg.edge_index.shape[1] == 2 * n_both + n_restricted


def test_zone_secret_column_reads_planted_zone(building):
    from topospec.data.synthetic import planted_labels

    fg = featurize(building)  # R4
    lab = planted_labels(building, "planted_zone")
    col = zone_secret_column()
    for nid, y in lab.items():
        assert int(fg.x[fg.node_pos[nid], col] > 0.5) == y


def test_featurize_is_deterministic(building):
    fa = featurize(building, with_pe=True)
    fb = featurize(building, with_pe=True)
    np.testing.assert_array_equal(fa.x, fb.x)
    np.testing.assert_array_equal(fa.edge_index, fb.edge_index)
