"""MSB-17/80 digital two-pilot cockpit + the two mission stations (custom structure only; the seats, sticks and throttle are the stock
SFB-81 / ejection-seat parts kitbashed in Unity, memory kitbash-stock-parts: a two-pilot bomber takes the bomber stick and throttle).

  flight deck (fus_cockpit, floor z 0.40): floor, side consoles, centre pedestal (throttle anchor), main panel with five screens under a glare
  shield (mfd_left / mfd_center / mfd_right = live stock tac pages in Unity; cockpit_screen_pilot / _copilot = stock dark glass), stick anchors
  stick_L / stick_R (stock sfb_joystick), rear bulkhead at the bay front.
  EWO (centre section, behind the co-pilot): console with two screens on the right wall, facing outboard.
  WSO (nose, the B-17G bombardier position): low console under the glazing with two screens.
Crew eyes crew_eye_<role> (pilot, copilot, wso, ewo) + cockpit_eye; nothing stands between an eye and its screens (Blender check j).
"""
import math
from mathutils import Vector as V, Quaternion, Matrix
import b17g_spec as S
import msb_spec as M
from b25h_geom import MeshBuf, circle_pts, loft, fan_cap, annulus, oriented_quad, cylinder, box
from b25h_parts import Part

FLOOR_Z = M.FLOOR_Z
Y_BACK = S.BAY_Y[1] + 0.03          # flight deck runs back to the bay's front bulkhead
PANEL_Y0, PANEL_K, PANEL_HW, PANEL_ZB, PANEL_ZT = 4.22, 0.08, 0.95, 0.95, 1.43
TILT = math.radians(14)             # panel face leans back (top toward the nose) 14 deg


def wall_x(y, z, inset=0.02):
    import b17g_parts as P
    return P.fus_skin_x(y, z, inset)


def panel_pt(x, z, off=0.0):
    """point on the main panel face (plan curve y = Y0 - K x^2, leaning back by TILT about its bottom edge); off = toward the pilots."""
    y = PANEL_Y0 - PANEL_K * x * x + (z - PANEL_ZB) * math.tan(TILT)
    n = V((-2 * PANEL_K * x, -1.0, -math.tan(TILT))).normalized()
    return V((x, y, z)) + n * off, n


def screen_quad(mb, x, z, w, h, off, mat):
    c, n = panel_pt(x, z, off)
    right = V((1, 2 * PANEL_K * x * 0, 0)).cross(n).cross(n) * -1
    right = V((1.0, -2 * PANEL_K * x, 0.0)).normalized()
    up = n.cross(right).normalized() * -1
    if up.z < 0:
        up = -up
    q = [c - right * (w / 2) - up * (h / 2), c + right * (w / 2) - up * (h / 2), c + right * (w / 2) + up * (h / 2), c - right * (w / 2) + up * (h / 2)]
    oriented_quad(mb, q, mat, -n)
    return q, n


SCREENS = [('mfd_left', -0.66, 1.17, 0.26, 0.21), ('cockpit_screen_pilot', -0.34, 1.17, 0.27, 0.22), ('mfd_center', 0.0, 1.15, 0.30, 0.26),
           ('cockpit_screen_copilot', 0.34, 1.17, 0.27, 0.22), ('mfd_right', 0.66, 1.17, 0.26, 0.21)]


