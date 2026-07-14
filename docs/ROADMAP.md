# ROADMAP — T4 Representation Spectrum Study

Operationalizes `T4_spectrum_study_plan.md` §6 (methodology) and §13 (timeline) into
tasks with acceptance criteria. Work in phase order; respect gates. Update checkboxes
and the STATUS block as work completes. Task IDs are referenced from code
(`NotImplementedError` messages), DECISIONS.md, and commit messages.

## STATUS (update on every merge)

- **Current week:** W1 (2026-07-14 – 2026-07-18)
- **Active phase(s):** INFRA (complete) → GATE + A0 + Phase A corpus derivation
- **Gates passed:** none yet (A0 smoke calibration PASS on 2026-07-14; full A0 pending
  as a slurm run)
- **Blockers:** institutional building sources for Gate-b / InstBuild (open question
  §14.1); annotator availability (§14.3). ~~GPU access~~ resolved: slurm on deepnet
  (docs/CLUSTER.md); grid runner needs `--shard N/M` before B-3.
- **Compute rule:** all experiments via `sbatch --mcs-label=morshed` on partition gpu2 —
  NEVER on the login node (docs/CLUSTER.md).
- **Last updated:** 2026-07-14 (repo scaffolded, env installed, core package + tests
  live, slurm probed, GitHub remote InfoLadder)

## Calendar (plan §13, anchored to 2026-07-14)

| Week | Dates | Contents |
|---|---|---|
| W1 | Jul 14–18 | Gate triple; A0 calibration; corpus derivation starts |
| W2 | Jul 20–24 | Phase A silver corpus + labels; A0 done; A2 starts (capped) |
| W3 | Jul 27–31 | Phase A complete (gold annotations done); Phase B starts |
| W4 | Aug 3–7 | Phase B grid; **A2 kill-or-keep checkpoint** |
| W5 | Aug 10–14 | Phase B complete; Phase C starts |
| W6 | Aug 17–21 | Phase C complete; Phase D starts |
| W7 | Aug 24–28 | Phase D complete; writing starts |
| W8 | Aug 31–Sep 4 | Writing, figures, release packaging, red-team |
| buffer | Sep 7–deadline | polish, internal review, submit |

---

## Phase INFRA (W1) — repo, env, instrument core  ✅ this scaffold

- [x] INFRA-1 Conda env `topofield` populated; imports verified (`scripts/setup_env.sh`)
- [x] INFRA-2 Package skeleton with schema/levels/forgetting maps + tests
- [x] INFRA-3 V-info + conditional V-info + MDL estimators + sanity tests
- [x] INFRA-4 PDE solver (masked finite-difference Laplace) + analytic test
- [x] INFRA-5 Probe families V0–V5 + featurization interface + budget assertions
- [x] INFRA-6 Run manifest + append-only registry + config-driven runner + CLI
- [x] INFRA-7 Synthetic planted-target generators (edge-type / direction / containment)
- [ ] INFRA-8 GraphGPS-style V6 probe (≤2M params) — needed by B-3; CPU-viable size
- [ ] INFRA-9 IndoorGML + IFC spatial-structure serializers (plan App. B; toolkit claim C1/T5).
      Acceptance: round-trip R1+→IndoorGML and R4→IFC IfcZone groups on 3 fixture graphs;
      validates against schema versions pinned in DECISIONS.md
- [ ] INFRA-10 V7 frozen-LM probe (appendix tier, optional): JSON serialization per level +
      linear readout over frozen small-LM embeddings. Defer until Phase B core grid done.

## GATE (W1) — feasibility triple (plan §6 Gate). BLOCKS Phases B–D claims on real data

- [ ] G-a RC-surrogate validation: fit RC-network thermal model on 3 IFC-lane buildings;
      compare zone/rank labels vs full EnergyPlus.
      **Acceptance: ARI > 0.7** label agreement. Artifacts: registry runs + report in
      `results/gate/`. Requires: E+ install (A-5), IFC buildings (DATA-5).
- [ ] G-b Annotate ONE institutional building R0→R4, timed.
      **Acceptance: ≤ 4 h** total annotation time, logged per level increment (this is
      also the first c(k→k+1) measurement, claim C3). Requires DATA-5 source plans.
