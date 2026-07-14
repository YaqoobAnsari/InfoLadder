#!/usr/bin/env bash
#SBATCH --job-name=msd-build
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# DATA-3: derive the full MSD corpus (~4,167 plans) -> R0-R4 SpectrumGraphs.
# CPU-only + light (200 plans took ~15s); gpu2 partition because the cpu
# partition cannot see /data1 (docs/CLUSTER.md). Submit from the repo root:
#   sbatch --mcs-label=morshed scripts/slurm/msd_build.sbatch
set -euo pipefail
cd /data1/yansari/PhD/topofield/spectrum
/data1/yansari/.conda/envs/topofield/bin/python scripts/build_msd_corpus.py
