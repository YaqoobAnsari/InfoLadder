"""Batch-ingest data/raw/prelim_rasters through the raster->R0 lane (ROADMAP DATA-0).

Run on the cluster (scripts/slurm/ingest_rasters.sbatch), NOT the login node.

Outputs (data/derived/prelim_rasters/):
  <stem>.r0.json          validated SpectrumGraph R0
  <stem>.rooms.npz        room-index grid + wall mask (feeds labels/pde.py)
  <stem>.ypde.json        per-room PDE means + ranks (preliminary Y_pde)
  overlays/<stem>.png     QA overlay figure (rooms + graph on the source raster)
  ingest_report.json      per-file stats, skips, failures
Also refreshes results/reports/data0_raster_prototype/report.md (tracked).

Dedup rule (data/raw/prelim_rasters/README.md): for sheets with `up`/`upE`
variants keep ONE per sheet, preferring `upE` > `up` > plain (latest text pass).
Non-floorplan images (white_background, t*.png) are skipped explicitly.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from topospec.data.raster import extract_rooms, overlay_figure, pde_inputs
from topospec.graphs.serializers.json_io import save_graph
from topospec.graphs.validate import SchemaError, validate_graph
from topospec.labels.pde import solve_masked_poisson

RAW = Path("data/raw/prelim_rasters")
OUT = Path("data/derived/prelim_rasters")
REPORT_DIR = Path("results/reports/data0_raster_prototype")

SKIP = {"white_background.png", "t1.png", "t2.png", "t3.png"}

# extraction parameters per image family (split radius auto-tunes; documented
# in the report). min_room_px calibrated on FF part 1 (~39 px/m: 2000 px ~ 1.3 m^2)
PARAMS_LARGE = dict(min_room_px=2000)
PARAMS_SMALL = dict(min_room_px=300)


def dedupe(files: list[Path]) -> tuple[list[Path], list[str]]:
    """One variant per sheet: prefer upE > up > plain."""
    rank = {"upE": 2, "up": 1, "": 0}
    groups: dict[str, list[tuple[int, Path]]] = {}
    for f in files:
        m = re.match(r"^(.*?)(upE|up)?$", f.stem)
        base, suffix = m.group(1).strip(), m.group(2) or ""
        groups.setdefault(base, []).append((rank[suffix], f))
    kept, dropped = [], []
    for _base, variants in sorted(groups.items()):
        variants.sort(reverse=True)
        kept.append(variants[0][1])
        dropped += [str(v[1].name) for v in variants[1:]]
    return kept, dropped


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "overlays").mkdir(exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    all_pngs = sorted(p for p in RAW.glob("*.png") if p.name not in SKIP)
    kept, dropped = dedupe(all_pngs)
    report: dict = {"kept": [k.name for k in kept], "dropped_variants": dropped,
                    "skipped_non_floorplan": sorted(SKIP), "files": {}}

    for path in kept:
        stem = path.stem.replace(" ", "_")
        # convert('RGB'): palette-mode PNGs (the file_N set) otherwise yield
        # palette INDICES, which read as all-ink
        img = np.asarray(Image.open(path).convert("RGB"))
        large = img.shape[0] * img.shape[1] > 500_000
        params = PARAMS_LARGE if large else PARAMS_SMALL
        entry: dict = {"params": params, "shape": list(img.shape)}
        try:
            ex = extract_rooms(img, building_id=f"prelim:{stem}", **params)
            validate_graph(ex.graph)
            save_graph(ex.graph, OUT / f"{stem}.r0.json")
            np.savez_compressed(
                OUT / f"{stem}.rooms.npz",
                room_ix=ex.room_ix, wall_mask=ex.wall_mask,
                room_ids=np.array(ex.room_ids),
            )
            overlay_figure(img, ex, OUT / "overlays" / f"{stem}.png")

            interior, room_ix, tr = pde_inputs(ex)
            u = solve_masked_poisson(interior, np.zeros(interior.shape), source=1.0)
            means = {
                rid: float(u[(room_ix == k) & interior].mean())
                for k, rid in enumerate(tr["room_ids"])
            }
            ranks = {
                rid: int(r)
                for r, rid in enumerate(sorted(means, key=means.get))
            }
            (OUT / f"{stem}.ypde.json").write_text(
                json.dumps({"means": means, "ranks": ranks}, indent=1)
            )
            entry.update(status="ok", **ex.stats)
        except (SchemaError, ValueError, MemoryError) as exc:
            entry.update(status="failed", error=str(exc)[:500])
        report["files"][path.name] = entry
        print(f"{entry['status']:>6}  {path.name}: "
              f"{entry.get('n_rooms', '-')} rooms, "
              f"{entry.get('n_edges_opening', '-')} edges")

    (OUT / "ingest_report.json").write_text(json.dumps(report, indent=1))
    _write_report_md(report)
    n_fail = sum(1 for e in report["files"].values() if e["status"] != "ok")
    print(f"\ndone: {len(report['files']) - n_fail} ok, {n_fail} failed; "
          f"outputs in {OUT}")
    return 1 if n_fail == len(report["files"]) else 0


def _write_report_md(report: dict) -> None:
    lines = [
        "# DATA-0 prototype — prelim raster ingest report",
        "",
        "Generated by scripts/ingest_prelim_rasters.py (rerun to refresh).",
        "QA overlays: `data/derived/prelim_rasters/overlays/` — INSPECT THESE;",
        "segmentation quality on real sheets is the acceptance evidence for DATA-0.",
        "",
        f"- kept {len(report['kept'])} images "
        f"(dropped {len(report['dropped_variants'])} duplicate text-variants, "
        f"skipped {len(report['skipped_non_floorplan'])} non-floorplans)",
        "",
        "| file | status | rooms | opening edges | wall-only adj |",
        "|---|---|---|---|---|",
    ]
    for name, e in sorted(report["files"].items()):
        lines.append(
            f"| {name} | {e['status']} | {e.get('n_rooms', '-')} | "
            f"{e.get('n_edges_opening', '-')} | {e.get('n_adjacent_wall_only', '-')} |"
        )
    lines += [
        "",
        "Caveats: R0 only (no door/corridor semantics yet); stairs/elevators appear "
        "as rooms; FF sheets are per-sheet graphs, not yet stitched into one "
        "building; PDE labels here are PRELIMINARY (pixel-resolution, no "
        "convergence check).",
    ]
    (REPORT_DIR / "report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