- [ ] G-c Probe pipeline smoke test on 50 Structured3D scenes end-to-end
      (derive R0–R2 → auto labels → probe → I_V numbers in registry).
      **Acceptance: pipeline completes; control task at chance ± 2·SE.**
- [ ] G-d (added, from plan §7 data table) Directed-edge class balance check: ≥100
      directed instances across gold set, or flag scope risk to user.
- **Gate failure protocol (plan §6):** scope reduction (fewer targets / residential-only
  with institutional case study), never schedule slip. Scope cuts require a DECISIONS.md
  entry approved by the user.

## Phase A0 (W1–2) — instrument calibration on synthetic ground truth. BLOCKS all real-data claims

- [x] A0-1 Synthetic families with planted targets (INFRA-7):
      `planted_tau` (readable at R2+, connectivity-invariant), `planted_delta` (R3+),
      `planted_zone` (R4 only), plus `planted_degree` (R0+ positive control).
- [ ] A0-2 Full probing protocol on synthetic families: {R0..R4} × {4 planted targets} ×
      {V1,V2,V3,V4,V5} × 3 seeds, via `make calibrate` (submits slurm job).
      **Acceptance (plan §6): estimated I_V surface recovers each planted saturation
      level** — large jump exactly at the planted level, ≈flat elsewhere; shuffled
      control extracts nothing. This becomes paper Figure 2.
      (Smoke variant PASSed 2026-07-14 on 12 buildings / 3 levels / V1-V2 — see
      registry run 20260714T*-calibration_a0-s20260714-smoke.)
- [ ] A0-3 Phase report: `results/reports/a0_calibration/report.md` + I_V-surface
      figure (levels × targets × families) from registry; PASS/FAIL stamped. A FAIL
      freezes Phase B until the estimator is fixed. (Standing rule: EVERY phase ends
      with such a report — results/CLAUDE.md §5.)

## Phase A (W1–3) — corpus + labels

Data acquisition (details in docs/DATA.md):
- [ ] DATA-1 Structured3D: download, parse annotations → R0–R2 (~3.5K scenes / ~20K rooms)
- [ ] DATA-2 CubiCasa5K: download, parse SVG annotations → R0–R2 (~25K rooms)
- [ ] DATA-3 MSD (ECCV 2024): download → R0–R2 (~85K rooms) **and near-R4 via shipped
      per-room zone labels on 5,372 plans** (plan Lane 5 — the timeline de-risk)
- [ ] DATA-4 Split generation: building-level, stratified by dataset & size; hash stored
- [ ] DATA-5 InstBuild: source 5–10 institutional buildings (**needs user input — open
      question §14.1**); ingest to R0–R2
- [ ] DATA-6 Gold R4 annotation of InstBuild (5–10 bldgs, ≤4h each, timed → c(k→k+1));
      annotation guide written first (A-7)

Label pipelines:
- [ ] A-1 Y_pde everywhere geometry permits: steady-state heat equation on true floor
      geometry via `labels/pde.py`; per-room means + ranks. Acceptance: solver validated
      on analytic cases (done: tests) + convergence check on 10 real plans (grid
      refinement, per-room mean drift < 1%).
- [ ] A-2 Y_zone silver: RC-network surrogate on full corpus (gated by G-a validation)
- [ ] A-3 Y_rank: pairwise room temperature ordering from RC/PDE temps
- [ ] A-4 Y_egress: JuPedSim (or Vadere) evacuation sim on stratified sample → top-k
      congestion bottleneck membership; betweenness reference target on ALL plans
      (decision §14.4 — default: betweenness everywhere + JuPedSim on the sample; both
      reported). Acceptance: sim configs versioned; sample stratification documented.
- [ ] A-5 Y_zone gold lane: EnergyPlus + bim2sim on the IFC subset
- [ ] A-6 Y_type (positive control) + Y_ctrl (shuffled labels, seeded) on full corpus
- [ ] A-7 Annotation guide for R3 (access direction) + R4 (containment/zones) with
      worked example; timing sheet template (feeds C3 annotation-cost axis)

## Phase A2 (W2–4) — second domain, HARD-CAPPED (plan §6: one task, one figure, one person-week)

