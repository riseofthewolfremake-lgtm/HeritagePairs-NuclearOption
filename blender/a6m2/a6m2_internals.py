"""A6M2 round 5 internals (design 7.3; stock aircraft_structure look in Unity via the 'structure' material, no livery atlas):
wing spars (front at 29 % chord, rear at 65 %) and ribs every 0.30 m in wing_C / wing_inner / wing_mid, the wing fuel-tank shells
between the spars (b 0.85-1.55, where the FuelTank of wing_inner sits), fuselage ring frames every 0.35 m with two longerons, the
fuselage tank ahead of the cockpit (A6M2 root, FuelTank 104 kg), the firewall and the oil tank behind the engine (fus_engine).
They are added INTO the part meshes, so they leave with their part and show through the damage holes (skin dmg alpha).
Spars and ribs skip the wheel-well openings and the leg slots (in_opening, 40 mm margin): the gear sweep check stays clean.
Every piece is a closed box / plate (model checks: orientation and see-through on every mesh).

r8o (user test of r8n: every break showed a SOLID round metal disc, and a 'box' in the same metal texture through the damage holes ahead
of the cockpit): breaks are open like stock (no cap; a dark 25 mm band at the end of the inner skin, an open frame / closed rib set back
END_FRAME_SETBACK, stringer / spar stubs ending 15-40 mm short of the plane); 'structure' (the stock aircraft_structure look) is used only on
thin members (frames, ribs, spars, stubs, flanges); the tanks are rounded cells in plain 'tank' metal with dark straps, the firewall is
'metal_dark' with a 'structure' flange and engine-mount stubs."""
import math
import random
import a6m2_spec as S
from b25h_geom import V, MeshBuf, box, cylinder, loft, fan_cap, oriented_quad, annulus

K = S.K
INSET = 0.006          # m inside the skin
END_FRAME_SETBACK = 0.10     # r8o: the frame / rib nearest a break stands this far inside the break plane (B-25H v3 TEAR_SETBACK)
STUB_SHORT = (0.015, 0.040)  # r8o: stubs (stringers, spars, longerons) end this far short of the break plane (random per stub)
TANKS = []             # r8o: (name, part, centre, half size) of every tank cell, filled by add() (model check tanks_material)
FRAMES_AT = []         # r8o: (part, y of the frame face nearest the break, toward) of every end frame (model checks)


def rng(*key):
    """r8o: deterministic per-joint random stream (str seed -> sha512 in random.Random, not the per-process hash())."""
    return random.Random('a6m2r8o:' + ':'.join(str(k) for k in key))


def _tri(mb, pts, mat, toward):
    a, b, c = pts
    if (b - a).cross(c - a).dot(V(toward)) < 0:
        b, c = c, b
    mb.poly([a, b, c], mat)


def rcell(mb, c, half, axis='y', n=4.0, N=24, M=14, mat='tank'):
    """r8o: rounded tank cell = superellipsoid (exponent n in both directions; n 4 gives flat sides with rounded edges / corners), centre c,
    half sizes (hx, hy, hz) in built axes, long axis 'y' (fuselage tank) or 'x' (wing tank). Closed, outward."""
    c = V(c)
    e = 2.0 / n
    sp = lambda v: math.copysign(abs(v) ** e, v)
    hx, hy, hz = half
    rings = []
    for k in range(1, M):
        phi = -math.pi / 2 + math.pi * k / M
        ax_ = sp(math.sin(phi)); r_ = abs(math.cos(phi)) ** e
        ring = []
        for j in range(N):
            th = 2 * math.pi * j / N
            a_, b_ = r_ * sp(math.cos(th)), r_ * sp(math.sin(th))
            if axis == 'y':
                ring.append(c + V((hx * a_, hy * ax_, hz * b_)))
            else:
                ring.append(c + V((hx * ax_, hy * a_, hz * b_)))
        rings.append(ring)
    loft(mb, rings, mat, closed=True, outward=True)
    d = V((0, 1, 0)) if axis == 'y' else V((1, 0, 0))
    hl = hy if axis == 'y' else hx
    fan_cap(mb, rings[0], c - d * hl, mat, -d)
    fan_cap(mb, rings[-1], c + d * hl, mat, d)
    return rings


