"""GA-25X visual pass (2026-10-31): the parts that make the airframe read as a 2080s gunship, not a repainted B-25.

Same conventions as ga25x_parts / the B-25H builders (MeshBuf in WORLD coordinates, Blender: nose +Y, up +Z, right
wing +X, metres; material slots by name; `paint` faces go to the livery atlas). Object names, parents and pivots are
the ones GA25XBuild.cs already uses (contract-compatible); new objects: pylon_root/mid_L/R + hp_root/mid_L/R only.
Only the material slots the generator already knows are used (paint, interior, structure, metal_dark, rubber, prop,
cockpit, gauges, screen, glass, sensor).

  build_canopy()            low-frame bubble canopy over the B-25H cockpit cut-out (windscreen + roof hatch + quarter glass)
  build_nacelle(side)       the B-25H nacelle builder minus the radial-engine mount tubes (slim NAC_TABLE in ga25x_spec)
  build_turboprop(side)     ogive cowl, chin intake, flattened IR-suppressed exhaust outlets (exhaust_L/R)
  build_prop6(side)         6-blade scimitar composite props with nickel erosion sheaths, long pointed spinner
  build_laser_turret()      faceted low-profile beam director (same pivots / muzzle as 0.1.0)
  build_chin_turret()       EO/IR gimbal ball with a flat window face (EO, IR, laser)
  build_package_fairing()   chined package fairings, one 20 mm each
  add_sensor_panels()       flush conformal sensor panels + flush flare dispenser grilles (old waist windows)
  tailcone()                sensor tail cone: MWS windows, IR-jammer ball turret, flare dispensers
  build_pylons()            4 pylons per wing (root, inner, mid, outer)
  modern_cockpit(parts)     modern throttle grips, ISIS standby displays in place of the 1940s dials
"""
import math
from mathutils import Vector, Quaternion
import b25h_spec as S
import ga25x_spec as G
from b25h_geom import (V, MeshBuf, loft, fan_cap, annulus, oriented_quad, cylinder, tube, box, circle_pts, arc_lengths,
                       ring_arc_uv, superellipse_ring, interp_table, frame_from_axes)

UP = V((0, 0, 1))
FWD = V((0, 1, 0))


def _P():
    import b25h_parts as P
    return P


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def prism(mb, poly, axis_pts, mat, scale=None, smooth=False, caps=True):
    """flat-shaded prism: `poly` = list of (u, v) in the plane spanned by (U, Vv) at each axis point; axis_pts = list of
    (origin, U, Vv) frames; scale = optional per-station scale. Returns the rings."""
    rings = []
    for k, (o, U, Vv) in enumerate(axis_pts):
        s = scale[k] if scale else 1.0
        rings.append([o + U * (u * s) + Vv * (v * s) for u, v in poly])
    loft(mb, rings, mat, smooth=smooth)
    if caps:
        for r, d in ((rings[0], axis_pts[0][0] - axis_pts[1][0]), (rings[-1], axis_pts[-1][0] - axis_pts[-2][0])):
            fan_cap(mb, r, sum(r, V()) / len(r), mat, d)
    return rings


def disc(mb, c, n, r, mat, N=20, ref=None):
    ring = circle_pts(c, n, r, N, ref=ref)
    fan_cap(mb, ring, c, mat, n)
    return ring


def bezel_window(mb, c, n, r, win='sensor', rim='metal_dark', rim_w=0.012, N=20, proud=0.004, ref=None):
    """round sensor window with a thin raised bezel, facing n."""
    n = V(n).normalized()
    c = V(c)
    o = circle_pts(c + n * proud, n, r + rim_w, N, ref=ref)
    i = circle_pts(c + n * proud, n, r, N, ref=ref)
    b = circle_pts(c - n * 0.004, n, r + rim_w, N, ref=ref)
    loft(mb, [b, o], rim)
    annulus(mb, o, i, rim, n)
    fan_cap(mb, i, c + n * (proud - 0.002), win, n)


# ============================================================================================ canopy
CANOPY_BULGE = 0.075        # m, bubble height over the B-25H cockpit section (0 at the cut-out edges)
BOW_Y = 3.79                # windscreen arch (just ahead of the roof hatch)


def build_canopy():
    """modern low-frame canopy over the B-25H cockpit cut-out (S.CANOPY_Y x V3.CANOPY_J): the glazing is lifted into
    a smooth bubble that meets the fuselage cut exactly at its edges; frames = windscreen base, one windscreen arch,
    aft edge and the two sills only. 0.3.0 (ejection seats): the aft section (canopy aft edge .. windscreen arch) is two
    jettison panels canopy_jettison_L/R (one over each seat, split on the centreline, hinged on the outboard sill,
    generator: Canopy per panel); canopy_glass is the fixed windscreen. hatch_cockpit_top no longer exists."""
    import b25h_v3 as V3
    P = _P()
    J0, J1 = V3.CANOPY_J
    JH0, JH1 = V3.HATCH_TOP_J
    Y0, Y1 = S.CANOPY_Y
    yh0, yh1 = S.HATCH_TOP_Y

    def bump(y, j):
        u = (y - Y0) / (Y1 - Y0)
        v = (j - J0) / (J1 - J0)
        if u <= 0 or u >= 1 or v <= 0 or v >= 1:
            return 0.0
        return CANOPY_BULGE * math.sin(math.pi * u) ** 0.65 * math.sin(math.pi * v) ** 0.75

    def pt(y, j):
        return V3.rr_point(y, j) + V3.rr_normal(y, j) * bump(y, j)

    def nrm(y, j):
        e = 1e-3
        a = pt(y, j + e) - pt(y, j - e)
        b = pt(y + e, j) - pt(y - e, j)
        n = a.cross(b).normalized()
        if n.dot(pt(y, j) - V((0, y, 0.25))) < 0:
            n = -n
        return n

    ys = V3.canopy_ys()
    js = [J0 + 0.25 * k for k in range(int((J1 - J0) / 0.25) + 1)]
    JC = (J0 + J1) / 2                                   # centreline (x = 0)
    yb = min(ys, key=lambda y: abs(y - BOW_Y))          # windscreen arch = boundary fixed windscreen / jettison panels
    th = 0.008
    gm = MeshBuf()
    pm = {'L': MeshBuf(), 'R': MeshBuf()}

    def region(y, j):
        if y > yb:
            return 'fixed'
        return 'L' if j > JC else 'R'                   # larger ring index = x < 0 (left)

    for mb, sel in ((gm, 'fixed'), (pm['L'], 'L'), (pm['R'], 'R')):
        go = [[mb.v(pt(y, j)) for j in js] for y in ys]
        gi = [[mb.v(pt(y, j) - nrm(y, j) * th) for j in js] for y in ys]

        def keep(i, j, sel=sel):
            return region((ys[i] + ys[i + 1]) / 2, (js[j] + js[j + 1]) / 2) == sel
        out = lambda c: c - V((0, c.y, 0.25))
        V3.grid_faces(mb, go, 'glass', out, keep)
        V3.grid_faces(mb, gi, 'glass', lambda c: -out(c), keep)
    glass = P.Part('canopy_glass', 'fus_cockpit', (0, 3.6, 1.2), gm,
                   info=dict(note='0.3.0: fixed windscreen only (gold-film coating: Unity material); the aft section is the two '
                                  'jettison panels canopy_jettison_L/R'))
    fm = MeshBuf()

    def bar_y(y, j0, j1, w, ho, hi, mb=fm):
        n = max(2, int(abs(j1 - j0) / 0.25))
        jj = [j0 + (j1 - j0) * k / n for k in range(n + 1)]
        V3.sweep_rect(mb, [pt(y, j) for j in jj], [nrm(y, j) for j in jj], w, ho, hi)

    def bar_j(j, y0, y1, w, ho, hi, mb=fm):
        yy = [y0 + (y1 - y0) * k / 28 for k in range(29)]
        V3.sweep_rect(mb, [pt(y, j) for y in yy], [nrm(y, j) for y in yy], w, ho, hi)
    bar_y(Y1 - 0.012, J0, J1, 0.040, 0.010, 0.012)            # windscreen base (on the nose cut)
    bar_y(yb, J0 - 0.15, J1 + 0.15, 0.050, 0.016, 0.016)      # windscreen arch (covers the panel front seam)
    bar_y(Y0 + 0.010, J0 - 0.15, J1 + 0.15, 0.030, 0.006, 0.012)   # aft canopy rail on the fuselage cut
    for j in (J0 + 0.06, J1 - 0.06):                          # sills (fixed rails, full length)
        bar_j(j, Y0, Y1, 0.040, 0.012, 0.012)
    frame = P.Part('canopy_frame', 'fus_cockpit', (0, 3.6, 1.2), fm,
                   info=dict(note='windscreen base + arch, aft rail and sills (fixed); panel frames are on canopy_jettison_L/R'))
    out = [glass, frame]
    # jettison panels: own frame on their perimeter (aft edge, centre seam, front edge, outboard edge), hinge on the sill
    ym = (Y0 + yb) / 2
    for L, jout, jin, sgn in (('L', J1, JC, -1.0), ('R', J0, JC, 1.0)):
        mb = pm[L]
        jo = jout + (0.30 if jout < JC else -0.30)            # just inboard of the fixed sill rail
        bar_y(Y0 + 0.030, jo, jin, 0.028, 0.012, 0.010, mb)   # aft edge
        bar_y(yb - 0.030, jo, jin, 0.024, 0.010, 0.010, mb)   # front edge (under the arch)
        bar_j(jin + (0.10 if L == 'L' else -0.10), Y0 + 0.02, yb - 0.02, 0.022, 0.012, 0.010, mb)   # centre seam
        bar_j(jo, Y0 + 0.02, yb - 0.02, 0.020, 0.008, 0.010, mb)                                       # outboard edge
        hp = pt(ym, jout)
        axis = V((0, 1, 0))
        fr = frame_from_axes(axis, V((0, 0, 1)))
        open_deg = 60.0 * (-1 if L == 'L' else 1)             # inboard edge swings up and outboard (Blender, about +Y)
        out.append(P.Part(f'canopy_jettison_{L}_hinge', 'fus_cockpit', hp, None, fr, info=dict(kind='hatch_hinge', hinge_axis=tuple(axis))))
        out.append(P.Part(f'canopy_jettison_{L}', f'canopy_jettison_{L}_hinge', hp, mb, fr,
                          info=dict(kind='canopy', open_deg_blender=open_deg, crew='pilot' if L == 'L' else 'wso',
                                    note='jettisonable canopy panel over the ' + ('pilot' if L == 'L' else 'weapons officer') +
                                         ' seat (glass + frame); hinge on the outboard sill (ground opening); '
                                         'Canopy.ejectionTransform on ejection')))
    return out


