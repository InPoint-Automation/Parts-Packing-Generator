# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Top ribbon + feature-toggle row

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolBar, QComboBox, QCheckBox

from ..project import Project
from ..params import Axis, ExportFormat
from .icons import icon_button
from .widgets import rib_group, field
from .theme import STEP_TINTS
from .mw_common import _enum_values


class RibbonMixin:
    def _build_ribbon(self):
        tb = QToolBar("ribbon")
        tb.setObjectName("ribbon")
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)

        STEP_FILE, STEP_ORIENT, STEP_BUILD, STEP_PROJECT = 1, 2, 3, 4

        tb.addWidget(rib_group("File", [
            icon_button("load_step", self.load_step, "Load STEP part", "Load"),
            icon_button("open_preset", self.open_preset, "Open preset JSON",
                        "Preset"),
            icon_button("preset", self.save_preset, "Save preset JSON", "Save"),
            icon_button("settings", self.settings, "Settings", "Setup"),
            icon_button("help", self.about, "About", "About")],
            step=STEP_FILE, tint=STEP_TINTS[0]))
        tb.addSeparator()

        self.cb_axis = QComboBox()
        self.cb_axis.addItems(_enum_values(Axis))
        self.cb_axis.setCurrentText(self.params.seating_axis)
        self.cb_axis.activated.connect(
            lambda _i: self._set("seating_axis", self.cb_axis.currentText()))
        self.btn_flip = icon_button("flip", self._toggle_flip, "Invert down",
                                    "Flip", toggle=True)
        self._btn_ghost = icon_button(
            "capture", self.toggle_ghost,
            "Cavity ghost - overlay the pocket on the part to see hug vs gap "
            "(live, coarse)", "Ghost", toggle=True)
        self._btn_ghost.setChecked(True)
        self.btn_section = icon_button(
            "section", self.toggle_section,
            "Cutaway - clip the part body at the section plane to see the "
            "cross-section (the draggable plane is always shown)", "Cutaway",
            toggle=True)
        # part-action buttons
        self._part_btns = {}
        for key, icon, tip in (
                ("ghost_height", "band", "Cradle depth - set how deep parts sit"),
                ("rotate_parts", "rotate", "Spin + lean the parts"),
                ("rotate_tray", "tilt", "Angle the pocket for oblique insertion"),
                ("change_axis", "orient", "Pick the down axis / flip the part")):
            label = self._PART_ACTIONS[key][0]
            self._part_btns[key] = icon_button(
                icon, lambda _c=False, k=key: self._toggle_part_action(k),
                tip, label, toggle=True)
        self._btn_reset_rot = icon_button(
            "undo", self._reset_rotations,
            "Reset all rotations (spin, lean, tray angle) to 0", "Reset rot")
        tb.addWidget(rib_group("Orientation", [
            self._btn_ghost, self.btn_section,
            *self._part_btns.values(), self._btn_reset_rot],
            step=STEP_ORIENT, tint=STEP_TINTS[1]))
        tb.addSeparator()

        self.cb_export = QComboBox()
        self.cb_export.addItems(_enum_values(ExportFormat))
        self.cb_export.setCurrentText(self.params.export_format)
        self.cb_export.activated.connect(
            lambda _i: self._set("export_format", self.cb_export.currentText()))
        self._btn_generate = icon_button("generate", self.generate,
                                         "Generate tray (full res)", "Generate",
                                         color="#ffffff")
        self._btn_generate.setObjectName("generate_btn")
        self._btn_generate.setAutoRaise(False)
        self._refresh_generate_style()
        self._btn_export = icon_button("export", self.export,
                                       "Export tray", "Export")
        tb.addWidget(rib_group("Build", [
            self._btn_generate, self._btn_export,
            field("format", self.cb_export)],
            step=STEP_BUILD, tint=STEP_TINTS[2]))
        tb.addSeparator()

        self._btn_drawer = icon_button("drawer", self.generate_drawer,
                                       "Generate one packed drawer (all parts "
                                       "in a single base)", "Drawer")
        self._btn_batch = icon_button("generate", self.generate_batch,
                                      "Generate every project part as its own "
                                      "tray (batch)", "Batch")
        tb.addWidget(rib_group("Project", [
            icon_button("library", self.project_new, "New empty project",
                        "New"),
            icon_button("open_preset", self.project_open, "Open a .ppproj",
                        "Open"),
            icon_button("save", self.project_save, "Save the project", "Save"),
            icon_button("addpart", self.project_add_current,
                        "Add the loaded part + current params to the project",
                        "Add part"),
            self._btn_drawer, self._btn_batch],
            step=STEP_PROJECT, tint=STEP_TINTS[2]))
        tb.addSeparator()

        self._view_btns["part"] = icon_button(
            "view_part", lambda: self._apply_view_mode("part"),
            "Show the part + reference planes", "Part", toggle=True)
        self._view_btns["tray"] = icon_button(
            "view_tray", lambda: self._apply_view_mode("tray"),
            "Show the generated tray", "Tray", toggle=True)
        self._view_btns["split"] = icon_button(
            "view_split", lambda: self._apply_view_mode("split"),
            "Show part and tray side by side", "Split", toggle=True)
        tb.addWidget(rib_group("View layout", list(self._view_btns.values()),
                               step=None, tint=None))
        tb.addSeparator()

        tb.addWidget(rib_group("Camera", [
            icon_button("fit", self.fit, "Fit  Home", "Fit"),
            icon_button("zoom_in", lambda: self._zoom(1.25), "Zoom +", "In"),
            icon_button("zoom_out", lambda: self._zoom(0.8), "Zoom -", "Out"),
            icon_button("rotate", self._reset_view, "Reset view", "Reset")],
            step=None, tint=None))

        self._build_feature_row()

    # second ribbon row: on/off feature toggles
    _FEATURE_TOGGLES = [
        ("two_sided", "sandwich", "2-sided", "Two-sided sandwich tray"),
        ("finger_divot", "relief", "Divots", "Finger divots"),
        ("pocket_rotate", "rotate", "Rotate", "Rotate parts in their pockets"),
        ("push_hole", "band", "Push", "Push-out holes under pockets"),
        ("vent_holes", "grid", "Vents", "Vent holes in the base"),
        ("magnet_holes", "base", "Magnets", "Magnet holes (gridfinity base)"),
        ("stacking_feet", "up", "Feet", "Stacking feet"),
        ("pocket_index", "panel", "Index", "Pocket index numbers"),
        ("fit_to_bed", "fit", "Fit bed", "Auto-fit the grid to the bed"),
        ("bed_split", "section", "Split", "Split the tray into bed-sized tiles"),
    ]

    def _build_feature_row(self):
        self.addToolBarBreak(Qt.TopToolBarArea)
        tb = QToolBar("ribbon_features")
        tb.setObjectName("ribbon_features")
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)
        self._feature_btns = {}
        btns = []
        for name, icon, label, tip in self._FEATURE_TOGGLES:
            b = icon_button(icon, lambda n=name: self._toggle_feature(n),
                            tip, label, toggle=True)
            b.setChecked(bool(getattr(self.params, name)))
            self._feature_btns[name] = b
            btns.append(b)
        tb.addWidget(rib_group("Features (click to enable / disable)", btns,
                               step=None, tint=None))

    def _toggle_feature(self, name):
        on = self._feature_btns[name].isChecked()
        self._set(name, on)
        w = self._widgets.get(name)
        if isinstance(w, QCheckBox):
            w.blockSignals(True)
            w.setChecked(on)
            w.blockSignals(False)

