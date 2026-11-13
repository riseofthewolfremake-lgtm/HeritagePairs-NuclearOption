"""GA-25X parts that differ from the B-25H. Everything else is built by the B-25H modules (blender/v2) with the
GA-25X spec applied (ga25x_spec.apply). Same conventions as the B-25H builders: Part meshes are MeshBuf in WORLD
coordinates (Blender: nose +Y, up +Z, right wing +X), materials by slot name, `paint` faces go to the livery atlas.

Visual pass 2026-10-31: canopy, nacelles, turboprop, props, laser turret, chin ball, package fairings, sensor panels,
tail cone and pylons moved to ga25x_visual.py (this file keeps the cannon, tail hook, bay and cockpit).
Objects (names used by unity/Editor/GA25XBuild.cs through the contract):
  engine_L/R (+ exhaust_L/R)      hybrid turboprop: slim cowl, chin intake, two low-IR exhaust coolers per engine
  prop_hub_L/R, prop_L/R_blade1-6 6-blade composite scimitar props + spinner
  cannon / muzzle_cannon          76 mm autoloading gun on the nose axis (fus_nose)
  chin_turret / targetcam_point   EO/IR + laser designator ball under the nose
  package_guns_L/R, muzzle_package_L1/R1   modern package fairings, one 20 mm each
  laser_turret_mount/_az/_el, muzzle_laser  dorsal 120 kW laser turret (Turret convention as the B-25H turrets)
  sensor panels + flare dispensers (in fus_rear), flare_L/R
  sensor tail cone (in fus_tail; replaces b25h_v3_arms.tail_cap), mws_tail, flare_tail_L/R
  tailhook (+ hp_tailhook)        own arrester hook (moved into the tail-hook mount prefab by the build)
  pylon_inner/outer_L/R + hp_*    2 pylons per wing in the B-25H rocket-rail area
  hp_bombbay, hp_bay_L/R          bay centre hardpoint + paired racks
  glass cockpit: cockpit_interior, cockpit_gauges (3 standby dials), mfd_center/left/right/wso, stick_L/R,
                 cockpit_rudder_pedals_L/R, cockpit_seat_L/R, quadrant_throttle_L/R, gunsight_pilot (HUD), crew_wso_eye
"""
import math
from mathutils import Vector, Quaternion
import b25h_spec as S
import ga25x_spec as G
from b25h_geom import (V, MeshBuf, loft, fan_cap, annulus, oriented_quad, cylinder, tube, box, circle_pts, arc_lengths,
                       ring_arc_uv, superellipse_ring, interp_table, frame_from_axes)

UP = V((0, 0, 1))


def _P():
    import b25h_parts as P
    return P


def _frame_x(xaxis, zhint=(0, 0, 1)):
    return frame_from_axes(V(xaxis), V(zhint))


def sphere(mb, c, r, mat, N=20, M=10, uvfunc=None):
    rings = []
    for i in range(1, M):
        phi = -math.pi / 2 + math.pi * i / M
        rings.append(circle_pts(V(c) + UP * (r * math.sin(phi)), UP, r * math.cos(phi), N, ref=V((1, 0, 0))))
    loft(mb, rings, mat)
    fan_cap(mb, rings[0], V(c) - UP * r, mat, -UP, smooth=True)
    fan_cap(mb, rings[-1], V(c) + UP * r, mat, UP, smooth=True)


# ============================================================================================ nose: 76 mm, chin turret
def build_cannon():
    P = _P()
    z = G.CANNON_Z
    tip = V((0, S.NOSE_TIP_Y + 0.30, z))
    cm = MeshBuf()
    tube(cm, V((0, G.CANNON_BREECH_Y + 0.30, z)), tip, 0.060, 0.038, N=18)            # barrel (fluted look: plain)
    cylinder(cm, V((0, S.NOSE_TIP_Y - 0.55, z)), V((0, S.NOSE_TIP_Y + 0.06, z)), 0.105, 0.085, N=24, mat='paint')  # nose shroud
    for k in range(3):                                                                  # muzzle brake ports
        yy = tip.y - 0.05 - 0.07 * k
        cylinder(cm, V((0, yy - 0.02, z)), V((0, yy + 0.02, z)), 0.072, N=18)
    # 0.3.2: breech 0.19 m wide (was 0.30): the stock crew figures' inner feet (COIN bone pose, |x| >= 0.12) stand beside it
    # in the deepened footwells; the centre cover strip over it is +-0.101 (ga25x_cockpit.CENTRE_FWD_HALF_X)
    box(cm, (0, G.CANNON_BREECH_Y, z), (0.19, 0.55, 0.30), 'metal_dark')                # breech + autoloader ring
    box(cm, (0, G.CANNON_BREECH_Y - 0.55, z - 0.03), (0.42, 0.55, 0.34), 'metal_dark')  # 96-round drum feed (0.3.3: top 1 cm under the cabin deck; at 0.10 it z-fought with the deck between the seats)
    cylinder(cm, V((0, G.CANNON_BREECH_Y + 0.28, z)), V((0, G.CANNON_BREECH_Y + 0.95, z)), 0.095, N=18)   # recoil sleeve
    can = P.Part('cannon', 'fus_nose', V((0, G.CANNON_BREECH_Y + 0.30, z)), cm,
                 info=dict(note='76 mm autoloading gun (stock VL-49 Tarantula weapon, fixed forward), 96 guided shells'))
    return [can, P.Part('muzzle_cannon', 'cannon', tip, info=dict(kind='muzzle'))]


