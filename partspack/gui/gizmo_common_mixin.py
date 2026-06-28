# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Shared gizmo math, hover/cursor, render batching, plane/arrow


from PySide6.QtCore import Qt

from .viewer_common import _hex_rgb


class GizmoCommonMixin:
    def _vtk_iren(self):
        """Raw vtkRenderWindowInteractor."""
        iren = getattr(self.plotter, "iren", None)
        if iren is None:
            return None
        return getattr(iren, "interactor", iren)

    def _scene_size(self, bounds):
        xmin, xmax, ymin, ymax, zmin, zmax = bounds
        reach = max(abs(v) for v in bounds) if any(bounds) else 1.0
        ext = max(xmax - xmin, ymax - ymin, zmax - zmin, 1.0)
        return max(reach, ext) * 1.4

    def _world_per_pixel(self, world_pt):
        """World units per screen pixel at world_pt; None if unavailable."""
        import numpy as np
        import math
        try:
            ren = self.plotter.renderer
            cam = ren.GetActiveCamera()
            h_px = self.plotter.render_window.GetSize()[1]
        except Exception:
            return None
        if not h_px or h_px <= 0:
            return None
        if cam.GetParallelProjection():
            return (2.0 * cam.GetParallelScale()) / h_px
        pos = np.array(cam.GetPosition(), dtype=float)
        dist = float(np.linalg.norm(np.asarray(world_pt, dtype=float) - pos))
        world_h = 2.0 * dist * math.tan(math.radians(cam.GetViewAngle()) / 2.0)
        return world_h / h_px

    def _px_size(self, center, px):
        """World length for px-pixel on-screen size at center."""
        wpp = self._world_per_pixel(center)
        if wpp is None or wpp <= 0:
            b = self._part_mesh.bounds
            return max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 1.0) * 0.5
        return px * wpp

    def _handle_near(self, obj, handle_world, threshold=24):
        """True if mouse within threshold px of world handle point."""
        import math
        if handle_world is None:
            return False
        try:
            x, y = obj.GetEventPosition()
        except Exception:
            return False
        sx, sy = self._world_to_display(handle_world)
        return math.hypot(sx - x, sy - y) < threshold

    def _any_hover(self):
        return self._tr3d_hover or self._tilt3d_hover or self._spin3d_hover

    def _set_hover_cursor(self, on):
        """Pointing-hand cursor over draggable handle."""
        try:
            from PySide6.QtCore import Qt
            w = getattr(self.plotter, "interactor", None) or self.plotter
            if on:
                w.setCursor(Qt.PointingHandCursor)
            else:
                w.unsetCursor()
        except Exception:
            pass

    def _ring_edge_on(self, bg):
        """True if ring too edge-on to drag reliably."""
        import numpy as np
        if bg is None:
            return False
        c, R, u, v = bg
        n = np.cross(u, v)
        nn = np.linalg.norm(n)
        if nn < 1e-9:
            return False
        try:
            vd = np.array(self.plotter.renderer.GetActiveCamera()
                          .GetDirectionOfProjection(), dtype=float)
        except Exception:
            return False
        return abs(float((n / nn) @ vd)) < 0.2

    def _install_gizmo_cam_observer(self):
        """Resize gizmos to constant screen size after camera moves."""
        if getattr(self, "_gizmo_cam_obs", None):
            return
        iren = self._vtk_iren()
        if iren is None:
            return
        self._gizmo_cam_obs = iren.AddObserver(
            "EndInteractionEvent", self._on_gizmo_cam_change, 0.0)

    def _redraw_active_gizmos(self):
        """Redraw all visible gizmos with single render."""
        self._suspend_render = True
        try:
            if self._tr3d_on:
                self._draw_translate_gizmo()
            if self._tilt3d_on:
                self._redraw_tilt_gizmo3d()
            if self._spin3d_on:
                self._redraw_spin_gizmo3d()
        finally:
            self._suspend_render = False
        self._do_render()

    def _on_gizmo_cam_change(self, obj, _evt):
        self._redraw_active_gizmos()

    def _do_render(self):
        if self._suspend_render or not self.plotter:
            return
        try:
            self.plotter.render()
        except Exception:
            pass

    def render_batched(self, fn):
        """Run fn() with per-add_mesh renders suppressed, then render once."""
        pl = self.plotter
        if pl is None:
            fn()
            return
        prev = getattr(pl, "suppress_rendering", False)
        pl.suppress_rendering = True
        self._suspend_render = True
        try:
            fn()
        finally:
            self._suspend_render = False
            pl.suppress_rendering = prev
        if not prev:                 # outermost batch renders
            try:
                pl.render()
            except Exception:
                pass

    def _schedule_gizmo(self, kind):
        """Coalesce drag-time gizmo redraws to one per frame."""
        self._giz_pending.add(kind)
        if not self._giz_timer.isActive():
            self._giz_timer.start(16)

    def _giz_flush(self):
        pending, self._giz_pending = self._giz_pending, set()
        self._suspend_render = True
        # suppress at plotter too so add_mesh renders collapse
        prev = getattr(self.plotter, "suppress_rendering", False) \
            if self.plotter else False
        if self.plotter:
            self.plotter.suppress_rendering = True
        try:
            if "tr" in pending:
                self._draw_translate_gizmo()
            if "tilt" in pending:
                self._redraw_tilt_gizmo3d()
            if "spin" in pending:
                self._redraw_spin_gizmo3d()
        finally:
            self._suspend_render = False
            if self.plotter:
                self.plotter.suppress_rendering = prev
        self._do_render()

    def _ghost_flush(self):
        if self._cav_on:
            self._update_overlays()

    _AXIS_COLORS = {"X": "#d05a5a", "Y": "#4caf6a", "Z": "#5a86d0"}

    def _add_plane_indicator(self):
        """Lower-left orientation gizmo (triad + quadrant planes)."""
        try:
            import pyvista as pv
            from vtkmodules.vtkRenderingCore import (
                vtkActor, vtkPolyDataMapper, vtkAssembly)

            def _actor(poly, color, opacity=1.0, lighting=True):
                mapper = vtkPolyDataMapper()
                mapper.SetInputData(poly)
                actor = vtkActor()
                actor.SetMapper(mapper)
                prop = actor.GetProperty()
                prop.SetColor(*_hex_rgb(color))
                prop.SetOpacity(opacity)
                if not lighting:
                    prop.LightingOff()
                return actor

            assembly = vtkAssembly()
            L = 1.0
            for direction, axis in (((1, 0, 0), "X"),
                                    ((0, 1, 0), "Y"),
                                    ((0, 0, 1), "Z")):
                arrow = pv.Arrow(start=(0, 0, 0), direction=direction, scale=L,
                                 tip_length=0.28, tip_radius=0.075,
                                 shaft_radius=0.028)
                assembly.AddPart(_actor(arrow, self._AXIS_COLORS[axis]))
            ps = L * 0.6
            c = ps / 2.0
            for center, normal, axis in (((c, c, 0.0), (0, 0, 1), "Z"),  # XY
                                         ((c, 0.0, c), (0, 1, 0), "Y"),  # XZ
                                         ((0.0, c, c), (1, 0, 0), "X")):  # YZ
                plane = pv.Plane(center=center, direction=normal,
                                 i_size=ps, j_size=ps)
                assembly.AddPart(_actor(plane, self._AXIS_COLORS[axis],
                                        opacity=0.22, lighting=False))
            self.plotter.add_orientation_widget(assembly, interactive=False)
        except Exception:
            try:
                self.plotter.add_axes()
            except Exception:
                pass

    def _add_direction_arrow(self, bounds, seating_dir, plane_normal=None):
        """Arrow + translucent tray plane showing part insertion."""
        import numpy as np
        import pyvista as pv
        d = np.asarray(seating_dir, dtype=float)
        n = np.linalg.norm(d)
        if n < 1e-9:
            return
        d = d / n
        pn = np.asarray(plane_normal, dtype=float) if plane_normal is not None else d
        npn = np.linalg.norm(pn)
        pn = pn / npn if npn > 1e-9 else d

        xmin, xmax, ymin, ymax, zmin, zmax = bounds
        c = np.array([(xmin + xmax) / 2.0, (ymin + ymax) / 2.0,
                      (zmin + zmax) / 2.0])
        size = np.array([xmax - xmin, ymax - ymin, zmax - zmin])
        s = self._scene_size(bounds)
        reach = 0.5 * float(np.dot(np.abs(d), size))
        gap = 0.10 * s
        arrow_len = 0.42 * s

        edge = c + d * reach
        start = edge + d * gap
        arrow = pv.Arrow(start=tuple(start), direction=tuple(d), scale=arrow_len,
                         tip_length=0.28, tip_radius=0.07, shaft_radius=0.03)
        self.plotter.add_mesh(arrow, color="#e0892b", pickable=False)

        plane_c = start + d * (arrow_len + 0.06 * s)
        psize = max(float(size.max()), s * 0.5) * 1.05
        plane = pv.Plane(center=tuple(plane_c), direction=tuple(pn),
                         i_size=psize, j_size=psize)
        self.plotter.add_mesh(plane, color="#5a86d0", opacity=0.16,
                              show_edges=True, edge_color="#88a8e0",
                              pickable=False, lighting=False)
        self.plotter.add_point_labels(
            [tuple(start + d * (arrow_len * 0.5))], ["into tray"], font_size=11,
            text_color="#e0892b", shape=None, show_points=False,
            always_visible=True)

