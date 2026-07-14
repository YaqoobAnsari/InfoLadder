"""Statistical protocol — plan §9, operationalized in docs/EXPERIMENT_PROTOCOL.md.

Cluster bootstrap (clusters = buildings), paired Wilcoxon, Holm correction, and the
task-native secondary metrics. All confidence intervals in this study come from here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as sps


@dataclass
class BootstrapCI:
    mean: float
    lo: float
    hi: float
    n_clusters: int
    n_boot: int


def cluster_bootstrap_ci(
    values_by_cluster: dict[str, float] | list[float],
    rng: np.random.Generator,
    n_boot: int = 1000,
    alpha: float = 0.05,
) -> BootstrapCI:
    """Percentile bootstrap CI of the mean, resampling clusters (buildings)."""
    vals = (
        np.array(list(values_by_cluster.values()), dtype=np.float64)
        if isinstance(values_by_cluster, dict)
        else np.asarray(values_by_cluster, dtype=np.float64)
    )
    n = len(vals)
    if n == 0:
        raise ValueError("no clusters")
    boots = np.empty(n_boot)
    for i in range(n_boot):
        boots[i] = vals[rng.integers(0, n, size=n)].mean()
    return BootstrapCI(
        mean=float(vals.mean()),
        lo=float(np.percentile(boots, 100 * alpha / 2)),
        hi=float(np.percentile(boots, 100 * (1 - alpha / 2))),
        n_clusters=n,
        n_boot=n_boot,
    )


def paired_wilcoxon(
    a: np.ndarray, b: np.ndarray, alternative: str = "two-sided"
) -> tuple[float, float]:
    """Paired Wilcoxon signed-rank across buildings; returns (statistic, p)."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError("paired arrays must have identical shape")
    d = a - b
    if np.allclose(d, 0):
        return 0.0, 1.0
    res = sps.wilcoxon(a, b, alternative=alternative, zero_method="wilcox")
    return float(res.statistic), float(res.pvalue)


def holm_correction(pvals: list[float]) -> list[float]:
    """Holm step-down adjusted p-values (family = the input list)."""
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * pvals[idx])
        adj[idx] = min(1.0, running)
    return adj.tolist()


# ------------------------------------------------------- task-native secondaries §9
def ari(labels_a: list[int], labels_b: list[int]) -> float:
    from sklearn.metrics import adjusted_rand_score

    return float(adjusted_rand_score(labels_a, labels_b))


def nmi(labels_a: list[int], labels_b: list[int]) -> float:
    from sklearn.metrics import normalized_mutual_info_score

    return float(normalized_mutual_info_score(labels_a, labels_b))


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    return float(sps.spearmanr(x, y).statistic)


def precision_at_k(scores: dict[str, float], positives: set[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    ranked = sorted(scores, key=lambda n: (-scores[n], n))[:k]
    return sum(1 for n in ranked if n in positives) / k


def macro_f1(y_true: list[int], y_pred: list[int]) -> float:
    from sklearn.metrics import f1_score

    return float(f1_score(y_true, y_pred, average="macro"))
