#!/usr/bin/env bash
#SBATCH --job-name=msd-score
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# Standalone RE-SCORER: score existing Tesseract2 outputs on the MSD renders against
# MSD ground truth WITHOUT re-running render or Tesseract (reads the post_pruning JSONs
# already on disk). Use it to (a) re-score after job 7230 completes if its in-job
# scorer step did not run, and (b) recompute the before/after adjacency-F1 KPI after a
# retrained door model is deployed and the affected plans are re-Tesseracted.
#
# Memory: the scorer loads one small MSD graph pickle + one ~20 KB post_pruning JSON at
# a time and accumulates tiny per-plan stat dicts; peak is well under 1 GB even at the
# full 4,167-plan scale (the 7228 OOM was in the door R-CNN detect_doors step, NOT
# scoring). 8G is generous headroom. gpu2 (no GPU needed) because the cpu partition
# cannot see /data1 (docs/CLUSTER.md).
#   sbatch --mcs-label=morshed scripts/slurm/msd_score.sbatch [RENDER_DIR]
set -uo pipefail

REPO=/data1/yansari/PhD/topofield/spectrum
PY=/data1/yansari/.conda/envs/topofield/bin/python
RENDER_DIR="${1:-$REPO/data/derived/msd_render_arc}"
cd "$REPO"
echo "NODE: $(hostname)  RENDER_DIR=$RENDER_DIR  @ $(date -Is)"
$PY scripts/score_msd_tesseract.py "$RENDER_DIR"
echo "DONE @ $(date -Is)"
