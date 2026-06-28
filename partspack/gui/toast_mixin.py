# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# transient toast overlay (MainWindow mixin)

from __future__ import annotations


from PySide6.QtCore import Qt, QTimer, QPropertyAnimation
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect


class ToastMixin:
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

