# Phase A0 — instrument calibration report

**Verdict: PASS ✅** (smoke run — reduced grid)

The measuring instrument (V-information probing protocol) is run on
synthetic buildings where each target is PLANTED at a known level.
It passes only if the measured usable information jumps exactly at the
planted level and shuffled controls extract nothing (plan §6 Phase A0).

| | |
|---|---|
| run_id | `20260714T013229Z-calibration_a0-s20260714-smoke` |
| git SHA | `565240926555` |
| config | `configs/calibration_a0.yaml` (sha256 `576a67a36af6…`) |
| seed | 20260714 |
| cells | 19 (0 failed) |
| host/job | gpujobs |

## Calibration surface

![calibration surface](figures/calibration_surface.png)

Reading guide: each panel is one planted target; the dashed vertical line
marks where the answer was hidden. A correct instrument shows curves that
are ~flat at zero LEFT of the line and jump at/after it — for the families
capable of reading that structure (V2+ linear for attribute counts, V4/V5
GNNs for connectivity, V0 readout for the R4 zone attribute).

## Controls

![controls](figures/controls.png)

Negative values are harmless optimization noise; only values ABOVE the
dashed tolerance would indicate leakage/memorization.

## Checks

| check | detail | result |
|---|---|---|
| saturation | planted_tau · V2: I_V@R2 = 0.635 vs max below = -0.058 (margin 0.1) | PASS |
| saturation | planted_zone · V0: I_V@R4 = 0.731 vs max below = 0.000 (margin 0.1) | PASS |
| saturation | planted_zone · V2: I_V@R4 = 0.710 vs max below = -0.046 (margin 0.1) | PASS |
| control | control planted_tau_ctrl · V2 @R1: I_V = +0.017 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V2 @R2: I_V = +0.009 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V2 @R4: I_V = -0.010 (< tol, one-sided) | PASS |

_Regenerate with `scripts/make_reports.py` — figures are derived from the
run's cell records; nothing here is hand-entered._