def build_tailhook():
    """arrester hook, stowed flush along the bottom line. Object origin = hinge; mesh points aft (-Y Blender)."""
    P = _P()
    hp = V(G.TAILHOOK_PIVOT)
    L = 2.30
    zb0 = P.fus_params(hp.y)[1]
    pv = V((0, hp.y, zb0 - 0.05))
    end_y = hp.y - L * math.cos(math.radians(8.5))
    endp = V((0, end_y, pv.z + L * math.sin(math.radians(8.5))))
    mb = MeshBuf()
    cylinder(mb, pv - V((0.07, 0, 0)), pv + V((0.07, 0, 0)), 0.035, N=12, mat='metal_dark')           # hinge boss
    cylinder(mb, pv, endp, 0.032, 0.026, N=12, mat='paint')                                          # shank
    d = (endp - pv).normalized()
    box(mb, endp + d * 0.04 - UP * 0.03, (0.09, 0.14, 0.07), 'metal_dark',
        rot=Quaternion(V((1, 0, 0)), math.atan2(d.z, -d.y)))                                         # hook head
    hook = P.Part('tailhook', 'fus_tail', pv, mb,
                  info=dict(kind='tailhook', length=L, stowed_up_deg=8.5,
                            note='hinge at origin, Unity local X = hinge axis; at angle 0 the hook points straight aft (-Z Unity); '
                                 'stowed = +8.5 deg (tip up, flush), deployed down = negative angles'))
    hp_ = P.Part('hp_tailhook', 'fus_tail', pv, None, info=dict(kind='hardpoint', note='tail-hook mount (WeaponMount.tailHook)'))
    end = P.Part('tailhook_end', 'tailhook', pv + V((0, -L, 0)), None, info=dict(kind='hook_end', note='at angle 0'))
    return [hook, hp_, end]


def add_bay_carrier(ctr_mesh):
    hx, hy, hz = G.HP_BOMBBAY
    bz = hz + 0.105
    for x in (0.0, -G.BAY_RACK_X, G.BAY_RACK_X):
        box(ctr_mesh, (x, hy, bz), (0.06, 2.70, 0.05), 'structure')
    for y in (hy + 1.0, hy, hy - 1.0):
        box(ctr_mesh, (0, y, bz), (2 * (S.BAY_HALF_X - 0.06), 0.05, 0.04), 'structure')


def bay_hardpoints():
    P = _P()
    hx, hy, hz = G.HP_BOMBBAY
    return [P.Part('hp_bombbay', 'fus_center', (0, hy, hz), info=dict(kind='hardpoint', note='bay centre (single mounts)')),
            P.Part('hp_bay_L', 'fus_center', (-G.BAY_RACK_X, hy, hz), info=dict(kind='hardpoint', note='paired rack, left')),
            P.Part('hp_bay_R', 'fus_center', (G.BAY_RACK_X, hy, hz), info=dict(kind='hardpoint', note='paired rack, right'))]


