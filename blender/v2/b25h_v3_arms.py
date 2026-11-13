"""B-25H v3 armament and stores: Bendix top turret, H tail gun position, waist ball mounts, our own M2 bodies at
the stock door-gun mesh origin, T13E1 75 mm, wing pylons (hardpoints at the pylon bottom face, as the stock
CAS1 pylons), bomb-bay carrier, crew seats/eyes outside the cockpit, tail cap with gun opening, prop blur meshes.

Turret convention (Turret.cs): az.localEulerAngles = (0, traverse, 0), el.localEulerAngles = (elev, 0, 0) are
ABSOLUTE, so every az rests with identity rotation under its `*_mount` (which carries the orientation: local +Z
Unity = gun forward, +Y = up) and every el rests with identity rotation under its az. Elevation limits are
given as Turret.minElevation (down, negative) / maxElevation (up); Turret clamps localEuler.x to
[-maxElevation, -minElevation], i.e. Unity +X rotation = muzzle DOWN.
"""
import math
from mathutils import Vector, Quaternion
import b25h_spec as S
from b25h_geom import (V, MeshBuf, loft, fan_cap, annulus, oriented_quad, cylinder, tube, box, circle_pts, planar_uv,
                       arc_lengths, ring_arc_uv, lerp)
import b25h_parts as P
from b25h_parts import Part, fus_params, fus_ring
from b25h_v3 import frame_x, grid_faces, sweep_rect, m2_gun, FLOOR_Z

UP = V((0, 0, 1))


def sphere(mb, c, r, mat, N=16, M=8):
    rings = []
    for i in range(1, M):
        phi = -math.pi / 2 + math.pi * i / M
        rings.append(circle_pts(V(c) + UP * (r * math.sin(phi)), UP, r * math.cos(phi), N, ref=V((1, 0, 0))))
    loft(mb, rings, mat)
    fan_cap(mb, rings[0], V(c) - UP * r, mat, -UP, smooth=True)
    fan_cap(mb, rings[-1], V(c) + UP * r, mat, UP, smooth=True)


def gun_part(name, parent, origin, fwd, up, muzzle_name, note):
    """our M2 body as its own object at the stock door-gun mesh origin (swap-in point), muzzle child."""
    mb = MeshBuf()
    mz = m2_gun(mb, origin, fwd, up)
    # local axes: X = right of the barrel, Y = barrel forward, Z = up  (Unity: X right, Y up, Z forward)
    xr = V(fwd).cross(V(up)).normalized()
    from b25h_geom import frame_from_axes
    fr = frame_from_axes(xr, V(up))
    g = Part(name, parent, origin, mb, fr, info=dict(kind='gun_body', swap='stock 50cal_doorGun_barrel mesh fits this '
                                                       'transform 1:1 (origin, +Z fwd, +Y up)', note=note))
    m = Part(muzzle_name, name, mz, None, fr, info=dict(kind='muzzle'))
    return [g, m]


