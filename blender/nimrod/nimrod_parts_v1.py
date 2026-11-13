"""Hawker Nimrod Mk I exterior parts (procedural, our own geometry; dimensions from nimrod_spec).

Every builder returns b25h_parts.Part objects (mesh in WORLD coordinates, Blender frame: x right, y forward, z up).
Paint faces carry metre UVs (arc length / span) that build_nimrod packs into the livery atlas.
"""
import math, os, sys
from mathutils import Vector, Quaternion, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(HERE, '..', 'v2')
for p in (HERE, V2):
    if p not in sys.path:
        sys.path.insert(0, p)
from b25h_geom import (V, MeshBuf, loft, cylinder, box, circle_pts, fan_cap, oriented_quad, annulus, superellipse_ring,
                       Station, surface, planar_uv, frame_from_axes)
from b25h_parts import Part
import nimrod_spec as S


def frame_x(xaxis, zhint=(0, 0, 1)):
    return frame_from_axes(V(xaxis), V(zhint))


# ------------------------------------------------------------------------------------------- helpers
def fus_ring(y, N=36):
    """fuselage section at y (point 0 at the top centre, going to +x)."""
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
    L = lambda i: a[i] + (b[i] - a[i]) * t
    hw, zt, zb, n = L(1), L(2), L(3), L(4)
    cz = (zt + zb) / 2
    # flat-sided box with a rounder top decking: exponent n for the sides, top half uses a rounder curve
    pts = []
    for j in range(N):
        ang = 2 * math.pi * j / N
        s, c = math.sin(ang), math.cos(ang)
        e = n if c < 0 else max(2.0, n - 0.6)
        x = hw * math.copysign(abs(s) ** (2.0 / e), s)
        hz = (zt - cz) if c >= 0 else (cz - zb)
        z = cz + hz * math.copysign(abs(c) ** (2.0 / e), c)
        pts.append(V((x, y, z)))
    return pts


def ring_uv(rings, ys):
    """u = arc length round the section (from the top), v = station y (metres) - continuous fuselage island."""
    from b25h_geom import arc_lengths
    al = [arc_lengths(r) for r in rings]
    n = len(rings[0])

    def f(ci, cj, j):
        acc, P = al[ci]
        u = P if (cj == 0 and j == n - 1) else acc[cj]
        return (u, ys[ci])
    return f


def strut(mb, p0, p1, w, t, mat='paint', N=10, fwd=V((0, 1, 0))):
    """streamlined strut (elliptic section: chord w along the flight direction, thickness t)."""
    p0, p1 = V(p0), V(p1)
    ax = (p1 - p0).normalized()
    f = (fwd - ax * fwd.dot(ax)).normalized()
    s = ax.cross(f).normalized()
    def ring(c):
        return [c + f * (math.cos(2 * math.pi * k / N) * w / 2) + s * (math.sin(2 * math.pi * k / N) * t / 2) for k in range(N)]
    r0, r1 = ring(p0), ring(p1)
    loft(mb, [r0, r1], mat, smooth=True)
    fan_cap(mb, r0, p0, mat, -ax)
    fan_cap(mb, r1, p1, mat, ax)


def wire(mb, p0, p1, r=0.0045):
    cylinder(mb, p0, p1, r, N=4, mat='metal_dark', cap0=False, cap1=False, smooth=True)


# ------------------------------------------------------------------------------------------- fuselage
def build_fuselage():
    ys_all = sorted({round(s[0], 3) for s in S.FUS} | {S.ENGINE_AFT_Y, S.CENTRE_AFT_Y, S.COCKPIT_Y[0], S.COCKPIT_Y[1],
                    -0.55, -0.85, 1.2, 0.8, 0.4, -1.15, -2.6, -3.2, -3.8, -4.3}, reverse=True)
    segs = {'fus_engine': [y for y in ys_all if y >= S.ENGINE_AFT_Y],
            'NIMROD1': [y for y in ys_all if S.ENGINE_AFT_Y >= y >= S.CENTRE_AFT_Y],
            'fus_rear': [y for y in ys_all if y <= S.CENTRE_AFT_Y]}
    out = {}
    for name, ys in segs.items():
        mb = MeshBuf()
        rings = [fus_ring(y) for y in ys]
        n = len(rings[0])

        def keep(i, j, ys=ys, rings=rings):
            # cockpit opening: drop top faces between the cockpit stations above the sill
            ya, yb = ys[i], ys[i + 1]
            if S.COCKPIT_Y[0] - 1e-4 <= min(ya, yb) and max(ya, yb) <= S.COCKPIT_Y[1] + 1e-4:
                z = (rings[i][j].z + rings[i][(j + 1) % n].z) / 2
                return z < S.COCKPIT_SILL_Z
            return True
        loft(mb, rings, 'paint', keep=keep if name == 'NIMROD1' else None, uvfunc=ring_uv(rings, ys))
        if name == 'fus_engine':
            # cowl front ring: annulus to the spinner back plate (dark), and a closed disc behind it
            inner = [V((p.x * 0.88, p.y, p.z * 0.88)) for p in rings[0]]
            annulus(mb, rings[0], inner, 'metal_dark', V((0, 1, 0)))
            fan_cap(mb, inner, V((0, rings[0][0].y - 0.01, 0)), 'metal_dark', V((0, 1, 0)))
        if name == 'fus_rear':
            fan_cap(mb, rings[-1], sum(rings[-1], V()) / n, 'paint', V((0, -1, 0)), uvfunc=lambda p: (p.x * 4, p.z * 4))
        out[name] = mb
    return out


