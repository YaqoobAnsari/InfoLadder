"""Shared figure style for all result reports (light theme).

Palette: the validated categorical set from the dataviz reference (fixed slot
order = the CVD-safety mechanism). Probe families map to slots by IDENTITY and
never get repainted when a subset is plotted.
"""

from __future__ import annotations

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
TEXT_MUTED = "#8a887f"
GRID = "#e5e4df"

# categorical slots (validated order — do not shuffle)
_SLOTS = [
    "#2a78d6",  # blue
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
    "#e87ba4",  # magenta
    "#eb6834",  # orange
]

# fixed identity mapping: family -> color (independent of what's plotted)
FAMILY_COLORS = {
    "V0": _SLOTS[3],  # green  — parameter-free readout
    "V1": _SLOTS[2],  # yellow — prior
    "V2": _SLOTS[0],  # blue   — linear
    "V3": _SLOTS[4],  # violet — linear+PE
    "V4": _SLOTS[1],  # aqua   — 1-layer GNN
    "V5": _SLOTS[5],  # red    — 2-layer GNN
    "V6": _SLOTS[7],  # orange — GraphGPS
    "V7": _SLOTS[6],  # magenta — frozen LM
}

FAMILY_ORDER = ["V0", "V1", "V2", "V3", "V4", "V5", "V6", "V7"]


def apply(ax) -> None:
    """Recessive axes: light grid, no top/right spines, secondary-ink labels."""
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)
    ax.xaxis.label.set_color(TEXT_SECONDARY)
    ax.yaxis.label.set_color(TEXT_SECONDARY)
    ax.title.set_color(TEXT_PRIMARY)


def new_figure(nrows: int, ncols: int, cell: tuple[float, float] = (3.4, 2.9)):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(
        nrows, ncols,
        figsize=(cell[0] * ncols, cell[1] * nrows),
        facecolor=SURFACE,
        squeeze=False,
    )
    return fig, axes
