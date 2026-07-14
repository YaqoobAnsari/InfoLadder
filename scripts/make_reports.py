"""Regenerate all phase reports under results/reports/ from run artifacts.

Usage:  $TOPOSPEC_PYTHON scripts/make_reports.py
Idempotent; safe to run after every completed job. Reports are TRACKED (committed)
so results are followable in writing and visually (CLAUDE.md mission priority 3).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from topospec.reporting.calibration import make_report as calibration_report

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
REPORTS = ROOT / "results" / "reports"


def latest_calibration_run() -> Path | None:
    """Newest completed calibration run; prefer non-smoke over smoke."""
    candidates = []
    for mpath in RUNS.glob("*/manifest.json"):
        m = json.loads(mpath.read_text())
        if m.get("experiment") == "calibration_a0" and m.get("status") == "completed":
            candidates.append((not m.get("smoke", False), m["started_utc"], mpath.parent))
    if not candidates:
        return None
    return sorted(candidates)[-1][2]


def data0_report() -> None:
    """Raster-ingest visual report: stats table + embedded QA overlays."""
    derived = ROOT / "data" / "derived" / "prelim_rasters"
    rep_path = derived / "ingest_report.json"
    if not rep_path.exists():
        print("data0: no ingest_report.json yet — skipped")
        return
    report = json.loads(rep_path.read_text())
    out = REPORTS / "data0_raster_prototype"
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    ok = {n: e for n, e in report["files"].items() if e["status"] == "ok"}
    failed = {n: e for n, e in report["files"].items() if e["status"] != "ok"}

    # embed up to 6 representative overlays: largest sheets + one small plan
    ranked = sorted(ok, key=lambda n: -ok[n].get("n_rooms", 0))
    picks = ranked[:4] + [n for n in ranked[4:] if n.startswith("file_")][:2]
    embedded = []
    for name in picks:
        stem = Path(name).stem.replace(" ", "_")
        src = derived / "overlays" / f"{stem}.png"
        if src.exists():
            shutil.copy(src, figs / f"{stem}.png")
            embedded.append((name, f"figures/{stem}.png"))

    lines = [
        "# DATA-0 — raster→graph ingest report (prelim pool)",
        "",
        "Every user-supplied floorplan raster is segmented into rooms (hierarchical",
        "multi-scale marker watershed on the free-space distance transform), turned",
        "into a validated R0 connectivity graph, and given preliminary PDE heat",
        "labels. QA overlays below show segmentation + graph over the source sheet.",
        "",
        f"**{len(ok)} ingested OK · {len(failed)} failed** · "
        f"{len(report['dropped_variants'])} duplicate text-variants deduped · "
        f"{len(report['skipped_non_floorplan'])} non-floorplans skipped",
        "",
        "| file | status | rooms | opening edges | wall-only adj | auto split px |",
        "|---|---|---|---|---|---|",
    ]
    for name, e in sorted(report["files"].items()):
        lines.append(
            f"| {name} | {e['status']} | {e.get('n_rooms', '—')} | "
            f"{e.get('n_edges_opening', '—')} | {e.get('n_adjacent_wall_only', '—')} | "
            f"{e.get('split_erosion_px_used', '—')} |"
        )
    if failed:
        lines += ["", "## Failures", ""]
        for name, e in sorted(failed.items()):
            lines.append(f"- `{name}`: {e.get('error', '?')[:200]}")
    lines += ["", "## QA overlays (representative)", ""]
    for name, rel in embedded:
        lines += [f"### {name}", "", f"![{name}]({rel})", ""]
    lines += [
        "All overlays: `data/derived/prelim_rasters/overlays/` (not tracked).",
        "",
        "Known limitations (documented in `topospec/data/raster.py`): R0 only —",
        "door/corridor semantics come from the CAD-vector lane or annotation;",
        "stairs/elevators segment as rooms; exterior courtyards can read as",
        "interior on open-site sheets; FF sheets are per-sheet graphs (stitching",
        "into ONE building is part of Gate-b prep). PDE labels are pixel-resolution",
        "preliminaries (no convergence check yet — ROADMAP A-1).",
        "",
        "**⚠ file_N residential renders — pipeline smoke tests ONLY, not",
        "measurement data.** Their furniture is drawn with wall-thickness strokes,",
        "so pure morphology over-segments (e.g. file_1: ~40 regions for a 4-room",
        "flat; A/B sweeps of the wall filter either keep furniture or destroy",
        "walls). The institutional FF/LF/SF sheets do NOT have this problem (thin",
        "furniture strokes) and extract cleanly. Real residential corpora arrive",
        "with vector annotations (Structured3D/CubiCasa/MSD — no extraction), and",
        "the FloorPlanCAD lane rasterizes wall primitives only, so this limitation",
        "is confined to these test images.",
        "",
        "_Regenerate with `scripts/make_reports.py`._",
    ]
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print(f"data0: report written -> {out / 'report.md'} ({len(embedded)} overlays embedded)")


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    run = latest_calibration_run()
    if run is not None:
        path = calibration_report(run, REPORTS / "a0_calibration")
        print(f"a0_calibration: report written -> {path} (from {run.name})")
    else:
        print("a0_calibration: no completed run found — skipped")
    # data0_report() retired: superseded by results/corpora (D-014;
    # scripts/build_corpus_results.py)


if __name__ == "__main__":
    main()
