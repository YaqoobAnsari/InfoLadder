# CAD Floorplan Dataset Scout — FloorPlanCAD & ArchCAD-400K

**Task:** DATA-7 practical-access scouting + land parseable samples.
**Date:** 2026-07-14 · **Scout:** data-engineer · **Node:** deepnet login node (no heavy compute used).

## Verdicts at a glance

| Dataset | Access verdict | What we can get today | Format | License |
|---|---|---|---|---|
| **FloorPlanCAD** | ✅ **WORKS-NOW** | Full SVG splits via public Google Drive; **val split (810 SVGs, 10.2 MB) downloaded**, 25-file sample landed | Annotated **SVG** vector primitives, per-`<path>` `semanticId`/`instanceId` | CC BY-NC 4.0 (annotations) |
| **ArchCAD-400K** | 🟡 **NEEDS-REQUEST** | Nothing without approval — HF repo is `gated: manual`; even the README 401s | SVG + parsed-JSON + PNG + point-cloud + captions (zips) | ACADEMIC-USE-ONLY (non-commercial); metadata inconsistent — see §2.4 |

**Bottom line:** adopt **FloorPlanCAD first** for the `drawing→SpectrumGraph` (rooms-from-primitives) derivation — it is downloadable now, ships the exact wall/door/window primitive semantics we need, and includes large public buildings. File the ArchCAD access request in parallel (it is the higher-volume institutional-regime source, but is gated behind manual maintainer approval that we cannot self-serve).

---

## 1. FloorPlanCAD — WORKS-NOW

### 1.1 Access reality (leads run down)

- **Official site** `https://floorplancad.github.io/` — project "shutdown early 2022" but the **Google Drive links are live**. It offers three archives (Train set 1, Train set 2, Test set) as **`.tar.xz`**. The **Test set is 1.84 GB** (`FD 37 7A 58 5A` xz magic; it bundles `coco_vis/*.png` + full-res PNGs + SVGs, PNGs stored *first* → streaming to reach the SVGs would cost ~1 GB+). **Not used** — violates the no-GBs rule.
- **HuggingFace mirrors are all raster/derived, NOT raw SVG** — none usable for per-primitive semantics:
  - `Voxel51/FloorPlanCAD` (454 MB) — PNG + FiftyOne bbox detections only.
  - `Andreasvdb5/FloorPlanCAD` — 997 PNGs. `tilak1114/FloorPlanCAD[-with-masks]` — parquet (raster+masks). `joshlyman/...` — a training script, no data.
- **Winning path — CADTransformer's redistribution** (`VITA-Group/CADTransformer`, CVPR 2022, the canonical FloorPlanCAD panoptic repo). Its `preprocess/download_data.py` ships **SVG-only `.zip` splits** (walls/doors clipped, no rasters) that are tiny and **support HTTP Range**:

  | split | Google Drive id | size | contents |
  |---|---|---|---|
  | train | `16McNNY_-Y2uVnq42ntZTdYKPWgOZxwp3` | 84.9 MB | `train/svg_gt/*.svg` |
  | **val** | `1xgLqcj91i13_3vhfsUYcRYh3PhFYB9LJ` | **10.2 MB** | `val/svg_gt/*.svg` (810 files) |
  | test | `1Hc4-ggsUMoB_5uqJdqYRn9K73QS8rOgG` | 40.4 MB | `test/svg_gt/*.svg` |

  These are the same `svg_gt` files the ArchCAD/DPSS pipeline also consumes (`parse_FpCAD_svg.py`), so the format is canonical, not a fork.

### 1.2 Exact commands used for the sample download

Google Drive's large-file confirm flow must be walked manually (gdown 6.1.0 dropped `--fuzzy`; the `drive.usercontent.google.com/download` form needs the `confirm`+`uuid` fields). The resolver used:

