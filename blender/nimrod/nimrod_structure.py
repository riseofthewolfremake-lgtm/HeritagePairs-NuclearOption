"""Nimrod damage structure + skins (2026-11-02 rebuild after user review 1; method of docs/stock_damage_study.md 2, 4, 11 and the
B-25H v3 code blender/v2/b25h_v3.py tear_mesh / fus_break_structure / wing_break_structure).

  * double_skin: every paint face (and selected others) gets an inner face 4 mm inside, reversed (material fabric_in = the back of
    the doped fabric, or 'interior' under metal), and every open boundary of the skin gets an edge strip (structure) joining the
    outer and inner skins. A broken part then shows its inner skin instead of nothing (Unity culls back faces).
  * tear: complementary zig-zag skin edges at every split, computed from the vertex position so the two parts mate exactly
    while intact (b25h_v3.tear_mesh idea, own implementation).
  * break structure: the Nimrod is a steel-tube Warren-truss fuselage with fabric over stringers and two-spar fabric wings:
    longeron / spar stubs, a set-back frame or rib, truss tubes. Material 'structure' (tiled trim = stock jet_mechanical role).
  * fuselage surface queries for fitting struts, fillets and gear legs to the real skin (connectivity).
No bpy: mathutils only.
"""
import math, random
from mathutils import Vector
import nimrod_spec as S
from b25h_geom import V, MeshBuf, loft, fan_cap, oriented_quad, cylinder, box, circle_pts


# ================================================================================ fuselage surface
def fus_params(y):
    st = S.FUS
    if y >= st[0][0]:
        a = b = st[0]; t = 0.0
    elif y <= st[-1][0]:
        a = b = st[-1]; t = 0.0
    else:
        for a, b in zip(st, st[1:]):
            if a[0] >= y >= b[0]:
                break
        t = (a[0] - y) / (a[0] - b[0])
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(1, 5))     # hw, zt, zb, n


def fus_half_width(y, z):
    """|x| of the fuselage skin at station y and height z (nimrod_parts.fus_ring shape); 0 outside the section."""
    hw, zt, zb, n = fus_params(y)
    cz = (zt + zb) / 2
    if z >= cz:
        e, hz = max(2.0, n - 0.6), zt - cz
    else:
        e, hz = n, cz - zb
    r = abs(z - cz) / hz
    if r >= 1.0:
        return 0.0
    return hw * (1 - r ** e) ** (1.0 / e)


def fus_z(x, y, top=True):
    """skin height at (|x|, y) on the top or the bottom half."""
    hw, zt, zb, n = fus_params(y)
    cz = (zt + zb) / 2
    r = min(abs(x) / hw, 1.0)
    if top:
        e = max(2.0, n - 0.6)
        return cz + (zt - cz) * (1 - r ** e) ** (1.0 / e)
    return cz - (cz - zb) * (1 - r ** n) ** (1.0 / n)


def fus_surface_point(x, y, z, embed=0.0):
    """project (x, y, z) horizontally onto the fuselage side (same sign of x), moved `embed` metres inside."""
    w = fus_half_width(y, z)
    return V((math.copysign(max(w - embed, 0.0), x if x != 0 else 1.0), y, z))


# ================================================================================ double skin
def _key(p):
    return (round(p.x, 5), round(p.y, 5), round(p.z, 5))


def double_skin(mb, t=0.004, mats=('paint',), inner=lambda f, c: 'fabric_in', select=None, edge_mat='structure'):
    """add inner skins (offset t along -vertex normal, reversed) for faces whose material is in mats (and select(face centre) if
    given), plus edge strips on the open boundary of that skin set. Returns (faces added, boundary edges)."""
    faces = [f for f in mb.faces if f['mat'] in mats]
    if select is not None:
        faces = [f for f in faces if select(sum((mb.verts[i] for i in f['idx']), V()) / len(f['idx']))]
    if not faces:
        return 0, 0
    acc = {}
    for f in faces:
        P = [mb.verts[i] for i in f['idx']]
        n = V()
        for k in range(1, len(P) - 1):
            n += (P[k] - P[0]).cross(P[k + 1] - P[0])
        f['_n'] = n.normalized() if n.length > 0 else V((0, 0, 1))
        for p in P:
            acc[_key(p)] = acc.get(_key(p), V()) + n
    nrm = {k: (v.normalized() if v.length > 1e-12 else V((0, 0, 1))) for k, v in acc.items()}
    inner_idx = {}

    def iv(p):
        k = _key(p)
        if k not in inner_idx:
            inner_idx[k] = mb.v(p - nrm[k] * t)
        return inner_idx[k]
    edges = {}
    n0 = len(mb.faces)
    seen_sets = set()
    for f in faces:
        P = [mb.verts[i] for i in f['idx']]
        c = sum(P, V()) / len(P)
        idx = []
        for p in P:
            k_ = iv(p)
            if k_ not in idx:
                idx.append(k_)
        ks = frozenset(idx)
        if len(idx) >= 3 and ks not in seen_sets:
            seen_sets.add(ks)
            mb.face(list(reversed(idx)), inner(f, c), None, smooth=f.get('smooth', True))
        for a, b in zip(P, P[1:] + P[:1]):
            k = tuple(sorted((_key(a), _key(b))))
            edges.setdefault(k, []).append((a, b, c))
    nb = 0
    for k, lst in edges.items():
        if len(lst) != 1:
            continue
        a, b, c = lst[0]
        nb += 1
        mid = (a + b) / 2
        out = mid - c
        e = (b - a).normalized()
        out = out - e * out.dot(e)
        oriented_quad(mb, [a, b, mb.verts[iv(b)], mb.verts[iv(a)]], edge_mat, out if out.length > 1e-9 else V((0, 0, 1)))
    for f in faces:
        f.pop('_n', None)
    return len(mb.faces) - n0, nb


