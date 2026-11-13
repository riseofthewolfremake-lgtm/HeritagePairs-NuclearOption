"""MSB-17/80 1.9.5 flight deck: OUR OWN two-pilot side-by-side deck in the B-17 hull, with single stock parts placed in it (user order
2026-11-10, "Rebuild a custom cockpit using stock parts"; memory kitbash-stock-parts: no whole stock cockpit, the SFB-81 cockpit is the bar,
check-own-screenshots-and-stock-refs: clean, no busy procedural textures). Replaces the 1.9.1 stock EW-25 tub (msb_spec.STOCK_DECK).

Ours (this module, Blender frame: x right, y forward, z up, metres):
  cockpit_panel        main instrument panel: plan-curved, leaning back 15 deg, its top edge follows the windscreen sill down at the sides
                       (inside the hull at every height); six MFD units (bezel, soft keys, dark backing) + two switch strips
  cockpit_glareshield  visor over the panel top + coaming forward to the windscreen base, ends capped AT THE PANEL ENDS (|x| <= PANEL_X)
  cockpit_pedestal     centre pedestal between the seats (|x| <= 0.105: the seat armrests are at 0.111), throttle gate = an arc about the
                       stock throttle's pivot axis (the levers ride 5 mm above it from idle to full), two lever slots, forward switch deck
  cockpit_console_L/R  side consoles along the walls (top 0.98, switch plates)
  cockpit_interior     floor (the 1.9.1 tub floor level z 0.629, wall to wall from the bay bulkhead; the EWO stands on it), footwells
                       (z 0.50) under the panel, riser, knee wall and shelf, seat rails, stick boots, left aft wall liner, bay bulkhead
  cockpit_overhead     the 1.9.2 overhead strip (msb_stations.overhead_part, unchanged)
  cockpit_screen_deck_* screen quads (UV 0..1) on the MFD units: Unity lays the live stock tac page / stock dark glass on them
Stock (Unity, msb_spec anchors, meshes read from the user's install at build time, never in the repo):
  stick_L / stick_R    sfb_joystick (SFB-81 two-pilot bomber stick, Cockpit.joysticks range 12), placed as on the SFB-81 from our figure root
  cockpit_throttle     sfb_throttle (the SFB-81's ONE centre quadrant: one lever per pilot), Cockpit.throttles rotation range 52
  warnlamp_L / _R      EW1_warningLights (EW-25 missile-warning lamp, stock CockpitWarningLights), one on the glare-shield lip per pilot
  seats                ejectionSeat on each crew figure (the seat that fires; unchanged since 1.9.0)
"""
import math
from mathutils import Vector as V
import b17g_spec as S
import msb_spec as M
from b25h_geom import MeshBuf, oriented_quad, cylinder, box, loft, fan_cap, annulus, circle_pts
from b25h_parts import Part
import msb_stations as MST
import msb_detail196 as D

DETAIL = getattr(M, 'DETAIL196', False)      # 1.9.6 detail pass (msb_detail196); False = the 1.9.5 deck

FLOOR_Z = M.DECK_Z                    # 0.629: the 1.9.1 tub floor = the EWO platform level (EWO station unchanged)
# footwells under the panel: the figures' heels sit 1.16 under the eye and 0.61-0.83 ahead of it; the riser stays 0.43 ahead of the eye
# (the stick boots stand in the well)
WELL_Z, WELL_Y0, WELL_Y1, WELL_X = 0.495, M.EYE_PILOT[1] + 0.43, 4.50, 0.70
PANEL_YB, PANEL_K, PANEL_ZB = 4.30, 0.10, 0.98                 # bottom edge plan y = YB - K x^2 at z ZB
PANEL_TILT = math.radians(15.0)       # face leans back (top toward the nose)
PANEL_X = 0.92                        # panel half width (the glare shield ends here too)
PANEL_ZT_MAX = 1.42
PANEL_T = 0.03                        # panel thickness
CONSOLE_X0, CONSOLE_TOP, CONSOLE_Y0 = 0.70, 0.98, 3.00
PED_X = 0.105                         # pedestal half width (seat armrests at |x| 0.111)
GATE_R = 0.163                        # throttle gate radius about the stock pivot (lever arm feet at r 0.170-0.211)
GATE_A0, GATE_A1 = -78.0, 28.0        # gate arc, deg from straight up toward the nose (levers -56..-46 at idle, -4..+6 at full)
LEVER_X = (0.078, 0.096)              # sfb_throttle lever arms / knobs |x| 0.075-0.099
COAMING_Y = 4.53                      # coaming front edge (the windscreen bottom frame is at y 4.55)
# windscreen bottom edge z by |x| (msb1780.blend, fus_cockpit glass faces facing forward, lowest vertex per 0.1 m of x; the B-17G
# windscreen is kept, so this is fixed): the panel top stays 7 cm under it, the coaming front 1.5 cm under it
SILL = [(0.0, 1.620), (0.4, 1.592), (0.6, 1.530), (0.8, 1.398), (0.9, 1.356), (1.0, 1.310)]
# MFD units: (role, x centre, z centre, screen w, screen h, content); content as the Unity layout (TacElements): map = the tac map,
# panels12 = power + engine dials, panel3 = attitude, dark = stock dark glass (standby, off)
MFDS = [('mapL', -0.660, 1.195, 0.200, 0.150, 'map'), ('sysL', -0.330, 1.195, 0.240, 0.150, 'panels12'),
        ('attC', 0.0, 1.245, 0.130, 0.150, 'panel3'), ('stbyC', 0.0, 1.060, 0.130, 0.070, 'panel3' if getattr(M, 'DETAIL196', False) else 'dark'),
        ('sysR', 0.330, 1.195, 0.240, 0.150, 'panels12'), ('mapR', 0.660, 1.195, 0.200, 0.150, 'map')]
BEZEL = 0.032                         # bezel bar width round a screen
LAMP_X = (-0.38, 0.38)
STACK_X, STACK_Z0, STACK_Z1, STACK_D = 0.165, 0.990, 1.372, 0.036   # 1.9.6 raised centre stack (|x|, bottom, top, standing off the face)                # missile-warning lamps on the glare-shield lip, on each pilot's centre line


def wall_x(y, z, inset=0.02):
    import b17g_parts as P
    return P.fus_skin_x(y, z, inset)


