#!/usr/bin/env bash
#SBATCH --job-name=ingest-rasters
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# DATA-0: batch-ingest data/raw/prelim_rasters -> R0 graphs + PDE labels + QA overlays.
set -euo pipefail
cd /data1/yansari/PhD/topofield/spectrum
/data1/yansari/.conda/envs/topofield/bin/python scripts/ingest_prelim_rasters.py
