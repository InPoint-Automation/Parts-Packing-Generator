# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# project / part-library panel mixin

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDockWidget, QFileDialog, QMessageBox, QPushButton, QLineEdit, QListWidget, QListWidgetItem

from ..config import save_cfg
from ..project import Project
from .icons import icon_button
from .theme import OFFICE


class ProjectMixin:
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

        self._proj_detail = QLabel("No entry selected.")
        self._proj_detail.setWordWrap(True)
        self._proj_detail.setStyleSheet(
            "color:%s; font-size:8pt; padding:2px 0;" % OFFICE["muted"])
        v.addWidget(self._proj_detail)

        cnt_row = QHBoxLayout()
        cnt_row.addWidget(QLabel("Copies"))
        self._proj_count = QSpinBox()
        self._proj_count.setRange(1, 999)
        self._proj_count.setEnabled(False)
        self._proj_count.valueChanged.connect(self._project_count_changed)
        cnt_row.addWidget(self._proj_count)
        cnt_row.addStretch(1)
        up = icon_button("move_up", lambda: self._project_move(-1),
                         "Move selected entry up")
        down = icon_button("move_down", lambda: self._project_move(1),
                           "Move selected entry down")
        cnt_row.addWidget(up)
        cnt_row.addWidget(down)
        v.addLayout(cnt_row)

        row1 = QHBoxLayout()
        add = QPushButton("Add current")
        add.setToolTip("Add the loaded part + current params as a new entry")
        add.clicked.connect(self.project_add_current)
        upd = QPushButton("Update")
        upd.setToolTip("Write the current panel params back into the selected "
                       "entry (keeps its position + copies)")
        upd.clicked.connect(self.project_update_selected)
        for b in (add, upd):
            row1.addWidget(b)
        v.addLayout(row1)

        row2 = QHBoxLayout()
        load = QPushButton("Load")
        load.setToolTip("Load the selected entry's part + params into the editor")
        load.clicked.connect(self._project_load_selected)
        dup = QPushButton("Duplicate")
        dup.clicked.connect(self.project_duplicate_selected)
        rem = QPushButton("Remove")
        rem.clicked.connect(self._project_remove_selected)
        for b in (load, dup, rem):
            row2.addWidget(b)
        v.addLayout(row2)

        # drawer-only settings; rest from Parameters panel
        dg = self._group("Drawer", [
            ("drawer_pack_gap", self._dspin("drawer_pack_gap", 0, 60, 1)),
            ("bed_split", self._check("bed_split")),
        ])
        v.addWidget(dg)

        self._proj_summary = QLabel()
        self._proj_summary.setWordWrap(True)
        self._proj_summary.setStyleSheet(
            "color:%s; font-size:8pt; padding:2px 0;" % OFFICE["muted"])
        v.addWidget(self._proj_summary)

        self._proj_note = QLabel(
            "Double-click loads an entry. Drawer = all parts in one packed base; "
            "Batch = one tray per part. Base/skeleton/margins/bed come from the "
            "Parameters panel; per-part capture/relief stay with each entry.")
        self._proj_note.setWordWrap(True)
        self._proj_note.setStyleSheet(
            "color:%s; font-size:8pt;" % OFFICE["muted"])
        v.addWidget(self._proj_note)

        dock.setWidget(body)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.setMinimumWidth(240)
        self._refresh_project_list()
        self._refresh_drawer_summary()

    def _refresh_project_list(self):
        """Repaint entry list and name."""
        self._proj_list.blockSignals(True)
        self._proj_list.clear()
        for e in self.project.entries:
            QListWidgetItem(self._entry_text(e), self._proj_list)
        self._proj_list.blockSignals(False)
        self._proj_name.blockSignals(True)
        self._proj_name.setText(self.project.name)
        self._proj_name.blockSignals(False)
        self._project_row_changed(self._proj_list.currentRow())

    @staticmethod
    def _entry_text(e):
        dims = ("   " + e.dims) if e.dims else ""
        return "%s%s   x%d" % (e.name(), dims, e.count)

    def _project_row_changed(self, row):
        ok = 0 <= row < len(self.project.entries)
        self._proj_count.blockSignals(True)
        self._proj_count.setEnabled(ok)
        if ok:
            self._proj_count.setValue(int(self.project.entries[row].count))
        self._proj_count.blockSignals(False)
        if hasattr(self, "_proj_detail"):
            self._proj_detail.setText(
                self._entry_detail(self.project.entries[row]) if ok
                else "No entry selected.")

    @staticmethod
    def _entry_detail(e):
        """One-line per-entry param summary."""
        p = e.params
        bits = ["seat %s" % p.seating]
        if str(p.seating) == "axis":
            bits[0] += "/%s" % p.seating_axis
        if p.flip:
            bits.append("flip")
        bits.append("hold %.1f" % float(p.hold_height))
        if p.two_sided:
            bits.append("two-sided")
        if float(p.part_lean_deg):
            bits.append("lean %+.0f deg" % float(p.part_lean_deg))
        if float(p.tray_angle_deg):
            bits.append("tray %+.0f deg" % float(p.tray_angle_deg))
        return " - ".join(bits)

    def _part_dims_str(self):
        """WxHxD of loaded raw part, or '' if unavailable."""
        part = getattr(self.bridge, "part", None)
        if part is None:
            return ""
        try:
            bb = part.bounding_box()
            s = bb.size
            return "%.0fx%.0fx%.0f mm" % (float(s.X), float(s.Y), float(s.Z))
        except Exception:
            return ""

    def _refresh_drawer_summary(self):
        """Drawer base driven by Parameters panel."""
        if not hasattr(self, "_proj_summary"):
            return
        from ..core import array
        p = self.params
        l, r, back, front = array.margins(p)
        if p.margin_advanced:
            mtxt = "margins L%g R%g B%g F%g" % (l, r, back, front)
        else:
            mtxt = "margin %g" % l
        bed = ("bed %gx%g" % (p.bed_x, p.bed_y)
               if p.bed_x and p.bed_y else "bed unset")
        self._proj_summary.setText(
            "Drawer base from Parameters: %s - %s - %s"
            % (p.skeleton_style, mtxt, bed))

    def _project_count_changed(self, val):
        row = self._proj_list.currentRow()
        if 0 <= row < len(self.project.entries):
            self.project.entries[row].count = int(val)
            it = self._proj_list.item(row)
            e = self.project.entries[row]
            if it is not None:
                it.setText(self._entry_text(e))

    def project_add_current(self):
        if not self.bridge.step_path:
            self.statusBar().showMessage("Load a STEP part first.")
            return
        self.project.add(self.bridge.step_path, self.params,
                         count=1, dims=self._part_dims_str())
        self._refresh_project_list()
        self._proj_list.setCurrentRow(len(self.project.entries) - 1)
        self.statusBar().showMessage(
            "Added %s to the project (%d part%s)."
            % (self.project.entries[-1].name(), len(self.project.entries),
               "" if len(self.project.entries) == 1 else "s"))

    def project_update_selected(self):
        """Write current panel params into selected entry."""
        row = self._proj_list.currentRow()
        if not (0 <= row < len(self.project.entries)):
            self.statusBar().showMessage("Select an entry to update.")
            return
        e = self.project.entries[row]
        e.params = self.params.model_copy(deep=True)
        # refresh cached dims if entry's part is loaded
        if self.bridge.step_path and e.step_path == self.bridge.step_path:
            e.dims = self._part_dims_str() or e.dims
        it = self._proj_list.item(row)
        if it is not None:
            it.setText(self._entry_text(e))
        self._project_row_changed(row)
        self.statusBar().showMessage("Updated %s with the current params."
                                     % e.name())

    def project_duplicate_selected(self):
        row = self._proj_list.currentRow()
        j = self.project.duplicate(row)
        if j < 0:
            self.statusBar().showMessage("Select an entry to duplicate.")
            return
        self._refresh_project_list()
        self._proj_list.setCurrentRow(j)
        self.statusBar().showMessage("Duplicated %s."
                                     % self.project.entries[j].name())

    def _project_move(self, delta):
        row = self._proj_list.currentRow()
        if not (0 <= row < len(self.project.entries)):
            return
        j = self.project.move(row, delta)
        self._refresh_project_list()
        self._proj_list.setCurrentRow(j)

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
                                   part_tilt=self._part_view_matrix())
        self._apply_part_gizmos()
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