# ============================================================================================ top turret
ANM2_DORSAL = True       # 1.8.13 r2 (offline L): dorsal slots / cross beam / seat hangers cleared for the AN/M2 receivers
def build_top_turret():
    c = V(S.TURRET_C)                         # (0, 1.82, 1.34)
    ring_top = S.TURRET_RING_Z + 0.05         # ring structure top in fus_forward (1.23)
    piv = V((0, c.y, ring_top))
    base_z = c.z + 0.08                       # drum top / dome base (1.42)
    mount = Part('turret_dorsal_mount', 'fus_forward', piv, None, info=dict(kind='turret_mount', note='identity (fwd = +Z)'))
    az = MeshBuf()
    R = 0.465
    N = 64
    zs = [ring_top - 0.004, ring_top + 0.06, base_z]
    outer = [circle_pts(V((0, c.y, z)), UP, R, N, ref=V((0, 1, 0))) for z in zs]
    sp = [z for z in zs]
    loft(az, outer, 'paint', uvfunc=ring_arc_uv(outer, sp))
    loft(az, [[p + (V((0, c.y, p.z)) - p).normalized() * 0.008 for p in r] for r in outer], 'interior', outward=False)
    annulus(az, outer[-1], circle_pts(V((0, c.y, base_z)), UP, R - 0.045, N, ref=V((0, 1, 0))), 'metal_dark', UP)
    annulus(az, outer[0], circle_pts(V((0, c.y, zs[0])), UP, R - 0.07, N, ref=V((0, 1, 0))), 'structure', -UP)
    # dome: sphere grid (64 x 13), outer + inner surfaces, gun slots in the front
    dc = V((0, c.y, base_z))
    rd = 0.43
    phis = [math.radians(7.5 * k) for k in range(12)] + [math.radians(88.5)]
    thetas = [2 * math.pi * k / N for k in range(N + 1)]

    def dp(phi, th, r):
        return dc + V((r * math.cos(phi) * math.sin(th), r * math.cos(phi) * math.cos(th), r * math.sin(phi)))

    # 1.8.13 r3: exact slot edges (one ring vertex snapped onto each edge line x = const, so the cut is a clean band, no staircase) and a
    # thin rim along them; slot 62 mm clear inside 10 mm rims (AN/M2 jacket 52 mm), from the base up to 75 deg (85 deg elevation path)
    W_, PH_TOP = 0.040, math.radians(75.5)
    bands = [(gx - W_, gx + W_) for gx in (-0.13, 0.13)]
    def ring_thetas(ph):
        th = list(thetas[:-1])
        rho = rd * math.cos(ph)
        if ANM2_DORSAL and ph < PH_TOP:
            for x0, x1 in bands:
                for xe in (x0, x1):
                    if abs(xe) >= rho * 0.999:
                        continue
                    te = math.asin(xe / rho)                       # front half (cos > 0)
                    j = min(range(N), key=lambda k: abs(rho * math.sin(th[k]) - xe) if math.cos(th[k]) > 0 else 9.0)
                    th[j] = te % (2 * math.pi)
                # r4: where the band's outer edge has left the dome (near the crown) the cut ends at y = -0.03: snap a vertex there too,
                # so that boundary is exact as well (the stepped edge read as dark stairs)
                xo = x1 if x1 > 0 else x0
                if abs(xo) >= rho * 0.999 and ph > 0:
                    tb = math.acos(max(-1.0, -0.03 / rho))
                    tb = tb if xo > 0 else 2 * math.pi - tb
                    j = min(range(N), key=lambda k: abs(((th[k] - tb + math.pi) % (2 * math.pi)) - math.pi))
                    th[j] = tb
        return th + [th[0] + 2 * math.pi]
    TH = [ring_thetas(ph) for ph in phis]

    def keep(i, j):
        ph = (phis[i] + phis[i + 1]) / 2
        if ANM2_DORSAL:
            q = sum((dp(phis[ii], TH[ii][jj], rd) for ii in (i, i + 1) for jj in (j, j + 1)), V()) / 4
            if ph < PH_TOP and q.y - dc.y > -0.03 and any(x0 < q.x < x1 for x0, x1 in bands):
                return False
            return True
        th = (thetas[j] + thetas[j + 1]) / 2
        p = dp(ph, th, rd)
        if ph < math.radians(80) and p.y - dc.y > 0.02:
            if any(abs(p.x - gx) < 0.032 for gx in (-0.13, 0.13)):
                return False
        return True
    for r_, sgn in ((rd, 1), (rd - 0.006, -1)):
        g = [[az.v(dp(ph, th, r_)) for th in (TH[i] if ANM2_DORSAL else thetas)] for i, ph in enumerate(phis)]
        for row in g:
            row[-1] = row[0]
        grid_faces(az, g, 'glass', (lambda p, s=sgn: (p - dc) * s), keep)
        top = az.v(dc + UP * r_)
        last = g[-1]
        for j in range(N):
            tri = [top, last[j], last[j + 1]]
            P0 = [az.verts[t] for t in tri]
            if (P0[1] - P0[0]).cross(P0[2] - P0[0]).dot((P0[0] - dc) * sgn) < 0:
                tri = [tri[0], tri[2], tri[1]]
            az.face(tri, 'glass', None, True)
    if ANM2_DORSAL:        # rims round each slot: inner edge, outer edge then the crown boundary (r4: closed round the notch), top arc, bottom
        rim = lambda pts: sweep_rect(az, pts, [q - dc for q in pts], 0.010, 0.006, 0.002, 'metal_dark', 'metal_dark', 'metal_dark') if len(pts) >= 2 else None
        for x0, x1 in bands:
            xi, xo = (x0, x1) if x1 > 0 else (x1, x0)
            inner = [dp(ph, math.asin(xi / (rd * math.cos(ph))), rd) for ph in phis if ph < PH_TOP and abs(xi) < rd * math.cos(ph) * 0.999]
            outer, crown = [], []
            for ph in phis:
                if ph >= PH_TOP:
                    break
                rho = rd * math.cos(ph)
                if abs(xo) < rho * 0.999:
                    outer.append(dp(ph, math.asin(xo / rho), rd))
                elif ph > 0:
                    tb = math.acos(max(-1.0, -0.03 / rho))
                    crown.append(dp(ph, tb if xo > 0 else 2 * math.pi - tb, rd))
            rim(inner); rim(outer); rim(crown)      # r4b: no chord from the outer edge to the crown boundary (it crossed the jackets' 85 deg path)
            rim([inner[0], outer[0]])
            # (r4: no rim across the slot's top - the jackets pass there at 85 deg)
    # dome frames: base ring + meridians at the sides and rear (metal)
    for th0 in (math.pi / 2, math.pi, 3 * math.pi / 2):
        pts = [dp(math.radians(a), th0, rd) for a in range(0, 65 if ANM2_DORSAL else 89, 4)]     # r2: side meridians stop below the guns' 85 deg path
        sweep_rect(az, pts, [p - dc for p in pts], 0.022, 0.010, 0.006, 'metal_dark', 'metal_dark', 'metal_dark')
    # cradle supports: cross beam on the ring, two side plates up to the trunnion
    if ANM2_DORSAL:       # 1.8.13 r2: the cross beam is two stubs outboard of the side plates: the receivers swing down between them
        for k in (-1, 1):
            box(az, (k * (0.215 + R) / 2, c.y, ring_top + 0.02), (R - 0.225, 0.08, 0.04), 'structure')
    else:
        box(az, (0, c.y, ring_top + 0.02), (2 * R - 0.02, 0.08, 0.04), 'structure')
    tz = c.z + (0.12 if ANM2_DORSAL else 0.22)                        # trunnion height (1.56; r2 1.46, 4 cm over the dome centre: the AN/M2 front clears the dome top at 85 deg, the rear the dome at 0)
    for k in (-1, 1):
        box(az, (k * 0.225, c.y, (ring_top + tz) / 2 + 0.03), (0.02, 0.16, tz - ring_top + 0.10), 'structure')
    # engineer / turret gunner sling seat hanging from the cross beam (rotates with the turret)
    sy = S.CREW['engineer']['seat'][1]
    seat_z = 0.62
    for k in (-1, 1):
        rx = 0.30 if ANM2_DORSAL else 0.18          # r2: seat hangers outboard of the receivers' swing
        cylinder(az, V((k * rx, c.y - 0.02, ring_top + 0.01)), V((k * 0.18, sy, seat_z + 0.02)), 0.014, N=8, mat='metal_dark')
    box(az, (0, sy, seat_z), (0.40, 0.30, 0.05), 'cockpit')
    box(az, (0, sy - 0.17, seat_z + 0.18), (0.36, 0.03, 0.32), 'cockpit')
    for k in (-1, 1):
        cylinder(az, V((k * 0.17, sy - 0.17, seat_z + 0.02)), V((k * 0.17, sy - 0.17, seat_z + 0.34)), 0.012, N=6, mat='metal_dark')
    azp = Part('turret_dorsal', 'turret_dorsal_mount', piv, az,
               info=dict(kind='turret_az', axis_local='+Y (Unity) = up', traverseRange=360, traverseRate=45,
                         note='Bendix top turret: drum, dome, frames, cradle supports, gunner seat; rests identity'))
    azp.uv_group = 'turret_top'
    # elevation cradle
    el = MeshBuf()
    tp = V((0, c.y, tz))
    cylinder(el, tp - V((0.235, 0, 0)), tp + V((0.235, 0, 0)), 0.025, N=12, mat='metal_dark')         # trunnion shaft
    if ANM2_DORSAL:       # r4: the AN/M2s carry themselves; a slim cradle bar and sight between them (the 0.34 m slab showed through the slots)
        box(el, (0, c.y - 0.04, tz - 0.03), (0.12, 0.16, 0.03), 'metal_dark')
        box(el, (0, c.y + 0.02, tz + 0.05), (0.04, 0.06, 0.06), 'metal_dark')
    else:
        box(el, (0, c.y + 0.02, tz - 0.01), (0.34, 0.22, 0.05), 'metal_dark')                             # cradle
        box(el, (0, c.y + 0.10, tz + 0.06), (0.05, 0.08, 0.08), 'metal_dark')                             # sight body
    elp = Part('turret_dorsal_guns', 'turret_dorsal', tp, el,
               info=dict(kind='turret_el', axis_local='+X (Unity) = right', minElevation=-5, maxElevation=85, elevationRate=40,
                         note='twin M2 cradle; rests identity under turret_dorsal'))
    out = [mount, azp, elp]
    for k, L in ((-1, 'L'), (1, 'R')):
        o = V((k * 0.13, c.y - 0.02, tz - 0.046))
        out += gun_part(f'gun_turret_{L}', 'turret_dorsal_guns', o, V((0, 1, 0)), UP, f'muzzle_turret_{L}', 'top turret M2')
    out.append(Part('crew_engineer_eye', 'turret_dorsal', S.CREW['engineer']['eye'], None,
                    info=dict(kind='crew_eye', crew='engineer', look='+Z (Unity), turns with the turret')))
    return out


