"""MSD (Modified Swiss Dwellings, ECCV 2024) loader -> R0-R2 + near-R4.

MSD ships per-room zone labels on 5,372 multi-unit plans (plan §2 Lane 5): these
auto-derive a near-R4 richness level at zero annotation cost — the timeline de-risk.
"""

from pathlib import Path

from topospec.graphs.schema import SpectrumGraph


def build_graphs(raw_dir: Path, out_dir: Path) -> list[SpectrumGraph]:
    raise NotImplementedError(
        "MSD ingest is ROADMAP task DATA-3 (docs/ROADMAP.md): R0-R2 for ~85K rooms "
        "plus near-R4 from shipped zone labels. Acquisition notes in docs/DATA.md."
    )
