"""Interior parts of the B-25H v2 model: cockpit objects and compartment structure.

Cockpit pieces are separate objects under fus_cockpit (material `cockpit`, gauge faces `gauges`).
Compartment structure (gun bay, ammo, turret ring, bomb-bay racks, carry-through, radio/waist and
tail compartments) is appended to the mesh of the fuselage section it belongs to, so it breaks
away with that section.
"""
import math
from mathutils import Vector, Quaternion
import b25h_spec as S
from b25h_geom import V, MeshBuf, cylinder, box, tube, oriented_quad, circle_pts, annulus, loft, fan_cap
from b25h_parts import Part, fus_params, NOSE_GUN_XZ, CANNON_XZ
import b25h_parts as P

CK = 'cockpit'
FLOOR_Z = 0.10


def rot_x(deg):
    return Quaternion(V((1, 0, 0)), math.radians(deg))


def clip_poly(poly, x0, x1, z0, z1):
    def clip(pts, inside, inter):
        out = []
        for k in range(len(pts)):
            a, b = pts[k - 1], pts[k]
            ia, ib = inside(a), inside(b)
            if ib:
                if not ia:
                    out.append(inter(a, b))
                out.append(b)
            elif ia:
                out.append(inter(a, b))
        return out
    def lx(c):
        return lambda a, b: (c, a[1] + (b[1] - a[1]) * (c - a[0]) / (b[0] - a[0]))
    def lz(c):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (c - a[1]) / (b[1] - a[1]), c)
    pts = clip(poly, lambda p: p[0] >= x0, lx(x0))
    pts = clip(pts, lambda p: p[0] <= x1, lx(x1)) if pts else pts
    pts = clip(pts, lambda p: p[1] >= z0, lz(z0)) if pts else pts
    pts = clip(pts, lambda p: p[1] <= z1, lz(z1)) if pts else pts
    return pts


def section_panel(mb, y, rect, mat, inset=0.03, t=0.03):
    """flat bulkhead panel = fuselage inner section at y clipped to rect (x0,x1,z0,z1); closed slab."""
    from b25h_parts import fus_ring
    ring = [(p.x, p.z) for p in fus_ring(y, inset)]
    poly = clip_poly(ring, *rect)
    if len(poly) < 3:
        return
    cx = sum(p[0] for p in poly) / len(poly)
    cz = sum(p[1] for p in poly) / len(poly)
    for yy, sgn in ((y + t / 2, 1), (y - t / 2, -1)):
        for k in range(len(poly)):
            a, b = poly[k], poly[(k + 1) % len(poly)]
            oriented_quad(mb, [V((cx, yy, cz)), V((a[0], yy, a[1])), V((b[0], yy, b[1]))], mat, V((0, sgn, 0)))
    for k in range(len(poly)):
        a, b = poly[k], poly[(k + 1) % len(poly)]
        q = [V((a[0], y - t / 2, a[1])), V((b[0], y - t / 2, b[1])), V((b[0], y + t / 2, b[1])), V((a[0], y + t / 2, a[1]))]
        oriented_quad(mb, q, mat, V(((a[0] + b[0]) / 2 - cx, 0, (a[1] + b[1]) / 2 - cz)))


