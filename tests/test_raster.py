"""Raster ingest lane (DATA-0): extraction correctness on a synthetic raster."""

import numpy as np
import pytest

from topospec.data.raster import extract_rooms, overlay_figure, pde_inputs
from topospec.graphs.validate import validate_graph
from topospec.labels.pde import solve_masked_poisson


def synthetic_floorplan(
    room_w: int = 80, room_h: int = 60, wall: int = 8, door: int = 14
) -> np.ndarray:
    """Three rooms in a row on white; doors between 1-2 and 2-3; no door 1-3.

    Layout: [room0 | wall+door | room1 | wall+door | room2], outer walls all
    around, thin 'text' strokes inside rooms to test stroke rejection.
    """
    width = 3 * room_w + 4 * wall
    height = room_h + 2 * wall
    img = np.full((height, width), 255, dtype=np.uint8)

    def vline(x0, x1):
        img[:, x0:x1] = 0

    # outer walls
    img[:wall, :] = 0
    img[-wall:, :] = 0
    vline(0, wall)
    vline(width - wall, width)
    # inner partition walls with door gaps (gap in the vertical middle)
    for k in (1, 2):
        x0 = wall + k * (room_w + wall) - wall
        vline(x0, x0 + wall)
        gy = height // 2
        img[gy - door // 2 : gy + door // 2, x0 : x0 + wall] = 255  # door gap
    # thin text-like strokes inside room 0 (must be ignored)
    img[wall + 10, wall + 10 : wall + 40] = 0
    img[wall + 20 : wall + 45, wall + 15] = 0
    return img


@pytest.fixture(scope="module")
def extraction():
    img = synthetic_floorplan()
    return extract_rooms(
        img,
        wall_open_px=3,
        split_erosion_px=8,
        min_room_px=200,
        building_id="raster:synthetic",
    )


def test_finds_three_rooms(extraction):
    assert extraction.stats["n_rooms"] == 3


def test_r0_graph_validates(extraction):
    assert validate_graph(extraction.graph)
    assert extraction.graph.level == 0


def test_adjacency_is_chain_not_clique(extraction):
    """Doors 0-1 and 1-2 exist; rooms 0 and 2 are NOT directly connected."""
    g = extraction.graph
    assert len(g.edges) == 2
    # the middle room (largest x-centroid rank 1) appears in both edges
    order = sorted(g.nodes, key=lambda nid: g.nodes[nid].centroid[0])
    mid = order[1]
    assert all(mid in (e.u, e.v) for e in g.edges)


def test_room_areas_reasonable(extraction):
    areas = [n.area for n in extraction.graph.nodes.values()]
    assert all(abs(a - areas[0]) / areas[0] < 0.25 for a in areas)  # similar rooms


def test_thin_strokes_rejected(extraction):
    """Text strokes inside room 0 must not create walls or extra rooms."""
    assert extraction.stats["n_rooms"] == 3  # already checked; explicit intent


def test_pde_runs_on_extraction(extraction):
    """The extraction feeds the PDE labeler end-to-end (DATA-0 acceptance path)."""
    interior, room_ix, tr = pde_inputs(extraction)
    dirichlet = np.zeros(interior.shape)
    u = solve_masked_poisson(interior, dirichlet, source=1.0, h=1.0)
    means = {
        rid: float(u[(room_ix == k) & interior].mean())
        for k, rid in enumerate(tr["room_ids"])
    }
    assert all(v > 0 for v in means.values())
    # middle room is farther from the exterior boundary on average -> warmest
    g = extraction.graph
    order = sorted(g.nodes, key=lambda nid: g.nodes[nid].centroid[0])
    assert means[order[1]] >= max(means[order[0]], means[order[2]]) * 0.8


def test_overlay_figure_writes(extraction, tmp_path):
    img = synthetic_floorplan()
    out = tmp_path / "overlay.png"
    overlay_figure(img, extraction, out)
    assert out.exists() and out.stat().st_size > 2_000


def test_rgba_and_scale_handling():
    img = synthetic_floorplan()
    rgba = np.stack([img, img, img, np.full_like(img, 255)], axis=2)
    ex = extract_rooms(
        rgba, split_erosion_px=8, min_room_px=200, px_per_m=20.0,
        building_id="raster:rgba",
    )
    assert ex.stats["n_rooms"] == 3
    # 80x60 px rooms at 20 px/m -> 4m x 3m = 12 m^2 (loose: segmentation eats margins)
    for n in ex.graph.nodes.values():
        assert 6.0 < n.area < 20.0
