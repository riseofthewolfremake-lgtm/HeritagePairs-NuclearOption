"""A6M2 Zero Model 21 exterior parts (round 1): our own procedural geometry from the reviewed numbers in a6m2_spec.py.

Every builder returns Part objects (world-space meshes, GEAR DOWN, flight attitude; see b25h_parts.Part). No file under refs\\ is read;
every coordinate comes from a6m2_spec (pre-scale numbers) through S.pre() / S.span_built() (scale + span plug, design 0.1.1).
Construction rules carried over (memory airframe-build-lessons, prop-blade-one-renderer, fd32 reviews):
  - every shell is closed (break faces = 'structure' ribs / frames), the fuselage has a backed inner skin (cockpit opening, wells);
  - lofts use b25h_geom.loft(outward=True) and the model check tests the face orientation of every mesh;
  - each prop blade is ONE mesh with one material ('prop'), no child objects;
  - the gear is modelled down; the leg cover is built flush in the retracted pose and rotated into the down pose with the leg.
"""
import math
from mathutils import Vector, Quaternion, Matrix
import a6m2_spec as S
from b25h_geom import (V, MeshBuf, loft, fan_cap, annulus, oriented_quad, cylinder, box, planar_uv, Station, naca_pts,
                       circle_pts, frame_from_axes, section_cap)
from b25h_parts import Part

K = S.K
ATTACH = []          # (object name, point, [target object names]) for the connectivity check


def attach(obj, p, targets):
    ATTACH.append((obj, tuple(V(p)), list(targets)))


def P(p, plug=True):
    return V(S.pre(p, plug))


def frame_x(xaxis, zhint=(0, 0, 1)):
    return frame_from_axes(V(xaxis), V(zhint))


# =============================================================================================== fuselage body
def body_params(yb):
    """built y -> built (zt, zb, hw, zw, nt, nb) (linear between the pre-scale stations, scaled by K)."""
    yp = yb / K
    tab = sorted(S.BODY, key=lambda r: r[0])
    vals = [S.lin(tab, yp, c) for c in range(1, 7)]
    zt, zb, hw, zw, nt, nb = vals
    return zt * K, zb * K, hw * K, zw * K, nt, nb


# r8j (in game r8i: dark vertical wedge at the front of the root fillet): the floor clamp switched ON at the centre-section LE
# (wing_upper_centre_z is None ahead of it), so at y ~0.797 the body bottom jumped ~0.1 m and the side pinched 40 mm inward in 5 mm of y:
# an aft- and down-facing step just ahead of the fillet front. The clamp now fades in behind the LE (aiming ahead of it, r8j try 1,
# changed the fillet nose rows: fillet smooth 2.7 > 2.5 and belly shading seams).
FLOOR_CLAMP_LE_FADE = True
FLOOR_CLAMP_LE_RAMP = 0.06     # chord fraction behind the centre LE over which the clamp fades in


def wing_upper_centre_z(yb):
    """upper skin z of the wing centre section at x = 0 (built y): the body floor stays just inside it (wells below)."""
    st = wing_station(0.0, 1)
    c = st.chord
    s = (st.le.y - yb) / max(c, 1e-6)
    if s <= 0.0 or s >= 1.0:
        return None
    return st.point(min(max(s, 0.0), 1.0), True).z


# ring parameter u in [0, 1): 0 top centre, 0.25 +x side (zw), 0.5 bottom, 0.75 -x side. Dense near the gun troughs (u ~0.06 / 0.94).
def _u_list(n_base=88, dense=((0.025, 0.095), (0.905, 0.975)), factor=4.0):
    fine = 2000
    w = []
    for k in range(fine):
        u = (k + 0.5) / fine
        w.append(factor if any(a <= u <= b for a, b in dense) else 1.0)
    tot = sum(w)
    out = [0.0]
    acc = 0.0
    step = tot / n_base
    nxt = step
    for k in range(fine):
        acc += w[k]
        while acc >= nxt and len(out) < n_base:
            out.append((k + 1) / fine)
            nxt += step
    return out[:n_base]


U_RING = _u_list()
NR = len(U_RING)


def se_point(u, zt, zb, hw, zw, nt, nb):
    """(x, z) on the two-superellipse section; u as U_RING."""
    a = u * 2 * math.pi                       # 0 top, pi/2 +x, pi bottom
    sx = math.sin(a)
    cz = math.cos(a)
    if cz >= 0:                                # upper half
        x = math.copysign(hw * abs(sx) ** (2.0 / nt), sx)
        z = zw + (zt - zw) * abs(cz) ** (2.0 / nt)
    else:
        x = math.copysign(hw * abs(sx) ** (2.0 / nb), sx)
        z = zw - (zw - zb) * abs(cz) ** (2.0 / nb)
    return x, z


def trough_depth(x, z, yb):
    """gun-trough groove depth at a top-surface point of the cowl (0 outside)."""
    y0, y1 = S.TROUGH_Y[0] * K, S.TROUGH_Y[1] * K
    if yb < y0 - 0.001 or yb > y1 + 0.001 or z < 0.30:
        return 0.0
    w = S.TROUGH_HALF_W * K
    d = abs(abs(x) - S.TROUGH_X * K)
    if d >= w:
        return 0.0
    ramp = min(1.0, (yb - y0) / 0.03 + 0.0) if yb >= y0 else 0.0
    return ramp * math.cos(d / w * math.pi / 2) ** 0.6