def capsule(mb, p0, p1, r, N=16, M=5, mat='tank'):
    """r8o: cylinder p0..p1 with hemispherical ends (oil tank)."""
    p0, p1 = V(p0), V(p1)
    ax = (p1 - p0).normalized()
    ref = V((0, 0, 1)) if abs(ax.z) < 0.9 else V((1, 0, 0))
    u = (ref - ax * ref.dot(ax)).normalized(); w = ax.cross(u)
    rings = []
    for k in range(1, M + 1):                      # rear hemisphere (pole excluded)
        a = math.pi / 2 * k / M - math.pi / 2
        rings.append([p0 + ax * (r * math.sin(a)) + (u * math.cos(2 * math.pi * j / N) + w * math.sin(2 * math.pi * j / N)) * (r * math.cos(a)) for j in range(N)])
    for k in range(0, M):                          # front hemisphere
        a = math.pi / 2 * k / M
        rings.append([p1 + ax * (r * math.sin(a)) + (u * math.cos(2 * math.pi * j / N) + w * math.sin(2 * math.pi * j / N)) * (r * math.cos(a)) for j in range(N)])
    loft(mb, rings, mat, closed=True, outward=True)
    fan_cap(mb, rings[0], p0 - ax * r, mat, -ax)
    fan_cap(mb, rings[-1], p1 + ax * r, mat, ax)


def strap(mb, ring_at, y0, y1, out=0.003, inn=0.004, mat='metal_dark'):
    """r8o: closed band round a tank cell between y0 and y1; ring_at(y, d) = the cell section at y pushed out by d along its own normal."""
    o0, o1 = ring_at(y0, out), ring_at(y1, out)
    i0, i1 = ring_at(y0, -inn), ring_at(y1, -inn)
    loft(mb, [o0, o1], mat, closed=True, outward=True)
    loft(mb, [i0, i1], mat, closed=True, outward=False)
    annulus(mb, o0, i0, mat, V((0, -1, 0))); annulus(mb, o1, i1, mat, V((0, 1, 0)))


def _seg_ok(AP, x, y, margin=0.04):
    for dx, dy in ((0, 0), (margin, 0), (-margin, 0), (0, margin), (0, -margin)):
        if AP.in_opening(V((x + dx, y + dy, 0))):
            return False
    return True


def wing_tank_x(xb0, xb1):
    """r8o: wing tank span centre: first bay outboard of the root rib (xb0 + END_FRAME_SETBACK + 20 mm + half span), clamped 0.12 m
    inside the outer break (r8n: xm 1.20 put the cell 94 mm through the root break into the root part)."""
    xm = xb0 + END_FRAME_SETBACK + 0.02 + 0.33
    return min(xm, xb1 - 0.12 - 0.33)


