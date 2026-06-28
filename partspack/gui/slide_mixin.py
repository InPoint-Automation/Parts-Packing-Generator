# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# slide preview, overlay buttons, part array


from PySide6.QtCore import Qt

from .viewer_common import _OVERLAY_BTN_CSS


class SlideMixin:
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
        self._depth_peel()
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
        """One cycle: slide in, hold, slide out."""
        if self._slide_mesh is None or not self.plotter:
            return
        self._stop_slide()
        self._add_slide_actor()
        self._set_slide_offset(self._slide_dist)
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

    def _ensure_slide_overlay(self):
        if self._slide_play_btn is not None:
            return
        from PySide6.QtWidgets import QToolButton
        from PySide6.QtCore import QSize
        from .icons import make_icon, UI_SCALE
        specs = [("play", "Play", "Play: slide the part in and out of its pocket",
                  False),
                 ("popin", "Pop", "Pop the part into / out of its pocket", False),
                 ("grid", "Ghost all", "Ghost all: overlay every placed part to "
                  "check collision / spacing", True)]
        isz = max(1, int(round(22 * UI_SCALE)))
        bw, bh = int(round(64 * UI_SCALE)), int(round(56 * UI_SCALE))
        btns = []
        for icon, label, tip, checkable in specs:
            b = QToolButton(self)
            b.setIcon(make_icon(icon, None, isz))
            b.setIconSize(QSize(isz, isz))
            b.setText(label)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFixedSize(bw, bh)
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet(_OVERLAY_BTN_CSS)
            b.setCursor(Qt.PointingHandCursor)
            btns.append(b)
        play, pop, gall = btns
        play.clicked.connect(lambda: self._play_slide())
        pop.clicked.connect(lambda: self._toggle_pop())
        gall.clicked.connect(self._on_ghost_all_clicked)
        self._slide_play_btn = play
        self._slide_pop_btn = pop
        self._ghost_all_btn = gall
        self._position_slide_overlay()

    def set_ghost_all_callback(self, cb):
        self._ghost_all_cb = cb

    def _on_ghost_all_clicked(self):
        if self._ghost_all_cb is not None:
            self._ghost_all_cb(self._ghost_all_btn.isChecked())

    def set_part_array(self, meshes, on=True):
        """Overlay placed-part copies."""
        self._clear_part_array()
        if not on or not meshes or not self.plotter:
            try:
                self.plotter.render()
            except Exception:
                pass
            return
        self._depth_peel()
        for m in meshes:
            if m is None or not getattr(m, "n_points", 0):
                continue
            try:
                self._array_actors.append(self.plotter.add_mesh(
                    m, color="#9fb3d1", opacity=0.45, show_edges=False,
                    smooth_shading=True, specular=0.2, pickable=False))
            except Exception:
                pass
        try:
            self.plotter.render()
        except Exception:
            pass

    def _clear_part_array(self):
        for a in self._array_actors:
            try:
                self.plotter.remove_actor(a)
            except Exception:
                pass
        self._array_actors = []

    def _show_slide_overlay(self, on):
        for b in (self._slide_play_btn, self._slide_pop_btn):
            if b is not None:
                b.setVisible(bool(on))
                if on:
                    b.raise_()

    def _position_slide_overlay(self):
        if self._slide_play_btn is None:
            return
        from .icons import UI_SCALE
        x0, y = int(round(8 * UI_SCALE)), int(round(44 * UI_SCALE))
        step = int(round(68 * UI_SCALE))      # 64 button + 4 gap
        self._slide_play_btn.move(x0, y)
        self._slide_pop_btn.move(x0 + step, y)
        if self._ghost_all_btn is not None:
            self._ghost_all_btn.move(x0 + 2 * step, y)

