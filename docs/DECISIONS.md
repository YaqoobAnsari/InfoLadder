# DECISIONS.md — architecture & scope decision log

Append-only. One entry per non-obvious choice: date, decision, alternatives, consequences.
Scope *cuts* (dropping grid cells, targets, datasets) additionally require user approval.

---

## 2026-07-14 — D-001: R0 node set = all spaces; corridors differentiated (not created) at R1

**Context.** Plan §4.1 says R1 "adds door/corridor nodes". Two readings: (a) corridor
*spaces* are absent at R0 and rooms they connect become pairwise edges; (b) corridor
spaces exist at R0 as undifferentiated space nodes, R1 adds door nodes and *kind*
semantics distinguishing corridors.
**Decision.** Reading (b): R0 contains every space (room or corridor) as an untyped node
with only geometric attributes (area, centroid); R1 adds door nodes + `kind` +
semantic labels. The forgetting map R1→R0 removes door nodes (reconnecting their room
pairs) and strips kinds/labels.
**Why.** (b) keeps |V| comparable across levels (fairness §4.4), avoids clique blow-up
around long corridors, and matches Tesseract's navigable-graph lineage where corridors
are traversable spaces. Strict refinement holds under both; (b) is the cleaner φ.
**Consequences.** R0 connectivity through corridors is mediated by corridor nodes (as
untyped spaces). Documented in GLOSSARY; if the group prefers (a), only
`graphs/levels.py:forget_r1_to_r0` changes.

## 2026-07-14 — D-002: PDE target solver = masked finite-difference Laplace (scipy sparse), not FEM

**Context.** Y_pde needs a "standard PDE solver" on true floor geometry (plan §4.2).
**Decision.** Rasterize floor polygons (shapely) to a fine grid mask; solve steady-state
heat (Laplace/Poisson with Dirichlet exterior walls, configurable interior sources) via
scipy sparse direct solve; aggregate per-room means/ranks. Grid-refinement convergence
check required on real plans (ROADMAP A-1) before labels are declared final.
**Alternatives.** FEniCS/scikit-fem FEM on a polygon mesh — heavier dependency, better
boundary fidelity. Revisit if convergence checks fail on thin-wall geometries.
**Consequences.** Resolution is a label-pipeline hyperparameter, stored in label
manifests. Mathematical exactness claim in the paper phrased as "converged numerical
solution of an exactly specified PDE problem".

## 2026-07-14 — D-003: Compute reality — this host is CPU-only

**Context.** Plan §7 assumes "single GPU" for probes. Host = 10-core CPU VM, 46 GB RAM.
**Decision.** Probes V0–V5 run CPU-parallel here (each cell is minutes). V6 (≤2M
transformer) attempted on CPU with reduced-throughput budget; Phase D (45 runs, ≤8M
params) requires a GPU host or a decision to accept multi-day CPU runs — escalated in
ROADMAP STATUS blockers and open question §14.2.
**Consequences.** All code device-agnostic; configs carry `device: cpu`.

## 2026-07-14 — D-004: Egress default = betweenness everywhere + JuPedSim on stratified sample

**Context.** Open question §14.4 (heavier vs lighter egress labels) is unresolved.
**Decision (provisional, reversible).** Implement betweenness reference target now
(zero-dependency, plan §4.2 names it as the graph-theoretic reference), scaffold the
JuPedSim lane for the stratified sample as plan §6 Phase A specifies. Both reported.
**Consequences.** If the group chooses heuristics-only, JuPedSim lane is dropped by
config, not code surgery.

## 2026-07-14 — D-005: Phase A2 default dataset lane = code property graphs on an established defect dataset

**Context.** Plan §6 A2 requires an established dataset + one standard target with an
auto-derivable AST→+dataflow→+call ladder.
**Decision (provisional).** Devign/BigVul-lineage function-level defect detection as the
default candidate; final pick at A2-1 after checking ladder derivability with available
tooling (tree-sitter/Joern), recorded here.
**Consequences.** None yet; hard cap (one task/figure/person-week) unchanged.
