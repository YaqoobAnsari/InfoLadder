# Canonical entrypoints for the T4 spectrum study.
# ALL python invocations go through the topofield conda env — never the system python.
PY  := /data1/yansari/.conda/envs/topofield/bin/python
PIP := /data1/yansari/.conda/envs/topofield/bin/pip

.PHONY: setup install test test-all lint verify calibrate-smoke calibrate gate grid clean

setup:            ## install third-party deps into the topofield env
	bash scripts/setup_env.sh

install:          ## editable-install the topospec package
	$(PIP) install -e ".[dev]"

test:             ## fast test suite (excludes slow end-to-end probing tests)
	$(PY) -m pytest -m "not slow"

test-all:         ## full test suite including slow tests
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests

verify: lint test ## the pre-commit bar: lint + fast tests must pass

calibrate-smoke:  ## tiny end-to-end Phase A0 run (~1 min) — pipeline liveness check
	$(PY) -m topospec.cli calibrate --config configs/calibration_a0.yaml --smoke

# HARD RULE (docs/CLUSTER.md): real experiments never run on the login node.
# These targets SUBMIT slurm jobs; monitor with `squeue -u $$USER`.
calibrate:        ## full Phase A0 calibration — submits to slurm
	sbatch --mcs-label=morshed scripts/slurm/calibrate.sbatch

verify-cluster:   ## full test suite incl. slow tests, on a compute node
	sbatch --mcs-label=morshed scripts/slurm/verify.sbatch

gate:             ## Week-1 Gate experiments (requires data; see docs/ROADMAP.md)
	@echo "Gate runner not implemented yet (ROADMAP G-*); will submit via scripts/slurm/ when ready" && exit 1

grid:             ## Phase B probing grid — submits array job (requires corpus + labels)
	sbatch --mcs-label=morshed scripts/slurm/grid_array.sbatch

clean:
	rm -rf .pytest_cache .ruff_cache src/*.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
