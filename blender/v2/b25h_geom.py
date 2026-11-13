"""Pure geometry helpers for the B-25H v2 model (no bpy; uses mathutils only).

All geometry is built in WORLD space (Blender: nose +Y, up +Z, right wing +X, metres).
A MeshBuf collects vertices and faces; every face carries a material name and, for
`paint` faces, a per-corner `livery` UV in metres (packed into 0-1 later).
"""
import math
from mathutils import Vector, Matrix, Quaternion

V = Vector


class MeshBuf:
    def __init__(self):
        self.verts = []
        self.faces = []   # dict(idx, mat, uv(list of (u,v)) or None, smooth)

    def v(self, p):
        self.verts.append(V(p))
        return len(self.verts) - 1

    def face(self, idx, mat, uv=None, smooth=True):
        idx = list(idx)
        # drop consecutive duplicates (degenerate corners)
        if len(set(idx)) < 3:
            return
        if mat == 'paint' and uv is None:
            pts = [self.verts[i] for i in idx]
            n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
            if n.length < 1e-12 and len(pts) > 3:
                n = (pts[2] - pts[0]).cross(pts[3] - pts[0])
            uv = [planar_uv(p, n) for p in pts]
        self.faces.append(dict(idx=idx, mat=mat, uv=uv, smooth=smooth))

    def poly(self, pts, mat, uv=None, smooth=True):
        """add a polygon from points (new verts)."""
        self.face([self.v(p) for p in pts], mat, uv, smooth)

    def extend(self, other):
        off = len(self.verts)
        self.verts += [V(p) for p in other.verts]
        for f in other.faces:
            self.faces.append(dict(idx=[i + off for i in f['idx']], mat=f['mat'], uv=f['uv'], smooth=f['smooth']))

    def tri_count(self):
        return sum(len(f['idx']) - 2 for f in self.faces)


def lerp(a, b, t):
    return a + (b - a) * t


def interp_table(table, x):
    """table: sorted list of (x, value-tuple); linear interpolation, clamped."""
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    for (x0, v0), (x1, v1) in zip(table, table[1:]):
        if x0 <= x <= x1:
            t = (x - x0) / (x1 - x0) if x1 != x0 else 0
            return tuple(a + (b - a) * t for a, b in zip(v0, v1))
    return table[-1][1]


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------------------- rings
# Rounded-rectangle ring (fuselage). Counts per half, starting at bottom centre, going
# around the +X side to top centre, then down the -X side.
RR_COUNTS = (3, 5, 6, 8, 3)   # bottom flat, bottom corner, side, top corner, top flat
RR_HALF = sum(RR_COUNTS)      # segments per half (25)
RR_N = 2 * RR_HALF            # points per ring (50)


def rr_category(j):
    """category of ring segment j (between point j and j+1)."""
    k = j if j < RR_HALF else (2 * RR_HALF - 1 - j)
    names = ('bflat', 'bcorner', 'side', 'tcorner', 'tflat')
    acc = 0
    for n, c in zip(names, RR_COUNTS):
        if k < acc + c:
            return n
        acc += c
    return 'tflat'


def rr_ring(y, hw, zb, zt, rt, rb):
    """rounded-rectangle ring at station y; returns RR_N points."""
    hw = max(hw, 1e-4)
    rb = min(rb, hw, (zt - zb) * 0.5)
    rt = min(rt, hw, (zt - zb) - rb)
    nbf, nbc, ns, ntc, ntf = RR_COUNTS
    half = []
    for k in range(nbf):                       # bottom flat
        half.append((lerp(0, hw - rb, k / nbf), zb))
    for k in range(nbc):                       # bottom corner
        a = -math.pi / 2 + (math.pi / 2) * k / nbc
        half.append((hw - rb + rb * math.cos(a), zb + rb + rb * math.sin(a)))
    for k in range(ns):                        # side
        half.append((hw, lerp(zb + rb, zt - rt, k / ns)))
    for k in range(ntc):                       # top corner
        a = (math.pi / 2) * k / ntc
        half.append((hw - rt + rt * math.cos(a), zt - rt + rt * math.sin(a)))
    for k in range(ntf):                       # top flat
        half.append((lerp(hw - rt, 0, k / ntf), zt))
    half.append((0.0, zt))                     # top centre (index RR_HALF)
    pts = [V((x, y, z)) for x, z in half]
    for x, z in reversed(half[1:-1]):
        pts.append(V((-x, y, z)))
    assert len(pts) == RR_N
    return pts


