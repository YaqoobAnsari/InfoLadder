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
ACCESS_GAP_M = {"door": 0.5, "entrance": 0.6, "passage": 0.7}  # opening half-width (m)
RAW = Path("data/raw/msd/graph_out")
OUT = Path("data/derived/msd_render")


def _font(size: int) -> ImageFont.FreeTypeFont:
    from matplotlib import font_manager

    return ImageFont.truetype(font_manager.findfont("DejaVu Sans"), size)


def render_plan(graph, native_id: str, wall_px: int = 3, pad_px: int = 24) -> tuple[Image.Image, dict]:
    """Render one MSD networkx plan to a clean raster. Returns (image, stats)."""
    rooms = []
    for _key, att in graph.nodes(data=True):
        rt = att.get("room_type")
        geom = att.get("geometry")
        if rt is None or not geom or len(geom) < 3:
            continue
        cen = att.get("centroid")
        rooms.append(
            {
                "name": ROOM_NAMES[int(rt)] if int(rt) < len(ROOM_NAMES) else str(rt),
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

    # approximate door/opening gaps at access edges (needs shapely)
    n_gaps = 0
    try:
        from shapely.geometry import Polygon
        from shapely.ops import nearest_points

        key_to_poly = {}
        for key, att in graph.nodes(data=True):
            g = att.get("geometry")
            if g and len(g) >= 3:
                try:
                    key_to_poly[key] = Polygon(g)
                except Exception:
                    pass
        for u, v, att in graph.edges(data=True):
            conn = att.get("connectivity")
            gap_m = ACCESS_GAP_M.get(conn)
            if gap_m is None or u not in key_to_poly or v not in key_to_poly:
                continue
            try:
                p1, p2 = nearest_points(key_to_poly[u], key_to_poly[v])
            except Exception:
                continue
            gx, gy = (p1.x + p2.x) / 2.0, (p1.y + p2.y) / 2.0
            cx, cy = to_px(gx, gy)
            rpx = gap_m * ppm
            draw.ellipse([cx - rpx, cy - rpx, cx + rpx, cy + rpx], fill=255)  # punch opening
            n_gaps += 1
    except ImportError:
        pass

    # room-type text labels at centroids (CRAFT reads these)
    font = _font(14)
    for r in rooms:
        if r["centroid"] is None:
            continue
        cx, cy = to_px(*r["centroid"])
        draw.text((cx, cy), r["name"], fill=0, font=font, anchor="mm")

    stats = {"native_id": native_id, "n_rooms": len(rooms), "n_gaps": n_gaps,
             "px_per_m": round(ppm, 1), "size": [w, h]}
    return img, stats


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    pickles = sorted(RAW.glob("*.pickle"), key=lambda p: (len(p.stem), p.stem))[:n]
    stats_all, thumbs = [], []
    for pk in pickles:
        try:
            g = pickle.load(open(pk, "rb"))
            img, st = render_plan(g, pk.stem)
        except Exception as e:  # noqa: BLE001 - prototype: log + continue
            print(f"  SKIP {pk.stem}: {type(e).__name__}: {e}")
            continue
        img.save(OUT / f"{pk.stem}.png")
        stats_all.append(st)
        thumbs.append((pk.stem, img, st))
        print(f"  {pk.stem}: {st['n_rooms']} rooms, {st['n_gaps']} gaps, {st['px_per_m']} px/m, {st['size']}")

    _contact_sheet(thumbs, OUT / "contact_sheet.png")
    import json

    (OUT / "render_report.json").write_text(json.dumps(stats_all, indent=2))
    print(f"\nrendered {len(stats_all)} plans -> {OUT} (+ contact_sheet.png)")
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
