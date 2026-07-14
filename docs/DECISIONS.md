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

## 2026-07-14 — D-008: User-supplied rasters adopted as the preliminary test set + Gate-b candidate

**Context.** User provided 35 PNGs (moved `Input_Images/` → `data/raw/prelim_rasters/`):
one real institutional building across FF/LF/SF sheets (with `up`/`upE` text-variant
duplicates, cleanup pending) + 10 small residential plans + misc test images.
**Decision.** Use as (a) the end-to-end pipeline test bed before public corpora land,
(b) Gate-b candidate building (timed R0→R4 annotation). Ingest goes through the new
DATA-0 drawing→SpectrumGraph lane (semi-automatic extraction + manual correction).
Dedupe rule: one variant per sheet; never let variants enter splits as distinct
buildings. Provenance/licensing unknown → internal use only, never redistributed.
**Consequences.** New ROADMAP tasks DATA-0/DATA-7; InstBuild blocker downgraded.

## 2026-07-14 — D-009: ArchCAD-400K and FloorPlanCAD identified as institutional-scale corpus candidates

**Context.** The plan's corpora (Structured3D/CubiCasa/MSD) are residential-heavy; the
S4 scale hypothesis needs institutional volume. Scouting found: ArchCAD-400K (2025;
5,538 complete drawings, 86% non-residential; primitive-level panoptic annotations;
GitHub subset, license TBD) and FloorPlanCAD (ICCV'21; 15K+ plans incl. schools/
hospitals/malls; SVG vectors; CC BY-NC 4.0; HuggingFace download).
**Decision (provisional).** Evaluate both at DATA-7 before committing: neither ships
room polygons, so value hinges on a robust rooms-from-primitives derivation (shared
with DATA-0). FloorPlanCAD first (accessible now, license clear), ArchCAD-400K second
(bigger, newer, access to verify).
**Consequences.** If derivation works, the institutional regime gets silver-corpus
volume and InstBuild gold effort concentrates on R3/R4 annotation only — a material
de-risk for the paper's headline S4 analysis.

## 2026-07-14 — D-010: FloorPlanCAD = parser + machinery source, NOT the institutional corpus; corpus bet moves to ArchCAD-400K + primary loaders

**Context.** DATA-7 prototype (delegated agent) found two format facts beyond the
scout report: (a) FloorPlanCAD walls run CONTINUOUSLY through doorways (doors are
separate symbols) — solved by door-gap punching in `build_r0`, which is legitimately
R0 semantics ("connected by an opening"); (b) EVERY val sheet is a 140×140-unit crop
of a larger building — an exhaustive 810-sheet search found zero self-contained
multi-room plans, so rooms-from-primitives on raw sheets yields fragments (interiors
leak off-sheet; verified on the committed fixture 0402-0048).
**Decision.** Keep and commit the parser/rasterizer lane (`topospec/data/floorplancad.py`)
— it is the template for ANY labeled-vector source and already yields door positions
for R1/R2. Do NOT invest in sheet-stitching now. The institutional-volume bet moves to
ArchCAD-400K (self-contained professional drawings; access request pending) and the
plan's primary corpora (Structured3D/CubiCasa/MSD loaders, DATA-1..3, which ship
vector annotations and need no extraction). Revisit stitching only if ArchCAD access
is denied AND the primary corpora leave the institutional regime under-powered.
**Consequences.** DATA-7 partially closed (parser ✅, corpus ❌ for now); MSD loader
(DATA-3) promoted to next data task (shipped zone labels = near-R4 at zero cost).

## 2026-07-14 — D-011: Tesseract2 (user's own pipeline) is the PRIMARY raster→graph lane; morphology lane demoted to fallback/QA

