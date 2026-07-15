"""Score Tesseract2 output on MSD renders against MSD shipped ground truth (D-014).

SCOPE (team-lead order, 2026-07-14): this validates the FREE tiers T0/T1 — room
detection, room-type labels (CRAFT), and connectivity — NOT the door tier. With the
synthetic door arcs detected at only ~2/19, T2 door-node numbers are NOT valid for
tier-information claims; the door-detection rate is reported only as evidence for the
door-model decision.

Per plan it maps MSD ground-truth spaces (meters) into the render's pixel frame
(render_report transform) and matches them to Tesseract post_pruning nodes by
centroid, then computes: room-detection precision/recall/F1, per-category space
counts, room-type accuracy (CRAFT-read label vs the drawn label), adjacency
agreement, and the door-detection rate. Aggregates to a batch report.

Reads:  render dir (render_report.json + the MSD pickles in data/raw/msd/graph_out)
        Tesseract2 Results/Json/<img>/<img>_post_pruning.json + room_labels.txt
Writes: <render_dir>/batch_report.{json,md}
"""

from __future__ import annotations

import json
import math
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAW = Path("data/raw/msd/graph_out")
TESS = Path("/data1/yansari/PhD/topofield/Tesseract2")
ROOM_NAMES = [
    "Bedroom", "Livingroom", "Kitchen", "Dining", "Corridor", "Stairs",
    "Storeroom", "Bathroom", "Balcony", "Structure", "Door", "Entrance Door", "Window",
]
# MSD room type -> coarse space category (matches Tesseract node types)
CATEGORY = {
    "Bedroom": "room", "Livingroom": "room", "Kitchen": "room", "Dining": "room",
    "Storeroom": "room", "Bathroom": "room",
    "Corridor": "corridor", "Balcony": "outside", "Stairs": "transition",
}
# MSD type -> the label drawn on the raster (must match render_msd_rasters.LABEL_REMAP)
DRAWN = {
    "Bedroom": "bedroom", "Livingroom": "livingroom", "Kitchen": "kitchen",
    "Dining": "diningroom", "Corridor": "hall", "Stairs": "stairs",
    "Storeroom": "study", "Bathroom": "bathroom", "Balcony": "na",
}


def _gt_spaces(graph, tr):
    """MSD spaces with centroids in pixel coords (via the render transform)."""
    minx, maxy, ppm, pad = tr["minx"], tr["maxy"], tr["ppm"], tr["pad"]
    spaces = {}
    for key, att in graph.nodes(data=True):
        rt = att.get("room_type")
        cen = att.get("centroid")
        if rt is None or cen is None:
            continue
        name = ROOM_NAMES[int(rt)] if int(rt) < len(ROOM_NAMES) else str(rt)
        px = (float(cen[0]) - minx) * ppm + pad
        py = (maxy - float(cen[1])) * ppm + pad
        spaces[key] = {"name": name, "cat": CATEGORY.get(name, "room"),
                       "drawn": DRAWN.get(name, name.lower()), "px": (px, py)}
    edges = [(u, v) for u, v, _ in graph.edges(data=True)]
    return spaces, edges


def _tess_spaces(post):
    """Tesseract space nodes (room/corridor/transition) + door-contracted adjacency."""
    nodes = {n["id"]: n for n in post["nodes"]}
    spaces = {}
    for nid, n in nodes.items():
        t = n.get("type")
        if t in ("room", "corridor", "transition") and not n.get("is_subnode"):
            pos = n.get("position") or n.get("room_centroid_xy") or [0, 0]
            spaces[nid] = {"cat": t, "px": (float(pos[0]), float(pos[1]))}
    doors = {nid for nid, n in nodes.items() if n.get("type") == "door"}
    adj = defaultdict(set)
    door_nbrs = defaultdict(set)
    for e in post["edges"]:
        s, t = e["source"], e["target"]
        if s in doors or t in doors:
            d, o = (s, t) if s in doors else (t, s)
            if o in spaces:
                door_nbrs[d].add(o)
        elif s in spaces and t in spaces:
            adj[s].add(t)
            adj[t].add(s)
    for nbrs in door_nbrs.values():  # contract doors -> pairwise space edges
        nbrs = list(nbrs)
        for i in range(len(nbrs)):
            for j in range(i + 1, len(nbrs)):
                adj[nbrs[i]].add(nbrs[j])
                adj[nbrs[j]].add(nbrs[i])
    return spaces, adj, len(doors)


def _read_labels(txt_path):
    if not txt_path.exists():
        return []
    out = []
    for m in re.finditer(r"\[(\d+),\s*(\d+),.*?\], Text:\s*([a-z ]+)", txt_path.read_text()):
        out.append((float(m.group(1)), float(m.group(2)), m.group(3).strip()))
    return out


