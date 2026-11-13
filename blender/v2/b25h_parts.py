"""Exterior parts of the B-25H v2 model. Everything is generated procedurally from b25h_spec.

Each builder returns Part objects (world-space meshes in the REST pose; see Part docstring).
"""
import math
from mathutils import Vector, Quaternion, Matrix
import b25h_spec as S
from b25h_geom import (V, MeshBuf, ring_arc_uv, interp_table, rr_ring, rr_category, RR_N, RR_HALF, superellipse_ring,
                       circle_pts, arc_lengths, loft, fan_cap, annulus, oriented_quad, cylinder, tube, box,
                       planar_uv, Station, surface, box_ring, aft_ring, section_cap, frame_from_axes, naca_pts,
                       cos_space, ear_clip, lerp)


class Part:
    """A scene object.
    mesh: MeshBuf in WORLD coordinates, in the closed/rest configuration.
    pivot: world position of the object origin (hinge / axle / spin centre).
    frame: Quaternion, orientation of the object's local axes in world (rest).
    pose: Quaternion applied about the local axes for the pose stored in the file (e.g. open doors).
    info: dict for the parts table (hinge axis, angles, notes)."""

    def __init__(self, name, parent, pivot=(0, 0, 0), mesh=None, frame=None, pose=None, info=None):
        self.name, self.parent = name, parent
        self.pivot = V(pivot)
        self.mesh = mesh
        self.frame = frame if frame is not None else Quaternion()
        self.pose = pose if pose is not None else Quaternion()
        self.info = info or {}
        self.uv_group = name          # livery islands only weld within one group


def mirror_x(p, side):
    return V((p[0] * side, p[1], p[2]))


# =============================================================================== fuselage
def fus_params(y):
    """(hw, zb, zt, rt, rb) at station y."""
    if y > S.NOSE_BASE_Y:
        L = S.NOSE_TIP_Y - S.NOSE_BASE_Y
        d = max(S.NOSE_TIP_Y - y, 0.0)
        e = math.sqrt(max(0.0, 1 - (1 - d / L) ** 2))
        hw0, zb0, zt0, rtf = S.FUS_TABLE[0][1:]
        et = e ** 0.85     # slightly fuller top line
        hw = hw0 * e
        zt = S.NOSE_TIP_Z + (zt0 - S.NOSE_TIP_Z) * et
        zb = S.NOSE_TIP_Z + (zb0 - S.NOSE_TIP_Z) * e
        return hw, zb, zt, rtf * hw, S.RB_FACTOR * hw
    tab = sorted([(r[0], r[1:]) for r in S.FUS_TABLE])
    hw, zb, zt, rtf = interp_table(tab, y)
    return hw, zb, zt, rtf * hw, S.RB_FACTOR * hw


def fus_ring(y, inset=0.0):
    hw, zb, zt, rt, rb = fus_params(y)
    return rr_ring(y, hw - inset, zb + inset, zt - inset, max(rt - inset, 0.005), max(rb - inset, 0.005))


def inside_fus(x, y, z, margin=0.0):
    if y > S.NOSE_TIP_Y or y < S.TAIL_END_Y:
        return False
    hw, zb, zt, rt, rb = fus_params(y)
    ax = abs(x)
    if ax > hw - margin or z < zb + margin or z > zt - margin:
        return False
    # corners
    if z > zt - rt and ax > hw - rt:
        return (V((ax - (hw - rt), 0, z - (zt - rt))).length < rt - margin)
    if z < zb + rb and ax > hw - rb:
        return (V((ax - (hw - rb), 0, z - (zb + rb))).length < rb - margin)
    return True


def fus_exit_y(x, z, y_start, step=0.005):
    """march forward from y_start until the point leaves the fuselage (nose)."""
    y = y_start
    while y < S.NOSE_TIP_Y + 0.2 and inside_fus(x, y, z):
        y += step
    return y