def build_structure():
    out = []
    mb = MeshBuf()
    # floor (both faces) from the bay bulkhead to under the panel
    yf = PANEL_Y0 + 0.05
    box(mb, (0, (Y_BACK + yf) / 2, FLOOR_Z - 0.02), (2.2, yf - Y_BACK, 0.04), 'ck_floor')
    # rear bulkhead (bay front), cut to the fuselage section, both faces
    top = S.fus_station(Y_BACK)[0]
    zs = [FLOOR_Z + (top - 0.03 - FLOOR_Z) * k / 14 for k in range(15)]
    for za, zb in zip(zs, zs[1:]):
        wa, wb = wall_x(Y_BACK - 0.02, za), wall_x(Y_BACK - 0.02, zb)
        q = [V((-wa, Y_BACK - 0.02, za)), V((wa, Y_BACK - 0.02, za)), V((wb, Y_BACK - 0.02, zb)), V((-wb, Y_BACK - 0.02, zb))]
        oriented_quad(mb, q, 'ck_wall', V((0, 1, 0)))
        oriented_quad(mb, [p + V((0, -0.025, 0)) for p in q], 'ck_wall', V((0, -1, 0)))
    # side consoles along both walls (pilot / co-pilot), top at z 0.90, switch-panel strips and knobs
    for sx in (-1, 1):
        y0, y1 = 2.95, 4.05
        xin = 0.72
        for ya, yb in ((y0, y1),):
            xo = wall_x((ya + yb) / 2, 0.75, 0.03)
            box(mb, (sx * (xin + xo) / 2, (ya + yb) / 2, (FLOOR_Z + 0.90) / 2), (xo - xin, yb - ya, 0.90 - FLOOR_Z), 'ck_panel')
            for k in range(5):
                yy = ya + 0.12 + k * 0.20
                box(mb, (sx * (xin + xo) / 2, yy, 0.905), ((xo - xin) * 0.8, 0.14, 0.012), 'ck_black')
                for j in range(3):
                    cylinder(mb, V((sx * (xin + 0.04 + j * 0.06), yy, 0.91)), V((sx * (xin + 0.04 + j * 0.06), yy, 0.935)), 0.010, N=8, mat='ck_bezel')
    # centre pedestal between the seats (throttle quadrant on top: stock sfb_throttle in Unity at cockpit_throttle)
    box(mb, (0, 3.80, (FLOOR_Z + 0.86) / 2), (0.22, 0.84, 0.86 - FLOOR_Z), 'ck_panel')
    box(mb, (0, 3.80, 0.868), (0.19, 0.80, 0.016), 'ck_black')
    for k in range(4):
        box(mb, (0, 4.05 + 0.03 * k, 0.88), (0.16, 0.02, 0.012), 'ck_bezel')
    # main panel: the face (ck_panel, both faces), recessed screen frames, glare shield on top, knee wall below
    xs = [-PANEL_HW + 2 * PANEL_HW * k / 20 for k in range(21)]
    zs_ = [PANEL_ZB + (PANEL_ZT - PANEL_ZB) * k / 6 for k in range(7)]
    for xa, xb in zip(xs, xs[1:]):
        for za, zb in zip(zs_, zs_[1:]):
            q = [panel_pt(xa, za)[0], panel_pt(xb, za)[0], panel_pt(xb, zb)[0], panel_pt(xa, zb)[0]]
            n = panel_pt((xa + xb) / 2, (za + zb) / 2)[1]
            oriented_quad(mb, q, 'ck_panel', n)
            oriented_quad(mb, [p - n * 0.02 for p in q], 'ck_panel', -n)
    for name, x, z, w, h in SCREENS:
        q, n = screen_quad(mb, x, z, w + 0.05, h + 0.05, 0.004, 'ck_black')          # bezel plate
        for a_, b_ in zip(q, q[1:] + q[:1]):
            NS_bar(mb, a_ - n * 0.0, b_ - n * 0.0, 0.016, 0.014, -n)
        for k in range(6):                                                           # soft keys along the bezel bottom
            px, pz = x - w / 2 + (k + 0.5) * w / 6, z - h / 2 - 0.018
            c_, n_ = panel_pt(px, pz, 0.010)
            box(mb, tuple(c_), (0.022, 0.012, 0.012), 'ck_bezel')
    # glare shield: a sloped hood over the panel top (both faces)
    for xa, xb in zip(xs, xs[1:]):
        a0 = panel_pt(xa, PANEL_ZT)[0]; b0 = panel_pt(xb, PANEL_ZT)[0]
        a1 = a0 + V((0, -0.16, 0.03)); b1 = b0 + V((0, -0.16, 0.03))
        oriented_quad(mb, [a0, b0, b1, a1], 'ck_black', V((0, 0, 1)))
        oriented_quad(mb, [p - V((0, 0, 0.012)) for p in (a0, b0, b1, a1)], 'ck_black', V((0, 0, -1)))
    # knee wall under the panel (dark), to the floor
    for xa, xb in zip(xs, xs[1:]):
        a0 = panel_pt(xa, PANEL_ZB)[0]; b0 = panel_pt(xb, PANEL_ZB)[0]
        q = [V((a0.x, a0.y, FLOOR_Z)), V((b0.x, b0.y, FLOOR_Z)), b0, a0]
        oriented_quad(mb, q, 'ck_black', V((0, -1, 0)))
    # HUD combiner frame above the glare shield on the pilot side (the game draws the HUD; this is only the glass frame)
    hc = panel_pt(-0.45, PANEL_ZT)[0] + V((0, -0.10, 0.04))
    for dx in (-0.08, 0.08):
        box(mb, (hc.x + dx, hc.y, hc.z + 0.06), (0.012, 0.012, 0.12), 'ck_bezel')
    out.append(Part('cockpit_interior', 'fus_cockpit', mesh=mb, info={'kind': 'cockpit'}))
    # screens: separate quads on the 'screen' material (Unity puts the stock tac page / dark glass on them)
    for name, x, z, w, h in SCREENS:
        sm = MeshBuf()
        q, n = screen_quad(sm, x, z, w, h, 0.012, 'screen')
        for f in sm.faces:
            f['uv'] = [(0, 0), (1, 0), (1, 1), (0, 1)]
        out.append(Part(name, 'cockpit_interior', mesh=sm, info={'kind': 'screen', 'w': w, 'h': h}))
    # EWO station (centre section): console on the right wall with two screens, small desk
    em = MeshBuf()
    ex, ey = M.EYE_EWO[0], M.EYE_EWO[1]
    xw = wall_x(ey, 1.0, 0.04)
    box(em, ((ex + 0.30 + xw) / 2, ey, 0.80), (xw - ex - 0.30, 0.70, 0.04), 'ck_panel')                           # desk
    box(em, ((ex + 0.30 + xw) / 2, ey, (FLOOR_Z + 0.78) / 2), (xw - ex - 0.30, 0.60, 0.78 - FLOOR_Z), 'ck_panel')   # pedestal
    xp = min(xw - 0.04, ex + 0.62)
    box(em, (xp + 0.02, ey, 1.25), (0.04, 0.78, 0.80), 'ck_panel')                                                 # screen panel
    out.append(Part('cockpit_ewo_console', 'B17G', mesh=em, info={'kind': 'cockpit'}))
    for k, dy in enumerate((-0.21, 0.17)):
        sm = MeshBuf()
        c = V((xp - 0.002, ey + dy, 1.30))
        q = [c + V((0, -0.15, -0.12)), c + V((0, 0.15, -0.12)), c + V((0, 0.15, 0.12)), c + V((0, -0.15, 0.12))]
        oriented_quad(sm, q, 'screen', V((-1, 0, 0)))
        for f in sm.faces:
            f['uv'] = [(0, 0), (1, 0), (1, 1), (0, 1)]
        out.append(Part(f'cockpit_screen_ewo{k + 1}', 'cockpit_ewo_console', mesh=sm, info={'kind': 'screen'}))
    # WSO station (nose): low sloped console ahead of the WSO under the glazing, two screens
    wm = MeshBuf()
    wy = M.EYE_WSO[1]
    cz0 = M.NOSE_FLOOR_Z
    box(wm, (0, wy + 0.42, (cz0 + 0.52) / 2), (0.62, 0.16, 0.52 - cz0), 'ck_panel')
    slope = [V((-0.31, wy + 0.34, 0.52)), V((0.31, wy + 0.34, 0.52)), V((0.31, wy + 0.50, 0.70)), V((-0.31, wy + 0.50, 0.70))]
    oriented_quad(wm, slope, 'ck_panel', V((0, -0.75, 0.66)))
    oriented_quad(wm, [p + V((0, 0.012, -0.010)) for p in slope], 'ck_panel', V((0, 0.75, -0.66)))
    so = V((0, 0.012, -0.010))      # closed edges (the open top edge showed its back face to a ray from above: Blender n17)
    oriented_quad(wm, [slope[3], slope[2], slope[2] + so, slope[3] + so], 'ck_panel', V((0, 0.66, 0.75)))
    for a_, b_, n_ in ((slope[0], slope[3], V((-1, 0, 0))), (slope[1], slope[2], V((1, 0, 0)))):
        oriented_quad(wm, [a_, b_, b_ + so, a_ + so], 'ck_panel', n_)
    out.append(Part('cockpit_wso_console', 'fus_nose', mesh=wm, info={'kind': 'cockpit'}))
    nrm = V((0, -0.75, 0.66)).normalized()
    for k, dx in enumerate((-0.15, 0.15)):
        sm = MeshBuf()
        c = (slope[0] + slope[2]) / 2 + V((dx, 0, 0)) + nrm * 0.004
        u = (slope[2] - slope[1]).normalized()
        q = [c - V((0.12, 0, 0)) - u * 0.09, c + V((0.12, 0, 0)) - u * 0.09, c + V((0.12, 0, 0)) + u * 0.09, c - V((0.12, 0, 0)) + u * 0.09]
        oriented_quad(sm, q, 'screen', nrm)
        for f in sm.faces:
            f['uv'] = [(0, 0), (1, 0), (1, 1), (0, 1)]
        out.append(Part(f'cockpit_screen_wso{k + 1}', 'cockpit_wso_console', mesh=sm, info={'kind': 'screen'}))
    return out