```python
# resolve a Drive file id to a Range-capable direct URL
import requests, re
def resolve(fid):
    s = requests.Session(); s.headers.update({"User-Agent": "Mozilla/5.0"})
    r1 = s.get(f"https://drive.usercontent.google.com/download?id={fid}&export=download", timeout=60)
    fields = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', r1.text))  # id, export, confirm, uuid
    r2 = s.get("https://drive.usercontent.google.com/download",
               params={k: fields[k] for k in ("id","export","confirm","uuid") if k in fields},
               stream=True, timeout=60)
    return s, r2.url            # r2.url -> Accept-Ranges: bytes, application/octet-stream

# download val.zip (10.2 MB) in full, then extract SVGs with stdlib zipfile
```

- **Downloaded:** `val.zip` — **10,156,480 bytes**, `sha256 = cd6bc7c910d2563c00f70fda05b9deb548094aedbf1cde15ef93e0ee9282702f`, magic `504b0304` (valid ZIP), 810 files under `val/svg_gt/`.
- **Landed at** `data/raw/floorplancad_sample/`:
  - `_source_val.zip` (the pristine 10.2 MB archive),
  - **25 sample SVGs** chosen to span the size distribution (4.8 KB … 10.2 MB),
  - `manifest.json` (per-file sha256 + provenance).