def station_list(y0, y1, required, max_step=0.34):
    """stations from y0 (front) to y1 (back), descending, including required ys inside."""
    ys = sorted({round(y, 4) for y in [y0, y1] + [r for r in required if y1 < r < y0]}, reverse=True)
    out = [ys[0]]
    for a, b in zip(ys, ys[1:]):
        n = max(1, int(math.ceil((a - b) / max_step - 1e-6)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return out


# seam fix (2026-10-31): the hinge wall of every fixed surface (wing box at the flap/aileron hinge, stabiliser at the
# elevator hinge, fin at the rudder hinge) was bare-aluminium 'structure'; seen through the hinge gap it lit up as a light
# line. Dark 'metal_dark' instead (geometry, names, UVs unchanged); the control-surface noses are darkened in the textures
# (tex_lib.hinge_gap).
HINGE_WALL_MAT = getattr(S, 'HINGE_WALL_MAT', 'metal_dark')
_TORN_Y = list(getattr(S, 'FUS_TORN', {}).keys())
TURRET_ROUND_HOLE = True      # 1.8.13 r2: see fus_classify
TURRET_HOLE_Y = (S.TURRET_C[1] - 0.32, S.TURRET_C[1] + 0.32)
REQUIRED_Y = ([r[0] for r in S.FUS_TABLE if all(abs(r[0] - t) > 0.08 or abs(r[0] - t) < 1e-6 for t in _TORN_Y)] +
              list(S.CANOPY_Y) + list(S.NOSE_WELL_Y) + list(S.BAY_Y) +
              list(S.WAIST_L_Y) + list(S.WAIST_R_Y) + [S.TAIL_GLASS_Y, -8.45] + [v for a in S.SPLITS.values() for v in a] +
              list(getattr(S, 'HATCH_FWD_Y', ())) + list(getattr(S, 'HATCH_REAR_Y', ())) + list(getattr(S, 'HATCH_TOP_Y', ())) +
              list(TURRET_HOLE_Y))


def fus_classify(ym, j, cen):
    cat = rr_category(j)
    if S.CANOPY_Y[0] < ym < S.CANOPY_Y[1] and cat in ('tcorner', 'tflat'):
        return 'canopy'
    if S.NOSE_WELL_Y[0] < ym < S.NOSE_WELL_Y[1] and cat == 'bflat' and abs(cen.x) < S.NOSE_WELL_HALF_X:
        return 'nwL' if cen.x < 0 else 'nwR'
    if S.BAY_Y[0] < ym < S.BAY_Y[1] and cat in ('bflat', 'bcorner') and abs(cen.x) < S.BAY_HALF_X:
        return 'bayL' if cen.x < 0 else 'bayR'
    if cat == 'side' and S.WAIST_Z[0] < cen.z < S.WAIST_Z[1]:
        if cen.x < 0 and S.WAIST_L_Y[0] < ym < S.WAIST_L_Y[1]:
            return 'waistL'
        if cen.x > 0 and S.WAIST_R_Y[0] < ym < S.WAIST_R_Y[1]:
            return 'waistR'
    if ym < S.TAIL_GLASS_Y and cat in ('tcorner', 'tflat'):
        return 'tailglass'
    if hasattr(S, 'HATCH_FWD_Y'):
        if S.HATCH_FWD_Y[0] < ym < S.HATCH_FWD_Y[1] and cat == 'bflat' and abs(cen.x) < S.HATCH_FWD_HALF_X:
            return 'hatchFwd'
        if S.HATCH_REAR_Y[0] < ym < S.HATCH_REAR_Y[1] and cat == 'bflat' and abs(cen.x) < S.HATCH_REAR_HALF_X:
            return 'hatchRear'
        if TURRET_HOLE_Y[0] < ym < TURRET_HOLE_Y[1] and cat == 'tflat':
            return 'turret'
        # 1.8.13 r2 (offline L): a round opening the size of the turret drum (r 0.46): the AN/M2 receivers swing down into the fuselage at
        # high elevation (the B-25H's Bendix turret had a basket); the ring structure annulus (r 0.42-0.50) below closes the edge
        if TURRET_ROUND_HOLE and cat in ('tflat', 'tcorner') and math.hypot(cen.x, cen.y - S.TURRET_C[1]) < 0.50:
            return 'turret'
    return 'skin'


def shell(mb, outer, inner, ys, classify, uvfunc, end_front, end_back, axis=V((0, 1, 0)), frame_depth=0.09):
    """Thick shell between aligned outer/inner ring lists.
    classify(i, j, centroid) -> 'skin' or a hole tag. Returns {tag: [(outer4, inner4, uv4)]}.
    end_front / end_back: 'frame' | 'disc' | 'fan_paint' | 'fan_glass' | None, or ('fan_paint', tip_point)."""
    n = len(outer[0])
    strips = len(outer) - 1
    kinds = [[None] * n for _ in range(strips)]
    cents = [[None] * n for _ in range(strips)]
    for i in range(strips):
        for j in range(n):
            j1 = (j + 1) % n
            c = (outer[i][j] + outer[i][j1] + outer[i + 1][j] + outer[i + 1][j1]) / 4
            cents[i][j] = c
            kinds[i][j] = classify(i, j, c)
    # orientation (outward) from all faces
    score = 0.0
    for i in range(strips):
        cen = sum(outer[i], V()) / n
        for j in range(n):
            a, b, d = outer[i][j], outer[i][(j + 1) % n], outer[i + 1][j]
            score += (b - a).cross(d - a).dot(cents[i][j] - cen)
    flip = score < 0
    ov, iv = {}, {}

    def gv(cache, rings, i, j):
        k = (i, j)
        if k not in cache:
            cache[k] = mb.v(rings[i][j])
        return cache[k]

    holes = {}
    for i in range(strips):
        for j in range(n):
            j1 = (j + 1) % n
            corners = [(i, j), (i, j1), (i + 1, j1), (i + 1, j)]
            if flip:
                corners = [corners[0], corners[3], corners[2], corners[1]]
            uv = [uvfunc(ci, cj, j) for ci, cj in corners]
            k = kinds[i][j]
            if k == 'skin':
                mb.face([gv(ov, outer, ci, cj) for ci, cj in corners], 'paint', uv)
                mb.face([gv(iv, inner, ci, cj) for ci, cj in reversed(corners)], 'interior')
                # rims toward non-skin neighbours
                nbs = [((i, (j - 1) % n), (i, j), (i + 1, j)), ((i, j1), (i, j1), (i + 1, j1))]
                if i > 0:
                    nbs.append(((i - 1, j), (i, j), (i, j1)))
                if i < strips - 1:
                    nbs.append(((i + 1, j), (i + 1, j), (i + 1, j1)))
                for (ni, nj), e0, e1 in nbs:
                    if kinds[ni][nj] != 'skin':
                        q = [outer[e0[0]][e0[1]], outer[e1[0]][e1[1]], inner[e1[0]][e1[1]], inner[e0[0]][e0[1]]]
                        mid = (q[0] + q[1]) / 2
                        oriented_quad(mb, q, 'structure', cents[ni][nj] - mid)
            else:
                holes.setdefault(k, []).append(([outer[ci][cj] for ci, cj in corners],
                                                [inner[ci][cj] for ci, cj in corners], uv))
    # ends
    for end, ring_i, sgn, strip_i in ((end_front, 0, 1, 0), (end_back, len(outer) - 1, -1, strips - 1)):
        if end is None:
            continue
        kind = end[0] if isinstance(end, tuple) else end
        out_dir = axis * sgn            # pointing out of the section through this end
        o, inn = outer[ring_i], inner[ring_i]
        if kind == 'torn':
            for j in range(n):
                if kinds[strip_i][j] != 'skin':
                    continue
                j1 = (j + 1) % n
                oriented_quad(mb, [o[j], o[j1], inn[j1], inn[j]], 'structure', out_dir)
        elif kind in ('frame', 'disc'):
            # skin edge rim (only where the strip is skin)
            for j in range(n):
                if kinds[strip_i][j] != 'skin':
                    continue
                j1 = (j + 1) % n
                oriented_quad(mb, [o[j], o[j1], inn[j1], inn[j]], 'structure', out_dir)
            cen = sum(inn, V()) / n
            if kind == 'disc':
                fan_cap(mb, [p - out_dir * 0.003 for p in inn], cen - out_dir * 0.003, 'structure', out_dir)
            else:
                a = [p - out_dir * 0.002 for p in inn]
                b = [p + (cen - p).normalized() * frame_depth - out_dir * 0.002 for p in inn]
                a2 = [p - out_dir * 0.035 for p in a]
                b2 = [p - out_dir * 0.035 for p in b]
                annulus(mb, a, b, 'structure', out_dir)
                annulus(mb, a2, b2, 'structure', -out_dir)
                loft(mb, [b, b2], 'structure', outward=False)
                # bulkhead web inside the frame, facing out of the section: a separated fuselage section shows a
                # capped, textured break (one-sided, so it is invisible from inside the section, e.g. the cockpit)
                fan_cap(mb, b2, cen - out_dir * 0.037, 'structure', out_dir)
        elif kind in ('fan_paint', 'fan_glass'):
            tip = V(end[1])
            mat = 'paint' if kind == 'fan_paint' else 'glass'
            ti = mb.v(tip)
            for j in range(n):
                j1 = (j + 1) % n
                pts = [tip, o[j], o[j1]]
                nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
                order = [j, j1] if nrm.dot(out_dir) >= 0 else [j1, j]
                if mat == 'paint':
                    u1, u2 = uvfunc(ring_i, order[0], j), uvfunc(ring_i, order[1], j)
                    uv = [(tip.y, (u1[1] + u2[1]) / 2), u1, u2]
                    mb.face([ti, gv(ov, outer, ring_i, order[0]), gv(ov, outer, ring_i, order[1])], 'paint', uv)
                else:
                    mb.poly([tip, o[order[0]], o[order[1]]], 'glass')
                    mb.poly([tip, o[order[1]], o[order[0]]], 'glass')
    return holes, kinds


def fus_uvfunc(rings, ys):
    arcs = [arc_lengths(r) for r in rings]

    def f(ci, cj, j):
        acc, P = arcs[ci]
        if j < RR_HALF:
            v = acc[cj] if cj != 0 or j == 0 else acc[cj]
        else:
            v = -(P - acc[cj]) if cj != 0 else 0.0
        return (ys[ci], v)
    return f


def plate(mb, quads, mat_out='paint', mat_in='interior', mat_edge='structure', out_offset=0.0, weld=False):
    """thick plate from shell hole quads (outer winding is outward). weld=True shares vertices between the
    quads of each surface so curved glazing is smooth-shaded (v3)."""
    if weld:
        cache = {}

        def wv(p, tag):
            k = (tag, round(p.x, 5), round(p.y, 5), round(p.z, 5))
            if k not in cache:
                cache[k] = mb.v(p)
            return cache[k]
        for o, i, uv in quads:
            mb.face([wv(p, 'o') for p in o], mat_out, uv if mat_out == 'paint' else None)
            mb.face([wv(p, 'i') for p in reversed(i)], mat_in, None)
        return
    edge_count = {}

    def key(p):
        return (round(p.x, 5), round(p.y, 5), round(p.z, 5))
    for o, i, uv in quads:
        for k in range(4):
            a, b = o[k], o[(k + 1) % 4]
            ek = tuple(sorted((key(a), key(b))))
            edge_count[ek] = edge_count.get(ek, 0) + 1
    for o, i, uv in quads:
        nrm = (o[1] - o[0]).cross(o[3] - o[0]).normalized()
        oo = [p + nrm * out_offset for p in o]
        mb.poly(oo, mat_out, uv if mat_out == 'paint' else None)
        mb.poly(list(reversed(i)), mat_in, None)
        c = sum(o, V()) / 4
        for k in range(4):
            a, b = o[k], o[(k + 1) % 4]
            ek = tuple(sorted((key(a), key(b))))
            if edge_count[ek] == 1:
                q = [oo[k], oo[(k + 1) % 4], i[(k + 1) % 4], i[k]]
                oriented_quad(mb, q, mat_edge, (a + b) / 2 - c)


def build_fuselage():
    parts = {}
    holes_all = {}
    frames_at = []
    for name, (y0, y1) in S.SPLITS.items():
        mb = MeshBuf()
        if name == 'fus_nose':
            ds = [0.003, 0.015, 0.04, 0.09, 0.17, 0.28, 0.42, 0.60, 0.80, 1.02, 1.22]
            ys = [S.NOSE_TIP_Y - d for d in ds] + [S.NOSE_BASE_Y]
        else:
            ys = station_list(y0, y1, REQUIRED_Y)
        outer = [fus_ring(y) for y in ys]
        inner = [fus_ring(y, S.SKIN_T) for y in ys]
        uvf = fus_uvfunc(outer, ys)

        def cls(i, j, c, ys=ys):
            return fus_classify((ys[i] + ys[i + 1]) / 2, j, c)
        torn = getattr(S, 'FEATURES', {}).get('torn_breaks', False)
        ef = ('fan_paint', V((0, S.NOSE_TIP_Y, S.NOSE_TIP_Z))) if name == 'fus_nose' else ('torn' if torn else 'frame')
        eb = (None if torn else ('fan_glass', V((0, S.TAIL_END_Y - 0.06, 0.40)))) if name == 'fus_tail' else ('torn' if torn else 'frame')
        holes, kinds = shell(mb, outer, inner, ys, cls, uvf, ef, eb)
        for k, v in holes.items():
            holes_all.setdefault(k, []).extend(v)
        # interior frames + stringers
        if name not in ('fus_nose', 'fus_cockpit'):
            add_frames(mb, ys, inner, kinds, y0, y1)
        if name == 'fus_tail':
            plate(mb, holes.pop('tailglass', []), 'glass', 'glass', 'glass', weld=True)
            holes_all.pop('tailglass', None)
        if getattr(S, 'FEATURES', {}).get('torn_breaks', False):
            import b25h_v3 as V3
            for k, yy in enumerate(S.FUS_TORN):
                if abs(yy - y0) < 1e-6:
                    V3.fus_break_structure(mb, yy, +1, 101 + k)
                if abs(yy - y1) < 1e-6:
                    V3.fus_break_structure(mb, yy, -1, 201 + k)
            if name == 'fus_tail':
                import b25h_v3_arms as A3
                A3.tail_cap(mb)
        piv = {'fus_center': (0, 0, 0)}.get(name, (0, y0, 0.25))
        parts[name] = Part(name, None, piv, mb)
    return parts, holes_all


STRINGER_J = [6, 11, 16, 20, 23, 26, 29, 33, 38, 43]


def add_frames(mb, ys, inner, kinds, y0, y1):
    n = RR_N
    for i, y in enumerate(ys):
        if abs(y - y0) < 0.2 or abs(y - y1) < 0.2:
            continue
        if TURRET_ROUND_HOLE and -9.5 < y < -8.85:      # 1.8.13 r2: no frame in the tail gun bay (the AN/M2 grips swing to the walls at +-20 deg)
            continue
        if i % 2 == 1 and len(ys) > 4:
            continue
        hw, zb, zt, rt, rb = fus_params(y)
        cen = V((0, y, (zb + zt) / 2))
        ring = inner[i]
        # 1.8.13 r2: shallow frames in the tail gun bay (the AN/M2 grips swing to the walls at +-20 deg)
        fd = 0.02 if (TURRET_ROUND_HOLE and -9.5 < y < -8.85) else 0.055
        deep = [p + (cen - p).normalized() * fd for p in ring]
        for j in range(n):
            ok = True
            for si in (i - 1, i):
                if 0 <= si < len(kinds) and kinds[si][j] != 'skin':
                    ok = False
            if not ok:
                continue
            j1 = (j + 1) % n
            a, b, c_, d = ring[j], ring[j1], deep[j1], deep[j]
            off = V((0, 0.018, 0))
            oriented_quad(mb, [a + off, b + off, c_ + off, d + off], 'structure', V((0, 1, 0)))
            oriented_quad(mb, [a - off, b - off, c_ - off, d - off], 'structure', V((0, -1, 0)))
            oriented_quad(mb, [d + off, c_ + off, c_ - off, d - off], 'structure', cen - (c_ + d) / 2)
    # stringers
    for i in range(len(ys) - 1):
        for jj in STRINGER_J:
            if kinds[i][jj] != 'skin' or kinds[i][jj - 1] != 'skin':
                continue
            a, b = inner[i][jj], inner[i + 1][jj]
            ca = V((0, a.y, a.z)) * 0 + V((0, a.y, 0.25))
            da = (V((0, a.y, 0.25)) - a)
            da.y = 0
            da = da.normalized()
            db = (V((0, b.y, 0.25)) - b)
            db.y = 0
            db = db.normalized()
            w = 0.012
            side_a = da.cross(V((0, 1, 0))).normalized() * w
            side_b = db.cross(V((0, 1, 0))).normalized() * w
            h = 0.025
            q1 = [a + side_a, b + side_b, b + side_b + db * h, a + side_a + da * h]
            q2 = [a - side_a, b - side_b, b - side_b + db * h, a - side_a + da * h]
            q3 = [a + side_a + da * h, b + side_b + db * h, b - side_b + db * h, a - side_a + da * h]
            oriented_quad(mb, q1, 'structure', side_a)
            oriented_quad(mb, q2, 'structure', -side_a)
            oriented_quad(mb, q3, 'structure', da)


def hinge_from_quads(quads, pick):
    """pick(point)->score; returns (front, back) points of the hinge line = boundary verts with max score."""
    pts = [p for o, i, uv in quads for p in o]
    ys = sorted({round(p.y, 4) for p in pts})
    yf, yb = ys[-1], ys[0]
    front = max([p for p in pts if abs(p.y - yf) < 1e-3], key=pick)
    back = max([p for p in pts if abs(p.y - yb) < 1e-3], key=pick)
    return front, back


def door_from_holes(name, parent, quads, pick, open_deg, note):
    mb = MeshBuf()
    plate(mb, quads)
    f, b = hinge_from_quads(quads, pick)
    axis = (f - b).normalized()          # points forward (+Y-ish)
    pivot = (f + b) / 2
    frame = frame_from_axes(V((1, 0, 0)))      # identity
    pose = Quaternion(axis, math.radians(open_deg))
    # pose is applied in local axes: axis is in world = local (identity frame)
    return Part(name, parent, pivot, mb, frame, pose,
                info=dict(hinge_axis=tuple(axis), open_deg=open_deg, note=note))


# =============================================================================== wing
def wing_station(ax, side):
    if ax <= S.WING_TIP[0][0]:
        le, te = S.WING_LE(ax), S.WING_TE(ax)
    else:
        le, te = interp_table([(r[0], r[1:]) for r in S.WING_TIP], ax)
    chord = max(le - te, 0.02)
    t = interp_table([(0.62, (0.17,)), (2.95, (0.155,)), (9.58, (0.10,)), (10.30, (0.08,))], ax)[0]
    inc = math.radians(max(0.0, 3.0 - 3.0 * (ax - 0.62) / (9.58 - 0.62)))
    zc = S.WING_ROOT_Z + (min(ax, S.WING_BREAK_X) - S.WING_ROOT_X) * math.tan(S.DIHEDRAL_IN) + \
        max(0.0, ax - S.WING_BREAK_X) * math.tan(S.DIHEDRAL_OUT)
    dih = S.DIHEDRAL_IN if ax < S.WING_BREAK_X else S.DIHEDRAL_OUT
    cdir = V((0, -math.cos(inc), -math.sin(inc)))
    up0 = V((0, -math.sin(inc), math.cos(inc)))
    up = up0 * math.cos(dih) + V((-side, 0, 0)) * math.sin(dih)
    le_pt = V((side * ax, le, zc + 0.25 * chord * math.sin(inc)))
    return Station(side * ax, le_pt, cdir, up, chord, t, m=0.02)


def camber_mid(st, s):
    return (st.point(s, True) + st.point(s, False)) / 2


def inner_box_ring(st, s_end, d, n=12):
    ring, ss = box_ring(st, s_end, n)
    out = []
    # upper (reversed ss) then lower ss[1:]
    s_seq = list(reversed(ss)) + ss[1:]
    for p, s in zip(ring, s_seq):
        m = camber_mid(st, max(s, 0.03))
        dv = m - p
        if dv.length < 1e-6:
            out.append(p)
        else:
            out.append(p + dv.normalized() * min(d, dv.length * 0.6))
    return out


def wing_panel(side, xs, cap0, cap1, tank=None):
    """box (LE..hinge) with inner skin, spars and rib caps.
    cap0/cap1: 'rib' (structure rib with lightening hole), 'paint' (closed), None."""
    mb = MeshBuf()
    sts = [wing_station(x, side) for x in xs]
    rings = surface(mb, sts, 0.0, S.HINGE_F, hinge_mat=HINGE_WALL_MAT)
    inner = [inner_box_ring(st, S.HINGE_F, 0.014) for st in sts]
    nseg = len(inner[0])
    loft(mb, inner, 'interior', outward=False)
    for which, kind, st_i in ((0, cap0, 0), (1, cap1, len(sts) - 1)):
        if kind is None:
            continue
        if kind == 'torn':
            import b25h_v3 as V3
            V3.wing_break_structure(mb, side, xs[st_i], 1 if which == 1 else -1, int(xs[st_i] * 100) + (7 if side > 0 else 3))
            continue
        toward = V((-side, 0, 0)) if which == 0 else V((side, 0, 0))
        o, inn = rings[st_i], inner[st_i]
        if kind == 'paint':
            section_cap(mb, o, 'paint', toward, lambda p, t=toward: planar_uv(p, t))
        else:
            annulus(mb, o, inn, 'structure', toward)
            cen = camber_mid(sts[st_i], 0.38)
            hole = [p + (cen - p) * 0.55 for p in inn]
            hole = [h - toward * 0.004 for h in hole]
            web = [p - toward * 0.004 for p in inn]
            annulus(mb, web, hole, 'structure', toward)
            annulus(mb, [p - toward * 0.02 for p in web], [p - toward * 0.02 for p in hole], 'structure', -toward)
            loft(mb, [hole, [p - toward * 0.016 for p in hole]], 'structure', outward=False)
            # lightening hole closed by a recessed web (both faces): a broken-off panel shows a capped rib, never
            # a see-through wing box
            back = [p - toward * 0.016 for p in hole]
            bc = sum(back, V()) / len(back)
            fan_cap(mb, back, bc, 'structure', toward)
            fan_cap(mb, back, bc, 'structure', -toward)
    # spars (double-sided webs)
    for s in (0.15, 0.62):
        ups = [p for p in (inner_pt(st, s, True) for st in sts)]
        los = [p for p in (inner_pt(st, s, False) for st in sts)]
        for k in range(len(sts) - 1):
            q = [ups[k], ups[k + 1], los[k + 1], los[k]]
            oriented_quad(mb, q, 'structure', V((0, 1, 0)))
            oriented_quad(mb, q, 'structure', V((0, -1, 0)))
    if tank:
        x0, x1 = tank
        tx = [x0 + (x1 - x0) * k / 3 for k in range(4)]
        trings = []
        for x in tx:
            st = wing_station(x, side)
            a, b = 0.20, 0.57
            ua, ub = inner_pt(st, a, True), inner_pt(st, b, True)
            la, lb = inner_pt(st, a, False), inner_pt(st, b, False)
            sh = 0.02
            trings.append([ua - st.up * sh, ub - st.up * sh, lb + st.up * sh, la + st.up * sh])
        loft(mb, trings, 'structure')
        oriented_quad(mb, trings[0], 'structure', V((-side, 0, 0)))
        oriented_quad(mb, trings[-1], 'structure', V((side, 0, 0)))
    return mb, sts


def inner_pt(st, s, upper):
    p = st.point(s, upper)
    m = camber_mid(st, s)
    return p + (m - p).normalized() * 0.014


def aft_piece(mb, side, xs, cap0, cap1, inset=0.0):
    sts = [wing_station(x, side) for x in xs]
    c0 = V((-side, 0, 0)) if cap0 else None
    c1 = V((side, 0, 0)) if cap1 else None
    surface(mb, sts, S.HINGE_F, 1.0, cap0=c0, cap1=c1, cap_mat='paint', inset=inset)
    return sts


def hinge_point(st, f=S.HINGE_F):
    return camber_mid(st, f)


def control_surface(name, parent, side, xs, note):
    mb = MeshBuf()
    sts = aft_piece(mb, side, xs, True, True, inset=0.004)
    p0, p1 = hinge_point(sts[0]), hinge_point(sts[-1])
    axis = (p1 - p0) * side
    axis.normalize()
    frame = frame_from_axes(axis)
    return Part(name, parent, (p0 + p1) / 2, mb, frame, None,
                info=dict(hinge_axis_local='+X', hinge_axis_world=tuple(axis), note=note))


def well_cut(c):
    """wing skin/structure removed above the main wheel well (hidden inside the nacelle)."""
    if not (abs(abs(c.x) - S.NAC_X) < S.NAC_WELL_HALF_X + 0.08 and S.NAC_WELL_Y[0] - 0.05 < c.y < S.NAC_WELL_STEP_Y
            and c.z < S.NAC_WELL_TOP_AFT + 0.05):
        return False
    # only where the face is really inside the nacelle: aft of the wing the nacelle top drops below the wing skin,
    # and cutting there left an open hole behind the flaps (in-game 2026-10-30)
    hw, zb, zt, n = nac_params(c.y)
    dx = abs(abs(c.x) - S.NAC_X)
    if dx >= hw:
        return False
    cz = (zb + zt) / 2
    ztop = cz + (zt - cz) * (1.0 - (dx / hw) ** n) ** (1.0 / n)
    if c.z >= ztop - 0.015:
        return False
    # and only below the (sloped) well roof: wing skin above the roof stays, so the well has no gap between its
    # walls and the wing that would let you see the back of the upper wing skin from below
    roof = interp_table(sorted([(-0.85, (0.57,)), (-1.20, (0.565,)), (-1.60, (0.49,)), (-2.00, (0.37,)),
                                (-2.24, (0.29,))]), c.y)[0]
    return c.z < roof + 0.05


def build_wing(side):
    L = 'L' if side < 0 else 'R'
    parts = []
    # inner panel: root .. break, with fixed aft piece 2.41..2.95
    xs_in = [0.62, 1.05, 1.50, 1.95, 2.41, 2.68, 2.95]
    T = 'torn' if getattr(S, 'FEATURES', {}).get('torn_breaks', False) else 'rib'
    mb, sts = wing_panel(side, xs_in, 'rib', T, tank=(1.0, 2.25))
    aft_piece(mb, side, [2.41, 2.68, 2.95], True, False)
    hinge_brackets(mb, side, [0.95, 1.6, 2.25])
    cut_faces(mb, well_cut)
    parts.append(Part(f'wing_inner_{L}', 'fus_center', (side * S.WING_ROOT_X, 0.0, S.WING_ROOT_Z), mb,
                      info=dict(note='root rib at x=0.62 (inside fuselage side)')))
    xs_out = [2.95, 3.40, 3.90, 4.45, 5.00, 5.60, 6.15]
    mb, sts = wing_panel(side, xs_out, T, T, tank=(3.6, 5.2))
    aft_piece(mb, side, [2.95, 3.40], False, True)
    hinge_brackets(mb, side, [3.6, 4.5, 5.4])
    cut_faces(mb, well_cut)
    st = wing_station(S.WING_BREAK_X, side)
    parts.append(Part(f'wing_outer_{L}', f'wing_inner_{L}', camber_mid(st, 0.3), mb))
    xs_tip = [6.15, 6.80, 7.50, 8.20, 8.90, 9.58, 9.82, 10.00, 10.12, 10.22, 10.28, 10.30]
    mb, sts = wing_panel(side, xs_tip, T, 'paint')
    aft_piece(mb, side, [9.58, 9.82, 10.00, 10.12, 10.22, 10.28, 10.30], True, True)
    hinge_brackets(mb, side, [6.5, 7.9, 9.3])
    st = wing_station(S.WING_TIPSPLIT_X, side)
    parts.append(Part(f'wing_tip_{L}', f'wing_outer_{L}', camber_mid(st, 0.3), mb))
    parts.append(control_surface(f'flap_inner_{L}', f'wing_inner_{L}', side, [0.74, 1.05, 1.50, 1.95, 2.41],
                                 'split/plain flap; positive local-X rotation = see table'))
    parts.append(control_surface(f'flap_outer_{L}', f'wing_outer_{L}', side, [3.40, 3.90, 4.45, 5.00, 5.60, 6.15],
                                 'flap'))
    parts.append(control_surface(f'aileron_{L}', f'wing_tip_{L}', side, [6.15, 6.80, 7.50, 8.20, 8.90, 9.58],
                                 'aileron'))
    return parts


def hinge_brackets(mb, side, xs):
    for x in xs:
        st = wing_station(x, side)
        p = st.point(S.HINGE_F + 0.02, False)
        box(mb, p - st.up * 0.03, (0.03, 0.12, 0.07), 'metal_dark')


# =============================================================================== nacelle
def nac_params(y):
    tab = sorted([(r[0], r[1:]) for r in S.NAC_TABLE])
    return interp_table(tab, y)


NAC_N = 40


def nac_ring(y, cx, inset=0.0):
    hw, zb, zt, n = nac_params(y)
    cz = (zb + zt) / 2
    return superellipse_ring(cx, y, cz, hw - inset, (zt - cz) - inset, (cz - zb) - inset, n=n, N=NAC_N)


def build_nacelle(side):
    L = 'L' if side < 0 else 'R'
    cx = side * S.NAC_X
    req = [r[0] for r in S.NAC_TABLE] + list(S.NAC_WELL_Y)
    ys = station_list(S.FIREWALL_Y, S.NAC_TABLE[-1][0], req, 0.3)
    outer = [nac_ring(y, cx) for y in ys]
    inner = [nac_ring(y, cx, S.SKIN_T) for y in ys]
    arcs = [arc_lengths(r) for r in outer]

    def uvf(ci, cj, j):
        acc, P = arcs[ci]
        if j < NAC_N // 2:
            v = acc[cj]
        else:
            v = -(P - acc[cj]) if cj != 0 else 0.0
        return (ys[ci], v)

    def cls(i, j, c):
        ym = (ys[i] + ys[i + 1]) / 2
        hw, zb, zt, n = nac_params(ym)
        cz = (zb + zt) / 2
        if S.NAC_WELL_Y[0] < ym < S.NAC_WELL_Y[1] and abs(c.x - cx) < S.NAC_WELL_HALF_X and c.z < cz - 0.35:
            return 'wellA' if abs(c.x) < S.NAC_X else 'wellB'
        return 'skin'
    mb = MeshBuf()
    tip = V((cx, S.NAC_TIP[0], S.NAC_TIP[1]))
    holes, kinds = shell(mb, outer, inner, ys, cls, uvf, 'disc', ('fan_paint', tip))
    # gear well box (open bottom), double sided interior
    y0, y1 = S.NAC_WELL_Y
    wx = S.NAC_WELL_HALF_X - 0.01
    zl = -0.60
    # aft roof follows the tapering nacelle skin (3-4 cm inside it at the well walls, |x-cx|=0.33): a flat roof at
    # NAC_WELL_TOP_AFT poked through the skin aft of y=-1.4 and showed as a light-green patch behind the flaps
    # (in-game 2026-10-30).
    prof = [(y1 - 0.01, zl), (y1 - 0.01, S.NAC_WELL_TOP_FWD), (S.NAC_WELL_STEP_Y, S.NAC_WELL_TOP_FWD),
            (S.NAC_WELL_STEP_Y, S.NAC_WELL_TOP_AFT), (-1.20, 0.565), (-1.60, 0.49), (-2.00, 0.37),
            (y0 + 0.01, 0.29), (y0 + 0.01, zl)]
    open_profile_box(mb, prof, cx - wx, cx + wx, 'interior', clamp=nac_well_clamp(cx))
    # firewall details: engine mount tubes (metal) from firewall to engine crankcase rear
    for k in range(6):
        a = 2 * math.pi * k / 6 + math.pi / 6
        p0 = V((cx + 0.55 * math.sin(a), S.FIREWALL_Y + 0.005, 0.55 * math.cos(a)))
        p1 = V((cx + 0.27 * math.sin(a + 0.4), 1.99, 0.27 * math.cos(a + 0.4)))
        cylinder(mb, p0, p1, 0.022, N=6)
    part = Part(f'nacelle_{L}', f'wing_inner_{L}', (cx, S.FIREWALL_Y, 0.0), mb,
                info=dict(note='firewall cap at y=1.62; main gear well open at bottom'))
    doors = []
    for tag, nm in (('wellA', 'a'), ('wellB', 'b')):
        qs = holes.get(tag, [])
        if not qs:
            continue
        outward = -1 if tag == 'wellA' else 1    # toward which |x| side the hinge sits
        pick = (lambda p, s=outward: s * (abs(p.x) - S.NAC_X))
        # door hangs open: rotate about hinge so the free edge drops ~95 deg
        d = door_from_holes(f'gear_door_main_{L}_{nm}', f'nacelle_{L}', qs, pick, 0.0,
                            'main gear door; hinge on well edge')
        # opening sense: free edge must move down. test both signs.
        d.pose = open_pose(d, qs, 95.0)
        d.info['open_deg'] = round(math.degrees(d.pose.angle) * (1 if d.pose.axis.dot(V(d.info['hinge_axis'])) > 0 else -1), 1)
        doors.append(d)
    return part, doors


def nac_well_clamp(cx, margin=0.008):
    """x clamp for the main gear well walls: keeps every well vertex inside the nacelle inner skin at its (y, z)
    (the aft lower corners of the box stood up to 0.27 m outside the tapering nacelle - the 'bucket' under the engine)."""
    def clamp(x, y, z):
        hw, zb, zt, n = nac_params(y)
        cz = (zb + zt) / 2
        hz = (zt - cz if z >= cz else cz - zb) - S.SKIN_T
        r = min(abs(z - cz) / hz, 1.0)
        lim = max((hw - S.SKIN_T) * (1 - r ** n) ** (1 / n) - margin, 0.01)
        return cx + max(-lim, min(lim, x - cx))
    return clamp


def open_profile_box(mb, prof, x0, x1, mat, clamp=None):
    """walls swept along X from a (y, z) profile whose closing segment (last->first) is left open;
    side walls are the profile polygon. Everything double-sided. clamp(x, y, z) -> x limits the side walls per vertex."""
    if clamp is not None:
        def Vc(x, y, z):
            return V((clamp(x, y, z), y, z))
    else:
        def Vc(x, y, z):
            return V((x, y, z))
    n = len(prof)
    yc = sum(p[0] for p in prof) / n
    zc = sum(p[1] for p in prof) / n
    for j in range(n - 1):
        a, b = prof[j], prof[j + 1]
        q = [Vc(x0, a[0], a[1]), Vc(x0, b[0], b[1]), Vc(x1, b[0], b[1]), Vc(x1, a[0], a[1])]
        mid = (q[0] + q[2]) / 2
        inward = V((0, yc - mid.y, zc - mid.z))
        oriented_quad(mb, q, mat, inward)
        oriented_quad(mb, q, mat, -inward)
    for t in ear_clip(prof):
        for X in (x0, x1):
            pts = [Vc(X, prof[k][0], prof[k][1]) for k in t]
            oriented_quad(mb, pts, mat, V((1, 0, 0)))
            oriented_quad(mb, pts, mat, V((-1, 0, 0)))


def cut_faces(mb, inside):
    """remove faces whose centroid satisfies inside(p) (e.g. wing skin over the wheel well)."""
    keep = []
    for f in mb.faces:
        c = sum((mb.verts[i] for i in f['idx']), V()) / len(f['idx'])
        if not inside(c):
            keep.append(f)
    mb.faces = keep


def open_pose(door, quads, deg):
    """rotation about the door hinge axis (world == local) that moves the door centroid DOWN."""
    axis = V(door.info['hinge_axis'])
    c = sum([p for o, i, uv in quads for p in o], V()) / (4 * len(quads)) - door.pivot
    best = None
    for sgn in (1, -1):
        q = Quaternion(axis, math.radians(deg * sgn))
        z = (q @ c).z
        if best is None or z < best[0]:
            best = (z, q)
    return best[1]


def open_box(mb, x0, x1, y0, y1, z0, z1, mat, open_side='-z', double=True):
    P = lambda x, y, z: V((x, y, z))
    faces = {
        '-x': ([P(x0, y0, z0), P(x0, y1, z0), P(x0, y1, z1), P(x0, y0, z1)], V((1, 0, 0))),
        '+x': ([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], V((-1, 0, 0))),
        '-y': ([P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)], V((0, 1, 0))),
        '+y': ([P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)], V((0, -1, 0))),
        '-z': ([P(x0, y0, z0), P(x1, y0, z0), P(x1, y1, z0), P(x0, y1, z0)], V((0, 0, 1))),
        '+z': ([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], V((0, 0, -1))),
    }
    for k, (q, inward) in faces.items():
        if k == open_side:
            continue
        oriented_quad(mb, q, mat, inward)
        if double:
            oriented_quad(mb, q, mat, -inward)


