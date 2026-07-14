#!/usr/bin/env bash
#SBATCH --job-name=phase-b-grid
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --array=0-0%8
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%A_%a.out
# Phase B grid as an array job: each task runs one config shard (ROADMAP B-1/B-3).
# The grid runner (topospec.cli grid) must support --shard N/M before this is used.
# Set the real array range when the grid is defined, e.g. --array=0-449%8.
# Add --gres=gpu:nvidia_h200_1g.18gb:1 for V6/transformer cells only.
set -euo pipefail
cd /data1/yansari/PhD/topofield/spectrum
/data1/yansari/.conda/envs/topofield/bin/python -m topospec.cli grid \
    --config configs/grid_phase_b.yaml \
    # --shard "${SLURM_ARRAY_TASK_ID}/${SLURM_ARRAY_TASK_COUNT}"   # enable at B-3
