"""FloorPlanCAD ingest lane (DATA-7): parser + rooms-from-primitives R0 build.

Parser tests are self-contained (synthetic SVG strings, both attribute spellings).
The end-to-end test runs the real derivation on a small committed fixture and only
asserts what the pipeline can honestly guarantee on FloorPlanCAD's cropped sheets
(see tests/fixtures/floorplancad/README.md and the QA note in the scout report).
"""

import numpy as np
import pytest

from topospec.data.floorplancad import (
    BOUNDARY_CLASSES,
    ParsedSvg,
    SvgPrimitive,
    build_r0,
    parse_path_d,
    parse_svg,
    rasterize_walls,
)
from topospec.graphs.validate import validate_graph

FIXTURE = "0402-0048"  # committed under tests/fixtures/floorplancad/
FIXTURE_ROOMS = (5, 16)  # inspected range; see fixture README


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(
        '<svg version="1.1" viewBox="0 0 10 10" '
        'xmlns="http://www.w3.org/2000/svg">' + body + "</svg>"
    )
    return p


def test_parse_camelcase_spelling(tmp_path):
    p = _write(
        tmp_path, "camel.svg",
        '<g><path d="M 1,1 L 9,1" semanticId="33" instanceId="-1"/>'
        '<path d="M 2,2 L 8,2" semanticId="1" instanceId="5"/></g>',
    )
    prims = parse_svg(p).primitives
    assert (prims[0].semantic_id, prims[0].instance_id) == (33, -1)
    assert (prims[1].semantic_id, prims[1].instance_id) == (1, 5)


def test_parse_hyphenated_spelling(tmp_path):
    """Original FloorPlanCAD release uses hyphenated attrs; must parse identically."""
    p = _write(
        tmp_path, "hyphen.svg",
        '<g><path d="M 1,1 L 9,1" semantic-id="33" instance-id="-1"/>'
        '<path d="M 2,2 L 8,2" semantic-id="7" instance-id="9"/></g>',
    )
    prims = parse_svg(p).primitives
    assert (prims[0].semantic_id, prims[0].instance_id) == (33, -1)
    assert (prims[1].semantic_id, prims[1].instance_id) == (7, 9)


def test_parse_defaults_missing_labels(tmp_path):
    """Missing semantic -> 0 (background); missing instance -> -1 (stuff)."""
    p = _write(tmp_path, "bare.svg", '<path d="M 1,1 L 9,9"/>')
    prim = parse_svg(p).primitives[0]
    assert prim.semantic_id == 0
    assert prim.instance_id == -1


def test_parse_path_polyline_coords(tmp_path):
    p = _write(tmp_path, "poly.svg", '<path d="M 0,0 L 10,0 L 10,10" semanticId="33"/>')
    poly = parse_svg(p).primitives[0].polylines[0]
    assert poly.shape == (3, 2)
    np.testing.assert_allclose(poly, [[0, 0], [10, 0], [10, 10]])


def test_parse_path_arc_is_sampled():
    """`A` arc commands are sampled into several vertices, not dropped."""
    polys = parse_path_d("M 0,0 A 5 5 0 0 1 10 0")
    assert polys and polys[0].shape[0] > 3  # arc expanded to a polyline


def test_parse_circle_and_ellipse(tmp_path):
    p = _write(
        tmp_path, "ce.svg",
        '<circle cx="5" cy="5" r="2" semanticId="19"/>'
        '<ellipse cx="3" cy="3" rx="2" ry="1" semanticId="27"/>',
    )
    prims = parse_svg(p).primitives
    kinds = {pr.kind for pr in prims}
    assert kinds == {"circle", "ellipse"}
    assert all(pr.polylines[0].shape[0] > 8 for pr in prims)  # sampled polygons


def test_rasterize_renders_only_boundary_classes():
    """Only wall/curtain-wall/railing become ink; furniture is not drawn."""
    wall = SvgPrimitive("path", 33, -1, [np.array([[1.0, 5.0], [9.0, 5.0]])])
    chair = SvgPrimitive("path", 13, 3, [np.array([[1.0, 8.0], [9.0, 8.0]])])
    parsed = ParsedSvg([wall, chair], viewbox=(0.0, 0.0, 10.0, 10.0))
    img = rasterize_walls(parsed, px_per_unit=10.0, wall_stroke_px=3)
    assert img.shape == (100, 100)
    assert (img[48:53, 10:90] < 128).any()  # wall stroke around y=50 is ink
    assert (img[75:82, 10:90] >= 128).all()  # chair row (y~80) stays white


def test_rasterize_bare_list_uses_geometry_bounds():
    """rasterize_walls accepts a plain primitive list (bounds from wall geometry)."""
    wall = SvgPrimitive("path", 34, -1, [np.array([[0.0, 0.0], [10.0, 0.0]])])
    img = rasterize_walls([wall], px_per_unit=5.0)
    assert img.ndim == 2 and (img < 128).any()


@pytest.fixture(scope="module")
def extraction():
    """Build the fixture R0 once (pinned split for a fast, deterministic test)."""
    from pathlib import Path

    p = Path(__file__).parent / "fixtures" / "floorplancad" / f"{FIXTURE}.svg"
    if not p.exists():
        pytest.skip(f"fixture {p} not present")
    return build_r0(p, px_per_unit=10.0, wall_stroke_px=5,
                    wall_close_px=4, split_erosion_px=14, min_room_px=900)


def test_build_r0_validates_and_segments(extraction):
    assert validate_graph(extraction.graph)
    assert extraction.graph.level == 0
    assert extraction.graph.building_id == f"fpcad:{FIXTURE}"
    lo, hi = FIXTURE_ROOMS
    assert lo <= extraction.stats["n_rooms"] <= hi


def test_build_r0_has_opening_and_door_hints(extraction):
    assert extraction.stats["n_edges_opening"] >= 1  # door-punch yields >=1 opening
    assert extraction.stats["n_door_hints"] >= 1
    # door_hints carry raster-pixel positions for the future R1/R2 step
    h = extraction.graph.meta["door_hints"][0]
    assert {"instance_id", "semantic_id", "x_px", "y_px"} <= h.keys()


def test_build_r0_records_provenance(extraction):
    fp = extraction.graph.meta["fpcad"]
    assert fp["builder"] == "topospec.data.floorplancad"
    assert fp["px_per_unit"] == 10.0
    assert fp["source_svg"] == FIXTURE
    assert fp["n_wall_primitives"] > 0
    assert tuple(BOUNDARY_CLASSES) == (33, 34, 35)