# =============================================================================== engine / cowl flaps / exhaust / prop
COWL_OUT = [(1.80, 0.775), (2.05, 0.780), (2.30, 0.780), (2.50, 0.768), (2.62, 0.742), (2.69, 0.705), (2.72, 0.670)]
COWL_IN = [(2.70, 0.630), (2.64, 0.640), (2.50, 0.700), (2.30, 0.755), (1.80, 0.752)]
N_COWL = 42


def build_engine(side):
    L = 'L' if side < 0 else 'R'
    cx = side * S.NAC_X
    ax = V((0, 1, 0))
    mb = MeshBuf()
    rings = [circle_pts(V((cx, y, 0)), ax, r, N_COWL, ref=V((0, 0, -1))) for y, r in COWL_OUT + COWL_IN]
    nout = len(COWL_OUT)
    ys = [y for y, r in COWL_OUT + COWL_IN]
    arcs = [arc_lengths(r)[0] for r in rings]

    def fm(i, j):
        return 'paint' if i < nout - 1 else ('paint' if i == nout - 1 else 'interior')

    cum = [0.0]
    for a_, b_ in zip(rings, rings[1:]):
        cum.append(cum[-1] + (a_[0] - b_[0]).length)       # meridian arc length -> u
    loft(mb, rings, 'paint', face_mat=fm, uvfunc=ring_arc_uv(rings, cum))
    annulus(mb, rings[0], rings[-1], 'structure', V((0, -1, 0)))
    # engine body
    c = V((cx, 0, 0))
    cylinder(mb, c + V((0, 1.97, 0)), c + V((0, 2.42, 0)), 0.31, N=20, mat='metal_dark')         # crankcase
    cylinder(mb, c + V((0, 2.42, 0)), c + V((0, 2.74, 0)), 0.30, 0.16, N=20, mat='metal_dark', cap0=False)  # nose case
    for row, yy, ph in ((0, 2.30, 0.0), (1, 2.08, math.pi / 7)):
        for k in range(7):
            a = ph + 2 * math.pi * k / 7
            d = V((math.sin(a), 0, math.cos(a)))
            p0 = c + V((0, yy, 0)) + d * 0.28
            p1 = c + V((0, yy, 0)) + d * 0.60
            cylinder(mb, p0, p0 + d * 0.20, 0.082, N=10, mat='metal_dark', cap0=False)          # barrel
            for f in range(4):                                                                   # fins
                pf = p0 + d * (0.03 + 0.045 * f)
                cylinder(mb, pf, pf + d * 0.012, 0.098, N=10, mat='metal_dark')
            cylinder(mb, p0 + d * 0.20, p1, 0.092, 0.07, N=10, mat='metal_dark')               # head
            cylinder(mb, p1 - d * 0.05 + V((0, 0.07, 0)), c + V((0, yy + 0.25, 0)) + d * 0.18, 0.012, N=4)  # pushrod
    cylinder(mb, c + V((0, 1.58, 0)), c + V((0, 1.86, 0)), 0.745, N=N_COWL, mat='metal_dark', cap0=False, cap1=False)  # skirt under cowl flaps
    annulus(mb, circle_pts(c + V((0, 1.94, 0)), ax, 0.745, 24), circle_pts(c + V((0, 1.94, 0)), ax, 0.30, 24),
            'metal_dark', V((0, 1, 0)))           # baffle / accessory section closes the cowl
    # carburettor intake scoop on top
    scoop = MeshBuf()
    sy = [2.30, 2.15, 1.95, 1.80]
    sh = [0.0, 0.17, 0.19, 0.16]
    srings = []
    for y, h in zip(sy, sh):
        hw = 0.16 if h > 0 else 0.10
        z0 = 0.70
        srings.append([V((cx - hw, y, z0)), V((cx - hw * 0.9, y, z0 + h)), V((cx + hw * 0.9, y, z0 + h)), V((cx + hw, y, z0))])
    loft(mb, srings, 'paint', closed=False)
    loft(mb, [[p + V((0, 0, -0.012)) if k in (1, 2) else p + V((0.012 if k == 0 else -0.012, 0, 0)) for k, p in enumerate(r)]
              for r in srings], 'metal_dark', closed=False, outward=False)      # inside of the intake scoop
    oriented_quad(mb, srings[-1], 'structure', V((0, -1, 0)))
    oriented_quad(mb, [srings[1][0], srings[1][1], srings[1][2], srings[1][3]], 'metal_dark', V((0, 1, 0)))
    eng = Part(f'engine_{L}', f'nacelle_{L}', (cx, S.FIREWALL_Y, 0.0), mb,
               info=dict(note='Wright R-2600: cowl + 2x7 finned cylinders + crankcase + nose case'))
    # cowl flaps
    flaps = []
    nfl = 14
    for k in range(nfl):
        a0 = 2 * math.pi * (k + 0.015) / nfl
        a1 = 2 * math.pi * (k + 0.985) / nfl
        am = (a0 + a1) / 2
        fm_ = MeshBuf()
        quads = []
        segs = 3
        for s in range(segs):
            aa, bb = a0 + (a1 - a0) * s / segs, a0 + (a1 - a0) * (s + 1) / segs
            P = lambda a, y, r: V((cx + r * math.sin(a), y, r * math.cos(a)))
            o = [P(aa, 1.80, 0.778), P(bb, 1.80, 0.778), P(bb, 1.60, 0.770), P(aa, 1.60, 0.770)]
            i = [P(aa, 1.80, 0.766), P(bb, 1.80, 0.766), P(bb, 1.60, 0.758), P(aa, 1.60, 0.758)]
            nrm = (o[1] - o[0]).cross(o[3] - o[0])
            radial = V((math.sin((aa + bb) / 2), 0, math.cos((aa + bb) / 2)))
            if nrm.dot(radial) < 0:
                o = [o[0], o[3], o[2], o[1]]
                i = [i[0], i[3], i[2], i[1]]
            uv = [(p.y, (cx + p.x) * 0 + math.atan2(p.x - cx, p.z) * 0.77) for p in o]
            quads.append((o, i, uv))
        plate(fm_, quads)
        radial = V((math.sin(am), 0, math.cos(am)))
        tangent = V((math.cos(am), 0, -math.sin(am)))
        pivot = V((cx, 1.80, 0)) + radial * 0.772
        frame = frame_from_axes(tangent, radial)
        # open = trailing edge (aft) moves radially outward
        te = V((cx, 1.60, 0)) + radial * 0.77 - pivot
        q = Quaternion(tangent, math.radians(18))
        sgn = 1 if (q @ te).dot(radial) > te.dot(radial) else -1
        flaps.append(Part(f'cowl_flap_{L}_{k + 1:02d}', f'engine_{L}', pivot, fm_, frame, None,
                          info=dict(hinge_axis_local='+X', open_deg=18 * sgn,
                                    note='hinge tangent to cowl rim; open = TE outward')))
    # exhaust stacks
    ex = MeshBuf()
    for k in range(7):
        a = math.radians(-120 + 240 * k / 6) + math.pi       # lower 2/3 of the ring
        d = V((math.sin(a), 0, math.cos(a)))
        p0 = V((cx, 1.62, 0)) + d * 0.72
        p1 = p0 + V((0, -0.26, 0)) + d * 0.07
        tube(ex, p0, p1, 0.045, 0.03, N=8)
    exh = Part(f'exhaust_{L}', f'engine_{L}', (cx, 1.75, -0.5), ex)
    return eng, flaps, exh


