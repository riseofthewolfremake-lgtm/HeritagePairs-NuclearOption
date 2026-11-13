"""1.8.17 B-17G nose to the reference (user: the nose does not match the War Thunder B-17G-60-VE).

Numbers measured on the reference in our frame (render_proof188 frame, 31.62 m span; ray-cast maps, numbers only, kept outside the repo in
nuclearoption-ref/study/b17g_nose/measure). Nothing of the reference mesh or textures is used. b17g_spec.NOSE1817 switches all of it.

- skin cutter: exact polygon cuts of the fuselage skin (side or top / bottom projection) on the flat skin triangles: windows (pieces inside
  become glass), openings (dropped). Replaces the anchored-ring windows (sawtooth-free, any outline, rounded corners).
- windows: navigator windows (2 left, 1 right), the right forward window, the top window, the astrodome.
- K-5 cheek guns: the staggered projecting window frames (a side pane that stands out more toward its front, an angled planar front face
  with two small panes over a socket plate with the gun hole at the cheek pivot, wedge closures top / bottom).
- chin turret: an exact round opening and the long keel (teardrop) fairing from the turret aft along the nose underside.
- glazed cone: frame ring at its base and the bombardier's optical-flat frame low at the front (no meridian bars).
- the mast on the nose top.
"""
import math
from mathutils import Vector as V
import b17g_spec as S
from b25h_geom import MeshBuf, oriented_quad, loft, fan_cap, circle_pts
import nimrod_structure as NS

LOG = {}


