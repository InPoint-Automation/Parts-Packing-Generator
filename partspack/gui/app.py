# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# GUI launch.

import os
import sys

# Force xcb: VTK QtInteractor uses native X11 window; Wayland -> BadWindow.
os.environ.setdefault("QT_API", "pyside6")
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtWidgets import QApplication  # noqa: E402

from ..config import load_cfg  # noqa: E402
from .icons import set_accent, set_ui_scale  # noqa: E402
from .theme import apply_office_theme  # noqa: E402
from .main_window import MainWindow  # noqa: E402


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
