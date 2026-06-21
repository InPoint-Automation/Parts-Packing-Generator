# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Sandwich top tray + registration pins + closure. Pattern symmetric about X, asymmetric about Y.

from __future__ import annotations


def _reg_points(tray_w, tray_h, params):
    """Corner registration points, symmetric about X, keyed asymmetric about Y."""
    import math
    pin_r = float(params.pin_diameter) / 2.0
    rk = pin_r + float(params.pin_clearance) + 1.5
    wall = float(params.wall_thickness)
    hw, hh = tray_w / 2.0, tray_h / 2.0
    a = hw - wall - rk
    b = hh - wall - rk
    if a <= 0 or b <= 0:
        return []
    # Slide back inside rounded corner so footprint stays on material.
    fillet = max(0.0, float(getattr(params, "corner_fillet", 0.0)))
    cx, cy = hw - fillet, hh - fillet
    if fillet > 1e-6 and a > cx and b > cy:
        dx, dy = a - cx, b - cy
        d = math.hypot(dx, dy)
        lim = max(0.0, fillet - rk)
        if d > lim and d > 1e-9:
            s = lim / d
            a, b = cx + dx * s, cy + dy * s
    key = min(5.0, a * 0.5)                                  # Y-asymmetry offset
    pts = [(a, b), (a, -b), (-a + key, b), (-a + key, -b)]
    n = max(0, min(int(params.pin_count), 4))
    return pts[:n]


def _pin_feature(x, y, block_top, params):
    """(male_solid, female_solid) for straight cylindrical pin."""
    from build123d import Pos, Cylinder, Cone
    r = float(params.pin_diameter) / 2.0
    depth = float(params.pin_depth)
    clr = float(params.pin_clearance)
    male = Pos(x, y, block_top + depth / 2.0) * Cylinder(radius=r, height=depth)
    if params.pin_taper:                       # lead-in tip
        tip_h = min(depth * 0.4, r)
        male = male + Pos(x, y, block_top + depth) * \
            Cone(bottom_radius=r, top_radius=r * 0.5, height=tip_h)
    hd = depth + 0.5
    female = Pos(x, y, block_top + 0.25 - hd / 2.0) * \
        Cylinder(radius=r + clr, height=hd)
    return male, female


def _taper_feature(x, y, block_top, params):
    """(male, female) conical taper boss + socket."""
    from build123d import Pos, Cone
    r = float(params.pin_diameter) / 2.0
    rt = max(0.75, r * float(params.pin_tip_ratio))   # top radius
    depth = float(params.pin_depth)
    clr = float(params.pin_clearance)
    male = Pos(x, y, block_top + depth / 2.0) * \
        Cone(bottom_radius=r, top_radius=rt, height=depth)
    hd = depth + 0.5
    female = Pos(x, y, block_top + 0.25 - hd / 2.0) * \
        Cone(bottom_radius=rt + clr, top_radius=r + clr, height=hd)
    return male, female
