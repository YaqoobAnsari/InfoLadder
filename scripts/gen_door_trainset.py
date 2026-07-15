"""Generate a door-detector fine-tuning set from MSD plans (D-016).

For each selected MSD `graph_out` plan we sample a randomized render style and call
`render_msd_rasters.render_plan_annotated`, which draws the plan and returns the EXACT
pixel bbox of every door symbol (the arcs are generated analytically, so boxes are not
estimated). We store the full annotated render + its boxes; the trainer
(`train_door_rcnn.py`) samples 300 px crops on the fly to match Tesseract's
`detect_doors` chunk regime (chunk_size=300), so doors are seen at the same pixel scale
at train and inference time.

Outputs (under --out, default data/derived/msd_door_train/):
  images/<id>.png        full annotated render (grayscale)
  annotations.json       {"images":[{native_id,file,width,height,boxes,style}], "meta":{}}
  split.json             plan-level train/val split (>=--val-frac held out), hashed
  sample_crops.png       inspection figure: door crops with boxes overlaid
  gen_report.json        counts, per-style tallies, ink-coverage self-check

Self-check: every stored box must bound drawn ink (a door symbol). We report the
fraction of boxes whose crop contains dark pixels; a low fraction would reveal a bbox
bug (e.g. a bad rotation remap). Seeds: per-plan rng = default_rng(seed + plan_index).

CPU only; a few-plan smoke is login-node-safe (seconds). The full few-hundred-plan
run goes through slurm (scripts/slurm/gen_door_trainset.sbatch).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_msd_rasters as R  # noqa: E402

RAW = Path("data/raw/msd/graph_out")


def _box_has_ink(arr: np.ndarray, box, thr: int = 128, min_dark: int = 3) -> bool:
    x1, y1, x2, y2 = box
    crop = arr[y1:y2, x1:x2]
    if crop.size == 0:
        return False
    return int((crop < thr).sum()) >= min_dark


def _sample_crops_figure(items, out_path, n=24, crop_pad=40):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    picks = []  # (native_id, arr, box, style)
    for it in items:
        arr = np.asarray(__import__("PIL.Image", fromlist=["Image"]).open(it["_file"]))
        for b in it["boxes"]:
            picks.append((it["native_id"], arr, b, it["style"]))
    if not picks:
        return 0
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(picks))[:n]
    picks = [picks[i] for i in idx]
    cols = 6
    rows = (len(picks) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2.2, rows * 2.2))
    for ax in np.asarray(axes).ravel():
        ax.axis("off")
    for ax, (nid, arr, b, st) in zip(np.asarray(axes).ravel(), picks, strict=False):
        h, w = arr.shape[:2]
        x1, y1, x2, y2 = b
        cx0, cy0 = max(0, x1 - crop_pad), max(0, y1 - crop_pad)
        cx1, cy1 = min(w, x2 + crop_pad), min(h, y2 + crop_pad)
        ax.imshow(arr[cy0:cy1, cx0:cx1], cmap="gray", vmin=0, vmax=255)
        ax.add_patch(patches.Rectangle(
            (x1 - cx0, y1 - cy0), x2 - x1, y2 - y1,
            linewidth=1.4, edgecolor="red", facecolor="none"))
        tag = f"{nid} w{st['wall_px']}{st['wall_style'][0]} s{st['stroke_px']}"
        tag += "h" if st["hatch"] else ""
        tag += "j" if st["jambs"] else ""
        tag += f" r{st['rot90']}"
        ax.set_title(tag, fontsize=6)
    fig.suptitle("MSD door-train crops (D-016): exact bboxes over randomized styles", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return len(picks)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate MSD door-detector training set (D-016).")
    ap.add_argument("-n", "--count", type=int, default=300, help="number of plans")
    ap.add_argument("--seed", type=int, default=20260715)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--out", default="data/derived/msd_door_train")
    ap.add_argument("--ids", nargs="*", help="explicit plan ids (overrides --count)")
    args = ap.parse_args()

    from PIL import Image

    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)

    if args.ids:
        pickles = [RAW / f"{i}.pickle" for i in args.ids]
    else:
        pickles = sorted(RAW.glob("*.pickle"), key=lambda p: (len(p.stem), p.stem))[: args.count]

    items, skipped = [], []
    from collections import Counter
    style_tally = Counter()
    ink_ok = ink_tot = 0
    for idx, pk in enumerate(pickles):
        if not pk.exists():
            skipped.append({"id": pk.stem, "reason": "pickle missing"})
            continue
        rng = np.random.default_rng(args.seed + idx)
        try:
            g = pickle.load(open(pk, "rb"))
            img, boxes, meta = R.render_plan_annotated(g, pk.stem, rng)
        except Exception as e:  # noqa: BLE001 - log + continue, never guess geometry
            skipped.append({"id": pk.stem, "reason": f"{type(e).__name__}: {e}"})
            continue
        if not boxes:
            skipped.append({"id": pk.stem, "reason": "no doors rendered"})
            continue
        fpath = out / "images" / f"{pk.stem}.png"
        img.save(fpath)
        arr = np.asarray(img)
        for b in boxes:
            ink_tot += 1
            ink_ok += int(_box_has_ink(arr, b))
        st = meta["style"]
        for k in ("wall_style",):
            style_tally[f"wall_{st[k]}"] += 1
        style_tally["hatch"] += int(st["hatch"])
        style_tally["jambs"] += int(st["jambs"])
        style_tally["text"] += int(st["draw_text"])
        style_tally[f"rot{st['rot90']}"] += 1
        items.append({"native_id": pk.stem, "file": f"images/{pk.stem}.png",
                      "_file": str(fpath), "width": img.size[0], "height": img.size[1],
                      "boxes": boxes, "style": st})

    # plan-level split (>= val_frac held out), deterministic by seed
    rng = np.random.default_rng(args.seed)
    ids = [it["native_id"] for it in items]
    perm = rng.permutation(len(ids))
    n_val = max(1, int(round(len(ids) * args.val_frac)))
    val_ids = sorted(ids[i] for i in perm[:n_val])
    train_ids = sorted(ids[i] for i in perm[n_val:])
    split = {"seed": args.seed, "val_frac": args.val_frac,
             "n_train_plans": len(train_ids), "n_val_plans": len(val_ids),
             "train": train_ids, "val": val_ids}
    split["hash"] = hashlib.sha256(
        json.dumps([train_ids, val_ids], sort_keys=True).encode()).hexdigest()[:16]

    n_doors = sum(len(it["boxes"]) for it in items)
    n_val_doors = sum(len(it["boxes"]) for it in items if it["native_id"] in set(val_ids))
    ann = {"meta": {"builder": "gen_door_trainset.py", "seed": args.seed,
                    "n_plans": len(items), "n_doors": n_doors,
                    "style_ranges": R.DOOR_STYLE_RANGES,
                    "note": "boxes are exact render-time door bboxes; trainer crops 300px on the fly"},
           "images": [{k: it[k] for k in ("native_id", "file", "width", "height", "boxes", "style")}
                      for it in items]}
    (out / "annotations.json").write_text(json.dumps(ann, indent=2))
    (out / "split.json").write_text(json.dumps(split, indent=2))
    n_crops = _sample_crops_figure(items, out / "sample_crops.png")

    report = {
        "n_plans_rendered": len(items), "n_plans_skipped": len(skipped),
        "n_doors_total": n_doors, "n_doors_train": n_doors - n_val_doors, "n_doors_val": n_val_doors,
        "ink_coverage": round(ink_ok / ink_tot, 4) if ink_tot else 0.0,
        "ink_boxes_checked": ink_tot,
        "split": {k: split[k] for k in ("n_train_plans", "n_val_plans", "val_frac", "hash")},
        "style_tally": dict(style_tally),
        "sample_crops": n_crops,
        "skipped_examples": skipped[:12],
    }
    (out / "gen_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if ink_tot and ink_ok / ink_tot < 0.98:
        print(f"WARNING: ink coverage {ink_ok/ink_tot:.3f} < 0.98 — possible bbox bug", file=sys.stderr)
    return 0 if items else 1


if __name__ == "__main__":
    sys.exit(main())
