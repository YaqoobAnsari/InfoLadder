# GLOSSARY — canonical definitions (source: T4_spectrum_study_plan.md)

## The spectrum (plan §4.1, App. B; claim C1)

Nested deterministic extractions R_k = f_k(P) of floorplan P; R_{k+1} strictly refines
R_k (R_k recoverable via forgetting map φ). Implemented in `topospec/graphs/levels.py`.

| Level | Adds | Annotation cost c(k→k+1)/building |
|---|---|---|
| **R0** | space nodes (area, centroid) + undirected connectivity edges | — (auto) |
| **R1** | door nodes; `node.kind ∈ {room, door, corridor}`; semantic label | ≈0 (auto) |
| **R2** | `edge.tau ∈ {wall, door, corridor-link}` | ≈0 (auto) |
| **R3** | `edge.delta ∈ {both, forward, backward}` on controlled subset | 0.5–1 h |
| **R4** | containment forest E_c over `{room, corridor-cluster, zone, wing}` + zone/wing attribute blocks (the **HDG**) | 1–2 h |

Costs are Phase-Zero estimates, re-measured in Gate-b / DATA-6.

## Targets (plan §4.2)

| Target | Definition | Ground truth | Leakage status |
|---|---|---|---|
| **Y_pde** | per-room mean/rank of steady-state heat field solved on true geometry | exact (converged PDE) | anchor target; no simulator objection |
| **Y_zone** | thermal/HVAC zone assignment per room | EnergyPlus (gold, IFC lane) / validated RC surrogate (silver) | partially present in R4 — see leakage analysis, plan §5 |
| **Y_rank** | pairwise room temperature ordering | from PDE/RC temps | leakage-free by construction |
| **Y_egress** | bottleneck membership of corridor nodes (top-k congestion in evacuation sim); betweenness as graph-theoretic reference | JuPedSim sample + betweenness everywhere | leakage-free by construction |
| **Y_type** | room type | dataset annotations | **positive control** (readable at R1+) |
| **Y_ctrl** | shuffled labels (Hewitt–Liang) | — | **validity control**: probes must be at chance |

## The measure (plan §4.3)

- **H_V(Y|X)** = inf_{f∈V} E[log-loss], estimated by held-out cross-entropy (nats).
- **I_V(X→Y) = H_V(Y) − H_V(Y|X)** — usable information; a lower bound achieved by
  optimization → best-of-k restarts, MDL complement.
- **Conditional V-info** I_V(ΔR_{k+1}→Y | R_k): probe on (R_{k+1} features) vs coarser
  alone — the annotation gain numerator (Hewitt et al. 2021 construction).
- **Annotation gain** = ΔI_V / Δc (nats per hour) — claim C3.
- **MDL codelength**: prequential/online coding; probe-effort-sensitive complement.
- **Proposition 1**: if V closed under composition with φ, I_V is monotone in level;
  closure failure → possible dips (hypothesis S9).

## Probe families (plan §8) — capacity-ordered V sweep

| ID | Family | Notes |
|---|---|---|
| V0 | parameter-free readout | e.g. read R4 zone attr for Y_zone; the lookup demonstration |
| V1 | predict-from-prior | label marginal |
| V2 | linear on raw node attrs | logistic/softmax |
| V3 | V2 + spectral/positional encodings | Laplacian eigenvectors |
| V4 | 1-layer GNN | |
| V5 | 2-layer GNN | |
| V6 | 4-layer GraphGPS-style transformer ≤2M params | |
| V7 | frozen small LM over JSON serialization + linear readout | optional appendix tier |

Bounds: shuffled-label floor + oracle skyline sandwich every curve. Probes consume
tau/delta/containment only where the level provides them (featurize.py enforces).

## Statistical protocol (plan §9) — see docs/EXPERIMENT_PROTOCOL.md

3 seeds; building-level splits; bootstrap 95% CIs; paired Wilcoxon across buildings,
Holm-corrected within level families; control-task selectivity; all raw grids released.

## Named things

- **HDG** — hierarchically organized typed directed graph = R4.
- **Structural Information Profile** — a representation's I_V-vs-refinement curve per
  task per capacity (the paper's framework name, plan §11).
- **Silver / gold corpus** — auto-derived labels at scale / EnergyPlus-validated + human
  R4 annotations on the institutional stress set (plan §7).
- **InstBuild** — the 5–10 gold institutional buildings (stress set, out-of-regime eval).
- **Gate** — Week-1 feasibility triple (RC validation, timed annotation, smoke test).
- **Phase A0** — instrument calibration on synthetic planted targets; paper Figure 2.
- **Three currencies** — structure (annotation hours), capacity (probe compute), samples
  (training data) all purchase nats; Phase C prices the exchange rates (plan §11).