def superellipse_ring(cx, y, cz, hw, hz_top, hz_bot, n=2.0, N=40, start_top=True):
    """ring in the XZ plane at station y; point 0 at top (start_top) going toward +X."""
    pts = []
    for j in range(N):
        a = 2 * math.pi * j / N
        s, c = math.sin(a), math.cos(a)       # a=0 -> top
        if not start_top:
            c = -c
        x = cx + hw * math.copysign(abs(s) ** (2.0 / n), s)
        hz = hz_top if c >= 0 else hz_bot
        z = cz + hz * math.copysign(abs(c) ** (2.0 / n), c)
        pts.append(V((x, y, z)))
    return pts


def circle_pts(center, axis, radius, N, ref=None, phase=0.0):
    """points of a circle around `axis` through center. ref: direction of point 0."""
    axis = V(axis).normalized()
    if ref is None:
        ref = V((0, 0, 1)) if abs(axis.z) < 0.9 else V((1, 0, 0))
    u = (V(ref) - axis * V(ref).dot(axis)).normalized()
    w = axis.cross(u)
    out = []
    for j in range(N):
        a = phase + 2 * math.pi * j / N
        out.append(V(center) + (u * math.cos(a) + w * math.sin(a)) * radius)
    return out


def arc_lengths(ring):
    acc = [0.0]
    for a, b in zip(ring, ring[1:]):
        acc.append(acc[-1] + (b - a).length)
    return acc, acc[-1] + (ring[0] - ring[-1]).length


# ----------------------------------------------------------------------------- loft
def loft(mb, rings, mat, closed=True, outward=True, face_mat=None, uvfunc=None, keep=None, smooth=True):
    """quad strips between consecutive rings (same point count).

    Orientation is chosen so normals point away from each ring's centroid (outward=True)
    or toward it. face_mat(i,j)->material overrides mat. keep(i,j)->bool skips faces.
    uvfunc(i,j,corner_ring_index, corner_point_index)->(u,v) for paint faces.
    Returns the index grid of vertices.
    """
    n = len(rings[0])
    grid = [[mb.v(p) for p in r] for r in rings]
    segs = n if closed else n - 1
    # orientation test on a representative face
    flip = None
    for i in range(len(rings) - 1):
        cen = sum(rings[i], V()) / n
        score = 0.0
        for j in range(segs):
            a, b = rings[i][j], rings[i][(j + 1) % n]
            d = rings[i + 1][j]
            nrm = (b - a).cross(d - a)
            mid = (a + b + d) / 3
            score += nrm.dot(mid - cen)
        if abs(score) > 1e-12:
            flip = score < 0
            break
    if flip is None:
        flip = False
    if not outward:
        flip = not flip
    for i in range(len(rings) - 1):
        for j in range(segs):
            if keep is not None and not keep(i, j):
                continue
            j1 = (j + 1) % n
            corners = [(i, j), (i, j1), (i + 1, j1), (i + 1, j)]
            if flip:
                corners = [corners[0], corners[3], corners[2], corners[1]]
            m = face_mat(i, j) if face_mat else mat
            uv = None
            if uvfunc is not None and m == 'paint':
                uv = [uvfunc(ci, cj, j) for ci, cj in corners]
            mb.face([grid[ci][cj] for ci, cj in corners], m, uv, smooth)
    return grid, flip


