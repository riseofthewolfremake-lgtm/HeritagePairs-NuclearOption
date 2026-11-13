"""B-25H v3 rework (2026-10-30): smooth glazing, hatches, crew stations, articulated controls and gauges,
MFD screens, defensive turrets, pylons, T13E1 cannon, torn breaks, prop blur meshes.

Everything is generated from b25h_spec numbers (Blender space: nose +Y, up +Z, right wing +X, metres).
Unity mapping (export_b25h_v2.py): Unity local X = Blender local X, Unity local Y = Blender local Z,
Unity local Z = Blender local Y; a Blender rotation +a about an axis is Unity AngleAxis(-a, axis_unity).

Articulated objects follow the stock drivers' conventions (decompiled scripts, see docs/stock_damage_study.md):
  * ControlSurface: visibleMesh.localRotation = rest * AngleAxis(angle, Vector3.right)  -> local X = axis
  * Cockpit.Throttle (rotation): transform.localEulerAngles = (throttle*range, 0, 0)    -> local X = axis, rest identity
  * Turret: turret.localEulerAngles = (0, traverse, 0); elevationTransform.localEulerAngles = (elev, 0, 0)
            -> az rests identity under an oriented mount, el identity under az; forward = local +Z (Unity)
  * Canopy.CanopyHinge: transform.localEulerAngles = right * hingeAngle * open        -> hinge empty (local X = axis)
"""
import math, random
from mathutils import Vector, Quaternion, Matrix
import b25h_spec as S
from b25h_geom import (V, MeshBuf, loft, fan_cap, annulus, oriented_quad, cylinder, tube, box, circle_pts,
                       frame_from_axes, planar_uv, lerp, interp_table, RR_COUNTS, RR_HALF, RR_N, arc_lengths)
import b25h_parts as P
from b25h_parts import Part, fus_params, fus_ring, station_list, REQUIRED_Y, plate

FLOOR_Z = 0.10
CK = 'cockpit'


# ============================================================================================ helpers
def frame_x(xaxis, zhint=(0, 0, 1)):
    """frame quaternion whose local X = xaxis, local Z = zhint orthogonalised (Blender)."""
    return frame_from_axes(V(xaxis), V(zhint))


def rr_point(y, jf, inset=0.0):
    """point of the fuselage rounded-rectangle section at station y and FRACTIONAL ring index jf
    (same parametrisation as b25h_geom.rr_ring; integer jf gives exactly the ring vertex)."""
    hw, zb, zt, rt, rb = fus_params(y)
    hw, zb, zt = hw - inset, zb + inset, zt - inset
    rt, rb = max(rt - inset, 0.005), max(rb - inset, 0.005)
    hw = max(hw, 1e-4)
    rb = min(rb, hw, (zt - zb) * 0.5)
    rt = min(rt, hw, (zt - zb) - rb)
    nbf, nbc, ns, ntc, ntf = RR_COUNTS
    jf = jf % RR_N
    sgn = 1.0
    k = jf
    if jf > RR_HALF:
        k = RR_N - jf
        sgn = -1.0
    a0, a1, a2, a3 = nbf, nbf + nbc, nbf + nbc + ns, nbf + nbc + ns + ntc
    if k < a0:
        x, z = lerp(0, hw - rb, k / nbf), zb
    elif k < a1:
        a = -math.pi / 2 + (math.pi / 2) * (k - a0) / nbc
        x, z = hw - rb + rb * math.cos(a), zb + rb + rb * math.sin(a)
    elif k < a2:
        x, z = hw, lerp(zb + rb, zt - rt, (k - a1) / ns)
    elif k < a3:
        a = (math.pi / 2) * (k - a2) / ntc
        x, z = hw - rt + rt * math.cos(a), zt - rt + rt * math.sin(a)
    else:
        x, z = lerp(hw - rt, 0, (k - a3) / ntf), zt
    return V((sgn * x, y, z))


def rr_normal(y, jf):
    e = 1e-3
    a = rr_point(y, jf + e) - rr_point(y, jf - e)
    b = rr_point(y + e, jf) - rr_point(y - e, jf)
    n = a.cross(b).normalized()
    p = rr_point(y, jf)
    if n.dot(p - V((0, y, 0.25))) < 0:
        n = -n
    return n


