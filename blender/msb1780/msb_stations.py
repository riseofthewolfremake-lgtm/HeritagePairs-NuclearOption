"""MSB-17/80 1.9.1 crew stations (offline worker, coordinator review of 1.9.0: the flat pilot panel, a floating WSO console and a slab EWO
console were not acceptable; memory kitbash-stock-parts / check-own-screenshots-and-stock-refs).

  flight deck: the STOCK EW-25 two-pilot glass cockpit (tub with panel, MFD glass, glare shield, centre pedestal, side consoles and floor;
      its wide tac screen; its sticks and throttle) is placed in Unity on the anchors made here (msb_spec.STOCK_KIT); ours is only what the
      EW-25 tub does not have in a B-17 hull: the aft platform at the tub's floor level (EWO area), the bay-front bulkhead and an overhead
      switch console between the two escape hatches.
  WSO (glazed nose): floor at the stock seat's base level, seat base with rails, side consoles (left / right), lower side liners, and an
      instrument panel on two posts ahead of the knees with two screens (Unity: tac page + stock dark glass); the feet go under the panel.
  EWO (behind the flight deck, facing the right wall): a console bank - knee-well desk with a keyboard tray, a tilted screen panel with two
      bezelled screens (Unity: tac page + dark glass), an equipment rack above, a rack below the desk behind the feet, end cheeks; every
      piece kept aft of the EW-25 tub's rear frame (y 2.944).
Closed solids are separate objects (cockpit_wso_console / _side_L / _side_R / _seatbase, cockpit_ewo_*) so the nose-closed check can skip
points inside furniture by object; floors and liners are double-faced quads.
"""
import math
from mathutils import Vector as V
import b17g_spec as S
import msb_spec as M
from b25h_geom import MeshBuf, oriented_quad, cylinder, box
from b25h_parts import Part


OVERHEAD_Y = (2.97, 3.36)     # 1.9.2: aft of the pilot eyes (y 3.45), ahead of the EWO hatch (y 2.62-2.93)
OVERHEAD_W = 0.24

def wall_x(y, z, inset=0.02):
    import b17g_parts as P
    return P.fus_skin_x(y, z, inset)


def dquad(mb, q, mat, n):
    """double-faced quad (thin panel: both faces front from their side)."""
    n = V(n)
    oriented_quad(mb, q, mat, n)
    oriented_quad(mb, [p - n.normalized() * 0.006 for p in q], mat, -n)