def blade_mesh(R=S.PROP_R, r0=0.16):
    """blade along +Z from hub centre (local), rotation +Y (forward) positive = clockwise from behind;
    chord leading edge toward +X (direction of motion) for blade1."""
    mb = MeshBuf()
    rs = [r0, 0.24, 0.36, 0.55, 0.80, 1.05, 1.30, 1.55, 1.72, 1.80, 1.86, 1.90, 1.925]
    rings = []
    tip_start = None
    for idx, r in enumerate(rs):
        f = r / R
        chord = interp_table([(0.08, (0.12,)), (0.13, (0.13,)), (0.25, (0.24,)), (0.45, (0.275,)), (0.70, (0.255,)),
                              (0.90, (0.19,)), (0.965, (0.15,)), (0.985, (0.11,)), (1.0, (0.05,))], f)[0]
        tc = interp_table([(0.08, (0.9,)), (0.15, (0.45,)), (0.3, (0.16,)), (0.6, (0.09,)), (1.0, (0.06,))], f)[0]
        beta = math.radians(interp_table([(0.08, (60,)), (0.3, (48,)), (0.7, (30,)), (1.0, (22,))], f)[0])
        tdir = V((math.cos(beta), math.sin(beta), 0))     # TE->LE: tangent (+X) and forward (+Y)
        ndir = V((-math.sin(beta), math.cos(beta), 0))    # thrust-side normal
        pts = []
        n = 8
        for k in range(n):
            a = 2 * math.pi * k / n
            x = 0.5 * math.cos(a)                # -0.5..0.5 along chord
            yv = 0.5 * tc * math.sin(a) * (1.0 + 0.3 * math.cos(a))
            pts.append(V((0, 0, r)) + tdir * (x * chord) + ndir * (yv * chord))
        rings.append(pts)
        if r >= 1.72 and tip_start is None:
            tip_start = idx
    nseg = len(rings) - 1

    def fm(i, j):
        return 'prop_tip' if i >= tip_start else 'prop'
    loft(mb, rings, 'prop', face_mat=fm)
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / len(rings[-1]) + V((0, 0, 0.008)), 'prop_tip', V((0, 0, 1)))
    fan_cap(mb, rings[0], sum(rings[0], V()) / len(rings[0]), 'prop', V((0, 0, -1)))
    return mb