def grid_faces(mb, grid, mat, outward, keep=None, uvfn=None, smooth=True, flip=False):
    """quads over a vertex-index grid (shared vertices -> smooth normals). outward(p)->vector."""
    for i in range(len(grid) - 1):
        for j in range(len(grid[0]) - 1):
            if keep is not None and not keep(i, j):
                continue
            idx = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
            pts = [mb.verts[k] for k in idx]
            n = (pts[1] - pts[0]).cross(pts[3] - pts[0])
            if n.length < 1e-12:
                n = (pts[2] - pts[1]).cross(pts[0] - pts[1])
            c = sum(pts, V()) / 4
            rev = n.dot(outward(c)) < 0
            if flip:
                rev = not rev
            cells = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if rev:
                idx = [idx[0]] + idx[:0:-1]
                cells = [cells[0]] + cells[:0:-1]
            uv = [uvfn(a, b) for a, b in cells] if (uvfn and mat in ('paint', 'gauges', 'screen', 'propdisc')) else None
            mb.face(idx, mat, uv, smooth)


def sweep_rect(mb, pts, ups, w, h_out, h_in, mat_out='paint', mat_side='paint', mat_in=CK, caps=True):
    """rectangular bar swept along a polyline; `ups` = outward normal per point. Shared vertices along the
    length (smooth), 90 deg corners (split by the angle rule). Paint faces get metre UVs (length, perimeter)."""
    n = len(pts)
    if n < 2:
        return
    rings = []
    acc = [0.0]
    for i in range(1, n):
        acc.append(acc[-1] + (pts[i] - pts[i - 1]).length)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        u = V(ups[i])
        u = (u - t * u.dot(t)).normalized()
        s = t.cross(u).normalized()
        rings.append([p + s * (w / 2) + u * h_out, p - s * (w / 2) + u * h_out,
                      p - s * (w / 2) - u * h_in, p + s * (w / 2) - u * h_in])
    per = [0.0, w, w + h_out + h_in, 2 * w + h_out + h_in]
    P_ = 2 * (w + h_out + h_in)

    def fm(i, j):
        return mat_out if j == 0 else (mat_in if j == 2 else mat_side)

    def uvf(ci, cj, j):
        v = per[cj]
        if j == 3 and cj == 0:
            v = P_
        return (acc[ci], v)
    loft(mb, rings, mat_out, closed=True, face_mat=fm, uvfunc=uvf)
    if caps:
        for r, d in ((rings[0], pts[0] - pts[1]), (rings[-1], pts[-1] - pts[-2])):
            oriented_quad(mb, r, mat_side, d, [planar_uv(q, d) for q in r] if mat_side == 'paint' else None)


def m2_gun(mb, origin, fwd, up, scale=1.0):
    """our own M2 .50 shaped like the stock 50cal_doorGun_barrel layout: origin = trunnion/mesh origin,
    back plate 0.345 behind, muzzle 1.20 ahead and 0.046 above the origin (S.STOCK_M2_MUZZLE)."""
    o, f, u = V(origin), V(fwd).normalized(), V(up).normalized()
    s = f.cross(u).normalized()
    P_ = lambda a, b, c: o + s * a + f * b + u * c
    # receiver (box along the barrel)
    rc = P_(0, 0.0, 0.0)
    q = frame_from_axes(s, u)       # local X = side, local Z = up -> local Y = fwd
    box(mb, P_(0, -0.07, 0.0), (0.075, 0.55, 0.12), 'metal_dark', rot=q)
    box(mb, P_(0, -0.34, -0.01), (0.09, 0.03, 0.13), 'metal_dark', rot=q)            # back plate
    box(mb, P_(-0.05, -0.05, 0.0), (0.03, 0.22, 0.06), 'metal_dark', rot=q)           # feed cover side
    for k in (-1, 1):                                                                 # spade grips
        cylinder(mb, P_(k * 0.035, -0.36, -0.02), P_(k * 0.035, -0.43, -0.02), 0.012, N=6)
    cylinder(mb, P_(0, 0.20, 0.046), P_(0, 0.62, 0.046), 0.034, N=12)                 # perforated jacket
    tube(mb, P_(0, 0.20, 0.046), P_(0, 1.20, 0.046), 0.021, 0.0065, N=10)             # barrel
    cylinder(mb, P_(0, 1.08, 0.046), P_(0, 1.17, 0.046), 0.026, N=10)                 # muzzle booster
    return P_(0, 1.20, 0.046)