def add_cowl_details(mb):
    """exhaust stubs (6 per side), chin intake, gun troughs on the top decking (metal_dark channels)."""
    for side in (-1, 1):
        for k in range(6):
            y = 0.40 + k * 0.245
            r = fus_ring(y)
            hw = max(abs(p.x) for p in r)
            c = V((side * (hw + 0.020), y, 0.07))
            box(mb, c, (0.05, 0.11, 0.06), 'metal_dark', rot=Quaternion((0, 0, 1), math.radians(side * -12)))
            box(mb, c + V((side * 0.028, -0.045, 0)), (0.012, 0.06, 0.045), 'exhaust')
        # gun trough: a dark channel let into the decking from the windscreen to the trough exit
        for y0, y1 in ((S.GUN_BREECH_Y + 0.30, S.GUN_TROUGH_END_Y),):
            zs = []
            for y in (y0, (y0 + y1) / 2, y1):
                rr = fus_ring(y, 72)
                zs.append(max(p.z for p in rr if abs(abs(p.x) - S.GUN_X) < 0.03))
            for (ya, za), (yb, zb) in zip(zip((y0, (y0 + y1) / 2), zs), zip(((y0 + y1) / 2, y1), zs[1:])):
                q = [V((side * (S.GUN_X - 0.032), ya, za + 0.004)), V((side * (S.GUN_X + 0.032), ya, za + 0.004)),
                     V((side * (S.GUN_X + 0.032), yb, zb + 0.004)), V((side * (S.GUN_X - 0.032), yb, zb + 0.004))]
                oriented_quad(mb, q, 'metal_dark', V((0, 0, 1)))
    # carburettor intake under the nose
    box(mb, (0, 1.85, -0.62), (0.16, 0.30, 0.10), 'paint')
    box(mb, (0, 2.005, -0.62), (0.12, 0.012, 0.07), 'metal_dark')


def build_radiator():
    """ventral radiator bath between the undercarriage legs (part of fus_engine)."""
    mb = MeshBuf()
    ys = [0.74, 0.66, 0.40, 0.12, 0.02]
    prof = {0.74: (0.20, -0.62), 0.66: (0.27, -0.95), 0.40: (0.28, -0.985), 0.12: (0.26, -0.95), 0.02: (0.20, -0.62)}
    rings = []
    for y in ys:
        hw, zb = prof[y]
        rings.append([V((-hw, y, -0.58)), V((-hw, y, zb + 0.03)), V((-hw + 0.03, y, zb)), V((hw - 0.03, y, zb)), V((hw, y, zb + 0.03)), V((hw, y, -0.58))])
    loft(mb, rings, 'paint', closed=False, uvfunc=lambda ci, cj, j: (cj * 0.25, ys[ci]))
    # matrix faces front and back
    for y, d in ((0.66, 1), (0.12, -1)):
        hw, zb = prof[y]
        oriented_quad(mb, [V((-hw + 0.02, y + d * 0.002, -0.60)), V((hw - 0.02, y + d * 0.002, -0.60)),
                           V((hw - 0.02, y + d * 0.002, zb + 0.02)), V((-hw + 0.02, y + d * 0.002, zb + 0.02))], 'radiator', V((0, d, 0)))
    return mb


# ------------------------------------------------------------------------------------------- wings
def wing_station(x, le, te, z, t=S.T_WING, inc=S.INCIDENCE):
    i = math.radians(inc)
    cdir = V((0, -math.cos(i), -math.sin(i)))
    up = V((0, math.sin(i), math.cos(i)))
    return Station(x, V((x, le, z)), cdir, up, max(le - te, 0.05) / math.cos(i), t, m=0.03)


def upper_z(ax):
    return S.UP_Z + max(ax - S.UP_CENTRE_X, 0.0) * math.tan(math.radians(S.UP_DIHEDRAL))


