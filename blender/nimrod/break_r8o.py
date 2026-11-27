"""Open break ends for the Nimrod Mk I / FD-32 (and any MeshBuf-built part), after the r8o break pattern (2026-11-22).

User (after the r8o damage check): "The Nimrod and FD-32 need to be changed as well". Every break face of these two was closed by a
solid 'structure' disc or full rib (fuselage tank / rear bulkheads 60-65 mm in, upper-wing full ribs 75 mm in, lower-wing / stab root
fillet discs, the fin root rib in the plane). Stock break ends are open hollow shells with frames set back. The r8o / B-25H v3
pattern, generic here (no bpy; mathutils only):
  * no cap in the break plane;
  * the inner skin / liner ends with a dark band (BAND = 25 mm, 'metal_dark') and a dark skin edge strip at the plane: through a
    hairline joint one sees dark, never light or sky (seam backing);
  * an open rib at the setback: a perimeter CAP STRIP only (<= CAP_W, <= CAP_FRAC of the local depth, two faces 4 mm apart + edge),
    or an open fuselage frame ring (nimrod_structure.frame_ring);
  * stubs end 15-40 mm short of the plane;
  * a lined cavity ends in a bay-end wall in the liner paint (>= 0.25 m in).
Every function takes the part's own paint mesh (MeshBuf) and builds NEW faces only: paint faces, UVs and the livery atlas are untouched.
"""
import math
from mathutils import Vector as V
from mathutils.geometry import tessellate_polygon
from b25h_geom import MeshBuf, oriented_quad
import nimrod_structure as ST

BAND = 0.025            # dark band at the open end of every liner (m)
CAP_W = 0.025           # cap-strip flange (m)
CAP_FRAC = 0.12         # ... at most this share of the local section depth
EDGE_IN = 0.0015        # rib / wall outline this far inside the outer skin (between skin and liner: no slit)
STUB_SHORT = (0.015, 0.040)


def depth(p, p0, n_out):
    """distance of p inside the part from the break plane (p0, unit normal n_out pointing OUT of the part)."""
    return (V(p0) - V(p)).dot(V(n_out))


def copy_faces(src, mats=('paint',), select=None):
    tmp = MeshBuf()
    tmp.verts = list(src.verts)
    for f in src.faces:
        if f['mat'] not in mats:
            continue
        if select is not None and not select(sum((src.verts[i] for i in f['idx']), V()) / len(f['idx'])):
            continue
        tmp.faces.append(dict(idx=list(f['idx']), mat='paint', uv=f['uv'], smooth=f.get('smooth', True)))
    return tmp


def _clip(mb, p0, keep_dir):
    out = MeshBuf(); out.verts = list(mb.verts); out.faces = [dict(f) for f in mb.faces]
    ST.clip_faces(out, V(p0), V(keep_dir))
    return out


def _skin(piece, t, inner, edge_mat):
    n0 = len(piece.faces)
    ST.double_skin(piece, t=t, mats=('paint',), inner=inner, edge_mat=edge_mat)
    add = MeshBuf(); add.verts = piece.verts; add.faces = piece.faces[n0:]
    return add


def liner(src, ends, t=0.004, inner='fabric_in', select=None, mats=('paint',), close=None, band=BAND, band_mat='metal_dark',
          edge_mat='structure'):
    """inner skin of src's faces (mats, select(centre)) offset t inward, split at every open end: the first `band` metres inside each
    end plane drawn in band_mat (+ its edge strips at the plane in band_mat), the rest in inner (a name or inner(face, centre)).
    ends = [(p0, n_out)]; close (single end): the liner stops `close` inside the plane. Returns a MeshBuf: the main liner FIRST (its
    material is the struct renderer's material[0], which the Unity seam-cove check expects to be the liner), then the bands."""
    inner_fn = inner if callable(inner) else (lambda f, c, m=inner: m)
    base = copy_faces(src, mats, select)
    if close is not None:
        p0, n = ends[0]
        base = _clip(base, V(p0) - V(n) * close, V(n))
    main = base
    bands = []
    for p0, n in (ends if band > 0 else ()):
        p0, n = V(p0), V(n)
        piece = _clip(_clip(base, p0, -n), p0 - n * band, n)       # 0 <= depth <= band
        if piece.faces:
            bands.append(piece)
        main = _clip(main, p0 - n * band, -n)                       # depth >= band
    out = MeshBuf()
    if main.faces:
        out.extend(_skin(main, t, inner_fn, edge_mat))
    for b in bands:
        out.extend(_skin(b, t, lambda f, c: band_mat, band_mat))
    return out


