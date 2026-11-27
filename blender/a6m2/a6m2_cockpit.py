"""A6M2 Zero cockpit (round 4, rebuilt r8 to the measured WT cockpit layout, centred): our own period cockpit, procedural, numbers in a6m2_ck_layout.py (WT cockpit extract = visual
reference only, design 8). Every piece is a closed solid (the model checks test orientation and see-through on every mesh).

Pieces (Part names; the Unity build copies every cockpit_* / gauge_* mesh onto the cockpit layer, NimrodBuild pattern):
  cockpit_panel (main panel + sub-panel between the breeches, bezels, dial faces on the `gauges` atlas, compass box),
  gauge_<id> empties + gauge_<id>_needle / _needle_short / gauge_turn_slip / gauge_horizon_card / gauge_compass_card movers,
  cockpit_breech_L / _R (Type 97 receivers with the charging handle and wooden knob), cockpit_sight (Type 98 reflector sight:
  body, lamp housing, tilted glass in a hinged frame, orange reticle), cockpit_seat (aluminium bucket seat with lightening holes), cockpit_stick
  (straight column + thick grip, Cockpit.Joystick, pivoting on the fixed floor mount cockpit_stick_base, r8m), cockpit_throttle (left quadrant lever, Cockpit.Throttle), cockpit_consoles
  (left quadrant box + trim wheel, right box + gear lever + magneto), cockpit_floor + closed bulkhead (a6m2_parts.cockpit_floor),
  r8: cockpit_coaming (green arch over the panel and breeches; with the bulkhead it closes the tub front).
No rudder pedals (nimrod-user-review-2), no modern parts (no MFD, no stock ejection seat / stick / throttle).
"""
import math
from mathutils import Vector
import a6m2_spec as S
import a6m2_ck_layout as L
from b25h_geom import V, MeshBuf, loft, cylinder, box, circle_pts, fan_cap, oriented_quad, annulus, planar_uv
from b25h_parts import Part

K = S.K
PN = V((0, -1, 0))          # toward the pilot (panels face aft)
PU = V((0, 0, 1))
X_ = V((1, 0, 0))


def Q(x, y, z):
    return V(S.pre((x, y, z), plug=False))


def frame_x(xaxis, zhint=(0, 0, 1)):
    from b25h_geom import frame_from_axes
    return frame_from_axes(V(xaxis), V(zhint))


def prism(mb, pts, n, t, mat, uvf=None, smooth=False):
    """closed plate: polygon pts (convex or fan-able from its centroid), thickness t along n (front face toward +n)."""
    c = sum(pts, V()) / len(pts)
    front = [p + n * t for p in pts]
    for ring, d in ((front, n), (pts, -n)):
        cc = sum(ring, V()) / len(ring)
        for j in range(len(ring)):
            a, b = ring[j], ring[(j + 1) % len(ring)]
            tri = [cc, a, b]
            if (a - cc).cross(b - cc).dot(d) < 0:
                tri = [cc, b, a]
            mb.poly(tri, mat, [uvf(q) for q in tri] if uvf else ([planar_uv(q, d) for q in tri] if mat == 'paint' else None), smooth)
    for j in range(len(pts)):
        a, b = pts[j], pts[(j + 1) % len(pts)]
        mid = (a + b) / 2
        oriented_quad(mb, [a, b, b + n * t, a + n * t], mat, mid - c, [uvf(q) for q in (a, b, b + n * t, a + n * t)] if uvf else None)


def disc(mb, c, n, up, r, t, mat, region=None, N=32):
    """closed disc of thickness t (face toward +n); the face carries the gauge-atlas region when given."""
    rt = up.cross(n).normalized() if abs(up.dot(n)) < 0.99 else X_
    pts = [c + (up * math.cos(2 * math.pi * k / N) + rt * math.sin(2 * math.pi * k / N)) * r for k in range(N)]

    def uvf(q):
        if region is None:
            return (0.0, 0.0)
        d = q - c
        return L.gauge_uv(region, d.dot(rt) / r, d.dot(up) / r)
    if region is None:
        prism(mb, pts, n, t, mat)
    else:
        prism(mb, pts, n, t, mat, uvf)
    return c + n * t


def ring(mb, c, n, r_out, r_in, t, mat, N=32):
    o0, o1 = circle_pts(c, n, r_out, N, ref=PU), circle_pts(c + n * t, n, r_out, N, ref=PU)
    i0, i1 = circle_pts(c, n, r_in, N, ref=PU), circle_pts(c + n * t, n, r_in, N, ref=PU)
    loft(mb, [o0, o1], mat, closed=True, outward=True)
    loft(mb, [i0, i1], mat, closed=True, outward=False)
    annulus(mb, o1, i1, mat, n); annulus(mb, o0, i0, mat, -n)


def wall_half(y, z):
    """inner wall half-width of the fuselage at built (y, z), 30 mm inside the skin."""
    import a6m2_parts as AP
    zt, zb, hw, zw, nt, nb = AP.body_params(y)
    return AP.body_ring_x(y, z) - 0.03          # r8: the real skin ring (body_x_at_z is up to 80 mm out near the floor: consoles poked through)


def needle(c, r, kind, zero_deg, n=PN, up0=PU):
    """needle in its rest pose pointing at the scale's first value: sword needle with a counterweight tail, 1 mm thick."""
    rt0 = up0.cross(n).normalized()          # pilot's right on the dial face
    a = math.radians(zero_deg)
    up = up0 * math.cos(a) + rt0 * math.sin(a)
    rt = rt0 * math.cos(a) - up0 * math.sin(a)
    nm = MeshBuf()
    if kind == 'ball':
        disc(nm, c - up0 * (r * 0.62) + n * 0.004, n, up0, r * 0.11, 0.002, 'gauges', 'ball', N=12)
        return nm
    Lh = r * (0.88 if kind == 'needle' else 0.60)
    w = r * (0.055 if kind == 'needle' else 0.09)
    tail = r * 0.25
    o = n * (0.005 if kind == 'needle' else 0.0042)
    pts = [c - up * tail - rt * w * 1.4, c - up * tail + rt * w * 1.4, c + rt * w, c + up * (0.80 * Lh) + rt * w * 0.7, c + up * Lh,
           c + up * (0.80 * Lh) - rt * w * 0.7, c - rt * w]
    pts = [p + o for p in pts]
    region = 'needle' if kind == 'needle' else 'needle_short'
    prism(nm, pts, n, 0.0009, 'gauges', lambda q: L.gauge_uv(region, 0.0, max(-0.9, min(0.9, (q - c).dot(up) / max(Lh, 1e-6)))))
    disc(nm, c + o + n * 0.0009, n, up0, r * 0.09, 0.0012, 'gauges', 'hub', N=12)
    return nm


def _bar(mb, a, b, w, h, up, mat):
    from a6m2_parts import bar
    bar(mb, a, b, w, h, up, mat)


def _sweep_bar(mb, pts, w, h, up, mat, fillet=0.0, nf=3):
    """r8n (user, r8m in game: the throttle handle was two rectangles with a gap at the elbow): ONE closed rectangular bar along the
    polyline `pts` (w across, h along `up`), mitred at every inner point so each straight run keeps its full w x h section through the
    bend; fillet > 0 rounds each inner point with a quadratic Bezier (nf inner samples) from E - t_in*fillet to E + t_out*fillet.
    Rings are skinned by loft() (vertices shared between neighbouring strips) and closed with quad end caps on the same vertices:
    one connected, closed shell (cf. a6m2_canopy.sweep)."""
    P = [V(p) for p in pts]
    if fillet > 0 and len(P) > 2:
        Q_ = [P[0]]
        for i in range(1, len(P) - 1):
            E = P[i]
            ti = (E - P[i - 1]).normalized(); to = (P[i + 1] - E).normalized()
            f_ = min(fillet, 0.45 * (E - P[i - 1]).length, 0.45 * (P[i + 1] - E).length)
            A, B = E - ti * f_, E + to * f_
            for k in range(nf + 2):
                t = k / (nf + 1)
                Q_.append(A * (1 - t) ** 2 + E * 2 * t * (1 - t) + B * t * t)
        Q_.append(P[-1])
        P = Q_
    up = V(up).normalized()
    rings = []
    for i, p in enumerate(P):
        t0 = (p - P[i - 1]).normalized() if i > 0 else (P[1] - p).normalized()
        t1 = (P[i + 1] - p).normalized() if i < len(P) - 1 else t0
        tb = (t0 + t1).normalized()
        z = (up - t0 * up.dot(t0)).normalized()
        y = z.cross(t0)
        ring = []
        for a, b in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
            c = p + y * a + z * b
            ring.append(c + t0 * (-(c - p).dot(tb) / t0.dot(tb)))     # corner on the mitre plane through p
        rings.append(ring)
    grid, _ = loft(mb, rings, mat, closed=True, outward=True, smooth=True)
    for g_, toward in ((grid[0], -(P[1] - P[0])), (grid[-1], P[-1] - P[-2])):
        q = [mb.verts[k] for k in g_]
        nrm = (q[1] - q[0]).cross(q[2] - q[0])
        mb.face(list(g_) if nrm.dot(toward) > 0 else list(reversed(g_)), mat, None, False)
    return grid


