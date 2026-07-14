# EXPERIMENT PROTOCOL — pre-registered analysis rules (plan §4.3, §4.4, §8, §9)

This file is the operational statistical contract. It is written BEFORE the Phase B grid
runs and changes only via DECISIONS.md entries. The stats-auditor agent checks every
reported claim against these rules.

## 1. Estimation

- **I_V cell estimate.** For grid cell (level k, target Y, family V, seed s):
  train probe on train split, select on val split (early stopping / regularization only —
  never architecture), report held-out test cross-entropy in nats.
  `I_V = H_V(Y) − H_V(Y|X)` where H_V(Y) uses family V1 (marginal) on the same splits.
- **Restarts.** k=3 optimization restarts per (cell, seed); all restarts stored; the
  cell value is best-of-k (lowest held-out CE), reflecting that I_V estimates are lower
  bounds (plan §8). Aggregation over the 3 seeds: mean ± bootstrap CI.
- **Conditional V-info (annotation gain numerator).** I_V(ΔR_{k+1}→Y | R_k) estimated as
  H_V(Y | R_k) − H_V(Y | R_k ⊕ Δ features), same family, same budgets, concatenated
  inputs (Hewitt et al. 2021). Never computed as a difference of two independent I_V
  estimates.
- **MDL.** Prequential coding with block schedule doubling from 1/64 of the training set;
  codelength = Σ block CE (nats) + uniform cost of first block. Reported per cell.

## 2. Fairness constraints (plan §4.4) — enforced in code

- Fixed probe parameter budget per family across levels (assertions in
  `probes/families.py`; tolerance ±5% forced by input-dim differences, which are
  documented per level in the run manifest).
- Identical optimizer, epochs, batch size, early-stopping rule per family across levels.
- Identical splits across ALL cells (split hash recorded in every manifest).
- Input dimensionality per level documented and released with the grids.
- Results are reported as capacity sweeps (all families), never a single probe.

## 3. Splits

- Building-level, never floor-level. Stratify by dataset and building size decile.
- Ratios 70/15/15 train/val/test. Generated once (DATA-4), sha256 of the assignment file
  recorded; any regeneration invalidates all prior cells and requires a DECISIONS entry.
- InstBuild gold set: held out entirely from probe training; used as the out-of-regime
  stress evaluation (plan §7) and for the S4 scale split.

## 4. Validity gates (must pass before results are interpreted)

- **Control task:** probes must extract nothing from Y_ctrl — I_V < tolerance
  (one-sided: negative control I_V is overfitting noise and harmless; POSITIVE
  extraction signals leakage/memorization) and accuracy within 2 SE of chance, for
  every family × level; otherwise the affected cells are quarantined (registry
  status=quarantined) and the cause investigated.
- **Calibration:** Phase A0 planted-target recovery must be PASS (ROADMAP A0-2/A0-3).
- **Oracle skyline sanity:** oracle features must beat every same-family real cell for
  the same target; violations flag an implementation bug.
- **Leakage reporting (plan §5):** ARI(R4 zone annotation, Y_zone) reported next to any
  Y_zone R4 cell; probe excess-over-agreement computed; Y_rank/Y_egress curves shown
  alongside as leakage-free confirmation.

## 5. Hypothesis tests (pre-registered; plan §10)

- Level comparisons (S1, S2, S9): paired Wilcoxon signed-rank across buildings on
  per-building held-out CE, one-sided where the hypothesis is directional,
  **Holm-corrected across the level-comparison family per target**. α = 0.05.
- Monotonicity (S1): test all adjacent pairs (R_k vs R_{k+1}); "monotone" claim requires
  all adjacent deltas ≥ 0 (within correction) AND at least one strictly positive.
- Dips (S9): a dip is a significant NEGATIVE adjacent delta for a small family (V2–V4)
  that is absent (non-significant or positive) for V5+ on the same cell.
- Capacity compensation (S3): compare V6-on-R0 vs V2-on-R4 at matched n; the ≥5× sample
  cost claim requires the sample-efficiency curves (C-2) to cross at ≥5× n, bootstrap CI
  on the crossing point.
- Scale dependence (S4): interaction contrast — (ΔI_V from R2→R4 on institutional) −
  (same on residential), cluster bootstrap over buildings, 95% CI excluding 0.
- Uncertainty: 1000-resample cluster bootstrap (clusters = buildings) for every reported
  mean; 95% percentile CIs on all I_V estimates and derived quantities (annotation gain,
  compensation gap).

## 6. Reporting

- Primary: I_V (nats) per cell + MDL codelength complement. Derived: annotation gain
  ΔI_V/Δc, compensation gap, sample-efficiency slopes. Secondaries: ARI/NMI (zones),
  Spearman (rank), precision@k (egress), macro-F1 (type).
- Negative and flat results are reported with the same prominence as positive ones
  (plan §12 commitment).
- Every figure/table cell → registry run_ids; the traceability map lives in
  paper/claims.md.
