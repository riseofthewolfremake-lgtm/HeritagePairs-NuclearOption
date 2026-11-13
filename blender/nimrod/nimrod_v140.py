"""Hawker Nimrod 1.4.0 geometry (user review 2, 2026-11-02): hand-refined parts that replace the 1.3.x ones, measured against the
War Thunder reference (numbers only, nimrod_spec 1.4.0 block) and the user's screenshots refs/nimrod_user_review_2.

  tail      stabiliser / elevator planform with the reference hinge line (-4.38) and horn balances, fin + rudder outline (rounded top,
            mass-balance horn), two tail struts per side + bracing wires to the fin, a sprung tail SKID (no wheel).
  hook      visible A-frame arrester hook under the belly (separate mesh `hook_visual`, driven to follow the functional hook).
  nose      radiator bath with vertical shutter slats and the round openings, finned oil cooler under the nose, pointed spinner
            with a ring joint and the Hucks starter dog, paddle propeller blades.
  sight     ring-and-bead sight (ring post ahead of the windscreen, bead post on the cowling).
  lamps     period wing-tip navigation lamps (red / green glass bulb in a chrome housing; no light source).
No bpy (mathutils only); every function returns MeshBuf(s) in the Blender model frame (x right, y nose, z up).
"""
import math
from mathutils import Vector, Matrix
from b25h_geom import V, MeshBuf, loft, fan_cap, oriented_quad, cylinder, box, circle_pts, Station, section_cap, cos_space, ring_arc_uv, planar_uv
import nimrod_spec as S
import nimrod_structure as ST


def interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    for (a, A), (b, B) in zip(table, table[1:]):
        if a <= x <= b:
            return A + (B - A) * (x - a) / (b - a)


def tube_pts(mb, pts, r, mat, N=8, cap=True):
    for a, b in zip(pts, pts[1:]):
        cylinder(mb, V(a), V(b), r, N=N, mat=mat, cap0=cap, cap1=cap, smooth=True)
    for p in pts[1:-1]:                                              # joint balls (no gaps at bends)
        sphere(mb, p, r * 1.02, mat, n=N)


def sphere(mb, c, r, mat, n=8, sz=1.0):
    rings = []
    for k in range(1, n // 2 + 1):
        a = math.pi * k / (n // 2 + 1) - math.pi / 2
        rings.append([V(c) + V((math.cos(a) * math.cos(2 * math.pi * j / n) * r, math.cos(a) * math.sin(2 * math.pi * j / n) * r, math.sin(a) * r * sz)) for j in range(n)])
    loft(mb, rings, mat, smooth=True)
    fan_cap(mb, rings[0], V(c) - V((0, 0, r * sz)), mat, V((0, 0, -1)), smooth=True)
    fan_cap(mb, rings[-1], V(c) + V((0, 0, r * sz)), mat, V((0, 0, 1)), smooth=True)


def lathe(mb, prof, c, axis, mat, N=24, cap0=True, cap1=True, ref=None):
    """surface of revolution: prof = [(r, along)], c = origin, axis = unit direction."""
    axis = V(axis).normalized()
    rings = [circle_pts(V(c) + axis * a, axis, max(r, 1e-4), N, ref=ref) for r, a in prof]
    f0 = len(mb.faces)
    grid, _ = loft(mb, rings, mat, smooth=True)
    # 1.4.1: loft() orients by the first ring pair with a non-zero score; a flat disc band (the spinner back plate) scores ~0, so its
    # rounding noise decided and the spinner came out inside-out. Re-orient every band from the profile: closed with the axis, the
    # (along, r) polygon's winding gives the outward side of each segment.
    pa = [(a, r) for r, a in prof] + [(prof[-1][1], 0.0), (prof[0][1], 0.0)]
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pa, pa[1:] + pa[:1]))
    sgn = 1.0 if area < 0 else -1.0
    ring_of = {vi: i for i, row in enumerate(grid) for vi in row}
    for f in mb.faces[f0:]:
        i = min(ring_of[k] for k in f['idx'])
        (r0, a0), (r1, a1) = prof[i], prof[i + 1]
        pts = [mb.verts[k] for k in f['idx']]
        cen = sum(pts, V()) / len(pts)
        rad = cen - V(c) - axis * (cen - V(c)).dot(axis)
        rad = rad.normalized() if rad.length > 1e-9 else V((0, 0, 0))
        want = (axis * -(r1 - r0) + rad * (a1 - a0)) * sgn
        nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if nrm.length < 1e-12 and len(pts) > 3:
            nrm = (pts[2] - pts[0]).cross(pts[3] - pts[0])
        if nrm.dot(want) < 0:
            f['idx'] = f['idx'][::-1]
            if f['uv']:
                f['uv'] = f['uv'][::-1]
    if cap0:
        fan_cap(mb, rings[0], V(c) + axis * prof[0][1], mat, -axis * sgn)
    if cap1:
        fan_cap(mb, rings[-1], V(c) + axis * prof[-1][1], mat, axis * sgn)
    return rings