def _toggle(mb, c, n, up, mat_plate='gauges'):
    """small toggle switch on a plate: plate (switchplate cell), boss, lever."""
    rt = up.cross(n).normalized()
    pts = [c + rt * -0.008 + up * -0.010, c + rt * 0.008 + up * -0.010, c + rt * 0.008 + up * 0.010, c + rt * -0.008 + up * 0.010]
    prism(mb, pts, n, 0.0015, mat_plate, lambda q: L.gauge_uv('switchplate', 0.0, 0.0))
    cylinder(mb, c + n * 0.0015, c + n * 0.006, 0.0035, N=8, mat='alu')
    cylinder(mb, c + n * 0.006, c + n * 0.016 + up * 0.004, 0.0013, N=6, mat='alu')


def _label(mb, c, n, up, w, h):
    rt = up.cross(n).normalized()
    pts = [c - rt * w / 2 - up * h / 2, c + rt * w / 2 - up * h / 2, c + rt * w / 2 + up * h / 2, c - rt * w / 2 + up * h / 2]
    prism(mb, pts, n, 0.0012, 'gauges', lambda q: L.gauge_uv('label', max(-0.9, min(0.9, (q - c).dot(rt) / (w / 2) * 0.9)), max(-0.9, min(0.9, (q - c).dot(up) / (h / 2) * 0.9))))


def _arch_ring(y, ck):
    """coaming arch section at built y: closed polygon (outer arc right->left, inner arc left->right), feet on the wall."""
    zf_, za = ck['z_foot'] * K, ck['z_apex'] * K
    xw = wall_half(y, zf_) + 0.028           # wall_half is 30 mm inside the skin: feet 2 mm inside the outer skin, buried in the inner skin
    out_, in_ = [], []
    N = 24
    for k in range(N + 1):
        a = math.pi * k / N                   # 0 = right foot
        zo, zi = zf_ + (za - zf_) * math.sin(a), zf_ + (za - ck['t'] - zf_) * math.sin(a)
        xo = math.copysign(min(abs(xw * math.cos(a)), wall_half(y, zo) + 0.026), math.cos(a) or 1.0)     # r8: never outside the skin
        xi = math.copysign(min(abs((xw - ck['t'] * 1.5) * math.cos(a)), wall_half(y, zi) + 0.026 - ck['t'] * 1.5), math.cos(a) or 1.0)
        out_.append(V((xo, y, zo)))
        in_.append(V((xi, y, zi)))
    return out_ + list(reversed(in_))


