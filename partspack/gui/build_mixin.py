# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# build orchestration, ghost-all, export

from __future__ import annotations

import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox

from .dialogs import _BuildThread, BuildProgressDialog


class BuildMixin:
    def _start_build(self, what, fn, silent=False):
        """Run fn(progress) on worker thread."""
        if getattr(self, "_build_thread", None) is not None:
            self.statusBar().showMessage("A build is already running...")
            return
        if not silent:
            self._set_build_buttons(False)
        self.statusBar().showMessage(
            "%s: %s..." % (what, "refreshing" if silent else "building"))
        if not silent:
            self.readout.setText("%s: building..." % what)
            dlg = BuildProgressDialog(what, self)
            self._progress_dialog = dlg
            dlg.show()

        # tessellate in worker, only finished PolyData crosses thread
        def _job(progress, _fn=fn, _what=what):
            result = _fn(progress)
            from .mesh import tessellate_for_display
            from ..core import profiling
            with profiling.timed_print("display tessellation [%s]" % _what):
                meshes = tessellate_for_display(result, _what)
            return (result, meshes)

        th = _BuildThread(_job, self)
        if not silent:
            th.progress.connect(self._progress_dialog.update_progress)
        th.done.connect(lambda res, w=what: self._on_build_done(w, res))
        th.failed.connect(lambda msg, w=what: self._on_build_failed(w, msg))
        th.finished.connect(self._build_finished)
        self._build_thread = th
        th.start()

    def _auto_rebuild(self):
        """Debounced live cavity-ghost refresh."""
        if not (self._ghost_active and self.bridge.step_path
                and self.cfg.get("live_preview", True)):
            return
        if self._build_thread is not None:
            self._rebuild_dirty = True
            return
        prm = self.params.model_copy()
        self._start_build(
            "Ghost", lambda pr: self.bridge.build_ghost(prm, progress=pr),
            silent=True)

    def _on_build_done(self, what, payload):
        result, meshes = payload
        import sys
        sys.stderr.write(
            "[gui] _on_build_done what=%s trays=%d tray_mesh=%s view_mode=%s\n"
            % (what, len(getattr(result, "trays", []) or []),
               meshes.get("tray") is not None, self._view_mode))
        if what == "Ghost":
            self._show_ghost(result, meshes)
            return
        if what == "Spec":
            # stash only if part+params still match snapshot built for
            snap, self._spec_snapshot = self._spec_snapshot, None
            if snap is not None and snap == self._spec_key():
                self._spec_result = (snap, payload)
            return
        # full build takes over view, stop live ghost refresh
        self._ghost_active = False
        self._rebuild_dirty = False
        self._result_dirty = False
        self._refresh_generate_style()
        if what == "Batch":
            self._on_batch_done(result, meshes)
            return
        n = len(result.trays)
        label = "drawer" if what == "Drawer" else "tray"
        msg = "%s: built %d %s%s." % (what, n, label, "" if n == 1 else "s")
        if result.warnings:
            msg += "  (" + "; ".join(result.warnings) + ")"
        self.statusBar().showMessage(msg)
        self.readout.setText(msg)
        if result.trays:
            self.viewer_tray.set_bed(self.params.bed_x or self.cfg.get("bed_x"),
                                     self.params.bed_y or self.cfg.get("bed_y"))
            self.viewer_tray.show_polydata(
                meshes.get("tray"), color="#cdd6e6",
                title="%s: print coordinates (Z up, floor at 0)"
                % ("Drawer" if what == "Drawer" else "Tray"))
            self._arm_slide_preview(result)
            self._refresh_ghost_all_if_on()    # rebuild wiped it
            if self._view_mode != "split":
                self._apply_view_mode("tray")

    def _arm_slide_preview(self, result):
        """Arm slide-in/out part preview in tray viewer."""
        place = getattr(result, "part_place", None)
        to_oriented = getattr(result, "to_oriented", None)
        raw = getattr(self.viewer_part, "_part_mesh", None)
        if place is None or to_oriented is None or raw is None:
            self.viewer_tray.set_slide_part(None)
            self._seated_part = None
            self._ghost_centres = []
            return
        import numpy as np
        M = np.asarray(to_oriented, float)
        pts = np.asarray(raw.points, float)
        cap_pts = (M[:3, :3] @ pts.T).T + M[:3, 3]
        # lean preview into oblique pocket
        if float(self.params.tray_angle_deg):
            from ..core.orient import _rodrigues, _AXIS_VEC
            axisvec = np.asarray(_AXIS_VEC[str(self.params.tray_angle_axis)], float)
            R = _rodrigues(axisvec, -np.radians(float(self.params.tray_angle_deg)))
            cap_pts = (R @ cap_pts.T).T
        seated_pts = cap_pts + np.asarray(place, float)
        seated = raw.copy()
        seated.points = seated_pts
        d = np.asarray(getattr(result, "part_slide_dir", (0.0, 0.0, 1.0)), float)
        d = d / (np.linalg.norm(d) or 1.0)
        span = float((seated_pts @ d).max() - (seated_pts @ d).min())
        # ghost-all base: un-spun seated part + pocket centres
        self._seated_part = seated
        self._ghost_centres = list(getattr(result, "centres", []) or [])
        self._ghost_spin = float(getattr(result, "pocket_spin", 0.0) or 0.0)
        # pocket-0 spin so slide matches carved pocket
        slide_mesh, slide_d = seated, d
        if self._ghost_spin and self._ghost_centres:
            slide_mesh, slide_d = self._spin_about(
                seated, d, self._ghost_centres[0], self._ghost_spin)
        self.viewer_tray.set_slide_part(slide_mesh, tuple(slide_d), span + 8.0)

    def _toggle_ghost_all(self, on):
        """Overlay all placed parts."""
        if not on:
            self.viewer_tray.set_part_array(None, on=False)
            return
        self.viewer_tray.set_part_array(self._build_ghost_all_meshes(), on=True)

    @staticmethod
    def _spin_about(mesh, slide_dir, centre, deg):
        """Rotate mesh and slide dir by deg about vertical axis at centre."""
        import numpy as np
        th = np.radians(float(deg))
        cos, sin = np.cos(th), np.sin(th)
        cx, cy = float(centre[0]), float(centre[1])
        pts = np.asarray(mesh.points, float).copy()
        dx, dy = pts[:, 0] - cx, pts[:, 1] - cy
        pts[:, 0] = cx + dx * cos - dy * sin
        pts[:, 1] = cy + dx * sin + dy * cos
        m = mesh.copy()
        m.points = pts
        d = np.asarray(slide_dir, float)
        sd = (d[0] * cos - d[1] * sin, d[0] * sin + d[1] * cos, d[2])
        return m, sd

    def _build_ghost_all_meshes(self):
        """Replicate seated part into every carved pocket."""
        import numpy as np
        seated = getattr(self, "_seated_part", None)
        centres = getattr(self, "_ghost_centres", None)
        if seated is None or not centres:
            return []
        spin = float(getattr(self, "_ghost_spin", 0.0) or 0.0)
        c0 = np.asarray(centres[0], float)
        th = np.radians(spin)
        cos, sin = np.cos(th), np.sin(th)
        base = np.asarray(seated.points, float)
        # part at pocket i = Rz(spin) * (seated - c0) + c_i
        out = []
        for (cx, cy) in centres:
            dx = base[:, 0] - c0[0]
            dy = base[:, 1] - c0[1]
            pts = base.copy()
            if spin:
                pts[:, 0] = cx + dx * cos - dy * sin
                pts[:, 1] = cy + dx * sin + dy * cos
            else:
                pts[:, 0] = cx + dx
                pts[:, 1] = cy + dy
            m = seated.copy()
            m.points = pts
            out.append(m)
        return out

    def _on_batch_done(self, results, meshes):
        """Show first batch tray, summarise rest."""
        n_trays = sum(len(r.trays) for _, r in results)
        warns = [w for _, r in results for w in r.warnings]
        msg = "Batch: built %d tray%s from %d part%s." % (
            n_trays, "" if n_trays == 1 else "s",
            len(results), "" if len(results) == 1 else "s")
        if warns:
            msg += "  (" + "; ".join(warns) + ")"
        self.statusBar().showMessage(msg)
        self.readout.setText(msg)
        if meshes.get("tray") is not None:
            self.viewer_tray.set_bed(self.params.bed_x or self.cfg.get("bed_x"),
                                     self.params.bed_y or self.cfg.get("bed_y"))
            self.viewer_tray.show_polydata(
                meshes.get("tray"), color="#cdd6e6",
                title="Batch: first part's tray (export writes all)")
            if self._view_mode != "split":
                self._apply_view_mode("tray")

    def _show_ghost(self, result, meshes):
        """Overlay cavity ghost on raw part."""
        cav = meshes.get("cavity")
        if cav is None or not self._btn_ghost.isChecked():
            return
        # cavity in part frame, viewer spins+leans via user-matrix
        cav_part = self._to_part_frame(cav, getattr(result, "to_part", None))
        self.viewer_part.set_cavity(cav_part, on=True)
        # top-half cradle overlay
        cav_top = meshes.get("cavity_top")
        if self.params.two_sided and cav_top is not None:
            cav_top = self._to_part_frame(
                cav_top, getattr(result, "to_part_top", None))
            self.viewer_part.set_cavity_top(cav_top, self._top_band(), on=True)
        else:
            self.viewer_part.set_cavity_top(None, 0.0, on=False)
        self._ghost_active = True
        self._ghost_built = True
        self.statusBar().showMessage(
            "Cavity ghost: amber shell past the part = clearance gap; it hugs "
            "where tight. Adjust part_clearance to tune.")

    @staticmethod
    def _to_part_frame(mesh, to_part):
        """Map PolyData to part frame by 4x4."""
        if mesh is None or to_part is None:
            return mesh
        import numpy as np
        m = mesh.copy()
        M = np.asarray(to_part, dtype=float)
        pts = np.asarray(m.points, dtype=float)
        m.points = (M[:3, :3] @ pts.T).T + M[:3, 3]
        return m

    def _on_build_failed(self, what, msg):
        import sys
        sys.stderr.write("[gui] _on_build_failed what=%s: %s\n" % (what, msg))
        if what == "Spec":                       # silent
            self._spec_snapshot = None
            return
        self.statusBar().showMessage("%s failed: %s" % (what, msg))
        self.readout.setText("%s failed:\n%s" % (what, msg))

    def _build_finished(self):
        self._build_thread = None
        self._set_build_buttons(True)
        dlg = getattr(self, "_progress_dialog", None)
        if dlg is not None:
            dlg.finish()
            self._progress_dialog = None
        # generate queued behind build: re-enter, adopt spec or warmed caches
        if self._pending_generate:
            self._pending_generate = False
            QTimer.singleShot(0, self.generate)
            return
        # param changed mid-build: fire one coalesced refresh
        if (self._rebuild_dirty and self._ghost_active
                and self.cfg.get("live_preview", True)):
            self._rebuild_dirty = False
            self._auto_timer.start(0)
        # idle: pre-run next Generate speculatively
        elif self._result_dirty and self.cfg.get("speculative_build", True):
            self._spec_timer.start(self._SPEC_MS)

    def _set_build_buttons(self, enabled):
        for b in (getattr(self, "_btn_ghost", None),
                  getattr(self, "_btn_generate", None),
                  getattr(self, "_btn_export", None),
                  getattr(self, "_btn_drawer", None),
                  getattr(self, "_btn_batch", None)):
            if b is not None:
                b.setEnabled(enabled)

    @staticmethod
    def _export_solids(res):
        """Bed-split tiles if multi-piece, else trays."""
        if res.tiles and len(res.tiles) > len(res.trays):
            return res.tiles
        return res.trays

    def export(self):
        if getattr(self.bridge, "batch", None):
            self._export_batch()
            return
        res = self.bridge.result
        if res is None or not res.trays:
            self.statusBar().showMessage("Generate a tray or drawer first.")
            return
        if self._result_dirty:
            r = QMessageBox.question(
                self, "Export",
                "Parameters changed since the last build.\n"
                "Export the geometry as currently shown anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                self.statusBar().showMessage("Export cancelled: regenerate first.")
                return
        from ..core import io
        solids = self._export_solids(res)
        fmt = str(self.params.export_format)
        base = os.path.splitext(os.path.basename(self.bridge.step_path))[0]
        suggested = os.path.join(self.cfg.get("last_dir") or os.path.expanduser("~"),
                                 "%s_tray.%s" % (base, fmt))
        path, _ = QFileDialog.getSaveFileName(
            self, "Export tray", suggested, "CAD (*.step *.stl *.3mf)")
        if not path:
            return
        stem, ext = os.path.splitext(path)
        out_fmt = ext.lstrip(".").lower() or fmt
        ext = ext or ("." + out_fmt)
        try:
            if len(solids) > 1:
                for i, s in enumerate(solids, 1):
                    io.export(s, "%s_%d%s" % (stem, i, ext), out_fmt,
                              self.params.tess_linear, self.params.tess_angular)
                msg = "Exported %d pieces (%s_1..%d)" % (
                    len(solids), os.path.basename(stem), len(solids))
            else:
                io.export(solids[0], path, out_fmt,
                          self.params.tess_linear, self.params.tess_angular)
                msg = "Exported %s" % os.path.basename(path)
            if getattr(res, "pins", None) is not None:
                io.export(res.pins, "%s_pins%s" % (stem, ext), out_fmt,
                          self.params.tess_linear, self.params.tess_angular)
                msg += " + pins"
        except Exception as e:
            hint = ""
            if out_fmt == "3mf":
                hint = ("\n\n3MF (lib3mf) is strict and rejects some valid "
                        "solids. Try exporting as STEP (the default) or STL.")
            QMessageBox.warning(self, "Export", "Export failed:\n%s%s" % (e, hint))
            return
        self.statusBar().showMessage(msg)

    def _export_batch(self):
        """Write each batch entry's tray(s) to chosen folder."""
        from ..core import io
        results = self.bridge.batch
        folder = QFileDialog.getExistingDirectory(
            self, "Export batch to folder",
            self.cfg.get("last_dir") or os.path.expanduser("~"))
        if not folder:
            return
        fmt = str(self.params.export_format)
        written = 0
        try:
            for entry, res in results:
                solids = self._export_solids(res)
                if not solids:
                    continue
                stem = os.path.join(folder, "%s_tray" % entry.name())
                if len(solids) > 1:
                    for i, s in enumerate(solids, 1):
                        io.export(s, "%s_%d.%s" % (stem, i, fmt), fmt,
                                  self.params.tess_linear,
                                  self.params.tess_angular)
                        written += 1
                else:
                    io.export(solids[0], "%s.%s" % (stem, fmt), fmt,
                              self.params.tess_linear, self.params.tess_angular)
                    written += 1
        except Exception as e:
            QMessageBox.warning(self, "Export", "Batch export failed:\n%s" % e)
            return
        self.statusBar().showMessage("Exported %d file(s) to %s"
                                     % (written, folder))

