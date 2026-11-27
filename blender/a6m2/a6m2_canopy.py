"""A6M2 canopy (r8): a framed glasshouse built by ONE generator for two station sets.

  EXT  the exterior canopy (WT exterior stations, design 1): flat windscreen front pane + quarter panes + top pane, sliding hood,
       rear glazing.  Parts canopy_windscreen / canopy_hood / canopy_rear (exterior renderers: hidden in the cockpit view).
  CK   the cockpit-view canopy (WT COCKPIT-model stations: WT's own cockpit model puts the windscreen 0.3 m further aft than its
       exterior, measured r8 study/a6m2/r8/ortho_wt*): parts ckcanopy_fixed / ckcanopy_hood (cockpit layer only; the hood one is a
       child of canopy_hood so it slides with it).

Frames (user review 1: "rectangles glued together") are swept along polylines with MITRED joints (one shared vertex ring per path
vertex, so the faces of a bend meet edge to edge; the build welds coincident vertices), a bevelled profile (paint outside, cockpit
green inside), closed ends buried in the member they meet (each end runs past the other member's centre line). The model checks test
open boundary edges and joint gaps > 1 mm (check_a6m2_model.py, 'frames').
Numbers: pre-scale metres, ours frame; nothing here reads the reference.
"""
import math
from mathutils import Vector as V
import a6m2_spec as S
from b25h_geom import MeshBuf, fan_cap, planar_uv
from b25h_parts import Part

K = S.K

# --------------------------------------------------------------------------- station sets (pre-scale y; WT measured r8)
EXT = dict(
    name='ext',
    ws_front=0.200, ws_top=-0.115, arch=-0.264,         # windscreen: front pane bottom / top edge, rear arch (r8b: foot y +0.19 from the WT
                                                        # side view, r8 had +0.28 = too long and raked; arch at the hood front)
    fp_half_bot=0.105, fp_half_top=0.105, fp_top_z=0.955,
    diag_x=0.215,                                       # top-pane diagonals meet the arch at |x|
    hood=(-0.264, -1.006), hood_frames=[-0.620], rear_end=-1.985, rear_frames=[-1.370, -1.750],
    side_bar_x=0.225, spine=True, rear_side_bar_end_x=0.150,
)
CK = dict(
    name='ck',
    ws_front=-0.040, ws_top=-0.400, arch=-0.440,
    fp_half_bot=0.124, fp_half_top=0.130, fp_top_z=0.955,
    diag_x=0.200,
    hood=(-0.440, -1.070), hood_frames=[-0.725], rear_end=-1.985, rear_frames=[-1.400, -1.760],
    side_bar_x=0.195, spine=False, rear_side_bar_end_x=0.120, straight_sill=True,
)
# r8b (critique: frames 2-3x too thick, faceted rectangular sections, cream slivers): flat strips with rounded edges, smooth shaded.
FW, FH, FI, FC = 0.040, 0.004, 0.008, 0.003      # exterior: 40 mm flat strips (WT), 4 mm proud of the glass, 8 mm inside, 3 mm edge radius
CK_GLASS_OUT = 0.014     # r8f: cockpit-view glass 14 mm outside its frames (frame outer faces 3-5 mm proud)
CK_CORNER_FITTING = True   # r8e: cast fitting over the top windscreen corner (cockpit view)
CK_FRAME = (0.030, 0.003, 0.008, 0.003)          # cockpit view: 30 mm wide x 11 mm deep (r8: 38 x 26 read as beams); all cockpit green
HOOD_LIFT = 0.012                                # the hood rides over the fixed glazing
CK_CORNERS = []      # r8f: cockpit-view windscreen top corners (the bake keeps wear chips off the corner fittings)
FRAMES = []          # every swept member: dict(set, part, path (centre line before end extension), closed) - the 'frames' model check
CUR = dict(set='', part='', shape='ext')


def _body():
    import a6m2_parts as AP
    return AP


