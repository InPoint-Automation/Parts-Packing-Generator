#!/usr/bin/env python3
# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# Create throwaway .build-venv with lean per-OS deps for Nuitka bundle.
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import venv
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OS = platform.system()
VENV = REPO / ".build-venv"
WHEELS = REPO / "packaging" / "wheels"

REQ_FILE = {
    "Linux": "requirements-build-linux.txt",
    "Windows": "requirements-build-windows.txt",
    "Darwin": "requirements-build-macos.txt",
}

# glm headers to compile pydelatin on Windows
GLM_VER = "1.0.1"
GLM_URL = (f"https://github.com/g-truc/glm/releases/download/"
           f"{GLM_VER}/glm-{GLM_VER}-light.zip")
GLM_DIR = REPO / "packaging" / ".glm"


def venv_python() -> str:
    sub = "Scripts" if OS == "Windows" else "bin"
    exe = "python.exe" if OS == "Windows" else "python"
    return str(VENV / sub / exe)


def run(*cmd: str, env: dict | None = None) -> None:
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def _ensure_glm() -> Path:
    """Download/extract glm release, return include root."""
    header = GLM_DIR / "glm" / "glm.hpp"
    if not header.exists():
        print(f"=== Downloading glm {GLM_VER} ===")
        GLM_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = GLM_DIR / "glm.zip"
        urllib.request.urlretrieve(GLM_URL, zip_path)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(GLM_DIR)
    if not header.exists():
        raise SystemExit(f"glm headers missing at {header}")
    return GLM_DIR


def _build_pydelatin_wheel(py: str) -> None:
    """Build pydelatin wheel vs glm into packaging/wheels (Windows)."""
    WHEELS.mkdir(parents=True, exist_ok=True)
    if list(WHEELS.glob("pydelatin-*.whl")):
        print("=== Reusing cached pydelatin wheel ===")
        return
    print("=== Building pydelatin wheel (one time, vs glm) ===")
    glm_inc = _ensure_glm()
    env = dict(os.environ)
    env["INCLUDE"] = str(glm_inc) + os.pathsep + env.get("INCLUDE", "")
    run(py, "-m", "pip", "wheel", "pydelatin",
        "--no-deps", "--no-binary", "pydelatin",
        "--wheel-dir", str(WHEELS), env=env)


def main() -> int:
    if OS not in REQ_FILE:
        print(f"Unsupported OS: {OS}")
        return 1
    req = REPO / REQ_FILE[OS]
    if not req.exists():
        print(f"Missing requirements file: {req}")
        return 1

    marker = VENV / ("Scripts" if OS == "Windows" else "bin")
    if marker.exists():
        print(f"=== Reusing existing build venv: {VENV} ===")
    else:
        print(f"=== Creating build venv: {VENV} ===")
        venv.create(VENV, with_pip=True)

    py = venv_python()
    run(py, "-m", "pip", "install", "--upgrade", "pip", "wheel")

    install = [py, "-m", "pip", "install", "-r", str(req)]
    if OS == "Windows":
        _build_pydelatin_wheel(py)
        install += ["--find-links", str(WHEELS)]   # resolve pydelatin
    run(*install)
    run(py, "-m", "pip", "install", "nuitka")

    print("\n=== build venv ready ===")
    print("Build with:")
    print(f"  {py} packaging/build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
