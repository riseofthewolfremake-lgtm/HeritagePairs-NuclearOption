"""B-17G nacelles, 1.8.3 (user bug review 2026-11-07 item 2: 'the engines and nacelles are still mismodelled against the reference').

Proportions come from section measurements of the War Thunder reference (blender/b17g/measure_nacelles.py; numbers only, the
reference itself is never read by this module): top / bottom lines of each nacelle every 0.1 m, the cowl-flap ring (y and radius).
What changes against 1.8.2 (S.NAC183 = True; False rebuilds the 1.8.2 nacelles):
  (c) cowl: a rolled lip ring painted olive drab (anti-glare ring), the drum, then 16 separate cowl flaps opening onto a slightly
      fatter nacelle body (ref: flaps 0.54-0.82 m behind the lip, trailing edge r 0.82 inner / 0.77 outer), a dark band under the flaps;
      the nacelle top stays full and round over the wing much further aft (ref top lines), the inboard belly rises behind the well.
  (a) wheel well: an opening shaped round the stowed tyre (rounded rectangle, 0.62 m wide) plus a narrow slot for the leg, a raised
      lip round it, a liner box above; the tyre protrudes below the belly as on the reference. The gear kinematics are unchanged.
  (b) turbo-supercharger (GE B-22): scroll housing with a ribbed bucket-wheel face, the turbine exhaust (waste-gate) stub, the
      compressor outlet (intercooler duct) elbow into the nacelle, and the exhaust pipe from the collector outside along the nacelle
      (inboard engines: outboard lower side; outboard engines: the belly) to the turbo. The outboard turbos move forward to y 1.6
      (reference); the inboard ones stay at y 0.05.
  Intercooler / oil-cooler intakes in the wing leading edge: real openings (cut, boxed, grilled) at the reference spans.
Physics: the engine part's convex collider is baked from its mesh; a hidden `engine_n_hullsrc` child carries the 1.8.2 turbo so the
collider (and with it the part's centre of mass) stays the 1.8.2 one (Unity bakes it in, then deletes the child).
"""
import math
from mathutils import Vector as V, Euler
import b17g_spec as S
from b25h_geom import (MeshBuf, superellipse_ring, circle_pts, loft, fan_cap, annulus, oriented_quad, cylinder, box, ring_arc_uv)
from b25h_parts import Part
import nimrod_structure as NS

FLAP_LE, FLAP_TE = 0.54, 0.82          # cowl flaps: hinge line / trailing edge, metres behind the lip (ref 3.51-3.79 inner, 2.91-3.19 outer)
BODY_R = {'inner': 0.80, 'outer': 0.775}
FLAP_TE_R = {'inner': 0.812, 'outer': 0.784}
N_FLAPS = 16
# nacelle top / bottom lines behind the cowl flaps (y ascending), from the reference sections (our axes: inner x 3.10, outer 6.575)
TOP = {'inner': [(-1.0, 0.35), (-0.6, 0.42), (-0.2, 0.49), (0.2, 0.56), (0.6, 0.64), (1.0, 0.715), (1.2, 0.745), (1.6, 0.79), (2.0, 0.81),
                 (2.4, 0.83), (3.0, 0.845), (3.53, 0.85)],
       'outer': [(-1.0, 0.525), (-0.8, 0.565), (-0.4, 0.63), (0.0, 0.70), (0.4, 0.79), (0.8, 0.89), (1.2, 0.98), (1.6, 1.035), (2.0, 1.07),
                 (2.4, 1.086), (2.6, 1.09), (2.94, 1.075)]}
BOT = {'inner': [(-1.0, -0.355), (-0.8, -0.39), (-0.4, -0.46), (0.0, -0.55), (0.3, -0.575), (0.6, -0.63), (0.9, -0.70), (1.4, -0.72),
                 (3.2, -0.745), (3.53, -0.75)],
       'outer': [(-0.5, -0.02), (-0.2, -0.06), (0.0, -0.115), (0.2, -0.165), (0.6, -0.27), (1.0, -0.37), (1.4, -0.43), (1.8, -0.435),
                 (2.0, -0.46), (2.4, -0.485), (2.7, -0.505), (2.94, -0.475)]}
TURBO_MAT_185E = True   # 1.8.5 offline E (in-game 1.8.3 F2): the turbo housing + volute face down into shade and read dark grey-brown; their own
                        # lighter, less metallic rust 'turbo' material (the collector pipes / elbows keep 'exhaust', which reads right). False = 1.8.4

TURBO_Y = {'inner': 0.05, 'outer': 1.60}
# wheel well opening (bottom view, u = x - MAIN_X * side): rounded rectangle round the stowed tyre + the leg slot behind it
WELL_U, WELL_Y = 0.31, (2.20, 3.72)          # tyre 0.50 wide, stowed y 2.27-3.69
SLOT_U, SLOT_Y = 0.13, (1.45, 2.30)          # leg r 0.085 crosses the belly between y 1.55 and 2.99 during the swing
WELL_BOX_Y, WELL_ROOF = (1.35, 3.72), 0.38
# leading-edge intakes (|x| ranges, reference front view): intercooler / oil-cooler air, two each side of the nacelles
LE_INTAKES = [(1.48, 1.78), (1.93, 2.11), (4.16, 4.33), (5.45, 5.64), (7.40, 7.74), (7.91, 8.11)]
LE_INTAKE_H = 0.17


def _tab(t, y):
    return S.interp(t, y)


