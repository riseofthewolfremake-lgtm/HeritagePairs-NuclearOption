"""FD-32 round 6 (docs/fd32_design.md 19): semi-retractable main gear (legs swing straight back about the lateral axis from a pivot
under the lower wing), the hook slot computed from the hook's swept envelope + its lined channel, and the spinner fairing that closes
the waist between the cowl ring and the fal spinner cone. Used by fd32_parts.py (which patches the Mk I generator in memory).
"""
import math
from mathutils import Matrix
from b25h_geom import V, MeshBuf, cylinder, oriented_quad, fan_cap
import nimrod_spec as S
import nimrod_structure as ST
import nimrod_parts as NP
import nimrod_v140 as N4
import fd32_spec as FS


# =========================================================================================== main gear
def wing_under_z(x, y):
    """z of the lower wing's underside at span |x|, station y (Blender), from the Mk I lower-wing aerofoil"""
    st = NP.lo_station(abs(x), 1)
    te_y = (st.le + st.cdir * st.chord).y
    sc = min(max((st.le.y - y) / (st.le.y - te_y), 0.0), 1.0)
    return NP.surf_pt(st, sc, False).z


def gear_pivot(side):
    """leg pivot BELOW the lower wing, GEAR_PIVOT_BELOW under its underside at (GEAR_LEG_X, GEAR_PIVOT_Y)"""
    x = FS.GEAR_LEG_X
    return V((side * x, FS.GEAR_PIVOT_Y, wing_under_z(x, FS.GEAR_PIVOT_Y) - FS.GEAR_PIVOT_BELOW))


def lname(side):
    return 'L' if side < 0 else 'R'


def main_gear(side):
    """single cantilever oleo leg in the plane GEAR_LEG_X (inboard of the tyre), raked forward from its pivot under the lower wing down
    to the Mk I axle; swings straight aft about the lateral axis (LandingGear fold). Returns (strut mesh, wheel mesh, axle, pivot)."""
    ax = V((side * S.MAIN_AXLE[0], S.MAIN_AXLE[1], S.MAIN_AXLE[2]))
    root = gear_pivot(side)
    st = MeshBuf()
    foot = V((side * FS.GEAR_LEG_X, ax.y, ax.z))                     # leg foot on the axle line, inboard of the tyre
    d = (foot - root).normalized()
    mid = root.lerp(foot, 0.52)
    cylinder(st, root, mid, 0.048, N=14, mat='metal_dark')                         # oleo cylinder
    cylinder(st, mid - d * 0.02, foot, 0.034, N=14, mat='alu')                     # sliding piston
    cylinder(st, foot - d * 0.03, foot + d * 0.03, 0.045, N=14, mat='metal_dark')  # axle knuckle
    cylinder(st, foot, ax + V((side * 0.02, 0, 0)), 0.030, N=12, mat='metal_dark') # axle stub
    cylinder(st, root - V((side * 0.050, 0, 0)), root + V((side * 0.050, 0, 0)), 0.052, N=16, mat='metal_dark')   # trunnion barrel (coaxial)
    pin_in = V((side * (FS.GEAR_MOUNT_X[1] + 0.006), root.y, root.z))              # trunnion pin into the mount boss (coaxial, 6 mm gap)
    cylinder(st, pin_in, root, 0.024, N=12, mat='metal_dark')
    NP.attach(f'gear_main_{lname(side)}_strut', pin_in, [f'gear_mount_{lname(side)}'])
    wh = MeshBuf()
    NP.wheel_from_prop(wh, ax, S.WHEEL_R, 0.155, mirror=side < 0)
    return st, wh, ax, root