# ============================================================================================ nacelle
def build_nacelle(side):
    """B-25H build_nacelle (blender/v2/b25h_parts.py) with the GA-25X slim NAC_TABLE, without the radial-engine mount
    tubes (they would poke through the slimmer firewall ring). Gear well, doors and holes exactly as the B-25H."""
    P = _P()
    from b25h_parts import Part, shell, open_profile_box, door_from_holes, open_pose, station_list, nac_ring, nac_params, NAC_N, nac_well_clamp
    L = 'L' if side < 0 else 'R'
    cx = side * S.NAC_X
    req = [r[0] for r in S.NAC_TABLE] + list(S.NAC_WELL_Y)
    ys = station_list(S.FIREWALL_Y, S.NAC_TABLE[-1][0], req, 0.3)
    outer = [nac_ring(y, cx) for y in ys]
    inner = [nac_ring(y, cx, S.SKIN_T) for y in ys]
    arcs = [arc_lengths(r) for r in outer]

    def uvf(ci, cj, j):
        acc, Pm = arcs[ci]
        if j < NAC_N // 2:
            v = acc[cj]
        else:
            v = -(Pm - acc[cj]) if cj != 0 else 0.0
        return (ys[ci], v)

    def cls(i, j, c):
        ym = (ys[i] + ys[i + 1]) / 2
        hw, zb, zt, n = nac_params(ym)
        cz = (zb + zt) / 2
        if S.NAC_WELL_Y[0] < ym < S.NAC_WELL_Y[1] and abs(c.x - cx) < S.NAC_WELL_HALF_X and c.z < cz - 0.35:
            return 'wellA' if abs(c.x) < S.NAC_X else 'wellB'
        return 'skin'
    mb = MeshBuf()
    tip = V((cx, S.NAC_TIP[0], S.NAC_TIP[1]))
    holes, kinds = shell(mb, outer, inner, ys, cls, uvf, 'disc', ('fan_paint', tip))
    y0, y1 = S.NAC_WELL_Y
    wx = S.NAC_WELL_HALF_X - 0.01
    zl = -0.60
    prof = [(y1 - 0.01, zl), (y1 - 0.01, S.NAC_WELL_TOP_FWD), (S.NAC_WELL_STEP_Y, S.NAC_WELL_TOP_FWD),
            (S.NAC_WELL_STEP_Y, S.NAC_WELL_TOP_AFT), (-1.20, 0.555), (-1.60, 0.48), (-2.00, 0.36),
            (y0 + 0.01, 0.28), (y0 + 0.01, zl)]
    open_profile_box(mb, prof, cx - wx, cx + wx, 'interior', clamp=nac_well_clamp(cx))
    part = Part(f'nacelle_{L}', f'wing_inner_{L}', (cx, S.FIREWALL_Y, 0.0), mb,
                info=dict(note='slim turboprop nacelle; firewall cap at y=1.62; main gear well open at bottom'))
    doors = []
    for tag, nm in (('wellA', 'a'), ('wellB', 'b')):
        qs = holes.get(tag, [])
        if not qs:
            continue
        outward = -1 if tag == 'wellA' else 1
        pick = (lambda p, s=outward: s * (abs(p.x) - S.NAC_X))
        d = door_from_holes(f'gear_door_main_{L}_{nm}', f'nacelle_{L}', qs, pick, 0.0, 'main gear door; hinge on well edge')
        d.pose = open_pose(d, qs, 95.0)
        d.info['open_deg'] = round(math.degrees(d.pose.angle) * (1 if d.pose.axis.dot(V(d.info['hinge_axis'])) > 0 else -1), 1)
        doors.append(d)
    return part, doors


def nac_pt(y, theta, cx):
    """point on the nacelle superellipse surface at station y, angle theta (0 = top, +pi/2 = +X side)."""
    P = _P()
    hw, zb, zt, n = P.nac_params(y)
    cz = (zb + zt) / 2
    sx, cz_ = math.sin(theta), math.cos(theta)
    b = (zt - cz) if cz_ >= 0 else (cz - zb)
    # solve |r sx / hw|^n + |r cz_ / b|^n = 1
    r = (abs(sx / hw) ** n + abs(cz_ / b) ** n) ** (-1.0 / n)
    return V((cx + r * sx, y, cz + r * cz_))


def nac_normal(y, theta, cx):
    e = 1e-3
    a = nac_pt(y, theta + e, cx) - nac_pt(y, theta - e, cx)
    b = nac_pt(y + e, theta, cx) - nac_pt(y - e, theta, cx)
    n = a.cross(b).normalized()
    p = nac_pt(y, theta, cx)
    P = _P()
    hw, zb, zt, _ = P.nac_params(y)
    if n.dot(p - V((cx, y, (zb + zt) / 2))) < 0:
        n = -n
    return n


# ============================================================================================ turboprop
# 0.3.0: the spinner meets the cowl. The spinner skirt now starts 4 mm ahead of the cowl lip plane with a radius
# 4 mm under the lip (0.2.0: 0.330 at y 2.660 against a 0.352 lip at 2.635 = a 22 mm step plus a visible dark ring).
SPIN_Y0, SPIN_R0 = 2.639, 0.348         # spinner skirt (on the prop hub; prop pivot PROP_Y 2.98 unchanged)
COWL_LIP_Y, COWL_LIP_R = 2.635, 0.352   # cowl front ring


