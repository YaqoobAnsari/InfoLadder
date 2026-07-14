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

## 2026-07-14 — D-006: Compute goes through slurm on deepnet; login node is compute-free (supersedes D-003)

**Context.** User directive: full GPU/CPU suite available via slurm ("deepnet"); hard
rule that no job runs on the login node (where this repo lives). Probed layout in
docs/CLUSTER.md: default partition `gpu2` (deepnet2: 64 CPUs, H200 MIG slices 28×1g/6×2g/2×7g,
QOS caps 4/2/1 per user, NFS-mounts our /data1); partition `cpu` (mcore-n01: 128 CPUs)
does NOT see our /data1. `--mcs-label=morshed` required on all submissions. 2-day walltime.
**Decision.** All experiments submit to `gpu2` via the sbatch templates in
scripts/slurm/ (CPU-only jobs included, since mcore-n01 can't reach the repo/data
without staging). Phase B runs as an array job over grid shards; Phase D requests one
1g.18gb MIG slice per run. The login node keeps only edit/git/queries/`make verify`.
**Consequences.** D-003's CPU-only constraint is void — Phase D is unblocked. The grid
runner must grow a `--shard N/M` flag before B-3 (added to task text). If Phase B ever
needs mcore-n01's 128 CPUs, write a staging script + new DECISIONS entry.

## 2026-07-14 — D-007: Project working name "InfoLadder"; package name stays topospec

**Context.** GitHub repo created as YaqoobAnsari/InfoLadder ("tentative name").
**Decision.** Repo/paper working name InfoLadder; the Python package remains
`topospec` until the name is final (rename is cheap and mechanical; churn now is not).
