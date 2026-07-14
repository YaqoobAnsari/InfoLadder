#!/usr/bin/env bash
#SBATCH --job-name=t-calib-v6
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=47:00:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# V6 row of the T-ladder calibration: 8 targets x 6 tiers x 3 seeds x 3 restarts on CPU.
set -euo pipefail
cd /data1/yansari/PhD/topofield/spectrum
export OMP_NUM_THREADS=16
/data1/yansari/.conda/envs/topofield/bin/python -m topospec.cli calibrate \
    --config configs/calibration_t_v6.yaml
