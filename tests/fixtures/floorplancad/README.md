# FloorPlanCAD test fixture

`0402-0048.svg` — one drawing from the FloorPlanCAD **validation** split
(`val/svg_gt/0402-0048.svg`), 88,507 bytes, copied verbatim from
`data/raw/floorplancad_sample/_source_val.zip`
(sha256 of the zip: `cd6bc7c910d2563c00f70fda05b9deb548094aedbf1cde15ef93e0ee9282702f`;
provenance in `docs/scout_reports/cad_datasets_2026-07-14.md`).

License: **CC BY-NC 4.0** (annotations). Redistributed here for non-commercial
research testing only, attributing FloorPlanCAD (Fan et al., CVPR 2021).

## Why this sheet

Used by `tests/test_floorplancad.py` to exercise `build_r0` end-to-end. With the
test's parameters (`px_per_unit=10, wall_stroke_px=5, wall_close_px=4,
split_erosion_px=14, min_room_px=900`) it segments into ~10 rooms with 2 door-punch
opening edges and 6 door hints, and validates as R0.

It was chosen as the **most balanced result of a full 810-sheet search**, NOT
because it is clean. It is honestly representative of FloorPlanCAD's limitation for
rooms-from-primitives:

- FloorPlanCAD sheets are **140×140-unit CROPS of larger buildings** — zero of the
  810 val sheets is a self-contained multi-room plan (enclosed interior ≥12% of the
  sheet). Walls run off the sheet edge, so much of the interior leaks to the page
  margin and is (correctly) dropped as "outside".
- Walls are **continuous double-lines through doorways** (the door is a separate
  symbol, semanticId 1–6), so a walls-only raster seals rooms; `build_r0` punches a
  gap at each door instance to recover R0 connectivity.

So this fixture is a pipeline-liveness fixture, not a quality benchmark. Segmentation
quality on FloorPlanCAD is discussed in the scout report; the institutional-corpus
recommendation is ArchCAD-400K (self-contained drawings) once access is granted.