def wing_internals(AP, mb, side, x0, x1, tank=False, seed=''):
    """spars + ribs for one wing part between built |x| x0..x1 (= the break planes; side +1 right / -1 left).
    r8o: the spars end U(STUB_SHORT) short of each break plane (uneven stubs); no regular rib within 0.05 m of the end ribs (built by
    a6m2_parts.wing_open_end at END_FRAME_SETBACK) or across the tank cell."""
    r = rng('wing', side, seed)
    step = 0.06
    for frac in (0.29, 0.65):                                 # spar webs, segment by segment
        # r8o: the break planes lean with the dihedral (the section plane): the spar ends are measured from the plane at the web's
        # top and bottom
        ends = []
        for xe in (x0, x1):
            ste = AP.wing_station(xe, 1)
            ye = ste.le.y - frac * ste.chord
            zs = (AP.lower_z(xe, ye) + INSET, AP.upper_z(xe, ye) - INSET)
            ends.append([AP.wing_plane_abs_x(side, xe, ye, z) for z in zs])
        xa0 = max(ends[0]) + r.uniform(*STUB_SHORT)
        xb_ = min(ends[1]) - r.uniform(*STUB_SHORT)
        n = max(2, int((xb_ - xa0) / step))
        for k in range(n):
            xa, xb = xa0 + (xb_ - xa0) * k / n, xa0 + (xb_ - xa0) * (k + 1) / n
            xm = 0.5 * (xa + xb)
            st = AP.wing_station(xm, 1)
            y = st.le.y - frac * st.chord
            if not _seg_ok(AP, side * xm, y):
                continue
            zl, zu = AP.lower_z(xm, y) + INSET, AP.upper_z(xm, y) - INSET
            if zu - zl < 0.02:
                continue
            box(mb, (side * xm, y, 0.5 * (zl + zu)), (xb - xa + (0.002 if 0 < k < n - 1 else 0.0), 0.006, zu - zl), 'structure')
    tank_x = None
    if tank:
        xm_t = wing_tank_x(x0, x1)
        tank_x = (xm_t - 0.33 - 0.03, xm_t + 0.33 + 0.03)
    xr = math.ceil(x0 / 0.30) * 0.30
    while xr < x1 - 0.02:                                     # ribs: plate following the section between 8 % and 88 % chord
        if xr < x0 + AP.wing_cavity(x0, -1) + 0.05 or xr > x1 - AP.wing_cavity(x1, 1) - 0.05 or (tank_x and tank_x[0] < xr < tank_x[1]):
            xr += 0.30                                        # r8o: no rib through the tank; round 2: none inside the lined break cavities
            continue                                          # (open cap strip at END_FRAME_SETBACK, bay-end wall at wing_cavity)
        st = AP.wing_station(xr, 1)
        pts_u, pts_l = [], []
        # r8g (game r8f sheet_ailgap: light slivers in the aileron gap every 0.30 m with the aileron down): the ribs ran to 88 % chord,
        # through the hinge wall into the aileron; in the aileron span they end 12 mm ahead of the hinge wall
        sa = AP.ail_s(xr)
        c_end = min(0.88, sa - AP.AIL_GAP / st.chord - 0.012 / st.chord) if sa is not None else 0.88
        for k in range(13):
            c = 0.08 + (c_end - 0.08) * k / 12
            y = st.le.y - c * st.chord
            zl_ = AP.lower_z(xr, y) + INSET
            sf = AP.flap_s(xr)
            if sf is not None and c > sf - 0.01:                  # r8: in the flap span the rib stops at the cove ceiling (was in the cove)
                t_ = max(0.0, (c - sf) / max(1 - sf, 1e-6))
                p_f = st.point(sf, False); p_te = st.point(1.0, True) - st.up * 0.0005
                zl_ = max(zl_, (p_f + (p_te - p_f) * t_ + st.up * (0.006 * (1 - t_) + 0.004 * math.sin(math.pi * t_))).z + INSET)
            pts_u.append((y, AP.upper_z(xr, y) - INSET)); pts_l.append((y, zl_))
        # r8: one closed plate per run of good chord segments (the r7 boxes had flat tops 8 mm proud of the sloping skin; per-segment
        # prisms welded into one shell with inner faces): side caps as quad strips, top / bottom strips, two end walls
        runs, cur = [], []
        for k in range(13):
            ok = pts_u[k][1] - pts_l[k][1] >= 0.02 and _seg_ok(AP, side * xr, pts_u[k][0])
            if ok:
                cur.append(k)
            elif cur:
                runs.append(cur); cur = []
        if cur:
            runs.append(cur)
        for run in runs:
            if len(run) < 2:
                continue
            for xo, tw in ((-0.002, V((-1, 0, 0))), (0.002, V((1, 0, 0)))):
                for k0, k1 in zip(run, run[1:]):
                    q = [V((side * xr + xo, pts_u[k0][0], pts_u[k0][1])), V((side * xr + xo, pts_u[k1][0], pts_u[k1][1])),
                         V((side * xr + xo, pts_l[k1][0], pts_l[k1][1])), V((side * xr + xo, pts_l[k0][0], pts_l[k0][1]))]
                    oriented_quad(mb, q, 'structure', tw)
            for k0, k1 in zip(run, run[1:]):
                for pts_, tw in ((pts_u, V((0, 0, 1))), (pts_l, V((0, 0, -1)))):
                    q = [V((side * xr - 0.002, pts_[k0][0], pts_[k0][1])), V((side * xr - 0.002, pts_[k1][0], pts_[k1][1])),
                         V((side * xr + 0.002, pts_[k1][0], pts_[k1][1])), V((side * xr + 0.002, pts_[k0][0], pts_[k0][1]))]
                    oriented_quad(mb, q, 'structure', tw)
            for k, tw in ((run[0], V((0, 1, 0))), (run[-1], V((0, -1, 0)))):
                q = [V((side * xr - 0.002, pts_u[k][0], pts_u[k][1])), V((side * xr + 0.002, pts_u[k][0], pts_u[k][1])),
                     V((side * xr + 0.002, pts_l[k][0], pts_l[k][1])), V((side * xr - 0.002, pts_l[k][0], pts_l[k][1]))]
                oriented_quad(mb, q, 'structure', tw)
        xr += 0.30
    if tank:                                                  # tank cell between the spars (r8o: rounded 'tank' cell inside the part)
        xm = wing_tank_x(x0, x1)
        st = AP.wing_station(xm, 1)
        y0, y1 = st.le.y - 0.31 * st.chord, st.le.y - 0.63 * st.chord
        ym = 0.5 * (y0 + y1)
        # r6: the box must clear the skins at all four corners (the r5 mid-point height let the aft outboard corner poke through the
        # lower skin: two light triangles in the bottom view)
        cs_ = [(xx, yy) for xx in (xm - 0.33, xm + 0.33) for yy in (y0 + 0.01, y1 - 0.01)]
        zl = max(AP.lower_z(xx, yy) for xx, yy in cs_) + 0.015
        zu = min(AP.upper_z(xx, yy) for xx, yy in cs_) - 0.015
        if zu - zl > 0.03:
            c_ = V((side * xm, ym, 0.5 * (zl + zu))); h_ = (0.33, 0.5 * (abs(y1 - y0) - 0.02), 0.5 * (zu - zl))
            rcell(mb, c_, h_, axis='x', n=4.0, mat='tank')
            TANKS.append((f'wing_tank_{"R" if side > 0 else "L"}', f'wing_inner_{"R" if side > 0 else "L"}', tuple(c_), h_))