# ============================================================================================ skin surface (analytic)
def skin_x(y, z, inset=0.0):
    top, bot, hw, n = S.fus_station(y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    t = min(abs(z - cz) / hz, 0.999999)
    return max(hw - inset, 0.01) * (1 - t ** n) ** (1.0 / n)


def skin_z(x, y, upper=True):
    top, bot, hw, n = S.fus_station(y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    u = min(abs(x) / hw, 0.999999)
    d = hz * (1 - u ** n) ** (1.0 / n)
    return cz + d if upper else cz - d


def skin_normal(p):
    top, bot, hw, n = S.fus_station(p.y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    dx, dz = p.x, p.z - cz
    gx = n * abs(dx) ** (n - 1) * math.copysign(1.0, dx) / hw ** n if abs(dx) > 1e-9 else 0.0
    gz = n * abs(dz) ** (n - 1) * math.copysign(1.0, dz) / hz ** n if abs(dz) > 1e-9 else 0.0
    g = V((gx, 0.0, gz))
    return g.normalized() if g.length > 1e-12 else V((0, 0, 1))


def side_pt(y, z, sgn, out=0.0):
    """point on the side skin (sgn +1 right / -1 left) at (y, z), `out` metres along the outward skin normal (negative = inside)."""
    p = V((sgn * skin_x(y, z), y, z))
    return p + skin_normal(p) * out


def top_pt(y, x, out=0.0, upper=True):
    p = V((x, y, skin_z(x, y, upper)))
    return p + skin_normal(p) * out


# ============================================================================================ polygons
def rounded_rect(u0, u1, v0, v1, rc, k=5):
    """CCW rounded rectangle in (u, v)."""
    rc = min(rc, (u1 - u0) / 2 - 1e-4, (v1 - v0) / 2 - 1e-4)
    out = []
    for cu, cv, a0 in ((u1 - rc, v0 + rc, -90), (u1 - rc, v1 - rc, 0), (u0 + rc, v1 - rc, 90), (u0 + rc, v0 + rc, 180)):
        for i in range(k + 1):
            a = math.radians(a0 + 90 * i / k)
            out.append((cu + rc * math.cos(a), cv + rc * math.sin(a)))
    return out


def circle2(cu, cv, r, n=40):
    return [(cu + r * math.cos(2 * math.pi * i / n), cv + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _ccw(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    return poly if a > 0 else list(reversed(poly))


def clip_halfplane(poly, a, b):
    """keep the part of poly (list of (q, w)) left of a->b (q 2D, w any vector-like payload interpolated linearly)."""
    def side(q):
        return (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
    out = []
    n = len(poly)
    for i in range(n):
        (q0, w0), (q1, w1) = poly[i], poly[(i + 1) % n]
        s0, s1 = side(q0), side(q1)
        if s0 >= 0:
            out.append((q0, w0))
        if (s0 >= 0) != (s1 >= 0):
            t = s0 / (s0 - s1)
            out.append(((q0[0] + (q1[0] - q0[0]) * t, q0[1] + (q1[1] - q0[1]) * t), tuple(x0 + (x1 - x0) * t for x0, x1 in zip(w0, w1))))
    return out


# ============================================================================================ skin cutter
SNAP = 0.0015


def min_alt(pts):
    """smallest altitude over the fan triangles of a convex polygon (sliver test)."""
    best = 9.0
    for k in range(1, len(pts) - 1):
        a, b, c = pts[0], pts[k], pts[k + 1]
        ar2 = ((b - a).cross(c - a)).length
        L = max((b - a).length, (c - b).length, (a - c).length)
        if L > 0:
            best = min(best, ar2 / L)
    return best

PROJ = {
    'R': (lambda p: (p.y, p.z), lambda n, c: n.x > 0.20 and c.x > 0.15),
    'L': (lambda p: (p.y, -p.z), lambda n, c: n.x < -0.20 and c.x < -0.15),      # mirrored so a CCW (y, z) polygon stays CCW
    'top': (lambda p: (p.y, p.x), lambda n, c: n.z > 0.20),
    'bot': (lambda p: (p.y, -p.x), lambda n, c: n.z < -0.20),
}


def cut(mb, poly, proj, mode, zrange=None, tag=''):
    """cut the paint skin of mb by the convex polygon `poly` given in the projection's (u, v) (for 'L' / 'bot' give it as for 'R' /
    'top': it is mirrored here). mode 'glass' (pieces inside become glass) or 'hole' (dropped). Pieces keep the parent face's plane
    (no crack against unsplit neighbours) and its UV (interpolated); vertices are welded by position."""
    f2, keep_face = PROJ[proj]
    if proj in ('L', 'bot'):
        poly = [(u, -v) for u, v in poly]
    poly = _ccw(poly)
    pu = [q[0] for q in poly]; pv = [q[1] for q in poly]
    bb = (min(pu), max(pu), min(pv), max(pv))
    key = {}
    for i, p in enumerate(mb.verts):
        key.setdefault((round(p.x, 6), round(p.y, 6), round(p.z, 6)), i)

    def vid(p):
        k = (round(p.x, 6), round(p.y, 6), round(p.z, 6))
        if k not in key:
            key[k] = mb.v(p)
        return key[k]
    out, n_in, n_split = [], 0, 0
    for f in mb.faces:
        if f['mat'] != 'paint' or len(f['idx']) < 3:
            out.append(f); continue
        P = [mb.verts[k] for k in f['idx']]
        c = sum(P, V()) / len(P)
        nrm = V()
        for k in range(1, len(P) - 1):
            nrm += (P[k] - P[0]).cross(P[k + 1] - P[0])
        if nrm.length < 1e-12:
            out.append(f); continue
        nrm.normalize()
        if not keep_face(nrm, c) or (zrange and not (zrange[0] <= c.z <= zrange[1])):
            out.append(f); continue
        Q = [f2(p) for p in P]
        if max(q[0] for q in Q) < bb[0] or min(q[0] for q in Q) > bb[1] or max(q[1] for q in Q) < bb[2] or min(q[1] for q in Q) > bb[3]:
            out.append(f); continue
        U = f['uv']
        pieces_in, pieces_out = [], []
        for t in range(1, len(P) - 1):           # fan triangles of the parent face
            tri = [0, t, t + 1]
            rem = [(Q[i], tuple(1.0 if j == i else 0.0 for j in tri)) for i in tri]
            for e in range(len(poly)):
                a, b = poly[e], poly[(e + 1) % len(poly)]
                outside = clip_halfplane(rem, b, a)
                if len(outside) >= 3:
                    pieces_out.append((tri, outside))
                rem = clip_halfplane(rem, a, b)
                if len(rem) < 3:
                    break
            if len(rem) >= 3:
                pieces_in.append((tri, rem))
        if not pieces_in:
            out.append(f); continue
        n_split += 1

        snap_pts = [(P[k], f['idx'][k], U[k] if U else None) for k in range(len(P))]      # parent corners + points made for this face

        def snap(p, u):
            # a cut point within SNAP of a parent corner or of a point already made here is that point (no sliver triangles: the
            # Unity importer / PhysX drop or weld them, opening hair-line gaps - the 1.8.17 first build's crew-in-hull rays left through them)
            for q, qi, qu in snap_pts:
                if (q - p).length < SNAP:
                    return q, qu
            snap_pts.append((p, None, u))
            return p, u

        def emit(tri, poly_, mat, with_uv):
            pts = [sum((P[tri[j]] * w[j] for j in range(3)), V()) for q, w in poly_]
            uv = None
            if with_uv and U:
                uv = [(sum(U[tri[j]][0] * w[j] for j in range(3)), sum(U[tri[j]][1] * w[j] for j in range(3))) for q, w in poly_]
            sn = [snap(p, uv[k] if uv else None) for k, p in enumerate(pts)]
            pts = [a_ for a_, b_ in sn]
            if uv:
                uv = [b_ if b_ is not None else uv[k] for k, (a_, b_) in enumerate(sn)]
            # drop (near-)collinear corners (< 0.05 mm off the line of their neighbours): a polygon keeps its whole area, its fan
            # triangulation no sliver. NEVER drop a whole piece for a sliver fan triangle (1.8.17 build 3: that opened holes in the skin
            # at window / K-5 edges - the crew-in-hull rays left through them)
            k = 0
            while len(pts) > 3 and k < len(pts):
                a_, b_, c_ = pts[k - 1], pts[k], pts[(k + 1) % len(pts)]
                L_ = (c_ - a_).length
                if L_ < 1e-9 or ((b_ - a_).cross(c_ - a_)).length / L_ < 5e-5:
                    del pts[k]
                    if uv:
                        del uv[k]
                    k = max(k - 1, 0)
                else:
                    k += 1
            nn = V()
            for k in range(1, len(pts) - 1):
                nn += (pts[k] - pts[0]).cross(pts[k + 1] - pts[0])
            area = nn.length / 2
            if area < 1e-9:
                return
            if nn.dot(nrm) < 0:
                pts = list(reversed(pts)); uv = list(reversed(uv)) if uv else None
            idx = [vid(p) for p in pts]
            keep_k = [k for k in range(len(idx)) if idx[k] != idx[(k + 1) % len(idx)]]      # weld can merge neighbours
            idx = [idx[k] for k in keep_k]; uv = [uv[k] for k in keep_k] if uv else None
            if len(idx) < 3 or len(set(idx)) != len(idx):
                return
            out.append(dict(idx=idx, mat=mat, uv=uv, smooth=f['smooth']))
        for tri, pc in pieces_out:
            emit(tri, pc, 'paint', True)
        if mode == 'glass':
            for tri, pc in pieces_in:
                emit(tri, pc, 'glass', False)
        n_in += len(pieces_in)
    mb.faces = out
    LOG.setdefault('cuts', []).append((tag, proj, mode, n_split, n_in))
    return n_split


# ============================================================================================ frames
def frame_line(mb, pts, nrm_fn, w=0.030, h=0.018, closed=False, inner=True, lift=0.009, inner_depth=0.016):
    """riveted frame bar along a polyline on a surface: outer half livery (paint) proud of the surface, inner bronze green."""
    seq = list(pts) + ([pts[0]] if closed else [])
    for k, (a, b) in enumerate(zip(seq, seq[1:])):
        if (b - a).length < 1e-4:
            continue
        n_ = (nrm_fn(a) + nrm_fn(b)).normalized()
        o_ = 0.0015 * (k % 2)
        NS.sec_tube(mb, a + n_ * (lift + o_), b + n_ * (lift + o_), w, h, n_, mat='paint')
        if inner:
            NS.sec_tube(mb, a - n_ * (inner_depth + o_), b - n_ * (inner_depth + o_), w, 0.024, n_, mat='interior')


def _poly_side(poly, sgn, out=0.0):
    return [side_pt(u, v, sgn, out) for u, v in poly]


def _poly_top(poly, out=0.0):
    return [top_pt(u, v, out) for u, v in poly]


# ============================================================================================ windows
def astrodome_body(mb, cy, r, h):
    """navigator's astrodome over its round opening (cut_part): a glass dome (inner copy) and a riveted base ring."""
    N = 40
    zc = skin_z(0.0, cy)
    prof = [(1.0, 0.0), (0.985, 0.25), (0.94, 0.48), (0.86, 0.67), (0.74, 0.82), (0.58, 0.93), (0.38, 0.985), (0.18, 1.0)]
    rings = []
    for k, (sr, sh) in enumerate(prof):
        ring = []
        for i in range(N):
            a = 2 * math.pi * i / N
            x, y = r * sr * math.cos(a), cy + r * sr * math.sin(a)
            zb = skin_z(x, y) - 0.003
            ring.append(V((x, y, zb * (1 - sh) + (zc + h) * sh) if k else (x, y, zb)))
        rings.append(ring)
    nf0 = len(mb.faces)
    loft(mb, rings, 'glass')
    fan_cap(mb, rings[-1], V((0, cy, zc + h + 0.002)), 'glass', V((0, 0, 1)), smooth=True)
    for f in mb.faces[nf0:]:
        f['uv'] = None
    tri_split(mb, nf0)
    _inner_glass(mb, mb.faces[nf0:], V((0, cy, zc)))
    ring1818 = getattr(S, 'DOME_RING1818', False)
    # outer (paint) ring: the same 40 blocks as 1.8.17 (outside unchanged); 1.8.18: the inner blocks are replaced by one continuous ring
    frame_line(mb, [top_pt(y, x) for x, y in [(r * math.cos(2 * math.pi * i / N), cy + r * math.sin(2 * math.pi * i / N)) for i in range(N)]],
               skin_normal, w=0.040, h=0.020, closed=True, inner=not ring1818)
    if ring1818:
        dome_inner_ring(mb, cy)


def dome_ring_pt(cy, rr, a, depth):
    """point of the astrodome's inner ring: plan radius rr at angle a about (0, cy), `depth` metres under the outer skin along its normal."""
    return top_pt(cy + rr * math.sin(a), rr * math.cos(a), -depth)


def dome_inner_ring(mb, cy):
    """1.8.18: the astrodome's inner frame as ONE continuous ring of rectangular section (bronze-green interior), in place of the 40
    straight 4 x 3.1 cm blocks of frame_line (each a chord turned 9 deg from the next, wedge gaps ~3 mm wide at the outer corners and
    overlaps at the inner, alternate blocks 1.5 mm deeper: from inside the nose a ring of jagged dark / light teeth, in game 1.8.17).
    Same envelope as those blocks (plan radius 0.18-0.22, 4-28 mm under the outer skin), so nothing new shows through the dome from
    outside. Four strips (top / bottom / inner / outer face), each with its own vertices (hard corners, smooth along the ring)."""
    R = S.DOME_RING1818_SECTION
    n = R['n']
    ang = [2 * math.pi * i / n for i in range(n)]
    corners = {k: [dome_ring_pt(cy, rr, a, dd) for a in ang] for k, (rr, dd) in
               dict(ti=(R['r_in'], R['d_top']), to=(R['r_out'], R['d_top']), bi=(R['r_in'], R['d_bot']), bo=(R['r_out'], R['d_bot'])).items()}
    centre = lambda p: V((0.0, cy, p.z))
    nf0 = len(mb.faces)
    for ka, kb, toward in (('ti', 'to', lambda q, p: skin_normal(p)), ('bi', 'bo', lambda q, p: -skin_normal(p)),
                           ('ti', 'bi', lambda q, p: centre(p) - p), ('to', 'bo', lambda q, p: p - centre(p))):
        A = [mb.v(p) for p in corners[ka]]; B = [mb.v(p) for p in corners[kb]]
        for i in range(n):
            j = (i + 1) % n
            q = [A[i], B[i], B[j], A[j]]
            P = [mb.verts[k] for k in q]
            c = sum(P, V()) / 4
            nn = (P[1] - P[0]).cross(P[3] - P[0])
            if nn.dot(toward(q, c)) < 0:
                q = [q[0], q[3], q[2], q[1]]
            mb.face(q, 'interior', None, smooth=True)
    tri_split(mb, nf0)      # fixed diagonals (non-planar quads on the curved nose top)
    LOG['dome_ring1818'] = dict(faces=len(mb.faces) - nf0, n=n)


def _inner_glass(mb, faces, centre, off=0.003):
    for f in list(faces):
        if f['mat'] != 'glass':
            continue
        P = [mb.verts[k] for k in f['idx']]
        c = sum(P, V()) / len(P)
        d = (centre - c)
        d = d.normalized() if d.length > 1e-9 else V((0, 0, -1))
        mb.face([mb.v(p + d * off) for p in reversed(P)], 'glass', None)


def tri_split(mb, start):
    """split the polygons added from `start` into triangles on one fixed diagonal fan, so a reversed copy uses the SAME diagonals (a
    non-planar quad and its reversed copy triangulate on opposite diagonals and cross each other: from inside, a ray then met the
    outer face's back first)."""
    out = mb.faces[:start]
    for f in mb.faces[start:]:
        i_, u_ = f['idx'], f['uv']
        if len(i_) <= 3:
            out.append(f); continue
        for k in range(1, len(i_) - 1):
            out.append(dict(idx=[i_[0], i_[k], i_[k + 1]], mat=f['mat'], uv=[u_[0], u_[k], u_[k + 1]] if u_ else None, smooth=f['smooth']))
    mb.faces = out


def _inner_copy(mb, faces, inward_fn, off=0.004, mat='interior'):
    """reversed copy of each face `off` behind it along its OWN normal (the side inward_fn points to): from that side the copy is
    always met first, whatever the slope of the face (a copy shifted toward a centre point fell behind near-horizontal faces)."""
    for f in list(faces):
        P = [mb.verts[k] for k in f['idx']]
        c = sum(P, V()) / len(P)
        nn = V()
        for k in range(1, len(P) - 1):
            nn += (P[k] - P[0]).cross(P[k + 1] - P[0])
        if nn.length < 1e-12:
            continue
        nn.normalize()
        d = -nn if nn.dot(inward_fn(c)) <= 0 else nn
        mb.face([mb.v(p + d * off) for p in reversed(P)], mat if f['mat'] != 'glass' else 'glass', None)


# ============================================================================================ K-5 cheek gun frames
def k5_geometry(spec):
    """numbers of one K-5 projecting frame from its spec: plane through the cheek pivot (normal horizontal, `face_deg` outboard of
    forward), side pane from y_a (flush) to the plane (stand-off s_f at its front edge), wedge top / bottom."""
    sg = spec['side']
    px, py, pz = spec['pivot']
    a = math.radians(spec['face_deg'])
    n = V((sg * math.sin(a), math.cos(a), 0.0))
    P = V((px, py, pz))

    def plane_x(y):          # |x| of the plane at y (horizontal line)
        # n.x * (x - px) + n.y * (y - py) = 0
        return abs(px - n.y * (y - py) / n.x)
    y_a, y_f = spec['y_a'], spec['y_f']
    s_f = plane_x(y_f) - skin_x(y_f, pz)

    def stand(y):
        return max(0.0, s_f * (y - y_a) / (y_f - y_a))

    def pane_x(y, z):
        return skin_x(y, z) + stand(y)

    def y_on_plane(fx, z, lo, hi):        # first y in [lo, hi] where fx(y, z) <= plane_x(y) (bisection on fx - plane)
        g = lambda y: fx(y, z) - plane_x(y)       # < 0 aft of the plane (surface inside it), > 0 ahead
        if g(lo) > 0:
            return lo
        if g(hi) <= 0:
            return hi
        for _ in range(60):
            m = (lo + hi) / 2
            if g(m) <= 0:
                lo = m
            else:
                hi = m
        return (lo + hi) / 2
    return dict(n=n, P=P, plane_x=plane_x, stand=stand, pane_x=pane_x, s_f=s_f,
                y_f=lambda z: y_on_plane(pane_x, z, y_a, y_f + 0.25),
                y_s=lambda z: min(y_on_plane(skin_x, z, y_a, y_f + 0.40), spec.get('y_max', 99.0)),      # clamped: ahead of y_max a cap
                y_s_raw=lambda z: y_on_plane(skin_x, z, y_a, y_f + 0.40))                                   # at y_max closes the wedge


def k5_cut(mb, spec):
    """the K-5 footprint opening in the side skin: aft edge y_a (z0..z1), wedge lines down / up to the front, front = where the face
    plane meets the skin (clamped at y_max). The front edge is not convex (the plane meets a narrower skin further forward above and
    below the widest line), so the opening is cut as horizontal bands, each a convex quad."""
    G = k5_geometry(spec)
    y_a, z0, z1 = spec['y_a'], spec['z0'], spec['z1']
    zb, zt = z0 - spec['drop'], z1 + spec['rise']
    ysb, yst = G['y_s'](zb), G['y_s'](zt)

    def y_aft(z):
        if z < z0:
            return y_a + (z0 - z) / (z0 - zb) * (ysb - y_a)
        if z > z1:
            return y_a + (z - z1) / (zt - z1) * (yst - y_a)
        return y_a
    lv = sorted(set([zb + (z0 - zb) * i / 4 for i in range(5)] + [z0 + (z1 - z0) * i / 12 for i in range(13)] + [z1 + (zt - z1) * i / 3 for i in range(4)]))
    for za, zc in zip(lv, lv[1:]):
        band = [(y_aft(za), za), (G['y_s'](za), za), (G['y_s'](zc), zc), (y_aft(zc), zc)]
        cut(mb, band, 'R' if spec['side'] > 0 else 'L', 'hole', tag=spec['tag'] + '_foot')


def k5(mb, spec, tag):
    sg = spec['side']
    G = k5_geometry(spec)
    n, P = G['n'], G['P']
    y_a, z0, z1 = spec['y_a'], spec['z0'], spec['z1']
    zb, zt = z0 - spec['drop'], z1 + spec['rise']
    zg = P.z + spec['plate_up']                    # top of the socket plate / bottom of the lower small pane
    NZ = 10
    # ---- footprint on the skin (side projection) and the cut
    ys_b, ys_t = G['y_s'](zb), G['y_s'](zt)
    nf0 = len(mb.faces)
    inset = -0.012      # closure / cap edges 12 mm under the true skin: the cut skin is flat facets up to ~4 mm inside it (no slit to see or
                        # shoot through at the seam - the Unity crew-in-hull rays left through it at the bottom closure line)

    def skin(y, z):
        return side_pt(y, z, sg, inset)

    def pane(y, z, dip=0.0):
        return V((sg * (G['pane_x'](y, z) - dip), y, z))
    # ---- side pane (glass): rows z0..z1, columns y_a..y_f(z)
    NY = 8
    rows = []
    for i in range(NZ + 1):
        z = z0 + (z1 - z0) * i / NZ
        yf = G['y_f'](z)
        rows.append([pane(y_a + (yf - y_a) * j / NY, z, 0.010 if j == 0 else 0.0) for j in range(NY + 1)])     # aft edge dips under the cut skin
    for i in range(NZ):
        for j in range(NY):
            q = [rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]]
            oriented_quad(mb, q, 'glass', V((sg, 0, 0)), smooth=True)
    # ---- front face (planar): outline in 2D (h along the plane's horizontal, z)
    th = V((-n.y, n.x, 0.0)) * (1 if sg > 0 else -1)       # horizontal tangent in the plane
    def to2(p):
        return ((p - P).dot(th), p.z - P.z)
    def to3(h, dz):
        return P + th * h + V((0, 0, dz))
    left = [rows[i][-1] for i in range(NZ + 1)]                       # pane front edge, z0 -> z1
    right = [V((sg * G['plane_x'](G['y_s'](zb + (zt - zb) * i / NZ)), G['y_s'](zb + (zt - zb) * i / NZ), zb + (zt - zb) * i / NZ))
             for i in range(NZ + 1)]                                  # skin edge on the plane, zb -> zt
    right = [p + skin_normal(p) * inset for p in right]
    # wedge cap at y_max where the plane does not meet the skin before the cone's base ring (left K-5 top: the nose narrows there)
    ymx = spec.get('y_max', 99.0)
    capped = [G['y_s_raw'](p.z) > ymx + 1e-4 for p in right]
    for i in range(NZ):
        if capped[i] or capped[i + 1]:
            q = [right[i], right[i + 1], skin(ymx, right[i + 1].z), skin(ymx, right[i].z)]
            oriented_quad(mb, q, 'paint', V((0, 1, 0)), smooth=False)
    LOG[tag + '_capped'] = sum(capped)
    outline2 = [to2(p) for p in left] + [to2(p) for p in reversed(right)]   # pane edge up, top line, skin edge down, bottom line
    outline2 = _ccw(outline2)

    def clip_z(poly, zlo, zhi):
        pp = [(q, (q[0], q[1])) for q in poly]
        # keep zlo <= z <= zhi (z relative to the pivot); half-planes as directed lines (left side kept)
        pp = clip_halfplane(pp, (0.0, zlo - P.z), (1.0, zlo - P.z))
        pp = clip_halfplane(pp, (1.0, zhi - P.z), (0.0, zhi - P.z))
        return [q for q, w in pp]
    zmid = (zg + z1 + 0.5 * spec['rise']) / 2
    plate = clip_z(outline2, -9, zg)
    pane_lo = clip_z(outline2, zg, zmid)
    pane_hi = clip_z(outline2, zmid, 9)
    face_faces0 = len(mb.faces)
    for poly_ in (pane_lo, pane_hi):
        if len(poly_) >= 3:
            c2 = (sum(q[0] for q in poly_) / len(poly_), sum(q[1] for q in poly_) / len(poly_))
            for k in range(len(poly_)):
                tri = [to3(*c2), to3(*poly_[k]), to3(*poly_[(k + 1) % len(poly_)])]
                oriented_quad(mb, tri, 'glass', n, smooth=False)
    # socket plate with the gun hole (annulus fan from the hole circle to the plate outline; plate is star-shaped about the pivot)
    rh = spec['hole_r']
    NA = 28
    def ray_hit(poly_, ang):
        d = (math.cos(ang), math.sin(ang)); best = None
        for k in range(len(poly_)):
            a, b = poly_[k], poly_[(k + 1) % len(poly_)]
            e = (b[0] - a[0], b[1] - a[1])
            den = d[0] * e[1] - d[1] * e[0]
            if abs(den) < 1e-12:
                continue
            t = (a[0] * e[1] - a[1] * e[0]) / den
            s = (a[0] * d[1] - a[1] * d[0]) / den
            if t > 0 and -1e-9 <= s <= 1 + 1e-9 and (best is None or t < best):
                best = t
        return best
    plate_faces0 = len(mb.faces)
    ok_plate = True
    for k in range(NA):
        a0, a1 = 2 * math.pi * k / NA, 2 * math.pi * (k + 1) / NA
        t0, t1 = ray_hit(plate, a0), ray_hit(plate, a1)
        if t0 is None or t1 is None or t0 < rh + 0.01 or t1 < rh + 0.01:
            ok_plate = False; continue
        q = [to3(rh * math.cos(a0), rh * math.sin(a0)), to3(t0 * math.cos(a0), t0 * math.sin(a0)),
             to3(t1 * math.cos(a1), t1 * math.sin(a1)), to3(rh * math.cos(a1), rh * math.sin(a1))]
        oriented_quad(mb, q, 'paint', n, smooth=False)
    LOG[tag + '_plate_ok'] = ok_plate
    # socket flange (dark metal) round the hole; no sleeve (a 5 cm sleeve met the jacket at the traverse / elevation corners)
    hole = [to3(rh * math.cos(2 * math.pi * k / NA), rh * math.sin(2 * math.pi * k / NA)) for k in range(NA)]
    # the socket is glazed (the K-5 ball mount's sight / blast window): the barrel passes it at the pivot at every pose (bore through the
    # pivot), the crew compartment stays closed (Unity crew-in-hull rule; an open 0.14 m port let the rays out)
    nfg = len(mb.faces)
    fan_cap(mb, hole, P, 'glass', n)
    for f in mb.faces[nfg:]:
        f['uv'] = None
    fl_o = [to3((rh + 0.028) * math.cos(2 * math.pi * k / NA), (rh + 0.028) * math.sin(2 * math.pi * k / NA)) + n * 0.006 for k in range(NA)]
    fl_i = [p + n * 0.006 for p in hole]
    for k in range(NA):
        oriented_quad(mb, [fl_i[k], fl_i[(k + 1) % NA], fl_o[(k + 1) % NA], fl_o[k]], 'metal_dark', n)
    loft(mb, [[p - n * 0.006 for p in fl_o], fl_o], 'metal_dark')
    # ---- wedge closures: top (pane top edge + front-face top line -> footprint top edge) and bottom
    def strip(outer, inner_, toward):
        m = max(len(outer), len(inner_))
        def rs(pl, m_):
            L = [0.0]
            for a, b in zip(pl, pl[1:]):
                L.append(L[-1] + (b - a).length)
            out = []
            for i in range(m_):
                s = L[-1] * i / (m_ - 1)
                k = max(kk for kk in range(len(L)) if L[kk] <= s + 1e-12)
                k = min(k, len(pl) - 2)
                t = (s - L[k]) / max(L[k + 1] - L[k], 1e-12)
                out.append(pl[k].lerp(pl[k + 1], min(max(t, 0.0), 1.0)))
            return out
        A, B = rs(outer, m), rs(inner_, m)
        for i in range(m - 1):
            oriented_quad(mb, [A[i], A[i + 1], B[i + 1], B[i]], 'paint', toward, smooth=False)
    NT = 10
    top_outer = rows[-1] + [left[-1].lerp(right[-1], k / NT) for k in range(1, NT + 1)]
    KK = NY + NT

    def lap(k):      # the closures' skin edge laps 15 mm past the cut line and 25 mm under the skin (no seam slit; ends kept on the corners)
        return min(1.0, 3.0 * min(k, KK - k) / KK)
    top_inner = [side_pt(y_a + (ys_t - y_a) * k / KK, z1 + (zt - z1) * k / KK + 0.015 * lap(k), sg, inset - 0.013 * lap(k)) for k in range(KK + 1)]
    strip(top_outer, top_inner, V((0, 0, 1)))
    bot_outer = rows[0] + [left[0].lerp(right[0], k / NT) for k in range(1, NT + 1)]
    bot_inner = [side_pt(y_a + (ys_b - y_a) * k / KK, z0 + (zb - z0) * k / KK - 0.015 * lap(k), sg, inset - 0.013 * lap(k)) for k in range(KK + 1)]
    strip(bot_outer, bot_inner, V((0, 0, -1)))
    tri_split(mb, nf0)
    new = mb.faces[nf0:]
    cen = V((0.0, P.y, P.z))
    # inside of the frame: a continuous second skin 2 mm in (vertex normals, edge strips at the open boundaries; nimrod_structure.double_skin):
    # per-face copies left cracks / fell behind sloped faces, and from inside a ray then met an outer back face first - PhysX any-hit
    # raycasts skip those (the Unity crew-in-hull check counted them as leaving the hull)
    _keys = {tuple(round(x, 5) for x in sum((mb.verts[k] for k in f['idx']), V()) / len(f['idx'])) for f in new if f['mat'] in ('paint', 'glass')}
    NS.double_skin(mb, t=0.002, mats=('paint', 'glass'), inner=lambda f, c: 'glass' if f['mat'] == 'glass' else 'interior',
                   select=lambda c: tuple(round(x, 5) for x in c) in _keys)
    # ---- frames: pane outline (aft edge on the skin, top, bottom), the corner pane / front face, the front face's outline and its
    # pane bars (outer only on the front face: its inside is the gunner's view)
    sk = lambda p: skin_normal(p)
    nfn = lambda p: n
    frame_line(mb, [pane(y_a, z0 + (z1 - z0) * i / NZ) for i in range(NZ + 1)], sk, w=0.035)
    frame_line(mb, rows[-1], sk, w=0.035)
    frame_line(mb, rows[0], sk, w=0.035)
    frame_line(mb, left, lambda p: (sk(p) + n).normalized(), w=0.045, h=0.024)
    frame_line(mb, [left[-1], right[-1]], nfn, w=0.035, inner=False)
    frame_line(mb, [left[0], right[0]], nfn, w=0.035, inner=False)
    frame_line(mb, right, lambda p: (sk(p) + n).normalized(), w=0.035, inner=False)
    for zz in (zg, zmid):
        seg = clip_z(outline2, zz - 1e-4, zz + 1e-4)
        if len(seg) >= 2:
            hs = [q[0] for q in seg]
            frame_line(mb, [to3(min(hs), zz - P.z), to3(max(hs), zz - P.z)], nfn, w=0.030, inner=False)
    LOG[tag] = dict(s_f=round(G['s_f'], 3), y_f=round(G['y_f'](P.z), 3), y_s=round(G['y_s'](P.z), 3), ys_top=round(ys_t, 3), ys_bot=round(ys_b, 3))
    return G


# ============================================================================================ cone frames
def cone_base_ring(mb, y, N=48):
    pts = []
    top, bot, hw, n = S.fus_station(y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    for i in range(N):
        a = 2 * math.pi * i / N
        s_, c_ = math.sin(a), math.cos(a)
        pts.append(V((hw * math.copysign(abs(s_) ** (2.0 / n), s_), y, cz + hz * math.copysign(abs(c_) ** (2.0 / n), c_))))
    frame_line(mb, pts, skin_normal, w=0.055, h=0.020, closed=True, inner=True, lift=0.010, inner_depth=0.028)     # deeper: the cone's shoulders are tighter than the 40-point facets


def _cone_F(q):
    top, bot, hw, n = S.fus_station(q.y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    return (abs(q.x) / hw) ** n + (abs(q.z - cz) / hz) ** n


def on_cone(p0, d=V((0.0, 0.75, -0.66))):
    """p0 moved along d (forward-down, the lower front of the cone faces that way) onto the glazed cone surface."""
    d = d.normalized()
    lo, hi = -0.4, 0.4
    if _cone_F(p0 + d * lo) > 1.0:
        return p0
    for _ in range(60):
        m = (lo + hi) / 2
        if _cone_F(p0 + d * m) > 1.0:
            hi = m
        else:
            lo = m
    return p0 + d * ((lo + hi) / 2)


def optical_flat(mb):
    """bombardier's optical flat: a framed trapezoid low on the front of the cone (reference, front view: bottom y 6.84 / z -0.18,
    x +-0.07 with rounded corners; top y 7.28 / z 0.32, x +-0.20)."""
    F = S.NOSE1817_FLAT
    (yb, zb, xb), (yt, zt, xt) = F['bottom'], F['top']
    corners = [(0.0, -xb), (1.0, -xt), (1.0, xt), (0.0, xb)]
    seq = []
    for (ta, xa), (tb, xb_) in zip(corners, corners[1:] + corners[:1]):
        for j in range(8):
            u = j / 8
            t, x = ta + (tb - ta) * u, xa + (xb_ - xa) * u
            seq.append(on_cone(V((x, yb + (yt - yb) * t, zb + (zt - zb) * t))))
    frame_line(mb, seq, _cone_normal, w=0.026, h=0.016, closed=True, inner=True, lift=0.006)
    LOG['optical_flat'] = [tuple(round(c, 3) for c in seq[k]) for k in (0, 8, 16, 24)]


def _cone_normal(p):
    """outward normal of the lofted cone at p (finite differences of the section table)."""
    def F(q):
        top, bot, hw, n = S.fus_station(q.y)
        cz, hz = (top + bot) / 2, (top - bot) / 2
        return (abs(q.x) / hw) ** n + (abs(q.z - cz) / hz) ** n
    e = 1e-4
    g = V(((F(p + V((e, 0, 0))) - F(p - V((e, 0, 0)))) / (2 * e), (F(p + V((0, e, 0))) - F(p - V((0, e, 0)))) / (2 * e),
           (F(p + V((0, 0, e))) - F(p - V((0, 0, e)))) / (2 * e)))
    return g.normalized() if g.length > 1e-12 else V((0, 1, 0))


# ============================================================================================ chin opening + keel fairing
def chin_hole(mb):
    t = S.TURRETS['chin']; c = V(t['pos'])
    r = S.NOSE1817_CHIN_HOLE_R
    poly = [(u, v) for u, v in circle2(c.y, c.x, r, 64)]
    # flat front edge at y_max (the glass ring sits just ahead of the drum): circle  half-plane (convex)
    ymax = S.NOSE1817_CHIN_HOLE_YMAX
    pp = clip_halfplane([(q, q) for q in poly], (ymax, -1.0), (ymax, 1.0))      # keep y <= ymax
    poly = [q for q, w in pp]
    cut(mb, poly, 'bot', 'hole', zrange=(-9, -0.05), tag='chin_hole')


def keel_fairing():
    """the long teardrop keel fairing under the nose, from the chin turret aft (reference: keel z -0.737 / -0.784 / -0.827 / -0.846 at
    y 4.6 / 5.0 / 5.4 / 5.6, i.e. 0.017 / 0.064 / 0.134 / 0.165 below our belly; half width ~0.12 / 0.30 / 0.38 / 0.45). Returns
    (aft MeshBuf for fus_cockpit, fore MeshBuf for fus_nose): split exactly at the 5.00 station."""
    K = S.NOSE1817_KEEL
    y0, L, d_max, w_max, ex, wy = K['y0'], K['L'], K['d'], K['w'], K['ex'], K['y_front']
    c = V(S.TURRETS['chin']['pos']); rw = K['r_drum']

    def d0(y):
        return d_max * max((y - y0) / L, 0.0) ** ex

    def w(y):
        return w_max * math.sqrt(max((y - y0) / L, 0.0))

    def y_aft(x):
        return y0 + L * (abs(x) / w_max) ** 2

    def y_end(x):
        e = c.y - math.sqrt(max(rw * rw - x * x, 0.0)) if abs(x) < rw else c.y
        return min(e, wy)
    X = 0.0
    for k in range(2000):        # widest column: y_aft(x) == y_end(x)
        x = k * 0.0005
        if y_aft(x) >= y_end(x) - 0.01:      # outermost column >= 1 cm long (no sliver triangles at the front corners)
            break
        X = x
    NX, NS_ = 26, 30
    xs = [X * math.sin(math.pi / 2 * (-1 + 2 * i / NX)) for i in range(NX + 1)]

    def zp(x, y):
        ww = w(y)
        t = min(abs(x) / ww, 1.0) if ww > 1e-6 else 1.0
        d = d0(y) * (1 - t ** K['m'])
        return skin_z(x, y, upper=False) - d + 0.004
    grid = []
    for x in xs:
        ya, ye = y_aft(x), y_end(x)
        if ye < ya:
            ye = ya
        col = []
        for j in range(NS_ + 1):
            s = j / NS_
            s = 1 - (1 - s) ** 1.6            # denser toward the front
            y = ya + (ye - ya) * s
            col.append(V((x, y, zp(x, y))))
        grid.append(col)
    mb = MeshBuf()
    for i in range(NX):
        for j in range(NS_):
            q = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
            if (q[0] - q[1]).length + (q[2] - q[3]).length < 1e-6:
                q = [q[0], q[2], q[3]]
            oriented_quad(mb, q, 'paint', V((0, 0, -1)), smooth=True)
    # end wall against the drum: from the front edge up into the hole (above the skin)
    fr = [grid[i][-1] for i in range(NX + 1)]
    top_ = [V((p.x, p.y, skin_z(p.x, p.y, upper=False) + 0.012)) for p in fr]
    for i in range(NX):
        q = [fr[i], fr[i + 1], top_[i + 1], top_[i]]
        if (q[0] - q[3]).length + (q[1] - q[2]).length < 2e-3:
            continue
        oriented_quad(mb, q, 'paint', V((0, 1, 0)), smooth=False)
    # split at the 5.00 station (fus_cockpit | fus_nose)
    aft, fore = MeshBuf(), MeshBuf()
    ys = 5.0
    for f in mb.faces:
        P = [mb.verts[k] for k in f['idx']]
        U = f['uv']
        poly = [(V(p), tuple(u) if U else (0.0, 0.0)) for p, u in zip(P, U or [None] * len(P))]
        for tgt, sgn in ((aft, -1), (fore, 1)):
            out = []
            for k in range(len(poly)):
                (p0, u0), (p1, u1) = poly[k], poly[(k + 1) % len(poly)]
                s0, s1 = sgn * (p0.y - ys), sgn * (p1.y - ys)
                if s0 >= 0:
                    out.append((p0, u0))
                if (s0 >= 0) != (s1 >= 0):
                    t = s0 / (s0 - s1)
                    out.append((p0.lerp(p1, t), (u0[0] + (u1[0] - u0[0]) * t, u0[1] + (u1[1] - u0[1]) * t)))
            if len(out) >= 3:
                pts = [p for p, u in out]
                nn = V()
                for k in range(1, len(pts) - 1):
                    nn += (pts[k] - pts[0]).cross(pts[k + 1] - pts[0])
                if nn.length / 2 > 2e-7:
                    tgt.face([tgt.v(p) for p in pts], f['mat'], [u for p, u in out] if U else None, f['smooth'])
    LOG['keel'] = dict(X=round(X, 3), tris_aft=aft.tri_count(), tris_fore=fore.tri_count(),
                       z_at=[(y, round(zp(0.0, y), 3)) for y in (4.6, 5.0, 5.3, 5.6)])
    return aft, fore


# ============================================================================================ mast
def mast(mb):
    M = S.NOSE1817_MAST
    yb, h, rake, chord, th = M['y'], M['top_z'], M['rake'], M['chord'], M['thick']
    zb = skin_z(0.0, yb) - 0.01
    N = 10
    def sec(y, z, ch, t):
        return [V((t / 2 * math.sin(2 * math.pi * i / N), y + ch / 2 * math.cos(2 * math.pi * i / N), z)) for i in range(N)]
    b = sec(yb, zb, chord, th); t_ = sec(yb + rake, h, chord * 0.7, th * 0.8)
    loft(mb, [b, t_], 'paint')
    fan_cap(mb, t_, sum(t_, V()) / N, 'paint', V((0, 0, 1)))
    y0, y1 = M['rod']
    zr = h + 0.012
    ring = lambda y, r: [V((r * math.cos(2 * math.pi * i / 8), y, zr + r * 0.45 * math.sin(2 * math.pi * i / 8))) for i in range(8)]
    rr = [ring(y0, 0.003), ring(y0 + 0.06, 0.016), ring(y1 - 0.06, 0.016), ring(y1, 0.003)]
    loft(mb, rr, 'paint')
    fan_cap(mb, rr[0], V((0, y0, zr)), 'paint', V((0, -1, 0)))
    fan_cap(mb, rr[-1], V((0, y1, zr)), 'paint', V((0, 1, 0)))


# ============================================================================================ entry points (build_fuselage)
def cut_part(name, mb):
    """openings / glazing cut into one fuselage part's skin (after the face kinds, triangulation and tear; before the double skin and
    the glass inner copies, which then treat the cut glass and the cut edges like the rest of the skin)."""
    for w in S.NOSE1817_WINDOWS:
        if w['part'] != name:
            continue
        if w['kind'] == 'side':
            cut(mb, rounded_rect(*w['rect'], w['rc']), 'R' if w['side'] > 0 else 'L', 'glass', tag=w['tag'])
        elif w['kind'] == 'top':
            cut(mb, rounded_rect(*w['rect'], w['rc']), 'top', 'glass', tag=w['tag'])
        elif w['kind'] == 'dome':
            cut(mb, circle2(w['cy'], 0.0, w['r'], 40), 'top', 'hole', tag=w['tag'])
    if name == 'fus_nose':
        chin_hole(mb)
        for sp in S.NOSE1817_K5:
            k5_cut(mb, sp)


def drop_slivers(mb, start):
    """drop the degenerate triangles / polygons among the faces added from `start` (strip ends, cap corners: altitude < 0.1 mm)."""
    keep = mb.faces[:start]; n = 0
    for f in mb.faces[start:]:
        pts = [mb.verts[k] for k in f['idx']]
        if len(pts) >= 3 and min_alt(pts) < 1e-4:
            n += 1; continue
        keep.append(f)
    mb.faces = keep
    LOG['slivers_dropped'] = LOG.get('slivers_dropped', 0) + n


def finish_part(name, mb, keel):
    """after the double skin / glass inner copies: window frames, the astrodome, the K-5 frames, cone ring, optical flat, mast, keel."""
    nf0 = len(mb.faces)
    for w in S.NOSE1817_WINDOWS:
        if w['part'] != name:
            continue
        if w['kind'] == 'side':
            frame_line(mb, _poly_side(rounded_rect(*w['rect'], w['rc']), w['side']), skin_normal, w=0.030, closed=True)
        elif w['kind'] == 'top':
            frame_line(mb, _poly_top(rounded_rect(*w['rect'], w['rc'])), skin_normal, w=0.030, closed=True)
        elif w['kind'] == 'dome':
            astrodome_body(mb, w['cy'], w['r'], w['h'])
    if name == 'fus_nose':
        for sp in S.NOSE1817_K5:
            k5(mb, sp, sp['tag'])
        cone_base_ring(mb, S.NOSE_GLASS_Y)
        optical_flat(mb)
        mast(mb)
        mb.extend(keel[1])
    if name == 'fus_cockpit':
        mb.extend(keel[0])
    drop_slivers(mb, nf0)
