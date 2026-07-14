# T4 — The Representation Spectrum Study

**How much structure does physical inference need?** Measuring usable information
(predictive V-information + MDL probing) across a nested five-level spectrum of
floorplan graph representations, R0 (rooms + undirected connectivity) → R4 (typed,
directed, hierarchically organized — the HDG), with an annotation-cost axis.

- **Full research plan:** [`T4_spectrum_study_plan.md`](T4_spectrum_study_plan.md) — the authoritative source for claims, hypotheses, and protocol.
- **Operational breakdown:** [`docs/ROADMAP.md`](docs/ROADMAP.md) — phases, tasks, acceptance criteria, gates.
- **Working norms for agents/contributors:** [`CLAUDE.md`](CLAUDE.md).
- **Target venue:** ICLR (deadline ~mid-September 2026; 8 working weeks from 2026-07-14).

## Quick start

```bash
make setup            # install deps into the topofield conda env (one-time)
make install          # editable-install the topospec package
make verify           # lint + fast tests — must pass before any commit
make calibrate-smoke  # tiny end-to-end Phase A0 run: proves the pipeline is alive
```

All python runs use `/data1/yansari/.conda/envs/topofield/bin/python` (the `topofield`
conda env). The Makefile enforces this; never use the system python.

## Repository layout

```
T4_spectrum_study_plan.md   authoritative research plan (do not edit casually)
CLAUDE.md                   working norms; scoped CLAUDE.md files live in subdirs
docs/                       roadmap, decisions, glossary, protocol, data guide
configs/                    YAML experiment configs (the only way to launch runs)
src/topospec/
  graphs/                   spectrum core: R0–R4 schema, forgetting maps, validation, serializers
  data/                     dataset builders (synthetic Phase-A0 + real-corpus loaders)
  labels/                   target generation: Y_pde, Y_zone, Y_rank, Y_egress, Y_type, Y_ctrl
  probes/                   probe families V0–V7 + level-respecting featurization
  vinfo/                    V-information / conditional V-information / MDL estimators
  stats/                    bootstrap CIs, paired Wilcoxon + Holm, task-native metrics
  experiments/              config loading, run manifests, append-only registry, grid runner
tests/                      invariant + estimator + solver tests (`make test`)
data/                       raw/derived corpora + labels (gitignored; see data/README.md)
runs/                       per-run artifacts incl. manifest.json (gitignored)
results/                    registry.jsonl (append-only, tracked) + figures
paper/                      claims traceability + LaTeX (Phase E)
```

## Integrity

Every reported number must trace to a run manifest (git SHA + config hash + seed) in
`results/registry.jsonl`. Results files are append-only and machine-written; hand-editing
them is prohibited. See `CLAUDE.md` §Integrity.
