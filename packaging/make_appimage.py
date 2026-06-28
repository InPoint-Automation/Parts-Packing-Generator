#!/usr/bin/env python3
# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Wrap Linux standalone build (bin/<App>.dist) into .AppImage.
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "bin"
CACHE = REPO / ".cache"
ARCH = os.environ.get("ARCH", "x86_64")

CATEGORIES = "Graphics;Engineering;"
ICON_SRC = REPO / "img" / "PartsPack.png"
APP_ID = "com.inpointautomation.PartsPack"
METAINFO_SRC = REPO / "packaging" / f"{APP_ID}.metainfo.xml"

APPIMAGETOOL_URL = (
    "https://github.com/AppImage/appimagetool/releases/download/continuous/"
    f"appimagetool-{ARCH}.AppImage"
)


def _meta() -> dict:
    txt = (REPO / "partspack" / "__init__.py").read_text(encoding="utf-8")

    def grab(key, default):
        m = re.search(r'^%s\s*=\s*"([^"]*)"' % key, txt, re.MULTILINE)
        return m.group(1) if m else default

    return {
        "name": grab("APP_NAME", "Parts Packing Generator"),
        "version": grab("__version__", "0.1.0"),
    }


def _appimagetool() -> Path:
    CACHE.mkdir(exist_ok=True)
    tool = CACHE / f"appimagetool-{ARCH}.AppImage"
    if not tool.exists():
        print(f"Fetching appimagetool -> {tool}")
        urllib.request.urlretrieve(APPIMAGETOOL_URL, tool)
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return tool


def main() -> int:
    dists = sorted(BIN.glob("*.dist"))
    if not dists:
        print("ERROR: no bin/*.dist found. Run build.py first (Linux standalone).")
        return 1
    src = dists[0]
    binname = src.stem
    meta = _meta()
    display = meta["name"]

    appdir = BIN / f"{binname}.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    (appdir / "usr" / "bin").mkdir(parents=True)

    shutil.copytree(src, appdir / "usr" / "bin", dirs_exist_ok=True)

    if ICON_SRC.exists():
        shutil.copy(ICON_SRC, appdir / f"{binname}.png")
    else:
        print(f"WARNING: {ICON_SRC} missing, AppImage will have no icon.")

    apprun = appdir / "AppRun"
    apprun.write_text(
        "#!/bin/sh\n"
        'HERE="$(dirname "$(readlink -f "${0}")")"\n'
        f'exec "${{HERE}}/usr/bin/{binname}" "$@"\n'
    )
    apprun.chmod(0o755)

    (appdir / f"{APP_ID}.desktop").write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={display}\n"
        f"Exec={binname}\n"
        f"Icon={binname}\n"
        f"Categories={CATEGORIES}\n"
        "Terminal=false\n"
    )

    if METAINFO_SRC.exists():
        meta_dir = appdir / "usr" / "share" / "metainfo"
        meta_dir.mkdir(parents=True, exist_ok=True)
        rdate = os.environ.get("RELEASE_DATE") or date.today().isoformat()
        rel = (
            "  <releases>\n"
            f'    <release version="{meta["version"]}" date="{rdate}"/>\n'
            "  </releases>\n"
        )
        xml = METAINFO_SRC.read_text(encoding="utf-8").replace(
            "</component>", rel + "</component>")
        (meta_dir / METAINFO_SRC.name).write_text(xml, encoding="utf-8")
    else:
        print(f"WARNING: {METAINFO_SRC} missing, AppImage will have no AppStream data.")

    out = BIN / f"{binname}-{ARCH}.AppImage"
    if out.exists():
        out.unlink()

    tool = _appimagetool()
    env = {**os.environ, "ARCH": ARCH}
    cmd = [str(tool), "--appimage-extract-and-run", "--no-appstream",
           str(appdir), str(out)]
    print("Running:", " ".join(cmd))
    rc = subprocess.run(cmd, env=env).returncode
    if rc != 0:
        print("appimagetool FAILED.")
        return rc

    out.chmod(out.stat().st_mode | stat.S_IEXEC)
    print(f"\nAppImage OK: {out}")
    print("Test it RAN, not just built:  ./%s" % out.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
