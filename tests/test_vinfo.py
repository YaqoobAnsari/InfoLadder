"""Estimator sanity on known-information cases (src/topospec/CLAUDE.md invariant 6)."""

import numpy as np
import pytest

from topospec.probes.families import (
    LinearFamily,
    PriorFamily,
    ProbeDataset,
    held_out_ce,
)
from topospec.probes.featurize import FeaturizedGraph
from topospec.vinfo.estimator import concat_datasets, estimate_cell, estimate_h_y


def _toy_dataset(rng, n_graphs=12, n_nodes=40, informative=True, noise=0.0):
    """X in R^4; y = 1[x0 > 0] when informative, else independent of X."""
    graphs, labels = [], []
    for b in range(n_graphs):
        x = rng.normal(size=(n_nodes, 4)).astype(np.float32)
        if informative:
            y = (x[:, 0] > 0).astype(np.int64)
            flip = rng.random(n_nodes) < noise
            y[flip] = 1 - y[flip]
        else:
            y = rng.integers(0, 2, size=n_nodes).astype(np.int64)
        node_ids = [f"n{i}" for i in range(n_nodes)]
        graphs.append(
            FeaturizedGraph(
                building_id=f"toy:{b}",
                level=0,
                node_ids=node_ids,
                x=x,
                edge_index=np.zeros((2, 0), dtype=np.int64),
                edge_attr=np.zeros((0, 0), dtype=np.float32),
                node_pos={nid: i for i, nid in enumerate(node_ids)},
            )
        )
        labels.append(y)
    return ProbeDataset(graphs=graphs, labels=labels, n_classes=2)


def _split(ds):
    n = len(ds.graphs)
    return ds.subset(list(range(0, n - 4))), ds.subset([n - 4, n - 3]), ds.subset([n - 2, n - 1])


def test_h_y_close_to_marginal_entropy(rng):
    ds = _toy_dataset(rng, informative=False)
    tr, _va, te = _split(ds)
    h = estimate_h_y(tr, te, rng)
    assert abs(h - np.log(2)) < 0.05  # balanced binary -> ln 2


def test_iv_near_h_y_when_x_determines_y(rng):
    ds = _toy_dataset(rng, informative=True, noise=0.0)
    tr, va, te = _split(ds)
    est = estimate_cell(LinearFamily(), tr, va, te, rng, n_restarts=1)
    assert est.i_v > 0.5  # most of ln(2) ~= 0.693 extracted
    assert est.h_y_given_x < 0.2


def test_iv_near_zero_when_independent(rng):
    ds = _toy_dataset(rng, informative=False)
    tr, va, te = _split(ds)
    est = estimate_cell(LinearFamily(), tr, va, te, rng, n_restarts=1)
    assert abs(est.i_v) < 0.08


def test_prior_family_gives_zero_iv(rng):
    ds = _toy_dataset(rng, informative=True)
    tr, va, te = _split(ds)
    est = estimate_cell(PriorFamily(), tr, va, te, rng, n_restarts=1)
    assert abs(est.i_v) < 1e-9  # same family as the H_V(Y) reference


def test_restarts_recorded_and_selection_by_val(rng):
    ds = _toy_dataset(rng, informative=True, noise=0.1)
    tr, va, te = _split(ds)
    est = estimate_cell(LinearFamily(), tr, va, te, rng, n_restarts=3)
    assert len(est.restarts) == 3
    vals = [r.val_ce for r in est.restarts]
    assert est.selected_restart == int(np.argmin(vals))
    assert est.h_y_given_x == est.restarts[est.selected_restart].test_ce


def test_conditional_vinfo_construction(rng):
    """Concat features carry at least as much usable info as the coarse side alone."""
    ds_fine = _toy_dataset(rng, informative=True, noise=0.05)
    # coarse = same graphs with the informative column zeroed out
    import copy

    ds_coarse = ProbeDataset(
        graphs=[copy.copy(g) for g in ds_fine.graphs],
        labels=[y.copy() for y in ds_fine.labels],
        n_classes=2,
    )
    for g in ds_coarse.graphs:
        g = g  # copies share x; replace with zeroed informative column
    ds_coarse.graphs = [
        FeaturizedGraph(
            building_id=g.building_id,
            level=0,
            node_ids=g.node_ids,
            x=np.concatenate([np.zeros_like(g.x[:, :1]), g.x[:, 1:]], axis=1),
            edge_index=g.edge_index,
            edge_attr=g.edge_attr,
            node_pos=g.node_pos,
        )
        for g in ds_fine.graphs
    ]
    both = concat_datasets(ds_coarse, ds_fine)
    tr_c, va_c, te_c = _split(ds_coarse)
    tr_b, va_b, te_b = _split(both)
    fam = LinearFamily()
    ce_coarse = held_out_ce(fam.fit(tr_c, va_c, rng), te_c)
    ce_both = held_out_ce(fam.fit(tr_b, va_b, rng), te_b)
    gain = ce_coarse - ce_both  # I_V(delta -> Y | coarse)
    assert gain > 0.3


@pytest.mark.slow
def test_gnn_family_reads_structure(rng):
    """V5 recovers a degree-defined target from structure alone at R0 (positive
    control of the calibration design)."""
    from topospec.data.synthetic import generate_corpus, planted_labels
    from topospec.graphs.levels import forget
    from topospec.probes.families import GNNFamily
    from topospec.probes.featurize import featurize

    corpus = generate_corpus(rng, n_buildings=16)
    feats, labels = [], []
    for g in corpus:
        lab = planted_labels(g, "planted_degree")
        fg = featurize(forget(g, 0))
        y = np.full(len(fg.node_ids), -1, dtype=np.int64)
        for nid, val in lab.items():
            y[fg.node_pos[nid]] = val
        feats.append(fg)
        labels.append(y)
    ds = ProbeDataset(graphs=feats, labels=labels, n_classes=2)
    tr, va, te = ds.subset(list(range(12))), ds.subset([12, 13]), ds.subset([14, 15])
    est = estimate_cell(GNNFamily(n_layers=2), tr, va, te, rng, n_restarts=1)
    assert est.i_v > 0.15  # clearly above zero: structure is being read
