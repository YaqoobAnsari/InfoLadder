"""Y_zone silver lane — RC-network thermal surrogate (plan §3.4, §6 Phase A).

Must be validated against EnergyPlus on the IFC subset at the Gate (G-a: ARI > 0.7)
before silver labels are used for any claim.
"""

from topospec.graphs.schema import SpectrumGraph


def zone_labels(g: SpectrumGraph, **rc_params) -> dict[str, int]:
    raise NotImplementedError(
        "RC surrogate is ROADMAP task A-2, gated by G-a validation (docs/ROADMAP.md)."
    )