def build_turboprop(side):
    """ogive cowl from the slim firewall ring into the spinner line, chin intake with a boundary-layer gap, and two
    flattened IR-suppressed exhaust outlets on the upper shoulders (exit ahead of the wing leading edge, the plume is
    shielded from below by the wing)."""
    P = _P()
    L = 'L' if side < 0 else 'R'
    cx = side * S.NAC_X
    mb = MeshBuf()
    N = P.NAC_N
    hw0, zb0, zt0, n0 = P.nac_params(S.FIREWALL_Y)
    cz0 = (zb0 + zt0) / 2
    base = superellipse_ring(cx, 0, cz0, hw0 + 0.003, (zt0 - cz0) + 0.003, (cz0 - zb0) + 0.003, n=n0, N=N)
    ts = [0.0, 0.12, 0.25, 0.38, 0.50, 0.62, 0.73, 0.83, 0.92, 1.0]
    rings, sp = [], []
    for t in ts:
        y = S.FIREWALL_Y - 0.02 + (COWL_LIP_Y - S.FIREWALL_Y + 0.02) * t
        f = t ** 1.12                                   # near-straight taper continuing the nacelle slope into the spinner
        ring = []
        for j, p in enumerate(base):
            a = 2 * math.pi * j / N
            circ = V((cx + COWL_LIP_R * math.sin(a), y, COWL_LIP_R * math.cos(a)))
            ring.append(V((p.x, y, p.z)).lerp(circ, f))
        rings.append(ring)
        sp.append(y)
    loft(mb, rings, 'paint', uvfunc=ring_arc_uv(rings, sp))
    lip_in = circle_pts(V((cx, COWL_LIP_Y - 0.012, 0)), FWD, SPIN_R0 - 0.010, N)
    annulus(mb, rings[-1], lip_in, 'metal_dark', FWD)                       # recessed lip face, hidden behind the skirt
    fan_cap(mb, lip_in, V((cx, COWL_LIP_Y - 0.012, 0)), 'metal_dark', FWD)  # closed cowl front (no see-through ring)
    # ---- chin intake: D-section scoop under the cowl, lip 3 cm below the cowl skin (boundary-layer gap + diverter)
    st = [(2.47, 0.165, -0.515), (2.38, 0.172, -0.528), (2.15, 0.172, -0.540), (1.90, 0.160, -0.548),
          (1.65, 0.140, -0.552), (1.40, 0.110, -0.556), (1.15, 0.070, -0.600)]
    ztop = -0.22

    def dsec(y, hw, zb, inset=0.0):
        hw, zb = hw - inset, zb + inset
        pts = [V((cx - hw, y, ztop))]
        for k in range(7):
            a = math.pi + math.pi * k / 6
            pts.append(V((cx + hw * math.cos(a), y, zb + 0.07 + 0.07 * math.sin(a))))
        pts.append(V((cx + hw, y, ztop)))
        return pts
    outer_r = [dsec(y, hw, zb) for y, hw, zb in st]
    loft(mb, outer_r, 'paint', closed=False, uvfunc=ring_arc_uv(outer_r, [s[0] for s in st]))
    lip_r = dsec(st[0][0], st[0][1], st[0][2], 0.022)
    lip_r = [p + V((0, 0.004, 0)) for p in lip_r]
    loft(mb, [outer_r[0], lip_r], 'metal_dark', closed=False)
    duct = [lip_r, [p + V((0, -0.32, 0.02)) for p in lip_r]]
    loft(mb, duct, 'metal_dark', closed=False, outward=False)
    back = duct[-1]
    fan_cap(mb, back, sum(back, V()) / len(back), 'metal_dark', FWD)
    # splitter (boundary-layer diverter) between the cowl skin and the intake top
    box(mb, (cx, 2.40, -0.36), (0.012, 0.16, 0.10), 'metal_dark')
    # cowl access panel latches (small, flush) on both sides
    for s in (-1, 1):
        for yy in (1.95, 2.25):
            p = nac_pt(1.62, s * math.pi / 2, cx)
            r = (p.x - cx)
            box(mb, (cx + s * (r * 0.92 - 0.01), yy, -0.12), (0.006, 0.05, 0.02), 'metal_dark')
    # ---- exhaust coolers: flattened outlets on the upper shoulders, exit facing aft/up just ahead of the wing LE
    ex = MeshBuf()
    for s in (-1, 1):
        stx = [(2.05, 0.000, 0.040, 0.70), (1.85, 0.030, 0.070, 0.72), (1.62, 0.055, 0.092, 0.74),
               (1.42, 0.068, 0.100, 0.76), (1.28, 0.072, 0.100, 0.78)]
        rings_e = []
        for y, h, wth, th in stx:
            th = s * th
            c = nac_pt(y, th, cx)
            n = nac_normal(y, th, cx)
            t = n.cross(FWD).normalized()               # along the surface, around the ring
            q = []
            for u, hh in ((-1.0, -0.004), (-0.9, 0.55), (-0.55, 1.0), (0.55, 1.0), (0.9, 0.55), (1.0, -0.004)):
                q.append(c + t * (u * wth) + n * (hh * h if hh > 0 else hh))
            rings_e.append(q)
        loft(ex, rings_e, 'paint', closed=False, uvfunc=ring_arc_uv(rings_e, [r[0] for r in stx]))
        last = rings_e[-1]
        cen = sum(last, V()) / len(last)
        inset = [cen + (p - cen) * 0.82 for p in last]
        loft(ex, [last, inset], 'metal_dark', closed=False)
        back = [p + V((0, 0.10, 0)) for p in inset]
        loft(ex, [inset, back], 'metal_dark', closed=False, outward=False)
        fan_cap(ex, back, sum(back, V()) / len(back), 'sensor', V((0, -1, 0)))
        # mixing vanes across the outlet
        for k in (-0.4, 0.0, 0.4):
            a, b = inset[0].lerp(inset[-1], 0.5 + k * 0.5), inset[2].lerp(inset[3], 0.5 + k * 0.5)
            m = (a + b) / 2
            d = (b - a)
            box(ex, m + V((0, 0.03, 0)), (0.006 + abs(d.x), 0.06, 0.006 + abs(d.z)), 'structure')
    eng = P.Part(f'engine_{L}', f'nacelle_{L}', (cx, S.FIREWALL_Y, 0.0), mb,
                 info=dict(note='hybrid-electric turboprop: 2,400 kW turbine + 900 kW motor-generator; ogive cowl, chin intake'))
    exh = P.Part(f'exhaust_{L}', f'engine_{L}', (cx, 1.70, 0.25), ex,
                 info=dict(note='flattened IR-suppressed exhaust outlets (ambient-air mixing, exits aft/up over the wing): IR source'))
    return eng, exh


# ============================================================================================ 6-blade scimitar prop
def blade_mesh6(R, r0=0.30):
    """composite scimitar blade along +Z (local), rotation axis +Y, blade1 LE toward +X. Strong aft sweep of the outer
    third, thin section, nickel erosion sheath (structure) as a narrow band near the tip (subtle tip stripe)."""
    mb = MeshBuf()
    rs = [r0, 0.40, 0.55, 0.75, 0.98, 1.20, 1.40, 1.56, 1.68, 1.76, 1.82, 1.87, 1.91, R - 0.004]
    rings = []
    for r in rs:
        f = (r - r0) / (R - r0)
        chord = interp_table([(0.0, (0.15,)), (0.12, (0.22,)), (0.40, (0.27,)), (0.65, (0.25,)), (0.85, (0.18,)),
                              (0.95, (0.11,)), (1.0, (0.05,))], f)[0]
        tc = interp_table([(0.0, (0.32,)), (0.18, (0.11,)), (0.6, (0.055,)), (1.0, (0.04,))], f)[0]
        beta = math.radians(interp_table([(0.0, (60,)), (0.3, (45,)), (0.7, (28,)), (1.0, (19,))], f)[0])
        sweep = 0.05 * f - 0.36 * f ** 2.6              # slight forward lean mid-span, strong aft sweep at the tip
        tdir = V((math.cos(beta), math.sin(beta), 0))
        ndir = V((-math.sin(beta), math.cos(beta), 0))
        pts = []
        n = 12
        for k in range(n):
            a = 2 * math.pi * k / n
            x = 0.5 * math.cos(a)
            yv = 0.5 * tc * math.sin(a) * (1.0 + 0.35 * math.cos(a))
            pts.append(V((sweep, 0, r)) + tdir * (x * chord) + ndir * (yv * chord))
        rings.append(pts)

    def fm(i, j):
        r = (rs[i] + rs[i + 1]) / 2
        return 'structure' if 1.80 <= r <= 1.86 else 'prop'
    loft(mb, rings, 'prop', face_mat=fm)
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / len(rings[-1]) + V((0, 0, 0.004)), 'prop', V((0, 0, 1)))
    fan_cap(mb, rings[0], sum(rings[0], V()) / len(rings[0]), 'prop', V((0, 0, -1)))
    return mb


