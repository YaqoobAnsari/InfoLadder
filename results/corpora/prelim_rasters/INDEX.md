# prelim_rasters — corpus index

Tiers T0–T3 derived from the user's annotated sheets via the Tesseract2
pipeline (D-014). Every building folder holds the bare floorplan, the four
tier JSONs, per-tier graph overlays, and a report card.

| building | T3 summary | provenance | report |
|---|---|---|---|
| FF_part_1up | 40 spaces · 38 doors · 78 edges | fresh (batch 7215) | [report](FF_part_1up/report.md) |
| FF_part_1upE | 42 spaces · 38 doors · 79 edges | fresh (batch 7215) | [report](FF_part_1upE/report.md) |
| FF_part_2up | 43 spaces · 39 doors · 80 edges | fresh (batch 7215) | [report](FF_part_2up/report.md) |
| FF_part_3up | 31 spaces · 33 doors · 70 edges | fresh (batch 7215) | [report](FF_part_3up/report.md) |
| FF_part_3upE | 30 spaces · 32 doors · 68 edges | fresh (batch 7215) | [report](FF_part_3upE/report.md) |
| FF_part_4up | 18 spaces · 17 doors · 34 edges | fresh (batch 7215) | [report](FF_part_4up/report.md) |
| FF_part_5up | 6 spaces · 0 doors · 5 edges | fresh (batch 7215) | [report](FF_part_5up/report.md) |
| FF_part_6up | 24 spaces · 21 doors · 47 edges | fresh (batch 7215) | [report](FF_part_6up/report.md) |
| FF_part_7up | 19 spaces · 10 doors · 30 edges | fresh (batch 7215) | [report](FF_part_7up/report.md) |
| FF_part_8up | FAILED: subnode room_17_subnode_1: missing parent_room_id | — | [report](FF_part_8up/report.md) |
| SF_part_1upE | 42 spaces · 38 doors · 79 edges | fresh (batch 7215) | [report](SF_part_1upE/report.md) |
| file_1 | 4 spaces · 4 doors · 7 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_1/report.md) |
| file_10 | 3 spaces · 2 doors · 4 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_10/report.md) |
| file_2 | 4 spaces · 4 doors · 7 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_2/report.md) |
| file_3 | 7 spaces · 6 doors · 12 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_3/report.md) |
| file_4 | 4 spaces · 4 doors · 7 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_4/report.md) |
| file_5 | 4 spaces · 4 doors · 7 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_5/report.md) |
| file_6 | 5 spaces · 3 doors · 7 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_6/report.md) |
| file_7 | 7 spaces · 2 doors · 8 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_7/report.md) |
| file_8 | 4 spaces · 3 doors · 6 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_8/report.md) |
| file_9 | 5 spaces · 4 doors · 8 edges | pre-existing pipeline artifact (older weights) — rerun pending | [report](file_9/report.md) |

_Regenerate: `scripts/build_corpus_results.py` (after each Tesseract batch)._