def lower_z(ax):
    return S.LO_Z + (ax - S.LO_ROOT_X) * math.tan(math.radians(S.LO_DIHEDRAL))


def tip_round(x, x0, x1, le, te, kind):
    """rounded tip planform: chord shrinks elliptically from x0 to x1 (LE recedes 30 %, TE advances 70 %)."""
    if x <= x0:
        return le, te
    f = min((x - x0) / (x1 - x0), 1.0)
    shrink = 1 - math.sqrt(max(1 - f * f, 0.0))
    c = (le - te)
    lo = c * 0.94 * shrink
    return le - lo * 0.35, te + lo * 0.65


def upper_panel(side):
    """outer upper wing (box to the aileron hinge + fixed TE where there is no aileron), aileron separately."""
    mb = MeshBuf()
    x0, x1 = S.UP_CENTRE_X, S.UP_TIP_X
    xs = [x0, 1.2, 1.6, S.AIL_X[0], 2.4, 3.0, S.STRUT_X, 3.9, 4.4, S.AIL_X[1], 4.98, 5.05, 5.10, x1]
    sts = []
    for ax in xs:
        le, te = tip_round(ax, 4.55, x1 + 0.02, S.UP_LE, S.UP_TE, 'upper')
        sts.append(wing_station(side * ax, le, te, upper_z(ax)))
    if side < 0:
        sts = list(reversed(sts))
    cap_in = V((-side, 0, 0))
    surface(mb, sts, 0.0, S.AIL_HINGE_S, cap0=cap_in if side > 0 else None, cap1=cap_in if side < 0 else None, cap_mat='paint',
            n_box=12, hinge_mat='structure')
    # fixed trailing edge inboard and outboard of the aileron
    for a, b in ((x0, S.AIL_X[0]), (S.AIL_X[1], x1)):
        sel = [s for s in sts if a - 1e-4 <= abs(s.span) <= b + 1e-4]
        if len(sel) >= 2:
            surface(mb, sel, S.AIL_HINGE_S, 1.0, n_aft=4, front_mat='structure')
    # tip cap
    tip = sts[-1] if side > 0 else sts[0]
    # aileron
    am = MeshBuf()
    asel = [s for s in sts if S.AIL_X[0] - 1e-4 <= abs(s.span) <= S.AIL_X[1] + 1e-4]
    surface(am, asel, S.AIL_HINGE_S, 1.0, cap0=V((-1, 0, 0)), cap1=V((1, 0, 0)), cap_mat='paint', n_aft=4, front_mat='structure', inset=0.012)
    hs = [s.point(S.AIL_HINGE_S, True) * 0.5 + s.point(S.AIL_HINGE_S, False) * 0.5 for s in asel]
    hinge_in = hs[0] if side > 0 else hs[-1]
    hinge_out = hs[-1] if side > 0 else hs[0]
    return mb, am, hinge_in, hinge_out


def upper_centre():
    mb = MeshBuf()
    xs = [-S.UP_CENTRE_X, -0.55, -S.UP_CUTOUT_X - 0.03, -S.UP_CUTOUT_X, -0.15, 0.0, 0.15, S.UP_CUTOUT_X, S.UP_CUTOUT_X + 0.03, 0.55, S.UP_CENTRE_X]
    sts = []
    for x in xs:
        cut = abs(x) <= S.UP_CUTOUT_X + 1e-4
        te = S.UP_CUTOUT_TE + (0.03 if abs(x) < 0.2 else 0.0) * (1 - abs(x) / 0.2) if cut else S.UP_TE
        sts.append(wing_station(x, S.UP_LE, te, S.UP_Z))
    surface(mb, sts, 0.0, 0.999, n_box=12, hinge_mat='paint')
    return mb


def lower_panel(side):
    mb = MeshBuf()
    xs = [S.LO_ROOT_X, 0.9, 1.4, S.RACK_X - 0.15, S.RACK_X + 0.15, 2.4, 3.0, S.STRUT_X, 3.8, 4.05, 4.2, 4.32, 4.40, S.LO_TIP_X]
    sts = []
    for ax in xs:
        le, te = tip_round(ax, 4.0, S.LO_TIP_X + 0.02, S.LO_LE, S.LO_TE, 'lower')
        sts.append(wing_station(side * ax, le, te, lower_z(ax)))
    if side < 0:
        sts = list(reversed(sts))
    surface(mb, sts, 0.0, 0.999, cap0=V((-1, 0, 0)) if side > 0 else None, cap1=V((1, 0, 0)) if side < 0 else None,
            cap_mat='paint', n_box=14, hinge_mat='paint')
    return mb


