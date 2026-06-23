# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# GUI launch.

import os
import sys

os.environ.setdefault("QT_API", "pyside6")

# Force xcb: VTK QtInteractor uses native X11 window; Wayland -> BadWindow.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat

if os.environ.get("PARTSPACK_SOFTGL"):
    try:
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    except Exception:
        pass

def _init_gl_format():
    try:
        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
        fmt.setVersion(3, 2)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setDepthBufferSize(24)
        fmt.setStencilBufferSize(8)
        fmt.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
        QSurfaceFormat.setDefaultFormat(fmt)
    except Exception:
        pass

try:
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
except Exception:
    pass

_init_gl_format()

from PySide6.QtWidgets import QApplication

from ..config import load_cfg
from .icons import set_accent, set_ui_scale
from .theme import apply_office_theme
from .main_window import MainWindow


def main():
    cfg = load_cfg()
    app = QApplication(sys.argv)
    set_accent(cfg.get("icon_color"))
    set_ui_scale(cfg.get("ui_scale"))
    apply_office_theme(app)
    win = MainWindow(cfg=cfg)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()