def gear_mount(side):
    """the fixed trunnion mount under the lower wing, inboard of the leg: a lug plate from 15 mm inside the wing underside down round
    the pivot, plus a boss on the pivot axis (coaxial with the leg's trunnion: the turning leg never reaches it). Part of the lower wing."""
    mb = MeshBuf()
    piv = gear_pivot(side)
    x0, x1 = FS.GEAR_MOUNT_X
    xa, xb = side * x0, side * x1
    ys = [piv.y + 0.13 - 0.26 * k / 10 for k in range(11)]

    def bottom(y):
        t = (y - piv.y) / 0.13
        return piv.z - 0.072 * math.sqrt(max(1 - t * t, 0.0)) - 0.004

    def top_(x, y):
        return wing_under_z(abs(x), y) + 0.015
    for x_, out_ in ((xa, -side), (xb, side)):
        ring = [V((x_, y, top_(x_, y))) for y in ys] + [V((x_, y, bottom(y))) for y in reversed(ys)]
        c = sum(ring, V()) / len(ring)
        for k in range(len(ring)):
            tri = [c, ring[k], ring[(k + 1) % len(ring)]]
            if (tri[1] - tri[0]).cross(tri[2] - tri[0]).length > 1e-10:
                oriented_quad(mb, tri, 'metal_dark', V((out_, 0, 0)))
    for y0_, y1_ in zip(ys, ys[1:]):
        q = [V((xa, y0_, top_(xa, y0_))), V((xb, y0_, top_(xb, y0_))), V((xb, y1_, top_(xb, y1_))), V((xa, y1_, top_(xa, y1_)))]
        oriented_quad(mb, q, 'metal_dark', V((0, 0, 1)))
        q = [V((xa, y0_, bottom(y0_))), V((xb, y0_, bottom(y0_))), V((xb, y1_, bottom(y1_))), V((xa, y1_, bottom(y1_)))]
        oriented_quad(mb, q, 'metal_dark', V((0, 0, -1)))
    for y_ in (ys[0], ys[-1]):
        q = [V((xa, y_, top_(xa, y_))), V((xb, y_, top_(xb, y_))), V((xb, y_, bottom(y_))), V((xa, y_, bottom(y_)))]
        oriented_quad(mb, q, 'metal_dark', V((0, 1 if y_ > piv.y else -1, 0)))
    cylinder(mb, V((side * (x0 - 0.012), piv.y, piv.z)), V((side * x1, piv.y, piv.z)), 0.040, N=16, mat='metal_dark')   # pivot boss
    NP.attach(f'gear_mount_{lname(side)}', V((side * (x0 + x1) / 2, piv.y, wing_under_z((x0 + x1) / 2, piv.y))), [f'wing_lower_{lname(side)}'])
    return mb, V((side * (x0 + x1) / 2, piv.y, piv.z))


def _frame(a, b):
    a = a.normalized(); b = (b - a * a.dot(b)).normalized()
    return Matrix((a, b, a.cross(b))).transposed()


def fold_axis_angle(side):
    """round 7: the single rotation (axis through the pivot, angle in deg) that takes the leg to lie flat aft along the wing-root
    underside (GEAR_STOW_BETA outboard of straight aft) with the axle pointing straight DOWN (the wheel flat under the wing). Blender
    frame; the left side is the mirror image."""
    P = gear_pivot(side)
    foot = V((side * FS.GEAR_LEG_X, S.MAIN_AXLE[1], S.MAIN_AXLE[2]))
    b = math.radians(FS.GEAR_STOW_BETA)
    d = V((side * math.sin(b), -math.cos(b), 0.0))
    R = _frame(V((0, 0, -1)), d) @ _frame(V((side, 0, 0)), foot - P).inverted()
    q = R.to_quaternion()
    return V(q.axis), math.degrees(q.angle)


def fold_matrix(side, frac=1.0):
    """4x4 world rotation of the main leg at `frac` of its swing (about its pivot, tilted axis)"""
    p = gear_pivot(side)
    ax, ang = fold_axis_angle(side)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(ang * frac), 4, ax) @ Matrix.Translation(-p)


# =========================================================================================== hook slot from the swept envelope
def hook_sweep(hook_mb, n=24):
    """hook mesh vertices at n+1 poses from stowed to deployed (pre-stretch frame; the whole swing lies aft of the stretch cut)"""
    p0 = V(S.HOOK_PIVOT)
    out = []
    for k in range(n + 1):
        a = -math.radians((S.HOOK_DEPLOY - S.HOOK_STOW_UP) * k / n)    # 'up' angles: tip down = +rotation about +X for an aft bar
        R = Matrix.Rotation(a, 3, 'X')
        out.append([p0 + R @ (V(v) - p0) for v in hook_mb.verts])
    return out


SLOT = {}


