"""Hawker Nimrod Mk I exterior parts, v3 (2026-11-02 rebuild after user review 1). Our own geometry; dimensions from nimrod_spec.

What changed against v1 (nimrod_parts_v1.py, the 1.2.3 model), defect by defect (refs/nimrod_user_review_1/shot1..8):
  1 / 4  struts: every cabane, interplane, stabiliser strut and every flying / landing / incidence wire ends on a fitting that sits
         ON the surface it attaches to (ends computed from the real fuselage section / wing aerofoil and embedded 15 mm);
         the interplane struts are the parallel pair of the reference (no diagonal); the pitot is mounted on the strut.
  2      the lower wings meet the fuselage through a root fillet (child object, so the wing collider is unchanged) whose inner edge
         follows the fuselage skin; Vickers Mk III guns are fal 3D models lying in real troughs cut into the decking.
  3      exhausts: fal Kestrel manifolds (six stubs into the cowling, collector and tail pipe) instead of boxes; louvres in the texture.
  5      every wing / tail tip is closed; the upper centre section is closed at both ends by the tear structure.
  6      the stabilisers meet the fuselage through a root fillet that follows the tail cone.
  7      breaks: complementary jagged skin edges at y 0 / -1.5 (fuselage) and x +-0.80 (upper wing), double skins (inner face 4 mm in,
         edge strips), bulkheads / formers / ribs set back from every split, longeron, truss and spar stubs, a Warren steel-tube
         truss inside the rear fuselage (nimrod_structure.py). Material `structure` = the stock jet_mechanical role.
  8      tail hook: fal arrester hook (forked hinge fitting, tube with clamp bands, forged claw), stretched to the functional 2.37 m
         and hinged at the unchanged hinge (0, -1.68, 0.08); a belly slot lets it swing down.
Functional geometry kept (check_nimrod_model.py compares with assets/model_nimrod/nimrod_functional_123.json): every Unity part's own
mesh bounds (collider, CoM, lift point), pivots, wheels (radius = bounds), hook hinge / length / angles, muzzles, hardpoints.
New geometry that would move a part's bounds lives in child objects (<part>_root, <part>_struct): not in the part collider.
"""
import math, os, sys
from mathutils import Vector, Quaternion, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(HERE, '..', 'v2')
for p in (HERE, V2):
    if p not in sys.path:
        sys.path.insert(0, p)
from b25h_geom import (V, MeshBuf, loft, cylinder, box, circle_pts, fan_cap, oriented_quad, annulus, Station, surface,
                       planar_uv, frame_from_axes, arc_lengths, section_cap)
from b25h_parts import Part
import nimrod_spec as S
import nimrod_structure as ST
import nimrod_props as PR
import nimrod_v140 as N4
import internals_r183 as IN
import break_r8o as BR

TEAR_AMP_FUS, TEAR_AMP_WING = 0.0, 0.0         # 1.4.0: straight splits on natural lines (cowl / firewall joint y 0, metal-to-fabric joint
                                               # y -1.5 behind the cockpit, centre-section joint x +-0.80); 1.3.x: 22 mm jags (user: visible)
FUS_SPLITS = (S.ENGINE_AFT_Y, S.CENTRE_AFT_Y)
BREAK_R8O = True               # 2026-11-22: open break ends (no discs / full ribs / root caps), r8o pattern; the FD-32 shares it
BREAK_SETBACK = 0.10           # open frame / rib cap strip this far inside every fuselage / upper-wing break (m)
TAIL_SETBACK = 0.06            # stab / fin root cap strip (m)
WING_CAVITY = 0.40             # lined wing break cavity ends in a bay-end wall this far in (m)
TAIL_CAVITY = 0.25             # stab / fin root cavity (m, beyond the root; the stab fillet adds 30-110 mm)
WING_SPLIT_X = S.UP_CENTRE_X
SETBACK = 0.075


def frame_x(xaxis, zhint=(0, 0, 1)):
    return frame_from_axes(V(xaxis), V(zhint))


# ------------------------------------------------------------------------------------------- fuselage section
def fus_ring(y, N=36):
    """v1 section (kept for the cockpit builder): point 0 at the top centre, going to +x."""
    hw, zt, zb, n = ST.fus_params(y)
    cz = (zt + zb) / 2
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


def _ring_angles():
    base = [7.5 * k for k in range(48)]
    extra = [9.5, 11.5, 13.0, 14.0, 16.0, 17.0, 18.5, 20.0, 21.0, 24.5, 26.5]
    a = set(round(x, 3) for x in base)
    for e in extra:
        a.add(e); a.add(round(360 - e, 3))
    return sorted(a)


RING_ANG = _ring_angles()
TROUGH_Y = (-0.22, 1.80)     # groove ramps in/out over 0.18 m at both ends
TROUGH_W = 0.046


def trough_floor(y):
    y0, y1 = TROUGH_Y
    if not (y0 < y < y1):
        return None
    f = min((y - y0) / 0.18, (y1 - y) / 0.18, 1.0)
    return (S.GUN_Z - 0.065) + (1 - f) * 0.20       # 0.39 in the full-depth run


def fus_ring2(y):
    """v3 exterior section: the v1 superellipse sampled at RING_ANG (dense over the gun troughs) with the troughs cut in."""
    hw, zt, zb, n = ST.fus_params(y)
    cz = (zt + zb) / 2
    fl = trough_floor(y)
    pts = []
    for deg in RING_ANG:
        ang = math.radians(deg)
        s, c = math.sin(ang), math.cos(ang)
        e = n if c < 0 else max(2.0, n - 0.6)
        x = hw * math.copysign(abs(s) ** (2.0 / e), s)
        hz = (zt - cz) if c >= 0 else (cz - zb)
        z = cz + hz * math.copysign(abs(c) ** (2.0 / e), c)
        if fl is not None and c > 0:
            dx = abs(abs(x) - S.GUN_X)
            if dx < TROUGH_W and z > fl:
                z = fl + (z - fl) * (dx / TROUGH_W) ** 2.2
        pts.append(V((x, y, z)))
    return pts


def ring_uv(rings, ys):
    al = [arc_lengths(r) for r in rings]
    n = len(rings[0])

    def f(ci, cj, j):
        acc, P = al[ci]
        u = P if (cj == 0 and j == n - 1) else acc[cj]
        return (u, ys[ci])
    return f


def fus_inset_ring(y, inset):
    """the section shrunk toward its centre by `inset` (formers, bulkheads, truss)."""
    r = fus_ring2(y)
    hw, zt, zb, n = ST.fus_params(y)
    c = V((0, y, (zt + zb) / 2))
    return [p + (c - p).normalized() * inset for p in r], c


def corner(y, side, top, inset=0.045):
    """longeron position: section corner (45 deg) moved `inset` inside."""
    hw, zt, zb, n = ST.fus_params(y)
    cz = (zt + zb) / 2
    ang = math.radians(45 if top else 135)
    s, c = math.sin(ang), math.cos(ang)
    e = n if c < 0 else max(2.0, n - 0.6)
    x = hw * abs(s) ** (2.0 / e)
    hz = (zt - cz) if c >= 0 else (cz - zb)
    z = cz + hz * math.copysign(abs(c) ** (2.0 / e), c)
    p = V((side * x, y, z)); cc = V((0, y, cz))
    return p + (cc - p).normalized() * inset


# ------------------------------------------------------------------------------------------- strut / wire helpers
def strut(mb, p0, p1, w, t, mat='paint', N=10, fwd=V((0, 1, 0)), ext=0.0):
    """streamlined strut (elliptic section, chord w along the flight direction, thickness t), extended `ext` past both ends."""
    p0, p1 = V(p0), V(p1)
    ax = (p1 - p0).normalized()
    p0, p1 = p0 - ax * ext, p1 + ax * ext
    f = (fwd - ax * fwd.dot(ax)).normalized()
    s = ax.cross(f).normalized()

    def ring(c):
        return [c + f * (math.cos(2 * math.pi * k / N) * w / 2) + s * (math.sin(2 * math.pi * k / N) * t / 2) for k in range(N)]
    r0, r1 = ring(p0), ring(p1)
    loft(mb, [r0, r1], mat, smooth=True)
    fan_cap(mb, r0, p0, mat, -ax)
    fan_cap(mb, r1, p1, mat, ax)


def fitting(mb, p, normal, size=(0.05, 0.07, 0.012), mat='metal_dark'):
    """small plate fitting lying on a surface (centre p ON the surface, half inside)."""
    n = V(normal).normalized()
    q = Quaternion(V((0, 0, 1)).rotation_difference(n))
    box(mb, p, size, mat, rot=q)


def wire(mb, p0, p1, r=0.0045):
    cylinder(mb, V(p0), V(p1), r, N=4, mat='metal_dark', cap0=True, cap1=True, smooth=True)


ATTACH = []      # (object name, end point, [target object names]) for the connectivity check


def attach(obj, p, targets):
    ATTACH.append((obj, tuple(round(c, 5) for c in V(p)), list(targets)))


# ------------------------------------------------------------------------------------------- fuselage
def fus_stations():
    ys = {round(s[0], 3) for s in S.FUS} | {S.ENGINE_AFT_Y, S.CENTRE_AFT_Y, S.COCKPIT_Y[0], S.COCKPIT_Y[1], -0.55, -0.85, 1.2, 0.8, 0.4,
                                          -1.15, -2.6, -3.2, -3.8, -4.3, -0.26, 1.58, 1.62, 1.80, -0.22, -0.04, 0.14, 0.6, -0.12,
                                          -1.75, -2.10, -1.62, 0.95, 0.30, 1.98, 2.15, -0.065, -1.44, -0.03, -1.47}
    return sorted(ys, reverse=True)


SLOT_Y = (-1.75, -2.10)
ENGINE_BODY = IN.kestrel      # 1.8.3: engine body in fus_engine_struct (the FD-32 sets IN.fd32_power)
_FUN123 = None


def fun123(name):
    """1.2.3 functional snapshot (assets/model_nimrod/nimrod_functional_123.json): own-mesh bounds of a Unity part."""
    global _FUN123
    if _FUN123 is None:
        import json
        _FUN123 = json.load(open(os.path.join(HERE, '..', '..', 'assets', 'model_nimrod', 'nimrod_functional_123.json')))
    return _FUN123[name]


def bounds_keeper(mb, name, body_pt, x):
    """0.1 mm wide sliver from the control surface body (body_pt) forward to the 1.2.3 bounds' front (max y) at span x: invisible
    (inside the hinge cove), it keeps the Unity collider / CoM / lift point of this hinge part exactly as flight-tested."""
    b = fun123(name)
    kp = V((x, b['hi'][1], body_pt.z))
    mb.face([mb.v(body_pt), mb.v(kp), mb.v(kp + V((0, 0, 0.0001)))], 'cove')
SLOT_HW = 0.075
RUDDER_BALANCE = True    # round 10: the Mk I's horn + aerial mast are back, re-modelled to the reference proportions (nimrod_v140); the FD-32 sets it False
HOOK_SLOT = False      # 1.4.0: the functional hook's mesh is hidden (the visible A-frame lies under the belly): belly closed


def opening_hx(y):
    """1.8.0: half width of the rounded cockpit opening at station y (0 outside it). Width at mid = the old sill width."""
    bx = ST.fus_half_width(y, S.COCKPIT_SILL_Z)
    ymap = getattr(S, 'OPENING_YMAP', None)
    if ymap is not None:                     # FD-32: shape the hole in the stretched frame (the skin is built before the stretch)
        y = ymap(y); y0, y1 = S.OPENING_Y_POST
    else:
        y0, y1 = S.COCKPIT_Y                 # rear, front
    a = (y1 - y0) / 2; yc = (y0 + y1) / 2
    t = (y - yc) / a
    if abs(t) >= 1.0:
        return 0.0
    m = S.OPENING_EXP[0] if t > 0 else S.OPENING_EXP[1]
    return bx * (1 - abs(t) ** m) ** (1.0 / m)


def opening_cut_index(rings):
    """+x index of the upper arc limit: the last ring point (from the top) that stays above OPENING_ZCUT on every cockpit ring."""
    n = len(rings[0])
    j = 0
    while j + 1 < n // 2 and all(r[j + 1].z >= S.OPENING_ZCUT for r in rings):
        j += 1
    return j


def opening_patch(mb, ys, rings, jc):
    """the skin of the cockpit rows from ring index jc (both sides) up over the top, ON the loft's own bilinear surface (sections lerped
    between the station rings, so every station edge matches the neighbouring rows exactly), with the ring points that fall inside the
    rounded hole moved onto the hole edge (degenerate slivers dropped). 25 mm sub-stations, livery UV = top view (x, y).
    Returns the hole-edge points per side (front to rear)."""
    n = len(rings[0])
    edge = {1: [], -1: []}
    for i in range(len(ys) - 1):
        ya, yb = ys[i], ys[i + 1]
        if not (S.COCKPIT_Y[0] - 1e-4 <= min(ya, yb) and max(ya, yb) <= S.COCKPIT_Y[1] + 1e-4):
            continue
        msub = max(2, int(math.ceil((ya - yb) / 0.025)))
        for side in (1, -1):
            jidx = list(range(jc, -1, -1)) if side > 0 else [(n - k) % n for k in range(jc, -1, -1)]   # from the cut up to the top centre
            grid = []
            for q in range(msub + 1):
                t = q / msub
                y = ya + (yb - ya) * t
                sec = [rings[i][j].lerp(rings[i + 1][j], t) for j in jidx]          # |x| falls to 0 at the top centre
                hx = opening_hx(y)
                ep = None
                if hx > 1e-6:
                    for p0, p1 in zip(sec, sec[1:]):
                        if abs(p0.x) >= hx >= abs(p1.x):
                            ep = p0.lerp(p1, (abs(p0.x) - hx) / max(abs(p0.x) - abs(p1.x), 1e-9)); break
                row = [p if (ep is None or abs(p.x) >= hx) else ep.copy() for p in sec]
                grid.append(row)
                edge[side].append(ep if ep is not None else sec[-1])
            idx = [[mb.v(p) for p in row] for row in grid]
            for q in range(msub):
                for k in range(len(jidx) - 1):
                    c4 = [idx[q][k], idx[q][k + 1], idx[q + 1][k + 1], idx[q + 1][k]]
                    P_ = [mb.verts[v] for v in c4]
                    nrm = (P_[1] - P_[0]).cross(P_[3] - P_[0]) + (P_[2] - P_[1]).cross(P_[0] - P_[1]) * 0
                    area = ((P_[2] - P_[0]).cross(P_[3] - P_[1])).length / 2
                    if area < 1e-8:
                        continue
                    ctr = sum(P_, V()) / 4
                    hw_, zt_, zb_, n_ = ST.fus_params(ctr.y)
                    out = V((ctr.x, 0, ctr.z - (zt_ + zb_) / 2))
                    if ((P_[2] - P_[0]).cross(P_[3] - P_[1])).dot(out) < 0:
                        c4 = c4[::-1]
                    mb.face(c4, 'paint', [(mb.verts[v].x, mb.verts[v].y) for v in c4])
    for sd in edge:
        edge[sd].sort(key=lambda p: -p.y)
    return edge


