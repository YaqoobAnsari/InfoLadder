# Phase A0 — instrument calibration report

**Verdict: FAIL ❌**

The measuring instrument (V-information probing protocol) is run on
synthetic buildings where each target is PLANTED at a known level.
It passes only if the measured usable information jumps exactly at the
planted level and shuffled controls extract nothing (plan §6 Phase A0).

| | |
|---|---|
| run_id | `20260714T021947Z-calibration_a0-s20260714` |
| git SHA | `2b738dfbc360` |
| config | `configs/calibration_a0.yaml` (sha256 `576a67a36af6…`) |
| seed | 20260714 |
| cells | 453 (0 failed) |
| host/job | deepnet2 |

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
| saturation | planted_degree · V4: I_V@R0 = 0.515 vs max below = 0.000 (margin 0.1) | PASS |
| saturation | planted_degree · V5: I_V@R0 = 0.516 vs max below = 0.000 (margin 0.1) | PASS |
| saturation | planted_tau · V2: I_V@R2 = 0.652 vs max below = 0.000 (margin 0.1) | PASS |
| saturation | planted_tau · V3: I_V@R2 = 0.652 vs max below = -0.002 (margin 0.1) | PASS |
| saturation | planted_tau · V4: I_V@R2 = 0.671 vs max below = -0.005 (margin 0.1) | PASS |
| saturation | planted_tau · V5: I_V@R2 = 0.671 vs max below = -0.005 (margin 0.1) | PASS |
| saturation | planted_delta · V2: I_V@R3 = 0.650 vs max below = -0.004 (margin 0.1) | PASS |
| saturation | planted_delta · V3: I_V@R3 = 0.650 vs max below = 0.000 (margin 0.1) | PASS |
| saturation | planted_delta · V4: I_V@R3 = 0.670 vs max below = -0.005 (margin 0.1) | PASS |
| saturation | planted_delta · V5: I_V@R3 = 0.670 vs max below = -0.006 (margin 0.1) | PASS |
| saturation | planted_zone · V0: I_V@R4 = 0.657 vs max below = 0.000 (margin 0.1) | PASS |
| saturation | planted_zone · V2: I_V@R4 = 0.653 vs max below = 0.001 (margin 0.1) | PASS |
| saturation | planted_zone · V3: I_V@R4 = 0.653 vs max below = -0.001 (margin 0.1) | PASS |
| saturation | planted_zone · V4: I_V@R4 = 0.657 vs max below = -0.082 (margin 0.1) | PASS |
| saturation | planted_zone · V5: I_V@R4 = 0.658 vs max below = -0.093 (margin 0.1) | PASS |
| control | control planted_tau_ctrl · V2 @R0: I_V = -0.001 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V2 @R1: I_V = -0.005 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V2 @R2: I_V = -0.002 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V2 @R3: I_V = -0.004 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V2 @R4: I_V = -0.007 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V3 @R0: I_V = -0.007 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V3 @R1: I_V = -0.012 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V3 @R2: I_V = -0.009 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V3 @R3: I_V = -0.011 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V3 @R4: I_V = -0.014 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V4 @R0: I_V = -0.009 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V4 @R1: I_V = -0.007 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V4 @R2: I_V = -0.001 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V4 @R3: I_V = -0.003 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V4 @R4: I_V = -0.005 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V5 @R0: I_V = -0.004 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V5 @R1: I_V = -0.001 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V5 @R2: I_V = +0.005 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V5 @R3: I_V = -0.004 (< tol, one-sided) | PASS |
| control | control planted_tau_ctrl · V5 @R4: I_V = -0.004 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V2 @R0: I_V = -0.002 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V2 @R1: I_V = -0.001 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V2 @R2: I_V = -0.004 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V2 @R3: I_V = -0.004 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V2 @R4: I_V = +0.115 (< tol, one-sided) | FAIL |
| control | control planted_zone_ctrl · V3 @R0: I_V = -0.003 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V3 @R1: I_V = -0.003 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V3 @R2: I_V = -0.005 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V3 @R3: I_V = -0.005 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V3 @R4: I_V = +0.114 (< tol, one-sided) | FAIL |
| control | control planted_zone_ctrl · V4 @R0: I_V = -0.119 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V4 @R1: I_V = -0.134 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V4 @R2: I_V = -0.099 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V4 @R3: I_V = -0.104 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V4 @R4: I_V = +0.028 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V5 @R0: I_V = -0.158 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V5 @R1: I_V = -0.135 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V5 @R2: I_V = -0.113 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V5 @R3: I_V = -0.131 (< tol, one-sided) | PASS |
| control | control planted_zone_ctrl · V5 @R4: I_V = +0.033 (< tol, one-sided) | PASS |

_Regenerate with `scripts/make_reports.py` — figures are derived from the
run's cell records; nothing here is hand-entered._
