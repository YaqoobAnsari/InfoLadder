"""Y_rank — pairwise room temperature ordering (plan §4.2). Leakage-free target."""

from __future__ import annotations

import numpy as np


def pairwise_rank_labels(
    room_values: dict[str, float],
    rng: np.random.Generator,
    n_pairs: int | None = None,
) -> list[tuple[str, str, int]]:
    """Sample unordered room pairs; label 1 iff value(a) > value(b).

    Ties are dropped (they carry no ordering information). Default n_pairs = 3x rooms.
    """
    rooms = sorted(room_values)
    if len(rooms) < 2:
        return []
    if n_pairs is None:
        n_pairs = 3 * len(rooms)
    out: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    max_tries = 20 * n_pairs
    tries = 0
    while len(out) < n_pairs and tries < max_tries:
        tries += 1
        i, j = rng.choice(len(rooms), size=2, replace=False)
        a, b = rooms[i], rooms[j]
        if (a, b) in seen or (b, a) in seen:
            continue
        seen.add((a, b))
        if room_values[a] == room_values[b]:
            continue
        out.append((a, b, int(room_values[a] > room_values[b])))
    return out