**Context.** User directive: "use github.com/YaqoobAnsari/Tesseract2". Tesseract2 is
the plan §3.3 R1 lineage — CRAFT text detection (labels rooms from the sheet's text
annotations, which is exactly what the prelim pool's `up`/`upE` variants carry),
Faster R-CNN door detection, flood-fill segmentation → typed navigable graphs (rooms,
corridors, doors incl. exit/r2c/r2r/c2c types, outside, stairs/elevator transitions,
multi-floor merging). The morphology lane's QA on FF_part_1upE showed pure morphology
tops out at a corrected R0 (user flagged the uncorrected graph as wrong; two
graph-correctness passes fixed the worst, but no doors/labels are derivable).
**Decision.** Adapter `topospec/data/tesseract.py` converts Tesseract2 navigation
JSON → SpectrumGraph R2 (rooms + corridor components + typed door nodes; taus known)
with R1/R0 via forget(). Tesseract2 runs as its own env + slurm jobs (tess-runner
agent; repo cloned at ../Tesseract2). The morphology lane (topospec/data/raster.py)
stays as fallback + cross-check QA for sources without text/door annotations.
**Consequences.** Prelim pool upgrade path: R0 (morphology) → R2 (Tesseract2), and
Gate-b annotation starts from a Tesseract2 pre-fill instead of from scratch. R3/R4
remain annotation tasks. Multi-floor merging (FF/LF/SF) can reuse Tesseract2's own
MultiFloor module later.

## 2026-07-14 — D-012: MSD zone target uses 'apartment' grouping to avoid room-type leakage

**Context.** DATA-3 dissection: MSD's shipped zoning (Zone1..Zone4) is a DETERMINISTIC
function of room type (bedroom->Zone1, bathroom->Zone3, ...). Since room type is the
R1 semantic label, a category-zone target would be readable from R1 — poisoning the
R4-vs-below comparison exactly like the §5 leakage scenario, but silently.
**Decision.** `topospec.data.msd` supports both zone modes; probing targets on MSD use
`zone_mode='apartment'` (spatial units = access-graph components cut at entrance-door
edges) — a grouping NOT recoverable from room types, i.e. genuinely R4-exclusive.
Category zones remain available as a documented positive-leakage control (a target that
SHOULD be readable at R1+ — usable as an extra instrument check).
**Consequences.** Y_zone-on-MSD experiment configs must state zone_mode explicitly.
MSD's access graph is undirected -> R3 adds nothing on MSD (delta='both' everywhere);
direction measurement rests on the gold InstBuild lane, as the plan already assumed.
(Also process note: this work was swept into commit 0e592df ahead of review by a
`git add -A`; reviewed post-hoc, verdict good. Rule going forward: targeted adds only
while agents share the working tree.)

## 2026-07-14 — D-013: Balanced per-building zone secrets after A0 caught a base-rate control leak

**Context.** Full A0 calibration (slurm 7207) FAILED on exactly 2 of 53 checks:
planted_zone_ctrl at R4, V2/V3, extracted +0.115 nats from SHUFFLED labels. Diagnosis:
control shuffles preserve each building's label base-rate; iid zone secrets give
buildings uneven base-rates; R4 zone-size features identify the building — so linear
probes read the per-building BASE RATE, not the labels. A channel in the instrument,
not memorization. (GNN controls passed; linear probes latch onto the scalar feature.)
**Decision.** Synthetic generator now assigns zone secrets BALANCED per building
(half 0s/half 1s, shuffled), pinning within-building marginals near 0.5 and closing
the channel by design. Regression test on 30-building corpora. Smoke calibration PASS
after fix; full run resubmitted. The FAILED run stays in the registry per protocol.
**Consequences.** For REAL data (Phase B), the same channel exists whenever per-building
base rates vary: the analysis must report per-building-marginal controls (or a
building-marginal-aware floor) alongside global H_V(Y) — noted for EXPERIMENT_PROTOCOL
before B-1 configs are written.

## 2026-07-14 — D-012 addendum: apartment zone mode is now the msd loader DEFAULT

Scout question resolved: `zone_mode` defaults to 'apartment' in plan_to_graph and
build_graphs so a default-built corpus can never silently carry the room-type-leaking
category zones into Y_zone probing. 'category' stays available explicitly, documented
as a positive-leakage instrument control. Also per scout report: only the ~4,167 TRAIN
plans are usable (test split withholds geometry — MSD is a generation benchmark);
corpus tables updated. Full-corpus build (train.zip 4.76 GB → 4,167 plans) delegated,
derivation via slurm.

## 2026-07-14 — D-014: THE PIVOT — six Tesseract-native tiers T0–T5, raster-first, stage-gated

**Context.** User course-correction: the project thesis is that floorplans are
deliberately engineered encodings (crowding, thermal behavior, restricted access,
egress logic are put INTO the drawing by convention) whose information is present but
not bioavailable to models; graph tiers progressively unlock it. Therefore every tier
must be DERIVED FROM THE RASTER through one real pipeline (Tesseract2 as engine), not
assembled from datasets that ship graphs. Prior R0–R4 construction (morphology-first,
dataset-direct loaders as tier factories) violated this and is superseded.

**The six tiers (schema v2, levels 0–5):**
  T0 skeleton: rooms + corridor-main + transition spaces, untyped, centroids kept;
     undirected connectivity (rooms hang off corridor mains). FREE (forget of T2).
  T1 named spaces: + node kinds (room/corridor/transition) + CRAFT text labels. FREE.
  T2 Tesseract full structure: + door NODES with subtypes (r2r/r2c/c2c/exit). FREE.
  T3 geometry-enriched: + measured node attrs (area, eq_radius, inradius, subnode
     count, door count). FREE (Tesseract's own measurements surfaced).
  T4 access control: + door directionality/restriction (delta). MANUAL (timed).
  T5 organization: + zone/wing containment forest + outdoor marking. MANUAL (timed).
Hot/crowded/thermal annotations are PREDICTION TARGETS and oracle-skyline material
only — never representation content. Manual annotation tool = future TODO.

**Stage gate.** Build T0–T3 at corpus scale (thousands of ACCURATE graphs, user-
inspectable), run the probing grid on the four free tiers; only if an increasing
information ordering is established do we invest manual hours in T4/T5.

**Consequences.** Schema v2 (levels 0–5, 'transition' space kind, doors-as-nodes,
numeric attrs at 3+, delta at 4+, containment at 5); forgetting maps rewritten;
old modules migrate or are explicitly quarantined pending migration (msd loader,
synthetic calibration ladder, featurization). Results tree rebuilt as
results/corpora/<dataset>/<building>/{source.png,tiers/,overlays/,report.md}.
Textless-raster lane (RoomFormer-class pseudo-labels -> Tesseract) is the scale
path; MSD gets a render-to-raster lane so pipeline output can be validated against
its shipped ground truth. Estimator/stats/probe machinery unchanged (representation-
agnostic; calibration re-run on the new ladder is required before tier claims).

## 2026-07-14 — D-015: Textless lane = CubiCasa segmentation first (RoomFormer-class is a modality mismatch); MSD render lane adopted with documented door limitation

**Context.** Scout survey (docs/scout_reports/textless_lane_2026-07-14.md): the
RoomFormer/PolyRoom/CAGE/HEAT family consumes point-density images from 3D scans —
their pretrained weights do not transfer to raster floorplan DRAWINGS. The
modality-correct family for drawings is semantic segmentation; best candidate:
the CubiCasa5k model (PyTorch weights, room+door+window taxonomy). License flag:
CubiCasa data CC BY-NC-SA 4.0 — pin exact terms at integration.
**Decision.** Integrate CubiCasa first for pseudo-labels on textless rasters (P-6);
defer RoomFormer-class unless a 3D-scan corpus enters scope. Eval protocol: score
pseudo-labels against MSD ground truth (IoU-matched room F1 >= 0.8, type acc >= 0.7,
adjacency agreement) before corpus use.
**Render lane (P-3).** MSD renders (walls + room-type text + approximated opening
gaps) adopted for scale + validation of Tesseract's ROOM/TEXT stages. LIMITATION:
MSD ships doors only as edge attributes (no geometry/symbols), so gap-only renders
won't exercise the door R-CNN — next step renders synthetic door ARCS (CAD
convention) at the approximated openings; a single-plan end-to-end Tesseract test
gates the batch scale-up. Full train.zip (4.4 GB) retained in data/raw/msd for
corpus-scale rendering.