OPENING_EDGE = {}


def build_fuselage():
    ys_all = fus_stations()
    segs = {'fus_engine': [y for y in ys_all if y >= S.ENGINE_AFT_Y],
            'NIMROD1': [y for y in ys_all if S.ENGINE_AFT_Y >= y >= S.CENTRE_AFT_Y],
            'fus_rear': [y for y in ys_all if y <= S.CENTRE_AFT_Y]}
    out = {}
    for name, ys in segs.items():
        mb = MeshBuf()
        rings = [fus_ring2(y) for y in ys]
        n = len(rings[0])
        ck_rings = [r for r, y in zip(rings, ys) if S.COCKPIT_Y[0] - 1e-4 <= y <= S.COCKPIT_Y[1] + 1e-4]
        jc = opening_cut_index(ck_rings) if (name == 'NIMROD1' and ck_rings) else 0

        def keep(i, j, ys=ys, rings=rings, name=name):
            ya, yb = ys[i], ys[i + 1]
            a, b = rings[i][j], rings[i][(j + 1) % n]
            if name == 'NIMROD1' and S.COCKPIT_Y[0] - 1e-4 <= min(ya, yb) and max(ya, yb) <= S.COCKPIT_Y[1] + 1e-4:
                if getattr(S, 'OPENING_ROUND', False):          # 1.8.0: the upper arc is rebuilt by opening_patch
                    return not (j < jc or j >= n - jc)
                return (a.z + b.z) / 2 < S.COCKPIT_SILL_Z
            if name == 'fus_rear' and HOOK_SLOT and SLOT_Y[1] - 1e-4 <= min(ya, yb) and max(ya, yb) <= SLOT_Y[0] + 1e-4:
                return not (abs((a.x + b.x) / 2) < SLOT_HW and (a.z + b.z) / 2 < -0.3)     # 1.3.x hook slot in the belly
            return True
        loft(mb, rings, 'paint', keep=keep, uvfunc=ring_uv(rings, ys))
        if name == 'NIMROD1' and getattr(S, 'OPENING_ROUND', False):
            OPENING_EDGE.clear(); OPENING_EDGE.update(opening_patch(mb, ys, rings, jc))
        if name == 'fus_engine':
            inner = [V((p.x * 0.88, p.y, p.z * 0.88)) for p in rings[0]]
            annulus(mb, rings[0], inner, 'metal_dark', V((0, 1, 0)))
            fan_cap(mb, inner, V((0, rings[0][0].y - 0.01, 0)), 'metal_dark', V((0, 1, 0)))
        if name == 'fus_rear':
            fan_cap(mb, rings[-1], sum(rings[-1], V()) / n, 'paint', V((0, -1, 0)), uvfunc=lambda p: (p.x * 4, p.z * 4))
        out[name] = mb
    return out


def tear_fuselage(fus):
    rep = {}
    for k, y in enumerate(FUS_SPLITS):
        n = 0
        for nm in (('fus_engine', 'NIMROD1') if k == 0 else ('NIMROD1', 'fus_rear')):
            n += ST.tear_mesh(fus[nm], (0, y, 0), (0, 1, 0), lambda v: math.atan2(v.x, v.z) * 0.45, TEAR_AMP_FUS, 11 + k, 0.035, mats=('paint',))
        rep[f'y={y}'] = n
    return rep


STRINGER_DEG = (22, 70, 90, 112, 158, 180, 202, 248, 270, 292, 338)     # around the section (0 = top; the corner longerons at 45 / 135)
STRINGER_W, STRINGER_H = 0.012, 0.016                                    # rectangular stringer, H standing off the liner


def wall_frame_ring(mb, y, depth=0.060, thick=0.014, skip_trough=True):
    """2026-11-27 round 3 (regression review of round 2): the 60 mm open frame in front of a cockpit wall. As ST.frame_ring, but no
    segment across a gun trough: the skin there ramps down along y (TROUGH_Y starts at -0.22), so a 14 mm thick ring cut from the
    section at one y stood 2-3.4 mm out through the trough floor (Mk I 49 struct vertices with a sky view, FD-32 12)."""
    ring, centre = fus_inset_ring(y, 0.002)
    n = len(ring)
    inner = [p + (centre - p).normalized() * depth for p in ring]
    off = V((0, thick / 2, 0))

    def in_trough(q):
        return skip_trough and q.z > centre.z and abs(abs(q.x) - S.GUN_X) < TROUGH_W + 0.012
    for j in range(n):
        j1 = (j + 1) % n
        a, b, c, d = ring[j], ring[j1], inner[j1], inner[j]
        if in_trough(a) or in_trough(b):
            continue
        oriented_quad(mb, [a + off, b + off, c + off, d + off], 'structure', V((0, 1, 0)))
        oriented_quad(mb, [a - off, b - off, c - off, d - off], 'structure', V((0, -1, 0)))
        oriented_quad(mb, [d + off, c + off, c - off, d - off], 'structure', centre - (c + d) / 2)
        if in_trough(ring[(j - 1) % n]):              # the ring stops at a trough: close its end
            oriented_quad(mb, [a + off, d + off, d - off, a - off], 'structure', a - b)
        if in_trough(ring[(j1 + 1) % n]):
            oriented_quad(mb, [b + off, c + off, c - off, b - off], 'structure', b - a)


BAY_FIT = True                 # 2026-11-27 round 3: header tank ahead of the cockpit, radio / oxygen / battery behind it
BAY_STYLE = 'period'           # FD-32 (fd32_parts.build_exterior): 'modern' - an avionics unit instead of the period radio set


def bay_fittings(cen, NC_):
    """2026-11-27 break faces round 3 (review of round 2: from both fus_center breaks one dark plane, the cockpit wall 0.22 m in, still
    covered 0.64 (front) / 0.81 (aft) of the axial view - the 'divider', only darker). The bays between the breaks and the cockpit walls
    get what the real aircraft carried there, as the accepted r8o pattern shows a fuselage tank body ahead of the cockpit:
      front bay (y 0 .. YB): the main fuel (header) tank, a rounded body across the fuselage over the footwell box, 'tank' metal
        (Unity <prefix>_tank, lit 0.55 grey) with dark straps, its front ~95 mm in (C6: tank >= 40 mm), clear of the longerons, the
        wall-station truss and the footwell box;
      aft bay (YA .. y -1.5): the radio set on a tube shelf (interior grey-green, dark panel plates and knobs), an oxygen bottle across
        the floor (dark, straps) and the battery box, all >= 40 mm inside the break, behind the wall-station truss.
    Built into fus_center_struct (in no collider; no mass / CoM change)."""
    if not BAY_FIT:
        return
    dk = 'metal_dark'
    # ---- front bay: header tank, axis along x; superellipse section n 3 (front face ~95 mm in, back 25 mm clear of the wall frame)
    yc, hy = -0.142, 0.047
    z0, z1, hx = -0.245, 0.345, 0.255
    zc, hz = (z0 + z1) / 2, (z1 - z0) / 2
    tank = lambda a_, b_, prof, mat, N=24: IN.body(cen, a_, b_, V((0, 0, 1)), prof, n=3.0, N=N, mat=mat)
    # body(): axis w = +x, u = up x w = +y (half size hw -> y), v = +z (half size hh -> z)
    tank((-hx, yc, zc), (hx, yc, zc), [(0.0, hy * 0.80, hz * 0.88), (0.035, hy, hz), (0.965, hy, hz), (1.0, hy * 0.80, hz * 0.88)], IN.TANK_MAT)
    for xs in (-0.13, 0.13):                        # straps: dark bands round the tank
        tank((xs - 0.011, yc, zc), (xs + 0.011, yc, zc), [(0.0, hy + 0.004, hz + 0.004), (1.0, hy + 0.004, hz + 0.004)], dk)
    for xs in (-1, 1):                              # cradle: tubes from the tank's lower ends out to the bottom longeron line
        IN.bar(cen, (xs * (hx - 0.03), yc, z0 + 0.06), (xs * (ST.fus_half_width(yc, -0.330) - 0.014), yc, -0.330), 0.008, mat='structure')
    IN.bar(cen, (0.10, yc, z1 - 0.020), (0.10, yc, z1 + 0.026), 0.016, mat=dk)                  # filler neck
    IN.bar(cen, (0.10, yc, z1 + 0.026), (0.10, yc, z1 + 0.036), 0.022, mat=dk)                  # cap
    # ---- aft bay (YA .. -1.5): shelf, radio, oxygen bottle, battery; break-side faces >= 44 mm inside y -1.5
    ya_ = S.CENTRE_AFT_Y
    yf_, yb_ = ya_ + 0.048, ya_ + 0.150             # break-side face / back of the fittings: y -1.452 .. -1.350
    ym = (yf_ + yb_) / 2
    for yy in (yf_ + 0.014, yb_ - 0.014):           # shelf tubes, side to side under the radio
        xe = ST.fus_half_width(yy, 0.040) - 0.0065    # to the side liner (2.5 mm inside the skin)
        IN.bar(cen, (-xe, yy, 0.040), (xe, yy, 0.040), 0.008, mat='structure')
    IN.rbox(cen, (0, ym, 0.205), (0.46, yb_ - yf_, 0.31), mat='interior', n=8.0)                # radio set
    IN.rbox(cen, (-0.075, ym + 0.004, -0.060), (0.25, yb_ - yf_ - 0.008, 0.16), mat='interior', n=8.0)   # its power unit, under the shelf
    for xs in (-0.17, 0.02):                        # power unit feet on the bottle straps' frame line
        IN.bar(cen, (xs, ym, -0.110), (xs, ym, -0.188), 0.008, mat='structure')
    if BAY_STYLE == 'modern':                       # FD-32: avionics unit - dark front with two pull handles and connectors
        IN.rbox(cen, (0, yf_ - 0.003, 0.205), (0.40, 0.008, 0.26), mat=dk, n=6.0)
        for xs in (-0.17, 0.17):
            IN.bar(cen, (xs, yf_ - 0.007, 0.29), (xs, yf_ - 0.024, 0.29), 0.008, mat='structure')
            IN.bar(cen, (xs, yf_ - 0.007, 0.12), (xs, yf_ - 0.024, 0.12), 0.008, mat='structure')
            IN.bar(cen, (xs, yf_ - 0.024, 0.12), (xs, yf_ - 0.024, 0.29), 0.008, mat='structure')
        for xs in (-0.06, 0.06):
            IN.bar(cen, (xs, yf_ - 0.007, 0.15), (xs, yf_ - 0.020, 0.15), 0.018, mat='structure')
    else:                                           # Mk I: period receiver / transmitter - round tuning dial, knobs, a name plate
        IN.body(cen, (-0.10, yf_ + 0.002, 0.245), (-0.10, yf_ - 0.008, 0.245), V((0, 0, 1)), [(0.0, 0.058, 0.058), (1.0, 0.058, 0.058)],
                n=2.0, N=20, mat=dk)
        IN.body(cen, (-0.10, yf_ - 0.008, 0.245), (-0.10, yf_ - 0.024, 0.245), V((0, 0, 1)), [(0.0, 0.020, 0.020), (1.0, 0.016, 0.016)],
                n=2.0, N=12, mat='structure')
        for xs, zz in ((0.07, 0.29), (0.15, 0.29), (0.07, 0.19), (0.15, 0.19)):
            IN.bar(cen, (xs, yf_ + 0.004, zz), (xs, yf_ - 0.016, zz), 0.012, mat=dk)
        IN.rbox(cen, (-0.10, yf_ - 0.003, 0.115), (0.15, 0.008, 0.035), mat='structure', n=6.0)
    for xs in (-0.19, 0.19):                        # rubber mounts on the shelf
        IN.bar(cen, (xs, ym, 0.047), (xs, ym, 0.0515), 0.018, mat=dk)
    # oxygen bottle across the floor (axis x), two straps, valve
    IN.body(cen, (-0.250, ym, -0.255), (0.120, ym, -0.255), V((0, 0, 1)),
            [(0.0, 0.020, 0.020), (0.05, 0.055, 0.055), (0.13, 0.066, 0.066), (0.94, 0.066, 0.066), (1.0, 0.058, 0.058)], n=2.0, N=20, mat=dk)
    IN.bar(cen, (-0.248, ym, -0.255), (-0.282, ym, -0.255), 0.013, mat='structure')
    for xs in (-0.17, 0.04):
        IN.body(cen, (xs - 0.009, ym, -0.255), (xs + 0.009, ym, -0.255), V((0, 0, 1)), [(0.0, 0.070, 0.070), (1.0, 0.070, 0.070)],
                n=2.0, N=20, mat='structure')
    IN.rbox(cen, (0.205, ym, -0.235), (0.11, yb_ - yf_ - 0.010, 0.15), mat=dk, n=8.0)            # battery box
    for xs in (0.175, 0.235):                       # terminals
        IN.bar(cen, (xs, ym, -0.162), (xs, ym, -0.150), 0.010, mat='structure')


