"""B-17G cockpit (Phase B milestone 2, round 2 after the coordinator's review). Period layout from the user's photos 106-111 and the
WW2 cockpit diagram (viewed only, never copied): two seats side by side, two B-17 control wheels (horizontal bar + half-wheel rim
below it, hub emblem) on thick green columns, the black pedestal with the throttle quadrant (four throttles with stacked T-bar
handles, T-1/T-4 high, T-2/T-3 low), the C-1 autopilot box below it, a wide nearly flat black panel with the arched top
(flight group left, boxed engine group centre, temperatures + starter / fire-extinguisher panels right, FLYING FORTRESS plate far
left), a thin coaming lip and a dark deck up to the windscreen frame, a small standby compass on the coaming. No rudder pedals, no
modern parts (no GPS / radio stack). The cab glazing + riveted frames are part of the skin (b17g_parts.cab_* : anchored ring).

fal art: seats, control wheels, columns, quadrant body, C-1 box (3D, src/fal/ck_*), dial faces + placards + panel / wall tiles
(assets/textures_b17g/fal_ck). Hand geometry only for structure / fit (floor, panel shell, coaming, pedestal, sub-panel outlines,
rivets, buttons, compass housing, throttle arms / T-bars that must move).

Contract (B-25H conventions, read by B17GBuild.cs and B25H.Instruments' B17G branch):
- needles / cards: object local +X points AT THE PILOT (dial normal), rest = 12 o'clock, +angle about local +X = clockwise seen by the pilot;
- controls: cockpit_column_L/R pitch about local +X at the floor pivot, cockpit_yoke_L/R roll about local +X (the column axis toward
  the pilot); Cockpit throttles: cockpit_throttle_1..4 rotate about local +X at their pivot (Blender -X = grip forward = full);
- eyes: cockpit_eye (pilot, left seat) and the crew_eye_* empties (10 crew).
"""
import math, json
from mathutils import Vector as V, Matrix, Quaternion
import b17g_spec as S
from b25h_geom import MeshBuf, box, cylinder, circle_pts, loft, fan_cap, oriented_quad, annulus
from b25h_parts import Part
import nimrod_structure as NS

FLOOR_Z = 0.40
Y_BACK, Y_FRONT = 2.95, 4.32
EYE_L = V((-0.45, 3.32, 1.70))        # round 2: seated eye 1.30 above the floor (was 1.55: the nose top hid the view)
EYE_R = V((0.45, 3.32, 1.70))

# panel: nearly flat (slight plan curve), arched top, wall to wall
PANEL_Y0, PANEL_K = 4.25, 0.10        # y(x) = Y0 - K x^2
PANEL_HW = 0.97
PANEL_ZB = 0.92


def panel_y(x):
    return PANEL_Y0 - PANEL_K * x * x


def panel_ztop(x):
    ax = abs(x)
    return 1.56 - 0.05 * (ax / 0.55) ** 2 if ax <= 0.55 else 1.51 - (ax - 0.55) / (PANEL_HW - 0.55) * 0.11


def panel_normal(x):
    return V((-2 * PANEL_K * x, -1.0, 0.0)).normalized()     # toward the pilots (-Y), tilted inward at the sides


def panel_point(x, z, off=0.0):
    return V((x, panel_y(x), z)) + panel_normal(x) * off