def _ring_frame(mb, on, inn, of, inf, axis_c, toward, skipped, mat='structure'):
    """r8o: frame between the near rings (on outer / inn inner, at the face nearest the break) and the far rings (of / inf); ring
    segments whose ends are skipped are left out, every run is a closed solid (front / back faces, inner / outer faces, end walls)."""
    n = len(on)
    tw = V((0, toward, 0))
    ok = [not skipped[j] and not skipped[(j + 1) % n] for j in range(n)]
    if all(ok):
        runs = [list(range(n))]
        closed = True
    else:
        closed = False
        start = next(j for j in range(n) if not ok[j])
        runs, cur = [], []
        for k in range(1, n + 1):
            j = (start + k) % n
            if ok[j]:
                cur.append(j)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
    for run in runs:
        for j in run:
            j1 = (j + 1) % n
            mid = (on[j] + on[j1]) / 2
            ax = V((0, mid.y, axis_c)) - V((mid.x, mid.y, mid.z))
            oriented_quad(mb, [on[j], on[j1], inn[j1], inn[j]], mat, tw)
            oriented_quad(mb, [of[j], of[j1], inf[j1], inf[j]], mat, -tw)
            oriented_quad(mb, [inn[j], inn[j1], inf[j1], inf[j]], mat, ax)
            oriented_quad(mb, [on[j], on[j1], of[j1], of[j]], mat, -ax)
        if not closed:
            for j, sgn in ((run[0], 1), ((run[-1] + 1) % n, -1)):
                jn = (j + sgn) % n
                oriented_quad(mb, [on[j], inn[j], inf[j], of[j]], mat, on[j] - on[jn])


def l_stub(mb, base0, base1, inward, mat='structure', w=0.012, h=0.025, t=0.002, sec_axis=None):
    """r8o: L-section stringer stub (flange w on the skin, web h inward, thickness t) from base0 to base1 (points on the skin line).
    The two end sections lie in planes normal to sec_axis (the break-plane normal; default the stub axis), so the stub end keeps its
    distance to the break plane even where the skin slopes (the belly keel)."""
    ax = (base1 - base0).normalized() if sec_axis is None else V(sec_axis).normalized()
    nin = (inward - ax * inward.dot(ax)).normalized()
    tg = nin.cross(ax).normalized()
    sec = [(0, 0), (w, 0), (w, t), (t, t), (t, h), (0, h), (0, t)]          # A B C D E F G (G on F-A: caps split in two rectangles)
    P0 = [base0 + tg * a + nin * b for a, b in sec]
    P1 = [base1 + tg * a + nin * b for a, b in sec]
    outs = [-nin, tg, nin, tg, nin, -tg, -tg]                             # outward normal of each section edge k -> k+1
    for k in range(len(sec)):
        k1 = (k + 1) % len(sec)
        oriented_quad(mb, [P0[k], P0[k1], P1[k1], P1[k]], mat, outs[k])
    for P_, d in ((P0, -ax), (P1, ax)):
        A, B, C, D, E, F, G = P_
        for tri in ((A, B, C), (A, C, D), (A, D, G), (G, D, E), (G, E, F)):
            _tri(mb, list(tri), mat, d)


