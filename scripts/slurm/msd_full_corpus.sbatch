#!/usr/bin/env bash
#SBATCH --job-name=msd-full-corpus
#SBATCH --partition=gpu2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=47:59:00
#SBATCH --mcs-label=morshed
#SBATCH --output=runs/slurm-%j.out
# P-3 FULL-SCALE: all ~4,167 usable MSD train plans -> render (arc) -> Tesseract2 ->
# score vs ground truth. SCOPE: T0/T1 validation (rooms/labels/connectivity); door
# tier (T2) is NOT validated pre-retrain (D-016) and these Tesseract runs will be
# repeated after the retrained door model ships — this pass exists so the user can
# inspect thousands of graphs and we get corpus-scale T0/T1 accuracy now.
# Resumable: the underlying batch skips plans whose Tesseract output already exists.
set -uo pipefail

REPO=/data1/yansari/PhD/topofield/spectrum
cd "$REPO"

# 0. extract ALL graph_out pickles from the full train.zip if not yet done
N_PICKLES=$(ls data/raw/msd/graph_out/*.pickle 2>/dev/null | wc -l)
if [ "$N_PICKLES" -lt 4000 ]; then
  echo "extracting graph_out from train.zip (have $N_PICKLES pickles)..."
  /data1/yansari/.conda/envs/topofield/bin/python - <<'EOF'
import zipfile, pathlib
zp = next(pathlib.Path("data/raw/msd").glob("*train*.zip"))
out = pathlib.Path("data/raw/msd")
n = 0
with zipfile.ZipFile(zp) as z:
    for name in z.namelist():
        if "graph_out/" in name and name.endswith(".pickle"):
            base = name.split("graph_out/")[-1]
            dest = out / "graph_out" / base
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(name))
                n += 1
print(f"extracted {n} new pickles")
EOF
fi
echo "pickles on disk: $(ls data/raw/msd/graph_out/*.pickle | wc -l)"

# 1. run the (resumable) render->Tesseract->score batch over everything
bash scripts/slurm/msd_tesseract_batch.sbatch 4167
