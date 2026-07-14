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

calibrate:        ## full Phase A0 instrument calibration on synthetic planted targets
	$(PY) -m topospec.cli calibrate --config configs/calibration_a0.yaml

gate:             ## Week-1 Gate experiments (requires data; see docs/ROADMAP.md)
	$(PY) -m topospec.cli gate --config configs/gate.yaml

grid:             ## Phase B probing grid (requires corpus + labels)
	$(PY) -m topospec.cli grid --config configs/grid_phase_b.yaml

clean:
	rm -rf .pytest_cache .ruff_cache src/*.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
