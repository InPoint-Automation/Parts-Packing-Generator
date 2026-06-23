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
    "PySide6.QtSvg",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "vtkmodules.all",
    "vtkmodules.util.numpy_support",
    "vtkmodules.qt.QVTKRenderWindowInteractor",
    "shapely",
    "pydantic",
]

from PyInstaller.utils.hooks import (collect_all, copy_metadata, collect_submodules)

for _pkg in (
    # 3D / CAD coreR
    "OCP", "build123d", "ocpsvg", "ocp_gordon",
    "vtkmodules", "vtk", "pyvista", "pyvistaqt",
    # mesh / geometry
    "manifold3d", "trimesh", "pydelatin", "shapely", "lib3mf",
    # scientific stack (build123d pulls these transitively; recent scipy
    # vendors array_api_compat submodules PyInstaller's stale hook misses)
    "scipy", "numpy", "skimage", "sklearn", "sympy", "networkx",
    "imageio", "tifffile", "lazy_loader",
    # misc deps that ship data/native bits or self-inspect
    "ezdxf", "svgpathtools", "svgelements", "anytree", "trianglesolver",
    "webcolors", "requests", "rich", "cyclopts", "pydantic", "IPython",
):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception as _e:
        print("PartsPack.spec: collect_all(%s) skipped: %s" % (_pkg, _e))

for _pkg in ("OCP", "build123d", "ocpsvg", "ocp_gordon"):
    try:
        hiddenimports += collect_submodules(_pkg)
    except Exception as _e:
        print("PartsPack.spec: collect_submodules(%s) skipped: %s" % (_pkg, _e))

_META = [
    # app-level deps
    "build123d", "pyvista", "pyvistaqt", "shapely", "pydantic",
    "manifold3d", "scikit-image", "pydelatin", "trimesh", "numpy",
    # build123d's dependency chain (dist names != import names for several)
    "cadquery-ocp-novtk", "cadquery-ocp-proxy", "cadquery-ocp",
    "ocp_gordon", "ocpsvg", "lib3mf", "svgpathtools", "svgelements",
    "anytree", "ezdxf", "ipython", "trianglesolver", "sympy", "scipy",
    "scikit-learn", "webcolors", "requests", "typing_extensions",
    # things that frequently self-check versions too
    "vtk", "PySide6", "PySide6_Essentials", "PySide6_Addons", "shiboken6",
    "pydantic_core", "networkx", "imageio", "tifffile", "lazy_loader",
    "rich", "cyclopts",
]
for _pkg in _META:
    try:
        datas += copy_metadata(_pkg)
    except Exception as _e:
        print("PartsPack.spec: copy_metadata(%s) skipped: %s" % (_pkg, _e))

for _pkg in ("build123d", "pyvista", "scikit-image"):
    try:
        datas += copy_metadata(_pkg, recursive=True)
    except Exception as _e:
        print("PartsPack.spec: copy_metadata(%s, recursive) skipped: %s"
              % (_pkg, _e))

import glob, sys

_lib_bin = os.path.join(sys.prefix, "Library", "bin")
for _pat in ("zlib.dll", "libffi*.dll", "ffi.dll", "liblzma.dll",
             "libbz2.dll", "bz2.dll", "libssl*.dll", "libcrypto*.dll"):
    for _dll in glob.glob(os.path.join(_lib_bin, _pat)):
        binaries.append((_dll, "."))
        print("PartsPack.spec: bundling conda DLL", os.path.basename(_dll))

a = Analysis(
    ["PartsPack.py"],
    pathex=[os.path.abspath(".")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PartsPack",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=bool(os.environ.get("PARTSPACK_CONSOLE")),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="packaging/partspack.ico" if os.path.exists(
        "packaging/partspack.ico") else None,
    version="packaging/version_info.txt" if os.path.exists(
        "packaging/version_info.txt") else None,
)