# =========================================================================================== tail: stabiliser + elevator
STAB_T = 0.085
WALL_OUT = -4.158      # stabiliser wall ahead of the horn (horn front -4.17: 12 mm, the horn swings on a 0.21 m radius < 0.222)
WALL_IN = S.ELEV_HINGE + 0.052
HORN_FRONT = -4.17


def stab_station(x, side):
    le = interp(S.STAB_LE_TABLE, x)
    te = interp(S.ELEV_TE_TABLE, x)
    return Station(side * x, V((side * x, le, S.STAB_Z)), V((0, -1, 0)), V((0, 0, 1)), max(le - te, 0.02), STAB_T, m=0.0)


def frac(st, y):
    return (st.le.y - y) / st.chord


def ring_to(st, s_list):
    """closed ring over chord fractions s_list (ascending, s_list[0] = 0 = LE): upper last -> LE, lower LE -> last."""
    up = [st.point(s, True) for s in reversed(s_list)]
    lo = [st.point(s, False) for s in s_list[1:]]
    return up + lo


def ring_between(st, s0, s1, n=4):
    ss = [s0 + (s1 - s0) * k / n for k in range(n + 1)]
    up = [st.point(s, True) for s in reversed(ss)]
    lo = [st.point(s, False) for s in ss]
    return up + lo


def loft_closed(mb, rings, sts, wall_mat='cove', wall_seg=None, uv=True):
    k = len(rings[0])
    fm = (lambda i, j: wall_mat if j == k - 1 else 'paint') if wall_seg == 'last' else None
    loft(mb, rings, 'paint', face_mat=fm, uvfunc=ring_arc_uv(rings, [st.span for st in sts]) if uv else None)


