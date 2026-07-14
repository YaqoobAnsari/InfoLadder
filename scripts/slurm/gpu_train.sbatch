#!/usr/bin/env bash
#SBATCH --job-name=phase-d-train
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --gres=gpu:nvidia_h200_1g.18gb:1
#SBATCH --time=24:00:00
#SBATCH --output=runs/slurm-%j.out
# Phase D transformer fine-tuning (ROADMAP D-2). One MIG slice fits <=8M-param models;
# escalate to 2g.35gb only with measured memory pressure (docs/CLUSTER.md).
set -euo pipefail
cd /data1/yansari/PhD/topofield/spectrum
/data1/yansari/.conda/envs/topofield/bin/python -m topospec.cli grid \
    --config "${CONFIG:?set CONFIG=configs/<phase_d_config>.yaml via sbatch --export}"
