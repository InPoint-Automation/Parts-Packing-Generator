# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Mesh-boolean carve-direct cavity from heightmap, capture frame.

from __future__ import annotations

from collections import OrderedDict

_OVERCUT = 1.0      # overcut above block top; coplanar tops break booleans

# ---- Stage caches (fast rebuild / direct drag) ----
_ORIENT_KEYS = ("seating", "seating_axis", "seating_normal", "flip",
                "tilt_deg", "tilt_axis", "tilt_mode", "tilt_back_wall",
                "hold_height", "bottom_margin")
_CAVITY_KEYS = _ORIENT_KEYS + ("part_clearance", "mouth_chamfer",
                               "capture_quality", "min_internal_feature",
                               "remove_internal_features", "internal_wall_floor")
_CAVITY_CACHE = OrderedDict()
_CAVITY_MAX = 6
_ORIENTED_CACHE = OrderedDict()
_ORIENTED_MAX = 4
_FRAME_KEYS = ("seating", "seating_axis", "seating_normal", "flip",
               "tilt_deg", "tilt_axis", "tilt_mode", "tilt_back_wall")
_GHOST_MARGIN = 8.0
_BLOCK_CACHE = OrderedDict()
_BLOCK_MAX = 8
_CARVED_CACHE = OrderedDict()
_CARVED_MAX = 6
_GHOST_CACHE = OrderedDict()
_GHOST_MAX = 4


def _subkey(params, keys):
    """Hashable value tuple over keys."""
    out = []
    for k in keys:
        v = getattr(params, k, None)
        if isinstance(v, list):
            v = tuple(v)
        out.append(v)
    return tuple(out)


def _oriented_cached(part, params):
    """Cached oriented solid (stable id)."""
    key = (id(part), _subkey(params, _FRAME_KEYS))
    hit = _ORIENTED_CACHE.get(key)
    if hit is not None:
        _ORIENTED_CACHE.move_to_end(key)
        oriented, base_info = hit[1], hit[2]
    else:
        from . import orient
        oriented, base_info = orient.orient_solid(part, params)
        _ORIENTED_CACHE[key] = (part, oriented, base_info)
        while len(_ORIENTED_CACHE) > _ORIENTED_MAX:
            _ORIENTED_CACHE.popitem(last=False)
    info = dict(base_info)
    info["band_base"] = 0.0
    info["world_z_offset"] = float(params.bottom_margin)
    return oriented, info


def _carve_cached(part, params):
    """Cached orient + carve_cavity. Returns (oriented, info, cap)."""
    key = (id(part), _subkey(params, _CAVITY_KEYS))
    hit = _CAVITY_CACHE.get(key)
    if hit is not None:
        _CAVITY_CACHE.move_to_end(key)
        return hit[1], hit[2], hit[3]
    oriented, info = _oriented_cached(part, params)
    cap = carve_cavity(oriented, info, params)
    _CAVITY_CACHE[key] = (part, oriented, info, cap)   # part ref pins id()
    while len(_CAVITY_CACHE) > _CAVITY_MAX:
        _CAVITY_CACHE.popitem(last=False)
    return oriented, info, cap


_GHOST_KEYS = tuple(k for k in _CAVITY_KEYS if k != "hold_height")


def ghost_cavity_cached(part, params, px):
    """Cached full-depth cavity carve for live ghost. Returns (oriented, cavity, to_part)."""
    key = (id(part), round(float(px), 5), _subkey(params, _GHOST_KEYS))
    hit = _GHOST_CACHE.get(key)
    if hit is not None:
        _GHOST_CACHE.move_to_end(key)
        return hit[1], hit[2], hit[3]
    oriented, info = _oriented_cached(part, params)
    gp = params.model_copy()
    gp.hold_height = float(info["z_top"]) + abs(float(info["band_base"])) + 2.0
    cav, _fp = build_cavity(oriented, gp, float(info["band_base"]), px=px,
                            margin=_GHOST_MARGIN)
    to_part = info.get("to_part")
    _GHOST_CACHE[key] = (part, oriented, cav, to_part)
    while len(_GHOST_CACHE) > _GHOST_MAX:
        _GHOST_CACHE.popitem(last=False)
    return oriented, cav, to_part


def _base_block_cached(w, h, d, params):
    """Cached base_block."""
    key = (round(float(w), 3), round(float(h), 3), round(float(d), 3),
           round(float(getattr(params, "corner_fillet", 0.0)), 3),
           round(float(getattr(params, "edge_chamfer", 0.0)), 3))
    hit = _BLOCK_CACHE.get(key)
    if hit is not None:
        _BLOCK_CACHE.move_to_end(key)
        return hit
    blk = base_block(w, h, d, params)
    _BLOCK_CACHE[key] = blk
    while len(_BLOCK_CACHE) > _BLOCK_MAX:
        _BLOCK_CACHE.popitem(last=False)
    return blk


def clear_cache():
    """Drop all stage caches."""
    _ORIENTED_CACHE.clear()
    _CAVITY_CACHE.clear()
    _BLOCK_CACHE.clear()
    _CARVED_CACHE.clear()
    _GHOST_CACHE.clear()
    try:
        from . import heightcapture
        heightcapture.clear_cache()
    except Exception:
        pass


# ---- manifold3d <-> (verts, tris) ----
def _manifold():
    import manifold3d
    return manifold3d


def to_manifold(verts, tris):
    """(verts, tris) -> manifold3d.Manifold."""
    import numpy as np
    m = _manifold()
    mesh = m.Mesh(
        vert_properties=np.ascontiguousarray(verts, dtype=np.float32),
        tri_verts=np.ascontiguousarray(tris, dtype=np.uint32),
    )
    return m.Manifold(mesh)


def from_manifold(man):
    """manifold3d.Manifold -> (verts, tris)."""
    import numpy as np
    mesh = man.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    tris = np.asarray(mesh.tri_verts, dtype=np.int64)
    return verts, tris


def to_polydata(man):
    """manifold3d.Manifold -> pyvista PolyData."""
    import numpy as np
    import pyvista as pv
    verts, tris = from_manifold(man)
    if len(verts) == 0 or len(tris) == 0:
        return None
    faces = np.empty((len(tris), 4), dtype=np.int64)
    faces[:, 0] = 3
    faces[:, 1:] = tris
    return pv.PolyData(verts, faces.ravel())


# ---- Heightfield -> watertight cavity mesh ----
def _disk(r):
    import numpy as np
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    return (xx * xx + yy * yy) <= (r * r + 1e-9)


_SCIPY_WARNED = set()


def _warn_no_scipy(feature):
    """One-shot stderr warning when scipy missing."""
    if feature in _SCIPY_WARNED:
        return
    _SCIPY_WARNED.add(feature)
    import sys
    print("partspack: scipy unavailable - '%s' left unprocessed." % feature,
          file=sys.stderr)


def _grey_fill_holes(img):
    """Grayscale hole-fill (MATLAB imfill)."""
    import numpy as np
    img = np.ascontiguousarray(img, dtype=float)
    marker = np.full_like(img, img.max())
    marker[0, :] = img[0, :]; marker[-1, :] = img[-1, :]
    marker[:, 0] = img[:, 0]; marker[:, -1] = img[:, -1]
    try:
        from skimage.morphology import reconstruction
        return reconstruction(marker, img, method="erosion")
    except Exception:
        pass
    from scipy.ndimage import grey_erosion
    cur = marker
    for _ in range(4 * (img.shape[0] + img.shape[1])):
        nxt = np.maximum(grey_erosion(cur, size=3), img)
        if np.array_equal(nxt, cur):
            break
        cur = nxt
    return cur