def rand(seed):
    return random.Random(seed)


# ============================================================================================ canopy
CANOPY_J = (14.0, 36.0)          # ring-index range of the canopy cut-out (tcorner + tflat)
HATCH_TOP_J = (21.0, 29.0)


def canopy_ys():
    base = station_list(S.CANOPY_Y[1], S.CANOPY_Y[0], REQUIRED_Y)
    out = []
    for a, b in zip(base, base[1:]):
        for k in range(2):
            out.append(a + (b - a) * k / 2)
    out.append(base[-1])
    return out


def build_canopy():
    """smooth glazing: shared-vertex grid sampled on the true fuselage section (2x denser along the length,
    4 samples per ring segment), outer + inner surface; frames = continuous swept bars.
    The roof escape hatch is cut out of the same grid (hatch_cockpit_top)."""
    ys = canopy_ys()
    js = [CANOPY_J[0] + 0.25 * k for k in range(int((CANOPY_J[1] - CANOPY_J[0]) / 0.25) + 1)]
    th = 0.008
    gm, hm = MeshBuf(), MeshBuf()
    yh0, yh1 = S.HATCH_TOP_Y

    def in_hatch(y, j):
        return yh0 - 1e-6 <= y <= yh1 + 1e-6 and HATCH_TOP_J[0] - 1e-6 <= j <= HATCH_TOP_J[1] + 1e-6

    for mb, sel in ((gm, False), (hm, True)):
        go = [[mb.v(rr_point(y, j)) for j in js] for y in ys]
        gi = [[mb.v(rr_point(y, j) - rr_normal(y, j) * th) for j in js] for y in ys]

        def keep(i, j, sel=sel):
            yc = (ys[i] + ys[i + 1]) / 2
            jc = (js[j] + js[j + 1]) / 2
            return in_hatch(yc, jc) == sel
        out = lambda c: c - V((0, c.y, 0.25))
        grid_faces(mb, go, 'glass', out, keep)
        grid_faces(mb, gi, 'glass', lambda c: -out(c), keep)
    glass = Part('canopy_glass', 'fus_cockpit', (0, 3.6, 1.2), gm,
                 info=dict(note='smooth glazing grid (shared vertices, 2 surfaces 8 mm apart); roof hatch cut out'))
    # frames
    fm = MeshBuf()
    fw, fo, fi = 0.026, 0.012, 0.010

    def bar_y(y, j0, j1, mb=fm):
        jj = [j0 + (j1 - j0) * k / max(1, int(abs(j1 - j0) / 0.25)) for k in range(int(abs(j1 - j0) / 0.25) + 1)]
        sweep_rect(mb, [rr_point(y, j) for j in jj], [rr_normal(y, j) for j in jj], fw, fo, fi)

    def bar_j(j, y0, y1, mb=fm):
        yy = [y0 + (y1 - y0) * k / 24 for k in range(25)]
        sweep_rect(mb, [rr_point(y, j) for y in yy], [rr_normal(y, j) for y in yy], fw, fo, fi)
    for y in (4.55, 4.15, 3.80, 3.00, 2.75):
        bar_y(y, CANOPY_J[0], CANOPY_J[1])
    for j in (18.0, 32.0, 14.0, 36.0):
        bar_j(j, 4.55, 2.75)
    bar_j(25.0, 4.55, 3.80)              # top centre bar: windscreen part only (the hatch sits behind it)
    bar_j(25.0, 3.00, 2.75)
    # fixed hatch coaming (surround) on the canopy frame
    for y in (yh0 - 0.03, yh1 + 0.03):
        bar_y(y, HATCH_TOP_J[0] - 0.4, HATCH_TOP_J[1] + 0.4)
    for j in (HATCH_TOP_J[0] - 0.4, HATCH_TOP_J[1] + 0.4):
        bar_j(j, yh0 - 0.03, yh1 + 0.03)
    frame = Part('canopy_frame', 'fus_cockpit', (0, 3.6, 1.2), fm, info=dict(note='swept smooth frame bars'))
    # hatch: frame on its own perimeter
    for y in (yh0 + 0.012, yh1 - 0.012):
        bar_y(y, HATCH_TOP_J[0], HATCH_TOP_J[1], hm)
    for j in HATCH_TOP_J:
        bar_j(j, yh0, yh1, hm)
    bar_j(25.0, yh0, yh1, hm)
    hinge_l, hinge_r = rr_point(yh1, HATCH_TOP_J[1]), rr_point(yh1, HATCH_TOP_J[0])   # front edge, x<0 .. x>0
    axis = (hinge_r - hinge_l).normalized()
    piv = (hinge_l + hinge_r) / 2
    fr = frame_x(axis)
    hinge = Part('hatch_cockpit_top_hinge', 'fus_cockpit', piv, None, fr,
                 info=dict(kind='hatch_hinge', hinge_axis=tuple(axis)))
    hatch = Part('hatch_cockpit_top', 'hatch_cockpit_top_hinge', piv, hm, fr,
                 info=dict(kind='hatch', open_deg_blender=-100.0, note='glazed roof escape hatch, hinged at its front edge, '
                           'opens upward; jettison = Canopy.ejectionTransform'))
    return [glass, frame, hinge, hatch]