def fus_end_frame(AP, mb, y_end, toward, seed, skip=None, frame=True, sides=True, keel=True, spine=True, part=''):
    """r8o (after b25h_v3.fus_break_structure, nothing past the plane): at a fuselage break y_end (toward = +1 when the mating part lies at
    larger y) an OPEN ring frame (30 mm wide, 30 mm deep inside the skin) with its face END_FRAME_SETBACK inside the plane, and L-section
    stringer stubs (12 x 25 mm) from the frame toward the break, each ending U(STUB_SHORT) short of the plane (seeded per joint): two a side
    at z ~0.30 / -0.18, the keel and the spine. skip(p) drops ring points (wing box below the floor, wells, the cockpit opening)."""
    r = rng('fus', round(y_end, 3), toward, seed)
    yn = y_end - toward * END_FRAME_SETBACK
    yf = yn - toward * 0.03
    on = AP.body_ring(yn, inset=INSET, trough=False)
    inn = AP.body_ring(yn, inset=INSET + 0.03, trough=False)
    of = AP.body_ring(yf, inset=INSET, trough=False)
    inf = AP.body_ring(yf, inset=INSET + 0.03, trough=False)
    zw = AP.body_params(yn)[3]

    def cut(p):
        if skip is not None and skip(p):
            return True
        return abs(p.x) < 0.30 and p.z > 0.45 and -1.32 * K < p.y < -0.22 * K
    skipped = [cut(p) for p in on]
    if frame:
        _ring_frame(mb, on, inn, of, inf, zw, toward, skipped)
        FRAMES_AT.append((part, yn, toward))
    picks = []
    n = len(on)
    if sides:
        for zf in (0.30, -0.18):
            for sx in (1, -1):
                cand = [j for j in range(n) if on[j].x * sx > 0.02]
                picks.append(min(cand, key=lambda j: abs(on[j].z - zf)))
    if keel:
        picks.append(min(range(n), key=lambda j: on[j].z))
    if spine:
        picks.append(max(range(n), key=lambda j: on[j].z))
    for j in picks:
        if skipped[j] or skipped[(j + 1) % n] or skipped[(j - 1) % n]:
            continue
        ye = y_end - toward * r.uniform(*STUB_SHORT)
        b0 = AP.body_ring(yn, inset=INSET + 0.0025, trough=False)[j]
        b1 = AP.body_ring(ye, inset=INSET + 0.0025, trough=False)[j]
        if cut(b1):
            continue
        l_stub(mb, b0, b1, V((0, b0.y, AP.body_params(b0.y)[3])) - b0, sec_axis=V((0, 1, 0)))


