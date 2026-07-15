#!/usr/bin/env bash
#SBATCH --job-name=t-calib-v6-gpu
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --gres=gpu:nvidia_h200_1g.18gb:1
#SBATCH --time=24:00:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# V6 row of the T-ladder calibration on a MIG slice (CPU run 7229 could not
# finish inside walltime: 28/144 cells in 16 h). Env: topofield-gpu (cu126).
set -euo pipefail
cd /data1/yansari/PhD/topofield/spectrum
/data1/yansari/.conda/envs/topofield-gpu/bin/python -m topospec.cli calibrate \
    --config configs/calibration_t_v6_gpu.yaml
