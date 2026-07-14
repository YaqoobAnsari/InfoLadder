"""Level-respecting featurization — THE single enforcement point (plan §8, §4.4).

"The representation defines the interface; probes never peek past it."

Feature blocks are strictly additive with level, mirroring the refinement ladder:

  R0+  geom(3):        area (log1p), centroid x, y (per-building standardized)
  R1+  kind(3):        one-hot in {room, door, corridor}
       label(8):       stable hash bucket of semantic label
  R2+  tau_counts(3):  incident edge counts per tau
  R3+  delta_counts(3): incident counts [outgoing-restricted, incoming-restricted, both]
  R4+  zone(1+8+1):    inherited zone attr 'secret' (or 0), zone-id hash bucket(8),
                       zone_size (log1p)

For node-level linear probes (V2/V3) incident-edge aggregates ARE the level's edge
content at the node interface; GNN probes additionally receive edge_index/edge_attr.
At R3+, direction-restricted edges are materialized as single-direction entries in
edge_index (delta semantics: 'forward' = u->v only).

Optional positional-encoding block (V3): top-`n_pe` Laplacian eigenvectors of the
undirected skeleton — structural, available at every level (it uses no typed content).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from topospec.graphs.schema import EDGE_TAUS, SPACE_KINDS, SpectrumGraph

N_LABEL_BUCKETS = 8
N_ZONE_BUCKETS = 8


def _bucket(s: str, n: int) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16) % n


def feature_dim(level: int, with_pe: bool = False, n_pe: int = 4) -> int:
    d = 3
    if level >= 1:
        d += 3 + N_LABEL_BUCKETS
    if level >= 2:
        d += 3
    if level >= 3:
        d += 3
    if level >= 4:
        d += 1 + N_ZONE_BUCKETS + 1
    if with_pe:
        d += n_pe
    return d


def edge_feature_dim(level: int) -> int:
    return (3 if level >= 2 else 0) + (3 if level >= 3 else 0)


def zone_secret_column() -> int:
    """Column index of the inherited zone 'secret' attribute in R4 features (no PE).

    Used by the V0 parameter-free readout for planted_zone (plan §8: richness turns a
    learning problem into a lookup)."""
    return feature_dim(3)


@dataclass
class FeaturizedGraph:
    building_id: str
    level: int
    node_ids: list[str]  # space nodes only, sorted
    x: np.ndarray  # (n, d) float32
    edge_index: np.ndarray  # (2, m) int64, direction-materialized
    edge_attr: np.ndarray  # (m, de) float32
    node_pos: dict[str, int]  # node_id -> row


def featurize(
    g: SpectrumGraph, with_pe: bool = False, n_pe: int = 4
) -> FeaturizedGraph:
    """Featurize a graph AT ITS OWN LEVEL. To probe level k, first forget(g, k)."""
    level = g.level
    spaces = g.space_nodes()
    node_ids = sorted(spaces)
    pos = {nid: i for i, nid in enumerate(node_ids)}
    n = len(node_ids)

    # --- incident aggregates (computed once)
    tau_counts = np.zeros((n, 3), dtype=np.float32)
    delta_counts = np.zeros((n, 3), dtype=np.float32)  # [out-restricted, in-restricted, both]
    for e in g.edges:
        iu, iv = pos[e.u], pos[e.v]
        if level >= 2:
            t = EDGE_TAUS.index(e.tau)
            tau_counts[iu, t] += 1
            tau_counts[iv, t] += 1
        if level >= 3:
            if e.delta == "both":
                delta_counts[iu, 2] += 1
                delta_counts[iv, 2] += 1
            elif e.delta == "forward":  # u -> v only
                delta_counts[iu, 0] += 1
                delta_counts[iv, 1] += 1
            elif e.delta == "backward":  # v -> u only
                delta_counts[iu, 1] += 1
                delta_counts[iv, 0] += 1

    # --- per-building standardization of centroids
    cents = np.array(
        [spaces[nid].centroid if spaces[nid].centroid is not None else (0.0, 0.0) for nid in node_ids],
        dtype=np.float64,
    )
    c_mu = cents.mean(axis=0)
    c_sd = cents.std(axis=0)
    c_sd[c_sd == 0] = 1.0
    cents = (cents - c_mu) / c_sd

    blocks: list[np.ndarray] = []
    geom = np.zeros((n, 3), dtype=np.float32)
    for i, nid in enumerate(node_ids):
        a = spaces[nid].area
        geom[i, 0] = np.log1p(a) if a is not None else 0.0
    geom[:, 1:] = cents.astype(np.float32)
    blocks.append(geom)

    if level >= 1:
        kind = np.zeros((n, 3), dtype=np.float32)
        lab = np.zeros((n, N_LABEL_BUCKETS), dtype=np.float32)
        for i, nid in enumerate(node_ids):
            nd = spaces[nid]
            if nd.kind in SPACE_KINDS:
                kind[i, SPACE_KINDS.index(nd.kind)] = 1.0
            if nd.label:
                lab[i, _bucket(nd.label, N_LABEL_BUCKETS)] = 1.0
        blocks += [kind, lab]

    if level >= 2:
        blocks.append(tau_counts)
    if level >= 3:
        blocks.append(delta_counts)

    if level >= 4:
        zone = np.zeros((n, 1 + N_ZONE_BUCKETS + 1), dtype=np.float32)
        for i, nid in enumerate(node_ids):
            zid = g.ancestor_of_kind(nid, "zone")
            if zid is not None:
                zattrs = g.nodes[zid].attrs
                zone[i, 0] = float(zattrs.get("secret", 0))
                zone[i, 1 + _bucket(zid, N_ZONE_BUCKETS)] = 1.0
                zone[i, -1] = np.log1p(float(zattrs.get("zone_size", 0)))
        blocks.append(zone)

    x = np.concatenate(blocks, axis=1)

    # --- edges, direction-materialized
    src, dst, eattrs = [], [], []

    def _eattr(e) -> np.ndarray:
        parts = []
        if level >= 2:
            t = np.zeros(3, dtype=np.float32)
            t[EDGE_TAUS.index(e.tau)] = 1.0
            parts.append(t)
        if level >= 3:
            d = np.zeros(3, dtype=np.float32)
            d[("both", "forward", "backward").index(e.delta)] = 1.0
            parts.append(d)
        return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)

    for e in g.edges:
        iu, iv = pos[e.u], pos[e.v]
        fa = _eattr(e)
        if level >= 3 and e.delta == "forward":
            dirs = [(iu, iv)]
        elif level >= 3 and e.delta == "backward":
            dirs = [(iv, iu)]
        else:
            dirs = [(iu, iv), (iv, iu)]
        for a, b in dirs:
            src.append(a)
            dst.append(b)
            eattrs.append(fa)

    edge_index = np.array([src, dst], dtype=np.int64) if src else np.zeros((2, 0), np.int64)
    de = edge_feature_dim(level)
    edge_attr = (
        np.stack(eattrs).astype(np.float32) if eattrs else np.zeros((0, de), np.float32)
    )
    if edge_attr.shape[1] != de:  # zero-dim guard at low levels
        edge_attr = edge_attr.reshape(len(eattrs), de)

    if with_pe:
        x = np.concatenate([x, _laplacian_pe(n, edge_index, n_pe)], axis=1)

    assert x.shape[1] == feature_dim(level, with_pe=with_pe, n_pe=n_pe)
    return FeaturizedGraph(
        building_id=g.building_id,
        level=level,
        node_ids=node_ids,
        x=x.astype(np.float32),
        edge_index=edge_index,
        edge_attr=edge_attr,
        node_pos=pos,
    )


def _laplacian_pe(n: int, edge_index: np.ndarray, n_pe: int) -> np.ndarray:
    """Top-n_pe nontrivial Laplacian eigenvectors of the undirected skeleton,
    sign-fixed (first nonzero entry positive) for determinism."""
    a_mat = np.zeros((n, n), dtype=np.float64)
    for s, d in edge_index.T:
        a_mat[s, d] = 1.0
        a_mat[d, s] = 1.0
    deg = a_mat.sum(axis=1)
    lap = np.diag(deg) - a_mat
    w, v = np.linalg.eigh(lap)
    order = np.argsort(w)
    pe = np.zeros((n, n_pe), dtype=np.float32)
    take = [i for i in order if w[i] > 1e-8][:n_pe]
    for c, i in enumerate(take):
        vec = v[:, i]
        nz = np.nonzero(np.abs(vec) > 1e-12)[0]
        if nz.size and vec[nz[0]] < 0:
            vec = -vec
        pe[:, c] = vec.astype(np.float32)
    return pe