def hook_slot(hook_mb):
    """belly slot = every point of the swept hook that comes within 30 mm of (or below) the fuselage bottom: y range and half width
    + margins. Sets nimrod_parts.SLOT_Y / SLOT_HW (pre-stretch) before the fuselage is built."""
    ys, xs = [], []
    for pose in hook_sweep(hook_mb):
        for v in pose:
            if not (min(r[0] for r in S.FUS) < v.y < max(r[0] for r in S.FUS)):
                continue
            zb = ST.fus_z(0.0, v.y, top=False)
            if v.z < zb + 0.10:
                ys.append(v.y); xs.append(abs(v.x))
    y0, y1 = max(ys) + 0.06, min(ys) - 0.06
    allx = [abs(v.x) for pose in hook_sweep(hook_mb, 4) for v in pose]
    hw = max(max(xs) + 0.04, max(allx) + 0.015)
    NP.SLOT_Y = (y0, y1)
    NP.SLOT_HW = hw
    SLOT.update(y0=y0, y1=y1, hw=hw, stow=hook_sweep(hook_mb, 1)[0], ych=V(S.HOOK_PIVOT).y + 0.10)
    return y0, y1, hw


def hook_channel():
    """dark lined channel over the slot: two walls from the belly up to a roof 30 mm above the stowed hook, the roof and the end walls,
    each a closed 3 mm slab. Pre-stretch frame; part of fus_rear."""
    mb = MeshBuf()
    y0, y1, hw = SLOT['ych'], SLOT['y1'], SLOT['hw']        # the channel runs from ahead of the hinge to the slot's aft end
    stow = SLOT['stow']
    ztop = max(v.z for v in stow)

    def roof(y):
        sel = [v.z for v in stow if abs(v.y - y) < 0.10]
        return min((max(sel) if sel else ztop) + 0.03, ST.fus_z(0.0, y, top=True) - 0.04)

    def low(y):
        return ST.fus_z(min(hw, 0.9 * ST.fus_params(y)[0]), y, top=False) - 0.004
    n = 24
    yy = [y0 + (y1 - y0) * k / n for k in range(n + 1)]

    def slab(q, nrm, t=0.003):
        oriented_quad(mb, q, 'cove', nrm)
        q2 = [p - nrm.normalized() * t for p in q]
        oriented_quad(mb, q2, 'cove', -nrm)
        c = sum(q, V()) / 4
        for i in range(4):                                     # closed edges (a ray never enters the slab between its faces)
            j = (i + 1) % 4
            e = [q[i], q[j], q2[j], q2[i]]
            if (e[1] - e[0]).length > 1e-6:
                oriented_quad(mb, e, 'cove', (q[i] + q[j]) / 2 - c)
    for a_, b_ in zip(yy, yy[1:]):
        for sx in (-1, 1):
            slab([V((sx * hw, a_, low(a_))), V((sx * hw, b_, low(b_))), V((sx * hw, b_, roof(b_))), V((sx * hw, a_, roof(a_)))], V((-sx, 0, 0)))
        slab([V((-hw, a_, roof(a_))), V((hw, a_, roof(a_))), V((hw, b_, roof(b_))), V((-hw, b_, roof(b_)))], V((0, 0, -1)))
    for y_, d in ((y0, -1), (y1, 1)):
        slab([V((-hw, y_, low(y_))), V((hw, y_, low(y_))), V((hw, y_, roof(y_))), V((-hw, y_, roof(y_)))], V((0, d, 0)))
    return mb


# =========================================================================================== spinner fairing
FAIR_Y0 = 2.383          # 3 mm ahead of the cowl front ring (y 2.38, r 0.333)
FAIR_R0 = 0.330


def spinner_fairing(mb, cone_y, cone_r):
    """closed, rotating fairing from the cowl ring to the base of the fal spinner cone (no waist: shot 98)"""
    L = cone_y - FAIR_Y0
    prof = [(0.02, 0.0), (FAIR_R0, 0.0), (FAIR_R0 + 0.002, 0.012)]
    for k in range(1, 7):
        t = k / 6
        r = FAIR_R0 + 0.002 + (cone_r - FAIR_R0 - 0.002) * (t * t * (3 - 2 * t))
        prof.append((r, 0.012 + (L - 0.012) * t))
    prof.append((0.02, L))
    N4.lathe(mb, prof, V((0, FAIR_Y0, 0)), V((0, 1, 0)), 'metal_dark', N=40, cap0=True, cap1=True, ref=V((0, 0, 1)))