# CK shape: the WT cockpit glass section (glass.ckpt half-widths per height, r8 measure), normalised: (u = height share, half-width share);
# base z 0.62 (WT sill), straight sloping sides into a rounded flat top - the r7 superellipse bulged out and reached down to z 0.53
CK_U = [(0.0, 1.0), (0.324, 0.84), (0.564, 0.686), (0.803, 0.481), (0.923, 0.378), (0.983, 0.192), (1.0, 0.0)]
CK_ZB = 0.620


def _ck_profile(yb, m):
    """right half of the CK section at built y: m + 1 points from the sill (u 0) to the apex, even arc length."""
    xs, zt, ex, zb = sec_params(yb)
    if CUR.get('shape') == 'ck':
        zb = CK_ZB * K                           # EXT (r8b): the same WT glass shape on the exterior base (flat sloping sides, flat top)
    poly = [V((f * xs, yb, zb + u * (zt - zb))) for u, f in CK_U]
    dense = []                                   # r8b: resample + Laplacian smoothing (the arches showed kinks at the table rows)
    for a_, b_ in zip(poly, poly[1:]):
        for k in range(8):
            dense.append(a_ + (b_ - a_) * (k / 8))
    dense.append(poly[-1])
    for _ in range(12):
        dense = [dense[0]] + [(dense[i - 1] + dense[i] * 2 + dense[i + 1]) / 4 for i in range(1, len(dense) - 1)] + [V((0.0, yb, (dense[-1].z + dense[-2].z) / 2))]   # r8c: mirror boundary at the apex (game r8b z_up_apex: a crease down the arch apex - the fixed apex point left a kink)
    poly = dense
    L = [0.0]
    for a_, b_ in zip(poly, poly[1:]):
        L.append(L[-1] + (b_ - a_).length)
    out = []
    for k in range(m + 1):
        t = L[-1] * k / m
        i = max(j for j in range(len(L) - 1) if L[j] <= t + 1e-12) if t < L[-1] else len(L) - 2
        f = (t - L[i]) / max(L[i + 1] - L[i], 1e-12)
        out.append(poly[i] + (poly[i + 1] - poly[i]) * f)
    return out


def section(yb, n=33, lift=0.0):
    """canopy glass section at built y: base right -> apex -> base left (n points, n odd). EXT: the a6m2_parts superellipse;
    CK (CUR['shape'] == 'ck'): the WT cockpit glass shape."""
    m = n // 2                                   # r8b: both sets use the WT glass shape (the r8 exterior superellipse read as a dome / birdcage)
    r = _ck_profile(yb, m)
    pts = r + [V((-p.x, p.y, p.z)) for p in reversed(r[:-1])]
    if lift:
        pts = [p + V((p.x, 0, p.z - 0.4)).normalized() * lift for p in pts]
    return pts


def sec_params(yb):
    yp = yb / K
    xs = S.lin(S.CANOPY, yp, 1) * K
    zt = S.lin(S.CANOPY, yp, 2) * K
    ex = S.lin(S.CANOPY, yp, 3) * S.CANOPY_EXP_SCALE
    zb = _body().body_z_at(xs, yb)
    return xs, zt, ex, zb


def sec_z(x, yb):
    """glass z at |x| on the section at built y."""
    if True:
        r = _ck_profile(yb, 64)
        for a_, b_ in zip(r, r[1:]):
            if a_.x >= abs(x) >= b_.x:
                return a_.z + (b_.z - a_.z) * (a_.x - abs(x)) / max(a_.x - b_.x, 1e-12)
        return r[-1].z
    xs, zt, ex, zb = sec_params(yb)
    r = min(abs(x) / xs, 0.999)
    return zb + (zt - zb) * (1 - r ** ex) ** (1.0 / ex)


def out_normal(p):
    return V((p.x, 0, p.z - 0.40)).normalized()


