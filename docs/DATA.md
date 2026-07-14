# DATA.md — dataset acquisition & provenance guide

An external grader must be able to rebuild `data/` from this file alone. Update it the
moment a dataset lands (URL used, version/commit, date, checksum, license note).

## Corpus overview (plan §7)

| Dataset | Scale | Levels derivable | Role | Status |
|---|---|---|---|---|
| **prelim_rasters** (user-supplied) | 1 institutional building (FF/LF/SF, multi-sheet) + 10 small residential plans | R0–R2 via DATA-0 ingest lane; R3/R4 by hand | **preliminary pipeline testing**; Gate-b candidate building | ✅ landed 2026-07-14 → `data/raw/prelim_rasters/` (see its README) |
| Structured3D | ~3.5K scenes / ~20K rooms | R0–R2 auto | silver corpus; Gate-c smoke set | ⬜ not downloaded |
| CubiCasa5K | ~5K plans / ~25K rooms | R0–R2 auto | silver corpus (residential regime) | ⬜ not downloaded |
| MSD (Modified Swiss Dwellings, ECCV 2024) | ~4,167 usable (train) multi-unit plans / ~140K spaces | R0–R2 auto + **near-R4 from zone/apartment grouping** | silver corpus + zero-cost rich level | ✅ 200-plan subset landed 2026-07-14 → `data/raw/msd/`; loader `topospec.data.msd` |
| InstBuild | 5–10 institutional buildings | R0–R4 (gold, hand-annotated) | out-of-regime stress set; S4 scale split; annotation-cost measurement | 🟡 partially unblocked: prelim_rasters FF building = candidate #1; ArchCAD-400K / FloorPlanCAD scouting below (DATA-7) |
| Code corpus (Phase A2) | 1 established dataset | AST → +dataflow → +call (auto) | generality check C5 | ⬜ pending A2-1 decision |

## Institutional-scale candidate sources (scouted 2026-07-14; evaluation = DATA-7)

| Source | Scale & mix | Format / annotations | Access | Fit |
|---|---|---|---|---|
| **ArchCAD-400K** (NeurIPS 2025, arXiv 2503.22346) | 413,062 chunks / 5,538 professional drawings (Arcplus ECADI) — offices/public/industrial; first release = 40K curated subset | SVG + parsed-JSON primitives, panoptic symbol labels; NO room polygons | 🔒 **GATED**: HF `jackluoluo/ArchCAD`, manual approval — **user must file the access request**; license = academic-use-only (sources inconsistent; pin at approval) | Highest-volume institutional source (S4); unlocks after approval |
| **FloorPlanCAD** (ICCV 2021) | 15,663 drawings, ~1,200+ projects incl. parking garages, auditoria, hospitals, towers | annotated SVG, per-primitive `semanticId`/`instanceId` (accept BOTH `semanticId` and `semantic-id` spellings!), 35 classes: walls=33, curtain wall=34, railing=35, doors=1–6, windows=7–10, stairs/elevator/escalator=28–30 | ✅ **FULL CORPUS LANDED 2026-07-14** → `data/raw/floorplancad/`: train 6,965 + test 3,827 + val 810 = **11,602 SVGs** (2.2 GB extracted; zips kept: train sha256 d940e6838d4e1678…, test 852913e44689de75…, val cd6bc7c910d2563c…). Sample dissection remains at `data/raw/floorplancad_sample/`. CC BY-NC 4.0 | Parser lane committed (D-010); sheets are crops — corpus use pending strategy |

Full access details, download commands, format dissection with literal primitive
examples, and taxonomy: `docs/scout_reports/cad_datasets_2026-07-14.md`.

**Derivation plan (DATA-7):** rasterize wall-class primitives (33/34/35) per sheet →
run the SAME watershed lane as prelim rasters (`topospec.data.raster`) → R0; door
primitives (1–6) then localize openings → R1/R2 semantics. One module serves both
raster and CAD corpora. If robust on FloorPlanCAD's public buildings, InstBuild stops
being annotation-bound for R0–R2 and gold effort concentrates on R3/R4 only.

## Acquisition notes

### Structured3D
- Source: https://structured3d-dataset.org — request access, download annotation-only
  bundle (we need room polygons + door/window annotations, NOT panoramas; keep the
  download small).