def interplane_struts(mb, side):
    x = side * S.STRUT_X
    zl, zu = lower_z(S.STRUT_X) + 0.06, upper_z(S.STRUT_X) - 0.05
    fl, rl = V((x, S.LO_LE - 0.22, zl)), V((x, S.LO_TE + 0.30, zl - 0.01))
    fu, ru = V((x, S.UP_LE - 0.24, zu)), V((x, S.UP_TE + 0.32, zu - 0.01))
    strut(mb, fl, fu, 0.075, 0.026)
    strut(mb, rl, ru, 0.075, 0.026)
    strut(mb, rl + V((0, 0.02, 0.02)), fu - V((0, 0.06, 0.02)), 0.06, 0.022)     # the N diagonal
    # pitot head on the left strut
    if side < 0:
        cylinder(mb, fu + V((0, -0.05, -0.35)), fu + V((0, 0.30, -0.35)), 0.008, N=6, mat='metal_dark')
    return fl, rl, fu, ru


def cabane(mb):
    for side in (-1, 1):
        for yb, yt in ((0.62, 1.02), (-0.10, 0.22)):
            p0 = V((side * 0.36, yb, fus_top(yb) - 0.01))
            p1 = V((side * 0.56, yt, S.UP_Z - 0.06))
            strut(mb, p0, p1, 0.06, 0.024)
        strut(mb, V((side * 0.36, 0.62, fus_top(0.62) - 0.01)), V((side * 0.56, 0.22, S.UP_Z - 0.06)), 0.05, 0.02)


def fus_top(y):
    return max(p.z for p in fus_ring(y)[:3])


def rigging(mb, side, fl, rl, fu, ru):
    """flying wires (lower root -> upper strut top) and landing wires (upper root -> lower strut foot), doubled."""
    x0l = side * (S.LO_ROOT_X + 0.02)
    roots_lo = [V((x0l, S.LO_LE - 0.25, lower_z(S.LO_ROOT_X) + 0.03)), V((x0l, S.LO_TE + 0.35, lower_z(S.LO_ROOT_X) + 0.03))]
    roots_up = [V((side * 0.56, S.UP_LE - 0.28, S.UP_Z - 0.06)), V((side * 0.56, S.UP_TE + 0.35, S.UP_Z - 0.06))]
    for k, (lo, up) in enumerate(zip(roots_lo, roots_up)):
        top, foot = (fu, fl) if k == 0 else (ru, rl)
        for d in (-0.012, 0.012):
            wire(mb, lo + V((0, d, 0)), top + V((0, d, -0.02)))
        wire(mb, up, foot + V((0, 0, 0.02)))
    # incidence wire in the strut bay plane and drag wire to the nose
    wire(mb, fl + V((0, 0, 0.05)), ru - V((0, 0, 0.05)))
    wire(mb, V((side * 0.40, 1.55, -0.20)), fl + V((0, 0.02, 0.02)))


# ------------------------------------------------------------------------------------------- tail
def stab(side):
    mb = MeshBuf()
    xs = [0.16, 0.45, 0.8, 1.1, 1.3, 1.42, 1.50, 1.55, S.STAB_TIP_X]
    sts = []
    for ax in xs:
        le, te = tip_round(ax, 1.20, S.STAB_TIP_X + 0.01, S.STAB_LE, S.STAB_TE, 'stab')
        sts.append(Station(side * ax, V((side * ax, le, S.STAB_Z)), V((0, -1, 0)), V((0, 0, 1)), max(le - te, 0.04), 0.085, m=0.0))
    if side < 0:
        sts = list(reversed(sts))
    hs = (S.STAB_LE - S.STAB_HINGE) / (S.STAB_LE - S.STAB_TE)
    surface(mb, sts, 0.0, hs, cap0=V((-1, 0, 0)) if side > 0 else None, cap1=V((1, 0, 0)) if side < 0 else None, cap_mat='paint', n_box=8, hinge_mat='structure')
    em = MeshBuf()
    esel = [s for s in sts if abs(s.span) >= 0.30]
    for s in esel:   # hinge chord fraction differs per station near the tip: use the station's own fraction of the fixed hinge line
        pass
    surface(em, esel, hs, 1.0, cap0=V((-1, 0, 0)), cap1=V((1, 0, 0)), cap_mat='paint', n_aft=4, front_mat='structure', inset=0.01)
    # bracing strut from the stab underside to the fuselage bottom (own child mesh: kept out of the stab collider)
    bm = MeshBuf()
    strut(bm, V((side * 0.85, -3.95, S.STAB_Z - 0.03)), V((side * 0.12, -3.80, -0.36)), 0.04, 0.016)
    hinge = [s.point(hs, True) * 0.5 + s.point(hs, False) * 0.5 for s in esel]
    return mb, em, hinge, bm


