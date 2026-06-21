# Parts Packing Generator - Copyright (C) 2026 InPoint Automation
# Licensed under the GNU General Public License v3 or later; see LICENSE.

# Heightmap capture: cavity profiles from z-min orthographic depth render.

from __future__ import annotations

import os
from collections import OrderedDict

_HM_CACHE = OrderedDict()
_HM_MAX = 6

_GPU_WARNED = False


def _agree(g, c):
    """Coverage match + median depth delta."""
    import numpy as np
    fg, fc = np.isfinite(g), np.isfinite(c)
    cov = float((fg == fc).mean())
    inter = fg & fc
    med = float(np.median(np.abs(g[inter] - c[inter]))) if inter.any() else 1e18
    return cov, med


def clear_cache():
    _HM_CACHE.clear()


def _backend() -> str:
    b = os.environ.get("PARTSPACK_DEPTH_BACKEND", "auto").strip().lower()
    return b if b in ("auto", "gpu", "cpu") else "auto"


def _verify() -> bool:
    """Cross-check GPU render against CPU oracle."""
    return os.environ.get("PARTSPACK_DEPTH_VERIFY", "0").strip().lower() \
        not in ("0", "false", "no", "off", "")


_QUALITY_PX = {"draft": 0.2, "normal": 0.1, "fine": 0.05}


def _pixel_size(params) -> float:
    """Raster resolution (mm/pixel)."""
    try:
        v = float(os.environ.get("PARTSPACK_CAPTURE_PX", "") or 0)
    except ValueError:
        v = 0.0
    if v > 1e-4:
        return v
    q = str(getattr(params, "capture_quality", "normal"))
    return _QUALITY_PX.get(q, 0.1)


def _capture_step(params) -> float:
    """Band-level scan vertical spacing (mm)."""
    try:
        v = float(os.environ.get("PARTSPACK_CAPTURE_STEP", "") or 0)
    except ValueError:
        v = 0.0
    return v if v > 1e-4 else 0.6


class Heightmap:
    """z-min depth map over an (x, y) pixel grid; NaN where empty."""

    def __init__(self, H, x0, y0, px):
        self.H = H
        self.x0 = float(x0)
        self.y0 = float(y0)
        self.px = float(px)

    @property
    def ny(self):
        return self.H.shape[0]

    @property
    def nx(self):
        return self.H.shape[1]


def _render_deflection(params):
    """Tessellation chord tol for render (mm)."""
    try:
        v = float(os.environ.get("PARTSPACK_CAPTURE_DEFL", "") or 0)
    except ValueError:
        v = 0.0
    return v if v > 1e-4 else max(2.0 * _pixel_size(params), 0.2)


def _tessellate_once(solid, deflection):
    """Tessellate -> (verts, tris) numpy arrays."""
    import numpy as np
    verts, tris = solid.tessellate(tolerance=deflection)
    v = np.array([tuple(p) for p in verts], dtype=float)
    f = np.array(tris, dtype=np.int64)
    return v, f


def _mesh(oriented, params, defl=None):
    """(verts, tris) of oriented solid."""
    if defl is None:
        defl = _render_deflection(params)
    return _tessellate_once(oriented, defl)


def _grid_bounds(verts, px, margin):
    import numpy as np
    xmin, ymin = verts[:, 0].min() - margin, verts[:, 1].min() - margin
    xmax, ymax = verts[:, 0].max() + margin, verts[:, 1].max() + margin
    nx = max(2, int(np.ceil((xmax - xmin) / px)) + 1)
    ny = max(2, int(np.ceil((ymax - ymin) / px)) + 1)
    return float(xmin), float(ymin), nx, ny