# ============================================================================================ glass cockpit
def build_cockpit():
    """2-seat glass cockpit in the armoured capsule: 4 MFDs, 3 standby dials, HUD, side sticks, pedals, quadrant."""
    import b25h_v3_cockpit as C3
    from b25h_v3 import FLOOR_Z, CK
    P = _P()
    parts = []
    m = MeshBuf()
    y0, y1 = 2.66, S.PANEL_Y
    hw = 0.66
    box(m, (0, (y0 + y1) / 2, FLOOR_Z - 0.015), (2 * hw, y1 - y0, 0.03), CK)
    for s in (-1, 1):
        box(m, (s * (hw + 0.005), (y0 + y1) / 2, 0.47), (0.01, y1 - y0, 0.74), 'metal_dark')     # capsule armour side
        box(m, (s * (hw - 0.10), 3.40, 0.46), (0.18, 0.95, 0.10), CK)                           # side console
        for k in range(5):
            box(m, (s * (hw - 0.10), 3.05 + 0.17 * k, 0.515), (0.13, 0.12, 0.004), 'screen')     # console keypads (dark)
    from b25h_interior import section_panel
    for rect in ((-1.0, -0.24, FLOOR_Z, 2.0), (0.24, 1.0, FLOOR_Z, 2.0), (-0.24, 0.24, 1.05, 2.0)):
        section_panel(m, y0, rect, 'metal_dark')                                                 # aft capsule bulkhead
    q = Quaternion(V((1, 0, 0)), -C3.RK)
    box(m, (0, y1, 0.70), (1.20, 0.05, 0.46), CK, rot=q)                                       # panel
    box(m, (0, y1 + 0.06, 0.955), (1.00, 0.24, 0.03), CK)                                      # glare shield
    box(m, (0, y1 - 0.04, (FLOOR_Z + 0.36) / 2), (1.10, 0.03, 0.36 - FLOOR_Z), CK)
    import ga25x_visual as VX
    quad_levers = VX.modern_quadrant_body(m)   # modern console; lever pivots/info from the B-25H quadrant
    rt, up = V((1, 0, 0)), C3.PU
    # MFDs: (name, x, z, w, h, note)
    MFDS = [('mfd_left', -0.47, 0.700, 0.20, 0.25, 'pilot left MFD (tac screen)'),
            ('mfd_center', -0.20, 0.700, 0.24, 0.25, 'pilot main MFD (tac screen = Cockpit.tacScreenRender)'),
            ('mfd_right', 0.20, 0.700, 0.24, 0.25, 'weapons officer main MFD (target camera)'),
            ('mfd_wso', 0.47, 0.700, 0.20, 0.25, 'weapons officer right MFD (tac screen)')]
    mfd_parts = []
    for nmn, x, z, w, h, note in MFDS:
        c = C3.panel_pt(x, z)
        for (a, b, ww, hh) in ((0, h / 2 + 0.012, w + 0.04, 0.024), (0, -h / 2 - 0.012, w + 0.04, 0.024),
                               (w / 2 + 0.012, 0, 0.024, h), (-w / 2 - 0.012, 0, 0.024, h)):
            box(m, c + rt * a + up * b + C3.PN * 0.005, (ww, 0.014, hh), 'metal_dark', rot=q)
        for k in range(5):                                                                     # bezel keys
            box(m, c + rt * (-w / 2 + w * (k + 0.5) / 5) - up * (h / 2 + 0.012) + C3.PN * 0.012, (0.02, 0.006, 0.012), 'rubber', rot=q)
        sm = MeshBuf()
        cs = c + C3.PN * 0.008
        pts = [cs - rt * (w / 2) - up * (h / 2), cs + rt * (w / 2) - up * (h / 2), cs + rt * (w / 2) + up * (h / 2), cs - rt * (w / 2) + up * (h / 2)]
        oriented_quad(sm, pts, 'screen', C3.PN, [(0, 0), (1, 0), (1, 1), (0, 1)])
        mp = P.Part(nmn, 'fus_cockpit', cs, sm, info=dict(kind='mfd', size_m=(w, h), normal_unity=(0.0, round(C3.PN.z, 4), round(C3.PN.y, 4)),
                                                         uv='0-1; u -> crew right, v -> panel up', note=note))
        mp.own_uv = True
        mfd_parts.append(mp)
    # standby instruments (airspeed, attitude, altimeter faces from the shared gauge atlas), centre column
    gf = MeshBuf()
    for (x, z, cell) in ((-0.06, 0.885, 0), (0.0, 0.885, 1), (0.06, 0.885, 2)):
        c = C3.panel_pt(x, z)
        r = 0.022
        annulus(m, circle_pts(c + C3.PN * 0.01, C3.PN, r + 0.007, 20, ref=C3.PU), circle_pts(c + C3.PN * 0.01, C3.PN, r, 20, ref=C3.PU), CK, C3.PN)
        C3.disc_uv(gf, c, rt, up, r, cell, C3.PN, 0.004)
    g = P.Part('cockpit_gauges', 'fus_cockpit', (0, y1, 0.70), gf, info=dict(note='standby dials, own UVs in the gauge atlas'))
    g.own_uv = True
    # HUD (pilot): projector body + tilted combiner glass
    gx = S.COCKPIT_EYE[0]
    gs = MeshBuf()
    box(gs, (gx, 4.28, 0.99), (0.16, 0.14, 0.07), 'metal_dark')
    cmb = MeshBuf()
    cq = Quaternion(V((1, 0, 0)), math.radians(-30))
    cc = V((gx, 4.20, 1.09))
    cpts = [cc + cq @ V(p) for p in ((-0.075, 0, -0.06), (0.075, 0, -0.06), (0.075, 0, 0.06), (-0.075, 0, 0.06))]
    oriented_quad(cmb, cpts, 'glass', V((0, -1, 0.3)))
    oriented_quad(cmb, cpts, 'glass', V((0, 1, -0.3)))
    stations = []
    for side, L, key in ((-1, 'L', 'pilot'), (1, 'R', 'wso')):
        sx, sy = S.CREW[key]['seat']
        eye = V(S.CREW[key]['eye'])
        cush = eye.z - 0.65
        stations.append(P.Part(f'cockpit_seat_{L}', 'fus_cockpit', (sx, sy, cush), C3.seat_mesh(sx, sy, cush, FLOOR_Z, armour=True),
                               info=dict(kind='crew_seat', crew=key)))
        if key == 'wso':
            stations.append(P.Part('crew_wso_eye', 'fus_cockpit', eye, None, info=dict(kind='crew_eye', crew='wso', look='+Z (Unity) forward')))
        # side stick on the outboard console: one transform, Cockpit.Joystick (X = pitch * range, Z = -roll * range)
        piv = V((side * (hw - 0.10), 3.62, 0.515))
        stm = MeshBuf()
        cylinder(stm, piv - V((0, 0, 0.01)), piv + V((0, 0.0, 0.03)), 0.03, N=14, mat='rubber')        # boot
        top = piv + V((0, 0.02, 0.14))
        cylinder(stm, piv, top, 0.012, N=10, mat='metal_dark')
        box(stm, top + V((0, 0.0, 0.05)), (0.040, 0.05, 0.11), 'rubber', rot=Quaternion(V((1, 0, 0)), math.radians(-12)))  # grip
        box(stm, top + V((0, 0.022, 0.10)), (0.03, 0.02, 0.02), 'metal_dark')                         # hat switch
        stations.append(P.Part(f'stick_{L}', 'fus_cockpit', piv, stm, Quaternion(),
                               info=dict(kind='side_stick', drive='Cockpit.Joystick (localEulerAngles = (pitch*range, 0, -roll*range))',
                                         range_deg=10, sign='as the stock CI-22 stick: pitch > 0 (push) tilts the top forward')))
        # rudder pedals: yaw bar, local X = up (ControlSurface.yawRange)
        pp = V((sx, 4.06, FLOOR_Z))
        pm = MeshBuf()
        cylinder(pm, pp, pp + V((0, 0, 0.07)), 0.022, N=12, mat='metal_dark')
        bar_z = FLOOR_Z + 0.05
        cylinder(pm, V((sx - 0.16, 4.06, bar_z)), V((sx + 0.16, 4.06, bar_z)), 0.015, N=8, mat='metal_dark')
        for k in (-1, 1):
            x = sx + k * 0.15
            cylinder(pm, V((x, 4.06, bar_z)), V((x, 4.00, bar_z + 0.15)), 0.012, N=8, mat='metal_dark')
            box(pm, (x, 3.995, bar_z + 0.135), (0.09, 0.025, 0.18), CK, rot=Quaternion(V((1, 0, 0)), math.radians(30)))
        stations.append(P.Part(f'cockpit_rudder_pedals_{L}', 'fus_cockpit', pp, pm, _frame_x((0, 0, 1), (0, 1, 0)),
                               info=dict(kind='rudder_pedals', axis_local='+X (Unity) = up', range_deg=15, drive='ControlSurface.yawRange')))
    parts.append(P.Part('cockpit_interior', 'fus_cockpit', (0, 3.45, FLOOR_Z), m))
    parts.append(g)
    parts += mfd_parts + stations + quad_levers
    parts.append(P.Part('gunsight_pilot', 'fus_cockpit', (gx, 4.28, 0.99), gs, info=dict(note='HUD projector')))
    parts.append(P.Part('gunsight_combiner', 'gunsight_pilot', cc, cmb, info=dict(kind='combiner', note='HUD combiner glass')))
    return VX.modern_cockpit(parts)