# gauges: (name, x, z, face, kind, radius). 1.8.4 (offline C): every dial is driven - 40 movers (names fixed by the plugin B17G.cs + the Unity
# check). The fal faces of suction / hyd / clock / engine gauge units / oil temps carry no painted needle, so the 1.8.3 'static' dials read nothing.
R_BIG, R_MED, R_SMALL = 0.050, 0.044, 0.034
GAUGES = [
    # flight group (left, boxed): gyro horizon + directional gyro on top, ASI / altimeter / turn & bank / rate of climb below
    ('dg', -0.50, 1.395, 'dial_dg', 'card', R_BIG), ('att', -0.37, 1.395, None, 'attitude', R_BIG), ('suction', -0.245, 1.400, 'dial_suction', 'needle', R_SMALL),
    ('asi', -0.56, 1.265, 'dial_asi', 'needle', R_BIG), ('alt', -0.43, 1.265, 'dial_alt', 'altimeter', R_BIG),
    ('turn', -0.30, 1.265, 'dial_turn', 'needle', R_BIG), ('vsi', -0.17, 1.265, 'dial_vsi', 'needle', R_BIG),
    ('clock', -0.10, 1.400, 'dial_clock', 'clock', R_SMALL),
    # engine group (centre, boxed): manifold pressure pair, tachometer pair, the four engine gauge units (fuel / oil press, oil temp)
    ('mp_12', 0.06, 1.395, 'dial_mp', 'dual', R_BIG), ('mp_34', 0.19, 1.395, 'dial_mp', 'dual', R_BIG),
    ('rpm_12', 0.06, 1.265, 'dial_rpm', 'dual', R_BIG), ('rpm_34', 0.19, 1.265, 'dial_rpm', 'dual', R_BIG),
    ('egu_1', 0.035, 1.115, 'dial_egu', 'egu', R_MED), ('egu_2', 0.135, 1.115, 'dial_egu', 'egu', R_MED),
    ('egu_3', 0.235, 1.115, 'dial_egu', 'egu', R_MED), ('egu_4', 0.335, 1.115, 'dial_egu', 'egu', R_MED),
    # right group: cylinder-head temperatures (driven, per engine) + the two oil temperature gauges
    ('cht_1', 0.45, 1.380, 'dial_temp', 'needle', R_MED), ('cht_2', 0.56, 1.380, 'dial_temp', 'needle', R_MED),
    ('cht_3', 0.45, 1.265, 'dial_temp', 'needle', R_MED), ('cht_4', 0.56, 1.265, 'dial_temp', 'needle', R_MED),
    ('oilt_12', 0.45, 1.140, 'dial_oilt', 'dual', R_SMALL), ('oilt_34', 0.56, 1.140, 'dial_oilt', 'dual', R_SMALL),
    # far left: clock-size suction / hydraulic pair under the nameplate
    ('hyd', -0.86, 1.255, 'dial_suction', 'needle', R_SMALL),
]
# placards: (name, x, z, w, h, face)
PLATES = [('plate_ff', -0.82, 1.37, 0.24, 0.085, 'plate_ff'), ('plate_warn', -0.80, 1.10, 0.22, 0.085, 'plate_warn'),
          ('plate_start', 0.83, 1.34, 0.24, 0.13, 'plate_start'), ('plate_fire', 0.83, 1.14, 0.24, 0.13, 'plate_fire')]
# sub-panel outlines (x0, x1, z0, z1)
BOXES = [(-0.64, -0.04, 1.175, 1.47), (-0.02, 0.39, 1.055, 1.47), (0.40, 0.62, 1.09, 1.45), (-0.97, -0.67, 1.03, 1.43), (0.69, 0.98, 1.06, 1.425)]
BUTTONS = [-0.50, -0.44, -0.30, -0.24]        # red feathering buttons (two pairs, guarded) in the centre row
BUTTON_Z = 1.115
FACES = ['dial_asi', 'dial_alt', 'dial_vsi', 'dial_mp', 'dial_rpm', 'dial_turn', 'dial_dg', 'dial_temp', 'att_sky', 'att_ground',
         'dial_egu', 'dial_oilt', 'dial_clock', 'dial_suction', 'plate_ff', 'plate_warn', 'plate_start', 'plate_fire', 'red', 'black']
ATLAS_N = 5                               # 5 x 5 atlas cells of 512 (b17g_gauges.png)

# throttle quadrant (fal body on the pedestal; arms + T-bars are hand geometry because they move)
QUAD = V((0.0, 3.93, 0.86))               # body base centre (top of the pedestal box)
QUAD_W = 0.30
THROTTLE_X = [-0.081, -0.027, 0.027, 0.081]
THROTTLE_PIVOT_YZ = (3.95, 0.98)        # 1.6.1: inside the body, arms long enough that the T-bars stand clear above its slotted top
THROTTLE_TOP_Z = 1.04                     # check: grips stay above this at idle and full
YOKE_HUB_Y, YOKE_HUB_Z = 3.92, 1.16
THROTTLE_REST = 20.0


# 1.8.4: sub-dial pivots on the fal faces (u, v in 0..1 of the dial disc, measured on the b17g_gauges cells), needle length (x R)
EGU_SUB = [('fuel', 0.500, 0.708, 0.27), ('oilp', 0.292, 0.417, 0.30), ('oilt', 0.708, 0.417, 0.30)]
CLOCK_SEC = (0.500, 0.229, 0.26)
N_MOVERS = 40


def gauge_centre(g):
    return panel_point(g[1], g[2], 0.004)


def atlas_uv(face, u, v):
    """cell of FACES in the ATLAS_N x ATLAS_N atlas; u, v in 0..1 inside the cell."""
    i = FACES.index(face)
    cx, cy = i % ATLAS_N, i // ATLAS_N
    return ((cx + 0.02 + 0.96 * u) / ATLAS_N, 1.0 - (cy + 0.02 + 0.96 * (1 - v)) / ATLAS_N)


def axis_frame(xaxis, up=V((0, 0, 1))):
    x = V(xaxis).normalized()
    z = (up - x * up.dot(x)).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed().to_quaternion()