def cen_stringers(cen, rr, NC_):
    """2026-11-27 break faces round 2: the bays between the fus_center breaks (y 0 / -1.5) and the cockpit walls (YB / YA, 0.22 m in).
    Longerons from the 0.10 m frame to the wall, an open frame 20 mm in front of the wall, stringers along the liner from 15-40 mm short
    of the plane to that frame. Skipped: the gun troughs (front bay top) and the footwell box (front bay floor).
    Round 3 (regression review of round 2): the wall-station truss stood on the PILOT side of the walls (yt = yw - d * 0.030 put the
    cross tubes / verticals at y -0.23 / -1.27, inside the cockpit, seen from the eye); now yt = yw + d * 0.030 (break side, >= 30 mm
    clear of the break-facing wall); the wall frame skips the gun troughs (wall_frame_ring); the bays get their fittings (bay_fittings)."""
    yb_w, ya_w = NC_.YB + 0.020, NC_.YA - 0.020
    for yp, yf, yw, d in ((S.ENGINE_AFT_Y, S.ENGINE_AFT_Y - BREAK_SETBACK, yb_w, 1), (S.CENTRE_AFT_Y, S.CENTRE_AFT_Y + BREAK_SETBACK, ya_w, -1)):
        wall_frame_ring(cen, yw)                                                        # the cockpit wall's mounting frame
        for side in (-1, 1):
            for top in (True, False):
                ST.tube(cen, corner(yf, side, top, 0.05), corner(yw - d * 0.003, side, top, 0.05), 0.013)
        # Warren truss bay (the Mk I fuselage is a steel-tube truss, as fus_rear): cross tubes and verticals at the wall station, side
        # diagonals from the 0.10 m frame down to it; no bottom cross tube over the footwell box (front bay)
        yt = yw + d * 0.030
        tl, tr, bl, br = (corner(yt, -1, True, 0.05), corner(yt, 1, True, 0.05), corner(yt, -1, False, 0.05), corner(yt, 1, False, 0.05))
        ST.tube(cen, tl, tr, 0.010)
        if d < 0:
            ST.tube(cen, bl, br, 0.010)
        ST.tube(cen, tl, bl, 0.010); ST.tube(cen, tr, br, 0.010)
        for side in (-1, 1):
            ST.tube(cen, corner(yf - d * 0.016, side, True, 0.05), corner(yt + d * 0.012, side, False, 0.05), 0.009)
        # top (and, aft, bottom) bay diagonals: the truss's plan bracing (round 3: diagonals from 16 mm behind the frame, so their sides do
        # not pass through the longerons' end caps at the frame - the cockpit z-fight row)
        ST.tube(cen, corner(yf - d * 0.016, -1, True, 0.05), corner(yt + d * 0.012, 1, True, 0.05), 0.008)
        if d < 0:
            ST.tube(cen, corner(yf - d * 0.016, 1, False, 0.05), corner(yt + d * 0.012, -1, False, 0.05), 0.008)
        inset = 0.0025 + 0.0015 + STRINGER_H / 2
        ys = yp - d * rr.uniform(*BR.STUB_SHORT)
        ra, ca = fus_inset_ring(ys, inset)
        rb, cb = fus_inset_ring(yw - d * 0.003, inset)
        for deg in STRINGER_DEG:
            k = min(range(len(RING_ANG)), key=lambda i: abs(((RING_ANG[i] - deg + 180) % 360) - 180))
            a, b = ra[k], rb[k]
            mid = (a + b) / 2
            if mid.z > ca.z and abs(abs(mid.x) - S.GUN_X) < TROUGH_W + 0.04:
                continue                                    # gun trough (front bay)
            if d > 0 and abs(mid.x) < NC_.FOOT_WX + 0.04 and mid.z < NC_.FOOT_Z + 0.03:
                continue                                    # footwell box (front bay floor)
            up = ((ca + cb) / 2 - mid)
            up = up - V((0, 1, 0)) * up.y
            ST.sec_tube(cen, a, b, STRINGER_W, STRINGER_H, up.normalized())
    bay_fittings(cen, NC_)


def fus_struct():
    """structure children of the three fuselage parts: inner skins are added by the caller; here bulkheads, formers, stubs, truss."""
    eng, cen, rear = MeshBuf(), MeshBuf(), MeshBuf()
    # ---- fus_engine: firewall 65 mm ahead of the split (closed, both faces) + 4 engine-bearer tube stubs reaching aft through the tear
    r, c = fus_inset_ring(0.065, 0.004)
    if IN.FIREWALL_ON_ENGINE:                   # 1.8.3: the firewall stays with the fuselage (fus_center tank bulkhead); the engine shows
        ST.disc(eng, r, c, 'structure', V((0, -1, 0)))
    import random as _rnd
    rr = _rnd.Random(1922)
    for side in (-1, 1):
        for top in (True, False):
            p = corner(0.065, side, top, 0.06)
            if BREAK_R8O:                       # 2026-11-22: no stubs through the y 0 break (they crossed it by 30-42 mm); the engine
                continue                        # body's own bearer A-frames (internals_r183, aft pick-ups y 0.035) end short of it
            else:
                ST.tube(eng, p, p + V((0, -0.095 - 0.012 * top, 0)), 0.016)     # ends 23-35 mm ahead of the fus_center tank bulkhead
    if ENGINE_BODY is not None:                 # 1.8.3 (user: "look at how stock aircraft use internal parts"): engine body + tank
        ENGINE_BODY(eng)
    # ---- fus_center: front tank bulkhead at -0.065 and rear bulkhead at -1.44 (closed), longeron stubs at both ends
    if BREAK_R8O:
        # 2026-11-22 (user: "The Nimrod and FD-32 need to be changed as well"): no tank / rear bulkhead discs. Open frame ring 0.10 m in
        # from each break (y 0 / -1.5) and four longeron stubs from it ending 15-40 mm short of the plane (r8o / B-25H v3 pattern).
        # The fuel tank stays in fus_engine; the cockpit's own walls (YA / YB, nimrod_cockpit) close the cockpit, now on both faces.
        for yb, d, yp in ((S.ENGINE_AFT_Y - BREAK_SETBACK, 1, S.ENGINE_AFT_Y), (S.CENTRE_AFT_Y + BREAK_SETBACK, -1, S.CENTRE_AFT_Y)):
            r, c = fus_inset_ring(yb, 0.002)
            ST.frame_ring(cen, r, c, depth=0.03, thick=0.014)
            for side in (-1, 1):
                for top in (True, False):
                    p = corner(yb, side, top, 0.05)
                    ST.tube(cen, p, V((p.x, yp - d * rr.uniform(*BR.STUB_SHORT), p.z)), 0.013)
        import nimrod_cockpit as NC_
        NC_.break_walls(cen, NC_.FOOT_WX, S.FLOOR_Z)     # the cockpit walls' break-facing sides (they faced the pilot only)
        # 2026-11-27 round 2 (review of round 1: the break-facing cockpit walls read as one uniform full-section plate, the rejected
        # 'divider'): the walls are dark now (nimrod_cockpit.BREAK_WALL_MAT) and the bay between the break and the wall gets the
        # fuselage structure one sees on the B-25H v3 ends: the four longerons run on from the 0.10 m frame to the wall, a
        # second open frame stands 20 mm in front of the wall, and stringers run along the liner from 15-40 mm short of the plane to
        # that frame (none through the footwell box).
        cen_stringers(cen, rr, NC_)
    for yb, d in (() if BREAK_R8O else ((-0.065, 1), (-1.44, -1))):
        r, c = fus_inset_ring(yb, 0.004)
        ST.disc(cen, r, c, 'structure', V((0, d, 0)), both=False)
        # the cockpit side of the tank bulkhead keeps the dark cockpit lining look (1.2.3 footwell); the rear one is plain structure
        fan_cap(cen, [p - V((0, d * 0.003, 0)) for p in r], c - V((0, d * 0.003, 0)), 'ck_lining' if yb > -1 else 'structure', V((0, -d, 0)))
        ST.frame_ring(cen, [p for p in r], c, depth=0.03, thick=0.014)
        for side in (-1, 1):
            for top in (True, False):
                p = corner(yb, side, top, 0.05)
                L = 0.10 + 0.025 * (side > 0) + 0.015 * top
                ST.tube(cen, p, p + V((0, d * L, 0)), 0.013)
    # ---- fus_rear: former at -1.56, Warren truss (4 longerons, cross tubes, side diagonals) to the sternpost, longeron stubs forward
    ST.frame_ring(rear, *fus_inset_ring(-1.565, 0.002), depth=0.03, thick=0.009)      # 1.4.0: rim into the inner skin, 9 mm thick (no grazing slit)
    st = [-1.565, -1.62, -2.30, -2.90, -3.50, -4.10]
    for side in (-1, 1):
        for top in (True, False):
            pts = [corner(y, side, top, 0.045) for y in st] + [corner(-4.40, side, top, 0.03)]
            if BREAK_R8O:                              # 2026-11-22: the longeron stub ends 15-40 mm short of the -1.5 break
                pts[0] = V((pts[0].x, S.CENTRE_AFT_Y - rr.uniform(*BR.STUB_SHORT), pts[0].z))
            else:
                pts[0] = pts[0] + V((0, 0.10, 0))      # stub through the tear into fus_center (hidden while intact)
            for a, b in zip(pts, pts[1:]):
                ST.tube(rear, a, b, 0.012, caps=True)
    for k, y in enumerate(st[1:-1] + [-4.10]):
        tl, tr, bl, br = corner(y, -1, True), corner(y, 1, True), corner(y, -1, False), corner(y, 1, False)
        ST.tube(rear, tl, tr, 0.009)                    # top cross tube
        if not HOOK_SLOT or not (SLOT_Y[1] - 0.05 < y < SLOT_Y[0] + 0.05):
            ST.tube(rear, bl, br, 0.009)                # bottom cross tube (none over the hook slot)
        ST.tube(rear, tl, bl, 0.009); ST.tube(rear, tr, br, 0.009)     # verticals
    for a, b in zip(st[1:-1], st[2:]):
        for side in (-1, 1):
            ST.tube(rear, corner(a, side, True), corner(b, side, False), 0.008)     # side diagonals (Warren)
    # hook slot lining: the inner skin edge strips close it; a light guide box over the slot
    return eng, cen, rear


# ------------------------------------------------------------------------------------------- engine details (fal props + fit)
def add_exhausts(mb):
    """fal Kestrel exhaust manifold per side: model +z (stubs) -> inboard, model +y (tail pipe) -> aft, model x -> up/down.
    Six stubs over y 1.70 .. 0.40 (the v1 stub positions), collector 0.045 m off the cowl side, tail pipe to y ~ -0.05."""
    lo_m, hi_m = PR.bbox('exhaust')
    for side in (-1, 1):
        ls = 1.75                         # model length 1.0 -> 1.75 m
        cs = 0.72                         # cross scale
        inward = V((-side, 0, 0))
        R = PR.axes(V((0, 0, side)), V((0, -1, 0)), inward, sx=cs, sy=ls, sz=cs)
        # model collector centre (x ~ 0, z ~ -0.05) at world (side*(hw + 0.040), y, 0.06)
        anchor_m = V((0.0, -0.5, -0.05))
        wy = 1.75
        hw = ST.fus_params(1.2)[0]
        aw = V((side * (hw + 0.028), wy, 0.06))

        PR.place(mb, 'exhaust', R, anchor_m, aw)        # no warp: bending the tail pipe in turned the collector inside out


def add_louvres(mb):
    """1.3.0b: the Kestrel cowling's row of raised louvres along the top of each side panel, as geometry (the louvre texture read as
    dotted print at game scale): 22 louvres per side, y 1.62 .. 0.57, each a wedge flush at its front edge and 7 mm proud at its
    aft edge (11 mm), opening aft (dark), painted with the livery."""
    z0, z1 = 0.155, 0.225
    for side in (-1, 1):
        for k in range(22):
            yf = 1.62 - k * 0.050
            yb = yf - 0.026
            def skin(y, z, out):
                w = ST.fus_half_width(y, z)
                return V((side * (w + out), y, z))
            f0, f1 = skin(yf, z0, -0.001), skin(yf, z1, -0.001)
            b0, b1 = skin(yb, z0 + 0.006, 0.011), skin(yb, z1 - 0.006, 0.011)
            bi0, bi1 = skin(yb, z0 + 0.006, -0.001), skin(yb, z1 - 0.006, -0.001)
            out = V((side, 0, 0))
            oriented_quad(mb, [f0, f1, b1, b0], 'paint', out + V((0, 0.35, 0)))                    # raised skin of the louvre
            oriented_quad(mb, [f1, b1, bi1], 'paint', V((0, 0, 1)))
            oriented_quad(mb, [f0, b0, bi0], 'paint', V((0, 0, -1)))
            oriented_quad(mb, [b0, b1, bi1, bi0], 'metal_dark', V((0, -1, 0)))                     # open aft face


GUN_BLAST_TUBES = False
GUN_FLASH_Y = 0.97      # 1.4.0: muzzle flash at the jacket's muzzle (the blast tubes are gone)


def gun_parts():
    """fal Vickers Mk III per side in its trough: muzzle end = model -y. Receiver (model y 0..0.5) thinned to fit under the decking
    in front of the cockpit breech casing (y -0.40 .. -0.02), cooling jacket (model y -0.5..0) along the trough (y -0.02 .. 0.62),
    hand-built blast tube in the trough to the trough exit (GUN_TROUGH_END_Y) with a flash cone."""
    mb = MeshBuf()
    for side in (-1, 1):
        x = side * S.GUN_X
        zc = S.GUN_Z - 0.005
        knots = [(-0.5, 0.95), (0.0, -0.03), (0.5, -0.40)]            # model y -> world y: jacket + muzzle attachment in the trough
        fy = PR.piecewise(knots)
        cross = (1, lambda t: 0.95)
        mx = -1 if side < 0 else 1
        R = PR.axes(V((mx, 0, 0)), V((0, 1, 0)), V((0, 0, 1)))
        anchor_m = V((-0.037, 0.0, 0.020))                             # jacket axis in the model
        # world = aw + R (S(p) - am) where S remaps y -> world y directly: use anchor y 0 and world y 0 offset
        # fal gun: the cooling jacket + muzzle (model y <= 0.02); the receiver under the decking is a plain gunmetal block (the fal
        # receiver thinned to fit there turned into 0.2 mm plates that z-fought in the cockpit view)
        PR.place(mb, 'vickers', R, anchor_m, V((x, 0.0, zc)), remap={1: fy}, cross=cross, keep=lambda vs: any(v[1] <= 0.02 for v in vs))
        box(mb, (x, -0.215, S.GUN_Z + 0.005), (0.07, 0.37, 0.09), 'gunmetal')
        # 1.4.0: with the blast tubes gone, one outboard facet of the fal jacket near y 0.12-0.27 is seen from behind (see-through check):
        # reversed twins 0.8 mm behind the jacket faces there
        keep_ = []
        for f in mb.faces:            # fal remesh needles: >0.35 m long, < 12 mm high (one lies across the jacket top, seen from behind)
            P_ = [mb.verts[i] for i in f['idx']]
            if f['mat'] == 'pr_vickers':
                L_ = max((P_[i_] - P_[i_ - 1]).length for i_ in range(len(P_)))
                A_ = sum(((P_[k_] - P_[0]).cross(P_[k_ + 1] - P_[0])).length / 2 for k_ in range(1, len(P_) - 1))
                if L_ > 0.35 and A_ / L_ < 0.006:
                    continue
            keep_.append(f)
        mb.faces = keep_
        if GUN_BLAST_TUBES:                                            # 1.3.x blast tube to the trough exit (user review 2: remove)
            cylinder(mb, V((x, 0.90, zc - 0.012)), V((x, S.GUN_TROUGH_END_Y - 0.05, zc - 0.006)), 0.016, N=10, mat='gunmetal')
            cylinder(mb, V((x, S.GUN_TROUGH_END_Y - 0.06, zc - 0.006)), V((x, S.GUN_TROUGH_END_Y, zc - 0.005)), 0.019, 0.025, N=10, mat='gunmetal')
            for yy in (1.15, 1.40):
                box(mb, (x, yy, zc - 0.028), (0.050, 0.02, 0.03), 'metal_dark')
    return mb


