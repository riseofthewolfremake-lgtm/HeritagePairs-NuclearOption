"""MSB-17/80 parts that the B-17G does not have (procedural hard surface; no fal, nothing from any reference model).

Every builder returns blender/v2/b25h_parts.Part objects (world-space MeshBuf in the rest pose), as the b17g modules do.
  - twin20_mesh / turret_twin20: our own automated twin 20 mm cannon (cradle, two receivers with top covers, feed ports and flexible
    feed chutes, recoil sleeves, ribbed barrels, slotted muzzle brakes) in a ball mantlet that elevates, on an azimuth drum
  - laser_turret: the 120 kW laser turrets (azimuth drum in the B-17G top / ball openings, yoke, elevating sensor head with the beam
    aperture, two small sensor windows)
  - nacelle_front / props: the turboprop cowl nose (chin intake), exhaust stub, two contra-rotating 6-blade rows with split spinners
  - engine_internals: reduction gearbox, turboshaft core, mounts and exhaust duct (instead of the B-17G radial / turbo)
  - pylons, bay hardpoints + the wing carry-through box over the 5.7 m bay, side bays (liners, doors, hardpoints)
  - sensors: EO/IR targeting ball, blade antennas, missile-warning windows, flare dispenser panels
"""
import math
from mathutils import Vector as V, Quaternion, Matrix
import b17g_spec as S
import msb_spec as M
from b25h_geom import MeshBuf, circle_pts, loft, fan_cap, annulus, oriented_quad, cylinder, box
from b25h_parts import Part
import nimrod_structure as NS


# ============================================================================================ helpers
def lathe(mb, c, axis, prof, N, mat, ref=None, cap0=None, cap1=None, outward=True):
    """rings circle_pts(c + axis * d, axis, r) for prof = [(d, r)] (d ascending); optional fan caps at either end (material)."""
    axis = V(axis).normalized()
    rings = [circle_pts(V(c) + axis * d, axis, max(r, 1e-4), N, ref) for d, r in prof]
    loft(mb, rings, mat, outward=outward)
    if cap0:
        fan_cap(mb, rings[0], V(c) + axis * prof[0][0], cap0, -axis)
    if cap1:
        fan_cap(mb, rings[-1], V(c) + axis * prof[-1][0], cap1, axis)
    return rings


def frame_quat(fwd, up=V((0, 0, 1))):
    """Blender local Y = fwd (Unity +Z), local Z = up (Unity +Y), local X = right (the b17g turret_frames convention)."""
    fwd = V(fwd).normalized()
    upn = (V(up) - fwd * V(up).dot(fwd)).normalized()
    xax = fwd.cross(upn).normalized()
    return Matrix((xax, fwd, upn)).transposed().to_quaternion()


def xform(mb, q, t):
    """MeshBuf in a local frame (X right, Y forward, Z up) -> world: rotate by q, translate to t (in place, returns mb)."""
    R = q.to_matrix()
    mb.verts = [V(t) + R @ p for p in mb.verts]
    return mb


def sphere_rings(c, r, frame, lats, nlon, rz=None):
    """rings of an ellipsoid about local Y (frame = (X, Y, Z)); lats = polar angles (deg) from +Y."""
    X, Y, Z = frame
    rz = r if rz is None else rz
    out = []
    for t in lats:
        tr = math.radians(t)
        out.append([V(c) + Y * (r * math.cos(tr)) + X * (r * math.sin(tr) * math.cos(2 * math.pi * k / nlon)) + Z * (rz * math.sin(tr) * math.sin(2 * math.pi * k / nlon))
                    for k in range(nlon)])
    return out


# ============================================================================================ twin 20 mm cannon (gun frame)
# Gun frame: origin on the elevation pivot (the cradle trunnion axis, local X), +Y = fire, +Z = up. Barrel axes at x = +-M.TWIN_DX, z 0.
TIP_Y = 1.62                    # muzzle-brake tip (bullets leave here)
BARREL_R = 0.021
REC = dict(y0=-0.30, y1=0.08, w=0.105, z0=-0.075, z1=0.070)


def twin20_mesh(ball_r=None):
    """the twin 20 mm unit. ball_r: the mantlet ball radius the receivers / chutes must stay inside (None = no limit)."""
    mb = MeshBuf()
    dx = M.TWIN_DX
    # cradle: centre beam between the receivers, trunnion pins out through it, front yoke plate tying the two barrels
    box(mb, (0, -0.02, -0.005), (2 * dx - REC['w'] - 0.004, 0.36, 0.11), 'gear')
    cylinder(mb, V((-0.06, 0, 0)), V((0.06, 0, 0)), 0.032, N=14, mat='metal_dark')
    for sx in (-1, 1):
        x = sx * dx
        # receiver: main body + raised top cover with hinge knuckle + side ribs + rear buffer housing + bolts
        box(mb, (x, (REC['y0'] + REC['y1']) / 2, (REC['z0'] + REC['z1']) / 2), (REC['w'], REC['y1'] - REC['y0'], REC['z1'] - REC['z0']), 'engine')
        box(mb, (x, (REC['y0'] + REC['y1']) / 2 + 0.02, REC['z1'] + 0.012), (REC['w'] - 0.022, REC['y1'] - REC['y0'] - 0.08, 0.024), 'gear')
        cylinder(mb, V((x - 0.035, REC['y0'] + 0.03, REC['z1'] + 0.012)), V((x + 0.035, REC['y0'] + 0.03, REC['z1'] + 0.012)), 0.010, N=8, mat='metal_dark')
        for k in range(4):
            yy = REC['y0'] + 0.08 + k * 0.10
            box(mb, (x + sx * (REC['w'] / 2 + 0.004), yy, 0.0), (0.008, 0.012, REC['z1'] - REC['z0'] - 0.03), 'gear')
        cylinder(mb, V((x, REC['y0'] - 0.07, -0.005)), V((x, REC['y0'], -0.005)), 0.040, 0.046, N=16, mat='metal_dark')
        for bz in (-0.04, 0.04):
            for by in (REC['y0'] + 0.05, REC['y1'] - 0.05):
                cylinder(mb, V((x - sx * 0.002 + sx * REC['w'] / 2, by, bz)), V((x + sx * (REC['w'] / 2 + 0.008), by, bz)), 0.007, N=6, mat='chrome')
        # feed port on the OUTBOARD side + flexible feed chute curving down and in (link chute, segmented)
        box(mb, (x + sx * (REC['w'] / 2 + 0.018), -0.06, 0.005), (0.036, 0.15, 0.080), 'gear')
        ch = []
        for k in range(6):
            a = math.radians(k * 15)
            ch.append(V((x + sx * (REC['w'] / 2 + 0.024 - 0.03 * (1 - math.cos(a))), -0.08 - 0.014 * k, 0.045 + 0.10 * math.sin(a))))
        for a_, b_ in zip(ch, ch[1:]):
            NS.sec_tube(mb, a_, b_, 0.040, 0.060, V((sx, 0, 0)), mat='metal_dark')
            m_ = (a_ + b_) / 2
            box(mb, (m_.x, m_.y, m_.z), (0.046, 0.010, 0.066), 'gear')
        # case-ejection chute under the receiver
        box(mb, (x, 0.0, REC['z0'] - 0.018), (0.05, 0.08, 0.036), 'metal_dark')
        # recoil sleeve + spring housing under the barrel, then the barrel with cooling bands and the slotted muzzle brake
        cylinder(mb, V((x, REC['y1'], 0)), V((x, 0.46, 0)), 0.038, 0.032, N=16, mat='engine')
        cylinder(mb, V((x, REC['y1'], -0.048)), V((x, 0.40, -0.048)), 0.015, N=10, mat='gear')
        cylinder(mb, V((x, 0.46, 0)), V((x, TIP_Y - 0.17, 0)), BARREL_R, BARREL_R * 0.92, N=14, mat='metal_dark')
        for yb in (0.62, 0.86, 1.10):
            cylinder(mb, V((x, yb, 0)), V((x, yb + 0.05, 0)), BARREL_R + 0.008, N=14, mat='engine')
        # muzzle brake: body with four rows of side ports (separate rings with gaps), open bore at the tip
        yb0 = TIP_Y - 0.17
        pr = [(yb0, 0.031), (yb0 + 0.03, 0.031)]
        for k in range(4):
            y0 = yb0 + 0.035 + k * 0.032
            cylinder(mb, V((x, y0, 0)), V((x, y0 + 0.018, 0)), 0.030, N=14, mat='metal_dark')
            cylinder(mb, V((x, y0 + 0.018, 0)), V((x, y0 + 0.032, 0)), 0.024, N=14, mat='metal_dark', cap0=False, cap1=False)
        cylinder(mb, V((x, yb0, 0)), V((x, yb0 + 0.035, 0)), 0.031, N=14, mat='metal_dark')
        tip0 = yb0 + 0.035 + 4 * 0.032
        rings = [circle_pts(V((x, tip0, 0)), V((0, 1, 0)), 0.031, 14), circle_pts(V((x, TIP_Y, 0)), V((0, 1, 0)), 0.029, 14)]
        loft(mb, rings, 'metal_dark')
        inner = circle_pts(V((x, TIP_Y, 0)), V((0, 1, 0)), 0.011, 14)
        annulus(mb, rings[-1], inner, 'metal_dark', V((0, 1, 0)))
        fan_cap(mb, circle_pts(V((x, TIP_Y - 0.05, 0)), V((0, 1, 0)), 0.011, 14), V((x, TIP_Y - 0.05, 0)), 'metal_dark', V((0, 1, 0)))
        loft(mb, [inner, circle_pts(V((x, TIP_Y - 0.05, 0)), V((0, 1, 0)), 0.011, 14)], 'metal_dark', outward=False)
    # front yoke: plate joining both barrels ahead of the sleeves (the twin's spacing), with a bore clamp per barrel
    box(mb, (0, 0.50, 0), (2 * dx, 0.03, 0.035), 'gear')
    for sx in (-1, 1):
        cylinder(mb, V((sx * dx, 0.485, 0)), V((sx * dx, 0.515, 0)), 0.030, N=14, mat='gear')
    return mb


