"""PDE solver validation against analytic solutions (decision D-002; ROADMAP A-1)."""

import numpy as np
import pytest

from topospec.labels.pde import per_room_field, solve_masked_poisson


def test_laplace_linear_profile():
    """Laplace on a strip with u=0 / u=1 ends -> linear profile."""
    hgt, wid = 5, 41
    interior = np.zeros((hgt, wid), dtype=bool)
    interior[1:-1, 1:-1] = True
    dirichlet = np.zeros((hgt, wid))
    dirichlet[:, -1] = 1.0
    # top/bottom rows mirror the interior (insulated strip approximated by tall grid);
    # instead: make the strip periodic-free by setting top/bottom to the linear profile
    xs = np.linspace(0, 1, wid)
    dirichlet[0, :] = xs
    dirichlet[-1, :] = xs
    dirichlet[:, 0] = 0.0
    u = solve_masked_poisson(interior, dirichlet, source=0.0, h=1.0 / (wid - 1))
    expected = np.tile(xs, (hgt, 1))
    np.testing.assert_allclose(u[interior], expected[interior], atol=1e-8)


def test_poisson_1d_parabola():
    """-u'' = 1 on (0,1), u(0)=u(1)=0 -> u = x(1-x)/2, max 0.125 at center."""
    wid = 201
    h = 1.0 / (wid - 1)
    interior = np.zeros((3, wid), dtype=bool)
    interior[1, 1:-1] = True
    xs = np.linspace(0, 1, wid)
    exact = xs * (1 - xs) / 2
    dirichlet = np.zeros((3, wid))
    dirichlet[0, :] = exact  # neighbors above/below pin the 1D behavior
    dirichlet[2, :] = exact
    u = solve_masked_poisson(interior, dirichlet, source=1.0, h=h)
    np.testing.assert_allclose(u[1, 1:-1], exact[1:-1], atol=5e-4)
    assert abs(u[1, wid // 2] - 0.125) < 5e-4


def test_maximum_principle():
    """Laplace solution stays within boundary value range (no source)."""
    rng = np.random.default_rng(3)
    interior = np.zeros((20, 20), dtype=bool)
    interior[1:-1, 1:-1] = True
    dirichlet = rng.uniform(0, 10, size=(20, 20))
    u = solve_masked_poisson(interior, dirichlet, source=0.0)
    assert u[interior].max() <= dirichlet.max() + 1e-9
    assert u[interior].min() >= dirichlet.min() - 1e-9


def test_per_room_field_interior_hotter_than_edge():
    """Uniform source, cold exterior boundary: an interior room is warmer than a
    corner room (diffusion distance-to-boundary effect)."""
    from shapely.geometry import box

    rooms = {
        "corner": box(0, 0, 4, 4),
        "middle": box(4, 0, 8, 4),
        "far": box(8, 0, 12, 4),
        "center": box(4, 4, 8, 8),
        "top": box(4, 8, 8, 12),
    }
    means = per_room_field(rooms, resolution=0.5, source=1.0, boundary_value=0.0)
    assert set(means) == set(rooms)
    assert all(v > 0 for v in means.values())
    assert means["center"] > means["corner"]


def test_per_room_field_too_coarse_raises():
    from shapely.geometry import box

    rooms = {"tiny": box(0, 0, 0.1, 0.1), "big": box(1, 0, 5, 5)}
    with pytest.raises(ValueError, match="refine"):
        per_room_field(rooms, resolution=2.0)
