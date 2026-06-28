# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# part library / projects, serialise to .ppproj JSON, atomic writes

from __future__ import annotations

import os
from typing import List

from pydantic import BaseModel, Field

from .params import Params
from .serial import JsonModel

PROJECT_EXT = ".ppproj"


class ProjectEntry(BaseModel):
    """One part: STEP path + Params."""

    model_config = {"validate_assignment": True}

    step_path: str = ""
    label: str = ""
    count: int = 1
    dims: str = ""          # cached "WxHxD mm"
    params: Params = Field(default_factory=Params)

    def name(self) -> str:
        """Label, else filename stem."""
        if self.label.strip():
            return self.label.strip()
        if self.step_path:
            return os.path.splitext(os.path.basename(self.step_path))[0]
        return "part"


class Project(JsonModel):
    """Named drawer: ordered entries + drawer-level Params."""

    model_config = {"validate_assignment": True}

    name: str = "Untitled drawer"
    entries: List[ProjectEntry] = Field(default_factory=list)
    drawer: Params = Field(default_factory=Params)

    def add(self, step_path: str, params: Params, label: str = "",
            count: int = 1, dims: str = "") -> ProjectEntry:
        e = ProjectEntry(step_path=step_path, label=label, count=max(1, count),
                         dims=dims, params=params.model_copy(deep=True))
        self.entries.append(e)
        return e

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            del self.entries[index]

    def duplicate(self, index: int) -> int:
        """Clone entry at index, insert after it."""
        if not (0 <= index < len(self.entries)):
            return -1
        clone = self.entries[index].model_copy(deep=True)
        self.entries.insert(index + 1, clone)
        return index + 1

    def move(self, index: int, delta: int) -> int:
        """Shift entry by delta (-1 up / +1 down)."""
        n = len(self.entries)
        if not (0 <= index < n):
            return index
        j = max(0, min(n - 1, index + delta))
        if j == index:
            return index
        self.entries.insert(j, self.entries.pop(index))
        return j

    def save(self, path: str) -> None:
        if not path.lower().endswith(PROJECT_EXT):
            path += PROJECT_EXT
        super().save(path)