# ============================================================================================ hatches
def hatch_from_holes(name, parent, quads, open_deg_blender, note, hinge='front'):
    """floor hatch from shell hole quads: thick plate, hinge along its front (max y) edge, axis +X."""
    mb = MeshBuf()
    plate(mb, quads)
    pts = [p for o, i, uv in quads for p in o]
    yf = max(p.y for p in pts)
    front = [p for p in pts if abs(p.y - yf) < 1e-4]
    a, b = min(front, key=lambda p: p.x), max(front, key=lambda p: p.x)
    axis = (b - a).normalized()
    piv = (a + b) / 2
    fr = frame_x(axis)
    hp = Part(name + '_hinge', parent, piv, None, fr, info=dict(kind='hatch_hinge', hinge_axis=tuple(axis)))
    h = Part(name, name + '_hinge', piv, mb, fr, info=dict(kind='hatch', open_deg_blender=open_deg_blender, note=note))
    h.uv_group = 'fuselage'
    return [hp, h]


def build_waist_hatch(side, holes):
    """waist window = hinged hatch (top edge) with frame, smooth curved glass and a ball socket for the gun."""
    L = 'L' if side < 0 else 'R'
    qs = holes.get('waist' + L, [])
    pts = [p for o, i, uv in qs for p in o]
    y0, y1 = min(p.y for p in pts), max(p.y for p in pts)
    z0, z1 = min(p.z for p in pts), max(p.z for p in pts)
    yc, zc = (y0 + y1) / 2, (z0 + z1) / 2
    hwc = fus_params(yc)[0]
    sock = V((side * (hwc + 0.004), yc, zc))
    mb = MeshBuf()
    # glass: annulus between the window rectangle and the socket circle, gently bulged
    N = 48
    rect = []
    perim = 2 * ((y1 - y0) + (z1 - z0))
    for k in range(N):
        t = perim * k / N
        if t < (y1 - y0):
            y, z = y0 + t, z0
        elif t < (y1 - y0) + (z1 - z0):
            y, z = y1, z0 + (t - (y1 - y0))
        elif t < 2 * (y1 - y0) + (z1 - z0):
            y, z = y1 - (t - (y1 - y0) - (z1 - z0)), z1
        else:
            y, z = y0, z1 - (t - 2 * (y1 - y0) - (z1 - z0))
        rect.append((y, z))
    # align circle phase to the rectangle points (angle of each rect point about the socket)
    rings_o, rings_i = [], []
    for f in (0.0, 0.33, 0.66, 1.0):
        ro, ri = [], []
        for (y, z) in rect:
            a = math.atan2(z - zc, y - yc)
            cy, cz = yc + 0.07 * math.cos(a), zc + 0.07 * math.sin(a)
            py, pz = lerp(y, cy, f), lerp(z, cz, f)
            bump = 0.035 * math.sin(math.pi * f)
            x = side * (fus_params(py)[0] + 0.004 + bump)
            ro.append(V((x, py, pz)))
            ri.append(V((x - side * 0.006, py, pz)))
        rings_o.append(ro)
        rings_i.append(ri)
    go = [[mb.v(p) for p in r] + [mb.v(r[0])] for r in rings_o]
    gi = [[mb.v(p) for p in r] + [mb.v(r[0])] for r in rings_i]
    # weld the closing column to the first (same position) by reusing the index
    for g in (go, gi):
        for row in g:
            row[-1] = row[0]
    grid_faces(mb, go, 'glass', lambda c: V((side, 0, 0)))
    grid_faces(mb, gi, 'glass', lambda c: V((-side, 0, 0)))
    # socket ring (metal) around the hole
    # 1.8.13 r2: socket ring 0.110 / 0.127 (r3; was 0.068 / 0.085): the AN/M2 jacket at the 40 deg corners passed 1-2 mm from the rim
    so = circle_pts(sock, V((side, 0, 0)), 0.127 if P.TURRET_ROUND_HOLE else 0.085, 20, ref=V((0, 0, 1)))
    si = circle_pts(sock, V((side, 0, 0)), 0.110 if P.TURRET_ROUND_HOLE else 0.068, 20, ref=V((0, 0, 1)))
    annulus(mb, so, si, 'metal_dark', V((side, 0, 0)))
    sl_ = 0.010 if P.TURRET_ROUND_HOLE else 0.03     # r4: socket sleeve 3 cm -> 1 cm (the AN/M2 receiver front met its inner lip at the 40 deg corner)
    loft(mb, [si, [p - V((side * sl_, 0, 0)) for p in si]], 'metal_dark', outward=False)
    loft(mb, [so, [p - V((side * sl_, 0, 0)) for p in so]], 'metal_dark')
    # frame strip around the window (paint, outer) + inner lip
    w = 0.035
    hwm = fus_params(yc)[0] + 0.004
    for (ya, za), (yb, zb_) in (((y0, z0), (y1, z0)), ((y1, z0), (y1, z1)), ((y1, z1), (y0, z1)), ((y0, z1), (y0, z0))):
        dy, dz = yb - ya, zb_ - za
        ln = math.hypot(dy, dz)
        ny, nz = -dz / ln * w, dy / ln * w
        q = [V((side * hwm, ya - ny, za - nz)), V((side * hwm, yb - ny, zb_ - nz)), V((side * hwm, yb + ny, zb_ + nz)), V((side * hwm, ya + ny, za + nz))]
        oriented_quad(mb, q, 'paint', V((side, 0, 0)), [(p.y, p.z) for p in q])
        oriented_quad(mb, [p - V((side * 0.012, 0, 0)) for p in q], 'interior', V((-side, 0, 0)))
    axis = V((0, 1, 0))
    piv = V((side * hwm, yc, z1))
    fr = frame_x(axis)
    # opening sense: the free (lower) edge swings outward
    c = V((side * hwm, yc, zc)) - piv
    best = None
    for sg in (1, -1):
        q = Quaternion(axis, math.radians(95 * sg))
        o = (q @ c).x * side
        if best is None or o > best[0]:
            best = (o, sg)
    hinge = Part(f'hatch_waist_{L}_hinge', 'fus_rear', piv, None, fr, info=dict(kind='hatch_hinge', hinge_axis=tuple(axis)))
    hatch = Part(f'hatch_waist_{L}', f'hatch_waist_{L}_hinge', piv, mb, fr,
                 info=dict(kind='hatch', open_deg_blender=95.0 * best[1],
                           note='waist window hatch (glazed, ball socket for the waist gun), hinged at its top edge, '
                                'free edge swings outward; jettison = Canopy.ejectionTransform'))
    return [hinge, hatch], sock


