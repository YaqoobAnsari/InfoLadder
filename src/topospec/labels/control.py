"""Y_ctrl — shuffled-label control task (Hewitt-Liang; plan §4.2, §9).

Probes must be at chance here or they measure memorization. The shuffle permutes the
label multiset over nodes within each building (preserving marginals), seeded.
"""

from __future__ import annotations

import numpy as np


def shuffled_labels(
    labels: dict[str, int], rng: np.random.Generator
) -> dict[str, int]:
    keys = sorted(labels)
    vals = np.array([labels[k] for k in keys])
    rng.shuffle(vals)
    return {k: int(v) for k, v in zip(keys, vals, strict=True)}