def twin20_tips():
    return [V((-M.TWIN_DX, TIP_Y, 0.0)), V((M.TWIN_DX, TIP_Y, 0.0))]


# ============================================================================================ turret frames (b17g convention)
def turret_parts(name, parent, mount, aim, up, el_pivot, kind):
    q = frame_quat(aim, up)
    t = S.TURRETS[name]
    out = [Part(f'{name}_mount', parent, pivot=V(mount), frame=q, info={'kind': 'turret_mount', 'station': t['station'], 'weapon': kind,
                                                                         'traverseRange': t['trav'], 'minElevation': t['emin'], 'maxElevation': t['emax']}),
           Part(f'{name}_az', f'{name}_mount', pivot=V(mount), frame=q),
           Part(f'{name}_el', f'{name}_az', pivot=V(el_pivot), frame=q)]
    return out, q


def turret_twin20(name, parent, mount, aim, up, el_off, ball_r, drum):
    """remote twin 20 mm turret: azimuth body (drum(mb) builds it), a ball mantlet (radius ball_r) on the elevation pivot with two barrel
    ports, the cannon inside. el_off: elevation pivot relative to the mount in the turret frame (x right, y aim, z up)."""
    q0 = frame_quat(aim, up)
    el = V(mount) + q0 @ V(el_off)
    out, q = turret_parts(name, parent, mount, aim, up, el, '20mm')
    body = drum()
    out.append(Part(f'{name}_body', f'{name}_az', mesh=body, info={'kind': 'turret_body', 'type': 'remote twin 20 mm housing'}))
    # mantlet ball: rings about the gun axis, the two barrel ports cut as holes (faces whose centre is within the port radius of a barrel axis
    # on the front half are dropped), a dark port liner round each opening, and an interior copy (seen through the ports)
    bm = MeshBuf()
    lats = [0, 6, 12, 18, 26, 36, 48, 62, 76, 90, 104, 118, 132, 146, 160, 172, 180]
    rings = sphere_rings(V((0, 0, 0)), ball_r, (V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1))), lats[1:-1], 36)
    port_r = 0.036
    def keep(i, j):
        a, b = rings[i][j], rings[i + 1][(j + 1) % 36]
        c = (a + b) / 2
        return not (c.y > 0 and any(math.hypot(c.x - sx * M.TWIN_DX, c.z) < port_r + 0.006 for sx in (-1, 1)))
    loft(bm, rings, 'paint', keep=keep)
    fan_cap(bm, rings[0], V((0, ball_r, 0)), 'paint', V((0, 1, 0)))
    fan_cap(bm, rings[-1], V((0, -ball_r, 0)), 'paint', V((0, -1, 0)))
    if math.hypot(M.TWIN_DX, 0) < ball_r:
        for sx in (-1, 1):
            yb = math.sqrt(max(ball_r ** 2 - M.TWIN_DX ** 2, 1e-6))
            cylinder(bm, V((sx * M.TWIN_DX, yb - 0.10, 0)), V((sx * M.TWIN_DX, yb + 0.012, 0)), port_r + 0.004, N=16, mat='metal_dark', cap0=False, cap1=False)
            ring_o = circle_pts(V((sx * M.TWIN_DX, yb + 0.012, 0)), V((0, 1, 0)), port_r + 0.018, 16)
            ring_i = circle_pts(V((sx * M.TWIN_DX, yb + 0.012, 0)), V((0, 1, 0)), port_r + 0.004, 16)
            annulus(bm, ring_o, ring_i, 'gear', V((0, 1, 0)))
            loft(bm, [circle_pts(V((sx * M.TWIN_DX, yb - 0.02, 0)), V((0, 1, 0)), port_r + 0.018, 16), ring_o], 'gear')
    n0 = len(bm.faces)
    for f in list(bm.faces[:n0]):
        if f['mat'] != 'paint':
            continue
        P_ = [bm.verts[k] for k in f['idx']]
        c_ = sum(P_, V()) / len(P_)
        nn = c_.normalized() if c_.length > 1e-6 else V((0, 0, 1))
        bm.face([bm.v(p - nn * 0.008) for p in reversed(P_)], 'interior', None)
    # seam ring round the ball's equator (vertical plane) and two hinge bosses on the trunnion axis
    for sx in (-1, 1):
        cylinder(bm, V((sx * (ball_r - 0.02), 0, 0)), V((sx * (ball_r + 0.018), 0, 0)), 0.055, N=18, mat='gear')
    xform(bm, q, el)
    out.append(Part(f'{name}_ball', f'{name}_el', mesh=bm, info={'kind': 'turret_frame', 'type': 'elevating ball mantlet'}))
    gun = xform(twin20_mesh(ball_r), q, el)
    out.append(Part(f'{name}_gun0', f'{name}_el', pivot=el, frame=q, mesh=gun, info={'kind': 'gun_20mm', 'type': 'MSB twin 20 mm (own model)'}))
    for k, tp in enumerate(twin20_tips()):
        out.append(Part(f'{name}_muzzle{k}', f'{name}_gun0', pivot=el + q @ tp, frame=q, info={'kind': 'muzzle'}))
    return out


