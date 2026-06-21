# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Main window: ribbon + viewport + param dock + status bar.

from __future__ import annotations

import os

from PySide6.QtCore import (Qt, QThread, Signal, QTimer,
                            QPropertyAnimation)
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QToolButton, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGroupBox, QLabel, QComboBox, QCheckBox, QDoubleSpinBox,
    QSpinBox, QScrollArea, QDockWidget, QFileDialog, QMessageBox, QDialog,
    QProgressBar, QPushButton, QDialogButtonBox, QLineEdit, QListWidget,
    QListWidgetItem, QGraphicsOpacityEffect, QSlider)

from .. import APP_NAME, __version__
from ..config import load_cfg, save_cfg
from ..project import Project
from ..params import (Params, Axis, CaptureQuality,
                      SkeletonStyle, BaseProfile, RibPattern, CellShape,
                      DivotShape, DivotStrategy, DivotAxis, DivotSide, PinStyle,
                      Closure, ExportFormat, LabelMode, LabelPlace, PocketRotate)
from .icons import icon_button, make_icon
from .widgets import rib_group, field
from .theme import OFFICE, STEP_TINTS
from .viewer import Viewer
from .bridge import Bridge


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


class _BuildThread(QThread):
    """Run pipeline.build off UI thread."""
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(float, str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            result = self._fn(lambda f, m: self.progress.emit(f, m))
        except NotImplementedError as e:
            self.failed.emit("not implemented: %s" % e)
        except Exception as e:
            self.failed.emit(str(e))
        else:
            self.done.emit(result)


class BuildProgressDialog(QDialog):
    """Modeless build-progress popup."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.setMinimumWidth(360)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)
        self._heading = QLabel("%s: starting…" % title)
        self._heading.setStyleSheet("font-weight:600;")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._stage = QLabel("Preparing…")
        self._stage.setWordWrap(True)
        self._stage.setStyleSheet("color:%s; font-size:8pt;" % OFFICE["muted"])
        v.addWidget(self._heading)
        v.addWidget(self._bar)
        v.addWidget(self._stage)

    def update_progress(self, frac, message):
        self._bar.setValue(int(round(frac * 100)))
        self._stage.setText(message)

    def closeEvent(self, event):
        if getattr(self, "_allow_close", False):
            event.accept()
        else:
            event.ignore()

    def finish(self):
        self._allow_close = True
        self.close()


def _contrast_text(hexcol):
    """Readable text color for background."""
    from PySide6.QtGui import QColor
    c = QColor(hexcol)
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return "#000000" if lum > 140 else "#ffffff"


class SettingsDialog(QDialog):
    """App preferences dialog."""

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(340)
        self._accent = cfg.get("icon_color") or "#1F3864"

        form = QFormLayout(self)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        self._accent_btn = QPushButton()
        self._accent_btn.setFixedWidth(130)
        self._accent_btn.clicked.connect(self._pick_accent)
        self._paint_accent()
        form.addRow(QLabel("Icon accent"), self._accent_btn)

        self._scale = QDoubleSpinBox()
        self._scale.setRange(0.0, 3.0)
        self._scale.setDecimals(2)
        self._scale.setSingleStep(0.05)
        self._scale.setSpecialValueText("Auto")
        self._scale.setValue(float(cfg.get("ui_scale") or 0))
        form.addRow(QLabel("UI scale"), self._scale)

        self._bed_x = self._mm_spin(cfg.get("bed_x") or 256.0)
        self._bed_y = self._mm_spin(cfg.get("bed_y") or 256.0)
        form.addRow(QLabel("Bed X"), self._bed_x)
        form.addRow(QLabel("Bed Y"), self._bed_y)

        self._gizmo = QCheckBox()
        self._gizmo.setChecked(bool(cfg.get("show_gizmo", True)))
        form.addRow(QLabel("Show gizmo"), self._gizmo)
        self._decimate = QCheckBox()
        self._decimate.setChecked(bool(cfg.get("decimate_preview", True)))
        form.addRow(QLabel("Decimate preview"), self._decimate)
        self._live = QCheckBox()
        self._live.setChecked(bool(cfg.get("live_preview", True)))
        self._live.setToolTip("Auto-refresh the cavity ghost when a parameter "
                              "changes.")
        form.addRow(QLabel("Live preview"), self._live)

        note = QLabel("UI scale applies on next launch.")
        note.setStyleSheet("color:%s; font-size:8pt;" % OFFICE["muted"])
        form.addRow(note)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    @staticmethod
    def _mm_spin(value):
        w = QDoubleSpinBox()
        w.setRange(20, 2000)
        w.setDecimals(0)
        w.setSuffix(" mm")
        w.setValue(float(value))
        return w

    def _paint_accent(self):
        self._accent_btn.setText(self._accent)
        self._accent_btn.setStyleSheet(
            "QPushButton { background:%s; color:%s; border:1px solid %s;"
            " font-weight:bold; }"
            % (self._accent, _contrast_text(self._accent), OFFICE["border"]))

    def _pick_accent(self):
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        col = QColorDialog.getColor(QColor(self._accent), self, "Icon accent")
        if col.isValid():
            self._accent = col.name()
            self._paint_accent()

    def values(self):
        scale = float(self._scale.value())
        return {
            "icon_color": self._accent,
            "ui_scale": scale if scale > 0 else 0,
            "bed_x": float(self._bed_x.value()),
            "bed_y": float(self._bed_y.value()),
            "show_gizmo": bool(self._gizmo.isChecked()),
            "decimate_preview": bool(self._decimate.isChecked()),
            "live_preview": bool(self._live.isChecked()),
        }


class MainWindow(QMainWindow):
    def __init__(self, cfg=None):
        super().__init__()
        self.cfg = cfg or load_cfg()
        self.params = Params()
        self.project = Project()
        self.project_path = None
        self.bridge = Bridge()
        self._widgets = {}
        self._rows = {}
        self._vis_rules = []
        self._build_thread = None
        self._progress_dialog = None
        self._ghost_active = False
        self._ghost_built = False
        self._rebuild_dirty = False
        self._result_dirty = False
        self._AUTO_MS = 150
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self._auto_rebuild)
        self._TILT_MS = 500
        self._pending_tilt = None
        self._tilt_timer = QTimer(self)
        self._tilt_timer.setSingleShot(True)
        self._tilt_timer.timeout.connect(self._commit_tilt)

        self.setWindowTitle("%s  v%s" % (APP_NAME, __version__))
        self.resize(1320, 840)

        self._build_central()
        self._build_ribbon()
        self._build_param_panel()
        self._build_project_panel()
        # Defer view hide until shown: pre-show hide -> VTK BadWindow.
        QTimer.singleShot(0, lambda: self._apply_view_mode("split"))
        self.statusBar().showMessage("Load a STEP part to begin.")

    # ---- Central: Part | Tray split/tab view ----
    def _build_central(self):
        from PySide6.QtWidgets import QSplitter
        self.viewer_part = Viewer(self)
        self.viewer_tray = Viewer(self)
        self.viewer_part.set_section_callback(self._on_section_drag)
        self.viewer_part.enable_tilt_gizmo3d(self._on_tilt_gizmo)
        self.viewer_part.set_tilt_gizmo3d(self.params.tilt_axis,
                                          self.params.tilt_deg,
                                          str(self.params.tilt_mode))
        self.viewer_part.show_tilt_gizmo3d(False)
        self._hold_slider = QSlider(Qt.Vertical)
        self._hold_slider.setRange(10, 800)        # value = mm*10
        self._hold_slider.setEnabled(False)
        self._hold_slider.setToolTip("Cradle depth (hold_height) - drag to set")
        self._hold_slider.valueChanged.connect(self._on_hold_slider)
        part_box = QWidget()
        ph = QHBoxLayout(part_box)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.setSpacing(2)
        ph.addWidget(self.viewer_part, 1)
        ph.addWidget(self._hold_slider)
        self._part_box = part_box
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

    # ---- Ribbon ----
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
        sp_tilt = self._dspin("tilt_deg", -45, 45, 0,
                              slot=lambda v: self._tilt_typed(v))
        cmb_taxis = QComboBox()
        cmb_taxis.addItems(["X", "Y"])
        _ta = str(self.params.tilt_axis)
        cmb_taxis.setCurrentText(_ta if _ta in ("X", "Y") else "X")
        cmb_taxis.setToolTip("Lean the part against the tray plane about its "
                             "in-plane X or Y axis.")
        cmb_taxis.activated.connect(
            lambda _i, c=cmb_taxis: self._set("tilt_axis", c.currentText()))
        self._widgets["tilt_axis"] = cmb_taxis
        # Enum values stay A/B for preset back-compat; synced by hand.
        cmb_tmode = QComboBox()
        cmb_tmode.addItem("rotate part", "A")
        cmb_tmode.addItem("rotate tray", "B")
        cmb_tmode.setCurrentIndex(0 if str(self.params.tilt_mode) == "A" else 1)
        cmb_tmode.setToolTip(
            "Rotate part: lean the part inside an upright pocket, lift straight "
            "up.\nRotate tray: angle the pocket so the part slides in at an angle.")
        cmb_tmode.activated.connect(
            lambda _i, c=cmb_tmode: self._set("tilt_mode", c.currentData()))
        self.cb_tmode = cmb_tmode
        tb.addWidget(rib_group("Orientation", [
            field("down axis", self.cb_axis),
            self.btn_flip,
            self._btn_ghost, self.btn_section,
            field("tilt°", sp_tilt),
            field("tilt axis", cmb_taxis),
            field("insertion", cmb_tmode)],
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

    # ---- Parameter panel (right dock) ----
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
            ("hold_height", self._dspin("hold_height", 1, 80, 1)),
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
            ("row_stagger", self._dspin("row_stagger", 0, 1, 2)),
            ("pocket_rotate", self._check("pocket_rotate")),
            ("pocket_rotate_deg", self._dspin("pocket_rotate_deg", 0, 360, 0)),
            ("pocket_rotate_pattern",
             self._combo("pocket_rotate_pattern", PocketRotate)),
            ("border", self._dspin("border", 0, 40, 1)),
            ("fit_to_bed", self._check("fit_to_bed")),
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
            ("magnet_holes", self._check("magnet_holes")),
            ("magnet_dia", self._dspin("magnet_dia", 0, 12, 1)),
            ("vent_holes", self._check("vent_holes")),
            ("bed_split", self._check("bed_split")),
        ]))

        v.addWidget(self._group("Finger access", [
            ("finger_divot", self._check("finger_divot")),
            ("divot_count", self._ispin("divot_count", 0, 2)),
            ("divot_shape", self._combo("divot_shape", DivotShape)),
            ("divot_diameter", self._dspin("divot_diameter", 0, 40, 1)),
            ("divot_depth", self._dspin("divot_depth", 0, 40, 1)),
            ("divot_chamfer", self._dspin("divot_chamfer", 0, 10, 1)),
            ("divot_axis", self._combo("divot_axis", DivotAxis)),
            ("divot_side", self._combo("divot_side", DivotSide)),
            ("divot_offset", self._dspin("divot_offset", -50, 50, 1)),
            ("divot_strategy", self._combo("divot_strategy", DivotStrategy)),
            ("push_hole", self._check("push_hole")),
            ("push_min_size", self._dspin("push_min_size", 0, 200, 1)),
        ]))

        v.addWidget(self._group("Two-sided sandwich", [
            ("two_sided", self._check("two_sided")),
            ("grip_gap", self._dspin("grip_gap", -2, 5, 2)),
            ("pin_style", self._combo("pin_style", PinStyle)),
            ("pin_count", self._ispin("pin_count", 0, 4)),
            ("pin_diameter", self._dspin("pin_diameter", 0, 20, 1)),
            ("pin_depth", self._dspin("pin_depth", 0, 20, 1)),
            ("closure", self._combo("closure", Closure)),
            ("screw_dia", self._dspin("screw_dia", 0, 12, 1)),
        ]))

        v.addWidget(self._group("Labels", [
            ("label_mode", self._combo("label_mode", LabelMode)),
            ("label_place", self._combo("label_place", LabelPlace)),
            ("label_text", self._line("label_text", "blank = part name")),
            ("pocket_index", self._check("pocket_index")),
            ("pocket_index_start", self._ispin("pocket_index_start", 0, 9999)),
        ]))

        # Hide dependent rows whose master option is off.
        scr = Closure.SCREW.value
        grid = BaseProfile.GRIDFINITY.value
        hexs = SkeletonStyle.HONEYCOMB.value
        ribbed = SkeletonStyle.RIBBED.value
        lighten = {SkeletonStyle.POCKETED.value, hexs, ribbed}
        self._vis_rules = [
            ("rows", lambda p: not p.fit_to_bed),
            ("cols", lambda p: not p.fit_to_bed),
            ("internal_wall_floor",
             lambda p: p.remove_internal_features or p.min_internal_feature > 0),
            ("pocket_rotate_deg", lambda p: p.pocket_rotate),
            ("pocket_rotate_pattern", lambda p: p.pocket_rotate),
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
            ("grip_gap",     lambda p: p.two_sided),
            ("pin_style",    lambda p: p.two_sided),
            ("pin_count",    lambda p: p.two_sided),
            ("pin_diameter", lambda p: p.two_sided),
            ("pin_depth",    lambda p: p.two_sided),
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

    # ---- Project / part-library panel ----
    def _build_project_panel(self):
        dock = QDockWidget("Project", self)
        dock.setObjectName("project_dock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        self._proj_name = QLineEdit(self.project.name)
        self._proj_name.setPlaceholderText("drawer name")
        self._proj_name.textEdited.connect(
            lambda t: setattr(self.project, "name", t))
        v.addWidget(QLabel("Drawer name"))
        v.addWidget(self._proj_name)

        self._proj_list = QListWidget()
        self._proj_list.itemDoubleClicked.connect(self._project_load_selected)
        self._proj_list.currentRowChanged.connect(self._project_row_changed)
        v.addWidget(self._proj_list, 1)

        cnt_row = QHBoxLayout()
        cnt_row.addWidget(QLabel("Copies"))
        self._proj_count = QSpinBox()
        self._proj_count.setRange(1, 999)
        self._proj_count.setEnabled(False)
        self._proj_count.valueChanged.connect(self._project_count_changed)
        cnt_row.addWidget(self._proj_count)
        cnt_row.addStretch(1)
        v.addLayout(cnt_row)

        btns = QHBoxLayout()
        add = QPushButton("Add current")
        add.setToolTip("Add the loaded part + current params as an entry")
        add.clicked.connect(self.project_add_current)
        rem = QPushButton("Remove")
        rem.clicked.connect(self._project_remove_selected)
        load = QPushButton("Load")
        load.setToolTip("Load the selected entry's part + params into the editor")
        load.clicked.connect(self._project_load_selected)
        for b in (add, load, rem):
            btns.addWidget(b)
        v.addLayout(btns)

        self._proj_note = QLabel(
            "Double-click an entry to load it. Drawer packs all parts into one "
            "base (using the current panel's base/skeleton/border/bed); Batch "
            "makes one tray per part.")
        self._proj_note.setWordWrap(True)
        self._proj_note.setStyleSheet(
            "color:%s; font-size:8pt;" % OFFICE["muted"])
        v.addWidget(self._proj_note)

        dock.setWidget(body)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setMinimumWidth(240)
        self._refresh_project_list()

    def _refresh_project_list(self):
        """Repaint entry list + name."""
        self._proj_list.blockSignals(True)
        self._proj_list.clear()
        for e in self.project.entries:
            QListWidgetItem("%s  ×%d" % (e.name(), e.count), self._proj_list)
        self._proj_list.blockSignals(False)
        self._proj_name.blockSignals(True)
        self._proj_name.setText(self.project.name)
        self._proj_name.blockSignals(False)
        self._project_row_changed(self._proj_list.currentRow())

    def _project_row_changed(self, row):
        ok = 0 <= row < len(self.project.entries)
        self._proj_count.blockSignals(True)
        self._proj_count.setEnabled(ok)
        if ok:
            self._proj_count.setValue(int(self.project.entries[row].count))
        self._proj_count.blockSignals(False)

    def _project_count_changed(self, val):
        row = self._proj_list.currentRow()
        if 0 <= row < len(self.project.entries):
            self.project.entries[row].count = int(val)
            it = self._proj_list.item(row)
            e = self.project.entries[row]
            if it is not None:
                it.setText("%s  ×%d" % (e.name(), e.count))

    def project_add_current(self):
        if not self.bridge.step_path:
            self.statusBar().showMessage("Load a STEP part first.")
            return
        self.project.add(self.bridge.step_path, self.params,
                         count=1)
        self._refresh_project_list()
        self._proj_list.setCurrentRow(len(self.project.entries) - 1)
        self.statusBar().showMessage(
            "Added %s to the project (%d part%s)."
            % (self.project.entries[-1].name(), len(self.project.entries),
               "" if len(self.project.entries) == 1 else "s"))

    def _project_remove_selected(self):
        row = self._proj_list.currentRow()
        if not (0 <= row < len(self.project.entries)):
            return
        name = self.project.entries[row].name()
        self.project.remove(row)
        self._refresh_project_list()
        self.statusBar().showMessage("Removed %s from the project." % name)

    def _project_load_selected(self, *_):
        """Load selected entry into editor."""
        row = self._proj_list.currentRow()
        if not (0 <= row < len(self.project.entries)):
            return
        entry = self.project.entries[row]
        try:
            part = self.bridge.load_part(entry.step_path)
        except Exception as e:
            QMessageBox.warning(self, "Load", "Could not load %s:\n%s"
                                % (entry.step_path, e))
            return
        self._ghost_active = False
        self._ghost_built = False
        self.params = entry.params.model_copy(deep=True)
        self._sync_widgets()
        self.viewer_part.show_part(part, self._seating_dir(), color="#9fb3d1",
                                   tray_normal=self._tray_normal(),
                                   part_tilt=self._part_tilt_matrix())
        if self._view_mode == "tray":
            self._apply_view_mode("part")
        self.statusBar().showMessage("Loaded %s from the project." % entry.name())

    def project_new(self):
        if self.project.entries and QMessageBox.question(
                self, "New project",
                "Discard the current project (%d part%s)?"
                % (len(self.project.entries),
                   "" if len(self.project.entries) == 1 else "s")) \
                != QMessageBox.Yes:
            return
        self.project = Project()
        self.project_path = None
        self._refresh_project_list()
        self.statusBar().showMessage("New project.")

    def project_open(self):
        from ..project import PROJECT_EXT
        path, _ = QFileDialog.getOpenFileName(
            self, "Open project",
            self.cfg.get("last_dir") or os.path.expanduser("~"),
            "Project (*%s)" % PROJECT_EXT)
        if not path:
            return
        try:
            self.project = Project.load(path)
        except Exception as e:
            QMessageBox.warning(self, "Project", "Could not open project:\n%s" % e)
            return
        self.project_path = path
        self.cfg["last_dir"] = os.path.dirname(path)
        save_cfg(self.cfg)
        self._refresh_project_list()
        self.statusBar().showMessage("Opened project %s" % os.path.basename(path))

    def project_save(self):
        from ..project import PROJECT_EXT
        suggested = self.project_path or os.path.join(
            self.cfg.get("last_dir") or os.path.expanduser("~"),
            (self.project.name or "drawer") + PROJECT_EXT)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project", suggested, "Project (*%s)" % PROJECT_EXT)
        if not path:
            return
        try:
            self.project.save(path)
        except Exception as e:
            QMessageBox.warning(self, "Project", "Could not save project:\n%s" % e)
            return
        self.project_path = path if path.endswith(PROJECT_EXT) \
            else path + PROJECT_EXT
        self.statusBar().showMessage("Saved project %s"
                                     % os.path.basename(self.project_path))

    def _apply_visibility(self):
        """Show/hide dependent rows."""
        for name, pred in self._vis_rules:
            row = self._rows.get(name)
            if row is None:
                continue
            lbl, w = row
            on = bool(pred(self.params))
            lbl.setVisible(on)
            w.setVisible(on)

    # ---- group + bound-widget factories ---- #
    def _group(self, title, rows):
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setContentsMargins(8, 6, 8, 6)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)
        for name, w in rows:
            lbl = QLabel(name)
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

    # ---- Param writeback ----
    _SEATING_KEYS = {"seating", "seating_axis", "flip", "tilt_deg",
                     "tilt_axis", "tilt_mode"}
    # Params that change the cavity ghost (live refresh triggers).
    _GHOST_KEYS = {"part_clearance", "mouth_chamfer", "capture_quality",
                   "min_internal_feature", "remove_internal_features",
                   "internal_wall_floor"}

    def _refresh_generate_style(self):
        """Tint Generate button green/amber by staleness."""
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
        self.statusBar().showMessage("%s = %s" % (name, value))
        # New seating plane invalidates lean; reset to 0.
        if name in ("seating", "seating_axis") and float(self.params.tilt_deg):
            self._reset_tilt()
        self._apply_visibility()
        if name in self._SEATING_KEYS:
            self._refresh_part_view()
            # Seating change alters part height; reseat cradle depth. Tilt must not.
            if (name in ("seating", "seating_axis", "flip")
                    and self.bridge.part is not None):
                self._default_hold_height(self.bridge.part, toast=True)
        elif name == "hold_height":
            self.viewer_part.set_hold(self.params.hold_height)
            self._sync_hold_slider()
        if (name in self._GHOST_KEYS and self._ghost_active
                and self.bridge.step_path
                and self.cfg.get("live_preview", True)):
            self._auto_timer.start(self._AUTO_MS)

    def _toggle_flip(self):
        self._set("flip", self.btn_flip.isChecked())

    def _tilt_typed(self, v):
        """Debounce tilt edits."""
        v = float(v)
        self._pending_tilt = v
        self._tilt_timer.start(self._TILT_MS)
        self._echo_tilt(v)

    def _on_tilt_gizmo(self, deg):
        """Arc-gizmo drag -> debounced tilt commit."""
        self._tilt_typed(float(deg))

    def _echo_tilt(self, v):
        """Mirror tilt into spinbox + gizmo without re-firing."""
        w = self._widgets.get("tilt_deg")
        if w is not None and abs(float(w.value()) - v) > 1e-9:
            w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(False)
        self.viewer_part.set_tilt_gizmo3d(self.params.tilt_axis, v,
                                          str(self.params.tilt_mode))

    def _reset_tilt(self):
        """Clear lean."""
        self._pending_tilt = None
        self._tilt_timer.stop()
        self.params.tilt_deg = 0.0
        self._echo_tilt(0.0)

    def _commit_tilt(self):
        if self._pending_tilt is not None:
            v, self._pending_tilt = self._pending_tilt, None
            self._set("tilt_deg", v)

    # ---- Actions ----
    def load_step(self):
        initdir = self.cfg.get("last_dir") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Load STEP part", initdir, "STEP (*.step *.stp *.STEP *.STP)")
        if not path:
            return
        self.cfg["last_dir"] = os.path.dirname(path)
        rec = [path] + [p for p in (self.cfg.get("recent") or []) if p != path]
        self.cfg["recent"] = rec[:8]
        save_cfg(self.cfg)
        self.statusBar().showMessage("Loading %s…" % os.path.basename(path))
        try:
            part = self.bridge.load_part(path)
        except Exception as e:
            QMessageBox.warning(self, "Load", "Could not load STEP:\n%s" % e)
            return
        self._ghost_active = False
        self._ghost_built = False
        self._default_hold_height(part)
        self.setWindowTitle("%s  v%s - %s"
                            % (APP_NAME, __version__, os.path.basename(path)))
        self.viewer_part.show_part(part, self._seating_dir(), color="#9fb3d1",
                                   reset=False, tray_normal=self._tray_normal(),
                                   part_tilt=self._part_tilt_matrix())
        self.viewer_part.orient_camera(self._seating_dir(), animate=False,
                                       fit=True)
        if self._view_mode == "tray":
            self._apply_view_mode("part")
        self.viewer_part.set_tilt_gizmo3d(self.params.tilt_axis,
                                          self.params.tilt_deg,
                                          str(self.params.tilt_mode))
        self.viewer_part.show_tilt_gizmo3d(True)
        self._hold_slider.setEnabled(True)
        self._sync_hold_slider()
        self.viewer_part.set_section(self.btn_section.isChecked())
        if self._btn_ghost.isChecked():
            self._request_ghost()
        self.readout.setText("Loaded: %s\nAdjust parameters, then Generate."
                             % os.path.basename(path))
        self.statusBar().showMessage("Loaded %s - Generate to build."
                                     % os.path.basename(path))

    def _default_hold_height(self, part, toast=False):
        """Seed hold_height to 40% of oriented part height."""
        try:
            from ..core import orient
            oriented, _info = orient.orient_solid(part, self.params)
            h = float(oriented.bounding_box(optimal=True).max.Z)
        except Exception:
            return
        if h <= 0:
            return
        val = round(0.4 * h, 1)
        w = self._widgets.get("hold_height")
        if w is not None:
            val = min(max(val, w.minimum()), w.maximum())
        self.params.hold_height = val
        if w is not None:
            w.blockSignals(True)
            w.setValue(val)
            w.blockSignals(False)
        self._sync_hold_slider()
        self.viewer_part.set_hold(self.params.hold_height)
        if toast:
            self._toast("hold_height → %.1f mm" % val)

    def _seating_dir(self):
        """Part-frame down-into-tray direction."""
        try:
            from ..core.orient import seating_direction
            return tuple(float(v) for v in seating_direction(self.params))
        except Exception:
            return (0.0, 0.0, 1.0)

    def _tray_normal(self):
        """Insertion-direction normal for tray preview plane."""
        d = self._seating_dir()
        if str(self.params.tilt_mode) != "B" or not float(self.params.tilt_deg):
            return d
        try:
            import numpy as np
            from ..core.orient import (rotation_a_to_b, seating_direction,
                                       _AXIS_VEC, _rodrigues)
            R_orient = np.asarray(
                rotation_a_to_b(seating_direction(self.params), (0.0, 0.0, -1.0)),
                dtype=float)
            ax = np.asarray(_AXIS_VEC[str(self.params.tilt_axis)], dtype=float)
            R_t = _rodrigues(ax, np.radians(float(self.params.tilt_deg)))
            world_ins = R_t @ np.array([0.0, 0.0, -1.0])
            d_part = R_orient.T @ world_ins
            n = np.linalg.norm(d_part)
            return tuple(float(v) for v in (d_part / n)) if n > 1e-9 else d
        except Exception:
            return d

    def _part_tilt_matrix(self):
        """Part-body lean matrix for rotate-part mode, else None."""
        if str(self.params.tilt_mode) != "A" or not float(self.params.tilt_deg):
            return None
        try:
            import numpy as np
            from ..core.orient import (rotation_a_to_b, seating_direction,
                                       _AXIS_VEC, _rodrigues)
            R_orient = np.asarray(
                rotation_a_to_b(seating_direction(self.params), (0.0, 0.0, -1.0)),
                dtype=float)
            ax = np.asarray(_AXIS_VEC[str(self.params.tilt_axis)], dtype=float)
            R_t = _rodrigues(ax, np.radians(float(self.params.tilt_deg)))
            return R_orient.T @ R_t @ R_orient
        except Exception:
            return None

    def _refresh_part_view(self):
        if self.bridge.part is not None:
            self.viewer_part.set_tilt_gizmo3d(self.params.tilt_axis,
                                              self.params.tilt_deg,
                                              str(self.params.tilt_mode))
            self.viewer_part.show_part(self.bridge.part, self._seating_dir(),
                                       color="#9fb3d1", reset=False,
                                       tray_normal=self._tray_normal(),
                                       part_tilt=self._part_tilt_matrix())
            # Drop stale ghost before camera swings; regen after settle.
            if self._ghost_active:
                self.viewer_part.clear_cavity()
            # Animate camera only if seating direction actually changed.
            import numpy as np
            new_dir = np.asarray(self._seating_dir(), float)
            prev = getattr(self, "_last_seating_dir", None)
            animate = prev is None or float(np.dot(new_dir, prev)) < 0.99999
            self._last_seating_dir = new_dir
            self.viewer_part.orient_camera(tuple(new_dir), animate=animate,
                                           on_done=self._kick_live_ghost)

    def _kick_live_ghost(self):
        """Post-rotation: start debounced ghost rebuild."""
        if (self._ghost_active and self.bridge.step_path
                and self.cfg.get("live_preview", True)):
            self._toast("Regenerating ghost…")
            self._auto_timer.start(self._AUTO_MS)

    def open_preset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open preset", self.cfg.get("last_dir") or os.path.expanduser("~"),
            "Preset (*.json)")
        if not path:
            return
        try:
            self.params = Params.load(path)
        except Exception as e:
            QMessageBox.warning(self, "Preset", "Could not load preset:\n%s" % e)
            return
        self._sync_widgets()
        self.cfg["last_preset"] = path
        save_cfg(self.cfg)
        self.statusBar().showMessage("Loaded preset %s" % os.path.basename(path))

    def save_preset(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save preset", self.cfg.get("last_dir") or os.path.expanduser("~"),
            "Preset (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self.params.save(path)
        except Exception as e:
            QMessageBox.warning(self, "Preset", "Could not save preset:\n%s" % e)
            return
        self.statusBar().showMessage("Saved preset %s" % os.path.basename(path))

    def _sync_widgets(self):
        """Push params back into bound widgets."""
        for name, w in self._widgets.items():
            val = getattr(self.params, name)
            w.blockSignals(True)
            if isinstance(w, QComboBox):
                w.setCurrentText(str(val))
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(val))
            elif isinstance(w, QLineEdit):
                w.setText(str(val or ""))
            elif isinstance(w, (QSpinBox,)):
                w.setValue(int(val))
            elif isinstance(w, QDoubleSpinBox):
                w.setValue(float(val))
            w.blockSignals(False)
        for cb, nm in ((self.cb_axis, "seating_axis"),
                       (self.cb_export, "export_format")):
            cb.blockSignals(True)
            cb.setCurrentText(str(getattr(self.params, nm)))
            cb.blockSignals(False)
        self.btn_flip.setChecked(bool(self.params.flip))
        self.cb_tmode.blockSignals(True)
        self.cb_tmode.setCurrentIndex(0 if str(self.params.tilt_mode) == "A" else 1)
        self.cb_tmode.blockSignals(False)
        self.viewer_part.set_tilt_gizmo3d(self.params.tilt_axis,
                                          self.params.tilt_deg,
                                          str(self.params.tilt_mode))
        self._apply_visibility()

    def settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec() != QDialog.Accepted:
            return
        vals = dlg.values()
        self.cfg.update(vals)
        save_cfg(self.cfg)

        from .icons import set_accent, set_ui_scale
        set_accent(vals["icon_color"])
        set_ui_scale(vals["ui_scale"])
        self._retint_icons()

        self.params.bed_x = vals["bed_x"]
        self.params.bed_y = vals["bed_y"]

        self.statusBar().showMessage("Settings saved.")

    def _retint_icons(self):
        """Rebuild button icons against current accent."""
        from .icons import make_icon
        for b in self.findChildren(QToolButton):
            name = b.property("icon_name")
            if not name:
                continue
            px = int(b.property("icon_size_px") or 22)
            b.setIcon(make_icon(name, b.property("icon_fixed_color"), px))

    def toggle_ghost(self):
        """Toggle cavity ghost overlay."""
        on = self._btn_ghost.isChecked()
        if on and self.bridge.part is None:
            self._btn_ghost.setChecked(False)
            self.statusBar().showMessage("Load a STEP part first.")
            return
        if on:
            if self._view_mode == "tray":
                self._apply_view_mode("part")
            self._request_ghost()
        else:
            self._ghost_active = False
            self._ghost_built = False
            self.viewer_part.clear_cavity()
            self.statusBar().showMessage("Ghost off.")

    def _request_ghost(self):
        """Kick off-thread cavity build."""
        if not self.bridge.step_path:
            return
        prm = self.params.model_copy()
        self._start_build(
            "Ghost", lambda pr: self.bridge.build_ghost(prm, progress=pr),
            silent=self._ghost_built)

    def toggle_section(self):
        """Toggle part cutaway clip."""
        on = self.btn_section.isChecked()
        if on and self.bridge.part is None:
            self.btn_section.setChecked(False)
            self.statusBar().showMessage("Load a STEP part first.")
            return
        if on and self._view_mode == "tray":
            self._apply_view_mode("part")
        self.viewer_part.set_section(on)
        self.statusBar().showMessage(
            "Part cutaway %s." % ("on" if on else "off"))

    def _on_section_drag(self, hold):
        """Section drag -> write hold_height."""
        w = self._widgets.get("hold_height")
        if w is None:
            return
        hold = min(max(float(hold), w.minimum()), w.maximum())
        w.setValue(round(hold, 1))

    def _on_hold_slider(self, v):
        w = self._widgets.get("hold_height")
        if w is not None:
            w.setValue(v / 10.0)             # slider = mm*10

    def _sync_hold_slider(self):
        s = getattr(self, "_hold_slider", None)
        if s is None:
            return
        s.blockSignals(True)
        s.setValue(int(round(float(self.params.hold_height) * 10)))
        s.blockSignals(False)

    def generate(self):
        if not self.bridge.step_path:
            self.statusBar().showMessage("Load a STEP part first.")
            return
        prm = self.params.model_copy()
        self._start_build("Generate",
                          lambda pr: self.bridge.build(prm, progress=pr))

    def generate_drawer(self):
        if not self.project.entries:
            self.statusBar().showMessage("Add parts to the project first.")
            return
        # Drawer-level base/skeleton from current panel; persist onto project.
        self.project.drawer = self.params.model_copy(deep=True)
        proj = self.project.model_copy(deep=True)
        self._start_build(
            "Drawer", lambda pr: self.bridge.build_drawer(proj, progress=pr))

    def generate_batch(self):
        if not self.project.entries:
            self.statusBar().showMessage("Add parts to the project first.")
            return
        proj = self.project.model_copy(deep=True)
        self._start_build(
            "Batch", lambda pr: self.bridge.build_batch(proj, progress=pr))

    # ---- Transient toast ----
    def _toast(self, text, msecs=2200):
        """Pop floating fade-out note."""
        lbl = getattr(self, "_toast_label", None)
        if lbl is None:
            lbl = QLabel(self)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                "background: rgba(40,44,52,235); color:#e8ecf2;"
                " padding:8px 16px; border-radius:6px; font-size:10pt;")
            eff = QGraphicsOpacityEffect(lbl)
            lbl.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.finished.connect(lbl.hide)
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._fade_toast)
            self._toast_label = lbl
            self._toast_effect = eff
            self._toast_anim = anim
            self._toast_timer = timer
        self._toast_anim.stop()
        self._toast_label.setText(text)
        self._toast_label.adjustSize()
        self._position_toast()
        self._toast_effect.setOpacity(1.0)
        self._toast_label.show()
        self._toast_label.raise_()
        self._toast_timer.start(msecs)

    def _position_toast(self):
        lbl = getattr(self, "_toast_label", None)
        if lbl is None:
            return
        x = (self.width() - lbl.width()) // 2
        y = self.height() - lbl.height() - 48
        lbl.move(max(0, x), max(0, y))

    def _fade_toast(self):
        anim = self._toast_anim
        anim.stop()
        anim.setDuration(450)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_toast()

    def closeEvent(self, event):
        # Block until in-flight build finishes; killing QThread mid-run crashes.
        th = getattr(self, "_build_thread", None)
        if th is not None and th.isRunning():
            self.statusBar().showMessage("Finishing build before closing…")
            th.wait()
        # Finalize VTK before Qt drops GL context.
        for v in (getattr(self, "viewer_part", None), getattr(self, "viewer_tray", None)):
            if v is not None:
                v.shutdown_vtk()
        super().closeEvent(event)

    def _start_build(self, what, fn, silent=False):
        """Run fn(progress) on worker thread."""
        if getattr(self, "_build_thread", None) is not None:
            self.statusBar().showMessage("A build is already running…")
            return
        if not silent:
            self._set_build_buttons(False)
        self.statusBar().showMessage(
            "%s: %s…" % (what, "refreshing" if silent else "building"))
        if not silent:
            self.readout.setText("%s: building…" % what)
            dlg = BuildProgressDialog(what, self)
            self._progress_dialog = dlg
            dlg.show()

        # Tessellate in worker; only finished PolyData crosses thread boundary.
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
        # Full build takes over view; stop live ghost refresh.
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
            self.viewer_tray.show_polydata(
                meshes.get("tray"), color="#cdd6e6",
                title="%s - print coordinates (Z up, floor at 0)"
                % ("Drawer" if what == "Drawer" else "Tray"))
            self._arm_slide_preview(result)
            if self._view_mode != "split":
                self._apply_view_mode("tray")

    def _arm_slide_preview(self, result):
        """Arm slide-in/out part preview in tray viewer."""
        place = getattr(result, "part_place", None)
        to_oriented = getattr(result, "to_oriented", None)
        raw = getattr(self.viewer_part, "_part_mesh", None)
        if place is None or to_oriented is None or raw is None:
            self.viewer_tray.set_slide_part(None)
            return
        import numpy as np
        M = np.asarray(to_oriented, float)
        pts = np.asarray(raw.points, float)
        cap_pts = (M[:3, :3] @ pts.T).T + M[:3, 3]
        # Rotate-tray: lean part so preview enters oblique pocket at angle.
        if str(self.params.tilt_mode) == "B" and float(self.params.tilt_deg):
            from ..core.orient import _rodrigues, _AXIS_VEC
            axisvec = np.asarray(_AXIS_VEC[str(self.params.tilt_axis)], float)
            R = _rodrigues(axisvec, -np.radians(float(self.params.tilt_deg)))
            cap_pts = (R @ cap_pts.T).T
        seated_pts = cap_pts + np.asarray(place, float)
        seated = raw.copy()
        seated.points = seated_pts
        d = np.asarray(getattr(result, "part_slide_dir", (0.0, 0.0, 1.0)), float)
        d = d / (np.linalg.norm(d) or 1.0)
        span = float((seated_pts @ d).max() - (seated_pts @ d).min())
        self.viewer_tray.set_slide_part(seated, tuple(d), span + 8.0)

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
            self.viewer_tray.show_polydata(
                meshes.get("tray"), color="#cdd6e6",
                title="Batch - first part's tray (export writes all)")
            if self._view_mode != "split":
                self._apply_view_mode("tray")

    def _show_ghost(self, result, meshes):
        """Overlay cavity ghost on raw part."""
        cav = meshes.get("cavity")
        if cav is None or not self._btn_ghost.isChecked():
            return
        cav_part = self._to_part_frame(cav, getattr(result, "to_part", None))
        # Rotate-part: lean ghost by same matrix about part centroid as the body.
        R = self._part_tilt_matrix()
        raw = getattr(self.viewer_part, "_part_mesh", None)
        if R is not None and cav_part is not None and raw is not None:
            import numpy as np
            c = np.asarray(raw.center, dtype=float)
            pts = np.asarray(cav_part.points, dtype=float)
            cav_part = cav_part.copy()
            cav_part.points = (np.asarray(R, dtype=float) @ (pts - c).T).T + c
        self.viewer_part.set_cavity(cav_part, on=True)
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
        self.statusBar().showMessage("%s failed: %s" % (what, msg))
        self.readout.setText("%s failed:\n%s" % (what, msg))

    def _build_finished(self):
        self._build_thread = None
        self._set_build_buttons(True)
        dlg = getattr(self, "_progress_dialog", None)
        if dlg is not None:
            dlg.finish()
            self._progress_dialog = None
        # Param changed mid-build: fire one coalesced refresh now.
        if (self._rebuild_dirty and self._ghost_active
                and self.cfg.get("live_preview", True)):
            self._rebuild_dirty = False
            self._auto_timer.start(0)

    def _set_build_buttons(self, enabled):
        for b in (getattr(self, "_btn_ghost", None),
                  getattr(self, "_btn_generate", None),
                  getattr(self, "_btn_export", None),
                  getattr(self, "_btn_drawer", None),
                  getattr(self, "_btn_batch", None)):
            if b is not None:
                b.setEnabled(enabled)

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
                self.statusBar().showMessage("Export cancelled - regenerate first.")
                return
        from ..core import io
        # Bed-split tiles when present, else tray(s); multi-piece -> _1, _2, …
        solids = res.tiles if (res.tiles and len(res.tiles) > len(res.trays)) \
            else res.trays
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
                solids = res.tiles if (res.tiles and
                                       len(res.tiles) > len(res.trays)) \
                    else res.trays
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

    def _active_viewers(self):
        return [v for v in (self.viewer_part, self.viewer_tray)
                if v.isVisible() and v.plotter is not None]

    def fit(self):
        for v in self._active_viewers():
            v.reset_camera()

    def _zoom(self, factor):
        for v in self._active_viewers():
            v.plotter.camera.zoom(factor)
            v.plotter.render()

    def _reset_view(self):
        for v in self._active_viewers():
            v.plotter.view_isometric()
            v.reset_camera()

    def about(self):
        QMessageBox.information(
            self, "About %s" % APP_NAME,
            "%s v%s\n\nParametric 3D-printable nesting trays that cradle the "
            "bottom band of complex CNC parts.\n\nSee "
            "parts_packing_generator_design.md." % (APP_NAME, __version__))
