# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Thin synchronous façade between GUI and core.pipeline.

from __future__ import annotations

from ..core import pipeline


class Bridge:
    """Single place GUI calls into core. Synchronous; run on worker thread."""

    def __init__(self):
        self.step_path = None
        self.part = None
        self.result = None
        self.batch = None

    def load_part(self, step_path: str):
        """Load STEP, remember path."""
        from ..core import io, meshbool
        meshbool.clear_cache()
        self.step_path = step_path
        self.result = None
        self.part = io.import_step(step_path)
        return self.part

    def build(self, params, progress=None):
        """Run pipeline."""
        if not self.step_path:
            raise ValueError("no part loaded")
        self.result = pipeline.build(params, self.step_path, progress=progress,
                                     part=self.part)
        self.batch = None
        return self.result

    def build_ghost(self, params, progress=None):
        """Build cavity ghost overlay; does not touch self.result."""
        if not self.step_path:
            raise ValueError("no part loaded")
        return pipeline.build_cavity_preview(params, self.step_path,
                                             progress=progress, part=self.part)

    def build_drawer(self, project, progress=None):
        """Pack project parts into one drawer."""
        from ..core import drawer
        self.result = drawer.build_drawer(project, progress=progress)
        self.batch = None
        return self.result

    def build_batch(self, project, progress=None):
        """Build each entry as its own tray."""
        self.batch = pipeline.build_project_batch(project, progress=progress)
        self.result = None
        return self.batch