def build_prop6(side):
    P = _P()
    L = 'L' if side < 0 else 'R'
    cx = side * S.NAC_X
    hub_c = V((cx, S.PROP_Y, 0.0))
    hm = MeshBuf()
    prof = [(SPIN_Y0, SPIN_R0), (2.700, 0.347), (2.80, 0.338), (2.96, 0.322), (3.10, 0.300), (3.22, 0.262), (3.33, 0.210), (3.42, 0.150),
            (3.50, 0.088), (3.56, 0.036), (3.58, 0.010)]
    rings = [circle_pts(V((cx, y, 0)), FWD, r, 36) for y, r in prof]
    loft(hm, rings, 'paint', uvfunc=ring_arc_uv(rings, [y for y, _ in prof]))
    fan_cap(hm, rings[-1], V((cx, 3.585, 0)), 'paint', FWD, smooth=True)
    fan_cap(hm, rings[0], V((cx, SPIN_Y0, 0)), 'metal_dark', V((0, -1, 0)))
    for k in range(6):            # blade root cuffs (composite fairings)
        a = 2 * math.pi * k / 6
        d = V((math.sin(a), 0, math.cos(a)))
        cylinder(hm, hub_c + d * 0.25, hub_c + d * 0.36, 0.068, 0.05, N=14, mat='prop')
    hub = P.Part(f'prop_hub_{L}', f'engine_{L}', hub_c, hm,
                 info=dict(spin_axis_local='+Y (Blender) = +Z (Unity) forward', blades=6,
                           note='6-blade composite scimitar, reverse-pitch capable (game: ConstantSpeedProp, see docs/ga25x_design.md)'))
    out = [hub]
    bm = blade_mesh6(S.PROP_R)
    for k in range(6):
        q = Quaternion(FWD, 2 * math.pi * k / 6)
        mb = MeshBuf()
        for p in bm.verts:
            mb.verts.append(hub_c + q @ p)
        mb.faces = [dict(f) for f in bm.faces]
        out.append(P.Part(f'prop_{L}_blade{k + 1}', f'prop_hub_{L}', hub_c, mb, frame=q,
                          info=dict(pitch_axis_local='+Z (Blender) = +Y (Unity), radial')))
    return out


# ============================================================================================ chin EO/IR ball
def build_chin_turret():
    P = _P()
    y = G.CHIN_TURRET[1]
    hw, zb, zt, rt, rb = P.fus_params(y)
    c = V((0, y, zb - 0.10))
    mb = MeshBuf()
    # streamlined neck fairing + yoke ring
    cylinder(mb, V((0, c.y, zb + 0.08)), V((0, c.y, c.z + 0.10)), 0.15, 0.135, N=28, mat='paint')
    cylinder(mb, V((0, c.y, c.z + 0.105)), V((0, c.y, c.z + 0.085)), 0.150, 0.150, N=28, mat='metal_dark')
    # gimbal ball
    rings = []
    R = 0.17
    for i in range(1, 14):
        phi = -math.pi / 2 + math.pi * i / 14
        rings.append(circle_pts(c + UP * (R * math.sin(phi)), UP, R * math.cos(phi), 32, ref=V((1, 0, 0))))
    loft(mb, rings, 'paint')
    fan_cap(mb, rings[0], c - UP * R, 'paint', -UP, smooth=True)
    fan_cap(mb, rings[-1], c + UP * R, 'paint', UP, smooth=True)
    # flat window face looking forward / 12 deg down: octagonal plate (dark frame) with EO, IR and laser windows
    d = V((0, math.cos(math.radians(12)), -math.sin(math.radians(12))))
    rt_ = V((1, 0, 0))
    upw = d.cross(rt_).normalized() * -1
    if upw.z < 0:
        upw = -upw
    fc = c + d * 0.150
    octo = [(math.cos(math.pi / 8 + k * math.pi / 4) * 0.125, math.sin(math.pi / 8 + k * math.pi / 4) * 0.115) for k in range(8)]
    plate = [fc + rt_ * u + upw * v for u, v in octo]
    back = [fc - d * 0.06 + rt_ * u * 1.02 + upw * v * 1.02 for u, v in octo]
    loft(mb, [back, plate], 'metal_dark', smooth=False)
    fan_cap(mb, plate, fc, 'metal_dark', d)
    bezel_window(mb, fc + rt_ * -0.035 + upw * 0.010, d, 0.050, 'sensor', 'structure', 0.008, N=24)   # EO (large aperture)
    sq = [fc + d * 0.004 + rt_ * u + upw * v for u, v in ((0.025, -0.055), (0.095, -0.055), (0.095, 0.020), (0.025, 0.020))]
    oriented_quad(mb, sq, 'sensor', d)                                                                 # IR window
    bezel_window(mb, fc + rt_ * 0.06 + upw * 0.060, d, 0.018, 'sensor', 'structure', 0.006, N=16)      # laser designator
    bezel_window(mb, fc + rt_ * -0.035 + upw * -0.075, d, 0.014, 'sensor', 'structure', 0.005, N=12)   # rangefinder rx
    ball = P.Part('chin_turret', 'fus_nose', c, mb, info=dict(note='EO/IR gimbal + laser designator / rangefinder (TargetCam mount)'))
    tc = P.Part('targetcam_point', 'fus_nose', c + V((0, 0.20, -0.02)), None, info=dict(kind='sensor', note='TargetCam forward mount'))
    radar = P.Part('radar_antenna', 'fus_nose', (0, S.NOSE_TIP_Y - 0.80, 0.25), None,
                   info=dict(kind='sensor', note='conformal radar array in the nose skin (Radar.scanner)'))
    return [ball, tc, radar]


# ============================================================================================ package fairings
def build_package_fairing(side):
    """chined conformal gun fairing on the fuselage side (one 20 mm each): flat-sided, faceted, sharp nose with a
    muzzle shroud; footprint as 0.1.0 (y 1.90-3.95, centre z -0.18)."""
    P = _P()
    L = 'L' if side < 0 else 'R'
    mb = MeshBuf()
    zc = -0.18
    st = [(1.90, 0.00, 0.06), (2.10, 0.07, 0.15), (2.45, 0.13, 0.19), (3.00, 0.15, 0.19), (3.45, 0.14, 0.17),
          (3.75, 0.10, 0.12), (3.95, 0.075, 0.07), (4.02, 0.065, 0.055)]   # tip wraps the barrel (0.3.1)
    rings = []
    for y, d, h in st:
        hw = P.fus_params(y)[0] - 0.03
        d = max(d, 0.012)
        sec = [(0.0, h), (0.55, h), (1.0, 0.25 * h), (1.0, -0.15 * h), (0.70, -0.85 * h), (0.0, -h)]   # chined section
        rings.append([V((side * (hw + u * (d + 0.03)), y, zc + v)) for u, v in sec])
    loft(mb, rings, 'paint', closed=False, smooth=False, uvfunc=ring_arc_uv(rings, [s[0] for s in st]))
    fan_cap(mb, rings[0], sum(rings[0], V()) / len(rings[0]), 'paint', V((0, -1, 0)))
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / len(rings[-1]), 'metal_dark', V((0, 1, 0)))
    x = side * (P.fus_params(4.02)[0] - 0.03 + 0.5 * (0.065 + 0.03))                   # on the fairing tip's axis (0.3.1: was 6 cm outboard)
    tip = V((x, 4.20, zc))
    tube(mb, V((x, 3.90, zc)), tip, 0.022, 0.010, N=14)
    cylinder(mb, V((x, 3.98, zc)), V((x, 4.08, zc)), 0.030, 0.027, N=14)                 # muzzle shroud
    for k in range(4):                                                                  # cooling slots on the fairing top
        yy = 2.55 + 0.16 * k
        hw = P.fus_params(yy)[0] - 0.03
        box(mb, (side * (hw + 0.10), yy, zc + 0.192), (0.06, 0.07, 0.004), 'metal_dark')
    return [P.Part(f'package_guns_{L}', 'fus_cockpit', (side * 0.80, 2.8, zc), mb,
                   info=dict(note='chined conformal gun fairing, one 20 mm cannon, 250 rounds')),
            P.Part(f'muzzle_package_{L}1', f'package_guns_{L}', tip, info=dict(kind='muzzle'))]


