"""Config-driven experiment runners — plan §6.

Implemented: Phase A0 calibration on synthetic planted targets (`run_calibration`).
Gate and Phase-B grid runners are ROADMAP G-* / B-* (need real corpora).

Calibration PASS criterion (plan §6 Phase A0): the estimated I_V surface recovers each
planted saturation level — for every family that can read the planted structure, mean
I_V at the saturation level exceeds every below-saturation level by `margin` nats, and
shuffled-control cells extract no information: I_V < ctrl_tol, ONE-SIDED (negative
control I_V is overfit noise and harmless; positive extraction signals leakage).
"""

from __future__ import annotations

import json
import zlib

import numpy as np

from topospec.data import synthetic
from topospec.experiments import registry as reg
from topospec.experiments.manifest import create_run, finalize_run
from topospec.graphs.levels import forget
from topospec.graphs.validate import validate_graph
from topospec.labels.control import shuffled_labels
from topospec.probes.families import ProbeDataset, ReadoutFamily, make_family
from topospec.probes.featurize import featurize, zone_secret_column
from topospec.vinfo.estimator import estimate_cell
from topospec.vinfo.mdl import prequential_codelength

# families able to read each planted structure at/above its saturation level
READABLE_BY = {
    "planted_degree": {"V4", "V5"},
    "planted_tau": {"V2", "V3", "V4", "V5"},
    "planted_delta": {"V2", "V3", "V4", "V5"},
    "planted_zone": {"V0", "V2", "V3", "V4", "V5"},
}

SMOKE_OVERRIDES = {
    "n_buildings": 12,
    "levels": [1, 2, 4],
    "targets": ["planted_tau", "planted_zone", "planted_tau_ctrl"],
    "families": ["V1", "V2"],
    "seeds": [0],
    "n_restarts": 1,
    "mdl": False,
}


def _build_datasets(
    corpus: list, levels: list[int], targets: list[str], rng: np.random.Generator
) -> tuple[dict, dict]:
    """labels_by_target[building_i][node_id]; datasets[(level, target)] = ProbeDataset."""
    labels_by_target: dict[str, list[dict[str, int]]] = {}
    for target in targets:
        base = target[: -len("_ctrl")] if target.endswith("_ctrl") else target
        per_bldg = [synthetic.planted_labels(g, base) for g in corpus]
        if target.endswith("_ctrl"):
            per_bldg = [shuffled_labels(lab, rng) for lab in per_bldg]
        labels_by_target[target] = per_bldg

    datasets: dict[tuple[int, str], ProbeDataset] = {}
    n_pe = 4
    for level in levels:
        feats = []
        for g in corpus:
            gk = forget(g, level)
            validate_graph(gk)
            feats.append(featurize(gk, with_pe=True, n_pe=n_pe))
        for target in targets:
            lab_arrays = []
            for fg, lab in zip(feats, labels_by_target[target], strict=True):
                y = np.full(len(fg.node_ids), -1, dtype=np.int64)
                for nid, val in lab.items():
                    y[fg.node_pos[nid]] = val
                lab_arrays.append(y)
            datasets[(level, target)] = ProbeDataset(
                graphs=feats,
                labels=lab_arrays,
                n_classes=2,
                n_pe=n_pe,
                meta={"level": level, "target": target},
            )
    return labels_by_target, datasets


def _make_v0(target: str, level: int):
    if target == "planted_zone" and level == 4:
        col = zone_secret_column()
        return ReadoutFamily(lambda g, c=col: (g.x[:, c] > 0.5).astype(np.int64))
    return None


