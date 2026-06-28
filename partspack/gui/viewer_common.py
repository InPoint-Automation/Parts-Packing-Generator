# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# viewer helpers + pyvista import probe, shared by Viewer mixins

import os

os.environ.setdefault("QT_API", "pyside6")  # before pyvistaqt imports qtpy

_PYVISTA_ERR = None
try:
    from pyvistaqt import QtInteractor
    HAVE_PYVISTA = True
except Exception as _e:                      # pragma: no cover - env dependent
    QtInteractor = None
    HAVE_PYVISTA = False
    _PYVISTA_ERR = _e


_OVERLAY_BTN_CSS = (
    "QToolButton{background:#f3f6fb; border:1px solid #a3b4cc;"
    " border-radius:4px; color:#1e1e1e; font-size:8pt; padding-top:3px;}"
    "QToolButton:hover{background:#e3ebf7;}"
    "QToolButton:checked{background:#cfe0f5; border:1px solid #5b8def;}")


def _opengl_usable():
    """Probe whether OpenGL 3.2+ context works."""
    if os.environ.get("PARTSPACK_SKIP_GLPROBE"):
        return True, None
    try:
        from PySide6.QtGui import (QOffscreenSurface, QOpenGLContext,
                                   QSurfaceFormat)
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 2)
        surf = QOffscreenSurface()
        surf.setFormat(fmt)
        surf.create()
        if not surf.isValid():
            return False, "offscreen surface invalid"
        ctx = QOpenGLContext()
        ctx.setFormat(fmt)
        if not ctx.create():
            return False, "QOpenGLContext.create() failed"
        if not ctx.makeCurrent(surf):
            return False, "makeCurrent() failed (no usable OpenGL driver)"
        got = ctx.format()
        major, minor = got.majorVersion(), got.minorVersion()
        ctx.doneCurrent()
        if (major, minor) < (3, 2):
            return False, ("OpenGL %d.%d only, VTK needs 3.2+. This usually "
                           "means a Remote Desktop session or a VM with no GPU "
                           "acceleration." % (major, minor))
        return True, None
    except Exception as e:
        return False, str(e)


def _hex_rgb(hexcol):
    """Hex string to (r, g, b) floats 0..1."""
    h = hexcol.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _slerp(a, b, t):
    """Spherical interp between two unit vectors."""
    import numpy as np
    a = np.asarray(a, float); b = np.asarray(b, float)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return b
    a, b = a / na, b / nb
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if dot > 0.9995:                         # near-parallel
        v = a + (b - a) * t
        n = np.linalg.norm(v)
        return v / n if n > 1e-12 else b
    if dot < -0.9995:                        # antiparallel
        ref = _least_aligned_axis(a)
        rel = np.cross(a, ref)
        rel = rel / np.linalg.norm(rel)
        theta = np.pi * t
        return a * np.cos(theta) + rel * np.sin(theta)
    theta = np.arccos(dot) * t
    rel = b - a * dot
    rel = rel / np.linalg.norm(rel)
    return a * np.cos(theta) + rel * np.sin(theta)


def _least_aligned_axis(v):
    """World axis most perpendicular to v."""
    import numpy as np
    v = np.abs(np.asarray(v, float))
    i = int(np.argmin(v))
    e = np.zeros(3); e[i] = 1.0
    return e