def NS_bar(mb, a, b, w, h, up):
    import nimrod_structure as NS
    NS.sec_tube(mb, a, b, w, h, up, mat='ck_bezel')


def axis_frame(xaxis, up=V((0, 0, 1))):
    x = V(xaxis).normalized()
    y = up.cross(x).normalized() if abs(up.dot(x)) < 0.99 else V((0, 1, 0))
    z = x.cross(y).normalized()
    return Matrix((x, y, z)).transposed().to_quaternion()


def anchors():
    """stick / throttle anchors (stock SFB-81 parts in Unity), cockpit eye, crew eyes (contract crew stations)."""
    out = []
    if not M.STOCK_DECK and not getattr(M, 'DECK195', False):     # 1.9.1: the EW-25 anchors come from msb_stations.stock_anchors; 1.9.5: msb_deck195
        for s, sx in (('L', -1), ('R', 1)):
            out.append(Part(f'stick_{s}', 'cockpit_interior', pivot=V((sx * 0.38, 3.96, FLOOR_Z + 0.01)), info={'kind': 'stock_anchor', 'stock': 'sfb_joystick'}))
        out.append(Part('cockpit_throttle', 'cockpit_interior', pivot=V((0.0, 3.72, 0.876)), info={'kind': 'stock_anchor', 'stock': 'sfb_throttle'}))
    out.append(Part('cockpit_eye', 'cockpit_interior', pivot=V(M.EYE_PILOT), info={'kind': 'eye', 'role': 'pilot'}))
    crew = [('pilot', 'fus_cockpit', V(M.EYE_PILOT), V((0, 1, 0)), 'hatch_pilot_L'), ('copilot', 'fus_cockpit', V(M.EYE_COPILOT), V((0, 1, 0)), 'hatch_pilot_R'),
            ('wso', 'fus_nose', V(M.EYE_WSO), V((0, 1, 0)), 'hatch_wso'), ('ewo', 'B17G', V(M.EYE_EWO), V((1, 0, 0)), 'hatch_ewo')]
    for i, (role, part, e, fwd, hatch) in enumerate(crew):
        out.append(Part(f'crew_eye_{role}', part, pivot=e, frame=axis_frame(fwd.cross(V((0, 0, 1)))),
                        info={'kind': 'crew_eye', 'role': role, 'part': part, 'index': i, 'forward': list(fwd), 'exit_hatch': hatch}))
    return out
