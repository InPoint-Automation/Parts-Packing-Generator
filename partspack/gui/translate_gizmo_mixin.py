# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Height translate gizmo (cradle depth).


class TranslateGizmoMixin:
    def enable_translate_gizmo3d(self, callback):
        """Draggable height arrow, callback(hold_mm) fires live."""
        if not self.plotter:
            return
        self._tr3d_cb = callback
        self._install_translate3d_observers()
        self._draw_translate_gizmo()

    def show_translate_gizmo3d(self, on):
        self._tr3d_on = bool(on)
        self._draw_translate_gizmo()

    def _seating_axis_color(self):
        """RGB=XYZ color for seating axis."""
        import numpy as np
        d = np.asarray(self._seating_dir, dtype=float)
        for ax, vec in (("X", (1, 0, 0)), ("Y", (0, 1, 0)), ("Z", (0, 0, 1))):
            if abs(abs(float(d @ np.array(vec, dtype=float))) - 1.0) < 1e-3:
                return self._AXIS_COLORS[ax]
        return "#5ad0c0"

    def _tr3d_anchor(self):
        """(handle base P on cut plane, axis d, length L)."""
        import numpy as np
        if self._part_mesh is None or not self.plotter:
            return None
        d = np.asarray(self._seating_dir, dtype=float)
        pts = self._tilted_points()              # rotated part
        c = pts.mean(axis=0)
        proj = self._cradle_level()              # seat(rotated) - hold
        P = c + (proj - float(c @ d)) * d        # part center on cut plane
        return P, d, self._px_size(P, 150)

    def _draw_translate_gizmo(self):
        if not self.plotter:
            return
        self._remove_actors(self._tr3d_actors)
        self._tr3d_actors = []
        if not self._tr3d_on or self._part_mesh is None:
            return
        anc = self._tr3d_anchor()
        if anc is None:
            return
        import numpy as np
        import pyvista as pv
        P, d, L = anc
        up = -d                                  # off seat face
        col = self._seating_axis_color()
        hot = self._tr3d_hover or self._tr3d_dragging
        head = P + up * (L * 0.55)
        try:
            # translucent cut plane at cradle top, single quad per frame
            size = self._scene_size(self._part_mesh.bounds)
            plane = pv.Plane(center=tuple(P), direction=tuple(d),
                             i_size=size * 0.85, j_size=size * 0.85,
                             i_resolution=1, j_resolution=1)
            self._tr3d_actors.append(self.plotter.add_mesh(
                plane, color=col, opacity=0.18 if hot else 0.12,
                show_edges=False, pickable=False,
                lighting=False, reset_camera=False))
            self._tr3d_actors.append(self.plotter.add_mesh(
                pv.lines_from_points(np.array([P, head])), color=col,
                line_width=5 if hot else 3, pickable=False, reset_camera=False,
                render_lines_as_tubes=True))
            self._tr3d_actors.append(self.plotter.add_mesh(
                pv.Cone(center=tuple(head), direction=tuple(up),
                        height=L * (0.22 if hot else 0.18),
                        radius=L * (0.09 if hot else 0.07), resolution=24),
                color="#ffffff" if hot else col, pickable=False,
                reset_camera=False, opacity=1.0 if hot else 0.85))
            self._tr3d_actors.append(self.plotter.add_point_labels(
                [tuple(P + up * (L * 0.72))], ["cradle  %.1f mm" % self._hold],
                font_size=12, text_color=col, shape=None, show_points=False,
                always_visible=True, reset_camera=False))
            if self._tr3d_dragging and self._tr3d_start_P is not None:
                self._tr3d_actors.append(self.plotter.add_mesh(
                    pv.Sphere(radius=L * 0.05, center=tuple(self._tr3d_start_P)),
                    color=col, opacity=0.35, pickable=False, reset_camera=False))
            for a in self._tr3d_actors:
                self._raise_actor(a)
            self._do_render()
        except Exception:
            self._tr3d_actors = []

    def _closest_axis_t(self, x, y, A, d):
        """Signed distance along d from A to point nearest mouse ray."""
        import numpy as np
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
        e = p1 - p0
        A = np.asarray(A, dtype=float)
        d = np.asarray(d, dtype=float)
        w = p0 - A
        a = float(e @ e)
        bb = float(e @ d)
        cc = float(d @ d)
        dc = float(e @ w)
        ec = float(d @ w)
        denom = a * cc - bb * bb
        if abs(denom) < 1e-9:
            return None
        return (a * ec - bb * dc) / denom

    def _install_translate3d_observers(self):
        if self._tr3d_obs:
            return
        iren = self._vtk_iren()
        if iren is None:
            return
        self._tr3d_obs = [
            iren.AddObserver("LeftButtonPressEvent", self._tr3d_press, 22.0),
            iren.AddObserver("MouseMoveEvent", self._tr3d_move, 22.0),
            iren.AddObserver("LeftButtonReleaseEvent", self._tr3d_release, 22.0),
        ]
        self._install_gizmo_cam_observer()

    def _tr3d_press(self, obj, _evt):
        if not self._tr3d_on or self._part_mesh is None:
            return
        anc = self._tr3d_anchor()
        if anc is None:
            return
        import numpy as np
        import math
        P, d, L = anc
        head = P + (-d) * (L * 0.55)
        try:
            x, y = obj.GetEventPosition()
        except Exception:
            return
        sx, sy = self._world_to_display(head)
        if math.hypot(sx - x, sy - y) >= 28:
            return
        tc0 = self._closest_axis_t(x, y, P, d)
        self._tr3d_dragging = True
        self._tr3d_grab_A = P
        self._tr3d_grab_proj0 = float(np.asarray(P, dtype=float) @ d)
        self._tr3d_grab_tc0 = tc0 if tc0 is not None else 0.0
        self._tr3d_start_P = P
        self._tr3d_saved_style = self._suppress_camera_style(obj)

    def _tr3d_move(self, obj, _evt):
        if not self._tr3d_dragging:
            near = False
            if self._tr3d_on and self._part_mesh is not None:
                anc = self._tr3d_anchor()
                if anc is not None:
                    P, d, L = anc
                    near = self._handle_near(obj, P + (-d) * (L * 0.55), 28)
            if near != self._tr3d_hover:
                self._tr3d_hover = near
                self._set_hover_cursor(self._any_hover())
                self._draw_translate_gizmo()
            return
        try:
            x, y = obj.GetEventPosition()
        except Exception:
            return
        import numpy as np
        d = np.asarray(self._seating_dir, dtype=float)
        # axis too near view axis is unstable
        try:
            vd = np.array(self.plotter.renderer.GetActiveCamera()
                          .GetDirectionOfProjection(), dtype=float)
            if abs(float(d @ vd)) > 0.97:
                return
        except Exception:
            pass
        tc = self._closest_axis_t(x, y, self._tr3d_grab_A, d)
        if tc is None:
            return
        new_proj = self._tr3d_grab_proj0 + (tc - self._tr3d_grab_tc0)
        mx = self._seat_proj()                   # rotated seat face
        hold = mx - new_proj
        try:
            if obj.GetShiftKey():
                hold = round(hold / 0.5) * 0.5
        except Exception:
            pass
        hold = max(1.0, min(80.0, hold))
        self._hold = hold
        self._schedule_gizmo("tr")
        if self._tr3d_cb:
            try:
                self._tr3d_cb(hold)
            except Exception:
                pass

    def _tr3d_release(self, obj, _evt):
        if not self._tr3d_dragging:
            return
        self._tr3d_dragging = False
        self._tr3d_start_P = None
        self._restore_style(obj, self._tr3d_saved_style)
        self._tr3d_saved_style = None
        if self._cav_on:                 # final ghost after drag
            self._update_overlays()
        self._draw_translate_gizmo()

    def _reclip_part(self):
        """Debounced part re-clip."""
        if self._section_on:
            self._rebuild_part_scene()

