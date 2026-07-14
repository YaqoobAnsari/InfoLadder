# T4 — The Representation Spectrum Study
## How Much Structure Does Physical Inference Need? Measuring Usable Information Across Floorplan Graph Representations

**Target venue:** ICLR (deadline ~mid-September, ≈2 months)
**Document status:** Standalone finalized plan for the T4 thread. Companion to the TopoField program; supersedes the spectrum sections of earlier documents.

---

# TABLE OF CONTENTS

1. Executive Summary and Claims
2. Research Gap Analysis (four audit lanes)
3. Literature Review
4. Formal Problem Setup — the Spectrum, the Targets, the Measure
5. The Leakage Analysis (stated before reviewers state it)
6. Methodology, Phase by Phase
7. Data Strategy and Budget
8. Probe and Model Families
9. Metrics and Statistical Protocol
10. Hypotheses
11. Venue Fit
12. Risk Register
13. Timeline (8 working weeks)
14. Open Questions
15. Appendix A: Citation-Safety Table
16. Appendix B: Representation Level Specifications

---

# 1. EXECUTIVE SUMMARY AND CLAIMS

**The question.** Graph representations of buildings range from bare room connectivity to full functional hierarchy. Nobody knows which structural content downstream physical inference actually needs. Annotation effort is therefore spent blind, and architectures are chosen by habit. We measure, for the first time, how much *usable information* about physical building properties each level of representational richness carries.

**The claims.**

**C1 (Spectrum).** A formalized five-level spectrum of floorplan graph representations, R0 (rooms + undirected connectivity) through R4 (typed, directed, hierarchically organized — the HDG), where each level is a strict refinement of the previous and each increment has a defined annotation cost.

**C2 (Measurement protocol — the methodological novelty).** The first application of usable-information measurement (predictive V-information, complemented by MDL probing) to *input representation levels of a structured data format*, rather than to learned model embeddings. The protocol quantifies, per task, how much information a bounded predictor family can extract from each level.

**C3 (Annotation economics).** The *annotation gain*: usable information purchased per human annotation hour, per level increment, per task. No such quantity has been reported for any structured data domain.

**C4 (The empirical answer).** Information–richness curves for thermal zoning, temperature ordering, egress structure, and an analytically defined diffusion target (a PDE solved on true geometry — mathematically exact ground truth, immune to simulator-validity objections), with a capacity-compensation analysis (can bigger models on poor representations match small models on rich ones, and at what sample cost) and a scale analysis (residential vs institutional regimes).

**C5 (Generality).** The framework demonstrated on a second structured domain with auto-derivable nested levels — code property graphs (AST → +dataflow → +call graph) on established datasets — showing the protocol is domain-general. Buildings carry the annotation-cost axis; code carries the generality check. Deliberately compact: one task, one figure, one section.

**Artifact.** The spectrum toolkit (thread T5): one converter from floorplan to any level, schema-validated, serializable to IFC spatial structure and IndoorGML (the standards hook).

**What this work deliberately does NOT claim.** Not a new probing method (we apply Xu et al.'s framework); not a new GNN architecture (encoders are instruments, not contributions); not physical field inference as a deployed capability (that is thread T6, gated on this study's answer).

---

# 2. RESEARCH GAP ANALYSIS

## Lane 1 — Probing and usable information

**Found.** The framework is mature and proliferating: predictive V-information (Xu et al., ICLR 2020) formalizes information extractable by a bounded predictor family, with the key property that *processing can increase usable information* (unlike Shannon MI under the data-processing inequality). Kleinman et al. (2021) track usable information in network layers during training. Voita & Titov (EMNLP 2020) contribute MDL probing (codelength folds probe effort into the score). Hewitt & Liang (EMNLP 2019) contribute control tasks. Ethayarajh et al. (ICML 2022) apply V-usable information to *dataset difficulty*. **Round-3 audit additions — the two closest relatives found across all audits:** (a) *Data Checklist* (2024) unit-tests NLP datasets by comparing I_V across feature transformations Φ(X), explicitly noting that features "can only make existing information more usable" — the formal move of comparing usable information across input transformations is therefore published; (b) Hewitt et al. (2021) define **conditional / multivariable V-information** — information beyond a baseline input — since adopted by rationale-evaluation (RORA) and rater-modeling work. Further 2025–26 applications (hallucination detection, task-specific image quality under sub-ideal observer families, steganography monitoring, adversarial-dataset measurement) confirm the tool is trusted and active.

