# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Pure-shapely web/lattice math + gridfinity foot constants.

from __future__ import annotations

import math


# Gridfinity base profile (42 mm grid unit).
GRID_PITCH = 42.0
_PAD = 41.5
_FOOT_H = 4.75
# (z, side-width, corner-radius) from foot bottom up.
_FOOT_SECTIONS = (
    (0.00, _PAD - 2 * 2.95, 4.0 - 2.95),
    (0.80, _PAD - 2 * 2.15, 4.0 - 2.15),
    (2.60, _PAD - 2 * 2.15, 4.0 - 2.15),
    (4.75, _PAD,            4.0),
)
_MAGNET_INSET = 13.0
_MAGNET_DEPTH = 2.0


def snap_footprint(params, tray_w, tray_h):
    """Round footprint up to whole gridfinity units."""
    if str(params.base_profile) != "gridfinity":
        return tray_w, tray_h
    nx = max(1, math.ceil(tray_w / GRID_PITCH - 1e-6))
    ny = max(1, math.ceil(tray_h / GRID_PITCH - 1e-6))
    return nx * GRID_PITCH, ny * GRID_PITCH


def _gaps(centres_1d, half_extent, keep_out, lo, hi):
    """Open gap intervals between cavity bands and borders."""
    bands = []
    for c in sorted(set(centres_1d)):
        bands.append((c - half_extent - keep_out, c + half_extent + keep_out))
    gaps = []
    cursor = lo
    for b_lo, b_hi in bands:
        if b_lo > cursor:
            gaps.append((cursor, b_lo))
        cursor = max(cursor, b_hi)
    if cursor < hi:
        gaps.append((cursor, hi))
    return [(a, b) for a, b in gaps if b - a > 0.5]


def _hex_tiles(web, params):
    """Hex cells fully inside web polygon."""
    from shapely.geometry import Polygon

    cell = max(2.0, float(params.honeycomb_cell))
    wall = max(0.4, float(params.honeycomb_wall))
    R = cell / math.sqrt(3.0)
    dx = cell + wall
    dy = 1.5 * R + wall
    minx, miny, maxx, maxy = web.bounds

    def hexagon(cx, cy):
        return Polygon([(cx + R * math.cos(math.radians(60 * k - 30)),
                         cy + R * math.sin(math.radians(60 * k - 30)))
                        for k in range(6)])

    hexes = []
    y, j = miny, 0
    while y <= maxy + dy:
        x = minx + ((dx / 2.0) if (j % 2) else 0.0)
        while x <= maxx + dx:
            h = hexagon(x, y)
            if web.contains(h):
                hexes.append(h)
            x += dx
        y += dy
        j += 1
    return hexes


def _tri_tiles(web, params):
    """Equilateral-triangle cells tiling web."""
    from shapely.geometry import Polygon
    s = max(2.0, float(params.honeycomb_cell))
    wall = max(0.4, float(params.honeycomb_wall))
    h = s * math.sqrt(3.0) / 2.0
    minx, miny, maxx, maxy = web.bounds
    out = []
    j = 0
    y = miny
    while y <= maxy + h:
        i = 0
        while minx + i * s <= maxx + s:
            bL = (minx + i * s, y)
            bR = (minx + (i + 1) * s, y)
            tL = (minx + s / 2.0 + i * s, y + h)
            tR = (minx + s / 2.0 + (i + 1) * s, y + h)
            for tri in (Polygon([bL, bR, tL]), Polygon([bR, tR, tL])):
                cell = tri.buffer(-wall / 2.0)
                if not cell.is_empty and web.contains(cell):
                    out.append(cell)
            i += 1
        j += 1
        y = miny + j * h
    return out


def _square_tiles(web, params):
    """Square cells tiling web."""
    from shapely.geometry import box as shp_box
    s = max(2.0, float(params.honeycomb_cell))
    wall = max(0.4, float(params.honeycomb_wall))
    pitch = s + wall
    minx, miny, maxx, maxy = web.bounds
    out = []
    y = miny
    while y <= maxy + pitch:
        x = minx
        while x <= maxx + pitch:
            cell = shp_box(x, y, x + s, y + s)
            if web.contains(cell):
                out.append(cell)
            x += pitch
        y += pitch
    return out