# ============================================================================================ tail position
def build_tail_turret():
    tp = V(S.TAIL_GUN_PIVOT)                    # el trunnion
    azz = 0.22
    piv = V((tp.x, tp.y, azz))
    fr = frame_x((-1, 0, 0))                    # local Y (Blender) = aft -> Unity forward = aft
    mount = Part('tail_turret_mount', 'fus_tail', piv, None, fr, info=dict(kind='turret_mount', note='Unity +Z = aft'))
    az = MeshBuf()
    cylinder(az, piv - UP * 0.02, piv + UP * 0.09, 0.045, N=16, mat='metal_dark')
    zb = azz + (0.02 if ANM2_WAIST_BALL_ON_EL else 0.10)     # r2: yoke base 8 cm lower (the receivers dip through 0.30 at +-25 deg)
    box(az, (tp.x, tp.y, zb), (0.46, 0.12, 0.03), 'metal_dark')
    for k in (-1, 1):
        box(az, (k * 0.215, tp.y, (zb + tp.z + 0.06) / 2), (0.02, 0.12, tp.z + 0.06 - zb), 'metal_dark')
    if not ANM2_WAIST_BALL_ON_EL:
        box(az, (0, tp.y + 0.06, tp.z + 0.10), (0.42, 0.015, 0.16), 'metal_dark')                   # armour shield (gunner side)
    # 1.8.13 r2: the shield stood across the AN/M2 receivers (they run 0.5 m forward of the trunnion line): dropped with the new guns
    azp = Part('tail_turret_az', 'tail_turret_mount', piv, az, fr,
               info=dict(kind='turret_az', axis_local='+Y (Unity) = up', traverseRange=20, traverseRate=40,
                         note='H tail position yoke; rests identity under tail_turret_mount'))
    el = MeshBuf()
    cylinder(el, tp - V((0.225, 0, 0)), tp + V((0.225, 0, 0)), 0.022, N=12, mat='metal_dark')
    box(el, (0, tp.y - 0.02, tp.z - 0.01), (0.30, 0.20, 0.05), 'metal_dark')
    elp = Part('tail_guns', 'tail_turret_az', tp, el, fr,
               info=dict(kind='turret_el', axis_local='+X (Unity) = gunner right (aircraft left)', minElevation=-25,
                         maxElevation=25, elevationRate=35, note='twin M2 cradle, rests identity under tail_turret_az'))
    out = [mount, azp, elp]
    for k, L in ((-1, 'L'), (1, 'R')):
        o = V((k * (0.085 if ANM2_DORSAL else 0.10), tp.y, tp.z - 0.046))     # r2: 0.17 apart (grips clear the tail walls at +-20 deg)
        out += gun_part(f'gun_tail_{L}', 'tail_guns', o, V((0, -1, 0)), UP, f'muzzle_tail_{L}', 'tail M2')
    # fixed pedestal (fus_tail) is added to the tail mesh by add_tail_fixed()
    return out


