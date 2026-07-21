# Claims traceability ledger

Every claim the paper will make, mapped to evidence. Statuses: `untested` | `supported` |
`refuted` | `mixed`. A claim with no registry run_ids stays `untested` and may not be
asserted. Update at every phase boundary; the stats-auditor agent signs off status
changes.

## Contributions (plan §1)

| Claim | Statement (abbrev.) | Status | Evidence (run_ids / artifacts) | Presented in |
|---|---|---|---|---|
| C1 | Formalized five-level nested spectrum R0–R4 with defined annotation costs | untested (schema built; costs unmeasured) | toolkit: `src/topospec/graphs/`; costs ← Gate-b, DATA-6 | §3 + App. B |
| C2 | First usable-information measurement protocol over input representation levels, calibrated on planted targets | untested | calibration ← A0-2/A0-3; protocol ← docs/EXPERIMENT_PROTOCOL.md | §4 + Fig. 2 |
| C3 | Annotation gain: nats per annotation hour, per increment, per task | untested | ← C-3 (needs B grid + timed annotations) | §6 |
| C4 | Information–richness curves for physical targets + capacity-compensation + scale analysis | untested | ← B-5, C-1, C-2, C-4 | §5–6 |
| C5 | Framework generality on code property graphs (one task, one figure) | untested | ← A2-1..3 (subject to W4 kill-or-keep) | §7 |

## Hypotheses (plan §10; tests pre-registered in docs/EXPERIMENT_PROTOCOL.md §5)

| # | Hypothesis (abbrev.) | Status | Evidence | Notes |
|---|---|---|---|---|
| S1 | I_V monotone in level for physical targets; flat for Y_ctrl | untested | ← B grid | |
| S2 | Task-dependent saturation (Y_zone gains at R4; Y_egress saturates R2–R3) | untested | ← B grid | most interesting cell |
| S3 | Capacity compensation partial; ≥5× sample cost to close | untested | ← C-1, C-2 | |
| S4 | Annotation gain ≈0 residential, large institutional | untested | ← C-4 | potential headline |
| S5 | Phase-D transformers preserve probe ordering | untested | ← D-4 | |
| S6 | Functional hierarchy > geometric-only hierarchy on Y_zone | untested | ← D-3 | |
| S7 | Code-graph ladder shows same qualitative pattern | untested | ← A2-2 | |
| S8 | Y_pde and Y_zone curves agree in ordering | untested | ← B-7 | certifies simulator target |
| S9 | Non-monotone dips for small families (V2–V4), vanishing with capacity | untested | ← B grid stratified by V | Proposition 1 link |

## Formal results

| Item | Status | Evidence |
|---|---|---|
| Proposition 1 (monotonicity under closure) | stated in plan §4.3; proof to be written (E-1); mechanized check on toy family optional | paper appendix |

## Standing commitments (must appear in the paper regardless of results)

- Leakage analysis three-part answer with measured ARI (plan §5) — ← B-6.
- Scoping statement: extractability, not usage (plan §8).
- Negative/flat results published with equal prominence (plan §12).
- All raw grids + toolkit released (plan §9); genre = findings/methodology (plan §11).

## Related-work register updates (audit 2026-07-16; D-018)

| Work | Role | Differentiation (verified) |
|---|---|---|
| Clio (arXiv 2404.13696, RSS'24) | closest conceptual relative — ADD | IB-based task-conditioned scene-graph granularity COMPRESSION online; ours = offline MEASUREMENT over a fixed nested cost-priced ladder with capacity sweeps + calibration |
| Almudévar & Ortega (arXiv 2601.21568) | V-info representation comparison — ADD | learned hidden-layer activations, not input tiers; cite their capacity-relativity theorem next to our V0–V6 sweep |
| FloorplanQA v4 (ICML 2026 poster) | in-domain format comparison — UPDATE CITE | prompting-accuracy over formats; no nesting/cost/probing; cite v4 not the 2025 preprint |
| KG-construction benchmark (arXiv 2605.05476) | construction-matters relative — MONITOR | accuracy-only, unordered variants, no cost axis; under SWJ review, expansion planned — recheck late Aug |
| Annotation-cost ROI line (2108.09913, 2209.15314, TMLR'25 2502.06209) | cost-framing precedent — ADD | per-sample label cost vs accuracy; never per-representation-tier cost vs information |
| Data Checklist | venue CORRECTION | COLM 2024 (not ACL) |

**Claim-wording rule (D-018):** novelty is the PROTOCOL (nested refinement + cost
axis + capacity sweep + calibrated controls) — never "first to study representation
effects on floorplans" (dead since the 2026 wave).
