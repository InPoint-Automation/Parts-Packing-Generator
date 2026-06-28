# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# tilt / spin / rotation param handling

from __future__ import annotations


class TiltMixin:
    def _toggle_flip(self):
        self._set("flip", self.btn_flip.isChecked())

    def _active_tilt_param(self):
        """Active tilt-edit param."""
        return ("tray_angle_deg" if self._active_part_action == "rotate_tray"
                else "part_lean_deg")

    def _tilt_typed(self, v, name=None):
        """Debounce tilt edits."""
        v = float(v)
        name = name or self._active_tilt_param()
        self._pending_tilt = (name, v)
        self._tilt_timer.start(self._TILT_MS)
        self._echo_tilt(name, v)
        if name == "part_lean_deg":          # body follows live
            self.viewer_part.set_part_tilt(self._part_view_matrix(lean=v))

    def _on_tilt_gizmo(self, deg):
        """Arc-gizmo drag: preview lean via cheap body matrix, heavy refresh on release."""
        name = self._active_tilt_param()
        v = float(deg)
        self._pending_tilt = (name, v)
        self._set_part_widget(name, v)       # live number
        if name == "part_lean_deg":
            self.viewer_part.set_part_tilt(self._part_view_matrix(lean=v))
        # fallback commit if release missed
        self._tilt_timer.start(self._TILT_MS)

    def _on_tilt_release(self):
        """Gizmo drag ended -> commit the seating change once."""
        self._tilt_timer.stop()
        self._commit_tilt()

    def _on_spin_gizmo(self, deg):
        """Spin-ring drag -> pocket rotation."""
        deg = float(deg)
        if not self.params.pocket_rotate:
            self._set("pocket_rotate", True)
        self._set("pocket_rotate_deg", deg)

    def _echo_tilt(self, name, v):
        """Mirror angle into gizmo + spin."""
        if name == "tray_angle_deg":
            self.viewer_part.set_tilt_gizmo3d(self.params.tray_angle_axis, v, "B")
        else:
            self.viewer_part.set_tilt_gizmo3d(self.params.part_lean_axis, v, "A")
        self._set_part_widget(name, v)

    def _reset_tilt(self):
        """Clear lean + tray angle."""
        self._pending_tilt = None
        self._tilt_timer.stop()
        # both seating keys, batch so scene rebuilds once
        self._batch_part_refresh(lambda: (
            self._set("part_lean_deg", 0.0),
            self._set("tray_angle_deg", 0.0)))
        self._apply_part_gizmos()

    def _reset_rotations(self):
        """Zero spin, lean, tray angle."""
        self._pending_tilt = None
        self._tilt_timer.stop()
        # lean + tray_angle each rebuild part-scene, batch them
        self._batch_part_refresh(lambda: [
            self._set(n, 0.0)
            for n in ("pocket_rotate_deg", "part_lean_deg", "tray_angle_deg")])
        self.viewer_part.set_spin_gizmo3d(0.0)
        self._refresh_part_panel()
        self._apply_part_gizmos()

    def _commit_tilt(self):
        if self._pending_tilt is not None:
            (name, v), self._pending_tilt = self._pending_tilt, None
            self._set(name, v)