def add_tail_fixed(tail_mesh):
    tp = V(S.TAIL_GUN_PIVOT)
    zf = fus_params(tp.y)[1] + 0.045
    cylinder(tail_mesh, V((tp.x, tp.y, zf)), V((tp.x, tp.y, 0.205)), 0.055, N=16, mat='metal_dark')
    box(tail_mesh, (0, tp.y, zf), (0.18, 0.22, 0.02), 'structure')


def tail_cap(tail_mesh):
    """tail end glazing with an opening for the guns (replaces the closed glass fan)."""
    ye = S.TAIL_END_Y
    o = fus_ring(ye)
    oi = fus_ring(ye, 0.006)
    tp = V(S.TAIL_GUN_PIVOT)
    cz = tp.z
    ax_, az_ = (0.30, 0.24) if ANM2_WAIST_BALL_ON_EL else (0.20, 0.17)     # r2: opening round the twin AN/M2 jackets' +-20 / +-25 deg sweep
    rings_o, rings_i = [], []
    for f in (0.0, 0.35, 0.7, 1.0):
        ro, ri = [], []
        for p, pi in zip(o, oi):
            a = math.atan2(p.z - cz, p.x)
            e = V((ax_ * math.cos(a), ye - 0.07, cz + az_ * math.sin(a)))
            bulge = -0.05 * math.sin(math.pi * f)
            q = p.lerp(e, f) + V((0, bulge, 0))
            qi = pi.lerp(e, f) + V((0, bulge + 0.006, 0))
            ro.append(q)
            ri.append(qi)
        rings_o.append(ro)
        rings_i.append(ri)
    loft(tail_mesh, rings_o, 'glass', outward=True)
    loft(tail_mesh, rings_i, 'glass', outward=False)
    # opening rim (metal) and canvas boot stub
    loft(tail_mesh, [rings_o[-1], [p + V((0, 0.05, 0)) for p in rings_o[-1]]], 'metal_dark', outward=False)
    loft(tail_mesh, [rings_o[-1], [p + V((0, 0.05, 0)) for p in rings_o[-1]]], 'metal_dark', outward=True)


