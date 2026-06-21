# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Headless CLI: STEP + params.json -> tray. Same pipeline entry as GUI.

from __future__ import annotations

import argparse
import os
import sys

from .params import Params
from .core import pipeline, io


def build_parser():
    p = argparse.ArgumentParser(
        prog="partspack",
        description="Generate a 3D-printable nesting tray from a STEP part.")
    p.add_argument("step", help="input STEP file")
    p.add_argument("-p", "--params", help="params preset JSON (defaults if omitted)")
    p.add_argument("-o", "--out", help="output path (extension sets format)")
    p.add_argument("-f", "--format", default=None,
                   choices=["3mf", "stl", "step"],
                   help="export format (overrides --out extension / preset)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    params = Params.load(args.params) if args.params else Params()

    fmt = args.format or (
        os.path.splitext(args.out)[1].lstrip(".").lower() if args.out else None
    ) or params.export_format
    out = args.out or (os.path.splitext(args.step)[0] + "_tray." + fmt)

    try:
        result = pipeline.build(params, args.step)
    except NotImplementedError:
        sys.exit("partspack: pipeline not implemented yet (Phase 1).")

    if not result.trays:
        sys.exit("partspack: build produced no trays.")
    io.export(result.trays[0], out, fmt,
              params.tess_linear, params.tess_angular)
    print("wrote %s" % out)
    for w in result.warnings:
        print("warning:", w, file=sys.stderr)


if __name__ == "__main__":
    main()
