#!/usr/bin/env bash
#SBATCH --job-name=topospec-verify
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# Full test suite including slow tests, off the login node.
set -euo pipefail
cd /data1/yansari/PhD/topofield/spectrum
/data1/yansari/.conda/envs/topofield/bin/python -m ruff check src tests
/data1/yansari/.conda/envs/topofield/bin/python -m pytest