# ============================================================================================ waist guns
ANM2_WAIST_BALL_ON_EL = True     # 1.8.13 r2 (offline L): ball socket on the elevation object (AN/M2 jacket through it, receiver inboard)
def build_waist_gun(side, sock):
    L = 'L' if side < 0 else 'R'
    out_dir = V((side, 0, 0))
    fr = frame_x((0, side * -1, 0))             # local Y (Blender) = outward
    mount = Part(f'waist_gun_{L}_mount', 'fus_rear', sock, None, fr, info=dict(kind='turret_mount', note='Unity +Z = outboard'))
    az = MeshBuf()
    if ANM2_WAIST_BALL_ON_EL:
        # 1.8.13 r2: the ball turns with the gun in BOTH axes (it is a ball mount): it moved to the elevation object, so the AN/M2 jacket
        # through its centre no longer runs into the azimuth body; the azimuth body keeps only the upper pivot pin above the socket
        cylinder(az, sock + UP * 0.108, sock + UP * 0.130, 0.012, N=10, mat='metal_dark')     # r3: on top of the 0.111 ball
    else:
        sphere(az, sock, 0.069, 'metal_dark', N=20, M=10)        # sits in the 0.068 m socket ring of the hatch
        cylinder(az, sock - out_dir * 0.09, sock - out_dir * 0.03, 0.03, N=10, mat='metal_dark')
    azp = Part(f'waist_gun_{L}_az', f'waist_gun_{L}_mount', sock, az, fr,
               info=dict(kind='turret_az', axis_local='+Y (Unity) = up', traverseRange=40, traverseRate=60,
                         note='ball socket in the waist hatch glass; rests identity under the mount'))
    el = MeshBuf()
    if ANM2_WAIST_BALL_ON_EL:
        sphere(el, sock, 0.111, 'metal_dark', N=20, M=10)        # the ball (r3: 0.111 in the widened 0.110 socket ring), the gun through its centre
    else:
        cylinder(el, sock - V((0, 0.05, 0)), sock + V((0, 0.05, 0)), 0.02, N=10, mat='metal_dark')
        box(el, sock - out_dir * 0.12 - UP * 0.04, (0.18, 0.08, 0.04), 'metal_dark')
    elp = Part(f'waist_gun_{L}', f'waist_gun_{L}_az', sock, el, fr,
               info=dict(kind='turret_el', axis_local='+X (Unity) (horizontal, along the fuselage)', minElevation=-30,
                         maxElevation=40, elevationRate=60, note='single M2 on the ball mount; rests identity under the az'))
    o = sock - out_dir * 0.28 - UP * 0.046
    res = [mount, azp, elp] + gun_part(f'gun_waist_{L}', f'waist_gun_{L}', o, out_dir, UP, f'muzzle_waist_{L}', 'waist M2')
    return res


