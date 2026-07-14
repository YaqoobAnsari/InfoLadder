"""Prequential (online) MDL codelength — plan §4.3, §8 (Voita & Titov 2020).

The probe-effort-sensitive, optimization-robust complement to I_V. Blocks are formed
at BUILDING granularity (probes need whole graphs; building-level integrity mirrors
the split protocol). Block boundaries double from `first_frac` of the buildings.

  L(Y|X) = n_1 * ln(C)  +  sum_i CE_sum(block_i | probe trained on blocks < i)   [nats]
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from topospec.probes.families import ProbeDataset, ProbeFamily, held_out_ce


@dataclass
class MDLResult:
    codelength_nats: float
    uniform_codelength_nats: float  # n * ln(C), the no-model baseline
    compression_ratio: float
    block_sizes: list[int] = field(default_factory=list)
    block_ce_sums: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "codelength_nats": self.codelength_nats,
            "uniform_codelength_nats": self.uniform_codelength_nats,
            "compression_ratio": self.compression_ratio,
            "block_sizes": self.block_sizes,
            "block_ce_sums": self.block_ce_sums,
        }


def _n_labeled(ds: ProbeDataset, idx: list[int]) -> int:
    return int(sum((ds.labels[i] >= 0).sum() for i in idx))


def prequential_codelength(
    family: ProbeFamily,
    dataset: ProbeDataset,
    rng: np.random.Generator,
    first_frac: float = 1 / 64,
    min_first_buildings: int = 2,
) -> MDLResult:
    """Online code the dataset with `family`, building-blocked, doubling schedule."""
    n_bldg = len(dataset.graphs)
    if n_bldg < 2 * min_first_buildings:
        raise ValueError(f"need >= {2 * min_first_buildings} buildings, got {n_bldg}")
    order = rng.permutation(n_bldg).tolist()

    # doubling boundaries in building counts
    b = max(min_first_buildings, int(np.ceil(first_frac * n_bldg)))
    bounds = [b]
    while bounds[-1] < n_bldg:
        bounds.append(min(2 * bounds[-1], n_bldg))

    ln_c = float(np.log(dataset.n_classes))
    first_idx = order[: bounds[0]]
    n_first = _n_labeled(dataset, first_idx)
    total = n_first * ln_c
    block_sizes = [n_first]
    block_ces = [n_first * ln_c]

    for lo, hi in zip(bounds, bounds[1:], strict=False):
        past = dataset.subset(order[:lo])
        block = dataset.subset(order[lo:hi])
        probe = family.fit(past, past, rng)  # prequential: no held-out val inside
        n_blk = _n_labeled(dataset, order[lo:hi])
        ce_sum = held_out_ce(probe, block) * n_blk
        total += ce_sum
        block_sizes.append(n_blk)
        block_ces.append(ce_sum)

    n_all = _n_labeled(dataset, order)
    uniform = n_all * ln_c
    return MDLResult(
        codelength_nats=total,
        uniform_codelength_nats=uniform,
        compression_ratio=uniform / total if total > 0 else float("inf"),
        block_sizes=block_sizes,
        block_ce_sums=block_ces,
    )
