# configs/ · runs/ · results/ — scoped norms

The experiment I/O triangle:

- **configs/** (tracked): YAML files, the only launch mechanism. A config fully
  determines a run given the code at one git SHA. Configs are immutable once a run that
  used them is registered — make a new file (`grid_phase_b_v2.yaml`), never edit in place.
- **runs/** (gitignored): one directory per run_id containing `manifest.json`
  (git SHA, config path + sha256, seed, host, package versions, start/end, status),
  `log.txt`, and raw per-cell outputs. Machine-written only.
- **results/registry.jsonl** (tracked, APPEND-ONLY): one line per completed OR failed
  run, written by `topospec.experiments.registry`. Never edit or delete lines; a bad run
  is superseded by a new line with `supersedes: <run_id>` and a reason.

Hard rules:

1. No number leaves this directory tree into the paper or a report unless it traces to a
   registry line. If asked to "quickly check" something, that's still a (smoke) run with
   a manifest.
2. Uncommitted-code runs are refused by the runner unless `allow_dirty: true` is set in
   the config — and that flag is for smoke tests only, never for registered grid cells.
3. Figures under `results/figures/` are regenerated from the registry by scripts;
   the generating script + registry state, not the PNG, is the artifact of record.
4. All grid cells get released with the paper (plan §9: "all raw grids released") —
   design file formats accordingly (JSON/CSV, self-describing, no pickles).
5. **Phase reports** (project guideline: neat, visual documentation): every completed
   phase gets `results/reports/<phase>/report.md` (tracked) — what ran (run_ids),
   headline figures, tables with CIs, interpretation, and surprises/anomalies — plus
   its figures. Reports are written for a reader who has not seen the runs. Load the
   dataviz skill before writing any figure code.