# ============================================================================================ 75 mm T13E1
def build_cannon():
    x, z = P.CANNON_XZ
    ye = P.fus_exit_y(x, z, 4.6)
    tip = V((x, ye + 0.10, z))
    cm = MeshBuf()
    tube(cm, V((x, 3.42, z)), tip, 0.050, 0.0375, N=16)                         # light barrel
    cylinder(cm, V((x, 3.40, z)), V((x, 4.12, z)), 0.076, N=18)                 # concentric recoil sleeve
    cylinder(cm, V((x, 4.12, z)), V((x, 4.20, z)), 0.064, 0.056, N=18)          # front gland
    box(cm, V((x, 3.24, z)), (0.24, 0.32, 0.24), 'metal_dark')                  # breech ring
    box(cm, V((x, 3.20, z - 0.02)), (0.09, 0.13, 0.34), 'metal_dark')            # vertical sliding block
    cylinder(cm, V((x - 0.17, 3.45, z)), V((x + 0.17, 3.45, z)), 0.03, N=10)     # cradle trunnions
    for k in (-1, 1):                                                           # recoil guard rails
        cylinder(cm, V((x + k * 0.11, 3.08, z - 0.08)), V((x + k * 0.11, 2.62, z - 0.08)), 0.015, N=6)
    box(cm, V((x, 2.62, z - 0.08)), (0.26, 0.03, 0.03), 'metal_dark')
    can = Part('cannon', 'fus_nose', V((x, 3.40, z)), cm,
               info=dict(note='75 mm T13E1 (lightweight M5 derivative, concentric recoil sleeve), lower left'))
    return [can, Part('muzzle_cannon', 'cannon', tip)]


