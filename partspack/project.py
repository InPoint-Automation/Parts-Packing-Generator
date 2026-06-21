# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Part library / projects. Serialises to `.ppproj` JSON. Atomic writes.

from __future__ import annotations

import os
import tempfile
from typing import List

from pydantic import BaseModel, Field

from .params import Params

PROJECT_EXT = ".ppproj"


class ProjectEntry(BaseModel):
    """One part: STEP path + Params."""

    model_config = {"validate_assignment": True}

    step_path: str = ""
    label: str = ""
    count: int = 1
    params: Params = Field(default_factory=Params)

    def name(self) -> str:
        """Display name: label, else filename stem."""
        if self.label.strip():
            return self.label.strip()
        if self.step_path:
            return os.path.splitext(os.path.basename(self.step_path))[0]
        return "part"


class Project(BaseModel):
    """Named drawer: ordered entries + drawer-level Params."""

    model_config = {"validate_assignment": True}

    name: str = "Untitled drawer"
    entries: List[ProjectEntry] = Field(default_factory=list)
    drawer: Params = Field(default_factory=Params)

    def add(self, step_path: str, params: Params, label: str = "",
            count: int = 1) -> ProjectEntry:
        e = ProjectEntry(step_path=step_path, label=label, count=max(1, count),
                         params=params.model_copy(deep=True))
        self.entries.append(e)
        return e

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            del self.entries[index]

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    def save(self, path: str) -> None:
        if not path.lower().endswith(PROJECT_EXT):
            path += PROJECT_EXT
        d = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(self.to_json())
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    @classmethod
    def from_json(cls, text: str) -> "Project":
        return cls.model_validate_json(text)

    @classmethod
    def load(cls, path: str) -> "Project":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())
