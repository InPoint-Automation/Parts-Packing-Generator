# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Parts Packing Generator.  Build with:
#     pyinstaller --clean --noconfirm PartsPack.spec

import os

block_cipher = None

datas = [
    ("partspack/gui/icons_svg", "partspack/gui/icons_svg"),
]
binaries = []

# stdlib + third-party modules PyInstaller's static analysis can miss
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",             # SVG icon rendering
    "PySide6.QtOpenGL",          # VTK render window
    "PySide6.QtOpenGLWidgets",   # pyvistaqt QtInteractor embeds this
    "vtkmodules.all",
    "vtkmodules.util.numpy_support",
    "vtkmodules.qt.QVTKRenderWindowInteractor",
    "shapely",
    "pydantic",
]

# Heavy native packages: pull in their data files, binaries and submodules
# wholesale. A lean/partial venv may lack one -> warn, don't kill the build.
from PyInstaller.utils.hooks import collect_all   # noqa: E402

for _pkg in ("OCP", "vtkmodules", "pyvista", "pyvistaqt", "build123d"):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception as _e:
        print("PartsPack.spec: collect_all(%s) skipped: %s" % (_pkg, _e))

a = Analysis(
    ["PartsPack.py"],
    pathex=[os.path.abspath(".")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # trim weight: things Parts Packing Generator never uses
    excludes=["trimesh",          # optional 'trimesh' section backend only
              "pytest", "scipy", "pandas", "matplotlib",
              "PyQt5", "PySide2", "tkinter", "IPython",
              # PySide6 modules never touched
              "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.Qt3DCore", "PySide6.QtWebEngineCore",
              "PySide6.QtMultimedia", "PySide6.QtCharts"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # onedir: binaries go in COLLECT
    name="PartsPack",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # UPX + big native DLLs = slow/fragile; off
    console=False,                  # GUI app: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,           # lets users drag a STEP onto the .exe
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="packaging/partspack.ico" if os.path.exists(
        "packaging/partspack.ico") else None,
    version="packaging/version_info.txt" if os.path.exists(
        "packaging/version_info.txt") else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PartsPack",
)
