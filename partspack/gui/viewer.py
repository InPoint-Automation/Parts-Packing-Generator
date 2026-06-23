# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# 3D viewport wrapping pyvistaqt QtInteractor; placeholder when pyvista missing.

import os

os.environ.setdefault("QT_API", "pyside6")  # before pyvistaqt imports qtpy

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

try:
    from pyvistaqt import QtInteractor
    HAVE_PYVISTA = True
except Exception as _e:
    QtInteractor = None
    HAVE_PYVISTA = False
    _PYVISTA_ERR = _e


def _opengl_usable():
    """check if opengl"""
    if os.environ.get("PARTSPACK_SKIP_GLPROBE"):
        return True, None
    try:
        from PySide6.QtGui import (QOffscreenSurface, QOpenGLContext,
                                   QSurfaceFormat)
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 2)
        surf = QOffscreenSurface()
        surf.setFormat(fmt)
        surf.create()
        if not surf.isValid():
            return False, "offscreen surface invalid"
        ctx = QOpenGLContext()
        ctx.setFormat(fmt)
        if not ctx.create():
            return False, "QOpenGLContext.create() failed"
        if not ctx.makeCurrent(surf):
            return False, "makeCurrent() failed (no usable OpenGL driver)"
        got = ctx.format()
        major, minor = got.majorVersion(), got.minorVersion()
        ctx.doneCurrent()
        if (major, minor) < (3, 2):
            return False, ("OpenGL %d.%d only -- VTK needs 3.2+. This usually "
                           "means a Remote Desktop session or a VM with no GPU "
                           "acceleration." % (major, minor))
        return True, None
    except Exception as e:
        return False, str(e)