def fuselage_frames(AP, mb, y0, y1, aft_joint=False, seed=''):
    """ring frames every 0.35 m (30 mm wide, 30 mm deep inside the skin) + two longerons, between built y0 > y1.
    r8o: the first frame face stands END_FRAME_SETBACK behind the front break y0 (it is that joint's end frame); with aft_joint the last
    frame is the aft joint's end frame at y1 + END_FRAME_SETBACK; the longerons end U(STUB_SHORT) short of the joint planes."""
    r = rng('frames', round(y0, 3), seed)
    y = y0 - END_FRAME_SETBACK
    stops = []
    while y - 0.03 > y1 + 0.02 + (END_FRAME_SETBACK + 0.15 if aft_joint else 0.0):
        stops.append(y)
        y -= 0.35
    if aft_joint:
        stops.append(y1 + END_FRAME_SETBACK + 0.03)              # its aft face stands END_FRAME_SETBACK inside the aft break
    hs = S.HOOK_SLOT

    def skip(p):
        if abs(p.x) < 0.30 and p.z > 0.45 and -1.32 * K < p.y < -0.22 * K:
            return True                                       # no frame across the cockpit opening
        # r8o: no frame across the hook slot / its dark backing tray (r5-r8n frames crossed the open slot: structure bars seen from below)
        return hs[1] * K - 0.02 <= p.y <= hs[0] * K + 0.02 and abs(p.x) < hs[2] * K + 0.05 and p.z < hs[3] * K + 0.02
    for y in stops:
        # r8o: the far face is the ring AT y - 0.03 (r5-r8n shifted the ring at y: on the tapering tail its aft edge stood up to 4 mm
        # out of the skin - light structure wedges along the fus_tail sides over the stab root)
        on = AP.body_ring(y, inset=INSET, trough=False)
        inn = AP.body_ring(y, inset=INSET + 0.03, trough=False)
        of = AP.body_ring(y - 0.03, inset=INSET, trough=False)
        inf = AP.body_ring(y - 0.03, inset=INSET + 0.03, trough=False)
        skipped = [skip(p) or skip(q) for p, q in zip(on, of)]
        if all(skipped):
            continue
        _ring_frame(mb, on, inn, of, inf, AP.body_params(y)[3], 1, skipped)
    for zf in (0.30, -0.18):                                  # longerons (square tubes along the side, each side)
        for sx in (1, -1):
            ya = y0 - r.uniform(*STUB_SHORT)
            yb = (y1 + r.uniform(*STUB_SHORT)) if aft_joint else y1 + 0.02
            seg = 16
            # r8o: one tube following the skin (x and z at every station; r5-r8n boxes set at each segment's mid x stood up to 6 mm out
            # of the tapering tail skin: light structure wedges along the fus_tail sides over the stab root)
            ys_ = [ya + (yb - ya) * k / seg for k in range(seg + 1)]
            cs_ = []
            for yy in ys_:
                zt_ = AP.body_params(yy)[0]
                z_ = min(zf, zt_ - 0.08)
                x = min(AP.body_ring_x(yy, z_ - 0.01), AP.body_ring_x(yy, z_ + 0.01)) - INSET - 0.018
                cs_.append(V((sx * x, yy, z_)) if x >= 0.05 else None)
            run = []
            for c_ in cs_ + [None]:
                if c_ is not None:
                    run.append(c_)
                    continue
                if len(run) >= 2:
                    rings = [[c + V((dx, 0, dz)) for dx, dz in ((-0.01, -0.01), (0.01, -0.01), (0.01, 0.01), (-0.01, 0.01))] for c in run]
                    loft(mb, rings, 'structure', closed=True, outward=True, smooth=False)
                    fan_cap(mb, rings[0], run[0], 'structure', run[0] - run[1])
                    fan_cap(mb, rings[-1], run[-1], 'structure', run[-1] - run[-2])
                run = []


def _ring_cut(ring, axis, v):
    """r8o round 2: points where a closed ring (in a plane y = const) crosses x = v (axis 'x') or z = v (axis 'z')."""
    out = []
    k = 0 if axis == 'x' else 2
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        da, db = a[k] - v, b[k] - v
        if (da < 0) != (db < 0):
            out.append(a + (b - a) * (da / (da - db)))
    return out


def firewall(AP, mb, y):
    """r8o: firewall with its aft face at y (10 mm plate forward of it) in 'metal_dark' (r8n: a light 'structure' plate at y 1.00 K) and a
    25 mm flange ring 3 mm aft of it against the inner skin.
    r8o round 3 (review of round 2: from the aft engine break the firewall 0.17 m in was still a full round disc, now crossed by a 3 x 2
    lattice of light 'structure' hat stiffeners = the user's "metal texture dividing the parts"): a PLAIN dark plate, no stiffeners, the
    flange metal_dark too, and FIREWALL_SETBACK 0.38 m deep behind the open end frame and the engine-mount truss (engine_mount_truss)."""
    from a6m2_cockpit import prism
    zw = AP.body_params(y)[3]

    def ring_in(yy, d):                                        # radial inset of the actual skin ring (with the gun troughs)
        ro = AP.body_ring(yy)
        return [p - V((p.x, 0, p.z - zw)).normalized() * d for p in ro]
    prism(mb, ring_in(y, 0.012), V((0, 1, 0)), 0.010, 'metal_dark')
    o0, i0 = ring_in(y - 0.004, 0.0075), ring_in(y - 0.004, 0.0075 + 0.025)
    o1, i1 = ring_in(y - 0.001, 0.0075), ring_in(y - 0.001, 0.0075 + 0.025)
    annulus(mb, o0, i0, 'metal_dark', V((0, -1, 0)))
    annulus(mb, o1, i1, 'metal_dark', V((0, 1, 0)))
    loft(mb, [o0, o1], 'metal_dark', closed=True, outward=True)
    loft(mb, [i0, i1], 'metal_dark', closed=True, outward=False)