def bezel(mb, c, right, up, n, w, h, t=0.018):
    """screen bezel: four bars round a w x h opening centred at c (in the plane right / up, facing n), soft keys under it."""
    import nimrod_structure as NS
    corners = [c - right * (w / 2 + t / 2) - up * (h / 2 + t / 2), c + right * (w / 2 + t / 2) - up * (h / 2 + t / 2),
               c + right * (w / 2 + t / 2) + up * (h / 2 + t / 2), c - right * (w / 2 + t / 2) + up * (h / 2 + t / 2)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        NS.sec_tube(mb, a + n * 0.006, b + n * 0.006, t, 0.012, n, mat='ck_bezel')
    for k in range(5):
        p = c - right * (w / 2) + right * ((k + 0.5) * w / 5) - up * (h / 2 + t + 0.016) + n * 0.008
        box(mb, tuple(p), (0.024, 0.012, 0.012), 'ck_bezel')


def screen(name, parent, c, right, up, n, w, h):
    sm = MeshBuf()
    q = [c - right * (w / 2) - up * (h / 2), c + right * (w / 2) - up * (h / 2), c + right * (w / 2) + up * (h / 2), c - right * (w / 2) + up * (h / 2)]
    oriented_quad(sm, [p + n * 0.004 for p in q], 'screen', n)
    for f in sm.faces:
        f['uv'] = [(0, 0), (1, 0), (1, 1), (0, 1)]
    return Part(name, parent, mesh=sm, info={'kind': 'screen', 'w': w, 'h': h})


# ============================================================================================ flight deck (around the stock tub)
def bay_bulkhead(mb):
    """bay-front bulkhead from the bay roof up (both faces) - shared by the 1.9.1 deck and the 1.9.5 deck (msb_deck195)."""
    y_back = S.BAY_Y[1] + 0.03
    top = S.fus_station(y_back)[0]
    zs = [M.FLOOR_Z + (top - 0.03 - M.FLOOR_Z) * k / 14 for k in range(15)]
    for za, zb in zip(zs, zs[1:]):
        wa, wb = wall_x(y_back - 0.02, za), wall_x(y_back - 0.02, zb)
        q = [V((-wa, y_back - 0.02, za)), V((wa, y_back - 0.02, za)), V((wb, y_back - 0.02, zb)), V((-wb, y_back - 0.02, zb))]
        oriented_quad(mb, q, 'ck_wall', V((0, 1, 0)))
        oriented_quad(mb, [p + V((0, -0.025, 0)) for p in q], 'ck_wall', V((0, -1, 0)))


def overhead_part():
    """overhead switch console between the pilots' escape hatches (x +-0.17; the seat columns rise at |x| 0.24-0.52)
    1.9.2 (coordinator, sheet_cockpit r2: the 1.9.1 console y 3.32-4.12, 0.34 wide, 0.12 + 0.03 deep hung in the top of the pilots' view):
    smaller (0.24 wide, 0.055 deep, switches 0.012 long), moved up flush under the roof and aft to y 2.97-3.36, behind the pilot eyes (y 3.45),
    ahead of the EWO hatch (y 2.62-2.93); the escape hatches (|x| >= 0.17) and the seat columns stay clear (check s). 1.9.5: unchanged."""
    oh = MeshBuf()
    y0, y1 = OVERHEAD_Y
    n = 6
    for k in range(n):
        ya, yb = y0 + (y1 - y0) * k / n, y0 + (y1 - y0) * (k + 1) / n
        zt = min(S.fus_station(ya)[0], S.fus_station(yb)[0]) - 0.03
        box(oh, (0, (ya + yb) / 2, zt - 0.0275), (OVERHEAD_W, yb - ya + 0.002, 0.055), 'ck_panel')
        box(oh, (0, (ya + yb) / 2, zt - 0.0575), (OVERHEAD_W - 0.04, (yb - ya) * 0.75, 0.005), 'ck_black')          # switch panel face
        for j in range(3):
            xx = -0.06 + 0.06 * j
            cylinder(oh, V((xx, (ya + yb) / 2, zt - 0.059)), V((xx, (ya + yb) / 2, zt - 0.071)), 0.006, N=8, mat='ck_bezel')
    for sx in (-1, 1):                            # two hangers to the roof frame
        for yy in (y0 + 0.04, y1 - 0.04):
            zt = S.fus_station(yy)[0]
            box(oh, (sx * 0.08, yy, zt - 0.015), (0.025, 0.025, 0.04), 'ck_bezel')
    return Part('cockpit_overhead', 'fus_cockpit', mesh=oh, info={'kind': 'cockpit'})


def flight_deck():
    """1.9.1 deck pieces around the stock EW-25 tub (M.STOCK_DECK): aft platform + bay bulkhead + overhead console."""
    out = []
    mb = MeshBuf()
    y_back = S.BAY_Y[1] + 0.03
    zd = M.DECK_Z
    y_tub = M.STOCK_TUB_BOX[1][0] + 0.03          # platform runs 3 cm under the tub's rear edge (no slit)
    ys = [y_back + (y_tub - y_back) * k / 8 for k in range(9)]
    for ya, yb in zip(ys, ys[1:]):                # aft platform at the tub floor level (the EWO's floor), wall to wall
        wa, wb = wall_x(ya, zd, 0.02), wall_x(yb, zd, 0.02)
        dquad(mb, [V((-wa, ya, zd)), V((wa, ya, zd)), V((wb, yb, zd)), V((-wb, yb, zd))], 'ck_floor', V((0, 0, 1)))
    bay_bulkhead(mb)
    out.append(Part('cockpit_interior', 'fus_cockpit', mesh=mb, info={'kind': 'cockpit'}))
    out.append(overhead_part())
    return out


# ============================================================================================ EWO console bank
def ewo_station():
    out = []
    ex, ey, ez = M.EYE_EWO
    zd = M.DECK_Z
    ya, yb = ey - 0.34, min(ey + 0.14, M.STOCK_TUB_BOX[1][0] - 0.02)    # aft of the tub's rear frame
    ym = (ya + yb) / 2
    desk_z, x_desk = 1.12, (0.72 if getattr(M, 'DECK195', False) else 0.60)    # 1.9.5: the stock seat's armrests reach x 0.689 (check t2)
    xw = lambda z: wall_x(ym, z, 0.03)
    # desk (knee well under it), front lip, keyboard tray
    d = MeshBuf()
    box(d, ((x_desk + xw(desk_z)) / 2, ym, desk_z - 0.02), (xw(desk_z) - x_desk, yb - ya, 0.04), 'ck_panel')
    cylinder(d, V((x_desk, ya, desk_z - 0.02)), V((x_desk, yb, desk_z - 0.02)), 0.022, N=12, mat='ck_black')
    box(d, (x_desk + 0.13, ym, desk_z + 0.008), (0.20, yb - ya - 0.10, 0.016), 'ck_black')
    for k in range(6):
        box(d, (x_desk + 0.07 + 0.024 * k, ym, desk_z + 0.019), (0.012, yb - ya - 0.16, 0.006), 'ck_bezel')
    out.append(Part('cockpit_ewo_desk', 'B17G', mesh=d, info={'kind': 'cockpit'}))
    # tilted screen panel above the desk, facing the eye
    p0 = V((0.82, 0, desk_z + 0.06)); p1 = V((min(0.96, xw(1.80) - 0.05), 0, 1.80))
    u = (p1 - p0).normalized(); nrm = V((-u.z, 0, u.x)).normalized()
    if nrm.x > 0:
        nrm = -nrm
    pm = MeshBuf()
    q = [V((p0.x, ya, p0.z)), V((p0.x, yb, p0.z)), V((p1.x, yb, p1.z)), V((p1.x, ya, p1.z))]
    oriented_quad(pm, q, 'ck_panel', nrm)
    oriented_quad(pm, [p - nrm * 0.03 for p in q], 'ck_panel', -nrm)
    for a, b in ((q[0], q[1]), (q[1], q[2]), (q[2], q[3]), (q[3], q[0])):                # closed edges
        oriented_quad(pm, [a, b, b - nrm * 0.03, a - nrm * 0.03], 'ck_panel', (a + b) / 2 - (q[0] + q[2]) / 2)
    right = V((0, 1, 0)); up = u
    sw, sh = 0.22, 0.20
    yc = [ya + 0.03 + sw / 2 + 0.01, yb - 0.03 - sw / 2 - 0.01]
    for k, y_ in enumerate(yc):
        t = 0.40
        c = V((p0.x + (p1.x - p0.x) * t, y_, p0.z + (p1.z - p0.z) * t))
        bezel(pm, c, right, up, nrm, sw, sh)
        out.append(screen(f'cockpit_screen_ewo{k + 1}', 'cockpit_ewo_panel', c, right, up, nrm, sw, sh))
    out.append(Part('cockpit_ewo_panel', 'B17G', mesh=pm, info={'kind': 'cockpit'}))
    # equipment rack above the panel (where the wall still has room), rack under the desk behind the feet, end cheeks
    r = MeshBuf()
    zr0, zr1 = 1.84, 1.98
    xr0 = p1.x - 0.02
    if wall_x(ym, zr1, 0.03) - xr0 > 0.06:
        box(r, ((xr0 + wall_x(ym, zr1, 0.03)) / 2, ym, (zr0 + zr1) / 2), (wall_x(ym, zr1, 0.03) - xr0, yb - ya, zr1 - zr0), 'ck_panel')
        box(r, ((xr0 + wall_x(ym, zr1, 0.03)) / 2 - 0.01, ym, zr0 - 0.004), (wall_x(ym, zr1, 0.03) - xr0 - 0.04, yb - ya - 0.06, 0.008), 'ck_black')
    xl0 = 1.04
    if xw(0.9) - xl0 > 0.05:
        box(r, ((xl0 + xw(0.9)) / 2, ym, (zd + 1.06) / 2), (xw(0.9) - xl0, yb - ya, 1.06 - zd), 'ck_panel')
        for k in range(3):
            box(r, (xl0 - 0.004, ym, zd + 0.10 + 0.13 * k), (0.008, yb - ya - 0.08, 0.09), 'ck_black')
    out.append(Part('cockpit_ewo_rack', 'B17G', mesh=r, info={'kind': 'cockpit'}))
    c_ = MeshBuf()
    for yy, sg in ((ya - 0.012, -1), (yb + 0.012, 1)):
        zs = [zd + (1.92 - zd) * k / 10 for k in range(11)]
        for za, zb in zip(zs, zs[1:]):
            q = [V((0.58, yy, za)), V((wall_x(yy, za, 0.03), yy, za)), V((wall_x(yy, zb, 0.03), yy, zb)), V((0.58, yy, zb))]
            dquad(c_, q, 'ck_wall', V((0, sg, 0)))
    out.append(Part('cockpit_ewo_cheeks', 'B17G', mesh=c_, info={'kind': 'cockpit'}))
    return out


# ============================================================================================ WSO station (glazed nose)
def wso_station():
    out = []
    wx, wy, wz = M.EYE_WSO
    zf = M.NOSE_FLOOR_Z
    # floor from the nose bulkhead to under the feet (double-faced), lower side liners up to z 0.50
    f = MeshBuf()
    ys = [5.40 + 0.10 * k for k in range(16)]
    for ya, yb in zip(ys, ys[1:]):
        wa, wb = wall_x(ya, zf, 0.02), wall_x(yb, zf, 0.02)
        if min(wa, wb) < 0.12:
            continue
        dquad(f, [V((-wa, ya, zf)), V((wa, ya, zf)), V((wb, yb, zf)), V((-wb, yb, zf))], 'ck_floor', V((0, 0, 1)))
    for sx in (-1, 1):
        for ya, yb in zip(ys[:12], ys[1:13]):
            zs = [zf + (0.50 - zf) * k / 4 for k in range(5)]
            for za, zb in zip(zs, zs[1:]):
                q = [V((sx * wall_x(ya, za, 0.035), ya, za)), V((sx * wall_x(yb, za, 0.035), yb, za)), V((sx * wall_x(yb, zb, 0.035), yb, zb)), V((sx * wall_x(ya, zb, 0.035), ya, zb))]
                dquad(f, q, 'ck_wall', V((-sx, 0, 0)))
    out.append(Part('cockpit_wso_floor', 'fus_nose', mesh=f, info={'kind': 'cockpit'}))
    # seat base with two rails (the stock ejection seat's base sits at ~z 0.13)
    sb = MeshBuf()
    if getattr(M, 'DECK195', False):     # 1.9.5: the stock seat's base sits at eye - 1.027 (0.108): a 4 mm plate + two 3 mm rails under it
        box(sb, (0, wy + 0.02, zf + 0.002), (0.46, 0.44, 0.004), 'ck_black')
        for sx in (-1, 1):
            box(sb, (sx * 0.16, wy + 0.02, zf + 0.0055), (0.04, 0.46, 0.003), 'ck_bezel')
    else:
        box(sb, (0, wy + 0.02, zf + 0.025), (0.46, 0.40, 0.05), 'ck_black')
        for sx in (-1, 1):
            box(sb, (sx * 0.16, wy + 0.02, zf + 0.06), (0.04, 0.44, 0.02), 'ck_bezel')
    out.append(Part('cockpit_wso_seatbase', 'fus_nose', mesh=sb, info={'kind': 'cockpit'}))
    # side consoles left / right (armrest height), switch panels on top
    for s, sx in (('L', -1), ('R', 1)):
        sc = MeshBuf()
        y0, y1, ztop, xin = wy - 0.30, wy + 0.42, 0.60, 0.34
        xo = min(wall_x(y0, 0.35, 0.04), wall_x(y1, 0.35, 0.04))
        if xo - xin > 0.06:
            box(sc, (sx * (xin + xo) / 2, (y0 + y1) / 2, (zf + ztop) / 2), (xo - xin, y1 - y0, ztop - zf), 'ck_panel')
            for k in range(4):
                yy = y0 + 0.10 + k * 0.17
                box(sc, (sx * (xin + xo) / 2, yy, ztop + 0.004), ((xo - xin) * 0.8, 0.12, 0.008), 'ck_black')
                for j in range(2):
                    xx = sx * (xin + 0.05 + 0.06 * j)
                    cylinder(sc, V((xx, yy, ztop + 0.008)), V((xx, yy, ztop + 0.03)), 0.009, N=8, mat='ck_bezel')
            out.append(Part(f'cockpit_wso_side_{s}', 'fus_nose', mesh=sc, info={'kind': 'cockpit'}))
    # instrument panel ahead of the knees on two posts (the feet go under it), tilted toward the eye, two bezelled screens
    pc = MeshBuf()
    yp, zb_, zt_ = wy + 0.62, 0.56, 0.96
    hw = min(0.36, wall_x(yp, zt_, 0.05), wall_x(yp, zb_, 0.05))
    tilt = math.radians(28)                      # top toward the nose
    u = V((0, math.sin(tilt), math.cos(tilt)))
    nrm = V((0, -math.cos(tilt), math.sin(tilt)))
    base = V((0, yp, zb_))
    L = (zt_ - zb_) / math.cos(tilt)
    q = [base + V((-hw, 0, 0)), base + V((hw, 0, 0)), base + V((hw, 0, 0)) + u * L, base + V((-hw, 0, 0)) + u * L]
    oriented_quad(pc, q, 'ck_panel', nrm)
    oriented_quad(pc, [p - nrm * 0.04 for p in q], 'ck_panel', -nrm)
    for a, b in ((q[0], q[1]), (q[1], q[2]), (q[2], q[3]), (q[3], q[0])):
        oriented_quad(pc, [a, b, b - nrm * 0.04, a - nrm * 0.04], 'ck_panel', (a + b) / 2 - (q[0] + q[2]) / 2)
    hood = [q[3], q[2], q[2] - nrm * 0.0 + V((0, -0.10, 0.03)), q[3] + V((0, -0.10, 0.03))]          # small glare hood
    dquad(pc, hood, 'ck_black', V((0, 0, 1)))
    for sx in (-1, 1):                                                                                # posts to the floor
        px = sx * (hw - 0.04)
        box(pc, (px, yp + 0.03, (zf + zb_) / 2), (0.04, 0.04, zb_ - zf), 'ck_bezel')
        box(pc, (px, yp + 0.03, zf + 0.01), (0.10, 0.10, 0.02), 'ck_bezel')
    box(pc, (0, yp + 0.03, zb_ - 0.03), (2 * hw - 0.06, 0.03, 0.03), 'ck_bezel')                       # cross bar under the panel
    right = V((1, 0, 0))
    sw, sh = 0.24, 0.18
    for k, xx in enumerate((-0.14, 0.14)):
        c = base + V((xx, 0, 0)) + u * (L * 0.48)
        bezel(pc, c, right, u, nrm, sw, sh)
        out.append(screen(f'cockpit_screen_wso{k + 1}', 'cockpit_wso_console', c, right, u, nrm, sw, sh))
    out.append(Part('cockpit_wso_console', 'fus_nose', mesh=pc, info={'kind': 'cockpit'}))
    return out


def stock_anchors():
    """empties where Unity places the stock EW-25 parts (identity frames: the stock meshes keep their own orientation)."""
    out = []
    for name, mesh, tpl, u in M.STOCK_KIT:
        out.append(Part(name, 'cockpit_interior', pivot=V(M.stock_pos(u)), info={'kind': 'stock_anchor', 'stock': mesh, 'template': tpl}))
    return out


def build():
    return flight_deck() + ewo_station() + wso_station() + stock_anchors()


def build_stations():
    """1.9.5: the WSO and EWO stations only (the flight deck is msb_deck195)."""
    return ewo_station() + wso_station()
