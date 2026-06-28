# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Heterogeneous drawer: shelf-pack different parts' cavities into one base block.

from __future__ import annotations

import math
from typing import List, Tuple


def pack(items, params, max_w=None) -> List[Tuple]:
    """Shelf-pack axis-aligned cavities; items=(key,w,h) -> [(key,cx,cy,w,h)]."""
    from . import array
    items = list(items)
    if not items:
        return []
    sp = float(getattr(params, "drawer_pack_gap", None) or params.part_spacing)
    left, right, back, front = array.margins(params)

    if max_w is None:
        if getattr(params, "bed_x", None):
            max_w = max(float(params.bed_x) - (left + right), 1.0)
        else:
            widest = max(w for _, w, _ in items)
            total = sum(w + sp for _, w, _ in items)
            ncol = max(1, int(round(math.sqrt(len(items)))))
            max_w = max(widest, total / ncol)

    order = sorted(range(len(items)), key=lambda i: -items[i][2])

    placements = []
    x_cursor = 0.0
    row_bottom = 0.0
    row_h = 0.0
    for i in order:
        key, w, h = items[i]
        if x_cursor > 0.0 and x_cursor + w > max_w:    # wrap
            row_bottom += row_h + sp
            x_cursor = 0.0
            row_h = 0.0
        cx = x_cursor + w / 2.0
        cy = row_bottom + h / 2.0
        placements.append([key, cx, cy, w, h])
        x_cursor += w + sp
        row_h = max(row_h, h)

    # center then grid offset
    minx = min(p[1] - p[3] / 2.0 for p in placements)
    maxx = max(p[1] + p[3] / 2.0 for p in placements)
    miny = min(p[2] - p[4] / 2.0 for p in placements)
    maxy = max(p[2] + p[4] / 2.0 for p in placements)
    ox, oy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    gx, gy = array.grid_offset(params)
    for p in placements:
        p[1] -= ox - gx
        p[2] -= oy - gy
    return [tuple(p) for p in placements]


def _drawer_footprint(placements, params):
    """(w, h) enclosing all cavities plus per-side margins."""
    from . import array
    left, right, back, front = array.margins(params)
    minx = min(cx - w / 2.0 for _, cx, cy, w, h in placements)
    maxx = max(cx + w / 2.0 for _, cx, cy, w, h in placements)
    miny = min(cy - h / 2.0 for _, cx, cy, w, h in placements)
    maxy = max(cy + h / 2.0 for _, cx, cy, w, h in placements)
    return (maxx - minx + left + right, maxy - miny + back + front)


def build_drawer(project, progress=None):
    """Pack all entries' cavities into one drawer block -> BuildResult."""
    from . import io, orient, base, meshbool
    from .pipeline import BuildResult, _Reporter

    entries = [e for e in project.entries if e.step_path]
    if not entries:
        raise ValueError("project has no parts to pack")
    dp = project.drawer

    rep = _Reporter(progress, total=len(entries) + 5)
    result = BuildResult()

    # carve each part once
    groups = []
    for e in entries:
        rep.step("Capturing %s..." % e.name())
        ep = e.params
        oriented, info = orient.orient_solid(io.import_step(e.step_path), ep)
        cap = meshbool.carve_cavity(oriented, info, ep)
        x0, y0, x1, y1 = cap["fp_bounds"]
        if cap.get("world_placed"):                # world-placed
            zlift = 0.0
            block_top = float(cap["placed_block_top"])
        else:
            zlift = float(info.get("world_z_offset", ep.bottom_margin))
            block_top = float(ep.bottom_margin) + float(ep.hold_height)
        groups.append({"entry": e, "cap": cap, "w": x1 - x0, "h": y1 - y0,
                       "fxy": ((x0 + x1) / 2.0, (y0 + y1) / 2.0),
                       "count": max(1, int(e.count)), "zlift": zlift,
                       "block_top": block_top, "oriented": oriented})

    items = []
    for gi, g in enumerate(groups):
        items.extend((gi, g["w"], g["h"]) for _ in range(g["count"]))
    rep.step("Packing %d cavities..." % len(items))
    placements = pack(items, dp)

    tray_w, tray_h = _drawer_footprint(placements, dp)
    tray_w, tray_h = base.snap_footprint(dp, tray_w, tray_h)

    if getattr(dp, "bed_x", None) and tray_w > float(dp.bed_x) + 1e-6:
        result.warnings.append(
            "drawer %.0f mm wide exceeds bed X %.0f mm" % (tray_w, dp.bed_x))
    if getattr(dp, "bed_y", None) and tray_h > float(dp.bed_y) + 1e-6:
        result.warnings.append(
            "drawer %.0f mm deep exceeds bed Y %.0f mm" % (tray_h, dp.bed_y))

    block_top = max(g["block_top"] for g in groups)
    rep.step("Building drawer block...")
    tray = meshbool.box(tray_w, tray_h, block_top, center=(0, 0, block_top / 2.0))

    box_placements = []
    group_centres = [[] for _ in groups]
    for (gi, cx, cy, w, h) in placements:
        g = groups[gi]
        fx, fy = g["fxy"]
        tray = tray - g["cap"]["cavity"].translate([cx - fx, cy - fy, g["zlift"]])
        box_placements.append((cx, cy, w, h))
        group_centres[gi].append((cx, cy))

    rep.step("Lightening web...")
    web = base.web_region_multi(box_placements, dp, tray_w, tray_h)
    tray = meshbool.lighten_web(tray, web, dp, block_top)
    if str(dp.base_profile) == "gridfinity":
        tray = meshbool._gridfinity_feet(tray, tray_w, tray_h, dp)

    # reliefs per group, force 'all' divots
    rep.step("Adding reliefs...")
    for gi, g in enumerate(groups):
        ep = g["entry"].params
        centres = group_centres[gi]
        if not centres:
            continue
        fx, fy = g["fxy"]
        if ep.push_hole:
            tray, n_holes, info = meshbool.add_push_holes(
                tray, centres, g["cap"]["bottom_sec"], fx, fy, ep)
            if n_holes == 0:
                result.warnings.append(
                    "%s: push holes skipped (%s)" % (g["entry"].name(), info))
        if ep.finger_divot:
            ep_all = ep.model_copy(update={"divot_strategy": "all"})
            tray, _ = meshbool.add_finger_divots(
                tray, g["cap"]["fp_poly"], centres, ep_all)

    tray = meshbool.add_label(tray, project.name, dp)
    result.trays = [tray]
    result.oriented_part = groups[0]["oriented"]
    result.cavity = groups[0]["cap"]["cavity"]
    if dp.bed_split:
        tiles = []
        for t in result.trays:
            tiles.extend(meshbool.bed_split(t, dp))
        result.tiles = tiles
        if len(tiles) > len(result.trays):
            result.warnings.append("bed-split into %d tiles" % len(tiles))
    rep.done("Drawer ready (%d parts, %d cavities)."
             % (len(groups), len(placements)))
    return result