# ============================================================================================ dorsal laser turret
LASER_RING_Z = S.TURRET_RING_Z + 0.05    # 1.23, ring structure top in fus_forward (B-25H turret ring)
LASER_TZ = LASER_RING_Z + 0.30           # trunnion = beam director pivot (0.1.0 value: the self-fire envelope uses it)


def build_laser_turret():
    """faceted low-profile turret: octagonal armoured base, two faceted cheek plates carrying the beam director; the
    director is a faceted box with a large polished-ring mirror aperture, a tracker window and rear heat-exchanger fins.
    Pivots, axes and the muzzle are the 0.1.0 values (beam origin unchanged, so the generator's self-fire scan holds)."""
    P = _P()
    cy = G.LASER_C[1]
    RZ = LASER_RING_Z
    piv = V((0, cy, RZ))
    mount = P.Part('laser_turret_mount', 'fus_forward', piv, None, info=dict(kind='turret_mount', note='identity (fwd = +Z Unity); 360 deg traverse'))
    az = MeshBuf()
    oct_ = lambda r, z: [V((r * math.cos(math.pi / 8 + k * math.pi / 4), cy + r * math.sin(math.pi / 8 + k * math.pi / 4), z)) for k in range(8)]
    base = [oct_(0.455, RZ - 0.006), oct_(0.440, RZ + 0.045), oct_(0.395, RZ + 0.085), oct_(0.330, RZ + 0.100)]
    loft(az, base, 'paint', smooth=False, uvfunc=ring_arc_uv(base, [r[0].z for r in base]))
    fan_cap(az, base[-1], V((0, cy, RZ + 0.100)), 'paint', UP, uvfunc=lambda p: (p.x, p.y))
    annulus(az, base[0], oct_(0.39, RZ - 0.006), 'structure', -UP)
    # cheek plates (faceted wedges) at x +-0.215
    prof = [(-0.25, RZ + 0.07), (0.20, RZ + 0.07), (0.23, RZ + 0.13), (0.12, LASER_TZ + 0.10), (-0.05, LASER_TZ + 0.14), (-0.22, LASER_TZ + 0.06)]
    for s in (-1, 1):
        for xi, xo in ((0.180, 0.252),):
            a = [V((s * xi, cy + py, pz)) for py, pz in prof]
            b = [V((s * (xo - 0.012 * (1 if pz > RZ + 0.2 else 0)), cy + py, pz)) for py, pz in prof]
            loft(az, [a, b], 'paint', smooth=False, uvfunc=ring_arc_uv([a, b], [s * xi, s * xo]))
            fan_cap(az, a, sum(a, V()) / len(a), 'paint', V((-s, 0, 0)))
            fan_cap(az, b, sum(b, V()) / len(b), 'paint', V((s, 0, 0)), uvfunc=lambda p: (p.y, p.z))
        box(az, (s * 0.268, cy - 0.02, LASER_TZ), (0.03, 0.09, 0.09), 'metal_dark')            # elevation drive housing
    azp = P.Part('laser_turret_az', 'laser_turret_mount', piv, az,
                 info=dict(kind='turret_az', axis_local='+Y (Unity) = up', traverseRange=360, traverseRate=150,
                           note='faceted armoured base + cheek plates; rests identity under laser_turret_mount (rates: stock HLT laser turret)'))
    azp.uv_group = 'laser_turret'
    el = MeshBuf()
    tp = V((0, cy, LASER_TZ))
    X, Z = V((1, 0, 0)), UP
    sec = [(-0.165, -0.055), (-0.115, -0.120), (0.115, -0.120), (0.165, -0.055), (0.165, 0.060), (0.110, 0.125),
           (-0.110, 0.125), (-0.165, 0.060)]
    frames = [(tp + FWD * dy, X, Z) for dy in (-0.15, 0.20, 0.30)]
    rings = prism(el, sec, frames, 'paint', scale=[0.92, 1.0, 0.80], caps=False)
    fan_cap(el, rings[0], tp + FWD * -0.15, 'metal_dark', -FWD)
    front = rings[-1]
    fc = tp + FWD * 0.30
    fan_cap(el, front, fc, 'metal_dark', FWD)
    # mirror aperture: polished ring + recessed mirror, plus a small tracker / illuminator window
    o = circle_pts(fc + FWD * 0.004, FWD, 0.098, 32, ref=Z)
    i = circle_pts(fc + FWD * 0.004, FWD, 0.080, 32, ref=Z)
    annulus(el, o, i, 'structure', FWD)
    rec = circle_pts(fc - FWD * 0.03, FWD, 0.080, 32, ref=Z)
    loft(el, [i, rec], 'metal_dark', outward=False)
    fan_cap(el, rec, fc - FWD * 0.03, 'sensor', FWD)
    bezel_window(el, fc + X * 0.095 + Z * 0.065, FWD, 0.016, 'sensor', 'structure', 0.005, N=14)
    bezel_window(el, fc + X * -0.095 + Z * 0.065, FWD, 0.010, 'sensor', 'structure', 0.004, N=12)
    cylinder(el, tp - X * 0.19, tp + X * 0.19, 0.038, N=14, mat='metal_dark')               # trunnion
    for k in range(5):                                                                     # rear heat-exchanger fins
        zz = -0.08 + 0.04 * k
        box(el, tp + FWD * -0.175 + Z * zz, (0.24, 0.05, 0.008), 'metal_dark')
    box(el, tp + FWD * 0.05 + Z * 0.128, (0.14, 0.22, 0.008), 'structure')                  # top access panel
    elp = P.Part('laser_turret_el', 'laser_turret_az', tp, el,
                 info=dict(kind='turret_el', axis_local='+X (Unity) = right', minElevation=7.5, maxElevation=90, elevationRate=60,
                           note='faceted beam director; Laser component here (forward = +Z Unity); rests identity under the az; min '
                                'elevation +7.5 = the B-25H dorsal turret safe envelope at this ring (in-game 1.1.0: 0 self hits)'))
    elp.uv_group = 'laser_turret'
    mz = P.Part('muzzle_laser', 'laser_turret_el', tp + FWD * 0.31, None, info=dict(kind='muzzle', note='Laser.directionTransform + beam origin'))
    return [mount, azp, elp, mz]


# ============================================================================================ formation / gear-down light strips
SLIME_OFF = 0.003     # strip lift off the skin (m): 3 mm, never coplanar with the paint


def _strip(mb, rows, normals):
    """quad strip from rows of (edge_a, edge_b) points, each face oriented along the local normal."""
    for (a0, b0), (a1, b1), n0, n1 in zip(rows, rows[1:], normals, normals[1:]):
        oriented_quad(mb, [a0, b0, b1, a1], 'light_off', (n0 + n1) / 2)


