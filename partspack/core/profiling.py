# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# per-stage profiler, gated by PARTSPACK_PROFILE (default on)

from __future__ import annotations

import os
import sys
import threading
import time
from contextlib import contextmanager


def enabled() -> bool:
    return os.environ.get("PARTSPACK_PROFILE", "1").strip().lower() \
        not in ("0", "false", "no", "off", "")


# active Profiler per thread, shared via module-level stage()
_local = threading.local()


def current():
    return getattr(_local, "prof", None)


def _set_current(prof):
    _local.prof = prof


@contextmanager
def stage(label: str):
    """Time block against active Profiler, no-op if inactive."""
    p = current()
    if p is None or not p.active:
        yield
        return
    with p.stage(label):
        yield


# optional sink, lets harness capture timings without scraping stdout
_sink = None


def set_sink(cb):
    """Install dump() sink, None clears, returns previous."""
    global _sink
    prev = _sink
    _sink = cb
    return prev


class Profiler:
    """Collect (label, seconds) rows, print table at dump()."""

    def __init__(self, title: str, active: bool = True):
        self.title = title
        self.active = bool(active) and enabled()
        self.rows = []
        self._t0 = time.perf_counter()
        if self.active:
            _set_current(self)

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

    def dump(self):
        if _sink is not None:
            try:
                _sink(self.title, list(self.rows),
                      time.perf_counter() - self._t0)
            except Exception:
                pass
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
    """Time block, print one line, for one-off costs."""
    if not enabled():
        yield
        return
    t = time.perf_counter()
    try:
        yield
    finally:
        sys.stdout.write("[profile] %s: %.3f s\n" % (label, time.perf_counter() - t))
        sys.stdout.flush()