def build_radiator():
    """ventral radiator bath between the undercarriage legs (part of fus_engine); top embedded in the belly (v1 top -0.58 left a gap)."""
    mb = MeshBuf()
    ys = [0.74, 0.66, 0.40, 0.12, 0.02]
    prof = {0.74: (0.20, -0.62), 0.66: (0.27, -0.95), 0.40: (0.28, -0.985), 0.12: (0.26, -0.95), 0.02: (0.20, -0.62)}
    top = -0.48
    rings = []
    for y in ys:
        hw, zb = prof[y]
        rings.append([V((-hw, y, top)), V((-hw, y, zb + 0.03)), V((-hw + 0.03, y, zb)), V((hw - 0.03, y, zb)), V((hw, y, zb + 0.03)), V((hw, y, top))])
    loft(mb, rings, 'paint', closed=False, uvfunc=lambda ci, cj, j: (cj * 0.25, ys[ci]))
    for ra, rb_ in zip(rings, rings[1:]):                              # closed top (inside the belly): no open box seen from the engine bay
        oriented_quad(mb, [ra[0], ra[-1], rb_[-1], rb_[0]], 'radiator', V((0, 0, 1)))
    for r_, d_ in ((rings[0], 1), (rings[-1], -1)):
        c_ = sum(r_, V()) / len(r_)
        fan_cap(mb, r_, c_, 'paint', V((0, d_, 0)), uvfunc=lambda q: (q.x, q.z))
    for y, d in ((0.66, 1), (0.12, -1)):
        hw, zb = prof[y]
        oriented_quad(mb, [V((-hw + 0.02, y + d * 0.002, -0.60)), V((hw - 0.02, y + d * 0.002, -0.60)),
                           V((hw - 0.02, y + d * 0.002, zb + 0.02)), V((-hw + 0.02, y + d * 0.002, zb + 0.02))], 'radiator', V((0, d, 0)))
        for k in range(1, 9):                                          # matrix slats
            xx = -hw + 0.02 + k * (2 * hw - 0.04) / 9
            box(mb, (xx, y + d * 0.006, (zb - 0.60) / 2 + 0.01), (0.006, 0.008, abs(zb + 0.60) - 0.04), 'metal_dark')
    return mb


def add_nose_details(mb):
    box(mb, (0, 1.85, -0.60), (0.16, 0.30, 0.12), 'paint')            # carburettor intake (top embedded)
    box(mb, (0, 2.005, -0.62), (0.12, 0.012, 0.07), 'metal_dark')


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


def tip_round(x, x0, x1, le, te):
    if x <= x0:
        return le, te
    f = min((x - x0) / (x1 - x0), 1.0)
    shrink = 1 - math.sqrt(max(1 - f * f, 0.0))
    c = (le - te)
    lo = c * 0.94 * shrink
    return le - lo * 0.35, te + lo * 0.65


def up_station(ax, side=1):
    le, te = tip_round(ax, 4.55, S.UP_TIP_X + 0.02, S.UP_LE, S.UP_TE)
    return wing_station(side * ax, le, te, upper_z(ax))


def lo_station(ax, side=1):
    le, te = tip_round(ax, 4.0, S.LO_TIP_X + 0.02, S.LO_LE, S.LO_TE)
    return wing_station(side * ax, le, te, lower_z(ax))


def surf_pt(st, s, upper, embed=0.0):
    """point on the aerofoil surface at chord fraction s, moved `embed` into the section."""
    p = st.point(s, upper)
    return p - st.up * embed if upper else p + st.up * embed


def tip_cap(mb, rings_last, toward):
    ring = rings_last
    c = sum(ring, V()) / len(ring)
    fan_cap(mb, ring, c, 'paint', toward, uvfunc=lambda p: planar_uv(p, toward))


def wing_rib(mb, st, s_end, toward, n=10):
    """closed rib web (both faces) on the box contour of station st (0..s_end)."""
    from b25h_geom import box_ring
    ring, _ = box_ring(st, s_end, n)
    c = sum(ring, V()) / len(ring)
    ring = [p + (c - p).normalized() * 0.004 for p in ring]
    ST.disc(mb, ring, c, 'structure', toward)


def aft_rib(mb, st, toward):
    from b25h_geom import aft_ring
    ring, _ = aft_ring(st, S.AIL_HINGE_S, 4)
    c = sum(ring, V()) / len(ring)
    ring = [p + (c - p).normalized() * 0.003 for p in ring]
    section_cap(mb, ring, 'structure', toward)
    section_cap(mb, [p - V(toward).normalized() * 0.003 for p in ring], 'structure', -V(toward))


def spar_stubs(mb, st_a, st_b, toward_len, seed, s_list=(0.16, 0.62), jitter=0.04):
    """front and rear spar (I-section: two caps + web) from station st_a, `toward_len` (+ up to `jitter`) long toward st_b."""
    import random
    r = random.Random(seed)
    for s in s_list:
        L = toward_len + r.uniform(0.0, jitter)
        ua, la = surf_pt(st_a, s, True, 0.012), surf_pt(st_a, s, False, 0.012)
        d = (st_b.le - st_a.le); d.y = 0; d.z = 0; d = d.normalized()
        ub, lb = ua + d * L, la + d * L
        for p, q, up in ((ua, ub, st_a.up), (la, lb, st_a.up)):
            ST.sec_tube(mb, p, q, 0.05, 0.008, up)
        mid_a, mid_b = (ua + la) / 2, (ub + lb) / 2
        ST.sec_tube(mb, mid_a, mid_b, 0.006, (ua - la).length * 0.92, st_a.up)
    for s in (0.30, 0.45):                                              # rib cap-strip stubs on the upper skin
        a = surf_pt(st_a, s, True, 0.006)
        d = V((1 if st_b.le.x > st_a.le.x else -1, 0, 0))
        ST.sec_tube(mb, a, a + d * (toward_len * 0.6 + r.uniform(0, 0.03)), 0.014, 0.006, st_a.up)


def full_ring(st, n_box=12, n_aft=4):
    """one closed aerofoil ring with the same chord sampling as box_ring (0..hinge) + aft_ring (hinge..TE): upper TE -> LE, lower LE -> TE.
    The centre section and the outer panels' roots use it, so the rings at the x +-0.80 split are identical (complementary tear) and
    there is no internal wall pair at the hinge line."""
    from b25h_geom import cos_space
    hs = S.AIL_HINGE_S
    sb = cos_space(0.0, S_WALL, n_box)                   # 1.3.1: box to the cove wall, then the lip stations, then the aft piece
    sl = [S_LIP, hs]
    sa = [hs + (1 - hs) * k / n_aft for k in range(n_aft + 1)]
    up = [st.point(x, True) for x in reversed(sa[1:])] + [st.point(x, True) for x in reversed(sl)] + [st.point(x, True) for x in reversed(sb)]
    lo = [st.point(x, False) for x in sb[1:]] + [st.point(x, False) for x in sl] + [st.point(x, False) for x in sa[1:]]
    return up + lo


# 1.3.1 (game test: a bright red / green line along each aileron hinge = the 16-18 mm gap showing the lit 'structure' nose / wall):
# the wing box ends at a cove wall S_WALL, thin skin lips run aft over the aileron nose to 6 mm ahead of the hinge axis, and the
# aileron carries a round nose concentric with its hinge axis (child object: the aileron's own mesh / collider / lift point are
# unchanged). Visible slot ~6 mm; the cove wall, lip undersides and the aileron front face are the dark matte 'cove' material.
S_WALL = 0.666
S_LIP = 0.683


def lip(mb, sts, s_a, s_b_fn, upper, t=0.0025):
    """thin skin lip on the upper / lower surface from chord fraction s_a to s_b_fn(st) (closed: outer skin, inner face, edges)."""
    rows = []
    for st in sts:
        sb_ = s_b_fn(st)
        sa_ = s_a(st) if callable(s_a) else s_a
        ss = [sa_, (sa_ + sb_) / 2, sb_]
        o = [st.point(x, upper) for x in ss]
        i = [q - st.up * t if upper else q + st.up * t for q in o]
        rows.append((o, i))
    out_n = V((0, 0, 1)) if upper else V((0, 0, -1))
    sgn = 1 if sts[-1].span > sts[0].span else -1
    for (oa, ia), (ob, ib) in zip(rows, rows[1:]):
        for k in range(2):
            oriented_quad(mb, [oa[k], oa[k + 1], ob[k + 1], ob[k]], 'paint', out_n)
            oriented_quad(mb, [ia[k], ia[k + 1], ib[k + 1], ib[k]], 'cove', -out_n)
        oriented_quad(mb, [oa[2], ob[2], ib[2], ia[2]], 'cove', V((0, -1, 0)))
    for (o, i), d in ((rows[0], -1), (rows[-1], 1)):
        for k in range(2):
            oriented_quad(mb, [o[k], o[k + 1], i[k + 1], i[k]], 'cove', V((d * sgn, 0, 0)))


def axis_at(st, s_hinge, p0, axis):
    """the true hinge axis point in station st's plane, its chord fraction, and the local half-thicknesses there."""
    axis = V(axis).normalized()
    hm = st.point(s_hinge, True) * 0.5 + st.point(s_hinge, False) * 0.5
    c = p0 + axis * (hm - p0).dot(axis)
    sc = (c - st.le).dot(st.cdir) / st.chord
    return c, sc


def cs_body(mb, sts, s0_fn, n_aft=4):
    """control-surface body from a per-station front fraction s0_fn(st) to the TE: skin paint, flat front 'cove', paint end caps."""
    from b25h_geom import aft_ring, ring_arc_uv
    rings = [aft_ring(st, s0_fn(st), n_aft)[0] for st in sts]
    k = len(rings[0]) // 2
    loft(mb, rings, 'paint', face_mat=lambda i, j: 'cove' if j == k - 1 else 'paint', uvfunc=ring_arc_uv(rings, [st.span for st in sts]))
    sgn = 1 if sts[-1].span > sts[0].span else -1
    for r, d in ((rings[0], -1), (rings[-1], 1)):
        section_cap(mb, r, 'paint', V((d * sgn, 0, 0)), lambda q, d=d: planar_uv(q, V((1, 0, 0))))


def nose_mesh2(sts, s_hinge, s0_fn, p0, axis, wall_fn, rf=0.90):
    """round nose concentric with the true hinge axis (p0, axis), from the body's front (s0_fn) round the front of the axis;
    radius = 0.9 x the local half-thickness, never closer than 4 mm to the cove wall (wall_fn(st) = its chord fraction)."""
    mb = MeshBuf()
    rings = []
    for st in sts:
        c, sc = axis_at(st, s_hinge, p0, axis)
        f = -st.cdir; u = st.up
        hu, hl = st.point(sc, True) - c, st.point(sc, False) - c
        R = min(rf * min(hu.length, hl.length), (sc - wall_fn(st)) * st.chord - 0.006)
        arc = [c + (f * math.cos(math.radians(a)) + u * math.sin(math.radians(a))) * R for a in range(90, -91, -20)]
        rings.append([st.point(s0_fn(st), True), c + hu * 0.92] + arc + [c + hl * 0.92, st.point(s0_fn(st), False)])
    loft(mb, rings, 'paint')
    sgn = 1 if sts[-1].span > sts[0].span else -1
    for r, d in ((rings[0], -1), (rings[-1], 1)):
        fan_cap(mb, r, sum(r, V()) / len(r), 'paint', V((d * sgn, 0, 0)))
    return mb


def nose_mesh(sts, s_hinge, s_face, p0, axis):
    """round control-surface nose concentric with the hinge axis (p0, axis): per station an arc of radius 0.9 x the smaller hinge
    half-thickness from top to bottom ahead of the axis, joined to the surface's own skin at s_face (its front face)."""
    mb = MeshBuf()
    axis = V(axis).normalized()
    rings = []
    for st in sts:
        hm = st.point(s_hinge, True) * 0.5 + st.point(s_hinge, False) * 0.5
        c = p0 + axis * (hm - p0).dot(axis)                # the hinge axis point in this station's plane
        f = -st.cdir; u = st.up
        hu, hl = st.point(s_hinge, True) - c, st.point(s_hinge, False) - c
        R = 0.90 * min(hu.length, hl.length)
        arc = [c + (f * math.cos(math.radians(a)) + u * math.sin(math.radians(a))) * R for a in range(90, -91, -20)]
        rings.append([st.point(s_face, True), c + hu * 0.95] + arc + [c + hl * 0.95, st.point(s_face, False)])
    loft(mb, rings, 'paint')
    sgn = 1 if sts[-1].span > sts[0].span else -1
    for r, d in ((rings[0], -1), (rings[-1], 1)):
        fan_cap(mb, r, sum(r, V()) / len(r), 'paint', V((d * sgn, 0, 0)))
    return mb


