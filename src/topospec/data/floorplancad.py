"""FloorPlanCAD vector drawing → SpectrumGraph R0 ingest lane (ROADMAP DATA-7).

FloorPlanCAD ships SVG floor plans whose graphical primitives carry per-primitive
panoptic labels: `semanticId` (class 1..35, 0 = unlabeled background) and
`instanceId` (countable-symbol instance, -1 for "stuff"). Room *polygons are not
shipped* — the plan is a soup of wall/door/window/furniture primitives — so rooms
must be DERIVED from the boundary geometry.

Rather than reimplement segmentation, this lane renders only the boundary classes
(wall/curtain-wall/railing) to a clean "dark ink on white" raster and hands it to
the existing morphology lane `topospec.data.raster.extract_rooms` (DATA-0). That
reuse is deliberate: one segmentation code path serves both the prelim rasters and
the CAD corpora, so its failure modes are inspected once.

Format notes (dissected from the val split, scout report
docs/scout_reports/cad_datasets_2026-07-14.md):
  * root carries only a `viewBox` ("minx miny w h"); no width/height. Sheets are
    clipped to a uniform 140x140 user-unit window.
  * semantic/instance attributes appear in TWO spellings across releases:
    camelCase `semanticId`/`instanceId` (CADTransformer redistribution) and
    hyphenated `semantic-id`/`instance-id` (original release). Both are accepted.
  * primitives are `<path>` (M/L polylines, ~2% elliptical `A` arcs), plus a few
    `<circle>`/`<ellipse>`; `<line>` never appears.

Boundary classes (semanticId): 33 wall, 34 curtain wall, 35 railing. Openings:
1..6 doors, 7..10 windows. Door instances are returned as `door_hints` (raster-
pixel positions) for the future R1/R2 opening-semantics step — this lane emits R0
only.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from topospec.data.raster import RasterExtraction, extract_rooms

# semanticId groupings (raw FloorPlanCAD ids; see anno_config / scout report)
BOUNDARY_CLASSES: tuple[int, ...] = (33, 34, 35)  # wall, curtain wall, railing
DOOR_CLASSES: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
WINDOW_CLASSES: tuple[int, ...] = (7, 8, 9, 10)
BACKGROUND_CLASS = 0

_PRIMITIVE_TAGS = ("path", "circle", "ellipse")
# tokenizer for the path `d` attribute: a command letter OR a signed float
_D_TOKEN = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")
_CURVE_SAMPLES = 16  # points sampled along an arc / bezier segment


@dataclass
class SvgPrimitive:
    """One labelled graphical primitive as one or more polylines in user units."""

    kind: str  # 'path' | 'circle' | 'ellipse'
    semantic_id: int
    instance_id: int
    polylines: list[np.ndarray] = field(default_factory=list)  # each (N, 2) float64

    def points(self) -> np.ndarray:
        """All vertices stacked, (M, 2); empty (0, 2) if the primitive is degenerate."""
        if not self.polylines:
            return np.zeros((0, 2), dtype=np.float64)
        return np.concatenate(self.polylines, axis=0)

    def centroid(self) -> tuple[float, float] | None:
        pts = self.points()
        if pts.size == 0:
            return None
        return float(pts[:, 0].mean()), float(pts[:, 1].mean())


@dataclass
class ParsedSvg:
    """A parsed FloorPlanCAD drawing: its primitives plus the viewBox bounds.

    Iterates and indexes as the primitive list (so it satisfies a "list of
    primitives" contract) while also exposing `viewbox` for rasterization bounds.
    """

    primitives: list[SvgPrimitive]
    viewbox: tuple[float, float, float, float]  # minx, miny, width, height
    source: str = ""

    def __iter__(self):
        return iter(self.primitives)

    def __len__(self) -> int:
        return len(self.primitives)

    def __getitem__(self, i):
        return self.primitives[i]

    @property
    def width(self) -> float:
        return self.viewbox[2]

    @property
    def height(self) -> float:
        return self.viewbox[3]


# --------------------------------------------------------------------------- parse


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _local(tag: str) -> str:
    """Strip the '{namespace}' prefix ElementTree prepends."""
    return tag[tag.find("}") + 1 :] if "}" in tag else tag


def _arc_points(
    p0: tuple[float, float],
    rx: float,
    ry: float,
    phi_deg: float,
    large_arc: int,
    sweep: int,
    p1: tuple[float, float],
    n: int = _CURVE_SAMPLES,
) -> list[tuple[float, float]]:
    """Sample an SVG elliptical arc via the W3C endpoint->center parameterization."""
    x0, y0 = p0
    x1, y1 = p1
    if rx == 0 or ry == 0 or (x0 == x1 and y0 == y1):
        return [p1]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(phi_deg)
    cosp, sinp = math.cos(phi), math.sin(phi)
    dx, dy = (x0 - x1) / 2.0, (y0 - y1) / 2.0
    x1p = cosp * dx + sinp * dy
    y1p = -sinp * dx + cosp * dy
    # correct out-of-range radii (W3C F.6.6)
    lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large_arc == sweep:
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = cosp * cxp - sinp * cyp + (x0 + x1) / 2.0
    cy = sinp * cxp + cosp * cyp + (y0 + y1) / 2.0

    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        length = math.hypot(ux, uy) * math.hypot(vx, vy)
        a = math.acos(max(-1.0, min(1.0, dot / length))) if length else 0.0
        return -a if (ux * vy - uy * vx) < 0 else a

    theta0 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle(
        (x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry
    )
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi
    out = []
    for i in range(1, n + 1):
        t = theta0 + dtheta * (i / n)
        x = cosp * rx * math.cos(t) - sinp * ry * math.sin(t) + cx
        y = sinp * rx * math.cos(t) + cosp * ry * math.sin(t) + cy
        out.append((x, y))
    return out


def _sample_bezier(pts: list[tuple[float, float]], n: int = _CURVE_SAMPLES) -> list[tuple]:
    """De Casteljau sampling of a quadratic/cubic bezier (control points `pts`)."""
    out = []
    for i in range(1, n + 1):
        t = i / n
        cur = list(pts)
        while len(cur) > 1:
            cur = [
                ((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1])
                for a, b in zip(cur[:-1], cur[1:], strict=False)
            ]
        out.append(cur[0])
    return out


def parse_path_d(d: str) -> list[np.ndarray]:
    """Parse an SVG path `d` string into subpath polylines (arcs/beziers sampled).

    Handles M/L/H/V/Z and (absolute or relative) A arc, C/S cubic, Q/T quadratic
    commands — the full grammar FloorPlanCAD uses is M/L/A, the rest are supported
    defensively. Returns a list of (N, 2) float64 arrays, one per subpath.
    """
    tokens = _D_TOKEN.findall(d)
    subpaths: list[np.ndarray] = []
    cur: list[tuple[float, float]] = []
    start: tuple[float, float] = (0.0, 0.0)
    pos: tuple[float, float] = (0.0, 0.0)
    prev_ctrl: tuple[float, float] | None = None
    cmd = ""
    i = 0

    def num() -> float:
        nonlocal i
        while i < len(tokens) and tokens[i][0]:  # skip stray command letters
            i += 1
        val = float(tokens[i][1])
        i += 1
        return val

    def flush() -> None:
        if len(cur) >= 2:
            subpaths.append(np.asarray(cur, dtype=np.float64))

    while i < len(tokens):
        letter, _ = tokens[i]
        if letter:
            cmd = letter
            i += 1
            if cmd in "Zz":
                if cur:
                    cur.append(start)
                flush()
                cur = []
                pos = start
                prev_ctrl = None
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            x, y = num(), num()
            if rel:
                x, y = pos[0] + x, pos[1] + y
            flush()
            cur = [(x, y)]
            start = pos = (x, y)
            cmd = "l" if rel else "L"  # implicit lineto for extra coordinate pairs
            prev_ctrl = None
        elif c == "L":
            x, y = num(), num()
            if rel:
                x, y = pos[0] + x, pos[1] + y
            cur.append((x, y))
            pos = (x, y)
            prev_ctrl = None
        elif c == "H":
            x = num()
            x = pos[0] + x if rel else x
            cur.append((x, pos[1]))
            pos = (x, pos[1])
            prev_ctrl = None
        elif c == "V":
            y = num()
            y = pos[1] + y if rel else y
            cur.append((pos[0], y))
            pos = (pos[0], y)
            prev_ctrl = None
        elif c in ("C", "S", "Q", "T"):
            controls = [pos]
            if c == "C":
                controls += [(num(), num()), (num(), num()), (num(), num())]
            elif c == "S":
                refl = pos if prev_ctrl is None else (2 * pos[0] - prev_ctrl[0], 2 * pos[1] - prev_ctrl[1])
                controls += [refl, (num(), num()), (num(), num())]
            elif c == "Q":
                controls += [(num(), num()), (num(), num())]
            else:  # T
                refl = pos if prev_ctrl is None else (2 * pos[0] - prev_ctrl[0], 2 * pos[1] - prev_ctrl[1])
                controls += [refl, (num(), num())]
            if rel:
                controls = [controls[0]] + [(pos[0] + px, pos[1] + py) for px, py in controls[1:]]
            sampled = _sample_bezier(controls)
            cur.extend(sampled)
            prev_ctrl = controls[-2]
            pos = sampled[-1]
        elif c == "A":
            rx, ry, rot = num(), num(), num()
            large, sweep = int(num()), int(num())
            x, y = num(), num()
            if rel:
                x, y = pos[0] + x, pos[1] + y
            for p in _arc_points(pos, rx, ry, rot, large, sweep, (x, y)):
                cur.append(p)
            pos = (x, y)
            prev_ctrl = None
        else:  # unknown command: consume one number to avoid an infinite loop
            num()
    flush()
    return subpaths


def _circle_polyline(cx: float, cy: float, r: float, n: int = 48) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, n, endpoint=True)
    return np.stack([cx + r * np.cos(t), cy + r * np.sin(t)], axis=1)


def _ellipse_polyline(cx: float, cy: float, rx: float, ry: float, n: int = 48) -> np.ndarray:
    t = np.linspace(0, 2 * np.pi, n, endpoint=True)
    return np.stack([cx + rx * np.cos(t), cy + ry * np.sin(t)], axis=1)


def parse_svg(path: str | Path) -> ParsedSvg:
    """Parse a FloorPlanCAD SVG into labelled primitives + viewBox bounds.

    Accepts both attribute spellings (`semanticId`/`semantic-id`,
    `instanceId`/`instance-id`); missing semantic -> 0, missing instance -> -1.
    """
    root = ET.parse(str(path)).getroot()
    primitives: list[SvgPrimitive] = []
    for el in root.iter():
        tag = _local(el.tag)
        if tag not in _PRIMITIVE_TAGS:
            continue
        a = el.attrib
        sid = _to_int(a.get("semanticId", a.get("semantic-id")), BACKGROUND_CLASS)
        iid = _to_int(a.get("instanceId", a.get("instance-id")), -1)
        if tag == "path":
            polylines = parse_path_d(a.get("d", ""))
        elif tag == "circle":
            polylines = [
                _circle_polyline(
                    float(a.get("cx", 0)), float(a.get("cy", 0)), float(a.get("r", 0))
                )
            ]
        else:  # ellipse
            polylines = [
                _ellipse_polyline(
                    float(a.get("cx", 0)),
                    float(a.get("cy", 0)),
                    float(a.get("rx", 0)),
                    float(a.get("ry", 0)),
                )
            ]
        polylines = [p for p in polylines if p.shape[0] >= 1]
        primitives.append(SvgPrimitive(tag, sid, iid, polylines))

    viewbox = _read_viewbox(root, primitives)
    return ParsedSvg(primitives=primitives, viewbox=viewbox, source=str(path))


def _read_viewbox(
    root: ET.Element, primitives: list[SvgPrimitive]
) -> tuple[float, float, float, float]:
    vb = root.attrib.get("viewBox")
    if vb:
        parts = [float(x) for x in vb.replace(",", " ").split()]
        if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
            return (parts[0], parts[1], parts[2], parts[3])
    w = root.attrib.get("width")
    h = root.attrib.get("height")
    if w and h:
        try:
            return (0.0, 0.0, float(re.sub(r"[^0-9.]", "", w)), float(re.sub(r"[^0-9.]", "", h)))
        except ValueError:
            pass
    # last resort: bounding box of all geometry
    allpts = np.concatenate(
        [p.points() for p in primitives if p.points().size] or [np.zeros((1, 2))]
    )
    minx, miny = allpts.min(axis=0)
    maxx, maxy = allpts.max(axis=0)
    return (float(minx), float(miny), float(maxx - minx) or 1.0, float(maxy - miny) or 1.0)


# ----------------------------------------------------------------------- rasterize


def rasterize_walls(
    primitives,
    px_per_unit: float,
    viewbox: tuple[float, float, float, float] | None = None,
    wall_stroke_px: int = 3,
    boundary_classes: tuple[int, ...] = BOUNDARY_CLASSES,
) -> np.ndarray:
    """Render only boundary-class primitives as dark ink on a white raster.

    FloorPlanCAD walls are thin face-lines, so they are stroked a few pixels wide
    (`wall_stroke_px`) to form solid barriers that `extract_rooms` can close over,
    while door gaps in the wall geometry stay open. Returns an (H, W) uint8 array
    (0 = ink, 255 = white); SVG y (downward) maps directly to image rows.

    `primitives` may be a `ParsedSvg` (its viewBox is used) or a bare primitive
    list (pass `viewbox`, else bounds are taken from the boundary geometry).
    """
    if viewbox is None:
        viewbox = getattr(primitives, "viewbox", None)
    walls = [p for p in primitives if p.semantic_id in boundary_classes]
    if viewbox is None:
        pts = np.concatenate(
            [p.points() for p in walls if p.points().size] or [np.zeros((1, 2))]
        )
        minx, miny = pts.min(axis=0)
        maxx, maxy = pts.max(axis=0)
        viewbox = (float(minx), float(miny), float(maxx - minx) or 1.0, float(maxy - miny) or 1.0)
    minx, miny, w, h = viewbox
    width_px = max(1, int(math.ceil(w * px_per_unit)))
    height_px = max(1, int(math.ceil(h * px_per_unit)))

    img = Image.new("L", (width_px, height_px), color=255)
    draw = ImageDraw.Draw(img)
    for prim in walls:
        for poly in prim.polylines:
            if poly.shape[0] < 2:
                continue
            xy = [
                ((float(x) - minx) * px_per_unit, (float(y) - miny) * px_per_unit)
                for x, y in poly
            ]
            draw.line(xy, fill=0, width=wall_stroke_px, joint="curve")
    return np.asarray(img, dtype=np.uint8)


# -------------------------------------------------------------------------- build


def build_r0(
    svg_path: str | Path,
    px_per_unit: float = 10.0,
    wall_stroke_px: int = 3,
    **extract_kwargs,
) -> RasterExtraction:
    """FloorPlanCAD SVG -> validated R0 SpectrumGraph via the raster lane (DATA-7).

    Renders the wall/curtain-wall/railing boundary, segments rooms with
    `extract_rooms` (auto split-scale by default), and records door-primitive
    positions in raster coordinates as `door_hints` for the future R1/R2 opening
    step (this lane emits R0 only). `building_id` is `fpcad:<stem>`; provenance and
    `px_per_unit` are stamped into the graph meta.

    Morphology defaults differ from the raster lane's: this raster contains ONLY
    boundary strokes (no furniture/text to reject), so the wall-opening step is
    minimized (`wall_open_px=1`) to avoid eroding thin face-lines, and closing is
    raised (`wall_close_px=3`) to fuse FloorPlanCAD's double-line walls into solid
    barriers. Both are overridable via kwargs.
    """
    extract_kwargs.setdefault("wall_open_px", 1)
    extract_kwargs.setdefault("wall_close_px", 3)
    parsed = parse_svg(svg_path)
    wall_img = rasterize_walls(parsed, px_per_unit, wall_stroke_px=wall_stroke_px)
    stem = Path(svg_path).stem

    ex = extract_rooms(wall_img, building_id=f"fpcad:{stem}", **extract_kwargs)

    minx, miny, _, _ = parsed.viewbox
    door_hints = _door_hints(parsed, minx, miny, px_per_unit)
    n_wall = sum(1 for p in parsed.primitives if p.semantic_id in BOUNDARY_CLASSES)

    ex.graph.meta["fpcad"] = {
        "builder": "topospec.data.floorplancad",
        "source_svg": stem,
        "px_per_unit": px_per_unit,
        "wall_stroke_px": wall_stroke_px,
        "viewbox": list(parsed.viewbox),
        "n_primitives": len(parsed.primitives),
        "n_wall_primitives": n_wall,
        "n_door_instances": len(door_hints),
    }
    ex.graph.meta["door_hints"] = door_hints  # raster-px positions for R1/R2 (DATA-7)
    ex.stats["door_hints"] = door_hints
    ex.stats["n_door_hints"] = len(door_hints)
    ex.stats["n_wall_primitives"] = n_wall
    return ex


def _door_hints(
    parsed: ParsedSvg, minx: float, miny: float, px_per_unit: float
) -> list[dict]:
    """One hint per door INSTANCE: its centroid in raster pixels + class id."""
    by_inst: dict[int, list[SvgPrimitive]] = {}
    loose: list[SvgPrimitive] = []
    for p in parsed.primitives:
        if p.semantic_id not in DOOR_CLASSES:
            continue
        if p.instance_id is not None and p.instance_id >= 0:
            by_inst.setdefault(p.instance_id, []).append(p)
        else:
            loose.append(p)

    hints: list[dict] = []

    def _emit(prims: list[SvgPrimitive], inst: int) -> None:
        pts = np.concatenate([q.points() for q in prims if q.points().size] or [np.zeros((0, 2))])
        if pts.size == 0:
            return
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        hints.append(
            {
                "instance_id": int(inst),
                "semantic_id": int(prims[0].semantic_id),
                "x_px": float((cx - minx) * px_per_unit),
                "y_px": float((cy - miny) * px_per_unit),
            }
        )

    for inst, prims in sorted(by_inst.items()):
        _emit(prims, inst)
    for k, p in enumerate(loose):
        _emit([p], -1 - k)
    return hints
