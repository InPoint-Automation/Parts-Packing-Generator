# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# parameter dock: build, visibility, widget factories, writeback

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton, QWidget, QVBoxLayout, QFormLayout, QGroupBox, QLabel, QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QScrollArea, QDockWidget, QLineEdit

from ..params import Params, Axis, CaptureQuality, SkeletonStyle, BaseProfile, RibPattern, CellShape, DivotShape, DivotStrategy, DivotAxis, DivotSide, PinStyle, PackMode, Closure, SandwichMode, LabelMode, LabelPlace
from .theme import OFFICE
from .mw_common import _enum_values


class ParamPanelMixin:
    def _build_param_panel(self):
        dock = QDockWidget("Parameters", self)
        dock.setObjectName("param_dock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(8)

        v.addWidget(self._group("Capture", [
            ("bottom_margin", self._dspin("bottom_margin", 0, 20, 1)),
            ("part_clearance", self._dspin("part_clearance", 0, 2, 2)),
            ("mouth_chamfer", self._dspin("mouth_chamfer", 0, 5, 1)),
            ("resolution", self._combo("capture_quality", CaptureQuality)),
            ("min_internal_feature",
             self._dspin("min_internal_feature", 0, 50, 1)),
            ("remove_internal_features",
             self._check("remove_internal_features")),
            ("internal_wall_floor",
             self._dspin("internal_wall_floor", 0, 10, 1)),
        ]))

        v.addWidget(self._group("Grid & layout", [
            ("rows", self._ispin("rows", 1, 50)),
            ("cols", self._ispin("cols", 1, 50)),
            ("part_spacing", self._dspin("part_spacing", 0, 50, 1)),
            ("part_spacing_x", self._dspin_opt("part_spacing_x", -50, 50, 1)),
            ("part_spacing_y", self._dspin_opt("part_spacing_y", -50, 50, 1)),
            ("pack_mode", self._combo("pack_mode", PackMode)),
            ("row_stagger", self._dspin("row_stagger", 0, 1, 2)),
            ("border", self._dspin("border", 0, 40, 1)),
            ("margin_advanced", self._check("margin_advanced")),
            ("margin_x", self._dspin_opt("margin_x", 0, 60, 1, auto=-999)),
            ("margin_y", self._dspin_opt("margin_y", 0, 60, 1, auto=-999)),
            ("margin_front", self._dspin_opt("margin_front", 0, 60, 1, auto=-999)),
        ]))

        v.addWidget(self._group("Base & skeleton", [
            ("skeleton_style", self._combo("skeleton_style", SkeletonStyle)),
            ("cell_shape", self._combo("cell_shape", CellShape)),
            ("honeycomb_cell", self._dspin("honeycomb_cell", 2, 40, 1)),
            ("honeycomb_wall", self._dspin("honeycomb_wall", 0.4, 10, 1)),
            ("rib_width", self._dspin("rib_width", 0.4, 10, 1)),
            ("rib_spacing", self._dspin("rib_spacing", 2, 60, 1)),
            ("rib_pattern", self._combo("rib_pattern", RibPattern)),
            ("lightening_through", self._check("lightening_through")),
            ("outside_lightening", self._check("outside_lightening")),
            ("outside_wall", self._dspin("outside_wall", 0, 30, 1)),
            ("outside_rim", self._dspin("outside_rim", 0, 30, 1)),
            ("base_profile", self._combo("base_profile", BaseProfile)),
            ("rim_width", self._dspin("rim_width", 0, 20, 1)),
            ("wall_thickness", self._dspin("wall_thickness", 0, 20, 1)),
            ("corner_fillet", self._dspin("corner_fillet", 0, 30, 1)),
            ("edge_chamfer", self._dspin("edge_chamfer", 0, 10, 1)),
            ("magnet_dia", self._dspin("magnet_dia", 0, 12, 1)),
        ]))

        v.addWidget(self._group("Finger access", [
            ("divot_count", self._ispin("divot_count", 0, 2)),
            ("divot_shape", self._combo("divot_shape", DivotShape)),
            ("divot_diameter", self._dspin("divot_diameter", 0, 40, 1)),
            ("divot_depth", self._dspin("divot_depth", 0, 40, 1)),
            ("divot_chamfer", self._dspin("divot_chamfer", 0, 10, 1)),
            ("divot_axis", self._combo("divot_axis", DivotAxis)),
            ("divot_side", self._combo("divot_side", DivotSide)),
            ("divot_offset", self._dspin("divot_offset", -50, 50, 1)),
            ("divot_strategy", self._combo("divot_strategy", DivotStrategy)),
            ("push_min_size", self._dspin("push_min_size", 0, 200, 1)),
        ]))

        v.addWidget(self._group("Two-sided sandwich", [
            ("two_sided_mode", self._combo("two_sided_mode", SandwichMode)),
            ("top_hold_height", self._dspin_opt("top_hold_height", 0, 80, 1)),
            ("grip_gap", self._dspin("grip_gap", -2, 5, 2)),
            ("pin_style", self._combo("pin_style", PinStyle)),
            ("pin_count", self._ispin("pin_count", 0, 4)),
            ("pin_diameter", self._dspin("pin_diameter", 0, 20, 1)),
            ("pin_depth", self._dspin("pin_depth", 0, 20, 1)),
            ("stack_pins", self._check("stack_pins")),
            ("stack_pin_diameter", self._dspin("stack_pin_diameter", 0, 20, 1)),
            ("stack_pin_length", self._dspin("stack_pin_length", 1, 60, 1)),
            ("stack_pin_hole_depth", self._dspin("stack_pin_hole_depth", 0, 40, 1)),
            ("closure", self._combo("closure", Closure)),
            ("screw_dia", self._dspin("screw_dia", 0, 12, 1)),
        ]))

        v.addWidget(self._group("Labels", [
            ("label_mode", self._combo("label_mode", LabelMode)),
            ("label_place", self._combo("label_place", LabelPlace)),
            ("label_text", self._line("label_text", "blank = part name")),
            ("pocket_index_start", self._ispin("pocket_index_start", 0, 9999)),
        ]))

        # hide dependent rows when master off
        scr = Closure.SCREW.value
        clam = SandwichMode.CLAMSHELL.value
        stack = SandwichMode.STACKING.value
        grid = BaseProfile.GRIDFINITY.value
        hexs = SkeletonStyle.HONEYCOMB.value
        ribbed = SkeletonStyle.RIBBED.value
        lighten = {SkeletonStyle.POCKETED.value, hexs, ribbed}
        self._vis_rules = [
            ("rows", lambda p: not p.fit_to_bed),
            ("cols", lambda p: not p.fit_to_bed),
            ("margin_x",     lambda p: p.margin_advanced),
            ("margin_y",     lambda p: p.margin_advanced),
            ("margin_front", lambda p: p.margin_advanced),
            ("internal_wall_floor",
             lambda p: p.remove_internal_features or p.min_internal_feature > 0),
            ("cell_shape",         lambda p: p.skeleton_style == hexs),
            ("honeycomb_cell",     lambda p: p.skeleton_style == hexs),
            ("honeycomb_wall",     lambda p: p.skeleton_style == hexs),
            ("rib_width",          lambda p: p.skeleton_style == ribbed),
            ("rib_spacing",        lambda p: p.skeleton_style == ribbed),
            ("rib_pattern",        lambda p: p.skeleton_style == ribbed),
            ("lightening_through", lambda p: p.skeleton_style in lighten),
            ("outside_lightening", lambda p: p.skeleton_style in lighten),
            ("outside_wall",    lambda p: p.outside_lightening
                                and p.skeleton_style in lighten),
            ("outside_rim",     lambda p: p.outside_lightening
                                and p.skeleton_style in lighten),
            ("magnet_holes", lambda p: p.base_profile == grid),
            ("magnet_dia",   lambda p: p.base_profile == grid and p.magnet_holes),
            ("divot_count",    lambda p: p.finger_divot),
            ("divot_shape",    lambda p: p.finger_divot),
            ("divot_diameter", lambda p: p.finger_divot),
            ("divot_depth",    lambda p: p.finger_divot),
            ("divot_chamfer",  lambda p: p.finger_divot),
            ("divot_axis",     lambda p: p.finger_divot),
            ("divot_side",     lambda p: p.finger_divot and p.divot_count == 1),
            ("divot_offset",   lambda p: p.finger_divot),
            ("divot_strategy", lambda p: p.finger_divot),
            ("push_min_size",  lambda p: p.push_hole),
            ("two_sided_mode", lambda p: p.two_sided),
            ("top_hold_height", lambda p: p.two_sided),
            ("grip_gap",     lambda p: p.two_sided),
            ("pin_style",    lambda p: p.two_sided and p.two_sided_mode == clam),
            ("pin_count",    lambda p: p.two_sided),
            ("pin_diameter", lambda p: p.two_sided and p.two_sided_mode == clam),
            ("pin_depth",    lambda p: p.two_sided and p.two_sided_mode == clam),
            ("stack_pins",   lambda p: p.two_sided and p.two_sided_mode == stack),
            ("stack_pin_diameter",
             lambda p: p.two_sided and p.two_sided_mode == stack and p.stack_pins),
            ("stack_pin_length",
             lambda p: p.two_sided and p.two_sided_mode == stack and p.stack_pins),
            ("stack_pin_hole_depth",
             lambda p: p.two_sided and p.two_sided_mode == stack and p.stack_pins),
            ("closure",      lambda p: p.two_sided),
            ("screw_dia",    lambda p: p.two_sided and p.closure == scr),
            ("label_place",  lambda p: p.label_mode != LabelMode.NONE.value),
            ("label_text",   lambda p: p.label_mode != LabelMode.NONE.value),
            ("pocket_index_start", lambda p: p.pocket_index),
        ]
        self._apply_visibility()

        v.addStretch(1)
        self.readout = QLabel("No part loaded.")
        self.readout.setWordWrap(True)
        self.readout.setStyleSheet(
            "color:%s; font-size:8pt; padding:4px;" % OFFICE["muted"])
        v.addWidget(self.readout)

        scroll.setWidget(body)
        dock.setWidget(scroll)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        dock.setMinimumWidth(300)


    def _apply_visibility(self):
        # show/hide dependent rows
        for name, pred in self._vis_rules:
            row = self._rows.get(name)
            if row is None:
                continue
            lbl, w = row
            on = bool(pred(self.params))
            lbl.setVisible(on)
            w.setVisible(on)

    # special-case labels; rest prettified generically
    _PARAM_LABELS = {
        "min_internal_feature": "Min feature",
        "stack_pin_hole_depth": "Pin hole depth",
        "stack_pin_clearance": "Pin clearance",
        "stack_pin_diameter": "Pin diameter",
        "stack_pin_length": "Pin length",
    }

    @classmethod
    def _param_label(cls, name):
        # human label for param key
        return cls._PARAM_LABELS.get(name, name.replace("_", " ").capitalize())

    # tooltip per param row, mm where relevant
    _PARAM_HELP = {
        "bottom_margin": "Flat margin below the part's lowest captured point.",
        "part_clearance": "Extra gap between part and cavity walls for easy fit.",
        "mouth_chamfer": "Chamfer on the cavity mouth to guide insertion.",
        "resolution": "Heightmap capture detail; finer is slower, more accurate.",
        "min_internal_feature": "Recesses narrower than this are filled; 0 keeps all.",
        "remove_internal_features": "Fill internal pockets so only the outer profile is cradled.",
        "internal_wall_floor": "Floor left under removed internal recesses.",
        "rows": "Number of cavity rows.",
        "cols": "Number of cavity columns.",
        "part_spacing": "Gap between adjacent cavities.",
        "part_spacing_x": "Per-axis X gap; blank uses Part spacing.",
        "part_spacing_y": "Per-axis Y gap; blank uses Part spacing. Negative nests parts.",
        "pack_mode": "How cavity footprints pack (bounding box vs hull).",
        "row_stagger": "Offset alternate rows by this fraction (0-1) of pitch.",
        "border": "Tray border around the outermost cavities.",
        "margin_advanced": "Use per-side margins instead of one uniform border.",
        "margin_x": "Left/right margin; blank uses Border.",
        "margin_y": "Back (+Y) margin; blank uses Border.",
        "margin_front": "Front (-Y) margin, the label/divot face; blank uses Border.",
        "skeleton_style": "Infill style for the lightened web.",
        "cell_shape": "Honeycomb cell shape.",
        "honeycomb_cell": "Honeycomb cell size.",
        "honeycomb_wall": "Honeycomb wall thickness.",
        "rib_width": "Rib thickness for the ribbed lattice.",
        "rib_spacing": "Spacing between ribs.",
        "rib_pattern": "Rib lattice direction.",
        "lightening_through": "Cut lightening holes all the way through the base.",
        "outside_lightening": "Also lighten the web outside cavities, not just between.",
        "outside_wall": "Solid wall kept around the tray's outer edge.",
        "outside_rim": "Solid rim kept around each cavity in the outside web.",
        "base_profile": "Base style (plain or Gridfinity-compatible feet).",
        "rim_width": "Solid rim around each cavity.",
        "wall_thickness": "Minimum wall between adjacent cavities.",
        "corner_fillet": "Rounding radius on the tray's outer corners.",
        "edge_chamfer": "Chamfer on the tray's top edges.",
        "magnet_dia": "Magnet hole diameter when magnet holes are on.",
        "divot_count": "Finger divots per cavity (0 disables).",
        "divot_shape": "Finger-divot cutter shape.",
        "divot_diameter": "Finger-divot diameter.",
        "divot_depth": "Finger-divot depth.",
        "divot_chamfer": "Chamfer on the divot mouth.",
        "divot_axis": "Axis the divots are placed along.",
        "divot_side": "Which side(s) of the cavity get divots.",
        "divot_offset": "Shift divots along their axis from centre.",
        "divot_strategy": "Which cavities get divots (all, perimeter, shared web).",
        "push_min_size": "Add push-out holes only when the cavity is at least this wide.",
        "two_sided_mode": "Sandwich type for two-sided trays.",
        "top_hold_height": "Cradle depth of the top half; blank mirrors the bottom.",
        "grip_gap": "Gap between the two halves where they meet.",
        "pin_style": "Alignment pin style (taper or straight).",
        "pin_count": "Alignment pins between the two halves.",
        "pin_diameter": "Alignment pin diameter.",
        "pin_depth": "Alignment pin length.",
        "stack_pins": "Add pins so finished trays stack on each other.",
        "stack_pin_diameter": "Stacking pin diameter.",
        "stack_pin_length": "Stacking pin length.",
        "stack_pin_hole_depth": "Stacking pin socket depth.",
        "closure": "How the two halves are held shut (none or screws).",
        "screw_dia": "Closure screw diameter.",
        "label_mode": "Label style (none, debossed, embossed).",
        "label_place": "Where the label goes (top or front face).",
        "label_text": "Label text; blank uses the part name.",
        "pocket_index_start": "Starting number for per-pocket index labels.",
        "drawer_pack_gap": "Gap between different parts packed in one drawer.",
        "bed_split": "Split oversized output into bed-sized tiles for printing.",
    }

    # group + bound-widget factories
    def _group(self, title, rows):
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setContentsMargins(8, 6, 8, 6)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)
        for name, w in rows:
            lbl = QLabel(self._param_label(name))
            tip = self._PARAM_HELP.get(name)
            if tip:
                lbl.setToolTip(tip)
                w.setToolTip(tip)
            form.addRow(lbl, w)
            self._rows[name] = (lbl, w)
        return box

    def _dspin(self, name, lo, hi, dec, slot=None):
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setDecimals(dec)
        w.setSingleStep(10 ** -dec if dec else 1)
        w.setValue(float(getattr(self.params, name)))
        w.valueChanged.connect(slot or (lambda v, n=name: self._set(n, float(v))))
        self._widgets[name] = w
        return w

    def _dspin_opt(self, name, lo, hi, dec, auto=None):
        # optional float spin, auto=None; sentinel below lo keeps real lo selectable
        sentinel = lo if auto is None else auto
        w = QDoubleSpinBox()
        w.setRange(sentinel, hi)
        w.setDecimals(dec)
        w.setSingleStep(10 ** -dec if dec else 1)
        w.setSpecialValueText("auto")
        val = getattr(self.params, name)
        w.setValue(sentinel if val is None else float(val))
        w.valueChanged.connect(
            lambda v, n=name, m=sentinel: self._set(n, None if v <= m else float(v)))
        self._widgets[name] = w
        return w

    def _ispin(self, name, lo, hi):
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setValue(int(getattr(self.params, name)))
        w.valueChanged.connect(lambda v, n=name: self._set(n, int(v)))
        self._widgets[name] = w
        return w

    def _check(self, name):
        w = QCheckBox()
        w.setChecked(bool(getattr(self.params, name)))
        w.toggled.connect(lambda on, n=name: self._set(n, bool(on)))
        self._widgets[name] = w
        return w

    def _line(self, name, placeholder=""):
        w = QLineEdit()
        w.setText(str(getattr(self.params, name) or ""))
        if placeholder:
            w.setPlaceholderText(placeholder)
        w.textEdited.connect(lambda t, n=name: self._set(n, t))
        self._widgets[name] = w
        return w

    def _combo(self, name, enum_cls):
        w = QComboBox()
        w.addItems(_enum_values(enum_cls))
        w.setCurrentText(getattr(self.params, name))
        w.activated.connect(lambda _i, n=name, c=w: self._set(n, c.currentText()))
        self._widgets[name] = w
        return w

    # param writeback
    _SEATING_KEYS = {"seating", "seating_axis", "flip",
                     "part_lean_deg", "part_lean_axis",
                     "tray_angle_deg", "tray_angle_axis"}
    # params that change cavity ghost, trigger live refresh
    _GHOST_KEYS = {"part_clearance", "mouth_chamfer", "capture_quality",
                   "min_internal_feature", "remove_internal_features",
                   "internal_wall_floor", "two_sided", "top_hold_height",
                   "grip_gap"}

    def _top_band(self):
        # top-half cradle depth, mm
        p = self.params
        band = (float(p.top_hold_height) if p.top_hold_height is not None
                else 0.5 * float(p.hold_height))
        return max(0.5, band - float(p.grip_gap))

    def _refresh_generate_style(self):
        # tint Generate button green/amber by staleness
        btn = getattr(self, "_btn_generate", None)
        if btn is None:
            return
        stale = bool(getattr(self, "_result_dirty", False))
        bg, hov, prs, bd = (("#e0892b", "#ed9a3e", "#c9781f", "#a85f12") if stale
                            else ("#1e8e3e", "#27a24a", "#176b2e", "#11652a"))
        btn.setStyleSheet(
            "QToolButton{background:%s; color:#ffffff; font-weight:bold;"
            " border:1px solid %s; border-radius:4px; padding:3px 8px;}"
            "QToolButton:hover{background:%s;}"
            "QToolButton:pressed{background:%s;}"
            "QToolButton:disabled{background:#9bc6a6; color:#eef3ee;"
            " border:1px solid #7da888;}" % (bg, bd, hov, prs))
        btn.setToolTip("Generate tray - params changed, rebuild due" if stale
                       else "Generate tray - up to date")

    def _set(self, name, value):
        try:
            setattr(self.params, name, value)
        except Exception as e:
            self.statusBar().showMessage("Invalid %s: %s" % (name, e))
            return
        if name not in ("export_format", "tess_linear", "tess_angular",
                        "name_pattern"):
            self._result_dirty = True
            self._refresh_generate_style()
            self._invalidate_spec()
        self.statusBar().showMessage("%s = %s" % (name, value))
        # new seating plane invalidates lean, reset to 0
        if name in ("seating", "seating_axis") and (
                float(self.params.part_lean_deg)
                or float(self.params.tray_angle_deg)):
            self._reset_tilt()
        self._apply_visibility()
        if name in self._SEATING_KEYS:
            self._refresh_part_view()
            # seating reseats cradle depth, tilt must not
            if (name in ("seating", "seating_axis", "flip")
                    and self.bridge.part is not None):
                self._default_hold_height(self.bridge.part, toast=True)
        elif name == "hold_height":
            self.viewer_part.set_hold(self.params.hold_height)
        self._refresh_part_panel()             # sync overlay
        fb = getattr(self, "_feature_btns", {}).get(name)
        if fb is not None and fb.isChecked() != bool(value):
            fb.blockSignals(True)
            fb.setChecked(bool(value))
            fb.blockSignals(False)
        if name in ("pocket_rotate", "pocket_rotate_deg"):
            # spin part body + cavity ghost live
            self.viewer_part.set_part_tilt(self._part_view_matrix())
            self._refresh_ghost_all_if_on()
        if (name in self._GHOST_KEYS and self._ghost_active
                and self.bridge.step_path
                and self.cfg.get("live_preview", True)):
            self._auto_timer.start(self._AUTO_MS)
        self._refresh_drawer_summary()

