"""FD-32 Nimrod, Heritage Pairs 1.8.3 (offline B): canopy redesign + cockpit opening rebuilt on the stretched skin + raised spine.

User (1.7.13 review): "the canopy needs a complete redesign, right now it looks so stupid"; "mesh issues on the cockpit/fuselage edge".
The 1.5-1.8 canopy was a 1.42 m flat-sided bubble (vertical sides, flat top) behind an upright 30 mm hoop, ending in a flat plate on a
bare deck; the cockpit hole was the Mk I's rectangular cut (cells above z 0.50) whose edge stepped between the stations (0.474 / 0.500 /
0.516 m) and was hidden by 4 mm skirts.

Stock method (AssetRipper export, SmallFighter1 / Fighter1 / COIN prefabs): a canopyFrame object painted with the skin material (Canopy
component) carries the exterior glass (`canopy`) and cockpit-layer copies (`canopyFrame_int`, `canopy_int`); the frames are slim and
painted; the bubble's rear is faired into a raised spine. The cockpit-layer glass stays our 1.8.1 faint URP-Lit copy (FD32Build).

New layout (Blender frame, after the 0.40 m stretch; eye (0, -0.92, 0.745)):
  windscreen  one-piece wrap screen from a base line on the decking at y -0.26 to a vertical arch at y -0.66 (top 1.015), blown 3 cm,
              slim painted arch (30 mm), base lip; its sides run down onto the sill rails
  hood        bubble from the arch to y -1.615: elliptical section with 2 cm tumblehome over the sill, top 1.065 over the head (head
              top ~0.92, stock seat head box 1.014), dropping to 0.995 at the rear bow; slim painted bows (30 / 40 mm) and sill frames;
              tilts up 30 deg about the top of its rear bow (stock Canopy hinge, as before), jettisoned whole
  rails       a rounded sill rail on each side along the canopy footprint (covers the hole edge), painted
  opening     the fus_center skin above ring index jc (z >= 0.44 on every cockpit station) is rebuilt over the cockpit rows on the
              loft's own bilinear surface with the hole cut on a smooth plan outline (superellipse, half width 0.33), inner skin
              doubled, and a 10 cm coaming wall down from the hole edge (no gap between skin and the cockpit lining)
  spine       raised turtle deck from the hood's rear bow to the fin leading edge (y -4.08, z 0.36), section continuing the hood's,
              its lower edge embedded 8 mm in the skin; split at the fus_center / fus_rear joint with structure caps
  collider    the FD32 root collider is baked from the convex hull of the 1.8.2 fus_center skin (computed here from the generator BEFORE
              the opening rebuild; contract collider_fus_center), so CoM / inertia of the root body do not change
Cannot do: the hood does not slide (stock Canopy = hinge rotation only); the spine is visual (not in any collider, no drag change).
"""
import math
from mathutils import Vector as V
from mathutils.kdtree import KDTree
import nimrod_spec as S
import nimrod_structure as ST
import nimrod_parts as NP
import fd32_spec as FS
from b25h_geom import MeshBuf, loft, fan_cap, oriented_quad
from b25h_parts import Part

ENABLED = True                      # 1.8.3 canopy / opening / spine (False = the 1.8.2 canopy, fd32_parts.build_canopy_fd32)
WS_BASE_Y = -0.22                   # 1.8.3 polish: base at the gun troughs' rear end, raked front ~33 deg
ARCH_Y = -0.72
HOOD_REAR_Y = -1.615
RAIL_X = 0.342                      # sill rail centre line (rail radius RAIL_R) from the windscreen base to RAIL_TAPER_Y
RAIL_R = 0.016
RAIL_DARK_185E = True               # 1.8.5 offline E (in-game 1.8.3 F4): the thin painted rail tube took a sliver of the livery atlas and read as a
                                    # yellow-olive line along the left sill from the screen base; the tube is drawn metal_dark like the arch / sill frames
                                    # (the painted skirt under it stays paint). False = 1.8.4 (painted tube)
RAIL_TAPER = (-1.20, -1.625, 0.300)  # the footprint narrows from RAIL_X at y0 to x1 at y1 (the bubble's rear)
HOLE = dict(y_front=-0.40, y_rear=-1.45, hw=0.330, m_front=8.0, m_rear=4.0, zcut=0.44)
PATCH_Y = (-0.40, -1.71)            # 1.8.3 polish: the rebuilt skin rows reach aft under the hood's rear (the skin drops there)
TUMBLE = (0.08, 0.24)               # ellipse centre this far above the sill, lower semi-axis: x(sill) = 0.943 W
# one top line for the hood and the spine (the bubble flows into the spine; the spine starts 8 mm under the hood's rear bow)
TOP_LINE = [(-0.72, 0.910), (-0.80, 0.965), (-0.90, 1.025), (-1.02, 1.064), (-1.15, 1.064), (-1.30, 1.048), (-1.50, 1.008), (-1.615, 0.980),
            (-1.90, 0.918), (-2.30, 0.832), (-2.80, 0.700), (-3.30, 0.562), (-3.75, 0.442), (-4.08, 0.360)]
