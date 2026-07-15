"""Render MSD plans -> clean raster floorplans for the Tesseract2 pipeline (D-014).

The pivot (DECISIONS D-014) derives every tier FROM THE RASTER via Tesseract2;
graph-shipping datasets like MSD become validation sources. This prototype turns an
MSD `graph_out` plan (room polygons + types + access edges) into a clean raster that
Tesseract2 can consume:

  * white background, solid dark WALLS along every room-polygon boundary (~3 px);
  * approximate door/opening GAPS punched at each access edge — MSD ships doors only
    as edge attributes (no door geometry), so the opening is placed at the nearest
    point between the two connected room polygons (shapely). This is an APPROXIMATION:
    there is no door symbol/arc and no true door position (see report);
  * room-type TEXT LABELS at each room centroid (DejaVu Sans ~14 px) for Tesseract's
    CRAFT text stage.

Resolution is auto-scaled so rooms are ~100+ px. This is a standalone renderer that
reads the raw pickles directly (does NOT import the msd loader / graphs package,
which are under schema-v2 rewrite). Login-node safe for a small sample; corpus-scale
rendering should go through slurm.
"""

from __future__ import annotations

import math
import pickle
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# room_type is an int index into this (MSD constants.py, verbatim)
ROOM_NAMES = [
    "Bedroom", "Livingroom", "Kitchen", "Dining", "Corridor", "Stairs",
    "Storeroom", "Bathroom", "Balcony", "Structure", "Door", "Entrance Door", "Window",
]
# MSD room type -> the TEXT drawn on the raster, mapped to Tesseract2's room
# vocabulary (Models/Interpreter/text_interpreter.py valid_room_labels; 'hall' is the
# corridor key, 'na' the outdoor key). Stairs is handled by Tesseract's separate
# transition detector. Original MSD types are kept in render_report for audit.
LABEL_REMAP = {
    "Bedroom": "bedroom",
    "Livingroom": "livingroom",   # UNSPACED: CRAFT splits "living room" -> both rejected;
    "Kitchen": "kitchen",         # the unspaced form fuzzy-matches 'living room' (verified)
    "Dining": "diningroom",       # unspaced likewise (avoids the CRAFT word-split)
    "Corridor": "hall",           # hall = corridor
    "Stairs": "stairs",
    "Storeroom": "study",         # no storeroom label in vocab -> generic interior room
    "Bathroom": "bathroom",
    "Balcony": "na",              # na = outdoor
}
ACCESS_GAP_M = {"door": 0.5, "entrance": 0.6, "passage": 0.7}  # opening half-width (m)
RAW = Path("data/raw/msd/graph_out")
OUT = Path("data/derived/msd_render")


def _font(size: int) -> ImageFont.FreeTypeFont:
    from matplotlib import font_manager

    return ImageFont.truetype(font_manager.findfont("DejaVu Sans"), size)


def _draw_door_arc(draw, to_px, opening, room_center, door_w, width: int = 2) -> bool:
    """Draw a CAD door symbol (quarter-circle swing arc + open leaf) at `opening`.

    Hinged at one jamb, swinging toward `room_center` (the larger room). `door_w` is
    the door width in world metres; `to_px` maps world->pixels. Stroke is kept thin
    (2 px, below the 3 px walls) but detectable, so the gate tests the arc convention
    rather than sub-pixel rendering. Returns True if drawn.
    """
    ox, oy = opening
    sx, sy = room_center[0] - ox, room_center[1] - oy  # toward the larger room
    n = math.hypot(sx, sy)
    if n < 1e-9:
        return False
    sx, sy = sx / n, sy / n  # swing (into-room) unit vector
    wx, wy = -sy, sx  # wall direction (perpendicular to swing)
    hinge = (ox - wx * door_w / 2.0, oy - wy * door_w / 2.0)  # one jamb
    closed = (hinge[0] + wx * door_w, hinge[1] + wy * door_w)  # leaf shut (along wall)
    leaf = (hinge[0] + sx * door_w, hinge[1] + sy * door_w)  # leaf open (perp to wall)
    a0 = math.atan2(closed[1] - hinge[1], closed[0] - hinge[0])
    a1 = math.atan2(leaf[1] - hinge[1], leaf[0] - hinge[0])
    d = a1 - a0
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    arc = [
        to_px(hinge[0] + door_w * math.cos(a0 + d * t / 12.0),
              hinge[1] + door_w * math.sin(a0 + d * t / 12.0))
        for t in range(13)
    ]
    draw.line(arc, fill=0, width=width, joint="curve")  # swing arc
    draw.line([to_px(*hinge), to_px(*leaf)], fill=0, width=width)  # open leaf
    return True