def _remove_internal_pillars(floor, px, band_base, block_top,
                             min_feature, remove_all, wall_floor=0.0):
    """Remove internal recess features, keep contour + lowest points."""
    import numpy as np
    if not (remove_all or float(min_feature) > 0.0):
        return floor
    try:
        from scipy.ndimage import binary_opening
    except Exception:
        _warn_no_scipy("remove-internal-features")
        return floor
    cut = floor < block_top - 1e-9
    if not cut.any():
        return floor

    inv = float(block_top) - floor
    floor_env = float(block_top) - _grey_fill_holes(inv)
    internal = floor_env < floor - 1e-9
    if not internal.any():
        return floor

    if not remove_all and float(min_feature) > 0.0:
        r = max(1, int(round((float(min_feature) / 2.0) / float(px))))
        internal = binary_opening(internal, structure=_disk(r))
        if not internal.any():
            return floor

    floor = floor.copy()
    if float(wall_floor) > 0.0:
        floor[internal] = max(float(band_base), float(band_base) + float(wall_floor))
    else:
        floor[internal] = floor_env[internal]
    return floor


def cavity_floor(H, px, band_base, block_top, clearance,
                 min_feature=0.0, remove_internal=False, wall_floor=0.0):
    """Cavity bottom-surface floor(x,y) over full grid."""
    import numpy as np
    H = np.asarray(H, dtype=float)
    finite = np.isfinite(H)

    work = H.copy()
    try:
        from scipy.ndimage import binary_fill_holes
        filled = binary_fill_holes(finite)
        interior = filled & ~finite
        work[interior] = band_base      # fill enclosed bores
    except Exception:
        filled = finite

    work[~np.isfinite(work)] = np.inf    # background can't pull floor up
    r = int(round(float(clearance) / float(px)))
    if r >= 1:
        try:
            from scipy.ndimage import grey_erosion
            work = grey_erosion(work, footprint=_disk(r))
        except Exception:
            pass

    mask = work <= block_top
    floor = np.clip(work, band_base, block_top)
    floor[~mask] = block_top
    floor = _remove_internal_pillars(floor, px, band_base, block_top,
                                     min_feature, remove_internal, wall_floor)
    return floor


def _apply_mouth_chamfer(floor, px, block_top, chamfer):
    """Bevel cavity mouth as 45° lead-in on cutter floor."""
    import numpy as np
    chamfer = float(chamfer)
    if chamfer <= 1e-6:
        return floor
    try:
        from scipy.ndimage import distance_transform_edt
    except Exception:
        return floor
    cav = floor < block_top - 1e-9
    if not cav.any():
        return floor
    dist_mm = distance_transform_edt(~cav) * float(px)
    ramp = block_top - np.clip(chamfer - dist_mm, 0.0, chamfer)
    return np.minimum(floor, ramp)


def heightfield_cutter_mesh(floor, x0, y0, px, top):
    """Watertight cutter mesh for height field. Returns (verts, tris)."""
    import numpy as np
    floor = np.asarray(floor, dtype=float)
    ny, nx = floor.shape
    NB = nx * ny

    jj, ii = np.meshgrid(np.arange(nx), np.arange(ny))
    X = x0 + jj * px
    Y = y0 + ii * px
    bot = np.stack([X, Y, floor], axis=-1).reshape(-1, 3)
    topv = np.stack([X, Y, np.full_like(floor, top)], axis=-1).reshape(-1, 3)
    verts = np.concatenate([bot, topv], axis=0)

    ci, cj = np.meshgrid(np.arange(ny - 1), np.arange(nx - 1), indexing="ij")
    v00 = (ci * nx + cj).ravel()
    v01 = (ci * nx + cj + 1).ravel()
    v10 = ((ci + 1) * nx + cj).ravel()
    v11 = ((ci + 1) * nx + cj + 1).ravel()

    # Winding must be globally consistent or manifold3d rejects mesh.
    bot_t = np.concatenate([np.stack([v00, v10, v11], -1),
                            np.stack([v00, v11, v01], -1)], axis=0)
    top_t = np.concatenate([np.stack([v00 + NB, v01 + NB, v11 + NB], -1),
                            np.stack([v00 + NB, v11 + NB, v10 + NB], -1)], axis=0)

    top_edge = [0 * nx + j for j in range(nx)]
    right_edge = [i * nx + (nx - 1) for i in range(1, ny)]
    bottom_edge = [(ny - 1) * nx + j for j in range(nx - 2, -1, -1)]
    left_edge = [i * nx + 0 for i in range(ny - 2, 0, -1)]
    loop = np.array(top_edge + right_edge + bottom_edge + left_edge, dtype=np.int64)
    b0 = loop
    b1 = np.roll(loop, -1)
    skirt = np.concatenate([np.stack([b0, b1, b1 + NB], -1),
                            np.stack([b0, b1 + NB, b0 + NB], -1)], axis=0)

    tris = np.concatenate([bot_t, top_t, skirt], axis=0).astype(np.int64)

    # Orient outward: signed volume must be positive.
    p0, p1, p2 = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    vol = np.einsum("ij,ij->i", p0, np.cross(p1 - p0, p2 - p0)).sum() / 6.0
    if vol < 0:
        tris = tris[:, ::-1].copy()
    return verts, tris


_TIN_MAX_ERROR = 0.05      # mm vertical tol for adaptive cutter TIN


def _tin_cutter_mesh(floor, x0, y0, px, top, max_error=_TIN_MAX_ERROR):
    """Watertight cutter mesh via error-bounded TIN (pydelatin)."""
    import numpy as np
    from pydelatin import Delatin
    d = Delatin(np.ascontiguousarray(floor, dtype="float32"),
                max_error=float(max_error))
    v = np.asarray(d.vertices, dtype=float)
    t = np.asarray(d.triangles, dtype=np.int64)
    M = len(v)
    a0, a1, a2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    area2 = ((a1[:, 0] - a0[:, 0]) * (a2[:, 1] - a0[:, 1])
             - (a1[:, 1] - a0[:, 1]) * (a2[:, 0] - a0[:, 0]))
    if area2.sum() < 0:
        t = t[:, ::-1].copy()

    xw = x0 + v[:, 0] * px
    # pydelatin row 0 at top: flip Y or cavity comes out mirrored.
    ny = floor.shape[0]
    yw = y0 + (ny - 1 - v[:, 1]) * px
    bottom = np.stack([xw, yw, v[:, 2]], axis=-1)
    topv = np.stack([xw, yw, np.full(M, float(top))], axis=-1)
    verts = np.concatenate([bottom, topv], axis=0)

    # Boundary = directed edges with no reverse twin.
    edges = {}
    for a, b, c in t:
        for e in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            edges[e] = edges.get(e, 0) + 1
    skirt = []
    for (a, b), n in edges.items():
        if (b, a) not in edges:
            skirt.append((a, b, b + M))
            skirt.append((a, b + M, a + M))
    bot_t = t[:, ::-1]
    top_t = t + M
    tris = np.concatenate([bot_t, top_t,
                           np.asarray(skirt, dtype=np.int64)], axis=0)
    p0, p1, p2 = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    if np.einsum("ij,ij->i", p0, np.cross(p1 - p0, p2 - p0)).sum() < 0:
        tris = tris[:, ::-1].copy()
    return verts, tris


def _cutter_manifold(floor, x0, y0, px, top):
    """Cutter Manifold from floor: TIN, falling back to grid."""
    try:
        v, t = _tin_cutter_mesh(floor, x0, y0, px, top)
        man = to_manifold(v, t)
        if man is not None and not man.is_empty():
            return man
    except Exception:
        pass
    v, t = heightfield_cutter_mesh(floor, x0, y0, px, top)
    return to_manifold(v, t)