WS_RAKE_DEG = 33.0                  # the windscreen's centre line runs straight from the base on the deck to the arch at this rake
FRAME = dict(arch=0.022, rear=0.020, sill=0.015, out=0.005)     # slim dark frames (stock FS-12 / KR-67: ~3-4 cm visible)
HOOD_TOP = TOP_LINE
SPINE_TOP = TOP_LINE
SPINE_END_Y = -4.08
SPINE_OPEN = True                   # 2026-11-22: no structure caps at the y -1.90 split (open, dark-lined fairing)
SPINE_SPLIT_Y = None                # = S.CENTRE_AFT_Y after the stretch (-1.90)
WALL_DEPTH = 0.10
N_SEC = 16                          # points per canopy section (sill to sill)

_CAP = {}


# ----------------------------------------------------------------------------------------------- small math
def pchip(tab, x):
    xs = [a for a, b in tab]; ys = [b for a, b in tab]
    if xs[0] > xs[-1]:
        xs = xs[::-1]; ys = ys[::-1]
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    dl = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = dl[0], dl[-1]
    for i in range(1, n - 1):
        if dl[i - 1] * dl[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / dl[i - 1] + w2 / dl[i])
    for i in range(n - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / h[i]
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t; h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
            return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]
    return ys[-1]


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------------------------------------- the stretched skin (exact)
def capture():
    """call BEFORE the stretch (fd32_spec.apply_stretch shifts S.FUS / S.COCKPIT_Y / S.CENTRE_AFT_Y): the pre-stretch fuselage station
    rings of all three skin segments (NP.fus_ring2 = the loft's own rings), stored in the post-stretch frame."""
    assert not getattr(S, '_fd32_stretched', False), 'capture() must run before fd32_spec.apply_stretch()'
    ys = NP.fus_stations()
    L, ycut = FS.STRETCH_L, FS.STRETCH_Y
    rings = []
    for y in ys:
        r = NP.fus_ring2(y)
        rp = [V((p.x, p.y - L if p.y < ycut else p.y, p.z)) for p in r]
        rings.append((rp[0].y, rp))
    rings.sort(key=lambda t: -t[0])
    _CAP['rings'] = rings
    _CAP['ck_pre'] = tuple(S.COCKPIT_Y)
    _CAP['n'] = len(rings[0][1])
    return len(rings)


def _ring_at(y):
    rings = _CAP['rings']
    if y >= rings[0][0]:
        return rings[0][1]
    for (ya, ra), (yb, rb) in zip(rings, rings[1:]):
        if ya >= y >= yb:
            t = 0.0 if ya == yb else (ya - y) / (ya - yb)
            return [a.lerp(b, t) for a, b in zip(ra, rb)]
    return rings[-1][1]


