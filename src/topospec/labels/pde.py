"""Y_pde — steady-state heat equation on true floor geometry (plan §4.2).

Analytically defined diffusion target: we solve  -Δu = f  on the floor's interior
(masked finite-difference 5-point Laplacian, scipy sparse direct solve) with Dirichlet
conditions on specified cells, then aggregate per-room means and ranks. Ground truth is
a converged numerical solution of an exactly specified PDE problem (decision D-002;
convergence checks on real plans are ROADMAP A-1).

Geometry interface: rooms as shapely Polygons. The solver itself is geometry-agnostic:
it takes a boolean interior mask + Dirichlet value grid, so tests can drive it with
analytic cases directly.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def solve_masked_poisson(
    interior: np.ndarray,
    dirichlet: np.ndarray,
    source: np.ndarray | float = 0.0,
    h: float = 1.0,
) -> np.ndarray:
    """Solve -Δu = source on {interior}, u = dirichlet elsewhere adjacent.

    Args:
        interior: (H, W) bool — cells where u is unknown.
        dirichlet: (H, W) float — boundary values; read at non-interior cells adjacent
            to interior ones. Cells outside the domain that are never referenced may
            hold anything (use 0).
        source: forcing term f, scalar or (H, W).
        h: grid spacing.

    Returns:
        (H, W) float64 field; u = dirichlet at non-interior cells, solved at interior.
    """
    interior = np.asarray(interior, dtype=bool)
    dirichlet = np.asarray(dirichlet, dtype=np.float64)
    if interior.shape != dirichlet.shape:
        raise ValueError("interior and dirichlet must have identical shapes")
    hgt, wid = interior.shape
    n = int(interior.sum())
    if n == 0:
        raise ValueError("no interior cells")
    f = np.broadcast_to(np.asarray(source, dtype=np.float64), interior.shape)

    idx = -np.ones(interior.shape, dtype=np.int64)
    idx[interior] = np.arange(n)

    rows, cols, vals = [], [], []
    rhs = np.zeros(n, dtype=np.float64)
    offsets = ((1, 0), (-1, 0), (0, 1), (0, -1))
    ii, jj = np.nonzero(interior)
    for i, j in zip(ii.tolist(), jj.tolist(), strict=True):
        k = idx[i, j]
        rows.append(k)
        cols.append(k)
        vals.append(4.0)
        rhs[k] += f[i, j] * h * h
        for di, dj in offsets:
            ni, nj = i + di, j + dj
            if 0 <= ni < hgt and 0 <= nj < wid and interior[ni, nj]:
                rows.append(k)
                cols.append(idx[ni, nj])
                vals.append(-1.0)
            else:
                # Dirichlet neighbor (including out-of-bounds treated as boundary)
                bval = dirichlet[ni, nj] if 0 <= ni < hgt and 0 <= nj < wid else 0.0
                rhs[k] += bval

    a_mat = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    u_int = spla.spsolve(a_mat, rhs)

    u = dirichlet.copy()
    u[interior] = u_int
    return u


def rasterize_rooms(
    room_polygons: dict[str, "object"], resolution: float
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Rasterize shapely room polygons to (interior mask, room-id grid, transform).

    Returns interior (H, W) bool, room_ix (H, W) int (-1 outside; else index into
    sorted room ids), and a transform dict {x0, y0, resolution, room_ids}.
    """
    from shapely.geometry import Point
    from shapely.ops import unary_union

    room_ids = sorted(room_polygons)
    union = unary_union([room_polygons[r] for r in room_ids])
    x0, y0, x1, y1 = union.bounds
    pad = resolution
    x0, y0 = x0 - pad, y0 - pad
    wid = int(np.ceil((x1 - x0 + pad) / resolution)) + 1
    hgt = int(np.ceil((y1 - y0 + pad) / resolution)) + 1

    interior = np.zeros((hgt, wid), dtype=bool)
    room_ix = -np.ones((hgt, wid), dtype=np.int64)
    prepared = [(k, room_polygons[r]) for k, r in enumerate(room_ids)]
    # sample CELL CENTERS (half-offset): grid points never land exactly on shared
    # room boundaries, so inter-room walls are not misread as exterior boundary
    for i in range(hgt):
        for j in range(wid):
            p = Point(x0 + (j + 0.5) * resolution, y0 + (i + 0.5) * resolution)
            for k, poly in prepared:
                if poly.covers(p):
                    interior[i, j] = True
                    room_ix[i, j] = k
                    break
    return interior, room_ix, {"x0": x0, "y0": y0, "resolution": resolution, "room_ids": room_ids}


def per_room_field(
    room_polygons: dict[str, "object"],
    resolution: float = 0.25,
    source: float = 1.0,
    boundary_value: float = 0.0,
) -> dict[str, float]:
    """Y_pde per-room means: solve -Δu = source with u = boundary_value on the
    exterior boundary of the floor union, aggregate cell means per room."""
    interior, room_ix, tr = rasterize_rooms(room_polygons, resolution)
    dirichlet = np.full(interior.shape, boundary_value, dtype=np.float64)
    u = solve_masked_poisson(interior, dirichlet, source=source, h=resolution)
    out: dict[str, float] = {}
    for k, rid in enumerate(tr["room_ids"]):
        cells = u[(room_ix == k) & interior]
        if cells.size == 0:
            raise ValueError(
                f"room {rid} has no interior cells at resolution {resolution}; refine"
            )
        out[rid] = float(cells.mean())
    return out