# ================================================================================ tear (complementary jagged edges)
def _hash01(k, seed):
    return random.Random(k * 7919 + seed * 104729).random()


def jag(param, seed, amp, width):
    k = int(math.floor(param / width))
    h = _hash01(k, seed)
    return amp * (0.30 + 0.70 * h) * (1 if k % 2 == 0 else -1)


def tear_mesh(mb, p0, nrm, param_fn, amp, seed, width, mats=None, uv_axis=1, u_scale=1.0):
    """displace every vertex lying on the plane (p0, nrm) along nrm by jag(param). Both parts sharing the plane run the same
    function, so their edges stay complementary (no gap while intact). Paint UVs move with the vertex (u = coordinate along nrm)."""
    p0, nrm = V(p0), V(nrm).normalized()
    use = None
    if mats is not None:
        use = set(i for f in mb.faces if f['mat'] in mats for i in f['idx'])
    moved = {}
    for i, v in enumerate(mb.verts):
        if abs((v - p0).dot(nrm)) < 2e-5 and (use is None or i in use):
            moved[i] = jag(param_fn(v), seed, amp, width)
    for i, d in moved.items():
        mb.verts[i] = mb.verts[i] + nrm * d
    for f in mb.faces:
        if f['mat'] == 'paint' and f['uv']:
            uv = list(f['uv']); ch = False
            for k, vi in enumerate(f['idx']):
                if vi in moved:
                    q = list(uv[k]); q[uv_axis] += moved[vi] * u_scale; uv[k] = tuple(q)
                    ch = True
            if ch:
                f['uv'] = uv
    return len(moved)


# ================================================================================ structure primitives
def tube(mb, p0, p1, r, mat='structure', N=6, caps=True):
    cylinder(mb, V(p0), V(p1), r, N=N, mat=mat, cap0=caps, cap1=caps, smooth=True)


def sec_tube(mb, a, b, w, h, up, mat='structure'):
    """rectangular section bar (spar cap / longeron stub) from a to b, w across, h along `up`."""
    a, b, up = V(a), V(b), V(up).normalized()
    ax = (b - a).normalized()
    s = ax.cross(up).normalized()
    u = s.cross(ax).normalized()
    ring = lambda c: [c + s * (w / 2) + u * (h / 2), c - s * (w / 2) + u * (h / 2), c - s * (w / 2) - u * (h / 2), c + s * (w / 2) - u * (h / 2)]
    ra, rb = ring(a), ring(b)
    loft(mb, [ra, rb], mat, smooth=False)
    oriented_quad(mb, ra, mat, -ax)
    oriented_quad(mb, rb, mat, ax)


def disc(mb, ring, centre, mat, toward, both=True):
    fan_cap(mb, ring, centre, mat, toward)
    if both:
        fan_cap(mb, [p - V(toward).normalized() * 0.003 for p in ring], V(centre) - V(toward).normalized() * 0.003, mat, -V(toward))


def frame_ring(mb, ring, centre, depth=0.035, thick=0.012, mat='structure'):
    """open fuselage former: flat ring of `depth` inward from the skin ring, `thick` along y (both faces + inner rim)."""
    n = len(ring)
    inner = [p + (centre - p).normalized() * depth for p in ring]
    off = V((0, thick / 2, 0))
    for j in range(n):
        j1 = (j + 1) % n
        a, b, c, d = ring[j], ring[j1], inner[j1], inner[j]
        oriented_quad(mb, [a + off, b + off, c + off, d + off], mat, V((0, 1, 0)))
        oriented_quad(mb, [a - off, b - off, c - off, d - off], mat, V((0, -1, 0)))
        oriented_quad(mb, [d + off, c + off, c - off, d - off], mat, centre - (c + d) / 2)