def build_prop(side):
    L = 'L' if side < 0 else 'R'
    cx = side * S.NAC_X
    hub_c = V((cx, S.PROP_Y, 0.0))
    hm = MeshBuf()
    cylinder(hm, hub_c + V((0, -0.24, 0)), hub_c + V((0, 0.10, 0)), 0.17, 0.17, N=20, mat='metal_dark')
    dome = [(0.10, 0.17), (0.17, 0.155), (0.23, 0.12), (0.27, 0.07), (0.29, 0.0)]
    rings = [circle_pts(hub_c + V((0, d, 0)), V((0, 1, 0)), max(r, 0.004), 20) for d, r in dome]
    loft(hm, rings, 'metal_dark')
    for k in range(3):     # blade sockets
        a = 2 * math.pi * k / 3
        d = V((math.sin(a), 0, math.cos(a)))
        cylinder(hm, hub_c + d * 0.10, hub_c + d * 0.20, 0.085, N=12, mat='metal_dark')
    hub = Part(f'prop_hub_{L}', f'engine_{L}', hub_c, hm,
               info=dict(spin_axis_local='+Y (Blender) = +Z (Unity) forward', note='clockwise seen from behind (both engines)'))
    blades = []
    bm = blade_mesh()
    for k in range(3):
        ang = 2 * math.pi * k / 3     # blade1 up; blade2 at +120 deg about +Y (toward +X first)
        q = Quaternion(V((0, 1, 0)), ang)
        mb = MeshBuf()
        for p in bm.verts:
            mb.verts.append(hub_c + q @ p)
        mb.faces = [dict(f) for f in bm.faces]
        blades.append(Part(f'prop_{L}_blade{k + 1}', f'prop_hub_{L}', hub_c, mb, frame=q,
                           info=dict(pitch_axis_local='+Z (Blender) = +Y (Unity), radial')))
    return [hub] + blades


