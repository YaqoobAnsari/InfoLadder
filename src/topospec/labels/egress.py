"""Y_egress — bottleneck membership (plan §4.2).

Two lanes (decision D-004): betweenness reference target everywhere (implemented);
JuPedSim evacuation simulation on a stratified sample (ROADMAP A-4).
"""

from __future__ import annotations

import networkx as nx

from topospec.graphs.schema import SpectrumGraph


def to_networkx(g: SpectrumGraph) -> nx.Graph:
    nxg = nx.Graph()
    for nid, n in g.space_nodes().items():
        nxg.add_node(nid, kind=n.kind, area=n.area)
    for e in g.edges:
        nxg.add_edge(e.u, e.v)
    return nxg


def betweenness_bottlenecks(g: SpectrumGraph, top_frac: float = 0.1) -> dict[str, int]:
    """Reference target: top-`top_frac` betweenness membership over space nodes.

    Computed on the R0 skeleton (undirected connectivity) regardless of g.level, so
    the target is identical across representation levels — the representation, not
    the label, varies (leakage-free by construction, plan §5).
    """
    nxg = to_networkx(g)
    bc = nx.betweenness_centrality(nxg, normalized=True)
    ranked = sorted(bc, key=lambda k: (-bc[k], k))
    k = max(1, int(round(top_frac * len(ranked))))
    top = set(ranked[:k])
    return {nid: int(nid in top) for nid in bc}


def jupedsim_bottlenecks(g: SpectrumGraph, **sim_kwargs) -> dict[str, int]:
    raise NotImplementedError(
        "JuPedSim egress lane is ROADMAP task A-4 (docs/ROADMAP.md); "
        "stratified-sample simulation with versioned configs."
    )
