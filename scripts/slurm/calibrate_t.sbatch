#!/usr/bin/env bash
#SBATCH --job-name=t-calibrate
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# T-ladder instrument calibration (D-014 P-4): 6 tiers x 8 targets x V1-V5 x 3 seeds.
set -euo pipefail
cd /data1/yansari/PhD/topofield/spectrum
/data1/yansari/.conda/envs/topofield/bin/python -m topospec.cli calibrate \
    --config configs/calibration_t_ladder.yaml
