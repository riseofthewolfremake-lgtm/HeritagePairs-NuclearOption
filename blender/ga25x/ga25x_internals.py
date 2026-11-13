"""GA-25X 1.8.3: an engine body behind the turboprop cowl (user review 2026-11-07 item 9: 'all aircraft still lack internal parts';
stock aircraft carry their engines inside the engine part, seen at the break-off face).

Until 1.8.2 the engine part was a closed ogive cowl, the chin intake and the shoulder exhaust outlets with nothing inside. This adds,
inside the cowl (so the outside look and the engine part's convex collider are unchanged): the reduction gearbox behind the spinner,
the intake plenum fed by the chin duct, the compressor / combustor / turbine core, the motor-generator drum at the firewall, the mount
ring with six struts, and the two exhaust stubs up to the shoulder outlets. Materials: 'structure' (the stock aircraft_structure in
game, StockStructure.cs) and 'metal_dark'.
"""
import math
from mathutils import Vector as V
import b25h_spec as S
from b25h_geom import MeshBuf, cylinder, circle_pts, fan_cap, box

FWD = V((0, 1, 0))


def _cowl_r(y, cx, rings_fn):
    """smallest distance from the prop axis to the cowl skin at station y (rings_fn(y) -> ring points)."""
    ring = rings_fn(y)
    return min(math.hypot(p.x - cx, p.z) for p in ring)


def cowl_ring_at_fn(side):
    """the cowl ring at station y, exactly as ga25x_visual.build_turboprop lofts it (base nacelle section -> lip circle, f = t^1.12)."""
    import ga25x_visual as VX
    from b25h_geom import superellipse_ring
    P = VX._P()
    cx = side * S.NAC_X
    N = P.NAC_N
    hw0, zb0, zt0, n0 = P.nac_params(S.FIREWALL_Y)
    cz0 = (zb0 + zt0) / 2
    base = superellipse_ring(cx, 0, cz0, hw0 + 0.003, (zt0 - cz0) + 0.003, (cz0 - zb0) + 0.003, n=n0, N=N)
    def ring(y):
        t = (y - (S.FIREWALL_Y - 0.02)) / (VX.COWL_LIP_Y - S.FIREWALL_Y + 0.02)
        t = max(0.0, min(1.0, t)); f = t ** 1.12
        return [V((p.x, y, p.z)).lerp(V((cx + VX.COWL_LIP_R * math.sin(2 * math.pi * j / N), y, VX.COWL_LIP_R * math.cos(2 * math.pi * j / N))), f)
                for j, p in enumerate(base)]
    return ring


def turboprop_core(side, cowl_ring_at=None):
    """mesh of the engine body (world space, rest pose) for the engine part of `side`. cowl_ring_at(y) gives the cowl ring at y."""
    cx = side * S.NAC_X
    cowl_ring_at = cowl_ring_at or cowl_ring_at_fn(side)
    mb = MeshBuf()
    ax = lambda y: V((cx, y, 0.0))
    def fit(y, r):          # never closer than 4 cm to the cowl skin
        return min(r, _cowl_r(y, cx, cowl_ring_at) - 0.04)
    # reduction gearbox (behind the spinner) and the propeller shaft housing
    cylinder(mb, ax(2.58), ax(2.30), fit(2.58, 0.17), fit(2.30, 0.23), N=20, mat='structure')
    cylinder(mb, ax(2.60), ax(2.54), 0.08, 0.10, N=14, mat='metal_dark')
    # intake plenum (annular, fed by the chin duct below) and its screen
    cylinder(mb, ax(2.30), ax(2.12), fit(2.30, 0.26), fit(2.12, 0.27), N=24, mat='structure')
    for k in range(12):
        a = 2 * math.pi * k / 12
        d = V((math.sin(a), 0, math.cos(a)))
        box(mb, ax(2.21) + d * fit(2.21, 0.27), (0.012, 0.16, 0.012), 'metal_dark')
    # compressor case (two diameters + a flange ring), combustor, turbine
    cylinder(mb, ax(2.12), ax(1.96), fit(2.12, 0.22), fit(1.96, 0.21), N=24, mat='structure')
    cylinder(mb, ax(1.97), ax(1.95), fit(1.96, 0.24), N=24, mat='metal_dark')
    cylinder(mb, ax(1.96), ax(1.80), fit(1.96, 0.25), fit(1.80, 0.25), N=24, mat='structure')
    cylinder(mb, ax(1.80), ax(1.70), fit(1.80, 0.23), fit(1.70, 0.21), N=24, mat='metal_dark')
    # motor-generator drum at the firewall
    cylinder(mb, ax(1.70), ax(1.645), fit(1.70, 0.30), N=24, mat='structure')
    # rear baffle / engine-side firewall: closes the cowl annulus behind the motor-generator (the engine's break-off face shows it)
    yb = S.FIREWALL_Y + 0.012
    outer = [V((p.x, yb, p.z)).lerp(V((cx, yb, 0.0)), 0.0) for p in cowl_ring_at(yb)]
    outer = [V((cx, yb, 0.0)) + (q - V((cx, yb, 0.0))) * (1 - 0.012 / max((q - V((cx, yb, 0.0))).length, 0.05)) for q in outer]
    inner = [V((cx, yb, 0.0)) + (q - V((cx, yb, 0.0))).normalized() * fit(1.70, 0.30) * 0.98 for q in outer]
    from b25h_geom import annulus
    annulus(mb, outer, inner, 'structure', V((0, -1, 0)))
    annulus(mb, [q + V((0, 0.004, 0)) for q in outer], [q + V((0, 0.004, 0)) for q in inner], 'structure', V((0, 1, 0)))
    for k in range(8):           # stiffeners on the baffle
        a_ = 2 * math.pi * (k + 0.5) / 8
        d = V((math.sin(a_), 0, math.cos(a_)))
        q0 = V((cx, yb - 0.006, 0.0)) + d * fit(1.70, 0.30)
        q1 = V((cx, yb - 0.006, 0.0)) + d * (_cowl_r(yb, cx, cowl_ring_at) - 0.03)
        box(mb, (q0 + q1) / 2, (0.02, 0.012, 0.02), 'metal_dark') if (q1 - q0).length < 0.03 else cylinder(mb, q0, q1, 0.012, N=6, mat='metal_dark')
    # mount ring + six struts from the firewall to the compressor flange
    ring = circle_pts(ax(1.66), FWD, fit(1.66, 0.40), 12)
    for a_, b_ in zip(ring, ring[1:] + ring[:1]):
        cylinder(mb, a_, b_, 0.02, N=6, mat='structure')
    fl = circle_pts(ax(1.96), FWD, fit(1.96, 0.24), 6)
    for k in range(6):
        cylinder(mb, ring[2 * k], fl[k], 0.018, N=6, mat='structure')
    # exhaust stubs from the turbine to under the shoulder outlets (the outlets themselves are the exhaust part)
    for s in (-1, 1):
        th = s * 0.72
        d = V((math.sin(th), 0, math.cos(th)))
        p0 = ax(1.76) + d * 0.20
        p1 = ax(1.92) + d * max(0.24, fit(1.92, 0.40))
        cylinder(mb, p0, p1, 0.07, 0.06, N=12, mat='metal_dark')
    return mb