# ============================================================================================ pylons / hardpoints
def lower_skin_z(x, y, side):
    st = P.wing_station(abs(x), side)
    s = 0.3
    for _ in range(4):
        p = st.point(max(0.005, min(0.995, s)), False)
        s += (p.y - y) / (st.chord * abs(st.cdir.y))
    s = max(0.005, min(0.995, s))
    return st.point(s, False).z, s


def pylon(name, parent, side, x, y_mid, length, width, depth, hp_name, note):
    """streamlined blade pylon from inside the wing skin down to a flat bottom face; returns (pylon part,
    hardpoint empty at the bottom-face centre). Stock mounts put their attach rail 3-5.5 cm ABOVE the
    hardpoint (RocketPod1_single mesh top +0.055, launchpylon1 +0.030..+0.050), i.e. inside the pylon."""
    N = 28
    plan = []
    for k in range(N):
        t = k / N * 2
        if t <= 1:
            yy, ss = y_mid + length / 2 - length * t, 1
        else:
            yy, ss = y_mid - length / 2 + length * (t - 1), -1
        tt = (y_mid + length / 2 - yy) / length
        hw = width / 2 * max(0.0, 4 * tt * (1 - tt)) ** 0.5
        plan.append((x + ss * hw, yy))
    zs = [lower_skin_z(px, py, side)[0] for px, py in plan]
    zb = min(zs) - depth
    mb = MeshBuf()
    top = [V((px, py, z + 0.03)) for (px, py), z in zip(plan, zs)]
    bot = [V((px, py, zb)) for px, py in plan]
    rings = [bot, top]
    arcs = [arc_lengths(r) for r in rings]

    def uvf(ci, cj, j):
        acc, Pp = arcs[ci]
        v = acc[cj] if not (cj == 0 and j == N - 1) else Pp
        return (rings[ci][cj].z * 1.0, v)
    loft(mb, rings, 'paint', uvfunc=uvf)
    fan_cap(mb, bot, sum(bot, V()) / N, 'paint', -UP, uvfunc=lambda p: (p.x, p.y))
    fan_cap(mb, top, sum(top, V()) / N, 'structure', UP)
    hp = V((x, y_mid, zb))
    p = Part(name, parent, hp, mb, info=dict(kind='pylon', bottom_z=round(zb, 4), depth_below_skin=depth, note=note))
    p.uv_group = name
    h = Part(hp_name, parent, hp, None, info=dict(kind='hardpoint', note='at the pylon bottom face (stock CAS1 pattern: '
                                                    'hardpoint = pylon origin at its bottom)'))
    return p, h


def build_pylons():
    out = []
    for side, L in ((-1, 'L'), (1, 'R')):
        for k, x in enumerate((4.10, 4.60, 5.10, 5.60)):
            st = P.wing_station(x, side)
            y = st.point(0.32, False).y
            p, h = pylon(f'pylon_rail_{L}{k + 1}', f'wing_outer_{L}', side, side * x, y, 0.95, 0.07, 0.07,
                         f'hp_rail_{L}{k + 1}', 'HVAR zero-length launcher post; RocketPod1_single hangs from it')
            out += [p, h]
        st = P.wing_station(1.75, side)
        y = st.point(0.35, False).y
        p, h = pylon(f'pylon_wingrack_{L}', f'wing_inner_{L}', side, side * 1.75, y, 1.20, 0.10, 0.11,
                     f'hp_wingrack_{L}', 'wing bomb rack; launchpylon1-based bomb mounts hang from it')
        out += [p, h]
    return out


HP_BOMBBAY = (0.0, -0.08, -0.18)


