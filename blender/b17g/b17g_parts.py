"""B-17G exterior parts (Phase B milestone 1): procedural airframe + structure; fal props placed by b17g_props.py.

Every builder returns Part objects (blender/v2/b25h_parts.Part: world-space MeshBuf in the rest pose, pivot, frame, info).
Damage-ready structure (docs/stock_damage_study.md 2/4/11, airframe-build-lessons): outer skin + inner skin (double_skin) with edge
strips, complementary jagged edges at every split (tear_mesh, same seed on both parts), a frame / rib 0.08-0.10 m inside each
split, longeron / spar stubs through the split plane.
"""
import math
from mathutils import Vector as V, Quaternion, Matrix
import b17g_spec as S
from b25h_geom import (MeshBuf, superellipse_ring, circle_pts, loft, fan_cap, annulus, oriented_quad, cylinder, box,
                       planar_uv, Station, box_ring, aft_ring, section_cap, ring_arc_uv, arc_lengths, frame_from_axes, cos_space)
from b25h_parts import Part
import nimrod_structure as NS

TEAR_AMP, TEAR_W = 0.028, 0.14


# ============================================================================================ fuselage
def fus_ring(y, inset=0.0, N=S.FUS_N):
    top, bot, hw, n = S.fus_station(y)
    cz = (top + bot) / 2
    hz = (top - bot) / 2
    ring = superellipse_ring(0.0, y, cz, max(hw - inset, 0.01), max(hz - inset, 0.01), max(hz - inset, 0.01), n=n, N=N)
    return [V((S.fus_pinch(y, p.x, p.z, inset), p.y, p.z)) for p in ring]      # 1.7.8: fin-root pinch of the aft fuselage


# 1.8.8 tail cab glazing edges (S.TAIL_CAB): ring stations on every pane / post edge
TAIL_CAB_YS = tuple(sorted({S.TAIL_CAB['small'][0], S.TAIL_CAB['small'][1], S.TAIL_CAB['main'][0], S.TAIL_CAB['main'][1], S.TAIL_CAB['post'][0],
                            S.TAIL_CAB['post'][1], S.TAIL_CAB['aft_face']})) if S.TAIL188 else ()


def fus_stations(y0, y1, step=0.28):
    req = sorted({y0, y1} | {r[0] for r in S.FUS if y1 < r[0] < y0} |
                 {v for v in (S.BAY_Y[0], S.BAY_Y[1], 3.00, 3.25, 3.50, 3.85, 3.97, CHEEK_R_Y[0], CHEEK_R_Y[1], CHEEK_L_Y[0], CHEEK_L_Y[1], S.WINDSCREEN[1], S.NOSE_GLASS_Y, S.RADIO_HATCH[0], S.RADIO_HATCH[1],
                              S.WAIST_R[0], S.WAIST_R[1], S.WAIST_L[0], S.WAIST_L[1], S.TAIL_WIN[0], S.TAIL_WIN[1]) + TAIL_CAB_YS if y1 < v < y0}, reverse=True)
    out = [req[0]]
    for a, b in zip(req, req[1:]):
        k = max(1, int(math.ceil((a - b) / step)))
        out += [a + (b - a) * i / k for i in range(1, k + 1)]
    return out


CHIN_HOLE_R, BALL_HOLE_R = 0.50, 0.72     # round 6: chin opening 0.60 -> 0.50 (cut exactly by b17g_detail.round_hole; drum r 0.475)
CHIN_COLLAR_R0 = CHIN_HOLE_R + 0.01     # inner edge of the chin collar = the opening (the swept pod reaches ~0.58 m; check k includes chin_ring)
TAIL_WELL_HW = 0.19      # 1.6.1: stowed fork plates at +-0.135 + tyre clearance (was 0.25)     # round 3: clear of the swept bodies (check k; ball protrusions reach r 0.623, chin pod 0.47)


