# Local patches to external repos

## tesseract2-5color-tolerance.patch
Applied to ../Tesseract2/utils/Improve.py on 2026-07-15 (uncommitted in that clone).
classify_doors previously required exactly 5 palette colours in the segmented map;
plans lacking a region class (no corridor / no balcony — ~36% of MSD) crashed before
producing graphs. The patch tolerates palette SUBSETS while still rejecting
off-palette images loudly. Verified end-to-end on msd_2296 (previously crashed).
Candidate for upstreaming to github.com/YaqoobAnsari/Tesseract2 — user's call.
