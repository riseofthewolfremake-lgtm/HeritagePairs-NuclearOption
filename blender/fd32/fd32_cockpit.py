"""FD-32 cockpit: modern kitbash in the GA-25X 0.3.x style (docs/fd32_design.md 6).

Stock parts are added by FD32Build.cs at build time (referenced, never copied): the ejection seat stays on the stock pilot figure,
the SFB-81 `sfb_joystick` goes on the empty `cockpit_stick` (on our boot), the SFB-81 `sfb_throttle` on the empty `cockpit_throttle`
(left console), the screens are stock tacScreenDisplay / targetCamDisplay on our MFD quads. Custom geometry only for the tub
(the Mk I lining shell, re-materialled), the floor mat, the side consoles, the instrument panel with two MFD bezels, the glareshield
and the stick boot. NO rudder pedals (user rule). HUD = the game's (FD32Build).
"""
import math
from mathutils import Vector
from b25h_geom import V, MeshBuf, loft, cylinder, box, oriented_quad, fan_cap
from b25h_parts import Part
import nimrod_spec as S
import nimrod_cockpit as NC
from nimrod_parts import fus_ring, frame_x

TILT = math.radians(14.0)                       # panel leans back 14 deg
PN = V((0, -math.cos(TILT), math.sin(TILT)))    # panel normal toward the pilot
PU = V((0, math.sin(TILT), math.cos(TILT)))
X_ = V((1, 0, 0))
PANEL_C = V((0, -0.37, 0.355))                  # panel face centre
PANEL_W, PANEL_H = 0.62, 0.36
STICK = V((0.0, -0.43, -0.39))                  # stock SFB-81 joystick pivot (on the boot); round 8: 3 cm lower, 1 cm forward (in flight the grip covered the map's bottom centre; 5 cm lower hit the seat at 12/12 deg)
# round 6 (user, 1.5.1: the fal throttle "makes no sense"; brief: front-left, on a proper console): the left side console runs forward
# to the panel's lower edge and rises into a flat-topped forward console (FWD_TOP) against the left wall; the new fal lever (throttle_v7)
# stands in a slotted quadrant on it, outboard of the stock seat (|x| >= 0.285, the side consoles' inboard face)
FWD_Y = (-0.90, -0.80, -0.415)                  # round 10: flat top from -0.80 (the CI-22 throttle slides -0.735 .. -0.515)                  # ramp start (on the side console) / flat top start / front (the panel's lower edge)
FWD_TOP = 0.140
CONSOLE_XIN = 0.285
# round 10 (user: "a SINGLE SEAT FIGHTER, why the BOMBER throttle?!"): the CI-22 Cricket's single throttle (COIN_throttle, material hotas),
# mounted as the CI-22 mounts it: an identity frame, Cockpit.Throttle MOTION (slides along local +Z), range 0.22 m (COIN.prefab Cockpit
# throttles). THROTTLE = the mesh origin (its bottom) at idle, on the forward-left console top; full throttle = 0.22 m further forward.
# The mesh spans x 0 .. +0.136 (inboard), y -0.055 .. +0.084, z 0 .. 0.103 from its origin (measured on the placeholder; numbers only).
STOCK_THR = dict(mesh='COIN_throttle', x=(-0.010, 0.136), y=(-0.055, 0.084), z=(-0.001, 0.103), travel=0.22)
THROTTLE = V((-0.414, -0.735, FWD_TOP + 0.003))  # idle; origin = the mesh bottom 3 mm over the console top (rides on the rails)
QUAD_Y = (-0.505, -0.665)
QUAD_TOP = FWD_TOP + 0.062
QUAD_BASE = FWD_TOP + 0.002                     # quadrant floor on the console top
LEVER_H = 0.17                                  # lever pivot to grip top
CONSOLE_Z = 0.055
YA, YB = NC.YA, NC.YB


def wall_x(y, z, inset=0.0):
    return NC.wall_x(y, z, inset)


