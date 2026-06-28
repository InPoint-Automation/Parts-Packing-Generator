# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# grid layout: pitches, centres, margins, bed fit
from __future__ import annotations

from typing import List, Tuple


_MIN_PITCH = 0.5


def _axis_spacing(params) -> Tuple[float, float]:
    """Per-axis gap (X, Y)."""
    sx = params.part_spacing if params.part_spacing_x is None else params.part_spacing_x
    sy = params.part_spacing if params.part_spacing_y is None else params.part_spacing_y
    return float(sx), float(sy)


def pocket_spin(params) -> float:
    """Uniform per-pocket Z-rotation deg, 0 if disabled."""
    return float(params.pocket_rotate_deg) if params.pocket_rotate else 0.0


def margins(params) -> Tuple[float, float, float, float]:
    """Per-side margins (left, right, back +Y, front -Y) mm, uniform border unless margin_advanced."""
    b = float(params.border)
    if not getattr(params, "margin_advanced", False):
        return b, b, b, b
    mx = b if params.margin_x is None else float(params.margin_x)
    my = b if params.margin_y is None else float(params.margin_y)
    mf = b if params.margin_front is None else float(params.margin_front)
    return mx, mx, my, mf


def grid_offset(params) -> Tuple[float, float]:
    """XY grid shift for asymmetric margins, block stays centred, grid slides to leave requested gap each side."""
    left, right, back, front = margins(params)
    return (left - right) / 2.0, (front - back) / 2.0


def _rot_bbox(w: float, h: float, deg: float) -> Tuple[float, float]:
    """Bbox of rotated rect."""
    import math
    if not deg:
        return float(w), float(h)
    t = math.radians(deg)
    c, s = abs(math.cos(t)), abs(math.sin(t))
    return w * c + h * s, w * s + h * c


def _hull_touch(poly, deg):
    """Min non-overlap pitch (X, Y)."""
    from shapely.affinity import rotate, translate
    minx, miny, maxx, maxy = poly.bounds
    if deg:
        poly = rotate(poly, deg, origin=((minx + maxx) / 2.0, (miny + maxy) / 2.0))
        minx, miny, maxx, maxy = poly.bounds

    def touch(ext, horiz):
        lo, hi = 0.0, float(ext) + 1e-6
        for _ in range(40):
            d = (lo + hi) / 2.0
            sh = translate(poly, d, 0) if horiz else translate(poly, 0, d)
            if poly.intersection(sh).area > 1e-9:
                lo = d
            else:
                hi = d
        return hi

    return touch(maxx - minx, True), touch(maxy - miny, False)


def pitches(params, cavity_w: float, cavity_h: float,
            fp_poly=None) -> Tuple[float, float]:
    """Centre-to-centre spacing."""
    sx, sy = _axis_spacing(params)
    deg = pocket_spin(params)
    if str(params.pack_mode) == "hull" and fp_poly is not None:
        try:
            bx, by = _hull_touch(fp_poly, deg)
        except Exception:
            bx, by = _rot_bbox(cavity_w, cavity_h, deg)
    else:
        bx, by = _rot_bbox(cavity_w, cavity_h, deg)
    px = float(params.pitch_x) if params.pitch_x is not None else bx + sx
    py = float(params.pitch_y) if params.pitch_y is not None else by + sy
    return max(_MIN_PITCH, px), max(_MIN_PITCH, py)


def grid_centres(params, cavity_w: float = 0.0, cavity_h: float = 0.0,
                 rows=None, cols=None, fp_poly=None) -> List[Tuple[float, float]]:
    """Cavity centres for rows x cols grid, centred on origin."""
    px, py = pitches(params, cavity_w, cavity_h, fp_poly=fp_poly)
    rows = int(params.rows if rows is None else rows)
    cols = int(params.cols if cols is None else cols)
    stagger = float(params.row_stagger) * px

    ox, oy = grid_offset(params)
    x0 = -(cols - 1) * px / 2.0 + ox
    y0 = -(rows - 1) * py / 2.0 + oy

    centres = []
    for r in range(rows):
        off = stagger * (r % 2) - (stagger / 2.0 if stagger else 0.0)
        for c in range(cols):
            centres.append((x0 + c * px + off, y0 + r * py))
    return centres


def footprint(params, centres, cavity_w: float, cavity_h: float, fp_poly=None):
    """Tray XY footprint (width, height) enclosing all cavities."""
    left, right, back, front = margins(params)
    if not centres:
        return (left + right, back + front)
    ew, eh = _rot_bbox(cavity_w, cavity_h, pocket_spin(params))
    xs = [x for x, _ in centres]
    ys = [y for _, y in centres]
    w = (max(xs) - min(xs)) + ew + left + right
    h = (max(ys) - min(ys)) + eh + back + front
    return (w, h)


def fit_to_bed(params, cavity_w: float, cavity_h: float) -> Tuple[int, int]:
    """Derive rows x cols fitting bed_x x bed_y, returns (rows, cols)."""
    if not params.bed_x or not params.bed_y:
        raise ValueError("fit_to_bed needs bed_x and bed_y")
    px, py = pitches(params, cavity_w, cavity_h)
    left, right, back, front = margins(params)
    usable_x = params.bed_x - (left + right)
    usable_y = params.bed_y - (back + front)
    cols = max(1, int((usable_x - cavity_w) // px) + 1)
    rows = max(1, int((usable_y - cavity_h) // py) + 1)
    return (rows, cols)