def nac_profile183(kind, y):
    """(half width, z top, z bottom) of the nacelle at y (1.8.3)."""
    xa, za, ylip, yprop, R, yend, zbelly = S.NACELLES[kind]
    if y >= ylip - 0.05:
        t = (y - (ylip - 0.05)) / 0.05
        return R * (1 - 0.06 * t), za + R * (1 - 0.06 * t), za - R * (1 - 0.06 * t)
    if y >= ylip - FLAP_LE:
        return R, za + R, za - R
    RB = BODY_R[kind]
    if y > ylip - FLAP_TE:
        t = (ylip - FLAP_LE - y) / (FLAP_TE - FLAP_LE)
        r = R + (RB - R) * t
        return r, za + r, za - r
    if y <= yend + 0.02:
        return 0.05, S.wing_z(xa) + 0.04, S.wing_z(xa) - 0.04
    yb = ylip - FLAP_TE
    t = max(0.0, min(1.0, (yb - y) / (yb - yend)))
    rs = RB * (1 - 0.55 * t ** 1.4)
    if kind == 'inner':          # the gear trunnion (x +-0.415 from the axis at z -0.52..-0.59, y 1.6) stays inside the skin
        rs = max(rs, _tab([(1.0, 0.0), (1.3, 0.72), (2.3, 0.72), (2.6, 0.0)], y))
    top = _tab([(yend, S.wing_z(xa) + 0.04)] + TOP[kind], y)
    bot = _tab([(yend, S.wing_z(xa) - 0.04)] + BOT[kind], y)
    return rs, top, bot


def nac_ring(kind, side, y, N):
    xa, za, *_ = S.NACELLES[kind]
    rs, top, bot = nac_profile183(kind, y)
    cz = (top + bot) / 2
    return superellipse_ring(xa * side, y, cz, rs, (top - bot) / 2, (top - bot) / 2, n=2.2, N=N)


# ============================================================================================ 1.8.8 bodies (S.NAC188)
# Behind the wing leading edge the body is two half-superellipses hung on OUR wing skin: the lower one D below the local lower skin with
# footprint half width A_lo, the upper one H above the upper skin with half width A_up (both from the reference sections, measured
# relative to the reference's own wing: nuclearoption-ref/scratch_I/meas_I.py, numbers only). Their edges run E188 = 3 cm inside the
# wing. Ahead of that (cowl flaps -> wing LE) the body stays the 1.8.3 absolute superellipse (TOP / BOT, width HW_A). Between ZONE[kind]
# (start, end) the two are blended point by point (smoothstep). The inner body stays absolute down to y 1.35 (the main-gear well, slot
# and trunnion are 1.8.3 geometry; the physics worker owns the gear).
_USE188 = True          # build switch (the 1.8.7 body is built once more as the nacelle collider source, see build_nacelle)
E188 = 0.03
ZONE = {'inner': (1.35, 0.75), 'outer': (1.79, 1.30)}
YEND188 = {'inner': -1.06, 'outer': -0.20}
HW_A = {'inner': [(1.0, 0.72), (3.53, 0.80)],
        'outer': [(1.2, 0.62), (1.4, 0.66), (1.6, 0.70), (1.8, 0.73), (2.0, 0.76), (2.2, 0.77), (2.6, 0.78), (2.94, 0.775)]}
B188 = {   # (y ascending, value): footprint half widths and depth / height relative to the local wing skin (reference, numbers only)
    'outer': dict(
        A_lo=[(-0.18, 0.0), (-0.14, 0.04), (-0.06, 0.10), (0.04, 0.165), (0.14, 0.22), (0.24, 0.26), (0.34, 0.31), (0.44, 0.36), (0.54, 0.40),
              (0.64, 0.44), (0.74, 0.47), (0.84, 0.50), (0.94, 0.53), (1.04, 0.555), (1.2, 0.595), (1.4, 0.635), (1.6, 0.66), (1.9, 0.70)],
        D=[(-0.18, 0.0), (-0.14, 0.03), (-0.06, 0.065), (0.04, 0.092), (0.14, 0.116), (0.24, 0.14), (0.34, 0.169), (0.44, 0.20), (0.54, 0.228),
           (0.64, 0.256), (0.74, 0.283), (0.84, 0.313), (0.94, 0.341), (1.04, 0.368), (1.2, 0.42), (1.4, 0.47), (1.6, 0.53), (1.9, 0.62)],
        A_up=[(0.20, 0.0), (0.24, 0.03), (0.34, 0.10), (0.44, 0.175), (0.54, 0.23), (0.64, 0.28), (0.74, 0.32), (0.84, 0.36), (0.94, 0.40),
              (1.04, 0.43), (1.14, 0.465), (1.24, 0.49), (1.34, 0.52), (1.4, 0.55), (1.6, 0.60), (1.9, 0.66)],
        H=[(0.20, 0.0), (0.24, 0.016), (0.34, 0.04), (0.44, 0.065), (0.54, 0.09), (0.64, 0.114), (0.74, 0.136), (0.84, 0.16), (0.94, 0.187),
           (1.04, 0.216), (1.14, 0.245), (1.24, 0.271), (1.34, 0.306), (1.44, 0.34), (1.6, 0.40), (1.9, 0.48)],
        n_lo=[(-0.2, 2.2), (2.0, 2.2)]),
    'inner': dict(
        A_lo=[(-1.06, 0.0), (-1.02, 0.40), (-0.96, 0.42), (-0.8, 0.425), (-0.6, 0.44), (-0.4, 0.46), (-0.2, 0.475), (0.0, 0.49), (0.2, 0.52),
              (0.4, 0.555), (0.6, 0.575), (1.0, 0.58), (1.4, 0.60)],
        D=[(-1.06, 0.0), (-1.02, 0.0), (-0.98, 0.026), (-0.9, 0.032), (-0.8, 0.042), (-0.6, 0.072), (-0.4, 0.105), (-0.2, 0.15), (0.0, 0.19), (0.2, 0.215),
           (0.4, 0.235), (0.6, 0.27), (0.8, 0.325), (1.0, 0.33), (1.4, 0.40)],
        A_up=[(0.10, 0.0), (0.24, 0.02), (0.34, 0.04), (0.44, 0.08), (0.54, 0.115), (0.64, 0.155), (0.74, 0.19), (0.84, 0.215), (0.94, 0.235),
              (1.04, 0.265), (1.24, 0.33), (1.44, 0.38), (1.64, 0.435), (1.84, 0.50)],
        H=[(0.06, 0.0), (0.14, 0.005), (0.24, 0.018), (0.34, 0.029), (0.44, 0.042), (0.54, 0.056), (0.64, 0.067), (0.74, 0.078), (0.84, 0.089),
           (0.94, 0.10), (1.04, 0.114), (1.24, 0.151), (1.44, 0.189), (1.64, 0.233), (1.84, 0.29)],
        n_lo=[(-1.1, 3.0), (0.3, 3.0), (0.8, 2.2), (2.0, 2.2)],
        e_lo=[(-1.1, 0.010), (-0.5, 0.010), (0.0, 0.03)]),      # the squared end: the fairing's edge 1 cm into the wing (keeps its width to the end)
}
NH188 = 18              # segments per half ring (the ring has 2 x (NH188 + 1) points: upper arc, then lower arc, both endpoints kept)
_WCACHE = {}