def _render_cpu(verts, tris, x0, y0, nx, ny, px):
    """Numpy z-min triangle rasterizer (oracle + fallback)."""
    import numpy as np
    v = np.asarray(verts, dtype=float)
    tris = np.asarray(tris, dtype=np.int64)
    p0, p1, p2 = v[tris[:, 0]], v[tris[:, 1]], v[tris[:, 2]]
    j0 = np.floor((np.minimum.reduce([p0[:, 0], p1[:, 0], p2[:, 0]]) - x0) / px).astype(np.int64)
    j1 = np.ceil((np.maximum.reduce([p0[:, 0], p1[:, 0], p2[:, 0]]) - x0) / px).astype(np.int64)
    i0 = np.floor((np.minimum.reduce([p0[:, 1], p1[:, 1], p2[:, 1]]) - y0) / px).astype(np.int64)
    i1 = np.ceil((np.maximum.reduce([p0[:, 1], p1[:, 1], p2[:, 1]]) - y0) / px).astype(np.int64)

    Hflat = np.full(ny * nx, np.inf, dtype=float)
    ext = np.maximum(j1 - j0, i1 - i0) + 1
    remaining = np.ones(p0.shape[0], dtype=bool)
    budget = 8_000_000
    K = 4
    while K <= 256:
        sel = np.nonzero(remaining & (ext <= K))[0]
        if sel.size:
            per = max(1, budget // (K * K))
            for s in range(0, sel.size, per):
                b = sel[s:s + per]
                _raster_block(Hflat, nx, ny, x0, y0, px, K,
                              p0[b], p1[b], p2[b], j0[b], i0[b])
            remaining[sel] = False
        K *= 2
    for t in np.nonzero(remaining)[0].tolist():
        _raster_one(Hflat, nx, ny, x0, y0, px,
                    p0[t], p1[t], p2[t], int(j0[t]), int(j1[t]),
                    int(i0[t]), int(i1[t]))
    H = Hflat.reshape(ny, nx)
    H[~np.isfinite(H)] = np.nan
    return H


def _bary(p0x, p0y, p1x, p1y, p2x, p2y, X, Y):
    """Barycentric (w0, w1, w2) of (X, Y) vs triangle."""
    import numpy as np
    d = (p1y - p2y) * (p0x - p2x) + (p2x - p1x) * (p0y - p2y)
    d = np.where(np.abs(d) < 1e-12, 1e-12, d)
    w0 = ((p1y - p2y) * (X - p2x) + (p2x - p1x) * (Y - p2y)) / d
    w1 = ((p2y - p0y) * (X - p2x) + (p0x - p2x) * (Y - p2y)) / d
    return w0, w1, 1.0 - w0 - w1


def _raster_block(Hflat, nx, ny, x0, y0, px, K, p0, p1, p2, j0, i0):
    import numpy as np
    M = p0.shape[0]
    if M == 0:
        return
    off = np.arange(K)
    J = j0[:, None, None] + off[None, None, :]
    I = i0[:, None, None] + off[None, :, None]
    X = x0 + J * px
    Y = y0 + I * px
    w0, w1, w2 = _bary(p0[:, 0, None, None], p0[:, 1, None, None],
                       p1[:, 0, None, None], p1[:, 1, None, None],
                       p2[:, 0, None, None], p2[:, 1, None, None], X, Y)
    Z = w0 * p0[:, 2, None, None] + w1 * p1[:, 2, None, None] + w2 * p2[:, 2, None, None]
    ok = ((w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
          & (J >= 0) & (J < nx) & (I >= 0) & (I < ny))
    flat = (I * nx + J)[ok]
    np.minimum.at(Hflat, flat, Z[ok])


def _raster_one(Hflat, nx, ny, x0, y0, px, p0, p1, p2, j0, j1, i0, i1):
    import numpy as np
    j0 = max(0, j0); j1 = min(nx - 1, j1)
    i0 = max(0, i0); i1 = min(ny - 1, i1)
    if j1 < j0 or i1 < i0:
        return
    gx, gy = np.meshgrid(x0 + np.arange(j0, j1 + 1) * px,
                         y0 + np.arange(i0, i1 + 1) * px)
    w0, w1, w2 = _bary(p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], gx, gy)
    inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
    z = np.where(inside, w0 * p0[2] + w1 * p1[2] + w2 * p2[2], np.inf)
    sub = Hflat.reshape(ny, nx)[i0:i1 + 1, j0:j1 + 1]
    np.minimum(sub, z, out=sub)


def _render_gpu(verts, tris, x0, y0, nx, ny, px):
    """Offscreen GPU z-min via VTK z-buffer; None if no GL context."""
    try:
        import numpy as np
        import pyvista as pv
        import vtk
        from vtkmodules.util.numpy_support import vtk_to_numpy
        faces = np.empty((len(tris), 4), dtype=np.int64)
        faces[:, 0] = 3
        faces[:, 1:] = tris
        mesh = pv.PolyData(verts, faces.ravel())
        zmin = float(verts[:, 2].min())
        zmax = float(verts[:, 2].max())
        cx = x0 + (nx - 1) * px / 2.0
        cy = y0 + (ny - 1) * px / 2.0

        rw = vtk.vtkRenderWindow()
        rw.SetOffScreenRendering(1)
        rw.SetSize(int(nx), int(ny))
        ren = vtk.vtkRenderer()
        rw.AddRenderer(ren)
        m = vtk.vtkPolyDataMapper()
        m.SetInputData(mesh)
        ac = vtk.vtkActor()
        ac.SetMapper(m)
        ren.AddActor(ac)
        cam = ren.GetActiveCamera()
        cam.ParallelProjectionOn()
        cam.SetPosition(cx, cy, zmin - 1.0)
        cam.SetFocalPoint(cx, cy, zmax + 1.0)
        cam.SetViewUp(0.0, 1.0, 0.0)
        cam.SetParallelScale(ny * px / 2.0)
        cam.SetClippingRange(0.1, (zmax - zmin) + 3.0)
        rw.Render()

        zb = vtk.vtkFloatArray()
        rw.GetZbufferData(0, 0, int(nx) - 1, int(ny) - 1, zb)
        z = vtk_to_numpy(zb).reshape(int(ny), int(nx)).astype(float)
        near, far = cam.GetClippingRange()
        H = (zmin - 1.0) + near + z * (far - near)
        H[z >= 1.0 - 1e-6] = np.nan
        return H[:, ::-1]                             # cols reversed: VTK camera basis
    except Exception as e:
        global _GPU_WARNED
        if not _GPU_WARNED:
            import sys
            sys.stderr.write("[heightcapture] GPU render unavailable, using CPU: "
                             "%r\n" % e)
            _GPU_WARNED = True
        return None


def render_heightmap(oriented, params, px=None, margin=None):
    """Render z-min heightmap; GPU primary, CPU fallback. Memoised."""
    import numpy as np
    override = px is not None
    px = float(px) if override else _pixel_size(params)
    defl = max(2.0 * px, 0.2) if override else _render_deflection(params)
    if margin is None:
        margin = (float(params.part_clearance)
                  + float(getattr(params, "mouth_chamfer", 0.0)) + 2.0 * px)
    margin = float(margin)
    key = (id(oriented), round(px, 5), round(defl, 5), round(margin, 4))
    hit = _HM_CACHE.get(key)
    if hit is not None:
        _HM_CACHE.move_to_end(key)
        return hit[1]

    verts, tris = _mesh(oriented, params, defl)
    verts = np.asarray(verts, dtype=float)
    tris = np.asarray(tris, dtype=np.int64)
    x0, y0, nx, ny = _grid_bounds(verts, px, margin)

    import sys
    want = _backend()
    H = None
    if want in ("auto", "gpu"):
        g = _render_gpu(verts, tris, x0, y0, nx, ny, px)
        if g is None and want == "gpu":
            raise RuntimeError("PARTSPACK_DEPTH_BACKEND=gpu but no GL context")
        if g is not None:
            if _verify():
                c = _render_cpu(verts, tris, x0, y0, nx, ny, px)
                cov, med = _agree(g, c)
                ok = cov > 0.9 and med < max(0.5, px)
                sys.stderr.write("[heightcapture] GPU vs CPU: coverage=%.3f "
                                 "med_dz=%.3fmm -> using %s\n"
                                 % (cov, med, "GPU" if ok else "CPU"))
                H = g if ok else c
            else:
                H = g
    if H is None:
        H = _render_cpu(verts, tris, x0, y0, nx, ny, px)
    hm = Heightmap(H, x0, y0, px)
    _HM_CACHE[key] = (oriented, hm)         # strong ref pins id()
    _HM_CACHE.move_to_end(key)
    if len(_HM_CACHE) > _HM_MAX:
        _HM_CACHE.popitem(last=False)
    return hm


# Node-snap grid (mm): coincides ULP-mismatched shared nodes so polygonize closes rings.
_NODE_GRID = 1e-7


def _segments_to_shapely(segs):
    """Assemble boundary segments into shapely geom via polygonize."""
    if not segs:
        return None
    import shapely
    from shapely.geometry import LineString
    from shapely.ops import unary_union, polygonize
    lines = [LineString([a, b]) for a, b in segs
             if (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 > 1e-18]
    if not lines:
        return None
    noded = shapely.set_precision(unary_union(lines), _NODE_GRID)
    polys = list(polygonize(noded))
    if not polys:
        return None
    geom = unary_union([p.buffer(0) for p in polys])
    return None if geom.is_empty else geom


def _mask_to_polygon(mask, hm):
    """Trace boolean pixel mask boundary into shapely geom."""
    return _segments_to_shapely(_mask_edges(mask, hm.px, hm.x0, hm.y0))


def _mask_edges(mask, px, x0, y0):
    """Boundary unit-edges of boolean pixel mask, world coords."""
    import numpy as np
    try:
        from scipy.ndimage import binary_fill_holes
        mask = binary_fill_holes(mask)
    except Exception:
        pass
    ny, nx = mask.shape
    pad = np.zeros((ny + 2, nx + 2), dtype=bool)
    pad[1:-1, 1:-1] = mask
    segs = []
    I, k = np.nonzero(pad[:, 1:] ^ pad[:, :-1])
    xv = x0 + (k - 0.5) * px
    yv0 = y0 + (I - 1.5) * px
    yv1 = y0 + (I - 0.5) * px
    for n in range(I.size):
        segs.append(((float(xv[n]), float(yv0[n])), (float(xv[n]), float(yv1[n]))))
    k2, J = np.nonzero(pad[1:, :] ^ pad[:-1, :])
    yh = y0 + (k2 - 0.5) * px
    xh0 = x0 + (J - 1.5) * px
    xh1 = x0 + (J - 0.5) * px
    for n in range(k2.size):
        segs.append(((float(xh0[n]), float(yh[n])), (float(xh1[n]), float(yh[n]))))
    return segs


def _h_range(H):
    import numpy as np
    f = H[np.isfinite(H)]
    return "empty" if f.size == 0 else "%.2f..%.2f" % (float(f.min()), float(f.max()))


def bottom_section(oriented, params, band_base):
    """Lowest meaningful footprint from heightmap."""
    import numpy as np
    hm = render_heightmap(oriented, params)
    z0 = float(band_base)
    step = _capture_step(params)
    n = max(1, int((float(params.hold_height) / 3.0) / step))
    finite = np.isfinite(hm.H)
    for k in range(1, n + 1):
        mask = finite & (hm.H <= z0 + k * step)
        if not mask.any():
            continue
        poly = _mask_to_polygon(mask, hm)
        if poly is not None and not poly.is_empty \
                and poly.area > params.min_island_area:
            return poly.buffer(0)
    return None
