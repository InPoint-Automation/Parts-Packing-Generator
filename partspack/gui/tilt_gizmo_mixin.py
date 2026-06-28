# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# 3D on-object tilt gizmo


class TiltGizmoMixin:
    def enable_tilt_gizmo3d(self, callback, on_release=None):
        # callback(deg) live, on_release once at drag end
        if not self.plotter:
            return
        self._tilt3d_cb = callback
        self._tilt3d_release_cb = on_release
        self._tilt3d_on = True
        self._install_tilt3d_observers()
        self._redraw_tilt_gizmo3d()

    def set_tilt_gizmo3d(self, axis, angle, mode="A"):
        # sync axis, angle, mode without callback
        self._tilt3d_axis = str(axis).upper()
        self._tilt3d_angle = max(-45.0, min(45.0, float(angle)))
        self._tilt3d_mode = str(mode).upper()
        if self._tilt3d_on:
            self._redraw_tilt_gizmo3d()

    def show_tilt_gizmo3d(self, on):
        self._tilt3d_on = bool(on)
        self._redraw_tilt_gizmo3d()

    def _tilt3d_basis(self):
        # (centre, radius, up, lean) for gizmo ring
        import numpy as np
        if self._part_mesh is None or not self.plotter:
            return None
        b = self._part_mesh.bounds
        cx, cy = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
        up = np.array([0.0, 0.0, 1.0])
        lean = np.array([0.0, 1.0, 0.0]) if self._tilt3d_axis == "X" \
            else np.array([1.0, 0.0, 0.0])
        if self._tilt3d_mode == "A":          # rotate part
            lean = -lean
            centre = np.array([cx, cy, (b[4] + b[5]) / 2.0])
        else:                                  # rotate tray
            centre = np.array([cx, cy, b[4]])
        return centre, self._px_size(centre, 105), up, lean

    def _tilt3d_color(self):
        return "#2ecc71" if self._tilt3d_mode == "A" else "#e8483a"

    def _tilt3d_handle(self):
        import numpy as np
        import math
        bg = self._tilt3d_basis()
        if bg is None:
            return None
        c, R, up, lean = bg
        t = math.radians(self._tilt3d_angle)
        return c + R * (math.cos(t) * up + math.sin(t) * lean)

    def _redraw_tilt_gizmo3d(self):
        if not self.plotter:
            return
        self._remove_actors(self._tilt3d_actors)
        self._tilt3d_actors = []
        if not self._tilt3d_on or self._part_mesh is None:
            return
        bg = self._tilt3d_basis()
        if bg is None:
            return
        txt = "Rotate Part" if self._tilt3d_mode == "A" else "Rotate Tray"
        delta = ((self._tilt3d_start_angle, self._tilt3d_angle)
                 if self._tilt3d_dragging else None)
        try:
            self._tilt3d_actors = self._draw_ring_gizmo(
                bg, self._tilt3d_color(), self._tilt3d_angle,
                "%s  %+.0f deg" % (txt, self._tilt3d_angle),
                sweep=(-45, 46, 6), ring_width=3, ring_opacity=0.55,
                hot=self._tilt3d_hover or self._tilt3d_dragging, delta=delta)
            self._do_render()
        except Exception:
            self._tilt3d_actors = []

    def _install_tilt3d_observers(self):
        if self._tilt3d_obs:
            return
        iren = self._vtk_iren()
        if iren is None:
            return
        self._tilt3d_obs = [
            iren.AddObserver("LeftButtonPressEvent", self._tilt3d_press, 20.0),
            iren.AddObserver("MouseMoveEvent", self._tilt3d_move, 20.0),
            iren.AddObserver("LeftButtonReleaseEvent", self._tilt3d_release, 20.0),
        ]
        self._install_gizmo_cam_observer()

    def _world_to_display(self, p):
        ren = self.plotter.renderer
        ren.SetWorldPoint(float(p[0]), float(p[1]), float(p[2]), 1.0)
        ren.WorldToDisplay()
        d = ren.GetDisplayPoint()
        return d[0], d[1]

    def _tilt3d_press(self, obj, _evt):
        if not self._tilt3d_on or self._part_mesh is None:
            return
        h = self._tilt3d_handle()
        if h is None:
            return
        try:
            x, y = obj.GetEventPosition()
        except Exception:
            return
        import math
        sx, sy = self._world_to_display(h)
        if math.hypot(sx - x, sy - y) < 24:
            # suppress camera on drag
            self._tilt3d_dragging = True
            self._tilt3d_start_angle = self._tilt3d_angle
            self._tilt3d_saved_style = self._suppress_camera_style(obj)

    def _tilt3d_move(self, obj, _evt):
        if not self._tilt3d_dragging:
            near = bool(self._tilt3d_on and self._part_mesh is not None
                        and self._handle_near(obj, self._tilt3d_handle()))
            if near != self._tilt3d_hover:
                self._tilt3d_hover = near
                self._set_hover_cursor(self._any_hover())
                self._redraw_tilt_gizmo3d()
            return
        if self._ring_edge_on(self._tilt3d_basis()):
            return
        try:
            x, y = obj.GetEventPosition()
        except Exception:
            return
        ang = self._tilt3d_angle_at(x, y)
        if ang is None:
            return
        try:
            if obj.GetShiftKey():
                ang = round(ang / 5.0) * 5.0
        except Exception:
            pass
        self._tilt3d_angle = max(-45.0, min(45.0, ang))
        self._schedule_gizmo("tilt")
        if self._tilt3d_cb:
            try:
                self._tilt3d_cb(self._tilt3d_angle)
            except Exception:
                pass

    def _tilt3d_release(self, obj, _evt):
        if not self._tilt3d_dragging:
            return
        self._tilt3d_dragging = False
        self._restore_style(obj, self._tilt3d_saved_style)
        self._tilt3d_saved_style = None
        self._redraw_tilt_gizmo3d()      # clear drag delta arc
        if self._tilt3d_release_cb:
            try:
                self._tilt3d_release_cb()
            except Exception:
                pass

    def _tilt3d_angle_at(self, x, y):
        # angle of mouse ray hit on gizmo plane
        return self._ray_angle_on_plane(x, y, self._tilt3d_basis())