def render_plan(
    graph, native_id: str, wall_px: int = 3, pad_px: int = 24, door_style: str = "arc"
) -> tuple[Image.Image, dict]:
    """Render one MSD networkx plan to a clean raster. Returns (image, stats).

    door_style: 'arc'  = punch the opening + draw a CAD door symbol (quarter-circle
                         swing arc + leaf, swinging into the larger room) that the
                         Tesseract door R-CNN is trained on;
                'gap'  = punch the opening only (no symbol);
                'none' = leave walls sealed (no openings).
    """
    rooms = []
    for _key, att in graph.nodes(data=True):
        rt = att.get("room_type")
        geom = att.get("geometry")
        if rt is None or not geom or len(geom) < 3:
            continue
        cen = att.get("centroid")
        name = ROOM_NAMES[int(rt)] if int(rt) < len(ROOM_NAMES) else str(rt)
        rooms.append(
            {
                "name": name,  # original MSD type (auditable)
                "text": LABEL_REMAP.get(name, name.lower()),  # drawn text (Tesseract vocab)
                "poly": np.asarray(geom, dtype=float),
                "centroid": (float(cen[0]), float(cen[1])) if cen is not None else None,
            }
        )
    if not rooms:
        raise ValueError(f"{native_id}: no renderable rooms")

    allpts = np.concatenate([r["poly"] for r in rooms])
    minx, miny = allpts.min(axis=0)
    maxx, maxy = allpts.max(axis=0)
    extent = max(maxx - minx, maxy - miny) or 1.0
    ppm = float(np.clip(1400.0 / extent, 30.0, 60.0))  # rooms land ~100+ px

    def to_px(x, y):  # world (y-up, meters) -> image (y-down, px)
        return ((x - minx) * ppm + pad_px, (maxy - y) * ppm + pad_px)

    w = int((maxx - minx) * ppm) + 2 * pad_px
    h = int((maxy - miny) * ppm) + 2 * pad_px
    img = Image.new("L", (w, h), color=255)
    draw = ImageDraw.Draw(img)

    # walls = every room-polygon boundary
    for r in rooms:
        ring = [to_px(x, y) for x, y in r["poly"]]
        draw.line(ring + [ring[0]], fill=0, width=wall_px, joint="curve")

    # openings at access edges (needs shapely). MSD ships doors only as edge
    # attributes, so the opening is placed at the nearest point between the two
    # connected room polygons; door_style controls the drawn convention.
    n_gaps = n_arcs = 0
    if door_style != "none":
        from shapely.geometry import Polygon
        from shapely.ops import nearest_points

        key_to_poly, key_to_area, key_to_cxy = {}, {}, {}
        for key, att in graph.nodes(data=True):
            g = att.get("geometry")
            if g and len(g) >= 3:
                try:
                    poly = Polygon(g)
                except Exception:
                    continue
                key_to_poly[key] = poly
                key_to_area[key] = poly.area
                key_to_cxy[key] = (poly.centroid.x, poly.centroid.y)
        for u, v, att in graph.edges(data=True):
            gap_m = ACCESS_GAP_M.get(att.get("connectivity"))
            if gap_m is None or u not in key_to_poly or v not in key_to_poly:
                continue
            try:
                p1, p2 = nearest_points(key_to_poly[u], key_to_poly[v])
            except Exception:
                continue
            ox, oy = (p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0
            cx, cy = to_px(ox, oy)
            rpx = gap_m * ppm
            draw.ellipse([cx - rpx, cy - rpx, cx + rpx, cy + rpx], fill=255)  # punch opening
            n_gaps += 1
            if door_style == "arc":
                # swing INTO the larger room; door width sized to the opening
                larger = v if key_to_area[v] >= key_to_area[u] else u
                dcx, dcy = key_to_cxy[larger]
                if _draw_door_arc(draw, to_px, (ox, oy), (dcx, dcy), 2.0 * gap_m):
                    n_arcs += 1

    # room-type text labels at centroids (CRAFT reads these; Tesseract vocabulary)
    font = _font(14)
    for r in rooms:
        if r["centroid"] is None:
            continue
        cx, cy = to_px(*r["centroid"])
        draw.text((cx, cy), r["text"], fill=0, font=font, anchor="mm")

    from collections import Counter

    stats = {"native_id": native_id, "n_rooms": len(rooms), "n_gaps": n_gaps,
             "n_arcs": n_arcs, "door_style": door_style,
             "px_per_m": round(ppm, 1), "size": [w, h],
             # world(m)->px transform so scorers can map GT centroids into the raster:
             # px = (x-minx)*ppm + pad ; py = (maxy-y)*ppm + pad
             "transform": {"minx": float(minx), "miny": float(miny), "maxy": float(maxy),
                           "ppm": ppm, "pad": pad_px},
             "msd_room_types": dict(Counter(r["name"] for r in rooms)),
             "drawn_labels": dict(Counter(r["text"] for r in rooms))}
    return img, stats


# ---------------------------------------------------------------------------
# Door-detector training data (D-016): annotated renders with EXACT door bboxes
# plus style-domain randomization.
#
# render_plan_annotated emits, at render time, the pixel bounding box of every door
# symbol it draws. The symbol is generated from known world geometry (the swing arc
# is sampled analytically), so the box is exact — no post-hoc detection. The
# randomization (wall thickness + single/double-line walls, arc/leaf stroke, single
# vs double swing, hinge side, swing direction, door-frame jambs, wall hatching, and
# k*90 rotation) is what lets a fine-tuned R-CNN generalize from one clean synthetic
# style to real bold double-swing symbols in thick hatched walls (D-016) instead of
# overfitting the thin arc. This is a SEPARATE entry point from render_plan (the
# T0/T1 validation renderer, unchanged); nothing here affects that lane.
# ---------------------------------------------------------------------------

# Randomization ranges are documented so the grader can reproduce the training set
# from a seed. All draws use the passed rng (np.random.Generator) — no global seeding.
DOOR_STYLE_RANGES = {
    "wall_px": "[2,7]", "wall_style": "single|double (p=.55/.45)",
    "stroke_px": "[1,4]", "door_w_scale": "[0.8,1.35]",
    "swing_double_p": 0.5, "swing_into_larger_p": 0.7, "hinge_side": "per-door 0/1",
    "jambs_p": 0.5, "hatch_p": 0.4, "hatch_spacing": "[4,8]",
    "draw_text_p": 0.6, "rot90": "{0,1,2,3}",
}


def _sample_door_style(rng) -> dict:
    """Sample a per-plan render style for door-detector domain randomization (D-016)."""
    return {
        "wall_px": int(rng.integers(2, 8)),
        "wall_style": "double" if rng.random() < 0.45 else "single",
        "stroke_px": int(rng.integers(1, 5)),
        "door_w_scale": float(rng.uniform(0.8, 1.35)),
        "swing_double_p": 0.5,
        "swing_into": "larger" if rng.random() < 0.7 else "smaller",
        "jambs": bool(rng.random() < 0.5),
        "hatch": bool(rng.random() < 0.4),
        "hatch_spacing": int(rng.integers(4, 9)),
        "draw_text": bool(rng.random() < 0.6),
        "rot90": int(rng.integers(0, 4)),
    }


def _unit(dx, dy):
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-9 else (0.0, 0.0)


def _leaf_points(hinge, wall_dir, swing_unit, leaf_len):
    """World-coord points of one door leaf: swing arc (13 samples) + open leaf line.

    Returns (polylines, all_points). polylines is a list of point-lists to stroke;
    all_points is every vertex (for the exact bbox).
    """
    hx, hy = hinge
    closed = (hx + wall_dir[0] * leaf_len, hy + wall_dir[1] * leaf_len)
    openp = (hx + swing_unit[0] * leaf_len, hy + swing_unit[1] * leaf_len)
    a0 = math.atan2(closed[1] - hy, closed[0] - hx)
    a1 = math.atan2(openp[1] - hy, openp[0] - hx)
    d = a1 - a0
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    arc = [(hx + leaf_len * math.cos(a0 + d * t / 12.0),
            hy + leaf_len * math.sin(a0 + d * t / 12.0)) for t in range(13)]
    polylines = [arc, [hinge, openp]]
    return polylines, arc + [hinge, openp, closed]


def _draw_door_symbol(draw, to_px, opening, wall_unit, swing_unit, door_w, style, rng):
    """Draw a door symbol at `opening` and return its EXACT pixel bbox [x1,y1,x2,y2].

    wall_unit is the unit vector along the wall (perpendicular to swing_unit); the two
    jambs are opening +/- wall_unit*door_w/2. Randomizes single/double swing, hinge
    side, and optional frame jambs. Stroke width from style['stroke_px'].
    """
    ox, oy = opening
    jambA = (ox - wall_unit[0] * door_w / 2.0, oy - wall_unit[1] * door_w / 2.0)
    jambB = (ox + wall_unit[0] * door_w / 2.0, oy + wall_unit[1] * door_w / 2.0)
    stroke = style["stroke_px"]
    double = rng.random() < style.get("swing_double_p", 0.5)
    pts_world = []
    polylines = []
    if double:
        half = door_w / 2.0
        p1, a1 = _leaf_points(jambA, wall_unit, swing_unit, half)
        p2, a2 = _leaf_points(jambB, (-wall_unit[0], -wall_unit[1]), swing_unit, half)
        polylines += p1 + p2
        pts_world += a1 + a2
    else:
        hinge_side = int(rng.integers(0, 2))
        hinge = jambA if hinge_side == 0 else jambB
        wdir = wall_unit if hinge_side == 0 else (-wall_unit[0], -wall_unit[1])
        pl, ap = _leaf_points(hinge, wdir, swing_unit, door_w)
        polylines += pl
        pts_world += ap
    if style.get("jambs"):
        jl = door_w * 0.28  # frame tick half-length, across the wall
        for jx, jy in (jambA, jambB):
            t0 = (jx - swing_unit[0] * jl, jy - swing_unit[1] * jl)
            t1 = (jx + swing_unit[0] * jl, jy + swing_unit[1] * jl)
            polylines.append([t0, t1])
            pts_world += [t0, t1]
    for pl in polylines:
        draw.line([to_px(*p) for p in pl], fill=0, width=stroke, joint="curve")
    xs = [to_px(*p)[0] for p in pts_world]
    ys = [to_px(*p)[1] for p in pts_world]
    pad = stroke + 2
    return [int(min(xs) - pad), int(min(ys) - pad), int(max(xs) + pad), int(max(ys) + pad)]


def _draw_walls_styled(draw, rooms, to_px, style):
    """Stroke room-polygon boundaries; single thick line or offset double line."""
    wpx = style["wall_px"]
    for r in rooms:
        ring = [to_px(x, y) for x, y in r["poly"]]
        ring_closed = ring + [ring[0]]
        if style["wall_style"] == "double":
            off = max(1.5, wpx * 0.9)
            for sgn in (+1, -1):
                shifted = []
                n = len(ring_closed)
                for i in range(n):
                    x0, y0 = ring_closed[i]
                    x1, y1 = ring_closed[(i + 1) % n]
                    nx, ny = _unit(-(y1 - y0), (x1 - x0))
                    shifted.append((x0 + sgn * nx * off, y0 + sgn * ny * off))
                shifted.append(shifted[0])
                draw.line(shifted, fill=0, width=max(1, wpx // 2), joint="curve")
        else:
            draw.line(ring_closed, fill=0, width=wpx, joint="curve")


def _apply_hatch(img, rooms, to_px, style):
    """Overlay diagonal hatch lines within a dilated wall band (numpy compositing)."""
    from PIL import ImageDraw as _ID
    w, h = img.size
    band = max(4, style["wall_px"] + 3)
    mask = Image.new("L", (w, h), 0)
    md = _ID.Draw(mask)
    for r in rooms:
        ring = [to_px(x, y) for x, y in r["poly"]]
        md.line(ring + [ring[0]], fill=255, width=band, joint="curve")
    hatch = Image.new("L", (w, h), 255)
    hd = _ID.Draw(hatch)
    sp = style["hatch_spacing"]
    for c in range(-h, w, sp):  # 45-degree diagonals
        hd.line([(c, 0), (c + h, h)], fill=0, width=1)
    a_img = np.asarray(img).copy()
    m = (np.asarray(mask) > 0) & (np.asarray(hatch) == 0)
    a_img[m] = 0
    return Image.fromarray(a_img, mode="L")


def _rot90_image_boxes(img, boxes, k):
    """Rotate an 'L' image by k*90 deg CCW (lossless) and remap axis-aligned boxes.

    np.rot90(arr, k) rotates CCW. For k=1 on a (H,W) image, pixel (x,y) [x=col, y=row]
    maps to (x', y') = (y, W-1-x). Compose for k>1. Verified by the ink-coverage self
    check in gen_door_trainset (boxes must still bound drawn ink after rotation).
    """
    k %= 4
    if k == 0:
        return img, boxes
    arr = np.asarray(img)
    W = arr.shape[1]
    H = arr.shape[0]
    out = Image.fromarray(np.rot90(arr, k), mode="L")
    def remap(b, w, h):
        x1, y1, x2, y2 = b
        # single CCW step on a w x h image -> (x,y) -> (y, w-1-x)
        nx1, ny1 = y1, w - 1 - x1
        nx2, ny2 = y2, w - 1 - x2
        return [min(nx1, nx2), min(ny1, ny2), max(nx1, nx2), max(ny1, ny2)]
    w, h = W, H
    for _ in range(k):
        boxes = [remap(b, w, h) for b in boxes]
        w, h = h, w
    return out, boxes


def render_plan_annotated(graph, native_id, rng, style=None, pad_px=24):
    """Render one MSD plan with domain randomization and return (img, boxes, meta).

    boxes are exact pixel door bboxes [x1,y1,x2,y2]; meta carries the sampled style,
    the world->px transform, and counts. Emits door bboxes AT RENDER TIME (D-016).
    """
    if style is None:
        style = _sample_door_style(rng)

    rooms = []
    for _key, att in graph.nodes(data=True):
        rt = att.get("room_type")
        geom = att.get("geometry")
        if rt is None or not geom or len(geom) < 3:
            continue
        cen = att.get("centroid")
        name = ROOM_NAMES[int(rt)] if int(rt) < len(ROOM_NAMES) else str(rt)
        rooms.append({
            "name": name, "text": LABEL_REMAP.get(name, name.lower()),
            "poly": np.asarray(geom, dtype=float),
            "centroid": (float(cen[0]), float(cen[1])) if cen is not None else None,
        })
    if not rooms:
        raise ValueError(f"{native_id}: no renderable rooms")

    allpts = np.concatenate([r["poly"] for r in rooms])
    minx, miny = allpts.min(axis=0)
    maxx, maxy = allpts.max(axis=0)
    extent = max(maxx - minx, maxy - miny) or 1.0
    ppm = float(np.clip(1400.0 / extent, 30.0, 60.0))

    def to_px(x, y):
        return ((x - minx) * ppm + pad_px, (maxy - y) * ppm + pad_px)

    w = int((maxx - minx) * ppm) + 2 * pad_px
    h = int((maxy - miny) * ppm) + 2 * pad_px
    img = Image.new("L", (w, h), color=255)
    draw = ImageDraw.Draw(img)

    _draw_walls_styled(draw, rooms, to_px, style)
    if style["hatch"]:
        img = _apply_hatch(img, rooms, to_px, style)
        draw = ImageDraw.Draw(img)

    from shapely.geometry import Polygon
    from shapely.ops import nearest_points

    key_to_poly, key_to_area, key_to_cxy = {}, {}, {}
    for key, att in graph.nodes(data=True):
        g = att.get("geometry")
        if g and len(g) >= 3:
            try:
                poly = Polygon(g)
            except Exception:
                continue
            key_to_poly[key] = poly
            key_to_area[key] = poly.area
            key_to_cxy[key] = (poly.centroid.x, poly.centroid.y)

    boxes = []
    for u, v, att in graph.edges(data=True):
        gap_m = ACCESS_GAP_M.get(att.get("connectivity"))
        if gap_m is None or u not in key_to_poly or v not in key_to_poly:
            continue
        try:
            p1, p2 = nearest_points(key_to_poly[u], key_to_poly[v])
        except Exception:
            continue
        ox, oy = (p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0
        door_w = 2.0 * gap_m * style["door_w_scale"]
        # swing toward the chosen room; opening (world) -> swing unit + wall unit
        if style["swing_into"] == "larger":
            target = v if key_to_area[v] >= key_to_area[u] else u
        else:
            target = u if key_to_area[v] >= key_to_area[u] else v
        tcx, tcy = key_to_cxy[target]
        swing_unit = _unit(tcx - ox, tcy - oy)
        if swing_unit == (0.0, 0.0):
            continue
        wall_unit = (-swing_unit[1], swing_unit[0])
        rpx = (door_w / 2.0) * ppm
        cx, cy = to_px(ox, oy)
        draw.ellipse([cx - rpx, cy - rpx, cx + rpx, cy + rpx], fill=255)  # punch opening
        bbox = _draw_door_symbol(draw, to_px, (ox, oy), wall_unit, swing_unit, door_w, style, rng)
        # clamp into image
        bbox = [max(0, min(bbox[0], w - 1)), max(0, min(bbox[1], h - 1)),
                max(0, min(bbox[2], w - 1)), max(0, min(bbox[3], h - 1))]
        if bbox[2] - bbox[0] >= 2 and bbox[3] - bbox[1] >= 2:
            boxes.append(bbox)

    if style["draw_text"]:
        font = _font(14)
        for r in rooms:
            if r["centroid"] is None:
                continue
            tx, ty = to_px(*r["centroid"])
            draw.text((tx, ty), r["text"], fill=0, font=font, anchor="mm")

    if style["rot90"]:
        img, boxes = _rot90_image_boxes(img, boxes, style["rot90"])

    meta = {
        "native_id": native_id, "n_rooms": len(rooms), "n_doors": len(boxes),
        "px_per_m": round(ppm, 1), "size": list(img.size), "style": style,
    }
    return img, boxes, meta


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Render MSD plans to Tesseract-ready rasters (D-014).")
    ap.add_argument("-n", "--count", type=int, default=20)
    ap.add_argument("--door-style", choices=["arc", "gap", "none"], default="arc")
    ap.add_argument("--ids", nargs="*", help="explicit plan ids to render (overrides --count)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--no-contact", action="store_true", help="skip the contact sheet (batch use)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.ids:
        pickles = [RAW / f"{i}.pickle" for i in args.ids]
    else:
        pickles = sorted(RAW.glob("*.pickle"), key=lambda p: (len(p.stem), p.stem))[: args.count]

    stats_all, thumbs = [], []
    for pk in pickles:
        try:
            g = pickle.load(open(pk, "rb"))
            img, st = render_plan(g, pk.stem, door_style=args.door_style)
        except Exception as e:  # noqa: BLE001 - prototype: log + continue
            print(f"  SKIP {pk.stem}: {type(e).__name__}: {e}")
            continue
        img.save(out / f"{pk.stem}.png")
        stats_all.append(st)
        thumbs.append((pk.stem, img, st))
        print(f"  {pk.stem}: {st['n_rooms']} rooms, {st['n_gaps']} gaps, "
              f"{st['n_arcs']} arcs, {st['px_per_m']} px/m, {st['size']}")

    if not args.no_contact and thumbs:
        _contact_sheet(thumbs[:40], out / "contact_sheet.png")
    import json

    (out / "render_report.json").write_text(json.dumps(stats_all, indent=2))
    print(f"\nrendered {len(stats_all)} plans (door_style={args.door_style}) -> {out}")
    return 0 if stats_all else 1


def _contact_sheet(thumbs, path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(thumbs)
    cols = 5
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2.6, rows * 2.6))
    for ax in np.asarray(axes).ravel():
        ax.axis("off")
    for ax, (stem, img, st) in zip(np.asarray(axes).ravel(), thumbs, strict=False):
        ax.imshow(np.asarray(img), cmap="gray", vmin=0, vmax=255)
        ax.set_title(f"{stem}: {st['n_rooms']}r/{st['n_gaps']}g", fontsize=7)
    fig.suptitle("MSD render lane (D-014): walls + approx door gaps + room-type text", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