- Loader: `topospec.data.structured3d` (ROADMAP DATA-1). Record: version, download date,
  file list checksum here.

### CubiCasa5K
- Source: https://github.com/CubiCasa/CubiCasa5k (SVG floorplan annotations + images;
  we parse the SVGs). License: CC BY-NC 4.0 — non-commercial research OK; note in paper.
- Loader: `topospec.data.cubicasa` (DATA-2).

### MSD — Modified Swiss Dwellings  ✅ subset landed 2026-07-14 (DATA-3)
- Source: **4TU.ResearchData** `e1d89cb5-6872-48fc-be63-aadd687ee6f9` (v2, 2023-07-11),
  ECCV 2024. **License: CC BY 4.0** (attribute van Engelenburg et al.; fixtures may be
  committed). Files: `…-v1-train.zip` (4.76 GB, uuid `279ef4b4-…`), `…-v1-test.zip`
  (0.79 GB, uuid `7cccae96-…`, sha256 `bd65dfe6…928e89f`).
- **Only the ~4,167 TRAIN plans are usable**: the test split withholds `graph_out`
  (geometry ground truth — MSD is a generation benchmark). Full format dissection +
  the two leakage/direction caveats: `docs/scout_reports/msd_2026-07-14.md`.
- 4TU has **no HTTP range support**, but the train zip stores tiny `graph_in/` before
  `graph_out/`, so a subset is stream-extractable cheaply. Landed 200 plans into
  `data/raw/msd/{graph_out,graph_in}/` via `stream-unzip`:
  ```python
  # /data1/yansari/.conda/envs/topofield/bin/pip install stream-unzip
  import requests
  from stream_unzip import stream_unzip
  URL = "https://data.4tu.nl/file/e1d89cb5-6872-48fc-be63-aadd687ee6f9/279ef4b4-d3bd-41f4-b0c9-5e9af8cce6f6"
  def chunks():
      with requests.get(URL, stream=True) as r:
          yield from r.iter_content(1 << 20)
  # iterate stream_unzip(chunks()); save graph_out/<id>.pickle (+ buffered graph_in),
  # break after N -> ~8.7 MB streamed for 200 plans (full script in scout report)
  ```
  For the FULL corpus: download the whole train zip (4.76 GB) and drop all
  `graph_out/*.pickle` into `data/raw/msd/graph_out/`.
- Loader: `topospec.data.msd.build_graphs(raw_dir, out_dir, zone_mode=…)` → validated
  R0–R4 JSON per building in `data/derived/msd/` + `exclusions.jsonl`. 200-plan subset:
  0 exclusions, 6,720 spaces, all levels validate (14.6 s login-node). Full corpus
  (4,167 plans → ~20k JSON files) runs via slurm.

### InstBuild (gold institutional set)
- **Needs user/advisor decision** (plan §14.1): candidate sources — university facility
  plans, hospital/school plans from public IFC repositories (e.g. buildingSMART sample
  files, Open IFC Model Repository), or partner institutions. Requirements: multi-wing /
  multi-zone scale, ≥100 directed-access instances across the set (Gate-d), formats we
  can ingest (IFC preferred — feeds the EnergyPlus gold lane via bim2sim).
- Annotation: guide + timing sheets per ROADMAP A-7/DATA-6; times feed claim C3.

## External simulators (label lanes)

| Tool | Purpose | Install route | Status |
|---|---|---|---|
| EnergyPlus ≥ 23.x | Y_zone gold lane | https://energyplus.net (Linux tarball, user-space install OK) | ⬜ |
| bim2sim | IFC → EnergyPlus models | pip/github, python-compatible | ⬜ |
| JuPedSim | Y_egress evacuation traces | `pip install jupedsim` | ⬜ (decision D-004: sample lane) |
| (Vadere) | egress alternative | Java; only if JuPedSim blocks | ⬜ |

## Rules (see also data/CLAUDE.md)

- `data/raw/` read-only after download; derivation only via `topospec.data.*` builders;
  every derived graph passes `topospec validate`; exclusions logged with reasons.
- Building IDs are globally unique: `<dataset>:<native_id>`; splits key on these.
- Personally identifying content: none of these datasets should contain any; if an
  InstBuild source does (e.g. named room occupants), strip at ingest.
