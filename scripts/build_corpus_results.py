"""Build the browsable corpus results tree (D-014; user-approved layout).

results/corpora/<dataset>/
    INDEX.md                      one row per building: tiers, stats, links
    <building>/
        source.png                the bare floorplan raster
        tiers/T0.json .. T3.json  validated tier graphs
        overlays/T0.png .. T3.png graph drawn over the floorplan, per tier
        report.md                 per-building card

Currently covers dataset 'prelim_rasters' (Tesseract2 batch outputs over the
user's annotated up/upE sheets). Rerun after every Tesseract batch:
    $TOPOSPEC_PYTHON scripts/build_corpus_results.py
(render is minutes of matplotlib work — run via srun/sbatch, not the login node)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from topospec.data.tesseract import TesseractGraphError, build_tiers
from topospec.reporting import style

ROOT = Path(__file__).resolve().parent.parent
TESS_RESULTS = Path("/data1/yansari/PhD/topofield/Tesseract2/Results/Json")
RAW = ROOT / "data" / "raw" / "prelim_rasters"
OUT = ROOT / "results" / "corpora" / "prelim_rasters"
BATCH_SBATCH = ROOT / "scripts" / "slurm" / "tesseract_batch.sbatch"


def fresh_batch_images() -> set[str]:
    """Images run by OUR batch job (source of truth: the sbatch images array).
    Everything else under Tesseract2/Results is a pre-existing checkout artifact
    produced by an older door-backbone version — usable, but marked as such."""
    import re

    text = BATCH_SBATCH.read_text()
    return {m.group(1)[:-4] for m in re.finditer(r'"([^"]+\.png)"', text)}

KIND_COLORS = {
    "room": style.FAMILY_COLORS["V2"],       # blue
    "corridor": style.FAMILY_COLORS["V4"],   # aqua
    "transition": style.FAMILY_COLORS["V3"],  # violet
    "door": style.FAMILY_COLORS["V5"],       # red
    None: "#555555",                          # T0 untyped
}


def overlay(g, img: np.ndarray, out_path: Path, tier: int) -> None:
    h, w = img.shape[:2]
    fig, ax = plt.subplots(figsize=(min(15, w / 130), min(15, h / 130)))
    ax.imshow(img, cmap="gray" if img.ndim == 2 else None)
    pos = {nid: n.centroid for nid, n in g.nodes.items() if n.centroid}
    for e in g.edges:
        if e.u in pos and e.v in pos:
            (x1, y1), (x2, y2) = pos[e.u], pos[e.v]
            ax.plot([x1, x2], [y1, y2], "-", color="#d62828", lw=1.4, alpha=0.85, zorder=2)
    for nid, n in g.nodes.items():
        if nid not in pos:
            continue
        x, y = pos[nid]
        if n.kind == "door":
            ax.plot(x, y, "s", color=KIND_COLORS["door"], ms=4.5, zorder=4)
        else:
            size = 7.0
            if tier >= 3 and n.area:
                size = float(np.clip(4 + np.sqrt(n.area) / 12, 5, 16))
            ax.plot(x, y, "o", color=KIND_COLORS.get(n.kind, "#555555"),
                    ms=size, zorder=3, markeredgecolor="white", markeredgewidth=0.6)
            if tier >= 1 and n.label:  # labels are T1+ content; render for QA
                ax.annotate(
                    n.label, (x, y), xytext=(0, 7), textcoords="offset points",
                    fontsize=6.5, color=KIND_COLORS.get(n.kind, "#333333"),
                    ha="center", zorder=5, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.12", fc="white",
                              ec="none", alpha=0.75),
                )
    n_doors = sum(1 for n in g.nodes.values() if n.kind == "door")
    ax.set_title(
        f"{g.building_id} — T{tier}: {len(g.nodes) - n_doors} spaces"
        + (f", {n_doors} doors" if tier >= 2 else "")
        + f", {len(g.edges)} edges",
        fontsize=11, color=style.TEXT_PRIMARY,
    )
    ax.axis("off")
    fig.savefig(out_path, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def building_report(bdir: Path, name: str, tiers: dict) -> None:
    lines = [
        f"# {name}",
        "",
        "| tier | spaces | doors | edges | labeled spaces |",
        "|---|---|---|---|---|",
    ]
    for lvl in (0, 1, 2, 3):
        g = tiers[lvl]
        doors = sum(1 for n in g.nodes.values() if n.kind == "door")
        labeled = sum(1 for n in g.nodes.values() if n.label and n.kind != "door")
        lines.append(
            f"| T{lvl} | {len(g.nodes) - doors} | {doors if lvl >= 2 else '—'} | "
            f"{len(g.edges)} | {labeled if lvl >= 1 else '—'} |"
        )
    lines += ["", "## Source", "", "![source](source.png)", ""]
    for lvl in (0, 1, 2, 3):
        lines += [f"## T{lvl}", "", f"![T{lvl}](overlays/T{lvl}.png)", ""]
    lines += [
        "Tier JSONs: `tiers/T0.json` … `tiers/T3.json` (schema v2, validated).",
        "T4/T5 (direction, zones) await the manual annotation stage-gate (D-014).",
    ]
    (bdir / "report.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fresh = fresh_batch_images()
    rows = []
    exports = sorted(TESS_RESULTS.glob("*/*_pre_pruning.json"))
    for export in exports:
        image_name = export.parent.name  # e.g. "FF part 1upE"
        src_png = RAW / f"{image_name}.png"
        if not src_png.exists():
            continue  # only the project's own pool
        provenance = (
            "fresh (batch 7215)" if image_name in fresh
            else "pre-existing pipeline artifact (older weights) — rerun pending"
        )
        bname = image_name.replace(" ", "_")
        bdir = OUT / bname
        (bdir / "tiers").mkdir(parents=True, exist_ok=True)
        (bdir / "overlays").mkdir(exist_ok=True)
        try:
            tiers = build_tiers(export, building_id=f"prelim:{bname}")
        except TesseractGraphError as exc:
            rows.append((bname, f"FAILED: {str(exc)[:80]}", "—"))
            continue
        shutil.copy(src_png, bdir / "source.png")
        img = np.asarray(Image.open(src_png).convert("RGB"))
        from topospec.graphs.serializers.json_io import save_graph

        for lvl, g in sorted(tiers.items()):
            save_graph(g, bdir / "tiers" / f"T{lvl}.json")
            overlay(g, img, bdir / "overlays" / f"T{lvl}.png", lvl)
        building_report(bdir, bname, tiers)
        (bdir / "PROVENANCE.txt").write_text(provenance + f"\nsource: {export}\n")
        g3 = tiers[3]
        doors = sum(1 for n in g3.nodes.values() if n.kind == "door")
        rows.append(
            (bname,
             f"{len(g3.nodes) - doors} spaces · {doors} doors · {len(g3.edges)} edges",
             provenance)
        )
        print(f"built {bname}")

    lines = [
        "# prelim_rasters — corpus index",
        "",
        "Tiers T0–T3 derived from the user's annotated sheets via the Tesseract2",
        "pipeline (D-014). Every building folder holds the bare floorplan, the four",
        "tier JSONs, per-tier graph overlays, and a report card.",
        "",
        "| building | T3 summary | provenance | report |",
        "|---|---|---|---|",
    ]
    for bname, summary, provenance in rows:
        lines.append(
            f"| {bname} | {summary} | {provenance} | [report]({bname}/report.md) |"
        )
    lines += ["", "_Regenerate: `scripts/build_corpus_results.py` (after each Tesseract batch)._"]
    (OUT / "INDEX.md").write_text("\n".join(lines) + "\n")
    print(f"\nINDEX: {OUT / 'INDEX.md'} ({len(rows)} buildings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
