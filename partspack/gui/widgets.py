# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Ribbon building blocks: Office-style groups and captioned fields.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QSizePolicy)

from .theme import OFFICE


def rib_group(caption, widgets, step=None, tint=None):
    """Ribbon group: row of controls with caption beneath."""
    g = QWidget()
    g.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)
    if tint:
        name = "rg_" + "".join(c for c in caption if c.isalnum())
        g.setObjectName(name)
        g.setStyleSheet(
            "QWidget#%s { background:%s; border:1px solid %s;"
            " border-radius:6px; }" % (name, tint, OFFICE["border_lt"]))
    v = QVBoxLayout(g)
    v.setContentsMargins(5, 3, 5, 2)
    v.setSpacing(1)
    roww = QWidget()
    roww.setStyleSheet("background:transparent;")
    row = QHBoxLayout(roww)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    for w in widgets:
        row.addWidget(w)
    v.addWidget(roww, 0, Qt.AlignTop)
    v.addStretch(1)
    if step:
        text = ("<span style='background:%s; color:#ffffff; font-weight:bold;'>"
                "&nbsp;%d&nbsp;</span>&nbsp;<b>%s</b>"
                % (OFFICE["accent"], step, caption))
    else:
        text = caption
    cap = QLabel(text)
    cap.setTextFormat(Qt.RichText)
    cap.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
    cap.setStyleSheet("font-size:8pt; color:%s; background:transparent;"
                      % OFFICE["muted"])
    v.addWidget(cap, 0, Qt.AlignBottom)
    return g


def field(label, widget, top=None):
    """Captioned control: label above widget."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(2, 0, 2, 0)
    v.setSpacing(1)
    if top is not None:
        v.addWidget(top)
    lab = QLabel(label)
    lab.setStyleSheet("font-size:7pt; color:%s;" % OFFICE["muted"])
    v.addWidget(lab)
    v.addWidget(widget)
    return w
