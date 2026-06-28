# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Finger divots + push-from-below holes; placement gates + cutter builders.

from __future__ import annotations

import math


def _inscribed_circle(poly):
    """Largest inscribed circle: (centre, diameter)."""
    from shapely.geometry import Point
    if poly is None or poly.is_empty:
        return None, 0.0
    # collapse raster staircase, estimate needs no precision
    s = poly.simplify(0.2, preserve_topology=True)
    if not s.is_empty:
        poly = s
    minx, miny, maxx, maxy = poly.bounds
    hi = min(maxx - minx, maxy - miny) / 2.0
    lo = 0.0
    best = poly.representative_point()
    for _ in range(24):
        mid = (lo + hi) / 2.0
        eroded = poly.buffer(-mid)
        if not eroded.is_empty:
            lo = mid
            best = eroded.representative_point()
        else:
            hi = mid
    return Point(best.x, best.y), 2.0 * lo


def push_hole_allowed(bottom_section, params):
    """Gate push hole. Returns (allowed, centre_xy, info)."""
    if not params.push_hole or bottom_section is None or bottom_section.is_empty:
        return False, None, "disabled or no bottom section"

    centre, inscribed = _inscribed_circle(bottom_section)
    if inscribed < float(params.push_min_size):
        return False, None, ("part too small: inscribed dia %.1f < push_min_size "
                             "%.1f" % (inscribed, params.push_min_size))
    r = float(params.push_hole_diameter) / 2.0
    margin = max(1.0, 2.0 * float(params.part_clearance))
    from shapely.geometry import Point
    disk = Point(centre.x, centre.y).buffer(r + margin)
    if not disk.within(bottom_section):
        return False, None, "hole does not fit under the part footprint"
    return True, (centre.x, centre.y), "ok (inscribed dia %.1f)" % inscribed


def _slot(hx, hy, r, height, zc, params):
    """Capsule slot: box capped by two cylinders."""
    from build123d import Pos, Cylinder, Box
    length = 2.0 * r
    body = Pos(hx, hy, zc) * Box(length, 2 * r, height)
    c1 = Pos(hx - length / 2.0, hy, zc) * Cylinder(radius=r, height=height)
    c2 = Pos(hx + length / 2.0, hy, zc) * Cylinder(radius=r, height=height)
    return body + c1 + c2


def _ray_radius(poly, ox, oy, theta):
    """Distance to first boundary crossing along theta. Nearest hit, not summed chord (non-convex)."""
    from shapely.geometry import LineString, Point
    minx, miny, maxx, maxy = poly.bounds
    L = 2.0 * (abs(maxx - minx) + abs(maxy - miny)) + 10.0
    ray = LineString([(ox, oy),
                      (ox + L * math.cos(theta), oy + L * math.sin(theta))])
    hits = ray.intersection(poly.boundary)
    if hits.is_empty:
        return 0.0
    origin = Point(ox, oy)
    geoms = getattr(hits, "geoms", [hits])
    dists = [origin.distance(g) for g in geoms if not g.is_empty]
    return min(dists) if dists else 0.0


def _divot_solid(shape, bx, by, theta, depth, z_top, params):
    """One divot cutter on wall point (bx, by)."""
    from build123d import (Pos, Location, Cylinder, Box, Sphere)

    d = float(params.divot_diameter)
    r = d / 2.0
    z_lo = z_top - depth
    h = depth + 1.0
    zc = (z_lo + (z_top + 1.0)) / 2.0
    deg = math.degrees(theta)

    if shape == "round":
        return Pos(bx, by, zc) * Cylinder(radius=r, height=h)
    if shape == "scallop":
        cyl = Pos(bx, by, zc) * Cylinder(radius=r, height=h)
        ball = Pos(bx, by, z_lo) * Sphere(radius=r)
        return cyl + ball
    if shape == "square":
        return Pos(bx, by, zc) * Box(d, d, h)
    if shape == "rect":
        return Location((bx, by, zc), (0, 0, 1), deg) * Box(d * 0.6, d, h)
    if shape == "u_channel":
        box = Location((bx, by, zc), (0, 0, 1), deg) * Box(d * 0.6, d, h)
        floor = Location((bx, by, z_lo), (1, 0, 0), 90) * \
            (Location((0, 0, 0), (0, 0, 1), deg) * Cylinder(radius=r, height=d))
        return box + floor
    return Pos(bx, by, zc) * Cylinder(radius=r, height=h)


def _divot_directions(params):
    """Outward divot direction(s) in radians."""
    if params.divot_angle is not None:
        base = math.radians(float(params.divot_angle))
    else:
        base = 0.0 if str(params.divot_axis) == "X" else math.pi / 2.0

    if int(params.divot_count) >= 2:
        return [base, base + math.pi]
    return [base] if str(params.divot_side) == "pos" else [base + math.pi]


def _point_inside(poly, x, y):
    from shapely.geometry import Point
    return poly.contains(Point(x, y))
