# Textless raster → pseudo room-label lane — model survey (D-014)

**Date:** 2026-07-14 · **Scout:** cad-scout · **Report only (no code).**
Goal: pick a model that labels rooms on floorplan RASTERS **without text**, to pseudo-
label CAD-style renders (FloorPlanCAD, our MSD render lane) at scale for the
Tesseract2 pipeline, scored against MSD's shipped ground-truth graphs.

## Headline finding (matters for the D-014 plan)

There are two model families, and they consume **different input modalities**:

- **Reconstruction / vectorization** (RoomFormer, HEAT, PolyRoom, CAGE): input is a
  **point-density image projected from a 3D point cloud**; output is vector room
  polygons. Their released weights are trained on Structured3D / SceneCAD density
  maps — **NOT floorplan drawings**. On a CAD line-drawing or a scanned plan they
  are out-of-distribution and would need retraining.
- **Semantic segmentation** (Deep Floor Plan Recognition, CubiCasa5k model, and the
  2024-25 successors): input is a **raster floorplan IMAGE/drawing**; output is a
  per-pixel room-type + wall/opening map. This is the modality that matches our
  rasters (FloorPlanCAD renders, MSD renders, scanned plans).

**So the D-014 phrase "RoomFormer-class pseudo-labels" is a modality mismatch for our
data.** RoomFormer-class is right only if the raster is a 3D-scan density map; for
floorplan DRAWINGS the segmentation family is the correct pick. (RoomFormer-class
becomes relevant if/when a 3D-scan corpus enters, or if we retrain one on rasterized
floorplans — a real project, not a drop-in.)

## Candidates

| Model | Input | Output | Weights | License | Fit: CAD renders / scans |
|---|---|---|---|---|---|
| **CubiCasa5k model** (floortrans, Kalervo 2019) | raster floorplan image | multi-task seg: room types + wall/rail + icons (door/window) | ✅ PyTorch ckpt in repo | code Apache-ish (verify repo `LICENSE`); trained on CubiCasa5k data = **CC BY-NC-SA 4.0** (non-commercial) | **Best.** Trained on real scanned plans; transfers to clean CAD line-art; taxonomy already has rooms+doors+windows |
| **Deep Floor Plan Recognition / DFPR** (Zeng ICCV 2019, `zlzeng/DeepFloorplan`; TF2 port `zcemycl/TF2DeepFloorplan`) | raster floorplan image | room-boundary (wall/door/window) + room-type seg | ✅ (download link in repo) | check repo; research use | Good on clean plans; fewer room classes; TF1 (port is TF2). Solid simple baseline |
| **Multibranch/Multiattention seg** (De Nardin, CACIE 2025) | raster floorplan image | room seg (SOTA on R2V/R3D) | paper-stage (verify) | verify | Likely strong but no confirmed drop-in weights yet |
| **SAM-based few-shot seg** (Sci.Direct 2024; "Segment Anything in Architecture" 2025) | raster + prompts | room masks (class-agnostic) | SAM weights ✅ | Apache-2.0 (SAM) | Class-agnostic masks need a labeler on top; useful fallback for odd styles |
| **RoomFormer** (CVPR 2023, `ywyue/RoomFormer`) | **3D-scan density image** | room polygons (+opt types/doors) | ✅ MIT (code+weights) | MIT | **Modality mismatch** for drawings; retrain needed |
| **HEAT** (CVPR 2022, `woodfrog/heat`) | density image / raster | planar graph (corners+edges) | ✅ | check | Mismatch (floorplan variant uses density) |
| **PolyRoom** (ECCV 2024, `3dv-casia/PolyRoom`) | **3D-scan density image** | room polygons (RoomFormer successor, better) | ✅ code | check | Mismatch; best-in-class IF we go density-map route |
| **CAGE** (2025, `ee-Liu/CAGE`) | 3D-scan density image | robust room polygons (newest) | ✅ code | check | Mismatch; newest reconstruction SOTA |

## Recommendation: integrate the **CubiCasa5k model** first

Reasons: (1) correct input modality — raster floorplan drawings, exactly our
FloorPlanCAD/MSD renders and scanned plans; (2) pretrained PyTorch weights (fits the
`topofield` torch env, no TF); (3) its taxonomy already emits the elements Tesseract
needs downstream — room polygons with types, plus wall and **door/window** channels —
so it can seed room labels AND opening hints on textless rasters; (4) we already
scouted its SVG format (DATA-2 planning) so ground-truth alignment is understood.
Runner-up: **DFPR/TF2DeepFloorplan** as a simpler second opinion. Defer RoomFormer-
class unless a 3D-scan corpus appears or we commit to retraining on rasterized plans.

License caveat: CubiCasa data is **CC BY-NC-SA 4.0** (non-commercial + share-alike);
fine for academic research, but record it in DECISIONS before any release, and prefer
the model *weights'* license over the dataset's where they differ (verify at integration).

## Evaluation protocol (we have MSD ground truth)

1. **Textless render set.** Re-render N MSD plans (reuse `scripts/render_msd_rasters.py`
   with a `--no-text` flag) → walls-only rasters. Keep the shipped MSD graph as truth
   (room polygons + `room_type` + access edges). Optionally add FloorPlanCAD renders
   for CAD-style stress (no truth there → qualitative only).
2. **Run the model** → predicted room masks + room-type per pixel.
3. **Match & score** predicted rooms ↔ MSD truth rooms by mask IoU (Hungarian):
   - room detection: precision/recall/F1 at IoU≥0.5 (room count fidelity);
   - room-type accuracy on matched rooms (map CubiCasa's ~60 types → MSD's 9 via a
     fixed lookup, since our tiers only need the coarse type);
   - topology: adjacency/access-edge agreement vs MSD edges (does the pseudo-graph
     preserve the access structure the tiers depend on?).
4. **Gate.** Adopt for the scale lane only if matched-room room-type accuracy and
   room-detection F1 clear a bar the lead sets (suggest ≥0.8 F1, ≥0.7 type acc on the
   MSD-render set) — otherwise fall back to text-carrying renders + Tesseract CRAFT,
   or SAM-masks + a small type classifier.
5. Heavy inference (batched over the corpus) runs via sbatch on gpu2; a 20-plan
   smoke set runs on the login node.

## Sources
- RoomFormer: https://github.com/ywyue/RoomFormer (MIT; density-image input, room polygons)
- HEAT: https://github.com/woodfrog/heat · https://heat-structured-reconstruction.github.io/
- PolyRoom (ECCV24): https://github.com/3dv-casia/PolyRoom
- CAGE (2025): https://github.com/ee-Liu/CAGE
- DFPR (ICCV19): https://github.com/zlzeng/DeepFloorplan · TF2: https://github.com/zcemycl/TF2DeepFloorplan
- CubiCasa5k model+data: https://github.com/CubiCasa/CubiCasa5k · https://zenodo.org/record/2613548 (CC BY-NC-SA 4.0)
- Multibranch seg 2025: https://onlinelibrary.wiley.com/doi/10.1111/mice.70030
- SAM-for-floorplans 2024: https://www.sciencedirect.com/science/article/pii/S2772991524000562
