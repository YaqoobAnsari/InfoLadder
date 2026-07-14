"""Raster floorplan → SpectrumGraph R0 ingest lane (ROADMAP DATA-0; decision D-008).

Scope: CLEAN, CAD-rendered rasters (thick dark walls on white), like
data/raw/prelim_rasters/. This is deliberately vision-free — classical morphology
only — so its failure modes are inspectable and it needs no training data:

  1. composite alpha on white, grayscale, threshold → ink mask
  2. wall mask = opening(closing(ink)): closing solidifies hatched/double-line
     CAD walls; opening then drops thin strokes (text, door arcs, furniture)
  3. hierarchical multi-scale markers on the free-space distance transform:
     each space is seeded at the largest inscribed radius it supports (halls >
     offices > corridors), so door necks split spaces without erasing corridors
  4. geodesic watershed floods markers within free space (never across walls);
     regions touching the padded border = page background/off-sheet = outside.
     Rationale: real sheets are NEVER hermetically sealed (entrance doors, plans
     continuing onto the next sheet), so border flood-fill would flood the whole
     building through door gaps; marker-based outside detection is leak-proof.
  5. adjacency: rooms whose pixels touch directly (within 2 px) share an opening
     → R0 E_conn edge; rooms that only meet across wall pixels are wall-adjacent
     (R2 material, counted in stats but not an R0 edge).

Outputs: SpectrumGraph R0 (areas in px^2 or m^2 via px_per_m, centroids in image
coords) + the room-index grid, which feeds labels/pde.py DIRECTLY (no polygons
needed). Quality is checked visually via `overlay_figure` (project guideline:
visual documentation) and numerically via extraction stats.

Known limitations (documented, acceptable for the preliminary lane): no door/
corridor semantics (R1+ needs the annotation path or the CAD-vector lane), stairs/
elevators segment as rooms, multi-sheet buildings are ingested per sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage

from topospec.graphs.schema import Edge, Node, SpectrumGraph


@dataclass
class RasterExtraction:
    graph: SpectrumGraph
    room_ix: np.ndarray  # (H, W) int64: -1 outside/wall, else room index
    room_ids: list[str]  # index -> node id
    wall_mask: np.ndarray  # (H, W) bool
    stats: dict


def _to_gray(img: np.ndarray) -> np.ndarray:
    """(H,W[,C]) uint8/float -> grayscale float in [0,255], alpha composited on white."""
    arr = np.asarray(img, dtype=np.float64)
    if arr.ndim == 2:
        return arr if arr.max() > 1.5 else arr * 255.0
    if arr.shape[2] == 4:
        a = arr[..., 3:4] / (255.0 if arr[..., 3].max() > 1.5 else 1.0)
        rgb = arr[..., :3] if arr[..., :3].max() > 1.5 else arr[..., :3] * 255.0
        arr = rgb * a + 255.0 * (1.0 - a)
    else:
        arr = arr[..., :3] if arr[..., :3].max() > 1.5 else arr[..., :3] * 255.0
    return arr.mean(axis=2)


DEFAULT_SPLIT_CANDIDATES = (8, 12, 16, 20, 24, 28, 32, 40, 48)


def extract_rooms(
    image: np.ndarray,
    ink_threshold: float = 128.0,
    wall_close_px: int = 2,
    wall_open_px: int = 2,
    split_erosion_px: int | None = None,
    min_room_px: int = 400,
    adjacency_reach_px: int | None = None,
    building_id: str = "raster:unknown",
    px_per_m: float | None = None,
) -> RasterExtraction:
    """Extract rooms + R0 connectivity from a clean CAD-rendered raster.

    Args:
        image: (H,W[,C]) array (PIL Image works via np.asarray).
        ink_threshold: gray value below which a pixel is ink.
        wall_close_px: closing radius that solidifies hatched/double-line walls.
        wall_open_px: opening radius separating thick walls from thin strokes.
        split_erosion_px: the FINEST marker scale r_min (markers are claimed
            hierarchically at every candidate radius >= r_min; see _segment).
            Must exceed the widest door half-gap or doors won't split spaces.
            None (default) = AUTO-TUNE: sweep DEFAULT_SPLIT_CANDIDATES as r_min
            and keep the value yielding the most sanely-sized rooms.
        min_room_px: components smaller than this are absorbed into neighbors.
        adjacency_reach_px: max gap for wall-adjacency counting
            (default: 2*wall_open_px + 4).
        px_per_m: optional scale; if given, areas are m^2 and centroids meters.
    """
    gray = _to_gray(image)

    # pad with white page margin: guarantees the page background survives erosion
    # as a fat border-touching seed, so 'outside' detection works even on sheets
    # cropped tight to the drawing
    candidates = (
        (split_erosion_px,) if split_erosion_px is not None else DEFAULT_SPLIT_CANDIDATES
    )
    pad = 4 * max(candidates)
    gray = np.pad(gray, pad, constant_values=255.0)
    ink = gray < ink_threshold

    # walls: closing solidifies hatched/double-line CAD walls, opening then drops
    # thin strokes (text, door arcs, furniture, dimension lines)
    wall = ndimage.binary_opening(
        ndimage.binary_closing(ink, structure=_disk(wall_close_px)),
        structure=_disk(wall_open_px),
    )
    free = ~wall
    dist = ndimage.distance_transform_edt(free)  # one EDT serves all candidates

    def _segment(r_min: int) -> np.ndarray | None:
        """Room grid via hierarchical multi-scale markers (0 = outside), or None.

        Markers are claimed coarse-to-fine: a space gets its marker at the
        LARGEST radius its inscribed disk supports (halls at r=48, offices at
        r=32, corridors at r=16...), and finer-scale components only become new
        markers where no coarser marker exists. A single-scale rule cannot work
        here: door necks require r > door_halfwidth while corridors require
        r < corridor_halfwidth, and on real sheets those windows don't overlap
        across all spaces. `r_min` bounds the finest marker scale (below it,
        text-gap debris would seed). Watershed on -dist then floods every marker
        GEODESICALLY within free space (never across walls); regions touching
        the padded border (page background) are dropped as outside."""
        from skimage.segmentation import watershed

        radii = sorted((c for c in candidates if c >= r_min), reverse=True)
        markers = np.zeros(dist.shape, dtype=np.int32)
        claimed = np.zeros(dist.shape, dtype=bool)
        next_id = 1
        for r in radii:
            comp, n = ndimage.label(dist > r)
            if n == 0:
                continue
            touched = np.unique(comp[claimed])
            fresh = np.setdiff1d(np.arange(1, n + 1), touched, assume_unique=True)
            if fresh.size:
                m = np.isin(comp, fresh)
                lbl, k = ndimage.label(m)
                markers[m] = lbl[m] + (next_id - 1)
                next_id += k
            claimed |= comp > 0
        if next_id == 1:
            return None
        assigned = watershed(-dist, markers=markers, mask=free).astype(np.int64)
        border = np.unique(
            np.concatenate(
                [assigned[0, :], assigned[-1, :], assigned[:, 0], assigned[:, -1]]
            )
        )
        outside_ids = border[border != 0]
        assigned[np.isin(assigned, outside_ids)] = 0
        return assigned

    def _score(assigned: np.ndarray) -> int:
        """Sane rooms: big enough to be real, small enough to not be a merge blob."""
        vals, counts = np.unique(assigned[assigned != 0], return_counts=True)
        total = counts.sum()
        if total == 0:
            return 0
        return int(((counts >= min_room_px) & (counts <= 0.25 * total)).sum())

    grids, scores = {}, {}
    for r in candidates:
        grid = _segment(r)
        grids[int(r)] = grid
        scores[int(r)] = _score(grid) if grid is not None else 0
    # knee rule: the finest scales over-segment (debris pockets seed extra
    # markers and inflate the sane-room count), so take the LARGEST r_min whose
    # score stays within 90% of the maximum — coarsest competitive segmentation
    top = max(scores.values())
    best_r = max((r for r, s in scores.items() if s >= 0.9 * top), default=None)
    best_grid = grids.get(best_r)
    if best_grid is None or not (best_grid > 0).any():
        raise ValueError(
            f"{building_id}: no enclosed rooms found at any split radius "
            f"{list(candidates)} — image may not match clean-CAD-raster assumptions"
        )
    split_used = best_r

    # unpad everything back to the source image frame
    room_ix = best_grid[pad:-pad, pad:-pad]
    wall = wall[pad:-pad, pad:-pad]

    # absorb tiny fragments into their most-contacted neighbor
    room_ix = _absorb_small(room_ix, min_room_px)
    labels = [int(v) for v in np.unique(room_ix) if v != 0]
    remap = {old: k for k, old in enumerate(labels)}
    room_grid = -np.ones_like(room_ix)
    for old, k in remap.items():
        room_grid[room_ix == old] = k
    n_rooms = len(labels)

    # nodes
    scale = 1.0 / px_per_m if px_per_m else 1.0
    nodes: dict[str, Node] = {}
    room_ids = []
    for k in range(n_rooms):
        m = room_grid == k
        ys, xs = np.nonzero(m)
        rid = f"s{k:03d}"
        room_ids.append(rid)
        nodes[rid] = Node(
            id=rid,
            area=float(m.sum()) * scale * scale,
            centroid=(float(xs.mean()) * scale, float(ys.mean()) * scale),
        )

    # adjacency. Nearest-seed assignment partitions EVERY interior free pixel, so
    # rooms joined by a door gap touch pixel-to-pixel there, while wall-separated
    # rooms always have wall (room_grid == -1) between them:
    #   touch within 2px            -> opening edge (R0 E_conn)
    #   meet only across wall reach -> wall-only adjacency (R2 material, counted)
    reach = adjacency_reach_px or (2 * wall_open_px + 4)
    edges: list[Edge] = []
    n_open, n_wallonly = 0, 0
    boxes = ndimage.find_objects(room_grid + 1)  # slice per room, +1: bg -1 -> 0
    margin = reach + 4

    def _grown(k: int, r: int, window: tuple[slice, slice]) -> np.ndarray:
        return ndimage.binary_dilation(
            room_grid[window] == k, structure=_disk(r)
        )

    for a in range(n_rooms):
        for b in range(a + 1, n_rooms):
            win = _union_box(boxes[a], boxes[b], margin, room_grid.shape)
            if win is None:
                continue
            if (_grown(a, 2, win) & (room_grid[win] == b)).any():
                edges.append(Edge(u=room_ids[a], v=room_ids[b]))
                n_open += 1
            elif (
                _grown(a, reach // 2 + 1, win)
                & _grown(b, reach // 2 + 1, win)
                & wall[win]
            ).any():
                n_wallonly += 1  # separated by wall within reach: not R0 E_conn

    g = SpectrumGraph(
        level=0,
        building_id=building_id,
        nodes=nodes,
        edges=edges,
        containment={},
        meta={
            "source": "topospec.data.raster",
            "params": {
                "ink_threshold": ink_threshold,
                "wall_close_px": wall_close_px,
                "wall_open_px": wall_open_px,
                "split_erosion_px": split_used,
                "split_auto_scores": scores,
                "min_room_px": min_room_px,
                "adjacency_reach_px": reach,
                "px_per_m": px_per_m,
            },
        },
    )
    stats = {
        "n_rooms": n_rooms,
        "n_edges_opening": n_open,
        "n_adjacent_wall_only": n_wallonly,
        "split_erosion_px_used": split_used,
        "split_auto_scores": scores,
        "interior_px": int((room_grid >= 0).sum()),
        "wall_px": int(wall.sum()),
        "image_shape": [gray.shape[0] - 2 * pad, gray.shape[1] - 2 * pad],
    }
    return RasterExtraction(
        graph=g, room_ix=room_grid, room_ids=room_ids, wall_mask=wall, stats=stats
    )


def _disk(r: int) -> np.ndarray:
    if r <= 0:
        return np.ones((1, 1), dtype=bool)
    y, x = np.ogrid[-r : r + 1, -r : r + 1]
    return (x * x + y * y) <= r * r


def _union_box(
    sa: tuple[slice, slice] | None,
    sb: tuple[slice, slice] | None,
    margin: int,
    shape: tuple[int, int],
) -> tuple[slice, slice] | None:
    """Expanded union of two bounding boxes, or None if farther than margin."""
    if sa is None or sb is None:
        return None
    # quick rejection: boxes farther apart than margin can't interact
    for d in (0, 1):
        if sa[d].start - sb[d].stop > margin or sb[d].start - sa[d].stop > margin:
            return None
    return tuple(
        slice(
            max(0, min(sa[d].start, sb[d].start) - margin),
            min(shape[d], max(sa[d].stop, sb[d].stop) + margin),
        )
        for d in (0, 1)
    )


def _absorb_small(room_ix: np.ndarray, min_px: int) -> np.ndarray:
    out = room_ix.copy()
    for _ in range(8):  # iterate: absorption can create new small components
        vals, counts = np.unique(out[out != 0], return_counts=True)
        small = [int(v) for v, c in zip(vals.tolist(), counts.tolist(), strict=True) if c < min_px]
        if not small:
            break
        for v in small:
            m = out == v
            ring = ndimage.binary_dilation(m, structure=_disk(2)) & ~m
            nb_vals = out[ring]
            nb_vals = nb_vals[(nb_vals != 0) & (nb_vals != v)]
            if nb_vals.size:
                out[m] = np.bincount(nb_vals).argmax()
            else:
                out[m] = 0  # isolated speck: drop to background
    return out


def pde_inputs(ex: RasterExtraction) -> tuple[np.ndarray, np.ndarray, dict]:
    """Adapt an extraction to labels/pde.py: (interior, room_ix, transform).

    Interior = all room pixels; door gaps between rooms are free pixels ALREADY
    inside room regions (nearest-seed assignment covers them), so heat can flow
    between connected rooms; walls stay Dirichlet boundary.
    """
    interior = ex.room_ix >= 0
    tr = {"room_ids": ex.room_ids, "resolution": 1.0}
    return interior, ex.room_ix, tr


def overlay_figure(
    image: np.ndarray, ex: RasterExtraction, out_path: str | Path
) -> None:
    """Save a QA overlay: room segmentation + graph drawn over the source raster."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gray = _to_gray(image)
    h, w = gray.shape
    fig, ax = plt.subplots(figsize=(min(16, w / 120), min(16, h / 120)))
    ax.imshow(gray, cmap="gray", vmin=0, vmax=255)
    masked = np.ma.masked_where(ex.room_ix < 0, ex.room_ix)
    ax.imshow(masked, cmap="tab20", alpha=0.45, interpolation="nearest")
    pos = {}
    for rid in ex.room_ids:
        n = ex.graph.nodes[rid]
        pos[rid] = n.centroid
        ax.plot(*n.centroid, "o", color="black", ms=3)
    for e in ex.graph.edges:
        (x1, y1), (x2, y2) = pos[e.u], pos[e.v]
        ax.plot([x1, x2], [y1, y2], "-", color="red", lw=1.2, alpha=0.85)
    ax.set_title(
        f"{ex.graph.building_id}: {ex.stats['n_rooms']} rooms, "
        f"{ex.stats['n_edges_opening']} opening edges"
    )
    ax.axis("off")
    fig.savefig(out_path, dpi=110, bbox_inches="tight")
    plt.close(fig)