def _sstep(e0, e1, v):
    t = min(max((v - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def body_ring(yb, inset=0.0, trough=True):
    zt, zb, hw, zw, nt, nb = body_params(yb)
    # r8d (r8c sheets: jagged light shards where wing, fillet and fuselage meet at the LE root). Cause: two switches in the body section at
    # the wing root - the floor clamp started at y 0.70 (pre) as a step (zb jumped, so every lower ring point moved between two stations),
    # and the per-point hug of the wing's upper skin switched on at s = -0.02 and off at 1.02 (a 0.1-0.2 m cliff in the body bottom just
    # ahead of the LE nose and behind the TE, crossing the wing skin at a shallow angle). Both are now ramped: the floor clamp over y 0.70 ->
    # 0.92, the hug over s -0.14 -> 0.03 at the LE and 0.97 -> 1.12 at the TE, and near the thin LE / TE the target is never below the wing's
    # mid-height there (the body stays inside the nose instead of poking out under it).
    fw_ = 0.0 if yb / K < -2.0 else _sstep(0.92, 0.70, yb / K)
    if fw_ > 0.0:
        zu = wing_upper_centre_z(yb)
        wc_ = 1.0
        if zu is not None and FLOOR_CLAMP_LE_FADE:  # r8j: the clamp switched on at full strength right at the centre LE (zu None ahead of
            st0_ = wing_station(0.0, 1)             # it): a step in the body. It now fades in over FLOOR_CLAMP_LE_RAMP of chord behind the LE.
            wc_ = _sstep(0.0, FLOOR_CLAMP_LE_RAMP, (st0_.le.y - yb) / max(st0_.chord, 1e-6))
        if zu is not None:
            zb = zb + max(0.0, zu - 0.012 - zb) * fw_ * wc_
    pts = []
    for u in U_RING:
        x, z = se_point(u, zt - inset, zb + inset, hw - inset, zw, nt, nb)
        if z < zw:                                  # r1 check: inside the wing chord the body's lower surface hugs the wing's upper skin
            st = wing_station(min(abs(x), 0.55 * K), 1)    # from inside (12 mm), so the wheel wells under it stay clear
            s_ = (st.le.y - yb) / st.chord
            w_ = _sstep(-0.14, 0.03, s_) * (1.0 - _sstep(0.97, 1.12, s_))
            if w_ > 0.0:
                sc = min(max(s_, 0.0), 1.0)
                up_, lo_ = st.point(sc, True).z, st.point(sc, False).z
                tgt = max(up_ - 0.012, 0.5 * (up_ + lo_))
                if tgt > z:
                    z = z + (tgt - z) * w_
        if trough and inset == 0.0:
            t = trough_depth(x, z, yb)
            if t > 0:
                floor = S.TROUGH_FLOOR_Z * K
                z = z + (floor - z) * t if z > floor else z
        pts.append(V((x, yb, z)))
    return pts


def body_z_at(x, yb):
    """upper-surface z of the body at |x| (no trough)."""
    zt, zb, hw, zw, nt, nb = body_params(yb)
    r = min(abs(x) / hw, 0.999)
    return zw + (zt - zw) * (1 - r ** nt) ** (1.0 / nt)


def body_ys(y0, y1, step=0.10, extra=()):
    """built stations from y0 (front) down to y1, every <= step, including the pre-scale table stations and extra."""
    req = sorted({round(y0, 5), round(y1, 5)} | {round(r[0] * K, 5) for r in S.BODY if y1 < r[0] * K < y0}
                 | {round(e, 5) for e in extra if y1 < e < y0}, reverse=True)
    out = [req[0]]
    for a, b in zip(req, req[1:]):
        n = max(1, int(math.ceil((a - b) / step - 1e-9)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return out


def cockpit_open(xc, yc, zc):
    """faces of the root body skin removed for the cockpit opening (under the sliding hood: pilot's opening)."""
    yp = yc / K
    if not (-1.30 <= yp <= -0.25):
        return False
    xs = S.lin(S.CANOPY, yp, 1) * K - 0.025
    return abs(xc) < xs and zc > body_z_at(xs, yc) - 0.005


def in_hook_slot(q):
    y0, y1, hw, roof = S.HOOK_SLOT
    return y1 * K <= q.y <= y0 * K and abs(q.x) < hw * K and q.z < body_params(q.y)[3]


def hook_slot(mb):
    """the stowed hook's belly slot (r1 overlay: the belly line stays, the hook lies in a slot like the reference): side walls, roof,
    end walls (well colour) and a flush rim band over the stepped skin cut."""
    y0, y1, hw, roof = S.HOOK_SLOT
    y0, y1, hw, roof = y0 * K, y1 * K, hw * K, roof * K
    n = 16
    ys = [y0 + (y1 - y0) * k / n for k in range(n + 1)]
    def zb(x, y):
        zt, zb_, hw_, zw, nt, nb = body_params(y)
        r = min(abs(x) / hw_, 0.999)
        return zw - (zw - zb_) * (1 - r ** nb) ** (1.0 / nb) - 0.0015
    for k in range(n):
        ya, yb_ = ys[k], ys[k + 1]
        for s_ in (-1, 1):
            q = [V((s_ * hw, ya, zb(hw, ya))), V((s_ * hw, yb_, zb(hw, yb_))), V((s_ * hw, yb_, roof)), V((s_ * hw, ya, roof))]
            oriented_quad(mb, q, 'well', V((-s_, 0, 0)))
            r = [V((s_ * hw, ya, zb(hw, ya))), V((s_ * hw, yb_, zb(hw, yb_))), V((s_ * (hw + 0.045), yb_, zb(hw + 0.045, yb_))), V((s_ * (hw + 0.045), ya, zb(hw + 0.045, ya)))]
            oriented_quad(mb, r, 'paint', V((0, 0, -1)), uv=[planar_uv(x, V((0, 0, -1))) for x in r])
        oriented_quad(mb, [V((-hw, ya, roof)), V((hw, ya, roof)), V((hw, yb_, roof)), V((-hw, yb_, roof))], 'well', V((0, 0, -1)))
    if OPEN_BREAKS:
        # r8o: the fus_tail front end is open (no cap): from inside the fuselage the slot's walls and roof (and the stepped cut of the inner
        # skin round it) were seen from behind (culled: sky through the slot).
        # r8o round 3 (review of round 2: the r8o dark backing tray - 0.19 m wide, roof high, 1.3 m long - read as a large black box in the
        # lower fus_tail section): no tray. The slot's own walls, roof and end walls get backs 1 mm outside in the interior paint (a slim
        # channel the colour of the lining), and the belly round the slot - between the slot edge and the inner skin's cell-stepped cut -
        # gets a flat floor strip 4 mm over the outer skin facing in (interior paint, under the inner skin's level).
        bk, mx, my = 0.001, 0.035, 0.11
        X, Ya, Yb = hw + mx, y0 + my, y1 - my
        yT = [Ya + (y0 - Ya) * k / 3 for k in range(3)] + ys + [y1 + (Yb - y1) * k / 3 for k in range(1, 4)]
        for k in range(n):                                     # wall / roof backs over the slot length
            ya, yb_ = ys[k], ys[k + 1]
            for s_ in (-1, 1):
                q = [V((s_ * (hw + bk), ya, zb(hw, ya) + 0.004)), V((s_ * (hw + bk), yb_, zb(hw, yb_) + 0.004)),
                     V((s_ * (hw + bk), yb_, roof + bk)), V((s_ * (hw + bk), ya, roof + bk))]
                oriented_quad(mb, q, 'interior', V((s_, 0, 0)))
            oriented_quad(mb, [V((-hw - bk, ya, roof + bk)), V((hw + bk, ya, roof + bk)), V((hw + bk, yb_, roof + bk)), V((-hw - bk, yb_, roof + bk))],
                          'interior', V((0, 0, 1)))
        for yy, tw in ((y0 + bk, V((0, 1, 0))), (y1 - bk, V((0, -1, 0)))):     # end wall backs
            oriented_quad(mb, [V((-hw - bk, yy, zb(hw, yy) + 0.004)), V((hw + bk, yy, zb(hw, yy) + 0.004)), V((hw + bk, yy, roof + bk)),
                               V((-hw - bk, yy, roof + bk))], 'interior', tw)
        xs_ = [-X + 2 * X * k / 8 for k in range(9)]
        for ya, yb_ in zip(yT, yT[1:]):                        # floor strip round the slot (faces up, into the fuselage)
            in_slot = y1 - 1e-6 <= 0.5 * (ya + yb_) <= y0 + 1e-6
            for xa, xb_ in zip(xs_, xs_[1:]):
                pieces = [(xa, xb_)]
                if in_slot:
                    pieces = [(a_, b_) for a_, b_ in ((xa, min(xb_, -hw - bk)), (max(xa, hw + bk), xb_)) if b_ - a_ > 1e-4]
                for a_, b_ in pieces:
                    oriented_quad(mb, [V((a_, ya, zb(a_, ya) + 0.004)), V((b_, ya, zb(b_, ya) + 0.004)), V((b_, yb_, zb(b_, yb_) + 0.004)),
                                       V((a_, yb_, zb(a_, yb_) + 0.004))], 'interior', V((0, 0, 1)))
    for yy, tw in ((y0, V((0, -1, 0))), (y1, V((0, 1, 0)))):
        oriented_quad(mb, [V((-hw, yy, zb(hw, yy))), V((hw, yy, zb(hw, yy))), V((hw, yy, roof)), V((-hw, yy, roof))], 'well', tw)
        for dy in ((0.0, 0.045) if tw.y < 0 else (-0.045, 0.0),):
            yy2 = yy + (0.045 if tw.y < 0 else -0.045)
            r = [V((-(hw + 0.045), yy, zb(hw, yy))), V((hw + 0.045, yy, zb(hw, yy))), V((hw + 0.045, yy2, zb(hw, yy2))), V((-(hw + 0.045), yy2, zb(hw, yy2)))]
            oriented_quad(mb, r, 'paint', V((0, 0, -1)), uv=[planar_uv(x, V((0, 0, -1))) for x in r])


def body_uv(rings, ys):
    from b25h_geom import arc_lengths
    al = [arc_lengths(r) for r in rings]

    def f(ci, cj, j):
        acc, Pm = al[ci]
        if cj == 0 and j == NR - 1:
            return (ys[ci], Pm)
        return (ys[ci], acc[cj])
    return f


INNER_ROOT_INSET = 0.008   # r8j: extra inner-skin inset (m) on the lower body at the wing root
SEAM_BAND = 0.025          # r8o: dark band (metal_dark) at the open end of every inner skin / wing liner (m)
OPEN_BREAKS = True         # r8o: break ends are open (no cap) with a set-back frame / rib, as stock and the accepted B-25H v3
STAB_ROOT_SETBACK = 0.06   # r8o: stab / fin root rib set back (m; thin sections, the root lies inside fus_tail)
TAIL_CAVITY = 0.30         # r8o round 2: stab / fin root: lined cavity to a bay-end wall 0.30 m in (the cap strip at 0.06 m is open)


def body_section(name, y0, y1, cap_front, cap_back, extra=()):
    """closed outer skin + inner skin (interior) between built y0 > y1; caps = 'paint' (structure ring), 'fan' or None."""
    # r8e: dense stations where the body meets the wing (the LE ramp y 0.40..1.0 every 25 mm, the TE ramp every 50 mm): the 0.1 m stations
    # showed as flat facets at 0.5 m once the wing / fairing were unioned into this skin
    dense = [round(1.0 - 0.025 * k, 4) for k in range(25)] + [round(-1.50 - 0.05 * k, 4) for k in range(18)]
    ys = body_ys(y0, y1, extra=list(extra) + [d * K for d in dense])
    outer = [body_ring(y) for y in ys]
    def inner_of(y, ro):                          # r1 check: the inner skin follows the gun troughs (was poking out above their floor)
        zw = body_params(y)[3]
        # r8j: under the LE root the unioned outer skin's cut polygons sag up to ~8 mm below the ring (exact boolean on the curved body
        # quads), so the 6 mm inner skin poked out under the right LE root (x 0.25-0.27, y 0.79: interior seen from below). Lower half,
        # y 0.40-1.00: 14 mm.
        wl = INNER_ROOT_INSET * _sstep(0.30 * K, 0.40 * K, y) * (1.0 - _sstep(1.00 * K, 1.08 * K, y))
        return [p - V((p.x, 0, p.z - zw)).normalized() * (0.006 + (wl if p.z < zw else 0.0)) for p in ro]
    inner = [inner_of(y, ro) for y, ro in zip(ys, outer)]
    mb = MeshBuf()
    cut = name == 'A6M2'
    slot = name == 'fus_tail'

    def keep(i, j):
        a, b, c, d = outer[i][j], outer[i][(j + 1) % NR], outer[i + 1][j], outer[i + 1][(j + 1) % NR]
        if slot:
            return not any(in_hook_slot(q) for q in (a, b, c, d))
        if not cut:
            return True
        cen = (a + b + c + d) / 4
        return not cockpit_open(cen.x, cen.y, cen.z)
    loft(mb, outer, 'paint', closed=True, outward=True, uvfunc=body_uv(outer, ys), keep=keep)
    # r8o: an open break end ('paint') gets a dark band SEAM_BAND long at the end of the inner skin (seam backing: through a hairline joint
    # one sees 'metal_dark', and the end frame stays hidden); the outer skin keeps its stations (paint faces / livery atlas untouched), the
    # inner skin's end row is split at the band edge when it is longer than the band
    nrow = len(ys) - 1
    band_rows = {}
    for mode, i_end, sgn in ((cap_front, 0, -1), (cap_back, nrow - 1, 1)):
        if mode != 'paint':
            continue
        y_end = ys[0] if i_end == 0 else ys[-1]
        y_b = y_end + sgn * SEAM_BAND
        y_far = ys[i_end + 1] if i_end == 0 else ys[i_end]
        if abs(y_far - y_end) <= SEAM_BAND + 0.004:
            band_rows[i_end] = None                               # the end row is the band
        else:
            band_rows[i_end] = y_b
    loft(mb, inner, 'interior', closed=True, outward=False, keep=lambda i, j: keep(i, j) and i not in band_rows,
         face_mat=None)
    for i_end, y_b in band_rows.items():
        r0, r1 = inner[i_end], inner[i_end + 1]
        if y_b is None:
            loft(mb, [r0, r1], 'metal_dark', closed=True, outward=False)
            continue
        rb = inner_of(y_b, body_ring(y_b))
        if i_end == 0:
            loft(mb, [r0, rb], 'metal_dark', closed=True, outward=False)
            loft(mb, [rb, r1], 'interior', closed=True, outward=False)
        else:
            loft(mb, [r0, rb], 'interior', closed=True, outward=False)
            loft(mb, [rb, r1], 'metal_dark', closed=True, outward=False)
    if slot:
        hook_slot(mb)
    if cut:          # sill walls round the opening (outer skin -> inner skin), so the opening shows a skin edge, not a gap
        for i in range(len(ys) - 1):
            for j in range(NR):
                if keep(i, j):
                    continue
                for (di, dj, ei, ej) in ((0, 0, 0, 1), (1, 0, 1, 1), (0, 0, 1, 0), (0, 1, 1, 1)):
                    # edge (i+di, j+dj)-(i+ei, j+ej) is on the boundary when the neighbouring face across it is kept
                    if (di, ei) == (0, 0):
                        nb_ = (i - 1, j) if i > 0 else None
                    elif (di, ei) == (1, 1):
                        nb_ = (i + 1, j) if i + 1 < len(ys) - 1 else None
                    elif (dj, ej) == (0, 0):
                        nb_ = (i, (j - 1) % NR)
                    else:
                        nb_ = (i, (j + 1) % NR)
                    if nb_ is None or not keep(*nb_):
                        continue
                    a, b = outer[i + di][(j + dj) % NR], outer[i + ei][(j + ej) % NR]
                    ai, bi = inner[i + di][(j + dj) % NR], inner[i + ei][(j + ej) % NR]
                    cen = (outer[i][j] + outer[i + 1][(j + 1) % NR]) / 2
                    oriented_quad(mb, [a, b, bi, ai], 'interior', cen - (a + b) / 2)
    for ring_o, ring_i, yy, tow, mode in ((outer[0], inner[0], ys[0], V((0, 1, 0)), cap_front), (outer[-1], inner[-1], ys[-1], V((0, -1, 0)), cap_back)):
        if mode == 'paint':
            # r8o (user test r8n: a SOLID round metal disc closed every break; stock breaks are open): no cap. The annulus between the outer
            # and the inner skin is the 6 mm skin edge, dark (seam backing, r8g / 1.9.13 rule); the end frame and stubs are in
            # a6m2_internals.fus_end_frame / fuselage_frames, END_FRAME_SETBACK inside the plane
            annulus(mb, ring_o, ring_i, 'metal_dark', tow)
        elif mode == 'fan':
            c = sum(ring_o, V()) / NR
            fan_cap(mb, ring_o, c, 'paint', tow, uvfunc=lambda p, t=tow: planar_uv(p, t))
            fan_cap(mb, ring_i, c - tow * 0.006, 'interior', -tow)
    return mb


def build_fuselage():
    ye, yr, yt = S.ENGINE_AFT_Y * K, S.REAR_FWD_Y * K, S.TAIL_FWD_Y * K
    ylip = S.COWL_LIP_Y * K
    parts = []
    eng = body_section('fus_engine', ylip, ye, None, 'paint', extra=[S.TROUGH_Y[0] * K, S.TROUGH_Y[0] * K + 0.03])
    cowl_lip(eng)
    cowl_flaps(eng)
    chin_fairing(eng)
    exhausts(eng)
    engine_front(eng)
    gun_troughs(eng)
    parts.append(Part('fus_engine', 'A6M2_root', (0, 1.30, 0), eng))
    root = body_section('A6M2', ye, yr, 'paint', 'paint', extra=[-0.25 * K, -1.30 * K, -0.264 * K])
    cockpit_floor(root)       # round 4: the cockpit itself is a6m2_cockpit.build_cockpit() (separate cockpit_* / gauge_* parts)
    parts.append(Part('fus_center', 'A6M2_root', (0, -0.90, 0), root))
    rear = body_section('fus_rear', yr, yt, 'paint', 'paint')
    parts.append(Part('fus_rear', 'A6M2_root', (0, -3.40, 0.05), rear))
    tail = body_section('fus_tail', yt, S.TAIL_TIP_Y * K, 'paint', None)
    parts.append(Part('fus_tail', 'A6M2_root', (0, -5.00, 0.10), tail))
    return parts


# ----------------------------------------------------------------------------------------------- cowl details
def cowl_lip(mb):
    """rounded lip from the outer skin ring at y 1.94 rolling in to the opening (r 0.375) and an inner duct to the engine face."""
    y0 = S.COWL_LIP_Y * K
    outer = body_ring(y0, trough=False)
    zc = -0.005 * K
    rin = S.COWL_LIP_IN_R * K
    rings = [outer]
    for k, a in enumerate((25, 55, 90, 125, 160)):
        t = math.radians(a)
        f = (1 - math.cos(t)) / 2                       # 0 at the outer ring, 1 at the inner radius
        yy = y0 + 0.035 * math.sin(t) - (1 - math.cos(t)) * 0.018
        ring = []
        for p in outer:
            d = V((p.x, 0, p.z - zc))
            r_o = d.length
            r = r_o + (rin - r_o) * f
            ring.append(V((d.x / max(r_o, 1e-6) * r, yy, zc + d.z / max(r_o, 1e-6) * r)))
        rings.append(ring)
    # inner duct back to the engine face
    yf = S.ENGINE_FACE_Y * K
    for yy in (S.COWL_LIP_IN_Y * K - 0.02, yf + 0.05, yf, yf - 0.06):     # r1 check: the duct runs 60 mm past the engine face (no gap at the baffle)
        rr = rin + (0.02 if yy < S.COWL_LIP_IN_Y * K - 0.03 else 0.0)
        rings.append([V((p.x, yy, p.z)) for p in circle_ring(rr, zc, yy, outer)])
    # orientation: outward = away from the axis for the lip front; the duct faces the axis
    loft(mb, rings[:6], 'paint', closed=True, outward=True)
    loft(mb, rings[5:], 'metal_dark', closed=True, outward=False)
    fan_cap(mb, rings[-1], V((0, yf - 0.06, zc)), 'metal_dark', V((0, 1, 0)))       # duct back wall (faces forward)


def circle_ring(r, zc, yy, like):
    """circle with the same angular order as a body ring (point k at the angle of like[k])."""
    out = []
    for p in like:
        a = math.atan2(p.x, p.z - zc)
        out.append(V((r * math.sin(a), yy, zc + r * math.cos(a))))
    return out


def engine_front(mb):
    """Sakae front row behind the opening (dark baffle, 7 cylinders with fins, crankcase, reduction housing up to the spinner)."""
    zc = -0.005 * K
    yf = S.ENGINE_FACE_Y * K
    rin = S.COWL_LIP_IN_R * K
    # baffle disc closing the duct (seen dark through the gaps)
    ring = circle_pts(V((0, yf, zc)), V((0, 1, 0)), rin + 0.010, 48)
    fan_cap(mb, ring, V((0, yf, zc)), 'metal_dark', V((0, 1, 0)))
    for k in range(7):
        a = 2 * math.pi * k / 7 + math.pi / 7
        d = V((math.sin(a), 0, math.cos(a)))
        base = V((0, yf + 0.005, zc)) + d * 0.17
        tip = V((0, yf + 0.005, zc)) + d * 0.335
        cyl_axis = tip - base
        cylinder(mb, base + V((0, 0.07, 0)), tip + V((0, 0.07, 0)), 0.068, 0.062, N=14, mat='engine')
        for f in range(5):                            # cooling fins
            c0 = base + cyl_axis * (0.25 + 0.15 * f) + V((0, 0.07, 0))
            cylinder(mb, c0 - cyl_axis.normalized() * 0.004, c0 + cyl_axis.normalized() * 0.004, 0.085, N=14, mat='engine')
    cylinder(mb, V((0, yf + 0.004, zc)), V((0, yf + 0.13, zc)), 0.20, 0.19, N=28, mat='engine')          # crankcase front
    ync = S.NOSECASE_Y0 * K
    cylinder(mb, V((0, yf + 0.12, zc)), V((0, S.SPINNER[0][0] * K + 0.004, zc)), S.NOSECASE_R * K, S.NOSECASE_R * K * 0.98,
             N=32, mat='metal_dark')                                                                      # reduction housing to the spinner back


def body_point_at_elev(ring, side, el):
    """point on a body ring at elevation el (rad, atan2(z, side*x)) on one side, interpolated between ring points
    (r1 picked the nearest ring point: the flap edges stepped with the ring spacing, a Z-shaped seam)."""
    pts = [p for p in ring if p.x * side > 1e-6]
    best = None
    for a, b in zip(pts, pts[1:]):
        ea, eb = math.atan2(a.z, side * a.x), math.atan2(b.z, side * b.x)
        if (ea - el) * (eb - el) <= 0 and abs(ea - eb) > 1e-9:
            t = (el - ea) / (eb - ea)
            best = a + (b - a) * t
            break
    if best is None:
        best = min(pts, key=lambda p: abs(math.atan2(p.z, side * p.x) - el))
    return best


def cowl_flaps(mb):
    """r1b: one even band of cowl flaps a side (S.COWL_FLAP_ANG), each a 4 mm thick panel whose edges sit exactly on their
    elevation lines (no Z seams), flush at the hinge and standing 7 mm out at the trailing edge (the closed-flap step)."""
    yh, yt = S.COWL_FLAP_Y[0] * K, S.COWL_FLAP_Y[1] * K
    ring_h, ring_t = body_ring(yh, trough=False), body_ring(yt, trough=False)
    for side in (1, -1):
        for a0, a1 in S.COWL_FLAP_ANG:
            n = 6
            row_h, row_t = [], []
            for k in range(n + 1):
                el = math.radians(a0 + (a1 - a0) * k / n)
                for ring, row, proud in ((ring_h, row_h, 0.0015), (ring_t, row_t, 0.007)):
                    p = body_point_at_elev(ring, side, el)
                    d = V((p.x, 0, p.z)).normalized()
                    row.append(p + d * proud)

            def inn(p):
                return p - V((p.x, 0, p.z)).normalized() * 0.004
            for k in range(n):
                q = [row_h[k], row_h[k + 1], row_t[k + 1], row_t[k]]
                cen = sum(q, V()) / 4
                oriented_quad(mb, q, 'paint', V((cen.x, 0, cen.z)), [planar_uv(p, V((cen.x, 0, cen.z))) for p in q])
                oriented_quad(mb, [inn(p) for p in q], 'metal_dark', -V((cen.x, 0, cen.z)))
            for row, tw in ((row_h, V((0, 1, 0))), (row_t, V((0, -1, 0)))):
                for k in range(n):
                    a, b = row[k], row[k + 1]
                    oriented_quad(mb, [a, b, inn(b), inn(a)], 'metal_dark', tw)
            fc = sum(row_h + row_t, V()) / (2 * (n + 1))
            for k in (0, n):
                a, b = row_h[k], row_t[k]
                oriented_quad(mb, [a, b, inn(b), inn(a)], 'metal_dark', (a + b) / 2 - fc)


CHIN_TUCK = True
CHIN_TUCK_Y = 0.80          # stations ahead of the centre-section LE (y 0.797); inside the wing the old top stays (clear of the wells)
CHIN_TUCK_IN = 0.040


def chin_fairing(mb):
    """oil-cooler chin under the cowl (y 1.62 .. 0.62), a half-round fairing with the intake at the front."""
    rings = []
    st_ = list(S.CHIN)
    if CHIN_TUCK:            # r8j: one more station on the tuck line (the slot reopened between the 0.85 and 0.65 stations at y 0.80)
        a_, b_ = [r for r in st_ if r[0] > CHIN_TUCK_Y][-1], [r for r in st_ if r[0] <= CHIN_TUCK_Y][0]
        t_ = (a_[0] - (CHIN_TUCK_Y + 0.005)) / (a_[0] - b_[0])
        st_.insert(st_.index(b_), tuple(a_[k] + (b_[k] - a_[k]) * t_ for k in range(4)))
    for y, x, zbot, hw in st_:
        yb = y * K
        zt, zb, bhw, zw, nt, nb = body_params(yb)
        ztop = zb + 0.12
        if CHIN_TUCK and yb > CHIN_TUCK_Y:
            # r8j (in game r8i: dark slit under the LE root next to the cowl; offline: a see-through slot 0.17 m long, up to 0.06 m tall,
            # sideways under the nose at y 0.75-0.92): the body floor ahead of the centre LE is raised onto the wing (body_ring floor
            # clamp + hug), the chin's top stayed at the raw body bottom + 0.12. Its top now sits CHIN_TUCK_IN inside the actual belly.
            belly = max(q.z for q in body_ring(yb) if abs(q.x) <= hw * K + 0.015 and q.z < zw)
            ztop = max(ztop, belly + CHIN_TUCK_IN)
        ring = []
        for k in range(13):
            a = math.pi * k / 12                       # 0 .. pi across the bottom (+x to -x)
            xx = hw * K * math.cos(a)
            zz = ztop - (ztop - zbot * K) * math.sin(a) ** 0.7
            ring.append(V((xx, yb, zz)))
        rings.append(ring)
    loft(mb, rings, 'paint', closed=True, outward=True)             # r1 check: closed (its aft end leaves the engine part's frame)
    for ring, tw in ((rings[0], V((0, 1, 0))), (rings[-1], V((0, -1, 0)))):
        c = sum(ring, V()) / len(ring)
        fan_cap(mb, ring, c, 'metal_dark', tw)


def exhausts(mb):
    """r1b: exhaust stacks (one a side, the Sakae collector outlets): a curved pipe of flattened section coming out from under
    the cowl-flap trailing edge, 3 mm wall, a rolled lip at the mouth and a sooted inside (was one short round stub)."""
    for x, y, z in S.EXHAUSTS:
        side = 1 if x > 0 else -1
        p = P((x, y, z), plug=False)
        d = V((side * 0.25, -1.0, -0.15)).normalized()
        start = p - d * 0.20 + V((-side * 0.035, 0, 0.03))      # inside the cowl under the flap band
        ctrl = p - d * 0.08
        path = []
        for k in range(7):
            t = k / 6
            path.append(start * (1 - t) ** 2 + ctrl * 2 * t * (1 - t) + p * t * t)
        rings_o, rings_i = [], []
        for k, c in enumerate(path):
            tg = (path[min(k + 1, 6)] - path[max(k - 1, 0)]).normalized()
            wv = V((0, 0, 1)) - tg * tg.z
            wv.normalize()
            hv = tg.cross(wv).normalized()
            a_, b_ = 0.036, 0.038                                   # r8c (WT cowl_under): a round 72-76 mm stub, not a flattened cone
            ro, ri = [], []
            fl = 1.0 + 0.10 * max(0.0, (k - 4) / 2)                # mouth flares 10 %
            a_, b_ = a_ * fl, b_ * fl
            for j in range(16):
                ph = 2 * math.pi * j / 16
                ro.append(c + hv * (a_ * math.cos(ph)) + wv * (b_ * math.sin(ph)))
                ri.append(c + hv * ((a_ - 0.003) * math.cos(ph)) + wv * ((b_ - 0.003) * math.sin(ph)))
            rings_o.append(ro)
            rings_i.append(ri)
        loft(mb, rings_o, 'metal_dark', closed=True, outward=True)          # r8c: sooty dark outside (WT), copper-brown inside
        loft(mb, rings_i, 'exhaust', closed=True, outward=False)
        tg = (path[-1] - path[-2]).normalized()
        annulus(mb, rings_o[-1], rings_i[-1], 'metal_dark', tg)     # mouth face (the 3 mm wall)
        annulus(mb, rings_o[0], rings_i[0], 'metal_dark', -tg)
        back = [path[2] + (q - path[2]) * 0.97 for q in rings_i[2]]
        fan_cap(mb, back, path[2], 'metal_dark', tg)                # soot-dark back wall inside the pipe


def gun_troughs(mb):
    """Type 97 barrel stubs (slim barrel + perforated jacket front) recessed in the troughs; the muzzle at y 0.911."""
    for side in (1, -1):
        m = P((side * S.TYPE97_MUZZLE[0], S.TYPE97_MUZZLE[1], S.TYPE97_MUZZLE[2]), plug=False)
        cylinder(mb, m - V((0, 0.22, 0)), m - V((0, 0.02, 0)), 0.024, N=12, mat='gunmetal')        # jacket front (perforated look: gunmetal)
        cylinder(mb, m - V((0, 0.02, 0)), m + V((0, 0.012, 0)), 0.011, N=10, mat='gunmetal')      # muzzle
        for k in range(4):                                                                         # jacket holes as dark rings
            c = m - V((0, 0.05 + 0.04 * k, 0))
            cylinder(mb, c - V((0, 0.006, 0)), c + V((0, 0.006, 0)), 0.0245, N=12, mat='metal_dark', cap0=False, cap1=False)


def cockpit_floor_z():
    """r4c: floor height = 20 mm above the HIGHEST point of the wing-centre upper skin under the cockpit (r4 used y -0.8 K only, and the
    skin, which rises forward, came up through the floor ahead of the stick: cream livery patch in the eye view)."""
    return max(wing_upper_centre_z(y * K) for y in [-0.22 - 0.05 * k for k in range(25)]) + 0.03   # r8: +30 mm (the tub check saw the wing top beside the floor)


def cockpit_floor(mb):
    """cockpit floor + stiffeners in the root body mesh (stock aircraft_structure look in Unity): it also closes the detached
    fus_center from below (see-through check), as the r1 placeholder floor did. Round 4."""
    zf = cockpit_floor_z()
    y0, y1 = -0.225 * K, -1.42 * K
    # r4c: wall to wall (r4 0.56 m left the cream wing-centre skin showing beside it from the eye) and in cockpit green
    fw = 2 * min(body_ring_x(y, zf - 0.006) for y in (y0, (y0 + y1) / 2, y1)) - 0.012
    box(mb, (0.0, (y0 + y1) / 2, zf), (fw, abs(y1 - y0), 0.012), 'ck_dark')          # r8b: darker floor (WT)
    for xs_ in (-0.20, -0.10, 0.10, 0.20):                                            # r8b: longitudinal floor stringers
        box(mb, (xs_, (y0 + y1) / 2, zf + 0.012), (0.014, abs(y1 - y0) - 0.04, 0.012), 'interior')
    # r8 tub check: the floor box stopped 6+ mm short of the walls (the wing-centre top skin showed beside it from the eye); edge strips per
    # 0.05 m reach 3 mm into the inner skin, from the bulkhead to the seat bulkhead
    ns_ = int(abs(y1 - y0) / 0.05) + 1
    for side in (1, -1):
        for k in range(ns_):
            ya_, yb2_ = y0 + (y1 - y0) * k / ns_, y0 + (y1 - y0) * (k + 1) / ns_
            xw_ = min(body_ring_x(ya_, zf - 0.006), body_ring_x(yb2_, zf - 0.006)) - 0.002
            box(mb, (side * (fw / 2 + xw_) / 2, (ya_ + yb2_) / 2, zf), (abs(xw_ - fw / 2) + 0.004, abs(yb2_ - ya_) + 0.002, 0.012), 'ck_dark')
            # kick strip up the curved wall (the wall leans out above the floor: 14 mm open at the floor top at the front corners)
            q_ = [V((side * xw_, ya_, zf - 0.004)), V((side * xw_, yb2_, zf - 0.004)),
                  V((side * (min(body_ring_x(yb2_, zf + 0.04), body_ring_x(ya_, zf + 0.04)) - 0.002), yb2_, zf + 0.04)),
                  V((side * (min(body_ring_x(yb2_, zf + 0.04), body_ring_x(ya_, zf + 0.04)) - 0.002), ya_, zf + 0.04))]
            oriented_quad(mb, q_, 'ck_dark', V((-side, 0, 1)))
    for k in range(5):
        y = y0 + (y1 - y0) * (k + 0.5) / 5
        box(mb, (0.0, y, zf + 0.0125), (fw - 0.06, 0.018, 0.013), 'interior')
    # forward bulkhead behind the instrument panel and the bulkhead behind the seat: they close the detached fus_center's cabin
    # (from outside one looked into the tube onto the back faces of the end caps)
    from a6m2_cockpit import prism
    # r8 (user review 1: gaps in the front panel looked into the engine): the forward bulkhead fills the WHOLE inner section, floor to
    # the deck skin (r7 stopped at z 0.62 and left the band under the deck open); with cockpit_coaming it closes the tub front
    for yb_, zt_ in ((-0.240 * K, body_params(-0.240 * K)[0] - 0.008), (-1.42 * K, 0.62)):
        zs_ = [zf - 0.01 + (zt_ - zf + 0.01) * k / 16 for k in range(17)]
        rt_ = [V((body_ring_x(yb_, z) - 0.004, yb_, z)) for z in zs_]       # 4 mm inside the outer skin: buried in the inner skin
        prism(mb, rt_ + [V((-p.x, p.y, p.z)) for p in reversed(rt_)], V((0, 1, 0)), 0.012, 'interior')


# =============================================================================================== canopy
def canopy_section(yb, n=17, base_drop=0.0):
    """glazing arc at built y: from the body surface at the base half-width (both sides) over the apex."""
    yp = yb / K
    xs = S.lin(S.CANOPY, yp, 1) * K
    zt = S.lin(S.CANOPY, yp, 2) * K
    ex = S.lin(S.CANOPY, yp, 3) * S.CANOPY_EXP_SCALE
    zb = body_z_at(xs, yb) - base_drop
    pts = []
    for k in range(n):
        a = math.pi * k / (n - 1)                    # 0 = +x base, pi = -x base
        cx = math.cos(a)
        sz = math.sin(a)
        x = math.copysign(xs * abs(cx) ** (2.0 / ex), cx)
        z = zb + (zt - zb) * abs(sz) ** (2.0 / ex)
        pts.append(V((x, yb, z)))
    return pts


def build_canopy():
    """windscreen (fixed, fus_center), sliding hood (canopy object), rear glazing (fixed): two-sided glass + frame bars."""
    parts = []
    y0, y1 = S.CANOPY_Y[0] * K, S.CANOPY_Y[1] * K
    pieces = [('canopy_windscreen', S.WINDSCREEN_Y), ('canopy_hood', S.HOOD_Y), ('canopy_rear', (S.HOOD_Y[1] - 0.010, S.REAR_GLAZ_Y[1]))]
    for name, (a, b) in pieces:
        ya, yb_ = a * K, b * K
        nseg = max(3, int(abs(ya - yb_) / 0.06))
        ys = [ya + (yb_ - ya) * k / nseg for k in range(nseg + 1)]
        lift = 0.012 if name == 'canopy_hood' else 0.0          # the hood rides over the windscreen / rear glazing
        rings = [[p + V((0, 0, 0)) + (V((p.x, 0, p.z - 0.4)).normalized() * lift if lift else V()) for p in canopy_section(y)] for y in ys]
        mb = MeshBuf()
        loft(mb, rings, 'glass', closed=False, outward=True)
        loft(mb, rings, 'glass', closed=False, outward=False)
        # frames: ends + the design frame stations inside this piece + base rails + hood spine
        fys = [y for y in (f * K for f in S.CANOPY_FRAMES_Y) if min(ya, yb_) - 1e-6 <= y <= max(ya, yb_) + 1e-6] + [ya, yb_]
        for fy in sorted(set(round(f, 5) for f in fys)):
            arc = [p + (V((p.x, 0, p.z - 0.4)).normalized() * lift if lift else V()) for p in canopy_section(fy)]
            # r4c: the windscreen's base frame lies on the deck skin; at the flat 6 mm height its top face sat within 0.6 mm of the
            # deck (z-fight check) -> keep the r4 12 mm there
            frame_arc(mb, arc, V((0, 1, 0)), 0.012 if (name == 'canopy_windscreen' and abs(fy - ya) < 1e-4) else None)
        for side in (0, -1):
            rail = [r[side] for r in rings]
            frame_line(mb, rail, V((0, 0, 1)))
        if name == 'canopy_hood' and S.HOOD_SPINE:
            spine = [r[len(r) // 2] for r in rings]
            frame_line(mb, spine, V((0, 0, 1)))
        if name == 'canopy_windscreen':                         # front flat panel edges (windscreen quarter frames)
            for k in (5, 11):
                frame_line(mb, [r[k] for r in rings], V((0, 0, 1)))
        piv = (0, (ya + yb_) / 2, 0.85)
        parts.append(Part(name, 'fus_center', piv, mb, info=dict(kind='glass' if name != 'canopy_hood' else 'canopy',
                                                               slide_m=S.CANOPY_SLIDE * K if name == 'canopy_hood' else 0.0)))
    return parts


def frame_arc(mb, arc, along, h_out=None):
    """flat frame bar following an arc: outside strip FRAME_H proud of the glass (paint), inside strip FRAME_IN below it (r4c: flat, narrow,
    the inner face and inner sides in cockpit green 'interior', as the reference's painted frames seen from the seat)."""
    w, h, hi = S.FRAME_W, (S.FRAME_H if h_out is None else h_out), S.FRAME_IN
    for a, b in zip(arc, arc[1:]):
        t = (b - a).normalized()
        nrm = V((a.x + b.x, 0, (a.z + b.z) / 2 - 0.40)).normalized()
        side = t.cross(nrm).normalized() * (w / 2)
        if side.dot(along) < 0:
            side = -side
        _frame_seg(mb, a, b, side, nrm, h, hi)


def _frame_seg(mb, a, b, side, nrm, h, hi):
    q_out = [a - side + nrm * h, b - side + nrm * h, b + side + nrm * h, a + side + nrm * h]
    oriented_quad(mb, q_out, 'paint', nrm)
    for s_ in (-1, 1):
        q = [a + side * s_, b + side * s_, b + side * s_ + nrm * h, a + side * s_ + nrm * h]
        oriented_quad(mb, q, 'paint', side * s_)
    q_in = [a - side - nrm * hi, b - side - nrm * hi, b + side - nrm * hi, a + side - nrm * hi]
    oriented_quad(mb, q_in, 'interior', -nrm)
    for s_ in (-1, 1):
        q = [a + side * s_, b + side * s_, b + side * s_ - nrm * hi, a + side * s_ - nrm * hi]
        oriented_quad(mb, q, 'interior', side * s_)


def frame_line(mb, pts, up):
    for a, b in zip(pts, pts[1:]):
        t = (b - a).normalized()
        nrm = V((a.x + b.x, 0, (a.z + b.z) - 0.8)).normalized()
        side = t.cross(nrm).normalized() * (S.FRAME_W / 2)
        _frame_seg(mb, a, b, side, nrm, S.FRAME_H, S.FRAME_IN)


# =============================================================================================== wing
def wing_station(xb, side, t_override=None):
    """Station at built span |x| = xb (side +1 right, -1 left); chord line from the table (pre) scaled, plug z added."""
    xp = S.span_pre(xb)
    le_y = S.lin(S.WING, xp, 1) * K
    te_y = S.lin(S.WING, xp, 2) * K
    zle = S.lin(S.WING, xp, 3) * K + S.plug_z(xb)
    zte = S.lin(S.WING, xp, 4) * K + S.plug_z(xb)
    tc = S.lin(S.WING, xp, 5) if t_override is None else t_override
    le = V((side * xb, le_y, zle))
    te = V((side * xb, te_y, zte))
    c = (te - le).length
    cdir = (te - le).normalized()
    sd = V((side, 0, S.TAN_DIH)).normalized()
    up = cdir.cross(sd) if side > 0 else sd.cross(cdir)
    if up.z < 0:
        up = -up
    return Station(xb, le, cdir, up, max(c, 0.002), tc, m=S.WING_CAMBER)


def s_mixed(n):
    """chord fractions 0..1 (n+1 values): 35 % cosine (LE / TE clustering) + 65 % uniform (resolution for the well cut-outs)."""
    return [0.5 * (1 - math.cos(math.pi * k / n)) * 0.35 + (k / n) * 0.65 for k in range(n + 1)]


def flap_s(xb):
    xp = S.span_pre(xb)
    if not (S.FLAP_X[0] <= xp <= S.FLAP_X[1]):
        return None
    st = wing_station(xb, 1)
    return 1.0 - S.lin(S.FLAP_CHORD, xp) * K / st.chord


def ail_s(xb):
    xp = S.span_pre(xb)
    if not (S.AIL_X[0] <= xp <= S.AIL_X[1]):
        return None
    st = wing_station(xb, 1)
    return 1.0 - S.lin(S.AIL_CHORD, xp) * K / st.chord


GAP = 0.010         # hinge gap (m) between the fixed wing and the control surface nose
AIL_FIXED_SPLIT = True   # r8f: constant number of chord samples aft of the aileron hinge (no slots in the loft)
AIL_LIP = True      # r8e: upper-skin lip over the aileron slit (wing_ring 'ail')
AIL_GAP = 0.003     # r8c (game r8b z_L6_top: the 10 mm aileron gap read as a dark crack across the upper wing): 3 mm


def wing_ring(st, xb, mode, ns=22):
    """closed ring: upper TE..LE then lower LE..TE (2 ns + 1 points).
    mode 'full' | 'flap' (lower aft replaced by the cove ceiling line) | 'ail' (aft of the hinge collapsed onto the hinge wall)."""
    ss = s_mixed(ns)
    if mode == 'ail' and AIL_FIXED_SPLIT:
        # r8f (game r8e z_wing_slits / z_ail_dn: dark triangular slots along the aileron hinge line, light slivers in the gap with the
        # aileron down): the number of chord samples aft of the hinge changed from station to station (sh moves along the span), so the
        # loft joined the r8e lip of one station to a surface point of the next - a triangular slot every time the count changed. The
        # chord samples are warped so the same index always falls just aft of the hinge (constant topology along the aileron).
        sh_ = ail_s(xb) - AIL_GAP / st.chord
        i0 = next(i for i, v in enumerate(ss) if v >= 0.70)
        s0 = ss[i0] - 1e-6
        ss = [v * sh_ / s0 if v <= s0 else sh_ + (v - s0) * (1.0 - sh_) / (1.0 - s0) for v in ss]
    up = [st.point(s, True) for s in reversed(ss)]
    lo = [st.point(s, False) for s in ss[1:]]
    if mode == 'flap':
        sf = flap_s(xb)
        p_f = st.point(sf, False)
        p_te = st.point(1.0, True) - st.up * 0.0005           # r1 z-fight: the cove ceiling runs to the UPPER trailing edge, always above the flap
        lo = [st.point(s, False) if s <= sf else p_f + (p_te - p_f) * ((s - sf) / (1 - sf)) + st.up * (0.006 * (1 - (s - sf) / (1 - sf)) + 0.004 * math.sin(math.pi * (s - sf) / (1 - sf)))
              for s in ss[1:]]
    elif mode == 'ail':
        sh = ail_s(xb) - AIL_GAP / st.chord
        hu, hl = st.point(sh, True), st.point(sh, False)
        nb = sum(1 for s in ss if s > sh)
        for k in range(nb):                                   # upper points aft of the hinge: down the hinge wall from hu to mid
            up[k] = hu + (hl - hu) * (0.49 * (nb - k) / nb)
        if AIL_LIP and nb >= 4:
            # r8e (game r8d L6_topR: a black hairline across the upper wing on Matte Black): from above, the 3 mm slit between the wing's
            # upper edge and the aileron nose was a dark crevice. The upper skin now overhangs the slit as a thin lip (the real Zero's
            # shroud): tip AIL_GAP + 1.5 mm aft of the hinge wall, 1.2 mm over the surface line, underside 0.4 mm over it - it clears the
            # aileron's top skin and hides the slit from above.
            cd_ = st.cdir.normalized(); upn = st.up.normalized()
            tip = hu + cd_ * (AIL_GAP + 0.0015)
            up[nb - 1] = tip + upn * 0.0012
            up[nb - 2] = tip + upn * 0.0004
            up[nb - 3] = hu + upn * 0.0004
            for k in range(nb - 3):
                up[k] = hu + (hl - hu) * (0.49 * (nb - 3 - k) / (nb - 3))
        for m in range(nb):                                   # lower points aft of the hinge: up the wall from hl to mid
            lo[len(lo) - nb + m] = hl + (hu - hl) * (0.49 * (m + 1) / nb)
    ring = up + lo
    if abs(xb) < 1e-6:                                         # r1 check: the two halves of the centre section meet in the plane x = 0
        ring = [V((0.0, q.y, q.z)) for q in ring]
    return ring


def wing_mode(xb):
    if ail_s(xb) is not None:
        return 'ail'
    if flap_s(xb) is not None:
        return 'flap'
    return 'full'


# --- wheel wells (D-shaped: straight inner-door hinge edge near the centreline, round outboard)
def well_centre(side):
    c = P((side * S.MAIN_WHEEL_UP[0], S.MAIN_WHEEL_UP[1], S.MAIN_WHEEL_UP[2]), plug=False)
    return V((c.x, c.y, 0))


SLOT_W = 0.100     # r1 gear sweep: the leg swings about a tilted axis and needs 0.20 m


def slot_axis(side):
    a = V((side * S.MAIN_PIVOT[0] * K, S.MAIN_PIVOT[1] * K, 0))
    return a, well_centre(side)


WELL_CLIP_HINGE = True
WELL_CLIP_IN = 0.001    # m: the opening's straight inboard edge sits this far under the closed inner door's hinge edge (no gap on the hinge line)


def opening_outline(side, R=None, half=None, n=48, w=None):
    """plan polygon of the opening (round well + the leg slot from the pivot). half='out' keeps only the outboard half circle
    (x*side >= centre) closed along the diameter line: the leg cover in the retracted pose."""
    a, c = slot_axis(side)
    R = S.WELL_R * K if R is None else R
    SW = SLOT_W if w is None else w
    e = (a - c).normalized()
    pe = V((-e.y, e.x, 0))
    te = math.atan2(e.y, e.x)
    dl = math.asin(min(SW / R, 0.99))
    if half == 'out':                                  # r1 overlay: the cover takes the well from the inner door's edge (x_split) outboard
        xs_ = door_split_x(side)
        h_ = math.acos(max(-1.0, min(1.0, (xs_ - c.x) * side / R)))
        a0, span = (-h_, 2 * h_) if side > 0 else (math.pi - h_, 2 * h_)
    else:
        a0, span = te + dl, 2 * math.pi - 2 * dl
    pts = []
    for k in range(n + 1):
        ang = a0 + span * k / n
        d = (ang - te + math.pi) % (2 * math.pi) - math.pi
        if abs(d) < dl - 1e-9:
            continue
        pts.append((ang, c + V((math.cos(ang), math.sin(ang), 0)) * R))
    slot = [c + V((math.cos(te - dl), math.sin(te - dl), 0)) * R, a - pe * SW, a + pe * SW, c + V((math.cos(te + dl), math.sin(te + dl), 0)) * R]
    if half != 'out':
        # starts just after the slot (+pe side), ends just before it (-pe side): close through the slot
        full = [p for _, p in pts] + [slot[0], slot[1], slot[2]]
        if WELL_CLIP_HINGE:
            # r8k (in game r8j, gear up: a light-blue crescent + dark sliver at the inboard edge of each closed well): the round opening
            # reached 27 mm inboard of the inner door's hinge line (circle to x 0.067, door from x 0.094), so a 0.27 m crescent of the
            # well stayed open with the gear up. The opening now stops on the hinge line, straight, like the reference (inboard edge of
            # each well on the belly keel; WT gear up: fully closed).
            xc_ = S.INNER_DOOR_HINGE_X * K + 0.004 - WELL_CLIP_IN      # inner_door's hinge edge (xh) less 1 mm
            full = [V((side * max(side * p.x, xc_), p.y, p.z)) for p in full]
            full = [p for i, p in enumerate(full) if i == 0 or (p - full[i - 1]).length > 1e-6]
        return full
    # arc on the outboard side of the split line: insert the slot where the angle passes te
    out = []
    ins = False
    for i, (ang, p) in enumerate(pts):
        d = (ang - te + math.pi) % (2 * math.pi) - math.pi
        if not ins and d > 0:
            out += slot
            ins = True
        out.append(p)
    if S.SPLIT_BOW > 0:                                # r6: curved split line (the door bulges outboard into the cover)
        cur = split_curve(side, c, R)
        if (cur[0] - out[-1]).length > (cur[-1] - out[-1]).length:
            cur = list(reversed(cur))
        out += cur[1:-1]
    return out


def split_curve(side, c, R, n=16):
    """r6: the inner door / leg cover split line as a bow (x bulges outboard by SPLIT_BOW at the well centre), ends on the well circle."""
    xs_ = door_split_x(side)
    hs = math.sqrt(max(R * R - (xs_ - c.x) ** 2, 0.0))
    pts = []
    for k in range(n + 1):
        t = -1.0 + 2.0 * k / n
        pts.append(V((xs_ + side * S.SPLIT_BOW * K * (1.0 - t * t), c.y + hs * t, 0)))
    return pts


def door_split_x(side):
    """built x of the line between the inner well door and the leg cover."""
    return side * (S.INNER_DOOR_HINGE_X + S.INNER_DOOR_W) * K


def _pip(poly, x, y):
    ins = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i].x, poly[i].y
        x2, y2 = poly[(i + 1) % n].x, poly[(i + 1) % n].y
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                ins = not ins
    return ins


_OPEN = {}


def in_opening(p):
    for side in (1, -1):
        if side not in _OPEN:
            _OPEN[side] = opening_outline(side)
        if _pip(_OPEN[side], p.x, p.y):
            return side
    return 0


RIM_LE = 0.020      # r8d: the rim band stops this far behind the wing LE
RIM_W = 0.050       # flush trim band round the opening (hides the cell-stepped cut of the skin)


def wing_xs(x0, x1, step, extra=()):
    bounds = []
    for xp in (S.FLAP_X[0], S.FLAP_X[1], S.AIL_X[0], S.AIL_X[1]):
        xb = S.span_built(xp)
        if x0 < xb < x1:
            bounds.append(xb)
    req = sorted({round(x0, 6), round(x1, 6)} | {round(b, 6) for b in bounds} | {round(e, 6) for e in extra if x0 < e < x1})
    xs = [req[0]]
    for a, b in zip(req, req[1:]):
        n = max(1, int(math.ceil((b - a) / step - 1e-9)))
        for k in range(1, n + 1):
            xs.append(a + (b - a) * k / n)
    return xs, bounds


WING_CAP_MAT = 'metal_dark'   # r8g (game r8f z_wing_hingeL: a light dotted hairline across the left hinomaru = the light-grey 'structure'
                              # break caps seen through the hairline seam at the wing-fold / part breaks): dark seam backing, as FD-32 / Mk I 1.9.13


def loft_wing(mb, side, x0, x1, cap0, cap1, step=0.12, extra=(), cut=False, ns=22, mat_cap=None):
    """one wing piece over built |x| x0..x1. Duplicated stations at the flap / aileron ends make the cut-out walls.
    cut=True: lower-skin faces with ANY corner inside a well opening are dropped (the cut lies outside the outline, under the rim)."""
    mat_cap = mat_cap or WING_CAP_MAT
    xs, bounds = wing_xs(x0, x1, step, extra)
    rings = []
    eps = 2e-4                 # r8e: 0.2 mm (1e-5 welded the two rings of a flap-end wall into non-manifold edges)
    for x in xs:
        st = wing_station(x, side)
        if any(abs(x - b) < 1e-6 for b in bounds):
            m_in, m_out = wing_mode(x - eps), wing_mode(x + eps)
            rings.append(wing_ring(st, x - eps, m_in, ns))
            rings.append(wing_ring(st, x + eps, m_out, ns))
        else:
            rings.append(wing_ring(st, x, wing_mode(x), ns))
    nlo = len(rings[0])
    half = nlo // 2

    def keep(i, j):
        if not cut or j < half:
            return True
        qs = (rings[i][j], rings[i][(j + 1) % nlo], rings[i + 1][j], rings[i + 1][(j + 1) % nlo])
        if all(q.y > le_cut_y(q.x) for q in qs):
            return True                    # r8d: the LE nose is never cut (the well's front edge lies 37 mm behind the LE)
        return not any(in_opening(q) for q in qs)
    from b25h_geom import ring_arc_uv
    loft(mb, rings, 'paint', closed=True, outward=True, uvfunc=ring_arc_uv(rings, [r[0].x for r in rings]), keep=keep)     # round 5: SIGNED span (|x| folded wing_C's two halves into one island)
    for ring, x, cap in ((rings[0], x0, cap0), (rings[-1], x1, cap1)):
        tw = 1 if x == x1 else -1
        if cap and OPEN_BREAKS:
            # r8o: open break end (no cap in the plane). cap = ('post', name): the part goes through build_a6m2.unify_root's booleans
            # (wing_C union, well cutters), which need a closed solid: a temporary fan cap (WING_CAP_MAT) is built here and removed after
            # the booleans (build_a6m2.open_root_breaks); the open end goes to POST_ADD[name] and is added after them
            if isinstance(cap, tuple) and cap[0] == 'post':
                c = sum(ring, V()) / len(ring)
                fan_cap(mb, ring, c, mat_cap, V((side * tw, 0, 0)))
                wing_open_end(post_mb(cap[1]), side, x, tw, ns, notch=True)
            else:
                wing_open_end(mb, side, x, tw, ns, notch=abs(x - S.span_built(S.WING_BREAKS[0])) < 1e-6)
        elif cap and cut and abs(x - S.span_built(S.WING_BREAKS[0])) < 1e-6:
            notched_rib(mb, ring, side, x, V((side * tw, 0, 0)), mat_cap)
        elif cap:
            c = sum(ring, V()) / len(ring)
            fan_cap(mb, ring, c, mat_cap, V((side * tw, 0, 0)))
    return rings


def notched_rib(mb, ring, side, xb, toward, mat):
    """break rib with a notch where the wheel well crosses the break (r1 gear sweep: the stowed wheel passes x = break). Built as
    vertical strips between the upper and lower skin (no polygon triangulation); inside the notch the strip ends at the well ceiling."""
    c = well_centre(side)
    R = S.WELL_R * K
    dx = abs(xb - abs(c.x))
    st = wing_station(xb, side)
    if dx >= R:
        cc = sum(ring, V()) / len(ring)
        fan_cap(mb, ring, cc, mat, toward)
        return
    h = math.sqrt(R * R - dx * dx)
    y0, y1 = c.y - h - 0.004, c.y + h + 0.004
    s_of = lambda y: (st.le.y - y) / st.chord
    ss = sorted(set([round(s, 6) for s in s_mixed(60)] + [round(s_of(y0), 6), round(s_of(y1), 6)]))
    cz = lambda y: min(upper_z(xb, y), upper_z(c.x, c.y)) - WELL_CEIL - 0.012 - 0.002
    cols = []
    for s in ss:
        if not (0.0 <= s <= 1.0):
            continue
        u = st.point(s, True)
        l = st.point(s, False)
        yy = u.y
        if abs(s - s_of(y0)) < 1e-6 or abs(s - s_of(y1)) < 1e-6:
            cols.append((u, l))
            cols.append((u, V((l.x, l.y, cz(l.y)))))
            if (abs(s - s_of(y1)) < 1e-6):                 # entering the notch (LE side): lower first, then the ceiling
                pass
            else:                                          # leaving it: ceiling first, then the lower skin
                cols[-2], cols[-1] = cols[-1], cols[-2]
        elif y0 < yy < y1:
            cols.append((u, V((l.x, l.y, cz(l.y)))))
        else:
            cols.append((u, l))
    for (u0, l0), (u1, l1) in zip(cols, cols[1:]):
        q = [u0, u1, l1, l0]
        if (u1 - u0).length < 1e-7 and (l1 - l0).length < 1e-7:
            continue
        nrm = (q[1] - q[0]).cross(q[3] - q[0])
        if nrm.length < 1e-12:
            nrm = (q[2] - q[1]).cross(q[0] - q[1])
        if nrm.length < 1e-12:
            continue
        oriented_quad(mb, q, mat, toward)


# =============================================================================================== r8o open break ends (wings, tail roots)
POST_ADD = {}       # r8o: object name -> MeshBuf added after build_a6m2.unify_root (open ends of the parts that go through the booleans)


def wing_break_plane(side, xb):
    """r8o: the plane of the wing section at built |x| xb (it leans with the dihedral: +-20 mm in x over the root thickness) as
    (point, unit normal pointing outboard)."""
    st = wing_station(xb, side)
    n = st.cdir.cross(st.up).normalized()
    if n.x * side < 0:
        n = -n
    return V(st.le), n


def wing_plane_abs_x(side, xb, y, z):
    """r8o: |x| of the break plane at (y, z)."""
    p0, n = wing_break_plane(side, xb)
    return abs(p0.x - ((y - p0.y) * n.y + (z - p0.z) * n.z) / n.x)


def post_mb(name):
    if name not in POST_ADD:
        POST_ADD[name] = MeshBuf()
    return POST_ADD[name]


def _plane_basis(axis):
    a = V(axis).normalized()
    ref = V((0, 0, 1)) if abs(a.z) < 0.9 else V((1, 0, 0))
    u = (ref - a * ref.dot(a)).normalized()
    return a, u, a.cross(u)


def _ray_depth2(P2, j, o, d):
    """distance along the 2D ray o + t d to the polygon P2 (closed), edges touching vertex j excluded."""
    n = len(P2)
    best = 9.0
    for k in range(n):
        k1 = (k + 1) % n
        if k == j or k1 == j:
            continue
        a, b = P2[k], P2[k1]
        ex, ey = b[0] - a[0], b[1] - a[1]
        den = d[0] * ey - d[1] * ex
        if abs(den) < 1e-12:
            continue
        wx, wy = a[0] - o[0], a[1] - o[1]
        t = (wx * ey - wy * ex) / den
        s = (wx * d[1] - wy * d[0]) / den
        if t > 1e-6 and -1e-9 <= s <= 1 + 1e-9:
            best = min(best, t)
    return best


def inward_ring(ring, axis, d=0.003, frac=0.4):
    """r8o: a closed section ring (points in one plane normal to axis) offset INTO the section by d (at most frac x the local depth along
    the offset direction, so the thin trailing edge / hinge walls do not cross over). Liner rings of the open break ends."""
    a, u, w = _plane_basis(axis)
    n = len(ring)
    P2 = [(p.dot(u), p.dot(w)) for p in ring]
    area = sum(P2[j][0] * P2[(j + 1) % n][1] - P2[(j + 1) % n][0] * P2[j][1] for j in range(n))
    sg = 1.0 if area > 0 else -1.0
    out = []
    for j in range(n):
        tx, ty = P2[(j + 1) % n][0] - P2[j - 1][0], P2[(j + 1) % n][1] - P2[j - 1][1]
        L = math.hypot(tx, ty)
        if L < 1e-9:
            out.append(V(ring[j]))
            continue
        nx, ny = -ty / L * sg, tx / L * sg                       # left of the travel direction = inside for a CCW ring
        dep = _ray_depth2(P2, j, P2[j], (nx, ny))
        dd = min(d, frac * dep)
        out.append(V(ring[j]) + (u * nx + w * ny) * dd)
    return out


def section_pairs(n, ns=None):
    """(upper index, lower index) from the LE to the TE for a wing / stab ring (up TE..LE + lo LE..TE, 2 ns + 1 points) or a fin ring
    (one side front..aft, the mirror aft..front: 2 (n_side - 1) points)."""
    if ns is not None:
        return [(ns, ns)] + [(ns - m, ns + m) for m in range(1, ns + 1)]
    half = n // 2
    return [(0, 0)] + [(k, n - k) for k in range(1, half)] + [(half, half)]


def rib_strips(mb, ring, pairs, toward, mat='structure', floor=None, skip=(), cdir=None):
    """r8o: a rib web as strips between paired upper / lower section points (no polygon triangulation: any section shape); floor(p) -> z
    raises a lower point (the notch over the wheel-well / leg-slot cutter); strips whose index is in skip are left out (stiffeners)."""
    def lo(p):
        if floor is None:
            return p
        zf = floor(p)
        return p if zf is None or zf <= p.z else V((p.x, p.y, zf))
    for m_, ((a0, b0), (a1, b1)) in enumerate(zip(pairs, pairs[1:])):
        if m_ in skip:
            continue
        U0, U1 = ring[a0], ring[a1]
        L0, L1 = lo(ring[b0]), lo(ring[b1])
        if cdir is not None and ((U1 - U0).dot(cdir) < 1e-5 or (L1 - L0).dot(cdir) < 1e-5):
            continue                                            # no chord progress: the collapsed hinge wall / lip (strips would fold)
        if floor is not None and ((L0 - ring[b0]).length > 1e-9 or (L1 - ring[b1]).length > 1e-9) and (L0.z >= U0.z - 0.004 or L1.z >= U1.z - 0.004):
            continue                                            # the notch floor reaches the upper surface: no web there
        if (U0 - L0).length < 1e-7:
            q = [U0, U1, L1]
        elif (U1 - L1).length < 1e-7:
            q = [U0, U1, L0]
        else:
            q = [U0, U1, L1, L0]
        nrm = (q[1] - q[0]).cross(q[-1] - q[0])
        if nrm.length < 1e-12:
            continue
        oriented_quad(mb, q, mat, toward)


def _opening_floor(p, margin=0.012):
    """r8o: z the rib notch stands on where (p.x, p.y) is in / within margin of a wheel-well opening (cutter top + 4 mm), else None."""
    hit = False
    for dx, dy in ((0, 0), (margin, 0), (-margin, 0), (0, margin), (0, -margin)):
        if in_opening(V((p.x + dx, p.y + dy, 0))):
            hit = True
            break
    if not hit:
        return None
    side = 1 if p.x > 0 else -1
    a, c = slot_axis(side)
    R = S.WELL_R * K
    zceil0 = upper_z(c.x, c.y) - WELL_CEIL - 0.012
    zs = [lower_z(p.x, p.y) + 0.075]
    if (V((p.x, p.y, 0)) - V((c.x, c.y, 0))).length <= R + 0.002 + margin:
        zs.append(min(zceil0, upper_z(p.x, p.y) - WELL_CEIL - 0.012))
    return max(zs) + 0.004


def _near_opening(p, margin=0.02):
    for dx, dy in ((0, 0), (margin, 0), (-margin, 0), (0, margin), (0, -margin)):
        if in_opening(V((p.x + dx, p.y + dy, 0))):
            return True
    return False


CAP_STRIP = 0.025          # r8o round 2: break-rib cap strip (flange) depth inward from the liner, at most CAP_STRIP_FRAC x the local depth
CAP_STRIP_FRAC = 0.12      # (each side: <= 24 % of the section height in one plane; review: the r8o two-web rib covered the whole section)
CLOSE_MAT = 'interior'     # r8o round 2: the deep bay-end wall that closes a lined break cavity (painted aotake like the liner, not the
                           # aircraft_structure look; stock: frames / ribs 0.4 m or more inside the break)


def _bounds_d(ring_at, close):
    """r8o round 2: depths (0..close) where the ring's section mode changes (flap / aileron ends): a pair of stations 0.2 mm either side."""
    out = []
    bd = getattr(ring_at, 'bounds', None)
    if bd:
        for d in bd(close):
            if 0.004 < d < close - 0.004:
                out += [round(d - 2e-4, 6), round(d + 2e-4, 6)]
    return out


def open_end(mb, ring_at, axis_out, pairs, depth=None, band=None, seed='', stubs=(), spar_stub=None, notch=False,
             liner_d=0.003, stiff=(), close=None, step=0.035, close_back=True):
    """r8o: the open end of a part at a break plane (no cap): ring_at(d) = the skin section d inside the plane; axis_out = unit vector out
    of the part through the plane. Builds the dark skin edge (annulus skin -> liner, 'metal_dark'), the liner (offset liner_d inward, the
    first `band` 'metal_dark', the rest 'interior'), stringer stubs (L 12 x 25 mm, rib -> U(STUB_SHORT) short of the plane) at the given
    (s, upper) and an optional spar stub.
    r8o round 2 (review of r8o: the rib at `depth` was a two-web plate over the WHOLE section in the aircraft_structure look = the
    'metal texture dividing the parts' again): the rib at `depth` is a perimeter CAP STRIP only (flange CAP_STRIP deep, at most
    CAP_STRIP_FRAC of the local depth, two faces 4 mm apart + inner edge, 'metal_dark'), the centre of the section open. The liner runs
    on to `close` (default 0.40 m) where a bay-end wall (CLOSE_MAT, two faces) closes the lined cavity (stock: the first full rib 0.4 m or
    more inside the break); spars / tanks / stubs inside the cavity are seen through the open cap strip. (stiff: unused since round 2.)"""
    import a6m2_internals as AI
    depth = AI.END_FRAME_SETBACK if depth is None else depth
    band = SEAM_BAND if band is None else band
    close = max(depth + 0.10, 0.40) if close is None else close
    r = AI.rng('open_end', seed)
    ax = V(axis_out).normalized()
    special = [0.0, band, depth - 0.002, depth, depth + 0.002, close - 0.002, close, close + 0.002]
    special = [round(d, 6) for d in special] + _bounds_d(ring_at, close)
    grid = []
    k = 1
    while k * step < close - 0.004:
        grid.append(round(k * step, 6))
        k += 1
    grid = [g for g in grid if all(abs(g - d) >= 0.004 for d in special)]
    ds = sorted(set(special + grid))
    skin = {d: ring_at(d) for d in ds}
    lin = {d: inward_ring(rr, ax, liner_d) for d, rr in skin.items()}
    n = len(skin[0.0])
    lower = set(b for _, b in pairs[1:])

    def near_open(q):
        return _near_opening(q, 0.006)

    def keep_rows(ra_, rb_):
        def kp(i, j):
            if not notch:
                return True
            j1 = (j + 1) % n
            if j not in lower and j1 not in lower:
                return True
            return not any(near_open(q) for q in (ra_[j], ra_[j1], rb_[j], rb_[j1]))
        return kp
    for da, db in zip(ds, ds[1:]):
        if db > close + 1e-9:
            break
        if len(lin[da]) != len(lin[db]):
            continue
        mat_l = 'metal_dark' if db <= band + 1e-9 else 'interior'
        loft(mb, [lin[da], lin[db]], mat_l, closed=True, outward=False, keep=keep_rows(lin[da], lin[db]))
    for j in range(n):                                          # skin edge (dark seam backing)
        j1 = (j + 1) % n
        if notch and (j in lower or j1 in lower) and any(near_open(q) for q in (skin[0.0][j], skin[0.0][j1])):
            continue
        q = [skin[0.0][j], skin[0.0][j1], lin[0.0][j1], lin[0.0][j]]
        if (q[0] - q[3]).length < 1e-6 and (q[1] - q[2]).length < 1e-6:
            continue
        nrm = (q[1] - q[0]).cross(q[3] - q[0])
        if nrm.length < 1e-12:
            nrm = (q[2] - q[1]).cross(q[0] - q[1])
        if nrm.length < 1e-12:
            continue
        oriented_quad(mb, q, 'metal_dark', ax)
    fl = _opening_floor if notch else None
    # cap-strip ring (flange) at depth: two faces 4 mm apart + the inner edge, the centre of the section open
    ra0, ra1 = lin[round(depth - 0.002, 6)], lin[round(depth + 0.002, 6)]
    cd_dep = ring_at.station(depth).cdir.normalized()
    ia0 = inward_ring(ra0, ax, CAP_STRIP, frac=CAP_STRIP_FRAC)
    ia1 = inward_ring(ra1, ax, CAP_STRIP, frac=CAP_STRIP_FRAC)
    for j in range(n):
        j1 = (j + 1) % n
        if notch and (j in lower or j1 in lower) and any(near_open(q) for q in (ra0[j], ra0[j1], ia0[j], ia0[j1])):
            continue
        if fl is not None and (j in lower or j1 in lower) and (fl(ra0[j]) is not None or fl(ra0[j1]) is not None):
            continue
        if (ia0[j] - ra0[j]).length < 0.0015 and (ia0[j1] - ra0[j1]).length < 0.0015:
            continue
        qa_ = [ra0[j], ra0[j1], ia0[j1], ia0[j]]
        qn_ = (qa_[2] - qa_[0]).cross(qa_[3] - qa_[1])
        if 0.5 * qn_.length < 3e-5 or abs(qn_.normalized().dot(ax)) < 0.87 or                 any(abs(((qa_[(i + 1) % 4] - qa_[i]).cross(qa_[(i + 3) % 4] - qa_[i])).normalized().dot(ax)) < 0.87
                    for i in range(4) if ((qa_[(i + 1) % 4] - qa_[i]).cross(qa_[(i + 3) % 4] - qa_[i])).length > 1e-12):
            continue                                            # slivers / twisted quads (collapsed aileron hinge wall, LE / TE): no flange
        for q, tw in (([ra0[j], ra0[j1], ia0[j1], ia0[j]], ax), ([ra1[j], ra1[j1], ia1[j1], ia1[j]], -ax)):
            nrm = (q[1] - q[0]).cross(q[3] - q[0])
            if nrm.length < 1e-12:
                nrm = (q[2] - q[1]).cross(q[0] - q[1])
            if nrm.length < 1e-12:
                continue
            oriented_quad(mb, q, 'metal_dark', tw)
        e_ = [ia0[j], ia0[j1], ia1[j1], ia1[j]]
        inw = ((ia0[j] - ra0[j]) + (ia0[j1] - ra0[j1]))
        if inw.length > 1e-6 and (e_[1] - e_[0]).length > 0.005 and abs(inw.normalized().dot(cd_dep)) < 0.7:
            # (no edge strip along a wall across the chord: the collapsed aileron hinge wall / TE, where the strip would stand edge-on)
            oriented_quad(mb, e_, 'metal_dark', inw)
    # the bay-end wall at `close` (two faces 4 mm apart; notched over a wheel-well / leg-slot opening)
    cdv_ = ring_at.station(close).cdir.normalized()
    rib_strips(mb, lin[round(close - 0.002, 6)], pairs, ax, CLOSE_MAT, fl, cdir=cdv_)
    if close_back:                                              # (wing_tip: the far side faces the painted fold rib 13 mm away - a closed pocket)
        rib_strips(mb, lin[round(close + 0.002, 6)], pairs, -ax, CLOSE_MAT, fl, cdir=cdv_)
    for s_, upper in stubs:                                     # stringer stubs on the liner
        stA = ring_at.station(depth)
        stB_d = r.uniform(*AI.STUB_SHORT)
        stB = ring_at.station(stB_d)
        pA, pB = stA.point(s_, upper), stB.point(s_, upper)
        oA, oB = stA.point(s_, not upper), stB.point(s_, not upper)
        dA, dB = (oA - pA).normalized(), (oB - pB).normalized()
        b0, b1 = pA + dA * (liner_d + 0.0015), pB + dB * (liner_d + 0.0015)
        if notch and (_near_opening(b0, 0.03) or _near_opening(b1, 0.03)):
            continue
        AI.l_stub(mb, b0, b1, dA, h=min(0.025, 0.35 * (oA - pA).length), sec_axis=ax)
    if spar_stub is not None:                                   # spar web stub (two-sided 4 mm plate) from the rib toward the plane
        s_ = spar_stub
        stA = ring_at.station(depth)
        stB = ring_at.station(r.uniform(*AI.STUB_SHORT))
        q = []
        for st_ in (stA, stB):
            u_, l_ = st_.point(s_, True), st_.point(s_, False)
            dd = (l_ - u_).normalized()
            q.append((u_ + dd * (liner_d + 0.001), l_ - dd * (liner_d + 0.001)))
        cd = stA.cdir.normalized()
        for sg in (1, -1):
            o_ = cd * (0.002 * sg)
            oriented_quad(mb, [q[0][0] + o_, q[1][0] + o_, q[1][1] + o_, q[0][1] + o_], 'structure', cd * sg)
        for k in (0, 1):
            oriented_quad(mb, [q[0][k] + cd * 0.002, q[1][k] + cd * 0.002, q[1][k] - cd * 0.002, q[0][k] - cd * 0.002], 'structure',
                          (q[0][k] - q[0][1 - k]))
        for qq, d_ in ((q[0], -ax), (q[1], ax)):
            oriented_quad(mb, [qq[0] + cd * 0.002, qq[1] + cd * 0.002, qq[1] - cd * 0.002, qq[0] - cd * 0.002], 'structure', d_)


def _floor_hit(p):
    return _opening_floor(p) is not None


class _RingAt:
    """ring_at(d) callable with .station(d) (the Station at d inside the plane) for open_end; optional .bounds(close) -> the depths where
    the section mode changes (r8o round 2: the lined cavity runs across the flap / aileron ends)."""
    def __init__(self, ring_fn, station_fn, bounds_fn=None):
        self.ring_fn, self.station_fn = ring_fn, station_fn
        if bounds_fn is not None:
            self.bounds = bounds_fn

    def __call__(self, d):
        return self.ring_fn(d)

    def station(self, d):
        return self.station_fn(d)


def wing_cavity(x_end, toward):
    """r8o round 2: depth of the lined break cavity (cap strip at END_FRAME_SETBACK, bay-end wall at this depth) of a wing break end at
    built |x| x_end; toward +1 = the part's outboard end. Root on fus_center (wing_C): the wall at |x| 0.535, outboard of the fuselage side
    (the well drum crosses the cavity: its back is dark, build_a6m2.open_root_breaks); wing_inner root: 0.85 m (the tank cell inside);
    wing_tip root: up to 13 mm before the painted fold rib; else 0.40 m."""
    br = [S.span_built(b) for b in S.WING_BREAKS]
    if abs(x_end - br[0]) < 1e-6:
        return br[0] - 0.535 if toward > 0 else 0.85
    if abs(x_end - br[2]) < 1e-6 and toward < 0:
        return br[3] - br[2] - 0.013
    return 0.40


def wing_open_end(mb, side, x_end, toward, ns, notch=False, seed=''):
    """r8o: open wing break end at built |x| x_end; toward +1 when the break is the part's outboard end (the mating part lies outboard).
    Replaces the r1-r8n fan cap / notched_rib in the break plane (user test r8n: solid metal discs at every wing break).
    r8o round 2: perimeter cap strip at 0.10 m (no web), liner on to the bay-end wall at wing_cavity()."""
    xs = lambda d: x_end - toward * d
    bx = sorted({S.span_built(v) for v in (S.FLAP_X[0], S.FLAP_X[1], S.AIL_X[0], S.AIL_X[1])})
    ra = _RingAt(lambda d: wing_ring(wing_station(xs(d), side), xs(d), wing_mode(xs(d)), ns),
                 lambda d: wing_station(xs(d), side),
                 lambda close: [toward * (x_end - b) for b in bx if 0 < toward * (x_end - b) < close])
    open_end(mb, ra, V((side * toward, 0, 0)), section_pairs(2 * ns + 1, ns), seed=f'wing:{side}:{round(x_end, 3)}:{seed}',
             stubs=((0.25, True), (0.55, True), (0.25, False), (0.55, False)), notch=notch, close=wing_cavity(x_end, toward),
             close_back=not (abs(x_end - S.span_built(S.WING_BREAKS[2])) < 1e-6 and toward < 0))


def wing_tip_cap(mb, side, ring_last, xb):
    """rounded tip: rings shrinking toward the tip point (pre 5.84), closed with a fan."""
    tip = P((side * 5.84, -0.24, 0.118))
    c = sum(ring_last, V()) / len(ring_last)
    rings = [ring_last]
    for f in (0.30, 0.58, 0.80, 0.94):
        cc = c + (tip - c) * f
        rings.append([cc + (p - c) * math.sqrt(max(1 - f * f, 0.0)) for p in ring_last])
    loft(mb, rings, 'paint', closed=True, outward=True)
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / len(rings[-1]), 'paint', V((side, 0, 0)), uvfunc=lambda p: planar_uv(p, V((side, 0, 0))))


def build_wings():
    parts = []
    br = [S.span_built(b) for b in S.WING_BREAKS]
    tip_last = S.span_built(5.76)
    mb = MeshBuf()
    POST_ADD.clear()
    for side in (1, -1):
        loft_wing(mb, side, 0.0, br[0], cap0=False, cap1=('post', 'fus_center') if OPEN_BREAKS else True, step=0.035, cut=not WELL_BOOLEAN, ns=60)
        if WELL_BOOLEAN:
            mark_cove(mb, side)      # r8e: the flap cove from x 0.70 now lies in the root part (break 0.95)
    if not WELL_BOOLEAN:
        wells(mb, (1, -1), 'C')
    parts.append(Part('wing_C', 'fus_center', (0, -0.45, -0.45), mb, info=dict(kind='wing_centre', note='on the root part')))
    for side, L in ((1, 'R'), (-1, 'L')):
        mb = MeshBuf()
        loft_wing(mb, side, br[0], br[1], ('post', f'wing_inner_{L}') if OPEN_BREAKS else True, True, step=0.035, cut=not WELL_BOOLEAN, ns=60)
        if not WELL_BOOLEAN:
            wells(mb, (side,), 'inner')
        mark_cove(mb, side)          # r8: aotake cove + ribs (split flap review)
        cove_details(mb, side)
        parts.append(Part(f'wing_inner_{L}', 'A6M2_root', (side * 1.6, -0.40, -0.33), mb))
        mb = MeshBuf()
        loft_wing(mb, side, br[1], br[2], True, True, extra=[S.PLUG_X, S.PLUG_X + S.PLUG])
        parts.append(Part(f'wing_mid_{L}', f'wing_inner_{L}', (side * 3.8, -0.30, -0.10), mb))
        mb = MeshBuf()
        rt_ = loft_wing(mb, side, br[2], br[3], True, False, step=0.08)
        fan_cap(mb, rt_[-1], sum(rt_[-1], V()) / len(rt_[-1]), 'paint', V((side, 0, 0)), uvfunc=lambda p: planar_uv(p, V((side, 0, 0))))   # r8b: painted fold rib face
        stf = wing_station(br[3], side)
        cylinder(mb, stf.point(0.04, True) + stf.up * 0.003, stf.point(0.96, True) + stf.up * 0.003, 0.004, N=8, mat='gear')         # fold hinge line
        parts.append(Part(f'wing_tip_{L}', f'wing_mid_{L}', (side * 5.1, -0.25, 0.05), mb))
        mb = MeshBuf()
        rings = loft_wing(mb, side, br[3], tip_last, False, False, step=0.06)
        fan_cap(mb, rings[0], sum(rings[0], V()) / len(rings[0]), 'paint', V((-side, 0, 0)), uvfunc=lambda p: planar_uv(p, V((-side, 0, 0))))   # r8b
        wing_tip_cap(mb, side, rings[-1], tip_last)
        nav_lamp(mb, side)
        parts.append(Part(f'wing_fold_{L}', f'wing_tip_{L}', (side * 5.6, -0.20, 0.10), mb))
        parts += control_surfaces(side, L)
        if FILLET_BALL:
            import a6m2_fillet_ball as FB_       # r8i: rolling-ball fillet (see a6m2_fillet_ball)
            parts += FB_.fillet_ball(side, L)
            FILLET_ROWS[L] = FB_.ROWS[L]
            FILLET_FRAMES[L] = FB_.FRAMES[L]
            globals()['FILLET_VIS'] = FB_.NA + 1
        else:
            parts += fillet(side, L)
    return parts


def lower_z(x, y):
    """wing lower-skin z at built (x, y) (flap cove ignored)."""
    st = wing_station(min(abs(x), 6.0), 1)
    s = min(max((st.le.y - y) / st.chord, 0.0), 1.0)
    return st.point(s, False).z


def upper_z(x, y):
    st = wing_station(min(abs(x), 6.0), 1)
    s = min(max((st.le.y - y) / st.chord, 0.0), 1.0)
    return st.point(s, True).z


WELL_BOOLEAN = True  # r8e: the wheel wells are boolean-cut into the solid wing (build_a6m2.unify_root): clean holes, no liners / rim
WELL_CEIL = 0.006   # r1 gear sweep: well ceiling 18 mm under the upper skin (the body floor hugs it at 12 mm, the stowed wheel needs the depth)


def _signed_area(poly):
    return 0.5 * sum(poly[i].x * poly[(i + 1) % len(poly)].y - poly[(i + 1) % len(poly)].x * poly[i].y for i in range(len(poly)))


def offset_poly(poly, d):
    """plan polygon offset outward by d (vertex normals from the two adjacent edges)."""
    ccw = _signed_area(poly) > 0
    out = []
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        e1 = (b - a).normalized(); e2 = (c - b).normalized()
        n1 = V((e1.y, -e1.x, 0)) if ccw else V((-e1.y, e1.x, 0))
        n2 = V((e2.y, -e2.x, 0)) if ccw else V((-e2.y, e2.x, 0))
        nm = (n1 + n2)
        if nm.length < 1e-6:
            nm = n1
        nm.normalize()
        cosh = max(nm.dot(n1), 0.35)
        out.append(b + nm * (d / cosh))
    return out


def _clip_x(poly, x0, keep_inside):
    """Sutherland-Hodgman against the plane |x| = x0 (same side of the aircraft for every point of a face)."""
    def ins(q):
        return (abs(q.x) <= x0 + 1e-9) if keep_inside else (abs(q.x) >= x0 - 1e-9)
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ia, ib = ins(a), ins(b)
        if ia:
            out.append(a)
        if ia != ib:
            da, db = abs(a.x) - x0, abs(b.x) - x0
            t = da / (da - db) if abs(da - db) > 1e-12 else 0.0
            out.append(a + (b - a) * t)
    return out


def le_cut_y(x, margin=0.045):
    """r8d: the line the wheel-well cut never passes (built y): 45 mm behind the wing's leading edge at |x|; the rim band stops 20 mm
    behind the LE (it overlaps the first uncut skin row instead of leaving a slit: root-seam check)."""
    st = wing_station(min(max(abs(x), 0.05), 6.0), 1)
    return st.le.y - margin


def _clip_y_le(poly):
    """Sutherland-Hodgman against y <= le_cut_y(x) (the LE line is straight enough over a rim segment to use its value at the edge points)."""
    def ins(q):
        return q.y <= le_cut_y(q.x, RIM_LE) + 1e-9
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ia, ib = ins(a), ins(b)
        if ia:
            out.append(a)
        if ia != ib:
            da, db = a.y - le_cut_y(a.x, RIM_LE), b.y - le_cut_y(b.x, RIM_LE)
            t = da / (da - db) if abs(da - db) > 1e-12 else 0.0
            out.append(a + (b - a) * t)
    return out


def _emit(mb, pts, mat, toward, region):
    """add a planar polygon clipped to the part region ('C': |x| <= break, 'inner': >= break), oriented toward `toward`."""
    x0 = S.span_built(S.WING_BREAKS[0])
    q = _clip_x(pts, x0, region == 'C') if region else list(pts)
    if len(q) < 3:
        return
    n = V()
    for i in range(1, len(q) - 1):
        n += (q[i] - q[0]).cross(q[i + 1] - q[0])
    if n.length < 1e-12:
        return
    if n.dot(V(toward)) < 0:
        q = list(reversed(q))
    mb.poly(q, mat, [planar_uv(x, V((0, 0, -1))) for x in q] if mat == 'paint' else None)


def well_cutter(side):
    """r8e: the wheel-well cutter of one side as (bottom ring, top ring) over the opening outline (round well + leg slot): from 30 mm
    under the lower skin up to the well ceiling (round part: 18 mm under the upper skin, as the r1 liners) or the slot floor (75 mm over
    the lower skin). build_a6m2.unify_root subtracts it from the root mesh and the wing_inner parts (EXACT boolean): the hole, its walls
    and ceiling in one piece, aotake ('well') from the cutter."""
    a, c = slot_axis(side)
    R = S.WELL_R * K
    zceil0 = upper_z(c.x, c.y) - WELL_CEIL - 0.012
    ol = opening_outline(side)
    bot, top = [], []
    for p in ol:
        lz = lower_z(p.x, p.y)
        inside = (V((p.x, p.y, 0)) - V((c.x, c.y, 0))).length <= R + 0.002
        zt = min(zceil0, upper_z(p.x, p.y) - WELL_CEIL - 0.012) if inside else lz + 0.075
        bot.append(V((p.x, p.y, lz - 0.03)))
        top.append(V((p.x, p.y, zt)))
    return bot, top


def wells(mb, sides=(1, -1), region='C'):
    """round well liners (wall + ceiling), leg grooves and a flush rim round each opening, clipped at the wing_C / wing_inner break so
    each part closes its own share of the cut (r1 check: a detached wing_inner showed through its slot)."""
    for side in sides:
        a, c = slot_axis(side)
        R = S.WELL_R * K
        e = (a - c).normalized()
        te = math.atan2(e.y, e.x)
        dl = math.asin(min(SLOT_W / R, 0.99))
        zceil0 = upper_z(c.x, c.y) - WELL_CEIL - 0.012

        def zc(p):
            return min(zceil0, upper_z(p.x, p.y) - WELL_CEIL - 0.012)
        N = 48
        circ = [c + V((math.cos(te + dl + (2 * math.pi - 2 * dl) * k / N), math.sin(te + dl + (2 * math.pi - 2 * dl) * k / N), 0)) * R for k in range(N + 1)]
        for i in range(N):
            p0, p1 = circ[i], circ[i + 1]
            q = [V((p0.x, p0.y, lower_z(p0.x, p0.y) - 0.0015)), V((p1.x, p1.y, lower_z(p1.x, p1.y) - 0.0015)),
                 V((p1.x, p1.y, zc(p1))), V((p0.x, p0.y, zc(p0)))]
            mid = (p0 + p1) / 2
            _emit(mb, q, 'well', V((c.x - mid.x, c.y - mid.y, 0)), region)
        # ceiling: polar grid (clippable), faces down
        nr = 6
        for ir in range(nr):
            r0, r1 = R * ir / nr, R * (ir + 1) / nr
            for k in range(N):
                a0, a1 = 2 * math.pi * k / N, 2 * math.pi * (k + 1) / N
                pts = [c + V((math.cos(a0), math.sin(a0), 0)) * r0, c + V((math.cos(a0), math.sin(a0), 0)) * r1,
                       c + V((math.cos(a1), math.sin(a1), 0)) * r1, c + V((math.cos(a1), math.sin(a1), 0)) * r0]
                if ir == 0:
                    pts = [pts[0], pts[1], pts[2]]
                _emit(mb, [V((x.x, x.y, zc(x))) for x in pts], 'well', V((0, 0, -1)), region)
        # leg groove from the pivot to the well: side walls on the slot edges, floor 75 mm up, end wall at the pivot
        L = (c - a).length
        d = -e
        nrm = V((-d.y, d.x, 0))
        for k in range(13):
            t0, t1 = L * k / 13, L * (k + 1) / 13
            for s_ in (-1, 1):
                pa, pb = a + d * t0 + nrm * (SLOT_W * s_), a + d * t1 + nrm * (SLOT_W * s_)
                za, zb = lower_z(pa.x, pa.y) - 0.0015, lower_z(pb.x, pb.y) - 0.0015
                _emit(mb, [V((pa.x, pa.y, za)), V((pb.x, pb.y, zb)), V((pb.x, pb.y, zb + 0.075)), V((pa.x, pa.y, za + 0.075))], 'well', -nrm * s_, region)
            pa, pb = a + d * t0, a + d * t1
            fl = [pa + nrm * SLOT_W, pb + nrm * SLOT_W, pb - nrm * SLOT_W, pa - nrm * SLOT_W]
            _emit(mb, [V((x.x, x.y, lower_z(x.x, x.y) + 0.0735)) for x in fl], 'well', V((0, 0, -1)), region)
        e0 = [a + nrm * SLOT_W, a - nrm * SLOT_W]
        _emit(mb, [V((x.x, x.y, lower_z(x.x, x.y) - 0.0015)) for x in e0] + [V((x.x, x.y, lower_z(x.x, x.y) + 0.0735)) for x in reversed(e0)], 'well', d, region)
        # rim: flush band from the opening outline outward (covers the stepped skin cut)
        # r8d (r8c sheets: jagged shards at the LE root, lower side): the 50 mm band reached 13 mm AHEAD of the wing LE (opening front y 0.73,
        # LE 0.767), where lower_z is clamped to the LE: planar pieces stuck out of the nose. The band now stops at the LE cut line
        # (le_cut_y), and the skin ahead of that line is never cut (loft_wing keep)
        ol = opening_outline(side)
        ob = offset_poly(ol, RIM_W)
        for i in range(len(ol)):
            j = (i + 1) % len(ol)
            q = [ol[i], ol[j], ob[j], ob[i]]
            q = _clip_y_le(q)
            if len(q) >= 3:
                _emit(mb, [V((x.x, x.y, lower_z(x.x, x.y) - 0.0015)) for x in q], 'paint', V((0, 0, -1)), region)


def cove_gap(st, sf, s_):
    """r8: vertical room between the retracted flap's lower skin and the cove ceiling (wing_ring 'flap' mode) at chord share s_."""
    p_f = st.point(sf, False)
    p_te = st.point(1.0, True) - st.up * 0.0005
    t = (s_ - sf) / max(1 - sf, 1e-6)
    ceil = p_f + (p_te - p_f) * t + st.up * (0.006 * (1 - t) + 0.004 * math.sin(math.pi * t))
    return max(0.0, (ceil - st.point(s_, False)).dot(st.up) - 0.005)


def cove_details(mb, side):
    """r8: the flap cove of wing_inner in aotake ('well' faces: the cove ceiling of the lofted skin is re-tagged by mark_cove) with
    low chordwise ribs hanging 6 mm from the ceiling between the flap ribs."""
    x0, x1 = S.span_built(S.FLAP_X[0]), S.span_built(S.FLAP_X[1])
    nrib = max(2, int(round((x1 - x0) / 0.155)))
    for r in range(nrib):
        x = x0 + (x1 - x0) * (r + 0.5) / nrib
        st = wing_station(x, side)
        sf = flap_s(x)
        p_f = st.point(sf, False); p_te = st.point(1.0, True) - st.up * 0.0005
        for j in range(8):
            t0, t1 = 0.10 + 0.8 * j / 8, 0.10 + 0.8 * (j + 1) / 8
            a = p_f + (p_te - p_f) * t0 + st.up * (0.006 * (1 - t0) + 0.004 * math.sin(math.pi * t0))
            b = p_f + (p_te - p_f) * t1 + st.up * (0.006 * (1 - t1) + 0.004 * math.sin(math.pi * t1))
            bar(mb, a - st.up * 0.003, b - st.up * 0.003, 0.004, 0.006, st.up, 'well')


def mark_cove(mb, side):
    """r8: faces of the lofted wing skin that form the flap cove ceiling become 'well' (aotake, as the WT cove)."""
    x0, x1 = S.span_built(S.FLAP_X[0]), S.span_built(S.FLAP_X[1])
    for f in mb.faces:
        if f['mat'] != 'paint':
            continue
        q = [mb.verts[i] for i in f['idx']]
        c = sum(q, V()) / len(q)
        if not (x0 - 1e-3 < abs(c.x) < x1 + 1e-3) or c.x * side < 0:
            continue
        st = wing_station(abs(c.x), 1)
        sf = flap_s(min(max(abs(c.x), x0 + 2e-4), x1 - 2e-4))
        if sf is None:
            continue
        s_ = (st.le.y - c.y) / st.chord
        if sf + 0.004 < s_ < 0.94 and c.z < upper_z(abs(c.x), c.y) - 0.0015:     # r8b: the last 6 % of the cove (seen at the TE) stays in livery
            f['mat'] = 'well'; f['uv'] = None


def control_surfaces(side, L):
    parts = []
    # aileron: aft piece from the hinge (+gap) to the TE, x = AIL_X (built)
    x0, x1 = S.span_built(S.AIL_X[0]), S.span_built(S.AIL_X[1])
    n = max(3, int((x1 - x0) / 0.12))
    sts = []
    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n
        st = wing_station(x, side)
        sts.append((st, ail_s(x if k < n else x - 1e-4)))
    mb = MeshBuf()
    rings = []
    for st, sh in sts:
        ss = [sh + (1 - sh) * k / 8 for k in range(9)]
        hu, hl = st.point(sh, True), st.point(sh, False)
        mid = (hu + hl) / 2 - st.cdir * ((hu - hl).length * 0.42)     # round nose ahead of the hinge (inside the gap)
        up = [st.point(s, True) for s in reversed(ss)]
        lo = [st.point(s, False) for s in ss]
        nose = [hu + (mid - hu) * 0.55, mid, hl + (mid - hl) * 0.55]
        rings.append(up[:-1] + [hu] + nose + [hl] + lo[1:])
    loft(mb, rings, 'paint', closed=True, outward=True)
    for ring, tw in ((rings[0], V((-side, 0, 0))), (rings[-1], V((side, 0, 0)))):
        section_close(mb, ring, tw, 'paint')
    hinge_a = (sts[0][0].point(sts[0][1], True) + sts[0][0].point(sts[0][1], False)) / 2
    hinge_b = (sts[-1][0].point(sts[-1][1], True) + sts[-1][0].point(sts[-1][1], False)) / 2
    axis = (hinge_b - hinge_a).normalized() * side
    parts.append(Part(f'aileron_{L}', f'wing_mid_{L}', hinge_a, mb, frame=frame_x(axis), info=dict(kind='control', hinge_axis=tuple(axis))))
    # r8 split flap (user review 1: "disgusting"): the real A6M2 split flap - a stiffened plate that is the wing's lower skin from the
    # hinge to the trailing edge, flush when up. Plate 5 mm (outer face livery, inner face aotake 'well' like the WT flap and the wells),
    # piano hinge along the leading edge, chordwise ribs every ~155 mm and a spanwise stiffener on the inner face, their height kept under
    # the cove ceiling (cove_gap) so the retracted flap fits; closed end ribs. The cove above it is aotake with matching ribs (cove_details).
    x0, x1 = S.span_built(S.FLAP_X[0]), S.span_built(S.FLAP_X[1])
    n = max(6, int((x1 - x0) / 0.06))
    mb = MeshBuf()
    T = 0.005
    rows_o, rows_i, sts = [], [], []
    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n
        st = wing_station(x, side)
        sf = flap_s(min(max(x, x0 + 1e-4), x1 - 1e-4))
        ss = [sf + (1 - sf) * j / 10 for j in range(11)]
        o = [st.point(s_, False) for s_ in ss]
        i_ = [p + st.up * T for p in o]
        i_[-1] = o[-1] + st.up * 0.0012
        rows_o.append(o); rows_i.append(i_); sts.append((st, sf, x))
    po, pi_ = MeshBuf(), MeshBuf()
    loft(po, rows_o, 'paint', closed=False, outward=True)
    loft(pi_, rows_i, 'well', closed=False, outward=True, face_mat=lambda i, j: 'paint' if j >= 8 else 'well')   # r8b: TE strip in paint (teal TE line)
    for m_, want_down in ((po, True), (pi_, False)):
        for f in m_.faces:
            q = [m_.verts[i] for i in f['idx']]
            nz = ((q[1] - q[0]).cross(q[2] - q[0])).z
            if (nz > 0) == want_down:
                f['idx'] = list(reversed(f['idx']))
                if f['uv']:
                    f['uv'] = list(reversed(f['uv']))
        mb.extend(m_)
    cd = sts[0][0].cdir
    for k in range(n):
        oriented_quad(mb, [rows_o[k][0], rows_o[k + 1][0], rows_i[k + 1][0], rows_i[k][0]], 'well', -cd)
        oriented_quad(mb, [rows_o[k][-1], rows_o[k + 1][-1], rows_i[k + 1][-1], rows_i[k][-1]], 'paint', cd)
    for r_o, r_i, tw in ((rows_o[0], rows_i[0], V((-side, 0, 0))), (rows_o[-1], rows_i[-1], V((side, 0, 0)))):
        for j in range(len(r_o) - 1):
            oriented_quad(mb, [r_o[j], r_o[j + 1], r_i[j + 1], r_i[j]], 'well', tw)
    # ribs: chordwise, every ~155 mm incl. both ends; height = 70 % of the cove gap (max 22 mm), 4 mm thick
    nrib = max(2, int(round((x1 - x0) / 0.155)))
    for r in range(nrib + 1):
        x = x0 + 0.004 + (x1 - x0 - 0.008) * r / nrib
        st = wing_station(x, side)
        sf = flap_s(min(max(x, x0 + 1e-4), x1 - 1e-4))
        for j in range(9):
            s_a, s_b = sf + (1 - sf) * (0.04 + 0.92 * j / 9), sf + (1 - sf) * (0.04 + 0.92 * (j + 1) / 9)
            pa, pb = st.point(s_a, False) + st.up * T, st.point(s_b, False) + st.up * T
            ha = min(0.022, 0.7 * cove_gap(st, sf, s_a)); hb = min(0.022, 0.7 * cove_gap(st, sf, s_b))
            h_ = max(0.003, min(ha, hb))
            bar(mb, pa + st.up * (h_ / 2), pb + st.up * (h_ / 2), 0.004, h_, st.up, 'well')
            bar(mb, pa + st.up * (h_ + 0.0008), pb + st.up * (h_ + 0.0008), 0.016, 0.0016, st.up, 'well')   # r8c: rib cap flange (WT channel ribs)
        # r8c hinge bracket (coordinator r8c item 5): a gusset plate from the piano hinge down the rib's first 55 mm, and a knuckle block
        # round the hinge pin; every second rib and both ends. Height kept under 70 % of the cove gap like the ribs.
        if r % 2 == 0 or r == nrib:
            hp = st.point(sf, False) + st.up * T
            s1 = sf + min(0.055 / max(st.chord, 0.3), 0.3) * 1.0
            pb_ = st.point(s1, False) + st.up * T
            hgt = max(0.004, min(0.020, 0.7 * cove_gap(st, sf, sf + (s1 - sf) * 0.3)))
            tri = [hp + st.up * 0.002, pb_, hp + st.up * hgt]
            nrm_ = (tri[1] - tri[0]).cross(tri[2] - tri[0]).normalized()
            for off in (-0.003, 0.003):
                q = [v + nrm_ * off for v in tri]
                mb.poly(q if off > 0 else list(reversed(q)), 'gear', None, False)
            for a_, b_ in zip(tri, tri[1:] + tri[:1]):
                oriented_quad(mb, [a_ - nrm_ * 0.003, b_ - nrm_ * 0.003, b_ + nrm_ * 0.003, a_ + nrm_ * 0.003], 'gear', ((a_ + b_) / 2 - sum(tri, V()) / 3))
            box(mb, hp + st.up * 0.004, (0.028, 0.014, 0.012), 'gear', rot=None)
    # spanwise stiffener at 30 % of the flap chord; piano hinge along the leading edge
    for (k0, k1) in ((0, n),):
        sA, sfA, _ = sts[k0]; sB, sfB, _ = sts[k1]
        pa = sA.point(sfA + (1 - sfA) * 0.30, False) + sA.up * T; pb = sB.point(sfB + (1 - sfB) * 0.30, False) + sB.up * T
        h_ = max(0.003, min(0.014, 0.6 * cove_gap(sA, sfA, sfA + (1 - sfA) * 0.30), 0.6 * cove_gap(sB, sfB, sfB + (1 - sfB) * 0.30)))
        bar(mb, pa + sA.up * (h_ / 2), pb + sB.up * (h_ / 2), 0.006, h_, sA.up, 'well')
    for r in range(nrib + 1):                                   # r8c: oval pads where the ribs cross the stiffener (WT)
        x = x0 + 0.004 + (x1 - x0 - 0.008) * r / nrib
        st = wing_station(x, side)
        sf = flap_s(min(max(x, x0 + 1e-4), x1 - 1e-4))
        c_ = st.point(sf + (1 - sf) * 0.30, False) + st.up * T
        hh = max(0.003, min(0.016, 0.62 * cove_gap(st, sf, sf + (1 - sf) * 0.30)))
        cylinder(mb, c_, c_ + st.up * hh, 0.011, N=12, mat='well')
    st0 = wing_station(x0, side)
    h_a = st0.point(flap_s(x0 + 1e-4), False)
    st1 = wing_station(x1, side)
    h_b = st1.point(flap_s(x1 - 1e-4), False)
    cylinder(mb, h_a + st0.up * 0.004, h_b + st1.up * 0.004, 0.0045, N=10, mat='gear')
    fax = (h_b - h_a).normalized() * side
    parts.append(Part(f'flap_{L}', f'wing_inner_{L}', h_a, mb, frame=frame_x(fax), info=dict(kind='flap', hinge_axis=tuple(fax),
                                                                                            poses=S.FLAP_POSES)))
    return parts


def section_close(mb, ring, toward, mat):
    c = sum(ring, V()) / len(ring)
    fan_cap(mb, ring, c, mat, toward, uvfunc=(lambda p: planar_uv(p, toward)) if mat == 'paint' else None)


def body_x_at_z(yb, z):
    zt_, zb_, hw, zw, nt, nb = body_params(yb)
    if z > zw:
        r = (z - zw) / max(zt_ - zw, 1e-6)
        return hw * (1 - min(r, 0.999) ** nt) ** (1.0 / nt)
    r = (zw - z) / max(zw - zb_, 1e-6)
    return hw * (1 - min(r, 0.999) ** nb) ** (1.0 / nb)


_RING_CACHE = {}


def _ring_right(yb):
    k = round(yb, 4)
    if k not in _RING_CACHE:
        r = [q for q in body_ring(yb) if q.x >= -1e-9]
        r.sort(key=lambda q: math.atan2(q.z - body_params(yb)[3], q.x))
        _RING_CACHE[k] = r
    return _RING_CACHE[k]


def body_ring_x(yb, z):
    """r8: |x| of the ACTUAL outer skin ring (body_ring: flattened onto the wing top at the root) at height z, right side; below the
    ring's lowest side point the x of that point. body_x_at_z (the plain section formula) is up to 80 mm outboard of the real skin at
    z -0.18..-0.25 over the wing root, which left the r1-r7 fillet floating clear of the fuselage (user review 1: open gap)."""
    r = _ring_right(yb)
    best = None
    for a, b in zip(r, r[1:]):
        if (a.z - z) * (b.z - z) <= 0 and abs(b.z - a.z) > 1e-9:
            x = a.x + (b.x - a.x) * (z - a.z) / (b.z - a.z)
            best = x if best is None else max(best, x)
    if best is None:
        lo = min(r, key=lambda q: q.z)
        best = lo.x if z < lo.z else max(q.x for q in r)
    return best


FILLET_ROWS = {}         # r8c: the fillet rows per side (checks_r8.fillet_smooth)
FILLET_FRAMES = {}       # r8i: per row (spine point, sweep direction) of the rolling-ball fillet (rows in rotating planes)
FILLET_BALL = True       # r8i: the root fillet is a variable-radius rolling-ball blend (a6m2_fillet_ball); False = the r8h fairing
FILLET_VIS = 8           # r8i: visible points per row from the top edge (checks_r8.fillet_smooth)
FILLET_FILL = True       # r8h: fillet top edge at the body's widest line over the wing (no shadowed overhang)
FILLET_FRONT_RAMP = 0.55  # r8h: width ramp at the front (r8e-r8g 0.30)
FILLET_FRONT_Y = 0.82     # r8h: the filled fairing starts at the LE root (r8e moved it back to 0.60 behind the LE)
FILLET_FILL_RAMP = 0.40  # r8h: m from the fairing's front to the full raise
FILLET_TOP_BELOW = 0.04  # r8h: top edge this far under the widest line (a cleaner crossing than tangent)
FILLET_BEAD = 0.07       # r8h: foot this far beyond the widest line
FILLET_UNIFORM_FADE = True  # r8h: front rows scaled whole toward the body / wing corner
FILLET_FADE_TOP = False  # r8f: (False tried: exposed a hole at the LE root) r8e lowered the fading fairing's top edge toward the wing (exposed the body overhang)
FILLET_PROUD = -0.003    # r8d: top edge / foot 3 mm under the fuselage / wing skin; with FILLET_ARC they cross the skins at ~30 deg
FILLET_ARC = (12.0, 45.0)  # r8e: near-tangent again - the fairing is boolean-UNIONED into the root mesh (no overlap left)  # r8d: arc span (deg) of the fairing section (r1-r8c: 0-90, tangent to both skins)


def fillet(side, L):
    """root fairing (on the root part): a closed loft per side; top = concave quarter-round from the body side down to the wing top,
    bottom inside the wing (hidden) or, aft of the wing TE, at the TE lower level (the fairing runs on to y -2.25 like the reference)."""
    mb = MeshBuf()
    rows = []
    tab = sorted(S.FILLET, key=lambda r: -r[0])
    if FILLET_FILL and FILLET_FRONT_Y > tab[0][0]:
        tab = [(FILLET_FRONT_Y, tab[0][1], tab[0][2])] + tab
    dense = []                                    # r8: rows every <= 50 mm (the loft between the table rows cut inside the curved skin)
    for (ya, xa, za), (yb2, xb2, zb2) in zip(tab, tab[1:]):
        m_ = max(1, int(math.ceil((ya - yb2) / 0.05)))
        for k in range(m_):
            t = k / m_
            dense.append((ya + (yb2 - ya) * t, xa + (xb2 - xa) * t, za + (zb2 - za) * t))
    dense.append(tab[-1])
    y_front, y_back = dense[0][0], dense[-1][0]

    def sstep(e0, e1, v):
        t = min(max((v - e0) / (e1 - e0), 0.0), 1.0)
        return t * t * (3 - 2 * t)
    # r8c: the body ring flattens onto the wing top at the LE (x at the fillet top jumps 0.50 -> 0.38 within 40 mm): the fillet's top edge
    # follows the NARROWEST skin x within +-2 rows (always buried, never proud) so the jump does not crease the fairing
    # r8d (r8c shards): the fairing is TANGENT to the fuselage at its top edge and to the wing at its foot; 3 mm inside both skins it crossed
    # them at 8-24 deg along its whole length, and the two meshes' triangles interleaved there (jagged light shards). Now the top edge and the
    # foot stand 1 mm PROUD of the skins (no shallow crossing anywhere; the inner side / underside then dive steeply into the body / wing)
    # r8d: the fairing's top edge stays >= 40 mm above the wing's upper skin at the body side (the table's z -0.24..-0.25 at y 0.0..0.4 lay
    # UNDER the wing skin there: the fairing ran inside the wing, nearly coplanar with it, and broke through it in patches)
    dense2 = []
    for y, xf, zt in dense:
        zt_ = zt * K
        for _ in range(3):
            xs_ = body_ring_x(y * K, zt_)
            zt_ = max(zt * K, upper_z(max(xs_, 0.30), y * K) + 0.040) if -0.05 < (wing_station(max(xs_, 0.56), 1).le.y - y * K) / wing_station(max(xs_, 0.56), 1).chord < 1.05 else zt * K
        if FILLET_FILL and -0.20 < (wing_station(max(body_ring_x(y * K, zt_), 0.56), 1).le.y - y * K) / wing_station(max(body_ring_x(y * K, zt_), 0.56), 1).chord < 1.05:
            # r8h (game r8g, confirmed by the shadows-off probe: a sawtooth shadow band along the fillet-wing line): the body is
            # 100-400 mm narrower at the fillet's top edge than at its widest line, so its side above the fillet faced down and the
            # 40 deg sun cast a shadow band onto the fillet / wing root. The top edge goes up to the body's widest line (no
            # down-facing side left above it) and the foot stands FILLET_BEAD beyond that line (WT: a near-vertical side + a rounded bead)
            zs_ = [zt_ + 0.01 * i for i in range(46)]
            xw_ = [body_ring_x(y * K, z_) for z_ in zs_]
            iw = max(range(len(xw_)), key=lambda i: xw_[i])
            if xw_[iw] > body_ring_x(y * K, zt_) + 0.005:
                # the raise grows over FILLET_FILL_RAMP behind the fairing's front (a 0.3 m ramp stood up like a fin at the LE root)
                t_ = min(max((dense[0][0] - y) / FILLET_FILL_RAMP, 0.0), 1.0); r_ = t_ * t_ * (3 - 2 * t_)
                # and it fades out toward the trailing edge (a jump back to the table height at the TE made a step / inverted shell)
                stw_ = wing_station(max(body_ring_x(y * K, zt_), 0.56), 1); s_te = (stw_.le.y - y * K) / stw_.chord
                u_ = min(max((s_te - 0.70) / 0.30, 0.0), 1.0); r_ *= 1.0 - u_ * u_ * (3 - 2 * u_)
                zt_ = zt_ + ((zs_[iw] - FILLET_TOP_BELOW) - zt_) * r_
                xf = xf + (max(xf, (xw_[iw] + FILLET_BEAD) / K) - xf) * r_
        dense2.append((y, xf, zt_ / K))
    dense = dense2
    xb_raw = [body_ring_x(y * K, zt * K) + FILLET_PROUD for y, xf, zt in dense]
    xb_min = xb_raw                                          # r8d: the body ramp (body_ring) removed the ring jump at the LE: no envelope needed
    for (y, xf, zt), xb in zip(dense, xb_min):
        yb = y * K
        zt_b = zt * K
        # r8b (critique: a pod / tray glued on, a tubular lip ahead of the LE): the fairing grows out of the fuselage - zero width at both
        # ends (front y 0.80 -> full at 0.62, back full at -1.95 -> zero at -2.25), and off the wing (ahead of the LE / behind the TE) its
        # underside curves back into the fuselage instead of a flat tray
        tf_front = sstep(y_front, y_front - FILLET_FRONT_RAMP, y)
        tf = tf_front * sstep(y_back, y_back + 0.30, y)
        if FILLET_UNIFORM_FADE:
            # r8h (front tip as a knife-thin plate hovering over the wing - height and width faded by different rules): the front rows
            # are built at full shape and scaled as a whole toward the body / wing corner below (one rule: no plate, no fin)
            tf = sstep(y_back, y_back + 0.30, y)
        xfoot = xb + max((xf * K - xb) * tf, 0.006)
        st = wing_station(max(xfoot, 0.56), 1)
        sch = (st.le.y - yb) / st.chord
        # r8c (game r8b: a light spike at the LE root, a crease, a lipped shelf aft-low): ONE row topology for the whole fillet. The
        # on-wing shape (foot buried under the wing skin, inner side hugging the fuselage) and the off-wing shape (underside curving back
        # into the fuselage) are blended with a smooth weight over the LE / TE bands instead of switching between rows (the switch twisted
        # the loft into the spike and the shelf). The foot height uses the wing surface clamped into the chord.
        w_on = sstep(-0.06, 0.05, sch) * (1.0 - sstep(0.93, 1.06, sch))
        zw_ = upper_z(xfoot, st.le.y - min(max(sch, 0.0), 1.0) * st.chord) + FILLET_PROUD
        g_aft = 1.0 - sstep(1.0, 1.14, sch)              # behind the TE the foot climbs back up the body (no curtain / shelf under the TE)
        zfoot = zt_b - (zt_b - zw_) * tf * g_aft         # the foot drops to the wing only as the fairing grows (zero-size end rows)
        # r8e (0.5 m sheet: the front tip hovered over the wing and cast a wedge shadow): ON the wing the fading fairing shrinks into
        # the body / wing corner - foot on the wing skin, top edge lowered toward it - instead of lifting its foot off the wing
        if w_on > 0.0 and tf < 1.0:
            # r8f (0.5 m sheet r8e: a dark 'smudge' strip under the LE root = the fuselage's down-facing overhang above the wing, uncovered
            # once r8e lowered the fading fairing's top edge): the top edge stays under the overhang (FILLET_FADE_TOP = False); only the foot
            # goes onto the wing skin
            if FILLET_FADE_TOP:
                zt_on = zw_ + (zt_b - zw_) * max(tf, 0.15)
                zt_b = zt_b + (zt_on - zt_b) * w_on
            zfoot = zfoot + (zw_ - zfoot) * w_on
        row = []
        # r8d: a 30-60 deg arc, not a full quarter round - the fairing meets the fuselage and the wing at ~30 deg instead of tangentially
        # (tangent surfaces a few mm apart cross along the facets of both meshes: the jagged shards of the r8c sheets)
        a0, a1 = math.radians(FILLET_ARC[0]), math.radians(FILLET_ARC[1])
        fx0, fx1, fz0, fz1 = 1 - math.cos(a0), 1 - math.cos(a1), math.sin(a0), math.sin(a1)
        for k in range(7):
            a = a0 + (a1 - a0) * k / 6
            x = xb + (xfoot - xb) * ((1 - math.cos(a)) - fx0) / (fx1 - fx0)
            z = zt_b - (zt_b - zfoot) * (math.sin(a) - fz0) / (fz1 - fz0)
            row.append(V((side * x, yb, z)))
        # on-wing underside (5 points): buried just under the wing skin, then up the fuselage side
        zlow = zfoot - 0.012
        steep = (body_ring_x(yb, zt_b) - body_ring_x(yb, zt_b - 0.03)) < 0.045
        on = [V((xfoot, 0, zlow))]
        for k in range(4):
            z = zlow + (zt_b - zlow) * k / 4
            x = (body_ring_x(yb, z) - 0.003) if steep else (xb - 0.0005)
            on.append(V((min(max(x, xb - 0.08), xfoot - 0.004), 0, z)))
        # off-wing underside (5 points): convex quarter back into the fuselage
        h = 0.6 * (xfoot - xb) + 0.004
        zb2 = zfoot - h
        xc = body_ring_x(yb, zb2) - 0.003
        off = []
        for k in range(1, 6):
            a = math.pi / 2 * k / 5
            off.append(V((xc + (xfoot - xc) * math.cos(a), 0, zfoot - (zfoot - zb2) * math.sin(a))))
        for p_on, p_off in zip(on, off):
            q = p_off * (1.0 - w_on) + p_on * w_on
            row.append(V((side * q.x, yb, q.z)))
        # r8c: the end rows shrink onto a point inside the fuselage as the fairing fades out - no sliver / V at the ends
        sc_ = sstep(0.0, 0.35, tf)
        top_ = row[0] + V((-side * 0.025, 0, -0.020))         # anchor 25 mm inside / 20 mm under the top edge: the small end rows are buried
        row = [top_ + (q - top_) * sc_ if sc_ < 1.0 else q for q in row]
        if FILLET_UNIFORM_FADE and tf_front < 1.0:
            cz_ = upper_z(max(xb, 0.30), yb) + FILLET_PROUD - 0.004
            C_ = V((side * (body_ring_x(yb, cz_) - 0.010), yb, cz_))      # the body / wing corner, 10 mm inside the body
            f_ = max(tf_front, 0.02)
            row = [C_ + (q - C_) * f_ for q in row]
        rows.append(row)
    FILLET_ROWS[L] = rows
    loft(mb, rows, 'paint', closed=True, outward=True)
    for r, tw in ((rows[0], V((0, 1, 0))), (rows[-1], V((0, -1, 0)))):
        fan_cap(mb, r, sum(r, V()) / len(r), 'paint', tw, uvfunc=lambda p, t=tw: planar_uv(p, t))
    return [Part(f'fillet_{L}', 'fus_center', (side * 0.55, -0.6, -0.25), mb, info=dict(kind='fillet'))]


def nav_lamp(mb, side):
    """r8b: a faired teardrop lens on the tip (red port, blue-green starboard) instead of a dark cylinder."""
    p = P((side * 5.78, -0.20, 0.118))
    mat = 'navred' if side < 0 else 'navgreen'
    prof = [(0.0, 0.003), (0.015, 0.012), (0.035, 0.016), (0.060, 0.014), (0.085, 0.008), (0.100, 0.002)]
    rings = [circle_pts(p + V((0, 0.05 - d_, 0)), V((0, -1, 0)), r_, 12) for d_, r_ in prof]
    rings = [[q + V((side * 0.004, 0, 0)) for q in r] for r in rings]
    loft(mb, rings, mat, closed=True, outward=True)
    fan_cap(mb, rings[0], p + V((side * 0.004, 0.05, 0)), mat, V((0, 1, 0)))
    fan_cap(mb, rings[-1], p + V((side * 0.004, -0.05, 0)), mat, V((0, -1, 0)))


# =============================================================================================== tail
def stab_station(xb, side):
    xp = xb / K
    le = S.lin(S.STAB, xp, 1) * K
    te = S.lin(S.STAB, xp, 2) * K
    ht = S.lin(S.STAB, xp, 3) * K
    c = max(le - te, 0.004)
    return Station(xb, V((side * xb, le, S.STAB_Z * K)), V((0, -1, 0)), V((0, 0, 1)), c, min(2 * ht / c, 0.30), m=0.0)


def build_tail():
    parts = []
    hinge_y = S.ELEV_HINGE_Y * K
    for side, L in ((1, 'R'), (-1, 'L')):
        x_end = S.STAB[-1][0] * K
        xs = [0.0, 0.10, 0.20] + [S.ELEV_X[0] * K] + [S.ELEV_X[0] * K + (S.ELEV_X[1] * K - S.ELEV_X[0] * K) * k / 10 for k in range(1, 11)] + \
             [0.5 * (S.ELEV_X[1] * K + x_end), x_end - 0.01]
        xs = sorted(set(round(x, 5) for x in xs))
        mb = MeshBuf()
        rings = []
        e0, e1 = S.ELEV_X[0] * K, S.ELEV_X[1] * K
        xs2 = []
        for x in xs:                                    # r1 check: the elevator ends get a full + a cut station (a wall, no slanted overlap)
            if abs(x - e0) < 1e-4:
                xs2 += [(x, False), (x, True)]
            elif abs(x - e1) < 1e-4:
                xs2 += [(x, True), (x, False)]
            else:
                xs2.append((x, e0 < x < e1))
        for x, in_el in xs2:
            st = stab_station(x, side)
            ss = [0.5 * (1 - math.cos(math.pi * k / 16)) for k in range(17)]
            if in_el and st.le.y > hinge_y:
                sh = (st.le.y - hinge_y) / st.chord - GAP / st.chord
                sh = min(max(sh, 0.05), 0.999)
                ss2 = [min(s, sh) for s in ss]
            else:
                ss2 = ss
            up = [st.point(s, True) for s in reversed(ss2)]
            lo = [st.point(s, False) for s in ss2[1:]]
            rings.append(up + lo)
        loft(mb, rings, 'paint', closed=True, outward=True)
        if OPEN_BREAKS:
            # r8o: open root (the stab detaches from fus_tail): dark band 15 mm, liner to 0.06 m, rib at 0.06 m, spar stub (no cap)
            def stab_ring(x, side=side):
                st = stab_station(x, side)
                ss = [0.5 * (1 - math.cos(math.pi * k / 16)) for k in range(17)]
                return [st.point(s_, True) for s_ in reversed(ss)] + [st.point(s_, False) for s_ in ss[1:]]
            ra = _RingAt(lambda d, f=stab_ring: f(d), lambda d, side=side: stab_station(d, side))
            open_end(mb, ra, V((-side, 0, 0)), section_pairs(33, 16), depth=STAB_ROOT_SETBACK, band=0.015, seed=f'stab:{side}', close=TAIL_CAVITY,
                     spar_stub=0.25)
        else:
            section_close(mb, rings[0], V((-side, 0, 0)), 'structure')
        tip = V((side * (x_end + 0.005), S.STAB[-1][1] * K, S.STAB_Z * K))
        fan_cap(mb, rings[-1], tip, 'paint', V((side, 0, 0)), uvfunc=lambda p: planar_uv(p, V((side, 0, 0))))
        parts.append(Part(f'stab_{L}', 'fus_tail', (side * 0.9, -4.9, S.STAB_Z * K), mb))
        # elevator: hinge -> TE over ELEV_X
        mb = MeshBuf()
        rings = []
        exs = [S.ELEV_X[0] * K + 0.003 + (S.ELEV_X[1] * K - S.ELEV_X[0] * K - 0.003) * k / 10 for k in range(11)]   # r1 z-fight: 3 mm clear of the stab's cut-out wall
        for x in exs:
            st = stab_station(x, side)
            sh = min(max((st.le.y - hinge_y) / st.chord, 0.05), 0.99)
            ss = [sh + (1 - sh) * k / 6 for k in range(7)]
            hu, hl = st.point(sh, True), st.point(sh, False)
            mid = (hu + hl) / 2 + V((0, 0.4 * (hu - hl).length, 0))
            up = [st.point(s, True) for s in reversed(ss)]
            lo = [st.point(s, False) for s in ss]
            rings.append(up[:-1] + [hu, mid, hl] + lo[1:])
        loft(mb, rings, 'paint', closed=True, outward=True)
        section_close(mb, rings[0], V((-side, 0, 0)), 'paint')
        section_close(mb, rings[-1], V((side, 0, 0)), 'paint')
        piv = V((side * S.ELEV_X[0] * K, hinge_y, S.STAB_Z * K))
        parts.append(Part(f'elevator_{L}', f'stab_{L}', piv, mb, frame=frame_x(V((1, 0, 0))),
                          info=dict(kind='control', hinge_axis=(1.0, 0.0, 0.0))))
    parts += build_fin()
    return parts


def fin_station(z):
    zp = z / K
    le = S.lin(S.FIN, zp, 1) * K
    te = S.lin(S.FIN, zp, 2) * K
    ht = S.lin(S.FIN, zp, 3) * K
    hinge = S.RUDDER_HINGE_Y * K
    if zp > S.RUDDER_HORN_Z:
        hinge = -5.505 * K
    return le, te, ht, hinge


def _fin_th(y, le, te, ht):
    """r1b: ONE section law for fin + rudder: NACA 4-digit half thickness on the full fin chord (le -> te), max = ht."""
    c = max(le - te, 1e-4)
    s = min(max((le - y) / c, 0.0), 1.0)
    return 5 * (2 * ht / c) * (0.2969 * math.sqrt(s) - 0.126 * s - 0.3516 * s * s + 0.2843 * s ** 3 - 0.1036 * s ** 4) * c


def _fin_ring(z, y0, y1, le, te, ht, nose=0.0, n=14):
    """closed section at height z from y0 (front) to y1 (aft) on the shared law; nose > 0 rounds a cut leading edge
    (the rudder nose behind the hinge gap) with an elliptic nose of that length; the aft end is the cut (flat) or the true TE."""
    ys = [y0 - (y0 - y1) * 0.5 * (1 - math.cos(math.pi * k / n)) for k in range(n + 1)]
    pts = []
    for y in ys:
        th = _fin_th(y, le, te, ht)
        if nose > 0 and y0 - y < nose:
            base = _fin_th(y0 - nose, le, te, ht)
            u = (nose - (y0 - y)) / nose
            th = base * math.sqrt(max(1 - u * u, 0.0))
        pts.append(V((max(th, 0.0012), y, z)))
    return pts + [V((-p.x, p.y, p.z)) for p in reversed(pts[1:-1])]


FIN_GAP_WEB = True   # r8e: centre-plane web in the fin / rudder hinge gaps (no sky through the gap)


def build_fin():
    """r1b (coordinator review): fin and rudder are cut from ONE outline and ONE section law, so the outline runs on
    unbroken round the top and the only break is the 10 mm hinge gap (vertical below the horn, a horizontal gap under
    the horn balance). r1 built the rudder as its own slab (thick nose, own top) that stood up and aft of the fin."""
    parts = []
    z0, ztip = S.FIN[0][0] * K, S.FIN[-1][0] * K
    zh = S.RUDDER_HORN_Z * K
    hz = S.RUDDER_Z[0] * K
    zr_top = ztip - 0.004
    hl, hh = S.RUDDER_HINGE_Y * K, -5.505 * K

    def zgrid(a, b, n, top_dense=False):
        if top_dense:
            return [a + (b - a) * math.sin(0.5 * math.pi * k / n) for k in range(n + 1)]
        return [a + (b - a) * k / n for k in range(n + 1)]

    # ---- fin: LE -> hinge gap; above the horn bottom the gap moves forward to the horn hinge
    mb = MeshBuf()
    rings = []
    for z in zgrid(z0, zh, 12):
        le, te, ht, _ = fin_station(z)
        rings.append(_fin_ring(z, le, hl + GAP, le, te, ht))
    ztop_fin = zh
    for k in range(1, 40):                     # the fin above the horn ends where its LE meets the horn hinge line
        z = zh + (ztip - zh) * k / 40
        le, te, ht, _ = fin_station(z)
        if le - (hh + GAP) < 0.012:
            break
        ztop_fin = z
    zs_up = [zh + 0.0005] + zgrid(zh + 0.0005, ztop_fin, 5)[1:]
    for z in zs_up:
        le, te, ht, _ = fin_station(z)
        rings.append(_fin_ring(z, le, hh + GAP, le, te, ht))
    loft(mb, rings, 'paint', closed=True, outward=True)
    section_close(mb, rings[-1], V((0, 0, 1)), 'paint')
    if OPEN_BREAKS:
        # r8o: open fin root (the fin detaches from fus_tail): dark band 15 mm, liner to 0.06 m, rib at 0.06 m, spar stub (no cap)
        def fin_ring_at(d):
            z = z0 + d
            le, te, ht, _ = fin_station(z)
            return _fin_ring(z, le, hl + GAP, le, te, ht)

        class _FinSt:                                         # Station-like (point(s, upper), cdir) on the fin section at height z
            def __init__(self, z):
                le, te, ht, _ = fin_station(z)
                self.z, self.le, self.ht, self.te = z, le, ht, te
                self.cdir = V((0, -1, 0))

            def point(self, s_, upper):
                y = self.le - s_ * (self.le - (hl + GAP))
                th = max(_fin_th(y, self.le, self.te, self.ht), 0.0012)
                return V(((th if upper else -th), y, self.z))
        ra = _RingAt(fin_ring_at, lambda d: _FinSt(z0 + d))
        rr0 = fin_ring_at(0.0)
        open_end(mb, ra, V((0, 0, -1)), section_pairs(len(rr0)), depth=STAB_ROOT_SETBACK, band=0.015, seed='fin', spar_stub=0.30,
                 close=TAIL_CAVITY)
    else:
        fan_cap(mb, rings[0], sum(rings[0], V()) / len(rings[0]), 'structure', V((0, 0, -1)))
    dorsal(mb)
    if FIN_GAP_WEB:
        # r8e (game r8d z_liv7_fin / liv6_fin: a bright white line down the rudder hinge with a step under the horn): the 10 mm hinge
        # gaps were open from side to side, so the sky showed through. A thin livery web on the centre plane fills them, from the fin's
        # cut into the rudder nose (4 mm behind the hinge line, inside the 22 mm nose): below the horn, under the horn, at the horn hinge.
        T_ = 0.0012
        for (ya, yb_, za, zb) in ((hl - 0.004, hl + GAP + 0.003, z0 + 0.002, zh + GAP + 0.002),
                                  (hh - 0.004, hl + GAP + 0.003, zh - 0.002, zh + GAP + 0.002),
                                  (hh - 0.004, hh + GAP + 0.003, zh, ztop_fin)):
            box(mb, (0.0, (ya + yb_) / 2, (za + zb) / 2), (T_, abs(yb_ - ya), abs(zb - za)), 'paint')
    parts.append(Part('fin', 'fus_tail', (0, -5.1, 0.8), mb))

    # ---- rudder: hinge -> TE below the horn, horn balance above it (forward to the horn hinge, then the true LE at the top)
    mb = MeshBuf()
    rings = []
    zb_h = zh + GAP                             # horizontal hinge gap under the horn
    for z in zgrid(hz, zb_h, 12):
        le, te, ht, _ = fin_station(z)
        rings.append(_fin_ring(z, hl, te, le, te, ht, nose=0.022))
    loft(mb, rings, 'paint', closed=True, outward=True)
    section_close(mb, rings[0], V((0, 0, -1)), 'paint')
    lower_top = rings[-1]
    rings = []
    for z in [zb_h] + zgrid(zb_h, zr_top, 10, top_dense=True)[1:]:
        le, te, ht, _ = fin_station(z)
        if le <= hh:
            rings.append(_fin_ring(z, le, te, le, te, ht))
        else:
            rings.append(_fin_ring(z, hh, te, le, te, ht, nose=0.022))
    loft(mb, rings, 'paint', closed=True, outward=True)
    section_close(mb, rings[0], V((0, 0, -1)), 'paint')
    top = sum(rings[-1], V()) / len(rings[-1]) + V((0, 0, 0.003))
    fan_cap(mb, rings[-1], top, 'paint', V((0, 0, 1)), uvfunc=lambda p: planar_uv(p, V((0, 0, 1))))
    # the lower rudder's top face at the horn root is covered by the horn's bottom face where they overlap; close it as structure
    section_close(mb, lower_top, V((0, 0, 1)), 'paint')
    parts.append(Part('rudder', 'fin', (0, S.RUDDER_HINGE_Y * K, hz), mb, frame=frame_x(V((0, 0, 1)), V((0, -1, 0))),
                      info=dict(kind='control', hinge_axis=(0.0, 0.0, 1.0))))
    return parts


def dorsal(mb):
    """dorsal fillet: a thin wedge from the turtle deck up to the fin LE at z 0.6 (body top line under it)."""
    pts = []
    for k in range(9):
        y = S.DORSAL[0][0] + (S.FIN[2][1] - S.DORSAL[0][0]) * k / 8
        yb = y * K
        zt = body_params(yb)[0]
        ztop = S.lin([(S.DORSAL[0][0], S.DORSAL[0][1]), (S.DORSAL[1][0], S.DORSAL[1][1]), (S.DORSAL[2][0], S.DORSAL[2][1]),
                      (S.FIN[2][1], S.FIN[2][0])], y) * K
        ztop = max(ztop, zt + 0.004)
        hw = 0.006 + 0.04 * k / 8
        pts.append((yb, zt - 0.02, ztop, hw))
    rings = []
    for yb, z0, z1, hw in pts:
        rings.append([V((hw, yb, z0)), V((hw * 0.6, yb, (z0 + z1) / 2)), V((0, yb, z1)), V((-hw * 0.6, yb, (z0 + z1) / 2)), V((-hw, yb, z0))])
    loft(mb, rings, 'paint', closed=True, outward=True)
    section_close(mb, rings[0], V((0, 1, 0)), 'paint')
    section_close(mb, rings[-1], V((0, -1, 0)), 'paint')


# =============================================================================================== landing gear
def retract_axis(side):
    """unit axis (built, right-hand rotation) and angle (deg) taking the down wheel centre to the up one about the pivot."""
    piv = P((side * S.MAIN_PIVOT[0], S.MAIN_PIVOT[1], S.MAIN_PIVOT[2]), plug=False)
    d = P((side * S.MAIN_WHEEL_DOWN[0], S.MAIN_WHEEL_DOWN[1], S.MAIN_WHEEL_DOWN[2]), plug=False) - piv
    u = P((side * S.MAIN_WHEEL_UP[0], S.MAIN_WHEEL_UP[1], S.MAIN_WHEEL_UP[2]), plug=False) - piv
    ax = d.cross(u).normalized()
    ang = math.degrees(math.acos(max(-1, min(1, d.normalized().dot(u.normalized())))))
    return piv, ax, ang


def bar(mb, a, b, w, h, up, mat):
    """rectangular bar from a to b (w across, h along `up`), centred on the a-b line."""
    a, b = V(a), V(b)
    d = b - a
    box(mb, (a + b) / 2, (d.length, w, h), mat, rot=frame_x(d, up))


def tyre_mesh(mb, centre, R, W, hub_r, axis=V((1, 0, 0)), N=32, detail=True):
    """r1b: balloon tyre (bead at the rim, sidewall bulging to the full width at ~45 % height, squarish crown) and a
    built-up wheel: rim with flanges, dished wheel disc each side, hub boss with a bolt circle and an axle cap.
    hub_r = rim (bead) radius."""
    ax = axis.normalized()
    ref = V((0, 0, 1)) if abs(ax.z) < 0.9 else V((0, 1, 0))
    u = (ref - ax * ref.dot(ax)).normalized()
    w = ax.cross(u)
    rim_r = hub_r
    b = W * 0.34                                   # bead half-width
    r0 = rim_r + 0.40 * (R - rim_r)                # widest section height
    half = []                                      # one sidewall: bead -> crown centre (r, axial >= 0)
    for k in range(7):
        ps = 0.5 * math.pi * k / 6
        half.append((rim_r + (r0 - rim_r) * math.sin(ps), b + (W / 2 - b) * math.sqrt(max(1 - math.cos(ps), 0.0))))
    for k in range(1, 9):
        th = 0.5 * math.pi * k / 8
        half.append((r0 + (R - r0) * math.sin(th), (W / 2) * math.cos(th) ** 0.85))   # round crown (gear sweep: a square crown hits the well roof)
    half[-1] = (R, 0.0)
    prof = [(r, -a) for r, a in half] + [(r, a) for r, a in reversed(half[:-1])]
    rings = []
    for k in range(N):
        phi = 2 * math.pi * k / N
        d = u * math.cos(phi) + w * math.sin(phi)
        rings.append([centre + d * r + ax * a for r, a in prof])
    loft(mb, rings + [rings[0]], 'rubber', closed=True, outward=True)
    cylinder(mb, centre - ax * (b + 0.004), centre + ax * (b + 0.004), rim_r + 0.002, N=28, mat='hub', ref=u)   # rim band (2 mm over the bead face)
    if not detail:
        cylinder(mb, centre + ax * (b + 0.004), centre + ax * (b + 0.012), rim_r * 0.5, N=16, mat='metal_dark', ref=u)
        cylinder(mb, centre - ax * (b + 0.012), centre - ax * (b + 0.004), rim_r * 0.5, N=16, mat='metal_dark', ref=u)
        return
    for s in (1, -1):
        o = centre + ax * s * (b + 0.004)
        # r1b gear sweep: everything stays inside the tyre's width (the stowed wheel lies flat under the well ceiling)
        cylinder(mb, o - ax * s * 0.006, o + ax * s * 0.006, rim_r + 0.013, N=28, mat='hub', ref=u)               # rim flange
        cylinder(mb, o + ax * s * 0.001, o - ax * s * 0.022, rim_r - 0.004, rim_r * 0.42, N=24, mat='hub', ref=u)  # disc dished inward
        cylinder(mb, o - ax * s * 0.026, o + ax * s * 0.010, rim_r * 0.30, rim_r * 0.26, N=16, mat='metal_dark', ref=u)   # hub boss
        for k in range(6):                                                                                        # bolt circle
            ph = 2 * math.pi * k / 6
            bp = o - ax * s * 0.014 + (u * math.cos(ph) + w * math.sin(ph)) * rim_r * 0.55
            cylinder(mb, bp, bp + ax * s * 0.012, 0.007, N=6, mat='metal_dark', ref=u)
        cylinder(mb, o + ax * s * 0.008, o + ax * s * 0.018, rim_r * 0.12, N=12, mat='chrome', ref=u)             # axle cap


def rot_about(p, piv, ax, deg):
    q = Quaternion(ax, math.radians(deg))
    return piv + q @ (V(p) - piv)


def build_gear():
    parts = []
    for side, L in ((1, 'R'), (-1, 'L')):
        piv, ax, ang = retract_axis(side)
        wc = P((side * S.MAIN_WHEEL_DOWN[0], S.MAIN_WHEEL_DOWN[1], S.MAIN_WHEEL_DOWN[2]), plug=False)
        R = S.WHEEL_D / 2 * K
        W = S.WHEEL_W * K
        # r1b: oleo leg OUTBOARD of the wheel (reference front view): trunnion head, black oleo cylinder with collars, gland nut,
        # chromed slider, scissor (torque) links fore of the leg, single-sided fork head with the stub axle through the wheel
        mb = MeshBuf()
        fork_x = wc.x + side * (W / 2 + 0.035)
        top = piv + V((0, 0, -0.02))
        knee = V((fork_x, wc.y, wc.z + 0.12))
        e = (knee - top).normalized()
        Lk = (knee - top).length
        fwd = V((0, 1, 0)) - e * e.y
        fwd.normalize()
        p_oleo = top + e * (Lk * 0.55)
        # round-6 polish item done in r5 (coordinator: the reference strut is ~1.5 x ours): fat black oleo with bright bands
        cylinder(mb, top - e * 0.02, p_oleo, 0.076, 0.072, N=20, mat='metal_dark')                 # oleo cylinder (black)
        for t_, r_, l_ in ((0.06, 0.082, 0.025), (0.20, 0.079, 0.014), (0.34, 0.079, 0.014), (Lk * 0.55 - 0.025, 0.080, 0.022)):
            c0 = top + e * t_
            cylinder(mb, c0, c0 + e * l_, r_, N=20, mat='alu')                                     # bands / gland nut
        cylinder(mb, p_oleo - e * 0.03, knee, 0.052, 0.052, N=18, mat='chrome')                     # chromed slider
        cylinder(mb, knee - e * 0.01, knee + e * 0.05, 0.062, 0.058, N=16, mat='metal_dark')        # fork head
        cylinder(mb, knee + e * 0.03, V((fork_x, wc.y, wc.z)), 0.036, 0.032, N=12, mat='gear')      # fork arm to the axle
        cylinder(mb, V((fork_x, wc.y, wc.z)) + V((side * 0.014, 0, 0)), V((wc.x + side * 0.02, wc.y, wc.z)), 0.024, N=12, mat='gear')   # stub axle
        cylinder(mb, V((fork_x, wc.y, wc.z)) + V((side * 0.010, 0, 0)), V((fork_x, wc.y, wc.z)) + V((side * 0.026, 0, 0)), 0.030, N=6, mat='metal_dark')   # axle nut
        cylinder(mb, piv - ax * 0.14, piv + ax * 0.14, 0.035, N=12, mat='gear')                   # trunnion (spans the leg groove into the wing)
        box(mb, top, (0.075, 0.075, 0.06), 'gear', rot=frame_x(ax, e))                              # trunnion head
        # scissor links: upper lug on the oleo, lower lug on the fork head, knee pin forward of the leg
        lu = top + e * (Lk * 0.42) + fwd * 0.085
        ll = knee + e * 0.02 + fwd * 0.070
        km = (lu + ll) / 2 + fwd * 0.080
        side_v = e.cross(fwd).normalized()
        for a_, b_ in ((lu, km), (km, ll)):
            bar(mb, a_, b_, 0.012, 0.030, side_v, 'gear')
        for p_ in (lu, km, ll):
            cylinder(mb, p_ - side_v * 0.018, p_ + side_v * 0.018, 0.008, N=8, mat='metal_dark')
        bar(mb, top + e * (Lk * 0.42), lu, 0.02, 0.02, side_v, 'gear')
        bar(mb, knee + e * 0.02, ll, 0.02, 0.02, side_v, 'gear')
        attach(f'gear_main_{L}_strut', piv + ax * 0.14, [f'wing_inner_{L}', 'wing_C'])
        # leg cover: built flush with the lower skin in the RETRACTED pose, then rotated with the leg into the down pose
        cover = leg_cover_up(side)
        cv = MeshBuf()
        for f in cover.faces:
            cv.face([cv.v(rot_about(cover.verts[i], piv, ax, -ang)) for i in f['idx']], f['mat'], f['uv'], f['smooth'])
        mb.extend(cv)
        parts.append(Part(f'gear_main_{L}_strut', f'wing_inner_{L}', piv, mb,
                          info=dict(kind='gear_leg', retract_axis_world=tuple(ax), retract_deg=ang, pivot=tuple(piv),
                                    wheel_up=tuple(P((side * S.MAIN_WHEEL_UP[0], S.MAIN_WHEEL_UP[1], S.MAIN_WHEEL_UP[2]), plug=False)))))
        wm = MeshBuf()
        tyre_mesh(wm, wc, R, W, 0.165, V((1, 0, 0)))
        parts.append(Part(f'gear_main_{L}_wheel', f'gear_main_{L}_strut', wc, wm, info=dict(kind='wheel', radius=R, spin_axis_local='+X')))
        # inner well door: hinged on a fore-aft line near the centreline; modelled OPEN (gear down)
        dm, hinge_p, hinge_ax = inner_door(side)
        parts.append(Part(f'gear_door_{L}', 'wing_C', hinge_p, dm, frame=frame_x(hinge_ax),
                          info=dict(kind='gear_door', hinge_axis=tuple(hinge_ax), open_deg=S.INNER_DOOR_OPEN)))
    # tail wheel: fork arm from the pivot to the axle (down, fixed in round 1), wheel
    piv = P(S.TAIL_PIVOT, plug=False)
    tc = P(S.TAIL_WHEEL_DOWN, plug=False)
    mb = MeshBuf()
    cylinder(mb, piv, tc + V((0, 0.0, 0.05)), 0.022, 0.018, N=10, mat='gear')
    for s_ in (1, -1):
        cylinder(mb, tc + V((0, 0, 0.05)) + V((s_ * 0.042, 0, 0)), tc + V((s_ * 0.042, 0, 0)), 0.010, N=8, mat='gear')
    cylinder(mb, tc + V((-0.046, 0, 0)), tc + V((0.046, 0, 0)), 0.008, N=8, mat='gear')
    box(mb, (0, piv.y - 0.03, piv.z + 0.01), (0.07, 0.10, 0.05), 'gear')
    attach('gear_tail_strut', piv, ['fus_tail'])
    parts.append(Part('gear_tail_strut', 'fus_tail', piv, mb, info=dict(kind='gear_leg', note='fixed down in round 1 (semi-retraction visual not driven)')))
    wm = MeshBuf()
    tyre_mesh(wm, tc, S.TAIL_WHEEL_D / 2 * K, S.TAIL_WHEEL_W * K, 0.035, V((1, 0, 0)), N=24, detail=False)
    parts.append(Part('gear_tail_wheel', 'gear_tail_strut', tc, wm, info=dict(kind='wheel', radius=S.TAIL_WHEEL_D / 2 * K)))
    return parts


def _seg_in_poly(poly, a, b):
    """parts of the plan segment a-b inside poly (pairs of points)."""
    ts = []
    n = len(poly)
    d = b - a
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        e = q - p
        den = d.x * e.y - d.y * e.x
        if abs(den) < 1e-12:
            continue
        t = ((p.x - a.x) * e.y - (p.y - a.y) * e.x) / den
        s = ((p.x - a.x) * d.y - (p.y - a.y) * d.x) / den
        if 0 <= t <= 1 and 0 <= s <= 1:
            ts.append(t)
    ts = sorted(set(round(t, 9) for t in ts))
    out = []
    for i in range(0, len(ts) - 1, 2):
        out.append((a + d * ts[i], a + d * ts[i + 1]))
    return out


def _dist_to_poly(poly, p):
    best = 1e9
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ab = b - a
        L2 = ab.x * ab.x + ab.y * ab.y
        t = 0.0 if L2 < 1e-14 else max(0.0, min(1.0, ((p.x - a.x) * ab.x + (p.y - a.y) * ab.y) / L2))
        dx, dy = p.x - (a.x + ab.x * t), p.y - (a.y + ab.y * t)
        best = min(best, math.hypot(dx, dy))
    return best


def _resample(poly, step):
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        m = max(1, int(math.ceil((b - a).length / step)))
        for k in range(m):
            out.append(a + (b - a) * (k / m))
    return out


def _plate(outline_xy, side, mat_out='paint', proud=0.006, thick=0.007, bulge=0.006, lip=0.016, ribs=(), rib_h=0.012,
           dome=None, roll=0.045, rim_mat='well'):
    """r1b: pressed panel over a plan polygon (constrained Delaunay mesh), flush with the lower skin at its edge: the outer
    face (paint, faces down) rolls `bulge` out over `roll` from the edge (a rounded edge, no flat slab) plus an optional
    dome(p) (m, outward), the inner face (well) sits `thick` above it with a `lip` deep flange round the edge, and `ribs`
    (plan segments) are stiffeners on the inner face. Built in the closed pose."""
    from mathutils.geometry import delaunay_2d_cdt
    from mathutils import Vector as V2
    mb = MeshBuf()
    poly = [V((p.x, p.y, 0)) for p in outline_xy]
    if _signed_area(poly) < 0:
        poly = list(reversed(poly))
    bnd = _resample(poly, 0.010)
    xs = [p.x for p in poly]
    ys = [p.y for p in poly]
    pts = [V2((p.x, p.y)) for p in bnd]
    g = 0.018
    nx, ny = int((max(xs) - min(xs)) / g) + 1, int((max(ys) - min(ys)) / g) + 1
    for i in range(nx + 1):
        for j in range(ny + 1):
            q = V((min(xs) + i * g + (0.5 * g if j % 2 else 0.0), min(ys) + j * g, 0))
            if _pip(poly, q.x, q.y) and _dist_to_poly(poly, q) > 0.006:
                pts.append(V2((q.x, q.y)))
    nb = len(bnd)
    edges = [(i, (i + 1) % nb) for i in range(nb)]
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(pts, edges, [list(range(nb))], 1, 1e-7)
    P3 = [V((v.x, v.y, 0)) for v in vs]
    dist = [_dist_to_poly(poly, p) for p in P3]

    def zo(p, d):
        z = lower_z(p.x, p.y) - proud - bulge * math.sin(0.5 * math.pi * min(d / roll, 1.0))
        return z - (dome(p) if dome else 0.0)

    def tk(d):
        return thick + (lip - thick) * max(0.0, 1.0 - d / 0.010)

    def uvd(q):
        return [planar_uv(p, V((0, 0, -1))) for p in q] if mat_out == 'paint' else None
    O = [V((p.x, p.y, zo(p, d))) for p, d in zip(P3, dist)]
    I = [V((p.x, p.y, zo(p, d) + tk(d))) for p, d in zip(P3, dist)]
    ecount = {}
    for f in fs:
        q = [O[i] for i in f]
        oriented_quad(mb, q, mat_out, V((0, 0, -1)), uvd(q), smooth=True)
        oriented_quad(mb, [I[i] for i in f], 'well', V((0, 0, 1)), smooth=True)
        for k in range(len(f)):
            key = tuple(sorted((f[k], f[(k + 1) % len(f)])))
            ecount[key] = ecount.get(key, 0) + 1
    for f in fs:
        fc = sum((P3[i] for i in f), V()) / len(f)
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            if ecount[tuple(sorted((a, b)))] != 1:
                continue
            mid = (P3[a] + P3[b]) / 2
            q_ = [O[a], O[b], I[b], I[a]]
            tw_ = V((mid.x - fc.x, mid.y - fc.y, 0))
            oriented_quad(mb, q_, rim_mat, tw_, [planar_uv(x, tw_) for x in q_] if rim_mat == 'paint' else None)
    for a, b in ribs:
        for p0, p1 in _seg_in_poly(poly, V((a[0], a[1], 0)), V((b[0], b[1], 0))):
            dv = p1 - p0
            if dv.length < 0.06:
                continue
            p0, p1 = p0 + dv.normalized() * 0.014, p1 - dv.normalized() * 0.014     # stop on the flange
            m = (p0 + p1) / 2
            zb = max(zo(q, _dist_to_poly(poly, q)) + tk(_dist_to_poly(poly, q)) for q in (p0, m, p1)) - 0.002
            bar(mb, V((p0.x, p0.y, zb + rib_h / 2)), V((p1.x, p1.y, zb + rib_h / 2)), 0.006, rib_h, V((0, 0, 1)), 'well')
    return mb


def leg_cover_up(side):
    """leg cover in the RETRACTED pose: outboard half of the well + the leg slot, flush at its edge, pressed outward,
    a flange round the edge and stiffeners across the wheel disc and along the leg strip (inner face)."""
    a, c = slot_axis(side)
    e = (a - c).normalized()
    pe = V((-e.y, e.x, 0))
    R = S.WELL_R * K + COVER_LAP     # r8k: 1.5 mm inside the opening (was 4 mm: a ring of aotake hairline round each closed well)
    ribs = []
    for off in (-0.16, -0.06, 0.06, 0.16):              # across the wheel disc, square to the leg line
        p = c + pe * off
        q0, q1 = p - e * R, p + e * R
        ribs.append(((q0.x, q0.y), (q1.x, q1.y)))
    ribs.append((((c + e * 0.05).x, (c + e * 0.05).y), ((a - e * 0.05).x, (a - e * 0.05).y)))   # along the leg strip
    dome = lambda p: 0.018 * max(0.0, 1.0 - ((p.x - c.x) ** 2 + (p.y - c.y) ** 2) / (R * R))      # pressed out over the wheel
    # r8j (in game r8i: a teal sliver under the LE root): the cover stands 5.5 mm proud of the skin, so its edge band shows from outside
    # with the gear up; it was aotake ('well') and read as sky through a gap. Edge band in the cover's paint now (COVER_RIM_PAINT).
    return _plate(opening_outline(side, R=R, half='out', w=SLOT_W - 0.006), side, proud=0.0055, bulge=0.004, ribs=ribs, dome=dome,
                  rim_mat='paint' if COVER_RIM_PAINT else 'well')


COVER_RIM_PAINT = True
COVER_LAP = -0.0015    # r8k: cover / door radius vs the well opening (r8j -0.004: an aotake hairline ring; +0.002 put the 16 mm edge flange through the skin, gear sweep)


def inner_door(side):
    """inner well door: circle segment between the hinge line (x 0.09) and the split line, a pressed panel with a flange,
    two stiffeners along the hinge line, one across, and hinge knuckles; modelled OPEN (gear down)."""
    c = well_centre(side)
    R = S.WELL_R * K + COVER_LAP     # r8k: 1.5 mm inside the opening (was 4 mm: a ring of aotake hairline round each closed well)
    xh = side * (S.INNER_DOOR_HINGE_X * K + 0.004)
    dx = abs(c.x - xh)
    h = math.sqrt(max(R * R - dx * dx, 0.0))
    xs_ = door_split_x(side)                                   # r1 overlay: the door is 0.23 m wide (hinge .. split line)
    hs = math.sqrt(max(R * R - (xs_ - c.x) ** 2, 0.0))
    pts = [V((xh, c.y - h, 0)), V((xh, c.y + h, 0))] + split_curve(side, c, R)    # r6: bowed free edge (reference outline)
    for k in range(64):
        ang = 2 * math.pi * k / 64
        p = c + V((math.cos(ang), math.sin(ang), 0)) * R
        if (p.x - xh) * side > 1e-6 and (xs_ - p.x) * side > 1e-6:
            pts.append(p)
    cen = sum(pts, V()) / len(pts)
    poly = sorted(pts, key=lambda p: math.atan2(p.y - cen.y, p.x - cen.x))
    ribs = [((xh + side * 0.07, c.y - R), (xh + side * 0.07, c.y + R)), ((xh + side * 0.16, c.y - R), (xh + side * 0.16, c.y + R)),
            ((xh, c.y), (xs_, c.y))]
    span_ = abs(xs_ - xh)
    dome = lambda p: S.DOOR_DOME * math.sin(math.pi * min(max(abs(p.x - xh) / span_, 0.0), 1.0)) * max(0.0, 1.0 - ((p.y - c.y) / R) ** 2)
    mb = _plate(poly, side, proud=0.0055, thick=0.007, bulge=0.004, ribs=ribs, rib_h=0.010, dome=dome, roll=0.030)
    for f in mb.faces:                         # r8b (critique: teal 'fin' under the root): the open door shows its inner face from
        if f['mat'] == 'well':                 # outboard; paint both faces (WT doors read grey from outside)
            q = [mb.verts[i] for i in f['idx']]
            n_ = (q[1] - q[0]).cross(q[2] - q[0])
            f['mat'] = 'paint'; f['uv'] = [planar_uv(x, n_) for x in q]
    hinge_p = V((xh, c.y, lower_z(xh, c.y) - 0.0055))
    hz = hinge_p.z + 0.012
    for y0, y1 in ((c.y - h * 0.8, c.y - h * 0.35), (c.y + h * 0.35, c.y + h * 0.8)):   # hinge knuckles on the inner face
        cylinder(mb, V((xh + side * 0.012, y0, hz)), V((xh + side * 0.012, y1, hz)), 0.008, N=8, mat='gear')
    ax = V((0, 1, 0))
    for sgn in (1, -1):                        # pick the sense that swings the free edge DOWN
        o = MeshBuf()
        for f in mb.faces:
            o.face([o.v(rot_about(mb.verts[i], hinge_p, ax, sgn * S.INNER_DOOR_OPEN)) for i in f['idx']], f['mat'], f['uv'], f['smooth'])
        if (sum(o.verts, V()) / len(o.verts)).z < hinge_p.z:
            return o, hinge_p, ax * sgn
    return mb, hinge_p, ax


# =============================================================================================== hook
def build_hook():
    """A-frame-like single arm with the hook tip, lying aft along the belly (stowed visible), pivot (0, -4.536, -0.26)."""
    piv = P(S.HOOK_PIVOT, plug=False)
    L = S.HOOK_LEN * K
    mb = MeshBuf()
    d = V((0, -1, 0)).normalized()
    # stowed: rotated up by HOOK_STOW_DEG about +x (tip up)
    q = Quaternion(V((1, 0, 0)), math.radians(-S.HOOK_STOW_DEG))
    dd = q @ d
    tip = piv + dd * L
    for s_ in (1, -1):                                          # two arms joining at the tip (A-frame)
        a = piv + V((s_ * 0.045, 0, 0))
        cylinder(mb, a, tip + V((s_ * 0.008, 0, 0.004)), 0.012, 0.010, N=8, mat='hook')
    cylinder(mb, piv - V((0.06, 0, 0)), piv + V((0.06, 0, 0)), 0.014, N=8, mat='hook')
    hook_tip = tip + dd * 0.05 + V((0, 0, -0.035))
    cylinder(mb, tip, hook_tip, 0.016, 0.012, N=8, mat='hookyellow')
    attach('tailhook', piv + V((0.06, 0, 0)), ['fus_tail', 'fus_rear'])     # the hinge axle ends on the hook slot's side walls
    return [Part('tailhook', 'fus_tail', piv, mb, info=dict(kind='tailhook', length=L, stowed_up_deg=S.HOOK_STOW_DEG,
                                                             deployed_deg=S.HOOK_STOW_DEG - S.HOOK_DOWN_DEG)),
            Part('hp_tailhook', 'fus_tail', piv, None, info=dict(kind='hardpoint'))]


# =============================================================================================== prop
def build_prop():
    parts = []
    zc = 0.0
    hub = V((0, S.PROP_PLANE_Y * K, zc))
    mb = MeshBuf()
    prof = [(y * K, r * K) for y, r in S.SPINNER]
    N = 36
    rings = []
    for y, r in prof[:-1]:
        rings.append(circle_pts(V((0, y, zc)), V((0, 1, 0)), r, N, ref=V((0, 0, 1))))
    loft(mb, rings, 'spinner', closed=True, outward=True)
    tip = V((0, prof[-1][0], zc))
    fan_cap(mb, rings[-1], tip, 'spinner', V((0, 1, 0)))
    fan_cap(mb, rings[0], V((0, prof[0][0], zc)), 'metal_dark', V((0, -1, 0)))       # back plate (faces aft, on the nose case)
    parts.append(Part('prop_hub', 'prop', hub, mb, info=dict(kind='prop_hub', note='spin axis = Unity +Z; spinner')))
    fwd = V((0, 1, 0))
    for k in range(3):
        a = math.pi + 2 * math.pi * k / 3          # blade 0 straight down (reference parked pose)
        rad = V((math.sin(a), 0, math.cos(a)))
        tang = fwd.cross(rad).normalized()
        bm = MeshBuf()
        rings = []
        for r, chord, tc, beta in S.BLADE:
            rb = r * K
            chord = chord * K
            th = math.radians(beta)
            cdir = (tang * math.cos(th) - fwd * math.sin(th)).normalized()      # chord line LE -> TE
            up = cdir.cross(rad).normalized()
            if up.dot(fwd) < 0:
                up = -up
            c0 = hub + rad * rb - cdir * chord * 0.35
            st = Station(rb, c0, cdir, up, max(chord, 0.004), min(tc, 0.4), m=0.03)
            ss = [0.5 * (1 - math.cos(math.pi * j / 10)) for j in range(11)]
            upp = [st.point(s, True) for s in reversed(ss)]
            low = [st.point(s, False) for s in ss[1:-1]]
            rings.append(upp + low)
        loft(bm, rings, 'prop', closed=True, outward=True)
        fan_cap(bm, rings[0], sum(rings[0], V()) / len(rings[0]), 'prop', -rad)
        fan_cap(bm, rings[-1], sum(rings[-1], V()) / len(rings[-1]), 'prop', rad)
        parts.append(Part(f'prop_blade_{k}', 'prop_hub', hub, bm, frame=frame_x(tang, rad),
                          info=dict(kind='prop_blade', note='ONE renderer, material prop; local +Y (Unity) = radial')))
    return parts


# =============================================================================================== details
def build_details():
    parts = []
    # Type 99 cannon barrels proud of the LE + fairing, on wing_inner
    for side, L in ((1, 'R'), (-1, 'L')):
        m = P((side * S.TYPE99_MUZZLE[0], S.TYPE99_MUZZLE[1], S.TYPE99_MUZZLE[2]), plug=False)
        mb = MeshBuf()
        tipp = m + V((0, S.TYPE99_BARREL_PROUD * K, 0))
        cylinder(mb, m - V((0, 0.10, 0)), m + V((0, 0.03, 0)), 0.036, 0.030, N=14, mat='paint')      # LE blast fairing
        cylinder(mb, m, tipp, 0.021, 0.018, N=12, mat='gunmetal')
        from b25h_geom import tube
        tube(mb, tipp - V((0, 0.03, 0)), tipp + V((0, 0.005, 0)), 0.022, 0.011, N=12, mat='gunmetal')
        attach(f'cannon_{L}', m - V((0, 0.10, 0)), [f'wing_inner_{L}'])
        parts.append(Part(f'cannon_{L}', f'wing_inner_{L}', m, mb, info=dict(kind='gun_barrel')))
        # round 2: the 60 kg rack is part of the bomb mount (build_stores; shown only with bombs fitted)
        parts.append(Part(f'hp_bomb_{L}', f'wing_inner_{L}', P((side * S.RACK_HANG[0], S.RACK_HANG[1], S.RACK_HANG[2]), plug=False), None,
                          info=dict(kind='hardpoint')))
        parts.append(Part(f'muzzle_cannon_{L}', f'wing_inner_{L}', V((m.x, S.TYPE99_BULLET_Y * K, m.z)), None, info=dict(kind='muzzle')))
        parts.append(Part(f'flash_cannon_{L}', f'wing_inner_{L}', tipp, None, info=dict(kind='muzzle_flash')))
        parts.append(Part(f'cannon_body_{L}', f'wing_inner_{L}', P((side * S.TYPE99_BODY[0], S.TYPE99_BODY[1], S.TYPE99_BODY[2]), plug=False), None,
                          info=dict(kind='gun_hp')))
        mm = P((side * S.TYPE97_MUZZLE[0], S.TYPE97_MUZZLE[1], S.TYPE97_MUZZLE[2]), plug=False)
        parts.append(Part(f'muzzle_gun_{L}', 'fus_engine', V((mm.x, S.TYPE97_BULLET_Y * K, mm.z)), None, info=dict(kind='muzzle')))
        parts.append(Part(f'flash_gun_{L}', 'fus_engine', mm + V((0, 0.012, 0)), None, info=dict(kind='muzzle_flash')))
    # pitot (left wing, on wing_mid)
    x, (ya, yb_), z = S.PITOT
    a = P((x, ya, z))
    b = P((x, yb_, z))
    stp = wing_station(abs(a.x), -1)
    le = stp.le
    mb = MeshBuf()
    cylinder(mb, V((a.x, le.y - 0.05, le.z + 0.01)), a + V((0, 0, 0)), 0.010, N=8, mat='gear')
    cylinder(mb, a, b, 0.008, N=8, mat='chrome')
    attach('pitot', V((a.x, le.y - 0.05, le.z + 0.01)), ['wing_tip_L', 'wing_mid_L'])
    parts.append(Part('pitot', 'wing_tip_L', a, mb))          # x 4.89 built: outboard of the mid / tip break (4.86)
    # aerial mast + wire
    mb = MeshBuf()
    mbase, mtop = P(S.MAST_BASE, plug=False), P(S.MAST_TOP, plug=False)
    # r1b: tapered aerofoil mast (symmetric NACA 00xx sections, chord 75 -> 25 mm, LE forward), standing on the turtle deck
    # inside the rear glazing as in the reference side view; the rake stays FORWARD (reference side view: top ahead of the base)
    mbase = V((0, mbase.y, body_params(mbase.y)[0] - 0.012))
    nseg = 10
    rings_m = []
    for k in range(nseg + 1):
        t = k / nseg
        cpt = mbase + (mtop - mbase) * t
        ch = 0.075 + (0.025 - 0.075) * t
        tcm = 0.22 + 0.08 * t
        ring = []
        nn = 8
        for q in range(nn + 1):
            sx = 0.5 * (1 - math.cos(math.pi * q / nn))
            hth = 5 * tcm * ch * (0.2969 * math.sqrt(sx) - 0.126 * sx - 0.3516 * sx * sx + 0.2843 * sx ** 3 - 0.1036 * sx ** 4)
            ring.append(V((max(hth, 0.0008), cpt.y + ch * 0.4 - sx * ch, cpt.z)))
        ring = ring + [V((-p_.x, p_.y, p_.z)) for p_ in reversed(ring[1:-1])]
        rings_m.append(ring)
    loft(mb, rings_m, 'paint', closed=True, outward=True)
    fan_cap(mb, rings_m[0], sum(rings_m[0], V()) / len(rings_m[0]), 'paint', V((0, 0, -1)))
    fan_cap(mb, rings_m[-1], sum(rings_m[-1], V()) / len(rings_m[-1]) + V((0, 0, 0.004)), 'paint', V((0, 0, 1)))
    wf = P(S.WIRE_FIN, plug=False)
    cylinder(mb, mtop, wf, 0.0025, N=5, mat='wire')
    attach('aerial', mbase, ['fus_center', 'canopy_rear'])
    attach('aerial_wire', wf, ['rudder', 'fin'])
    parts.append(Part('aerial', 'fus_center', mbase, mb))
    # empties
    parts.append(Part('cockpit_eye', 'fus_center', P(S.EYE, plug=False), None, info=dict(kind='eye')))
    parts.append(Part('exhaust_point', 'fus_engine', P((0.29, 1.062, -0.59), plug=False), None, info=dict(kind='ir_source')))
    parts.append(Part('hp_special', 'fus_center', P(S.SPECIAL_HANG, plug=False), None, info=dict(kind='hardpoint', note='round 3')))
    return parts


# =============================================================================================== stores (round 2 / 3)
def _revolve(mb, nose, profile, fins, mat, band=None, N=24):
    """body of revolution along -y from `nose` (profile = (distance, radius)), closed at both ends; cruciform fins with a box-tail ring;
    an optional coloured nose band (distance from, to)."""
    rings = []
    ax = V((0, -1, 0))
    for d, r in profile:
        c = nose + ax * d
        rings.append(circle_pts(c, ax, max(r, 0.0005), N, ref=V((0, 0, 1))))
    loft(mb, rings, mat, closed=True, outward=True)
    fan_cap(mb, rings[0], nose, mat, -ax)
    fan_cap(mb, rings[-1], nose + ax * profile[-1][0], mat, ax)
    f0, f1, rt = fins
    rbody = S.lin(profile, (f0 + f1) / 2, 1)
    for k in range(4):                                      # fins at 45 deg (X tail, clear of the rack above)
        a = math.pi / 4 + k * math.pi / 2
        d = V((math.cos(a), 0, math.sin(a)))
        nrm = V((-math.sin(a), 0, math.cos(a)))
        y0, y1 = (nose + ax * f0).y, (nose + ax * f1).y
        r0 = S.lin(profile, f0, 1) * 0.8
        q = [V((0, y0, 0)) + d * r0, V((0, y1, 0)) + d * min(rbody, 0.05), V((0, y1, 0)) + d * rt, V((0, y0 + (y1 - y0) * 0.45, 0)) + d * rt]
        q = [p + V((nose.x, 0, nose.z)) for p in q]
        t = 0.003
        top = [p + nrm * t for p in q]; bot = [p - nrm * t for p in q]
        oriented_quad(mb, top, mat, nrm); oriented_quad(mb, bot, mat, -nrm)
        for i in range(4):
            j = (i + 1) % 4
            mid = (q[i] + q[j]) / 2; cen = sum(q, V()) / 4
            oriented_quad(mb, [top[i], top[j], bot[j], bot[i]], mat, mid - cen)
    # box-tail ring at the fin tips (a thin tube)
    ya, yb = (nose + ax * (f1 - 0.11)).y, (nose + ax * f1).y
    c0, c1 = V((nose.x, ya, nose.z)), V((nose.x, yb, nose.z))
    ro, ri = rt + 0.004, rt - 0.002
    o0, o1 = circle_pts(c0, ax, ro, N, ref=V((0, 0, 1))), circle_pts(c1, ax, ro, N, ref=V((0, 0, 1)))
    i0, i1 = circle_pts(c0, ax, ri, N, ref=V((0, 0, 1))), circle_pts(c1, ax, ri, N, ref=V((0, 0, 1)))
    loft(mb, [o0, o1], mat, closed=True, outward=True)
    loft(mb, [i0, i1], mat, closed=True, outward=False)
    annulus(mb, o0, i0, mat, -ax); annulus(mb, o1, i1, mat, ax)
    if band:
        b0, b1 = band
        ro_ = [circle_pts(nose + ax * d, ax, S.lin(profile, d, 1) + 0.0015, N, ref=V((0, 0, 1))) for d in (b0, b1)]
        ri_ = [circle_pts(nose + ax * d, ax, S.lin(profile, d, 1) - 0.003, N, ref=V((0, 0, 1))) for d in (b0, b1)]
        loft(mb, ro_, 'bombband', closed=True, outward=True)
        loft(mb, ri_, 'bombband', closed=True, outward=False)
        annulus(mb, ro_[0], ri_[0], 'bombband', -ax); annulus(mb, ro_[1], ri_[1], 'bombband', ax)


def _rack(mb, hang, length, width, top_z_fn, braces, mat='gear'):
    """our own rack: a beam from the skin (buried 10 mm) down to the hang point, a shackle block with two lugs, and sway-brace pairs
    reaching down to the store's shoulders. braces = (store radius, brace y offsets)."""
    zt = max(top_z_fn(hang.x, hang.y + dy) for dy in (-length / 2, 0.0, length / 2)) + 0.010
    h = zt - hang.z
    box(mb, (hang.x, hang.y, hang.z + h / 2 + 0.02), (width, length, h - 0.04), mat)                      # beam
    box(mb, (hang.x, hang.y, hang.z + 0.025), (width * 0.8, 0.22, 0.05), 'metal_dark')                    # shackle block
    for dy in (-0.07, 0.07):
        box(mb, (hang.x, hang.y + dy, hang.z + 0.004), (0.012, 0.03, 0.012), 'metal_dark')                # suspension lugs
    rs, offs = braces
    for dy in offs:
        for sx in (-1, 1):
            a = V((hang.x + sx * width * 0.5, hang.y + dy, hang.z + 0.03))
            b = V((hang.x + sx * rs * 0.62, hang.y + dy, hang.z - rs * 0.25))
            cylinder(mb, a, b, 0.008, N=6, mat='metal_dark')
            box(mb, b + V((0, 0, -0.004)), (0.03, 0.03, 0.008), 'metal_dark')                                # brace pad


def build_stores():
    """round 2 / 3 stores, modelled ONCE at the right-hand / centre hardpoint (A6M2Build moves them into the mount prefabs and deletes
    them from the aircraft): 60 kg No.6 bomb + its wing rack, 250 kg charge + the centre rack. Pivots: bomb = its own centre (the
    capsule centre, Nimrod 1.4.0 airburst lesson), rack = the hang point (= the hardpoint)."""
    parts = []
    hang = P((S.RACK_HANG[0], S.RACK_HANG[1], S.RACK_HANG[2]), plug=False)
    r6 = max(r for _, r in S.NO6_PROFILE)
    L6 = S.NO6_PROFILE[-1][0]
    centre = hang + V((0, 0, -r6 - 0.002))
    mb = MeshBuf()
    _revolve(mb, centre + V((0, L6 / 2, 0)), S.NO6_PROFILE, S.NO6_FINS, 'bomb', band=(0.20, 0.235))
    box(mb, (centre.x, centre.y, centre.z + r6 - 0.006), (0.02, 0.18, 0.016), 'metal_dark')                # lug strap
    parts.append(Part('store_no6_bomb', 'wing_inner_R', centre, mb, info=dict(kind='store', length=L6, radius=r6, mass=S.NO6_MASS)))
    mb = MeshBuf()
    _rack(mb, hang, S.NO6_RACK_LEN, 0.05, lower_z, (r6, (-0.22, 0.22)))
    parts.append(Part('store_no6_rack', 'wing_inner_R', hang, mb, info=dict(kind='store_rack')))
    sh = P(S.SPECIAL_HANG, plug=False)
    rt = max(r for _, r in S.TOKKO_PROFILE)
    Lt = S.TOKKO_PROFILE[-1][0]
    ct = sh + V((0, 0, -rt - 0.002))
    mb = MeshBuf()
    _revolve(mb, ct + V((0, Lt / 2, 0)), S.TOKKO_PROFILE, S.TOKKO_FINS, 'bomb', band=(0.30, 0.36))
    box(mb, (ct.x, ct.y, ct.z + rt - 0.006), (0.03, 0.30, 0.016), 'metal_dark')
    parts.append(Part('store_tokko_bomb', 'fus_center', ct, mb, info=dict(kind='store', length=Lt, radius=rt, mass=S.TOKKO_MASS)))
    mb = MeshBuf()
    _rack(mb, sh, S.CENTRE_RACK_LEN, 0.10, lambda x, y: lower_z(0.0, y), (rt, (-0.30, 0.30)))
    parts.append(Part('store_tokko_rack', 'fus_center', sh, mb, info=dict(kind='store_rack')))
    return parts


def build_exterior():
    ATTACH.clear()
    parts = build_fuselage()
    import a6m2_canopy
    parts += a6m2_canopy.build_canopy()       # r8: framed glasshouse, mitred continuous frames, exterior + cockpit-view sets
    parts += build_wings()
    parts += build_tail()
    parts += build_gear()
    parts += build_hook()
    parts.insert(1, Part('prop', 'fus_engine', (0, S.PROP_PLANE_Y * K, 0), None, info=dict(kind='prop_part')))
    parts += build_prop()
    parts += build_details()
    parts += build_stores()                 # round 2 / 3: moved into the mount prefabs by A6M2Build
    import a6m2_cockpit
    parts += a6m2_cockpit.build_cockpit()   # round 4
    import a6m2_internals
    a6m2_internals.add(parts)               # round 5: spars, ribs, tanks, frames, firewall, oil tank (structure)
    return parts


# =============================================================================================== r8l well interior detail
WELL_DETAIL = True
WELL_RING_R = 0.60          # ring rib radius (x WELL_R)
WELL_RIB_W, WELL_RIB_D = 0.012, 0.014     # ring rib width / depth below the ceiling (m)
WELL_RAD_N, WELL_RAD_W, WELL_RAD_D = 8, 0.010, 0.012   # radial ribs: count, width, depth
WELL_LIP_Z, WELL_LIP_IN, WELL_LIP_T = 0.030, 0.008, 0.005   # rim lip: height over the lower skin, inward reach, thickness
WELL_BURY = 0.003           # ribs start this far above the ceiling (buried) so they read as joined


def well_detail_segments(side):
    """r8l (coordinator: our wells were flat teal cups; WT: domed well with radial and ring ribs, a rim ledge and dark recesses): the
    detail of one well as bar segments (p0, p1, width, height, up, kind) in built coordinates - a ring rib, WELL_RAD_N radial ribs and
    a lip round the round wall. build_a6m2.well_detail drops any segment that the main leg / wheel would touch at any retraction step,
    so the ribs clear the stowed tyre (it sits within 3 mm of the ceiling at 0.6-0.8 R)."""
    c = well_centre(side)
    R = S.WELL_R * K
    a, _ = slot_axis(side)
    e = (a - c).normalized()
    te = math.atan2(e.y, e.x)
    dl = math.asin(min(SLOT_W / R, 0.99)) + 0.06
    xc_ = S.INNER_DOOR_HINGE_X * K + 0.004 - WELL_CLIP_IN
    zce = upper_z(c.x, c.y) - WELL_CEIL - 0.012

    def zc(p):
        return min(zce, upper_z(p.x, p.y) - WELL_CEIL - 0.012)

    def inside(p, m):
        return (V((p.x, p.y, 0)) - c).length <= R - m and side * p.x >= xc_ + m

    def in_slot(ang):
        return abs((ang - te + math.pi) % (2 * math.pi) - math.pi) < dl
    up = V((0, 0, 1))
    seg = []

    def rib(p0, p1, w, d, kind):
        q0, q1 = V((p0.x, p0.y, 0)), V((p1.x, p1.y, 0))
        if not (inside(q0, w) and inside(q1, w)):
            return
        z0, z1 = zc(q0) + WELL_BURY - (d + WELL_BURY) / 2, zc(q1) + WELL_BURY - (d + WELL_BURY) / 2
        seg.append((V((q0.x, q0.y, z0)), V((q1.x, q1.y, z1)), w, d + WELL_BURY, up, kind))
    n = 40                                                      # ring rib
    rr = WELL_RING_R * R
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        rib(c + V((math.cos(a0), math.sin(a0), 0)) * rr, c + V((math.cos(a1), math.sin(a1), 0)) * rr, WELL_RIB_W, WELL_RIB_D, 'ring')
    for k in range(WELL_RAD_N):                                 # radial ribs, 40 mm pieces, from the hub disc to the wall
        ang = te + math.pi / WELL_RAD_N + 2 * math.pi * k / WELL_RAD_N
        d_ = V((math.cos(ang), math.sin(ang), 0))
        r = 0.16 * R
        while r < R - 0.02:
            r1 = min(r + 0.04, R - 0.012)
            rib(c + d_ * r, c + d_ * r1, WELL_RAD_W, WELL_RAD_D, 'radial')
            r = r1
    m = 48                                                      # lip round the round wall (not across the leg slot / the straight inboard edge)
    rl = R - WELL_LIP_IN / 2
    for k in range(m):
        a0, a1 = 2 * math.pi * k / m, 2 * math.pi * (k + 1) / m
        if in_slot(a0) or in_slot(a1):
            continue
        p0, p1 = c + V((math.cos(a0), math.sin(a0), 0)) * rl, c + V((math.cos(a1), math.sin(a1), 0)) * rl
        if side * p0.x < xc_ + 0.02 or side * p1.x < xc_ + 0.02:
            continue
        z0, z1 = lower_z(p0.x, p0.y) + WELL_LIP_Z, lower_z(p1.x, p1.y) + WELL_LIP_Z
        # radial extent = the lip's inward reach + 3 mm into the wall
        seg.append((V((p0.x, p0.y, z0)), V((p1.x, p1.y, z1)), WELL_LIP_IN + 0.006, WELL_LIP_T, up, 'lip'))
    return seg
