# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# App-level config: UI prefs, recents in ~/.partspack.json

import copy
import json
import os
import sys

from .serial import atomic_write_text

CFG_PATH = os.path.join(os.path.expanduser("~"), ".partspack.json")

CFG_DEFAULT = {
    "icon_color": "#1F3864",
    "ui_scale": 0,             # 0 = auto from DPI
    "last_dir": "",
    "recent": [],
    "last_preset": "",
    "bed_x": 256.0,
    "bed_y": 256.0,
    "show_gizmo": True,
}


def load_cfg():
    cfg = copy.deepcopy(CFG_DEFAULT)
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return cfg
    except Exception as e:
        print("partspack: config load failed (%s); using defaults" % e,
              file=sys.stderr)
        return cfg
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def save_cfg(cfg):
    # atomic so crash mid-save can't corrupt config
    try:
        atomic_write_text(CFG_PATH, json.dumps(cfg, indent=1), fsync=False)
    except Exception as e:
        print("partspack: config save failed (%s)" % e, file=sys.stderr)
