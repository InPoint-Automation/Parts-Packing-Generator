# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# STEP import + STL/3MF/STEP export. Carved trays are meshes (STL/3MF only).

from __future__ import annotations


def import_step(path: str):
    """Load STEP into build123d B-rep."""
    from build123d import import_step as _import_step
    return _import_step(path)


def _is_mesh(shape) -> bool:
    """True for manifold3d.Manifold."""
    return hasattr(shape, "to_mesh")


def _manifold_arrays(man):
    """manifold3d.Manifold -> (verts Nx3 float64, tris Mx3 int64)."""
    import numpy as np
    mesh = man.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    tris = np.asarray(mesh.tri_verts, dtype=np.int64)
    return verts, tris


def _write_binary_stl(path: str, verts, tris) -> None:
    """Binary STL from triangle arrays."""
    import numpy as np
    tri = np.asarray(verts)[np.asarray(tris)]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.where(ln == 0.0, 1.0, ln)
    m = len(tri)
    rec = np.zeros(m, dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"),
                                      ("attr", "<u2")]))
    rec["n"] = n.astype("<f4")
    rec["v"] = tri.reshape(m, 9).astype("<f4")
    with open(path, "wb") as f:
        f.write(b"PartsPack carve-direct".ljust(80, b"\0"))
        f.write(np.uint32(m).tobytes())
        f.write(rec.tobytes())


def export_stl(shape, path: str, tess_linear: float = 0.05,
               tess_angular: float = 0.5) -> None:
    """STL export (mesh direct, else B-rep tessellation)."""
    if _is_mesh(shape):
        verts, tris = _manifold_arrays(shape)
        _write_binary_stl(path, verts, tris)
        return
    from build123d import export_stl as _export_stl
    _export_stl(shape, path, tolerance=tess_linear, angular_tolerance=tess_angular)


def export_step(shape, path: str) -> None:
    """Archival STEP export (B-rep only)."""
    if _is_mesh(shape):
        raise ValueError(
            "STEP export needs a B-rep solid, but carve-direct trays are meshes. "
            "Export as STL (native for carved trays).")
    from build123d import export_step as _export_step
    _export_step(shape, path)


def _write_3mf_mesh(path: str, verts, tris) -> None:
    """3MF from triangle arrays via lib3mf."""
    import os
    import ctypes
    from lib3mf import Lib3MF
    wrapper = Lib3MF.Wrapper(os.path.join(os.path.dirname(Lib3MF.__file__),
                                          "lib3mf"))
    model = wrapper.CreateModel()
    model.SetUnit(Lib3MF.ModelUnit.MilliMeter)
    mesh = model.AddMeshObject()
    cf3, cu3 = ctypes.c_float * 3, ctypes.c_uint * 3
    positions = [Lib3MF.Position(cf3(float(x), float(y), float(z)))
                 for x, y, z in verts]
    triangles = [Lib3MF.Triangle(cu3(int(a), int(b), int(c)))
                 for a, b, c in tris]
    mesh.SetGeometry(positions, triangles)
    model.AddBuildItem(mesh, wrapper.GetIdentityTransform())
    model.QueryWriter("3mf").WriteToFile(path)


def export_3mf(shape, path: str, tess_linear: float = 0.05,
               tess_angular: float = 0.5) -> None:
    """3MF export (mesh direct via lib3mf, else Mesher)."""
    if _is_mesh(shape):
        verts, tris = _manifold_arrays(shape)
        _write_3mf_mesh(path, verts, tris)
        return
    from build123d import Mesher
    m = Mesher()
    m.add_shape(shape, linear_deflection=tess_linear,
                angular_deflection=tess_angular)
    m.write(path)


def export(shape, path: str, fmt: str, tess_linear: float = 0.05,
           tess_angular: float = 0.5) -> None:
    """Dispatch on format string ('3mf' | 'stl' | 'step')."""
    fmt = fmt.lower()
    if fmt == "3mf":
        export_3mf(shape, path, tess_linear, tess_angular)
    elif fmt == "stl":
        export_stl(shape, path, tess_linear, tess_angular)
    elif fmt == "step":
        export_step(shape, path)
    else:
        raise ValueError("unknown export format: %r" % fmt)