def full_ring_aft_cap(st):
    """the part of full_ring behind the cove wall (s >= S_WALL), as a closed polygon (aileron bay inner rib)."""
    hs = S.AIL_HINGE_S
    sa = [hs + (1 - hs) * k / 4 for k in range(5)]
    ss = [S_WALL, S_LIP] + sa
    return [st.point(x, True) for x in reversed(ss)] + [st.point(x, False) for x in ss]


def full_loft(mb, sts):
    from b25h_geom import ring_arc_uv
    rings = [full_ring(st) for st in sts]
    loft(mb, rings, 'paint', uvfunc=ring_arc_uv(rings, [st.span for st in sts]))
    return rings


def full_rib(mb, st, toward):
    ring = full_ring(st)
    c = sum(ring, V()) / len(ring)
    ST.disc(mb, [p + (c - p).normalized() * 0.004 for p in ring], c, 'structure', toward)


def upper_panel(side):
    mb = MeshBuf()
    x0, x1 = S.UP_CENTRE_X, S.UP_TIP_X
    xs = [x0, x0 + SETBACK + 0.005, 1.2, 1.6, S.AIL_X[0], 2.4, 3.0, S.STRUT_X, 3.9, 4.4, 4.55, 4.65, 4.75, 4.83, S.AIL_X[1], 4.98, 5.05, 5.10, x1]
    sts = [up_station(ax, side) for ax in xs]
    if side < 0:
        sts = list(reversed(sts))
    out_dir = V((side, 0, 0))
    inb = [s_ for s_ in sts if abs(s_.span) <= S.AIL_X[0] + 1e-4]
    outb = [s_ for s_ in sts if abs(s_.span) >= S.AIL_X[0] - 1e-4]
    full_loft(mb, inb)
    from b25h_geom import aft_ring
    st_bay = up_station(S.AIL_X[0], side)
    poly = full_ring_aft_cap(st_bay)
    ST.disc(mb, poly, sum(poly, V()) / len(poly), 'cove', out_dir)                      # aileron bay inner rib (both faces)
    rings = surface(mb, outb, 0.0, S_WALL, n_box=12, hinge_mat='cove')                  # box to the cove wall
    tip_cap(mb, rings[-1] if side > 0 else rings[0], out_dir)
    sel = [s_ for s_ in sts if abs(s_.span) >= S.AIL_X[1] - 1e-4]
    rr = surface(mb, sel, S_WALL, 1.0, n_aft=4, front_mat='cove')
    tip_cap(mb, rr[-1] if side > 0 else rr[0], out_dir)
    section_cap(mb, rr[0] if side > 0 else rr[-1], 'cove', -out_dir)                   # aileron bay outer rib
    am = MeshBuf()
    asel = [s for s in sts if S.AIL_X[0] - 1e-4 <= abs(s.span) <= S.AIL_X[1] + 1e-4]
    hs = [s.point(S.AIL_HINGE_S, True) * 0.5 + s.point(S.AIL_HINGE_S, False) * 0.5 for s in asel]
    hinge_in = hs[0] if side > 0 else hs[-1]
    # 1.3.1: the hinge axis runs along the constant-chord hinge line (1.2.3 took its outer end on the rounded tip station, skewing the
    # axis up to 76 mm forward of the real hinge at x 4.4: the aileron swung through the wing box when deflected)
    sto = wing_station(side * S.AIL_X[1], S.UP_LE, S.UP_TE, upper_z(S.AIL_X[1]))
    hinge_out = sto.point(S.AIL_HINGE_S, True) * 0.5 + sto.point(S.AIL_HINGE_S, False) * 0.5
    ax_ = hinge_out - hinge_in
    s0 = lambda st: max(S.AIL_HINGE_S + 0.012, axis_at(st, S.AIL_HINGE_S, hinge_in, ax_)[1] + 0.012 / st.chord)
    bsel = list(asel)                                                                   # 6 mm spanwise clearance to the bay ribs
    bsel[0] = up_station(abs(asel[0].span) + 0.006 * (1 if abs(asel[0].span) < abs(asel[-1].span) else -1), side)
    bsel[-1] = up_station(abs(asel[-1].span) + 0.006 * (1 if abs(asel[-1].span) < abs(asel[0].span) else -1), side)
    cs_body(am, bsel, s0)
    bt = bsel[-1] if abs(bsel[-1].span) > abs(bsel[0].span) else bsel[0]
    bounds_keeper(am, f'aileron_{"L" if side < 0 else "R"}', (bt.point(s0(bt), True) + bt.point(s0(bt), False)) * 0.5, bt.span)
    for up_ in (True, False):                                                           # skin lips over the aileron nose
        lip(mb, asel, S_WALL, lambda st: axis_at(st, S.AIL_HINGE_S, hinge_in, ax_)[1] - 0.008 / st.chord, up_)
    upper_panel.nose = nose_mesh2(bsel, S.AIL_HINGE_S, s0, hinge_in, ax_, lambda st: S_WALL, rf=0.86)
    return mb, am, hinge_in, hinge_out


