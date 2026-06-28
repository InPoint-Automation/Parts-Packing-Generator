# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# ring-gizmo drawing and interaction primitives


from PySide6.QtCore import Qt


class RingGizmoMixin:
    # top layer draws gizmos over part; False if misbehaves
    _USE_GIZMO_OVERLAY = True

    def _gizmo_overlay(self):
        # lazy top render layer, None if unsupported
        if self._overlay_tried:
            return self._overlay_ren
        self._overlay_tried = True
        if not self._USE_GIZMO_OVERLAY:
            return None
        try:
            import vtk
            base = self.plotter.renderer
            rw = self.plotter.render_window
            ov = vtk.vtkRenderer()
            ov.SetLayer(1)
            ov.InteractiveOff()
            ov.SetActiveCamera(base.GetActiveCamera())
            rw.SetNumberOfLayers(2)
            rw.AddRenderer(ov)
            self._overlay_ren = ov
        except Exception:
            self._overlay_ren = None
        return self._overlay_ren

    def _raise_actor(self, actor):
        # move 3D actor to overlay, labels stay in base
        ov = self._gizmo_overlay()
        if ov is None or actor is None:
            return
        try:
            import vtk
            if not isinstance(actor, vtk.vtkProp3D):
                return
            self.plotter.renderer.RemoveActor(actor)
            ov.AddActor(actor)
        except Exception:
            pass

    def _remove_actors(self, actors):
        ov = self._overlay_ren
        for a in actors:
            try:
                self.plotter.remove_actor(a)
            except Exception:
                pass
            if ov is not None:
                try:
                    ov.RemoveActor(a)
                except Exception:
                    pass

    def _draw_ring_gizmo(self, bg, col, angle, label, sweep=None,
                         ring_width=3, ring_opacity=0.55, hot=False,
                         delta=None):
        # ring, handle, spoke, label; return actor list
        import numpy as np
        import math
        import pyvista as pv
        c, R, u, v = bg

        def pt(d):
            return c + R * (math.cos(math.radians(d)) * u
                            + math.sin(math.radians(d)) * v)

        acts = []
        acts.append(self.plotter.add_mesh(
            pv.lines_from_points(np.array([pt(d) for d in range(0, 361, 6)])),
            color=col, line_width=ring_width + (2 if hot else 0), pickable=False,
            reset_camera=False, opacity=1.0 if hot else ring_opacity,
            render_lines_as_tubes=True))
        if sweep is not None:
            lo, hi, w = sweep
            acts.append(self.plotter.add_mesh(
                pv.lines_from_points(np.array([pt(d) for d in range(lo, hi, 3)])),
                color=col, line_width=w, pickable=False, reset_camera=False,
                render_lines_as_tubes=True))
        if delta is not None:
            a0, a1 = delta
            n = max(2, int(abs(a1 - a0) / 3.0) + 1)
            arc = np.array([pt(a0 + (a1 - a0) * k / (n - 1)) for k in range(n)])
            acts.append(self.plotter.add_mesh(
                pv.lines_from_points(arc), color="#ffd24a", line_width=12,
                pickable=False, reset_camera=False, opacity=0.6,
                render_lines_as_tubes=True))
        t = math.radians(angle)
        h = c + R * (math.cos(t) * u + math.sin(t) * v)
        acts.append(self.plotter.add_mesh(
            pv.Sphere(radius=R * (0.14 if hot else 0.1), center=tuple(h)),
            color="#ffffff" if hot else col,
            pickable=False, reset_camera=False))
        acts.append(self.plotter.add_mesh(
            pv.lines_from_points(np.array([c, h])), color=col, line_width=2,
            pickable=False, reset_camera=False, render_lines_as_tubes=True))
        acts.append(self.plotter.add_point_labels(
            [tuple(c + u * R * 1.15)], [label], font_size=12, text_color=col,
            shape=None, show_points=False, always_visible=True,
            reset_camera=False))
        for a in acts:
            self._raise_actor(a)
        return acts

    def _hide_cursor(self, hidden):
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import Qt
            if hidden:
                QApplication.setOverrideCursor(Qt.BlankCursor)
            else:
                QApplication.restoreOverrideCursor()
        except Exception:
            pass

    def _suppress_camera_style(self, obj):
        # swap to no-op interactor style, return saved (or None)
        self._hide_cursor(True)
        try:
            from vtkmodules.vtkInteractionStyle import vtkInteractorStyleUser
        except Exception:
            try:
                from vtk import vtkInteractorStyleUser
            except Exception:
                return None
        saved = obj.GetInteractorStyle()
        obj.SetInteractorStyle(vtkInteractorStyleUser())
        return saved

    def _restore_style(self, obj, saved):
        self._hide_cursor(False)
        if saved is not None:
            try:
                obj.SetInteractorStyle(saved)
            except Exception:
                pass