def fin_rudder():
    fm = MeshBuf()
    zs = [S.FIN_ROOT_Z - 0.05, 0.45, 0.65, 0.85, 1.05, 1.20, 1.30, S.FIN_TOP_Z]
    sts = []
    for z in zs:
        f = (z - S.FIN_ROOT_Z) / (S.FIN_TOP_Z - S.FIN_ROOT_Z)
        le = S.FIN_LE_ROOT + (-4.44 - S.FIN_LE_ROOT) * max(f, 0) ** 1.25
        le = max(min(le, S.FIN_LE_ROOT), S.FIN_HINGE + 0.03)
        sts.append(Station(z, V((0, le, z)), V((0, -1, 0)), V((1, 0, 0)), max(le - S.FIN_HINGE, 0.03), 0.10, m=0.0))
    surface(fm, sts, 0.0, 0.999, cap1=V((0, 0, 1)), cap_mat='paint', n_box=8, hinge_mat='structure')
    rm = MeshBuf()
    rz = [S.RUDDER_BOTTOM_Z, -0.36, -0.25, -0.1, 0.06, 0.4, 0.7, 0.95, 1.12, 1.24, 1.32, 1.36]
    rs = []
    for z in rz:
        span = S.FIN_HINGE - 0.012 - S.RUDDER_TE          # ~0.82 m maximum rudder chord
        if z > 0.40:
            f = min((z - 0.40) / 0.97, 0.995)
            te = S.FIN_HINGE - 0.012 - span * math.sqrt(1 - f * f)
        elif z < 0.06:
            f = min((0.06 - z) / 0.48, 0.995)
            te = S.FIN_HINGE - 0.012 - span * math.sqrt(1 - f * f)
        else:
            te = S.RUDDER_TE
        rs.append(Station(z, V((0, S.FIN_HINGE - 0.012, z)), V((0, -1, 0)), V((1, 0, 0)), max(S.FIN_HINGE - 0.012 - te, 0.05), 0.09, m=0.0))
    surface(rm, rs, 0.0, 0.999, cap0=V((0, 0, -1)), cap1=V((0, 0, 1)), cap_mat='paint', n_box=8, hinge_mat='structure')
    return fm, rm


# ------------------------------------------------------------------------------------------- undercarriage, hook
def wheel_mesh(c, r, w, hub_mat='paint'):
    mb = MeshBuf()
    ax = V((1, 0, 0))
    rings = []
    for k in range(9):
        a = math.pi * k / 8
        rr = r - 0.06 + 0.06 * math.sin(a)
        dx = -math.cos(a) * w / 2
        rings.append(circle_pts(V(c) + ax * dx, ax, rr, 24, ref=V((0, 0, 1))))
    loft(mb, rings, 'rubber', closed=True)
    for d in (-1, 1):
        rim = circle_pts(V(c) + ax * (d * w * 0.48), ax, r - 0.06, 24, ref=V((0, 0, 1)))
        fan_cap(mb, rim, V(c) + ax * (d * w * 0.60), hub_mat, ax * d, uvfunc=lambda p: (p.y * 2, p.z * 2))
    return mb


def main_gear(side):
    ax = V((side * S.MAIN_AXLE[0], S.MAIN_AXLE[1], S.MAIN_AXLE[2]))
    st = MeshBuf()
    strut(st, V((side * 0.40, 1.02, -0.60)), ax + V((-side * 0.05, 0.02, 0.10)), 0.085, 0.05)       # oleo leg (front)
    strut(st, V((side * 0.38, 0.18, -0.60)), ax + V((-side * 0.05, -0.02, 0.06)), 0.05, 0.03)        # radius rod
    cylinder(st, ax + V((-side * 0.07, 0, 0)), V((0, ax.y, ax.z + 0.02)), 0.022, N=8, mat='metal_dark')  # split axle / spreader
    cylinder(st, ax + V((side * 0.0, 0, 0)), ax + V((-side * 0.09, 0, 0)), 0.03, N=8, mat='metal_dark')
    wh = wheel_mesh(ax, S.WHEEL_R, S.WHEEL_W)
    return st, wh, ax


def tail_gear():
    ax = V(S.TAIL_AXLE)
    st = MeshBuf()
    top = V((0, ax.y + 0.10, -0.30))
    for d in (-1, 1):
        cylinder(st, top + V((d * 0.04, 0, 0)), ax + V((d * 0.04, 0, 0)), 0.014, N=6, mat='metal_dark')
    cylinder(st, top + V((0, 0, 0.04)), top - V((0, 0, 0.02)), 0.03, N=8, mat='metal_dark')
    wh = wheel_mesh(ax, S.TAILWHEEL_R, 0.06, hub_mat='metal_dark')
    return st, wh, ax