def stab_v140(side):
    """returns (stab mesh, elevator mesh, elevator nose mesh, hinge pivot, hinge axis, root station, lip info, strut mesh)."""
    sgn = side
    NB = 9
    # ---- fixed stabiliser: inner box LE -> WALL_IN (x 0.16 .. HORN_X - 6 mm), outer box LE -> WALL_OUT (HORN_X - 6 mm .. 1.565)
    xin = [0.16, 0.30, 0.45, 0.65, 0.80, 0.95, 1.10, 1.16, 1.21, S.ELEV_HORN_X - 0.006]
    xout = [S.ELEV_HORN_X - 0.006, 1.31, 1.36, 1.41, 1.46, 1.51, 1.545, 1.565]
    sm = MeshBuf()

    def fr_in(st):
        so = frac(st, WALL_OUT)
        return cos_space(0.0, so, NB) + [so + (frac(st, WALL_IN) - so) * k / 2 for k in (1, 2)]

    def fr_out(st):
        return cos_space(0.0, frac(st, WALL_OUT), NB)
    sin_ = [stab_station(x, side) for x in xin]
    sout = [stab_station(x, side) for x in xout]
    if side < 0:
        sin_ = list(reversed(sin_)); sout = list(reversed(sout))
    rin = [ring_to(st, fr_in(st)) for st in sin_]
    rout = [ring_to(st, fr_out(st)) for st in sout]
    loft_closed(sm, rin, sin_, wall_seg='last')
    loft_closed(sm, rout, sout, wall_seg='last')
    out_dir = V((side, 0, 0))
    # step wall at HORN_X: the part of the inner box's end section aft of WALL_OUT faces outboard (the horn's side gap)
    rend = rin[-1] if side > 0 else rin[0]
    section_cap(sm, rend, 'cove', out_dir)
    rbeg = rout[0] if side > 0 else rout[-1]
    section_cap(sm, rbeg, 'cove', -out_dir)
    tip = rout[-1] if side > 0 else rout[0]
    c = sum(tip, V()) / len(tip)
    fan_cap(sm, tip, c, 'paint', out_dir, uvfunc=lambda p: planar_uv(p, out_dir))
    # skin lips over the elevator nose (inner part), dark cove underneath
    import nimrod_parts as NP
    axis_p0 = V((0.0, S.ELEV_HINGE, S.STAB_Z)); axis = V((1, 0, 0))
    lip_sts = [stab_station(x, side) for x in xin]
    if side < 0:
        lip_sts = list(reversed(lip_sts))
    for up_ in (True, False):
        NP.lip(sm, lip_sts, lambda st: frac(st, WALL_IN), lambda st: frac(st, S.ELEV_HINGE + 0.012), up_)
    # ---- elevator: body behind the hinge axis (ELEV_ROOT_X .. TE meets the axis), horn = full aerofoil from HORN_FRONT outboard
    em = MeshBuf()
    xb = [S.ELEV_ROOT_X, 0.21, 0.31, 0.41, 0.51, 0.70, 0.90, 1.10, 1.20, S.ELEV_HORN_X + 0.006]
    bst = [stab_station(x, side) for x in xb]
    if side < 0:
        bst = list(reversed(bst))
    s0 = lambda st: frac(st, S.ELEV_HINGE - 0.022)
    NP.cs_body(em, bst, s0)
    xh = [S.ELEV_HORN_X + 0.006, 1.31, 1.36, 1.41, 1.46, 1.50, 1.53, 1.55, 1.563, 1.571]
    hst = []
    for x in xh:
        te = interp(S.ELEV_TE_TABLE, x)
        le = max(HORN_FRONT, interp(S.STAB_LE_TABLE, x)) if x < 1.56 else interp(S.STAB_LE_TABLE, x)
        le = min(le, HORN_FRONT)
        ch = max(le - te, 0.03)
        # thickness ratio so the horn is as thick as the body at the junction (body: full-chord station)
        hst.append(Station(side * x, V((side * x, le, S.STAB_Z)), V((0, -1, 0)), V((0, 0, 1)), ch, min(0.16, STAB_T * 1.04 / max(ch, 0.3) * 0.62), m=0.0))
    if side < 0:
        hst = list(reversed(hst))
    from b25h_geom import aft_ring
    rh = [aft_ring(st, 0.0, 8)[0] for st in hst]
    loft(em, rh, 'paint', uvfunc=ring_arc_uv(rh, [st.span for st in hst]))
    sgh = 1 if hst[-1].span > hst[0].span else -1
    for r_, d in ((rh[0], -1), (rh[-1], 1)):
        section_cap(em, r_, 'paint', V((d * sgh, 0, 0)), lambda q: planar_uv(q, V((1, 0, 0))))
    nose = NP.nose_mesh2([b for b in bst if abs(b.span) <= S.ELEV_HORN_X + 0.007], 0.5, s0, axis_p0, axis, lambda st: frac(st, WALL_IN), rf=0.86) \
        if False else _elev_nose(bst, side)
    pivot = V((side * S.ELEV_ROOT_X, S.ELEV_HINGE, S.STAB_Z))
    root_st = sin_[0] if side > 0 else sin_[-1]
    return sm, em, nose, pivot, root_st


def _elev_nose(bst, side):
    """round nose concentric with the hinge axis (y ELEV_HINGE, z STAB_Z) on the elevator body's front (inner part only)."""
    mb = MeshBuf()
    rings = []
    sel = [b for b in bst if abs(b.span) <= S.ELEV_HORN_X + 0.0061]
    for st in sel:
        c = V((st.span, S.ELEV_HINGE, S.STAB_Z))
        sf = frac(st, S.ELEV_HINGE - 0.022)
        tu = st.point(frac(st, S.ELEV_HINGE), True).z - S.STAB_Z
        R = min(0.86 * tu, WALL_IN - S.ELEV_HINGE - 0.008)
        arc = [c + V((0, math.cos(math.radians(a)) * R, math.sin(math.radians(a)) * R)) for a in range(90, -91, -20)]
        top, bot = st.point(sf, True), st.point(sf, False)
        rings.append([top, V((st.span, S.ELEV_HINGE, c.z + tu * 0.92))] + arc + [V((st.span, S.ELEV_HINGE, c.z - tu * 0.92)), bot])
    loft(mb, rings, 'paint')
    sg = 1 if sel[-1].span > sel[0].span else -1
    for r, d in ((rings[0], -1), (rings[-1], 1)):
        fan_cap(mb, r, sum(r, V()) / len(r), 'paint', V((d * sg, 0, 0)))
    return mb