def _round_tiles(web, params):
    """Round holes, hex-packed."""
    from shapely.geometry import Point
    r = max(1.0, float(params.honeycomb_cell) / 2.0)
    wall = max(0.4, float(params.honeycomb_wall))
    dx = 2.0 * r + wall
    dy = dx * math.sqrt(3.0) / 2.0
    minx, miny, maxx, maxy = web.bounds
    out = []
    j = 0
    y = miny + r
    while y <= maxy + dy:
        x = minx + r + ((dx / 2.0) if (j % 2) else 0.0)
        while x <= maxx + dx:
            cell = Point(x, y).buffer(r, quad_segs=20)
            if web.contains(cell):
                out.append(cell)
            x += dx
        j += 1
        y += dy
    return out


def _cell_tiles(web, params):
    """Void cells in chosen cell_shape."""
    shape = str(getattr(params, "cell_shape", "hex"))
    if shape == "triangle":
        return _tri_tiles(web, params)
    if shape == "square":
        return _square_tiles(web, params)
    if shape == "round":
        return _round_tiles(web, params)
    return _hex_tiles(web, params)


def _web_region(centres, params, tray_w, tray_h, cav_w, cav_h):
    """Lightenable web: inner rect minus cavity collars."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    border = float(params.border)
    rim = float(params.rim_width)
    inner = box(-tray_w / 2.0 + border, -tray_h / 2.0 + border,
                tray_w / 2.0 - border, tray_h / 2.0 - border)
    keepouts = [box(cx - cav_w / 2.0 - rim, cy - cav_h / 2.0 - rim,
                    cx + cav_w / 2.0 + rim, cy + cav_h / 2.0 + rim)
                for (cx, cy) in centres]
    return inner.difference(unary_union(keepouts)) if keepouts else inner


def web_region_multi(placements, params, tray_w, tray_h):
    """Web for heterogeneous layout. placements: (cx, cy, w, h)."""
    from shapely.geometry import box
    from shapely.ops import unary_union
    border = float(params.border)
    rim = float(params.rim_width)
    inner = box(-tray_w / 2.0 + border, -tray_h / 2.0 + border,
                tray_w / 2.0 - border, tray_h / 2.0 - border)
    keepouts = [box(cx - w / 2.0 - rim, cy - h / 2.0 - rim,
                    cx + w / 2.0 + rim, cy + h / 2.0 + rim)
                for (cx, cy, w, h) in placements]
    return inner.difference(unary_union(keepouts)) if keepouts else inner


def _flatten_polys(geom, min_area=0.0):
    """Polygons of a (Multi)Polygon, dropping slivers."""
    from shapely.geometry import MultiPolygon
    if geom is None or geom.is_empty:
        return []
    geoms = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    return [g for g in geoms if g.geom_type == "Polygon" and g.area >= min_area]


def _rib_lattice(bounds, params):
    """Rib lattice polygon for pattern, or None."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    minx, miny, maxx, maxy = bounds
    w = max(0.4, float(params.rib_width))
    sp = max(w + 0.5, float(params.rib_spacing))
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    diag = math.hypot(maxx - minx, maxy - miny) + 2 * sp

    lines = []

    def parallels(angle_deg):
        a = math.radians(angle_deg)
        dirx, diry = math.cos(a), math.sin(a)
        nx, ny = -diry, dirx
        k = -diag / 2.0
        while k <= diag / 2.0:
            ox, oy = cx + nx * k, cy + ny * k
            lines.append(LineString([(ox - dirx * diag, oy - diry * diag),
                                     (ox + dirx * diag, oy + diry * diag)]))
            k += sp

    pattern = str(params.rib_pattern)
    if pattern == "diagonal":
        parallels(45); parallels(135)
    elif pattern == "hex":
        parallels(0); parallels(60); parallels(120)
    else:
        parallels(0); parallels(90)
    if not lines:
        return None
    return unary_union(lines).buffer(w / 2.0, cap_style="square")