def cavity_manifold(hm, params, band_base):
    """Cavity cutter Manifold from heightmap. Returns (manifold, footprint_xy)."""
    import numpy as np
    block_top = float(band_base) + float(params.hold_height)
    floor = cavity_floor(hm.H, hm.px, float(band_base), block_top,
                         float(params.part_clearance),
                         min_feature=float(params.min_internal_feature),
                         remove_internal=bool(params.remove_internal_features),
                         wall_floor=float(getattr(params, "internal_wall_floor", 0.0)))
    # Clamp chamfer so adjacent bevels can't eat the wall between cavities.
    chamfer = float(params.mouth_chamfer)
    gap = float(getattr(params, "part_spacing", 0.0))
    if gap > 0:
        chamfer = min(chamfer, max(0.0, gap / 2.0 - 0.1))
    floor = _apply_mouth_chamfer(floor, hm.px, block_top, chamfer)
    floor = np.nan_to_num(floor, nan=block_top, posinf=block_top,
                          neginf=float(band_base))
    man = _cutter_manifold(floor, hm.x0, hm.y0, hm.px, block_top + _OVERCUT)

    cut = floor < block_top - 1e-9
    if cut.any():
        ii, jj = np.nonzero(cut)
        minx = hm.x0 + jj.min() * hm.px
        maxx = hm.x0 + jj.max() * hm.px
        miny = hm.y0 + ii.min() * hm.px
        maxy = hm.y0 + ii.max() * hm.px
    else:
        minx = miny = maxx = maxy = 0.0
    return man, (float(minx), float(miny), float(maxx), float(maxy))


# ---- Primitives (cutters/blocks for ported feature ops, Phase B) ----
def box(w, h, d, center=(0.0, 0.0, 0.0)):
    """Axis-aligned box of size (w,h,d) centred at `center`."""
    m = _manifold()
    b = m.Manifold.cube([float(w), float(h), float(d)], center=True)
    return b.translate([float(center[0]), float(center[1]), float(center[2])])


def base_block(w, h, d, params):
    """Tray outer block with rounded corners + chamfered edges."""
    r = max(0.0, float(getattr(params, "corner_fillet", 0.0)))
    c = max(0.0, float(getattr(params, "edge_chamfer", 0.0)))
    half = min(float(w), float(h)) / 2.0
    r = min(r, half - 0.05) if r > 1e-6 else 0.0
    c = min(c, half - 0.05, float(d) / 2.0 - 0.05) if c > 1e-6 else 0.0
    if r <= 0.0 and c <= 0.0:
        return box(w, h, d, center=(0.0, 0.0, d / 2.0))
    try:
        from build123d import (RectangleRounded, Rectangle, extrude, chamfer,
                               Axis)
        prof = RectangleRounded(w, h, r) if r > 0 else Rectangle(w, h)
        solid = extrude(prof, float(d))
        if c > 0:
            zg = solid.edges().group_by(Axis.Z)
            solid = chamfer(zg[0] + zg[-1], c)
        man = from_b3d(solid)
        if man is not None and not man.is_empty():
            return man
    except Exception:
        pass
    return box(w, h, d, center=(0.0, 0.0, d / 2.0))


def cylinder(radius, height, segments=64, center=(0.0, 0.0, 0.0)):
    """Z-axis cylinder, centred at `center`."""
    m = _manifold()
    c = m.Manifold.cylinder(float(height), float(radius), float(radius),
                            int(segments), center=True)
    return c.translate([float(center[0]), float(center[1]), float(center[2])])


def sphere(radius, center=(0.0, 0.0, 0.0), segments=48):
    """Sphere centred at `center`."""
    m = _manifold()
    s = m.Manifold.sphere(float(radius), int(segments))
    return s.translate([float(center[0]), float(center[1]), float(center[2])])


def from_b3d(shape, linear=0.2, angular=0.5, weld_tol=1e-4):
    """Tessellate + weld build123d solid into watertight Manifold."""
    import numpy as np
    try:
        verts, tris = shape.tessellate(tolerance=linear, angular_tolerance=angular)
    except Exception:
        return None
    if not verts or not tris:
        return None
    V = np.array([tuple(v) for v in verts], dtype=float)
    T = np.array(tris, dtype=np.int64)
    # Weld coincident verts so faces share them (2-manifold).
    _, inv = np.unique(np.round(V / weld_tol).astype(np.int64), axis=0,
                       return_inverse=True)
    inv = np.asarray(inv).ravel()
    T2 = inv[T]
    degen = (T2[:, 0] == T2[:, 1]) | (T2[:, 1] == T2[:, 2]) | (T2[:, 0] == T2[:, 2])
    T2 = T2[~degen]
    if len(T2) == 0:
        return None
    Vu = np.zeros((int(inv.max()) + 1, 3), dtype=float)
    Vu[inv] = V
    man = to_manifold(Vu, T2)
    return None if man.is_empty() else man


# ---- Tray assembly: carve cavity grid out of base block (only tray path) ----
def build_cavity(oriented, params, band_base, px=None, margin=None):
    """Render heightmap + carve cavity. Returns (manifold, footprint_bounds)."""
    from . import heightcapture
    hm = heightcapture.render_heightmap(oriented, params, px=px, margin=margin)
    return cavity_manifold(hm, params, band_base)


def _spacing_wh(oriented, fp_bounds, params):
    """Grid-pitch envelope: footprint widened to part XY extent."""
    minx, miny, maxx, maxy = fp_bounds
    w, h = (maxx - minx), (maxy - miny)
    try:
        bb = oriented.bounding_box(optimal=False)
        w = max(w, float(bb.max.X - bb.min.X))
        h = max(h, float(bb.max.Y - bb.min.Y))
    except Exception:
        pass
    return w, h


def _subtract_all(solid, cutters):
    """solid minus all cutters in one batched boolean."""
    cutters = [c for c in cutters if c is not None]
    if not cutters:
        return solid
    try:
        m = _manifold()
        return m.Manifold.batch_boolean([solid] + cutters, m.OpType.Subtract)
    except Exception:
        for c in cutters:
            solid = solid - c
        return solid


def cavity_footprint_poly(hm, params, band_base):
    """Cavity top footprint as shapely polygon."""
    from . import heightcapture
    block_top = float(band_base) + float(params.hold_height)
    floor = cavity_floor(hm.H, hm.px, float(band_base), block_top,
                         float(params.part_clearance))
    mask = floor < block_top - 1e-9
    if not mask.any():
        return None
    poly = heightcapture._mask_to_polygon(mask, hm)
    return poly if (poly is not None and not poly.is_empty) else None


class _Carved:
    """Carve-direct build output."""
    __slots__ = ("oriented", "cavity", "trays", "part_place", "to_oriented",
                 "slide_dir")

    def __init__(self, oriented, cavity, trays, part_place=None,
                 to_oriented=None, slide_dir=(0.0, 0.0, 1.0)):
        self.oriented = oriented
        self.cavity = cavity
        self.trays = trays
        self.part_place = part_place
        self.to_oriented = to_oriented
        self.slide_dir = slide_dir


def _block_top(params):
    return float(params.bottom_margin) + float(params.hold_height)