**Boundary.** Every application measures learned embeddings, whole datasets, flat feature transformations, or image quality of a fixed modality. None measures *nested structural refinement levels of a representation format*, none attaches an annotation-cost axis, none sweeps probe capacity as a primary experimental dimension, and none touches graphs or spatial data. Data Checklist compares diagnostic feature functions for dataset debugging; we compare a cost-ordered refinement ladder for representation selection. The conditional V-information formalism is adopted, not invented (§4.3).

**Verdict.** Framework established (we cite, not invent); application unclaimed (that is the contribution). The strongest positioning available at ICLR: a trusted tool aimed at a new object.

## Lane 2 — Probing graph representations specifically

**Found.** Akhondzadeh et al. (2023) probe learned GNN embeddings on molecular data, showing graph transformers capture more chemically relevant information than message passing. GraphProbe (2024) benchmarks node-, path-, and structure-level probes across nine graph learners.

**Boundary.** Both probe *model* representations to interpret trained networks. The independent variable in our study is the *data* representation; models are held fixed as instruments. No overlap in question, only in machinery.

## Lane 2b — The "does graph structure help" literature (round-3 addition; the graph-community reviewer's citation)

**Found.** A developed line asks when message passing beats graph-agnostic models: the homophily principle and node-distinguishability analysis (Luan et al., NeurIPS 2023), adjusted homophily and *label informativeness* as structural descriptors (Platonov et al., 2023), an iff-characterization that geometry-aware gains are possible exactly when structure carries label-relevant information beyond features (2026), diagnostic studies showing structure alone can suffice under high homophily and can *hurt* when homophily is low and features are strong (2025), and the structure-learning critique line showing GCN+GSL can be bounded by MLPs on the same bases (2024).

**Boundary.** This literature answers a binary question about a *given* graph — use its structure or ignore it — diagnosed through homophily-family statistics at the Shannon/descriptor level, almost entirely on citation-style node classification. Our axis is orthogonal: not whether to use a given graph, but *which refinement level of structure to construct*, under explicit annotation cost, measured by capacity-bounded extraction. Their iff-characterizations answer whether extra label-relevant information *exists*; V-information measures whether bounded models can *access* it, per level, per price.

**Imported, not just differentiated.** Their finding that structure can hurt when it is noisy relative to features directly motivates our hypothesis S9: under bounded probe capacity, richness need not be monotone — added structure can distract small predictors. Their results make S9 plausible; our protocol makes it measurable on a cost-ordered ladder.

## Lane 3 — Floorplan representations and physical inference

**Found (from the standing TopoField audits, re-verified).** Floorplan graph work (Graph2Plan, room-classification GNNs, MSD) uses flat graphs for generation and labeling; hierarchical 3D scene graphs (Hydra lineage) come from sensor streams with geometric hierarchies; zero-sensor physical inference from structure does not exist in CV/ML or building science; thermal/HVAC ML requires operational data at inference.

**Verdict.** No prior work measures what building representations carry, and no prior work performs the inference the measurements are aimed at. Both ends open.

## Lane 4 — The theory that predicts the answer's direction

Oversquashing and oversmoothing (Alon & Yahav 2021; Topping et al. 2022; Li et al. 2018) predict flat graphs lose *accessible* signal at institutional scale; hierarchical message passing (HGNet 2021: logarithmic path guarantees) predicts hierarchy restores access; directionality results (Dir-GNN 2023; directed-GNN survey 2024) predict symmetrization destroys expressiveness. The theory licenses direction-of-effect expectations; it cannot predict effect sizes for this domain. That gap between licensed direction and unknown magnitude is exactly what the study fills.