# --------------------------------------------------------------------------- mitred sweep
def _profile():
    """r8b: flat strip with rounded edges (3 points per corner, <= 30 deg between faces, so the build's 38 deg sharp-edge rule keeps
    it smooth-shaded). Exterior: livery on the outer face and upper sides, cockpit green under the glass; cockpit view: all green."""
    ck = CUR.get('shape') == 'ck'
    fw, fh, fi, fc = CK_FRAME if ck else (FW, FH, FI, FC)
    w = fw / 2
    pts, mats = [], []
    corners = [((w - fc, fh - fc), 0), ((-w + fc, fh - fc), 90), ((-w + fc, -fi + fc), 180), ((w - fc, -fi + fc), 270)]
    for (cx, cy), a0 in corners:
        for k in range(4):
            a = math.radians(a0 + 30 * k)
            pts.append((cx + fc * math.cos(a), cy + fc * math.sin(a)))
    for i in range(len(pts)):
        ym = (pts[i][1] + pts[(i + 1) % len(pts)][1]) / 2
        mats.append('interior' if ck or ym < 0 else 'paint')
    return pts, mats


def sweep(mb, path, normals, closed=False, ext0=0.0, ext1=0.0, scale=1.0):
    """bevelled frame bar along path (points on the glass surface), outward normals per point. Mitred: at an interior vertex the
    side offset runs along the bisector of the two segment sides, scaled by 1/cos so both segments keep the full width.
    ext0 / ext1 extend an open bar beyond its first / last point (buried in the member it meets)."""
    P = [V(p) for p in path]
    N = [V(n).normalized() for n in normals]
    FRAMES.append(dict(set=CUR['set'], part=CUR['part'], path=[tuple(p) for p in P], closed=closed))
    if not closed:
        if ext0:
            P[0] = P[0] + (P[0] - P[1]).normalized() * ext0
        if ext1:
            P[-1] = P[-1] + (P[-1] - P[-2]).normalized() * ext1
    n = len(P)
    prof, pm = _profile()
    rings = []
    for i in range(n):
        if closed:
            a, b = P[i - 1], P[(i + 1) % n]
            t0, t1 = (P[i] - a).normalized(), (b - P[i]).normalized()
        else:
            t0 = (P[i] - P[i - 1]).normalized() if i > 0 else (P[1] - P[0]).normalized()
            t1 = (P[i + 1] - P[i]).normalized() if i < n - 1 else t0
        Ni = N[i]
        s0, s1 = t0.cross(Ni).normalized(), t1.cross(Ni).normalized()
        sm = (s0 + s1)
        if sm.length < 1e-6:
            sm = s0
        sm.normalize()
        k = 1.0 / max(sm.dot(s0), 0.35)
        rings.append([P[i] + sm * (sx * k * scale) + Ni * (sn * scale) for sx, sn in prof])
    m = len(prof)
    base = len(mb.verts)
    idx = [[mb.v(p) for p in r] for r in rings]
    segs = n if closed else n - 1
    for i in range(segs):
        r0, r1 = idx[i], idx[(i + 1) % n]
        for j in range(m):
            j1 = (j + 1) % m
            q = [r0[j], r1[j], r1[j1], r0[j1]]
            pts = [mb.verts[x] for x in q]
            c = sum(pts, V()) / 4
            ctr = (P[i] + P[(i + 1) % n]) / 2
            nrm = (pts[1] - pts[0]).cross(pts[3] - pts[0])
            if nrm.dot(c - ctr) < 0:
                q = [q[0], q[3], q[2], q[1]]
            mb.face(q, pm[j], None, True)
    if not closed:
        cm = 'interior' if CUR.get('shape') == 'ck' else 'paint'
        for r, tw, pc in ((rings[0], P[0] - P[1], P[0]), (rings[-1], P[-1] - P[-2], P[-1])):
            fan_cap(mb, r, sum(r, V()) / m, cm, tw, uvfunc=(lambda p, t=tw: planar_uv(p, t)) if cm == 'paint' else None)
    return mb