- Tooling installed into the `topofield` env (light): `pip install -U huggingface_hub remotezip gdown`.
- NB: `remotezip` (range-extract a few files from a remote zip's central directory) **works on the Drive URL** (`Accept-Ranges: bytes`, 206 verified) and is the fallback for grabbing a handful from `train.zip`/`test.zip` without full download; for `val.zip` a full 10 MB pull was simpler.

### 1.3 Format dissection (from the landed files — not from docs)

- **Container:** one SVG per clipped floor plan. Root is `<svg tag="svg" version="1.1" viewBox="0 0 140.0 140.0" xmlns="http://www.w3.org/2000/svg" ...>` — **only a `viewBox` (`minx miny width height`), no `width`/`height`**. Coordinates are model units in a clipped local window (drawings are cut from multi-floor project files into ~140×140-unit tiles).
- **Primitives carrying semantics:** `<path>` (dominant), plus `<circle>` and `<ellipse>`. In the 25-file sample: **74,849 `path`, 351 `circle`, 23 `ellipse`; zero `<line>`** — walls/doors are polyline *paths* (`d="M x,y L x,y"`), not `<line>`.
- **Per-primitive attributes:** `d`, `fill`, `stroke`, `stroke-width`, `tag`, **`semanticId`**, **`instanceId`**.
- **⚠ Attribute-name variant (load-bearing for the parser):** this CADTransformer redistribution uses **camelCase `semanticId`/`instanceId`** (all 25 files). The **original floorplancad.github.io release uses hyphenated `semantic-id`/`instance-id`** (see `CADTransformer/preprocess/utils_dataset.py`, which reads `line["semantic-id"]`, vs `utils/utils_dataset.py` which reads `line["semanticId"]`). **The `drawing→SpectrumGraph` (DATA-0) ingester must accept both spellings.**
- **Defaults:** missing `semanticId` → class **0** (background/unlabeled: dimension lines, hatching, text, leaders). Missing `instanceId` → **−1**.
- **Thing vs stuff:** countable classes (doors, windows, stairs, fixtures) get positive `instanceId`; "stuff" (wall/curtain-wall/railing and background) carry `instanceId="-1"`.

**Literal example primitives (verbatim from the sample):**

```xml
<!-- wall (semanticId 33, stuff → instanceId -1) — from 0030-0010.svg -->
<path d="M 133.19129750000002,93.5 L 140.0,93.5" fill="none"
      instanceId="-1" semanticId="33" stroke="rgb(178,178,0)" stroke-width="0.1" tag="path"/>

<!-- double door (semanticId 2, thing → instanceId 7) — from 0030-0010.svg -->
<path d="M 115.19129750000002,94.5 L 115.19129750000002,101.81200000000001" fill="none"
      instanceId="7" semanticId="2" stroke="rgb(0,178,178)" stroke-width="0.1" tag="path"/>

<!-- window (semanticId 7, thing → instanceId 9) — from 0085-0002.svg -->
<path d="M 123.55703399999999,51.38846849999999 L 123.55703399999999,61.38846849999999" fill="none"
      instanceId="9" semanticId="7" stroke="rgb(0,133,178)" stroke-width="0.1" tag="path"/>
```

### 1.4 Semantic taxonomy (35 classes, authoritative from `config/anno_config.py`)

Class 0 = background/none. IDs stored in the SVG are the **raw** ids below (a `RemapDict` exists in the repo only for the model's contiguous training space — ignore it for ingest).

- **Doors (thing):** 1 single door · 2 double door · 3 sliding door · 4 folding door · 5 revolving door · 6 rolling door
- **Windows (thing):** 7 window · 8 bay window · 9 blind window · 10 opening symbol
- **Furniture/fixtures (thing):** 11 sofa · 12 bed · 13 chair · 14 table · 15 TV cabinet · 16 Wardrobe · 17 cabinet · 18 gas stove · 19 sink · 20 refrigerator · 21 airconditioner · 22 bath · 23 bath tub · 24 washing machine · 25 squat toilet · 26 urinal · 27 toilet
- **Circulation/equipment (thing):** 28 stairs · 29 elevator · 30 escalator
- **Stuff (uncountable):** 31 row chairs · 32 parking spot · **33 wall** · **34 curtain wall** · **35 railing**

**Load-bearing for rooms-from-primitives:** the room-boundary geometry is **{33 wall, 34 curtain wall, 35 railing}**; **openings are {1–6 doors, 7–10 windows}**; **vertical circulation is 28/29/30**. Everything else is furniture clutter to ignore for topology.

### 1.5 Scale, scope, and "does it include large public buildings?" — YES

- Filenames are `PROJECT-SHEET.svg` (e.g. `0030-0010` = project 30, sheet 10); one architectural project yields many clipped sheets. Full corpus ≈ **15,663 drawings** across ~1,200+ projects (residential + commercial).
- The 25-file sample alone contains unmistakable **large public / non-residential** plans:
  - `0131-0199.svg` — **315 parking spots** (parking garage),
  - `0400-0082.svg` — **52,560 `chair` primitives** across 182 instances (auditorium/theatre/lecture-hall seating; 10 MB single SVG),
  - `0431-0012.svg` — **872 toilet** + 347 wall (large sanitary block),
  - `0089-0107.svg` — 679 sink (lab/hospital wet-room),
  - `1114-0046.svg` — 214 curtain-wall (glazed facade / tower),
  - `0030-0010.svg` — 210 elevator + 188 wall (core/lobby).
- Typical plan size: **~90–2,500 primitives**; large public sheets reach **50k+**. Sample-wide instance counts 1–182 per sheet.

---

## 2. ArchCAD-400K — NEEDS-REQUEST

### 2.1 Access reality

- Paper: **NeurIPS 2025**, "ArchCAD-400K: An Open Large-Scale Architectural CAD Dataset…", arXiv **2503.22346**. Code+baseline (DPSS) open at `github.com/ArchiAI-LAB/ArchCAD` (released 2025-10-16).
- Dataset lives at HF **`jackluoluo/ArchCAD`** and is **`gated: manual`** (`private:false`). Confirmed empirically:
  - `GET …/resolve/main/data/svg.zip` → **HTTP 401 Unauthorized**; even `…/raw/main/README.md` → *"Access to dataset … is restricted. You must … be authenticated."*
  - i.e. you must be **logged in with an HF account, click "Request access", and wait for the maintainer to approve** — not self-serviceable from this node, and no anonymous token works.
- The file tree *is* public (metadata only). First release = **40K-sample curated subset** (of the full 413K); more "in future releases."

### 2.2 What ships (file tree, sizes — all currently 401 to download)

`data/svg.zip` 311 MB · `data/json.zip` 393 MB · `data/png.zip` 1.83 GB · `data/point.zip` 80 MB · `data/caption.zip` 19 MB · `assets/data_example.png`.

- **SVG** = vector primitives (same panoptic lineage as FloorPlanCAD). **JSON** = parsed-primitive representation used for training (segments with semantic+instance labels). **point** = point-cloud sampling (SymPoint-style). **caption** = text captions. **No standalone room/space polygons** — it is panoptic *symbol spotting*, primitives only (same rooms-from-primitives derivation need as FloorPlanCAD).
- Because zips are single archives ≥200 MB, no sample was pulled (over the task's byte cap, and gated anyway). `caption.zip` (19 MB) and `point.zip` (80 MB) are the only sub-limit members but are not the geometry we'd dissect.

### 2.3 Scale & composition

- **413,062 chunks from 5,538 highly standardized drawings** ("26× larger than the previous largest CAD dataset"). Annotations auto-generated by an engine exploiting intrinsic CAD layer/block attributes.
- Source drawings are **real professional architecture** — copyright **Arcplus East China Architectural Design & Research Institute** — i.e. offices/public/industrial, strong fit for the institutional (S4) regime. (The earlier DATA.md "only 14% residential" figure is consistent with a professional-practice corpus; not re-verifiable from the gated card.)

### 2.4 License — inconsistent across sources (flag before use)

- GitHub `LICENSE`: **"ACADEMIC USE LICENSE … Commercial use is strictly prohibited"** (© Arcplus). HF card tag: `cc-by-nc-4.0`. arXiv page: "Creative Commons Attribution 4.0". **Effective reading: academic / non-commercial only.** Resolve the exact terms with the maintainer at access-request time and record in `docs/DECISIONS.md` before any release.

---

## 3. Recommendation

**Adopt FloorPlanCAD first** for the shared `drawing→SpectrumGraph` (DATA-0) rooms-from-primitives module:

1. It is **downloadable now** (no gating), CC BY-NC (compatible with the study's other silver corpora), and we already hold a parseable 810-SVG split + 25-file sample.
2. It ships **exactly** the primitives the derivation keys on — walls (33), curtain wall (34), railing (35), doors (1–6), windows (7–10), stairs/elevator/escalator (28–30) — with instance ids that separate countable openings from wall "stuff".
3. It **includes the large public buildings** the InstBuild/S4 regime needs (parking garages, auditoria, sanitary/lab blocks, glazed towers), so a robust room-derivation here directly unblocks R0–R2 for institutional plans without hand annotation.

**File the ArchCAD-400K access request in parallel** (HF "Request access" on `jackluoluo/ArchCAD`, logged-in account). It is the higher-volume, purpose-built institutional corpus and shares the identical primitive→topology derivation, so it drops in behind the same DATA-0 module once approved. Treat it as NEEDS-REQUEST, not a blocker.

**Immediate DATA-0 design notes to carry forward:**
- Parser must accept **both** `semanticId`/`instanceId` (camelCase, this redistribution) **and** `semantic-id`/`instance-id` (hyphen, original release).
- Root has **only `viewBox`** (no width/height); read units from `viewBox`.
- Treat `semanticId==0` as unlabeled scaffolding (dims/hatch/text) to be discarded for topology.
- `<line>` never appears — parse `<path> d`, `<circle>`, `<ellipse>` (svgpathtools handles `d`).

## 4. Reproduce `data/`

```bash
# env (login node OK — download only)
/data1/yansari/.conda/envs/topofield/bin/pip install -U gdown huggingface_hub remotezip

# FloorPlanCAD val split (10.2 MB) via CADTransformer's Drive id, then extract
#   file id 1xgLqcj91i13_3vhfsUYcRYh3PhFYB9LJ  ->  drive.usercontent confirm-form flow (see §1.2)
#   sha256(val.zip)=cd6bc7c910d2563c00f70fda05b9deb548094aedbf1cde15ef93e0ee9282702f
#   -> data/raw/floorplancad_sample/{_source_val.zip, 25×*.svg, manifest.json}

# ArchCAD-400K: request access at https://huggingface.co/datasets/jackluoluo/ArchCAD (gated:manual), then
#   huggingface-cli download jackluoluo/ArchCAD --repo-type dataset --include "data/svg.zip" --token <TOKEN>
```