# Round 3 (user review: one large radar screen that switches to the camera on a lock + three small screens below). Stock aircraft do it
# with ONE tacScreenDisplay mesh made of several islands, each island mapping one region of the aircraft's tac-screen render texture
# (decoded from the user's placeholders: sfb_tacscreen 10 islands, COIN_targetScreen 4 islands = map + 3 side panels). Regions of the
# CI-22 tac page (1024 x 512, B-25H 1.1.1 live RT dump): map u 0.001-0.791; power / prop-fuel panel u 0.802-0.983 v 0.718-0.979; engine
# panel u 0.801-0.985 v 0.390-0.697; attitude panel u 0.789-0.983 v 0.025-0.341. Side panels are drawn rotated: screen right -> +v,
# screen up -> -u (GA-25X / B-25H TacScreenMesh). The game swaps the map for the target-camera video during a lock (B-25H 1.1.1 test).
# round 4: the stock stick grip hid the centre of the old bottom row (attitude 4 % visible from the eye). Map in the centre, attitude +
# power in a column left of it, engine right of it: every screen >= 90 % visible (check k2).
SCREENS = {   # name: (dx, dy, width, (u lo, u hi, v lo, v hi), rotated)
    'map':    (0.000, 0.065, 0.300, (0.001, 0.786, 0.0, 1.0), False),       # round 6: u hi 0.786 (0.791 showed a sliver of the attitude panel, u lo 0.789)
    'flight': (-0.245, 0.068, 0.085, (0.789, 0.983, 0.025, 0.341), True),
    'power':  (-0.245, -0.072, 0.079, (0.802, 0.983, 0.718, 0.979), True),
    'engine': (0.245, 0.040, 0.092, (0.801, 0.985, 0.390, 0.697), True),
}


def screen_aspect(r, rot):
    du, dv = (r[1] - r[0]) * 1024.0, (r[3] - r[2]) * 512.0
    return dv / du if rot else du / dv


def screen_rect(name):
    dx, dy, w, r, rot = SCREENS[name]
    h = w / screen_aspect(r, rot)
    c = PANEL_C + X_ * dx + PU * dy
    return c, w, h


