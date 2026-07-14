#!/usr/bin/env bash
# Install all T4-spectrum dependencies into the `topofield` conda env.
# Idempotent: safe to re-run. CPU-only host: torch comes from the CPU wheel index.
set -euo pipefail

PIP=/data1/yansari/.conda/envs/topofield/bin/pip

$PIP install --upgrade pip

# Scientific core
$PIP install numpy scipy pandas matplotlib seaborn scikit-learn statsmodels

# Graphs + geometry
$PIP install networkx shapely

# Config / schema / IO
$PIP install pyyaml jsonschema tqdm

# Torch (CPU wheels — this host has no GPU) + PyG (pure-python core is enough
# for the GCN/GraphGPS-scale probes; compiled extensions not required)
$PIP install torch --index-url https://download.pytorch.org/whl/cpu
$PIP install torch_geometric

# Dev tooling
$PIP install pytest pytest-cov ruff

echo "=== install complete ==="
/data1/yansari/.conda/envs/topofield/bin/python - <<'EOF'
import numpy, scipy, pandas, sklearn, networkx, shapely, torch, torch_geometric, yaml, jsonschema, statsmodels
print("numpy", numpy.__version__)
print("scipy", scipy.__version__)
print("torch", torch.__version__, "cuda:", torch.cuda.is_available())
print("torch_geometric", torch_geometric.__version__)
print("networkx", networkx.__version__)
print("shapely", shapely.__version__)
print("ALL IMPORTS OK")
EOF
