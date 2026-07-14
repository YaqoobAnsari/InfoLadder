#!/usr/bin/env bash
#SBATCH --job-name=tess-batch
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# Batch-run Tesseract2 (raster floorplan -> navigable graph) over the annotated
# up/upE variants in Input_Images/. Outputs land in Tesseract2/Results/{Json,Plots,Time&Meta}.
# CPU inference (their code auto-selects CPU when torch.cuda.is_available() is False).
# NOT set -e: one bad image must not abort the batch; each run's status is logged.
set -uo pipefail

REPO=/data1/yansari/PhD/topofield/Tesseract2
PY=/data1/yansari/.conda/envs/tesseract2/bin/python
cd "$REPO"
export OMP_NUM_THREADS=8

# base_path in Main.py is os.getcwd(), so we MUST run from the repo root.
echo "NODE: $(hostname)  CWD: $(pwd)"
$PY -c "import torch,cv2; print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'cv2',cv2.__version__)"

images=(
  "FF part 1up.png"
  "FF part 1upE.png"
  "FF part 2up.png"
  "FF part 3up.png"
  "FF part 3upE.png"
  "FF part 4up.png"
  "FF part 5up.png"
  "FF part 6up.png"
  "FF part 7up.png"
  "FF part 8up.png"
  "SF part 1upE.png"
)

pass=0; fail=0
for img in "${images[@]}"; do
  echo "===== START: $img @ $(date -Is) ====="
  start=$(date +%s)
  if $PY -u Main.py "$img"; then
    status=OK; pass=$((pass+1))
  else
    status=FAILED; fail=$((fail+1))
  fi
  end=$(date +%s)
  echo "===== END:   $img  status=$status  walltime=$((end-start))s ====="
done

echo "BATCH SUMMARY: pass=$pass fail=$fail total=${#images[@]}"
