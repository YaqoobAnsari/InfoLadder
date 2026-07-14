"""Download Tesseract2 model weights into the repo's Model_weights/ dir.

Adapted from Tesseract2/download_weights.py, which hardcodes the Docker path
/app/Model_weights. Here we pull the same three checkpoints from the HF Space
`yansari/Tesseract` into <repo>/Model_weights so Main.py (which resolves
Model_weights relative to os.getcwd()) finds them when launched from repo root.

Login-node safe: this is network I/O only, no model inference.
"""
import os
from huggingface_hub import hf_hub_download

REPO_ROOT = "/data1/yansari/PhD/topofield/Tesseract2"

# (filename, minimum expected size in MB) — same minimums as the original script.
WEIGHTS = [
    ("craft_mlt_25k.pth", 50),
    ("None-VGG-BiLSTM-CTC.pth", 20),
    ("door_mdl_32.pth", 200),
]

os.makedirs(os.path.join(REPO_ROOT, "Model_weights"), exist_ok=True)

for name, min_mb in WEIGHTS:
    hf_hub_download(
        repo_id="yansari/Tesseract",
        filename=f"Model_weights/{name}",
        repo_type="space",
        local_dir=REPO_ROOT,
    )
    path = os.path.join(REPO_ROOT, "Model_weights", name)
    size = os.path.getsize(path)
    print(f"{name}: {size / 1e6:.1f} MB -> {path}")
    if size < min_mb * 1e6:
        raise RuntimeError(f"{name} too small: {size} bytes (min {min_mb} MB)")

print("All weights verified!")
