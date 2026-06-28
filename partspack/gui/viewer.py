# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# 3D viewport over pyvistaqt QtInteractor, assembled from concern mixins.

import os

os.environ.setdefault("QT_API", "pyside6")  # before pyvistaqt imports qtpy

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from .viewer_common import HAVE_PYVISTA, QtInteractor, _PYVISTA_ERR, _opengl_usable
from .scene_mixin import SceneMixin
from .clip_mixin import ClipMixin
from .translate_gizmo_mixin import TranslateGizmoMixin
from .gizmo_common_mixin import GizmoCommonMixin
from .camera_mixin import CameraMixin
from .slide_mixin import SlideMixin
from .ring_gizmo_mixin import RingGizmoMixin
from .tilt_gizmo_mixin import TiltGizmoMixin
from .spin_gizmo_mixin import SpinGizmoMixin


class Viewer(SceneMixin, ClipMixin, TranslateGizmoMixin, GizmoCommonMixin,
             CameraMixin, SlideMixin, RingGizmoMixin, TiltGizmoMixin,
             SpinGizmoMixin, QWidget):
    """3D viewport widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.plotter = None
        self._vtk_ready = False
        self._part_mesh = None
        self._seating_dir = (0.0, 0.0, 1.0)
        self._hold = 8.0                  # hold_height
        self._part_color = "#9fb3d1"
        self._part_actor = None
        self._edge_actor = None          # body wireframe (rotates with body)
        self._cav_mesh = None            # part frame
        self._cav_on = False
        self._cav_actor = None
        self._cav2_mesh = None           # top half (part frame)
        self._cav2_on = False
        self._cav2_band = 0.0            # top cradle depth (mm)
        self._cav2_actor = None
        self._section_on = False
        self._section_actor = None
        self._tr3d_on = False            # height translate gizmo
        self._tr3d_cb = None
        self._tr3d_actors = []
        self._tr3d_obs = []
        self._tr3d_dragging = False
        self._tr3d_hover = False
        self._tr3d_saved_style = None
        self._tr3d_grab_A = None
        self._tr3d_grab_proj0 = 0.0
        self._tr3d_grab_tc0 = 0.0
        self._tr3d_start_P = None
        self._drag_planes = []           # GPU clip planes live during a drag
        self._gizmo_cam_obs = None
        self._overlay_ren = None
        self._overlay_tried = False
        self._section_timer = QTimer(self)
        self._section_timer.setSingleShot(True)
        self._section_timer.timeout.connect(self._reclip_part)
        self._suspend_render = False
        self._peeling = False            # depth-peeling enabled once per scene
        self._clip_cache = {}            # (id(mesh),normal,origin) -> (mesh,res)
        self._giz_pending = set()
        self._giz_timer = QTimer(self)   # coalesce gizmo redraws to frame rate
        self._giz_timer.setSingleShot(True)
        self._giz_timer.timeout.connect(self._giz_flush)
        self._ghost_timer = QTimer(self)  # debounce live cavity ghost on drag
        self._ghost_timer.setSingleShot(True)
        self._ghost_timer.timeout.connect(self._ghost_flush)
        self._slide_mesh = None          # tray world coords
        self._slide_dir = (0.0, 0.0, 1.0)
        self._slide_dist = 0.0
        self._slide_actor = None
        self._slide_popped = False
        self._slide_i = 0
        self._slide_timer = QTimer(self)
        self._slide_timer.timeout.connect(self._slide_step)
        self._slide_play_btn = None
        self._slide_pop_btn = None
        self._ghost_all_btn = None
        self._ghost_all_cb = None
        self._array_actors = []
        self._bed = (None, None)         # (bed_x, bed_y) mm; None = no check
        self._tilt3d_on = False
        self._tilt3d_axis = "X"
        self._tilt3d_angle = 0.0
        self._tilt3d_mode = "A"          # A part / B tray
        self._tilt3d_cb = None
        self._tilt3d_release_cb = None
        self._tilt3d_dragging = False
        self._tilt3d_actors = []
        self._tilt3d_obs = []
        self._tilt3d_saved_style = None
        self._tilt3d_hover = False
        self._tilt3d_start_angle = 0.0
        self._spin3d_on = False          # pocket spin gizmo
        self._spin3d_angle = 0.0         # 0..360
        self._spin3d_cb = None
        self._spin3d_dragging = False
        self._spin3d_actors = []
        self._spin3d_obs = []
        self._spin3d_saved_style = None
        self._spin3d_hover = False
        self._spin3d_start_angle = 0.0
        self._anim_timer = None
        self._cam_anim = None

        err = None if HAVE_PYVISTA else _PYVISTA_ERR
        if HAVE_PYVISTA:
            ok, gl_err = _opengl_usable()
            if not ok:
                err = ("Can't open the 3D viewport: no usable OpenGL.\n\n"
                       "%s\n\n"
                       "Parts Packing Generator requires GPU/OpenGL 3.2+ support." % gl_err)
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "3D viewport unavailable", err)
            else:
                try:
                    self.plotter = QtInteractor(self)
                    lay.addWidget(self.plotter.interactor)
                except Exception as e:
                    self.plotter = None
                    err = e

        if self.plotter is None:
            ph = QLabel(
                "3D viewport unavailable.\n\n"
                "Install the geometry/viewer stack to enable it:\n"
                "    pip install -r requirements.txt\n\n"
                "(pyvista + pyvistaqt + VTK: see requirements.txt)\n\n"
                "Reason: %s" % str(err))
            ph.setAlignment(Qt.AlignCenter)
            ph.setWordWrap(True)
            ph.setStyleSheet(
                "background:#3b4252; color:#d8dee9; font-size:10pt;"
                " padding:24px;")
            lay.addWidget(ph)

    def shutdown_vtk(self):
        """Finalize VTK before Qt destroys GL context."""
        for t in (self._section_timer, self._slide_timer, self._anim_timer,
                  self._giz_timer, self._ghost_timer):
            try:
                if t is not None:
                    t.stop()
            except Exception:
                pass
        if self.plotter is not None:
            try:
                self.plotter.close()
            except Exception:
                pass
            self.plotter = None

    def showEvent(self, event):
        super().showEvent(event)
        if self.plotter is not None and not self._vtk_ready:
            self._vtk_ready = True
            try:
                self.plotter.set_background("#3b4252", top="#5a6680")
                self._setup_lighting()
                self._add_plane_indicator()
                self._depth_peel()
            except Exception:
                pass


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_slide_overlay()
