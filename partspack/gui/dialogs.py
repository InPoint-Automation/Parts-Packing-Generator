# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# standalone dialogs + build worker thread

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QProgressBar,
    QPushButton, QDialogButtonBox, QDoubleSpinBox, QCheckBox)

from .theme import OFFICE


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
        self._heading = QLabel("%s: starting..." % title)
        self._heading.setStyleSheet("font-weight:600;")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._stage = QLabel("Preparing...")
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
        self._live = QCheckBox()
        self._live.setChecked(bool(cfg.get("live_preview", True)))
        self._live.setToolTip("Auto-refresh the cavity ghost when a parameter "
                              "changes.")
        form.addRow(QLabel("Live preview"), self._live)
        self._spec = QCheckBox()
        self._spec.setChecked(bool(cfg.get("speculative_build", True)))
        self._spec.setToolTip("Pre-build the tray in the background while idle "
                              "so Generate is instant. Uses spare CPU; results "
                              "are only used when parameters still match.")
        form.addRow(QLabel("Background build"), self._spec)

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
            "live_preview": bool(self._live.isChecked()),
            "speculative_build": bool(self._spec.isChecked()),
        }