def belly_z(x, y):
    top, bot, hw, n = S.fus_station(y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    u = min(abs(x) / hw, 0.999)
    return cz - hz * (1 - u ** n) ** (1 / n)


def belly_flange(mb, c, r0, r1, ztop, N=40):
    """flat collar on the belly skin around a round opening: covers the face-wise cut edge of the skin hole (paint outside, interior
    inside), r0 = opening, r1 = outer edge."""
    ring = lambda r, dz: [V((c.x + r * math.cos(2 * math.pi * k / N), c.y + r * math.sin(2 * math.pi * k / N), 0)) for k in range(N)]
    lo = [V((p.x, p.y, belly_z(p.x, p.y) - 0.012)) for p in ring(r0, 0)]
    hi = [V((p.x, p.y, belly_z(p.x, p.y) - 0.012)) for p in ring(r1, 0)]
    for k in range(N):
        a, b, cc, d = lo[k], lo[(k + 1) % N], hi[(k + 1) % N], hi[k]
        oriented_quad(mb, [a, b, cc, d], 'paint', V((0, 0, -1)))
        oriented_quad(mb, [p + V((0, 0, 0.008)) for p in (a, b, cc, d)], 'interior', V((0, 0, 1)))
    if ztop is not None:
        lo2 = [V((p.x, p.y, min(ztop, p.z - 0.01))) for p in lo]     # round 5: never upward past the ring band (z-fight at the sides)
        loft(mb, [lo, lo2], 'interior', outward=False)          # the opening's wall up to the ring band (seen through the gap)


def fus_face_kind(c, ring_c):
    """material of a fuselage skin face by its centre c (world): glass zones, bay door, open hatch, else paint."""
    x, y, z = c
    top, bot, hw, n = S.fus_station(y)
    if S.WAIST_R[0] < y < S.WAIST_R[1] and x > 0.5 and S.WAIST_Z[0] < z < S.WAIST_Z[1]:
        return 'glass'
    if S.WAIST_L[0] < y < S.WAIST_L[1] and x < -0.5 and S.WAIST_Z[0] < z < S.WAIST_Z[1]:
        return 'glass'
    if not S.TAIL188 and S.TAIL_WIN[0] < y < S.TAIL_WIN[1] and 0.95 < z < 1.36 and abs(x) > 0.08:     # 1.7.8: not up into the fin-root fairing
        return 'glass'
    if S.RADIO_HATCH[0] < y < S.RADIO_HATCH[1] and z > top - 0.22 and abs(x) < 0.42:
        return 'hole'
    # chin turret opening: round 6 cuts it exactly in build_fuselage (b17g_detail.round_hole), no face-wise sawtooth
    if S.TAIL_WELL[0] < y < S.TAIL_WELL[1] and z < bot + 0.25 and abs(x) < TAIL_WELL_HW:      # tail-wheel well (1.6.1: as narrow as the stowed fork)
        return 'hole'
    if z < bot + 0.3 and x * x + (y - S.TURRETS['ball']['pos'][1]) ** 2 < BALL_HOLE_R ** 2:    # ball turret ring (round 3: clears the ball)
        return 'hole'
    # top turret: round 5 cuts a round hole in build_fuselage (b17g_detail.round_hole; was a 0.92 x 0.93 m square of whole faces)
    return 'paint'


# ---------------------------------------------------------------- cockpit cab (M2 round 2): anchored ring, straight window edges
# The fus_cockpit rings are sampled so that fixed ring indices sit ON the window edges (no per-face sawtooth): per side
# r_i (|x| = 0.10, overhead centre beam), r_o (|x| = 0.58, windscreen corner post / overhead window edge), t (z = 1.84, side
# window top), s (z = 1.31, sill). At the split stations (2.90, 5.00) the anchors sit on the uniform 40-point indices, so the ring
# equals the neighbours' ring exactly; inside the cab (3.00-4.60) they sit on their targets.
CAB_SNAP = (1, 3, 4, 7)                 # uniform indices of r_i, r_o, t, s at the splits (right side; left = 40 - j)
CAB_W = ((2.90, 0.0), (3.00, 1.0), (4.60, 1.0), (5.00, 0.0))
WIN_SIDE = (3.00, 3.97)                 # pilots' side windows (mullion at 3.50)
WIN_SCREEN = (3.97, 4.55)               # windscreen: front panes (centre post) + quarter panes
WIN_ROOF = (3.25, 3.85)                 # two overhead windows either side of the centre beam


def _se_pt(y, a, inset=0.0):
    top, bot, hw, n = S.fus_station(y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    hw, hz = max(hw - inset, 0.01), max(hz - inset, 0.01)
    s_, c_ = math.sin(a), math.cos(a)
    return V((hw * math.copysign(abs(s_) ** (2.0 / n), s_), y, cz + hz * math.copysign(abs(c_) ** (2.0 / n), c_)))


def _solve(y, f, target):
    lo, hi = 1e-4, math.pi - 1e-4          # f decreases along the right half from the top
    for _ in range(50):
        m = (lo + hi) / 2
        if f(_se_pt(y, m)) > target:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


# 1.6.1: the same anchored ring for the nose (glazing bottom edge + small cheek windows, in game 1.6.0 the face-chosen cheek zone was a
# 1.1 x 0.7 m sawtooth hole) and the bomb-bay door edges (a lit sawtooth slit along the closed doors, 06_bay_closed).
CHEEK_R_Y, CHEEK_L_Y = ((5.55, 6.07), (6.05, 6.57)) if S.ANM2_SLOTS else ((5.73, 6.07), (6.23, 6.57))      # around the staggered cheek gun pivots (5.90 / 6.40); 1.8.13 r3: 0.18 m longer aft (the AN/M2 jacket at the inboard limit)
PART_ANCHORS = {
    # right-half snap indices, targets, w(y) (ascending y)
    'fus_nose': dict(snap=(8, 10, 17), targets=(('z', 0.80), ('z', 0.45), ('zb', 0.12)), w=((5.00, 0.0), (5.12, 1.0), (9.0, 1.0))),
    'B17G': dict(snap=(14,), targets=(('xb', S.BAY_HALF_W),), w=((-1.60, 0.0), (-1.50, 1.0), (2.80, 1.0), (2.90, 0.0))),
}
if S.NOSE1817:     # 1.8.17: uniform nose rings (the windows are exact cuts, b17g_nose1817; the anchors made the cone's 'zb' bottom strip
    # climb to the tip: the grey tongue in front of the glass in game)
    PART_ANCHORS['fus_nose'] = dict(PART_ANCHORS['fus_nose'], w=((5.00, 0.0), (9.0, 0.0)))
if S.TAIL188:      # 1.8.8: the tail gunner's cab glazing (pane top z 1.64, small window bottom 1.31, sill 1.13); uniform at the -13.0 split
    PART_ANCHORS['tail_gun'] = dict(snap=(3, 7, 9), targets=(('z', S.TAIL_CAB['z_top']), ('z', S.TAIL_CAB['z_small']), ('z', S.TAIL_CAB['z_sill'])),
                                    w=((-15.5, 1.0), (-13.35, 1.0), (-13.0, 0.0)))


def _w_at(table, y):
    w = 0.0
    for (y0, w0), (y1, w1) in zip(table, table[1:]):
        if y0 <= y <= y1:
            t_ = (y - y0) / (y1 - y0) if y1 > y0 else 1.0
            t_ = t_ * t_ * (3 - 2 * t_)
            w = w0 + (w1 - w0) * t_
    return w


def _target_param(y, kind, v):
    top, bot, hw, n = S.fus_station(y)
    def bis(f, target, lo, hi):
        if not (min(f(_se_pt(y, lo)), f(_se_pt(y, hi))) <= target <= max(f(_se_pt(y, lo)), f(_se_pt(y, hi)))):
            return None
        dec = f(_se_pt(y, lo)) > f(_se_pt(y, hi))
        for _ in range(50):
            m = (lo + hi) / 2
            if (f(_se_pt(y, m)) > target) == dec:
                lo = m
            else:
                hi = m
        return (lo + hi) / 2
    if kind == 'z':
        return bis(lambda p: p.z, v, 1e-4, math.pi - 1e-4)
    if kind == 'zb':
        return bis(lambda p: p.z, bot + v, 1e-4, math.pi - 1e-4)
    if kind == 'xt':
        return bis(lambda p: abs(p.x), v, 1e-4, math.pi / 2)
    if kind == 'xb':
        return bis(lambda p: abs(p.x), v, math.pi / 2, math.pi - 1e-4)
    return None


def anchored_ring(name, y, inset=0.0):
    """40-point ring whose right-half indices `snap` sit on the part's anchor targets (left mirrored); uniform at w = 0."""
    spec = PART_ANCHORS[name]
    u = 2 * math.pi / S.FUS_N
    w = _w_at(spec['w'], y)
    snaps = list(spec['snap'])
    tg = [_target_param(y, k, v) for k, v in spec['targets']]
    A = []
    for i, (sn, t_) in enumerate(zip(snaps, tg)):
        a = sn * u if t_ is None else sn * u + (t_ - sn * u) * w
        A.append(a)
    for i in range(len(A)):          # keep the order (a target that cannot be met falls back between its neighbours)
        lo = (A[i - 1] if i else 0.0) + 0.02
        hi = (A[i + 1] if i + 1 < len(A) else math.pi) - 0.02
        if not (lo < A[i] < hi):
            A[i] = (lo + hi) / 2
    knots = [(0, 0.0)] + list(zip(snaps, A)) + [(S.FUS_N // 2, math.pi)]
    par = [0.0] * S.FUS_N
    for (j0, a0), (j1, a1) in zip(knots, knots[1:]):
        for j in range(j0, j1 + 1):
            par[j] = a0 + (a1 - a0) * (j - j0) / (j1 - j0)
    for j in range(1, S.FUS_N // 2):
        par[S.FUS_N - j] = 2 * math.pi - par[j]
    pts = [_se_pt(y, a, inset) for a in par]
    return [V((S.fus_pinch(y, p.x, p.z, inset), p.y, p.z)) for p in pts]      # 1.8.8: the fin-root pinch as fus_ring (no-op forward of -9.6)


def part_window(name, y0, y1, j):
    """'glass' / 'door' / None for the anchored-ring face between stations y0..y1 and ring segment j..j+1."""
    if name == 'fus_cockpit':
        return 'glass' if cab_window(y0, y1, j) else None
    right = j < S.FUS_N // 2
    jr = j if right else S.FUS_N - 1 - j
    ym = (y0 + y1) / 2
    if name == 'fus_nose' and S.NOSE1817:      # 1.8.17: the whole cone is glass down to the chin turret; windows are cut later
        return 'glass' if ym > S.NOSE_GLASS_Y else None
    if name == 'fus_nose':
        a, b, c = PART_ANCHORS['fus_nose']['snap']
        if ym > S.NOSE_GLASS_Y and jr < c:
            return 'glass'
        if a <= jr < b and ((right and CHEEK_R_Y[0] < ym < CHEEK_R_Y[1]) or (not right and CHEEK_L_Y[0] < ym < CHEEK_L_Y[1])):
            return 'glass'
    if name == 'B17G':
        if S.BAY_Y[0] < ym < S.BAY_Y[1] and jr >= PART_ANCHORS['B17G']['snap'][0]:
            return 'door'
    if name == 'tail_gun' and S.TAIL188:
        jt, js, jsill = PART_ANCHORS['tail_gun']['snap']
        C = S.TAIL_CAB
        if jr < jsill and ym < C['aft_face']:
            return 'glass'                    # the sloped aft face (and the cab sides beside it): the gunner's aft window
        if jt <= jr < jsill and (C['main'][0] < ym < C['main'][1] or ym < C['post'][0]):
            return 'glass'                    # main side pane, aft side pane
        if jt <= jr < js and C['small'][0] < ym < C['small'][1]:
            return 'glass'                    # small forward window
    return None


def tail_frames(mb, ys, rings):
    """1.8.8: frame bars round the tail gunner's cab glazing (riveted outside, bronze green inside)."""
    N = S.FUS_N
    jt, js, jsill = PART_ANCHORS['tail_gun']['snap']
    C = S.TAIL_CAB
    def along(j, y0, y1):
        return [rings[i][j % N] for i, y in enumerate(ys) if y0 - 1e-4 <= y <= y1 + 1e-4]
    def arc(y, ja, jb, right):
        i = min(range(len(ys)), key=lambda k: abs(ys[k] - y))
        js_ = range(ja, jb + 1) if right else range(N - ja, N - jb - 1, -1)
        return [rings[i][j % N] for j in js_]
    edges = []
    yend = min(ys)
    for right in (True, False):
        J = (lambda j: j) if right else (lambda j: N - j)
        edges += [(along(J(jt), C['aft_face'], C['main'][1]), 0.04), (along(J(jsill), C['aft_face'] - 0.09, C['main'][1]), 0.05)]
        for y_ in (C['main'][1], C['main'][0], C['post'][0]):
            edges.append((arc(y_, jt, jsill, right), 0.035))
        edges += [(along(J(jt), C['small'][0], C['small'][1]), 0.035), (along(J(js), C['small'][0], C['small'][1]), 0.035),
                  (arc(C['small'][0], jt, js, right), 0.035), (arc(C['small'][1], jt, js, right), 0.035)]
    window_frames(mb, ys, rings, edges, 'tail')


def window_frames(mb, ys, rings, edges, tag):
    """riveted frame bars along anchored polylines: edges = [(polyline, width)]; outer half livery, inner half bronze green."""
    def nrm(p):
        top, bot, hw, n = S.fus_station(p.y)
        d = V((p.x, 0, p.z - (top + bot) / 2))
        return d.normalized() if d.length > 1e-6 else V((0, 0, 1))
    for poly, w in edges:
        for k_, (a, b) in enumerate(zip(poly, poly[1:])):
            if (b - a).length < 1e-4:
                continue
            n_ = (nrm(a) + nrm(b)).normalized()
            o_ = 0.0015 * (k_ % 2)        # round 5: alternate segments 1.5 mm apart (overlapping joints were coplanar: z-fight)
            NS.sec_tube(mb, a + n_ * (0.011 + o_), b + n_ * (0.011 + o_), w, 0.022, n_, mat='paint')
            NS.sec_tube(mb, a - n_ * (0.015 + o_), b - n_ * (0.015 + o_), w, 0.030, n_, mat='interior')
    CAB_FRAME_LOG[tag] = len(edges)


def nose_frames(mb, ys, rings):
    N = S.FUS_N
    a, b, c = PART_ANCHORS['fus_nose']['snap']
    def along(j, y0, y1):
        return [rings[i][j % N] for i, y in enumerate(ys) if y0 - 1e-4 <= y <= y1 + 1e-4]
    def arc(y, ja, jb, right):
        i = min(range(len(ys)), key=lambda k: abs(ys[k] - y))
        js = range(ja, jb + 1) if right else range(N - ja, N - jb - 1, -1)
        return [rings[i][j % N] for j in js]
    edges = []
    for right, (y0, y1) in ((True, CHEEK_R_Y), (False, CHEEK_L_Y)):
        J = (lambda j: j) if right else (lambda j: N - j)
        edges += [(along(J(a), y0, y1), 0.06), (along(J(b), y0, y1), 0.06), (arc(y0, a, b, right), 0.06), (arc(y1, a, b, right), 0.06)]
    tip = max(ys)
    edges += [(along(c, S.NOSE_GLASS_Y, tip - 0.15), 0.05), (along(N - c, S.NOSE_GLASS_Y, tip - 0.15), 0.05)]     # round 5: stop short of the cone tip (inner / outer halves crossed: z-fight)
    window_frames(mb, ys, rings, edges, 'nose')


def cab_anchor_params(y):
    w = 0.0
    for (y0, w0), (y1, w1) in zip(CAB_W, CAB_W[1:]):
        if y0 <= y <= y1:
            t_ = (y - y0) / (y1 - y0); t_ = t_ * t_ * (3 - 2 * t_)
            w = w0 + (w1 - w0) * t_
    u = 2 * math.pi / S.FUS_N
    ri = _solve(y, lambda p: -abs(p.x), -0.10)
    ro = _solve(y, lambda p: -abs(p.x), -0.58)
    s_ = _solve(y, lambda p: p.z, 1.31)
    t_ = _solve(y, lambda p: p.z, 1.84)
    if not (ro + 0.02 < t_ < s_ - 0.02):           # windscreen stations: no side window top -> keep t midway
        t_ = (ro + s_) / 2
    tgt = (ri, ro, t_, s_)
    return [a_snap * u + (a_t - a_snap * u) * w for a_snap, a_t in zip(CAB_SNAP, tgt)]


def cab_ring(y, inset=0.0):
    """40-point ring with the cab anchors at fixed indices (same index layout at every station -> loft stays untwisted)."""
    A = cab_anchor_params(y)
    knots = [(0, 0.0)] + [(j, a) for j, a in zip(CAB_SNAP, A)] + [(S.FUS_N // 2, math.pi)]
    par = [0.0] * S.FUS_N
    for (j0, a0), (j1, a1) in zip(knots, knots[1:]):
        for j in range(j0, j1 + 1):
            par[j] = a0 + (a1 - a0) * (j - j0) / (j1 - j0)
    for j in range(1, S.FUS_N // 2):
        par[S.FUS_N - j] = 2 * math.pi - par[j]
    return [_se_pt(y, a, inset) for a in par]


def cab_window(y0, y1, j):
    """window kind of the cab face between stations y0..y1 and ring segment j..j+1 (None = skin)."""
    jr = j if j < S.FUS_N // 2 else S.FUS_N - 1 - j          # mirror the left side onto the right indices
    ri, ro, t_, s_ = CAB_SNAP
    ym = (y0 + y1) / 2
    if WIN_SCREEN[0] < ym < WIN_SCREEN[1]:
        if 0 <= jr < ro:
            return 'screen_front'
        if ro <= jr < s_:
            return 'screen_quarter'
    if WIN_SIDE[0] < ym < WIN_SIDE[1] and t_ <= jr < s_:
        return 'side'
    if WIN_ROOF[0] < ym < WIN_ROOF[1] and ri <= jr < ro:
        return 'roof'
    return None


CAB_FRAME_LOG = {}


def cab_frames(mb, ys, rings):
    """riveted frames on every cab window edge: outer half in the livery, inner half bronze green with rivet heads."""
    N = S.FUS_N
    ri, ro, t_, s_ = CAB_SNAP

    def nrm(p):
        top, bot, hw, n = S.fus_station(p.y)
        d = V((p.x, 0, p.z - (top + bot) / 2))
        return d.normalized() if d.length > 1e-6 else V((0, 0, 1))

    def along(j, y0, y1):
        return [rings[i][j % N] for i, y in enumerate(ys) if y0 - 1e-4 <= y <= y1 + 1e-4]

    def arc(y, ja, jb, side):
        i = min(range(len(ys)), key=lambda k: abs(ys[k] - y))
        js = range(ja, jb + 1) if side > 0 else range(N - ja, N - jb - 1, -1)
        return [rings[i][j % N] for j in js]

    edges = []
    for side in (1, -1):
        J = (lambda j: j) if side > 0 else (lambda j: N - j)
        edges += [(along(J(s_), *WIN_SIDE), 0.08), (along(J(t_), *WIN_SIDE), 0.07)]
        for y in (WIN_SIDE[0], 3.50):        # round 5: the WIN_SIDE[1] arc (3.97) lay on top of the windscreen arc (z-fight, check m)
            edges.append((arc(y, t_, s_, side), 0.07))
        edges += [(along(J(s_), *WIN_SCREEN), 0.08), (along(J(ro), *WIN_SCREEN), 0.06)]
        for y in WIN_SCREEN:
            edges.append((arc(y, 0, s_, side), 0.07))
        edges += [(along(J(ro), *WIN_ROOF), 0.06), (along(J(ri), *WIN_ROOF), 0.06)]
        for y in WIN_ROOF:
            edges.append((arc(y, ri, ro, side), 0.06))
    edges.append((along(0, *WIN_SCREEN), 0.07))          # windscreen centre post
    rivets = 0
    for poly, w in edges:
        for a, b in zip(poly, poly[1:]):
            if (b - a).length < 1e-4:
                continue
            n_ = (nrm(a) + nrm(b)).normalized()
            NS.sec_tube(mb, a + n_ * 0.011, b + n_ * 0.011, w, 0.022, n_, mat='paint')        # outer half (livery)
            NS.sec_tube(mb, a - n_ * 0.015, b - n_ * 0.015, w, 0.030, n_, mat='ck_wall')      # inner half (bronze green)
            ax = (b - a).normalized(); sd = ax.cross(n_).normalized()
            k = max(1, int((b - a).length / 0.075))
            for q in range(k):
                c = a + (b - a) * ((q + 0.5) / k) - n_ * 0.030
                for o in (sd * (w * 0.32), -sd * (w * 0.32)):
                    p0 = c + o
                    sq = [p0 + ax * 0.005, p0 + sd * 0.005, p0 - ax * 0.005, p0 - sd * 0.005]
                    tip = p0 - n_ * 0.004
                    for u_, v_ in zip(sq, sq[1:] + sq[:1]):
                        tri = [u_, v_, tip] if (v_ - u_).cross(tip - u_).dot(-n_) > 0 else [v_, u_, tip]
                        mb.face([mb.v(x_) for x_ in tri], 'ck_wall', None)
                    rivets += 1
    CAB_FRAME_LOG.update(edges=len(edges), rivets=rivets)
    return rivets


def build_fuselage():
    parts, doors = [], []
    if S.NOSE1817:
        import b17g_nose1817 as NZ
        keel = NZ.keel_fairing()
    bounds = [S.FUS[0][0]] + S.SPLITS + [S.FUS[-1][0]]
    for i, name in enumerate(S.FUS_PARTS):
        y0, y1 = bounds[i], bounds[i + 1]
        ys = fus_stations(y0, y1)
        cab = name == 'fus_cockpit'
        anch = cab or name in PART_ANCHORS
        rings = [cab_ring(y) if cab else anchored_ring(name, y) if anch else fus_ring(y) for y in ys]
        mb = MeshBuf()
        door = {'L': MeshBuf(), 'R': MeshBuf()}
        uvf = ring_arc_uv(rings, ys)
        grid, flip = loft(mb, rings, 'paint', closed=True, uvfunc=uvf)
        keep = []
        vid = {}
        if anch:
            for i_, r_ in enumerate(rings):
                for j_, p_ in enumerate(r_):
                    vid[(round(p_.x, 5), round(p_.y, 5), round(p_.z, 5))] = (i_, j_)
        for f in mb.faces:
            P = [mb.verts[k] for k in f['idx']]
            c = sum(P, V()) / len(P)
            kind = fus_face_kind(c, None)
            if anch and kind == 'paint':
                ij = [vid.get((round(p_.x, 5), round(p_.y, 5), round(p_.z, 5))) for p_ in P]
                if all(q is not None for q in ij):
                    js = sorted({q[1] for q in ij}); is_ = sorted({q[0] for q in ij})
                    j0 = js[0] if not (0 in js and S.FUS_N - 1 in js) else S.FUS_N - 1
                    kind = part_window(name, ys[is_[0]], ys[is_[-1]], j0) or kind
            if kind == 'paint':
                keep.append(f)
            elif kind == 'glass':
                f['mat'] = 'glass'; f['uv'] = None; keep.append(f)
            elif kind == 'door':
                side = 'L' if c.x < 0 else 'R'
                door[side].face([door[side].v(p) for p in P], 'paint', f['uv'])
            # 'hole': dropped (turret rings / hatch: the turret or a liner fills it)
        mb.faces = keep
        if name == 'B17G':
            import b17g_detail as D
            D.round_hole(mb, V(S.TURRETS['top']['pos']), 0.53, 0.80, z_min=1.5)
        if name == 'fus_nose' and not S.NOSE1817:     # 1.8.17: exact round opening (b17g_nose1817.chin_hole) after the tear
            import b17g_detail as D
            D.round_hole(mb, V(S.TURRETS['chin']['pos']), CHIN_HOLE_R + 0.07, 0.75, z_max=-0.05, n=4)     # skin teeth stay outside r 0.49 (drum 0.475; the fairing covers them to 0.68)
        if anch:      # anchored faces: wind every face outward (the anchored ring makes a few thin quads whose first-corner normal flips)
            for f in mb.faces:
                P = [mb.verts[k] for k in f['idx']]
                c = sum(P, V()) / len(P)
                nw = V((0, 0, 0))
                for k in range(len(P)):
                    p0, p1 = P[k], P[(k + 1) % len(P)]
                    nw += V(((p0.y - p1.y) * (p0.z + p1.z), (p0.z - p1.z) * (p0.x + p1.x), (p0.x - p1.x) * (p0.y + p1.y)))
                top_, bot_, hw_, n_ = S.fus_station(c.y)
                out = V((c.x, 0, c.z - (top_ + bot_) / 2))
                if name == 'tail_gun' and S.TAIL188 and c.y < -14.70:      # 1.8.8: the sloped aft face (glazed) faces aft: test with an aft component
                    out = V((c.x, -1.0, c.z - (top_ + bot_) / 2))
                if nw.dot(out) < 0:
                    f['idx'] = list(reversed(f['idx']))
                    if f['uv']:
                        f['uv'] = list(reversed(f['uv']))
        if anch or name in ('fus_tail', 'tail_gun'):     # 1.7.8: + the pinched tail (its twisted shoulder quads: inner skin poked through)
            # split quads on one fixed diagonal: the reversed inner copies (double skin, glass) then use the SAME diagonal
            # (a non-planar quad re-triangulated on the other diagonal pokes its inner copy through the outer face)
            tri = []
            for f in mb.faces:
                if len(f['idx']) == 4:
                    i_, u_ = f['idx'], f['uv']
                    for a_, b_, c_ in ((0, 1, 2), (0, 2, 3)):
                        tri.append(dict(idx=[i_[a_], i_[b_], i_[c_]], mat=f['mat'], uv=[u_[a_], u_[b_], u_[c_]] if u_ else None, smooth=f['smooth']))
                else:
                    tri.append(f)
            mb.faces = tri
        # nose cone tip / tail end caps
        if i == 0:
            fan_cap(mb, rings[0], sum(rings[0], V()) / len(rings[0]), 'glass', V((0, 1, 0)))
        if name == 'tail_gun':   # round 5: oblique Cheyenne opening + the gunner's aft window (b17g_detail.tail_cut)
            import b17g_detail as D
            D.tail_cut(mb, rings)
        # complementary jagged tear at the split planes (both neighbours use the same seed)
        for k, ys_ in ((0, y0), (1, y1)):
            if ys_ in S.SPLITS:
                seed = 100 + S.SPLITS.index(ys_)
                NS.tear_mesh(mb, V((0, ys_, 0)), V((0, 1, 0)), lambda v: math.atan2(v.x, v.z - 0.6) * 1.2, TEAR_AMP, seed, TEAR_W)
        if S.NOSE1817 and name in ('fus_nose', 'fus_cockpit'):     # 1.8.17: windows, astrodome / K-5 / chin openings (exact cuts)
            NZ.cut_part(name, mb)
        NS.double_skin(mb, t=0.006, mats=('paint',), inner=lambda f, c: 'interior', select=(lambda c: c.y < 7.25) if name == 'fus_nose' else None)
        # round 5: the double-skin edge strips of the two parts at a split lay on top of each other (same tear polyline): the aft
        # part's strips are re-made 1.5 mm into that part (check m)
        if y1 in S.SPLITS:
            moved = 0
            for f in mb.faces:
                if f['mat'] != 'structure':
                    continue
                P_ = [mb.verts[k] for k in f['idx']]
                if all(abs(p.y - y1) < 0.10 for p in P_):
                    f['idx'] = [mb.v(p + V((0, 0.0015, 0))) for p in P_]; moved += 1
        # glazing seen from inside: reversed copy 3 mm behind the outward glass (both faces render; no see-through)
        glass = [f for f in mb.faces if f['mat'] == 'glass']
        for f in glass:
            P = [mb.verts[k] for k in f['idx']]
            n = (P[1] - P[0]).cross(P[-1] - P[0])
            n = n.normalized() if n.length > 1e-12 else V((0, 0, 1))
            if anch:
                c_ = sum(P, V()) / len(P); t_, b_, h_, n__ = S.fus_station(c_.y)
                n = V((c_.x, 0, c_.z - (t_ + b_) / 2)).normalized()
            mb.face([mb.v(p - n * 0.003) for p in reversed(P)], 'glass', None)
        # frames 0.09 m inside every split + longeron stubs through the plane
        for ys_, sgn in ((y0, -1), (y1, 1)):
            if ys_ not in S.SPLITS:
                continue
            yf = ys_ - 0.09 if sgn < 0 else ys_ + 0.09
            ring = fus_ring(yf, inset=0.007)
            top, bot, hw, n = S.fus_station(yf)
            NS.frame_ring(mb, ring, V((0, yf, (top + bot) / 2)), depth=0.07, thick=0.022)
            for a in (35, 90, 145, 215, 270, 325):
                r = fus_ring(ys_, inset=0.03)
                p = r[(int(a / 360 * len(r)) + (0 if sgn < 0 else 1)) % len(r)]     # round 5: the neighbour's stubs one ring point apart (they overlapped: z-fight, check m)
                NS.sec_tube(mb, V((p.x, ys_ + (0.07 if sgn < 0 else -0.07), p.z)), V((p.x, ys_ + (-0.12 if sgn < 0 else 0.12), p.z)), 0.03, 0.03, (V((0, 0, 0)) - V((p.x, 0, p.z))).normalized() if (p.x ** 2 + p.z ** 2) > 1e-6 else V((0, 0, 1)))
        if cab:
            cab_frames(mb, ys, rings)
        if name == 'fus_nose' and not S.NOSE1817:
            nose_frames(mb, ys, rings)
        if name == 'tail_gun' and S.TAIL188:
            tail_frames(mb, ys, rings)
        if name == 'tail_gun':   # round 5: rim of the oblique Cheyenne opening (the cut is made before the double skin)
            import b17g_detail as D
            D.tail_lip(mb)
        if name == 'fus_nose' and not S.NOSE1817:   # plexiglass nose frames: 8 longitudinal bars + 2 hoops on the glazed cone
            gy = [y for y in ys if y > S.NOSE_GLASS_Y - 0.01]
            rr = [fus_ring(y, inset=-0.006) for y in gy]
            n_ = len(rr[0])
            for j in range(0, n_, n_ // 6):
                for a_, b_ in zip(rr[:-2], rr[1:-1]):
                    d_ = a_[j] - V((0, a_[j].y, 0.55))
                    NS.sec_tube(mb, a_[j], b_[j], 0.014, 0.008, d_.normalized() if d_.length > 1e-4 else V((0, 0, 1)), mat='paint')
            r_ = rr[0]
            for j in range(n_):
                NS.sec_tube(mb, r_[j], r_[(j + 1) % n_], 0.018, 0.008, V((0, 1, 0)), mat='paint')
        if S.NOSE1817 and name in ('fus_nose', 'fus_cockpit'):     # 1.8.17: frames, astrodome, K-5 frames, cone ring, optical flat, mast, keel
            NZ.finish_part(name, mb, keel)
        # round 5: the waist section gets its origin inside its own section (FuelTank / fire spawn point; it is also
        # where PilotDismounted searches the bail-out spot of the crew on that part); the others keep the datum
        piv = {'fus_waist': V((0, -5.90, 0.60))}.get(name, V())     # (fus_radio keeps the datum: 2 m beside -2.4 is over the flap)
        parts.append(Part(name, None if name == 'B17G' else 'B17G', pivot=piv, mesh=mb, info={'kind': 'fuselage', 'y': [y0, y1]}))
        for side in ('L', 'R'):
            if door[side].faces:
                doors.append((side, door[side]))
    return parts, doors


def build_bay(doors):
    """bomb bay: liner (walls, bulkheads, roof), catwalk keel beam, two doors hinged at the outer edges (open 90 deg)."""
    out = []
    mb = MeshBuf()
    y0, y1 = S.BAY_Y
    x = S.BAY_HALF_W - 0.02
    zb = -0.19      # 1.6.1: was -0.235, its bottom edge poked through the skin chords between stations (the lit 'slit', 06_bay_closed)
    for sx in (-1, 1):   # side walls (double)
        q = [V((sx * x, y0, zb)), V((sx * x, y1, zb)), V((sx * x, y1, S.BAY_ROOF_Z)), V((sx * x, y0, S.BAY_ROOF_Z))]
        oriented_quad(mb, q, 'structure', V((-sx, 0, 0)))
        oriented_quad(mb, [p + V((sx * 0.004, 0, 0)) for p in q], 'structure', V((sx, 0, 0)))
    for yy, d in ((y0, 1), (y1, -1)):   # bulkheads: bay section = fuselage section bottom arc (inset 1 cm) up to the roof
        ring = fus_ring(yy, inset=0.012)
        arc = sorted([p for p in ring if abs(p.x) <= x and p.z < S.BAY_ROOF_Z], key=lambda p: p.x)
        outline = [V((-x, yy, S.BAY_ROOF_Z)), V((-x, yy, zb))] + [V((p.x, yy, p.z)) for p in arc] + [V((x, yy, zb)), V((x, yy, S.BAY_ROOF_Z))]
        cen = sum(outline, V()) / len(outline)
        for a_, b_ in zip(outline, outline[1:] + outline[:1]):
            for off, dd in ((0.0, d), (-d * 0.004, -d)):
                oriented_quad(mb, [a_ + V((0, off, 0)), b_ + V((0, off, 0)), cen + V((0, off, 0))], 'structure', V((0, dd, 0)))
    q = [V((-x, y0, S.BAY_ROOF_Z)), V((x, y0, S.BAY_ROOF_Z)), V((x, y1, S.BAY_ROOF_Z)), V((-x, y1, S.BAY_ROOF_Z))]
    oriented_quad(mb, q, 'structure', V((0, 0, -1)))
    oriented_quad(mb, [p + V((0, 0, 0.004)) for p in q], 'structure', V((0, 0, 1)))
    # catwalk keel beam (low, under every stock store) and rack posts at the walls
    box(mb, (0, (y0 + y1) / 2, sum(S.CATWALK_Z) / 2), (S.CATWALK_HALF_W * 2, y1 - y0, S.CATWALK_Z[1] - S.CATWALK_Z[0]), 'structure')
    for yy in (y0 + 0.4, (y0 + y1) / 2, y1 - 0.4):
        for sx in (-1, 1):
            box(mb, (sx * (x - 0.05), yy, (zb + S.BAY_ROOF_Z) / 2), (0.06, 0.06, S.BAY_ROOF_Z - zb), 'structure')
    # 1.6.1: hinge strips on the skin over each door's outer edge (light showed through the door / skin edge, 06_bay_closed)
    hs = MeshBuf()
    for sx in (-1, 1):
        k_ = 12
        for i in range(k_):
            ya = y0 - 0.02 + (y1 - y0 + 0.04) * i / k_; yb_ = y0 - 0.02 + (y1 - y0 + 0.04) * (i + 1) / k_
            pa = V((sx * S.BAY_HALF_W, ya, belly_z(S.BAY_HALF_W, ya))); pb = V((sx * S.BAY_HALF_W, yb_, belly_z(S.BAY_HALF_W, yb_)))
            top_, bot_, hw_, n_ = S.fus_station(ya)
            nrm_ = V((pa.x, 0, pa.z - (top_ + bot_) / 2)).normalized()
            NS.sec_tube(hs, pa + nrm_ * 0.008, pb + nrm_ * 0.008, 0.07, 0.008, nrm_, mat='paint')
    out.append(Part('bay_hinge_strips', 'B17G', mesh=hs, info={'kind': 'bay_strip'}))
    out.append(Part('bay_liner', 'B17G', mesh=mb, info={'kind': 'bay'}))
    out.append(Part('hp_bombbay', 'B17G', pivot=S.HP_BOMBBAY, info={'kind': 'hardpoint', 'options': list(S.STORES)}))
    for side, dm in doors:
        sx = -1 if side == 'L' else 1
        NS.double_skin(dm, t=0.006, mats=('paint',), inner=lambda f, c: 'interior')
        hx = max((v.x * sx for v in dm.verts)) * sx
        hz = min((v.z for v in dm.verts if abs(v.x - hx) < 0.06), default=-0.5)
        hz = max(v.z for v in dm.verts if abs(abs(v.x) - abs(hx)) < 0.05)
        pivot = V((hx, (y0 + y1) / 2, hz))
        out.append(Part('bay_door_' + side, 'B17G', pivot=pivot, mesh=dm,
                        info={'kind': 'bay_door', 'hinge_axis': [0, 1, 0], 'open_deg': 92 * (1 if side == 'L' else -1)}))
    return out


# ============================================================================================ wings
def wing_station(x, side=1):
    le, te = S.wing_chord(x)
    chord = le - te
    inc = math.radians(S.interp(S.WING_INC, abs(x)))
    z = S.wing_z(x)
    cdir = V((0, -math.cos(inc), -math.sin(inc)))        # LE -> TE: aft and down (nose-up incidence)
    up = V((0, -math.sin(inc), math.cos(inc)))           # perpendicular to the chord
    # incidence rotates the section about its quarter chord (which stays on the dihedral plane)
    le_p = V((x * side, le, z + math.sin(inc) * chord * 0.25))
    return Station(x * side, le_p, cdir, up, chord, S.interp(S.WING_TC, abs(x)), m=0.02)


def span_list(x0, x1, step=0.45, extra=()):
    req = sorted({x0, x1} | {v for v in extra if x0 < v < x1})
    out = [req[0]]
    for a, b in zip(req, req[1:]):
        k = max(1, int(math.ceil((b - a) / step)))
        out += [a + (b - a) * i / k for i in range(1, k + 1)]
    return out


def fus_skin_x(y, z, inset=0.0):
    """|x| of the fuselage skin at (y, z) (superellipse section); 0 where z is outside the section."""
    top, bot, hw, n = S.fus_station(y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    t = abs(z - cz) / hz
    if t >= 1.0:
        return 0.0
    return S.fus_pinch(y, (hw - inset) * (1 - t ** n) ** (1.0 / n), z, inset)


def wing_root_fillet(mb, root_ring, side):
    """1.6.2 (coordinator: open slot along the lower wing-root junction, m3_bay_closed): below the chord the fuselage curves inward,
    so the root airfoil (x = WING_ROOT_X) stood up to 0.12 m off the skin and the root rib / inner skin showed through. A fillet skin
    runs from every root-airfoil point inward to the fuselage skin at the same (y, z) (2 mm under it), paint outside, interior inside;
    it is part of wing_inner, so it leaves with the wing when the root breaks (the damage split stays behind it)."""
    pts = []
    for p in root_ring:
        sx = fus_skin_x(p.y, p.z) - 0.002
        q = V((side * min(abs(p.x), max(sx, 0.0)), p.y, p.z)) if sx < abs(p.x) else V(p)
        pts.append((V(p), q))
    n = len(pts)
    for i in range(n):
        (a, qa), (b, qb) = pts[i], pts[(i + 1) % n]
        if (a - qa).length < 0.002 and (b - qb).length < 0.002:
            continue
        mid = (a + b + qa + qb) / 4
        out = V((0, 0, -1)) if mid.z < S.wing_z(abs(mid.x)) else V((0, 0, 1))
        quad = [a, b, qb, qa]
        if (quad[1] - quad[0]).length < 1e-5 or (quad[3] - quad[0]).length < 1e-5:
            quad = [a, b, qb] if (a - qa).length < 1e-5 else [a, b, qa] if (b - qb).length < 1e-5 else quad
        area = 0.5 * ((quad[1] - quad[0]).cross(quad[2] - quad[0]).length + ((quad[2] - quad[0]).cross(quad[3] - quad[0]).length if len(quad) == 4 else 0.0))
        if area < 1e-6:      # no zero-area slivers (Unity drops them on import: triangle parity check)
            continue
        oriented_quad(mb, quad, 'paint', out)
        oriented_quad(mb, [x_ + out * -0.004 for x_ in quad], 'interior', -out)


def build_wing(side):
    parts = []
    s = 'L' if side < 0 else 'R'
    xs_b = [S.WING_ROOT_X] + S.WING_SPLITS + [S.WING_TIP_X]
    names = ['wing_inner_' + s, 'wing_mid_' + s, 'wing_outer_' + s, 'wing_tip_' + s]
    parents = ['B17G', 'wing_inner_' + s, 'wing_mid_' + s, 'wing_outer_' + s]
    extra = [r[0] for r in S.WING_LE + S.WING_TE] + [S.AILERON[0], S.AILERON[1], S.FLAPS[0][1], S.FLAPS[1][2]]
    if S.NAC183:      # 1.8.3: stations at the edges of the leading-edge intakes (b17g_nacelle.le_intakes cuts them)
        import b17g_nacelle as N
        extra += [v for ab in N.LE_INTAKES for v in ab]
    for i, name in enumerate(names):
        x0, x1 = xs_b[i], xs_b[i + 1]
        xs = span_list(x0, x1, 0.40 if name.startswith('wing_tip') else 0.55, extra)
        if name.startswith('wing_tip'):
            xs = xs[:-1] + [x1 - 0.02]
        sts = [wing_station(x, side) for x in xs]
        mb = MeshBuf()
        s_to = 1.0 if name.startswith('wing_tip') else S.HINGE_F
        rings = []
        for st in sts:
            r, _ = box_ring(st, s_to, 14)
            rings.append(r)
        spans = [abs(st.span) for st in sts]
        uvf = ring_arc_uv(rings, spans)
        last = len(rings[0]) - 1
        loft(mb, rings, 'paint', closed=True, uvfunc=uvf, face_mat=lambda a, j: ('cove' if (j == last and s_to < 1) else 'paint'))
        if name.startswith('wing_tip'):   # round the tip: collapse to a small cap
            fan_cap(mb, rings[-1], sum(rings[-1], V()) / len(rings[-1]), 'paint', V((side, 0, 0)), uvfunc=lambda p: (p.y, p.z))
        for xb, sgn in ((x0, -1), (x1, 1)):
            if xb in S.WING_SPLITS:
                seed = 200 + S.WING_SPLITS.index(xb) + (10 if side < 0 else 0)
                NS.tear_mesh(mb, V((xb * side, 0, 0)), V((1, 0, 0)), lambda v: v.y * 1.0, TEAR_AMP, seed, TEAR_W, uv_axis=0)
        if x0 == S.WING_ROOT_X:   # root rib inside the fuselage (closed: no see-through into the wing)
            section_cap(mb, rings[0], 'structure', V((-side, 0, 0)))
        # 1.6.2: the jagged damage seam between wing parts showed the split ribs (structure) from outside (check b2): a paint section cap
        # 1.5 cm inside each split plane closes the seam; the ribs and spar stubs stay behind it for the break
        for ring_, xb, sgn in ((rings[0], x0, -1), (rings[-1], x1, 1)):
            if xb in S.WING_SPLITS:
                cen_ = sum(ring_, V()) / len(ring_)
                cap_ = [p_.lerp(cen_, 0.01) - V((side * sgn * 0.015, 0, 0)) for p_ in ring_]
                section_cap(mb, cap_, 'paint', V((side * sgn, 0, 0)))
                if S.BREAK183:
                    # 1.8.3 (user review item 9: a break face must show structure, not a painted plug): a rib web (structure = the stock
                    # aircraft_structure in game) 3 mm in front of the paint cap, 4 cm inside the skin all round, so the seam gaps still
                    # show only the paint cap from outside (check b2) and the livery atlas is unchanged (the cap faces stay)
                    rim_ = [p_ + (cen_ - p_).normalized() * min(0.04, 0.3 * (cen_ - p_).length) + V((side * sgn * 0.003, 0, 0)) for p_ in cap_]
                    section_cap(mb, rim_, 'structure', V((side * sgn, 0, 0)))
        # round 5: no inner skin on the last 0.2 m of the rounded tip (the 6 mm offset crossed the 1-2 cm thin section: check b2)
        NS.double_skin(mb, t=0.006, mats=('paint',), inner=lambda f, c: 'interior', select=(lambda c: abs(c.x) < 15.60) if name.startswith('wing_tip') else None)
        if x0 == S.WING_ROOT_X:   # round 5: the fillet after the double skin (it carries its own inner face; its edge strips showed at the bay door gap)
            wing_root_fillet(mb, rings[0], side)
        # ribs 0.09 m inside every split + spar caps through the plane
        for xb, sgn in ((x0, -1), (x1, 1)):
            if xb not in S.WING_SPLITS:
                continue
            xr = xb + 0.09 if sgn < 0 else xb - 0.09
            st = wing_station(xr, side)
            r, _ = box_ring(st, s_to if not (sgn > 0 and xb == S.WING_SPLITS[-1]) else S.HINGE_F, 14)
            rin = [p.lerp(sum(r, V()) / len(r), 0.04) for p in r]
            section_cap(mb, rin, 'structure', V((side * -sgn, 0, 0)))
            section_cap(mb, [p + V((side * 0.01 * sgn, 0, 0)) for p in rin], 'structure', V((side * sgn, 0, 0)))
            for sf in (0.15, 0.62):
                for up in (True, False):
                    p0 = st.point(sf, up).lerp(st.point(sf, not up), 0.08)
                    reach = 0.05 if xb == S.WING_SPLITS[-1] else 0.13      # round 5: at the thin rounded tip the 0.13 m stubs poked through the tip skin (check b2)
                    a = V(((xr + (0.006 if sgn < 0 else -0.006)) * side, p0.y, p0.z)); b = V(((xb + (reach if sgn > 0 else -reach)) * side, p0.y + (0.03 if sgn > 0 else -0.03), p0.z))
                    NS.sec_tube(mb, a, b, 0.05, 0.025, V((0, 0, 1)))     # round 5: end cap 6 mm off the rib plane, the neighbour's stubs 6 cm apart (z-fight)
        # round 5 (wreck fire): a FuelTank spawns its leak / fire effects at its part's ORIGIN and must sit on the part's own transform
        # (Unit.RpcFuelTankStatus: part transform TryGetComponent<FuelTank>), so the tank-carrying parts get their origin on the main fuel
        # cell between the spars (it was the aircraft datum for every part: a burning wing burned beside the fuselage)
        piv = V()
        if name in ('wing_inner_' + s, 'wing_mid_' + s, 'wing_outer_' + s):
            xc = {'wing_inner': 1.76, 'wing_mid': 5.31, 'wing_outer': 11.70}[name[:-2]]
            st_ = wing_station(xc, side)
            piv = st_.point(0.40, True).lerp(st_.point(0.40, False), 0.5)
        parts.append(Part(name, parents[i], pivot=piv, mesh=mb, info={'kind': 'wing', 'x': [x0 * side, x1 * side], 'origin': 'main fuel cell (FuelTank)' if piv.length else 'datum'}))
    # control surfaces
    for nm, xa, xb in S.FLAPS + [('aileron', S.AILERON[0], S.AILERON[1])]:
        xs = span_list(xa + 0.012, xb - 0.012, 0.6)     # round 5: 24 mm between neighbouring surfaces (the flap hinge-nose caps touched)
        sts = [wing_station(x, side) for x in xs]
        mb = MeshBuf()
        rings = [aft_ring(st, S.HINGE_F + 0.012, 6)[0] for st in sts]
        uvf = ring_arc_uv(rings, [abs(st.span) for st in sts])
        loft(mb, rings, 'paint', closed=True, uvfunc=uvf)
        section_cap(mb, rings[0], 'paint', V((-side, 0, 0)), uvfunc=lambda p: (p.y, p.z))
        section_cap(mb, rings[-1], 'paint', V((side, 0, 0)), uvfunc=lambda p: (p.y, p.z))
        # rounded nose in the cove (cylinder along the hinge)
        h0 = sts[0].point(S.HINGE_F + 0.012, True).lerp(sts[0].point(S.HINGE_F + 0.012, False), 0.5)
        h1 = sts[-1].point(S.HINGE_F + 0.012, True).lerp(sts[-1].point(S.HINGE_F + 0.012, False), 0.5)
        th0 = (sts[0].point(S.HINGE_F, True) - sts[0].point(S.HINGE_F, False)).length * 0.45
        th1 = (sts[-1].point(S.HINGE_F, True) - sts[-1].point(S.HINGE_F, False)).length * 0.45
        cylinder(mb, h0, h1, th0, th1, N=10, mat='cove')
        parent = ('wing_inner_' if xa < S.WING_SPLITS[0] else 'wing_mid_' if xa < S.WING_SPLITS[1] else 'wing_outer_') + s
        axis = (h1 - h0).normalized()
        parts.append(Part(f'{nm}_{s}', parent, pivot=(h0 + h1) / 2, mesh=mb, frame=frame_from_axes(axis if side > 0 else -axis),
                          info={'kind': 'control', 'hinge_axis': list(axis)}))
    return parts


# ============================================================================================ nacelles + engines
def nac_profile(kind, y):
    """(radius_side, z_top, z_bot) of the nacelle at y (1.8.3: b17g_nacelle when S.NAC183)."""
    if S.NAC183:
        import b17g_nacelle as N
        return N.nac_profile(kind, y)
    return nac_profile_v182(kind, y)


def nac_profile_v182(kind, y):
    """(radius_side, z_top, z_bot) of the 1.8.2 nacelle at y."""
    xa, za, ylip, yprop, R, yend, zbelly = S.NACELLES[kind]
    if y >= ylip - 0.05:
        t = (y - (ylip - 0.05)) / 0.05
        return R * (1 - 0.06 * t), za + R * (1 - 0.06 * t), za - R * (1 - 0.06 * t)
    if y > ylip - 1.0:     # cowl (constant), slight swell
        return R, za + R, za - R
    # behind the cowl: sides narrow, top drops into the wing, belly stays low over the gear well then rises to the end
    t = (ylip - 1.0 - y) / (ylip - 1.0 - yend)
    t = max(0.0, min(1.0, t))
    rs = R * (1 - 0.55 * t ** 1.4)
    top = za + R * (1 - 0.9 * t ** 1.1) - 0.05 * t
    if kind == 'inner':
        bot = zbelly if y > -0.10 else zbelly + (0.62) * min(1.0, (-0.10 - y) / (-0.10 - yend)) ** 1.2
    else:
        bot = zbelly + 0.50 * t ** 1.2
    if y <= yend + 0.02:
        rs, top, bot = 0.05, S.wing_z(xa) + 0.04, S.wing_z(xa) - 0.04
    return rs, top, max(bot, za - R) if y > ylip - 1.0 else bot


def nac_ring(kind, side, y, N=28):
    xa, za, *_ = S.NACELLES[kind]
    rs, top, bot = nac_profile(kind, y)
    cz = (top + bot) / 2
    return superellipse_ring(xa * side, y, cz, rs, (top - bot) / 2, (top - bot) / 2, n=2.2, N=N)


def build_nacelle(kind, side):
    if S.NAC183:
        import b17g_nacelle as N
        return N.build_nacelle(kind, side)
    s = 'L' if side < 0 else 'R'
    num = S.ENGINE_NUM[(side, kind)]
    xa, za, ylip, yprop, R, yend, zbelly = S.NACELLES[kind]
    ys = [ylip - k * 0.20 for k in range(int((ylip - yend) / 0.20) + 1)] + [yend]
    rings = [nac_ring(kind, side, y) for y in ys]
    mb = MeshBuf()
    loft(mb, rings, 'paint', closed=True, uvfunc=ring_arc_uv(rings, ys))
    keep = []
    for f in mb.faces:
        P = [mb.verts[k] for k in f['idx']]
        c = sum(P, V()) / len(P)
        if kind == 'inner' and 1.10 < c.y < 3.74 and c.z < zbelly + 0.25 and abs(c.x - S.MAIN_X * side) < 0.36:
            continue    # open gear well (the wheel stays half exposed when up)
        keep.append(f)
    mb.faces = keep
    NS.double_skin(mb, t=0.006, mats=('paint',), inner=lambda f, c: 'interior')
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / len(rings[-1]), 'paint', V((0, -1, 0)), uvfunc=lambda p: (p.x, p.z))   # 1.6.2: after the double skin
    parent = ('wing_inner_' if kind == 'inner' else 'wing_mid_') + s
    yo_ = (3.735 if kind == 'inner' else ylip - 1.05) - 0.32       # round 5: origin on the oil tank (FuelTank / fire effects spawn at the origin)
    out = [Part(f'nacelle_{num}', parent, pivot=V((xa * side, yo_, 0.52 if kind == 'inner' else za + 0.12)), mesh=mb, info={'kind': 'nacelle', 'engine': num})]
    if kind == 'inner':   # gear well liner: walls start on the nacelle's lower surface (never below the skin) + roof
        w = MeshBuf()
        x0, x1 = S.MAIN_X * side - 0.30, S.MAIN_X * side + 0.30
        y0, y1, z1 = 1.12, 3.72, 0.38

        def zskin(x, y):
            rs, top, bot = nac_profile(kind, y)
            cz, hz = (top + bot) / 2, (top - bot) / 2
            u = min(abs(x - xa * side) / max(rs, 1e-3), 0.999)
            return cz - hz * (1 - u ** 2.2) ** (1 / 2.2) + 0.012
        ys_ = [y0 + (y1 - y0) * k / 12 for k in range(13)]
        for xx, d in ((x0, 1), (x1, -1)):
            for ya, yb in zip(ys_, ys_[1:]):
                q = [V((xx, ya, zskin(xx, ya))), V((xx, yb, zskin(xx, yb))), V((xx, yb, z1)), V((xx, ya, z1))]
                oriented_quad(w, q, 'well', V((d, 0, 0)))
                oriented_quad(w, [p - V((d * 0.004, 0, 0)) for p in q], 'well', V((-d, 0, 0)))
        xs_ = [x0 + (x1 - x0) * k / 6 for k in range(7)]
        for yy, d in ((y0, 1), (y1, -1)):
            for xa_, xb_ in zip(xs_, xs_[1:]):
                q = [V((xa_, yy, zskin(xa_, yy))), V((xb_, yy, zskin(xb_, yy))), V((xb_, yy, z1)), V((xa_, yy, z1))]
                oriented_quad(w, q, 'well', V((0, d, 0)))
                oriented_quad(w, [p - V((0, d * 0.004, 0)) for p in q], 'well', V((0, -d, 0)))
        q = [V((x0, y0, z1)), V((x1, y0, z1)), V((x1, y1, z1)), V((x0, y1, z1))]
        oriented_quad(w, q, 'well', V((0, 0, -1)))
        oriented_quad(w, [p + V((0, 0, 0.004)) for p in q], 'well', V((0, 0, 1)))
        out.append(Part(f'gear_well_{s}', parent, mesh=w, info={'kind': 'well'}))
    # cowl lip ring (dark inside) + baffle disc behind the engine (no see-through) + cowl flaps band
    e = MeshBuf()
    ax = V((xa * side, ylip, za))
    lip_o = circle_pts(ax + V((0, 0.0, 0)), V((0, 1, 0)), R * 0.94, 32)
    lip_i = circle_pts(ax + V((0, -0.06, 0)), V((0, 1, 0)), R * 0.80, 32)
    loft(e, [lip_o, lip_i], 'cowl', outward=False)       # conical lip: faces forward-inward (seen from the front)
    deep = circle_pts(ax + V((0, -0.55, 0)), V((0, 1, 0)), R * 0.80, 32)
    loft(e, [lip_i, deep], 'cowl', outward=False)
    loft(e, [[p + (p - V((xa * side, p.y, za))).normalized() * 0.004 for p in lip_i], [p + (p - V((xa * side, p.y, za))).normalized() * 0.004 for p in deep]], 'cowl', outward=True)
    NS.disc(e, deep, ax + V((0, -0.55, 0)), 'metal_dark', V((0, 1, 0)))
    cylinder(e, ax + V((0, -0.20, 0)), V((xa * side, yprop - 0.02, za)), 0.17, 0.12, N=20, mat='cowl')     # nose case + shaft into the hub
    # exhaust / turbo-supercharger (inner + outer: under the nacelle aft of the wing LE)
    ty = -0.45 if kind == 'inner' else -0.55
    tb = V((xa * side, ty, nac_profile(kind, ty)[2] + 0.06))
    # round 5: the turbo-supercharger is b17g_detail.turbo (in the nacelle floor; the exhaust_n IR source moves to its exhaust hood)
    out.append(Part(f'engine_{num}', f'nacelle_{num}', pivot=ax, mesh=e, info={'kind': 'engine', 'engine': num, 'cowl_r': R}))
    out.append(Part(f'prop_{num}', f'engine_{num}', pivot=V((xa * side, yprop, za)), info={'kind': 'prop', 'engine': num, 'radius': S.PROP_R}))
    out.append(Part(f'exhaust_{num}', f'engine_{num}', pivot=tb - V((0, 0.40, 0)), info={'kind': 'ir_source'}))
    return out


# ============================================================================================ tail
ELEV_ROOT_X = 0.80     # 1.7.8: the elevator root moves out with the wider tail (skin hw 0.73-0.68 at z 1.05 over the elevator chord; was 0.45)


def build_tail():
    parts = []
    for side in (-1, 1):
        s = 'L' if side < 0 else 'R'
        xs = span_list(0.30, 6.60, 0.5, [r[0] for r in S.STAB_LE])
        sts = []
        for x in xs:
            le, te = S.interp(S.STAB_LE, x), S.interp(S.STAB_TE, x)
            sts.append(Station(x * side, V((x * side, le, S.STAB_Z)), V((0, -1, 0)), V((0, 0, 1)), le - te, S.STAB_TC, m=0.0))
        mb = MeshBuf()
        rings = []
        fr = []
        for st in sts:
            hf = min(0.98, max(0.3, (st.le.y - S.ELEV_HINGE_Y) / st.chord))
            fr.append(hf)
            rings.append(box_ring(st, hf, 10)[0])
        loft(mb, rings, 'paint', closed=True, uvfunc=ring_arc_uv(rings, xs), face_mat=lambda a, j: 'cove' if j == len(rings[0]) - 1 else 'paint')
        section_cap(mb, [p + V((side * 0.004, 0, 0)) for p in rings[0]], 'structure', V((-side, 0, 0)))     # round 5: 4 mm inside the double-skin edge strip (z-fight)
        section_cap(mb, rings[-1], 'paint', V((side, 0, 0)), uvfunc=lambda p: (p.y, p.z))
        NS.double_skin(mb, t=0.005, mats=('paint',), inner=lambda f, c: 'interior')
        parts.append(Part('stab_' + s, 'fus_tail', mesh=mb, info={'kind': 'stab'}))
        e = MeshBuf()
        xs2 = [ELEV_ROOT_X] + [x for x in xs if x > ELEV_ROOT_X + 0.05]     # 1.7.8: root at the (wider) fuselage side, not inside it
        r2 = [aft_ring(Station(x * side, V((x * side, S.interp(S.STAB_LE, x), S.STAB_Z)), V((0, -1, 0)), V((0, 0, 1)),
                                S.interp(S.STAB_LE, x) - S.interp(S.STAB_TE, x), S.STAB_TC, m=0.0),
                        min(0.98, max(0.3, (S.interp(S.STAB_LE, x) - S.ELEV_HINGE_Y) / (S.interp(S.STAB_LE, x) - S.interp(S.STAB_TE, x)))) + 0.01, 5)[0] for x in xs2]
        loft(e, r2, 'paint', closed=True)
        section_cap(e, r2[0], 'paint', V((-side, 0, 0)))
        section_cap(e, r2[-1], 'paint', V((side, 0, 0)))
        piv = V((ELEV_ROOT_X * side, S.ELEV_HINGE_Y - 0.03, S.STAB_Z))
        parts.append(Part('elevator_' + s, 'stab_' + s, pivot=piv, mesh=e, frame=frame_from_axes(V((1, 0, 0))), info={'kind': 'control'}))   # local X = +X both sides (CAS1 convention)
    # fin + dorsal fillet
    zs = [1.45 + k * 0.30 for k in range(14)] + [5.42]
    sts = []
    for z in zs:
        le, te = S.interp(S.FIN_LE, z), S.interp(S.FIN_TE, z)
        sts.append(Station(z, V((0, le, z)), V((0, -1, 0)), V((1, 0, 0)), le - te, S.FIN_TC, m=0.0))
    mb = MeshBuf()
    rings = []
    for st in sts:
        hf = min(0.97, max(0.3, (st.le.y - S.RUDDER_HINGE_Y) / st.chord))
        rings.append(box_ring(st, hf, 10)[0])
    loft(mb, rings, 'paint', closed=True, uvfunc=ring_arc_uv(rings, zs), face_mat=lambda a, j: 'cove' if j == len(rings[0]) - 1 else 'paint')
    section_cap(mb, rings[0], 'structure', V((0, 0, -1)))
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / len(rings[-1]), 'paint', V((0, 0, 1)), uvfunc=lambda p: (p.y, p.x))
    NS.double_skin(mb, t=0.005, mats=('paint',), inner=lambda f, c: 'interior')
    # dorsal fillet: thin wedge from y -5.4 on the fuselage top into the fin LE (closed single skin)
    dys = [-5.40 + (-9.30 + 5.40) * k / 12 for k in range(13)]
    drings = []
    for y in dys:
        top = S.fus_station(y)[0]
        zt = _dorsal_z(y)
        w = 0.05 + 0.09 * (y - -5.40) / (-9.30 + 5.40)
        drings.append([V((0, y, zt)), V((w, y, top - 0.06)), V((w * 0.8, y, top - 0.15)), V((-w * 0.8, y, top - 0.15)), V((-w, y, top - 0.06))])
    nf0 = len(mb.faces)
    loft(mb, drings, 'paint', closed=True, uvfunc=ring_arc_uv(drings, dys))
    for f in mb.faces[nf0:]:
        Pf = [mb.verts[k] for k in f['idx']]
        c = sum(Pf, V()) / len(Pf)
        n = (Pf[1] - Pf[0]).cross(Pf[-1] - Pf[0])
        ax_c = V((0, c.y, S.fus_station(c.y)[0] - 0.05))
        if n.dot(c - ax_c) < 0:
            f['idx'] = list(reversed(f['idx']))
            if f['uv']:
                f['uv'] = list(reversed(f['uv']))
    oriented_quad(mb, drings[0], 'paint', V((0, 1, 0)), uv=[(p.x, p.z) for p in drings[0]])
    parts.append(Part('fin', 'fus_tail', mesh=mb, info={'kind': 'fin'}))
    e = MeshBuf()
    r2 = []
    for z in zs[:-1]:
        le, te = S.interp(S.FIN_LE, z), S.interp(S.FIN_TE, z)
        st = Station(z, V((0, le, z)), V((0, -1, 0)), V((1, 0, 0)), le - te, S.FIN_TC, m=0.0)
        r2.append(aft_ring(st, min(0.97, max(0.3, (le - S.RUDDER_HINGE_Y) / (le - te))) + 0.01, 5)[0])
    loft(e, r2, 'paint', closed=True)
    section_cap(e, r2[0], 'paint', V((0, 0, -1)))
    section_cap(e, r2[-1], 'paint', V((0, 0, 1)))
    parts.append(Part('rudder', 'fin', pivot=V((0, S.RUDDER_HINGE_Y - 0.03, 3.3)), mesh=e, frame=frame_from_axes(V((0, 0, 1)), V((0, 1, 0))), info={'kind': 'control'}))
    return parts


def _dorsal_z(y):
    pts = sorted(S.DORSAL, key=lambda r: r[0])
    return S.interp(pts, y)


# ============================================================================================ gear
def main_gear(side):
    s = 'L' if side < 0 else 'R'
    py, pz = S.MAIN_PIVOT
    x = S.MAIN_X * side
    piv = V((x, py, pz))
    axle = V((x, py + S.MAIN_RAKE, pz - S.MAIN_LEG))      # round 3: leg raked forward (nose-over margin)
    mb = MeshBuf()
    # oleo: twin cylinders + torque link + trunnion boss (procedural structure; wheel is fal)
    u_ = (axle - piv).normalized()      # along the (raked) leg
    cylinder(mb, piv - u_ * 0.05, piv + u_ * 0.70, 0.085, N=12, mat='gear')
    cylinder(mb, piv + u_ * 0.70, axle - u_ * 0.05, 0.065, N=12, mat='chrome')
    cylinder(mb, piv - V((0.295, 0, 0)), piv + V((0.295, 0, 0)), 0.07, N=10, mat='gear')
    cylinder(mb, axle - V((0.22, 0, 0)), axle + V((0.22, 0, 0)), 0.105, N=12, mat='gear')
    # retraction screw / drag brace from the leg mid point forward-up to the well roof
    leg = Part('gear_main_' + s, 'wing_inner_' + s, pivot=piv, mesh=mb, frame=frame_from_axes(V((1, 0, 0))),
               info={'kind': 'gear', 'fold_deg': S.MAIN_FOLD, 'fold_axis': [1, 0, 0], 'fold_sense': 'forward-up', 'radius': S.WHEEL_R})
    # M1 review: round tyre (48 segments) instead of the decimated generated one; tread / sidewall detail comes from the fal rubber tile
    tm = MeshBuf()
    prof = [(0.330, -0.205), (0.470, -0.250), (0.600, -0.245), (0.675, -0.200), (0.705, -0.120), (0.711, 0.0),
            (0.705, 0.120), (0.675, 0.200), (0.600, 0.245), (0.470, 0.250), (0.330, 0.205)]
    rings = [[axle + V((w, 0, 0)) + V((0, r * math.cos(2 * math.pi * k / 48), r * math.sin(2 * math.pi * k / 48))) for k in range(48)] for r, w in prof]
    nf0 = len(tm.faces)
    loft(tm, rings, 'tyre', closed=True)
    for f in tm.faces[nf0:]:      # outward = away from the tyre's torus core (r 0.52 at the axle plane)
        Pf = [tm.verts[k] for k in f['idx']]; c = sum(Pf, V()) / len(Pf)
        d = c - axle; d.x = 0
        core = axle + d.normalized() * 0.52
        n = (Pf[1] - Pf[0]).cross(Pf[-1] - Pf[0])
        if n.dot(c - core) < 0:
            f['idx'] = list(reversed(f['idx']))
    for sx in (-1, 1):   # hub faces with a bolt boss
        rim = [axle + V((sx * 0.205, 0, 0)) + V((0, 0.33 * math.cos(2 * math.pi * k / 48), 0.33 * math.sin(2 * math.pi * k / 48))) for k in range(48)]
        fan_cap(tm, rim, axle + V((sx * 0.17, 0, 0)), 'gear', V((sx, 0, 0)))
        cylinder(tm, axle + V((sx * 0.17, 0, 0)), axle + V((sx * 0.25, 0, 0)), 0.11, N=24, mat='gear')
    wheel = Part('wheel_main_' + s, 'gear_main_' + s, pivot=axle, mesh=tm, info={'kind': 'wheel', 'radius': S.WHEEL_R, 'width': S.WHEEL_W})
    return [leg, wheel]



TAIL_COLLAR = (0.47, 0.62)        # steering collar on the leg, z above the axle (the fork post slides in it)


def tyre_mesh(axle, R, W):
    """round tyre + hub faces about an axle along X (same lathe as the main tyres, scaled): symmetric about the axle, so it can spin."""
    tm = MeshBuf()
    k, kw = R / 0.711, W / 0.50
    prof = [(0.330, -0.205), (0.470, -0.250), (0.600, -0.245), (0.675, -0.200), (0.705, -0.120), (0.711, 0.0),
            (0.705, 0.120), (0.675, 0.200), (0.600, 0.245), (0.470, 0.250), (0.330, 0.205)]
    rings = [[axle + V((w * kw, 0, 0)) + V((0, r * k * math.cos(2 * math.pi * j / 40), r * k * math.sin(2 * math.pi * j / 40))) for j in range(40)] for r, w in prof]
    nf0 = len(tm.faces)
    loft(tm, rings, 'tyre', closed=True)
    for f in tm.faces[nf0:]:
        Pf = [tm.verts[q] for q in f['idx']]; c = sum(Pf, V()) / len(Pf)
        d = c - axle; d.x = 0
        core = axle + d.normalized() * 0.52 * k
        n = (Pf[1] - Pf[0]).cross(Pf[-1] - Pf[0])
        if n.dot(c - core) < 0:
            f['idx'] = list(reversed(f['idx']))
    for sx in (-1, 1):
        rim = [axle + V((sx * 0.205 * kw, 0, 0)) + V((0, 0.33 * k * math.cos(2 * math.pi * j / 40), 0.33 * k * math.sin(2 * math.pi * j / 40))) for j in range(40)]
        fan_cap(tm, rim, axle + V((sx * 0.17 * kw, 0, 0)), 'gear', V((sx, 0, 0)))
    return tm


def tail_fork(axle):
    """zero-trail fork: two side plates from the axle bolt up to a crown above the tyre, a post up into the leg's steering collar."""
    fb = MeshBuf()
    hw = S.TAIL_WHEEL_W / 2 + 0.012       # plates 1 mm off the tyre sides
    crown = S.TAIL_WHEEL_R + 0.06
    for sx in (-1, 1):
        NS.sec_tube(fb, axle + V((sx * hw, 0, -0.03)), axle + V((sx * hw, 0, crown)), 0.06, 0.022, V((sx, 0, 0)), mat='gear')
    cylinder(fb, axle - V((hw + 0.02, 0, 0)), axle + V((hw + 0.02, 0, 0)), 0.028, N=10, mat='gear')
    box(fb, axle + V((0, 0, crown + 0.02)), (2 * hw + 0.03, 0.08, 0.045), 'gear')
    cylinder(fb, axle + V((0, 0, crown + 0.04)), axle + V((0, 0, TAIL_COLLAR[1] - 0.01)), 0.036, N=12, mat='chrome')
    return fb


def tail_gear():
    py, pz = S.TAIL_PIVOT
    ay, az = S.TAIL_AXLE_DOWN
    piv, axle = V((0, py, pz)), V((0, ay, az))
    mb = MeshBuf()
    # trailing arm from the trunnion to a vertical steering collar above the wheel (round 3: the fork + wheel are separate objects:
    # LandingGear spins every transform in `wheels` about its local X (LandingGear.cs 556-558) and steers `unsprung` about its local
    # Y (LandingGear.cs 718-724), so the tyre alone is the wheel and the fork rides on unsprung)
    top = axle + V((0, 0, TAIL_COLLAR[0]))
    cylinder(mb, piv, top + V((0, 0, 0.03)), 0.05, N=10, mat='gear')
    cylinder(mb, top, axle + V((0, 0, TAIL_COLLAR[1])), 0.055, N=12, mat='gear')
    cylinder(mb, piv - V((TAIL_WELL_HW, 0, 0)), piv + V((TAIL_WELL_HW, 0, 0)), 0.05, N=8, mat='gear')     # trunnion pins into the well walls
    leg = Part('gear_tail', 'fus_tail', pivot=piv, mesh=mb, frame=frame_from_axes(V((1, 0, 0))),
               info={'kind': 'gear', 'fold_deg': S.TAIL_FOLD, 'fold_axis': [1, 0, 0], 'fold_sense': 'aft-up', 'radius': S.TAIL_WHEEL_R})
    wheel = Part('wheel_tail', 'gear_tail', pivot=axle, mesh=tyre_mesh(axle, S.TAIL_WHEEL_R, S.TAIL_WHEEL_W),
                 info={'kind': 'wheel', 'radius': S.TAIL_WHEEL_R, 'width': S.TAIL_WHEEL_W})
    fork = Part('fork_tail', 'gear_tail', pivot=axle, mesh=tail_fork(axle), info={'kind': 'gear_fork', 'gear': 'gear_tail',
                'note': 'Unity: child of the gear unsprung (steers + rides the suspension, never spins)'})
    # tail-wheel well liner in the tail cone (open bottom)
    w = MeshBuf()
    x0, x1, y0, y1, z1 = -(TAIL_WELL_HW + 0.01), TAIL_WELL_HW + 0.01, S.TAIL_WELL[0], S.TAIL_WELL[1], 0.85

    def zb(x, y):
        top, bot, hw, n = S.fus_station(y)
        cz, hz = (top + bot) / 2, (top - bot) / 2
        u = min(abs(x) / hw, 0.999)
        return cz - hz * (1 - u ** n) ** (1 / n) + 0.012
    ys_ = [y0 + (y1 - y0) * k / 8 for k in range(9)]
    for xx, d in ((x0, 1), (x1, -1)):
        for ya, yb_ in zip(ys_, ys_[1:]):
            q = [V((xx, ya, zb(xx, ya))), V((xx, yb_, zb(xx, yb_))), V((xx, yb_, z1)), V((xx, ya, z1))]
            oriented_quad(w, q, 'well', V((d, 0, 0))); oriented_quad(w, [p - V((d * 0.004, 0, 0)) for p in q], 'well', V((-d, 0, 0)))
    for yy, d in ((y0, 1), (y1, -1)):
        q = [V((x0, yy, zb(x0, yy))), V((0, yy, zb(0, yy))), V((x1, yy, zb(x1, yy))), V((x1, yy, z1)), V((x0, yy, z1))]
        oriented_quad(w, q, 'well', V((0, d, 0))); oriented_quad(w, [p - V((0, d * 0.004, 0)) for p in q], 'well', V((0, -d, 0)))
    q = [V((x0, y0, z1)), V((x1, y0, z1)), V((x1, y1, z1)), V((x0, y1, z1))]
    oriented_quad(w, q, 'well', V((0, 0, -1))); oriented_quad(w, [p + V((0, 0, 0.004)) for p in q], 'well', V((0, 0, 1)))
    return [leg, wheel, fork, Part('gear_tail_well', 'fus_tail', mesh=w, info={'kind': 'well'})]


# ============================================================================================ turrets / gun positions (contract frames)
def turret_frames(name):
    """mount (oriented: +Z = rest aim, +Y = up) > az (identity) > el (identity) > gun_k > muzzle_k, as the B-25H contract."""
    t = S.TURRETS[name]
    pos, fwd = V(t['pos']), V(t['fwd']).normalized()
    upv = V((0, 0, 1)) if abs(fwd.z) < 0.95 else V((0, 1, 0))
    if name == 'radio':
        upv = V((0, 1, 0)) * -1 + V((0, 0, 1)) * 0.0
        upv = V((0, -0.866, -0.5)) * -1
    # Unity frame (export_b17g.py: Unity local Y = Blender local Z, Unity local Z = Blender local Y): Blender local Y = aim (Unity +Z),
    # Blender local Z = up (Unity +Y), local X = right
    upn = (upv - fwd * upv.dot(fwd)).normalized()
    xax = fwd.cross(upn).normalized()
    yax = upn
    m = Matrix((xax, fwd, upn)).transposed().to_quaternion()
    out = [Part(f'{name}_mount', None, pivot=pos, frame=m, info={'kind': 'turret_mount', 'station': t['station'],
                                                                'traverseRange': t['trav'], 'minElevation': t['emin'], 'maxElevation': t['emax']}),
           Part(f'{name}_az', f'{name}_mount', pivot=pos, frame=m)]
    elp = pos + yax * t.get('el_dz', 0.0)       # 1.8.13 r2: the top turret's elevation axis sits 0.10 m below the azimuth pivot
    out.append(Part(f'{name}_el', f'{name}_az', pivot=elp, frame=m))
    for k, (dx, dz) in enumerate(t['guns']):
        gp = elp + xax * dx + yax * dz + fwd * 0.10
        out.append(Part(f'{name}_gun{k}', f'{name}_el', pivot=gp, frame=m, info={'kind': 'gun_slot', 'stock_mesh': '50cal_doorGun_barrel'}))
        out.append(Part(f'{name}_muzzle{k}', f'{name}_gun{k}', pivot=gp + fwd * 1.20, frame=m, info={'kind': 'muzzle'}))
    return out


TURRET_PARENT = {'chin': 'fus_nose', 'top': 'B17G', 'ball': 'fus_waist', 'tail': 'tail_gun', 'cheek_R': 'fus_nose', 'cheek_L': 'fus_nose',
                 'waist_R': 'fus_waist', 'waist_L': 'fus_waist', 'radio': 'fus_radio'}


def build_turret_rings():
    """fixed structure around the turret openings: chin pod fairing ring, top turret race, ball yoke ring, radio hatch coaming,
    gun-mount plates in the cheek / waist windows (these are structure; the turret bodies are fal props)."""
    out = []
    mb = MeshBuf()
    # top turret race ring (sits in the roof opening)
    t = S.TURRETS['top']; c = V(t['pos'])
    # round 5: the race is a low flange following the roof skin (r 0.47-0.60, 12 mm proud) over the round hole + a liner inside;
    # it stood 0.12 m above the roof as a collar (user review 2 / 10, reference: the dome rises straight off the roof)
    def top_z(x, y):
        top_, bot_, hw_, n_ = S.fus_station(y)
        cz, hz = (top_ + bot_) / 2, (top_ - bot_) / 2
        u = min(abs(x) / hw_, 0.999)
        return cz + hz * (1 - u ** n_) ** (1 / n_)
    N = 48
    ring = lambda r: [V((c.x + r * math.cos(2 * math.pi * k / N), c.y + r * math.sin(2 * math.pi * k / N), 0)) for k in range(N)]
    fi = [V((p.x, p.y, top_z(p.x, p.y) + 0.012)) for p in ring(0.49)]     # the turret skirt (r 0.47) turns inside
    fo = [V((p.x, p.y, top_z(p.x, p.y) + 0.002)) for p in ring(0.60)]
    for k in range(N):
        a, b, cc, d = fi[k], fi[(k + 1) % N], fo[(k + 1) % N], fo[k]
        oriented_quad(mb, [a, b, cc, d], 'paint', V((0, 0, 1)))
        oriented_quad(mb, [p - V((0, 0, 0.008)) for p in (a, b, cc, d)], 'interior', V((0, 0, -1)))
    lo = [V((p.x, p.y, c.z - 0.30)) for p in fi]
    loft(mb, [fi, lo], 'interior', outward=False)
    loft(mb, [[p + (p - V((c.x, c.y, p.z))).normalized() * 0.006 for p in fi], [p + (p - V((c.x, c.y, p.z))).normalized() * 0.006 for p in lo]], 'interior')
    out.append(Part('top_race', 'B17G', mesh=mb, info={'kind': 'turret_race'}))
    # round 5: the dome, frames and gun housing are b17g_detail.top_turret (turns with top_az)
    mb = MeshBuf()
    t = S.TURRETS['ball']; c = V(t['pos'])
    rb = BALL_HOLE_R + 0.01
    o0 = circle_pts(c + V((0, 0, 0.62)), V((0, 0, 1)), rb, 40); o1 = circle_pts(c + V((0, 0, 0.40)), V((0, 0, 1)), rb, 40)
    loft(mb, [o0, o1], 'paint', uvfunc=lambda ci, cj, j: (cj * 0.1, ci * 0.2))
    loft(mb, [[p.lerp(c + V((0, 0, 0.62)), 0.04) for p in o0], [p.lerp(c + V((0, 0, 0.40)), 0.04) for p in o1]], 'interior', outward=False)
    annulus(mb, o0, [p.lerp(c + V((0, 0, 0.62)), 0.04) for p in o0], 'interior', V((0, 0, 1)))
    belly_flange(mb, c, rb, rb + 0.18, c.z + 0.40)
    out.append(Part('ball_ring', 'fus_waist', mesh=mb, info={'kind': 'turret_race'}))
    # yoke (turns with the turret in azimuth; the ball elevates between the arms): race ring under the band + two arms to the ball poles
    yk = MeshBuf()
    annulus(yk, circle_pts(c + V((0, 0, 0.39)), V((0, 0, 1)), rb - 0.005, 40), circle_pts(c + V((0, 0, 0.39)), V((0, 0, 1)), 0.58, 40), 'gear', V((0, 0, -1)))
    annulus(yk, circle_pts(c + V((0, 0, 0.40)), V((0, 0, 1)), rb - 0.005, 40), circle_pts(c + V((0, 0, 0.40)), V((0, 0, 1)), 0.58, 40), 'gear', V((0, 0, 1)))
    for sx in (-1, 1):
        # round 5 (user review 2 / reference): each yoke arm is a rounded U-shaped side fairing over the trunnion (0.24 m wide), not a bar
        prof = [V((0, 0.12, 0.395)), V((0, 0.12, 0.0))] + [V((0, 0.12 * math.cos(math.pi * k / 10), -0.12 * math.sin(math.pi * k / 10))) for k in range(1, 10)] + \
               [V((0, -0.12, 0.0)), V((0, -0.12, 0.395))]
        for xa, xb in ((0.600, 0.645),):
            outer = [c + V((sx * xb, p.y, p.z)) for p in prof]; inner = [c + V((sx * xa, p.y, p.z)) for p in prof]
            cen_o = c + V((sx * xb, 0, 0.15)); cen_i = c + V((sx * xa, 0, 0.15))
            fan_cap(yk, outer, cen_o, 'paint', V((sx, 0, 0)))
            fan_cap(yk, inner, cen_i, 'gear', V((-sx, 0, 0)))
            loft(yk, [outer, inner], 'paint', closed=True)
    out.append(Part('ball_yoke', 'ball_az', mesh=yk, info={'kind': 'turret_frame'}))
    mb = MeshBuf()
    t = S.TURRETS['chin']; c = V(t['pos'])
    rc = CHIN_HOLE_R + 0.01
    o0 = circle_pts(c + V((0, 0, 0.45)), V((0, 0, 1)), rc, 40)
    zb_ = 0.27 if S.ANM2_SLOTS else 0.22     # 1.8.13 r2: band 5 cm higher - the AN/M2 jackets at az +-86 / el +20 pass under it
    o1 = [V((p.x, p.y, max(c.z + zb_, belly_z(p.x, p.y) + 0.03))) for p in circle_pts(c + V((0, 0, zb_)), V((0, 0, 1)), rc, 40)]   # never below the nose skin
    loft(mb, [o0, o1], 'paint', uvfunc=lambda ci, cj, j: (cj * 0.1, ci * 0.2))
    kl = 0.012      # round 6: liner 6 mm inside the band (r 0.504; the drum's superellipse plan reaches r 0.487 on the diagonals)
    loft(mb, [[p.lerp(c + V((0, 0, 0.45)), kl) for p in o0], [p.lerp(c + V((0, 0, zb_)), kl) for p in o1]], 'interior', outward=False)
    annulus(mb, o1, [p.lerp(c + V((0, 0, zb_)), kl) for p in o1], 'paint', V((0, 0, -1)))
    annulus(mb, o0, [p.lerp(c + V((0, 0, 0.45)), kl) for p in o0], 'interior', V((0, 0, 1)))
    # round 6: a sloped fairing from just outside the drum (r 0.50, 5 cm below the skin) up to the nose skin at r 0.68: the drum's top
    # reads tucked into the nose contour (was a flat collar 1 cm under the skin round a 0.60 m hole)
    NF = 48 if not S.NOSE1817 else 0      # 1.8.17: exact 0.50 opening (no skin teeth to cover) + the keel fairing aft: no sloped fairing
    fi_ = [c + V((0.50 * math.cos(2 * math.pi * k / NF), 0.50 * math.sin(2 * math.pi * k / NF), 0)) for k in range(NF)]
    fo_ = [c + V((0.68 * math.cos(2 * math.pi * k / NF), 0.68 * math.sin(2 * math.pi * k / NF), 0)) for k in range(NF)]
    # r3: the lifted inner edge never above 8 mm under the skin (r2 let it rise through the skin where the nose belly is low: thin light
    # slivers and the hole's sawtooth showed from below)
    fi_ = [V((p.x, p.y, min(max(belly_z(p.x, p.y) - 0.055, c.z + zb_ - 0.005), belly_z(p.x, p.y) - 0.008) if S.ANM2_SLOTS else belly_z(p.x, p.y) - 0.055)) for p in fi_]
    fo_ = [V((p.x, p.y, belly_z(p.x, p.y) - 0.003)) for p in fo_]
    for k in range(NF):
        a_, b_, c_, d_ = fi_[k], fi_[(k + 1) % NF], fo_[(k + 1) % NF], fo_[k]
        oriented_quad(mb, [a_, b_, c_, d_], 'paint', V((0, 0, -1)))
        oriented_quad(mb, [p + V((0, 0, 0.006)) for p in (a_, b_, c_, d_)], 'interior', V((0, 0, 1)))
    if fi_:
        loft(mb, [fi_, [V((p.x, p.y, max(p.z, c.z + zb_) + 0.10)) for p in fi_]], 'interior', outward=False)     # inner wall up into the nose
    out.append(Part('chin_ring', 'fus_nose', mesh=mb, info={'kind': 'turret_race'}))
    rc_ = MeshBuf()      # rotating race on the pod top (turns with chin_az): a puck 5 mm inside the fixed ring liner, seated on the pod
    rr_ = rc - 0.012     # round 6: closes the annulus between the drum and the ring liner (r 0.504) from above (it was 0.485)
    b_, t_ = circle_pts(c + V((0, 0, 0.425)), V((0, 0, 1)), rr_, 40), circle_pts(c + V((0, 0, 0.445)), V((0, 0, 1)), rr_, 40)
    fan_cap(rc_, b_, c + V((0, 0, 0.425)), 'gear', V((0, 0, -1))); fan_cap(rc_, t_, c + V((0, 0, 0.445)), 'gear', V((0, 0, 1)))
    loft(rc_, [b_, t_], 'gear')
    out.append(Part('chin_race', 'chin_az', mesh=rc_, info={'kind': 'turret_frame'}))
    mb = MeshBuf()
    t = S.TURRETS['radio']; c = V(t['pos'])
    top = S.fus_station(c.y)[0]
    zc_, hz_ = (top - 0.03, 0.10) if S.ANM2_SLOTS else (top - 0.05, 0.14)     # r4c: bottom edge 1 cm into the skin at the opening's edge (z ~1.75)
    xr_ = 0.55 if S.ANM2_SLOTS else 0.43     # r4c: the rails on the opening's real edge (whole skin faces are dropped out to |x| ~0.55: at 0.43 the coaming floated 18 mm inside the hole)
    for sx in (-1, 1):     # r3: the side rails run the hatch's full length
        nseg_ = 12 if S.ANM2_SLOTS else 1     # r4c: in 12 lengths so the rail's lower edge has vertices all along the skin (connectivity check)
        L_ = (S.RADIO_HATCH[1] - S.RADIO_HATCH[0]) / nseg_
        for k_ in range(nseg_):
            box(mb, (sx * xr_, S.RADIO_HATCH[0] + L_ * (k_ + 0.5), zc_), (0.03, L_, hz_), 'paint')
    for yy in (S.RADIO_HATCH[0] + 0.02, S.RADIO_HATCH[1] - 0.02):
        box(mb, (0, yy, zc_), (2 * xr_, 0.03, hz_), 'paint')
    out.append(Part('radio_coaming', 'fus_radio', mesh=mb, info={'kind': 'coaming'}))
    return out
