# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Params -> finished tray solid(s). Single entry for GUI and CLI. Carve-direct.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from . import profiling


@dataclass
class BuildResult:
    """Build output: trays (one or [bottom, top]) plus tiles."""
    trays: list = field(default_factory=list)
    tiles: list = field(default_factory=list)
    oriented_part: Optional[object] = None
    cavity: Optional[object] = None
    to_part: Optional[object] = None          # oriented->part 4x4
    to_oriented: Optional[object] = None       # part->oriented 4x4
    part_place: Optional[object] = None
    part_slide_dir: tuple = (0.0, 0.0, 1.0)
    warnings: List[str] = field(default_factory=list)


class _Reporter:
    """Drip-feeds stage progress to callback."""

    def __init__(self, cb, total):
        self.cb = cb or (lambda frac, msg: None)
        self.total = max(1, total)
        self.i = 0

    def step(self, msg):
        self.i += 1
        self.cb(min(1.0, self.i / self.total), msg)

    def done(self, msg="Done."):
        self.cb(1.0, msg)


def build(params, step_path: str, progress=None, part=None) -> BuildResult:
    """Carve-direct build. part = optional pre-loaded part."""
    from . import io, meshbool

    rep = _Reporter(progress, total=3)
    prof = profiling.Profiler(
        "build %dx%d q=%s%s"
        % (int(params.rows), int(params.cols), str(params.capture_quality),
           " two-sided" if params.two_sided else ""))

    result = BuildResult()
    rep.step("Importing STEP part…")
    if part is None:
        with prof.stage("import_step"):
            part = io.import_step(step_path)

    rep.step("Carving…")
    with prof.stage("carve trays [mesh]"):
        carved = meshbool.build_result_trays(
            part, params, _label_text(params, step_path))
    result.oriented_part = carved.oriented
    result.cavity = carved.cavity
    result.trays = carved.trays
    result.to_oriented = carved.to_oriented
    result.part_place = carved.part_place
    result.part_slide_dir = getattr(carved, "slide_dir", (0.0, 0.0, 1.0))

    with prof.stage("bed_split"):
        _maybe_bed_split(meshbool, result.trays, params, result)
    rep.done("Tray ready (carve-direct).")
    prof.dump()
    return result


def build_cavity_preview(params, step_path: str, progress=None,
                         part=None, px=None) -> BuildResult:
    """Single full-depth cavity ghost for stage-3 overlay. px = coarse pitch."""
    from . import io, meshbool, heightcapture

    # ~4x coarser than export carve.
    if px is None:
        px = heightcapture._pixel_size(params) * 4.0
    prof = profiling.Profiler("ghost px=%.2f" % float(px))
    rep = _Reporter(progress, total=3)
    result = BuildResult()
    rep.step("Importing STEP part…")
    if part is None:
        with prof.stage("import_step"):
            part = io.import_step(step_path)

    rep.step("Carving cavity…")
    with prof.stage("carve cavity [mesh]"):
        oriented, cav, to_part = meshbool.ghost_cavity_cached(part, params, px)
    result.oriented_part = oriented
    result.cavity = cav
    result.to_part = to_part
    rep.done("Cavity ghost ready (carve-direct).")
    prof.dump()
    return result


def build_project_batch(project, progress=None):
    """Build each project entry as own single-part tray."""
    entries = [e for e in project.entries if e.step_path]
    rep = _Reporter(progress, total=max(1, len(entries)))
    out = []
    for e in entries:
        rep.step("Building %s…" % e.name())
        out.append((e, build(e.params, e.step_path)))
    rep.done("Batch built %d tray set(s)." % len(out))
    return out


def _maybe_bed_split(splitter, trays, params, result):
    """Tile each tray to bed when bed_split on."""
    if not params.bed_split:
        return
    tiles = []
    for tray in trays:
        tiles.extend(splitter.bed_split(tray, params))
    result.tiles = tiles
    if len(tiles) > len(trays):
        result.warnings.append("bed-split into %d tiles" % len(tiles))
    elif not (params.bed_x and params.bed_y):
        result.warnings.append("bed-split on but no bed size set")


def _label_text(params, step_path):
    """Label text: explicit, else STEP filename."""
    t = (params.label_text or "").strip()
    if t:
        return t
    import os
    return os.path.splitext(os.path.basename(step_path))[0]
