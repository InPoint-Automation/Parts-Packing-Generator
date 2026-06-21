# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Bed-fit math for tiling oversize trays (diagonal fit).

from __future__ import annotations

import math

BED_MARGIN = 5.0


def _fits(w, h, bx, by, steps=181):
    """Does w×h fit in bx×by bed at some rotation?"""
    if w <= bx and h <= by:
        return True
    if w <= by and h <= bx:
        return True
    for k in range(steps):
        t = math.radians(90.0 * k / (steps - 1))
        c, s = abs(math.cos(t)), abs(math.sin(t))
        if w * c + h * s <= bx + 1e-6 and w * s + h * c <= by + 1e-6:
            return True
    return False


def _grid(W, H, bx, by, cap=8):
    """Smallest nx×ny of equal tiles fitting bed. Returns (nx, ny)."""
    best = None
    for nx in range(1, cap + 1):
        for ny in range(1, cap + 1):
            if _fits(W / nx, H / ny, bx, by):
                key = (nx * ny, nx + ny)
                if best is None or key < best[0]:
                    best = (key, nx, ny)
    return (best[1], best[2]) if best else (cap, cap)