def build_panel():
    """anti-glare panel slab (ck_modern), a black bezel round each of the four screens with push buttons on the big one, glareshield."""
    m = MeshBuf()
    w, h = PANEL_W / 2, PANEL_H / 2
    c0 = PANEL_C
    q = [c0 - X_ * w - PU * h, c0 + X_ * w - PU * h, c0 + X_ * w + PU * h, c0 - X_ * w + PU * h]
    back = [p - PN * 0.025 for p in q]
    oriented_quad(m, q, 'ck_modern', PN)
    oriented_quad(m, list(reversed(back)), 'ck_modern', -PN)
    for a, b in zip(range(4), [1, 2, 3, 0]):
        oriented_quad(m, [q[a], q[b], back[b], back[a]], 'ck_modern', (q[a] + q[b]) / 2 - c0)
    for name in SCREENS:
        bc, sw, sh = screen_rect(name)
        bc = bc + PN * 0.004
        bw, bh = sw / 2 + (0.03 if name == 'map' else 0.012), sh / 2 + (0.018 if name == 'map' else 0.012)
        bp = [bc - X_ * bw - PU * bh, bc + X_ * bw - PU * bh, bc + X_ * bw + PU * bh, bc - X_ * bw + PU * bh]
        oriented_quad(m, bp, 'ck_black', PN)
        for a, b in zip(range(4), [1, 2, 3, 0]):
            oriented_quad(m, [bp[a], bp[b], bp[b] - PN * 0.004, bp[a] - PN * 0.004], 'ck_black', (bp[a] + bp[b]) / 2 - bc)
        if name == 'map':
            for k in range(5):
                for sgn in (-1, 1):
                    p = bc + X_ * sgn * (sw / 2 + 0.015) + PU * (-sh / 2 + 0.02 + k * (sh - 0.04) / 4)
                    box(m, p + PN * 0.004, (0.014, 0.010, 0.010), 'ck_grey')
    # round 4: shaped glare-shield coaming (was a flat black slab): an arched hood over the panel top, rounded rear lip, running forward
    # to the windscreen base; 13 stations across, crinkle finish. Rows: lip underside, lip top, hood top, front edge.
    tl, tr = q[3], q[2]
    xs = [-w * 1.04 + 2 * w * 1.04 * k / 12 for k in range(13)]
    def arch(x):
        return 0.022 * max(0.0, 1 - (x / (w * 1.04)) ** 2)
    zt, yt = tl.z, tl.y
    import fd32_spec as _FS
    yfr = min(yt + 0.030, _FS.WS_BASE_Y - 0.006)        # round 4: the hood stays inside the windscreen (v4a poked out on the deck)
    rows = [[V((x, yt - 0.006, zt + 0.002)) for x in xs],
            [V((x, yt - 0.012, zt + 0.018 + arch(x))) for x in xs],
            [V((x, yt + 0.008, zt + 0.026 + arch(x))) for x in xs],
            [V((x, yfr, zt + 0.010 + arch(x) * 0.5)) for x in xs]]
    for a_, b_ in zip(rows, rows[1:]):
        for k in range(12):
            qd = [a_[k], a_[k + 1], b_[k + 1], b_[k]]
            cen = sum(qd, V()) / 4
            oriented_quad(m, qd, 'ck_crinkle', V((0, -0.4, 1)) if a_ is not rows[0] else V((0, -1, 0.2)))
    under = [V((x, yfr, zt - 0.004)) for x in xs]
    for k in range(12):
        oriented_quad(m, [rows[0][k], rows[0][k + 1], under[k + 1], under[k]], 'ck_crinkle', V((0, -0.2, -1)))
        oriented_quad(m, [rows[3][k], rows[3][k + 1], under[k + 1], under[k]], 'ck_crinkle', V((0, 1, 0)))
    for k, sx in ((0, -1), (12, 1)):
        oriented_quad(m, [rows[0][k], rows[1][k], rows[2][k], rows[3][k], under[k]], 'ck_crinkle', V((sx, 0, 0)))
    return m


def build_tac_screens():
    """round 6: FOUR quad meshes (mfd_map, mfd_power, mfd_flight, mfd_engine) on material 'screen' (round 3's 'tacscreen' faces lost
    their UVs: create_objects keeps face UVs only for whitelisted materials, and FD32Build.CopyMesh then put the planar detail UV on
    UV0 - docs/fd32_design.md 19 fault 6). FD32Build gives each the stock tacScreenDisplay material; each maps one tac-page region."""
    out = {}
    for name, (dx, dy, w, r, rot) in SCREENS.items():
        mb = MeshBuf()
        c, sw, sh = screen_rect(name)
        c = c + PN * 0.0055
        x0, x1 = -sw / 2, sw / 2
        y0, y1 = -sh / 2, sh / 2
        P = [c + X_ * x0 + PU * y0, c + X_ * x1 + PU * y0, c + X_ * x1 + PU * y1, c + X_ * x0 + PU * y1]
        if rot:
            uv = [(r[1], r[2]), (r[1], r[3]), (r[0], r[3]), (r[0], r[2])]
        else:
            uv = [(r[0], r[2]), (r[1], r[2]), (r[1], r[3]), (r[0], r[3])]
        oriented_quad(mb, P, 'screen', PN, uv=uv)
        out['mfd_' + name] = (mb, c)
    return out


