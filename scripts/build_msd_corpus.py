"""Derive the full MSD corpus -> validated SpectrumGraphs (ROADMAP DATA-3).

Runs on the cluster (scripts/slurm/msd_build.sbatch), NOT the login node — it emits
~5 JSON files per plan. Reads data/raw/msd/graph_out/*.pickle, writes
data/derived/msd/<id>.r{0..4}.json + exclusions.jsonl (via topospec.data.msd.
build_graphs, apartment zone_mode by default per D-012), then writes a corpus
summary to data/derived/msd/build_report.json.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from topospec.data.msd import build_graphs

RAW = Path("data/raw/msd")
OUT = Path("data/derived/msd")


def main() -> int:
    n_in = len(list((RAW / "graph_out").glob("*.pickle")))
    t0 = time.time()
    built = build_graphs(RAW, OUT)  # apartment zone_mode (D-012)
    dt = time.time() - t0

    excl = [
        json.loads(x)
        for x in (OUT / "exclusions.jsonl").read_text().splitlines()
        if x.strip()
    ]
    # corpus stats from the returned R4 graphs
    spaces = zones = 0
    tau_counts: Counter = Counter()
    room_labels: Counter = Counter()
    zone_sizes = []
    for g in built:
        for n in g.nodes.values():
            if n.kind in ("room", "corridor"):
                spaces += 1
                room_labels[n.label] += 1
            elif n.kind == "zone":
                zones += 1
                zone_sizes.append(n.attrs.get("n_member_spaces", 0))
        for e in g.edges:
            tau_counts[e.tau] += 1

    report = {
        "n_graph_out_pickles": n_in,
        "n_built": len(built),
        "n_excluded": len(excl),
        "exclusion_reasons": dict(Counter(e["reason"] for e in excl)),
        "total_spaces": spaces,
        "total_zone_nodes": zones,
        "mean_spaces_per_plan": round(spaces / max(len(built), 1), 2),
        "mean_zones_per_plan": round(zones / max(len(built), 1), 2),
        "tau_counts": dict(tau_counts),
        "room_label_counts": dict(room_labels.most_common()),
        "json_files_written": len(list(OUT.glob("*.json"))),
        "seconds": round(dt, 1),
    }
    (OUT / "build_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\ndone: built {len(built)}/{n_in}, {len(excl)} excluded, {dt:.1f}s -> {OUT}")
    # fail the job only if EVERYTHING failed (a real problem); partial is reported
    return 1 if built == [] and n_in > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