def tail_struts(side, fin_half):
    """two struts per side from the fuselage underside to the stabiliser underside at x 0.69 (front y -3.87, rear y -4.30),
    and two bracing wires from the stabiliser top to the fin. Returns (mesh, attach list)."""
    mb = MeshBuf(); att = []
    L = 'L' if side < 0 else 'R'
    x = S.TAIL_STRUT_X
    for k, y in enumerate((S.TAIL_STRUT_Y[0], -4.30)):
        st = stab_station(x, side)
        top = st.point(frac(st, y), False)
        if k == 0:
            zf = -0.349
            foot = ST.fus_surface_point(side, y, zf)
            fn = V((side, 0, -0.3)).normalized()
        else:
            zb = ST.fus_z(0.02, y, top=False)
            foot = V((side * 0.035, y, zb + 0.012))
            fn = V((0, 0, -1))
        cylinder(mb, foot - fn * 0.012, top + V((0, 0, 0.012)), 0.016, N=10, mat='paint', smooth=True)
        box(mb, top, (0.05, 0.05, 0.012), 'metal_dark')
        q = Matrix.Identity(3).to_quaternion() if k else V((0, 0, 1)).rotation_difference(fn)
        box(mb, foot, (0.04, 0.05, 0.012), 'metal_dark', rot=q)
        att.append((f'stab_strut_{L}', foot, ['fus_rear'])); att.append((f'stab_strut_{L}', top, [f'stab_{L}']))
    # bracing wires: stabiliser top (x 0.69, y -4.30) -> fin side (z 0.91, y -4.33)
    st = stab_station(x, side)
    a = st.point(frac(st, -4.30), True)
    b = V((side * fin_half(0.91, -4.33), -4.33, 0.91))
    cylinder(mb, a - V((0, 0, 0.004)), b - V((side * 0.004, 0, 0)), 0.0045, N=5, mat='metal_dark', smooth=True)
    box(mb, a, (0.03, 0.04, 0.008), 'metal_dark')
    att.append((f'stab_strut_{L}', a, [f'stab_{L}']))
    return mb, att


# =========================================================================================== fin + rudder
FIN_T = 0.075


def fin_station(z):
    le = interp(S.FIN_LE_TABLE, z)
    return Station(z, V((0, le, z)), V((0, -1, 0)), V((1, 0, 0)), max(le - S.FIN_HINGE, 0.03), FIN_T, m=0.0)


def fin_half_thick(z, y):
    st = fin_station(z)
    return abs(st.point(min(max(frac(st, y), 0.0), 1.0), True).x)