def build_consoles():
    """left / right side consoles along the walls (y -1.20 .. -0.48, top at CONSOLE_Z): body + switch panels + knobs."""
    out = {}
    for s, L in ((-1, 'L'), (1, 'R')):
        m = MeshBuf()
        y0, y1 = -1.20, -0.48
        zt, zb = CONSOLE_Z, S.FLOOR_Z + 0.004
        def wx(y, z):
            return wall_x(y, z, 0.006)
        xin = 0.285                                   # round 3: outboard of the stock seat (half width 0.269)
        for ya, yb in zip((y0, -0.96, -0.72), (-0.96, -0.72, y1)):
            top = [V((s * xin, ya, zt)), V((s * wx(ya, zt), ya, zt)), V((s * wx(yb, zt), yb, zt)), V((s * xin, yb, zt))]
            oriented_quad(m, top, 'ck_modern', V((0, 0, 1)))
            side_ = [V((s * xin, ya, zt)), V((s * xin, yb, zt)), V((s * xin, yb, zb)), V((s * xin, ya, zb))]
            oriented_quad(m, side_, 'ck_black', V((-s, 0, 0)))          # round 7: dark inboard face (1.5.2: a pale lit patch beside the seat)
        for y, toward in ((y0, V((0, -1, 0))), (y1, V((0, 1, 0)))):
            oriented_quad(m, [V((s * xin, y, zt)), V((s * wx(y, zt), y, zt)), V((s * wx(y, zb), y, zb)), V((s * xin, y, zb))], 'ck_modern', toward)
        # switch panels: 3 per console, each with 4 toggles / knobs
        for k, yc in enumerate((-1.08, -0.84, -0.60)):
            if xin + 0.075 + 0.065 > wx(yc, zt) - 0.01:
                continue
            xc = s * (xin + 0.075)
            box(m, V((xc, yc, zt + 0.003)), (0.13, 0.20, 0.006), 'ck_black')
            for j in range(4):
                p = V((xc + s * (-0.04 + 0.027 * j), yc + (0.05 if j % 2 else -0.04), zt + 0.012))
                cylinder(m, p - V((0, 0, 0.006)), p + V((0, 0, 0.010)), 0.007, N=8, mat='ck_grey')
        out[f'cockpit_console_{L}'] = m
    return out


def build_floor_mat():
    m = MeshBuf()
    fz = S.FLOOR_Z + 0.003
    ys = [YA + 0.02, -1.0, -0.70, -0.40, YB - 0.02]
    for ya, yb in zip(ys, ys[1:]):
        xa, xb = 0.205, 0.205
        oriented_quad(m, [V((-xa, ya, fz)), V((xa, ya, fz)), V((xb, yb, fz)), V((-xb, yb, fz))], 'ck_mat', V((0, 0, 1)))
    return m


def build_stick_boot():
    """round 6 (user, 1.5.1: no big ribbed gaiter column): GA-25X lesson only - the stock SFB-81 stick sits at its stock height relative
    to the pilot figure (pivot z -0.36) on a SMALL mount. FD-32's own: a square chamfered floor plate and a short tapered square boot
    from the floor up to the pivot, with a thin collar; nothing above the pivot + 10 mm."""
    m = MeshBuf()
    fz = S.FLOOR_Z
    c = STICK
    def sq(z, h):
        k = h * 0.30                                     # chamfered square ring (8 corners)
        pts = [(h - k, -h), (h, -h + k), (h, h - k), (h - k, h), (-h + k, h), (-h, h - k), (-h, -h + k), (-h + k, -h)]
        return [V((c.x + x, c.y + y, z)) for x, y in pts]
    rings = [sq(fz + 0.001, 0.090), sq(fz + 0.014, 0.090), sq(fz + 0.016, 0.062), sq(c.z - 0.022, 0.044), sq(c.z - 0.020, 0.050),
             sq(c.z + 0.002, 0.050), sq(c.z + 0.004, 0.034)]
    mats = ['ck_black', 'ck_black', 'ck_modern', 'ck_black', 'ck_black', 'ck_black']
    for k in range(len(rings) - 1):
        loft(m, [rings[k], rings[k + 1]], mats[k], closed=True)
    fan_cap(m, rings[-1], V((c.x, c.y, c.z + 0.004)), 'ck_black', V((0, 0, 1)))
    fan_cap(m, rings[0], V((c.x, c.y, fz + 0.001)), 'ck_black', V((0, 0, -1)))
    for sx in (-1, 1):                                   # four plate bolts
        for sy in (-1, 1):
            cylinder(m, V((c.x + sx * 0.068, c.y + sy * 0.068, fz + 0.014)), V((c.x + sx * 0.068, c.y + sy * 0.068, fz + 0.019)), 0.007, N=8, mat='ck_grey')
    return m


