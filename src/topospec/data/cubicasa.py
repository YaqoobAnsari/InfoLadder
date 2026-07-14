"""CubiCasa5K loader -> SpectrumGraph R0-R2 (plan §6 Phase A; ~25K rooms)."""

from pathlib import Path

from topospec.graphs.schema import SpectrumGraph


def build_graphs(raw_dir: Path, out_dir: Path) -> list[SpectrumGraph]:
    raise NotImplementedError(
        "CubiCasa5K ingest is ROADMAP task DATA-2 (docs/ROADMAP.md); parse the SVG "
        "annotations. Acquisition notes in docs/DATA.md."
    )