def hook_mesh():
    """tail hook in its STOWED pose (pivot at HOOK_PIVOT, bar pointing aft, tip up by HOOK_STOW_UP)."""
    mb = MeshBuf()
    p0 = V(S.HOOK_PIVOT)
    a = math.radians(S.HOOK_STOW_UP)
    d = V((0, -math.cos(a), math.sin(a)))
    p1 = p0 + d * S.HOOK_LEN
    cylinder(mb, p0, p1 - d * 0.10, 0.022, N=8, mat='metal_dark')
    box(mb, p1 - d * 0.05 + V((0, 0, -0.025)), (0.06, 0.12, 0.07), 'hookyellow')
    for k in (-1, 1):
        cylinder(mb, p0 + V((k * 0.05, 0.02, 0)), p0 + d * 0.25 + V((k * 0.03, 0, 0)), 0.01, N=6, mat='metal_dark')
    return mb


# ------------------------------------------------------------------------------------------- propeller
def build_prop():
    """two-blade fixed-pitch wooden propeller + pointed spinner; blade objects with local +Z (Blender) = radial."""
    parts = []
    hub = V((0, S.PROP_Y, 0))
    sp = MeshBuf()
    rings = []
    for k in range(9):
        f = k / 8
        y = S.PROP_Y - 0.10 + (S.SPINNER_TIP_Y - S.PROP_Y + 0.10) * f
        r = S.SPINNER_R * math.sqrt(max(1 - f ** 1.7, 0.0)) if k < 8 else 0.004
        rings.append(circle_pts(V((0, y, 0)), V((0, 1, 0)), max(r, 0.004), 24, ref=V((0, 0, 1))))
    loft(sp, rings, 'spinner')
    fan_cap(sp, rings[0], V((0, S.PROP_Y - 0.10, 0)), 'spinner', V((0, -1, 0)))
    parts.append(Part('prop_hub', 'prop', hub, sp, info=dict(kind='prop_hub', note='spin axis = Unity +Z; spinner + blade roots')))
    for k, sgn in ((1, 1), (2, -1)):
        bm = MeshBuf()
        rad = V((0, 0, sgn))
        tang = V((sgn, 0, 0))            # rotation direction (clockwise seen from behind for blade 1 at the top)
        stations = []
        for i in range(13):
            f = 0.10 + 0.90 * i / 12
            r = f * S.PROP_R
            chord = 0.20 * math.sin(math.pi * min(f * 1.05, 1.0)) ** 0.55 + 0.05
            if f > 0.93:
                chord *= max(0.25, 1 - (f - 0.93) / 0.07 * 0.75)
            twist = math.radians(10 + 34 * (0.18 / f) ** 0.9 if f > 0.12 else 55)
            thick = (0.055 if f < 0.25 else 0.11 * chord / 0.25 + 0.012)
            c = hub + rad * r
            fwd = V((0, 1, 0))
            cdir = (tang * math.cos(twist) - fwd * math.sin(twist)).normalized()    # LE -> TE
            up = cdir.cross(rad).normalized()
            if up.dot(fwd) < 0:
                up = -up
            stations.append(Station(r, c - cdir * chord * 0.35, cdir, up, chord, min(thick / max(chord, 0.05), 0.35), m=0.04))
        surface(bm, stations, 0.0, 0.999, cap0=-rad, cap1=rad, cap_mat='prop', n_box=8, hinge_mat='prop', uv=False)
        for f in bm.faces:
            f['mat'] = 'prop'
        tipm = MeshBuf()
        parts.append(Part(f'prop_blade_{k}', 'prop_hub', hub, bm, frame=frame_x(V((1, 0, 0)) * sgn, rad),
                          info=dict(kind='prop_blade', note='local +Y (Unity) = radial, +Z = forward')))
    return parts


# ------------------------------------------------------------------------------------------- guns
def gun_meshes():
    """two Vickers Mk III: breech in the cockpit, barrel jacket under the decking, blast tube in the trough."""
    out = MeshBuf()
    for side in (-1, 1):
        x = side * S.GUN_X
        z = S.GUN_Z - 0.02
        box(out, (x, S.GUN_BREECH_Y + 0.15, S.GUN_Z + 0.005), (0.07, 0.30, 0.09), 'gunmetal')     # receiver (rear end into the cockpit, above the lower panel)
        cylinder(out, V((x, S.GUN_BREECH_Y + 0.30, z)), V((x, S.GUN_BODY_Y, z)), 0.036, N=12, mat='gunmetal')  # barrel jacket
        cylinder(out, V((x, S.GUN_BODY_Y, z)), V((x, S.GUN_TROUGH_END_Y - 0.02, z + 0.012)), 0.017, N=8, mat='metal_dark')  # blast tube
        cylinder(out, V((x, S.GUN_TROUGH_END_Y - 0.06, z + 0.011)), V((x, S.GUN_TROUGH_END_Y, z + 0.013)), 0.024, N=8, mat='metal_dark')
    return out