def fin_rudder_v140():
    """fin (LE table, hinge wall at FIN_HINGE, top FIN_TOP), rudder (chord table aft of the hinge, rounded top/bottom) and the
    rudder's mass-balance horn + aerial mast (child mesh: not in the rudder collider). Returns fin, rudder, rudder_balance."""
    from b25h_geom import surface
    fm = MeshBuf()
    zs = [0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.06, 1.12, 1.16, 1.185]
    sts = [fin_station(z) for z in zs]
    surface(fm, sts, 0.0, 0.999, cap1=V((0, 0, 1)), cap_mat='paint', n_box=9, hinge_mat='cove')
    rm = MeshBuf()
    rz = [S.RUDDER_BOTTOM_Z + 0.002] + [z for z, _ in S.RUDDER_CHORD_TABLE[1:-1]] + [S.RUDDER_TOP - 0.004]
    rs = []
    for z in rz:
        ch = max(interp(S.RUDDER_CHORD_TABLE, z) - 0.006, 0.04)
        rs.append(Station(z, V((0, S.FIN_HINGE - 0.006, z)), V((0, -1, 0)), V((1, 0, 0)), ch, 0.11 * min(1.0, 0.75 / ch) ** 0.35, m=0.0))
    surface(rm, rs, 0.0, 0.999, cap0=V((0, 0, -1)), cap1=V((0, 0, 1)), cap_mat='paint', n_box=9, hinge_mat='cove')
    bm = MeshBuf()
    # round 10 (user, after the reference: our 1.4.0 horn was a wide flat teardrop lying on the fin top with a 0.17 m spike above it, read as
    # a "spur"): rebuilt to the reference proportions (sizes only, measured on the user's reference picture, nothing traced): a thin post on
    # the rudder's leading edge at the hinge line, 0.23 m tall; a SLIM mass-balance horn forward from the post 0.06 m above the rudder top,
    # bulb at its front end; a short horizontal aerial arm forward from the post top. All on the rudder (moves with it).
    hy = S.FIN_HINGE + 0.005
    rt = S.RUDDER_TOP
    cylinder(bm, V((0, hy, rt - 0.045)), V((0, hy, rt + 0.125)), 0.008, N=10, mat='metal_dark')                  # post (to 0.18 m over the fin top)
    lathe(bm, [(0.004, 0.0), (0.013, 0.004), (0.013, 0.022), (0.004, 0.026)], V((0, hy, rt + 0.002)), V((0, 0, 1)), 'metal_dark', N=12)   # base collar
    zh = rt - 0.020                                                         # horn 3-4 cm over the fin top (reference)
    prof = [(0.004, -0.004), (0.007, 0.03), (0.008, 0.12), (0.010, 0.20), (0.015, 0.255), (0.017, 0.285), (0.014, 0.31), (0.007, 0.325), (0.002, 0.33)]
    lathe(bm, prof, V((0, hy, zh)), V((0, 1, 0)), 'paint', N=12)                                                # slim horn, bulb forward
    za = rt + 0.110
    cylinder(bm, V((0, hy, za)), V((0, hy + 0.23, za)), 0.0045, N=8, mat='metal_dark')                         # aerial arm
    N4_ball = [(0.002, -0.009), (0.007, -0.005), (0.008, 0.0), (0.007, 0.005), (0.002, 0.009)]
    lathe(bm, N4_ball, V((0, hy + 0.235, za)), V((0, 1, 0)), 'metal_dark', N=8)                               # wire insulator knob
    lathe(bm, [(0.004, 0.0), (0.011, 0.003), (0.011, 0.015), (0.004, 0.018)], V((0, hy, za - 0.009)), V((0, 0, 1)), 'metal_dark', N=10)     # arm clamp
    return fm, rm, bm, sts


# =========================================================================================== tail skid
def tail_skid():
    """skid arm (fixed, gear_tail_strut) from the fuselage bottom fitting aft-down to the shoe; the shoe (gear_tail_skid, rides on
    the gear's unsprung frame) has its bottom on the old tailwheel contact point."""
    arm, shoe = MeshBuf(), MeshBuf()
    ax = V(S.TAIL_AXLE)
    zc = ax.z - S.TAILWHEEL_R                                           # contact height (unchanged)
    yc = ax.y
    p0 = V(S.SKID_PIVOT); p0.z = ST.fus_z(0.0, p0.y, top=False) + 0.01
    # reference: one straight arm from the fuselage fitting aft-down to the shoe (no tail wheel, no fork)
    sh_top = V((0, yc - 0.02, zc + 0.040))
    tube_pts(arm, [p0, sh_top], 0.018, 'metal_dark', N=10)
    box(arm, p0 + V((0, 0, 0.005)), (0.07, 0.09, 0.024), 'metal_dark')                  # fuselage fitting
    lathe(arm, [(0.026, -0.03), (0.026, 0.03)], p0 + V((0, 0, -0.012)), V((1, 0, 0)), 'metal_dark', N=12)    # pivot boss
    # shoe: rounded steel cup under the arm end, bottom exactly on the contact point (yc, zc)
    lathe(shoe, [(0.004, -0.045), (0.030, -0.035), (0.038, 0.0), (0.030, 0.035), (0.004, 0.045)], V((0, yc - 0.01, zc + 0.038)), V((0, 1, 0)), 'metal_dark', N=14)
    lathe(shoe, [(0.022, -0.03), (0.022, 0.03)], sh_top, V((1, 0, 0)), 'metal_dark', N=10)
    return arm, shoe


