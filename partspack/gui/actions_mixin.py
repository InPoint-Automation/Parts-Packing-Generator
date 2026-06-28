# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# MainWindow actions: load, presets, settings, ghost, section, generate

from __future__ import annotations

import os

from PySide6.QtWidgets import QToolButton, QFileDialog, QMessageBox, QDialog

from .. import APP_NAME, __version__
from ..config import save_cfg
from ..params import Params
from .icons import make_icon
from .dialogs import SettingsDialog


class ActionsMixin:
    def load_step(self):
        initdir = self.cfg.get("last_dir") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Load STEP part", initdir, "STEP (*.step *.stp *.STEP *.STP)")
        if not path:
            return
        self.cfg["last_dir"] = os.path.dirname(path)
        rec = [path] + [p for p in (self.cfg.get("recent") or []) if p != path]
        self.cfg["recent"] = rec[:8]
        save_cfg(self.cfg)
        self.statusBar().showMessage("Loading %s..." % os.path.basename(path))
        try:
            part = self.bridge.load_part(path)
        except Exception as e:
            QMessageBox.warning(self, "Load", "Could not load STEP:\n%s" % e)
            return
        self._ghost_active = False
        self._ghost_built = False
        self._default_hold_height(part)
        self.setWindowTitle("%s  v%s - %s"
                            % (APP_NAME, __version__, os.path.basename(path)))
        self.viewer_part.show_part(part, self._seating_dir(), color="#9fb3d1",
                                   reset=False, tray_normal=self._tray_normal(),
                                   part_tilt=self._part_view_matrix())
        self.viewer_part.orient_camera(self._seating_dir(), animate=False,
                                       fit=True)
        if self._view_mode == "tray":
            self._apply_view_mode("part")
        self._apply_part_gizmos()
        self.viewer_part.set_section(self.btn_section.isChecked())
        if self._btn_ghost.isChecked():
            self._request_ghost()
        self.readout.setText("Loaded: %s\nAdjust parameters, then Generate."
                             % os.path.basename(path))
        self.statusBar().showMessage("Loaded %s - Generate to build."
                                     % os.path.basename(path))

    def _default_hold_height(self, part, toast=False):
        """Seed hold_height to 40% of oriented part height."""
        try:
            # reuse cached orient, don't re-orient solid
            from ..core import meshbool
            oriented, _info = meshbool._oriented_cached(part, self.params)
            h = float(oriented.bounding_box(optimal=True).max.Z)
        except Exception:
            return
        if h <= 0:
            return
        val = min(max(round(0.4 * h, 1), 1.0), 80.0)
        self.params.hold_height = val
        self._set_part_widget("hold_height", val)
        self.viewer_part.set_hold(self.params.hold_height)
        if toast:
            self._toast("cradle depth %.1f mm" % val)

    def _seating_dir(self):
        """Part-frame down-into-tray direction."""
        try:
            from ..core.orient import seating_direction
            return tuple(float(v) for v in seating_direction(self.params))
        except Exception:
            return (0.0, 0.0, 1.0)

    def _tray_normal(self):
        """Tray preview insertion normal."""
        d = self._seating_dir()
        if not float(self.params.tray_angle_deg):
            return d
        try:
            import numpy as np
            from ..core.orient import (rotation_a_to_b, seating_direction,
                                       _AXIS_VEC, _rodrigues)
            R_orient = np.asarray(
                rotation_a_to_b(seating_direction(self.params), (0.0, 0.0, -1.0)),
                dtype=float)
            ax = np.asarray(_AXIS_VEC[str(self.params.tray_angle_axis)], dtype=float)
            R_t = _rodrigues(ax, np.radians(float(self.params.tray_angle_deg)))
            world_ins = R_t @ np.array([0.0, 0.0, -1.0])
            d_part = R_orient.T @ world_ins
            n = np.linalg.norm(d_part)
            return tuple(float(v) for v in (d_part / n)) if n > 1e-9 else d
        except Exception:
            return d

    def _part_view_matrix(self, lean=None, spin=None):
        """Part display rotation (spin+lean). Pass lean/spin to preview in-flight gizmo without mutating params."""
        if spin is None:
            spin = float(self.params.pocket_rotate_deg) \
                if self.params.pocket_rotate else 0.0
        if lean is None:
            lean = float(self.params.part_lean_deg)
        if not spin and not lean:
            return None
        try:
            import numpy as np
            from ..core.orient import (rotation_a_to_b, seating_direction,
                                       _AXIS_VEC, _rodrigues)
            sdir = np.asarray(seating_direction(self.params), dtype=float)
            # same world->part map as carve
            R_orient = np.asarray(
                rotation_a_to_b(tuple(sdir), (0.0, 0.0, -1.0)), dtype=float)
            R = np.eye(3)
            if spin:                              # about world +Z
                R_z = _rodrigues(np.array([0.0, 0.0, 1.0]), np.radians(spin))
                R = (R_orient.T @ R_z @ R_orient) @ R
            if lean:                              # about in-plane axis
                ax = np.asarray(_AXIS_VEC[str(self.params.part_lean_axis)],
                                dtype=float)
                R_t = _rodrigues(ax, np.radians(lean))
                R = (R_orient.T @ R_t @ R_orient) @ R
            return R
        except Exception:
            return None

    def _batch_part_refresh(self, fn):
        """Run fn() coalescing any _refresh_part_view it triggers into one."""
        self._suspend_part_refresh = True
        self._part_refresh_pending = False
        try:
            fn()
        finally:
            self._suspend_part_refresh = False
        if self._part_refresh_pending:
            self._refresh_part_view()

    def _refresh_part_view(self):
        if getattr(self, "_suspend_part_refresh", False):
            self._part_refresh_pending = True
            return
        if self.bridge.part is not None:
            self._apply_part_gizmos()
            # placement-only change, reuse cached mesh
            self.viewer_part.refresh_part_scene(
                self._seating_dir(), tray_normal=self._tray_normal(),
                part_tilt=self._part_view_matrix())
            # drop ghost before camera swing, regen after
            if self._ghost_active:
                self.viewer_part.clear_cavity()
            # animate only if seating direction changed
            import numpy as np
            new_dir = np.asarray(self._seating_dir(), float)
            prev = getattr(self, "_last_seating_dir", None)
            animate = prev is None or float(np.dot(new_dir, prev)) < 0.99999
            self._last_seating_dir = new_dir
            self.viewer_part.orient_camera(tuple(new_dir), animate=animate,
                                           on_done=self._kick_live_ghost)

    def _kick_live_ghost(self):
        """Post-rotation: start debounced ghost rebuild."""
        if (self._ghost_active and self.bridge.step_path
                and self.cfg.get("live_preview", True)):
            self._toast("Regenerating ghost...")
            self._auto_timer.start(self._AUTO_MS)

    def open_preset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open preset", self.cfg.get("last_dir") or os.path.expanduser("~"),
            "Preset (*.json)")
        if not path:
            return
        try:
            self.params = Params.load(path)
        except Exception as e:
            QMessageBox.warning(self, "Preset", "Could not load preset:\n%s" % e)
            return
        self._sync_widgets()
        self.cfg["last_preset"] = path
        save_cfg(self.cfg)
        self.statusBar().showMessage("Loaded preset %s" % os.path.basename(path))

    def save_preset(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save preset", self.cfg.get("last_dir") or os.path.expanduser("~"),
            "Preset (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self.params.save(path)
        except Exception as e:
            QMessageBox.warning(self, "Preset", "Could not save preset:\n%s" % e)
            return
        self.statusBar().showMessage("Saved preset %s" % os.path.basename(path))

    def _sync_widgets(self):
        """Push params back into bound widgets."""
        for name, w in self._widgets.items():
            val = getattr(self.params, name)
            w.blockSignals(True)
            self._set_widget_value(w, val)
            w.blockSignals(False)
        for cb, nm in ((self.cb_axis, "seating_axis"),
                       (self.cb_export, "export_format")):
            cb.blockSignals(True)
            cb.setCurrentText(str(getattr(self.params, nm)))
            cb.blockSignals(False)
        self.btn_flip.setChecked(bool(self.params.flip))
        self._apply_part_gizmos()
        self.viewer_part.set_spin_gizmo3d(self.params.pocket_rotate_deg)
        self._sync_axis_btns()
        for n, b in getattr(self, "_feature_btns", {}).items():
            b.blockSignals(True)
            b.setChecked(bool(getattr(self.params, n)))
            b.blockSignals(False)
        self._refresh_part_panel()
        self._apply_visibility()
        self._refresh_drawer_summary()

    def settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec() != QDialog.Accepted:
            return
        vals = dlg.values()
        self.cfg.update(vals)
        save_cfg(self.cfg)

        from .icons import set_accent, set_ui_scale
        set_accent(vals["icon_color"])
        set_ui_scale(vals["ui_scale"])
        self._retint_icons()

        self.params.bed_x = vals["bed_x"]
        self.params.bed_y = vals["bed_y"]
        self._apply_part_gizmos()

        # background build off: stop speculation, drop result
        if not vals["speculative_build"]:
            self._spec_timer.stop()
            self._spec_result = None
        elif self._result_dirty:
            self._spec_timer.start(self._SPEC_MS)

        self.statusBar().showMessage("Settings saved.")

    def _retint_icons(self):
        """Rebuild button icons against current accent."""
        from .icons import make_icon
        for b in self.findChildren(QToolButton):
            name = b.property("icon_name")
            if not name:
                continue
            px = int(b.property("icon_size_px") or 22)
            b.setIcon(make_icon(name, b.property("icon_fixed_color"), px))

    def toggle_ghost(self):
        """Toggle cavity ghost overlay."""
        on = self._btn_ghost.isChecked()
        if on and self.bridge.part is None:
            self._btn_ghost.setChecked(False)
            self.statusBar().showMessage("Load a STEP part first.")
            return
        if on:
            if self._view_mode == "tray":
                self._apply_view_mode("part")
            self._request_ghost()
        else:
            self._ghost_active = False
            self._ghost_built = False
            self.viewer_part.clear_cavity()
            self.statusBar().showMessage("Ghost off.")

    def _request_ghost(self):
        """Kick off-thread cavity build."""
        if not self.bridge.step_path:
            return
        prm = self.params.model_copy()
        self._start_build(
            "Ghost", lambda pr: self.bridge.build_ghost(prm, progress=pr),
            silent=self._ghost_built)

    def toggle_section(self):
        """Toggle part cutaway clip."""
        on = self.btn_section.isChecked()
        if on and self.bridge.part is None:
            self.btn_section.setChecked(False)
            self.statusBar().showMessage("Load a STEP part first.")
            return
        if on and self._view_mode == "tray":
            self._apply_view_mode("part")
        self.viewer_part.set_section(on)
        self.statusBar().showMessage(
            "Part cutaway %s." % ("on" if on else "off"))

    def _on_section_drag(self, hold):
        """Section drag -> hold_height."""
        hold = round(min(max(float(hold), 1.0), 80.0), 1)
        self._set("hold_height", hold)
        self._set_part_widget("hold_height", hold)

    def generate(self):
        if not self.bridge.step_path:
            self.statusBar().showMessage("Load a STEP part first.")
            return
        self._spec_timer.stop()
        # spec result for this exact (part, params), instant. part id in key blocks stale adoption
        spec = self._spec_result
        if spec is not None and spec[0] == self._spec_key():
            self._spec_result = None
            self.statusBar().showMessage("Generate: ready (precomputed).")
            self._on_build_done("Generate", spec[1])
            return
        # build running: queue Generate, spec warmed carve cache so queued run is fast
        if self._build_thread is not None:
            self._pending_generate = True
            self.statusBar().showMessage("Generate: finishing current build...")
            return
        prm = self.params.model_copy()
        self._start_build("Generate",
                          lambda pr: self.bridge.build(prm, progress=pr))

    def _spec_key(self):
        """Identity a speculative build is valid for: (part, all params)."""
        return (id(self.bridge.part), self.params.model_copy(deep=True))

    def _invalidate_spec(self):
        """Param changed: drop speculative result, re-arm idle timer."""
        self._spec_result = None
        if self.cfg.get("speculative_build", True) and self.bridge.step_path:
            self._spec_timer.start(self._SPEC_MS)

    def _maybe_speculate(self):
        """Idle tick: pre-run the full tray off-thread if it would be stale."""
        if not self.cfg.get("speculative_build", True):
            return
        if not (self.bridge.step_path and self._result_dirty):
            return
        if self._spec_result is not None:        # already ready
            return
        # yield to running build or pending live-ghost refresh, retry after
        if self._build_thread is not None or self._auto_timer.isActive():
            self._spec_timer.start(self._SPEC_MS)
            return
        key = self._spec_key()
        self._spec_snapshot = key
        prm = key[1]
        self._start_build("Spec",
                          lambda pr: self.bridge.build(prm, progress=pr),
                          silent=True)

    def generate_drawer(self):
        if not self.project.entries:
            self.statusBar().showMessage("Add parts to the project first.")
            return
        # drawer-level base from current panel, persist onto project
        self.project.drawer = self.params.model_copy(deep=True)
        proj = self.project.model_copy(deep=True)
        self._start_build(
            "Drawer", lambda pr: self.bridge.build_drawer(proj, progress=pr))

    def generate_batch(self):
        if not self.project.entries:
            self.statusBar().showMessage("Add parts to the project first.")
            return
        proj = self.project.model_copy(deep=True)
        self._start_build(
            "Batch", lambda pr: self.bridge.build_batch(proj, progress=pr))

