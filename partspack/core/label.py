# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Text helpers for engraved/embossed labels + pocket indices.

from __future__ import annotations

LABEL_DEPTH = 0.6


def _make_text(text, font_size):
    """Centred build123d Text sketch, or None if font/text can't render."""
    try:
        from build123d import Text, Align
        return Text(text, font_size=font_size,
                    align=(Align.CENTER, Align.CENTER))
    except Exception:
        return None