# =========================================================================================== arrester hook (visible A-frame)
def hook_visual():
    """A-frame in its STOWED pose (HOOKV_STOW deg tip up), hinge axis = x through HOOKV_PIVOT. Two tubes from the hinge lugs
    (x +-0.27) converge to the shank; collars (alu) and shock-strut sleeves (black); forged claw at the end hooking down."""
    mb = MeshBuf()
    P = V(S.HOOKV_PIVOT)
    a = math.radians(S.HOOKV_STOW)
    d = V((0, -math.cos(a), math.sin(a)))
    up = V((0, math.sin(a), math.cos(a)))
    Lc = S.HOOKV_LEN
    apex = P + d * (Lc * 0.86)
    hx = S.HOOKV_HALF_SPAN
    for s in (-1, 1):
        h = P + V((s * hx, 0, 0))
        lathe(mb, [(0.026, -0.03), (0.026, 0.03)], h, V((1, 0, 0)), 'metal_dark', N=12)       # hinge boss on the axis
        e = apex + V((s * 0.035, 0, 0))
        cylinder(mb, h, e, 0.019, N=10, mat='alu', cap0=True, cap1=True)
        L_ = (e - h).length; u = (e - h).normalized()
        for f, r, l, mat in ((0.30, 0.031, 0.10, 'metal_dark'), (0.52, 0.033, 0.12, 'metal_dark'), (0.18, 0.026, 0.05, 'alu'), (0.68, 0.026, 0.05, 'alu')):
            c = h + u * (L_ * f)
            cylinder(mb, c - u * l / 2, c + u * l / 2, r, N=12, mat=mat)
    # apex yoke + shank
    box(mb, apex, (0.11, 0.06, 0.05), 'metal_dark', rot=V((0, -1, 0)).rotation_difference(d))
    sh1 = P + d * (Lc - 0.06)
    cylinder(mb, apex, sh1, 0.024, N=12, mat='metal_dark')
    # claw: hooks down then forward (catch point at Lc along the axis, ~45 mm below it)
    c_pts = [sh1, sh1 + d * 0.05 - up * 0.01, sh1 + d * 0.085 - up * 0.045, sh1 + d * 0.07 - up * 0.085, sh1 + d * 0.03 - up * 0.10]
    tube_pts(mb, c_pts, 0.020, 'metal_dark', N=10)
    return mb


def hook_belly_fittings():
    """static parts on fus_rear: two hinge brackets from the belly skin down to the hinge axis, and the stowage catch box at the
    claw (the black box of the reference, behind the yellow band)."""
    mb = MeshBuf()
    P = V(S.HOOKV_PIVOT)
    for s in (-1, 1):
        x = s * S.HOOKV_HALF_SPAN
        zs = ST.fus_z(abs(x), P.y, top=False)
        h = max(zs - P.z + 0.02, 0.03)
        box(mb, V((x + s * 0.035, P.y, P.z + h / 2 - 0.005)), (0.012, 0.07, h + 0.03), 'metal_dark')
        box(mb, V((x - s * 0.035, P.y, P.z + h / 2 - 0.005)), (0.012, 0.07, h + 0.03), 'metal_dark')
        box(mb, V((x, P.y, zs + 0.004)), (0.10, 0.09, 0.012), 'metal_dark')
    a = math.radians(S.HOOKV_STOW)
    d = V((0, -math.cos(a), math.sin(a)))
    tipc = P + d * (S.HOOKV_LEN - 0.0)
    zs = ST.fus_z(0.0, tipc.y, top=False)
    zb = tipc.z - 0.02
    box(mb, V((0, tipc.y + 0.03, (zs + 0.02 + zb) / 2)), (0.13, 0.16, zs + 0.02 - zb), 'metal_dark')
    return mb