def carve_cavity(oriented, info, params):
    """Render heightmap + carve cavity, returning assembler placement data."""
    from . import heightcapture
    band_base = float(info["band_base"])
    hm = heightcapture.render_heightmap(oriented, params)
    cav_man, fp = cavity_manifold(hm, params, band_base)
    bsec = heightcapture.bottom_section(oriented, params, band_base)

    if info.get("tilt_mode_b"):
        cav_man, fp, fp_poly = _shear_cavity_mesh(cav_man, params)
        cav_w, cav_h = (fp[2] - fp[0], fp[3] - fp[1])
        return {"cavity": cav_man, "fp_bounds": fp, "fp_poly": fp_poly,
                "cav_wh": (cav_w, cav_h), "bottom_sec": bsec,
                "world_placed": False, "placed_block_top": None}

    fp_poly = cavity_footprint_poly(hm, params, band_base)
    cav_w, cav_h = _spacing_wh(oriented, fp, params)
    return {"cavity": cav_man, "fp_bounds": fp, "fp_poly": fp_poly,
            "cav_wh": (cav_w, cav_h), "bottom_sec": bsec,
            "world_placed": False, "placed_block_top": None}


def _shear_cavity_mesh(cav_man, params):
    """Shear cavity into oblique pocket for rotate-tray. Returns (sheared, fp_bounds, fp_poly)."""
    import math
    import numpy as np
    from shapely.geometry import box as shp_box
    deg = float(params.tilt_deg)
    t = math.tan(math.radians(deg))
    axis = str(params.tilt_axis)
    if axis == "X":
        M = np.array([[1, 0, 0, 0], [0, 1, t, 0], [0, 0, 1, 0]], dtype=float)
    elif axis == "Y":
        M = np.array([[1, 0, t, 0], [0, 1, 0, 0], [0, 0, 1, 0]], dtype=float)
    else:                                       # Z tilt degenerate
        bb = cav_man.bounding_box()
        fp = (float(bb[0]), float(bb[1]), float(bb[3]), float(bb[4]))
        return cav_man, fp, shp_box(*fp)
    sheared = cav_man.transform(M)
    bb = sheared.bounding_box()
    fp = (float(bb[0]), float(bb[1]), float(bb[3]), float(bb[4]))
    return sheared, fp, shp_box(*fp)


def assemble_tray(cap, info, params, centres, tray_size=None, push_holes=True,
                  label_text=None, reg_pts=None):
    """Carve cavity grid + skeleton/reliefs/feet/label. Returns (tray, (w, h, block_top))."""
    from . import array, base
    cav_man = cap["cavity"]
    fx0, fy0, fx1, fy1 = cap["fp_bounds"]
    fx, fy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
    cav_w, cav_h = cap["cav_wh"]
    if tray_size is None:
        tray_w, tray_h = array.footprint(params, centres, cav_w, cav_h)
        tray_w, tray_h = base.snap_footprint(params, tray_w, tray_h)
    else:
        tray_w, tray_h = tray_size
    if cap.get("world_placed"):
        block_top = float(cap["placed_block_top"])
        zlift = 0.0
    else:
        block_top = _block_top(params)
        zlift = float(info.get("world_z_offset", params.bottom_margin))

    sub_key = (id(cav_man),
               round(float(tray_w), 3), round(float(tray_h), 3),
               round(float(block_top), 3),
               round(float(getattr(params, "corner_fillet", 0.0)), 3),
               round(float(getattr(params, "edge_chamfer", 0.0)), 3),
               round(float(zlift), 4), round(float(fx), 4), round(float(fy), 4),
               tuple((round(float(cx), 4), round(float(cy), 4))
                     for cx, cy in centres))
    hit = _CARVED_CACHE.get(sub_key)
    if hit is not None:
        _CARVED_CACHE.move_to_end(sub_key)
        tray = hit[1]
    else:
        block = _base_block_cached(tray_w, tray_h, block_top, params)
        copies = [cav_man.translate([cx - fx, cy - fy, zlift])
                  for cx, cy in centres]
        tray = _subtract_all(block, copies)
        _CARVED_CACHE[sub_key] = (cav_man, tray)
        while len(_CARVED_CACHE) > _CARVED_MAX:
            _CARVED_CACHE.popitem(last=False)

    tray = _skeleton(tray, centres, params, tray_w, tray_h, block_top,
                     cav_w, cav_h, cap, reg_pts=reg_pts)

    gridfinity = str(params.base_profile) == "gridfinity"
    # Gridfinity defers push holes until after feet added (drill through them).
    if push_holes and not gridfinity:
        tray, _n, _i = add_push_holes(tray, centres, cap["bottom_sec"], fx, fy,
                                      params)
    tray, _nd = add_finger_divots(tray, cap["fp_poly"], centres, params)
    if params.pocket_index:
        tray = add_pocket_indices(tray, centres, params, cav_w, cav_h)
    if gridfinity:
        tray = _gridfinity_feet(tray, tray_w, tray_h, params)
        if push_holes:
            from .base import _FOOT_H
            tray, _n, _i = add_push_holes(tray, centres, cap["bottom_sec"],
                                          fx, fy, params, bottom_z=-_FOOT_H)
    if label_text:
        tray = add_label(tray, label_text, params)
    return tray, (tray_w, tray_h, block_top)


def build_result_trays(part, params, label_text):
    """Full carve-direct build (single/two-sided/tilt B). Returns _Carved."""
    from . import array, base

    oriented_b, info_b, cap_b = _carve_cached(part, params)

    if not params.two_sided:
        cav_w, cav_h = cap_b["cav_wh"]
        centres = array.grid_centres(params, cav_w, cav_h)
        tray, _ = assemble_tray(cap_b, info_b, params, centres,
                                push_holes=True, label_text=label_text)
        import math
        place = None
        slide_dir = (0.0, 0.0, 1.0)
        if centres:
            fx0, fy0, fx1, fy1 = cap_b["fp_bounds"]
            fx, fy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
            zlift = float(info_b.get("world_z_offset", params.bottom_margin))
            cx, cy = centres[0]
            place = (cx - fx, cy - fy, zlift)
            if info_b.get("tilt_mode_b") and float(params.tilt_deg):
                tt = math.tan(math.radians(float(params.tilt_deg)))
                d = ((0.0, tt, 1.0) if str(params.tilt_axis) == "X"
                     else (tt, 0.0, 1.0) if str(params.tilt_axis) == "Y"
                     else (0.0, 0.0, 1.0))
                nrm = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
                slide_dir = (d[0] / nrm, d[1] / nrm, d[2] / nrm)
        return _Carved(oriented_b, cap_b["cavity"], [tray], place,
                       info_b.get("to_oriented"), slide_dir)

    # ---- two-sided sandwich ----
    part_len = float(info_b["z_top"])
    bottom_band = float(params.hold_height)
    grip_gap = float(params.grip_gap)
    top_band = part_len - bottom_band - grip_gap
    _MIN_BAND = 0.5
    if top_band < _MIN_BAND:
        top_band = _MIN_BAND
    elif top_band > part_len:
        top_band = part_len

    p_t = params.model_copy()
    p_t.flip = not params.flip                 # opposite end
    p_t.hold_height = float(top_band)
    oriented_t, info_t, cap_t = _carve_cached(part, p_t)

    bw, bh = cap_b["cav_wh"]
    tw, th = cap_t["cav_wh"]
    cav_w, cav_h = max(bw, tw), max(bh, th)
    centres = array.grid_centres(params, cav_w, cav_h)
    tray_w, tray_h = array.footprint(params, centres, cav_w, cav_h)
    tray_w, tray_h = base.snap_footprint(params, tray_w, tray_h)

    from . import mate
    reg_pts = _filter_reg_over_cavity(
        mate._reg_points(tray_w, tray_h, params), cap_b, centres, params)

    bottom, (_, _, block_top_b) = assemble_tray(
        cap_b, info_b, params, centres, tray_size=(tray_w, tray_h),
        push_holes=True, reg_pts=reg_pts)
    top, (_, _, block_top_t) = assemble_tray(
        cap_t, info_t, p_t, centres, tray_size=(tray_w, tray_h),
        push_holes=False, reg_pts=reg_pts)

    bottom, top = add_registration(bottom, top, tray_w, tray_h,
                                   block_top_b, block_top_t, params,
                                   reg_pts=reg_pts)
    bottom, top = add_closure(bottom, top, tray_w, tray_h,
                              block_top_b, block_top_t, params)
    if label_text:                             # bottom half only
        bottom = add_label(bottom, label_text, params)
    return _Carved(oriented_b, cap_b["cavity"], [bottom, top])


