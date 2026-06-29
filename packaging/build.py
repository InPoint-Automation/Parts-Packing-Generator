#!/usr/bin/env python3
# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Cross-platform Nuitka build. Run from repo root: python packaging/build.py
from __future__ import annotations
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# app config
APP = {
    "name": "PartsPack",
    "entry": "PartsPack.py",
    "icon": "img/PartsPack.png",
    "include_packages": [
        "OCP", "ocpsvg", "ocp_gordon", "build123d", "lib3mf",
        "vtkmodules", "pyvista", "pyvistaqt",
        "scipy._external.array_api_compat",
        "partspack",
    ],
    "include_package_data": [
        "pyvista", "vtkmodules", "OCP", "build123d", "skimage",
    ],

    "include_modules": [
        "vtkmodules.all",
        "vtkmodules.util.numpy_support",
        "vtkmodules.qt.QVTKRenderWindowInteractor",
    ],
    "data_dirs": [
        ("partspack/gui/icons_svg", "partspack/gui/icons_svg"),
    ],
    "data_files": [],
}

REPO = Path(__file__).resolve().parent.parent
BIN = REPO / "bin"       # build output
OS = platform.system()


def _meta() -> dict:
    """Read APP_NAME / ORG / __version__ from __init__.py by regex, no import."""
    txt = (REPO / "partspack" / "__init__.py").read_text(encoding="utf-8")

    def grab(key, default):
        m = re.search(r'^%s\s*=\s*"([^"]*)"' % key, txt, re.MULTILINE)
        return m.group(1) if m else default

    return {
        "name": grab("APP_NAME", "Parts Packing Generator"),
        "org": grab("ORG", "InPoint Automation Sp. z o.o."),
        "version": grab("__version__", "0.1.0"),
    }


META = _meta()


def _win_versions() -> str:
    return ".".join((META["version"].split(".") + ["0", "0", "0", "0"])[:4])

sys.path.insert(0, str(REPO))


def _installed(name: str) -> bool:
    import importlib.util
    top = name.split(".")[0]
    try:
        return importlib.util.find_spec(top) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def _present(names: list[str], what: str) -> list[str]:
    keep, skip = [], []
    for n in names:
        (keep if _installed(n) else skip).append(n)
    if skip:
        print(f"NOTE: skipping {what} not installed in this env: "
              + ", ".join(skip))
    return keep


def flags() -> list[str]:
    import os
    f = [
        sys.executable, "-m", "nuitka",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        f"--output-dir={BIN}",
        f"--output-filename={APP['name']}",
        "--show-progress",
        "--show-modules",
    ]

    if OS in ("Linux", "Windows") and os.environ.get("PARTSPACK_CLANG", "1") not in ("0", "false"):
        f.append("--clang")
    if os.environ.get("PARTSPACK_LOWMEM", "0") in ("1", "true"):
        f.append("--low-memory")                       # splits big units, jobs=1
    else:
        f.append(f"--jobs={os.environ.get('PARTSPACK_JOBS', '6')}")
    f.append(f"--lto={os.environ.get('PARTSPACK_LTO', 'no')}")
    if OS == "Linux":
        f.append("--static-libpython=no")

    f += [
        "--noinclude-pytest-mode=nofollow",
        "--noinclude-setuptools-mode=nofollow",
        "--noinclude-unittest-mode=nofollow",
    ]
    for pkg in ("jedi", "parso", "rich", "cyclopts"):
        f.append(f"--nofollow-import-to={pkg}")

    for pkg in _present(APP["include_packages"], "include_packages"):
        f.append(f"--include-package={pkg}")
    for pkg in _present(APP["include_package_data"], "include_package_data"):
        f.append(f"--include-package-data={pkg}")
    for mod in _present(APP["include_modules"], "include_modules"):
        f.append(f"--include-module={mod}")
    for src, dest in APP["data_dirs"]:
        f.append(f"--include-data-dir={REPO / src}={dest}")
    for src, dest in APP["data_files"]:
        f.append(f"--include-data-file={REPO / src}={dest}")

    if OS == "Windows":
        f.append("--onefile")
        f.append("--windows-console-mode=disable")
        v = _win_versions()
        f += [
            f"--company-name={META['org']}",
            f"--product-name={META['name']}",
            f"--file-version={v}",
            f"--product-version={v}",
            f"--file-description={META['name']} - parametric 3D-printable nesting trays",
        ]
        if APP["icon"] and (REPO / APP["icon"]).exists():
            f.append(f"--windows-icon-from-ico={REPO / APP['icon']}")
    elif OS == "Linux":
        f.append("--standalone")
    elif OS == "Darwin":
        f.append("--macos-create-app-bundle")
        f.append(f"--macos-app-name={APP['name']}")
        if APP["icon"] and (REPO / APP["icon"]).exists():
            f.append(f"--macos-app-icon={REPO / APP['icon']}")

    f.append(str(REPO / APP["entry"]))
    return f


def main() -> int:
    # clean output
    name = APP["name"]
    for stale in (
        BIN / f"{name}.exe", BIN / f"{name}.bin", BIN / f"{name}.app",
        BIN / f"{name}.dist", BIN / f"{name}.build",
        BIN / f"{name}.onefile-build",
    ):
        if stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)
        elif stale.exists():
            stale.unlink()

    cmd = flags()
    print("Running Nuitka:\n  " + " \\\n  ".join(cmd) + "\n")

    result = subprocess.run(cmd, cwd=REPO)
    if result.returncode != 0:
        print("\nBUILD FAILED. Read the last lines for the missing "
              "module/DLL.")
        return result.returncode

    print(f"\nBuild OK. Output in: {BIN}")
    if OS == "Linux":
        print("Linux standalone in bin/PartsPack.dist. Wrap to AppImage: "
              "python packaging/make_appimage.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())