def fan_cap(mb, ring, center, mat, toward, uvfunc=None, smooth=False):
    """triangle fan closing a ring; normal oriented along `toward` (a direction)."""
    c = V(center)
    n = len(ring)
    for j in range(n):
        a, b = ring[j], ring[(j + 1) % n]
        nrm = (a - c).cross(b - c)
        pts = [c, a, b] if nrm.dot(V(toward)) >= 0 else [c, b, a]
        uv = [uvfunc(p) for p in pts] if uvfunc else None
        mb.poly(pts, mat, uv, smooth)


def annulus(mb, outer, inner, mat, toward, smooth=False):
    n = len(outer)
    for j in range(n):
        j1 = (j + 1) % n
        q = [outer[j], outer[j1], inner[j1], inner[j]]
        nrm = (q[1] - q[0]).cross(q[3] - q[0])
        if nrm.length < 1e-12:
            nrm = (q[2] - q[1]).cross(q[0] - q[1])
        if nrm.dot(V(toward)) < 0:
            q = [q[0], q[3], q[2], q[1]]
        mb.poly(q, mat, None, smooth)


def oriented_quad(mb, q, mat, toward, uv=None, smooth=False):
    nrm = (V(q[1]) - V(q[0])).cross(V(q[-1]) - V(q[0]))
    if nrm.dot(V(toward)) < 0:
        q = [q[0]] + list(reversed(q[1:]))
        if uv:
            uv = [uv[0]] + list(reversed(uv[1:]))
    mb.poly(q, mat, uv, smooth)


# ----------------------------------------------------------------------------- primitives
def cylinder(mb, p0, p1, r0, r1=None, N=12, mat='metal_dark', cap0=True, cap1=True, ref=None, smooth=True):
    r1 = r0 if r1 is None else r1
    ax = V(p1) - V(p0)
    ring0 = circle_pts(p0, ax, r0, N, ref)
    ring1 = circle_pts(p1, ax, r1, N, ref)
    loft(mb, [ring0, ring1], mat, smooth=smooth)
    if cap0:
        fan_cap(mb, ring0, p0, mat, -ax)
    if cap1:
        fan_cap(mb, ring1, p1, mat, ax)


def tube(mb, p0, p1, r_out, r_in, N=12, mat='metal_dark'):
    """hollow barrel (gun muzzle look)."""
    ax = V(p1) - V(p0)
    o0, o1 = circle_pts(p0, ax, r_out, N), circle_pts(p1, ax, r_out, N)
    i0, i1 = circle_pts(p0, ax, r_in, N), circle_pts(p1, ax, r_in, N)
    loft(mb, [o0, o1], mat)
    loft(mb, [i0, i1], mat, outward=False)
    annulus(mb, o1, i1, mat, ax)
    annulus(mb, o0, i0, mat, -ax)
    fan_cap(mb, circle_pts(V(p1) - ax.normalized() * 0.03, ax, r_in, N), V(p1) - ax.normalized() * 0.03, 'metal_dark', ax)


def box(mb, center, size, mat, rot=None, uvscale=None):
    c = V(center)
    sx, sy, sz = (s * 0.5 for s in size)
    R = rot.to_matrix() if rot is not None else Matrix.Identity(3)
    P = lambda x, y, z: c + R @ V((x, y, z))
    faces = [((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1), (0, -1, 0)),
             ((1, 1, -1), (-1, 1, -1), (-1, 1, 1), (1, 1, 1), (0, 1, 0)),
             ((-1, 1, -1), (-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 0, 0)),
             ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1), (1, 0, 0)),
             ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1), (0, 0, 1)),
             ((-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1), (0, 0, -1))]
    for a, b, cc, d, n in faces:
        q = [P(a[0] * sx, a[1] * sy, a[2] * sz), P(b[0] * sx, b[1] * sy, b[2] * sz),
             P(cc[0] * sx, cc[1] * sy, cc[2] * sz), P(d[0] * sx, d[1] * sy, d[2] * sz)]
        uv = None
        if mat == 'paint':
            nn = R @ V(n)
            uv = [planar_uv(p, nn) for p in q]
        oriented_quad(mb, q, mat, R @ V(n), uv)