def interp(tab, x):
    x = abs(x)
    for (x0, y0), (x1, y1) in zip(tab, tab[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tab[-1][1]


def dquad(mb, q, mat, n, t=0.006):
    n = V(n)
    oriented_quad(mb, q, mat, n)
    oriented_quad(mb, [p - n.normalized() * t for p in q], mat, -n)


# ------------------------------------------------------------------------------------------------ panel frame
def panel_y(x, z):
    return PANEL_YB - PANEL_K * x * x + (z - PANEL_ZB) * math.tan(PANEL_TILT)


def panel_pt(x, z, off=0.0):
    """point on the panel face (+off toward the pilots) and the face normal (toward the pilots).
    face y(x, z) = YB - K x^2 + (z - ZB) tan(tilt): tangents (1, -2Kx, 0) and (0, tan, 1); the normal points aft (-y)."""
    t1 = V((1.0, -2 * PANEL_K * x, 0.0)); t2 = V((0.0, math.tan(PANEL_TILT), 1.0))
    n = t1.cross(t2).normalized()
    if n.y > 0:
        n = -n
    return V((x, panel_y(x, z), z)) + n * off, n


def panel_axes(x, z):
    """right / up unit vectors in the panel face at (x, z)."""
    _, n = panel_pt(x, z)
    right = V((1.0, -2 * PANEL_K * x, 0.0)).normalized()
    up = n.cross(right).normalized()
    if up.z < 0:
        up = -up
    return right, up, n


def z_top(x):
    """panel top edge height at x: under the windscreen sill (7 cm) and inside the hull (3 cm), at most PANEL_ZT_MAX."""
    zt = min(PANEL_ZT_MAX, interp(SILL, x) - 0.07)
    while zt > PANEL_ZB + 0.1 and wall_x(panel_y(x, zt), zt, 0.0) < abs(x) + 0.03:
        zt -= 0.005
    return zt


def unit_rect(role):
    for r, x, z, w, h, c in MFDS:
        if r == role:
            return x, z, w, h, c
    raise KeyError(role)


def build_panel():
    out = []
    mb = MeshBuf()
    nx = 46
    xs = [-PANEL_X + 2 * PANEL_X * k / nx for k in range(nx + 1)]
    nz = 10
    # face (toward the pilots) and back (0.03 behind), as a grid that follows the top edge
    for xa, xb in zip(xs, xs[1:]):
        za_t, zb_t = z_top(xa), z_top(xb)
        for k in range(nz):
            fa0, fa1 = k / nz, (k + 1) / nz
            pa0 = PANEL_ZB + (za_t - PANEL_ZB) * fa0; pa1 = PANEL_ZB + (za_t - PANEL_ZB) * fa1
            pb0 = PANEL_ZB + (zb_t - PANEL_ZB) * fa0; pb1 = PANEL_ZB + (zb_t - PANEL_ZB) * fa1
            q = [panel_pt(xa, pa0)[0], panel_pt(xb, pb0)[0], panel_pt(xb, pb1)[0], panel_pt(xa, pa1)[0]]
            n = panel_pt((xa + xb) / 2, (pa0 + pb1) / 2)[1]
            oriented_quad(mb, q, 'ck_od', n)
            oriented_quad(mb, [p - n * PANEL_T for p in q], 'ck_panel', -n)
        # top edge strip and bottom edge strip (closed solid)
        ta, na = panel_pt(xa, za_t); tb, nb = panel_pt(xb, zb_t)
        oriented_quad(mb, [ta, tb, tb - nb * PANEL_T, ta - na * PANEL_T], 'ck_panel', V((0, 0, 1)))
        ba, na = panel_pt(xa, PANEL_ZB); bb, nb = panel_pt(xb, PANEL_ZB)
        oriented_quad(mb, [ba, bb, bb - nb * PANEL_T, ba - na * PANEL_T], 'ck_panel', V((0, 0, -1)))
    for xe, sg in ((-PANEL_X, -1), (PANEL_X, 1)):                     # end caps
        zt = z_top(xe)
        a, n = panel_pt(xe, PANEL_ZB); b, _ = panel_pt(xe, zt)
        oriented_quad(mb, [a, b, b - n * PANEL_T, a - n * PANEL_T], 'ck_panel', V((sg, 0, 0)))
    if DETAIL:
        out += panel_detail196(mb)
    # MFD units: dark backing plate, four bezel bars, soft keys (5 under, 4 down each side), screen quad (separate part)
    for role, x, z, w, h, content in ([] if DETAIL else MFDS):
        right, up, n = panel_axes(x, z)
        c = panel_pt(x, z, 0.0)[0]
        W, H = w + 2 * BEZEL, h + 2 * BEZEL
        plate = [c - right * (W / 2) - up * (H / 2), c + right * (W / 2) - up * (H / 2), c + right * (W / 2) + up * (H / 2), c - right * (W / 2) + up * (H / 2)]
        oriented_quad(mb, [p + n * 0.002 for p in plate], 'ck_black', n)
        import nimrod_structure as NS
        corners = [c - right * (w / 2 + BEZEL / 2) - up * (h / 2 + BEZEL / 2), c + right * (w / 2 + BEZEL / 2) - up * (h / 2 + BEZEL / 2),
                   c + right * (w / 2 + BEZEL / 2) + up * (h / 2 + BEZEL / 2), c - right * (w / 2 + BEZEL / 2) + up * (h / 2 + BEZEL / 2)]
        for a, b in zip(corners, corners[1:] + corners[:1]):
            NS.sec_tube(mb, a + n * 0.009, b + n * 0.009, BEZEL * 0.9, 0.014, n, mat='ck_bezel')
        nk = 5 if w > 0.15 else 3
        for k in range(nk):                                               # soft keys in the bottom bezel bar
            p = c - right * (w / 2) + right * ((k + 0.5) * w / nk) - up * (h / 2 + BEZEL / 2) + n * 0.018
            box(mb, tuple(p), (0.022, 0.008, 0.010), 'ck_black', rot=_rot(right, up, n))
        if h >= 0.12:
            for sd in (-1, 1):                                            # side keys
                for k in range(4):
                    p = c + right * sd * (w / 2 + BEZEL / 2) - up * (h / 2) + up * ((k + 0.5) * h / 4) + n * 0.018
                    box(mb, tuple(p), (0.010, 0.008, 0.020), 'ck_black', rot=_rot(right, up, n))
        q = [c - right * (w / 2) - up * (h / 2), c + right * (w / 2) - up * (h / 2), c + right * (w / 2) + up * (h / 2), c - right * (w / 2) + up * (h / 2)]
        sm = MeshBuf()
        oriented_quad(sm, [p + n * 0.006 for p in q], 'screen', n)
        for f in sm.faces:
            f['uv'] = [(0, 0), (1, 0), (1, 1), (0, 1)]
        out.append(Part(f'cockpit_screen_deck_{role}', 'cockpit_panel', mesh=sm, info={'kind': 'screen', 'w': w, 'h': h, 'content': content, 'deck': True}))
    # switch strips between the inner MFDs and the centre stack, and along the bottom of the outer units
    for sx in ((-1, 1) if not DETAIL else ()):
        x = sx * 0.140
        right, up, n = panel_axes(x, 1.20)
        c = panel_pt(x, 1.20, 0.0)[0]
        strip = [c - right * 0.028 - up * 0.10, c + right * 0.028 - up * 0.10, c + right * 0.028 + up * 0.10, c - right * 0.028 + up * 0.10]
        oriented_quad(mb, [p + n * 0.003 for p in strip], 'ck_black', n)
        for k in range(4):
            p = c - up * 0.075 + up * (k * 0.05)
            cylinder(mb, p + n * 0.003, p + n * 0.020, 0.0045, N=8, mat='ck_bezel')
        for x2 in (sx * 0.62, sx * 0.80):
            if abs(x2) > PANEL_X - 0.04:
                continue
            right, up, n = panel_axes(x2, 1.035)
            c = panel_pt(x2, 1.035, 0.0)[0]
            pl = [c - right * 0.06 - up * 0.022, c + right * 0.06 - up * 0.022, c + right * 0.06 + up * 0.022, c - right * 0.06 + up * 0.022]
            oriented_quad(mb, [p + n * 0.003 for p in pl], 'ck_black', n)
            for k in range(3):
                p = c - right * 0.04 + right * (k * 0.04)
                cylinder(mb, p + n * 0.003, p + n * 0.016, 0.005, N=8, mat='ck_bezel')
    # shelf under the panel bottom forward-down to the knee wall, and the knee wall to the footwell floor (dark)
    xs2 = [-PANEL_X + 2 * PANEL_X * k / 20 for k in range(21)]
    for xa, xb in zip(xs2, xs2[1:]):
        ba = panel_pt(xa, PANEL_ZB)[0] - panel_pt(xa, PANEL_ZB)[1] * PANEL_T
        bb = panel_pt(xb, PANEL_ZB)[0] - panel_pt(xb, PANEL_ZB)[1] * PANEL_T
        fa, fb = V((xa, WELL_Y1, 0.80)), V((xb, WELL_Y1, 0.80))
        dquad(mb, [ba, bb, fb, fa], 'ck_panel', V((0, -0.6, -0.8)))
        if max(abs(xa), abs(xb)) <= WELL_X + 1e-6:
            dquad(mb, [V((xa, WELL_Y1, WELL_Z)), V((xb, WELL_Y1, WELL_Z)), fb, fa], 'ck_panel', V((0, -1, 0)))
    out.append(Part('cockpit_panel', 'cockpit_interior', mesh=mb, info={'kind': 'cockpit'}))
    return out


# ------------------------------------------------------------------------------------------------ 1.9.6 panel detail
def stack_pt(x, z, off=0.0):
    """a point on the raised centre stack's face (STACK_D off the panel face)."""
    return panel_pt(x, z, STACK_D + off)


def panel_detail196(mb):
    """1.9.6: raised centre stack, recessed screen wells, gear lever / flap selector on the stack, annunciator strips, rotary selectors,
    push-button strips and toggle rows with backlit legends. Returns the screen parts."""
    out = []
    # centre stack: a box standing STACK_D off the panel face, |x| <= STACK_X, z STACK_Z0..STACK_Z1 (face ck_od, sides ck_panel)
    xs = [-STACK_X + 2 * STACK_X * k / 6 for k in range(7)]
    for xa, xb in zip(xs, xs[1:]):
        q = [stack_pt(xa, STACK_Z0)[0], stack_pt(xb, STACK_Z0)[0], stack_pt(xb, STACK_Z1)[0], stack_pt(xa, STACK_Z1)[0]]
        oriented_quad(mb, q, 'ck_od', panel_pt((xa + xb) / 2, 1.2)[1])
        for z_, nn in ((STACK_Z0, V((0, 0, -1))), (STACK_Z1, V((0, 0, 1)))):
            oriented_quad(mb, [panel_pt(xa, z_)[0], panel_pt(xb, z_)[0], stack_pt(xb, z_)[0], stack_pt(xa, z_)[0]], 'ck_panel', nn)
    for xe, sg in ((-STACK_X, -1), (STACK_X, 1)):
        oriented_quad(mb, [panel_pt(xe, STACK_Z0)[0], panel_pt(xe, STACK_Z1)[0], stack_pt(xe, STACK_Z1)[0], stack_pt(xe, STACK_Z0)[0]], 'ck_panel', V((sg, 0, 0)))
    # screen wells with real depth; units on the stack sit on its face
    for role, x, z, w, h, content in MFDS:
        right, up, n = panel_axes(x, z)
        base = (stack_pt if abs(x) < STACK_X else panel_pt)(x, z)[0]
        sc = D.well(mb, base, right, up, n, w, h, BEZEL)
        D.softkeys(mb, base + n * 0.026, right, up, n, w, h, BEZEL)
        q = [sc - right * (w / 2) - up * (h / 2), sc + right * (w / 2) - up * (h / 2), sc + right * (w / 2) + up * (h / 2), sc - right * (w / 2) + up * (h / 2)]
        sm = MeshBuf()
        oriented_quad(sm, [p_ + n * 0.0008 for p_ in q], 'screen', n)
        for f in sm.faces:
            f['uv'] = [(0, 0), (1, 0), (1, 1), (0, 1)]
        out.append(Part(f'cockpit_screen_deck_{role}', 'cockpit_panel', mesh=sm, info={'kind': 'screen', 'w': w, 'h': h, 'content': content, 'deck': True}))
    # on the stack: gear lever (right of the standby display), flap selector (left), toggle columns above them
    for x, fn in ((0.128, D.gear_lever), (-0.128, D.flap_selector)):
        right, up, n = panel_axes(x, 1.075)
        fn(mb, stack_pt(x, 1.075)[0], right, up, n)
    for sx in (-1, 1):
        for k in range(4):
            x, z = sx * 0.128, 1.170 + 0.045 * k
            right, up, n = panel_axes(x, z)
            D.toggle(mb, stack_pt(x, z)[0], right, up, n)
    # caution / annunciator strips under the glare shield (over each pilot's systems MFD) and the master caution pair
    for sx in (-1, 1):
        x, z = sx * 0.345, 1.322
        right, up, n = panel_axes(x, z)
        D.annunciators(mb, panel_pt(x, z)[0], right, up, n, k=7, h=0.014, amber=(1, 4) if sx < 0 else (2, 5))
        x2 = sx * 0.640
        right, up, n = panel_axes(x2, 1.322)
        if 1.322 + 0.02 < z_top(x2) - 0.005:
            D.annunciators(mb, panel_pt(x2, 1.322)[0], right, up, n, k=3, w=0.034, h=0.014, amber=(0,))
    # under the outer (map) units: two rotary selectors + a push-button strip; under the systems units: a toggle row
    for sx in (-1, 1):
        for x, z in ((sx * 0.580, 1.035), (sx * 0.740, 1.035)):
            right, up, n = panel_axes(x, z)
            D.rotary(mb, panel_pt(x, z)[0], right, up, n)
        x, z = sx * 0.660, 1.000
        right, up, n = panel_axes(x, z)
        D.pushbuttons(mb, panel_pt(x, z)[0], right, up, n, k=6)
        for k in range(5):
            x, z = sx * (0.250 + 0.040 * k), 1.035
            right, up, n = panel_axes(x, z)
            D.toggle(mb, panel_pt(x, z)[0], right, up, n)
        x, z = sx * 0.330, 0.998
        right, up, n = panel_axes(x, z)
        D.pushbuttons(mb, panel_pt(x, z)[0], right, up, n, k=5)
    return out


def _rot(right, up, n):
    from mathutils import Matrix
    return Matrix((right, n, up)).transposed().to_quaternion()


# ------------------------------------------------------------------------------------------------ glare shield
def coaming_z(x):
    """coaming front edge z at COAMING_Y: 1.5 cm under the windscreen sill and 1 cm inside the hull."""
    z = interp(SILL, x) - 0.015
    while z > 1.0 and wall_x(COAMING_Y, z, 0.0) < abs(x) + 0.01:
        z -= 0.003
    return z


def glare_profile(x):
    t, n = panel_pt(x, z_top(x))
    yt, zt = t.y, t.z
    zf = max(coaming_z(x), zt + 0.05)
    if DETAIL:      # 1.9.6: a taller lip face (the mode-control strip) and a soft roll (r 14 mm) where the lip meets the visor top
        r = 0.014; yl, z0, z1 = yt - 0.150, zt - 0.026, zt + 0.032
        roll = [V((x, yl + r - r * math.cos(a), z1 - r + r * math.sin(a))) for a in (math.radians(d) for d in (0, 30, 60, 90))]
        return [V((x, yl, z0))] + roll + [V((x, yt - 0.02, zt + 0.048)), V((x, COAMING_Y, zf)),
                V((x, COAMING_Y, zf - 0.020)), V((x, yt + 0.004, zt - 0.004)), V((x, yl + 0.012, z0))]
    return [V((x, yt - 0.150, zt - 0.012)), V((x, yt - 0.150, zt + 0.030)), V((x, yt - 0.02, zt + 0.048)), V((x, COAMING_Y, zf)),
            V((x, COAMING_Y, zf - 0.020)), V((x, yt + 0.004, zt - 0.004)), V((x, yt - 0.130, zt - 0.012))]


def build_glareshield():
    mb = MeshBuf()
    nx = 46
    xs = [-PANEL_X + 2 * PANEL_X * k / nx for k in range(nx + 1)]
    rings = [glare_profile(x) for x in xs]
    for ra, rb in zip(rings, rings[1:]):
        m = len(ra)
        # outward normal of each profile edge from the profile's winding in (y, z) (1.9.5 build 1: a centroid test turned the long coaming
        # top inward on this thin profile, so it was culled in Unity and the nose interior showed through)
        area = sum(p.y * q.z - q.y * p.z for p, q in zip(ra, ra[1:] + ra[:1]))
        for i in range(m):
            a0, a1, b0, b1 = ra[i], ra[(i + 1) % m], rb[i], rb[(i + 1) % m]
            dy, dz = a1.y - a0.y, a1.z - a0.z
            out_dir = V((0, dz, -dy)) if area > 0 else V((0, -dz, dy))
            mat = 'ck_black' if i in ((0, 1, 2, 3, 4, 5) if DETAIL else (0, 1, 2)) else 'ck_panel'
            oriented_quad(mb, [a0, b0, b1, a1], mat, out_dir)
    for ring, sg in ((rings[0], -1), (rings[-1], 1)):                  # end caps at the panel ends
        cen = sum(ring, V()) / len(ring)
        for a, b in zip(ring, ring[1:] + ring[:1]):
            mb.poly([cen, a, b] if (a - cen).cross(b - cen).x * sg > 0 else [cen, b, a], 'ck_panel', smooth=False)
    if DETAIL:      # mode-control strip on the lip face between the two lamps: windows (dark, legend digits) and knobs
        n = V((0, -1, 0)); right = V((1, 0, 0)); up = V((0, 0, 1))
        for x in (-0.26, -0.13, 0.0, 0.13, 0.26):
            p = glare_profile(x); c = V((x, p[0].y, (p[0].z + p[4].z) / 2))
            D.plate(mb, c + V((0.03, 0, 0)), right, up, n, 0.062, 0.030, 0.002, 'ck_panel')
            q = [c + right * sx_ * 0.016 + up * sz_ * 0.007 + n * 0.0032 for sx_, sz_ in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            oriented_quad(mb, q, 'ck_black', n)
            for k in range(3):
                D.legend(mb, c + n * 0.0032 + right * (-0.009 + 0.009 * k), right, up, n, 0.005, 0.006)
            D.knob(mb, c + right * 0.042 + n * 0.002, n, 0.009, 0.011, N=10)
            D.legend(mb, c + right * 0.042 + up * 0.0135 + n * 0.002, right, up, n, 0.012, 0.002)
    return Part('cockpit_glareshield', 'cockpit_interior', mesh=mb, info={'kind': 'cockpit'})


def lamp_targets():
    """(x, y, z) of each missile-warning lamp centre: on the glare-shield rear lip face, 3 mm proud."""
    out = []
    for x in LAMP_X:
        p = glare_profile(x)
        out.append(V((x, p[0].y - 0.003, ((p[0].z + p[4].z) / 2) if DETAIL else (p[0].z + p[1].z) / 2)))
    return out


# ------------------------------------------------------------------------------------------------ pedestal + throttle gate
def build_pedestal():
    mb = MeshBuf()
    ty, tz = M.throttle_anchor()[1], M.throttle_anchor()[2]
    angs = [math.radians(GATE_A0 + (GATE_A1 - GATE_A0) * k / 24) for k in range(25)]
    arc = [(ty + GATE_R * math.sin(a), tz + GATE_R * math.cos(a)) for a in angs]
    y_rear, y_front = arc[0][0], arc[-1][0]
    yp = panel_y(0.0, PANEL_ZB) - 0.004
    # side walls (profile: floor -> arc -> forward deck -> panel bottom), closed with a rear face and a top deck
    prof = [(y_rear, WELL_Z)] + [(y, z) for y, z in arc] + [(y_front + 0.02, arc[-1][1]), (yp, 0.955), (yp, WELL_Z)]
    for sx in (-1, 1):
        x = sx * PED_X
        import b25h_geom as G
        pts = [V((x, y, z)) for y, z in prof]
        tris = G.ear_clip([(p.y, p.z) for p in pts])
        for a, b, c in tris:
            q = [pts[a], pts[b], pts[c]]
            nrm = (q[1] - q[0]).cross(q[2] - q[0])
            if nrm.x * sx < 0:
                q = [q[0], q[2], q[1]]
            mb.poly(q, 'ck_od', smooth=False)
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(prof, prof[1:] + prof[:1]))
    n_arc = len(arc)
    for i, ((ya, za), (yb, zb)) in enumerate(zip(prof, prof[1:] + prof[:1])):   # the strip round the profile (rear, gate, deck, front)
        if i == len(prof) - 1:
            continue                                                      # bottom (on the floor)
        q = [V((-PED_X, ya, za)), V((PED_X, ya, za)), V((PED_X, yb, zb)), V((-PED_X, yb, zb))]
        dy, dz = yb - ya, zb - za
        out_dir = V((0, dz, -dy)) if area > 0 else V((0, -dz, dy))        # outward normal of a (y, z) polygon edge
        on_arc = 1 <= i <= n_arc - 1
        oriented_quad(mb, q, 'ck_panel' if on_arc else 'ck_od', out_dir)
    # lever slots on the gate (dark strips 3 mm proud of the arc, under the lever arms) and the gate side plates
    for sx in (-1, 1):
        for (a0, a1) in zip(angs, angs[1:]):
            r = GATE_R + 0.003
            p00 = V((sx * LEVER_X[0], ty + r * math.sin(a0), tz + r * math.cos(a0))); p10 = V((sx * LEVER_X[1], ty + r * math.sin(a0), tz + r * math.cos(a0)))
            p01 = V((sx * LEVER_X[0], ty + r * math.sin(a1), tz + r * math.cos(a1))); p11 = V((sx * LEVER_X[1], ty + r * math.sin(a1), tz + r * math.cos(a1)))
            oriented_quad(mb, [p00, p10, p11, p01], 'ck_black', V((0, math.sin((a0 + a1) / 2), math.cos((a0 + a1) / 2))))
    if M.QUADRANT197:
        quadrant197(mb, ty, tz, angs)
    if DETAIL:
        pedestal_detail196(mb, ty, tz, angs, y_rear)
    # forward deck switch plates (between the gate and the panel)
    for k, yy in enumerate((y_front + 0.07, y_front + 0.16)):
        if yy > yp - 0.04:
            continue
        zz = arc[-1][1] + (0.955 - arc[-1][1]) * (yy - y_front - 0.02) / max(yp - y_front - 0.02, 1e-3)
        box(mb, (0, yy, zz + 0.004), (0.17, 0.06, 0.008), 'ck_black')
        for j in (-1, 0, 1):
            cylinder(mb, V((j * 0.05, yy, zz + 0.008)), V((j * 0.05, yy, zz + 0.024)), 0.0055, N=8, mat='ck_bezel')
    return Part('cockpit_pedestal', 'cockpit_interior', mesh=mb, info={'kind': 'cockpit'})


def quadrant197(mb, ty, tz, angs):
    """1.9.7 throttle quadrant housing: the console top at radius M.QUAD_TOP_R about the stock pivot over the whole gate arc, open only along
    two slots (M.QUAD_SLOT_X, arc stations M.QUAD_SLOT_K) whose dark floor is the 1.9.5 lever strip (GATE_R + 3 mm). The stock lever arms
    (foot r 0.178) stand 15-27 mm deep in the slots from idle to full; the knobs (from r 0.260) ride 55 mm above the top."""
    R0, R1 = GATE_R, M.QUAD_TOP_R
    x0, x1 = M.QUAD_SLOT_X; k0, k1 = M.QUAD_SLOT_K
    P = lambda a, r, x: V((x, ty + r * math.sin(a), tz + r * math.cos(a)))
    up = lambda a: V((0, math.sin(a), math.cos(a)))
    for k, (a0, a1) in enumerate(zip(angs, angs[1:])):
        am = (a0 + a1) / 2
        in_slot = k0 <= k < k1
        bands = [(-PED_X, -x1), (-x0, x0), (x1, PED_X)] if in_slot else [(-PED_X, PED_X)]
        for xa, xb in bands:                                             # top surface
            oriented_quad(mb, [P(a0, R1, xa), P(a0, R1, xb), P(a1, R1, xb), P(a1, R1, xa)], 'ck_panel', up(am), smooth=True)
        for sx in (-1, 1):                                               # outer sides (continue the pedestal side walls up)
            oriented_quad(mb, [P(a0, R0, sx * PED_X), P(a0, R1, sx * PED_X), P(a1, R1, sx * PED_X), P(a1, R0, sx * PED_X)], 'ck_od', V((sx, 0, 0)))
            if in_slot:                                                  # slot walls (dark), facing into the slot
                oriented_quad(mb, [P(a0, R0, sx * x0), P(a0, R1, sx * x0), P(a1, R1, sx * x0), P(a1, R0, sx * x0)], 'ck_black', V((sx, 0, 0)))
                oriented_quad(mb, [P(a0, R0, sx * x1), P(a0, R1, sx * x1), P(a1, R1, sx * x1), P(a1, R0, sx * x1)], 'ck_black', V((-sx, 0, 0)))
    for sx in (-1, 1):                                                   # slot end walls
        for k, sgn in ((k0, 1), (k1, -1)):
            a = angs[k]; t = V((0, math.cos(a), -math.sin(a))) * sgn     # along the arc, into the slot
            oriented_quad(mb, [P(a, R0, sx * x0), P(a, R0, sx * x1), P(a, R1, sx * x1), P(a, R1, sx * x0)], 'ck_black', t)
    for a, sgn in ((angs[0], -1), (angs[-1], 1)):                        # housing ends (aft / forward)
        t = V((0, math.cos(a), -math.sin(a))) * sgn
        oriented_quad(mb, [P(a, R0, -PED_X), P(a, R0, PED_X), P(a, R1, PED_X), P(a, R1, -PED_X)], 'ck_od', t)


PED_AFT_Y0, PED_AFT_Z = 3.42, 0.880       # 1.9.6 aft pedestal extension: from here to the gate's rear, top height


def pedestal_detail196(mb, ty, tz, angs, y_rear):
    """1.9.6 throttle quadrant surround + aft pedestal: a centre spine riding over the gate between the two levers with detent marks and
    IDLE / MIL / MAX legends, detent ticks at each slot; aft extension (|x| <= 0.100, 11 mm clear of the seats) carrying two radio / nav
    heads, the pitch-trim wheel in a slot and the speed-brake lever."""
    sp_x, sp_r = 0.058, (M.QUAD_TOP_R if M.QUADRANT197 else GATE_R + 0.016)
    for a0, a1 in (() if M.QUADRANT197 else zip(angs, angs[1:])):      # 1.9.7: the housing top replaces the spine
        P = lambda a, r, x: V((x, ty + r * math.sin(a), tz + r * math.cos(a)))
        oriented_quad(mb, [P(a0, sp_r, -sp_x), P(a0, sp_r, sp_x), P(a1, sp_r, sp_x), P(a1, sp_r, -sp_x)], 'ck_black', V((0, math.sin(a0), math.cos(a0))))
        for sx in (-1, 1):
            oriented_quad(mb, [P(a0, GATE_R, sx * sp_x), P(a0, sp_r, sx * sp_x), P(a1, sp_r, sx * sp_x), P(a1, GATE_R, sx * sp_x)], 'ck_panel', V((sx, 0, 0)))
    for d, lg in ((-50.5, 'IDLE'), (-24.0, 'MIL'), (1.5, 'MAX')):            # the lever feet at idle / mid / full (deg from up)
        a = math.radians(d)
        up_ = V((0, math.sin(a), math.cos(a))); along = V((0, math.cos(a), -math.sin(a)))
        c = V((0, ty, tz)) + up_ * (sp_r + 0.0012)
        q = [c - V((0.040, 0, 0)) - along * 0.0012, c + V((0.040, 0, 0)) - along * 0.0012, c + V((0.040, 0, 0)) + along * 0.0012, c - V((0.040, 0, 0)) + along * 0.0012]
        oriented_quad(mb, q, 'ck_legend', up_)
        for sx in (-1, 1):                                                   # detent ticks beside each slot (outside the lever path)
            t = V((sx * (0.100 if M.QUADRANT197 else 0.102), 0, 0)) + V((0, ty, tz)) + up_ * ((M.QUAD_TOP_R if M.QUADRANT197 else GATE_R) + 0.0035)
            box(mb, tuple(t), (0.005, 0.004, 0.003), 'ck_legend', rot=D.rot(V((1, 0, 0)), along, up_))
    # aft extension
    y0, y1, zt = PED_AFT_Y0, y_rear, PED_AFT_Z
    box(mb, (0, (y0 + y1) / 2, (WELL_Z + zt) / 2), (2 * 0.100, y1 - y0, zt - WELL_Z), 'ck_od')
    n, right = V((0, 0, 1)), V((1, 0, 0)); fwd = V((0, 1, 0))
    for yy in (y1 - 0.075, y1 - 0.150):      # aft of the throttle levers' idle position (arms from y 3.886)
        D.radio_head(mb, V((0, yy, zt)), right, fwd, n, w=0.180, h=0.060)
    # pitch-trim wheel standing through a slot in the top (right half), speed-brake lever (left half)
    oriented_quad(mb, [V((x_, y_, zt + 0.0012)) for x_, y_ in ((0.044, y0 + 0.03), (0.084, y0 + 0.03), (0.084, y0 + 0.15), (0.044, y0 + 0.15))], 'ck_black', n)
    D.trim_wheel(mb, V((0.064, y0 + 0.09, zt - 0.020)), V((1, 0, 0)), r=0.050, t=0.012)
    D.plate(mb, V((-0.055, y0 + 0.09, zt)), right, fwd, n, 0.050, 0.120, 0.003, 'ck_black')
    oriented_quad(mb, [V((-0.059, y0 + 0.04, zt + 0.0042)), V((-0.051, y0 + 0.04, zt + 0.0042)), V((-0.051, y0 + 0.14, zt + 0.0042)), V((-0.059, y0 + 0.14, zt + 0.0042))], 'ck_panel', n)
    root = V((-0.055, y0 + 0.06, zt + 0.003)); tip = root + V((0, -0.010, 0.060))
    cylinder(mb, root, tip, 0.004, N=6, mat='ck_bezel', cap0=False)
    box(mb, tuple(tip), (0.040, 0.012, 0.012), 'ck_black')
    for k in range(3):
        D.legend(mb, V((-0.030, y0 + 0.05 + 0.04 * k, zt + 0.003)), right, fwd, n, 0.008, 0.002)


# ------------------------------------------------------------------------------------------------ side consoles

def console_detail196(mb, sx, z1):
    """1.9.6 side console top: comm panel (volume knobs + push buttons), oxygen panel (flow blinker, supply toggle, legends), switch panel
    (two toggle rows), and a map pocket on the inboard face (21 mm clear of the seat)."""
    n = V((0, 0, 1)); right = V((sx, 0, 0)); fwd = V((0, 1, 0))
    xin = CONSOLE_X0 + 0.015
    def W(y):
        return wall_x(y, z1, 0.03) - 0.015
    for ya, yb, kind in ((3.06, 3.32, 'comm'), (3.38, 3.62, 'oxy'), (3.68, 3.98, 'sw'), (4.02, 4.20, 'sw2')):
        wd = min(W(ya), W(yb)) - xin
        xm = xin + wd / 2
        c = V((sx * xm, (ya + yb) / 2, z1))
        D.plate(mb, c, right, fwd, n, wd, yb - ya, 0.004, 'ck_black')
        f = c + n * 0.004
        if kind == 'comm':
            for k in range(4):
                p = f + right * (-wd / 2 + 0.05 + 0.075 * k) + fwd * 0.05
                if abs(p.x) < W(p.y) - 0.015:
                    D.knob(mb, p, n, 0.009, 0.012, N=10); D.legend(mb, p - fwd * 0.018, right, fwd, n, 0.012, 0.002)
            D.pushbuttons(mb, f - fwd * 0.055, right, fwd, n, k=min(6, int((wd - 0.02) / 0.026)), pitch=0.026)
        elif kind == 'oxy':
            p = f + right * (-wd / 2 + 0.06)
            q = [p - right * 0.018 - fwd * 0.012, p + right * 0.018 - fwd * 0.012, p + right * 0.018 + fwd * 0.012, p - right * 0.018 + fwd * 0.012]
            oriented_quad(mb, [x_ + n * 0.0012 for x_ in q], 'ck_green', n)                       # flow blinker
            for k, dx in enumerate((0.13, 0.20)):
                D.toggle(mb, f + right * (-wd / 2 + dx), right, fwd, n, 0.022)
            D.rotary(mb, f + right * (-wd / 2 + 0.29) + fwd * 0.01, right, fwd, n, r=0.012)
            D.legend(mb, p + fwd * 0.025, right, fwd, n, 0.030, 0.003)
        else:
            rows = 2 if kind == 'sw' else 1
            for j in range(rows):
                for i in range(int((wd - 0.04) / 0.05)):
                    D.toggle(mb, f + right * (-wd / 2 + 0.04 + 0.05 * i) + fwd * (0.06 - 0.11 * j + (0.0 if rows == 2 else -0.04)), right, fwd, n)
    # map pocket on the inboard face of the console (a pouch 0.025 proud: the seat's outer edge is 0.051 inboard of the console)
    y0, y1, za, zb = 3.18, 3.58, 0.62, 0.82
    xo = sx * CONSOLE_X0; xi = sx * (CONSOLE_X0 - 0.025)
    for q, nn in (([V((xi, y0, za)), V((xi, y1, za)), V((xi, y1, zb - 0.03)), V((xi, y0, zb - 0.03))], V((-sx, 0, 0))),
                  ([V((xo, y0, za)), V((xi, y0, za)), V((xi, y0, zb - 0.03)), V((xo, y0, zb))], V((0, -1, 0))),
                  ([V((xo, y1, za)), V((xi, y1, za)), V((xi, y1, zb - 0.03)), V((xo, y1, zb))], V((0, 1, 0))),
                  ([V((xo, y0, za)), V((xi, y0, za)), V((xi, y1, za)), V((xo, y1, za))], V((0, 0, -1)))):
        oriented_quad(mb, q, 'ck_panel', nn)
    oriented_quad(mb, [V((xi, y0, zb - 0.03)), V((xi, y1, zb - 0.03)), V((xo, y1, zb)), V((xo, y0, zb))], 'ck_black', V((-sx, 0, 1)))   # opening


def build_consoles():
    out = []
    for s, sx in (('L', -1), ('R', 1)):
        mb = MeshBuf()
        ys = [CONSOLE_Y0 + (panel_y(sx * CONSOLE_X0, PANEL_ZB) - 0.006 - CONSOLE_Y0) * k / 8 for k in range(9)]
        z0, z1 = WELL_Z, CONSOLE_TOP
        outer = [wall_x(y, z1, 0.03) for y in ys]
        for ya, yb, oa, ob in zip(ys, ys[1:], outer, outer[1:]):
            top = [V((sx * CONSOLE_X0, ya, z1)), V((sx * oa, ya, z1)), V((sx * ob, yb, z1)), V((sx * CONSOLE_X0, yb, z1))]
            oriented_quad(mb, top, 'ck_od', V((0, 0, 1)))
            oriented_quad(mb, [V((sx * CONSOLE_X0, ya, z0)), V((sx * CONSOLE_X0, yb, z0)), V((sx * CONSOLE_X0, yb, z1)), V((sx * CONSOLE_X0, ya, z1))], 'ck_panel', V((-sx, 0, 0)))
            oriented_quad(mb, [V((sx * oa, ya, z0)), V((sx * ob, yb, z0)), V((sx * ob, yb, z1)), V((sx * oa, ya, z1))], 'ck_panel', V((sx, 0, 0)))
        for y, o, nrm in ((ys[0], outer[0], V((0, -1, 0))), (ys[-1], outer[-1], V((0, 1, 0)))):
            oriented_quad(mb, [V((sx * CONSOLE_X0, y, z0)), V((sx * o, y, z0)), V((sx * o, y, z1)), V((sx * CONSOLE_X0, y, z1))], 'ck_panel', nrm)
        if DETAIL:
            console_detail196(mb, sx, z1)
        # three switch plates with toggles / knobs on top
        for k, (ya, yb) in enumerate(((3.08, 3.36), (3.44, 3.72), (3.80, 4.06)) if not DETAIL else ()):
            xm = (CONSOLE_X0 + min(wall_x(ya, z1, 0.03), wall_x(yb, z1, 0.03))) / 2
            wdt = min(wall_x(ya, z1, 0.03), wall_x(yb, z1, 0.03)) - CONSOLE_X0 - 0.06
            box(mb, (sx * xm, (ya + yb) / 2, z1 + 0.003), (wdt, yb - ya, 0.006), 'ck_black')
            for j in range(3):
                for i in range(2):
                    p = V((sx * (CONSOLE_X0 + 0.06 + i * 0.12), ya + 0.06 + j * 0.08, z1 + 0.006))
                    if k == 1 and i == 1:
                        cylinder(mb, p, p + V((0, 0, 0.018)), 0.011, N=12, mat='ck_bezel')          # knobs
                    else:
                        cylinder(mb, p, p + V((0, 0, 0.022)), 0.0045, N=8, mat='ck_bezel')          # toggles
        out.append(Part(f'cockpit_console_{s}', 'cockpit_interior', mesh=mb, info={'kind': 'cockpit'}))
    return out


# ------------------------------------------------------------------------------------------------ floor, footwells, walls, rails, boots
def build_interior():
    mb = MeshBuf()
    y_back = S.BAY_Y[1] + 0.03
    ys = [y_back + (WELL_Y0 - y_back) * k / 14 for k in range(15)]
    for ya, yb in zip(ys, ys[1:]):                                      # deck floor, wall to wall (EWO platform level)
        wa, wb = wall_x(ya, FLOOR_Z, 0.02), wall_x(yb, FLOOR_Z, 0.02)
        dquad(mb, [V((-wa, ya, FLOOR_Z)), V((wa, ya, FLOOR_Z)), V((wb, yb, FLOOR_Z)), V((-wb, yb, FLOOR_Z))], 'ck_panel', V((0, 0, 1)))
    # forward of the riser: the floor outboard of the footwells (under the consoles) and the footwell floor
    for xa, xb in ((-WELL_X, WELL_X),):
        dquad(mb, [V((xa, WELL_Y0, WELL_Z)), V((xb, WELL_Y0, WELL_Z)), V((xb, WELL_Y1, WELL_Z)), V((xa, WELL_Y1, WELL_Z))], 'ck_panel', V((0, 0, 1)))
    dquad(mb, [V((-WELL_X, WELL_Y0, WELL_Z)), V((WELL_X, WELL_Y0, WELL_Z)), V((WELL_X, WELL_Y0, FLOOR_Z)), V((-WELL_X, WELL_Y0, FLOOR_Z))], 'ck_od', V((0, 1, 0)))   # riser
    for sx in (-1, 1):                                                  # footwell side walls between the console fronts and the knee wall
        yc = panel_y(sx * WELL_X, PANEL_ZB) - 0.012
        yb_ = panel_pt(sx * WELL_X, PANEL_ZB)[0].y - panel_pt(sx * WELL_X, PANEL_ZB)[1].y * PANEL_T
        dquad(mb, [V((sx * WELL_X, yc, WELL_Z)), V((sx * WELL_X, WELL_Y1, WELL_Z)), V((sx * WELL_X, WELL_Y1, 0.80)), V((sx * WELL_X, yb_, PANEL_ZB - 0.01)), V((sx * WELL_X, yc, PANEL_ZB - 0.01))], 'ck_od', V((-sx, 0, 0)))
    # seat rails (the stock seats' base sits 4.4 cm above the floor) and stick boots
    seat_y = M.EYE_PILOT[1] + 0.024
    for ex in (M.EYE_PILOT[0], M.EYE_COPILOT[0]):
        gap = M.EYE_PILOT[2] - 1.027 - FLOOR_Z                      # stock seat base above the floor (4 mm)
        for dx in (-0.16, 0.16):
            box(mb, (ex + dx, seat_y - 0.02, FLOOR_Z + gap * 0.4), (0.035, 0.80, gap * 0.8), 'ck_bezel')
        box(mb, (ex, seat_y - 0.02, FLOOR_Z + 0.001), (0.40, 0.84, 0.002), 'ck_black')
    for side in (-1, 1):
        sx_, sy_, sz_ = M.stick_anchor(side)
        # boot: flange on the footwell floor, tapered sleeve open at the top (the sfb_joystick shaft, 34 x 64 mm, rises out of it and tilts
        # +-12 deg about its foot inside the 45 mm opening), closed 3 mm under the stick foot
        cylinder(mb, V((sx_, sy_, WELL_Z)), V((sx_, sy_, WELL_Z + 0.018)), 0.080, N=24, mat='ck_black')
        cylinder(mb, V((sx_, sy_, WELL_Z + 0.018)), V((sx_, sy_, sz_ + 0.027)), 0.062, 0.052, N=24, mat='ck_black', cap1=False)
        top_o = circle_pts(V((sx_, sy_, sz_ + 0.027)), V((0, 0, 1)), 0.052, 24)
        top_i = circle_pts(V((sx_, sy_, sz_ + 0.027)), V((0, 0, 1)), 0.045, 24)
        bot_i = circle_pts(V((sx_, sy_, sz_ - 0.012)), V((0, 0, 1)), 0.045, 24)
        annulus(mb, top_o, top_i, 'ck_black', V((0, 0, 1)))
        loft(mb, [top_i, bot_i], 'ck_black', outward=False, smooth=False)
        fan_cap(mb, bot_i, V((sx_, sy_, sz_ - 0.012)), 'ck_black', V((0, 0, 1)))
    # left aft wall liner (y_back .. console start), from the floor up under the roof frame (the right side is the EWO bank)
    ys = [y_back + (CONSOLE_Y0 - y_back) * k / 6 for k in range(7)]
    zs = [FLOOR_Z + (1.85 - FLOOR_Z) * k / 10 for k in range(11)]
    for ya, yb in zip(ys, ys[1:]):
        for za, zb in zip(zs, zs[1:]):
            q = [V((-wall_x(ya, za, 0.03), ya, za)), V((-wall_x(yb, za, 0.03), yb, za)), V((-wall_x(yb, zb, 0.03), yb, zb)), V((-wall_x(ya, zb, 0.03), ya, zb))]
            dquad(mb, q, 'ck_od', V((1, 0, 0)))
    MST.bay_bulkhead(mb)
    return Part('cockpit_interior', 'fus_cockpit', mesh=mb, info={'kind': 'cockpit'})


def stock_anchors():
    """empties where Unity places the single stock parts (identity frames: the stock meshes keep their own orientation)."""
    out = []
    for name, mesh, mats, pos in kit():
        out.append(Part(name, 'cockpit_interior', pivot=V(pos), info={'kind': 'stock_anchor', 'stock': mesh, 'materials': mats}))
    return out


def kit():
    """(our name, stock mesh, stock materials per submesh, Blender position of the mesh origin)."""
    k = [('stick_L', 'sfb_joystick', ['hotas', 'SFB_cockpit'], M.stick_anchor(-1)),
         ('stick_R', 'sfb_joystick', ['hotas', 'SFB_cockpit'], M.stick_anchor(1)),
         ('cockpit_throttle', 'sfb_throttle', ['SFB_cockpit'], M.throttle_anchor())]
    for s, t in zip(('L', 'R'), lamp_targets()):
        k.append((f'warnlamp_{s}', 'EW1_warningLights', ['CockpitWarningLight'], tuple(t - V(M.EW1_LAMP_LOCAL))))
    return k


def overhead196():
    """the 1.9.2 overhead strip (unchanged position / size) + 1.9.6 breaker rows on its two aft segments and legends under its switches."""
    oh = MST.overhead_part()
    if not DETAIL:
        return oh
    y0, y1 = MST.OVERHEAD_Y
    n, right, up = V((0, 0, -1)), V((1, 0, 0)), V((0, 1, 0))
    for k in range(6):
        ya, yb = y0 + (y1 - y0) * k / 6, y0 + (y1 - y0) * (k + 1) / 6
        zt = min(S.fus_station(ya)[0], S.fus_station(yb)[0]) - 0.03
        c = V((0, (ya + yb) / 2, zt - 0.0600))
        if k < 2:
            D.breakers(oh.mesh, c + V((0, 0.018, 0.0)), right, up, n, cols=7, rows=1, pitch=0.026)
        else:
            for j in range(3):
                D.legend(oh.mesh, V((-0.06 + 0.06 * j, (ya + yb) / 2 - 0.016, zt - 0.0601)), right, up, n, 0.016, 0.0025)
    return oh


def build():
    return [build_interior()] + build_panel() + [build_glareshield(), build_pedestal()] + build_consoles() + [overhead196()] + stock_anchors()
