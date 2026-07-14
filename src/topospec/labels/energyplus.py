"""Y_zone gold lane — EnergyPlus + bim2sim on the IFC subset (plan §3.4, §6)."""

from pathlib import Path


def zone_labels_from_ifc(ifc_path: Path, workdir: Path) -> dict[str, int]:
    raise NotImplementedError(
        "EnergyPlus lane is ROADMAP task A-5 (docs/ROADMAP.md); install notes in "
        "docs/DATA.md (External simulators)."
    )
