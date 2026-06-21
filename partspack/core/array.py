# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
from __future__ import annotations

from typing import List, Tuple


def pitches(params, cavity_w: float, cavity_h: float) -> Tuple[float, float]:
    """Centre-to-centre spacing in X, Y."""
    px = params.pitch_x if params.pitch_x is not None else cavity_w + params.part_spacing
    py = params.pitch_y if params.pitch_y is not None else cavity_h + params.part_spacing
    return float(px), float(py)


def grid_centres(params, cavity_w: float = 0.0, cavity_h: float = 0.0,
                 rows=None, cols=None) -> List[Tuple[float, float]]:
    """Cavity centres for rows×cols grid, centred on origin."""
    px, py = pitches(params, cavity_w, cavity_h)
    rows = int(params.rows if rows is None else rows)
    cols = int(params.cols if cols is None else cols)
    stagger = float(params.row_stagger) * px

    x0 = -(cols - 1) * px / 2.0
    y0 = -(rows - 1) * py / 2.0

    centres = []
    for r in range(rows):
        off = stagger * (r % 2) - (stagger / 2.0 if stagger else 0.0)
        for c in range(cols):
            centres.append((x0 + c * px + off, y0 + r * py))
    return centres


def pocket_angles(params, rows, cols) -> List[float]:
    """Per-pocket Z-rotation (degrees), row-major like grid_centres."""
    rows = int(rows)
    cols = int(cols)
    if not params.pocket_rotate:
        return [0.0] * (rows * cols)
    deg = float(params.pocket_rotate_deg)
    pat = str(params.pocket_rotate_pattern)

    def rotated(r, c):
        if pat == "alt_rows":
            return r % 2 == 1
        if pat == "checker":
            return (r + c) % 2 == 1
        return c % 2 == 1

    return [deg if rotated(r, c) else 0.0
            for r in range(rows) for c in range(cols)]


def footprint(params, centres, cavity_w: float, cavity_h: float):
    """Tray XY footprint (width, height) enclosing all cavities."""
    if not centres:
        return (2 * params.border, 2 * params.border)
    xs = [x for x, _ in centres]
    ys = [y for _, y in centres]
    w = (max(xs) - min(xs)) + cavity_w + 2 * params.border
    h = (max(ys) - min(ys)) + cavity_h + 2 * params.border
    return (w, h)


def fit_to_bed(params, cavity_w: float, cavity_h: float) -> Tuple[int, int]:
    """Derive rows×cols fitting bed_x×bed_y. Returns (rows, cols)."""
    if not params.bed_x or not params.bed_y:
        raise ValueError("fit_to_bed needs bed_x and bed_y")
    px, py = pitches(params, cavity_w, cavity_h)
    usable_x = params.bed_x - 2 * params.border
    usable_y = params.bed_y - 2 * params.border
    cols = max(1, int((usable_x - cavity_w) // px) + 1)
    rows = max(1, int((usable_y - cavity_h) // py) + 1)
    return (rows, cols)
