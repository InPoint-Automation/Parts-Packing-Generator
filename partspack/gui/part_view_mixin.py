# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# central split view, part overlay panel, part-view refresh

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QPushButton, QLineEdit, QFrame, QStackedWidget

from ..params import Params, Axis
from .widgets import field
from .theme import OFFICE
from .viewer import Viewer
from .mw_common import _enum_values


class PartViewMixin:
    # central part/tray split view
    def _build_central(self):
        from PySide6.QtWidgets import QSplitter
        self.viewer_part = Viewer(self)
        self.viewer_tray = Viewer(self)
        self.viewer_tray.set_ghost_all_callback(self._toggle_ghost_all)
        self.viewer_part.enable_translate_gizmo3d(self._on_section_drag)
        self.viewer_part.enable_tilt_gizmo3d(self._on_tilt_gizmo,
                                             on_release=self._on_tilt_release)
        self.viewer_part.set_tilt_gizmo3d(self.params.part_lean_axis,
                                          self.params.part_lean_deg, "A")
        self.viewer_part.show_tilt_gizmo3d(False)
        self.viewer_part.enable_spin_gizmo3d(self._on_spin_gizmo)
        self.viewer_part.set_spin_gizmo3d(self.params.pocket_rotate_deg)
        self.viewer_part.show_spin_gizmo3d(False)
        part_box = QWidget()
        ph = QHBoxLayout(part_box)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.setSpacing(2)
        ph.addWidget(self.viewer_part, 1)
        self._part_box = part_box
        self._build_part_overlay()
        split = QSplitter(Qt.Horizontal)
        split.addWidget(part_box)
        split.addWidget(self.viewer_tray)
        split.setSizes([600, 600])
        self._split = split
        self._view_btns = {}
        self._view_mode = "split"
        self.setCentralWidget(split)

    def _apply_view_mode(self, mode):
        """Show part, tray, or both."""
        self._view_mode = mode
        self._part_box.setVisible(mode in ("part", "split"))
        self.viewer_tray.setVisible(mode in ("tray", "split"))
        for m, btn in self._view_btns.items():
            btn.blockSignals(True)
            btn.setChecked(m == mode)
            btn.blockSignals(False)

    # part overlay panel
    def _build_part_overlay(self):
        """Part-action settings panel."""
        self._part_widgets = []          # (name, widget)
        panel = QFrame(self.viewer_part)
        panel.setObjectName("part_panel")
        panel.setStyleSheet(
            "#part_panel{background:%s; border:1px solid %s; border-radius:6px;}"
            % (OFFICE.get("panel", "#f3f6fb"), OFFICE["border"]))
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(8, 6, 8, 8)
        pv.setSpacing(4)
        self._part_title = QLabel("")
        self._part_title.setStyleSheet(
            "font-weight:bold; color:%s; font-size:9pt;" % OFFICE["text"])
        pv.addWidget(self._part_title)
        self._part_stack = QStackedWidget()
        pv.addWidget(self._part_stack)
        self._part_pages = {}
        for name, builder in (("ghost_height", self._page_ghost_height),
                              ("rotate_parts", self._page_rotate_parts),
                              ("rotate_tray", self._page_rotate_tray),
                              ("change_axis", self._page_change_axis)):
            self._part_pages[name] = self._part_stack.addWidget(builder())
        from .icons import UI_SCALE
        panel.setMinimumWidth(int(round(230 * UI_SCALE)))
        panel.move(int(round(12 * UI_SCALE)), int(round(48 * UI_SCALE)))
        panel.hide()
        self._part_panel = panel
        self._active_part_action = None

    def _ov_dspin(self, name, lo, hi, dec, slot):
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setDecimals(dec)
        w.setSingleStep(10 ** -dec if dec else 1)
        w.valueChanged.connect(slot)
        self._part_widgets.append((name, w))
        return w

    def _reset_params(self, names):
        """Reset named params to defaults"""
        d = Params()
        for n in names:
            self._set(n, getattr(d, n))
        self._refresh_part_panel()
        self._sync_axis_btns()
        self._apply_part_gizmos()

    def _reset_btn(self, names):
        from PySide6.QtWidgets import QPushButton
        b = QPushButton("Reset")
        b.setFocusPolicy(Qt.NoFocus)
        b.clicked.connect(lambda: self._reset_params(names))
        return b

    def _page_ghost_height(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        sp = self._ov_dspin("hold_height", 1, 80, 1,
                            lambda v: self._set("hold_height", float(v)))
        lay.addWidget(field("cradle depth (mm)", sp))
        lay.addWidget(self._reset_btn(["hold_height"]))
        return w

    def _page_rotate_parts(self):
        """Spin + lean parts."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        sp = self._ov_dspin("pocket_rotate_deg", 0, 360, 0, self._ov_spin_deg)
        lay.addWidget(field("spin deg (Z, all pockets)", sp))
        ln = self._ov_dspin("part_lean_deg", -45, 45, 0,
                            lambda v: self._tilt_typed(float(v)))
        lay.addWidget(field("lean deg (upright pocket)", ln))
        lay.addWidget(field("lean axis", self._ov_axis_combo("part_lean_axis")))
        lay.addWidget(self._reset_btn(["pocket_rotate_deg", "part_lean_deg"]))
        return w

    def _ov_spin_deg(self, v):
        if not self.params.pocket_rotate:
            self._set("pocket_rotate", True)
        self._set("pocket_rotate_deg", float(v))
        self.viewer_part.set_spin_gizmo3d(float(v))

    def _ov_axis_combo(self, name, items=("X", "Y")):
        c = QComboBox()
        c.addItems(list(items))
        c.activated.connect(
            lambda _i, cc=c, n=name: self._set(n, cc.currentText()))
        self._part_widgets.append((name, c))
        return c

    def _page_rotate_tray(self):
        """Angle pocket for tilt insertion."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        sp = self._ov_dspin("tray_angle_deg", -45, 45, 0,
                            lambda v: self._tilt_typed(float(v)))
        lay.addWidget(field("angle deg (angled pocket)", sp))
        lay.addWidget(field("axis", self._ov_axis_combo("tray_angle_axis")))
        lay.addWidget(self._reset_btn(["tray_angle_deg"]))
        return w

    def _page_change_axis(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(3)
        from .icons import UI_SCALE
        self._axis_btns = {}
        for ax in _enum_values(Axis):
            b = QToolButton()
            b.setText(ax)
            b.setCheckable(True)
            b.setFixedWidth(int(round(34 * UI_SCALE)))
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _c=False, a=ax: self._set_axis(a))
            self._axis_btns[ax] = b
            h.addWidget(b)
        inv = QToolButton()
        inv.setText("Invert")
        inv.setCheckable(True)
        inv.setFocusPolicy(Qt.NoFocus)
        inv.clicked.connect(
            lambda _c=False: self._set("flip", self._invert_btn.isChecked()))
        self._invert_btn = inv
        h.addWidget(inv)
        lay.addWidget(field("down axis", row))
        lay.addWidget(self._reset_btn(["seating_axis", "flip"]))
        return w

    def _set_axis(self, ax):
        self._set("seating_axis", ax)
        self._sync_axis_btns()

    def _sync_axis_btns(self):
        for ax, b in getattr(self, "_axis_btns", {}).items():
            b.blockSignals(True)
            b.setChecked(ax == str(self.params.seating_axis))
            b.blockSignals(False)
        inv = getattr(self, "_invert_btn", None)
        if inv is not None:
            inv.blockSignals(True)
            inv.setChecked(bool(self.params.flip))
            inv.blockSignals(False)

    # title, gizmo, mode
    _PART_ACTIONS = {
        "ghost_height": ("Cradle depth", None, None),
        "rotate_parts": ("Rotate parts", "spin+tilt", "A"),
        "rotate_tray": ("Rotate tray", "tilt", "B"),
        "change_axis": ("Change axis", None, None),
    }

    def _toggle_part_action(self, name):
        """Show one part-action page."""
        btn = self._part_btns.get(name)
        on = btn.isChecked() if btn is not None else False
        for other, b in self._part_btns.items():
            if other != name:
                b.blockSignals(True)
                b.setChecked(False)
                b.blockSignals(False)
        if not on:
            self._active_part_action = None
            self._apply_part_gizmos()
            self._part_panel.hide()
            return
        if self._view_mode == "tray":
            self._apply_view_mode("part")
        title, _gizmo, _mode = self._PART_ACTIONS[name]
        self._active_part_action = name
        self._part_title.setText(title)
        self._part_stack.setCurrentIndex(self._part_pages[name])
        self._refresh_part_panel()
        self._apply_part_gizmos()
        self._part_panel.adjustSize()
        self._part_panel.show()
        self._part_panel.raise_()

    def _apply_part_gizmos(self):
        """Show active action's gizmos."""
        act = getattr(self, "_active_part_action", None)
        _t, gizmo, _m = self._PART_ACTIONS.get(act, (None, None, None))
        on = self.cfg.get("show_gizmo", True)
        tilt = on and gizmo in ("tilt", "spin+tilt")
        spin = on and gizmo in ("spin", "spin+tilt")

        def _apply():
            if tilt and act == "rotate_tray":
                self.viewer_part.set_tilt_gizmo3d(self.params.tray_angle_axis,
                                                  self.params.tray_angle_deg, "B")
            elif tilt:
                self.viewer_part.set_tilt_gizmo3d(self.params.part_lean_axis,
                                                  self.params.part_lean_deg, "A")
            self.viewer_part.show_tilt_gizmo3d(tilt)
            self.viewer_part.show_spin_gizmo3d(spin)
            self.viewer_part.show_translate_gizmo3d(on and act == "ghost_height")

        # page switch fires ~30 gizmo frames, coalesce to one
        self.viewer_part.render_batched(_apply)

    def _refresh_ghost_all_if_on(self):
        """Redraw Ghost-all if active."""
        btn = getattr(self.viewer_tray, "_ghost_all_btn", None)
        if btn is not None and btn.isChecked():
            self.viewer_tray.set_part_array(self._build_ghost_all_meshes(),
                                            on=True)

    @staticmethod
    def _set_widget_value(w, val):
        """Push value into bound widget, signals already blocked"""
        if isinstance(w, QComboBox):
            w.setCurrentText(str(val))
        elif isinstance(w, QCheckBox):
            w.setChecked(bool(val))
        elif isinstance(w, QLineEdit):
            w.setText(str(val or ""))
        elif isinstance(w, QSpinBox):
            w.setValue(int(val))
        elif isinstance(w, QDoubleSpinBox):
            w.setValue(w.minimum() if val is None else float(val))

    def _refresh_part_panel(self):
        """Sync params into overlay widgets."""
        for name, w in getattr(self, "_part_widgets", []):
            val = getattr(self.params, name)
            w.blockSignals(True)
            self._set_widget_value(w, val)
            w.blockSignals(False)
        self._sync_axis_btns()

    def _set_part_widget(self, name, v):
        """Set one overlay spin value."""
        for n, w in getattr(self, "_part_widgets", []):
            if n == name and isinstance(w, QDoubleSpinBox):
                w.blockSignals(True)
                w.setValue(float(v))
                w.blockSignals(False)