MOUNT_PTS = ((0.306, 0.257), (-0.306, 0.257), (-0.306, -0.257), (0.306, -0.257))   # engine-mount pick-ups on the firewall (x, z - zc), cyclic:
                                                                                    # r 0.40 at 50 / 130 deg, so the bearers run fore-aft near the skin
MOUNT_R = 0.014


def engine_mount_truss(AP, mb, y_fw, y_frame):
    """r8o round 3 (review option a): the engine-mount tube truss between the firewall (aft face y_fw) and the open end frame of the
    fus_engine aft break (its far face y_frame): four bearers from the firewall bolt points out to the frame and one diagonal per bay
    (Warren), r 14 mm tubes in 'gear'; their frame ends are buried 10 mm in the frame (inset 20 mm of 6..36), nothing aft of the frame."""
    zc = -0.005 * K
    yb = y_frame - 0.015                                       # mid depth of the frame
    zw = AP.body_params(yb)[3]
    ring = AP.body_ring(yb, inset=INSET + 0.020, trough=False)

    def at_frame(x, z):
        a = math.atan2(x, z - zw)
        return min(ring, key=lambda p: abs(math.atan2(p.x, p.z - zw) - a))
    fw = [V((x, y_fw - 0.002, zc + z)) for x, z in MOUNT_PTS]
    fr = [at_frame(p.x, p.z) for p in fw]
    n = len(fw)
    for k in range(n):
        cylinder(mb, fw[k], fr[k], MOUNT_R, N=10, mat='gear')                # bearer
        cylinder(mb, fw[k], fr[(k + 1) % n], MOUNT_R, N=10, mat='gear')      # diagonal
    return fw, fr


FUS_TANK = dict(c=(0.0, 0.10 * K, 0.22), half=(0.26, 0.27, 0.18), straps_y=(0.0, 0.25), strap_w=0.020)


def fuselage_tank(mb):
    """r8o: the fuselage tank ahead of the cockpit (FuelTank 104 kg) as a rounded cell (superellipsoid n 4) in 'tank' metal, 0.52 x 0.54 x
    0.36 m (r8n: a 0.56 x 0.58 x 0.40 m 'structure' box = the 'box' seen through the damage holes), two 20 mm dark straps."""
    c = V(FUS_TANK['c'])
    hx, hy, hz = FUS_TANK['half']
    rcell(mb, c, (hx, hy, hz), axis='y', n=4.0, N=32, M=16, mat='tank')
    e = 0.5
    sp = lambda v: math.copysign(abs(v) ** e, v)

    def ring_at(y, d, N=48):
        t = max(-0.999, min(0.999, (y - c.y) / hy))
        sphi = math.copysign(abs(t) ** (1.0 / e), t)
        r_ = math.sqrt(max(0.0, 1 - sphi * sphi)) ** e
        pts = [V((c.x + hx * r_ * sp(math.cos(2 * math.pi * j / N)), y, c.z + hz * r_ * sp(math.sin(2 * math.pi * j / N)))) for j in range(N)]
        out = []
        for j in range(N):
            tng = pts[(j + 1) % N] - pts[j - 1]
            nn = V((tng.z, 0, -tng.x)).normalized()
            if nn.dot(pts[j] - V((c.x, y, c.z))) < 0:
                nn = -nn
            out.append(pts[j] + nn * d)
        return out
    for ys in FUS_TANK['straps_y']:
        strap(mb, ring_at, ys - FUS_TANK['strap_w'] / 2, ys + FUS_TANK['strap_w'] / 2)
    TANKS.append(('fus_tank', 'fus_center', tuple(c), (hx, hy, hz)))


FIREWALL_SETBACK = 0.38     # r8o round 3 (review of round 2: 0.17 m in with a light stiffener lattice was the round disc again): a plain
                            # dark plate 0.38 m in, behind the open end frame (0.10 m) and the engine-mount truss; the one intended
                            # full-section wall near a fuselage break (checks_r8 C11 DEEP_WALL_ALLOW)
