"""Statistical protocol components (plan §9; docs/EXPERIMENT_PROTOCOL.md)."""

import numpy as np
import pytest

from topospec.stats.protocol import (
    cluster_bootstrap_ci,
    holm_correction,
    macro_f1,
    paired_wilcoxon,
    precision_at_k,
    spearman,
)


def test_bootstrap_ci_covers_sample_mean(rng):
    draws = rng.normal(5, 1, size=40)
    vals = {f"b{i}": float(v) for i, v in enumerate(draws)}
    ci = cluster_bootstrap_ci(vals, rng)
    assert ci.lo < ci.mean < ci.hi
    assert ci.mean == pytest.approx(draws.mean())
    # width of a 95% CI of the mean ~ 2 * 1.96 * SE; allow a loose factor
    se = draws.std(ddof=1) / np.sqrt(40)
    assert 2 * se < (ci.hi - ci.lo) < 8 * se
    assert ci.n_clusters == 40


def test_bootstrap_ci_narrows_with_n(rng):
    small = cluster_bootstrap_ci(list(rng.normal(0, 1, 10)), rng)
    large = cluster_bootstrap_ci(list(rng.normal(0, 1, 1000)), rng)
    assert (large.hi - large.lo) < (small.hi - small.lo)


def test_wilcoxon_detects_shift(rng):
    a = rng.normal(0, 1, 30)
    b = a + 0.8
    _, p = paired_wilcoxon(b, a, alternative="greater")
    assert p < 0.01
    _, p_null = paired_wilcoxon(a, a + rng.normal(0, 1e-6, 30))
    assert p_null > 0.05


def test_holm_correction_properties():
    ps = [0.01, 0.04, 0.03, 0.005]
    adj = holm_correction(ps)
    assert all(a >= p for a, p in zip(adj, ps, strict=True))  # never smaller
    assert all(0 <= a <= 1 for a in adj)
    # monotone in the original ordering of sorted p-values
    order = np.argsort(ps)
    assert np.all(np.diff(np.array(adj)[order]) >= -1e-12)
    # smallest: p*m = 0.005*4 = 0.02
    assert abs(adj[3] - 0.02) < 1e-12


def test_holm_empty_and_single():
    assert holm_correction([]) == []
    assert holm_correction([0.2]) == [0.2]


def test_precision_at_k():
    scores = {"a": 3.0, "b": 2.0, "c": 1.0, "d": 0.5}
    assert precision_at_k(scores, {"a", "c"}, k=2) == 0.5
    assert precision_at_k(scores, {"a", "b"}, k=2) == 1.0
    with pytest.raises(ValueError):
        precision_at_k(scores, {"a"}, k=0)


def test_spearman_and_f1():
    x = np.arange(10, dtype=float)
    assert spearman(x, x * 2 + 1) == pytest.approx(1.0)
    assert macro_f1([0, 1, 0, 1], [0, 1, 0, 1]) == 1.0