def planar_uv(p, n):
    n = V(n)
    ax = max(range(3), key=lambda i: abs(n[i]))
    if ax == 0:
        return (p.y, p.z)
    if ax == 1:
        return (p.x, p.z)
    return (p.x, p.y)


def double_sided_quad(mb, q, mat, toward):
    oriented_quad(mb, q, mat, toward)
    oriented_quad(mb, q, mat, -V(toward))


def extrude_profile_x(mb, prof_yz, x0, x1, mat, double=True):
    """extrude a closed polygon in the YZ plane between x0 and x1 (walls + end caps).
    End caps are triangulated by ear clipping. Used for the bomb bay and wells."""
    n = len(prof_yz)
    a = [V((x0, y, z)) for y, z in prof_yz]
    b = [V((x1, y, z)) for y, z in prof_yz]
    for j in range(n):
        j1 = (j + 1) % n
        q = [a[j], a[j1], b[j1], b[j]]
        mb.poly(q, mat)
        if double:
            mb.poly(list(reversed(q)), mat)
    tris = ear_clip(prof_yz)
    for t in tris:
        for X, sgn in ((x0, 1), (x1, -1)):
            pts = [V((X, prof_yz[k][0], prof_yz[k][1])) for k in t]
            oriented_quad(mb, pts, mat, V((sgn, 0, 0)))
            if double:
                oriented_quad(mb, pts, mat, V((-sgn, 0, 0)))


def ear_clip(poly):
    """triangulate a simple 2D polygon; returns index triples."""
    idx = list(range(len(poly)))
    area = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in idx)
    ccw = area > 0
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def inside(p, a, b, c):
        d1, d2, d3 = cross(a, b, p), cross(b, c, p), cross(c, a, p)
        neg = d1 < 0 or d2 < 0 or d3 < 0
        pos = d1 > 0 or d2 > 0 or d3 > 0
        return not (neg and pos)

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            cr = cross(a, b, c)
            if (cr > 0) != ccw or abs(cr) < 1e-12:
                continue
            if any(inside(poly[m], a, b, c) for m in idx if m not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


# ----------------------------------------------------------------------------- airfoils
def naca_pts(s, t, m=0.02, p=0.4):
    """NACA 4-digit: returns (upper (x,z), lower (x,z)) at chord fraction s."""
    yt = 5 * t * (0.2969 * math.sqrt(max(s, 0)) - 0.1260 * s - 0.3516 * s ** 2 + 0.2843 * s ** 3 - 0.1036 * s ** 4)
    if s < p:
        yc = m / p ** 2 * (2 * p * s - s * s)
        dy = 2 * m / p ** 2 * (p - s)
    else:
        yc = m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * s - s * s)
        dy = 2 * m / (1 - p) ** 2 * (p - s)
    th = math.atan(dy)
    yt = max(yt, 0.0025)
    return (s - yt * math.sin(th), yc + yt * math.cos(th)), (s + yt * math.sin(th), yc - yt * math.cos(th))


def cos_space(a, b, n, le_dense=True):
    """n+1 values from a to b, clustered toward a (the leading edge) when le_dense."""
    out = []
    for k in range(n + 1):
        t = k / n
        if le_dense:
            t = 1 - math.cos(t * math.pi / 2)
        out.append(a + (b - a) * t)
    return out


class Station:
    """one chordwise section of a lifting surface.
    le: 3D leading-edge point; cdir: unit chord direction (LE->TE); up: unit thickness
    direction; chord: length; t: thickness ratio; camber m."""

    def __init__(self, span, le, cdir, up, chord, t, m=0.02):
        self.span, self.le, self.cdir, self.up = span, V(le), V(cdir).normalized(), V(up).normalized()
        self.chord, self.t, self.m = chord, t, m

    def point(self, s, upper):
        u, l = naca_pts(s, self.t, self.m)
        xz = u if upper else l
        return self.le + self.cdir * (xz[0] * self.chord) + self.up * (xz[1] * self.chord)