OIL_R = 0.070               # round 3: the oil tank sits between the firewall (fwd face y 1.345) and the duct back wall (y 1.509)
OIL_Y = S.ENGINE_AFT_Y * K + FIREWALL_SETBACK + 0.010 + 0.010 + OIL_R
OIL_TANK = dict(p0=(-0.10, OIL_Y, 0.28), p1=(0.10, OIL_Y, 0.28), r=OIL_R)


def add(parts):
    import a6m2_parts as AP
    TANKS.clear()
    FRAMES_AT.clear()
    by = {p.name: p for p in parts}
    xb0, xb1, xb2 = (S.span_built(x) for x in S.WING_BREAKS[:3])
    for side, L in ((1, 'R'), (-1, 'L')):
        wing_internals(AP, by[f'wing_inner_{L}'].mesh, side, xb0, xb1, tank=True, seed='inner')
        wing_internals(AP, by[f'wing_mid_{L}'].mesh, side, xb1, xb2, seed='mid')
    ye, yr, yt = S.ENGINE_AFT_Y * K, S.REAR_FWD_Y * K, S.TAIL_FWD_Y * K
    # fuselage: frames in fus_rear / fus_tail (r8o: their first / last frames are the joints' end frames, the longerons the side stubs);
    # open end frames + stubs in fus_center at both joints; fuselage tank ahead of the cockpit (root); firewall + oil tank (engine)
    fuselage_frames(AP, by['fus_rear'].mesh, yr, yt, aft_joint=True, seed='rear')
    FRAMES_AT.append(('fus_rear', yr - END_FRAME_SETBACK, 1))
    FRAMES_AT.append(('fus_rear', yt + END_FRAME_SETBACK, -1))
    fus_end_frame(AP, by['fus_rear'].mesh, yr, 1, 'rear_f', frame=False, sides=False)          # keel / spine stubs
    fus_end_frame(AP, by['fus_rear'].mesh, yt, -1, 'rear_a', frame=False, sides=False)
    vs = by['fus_tail'].mesh.verts
    fuselage_frames(AP, by['fus_tail'].mesh, yt, min(v.y for v in vs) + 0.25, seed='tail')
    FRAMES_AT.append(('fus_tail', yt - END_FRAME_SETBACK, 1))
    fus_end_frame(AP, by['fus_tail'].mesh, yt, 1, 'tail_f', frame=False, sides=False)
    root = by['fus_center'].mesh

    def skip_c(p):                                            # the wing box under the body floor, the wells
        zw_ = AP.wing_upper_centre_z(p.y)
        if zw_ is not None and p.z < zw_ + 0.02:
            return True
        R_ = S.WELL_R * K + 0.02
        return any((V((p.x, p.y, 0)) - AP.well_centre(sd)).length < R_ for sd in (1, -1))
    fus_end_frame(AP, root, ye, 1, 'center_f', skip=skip_c, part='fus_center')
    fus_end_frame(AP, root, yr, -1, 'center_a', skip=skip_c, part='fus_center')
    fuselage_tank(root)                                       # fuselage fuel tank (FuelTank 104 kg)
    eng = by['fus_engine'].mesh
    # r8o round 3: the engine part's aft break gets the open end frame + stubs like fus_center (skipping the gun troughs), the mount
    # truss behind it and the plain dark firewall FIREWALL_SETBACK in
    tx, thw = S.TROUGH_X * K, S.TROUGH_HALF_W * K

    def skip_e(p):
        return p.z > AP.body_params(p.y)[3] and abs(abs(p.x) - tx) < thw + 0.03
    fus_end_frame(AP, eng, ye, -1, 'engine_a', skip=skip_e, part='fus_engine')
    firewall(AP, eng, ye + FIREWALL_SETBACK)
    engine_mount_truss(AP, eng, ye + FIREWALL_SETBACK, ye + END_FRAME_SETBACK + 0.03)
    o = OIL_TANK
    capsule(eng, V(o['p0']), V(o['p1']), o['r'], N=16, M=5, mat='tank')   # oil tank (horseshoe simplified; r8o: round ends, 'tank')
    TANKS.append(('oil_tank', 'fus_engine', tuple((V(o['p0']) + V(o['p1'])) / 2), (0.10 + o['r'], o['r'], o['r'])))