def chin_drum():
    """chin: a squat drum in the 0.50 m chin opening (r 0.470, the race ring above it from the B-17G nose) with a rounded bottom and a
    front window where the mantlet ball stands out; panel seams; turns in azimuth."""
    c = V(S.TURRETS['chin']['pos'])
    mb = MeshBuf()
    prof = [(0.418, 0.468), (0.30, 0.470), (0.10, 0.470), (-0.06, 0.462), (-0.14, 0.440), (-0.20, 0.395), (-0.235, 0.32), (-0.255, 0.20), (-0.262, 0.0)]
    rings = [circle_pts(c + V((0, 0, z)), V((0, 0, 1)), max(r, 1e-3), 48, ref=V((0, 1, 0))) for z, r in prof]
    el = c + V((0, 0.30, -0.10)); br = 0.27
    def keep(i, j):
        a, b = rings[i][j], rings[i + 1][(j + 1) % 48]
        m_ = (a + b) / 2
        return (m_ - el).length > br - 0.010
    loft(mb, rings, 'paint', keep=keep)
    fan_cap(mb, rings[0], c + V((0, 0, prof[0][0])), 'paint', V((0, 0, 1)))
    inner = []
    for f in list(mb.faces):
        P_ = [mb.verts[k] for k in f['idx']]
        cc = sum(P_, V()) / len(P_)
        nn = (cc - V((c.x, c.y, cc.z))).normalized() if (cc - V((c.x, c.y, cc.z))).length > 1e-6 else V((0, 0, -1))
        inner.append([mb.v(p - nn * 0.008) for p in reversed(P_)])
    for idx in inner:
        mb.face(idx, 'interior', None)
    for z, w in ((0.06, 0.010), (-0.16, 0.010)):
        ring = [p for p in circle_pts(c + V((0, 0, z)), V((0, 0, 1)), 0.474 if z > 0 else 0.44, 48, ref=V((0, 1, 0)))]
        runs, cur = [], []
        for p in ring + ring[:1]:
            if (p - el).length < br + 0.02:
                if len(cur) >= 2:
                    runs.append(cur)
                cur = []
            else:
                cur.append(p)
        if len(cur) >= 2:
            runs.append(cur)
        for run in runs:
            for a_, b_ in zip(run, run[1:]):
                n_ = ((a_ + b_) / 2 - V((c.x, c.y, (a_.z + b_.z) / 2))).normalized()
                NS.sec_tube(mb, a_ + n_ * 0.004, b_ + n_ * 0.004, w, 0.005, n_, mat='paint')
    return mb


def tail_drum():
    """tail: the Cheyenne cover position becomes a rounded remote-turret housing (superellipsoid of revolution about the azimuth axis,
    the B-17G cover's size, so it turns inside the fuselage end) with the mantlet ball on its aft face."""
    c = V(S.TURRETS['tail']['pos'])
    rh, rv, n = 0.41, 0.38, 2.6          # 4 cm narrower than the B-17G cover: clear of the opening's rim at every azimuth
    mb = MeshBuf()
    el = c + V((0, -0.20, 0.0)); br = 0.28          # chin method: the elevation axis 0.21 inside the drum face, so the receivers + feed chutes swing in the open drum and the r 0.28 mantlet stands 7 cm proud
    zs = [rv * math.sin(math.radians(a)) for a in (89.5, 75, 60, 45, 30, 15, 0, -15, -30, -45, -60, -75, -89.5)]
    rings = []
    for z in zs:
        r = rh * max(1 - (abs(z) / rv) ** n, 1e-6) ** (1 / n)
        rings.append(circle_pts(c + V((0, 0, z)), V((0, 0, 1)), r, 48, ref=V((0, -1, 0))))
    def keep(i, j):
        a, b = rings[i][j], rings[i + 1][(j + 1) % 48]
        m_ = (a + b) / 2; d_ = m_ - el
        slot = abs(d_.x) < 0.20 and -d_.y > 0 and abs(math.degrees(math.atan2(d_.z, -d_.y))) < 64.0      # vertical gun slot (15-deg rings, sleeve under the barrel): the barrels' +-40 deg path
        return d_.length > br - 0.010 and not slot and (m_ - c).dot(V((0, -1, 0))) > -0.02     # the aft half (the front half would sit
    loft(mb, rings, 'paint', keep=keep)                                                                                       # inside the fuselage end: B-17G cover method)
    for f in list(mb.faces):
        P_ = [mb.verts[k] for k in f['idx']]
        cc = sum(P_, V()) / len(P_)
        nn = (cc - c).normalized()
        mb.face([mb.v(p - nn * 0.008) for p in reversed(P_)], 'interior', None)
    return mb


# ============================================================================================ 120 kW laser turrets
APERTURE_R = 0.105


def ventral_seal():
    """1.9.1 (coordinator: a dark 3-12 cm ring showed round the ventral laser drum): a fixed seal ring on the belly closing the gap between
    the drum (r 0.60, seam bands to r 0.612) and the B-17G ball-turret ring band (r 0.73): skin-coloured annulus r 0.618 -> 0.73 flush
    with the B-17G flange (belly - 12 mm, the flange starts at r 0.73) and a dark rubber lip at its inner edge. The drum turns inside it."""
    import b17g_parts as P
    t = S.TURRETS['ball']; c = V(t['pos'])
    mb = MeshBuf()
    N = 48
    r_in, r_lip, r_out = 0.618, 0.632, M.BALL_HOLE_R + 0.01
    ring = lambda r, dz: [V((c.x + r * math.cos(2 * math.pi * k / N), c.y + r * math.sin(2 * math.pi * k / N), 0)) for k in range(N)]
    def onb(pts, dz):
        return [V((p.x, p.y, P.belly_z(p.x, p.y) - 0.012 + dz)) for p in pts]
    lip, mid, out_ = onb(ring(r_in, 0), 0), onb(ring(r_lip, 0), 0), onb(ring(r_out, 0), 0)
    for a_, b_, mat in ((lip, mid, 'gear'), (mid, out_, 'paint')):
        for k in range(N):
            q = [a_[k], a_[(k + 1) % N], b_[(k + 1) % N], b_[k]]
            oriented_quad(mb, q, mat, V((0, 0, -1)))
            oriented_quad(mb, [p + V((0, 0, 0.008)) for p in q], 'interior', V((0, 0, 1)))
    lip_up = [p + V((0, 0, 0.008)) for p in lip]                       # closed inner edge
    for k in range(N):
        oriented_quad(mb, [lip[k], lip[(k + 1) % N], lip_up[(k + 1) % N], lip_up[k]], 'gear', (lip[k] - V((c.x, c.y, lip[k].z))))
    return [Part('ball_seal', 'fus_waist', mesh=mb, info={'kind': 'turret_race', 'type': 'ventral laser seal ring'})]


