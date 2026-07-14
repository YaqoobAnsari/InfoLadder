"""IFC spatial-structure export for R4 with IfcZone groups (plan Appendix B)."""

from topospec.graphs.schema import SpectrumGraph


def to_ifc_spatial(g: SpectrumGraph) -> bytes:
    raise NotImplementedError(
        "IFC serializer is ROADMAP task INFRA-9 (docs/ROADMAP.md). "
        f"Requested for building {g.building_id!r} at R{g.level}."
    )
