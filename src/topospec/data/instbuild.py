"""InstBuild gold institutional set -> R0-R4 (plan §6 Phase A; the stress set).

Blocked on source selection (plan §14.1 / ROADMAP DATA-5). Gold R4 annotations are
human-made per the annotation guide (ROADMAP A-7) with timing sheets feeding claim C3.
"""

from pathlib import Path

from topospec.graphs.schema import SpectrumGraph


def build_graphs(raw_dir: Path, out_dir: Path) -> list[SpectrumGraph]:
    raise NotImplementedError(
        "InstBuild ingest is ROADMAP task DATA-5/DATA-6 (docs/ROADMAP.md), blocked on "
        "institutional building sourcing (open question plan §14.1)."
    )