## Lane 5 — The harsh adjacency scan (2026 additions; the findings that force the repositioning)

**Adverse finding: the *observation* is folklore.** A May 2026 benchmark jointly evaluates knowledge-graph construction methods by downstream GNN performance against an expert reference graph — the closest structural relative to this study, in the biomedical domain. Code-graph papers routinely ablate node/edge types within-paper (IRGraph lineage). Crystal-GNN and fMRI-GNN literatures carry scattered construction-choice observations. FMLM (April 2026) argues suboptimal representations are why floorplan generation fails to generalize. Pitching this paper as "representation content matters" is therefore dead on arrival — reviewers have seen the observation.

**Boundary — verified unclaimed across all fragments:** none of these works has a *nested refinement spectrum*, none formalizes the question as usable information under bounded predictors, none sweeps probe capacity, none attaches an annotation-cost axis, and none reports information-per-annotation-hour. The KG benchmark compares alternative graphs, not strict refinements; the ablations are ad-hoc robustness checks, not a measurement protocol.

**Supporting finds.** FloorplanQA (2026, ICLR-workshop-visible) probes LLM reasoning over structured floorplan inputs, and FML treats representation as generation's bottleneck — the topic area is warming at exactly the target venue while the formalized question stays open. Practical discovery: **MSD ships per-room zone labels** on 5,372 public multi-unit plans — an auto-derivable near-R4 richness level at zero annotation cost (folded into Phase A).

**Verdict.** Gap confirmed, framing corrected: the spine is the measurement framework with cost semantics, never the observation. The fragments above become cited relatives in the differentiation table.

## Consolidated gap statement

> "Representation content matters" is community folklore — within-paper ablations, domain observations, and one fresh construction benchmark all attest to it. What has never existed, in any domain: a nested refinement spectrum of input representations, measured under a formal usable-information protocol with probe-capacity sweeps, tied to the annotation cost of each refinement, and tested across scale regimes. Usable-information measurement itself has never been applied to representation levels of a structured input, never tied to annotation cost, and never used on spatial data. This study contributes that framework, answers it for buildings (with cost economics) and for code graphs (generality), and reports the first information-per-annotation-hour figures in the literature.

---

# 3. LITERATURE REVIEW

**3.1 Usable information and probing.** Xu et al. (ICLR 2020): predictive V-information, definitions, PAC bounds, the DPI-violation property. Ethayarajh et al. (ICML 2022): pointwise V-information for dataset difficulty. Kleinman et al. (2021): usable information across layers/training. Voita & Titov (2020): MDL probes. Hewitt & Liang (2019): control tasks and probe selectivity. Alain & Bengio (2017): linear probes origin. Pimentel et al. (2020): information-theoretic critique of probing — we adopt their caution (report probe capacity sweeps, never a single probe).

**3.2 Graph probing.** Akhondzadeh et al. (2023); GraphProbe (2024). Machinery adopted; question orthogonal (§2 Lane 2).

**3.3 Floorplan graph representations.** Tesseract (SIGSPATIAL 2025): rooms/doors/corridors navigable graphs — our R1, and our own lineage. Chen & Stouffs (2022): typed adjacency — the R2 mechanism. Raster-to-Graph (EG 2024): structural graph extraction. Graph2Plan / HouseGAN++ / HouseDiffusion: flat bubble conditioning. MSD (ECCV 2024): multi-unit complexity precedent. 3DSG/Hydra/HOV-SG: containment+peer hierarchical pattern from sensors — convergent validation for R4's design, disjoint input modality.

**3.4 Physical labels infrastructure.** EnergyPlus + bim2sim (IFC lane); RC-network thermal surrogates (validated against EnergyPlus on a subset); JuPedSim/Vadere for egress traces; betweenness as the zeroth-order egress theory.

**3.5 Theory.** Oversquashing/oversmoothing corpus; HGNet; HC-GNN; Dir-GNN; directed expressiveness survey. Roles as in §2 Lane 4.

---

# 4. FORMAL PROBLEM SETUP

## 4.1 The spectrum as nested functions of the plan

