---
name: verify
description: Project verification for the T4 spectrum repo — lint, tests, invariant checks, and a live end-to-end calibration smoke run. Run before committing any change to src/, configs/, or tests/.
---

# Verify — T4 spectrum repo

Run these in order from the repo root; ALL must pass. Python is always
`/data1/yansari/.conda/envs/topofield/bin/python` (the topofield env).

1. **Lint:** `make lint`
2. **Fast tests:** `make test` — includes the non-negotiable invariants:
   refinement/forgetting round-trips (test_levels), planted-target recovery sanity
   (test_synthetic), estimator sanity on known-information cases (test_vinfo),
   MDL behavior (test_mdl), PDE analytic solutions (test_pde), stats protocol
   (test_stats).
3. **Live pipeline check:** `make calibrate-smoke` — a tiny Phase-A0 run end-to-end
   (synthetic data → featurize → probes → I_V → manifest + registry). Verify it exits 0
   AND check its printed summary: the shuffled control must extract nothing (I_V <
   0.05 nats one-sided — negative values are overfit noise and fine) and the
   readable-level cell must beat the unreadable-level cell for the planted target.
   A smoke run writes to runs/ with `smoke: true`; that is expected.
4. **If you touched schema/levels code:** additionally run
   `make test-all` (includes slow probing tests).
5. **If you touched anything under `src/topospec/experiments/`:** confirm a dirty-tree
   registered run is refused (`tests/test_manifest.py` covers this; run it explicitly).

Do not hand-wave a failure as pre-existing: check `git stash` / `git log` to attribute
it, and report honestly either way. A change is verified only when all applicable steps
above pass on the final state of the working tree.