# ------------------------------------------------------------------------------------------- collect
def build_exterior():
    parts = []
    fus = build_fuselage()
    add_cowl_details(fus['fus_engine'])
    fus['fus_engine'].extend(build_radiator())
    fus['fus_engine'].extend(gun_meshes())
    parts.append(Part('fus_center', 'NIMROD1_root', (0, -0.75, 0), fus['NIMROD1']))
    parts.append(Part('fus_engine', 'fus_center', (0, 1.10, 0), fus['fus_engine']))
    parts.append(Part('fus_rear', 'fus_center', (0, -2.80, 0), fus['fus_rear']))
    # upper wing
    uc = upper_centre()
    cb = MeshBuf()
    cabane(cb)
    parts.append(Part('wing_upper_C', 'fus_center', (0, (S.UP_LE + S.UP_TE) / 2, S.UP_Z), uc))
    parts.append(Part('cabane', 'wing_upper_C', (0, 0.45, 0.75), cb, info=dict(kind='struts', note='not in the part collider')))
    for side, L in ((-1, 'L'), (1, 'R')):
        wm, am, hin, hout = upper_panel(side)
        lm = lower_panel(side)
        sm_ = MeshBuf(); rg = MeshBuf()
        fl, rl, fu, ru = interplane_struts(sm_, side)
        rigging(rg, side, fl, rl, fu, ru)
        parts.append(Part(f'wing_upper_{L}', 'wing_upper_C', (side * 2.9, 0.55, upper_z(2.9)), wm))
        axis = (hout - hin).normalized() * side
        parts.append(Part(f'aileron_{L}', f'wing_upper_{L}', hin, am, frame=frame_x(axis), info=dict(kind='control', hinge_axis=tuple(axis))))
        parts.append(Part(f'wing_lower_{L}', 'fus_center', (side * 2.4, -0.30, lower_z(2.4)), lm))
        parts.append(Part(f'struts_{L}', f'wing_upper_{L}', (side * S.STRUT_X, 0.30, 0.25), sm_, info=dict(kind='struts', note='interplane N-strut; not in the part collider')))
        parts.append(Part(f'rigging_{L}', f'wing_lower_{L}', (side * 1.9, 0.0, 0.2), rg, info=dict(kind='wires', note='flying/landing wires; not in the part collider')))
        sm, em, eh, bm = stab(side)
        parts.append(Part(f'stab_{L}', 'fus_rear', (side * 0.8, -4.0, S.STAB_Z), sm))
        parts.append(Part(f'stab_strut_{L}', f'stab_{L}', (side * 0.5, -3.9, -0.1), bm, info=dict(kind='struts')))
        eax = (eh[-1] - eh[0]).normalized()
        if eax.x < 0:
            eax = -eax
        parts.append(Part(f'elevator_{L}', f'stab_{L}', eh[0] if side > 0 else eh[-1], em, frame=frame_x(eax), info=dict(kind='control', hinge_axis=tuple(eax))))
        st, wh, axle = main_gear(side)
        parts.append(Part(f'gear_main_{L}_strut', 'fus_center', V((side * 0.40, 1.02, -0.60)), st))
        parts.append(Part(f'gear_main_{L}_wheel', f'gear_main_{L}_strut', axle, wh, info=dict(kind='wheel', radius=S.WHEEL_R)))
        parts.append(Part(f'hp_bomb_{L}', f'wing_lower_{L}', (side * S.RACK_X, S.RACK_Y, lower_z(S.RACK_X) - 0.075),
                          info=dict(kind='hardpoint', note='Cooper x2 rack mount (stock mount convention: origin at the rack top)')))
        parts.append(Part(f'navlight_{L}', f'wing_upper_{L}', (side * (S.UP_TIP_X - 0.06), 0.62, upper_z(S.UP_TIP_X) + 0.01),
                          info=dict(kind='navlight')))
        parts.append(Part(f'muzzle_gun_{L}', 'fus_engine', (side * S.GUN_X, S.MUZZLE_Y, S.GUN_Z), frame=Quaternion(),
                          info=dict(kind='muzzle', note='bullet origin AHEAD of the prop disc (synchroniser); +Z Unity = forward')))
        parts.append(Part(f'flash_gun_{L}', 'fus_engine', (side * S.GUN_X, S.GUN_TROUGH_END_Y, S.GUN_Z), info=dict(kind='muzzle_flash')))
    fm, rm = fin_rudder()
    parts.append(Part('fin', 'fus_rear', (0, -4.0, 0.7), fm))
    rax = V((0, 0, 1))
    parts.append(Part('rudder', 'fin', (0, S.FIN_HINGE, 0.45), rm, frame=frame_x(rax, V((0, -1, 0))), info=dict(kind='control', hinge_axis=(0, 0, 1))))
    st, wh, axle = tail_gear()
    parts.append(Part('gear_tail_strut', 'fus_rear', V((0, axle.y + 0.10, -0.30)), st))
    parts.append(Part('gear_tail_wheel', 'gear_tail_strut', axle, wh, info=dict(kind='wheel', radius=S.TAILWHEEL_R)))
    parts.append(Part('tailhook', 'fus_center', S.HOOK_PIVOT, hook_mesh(), info=dict(kind='tailhook', length=S.HOOK_LEN, stowed_up_deg=S.HOOK_STOW_UP,
                      deployed_deg=S.HOOK_DEPLOY, note='hinge at origin; angle 0 = straight aft; stowed = +stow (tip up); mesh modelled stowed')))
    parts.append(Part('hp_tailhook', 'fus_center', S.HOOK_PIVOT, info=dict(kind='hardpoint')))
    parts.append(Part('exhaust_point', 'fus_engine', (0.47, 1.0, 0.07), info=dict(kind='ir_source')))
    parts += build_prop()
    parts.insert(0, Part('prop', 'fus_engine', (0, S.PROP_Y, 0), None, info=dict(kind='prop_part')))
    return parts


