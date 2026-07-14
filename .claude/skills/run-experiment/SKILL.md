---
name: run-experiment
description: Launch a registered T4 experiment (calibration, gate, grid) the compliant way — config, clean tree, manifest, registry, validity gates. Use whenever asked to "run" any measurement.
---

# Run an experiment — compliant procedure

1. **Locate or write the config** under `configs/`. Configs are immutable once used —
   variant = new file. Required keys: `experiment`, `seed`, `device`, `out_dir`, and the
   experiment-specific block (see `src/topospec/experiments/config.py` docstrings).
2. **Pre-flight:** `make verify` passes; `git status` clean (registered runs refuse
   dirty trees); disk space sanity (`du -sh runs/`).
3. **Launch:**
   `/data1/yansari/.conda/envs/topofield/bin/python -m topospec.cli <calibrate|gate|grid> --config configs/<file>.yaml`
   For anything over ~10 minutes, run under nohup in the background and monitor the log.
   This is a 10-core CPU host — set `workers` accordingly (≤ 8, leave headroom).
4. **Post-flight (mandatory):**
   - `runs/<run_id>/manifest.json` exists; git SHA and config sha256 correct.
   - `results/registry.jsonl` gained exactly the expected lines (one per run/cell batch).
   - Validity gates per docs/EXPERIMENT_PROTOCOL.md §4: control-task cells at chance;
     oracle above real cells; failures logged with status=failed.
5. **Report** run_ids, cell counts (completed/failed/quarantined), and gate outcomes.
   For results destined for claims.md or the paper, hand off to the stats-auditor agent
   before any hypothesis status changes.
