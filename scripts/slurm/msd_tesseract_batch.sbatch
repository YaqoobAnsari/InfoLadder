#!/usr/bin/env bash
#SBATCH --job-name=msd-tess-batch
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=05:00:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# D-014 T0/T1 validation: render MSD plans -> Tesseract2 -> score vs MSD ground truth.
# SCOPE = rooms + labels + connectivity (T0/T1). Door tier (T2) is NOT validated
# (synthetic arcs detect ~2/19); the door-detection rate is reported as evidence only.
# ~27 s/plan on CPU; ~200 plans -> ~90 min + render + score. gpu2 because the cpu
# partition can't see /data1 (docs/CLUSTER.md). NOT set -e: one crash mustn't abort.
#   sbatch --mcs-label=morshed scripts/slurm/msd_tesseract_batch.sbatch [N]
set -uo pipefail

REPO=/data1/yansari/PhD/topofield/spectrum
TESS=/data1/yansari/PhD/topofield/Tesseract2
PY=/data1/yansari/.conda/envs/topofield/bin/python
TPY=/data1/yansari/.conda/envs/tesseract2/bin/python
RENDER_DIR="$REPO/data/derived/msd_render_arc"
N=${1:-200}
export OMP_NUM_THREADS=8
echo "NODE: $(hostname)  N=$N  @ $(date -Is)"

# 1. render N plans (arc; records world->px transform + remap table).
# Renders are deterministic (seeded per plan) — skip if already complete so
# RESUBMISSIONS spend walltime on Tesseract, not re-rendering.
cd "$REPO"
N_PNG=$(ls "$RENDER_DIR"/*.png 2>/dev/null | grep -vc contact_sheet || echo 0)
if [ "$N_PNG" -lt "$N" ]; then
  $PY scripts/render_msd_rasters.py -n "$N" --door-style arc --no-contact --out "$RENDER_DIR"
else
  echo "renders already complete ($N_PNG >= $N) — skipping render step"
fi

# 2+3. per plan: copy into Input_Images, run Tesseract (skip if already done)
cd "$TESS"
pass=0; fail=0; skip=0
for f in "$RENDER_DIR"/*.png; do
  base=$(basename "$f"); [ "$base" = "contact_sheet.png" ] && continue
  id="${base%.png}"
  out="$TESS/Results/Json/msd_${id}/msd_${id}_post_pruning.json"
  if [ -f "$out" ]; then skip=$((skip+1)); continue; fi
  cp "$f" "$TESS/Input_Images/msd_${id}.png"
  if $TPY -u Main.py "msd_${id}.png" >/dev/null 2>&1; then
    pass=$((pass+1))
  else
    fail=$((fail+1)); echo "  TESS-FAIL msd_${id} (likely <5 colors: no corridor/balcony)"
  fi
done
echo "TESSERACT: pass=$pass fail=$fail skip=$skip"

# 4. score vs MSD ground truth -> batch_report.{json,md}
cd "$REPO"
$PY scripts/score_msd_tesseract.py "$RENDER_DIR"
echo "DONE @ $(date -Is)"
