"""B-25H v3 cockpit: instrument panel with real gauge objects (needle / card transforms), MFD screen quads,
reflector gunsight, two seats, two control columns with ram's-horn yokes, two rudder-pedal bars.

Driver conventions (decompiled stock scripts, see docs/stock_damage_study.md and the contract):
  column  : ControlSurface (pitchRange) or Cockpit.Joystick X  -> rotation about local +X (Unity) = lateral axis
  yoke    : ControlSurface (rollRange)                         -> rotation about local +X = hub axis
  pedals  : ControlSurface (yawRange)                          -> rotation about local +X = vertical axis
  needles : Cockpit.Throttle (rotation=true) for throttle-proportional dials, or any custom driver
            -> localEulerAngles = (angle, 0, 0): local +X = toward the pilot, rest = 12 o'clock
"""
import math
from mathutils import Vector, Quaternion
import b25h_spec as S
from b25h_geom import V, MeshBuf, loft, fan_cap, annulus, oriented_quad, cylinder, box, circle_pts
from b25h_parts import Part
from b25h_v3 import frame_x, FLOOR_Z, CK

RK = math.radians(S.PANEL_RAKE)
PN = V((0, -math.cos(RK), math.sin(RK)))        # panel normal, toward the crew
PU = V((0, math.sin(RK), math.cos(RK)))         # panel "up" (in the panel plane)
PANEL_FACE_Y0, PANEL_FACE_Z0 = S.PANEL_Y - 0.02 * math.cos(RK), 0.70 + 0.02 * math.sin(RK)


def panel_pt(x, z, off=0.0):
    t = (z - PANEL_FACE_Z0) / math.cos(RK)
    return V((x, PANEL_FACE_Y0 + math.sin(RK) * t, z)) + PN * off


GRID = 8      # gauges texture = 8 x 8 cells (cell k: column k % 8, row k // 8, row 0 at v = 0)
# id, x, z, radius, face cell, movers: list of (object suffix, kind, cell)
GAUGES = [
    ('airspeed',   -0.48, 0.840, 0.042, 0, [('needle', 'needle', 62)]),
    ('attitude',   -0.35, 0.840, 0.042, 1, [('card', 'card', 10)]),
    ('altimeter',  -0.22, 0.840, 0.042, 2, [('needle', 'needle', 62), ('needle_short', 'short', 63)]),
    ('heading',    -0.35, 0.715, 0.042, 3, [('card', 'card', 11)]),
    ('vsi',        -0.22, 0.715, 0.042, 4, [('needle', 'needle', 62)]),
    ('fuel',       -0.48, 0.715, 0.042, 5, [('needle', 'needle', 62)]),
    ('manifold_L',  0.27, 0.840, 0.042, 6, [('needle', 'needle', 62)]),
    ('manifold_R',  0.39, 0.840, 0.042, 7, [('needle', 'needle', 62)]),
    ('rpm_L',       0.27, 0.715, 0.042, 8, [('needle', 'needle', 62)]),
    ('rpm_R',       0.39, 0.715, 0.042, 9, [('needle', 'needle', 62)]),
    ('oil_press',   0.50, 0.840, 0.028, 12, []),
    ('oil_temp',    0.50, 0.750, 0.028, 13, []),
    ('cyl_temp',    0.50, 0.660, 0.028, 14, []),
    ('hydraulic',  -0.05, 0.605, 0.028, 15, []),
    ('flaps_pos',   0.05, 0.605, 0.028, 16, []),
    ('gear_pos',    0.15, 0.605, 0.028, 17, []),
]
# needle angle (deg, clockwise seen by the pilot, from 12 o'clock) = (value - v0) * sweep / (v1 - v0)
GAUGE_SCALE = {
    'airspeed': dict(value='indicated airspeed', unit='mph', v0=0, v1=400, sweep=320),
    'altimeter': dict(value='altitude, long needle (1000 ft per turn)', unit='ft', v0=0, v1=1000, sweep=360),
    'altimeter_short': dict(value='altitude, short needle (10000 ft per turn)', unit='ft', v0=0, v1=10000, sweep=360),
    'vsi': dict(value='vertical speed', unit='ft/min', v0=0, v1=6000, sweep=170, note='descent = anticlockwise (negative)'),
    'fuel': dict(value='fuel remaining', unit='%', v0=0, v1=100, sweep=270),
    'manifold_L': dict(value='manifold pressure, left engine', unit='inHg', v0=10, v1=75, sweep=300),
    'manifold_R': dict(value='manifold pressure, right engine', unit='inHg', v0=10, v1=75, sweep=300),
    'rpm_L': dict(value='engine rpm, left', unit='rpm', v0=0, v1=3500, sweep=300),
    'rpm_R': dict(value='engine rpm, right', unit='rpm', v0=0, v1=3500, sweep=300),
    'attitude': dict(value='bank (card roll) and pitch (card offset)', unit='deg',
                     note='card angle = -bank; card local +Y (Unity) offset = -0.0015 m per deg of pitch up'),
    'heading': dict(value='heading (compass card)', unit='deg', note='card angle = -heading (current heading at 12 o\'clock)'),
}
MFDS = [('mfd_center', 0.03, 0.780, 0.26, 0.20, 'main tac screen (Cockpit.tacScreenRender)'),
        ('mfd_left', -0.35, 0.570, 0.24, 0.16, 'pilot side tablet'),
        ('mfd_right', 0.33, 0.570, 0.22, 0.15, 'navigator side tablet')]