def _match(gt, tess, max_px):
    """Greedy nearest-centroid matching gt_id -> tess_id within max_px."""
    pairs = []
    for g, gv in gt.items():
        for t, tv in tess.items():
            d = math.dist(gv["px"], tv["px"])
            if d <= max_px:
                pairs.append((d, g, t))
    pairs.sort()
    gm, tm, matched = set(), set(), {}
    for _d, g, t in pairs:
        if g in gm or t in tm:
            continue
        gm.add(g)
        tm.add(t)
        matched[g] = t
    return matched


def score_plan(native_id, tr, ppm):
    graph = pickle.load(open(RAW / f"{native_id}.pickle", "rb"))
    post_p = TESS / "Results/Json" / f"msd_{native_id}" / f"msd_{native_id}_post_pruning.json"
    if not post_p.exists():
        return None
    gt, gt_edges = _gt_spaces(graph, tr)
    tess, tess_adj, n_doors = _tess_spaces(json.load(open(post_p)))
    max_px = 2.0 * ppm  # match within ~2 m

    # room detection (room category only)
    gt_rooms = {k: v for k, v in gt.items() if v["cat"] == "room"}
    tess_rooms = {k: v for k, v in tess.items() if v["cat"] == "room"}
    m_rooms = _match(gt_rooms, tess_rooms, max_px)
    tp = len(m_rooms)
    fp = len(tess_rooms) - tp
    fn = len(gt_rooms) - tp
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    # room-type accuracy: CRAFT-read label nearest each GT space vs the drawn label
    labels = _read_labels(TESS / "Results/Plots/interpreter_detect" / f"msd_{native_id}" / "room_labels.txt")
    type_hits = type_tot = 0
    for gv in gt.values():
        type_tot += 1
        if not labels:
            continue
        best = min(labels, key=lambda L: math.dist((L[0], L[1]), gv["px"]))
        if math.dist((best[0], best[1]), gv["px"]) <= max_px and best[2] == gv["drawn"]:
            type_hits += 1

    # adjacency agreement over the MATCHED subgraph (all categories, doors contracted)
    g2t = _match(gt, tess, max_px)
    matched_tess = set(g2t.values())
    gt_pairs = set()
    for u, v in gt_edges:
        if u in g2t and v in g2t and g2t[u] != g2t[v]:
            gt_pairs.add(frozenset((g2t[u], g2t[v])))
    tess_pairs = set()
    for s, nbrs in tess_adj.items():
        for t in nbrs:
            if s in matched_tess and t in matched_tess and s != t:
                tess_pairs.add(frozenset((s, t)))
    inter = len(gt_pairs & tess_pairs)
    adj_prec = inter / len(tess_pairs) if tess_pairs else 0.0
    adj_rec = inter / len(gt_pairs) if gt_pairs else 0.0
    adj_f1 = 2 * adj_prec * adj_rec / (adj_prec + adj_rec) if adj_prec + adj_rec else 0.0

    gt_cat = Counter(v["cat"] for v in gt.values())
    tess_cat = Counter(v["cat"] for v in tess.values())
    return {
        "native_id": native_id,
        "gt_rooms": len(gt_rooms), "tess_rooms": len(tess_rooms),
        "room_precision": round(prec, 3), "room_recall": round(rec, 3), "room_f1": round(f1, 3),
        "type_acc": round(type_hits / type_tot, 3) if type_tot else 0.0,
        "adj_f1": round(adj_f1, 3), "adj_gt_edges": len(gt_pairs), "adj_match_edges": inter,
        "gt_categories": dict(gt_cat), "tess_categories": dict(tess_cat),
        "n_doors_detected": n_doors,
    }


def _reconcile_missing(missing) -> dict:
    """Explain plans that have no post_pruning graph by their leftover Tesseract JSON
    fingerprint, so 'n_missing_output' is accounted for rather than opaque (D-014).

    Main.py writes JSON in this order: ini_graph -> final_graph -> classify_doors
    (the 5-colour-palette gate at utils/Improve.py) -> pre_pruning -> post_pruning.
    So a plan that died in the door stage has ini+final but neither pruning file.
    Buckets (a plan is "missing" here iff it lacks post_pruning):
      doorstage_no_pruning : ini+final present, no pre/post. Dominant cause is the
        classify_doors 5-colour crash on plans lacking a region class (no corridor/
        balcony) — patched 2026-07-15 (InfoLadder); a rare door-detection OOM leaves
        the same fingerprint (disambiguate via the slurm oom_kill count).
      pre_no_post   : pre_pruning present, post absent (pruning-stage crash).
      early_crash   : ini present, final absent (crash before the door stage).
      no_output     : no result dir at all (render/copy/other failure).
    """
    from collections import Counter
    buckets: Counter = Counter()
    ids = defaultdict(list)
    for nid in missing:
        d = TESS / "Results/Json" / f"msd_{nid}"
        def _has(stage, _nid=nid, _d=d):
            return (_d / f"msd_{_nid}_{stage}.json").exists()
        if not d.exists():
            key = "no_output"
        elif _has("pre_pruning"):
            key = "pre_no_post"
        elif _has("ini_graph") and _has("final_graph"):
            key = "doorstage_no_pruning"
        elif _has("ini_graph"):
            key = "early_crash"
        else:
            key = "no_output"
        buckets[key] += 1
        ids[key].append(nid)
    return {"counts": dict(buckets), "examples": {k: sorted(v)[:8] for k, v in ids.items()}}