# ================================================================================ clipping / twins
def clip_faces(mb, p0, keep_dir):
    """clip every face of mb by the plane through p0: keep the side keep_dir points to (Sutherland-Hodgman per face, UVs interpolated)."""
    p0, n = V(p0), V(keep_dir).normalized()
    out = []
    for f in mb.faces:
        P = [mb.verts[i] for i in f['idx']]
        U = f['uv'] if f['uv'] else [None] * len(P)
        dist = [(q - p0).dot(n) for q in P]
        if all(d >= 0 for d in dist):
            out.append(f); continue
        if all(d < 0 for d in dist):
            continue
        cp, cu = [], []
        for k in range(len(P)):
            a, b, da, db, ua, ub = P[k], P[(k + 1) % len(P)], dist[k], dist[(k + 1) % len(P)], U[k], U[(k + 1) % len(P)]
            if da >= 0:
                cp.append(a); cu.append(ua)
            if (da >= 0) != (db >= 0):
                t = da / (da - db)
                cp.append(a.lerp(b, t)); cu.append(None if ua is None else (ua[0] + (ub[0] - ua[0]) * t, ua[1] + (ub[1] - ua[1]) * t))
        if len(cp) >= 3:
            idx = [mb.v(q) for q in cp]
            out.append(dict(idx=idx, mat=f['mat'], uv=None if U[0] is None else cu, smooth=f['smooth']))
    mb.faces = out


def twin_faces(mb, select, offset=0.0008):
    """reversed copy (offset `offset` behind the face) of every face whose centre passes select(centre): seen from behind it shows."""
    add = []
    for f in mb.faces:
        P = [mb.verts[i] for i in f['idx']]
        c = sum(P, V()) / len(P)
        if not select(c):
            continue
        nrm = V()
        for k in range(1, len(P) - 1):
            nrm += (P[k] - P[0]).cross(P[k + 1] - P[0])
        if nrm.length < 1e-12:
            continue
        nrm.normalize()
        add.append(([q - nrm * offset for q in reversed(P)], f['mat'], list(reversed(f['uv'])) if f['uv'] else None, f['smooth']))
    for pts, m, uv, sm in add:
        mb.face([mb.v(q) for q in pts], m, uv, sm)
    return len(add)


def unfight(mb, gap=0.0004, push=0.0008, _depth=0):
    """z-fight fix (user review 1: flickering cockpit surfaces; 1.2.3 had exactly coplanar overlapping faces in cockpit_panel and
    cockpit_floor, and the fal Vickers has doubled shells): for every pair of same-facing faces of DIFFERENT islands of this mesh
    that overlap within `gap` of each other's plane, the island with the smaller total area is moved `push` along the face normal
    (a decal / plate comes forward of its backing; a doubled shell hides inside). Returns the number of islands moved."""
    from mathutils.bvhtree import BVHTree
    n = len(mb.verts)
    par = list(range(n))
    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for f in mb.faces:
        r0 = find(f['idx'][0])
        for i in f['idx'][1:]:
            ri = find(i)
            if ri != r0:
                par[ri] = r0
    first = {}                                  # weld by position (the islands the game / the check see after welding)
    for i, p_ in enumerate(mb.verts):
        k_ = (round(p_.x, 5), round(p_.y, 5), round(p_.z, 5))
        if k_ in first:
            a_, b_ = find(i), find(first[k_])
            if a_ != b_:
                par[a_] = b_
        else:
            first[k_] = i
    isl = [find(f['idx'][0]) for f in mb.faces]
    area, nrm, cen = {}, [], []
    for f, k in zip(mb.faces, isl):
        P = [mb.verts[i] for i in f['idx']]
        nv = V()
        for j in range(1, len(P) - 1):
            nv += (P[j] - P[0]).cross(P[j + 1] - P[0])
        a = nv.length / 2
        area[k] = area.get(k, 0.0) + a
        nrm.append(nv.normalized() if nv.length > 0 else V((0, 0, 1)))
        cen.append(sum(P, V()) / len(P))
    tris, owner = [], []
    for fi, f in enumerate(mb.faces):
        for j in range(1, len(f['idx']) - 1):
            tris.append((f['idx'][0], f['idx'][j], f['idx'][j + 1])); owner.append(fi)
    if not tris:
        return 0
    tb = BVHTree.FromPolygons(mb.verts, tris)
    pairs = {}
    for fi, f in enumerate(mb.faces):
        c = cen[fi]
        for (co, no, ti, d) in tb.find_nearest_range(c, 0.002):
            fj = owner[ti]
            a, b = isl[fi], isl[fj]
            if a == b or nrm[fj].dot(nrm[fi]) < 0.999:
                continue
            if abs((c - co).dot(nrm[fi])) <= gap:
                pairs.setdefault(a, {})[b] = nrm[fi]
                pairs.setdefault(b, {})[a] = nrm[fi]
    if not pairs:
        return 0
    # each group of mutually overlapping islands: the largest stays, the others step out by 1, 2, ... x push (smaller = further out)
    move, seen = {}, set()
    for k in pairs:
        if k in seen:
            continue
        grp, st = [], [k]; seen.add(k)
        while st:
            u = st.pop(); grp.append(u)
            for w in pairs[u]:
                if w not in seen:
                    seen.add(w); st.append(w)
        grp.sort(key=lambda g: -area[g])
        base_n = next(iter(pairs[grp[0]].values()))
        for rank, g in enumerate(grp[1:], 1):
            move[g] = next(iter(pairs[g].values())) * (push * rank)
    for i in range(n):
        k = find(i)
        if k in move:
            mb.verts[i] = mb.verts[i] + move[k]
    return len(move)
