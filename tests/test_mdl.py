"""Prequential MDL sanity (plan §4.3, §8)."""

import numpy as np

from tests.test_vinfo import _toy_dataset
from topospec.probes.families import LinearFamily
from topospec.vinfo.mdl import prequential_codelength


def test_informative_data_compresses(rng):
    ds = _toy_dataset(rng, n_graphs=16, informative=True, noise=0.0)
    res = prequential_codelength(LinearFamily(), ds, rng)
    assert res.codelength_nats < res.uniform_codelength_nats
    assert res.compression_ratio > 1.5


def test_random_labels_do_not_compress(rng):
    ds = _toy_dataset(rng, n_graphs=16, informative=False)
    res = prequential_codelength(LinearFamily(), ds, rng)
    # codelength within a few percent of the uniform code (no usable signal)
    assert res.compression_ratio < 1.1


def test_block_accounting(rng):
    ds = _toy_dataset(rng, n_graphs=16, informative=True)
    res = prequential_codelength(LinearFamily(), ds, rng)
    n_total = sum((y >= 0).sum() for y in ds.labels)
    assert sum(res.block_sizes) == n_total
    assert abs(sum(res.block_ce_sums) - res.codelength_nats) < 1e-9
    assert res.block_ce_sums[0] == res.block_sizes[0] * np.log(2)