def deck_z(x, y):
    """z of the (stretched) skin's upper arc at |x| on station y, on the loft's own surface (lerp between the station rings)."""
    r = _ring_at(y)
    n = len(r)
    ax = abs(x)
    up = r[:n // 2 + 1]                 # point 0 = top centre, going to +x and down
    for a, b in zip(up, up[1:]):
        if (a.x - ax) * (b.x - ax) <= 0 and abs(b.x - a.x) > 1e-9:
            t = (ax - a.x) / (b.x - a.x)
            return a.z + (b.z - a.z) * t
    return up[-1].z


def hole_hx(y):
    h = HOLE
    a = (h['y_front'] - h['y_rear']) / 2; yc = (h['y_front'] + h['y_rear']) / 2
    t = (y - yc) / a
    if abs(t) >= 1.0:
        return 0.0
    m = h['m_front'] if t > 0 else h['m_rear']
    return h['hw'] * (1 - abs(t) ** m) ** (1.0 / m)


def rail_x(y):
    y0, y1, x1 = RAIL_TAPER
    if y >= y0:
        return RAIL_X
    return RAIL_X + (x1 - RAIL_X) * smooth01((y0 - y) / (y0 - y1))


_SILL = {}


def rail_line(y):
    """1.8.3 polish: one smooth, nearly straight sill line (least-squares quadratic of the skin height under the rail over the
    footprint); the rebuilt skin under the rail is shifted onto it (rebuild_opening / _to_sill), so the hood sits on a clean sill."""
    if 'c' not in _SILL:
        y0, y1 = WS_BASE_Y - 0.01, HOOD_REAR_Y
        ys = [y0 + (y1 - y0) * k / 60 for k in range(61)]
        zs = [deck_z(rail_x(y), y) for y in ys]
        us = [(y - y0) / (y1 - y0) for y in ys]
        A = [[sum(u ** (i + j) for u in us) for j in range(3)] for i in range(3)]
        b = [sum(z * u ** i for u, z in zip(us, zs)) for i in range(3)]
        for i in range(3):
            for k in range(i + 1, 3):
                f = A[k][i] / A[i][i]
                A[k] = [a - f * c for a, c in zip(A[k], A[i])]; b[k] -= f * b[i]
        c = [0.0] * 3
        for i in range(2, -1, -1):
            c[i] = (b[i] - sum(A[i][j] * c[j] for j in range(i + 1, 3))) / A[i][i]
        lift = max(z - sum(c[i] * u ** i for i in range(3)) for u, z in zip(us, zs))   # upper envelope: the skin is only raised onto it
        _SILL.update(c=c, y0=y0, y1=y1, lift=lift)
    u = (y - _SILL['y0']) / (_SILL['y1'] - _SILL['y0'])
    return sum(_SILL['c'][i] * u ** i for i in range(3)) + _SILL['lift']


def rail_z(y):
    return rail_line(y) - 0.004


def sill_z(y):
    return rail_z(y) + RAIL_R * 0.75


# ----------------------------------------------------------------------------------------------- sections
def section(y, xs, zs, zt, N=N_SEC, off=0.0):
    """canopy-family section at station y: sill points (+-xs, zs), top zt; ellipse centre TUMBLE[0] above the sill, lower semi-axis
    TUMBLE[1] (x(sill) = 0.943 W: 2 cm tumblehome), upper part a superellipse (exponent 2.25). Points from the right sill over the top
    to the left sill; `off` grows the section outward (frames)."""
    dz, hd = TUMBLE
    W = xs / math.sqrt(1 - (dz / hd) ** 2)
    zc = zs + dz
    hu = zt - zc
    th0 = -math.asin(dz / hd)
    pts = []
    for k in range(N + 1):
        th = th0 + (math.pi - 2 * th0) * k / N
        c, s_ = math.cos(th), math.sin(th)
        if s_ >= 0:
            e = 2.25
            x = (W + off) * math.copysign(abs(c) ** (2 / e), c)
            z = zc + (hu + off) * abs(s_) ** (2 / e)
        else:
            x = (W + off) * c
            z = zc + (hd + off) * s_
        pts.append(V((x, y, z)))
    return pts, V((0, y, zc))


def hood_section(y, off=0.0, N=N_SEC):
    return section(y, rail_x(y), sill_z(y), pchip(HOOD_TOP, y), N, off)


SPINE_START_Y = None                # = HOOD_REAR_Y + 0.020: the spine starts 2 cm inside the hood, under its 40 mm rear bow (no slit)


def spine_section(y, N=N_SEC):
    """1.8.3 polish: the spine starts 1 cm inside the hood on the hood's own outline (2 mm in) and continues its top line and sill
    line; over 0.25 m behind the hood its sides sink onto the skin (8 mm embedded) and it narrows to the fin's leading edge."""
    if y >= HOOD_REAR_Y:
        r, c = section(y, rail_x(y) - 0.002, sill_z(y) - 0.001, pchip(HOOD_TOP, y) - 0.002, N)
        return r, c
    u = (HOOD_REAR_Y - y) / (HOOD_REAR_Y - SPINE_END_Y)
    u = max(0.0, min(1.0, u))
    x0 = rail_x(HOOD_REAR_Y) - 0.002
    xs = 0.02 + (x0 - 0.02) * (1 - u) ** 1.25
    zt = pchip(SPINE_TOP, y) - 0.002 * (1 - u)
    b = smooth01((HOOD_REAR_Y - y) / 0.25)                       # 0 at the hood: sill line; 1 after 0.25 m: embedded in the skin
    zs = (1 - b) * (sill_z(y) - 0.001) + b * (deck_z(xs, y) - 0.008)
    zs = min(zs, deck_z(xs, y) + 0.012)
    zt = max(zt, zs + 0.03)
    return section(y, xs, zs, zt, N)


# ----------------------------------------------------------------------------------------------- helpers
def _quad_strip(mb, A, B, mat, out_ref, flip=False):
    """quads between two polylines A, B (same count); faces oriented away from out_ref(point) (a function returning a reference centre)."""
    for k in range(len(A) - 1):
        q = [A[k], A[k + 1], B[k + 1], B[k]]
        c = sum(q, V()) / 4
        d = c - out_ref(c)
        oriented_quad(mb, q, mat, -d if flip else d, smooth=True)


def frame_band(mb, rings, centres, off_out=0.008, mat='paint', inner_mat='metal_dark', off_in=0.0015):
    """closed frame band on the glass: rings (list of sections) bound it along the band; outer face `off_out` out, inner face 1.5 mm out."""
    def grow(r, c, d):
        return [p + (p - c).normalized() * d for p in r]
    outs = [grow(r, c, off_out) for r, c in zip(rings, centres)]
    ins = [grow(r, c, off_in) for r, c in zip(rings, centres)]
    cen = lambda p: V((0, p.y, centres[0].z))
    for i in range(len(rings) - 1):
        _quad_strip(mb, outs[i], outs[i + 1], mat, lambda p, i=i: V((0, p.y, centres[i].z)))
        _quad_strip(mb, ins[i], ins[i + 1], inner_mat, lambda p, i=i: V((0, p.y, centres[i].z)), flip=True)
    for i, nb in ((0, 1), (len(rings) - 1, len(rings) - 2)):
        dy = rings[i][0].y - rings[nb][0].y
        for k in range(len(rings[i]) - 1):
            oriented_quad(mb, [outs[i][k], outs[i][k + 1], ins[i][k + 1], ins[i][k]], mat, V((0, dy, 0)))
    for k, kn in ((0, 1), (len(rings[0]) - 1, len(rings[0]) - 2)):
        for i in range(len(rings) - 1):
            q = [outs[i][k], outs[i + 1][k], ins[i + 1][k], ins[i][k]]
            oriented_quad(mb, q, mat, (outs[i][k] + outs[i + 1][k]) - (outs[i][kn] + outs[i + 1][kn]))


def side_strip(sec_list, width, side):
    """the first `width` metres of arc from the sill (side 0 = right, 1 = left) of each section: thin sill frames."""
    out = []
    for r in sec_list:
        pts = r if side == 0 else r[::-1]
        acc, strip = 0.0, [pts[0]]
        for a, b in zip(pts, pts[1:]):
            L = (b - a).length
            if acc + L >= width:
                strip.append(a.lerp(b, (width - acc) / L)); break
            acc += L; strip.append(b)
        out.append(strip)
    n = min(len(s) for s in out)
    out = [s[:n] for s in out]
    return out if side == 0 else [s[::-1] for s in out]


def tube_along(mb, pts, r, mat, N=10, up=V((0, 0, 1)), caps=True):
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        u = up.cross(t).normalized(); v = t.cross(u).normalized()
        rings.append([p + (u * math.cos(2 * math.pi * k / N) + v * math.sin(2 * math.pi * k / N)) * r for k in range(N)])
    loft(mb, rings, mat, smooth=True)
    if caps:
        fan_cap(mb, rings[0], pts[0], mat, pts[0] - pts[1])
        fan_cap(mb, rings[-1], pts[-1], mat, pts[-1] - pts[-2])


# ----------------------------------------------------------------------------------------------- canopy parts
def build_windscreen():
    glass, frame = MeshBuf(), MeshBuf()
    arch, ca = hood_section(ARCH_Y)
    M = 10
    base = []
    for p in arch:
        bx = math.copysign(min(abs(p.x), rail_x(WS_BASE_Y)), p.x)
        by = WS_BASE_Y - 0.06 * (abs(bx) / rail_x(WS_BASE_Y)) ** 2            # corners swept back a little (wrap)
        bz = deck_z(bx, by) + 0.002
        if abs(bx) > rail_x(WS_BASE_Y) - 0.03:
            bz = max(bz, sill_z(by))                                          # the side edges start on the sill line
        base.append(V((bx, by, bz)))
    lin = [[b.lerp(a, t / M) for b, a in zip(base, arch)] for t in range(M + 1)]
    rings = []
    for i, r in enumerate(lin):
        t = i / M
        nr = []
        for k, p in enumerate(r):
            km, kp = max(k - 1, 0), min(k + 1, len(r) - 1)
            im, ip = max(i - 1, 0), min(i + 1, M)
            dk = lin[i][kp] - lin[i][km]; di = lin[ip][k] - lin[im][k]
            n = di.cross(dk)
            if n.dot(p - V((0, p.y, ca.z - 0.25))) < 0:
                n = -n
            w = math.sin(math.pi * k / (len(r) - 1)) ** 1.5
            nr.append(p + n.normalized() * 0.008 * math.sin(math.pi * t) * w)     # nearly flat raked front
        rings.append(nr)
    loft(glass, rings, 'glass', closed=False, smooth=True)
    _fix_out(glass, lambda c: V((0, -0.75, 0.55)))
    # 1.8.3 polish: ONE slim dark arch (22 mm) over the screen / hood joint, 5 mm proud
    rf = [a.lerp(b, (FRAME['arch'] * 0.5) / max((a - b).length, 1e-6)) for a, b in zip(rings[-1], rings[-2])]
    hb, chb = hood_section(ARCH_Y - FRAME['arch'] * 0.5)
    frame_band(frame, [rf, rings[-1], hb], [V((0, rf[0].y, ca.z)), ca, chb], off_out=FRAME['out'], mat='metal_dark', off_in=0.0025)
    # base lip on the decking along the screen's front edge (closed tube, painted)
    lip = [V((p.x * 0.995, p.y + 0.004, p.z + 0.004)) for p in base]
    tube_along(frame, lip, 0.006, 'metal_dark', N=6)
    return glass, frame, base


def _fix_out(mb, centre_fn):
    """orient every face of mb away from centre_fn(face centre)."""
    for f in mb.faces:
        P = [mb.verts[i] for i in f['idx']]
        n = (P[1] - P[0]).cross(P[-1] - P[0])
        c = sum(P, V()) / len(P)
        if n.dot(c - centre_fn(c)) < 0:
            f['idx'] = list(reversed(f['idx']))
            if f.get('uv'):
                f['uv'] = list(reversed(f['uv']))


def hood_ys():
    n = 16
    return [ARCH_Y - 0.002 - (ARCH_Y - 0.002 - HOOD_REAR_Y) * k / n for k in range(n + 1)]


def build_hood():
    glass, frame = MeshBuf(), MeshBuf()
    ys = hood_ys()
    secs = [hood_section(y) for y in ys]
    rings = [s[0] for s in secs]
    loft(glass, rings, 'glass', closed=False, smooth=True)
    _fix_out(glass, lambda c: V((0, c.y, pchip(HOOD_TOP, c.y) - 0.40)))
    # 1.8.3 polish: no front bow (the windscreen arch covers the joint); slim dark rear bow and sill frames
    ra, ca = hood_section(HOOD_REAR_Y + FRAME['rear']); rb, cb = hood_section(HOOD_REAR_Y)
    frame_band(frame, [ra, rb], [ca, cb], off_out=FRAME['out'], mat='metal_dark', off_in=0.0025)
    for side in (0, 1):
        st = side_strip(rings, FRAME['sill'], side)
        cs = [s_[1] for s_ in secs]
        frame_band(frame, st, cs, off_out=FRAME['out'] - 0.001, mat='metal_dark', off_in=0.0025)
    hinge = V((0, HOOD_REAR_Y - 0.002, pchip(HOOD_TOP, HOOD_REAR_Y) + FRAME['out']))
    return glass, frame, hinge


def build_rails():
    """rail tubes on the smooth sill line + a painted skirt (both faces) from the rail down 6 mm into the skin where the skin is lower."""
    mb = MeshBuf()
    ys = [WS_BASE_Y + 0.02 - (WS_BASE_Y + 0.02 - (HOOD_REAR_Y - 0.010)) * k / 24 for k in range(25)]
    for s in (-1, 1):
        pts = [V((s * rail_x(y), y, rail_z(y))) for y in ys]
        tube_along(mb, pts, RAIL_R, 'metal_dark' if RAIL_DARK_185E else 'paint', N=7)
        top = [V((s * (rail_x(y) + RAIL_R * 0.55), y, rail_z(y) - RAIL_R * 0.80)) for y in ys]
        bot = [V((p.x, p.y, deck_z(p.x, p.y) - 0.006)) for p in top]
        for a0, a1, b0, b1 in zip(top, top[1:], bot, bot[1:]):
            if min(a0.z - b0.z, a1.z - b1.z) < 0.001:
                continue
            q = [a0, a1, b1, b0]
            oriented_quad(mb, q, 'paint', V((s, 0, 0)), smooth=True)
            oriented_quad(mb, [p - V((s * 0.0015, 0, 0)) for p in q], 'paint', V((-s, 0, 0)), smooth=True)
    return mb


def build_spine():
    """two objects: forward (fus_center, to the split) and aft (fus_rear)."""
    ysplit = S.CENTRE_AFT_Y
    y0 = HOOD_REAR_Y + 0.010
    n_f = 5; n_a = 16
    ys_f = [y0 + (ysplit - y0) * k / n_f for k in range(n_f + 1)]
    ys_a = [ysplit + (SPINE_END_Y - ysplit) * (k / n_a) ** 1.0 for k in range(n_a + 1)]
    out = []
    capset = ((ys_f, ('paint', None)), (ys_a, (None, 'structure'))) if SPINE_OPEN else ((ys_f, ('paint', 'structure')), (ys_a, ('structure', 'structure')))
    for ys, caps in capset:
        mb = MeshBuf()
        secs = [spine_section(y) for y in ys]
        rings = [s[0] for s in secs]
        loft(mb, rings, 'paint', closed=False, smooth=True)
        _fix_out(mb, lambda c: V((0, c.y, deck_z(0.0, c.y) - 0.10)))
        if SPINE_OPEN:
            # 2026-11-22 (break faces opened, r8o pattern): no 'structure' cap in the y -1.90 split plane (each was 0.22 m2, 46 % of
            # the fuselage end). The fairing is lined in metal_dark (a dark cavity, its band and skin edge dark at the split); the
            # forward piece's painted front cap 0.29 m in gets a dark back (the cavity's end wall).
            import nimrod_structure as _ST
            tmp = MeshBuf(); tmp.verts = list(mb.verts); tmp.faces = [dict(f) for f in mb.faces]; n0 = len(tmp.faces)
            _ST.double_skin(tmp, t=0.0015, mats=('paint',), inner=lambda f, c: 'metal_dark', edge_mat='metal_dark')
            add = MeshBuf(); add.verts = tmp.verts; add.faces = tmp.faces[n0:]
            mb.extend(add)
            if caps[0] == 'paint':
                r0 = rings[0]
                cc0 = sum(r0, V()) / len(r0)
                fan_cap(mb, [p - V((0, 0.002, 0)) + (cc0 - p).normalized() * 0.0015 for p in r0], cc0 - V((0, 0.002, 0)), 'metal_dark', V((0, -1, 0)))
        for r, c_, mat, toward, dome in ((rings[0], secs[0][1], caps[0], V((0, 1, 0)), 0.0),
                                         (rings[-1], secs[-1][1], caps[1], V((0, -1, 0)), 0.0)):
            if mat is None:
                continue
            cc = sum(r, V()) / len(r)
            if dome:                                         # painted front bulkhead, domed 3.5 cm forward under the hood's rear bow
                mid = [p.lerp(cc, 0.45) + toward * dome * 0.7 for p in r]
                loft(mb, [r, mid], mat, closed=False, smooth=True)
                _fix_out(mb, lambda c, cc=cc: cc - toward * 0.2) if False else None
                fan_cap(mb, mid, cc + toward * dome, mat, toward)
            else:
                fan_cap(mb, r, cc, mat, toward)
        out.append(mb)
    return out


def build_coaming_wall(edge):
    """vertical coaming wall from the hole edge down WALL_DEPTH (both faces, 1.5 mm apart), cockpit paint."""
    mb = MeshBuf()
    yf, yr = HOLE['y_front'], HOLE['y_rear']
    # sides from behind the instrument panel (y < -0.47: further forward it hid the screens' lower corners) + the rear
    loop = [p for p in edge[1] if p.y < -0.47] + [V((0, yr, deck_z(0.0, yr)))] + [p for p in edge[-1][::-1] if p.y < -0.47]
    loop = [p for i, p in enumerate(loop) if i == 0 or (p - loop[i - 1]).length > 1e-5]
    top = loop
    bot = [p - V((0, 0, WALL_DEPTH)) for p in top]
    cy = sum((p.y for p in loop), 0.0) / len(loop)
    ctr = lambda c: V((0, cy, c.z))
    _quad_strip(mb, top, bot, 'ck_modern', ctr, flip=True)                  # faces the cockpit
    top2 = [p + (p - V((0, cy, p.z))).normalized() * 0.0015 for p in top]
    bot2 = [p - V((0, 0, WALL_DEPTH)) for p in top2]
    _quad_strip(mb, top2, bot2, 'ck_modern', ctr)                            # faces the skin
    return mb


# ----------------------------------------------------------------------------------------------- the opening rebuild
def _to_sill(p, ya, yb, xb):
    """shift the rebuilt skin near the rail by the sill line's offset from the skin (cross-section shape kept, no ledge): fully for
    |x| within rail_x -0.05 .. +0.025, fading to 0 at rail_x - 0.11 inward and at the patch's lower boundary xb - 0.005 outward, and
    within 4 cm of the patch's end stations, so the patch still meets its neighbours exactly."""
    ax = abs(p.x); rx = rail_x(p.y)
    w = smooth01((ax - (rx - 0.11)) / 0.06) * smooth01(((xb - 0.004) - ax) / max((xb - 0.004) - (rx + 0.012), 1e-3))
    w *= smooth01((ya - p.y) / 0.02) * smooth01((p.y - yb) / 0.10)      # rear: a 10 cm ramp behind the hood, under the spine's sides
    if w <= 0.0:
        return p
    return V((p.x, p.y, p.z + w * max(0.0, rail_line(p.y) - deck_z(rx, p.y))))     # raise only: the lining below is never cut


def rebuild_opening(fus_center, fus_center_struct):
    """fus_center / fus_center_struct MeshBufs (stretched): delete the upper arc of the cockpit rows (ring index <= jc both sides)
    and rebuild it with the smooth hole; returns the hole edge {1: [...], -1: [...]} (front -> rear) and stats."""
    rings = _CAP['rings']
    n = _CAP['n']
    ya, yb = PATCH_Y
    ck = [(y, r) for y, r in rings if yb - 1e-4 <= y <= ya + 1e-4]
    # rebuild from the first ring index that lies outside the hole outline (x >= hw + 2.5 cm) and below the old rectangular cut
    # (z <= 0.495) on EVERY cockpit station: the old cut's missing cells are all rebuilt and the hole edge is always found
    jc = 0
    while jc + 1 < n // 2 and not all(r[jc].x >= HOLE['hw'] + 0.025 and r[jc].z <= 0.495 for y, r in ck):
        jc += 1
    top = set()
    pts = []
    for y, r in ck:
        for j in list(range(0, jc + 1)) + list(range(n - jc, n)):
            k = (round(r[j].x, 4), round(r[j].y, 4), round(r[j].z, 4)); top.add(k); pts.append(r[j])
    key = lambda p: (round(p.x, 4), round(p.y, 4), round(p.z, 4))
    # 1) skin: delete every paint face whose corners are all upper-arc ring points of the cockpit stations
    keep, dropped = [], 0
    for f in fus_center.faces:
        if f['mat'] == 'paint' and all(key(fus_center.verts[i]) in top for i in f['idx']):
            dropped += 1; continue
        keep.append(f)
    fus_center.faces = keep
    # 2) inner skin / edge strips of that region in fus_center_struct (every corner within 3 mm of an upper-arc ring point)
    kd = KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    keep, sdrop = [], 0
    for f in fus_center_struct.faces:
        P = [fus_center_struct.verts[i] for i in f['idx']]
        if all(kd.find(p)[2] < 0.003 for p in P) and min(p.y for p in P) >= yb - 1e-3 and max(p.y for p in P) <= ya + 1e-3:
            sdrop += 1; continue
        keep.append(f)
    fus_center_struct.faces = keep
    # 3) the new upper arc with the smooth hole (opening_patch logic on the post-stretch rings), paint + 1 mm inner skin
    patch = MeshBuf()
    edge = {1: [], -1: []}
    for (y0, r0), (y1, r1) in zip(ck, ck[1:]):
        msub = max(2, int(math.ceil((y0 - y1) / 0.03)))
        tq = {round(q / msub, 6) for q in range(msub + 1)}
        for ye in (HOLE['y_front'], HOLE['y_rear']):                                  # 4 mm sub-stations within 3 cm of the hole's front / rear end
            for k in range(1, 8):
                for yy in (ye - 0.004 * k, ye + 0.004 * k):
                    if y1 < yy < y0:
                        tq.add(round((y0 - yy) / (y0 - y1), 6))
        tq = sorted(tq)
        for side in (1, -1):
            jidx = list(range(jc, -1, -1)) if side > 0 else [(n - k) % n for k in range(jc, -1, -1)]
            grid = []
            for t in tq:
                y = y0 + (y1 - y0) * t
                sec = [r0[j].lerp(r1[j], t) for j in jidx]
                hx = hole_hx(y)
                ep = None
                if hx > 1e-6:
                    for p0, p1 in zip(sec, sec[1:]):
                        if abs(p0.x) >= hx >= abs(p1.x):
                            ep = p0.lerp(p1, (abs(p0.x) - hx) / max(abs(p0.x) - abs(p1.x), 1e-9)); break
                row = [p if (ep is None or abs(p.x) >= hx) else ep.copy() for p in sec]
                row = [_to_sill(p, ya, yb, abs(sec[0].x)) for p in row]     # 1.8.3 polish: the skin under the rail onto the sill line
                grid.append(row)
                if ep is not None:
                    edge[side].append(_to_sill(ep, ya, yb, abs(sec[0].x)))
            idx = [[patch.v(p) for p in row] for row in grid]
            for q in range(len(tq) - 1):
                for k in range(len(jidx) - 1):
                    c4 = [idx[q][k], idx[q][k + 1], idx[q + 1][k + 1], idx[q + 1][k]]
                    P_ = [patch.verts[v] for v in c4]
                    if ((P_[2] - P_[0]).cross(P_[3] - P_[1])).length < 1e-8:
                        continue
                    ctr = sum(P_, V()) / 4
                    out = V((ctr.x, 0, ctr.z - 0.0))
                    if ((P_[2] - P_[0]).cross(P_[3] - P_[1])).dot(out) < 0:
                        c4 = c4[::-1]
                    patch.face(c4, 'paint', [(patch.verts[v].x, patch.verts[v].y) for v in c4])
    for sd in edge:
        edge[sd].sort(key=lambda p: -p.y)
        ded = []
        for p in edge[sd]:
            if not ded or (p - ded[-1]).length > 1e-5:
                ded.append(p)
        edge[sd] = ded
    tmp = MeshBuf(); tmp.verts = list(patch.verts); tmp.faces = [dict(f) for f in patch.faces]; n0 = len(tmp.faces)
    ST.double_skin(tmp, t=0.001, mats=('paint',), inner=NP._inner_mat_fus)
    inner = MeshBuf(); inner.verts = tmp.verts; inner.faces = tmp.faces[n0:]
    fus_center.extend(patch)
    fus_center_struct.extend(inner)
    return edge, dict(jc=jc, skin_faces_dropped=dropped, struct_faces_dropped=sdrop, patch_faces=len(patch.faces),
                      edge_pts=(len(edge[1]), len(edge[-1])))


def hull_of(mb, root_c):
    """convex hull (vertices + triangles) of a MeshBuf's vertices, Unity frame relative to the CG root (contract U convention)."""
    import bmesh
    bm = bmesh.new()
    for p in mb.verts:
        bm.verts.new(p)
    r = bmesh.ops.convex_hull(bm, input=bm.verts[:])
    for g in r.get('geom_interior', []) + r.get('geom_unused', []):
        if isinstance(g, bmesh.types.BMVert) and g.is_valid:
            pass
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.verts.index_update()
    verts = [[round(v.co.x - root_c.x, 6), round(v.co.z - root_c.z, 6), round(v.co.y - root_c.y, 6)] for v in bm.verts]
    tris = [[f.verts[0].index, f.verts[1].index, f.verts[2].index] for f in bm.faces]
    bm.free()
    return dict(verts=verts, tris=tris)


def finish(parts):
    """after the stretch: the new canopy parts (names kept: windscreen, windscreen_frame, canopy_slide_hinge, canopy_slide,
    canopy_slide_glass) + canopy_rail, coaming_wall, spine_fwd, spine_aft; rebuilds the opening. Returns (new parts, info)."""
    by = {p.name: p for p in parts}
    fc, fcs = by['fus_center'].mesh, by['fus_center_struct'].mesh
    used = sorted({i for f in fc.faces for i in f['idx']})
    pre_hull_mb = MeshBuf(); pre_hull_mb.verts = [V(fc.verts[i]) for i in used]
    edge, st = rebuild_opening(fc, fcs)
    print('[fd32] 1.8.3 sill: y / skin z under the rail / line z', [(round(y, 2), round(deck_z(rail_x(y), y), 3), round(rail_line(y), 3)) for y in [WS_BASE_Y - k * 0.1 for k in range(15)]])
    ws_g, ws_f, base = build_windscreen()
    hg, hf, hinge = build_hood()
    rails = build_rails()
    sp_f, sp_a = build_spine()
    wall = build_coaming_wall(edge)
    frame_x = NP.frame_x
    out = [Part('windscreen', 'fus_center', (0, WS_BASE_Y, sill_z(WS_BASE_Y)), ws_g, info=dict(kind='glass')),
           Part('windscreen_frame', 'fus_center', (0, WS_BASE_Y, sill_z(WS_BASE_Y)), ws_f, info=dict(kind='frame', note='1.8.3 slim painted arch + base lip')),
           Part('canopy_slide_hinge', 'fus_center', hinge, None, frame=frame_x(V((1, 0, 0))),
                info=dict(kind='hatch_hinge', open_deg=FS.HOOD_OPEN_DEG, note='1.8.3: Canopy hinge at the top of the rear bow: tilts up on the ground, jettisoned whole on ejection')),
           Part('canopy_slide', 'canopy_slide_hinge', hinge, hf, frame=frame_x(V((1, 0, 0))), info=dict(kind='canopy', note='1.8.3 bubble hood: painted bows + sill frames (Canopy component)')),
           Part('canopy_slide_glass', 'canopy_slide', hinge, hg, frame=frame_x(V((1, 0, 0))), info=dict(kind='glass')),
           Part('canopy_rail', 'fus_center', (0, (WS_BASE_Y + HOOD_REAR_Y) / 2, sill_z(-0.9)), rails, info=dict(kind='frame', note='1.8.3 sill rails over the hole edge; not in the collider')),
           Part('coaming_wall', 'fus_center', (0, (HOLE['y_front'] + HOLE['y_rear']) / 2, 0.5), wall, info=dict(kind='coaming', note='1.8.3 coaming wall from the hole edge down 10 cm')),
           Part('spine_fwd', 'fus_center', (0, (HOOD_REAR_Y + S.CENTRE_AFT_Y) / 2, 0.8), sp_f, info=dict(kind='spine', note='1.8.3 raised spine behind the hood; not in the collider')),
           Part('spine_aft', 'fus_rear', (0, (S.CENTRE_AFT_Y + SPINE_END_Y) / 2, 0.6), sp_a, info=dict(kind='spine', note='1.8.3 raised spine to the fin leading edge; not in the collider'))]
    info = dict(opening=st, hinge=[round(c, 4) for c in hinge], hood_y=[ARCH_Y, HOOD_REAR_Y], ws_base_y=WS_BASE_Y,
                hood_top_max=max(z for y, z in HOOD_TOP), rail_x=RAIL_X)
    return out, info, pre_hull_mb
