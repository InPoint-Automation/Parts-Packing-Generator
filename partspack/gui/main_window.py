# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Main window: ribbon, viewport, param dock, status bar

from __future__ import annotations


from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtWidgets import QMainWindow, QMessageBox

from .. import APP_NAME, __version__
from ..config import load_cfg
from ..project import Project
from ..params import Params
from .bridge import Bridge

from .part_view_mixin import PartViewMixin
from .ribbon_mixin import RibbonMixin
from .param_panel_mixin import ParamPanelMixin
from .project_mixin import ProjectMixin
from .tilt_mixin import TiltMixin
from .actions_mixin import ActionsMixin
from .toast_mixin import ToastMixin
from .build_mixin import BuildMixin


class MainWindow(PartViewMixin, RibbonMixin, ParamPanelMixin, ProjectMixin,
                 TiltMixin, ActionsMixin, ToastMixin, BuildMixin, QMainWindow):
    def __init__(self, cfg=None):
        super().__init__()
        self.cfg = cfg or load_cfg()
        self.params = Params()
        # seed bed from config for over-bed check
        if self.cfg.get("bed_x"):
            self.params.bed_x = float(self.cfg["bed_x"])
        if self.cfg.get("bed_y"):
            self.params.bed_y = float(self.cfg["bed_y"])
        self.project = Project()
        self.project_path = None
        self.bridge = Bridge()
        self._widgets = {}
        self._rows = {}
        self._vis_rules = []
        self._build_thread = None
        self._progress_dialog = None
        self._ghost_active = False
        self._ghost_built = False
        self._rebuild_dirty = False
        self._result_dirty = False
        self._AUTO_MS = 150
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self._auto_rebuild)
        self._TILT_MS = 500
        self._pending_tilt = None
        self._tilt_timer = QTimer(self)
        self._tilt_timer.setSingleShot(True)
        self._tilt_timer.timeout.connect(self._commit_tilt)
        # speculative build: pre-run full tray off-thread while idle, adopt only on exact snapshot match
        self._SPEC_MS = 1200
        self._spec_timer = QTimer(self)
        self._spec_timer.setSingleShot(True)
        self._spec_timer.timeout.connect(self._maybe_speculate)
        self._spec_result = None         # (snapshot, payload) ready to adopt
        self._spec_snapshot = None       # in-flight spec snapshot
        self._pending_generate = False   # Generate queued behind running build

        self.setWindowTitle("%s  v%s" % (APP_NAME, __version__))
        self.resize(1320, 840)

        self._build_central()
        self._build_ribbon()
        self._build_param_panel()
        self._build_project_panel()
        # defer view hide until shown, pre-show hide gives VTK BadWindow
        QTimer.singleShot(0, lambda: self._apply_view_mode("split"))
        self.statusBar().showMessage("Load a STEP part to begin.")


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toast()

    def closeEvent(self, event):
        # block until in-flight build finishes, killing QThread mid-run crashes
        th = getattr(self, "_build_thread", None)
        if th is not None and th.isRunning():
            self.statusBar().showMessage("Finishing build before closing...")
            th.wait()
        # finalize VTK before Qt drops GL context
        for v in (getattr(self, "viewer_part", None), getattr(self, "viewer_tray", None)):
            if v is not None:
                v.shutdown_vtk()
        super().closeEvent(event)


    def _active_viewers(self):
        return [v for v in (self.viewer_part, self.viewer_tray)
                if v.isVisible() and v.plotter is not None]

    def fit(self):
        for v in self._active_viewers():
            v.reset_camera()

    def _zoom(self, factor):
        for v in self._active_viewers():
            v.plotter.camera.zoom(factor)
            v.plotter.render()

    def _reset_view(self):
        for v in self._active_viewers():
            v.plotter.view_isometric()
            v.reset_camera()

    def about(self):
        QMessageBox.information(
            self, "About %s" % APP_NAME,
            "%s v%s\n\nParametric 3D-printable nesting trays that cradle the "
            "bottom band of complex CNC parts.\n\n"
            "GPL v3 or later." % (APP_NAME, __version__))