# =============================================================================== tail
def stab_station(ax, side, te_override=None):
    le = S.STAB_LE(ax)
    te = te_override if te_override is not None else S.ELEV_TE(min(ax, 3.48))
    chord = le - te
    up = V((0, 0, 1))
    return Station(side * ax, V((side * ax, le, S.STAB_Z + 0.0)), V((0, -1, 0)), up, chord, 0.12, m=0.0)


def build_tail(side):
    L = 'L' if side < 0 else 'R'
    parts = []
    # stabiliser box up to elevator hinge; hinge fraction varies, so compute per station
    xs = [S.STAB_ROOT_X, 0.47, 1.0, 1.6, 2.2, 2.8, 3.19, 3.30, 3.38]   # tip ends inside the fin (3.48 cut through the fin's outer skin)
    mb = MeshBuf()
    sts = []
    for x in xs:
        sts.append(stab_station(x, side))
    # build box ring per station with s_end = hinge fraction
    rings = []
    for st in sts:
        f = (st.le.y - S.ELEV_HINGE_Y) / st.chord
        f = min(f, 0.97)
        rings.append(box_ring(st, f, 10)[0])
    nseg = len(rings[0])
    arcs = [arc_lengths(r)[0] for r in rings]
    loft(mb, rings, 'paint', face_mat=lambda i, j: HINGE_WALL_MAT if j == nseg - 1 else 'paint',
         uvfunc=ring_arc_uv(rings, [st.span for st in sts]))
    section_cap(mb, rings[0], 'structure', V((-side, 0, 0)))
    section_cap(mb, rings[-1], 'paint', V((side, 0, 0)), lambda p: planar_uv(p, V((1, 0, 0))))
    # fixed TE behind hinge outboard of elevator, up to just inside the fin (the old strip ran on to 3.48, through the
    # thin aft rudder; outboard of ~3.37 the trailing edge is ahead of the hinge anyway)
    for xa in ((3.19, 3.26),):
        aft_sts = [stab_station(x, side) for x in xa]
        ar = []
        for st in aft_sts:
            f = min((st.le.y - S.ELEV_HINGE_Y) / st.chord, 0.97)
            ar.append(aft_ring(st, f, 4)[0])
        if aft_sts[0].chord * (1 - min((aft_sts[0].le.y - S.ELEV_HINGE_Y) / aft_sts[0].chord, 0.97)) > 0.05:
            loft(mb, ar, 'paint')
            section_cap(mb, ar[0], 'paint', V((-side, 0, 0)), lambda p: planar_uv(p, V((1, 0, 0))))
            section_cap(mb, ar[-1], 'paint', V((side, 0, 0)), lambda p: planar_uv(p, V((1, 0, 0))))
    stab = Part(f'stab_{L}', 'fus_tail', (side * S.STAB_ROOT_X, -7.6, S.STAB_Z), mb)
    parts.append(stab)
    # elevator
    em = MeshBuf()
    exs = [0.47, 1.0, 1.6, 2.2, 2.6, 2.9, 3.05, 3.19]
    ers = []
    esp = []
    for x in exs:
        st = stab_station(x, side)
        f = (st.le.y - S.ELEV_HINGE_Y) / st.chord + 0.004
        ers.append(aft_ring(st, f, 5)[0])
        esp.append(st.span)
    earcs = [arc_lengths(r)[0] for r in ers]
    loft(em, ers, 'paint', uvfunc=ring_arc_uv(ers, esp))
    section_cap(em, ers[0], 'paint', V((-side, 0, 0)), lambda p: planar_uv(p, V((1, 0, 0))))
    section_cap(em, ers[-1], 'paint', V((side, 0, 0)), lambda p: planar_uv(p, V((1, 0, 0))))
    hp = V((side * 0.47, S.ELEV_HINGE_Y, S.STAB_Z))
    parts.append(Part(f'elevator_{L}', f'stab_{L}', hp, em, frame_from_axes(V((1, 0, 0))),
                      info=dict(hinge_axis_local='+X', note='elevator hinge y=-8.11')))
    # fin + rudder
    fx = side * S.FIN_X
    fm = MeshBuf()
    fsts = []
    for z, le, te in S.FIN_TABLE:
        st = Station(z, V((fx, le, z)), V((0, -1, 0)), V((side, 0, 0)), le - te, 0.13, m=0.0)
        fsts.append(st)
    frings = []
    for st in fsts:
        f = min((st.le.y - S.RUDDER_HINGE_Y) / st.chord, 0.96)
        frings.append(box_ring(st, f, 10)[0])
    nseg = len(frings[0])
    farcs = [arc_lengths(r)[0] for r in frings]
    loft(fm, frings, 'paint', face_mat=lambda i, j: HINGE_WALL_MAT if j == nseg - 1 else 'paint',
         uvfunc=ring_arc_uv(frings, [st.span for st in fsts]))
    section_cap(fm, frings[0], 'paint', V((0, 0, -1)), lambda p: planar_uv(p, V((0, 0, 1))))
    section_cap(fm, frings[-1], 'paint', V((0, 0, 1)), lambda p: planar_uv(p, V((0, 0, 1))))
    parts.append(Part(f'fin_{L}', f'stab_{L}', (fx, -7.6, S.STAB_Z), fm))
    rm = MeshBuf()
    rrings = []
    rsp = []
    for st in fsts[1:-1]:
        f = min((st.le.y - S.RUDDER_HINGE_Y) / st.chord, 0.96) + 0.004
        rrings.append(aft_ring(st, f, 5)[0])
        rsp.append(st.span)
    rarcs = [arc_lengths(r)[0] for r in rrings]
    loft(rm, rrings, 'paint', uvfunc=ring_arc_uv(rrings, rsp))
    section_cap(rm, rrings[0], 'paint', V((0, 0, -1)), lambda p: planar_uv(p, V((0, 0, 1))))
    section_cap(rm, rrings[-1], 'paint', V((0, 0, 1)), lambda p: planar_uv(p, V((0, 0, 1))))
    parts.append(Part(f'rudder_{L}', f'fin_{L}', (fx, S.RUDDER_HINGE_Y, S.STAB_Z), rm,
                      frame_from_axes(V((0, 1, 0)), V((0, 0, 1))) if False else None,
                      info=dict(hinge_axis_local='+Z (Blender) = +Y (Unity)', note='rudder hinge y=-8.12')))
    return parts