def hinge_brackets(mb, hs, side, face_back=0.018):
    """three hinge lugs on the control surface's front face (seen when it is shot off): from `face_back` behind the hinge line
    (inside the surface) to 3 mm behind it, i.e. 15 mm proud of the front face."""
    for k in sorted({1, len(hs) // 2, len(hs) - 2}):
        p = hs[k]
        box(mb, p + V((0, -(face_back + 0.012) / 2 - 0.0015, 0)), (0.025, face_back + 0.012 - 0.003, 0.03), 'metal_dark')


UP_CUTOUT = False


def centre_fittings(mb):
    """1.4.0 (shot 9/10): two lifting hooks on top of the centre section (x +-0.42, y 0.80) and two hand holes near the trailing edge
    (x +-0.054..0.202, y -0.181..-0.123, top and bottom); in the cabane object (outside the wing collider)."""
    for s_ in (-1, 1):
        x = s_ * 0.421
        st = wing_station(x, S.UP_LE, S.UP_TE, S.UP_Z)
        base = surf_pt(st, (S.UP_LE - 0.80) / (S.UP_LE - S.UP_TE), True)
        box(mb, base + V((0, 0, 0.003)), (0.04, 0.09, 0.012), 'metal_dark')
        pts = [base + V((0, 0.03, 0)), base + V((0, 0.03, 0.12)), base + V((0, 0.0, 0.17)), base + V((0, -0.045, 0.165)), base + V((0, -0.06, 0.13))]
        for a_, b_ in zip(pts, pts[1:]):
            cylinder(mb, a_, b_, 0.008, N=6, mat='metal_dark', cap0=True, cap1=True)
        x0, x1, y0, y1 = 0.054, 0.202, -0.181, -0.123
        for upper in (True, False):
            q = []
            for (xx, yy) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                stq = wing_station(s_ * xx, S.UP_LE, S.UP_TE, S.UP_Z)
                p = surf_pt(stq, (S.UP_LE - yy) / (S.UP_LE - S.UP_TE), upper)
                q.append(p + V((0, 0, 0.0012 if upper else -0.0012)))
            oriented_quad(mb, q, 'cove', V((0, 0, 1 if upper else -1)))


def upper_centre():
    mb = MeshBuf()
    xs = [-S.UP_CENTRE_X, -(S.UP_CENTRE_X - SETBACK - 0.005), -0.55, -S.UP_CUTOUT_X - 0.03, -S.UP_CUTOUT_X, -0.15, 0.0, 0.15, S.UP_CUTOUT_X,
          S.UP_CUTOUT_X + 0.03, 0.55, S.UP_CENTRE_X - SETBACK - 0.005, S.UP_CENTRE_X]
    sts = []
    for x in xs:
        cut = UP_CUTOUT and abs(x) <= S.UP_CUTOUT_X + 1e-4     # 1.4.0: no trailing-edge cut-out (user review 2: the real centre section is continous)
        te = S.UP_CUTOUT_TE + (0.03 if abs(x) < 0.2 else 0.0) * (1 - abs(x) / 0.2) if cut else S.UP_TE
        sts.append(wing_station(x, S.UP_LE, te, S.UP_Z))
    full_loft(mb, sts)
    return mb, sts


def lower_panel(side):
    mb = MeshBuf()
    xs = [S.LO_ROOT_X, 0.9, 1.4, S.RACK_X - 0.15, S.RACK_X + 0.15, 2.4, S.STRUT_X_LO, S.STRUT_X, 3.8, 4.05, 4.2, 4.32, 4.40, S.LO_TIP_X]
    sts = [lo_station(ax, side) for ax in xs]
    if side < 0:
        sts = list(reversed(sts))
    rings = surface(mb, sts, 0.0, 0.999, n_box=14, hinge_mat='paint')
    tip_cap(mb, rings[-1] if side > 0 else rings[0], V((side, 0, 0)))
    return mb, (sts[0] if side > 0 else sts[-1])


def root_fillet(root_st, s_end, side, inner_fn, n_box=14, name_seed=1, ring=None):
    """child mesh joining a lifting surface's root section to the fuselage skin: the root ring (shared, no cap) and an inner ring whose
    points sit on the fuselage skin (inner_fn(point) -> point moved onto the skin and 10 mm into it). Inner end: closed rib + spar root lugs.
    ring (1.4.0): the part's own root ring when it is not a plain box_ring (same layout: upper end -> LE -> lower end, 2 n_box + 1 points)."""
    from b25h_geom import box_ring
    mb = MeshBuf()
    if ring is None:
        ring, _ = box_ring(root_st, s_end, n_box)
    else:
        n_box = (len(ring) - 1) // 2
    inner = [inner_fn(p) for p in ring]
    for k in range(1, n_box + 1):
        up_, lo_ = inner[n_box - k], inner[n_box + k]
        if lo_.z > up_.z - 0.004:
            inner[n_box + k] = V((lo_.x, lo_.y, up_.z - 0.004))
    span = abs(root_st.span)
    loft(mb, [inner, ring] if side > 0 else [ring, inner], 'paint',
         uvfunc=lambda ci, cj, j, rr=([inner, ring] if side > 0 else [ring, inner]): (rr[ci][cj].x, rr[ci][cj].y))
    c = sum(inner, V()) / len(inner)
    # outward skin: the loft's own orientation test can fail between such different rings; check against the fillet axis and flip
    cr = sum(ring, V()) / len(ring)
    score = 0.0
    for f in mb.faces:
        P = [mb.verts[i] for i in f['idx']]
        fc = sum(P, V()) / len(P)
        n = (P[1] - P[0]).cross(P[-1] - P[0])
        ax = cr - c
        t = max(0.0, min(1.0, (fc - c).dot(ax) / max(ax.length_squared, 1e-9)))
        score += n.dot(fc - (c + ax * t))
    if score < 0:
        for f in mb.faces:
            f['idx'] = list(reversed(f['idx']))
            if f['uv']:
                f['uv'] = list(reversed(f['uv']))
    if BREAK_R8O:
        # 2026-11-22: no root disc at the fuselage skin (it closed the whole root). The fillet is the first part of the lined root
        # cavity: dark skin edge at the inner ring, liner (3 mm in) with its first 25 mm metal_dark, fabric_in on to 10 mm past the root
        # ring (under the panel's own liner, lining_cavity).
        inw = BR._inward(ring, V((1, 0, 0)))
        off = [v * min(0.003, 0.3 * D) for v, D in inw]
        L0 = [p + o for p, o in zip(inner, off)]
        tb = [min(BR.BAND / max((r_ - i_).length, 1e-6), 0.9) for r_, i_ in zip(ring, inner)]
        Lb = [i_ + (r_ - i_) * t_ + o for i_, r_, t_, o in zip(inner, ring, tb, off)]
        L1 = [r_ + V((side * 0.010, 0, 0)) + o for r_, o in zip(ring, off)]
        loft(mb, [L0, Lb], 'metal_dark', outward=False)
        loft(mb, [Lb, L1], 'fabric_in', outward=False)
        annulus(mb, inner, L0, 'metal_dark', V((-side, 0, 0)))
        return mb
    ST.disc(mb, inner, c, 'structure', V((-side, 0, 0)), both=True)
    for s in (0.16, 0.62):                                              # spar root lugs on the inner rib
        k = int(round(s / s_end * n_box))
        p = (ring[n_box - k] + ring[n_box + k]) / 2 if 0 < k < n_box else c
        pi = inner_fn(p)
        box(mb, pi + V((-side * 0.012, 0, 0)), (0.03, 0.03, 0.05), 'structure')
    return mb


def lining_cavity(mb, panel, side, x0, close, setback, stub_seed, t=0.004, stub_st=None):
    """2026-11-22: the open root cavity of a lifting surface whose root fillet (mb) carries the break: the panel's liner from its root
    (|x| x0) to a bay-end wall `close` out (liner paint), an open cap strip `setback` out, spar stubs from it ending 15-40 mm short of
    the root ring. All in the fillet child (not in the collider; the panel's paint mesh and the livery atlas are untouched)."""
    p0, nn = V((side * x0, 0, 0)), V((-side, 0, 0))
    mb.extend(BR.liner(panel, [(p0, nn)], t=t, close=close, band=0.0, mats=('paint', 'cove'), edge_mat='fabric_in'))
    BR.cap_strip(mb, panel, p0, nn, setback)
    BR.bay_wall(mb, panel, p0, nn, close, mat='fabric_in', both=False)
    if stub_st is not None:
        spar_stubs(mb, stub_st(x0 + setback), stub_st(max(x0 - 0.1, 0.05)), setback - BR.STUB_SHORT[1], stub_seed,
                   jitter=BR.STUB_SHORT[1] - BR.STUB_SHORT[0])


def lower_root_inner(side):
    def f(p):
        y, z = p.y, p.z
        w = ST.fus_half_width(y, z)
        if w - 0.010 >= 0.20:
            return V((side * (w - 0.010), y, z))
        # under the rounded belly corner: stop at x 0.20 and lift onto the skin (10 mm inside)
        return V((side * 0.20, y, max(z, ST.fus_z(0.20, y, top=False) + 0.010)))
    return f


def interplane_struts(mb, side):
    x = S.STRUT_X
    stl, stu = lo_station(S.STRUT_X_LO, side), up_station(x, side)
    sf_l, sr_l = 0.16, 0.62          # front / rear spar (rear upper end ahead of the aileron hinge at 0.70)
    sf_u, sr_u = 0.16, 0.62
    fl, rl = surf_pt(stl, sf_l, True), surf_pt(stl, sr_l, True)
    fu, ru = surf_pt(stu, sf_u, False), surf_pt(stu, sr_u, False)
    for a, b in ((fl, fu), (rl, ru)):
        strut(mb, a - stl.up * 0.015, b + stu.up * 0.015, 0.080, 0.028)
        fitting(mb, a, stl.up, (0.06, 0.09, 0.010))
        fitting(mb, b, -stu.up, (0.06, 0.09, 0.010))
        attach(f'struts_{"L" if side < 0 else "R"}', a, [f'wing_lower_{"L" if side < 0 else "R"}'])
        attach(f'struts_{"L" if side < 0 else "R"}', b, [f'wing_upper_{"L" if side < 0 else "R"}'])
    if side < 0:                                                        # pitot head on the left front strut: short clamp arm, tube close
        p = fl.lerp(fu, 0.62)                                           # alongside the strut, aluminium (v1: a black bar 0.1 m off the strut)
        arm = p + V((-0.042, 0.0, 0.0))
        box(mb, p + V((-0.004, 0, 0)), (0.040, 0.05, 0.03), 'alu')     # strut clamp
        cylinder(mb, p, arm, 0.008, N=8, mat='alu')
        cylinder(mb, arm + V((0, -0.05, 0)), arm + V((0, 0.24, 0)), 0.010, N=10, mat='alu')
        cylinder(mb, arm + V((0, 0.24, 0)), arm + V((0, 0.29, 0)), 0.010, 0.004, N=10, mat='alu')
    return fl, rl, fu, ru


def cabane(mb):
    for side in (-1, 1):
        stc = wing_station(side * 0.56, S.UP_LE, S.UP_TE, S.UP_Z)
        feet = {}
        for yb, s in ((0.62, (S.UP_LE - 1.02) / (S.UP_LE - S.UP_TE)), (-0.10, (S.UP_LE - 0.22) / (S.UP_LE - S.UP_TE))):
            zf = ST.fus_z(0.36, yb, top=True)
            foot = V((side * 0.36, yb, zf))
            head = surf_pt(stc, s, False)
            nf = (foot - V((0, yb, zf - 0.3))).normalized()
            strut(mb, foot - nf * 0.018, head + stc.up * 0.015, 0.06, 0.024)
            fitting(mb, foot, nf, (0.05, 0.07, 0.012))
            fitting(mb, head, -stc.up, (0.05, 0.07, 0.010))
            attach('cabane', foot, ['fus_center', 'fus_engine'])
            attach('cabane', head, ['wing_upper_C'])
            feet[yb] = (foot, head, nf)
        f0, h1 = feet[0.62][0], feet[-0.10][1]
        strut(mb, f0 - feet[0.62][2] * 0.018, h1 + stc.up * 0.015, 0.05, 0.02)


def rigging(mb, side, fl, rl, fu, ru):
    """flying wires (lower root -> upper strut top, doubled), landing wires (upper centre root -> lower strut foot), incidence wire,
    drag wire to the nose. Every end is on a fitting (on a surface or a strut end)."""
    L = 'L' if side < 0 else 'R'
    rx = 0.62
    stl = lo_station(rx, side); stc = wing_station(side * 0.56, S.UP_LE, S.UP_TE, S.UP_Z)
    roots_lo = [surf_pt(stl, 0.17, True), surf_pt(stl, 0.72, True)]
    roots_up = [surf_pt(stc, 0.20, False), surf_pt(stc, 0.74, False)]
    for k, (lo, up) in enumerate(zip(roots_lo, roots_up)):
        top, foot = (fu, fl) if k == 0 else (ru, rl)
        fitting(mb, lo, stl.up, (0.04, 0.06, 0.010))
        for d in (-0.012, 0.012):
            wire(mb, lo + V((0, d, 0.004)), top + V((0, d, -0.008)))
        wire(mb, up - V((0, 0, 0.004)), foot + V((0, 0, 0.008)))
        attach(f'rigging_{L}', lo, [f'wing_lower_{L}', f'wing_lower_{L}_root'])
        attach(f'rigging_{L}', top, [f'struts_{L}', f'wing_upper_{L}'])
        attach(f'rigging_{L}', up, ['wing_upper_C', 'cabane'])
        attach(f'rigging_{L}', foot, [f'struts_{L}', f'wing_lower_{L}'])
    wire(mb, fl + V((0, 0, 0.03)), ru - V((0, 0, 0.03)))
    attach(f'rigging_{L}', fl + V((0, 0, 0.03)), [f'struts_{L}'])
    attach(f'rigging_{L}', ru - V((0, 0, 0.03)), [f'struts_{L}'])
    nose = ST.fus_surface_point(side, 1.55, -0.20, embed=0.012)
    wire(mb, nose, fl + V((0, 0.0, 0.01)))
    fitting(mb, ST.fus_surface_point(side, 1.55, -0.20), V((side, 0, 0)), (0.012, 0.05, 0.04))
    attach(f'rigging_{L}', nose, ['fus_engine'])


# ------------------------------------------------------------------------------------------- tail
def stab(side):
    mb = MeshBuf()
    xs = [0.16, 0.45, 0.8, 1.1, 1.3, 1.42, 1.50, 1.55, S.STAB_TIP_X]
    sts = []
    for ax in xs:
        le, te = tip_round(ax, 1.20, S.STAB_TIP_X + 0.01, S.STAB_LE, S.STAB_TE)
        sts.append(Station(side * ax, V((side * ax, le, S.STAB_Z)), V((0, -1, 0)), V((0, 0, 1)), max(le - te, 0.04), 0.085, m=0.0))
    if side < 0:
        sts = list(reversed(sts))
    hs = (S.STAB_LE - S.STAB_HINGE) / (S.STAB_LE - S.STAB_TE)
    sw = hs - 0.052 / (S.STAB_LE - S.STAB_TE)                                         # 1.3.1 cove wall 52 mm ahead of the hinge
    rings = surface(mb, sts, 0.0, sw, n_box=8, hinge_mat='cove')
    tip_cap(mb, rings[-1] if side > 0 else rings[0], V((side, 0, 0)))
    em = MeshBuf()
    esel = [s for s in sts if abs(s.span) >= 0.30]
    hinge = [s.point(hs, True) * 0.5 + s.point(hs, False) * 0.5 for s in esel]
    sto = Station(side * S.STAB_TIP_X, V((side * S.STAB_TIP_X, S.STAB_LE, S.STAB_Z)), V((0, -1, 0)), V((0, 0, 1)), S.STAB_LE - S.STAB_TE, 0.085, m=0.0)
    h_out = sto.point(hs, True) * 0.5 + sto.point(hs, False) * 0.5                      # true axis: the straight hinge line
    if side > 0:
        hinge[-1] = h_out
    else:
        hinge[0] = h_out
    h_in = hinge[0] if side > 0 else hinge[-1]
    ax_ = (h_out - h_in)
    s0 = lambda st: max(hs + 0.01, axis_at(st, hs, h_in, ax_)[1] + 0.022 / st.chord)    # front corners stay behind the axis plane at 26 deg

    def st_at(axx):
        le, te = tip_round(axx, 1.20, S.STAB_TIP_X + 0.01, S.STAB_LE, S.STAB_TE)
        return Station(side * axx, V((side * axx, le, S.STAB_Z)), V((0, -1, 0)), V((0, 0, 1)), max(le - te, 0.04), 0.085, m=0.0)
    bsel = list(esel)
    i_in, i_out = (0, -1) if side > 0 else (-1, 0)
    bsel[i_in] = st_at(abs(esel[i_in].span))
    bsel[i_out] = st_at(S.STAB_TIP_X - 0.006)
    cs_body(em, bsel, s0)
    bt = bsel[i_out]
    bounds_keeper(em, f'elevator_{"L" if side < 0 else "R"}', (bt.point(s0(bt), True) + bt.point(s0(bt), False)) * 0.5, bt.span)
    for up_ in (True, False):
        lip(mb, sts, sw, lambda st: min(axis_at(st, hs, h_in, ax_)[1], hs) - 0.012 / st.chord, up_)
    stab.nose = nose_mesh2(bsel, hs, s0, h_in, ax_, lambda st: sw, rf=0.86)
    stab.lip_root = (sts[0] if side > 0 else sts[-1], hs, h_in, ax_)
    stab.sw = sw
    # bracing strut: stab underside (fitting) -> fuselage side low (fitting), both ends on their surfaces
    bm = MeshBuf()
    st85 = Station(side * 0.85, V((side * 0.85, S.STAB_LE, S.STAB_Z)), V((0, -1, 0)), V((0, 0, 1)), S.STAB_LE - S.STAB_TE, 0.085, m=0.0)
    top = surf_pt(st85, 0.205, False)
    yb, zb = -3.80, -0.30
    foot = ST.fus_surface_point(side, yb, zb)
    strut(bm, foot - V((side * 0.012, 0, 0)), top + V((0, 0, 0.012)), 0.04, 0.016)
    fitting(bm, foot, V((side, 0, 0)), (0.012, 0.05, 0.04))
    fitting(bm, top, V((0, 0, -1)), (0.04, 0.05, 0.010))
    L = 'L' if side < 0 else 'R'
    attach(f'stab_strut_{L}', foot, ['fus_rear'])
    attach(f'stab_strut_{L}', top, [f'stab_{L}'])
    root_st = sts[0] if side > 0 else sts[-1]
    return mb, em, hinge, bm, root_st, hs


def stab_root_inner(side):
    def f(p):
        w = ST.fus_half_width(p.y, p.z)
        if p.y < -4.45 or w <= 0.012:
            return V((side * 0.012, p.y, p.z))
        return V((side * max(w - 0.010, 0.012), p.y, p.z))
    return f


def fin_rudder():
    fm = MeshBuf()
    zs = [S.FIN_ROOT_Z - 0.05, 0.45, 0.65, 0.85, 1.05, 1.20, 1.30, S.FIN_TOP_Z]
    sts = []
    for z in zs:
        f = (z - S.FIN_ROOT_Z) / (S.FIN_TOP_Z - S.FIN_ROOT_Z)
        le = S.FIN_LE_ROOT + (-4.44 - S.FIN_LE_ROOT) * max(f, 0) ** 1.25
        le = max(min(le, S.FIN_LE_ROOT), S.FIN_HINGE + 0.03)
        sts.append(Station(z, V((0, le, z)), V((0, -1, 0)), V((1, 0, 0)), max(le - S.FIN_HINGE, 0.03), 0.10, m=0.0))
    rings = surface(fm, sts, 0.0, 0.999, cap1=V((0, 0, 1)), cap_mat='paint', n_box=8, hinge_mat='cove')
    r0 = rings[0]
    c = sum(r0, V()) / len(r0)
    fs = MeshBuf()
    ST.disc(fs, r0, c, 'structure', V((0, 0, -1)), both=True)         # root rib (seen when shot off)
    for s in (0.2, 0.75):                                               # fin post stubs into the fuselage
        p = sts[0].point(s, True) * 0.5 + sts[0].point(s, False) * 0.5
        ST.sec_tube(fs, p, p - V((0, 0, 0.07 + 0.02 * s)), 0.02, 0.03, V((1, 0, 0)))
    fin_rudder.struct = fs
    rm = MeshBuf()
    rz = [S.RUDDER_BOTTOM_Z, -0.36, -0.25, -0.1, 0.06, 0.4, 0.7, 0.95, 1.12, 1.24, 1.32, 1.36]
    rs = []
    for z in rz:
        span = S.FIN_HINGE - 0.006 - S.RUDDER_TE
        if z > 0.40:
            f = min((z - 0.40) / 0.97, 0.995)
            te = S.FIN_HINGE - 0.006 - span * math.sqrt(1 - f * f)
        elif z < 0.06:
            f = min((0.06 - z) / 0.48, 0.995)
            te = S.FIN_HINGE - 0.006 - span * math.sqrt(1 - f * f)
        else:
            te = S.RUDDER_TE
        rs.append(Station(z, V((0, S.FIN_HINGE - 0.006, z)), V((0, -1, 0)), V((1, 0, 0)), max(S.FIN_HINGE - 0.006 - te, 0.05), 0.09, m=0.0))
    surface(rm, rs, 0.0, 0.999, cap0=V((0, 0, -1)), cap1=V((0, 0, 1)), cap_mat='paint', n_box=8, hinge_mat='structure')
    return fm, rm


# ------------------------------------------------------------------------------------------- undercarriage, hook (fal props)
def wheel_from_prop(mb, axle, radius, width, name='wheel', centre_m=None, mirror=False):
    """fal wheel: model axle = x, round in y/z. Scaled so the tyre radius is exactly `radius` (Unity reads the radius from the
    mesh bounds: extents.y = radius) and the width `width`."""
    lo, hi = PR.bbox(name)
    cm = centre_m if centre_m is not None else (lo + hi) / 2
    rad_m = max(hi.z - cm.z, cm.z - lo.z)
    s = radius / rad_m
    sx = width / (hi.x - lo.x)
    R = PR.axes(V((-1 if mirror else 1, 0, 0)), V((0, 1, 0)), V((0, 0, 1)), sx=sx, sy=s, sz=s)
    return PR.place(mb, name, R, cm, V(axle))


def main_gear(side):
    ax = V((side * S.MAIN_AXLE[0], S.MAIN_AXLE[1], S.MAIN_AXLE[2]))
    st = MeshBuf()
    L = 'L' if side < 0 else 'R'
    for (x, y, w, t) in ((0.40, 1.02, 0.085, 0.05), (0.38, 0.18, 0.05, 0.03)):
        ztop = ST.fus_z(x, y, top=False)
        topp = V((side * x, y, ztop))
        nrm = (topp - V((0, y, ztop + 0.3))).normalized()
        foot = ax + V((-side * 0.05, 0.02 if y > 0.6 else -0.02, 0.10 if y > 0.6 else 0.06))
        strut(st, topp - nrm * 0.02, foot, w, t)
        fitting(st, topp, nrm, (0.06, 0.08, 0.014))
        attach(f'gear_main_{L}_strut', topp, ['fus_engine', 'fus_center'])
    cylinder(st, ax + V((-side * 0.07, 0, 0)), V((0, ax.y, ax.z + 0.02)), 0.022, N=8, mat='metal_dark')
    cylinder(st, ax + V((side * 0.0, 0, 0)), ax + V((-side * 0.10, 0, 0)), 0.03, N=8, mat='metal_dark')
    wh = MeshBuf()
    wheel_from_prop(wh, ax, S.WHEEL_R, 0.155, mirror=side < 0)
    return st, wh, ax


def tail_gear():
    ax = V(S.TAIL_AXLE)
    lo, hi = PR.bbox('tailwheel_wheel')
    cm = (lo + hi) / 2
    rad_m = (hi.z - lo.z) / 2
    s = S.TAILWHEEL_R / rad_m
    wh = MeshBuf()
    R = PR.axes(V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1)), sx=s, sy=s, sz=s)
    PR.place(wh, 'tailwheel_wheel', R, cm, ax)
    st = MeshBuf()
    _, fhi = PR.place(st, 'tailwheel_fork', R, cm, ax)
    # post from the fork top up into the fuselage bottom (stern frame)
    ftop = ax + R @ (V((0.0, 0.127, 0.25)) - cm)
    zf = ST.fus_z(0.0, ftop.y, top=False)
    cylinder(st, ftop - V((0, 0, 0.02)), V((ftop.x, ftop.y, zf + 0.05)), 0.018, N=10, mat='metal_dark')
    fitting(st, V((0, ftop.y, zf)), V((0, 0, -1)), (0.07, 0.07, 0.014))
    attach('gear_tail_strut', V((0, ftop.y, zf)), ['fus_rear'])
    return st, wh, ax