Let P be a floorplan (the underlying source). Each level is a deterministic extraction R_k = f_k(P), constructed so that R_{k+1} strictly refines R_k (R_k is recoverable from R_{k+1} by forgetting structure):

```
R0 = (V_room, E_conn)                      rooms, undirected connectivity
R1 = R0 + door/corridor nodes + node semantics        (Tesseract level)
R2 = R1 + edge types tau in {wall, door, corridor-link}
R3 = R2 + access direction delta on the controlled subset
R4 = R3 + containment forest E_c over levels {room, corridor-cluster, zone, wing}
       + zone/wing node attributes                    (the HDG)
```

Annotation cost c(k→k+1) per building: c(0..2) ≈ 0 (automatic), c(2→3) ≈ 0.5–1 h, c(3→4) ≈ 1–2 h (from the standing Phase-Zero estimates; re-measured in this study's Gate experiment).

## 4.2 Targets

- Y_zone: simulator-derived thermal zone assignment per room (EnergyPlus or validated RC surrogate)
- Y_pde: an analytically defined diffusion field — steady-state heat equation solved by a standard PDE solver on the *true floor geometry* with fixed boundary conditions, discretized to per-room means and ranks. Ground truth is mathematically exact; no simulator-validity or circularity objection can attach to it. This is the cleanest target in the study and the anchor for all cross-target consistency checks
- Y_rank: pairwise room temperature ordering
- Y_egress: bottleneck membership of corridor nodes (top-k congestion in evacuation simulation); plus raw betweenness as a graph-theoretic reference target
- Y_type: room type — a *positive control* (should be readable at R1+)
- Y_ctrl: shuffled-label control task (Hewitt–Liang) — probes must fail here, or they measure memorization

## 4.3 The measure

For predictor family V, predictive conditional V-entropy H_V(Y|X) = inf over f in V of expected log-loss; usable information I_V(X→Y) = H_V(Y) − H_V(Y|X). Estimated directly by training the probe and evaluating held-out cross-entropy.

**The coarsening frame (round-3 formal upgrade).** Because the levels are nested, every level is a deterministic coarsening of the richest one: R_k = φ_k(R4). The study is therefore *V-information under structured coarsening* — precisely the "processing" setting in which the framework permits usable information to rise or fall while Shannon information cannot rise. The formal statement of the central claim: the refinements f_3, f_4 (annotation) increase I_V for physical targets — computation applied in advance, surfacing buried structure.

**Proposition 1 (monotonicity under closure; short proof in appendix).** If the probe family V is closed under composition with the forgetting map φ (i.e., for every f ∈ V, f∘φ ∈ V), then I_V(R_{k+1}→Y) ≥ I_V(R_k→Y): richer input cannot hurt a family that can simulate forgetting. When closure fails — bounded probes cannot cheaply ignore added structure — non-monotonicity becomes possible. This turns "does more structure ever hurt?" from anecdote (documented in the homophily literature, Lane 2b) into a testable prediction about *which probe families* show dips (hypothesis S9).

**Annotation gain, properly defined (round-3 formal upgrade).** Rather than a difference of two independently estimated lower bounds, the gain of a refinement is measured as **conditional V-information** (Hewitt et al., 2021): I_V(ΔR_{k+1} → Y | R_k) — the information the added structure carries about Y *beyond* what the coarser level already provides, estimated by probes given both inputs versus the coarser input alone. This is the established "information beyond a baseline" construction, is less noise-sensitive than differencing, and is the quantity paired with the measured annotation cost c(k→k+1).

MDL codelength is reported alongside as the probe-effort-sensitive complement throughout.

## 4.4 Fairness constraints

Representations differ in size (R4 has more nodes/attributes). Rules: fixed probe parameter budgets per family across levels; identical training compute; identical splits; input dimensionality documented per level; results reported as capacity sweeps, never single probes (Pimentel caution).

---

# 5. THE LEAKAGE ANALYSIS

Reviewers will ask: R4 contains annotated functional zones; for Y_zone, is the probe just reading the answer? Three-part answer, stated in the paper before review:

1. **Partial leakage is the hypothesis, not a bug.** The claim is precisely that annotation surfaces buried information. What must be shown is that the surfaced structure predicts a *different* quantity than itself.
2. **Functional ≠ physical zoning.** R4's zones are architectural/functional annotations (wards, departments); Y_zone is simulator-derived HVAC/thermal grouping. Correlated, not identical; the measured correlation is the finding. We report the annotation–target agreement (ARI between R4 zones and Y_zone) explicitly, and the probe's *excess* performance beyond that agreement.
3. **Two targets are leakage-free by construction.** Y_rank and Y_egress appear in no representation at any level. If the R-curves for these targets show the same ordering as Y_zone, the leakage objection cannot explain the result.

---

# 6. METHODOLOGY, PHASE BY PHASE

**Gate (Week 1). Feasibility triple.** (a) RC-surrogate validation: fit the RC-network thermal model on 3 IFC-lane buildings, compare zone/rank labels against full EnergyPlus; proceed if label agreement ARI > 0.7. (b) One institutional building annotated R0→R4, timed; proceed if ≤4 h. (c) Probe pipeline smoke test on 50 Structured3D scenes end-to-end. Any gate failure triggers scope reduction (fewer targets, or residential-only with institutional as case study), not schedule slip.

**Phase A0 (Week 1–2, alongside the Gate). Instrument calibration on synthetic ground truth (round-3 addition).** Construct synthetic graph families where the target is *planted at a known level by design*: one target computable exactly from edge types but invariant to connectivity; one computable only from containment membership; one from direction alone. Run the full probing protocol. The instrument passes calibration only if it recovers each planted saturation level. This converts the estimator from an article of faith into a validated instrument before any real-data claim is made — and doubles as Figure 2 of the paper.

**Phase A (Weeks 1–3). Corpus.** Auto-derive R0–R2 for Structured3D (3.5K scenes), CubiCasa5K, MSD (silver corpus, ~130K room nodes); exploit MSD's shipped per-room zone labels to auto-derive a near-R4 level on 5,372 plans at zero annotation cost (the timeline de-risk from the Lane-5 audit); run the label pipeline (PDE solver for Y_pde everywhere geometry permits; RC surrogate everywhere; EnergyPlus on the IFC subset; egress simulation on a stratified sample plus betweenness everywhere). Annotate 5–10 InstBuild buildings to R4 (the institutional stress set). Toolkit hardened as the byproduct; IFC/IndoorGML serializers included.

**Phase A2 (Weeks 2–4, parallel, capped). Second domain.** Code property graphs on an established dataset: derive the level ladder automatically (AST-only → +dataflow edges → +call-graph edges), pick one standard prediction target, run the identical probing grid. Hard cap: one task, one figure, one week of one person's time — the generality check must never compete with the primary domain for resources.

**Phase B (Weeks 3–5). Probing campaign.** Full grid: {R0..R4} × {targets} × {probe families} × {3 seeds}. Control tasks throughout. Primary deliverable: the usable-information surface.

**Phase C (Weeks 5–6). Capacity and sample-efficiency analysis.** Vary probe capacity and training-set size; measure whether and at what sample cost large-V-on-R0 matches small-V-on-R4. Annotation-gain computation: ΔI_V per level paired with measured c(k→k+1).

**Phase D (Weeks 6–7). Transformer confirmation.** One graph transformer encoder (level as config flag, identical budgets) fine-tuned per level per task — does full training preserve the probe ordering? Includes the geometric-hierarchy control (Hydra-style floors-only R4 variant) to separate "hierarchy" from "functional hierarchy."

**Phase E (Weeks 7–8). Writing, figures, release.** Toolkit + graphs + label-generation code packaged; internal red-team against Appendix A.

---

# 7. DATA STRATEGY AND BUDGET

| Quantity | Value | Notes |
|---|---|---|
| Silver room nodes (R0–R2, auto) | ~130,000 | Structured3D ~20K, CubiCasa ~25K, MSD ~85K |
| Silver labels | all of the above | RC surrogate (validated); egress on stratified sample |
| Gold institutional buildings (to R4) | 5–10 | the stress set; ≤4 h each ⇒ ≤40 h total annotation |
| Directed-edge instances | ≥100 across gold set | class-balance check at the Gate |
| Probe runs | ≈ 5 levels × 5 targets × 6 families × 3 seeds ≈ 450 | each minutes-to-tens-of-minutes; single GPU |
| Transformer runs (Phase D) | ≈ 5 × 3 tasks × 3 seeds = 45 | small models (≤8M params), hours each |

The two-month feasibility rests on two facts: R0–R2 require zero annotation, and probes are cheap. The expensive objects (institutional R4 annotations) are capped at ten buildings, and their scarcity is methodologically fine — they serve as the out-of-regime stress evaluation, not the training corpus.

---

# 8. PROBE AND MODEL FAMILIES

Ordered by capacity (the V sweep): (V0) **parameter-free readout** where the level permits it — for Y_zone at R4, directly reading the zone attribute is a zero-parameter probe, the cleanest possible demonstration that richness converts a learning problem into a lookup; (V1) predict-from-prior; (V2) linear on raw node attributes; (V3) linear on attributes + spectral/positional encodings; (V4) 1-layer GNN; (V5) 2-layer GNN; (V6) 4-layer GraphGPS-style transformer (≤2M params); (V7, optional appendix tier) **frozen small language model** consuming each level serialized as JSON, with a linear readout — one row that pre-empts the inevitable "why not an LLM" question and connects to the emerging LLM-over-structured-floorplan thread (FloorplanQA). Edge-type and direction consumption switched on only where the level provides them (the representation defines the interface; probes never peek past it).

**Bounds, per the Belinkov prescriptions.** Every curve is sandwiched: a random/shuffled-label floor below (control tasks) and an **oracle skyline** above — the same probe families run on hand-constructed oracle features containing the target-relevant structure explicitly. Curves are interpretable only relative to both bounds. **Optimization robustness:** every I_V estimate is a lower bound achieved by optimization, so each cell reports best-of-k restarts across 3 seeds, and prequential (online) MDL codelength is reported alongside as the optimization-robust complement. **Scoping statement (written into the paper):** this study measures *extractability*, which is exactly the quantity representation selection needs — the standard "presence does not imply usage" critique of probing is out of scope by construction. Phase-D encoder: the hierarchical heterogeneous graph transformer from the TopoField plan, plus flat GraphGPS and HGT as instrument controls.

---

# 9. METRICS AND STATISTICAL PROTOCOL

**Primary:** I_V(R_k→Y) via held-out cross-entropy (nats), per cell of the grid; MDL codelength as complement. **Derived:** annotation gain ΔI_V/Δc (nats per hour); capacity-compensation gap; sample-efficiency slopes. **Task-native secondaries:** ARI/NMI (zones), Spearman (rank), precision@k (egress), macro-F1 (type). **Validity:** control-task selectivity (probe accuracy on Y_ctrl must be ≈ chance); R4-zone/Y_zone agreement reported per §5. **Statistics:** 3 seeds; building-level splits (never floor-level); bootstrap 95% CIs on all I_V estimates; paired Wilcoxon across buildings for level comparisons, Holm-corrected across the level family; all raw grids released.

---

# 10. HYPOTHESES

| # | Hypothesis | Test | Risk |
|---|---|---|---|
| S1 | I_V increases monotonically with level for physical targets, and is flat for Y_ctrl | main grid | Low–Med |
| S2 | Saturation is task-dependent: Y_zone gains most at R4; Y_egress saturates by R2–R3 | per-task curves | Med — the most interesting cell |
| S3 | Capacity compensation is partial: V6-on-R0 does not reach V2-on-R4 for Y_zone at matched samples; closing the gap costs ≥5× data | Phase C | Med |
| S4 | Scale dependence: annotation gain for R3/R4 is near zero on residential plans and large on institutional plans | residential vs stress set | Med — the headline if it holds |
| S5 | Phase-D transformers preserve the probe ordering | Phase D | Low |
| S6 | Functional hierarchy beats geometric-only hierarchy (floors-only R4 variant) on Y_zone | Phase D control | Med |

| S7 | The framework transfers: the code-graph ladder shows the same qualitative pattern (monotone gain for structure-dependent targets, task-dependent saturation) | Phase A2 grid | Med |
| S8 | Y_pde and Y_zone curves agree in ordering — the analytic target certifies the simulator-derived one | cross-target consistency | Low–Med |
| S9 | Non-monotonicity exists: for small probe families (V2–V4), added structure produces measurable dips at some level–task cells, vanishing as capacity grows (Proposition 1's closure condition kicks in) | main grid, stratified by V | Med — a finding either way, and a genuinely ICLR-flavored one |

S4 deserves emphasis: if richness only pays off at institutional scale, the study simultaneously explains why the field never noticed the need (its benchmarks are residential) and quantifies exactly when the annotation investment is rational. S7 is what converts a domain study into a framework paper; S8 is what makes the simulator objection unanswerable.

---

# 11. VENUE FIT

ICLR-native on every axis: a formal information-theoretic tool the venue introduced (V-information is an ICLR 2020 paper), a falsifiable representation-learning question, an ablation-native design, curves rather than leaderboard deltas, and theory-guided expectations (oversquashing, directionality) tested empirically — now including one small formal contribution of our own (Proposition 1 and its empirically testable failure mode, S9). No vision component is needed to justify the paper.

**Genre discipline (round-3 addition).** ICLR has no datasets-and-benchmarks track: the paper must be a *findings and methodology* paper, never a benchmark paper. InstBuild annotations and the toolkit are artifacts in the appendix; the contributions are the framework, the calibrated instrument (Phase A0), the curves, and the propositions.

**The headline framing (round-3 addition).** Three currencies purchase the same nats: *structure* (annotation hours), *capacity* (probe compute), and *samples* (training data). The capacity-compensation and sample-efficiency analyses price the exchange rates between them — "annotation is computation done in advance" made quantitative. This connects the paper to the scaling-tradeoffs discourse the venue is currently absorbed by, without overclaiming a scaling law. Suggested framework name for memorability: **Structural Information Profiles** (a representation's I_V-vs-refinement curve per task, per capacity).

The dataset-difficulty lineage (Ethayarajh, ICML) and the 2024–26 proliferation of V-information applications show measurement-of-data papers clear top venues when the protocol is rigorous; the calibrated-instrument phase and conditional-V-information formalization are what push this from "applies a known tool" to "builds a validated measurement method."

---

# 12. RISK REGISTER

| Risk | P | Impact | Mitigation |
|---|---|---|---|
| Flat result (levels indistinguishable) | Low–Med | headline loss | S4's scale split is the likely saver; a genuinely flat result on institutional data is itself a strong negative finding — commit to publishing it |
| Leakage objection dominates review | Med | credibility | §5 written into the paper; leakage-free targets carry the claim |
| RC surrogate labels too coarse | Med | label validity | Gate (a); EnergyPlus subset comparison reported; sensitivity analysis |
| Probe-choice criticism | Med | methods | full capacity sweep + MDL + controls (Pimentel-proofed) |
| Two-month clock | High | scope | gates trigger scope cuts, not slips; residential-only fallback pre-declared |
| Someone publishes similar probing on spatial data first | Low | novelty | none found in three audits; speed is the defense |
| Paper read as "construction matters" folklore | High if mis-pitched | rejection | repositioned spine (Lane 5): the framework with cost semantics is the claim; KG benchmark, FMLM, and ablation folklore cited as relatives lacking the measure |
| The lane is warming (KG benchmark May 2026; FMLM Apr 2026; FloorplanQA) | Med | first-mover erosion | two-month clock is now an asset; the formalized protocol + cost axis + two domains is a moat fragments cannot assemble quickly |
| Second domain dilutes focus | Med | depth | Phase A2 hard cap: one task, one figure, one person-week; cut entirely at the Week-4 checkpoint if primary domain slips |

---

# 13. TIMELINE (8 WORKING WEEKS)

W1 Gate triple + corpus derivation starts. W2–3 Phase A complete (silver labels done, gold annotations done). W3–5 Phase B probing grid. W5–6 Phase C capacity/sample analysis. W6–7 Phase D transformer confirmation. W7–8 writing, release packaging, red-team, submit.

---

# 14. OPEN QUESTIONS

1. Which 5–10 institutional buildings, and in which formats (drives Gate (b))?
2. Compute quota (the 450-run grid parallelizes trivially — how many GPUs)?
3. Annotator availability for ≤40 hours in weeks 1–3?
4. Does the group want egress labels from JuPedSim (heavier, more credible) or betweenness+capacity heuristics (lighter) for the ICLR cut?
5. Author-order and thread ownership across T4/T5.

---

# 15. APPENDIX A — CITATION-SAFETY TABLE

| Work | Cite because | Differentiation |
|---|---|---|
| Xu et al. ICLR 2020 | the measure | we apply to input representation levels, new object |
| Hewitt et al. 2021 (conditional V-information); RORA; Value Profiles | the "information beyond a baseline" formalism | adopted for annotation gain; their applications are NLP rationales and rater modeling |
| Data Checklist (2024) | compares I_V across feature transformations of inputs — closest methodological relative | dataset unit-testing with diagnostic features; ours is a cost-ordered structural refinement ladder for representation selection |
| Observer-Usable Information (2025–26) | V-info as task-specific input-quality metric under sub-ideal observers | image quality of a fixed modality; no refinement levels, no cost axis |
| Luan et al. 2023; Platonov et al. 2023; ASEHybrid 2026; GCN diagnostic 2025; GSL critique 2024 | the "does structure help" line a graph reviewer will cite | binary use-vs-ignore of a given graph via homophily descriptors; our axis is which level to construct, cost-aware, capacity-swept; their structure-can-hurt finding motivates S9 |
| MI-based feature selection (mRMR lineage) | classical information-driven input selection | Shannon-estimate feature subsets; no capacity dimension, no structural nesting, no construction cost |
| Ethayarajh ICML 2022 | closest relative (data-side V-info) | dataset difficulty vs representation richness; no structure, no cost pairing |
| Voita & Titov; Hewitt & Liang; Pimentel | probing rigor | adopted as protocol components |
| Akhondzadeh 2023; GraphProbe 2024 | graph probing exists | they probe learned embeddings; we probe data representations |
| Tesseract; Chen & Stouffs; Raster-to-Graph | spectrum machinery | levels R1/R2 build on them, credited |
| Hydra/3DSG lineage | hierarchy pattern exists | sensor input, geometric hierarchy; our S6 control quantifies the difference |
| Oversquashing/HGNet/Dir-GNN corpus | direction-of-effect theory | we measure the magnitudes theory cannot predict |
| PINN/GNN-HVAC literature | adjacent physics ML | sensor-dependent; our targets are structure-only |
| KG-construction + GNN benchmark (2026) | closest structural relative | alternative graphs, not nested refinements; no information formalization, no capacity sweeps, no cost axis |
| IRGraph-style code-graph ablations | representation ablation folklore | ad-hoc within-paper checks; we supply the protocol they lack — and their level ladder becomes our second domain |
| FMLM (2026) | representation-as-bottleneck framing in floorplans | proposes one representation for generation; we measure a spectrum for inference |
| FloorplanQA (2026) | structured-floorplan inputs at ICLR-adjacent venues | LLM QA diagnostic; orthogonal question, cited as topic-area evidence |

# 16. APPENDIX B — REPRESENTATION LEVEL SPECIFICATIONS

Machine-checkable schema per level (toolkit-enforced): R0 node set with area/centroid attributes, undirected edge list. R1 adds node.kind in {room, door, corridor}, semantic label field. R2 adds edge.tau enum. R3 adds edge.delta enum, default bidirectional. R4 adds containment forest with level map L, zone/wing attribute blocks. Serializers: each level exports to JSON (native), R1+ to IndoorGML, R4 to IFC spatial structure with IfcZone groups. Validation CLI ships with the toolkit; the schema file is versioned and cited in the paper.
