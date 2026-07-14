"""IndoorGML export for R1+ (plan Appendix B; the standards hook, claim C1/T5)."""

from topospec.graphs.schema import SpectrumGraph


def to_indoorgml(g: SpectrumGraph) -> str:
    raise NotImplementedError(
        "IndoorGML serializer is ROADMAP task INFRA-9 (docs/ROADMAP.md). "
        f"Requested for building {g.building_id!r} at R{g.level}."
    )
