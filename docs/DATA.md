# DATA.md — dataset acquisition & provenance guide

An external grader must be able to rebuild `data/` from this file alone. Update it the
moment a dataset lands (URL used, version/commit, date, checksum, license note).

## Corpus overview (plan §7)

| Dataset | Scale | Levels derivable | Role | Status |
|---|---|---|---|---|
| **prelim_rasters** (user-supplied) | 1 institutional building (FF/LF/SF, multi-sheet) + 10 small residential plans | R0–R2 via DATA-0 ingest lane; R3/R4 by hand | **preliminary pipeline testing**; Gate-b candidate building | ✅ landed 2026-07-14 → `data/raw/prelim_rasters/` (see its README) |
| Structured3D | ~3.5K scenes / ~20K rooms | R0–R2 auto | silver corpus; Gate-c smoke set | ⬜ not downloaded |
| CubiCasa5K | ~5K plans / ~25K rooms | R0–R2 auto | silver corpus (residential regime) | ⬜ not downloaded |
| MSD (Modified Swiss Dwellings, ECCV 2024) | 5,372 multi-unit plans / ~85K rooms | R0–R2 auto + **near-R4 from shipped per-room zone labels** | silver corpus + zero-cost rich level | ⬜ not downloaded |
| InstBuild | 5–10 institutional buildings | R0–R4 (gold, hand-annotated) | out-of-regime stress set; S4 scale split; annotation-cost measurement | 🟡 partially unblocked: prelim_rasters FF building = candidate #1; ArchCAD-400K / FloorPlanCAD scouting below (DATA-7) |
| Code corpus (Phase A2) | 1 established dataset | AST → +dataflow → +call (auto) | generality check C5 | ⬜ pending A2-1 decision |

## Institutional-scale candidate sources (scouted 2026-07-14; evaluation = DATA-7)

| Source | Scale & mix | Format / annotations | Access | Fit |
|---|---|---|---|---|
| **ArchCAD-400K** (arXiv 2503.22346, 2025) | 5,538 complete drawings from 11,917 industry drawings; **only 14% residential** — offices, industrial parks, large public buildings | vector CAD primitives with panoptic symbol annotations (56 classes: walls, doors, windows, stairs...); NO room/space polygons shipped | GitHub `ArchiAI-LAB/ArchCAD` (public subset released; license unstated — verify) | Best volume source for the institutional regime (S4). Requires a primitives→room-topology derivation step (shared with DATA-0 lane) |
| **FloorPlanCAD** (ICCV 2021) | 15,000+ plans incl. schools, hospitals, malls, residential towers (100+ projects) | SVG vector, line-grained semantic+instance labels, 30+ classes | floorplancad.github.io + HuggingFace `Voxel51/FloorPlanCAD`; CC BY-NC 4.0 | Established, downloadable now; same rooms-from-primitives derivation need |

Both ship wall/door **primitives**, not room graphs → one shared `drawing→SpectrumGraph`
module (DATA-0) serves prelim rasters AND these CAD corpora. If room derivation proves
robust on FloorPlanCAD's hospitals/schools, InstBuild stops being annotation-bound for
R0–R2 and gold effort concentrates on R3/R4 only.

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

### MSD — Modified Swiss Dwellings
- Source: ECCV 2024 release (check https://caviavart.github.io/msd-dataset/ and the
  4TU/Zenodo mirror). Ships access graphs + per-room **zone labels** on 5,372 plans —
  these auto-derive the near-R4 level (plan Lane 5). License: check on download.
- Loader: `topospec.data.msd` (DATA-3).

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