def build_cockpit():
    parts = []
    m = MeshBuf()
    y0, y1 = 2.66, 4.26                     # rear bulkhead .. instrument panel
    hw = 0.66
    # floor + crawl passage floor forward under the panel to the nose bulkhead
    box(m, (0, (y0 + y1) / 2, FLOOR_Z - 0.015), (2 * hw, y1 - y0, 0.03), CK)
    # side walls (lining) with frames and stringers
    for s in (-1, 1):
        box(m, (s * (hw + 0.005), (y0 + y1) / 2, 0.47), (0.01, y1 - y0, 0.74), CK)
        for y in (2.95, 3.35, 3.75, 4.10):
            box(m, (s * (hw - 0.025), y, 0.47), (0.04, 0.03, 0.74), CK)
        for z in (0.30, 0.60):
            box(m, (s * (hw - 0.015), (y0 + y1) / 2, z), (0.02, y1 - y0, 0.025), CK)
        # side consoles
        box(m, (s * (hw - 0.09), 3.45, 0.43), (0.16, 0.90, 0.12), CK)
        for k in range(4):
            cylinder(m, V((s * (hw - 0.09) + 0.03 * (k - 1.5), 3.25 + 0.15 * k, 0.49)),
                     V((s * (hw - 0.09) + 0.03 * (k - 1.5), 3.25 + 0.15 * k, 0.56)), 0.012, N=6, mat='metal_dark')
    # rear bulkhead with crawl doorway (|x| < 0.24, z < 1.05), shaped to the fuselage section
    for rect in ((-1.0, -0.24, FLOOR_Z, 2.0), (0.24, 1.0, FLOOR_Z, 2.0), (-0.24, 0.24, 1.05, 2.0)):
        section_panel(m, y0, rect, CK)
    # instrument panel: main panel slightly raked, centre section deeper, glare shield
    q = rot_x(-8)
    box(m, (0, y1, 0.70), (1.10, 0.04, 0.44), CK, rot=q)
    box(m, (0, y1 - 0.03, 0.42), (0.40, 0.10, 0.14), CK)          # lower centre (engine instruments)
    box(m, (0, y1 + 0.06, 0.945), (0.92, 0.20, 0.03), CK)         # glare shield top
    box(m, (0, y1 - 0.04, 0.93), (0.92, 0.04, 0.035), CK)          # shield lip
    # centre pedestal + throttle quadrant
    box(m, (0.0, 3.92, 0.36), (0.22, 0.46, 0.52), CK)
    box(m, (0.0, 3.95, 0.66), (0.26, 0.30, 0.10), CK)             # quadrant head
    for k, x in enumerate((-0.09, -0.03, 0.03, 0.09)):
        p0 = V((x, 3.95, 0.70))
        p1 = V((x, 3.86, 0.86))
        cylinder(m, p0, p1, 0.008, N=5, mat='metal_dark')
        box(m, p1, (0.025, 0.03, 0.03), 'metal_dark' if k % 2 else CK)
    # cannon breech cover / loader station on the right-aft (H: navigator-cannoneer)
    box(m, (0.38, 3.0, 0.30), (0.40, 0.40, 0.04), CK)               # folding table
    parts.append(Part('cockpit_interior', 'fus_cockpit', (0, 3.45, FLOOR_Z), m))
    # gauges: bezels on panel + flat faces with a 0-1 UV grid
    gb = MeshBuf()
    gf = MeshBuf()
    gpos = []
    for r, z in enumerate((0.84, 0.74, 0.64, 0.54)):
        for c, x in enumerate((-0.50, -0.40, -0.30, -0.20, -0.10)):
            gpos.append((x, z, 0.040))
    for r, z in enumerate((0.82, 0.70, 0.58)):
        for c, x in enumerate((0.05, 0.15, 0.25, 0.37, 0.48)):
            gpos.append((x, z, 0.036))
    for c, x in enumerate((-0.12, -0.04, 0.04, 0.12)):
        gpos.append((x, 0.43, 0.030))
    grid = 8
    for k, (x, z, r) in enumerate(gpos):
        # panel face plane (raked 8 deg): y = y1 - 0.02 - (z-0.78)*tan(8)
        yf = y1 - 0.021 - (z - 0.70) * math.tan(math.radians(8))
        n = V((0, -math.cos(math.radians(8)), math.sin(math.radians(8))))
        c = V((x, yf, z))
        # bezel ring
        ring_o = circle_pts(c + n * 0.012, n, r + 0.008, 12, ref=V((0, 0, 1)))
        ring_i = circle_pts(c + n * 0.012, n, r, 12, ref=V((0, 0, 1)))
        annulus(gb, ring_o, ring_i, CK, n)
        loft(gb, [circle_pts(c, n, r + 0.008, 12, ref=V((0, 0, 1))), ring_o], CK)
        # face quad (cell k of an 8x8 grid)
        cu, cv = (k % grid) / grid, (k // grid) / grid
        up = V((0, 0, 1))
        rt = n.cross(up).normalized() * -1
        upv = rt.cross(n).normalized() * -1
        pts = [c + n * 0.004 + (rt * sx + upv * sz) * r for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        uv = [(cu, cv), (cu + 1 / grid, cv), (cu + 1 / grid, cv + 1 / grid), (cu, cv + 1 / grid)]
        oriented_quad(gf, pts, 'gauges', n, uv)
    parts[-1].mesh.extend(gb)
    gauges = Part('cockpit_gauges', 'fus_cockpit', (0, y1, 0.70), gf, info=dict(note='gauge faces, own 0-1 UVs (8x8 grid) in `livery` slot'))
    gauges.own_uv = True
    parts.append(gauges)
    # pilot seat (left) with armoured back
    sm = MeshBuf()
    sx, sy = S.COCKPIT_EYE[0], 3.28
    cush = S.COCKPIT_EYE[2] - 0.65
    box(sm, (sx, sy, cush - 0.04), (0.46, 0.44, 0.08), CK)                     # cushion
    box(sm, (sx, sy, (FLOOR_Z + cush - 0.08) / 2), (0.36, 0.36, cush - 0.08 - FLOOR_Z), CK)   # pan/base
    box(sm, (sx, sy - 0.25, cush + 0.38), (0.50, 0.04, 0.80), 'metal_dark', rot=rot_x(-10))  # armour back
    box(sm, (sx, sy - 0.31, cush + 0.86), (0.30, 0.05, 0.22), 'metal_dark', rot=rot_x(-10))  # head armour
    for s in (-1, 1):
        box(sm, (sx + s * 0.24, sy, cush + 0.10), (0.03, 0.40, 0.20), CK)      # side rails / arm rests
    parts.append(Part('cockpit_seat_L', 'fus_cockpit', (sx, sy, cush), sm))
    rm = MeshBuf()
    rx = 0.36
    box(rm, (rx, 3.10, 0.38), (0.42, 0.40, 0.07), CK)
    box(rm, (rx, 3.10, (FLOOR_Z + 0.34) / 2), (0.30, 0.30, 0.34 - FLOOR_Z), CK)
    box(rm, (rx, 2.88, 0.75), (0.44, 0.04, 0.70), CK, rot=rot_x(-8))
    parts.append(Part('cockpit_seat_R', 'fus_cockpit', (rx, 3.10, 0.42), rm,
                      info=dict(note='navigator/cannoneer station (no co-pilot controls on the H)')))
    # yoke (pivot at column base hinge, local X = pitch axis)
    ym = MeshBuf()
    hinge = V((sx, 3.88, FLOOR_Z + 0.03))
    top = V((sx, 3.84, 0.72))
    cylinder(ym, hinge, top, 0.025, N=8, mat=CK)
    box(ym, hinge, (0.10, 0.08, 0.05), 'metal_dark')
    hub = top + V((0, -0.06, 0.02))
    cylinder(ym, top, hub, 0.03, N=8, mat='metal_dark')
    # ram's-horn wheel: arc of short cylinders
    prev = None
    for k in range(9):
        a = math.radians(-70 + 140 * k / 8)
        p = hub + V((0.17 * math.sin(a), 0, -0.06 + 0.11 * (1 - math.cos(a)) * -1 + 0.10))
        if prev is not None:
            cylinder(ym, prev, p, 0.016, N=6, mat=CK)
        prev = p
    for s in (-1, 1):
        g0 = hub + V((s * 0.16, 0, 0.13))
        cylinder(ym, g0, g0 + V((0, 0, 0.09)), 0.022, N=8, mat=CK)
    parts.append(Part('cockpit_yoke_L', 'fus_cockpit', hinge, ym,
                      info=dict(note='pitch: rotate about local X at the column hinge; roll: wheel about column (local Y-ish)')))
    pm = MeshBuf()
    pc = V((sx, 4.12, FLOOR_Z + 0.05))
    box(pm, pc, (0.36, 0.04, 0.04), 'metal_dark')
    for s in (-1, 1):
        box(pm, pc + V((s * 0.13, 0.0, 0.14)), (0.10, 0.03, 0.20), CK, rot=rot_x(15))
        cylinder(pm, pc + V((s * 0.13, 0, 0)), pc + V((s * 0.13, 0, 0.05)), 0.012, N=6)
    parts.append(Part('cockpit_rudder_pedals_L', 'fus_cockpit', pc, pm, info=dict(note='yaw bar: rotate about local Z')))
    return parts


def add_nose_compartment(nose_mesh, guns_mesh):
    """gun bodies, feed chutes, ammo boxes, mounting frame; cannon recoil/ammo in the cockpit floor area."""
    for x, z in NOSE_GUN_XZ:
        box(guns_mesh, (x, 4.82, z), (0.10, 0.62, 0.15), 'metal_dark')                # receiver
        box(guns_mesh, (x, 4.48, z - 0.02), (0.08, 0.14, 0.12), 'metal_dark')         # back plate
        # feed chute from the ammo box below
        a = V((x, 4.80, z - 0.08))
        b = V((x * 1.1, 4.70, 0.05))
        cylinder(guns_mesh, a, b, 0.035, N=6, mat='metal_dark')
    # mounting frame (fus_nose)
    box(nose_mesh, (0, 4.85, 0.32), (0.62, 0.60, 0.03), 'structure')
    for x in (-0.30, 0.30):
        box(nose_mesh, (x, 4.85, 0.06), (0.03, 0.50, 0.52), 'structure')
    # ammo boxes (4) below the guns
    for x in (-0.32, -0.11, 0.11, 0.32):
        box(nose_mesh, (x, 4.85, -0.10), (0.18, 0.42, 0.26), 'interior')
    # nose bulkhead behind the gun bay (at the nose/cockpit split) is the section frame ring


def add_cannon_bits(cockpit_mesh):
    x, z = CANNON_XZ
    # 21-round ready rack (3 x 7 shells) beside the breech, under the cockpit floor (left side)
    rack_x = -0.55
    box(cockpit_mesh, (rack_x, 3.05, -0.36), (0.20, 0.80, 0.42), 'interior')
    for r in range(3):
        for c in range(7):
            p = V((rack_x + 0.11, 2.72 + 0.11 * c, -0.50 + 0.13 * r))
            cylinder(cockpit_mesh, p, p + V((0.10, 0, 0)), 0.04, N=6, mat='structure')


def add_forward_compartment(fwd_mesh):
    # floor (navigator/turret compartment)
    box(fwd_mesh, (0, (2.62 + 1.30) / 2, FLOOR_Z - 0.015), (1.30, 1.26, 0.03), 'interior')   # 3 cm clear of the split planes
    # turret ring structure: ring + 4 posts + pedestal
    c = V(S.TURRET_C)
    rz = c.z - 0.16
    r_o = circle_pts(V((0, c.y, rz)), V((0, 0, 1)), 0.50, 28)
    r_i = circle_pts(V((0, c.y, rz)), V((0, 0, 1)), 0.42, 28)
    annulus(fwd_mesh, r_o, r_i, 'structure', V((0, 0, -1)))
    annulus(fwd_mesh, [p + V((0, 0, 0.05)) for p in r_o], [p + V((0, 0, 0.05)) for p in r_i], 'structure', V((0, 0, 1)))
    loft(fwd_mesh, [r_i, [p + V((0, 0, 0.05)) for p in r_i]], 'structure', outward=False)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        p = V((0.46 * math.cos(a), c.y + 0.46 * math.sin(a), rz))
        cylinder(fwd_mesh, p, V((p.x * 1.2, p.y, FLOOR_Z)), 0.025, N=6, mat='structure')
    # (v3: no central pedestal - the turret gunner's sling seat hangs from the rotating turret)
    if getattr(P, 'TURRET_ROUND_HOLE', False):
        # 1.8.13 r3: a trim ring on the roof round the dorsal drum (r 0.455-0.62, 4 mm proud) covers the cut edge of the round opening
        def roof_z(x, y):
            hw, zb, zt, rt, rb = P.fus_params(y)
            k = abs(x) - (hw - rt)
            return zt if k <= 0 else zt - rt + math.sqrt(max(0.0, rt * rt - k * k))
        # r4: 96 segments x 4 radial bands, 5 mm proud (one 48 x 1 band's straight edges sagged into the curved roof: a wavy seam)
        rads = [0.455, 0.50, 0.54, 0.58, 0.62]
        rr_ = [[V((p.x, p.y, roof_z(p.x, p.y) + 0.005)) for p in circle_pts(V((0, c.y, 0)), V((0, 0, 1)), r_, 96)] for r_ in rads]
        for ri, ro in zip(rr_, rr_[1:]):
            annulus(fwd_mesh, ro, ri, 'paint', V((0, 0, 1)))
            annulus(fwd_mesh, [q - V((0, 0, 0.003)) for q in ro], [q - V((0, 0, 0.003)) for q in ri], 'interior', V((0, 0, -1)))
    # package-gun ammo boxes inside the forward fuselage sides (behind the blisters)
    for s in (-1, 1):
        box(fwd_mesh, (s * 0.52, 2.20, -0.25), (0.22, 0.55, 0.40), 'interior')


def add_center_compartment(ctr_mesh, wing_root_station):
    st = wing_root_station
    # wing carry-through: front + rear spar caps crossing the fuselage (visible from inside / bay)
    for s in (0.15, 0.62):
        up = st.point(s, True)
        lo = st.point(s, False)
        y = (up.y + lo.y) / 2
        box(ctr_mesh, (0, y, (up.z + lo.z) / 2), (1.40, 0.07, max(up.z - lo.z - 0.04, 0.1)), 'structure')
        for zz in (up.z - 0.03, lo.z + 0.03):
            box(ctr_mesh, (0, y, zz), (1.40, 0.16, 0.03), 'structure')
    # bomb-bay racks: vertical beams with shackle points, both sides; catwalk; transverse frames
    hx = S.BAY_HALF_X - 0.06
    for s in (-1, 1):
        for y in (0.58, -0.02, -0.62):
            box(ctr_mesh, (s * hx, y, 0.10), (0.05, 0.10, 1.84), 'structure')
            for z in (-0.55, -0.22, 0.11, 0.44, 0.77):
                box(ctr_mesh, (s * (hx - 0.05), y, z), (0.07, 0.06, 0.05), 'metal_dark')
        box(ctr_mesh, (s * hx, -0.02, 0.99), (0.05, 1.40, 0.05), 'structure')
    box(ctr_mesh, (0, -0.02, -0.30), (0.26, 1.50, 0.03), 'interior')          # catwalk
    for y in (0.68, -0.84):
        box(ctr_mesh, (0, y, 0.18), (1.18, 0.04, 0.06), 'structure')
        box(ctr_mesh, (0, y, 1.00), (1.18, 0.04, 0.05), 'structure')


def add_rear_compartment(rear_mesh):
    # floor
    for y0, y1 in ((-1.90, -3.90), (-3.90, -5.90)):
        zb = fus_params((y0 + y1) / 2)[1]
        fz = max(-0.42, zb + 0.30)
        hw = fus_params(y1)[0] - 0.12
        box(rear_mesh, (0, (y0 + y1) / 2, fz), (2 * hw, abs(y1 - y0), 0.03), 'interior')
    # radio rack (fwd right), crew bench (right), ammo boxes at waist positions, gun cradles
    box(rear_mesh, (0.45, -2.15, 0.10), (0.30, 0.40, 0.95), 'interior')
    box(rear_mesh, (0.42, -4.80, -0.22), (0.30, 1.00, 0.06), 'interior')
    for y in (-4.40, -5.20):
        box(rear_mesh, (0.42, y, -0.33), (0.25, 0.04, 0.18), 'structure')
    for side, (ya, yb) in ((-1, S.WAIST_L_Y), (1, S.WAIST_R_Y)):
        yc = (ya + yb) / 2
        hw = fus_params(yc)[0]
        # (v3: the waist gun sits in a ball socket in the hatch glass; no floor cradle)
        box(rear_mesh, (side * (hw - 0.22), yc - side * 0.56, -0.25), (0.22, 0.30, 0.26), 'interior')  # ammo (r2: 0.11 further from the hatch, clear of the AN/M2 receiver at 40 deg)


def add_tail_compartment(tail_mesh):
    box(tail_mesh, (0, -8.55, -0.04), (0.60, 1.60, 0.03), 'interior')          # floor
    # (v3: tail gunner seat is its own object, crew_seat_tail)
    for s in (-1, 1):
        box(tail_mesh, (s * 0.24, -7.55, 0.10), (0.18, 0.40, 0.26), 'interior')  # ammo boxes
        p0 = V((s * 0.20, -7.75, 0.20))
        p1 = V((s * 0.16, -8.60, 0.30))
        p2 = V((s * 0.16, -8.95, 0.33))             # 1.8.13 r2: chutes end clear of the AN/M2 receivers' sweep (were to -9.20 at the trunnion line)
        cylinder(tail_mesh, p0, p1, 0.03, N=6, mat='metal_dark')               # feed tracks
        cylinder(tail_mesh, p1, p2, 0.03, N=6, mat='metal_dark')


def build_interior(holes, parts_by_name=None):
    return build_cockpit()
