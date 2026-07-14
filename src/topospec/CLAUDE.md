# topospec package — scoped norms

Implements the plan phase-by-phase. Module ↔ plan mapping:

| Module | Plan section | Role |
|---|---|---|
| `graphs/` | §4.1, App. B | R0–R4 schema, strict-refinement forgetting maps φ, validation, serializers (T5 toolkit artifact) |
| `data/synthetic.py` | §6 Phase A0 | planted-target families for instrument calibration |
| `data/{structured3d,cubicasa,msd,instbuild}.py` | §6 Phase A, §7 | corpus loaders → SpectrumGraph |
| `labels/` | §4.2 | Y_pde (exact PDE), Y_zone (RC/E+), Y_rank, Y_egress, Y_type, Y_ctrl |
| `probes/` | §8 | families V0–V7, fixed budgets, level-respecting featurization |
| `vinfo/` | §4.3 | I_V, conditional I_V (Hewitt 2021 construction), prequential MDL |
| `stats/` | §9 | bootstrap CIs, paired Wilcoxon + Holm, task-native metrics |
| `experiments/` | §6, §9 | configs, run manifests, append-only registry, grid runner |

## Invariants this package must never break

1. **Strict refinement (C1).** For every level k<4 and every graph g at level k+1:
   `forget(g, k)` is defined, deterministic, and idempotent
   (`forget(forget(g,k),k) == forget(g,k)`). Tests: `tests/test_levels.py`. Any new
   attribute added to a level MUST be handled by the forgetting map in the same commit.
2. **Interface enforcement.** `probes/featurize.py` is the ONLY place representation
   content becomes tensors. It must raise if asked for a feature the level doesn't carry
   (tau below R2, delta below R3, containment below R4). Never featurize inline elsewhere.
3. **Budget parity (plan §4.4).** Probe families expose `param_count(input_dim)`;
   `families.py` asserts identical budgets across levels for the same family. Training
   compute (epochs, batch, optimizer) is fixed per family in config, not per level.
4. **Everything seeded.** Public functions that use randomness take
   `rng: np.random.Generator` or `seed: int`. Torch code seeds from the same source.
5. **Nats.** All entropies/codelengths in natural log units. sklearn's `log_loss` is
   already ln-based; keep torch losses ln-based (default). Never mix log2 in.
6. **Estimates are lower bounds** (plan §8): I_V cells report best-of-k restarts across
   seeds; the estimator API returns all restarts, the registry stores all of them, and
   aggregation to best-of-k happens in analysis, transparently.

## Style

- Dataclasses for schema objects; pure functions for transforms; no hidden state.
- Docstrings cite the plan section implemented.
- Anything not yet implemented raises `NotImplementedError` with a pointer to its
  ROADMAP task ID — no silent stubs that return fake values. **Never return placeholder
  numbers from an unimplemented path.**