# --------------------------------------------------------------------------- glass
def glass_quad_strip(mb, A, B):
    """two-sided glass between two polylines of equal length (A row, B row)."""
    if CUR.get('shape') == 'ck' and CUR.get('part') == 'windscreen' and CK_GLASS_OUT > 0:     # windscreen panes only (hood / rear glass sit on the sill rails)
        # r8f (game r8e z_up_jointL: a light ragged patch over the corner block / top bar): the flat cockpit-view panes cut INSIDE the
        # curved arch and the corner members, and the faint glass drew its jagged triangle edges over the frames. The cockpit-view glass
        # (seen only from the seat) moves CK_GLASS_OUT outward, beyond the frames' outer faces: every frame is in front of the glass.
        # (faded to 0 within 20-100 mm over the sill / deck line, so the glass still meets the sill: no gap to the outside there)
        def _off(p):
            f = min(max((p.z - _deck_z(p.x, p.y) - 0.02) / 0.08, 0.0), 1.0)
            return p + out_normal(p) * (CK_GLASS_OUT * f)
        A = [_off(p) for p in A]; B = [_off(p) for p in B]
    for i in range(len(A) - 1):
        q = [A[i], A[i + 1], B[i + 1], B[i]]
        c = sum(q, V()) / 4
        nrm = out_normal(c)
        for sgn in (1, -1):
            qq = q
            nn = (qq[1] - qq[0]).cross(qq[3] - qq[0])
            if nn.length < 1e-12:
                nn = (qq[2] - qq[0]).cross(qq[3] - qq[1])
            if nn.dot(nrm) * sgn < 0:
                qq = [qq[0], qq[3], qq[2], qq[1]]
            mb.poly(qq, 'glass', None, False)


def glass_loft(mb, rings):
    for a, b in zip(rings, rings[1:]):
        glass_quad_strip(mb, a, b)


def _deck_z(x, yb):
    return _body().body_z_at(abs(x), yb)