# =============================================================================== landing gear
def tyre(mb, center, R, W, r_in, N=32):
    prof = []
    rr = W * 0.42
    for k in range(10):     # rounded tread profile (radial, axial)
        a = -math.pi / 2 + math.pi * k / 9
        prof.append((R - rr + rr * math.cos(a), (W / 2) * math.sin(a)))
    prof = [(r_in, -W * 0.40)] + prof + [(r_in, W * 0.40)]
    rings = []
    for k in range(N):
        phi = 2 * math.pi * k / N
        d = V((0, math.cos(phi), math.sin(phi)))
        rings.append([V(center) + d * r + V((a, 0, 0)) for r, a in prof])
    rings.append(rings[0])
    loft(mb, rings, 'rubber', closed=True)


def wheel(name, parent, center, R, W, hub_r):
    mb = MeshBuf()
    c = V(center)
    tyre(mb, c, R, W, hub_r)
    cylinder(mb, c - V((W * 0.40, 0, 0)), c + V((W * 0.40, 0, 0)), hub_r, N=24, mat='metal_dark')
    cylinder(mb, c + V((W * 0.40, 0, 0)), c + V((W * 0.46, 0, 0)), hub_r * 0.45, N=16, mat='metal_dark')
    cylinder(mb, c - V((W * 0.46, 0, 0)), c - V((W * 0.40, 0, 0)), hub_r * 0.45, N=16, mat='metal_dark')
    # make the geometry exactly symmetric about the axle centre
    return Part(name, parent, c, mb, info=dict(spin_axis_local='+X', note='pivot = axle centre'))


def main_strut(side):
    L = 'L' if side < 0 else 'R'
    piv = mirror_x(S.MAIN_PIVOT, side)
    axle = mirror_x(S.MAIN_AXLE, side)
    mb = MeshBuf()
    W = S.MAIN_WHEEL_W
    top = piv
    yoke = axle + V((0, 0, 0.72))
    cylinder(mb, top + V((0, 0, 0.05)), yoke + V((0, 0, 0.30)), 0.085, N=14)             # oleo cylinder
    cylinder(mb, yoke + V((0, 0, 0.32)), yoke, 0.06, N=12)                                # piston
    box(mb, yoke, (W + 0.20, 0.14, 0.10), 'metal_dark')                                  # fork crown
    for sx in (-1, 1):
        xo = sx * (W / 2 + 0.07)
        cylinder(mb, yoke + V((xo, 0, 0)), axle + V((xo, 0, 0)), 0.04, N=8)              # fork legs
    cylinder(mb, axle - V((W / 2 + 0.11, 0, 0)), axle + V((W / 2 + 0.11, 0, 0)), 0.035, N=10)   # axle
    cylinder(mb, top - V((0.35, 0, 0)), top + V((0.35, 0, 0)), 0.05, N=10)              # trunnion = hinge
    # drag brace (folds with the strut)
    cylinder(mb, top + V((0, 0.0, -0.62)), top + V((0, 0.26, -0.10)), 0.03, N=8)   # short brace, stays in the well when retracted
    # torque links
    cylinder(mb, yoke + V((0, 0.08, 0.30)), yoke + V((0, 0.14, 0.12)), 0.018, N=6)
    cylinder(mb, yoke + V((0, 0.14, 0.12)), yoke + V((0, 0.07, 0.0)), 0.018, N=6)
    strut = Part(f'gear_main_{L}_strut', f'nacelle_{L}', piv, mb,
                 info=dict(hinge_axis_local='+X (Blender) = +X (Unity)', retract_deg_blender=S.MAIN_RETRACT_DEG,
                           note='retracts aft/up into nacelle well'))
    wh = wheel(f'gear_main_{L}_wheel', f'gear_main_{L}_strut', axle, S.MAIN_WHEEL_R, S.MAIN_WHEEL_W, 0.27)
    return [strut, wh]


def nose_strut():
    piv = V(S.NOSE_PIVOT)
    axle = V(S.NOSE_AXLE)
    mb = MeshBuf()
    W = S.NOSE_WHEEL_W
    d = (axle - piv)
    fork_top = axle + V((0, -0.05, 0.50))
    cylinder(mb, piv, piv + (fork_top - piv) * 0.6, 0.065, N=12)
    cylinder(mb, piv + (fork_top - piv) * 0.6, fork_top + V((0, 0, 0.05)), 0.048, N=12)
    box(mb, fork_top, (W + 0.16, 0.12, 0.08), 'metal_dark')
    for sx in (-1, 1):
        xo = sx * (W / 2 + 0.05)
        cylinder(mb, fork_top + V((xo, 0, 0)), axle + V((xo, 0, 0)), 0.03, N=8)
    cylinder(mb, axle - V((W / 2 + 0.08, 0, 0)), axle + V((W / 2 + 0.08, 0, 0)), 0.025, N=8)
    cylinder(mb, piv - V((0.22, 0, 0)), piv + V((0.22, 0, 0)), 0.04, N=10)
    cylinder(mb, piv + V((0, -0.70, 0.10)), piv + d * 0.45, 0.025, N=8)       # drag strut
    strut = Part('gear_nose_strut', 'fus_cockpit', piv, mb,
                 info=dict(hinge_axis_local='+X', retract_deg_blender=S.NOSE_RETRACT_DEG, note='retracts aft into nose well'))
    wh = wheel('gear_nose_wheel', 'gear_nose_strut', axle, S.NOSE_WHEEL_R, S.NOSE_WHEEL_W, 0.17)
    return [strut, wh]


# =============================================================================== armament / glazing
def build_turret():
    c = V(S.TURRET_C)
    mb = MeshBuf()
    cylinder(mb, c + V((0, 0, -0.14)), c + V((0, 0, 0.08)), 0.47, N=32, mat='metal_dark', cap0=False)
    annulus(mb, circle_pts(c + V((0, 0, 0.08)), V((0, 0, 1)), 0.47, 32), circle_pts(c + V((0, 0, 0.08)), V((0, 0, 1)), 0.43, 32),
            'metal_dark', V((0, 0, 1)))
    prof = [(0.0, 0.43), (0.12, 0.425), (0.22, 0.40), (0.30, 0.355), (0.36, 0.29), (0.40, 0.20), (0.42, 0.10), (0.43, 0.0)]
    rings = [circle_pts(c + V((0, 0, 0.08 + h)), V((0, 0, 1)), max(r, 0.003), 32) for h, r in prof]
    loft(mb, rings, 'glass')
    loft(mb, [[p + (c + V((0, 0, 0.08)) - p).normalized() * 0.006 for p in r] for r in rings], 'glass', outward=False)
    tur = Part('turret_dorsal', 'fus_forward', c, mb, info=dict(yaw_axis_local='+Z (Blender) = +Y (Unity)'))
    gm = MeshBuf()
    gp = c + V((0, 0, 0.21))
    for sx in (-1, 1):
        x = sx * 0.12
        box(gm, gp + V((x, 0.05, 0)), (0.10, 0.55, 0.13), 'metal_dark')                 # receiver
        tube(gm, gp + V((x, 0.32, 0)), gp + V((x, 1.30, 0)), 0.028, 0.012, N=10)
        cylinder(gm, gp + V((x, 0.32, 0)), gp + V((x, 0.80, 0)), 0.045, N=10)           # barrel jacket
    guns = Part('turret_dorsal_guns', 'turret_dorsal', gp, gm, info=dict(elev_axis_local='+X'))
    mz = [Part('muzzle_turret_L', 'turret_dorsal_guns', gp + V((-0.12, 1.30, 0))),
          Part('muzzle_turret_R', 'turret_dorsal_guns', gp + V((0.12, 1.30, 0)))]
    return [tur, guns] + mz