def build_console_fwd():
    """round 6: forward-left console: the left side console continued forward to the panel's lower edge, rising (ramp FWD_Y[0]..[1]) to
    a flat top FWD_TOP; inboard face at x -CONSOLE_XIN from its top to the floor, outboard against the wall; closed box."""
    m = MeshBuf()
    s_ = -1
    zb = S.FLOOR_Z + 0.004
    ys = [FWD_Y[0], FWD_Y[1], -0.60, -0.50, FWD_Y[2]]

    def ztop(y):
        if y <= FWD_Y[1]:
            t = (y - FWD_Y[0]) / (FWD_Y[1] - FWD_Y[0])
            return CONSOLE_Z + 0.004 + (FWD_TOP - CONSOLE_Z - 0.004) * t
        return FWD_TOP

    def wx(y, z):
        return wall_x(y, z, -0.006)                      # 6 mm into the lining (touches the wall)

    def zbot(y):
        return zb if y > -0.48 else CONSOLE_Z - 0.002    # behind -0.48 it sits on the side console
    for ya, yb in zip(ys, ys[1:]):
        oriented_quad(m, [V((s_ * CONSOLE_XIN, ya, ztop(ya))), V((s_ * wx(ya, ztop(ya)), ya, ztop(ya))), V((s_ * wx(yb, ztop(yb)), yb, ztop(yb))),
                          V((s_ * CONSOLE_XIN, yb, ztop(yb)))], 'ck_modern', V((0, 0, 1)))
        za, zb_ = zbot(ya), zbot(yb)
        if ya < -0.48 < yb:
            za = zb_ = zb
        oriented_quad(m, [V((s_ * CONSOLE_XIN, ya, ztop(ya))), V((s_ * CONSOLE_XIN, yb, ztop(yb))), V((s_ * CONSOLE_XIN, yb, zbot(yb) if not (ya < -0.48 < yb) else zb)),
                          V((s_ * CONSOLE_XIN, ya, zbot(ya) if not (ya < -0.48 < yb) else zb))], 'ck_black', V((1, 0, 0)))
    y0, y1 = ys[0], ys[-1]
    oriented_quad(m, [V((s_ * CONSOLE_XIN, y0, ztop(y0))), V((s_ * wx(y0, ztop(y0)), y0, ztop(y0))), V((s_ * wx(y0, CONSOLE_Z), y0, CONSOLE_Z - 0.002)),
                      V((s_ * CONSOLE_XIN, y0, CONSOLE_Z - 0.002))], 'ck_modern', V((0, -1, 0)))
    oriented_quad(m, [V((s_ * CONSOLE_XIN, y1, ztop(y1))), V((s_ * wx(y1, ztop(y1)), y1, ztop(y1))), V((s_ * wx(y1, zb), y1, zb)),
                      V((s_ * CONSOLE_XIN, y1, zb))], 'ck_modern', V((0, 1, 0)))
    # trim strip along the inboard top edge + a small switch row behind the quadrant
    box(m, V((s_ * (CONSOLE_XIN + 0.006), (FWD_Y[1] + FWD_Y[2]) / 2, FWD_TOP + 0.003)), (0.012, FWD_Y[2] - FWD_Y[1], 0.006), 'ck_black')
    for j in range(3):
        p = V((THROTTLE.x + 0.005, -0.69 + 0.0, FWD_TOP + 0.004))
        cylinder(m, p + V((s_ * (-0.03 + 0.03 * j), 0, -0.003)), p + V((s_ * (-0.03 + 0.03 * j), 0, 0.012)), 0.006, N=8, mat='ck_grey')
    return m


