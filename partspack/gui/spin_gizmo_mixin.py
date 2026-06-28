# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# spin gizmo, pocket rotation


class SpinGizmoMixin:
    def enable_spin_gizmo3d(self, callback):
        """Enable spin ring gizmo."""
        if not self.plotter:
            return
        self._spin3d_cb = callback
        self._install_spin3d_observers()
        self._redraw_spin_gizmo3d()

    def set_spin_gizmo3d(self, angle):
        self._spin3d_angle = float(angle) % 360.0
        if self._spin3d_on:
            self._redraw_spin_gizmo3d()

    def show_spin_gizmo3d(self, on):
        self._spin3d_on = bool(on)
        self._redraw_spin_gizmo3d()

    def _spin3d_basis(self):
        """Ring basis (c, R, u, v)."""
        import numpy as np
        if self._part_mesh is None or not self.plotter:
            return None
        b = self._part_mesh.bounds
        cx, cy = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
        centre = np.array([cx, cy, b[4]])
        return (centre, self._px_size(centre, 90),
                np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))

    def _spin3d_handle(self):
        import math
        bg = self._spin3d_basis()
        if bg is None:
            return None
        c, R, u, v = bg
        t = math.radians(self._spin3d_angle)
        return c + R * (math.cos(t) * u + math.sin(t) * v)

    def _redraw_spin_gizmo3d(self):
        if not self.plotter:
            return
        self._remove_actors(self._spin3d_actors)
        self._spin3d_actors = []
        if not self._spin3d_on or self._part_mesh is None:
            return
        bg = self._spin3d_basis()
        if bg is None:
            return
        delta = None
        if self._spin3d_dragging:
            sd = ((self._spin3d_angle - self._spin3d_start_angle + 180) % 360) - 180
            delta = (self._spin3d_start_angle, self._spin3d_start_angle + sd)
        try:
            self._spin3d_actors = self._draw_ring_gizmo(
                bg, "#2d7ff9", self._spin3d_angle,
                "Rotate Parts  %.0f deg" % self._spin3d_angle,
                ring_width=5, ring_opacity=0.8,
                hot=self._spin3d_hover or self._spin3d_dragging, delta=delta)
            self._do_render()
        except Exception:
            self._spin3d_actors = []

    def _install_spin3d_observers(self):
        if self._spin3d_obs:
            return
        iren = self._vtk_iren()
        if iren is None:
            return
        self._spin3d_obs = [
            iren.AddObserver("LeftButtonPressEvent", self._spin3d_press, 21.0),
            iren.AddObserver("MouseMoveEvent", self._spin3d_move, 21.0),
            iren.AddObserver("LeftButtonReleaseEvent", self._spin3d_release, 21.0),
        ]
        self._install_gizmo_cam_observer()

    def _spin3d_press(self, obj, _evt):
        if not self._spin3d_on or self._part_mesh is None:
            return
        h = self._spin3d_handle()
        if h is None:
            return
        try:
            x, y = obj.GetEventPosition()
        except Exception:
            return
        import math
        sx, sy = self._world_to_display(h)
        if math.hypot(sx - x, sy - y) < 24:
            self._spin3d_dragging = True
            self._spin3d_start_angle = self._spin3d_angle
            self._spin3d_saved_style = self._suppress_camera_style(obj)

    def _spin3d_move(self, obj, _evt):
        if not self._spin3d_dragging:
            near = bool(self._spin3d_on and self._part_mesh is not None
                        and self._handle_near(obj, self._spin3d_handle()))
            if near != self._spin3d_hover:
                self._spin3d_hover = near
                self._set_hover_cursor(self._any_hover())
                self._redraw_spin_gizmo3d()
            return
        if self._ring_edge_on(self._spin3d_basis()):
            return
        try:
            x, y = obj.GetEventPosition()
        except Exception:
            return
        ang = self._ray_angle_on_plane(x, y, self._spin3d_basis())
        if ang is None:
            return
        try:
            if obj.GetShiftKey():
                ang = round(ang / 5.0) * 5.0
        except Exception:
            pass
        self._spin3d_angle = ang % 360.0
        self._schedule_gizmo("spin")
        if self._spin3d_cb:
            try:
                self._spin3d_cb(self._spin3d_angle)
            except Exception:
                pass

    def _spin3d_release(self, obj, _evt):
        if not self._spin3d_dragging:
            return
        self._spin3d_dragging = False
        self._restore_style(obj, self._spin3d_saved_style)
        self._spin3d_saved_style = None
        self._redraw_spin_gizmo3d()      # clear drag arc

    def _ray_angle_on_plane(self, x, y, bg):
        """Mouse-ray angle (deg) on ring plane (c, R, u, v)."""
        import numpy as np
        import math
        if bg is None:
            return None
        c, R, u, v = bg
        ren = self.plotter.renderer
        ren.SetDisplayPoint(float(x), float(y), 0.0)
        ren.DisplayToWorld()
        w0 = np.array(ren.GetWorldPoint())
        ren.SetDisplayPoint(float(x), float(y), 1.0)
        ren.DisplayToWorld()
        w1 = np.array(ren.GetWorldPoint())
        if abs(w0[3]) < 1e-12 or abs(w1[3]) < 1e-12:
            return None
        p0, p1 = w0[:3] / w0[3], w1[:3] / w1[3]
        ray = p1 - p0
        n = np.cross(u, v)
        denom = float(np.dot(ray, n))
        if abs(denom) < 1e-9:
            return None
        q = p0 + ray * (float(np.dot(c - p0, n)) / denom)
        d = q - c
        return math.degrees(math.atan2(float(np.dot(d, v)),
                                       float(np.dot(d, u))))