- [ ] A2-1 Pick dataset + task (default candidate: method-level code property graphs on
      an established defect/vulnerability dataset, e.g. Devign/BigVul lineage; record
      choice in DECISIONS.md). Derive ladder automatically: AST → +dataflow → +call edges.
- [ ] A2-2 Run the identical probing grid (reuse runner; new loader only)
- [ ] A2-3 One figure + one section draft. **W4 checkpoint: cut entirely if primary
      domain has slipped (plan §12).**

## Phase B (W3–5) — the probing campaign (primary deliverable)

- [ ] B-1 Grid configs: {R0..R4} × {Y_pde, Y_zone, Y_rank, Y_egress, Y_type, Y_ctrl} ×
      {V0..V6} × 3 seeds × best-of-3 restarts (≈450 registered runs, plan §7)
- [ ] B-2 Oracle skylines per target (plan §8): probes on hand-constructed oracle
      features; random/shuffled floors from Y_ctrl. Every curve sandwiched.
- [ ] B-3 Execute grid (parallelize across 10 CPU cores; V6 cells may need GPU host —
      flag early). Failed cells re-run with logged attempts, never dropped silently.
- [ ] B-4 MDL prequential codelength for every cell (same runs, online coding schedule)
- [ ] B-5 The usable-information surface: per-task I_V-vs-level curves with bootstrap
      CIs; conditional V-info ΔI_V(ΔR→Y|R_k) per increment (plan §4.3)
- [ ] B-6 Leakage analysis artifacts (plan §5): ARI(R4 zones, Y_zone) reported; probe
      excess-over-agreement; leakage-free targets (Y_rank, Y_egress) cross-check
- [ ] B-7 Hypothesis adjudication S1, S2, S8, S9 vs pre-registered tests in
      docs/EXPERIMENT_PROTOCOL.md; update paper/claims.md

## Phase C (W5–6) — capacity & sample-efficiency

- [ ] C-1 Capacity sweep: vary probe family capacity on R0 vs R4 for Y_zone (+ Y_pde);
      does V6-on-R0 reach V2-on-R4 at matched samples? (S3)
- [ ] C-2 Sample-efficiency slopes: training-set-size sweep per (level, family)
- [ ] C-3 Annotation gain: conditional ΔI_V per increment ÷ measured c(k→k+1) →
      nats-per-hour table (claim C3, first in literature)
- [ ] C-4 Scale split: residential vs institutional stress set (S4 — potential headline)

## Phase D (W6–7) — transformer confirmation

- [ ] D-1 Hierarchical heterogeneous graph transformer encoder (from TopoField plan) +
      flat GraphGPS + HGT instrument controls; level as config flag; identical budgets
- [ ] D-2 Fine-tune per level × 3 tasks × 3 seeds (45 runs, ≤8M params — **needs GPU
      or generous CPU time; decide by W5**)
- [ ] D-3 Geometric-hierarchy control: floors-only R4 variant (S6: functional vs
      geometric hierarchy)
- [ ] D-4 Ordering-preservation analysis vs Phase B probe ordering (S5)

## Phase E (W7–8) — writing, figures, release

- [ ] E-1 Paper skeleton with claims C1–C5 mapped to sections; leakage §5 and scoping
      statement (plan §8) written in from the first draft
- [ ] E-2 All figures scripted from registry (no hand-made numbers)
- [ ] E-3 Toolkit release packaging: schema files versioned, validation CLI, serializers,
      label-generation code, all raw grids (plan §9)
- [ ] E-4 Internal red-team against Appendix A citation-safety table + reviewer
      simulation (use the red-team-reviewer agent)
- [ ] E-5 Reproducibility pass: fresh-clone → `make verify` → one grid cell reproduced
      bit-for-bit from its manifest

## Standing open questions (plan §14 — need user/advisor input)

1. Which 5–10 institutional buildings, and in which formats? (blocks G-b, DATA-5)
2. Compute quota / GPU access for Phase B parallelism and Phase D?
3. Annotator availability, ≤40 h in W1–3?
4. Egress labels: JuPedSim (heavier) vs betweenness+capacity heuristics (lighter)?
   Default assumed here: both (betweenness everywhere, JuPedSim on stratified sample).
5. Author order / thread ownership T4 vs T5.