def build_slimelights():
    """0.3.0: green gear-down strips in the Nuclear Option design language (stock NavLights entries 'slimelight_*', lit
    material slimelight_on; research doc section 3). Separate thin quad meshes, 3 mm proud of the skin, own material slot
    'light_off' (never the paint slot: the livery swaps material[0] and NavLights restores the material it captured).
    Placement after the A-19 (closest stock twin): nose sides under the canopy sill, wing-tip tops (chordwise), outboard
    faces of the twin fins along the leading edge, plus the outboard nacelle sides (user)."""
    P = _P()
    from b25h_geom import Station
    out = []
    for side, L in ((-1, 'L'), (1, 'R')):
        nrm_side = V((side, 0, 0))
        # 1. nose / cockpit side: 0.80 x 0.06 m, 0.10 m under the side-glazing sill, aft end ahead of the canopy aft frame
        mb = MeshBuf()
        y0, y1, zc, hh = 2.88, 3.68, 0.765, 0.03
        rows, ns = [], []
        for k in range(5):
            y = y0 + (y1 - y0) * k / 4
            x = side * (P.fus_params(y)[0] + SLIME_OFF)
            rows.append((V((x, y, zc - hh)), V((x, y, zc + hh))))
            ns.append(nrm_side)
        _strip(mb, rows, ns)
        out.append(P.Part(f'slimelight_nose_{L}', 'fus_cockpit', V((side * (P.fus_params(3.28)[0] + SLIME_OFF), 3.28, zc)), mb,
                          info=dict(kind='slimelight', size_m=(0.80, 0.06), note='horizontal strip under the canopy sill (A-19 slimelights_F)')))
        # 2. wing tip top: chordwise 0.60 x 0.06 m at |x| 9.30 (ahead of the aileron hinge at 74 % chord)
        mb = MeshBuf()
        xs = (9.27, 9.33)
        sts = [P.wing_station(x, side) for x in xs]
        c = sts[0].chord
        s0, s1 = 0.08, 0.08 + 0.60 / c
        rows, ns = [], []
        for k in range(7):
            sv = s0 + (s1 - s0) * k / 6
            pa, pb = sts[0].point(sv, True), sts[1].point(sv, True)
            ux = (pb - pa).normalized()
            fwd = (sts[0].point(min(sv + 0.01, 0.99), True) - sts[0].point(max(sv - 0.01, 0.0), True)).normalized()
            n = fwd.cross(ux).normalized()
            if n.z < 0:
                n = -n
            rows.append((pa + n * SLIME_OFF, pb + n * SLIME_OFF))
            ns.append(n)
        _strip(mb, rows, ns)
        out.append(P.Part(f'slimelight_tip_{L}', f'wing_tip_{L}', (rows[3][0] + rows[3][1]) / 2, mb,
                          info=dict(kind='slimelight', size_m=(0.06, 0.60), note='chordwise strip on the wing-tip top (A-19 slimelight_L/R)')))
        # 3. fin outboard face: 1.0 x 0.07 m, 0.15 m behind the leading edge, z 0.95 .. 1.95
        mb = MeshBuf()
        fx = side * S.FIN_X
        tab = S.FIN_TABLE
        zs = sorted({0.95, 1.95} | {r[0] for r in tab if 0.95 < r[0] < 1.95})
        rows, ns = [], []
        for z in zs:
            le = interp_table([(r[0], (r[1], r[2])) for r in tab], z)
            st = Station(z, V((fx, le[0], z)), V((0, -1, 0)), V((side, 0, 0)), le[0] - le[1], 0.13, m=0.0)
            sa, sb = (0.15 - 0.035) / st.chord, (0.15 + 0.035) / st.chord
            pa, pb = st.point(sa, True), st.point(sb, True)
            rows.append((pa + nrm_side * SLIME_OFF, pb + nrm_side * SLIME_OFF))
            ns.append(nrm_side)
        _strip(mb, rows, ns)
        mid = rows[len(rows) // 2]
        out.append(P.Part(f'slimelight_fin_{L}', f'fin_{L}', (mid[0] + mid[1]) / 2, mb,
                          info=dict(kind='slimelight', size_m=(0.07, 1.0), note='outboard fin face along the leading edge (EW-25 / A-19)')))
        # 4. nacelle outboard side under the wing: 0.55 x 0.05 m, y 0.40 .. 0.95 (behind the cowl, ahead of the gear well)
        mb = MeshBuf()
        cx = side * S.NAC_X
        rows, ns = [], []
        for k in range(5):
            y = 0.40 + 0.55 * k / 4
            th = side * math.pi / 2
            hw = P.nac_params(y)[0]
            dth = 0.025 / max(hw, 0.2)
            pa, pb = nac_pt(y, th + dth, cx), nac_pt(y, th - dth, cx)
            n = nac_normal(y, th, cx)
            rows.append((pa + n * SLIME_OFF, pb + n * SLIME_OFF))
            ns.append(n)
        _strip(mb, rows, ns)
        out.append(P.Part(f'slimelight_nacelle_{L}', f'nacelle_{L}', (rows[2][0] + rows[2][1]) / 2, mb,
                          info=dict(kind='slimelight', size_m=(0.55, 0.05), note='outboard nacelle side under the wing (user; KR-67 intake-side analogue)')))
    return out


# ============================================================================================ belly laser turret (0.3.0)
def belly_skin_z(x, y):
    """lower fuselage skin z at (x, y) (rounded-rectangle section)."""
    P = _P()
    hw, zb, zt, rt, rb = P.fus_params(y)
    ax = abs(x)
    if ax <= hw - rb:
        return zb
    d = min(ax - (hw - rb), rb)
    return zb + rb - math.sqrt(max(rb * rb - d * d, 0.0))


def build_laser_belly(rear_mesh):
    """0.3.0 (user): the laser turret moves from the dorsal ring to the belly just behind the bomb bay. The 0.2.0 turret
    meshes are reused, turned upside down (180 deg about the forward axis) around a new mount under fus_rear, inside a
    shallow ventral fairing. Object frames stay IDENTITY (stock Turret convention: traverse about the mount's +Y,
    elevation localEulerAngles.x, positive = muzzle down), so the turret aims into the lower hemisphere with
    minElevation -90 / maxElevation -2 (research doc section 8). The dorsal ring hole is plated over (build_ga25x)."""
    P = _P()
    src = build_laser_turret()
    yL = G.LASER_BELLY_Y
    zb = belly_skin_z(0.0, yL)
    zm = zb - G.LASER_FAIRING_DEPTH
    Pd = V((0, G.LASER_C[1], LASER_RING_Z))
    M = V((0, yL, zm))
    T = lambda p: M + V((-(p.x - Pd.x), p.y - Pd.y, -(p.z - Pd.z)))
    out = []
    for q in src:
        mb = None
        if q.mesh is not None:
            mb = MeshBuf()
            mb.verts = [T(v) for v in q.mesh.verts]
            mb.faces = [dict(f) for f in q.mesh.faces]
        info = dict(q.info)
        if q.name == 'laser_turret_mount':
            info['note'] = ('identity (+Y up, fwd = +Z Unity) under fus_rear on the belly, 0.3.0; 360 deg traverse; the turret hangs '
                            'below it (meshes upside down)')
        if q.name == 'laser_turret_el':
            info.update(minElevation=-90.0, maxElevation=-2.0,
                        note='ventral beam director; Laser here (forward = +Z Unity); rests identity under the az; elevation '
                             '-90..-2 = below the turret plane (Turret.cs:714 clamps localEulerAngles.x to [2, 90], positive = '
                             'muzzle down). Generator: FiringCone axis = -mount.up, exclusion cone toward the open bay doors.')
        if q.name == 'laser_turret_az':
            info['note'] = 'faceted armoured base + cheek plates (upside down under the ventral fairing); rests identity under the mount'
        n = P.Part(q.name, 'fus_rear' if q.name == 'laser_turret_mount' else q.parent, T(q.pivot), mb, info=info)
        n.uv_group = q.uv_group
        out.append(n)
    # ventral fairing (paint) blending from the belly skin into the turret ring, closed by a dark ring floor
    N = 40
    A0, B0 = 0.62, 0.50          # footprint semi-axes (x, y) on the skin
    R1 = 0.47                    # ring at the mount plane (outside the 0.455 m octagonal base)
    us = [0.0, 0.3, 0.6, 0.85, 1.0]
    rings = []
    for u in us:
        a, b = A0 + (R1 - A0) * u, B0 + (R1 - B0) * u
        w = smooth01(u)
        ring = []
        for k in range(N):
            th = 2 * math.pi * k / N
            x, y = a * math.cos(th), yL + b * math.sin(th)
            z = (belly_skin_z(x, y) - 0.002) * (1 - w) + zm * w
            ring.append(V((x, y, z)))
        rings.append(ring)
    loft(rear_mesh, rings, 'paint', outward=True)
    inner = circle_pts(V((0, yL, zm)), UP, 0.40, N, ref=V((1, 0, 0)))
    annulus(rear_mesh, rings[-1], inner, 'metal_dark', -UP)
    loft(rear_mesh, [inner, [p + UP * 0.03 for p in inner]], 'metal_dark', outward=False)
    fan_cap(rear_mesh, [p + UP * 0.03 for p in inner], V((0, yL, zm + 0.03)), 'metal_dark', -UP)
    return out


# ============================================================================================ waist sensor panels
def _side_pt(side, y, z, off=0.0):
    P = _P()
    return V((side * (P.fus_params(y)[0] + off), y, z))


def flush_pad(mb, side, y0, y1, z0, z1, proud=0.004, bevel=0.012, mat='paint'):
    """flat panel on the fuselage side, `proud` above the skin, bevelled edges (reads as a separate flush panel)."""
    out = [_side_pt(side, y, z, 0.0005) for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1))]
    inn = [_side_pt(side, y, z, proud) for y, z in ((y0 + bevel, z0 + bevel), (y1 - bevel, z0 + bevel), (y1 - bevel, z1 - bevel), (y0 + bevel, z1 - bevel))]
    loft(mb, [out, inn], mat, smooth=False, uvfunc=ring_arc_uv([out, inn], [0.0, proud]))
    oriented_quad(mb, inn, mat, V((side, 0, 0)))
    return inn