def cell_uv(cell, lu, lv):
    """lu, lv in [-1, 1] -> UV inside the cell (2 % margin)."""
    cu, cv = (cell % GRID) / GRID, (cell // GRID) / GRID
    h = 0.5 / GRID * 0.96
    return (cu + 0.5 / GRID + lu * h, cv + 0.5 / GRID + lv * h)


def disc_uv(mb, c, rt, up, r, cell, n, off, N=24, mat='gauges'):
    """flat disc facing n with UVs filling a gauges cell."""
    ci = mb.v(c + n * off)
    pts = [(math.cos(2 * math.pi * k / N), math.sin(2 * math.pi * k / N)) for k in range(N)]
    vi = [mb.v(c + n * off + (rt * x + up * y) * r) for x, y in pts]
    for k in range(N):
        tri = [ci, vi[k], vi[(k + 1) % N]]
        P0 = [mb.verts[t] for t in tri]
        uvs = [cell_uv(cell, 0, 0), cell_uv(cell, *pts[k]), cell_uv(cell, *pts[(k + 1) % N])]
        if (P0[1] - P0[0]).cross(P0[2] - P0[0]).dot(n) < 0:
            tri, uvs = [tri[0], tri[2], tri[1]], [uvs[0], uvs[2], uvs[1]]
        mb.face(tri, mat, uvs, True)


def needle_mesh(nm, c, rt, up, r, kind, mcell):
    L = r * (0.86 if kind == 'needle' else 0.55)
    wdt = 0.0032 if kind == 'needle' else 0.0045
    o = PN * (0.008 if kind == 'needle' else 0.0075)
    tip = c + up * L + o
    tail = c - up * (0.22 * r) + o
    pts = [tail - rt * wdt, tail + rt * wdt, c + up * (0.7 * L) + rt * wdt * 0.8 + o, tip, c + up * (0.7 * L) - rt * wdt * 0.8 + o]
    uvq = [cell_uv(mcell, -0.8, -0.8), cell_uv(mcell, 0.8, -0.8), cell_uv(mcell, 0.8, 0.6), cell_uv(mcell, 0, 0.9), cell_uv(mcell, -0.8, 0.6)]
    vids = [nm.v(p) for p in pts]
    for a, b, cc in ((0, 1, 2), (0, 2, 3), (0, 3, 4)):
        tri = [vids[a], vids[b], vids[cc]]
        P0 = [nm.verts[t] for t in tri]
        uvs = [uvq[a], uvq[b], uvq[cc]]
        if (P0[1] - P0[0]).cross(P0[2] - P0[0]).dot(PN) < 0:
            tri, uvs = [tri[0], tri[2], tri[1]], [uvs[0], uvs[2], uvs[1]]
        nm.face(tri, 'gauges', uvs, False)
    disc_uv(nm, c, rt, up, 0.006, mcell, PN, 0.0095, N=10)           # hub cap


def build_cockpit():
    parts = []
    m = MeshBuf()
    y0, y1 = 2.66, S.PANEL_Y
    hw = 0.66
    box(m, (0, (y0 + y1) / 2, FLOOR_Z - 0.015), (2 * hw, y1 - y0, 0.03), CK)
    for s in (-1, 1):
        box(m, (s * (hw + 0.005), (y0 + y1) / 2, 0.47), (0.01, y1 - y0, 0.74), CK)
        for y in (2.95, 3.35, 3.75, 4.10):
            box(m, (s * (hw - 0.025), y, 0.47), (0.04, 0.03, 0.74), CK)
        for z in (0.30, 0.60):
            box(m, (s * (hw - 0.015), (y0 + y1) / 2, z), (0.02, y1 - y0, 0.025), CK)
        box(m, (s * (hw - 0.09), 3.45, 0.43), (0.16, 0.90, 0.12), CK)
        for k in range(4):
            cylinder(m, V((s * (hw - 0.09) + 0.03 * (k - 1.5), 3.25 + 0.15 * k, 0.49)),
                     V((s * (hw - 0.09) + 0.03 * (k - 1.5), 3.25 + 0.15 * k, 0.56)), 0.012, N=6, mat='metal_dark')
    from b25h_interior import section_panel
    for rect in ((-1.0, -0.24, FLOOR_Z, 2.0), (0.24, 1.0, FLOOR_Z, 2.0), (-0.24, 0.24, 1.05, 2.0)):
        section_panel(m, y0, rect, CK)
    q = Quaternion(V((1, 0, 0)), -RK)
    box(m, (0, y1, 0.70), (1.10, 0.04, 0.44), CK, rot=q)
    box(m, (0, y1 - 0.03, 0.42), (0.40, 0.10, 0.14), CK)
    box(m, (0, y1 + 0.06, 0.945), (0.92, 0.20, 0.03), CK)
    box(m, (0, y1 - 0.04, 0.93), (0.92, 0.04, 0.035), CK)
    box(m, (0, y1 - 0.04, (FLOOR_Z + 0.36) / 2), (1.10, 0.03, 0.36 - FLOOR_Z), CK)   # lower panel closing the space under the panel
    quad_levers = throttle_quadrant(m)
    box(m, (0.38, 2.92, 0.30), (0.40, 0.36, 0.04), CK)                        # navigator / loader table (aft right)
    gf = MeshBuf()
    rt, up = V((1, 0, 0)), PU
    movers = []
    for gid, x, z, r, cell, mv in GAUGES:
        c = panel_pt(x, z)
        ro = circle_pts(c + PN * 0.012, PN, r + 0.009, 24, ref=PU)
        ri = circle_pts(c + PN * 0.012, PN, r, 24, ref=PU)
        annulus(m, ro, ri, CK, PN)
        loft(m, [circle_pts(c, PN, r + 0.009, 24, ref=PU), ro], CK)
        loft(m, [ri, circle_pts(c + PN * 0.003, PN, r, 24, ref=PU)], CK, outward=False)
        disc_uv(gf, c, rt, up, r, cell, PN, 0.004)
        if not mv:
            continue
        fr = frame_x(PN, PU)                      # local X = toward the pilot, local Z(Blender) = panel up
        movers.append(Part(f'gauge_{gid}', 'cockpit_gauges', c, None, fr, info=dict(kind='gauge', face_cell=cell, radius=r)))
        for suf, kind, mcell in mv:
            nm = MeshBuf()
            if kind == 'card':
                disc_uv(nm, c, rt, up, r * 0.86, mcell, PN, 0.006, N=32)
            else:
                needle_mesh(nm, c, rt, up, r, kind, mcell)
            key = gid if suf in ('needle', 'card') else gid + '_short'
            sc = GAUGE_SCALE.get(key, {})
            info = dict(kind='gauge_' + kind, axis_local='+X (Unity) = toward the pilot',
                        rest="12 o'clock (local +Y Unity = panel up)", cell=mcell,
                        sign='Unity +angle about local +X = clockwise as seen by the pilot', **sc)
            if 'sweep' in sc:
                info['deg_per_unit'] = round(sc['sweep'] / (sc['v1'] - sc['v0']), 6)
            part = Part(f'gauge_{gid}_{suf}', f'gauge_{gid}', c, nm, fr, info=info)
            part.own_uv = True
            movers.append(part)
    mfd_parts = []
    for nmn, x, z, w, h, note in MFDS:
        c = panel_pt(x, z)
        for (a, b, ww, hh) in ((0, h / 2 + 0.008, w + 0.032, 0.016), (0, -h / 2 - 0.008, w + 0.032, 0.016),
                               (w / 2 + 0.008, 0, 0.016, h), (-w / 2 - 0.008, 0, 0.016, h)):
            box(m, c + rt * a + up * b + PN * 0.004, (ww, 0.012, hh), CK, rot=q)
        sm = MeshBuf()
        cs = c + PN * 0.007
        pts = [cs - rt * (w / 2) - up * (h / 2), cs + rt * (w / 2) - up * (h / 2), cs + rt * (w / 2) + up * (h / 2), cs - rt * (w / 2) + up * (h / 2)]
        oriented_quad(sm, pts, 'screen', PN, [(0, 0), (1, 0), (1, 1), (0, 1)])
        mp = Part(nmn, 'fus_cockpit', cs, sm, info=dict(kind='mfd', size_m=(w, h),
                                                         normal_unity=(0.0, round(PN.z, 4), round(PN.y, 4)),
                                                         uv='0-1; u -> pilot right, v -> panel up', note=note))
        mp.own_uv = True
        mfd_parts.append(mp)
    gs = MeshBuf()
    gx = S.COCKPIT_EYE[0]
    box(gs, (gx, 4.27, 0.985), (0.07, 0.12, 0.07), 'metal_dark')
    box(gs, (gx, 4.215, 1.025), (0.05, 0.05, 0.02), 'metal_dark')
    cmb = MeshBuf()
    cq = Quaternion(V((1, 0, 0)), math.radians(-35))
    cc = V((gx, 4.20, 1.062))
    cpts = [cc + cq @ V(p) for p in ((-0.035, 0, -0.027), (0.035, 0, -0.027), (0.035, 0, 0.027), (-0.035, 0, 0.027))]
    oriented_quad(cmb, cpts, 'glass', V((0, -1, 0.3)))
    oriented_quad(cmb, cpts, 'glass', V((0, 1, -0.3)))
    stations = []
    for side, L in ((-1, 'L'), (1, 'R')):
        stations += cockpit_station(side, L, m)
    parts.append(Part('cockpit_interior', 'fus_cockpit', (0, 3.45, FLOOR_Z), m))
    g = Part('cockpit_gauges', 'fus_cockpit', (0, y1, 0.70), gf, info=dict(note='static dial faces, own 0-1 UVs (8x8 grid) in `livery` slot'))
    g.own_uv = True
    parts.append(g)
    parts += movers + mfd_parts + stations + quad_levers
    parts.append(Part('gunsight_pilot', 'fus_cockpit', (gx, 4.27, 0.95), gs, info=dict(note='N-3B style reflector sight')))
    parts.append(Part('gunsight_combiner', 'gunsight_pilot', cc, cmb, info=dict(kind='combiner', note='glass quad; reticle material slot')))
    return parts


# ---- throttle quadrant (B-25 pattern): a low pedestal between the seats whose top stays below the panel's lower edge
# and the pilot's sight line to the centre screen; six short levers in slots - throttles (centre pair, flat grips),
# propeller pitch (ball knobs), mixture (small knobs, outboard) - plus the friction-lock wheel on the side.
QUAD_Y, QUAD_TOP = 3.84, 0.36            # pedestal centre y, height of the quadrant face at its centre
QUAD_TILT = math.radians(14)             # face slopes up toward the panel
THROTTLE_REST, THROTTLE_RANGE = 6.0, 40.0     # Blender deg about +X (+ = top aft) on top of the face normal (already 14 deg aft): idle 20 deg aft, full 20 deg forward


def ball(mb, c, r, mat, N=12, rings=6):
    c = V(c)
    rs = []
    for i in range(1, rings):
        th = math.pi * i / rings
        rs.append([c + V((r * math.sin(th) * math.cos(2 * math.pi * k / N), r * math.sin(th) * math.sin(2 * math.pi * k / N),
                          r * math.cos(th))) for k in range(N)])
    loft(mb, rs, mat)
    fan_cap(mb, rs[0], c + V((0, 0, r)), mat, (0, 0, 1))
    fan_cap(mb, rs[-1], c - V((0, 0, r)), mat, (0, 0, -1))


def quad_face_pt(x, dy):
    """point on the sloped quadrant face, dy along the slope from its centre (+ = toward the panel)."""
    return V((x, QUAD_Y + dy * math.cos(QUAD_TILT), QUAD_TOP + dy * math.sin(QUAD_TILT)))


def throttle_quadrant(m):
    q = Quaternion(V((1, 0, 0)), QUAD_TILT)
    hb = 0.30                                                                      # face length along the slope
    box(m, (0, QUAD_Y, (FLOOR_Z + QUAD_TOP - 0.05) / 2), (0.17, 0.26, QUAD_TOP - 0.05 - FLOOR_Z), CK)   # pedestal body
    up = q @ V((0, 0, 1))
    box(m, quad_face_pt(0, 0) - up * 0.03, (0.20, hb, 0.06), CK, rot=q)           # quadrant housing, sloped top
    for x in (-0.072, -0.042, -0.014, 0.014, 0.042, 0.072):                       # lever slots
        box(m, quad_face_pt(x, 0.0) + up * 0.0005, (0.008, 0.20, 0.002), 'metal_dark', rot=q)
    for k in (-1, 1):                                                              # side cheek plates
        box(m, quad_face_pt(k * 0.101, 0) - up * 0.025, (0.006, hb + 0.01, 0.07), 'metal_dark', rot=q)
    fw = quad_face_pt(0.115, -0.06) - up * 0.04                                    # friction-lock wheel
    cylinder(m, fw - V((0.012, 0, 0)), fw + V((0.012, 0, 0)), 0.026, N=16, mat='metal_dark')
    cylinder(m, fw - V((0.02, 0, 0)), fw + V((0.02, 0, 0)), 0.008, N=8, mat='metal_dark')
    rest = Quaternion(V((1, 0, 0)), math.radians(THROTTLE_REST))
    # static levers at mid travel: prop pitch (ball knobs), mixture (small knobs, outboard)
    for x, ln, knob, mat in ((-0.042, 0.11, 0.016, 'rubber'), (0.042, 0.11, 0.016, 'rubber'),
                             (-0.072, 0.09, 0.012, 'metal_dark'), (0.072, 0.09, 0.012, 'metal_dark')):
        p0 = quad_face_pt(x, 0.0) - up * 0.01
        d = Quaternion(V((1, 0, 0)), math.radians(-6)) @ up
        p1 = p0 + d * ln
        cylinder(m, p0, p1, 0.0055, N=10, mat='metal_dark')
        ball(m, p1 + d * knob * 0.8, knob, mat)
    # throttles: separate objects, local X = lateral axis (Cockpit.Throttle rotation: localEulerAngles.x = throttle * range)
    out = []
    for L, x in (('L', -0.014), ('R', 0.014)):
        piv = quad_face_pt(x, 0.0) - up * 0.02
        lm = MeshBuf()
        d = rest @ up
        tip = piv + d * 0.15
        cylinder(lm, piv - V((0.008, 0, 0)), piv + V((0.008, 0, 0)), 0.012, N=10, mat='metal_dark')     # pivot hub
        cylinder(lm, piv, tip, 0.0065, N=10, mat='metal_dark')
        g = tip + d * 0.012                                                         # flat grip, offset outboard
        gx = -1 if L == 'L' else 1
        box(lm, g + V((gx * 0.008, 0, 0)), (0.034, 0.022, 0.026), 'rubber', rot=rest @ q)
        out.append(Part(f'quadrant_throttle_{L}', 'fus_cockpit', piv, lm, Quaternion(),
                        info=dict(kind='throttle_lever', axis_local='+X (Unity) = right (lateral)', rest_deg=THROTTLE_REST,
                                  range_deg=THROTTLE_RANGE, drive='Cockpit.throttles[] rotation',
                                  sign='Unity +angle about local +X moves the lever top FORWARD (as the column); idle at rest')))
    return out


def seat_mesh(sx, sy, cush, floor, armour=True):
    sm = MeshBuf()
    q10 = Quaternion(V((1, 0, 0)), math.radians(-10))
    box(sm, (sx, sy, cush - 0.04), (0.46, 0.44, 0.08), CK)
    box(sm, (sx, sy, (floor + cush - 0.08) / 2), (0.36, 0.36, cush - 0.08 - floor), CK)
    box(sm, (sx, sy - 0.25, cush + 0.36), (0.50, 0.04, 0.72), 'metal_dark' if armour else CK, rot=q10)
    if armour:      # head armour kept below the canopy roof (its top at cush + 0.78)
        box(sm, (sx, sy - 0.30, cush + 0.70), (0.30, 0.05, 0.16), 'metal_dark', rot=q10)
    for s in (-1, 1):
        box(sm, (sx + s * 0.24, sy, cush + 0.10), (0.03, 0.40, 0.20), CK)
    return sm


def cockpit_station(side, L, interior):
    """seat + control column (pitch) + yoke wheel (roll) + rudder pedals (yaw) for one cockpit seat."""
    out = []
    key = 'pilot' if side < 0 else 'navigator'
    sx, sy = S.CREW[key]['seat']
    eye = V(S.CREW[key]['eye'])
    cush = eye.z - 0.65
    out.append(Part(f'cockpit_seat_{L}', 'fus_cockpit', (sx, sy, cush), seat_mesh(sx, sy, cush, FLOOR_Z, armour=True),
                    info=dict(kind='crew_seat', crew=key)))
    if side > 0:
        out.append(Part('crew_navigator_eye', 'fus_cockpit', eye, None, info=dict(kind='crew_eye', crew=key, look='+Z (Unity) forward')))
    if side > 0 and not S.FEATURES['copilot_controls']:
        return out
    # ---- column: floor pivot (local X = lateral pitch axis), tube, elbow to the hub
    piv = V((sx, 3.97, FLOOR_Z + 0.045))
    cm = MeshBuf()
    cylinder(cm, piv - V((0.045, 0, 0)), piv + V((0.045, 0, 0)), 0.035, N=16, mat='metal_dark')     # pivot boss
    top, elb, hub = V((sx, 3.93, 0.60)), V((sx, 3.88, 0.675)), V((sx, 3.80, 0.715))
    a = V((0, -1, 0.30)).normalized()          # hub axis, toward the pilot
    cylinder(cm, piv, top, 0.022, N=12, mat=CK)
    cylinder(cm, top, elb, 0.022, N=12, mat=CK)
    cylinder(cm, elb, hub - a * 0.03, 0.022, N=12, mat=CK)
    for p in (top, elb):
        cylinder(cm, p - V((0.024, 0, 0)), p + V((0.024, 0, 0)), 0.024, N=12, mat=CK)          # joint collars
    out.append(Part(f'cockpit_column_{L}', 'fus_cockpit', piv, cm, Quaternion(),
                    info=dict(kind='control_column', axis_local='+X (Unity) = right (lateral)', range_deg=12,
                              drive='ControlSurface.pitchRange (or Cockpit.Joystick: its X term)',
                              sign='Unity +angle about local +X moves the column top FORWARD (push); pull = negative')))
    for k in (-1, 1):                                                                              # fixed floor clevis
        box(interior, piv + V((k * 0.058, 0, -0.012)), (0.012, 0.08, 0.075), 'metal_dark')
    cylinder(interior, piv - V((0.07, 0, 0)), piv + V((0.07, 0, 0)), 0.012, N=8, mat='structure')
    box(interior, (sx, 3.97, FLOOR_Z + 0.004), (0.16, 0.12, 0.008), 'metal_dark')
    # ---- yoke wheel (ram's horn) on the hub; local X = hub axis toward the pilot
    ym = MeshBuf()
    u = V((1, 0, 0))
    w = a.cross(u).normalized()                # wheel "up"
    cylinder(ym, hub - a * 0.035, hub + a * 0.03, 0.032, N=16, mat='metal_dark')                     # hub boss
    cylinder(ym, hub - w * 0.02 - u * 0.13, hub - w * 0.02 + u * 0.13, 0.016, N=10, mat=CK)          # crossbar
    for k in (-1, 1):
        prev = hub - w * 0.02 + u * (k * 0.13)
        for i in range(1, 7):
            phi = (math.pi / 2) * i / 6
            pnt = hub + u * (k * (0.13 + 0.045 * math.sin(phi))) + w * (-0.02 + 0.07 * (1 - math.cos(phi)))
            cylinder(ym, prev, pnt, 0.016, N=10, mat=CK)
            d = (pnt - prev).normalized()
            cylinder(ym, pnt - d * 0.003, pnt + d * 0.003, 0.0168, N=10, mat=CK)        # joint ring hides the mitre
            prev = pnt
        cylinder(ym, prev - w * 0.01, prev + w * 0.11, 0.019, N=12, mat='rubber')                     # grips
    cylinder(ym, hub + a * 0.03, hub + a * 0.04, 0.026, N=16, mat='metal_dark')                      # centre cap
    out.append(Part(f'cockpit_yoke_{L}', f'cockpit_column_{L}', hub, ym, frame_x(a, (0, 0, 1)),
                    info=dict(kind='control_wheel', axis_local='+X (Unity) = hub axis, toward the pilot', range_deg=45,
                              drive='ControlSurface.rollRange',
                              sign='Unity +angle about local +X turns the wheel top to the RIGHT (= right roll)')))
    # ---- rudder pedals: yaw bar about the vertical axis through its centre post; local X = up
    pp = V((sx, 4.06, FLOOR_Z))
    pm = MeshBuf()
    cylinder(pm, pp, pp + V((0, 0, 0.07)), 0.022, N=12, mat='metal_dark')
    bar_z = FLOOR_Z + 0.05
    cylinder(pm, V((sx - 0.16, 4.06, bar_z)), V((sx + 0.16, 4.06, bar_z)), 0.015, N=8, mat='metal_dark')
    for k in (-1, 1):
        x = sx + k * 0.15
        cylinder(pm, V((x, 4.06, bar_z)), V((x, 4.00, bar_z + 0.15)), 0.012, N=8, mat='metal_dark')
        box(pm, (x, 3.995, bar_z + 0.135), (0.09, 0.025, 0.18), CK, rot=Quaternion(V((1, 0, 0)), math.radians(30)))
    cylinder(interior, pp - V((0, 0, 0.012)), pp + V((0, 0, 0.018)), 0.036, N=12, mat='metal_dark')  # floor socket
    out.append(Part(f'cockpit_rudder_pedals_{L}', 'fus_cockpit', pp, pm, frame_x((0, 0, 1), (0, 1, 0)),
                    info=dict(kind='rudder_pedals', axis_local='+X (Unity) = up', range_deg=15, drive='ControlSurface.yawRange',
                              sign='Unity +angle about local +X (up) moves the RIGHT pedal AFT; right rudder = negative')))
    return out