def laser_turret(name, parent):
    """azimuth drum in the race (top: on the roof, ball: under the belly), yoke arms, elevating sensor head (ellipsoid) with the beam
    aperture (dark ring + glass) on its nose and two small sensor windows; the beam leaves from <name>_aperture (Laser.directionTransform)."""
    t = S.TURRETS[name]
    c = V(t['pos'])
    down = name == 'ball'
    s = -1.0 if down else 1.0
    Z = V((0, 0, s))
    # skin height at the race centre
    top, bot, hw, nn = S.fus_station(c.y)
    zs = top if not down else bot
    base = V((c.x, c.y, zs))
    el = base + Z * 0.36
    aim = V((0, 1, 0))
    out, q = turret_parts(name, parent, c, aim, V((0, 0, 1)), el, 'laser')
    # drum: from 0.12 inside the skin to 0.13 outside, rounded shoulder; a low fairing ring between the yoke arms
    mb = MeshBuf()
    R0 = 0.475 if not down else M.BALL_HOLE_R - 0.12          # fills the B-17G race (top: flange from r 0.49) / ball: 0.60, inside the face-cut hole (its rim reaches r 0.63)
    d0 = -0.12 if not down else -0.06                         # 1.9.1 ventral: the wall rises 6 cm (top z -0.43: under the skin at the sides, -0.39, and inside the hole fore and aft); the r 0.618 seal ring leaves a 6-18 mm slit
    prof = [(d0, R0), (0.06, R0), (0.10, R0 - 0.005), (0.125, R0 - 0.03), (0.14, R0 - 0.08), (0.15, 0.20), (0.152, 0.0)]
    rings = [circle_pts(base + Z * d, Z, max(r, 1e-3), 48, ref=V((0, 1, 0))) for d, r in prof]
    loft(mb, rings, 'paint')
    fan_cap(mb, rings[0], base + Z * prof[0][0], 'interior', -Z)
    for d, w in ((0.03, 0.010), (0.10, 0.008)):
        ring = circle_pts(base + Z * d, Z, R0 + 0.002 if d < 0.08 else R0 - 0.003, 48, ref=V((0, 1, 0)))
        for a_, b_ in zip(ring, ring[1:] + ring[:1]):
            n_ = ((a_ + b_) / 2 - (base + Z * d)).normalized()
            NS.sec_tube(mb, a_ + n_ * 0.004, b_ + n_ * 0.004, w, 0.005, n_, mat='paint')
    # yoke arms (to the head's trunnions at x +-0.25) and a small sensor fairing at the rear of the drum
    for sx in (-1, 1):
        prof2 = [V((sx * 0.235, -0.09, 0.0)), V((sx * 0.235, 0.09, 0.0)), V((sx * 0.235, 0.07, 0.36)), V((sx * 0.235, -0.07, 0.36))]
        o_ = [base + V((p.x, p.y, p.z * s)) for p in prof2]
        i_ = [p + V((-sx * 0.045, 0, 0)) for p in o_]
        oriented_quad(mb, o_, 'paint', V((sx, 0, 0))); oriented_quad(mb, i_, 'paint', V((-sx, 0, 0)))
        for k in range(4):
            a, b = o_[k], o_[(k + 1) % 4]; a2, b2 = i_[k], i_[(k + 1) % 4]
            m_ = (a + b + a2 + b2) / 4
            oriented_quad(mb, [a, b, b2, a2], 'paint', m_ - (base + Z * 0.18 + V((sx * 0.21, 0, 0))))
    box(mb, (c.x, c.y - 0.30, zs + s * 0.19), (0.16, 0.14, 0.10), 'paint')
    oriented_quad(mb, [V((c.x - 0.05, c.y - 0.229, zs + s * 0.16)), V((c.x + 0.05, c.y - 0.229, zs + s * 0.16)), V((c.x + 0.05, c.y - 0.229, zs + s * 0.22)),
                       V((c.x - 0.05, c.y - 0.229, zs + s * 0.22))], 'glass', V((0, 1, 0)))
    out.append(Part(f'{name}_body', f'{name}_az', mesh=mb, info={'kind': 'turret_body', 'type': '120 kW laser turret base'}))
    # elevating head (gun frame: Y = beam, Z = up): ellipsoid 0.20 / 0.19 / 0.17, aperture ring + glass on its nose, trunnion bosses
    hb = MeshBuf()
    lats = [8, 16, 24, 34, 46, 60, 75, 90, 105, 120, 135, 150, 165, 174]
    rr = sphere_rings(V((0, 0, 0)), 0.20, (V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1))), lats, 32, rz=0.17)
    loft(hb, rr, 'paint')
    fan_cap(hb, rr[-1], V((0, -0.20, 0)), 'paint', V((0, -1, 0)))
    front = rr[0]
    yA = 0.20 * math.cos(math.radians(8))
    ring_ap = circle_pts(V((0, yA + 0.01, 0)), V((0, 1, 0)), APERTURE_R + 0.022, 32)
    loft(hb, [front, ring_ap], 'metal_dark')
    ring_in = circle_pts(V((0, yA + 0.01, 0)), V((0, 1, 0)), APERTURE_R, 32)
    annulus(hb, ring_ap, ring_in, 'metal_dark', V((0, 1, 0)))
    deep = circle_pts(V((0, yA - 0.03, 0)), V((0, 1, 0)), APERTURE_R, 32)
    loft(hb, [ring_in, deep], 'metal_dark', outward=False)
    fan_cap(hb, deep, V((0, yA - 0.03, 0)), 'metal_dark', V((0, 1, 0)))
    fan_cap(hb, circle_pts(V((0, yA - 0.005, 0)), V((0, 1, 0)), APERTURE_R - 0.002, 32), V((0, yA - 0.005, 0)), 'glass', V((0, 1, 0)))
    for sx in (-1, 1):
        cylinder(hb, V((sx * 0.17, 0, 0)), V((sx * 0.205, 0, 0)), 0.065, N=18, mat='metal_dark')
        p = V((sx * 0.11, 0.13, 0.08))
        nrm = V((sx * 0.11 / 0.20, 0.13 / 0.20, 0.08 / 0.17)).normalized()
        sq = [p + V((dx_, 0, dz_)) for dx_, dz_ in ((-0.025, -0.02), (0.025, -0.02), (0.025, 0.02), (-0.025, 0.02))]
        oriented_quad(hb, [v + nrm * 0.006 for v in sq], 'glass', nrm)
        oriented_quad(hb, [v + nrm * 0.002 for v in sq], 'metal_dark', nrm)
    xform(hb, q, el)
    out.append(Part(f'{name}_head', f'{name}_el', mesh=hb, info={'kind': 'turret_frame', 'type': 'laser head'}))
    out.append(Part(f'{name}_aperture', f'{name}_el', pivot=el + q @ V((0, yA + 0.012, 0)), frame=q, info={'kind': 'laser_aperture'}))
    return out


# ============================================================================================ engines: cowl nose, props, exhaust
def _r_cowl(R, s):
    return R - (R - M.COWL['r_spin']) * s ** 1.6