# ---- Skeleton (pocketed | honeycomb | ribbed): mesh ports of base.py ----
def _skeleton(tray, centres, params, tray_w, tray_h, block_top, cav_w, cav_h,
              cap=None, reg_pts=None):
    style = str(params.skeleton_style)
    if style == "solid":
        return tray
    if cap is not None and getattr(params, "outside_lightening", False):
        region = _lighten_region(params, tray_w, tray_h, centres, cap, reg_pts)
        if region is None or region.is_empty:
            return tray
        return lighten_web(tray, region, params, block_top)
    if style == "pocketed":
        return _skeleton_pocketed(tray, centres, params, tray_w, tray_h,
                                  block_top, cav_w, cav_h)
    return _skeleton_cells(tray, centres, params, tray_w, tray_h, block_top,
                           cav_w, cav_h, style)


def _rounded_rect(w, h, fillet):
    """Rounded-corner w×h rectangle as shapely polygon."""
    from shapely.geometry import box
    core = box(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0)
    r = max(0.0, min(float(fillet), min(w, h) / 2.0 - 0.1))
    return core.buffer(-r).buffer(r) if r > 1e-6 else core


def _reg_keepout_r(params):
    """Keep-out radius under each registration pin/socket."""
    return float(params.pin_diameter) / 2.0 + float(params.pin_clearance) + 1.5


def _filter_reg_over_cavity(pts, cap, centres, params):
    """Drop registration points sitting over a cavity."""
    if not pts:
        return pts
    from shapely.ops import unary_union
    from shapely.affinity import translate
    from shapely.geometry import Point
    fp = cap.get("fp_poly") if cap else None
    if fp is None or fp.is_empty or not centres:
        return pts
    fx0, fy0, fx1, fy1 = cap["fp_bounds"]
    fx, fy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
    placed = unary_union([translate(fp, cx - fx, cy - fy) for cx, cy in centres])
    r = _reg_keepout_r(params)
    return [(x, y) for (x, y) in pts
            if not placed.intersects(Point(x, y).buffer(r))]


def _lighten_region(params, tray_w, tray_h, centres, cap, reg_pts=None):
    """Full-tray lightenable region minus footprints/label/pins."""
    from shapely.ops import unary_union
    from shapely.affinity import translate
    from shapely.geometry import box as shp_box, Polygon
    if not centres:
        return Polygon()
    edge = float(params.outside_wall)
    feat = float(params.outside_rim)
    region = _rounded_rect(tray_w, tray_h, params.corner_fillet).buffer(-edge)
    fp = cap.get("fp_poly") if cap else None
    if fp is not None and not fp.is_empty and centres:
        fx0, fy0, fx1, fy1 = cap["fp_bounds"]
        fx, fy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
        placed = [translate(fp, cx - fx, cy - fy) for cx, cy in centres]
        region = region.difference(unary_union(placed).buffer(feat))
        divots = _divot_footprints(fp, centres, params)
        if divots:
            region = region.difference(unary_union(divots).buffer(feat))
    if str(params.label_mode) != "none" and str(params.label_place) == "top":
        band = float(params.border) + 8.0
        region = region.difference(
            shp_box(-tray_w / 2.0, -tray_h / 2.0, tray_w / 2.0,
                    -tray_h / 2.0 + band))
    if reg_pts:
        from shapely.geometry import Point
        r = _reg_keepout_r(params)
        region = region.difference(
            unary_union([Point(x, y).buffer(r) for (x, y) in reg_pts]))
    return region


def extrude_polygon(poly, z_lo, z_hi):
    """shapely polygon -> manifold prism between z_lo and z_hi."""
    m = _manifold()
    contours = []
    geoms = poly.geoms if poly.geom_type == "MultiPolygon" else [poly]
    for g in geoms:
        if g.is_empty:
            continue
        contours.append(list(g.exterior.coords)[:-1])
        for ring in g.interiors:
            contours.append(list(ring.coords)[:-1])
    if not contours:
        return None
    cs = m.CrossSection(contours, m.FillRule.EvenOdd)
    if cs.area() <= 1e-9:
        return None
    return m.Manifold.extrude(cs, float(z_hi - z_lo)).translate([0.0, 0.0,
                                                                 float(z_lo)])


def _cut_web_cells(tray, polys, params, block_top):
    """Subtract web void cells, blind or through."""
    if not polys:
        return tray
    if params.lightening_through:
        z_lo, z_hi = -1.0, block_top + 1.0
    else:
        z_lo, z_hi = float(params.web_floor), block_top + 1.0
    cutters = []
    for poly in polys:
        c = extrude_polygon(poly, z_lo, z_hi)
        if c is not None:
            cutters.append(c)
    return _subtract_all(tray, cutters)


def lighten_web(tray, web, params, block_top):
    """Apply skeleton style to arbitrary web polygon."""
    if web is None or web.is_empty:
        return tray
    from . import base
    style = str(params.skeleton_style)
    if style == "solid":
        return tray
    if style == "honeycomb":
        polys = base._cell_tiles(web, params)
    elif style == "ribbed":
        ribs = base._rib_lattice(web.bounds, params)
        cells = web.difference(ribs) if ribs is not None else web
        polys = base._flatten_polys(cells,
                                    min_area=max(1.0, float(params.rib_width) ** 2))
    else:                                      # pocketed / fallback
        polys = base._flatten_polys(web)
    return _cut_web_cells(tray, polys, params, block_top)


def _skeleton_cells(tray, centres, params, tray_w, tray_h, block_top,
                    cav_w, cav_h, style):
    """Legacy between-cavity lightening (honeycomb / ribbed)."""
    from . import base
    web = base._web_region(centres, params, tray_w, tray_h, cav_w, cav_h)
    if web.is_empty:
        return tray
    if style == "honeycomb":
        polys = base._cell_tiles(web, params)
    else:
        ribs = base._rib_lattice(web.bounds, params)
        cells = web.difference(ribs) if ribs is not None else web
        polys = base._flatten_polys(cells,
                                    min_area=max(1.0, float(params.rib_width) ** 2))
    return _cut_web_cells(tray, polys, params, block_top)


def _gridfinity_feet(tray, tray_w, tray_h, params):
    """One lofted gridfinity foot per grid unit, magnet-bored."""
    from build123d import RectangleRounded, Pos, loft
    from .base import (_FOOT_SECTIONS, _FOOT_H, GRID_PITCH, _MAGNET_INSET,
                       _MAGNET_DEPTH)
    sections = [Pos(0, 0, z) * RectangleRounded(w, w, r)
                for (z, w, r) in _FOOT_SECTIONS]
    foot = from_b3d(Pos(0, 0, -_FOOT_H) * loft(sections, ruled=True))
    if foot is None:
        return tray
    nx = max(1, int(round(tray_w / GRID_PITCH)))
    ny = max(1, int(round(tray_h / GRID_PITCH)))
    x0 = -tray_w / 2.0 + GRID_PITCH / 2.0
    y0 = -tray_h / 2.0 + GRID_PITCH / 2.0
    mag_r = float(params.magnet_dia) / 2.0
    for i in range(nx):
        for j in range(ny):
            cx, cy = x0 + i * GRID_PITCH, y0 + j * GRID_PITCH
            f = foot.translate([cx, cy, 0.0])
            if params.magnet_holes and mag_r > 0:
                for sx in (-1.0, 1.0):
                    for sy in (-1.0, 1.0):
                        f = f - cylinder(mag_r, _MAGNET_DEPTH,
                                         center=(cx + sx * _MAGNET_INSET,
                                                 cy + sy * _MAGNET_INSET,
                                                 -_FOOT_H + _MAGNET_DEPTH / 2.0))
            tray = tray + f
    return tray