def hook_mesh():
    """fal arrester hook in its STOWED pose: hinge fitting at HOOK_PIVOT, bar aft (tip up by HOOK_STOW_UP), claw pointing down.
    Model: hinge fork at y -0.5, claw at y +0.5 curving to +z; length stretched to HOOK_LEN in the tube only."""
    mb = MeshBuf()
    p0 = V(S.HOOK_PIVOT)
    a = math.radians(S.HOOK_STOW_UP)
    d = V((0, -math.cos(a), math.sin(a)))                                # hinge -> tip (aft, slightly up)
    up = V((0, math.sin(a), math.cos(a)))
    cs = 0.90
    # model y -> distance along the bar from the hinge: hinge bolt (model ~ -0.47) at 0, claw tip (0.5) at HOOK_LEN
    f = PR.piecewise([(-0.47, 0.0), (-0.30, 0.17 * cs), (0.25, S.HOOK_LEN - 0.25 * cs), (0.5, S.HOOK_LEN)])
    R = Matrix((V((1, 0, 0)) * cs, d, -up * cs)).transposed()
    PR.place(mb, 'tailhook_v2', R, V((0.0, 0.0, -0.04)), p0, remap={1: f})
    return mb


# ------------------------------------------------------------------------------------------- propeller (unchanged from v1)
def build_prop():
    parts = []
    hub = V((0, S.PROP_Y, 0))
    sp = N4.spinner_v140()          # 1.4.0: pointed spinner with a ring joint and the Hucks starter dog (was a round dome)
    parts.append(Part('prop_hub', 'prop', hub, sp, info=dict(kind='prop_hub', note='spin axis = Unity +Z; spinner + blade roots')))
    for k, sgn in ((1, 1), (2, -1)):
        bm = MeshBuf()
        rad = V((0, 0, sgn))
        tang = V((sgn, 0, 0))
        stations = []
        for r in (0.165, 0.29, 0.42, 0.55, 0.70, 0.85, 1.00, 1.15, 1.30, 1.42, 1.50, 1.56, 1.60, 1.625, 1.643):
            f = r / S.PROP_R
            chord = N4.interp(N4.BLADE_CHORD, r)        # 1.4.0: reference paddle planform (near-parallel, round tip)
            twist = math.radians(10 + 34 * (0.18 / f) ** 0.9 if f > 0.12 else 55)
            thick = (0.055 if f < 0.25 else 0.11 * chord / 0.25 + 0.012)
            c = hub + rad * r
            fwd = V((0, 1, 0))
            cdir = (tang * math.cos(twist) - fwd * math.sin(twist)).normalized()
            up = cdir.cross(rad).normalized()
            if up.dot(fwd) < 0:
                up = -up
            stations.append(Station(r, c - cdir * chord * 0.35, cdir, up, chord, min(thick / max(chord, 0.05), 0.35), m=0.04))
        surface(bm, stations, 0.0, 0.999, cap0=-rad, cap1=rad, cap_mat='prop', n_box=8, hinge_mat='prop', uv=False)
        for f_ in bm.faces:
            f_['mat'] = 'prop'
        parts.append(Part(f'prop_blade_{k}', 'prop_hub', hub, bm, frame=frame_x(V((1, 0, 0)) * sgn, rad),
                          info=dict(kind='prop_blade', note='local +Y (Unity) = radial, +Z = forward')))
    return parts


# ------------------------------------------------------------------------------------------- collect
def _inner_mat_fus(f, c):
    return 'interior' if c.y > -0.26 else 'fabric_in'