def add_sensor_panels(rear_mesh):
    """old waist-window band: flush conformal sensor panels (ESM / missile-warning apertures) + flush flare dispensers."""
    P = _P()
    y0, y1 = G.SENSOR_PANEL_Y
    yc = (y0 + y1) / 2
    for side in (-1, 1):
        n = V((side, 0, 0))
        flush_pad(rear_mesh, side, y0 + 0.15, y1 - 0.15, 0.10, 0.48)
        hw = P.fus_params(yc)[0]
        # two missile-warning apertures + a narrow ESM strip window
        yy = yc - 0.28
        bezel_window(rear_mesh, V((side * (P.fus_params(yy)[0] + 0.004), yy, 0.29)), n, 0.055, 'sensor', 'metal_dark', 0.010, N=24)
        for k in range(3):                                   # ESM interferometer apertures (vertical slots)
            ya = yc + 0.10 + 0.085 * k
            slot = [_side_pt(side, y, z, 0.0055) for y, z in ((ya - 0.018, 0.17), (ya + 0.018, 0.17), (ya + 0.018, 0.41), (ya - 0.018, 0.41))]
            oriented_quad(rear_mesh, slot, 'sensor', n)
        # flush flare dispenser: dark frame + 2 x 6 cartridge cells, below the panel
        fr = flush_pad(rear_mesh, side, yc - 0.27, yc + 0.27, -0.40, -0.22, 0.003, 0.008, 'metal_dark')
        for i in range(6):
            for j in range(2):
                ya, za = yc - 0.225 + 0.09 * i, -0.36 + 0.08 * j
                cell = [_side_pt(side, y, z, 0.0045) for y, z in ((ya - 0.03, za - 0.025), (ya + 0.03, za - 0.025), (ya + 0.03, za + 0.025), (ya - 0.03, za + 0.025))]
                oriented_quad(rear_mesh, cell, 'sensor', n)
    out = []
    for side, L in ((-1, 'L'), (1, 'R')):
        hw = P.fus_params(yc)[0]
        out.append(P.Part(f'flare_{L}', 'fus_rear', (side * (hw + 0.03), yc, -0.31), None, frame_from_axes(V((0, 1, 0)), V((side, 0, -0.6))),
                          info=dict(kind='flare_point', note='FlareEjector ejection point, Unity +Y = outward/down')))
    return out


# ============================================================================================ sensor tail cone
def tailcone(tail_mesh):
    """sensor tail cone (replaces b25h_v3_arms.tail_cap): tapered fairing into a sensor head carrying four
    missile-warning windows (aft, aft-left, aft-right, aft-down), an IR-jammer ball turret in a socket at the tip,
    flush flare dispensers on the lower flanks and the tail-hook keel fairing."""
    P = _P()
    ye = S.TAIL_END_Y
    o = P.fus_ring(ye)
    c = sum(o, V()) / len(o)
    prof = [(0.0, 1.0), (0.05, 0.95), (0.10, 0.84), (0.15, 0.70), (0.19, 0.58), (0.205, 0.56)]
    base = [V((c.x + (p.x - c.x) * prof[-1][1], 0, c.z + (p.z - c.z) * prof[-1][1])) for p in o]
    hx = max(abs(p.x - c.x) for p in base)
    hz = max(abs(p.z - c.z) for p in base)
    octo = [(hx * math.cos(math.pi / 8 + a * math.pi / 4), hz * math.sin(math.pi / 8 + a * math.pi / 4)) for a in range(8)]

    def on_oct(p, k):
        """point of the octagon (scale k) on the ray from the section centre through p (x/z)."""
        dx, dz = p.x - c.x, p.z - c.z
        best = None
        for i in range(8):
            (ax, az), (bx, bz) = octo[i], octo[(i + 1) % 8]
            ex, ez = bx - ax, bz - az
            den = dx * ez - dz * ex
            if abs(den) < 1e-12:
                continue
            t = (ax * ez - az * ex) / den
            u = (ax * dz - az * dx) / den
            if t > 0 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best):
                best = t
        return V((c.x + dx * best * k, 0, c.z + dz * best * k))
    # 0.3.0: the taper's last two rings morph from the fuselage section into the octagonal sensor drum, and the drum is
    # sampled with the same vertex count, so cone and drum are one closed surface (0.2.0 had a forward-facing cap here:
    # culled from behind = the open gap at the drum corners).
    rings = []
    for k, (d, sc) in enumerate(prof):
        ring = [V((c.x + (p.x - c.x) * sc, ye - d, c.z + (p.z - c.z) * sc)) for p in o]
        t = {len(prof) - 2: 0.5, len(prof) - 1: 1.0}.get(k, 0.0)
        if t:
            ring = [q.lerp(on_oct(q, 1.0) + V((0, ye - d, 0)), t) for q in ring]
        rings.append(ring)
    loft(tail_mesh, rings, 'paint', uvfunc=ring_arc_uv(rings, [ye - d for d, _ in prof]))
    ring_end = rings[-1]
    drum = [ring_end] + [[on_oct(q, kk) + V((0, yy, 0)) for q in ring_end] for yy, kk in ((ye - 0.26, 0.97), (ye - 0.29, 0.80))]
    loft(tail_mesh, drum, 'paint', smooth=False, uvfunc=ring_arc_uv(drum, [r[0].y for r in drum]))
    face = drum[-1]
    fcen = V((c.x, ye - 0.29, c.z))
    fan_cap(tail_mesh, face, fcen, 'metal_dark', V((0, -1, 0)))
    # IR-jammer ball turret in a socket
    br = min(hx, hz) * 0.62
    sock_o = circle_pts(fcen - V((0, 0.004, 0)), V((0, -1, 0)), br + 0.02, 28)
    sock_i = circle_pts(fcen - V((0, 0.004, 0)), V((0, -1, 0)), br + 0.004, 28)
    annulus(tail_mesh, sock_o, sock_i, 'structure', V((0, -1, 0)))
    bc = fcen + V((0, 0.02, 0))
    rr = []
    for i in range(1, 12):
        phi = -math.pi / 2 + math.pi * i / 12
        rr.append(circle_pts(bc + V((0, -br * math.sin(phi), 0)), V((0, -1, 0)), br * math.cos(phi), 24))
    loft(tail_mesh, rr[5:], 'paint')
    fan_cap(tail_mesh, rr[-1], bc + V((0, -br, 0)), 'paint', V((0, -1, 0)), smooth=True)
    # jammer emitter window on the ball (aft, slightly down) + a dark band
    wd = V((0, -1, -0.25)).normalized()
    bezel_window(tail_mesh, bc + wd * (br - 0.006), wd, br * 0.42, 'sensor', 'metal_dark', 0.008, N=20)
    # MWS windows on the drum facets: left, right, down, up (aft-looking)
    for d in (V((-1, -0.55, 0.0)), V((1, -0.55, 0.0)), V((0, -0.55, -1.0)), V((0, -0.55, 1.0))):
        d = d.normalized()
        lat = V((d.x, 0, d.z)).normalized()
        p = V((c.x + lat.x * hx * 0.93, ye - 0.235, c.z + lat.z * hz * 0.93))
        bezel_window(tail_mesh, p, d, 0.028, 'sensor', 'metal_dark', 0.008, N=16, proud=0.006)
    # flush flare dispensers on the lower flanks (cells 2 x 3), around the flare_tail points
    for side in (-1, 1):
        y = ye + 0.30
        hw, zb, zt, rt, rb = P.fus_params(y)
        z0 = zb + rb * 0.9
        nrm = V((side, 0, -0.6)).normalized()
        pc = V((side * (hw - rb * 0.28), y, zb + rb * 0.28))
        u = V((0, 1, 0))
        v = nrm.cross(u).normalized()
        quad = [pc + nrm * 0.004 + u * a + v * b for a, b in ((-0.13, -0.05), (0.13, -0.05), (0.13, 0.05), (-0.13, 0.05))]
        oriented_quad(tail_mesh, quad, 'metal_dark', nrm)
        for i in range(3):
            for j in range(2):
                a0, b0 = -0.09 + 0.09 * i, -0.022 + 0.044 * j
                cell = [pc + nrm * 0.006 + u * (a0 + a) + v * (b0 + b) for a, b in ((-0.035, -0.017), (0.035, -0.017), (0.035, 0.017), (-0.035, 0.017))]
                oriented_quad(tail_mesh, cell, 'sensor', nrm)
    # tail-hook keel fairing
    hp = V(G.TAILHOOK_PIVOT)
    zb = P.fus_params(hp.y + 0.10)[1]
    box(tail_mesh, (0, hp.y + 0.05, zb - 0.02), (0.20, 0.30, 0.06), 'paint')
    return tail_mesh