def _wing_surf(x, y, upper):
    """z of OUR wing skin at (x, y) (analytic section, as b17g_parts.wing_station builds it); ahead of the LE / behind the TE the LE / TE z."""
    import b17g_parts as P
    key = (round(x, 4), round(y, 4), upper)
    if key in _WCACHE:
        return _WCACHE[key]
    side = 1 if x >= 0 else -1
    st = P.wing_station(abs(x), side)
    p0, p1 = st.point(0.0, upper), st.point(1.0, upper)
    if y >= p0.y:
        z = p0.z
    elif y <= p1.y:
        z = p1.z
    else:
        lo, hi = 0.0, 1.0
        for _ in range(30):
            m = (lo + hi) / 2
            if st.point(m, upper).y > y:
                lo = m
            else:
                hi = m
        z = st.point((lo + hi) / 2, upper).z
    _WCACHE[key] = z
    return z


def _se(a, n):
    s_, c_ = math.sin(a), math.cos(a)
    return math.copysign(abs(s_) ** (2.0 / n), s_), abs(c_) ** (2.0 / n)


def _ring_A(kind, side, y):
    xa, za, ylip, *_ = S.NACELLES[kind]
    rs, top, bot = nac_profile183(kind, y)
    if y < ylip - FLAP_TE and kind == 'outer':      # (inner: the 1.8.3 width over the well, trunnion and gear stay as they were)
        rs = _tab(HW_A[kind], y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    up, lo = [], []
    for k in range(NH188 + 1):
        sx, f = _se(-math.pi / 2 + math.pi * k / NH188, 2.2)      # upper arc: -x .. top .. +x (x absolute)
        up.append(V((xa * side + rs * sx, y, cz + hz * f + (0.001 if k in (0, NH188) else 0.0))))
    for k in range(NH188 + 1):
        sx, f = _se(math.pi / 2 + math.pi * k / NH188, 2.2)       # lower arc: +x .. bottom .. -x (equator points 2 mm apart: no zero-area wall)
        lo.append(V((xa * side + rs * sx, y, cz - hz * f - (0.001 if k in (0, NH188) else 0.0))))
    return up + lo


def _ring_B(kind, side, y):
    xa = S.NACELLES[kind][0]
    T_ = B188[kind]
    a_lo, d, a_up, h, n_lo = (_tab(T_['A_lo'], y), _tab(T_['D'], y), _tab(T_['A_up'], y), _tab(T_['H'], y), _tab(T_['n_lo'], y))
    a_lo, a_up = max(a_lo, 0.04), max(a_up, 0.04)        # a run-out arc keeps 4 cm of width inside the wing (no collapsed, zero-area triangles)
    up, lo = [], []
    for k in range(NH188 + 1):
        sx, f = _se(-math.pi / 2 + math.pi * k / NH188, 2.2)
        x = xa * side + a_up * sx
        wu, wl = _wing_surf(x, y, True), _wing_surf(x, y, False)
        e = min(E188, 0.3 * max(wu - wl, 0.0))
        up.append(V((x, y, wu - e + (h + e * min(1.0, h / 0.02)) * f)))      # (flat at wu - e once the fairing has run out: no fin to the skin)
    for k in range(NH188 + 1):
        sx, f = _se(math.pi / 2 + math.pi * k / NH188, n_lo)
        x = xa * side + a_lo * sx
        wu, wl = _wing_surf(x, y, True), _wing_surf(x, y, False)
        e = min(_tab(T_['e_lo'], y) if 'e_lo' in T_ else E188, 0.3 * max(wu - wl, 0.0))
        lo.append(V((x, y, wl + e - (d + e * min(1.0, d / 0.02)) * f)))
    return up + lo


def ring188(kind, side, y):
    """1.8.8 body ring at y: 2 x (NH188 + 1) points (upper arc -x -> +x, lower arc +x -> -x, x absolute)."""
    y0, y1 = ZONE[kind]
    if y >= y0:
        return _ring_A(kind, side, y)
    if y <= y1:
        return _ring_B(kind, side, y)
    t = (y0 - y) / (y0 - y1); t = t * t * (3 - 2 * t)
    return [a.lerp(b, t) for a, b in zip(_ring_A(kind, side, y), _ring_B(kind, side, y))]


def nac_profile188(kind, y):
    """(half width, z top, z bottom) at y on the 1.8.8 body (from the ring: its top / bottom points on the axis)."""
    xa, za, ylip, *_ = S.NACELLES[kind]
    if y >= ylip - FLAP_TE:
        return nac_profile183(kind, y)
    r = ring188(kind, 1, y)
    return max(abs(p.x - xa) for p in r), r[NH188 // 2].z, r[NH188 + 1 + NH188 // 2].z


def nac_profile(kind, y):
    """(half width, z top, z bottom) of the nacelle at y (1.8.8 when S.NAC188, else 1.8.3)."""
    if S.NAC188 and _USE188:
        return nac_profile188(kind, y)
    return nac_profile183(kind, y)


def zskin_bottom(kind, x, y, side):
    """z of the nacelle's lower skin at (x, y)."""
    xa = S.NACELLES[kind][0]
    rs, top, bot = nac_profile(kind, y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    u = min(abs(x - xa * side) / max(rs, 1e-3), 0.999)
    return cz - hz * (1 - u ** 2.2) ** (1 / 2.2)


def _sd_roundrect(u, y, u0, u1, y0, y1, r):
    cu, cy, hu, hy = (u0 + u1) / 2, (y0 + y1) / 2, (u1 - u0) / 2, (y1 - y0) / 2
    qx, qy = abs(u - cu) - hu + r, abs(y - cy) - hy + r
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r


def well_sd(u, y):
    """signed distance (bottom view) to the well opening: tyre opening (rounded rectangle) united with the leg slot."""
    a = _sd_roundrect(u, y, -WELL_U, WELL_U, WELL_Y[0], WELL_Y[1], 0.17)
    b = _sd_roundrect(u, y, -SLOT_U, SLOT_U, SLOT_Y[0], SLOT_Y[1], SLOT_U - 0.001)
    return min(a, b)


def well_outline(n_arc=8):
    """outline of the opening (u, y), going round once (tyre opening + slot)."""
    pts = []
    def arc(cu, cy, r, a0, a1):
        for k in range(n_arc + 1):
            a = math.radians(a0 + (a1 - a0) * k / n_arc)
            pts.append((cu + r * math.cos(a), cy + r * math.sin(a)))
    r = 0.17
    u, (y0, y1) = WELL_U, WELL_Y
    arc(u - r, y1 - r, r, 0, 90)                      # front outboard (+u) corner
    arc(-u + r, y1 - r, r, 90, 180)                   # front -u corner
    arc(-u + r, y0 + r, r, 180, 270)                  # rear -u corner
    pts.append((-SLOT_U - 0.04, y0)); pts.append((-SLOT_U, y0 - 0.02))
    arc(0.0, SLOT_Y[0] + SLOT_U, SLOT_U, 180, 360)    # slot end (rounded)
    pts.append((SLOT_U, y0 - 0.02)); pts.append((SLOT_U + 0.04, y0))
    arc(u - r, y0 + r, r, 270, 360)                   # rear +u corner
    # de-duplicate
    out = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-4:
            out.append(p)
    return out


def _flap_skip(kind, side, c):
    if kind != 'inner':
        return False
    xa, za = S.NACELLES[kind][0], S.NACELLES[kind][1]
    return c.z < za - 0.40 and well_sd(c.x - S.MAIN_X * side, c.y) < 0.08


# ============================================================================================ nacelle part
def build_nacelle(kind, side):
    global _USE188
    s = 'L' if side < 0 else 'R'
    num = S.ENGINE_NUM[(side, kind)]
    xa, za, ylip, yprop, R, yend, zbelly = S.NACELLES[kind]
    cx = xa * side
    out = []
    mb = _nacelle_mesh(kind, side)
    parent = ('wing_inner_' if kind == 'inner' else 'wing_mid_') + s
    yo_ = (3.735 if kind == 'inner' else ylip - 1.05) - 0.32       # origin on the oil tank (FuelTank / fire effects spawn at the origin)
    out.append(Part(f'nacelle_{num}', parent, pivot=V((cx, yo_, 0.52 if kind == 'inner' else za + 0.12)), mesh=mb,
                    info={'kind': 'nacelle', 'engine': num, 'v': '1.8.8' if (S.NAC188 and _USE188) else '1.8.3'}))
    if S.NAC188:
        # 1.8.8: the nacelle part's convex collider (and with it the part's mass centre, check: parts-collider CoM) stays the 1.8.7 one:
        # the 1.8.7 nacelle mesh rides along as a hidden child `nacelle_n_hullsrc` (all faces metal_dark: not in the livery atlas);
        # Unity bakes it into the collider and deletes it (gen_b17gbuild.py, the 1.8.3 engine_n_hullsrc mechanism)
        _USE188 = False
        try:
            old = _nacelle_mesh(kind, side)
        finally:
            _USE188 = True
        for f in old.faces:
            f['mat'] = 'metal_dark'; f['uv'] = None
        out.append(Part(f'nacelle_{num}_hullsrc', f'nacelle_{num}', mesh=old,
                        info={'kind': 'hull_src', 'note': 'collider source only (1.8.7 nacelle): Unity bakes it into the nacelle collider, then deletes it'}))
    if kind == 'inner':
        out.append(well_part(kind, side, parent))
    out += engine_front(kind, side)
    return out


def _nacelle_mesh(kind, side):
    """drum, body, cowl flaps and band of one nacelle (1.8.8 body when S.NAC188 and _USE188, else the 1.8.3 body)."""
    xa, za, ylip, yprop, R, yend, zbelly = S.NACELLES[kind]
    cx = xa * side
    N = 48
    new = S.NAC188 and _USE188
    if new:
        yend = YEND188[kind]
    mb = MeshBuf()
    # --- cowl drum (paint): lip ring of the engine part covers y > ylip - 0.10
    yd = [ylip - 0.10, ylip - 0.30, ylip - FLAP_LE]
    drum = [circle_pts(V((cx, y, za)), V((0, 1, 0)), R, N, ref=V((0, 0, 1))) for y in yd]
    d0 = len(mb.faces)
    loft(mb, drum, 'paint', closed=True, uvfunc=ring_arc_uv(drum, yd))
    drum_faces = mb.faces[d0:]
    # --- body behind the flaps (paint); dense stations over the well on the inboard nacelles
    yb = ylip - FLAP_TE + 0.02
    ys = []
    y = yb
    while y > yend + 0.01:
        ys.append(y)
        y -= 0.08 if (kind == 'inner' and 1.25 < y < 3.85) else (0.14 if new else 0.20)
    ys.append(yend)
    rings = [ring188(kind, side, y) for y in ys] if new else [nac_ring(kind, side, y, N) for y in ys]
    b0 = len(mb.faces)
    loft(mb, rings, 'paint', closed=True, uvfunc=ring_arc_uv(rings, ys))
    if kind == 'inner':        # well opening: drop body faces whose centre lies within 5 cm outside the outline (the 10 cm lip covers the steps)
        keep = mb.faces[:b0]
        for f in mb.faces[b0:]:
            P = [mb.verts[k] for k in f['idx']]
            c = sum(P, V()) / len(P)
            if c.z < za - 0.25 and well_sd(c.x - S.MAIN_X * side, c.y) < 0.05:
                continue
            keep.append(f)
        mb.faces = keep
    # inner skins: drum (rolled painted edges) and body (structure edge strips, hidden under the flaps / in the well)
    drum_set = set(id(f) for f in drum_faces)
    NS.double_skin(mb, t=0.006, mats=('paint',), inner=lambda f, c: 'interior', select=lambda c: c.y > ylip - FLAP_LE - 0.01, edge_mat='paint')
    NS.double_skin(mb, t=0.006, mats=('paint',), inner=lambda f, c: 'interior', select=lambda c: c.y < yb + 0.01 and c.y > yend - 0.5)
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / len(rings[-1]), 'paint', V((0, -1, 0)), uvfunc=lambda p: (p.x, p.z))
    # --- dark band under the flaps + the 16 cowl flaps
    yA, yB = ylip - FLAP_LE - 0.005, ylip - FLAP_TE + 0.01
    for k in range(N_FLAPS):
        a0 = 2 * math.pi * (k + 0.03) / N_FLAPS; a1 = 2 * math.pi * (k + 0.97) / N_FLAPS
        am = (a0 + a1) / 2
        dirm = V((math.sin(am), 0, math.cos(am)))
        if _flap_skip(kind, side, V((cx, (yA + yB) / 2, za)) + dirm * R):
            continue
        segs = 3
        for q in range(segs):
            aa, bb = a0 + (a1 - a0) * q / segs, a0 + (a1 - a0) * (q + 1) / segs
            P = lambda a, y, r: V((cx + r * math.sin(a), y, za + r * math.cos(a)))
            # flap: LE tucked 8 mm under the drum's trailing edge, TE flared onto the body
            o = [P(aa, yA, R - 0.008), P(bb, yA, R - 0.008), P(bb, yB, FLAP_TE_R[kind]), P(aa, yB, FLAP_TE_R[kind])]
            rad = V((math.sin((aa + bb) / 2), 0, math.cos((aa + bb) / 2)))
            oriented_quad(mb, o, 'paint', rad)
            oriented_quad(mb, [p - rad * 0.005 for p in o], 'metal_dark', -rad)
        # side edges of the flap (thickness) so the gap reads as a slot
        for aa in (a0, a1):
            P = lambda a, y, r: V((cx + r * math.sin(a), y, za + r * math.cos(a)))
            tg = V((math.cos(aa), 0, -math.sin(aa))) * (1 if aa == a1 else -1)
            q4 = [P(aa, yA, R - 0.008), P(aa, yB, FLAP_TE_R[kind]), P(aa, yB, FLAP_TE_R[kind] - 0.005), P(aa, yA, R - 0.013)]
            oriented_quad(mb, q4, 'metal_dark', tg)
    # band: a dark ring under the flaps, 3.5 cm inside the skin line (seen through the flap gaps)
    band = [circle_pts(V((cx, ylip - FLAP_LE, za)), V((0, 1, 0)), R - 0.006, N, ref=V((0, 0, 1)))]      # from the drum's inner skin
    for y in (ylip - FLAP_LE - 0.04, ylip - FLAP_TE + 0.005):
        rs, top, bot = nac_profile(kind, y)
        band.append(circle_pts(V((cx, y, za)), V((0, 1, 0)), rs - 0.035, N, ref=V((0, 0, 1))))
    nb0 = len(mb.faces)
    loft(mb, band, 'metal_dark', closed=True)
    if kind == 'inner':
        kb = mb.faces[:nb0]
        for f in mb.faces[nb0:]:
            P_ = [mb.verts[k] for k in f['idx']]
            if not _flap_skip(kind, side, sum(P_, V()) / len(P_)):
                kb.append(f)
        mb.faces = kb
    return mb


def well_part(kind, side, parent):
    """lip round the opening (paint, 4 mm proud, 10 cm wide) + liner box (well) from the skin to the roof."""
    s = 'L' if side < 0 else 'R'
    xm = S.MAIN_X * side
    w = MeshBuf()
    ol = well_outline()
    def skin_pt(u, y, lift=0.0):
        x = xm + u
        return V((x, y, zskin_bottom(kind, x, y, side) - lift))
    n = len(ol)
    # outward (away from the opening) unit normal per outline vertex: average of the two adjacent edge normals (continuous lip)
    def edge_n(i):
        (u0, y0), (u1, y1) = ol[i], ol[(i + 1) % n]
        L = math.hypot(u1 - u0, y1 - y0)
        nu, ny = (y1 - y0) / L, -(u1 - u0) / L
        mu, my = (u0 + u1) / 2, (y0 + y1) / 2
        if well_sd(mu + nu * 0.01, my + ny * 0.01) < well_sd(mu, my):
            nu, ny = -nu, -ny
        return nu, ny
    en = [edge_n(i) for i in range(n)]
    vn = []
    for i in range(n):
        a, b = en[i - 1], en[i]
        nu, ny = a[0] + b[0], a[1] + b[1]
        L = math.hypot(nu, ny) or 1.0
        vn.append((nu / L, ny / L))
    inn = [skin_pt(u, y, 0.004) for (u, y) in ol]
    outr = [skin_pt(u + nu * 0.10, y + ny * 0.10, 0.004) for (u, y), (nu, ny) in zip(ol, vn)]
    upp = [p + V((0, 0, 0.035)) for p in inn]
    for i in range(n):
        j = (i + 1) % n
        oriented_quad(w, [inn[i], inn[j], outr[j], outr[i]], 'paint', V((0, 0, -1)))
        nu, ny = en[i]
        oriented_quad(w, [inn[i], inn[j], upp[j], upp[i]], 'paint', V((-nu, -ny, 0)))
        oriented_quad(w, [outr[i] + V((0, 0, 0.003)), outr[j] + V((0, 0, 0.003)), inn[j] + V((0, 0, 0.003)), inn[i] + V((0, 0, 0.003))], 'well', V((0, 0, 1)))
    # liner box above the opening: walls at u = +-WELL_U (y 1.35-3.72), front / rear walls, roof
    y0, y1 = WELL_BOX_Y
    ys_ = [y0 + (y1 - y0) * k / 16 for k in range(17)]
    for uu, d in ((-WELL_U, 1), (WELL_U, -1)):
        for ya, yb in zip(ys_, ys_[1:]):
            za_, zb_ = zskin_bottom(kind, xm + uu, ya, side) + 0.012, zskin_bottom(kind, xm + uu, yb, side) + 0.012
            q = [V((xm + uu, ya, za_)), V((xm + uu, yb, zb_)), V((xm + uu, yb, WELL_ROOF)), V((xm + uu, ya, WELL_ROOF))]
            oriented_quad(w, q, 'well', V((d * side * 0 + d, 0, 0)))
            oriented_quad(w, [p - V((d * 0.004, 0, 0)) for p in q], 'well', V((-d, 0, 0)))
    us_ = [-WELL_U + 2 * WELL_U * k / 8 for k in range(9)]
    for yy, d in ((y0, 1), (y1, -1)):
        for ua, ub in zip(us_, us_[1:]):
            q = [V((xm + ua, yy, zskin_bottom(kind, xm + ua, yy, side) + 0.012)), V((xm + ub, yy, zskin_bottom(kind, xm + ub, yy, side) + 0.012)),
                 V((xm + ub, yy, WELL_ROOF)), V((xm + ua, yy, WELL_ROOF))]
            oriented_quad(w, q, 'well', V((0, d, 0)))
            oriented_quad(w, [p - V((0, d * 0.004, 0)) for p in q], 'well', V((0, -d, 0)))
    q = [V((xm - WELL_U, y0, WELL_ROOF)), V((xm + WELL_U, y0, WELL_ROOF)), V((xm + WELL_U, y1, WELL_ROOF)), V((xm - WELL_U, y1, WELL_ROOF))]
    oriented_quad(w, q, 'well', V((0, 0, -1)))
    oriented_quad(w, [p + V((0, 0, 0.004)) for p in q], 'well', V((0, 0, 1)))
    # roof ribs (structure, as the reference well's ceiling)
    for k in range(1, 6):
        yy = y0 + (y1 - y0) * k / 6
        box(w, (xm, yy, WELL_ROOF - 0.03), (2 * WELL_U - 0.02, 0.025, 0.05), 'structure')
    return Part(f'gear_well_{s}', parent, mesh=w, info={'kind': 'well', 'v': '1.8.3'})


def engine_front(kind, side):
    """engine part: rolled lip ring (olive drab anti-glare ring), the inner wall back to the engine, baffle disc, nose case + shaft."""
    num = S.ENGINE_NUM[(side, kind)]
    xa, za, ylip, yprop, R, yend, zb = S.NACELLES[kind]
    cx = xa * side
    ax = V((cx, ylip, za))
    e = MeshBuf()
    prof = [(R, -0.10), (R * 0.998, -0.05), (R * 0.985, -0.02), (R * 0.962, -0.004), (R * 0.93, 0.0), (R * 0.895, -0.006),
            (R * 0.868, -0.025), (R * 0.852, -0.055), (R * 0.848, -0.09)]
    rings = [circle_pts(ax + V((0, dy, 0)), V((0, 1, 0)), r, 48, ref=V((0, 0, 1))) for r, dy in prof]
    loft(e, rings, 'cowl_ring', closed=True, outward=True)
    # inner wall (dark) from the lip back past the engine face to the baffle
    wall = [circle_pts(ax + V((0, dy, 0)), V((0, 1, 0)), R * 0.848, 48, ref=V((0, 0, 1))) for dy in (-0.09, -0.30, -0.55)]
    loft(e, wall, 'metal_dark', closed=True, outward=False)
    loft(e, [[p + (p - V((cx, p.y, za))).normalized() * 0.004 for p in r_] for r_ in wall], 'cowl_ring', closed=True, outward=True)
    NS.disc(e, wall[-1], ax + V((0, -0.55, 0)), 'metal_dark', V((0, 1, 0)))
    cylinder(e, ax + V((0, -0.20, 0)), V((cx, yprop - 0.02, za)), 0.17, 0.12, N=20, mat='cowl')     # nose case + shaft into the hub
    out = [Part(f'engine_{num}', f'nacelle_{num}', pivot=ax, mesh=e, info={'kind': 'engine', 'engine': num, 'cowl_r': R})]
    out.append(Part(f'prop_{num}', f'engine_{num}', pivot=V((cx, yprop, za)), info={'kind': 'prop', 'engine': num, 'radius': S.PROP_R}))
    ty = TURBO_Y[kind]
    out.append(Part(f'exhaust_{num}', f'engine_{num}', pivot=V((cx, ty - 0.40, nac_profile(kind, ty)[2])), info={'kind': 'ir_source'}))
    return out


# ============================================================================================ turbo + exhaust (engine part)
def _skin_pt(kind, side, y, ang_deg, lift):
    """point on the nacelle skin at y, angle from the bottom (0) toward outboard (+), lifted `lift` along the outward normal."""
    xa, za = S.NACELLES[kind][0], S.NACELLES[kind][1]
    rs, top, bot = nac_profile(kind, y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    a = math.radians(ang_deg)
    sx, cz_ = math.sin(a), -math.cos(a)
    n = 2.2
    x = xa * side + side * rs * math.copysign(abs(sx) ** (2 / n), sx)
    z = cz + hz * math.copysign(abs(cz_) ** (2 / n), cz_)
    nrm = V((side * sx / max(rs, 1e-3), 0, cz_ / max(hz, 1e-3))).normalized()
    return V((x, y, z)) + nrm * lift


def _pipe(mb, pts, r, mat, N=12):
    for a, b in zip(pts, pts[1:]):
        cylinder(mb, a, b, r, N=N, mat=mat, cap0=False, cap1=False)
    for p in pts[1:-1]:                       # joint balls hide the mitre gaps
        cylinder(mb, p - V((0, 0, r * 0.98)), p + V((0, 0, r * 0.98)), r * 1.0, N=N, mat=mat)


def turbo(kind, side):
    """GE B-22 on the nacelle belly. Returns (mb, exhaust exit point)."""
    xa, za, ylip, yprop, R, yend, zb = S.NACELLES[kind]
    ty = TURBO_Y[kind]
    x = xa * side
    zs = nac_profile(kind, ty)[2]
    c = V((x, ty, zs + 0.004))
    up = V((0, 0, 1))
    mb = MeshBuf()
    # recess ring in the skin (dark gap round the housing)
    annulus(mb, circle_pts(c - up * 0.002, up, 0.315, 32), circle_pts(c - up * 0.002, up, 0.27, 32), 'metal_dark', V((0, 0, -1)))
    # scroll housing: a squat drum + the volute torus round it (rust)
    TM = 'turbo' if TURBO_MAT_185E else 'exhaust'
    cylinder(mb, c + up * 0.10, c - up * 0.08, 0.255, 0.255, N=32, mat=TM, cap0=False)
    vc = c - up * 0.045
    vr = []                       # volute: one smooth scroll (tube radius 0.035 -> 0.075 round the housing), lofted
    for k in range(49):
        a = 2 * math.pi * k / 48 * 0.96
        r = 0.035 + 0.040 * k / 48
        cen = vc + V((math.cos(a), math.sin(a), 0)) * (0.255 + r * 0.45)
        tg = V((-math.sin(a), math.cos(a), 0))
        vr.append(circle_pts(cen, tg, r, 14, ref=V((0, 0, 1))))
    loft(mb, vr, TM, closed=True, outward=True)
    fan_cap(mb, vr[0], sum(vr[0], V()) / len(vr[0]), TM, -V((0, 1, 0)))
    fan_cap(mb, vr[-1], sum(vr[-1], V()) / len(vr[-1]), TM, V((-math.sin(2 * math.pi * 0.96), math.cos(2 * math.pi * 0.96), 0)))
    # bucket-wheel face: dark disc, 24 radial buckets, hub cap
    fan_cap(mb, circle_pts(c - up * 0.081, up, 0.23, 32), c - up * 0.081, 'metal_dark', V((0, 0, -1)))
    for k in range(16):
        a = 2 * math.pi * k / 16
        d = V((math.cos(a), math.sin(a), 0))
        box(mb, c - up * 0.090 + d * 0.15, (0.14, 0.010, 0.016), 'metal_dark', rot=Euler((0, 0, math.atan2(d.y, d.x))))
    cylinder(mb, c - up * 0.08, c - up * 0.125, 0.075, 0.05, N=16, mat='exhaust')
    # turbine exhaust / waste-gate stub: aft and down from the housing rim (its mouth = the IR source)
    s0 = c + V((0, -0.24, -0.03)); s1 = s0 + V((0, -0.17, -0.07))
    cylinder(mb, s0, s1, 0.075, 0.07, N=16, mat='metal_dark', cap1=False)
    annulus(mb, circle_pts(s1, s1 - s0, 0.07, 16), circle_pts(s1 + (s0 - s1).normalized() * 0.02, s1 - s0, 0.05, 16), 'metal_dark', s1 - s0)
    fan_cap(mb, circle_pts(s1 + (s0 - s1).normalized() * 0.05, s1 - s0, 0.05, 16), s1 + (s0 - s1).normalized() * 0.05, 'cove', s1 - s0)
    # compressor outlet (intercooler duct): elbow from the housing side, forward and up into the nacelle belly
    e0 = c + V((-side * 0.21, 0.10, 0.02)); e1 = e0 + V((-side * 0.05, 0.24, 0.0)); e2 = e1 + V((-side * 0.02, 0.16, 0.20))
    _pipe(mb, [e0, e1, e2], 0.06, 'exhaust')
    # exhaust inlet: elbow from the housing's outboard side forward and up into the nacelle (the pipe runs inside from there)
    i0 = c + V((side * 0.22, 0.12, 0.03)); i1 = i0 + V((side * 0.08, 0.30, 0.02)); i2 = i1 + V((side * 0.06, 0.22, 0.24))
    _pipe(mb, [i0, i1, i2], 0.075, 'exhaust')
    # exhaust pipe from the collector ring (behind the cowl flaps) outside along the nacelle in a dark channel (reference), then in
    if kind == 'inner':
        ang, ys_ = 80, (ylip - FLAP_TE + 0.02, 3.0, 2.5, 2.1)
    else:
        ang, ys_ = 12, (ylip - FLAP_TE + 0.02, 2.6, 2.2, 1.95)
    pts = [_skin_pt(kind, side, y, ang, 0.012) for y in ys_]
    _pipe(mb, pts, 0.058, 'exhaust')
    for dang in (-9, 9):           # channel: dark strips either side of the pipe, 2 mm proud of the skin
        a_ = [_skin_pt(kind, side, y, ang + dang * 0.55, 0.002) for y in ys_]
        b_ = [_skin_pt(kind, side, y, ang + dang * 1.25, 0.002) for y in ys_]
        for k in range(len(ys_) - 1):
            out_ = (a_[k] - V((S.NACELLES[kind][0] * side, a_[k].y, S.NACELLES[kind][1]))).normalized()
            oriented_quad(mb, [a_[k], a_[k + 1], b_[k + 1], b_[k]], 'metal_dark', out_)
    for p0, p1 in ((pts[0], pts[1]), (pts[-1], pts[-2])):      # collars where the pipe leaves / enters the skin
        annulus(mb, circle_pts(p0, p1 - p0, 0.078, 12), circle_pts(p0, p1 - p0, 0.058, 12), 'metal_dark', p1 - p0)
        fan_cap(mb, circle_pts(p0, p1 - p0, 0.058, 12), p0, 'cove', p0 - p1)
    return mb, s1


def turbo_legacy(kind, side, nac_profile_old):
    """the 1.8.2 turbo (b17g_detail.turbo on the 1.8.2 profile): collider source only (engine_n_hullsrc), never rendered in game."""
    import b17g_detail as D
    return D.turbo(kind, side, nac_profile_old)[0]


# ============================================================================================ leading-edge intakes
def le_intakes(parts, wing_station):
    """cut real openings into the wing leading edge (the wing has stations at their edges), box them (dark) with grille bars."""
    by = {p.name: p for p in parts}
    stats = {}
    for side in (-1, 1):
        s = 'L' if side < 0 else 'R'
        for x0, x1 in LE_INTAKES:
            name = ('wing_inner_' if (x0 + x1) / 2 < S.WING_SPLITS[0] else 'wing_mid_' if (x0 + x1) / 2 < S.WING_SPLITS[1] else 'wing_outer_') + s
            p = by[name]
            xm = (x0 + x1) / 2
            st = wing_station(xm, side)
            le = st.point(0.0, True)
            h = LE_INTAKE_H
            # drop LE faces inside the opening (both skins): centre within the x range, within h/2 of the LE height, near the LE
            keep = []
            for f in p.mesh.faces:
                P = [p.mesh.verts[k] for k in f['idx']]
                c = sum(P, V()) / len(P)
                if x0 + 0.002 < abs(c.x) < x1 - 0.002 and abs(c.z - le.z) < h / 2 and c.y > le.y - 0.16 and f['mat'] in ('paint', 'interior', 'structure'):
                    continue
                keep.append(f)
            p.mesh.faces = keep
            mb = MeshBuf()
            yf, yb = le.y + 0.012, le.y - 0.14
            zt, zb_ = le.z + h / 2, le.z - h / 2
            xa_, xb_ = x0 * side, x1 * side
            # box: top / bottom / sides / back (dark inside, paint outside where it can be seen from outside: none - inside the wing)
            for zz, d in ((zt, -1), (zb_, 1)):
                q = [V((xa_, yf, zz)), V((xb_, yf, zz)), V((xb_, yb, zz)), V((xa_, yb, zz))]
                oriented_quad(mb, q, 'metal_dark', V((0, 0, d)))
                oriented_quad(mb, [v + V((0, 0, -d * 0.004)) for v in q], 'paint', V((0, 0, -d)))
            for xx in (xa_, xb_):
                d = 1 if (xx - (xa_ + xb_) / 2) < 0 else -1
                q = [V((xx, yf, zt)), V((xx, yf, zb_)), V((xx, yb, zb_)), V((xx, yb, zt))]
                oriented_quad(mb, q, 'metal_dark', V((d, 0, 0)))
                oriented_quad(mb, [v + V((-d * 0.004, 0, 0)) for v in q], 'paint', V((-d, 0, 0)))
            q = [V((xa_, yb, zt)), V((xb_, yb, zt)), V((xb_, yb, zb_)), V((xa_, yb, zb_))]
            oriented_quad(mb, q, 'cove', V((0, 1, 0)))
            # frame lip round the mouth (paint, 1.2 cm proud of the cut)
            for a, b in ((V((xa_, yf, zt)), V((xb_, yf, zt))), (V((xa_, yf, zb_)), V((xb_, yf, zb_))),
                         (V((xa_, yf, zt)), V((xa_, yf, zb_))), (V((xb_, yf, zt)), V((xb_, yf, zb_)))):
                NS.sec_tube(mb, a, b, 0.02, 0.02, V((0, 1, 0)), mat='paint')
            # grille: horizontal bars across the mouth, 3 cm behind it
            nb = int(h / 0.035)
            for k in range(1, nb):
                zz = zb_ + h * k / nb
                NS.sec_tube(mb, V((xa_, yf - 0.03, zz)), V((xb_, yf - 0.03, zz)), 0.008, 0.012, V((0, 0, 1)), mat='metal_dark')
            p.mesh.extend(mb)
            stats[name] = stats.get(name, 0) + mb.tri_count()
    return stats
