"""Regression tests for slurm job 7206's failure: degenerate single-class blocks."""

import numpy as np

from topospec.probes.families import LinearFamily, ProbeDataset, held_out_ce
from topospec.probes.featurize import FeaturizedGraph
from topospec.vinfo.mdl import prequential_codelength


def _single_class_dataset(rng, n_graphs=6, n_nodes=20):
    graphs, labels = [], []
    for b in range(n_graphs):
        x = rng.normal(size=(n_nodes, 4)).astype(np.float32)
        y = np.ones(n_nodes, dtype=np.int64)  # every label = 1
        node_ids = [f"n{i}" for i in range(n_nodes)]
        graphs.append(
            FeaturizedGraph(
                building_id=f"deg:{b}",
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


def test_linear_family_survives_single_class_train(rng):
    """Job 7206 crash: sklearn refuses single-class fits; family must degrade to
    the smoothed marginal instead of raising."""
    ds = _single_class_dataset(rng)
    tr, te = ds.subset([0, 1, 2, 3]), ds.subset([4, 5])
    probe = LinearFamily().fit(tr, tr, rng)
    ce = held_out_ce(probe, te)
    assert np.isfinite(ce) and ce < 0.5  # near-certain constant prediction


def test_mdl_survives_single_class_first_block(rng):
    """Prequential MDL's first blocks are tiny; single-class prefixes must code."""
    # first 2 buildings all-ones, rest mixed
    ds = _single_class_dataset(rng, n_graphs=8)
    for y in ds.labels[2:]:
        y[::2] = 0
    res = prequential_codelength(LinearFamily(), ds, rng)
    assert np.isfinite(res.codelength_nats)
    assert res.codelength_nats > 0