def main() -> int:
    render_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/derived/msd_render_arc")
    reports = {r["native_id"]: r for r in json.load(open(render_dir / "render_report.json"))}
    rows, missing = [], []
    for nid, rr in reports.items():
        tr = rr.get("transform")
        if tr is None:
            missing.append(nid)
            continue
        s = score_plan(nid, tr, rr["px_per_m"])
        if s is None:
            missing.append(nid)
            continue
        s["n_arcs"] = rr.get("n_arcs", 0)
        rows.append(s)

    n = len(rows)
    def mean(k):
        return round(sum(r[k] for r in rows) / n, 3) if n else 0.0
    tot_arcs = sum(r["n_arcs"] for r in rows)
    tot_doors = sum(r["n_doors_detected"] for r in rows)
    agg = {
        "n_scored": n, "n_missing_output": len(missing),
        "room_detection": {"precision": mean("room_precision"), "recall": mean("room_recall"),
                           "f1": mean("room_f1")},
        "room_type_accuracy": mean("type_acc"),
        "adjacency_f1": mean("adj_f1"),
        "door_detection_rate": round(tot_doors / tot_arcs, 4) if tot_arcs else 0.0,
        "door_note": "T2 door tier NOT valid at this detection rate (see D-014 gate).",
        "total_arcs_rendered": tot_arcs, "total_doors_detected": tot_doors,
        "missing_reconciliation": _reconcile_missing(missing),
    }
    out = {"aggregate": agg, "provenance": _provenance(), "per_plan": rows, "missing": missing}
    (render_dir / "batch_report.json").write_text(json.dumps(out, indent=2))
    _write_md(render_dir, agg, rows, missing)
    print(json.dumps(agg, indent=2))
    return 0 if n else 1


def _provenance() -> dict:
    import datetime
    import hashlib

    def sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16] if Path(p).exists() else None

    return {
        "generated_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "scripts": {
            "render_msd_rasters.py": sha("scripts/render_msd_rasters.py"),
            "score_msd_tesseract.py": sha("scripts/score_msd_tesseract.py"),
        },
        "label_remap": DRAWN,
        "category_map": CATEGORY,
        "match_threshold": "~2 m (2*px_per_m) greedy nearest centroid",
        "door_style": "arc (opening + CAD swing-arc+leaf); door tier NOT validated",
    }


def _write_md(render_dir, agg, rows, missing):
    lines = [
        "# MSD-render → Tesseract2 batch validation (D-014, T0/T1 scope)",
        "",
        f"Scored **{agg['n_scored']}** plans ({agg['n_missing_output']} without Tesseract output).",
        "**Scope:** validates T0/T1 (rooms, labels, connectivity) vs MSD ground truth. "
        "Door tier (T2) is NOT validated — synthetic arcs detect at "
        f"**{agg['door_detection_rate']:.1%}** "
        f"({agg['total_doors_detected']}/{agg['total_arcs_rendered']} arcs); reported only "
        "as input to the door-model decision.",
        "",
        "## Aggregate",
        f"- room detection: precision {agg['room_detection']['precision']}, "
        f"recall {agg['room_detection']['recall']}, **F1 {agg['room_detection']['f1']}**",
        f"- room-type accuracy (CRAFT label vs drawn): **{agg['room_type_accuracy']}**",
        f"- adjacency agreement F1: **{agg['adjacency_f1']}**",
        f"- door-detection rate: {agg['door_detection_rate']:.1%} (T2 NOT valid)",
        "",
        "## Missing-output reconciliation",
        f"{agg['n_missing_output']} of {agg['n_scored'] + agg['n_missing_output']} "
        "plans have no post_pruning graph. By leftover-JSON fingerprint "
        "(ini_graph -> final_graph -> classify_doors 5-colour gate -> pre_pruning -> "
        "post_pruning):",
        *[f"- `{k}`: {v}" for k, v in
          sorted(agg["missing_reconciliation"]["counts"].items(), key=lambda kv: -kv[1])],
        "`doorstage_no_pruning` = crashed at the door stage; dominant cause is the "
        "classify_doors 5-colour crash on plans lacking a region class (patched "
        "2026-07-15), plus any rare door-detection OOM (same fingerprint — use the "
        "slurm oom_kill count to separate).",
        "",
        "Matching: MSD GT centroids mapped to the render pixel frame (render_report "
        "transform), greedy nearest within ~2 m to Tesseract post_pruning nodes; doors "
        "contracted for adjacency. Provenance: see `batch_report.json` (script hashes, "
        "remap table). Regenerate: `scripts/slurm/msd_tesseract_batch.sbatch`.",
    ]
    (render_dir / "batch_report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