# ------------------------------------------------------------------------------------------- sections
def _basis(n):
    n = V(n).normalized()
    ref = V((0, 0, 1)) if abs(n.z) < 0.9 else V((1, 0, 0))
    u = (ref - n * ref.dot(n)).normalized()
    return u, n.cross(u)


def section_loop(src, q0, n, mats=('paint', 'cove')):
    """the outline of src's skin (faces in mats) cut by the plane (q0, n): the longest closed loop of chained segments (3D points)."""
    q0, n = V(q0), V(n).normalized()
    segs = []
    for f in src.faces:
        if f['mat'] not in mats:
            continue
        P = [src.verts[i] for i in f['idx']]
        d = [(p - q0).dot(n) for p in P]
        pts = []
        for k in range(len(P)):
            a, b, da, db = P[k], P[(k + 1) % len(P)], d[k], d[(k + 1) % len(P)]
            if (da < 0) != (db < 0):
                pts.append(a + (b - a) * (da / (da - db)))
        if len(pts) == 2 and (pts[0] - pts[1]).length > 1e-6:
            segs.append(pts)
    if not segs:
        return []
    key = lambda p: (round(p.x, 5), round(p.y, 5), round(p.z, 5))
    adj = {}
    for s_ in segs:
        a, b = key(s_[0]), key(s_[1])
        adj.setdefault(a, []).append((b, s_[1]))
        adj.setdefault(b, []).append((a, s_[0]))
    pos = {}
    for s_ in segs:
        pos[key(s_[0])] = s_[0]; pos[key(s_[1])] = s_[1]
    seen = set()
    best = []
    for k0 in adj:
        if k0 in seen:
            continue
        loop = [pos[k0]]; seen.add(k0); cur = k0; prev = None
        while True:
            nxt = [k for k, _ in adj[cur] if k != prev and k not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur); loop.append(pos[cur])
        if len(loop) > len(best):
            best = loop
    # drop near-duplicate points
    out = []
    for p in best:
        if not out or (p - out[-1]).length > 2e-4:
            out.append(p)
    if len(out) > 2 and (out[0] - out[-1]).length < 2e-4:
        out.pop()
    return out


def _inward(loop, n):
    """per point of a closed planar loop: unit inward direction in the plane and the local section depth along it (2D ray)."""
    u, w = _basis(n)
    P = [(p.dot(u), p.dot(w)) for p in loop]
    m = len(P)
    area = sum(P[i][0] * P[(i + 1) % m][1] - P[(i + 1) % m][0] * P[i][1] for i in range(m)) / 2
    sg = 1.0 if area > 0 else -1.0                         # CCW: inward = left normal
    out = []
    for i in range(m):
        a, b, c = P[i - 1], P[i], P[(i + 1) % m]
        e1 = (b[0] - a[0], b[1] - a[1]); e2 = (c[0] - b[0], c[1] - b[1])
        def ln(e):
            L = math.hypot(*e) or 1.0
            return (-e[1] / L * sg, e[0] / L * sg)
        n1, n2 = ln(e1), ln(e2)
        nx, ny = n1[0] + n2[0], n1[1] + n2[1]
        L = math.hypot(nx, ny)
        if L < 1e-9:
            nx, ny = n2; L = 1.0
        nx, ny = nx / L, ny / L
        # local depth: first crossing of the ray b + s (nx, ny) with the loop (other than the adjacent edges)
        D = 9.0
        for j in range(m):
            if j in (i, (i - 1) % m):
                continue
            p, q = P[j], P[(j + 1) % m]
            ex, ey = q[0] - p[0], q[1] - p[1]
            den = nx * ey - ny * ex
            if abs(den) < 1e-12:
                continue
            s = ((p[0] - b[0]) * ey - (p[1] - b[1]) * ex) / den
            r = ((p[0] - b[0]) * ny - (p[1] - b[1]) * nx) / den
            if s > 1e-6 and -1e-9 <= r <= 1 + 1e-9:
                D = min(D, s)
        out.append((u * nx + w * ny, D))
    return out