def _hex_rgb(hexcol):
    """Hex string to (r, g, b) floats 0..1."""
    h = hexcol.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _slerp(a, b, t):
    """Spherical interp between two unit vectors."""
    import numpy as np
    a = np.asarray(a, float); b = np.asarray(b, float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return b
    a, b = a / na, b / nb
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if dot > 0.9995:                         # near-parallel
        v = a + (b - a) * t
        n = np.linalg.norm(v)
        return v / n if n > 1e-12 else b
    if dot < -0.9995:                        # antiparallel
        ref = _least_aligned_axis(a)
        rel = np.cross(a, ref)
        rel = rel / np.linalg.norm(rel)
        theta = np.pi * t
        return a * np.cos(theta) + rel * np.sin(theta)
    theta = np.arccos(dot) * t
    rel = b - a * dot
    rel = rel / np.linalg.norm(rel)
    return a * np.cos(theta) + rel * np.sin(theta)


def _least_aligned_axis(v):
    """World axis most perpendicular to v."""
    import numpy as np
    v = np.abs(np.asarray(v, float))
    i = int(np.argmin(v))
    e = np.zeros(3); e[i] = 1.0
    return e


class Viewer(QWidget):
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
        self._cav_mesh = None            # part frame
        self._cav_on = False
        self._cav_actor = None
        self._section_on = False
        self._section_cb = None
        self._plane_widget = None
        self._section_actor = None
        self._dragging = False
        self._section_timer = QTimer(self)
        self._section_timer.setSingleShot(True)
        self._section_timer.timeout.connect(self._reclip_part)
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
        self._tilt3d_on = False
        self._tilt3d_axis = "X"
        self._tilt3d_angle = 0.0
        self._tilt3d_mode = "A"          # A part / B tray
        self._tilt3d_cb = None
        self._tilt3d_dragging = False
        self._tilt3d_actors = []
        self._tilt3d_obs = []
        self._tilt3d_saved_style = None
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
                "(pyvista + pyvistaqt + VTK - see requirements.txt)\n\n"
                "Reason: %s" % str(err))
            ph.setAlignment(Qt.AlignCenter)
            ph.setWordWrap(True)
            ph.setStyleSheet(
                "background:#3b4252; color:#d8dee9; font-size:10pt;"
                " padding:24px;")
            lay.addWidget(ph)

    def shutdown_vtk(self):
        """Finalize VTK before Qt destroys GL context."""
        for t in (self._section_timer, self._slide_timer, self._anim_timer):
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
            except Exception:
                pass

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

    # split_sharp_edges essential for welded carve-direct tray (else blotchy shading).
    _MATERIAL = dict(smooth_shading=True, split_sharp_edges=True,
                     feature_angle=30.0, ambient=0.28, diffuse=0.85,
                     specular=0.35, specular_power=18)

    def _add_feature_edges(self, mesh, color="#11151b"):
        """Overlay sharp + boundary edges."""
        if mesh is None or not self.plotter:
            return
        try:
            edges = mesh.extract_feature_edges(
                feature_angle=25, boundary_edges=True, feature_edges=True,
                manifold_edges=False, non_manifold_edges=False)
            if edges.n_cells:
                self.plotter.add_mesh(edges, color=color, line_width=1.4,
                                      pickable=False, lighting=False)
        except Exception:
            pass

    # ---- API the bridge/main window call ----
    def show_mesh(self, mesh, reset=True, title=None, **kw):
        """Replace displayed mesh."""
        if not self.plotter:
            return
        self.plotter.clear()
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

    def show_shape(self, shape, color="#cdd6e6", linear=0.1, angular=0.5,
                   reset=True, title=None):
        """Tessellate and display a shape."""
        if not self.plotter:
            return False
        from .mesh import shape_to_polydata
        return self.show_polydata(shape_to_polydata(shape, linear, angular),
                                  color=color, reset=reset, title=title)

    def show_polydata(self, mesh, color="#cdd6e6", reset=True, title=None):
        """Display tessellated PolyData."""
        if not self.plotter or mesh is None:
            return False
        self.show_mesh(mesh, reset=reset, title=title, color=color,
                       show_edges=False, **self._MATERIAL)
        return True

    def show_ghost(self, part_shape, cavity_shape, reset=True, title=None):
        """Cavity-ghost preview from shapes."""
        if not self.plotter:
            return False
        from .mesh import shape_to_polydata
        cav_mesh = shape_to_polydata(cavity_shape, 0.3, 0.5)
        part_mesh = (shape_to_polydata(part_shape, 0.3, 0.5)
                     if part_shape is not None else None)
        return self.show_ghost_polydata(part_mesh, cav_mesh, reset=reset,
                                        title=title)

    def show_ghost_polydata(self, part_mesh, cav_mesh, reset=True, title=None):
        """Cavity-ghost display from meshes."""
        if not self.plotter or cav_mesh is None:
            return False

        self.plotter.clear()
        self._setup_lighting()
        self._add_plane_indicator()
        # depth peeling: nested translucent shell renders correctly
        try:
            self.plotter.enable_depth_peeling(10)
        except Exception:
            pass

        if part_mesh is not None:
            self.plotter.add_mesh(part_mesh, color="#9fb3d1", show_edges=False,
                                  pickable=False, **self._MATERIAL)
        self.plotter.add_mesh(cav_mesh, color="#e0892b", opacity=0.32,
                              show_edges=False, smooth_shading=True,
                              specular=0.1, pickable=False)
        self._add_feature_edges(cav_mesh, color="#b5651d")

        self.plotter.add_text(
            title or "Cavity ghost - amber shell past the part = gap; "
            "hugs where it's tight", position="upper_left", font_size=9,
            color="#d8dee9")
        if reset:
            self.plotter.reset_camera()
        return True

    def show_part(self, shape, seating_dir=(0, 0, 1), color="#9fb3d1",
                  reset=True, tray_normal=None, part_tilt=None):
        """Display loaded part with reference planes + seating arrow."""
        if not self.plotter:
            return False

        self.plotter.clear()
        self._remove_plane_widget()
        self._setup_lighting()
        self._part_actor = None
        self._part_mesh = None
        self._cav_actor = None
        self._section_actor = None
        import numpy as _np
        _d = _np.asarray(seating_dir, dtype=float)
        _n = _np.linalg.norm(_d)
        self._seating_dir = tuple(_d / _n) if _n > 1e-9 else (0.0, 0.0, 1.0)
        self._part_tilt = (_np.asarray(part_tilt, dtype=float)
                           if part_tilt is not None else None)
        self._part_color = color

        from .mesh import shape_to_polydata
        mesh = shape_to_polydata(shape, 0.3, 0.5)
        if mesh is None:
            return False
        self._part_mesh = mesh

        self._add_plane_indicator()
        self._add_direction_arrow(mesh.bounds, seating_dir,
                                  plane_normal=tray_normal)
        self.plotter.add_text("Part - part coordinates (choose seating here)",
                              position="upper_left", font_size=9,
                              color="#d8dee9")
        self._rebuild_part_scene()
        self._install_plane_widget()
        if reset:
            self.plotter.reset_camera()
        self._redraw_tilt_gizmo3d()        # clear() wiped gizmo actors
        return True

    # ---- part-view layers ----
    def _rebuild_part_scene(self):
        """Full rebuild: part body actor + overlays."""
        if not self.plotter or self._part_mesh is None:
            return
        import numpy as np
        for attr in ("_part_actor",):
            a = getattr(self, attr, None)
            if a is not None:
                try:
                    self.plotter.remove_actor(a)
                except Exception:
                    pass
                setattr(self, attr, None)

        d = np.asarray(self._seating_dir, dtype=float)
        clip = self._section_on
        origin = self._section_origin() if clip else None

        shown = self._clip(self._part_mesh, d, origin) if clip \
            else self._part_mesh
        if shown is not None and shown.n_points:
            self._part_actor = self.plotter.add_mesh(
                shown, color=self._part_color, show_edges=False,
                opacity=0.92, **self._MATERIAL)
        # rotate-part: user-matrix rotation about part centroid
        if (getattr(self, "_part_tilt", None) is not None
                and self._part_actor is not None):
            try:
                c = np.asarray(self._part_mesh.center, float)
                R = np.asarray(self._part_tilt, float)
                M = np.eye(4)
                M[:3, :3] = R
                M[:3, 3] = c - R @ c
                self._part_actor.user_matrix = M
            except Exception:
                pass
        self._add_feature_edges(shown)
        self._update_overlays()

    def _update_overlays(self):
        """Cheap per-drag refresh: cavity ghost + section disc."""
        if not self.plotter or self._part_mesh is None:
            return
        import numpy as np
        for attr in ("_cav_actor", "_section_actor"):
            a = getattr(self, attr, None)
            if a is not None:
                try:
                    self.plotter.remove_actor(a)
                except Exception:
                    pass
                setattr(self, attr, None)
        d = np.asarray(self._seating_dir, dtype=float)
        origin = self._section_origin()

        # cavity ghost always sectioned at plane to show real cradle
        if self._cav_on and self._cav_mesh is not None:
            try:
                self.plotter.enable_depth_peeling(10)
            except Exception:
                pass
            cav = self._clip(self._cav_mesh, d, origin)
            if cav is not None and cav.n_points:
                self._cav_actor = self.plotter.add_mesh(
                    cav, color="#e0892b", opacity=0.32, show_edges=False,
                    smooth_shading=True, specular=0.1, pickable=False)

        # fallback static indicator only when widget couldn't be created
        if self._plane_widget is None:
            self._draw_section_disc(d, origin)
        try:
            self.plotter.render()
        except Exception:
            pass

    def _clip(self, mesh, d, origin):
        """Cutaway clip; capped when possible, else open clip."""
        try:
            return mesh.clip_closed_surface(normal=tuple(d),
                                            origin=tuple(origin))
        except Exception:
            try:
                return mesh.clip(normal=tuple(d), origin=tuple(origin),
                                 invert=False)
            except Exception:
                return mesh

    def _section_proj(self):
        """Section-plane projection along seating dir."""
        import numpy as np
        if self._part_mesh is None:
            return 0.0
        d = np.asarray(self._seating_dir, dtype=float)
        mx = float((self._part_mesh.points @ d).max())
        return mx - self._hold

    def _section_origin(self):
        import numpy as np
        d = np.asarray(self._seating_dir, dtype=float)
        return d * self._section_proj()

    def _draw_section_disc(self, d, origin):
        import pyvista as pv
        size = self._scene_size(self._part_mesh.bounds)
        plane = pv.Plane(center=tuple(origin), direction=tuple(d),
                         i_size=size * 0.8, j_size=size * 0.8)
        self._section_actor = self.plotter.add_mesh(
            plane, color="#5ad0c0", opacity=0.25, show_edges=True,
            edge_color="#8fe0d4", pickable=False, lighting=False)

    # ---- cavity ghost ----
    def set_cavity(self, cav_mesh, on=True):
        """Overlay cavity ghost (part frame)."""
        self._cav_mesh = cav_mesh
        self._cav_on = bool(on) and cav_mesh is not None
        self._rebuild_part_scene()

    def clear_cavity(self):
        self._cav_mesh = None
        self._cav_on = False
        self._rebuild_part_scene()

    # ---- section ----
    def set_section_callback(self, cb):
        """Register hold_height drag callback."""
        self._section_cb = cb

    def set_section(self, on):
        """Toggle part cutaway."""
        self._section_on = bool(on)
        self._rebuild_part_scene()

    def _install_plane_widget(self):
        if not self.plotter or self._part_mesh is None:
            return
        self._remove_plane_widget()
        import numpy as np
        d = np.asarray(self._seating_dir, dtype=float)
        origin = self._section_origin()
        # axis-aligned seating: lock widget normal to that axis
        axis = None
        for ax, vec in (("x", (1, 0, 0)), ("y", (0, 1, 0)), ("z", (0, 0, 1))):
            if abs(abs(float(np.dot(d, vec))) - 1.0) < 1e-6:
                axis = ax
                break
        try:
            self._plane_widget = self.plotter.add_plane_widget(
                self._on_plane_widget, normal=tuple(d), origin=tuple(origin),
                normal_rotation=False, assign_to_axis=axis,
                tubing=False, outline_translation=False)
        except Exception:
            self._plane_widget = None

    def _remove_plane_widget(self):
        if self._plane_widget is not None:
            try:
                self.plotter.clear_plane_widgets()
            except Exception:
                pass
            self._plane_widget = None

    def _on_plane_widget(self, normal, origin):
        """Drag callback: map plane origin to hold_height."""
        import numpy as np
        if self._part_mesh is None or self._section_cb is None:
            return
        d = np.asarray(self._seating_dir, dtype=float)
        mx = float((self._part_mesh.points @ d).max())
        proj = float(np.dot(np.asarray(origin, dtype=float), d))
        self._dragging = True
        try:
            self._section_cb(mx - proj)
        except Exception:
            pass
        finally:
            self._dragging = False

    def set_hold(self, hold_height):
        """Update cradle depth live."""
        self._hold = float(hold_height)
        if self._cav_on:
            self._update_overlays()
        if self._section_on:
            self._section_timer.start(140)   # debounce heavy part cutaway
        if (self._plane_widget is not None and not self._dragging):
            try:
                rep = self._plane_widget.GetRepresentation()
                rep.SetOrigin(*self._section_origin())
            except Exception:
                pass

    def _reclip_part(self):
        """Debounced part re-clip."""
        if self._section_on:
            self._rebuild_part_scene()

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

    def clear(self):
        if self.plotter:
            self.plotter.clear()
            self._add_plane_indicator()

    def reset_camera(self):
        if self.plotter:
            self.plotter.reset_camera()

    # ---- seating-down camera orientation ----
    def _seat_view(self, seating_dir):
        """Target (focal, view_dir, up) for 3/4 seating-down view."""
        import numpy as np
        d = np.asarray(seating_dir, float)
        n = np.linalg.norm(d)
        if n < 1e-9:
            return None
        d = d / n
        up = -d
        ref = _least_aligned_axis(up)
        right = np.cross(up, ref); right /= np.linalg.norm(right)
        fwd = np.cross(right, up); fwd /= np.linalg.norm(fwd)
        view = fwd * 1.0 + right * 0.6 + up * 0.8
        view /= np.linalg.norm(view)
        b = (self._part_mesh.bounds if self._part_mesh is not None
             else self.plotter.bounds)
        foc = np.array([(b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0,
                        (b[4] + b[5]) / 2.0], float)
        return foc, view, up

    def orient_camera(self, seating_dir, animate=True, fit=False,
                      duration_ms=420, on_done=None):
        """Swing camera so seating_dir points down."""
        if not self.plotter:
            if on_done:
                on_done()
            return
        import numpy as np
        target = self._seat_view(seating_dir)
        if target is None:
            if on_done:
                on_done()
            return
        foc1, dir1, up1 = target
        cam = self.plotter.camera
        pos0 = np.asarray(cam.position, float)
        foc0 = np.asarray(cam.focal_point, float)
        up0 = np.asarray(cam.up, float)
        radius = float(np.linalg.norm(pos0 - foc0))
        if radius < 1e-6:
            radius = self._scene_size(self._part_mesh.bounds
                                      if self._part_mesh is not None
                                      else self.plotter.bounds)
        self._stop_camera_anim()
        if fit or not animate:
            cam.focal_point = tuple(foc1)
            cam.position = tuple(foc1 + dir1 * radius)
            cam.up = tuple(up1)
            if fit:
                self.plotter.reset_camera()
            self.plotter.render()
            if on_done:
                on_done()
            return
        dir0 = (pos0 - foc0) / radius
        frames = max(2, int(duration_ms / 16))
        self._cam_anim = dict(foc0=foc0, foc1=foc1, dir0=dir0, dir1=dir1,
                              up0=up0, up1=up1, r=radius, i=0, n=frames,
                              on_done=on_done)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._camera_anim_step)
        self._anim_timer.start(16)

    def _camera_anim_step(self):
        a = self._cam_anim
        if a is None or not self.plotter:
            self._stop_camera_anim()
            return
        a["i"] += 1
        t = min(1.0, a["i"] / a["n"])
        te = t * t * (3.0 - 2.0 * t)         # smoothstep
        import numpy as np
        foc = a["foc0"] + (a["foc1"] - a["foc0"]) * te
        dirv = _slerp(a["dir0"], a["dir1"], te)
        up = _slerp(a["up0"], a["up1"], te)
        cam = self.plotter.camera
        cam.focal_point = tuple(foc)
        cam.position = tuple(np.asarray(foc) + np.asarray(dirv) * a["r"])
        cam.up = tuple(up)
        self.plotter.render()
        if t >= 1.0:
            cb = a.get("on_done")
            self._stop_camera_anim()
            if cb:
                cb()

    def _stop_camera_anim(self):
        if self._anim_timer is not None:
            try:
                self._anim_timer.stop()
                self._anim_timer.timeout.disconnect()
            except Exception:
                pass
            self._anim_timer = None
        self._cam_anim = None

    # ---- slide-in/out preview ----
    def set_slide_part(self, mesh, slide_dir=(0, 0, 1), slide_dist=0.0):
        """Arm slide preview; mesh=None disarms."""
        import numpy as np
        self._stop_slide()
        if mesh is None or not self.plotter:
            self._slide_mesh = None
            self._show_slide_overlay(False)
            return
        d = np.asarray(slide_dir, float)
        n = np.linalg.norm(d)
        self._slide_dir = tuple(d / n) if n > 1e-9 else (0.0, 0.0, 1.0)
        self._slide_mesh = mesh
        self._slide_dist = float(slide_dist)
        self._ensure_slide_overlay()
        self._show_slide_overlay(True)

    def _add_slide_actor(self):
        """Add seated part as semi-transparent actor."""
        if self._slide_mesh is None or not self.plotter:
            return None
        self._slide_actor = self.plotter.add_mesh(
            self._slide_mesh, color="#9fb3d1", opacity=0.45, show_edges=False,
            pickable=False, smooth_shading=True, specular=0.2)
        return self._slide_actor

    def _set_slide_offset(self, offset):
        """Translate slide actor offset mm along slide dir."""
        if self._slide_actor is None:
            return
        import numpy as np
        p = np.asarray(self._slide_dir, float) * float(offset)
        try:
            self._slide_actor.SetPosition(float(p[0]), float(p[1]), float(p[2]))
        except Exception:
            try:
                self._slide_actor.position = (p[0], p[1], p[2])
            except Exception:
                pass

    def _play_slide(self):
        """One cycle: spawn above pocket, slide in, pause, slide out, remove."""
        if self._slide_mesh is None or not self.plotter:
            return
        self._stop_slide()
        self._add_slide_actor()
        self._set_slide_offset(self._slide_dist)     # start popped out
        self._slide_i = 0
        self._slide_timer.start(16)

    _SLIDE_IN, _SLIDE_HOLD, _SLIDE_OUT = 52, 32, 52  # frames per phase

    def _slide_step(self):
        if self._slide_actor is None:
            self._stop_slide()
            return
        i = self._slide_i
        self._slide_i += 1
        nin, nh, nout = self._SLIDE_IN, self._SLIDE_HOLD, self._SLIDE_OUT
        d = self._slide_dist
        if i <= nin:                                  # slide in
            t = i / nin
            off = d * (1.0 - t * t * (3.0 - 2.0 * t))
        elif i <= nin + nh:                           # hold
            off = 0.0
        elif i <= nin + nh + nout:                    # slide out
            t = (i - nin - nh) / nout
            off = d * (t * t * (3.0 - 2.0 * t))
        else:
            self._stop_slide()
            return
        self._set_slide_offset(off)
        try:
            self.plotter.render()
        except Exception:
            pass

    def _toggle_pop(self):
        """Pop part into pocket or remove it."""
        if self._slide_mesh is None or not self.plotter:
            return
        self._slide_timer.stop()
        if self._slide_actor is not None and self._slide_popped:
            self._remove_slide_actor()
            self._slide_popped = False
        else:
            self._remove_slide_actor()
            self._add_slide_actor()
            self._set_slide_offset(0.0)
            self._slide_popped = True
        try:
            self.plotter.render()
        except Exception:
            pass

    def _remove_slide_actor(self):
        if self._slide_actor is not None:
            try:
                self.plotter.remove_actor(self._slide_actor)
            except Exception:
                pass
            self._slide_actor = None

    def _stop_slide(self):
        self._slide_timer.stop()
        self._remove_slide_actor()
        self._slide_popped = False

    # ---- overlay Play/Pop buttons ----
    def _ensure_slide_overlay(self):
        if self._slide_play_btn is not None:
            return
        from PySide6.QtWidgets import QToolButton
        from PySide6.QtCore import QSize
        from .icons import make_icon
        css = ("QToolButton{background:rgba(40,44,52,210);"
               " border:1px solid #5a6680; border-radius:4px;}"
               "QToolButton:hover{background:rgba(60,66,80,230);}")
        play = QToolButton(self)
        play.setIcon(make_icon("play", "#e8ecf2", 18))
        play.setIconSize(QSize(18, 18))
        play.setToolTip("Play: slide the part in and out of its pocket")
        pop = QToolButton(self)
        pop.setIcon(make_icon("popin", "#e8ecf2", 18))
        pop.setIconSize(QSize(18, 18))
        pop.setToolTip("Pop the part into / out of its pocket")
        for b in (play, pop):
            b.setFixedSize(30, 30)
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet(css)
            b.setCursor(Qt.PointingHandCursor)
        play.clicked.connect(lambda: self._play_slide())
        pop.clicked.connect(lambda: self._toggle_pop())
        self._slide_play_btn = play
        self._slide_pop_btn = pop
        self._position_slide_overlay()

    def _show_slide_overlay(self, on):
        for b in (self._slide_play_btn, self._slide_pop_btn):
            if b is not None:
                b.setVisible(bool(on))
                if on:
                    b.raise_()

    def _position_slide_overlay(self):
        if self._slide_play_btn is None:
            return
        self._slide_play_btn.move(8, 8)
        self._slide_pop_btn.move(44, 8)

    # ---- 3D on-object tilt gizmo ----
    def enable_tilt_gizmo3d(self, callback):
        """Enable draggable rotation arc; callback(deg) fires live."""
        if not self.plotter:
            return
        self._tilt3d_cb = callback
        self._tilt3d_on = True
        self._install_tilt3d_observers()
        self._redraw_tilt_gizmo3d()

    def set_tilt_gizmo3d(self, axis, angle, mode="A"):
        """Sync gizmo axis + angle + mode (no callback)."""
        self._tilt3d_axis = str(axis).upper()
        self._tilt3d_angle = max(-45.0, min(45.0, float(angle)))
        self._tilt3d_mode = str(mode).upper()
        if self._tilt3d_on:
            self._redraw_tilt_gizmo3d()

    def show_tilt_gizmo3d(self, on):
        self._tilt3d_on = bool(on)
        self._redraw_tilt_gizmo3d()

    def _tilt3d_basis(self):
        """(centre, radius, up, lean) for gizmo ring."""
        import numpy as np
        if self._part_mesh is None or not self.plotter:
            return None
        b = self._part_mesh.bounds
        cx, cy = (b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0
        size = max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 1.0)
        R = size * 0.6
        up = np.array([0.0, 0.0, 1.0])
        lean = np.array([0.0, 1.0, 0.0]) if self._tilt3d_axis == "X" \
            else np.array([1.0, 0.0, 0.0])
        if self._tilt3d_mode == "A":          # rotate-part
            lean = -lean
            centre = np.array([cx, cy, (b[4] + b[5]) / 2.0])
        else:                                  # rotate-tray
            centre = np.array([cx, cy, b[4]])
        return centre, R, up, lean

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
        import numpy as np
        import math
        if not self.plotter:
            return
        for a in self._tilt3d_actors:
            try:
                self.plotter.remove_actor(a)
            except Exception:
                pass
        self._tilt3d_actors = []
        if not self._tilt3d_on or self._part_mesh is None:
            return
        import pyvista as pv
        bg = self._tilt3d_basis()
        if bg is None:
            return
        c, R, up, lean = bg
        col = self._tilt3d_color()
        try:
            # full ring
            ring = np.array([c + R * (math.cos(math.radians(d)) * up
                                      + math.sin(math.radians(d)) * lean)
                             for d in range(0, 361, 6)])
            self._tilt3d_actors.append(self.plotter.add_mesh(
                pv.lines_from_points(ring), color=col, line_width=3,
                pickable=False, reset_camera=False, opacity=0.55))
            # usable +/-45 sweep
            sweep = np.array([c + R * (math.cos(math.radians(d)) * up
                                       + math.sin(math.radians(d)) * lean)
                              for d in range(-45, 46, 3)])
            self._tilt3d_actors.append(self.plotter.add_mesh(
                pv.lines_from_points(sweep), color=col, line_width=6,
                pickable=False, reset_camera=False))
            # handle + spoke
            h = self._tilt3d_handle()
            self._tilt3d_actors.append(self.plotter.add_mesh(
                pv.Sphere(radius=R * 0.1, center=tuple(h)), color=col,
                pickable=False, reset_camera=False))
            self._tilt3d_actors.append(self.plotter.add_mesh(
                pv.lines_from_points(np.array([c, h])), color=col, line_width=2,
                pickable=False, reset_camera=False))
            txt = ("Rotate Part" if self._tilt3d_mode == "A" else "Rotate Tray")
            self._tilt3d_actors.append(self.plotter.add_point_labels(
                [tuple(c + up * R * 1.15)], ["%s  %+.0f°" % (txt, self._tilt3d_angle)],
                font_size=12, text_color=col, shape=None, show_points=False,
                always_visible=True, reset_camera=False))
            self.plotter.render()
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
            # grab handle: swap to no-op style to suppress camera during drag
            self._tilt3d_dragging = True
            try:
                from vtkmodules.vtkInteractionStyle import vtkInteractorStyleUser
            except Exception:
                try:
                    from vtk import vtkInteractorStyleUser
                except Exception:
                    vtkInteractorStyleUser = None
            if vtkInteractorStyleUser is not None:
                self._tilt3d_saved_style = obj.GetInteractorStyle()
                obj.SetInteractorStyle(vtkInteractorStyleUser())

    def _tilt3d_move(self, obj, _evt):
        if not self._tilt3d_dragging:
            return
        try:
            x, y = obj.GetEventPosition()
        except Exception:
            return
        ang = self._tilt3d_angle_at(x, y)
        if ang is None:
            return
        self._tilt3d_angle = max(-45.0, min(45.0, ang))
        self._redraw_tilt_gizmo3d()
        if self._tilt3d_cb:
            try:
                self._tilt3d_cb(self._tilt3d_angle)
            except Exception:
                pass

    def _tilt3d_release(self, obj, _evt):
        if not self._tilt3d_dragging:
            return
        self._tilt3d_dragging = False
        if self._tilt3d_saved_style is not None:
            try:
                obj.SetInteractorStyle(self._tilt3d_saved_style)
            except Exception:
                pass
            self._tilt3d_saved_style = None

    def _tilt3d_angle_at(self, x, y):
        """Angle (deg) of mouse ray hit on gizmo plane."""
        import numpy as np
        import math
        bg = self._tilt3d_basis()
        if bg is None:
            return None
        c, R, up, lean = bg
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
        n = np.cross(up, lean)
        denom = float(np.dot(ray, n))
        if abs(denom) < 1e-9:
            return None
        q = p0 + ray * (float(np.dot(c - p0, n)) / denom)
        v = q - c
        return math.degrees(math.atan2(float(np.dot(v, lean)),
                                       float(np.dot(v, up))))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_slide_overlay()
