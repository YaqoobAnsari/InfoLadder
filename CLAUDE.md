# T4 Representation Spectrum Study — Working Norms

Research codebase for an ICLR submission (deadline ~mid-September 2026; week 1 began
2026-07-14). The study measures usable information (predictive V-information + MDL)
across a nested spectrum of floorplan graph representations R0→R4, with an
annotation-cost axis, a capacity-compensation analysis, and a code-graph generality check.

**Authoritative plan:** `T4_spectrum_study_plan.md` (root). Read it before making design
decisions. It defines the claims (C1–C5), hypotheses (S1–S9), leakage analysis, fairness
constraints, statistical protocol, and phase gates. This file and the docs/ tree
operationalize it; the plan wins on any conflict — and if you find a conflict, record it
in `docs/DECISIONS.md` and surface it.

## Mission priorities (in order)

1. **Accuracy over speed; completeness over rash decisions.** Never trade correctness
   of an estimate, label, or statistic for wall-clock time. Prefer the holistic,
   well-considered route: when options exist (datasets, solvers, probe designs),
   explore and document the range before committing. Unavoidable shortcuts are
   recorded in `docs/DECISIONS.md` with consequences + a follow-up ROADMAP task.
2. **Comprehensiveness.** The deliverable is the FULL grid: all 5 levels × all targets ×
   all probe families × 3 seeds, with all baselines (controls, oracle skylines,
   betweenness reference) and all metrics (I_V, MDL codelength, task-native secondaries).
   Partial grids are intermediate states, never endpoints. If a cell is dropped, that is
   a scope decision the user must make — flag it, don't silently skip.
3. **Neat, visual documentation of results.** Every experiment phase ends with a
   written report + figures (curves, surfaces, tables) generated from the registry —
   under `results/reports/<phase>/`. Numbers without a plot and a paragraph of
   interpretation are unfinished work.
4. **External accountability.** All code and results are externally monitored and graded
   (independent review by Codex). Assume every number will be re-derived from artifacts
   and every line of code adversarially read. Reputation rides on reproducibility.

## Integrity (non-negotiable)

- **Never fabricate, extrapolate, or hand-edit results.** Every reported number traces to
  a run directory under `runs/<run_id>/` with a `manifest.json` (git SHA, config hash,
  seed, package versions) and a line in `results/registry.jsonl` (append-only).
- **Failed runs are reported as failed.** Log them in the registry with status=failed;
  do not delete or retry-until-green without recording each attempt.
- **Control tasks are hard constraints:** probe accuracy on Y_ctrl must be ≈ chance and
  Phase A0 calibration must pass before any real-data claim is stated (plan §6, §9).
- **Splits are building-level, never floor-level** (plan §9). Split assignment is
  computed once, hashed, and stored; probes never see test buildings.
- **Probes never peek past the level interface:** edge types only at R2+, direction only
  at R3+, containment only at R4 (plan §8). `topospec.probes.featurize` is the single
  enforcement point — all featurization goes through it.

## Environment

- Conda env: **topofield** — `/data1/yansari/.conda/envs/topofield/bin/python` (3.10).
  Use `make <target>` or that absolute path; never the system python.
- **We sit on the deepnet LOGIN NODE (no GPU, 10 cores). HARD RULE: no job runs on the
  login node.** All compute — probing grids, calibration, label generation, training,
  dataset processing — goes through slurm (`sbatch --mcs-label=$USER`, templates in
  `scripts/slurm/`). Login-node allowance: editing, git, `sinfo`/`squeue`, and
  `make verify`-scale checks (seconds). Full cluster map, GPU QOS caps, and the
  /data1-visibility trap (cpu partition CANNOT see our /data1): **docs/CLUSTER.md**.
- Keep all code device-agnostic (`torch.device` from config; probes are CPU-fine, Phase
  D uses an H200 MIG slice).
- Internet available on the login node. Datasets download into `data/raw/` only
  (gitignored), per `docs/DATA.md`.
- GitHub remote: https://github.com/YaqoobAnsari/InfoLadder (project working name:
  **InfoLadder**; package name stays `topospec`).

## Commands

```
make verify           # lint + fast tests — the bar every commit must clear
make test-all         # includes slow end-to-end probing tests
make calibrate-smoke  # 1-minute pipeline liveness check
make calibrate        # full Phase A0 instrument calibration
```

Experiments launch ONLY through configs: `topospec <cmd> --config configs/<file>.yaml`.
No ad-hoc hyperparameters on the command line; if you need a variant, write a config.

## Repo map & scoped norms

| Path | Contents | Scoped norms |
|---|---|---|
| `src/topospec/` | the package | `src/topospec/CLAUDE.md` |
| `data/` | corpora + labels (gitignored) | `data/CLAUDE.md` |
| `configs/`, `runs/`, `results/` | experiment I/O | `results/CLAUDE.md` |
| `paper/` | claims traceability, LaTeX | `paper/CLAUDE.md` |
| `docs/` | ROADMAP (tasks/gates), DECISIONS (ADR log), GLOSSARY, EXPERIMENT_PROTOCOL, DATA | — |

## Workflow

- **Pick work from `docs/ROADMAP.md`** in phase order; respect gate dependencies (the
  Week-1 Gate and Phase A0 calibration block everything downstream of them). Update task
  checkboxes and the STATUS block when you finish something.
- **Every non-obvious design choice** → one entry in `docs/DECISIONS.md` (dated, with
  alternatives considered). Especially: anything where the plan is ambiguous.
- **Tests first for invariants.** The refinement property (R_k recoverable from R_{k+1}
  via the forgetting map), schema validity, estimator sanity, and fairness constraints
  all have tests in `tests/`; extend them with every new level/target/probe. `make verify`
  must pass before every commit.
- **Seeds:** all randomness flows from the config's `seed`; grid cells use
  seed = base_seed + cell_index. No unseeded RNG anywhere.
- **Figures** are generated by scripts in `src/topospec/` or `scripts/` from registry
  data — never hand-assembled.
- Commit style: small, imperative subject, body says *why*. Never commit `data/`, `runs/`
  bulk artifacts, or edited results files.

## Writing code here

- Python 3.10, ruff-clean (`make lint`), type hints on public functions, docstrings that
  cite the plan section they implement (e.g. "plan §4.3").
- Numerical code: nats everywhere (natural log), float64 for estimator accumulations,
  explicit `rng: np.random.Generator` parameters — no global numpy seeding.
- Keep probe families cheap and honest: fixed parameter budgets per family across levels
  (plan §4.4); budget assertions live in `probes/families.py`.