def add_bay_carrier(ctr_mesh):
    """longitudinal carrier beam + cross beams from the side racks; shackle lugs at the stock internal-mount
    bomb positions (x = 0, +-0.20, +-0.275, +-0.35; tops 0.007..0.077 m above the hardpoint)."""
    hx, hy, hz = HP_BOMBBAY
    bz = hz + 0.105
    box(ctr_mesh, (0, -0.10, bz), (0.08, 2.40, 0.05), 'structure')
    for y in (0.58, -0.02, -0.62):
        box(ctr_mesh, (0, y, bz), (2 * (S.BAY_HALF_X - 0.06), 0.05, 0.04), 'structure')
    for x in (0.0, -0.20, 0.20, -0.275, 0.275, -0.35, 0.35):
        for y in (-0.70, -0.08, 0.55):
            box(ctr_mesh, (x, y, bz - 0.035), (0.03, 0.05, 0.03), 'metal_dark')


# ============================================================================================ crew (rear)
def build_rear_crew():
    out = []
    ry = S.CREW['radio']['seat'][1]
    fz = -0.42
    sm = MeshBuf()
    box(sm, (0, ry, fz + 0.40), (0.42, 0.40, 0.06), 'cockpit')
    box(sm, (0, ry, (fz + fz + 0.37) / 2), (0.30, 0.30, 0.37), 'cockpit')
    box(sm, (0, ry - 0.22, fz + 0.75), (0.42, 0.04, 0.66), 'cockpit')
    out.append(Part('crew_seat_radio', 'fus_rear', (0, ry, fz + 0.43), sm, info=dict(kind='crew_seat', crew='radio')))
    out.append(Part('crew_radio_eye', 'fus_rear', S.CREW['radio']['eye'], None, info=dict(kind='crew_eye', crew='radio', look='+Z (Unity)')))
    ty = S.CREW['tail']['seat'][1]
    tm = MeshBuf()
    box(tm, (0, ty, 0.22), (0.36, 0.30, 0.05), 'interior')
    box(tm, (0, ty, 0.08), (0.24, 0.24, 0.24), 'interior')
    box(tm, (0, ty + 0.20, 0.48), (0.36, 0.04, 0.50), 'interior')             # back (forward of the seat: faces aft)
    out.append(Part('crew_seat_tail', 'fus_tail', (0, ty, 0.25), tm, info=dict(kind='crew_seat', crew='tail')))
    out.append(Part('crew_tail_eye', 'fus_tail', S.CREW['tail']['eye'], None, frame_x((-1, 0, 0)),
                    info=dict(kind='crew_eye', crew='tail', look='+Z (Unity) = aft')))
    return out


# ============================================================================================ prop blur (separate FBX)
def prop_disc_meshes(R=S.PROP_R, r0=0.17):
    """two discs in the hub frame (Blender: spin axis +Y). UV layout of the stock CI-22 blur texture
    (COIN_propblur_b, 512 x 1024): top half (v 0.5-1) = slow blur of the blades, bottom half (v 0-0.5) = full disc."""
    out = {}
    for name, vc in (('propdisc_blur', 0.75), ('propdisc_full', 0.25)):
        mb = MeshBuf()
        N, M = 64, 6
        rs = [r0 + (R - r0) * k / M for k in range(M + 1)]
        for sgn in (1, -1):
            g = [[mb.v(V((r * math.sin(2 * math.pi * j / N), sgn * 0.004, r * math.cos(2 * math.pi * j / N)))) for j in range(N + 1)] for r in rs]
            for row in g:
                row[-1] = row[0]
            uvf = lambda i, j, rs=rs: (0.5 + 0.485 * rs[i] / R * math.sin(2 * math.pi * j / N), vc + 0.2425 * rs[i] / R * math.cos(2 * math.pi * j / N))
            grid_faces(mb, g, 'propdisc', lambda p, s=sgn: V((0, s, 0)), uvfn=uvf)
        out[name] = mb
    return out
