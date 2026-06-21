# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Per-stage profiler. Gated by PARTSPACK_PROFILE (default ON).

from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager


def enabled() -> bool:
    return os.environ.get("PARTSPACK_PROFILE", "1").strip().lower() \
        not in ("0", "false", "no", "off", "")


# Active Profiler per thread (for module-level stage()/note()).
_local = threading.local()


def current():
    return getattr(_local, "prof", None)


def _set_current(prof):
    _local.prof = prof


@contextmanager
def stage(label: str):
    """Time a block against active Profiler."""
    p = current()
    if p is None or not p.active:
        yield
        return
    with p.stage(label):
        yield


def note(label: str, secs: float):
    """Record a pre-measured row."""
    p = current()
    if p is not None:
        p.mark(label, secs)


class Profiler:
    """Collects (label, seconds) rows; prints table at dump()."""

    def __init__(self, title: str, active: bool = True):
        self.title = title
        self.active = bool(active) and enabled()
        self.rows = []
        self._t0 = time.perf_counter()
        if self.active:
            _set_current(self)

    @classmethod
    def disabled(cls) -> "Profiler":
        """No-op profiler."""
        return cls("", active=False)

    @contextmanager
    def stage(self, label: str):
        if not self.active:
            yield
            return
        t = time.perf_counter()
        try:
            yield
        finally:
            self.rows.append((label, time.perf_counter() - t))

    def mark(self, label: str, secs: float):
        if self.active:
            self.rows.append((label, float(secs)))

    def dump(self):
        if not self.active:
            return
        total = time.perf_counter() - self._t0
        w = max([len(l) for l, _ in self.rows] + [len("(other/overhead)")])
        out = ["", "=== PROFILE: %s ===" % self.title]
        acc = 0.0
        for label, secs in self.rows:
            acc += secs
            pct = (secs / total * 100.0) if total > 0 else 0.0
            out.append("  %-*s  %9.3f s  %5.1f%%" % (w, label, secs, pct))
        other = total - acc
        if other > 1e-3:
            out.append("  %-*s  %9.3f s  %5.1f%%"
                       % (w, "(other/overhead)", other,
                          other / total * 100.0 if total > 0 else 0.0))
        out.append("  %-*s  %9.3f s  100.0%%" % (w, "TOTAL", total))
        sys.stdout.write("\n".join(out) + "\n")
        sys.stdout.flush()
        if current() is self:
            _set_current(None)


@contextmanager
def timed_print(label: str):
    """Time a block, print one line; for one-off costs."""
    if not enabled():
        yield
        return
    t = time.perf_counter()
    try:
        yield
    finally:
        sys.stdout.write("[profile] %s: %.3f s\n" % (label, time.perf_counter() - t))
        sys.stdout.flush()
