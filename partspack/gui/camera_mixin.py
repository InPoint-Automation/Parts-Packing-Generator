# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# camera orientation + swing animation


from PySide6.QtCore import QTimer

from .viewer_common import _slerp, _least_aligned_axis


class CameraMixin:
    def clear(self):
        if self.plotter:
            self.plotter.clear()
            self._add_plane_indicator()

    def reset_camera(self):
        if self.plotter:
            self.plotter.reset_camera()

    def _seat_view(self, seating_dir):
        # target focal, view_dir, up for 3/4 seating-down view
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
        # swing camera so seating_dir points down
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
            self._stop_camera_anim()      # fires on_done once

    def _stop_camera_anim(self):
        # CAVEAT: must always fire pending on_done, even if swing interrupted.
        # on_done re-arms live ghost rebuild; dropping it leaves ghost gone.
        # Fires once: cam_anim cleared first.
        if self._anim_timer is not None:
            try:
                self._anim_timer.stop()
                self._anim_timer.timeout.disconnect()
            except Exception:
                pass
            self._anim_timer = None
        cb = None
        if self._cam_anim is not None:
            cb = self._cam_anim.get("on_done")
            self._cam_anim = None
        if cb:
            try:
                cb()
            except Exception:
                pass