def add_pocket_indices(tray, centres, params, cav_w, cav_h):
    """Deboss running number in front of each pocket."""
    if not centres or not params.pocket_index:
        return tray
    from build123d import Pos, extrude
    from .label import _make_text, LABEL_DEPTH
    z_top = tray.bounding_box()[5]
    fs = max(3.0, min(6.0, min(cav_w, cav_h) * 0.18))
    off = cav_h / 2.0 + fs * 0.6 + 0.8
    cutters = []
    start = int(getattr(params, "pocket_index_start", 1))
    for i, (cx, cy) in enumerate(centres, start=start):
        sk = _make_text(str(i), fs)
        if sk is None:
            continue
        try:
            solid = extrude(Pos(cx, cy - off, z_top - LABEL_DEPTH) * sk,
                            amount=LABEL_DEPTH + 0.1)
        except Exception:
            continue
        c = from_b3d(solid)
        if c is not None:
            cutters.append(c)
    return _subtract_all(tray, cutters)


# ---- Two-sided registration + closure: mesh ports of mate.py ----
def add_registration(bottom, top, tray_w, tray_h, block_top_b, block_top_t,
                     params, reg_pts=None):
    """Keyed alignment males on one half, female recesses in other."""
    from . import mate
    pts = reg_pts if reg_pts is not None else mate._reg_points(tray_w, tray_h, params)
    if not pts:
        return bottom, top
    # Clamp pin reach to thinner half so it isn't pierced through.
    max_depth = max(0.5, min(float(block_top_b), float(block_top_t)) - 1.0)
    if float(params.pin_depth) > max_depth:
        params = params.model_copy(update={"pin_depth": max_depth})
    feature = (mate._taper_feature if str(params.pin_style) == "taper"
               else mate._pin_feature)
    pin_on_bottom = str(params.pin_on) != "top"
    male_top = block_top_b if pin_on_bottom else block_top_t
    female_top = block_top_t if pin_on_bottom else block_top_b

    males, females = [], []
    for (x, y) in pts:
        m_sol, _ = feature(x, y, male_top, params)
        _, f_sol = feature(x, y, female_top, params)
        mm, ff = from_b3d(m_sol), from_b3d(f_sol)
        if mm is not None:
            males.append(mm)
        if ff is not None:
            females.append(ff)

    male_tray, female_tray = (bottom, top) if pin_on_bottom else (top, bottom)
    for mm in males:
        male_tray = male_tray + mm
    for ff in females:
        female_tray = female_tray - ff
    return (male_tray, female_tray) if pin_on_bottom else (female_tray, male_tray)


def add_closure(bottom, top, tray_w, tray_h, block_top_b, block_top_t, params):
    """Screw closure: corner bosses with through holes on both halves."""
    if str(params.closure) != "screw":
        return bottom, top
    boss_r = float(params.screw_boss) / 2.0
    hole_r = float(params.screw_dia) / 2.0
    inset = float(params.wall_thickness) + boss_r
    a = tray_w / 2.0 - inset
    b = tray_h / 2.0 - inset
    if a <= 0 or b <= 0:
        return bottom, top
    corners = [(a, b), (a, -b), (-a, b), (-a, -b)]
    out = []
    for tray, block_top in ((bottom, block_top_b), (top, block_top_t)):
        for (x, y) in corners:
            tray = tray + cylinder(boss_r, block_top, center=(x, y, block_top / 2.0))
            tray = tray - cylinder(hole_r, block_top + 2.0,
                                   center=(x, y, block_top / 2.0))
        out.append(tray)
    return out[0], out[1]


# ---- Feature cutters (push holes / finger divots / label) ----
def add_push_holes(tray, centres, bottom_section, fx, fy, params,
                   pocket_angles=None, bottom_z=0.0):
    """Drill push holes. Returns (tray, n_holes, info)."""
    import math
    from . import relief

    allowed, centre_xy, info = relief.push_hole_allowed(bottom_section, params)
    if not allowed:
        return tray, 0, info

    hx0, hy0 = centre_xy
    r = float(params.push_hole_diameter) / 2.0
    band_base = float(params.bottom_margin)
    z_lo, z_hi = float(bottom_z) - 1.0, band_base + 0.5
    height = z_hi - z_lo
    zc = (z_lo + z_hi) / 2.0
    cs_depth = (min(2.0, float(params.bottom_margin))
                if params.push_hole_countersink else 0.0)
    dx0, dy0 = hx0 - fx, hy0 - fy

    cutters, n = [], 0
    for i, (cx, cy) in enumerate(centres):
        a = math.radians(float(pocket_angles[i])) if pocket_angles else 0.0
        if a:
            dx = dx0 * math.cos(a) - dy0 * math.sin(a)
            dy = dx0 * math.sin(a) + dy0 * math.cos(a)
        else:
            dx, dy = dx0, dy0
        hx, hy = cx + dx, cy + dy
        if str(params.push_hole_shape) == "slot":
            c = from_b3d(relief._slot(hx, hy, r, height, zc, params))
            if c is not None:
                cutters.append(c)
        else:
            cutters.append(cylinder(r, height, center=(hx, hy, zc)))
        if cs_depth > 0:
            cutters.append(cylinder(r + 1.5, cs_depth + 1.0,
                                    center=(hx, hy, z_lo + (cs_depth + 1.0) / 2.0)))
        n += 1
    return _subtract_all(tray, cutters), n, info


def _divot_collar(shape, bx, by, theta, r, band_top, chamfer, params):
    """45° chamfer funnel matching divot outline, unioned onto cutter."""
    import math
    m = _manifold()
    eps = 0.05
    h = float(chamfer) + eps
    z0 = float(band_top) - float(chamfer)
    if shape in ("round", "scallop"):
        cone = m.Manifold.cylinder(h, float(r), float(r) + h, 64, center=False)
        return cone.translate([float(bx), float(by), z0])
    d = float(params.divot_diameter)
    if shape == "square":
        w, l, deg = d, d, 0.0
    else:                                       # rect, u_channel
        w, l, deg = d * 0.6, d, math.degrees(theta)
    cs = m.CrossSection([[(-w / 2.0, -l / 2.0), (w / 2.0, -l / 2.0),
                          (w / 2.0, l / 2.0), (-w / 2.0, l / 2.0)]],
                        m.FillRule.NonZero)
    frus = m.Manifold.extrude(cs, h, 0, 0.0,
                              ((w + 2.0 * h) / w, (l + 2.0 * h) / l))
    return frus.rotate([0.0, 0.0, deg]).translate([float(bx), float(by), z0])