def build_throttle_quadrant(lever=None):
    """round 10: the CI-22 throttle slides on the console top: a dark slot strip along its 0.22 m travel under the grip, a low guide rail
    on each side, front / rear stops, and a small BOOST plate at the front end. All on the console top (nothing floats)."""
    m = MeshBuf()
    x0 = THROTTLE.x + STOCK_THR['x'][0]; x1 = THROTTLE.x + STOCK_THR['x'][1]
    y0 = THROTTLE.y + STOCK_THR['y'][0] - 0.012; y1 = THROTTLE.y + STOCK_THR['y'][1] + STOCK_THR['travel'] + 0.012
    zt = FWD_TOP
    xc = (x0 + x1) / 2
    box(m, V((xc, (y0 + y1) / 2, zt + 0.0006)), (0.040, y1 - y0, 0.0012), 'ck_black')                       # slot strip
    for xr in (x0 - 0.006, x1 + 0.006):                                                                       # guide rails
        box(m, V((xr, (y0 + y1) / 2, zt + 0.006)), (0.008, y1 - y0, 0.012), 'ck_grey')
    for yy in (y0 - 0.006, y1 + 0.006):                                                                       # end stops
        box(m, V((xc, yy, zt + 0.008)), (x1 - x0 + 0.020, 0.010, 0.016), 'ck_black')
    box(m, V((xc, y1 + 0.025, zt + 0.002)), (0.06, 0.03, 0.004), 'red')                                     # BOOST plate (front)
    return m


def build_cockpit():
    global LEVER
    LEVER = None                                    # round 9: stock SFB-81 throttle (FD32Build), no fal lever
    parts = []
    shell = NC.build_shell()
    # round 4: the Mk I tub's forward hoop (a 3 cm ring at y -0.40 .. -0.36, just in front of the panel) drew an arc across the panel
    # and screens in the eye view; the panel + coaming close the front, so its faces above the panel's lower edge go
    pz = (PANEL_C - PU * (PANEL_H / 2)).z
    def _hoop(f):
        ps = [shell.verts[i] for i in f['idx']]
        return all(-0.425 <= p.y <= -0.345 and p.z > pz and abs(p.x) < 0.37 for p in ps)
    nf = len(shell.faces)
    shell.faces = [f for f in shell.faces if not _hoop(f)]
    print('[fd32] cockpit: removed', nf - len(shell.faces), 'forward-hoop faces of the Mk I tub')
    for f in shell.faces:                                   # lining -> modern composite tub colour; floor -> mat
        if f['mat'] == 'ck_floor':
            f['mat'] = 'ck_mat'
        elif f['mat'] == 'ck_lining':
            f['mat'] = 'ck_modern'
    parts.append(Part('cockpit_interior', 'fus_center', (0, -0.70, 0.0), shell))
    props = [('cockpit_panel', build_panel()), ('cockpit_floor', build_floor_mat()), ('cockpit_stickboot', build_stick_boot()),
             ('cockpit_quadrant', build_throttle_quadrant(LEVER)), ('cockpit_console_fwd', build_console_fwd())] + list(build_consoles().items())
    for name, mb in props:
        vs = mb.verts
        c = V((sum(v.x for v in vs) / len(vs), sum(v.y for v in vs) / len(vs), sum(v.z for v in vs) / len(vs)))
        parts.append(Part(name, 'fus_center', c, mb, info=dict(kind='cockpit_prop')))
    parts.append(Part('cockpit_stick', 'fus_center', STICK, None, info=dict(kind='stock_stick', stock_mesh='sfb_joystick')))
    parts.append(Part('cockpit_throttle', 'fus_center', THROTTLE, None, info=dict(kind='stock_throttle', stock_mesh=STOCK_THR['mesh'], drive='Cockpit.Throttle motion (CI-22: slides +Z, range 0.22)')))
    parts.insert(0, Part('cockpit_gauges', 'fus_center', PANEL_C, None, info=dict(kind='group')))
    for nm, (mb, c) in build_tac_screens().items():
        parts.append(Part(nm, 'cockpit_gauges', c, mb, frame_x(PN, PU),
                          info=dict(kind='mfd', role='tac', note='round 6: own quad, material screen -> stock tacScreenDisplay; one tac-page region')))
    parts.append(Part('cockpit_eye', 'fus_center', S.EYE, info=dict(kind='crew_eye', crew='pilot')))
    return parts
