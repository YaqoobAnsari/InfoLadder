"""Label pipelines: egress betweenness, rank pairs, shuffled control."""


from topospec.graphs.levels import forget
from topospec.labels.control import shuffled_labels
from topospec.labels.egress import betweenness_bottlenecks
from topospec.labels.rank import pairwise_rank_labels


def test_betweenness_is_level_invariant(building):
    """The target must not vary with representation level (leakage-free, plan §5)."""
    # computed on any level's graph, the R0-skeleton target must be recomputed
    # identically -> compare R0-derived labels from two different starting levels
    lab_from_r4 = betweenness_bottlenecks(forget(building, 0))
    lab_from_r2 = betweenness_bottlenecks(forget(forget(building, 2), 0))
    assert lab_from_r4 == lab_from_r2


def test_betweenness_topfrac(building):
    g0 = forget(building, 0)
    lab = betweenness_bottlenecks(g0, top_frac=0.1)
    assert set(lab.values()) <= {0, 1}
    assert sum(lab.values()) == max(1, round(0.1 * len(g0.nodes)))


def test_corridors_dominate_bottlenecks(building):
    """Corridor-spine geometry: the spine should capture top betweenness."""
    g0 = forget(building, 0)
    lab = betweenness_bottlenecks(g0, top_frac=0.1)
    corridors = {nid for nid, n in building.nodes.items() if n.kind == "corridor"}
    hits = sum(v for nid, v in lab.items() if nid in corridors)
    assert hits >= 1


def test_pairwise_rank_labels(rng):
    values = {f"r{i}": float(i) for i in range(10)}
    pairs = pairwise_rank_labels(values, rng, n_pairs=20)
    assert len(pairs) == 20
    for a, b, y in pairs:
        assert y == int(values[a] > values[b])


def test_rank_labels_drop_ties(rng):
    values = {"a": 1.0, "b": 1.0}
    assert pairwise_rank_labels(values, rng, n_pairs=5) == []


def test_shuffled_labels_preserve_marginal(rng):
    labels = {f"n{i}": int(i < 30) for i in range(100)}
    shuf = shuffled_labels(labels, rng)
    assert sorted(shuf.values()) == sorted(labels.values())
    assert set(shuf) == set(labels)
    # actually shuffled (probability of identity permutation is negligible)
    assert any(shuf[k] != labels[k] for k in labels)