# ============================================================================================ tear (torn breaks)
def _hash01(k, seed):
    r = random.Random(k * 7919 + seed * 104729)
    return r.random()


def jag(param, seed, amp, width):
    k = int(math.floor(param / width))
    h = _hash01(k, seed)
    return amp * (0.30 + 0.70 * h) * (1 if k % 2 == 0 else -1)


def tear_mesh(mb, p0, nrm, param_fn, amp, seed, width, mask=None, u_scale=1.0):
    """displace every vertex lying on the plane (p0, nrm) along nrm by jag(param). Deterministic in the vertex
    position, so the two parts sharing the plane get exactly complementary edges (no gap while intact).
    Paint UVs (u = coordinate along the axis for the fuselage and wing skins) move with the vertex."""
    p0, nrm = V(p0), V(nrm).normalized()
    moved = {}
    for i, v in enumerate(mb.verts):
        if abs((v - p0).dot(nrm)) < 2e-5:
            if mask is not None and not mask(v):
                continue
            moved[i] = jag(param_fn(v), seed, amp, width)
    for i, d in moved.items():
        mb.verts[i] = mb.verts[i] + nrm * d
    for f in mb.faces:
        if f['mat'] == 'paint' and f['uv']:
            uv = list(f['uv'])
            ch = False
            for k, vi in enumerate(f['idx']):
                if vi in moved:
                    uv[k] = (uv[k][0] + moved[vi] * u_scale, uv[k][1])
                    ch = True
            if ch:
                f['uv'] = uv
    return len(moved)


