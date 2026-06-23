#!/usr/bin/env python3
# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Launch the GUI. Deps: pip install -r requirements.txt

import io
import logging
import os
import sys

# Wayland fix
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


def _app_dir():
    """app directory"""
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                           else os.path.abspath(__file__))


LOG_PATH = os.path.join(_app_dir(), "PartsPack.log")


def _setup_logging():
    """PartsPack.log"""
    try:
        logf = open(LOG_PATH, "w", encoding="utf-8", buffering=1)
    except OSError:
        return
    logging.basicConfig(
        stream=logf, level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if getattr(sys, "frozen", False):
        sys.stdout = logf
        sys.stderr = logf
        for _fd in (1, 2):
            try:
                os.dup2(logf.fileno(), _fd)
            except (OSError, ValueError, io.UnsupportedOperation):
                pass

    def _hook(exc_type, exc, tb):
        logging.error("Uncaught exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = _hook
    logging.info("=== PartsPack start (frozen=%s) ===",
                 getattr(sys, "frozen", False))


def _report_fatal(title, message):
    """error window on windows"""
    logging.error("%s\n%s", title, message)
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        except Exception:
            pass


_setup_logging()

_MISSING = []
for _mod, _pip in (("PySide6", "PySide6"), ("pydantic", "pydantic"),
                   ("build123d", "build123d"), ("shapely", "shapely")):
    try:
        __import__(_mod)
    except ImportError:
        import traceback
        _MISSING.append((_pip, traceback.format_exc()))

if _MISSING:
    _detail = "\n\n".join("=== %s ===\n%s" % (name, tb)
                          for name, tb in _MISSING)
    _report_fatal("Parts Packing Generator dependency import failed",
                  "These imports failed:\n\n" + _detail)
    sys.exit(1)


if __name__ == "__main__":
    try:
        from partspack.gui.app import main
        main()
    except Exception:
        import traceback
        _report_fatal("Parts Packing Generator startup error",
                      traceback.format_exc())
        sys.exit(1)
