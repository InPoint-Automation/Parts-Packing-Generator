#!/usr/bin/env python3
# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Launch the GUI. Deps: pip install -r requirements.txt

import os
import sys

# Wayland fix
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

_MISSING = []
for _mod, _pip in (("PySide6", "PySide6"), ("pydantic", "pydantic"),
                   ("build123d", "build123d"), ("shapely", "shapely")):
    try:
        __import__(_mod)
    except ImportError:
        _MISSING.append(_pip)

if _MISSING:
    sys.exit("Missing deps: %s\n  pip install -r requirements.txt"
             % " ".join(_MISSING))

from partspack.gui.app import main

if __name__ == "__main__":
    main()
