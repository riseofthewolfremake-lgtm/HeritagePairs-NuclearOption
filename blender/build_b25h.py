"""Procedural B-25H Mitchell model for the Nuclear Option mod.

Run (headless):
  blender --background --factory-startup --python blender/build_b25h.py -- --out assets/model/b25h.blend

Convention (Blender): nose +Y, up +Z, pilot's right wing +X, metres.
All geometry is first defined in a "design" frame (wing root chord plane at z=0, x=0 on the
centreline) and then shifted in Y so that B25H_root (world origin) sits at 30% of the wing MAC.
Everything here is our own procedural geometry; no game data is used.
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector, Matrix

# ----------------------------------------------------------------------------- parameters
SPAN_HALF = 10.30          # 20.60 m span
WING_KINK_X = 3.75         # gull break, just outboard of the nacelle
DIHEDRAL_IN = math.radians(4.5)
DIHEDRAL_OUT = math.radians(-0.5)
ROOT_LE_Y = 1.17
ROOT_CHORD = 3.60
KINK_CHORD = 3.42
TIP_CHORD = 1.30
OUTER_LE_SWEEP = 0.50      # LE moves aft by this much from kink to tip
TIP_ROUND = 0.70           # length of the rounded tip
NAC_X = 3.05               # nacelle / thrust line
NAC_Z = 0.08
PROP_R = 1.93              # 3.86 m diameter
GROUND_Z = -2.45           # wheel contact plane (design z == world z)
MAIN_WHEEL_R = 0.595
NOSE_WHEEL_R = 0.38
STAB_Z = 0.70
STAB_HALF = 3.35
FIN_ZB, FIN_ZT = 0.10, 2.53

GAP = 0.012                # chordwise gap in front of control surfaces
SPAN_GAP = 0.02            # spanwise gap at ends of control surfaces

MATS = {
    'paint_olive':     (0.23, 0.25, 0.13, 1.0),
    'paint_grey':      (0.47, 0.48, 0.48, 1.0),
    'metal_dark':      (0.07, 0.07, 0.075, 1.0),
    'rubber':          (0.025, 0.025, 0.025, 1.0),
    'glass':           (0.55, 0.70, 0.80, 1.0),
    'prop_black':      (0.02, 0.02, 0.02, 1.0),
    'prop_tip_yellow': (0.90, 0.72, 0.05, 1.0),
}

# ----------------------------------------------------------------------------- math helpers
def pchip(xs, ys):
    """Monotone cubic (Fritsch-Carlson) interpolator; xs strictly increasing."""
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1 = 2 * h[i] + h[i - 1]
            w2 = h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = 0
        while xs[i + 1] < x:
            i += 1
        t = (x - xs[i]) / h[i]
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1
        h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2
        h11 = t ** 3 - t ** 2
        return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]
    return f


def table_interp(keys):
    """keys: list of tuples (s, v1, v2, ...) in any order -> function s -> tuple."""
    keys = sorted(keys, key=lambda k: k[0])
    xs = [k[0] for k in keys]
    fs = [pchip(xs, [k[j] for k in keys]) for j in range(1, len(keys[0]))]
    return lambda s: tuple(fn(s) for fn in fs)


def lerp(a, b, t):
    return a + (b - a) * t


def basis_for(d):
    d = Vector(d).normalized()
    ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(ref).normalized()
    v = d.cross(u).normalized()
    return d, u, v

# ----------------------------------------------------------------------------- mesh pieces
class Piece:
    def __init__(self, verts, faces, mat):
        self.verts = [Vector(v) for v in verts]
        self.faces = faces
        self.mat = mat


def loft(rings, mat, cap_start=True, cap_end=True, wrap=False):
    """rings: list of point lists. A ring of length 1 is a pole. All other rings share n."""
    verts, faces, idx = [], [], []
    n = max(len(r) for r in rings)
    for r in rings:
        idx.append(list(range(len(verts), len(verts) + len(r))))
        verts.extend(Vector(p) for p in r)
    pairs = list(zip(range(len(rings) - 1), range(1, len(rings))))
    if wrap:
        pairs.append((len(rings) - 1, 0))
    for i, k in pairs:
        a, b = idx[i], idx[k]
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for j in range(n):
                faces.append((a[0], b[(j + 1) % n], b[j]))
        elif len(b) == 1:
            for j in range(n):
                faces.append((a[j], a[(j + 1) % n], b[0]))
        else:
            for j in range(n):
                faces.append((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    if not wrap:
        for ring_i, do in ((0, cap_start), (len(rings) - 1, cap_end)):
            r = idx[ring_i]
            if do and len(r) > 2:
                c = Vector((0, 0, 0))
                for vi in r:
                    c += verts[vi]
                c /= len(r)
                ci = len(verts)
                verts.append(c)
                for j in range(len(r)):
                    faces.append((r[j], r[(j + 1) % len(r)], ci))
    return Piece(verts, faces, mat)


def lathe(origin, axis, profile, seg, mat, cap_start=True, cap_end=True, phase=0.0):
    """profile: list of (radius, t along axis). radius 0 -> pole."""
    d, u, v = basis_for(axis)
    o = Vector(origin)
    rings = []
    for r, t in profile:
        c = o + d * t
        if r <= 1e-6:
            rings.append([c])
        else:
            rings.append([c + (u * math.cos(phase + 2 * math.pi * k / seg) + v * math.sin(phase + 2 * math.pi * k / seg)) * r
                          for k in range(seg)])
    return loft(rings, mat, cap_start, cap_end)


def cylinder(p0, p1, r, seg, mat, r1=None):
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    return lathe(p0, p1 - p0, [(r, 0.0), (r if r1 is None else r1, L)], seg, mat)


def ellipsoid(center, radii, mat, seg=20, rings_n=12, axis_order='y'):
    """Ellipsoid with poles along Y (default) -- good for fairings and blisters."""
    cx, cy, cz = center
    rx, ry, rz = radii
    rings = []
    for i in range(rings_n + 1):
        th = math.pi * i / rings_n
        yy = cy + ry * math.cos(th)
        s = math.sin(th)
        if i == 0 or i == rings_n:
            rings.append([(cx, yy, cz)])
        else:
            rings.append([(cx + rx * s * math.cos(2 * math.pi * k / seg), yy, cz + rz * s * math.sin(2 * math.pi * k / seg))
                          for k in range(seg)])
    return loft(rings, mat)


def dome_z(center, r_xy, h, mat, seg=32, rings_n=10, base_extra=0.0):
    """Upward dome (poles along +Z), closed with a flat base at center z - base_extra."""
    cx, cy, cz = center
    rings = []
    for i in range(rings_n + 1):
        th = (math.pi / 2) * i / rings_n
        rr = r_xy * math.cos(th)
        zz = cz + h * math.sin(th)
        if i == rings_n:
            rings.append([(cx, cy, zz)])
        else:
            rings.append([(cx + rr * math.cos(2 * math.pi * k / seg), cy + rr * math.sin(2 * math.pi * k / seg), zz)
                          for k in range(seg)])
    if base_extra > 0:
        rings.insert(0, [(cx + r_xy * math.cos(2 * math.pi * k / seg), cy + r_xy * math.sin(2 * math.pi * k / seg), cz - base_extra)
                         for k in range(seg)])
    return loft(rings, mat)


def superellipse_ring(xc, y, zc, hw, ht, hb, pt, pb, n):
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        c, s = math.cos(t), math.sin(t)
        p = pt if s >= 0 else pb
        x = hw * math.copysign(abs(c) ** (2 / p), c)
        z = zc + (ht if s >= 0 else hb) * math.copysign(abs(s) ** (2 / p), s)
        pts.append((xc + x, y, z))
    return pts

# ----------------------------------------------------------------------------- airfoils
def naca_thick(xc, t):
    return 5 * t * (0.2969 * math.sqrt(max(xc, 0)) - 0.1260 * xc - 0.3516 * xc ** 2 + 0.2843 * xc ** 3 - 0.1015 * xc ** 4)


def naca_camber(xc, m, p=0.4):
    if m == 0:
        return 0.0
    if xc < p:
        return m / p ** 2 * (2 * p * xc - xc ** 2)
    return m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * xc - xc ** 2)


def cosine_samples(a, b, n):
    return [a + (b - a) * (1 - math.cos(math.pi * i / (n - 1))) / 2 for i in range(n)]


XC_MASTER = cosine_samples(0.0, 1.0, 19)


def sec_point(fr, xc, side):
    le, chord, tc, m, cdir, tdir = fr
    z = naca_camber(xc, m) + side * naca_thick(xc, tc)
    return le + cdir * (xc * chord) + tdir * (z * chord)


def main_ring(fr, cmax):
    xs = [min(x, cmax) for x in XC_MASTER]
    up = [sec_point(fr, x, +1) for x in reversed(xs)]
    lo = [sec_point(fr, x, -1) for x in xs[1:]]
    return up + lo


def ctrl_ring(fr, c0, n=8):
    xs = cosine_samples(c0, 1.0, n)
    xs = [c0 + (x - c0) for x in xs]
    up = [sec_point(fr, x, +1) for x in reversed(xs)]
    lo = [sec_point(fr, x, -1) for x in xs]
    return up + lo


def hinge_point(fr, c):
    le, chord, tc, m, cdir, tdir = fr
    return le + cdir * (c * chord) + tdir * (naca_camber(c, m) * chord)

# ----------------------------------------------------------------------------- wing
def wing_plane_z(x):
    x = abs(x)
    if x <= WING_KINK_X:
        return x * math.tan(DIHEDRAL_IN)
    return WING_KINK_X * math.tan(DIHEDRAL_IN) + (x - WING_KINK_X) * math.tan(DIHEDRAL_OUT)


def wing_planform(x):
    """returns (LE y, chord) for |x| without tip rounding"""
    x = abs(x)
    if x <= WING_KINK_X:
        t = x / WING_KINK_X
        return ROOT_LE_Y - 0.015 * x, lerp(ROOT_CHORD, KINK_CHORD, t)
    t = (x - WING_KINK_X) / (SPAN_HALF - WING_KINK_X)
    le_k = ROOT_LE_Y - 0.015 * WING_KINK_X
    return le_k - OUTER_LE_SWEEP * t, lerp(KINK_CHORD, TIP_CHORD, t)


def wing_frame(x, side):
    le_y, c = wing_planform(x)
    ax = abs(x)
    tc = pchip([0, WING_KINK_X, SPAN_HALF - TIP_ROUND, SPAN_HALF], [0.17, 0.15, 0.10, 0.09])(ax)
    m = lerp(0.02, 0.015, ax / SPAN_HALF)
    r0 = SPAN_HALF - TIP_ROUND
    if ax > r0:
        u = min((ax - r0) / TIP_ROUND, 1.0)
        f = max(math.sqrt(max(1 - u * u, 0)), 0.035)
        pivot = le_y - 0.40 * c
        c2 = c * f
        le_y = pivot + 0.40 * c2
        c = c2
        tc = tc * (0.6 + 0.4 * f)
    le = Vector((side * ax, le_y, wing_plane_z(ax)))
    # local "up" of the section follows the dihedral of the panel
    dih = DIHEDRAL_IN if ax <= WING_KINK_X else DIHEDRAL_OUT
    tdir = Vector((-side * math.sin(dih), 0, math.cos(dih)))
    return (le, c, tc, m, Vector((0, -1, 0)), tdir)


FLAP_IN = (0.75, 2.40, 0.72)    # (x0, x1, hinge fraction)
FLAP_OUT = (3.80, 6.30, 0.72)
AILERON = (6.35, 9.60, 0.75)


def wing_stations():
    """list of (x, cmax) with duplicated stations at cut-out edges"""
    regions = [(0.25, FLAP_IN[0], 1.0), FLAP_IN[:2] + (FLAP_IN[2],), (FLAP_IN[1], FLAP_OUT[0], 1.0),
               FLAP_OUT[:2] + (FLAP_OUT[2],), (FLAP_OUT[1], AILERON[0], 1.0), AILERON[:2] + (AILERON[2],),
               (AILERON[1], SPAN_HALF, 1.0)]
    st = []
    for (a, b, cm) in regions:
        if b == SPAN_HALF:   # tip: dense, cosine towards tip
            n = 10
            xs = [a + (b - a) * math.sin(0.5 * math.pi * i / (n - 1)) for i in range(n)]
        else:
            n = max(2, int(math.ceil((b - a) / 0.45)) + 1)
            xs = [a + (b - a) * i / (n - 1) for i in range(n)]
            if a < WING_KINK_X < b:
                xs = sorted(set(xs + [WING_KINK_X]))
        for x in xs:
            st.append((x, cm))
    return st


def build_wing(side):
    rings = []
    for x, cm in wing_stations():
        fr = wing_frame(x, side)
        if x >= SPAN_HALF - 1e-6:
            rings.append([sec_point(fr, 0.4, 0)])
        else:
            rings.append(main_ring(fr, cm))
    return [loft(rings, 'paint_olive')]


def build_ctrl_wing(side, spec):
    x0, x1, h = spec
    xa, xb = x0 + SPAN_GAP, x1 - SPAN_GAP
    n = max(3, int(math.ceil((xb - xa) / 0.4)) + 1)
    xs = [xa + (xb - xa) * i / (n - 1) for i in range(n)]
    if xa < WING_KINK_X < xb:
        xs = sorted(set(xs + [WING_KINK_X]))
    rings = [ctrl_ring(wing_frame(x, side), h + GAP / wing_planform(x)[1]) for x in xs]
    pa = hinge_point(wing_frame(xa, side), h + GAP / wing_planform(xa)[1])
    pb = hinge_point(wing_frame(xb, side), h + GAP / wing_planform(xb)[1])
    return [loft(rings, 'paint_olive')], pa, pb

# ----------------------------------------------------------------------------- tail
def stab_frame(x):
    ax = abs(x)
    t = ax / STAB_HALF
    le_y = lerp(-7.25, -7.45, t)
    c = lerp(1.85, 1.45, t)
    return (Vector((x, le_y, STAB_Z)), c, 0.11, 0.0, Vector((0, -1, 0)), Vector((0, 0, 1)))


ELEV = (0.32, 3.25, 0.68)


def build_stab():
    st = []
    xs_regions = [(-STAB_HALF, -ELEV[1], 1.0), (-ELEV[1], -ELEV[0], ELEV[2]), (-ELEV[0], ELEV[0], 1.0),
                  (ELEV[0], ELEV[1], ELEV[2]), (ELEV[1], STAB_HALF, 1.0)]
    for a, b, cm in xs_regions:
        n = max(2, int(math.ceil((b - a) / 0.5)) + 1)
        for i in range(n):
            st.append((a + (b - a) * i / (n - 1), cm))
    rings = [main_ring(stab_frame(x), cm) for x, cm in st]
    return [loft(rings, 'paint_olive')]


def build_elevator(side):
    x0, x1, h = ELEV
    xa, xb = x0 + SPAN_GAP, x1 - SPAN_GAP
    xs = [side * (xa + (xb - xa) * i / 6) for i in range(7)]
    rings = [ctrl_ring(stab_frame(x), h + GAP / stab_frame(x)[1]) for x in xs]
    pa = hinge_point(stab_frame(side * xa), h + GAP / stab_frame(xa)[1])
    pb = hinge_point(stab_frame(side * xb), h + GAP / stab_frame(xb)[1])
    return [loft(rings, 'paint_olive')], pa, pb


FIN_LE_MID = -7.60
FIN_CHORD = 1.50
RUDDER_HINGE_Y = -8.48
RUDDER_Z = (0.28, 2.33)


def fin_frame(z, side):
    zb, zt = FIN_ZB, FIN_ZT
    le_y = FIN_LE_MID - 0.04 * (z - STAB_Z)          # slight LE sweep
    c = FIN_CHORD
    pivot = le_y - 0.48 * c
    f = 1.0
    rb, rt = 0.40, 0.55
    if z < zb + rb:
        u = (zb + rb - z) / rb
        f = math.sqrt(max(1 - u * u, 0))
    elif z > zt - rt:
        u = (z - (zt - rt)) / rt
        f = math.sqrt(max(1 - u * u, 0))
    f = max(f, 0.03)
    c2 = c * f
    le_y = pivot + 0.48 * c2
    return (Vector((side * STAB_HALF, le_y, z)), c2, 0.105, 0.0, Vector((0, -1, 0)), Vector((1, 0, 0)))


def fin_cmax(fr):
    le, c = fr[0], fr[1]
    return min(1.0, (le.y - RUDDER_HINGE_Y) / c)


def fin_zs():
    zs = []
    zb, zt = FIN_ZB, FIN_ZT
    lo = [zb + 0.40 * (1 - math.cos(0.5 * math.pi * i / 5)) for i in range(6)]
    hi = [zt - 0.55 * (1 - math.cos(0.5 * math.pi * i / 6)) for i in range(7)][::-1]
    mid = [lerp(zb + 0.40, zt - 0.55, i / 8) for i in range(1, 8)]
    zs = sorted(set([round(z, 5) for z in lo + mid + hi]))
    return zs


def build_fin(side):
    st = []
    zs = fin_zs()
    za, zb_ = RUDDER_Z
    allz = sorted(set(zs + [za, zb_]))
    for z in allz:
        if z < za or z > zb_:
            st.append((z, 1.0))
        else:
            if z == za:
                st.append((z, 1.0))
            st.append((z, fin_cmax(fin_frame(z, side))))
            if z == zb_:
                st.append((z, 1.0))
    rings = []
    for z, cm in st:
        fr = fin_frame(z, side)
        if abs(z - FIN_ZB) < 1e-6 or abs(z - FIN_ZT) < 1e-6:
            rings.append([sec_point(fr, 0.5, 0)])
        else:
            rings.append(main_ring(fr, cm))
    return [loft(rings, 'paint_olive')]


def build_rudder(side):
    za, zb = RUDDER_Z[0] + SPAN_GAP, RUDDER_Z[1] - SPAN_GAP
    zs = [lerp(za, zb, i / 9) for i in range(10)]
    rings = []
    for z in zs:
        fr = fin_frame(z, side)
        rings.append(ctrl_ring(fr, fin_cmax(fr) + GAP / fr[1]))
    pa = Vector((side * STAB_HALF, RUDDER_HINGE_Y - GAP, za))
    pb = Vector((side * STAB_HALF, RUDDER_HINGE_Y - GAP, zb))
    return [loft(rings, 'paint_olive')], pa, pb

# ----------------------------------------------------------------------------- fuselage
FUS_KEYS = [  # y, half width, top z, bottom z, p_top, p_bot
    (6.15, 0.02, -0.08, -0.16, 2.0, 2.0),
    (6.12, 0.18, 0.02, -0.30, 2.0, 2.0),
    (6.00, 0.34, 0.15, -0.50, 2.1, 2.2),
    (5.75, 0.48, 0.28, -0.70, 2.2, 2.5),
    (5.30, 0.60, 0.40, -0.88, 2.4, 2.8),
    (4.70, 0.66, 0.48, -0.97, 2.6, 3.2),
    (4.00, 0.69, 0.55, -1.01, 2.8, 3.4),
    (3.00, 0.70, 0.66, -1.03, 2.8, 3.5),
    (2.00, 0.70, 0.82, -1.03, 2.8, 3.5),
    (1.00, 0.70, 0.89, -1.03, 2.8, 3.5),
    (-1.0, 0.70, 0.90, -1.03, 2.8, 3.5),
    (-3.0, 0.68, 0.89, -0.98, 2.8, 3.3),
    (-4.8, 0.61, 0.87, -0.80, 2.7, 3.0),
    (-6.5, 0.47, 0.84, -0.45, 2.5, 2.7),
    (-7.8, 0.34, 0.80, -0.08, 2.3, 2.4),
    (-8.6, 0.27, 0.74, 0.12, 2.2, 2.2),
    (-9.0, 0.19, 0.64, 0.24, 2.0, 2.0),
    (-9.10, 0.02, 0.48, 0.40, 2.0, 2.0),
]
FUS = table_interp(FUS_KEYS)
FUS_NOSE_Y, FUS_TAIL_Y = 6.155, -9.105
FUS_N = 48


def fus_section(y):
    hw, top, bot, pt, pb = FUS(y)
    zc = 0.5 * (top + bot)
    return hw, top, bot, pt, pb, zc


def fus_bottom_z(y, x):
    hw, top, bot, pt, pb, zc = fus_section(y)
    hb = zc - bot
    u = min(abs(x) / hw, 1.0)
    return zc - hb * (1 - u ** pb) ** (1 / pb)


def fus_top_z(y, x=0.0):
    hw, top, bot, pt, pb, zc = fus_section(y)
    ht = top - zc
    u = min(abs(x) / hw, 1.0)
    return zc + ht * (1 - u ** pt) ** (1 / pt)


def fus_half_width(y):
    return fus_section(y)[0]


def build_fuselage():
    ys = []
    # dense at both tips, ~0.25 m in the middle
    for i in range(10):
        ys.append(FUS_NOSE_Y - 0.01 - 0.9 * (1 - math.cos(0.5 * math.pi * i / 9)))
    y = ys[-1] - 0.25
    while y > -8.5:
        ys.append(y)
        y -= 0.27
    for i in range(8):
        ys.append(-8.5 - 0.59 * math.sin(0.5 * math.pi * (i + 1) / 8))
    ys = sorted(set(round(v, 4) for v in ys), reverse=True)
    rings = [[(0.0, FUS_NOSE_Y, -0.12)]]
    for yv in ys:
        hw, top, bot, pt, pb, zc = fus_section(yv)
        rings.append(superellipse_ring(0, yv, zc, hw, top - zc, zc - bot, pt, pb, FUS_N))
    rings.append([(0.0, FUS_TAIL_Y, 0.44)])
    pieces = [loft(rings, 'paint_olive')]
    # package-gun cheek fairings (two .50s each side)
    for s in (-1, 1):
        pieces.append(ellipsoid((s * 0.67, 3.70, -0.36), (0.13, 0.95, 0.28), 'paint_olive', seg=20, rings_n=14))
    # radio mast behind turret and a small dorsal fairing
    pieces.append(cylinder((0, -1.2, 0.85), (0, -1.45, 1.35), 0.025, 8, 'metal_dark', r1=0.012))
    return pieces


def build_canopy():
    keys = [  # y, half width, top
        (4.08, 0.40, 0.50),
        (3.88, 0.50, 0.84),
        (3.62, 0.57, 1.11),
        (3.40, 0.60, 1.22),
        (2.90, 0.61, 1.27),
        (2.45, 0.60, 1.25),
        (2.15, 0.56, 1.08),
        (1.95, 0.50, 0.93),
    ]
    f = table_interp(keys)
    ys = [lerp(4.08, 1.95, i / 22) for i in range(23)]
    rings = []
    for y in ys:
        hw, top = f(y)
        bot = 0.30
        zc = 0.30
        rings.append(superellipse_ring(0, y, zc, hw, top - zc, 0.05, 3.0, 2.0, 40))
    return [loft(rings, 'glass')]


def build_canopy_frames():
    """Thin framing bars over the glazing (metal_dark), part of the fuselage."""
    pieces = []
    keys = [(4.08, 0.40, 0.50), (3.88, 0.50, 0.84), (3.62, 0.57, 1.11), (3.40, 0.60, 1.22), (2.90, 0.61, 1.27),
            (2.45, 0.60, 1.25), (2.15, 0.56, 1.08), (1.95, 0.50, 0.93)]
    f = table_interp(keys)
    for y in (3.86, 3.42, 2.95, 2.45):
        hw, top = f(y)
        ring = superellipse_ring(0, y, 0.30, hw + 0.012, top - 0.30 + 0.012, 0.05, 3.0, 2.0, 40)
        pts = [Vector(p) for p in ring[:21]]          # upper half only
        for a, b in zip(pts[:-1], pts[1:]):
            pieces.append(cylinder(a, b, 0.018, 6, 'paint_olive'))
    # windscreen centre post and side sills
    for x in (0.0,):
        prev = None
        for y in [lerp(3.95, 3.40, i / 5) for i in range(6)]:
            hw, top = f(y)
            p = Vector((x, y, top + 0.012))
            if prev is not None:
                pieces.append(cylinder(prev, p, 0.02, 6, 'paint_olive'))
            prev = p
    return pieces

# ----------------------------------------------------------------------------- nacelles, cowlings, props
COWL_FRONT_Y = 3.06
COWL_REAR_Y = 1.95
PROP_Y = 3.30


def build_cowling(side):
    xn = side * NAC_X
    o = Vector((xn, 0, NAC_Z))
    prof = [(0.44, 2.72), (0.46, 2.95), (0.49, 3.03), (0.55, COWL_FRONT_Y), (0.62, 3.045), (0.675, 2.98),
            (0.705, 2.86), (0.72, 2.62), (0.718, 2.30), (0.705, COWL_REAR_Y)]
    pieces = [lathe(o, (0, 1, 0), prof, 40, 'paint_olive')]
    # engine face: crankcase nose + 7 front-row cylinders
    pieces.append(lathe(o, (0, 1, 0), [(0.46, 2.70), (0.46, 2.80), (0.24, 2.82), (0.20, 2.95), (0.10, 3.02), (0.0, 3.04)],
                        24, 'metal_dark'))
    for k in range(7):
        a = 2 * math.pi * k / 7 + math.pi / 2
        d = Vector((math.cos(a), 0, math.sin(a)))
        pieces.append(cylinder(o + Vector((0, 2.86, 0)) + d * 0.20, o + Vector((0, 2.86, 0)) + d * 0.43, 0.075, 10, 'metal_dark'))
    # exhaust stacks around the rear of the cowl (sides and lower half)
    for k in range(10):
        a = math.radians([150, 175, 200, 225, 250][k % 5]) if k < 5 else math.radians([30, 5, -20, -45, -70][k % 5])
        d = Vector((math.cos(a), 0, math.sin(a)))
        p0 = o + Vector((0, 2.10, 0)) + d * 0.66
        p1 = o + Vector((0, 1.82, 0)) + d * 0.76
        pieces.append(cylinder(p0, p1, 0.045, 8, 'metal_dark', r1=0.055))
    # carburettor air scoop on top
    pieces.append(ellipsoid((xn, 2.25, NAC_Z + 0.70), (0.12, 0.42, 0.11), 'paint_olive', seg=16, rings_n=10))
    return pieces


NAC_KEYS = [  # y, half width, top z, bottom z, p
    (COWL_REAR_Y + 0.02, 0.700, NAC_Z + 0.700, NAC_Z - 0.700, 2.0),
    (1.40, 0.680, 0.80, -0.70, 2.2),
    (0.50, 0.640, 0.72, -0.78, 2.5),
    (-1.00, 0.600, 0.63, -0.78, 2.6),
    (-2.40, 0.520, 0.56, -0.62, 2.5),
    (-3.20, 0.380, 0.50, -0.30, 2.3),
    (-3.75, 0.060, 0.42, 0.28, 2.0),
]


def build_nacelle(side):
    f = table_interp([(k[0], k[1], k[2], k[3], k[4]) for k in NAC_KEYS])
    xn = side * NAC_X
    ys = [lerp(NAC_KEYS[0][0], NAC_KEYS[-1][0], i / 26) for i in range(27)]
    rings = []
    for y in ys:
        hw, top, bot, p = f(y)
        zc = 0.5 * (top + bot)
        rings.append(superellipse_ring(xn, y, zc, hw, top - zc, zc - bot, p, p, 36))
    rings.append([(xn, -3.80, 0.36)])
    return [loft(rings, 'paint_olive')]


def blade_frame(r):
    """frame for a blade along +Z (local); returns section frame"""
    c = pchip([0.15, 0.35, 0.60, 1.10, 1.60, 1.80], [0.13, 0.14, 0.24, 0.30, 0.28, 0.26])(r)
    tc = pchip([0.15, 0.32, 0.50, 0.90, 1.75], [0.90, 0.85, 0.28, 0.12, 0.07])(r)
    beta = math.atan(0.745 / max(r, 0.2))
    r0 = PROP_R - 0.20
    if r > r0:
        u = min((r - r0) / 0.20, 1.0)
        c = c * max(math.sqrt(max(1 - u * u, 0)), 0.06)
    # clockwise seen from behind: top blade moves to +X; LE leads (+X) and forward (+Y)
    cdir = Vector((-math.cos(beta), -math.sin(beta), 0))
    tdir = Vector((-math.sin(beta), math.cos(beta), 0))
    le = Vector((0, 0, r)) - cdir * (0.30 * c)
    return (le, c, tc, 0.02 if r > 0.4 else 0.0, cdir, tdir)


def build_blade():
    rs = [0.15, 0.25, 0.35, 0.45, 0.60, 0.80, 1.00, 1.20, 1.40, 1.60, 1.73, 1.80]
    rs += [1.80 + (PROP_R - 1.80) * math.sin(0.5 * math.pi * i / 5) for i in range(1, 6)]
    rings_black, rings_tip = [], []
    for r in rs:
        fr = blade_frame(r)
        ring = main_ring(fr, 1.0) if r < PROP_R - 1e-6 else [sec_point(fr, 0.3, 0)]
        (rings_black if r <= 1.80 + 1e-6 else rings_tip).append(ring)
    rings_tip.insert(0, rings_black[-1])
    return [loft(rings_black, 'prop_black', cap_end=False), loft(rings_tip, 'prop_tip_yellow', cap_start=False)]


def build_hub():
    return [lathe((0, 0, 0), (0, 1, 0), [(0.0, -0.26), (0.20, -0.24), (0.23, -0.10), (0.22, 0.06), (0.17, 0.17),
                                         (0.09, 0.24), (0.0, 0.265)], 24, 'metal_dark')]

# ----------------------------------------------------------------------------- guns, turret, blisters
def barrel(p0, p1, r=0.022, mat='metal_dark', jacket=None):
    pcs = [cylinder(p0, p1, r, 12, mat)]
    if jacket:
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0)
        pcs.append(cylinder(p0, p0 + d * jacket[1], jacket[0], 12, mat))
    return pcs


NOSE_GUNS = [(-0.20, 0.00), (-0.07, 0.06), (0.07, 0.06), (0.20, 0.00)]   # (x, z)
NOSE_GUN_TIP_Y = 6.38


def build_nose_guns():
    pcs = []
    for x, z in NOSE_GUNS:
        pcs += barrel((x, 5.35, z), (x, NOSE_GUN_TIP_Y, z), 0.022, jacket=(0.034, 0.55))
    # package guns: two per side in the cheek fairings
    for s in (-1, 1):
        for z in (-0.22, -0.50):
            pcs += barrel((s * 0.74, 3.30, z), (s * 0.74, 4.80, z), 0.022, jacket=(0.034, 0.55))
    return pcs


CANNON_X, CANNON_Z, CANNON_TIP_Y = -0.30, -0.62, 6.06


def build_cannon():
    pcs = [cylinder((CANNON_X, 3.9, CANNON_Z), (CANNON_X, CANNON_TIP_Y - 0.10, CANNON_Z), 0.048, 16, 'metal_dark')]
    pcs.append(cylinder((CANNON_X, CANNON_TIP_Y - 0.12, CANNON_Z), (CANNON_X, CANNON_TIP_Y, CANNON_Z), 0.066, 16, 'metal_dark'))
    return pcs


TURRET_Y = 1.40
TURRET_RING_Z = fus_top_z(TURRET_Y) - 0.04 if False else 0.84
TURRET_TRUNNION = (0.0, TURRET_Y, 1.17)


def build_turret():
    pcs = [lathe((0, TURRET_Y, 0), (0, 0, 1), [(0.0, 0.76), (0.58, 0.76), (0.58, 0.93), (0.55, 0.96), (0.0, 0.96)], 36, 'paint_olive')]
    pcs.append(dome_z((0, TURRET_Y, 0.95), 0.53, 0.50, 'glass', seg=36, rings_n=10))
    return pcs


def build_turret_guns():
    x0, y0, z0 = TURRET_TRUNNION
    pcs = [cylinder((-0.17, y0, z0), (0.17, y0, z0), 0.05, 12, 'metal_dark')]
    for s in (-1, 1):
        pcs += barrel((s * 0.12, y0 + 0.25, z0), (s * 0.12, y0 - 1.20, z0), 0.022, jacket=(0.034, 0.5))
    return pcs


TAIL_GUN_PIVOT = (0.0, -8.78, 0.40)


def build_tail_guns():
    pcs = [ellipsoid((0, -8.86, 0.42), (0.24, 0.27, 0.26), 'glass', seg=24, rings_n=12)]
    for s in (-1, 1):
        pcs += barrel((s * 0.09, -8.60, 0.38), (s * 0.09, -9.16, 0.38), 0.020, jacket=(0.03, 0.4))
    return pcs


WAIST = {1: -4.70, -1: -5.00}   # side -> y (staggered as on B-25H/J)


def build_waist(side):
    y = WAIST[side]
    xw = fus_half_width(y)
    pcs = [ellipsoid((side * (xw - 0.04), y, 0.32), (0.16, 0.42, 0.30), 'glass', seg=20, rings_n=12)]
    pcs += barrel((side * (xw - 0.05), y, 0.30), (side * (xw + 0.55), y + 0.05, 0.28), 0.020, jacket=(0.03, 0.4))
    return pcs, Vector((side * xw, y, 0.32))

# ----------------------------------------------------------------------------- landing gear
CG_Y = None  # filled in main()


def gear_geometry(cg_y):
    main_axle = Vector((NAC_X, cg_y - 0.70, GROUND_Z + MAIN_WHEEL_R))
    main_hinge = Vector((NAC_X, main_axle.y + 0.25, -0.30))
    nose_axle = Vector((0.0, cg_y + 4.35, GROUND_Z + NOSE_WHEEL_R))
    nose_hinge = Vector((0.0, nose_axle.y + 0.25, -0.80))
    return main_hinge, main_axle, nose_hinge, nose_axle


def build_strut(hinge, axle, fork_half, crown_h, r_oleo):
    pcs = []
    crown = axle + Vector((0, 0, crown_h))
    mid = hinge.lerp(crown, 0.55)
    pcs.append(cylinder(hinge, mid, r_oleo, 14, 'metal_dark'))
    pcs.append(cylinder(mid + (hinge - mid).normalized() * 0.05, crown, r_oleo * 0.72, 14, 'metal_dark'))
    pcs.append(cylinder(hinge + Vector((-fork_half * 0.9, 0, 0)), hinge + Vector((fork_half * 0.9, 0, 0)), r_oleo * 0.7, 12, 'metal_dark'))
    pcs.append(cylinder(crown + Vector((-fork_half, 0, 0)), crown + Vector((fork_half, 0, 0)), r_oleo * 0.6, 12, 'metal_dark'))
    for s in (-1, 1):
        pcs.append(cylinder(crown + Vector((s * fork_half, 0, 0)), axle + Vector((s * fork_half, 0, -0.02)), r_oleo * 0.5, 10, 'metal_dark'))
    pcs.append(cylinder(axle + Vector((-fork_half - 0.02, 0, 0)), axle + Vector((fork_half + 0.02, 0, 0)), r_oleo * 0.4, 10, 'metal_dark'))
    # torque link
    pcs.append(cylinder(mid + Vector((0, 0.10, 0)), crown + Vector((0, 0.14, 0.05)), 0.02, 6, 'metal_dark'))
    return pcs


def build_wheel(ro, width, ri):
    # tyre: closed torus around X axis with a rounded-rectangle section
    hr, hw = (ro - ri) / 2, width / 2
    rc = (ri + ro) / 2
    sec = []
    for k in range(20):
        t = 2 * math.pi * k / 20
        c, s = math.cos(t), math.sin(t)
        p = 3.0
        sec.append((rc + hr * math.copysign(abs(c) ** (2 / p), c), hw * math.copysign(abs(s) ** (2 / p), s)))
    rings = []
    seg = 40
    for j in range(seg):
        a = 2 * math.pi * j / seg
        rings.append([(xx, r * math.cos(a), r * math.sin(a)) for (r, xx) in sec])
    tyre = loft(rings, 'rubber', wrap=True)
    hub = lathe((0, 0, 0), (1, 0, 0), [(0.0, -hw * 0.8), (ri * 0.5, -hw * 0.82), (ri + 0.02, -hw * 0.7), (ri + 0.02, hw * 0.7),
                                       (ri * 0.5, hw * 0.82), (0.0, hw * 0.8)], 24, 'metal_dark')
    return [tyre, hub]

# ----------------------------------------------------------------------------- bomb doors
BOMB_DOOR_X = 0.46


def build_bomb_door(side, cg_y):
    y0, y1 = cg_y + 0.85, cg_y - 1.55
    xs = [0.006 + (BOMB_DOOR_X - 0.006) * i / 12 for i in range(13)]
    rings = []
    for i in range(7):
        y = lerp(y0, y1, i / 6)
        outer = [(side * x, y, fus_bottom_z(y, x) - 0.008) for x in xs]
        inner = [(side * x, y, fus_bottom_z(y, x) + 0.022) for x in reversed(xs)]
        rings.append(outer + inner)
    yh = 0.5 * (y0 + y1)
    hinge = Vector((side * BOMB_DOOR_X, yh, fus_bottom_z(yh, BOMB_DOOR_X) + 0.007))
    return [loft(rings, 'paint_olive')], hinge, (y0, y1)

# ----------------------------------------------------------------------------- blender object creation
MAT_CACHE = {}


def get_mat(name):
    if name not in MAT_CACHE:
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.diffuse_color = MATS[name]
        m.roughness = 0.6 if name != 'glass' else 0.1
        m.metallic = 0.5 if name == 'metal_dark' else 0.0
        MAT_CACHE[name] = m
    return MAT_CACHE[name]


SHIFT = Vector((0, 0, 0))   # design -> world offset (set to -CG)
OBJ = {}


def fus_grey_rule(c, n):
    """underside rule for the fuselage: follows a constant ring parameter, so the
    olive/grey demarcation is a clean line instead of a per-face zig-zag"""
    hw, top, bot, pt, pb, zc = fus_section(min(max(c.y, FUS_TAIL_Y), FUS_NOSE_Y))
    return n.z < -0.05 and c.z < zc - 0.30 * (zc - bot)


def make_object(name, pieces, pivot, parent=None, split_under=True, sharp_deg=40.0, grey_rule=None):
    pivot = Vector(pivot)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    mats = []
    for pc in pieces:
        if pc.mat not in mats:
            mats.append(pc.mat)
    for pc in pieces:
        vs = [bm.verts.new(v - pivot) for v in pc.verts]
        mi = mats.index(pc.mat)
        for f in pc.faces:
            if len(set(f)) < 3:
                continue
            try:
                face = bm.faces.new([vs[i] for i in f])
                face.material_index = mi
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(get_mat(m))
    # olive upper / grey lower split
    if split_under and 'paint_olive' in mats:
        if 'paint_grey' not in mats:
            me.materials.append(get_mat('paint_grey'))
            mats.append('paint_grey')
        io, ig = mats.index('paint_olive'), mats.index('paint_grey')
        for p in me.polygons:
            if p.material_index != io:
                continue
            if grey_rule is not None:
                if grey_rule(p.center + pivot, p.normal):
                    p.material_index = ig
            elif p.normal.z < -0.3:
                p.material_index = ig
    me.shade_smooth()
    try:
        me.set_sharp_from_angle(angle=math.radians(sharp_deg))
    except Exception:
        pass
    box_uv(me)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    place(ob, pivot, parent)
    OBJ[name] = ob
    return ob


def make_empty(name, pivot, parent=None):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = 'PLAIN_AXES'
    ob.empty_display_size = 0.3
    bpy.context.scene.collection.objects.link(ob)
    place(ob, Vector(pivot), parent)
    OBJ[name] = ob
    return ob


def place(ob, pivot_design, parent):
    world = pivot_design + SHIFT
    ob['pivot_world'] = list(world)
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.location = world - Vector(parent['pivot_world'])
    else:
        ob.location = world


def set_hinge(ob, a, b=None, axis=None, kind='hinge'):
    """store hinge axis (Blender world == local since no part rotation except blades)"""
    if axis is None:
        axis = (Vector(b) - Vector(a)).normalized()
    axis = Vector(axis).normalized()
    dom = max(range(3), key=lambda i: abs(axis[i]))
    if axis[dom] < 0:
        axis = -axis          # canonical: dominant component positive
    ob['hinge_axis'] = list(Vector(axis).normalized())
    ob['hinge_kind'] = kind


def box_uv(me):
    uv = me.uv_layers.new(name='UVMap')
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                uv.data[li].uv = (co.y, co.z)
            elif ax == 1:
                uv.data[li].uv = (co.x, co.z)
            else:
                uv.data[li].uv = (co.x, co.y)

# ----------------------------------------------------------------------------- main
def compute_cg():
    n = 2000
    S = Sc2 = Scle = 0.0
    dx = SPAN_HALF / n
    for i in range(n):
        x = (i + 0.5) * dx
        le, c = wing_planform(x)
        S += c * dx
        Sc2 += c * c * dx
        Scle += c * le * dx
    mac = Sc2 / S
    le_mac = Scle / S
    return le_mac - 0.30 * mac, mac, le_mac, 2 * S


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = None
    if '--out' in argv:
        out = argv[argv.index('--out') + 1]
    global SHIFT
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    cg_y, mac, le_mac, area = compute_cg()
    print(f"[b25h] wing area (trapezoid) {area:.2f} m2, MAC {mac:.3f} m, MAC LE y {le_mac:.3f}, CG y(design) {cg_y:.3f}")
    SHIFT = Vector((0, -cg_y, 0))

    root = make_empty('B25H_root', (0, cg_y, 0))
    root['ground_offset'] = -GROUND_Z
    origin = Vector((0, cg_y, 0))

    fus = make_object('fuselage', build_fuselage() + build_canopy_frames(), origin, root,
                      grey_rule=fus_grey_rule)
    make_object('canopy_glass', build_canopy(), (0, 3.0, 0.30), root, split_under=False)
    ng = make_object('nose_guns', build_nose_guns(), (0, NOSE_GUN_TIP_Y, 0.03), root, split_under=False)
    cn = make_object('cannon', build_cannon(), (CANNON_X, CANNON_TIP_Y, CANNON_Z), root, split_under=False)
    tur = make_object('turret_dorsal', build_turret(), (0, TURRET_Y, TURRET_RING_Z), root)
    set_hinge(tur, None, axis=(0, 0, 1), kind='yaw')
    tg = make_object('turret_dorsal_guns', build_turret_guns(), TURRET_TRUNNION, tur, split_under=False)
    set_hinge(tg, None, axis=(1, 0, 0), kind='pitch')
    tl = make_object('tail_guns', build_tail_guns(), TAIL_GUN_PIVOT, root, split_under=False)
    set_hinge(tl, None, axis=(0, 0, 1), kind='yaw+pitch(X)')
    for s, nm in ((-1, 'waist_blister_L'), (1, 'waist_blister_R')):
        pcs, piv = build_waist(s)
        wb = make_object(nm, pcs, piv, root, split_under=False)
        set_hinge(wb, None, axis=(0, 0, 1), kind='gun yaw (optional)')

    for s, sfx in ((-1, 'L'), (1, 'R')):
        wing = make_object(f'wing_{sfx}', build_wing(s), origin, root)
        pcs, pa, pb = build_ctrl_wing(s, AILERON)
        ob = make_object(f'aileron_{sfx}', pcs, (pa + pb) / 2, wing)
        set_hinge(ob, pa, pb)
        pcs, pa, pb = build_ctrl_wing(s, FLAP_OUT)
        ob = make_object(f'flap_{sfx}', pcs, (pa + pb) / 2, wing)
        set_hinge(ob, pa, pb)
        pcs, pa, pb = build_ctrl_wing(s, FLAP_IN)
        ob = make_object(f'flap_{sfx}_inner', pcs, (pa + pb) / 2, wing)
        set_hinge(ob, pa, pb)

        make_object(f'nacelle_{sfx}', build_nacelle(s), (s * NAC_X, 0.0, NAC_Z), root)
        make_object(f'cowling_{sfx}', build_cowling(s), (s * NAC_X, COWL_REAR_Y, NAC_Z), root)
        hub_c = Vector((s * NAC_X, PROP_Y, NAC_Z))
        hub = make_object(f'prop_hub_{sfx}', build_hub(), (0, 0, 0), root, split_under=False)
        # hub mesh was built around the origin; re-place at hub centre
        hub['pivot_world'] = list(hub_c + SHIFT)
        hub.location = hub_c + SHIFT
        set_hinge(hub, None, axis=(0, 1, 0), kind='prop spin: clockwise seen from behind = NEGATIVE angle about Unity +Z')
        for k in range(3):
            bl = make_object(f'prop_{sfx}_blade{k + 1}', build_blade(), (0, 0, 0), hub, split_under=False, sharp_deg=60)
            bl.location = Vector((0, 0, 0))
            bl['pivot_world'] = list(hub_c + SHIFT)
            bl.rotation_mode = 'QUATERNION'
            bl.rotation_quaternion = Matrix.Rotation(math.radians(120 * k), 4, 'Y').to_quaternion()
            set_hinge(bl, None, axis=(0, 0, 1), kind='blade pitch (local axis)')

        bpcs, hinge, _ = build_bomb_door(s, cg_y)
        bd = make_object(f'bomb_door_{sfx}', bpcs, hinge, root)
        set_hinge(bd, None, axis=(0, 1, 0))

    stab = make_object('stab_h', build_stab(), (0, -8.1, STAB_Z), root)
    for s, sfx in ((-1, 'L'), (1, 'R')):
        pcs, pa, pb = build_elevator(s)
        ob = make_object(f'elevator_{sfx}', pcs, (pa + pb) / 2, stab)
        set_hinge(ob, pa, pb) if s > 0 else set_hinge(ob, pb, pa)
        fin = make_object(f'fin_{sfx}', build_fin(s), (s * STAB_HALF, -8.1, STAB_Z), root)
        pcs, pa, pb = build_rudder(s)
        ob = make_object(f'rudder_{sfx}', pcs, (pa + pb) / 2, fin)
        set_hinge(ob, pa, pb)

    mh, ma, nh, na = gear_geometry(cg_y)
    for s, sfx in ((-1, 'L'), (1, 'R')):
        h = Vector((s * mh.x, mh.y, mh.z))
        a = Vector((s * ma.x, ma.y, ma.z))
        st = make_object(f'gear_main_{sfx}_strut', build_strut(h, a, 0.27, 0.42, 0.085), h, root, split_under=False)
        set_hinge(st, None, axis=(1, 0, 0), kind='retract (aft)')
        w = make_object(f'gear_main_{sfx}_wheel', [p for p in build_wheel(MAIN_WHEEL_R, 0.38, 0.30)], (0, 0, 0), st, split_under=False)
        w['pivot_world'] = list(a + SHIFT)
        w.location = a - h
        set_hinge(w, None, axis=(1, 0, 0), kind='wheel spin')
    st = make_object('gear_nose_strut', build_strut(nh, na, 0.17, 0.30, 0.07), nh, root, split_under=False)
    set_hinge(st, None, axis=(1, 0, 0), kind='retract (aft)')
    w = make_object('gear_nose_wheel', build_wheel(NOSE_WHEEL_R, 0.24, 0.17), (0, 0, 0), st, split_under=False)
    w['pivot_world'] = list(na + SHIFT)
    w.location = na - nh
    set_hinge(w, None, axis=(1, 0, 0), kind='wheel spin')

    # muzzle / attachment empties (extras, not required by the brief)
    make_empty('muzzle_cannon', (CANNON_X, CANNON_TIP_Y, CANNON_Z), root)
    make_empty('muzzle_nose_guns', (0, NOSE_GUN_TIP_Y, 0.03), root)
    make_empty('muzzle_package_L', (-0.74, 4.80, -0.36), root)
    make_empty('muzzle_package_R', (0.74, 4.80, -0.36), root)
    make_empty('muzzle_turret', (0, TURRET_Y - 1.20, TURRET_TRUNNION[2]), tg)
    make_empty('muzzle_tail', (0, -9.16, 0.38), tl)
    make_empty('bomb_bay_centre', (0, cg_y - 0.35, -0.75), root)

    bpy.context.view_layer.update()
    tris = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
    print(f"[b25h] objects {len(bpy.data.objects)}  faces(pre-triangulation) {tris}")
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True)
        print(f"[b25h] saved {out}")


if __name__ == '__main__':
    main()