def cap_strip(mb, src, p0, n_out, d, mat='metal_dark', w=CAP_W, frac=CAP_FRAC, gap=0.004, mats=('paint', 'cove')):
    """open rib d inside the plane: a perimeter flange (two faces `gap` apart + the inner edge), the centre of the section open."""
    p0, n = V(p0), V(n_out).normalized()
    loop = section_loop(src, p0 - n * d, n, mats)
    if len(loop) < 3:
        return 0
    inw = _inward(loop, n)
    o_ = [p + v * min(EDGE_IN, 0.2 * D) for p, (v, D) in zip(loop, inw)]
    i_ = [p + v * min(EDGE_IN + w, frac * D) for p, (v, D) in zip(loop, inw)]
    m = len(loop); cnt = 0
    for j in range(m):
        j1 = (j + 1) % m
        if (i_[j] - o_[j]).length < 0.0015 and (i_[j1] - o_[j1]).length < 0.0015:
            continue
        for sg in (1, -1):
            off = n * (gap / 2 * sg)
            oriented_quad(mb, [o_[j] + off, o_[j1] + off, i_[j1] + off, i_[j] + off], mat, n * sg)
        e = [i_[j] + n * gap / 2, i_[j1] + n * gap / 2, i_[j1] - n * gap / 2, i_[j] - n * gap / 2]
        inw_ = (inw[j][0] + inw[j1][0])
        if inw_.length > 1e-6:                                     # inner edge: closes the flange (no see-through between its faces)
            oriented_quad(mb, e, mat, inw_)
        cnt += 1
    return cnt


def polygon_fill(mb, loops3, n, mat, toward):
    """fill planar loops (outer + holes) lying in a plane with normal n; faces oriented toward `toward`."""
    u, w = _basis(n)
    flat = [[V((p.dot(u), p.dot(w), 0.0)) for p in lp] for lp in loops3]
    allp = [p for lp in loops3 for p in lp]
    tris = tessellate_polygon(flat)
    for t in tris:
        oriented_quad(mb, [allp[k] for k in t], mat, toward)
    return len(tris)


def bay_wall(mb, src, p0, n_out, d, mat='fabric_in', both=True, gap=0.004, mats=('paint', 'cove')):
    """bay-end wall d inside the plane (the end of the lined cavity), outline EDGE_IN inside the skin, facing the break (+ the far side)."""
    p0, n = V(p0), V(n_out).normalized()
    loop = section_loop(src, p0 - n * d, n, mats)
    if len(loop) < 3:
        return 0
    inw = _inward(loop, n)
    lp = [p + v * min(EDGE_IN, 0.2 * D) for p, (v, D) in zip(loop, inw)]
    k = polygon_fill(mb, [[p + n * gap / 2 for p in lp]], n, mat, n)
    if both:
        k += polygon_fill(mb, [[p - n * gap / 2 for p in lp]], n, mat, -n)
    return k


def inset_ring(ring, n, d, frac=0.3):
    """a planar ring (plane normal n) moved inward by d (at most frac of the local depth)."""
    inw = _inward(ring, n)
    return [p + v * min(d, frac * D) for p, (v, D) in zip(ring, inw)]


def stub_len(r, depth0):
    """length of a stub from a rib `depth0` inside the plane to STUB_SHORT short of it."""
    return depth0 - r.uniform(*STUB_SHORT)
