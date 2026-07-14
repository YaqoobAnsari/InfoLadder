"""End-to-end calibration on the T-ladder: pipeline liveness + saturation recovery."""

import numpy as np
import pytest

from topospec.data import synthetic
from topospec.experiments.runner import _build_datasets
from topospec.probes.families import LinearFamily
from topospec.vinfo.estimator import estimate_cell


@pytest.fixture(scope="module")
def small_world():
    rng = np.random.default_rng(11)
    corpus = synthetic.generate_corpus(rng, n_buildings=14)
    targets = ["planted_door", "planted_zone", "planted_door_ctrl"]
    _, datasets = _build_datasets(corpus, [1, 2, 5], targets, rng)
    n = len(corpus)
    tr = list(range(0, n - 4))
    va = [n - 4, n - 3]
    te = [n - 2, n - 1]
    return datasets, (tr, va, te)


def _iv(datasets, splits, level, target, rng, family=None):
    tr, va, te = splits
    ds = datasets[(level, target)]
    est = estimate_cell(
        family or LinearFamily(),
        ds.subset(tr),
        ds.subset(va),
        ds.subset(te),
        rng,
        n_restarts=1,
    )
    return est.i_v


def test_door_target_saturates_at_t2(small_world, rng):
    datasets, splits = small_world
    iv_t1 = _iv(datasets, splits, 1, "planted_door", rng)
    iv_t2 = _iv(datasets, splits, 2, "planted_door", rng)
    assert iv_t2 > iv_t1 + 0.1
    assert iv_t2 > 0.3


def test_zone_target_saturates_at_t5(small_world, rng):
    datasets, splits = small_world
    iv_t2 = _iv(datasets, splits, 2, "planted_zone", rng)
    iv_t5 = _iv(datasets, splits, 5, "planted_zone", rng)
    assert iv_t5 > iv_t2 + 0.2
    assert abs(iv_t2) < 0.15  # unreadable below saturation


def test_control_extracts_nothing(small_world, rng):
    """One-sided: negative control I_V is overfit noise; positive = leakage."""
    datasets, splits = small_world
    for level in (1, 2, 5):
        iv = _iv(datasets, splits, level, "planted_door_ctrl", rng)
        assert iv < 0.1, f"control leaked at T{level}: I_V={iv:.3f}"


@pytest.mark.slow
def test_full_calibration_smoke_via_runner(tmp_path, monkeypatch):
    """Drive run_calibration end-to-end (smoke config) against tmp run/registry."""
    import topospec.experiments.manifest as m
    import topospec.experiments.registry as r
    import topospec.experiments.runner as runner

    monkeypatch.setattr(m, "git_info", lambda: {"sha": "test", "dirty": False})
    monkeypatch.setattr(r, "REGISTRY_PATH", tmp_path / "registry.jsonl")
    cfg = {"experiment": "calibration_a0", "seed": 5}
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)  # runs/ under tmp
    rc = runner.run_calibration(cfg, "0" * 64, "configs/calibration_a0.yaml", smoke=True)
    assert rc == 0, "smoke calibration must PASS"
    entries = r.read_entries(registry_path=tmp_path / "registry.jsonl")
    assert len(entries) == 1
    assert entries[0]["calibration_pass"] is True