def _divot_footprints(footprint_poly, centres, params):
    """Top-surface footprints of finger divots for lightening keep-out."""
    import math
    from . import relief
    if (footprint_poly is None or not params.finger_divot
            or params.divot_count < 1):
        return []
    from shapely.geometry import Point
    minx, miny, maxx, maxy = footprint_poly.bounds
    fx, fy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    origin = footprint_poly
    if not relief._point_inside(origin, fx, fy):
        rp = origin.representative_point()
        fx, fy = rp.x, rp.y
    depth = min(float(params.divot_depth), float(params.hold_height) * 0.95)
    chamfer = max(0.0, min(float(params.divot_chamfer), depth - 0.2,
                           float(params.hold_height) * 0.5))
    rows, cols = int(params.rows), int(params.cols)
    strategy = str(params.divot_strategy)
    offset = float(params.divot_offset)
    directions = relief._divot_directions(params)
    r = float(params.divot_diameter) / 2.0
    out = []
    for i, (cx, cy) in enumerate(centres):
        row, col = i // cols, i % cols
        perimeter = (row in (0, rows - 1)) or (col in (0, cols - 1))
        if strategy in ("perimeter", "shared_web") and not perimeter:
            continue
        for th in directions:
            tx, ty = -math.sin(th), math.cos(th)
            span_pos = relief._ray_radius(origin, fx, fy, th + math.pi / 2.0)
            span_neg = relief._ray_radius(origin, fx, fy, th - math.pi / 2.0)
            off = max(-(max(0.0, span_neg - r)),
                      min(offset, max(0.0, span_pos - r)))
            ox, oy = fx + off * tx, fy + off * ty
            if not relief._point_inside(origin, ox, oy):
                ox, oy = fx, fy
            R = relief._ray_radius(origin, ox, oy, th)
            if R <= 0:
                continue
            bx = cx + (ox + R * math.cos(th)) - fx
            by = cy + (oy + R * math.sin(th)) - fy
            out.append(Point(bx, by).buffer(r + chamfer + 0.1, quad_segs=16))
    return out


def add_finger_divots(tray, footprint_poly, centres, params, pocket_angles=None):
    """Add finger divots. Returns (tray, n_divots)."""
    import math
    from . import relief

    if (footprint_poly is None or not params.finger_divot
            or params.divot_count < 1):
        return tray, 0

    minx, miny, maxx, maxy = footprint_poly.bounds
    fx, fy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    origin = footprint_poly
    if not relief._point_inside(origin, fx, fy):
        rp = origin.representative_point()
        fx, fy = rp.x, rp.y

    band_top = float(params.bottom_margin) + float(params.hold_height)
    depth = min(float(params.divot_depth), float(params.hold_height) * 0.95)
    chamfer = max(0.0, min(float(params.divot_chamfer), depth - 0.2,
                           float(params.hold_height) * 0.5))
    shape = str(params.divot_shape)
    rows, cols = int(params.rows), int(params.cols)
    strategy = str(params.divot_strategy)
    offset = float(params.divot_offset)
    directions = relief._divot_directions(params)

    cutters, n = [], 0
    for i, (cx, cy) in enumerate(centres):
        row, col = i // cols, i % cols
        perimeter = (row in (0, rows - 1)) or (col in (0, cols - 1))
        if strategy in ("perimeter", "shared_web") and not perimeter:
            continue
        a = math.radians(float(pocket_angles[i])) if pocket_angles else 0.0
        for th in directions:
            tx, ty = -math.sin(th), math.cos(th)
            r = float(params.divot_diameter) / 2.0
            span_pos = relief._ray_radius(origin, fx, fy, th + math.pi / 2.0)
            span_neg = relief._ray_radius(origin, fx, fy, th - math.pi / 2.0)
            off = max(-(max(0.0, span_neg - r)),
                      min(offset, max(0.0, span_pos - r)))
            ox, oy = fx + off * tx, fy + off * ty
            if not relief._point_inside(origin, ox, oy):
                ox, oy = fx, fy
            R = relief._ray_radius(origin, ox, oy, th)
            if R <= 0:
                continue
            wdx = (ox + R * math.cos(th)) - fx
            wdy = (oy + R * math.sin(th)) - fy
            if a:
                wdx, wdy = (wdx * math.cos(a) - wdy * math.sin(a),
                            wdx * math.sin(a) + wdy * math.cos(a))
            bx, by = cx + wdx, cy + wdy
            c = from_b3d(relief._divot_solid(shape, bx, by, th + a, depth,
                                             band_top, params))
            if c is not None:
                if chamfer > 1e-6:
                    try:
                        c = c + _divot_collar(shape, bx, by, th + a, r,
                                              band_top, chamfer, params)
                    except Exception:
                        pass
                cutters.append(c)
                n += 1
    return _subtract_all(tray, cutters), n


def add_label(tray, text, params):
    """Add deboss/emboss label (top | front nameplate)."""
    mode = str(params.label_mode)
    text = str(text).strip()
    if mode == "none" or not text:
        return tray
    try:
        from . import label as _label
        bb = tray.bounding_box()
        if str(params.label_place) == "front":
            return _label_front_mesh(tray, text, params, mode, bb)
        if str(params.label_place) == "front_face":
            return _label_front_face_mesh(tray, text, params, mode, bb)
        minx, miny, minz, maxx, maxy, maxz = bb
        border = float(params.border)
        fs = max(3.0, min(8.0, border * 0.8 if border > 3.0 else 3.0))
        y_label = miny + max(border, fs) / 2.0
        sk = _label._make_text(text, fs)
        if sk is None:
            return tray
        return _apply_text_mesh(tray, sk, 0.0, y_label, maxz, mode)
    except Exception:
        return tray


def _apply_text_mesh(tray, sk, cx, cy, surface_z, mode):
    """Deboss or emboss extruded Text sketch at (cx,cy)."""
    from build123d import Pos, extrude
    from .label import LABEL_DEPTH
    try:
        if mode == "emboss":
            solid = extrude(Pos(cx, cy, surface_z - 0.05) * sk,
                            amount=LABEL_DEPTH + 0.05)
            man = from_b3d(solid)
            return tray + man if man is not None else tray
        solid = extrude(Pos(cx, cy, surface_z - LABEL_DEPTH) * sk,
                        amount=LABEL_DEPTH + 0.1)
        man = from_b3d(solid)
        return tray - man if man is not None else tray
    except Exception:
        return tray


def _label_front_mesh(tray, text, params, mode, bb):
    """Forward-projecting nameplate shelf + text."""
    from .label import _make_text
    minx, miny, minz, maxx, maxy, maxz = bb
    tray_w = maxx - minx
    fs = max(4.0, min(10.0, tray_w * 0.05))
    sk = _make_text(text, fs)
    if sk is None:
        return tray
    try:
        tb = sk.bounding_box()
        text_w, text_d = (tb.max.X - tb.min.X), (tb.max.Y - tb.min.Y)
    except Exception:
        text_w, text_d = fs * len(text) * 0.7, fs
    margin = max(2.0, fs * 0.4)
    tab_w = min(tray_w, text_w + 2 * margin)
    tab_d = text_d + 2 * margin
    tab_t = max(1.6, float(params.bottom_margin))
    overlap = 1.0
    label_cy = miny - tab_d / 2.0
    tab_cy = label_cy + overlap / 2.0
    tray = tray + box(tab_w, tab_d + overlap, tab_t,
                      center=(0.0, tab_cy, tab_t / 2.0))
    return _apply_text_mesh(tray, sk, 0.0, label_cy, tab_t, mode)


def _label_front_face_mesh(tray, text, params, mode, bb):
    """Label on tray front wall (−Y face)."""
    from build123d import Plane, extrude
    from .label import _make_text, LABEL_DEPTH
    minx, miny, minz, maxx, maxy, maxz = bb
    tray_w, wall_h = maxx - minx, maxz - minz
    fs = max(4.0, min(10.0, min(tray_w * 0.06, wall_h * 0.55)))
    sk = _make_text(text, fs)
    if sk is None:
        return tray
    z_centre = minz + wall_h * 0.5
    try:
        if mode == "emboss":
            pl = Plane(origin=(0.0, miny, z_centre), x_dir=(1, 0, 0),
                       z_dir=(0, -1, 0))
            man = from_b3d(extrude(pl * sk, amount=LABEL_DEPTH))
            return tray + man if man is not None else tray
        pl = Plane(origin=(0.0, miny - 0.1, z_centre), x_dir=(1, 0, 0),
                   z_dir=(0, -1, 0))
        man = from_b3d(extrude(pl * sk, amount=-(LABEL_DEPTH + 0.1)))
        return tray - man if man is not None else tray
    except Exception:
        return tray