def build_tail_guns():
    piv = V((0, -9.42, 0.40))
    mb = MeshBuf()
    box(mb, piv + V((0, 0.05, 0)), (0.40, 0.25, 0.20), 'metal_dark')
    out = []
    for sx, nm in ((-1, 'L'), (1, 'R')):
        x = sx * 0.13
        box(mb, piv + V((x, 0.15, 0)), (0.10, 0.55, 0.12), 'metal_dark')
        tube(mb, piv + V((x, -0.12, 0)), piv + V((x, -1.05, 0)), 0.026, 0.011, N=10)
        cylinder(mb, piv + V((x, -0.12, 0)), piv + V((x, -0.55, 0)), 0.042, N=10)
        out.append(Part(f'muzzle_tail_{nm}', 'tail_guns', piv + V((x, -1.05, 0))))
    return [Part('tail_guns', 'fus_tail', piv, mb, info=dict(note='twin .50, traverse about local Z/X'))] + out


NOSE_GUN_XZ = [(-0.10, 0.56), (0.10, 0.56), (-0.27, 0.42), (0.27, 0.42)]
CANNON_XZ = (-0.40, -0.30)


def build_nose_guns():
    mb = MeshBuf()
    parts = []
    for k, (x, z) in enumerate(NOSE_GUN_XZ):
        ye = fus_exit_y(x, z, 5.0)
        tip = V((x, ye + 0.16, z))
        tube(mb, V((x, 5.05, z)), tip, 0.027, 0.012, N=10)
        cylinder(mb, V((x, 5.05, z)), V((x, ye + 0.02, z)), 0.040, N=10)      # blast tube
        parts.append(Part(f'muzzle_nose_{k + 1}', 'nose_guns', tip))
    ng = Part('nose_guns', 'fus_nose', (0, 5.0, 0.5), mb, info=dict(note='4x .50 cal, fixed'))
    cm = MeshBuf()
    x, z = CANNON_XZ
    ye = fus_exit_y(x, z, 4.6)
    tip = V((x, ye + 0.10, z))
    tube(cm, V((x, 3.40, z)), tip, 0.058, 0.0375, N=14)
    cylinder(cm, V((x, 3.40, z)), V((x, 4.20, z)), 0.085, N=14)               # recoil cylinder
    box(cm, V((x, 2.95, z)), (0.30, 0.90, 0.28), 'metal_dark')                # breech
    can = Part('cannon', 'fus_nose', V((x, 3.40, z)), cm, info=dict(note='75 mm M4, lower left'))
    return [ng, can] + parts + [Part('muzzle_cannon', 'cannon', tip)]


def build_package_guns(side):
    L = 'L' if side < 0 else 'R'
    mb = MeshBuf()
    ys = [1.95, 2.10, 2.40, 2.80, 3.20, 3.45, 3.58]
    depth = [0.0, 0.10, 0.17, 0.19, 0.18, 0.12, 0.0]
    hh = [0.10, 0.22, 0.28, 0.29, 0.28, 0.22, 0.10]
    zc = -0.12
    rings = []
    for y, d, h in zip(ys, depth, hh):
        hw = fus_params(y)[0]
        pts = []
        for k in range(9):
            a = -math.pi / 2 + math.pi * k / 8
            pts.append(V((side * (hw - 0.03 + max(d, 0.004) * math.cos(a) + 0.03 * math.cos(a)), y, zc + h * math.sin(a))))
        for k in range(1, 4):
            pts.append(V((side * (hw - 0.04), y, zc + h - 2 * h * k / 4)))
        rings.append(pts)
    sp = [y for y in ys]
    arcs = [arc_lengths(r)[0] for r in rings]
    loft(mb, rings, 'paint', uvfunc=ring_arc_uv(rings, sp))
    fan_cap(mb, rings[0], sum(rings[0], V()) / len(rings[0]), 'paint', V((0, -1, 0)))
    fan_cap(mb, rings[-1], sum(rings[-1], V()) / len(rings[-1]), 'paint', V((0, 1, 0)))
    parts = []
    for k, z in enumerate((0.01, -0.25)):
        x = side * (fus_params(3.0)[0] + 0.12)
        tip = V((x, 4.12, z))
        tube(mb, V((x, 3.30, z)), tip, 0.027, 0.012, N=10)
        cylinder(mb, V((x, 3.30, z)), V((x, 3.70, z)), 0.040, N=10)
        parts.append(Part(f'muzzle_package_{L}{k + 1}', f'package_guns_{L}', tip))
    return [Part(f'package_guns_{L}', 'fus_cockpit', (side * 0.80, 2.8, -0.12), mb)] + parts


def build_waist(side, holes):
    L = 'L' if side < 0 else 'R'
    qs = holes.get('waist' + L, [])
    pts = [p for o, i, uv in qs for p in o]
    y0, y1 = min(p.y for p in pts), max(p.y for p in pts)
    z0, z1 = min(p.z for p in pts), max(p.z for p in pts)
    mb = MeshBuf()
    nu, nv = 6, 6
    grid = []
    for a in range(nu + 1):
        row = []
        for b in range(nv + 1):
            u, v = a / nu, b / nv
            y, z = lerp(y0, y1, u), lerp(z0, z1, v)
            hw = fus_params(y)[0]
            bump = 0.07 * math.sin(math.pi * u) ** 0.6 * math.sin(math.pi * v) ** 0.6
            row.append(V((side * (hw + 0.002 + bump), y, z)))
        grid.append(row)
    for a in range(nu):
        for b in range(nv):
            q = [grid[a][b], grid[a + 1][b], grid[a + 1][b + 1], grid[a][b + 1]]
            oriented_quad(mb, q, 'glass', V((side, 0, 0)))
            oriented_quad(mb, [p - V((side * 0.006, 0, 0)) for p in q], 'glass', V((-side, 0, 0)))
    # frame strip around the window (paint)
    w = 0.035
    hwm = fus_params((y0 + y1) / 2)[0] + 0.004
    for (ya, za), (yb, zb_) in (((y0, z0), (y1, z0)), ((y1, z0), (y1, z1)), ((y1, z1), (y0, z1)), ((y0, z1), (y0, z0))):
        dy, dz = yb - ya, zb_ - za
        ln = math.hypot(dy, dz)
        ny, nz = -dz / ln * w, dy / ln * w
        q = [V((side * hwm, ya - ny, za - nz)), V((side * hwm, yb - ny, zb_ - nz)), V((side * hwm, yb + ny, zb_ + nz)), V((side * hwm, ya + ny, za + nz))]
        oriented_quad(mb, q, 'paint', V((side, 0, 0)), [(p.y, p.z) for p in q])
    blister = Part(f'waist_blister_{L}', 'fus_rear', (side * hwm, (y0 + y1) / 2, (z0 + z1) / 2), mb)
    gm = MeshBuf()
    mount = V((side * (hwm - 0.35), (y0 + y1) / 2, (z0 + z1) / 2))
    box(gm, mount, (0.45, 0.10, 0.12), 'metal_dark')
    tube(gm, mount + V((side * 0.20, 0, 0)), mount + V((side * 0.62, 0, 0)), 0.026, 0.011, N=10)
    gun = Part(f'waist_gun_{L}', f'fus_rear', mount, gm, info=dict(note='flexible .50 on cradle (cradle in fus_rear)'))
    return [blister, gun]


def build_canopy(holes):
    gm = MeshBuf()
    plate(gm, holes.get('canopy', []), 'glass', 'glass', 'glass')
    glass = Part('canopy_glass', 'fus_cockpit', (0, 3.6, 1.2), gm)
    # frames: transverse at y stations and longitudinal at ring points
    fm = MeshBuf()
    ys = [4.55, 4.15, 3.80, 3.00, 2.75]
    # longitudinal frame lines at ring point indices (top centre, windscreen posts, side-window top)
    js = [RR_HALF, 18, RR_N - 18, 14, RR_N - 14]
    ystations = station_list(4.55, 2.75, REQUIRED_Y)
    for y in ys:
        r = fus_ring(y)
        for j in range(14, RR_N - 14):
            a, b = r[j], r[j + 1]
            frame_bar(fm, a, b, V((0, 1, 0)))
    for j in js:
        pts = [fus_ring(y)[j] for y in ystations]
        for a, b in zip(pts, pts[1:]):
            frame_bar(fm, a, b, None)
    frame = Part('canopy_frame', 'fus_cockpit', (0, 3.6, 1.2), fm)
    return [glass, frame]


def frame_bar(mb, a, b, along_normal_hint, w=0.022, h=0.010):
    """small bar lying on the canopy surface from a to b (outer paint, inner cockpit)."""
    d = (b - a)
    if d.length < 1e-6:
        return
    mid = (a + b) / 2
    out = V((mid.x, 0, mid.z - 0.25))
    out.y = 0
    out = (out - d.normalized() * out.dot(d.normalized())).normalized()
    side = d.normalized().cross(out).normalized() * (w / 2)
    lo, hi = -h, h
    A = [a + side + out * hi, b + side + out * hi, b - side + out * hi, a - side + out * hi]
    B = [a + side + out * lo, b + side + out * lo, b - side + out * lo, a - side + out * lo]
    oriented_quad(mb, A, 'paint', out, [(p.y, p.x * 0.5 + p.z) for p in A])
    oriented_quad(mb, B, 'cockpit', -out)
    oriented_quad(mb, [A[0], A[1], B[1], B[0]], 'paint', side, [(p.y, p.z) for p in (A[0], A[1], B[1], B[0])])
    oriented_quad(mb, [A[3], A[2], B[2], B[3]], 'paint', -side, [(p.y, p.z + 3) for p in (A[3], A[2], B[2], B[3])])