def fus_tear_param(v):
    return math.atan2(v.x, v.z - 0.25) * 0.9


def fus_amp(y):
    """amplitude limited by the nearest fuselage station on either side of the plane."""
    ys = sorted(set(round(r, 4) for r in REQUIRED_Y))
    gaps = [abs(r - y) for r in ys if abs(r - y) > 1e-4]
    return min(S.TEAR_AMP_FUS, 0.7 * min(gaps))


def tear_fuselage(parts_by_name):
    rep = {}
    for k, (y, (a, b)) in enumerate(S.FUS_TORN.items()):
        amp = fus_amp(y)
        mask = (lambda v: v.z < 0.80) if abs(y - S.NOSE_BASE_Y) < 1e-6 else None     # windscreen base stays straight
        n = 0
        for nm in (a, b):
            n += tear_mesh(parts_by_name[nm].mesh, (0, y, 0), (0, 1, 0), fus_tear_param, amp, 11 + k, 0.11, mask)
        rep[f'y={y}'] = dict(amp=round(amp, 3), verts=n)
    return rep


def wing_tear_param(v):
    return v.y + 7.0 * v.z


def tear_wings(parts_by_name):
    rep = {}
    for side, L in ((-1, 'L'), (1, 'R')):
        for k, (x, (a, b)) in enumerate(S.WING_TORN.items()):
            n = 0
            st = P.wing_station(x, side)
            nrm = st.cdir.cross(st.up).normalized()
            if nrm.x * side < 0:
                nrm = -nrm
            for nm in (a + '_' + L, b + '_' + L):
                n += tear_mesh(parts_by_name[nm].mesh, st.le, nrm, wing_tear_param, S.TEAR_AMP_WING, 31 + k, 0.10,
                               u_scale=side * abs(nrm.x))
            rep[f'{L} x={x}'] = n
    return rep


def fus_break_structure(mb, y, toward, seed):
    """set-back frame ring + stringer/longeron stubs protruding through the tear (all inside the skin).
    toward = +1 if the mating part lies at larger y."""
    r = rand(seed)
    ys = y - toward * S.TEAR_SETBACK
    hw, zb, zt, rt, rb = fus_params(ys)
    cen = V((0, ys, (zb + zt) / 2))
    ring = fus_ring(ys, S.SKIN_T)
    deep = [p + (cen - p).normalized() * 0.06 for p in ring]
    off = V((0, 0.018, 0))
    for j in range(RR_N):
        j1 = (j + 1) % RR_N
        a, b, c_, d = ring[j], ring[j1], deep[j1], deep[j]
        oriented_quad(mb, [a + off, b + off, c_ + off, d + off], 'structure', V((0, 1, 0)))
        oriented_quad(mb, [a - off, b - off, c_ - off, d - off], 'structure', V((0, -1, 0)))
        oriented_quad(mb, [d + off, c_ + off, c_ - off, d - off], 'structure', cen - (c_ + d) / 2)
    # stringer stubs: L-section stubs from the set-back frame through the tear plane, random lengths
    for jj in P.STRINGER_J + [3, RR_N - 3, 9, RR_N - 9]:
        a = fus_ring(ys, S.SKIN_T)[jj]
        L = S.TEAR_SETBACK + r.uniform(0.02, 0.085)
        b = V((a.x, ys + toward * L, a.z))
        bc = fus_ring(min(max(b.y, S.TAIL_END_Y + 0.05), S.NOSE_TIP_Y - 0.05), S.SKIN_T)[jj]
        b = V((bc.x, b.y, bc.z))
        inward = (V((0, a.y, 0.25)) - a)
        inward.y = 0
        inward = inward.normalized()
        tang = inward.cross(V((0, 1, 0))).normalized()
        w, h = 0.012, 0.028
        q1 = [a + tang * w, b + tang * w, b + tang * w + inward * h, a + tang * w + inward * h]
        q2 = [a - tang * w, b - tang * w, b - tang * w + inward * h, a - tang * w + inward * h]
        oriented_quad(mb, q1, 'structure', tang)
        oriented_quad(mb, q2, 'structure', -tang)
        oriented_quad(mb, [q1[2], q1[3], q2[3], q2[2]], 'structure', inward)
        oriented_quad(mb, [q1[1], q1[2], q2[2], q2[1]], 'structure', V((0, toward, 0)))
    # floor beam stub (where a floor exists)
    if zb < FLOOR_Z - 0.2:
        L = S.TEAR_SETBACK + r.uniform(0.03, 0.07)
        fz = FLOOR_Z - 0.06 if ys > -1.9 else max(-0.42, fus_params(ys)[1] + 0.30) - 0.05
        box(mb, (0, ys + toward * L / 2, fz), (2 * (hw - 0.08), L, 0.05), 'structure')