def _skeleton_pocketed(tray, centres, params, tray_w, tray_h, block_top,
                       cav_w, cav_h):
    """Full-length strip boxes in gaps between cavity columns/rows."""
    from . import base
    border = float(params.border)
    rim = float(params.rim_width)
    xlo, xhi = -tray_w / 2.0 + border, tray_w / 2.0 - border
    ylo, yhi = -tray_h / 2.0 + border, tray_h / 2.0 - border
    if xhi <= xlo or yhi <= ylo:
        return tray
    if params.lightening_through:
        z_lo, z_hi = -1.0, block_top + 1.0
    else:
        z_lo, z_hi = float(params.web_floor), block_top + 1.0
    depth = z_hi - z_lo
    zc = (z_lo + z_hi) / 2.0
    xs = [cx for cx, _ in centres]
    ys = [cy for _, cy in centres]
    cutters = []
    for (a, b) in base._gaps(xs, cav_w / 2.0, rim, xlo, xhi):
        cutters.append(box(b - a, yhi - ylo, depth, center=((a + b) / 2.0, 0.0, zc)))
    for (a, b) in base._gaps(ys, cav_h / 2.0, rim, ylo, yhi):
        cutters.append(box(xhi - xlo, b - a, depth, center=(0.0, (a + b) / 2.0, zc)))
    return _subtract_all(tray, cutters)


# ---- Bed-split: mesh port of bedsplit.py ----
def _cyl_axis(r, length, center, axis):
    """Cylinder with axis along world X or Y."""
    m = _manifold()
    c = m.Manifold.cylinder(float(length), float(r), float(r), 64, center=True)
    if axis == "X":
        c = c.rotate([0.0, 90.0, 0.0])
    elif axis == "Y":
        c = c.rotate([90.0, 0.0, 0.0])
    return c.translate([float(center[0]), float(center[1]), float(center[2])])


def _add_split_dowels(tray, xe, ye, z0, z1, nx, ny, params):
    """Drill dowel hole across every interior seam before cutting."""
    r = float(params.pin_diameter) / 2.0 + float(params.pin_clearance)
    if r <= 0:
        return tray
    half = max(6.0, float(params.pin_depth))
    zc = (z0 + z1) / 2.0
    cx = [(xe[i] + xe[i + 1]) / 2.0 for i in range(nx)]
    cy = [(ye[j] + ye[j + 1]) / 2.0 for j in range(ny)]
    cutters = []
    for i in range(1, nx):                          # vertical seams
        for j in range(ny):
            cutters.append(_cyl_axis(r, 2 * half, (xe[i], cy[j], zc), "X"))
    for j in range(1, ny):                          # horizontal seams
        for i in range(nx):
            cutters.append(_cyl_axis(r, 2 * half, (cx[i], ye[j], zc), "Y"))
    return _subtract_all(tray, cutters)


def bed_split(tray, params):
    """Tile oversize tray to bed. Returns list of tile manifolds."""
    from . import bedsplit as bs
    bed_x = float(params.bed_x or 0.0) - bs.BED_MARGIN
    bed_y = float(params.bed_y or 0.0) - bs.BED_MARGIN
    if bed_x <= 0 or bed_y <= 0:
        return [tray]

    x0, y0, z0, x1, y1, z1 = tray.bounding_box()
    W, H = x1 - x0, y1 - y0
    if bs._fits(W, H, bed_x, bed_y):
        return [tray]
    nx, ny = bs._grid(W, H, bed_x, bed_y)
    if nx <= 1 and ny <= 1:
        return [tray]

    xe = [x0 + W * i / nx for i in range(nx + 1)]
    ye = [y0 + H * j / ny for j in range(ny + 1)]
    tray = _add_split_dowels(tray, xe, ye, z0, z1, nx, ny, params)

    tiles = []
    for i in range(nx):
        for j in range(ny):
            cell = box(xe[i + 1] - xe[i], ye[j + 1] - ye[j], (z1 - z0) + 2.0,
                       center=((xe[i] + xe[i + 1]) / 2.0,
                               (ye[j] + ye[j + 1]) / 2.0, (z0 + z1) / 2.0))
            tile = tray ^ cell
            if tile.is_empty() or tile.volume() <= 1e-6:
                continue
            tiles.append(tile)
    return tiles or [tray]


# ---- Self-test: synthetic dome -> carve block ----
def _selftest():
    import sys
    import numpy as np

    class P:
        hold_height = 8.0
        part_clearance = 0.2

    class HM:
        px = 0.1

    try:
        from importlib.metadata import version
        print("manifold3d", version("manifold3d"))
    except Exception:
        print("manifold3d (version unknown)")

    # Synthetic heightmap: dome + interior bore.
    px = 0.1
    nx, ny = 300, 400
    x0, y0 = -15.0, -20.0
    jj, ii = np.meshgrid(np.arange(nx), np.arange(ny))
    X = x0 + jj * px
    Y = y0 + ii * px
    R = np.hypot(X, Y)
    band_base = 1.0
    H = np.full((ny, nx), np.nan)
    inside = R <= 12.0
    H[inside] = band_base + 0.5 + (R[inside] / 12.0) * 5.5
    H[(R > 4.0) & (R < 4.6)] = np.nan          # annular bore

    hm = HM()
    hm.H = H
    hm.x0, hm.y0, hm.px = x0, y0, px
    p = P()

    man, fp = cavity_manifold(hm, p, band_base)
    print("cavity: tris=%d volume=%.2f genus=%s footprint=%s"
          % (man.num_tri(), man.volume(),
             getattr(man, "genus", lambda: "?")(),
             tuple(round(v, 2) for v in fp)))
    if man.volume() <= 0:
        print("FAIL: cavity has non-positive volume (winding/topology wrong)")
        return 1

    block_top = band_base + p.hold_height
    block = box(40, 50, block_top + 2.0, center=(0, 0, (block_top + 2.0) / 2.0))
    tray = block - man
    print("tray:   tris=%d volume=%.2f" % (tray.num_tri(), tray.volume()))
    if tray.volume() >= block.volume():
        print("FAIL: subtract removed nothing")
        return 1

    verts, tris = from_manifold(tray)
    print("tray mesh: verts=%d tris=%d  (z %.2f..%.2f)"
          % (len(verts), len(tris), verts[:, 2].min(), verts[:, 2].max()))
    try:
        out = "/tmp/claude/carve_selftest.stl"
        import os
        os.makedirs("/tmp/claude", exist_ok=True)
        _write_stl(out, verts, tris)
        print("wrote", out, "(open to eyeball the carved dome+bore)")
    except Exception as e:
        print("stl write skipped:", repr(e))
    print("PASS")
    return 0


def _write_stl(path, verts, tris):
    import numpy as np
    v = np.asarray(verts)[np.asarray(tris)]            # (M,3,3)
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    with open(path, "w") as f:
        f.write("solid carve\n")
        for tri, nor in zip(v, n):
            f.write(" facet normal %g %g %g\n  outer loop\n" % tuple(nor))
            for p in tri:
                f.write("   vertex %g %g %g\n" % tuple(p))
            f.write("  endloop\n endfacet\n")
        f.write("endsolid carve\n")


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