# ------------------------------------------------------------------------------------------- 20 lb Cooper bomb + light rack
def cooper_parts():
    """our own 20 lb Cooper: 0.62 m finned teardrop, 0.127 m body; pivot = suspension lug (top centre), nose +Y.
    Built at an out-of-the-way spot under the root; the Unity builder takes the meshes for the bomb / mount prefabs and
    deletes these objects from the aircraft."""
    base = V((0.0, -6.5, -2.5))
    bm = MeshBuf()
    prof = [(0.30, 0.0), (0.28, 0.030), (0.24, 0.050), (0.17, 0.062), (0.08, 0.0635), (0.0, 0.060), (-0.10, 0.050),
            (-0.18, 0.036), (-0.24, 0.024), (-0.27, 0.018)]
    rings = [circle_pts(base + V((0, y, -0.064)), V((0, 1, 0)), max(r, 0.002), 16, ref=V((0, 0, 1))) for y, r in prof]
    loft(bm, rings, 'bomb')
    fan_cap(bm, rings[0], base + V((0, 0.305, -0.064)), 'bomb', V((0, 1, 0)))
    fan_cap(bm, rings[-1], base + V((0, -0.27, -0.064)), 'bomb', V((0, -1, 0)))
    band = [circle_pts(base + V((0, y, -0.064)), V((0, 1, 0)), r + 0.0015, 16, ref=V((0, 0, 1))) for y, r in ((0.20, 0.0605), (0.16, 0.0625))]
    loft(bm, band, 'bombband')
    # box tail: 4 fins + ring
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = V((math.cos(a), 0, math.sin(a)))
        c = base + V((0, -0.26, -0.064))
        q = [c + d * 0.015, c + d * 0.075 + V((0, 0.02, 0)), c + d * 0.075 + V((0, -0.06, 0)), c + d * 0.02 + V((0, -0.06, 0))]
        oriented_quad(bm, q, 'bomb', d.cross(V((0, 1, 0))))
        oriented_quad(bm, q, 'bomb', -d.cross(V((0, 1, 0))))
    box(bm, base + V((0, 0.02, -0.002)), (0.012, 0.03, 0.006), 'metal_dark')     # lug
    rm = MeshBuf()
    rb = V((3.0, -6.5, -2.5))
    box(rm, rb + V((0, 0, -0.012)), (0.40, 0.10, 0.024), 'metal_dark')
    for s in (-1, 1):
        box(rm, rb + V((s * 0.16, 0, -0.035)), (0.03, 0.08, 0.03), 'metal_dark')
        box(rm, rb + V((s * 0.16, 0.05, -0.065)), (0.10, 0.012, 0.012), 'metal_dark')   # sway braces
    return [Part('cooper_bomb', 'NIMROD1_root', base, bm, info=dict(kind='store_mesh', note='bomb prefab mesh; removed from the aircraft')),
            Part('cooper_rack', 'NIMROD1_root', rb, rm, info=dict(kind='store_mesh', note='rack mesh for the Cooper x2 mount; bombs at x +-0.16, y -0.035 (Unity)'))]
