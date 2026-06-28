# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# shared helpers for MainWindow mixin split

from __future__ import annotations


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]