def run_calibration(
    cfg: dict, config_sha: str, config_path: str, smoke: bool = False
) -> int:
    """Returns process exit code: 0 PASS, 2 FAIL (calibration criterion unmet)."""
    if smoke:
        cfg = {**cfg, **SMOKE_OVERRIDES}
    seed = int(cfg["seed"])
    levels = list(cfg.get("levels", [0, 1, 2, 3, 4]))
    targets = list(cfg.get("targets", [*synthetic.PLANTED_TARGETS, "planted_tau_ctrl"]))
    families = list(cfg.get("families", ["V1", "V2", "V3", "V4", "V5"]))
    seeds = list(cfg.get("seeds", [0, 1, 2]))
    n_restarts = int(cfg.get("n_restarts", 3))
    margin = float(cfg.get("margin_nats", 0.1))
    ctrl_tol = float(cfg.get("ctrl_tol_nats", 0.05))
    run_mdl = bool(cfg.get("mdl", False))

    run_dir = create_run(
        experiment="calibration_a0",
        config_path=config_path,
        config_sha256=config_sha,
        seed=seed,
        smoke=smoke,
        allow_dirty=bool(cfg.get("allow_dirty", False)),
    )
    (run_dir / "cells").mkdir()
    print(f"[calibrate] run dir: {run_dir}")

    try:
        rng = np.random.default_rng(seed)
        corpus = synthetic.generate_corpus(rng, n_buildings=int(cfg.get("n_buildings", 60)))
        for g in corpus:
            validate_graph(g)
        _, datasets = _build_datasets(corpus, levels, targets, rng)

        n_bldg = len(corpus)
        perm = np.random.default_rng(seed + 1).permutation(n_bldg)
        n_tr, n_va = int(0.7 * n_bldg), int(0.15 * n_bldg)
        tr_idx = perm[:n_tr].tolist()
        va_idx = perm[n_tr : n_tr + n_va].tolist()
        te_idx = perm[n_tr + n_va :].tolist()

        results: list[dict] = []
        cell_no = 0
        for (level, target), ds in sorted(datasets.items()):
            fam_names = list(families)
            if "V0" not in fam_names and _make_v0(target, level) is not None:
                fam_names = ["V0", *fam_names]
            for fam_name in fam_names:
                if fam_name == "V0":
                    family = _make_v0(target, level)
                    if family is None:
                        continue
                else:
                    family = make_family(fam_name)
                for s in seeds:
                    cell_no += 1
                    # crc32, not hash(): str hash is process-randomized (CLAUDE.md: seeded RNG only)
                    cell_rng = np.random.default_rng(
                        [seed, level, zlib.crc32(target.encode()), s, cell_no]
                    )
                    est = estimate_cell(
                        family,
                        ds.subset(tr_idx),
                        ds.subset(va_idx),
                        ds.subset(te_idx),
                        cell_rng,
                        n_restarts=n_restarts,
                    )
                    rec = {
                        "level": level,
                        "target": target,
                        "family": fam_name,
                        "seed": s,
                        **est.to_dict(),
                    }
                    if run_mdl and fam_name not in ("V0", "V1"):
                        mdl = prequential_codelength(family, ds.subset(tr_idx), cell_rng)
                        rec["mdl"] = mdl.to_dict()
                    results.append(rec)
                    fname = f"L{level}_{target}_{fam_name}_s{s}.json"
                    (run_dir / "cells" / fname).write_text(json.dumps(rec, indent=1))
                    print(
                        f"  cell L{level:<2} {target:<18} {fam_name:<3} s{s}: "
                        f"I_V={est.i_v:+.3f} nats (H_V(Y)={est.h_y:.3f})"
                    )

        report = _calibration_report(results, targets, levels, margin, ctrl_tol)
        (run_dir / "summary.json").write_text(json.dumps(report, indent=2))
        _print_report(report)

        manifest = finalize_run(
            run_dir, "completed", {"calibration_pass": report["pass"]}
        )
        reg.append_entry(
            {
                "run_id": manifest["run_id"],
                "experiment": "calibration_a0",
                "status": "completed",
                "smoke": smoke,
                "n_cells": len(results),
                "calibration_pass": report["pass"],
                "config_sha256": config_sha,
                "git_sha": manifest["git"]["sha"],
                "seed": seed,
            }
        )
        return 0 if report["pass"] else 2
    except Exception:
        finalize_run(run_dir, "failed")
        manifest = json.loads((run_dir / "manifest.json").read_text())
        reg.append_entry(
            {
                "run_id": manifest["run_id"],
                "experiment": "calibration_a0",
                "status": "failed",
                "smoke": smoke,
                "config_sha256": config_sha,
                "git_sha": manifest["git"]["sha"],
                "seed": seed,
            }
        )
        raise


def _mean_iv(results: list[dict], target: str, level: int, family: str) -> float | None:
    vals = [
        r["i_v"]
        for r in results
        if r["target"] == target and r["level"] == level and r["family"] == family
    ]
    return float(np.mean(vals)) if vals else None


def _calibration_report(
    results: list[dict], targets: list[str], levels: list[int],
    margin: float, ctrl_tol: float,
) -> dict:
    checks: list[dict] = []
    for target in targets:
        fams = sorted({r["family"] for r in results if r["target"] == target})
        if target.endswith("_ctrl"):
            for fam in fams:
                if fam == "V1":
                    continue
                for level in levels:
                    iv = _mean_iv(results, target, level, fam)
                    if iv is None:
                        continue
                    checks.append(
                        {
                            "kind": "control",
                            "target": target,
                            "family": fam,
                            "level": level,
                            "i_v": iv,
                            "ok": bool(iv < ctrl_tol),  # one-sided: no extraction
                        }
                    )
            continue
        sat = synthetic.PLANTED_SATURATION_LEVEL[target]
        for fam in fams:
            if fam not in READABLE_BY[target]:
                continue
            at = _mean_iv(results, target, sat, fam) if sat in levels else None
            if at is None:
                at_levels = [lv for lv in levels if lv >= sat]
                if not at_levels:
                    continue
                at = _mean_iv(results, target, min(at_levels), fam)
            below = [
                _mean_iv(results, target, lv, fam) for lv in levels if lv < sat
            ]
            below = [b for b in below if b is not None]
            below_max = max(below) if below else 0.0
            ok = at is not None and at >= below_max + margin
            checks.append(
                {
                    "kind": "saturation",
                    "target": target,
                    "family": fam,
                    "saturation_level": sat,
                    "i_v_at_saturation": at,
                    "max_i_v_below": below_max,
                    "margin": margin,
                    "ok": bool(ok),
                }
            )
    return {"pass": all(c["ok"] for c in checks) and len(checks) > 0, "checks": checks}


def _print_report(report: dict) -> None:
    print("\n=== calibration checks ===")
    for c in report["checks"]:
        flag = "PASS" if c["ok"] else "FAIL"
        if c["kind"] == "control":
            print(
                f"  [{flag}] control {c['target']} {c['family']} L{c['level']}: "
                f"I_V={c['i_v']:+.3f} (must be < tol; negative = overfit noise)"
            )
        else:
            print(
                f"  [{flag}] {c['target']} {c['family']}: I_V@R{c['saturation_level']}="
                f"{c['i_v_at_saturation']:.3f} vs below-max {c['max_i_v_below']:.3f}"
            )
    print(f"=== calibration {'PASS' if report['pass'] else 'FAIL'} ===")


def run_gate(cfg: dict, config_sha: str, config_path: str) -> int:
    raise NotImplementedError(
        "Gate runner needs real data lanes: ROADMAP G-a/G-b/G-c (docs/ROADMAP.md)."
    )


def run_grid(cfg: dict, config_sha: str, config_path: str) -> int:
    raise NotImplementedError(
        "Phase B grid runner is ROADMAP B-1/B-3 (docs/ROADMAP.md); requires corpus "
        "(DATA-1..3) and labels (A-1..A-6)."
    )