def wall_x(y, z, inset=0.012):
    top, bot, hw, n = S.fus_station(y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    t = min(abs(z - cz) / hz, 0.999)
    return (hw - inset) * (1 - t ** n) ** (1.0 / n)


def stud(mb, p, nrm, mat, r=0.0045, h=0.004):
    """rivet / screw head: 4-sided low pyramid on a surface (normal nrm)."""
    a = nrm.orthogonal().normalized(); b = nrm.cross(a)
    sq = [p + a * r, p + b * r, p - a * r, p - b * r]
    tip = p + nrm * h
    for u_, v_ in zip(sq, sq[1:] + sq[:1]):
        tri = [u_, v_, tip] if (v_ - u_).cross(tip - u_).dot(nrm) > 0 else [v_, u_, tip]
        mb.poly(tri, mat)


def uv_prism(mb, p0, p1, r, N, face, mat='gauges'):
    """closed cylinder whose every corner samples one atlas cell centre (solid colour from the gauge atlas: red buttons, black)."""
    uvc = atlas_uv(face, 0.5, 0.5)
    ax = (p1 - p0).normalized()
    r0, r1 = circle_pts(p0, ax, r, N), circle_pts(p1, ax, r, N)
    for k in range(N):
        a, b, c, d = r0[k], r0[(k + 1) % N], r1[(k + 1) % N], r1[k]
        mid = (a + b + c + d) / 4
        out = (mid - (p0 + p1) / 2); out -= ax * out.dot(ax)
        q = [a, b, c, d] if (b - a).cross(d - a).dot(out) > 0 else [a, d, c, b]
        mb.poly(q, mat, [uvc] * 4)
    for ring, cen, nrm in ((r0, p0, -ax), (r1, p1, ax)):
        for k in range(N):
            tri = [cen, ring[k], ring[(k + 1) % N]]
            if (tri[1] - tri[0]).cross(tri[2] - tri[0]).dot(nrm) < 0:
                tri = [cen, ring[(k + 1) % N], ring[k]]
            mb.poly(tri, mat, [uvc] * 3)


def build_structure():
    out = []
    mb = MeshBuf()
    # floor (both faces) between the walls, raised above the bombardier crawlway
    box(mb, (0, (Y_BACK + Y_FRONT) / 2, FLOOR_Z - 0.02), (2.2, Y_FRONT - Y_BACK, 0.04), 'ck_floor')
    # rear bulkhead with a dark doorway (bomb-bay catwalk door) - two side panels + lintel
    top = S.fus_station(Y_BACK)[0]
    # round 5 (user review 2, 03 'ears'): the bulkhead was two 0.80 m wide rectangles reaching x +-1.12 at z 1.88, where the fuselage
    # is only ~0.6 m wide: their outer corners stood out of the skin beside the top turret. Now cut to the fuselage section (2 cm
    # inside the skin), both faces, with the doorway (|x| < 0.32 up to top - 0.32)
    door_top = top - 0.32
    zs = [FLOOR_Z + (top - 0.03 - FLOOR_Z) * k / 16 for k in range(17)]
    zs = sorted(set(zs + [door_top]))
    for za, zb in zip(zs, zs[1:]):
        wa, wb = wall_x(Y_BACK - 0.02, za, 0.02), wall_x(Y_BACK - 0.02, zb, 0.02)
        if wa < 0.01 and wb < 0.01:
            continue
        segs = [(-1, 0.32), (1, 0.32)] if zb <= door_top + 1e-6 else [(0, 0.0)]
        for sx, xin in segs:
            if sx == 0:
                q = [V((-wa, Y_BACK - 0.02, za)), V((wa, Y_BACK - 0.02, za)), V((wb, Y_BACK - 0.02, zb)), V((-wb, Y_BACK - 0.02, zb))]
            else:
                q = [V((sx * xin, Y_BACK - 0.02, za)), V((sx * max(wa, xin), Y_BACK - 0.02, za)), V((sx * max(wb, xin), Y_BACK - 0.02, zb)), V((sx * xin, Y_BACK - 0.02, zb))]
            if (q[1] - q[0]).length < 1e-4 and (q[2] - q[3]).length < 1e-4:
                continue
            oriented_quad(mb, q, 'ck_wall', V((0, 1, 0)))
            oriented_quad(mb, [p + V((0, -0.025, 0)) for p in q], 'ck_wall', V((0, -1, 0)))
    # 1.6.1: the doorway is open onto the engineer's bay under the top turret (1.6.0: a flat black panel, 07_ck_back): door frame, bay
    # floor up to the bomb-bay bulkhead, the turret's lower ring (the engineer stands in it) and two ammunition boxes
    for sx in (-1, 1):
        box(mb, (sx * 0.335, Y_BACK - 0.02, (FLOOR_Z + top - 0.32) / 2), (0.04, 0.06, top - 0.32 - FLOOR_Z), 'ck_bezel')
    yb0 = S.BAY_Y[1] + 0.03
    box(mb, (0, (yb0 + Y_BACK) / 2, FLOOR_Z - 0.02), (1.20, Y_BACK - yb0, 0.04), 'ck_floor')
    tz = S.TURRETS['top']['pos'][2] - 0.22
    if S.ANM2_SLOTS:       # 1.8.13 r2: an open ring (r 0.43-0.46): the AN/M2 receivers swing down through it at high elevation (Sperry basket)
        ty_ = S.TURRETS['top']['pos'][1]
        for z_ in (tz - 0.05, tz):
            annulus(mb, circle_pts(V((0, ty_, z_)), V((0, 0, 1)), 0.46, 32), circle_pts(V((0, ty_, z_)), V((0, 0, 1)), 0.43, 32), 'ck_od', V((0, 0, 1 if z_ == tz else -1)))
        loft(mb, [circle_pts(V((0, ty_, tz - 0.05)), V((0, 0, 1)), 0.46, 32), circle_pts(V((0, ty_, tz)), V((0, 0, 1)), 0.46, 32)], 'ck_od')
        loft(mb, [circle_pts(V((0, ty_, tz - 0.05)), V((0, 0, 1)), 0.43, 32), circle_pts(V((0, ty_, tz)), V((0, 0, 1)), 0.43, 32)], 'ck_od', outward=False)
    else:
        cylinder(mb, V((0, S.TURRETS['top']['pos'][1], tz - 0.05)), V((0, S.TURRETS['top']['pos'][1], tz)), 0.30, N=20, mat='ck_od')
    for sx in (-1, 1):
        box(mb, (sx * 0.40, S.TURRETS['top']['pos'][1], tz - 0.38), (0.18, 0.30, 0.22), 'ck_od')     # round 5: top 1.83 (was 2.01, 2 cm through the roof skin)
    box(mb, (0, yb0 + 0.01, (FLOOR_Z + 1.30) / 2), (1.10, 0.02, 1.30 - FLOOR_Z), 'ck_wall')     # bomb-bay front bulkhead (seen through the door)
    # instrument panel: front face (ck_panel) + back face, arched top lip, bottom lip, ends; filler to the walls
    n = 34
    xs = [-PANEL_HW + 2 * PANEL_HW * k / n for k in range(n + 1)]
    lo = [V((x, panel_y(x), PANEL_ZB)) for x in xs]
    hi = [V((x, panel_y(x), panel_ztop(x))) for x in xs]
    back = lambda ring: [p + V((0, 0.03, 0)) for p in ring]
    for a, b, c, d in zip(lo, lo[1:], hi[1:], hi):
        oriented_quad(mb, [a, b, c, d], 'ck_panel', panel_normal((a.x + b.x) / 2))
    bl, bh = back(lo), back(hi)
    for a, b, c, d in zip(bl, bl[1:], bh[1:], bh):
        oriented_quad(mb, [a, b, c, d], 'ck_panel', V((0, 1, 0)))
    for ring, ringb, sgn in ((lo, bl, -1), (hi, bh, 1)):
        for a, b, c, d in zip(ring, ring[1:], ringb[1:], ringb):
            oriented_quad(mb, [a, b, c, d], 'ck_panel', V((0, 0, sgn)))
    for i, sx in ((0, -1), (-1, 1)):
        oriented_quad(mb, [lo[i], hi[i], bh[i], bl[i]], 'ck_panel', V((sx, 0, 0)))
        # filler from the panel end to the side wall (dark), z from the bottom to the top lip
        x0 = lo[i].x; y0 = lo[i].y
        zs = [PANEL_ZB + (hi[i].z - PANEL_ZB) * k / 4 for k in range(5)]
        inner = [V((x0, y0, z)) for z in zs]; outer = [V((sx * max(wall_x(y0, z, 0.08), PANEL_HW), y0, z)) for z in zs]
        for a, b, c, d in zip(inner, inner[1:], outer[1:], outer):
            wa, wb = abs(d.x - a.x) > 0.005, abs(c.x - b.x) > 0.005      # no zero-width filler where the wall meets the panel end
            if wa and wb:
                oriented_quad(mb, [a, b, c, d], 'ck_panel', V((0, -1, 0)))
            elif wa or wb:
                tri_ = [a, b, c] if wb else [a, b, d]
                if (tri_[1] - tri_[0]).cross(tri_[2] - tri_[0]).dot(V((0, -1, 0))) < 0:
                    tri_ = [tri_[0], tri_[2], tri_[1]]
                mb.poly(tri_, 'ck_panel')
    # under the panel: dark bulkhead to the floor (the nose crawlway is closed off in the game)
    yb = PANEL_Y0 + 0.05
    for a, b in zip(xs, xs[1:]):
        za, zb = PANEL_ZB, PANEL_ZB
        q = [V((a, yb, FLOOR_Z)), V((b, yb, FLOOR_Z)), V((b, yb, zb)), V((a, yb, za))]
        oriented_quad(mb, q, 'ck_od', V((0, -1, 0)))
    for sx in (-1, 1):
        zs = [FLOOR_Z + (PANEL_ZB - FLOOR_Z) * k / 4 for k in range(5)]
        inner = [V((sx * PANEL_HW, yb, z)) for z in zs]; outer = [V((sx * wall_x(yb, z), yb, z)) for z in zs]
        for a, b, c, d in zip(inner, inner[1:], outer[1:], outer):
            oriented_quad(mb, [a, b, c, d], 'ck_od', V((0, -1, 0)))
    # coaming: thin rounded lip along the arched panel top (photo 106), black
    lip = []
    for x in xs:
        c = V((x, panel_y(x) + 0.005, panel_ztop(x) + 0.012))
        t = V((1, -2 * PANEL_K * x, 0)).normalized()
        lip.append(circle_pts(c, t, 0.020, 10, ref=V((0, 0, 1))))
    loft(mb, lip, 'ck_black', closed=True)
    for ring, t in ((lip[0], V((-1, 0, 0))), (lip[-1], V((1, 0, 0)))):
        fan_cap(mb, ring, sum(ring, V()) / len(ring), 'ck_black', t)
    # deck under the windscreen: from behind the lip forward to the windscreen frame at y 4.55 (dark, both faces), wall to wall
    yd = 4.56
    topd, botd, hwd, nd = S.fus_station(yd)
    czd, hzd = (topd + botd) / 2, (topd - botd) / 2
    def skin_z(x):
        t = min(abs(x) / max(hwd - 0.03, 0.01), 0.999)
        return czd + (hzd - 0.03) * (1 - t ** nd) ** (1.0 / nd)
    rear = [V((x, panel_y(x) + 0.03, panel_ztop(x) + 0.012)) for x in xs]
    front = [V((x * 0.97, yd, max(skin_z(x * 0.97), panel_ztop(x) + 0.012))) for x in xs]
    for a, b, c, d in zip(rear, rear[1:], front[1:], front):
        oriented_quad(mb, [a, b, c, d], 'ck_black', V((0, -0.3, 1)))
        oriented_quad(mb, [p - V((0, 0, 0.008)) for p in (a, b, c, d)], 'ck_black', V((0, 0.3, -1)))
    # pedestal box between the seats (the fal quadrant on top, the fal C-1 box on its aft face)
    # 1.6.1 (in game 1.6.0 a plain black box): plinth, inset olive side / aft panels with dark frames, corner posts, control cables
    hp = QUAD.z - FLOOR_Z
    # round 5 (user review 2 / 06, the pedestal flicker): the olive box top was exactly the black top plate's top (and its bottom the
    # plinth's): same-facing coplanar faces = z-fight. Now the box stops 5 mm under the plate and starts 5 mm inside the plinth; the
    # corner posts stop 4 mm under the plate top
    box(mb, (0, QUAD.y, FLOOR_Z + 0.03), (0.34, 0.44, 0.06), 'ck_black')
    box(mb, (0, QUAD.y, (FLOOR_Z + 0.005 + QUAD.z - 0.025) / 2), (0.27, 0.37, hp - 0.03), 'ck_od')
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(mb, (sx * 0.142, QUAD.y + sy * 0.192, (FLOOR_Z + 0.004 + QUAD.z - 0.004) / 2), (0.025, 0.025, hp - 0.008), 'ck_black')
        for zz in (FLOOR_Z + 0.20, FLOOR_Z + 0.36):
            box(mb, (sx * 0.142, QUAD.y, zz), (0.022, 0.37, 0.02), 'ck_black')
    box(mb, (0, QUAD.y, QUAD.z - 0.01), (0.30, 0.40, 0.02), 'ck_black')
    for k in range(4):
        x = THROTTLE_X[k]
        cylinder(mb, V((x, QUAD.y + 0.19, QUAD.z - 0.02)), V((x * 1.4, QUAD.y + 0.30, FLOOR_Z + 0.01)), 0.008, N=6, mat='ck_bezel')
    # standby compass on the coaming centre: black housing + card window toward the pilots, on a short bracket
    cpos = V((0.0, panel_y(0) - 0.01, panel_ztop(0) + 0.075))
    box(mb, (0, cpos.y + 0.02, panel_ztop(0) + 0.035), (0.03, 0.03, 0.05), 'ck_black')
    uv_prism(mb, cpos + V((0, 0.05, 0)), cpos - V((0, 0.02, 0)), 0.034, 14, 'black')
    out.append(Part('cockpit_interior', 'fus_cockpit', mesh=mb, info={'kind': 'cockpit'}))
    # sub-panel outlines + screw heads + red buttons + placards: one small detail object on the panel
    d = MeshBuf()
    screws = 0
    for x0, x1, z0, z1 in BOXES:
        k = 24
        pts = ([(x0 + (x1 - x0) * i / k, z0) for i in range(k)] + [(x1, z0 + (z1 - z0) * i / 8) for i in range(8)] +
               [(x1 - (x1 - x0) * i / k, z1) for i in range(k)] + [(x0, z1 - (z1 - z0) * i / 8) for i in range(8)])
        P = [panel_point(x, z, 0.004) for x, z in pts]
        for k_, (a, b) in enumerate(zip(P, P[1:] + P[:1])):
            nrm = panel_normal((a.x + b.x) / 2)
            o_ = nrm * (0.0012 * (k_ % 2))       # round 5: alternate segments 1.2 mm apart (their joints overlapped: z-fight)
            NS.sec_tube(d, a + o_, b + o_, 0.010, 0.008, nrm, mat='ck_bezel')
        for x, z in pts[::4]:
            stud(d, panel_point(x, z, 0.008), panel_normal(x), 'ck_bezel', r=0.004, h=0.003)
            screws += 1
    for i, x in enumerate(BUTTONS):         # guarded red buttons: black guard plate + red cap
        c = panel_point(x, BUTTON_Z, 0.004); nrm = panel_normal(x)
        uv_prism(d, c, c + nrm * 0.010, 0.019, 10, 'black')
        uv_prism(d, c + nrm * 0.010, c + nrm * 0.024, 0.011, 12, 'red')
    for name, x, z, w, h, face in PLATES:
        nrm = panel_normal(x); rt = V((1, -2 * PANEL_K * x, 0)).normalized()
        c = panel_point(x, z, 0.006)
        q = [c - rt * w / 2 - V((0, 0, h / 2)), c + rt * w / 2 - V((0, 0, h / 2)), c + rt * w / 2 + V((0, 0, h / 2)), c - rt * w / 2 + V((0, 0, h / 2))]
        uv = [atlas_uv(face, 0, 0), atlas_uv(face, 1, 0), atlas_uv(face, 1, 1), atlas_uv(face, 0, 1)]
        if (q[1] - q[0]).cross(q[3] - q[0]).dot(nrm) < 0:
            q = [q[1], q[0], q[3], q[2]]; uv = [uv[1], uv[0], uv[3], uv[2]]
        d.poly(q, 'gauges', uv)
        for p in q:
            stud(d, p + (c - p) * 0.08 + nrm * 0.001, nrm, 'ck_bezel', r=0.004, h=0.003)
    out.append(Part('cockpit_panel_detail', 'cockpit_interior', mesh=d, info={'kind': 'cockpit_detail', 'screws': screws}))
    return out


def build_gauges():
    """gauge faces (atlas quads, 32-gon) + bezels; needles / cards as separate objects with the B-25H needle frame."""
    out = []
    faces = MeshBuf()
    bez = MeshBuf()
    movers = []
    for g in GAUGES:
        name, gx, z, face, kind, R = g
        c = gauge_centre(g)
        nrm = panel_normal(gx)
        up = V((0, 0, 1)) - nrm * nrm.z; up.normalize()
        right = up.cross(nrm).normalized()
        ring = [c + (right * math.sin(2 * math.pi * k / 32) + up * math.cos(2 * math.pi * k / 32)) * R for k in range(32)]
        f = face or 'att_ground'
        for k in range(32):
            a, b = ring[k], ring[(k + 1) % 32]
            uvs = [atlas_uv(f, 0.5, 0.5)]
            for p in (a, b):
                dd = p - c
                uvs.append(atlas_uv(f, 0.5 + 0.5 * dd.dot(right) / R, 0.5 + 0.5 * dd.dot(up) / R))
            ok = (a - c).cross(b - c).dot(nrm) > 0
            faces.face([faces.v(c), faces.v(a), faces.v(b)] if ok else [faces.v(c), faces.v(b), faces.v(a)], 'gauges', uvs if ok else [uvs[0], uvs[2], uvs[1]])
        outer = [c + (p - c) * 1.18 + nrm * 0.006 for p in ring]; inner = [c + (p - c) * 1.0 + nrm * 0.006 for p in ring]
        annulus(bez, outer, inner, 'ck_bezel', nrm)
        loft(bez, [[p - nrm * 0.006 for p in outer], outer], 'ck_bezel')
        q = axis_frame(nrm, up)          # local +X = the dial normal (toward the cockpit): needles turn in the dial plane
        if kind in ('needle', 'altimeter'):
            movers.append((f'gauge_{name}_needle', c + nrm * 0.008, q, 0.82, 0.0045, R))
        if kind == 'altimeter':
            movers.append((f'gauge_{name}_needle_short', c + nrm * 0.010, q, 0.55, 0.008, R))
        if kind == 'clock':                       # minute (long), hour (short), sweep second on the lower sub-dial
            movers.append((f'gauge_{name}_needle', c + nrm * 0.008, q, 0.82, 0.0035, R))
            movers.append((f'gauge_{name}_needle_short', c + nrm * 0.010, q, 0.55, 0.006, R))
            su, sv, sl = CLOCK_SEC
            movers.append((f'gauge_{name}_sec_needle', c + (right * (su - 0.5) + up * (sv - 0.5)) * 2 * R + nrm * 0.008, q, sl, 0.0018, R))
        if kind == 'egu':                         # fuel press / oil press / oil temp sub-dials of the engine gauge unit
            e = name.split('_')[1]
            for sub, su, sv, sl in EGU_SUB:
                movers.append((f'gauge_egu_{e}_{sub}_needle', c + (right * (su - 0.5) + up * (sv - 0.5)) * 2 * R + nrm * 0.008, q, sl, 0.0022, R))
        if kind == 'dual':
            e = name.split('_')[1]
            movers.append((f'gauge_{name.split("_")[0]}_{e[0]}_needle', c + nrm * 0.008, q, 0.80, 0.0045, R))
            movers.append((f'gauge_{name.split("_")[0]}_{e[1]}_needle', c + nrm * 0.010, q, 0.62, 0.0045, R))
        if kind == 'card':
            movers.append((f'gauge_{name}_card', c + nrm * 0.003, q, 'card_dg', 0, R))
        if kind == 'attitude':
            movers.append((f'gauge_{name}_card', c + nrm * 0.003, q, 'card_att', 0, R))
    out.append(Part('cockpit_gauge_faces', 'cockpit_interior', mesh=faces, info={'kind': 'gauges'}))
    out.append(Part('cockpit_bezels', 'cockpit_interior', mesh=bez, info={'kind': 'bezels'}))
    for name, pos, q, length, width, R in movers:
        mb = MeshBuf()
        M = q.to_matrix()
        xax, yax, zax = M.col[0], M.col[1], M.col[2]          # x toward the pilot, z = 12 o'clock
        if length == 'card_dg':
            for k in range(32):
                a0, a1 = 2 * math.pi * k / 32, 2 * math.pi * (k + 1) / 32
                pa = pos + (yax * math.sin(a0) + zax * math.cos(a0)) * R * 0.92
                pb = pos + (yax * math.sin(a1) + zax * math.cos(a1)) * R * 0.92
                # 1.8.0 (user: the compass card is mirrored): +yax is the pilot's RIGHT (x toward the pilot, z up, y = z x x), so the card's
                # u must grow with +yax like the dial faces (u = 0.5 + dot(right)); 1.6-1.7 had 0.5 - sin -> E and W swapped, digits reversed
                uv = [atlas_uv('dial_dg', 0.5, 0.5), atlas_uv('dial_dg', 0.5 + 0.46 * math.sin(a0), 0.5 + 0.46 * math.cos(a0)), atlas_uv('dial_dg', 0.5 + 0.46 * math.sin(a1), 0.5 + 0.46 * math.cos(a1))]
                tri = [pos, pa, pb]
                if (pa - pos).cross(pb - pos).dot(xax) < 0:
                    tri = [pos, pb, pa]; uv = [uv[0], uv[2], uv[1]]
                mb.poly(tri, 'gauges', uv)
        elif length == 'card_att':
            for face, sgn in (('att_sky', 1), ('att_ground', -1)):
                ring = [pos + (yax * math.cos(math.pi * k / 16) + zax * sgn * math.sin(math.pi * k / 16)) * R * 0.94 for k in range(17)]
                for a_, b_ in zip(ring, ring[1:]):
                    tri = [pos, a_, b_]
                    uv = [atlas_uv(face, 0.5, 0.5)] + [atlas_uv(face, 0.5 + 0.5 * (p - pos).dot(yax) / R, (0.0 if sgn > 0 else 1.0) + sgn * abs((p - pos).dot(zax)) / R * 0.9) for p in (a_, b_)]
                    if (a_ - pos).cross(b_ - pos).dot(xax) < 0:
                        tri = [pos, b_, a_]; uv = [uv[0], uv[2], uv[1]]
                    mb.poly(tri, 'gauges', uv)
        else:
            tip = pos + zax * R * length; tail = pos - zax * R * 0.18
            w = yax * width
            oriented_quad(mb, [tail - w, tail + w, tip + w * 0.4, tip - w * 0.4], 'needle', xax)
            hub = 0.006 if length > 0.5 else 0.0035          # 1.8.4: small hub on the sub-dial needles
            cylinder(mb, pos - xax * 0.001, pos + xax * 0.004, hub, N=10, mat='ck_bezel')
        out.append(Part(name, 'cockpit_interior', pivot=pos, mesh=mb, frame=q, info={'kind': 'gauge_mover', 'axis': 'local +X toward the pilot'}))
    return out


def throttle_mesh(k, piv):
    """throttle arm k (0..3) + its T-bar handle, in world space at rest (straight up; b17g_props leans it to idle).
    T-1 / T-4 handles high, T-2 / T-3 low and 15 mm aft of the arms (they pass behind the outer arms without touching)."""
    mb = MeshBuf()
    x = THROTTLE_X[k]
    high = k in (0, 3)
    h = 0.265 if high else 0.225       # 1.6.1: T-bars 8-12 cm above the slotted body top (in game 1.6.0 they floated beside it)
    yoff = 0.0 if high else -0.016
    top = piv + V((0, 0, h))
    NS.sec_tube(mb, piv, top, 0.010, 0.006, V((0, 1, 0)), mat='ck_bezel')
    end = top + V((0, yoff, 0))
    if yoff:
        NS.sec_tube(mb, top - V((0, 0, 0.006)), end - V((0, 0, 0.006)) + V((0, -0.005, 0)), 0.010, 0.012, V((0, 0, 1)), mat='ck_bezel')
    xa, xb = (-0.118, -0.004) if k < 2 else (0.004, 0.118)     # within the body width (0.30)
    cylinder(mb, V((xa, end.y, end.z)), V((xb, end.y, end.z)), 0.0085, N=10, mat='ck_black')
    R_ = Matrix.Rotation(math.radians(THROTTLE_REST), 3, 'X')       # idle lean: +X rotation = top aft (pose -40 = full forward)
    mb.verts = [piv + R_ @ (V(p) - piv) for p in mb.verts]
    return mb


def anchors():
    """empties where the fal props go (b17g_props.place_cockpit) + the control / lever pivots + crew eyes."""
    out = []
    for s, sx in (('L', -1), ('R', 1)):
        out.append(Part(f'cockpit_seat_{s}', 'cockpit_interior', pivot=V((sx * 0.45, 3.16, FLOOR_Z)), info={'kind': 'fal_anchor', 'prop': 'ck_seat', 'h': 1.05}))
        piv = V((sx * 0.45, YOKE_HUB_Y + 0.05, FLOOR_Z + 0.03))      # column straight under the hub, top into the hub boss
        out.append(Part(f'cockpit_column_{s}', 'cockpit_interior', pivot=piv, frame=axis_frame(V((1, 0, 0))),
                        info={'kind': 'ck_control', 'drive': {'field': 'pitchRange', 'value': 12.0, 'servoSpeed': 90}, 'prop': 'ck_column', 'h': YOKE_HUB_Z - FLOOR_Z - 0.03}))
        hub = V((sx * 0.45, YOKE_HUB_Y, YOKE_HUB_Z))
        toward = (V((sx * 0.45, 3.32, YOKE_HUB_Z + 0.12)) - hub).normalized()
        out.append(Part(f'cockpit_yoke_{s}', f'cockpit_column_{s}', pivot=hub, frame=axis_frame(toward),
                        info={'kind': 'ck_control', 'drive': {'field': 'rollRange', 'value': 45.0, 'servoSpeed': 120}, 'prop': 'ck_yoke2', 'w': 0.40}))
    out.append(Part('cockpit_quadrant', 'cockpit_interior', pivot=QUAD, info={'kind': 'fal_anchor', 'prop': 'ck_quadrant2', 'w': QUAD_W}))
    out.append(Part('cockpit_c1', 'cockpit_interior', pivot=V((0, QUAD.y - 0.25, 0.66)), info={'kind': 'fal_anchor', 'prop': 'ck_c1', 'w': 0.24}))
    for k in range(4):     # throttles: pivot inside the quadrant, rotate about +X (Blender -X = grip forward = full)
        piv = V((THROTTLE_X[k], THROTTLE_PIVOT_YZ[0], THROTTLE_PIVOT_YZ[1]))
        out.append(Part(f'cockpit_throttle_{k + 1}', 'cockpit_quadrant', pivot=piv, frame=axis_frame(V((1, 0, 0))), mesh=throttle_mesh(k, piv),
                        info={'kind': 'lever', 'drive': {'component': 'Cockpit.throttles', 'range': 40.0}, 'rest_deg': THROTTLE_REST}))
    out.append(Part('cockpit_eye', 'cockpit_interior', pivot=EYE_L, info={'kind': 'eye', 'role': 'pilot'}))
    crew = [('pilot', 'fus_cockpit', EYE_L), ('copilot', 'fus_cockpit', EYE_R), ('bombardier', 'fus_nose', V((0, 6.38, 0.83))),
            ('navigator', 'fus_nose', V((-0.52, 5.40, 0.88))), ('engineer', 'B17G', V((0, 2.05, 1.80))), ('radio', 'fus_radio', V((0.35, -2.2, 1.00))),
            ('ball', 'fus_waist', V((0, -3.95, -0.70))), ('waist_R', 'fus_waist', V((0.50, -5.17, 1.05))), ('waist_L', 'fus_waist', V((-0.50, -6.70, 1.05))),
            ('tail', 'tail_gun', V((0, -14.25, 1.25)) if S.TAIL188 else V((0, -14.15, 1.15)))]     # 1.8.8: eye mid-height in the glazed cab
    for i, (role, part, e) in enumerate(crew):
        fwd = V((0, -1, 0)) if role == 'tail' else V((1, 0, 0)) if role == 'waist_R' else V((-1, 0, 0)) if role == 'waist_L' else V((0, 1, 0))
        out.append(Part(f'crew_eye_{role}', part, pivot=e, frame=axis_frame(fwd.cross(V((0, 0, 1)))),
                        info={'kind': 'crew_eye', 'role': role, 'part': part, 'index': i, 'forward': list(fwd)}))
    return out


def eye_contract():
    return dict(pilot=list(EYE_L), copilot=list(EYE_R))