def wing_rib(mb, st, toward):
    """closed rib web (both faces + flange) filling the inner wing-box contour at station st."""
    ring = P.inner_box_ring(st, S.HINGE_F, 0.014)
    t = V(toward) * 0.004
    c = sum(ring, V()) / len(ring)
    fan_cap(mb, [p + t for p in ring], c + t, 'structure', toward)
    fan_cap(mb, [p - t for p in ring], c - t, 'structure', -V(toward))
    loft(mb, [[p - t for p in ring], [p + t for p in ring]], 'structure')


def wing_break_structure(mb, side, x, toward, seed):
    """set-back rib + spar caps/webs and stringers protruding through the tear plane (toward = +1 outboard)."""
    r = rand(seed)
    xs = x - toward * S.TEAR_SETBACK
    st_s = P.wing_station(xs, side)
    wing_rib(mb, st_s, V((side * toward, 0, 0)))
    for s in (0.15, 0.62):
        L = S.TEAR_SETBACK + r.uniform(0.03, 0.09)
        st_e = P.wing_station(xs + toward * L, side)
        ua, la = P.inner_pt(st_s, s, True), P.inner_pt(st_s, s, False)
        ub, lb = P.inner_pt(st_e, s, True), P.inner_pt(st_e, s, False)
        q = [ua, ub, lb, la]
        oriented_quad(mb, q, 'structure', V((0, 1, 0)))
        oriented_quad(mb, q, 'structure', V((0, -1, 0)))
        for (pa, pb, dn) in ((ua, ub, -st_s.up), (la, lb, st_s.up)):        # spar caps (flanges), longer
            L2 = L + r.uniform(0.01, 0.04)
            pb2 = pa + (pb - pa).normalized() * L2
            fl = [pa + V((0, 0.035, 0)), pb2 + V((0, 0.035, 0)), pb2 - V((0, 0.035, 0)), pa - V((0, 0.035, 0))]
            oriented_quad(mb, fl, 'structure', dn)
            oriented_quad(mb, [p + dn * 0.006 for p in fl], 'structure', -dn)
    # stringer stubs on the upper and lower skin
    for s in (0.25, 0.35, 0.45, 0.55, 0.68):
        for upper in (True, False):
            L = S.TEAR_SETBACK + r.uniform(0.0, 0.07)
            st_e = P.wing_station(xs + toward * L, side)
            a, b = P.inner_pt(st_s, s, upper), P.inner_pt(st_e, s, upper)
            dn = -st_s.up if upper else st_s.up
            q = [a + V((0, 0.008, 0)), b + V((0, 0.008, 0)), b - V((0, 0.008, 0)), a - V((0, 0.008, 0))]
            q2 = [p + dn * 0.022 for p in q]
            oriented_quad(mb, [q[0], q[1], q2[1], q2[0]], 'structure', V((0, 1, 0)))
            oriented_quad(mb, [q[3], q[2], q2[2], q2[3]], 'structure', V((0, -1, 0)))