def nacelle_front(kind, side):
    """engine_n: cowl nose from the B-17G drum lip (ylip - 0.10, radius R) to the spinner base (r 0.40, ylip + 0.50), a chin intake
    under it, the inner wall / bulkhead behind the spinner; prop_n (front row, the part) + prop_n_aft (aft row) empties; exhaust_n."""
    num = S.ENGINE_NUM[(side, kind)]
    xa, za, ylip, yprop, R, yend, zb = S.NACELLES[kind]
    cx = xa * side
    ax = V((0, 1, 0))
    y0 = ylip - 0.10
    L = M.COWL['y_spin'] + 0.10
    e = MeshBuf()
    prof = [(y0 + L * s, _r_cowl(R, s)) for s in (0.0, 0.08, 0.18, 0.30, 0.44, 0.58, 0.72, 0.86, 1.0)]
    rings = [circle_pts(V((cx, y, za)), ax, r, 48, ref=V((0, 0, 1))) for y, r in prof]
    loft(e, rings, 'paint')
    NS.double_skin(e, t=0.006, mats=('paint',), inner=lambda f, c: 'interior')
    yb = prof[-1][0]
    fan_cap(e, circle_pts(V((cx, yb - 0.02, za)), ax, M.COWL['r_spin'] - 0.01, 48, ref=V((0, 0, 1))), V((cx, yb - 0.02, za)), 'metal_dark', ax)
    # panel seams on the cowl (two rings + a top line), small fasteners
    for s_ in (0.30, 0.66):
        ring = circle_pts(V((cx, y0 + L * s_, za)), ax, _r_cowl(R, s_) + 0.003, 48, ref=V((0, 0, 1)))
        for a_, b_ in zip(ring, ring[1:] + ring[:1]):
            n_ = ((a_ + b_) / 2 - V((cx, (a_.y + b_.y) / 2, za))).normalized()
            NS.sec_tube(e, a_, b_, 0.010, 0.004, n_, mat='paint')
    # chin intake: a scoop under the cowl, mouth at ylip + 0.30, fairing back to ylip - 0.42 (U section, open into the cowl)
    ym, yt = ylip + 0.30, ylip - 0.42
    def zcowl(y):
        s_ = min(max((y - y0) / L, 0.0), 1.0)
        return za - (_r_cowl(R, s_) if y >= y0 else R)
    scoop = []
    for k, y in enumerate([ym - (ym - yt) * i / 8 for i in range(9)]):
        h = 0.16 * (1 - (i := k) / 8) ** 0.7 + 0.01
        w = 0.20 * (1 - 0.35 * i / 8)
        zc = zcowl(y)
        scoop.append([V((cx - w, y, zc + 0.10)), V((cx - w, y, zc - h + 0.03)), V((cx - w * 0.75, y, zc - h)), V((cx + w * 0.75, y, zc - h)),
                      V((cx + w, y, zc - h + 0.03)), V((cx + w, y, zc + 0.10))])
    loft(e, scoop, 'paint', closed=False)
    m0 = scoop[0]
    inner = [V((p.x + (cx - p.x) * 0.12, p.y - 0.02, p.z + (zcowl(ym) - 0.06 - p.z) * 0.12)) for p in m0]
    for a_, b_, c_, d_ in zip(m0, m0[1:], inner[1:], inner):
        oriented_quad(e, [a_, b_, c_, d_], 'metal_dark', V((0, 1, 0)))
    loft(e, [inner, [p - V((0, 0.35, 0)) for p in inner]], 'metal_dark', closed=False, outward=False)
    oriented_quad(e, [inner[0], inner[-1], inner[-1] - V((0, 0.35, 0)), inner[0] - V((0, 0.35, 0))], 'metal_dark', V((0, 0, -1)))
    out = [Part(f'engine_{num}', f'nacelle_{num}', pivot=V((cx, ylip, za)), mesh=e, info={'kind': 'engine', 'engine': num, 'cowl_r': R})]
    ya, yf, ytip = M.prop_planes(kind)
    out.append(Part(f'prop_{num}', f'engine_{num}', pivot=V((cx, yf, za)), info={'kind': 'prop', 'engine': num, 'radius': S.PROP_R, 'row': 'front', 'turn': M.ROW_TURN['front']}))
    out.append(Part(f'prop_{num}_aft', f'prop_{num}', pivot=V((cx, ya, za)), info={'kind': 'prop_row', 'engine': num, 'radius': S.PROP_R, 'row': 'aft', 'turn': M.ROW_TURN['aft']}))
    # exhaust: an oval stub on the nacelle's outboard upper side over the wing, pointing aft-out-up; IR source at its exit
    ye = 1.70 if kind == 'inner' else 1.20
    from b17g_nacelle import nac_profile
    hw_, top_, bot_ = nac_profile(kind, ye)
    zc = (top_ + bot_) / 2
    base = V((cx + side * hw_ * 0.78, ye, zc + (top_ - zc) * 0.55))
    d = V((side * 0.35, -1.0, 0.25)).normalized()
    ex = MeshBuf()
    ring0 = [base + V((side * 0.0, 0, 0)) + V((0.09 * math.cos(a) * 0.6, 0.13 * math.sin(a) * 0.3, 0.13 * math.sin(a))) for a in [2 * math.pi * k / 16 for k in range(16)]]
    ring1 = [p - V((side * 0.0, 0.0, 0)) + d * 0.40 + V((side * 0.02, 0, 0)) for p in ring0]
    loft(ex, [[p - d * 0.25 for p in ring0], ring0, ring1], 'exhaust')
    ring2 = [ring1[k] + (ring1[k] - sum(ring1, V()) / 16).normalized() * -0.025 for k in range(16)]
    annulus(ex, ring1, ring2, 'exhaust', d)
    loft(ex, [ring2, [p - d * 0.12 for p in ring2]], 'metal_dark', outward=False)
    fan_cap(ex, [p - d * 0.12 for p in ring2], sum(ring2, V()) / 16 - d * 0.12, 'metal_dark', d)
    e.extend(ex)
    out.append(Part(f'exhaust_{num}', f'engine_{num}', pivot=sum(ring1, V()) / 16 + d * 0.05, info={'kind': 'ir_source'}))
    return out


UV_DARK, UV_LIGHT, UV_HUB, UV_STEEL = (0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)
PROP_CELLS = {UV_DARK: (0.085, 0.088, 0.095), UV_LIGHT: (0.50, 0.51, 0.53), UV_HUB: (0.34, 0.35, 0.37), UV_STEEL: (0.16, 0.16, 0.17)}