# =========================================================================================== radiator + oil cooler
def radiator_v140():
    """radiator bath (reference: y -0.07 .. 0.91, x +-0.344, bottom -0.98): vertical front face at y 0.905 with 10 shutter slats
    over x +-0.248 and two round openings each side; rounded bottom corners; rear fairing sloping up to the belly at y 0.02."""
    mb = MeshBuf()
    top = -0.50
    yf, yb = 0.905, 0.02
    hw, zb, rc = 0.344, -0.978, 0.06
    def sec(y, hw_, zb_):
        pts = [V((-hw_, y, top))]
        for k in range(5):
            a = math.radians(180 + 90 * k / 4)
            pts.append(V((-hw_ + rc + rc * math.cos(a), y, zb_ + rc + rc * math.sin(a))))
        for k in range(5):
            a = math.radians(270 + 90 * k / 4)
            pts.append(V((hw_ - rc + rc * math.cos(a), y, zb_ + rc + rc * math.sin(a))))
        pts.append(V((hw_, y, top)))
        return pts
    ys = [yf, 0.80, 0.55, 0.30, 0.16, 0.08, yb]
    prof = {yf: (hw, zb), 0.80: (hw, zb), 0.55: (hw, zb), 0.30: (hw - 0.01, zb + 0.01), 0.16: (hw - 0.03, -0.86), 0.08: (hw - 0.05, -0.74), yb: (hw - 0.08, -0.62)}
    rings = [sec(y, *prof[y]) for y in ys]
    loft(mb, rings, 'paint', closed=False, uvfunc=lambda ci, cj, j: (cj * 0.12, ys[ci]))
    for ra, rb_ in zip(rings, rings[1:]):
        oriented_quad(mb, [ra[0], ra[-1], rb_[-1], rb_[0]], 'radiator', V((0, 0, 1)))
    rr = rings[-1]
    fan_cap(mb, rr, sum(rr, V()) / len(rr), 'paint', V((0, -1, 0)), uvfunc=lambda q: (q.x, q.z))
    # front face: frame (paint) around the matrix, matrix recessed 25 mm (radiator), slats, round openings
    rf = rings[0]
    zt_ = -0.585
    fr = MeshBuf()
    inner = [V((-0.250, yf, zt_)), V((0.250, yf, zt_)), V((0.250, yf, zb + 0.02)), V((-0.250, yf, zb + 0.02))]
    # side panels (with the round openings) and bottom lip as paint quads on the front plane
    for s in (-1, 1):
        q = [V((s * 0.250, yf, zt_)), V((s * hw, yf, zt_)), V((s * hw, yf, zb + rc)), V((s * 0.250, yf, zb + 0.02))]
        oriented_quad(mb, q, 'paint', V((0, 1, 0)), uv=[(q_.x, q_.z) for q_ in q])
        for zc in (-0.817, -0.677):
            c = V((s * 0.296, yf + 0.001, zc))
            ring = circle_pts(c - V((0, 0.03, 0)), V((0, 1, 0)), 0.036, 16)
            fan_cap(mb, ring, c - V((0, 0.03, 0)), 'radiator', V((0, 1, 0)))                    # dark round opening, 30 mm deep
            rings_ = [circle_pts(c + V((0, 0.006, 0)), V((0, 1, 0)), 0.042, 16), circle_pts(c, V((0, 1, 0)), 0.036, 16), ring]
            loft(mb, rings_, 'metal_dark', smooth=True)
    oriented_quad(mb, [V((-0.25, yf, zb + 0.02)), V((0.25, yf, zb + 0.02)), V((hw - rc, yf, zb)), V((-hw + rc, yf, zb))], 'paint', V((0, 1, 0)))
    oriented_quad(mb, [V((-hw, yf, top)), V((hw, yf, top)), V((hw, yf, zt_)), V((-hw, yf, zt_))], 'paint', V((0, 1, 0)))     # top band (inside the cowl)
    # close the corner gaps between the side panels and the rounded section edge
    for s in (-1, 1):
        cps = [p for p in rf if p.z < zb + rc + 1e-6 and s * p.x > 0.24]
        cps.sort(key=lambda p: s * p.x)
        for a, b in zip(cps, cps[1:]):
            oriented_quad(mb, [a, b, V((s * 0.25, yf, zb + 0.02))], 'paint', V((0, 1, 0)))
    # recessed matrix + reveal walls
    rec = 0.025
    oriented_quad(mb, [p - V((0, rec, 0)) for p in inner], 'radiator', V((0, 1, 0)))
    for a, b in zip(inner, inner[1:] + inner[:1]):
        oriented_quad(mb, [a, b, b - V((0, rec, 0)), a - V((0, rec, 0))], 'metal_dark', V((0, yf, (zt_ + zb) / 2)) - (a + b) / 2)
    # 10 vertical shutter slats, turned 30 deg
    for k in range(10):
        x = -0.225 + k * 0.05
        q = Matrix.Rotation(math.radians(30), 3, 'Z').to_quaternion()
        box(mb, V((x, yf - 0.012, (zt_ + zb + 0.02) / 2)), (0.048, 0.004, (zt_ - zb - 0.03)), 'paint', rot=q)          # painted shutter slats (reference)
    return mb


def oil_cooler():
    """finned oil cooler under the nose (reference: centreline, y 1.525 .. 1.924, 8 horizontal fins z -0.609 .. -0.719, two pipes)."""
    mb = MeshBuf()
    for k in range(8):
        z = -0.611 - k * 0.0155
        box(mb, V((0, 1.725, z)), (0.122, 0.40, 0.003), 'alu')
    for y in (1.58, 1.87):
        cylinder(mb, V((0, y, -0.56)), V((0, y, -0.79)), 0.017, N=10, mat='alu')
        lathe(mb, [(0.024, 0.0), (0.024, 0.02)], V((0, y, -0.80)), V((0, 0, 1)), 'metal_dark', N=10)
    box(mb, V((0, 1.725, -0.590)), (0.07, 0.42, 0.04), 'metal_dark')          # mounting rail to the cowling
    return mb