def build_cockpit():
    """r8: rebuilt to the WT cockpit (positions / sizes measured, centred on x = 0): main panel + lower plates + sub-panel between the
    breeches under a green coaming arch, closed tub front (bulkhead in a6m2_parts.cockpit_floor + the arch), Type 97 breeches with only
    their rear 0.2 m in the cockpit, Type 98 sight on the centreline with its body under the line of sight and a clear tinted reflector,
    left console (throttle quadrant, mixture / pitch / supercharger levers, trim wheel, switch box), right console (radio box, oxygen
    regulator, gear and flap selectors aft), stick forward at y -0.50, seat on the centreline."""
    parts = []
    import a6m2_parts as AP
    pm = MeshBuf()
    # ------------------------------------------------------------------ main panel plate (chamfered lower corners), lower plate, sub-panel
    yP = L.PANEL_Y
    h = L.PANEL_HALF
    # r8b: three WT plates with thickness and a visible edge - main plate with cut corners (10 mm), the raised upper housing between
    # the breeches, the lower pedestal pieces; a shadow gap to the side walls. (r8's black crossbar removed: WT has none.)
    outline = [Q(-h + 0.03, yP, L.PANEL_Z0), Q(h - 0.03, yP, L.PANEL_Z0), Q(h, yP, L.PANEL_Z0 + 0.03), Q(h, yP, L.PANEL_Z1 - 0.02),
               Q(h - 0.02, yP, L.PANEL_Z1), Q(-h + 0.02, yP, L.PANEL_Z1), Q(-h, yP, L.PANEL_Z1 - 0.02), Q(-h, yP, L.PANEL_Z0 + 0.03)]
    prism(pm, [p + V((0, 0.010, 0)) for p in outline], PN, 0.010, 'interior')
    for (x0_, x1_, z0_, z1_) in L.LOWER_PLATES:                      # lower pedestal pieces, each 10 mm thick, set 10 mm back
        prism(pm, [Q(x0_, L.LOWER['y'], z0_), Q(x1_, L.LOWER['y'], z0_), Q(x1_, L.LOWER['y'], z1_), Q(x0_, L.LOWER['y'], z1_)], PN, 0.010, 'interior')
    ySub = L.SUB_Y
    sh = L.SUB_HALF
    # upper housing: a dark plate with screws inside a raised grey-green bezel frame (WT), cheeks and roof back to the bulkhead
    prism(pm, [Q(-sh, ySub, L.SUB_Z0), Q(sh, ySub, L.SUB_Z0), Q(sh, ySub, L.SUB_Z1), Q(-sh, ySub, L.SUB_Z1)], PN, 0.008, 'ck_panel')
    fb = 0.014
    for (xa, za, xb2, zb2) in ((-sh - fb, L.SUB_Z0 - fb, sh + fb, L.SUB_Z0), (-sh - fb, L.SUB_Z1, sh + fb, L.SUB_Z1 + fb),
                               (-sh - fb, L.SUB_Z0, -sh, L.SUB_Z1), (sh, L.SUB_Z0, sh + fb, L.SUB_Z1)):
        prism(pm, [Q(xa, ySub, za), Q(xb2, ySub, za), Q(xb2, ySub, zb2), Q(xa, ySub, zb2)], PN, 0.022, 'interior')
    for sx in (-1, 1):
        for sz in (-1, 1):
            sp = Q(sx * (sh - 0.010), ySub, (L.SUB_Z0 if sz < 0 else L.SUB_Z1) - sz * 0.010) + PN * 0.008
            cylinder(pm, sp, sp + PN * 0.003, 0.0035, N=8, mat='alu')
    for sx in (-1, 1):
        box(pm, Q(sx * (sh + fb / 2), (ySub + L.BULKHEAD_Y) / 2, (L.SUB_Z0 + L.SUB_Z1) / 2), (fb * K, abs(L.BULKHEAD_Y - ySub) * K + 0.02, (L.SUB_Z1 - L.SUB_Z0 + 2 * fb) * K), 'interior')
    box(pm, Q(0, (ySub + L.BULKHEAD_Y) / 2, L.SUB_Z1 + fb / 2), (2 * (sh + fb) * K, abs(L.BULKHEAD_Y - ySub) * K + 0.02, fb * K), 'interior')
    cylinder(pm, Q(-0.314, yP, 0.383) + PN * 0.010, Q(-0.314, yP, 0.383) + PN * 0.022, 0.009, N=10, mat='alu')
    movers = []
    for gid, d in L.DIALS.items():
        py = {'main': L.PANEL_Y, 'sub': L.SUB_Y, 'lower': L.LOWER['y']}[d['panel']]
        c0 = Q(d['x'], py, d['z']) + PN * (0.006 if d['panel'] != 'sub' else 0.008)
        r = d['r'] * K
        ring(pm, c0, PN, r + 0.0055, r + 0.0005, 0.008, 'ck_black' if d['rim'] == 'black' else 'alu')
        for k in range(4):                                    # bezel screws at 45 deg
            a = math.radians(45 + 90 * k)
            sp = c0 + (PU * math.cos(a) + X_ * math.sin(a)) * (r + 0.0034) + PN * 0.008
            cylinder(pm, sp - PN * 0.001, sp + PN * 0.0016, 0.0013, N=6, mat='alu')
        face_c = disc(pm, c0 - PN * 0.002, PN, PU, r + 0.0006, 0.004, 'gauges', gid)
        if d['panel'] == 'main':
            _label(pm, Q(d['x'], py, d['z']) + PN * 0.0085 + PU * (r + 0.0095), PN, PU, 0.026, 0.0075)
        if not d['movers']:
            continue
        fr = frame_x(PN, PU)
        movers.append(Part(f'gauge_{gid}', 'fus_center', face_c, None, fr, info=dict(kind='gauge', radius=r)))
        for suf, kind in d['movers']:
            if kind == 'card':
                cm = MeshBuf()
                disc(cm, face_c + PN * 0.0005, PN, PU, r * 0.92, 0.0012, 'gauges', 'horizon_card', N=32)
                p = Part('gauge_horizon_card', f'gauge_{gid}', face_c, cm, fr, info=dict(kind='gauge_card', axis_local='+X (Unity) toward the pilot', **L.SCALES['horizon']))
            else:
                nm = needle(face_c, r, kind, d['zero'] if kind != 'ball' else 0)
                key = 'slip' if suf == 'slip' else (gid + '_short' if suf == 'needle_short' else gid)
                name = 'gauge_turn_slip' if suf == 'slip' else f'gauge_{gid}_{suf}'
                p = Part(name, f'gauge_{gid}', face_c, nm, fr, info=dict(kind='gauge_' + kind, zero_deg=d['zero'], scale=key,
                                                                         sign='Unity +angle about local +X = clockwise as seen by the pilot'))
            p.own_uv = True
            movers.append(p)
        if gid == 'horizon':
            ring(pm, face_c + PN * 0.003, PN, r + 0.0006, r * 0.80, 0.002, 'ck_black')
            box(pm, face_c + PN * 0.006, (r * 1.0, 0.002, r * 0.06), 'alu')
    # compass box spanning both rows (WT boxed centre instrument) with the drum card window
    C = L.COMPASS
    cx, cz = C['x'], C['z']
    cb = Q(cx, L.PANEL_Y, cz) + PN * 0.02
    box(pm, cb, (C['box_w'] * K, 0.04, C['box_h'] * K), 'ck_black')
    for sx in (-1, 1):
        for sz in (-1, 1):
            sp = cb + PN * 0.020 + V((sx * (C['box_w'] / 2 - 0.008), 0, sz * (C['box_h'] / 2 - 0.008)))
            cylinder(pm, sp - PN * 0.001, sp + PN * 0.002, 0.0018, N=6, mat='alu')
    wc = cb + PN * 0.020
    hwC, hhC = C['w'] * K / 2, C['h'] * K / 2
    prism(pm, [wc + V((-hwC, 0, -hhC)), wc + V((hwC, 0, -hhC)), wc + V((hwC, 0, hhC)), wc + V((-hwC, 0, hhC))], PN, 0.0015, 'gauges',
          lambda q: L.gauge_uv('compass_window', max(-0.9, min(0.9, (q - wc).x / hwC * 0.9)), max(-0.9, min(0.9, (q - wc).z / hhC * 0.9))))
    cc = cb + PN * 0.004
    rr = C['r'] * K
    cm = MeshBuf()
    N = 48
    top = [cc + V((rr * math.sin(2 * math.pi * k / N), -rr * math.cos(2 * math.pi * k / N), 0.012)) for k in range(N)]
    bot = [p - V((0, 0, 0.024)) for p in top]
    it = [cm.v(p) for p in top]; ib = [cm.v(p) for p in bot]
    for k in range(N):
        k1 = (k + 1) % N
        idx = [ib[k], ib[k1], it[k1], it[k]]
        uv = [L.strip_uv('compass_card', k / N, 0.0), L.strip_uv('compass_card', (k + 1) / N, 0.0),
              L.strip_uv('compass_card', (k + 1) / N, 1.0), L.strip_uv('compass_card', k / N, 1.0)]
        P_ = [cm.verts[i] for i in idx]
        if (P_[1] - P_[0]).cross(P_[3] - P_[0]).dot(sum(P_, V()) / 4 - cc) < 0:
            idx, uv = [idx[0], idx[3], idx[2], idx[1]], [uv[0], uv[3], uv[2], uv[1]]
        cm.face(idx, 'gauges', uv, False)
    for ring_i, zc in ((it, 0.012), (ib, -0.012)):
        ci = cm.v(cc + V((0, 0, zc)))
        for k in range(N):
            tri = [ci, ring_i[k], ring_i[(k + 1) % N]]
            P_ = [cm.verts[i] for i in tri]
            if (P_[1] - P_[0]).cross(P_[2] - P_[0]).z * zc < 0:
                tri = [ci, ring_i[(k + 1) % N], ring_i[k]]
            cm.face(tri, 'gauges', [L.gauge_uv('black', 0, 0)] * 3, False)
    movers.append(Part('gauge_compass', 'fus_center', cc, None, frame_x(V((0, 0, 1)), V((0, 1, 0))), info=dict(kind='gauge')))
    pc = Part('gauge_compass_card', 'gauge_compass', cc, cm, frame_x(V((0, 0, 1)), V((0, 1, 0))), info=dict(kind='gauge_card', axis_local='+X (Unity) = up', sign='card turns -heading'))
    pc.own_uv = True
    movers.append(pc)
    # lower pedestal (WT): primer pump knob on the left box, red lamp beside the clock column, oil-cooler shutter indicator (dark dial + lever)
    yl = L.LOWER['y']
    kn = Q(-0.170, yl, 0.228) + PN * 0.010
    cylinder(pm, kn, kn + PN * 0.006, 0.016, N=16, mat='ck_black')
    cylinder(pm, kn + PN * 0.006, kn + PN * 0.026, 0.010, N=6, mat='alu')                # primer pump knob (hex)
    disc(pm, Q(-0.050, yl, 0.228) + PN * 0.010, PN, PU, 0.008, 0.007, 'gauges', 'red', N=12)   # warning lamp
    oc = Q(0.200, yl, 0.228) + PN * 0.010
    ring(pm, oc, PN, 0.030, 0.025, 0.008, 'ck_black')
    disc(pm, oc - PN * 0.002, PN, PU, 0.0255, 0.004, 'gauges', 'fuelp', N=28)
    _bar(pm, oc + PN * 0.008 + V((0.018, 0, 0.010)), oc + PN * 0.012 + V((0.030, 0, 0.034)), 0.005, 0.004, PN, 'ck_gun')
    cylinder(pm, oc + PN * 0.012 + V((0.030, 0, 0.034)), oc + PN * 0.026 + V((0.030, 0, 0.034)), 0.006, N=10, mat='ck_black')
    pp = Part('cockpit_panel', 'fus_center', Q(0, L.PANEL_Y, L.PANEL_Z0), pm)
    pp.own_uv = True
    parts.append(pp)
    parts += movers

    # ------------------------------------------------------------------ coaming arch (green hood over panel + breeches, rolled lip)
    ck = L.COAMING
    cm2 = MeshBuf()
    ys = [ck['y_lip'] * K + (ck['y_front'] * K - ck['y_lip'] * K) * k / 6 for k in range(7)]
    rings_ = [_arch_ring(y, ck) for y in ys]
    nh_ = len(rings_[0]) // 2
    loft(cm2, rings_, 'ck_dark', closed=True, outward=True,          # r8b: darker riveted coaming (WT)
         face_mat=lambda i, j: 'ck_black' if nh_ <= j < 2 * nh_ - 1 else 'ck_dark')   # r8c: the underside of the hood is a dark recess (WT)
    for r_, tw in ((rings_[0], V((0, -1, 0))), (rings_[-1], V((0, 1, 0)))):     # crescent end faces: quads outer[k] / inner[k] (a fan from
        n_ = len(r_) // 2                                                           # the centroid filled the whole space under the arch)
        o_, i_ = r_[:n_], list(reversed(r_[n_:]))
        for k in range(n_ - 1):
            oriented_quad(cm2, [o_[k], o_[k + 1], i_[k + 1], i_[k]], 'ck_dark', tw)
    lip = rings_[0][:25]
    lipb = [p + V((0, 0.004, -0.004)) for p in lip]
    lipb = [V((math.copysign(min(abs(p.x), wall_half(p.y, p.z) + 0.016), p.x or 1.0), p.y, p.z)) for p in lipb]
    for a_, b_ in zip(lipb, lipb[1:]):
        cylinder(cm2, a_, b_, 0.010, N=12, mat='ck_dark')                         # r8b: rounded padded rear lip (WT, coaming colour)
    for k in range(2, 23):                                                           # r8b: rivet row along the coaming (WT)
        p_ = rings_[1][k]
        n_ = (p_ - V((0, p_.y, ck['z_foot'] * K))).normalized()
        cylinder(cm2, p_ + n_ * 0.0005, p_ + n_ * 0.0025, 0.0022, N=6, mat='interior')
    # deck inside the windscreen (r8 tub check: the livery deck skin showed between the coaming and the cockpit-view windscreen): a green
    # plate 2 mm over the deck from the cockpit opening front to the windscreen front pane, within the windscreen footprint
    import a6m2_canopy as CAN
    ws = CAN.CK
    for k in range(10):
        ya_ = (0.0 + (-0.262 - 0.0) * k / 10) * K
        yb_ = (0.0 + (-0.262 - 0.0) * (k + 1) / 10) * K
        rows_ = []
        for yy in (ya_, yb_):
            t_ = min(max((yy / K - ws['ws_front']) / (ws['arch'] - ws['ws_front']), 0.0), 1.0)
            hx_ = (ws['fp_half_bot'] + (0.31 - ws['fp_half_bot']) * t_) * K
            rows_.append([V((hx_ * (2 * j / 12 - 1), yy, AP.body_z_at(hx_ * (2 * j / 12 - 1), yy) + 0.002)) for j in range(13)])
        for j in range(12):
            oriented_quad(cm2, [rows_[0][j], rows_[0][j + 1], rows_[1][j + 1], rows_[1][j]], 'ck_dark', V((0, 0, 1)))
    parts.append(Part('cockpit_coaming', 'fus_center', Q(0, ck['y_lip'], ck['z_apex']), cm2, info=dict(kind='cockpit')))

    # ------------------------------------------------------------------ Type 97 breeches (r8c, measured on WT ortho renders study/a6m2/r8c/br_ortho:
    # back / inboard side / top, metric grid): a SLIM receiver 58 mm wide, 165 mm tall (z 0.480-0.645), rear face y -0.355, running forward
    # over the main panel under the coaming (y -0.08); raised top cover with a rear latch block; back plate, bolt hole; inboard cocking slide
    # (horizontal cylinder) + linkage plate + toothed charging wheel low; thin 6 mm lever from a low pivot up the inboard rear edge to the
    # dark-brown oval wooden knob (32 x 40 x 50 mm, centre |x| 0.105, z 0.71) with a metal strap over it; recoil spring outboard; feed chute
    # outboard / forward under the coaming. Dark gunmetal (ck_gun), not black.
    B = L.BREECH
    for side, Ls in ((1, 'R'), (-1, 'L')):
        bm = MeshBuf()
        x = side * B['x']
        hw_ = B['w'] / 2
        z0_, z1_ = B['z_bot'], B['z_top']
        yr, yf = B['y_rear'], B['y_front']
        rc = Q(x, (yr + yf) / 2, (z0_ + z1_) / 2)
        RL = (yf - yr) * K
        hh_ = (z1_ - z0_) * K / 2
        prof = [(-hw_, -hh_), (hw_, -hh_), (hw_, hh_ - 0.006), (hw_ - 0.006, hh_), (-hw_ + 0.006, hh_), (-hw_, hh_ - 0.006)]
        prism(bm, [rc + V((px, -RL / 2, pz)) for px, pz in prof], V((0, 1, 0)), RL, 'ck_gun')                 # receiver body
        rear = rc.y - RL / 2
        top = rc.z + hh_
        box(bm, V((rc.x, rear + 0.060, top + 0.005)), (B['w'] - 0.018, 0.120, 0.010), 'ck_gun')              # raised top cover
        box(bm, V((rc.x, rear + 0.012, top + 0.012)), (B['w'] - 0.026, 0.022, 0.024), 'ck_gun')              # rear latch block
        cylinder(bm, V((rc.x - 0.012, rear + 0.012, top + 0.024)), V((rc.x + 0.012, rear + 0.012, top + 0.024)), 0.006, N=10, mat='ck_gun')
        box(bm, V((rc.x, rear - 0.003, rc.z - 0.004)), (B['w'] - 0.012, 0.006, 2 * hh_ - 0.030), 'ck_gun')     # back plate
        cylinder(bm, V((rc.x, rear - 0.006, rc.z - 0.030)), V((rc.x, rear - 0.014, rc.z - 0.030)), 0.009, N=12, mat='ck_black')   # bolt hole (dark)
        cylinder(bm, V((rc.x + side * 0.016, rear - 0.006, rc.z + 0.045)), V((rc.x + side * 0.016, rear - 0.012, rc.z + 0.045)), 0.004, N=8, mat='ck_gun')
        for zz in (0.040, -0.050):                                                                          # side-plate rivets
            for k in range(4):
                cylinder(bm, V((rc.x + side * hw_, rear + 0.025 + 0.06 * k, rc.z + zz)), V((rc.x + side * (hw_ + 0.0025), rear + 0.025 + 0.06 * k, rc.z + zz)), 0.0022, N=6, mat='ck_gun')
        # inboard mechanism: linkage plate, cocking slide cylinder protruding aft, toothed charging wheel low
        xi = rc.x - side * hw_
        box(bm, V((xi - side * 0.010, rear + 0.035, rc.z - 0.005)), (0.020, 0.070, 0.130), 'ck_gun')       # linkage housing (WT: broad dark plates)
        cylinder(bm, V((xi - side * 0.030, rear + 0.090, rc.z - 0.010)), V((xi - side * 0.030, rear - 0.018, rc.z - 0.010)), 0.012, N=14, mat='ck_gun')
        cylinder(bm, V((xi - side * 0.030, rear - 0.018, rc.z - 0.010)), V((xi - side * 0.030, rear - 0.024, rc.z - 0.010)), 0.008, N=12, mat='ck_gun')
        wc = V((xi - side * 0.028, rear + 0.022, rc.z - hh_ + 0.028))
        cylinder(bm, wc - V((0, 0.006, 0)), wc + V((0, 0.006, 0)), 0.020, N=18, mat='ck_gun')
        for k in range(12):
            a_ = 2 * math.pi * k / 12
            box(bm, wc + V((0.022 * math.cos(a_), 0, 0.022 * math.sin(a_))), (0.006, 0.010, 0.006), 'ck_gun')
        # cocking lever: pivot at the wheel, thin rod up the inboard rear edge, bent in, into the knob
        kc = Q(side * B['knob_x'], B['knob_y'], B['knob_z'])
        p0 = wc + V((-side * 0.010, -0.008, 0.0))
        p1 = V((xi - side * 0.020, rear - 0.006, rc.z + 0.020))
        p2 = V((xi - side * 0.022, rear - 0.004, top - 0.010))
        p3 = kc - V((0, 0, 0.024))
        for a_, b_ in ((p0, p1), (p1, p2), (p2, p3)):
            cylinder(bm, a_, b_, 0.0032, N=8, mat='ck_gun')
        cylinder(bm, p0 - V((side * 0.006, 0, 0)), p0 + V((side * 0.004, 0, 0)), 0.008, N=10, mat='ck_gun')       # pivot boss
        rx, ry, rz = 0.0175, 0.020, 0.025                                                              # oval wooden knob (WT 35 x 40 x 50 mm)
        rings = []
        for k in range(1, 10):
            t_ = math.pi * k / 10
            rings.append([kc + V((rx * math.sin(t_) * math.cos(2 * math.pi * j / 16), ry * math.sin(t_) * math.sin(2 * math.pi * j / 16), -rz * math.cos(t_))) for j in range(16)])
        loft(bm, rings, 'ck_wood', closed=True, outward=True)
        fan_cap(bm, rings[0], kc - V((0, 0, rz)), 'ck_wood', V((0, 0, -1)), smooth=True)
        fan_cap(bm, rings[-1], kc + V((0, 0, rz)), 'ck_wood', V((0, 0, 1)), smooth=True)
        strap = [kc + V((0, (ry + 0.0015) * math.sin(t_), -(rz + 0.0015) * math.cos(t_))) for t_ in [math.pi * k / 10 for k in range(11)]]
        _sweep_bar(bm, strap, 0.006, 0.0015, V((1, 0, 0)), 'ck_gun')                                     # metal strap over the knob (WT); r8n: one mitred strip (was 10 butted bars)
        # recoil spring outboard (ribbed cylinder) and the feed chute, outboard and forward under the coaming
        xo = rc.x + side * hw_
        sc_ = V((xo + side * 0.012, rear + 0.030, rc.z - 0.020))
        for k in range(9):
            cylinder(bm, sc_ + V((0, 0, -0.036 + 0.009 * k)), sc_ + V((0, 0, -0.031 + 0.009 * k)), 0.011, N=12, mat='ck_gun')
        cylinder(bm, sc_ + V((0, 0, -0.040)), sc_ + V((0, 0, 0.044)), 0.007, N=10, mat='ck_gun')
        ch0 = V((xo, rear + 0.17, rc.z + 0.010))
        pts_ = [ch0 + V((side * 0.040 * (1 - math.cos(t)), 0.0, -0.090 * math.sin(t))) for t in [k * math.pi / 2 / 5 for k in range(6)]]
        _sweep_bar(bm, pts_, 0.026, 0.008, V((side, 0, 0)), 'ck_gun')                                    # r8n: one mitred chute (was 5 butted bars)
        parts.append(Part(f'cockpit_breech_{Ls}', 'fus_center', rc, bm, info=dict(kind='cockpit')))

    # ------------------------------------------------------------------ Type 98 sight on the centreline (user review 1: was an opaque black
    # square off centre). Body under the line of sight, collimator lens on top, clear tinted reflector ('sightglass') in a black frame:
    # side arms down to a hinge pin on the sight head, top rail (r8m, user review r8l: the r8 glass + struts floated 11 mm over the head);
    # emissive reticle ring + cross on the reflector only
    SG = L.SIGHT
    sm = MeshBuf()
    hb = SG['half']
    ytop = SG['body_top']
    # r8b (WT): lower box with the range cog on the left, a horizontal grey-metal cylinder over it with a ribbed collar and the lamp housing
    # at the rear, collimator lens on top, reflector at ~45 deg; mounting bracket down to the upper housing roof
    # r8b (WT, seen from the seat): a dark box body with the range cog on its rear face, a grey-metal turret (vertical cylinder) on top
    # carrying the collimator lens, lamp housing at the back; the reflector at ~45 deg above it
    zb_ = SG['body_bot']; zt_ = ytop - 0.040
    box(sm, Q(0, -0.355, (zb_ + zt_) / 2), (2 * hb * K, 0.080, (zt_ - zb_) * K), 'ck_gun')
    cog = Q(0, -0.396, (zb_ + zt_) / 2)
    cylinder(sm, cog, cog - V((0, 0.012, 0)), 0.021, N=18, mat='ck_gun')
    for k in range(14):
        a = 2 * math.pi * k / 14
        box(sm, cog - V((0, 0.006, 0)) + V((0.024 * math.cos(a), 0, 0.024 * math.sin(a))), (0.006, 0.012, 0.006), 'ck_gun')
    cylinder(sm, cog - V((0, 0.012, 0)), cog - V((0, 0.018, 0)), 0.008, N=10, mat='gear')
    cylinder(sm, Q(0, -0.350, zt_ - 0.002), Q(0, -0.350, ytop - 0.004), 0.026, 0.024, N=24, mat='gear')     # grey turret
    for k in range(4):
        zk = zt_ + 0.006 + 0.007 * k
        cylinder(sm, Q(0, -0.350, zk), Q(0, -0.350, zk + 0.003), 0.0275, N=24, mat='gear')                 # ribbed adjustment ring
    cylinder(sm, Q(0, -0.350, ytop - 0.004), Q(0, -0.350, ytop + 0.002), 0.018, N=20, mat='alu')            # lens
    cylinder(sm, Q(0, -0.395, zt_ - 0.012), Q(0, -0.425, zt_ - 0.012), 0.014, N=14, mat='ck_gun')             # lamp housing
    gb0, gb1 = Q(0, SG['gy0'], SG['gz0']), Q(0, SG['gy1'], SG['gz1'])                                      # reflector bottom / top edge centres
    gh = SG['ghalf'] * K
    gp = [gb0 + V((-gh, 0, 0)), gb0 + V((gh, 0, 0)), gb1 + V((gh, 0, 0)), gb1 + V((-gh, 0, 0))]
    gn = (gp[1] - gp[0]).cross(gp[3] - gp[0]).normalized()
    if gn.y > 0:
        gn = -gn
    prism(sm, gp, gn, 0.002, 'sightglass')
    # r8m: glass bottom edge forward, top leaning aft to the pilot (WT); the frame is joined to the head: head plate on the turret, hinge
    # housing forward of the lens, hinge pin (glass bottom edge 1 mm into it), two side arms pin -> 3 mm past the top edge (inner face 0.5 mm
    # inside the glass edge: no coplanar glass / frame faces), top rail, two thin stays head plate -> arms
    X = V((1, 0, 0))
    up2 = (gp[3] - gp[0]).normalized()
    box(sm, Q(0, -0.349, SG['head_z'] - 0.003), (0.074, 0.060, 0.006), 'gear')                                  # sight-head plate
    box(sm, Q(0, -0.325, (SG['head_z'] + 0.756) / 2), (0.068, 0.014, 0.756 - SG['head_z'] + 0.002), 'ck_gun')   # hinge housing
    cylinder(sm, Q(-0.036, SG['hinge_y'], SG['hinge_z']), Q(0.036, SG['hinge_y'], SG['hinge_z']), 0.004, N=14, mat='ck_gun')   # hinge pin
    for s_ in (-1, 1):
        _bar(sm, Q(s_ * (SG['ghalf'] + 0.002), SG['hinge_y'], SG['hinge_z']), gb1 + X * (s_ * (gh + 0.002)) + up2 * 0.003, 0.005, 0.004, gn, 'ck_gun')   # side arm
    _bar(sm, gb1 + up2 * 0.002 - X * (gh + 0.0045), gb1 + up2 * 0.002 + X * (gh + 0.0045), 0.004, 0.003, gn, 'ck_gun')                      # top rail
    for s_ in (-1, 1):
        cylinder(sm, Q(s_ * 0.031, -0.372, SG['head_z']), gb0 + (gb1 - gb0) * 0.45 + X * (s_ * (gh + 0.002)), 0.0018, N=8, mat='gear')     # stay
    # ring-and-bead back-up sight (WT): a wire ring with a cross on a short post on the coaming, left of the reflector
    RB = L.RING_SIGHT
    rbm = MeshBuf()                     # r8b: own mesh, so cockpit_sight stays centred on x = 0 (CHECK r8 sight)
    rcn = Q(RB['x'], RB['y'], RB['z'])
    for k in range(24):
        a0, a1 = 2 * math.pi * k / 24, 2 * math.pi * (k + 1) / 24
        cylinder(rbm, rcn + V((RB['r'] * math.cos(a0), 0, RB['r'] * math.sin(a0))), rcn + V((RB['r'] * math.cos(a1), 0, RB['r'] * math.sin(a1))), 0.0016, N=6, mat='gear')
    for dv in (V((1, 0, 0)), V((0, 0, 1))):
        cylinder(rbm, rcn - dv * RB['r'], rcn + dv * RB['r'], 0.0010, N=6, mat='gear')
    cylinder(rbm, rcn - V((0, 0, RB['r'])), Q(RB['x'], RB['y'], RB['post_z']), 0.0035, N=8, mat='gear')
    box(rbm, Q(RB['x'], RB['y'], RB['post_z']), (0.020, 0.030, 0.008), 'gear')
    rc_ = (gp[0] + gp[2]) / 2 + gn * 0.0025
    rt2 = up2.cross(gn).normalized()
    Nn = 24
    for k in range(Nn):
        a0, a1 = 2 * math.pi * k / Nn, 2 * math.pi * (k + 1) / Nn
        p0 = rc_ + (up2 * math.cos(a0) + rt2 * math.sin(a0)) * 0.013
        p1 = rc_ + (up2 * math.cos(a1) + rt2 * math.sin(a1)) * 0.013
        prism(sm, [p0, p1, p1 + (p1 - rc_).normalized() * 0.0008, p0 + (p0 - rc_).normalized() * 0.0008], gn, 0.0004, 'reticle')
    for dvec in (up2, rt2):
        a, b = rc_ - dvec * 0.018, rc_ + dvec * 0.018
        w = (rt2 if dvec is up2 else up2) * 0.0004
        prism(sm, [a - w, b - w, b + w, a + w], gn, 0.0004, 'reticle')
    parts.append(Part('cockpit_sight', 'fus_center', Q(0, -0.36, SG['body_bot']), sm, info=dict(kind='cockpit')))
    parts.append(Part('cockpit_ringsight', 'fus_center', Q(RB['x'], RB['y'], RB['post_z']), rbm, info=dict(kind='cockpit')))

    # ------------------------------------------------------------------ side walls: holed frames, longerons, sill rail, canopy-rail
    # brackets, pipes / cable loom (r6, frames moved to the WT stations)
    eye = Q(*S.EYE)
    zf = AP.cockpit_floor_z()
    wm = MeshBuf()
    for side in (-1, 1):
        for yy in L.WALL_FRAMES_Y:
            y = yy * K
            pts = []
            for k in range(9):
                z = zf + 0.06 + (0.52 - zf - 0.06) * k / 8
                pts.append(V((side * (wall_half(y, z) + 0.012), y, z)))
            for a_, b_ in zip(pts, pts[1:]):
                _bar(wm, a_, b_, 0.012, 0.030, V((-side, 0, 0)), 'interior')
            for k in (2, 4, 6):
                hp = pts[k] + V((-side * 0.016, 0, 0))
                disc(wm, hp + V((0, 0.007, 0)), V((0, 1, 0)), PU, 0.009, 0.001, 'ck_black', N=12)
                disc(wm, hp - V((0, 0.008, 0)), V((0, -1, 0)), PU, 0.009, 0.001, 'ck_black', N=12)
        for zl in (0.43, 0.12):
            for k in range(5):
                ya, yb = (-0.36 - 0.20 * k) * K, (-0.36 - 0.20 * (k + 1)) * K
                ym = 0.5 * (ya + yb)
                xw = side * (wall_half(ym, zl) + 0.012)
                box(wm, V((xw, ym, zl)), (0.018, abs(yb - ya) + 0.002, 0.018), 'interior')
        zs = 0.600 * K                                                                # r8: WT sill rail height (the CK sill panels reach z 0.62)
        rail = [V((side * (S.lin(S.CANOPY, y_, 1) * K - 0.030), y_ * K, zs)) for y_ in (-0.45, -0.55, -0.80, -1.05, -1.30)]
        for a_, b_ in zip(rail, rail[1:]):
            cylinder(wm, a_, b_, 0.011, N=12, mat='interior')                          # r8b: thin riveted sill edge (r8 40 mm tube)
        for y_ in L.RAIL_PLATES_Y:                                                     # drilled frame plates under the rail (WT, 3 holes)
            y = y_ * K
            xb_ = side * (S.lin(S.CANOPY, y_, 1) * K - 0.034)
            c_ = V((xb_, y, zs - 0.075))
            box(wm, c_, (0.006, 0.040, 0.140), 'interior')
            for k in range(3):
                hp = c_ + V((0, 0, -0.045 + 0.045 * k))
                disc(wm, hp + V((side * 0.0035, 0, 0)), V((side, 0, 0)), PU, 0.011, 0.0008, 'ck_dark', N=14)
                disc(wm, hp - V((side * 0.0035, 0, 0)), V((-side, 0, 0)), PU, 0.011, 0.0008, 'ck_dark', N=14)
        for zl in (0.20, 0.30, 0.38, 0.50):                                            # stringers between the frames
            run = [V((side * (wall_half(y_ * K, zl) + 0.020), y_ * K, zl)) for y_ in (-0.36, -0.60, -0.85, -1.10, -1.35)]
            for a_, b_ in zip(run, run[1:]):
                _bar(wm, a_, b_, 0.008, 0.016, V((0, 0, 1)), 'interior')
        for (zp, rp, mt) in ((0.32, 0.007, 'metal_dark'), (0.28, 0.006, 'interior'), (0.24, 0.009, 'ck_black')):
            run = [V((side * (wall_half(y_ * K, zp) - 0.018), y_ * K, zp)) for y_ in (-0.98, -1.10, -1.32)]
            for a_, b_ in zip(run, run[1:]):
                cylinder(wm, a_, b_, rp, N=8, mat=mt)
    parts.append(Part('cockpit_walls', 'fus_center', V((0, eye.y, 0.3)), wm, info=dict(kind='cockpit')))

    # ------------------------------------------------------------------ seat (centred), head pad
    SE = L.SEAT
    yb = -1.42 * K
    bk = MeshBuf()
    box(bk, (0, yb - 0.03 + 0.036, 0.70), (0.20, 0.04, 0.12), 'ck_black')
    parts.append(Part('cockpit_headpad', 'fus_center', V((0, yb, 0.70)), bk, info=dict(kind='cockpit')))
    st = MeshBuf()
    sy = (SE['y_front'] + SE['y_back']) / 2 * K
    sd = abs(SE['y_front'] - SE['y_back']) * K
    sz = SE['z'] * K
    sw = SE['w'] * K
    box(st, (0, sy + 0.02, sz), (sw, sd - 0.04, 0.012), 'alu')
    for sx in (-1, 1):
        box(st, (sx * sw / 2, sy, sz + 0.14), (0.012, sd, 0.28), 'alu')
        for k in range(3):
            disc(st, V((sx * (sw / 2 + 0.007), sy + 0.12 - 0.12 * k, sz + 0.14)), V((sx, 0, 0)), PU, 0.035, 0.002, 'ck_black', N=16)
    from mathutils import Quaternion
    box(st, V((0, sy - sd / 2 + 0.01, sz + 0.30)), (sw, 0.012, 0.58), 'alu', rot=Quaternion(V((1, 0, 0)), math.radians(-8)))
    for k in range(3):
        disc(st, V((0, sy - sd / 2 + 0.018 + 0.018 * k, sz + 0.12 + 0.13 * k)), V((0, -1, 0)), PU, 0.045, 0.002, 'ck_black', N=16)
    box(st, (0, sy - sd / 2 - 0.01, sz - 0.03), (0.30, 0.06, 0.05), 'alu')
    parts.append(Part('cockpit_seat', 'fus_center', V((0, sy, sz)), st, info=dict(kind='cockpit')))
    # ------------------------------------------------------------------ stick (WT: forward at y -0.50, grip top z ~0.36)
    STK = L.STICK
    # r8b (WT): a tapered grey-green tube ~2x the r8 diameter on a leather boot, cylindrical wrapped grip, trigger lever.
    # r8m (user review r8l: the base moved with the stick, a straight rod clipped through the front): a FIXED floor mount
    # (cockpit_stick_base: plate, bolts, lower boot fold; not driven) and the moving stick (cockpit_stick, Cockpit.Joystick) pivoting
    # at a gimbal G on top of the fixed fold. No torque tube: the r8l one went through the forward bulkhead (aft face y -0.2414) and
    # the floor cross-rib, and there is no room above the wing skin to keep one fixed under the floor.
    yp_ = STK['y_pivot'] * K
    GZ = 0.054                                       # gimbal = top of the fixed lower boot fold
    G = V((0.0, yp_, zf + GZ))                       # x = 0 (A6M2Build centreline check)
    sb = MeshBuf()
    box(sb, (0, yp_, zf + 0.014), (0.13, 0.11, 0.020), 'ck_gun')       # base plate z zf+0.004..0.024 (2 mm into the floor top: no coplanar faces)
    for bx_ in (-0.054, 0.054):
        for by_ in (-0.044, 0.044):
            cylinder(sb, V((bx_, yp_ + by_, zf + 0.023)), V((bx_, yp_ + by_, zf + 0.029)), 0.005, N=8, mat='gear')   # 4 bolt heads outside the boot
    cylinder(sb, V((0, yp_, zf + 0.022)), V((0, yp_, zf + GZ + 0.002)), 0.055, 0.046, N=18, mat='ck_leather')       # lower boot fold (fixed)
    parts.append(Part('cockpit_stick_base', 'fus_center', V((0, yp_, zf)), sb, info=dict(kind='cockpit')))
    # moving stick (column, upper boot, collar, grip, trigger, cannon button) about G
    sk = MeshBuf()
    top_ = V((0.0, STK['y_top'] * K, STK['z_top'] * K))
    ax_s = (top_ - G).normalized()
    cylinder(sk, G - ax_s * 0.004, top_, 0.026, 0.017, N=16, mat='interior')
    for r0_, r1_, z0_, z1_ in ((0.044, 0.034, -0.006, 0.040), (0.034, 0.024, 0.044, 0.080)):   # upper boot folds (r 0.044 inside the fixed fold's 0.046 top; starts 2 mm under the column end: no shared cap)
        cylinder(sk, G + ax_s * z0_, G + ax_s * z1_, r0_, r1_, N=18, mat='ck_leather')
    cylinder(sk, top_ - ax_s * 0.006, top_ + ax_s * 0.012, 0.019, 0.019, N=16, mat='gear')                 # collar
    cylinder(sk, top_ + ax_s * 0.0125, top_ + ax_s * 0.105, 0.021, 0.020, N=18, mat='ck_black')           # wrapped grip (dark, WT)
    cylinder(sk, top_ + ax_s * 0.1055, top_ + ax_s * 0.118, 0.020, 0.013, N=18, mat='gear')
    tr = top_ + ax_s * 0.070 + V((0, 0.021, 0))
    _bar(sk, tr, tr + V((0, 0.020, -0.034)), 0.012, 0.006, V((1, 0, 0)), 'gear')                           # gun trigger lever
    cylinder(sk, top_ + ax_s * 0.116 + V((0, 0.004, 0)), top_ + ax_s * 0.128 + V((0, 0.004, 0)), 0.006, N=10, mat='navred')   # cannon button
    parts.append(Part('cockpit_stick', 'fus_center', G, sk, info=dict(kind='cockpit_stick', drive='Cockpit.Joystick', gimbal_z_above_floor=GZ)))
    # ------------------------------------------------------------------ throttle (WT): a thin lever on the quadrant with an angled grip
    TH = L.THROTTLE
    th = MeshBuf()
    tp = Q(TH['x'], TH['y'], TH['z'])
    grip = Q(*TH['grip'])
    elbow = tp + (grip - tp) * 0.7 + V((-0.012, 0, 0))
    _sweep_bar(th, [tp, elbow, grip], 0.008, 0.014, V((1, 0, 0)), 'gear', fillet=0.010)                       # r8n: ONE mitred, rounded lever (r8m: two boxes, 2.1 mm V at the elbow)
    gdir = V((0.85, 0.15, 0.50)).normalized()                                                                 # angled handle, inboard-up
    cylinder(th, grip - gdir * 0.006, grip + gdir * 0.062, 0.013, 0.011, N=14, mat='ck_black')
    cylinder(th, tp + V((-0.014, 0, 0)), tp + V((0.014, 0, 0)), 0.013, N=12, mat='gear')
    parts.append(Part('cockpit_throttle', 'fus_center', tp, th, info=dict(kind='cockpit_throttle', drive='Cockpit.Throttle')))
    # ------------------------------------------------------------------ consoles (r8b: the boxes follow the wall at every height - r8 left
    # black voids beside them; green tops, no black slabs)
    cs = MeshBuf()
    for side, (y0, y1, ztop) in ((-1, (-0.55, -1.00, 0.33)), (1, (-0.55, -1.28, 0.27))):
        ys_ = [(y0 + (y1 - y0) * k / 8) * K for k in range(9)]
        zs_ = [zf + (ztop - zf) * j / 6 for j in range(7)]
        xin = side * 0.255
        rows = []
        for y in ys_:
            r_ = [V((side * (wall_half(y, z) + 0.024), y, z)) for z in zs_]              # outer side 6 mm inside the skin, along the wall
            rows.append([V((xin, y, zf))] + r_ + [V((xin, y, ztop))])
        loft(cs, rows, 'interior', closed=True, outward=True)
        for r_, tw in ((rows[0], V((0, 1, 0))), (rows[-1], V((0, -1, 0)))):
            fan_cap(cs, r_, sum(r_, V()) / len(r_), 'interior', tw)
        box(cs, V((xin + side * 0.006, (ys_[0] + ys_[-1]) / 2, ztop + 0.004)), (0.012, abs(ys_[-1] - ys_[0]) - 0.01, 0.008), 'ck_dark')   # console lip
    # throttle quadrant (r8m, user review r8l: full throttle clipped the minor levers): sector plate CONCENTRIC with the lever pivot
    # (fan 22..78 deg from vertical; the lever arm is at 30.7 deg at idle, 70.7 deg at full, Cockpit.Throttle +40 deg), slot / detent strip
    # on its inboard face, web down to the box, friction knob on the pivot axis outboard (WT)
    QD = L.QUAD
    fan_ = [tp + V((QD['plate_dx'] - 0.003, 0, 0))] + [tp + V((QD['plate_dx'] - 0.003, QD['arc_r'] * math.sin(math.radians(a_)), QD['arc_r'] * math.cos(math.radians(a_))))
                                                         for a_ in range(QD['a0'], QD['a1'] + 1, 4)]
    prism(cs, fan_, V((1, 0, 0)), 0.006, 'interior')                                    # solid fan plate, pivot -> arc_r (no saw-tooth rim)
    for k in range(8):
        a0 = math.radians(QD['a0'] + (QD['a1'] - QD['a0']) * k / 8)
        a1 = math.radians(QD['a0'] + (QD['a1'] - QD['a0']) * (k + 1) / 8)
        q0 = tp + V((QD['plate_dx'] + 0.004, QD['slot_r'] * math.sin(a0), QD['slot_r'] * math.cos(a0)))
        q1 = tp + V((QD['plate_dx'] + 0.004, QD['slot_r'] * math.sin(a1), QD['slot_r'] * math.cos(a1)))
        _bar(cs, q0, q1, 0.005, 0.003, V((1, 0, 0)), 'ck_dark')                         # slot / detent strip on the inboard face
    _bar(cs, tp + V((QD['plate_dx'], 0, 0)), tp + V((QD['plate_dx'], 0, -0.032)), 0.06, 0.006, V((1, 0, 0)), 'interior')   # web down to the box
    box(cs, tp + V((-0.020, 0.0, -0.041)), (0.05, 0.16, 0.05), 'interior')             # quadrant box (top tp.z-0.016: under the pivot hub)
    cylinder(cs, tp + V((-0.025, 0, 0)), tp + V((-0.045, 0, 0)), 0.010, N=10, mat='gear')   # friction knob on the pivot axis
    # mixture (blue handle), prop pitch and supercharger (red ball knobs): thin metal levers on their own plate in one plane x = QUAD xm,
    # outboard of the sector plate and the throttle's swept band (r8m)
    XM = QD['xm']
    box(cs, Q(XM, -0.665, 0.333), (0.024, 0.10, 0.012), 'ck_dark')                     # lever base plate (1 mm into the console top)
    for k, (yo, zt_, col) in enumerate(((-0.700, 0.416, 'ck_blue'), (-0.670, 0.397, 'navred'), (-0.640, 0.349, 'navred'))):
        lp = Q(XM, yo, 0.330)
        top_k = Q(XM, yo + 0.012, zt_ - 0.02)
        _bar(cs, lp, top_k, 0.005, 0.009, V((1, 0, 0)), 'gear')
        if col == 'ck_blue':
            _bar(cs, top_k, top_k + V((0.006, 0.010, 0.030)), 0.010, 0.016, V((1, 0, 0)), col)
        else:
            sph = [circle_pts(top_k + V((0, 0, 0.011 + 0.011 * math.cos(math.pi * (j + 1) / 7))), V((0, 0, 1)), 0.011 * math.sin(math.pi * (j + 1) / 7), 12) for j in range(6)]
            loft(cs, sph, col, closed=True, outward=True)
            fan_cap(cs, sph[0], top_k + V((0, 0, 2 * 0.011)), col, V((0, 0, 1)))
            fan_cap(cs, sph[-1], top_k, col, V((0, 0, -1)))
    # trim wheel (WT trimmer: x -0.30, y -0.874, z 0.307, dia 0.145) with the chain to the floor sprocket
    T = L.TRIM
    tw = Q(T['x'], T['y'], T['z'])
    ring(cs, tw, V((1, 0, 0)), T['r'] * K, T['r'] * K - 0.012, 0.018, 'ck_black', N=32)
    disc(cs, tw, V((1, 0, 0)), PU, 0.018, 0.024, 'gear', N=16)
    for k in range(5):
        a = 2 * math.pi * k / 5
        _bar(cs, tw + V((0.009, 0.0, 0.0)), tw + V((0.009, (T['r'] * K - 0.010) * math.cos(a), (T['r'] * K - 0.010) * math.sin(a))), 0.008, 0.006, V((1, 0, 0)), 'ck_black')
    sp = V((tw.x - 0.004, tw.y + 0.02, zf + 0.05))
    disc(cs, sp, V((-1, 0, 0)), PU, 0.025, 0.010, 'ck_gun', N=16)
    for sgn in (-1, 1):
        a_ = tw + V((-0.004, sgn * 0.045, -0.045)); b_ = sp + V((0, sgn * 0.024, 0))
        n_ = max(4, int((b_ - a_).length / 0.012))
        for k in range(n_):
            q0 = a_ + (b_ - a_) * (k / n_); q1 = a_ + (b_ - a_) * ((k + 0.7) / n_)
            _bar(cs, q0, q1, 0.006, 0.010, V((1, 0, 0)), 'ck_gun')
    # left switch box on the wall (WT y -0.62..-0.78, z 0.16..0.32): dark plate with toggles
    sb = V((-(min(wall_half(-0.78 * K, 0.165), wall_half(-0.78 * K, 0.315), wall_half(-0.62 * K, 0.315)) + 0.012), -0.70 * K, 0.24))
    box(cs, sb, (0.030, 0.16 * K, 0.15), 'ck_dark')
    for k in range(4):
        _toggle(cs, sb + V((0.016, -0.05 + 0.033 * k, 0.03)), V((1, 0, 0)), PU)
    # sill lever on the left (WT): red ball on a metal rod in a bracket on the sill
    rl = V((-wall_half(-0.58 * K, 0.52) + 0.020, -0.58 * K, 0.50))
    box(cs, rl + V((-0.006, 0, -0.010)), (0.016, 0.030, 0.030), 'interior')
    _bar(cs, rl, rl + V((0.010, -0.020, 0.075)), 0.006, 0.008, V((1, 0, 0)), 'gear')
    kb = rl + V((0.010, -0.020, 0.075))
    sph = [circle_pts(kb + V((0, 0, 0.012 + 0.012 * math.cos(math.pi * (j + 1) / 7))), V((0, 0, 1)), 0.012 * math.sin(math.pi * (j + 1) / 7), 12) for j in range(6)]
    loft(cs, sph, 'navred', closed=True, outward=True)
    fan_cap(cs, sph[0], kb + V((0, 0, 2 * 0.012)), 'navred', V((0, 0, 1)))
    fan_cap(cs, sph[-1], kb, 'navred', V((0, 0, -1)))
    # right side (WT): radio set forward as a rounded leather-covered housing with small black knobs on a backing plate; cowl-flap
    # handwheel (pale disc + lever with a blue tip) on the wall; switch box on the wall with toggles; gear and flap selectors aft
    xr = wall_half(-0.43 * K, 0.50) - 0.02
    rb = V((xr, -0.43 * K, 0.495))
    prof_r = [(-0.04, 0.035), (-0.028, 0.048), (0.028, 0.048), (0.04, 0.035), (0.04, -0.035), (0.028, -0.048), (-0.028, -0.048), (-0.04, -0.035)]
    prism(cs, [rb + V((0.0, py_, pz_)) for py_, pz_ in prof_r], V((-1, 0, 0)), 0.045, 'ck_leather')
    prism(cs, [rb + V((-0.046, -0.030, -0.030)), rb + V((-0.046, 0.030, -0.030)), rb + V((-0.046, 0.030, 0.030)), rb + V((-0.046, -0.030, 0.030))], V((-1, 0, 0)), 0.003, 'ck_dark')
    for k in range(3):
        cylinder(cs, rb + V((-0.049, -0.018 + 0.018 * k, -0.015)), rb + V((-0.057, -0.018 + 0.018 * k, -0.015)), 0.005, N=10, mat='ck_black')
    disc(cs, rb + V((-0.049, 0.0, 0.013)), V((-1, 0, 0)), PU, 0.012, 0.002, 'gauges', 'oxy', N=16)
    hwc = V((wall_half(-0.645 * K, 0.51) - 0.012, -0.645 * K, 0.51))
    ring(cs, hwc, V((-1, 0, 0)), 0.042, 0.032, 0.014, 'alu', N=32)
    disc(cs, hwc, V((-1, 0, 0)), PU, 0.033, 0.008, 'alu', N=24)
    cylinder(cs, hwc - V((0.008, 0, 0)), hwc - V((0.024, 0, 0)), 0.010, N=12, mat='gear')
    _bar(cs, hwc - V((0.024, 0, 0)), hwc - V((0.028, 0.110, -0.012)), 0.006, 0.010, V((1, 0, 0)), 'gear')
    _bar(cs, hwc - V((0.028, 0.105, -0.011)), hwc - V((0.028, 0.140, -0.014)), 0.009, 0.012, V((1, 0, 0)), 'ck_blue')
    cbx = V((min(wall_half(y_ * K, z_) for y_ in (-0.58, -0.75) for z_ in (0.235, 0.325)) + 0.012, -0.665 * K, 0.28))
    box(cs, cbx, (0.028, 0.16, 0.09), 'ck_dark')
    for k in range(3):
        _toggle(cs, cbx + V((-0.015, -0.045 + 0.045 * k, 0.0)), V((-1, 0, 0)), PU)
    for k, (yo, col) in enumerate(((-1.10, 'navred'), (-1.20, 'ck_white'))):
        gl = V((0.29, yo * K, 0.275))
        box(cs, gl, (0.04, 0.06, 0.02), 'ck_dark')
        _bar(cs, gl, gl + V((0, 0.03, 0.10)), 0.006, 0.009, V((1, 0, 0)), 'gear')
        cylinder(cs, gl + V((0, 0.03, 0.10)), gl + V((0, 0.03, 0.13)), 0.013, N=10, mat=col)
        _label(cs, gl + V((-0.021, 0, 0.0)), V((-1, 0, 0)), PU, 0.024, 0.010)
    parts.append(Part('cockpit_consoles', 'fus_center', V((0, eye.y + 0.2, 0.18)), cs, info=dict(kind='cockpit')))
    for p_ in parts:
        if p_.name in ('cockpit_consoles',):
            p_.own_uv = True
    return parts