def tailcone_parts():
    P = _P()
    ye = S.TAIL_END_Y
    o = P.fus_ring(ye)
    c = sum(o, V()) / len(o)
    out = [P.Part('mws_tail', 'fus_tail', (c.x, ye - 0.26, c.z), None, frame_from_axes(V((-1, 0, 0)), V((0, 0, 1))),
                  info=dict(kind='sensor', note='tail sensors (missile warning + IR jammer ball); Unity +Z = aft'))]
    for side, L in ((-1, 'L'), (1, 'R')):
        out.append(P.Part(f'flare_tail_{L}', 'fus_tail', (side * 0.22, ye + 0.30, c.z - 0.20), None,
                          frame_from_axes(V((0, 1, 0)), V((side, -0.3, -0.6))), info=dict(kind='flare_point')))
    return out


# ============================================================================================ pylons (4 per wing)
PYLONS = [  # key, parent part (per side), length, note (options: docs/ga25x_visual_pass_generator_changes.md)
    ('root', 'wing_inner', 1.45, 'root pylon (between fuselage and nacelle): all spec pylon stores'),
    ('inner', 'wing_outer', 1.45, 'inner pylon: AGM-68 / AGM-48 x3 / AGR-24 x12 / PAB-250LR'),
    ('mid', 'wing_outer', 1.25, 'mid pylon: single stores only (AGM-68 / AGR-24 x4 / PAB-250LR / MMR-S3)'),
    ('outer', 'wing_outer', 1.25, 'outer pylon: AGM-48 x3 / AGR-24 x4 / MMR-S3'),
]


def build_pylons():
    import b25h_v3_arms as A3
    P = _P()
    out = []
    for side, L in ((-1, 'L'), (1, 'R')):
        for key, parent, ln, note in PYLONS:
            x = G.PYLON_X[key]
            st = P.wing_station(x, side)
            y = st.point(0.30, False).y
            p, h = A3.pylon(f'pylon_{key}_{L}', f'{parent}_{L}', side, side * x, y, ln, 0.12, 0.16, f'hp_{key}_{L}', note)
            out += [p, h]
    return out


# ============================================================================================ cockpit modernisation
def modern_cockpit(parts):
    """in place on the build_cockpit() parts: HOTAS-style throttle grips (same objects, pivots, rest/range), ISIS
    standby displays instead of the three 1940s dials (cockpit_gauges keeps its name; own 0-1 cells of the GA-25X
    gauge atlas ga25x_gauges.png: cell 0 ISIS attitude, 1 engine/power, 2 nav/clock)."""
    import b25h_v3_cockpit as C3
    by = {p.name: p for p in parts}
    q = Quaternion(V((1, 0, 0)), C3.QUAD_TILT)
    up = q @ UP
    rest = Quaternion(V((1, 0, 0)), math.radians(C3.THROTTLE_REST))
    for L in ('L', 'R'):
        p = by[f'quadrant_throttle_{L}']
        piv = V(p.pivot)
        lm = MeshBuf()
        d = rest @ up
        tip = piv + d * 0.13
        gx = -1 if L == 'L' else 1
        cylinder(lm, piv - V((0.010, 0, 0)), piv + V((0.010, 0, 0)), 0.013, N=12, mat='metal_dark')
        cylinder(lm, piv, tip, 0.008, N=10, mat='metal_dark')
        rq = rest @ q
        g = tip + d * 0.035
        box(lm, g + V((gx * 0.010, 0, 0)), (0.040, 0.050, 0.075), 'rubber', rot=rq)              # grip body
        box(lm, g + rq @ V((gx * 0.010, -0.012, 0.042)), (0.036, 0.040, 0.012), 'rubber', rot=rq)  # palm rest cap
        for k, (bx, bz) in enumerate(((-0.008, 0.030), (0.010, 0.030), (0.0, 0.012))):            # thumb switches
            box(lm, g + rq @ V((gx * 0.010 + bx, 0.027, bz)), (0.010, 0.006, 0.010), 'metal_dark', rot=rq)
        p.mesh = lm
    # ISIS / standby displays
    g = by['cockpit_gauges']
    gf = MeshBuf()
    rt, pu, pn = V((1, 0, 0)), C3.PU, C3.PN
    for (x, z, cell, w) in ((-0.080, 0.885, 1, 0.060), (0.0, 0.885, 0, 0.072), (0.080, 0.885, 2, 0.060)):
        c = C3.panel_pt(x, z) + pn * 0.010
        h = w * 0.85
        for (a, b, ww, hh) in ((0, h / 2 + 0.006, w + 0.016, 0.012), (0, -h / 2 - 0.006, w + 0.016, 0.012),
                               (w / 2 + 0.006, 0, 0.012, h), (-w / 2 - 0.006, 0, 0.012, h)):
            box(gf, c + rt * a + pu * b - pn * 0.002, (ww, 0.010, hh), 'metal_dark', rot=Quaternion(V((1, 0, 0)), -C3.RK))
        pts = [c - rt * (w / 2) - pu * (h / 2), c + rt * (w / 2) - pu * (h / 2), c + rt * (w / 2) + pu * (h / 2), c - rt * (w / 2) + pu * (h / 2)]
        uvs = [C3.cell_uv(cell, -1, -1), C3.cell_uv(cell, 1, -1), C3.cell_uv(cell, 1, 1), C3.cell_uv(cell, -1, 1)]
        oriented_quad(gf, pts, 'gauges', pn, uvs)
    g.mesh = gf
    g.info = dict(note='ISIS standby displays (attitude, engine/power, nav/clock), own UVs in the GA-25X gauge atlas')
    return parts


def modern_quadrant_body(m):
    """centre console replacing the B-25 quadrant body (pedestal + sloped housing, two lever slots, no prop / mixture
    levers): returns the B-25H throttle lever parts (pivots / info unchanged) whose meshes modern_cockpit() replaces."""
    import b25h_v3_cockpit as C3
    from b25h_v3 import FLOOR_Z, CK
    scratch = MeshBuf()
    levers = C3.throttle_quadrant(scratch)
    q = Quaternion(V((1, 0, 0)), C3.QUAD_TILT)
    up = q @ UP
    box(m, (0, C3.QUAD_Y - 0.10, (FLOOR_Z + C3.QUAD_TOP - 0.05) / 2), (0.22, 0.50, C3.QUAD_TOP - 0.05 - FLOOR_Z), CK)
    box(m, C3.quad_face_pt(0, 0) - up * 0.03, (0.22, 0.30, 0.06), CK, rot=q)
    for x in (-0.014, 0.014):
        box(m, C3.quad_face_pt(x, 0.0) + up * 0.0005, (0.010, 0.20, 0.002), 'metal_dark', rot=q)
    for k, x in enumerate((-0.075, 0.075)):                         # small keypads / trim panels either side
        box(m, C3.quad_face_pt(x, 0.03) + up * 0.001, (0.05, 0.10, 0.002), 'screen', rot=q)
    box(m, (0, C3.QUAD_Y - 0.28, C3.QUAD_TOP - 0.02), (0.20, 0.16, 0.004), 'screen')   # aft console display strip
    return levers
