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
