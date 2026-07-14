"""Predictive V-information estimation — plan §4.3 (Xu et al., ICLR 2020).

  H_V(Y|X) = inf_{f in V} E[-log f(X)[Y]]   estimated by held-out cross-entropy (nats)
  I_V(X -> Y) = H_V(Y) - H_V(Y|X)

Estimates are lower bounds achieved by optimization (plan §8): each cell runs
`n_restarts` optimization restarts; restart selection uses VALIDATION CE, the reported
number is the selected restart's TEST CE; ALL restarts are returned and stored
(docs/EXPERIMENT_PROTOCOL.md §1).

H_V(Y) is estimated with the V1 prior family on the identical splits, which makes
I_V(X->Y) exactly the improvement over the label marginal under the same protocol.

Conditional V-information (annotation gain numerator, Hewitt et al. 2021):
  I_V(Delta -> Y | R_k) = H_V(Y | R_k) - H_V(Y | R_k (+) Delta)
computed by probing on concatenated features (`concat_datasets`), never as a
difference of two independent I_V estimates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from topospec.probes.families import (
    PriorFamily,
    ProbeDataset,
    ProbeFamily,
    held_out_accuracy,
    held_out_ce,
)


@dataclass
class RestartResult:
    restart: int
    val_ce: float
    test_ce: float
    test_accuracy: float


@dataclass
class CellEstimate:
    h_y: float
    h_y_given_x: float  # selected restart's test CE
    i_v: float
    selected_restart: int
    restarts: list[RestartResult] = field(default_factory=list)
    n_train: int = 0
    n_val: int = 0
    n_test: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def estimate_h_y(
    train: ProbeDataset, test: ProbeDataset, rng: np.random.Generator
) -> float:
    """H_V(Y): held-out CE of the prior family (label marginal)."""
    prior = PriorFamily().fit(train, train, rng)
    return held_out_ce(prior, test)


def estimate_cell(
    family: ProbeFamily,
    train: ProbeDataset,
    val: ProbeDataset,
    test: ProbeDataset,
    rng: np.random.Generator,
    n_restarts: int = 3,
) -> CellEstimate:
    """One grid cell: I_V for `family` on this (already level-featurized) dataset."""
    h_y = estimate_h_y(train, test, rng)

    restarts: list[RestartResult] = []
    for r in range(n_restarts):
        probe = family.fit(train, val, rng)
        restarts.append(
            RestartResult(
                restart=r,
                val_ce=held_out_ce(probe, val),
                test_ce=held_out_ce(probe, test),
                test_accuracy=held_out_accuracy(probe, test),
            )
        )
    sel = int(np.argmin([r.val_ce for r in restarts]))
    h_y_x = restarts[sel].test_ce

    def _count(ds: ProbeDataset) -> int:
        return int(sum((y >= 0).sum() for y in ds.labels))

    return CellEstimate(
        h_y=h_y,
        h_y_given_x=h_y_x,
        i_v=h_y - h_y_x,
        selected_restart=sel,
        restarts=restarts,
        n_train=_count(train),
        n_val=_count(val),
        n_test=_count(test),
    )


def concat_datasets(coarse: ProbeDataset, fine: ProbeDataset) -> ProbeDataset:
    """Feature-concatenate two featurizations of the SAME buildings/labels for the
    conditional V-information construction. Structure (edge_index/edge_attr) comes
    from the FINE graphs; node features are [coarse ; fine]. PE columns are stripped
    (conditional cells run without PE; V3 conditional cells re-add PE via the fine
    side upstream if ever needed)."""
    import copy

    if len(coarse.graphs) != len(fine.graphs):
        raise ValueError("datasets must cover identical buildings")
    graphs = []
    for gc, gf in zip(coarse.graphs, fine.graphs, strict=True):
        if gc.building_id != gf.building_id:
            raise ValueError(
                f"building mismatch: {gc.building_id} vs {gf.building_id}"
            )
        xc = gc.x if coarse.n_pe == 0 else gc.x[:, : -coarse.n_pe]
        xf = gf.x if fine.n_pe == 0 else gf.x[:, : -fine.n_pe]
        # align coarse rows to fine node ordering (fine may add nodes, e.g. doors)
        xc_aligned = np.zeros((len(gf.node_ids), xc.shape[1]), dtype=xc.dtype)
        for i, nid in enumerate(gf.node_ids):
            if nid in gc.node_pos:
                xc_aligned[i] = xc[gc.node_pos[nid]]
        g = copy.copy(gf)
        g.x = np.concatenate([xc_aligned, xf], axis=1)
        graphs.append(g)
    return ProbeDataset(
        graphs=graphs,
        labels=[y.copy() for y in fine.labels],
        n_classes=fine.n_classes,
        n_pe=0,
        meta={"conditional": True, **fine.meta},
    )
