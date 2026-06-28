# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Part-view layers, tilt clipping, section disc, cavity ghost.


class ClipMixin:
    def _rebuild_part_scene(self):
        """Full rebuild: part body actor + overlays."""
        if not self.plotter or self._part_mesh is None:
            return
        import numpy as np
        self._drop_actors("_part_actor", "_edge_actor")

        clip = self._section_on
        shown = (self._clip_tilted(self._part_mesh, self._cradle_level())
                 if clip else self._part_mesh)
        if shown is not None and shown.n_points:
            self._part_actor = self.plotter.add_mesh(
                shown, color=self._part_color, show_edges=False,
                opacity=0.92, **self._MATERIAL)
        self._apply_tilt(self._part_actor)
        # wireframe spins with body
        self._edge_actor = self._add_feature_edges(shown)
        self._apply_tilt(self._edge_actor)
        self._update_overlays()

    def _tilt_matrix4(self):
        """4x4 user-matrix: part-view rotation about centroid, or None."""
        R = getattr(self, "_part_tilt", None)
        if R is None or self._part_mesh is None:
            return None
        import numpy as np
        try:
            c = np.asarray(self._part_mesh.center, float)
            R = np.asarray(R, float)
            M = np.eye(4)
            M[:3, :3] = R
            M[:3, 3] = c - R @ c
            return M
        except Exception:
            return None

    def _apply_tilt(self, actor):
        """Apply or clear part-view rotation matrix on one actor."""
        if actor is None:
            return
        import numpy as np
        M = self._tilt_matrix4()
        try:
            actor.user_matrix = M if M is not None else np.eye(4)
        except Exception:
            pass

    def _tilt_RT(self):
        """(R, t) of part-view rotation: p_display = R @ p_raw + t."""
        import numpy as np
        M = self._tilt_matrix4()
        if M is None:
            return np.eye(3), np.zeros(3)
        M = np.asarray(M, float)
        return M[:3, :3], M[:3, 3]

    def _tilted_points(self):
        """Part-mesh points as displayed (after lean/spin user-matrix)."""
        import numpy as np
        pts = np.asarray(self._part_mesh.points, float)
        R, t = self._tilt_RT()
        return pts @ R.T + t

    def _seat_proj(self):
        """Seat-face level along seating dir, on rotated part (matches build re-base)."""
        import numpy as np
        d = np.asarray(self._seating_dir, dtype=float)
        return float((self._tilted_points() @ d).max())

    def _lo_proj(self):
        """Opposite (top-of-part) level along seating dir on the rotated part."""
        import numpy as np
        d = np.asarray(self._seating_dir, dtype=float)
        return float((self._tilted_points() @ d).min())

    def _cradle_level(self):
        """World plane (along seating dir) where the cradle tops out."""
        return self._seat_proj() - self._hold

    def _clip_tilted(self, mesh, level, capped=True, keep_above=False):
        """Clip at world plane {p . d == level} after part-view tilt; pulled back through actor user-matrix."""
        import numpy as np
        d = np.asarray(self._seating_dir, dtype=float)
        R, t = self._tilt_RT()
        n = R.T @ d
        o = n * (level - float(t @ d))
        return self._clip(mesh, (-n if keep_above else n), o, capped=capped)

    def _gpu_clip_ok(self):
        """GPU clip-plane fast path only when untilted (world == model); tilted falls back to CPU clip."""
        return self._tr3d_dragging and getattr(self, "_part_tilt", None) is None

    def _make_clip_plane(self, level):
        """vtkPlane matching CPU cradle clip; normal=+d keeps same visible half for drag (GPU) and release (capped)."""
        import numpy as np
        import vtk
        d = np.asarray(self._seating_dir, dtype=float)
        o = d * float(level)
        pl = vtk.vtkPlane()
        pl.SetOrigin(float(o[0]), float(o[1]), float(o[2]))
        pl.SetNormal(float(d[0]), float(d[1]), float(d[2]))
        return pl

    def _set_actor_clip(self, actor, plane):
        """Attach or clear GPU clipping plane on actor mapper."""
        if actor is None:
            return
        try:
            m = actor.mapper
            m.RemoveAllClippingPlanes()
            if plane is not None:
                m.AddClippingPlane(plane)
        except Exception:
            pass

    def _update_drag_clip(self):
        """Per-move cradle update: slide GPU clip planes, no re-mesh."""
        if not self._drag_planes:
            self._update_overlays()
            return
        import numpy as np
        d = np.asarray(self._seating_dir, dtype=float)
        o = d * float(self._cradle_level())
        for pl in self._drag_planes:
            pl.SetOrigin(float(o[0]), float(o[1]), float(o[2]))
        self._do_render()

    def set_part_tilt(self, R):
        """Live-update spin+lean rotation on body + cavity ghosts, no rebuild."""
        import numpy as np
        self._part_tilt = (np.asarray(R, float) if R is not None else None)
        for a in (getattr(self, "_part_actor", None),
                  getattr(self, "_edge_actor", None),
                  getattr(self, "_cav_actor", None),
                  getattr(self, "_cav2_actor", None)):
            self._apply_tilt(a)
        try:
            self.plotter.render()
        except Exception:
            pass

    def _update_overlays(self):
        """Per-drag refresh: cavity ghost + section disc."""
        if not self.plotter or self._part_mesh is None:
            return
        import numpy as np
        # suppress per-add_mesh renders, one at end
        prev = getattr(self.plotter, "suppress_rendering", False)
        self.plotter.suppress_rendering = True
        try:
            self._drop_actors("_cav_actor", "_cav2_actor", "_section_actor")
            self._drag_planes = []
            d = np.asarray(self._seating_dir, dtype=float)
            level = self._cradle_level()

            # untilted GPU-clips full ghost (slide plane), tilted uses CPU clip, capped on release
            gpu = self._gpu_clip_ok()
            capped = not self._tr3d_dragging
            if self._cav_on and self._cav_mesh is not None:
                self._depth_peel()
                cav = (self._cav_mesh if gpu
                       else self._clip_tilted(self._cav_mesh, level,
                                              capped=capped))
                if cav is not None and cav.n_points:
                    self._cav_actor = self.plotter.add_mesh(
                        cav, color="#e0892b", opacity=0.32, show_edges=False,
                        smooth_shading=True, specular=0.1, pickable=False)
                    self._apply_tilt(self._cav_actor)
                    if gpu:
                        pl = self._make_clip_plane(level)
                        self._set_actor_clip(self._cav_actor, pl)
                        self._drag_planes.append(pl)

            if self._cav2_on and self._cav2_mesh is not None:
                self._depth_peel()
                # cav2 top cut fixed, plain clip even mid-drag
                cav2 = self._clip_tilted(self._cav2_mesh,
                                         self._lo_proj() + self._cav2_band,
                                         capped=capped, keep_above=True)
                if cav2 is not None and cav2.n_points:
                    self._cav2_actor = self.plotter.add_mesh(
                        cav2, color="#9966cc", opacity=0.32, show_edges=False,
                        smooth_shading=True, specular=0.1, pickable=False)
                    self._apply_tilt(self._cav2_actor)

            # cut-plane disc at cradle top while sectioning
            if self._section_on:
                self._draw_section_disc(d, d * level)
        finally:
            self.plotter.suppress_rendering = prev
        try:
            self.plotter.render()
        except Exception:
            pass

    def _clip(self, mesh, d, origin, capped=True):
        """Cutaway clip, capped when possible; memoized by (mesh id, normal, origin, capped)."""
        import numpy as np
        key = (id(mesh),
               tuple(np.round(np.asarray(d, float), 5)),
               tuple(np.round(np.asarray(origin, float), 4)), bool(capped))
        hit = self._clip_cache.get(key)
        if hit is not None and hit[0] is mesh:
            return hit[1]
        result = self._clip_compute(mesh, d, origin, capped)
        if len(self._clip_cache) > 32:
            self._clip_cache.pop(next(iter(self._clip_cache)))
        self._clip_cache[key] = (mesh, result)
        return result

    @staticmethod
    def _clip_compute(mesh, d, origin, capped=True):
        if capped:
            try:
                return mesh.clip_closed_surface(normal=tuple(d),
                                                origin=tuple(origin))
            except Exception:
                pass
        try:
            return mesh.clip(normal=tuple(d), origin=tuple(origin),
                             invert=False)
        except Exception:
            return mesh

    def _section_proj(self):
        """Section-plane level along seating dir (on the rotated part)."""
        if self._part_mesh is None:
            return 0.0
        return self._cradle_level()

    def _section_origin(self):
        import numpy as np
        d = np.asarray(self._seating_dir, dtype=float)
        return d * self._section_proj()

    def _draw_section_disc(self, d, origin):
        import pyvista as pv
        size = self._scene_size(self._part_mesh.bounds)
        plane = pv.Plane(center=tuple(origin), direction=tuple(d),
                         i_size=size * 0.8, j_size=size * 0.8,
                         i_resolution=1, j_resolution=1)
        self._section_actor = self.plotter.add_mesh(
            plane, color="#5ad0c0", opacity=0.25, show_edges=True,
            edge_color="#8fe0d4", pickable=False, lighting=False)

    def set_cavity(self, cav_mesh, on=True):
        """Overlay cavity ghost (part frame)."""
        self._cav_mesh = cav_mesh
        self._cav_on = bool(on) and cav_mesh is not None
        self._rebuild_part_scene()

    def set_cavity_top(self, cav_mesh, band, on=True):
        """Overlay top-half cavity ghost."""
        self._cav2_mesh = cav_mesh
        self._cav2_band = float(band)
        self._cav2_on = bool(on) and cav_mesh is not None
        self._rebuild_part_scene()

    def clear_cavity(self):
        self._cav_mesh = None
        self._cav_on = False
        self._cav2_mesh = None
        self._cav2_on = False
        self._rebuild_part_scene()

    def set_section(self, on):
        """Toggle part cutaway."""
        self._section_on = bool(on)
        self._rebuild_part_scene()

    def set_hold(self, hold_height):
        """Update cradle depth live."""
        self._hold = float(hold_height)
        if self._cav_on:
            if self._tr3d_dragging:
                if self._gpu_clip_ok():
                    self._update_drag_clip()      # slide GPU plane
                elif not self._ghost_timer.isActive():
                    self._ghost_timer.start(50)   # tilted, debounce CPU clip
            else:
                self._update_overlays()
        if self._section_on:
            self._section_timer.start(140)   # debounce part cutaway
        if not self._tr3d_dragging:
            self._draw_translate_gizmo()

