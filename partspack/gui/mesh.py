# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.
#
# build123d shape -> pyvista PolyData (display only).

from __future__ import annotations


def tessellate_for_display(result, what):
    # tessellate build shapes to PolyData by role; worker thread
    import sys

    def _tess(role, shape):
        try:
            if hasattr(shape, "to_mesh"):
                from ..core import meshbool
                pd = meshbool.to_polydata(shape)
            elif hasattr(shape, "n_points"):
                pd = shape
            else:
                pd = shape_to_polydata(shape, 0.1, 0.5)
            if pd is None:
                sys.stderr.write("[display] %s tessellated to None\n" % role)
            else:
                sys.stderr.write("[display] %s mesh: %d pts %d cells\n"
                                 % (role, pd.n_points, pd.n_cells))
            return pd
        except Exception as e:
            sys.stderr.write("[display] %s tessellation FAILED: %r\n" % (role, e))
            return None

    out = {}
    if what == "Ghost":
        cav = getattr(result, "cavity", None)
        if cav is not None:
            out["cavity"] = _tess("cavity", cav)
        cav_top = getattr(result, "cavity_top", None)
        if cav_top is not None:
            out["cavity_top"] = _tess("cavity_top", cav_top)
    elif what == "Batch":
        for _entry, r in result:
            if getattr(r, "trays", None):
                out["tray"] = _tess("tray", r.trays[0])
                break
    else:
        trays = getattr(result, "trays", None)
        sys.stderr.write("[display] %s: result has %d tray(s)\n"
                         % (what, len(trays) if trays else 0))
        if trays and len(trays) == 1:
            out["tray"] = _tess("tray", trays[0])
        elif trays:
            out["tray"] = _tess_layout([_tess("tray", t) for t in trays])
    return out


def _tess_layout(pds, gap=10.0):
    # merge PolyData side by side along +X
    pds = [pd for pd in pds if pd is not None]
    if not pds:
        return None
    if len(pds) == 1:
        return pds[0]
    import pyvista as pv
    placed, x = [], 0.0
    for pd in pds:
        pd = pd.copy()
        xmin, xmax = pd.bounds[0], pd.bounds[1]
        pd.translate((x - xmin, 0.0, 0.0), inplace=True)
        x += (xmax - xmin) + gap
        placed.append(pd)
    return pv.merge(placed)


def shape_to_polydata(shape, linear: float = 0.1, angular: float = 0.5):
    # tessellate build123d shape; per-face fallback on failure
    import numpy as np
    import pyvista as pv

    try:
        verts, tris = shape.tessellate(tolerance=linear, angular_tolerance=angular)
    except Exception:
        return _per_face_polydata(shape, linear, angular)
    if not verts or not tris:
        return _per_face_polydata(shape, linear, angular)
    from ..core.meshbool import tris_to_vtk_faces
    pts = np.array([tuple(v) for v in verts], dtype=float)
    return pv.PolyData(pts, tris_to_vtk_faces(tris))


def _per_face_polydata(shape, linear: float, angular: float):
    # mesh each B-rep face alone, stitch survivors
    import numpy as np
    import pyvista as pv

    try:
        faces_list = list(shape.faces())
    except Exception:
        return None

    verts, tris, offset = [], [], 0
    for face in faces_list:
        try:
            v, ts = face.tessellate(tolerance=linear, angular_tolerance=angular)
        except Exception:
            continue
        if not v or not ts:
            continue
        verts.extend(tuple(p) for p in v)
        for (a, b, c) in ts:
            tris.append((3, a + offset, b + offset, c + offset))
        offset += len(v)

    if not verts or not tris:
        return None
    return pv.PolyData(np.array(verts, dtype=float),
                       np.array(tris, dtype=np.int64).ravel())


def shape_to_polydata_faces(shape, linear: float = 0.3, angular: float = 0.5):
    # per-face tessellate, tag triangles with face_id
    import numpy as np
    import pyvista as pv

    try:
        faces = list(shape.faces())
    except Exception:
        return None, []

    verts, tris, fids = [], [], []
    offset = 0
    for fi, face in enumerate(faces):
        try:
            v, ts = face.tessellate(tolerance=linear, angular_tolerance=angular)
        except Exception:
            continue
        if not v or not ts:
            continue
        verts.extend(tuple(p) for p in v)
        for (a, b, c) in ts:
            tris.append((3, a + offset, b + offset, c + offset))
            fids.append(fi)
        offset += len(v)

    if not verts or not tris:
        return None, faces
    mesh = pv.PolyData(np.array(verts, dtype=float),
                       np.array(tris, dtype=np.int64).ravel())
    mesh.cell_data["face_id"] = np.array(fids, dtype=np.int64)
    return mesh, faces
