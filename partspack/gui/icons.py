# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Lucide SVG to recolored QIcon, ribbon tool-button factory.

import os
import sys
import tempfile

from PySide6.QtCore import Qt, QSize, QRectF, QPointF
from PySide6.QtGui import (QIcon, QPixmap, QImage, QPainter, QColor, QPolygonF,
                           QPen)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QToolButton


def _icon_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [os.path.join(here, "icons_svg")]
    walk = here
    for _ in range(3):
        walk = os.path.dirname(walk)
        candidates.append(os.path.join(walk, "icons_svg"))
    try:
        candidates.append(os.path.join(__compiled__.containing_dir, "icons_svg"))
    except NameError:
        pass
    candidates.append(os.path.join(os.path.dirname(sys.argv[0]), "icons_svg"))
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(os.path.join(base, "icons_svg"))
        candidates.append(os.path.join(base, "partspack", "gui", "icons_svg"))
    for p in candidates:
        if os.path.isdir(p):
            return p
    return os.path.join(here, "icons_svg")


# per-icon accents
ICON_COLORS = {
    "load_step": "#2b6cb0", "open_preset": "#b7791f", "preset": "#217346",
    "save": "#217346", "export": "#6b46c1", "settings": "#4a5568",
    "help": "#2b6cb0", "fit": "#2b6cb0", "zoom_in": "#2b6cb0",
    "zoom_out": "#2b6cb0", "rotate": "#6b46c1", "orient": "#c05621",
    "flip": "#4a5568", "tilt": "#c05621",
    "capture": "#2c7a7b", "generate": "#217346",
    "band": "#c08a1f", "section": "#2c7a7b",
    "grid": "#4a5568", "base": "#4a5568", "relief": "#c53030",
    "sandwich": "#6b46c1", "undo": "#c05621", "panel": "#2c7a7b",
    "library": "#b7791f", "drawer": "#217346", "addpart": "#2b6cb0",
    "play": "#217346", "popin": "#2b6cb0", "up": "#4a5568",
    "move_up": "#4a5568", "move_down": "#4a5568",
}

_DEFAULT_COLOR = "#1F3864"
ACCENT = _DEFAULT_COLOR
UI_SCALE = 1.0

_svg_cache = {}
_icon_cache = {}
_arrow_cache = {}
_check_cache = {}


def set_accent(color):
    global ACCENT
    if not color or not QColor(color).isValid():
        return
    if color != ACCENT:
        ACCENT = color
        _icon_cache.clear()


def set_ui_scale(scale):
    global UI_SCALE
    UI_SCALE = float(scale) if scale and scale > 0 else 1.0


def spin_arrow_png(direction, color, px=18):
    """Render up/down triangle to temp PNG, return path."""
    key = (direction, color, px)
    path = _arrow_cache.get(key)
    if path and os.path.isfile(path.replace("/", os.sep)):
        return path

    scale = 3
    s = max(1, int(px)) * scale
    img = QImage(s, s, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    pad = s * 0.32
    cx = s / 2.0
    if direction == "up":
        pts = [QPointF(cx, pad), QPointF(s - pad, s - pad), QPointF(pad, s - pad)]
    else:
        pts = [QPointF(pad, pad), QPointF(s - pad, pad), QPointF(cx, s - pad)]
    p.drawPolygon(QPolygonF(pts))
    p.end()

    path = os.path.join(
        tempfile.gettempdir(),
        "partspack_spin_%s_%s_%d.png" % (direction, str(color).lstrip("#"), px))
    img.save(path, "PNG")
    path = path.replace(os.sep, "/")
    _arrow_cache[key] = path
    return path


def check_png(color="#ffffff", px=16):
    """Render checkmark to temp PNG, return path."""
    key = (color, px)
    path = _check_cache.get(key)
    if path and os.path.isfile(path.replace("/", os.sep)):
        return path

    scale = 3
    s = max(1, int(px)) * scale
    img = QImage(s, s, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(s * 0.14)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.drawPolyline(QPolygonF([QPointF(s * 0.22, s * 0.52),
                              QPointF(s * 0.43, s * 0.72),
                              QPointF(s * 0.78, s * 0.30)]))
    p.end()

    path = os.path.join(
        tempfile.gettempdir(),
        "partspack_check_%s_%d.png" % (str(color).lstrip("#"), px))
    img.save(path, "PNG")
    path = path.replace(os.sep, "/")
    _check_cache[key] = path
    return path


def _renderer(name):
    if name in _svg_cache:
        return _svg_cache[name]
    path = os.path.join(_icon_dir(), name + ".svg")
    r = QSvgRenderer(path) if os.path.isfile(path) else None
    if r is not None and not r.isValid():
        r = None
    _svg_cache[name] = r
    return r


def make_pixmap(name, color=None, px=20, dpr=1.0):
    color = color or ICON_COLORS.get(name) or ACCENT
    rend = _renderer(name)
    side = max(1, int(round(px * dpr)))
    img = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    if rend is not None:
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        rend.render(p, QRectF(0, 0, side, side))
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(0, 0, side, side, QColor(color))
        p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return pm


def make_icon(name, color=None, px=20):
    key = (name, color or "", px)
    hit = _icon_cache.get(key)
    if hit is None:
        hit = QIcon(make_pixmap(name, color, px))
        _icon_cache[key] = hit
    return hit


def icon_button(name, callback=None, tip="", label=None, color=None,
                toggle=False, size=22):
    """Flat tool button with accented icon."""
    size = max(1, int(round(size * UI_SCALE)))
    b = QToolButton()
    b.setIcon(make_icon(name, color, size))
    b.setIconSize(QSize(size, size))
    b.setAutoRaise(True)
    b.setFocusPolicy(Qt.NoFocus)
    if label:
        b.setText(label)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    else:
        b.setToolButtonStyle(Qt.ToolButtonIconOnly)
    if tip:
        b.setToolTip(tip)
    if toggle:
        b.setCheckable(True)
    if callback is not None:
        b.clicked.connect(lambda _checked=False: callback())
    # live re-tint on accent change
    b.setProperty("icon_name", name)
    b.setProperty("icon_size_px", size)
    b.setProperty("icon_fixed_color", color)
    return b