# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Shared serialization: atomic write + JSON model base.

from __future__ import annotations

import os
import tempfile

from pydantic import BaseModel


def atomic_write_text(path: str, text: str, fsync: bool = True) -> None:
    """Crash-safe write via temp + os.replace."""
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            if fsync:
                f.flush()
                os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


class JsonModel(BaseModel):
    """Pydantic model with atomic JSON file load/save."""

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    def save(self, path: str) -> None:
        atomic_write_text(path, self.to_json())

    @classmethod
    def from_json(cls, text: str):
        return cls.model_validate_json(text)

    @classmethod
    def load(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())