def build_exterior():
    ATTACH.clear()
    parts = []
    fus = build_fuselage()
    tear = tear_fuselage(fus)
    eng_s, cen_s, rear_s = fus_struct()
    # inner skins (structure children): whole fus_engine / fus_rear, fus_center outside the cockpit box (the cockpit walls line it)
    ye, yc = S.ENGINE_AFT_Y, S.CENTRE_AFT_Y
    fus_ends = {'fus_engine': [(V((0, ye, 0)), V((0, -1, 0)))], 'NIMROD1': [(V((0, ye, 0)), V((0, 1, 0))), (V((0, yc, 0)), V((0, -1, 0)))],
                'fus_rear': [(V((0, yc, 0)), V((0, 1, 0)))]}
    for nm, sm, sel in (('fus_engine', eng_s, None), ('NIMROD1', cen_s, lambda c: not (-1.40 < c.y < -0.36)), ('fus_rear', rear_s, None)):
        if BREAK_R8O:
            # 2026-11-22: the inner skin ends with a 25 mm metal_dark band at every break (seam backing, r8o); in fus_center it now
            # reaches under the cockpit lining (the cockpit walls YA / YB are 0.22 m from the breaks: no bare skin back between them)
            if nm == 'NIMROD1':
                sel = lambda c: not (-1.20 < c.y < -0.30)
            sm.extend(BR.liner(fus[nm], fus_ends[nm], t=0.0025, inner=_inner_mat_fus, select=sel, edge_mat='structure'))
            continue
        tmp = MeshBuf(); tmp.verts = list(fus[nm].verts); tmp.faces = [dict(f) for f in fus[nm].faces]
        n0 = len(tmp.faces)
        ST.double_skin(tmp, t=0.0025, mats=('paint',), inner=_inner_mat_fus, select=sel)
        add = MeshBuf(); add.verts = tmp.verts; add.faces = tmp.faces[n0:]
        sm.extend(add)
    tmp = MeshBuf(); tmp.verts = list(fus['NIMROD1'].verts); tmp.faces = [dict(f) for f in fus['NIMROD1'].faces]; n0 = len(tmp.faces)
    ST.double_skin(tmp, t=0.001, mats=('paint',), inner=_inner_mat_fus, select=lambda c: (-1.40 < c.y < -0.06) and c.z > 0.42)
    add = MeshBuf(); add.verts = tmp.verts; add.faces = tmp.faces[n0:]; cen_s.extend(add)
    add_exhausts(fus['fus_engine'])
    add_louvres(fus['fus_engine'])
    fus['fus_engine'].extend(N4.radiator_v140())          # 1.4.0: reference radiator (slats, round openings)
    fus['fus_engine'].extend(N4.oil_cooler())             # 1.4.0: finned oil cooler under the nose (was the carburettor box)
    fus['fus_engine'].extend(gun_parts())

    parts.append(Part('fus_center', 'NIMROD1_root', (0, -0.75, 0), fus['NIMROD1']))
    parts.append(Part('fus_engine', 'fus_center', (0, 1.10, 0), fus['fus_engine']))
    parts.append(Part('fus_rear', 'fus_center', (0, -2.80, 0), fus['fus_rear']))
    parts.append(Part('sight_ringbead', 'fus_engine', S.RING_SIGHT_C, N4.ring_bead(),
                      info=dict(kind='sight', note='1.4.0 ring-and-bead sight on the cowling (cockpit-layer copy in Unity); not in the fus_engine collider')))
    parts.append(Part('hook_fittings', 'fus_rear', S.HOOKV_PIVOT, N4.hook_belly_fittings(),
                      info=dict(kind='fittings', note='1.4.0 A-frame hinge brackets + stowage catch; not in the fus_rear collider')))
    parts.append(Part('fus_engine_struct', 'fus_engine', (0, 0.0, 0), eng_s, info=dict(kind='structure', note='firewall, bearer stubs, inner skin; not in the collider')))
    parts.append(Part('fus_center_struct', 'fus_center', (0, -0.75, 0), cen_s, info=dict(kind='structure', note='tank / rear bulkheads, longeron stubs, inner skin')))
    parts.append(Part('fus_rear_struct', 'fus_rear', (0, -2.8, 0), rear_s, info=dict(kind='structure', note='Warren tube truss, former, inner skin')))
    # upper wing centre + tear at x = +-0.80 with set-back ribs and spar stubs
    uc, ucs = upper_centre()
    up_panels = {}; up_noses = {}
    for side in (-1, 1):
        up_panels[side] = upper_panel(side)
        up_noses[side] = upper_panel.nose
    for side in (-1, 1):
        nrm = V((side, 0, 0))
        for mb in (uc, up_panels[side][0]):
            ST.tear_mesh(mb, (side * WING_SPLIT_X, 0, 0), nrm, lambda v: v.y + 7.0 * v.z, TEAR_AMP_WING, 31 + side, 0.09,
                         mats=('paint', 'structure'), uv_axis=0, u_scale=side)
    ucs_struct = MeshBuf()
    if BREAK_R8O:
        # 2026-11-22: no full rib 75 mm in (one 'structure' plane over 93 % of the section). Liner from each break to a bay-end wall
        # WING_CAVITY in (|x| 0.40, liner paint), dark 25 mm band at the break, open cap-strip rib BREAK_SETBACK in, spar stubs from
        # it ending 15-40 mm short of the plane (the 1.9.12 stubs crossed it by 50-90 mm).
        ends = [(V((sd * WING_SPLIT_X, 0, 0)), V((sd, 0, 0))) for sd in (-1, 1)]
        ucs_struct.extend(BR.liner(uc, ends, select=lambda c: abs(c.x) > WING_SPLIT_X - WING_CAVITY + 1e-4))
        for side in (-1, 1):
            p0, nn = ends[(side + 1) // 2]
            BR.cap_strip(ucs_struct, uc, p0, nn, BREAK_SETBACK)
            BR.bay_wall(ucs_struct, uc, p0, nn, WING_CAVITY, mat='fabric_in', both=False)
            st_r = wing_station(side * (WING_SPLIT_X - BREAK_SETBACK), S.UP_LE, S.UP_TE, S.UP_Z)
            spar_stubs(ucs_struct, st_r, up_station(WING_SPLIT_X + 0.1, side), BREAK_SETBACK - BR.STUB_SHORT[1], 70 + side,
                       jitter=BR.STUB_SHORT[1] - BR.STUB_SHORT[0])
    else:
        tmp = MeshBuf(); tmp.verts = list(uc.verts); tmp.faces = [dict(f) for f in uc.faces]; n0 = len(tmp.faces)
        ST.double_skin(tmp, mats=('paint',))
        add = MeshBuf(); add.verts = tmp.verts; add.faces = tmp.faces[n0:]; ucs_struct.extend(add)
    for side in ((-1, 1) if not BREAK_R8O else ()):
        xr = WING_SPLIT_X - SETBACK
        st_r = wing_station(side * xr, S.UP_LE, S.UP_TE, S.UP_Z)
        full_rib(ucs_struct, st_r, V((side, 0, 0)))
        st_far = up_station(WING_SPLIT_X + 0.1, side)
        spar_stubs(ucs_struct, st_r, st_far, SETBACK + 0.05, 70 + side)
    cb = MeshBuf()
    cabane(cb)
    centre_fittings(cb)
    parts.append(Part('wing_upper_C', 'fus_center', (0, (S.UP_LE + S.UP_TE) / 2, S.UP_Z), uc))
    parts.append(Part('wing_upper_C_struct', 'wing_upper_C', (0, 0.5, S.UP_Z), ucs_struct, info=dict(kind='structure')))
    parts.append(Part('cabane', 'wing_upper_C', (0, 0.45, 0.75), cb, info=dict(kind='struts', note='not in the part collider')))
    for side, L in ((-1, 'L'), (1, 'R')):
        wm, am, hin, hout = up_panels[side]
        # outer panel: inner skin near the root, set-back rib, spar stubs into the centre section
        ps = MeshBuf()
        if BREAK_R8O:                   # 2026-11-22: as the centre section (liner to |x| 1.20, cap strip at 0.90, stubs short of 0.80)
            p0, nn = V((side * WING_SPLIT_X, 0, 0)), V((-side, 0, 0))
            ps.extend(BR.liner(wm, [(p0, nn)], close=WING_CAVITY))
            BR.cap_strip(ps, wm, p0, nn, BREAK_SETBACK)
            BR.bay_wall(ps, wm, p0, nn, WING_CAVITY, mat='fabric_in', both=False)
            st_r = up_station(WING_SPLIT_X + BREAK_SETBACK, side)
            spar_stubs(ps, st_r, wing_station(side * (WING_SPLIT_X - 0.1), S.UP_LE, S.UP_TE, S.UP_Z), BREAK_SETBACK - BR.STUB_SHORT[1],
                       80 + side, jitter=BR.STUB_SHORT[1] - BR.STUB_SHORT[0])
        else:
            tmp = MeshBuf(); tmp.verts = list(wm.verts); tmp.faces = [dict(f) for f in wm.faces]; n0 = len(tmp.faces)
            ST.double_skin(tmp, mats=('paint',), select=lambda c: abs(c.x) < WING_SPLIT_X + SETBACK + 0.006)
            add = MeshBuf(); add.verts = tmp.verts; add.faces = tmp.faces[n0:]; ps.extend(add)
            st_r = up_station(WING_SPLIT_X + SETBACK, side)
            full_rib(ps, st_r, V((-side, 0, 0)))
            spar_stubs(ps, st_r, wing_station(side * (WING_SPLIT_X - 0.1), S.UP_LE, S.UP_TE, S.UP_Z), SETBACK + 0.05, 80 + side)
        lm, lroot = lower_panel(side)
        fil = root_fillet(lroot, 0.999, side, lower_root_inner(side), n_box=14)
        if BREAK_R8O:                   # 2026-11-22: the root cavity: fillet liner (root_fillet) + panel liner to a bay-end wall 0.40 m out
            lining_cavity(fil, lm, side, abs(lroot.span), WING_CAVITY, BREAK_SETBACK, 90 + side,
                          stub_st=lambda x, sd=side: lo_station(x, sd))
        sm_ = MeshBuf(); rg = MeshBuf()
        fl, rl, fu, ru = interplane_struts(sm_, side)
        rigging(rg, side, fl, rl, fu, ru)
        parts.append(Part(f'wing_upper_{L}', 'wing_upper_C', (side * 2.9, 0.55, upper_z(2.9)), wm))
        parts.append(Part(f'wing_upper_{L}_struct', f'wing_upper_{L}', (side * 1.0, 0.55, upper_z(1.0)), ps, info=dict(kind='structure')))
        axis = (hout - hin).normalized() * side
        parts.append(Part(f'aileron_{L}', f'wing_upper_{L}', hin, am, frame=frame_x(axis), info=dict(kind='control', hinge_axis=tuple(axis))))
        parts.append(Part(f'aileron_{L}_nose', f'aileron_{L}', hin, up_noses[side], frame=frame_x(axis),
                          info=dict(kind='control_nose', note='round nose concentric with the hinge (1.3.1); not in the aileron collider')))
        parts.append(Part(f'wing_lower_{L}', 'fus_center', (side * 2.4, -0.30, lower_z(2.4)), lm))
        parts.append(Part(f'wing_lower_{L}_root', f'wing_lower_{L}', (side * 0.40, -0.30, lower_z(0.4)), fil,
                          info=dict(kind='fillet', note='root fillet to the fuselage skin; not in the wing collider')))
        parts.append(Part(f'struts_{L}', f'wing_upper_{L}', (side * S.STRUT_X, 0.30, 0.25), sm_, info=dict(kind='struts', note='interplane struts; not in the part collider')))
        parts.append(Part(f'rigging_{L}', f'wing_lower_{L}', (side * 1.9, 0.0, 0.2), rg, info=dict(kind='wires', note='flying/landing wires; not in the part collider')))
        # 1.4.0 tail (user review 2): reference planform, hinge -4.38 with horn balances, two struts per side + wires to the fin
        sm, em, enose, epiv, sroot = N4.stab_v140(side)
        NB_ = 9
        so_ = N4.frac(sroot, N4.WALL_OUT)
        fr_ = __import__('b25h_geom').cos_space(0.0, so_, NB_) + [so_ + (N4.frac(sroot, N4.WALL_IN) - so_) * k / 2 for k in (1, 2)]
        sfil = root_fillet(sroot, N4.frac(sroot, N4.WALL_IN), side, stab_root_inner(side), ring=N4.ring_to(sroot, fr_))
        if BREAK_R8O:                   # 2026-11-22: stab root cavity (liner, cap strip 0.06 m, bay-end wall 0.25 m beyond the root)
            lining_cavity(sfil, sm, side, abs(sroot.span), TAIL_CAVITY, TAIL_SETBACK, None, t=0.003)
        ist = Station(side * 0.11, V((side * 0.11, sroot.le.y, sroot.le.z)), sroot.cdir, sroot.up, sroot.chord, sroot.t, m=0.0)   # inside the tail cone
        for up_ in (True, False):
            lip(sfil, [ist, sroot] if side > 0 else [sroot, ist], lambda st: N4.frac(st, N4.WALL_IN), lambda st: N4.frac(st, S.ELEV_HINGE + 0.012), up_)
        bm, att_ = N4.tail_struts(side, N4.fin_half_thick)
        for a_ in att_:
            attach(*a_)
        parts.append(Part(f'stab_{L}', 'fus_rear', (side * 0.8, -4.0, S.STAB_Z), sm))
        parts.append(Part(f'stab_{L}_root', f'stab_{L}', (side * 0.12, -3.9, S.STAB_Z), sfil, info=dict(kind='fillet', note='root fillet to the tail cone')))
        parts.append(Part(f'stab_strut_{L}', f'stab_{L}', (side * 0.5, -3.9, -0.1), bm, info=dict(kind='struts')))
        eax = V((1, 0, 0))
        parts.append(Part(f'elevator_{L}', f'stab_{L}', epiv, em, frame=frame_x(eax), info=dict(kind='control', hinge_axis=tuple(eax))))
        parts.append(Part(f'elevator_{L}_nose', f'elevator_{L}', epiv, enose, frame=frame_x(eax),
                          info=dict(kind='control_nose', note='round nose concentric with the hinge; not in the elevator collider')))
        st, wh, axle = main_gear(side)
        parts.append(Part(f'gear_main_{L}_strut', 'fus_center', V((side * 0.40, 1.02, -0.60)), st))
        parts.append(Part(f'gear_main_{L}_wheel', f'gear_main_{L}_strut', axle, wh, info=dict(kind='wheel', radius=S.WHEEL_R)))
        parts.append(Part(f'hp_bomb_{L}', f'wing_lower_{L}', (side * S.RACK_X, S.RACK_Y, lower_z(S.RACK_X) - 0.075),
                          info=dict(kind='hardpoint', note='Cooper x2 rack mount (stock mount convention: origin at the rack top)')))
        parts.append(Part(f'navlight_{L}', f'wing_upper_{L}', (side * (S.UP_TIP_X - 0.06), 0.62, upper_z(S.UP_TIP_X) + 0.01), info=dict(kind='navlight')))
        parts.append(Part(f'muzzle_gun_{L}', 'fus_engine', (side * S.GUN_X, S.MUZZLE_Y, S.GUN_Z), frame=Quaternion(),
                          info=dict(kind='muzzle', note='bullet origin AHEAD of the prop disc (synchroniser); +Z Unity = forward')))
        parts.append(Part(f'flash_gun_{L}', 'fus_engine', (side * S.GUN_X, GUN_FLASH_Y, S.GUN_Z), info=dict(kind='muzzle_flash')))
        lp_ = (side * (S.UP_TIP_X + 0.004), 0.70, upper_z(S.UP_TIP_X) + 0.022)
        parts.append(Part(f'navlamp_{L}', f'wing_upper_{L}', lp_, N4.tip_lamp(side, lp_),
                          info=dict(kind='lamp', note='1.4.0 period wing-tip lamp (coloured glass, no light source); not in the wing collider')))
    fm, rm, rbal, fsts = N4.fin_rudder_v140()
    fs = MeshBuf()
    from b25h_geom import box_ring
    if BREAK_R8O:
        # 2026-11-22: no root rib in the plane (98.8 % of the view). Liner from the root up TAIL_CAVITY with the dark 25 mm band, an open
        # cap strip TAIL_SETBACK up, a bay-end wall (liner paint) at the top of the cavity; the post stubs end 15-30 mm above the root.
        z0 = min(p.z for p in fm.verts)
        p0, nn = V((0, 0, z0)), V((0, 0, -1))
        fs.extend(BR.liner(fm, [(p0, nn)], t=0.003, close=TAIL_CAVITY, mats=('paint', 'cove')))
        BR.cap_strip(fs, fm, p0, nn, TAIL_SETBACK)
        BR.bay_wall(fs, fm, p0, nn, TAIL_CAVITY, mat='fabric_in', both=False)
        import random as _rnd
        rr = _rnd.Random(1255)
        for s_ in (0.2, 0.75):
            a_ = fsts[0].point(s_, True) * 0.5 + fsts[0].point(s_, False) * 0.5
            b_ = fsts[1].point(s_, True) * 0.5 + fsts[1].point(s_, False) * 0.5
            p = a_ + (b_ - a_) * ((z0 + TAIL_SETBACK - a_.z) / max(b_.z - a_.z, 1e-6))
            ST.sec_tube(fs, p, V((p.x, p.y, z0 + rr.uniform(0.015, 0.030))), 0.02, 0.03, V((1, 0, 0)))
    else:
        r0, _ = box_ring(fsts[0], 0.999, 9)
        c = sum(r0, V()) / len(r0)
        ST.disc(fs, r0, c, 'structure', V((0, 0, -1)), both=True)         # root rib (seen when shot off)
        for s_ in (0.2, 0.75):                                              # fin post stubs into the fuselage
            p = fsts[0].point(s_, True) * 0.5 + fsts[0].point(s_, False) * 0.5
            ST.sec_tube(fs, p, p - V((0, 0, 0.07 + 0.02 * s_)), 0.02, 0.03, V((1, 0, 0)))
    parts.append(Part('fin', 'fus_rear', (0, -4.0, 0.7), fm))
    parts.append(Part('fin_struct', 'fin', (0, -4.0, 0.2), fs, info=dict(kind='structure', note='root rib + post stubs; not in the fin collider')))
    parts.append(Part('rudder', 'fin', (0, S.FIN_HINGE, 0.45), rm, frame=frame_x(V((0, 0, 1)), V((0, -1, 0))), info=dict(kind='control', hinge_axis=(0, 0, 1))))
    if RUDDER_BALANCE:
        parts.append(Part('rudder_balance', 'rudder', (0, S.FIN_HINGE, 0.45), rbal, frame=frame_x(V((0, 0, 1)), V((0, -1, 0))),
                          info=dict(kind='control_nose', note='1.4.0 mass-balance horn + aerial mast; not in the rudder collider')))
    # 1.4.0 tail SKID (the real aircraft had no tail wheel): arm + shock strut fixed on fus_rear (gear_tail_strut), shoe on the gear's
    # unsprung frame (gear_tail_skid); gear_tail_wheel is an empty at the unchanged axle (Unity: wheel radius S.TAILWHEEL_R from the contract)
    arm, shoe = N4.tail_skid()
    axle = V(S.TAIL_AXLE)
    parts.append(Part('gear_tail_strut', 'fus_rear', V((0, axle.y + 0.10, -0.30)), arm))
    parts.append(Part('gear_tail_wheel', 'gear_tail_strut', axle, None, info=dict(kind='wheel', radius=S.TAILWHEEL_R, note='1.4.0 skid: empty contact frame')))
    parts.append(Part('gear_tail_skid', 'gear_tail_strut', axle, shoe, info=dict(kind='skid_shoe', note='bottom on the old tyre contact point')))
    attach('gear_tail_strut', V((0, S.SKID_PIVOT[1], ST.fus_z(0.0, S.SKID_PIVOT[1], top=False))), ['fus_rear'])
    parts.append(Part('hook_visual', 'fus_rear', S.HOOKV_PIVOT, N4.hook_visual(),
                      info=dict(kind='hook_visual', stowed_up_deg=S.HOOKV_STOW, deployed_deg=S.HOOKV_DEPLOY, length=S.HOOKV_LEN,
                                note='1.4.0 visible A-frame; hinge at origin about local X; modelled stowed; driven by B25H.Instruments to follow the functional hook')))
    hp_ = MeshBuf()                     # 1.4.0: the functional hook's own mesh is never shown (Unity hides it): a 12-tri proxy bar
    box(hp_, V(S.HOOK_PIVOT) + V((0, -S.HOOK_LEN / 2, 0)), (0.02, S.HOOK_LEN, 0.02), 'metal_dark')
    parts.append(Part('tailhook', 'fus_center', S.HOOK_PIVOT, hp_, info=dict(kind='tailhook', length=S.HOOK_LEN, stowed_up_deg=S.HOOK_STOW_UP,
                      deployed_deg=S.HOOK_DEPLOY, note='hinge at origin; angle 0 = straight aft; stowed = +stow (tip up); mesh modelled stowed; fal hook')))
    parts.append(Part('hp_tailhook', 'fus_center', S.HOOK_PIVOT, info=dict(kind='hardpoint')))
    parts.append(Part('exhaust_point', 'fus_engine', (0.47, 1.0, 0.07), info=dict(kind='ir_source')))
    parts += build_prop()
    parts.insert(0, Part('prop', 'fus_engine', (0, S.PROP_Y, 0), None, info=dict(kind='prop_part')))
    # connectivity table for check_nimrod_model.py
    for p in parts:
        if p.name == 'fus_center':
            p.info = dict(p.info or {}, attach=ATTACH[:], tear=tear)
    return parts


# ------------------------------------------------------------------------------------------- 20 lb Cooper bomb (fal) + light rack
def cooper_parts():
    """fal 20 lb Cooper: 0.62 m long, 0.127 m body; pivot = suspension lug (top centre), nose +Y. Built at an out-of-the-way spot
    under the root; the Unity builder takes the meshes for the bomb / mount prefabs and deletes these objects from the aircraft."""
    base = V((0.0, -6.5, -2.5))
    bm = MeshBuf()
    lo, hi = PR.bbox('cooper_single')
    sl = 0.62 / (hi.y - lo.y)
    sc = 0.127 / 0.38
    R = PR.axes(V((-1, 0, 0)), V((0, -1, 0)), V((0, 0, 1)), sx=sc, sy=sl, sz=sc)
    # model body axis ~ (0, *, 0); body top z ~ +0.19 -> lug top at the base; nose (model -y) forward
    PR.place(bm, 'cooper_single', R, V((0.0, 0.0, 0.19)), base + V((0, 0.0, 0.0)))
    rm = MeshBuf()
    rb = V((3.0, -6.5, -2.5))
    box(rm, rb + V((0, 0, -0.012)), (0.40, 0.10, 0.024), 'metal_dark')
    for s in (-1, 1):
        box(rm, rb + V((s * 0.16, 0, -0.035)), (0.03, 0.08, 0.03), 'metal_dark')
        box(rm, rb + V((s * 0.16, 0.05, -0.065)), (0.10, 0.012, 0.012), 'metal_dark')
    return [Part('cooper_bomb', 'NIMROD1_root', base, bm, info=dict(kind='store_mesh', note='bomb prefab mesh (fal); removed from the aircraft')),
            Part('cooper_rack', 'NIMROD1_root', rb, rm, info=dict(kind='store_mesh', note='rack mesh for the Cooper x2 mount; bombs at x +-0.16, y -0.035 (Unity)'))]
