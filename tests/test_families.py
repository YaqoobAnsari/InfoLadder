"""Probe family contracts: budgets, probability outputs, registry (plan §8, §4.4)."""

import numpy as np
import pytest

from tests.test_vinfo import _split, _toy_dataset
from topospec.probes.families import (
    GNNFamily,
    LinearFamily,
    PriorFamily,
    assert_architecture_parity,
    make_family,
)
from topospec.probes.featurize import feature_dim


def test_make_family_registry():
    for name, cls in [("V1", PriorFamily), ("V2", LinearFamily)]:
        assert isinstance(make_family(name), cls)
    assert make_family("V4").n_layers == 1
    assert make_family("V5").n_layers == 2
    with pytest.raises(KeyError):
        make_family("V99")


def test_v6_is_explicit_stub():
    fam = make_family("V6")
    with pytest.raises(NotImplementedError, match="INFRA-8"):
        fam.param_count(10, 2)


def test_probabilities_are_valid(rng):
    ds = _toy_dataset(rng)
    tr, va, te = _split(ds)
    for fam in (PriorFamily(), LinearFamily()):
        probe = fam.fit(tr, va, rng)
        for p in probe.predict_proba(te):
            assert p.shape[1] == 2
            assert np.all(p >= 0)
            np.testing.assert_allclose(p.sum(axis=1), 1.0, atol=1e-6)


def test_architecture_parity_across_levels():
    """Fairness §4.4: same architecture; param count varies only via input dim."""
    fam = GNNFamily(n_layers=2)
    dims = {lvl: feature_dim(lvl) for lvl in range(5)}
    counts = assert_architecture_parity(fam, dims, n_classes=2)
    assert set(counts) == set(range(5))
    # hidden-layer params identical: differences only in the input layer
    deltas = {
        lvl: counts[lvl] - counts[0] for lvl in range(1, 5)
    }
    for lvl, d in deltas.items():
        expected = (dims[lvl] - dims[0]) * 2 * fam.hidden  # w_m and w_s input rows
        assert d == expected


def test_gnn_param_count_matches_torch(rng):
    ds = _toy_dataset(rng, n_graphs=6, n_nodes=10)
    tr, va, _te = _split(ds)
    fam = GNNFamily(n_layers=1, max_epochs=2, patience=1)
    probe = fam.fit(tr, va, rng)
    n_torch = sum(p.numel() for p in probe.model.parameters())
    # declared count uses edge_dim=0; toy edge_attr dim is 0, so they must agree
    assert n_torch == fam.param_count(4, 2)
