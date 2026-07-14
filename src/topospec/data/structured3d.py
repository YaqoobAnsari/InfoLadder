"""Structured3D loader -> SpectrumGraph R0-R2 (plan §6 Phase A; ~3.5K scenes)."""

from pathlib import Path

from topospec.graphs.schema import SpectrumGraph


def build_graphs(raw_dir: Path, out_dir: Path) -> list[SpectrumGraph]:
    raise NotImplementedError(
        "Structured3D ingest is ROADMAP task DATA-1 (docs/ROADMAP.md); acquisition "
        "notes in docs/DATA.md. Parse room polygons + door annotations, emit R2, "
        "validate, then forget() down for R1/R0."
    )
