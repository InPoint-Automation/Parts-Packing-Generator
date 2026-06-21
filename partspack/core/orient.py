# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Orientation, tilt, capture frame, lowest-point.
# Chain: x_W = T · R_tilt · R_orient · x_P.

from __future__ import annotations

import numpy as np

_AXIS_VEC = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0), "Z": (0.0, 0.0, 1.0)}


def rotation_a_to_b(a, b):
    """Shortest-arc rotation matrix mapping a -> b."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.isclose(c, 1.0):
        return np.eye(3)
    if np.isclose(c, -1.0):
        ortho = np.array([1.0, 0.0, 0.0])
        if abs(a[0]) > 0.9:
            ortho = np.array([0.0, 1.0, 0.0])
        axis = np.cross(a, ortho)
        axis = axis / np.linalg.norm(axis)
        return _rodrigues(axis, np.pi)
    s = np.linalg.norm(v)
    axis = v / s
    angle = np.arctan2(s, c)
    return _rodrigues(axis, angle)


def _rodrigues(axis, angle):
    x, y, z = axis
    K = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)


def matrix_to_axis_angle(R):
    """3x3 rotation matrix -> (axis, angle degrees)."""
    R = np.asarray(R, dtype=float)
    cos_t = (np.trace(R) - 1.0) / 2.0
    cos_t = max(-1.0, min(1.0, cos_t))
    angle = np.arccos(cos_t)
    if np.isclose(angle, 0.0):
        return (0.0, 0.0, 1.0), 0.0
    if np.isclose(angle, np.pi):
        M = (R + np.eye(3)) / 2.0
        k = int(np.argmax(np.diag(M)))
        axis = M[:, k] / np.sqrt(M[k, k])
        axis = axis / np.linalg.norm(axis)
        return tuple(float(v) for v in axis), float(np.degrees(angle))
    axis = np.array([R[2, 1] - R[1, 2],
                     R[0, 2] - R[2, 0],
                     R[1, 0] - R[0, 1]]) / (2.0 * np.sin(angle))
    axis = axis / np.linalg.norm(axis)
    return tuple(float(v) for v in axis), float(np.degrees(angle))


def _loc_from_matrix(R):
    from build123d import Location
    axis, deg = matrix_to_axis_angle(R)
    return Location((0.0, 0.0, 0.0), axis, deg)


def seating_direction(params):
    """Part-frame 'down into tray' unit vector."""
    if str(params.seating) in ("face", "plane") and params.seating_normal:
        v = np.asarray(params.seating_normal, dtype=float)
        n = np.linalg.norm(v)
        if n > 1e-9:
            v = v / n
            return -v if params.flip else v
    v = np.array(_AXIS_VEC[str(params.seating_axis)], dtype=float)
    if params.flip:
        v = -v
    return v


def plane_down_vector(points, part=None):
    """Down vector for three-point plane seating; None if collinear."""
    p = [np.asarray(q, dtype=float) for q in list(points)[:3]]
    if len(p) < 3:
        return None
    n = np.cross(p[1] - p[0], p[2] - p[0])
    ln = float(np.linalg.norm(n))
    if ln < 1e-9:
        return None
    n = n / ln
    centroid = None
    if part is not None:
        try:
            bb = part.bounding_box(optimal=True)
            centroid = np.array([(bb.min.X + bb.max.X) / 2.0,
                                 (bb.min.Y + bb.max.Y) / 2.0,
                                 (bb.min.Z + bb.max.Z) / 2.0])
        except Exception:
            centroid = None
    if centroid is not None and np.dot(n, p[0] - centroid) < 0:
        n = -n
    return tuple(float(v) for v in n)


def face_down_vector(face):
    """Down vector for a picked face; None if unreadable."""
    try:
        if face.is_planar:
            n = face.normal_at()
            return (float(n.X), float(n.Y), float(n.Z))
    except Exception:
        pass
    ax = _surface_axis(face)
    if ax is not None:
        return ax
    try:
        n = face.normal_at()
        return (float(n.X), float(n.Y), float(n.Z))
    except Exception:
        return None


def _surface_axis(face):
    """Cylinder/cone face axis; None otherwise."""
    try:
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Cone
        ad = BRepAdaptor_Surface(face.wrapped)
        t = ad.GetType()
        if t == GeomAbs_Cylinder:
            d = ad.Cylinder().Axis().Direction()
        elif t == GeomAbs_Cone:
            d = ad.Cone().Axis().Direction()
        else:
            return None
        return (d.X(), d.Y(), d.Z())
    except Exception:
        return None


def orient_solid(part, params):
    """Apply R_orient, R_tilt, T -> (oriented_solid, info)."""
    from build123d import Location, Pos, Compound

    R_orient = rotation_a_to_b(seating_direction(params), (0.0, 0.0, -1.0))
    loc = _loc_from_matrix(R_orient)
    R_combined = np.asarray(R_orient, dtype=float)

    # Mode B: part un-tilted here; lean applied to cavity later. Mode A leans now.
    mode_b = bool(params.tilt_deg) and str(params.tilt_mode) == "B"
    if params.tilt_deg and not mode_b:
        tilt_axis = _AXIS_VEC[str(params.tilt_axis)]
        loc = Location((0.0, 0.0, 0.0), tilt_axis, float(params.tilt_deg)) * loc
        R_tilt = _rodrigues(np.asarray(tilt_axis, dtype=float),
                            np.radians(float(params.tilt_deg)))
        R_combined = R_tilt @ R_combined

    step1 = loc * part

    # optimal=False: optimal meshes whole solid then we tessellate AGAIN -> double meshing.
    bb = step1.bounding_box(optimal=False)
    dx = -(bb.min.X + bb.max.X) / 2.0
    dy = -(bb.min.Y + bb.max.Y) / 2.0
    dz = -bb.min.Z
    oriented = Pos(dx, dy, dz) * step1

    to_oriented = np.eye(4)
    to_oriented[:3, :3] = R_combined
    to_oriented[:3, 3] = (dx, dy, dz)
    to_part = np.linalg.inv(to_oriented)

    # .solids() bakes wrapper Location (intersect/section ignore it).
    oriented = Compound(oriented.solids())

    return oriented, {"z_min": 0.0,
                      "z_top": float(bb.max.Z - bb.min.Z),
                      "world_z_offset": float(params.bottom_margin),
                      "band_base": 0.0,
                      "tilt_mode_b": mode_b,
                      "to_oriented": to_oriented,
                      "to_part": to_part}


def lowest_point_z(oriented_solid) -> float:
    """Bounding-box min along extraction direction."""
    return oriented_solid.bounding_box(optimal=True).min.Z