# =========================================================================================== spinner + blades
def spinner_v140():
    mb = MeshBuf()
    y0 = 2.385
    # back plate fills the cowl ring, short parallel band, ring joint (groove) 75 mm aft of the back, then a long straight cone
    # reference: back plate ~0.70 of the cowl ring, short parallel band, ring joint, long slender cone to the starter dog
    prof = [(0.020, 0.0), (0.245, 0.0), (0.245, 0.035), (0.240, 0.055), (0.232, 0.060), (0.232, 0.066), (0.238, 0.070), (0.226, 0.10),
            (0.200, 0.15), (0.170, 0.20), (0.138, 0.25), (0.105, 0.30), (0.074, 0.345), (0.050, 0.38), (0.036, 0.40)]
    lathe(mb, prof, V((0, y0, 0)), V((0, 1, 0)), 'spinner', N=32, cap0=True, cap1=True, ref=V((0, 0, 1)))
    # Hucks starter dog: short shaft + cross bar at the tip
    yt = y0 + 0.40
    lathe(mb, [(0.026, 0.0), (0.026, 0.045), (0.022, 0.05)], V((0, yt, 0)), V((0, 1, 0)), 'metal_dark', N=14)
    box(mb, V((0, yt + 0.062, 0)), (0.075, 0.026, 0.018), 'metal_dark')
    return mb


BLADE_CHORD = [(0.10, 0.12), (0.25, 0.19), (0.30, 0.21), (0.50, 0.23), (0.80, 0.242), (1.10, 0.235), (1.30, 0.225), (1.45, 0.20),
               (1.55, 0.16), (1.61, 0.10), (1.64, 0.05)]


# =========================================================================================== ring-and-bead sight
def ring_bead():
    """on fus_engine: ring (r 50 mm, 4 cross wires) on a post from the decking just ahead of the windscreen; bead post forward."""
    mb = MeshBuf()
    c = V(S.RING_SIGHT_C); r = S.RING_SIGHT_R
    ring = circle_pts(c, V((0, 1, 0)), r, 24)
    for a, b in zip(ring, ring[1:] + ring[:1]):
        cylinder(mb, a, b, 0.0028, N=5, mat='metal_dark', cap0=False, cap1=False)
    inner = circle_pts(c, V((0, 1, 0)), r * 0.35, 16)
    for a, b in zip(inner, inner[1:] + inner[:1]):
        cylinder(mb, a, b, 0.0018, N=4, mat='metal_dark', cap0=False, cap1=False)
    for k in (0, 6, 12, 18):
        cylinder(mb, ring[k], c + (ring[k] - c) * 0.35, 0.0014, N=4, mat='metal_dark')
    zd = ST.fus_z(abs(c.x), c.y, top=True)
    cylinder(mb, V((c.x, c.y, zd - 0.006)), ring[12], 0.005, N=6, mat='metal_dark')
    box(mb, V((c.x, c.y, zd + 0.002)), (0.03, 0.03, 0.008), 'metal_dark')
    b = V(S.BEAD_POST)
    zb = ST.fus_z(abs(b.x), b.y, top=True)
    cylinder(mb, V((b.x, b.y, zb - 0.006)), V((b.x, b.y, b.z - 0.006)), 0.006, 0.0025, N=8, mat='metal_dark')
    sphere(mb, b, 0.006, 'metal_dark', n=8)
    box(mb, V((b.x, b.y, zb + 0.002)), (0.03, 0.03, 0.008), 'metal_dark')
    return mb


# =========================================================================================== wing-tip lamps
def tip_lamp(side, p):
    """small period navigation lamp on the wing tip: chrome housing + coloured glass bulb (red left, green right); no light."""
    mb = MeshBuf()
    p = V(p)
    ax = V((side, 0, 0))
    lathe(mb, [(0.004, -0.045), (0.016, -0.04), (0.019, -0.01), (0.017, 0.0)], p, ax, 'alu', N=14)
    sphere(mb, p + ax * 0.010, 0.0165, 'navred' if side < 0 else 'navgreen', n=12)
    return mb
