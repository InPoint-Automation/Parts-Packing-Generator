# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# scene setup, lighting, feature edges, show_mesh/part API


class SceneMixin:
    def _depth_peel(self):
        """Order-independent transparency; enable once per scene."""
        if not self.plotter or self._peeling:
            return
        try:
            self.plotter.enable_depth_peeling(10)
            self._peeling = True
        except Exception:
            pass

    def _drop_actors(self, *attrs):
        """Remove named actors, null their attrs."""
        for attr in attrs:
            a = getattr(self, attr, None)
            if a is not None:
                try:
                    self.plotter.remove_actor(a)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _setup_lighting(self):
        """Headlight + two camera-relative fills."""
        if not self.plotter:
            return
        import pyvista as pv
        try:
            self.plotter.remove_all_lights()
        except Exception:
            pass
        self.plotter.add_light(pv.Light(light_type="headlight", intensity=0.55))
        for pos, inten in (((-1.0, 1.0, 1.0), 0.45),
                           ((1.0, -0.6, 0.4), 0.25)):
            self.plotter.add_light(
                pv.Light(position=pos, light_type="camera light",
                         intensity=inten))

    # split_sharp_edges: weld else blotchy
    _MATERIAL = dict(smooth_shading=True, split_sharp_edges=True,
                     feature_angle=30.0, ambient=0.28, diffuse=0.85,
                     specular=0.35, specular_power=18)

    def _add_feature_edges(self, mesh, color="#11151b"):
        """Overlay sharp + boundary edges, memoised by mesh identity."""
        if mesh is None or not self.plotter:
            return None
        try:
            cache = getattr(self, "_edge_cache", None)
            if cache is not None and cache[0] is mesh:
                edges = cache[1]
            else:
                edges = mesh.extract_feature_edges(
                    feature_angle=25, boundary_edges=True, feature_edges=True,
                    manifold_edges=False, non_manifold_edges=False)
                self._edge_cache = (mesh, edges)
            if edges.n_cells:
                return self.plotter.add_mesh(edges, color=color, line_width=1.4,
                                             pickable=False, lighting=False)
        except Exception:
            pass
        return None

    def show_mesh(self, mesh, reset=True, title=None, **kw):
        """Replace displayed mesh."""
        if not self.plotter:
            return
        self.plotter.clear()
        self._array_actors = []
        self._setup_lighting()
        self._add_plane_indicator()
        if mesh is not None:
            self.plotter.add_mesh(mesh, **kw)
            self._add_feature_edges(mesh)
        if title:
            self.plotter.add_text(title, position="upper_left", font_size=9,
                                  color="#d8dee9")
        if reset:
            self.plotter.reset_camera()

    def show_polydata(self, mesh, color="#cdd6e6", reset=True, title=None):
        """Display tessellated PolyData."""
        if not self.plotter or mesh is None:
            return False
        self._array_actors = []
        self.show_mesh(mesh, reset=reset, title=title, color=color,
                       show_edges=False, **self._MATERIAL)
        if self._ghost_all_cb is not None:     # tray viewer
            self._ensure_slide_overlay()
            self._ghost_all_btn.setVisible(True)
            self._ghost_all_btn.raise_()
            self._show_tray_dims(mesh)
        return True

    def set_bed(self, bed_x, bed_y):
        """Bed XY (mm) for over-bed check; None disables."""
        self._bed = (bed_x, bed_y)

    def _show_tray_dims(self, mesh):
        """Tray XYZ readout, red if over bed."""
        if not self.plotter or mesh is None:
            return
        b = mesh.bounds
        dx, dy, dz = b[1] - b[0], b[3] - b[2], b[5] - b[4]
        bx, by = self._bed
        over = (bx and dx > float(bx) + 1e-6) or (by and dy > float(by) + 1e-6)
        text = "Tray  X %.1f   Y %.1f   Z %.1f mm" % (dx, dy, dz)
        color = "#d8dee9"
        if over:
            color = "#ff5a5a"
            text += "\nexceeds bed %s x %s mm" % (
                ("%.0f" % bx) if bx else "?", ("%.0f" % by) if by else "?")
        try:
            self.plotter.add_text(
                text, position="upper_right", font_size=9, color=color)
        except Exception:
            pass

    def show_part(self, shape, seating_dir=(0, 0, 1), color="#9fb3d1",
                  reset=True, tray_normal=None, part_tilt=None):
        """Tessellate B-rep, cache mesh, compose scene."""
        if not self.plotter:
            return False
        from .mesh import shape_to_polydata
        mesh = shape_to_polydata(shape, 0.3, 0.5)
        if mesh is None:
            return False
        self._part_mesh = mesh
        self._part_color = color
        return self._compose_part_scene(seating_dir, part_tilt, tray_normal,
                                        reset)

    def refresh_part_scene(self, seating_dir, tray_normal=None, part_tilt=None,
                           reset=False):
        """Recompose part scene from cached mesh, no re-tessellation."""
        if not self.plotter or self._part_mesh is None:
            return False
        return self._compose_part_scene(seating_dir, part_tilt, tray_normal,
                                        reset)

    def _compose_part_scene(self, seating_dir, part_tilt, tray_normal, reset):
        """Build part-view scene; suppress rendering, render once at end."""
        import numpy as _np
        prev_suppress = getattr(self.plotter, "suppress_rendering", False)
        self.plotter.suppress_rendering = True
        try:
            self.plotter.clear()
            self._peeling = False        # re-enable on next ghost
            self._clip_cache.clear()
            self._setup_lighting()
            self._part_actor = None
            self._edge_actor = None
            self._cav_actor = None
            self._section_actor = None
            _d = _np.asarray(seating_dir, dtype=float)
            _n = _np.linalg.norm(_d)
            self._seating_dir = tuple(_d / _n) if _n > 1e-9 else (0.0, 0.0, 1.0)
            self._part_tilt = (_np.asarray(part_tilt, dtype=float)
                               if part_tilt is not None else None)

            self._add_plane_indicator()
            self._add_direction_arrow(self._part_mesh.bounds, self._seating_dir,
                                      plane_normal=tray_normal)
            self.plotter.add_text(
                "Part - part coordinates (choose seating here)",
                position="upper_left", font_size=9, color="#d8dee9")
            self._rebuild_part_scene()
            self._draw_translate_gizmo()
            if reset:
                self.plotter.reset_camera()
            self._redraw_tilt_gizmo3d()
            self._redraw_spin_gizmo3d()
        finally:
            self.plotter.suppress_rendering = prev_suppress
        try:
            self.plotter.render()
        except Exception:
            pass
        return True

