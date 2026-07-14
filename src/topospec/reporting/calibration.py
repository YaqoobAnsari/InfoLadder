"""Phase A0 calibration report: registry cells -> report.md + figures (A0-3).

Figure 1 — the calibration surface: small multiples per planted target, I_V (nats)
vs level, one line per probe family (fixed identity colors), seed-mean with
per-seed dots. The instrument PASSes if each curve jumps exactly at its target's
planted saturation level (dashed vertical marker).

Figure 2 — control panel: shuffled-label targets; everything must sit below the
one-sided tolerance line (positive extraction = leakage; negative = harmless
overfit noise).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from topospec.data.synthetic import PLANTED_SATURATION_LEVEL
from topospec.reporting import style


def load_cells(run_dir: Path) -> list[dict]:
    cells = []
    for f in sorted((run_dir / "cells").glob("*.json")):
        cells.append(json.loads(f.read_text()))
    return cells


def _mean_iv(cells, target, level, family):
    vals = [
        c["i_v"]
        for c in cells
        if c["target"] == target and c["level"] == level and c["family"] == family
        and c.get("cell_status", "ok") == "ok"
    ]
    return (float(np.mean(vals)), [float(v) for v in vals]) if vals else (None, [])


def surface_figure(cells: list[dict], out_path: Path) -> None:
    targets = sorted(
        {c["target"] for c in cells if not c["target"].endswith("_ctrl")},
        key=lambda t: PLANTED_SATURATION_LEVEL.get(t, 99),
    )
    levels = sorted({c["level"] for c in cells})
    families = [f for f in style.FAMILY_ORDER if any(c["family"] == f for c in cells)]

    ncols = min(4, max(1, len(targets)))
    nrows = int(np.ceil(len(targets) / ncols))
    fig, axes = style.new_figure(nrows, ncols)
    for i, target in enumerate(targets):
        ax = axes[i // ncols][i % ncols]
        style.apply(ax)
        ax.axhline(0, color=style.GRID, linewidth=1.2, zorder=1)
        for fam in families:
            xs, ys = [], []
            for lv in levels:
                mean, seeds = _mean_iv(cells, target, lv, fam)
                if mean is None:
                    continue
                xs.append(lv)
                ys.append(mean)
                ax.scatter(
                    [lv] * len(seeds), seeds, s=9,
                    color=style.FAMILY_COLORS[fam], alpha=0.45, zorder=2,
                    linewidths=0,
                )
            if xs:
                ax.plot(
                    xs, ys, "-o", color=style.FAMILY_COLORS[fam], linewidth=2,
                    markersize=4, label=fam, zorder=3,
                )
        # planted-level marker AFTER plotting, so autoscaled limits are final
        sat = PLANTED_SATURATION_LEVEL.get(target)
        if sat is not None and sat in levels:
            ax.axvline(
                sat, color=style.TEXT_MUTED, linewidth=1.0, linestyle="--", zorder=1
            )
            ax.text(
                sat, ax.get_ylim()[0], " planted→", fontsize=7.5,
                color=style.TEXT_MUTED, va="bottom", ha="left",
            )
        ax.set_title(target, fontsize=10)
        ax.set_xticks(levels)
        ax.set_xticklabels([f"T{lv}" for lv in levels])
        if i % ncols == 0:
            ax.set_ylabel("I_V (nats)")
    for j in range(len(targets), nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")
    # harvest legend entries across ALL panels (V0 may exist in only one)
    seen: dict[str, object] = {}
    for row in axes:
        for ax in row:
            for h, lbl in zip(*ax.get_legend_handles_labels(), strict=True):
                seen.setdefault(lbl, h)
    order = [f for f in style.FAMILY_ORDER if f in seen]
    fig.legend(
        [seen[f] for f in order], order, loc="lower center", ncol=len(order),
        frameon=False, bbox_to_anchor=(0.5, -0.02), fontsize=9,
        labelcolor=style.TEXT_SECONDARY,
    )
    fig.suptitle(
        "Phase A0 calibration surface — usable information vs representation level",
        color=style.TEXT_PRIMARY, fontsize=12, y=1.0,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=style.SURFACE)
    import matplotlib.pyplot as plt

    plt.close(fig)


def control_figure(cells: list[dict], ctrl_tol: float, out_path: Path) -> bool:
    ctrl_targets = sorted({c["target"] for c in cells if c["target"].endswith("_ctrl")})
    if not ctrl_targets:
        return False
    levels = sorted({c["level"] for c in cells})
    families = [
        f for f in style.FAMILY_ORDER
        if f != "V1" and any(c["family"] == f for c in cells)
    ]
    fig, axes = style.new_figure(1, len(ctrl_targets), cell=(3.8, 3.0))
    for i, target in enumerate(ctrl_targets):
        ax = axes[0][i]
        style.apply(ax)
        ax.axhline(0, color=style.GRID, linewidth=1.2, zorder=1)
        ax.axhline(
            ctrl_tol, color=style.TEXT_MUTED, linewidth=1.0, linestyle="--", zorder=2
        )
        ax.text(
            levels[0], ctrl_tol, f" tolerance {ctrl_tol:g} (one-sided)",
            fontsize=7.5, color=style.TEXT_MUTED, va="bottom",
        )
        for fam in families:
            xs, ys = [], []
            for lv in levels:
                mean, _ = _mean_iv(cells, target, lv, fam)
                if mean is not None:
                    xs.append(lv)
                    ys.append(mean)
            if xs:
                ax.plot(
                    xs, ys, "-o", color=style.FAMILY_COLORS[fam], linewidth=2,
                    markersize=4, label=fam, zorder=3,
                )
        ax.set_title(f"{target} (must not rise above tolerance)", fontsize=9.5)
        ax.set_xticks(levels)
        ax.set_xticklabels([f"T{lv}" for lv in levels])
        if i == 0:
            ax.set_ylabel("I_V (nats)")
            ax.legend(frameon=False, fontsize=8.5, labelcolor=style.TEXT_SECONDARY)
    fig.suptitle(
        "Control tasks — shuffled labels must carry no extractable information",
        color=style.TEXT_PRIMARY, fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=style.SURFACE)
    import matplotlib.pyplot as plt

    plt.close(fig)
    return True


def make_report(run_dir: Path, out_dir: Path) -> Path:
    """Build results/reports/a0_calibration/ from one calibration run directory."""
    run_dir, out_dir = Path(run_dir), Path(out_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    summary = json.loads((run_dir / "summary.json").read_text())
    cells = load_cells(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figs = out_dir / "figures"
    figs.mkdir(exist_ok=True)

    surface_figure(cells, figs / "calibration_surface.png")
    ctrl_tol = 0.05
    has_ctrl = control_figure(cells, ctrl_tol, figs / "controls.png")

    ok_cells = [c for c in cells if c.get("cell_status", "ok") == "ok"]
    n_failed = len(cells) - len(ok_cells)
    verdict = "PASS ✅" if summary.get("pass") else "FAIL ❌"

    lines = [
        "# Phase A0 — instrument calibration report",
        "",
        f"**Verdict: {verdict}**"
        + (" (smoke run — reduced grid)" if manifest.get("smoke") else ""),
        "",
        "The measuring instrument (V-information probing protocol) is run on",
        "synthetic buildings where each target is PLANTED at a known level.",
        "It passes only if the measured usable information jumps exactly at the",
        "planted level and shuffled controls extract nothing (plan §6 Phase A0).",
        "",
        "| | |",
        "|---|---|",
        f"| run_id | `{manifest['run_id']}` |",
        f"| git SHA | `{manifest['git']['sha'][:12]}` |",
        f"| config | `{manifest['config_path']}` (sha256 `{manifest['config_sha256'][:12]}…`) |",
        f"| seed | {manifest['seed']} |",
        f"| cells | {len(cells)} ({n_failed} failed) |",
        f"| host/job | {manifest.get('host', '?')} |",
        "",
        "## Calibration surface",
        "",
        "![calibration surface](figures/calibration_surface.png)",
        "",
        "Reading guide: each panel is one planted target; the dashed vertical line",
        "marks where the answer was hidden. A correct instrument shows curves that",
        "are ~flat at zero LEFT of the line and jump at/after it — for the families",
        "capable of reading that structure (V2+ linear for attribute counts, V4/V5",
        "GNNs for connectivity, V0 readout for the R4 zone attribute).",
        "",
    ]
    if has_ctrl:
        lines += [
            "## Controls",
            "",
            "![controls](figures/controls.png)",
            "",
            "Negative values are harmless optimization noise; only values ABOVE the",
            "dashed tolerance would indicate leakage/memorization.",
            "",
        ]
    lines += ["## Checks", "", "| check | detail | result |", "|---|---|---|"]
    for c in summary["checks"]:
        if c["kind"] == "saturation":
            detail = (
                f"{c['target']} · {c['family']}: I_V@T{c['saturation_level']} = "
                f"{c['i_v_at_saturation']:.3f} vs max below = {c['max_i_v_below']:.3f} "
                f"(margin {c['margin']:g})"
            )
        else:
            detail = (
                f"control {c['target']} · {c['family']} @T{c['level']}: "
                f"I_V = {c['i_v']:+.3f} (< tol, one-sided)"
            )
        lines.append(f"| {c['kind']} | {detail} | {'PASS' if c['ok'] else 'FAIL'} |")
    lines += [
        "",
        "_Regenerate with `scripts/make_reports.py` — figures are derived from the",
        "run's cell records; nothing here is hand-entered._",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    return out_dir / "report.md"
