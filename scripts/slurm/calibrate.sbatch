#!/usr/bin/env bash
#SBATCH --job-name=a0-calibrate
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=runs/slurm-%j.out
# Full Phase A0 calibration (ROADMAP A0-2). CPU-only: probes V1-V5 need no GPU.
# Submit from the repo root on the login node:  sbatch --mcs-label=$USER scripts/slurm/calibrate.sbatch
set -euo pipefail
cd /data1/yansari/PhD/topofield/spectrum
export SLURM_RUN=1
/data1/yansari/.conda/envs/topofield/bin/python -m topospec.cli calibrate \
    --config configs/calibration_a0.yaml