def windscreen(st, lift=0.0):
    """flat windscreen panes and their frames. Returns (glass mb, frame mb, arch points used for the hood seam)."""
    yA, yB, yC = st['ws_front'] * K, st['ws_top'] * K, st['arch'] * K
    hb, ht = st['fp_half_bot'] * K, st['fp_half_top'] * K
    zB = st['fp_top_z'] * K
    arch = section(yC, n=41)
    dx = st['diag_x'] * K
    # arch points: index of |x| = dx on each side (nearest)
    iR = min(range(len(arch) // 2), key=lambda i: abs(arch[i].x - dx))
    iL = len(arch) - 1 - iR
    D_R, D_L = arch[iR], arch[iL]
    C_R, C_L = arch[0], arch[-1]
    A_R = V((hb, yA, _deck_z(hb, yA) + 0.002)); A_L = V((-hb, yA, A_R.z))
    B_R = V((ht, yB, zB)); B_L = V((-ht, yB, zB))
    g = MeshBuf()
    nb = 8
    # front pane (bilinear: A_L A_R / B_L B_R), rows bottom -> top
    rowsF = [[A_L + (A_R - A_L) * (k / nb) + ((B_L + (B_R - B_L) * (k / nb)) - (A_L + (A_R - A_L) * (k / nb))) * (j / 6) for k in range(nb + 1)] for j in range(7)]
    glass_loft(g, rowsF)
    # quarter panes: lower edge A -> C along the deck, upper edge B -> D -> (arch down to C)
    for side, A, B, D, C, arc in ((1, A_R, B_R, D_R, C_R, arch[:iR + 1][::-1]), (-1, A_L, B_L, D_L, C_L, arch[iL:])):
        # upper boundary: B, then the arch from D down to C ; lower boundary: deck line from A to C (same count)
        up = [B] + arc                       # arc runs D ... C
        nU = len(up)
        lo = []
        for k in range(nU):
            t = k / (nU - 1)
            x = A.x + (C.x - A.x) * t
            y = A.y + (C.y - A.y) * t
            zl = _deck_z(x, y) + 0.002
            if st.get('straight_sill'):
                zl = max(zl, A.z + (C.z - A.z) * t)
            lo.append(V((x, y, zl)))
        lo[-1] = C
        rows = [[lo[k] + (up[k] - lo[k]) * (j / 4) for k in range(nU)] for j in range(5)]
        glass_loft(g, rows)
    # top pane: B_L B_R -> arch between D_R and D_L
    topA = arch[iR:iL + 1]                  # D_R ... apex ... D_L
    nT = len(topA)
    frontT = [B_R + (B_L - B_R) * (k / (nT - 1)) for k in range(nT)]
    rowsT = [[frontT[k] + (topA[k] - frontT[k]) * (j / 4) for k in range(nT)] for j in range(5)]
    glass_loft(g, rowsT)
    # frames: front pane rectangle (closed loop), diagonals B-D, base rails A-C, the arch
    f = MeshBuf()
    loop = [A_L, A_R, B_R, B_L]
    npane = (A_R - A_L).cross(B_L - A_L).normalized()           # r8b: the front pane's own normal (the radial out_normal lay almost in
    if npane.y < 0:                                              # the pane plane on the posts and twisted the loop's profile)
        npane = -npane
    sweep(f, loop, [npane] * 4, closed=True)
    for B, D in ((B_R, D_R), (B_L, D_L)):
        # r8c (game r8b z_up_jointL: the diagonal's start stuck out past the pane corner as a pointed stub, a ragged notch): it starts half a
        # frame width up its own line, so its end face sits inside the corner of the pane loop
        B2 = B + (D - B).normalized() * ((CK_FRAME[0] if st['name'] == 'ck' else FW) * 0.5)
        D2 = D
        if st['name'] == 'ck' and CK_CORNER_FITTING:
            # r8f (game r8e z_up_jointL / ck_cornerL: the rail still ended in a pointed stub past the ARCH and notched the corner block):
            # the rail starts AT the corner point (its end face inside the corner block) and stops 0.35 frame widths short of the arch
            # centre line - its oblique end face no longer reaches past the arch's far edge
            B2 = B
            D2 = D - (D - B).normalized() * (CK_FRAME[0] * 0.35)
        sweep(f, [B2, D2], [out_normal(B2), out_normal(D2)])          # r8b: ends on the loop / arch centre lines (r8 overran: 'knobs')
        if st['name'] == 'ck' and CK_CORNER_FITTING:
            # r8e (game r8d z_up_jointL, still: a ragged notch at the top windscreen corner and the diagonal's pointed start past it): the
            # pane loop's mitred corner and the diagonal's oblique start never matched. A short cast corner fitting (the frame profile
            # x 1.25) over the joint, from 0.6 frame widths behind the corner to 1.4 up the diagonal, hides both ends inside it.
            w_ = CK_FRAME[0]; d_ = (D - B).normalized()
            CK_CORNERS.append(tuple(B))
            Bo = B_L if B is B_R else B_R
            tb = (B - Bo).normalized()                                   # along the top bar, outward through the corner
            P0, P1 = B - tb * (1.0 * w_), B + tb * (0.45 * w_)
            sweep(f, [P0, P1], [npane, npane], scale=1.8)               # the pane loop's own normal: coplanar profile, no twist
    for A, C in ((A_R, C_R), (A_L, C_L)):
        pts = []
        for k in range(9):
            t = k / 8
            x = A.x + (C.x - A.x) * t; y = A.y + (C.y - A.y) * t
            zl = _deck_z(x, y) + 0.002
            if st.get('straight_sill'):
                zl = max(zl, A.z + (C.z - A.z) * t)
            pts.append(V((x, y, zl)) if 0 < k < 8 else (A if k == 0 else C))
        sweep(f, pts, [out_normal(p) for p in pts])
    archx = [arch[0] - V((0, 0, 0.012))] + arch + [arch[-1] - V((0, 0, 0.012))]
    # r8b (game r8 z_r45_top: a step and hairline where the hood's front frame met the windscreen arch): the fixed arch under the hood
    # arch is 1.35x wider / deeper in the cockpit set, so from the seat it covers the lifted hood arch completely
    sweep(f, archx, [out_normal(p) for p in archx], scale=1.35 if st['name'] == 'ck' else 1.0)
    return g, f, (A_R, B_R, C_R, D_R)


def glasshouse(st, y0, y1, frames, lift, side_bar_x, side_bar_end_x=None, spine=False, end_frames=True, front_frame=True):
    """lofted glass between built y0 > y1 with arches at y0, y1 (end_frames) and at `frames`; base rails; longitudinal bars at
    |x| = side_bar_x (tapering to side_bar_end_x at y1) and an optional centre spine."""
    nseg = max(4, int(abs(y0 - y1) / 0.05))
    ys = [y0 + (y1 - y0) * k / nseg for k in range(nseg + 1)]
    rings = [section(y, n=33, lift=lift) for y in ys]
    g = MeshBuf()
    glass_loft(g, rings)
    f = MeshBuf()
    fys = sorted(set([round(v, 5) for v in (([y0] if front_frame else []) + [y1] if end_frames else []) + list(frames)]), reverse=True)
    for fy in fys:
        a = section(fy, n=41, lift=lift)
        big = 1.35 if (CUR.get('shape') == 'ck' and not lift and abs(fy - y0) < 1e-6 and CUR.get('part') == 'rear') else 1.0
        leg = 0.012                                                            # r8b: legs end inside the base rail (12 mm < half width)
        a = [a[0] - V((0, 0, leg))] + a + [a[-1] - V((0, 0, leg))]
        sweep(f, a, [out_normal(p) for p in a], scale=big)               # CK rear front arch: covers the hood's end arch from inside
    for side in (0, -1):                                                       # base rails (the sill line)
        rail = [r[side] for r in rings]
        sweep(f, rail, [out_normal(p) for p in rail])
    for sgn in (1, -1):
        bar = []
        for k, y in enumerate(ys):
            t = k / nseg
            xb = (side_bar_x + ((side_bar_end_x or side_bar_x) - side_bar_x) * t) * K
            p = V((sgn * xb, y, sec_z(xb, y)))
            if lift:
                p = p + out_normal(p) * lift
            bar.append(p)
        # r8b: longitudinal rails 1 mm under the arches' outer face so the arches read continuous over them (no coplanar crossing)
        sweep(f, [p - out_normal(p) * 0.001 for p in bar], [out_normal(p) for p in bar])
    if spine:
        sp = [r[len(r) // 2] - V((0, 0, 0.001)) for r in rings]
        sweep(f, sp, [V((0, 0, 1))] * len(sp))
    return g, f


def ck_sill(st):
    """CK only: opaque cockpit-green sill panels from the glass base (z 0.62, the WT sill) down into the fuselage skin, both sides,
    from the windscreen front to the rear glazing end (two-sided, 'interior'); under the windscreen they follow the quarter-pane edge."""
    mb = MeshBuf()
    yA, yC = st['ws_front'] * K, st['arch'] * K
    hb = st['fp_half_bot'] * K
    A = V((hb, yA, _deck_z(hb, yA) + 0.002))
    C = section(yC, n=41)[0]
    top, bot = [], []
    for k in range(9):
        t = k / 8
        x = A.x + (C.x - A.x) * t; y = A.y + (C.y - A.y) * t
        z = max(_deck_z(x, y) + 0.002, A.z + (C.z - A.z) * t)
        top.append(V((x, y, z))); bot.append(V((x, y, _deck_z(x, y) - 0.012)))
    ys = [yC + (st['rear_end'] * K - yC) * k / 30 for k in range(1, 31)]
    for y in ys:
        b = section(y, n=41)[0]
        top.append(b); bot.append(V((b.x, y, _deck_z(b.x, y) - 0.012)))
    for sgn in (1, -1):
        T = [V((sgn * p.x, p.y, p.z)) for p in top]; Bm = [V((sgn * p.x, p.y, p.z)) for p in bot]
        for i in range(len(T) - 1):
            q = [Bm[i], Bm[i + 1], T[i + 1], T[i]]
            for tw in (V((-sgn, 0, 0)), V((sgn, 0, 0))):
                nn = (q[1] - q[0]).cross(q[3] - q[0])
                qq = q if nn.dot(tw) > 0 else [q[0], q[3], q[2], q[1]]
                mb.poly(qq, 'interior', None, False)
    return mb


def grab_handle(st):
    """CK: the U-shaped grab handle on the inside of the right windscreen post (WT), a bent 10 mm tube standing 22 mm aft of the post."""
    from b25h_geom import cylinder
    mb = MeshBuf()
    arch = section(st['arch'] * K, n=81)
    # r8c (game r8b z_bar: the C cut across the right pane): smaller (~80 mm), standing 22 mm off the post TOWARD THE PILOT (-y) so from
    # the seat it lies over the post, as WT's
    pts = [p for p in arch if p.x > 0.15 and 0.82 < p.z < 0.90]
    if len(pts) < 2:
        return mb
    a, b = pts[0], pts[-1]
    a0, b0 = a - out_normal(a) * CK_FRAME[2], b - out_normal(b) * CK_FRAME[2]
    aft = V((0, -0.022, 0))
    path = [a0 + V((0, 0.004, 0)), a0 + aft, b0 + aft, b0 + V((0, 0.004, 0))]
    for k, (p0, p1) in enumerate(zip(path, path[1:])):          # each segment runs 2 mm into the next (no welded inner caps)
        d_ = (p1 - p0).normalized()
        cylinder(mb, p0 - d_ * (0.0 if k == 0 else 0.002), p1 + d_ * (0.002 if k < len(path) - 2 else 0.0), 0.005 - 0.0002 * k, N=10, mat='interior')
    return mb


def build_canopy_set(st, prefix):
    """parts of one station set. EXT: canopy_windscreen (glass + frames, on fus_center), canopy_hood (Canopy object), canopy_rear.
    CK: ckcanopy_fixed (windscreen + rear), ckcanopy_hood (child of canopy_hood)."""
    CUR['set'] = st['name']; CUR['part'] = 'windscreen'; CUR['shape'] = st['name']
    gW, fW, _ = windscreen(st)
    CUR['part'] = 'hood'
    h0, h1 = st['hood'][0] * K, st['hood'][1] * K
    gH, fH = glasshouse(st, h0, h1, [y * K for y in st['hood_frames']], HOOD_LIFT, st['side_bar_x'], spine=st['spine'])
    yr0 = h1                     # r8b: the rear's front arch lies UNDER the hood's end arch (same station, 12 mm in): one frame line, not a pair
    CUR['part'] = 'rear'
    gR, fR = glasshouse(st, yr0, st['rear_end'] * K, [y * K for y in st['rear_frames']], 0.0, st['side_bar_x'],
                        st['rear_side_bar_end_x'], spine=False)
    # the fixed part's front arch is the windscreen arch; join windscreen and the stretch between the arch and the hood front for CK
    parts = []
    piv_h = (0, (h0 + h1) / 2, 0.85)
    if prefix == 'canopy':
        w = MeshBuf(); w.extend(gW); w.extend(fW)
        parts.append(Part('canopy_windscreen', 'fus_center', (0, (st['ws_front'] + st['arch']) / 2 * K, 0.85), w, info=dict(kind='glass')))
        hm = MeshBuf(); hm.extend(gH); hm.extend(fH)
        parts.append(Part('canopy_hood', 'fus_center', piv_h, hm, info=dict(kind='canopy', slide_m=S.CANOPY_SLIDE * K)))
        rm = MeshBuf(); rm.extend(gR); rm.extend(fR)
        parts.append(Part('canopy_rear', 'fus_center', (0, (yr0 + st['rear_end'] * K) / 2, 0.85), rm, info=dict(kind='glass')))
    else:
        fx = MeshBuf(); fx.extend(gW); fx.extend(fW)
        fx.extend(grab_handle(st))
        fx.extend(gR); fx.extend(fR)
        fx.extend(ck_sill(st))
        parts.append(Part('ckcanopy_fixed', 'fus_center', (0, -0.9, 0.85), fx, info=dict(kind='ck_canopy', layer='cockpit only')))
        hm = MeshBuf(); hm.extend(gH); hm.extend(fH)
        parts.append(Part('ckcanopy_hood', 'canopy_hood', piv_h, hm, info=dict(kind='ck_canopy', layer='cockpit only, slides with the hood')))
    return parts


def build_canopy():
    FRAMES.clear(); CK_CORNERS.clear()
    out = build_canopy_set(EXT, 'canopy') + build_canopy_set(CK, 'ckcanopy')
    CUR['shape'] = 'ext'
    return out