def box_ring(st, s_end, n=12):
    """closed ring for the main box: upper from s_end -> LE, lower LE -> s_end."""
    ss = cos_space(0.0, s_end, n)
    up = [st.point(s, True) for s in reversed(ss)]
    lo = [st.point(s, False) for s in ss[1:]]
    return up + lo, ss


def aft_ring(st, s0, n=5):
    """closed ring for an aft piece (flap/aileron/fixed TE): upper TE -> s0, lower s0 -> TE."""
    ss = [s0 + (1 - s0) * k / n for k in range(n + 1)]
    up = [st.point(s, True) for s in reversed(ss)]
    lo = [st.point(s, False) for s in ss]
    return up + lo, ss


def section_cap(mb, ring, mat, toward, uvfunc=None):
    """close a box/aft ring (upper half then lower half, symmetric counts) with quads."""
    n = len(ring)
    if n % 2 == 1:   # box ring: upper (k+1 pts) + lower (k pts), LE shared
        k = (n - 1) // 2
        up = ring[:k + 1]            # s_end..LE
        lo = [ring[k]] + ring[k + 1:]  # LE..s_end
        up = list(reversed(up))      # LE..s_end
        for i in range(k):
            q = [up[i], up[i + 1], lo[i + 1], lo[i]]
            if (q[0] - q[3]).length < 1e-7:
                q = [up[i], up[i + 1], lo[i + 1]]
            uv = [uvfunc(p) for p in q] if uvfunc else None
            oriented_quad(mb, q, mat, toward, uv)
    else:
        k = n // 2
        up = list(reversed(ring[:k]))   # s0..TE
        lo = ring[k:]                   # s0..TE
        for i in range(k - 1):
            q = [up[i], up[i + 1], lo[i + 1], lo[i]]
            uv = [uvfunc(p) for p in q] if uvfunc else None
            oriented_quad(mb, q, mat, toward, uv)


def ring_arc_uv(rings, span_vals):
    """uvfunc for a closed loft: u = span value of the ring, v = arc length along the ring.
    The closing segment (last point -> point 0) uses v = perimeter for point 0 so it does not
    wrap back over the island."""
    al = [arc_lengths(r) for r in rings]
    n = len(rings[0])

    def f(ci, cj, j):
        acc, P = al[ci]
        if cj == 0 and j == n - 1:
            return (span_vals[ci], P)
        return (span_vals[ci], acc[cj])
    return f


def surface(mb, stations, s_from, s_to, mat='paint', cap0=None, cap1=None, cap_mat='structure',
            n_box=12, n_aft=5, uv=True, hinge_mat='structure', front_mat='paint', inset=0.0):
    """Loft a box (s_from=0, s_to=hinge) or an aft piece (s_from=hinge) over stations.
    cap0/cap1: direction vectors for end caps (None = no cap)."""
    if s_from <= 0.0:
        rings = [box_ring(st, s_to, n_box)[0] for st in stations]
        nseg = len(rings[0])
        last = nseg - 1   # closing segment = hinge wall

        def fm(i, j):
            return hinge_mat if j == last else mat
    else:
        rings = [aft_ring(st, s_from + inset, n_aft)[0] for st in stations]
        nseg = len(rings[0])
        k = nseg // 2

        def fm(i, j):
            return front_mat if j == k - 1 else mat
    spans = [st.span for st in stations]
    uvf = ring_arc_uv(rings, spans) if uv else None
    loft(mb, rings, mat, closed=True, face_mat=fm, uvfunc=uvf)
    cm = cap_mat
    if cap0 is not None:
        section_cap(mb, rings[0], cm, cap0, (lambda p: planar_uv(p, cap0)) if cm == 'paint' else None)
    if cap1 is not None:
        section_cap(mb, rings[-1], cm, cap1, (lambda p: planar_uv(p, cap1)) if cm == 'paint' else None)
    return rings


def frame_from_axes(xaxis, zhint=V((0, 0, 1))):
    x = V(xaxis).normalized()
    z = (V(zhint) - x * V(zhint).dot(x)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed()
    return m.to_quaternion()
