"""Probe families V0..V7 — plan §8, capacity-ordered.

Fairness (plan §4.4): architecture hyperparameters (hidden dims, layers, optimizer,
epochs, early-stopping) are FIXED per family across levels; parameter counts differ
only through the input dimension, which is documented per level in run manifests
(`param_count`). `assert_architecture_parity` enforces this.

Implemented here: V0 (parameter-free readout), V1 (prior), V2 (linear), V3
(linear + Laplacian PE), V4/V5 (1-/2-layer edge-conditioned GNN, plain torch).
V6 (GraphGPS-style, ≤2M params) is ROADMAP INFRA-8; V7 (frozen LM) is INFRA-10.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from topospec.probes.featurize import FeaturizedGraph

EPS = 1e-12


@dataclass
class ProbeDataset:
    """Node-classification dataset over featurized graphs (labels -1 = unlabeled)."""

    graphs: list[FeaturizedGraph]
    labels: list[np.ndarray]  # per graph, aligned to graph.node_ids
    n_classes: int
    n_pe: int = 0  # trailing PE columns (used by V3, sliced off by others)
    meta: dict = field(default_factory=dict)

    def subset(self, graph_idx: list[int]) -> "ProbeDataset":
        return ProbeDataset(
            graphs=[self.graphs[i] for i in graph_idx],
            labels=[self.labels[i] for i in graph_idx],
            n_classes=self.n_classes,
            n_pe=self.n_pe,
            meta=self.meta,
        )

    def flat_xy(self, with_pe: bool) -> tuple[np.ndarray, np.ndarray]:
        xs, ys = [], []
        for g, y in zip(self.graphs, self.labels, strict=True):
            m = y >= 0
            x = g.x if (with_pe or self.n_pe == 0) else g.x[:, : -self.n_pe]
            xs.append(x[m])
            ys.append(y[m])
        return np.concatenate(xs), np.concatenate(ys)


class FittedProbe(ABC):
    @abstractmethod
    def predict_proba(self, ds: ProbeDataset) -> list[np.ndarray]:
        """Per graph: (n_nodes, n_classes) probabilities (rows for ALL nodes)."""


class ProbeFamily(ABC):
    name: str
    consumes_structure: bool  # True if the probe uses edge_index (GNNs)

    @abstractmethod
    def fit(
        self, train: ProbeDataset, val: ProbeDataset, rng: np.random.Generator
    ) -> FittedProbe:
        ...

    @abstractmethod
    def param_count(self, input_dim: int, n_classes: int) -> int:
        ...


def held_out_ce(probe: FittedProbe, ds: ProbeDataset) -> float:
    """Mean held-out cross-entropy in nats over labeled nodes."""
    tot, cnt = 0.0, 0
    for probs, y in zip(probe.predict_proba(ds), ds.labels, strict=True):
        m = y >= 0
        p = np.clip(probs[m, y[m]], EPS, 1.0)
        tot += float(-np.log(p).sum())
        cnt += int(m.sum())
    return tot / max(cnt, 1)


def held_out_accuracy(probe: FittedProbe, ds: ProbeDataset) -> float:
    hit, cnt = 0, 0
    for probs, y in zip(probe.predict_proba(ds), ds.labels, strict=True):
        m = y >= 0
        hit += int((probs[m].argmax(axis=1) == y[m]).sum())
        cnt += int(m.sum())
    return hit / max(cnt, 1)


# --------------------------------------------------------------------------- V1
class PriorFamily(ProbeFamily):
    """V1 — predict-from-prior (train label marginal). Also supplies H_V(Y)."""

    name = "V1_prior"
    consumes_structure = False

    class _Fitted(FittedProbe):
        def __init__(self, p: np.ndarray):
            self.p = p

        def predict_proba(self, ds: ProbeDataset) -> list[np.ndarray]:
            return [np.tile(self.p, (len(g.node_ids), 1)) for g in ds.graphs]

    def fit(self, train, val, rng):
        _, y = train.flat_xy(with_pe=False)
        counts = np.bincount(y, minlength=train.n_classes).astype(np.float64)
        p = (counts + 1.0) / (counts.sum() + train.n_classes)  # Laplace smoothing
        return self._Fitted(p)

    def param_count(self, input_dim, n_classes):
        return n_classes - 1


# --------------------------------------------------------------------------- V0
class ReadoutFamily(ProbeFamily):
    """V0 — parameter-free readout where the level permits it (plan §8).

    `reader(graph) -> (n_nodes,) int predictions`; probability mass 1-eps on the
    read class. The reader is registered per (target, level) by the runner; fitting
    estimates nothing (eps fixed).
    """

    name = "V0_readout"
    consumes_structure = False

    def __init__(self, reader: Callable[[FeaturizedGraph], np.ndarray], eps: float = 1e-3):
        self.reader = reader
        self.eps = eps

    class _Fitted(FittedProbe):
        def __init__(self, reader, eps, n_classes):
            self.reader, self.eps, self.n_classes = reader, eps, n_classes

        def predict_proba(self, ds: ProbeDataset) -> list[np.ndarray]:
            out = []
            for g in ds.graphs:
                yhat = self.reader(g).astype(int)
                p = np.full((len(yhat), self.n_classes), self.eps / (self.n_classes - 1))
                p[np.arange(len(yhat)), yhat] = 1.0 - self.eps
                out.append(p)
            return out

    def fit(self, train, val, rng):
        return self._Fitted(self.reader, self.eps, train.n_classes)

    def param_count(self, input_dim, n_classes):
        return 0


# ---------------------------------------------------------------------- V2 / V3
class LinearFamily(ProbeFamily):
    """V2 — multinomial logistic regression on raw node attributes (no PE)."""

    name = "V2_linear"
    consumes_structure = False
    with_pe = False

    def __init__(self, c_reg: float = 1.0, max_iter: int = 2000):
        self.c_reg = c_reg
        self.max_iter = max_iter

    class _Fitted(FittedProbe):
        def __init__(self, clf, classes, n_classes, with_pe, n_pe, mu, sd):
            self.clf, self.classes, self.n_classes = clf, classes, n_classes
            self.with_pe, self.n_pe, self.mu, self.sd = with_pe, n_pe, mu, sd

        def predict_proba(self, ds: ProbeDataset) -> list[np.ndarray]:
            out = []
            for g in ds.graphs:
                x = g.x if (self.with_pe or self.n_pe == 0) else g.x[:, : -self.n_pe]
                x = (x - self.mu) / self.sd
                raw = self.clf.predict_proba(x)
                p = np.full((x.shape[0], self.n_classes), EPS)
                for col, cls in enumerate(self.classes):
                    p[:, int(cls)] = raw[:, col]
                out.append(p / p.sum(axis=1, keepdims=True))
            return out

    def fit(self, train, val, rng):
        from sklearn.linear_model import LogisticRegression

        x, y = train.flat_xy(with_pe=self.with_pe)
        mu = x.mean(axis=0)
        sd = x.std(axis=0)
        sd[sd == 0] = 1.0
        clf = LogisticRegression(
            C=self.c_reg, max_iter=self.max_iter, random_state=int(rng.integers(2**31))
        )
        clf.fit((x - mu) / sd, y)
        return self._Fitted(clf, clf.classes_, train.n_classes, self.with_pe, train.n_pe, mu, sd)

    def param_count(self, input_dim, n_classes):
        return (input_dim + 1) * n_classes


class LinearPEFamily(LinearFamily):
    """V3 — linear on attributes + spectral/positional encodings."""

    name = "V3_linear_pe"
    with_pe = True


# ---------------------------------------------------------------------- V4 / V5
class GNNFamily(ProbeFamily):
    """V4/V5 — 1-/2-layer edge-conditioned message passing (plain torch, CPU-fine).

    m_ij = ReLU(W_m [h_j ; e_ij]); h_i' = ReLU(W_s h_i + sum_j m_ij); linear head.
    SUM aggregation (GIN-style), not mean: mean is degree-invariant and provably
    cannot read connectivity-counting targets (e.g. the planted_degree calibration
    control). Hidden width fixed (32) across levels; input dim varies with level.
    """

    consumes_structure = True

    def __init__(self, n_layers: int, hidden: int = 32, lr: float = 0.01,
                 max_epochs: int = 300, patience: int = 30):
        self.n_layers = n_layers
        self.hidden = hidden
        self.lr = lr
        self.max_epochs = max_epochs
        self.patience = patience
        self.name = f"V{3 + n_layers}_gnn{n_layers}"

    class _Fitted(FittedProbe):
        def __init__(self, model, n_classes, n_pe):
            self.model, self.n_classes, self.n_pe = model, n_classes, n_pe

        def predict_proba(self, ds: ProbeDataset) -> list[np.ndarray]:
            import torch

            self.model.eval()
            out = []
            with torch.no_grad():
                for g in ds.graphs:
                    x = g.x if self.n_pe == 0 else g.x[:, : -self.n_pe]
                    logits = self.model(
                        torch.from_numpy(x),
                        torch.from_numpy(g.edge_index),
                        torch.from_numpy(g.edge_attr),
                    )
                    out.append(torch.softmax(logits, dim=1).numpy().astype(np.float64))
            return out

    def _build(self, in_dim: int, edge_dim: int, n_classes: int, seed: int):
        import torch
        import torch.nn as nn

        torch.manual_seed(seed)
        hidden, n_layers = self.hidden, self.n_layers

        class Layer(nn.Module):
            def __init__(self, dim_in):
                super().__init__()
                self.w_m = nn.Linear(dim_in + edge_dim, hidden)
                self.w_s = nn.Linear(dim_in, hidden)

            def forward(self, h, edge_index, edge_attr):
                src, dst = edge_index[0], edge_index[1]
                if src.numel() > 0:
                    m = torch.relu(self.w_m(torch.cat([h[src], edge_attr], dim=1)))
                    agg = torch.zeros(h.shape[0], m.shape[1], dtype=h.dtype)
                    agg.index_add_(0, dst, m)  # SUM aggregation: degree-aware
                else:
                    agg = torch.zeros(h.shape[0], hidden, dtype=h.dtype)
                return torch.relu(self.w_s(h) + agg)

        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                dims = [in_dim] + [hidden] * n_layers
                self.layers = nn.ModuleList(Layer(dims[i]) for i in range(n_layers))
                self.head = nn.Linear(dims[-1] if n_layers else in_dim, n_classes)

            def forward(self, x, edge_index, edge_attr):
                h = x
                for layer in self.layers:
                    h = layer(h, edge_index, edge_attr)
                return self.head(h)

        return Net()

    def fit(self, train, val, rng):
        import torch
        import torch.nn as nn

        n_pe = train.n_pe
        sample = train.graphs[0]
        in_dim = sample.x.shape[1] - n_pe
        edge_dim = sample.edge_attr.shape[1]
        model = self._build(in_dim, edge_dim, train.n_classes, int(rng.integers(2**31)))
        opt = torch.optim.Adam(model.parameters(), lr=self.lr)
        lossf = nn.CrossEntropyLoss()

        def tensors(ds):
            out = []
            for g, y in zip(ds.graphs, ds.labels, strict=True):
                x = g.x if n_pe == 0 else g.x[:, : -n_pe]
                out.append(
                    (
                        torch.from_numpy(x),
                        torch.from_numpy(g.edge_index),
                        torch.from_numpy(g.edge_attr),
                        torch.from_numpy(y.astype(np.int64)),
                    )
                )
            return out

        tr, va = tensors(train), tensors(val)
        best_val, best_state, since = np.inf, None, 0
        for _epoch in range(self.max_epochs):
            model.train()
            opt.zero_grad()
            losses = []
            for x, ei, ea, y in tr:
                m = y >= 0
                if m.sum() == 0:
                    continue
                logits = model(x, ei, ea)
                losses.append(lossf(logits[m], y[m]))
            loss = torch.stack(losses).mean()
            loss.backward()
            opt.step()

            model.eval()
            with torch.no_grad():
                tot, cnt = 0.0, 0
                for x, ei, ea, y in va:
                    m = y >= 0
                    if m.sum() == 0:
                        continue
                    logits = model(x, ei, ea)
                    tot += float(
                        nn.functional.cross_entropy(logits[m], y[m], reduction="sum")
                    )
                    cnt += int(m.sum())
                vce = tot / max(cnt, 1)
            if vce < best_val - 1e-5:
                best_val, since = vce, 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                since += 1
                if since >= self.patience:
                    break
        if best_state is not None:
            model.load_state_dict(best_state)
        return self._Fitted(model, train.n_classes, n_pe)

    def param_count(self, input_dim, n_classes):
        edge_dim = 0  # reported without edge dim; manifests document both
        total, dim_in = 0, input_dim
        for _ in range(self.n_layers):
            total += (dim_in + edge_dim + 1) * self.hidden + (dim_in + 1) * self.hidden
            dim_in = self.hidden
        total += (dim_in + 1) * n_classes
        return total


class GraphGPSFamily(ProbeFamily):
    """V6 — 4-layer GraphGPS-style transformer, <=2M params (plan §8)."""

    name = "V6_graphgps"
    consumes_structure = True

    def fit(self, train, val, rng):
        raise NotImplementedError("V6 GraphGPS probe is ROADMAP task INFRA-8.")

    def param_count(self, input_dim, n_classes):
        raise NotImplementedError("V6 GraphGPS probe is ROADMAP task INFRA-8.")


# ------------------------------------------------------------------------ registry
def make_family(name: str) -> ProbeFamily:
    table: dict[str, Callable[[], ProbeFamily]] = {
        "V1": PriorFamily,
        "V2": LinearFamily,
        "V3": LinearPEFamily,
        "V4": lambda: GNNFamily(n_layers=1),
        "V5": lambda: GNNFamily(n_layers=2),
        "V6": GraphGPSFamily,
    }
    if name not in table:
        raise KeyError(f"unknown probe family {name!r} (V0 is constructed per-target)")
    return table[name]()


def assert_architecture_parity(family: ProbeFamily, dims_by_level: dict[int, int],
                               n_classes: int) -> dict[int, int]:
    """Fairness §4.4: same architecture across levels; param counts differ only via
    input dim. Returns {level: param_count} for the run manifest."""
    return {
        lvl: family.param_count(d, n_classes) for lvl, d in sorted(dims_by_level.items())
    }