def write_prop_texture(path):
    """64 x 64 PNG: composite blade grey, leading-edge / tip erosion strip, spinner grey, steel (same cell layout as the B-17G prop)."""
    import bpy
    n = 64
    im = bpy.data.images.new('msbprop', n, n, alpha=False)
    px = [0.0] * (n * n * 4)
    for (u, v), col in PROP_CELLS.items():
        x0, y0 = int((u - 0.25) * n), int((v - 0.25) * n)
        for y in range(y0, y0 + n // 2):
            for x in range(x0, x0 + n // 2):
                k = (y * n + x) * 4
                px[k:k + 4] = [col[0], col[1], col[2], 1.0]
    im.pixels = px
    im.filepath_raw = path; im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def _smooth(table, x):
    """Catmull-Rom through (x, v) rows (smooth planform / thickness laws; clamped at the ends)."""
    xs = [a for a, _ in table]; vs = [b for _, b in table]
    if x <= xs[0]:
        return vs[0]
    if x >= xs[-1]:
        return vs[-1]
    k = max(i for i in range(len(xs) - 1) if xs[i] <= x)
    t = (x - xs[k]) / (xs[k + 1] - xs[k])
    p0 = vs[max(k - 1, 0)]; p1 = vs[k]; p2 = vs[k + 1]; p3 = vs[min(k + 2, len(vs) - 1)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


BLADE_SECT = 22          # points round each section (cosine-spaced chord stations, closed trailing edge)
BLADE_ST = 26            # radial stations


def blade_sections(R=S.PROP_R):
    """1.9.1 scimitar propfan blade (coordinator: the 1.9.0 blades looked twisted and crumpled). Sections = NACA-4 thickness on a 2 %
    camber line, pitch axis at 40 % chord, closed trailing edge; one consistent twist law beta = atan(0.70 / r) + 4 deg (61 deg at the
    root, 26 at the tip), smooth Catmull-Rom planform (max chord 0.32 m at r 0.85) and thickness (30 % -> 5 %), scimitar sweep in the
    plane of rotation (the leading edge set back, against the motion, by 0.30 m at the tip), round shank (r 0.055) blended into the
    airfoil between r 0.38 and 0.52. Local frame: +Z radial, rotation toward +X, +Y forward (axial). Returns (rings, chord-station of each
    ring point) for the loft and the leading-edge strip."""
    chord_t = [(0.30, 0.11), (0.38, 0.11), (0.50, 0.22), (0.65, 0.29), (0.85, 0.32), (1.05, 0.31), (1.25, 0.28), (1.42, 0.23), (1.55, 0.17), (1.64, 0.11), (1.70, 0.05)]
    tc_t = [(0.30, 0.30), (0.50, 0.30), (0.65, 0.16), (0.85, 0.10), (1.20, 0.07), (1.70, 0.05)]
    n = BLADE_SECT
    th = [2 * math.pi * k / n for k in range(n)]
    xcs = [(1 + math.cos(a)) / 2 for a in th]                      # 1 = TE (k 0), 0 = LE (k n/2)
    rs = [0.30 + (R - 0.30) * (1 - math.cos(math.pi / 2 * t)) ** 0.9 for t in [k / (BLADE_ST - 1) for k in range(BLADE_ST)]]
    rs = sorted(set(round(r, 4) for r in rs) | {round(M.COWL['r_spin'] - 0.015, 4)})      # a station on the spinner surface (joined, connectivity)
    rings = []
    for r in rs:
        c = _smooth(chord_t, r); tc = _smooth(tc_t, r)
        b = math.atan(0.70 / r) + math.radians(4.0)
        sw = 0.30 * ((r - 0.60) / (R - 0.60)) ** 2 if r > 0.60 else 0.0
        w = min(max((r - 0.38) / 0.14, 0.0), 1.0); w = w * w * (3 - 2 * w)
        tdir = V((math.cos(b), math.sin(b), 0)); ndir = V((-math.sin(b), math.cos(b), 0))
        pts = []
        for a, xc in zip(th, xcs):
            up = 1.0 if math.sin(a) > 1e-9 else (-1.0 if math.sin(a) < -1e-9 else 0.0)
            yt = 5 * tc * (0.2969 * math.sqrt(max(xc, 0.0)) - 0.1260 * xc - 0.3516 * xc ** 2 + 0.2843 * xc ** 3 - 0.1036 * xc ** 4)
            yc = 0.02 / 0.16 * (0.8 * xc - xc * xc) if xc < 0.4 else 0.02 / 0.36 * (0.2 + 0.8 * xc - xc * xc)     # NACA camber m 0.02, p 0.4
            sa = (0.40 - xc) * c                                    # along the chord, + toward the leading edge
            na = (yc + up * yt) * c
            ca, cn = -math.cos(a) * 0.055, math.sin(a) * 0.055           # shank circle in the same parameter (k 0 = trailing side, as the airfoil)
            sa, na = ca * (1 - w) + sa * w, cn * (1 - w) + na * w
            pts.append(V((0, 0, r)) + tdir * sa + ndir * na + V((-sw, 0, 0)))
        rings.append(pts)
    return rings, xcs, rs


def blade_mesh(R=S.PROP_R):
    """one blade (see blade_sections); UV cells: dark blade, light leading-edge erosion strip (outer 3/4) and tip band, steel root cap."""
    mb = MeshBuf()
    rings, xcs, rs = blade_sections(R)
    n = len(rings[0])
    nf0 = len(mb.faces)
    loft(mb, rings, 'pr_hsprop', smooth=True)
    for idx, f in enumerate(mb.faces[nf0:]):
        i, j = divmod(idx, n)
        r = (rs[i] + rs[i + 1]) / 2; xc = min(xcs[j], xcs[(j + 1) % n])
        f['uv'] = [UV_LIGHT if (r > 1.58 or (xc < 0.07 and r > 0.55)) else UV_DARK] * len(f['idx'])
    n0 = len(mb.faces)
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / n + V((0, 0, 0.004)), 'pr_hsprop', V((0, 0, 1)))
    fan_cap(mb, rings[0], sum(rings[0], V()) / n, 'pr_hsprop', V((0, 0, -1)))
    for k, f in enumerate(mb.faces[n0:]):
        f['uv'] = [UV_LIGHT if k < n else UV_STEEL] * len(f['idx'])
    return mb


def _spinner(c_back, c_front, r_back, r_front, tip=None, N=36):
    """spinner section (UV_HUB): a body of revolution about +Y from c_back to c_front (and a pointed tip ahead when tip is given)."""
    mb = MeshBuf()
    ax = V((0, 1, 0))
    prof = [(0.0, r_back), (1.0, r_front)]
    pts = [(c_back.lerp(c_front, t), r) for t, r in prof]
    if tip is not None:
        L = (tip - c_front).length
        for t in (0.25, 0.5, 0.7, 0.85, 0.95):
            pts.append((c_front + ax * (L * t), r_front * (1 - t ** 1.8) ** 0.75))
    rings = [circle_pts(p, ax, max(r, 0.002), N) for p, r in pts]
    loft(mb, rings, 'pr_hsprop')
    if tip is not None:
        fan_cap(mb, rings[-1], tip, 'pr_hsprop', ax)
    else:
        fan_cap(mb, rings[-1], pts[-1][0], 'pr_hsprop', ax)     # closed band (hidden inside the front spinner)
    fan_cap(mb, rings[0], pts[0][0], 'pr_hsprop', -ax)
    for f in mb.faces:
        f['uv'] = [UV_HUB] * len(f['idx'])
    return mb


def props(kind, side):
    """two 6-blade rows: prop_hub_n (front row: spinner front + tip) under prop_n, prop_hub_n_aft (aft row: spinner band) under
    prop_n_aft; blades prop_hub_n[_aft]_bladeK (children of the hub, local +Z radial). The aft row's blades are mirrored (it turns the
    other way). Origins ON the shaft axis."""
    num = S.ENGINE_NUM[(side, kind)]
    xa, za, ylip, yprop, R, yend, zb = S.NACELLES[kind]
    ya, yf, ytip = M.prop_planes(kind)
    out = []
    rs = M.COWL['r_spin']
    for row, y, hub, parent in (('front', yf, f'prop_hub_{num}', f'prop_{num}'), ('aft', ya, f'prop_hub_{num}_aft', f'prop_{num}_aft')):
        c = V((xa * side, y, za))
        if row == 'aft':
            sp = _spinner(V((c.x, ya - 0.19, za)), V((c.x, ya + 0.245, za)), rs - 0.003, rs - 0.012)
        else:
            sp = _spinner(V((c.x, ya + 0.25, za)), V((c.x, yf + 0.18, za)), rs - 0.012, rs - 0.030, tip=V((c.x, ytip, za)))
        out.append(Part(hub, parent, pivot=c, mesh=sp, info={'kind': 'prop_hub', 'row': row, 'spin_axis': 'local +Y (Unity +Z)'}))
        bm = blade_mesh()
        if M.ROW_TURN[row] < 0:
            mir = MeshBuf()
            mir.verts = [V((-p.x, p.y, p.z)) for p in bm.verts]
            mir.faces = [dict(f, idx=list(reversed(f['idx'])), uv=(list(reversed(f['uv'])) if f.get('uv') else f.get('uv'))) for f in bm.faces]
            bm = mir
        nb = S.PROP_BLADES
        for k in range(nb):
            ang = 2 * math.pi * k / nb + math.radians(15 if row == 'front' else 45)
            q = Quaternion(V((0, 1, 0)), ang)
            mb = MeshBuf()
            mb.verts = [c + q @ p for p in bm.verts]
            mb.faces = [dict(f) for f in bm.faces]
            out.append(Part(f'{hub}_blade{k + 1}', hub, pivot=c, mesh=mb, frame=q, info={'kind': 'blade', 'row': row}))
    return out


# ============================================================================================ engine internals (turboshaft)
def _bar(mb, a, b, w, h, up, mat='structure'):
    NS.sec_tube(mb, a, b, w, h, up, mat=mat)


def engine_internals(kind, side):
    """(engine mb, nacelle mb): reduction gearbox behind the spinner, turboshaft core (compressor case, combustor, turbine) along the axis
    (inboard: raised over the main-gear well), tubular mounts to the firewall ring, exhaust duct to the stub; firewall disc + oil tank."""
    import b17g_nacelle as N
    xa, za, ylip, yprop, R, yend, zb = S.NACELLES[kind]
    x = xa * side
    e, n_ = MeshBuf(), MeshBuf()
    cylinder(e, V((x, ylip + 0.40, za)), V((x, ylip + 0.05, za)), 0.30, 0.34, N=24, mat='engine')          # reduction gearbox
    cylinder(e, V((x, ylip + 0.05, za)), V((x, ylip - 0.10, za)), 0.34, 0.26, N=24, mat='engine')
    zc = za if kind == 'outer' else 0.60
    yc0, yc1 = ylip - 0.10, (ylip - 2.10 if kind == 'outer' else 1.90)
    cylinder(e, V((x, ylip - 0.10, za)), V((x, ylip - 0.30, zc)), 0.14, 0.14, N=16, mat='metal_dark')       # shaft housing
    rc = 0.27 if kind == 'outer' else 0.19
    cylinder(e, V((x, ylip - 0.30, zc)), V((x, ylip - 0.95, zc)), rc, rc * 0.93, N=24, mat='engine')         # compressor case
    cylinder(e, V((x, ylip - 0.95, zc)), V((x, ylip - 1.35, zc)), rc * 1.04, rc * 1.04, N=24, mat='exhaust')   # combustor
    cylinder(e, V((x, ylip - 1.35, zc)), V((x, yc1, zc)), rc * 0.95, rc * 0.80, N=24, mat='exhaust')          # turbine / jet pipe
    for k in range(6):                                                                                         # bands
        yy = ylip - 0.40 - k * 0.20
        cylinder(e, V((x, yy, zc)), V((x, yy - 0.025, zc)), rc * 1.07, N=24, mat='metal_dark')
    yfw = 3.735 if kind == 'inner' else ylip - 0.30
    ring = circle_pts(V((x, yfw + 0.02, zc)), V((0, 1, 0)), rc + 0.12, 12)
    for a, b in zip(ring, ring[1:] + ring[:1]):
        _bar(e, a, b, 0.03, 0.03, (a - V((x, yfw, zc))), 'engine')
    for k in range(0, 12, 2):
        p = ring[k]; q = V((x, ylip - 0.70, zc)) + (p - V((x, p.y, zc))).normalized() * (rc + 0.01)
        _bar(e, p, q, 0.028, 0.028, V((0, 0, 1)), 'engine')
    rs, top, bot = N.nac_profile(kind, yfw)
    cz = (top + bot) / 2
    fw = [V((x + (rs - 0.045) * math.cos(2 * math.pi * k / 24), yfw, cz + ((top - bot) / 2 - 0.045) * math.sin(2 * math.pi * k / 24))) for k in range(24)]
    fc = sum(fw, V()) / 24
    fan_cap(n_, fw, fc, 'structure', V((0, 1, 0)))
    fan_cap(n_, [p - V((0, 0.006, 0)) for p in fw], fc - V((0, 0.006, 0)), 'structure', V((0, -1, 0)))
    yo = yfw - 0.32
    zo = 0.52 if kind == 'inner' else za + 0.12
    cylinder(n_, V((x - 0.28, yo, zo + (0.18 if kind == 'outer' else 0.0))), V((x + 0.28, yo, zo + (0.18 if kind == 'outer' else 0.0))), 0.11, N=14, mat='metal_dark')
    return e, n_


# ============================================================================================ bay, carry-through, side bays, pylons
def bay_extras(root):
    """bay hardpoint empties (all five) + the wing carry-through box over the bay roof (front / rear spar caps, shear webs, ribs)."""
    out = []
    for name, p in M.BAY_HP.items():
        out.append(Part(name, root, pivot=V(p), info={'kind': 'hardpoint', 'options': list(M.STORES.get(name, {}))}))
    mb = MeshBuf()
    import b17g_parts as P
    st = P.wing_station(1.02)
    yf = st.point(0.18, True).y; yr = st.point(0.62, True).y
    z0, z1 = S.BAY_ROOF_Z + 0.04, S.BAY_ROOF_Z + 0.52
    xs = min(P.fus_skin_x(y_, z_, 0.0) for y_ in (yf, yr) for z_ in (z0, z1)) - 0.004      # spar webs end on the skin (connectivity)
    for yy in (yf, yr):
        box(mb, (0, yy, (z0 + z1) / 2), (2 * xs, 0.05, z1 - z0), 'structure')
        for zz in (z0 + 0.02, z1 - 0.02):
            box(mb, (0, yy, zz), (2 * xs, 0.16, 0.04), 'structure')
    for xx in (-0.90, -0.45, 0.0, 0.45, 0.90):
        box(mb, (xx, (yf + yr) / 2, z1 - 0.02), (0.04, yf - yr, 0.04), 'structure')
        box(mb, (xx, (yf + yr) / 2, z0 + 0.02), (0.04, yf - yr, 0.04), 'structure')
    out.append(Part('carry_through', root, mesh=mb, info={'kind': 'structure', 'note': 'wing carry-through box over the 5.7 m bay'}))
    return out


def side_bays(door_meshes):
    """door_meshes: {'L': MeshBuf, 'R': MeshBuf} of the side-bay skin faces taken out of fus_waist. -> liners (fus_waist), doors hinged at
    their top edge (open 100 deg up-out), hardpoints hp_def_L / hp_def_R (rolled so the mount's down points outboard)."""
    out = []
    sb = M.SIDE_BAY
    y0, y1 = sb['y']; z0, z1 = sb['z']
    for side, sx in (('L', -1), ('R', 1)):
        dm = door_meshes.get(side)
        if dm is None or not dm.faces:
            continue
        NS.double_skin(dm, t=0.006, mats=('paint',), inner=lambda f, c: 'interior')
        top = max(dm.verts, key=lambda p: p.z)
        hz = max(p.z for p in dm.verts)
        hx = max(abs(p.x) for p in dm.verts if abs(p.z - hz) < 0.05) * sx
        out.append(Part(f'side_bay_door_{side}', 'fus_waist', pivot=V((hx, (y0 + y1) / 2, hz)), mesh=dm,
                        info={'kind': 'bay_door', 'hinge_axis': [0, 1, 0], 'open_deg': -100 * sx}))
        # liner: back wall at |x| 0.56, top / bottom / end walls out to the skin
        lm = MeshBuf()
        import b17g_parts as P
        xi = sb['liner_x']
        ys = [y0 + (y1 - y0) * k / 10 for k in range(11)]
        for ya, yb in zip(ys, ys[1:]):
            q = [V((sx * xi, ya, z0)), V((sx * xi, yb, z0)), V((sx * xi, yb, z1)), V((sx * xi, ya, z1))]
            oriented_quad(lm, q, 'structure', V((sx, 0, 0)))
            oriented_quad(lm, [p - V((sx * 0.004, 0, 0)) for p in q], 'structure', V((-sx, 0, 0)))
            for zz, d in ((z0, 1), (z1, -1)):
                xa_ = P.fus_skin_x(ya, zz, 0.012); xb_ = P.fus_skin_x(yb, zz, 0.012)
                q = [V((sx * xi, ya, zz)), V((sx * xi, yb, zz)), V((sx * xb_, yb, zz)), V((sx * xa_, ya, zz))]
                oriented_quad(lm, q, 'structure', V((0, 0, d)))
                oriented_quad(lm, [p - V((0, 0, d * 0.004)) for p in q], 'structure', V((0, 0, -d)))
        for yy, d in ((y0, 1), (y1, -1)):
            zs = [z0 + (z1 - z0) * k / 6 for k in range(7)]
            for za_, zb_ in zip(zs, zs[1:]):
                q = [V((sx * xi, yy, za_)), V((sx * P.fus_skin_x(yy, za_, 0.012), yy, za_)), V((sx * P.fus_skin_x(yy, zb_, 0.012), yy, zb_)), V((sx * xi, yy, zb_))]
                oriented_quad(lm, q, 'structure', V((0, d, 0)))
                oriented_quad(lm, [p - V((0, d * 0.004, 0)) for p in q], 'structure', V((0, -d, 0)))
        for k in range(1, 5):          # launch rails / ribs on the back wall
            yy = y0 + (y1 - y0) * k / 5
            box(lm, (sx * (xi + 0.02), yy, (z0 + z1) / 2), (0.03, 0.03, z1 - z0 - 0.02), 'structure')
        out.append(Part(f'side_bay_liner_{side}', 'fus_waist', mesh=lm, info={'kind': 'bay'}))
        q = frame_quat(V((0, 1, 0)), V((-sx, 0, 0)))       # mount 'down' (-up) = outboard
        out.append(Part(f'hp_def_{side}', 'fus_waist', pivot=V((sx * sb['hp_x'], sb['hp_y'], sb['hp_z'])), frame=q,
                        info={'kind': 'hardpoint', 'options': ['AAM1_double_internal', 'AAM3_double_internal'], 'rolled': 'down = outboard'}))
    return out


def pylons():
    """4 pylons under the wing, outboard of the outer prop discs: streamlined blade + sway-brace plate, hardpoint empty at the bottom."""
    import b17g_parts as P
    out = []
    for kind, ax in M.PYLONS.items():
        for side, s in ((-1, 'L'), (1, 'R')):
            x = ax * side
            st = P.wing_station(ax, side)
            ylo = st.point(0.30, False)
            zw = min(st.point(f, False).z for f in (0.12, 0.2, 0.3, 0.4, 0.5))
            L = M.PYLON_LEN[kind]
            yc = st.point(0.30, False).y + 0.10
            zt, zb = zw + 0.05, zw - M.PYLON_DROP
            mb = MeshBuf()
            secs = []
            for k in range(9):
                t = k / 8
                y = yc + L / 2 - L * t
                hw = 0.075 * math.sin(math.pi * min(max(t, 0.03), 0.97)) ** 0.6 + 0.004
                secs.append([V((x - hw, y, zt)), V((x - hw, y, zb + 0.03)), V((x - hw * 0.6, y, zb)), V((x + hw * 0.6, y, zb)), V((x + hw, y, zb + 0.03)), V((x + hw, y, zt))])
            loft(mb, secs, 'paint', closed=False)
            fan_cap(mb, secs[0], sum(secs[0], V()) / 6, 'paint', V((0, 1, 0)))
            fan_cap(mb, secs[-1], sum(secs[-1], V()) / 6, 'paint', V((0, -1, 0)))
            box(mb, (x, yc, zb - 0.012), (0.18, 0.70, 0.024), 'metal_dark')
            for yy in (yc + 0.25, yc - 0.25):
                box(mb, (x, yy, zb - 0.04), (0.30, 0.04, 0.03), 'metal_dark')
            part = 'wing_outer_' + s
            out.append(Part(f'pylon_{kind}_{s}', part, mesh=mb, info={'kind': 'pylon'}))
            out.append(Part(f'hp_{kind}_{s}', part, pivot=V((x, yc, zb - 0.025)), info={'kind': 'hardpoint'}))
    return out


# ============================================================================================ sensors, antennas, dispensers
def sensors():
    """EO/IR targeting ball under the forward fuselage (keel), blade antennas, missile-warning sensor domes, flare dispenser panels."""
    out = []
    import b17g_parts as P
    # EO/IR ball on a short stalk under the keel fairing, behind the chin turret (fus_cockpit)
    c = V((0.0, 4.72, -0.97))
    mb = MeshBuf()
    bot = S.fus_station(c.y)[1]
    cylinder(mb, V((c.x, c.y, bot + 0.008)), c + V((0, 0, 0.12)), 0.13, 0.12, N=24, mat='paint')     # stalk top 8 mm inside the belly skin (joined, connectivity)
    rr = sphere_rings(c, 0.16, (V((1, 0, 0)), V((0, 0, -1)), V((0, 1, 0))), [10, 25, 45, 70, 90, 110, 135, 160, 175], 32)
    loft(mb, rr, 'paint')
    fan_cap(mb, rr[0], c + V((0, 0, -0.16)), 'paint', V((0, 0, -1)))
    fan_cap(mb, rr[-1], c + V((0, 0, 0.16)), 'paint', V((0, 0, 1)))
    w = [c + V((0.16 * 0.98 * math.cos(a) * 0 + 0.07 * math.cos(a), 0.152, -0.02 + 0.06 * math.sin(a))) for a in [2 * math.pi * k / 16 for k in range(16)]]
    fan_cap(mb, w, sum(w, V()) / 16 + V((0, 0.004, 0)), 'glass', V((0, 1, 0)))
    w2 = [c + V((0.11 + 0.025 * math.cos(a), 0.11, 0.02 + 0.025 * math.sin(a))) for a in [2 * math.pi * k / 12 for k in range(12)]]
    fan_cap(mb, w2, sum(w2, V()) / 12 + V((0.004, 0.004, 0)), 'glass', V((0.6, 0.8, 0)))
    out.append(Part('eo_ball', 'fus_cockpit', mesh=mb, info={'kind': 'sensor', 'type': 'EO/IR targeting ball'}))
    # blade antennas (top behind the dorsal laser, belly forward of the bay, top of the tail cone)
    for name, part, y, top_ in (('ant_top_1', 'B17G', 0.90, True), ('ant_top_2', 'fus_waist', -7.00, True), ('ant_belly_1', 'B17G', 2.70, False)):
        t_, b_, hw_, n_ = S.fus_station(y)
        z = t_ if top_ else b_
        sgn = 1 if top_ else -1
        mb = MeshBuf()
        prof = [V((0, y + 0.12, z - sgn * 0.01)), V((0, y - 0.14, z - sgn * 0.01)), V((0, y - 0.20, z + sgn * 0.26)), V((0, y - 0.09, z + sgn * 0.27))]
        for dx_ in (-0.008, 0.008):
            oriented_quad(mb, [p + V((dx_, 0, 0)) for p in prof], 'paint', V((math.copysign(1, dx_), 0, 0)))
        for a_, b2 in zip(prof, prof[1:] + prof[:1]):
            oriented_quad(mb, [a_ + V((-0.008, 0, 0)), b2 + V((-0.008, 0, 0)), b2 + V((0.008, 0, 0)), a_ + V((0.008, 0, 0))], 'paint', (a_ + b2) / 2 - sum(prof, V()) / 4)
        out.append(Part(name, part, mesh=mb, info={'kind': 'antenna'}))
    # missile-warning sensor domes: 2 on the nose sides, 2 on the tail cone sides, 1 under the tail (small glass domes on a dark base)
    mws = [('mws_nose_L', 'fus_nose', -1, 5.40, 0.30), ('mws_nose_R', 'fus_nose', 1, 5.40, 0.30), ('mws_tail_L', 'fus_tail', -1, -12.40, 0.70),
           ('mws_tail_R', 'fus_tail', 1, -12.40, 0.70)]
    for name, part, sx, y, z in mws:
        xs = P.fus_skin_x(y, z, 0.0)
        cc = V((sx * xs, y, z))
        nrm = V((sx, 0, 0))
        mb = MeshBuf()
        cylinder(mb, cc - nrm * 0.01, cc + nrm * 0.025, 0.065, 0.06, N=18, mat='metal_dark')
        rr = [circle_pts(cc + nrm * (0.025 + 0.04 * math.sin(math.radians(a))), nrm, 0.055 * math.cos(math.radians(a)) + 1e-3, 18) for a in (0, 30, 55, 75)]
        loft(mb, rr, 'glass')
        fan_cap(mb, rr[-1], cc + nrm * 0.068, 'glass', nrm)
        out.append(Part(name, part, mesh=mb, info={'kind': 'sensor', 'type': 'missile warning'}))
    # flare dispensers: 4 dark panels with cartridge holes on the lower aft fuselage (fus_waist), FlareEjector points in Unity
    for sx in (-1, 1):
        for k, y in enumerate((-8.05, -8.35)):
            mb = MeshBuf()
            t_, b_, hw_, n_ = S.fus_station(y)
            z = b_ + 0.22
            xs = P.fus_skin_x(y, z, 0.0)
            nrm = V((sx * 0.8, 0, -0.6)).normalized()
            cc = V((sx * xs, y, z)) + nrm * 0.004
            u = V((0, 1, 0)); v = nrm.cross(u).normalized()
            q = [cc + u * 0.13 + v * 0.06, cc - u * 0.13 + v * 0.06, cc - u * 0.13 - v * 0.06, cc + u * 0.13 - v * 0.06]
            oriented_quad(mb, q, 'metal_dark', nrm)
            oriented_quad(mb, [p - nrm * 0.006 for p in q], 'metal_dark', -nrm)
            for a_, b_ in zip(q, q[1:] + q[:1]):
                oriented_quad(mb, [a_, b_, b_ - nrm * 0.006, a_ - nrm * 0.006], 'metal_dark', (a_ + b_) / 2 - cc)
            for i in range(5):
                for j in range(2):
                    pc = cc + nrm * 0.002 + u * (-0.10 + 0.05 * i) + v * (-0.025 + 0.05 * j)
                    fan_cap(mb, circle_pts(pc, nrm, 0.014, 8), pc, 'cove', nrm)
            out.append(Part(f'flare_disp_{"L" if sx < 0 else "R"}{k + 1}', 'fus_waist', mesh=mb, info={'kind': 'dispenser'}))
    return out
