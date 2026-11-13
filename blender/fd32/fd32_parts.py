"""FD-32 Nimrod exterior (docs/fd32_design.md 5): the Nimrod Mk I v3 generator (blender/nimrod/nimrod_parts.py) run with the FD-32
changes patched in memory. The Nimrod modules are imported, never edited (GA-25X precedent).

Kept from the Mk I: fuselage stations, wing outlines, stagger / gap, tail, cabane / interplane struts, rigging, gear, gun troughs,
headrest, hook (functional + A-frame), every break / inner structure / seam-normal lesson of the v3 / 1.4.x model.
Changed:
  radiator bath + oil cooler   -> sensor-ball bay collar (the ball itself is a fal prop, part `sensor_ball`, retracts into the bay)
  Kestrel exhaust manifolds    -> six flush turbogenerator exhaust ports per side in the old stub positions
  Vickers + ring-and-bead      -> 12.7 mm barrels with slotted jackets in the same troughs; no ring sight
  2-blade wooden prop          -> fal 4-blade composite prop, R 1.50 (all stores launch outside the disc)
  lower wing                   -> flaperons (x 1.00-3.90) with cove / lips / round nose exactly as the Mk I upper ailerons
  rudder                       -> chord x 1.15
  Cooper racks                 -> 4 pylons (x 1.80 / 2.55), hardpoints on the pylon bottom faces
  + windscreen, sliding hood (hinge 10 m below = arc slide), canopy rails, flare dispenser points
"""
import math, os, sys
from mathutils import Vector, Quaternion, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
NIM = os.path.abspath(os.path.join(HERE, '..', 'nimrod'))
V2 = os.path.abspath(os.path.join(HERE, '..', 'v2'))
for p in (HERE, NIM, V2):
    if p not in sys.path:
        sys.path.insert(0, p)
import nimrod_spec as S
import fd32_spec as FS
FS.apply()
from b25h_geom import V, MeshBuf, loft, cylinder, box, circle_pts, fan_cap, oriented_quad, annulus, Station, surface, planar_uv, section_cap
from b25h_parts import Part
import nimrod_structure as ST
import nimrod_v140 as N4
import nimrod_props as PR
import nimrod_parts as NP
import cockpit_kit as K
import internals_r183 as IN
import fd32_canopy183 as CAN

FAL_OPT = os.path.abspath(os.path.join(HERE, '..', '..', 'assets', 'model_fd32', 'src', 'fal', 'opt'))
PR.MAT.update({'prop4': 'pr_prop4', 'sensorball': 'pr_sensor', 'hook_modern': 'pr_hook2', 'throttle': 'pr_throttle', 'throttle_v7': 'pr_throttle'})
_load0 = PR.load


def _load(name):
    p = os.path.join(FAL_OPT, name + '.glb')
    if name in ('prop4', 'sensorball', 'hook_modern', 'throttle', 'throttle_v7'):
        if name not in PR._cache:
            PR._cache[name] = K.read_glb(p)
        return PR._cache[name]
    return _load0(name)


PR.load = _load
EXTRA = {}          # flaperon meshes etc. collected while the Mk I generator runs


# =========================================================================================== sensor bay (replaces the radiator)
def sensor_bay():
    """round 11: the bay round the sensor ball, closed from every side (the belly skin and inner skin are cut open inside BAY_R in
    build_fd32): a collar ring on the belly (bottom face 4 mm below the skin, top face, closed inner / outer edges) and a 4 mm thick liner tube
    from just below the collar up to a cap BAY_DEPTH above the skin (inner + outer faces, bottom rim, cap closed both ways)."""
    mb = MeshBuf()
    zb = ST.fus_z(0.0, FS.BALL_Y, top=False)
    ax = V((0, 0, 1))
    R0, R1, T = FS.BAY_R, FS.BAY_R + 0.045, 0.004
    c = lambda z, r: circle_pts(V((0, FS.BALL_Y, z)), ax, r, 48)
    zlo, ztop = zb - 0.006, zb + FS.BAY_DEPTH
    annulus(mb, c(zb - 0.004, R1), c(zb - 0.004, R0), 'metal_dark', V((0, 0, -1)))          # collar bottom
    annulus(mb, c(zb + 0.002, R1), c(zb + 0.002, R0 + T), 'metal_dark', V((0, 0, 1)))       # collar top (inside the skin)
    loft(mb, [c(zb + 0.014, R1), c(zb - 0.004, R1)], 'metal_dark', smooth=True)            # collar outer edge up into the skin
    loft(mb, [c(zlo, R0), c(ztop, R0)], 'cove', outward=False)                              # liner inner face
    loft(mb, [c(zlo, R0 + T), c(ztop, R0 + T)], 'cove', outward=True)                       # liner outer face
    annulus(mb, c(zlo, R0 + T), c(zlo, R0), 'metal_dark', V((0, 0, -1)))                    # liner bottom rim
    fan_cap(mb, c(ztop, R0), V((0, FS.BALL_Y, ztop)), 'cove', V((0, 0, -1)))               # cap (seen from below)
    fan_cap(mb, c(ztop + 0.003, R0 + T), V((0, FS.BALL_Y, ztop + 0.003)), 'cove', V((0, 0, 1)))
    loft(mb, [c(ztop, R0 + T), c(ztop + 0.003, R0 + T)], 'cove', outward=True)
    return mb


def no_cooler():
    return MeshBuf()


# =========================================================================================== exhaust ports (replace the manifolds)
def exhaust_ports(mb):
    """six flush turbogenerator exhaust ports per side at the Kestrel stub positions (y 1.70 .. 0.40), z ~0.06: a dark grille plate
    5 mm proud of the cowl skin with closed edges (every face outward), sunk 6 mm into the skin."""
    for side in (-1, 1):
        for k in range(6):
            yc = 1.70 - k * 0.26
            z0, z1 = 0.02, 0.10
            ya, yb = yc + 0.07, yc - 0.07
            def sk(y, z, out):
                w = ST.fus_half_width(y, z)
                return V((side * (w + out), y, z))
            o = [sk(ya, z0, 0.005), sk(ya, z1, 0.005), sk(yb, z1, 0.005), sk(yb, z0, 0.005)]
            i = [sk(q.y, q.z, -0.006) for q in o]
            c = sum(o, V()) / 4
            oriented_quad(mb, o, 'exhaust', V((side, 0, 0)))
            for a_, b_ in zip(range(4), [1, 2, 3, 0]):
                mid = (o[a_] + o[b_]) / 2
                oriented_quad(mb, [o[a_], o[b_], i[b_], i[a_]], 'metal_dark', mid - c)


# =========================================================================================== 12.7 mm guns
def guns_127():
    mb = MeshBuf()
    for side in (-1, 1):
        x = side * S.GUN_X
        zc = S.GUN_Z - 0.005
        cylinder(mb, V((x, -0.02, zc)), V((x, 0.97, zc)), FS.GUN_R, N=12, mat='gunmetal')
        cylinder(mb, V((x, 0.97, zc)), V((x, 1.02, zc)), FS.GUN_R * 1.5, N=12, mat='gunmetal')             # flash suppressor
        cylinder(mb, V((x, 0.06, zc)), V((x, 0.78, zc)), FS.JACKET_R, N=14, mat='gunmetal')                 # barrel jacket
        for k in range(9):                                                                                   # cooling slots
            yy = 0.12 + k * 0.07
            box(mb, (x, yy, zc + FS.JACKET_R), (0.012, 0.035, 0.004), 'metal_dark')
        box(mb, (x, -0.165, S.GUN_Z + 0.005), (0.07, 0.27, 0.09), 'gunmetal')                               # receiver under the decking (ends ahead of the panel)
    return mb


# =========================================================================================== lower panel with flaperon
def lower_panel_fd32(side):
    """the Mk I lower panel rebuilt with the upper aileron's cove / lip / nose construction (nimrod_parts.upper_panel) over the
    flaperon span FS.FLAP_LO_X; root ring = full_ring (the root fillet follows it)."""
    mb = MeshBuf()
    F0, F1 = FS.FLAP_LO_X
    xs = sorted({S.LO_ROOT_X, 0.70, F0, 1.40, FS.PYLONS['inner'] - 0.2, FS.PYLONS['inner'] + 0.2, FS.PYLONS['outer'] - 0.2,
                 FS.PYLONS['outer'] + 0.2, S.STRUT_X_LO, S.STRUT_X, F1, 4.05, 4.2, 4.32, 4.40, S.LO_TIP_X})
    sts = [NP.lo_station(ax, side) for ax in xs]
    if side < 0:
        sts = list(reversed(sts))
    out_dir = V((side, 0, 0))
    inb = [s_ for s_ in sts if abs(s_.span) <= F0 + 1e-4]
    outb = [s_ for s_ in sts if abs(s_.span) >= F0 - 1e-4]
    # inboard of the flaperon: the Mk I construction (box ring to 0.999, the Mk I root fillet ring), capped at F0 = the flaperon bay inner rib
    if side > 0:
        surface(mb, inb, 0.0, 0.999, n_box=14, hinge_mat='paint', cap1=out_dir, cap_mat='cove')
    else:
        surface(mb, inb, 0.0, 0.999, n_box=14, hinge_mat='paint', cap0=out_dir, cap_mat='cove')
    rings = surface(mb, outb, 0.0, NP.S_WALL, n_box=12, hinge_mat='cove')
    NP.tip_cap(mb, rings[-1] if side > 0 else rings[0], out_dir)
    sel = [s_ for s_ in sts if abs(s_.span) >= F1 - 1e-4]
    rr = surface(mb, sel, NP.S_WALL, 1.0, n_aft=4, front_mat='cove')
    NP.tip_cap(mb, rr[-1] if side > 0 else rr[0], out_dir)
    section_cap(mb, rr[0] if side > 0 else rr[-1], 'cove', -out_dir)
    am = MeshBuf()
    asel = [s for s in sts if F0 - 1e-4 <= abs(s.span) <= F1 + 1e-4]
    hs = [s.point(S.AIL_HINGE_S, True) * 0.5 + s.point(S.AIL_HINGE_S, False) * 0.5 for s in asel]
    hinge_in = hs[0] if side > 0 else hs[-1]
    sto = NP.wing_station(side * F1, S.LO_LE, S.LO_TE, NP.lower_z(F1))
    hinge_out = sto.point(S.AIL_HINGE_S, True) * 0.5 + sto.point(S.AIL_HINGE_S, False) * 0.5
    ax_ = hinge_out - hinge_in
    s0 = lambda st: max(S.AIL_HINGE_S + 0.012, NP.axis_at(st, S.AIL_HINGE_S, hinge_in, ax_)[1] + 0.012 / st.chord)
    bsel = list(asel)
    bsel[0] = NP.lo_station(abs(asel[0].span) + 0.006 * (1 if abs(asel[0].span) < abs(asel[-1].span) else -1), side)
    bsel[-1] = NP.lo_station(abs(asel[-1].span) + 0.006 * (1 if abs(asel[-1].span) < abs(asel[0].span) else -1), side)
    NP.cs_body(am, bsel, s0)
    for up_ in (True, False):
        NP.lip(mb, asel, NP.S_WALL, lambda st: NP.axis_at(st, S.AIL_HINGE_S, hinge_in, ax_)[1] - 0.008 / st.chord, up_)
    nose = NP.nose_mesh2(bsel, S.AIL_HINGE_S, s0, hinge_in, ax_, lambda st: NP.S_WALL, rf=0.86)
    EXTRA[('flaperon', side)] = (am, nose, hinge_in, hinge_out)
    return mb, (sts[0] if side > 0 else sts[-1])


_root_fillet0 = NP.root_fillet


def root_fillet_fd32(root_st, s_end, side, inner_fn, n_box=14, name_seed=1, ring=None):
    if ring is None and abs(abs(root_st.span) - S.LO_ROOT_X) < 1e-4:
        ring = NP.full_ring(root_st)            # the FD-32 lower panel's root ring
    return _root_fillet0(root_st, s_end, side, inner_fn, n_box=n_box, name_seed=name_seed, ring=ring)


# =========================================================================================== propeller (fal 4-blade)
def build_prop_fd32():
    """fal 4-blade composite prop: axis = the model's smallest extent, forward = the spinner-tip end, scaled to R 1.50; faces split
    into the hub (radius < 0.27 m: spinner + blade roots) and four blades by azimuth (centred on the blade directions)."""
    hub = V((0, S.PROP_Y, 0))
    pts, tris = PR.load('prop4')
    lo, hi = K.bbox(pts)
    ext = hi - lo
    ai = min(range(3), key=lambda i: ext[i])
    cen = (lo + hi) / 2
    def rad_of(p):
        q = V(p) - cen; q[ai] = 0.0
        return q.length
    R_m = max(rad_of(p) for p in pts)
    # spinner tip = the axial extreme closest to the axis
    amin = min(pts, key=lambda p: p[ai]); amax = max(pts, key=lambda p: p[ai])
    fwd_sign = 1.0 if rad_of(amax) < rad_of(amin) else -1.0
    far = [p for p in pts if rad_of(p) > 0.6 * R_m]
    plane = sum(p[ai] for p in far) / len(far)
    s = FS.PROP_R / R_m
    o1, o2 = [i for i in range(3) if i != ai]
    def to_world(p):
        a = (p[ai] - plane) * fwd_sign * s
        u = (p[o1] - cen[o1]) * s; w = (p[o2] - cen[o2]) * s
        return V((u, S.PROP_Y + a, w)) if fwd_sign > 0 else V((-u, S.PROP_Y + a, w))     # keep right-handed
    # blade azimuths from the far points
    import collections
    hist = collections.Counter()
    for p in far:
        q = to_world(p); hist[int(math.degrees(math.atan2(q.z, q.x)) // 10)] += 1
    peaks = sorted(hist, key=lambda k: -hist[k])
    az = []
    for k in peaks:
        a = k * 10 + 5
        if all(abs((a - b + 180) % 360 - 180) > 50 for b in az):
            az.append(a)
        if len(az) == 4:
            break
    az.sort()
    meshes = {'hub': MeshBuf()}
    for k in range(4):
        meshes[k] = MeshBuf()
    # winding: the model -> world map is a pure axis permutation with signs + uniform scale; it is a reflection when its determinant is
    # negative (round 3: v1 only tested fwd_sign and missed the axis swap, so the fal prop came out inside-out)
    e = [to_world(cen + V(tuple(1.0 if i == k else 0.0 for i in range(3)))) - to_world(cen) for k in range(3)]
    mirror = Matrix((e[0], e[1], e[2])).transposed().determinant() < 0
    for vs, uvs in tris:
        w = [to_world(v) for v in vs]
        if mirror:
            w = [w[0], w[2], w[1]]; uvs = [uvs[0], uvs[2], uvs[1]]
        c = (w[0] + w[1] + w[2]) / 3
        r = math.hypot(c.x, c.z)
        if r < 0.27:
            key = 'hub'
        else:
            a = math.degrees(math.atan2(c.z, c.x))
            key = min(range(4), key=lambda i: abs((a - az[i] + 180) % 360 - 180))
        mb = meshes[key]
        if ((w[1] - w[0]).cross(w[2] - w[0])).length < 1e-12:
            continue
        # round 4: the fal atlas UVs of the blade faces wander over the whole atlas (954k of 1M texels) and pick up its light seam bands
        # and white specks (white 'holes' on the blades in r3_prop_back); the blades take the fal gunmetal tile (metal_dark, detail UV,
        # like the stock CI-22 Matte_black blades) and only the hub keeps the fal atlas
        mb.face([mb.v(p) for p in w], 'pr_prop4' if key == 'hub' else 'metal_dark', [tuple(x) for x in uvs], smooth=True)
    # round 6: the round-3 back cone (r 0.245) left a 0.2 m open waist between the cowl ring (r 0.333) and the fal cone base (shot 98):
    # a closed fairing from the cowl ring to the cone base instead (fd32_gear6.spinner_fairing)
    G6.spinner_fairing(meshes['hub'], 2.62, 0.288)
    for mb_ in meshes.values():
        orient_islands(mb_)
    parts = [Part('prop_hub', 'prop', hub, meshes['hub'], info=dict(kind='prop_hub', note='fal 4-blade prop: spinner + blade roots; spin axis = Unity +Z'))]
    for k in range(4):
        a = math.radians(az[k])
        rad = V((math.cos(a), 0, math.sin(a)))
        tang = V((rad.z, 0, -rad.x))
        parts.append(Part(f'prop_blade_{k + 1}', 'prop_hub', hub, meshes[k], frame=NP.frame_x(tang, rad),
                          info=dict(kind='prop_blade', azimuth_deg=round(az[k], 1), note='fal blade; local +Y (Unity) = radial')))
    return parts


def orient_islands(mb, min_faces=4):
    """every closed-ish island of a MeshBuf faces outward: flip an island whose signed volume (about its own centroid) is negative.
    Safety net for imported (fal / tripo) shells after any coordinate map (round 3: inside-out prop)."""
    adj = {}
    for fi, f in enumerate(mb.faces):
        for vi in f['idx']:
            adj.setdefault(vi, []).append(fi)
    seen = set(); flipped = 0
    for f0 in range(len(mb.faces)):
        if f0 in seen:
            continue
        st, isl = [f0], []
        seen.add(f0)
        while st:
            fi = st.pop(); isl.append(fi)
            for vi in mb.faces[fi]['idx']:
                for fj in adj[vi]:
                    if fj not in seen:
                        seen.add(fj); st.append(fj)
        if len(isl) < min_faces:
            continue
        c = sum((mb.verts[vi] for fi in isl for vi in mb.faces[fi]['idx']), V()) / sum(len(mb.faces[fi]['idx']) for fi in isl)
        vol = 0.0
        for fi in isl:
            P = [mb.verts[vi] - c for vi in mb.faces[fi]['idx']]
            for k in range(1, len(P) - 1):
                vol += P[0].dot(P[k].cross(P[k + 1]))
        if vol < 0:
            for fi in isl:
                f = mb.faces[fi]
                f['idx'] = list(reversed(f['idx']))
                if f.get('uv'):
                    f['uv'] = list(reversed(f['uv']))
            flipped += 1
    return flipped


# =========================================================================================== pylons
def pylon_mesh(side, x):
    """faired pylon under the lower wing: symmetric aerofoil outline in plan (thickness 0.07), from 15 mm inside the lower skin
    down to PYLON_DEPTH below the lowest skin point; flat bottom face = the stock hardpoint face."""
    mb = MeshBuf()
    st = NP.lo_station(x, side)
    yf, yr = FS.PYLON_Y + 0.36, FS.PYLON_Y + 0.36 - FS.PYLON_CHORD
    n = 10
    ys = [yf - (yf - yr) * (1 - math.cos(math.pi * k / n)) / 2 for k in range(n + 1)]
    def half_t(f):
        return 0.035 * 5 * (0.2969 * math.sqrt(max(f, 0)) - 0.126 * f - 0.3516 * f ** 2 + 0.2843 * f ** 3 - 0.1036 * f ** 4) / 0.6 + 0.004
    def zs(y):
        sc = (st.le.y - y) / (st.le.y - (st.le + st.cdir * st.chord).y)
        return NP.surf_pt(st, min(max(sc, 0.0), 1.0), False).z
    zlow = min(zs(y) for y in ys)
    zb = zlow - FS.PYLON_DEPTH
    top, bot = [], []
    for y in ys:
        f = (yf - y) / (yf - yr)
        t = half_t(f)
        top.append((y, t, zs(y) + 0.015))
    ring_t = [V((side * x + t, y, z)) for y, t, z in top] + [V((side * x - t, y, z)) for y, t, z in reversed(top[1:-1])]
    ring_b = [V((p.x, p.y, zb)) for p in ring_t]
    loft(mb, [ring_t, ring_b], 'paint', uvfunc=lambda ci, cj, j: (cj * 0.05, (ring_t if ci == 0 else ring_b)[cj].z))
    fan_cap(mb, ring_b, sum(ring_b, V()) / len(ring_b), 'metal_dark', V((0, 0, -1)))
    fan_cap(mb, ring_t, sum(ring_t, V()) / len(ring_t), 'structure', V((0, 0, 1)))
    return mb, V((side * x, FS.PYLON_Y, zb))


# =========================================================================================== round 6: semi-retractable gear (fd32_gear6)
import fd32_gear6 as G6


def main_gear_fd32(side):
    """round 6: the aft-swinging cantilever leg (fd32_gear6.main_gear); the pivot is recorded for the part pivot"""
    st, wh, ax, root = G6.main_gear(side)
    main_gear_fd32.root[side] = root
    return st, wh, ax


main_gear_fd32.root = {}
gear_pivot = G6.gear_pivot


def stretch(parts, ycut, dl):
    """lengthen the fuselage: every vertex and pivot aft of ycut moves dl aft (the fuselage / lining segments that straddle ycut stretch;
    nothing else straddles it: lower-wing TE -1.00, fillets end there). Connectivity records move with them."""
    n = 0
    for p in parts:
        if p.pivot.y < ycut:
            p.pivot = V((p.pivot.x, p.pivot.y - dl, p.pivot.z))
        if p.mesh is not None:
            for v in p.mesh.verts:
                if v.y < ycut:
                    v.y -= dl
                    n += 1
        if p.info and 'attach' in p.info:
            p.info['attach'] = [(o, (q[0], q[1] - dl if q[1] < ycut else q[1], q[2]), t) for o, q, t in p.info['attach']]
    return n


def hook_mesh_fd32():
    """modern arrester hook (fal hook_modern) on the functional hinge, modelled stowed: shank stretched along the functional length,
    the hinge fitting and the head kept at their own scale. Long axis -> hinge-to-tip; the head = the end with the deeper section."""
    mb = MeshBuf()
    pts, tris = PR.load('hook_modern')
    lo, hi = K.bbox(pts)
    ext = hi - lo
    ai = max(range(3), key=lambda i: ext[i])
    others = [i for i in range(3) if i != ai]
    dep = max(others, key=lambda i: ext[i])
    lat = [i for i in others if i != dep][0]

    def depth_at(t):
        sel = [p for p in pts if abs(p[ai] - t) < ext[ai] * 0.08]
        return (max(p[dep] for p in sel) - min(p[dep] for p in sel)) if sel else 0
    head_hi = depth_at(hi[ai] - ext[ai] * 0.08) > depth_at(lo[ai] + ext[ai] * 0.08)
    p0 = V(S.HOOK_PIVOT)
    a = math.radians(S.HOOK_STOW_UP)
    d = V((0, -math.cos(a), math.sin(a)))
    up = V((0, math.sin(a), math.cos(a)))
    cs = 0.16 / ext[dep]                       # the head ~0.16 m deep
    Lm = ext[ai]
    end_len = 0.15 * Lm * cs

    def along(t):
        f = (t - lo[ai]) / Lm if head_hi else (hi[ai] - t) / Lm      # 0 = hinge end, 1 = head end
        if f < 0.15:
            return f / 0.15 * end_len
        if f > 0.85:
            return S.HOOK_LEN - (1 - f) / 0.15 * end_len
        return end_len + (f - 0.15) / 0.70 * (S.HOOK_LEN - 2 * end_len)
    c = (lo + hi) / 2
    # head curve points DOWN when stowed (it hangs under the bar): flip the depth axis when the head's mass is on the + side
    head_sel = [p for p in pts if (p[ai] > hi[ai] - ext[ai] * 0.15) == head_hi]
    sgn = -1.0 if (sum(p[dep] for p in head_sel) / max(len(head_sel), 1)) > c[dep] else 1.0
    def to_w(v):
        return p0 + d * along(V(v)[ai]) + up * sgn * (V(v)[dep] - c[dep]) * cs + V((1, 0, 0)) * (V(v)[lat] - c[lat]) * cs
    e = [to_w(c + V(tuple(0.01 if i == k else 0.0 for i in range(3)))) - to_w(c) for k in range(3)]
    mirror = Matrix((e[0], e[1], e[2])).transposed().determinant() < 0
    for vs, uvs in tris:
        w = [to_w(v) for v in vs]
        if mirror:
            w = [w[0], w[2], w[1]]; uvs = [uvs[0], uvs[2], uvs[1]]
        if ((w[1] - w[0]).cross(w[2] - w[0])).length < 1e-12:
            continue
        mb.face([mb.v(q) for q in w], 'pr_hook2', [tuple(x) for x in uvs], smooth=True)
    orient_islands(mb)
    return mb


# =========================================================================================== round 3: canopy (closed, jettisoned whole)
def canopy_section(y):
    """(half width at the sill, top z) of the canopy at station y (front arch .. rear end on the turtle deck)."""
    yf, yr = FS.HOOD_Y
    f = (yf - y) / (yf - yr)
    top = FS.HOOD_TOP_Z - 0.03 * (1 - math.sin(math.pi * min(f / 0.4, 1.0) * 0.5))
    if f > 0.70:                                      # round 3: the taper starts behind the stock seat's head box
        deck = ST.fus_z(0.0, yr, top=True)
        top = top + (deck + 0.01 - top) * ((f - 0.70) / 0.30) ** 1.5
    hw = FS.HOOD_HW
    if f > 0.72:
        hw = FS.HOOD_HW * (1 - 0.5 * ((f - 0.72) / 0.28) ** 1.4)
    return hw, top


def canopy_ring(y, off=0.0, N=16):
    hw, top = canopy_section(y)
    sill = FS.HOOD_SILL_Z
    pts = []
    for k in range(N + 1):
        a = math.pi * k / N
        ex = 3.4                                     # round 3: fuller shoulders (stock seat head box)
        cx = math.cos(a); sz = math.sin(a)
        x = (hw + off) * math.copysign(abs(cx) ** (2 / ex), cx)
        z = sill + (top - sill + off) * (abs(sz) ** (2 / ex))
        pts.append(V((x, y, z)))
    return pts


def _outn(p):
    # round 3: the centre drops with points at / below the sill so the frame offset there is sideways (thin posts stay boxes)
    return (p - V((0, p.y, min(FS.HOOD_SILL_Z, p.z - 0.05)))).normalized()


def band(mb, rings, ka, kb, off=0.004, mat='metal_dark'):
    """a closed frame band ON the shell (ring indices ka..kb of each ring): outer face `off` out, inner face 1 mm out, closed sides
    and ends. It never leaves the shell outline (no spurs)."""
    out_ = [[p + _outn(p) * off for p in r[ka:kb + 1]] for r in rings]
    inn_ = [[p + _outn(p) * 0.001 for p in r[ka:kb + 1]] for r in rings]
    for i in range(len(rings) - 1):
        for j in range(len(out_[0]) - 1):
            q = [out_[i][j], out_[i][j + 1], out_[i + 1][j + 1], out_[i + 1][j]]
            oriented_quad(mb, q, mat, _outn(sum(q, V()) / 4))
            q = [inn_[i][j], inn_[i][j + 1], inn_[i + 1][j + 1], inn_[i + 1][j]]
            oriented_quad(mb, q, mat, -_outn(sum(q, V()) / 4))
    for i, nb in ((0, 1), (len(rings) - 1, len(rings) - 2)):     # ring-direction ends: face away from the neighbouring ring
        for j in range(len(out_[0]) - 1):
            q = [out_[i][j], out_[i][j + 1], inn_[i][j + 1], inn_[i][j]]
            oriented_quad(mb, q, mat, (out_[i][j] + out_[i][j + 1]) - (out_[nb][j] + out_[nb][j + 1]))
    for j in (0, len(out_[0]) - 1):                               # side edges
        for i in range(len(rings) - 1):
            q = [out_[i][j], out_[i + 1][j], inn_[i + 1][j], inn_[i][j]]
            other = out_[i][1 if j == 0 else j - 1]
            oriented_quad(mb, q, mat, out_[i][j] - other)


def edge_strip(rings, side, width):
    """rings cut to a strip `width` m wide along the ring from its first (side 0) or last (side 1) point: thin frame rails / posts
    (round 3 v2 look: a ring segment is ~7.5 cm, too heavy for a modern frame)"""
    out = []
    for r in rings:
        pts = r if side == 0 else r[::-1]
        acc, strip = 0.0, [pts[0]]
        for a_, b_ in zip(pts, pts[1:]):
            L = (b_ - a_).length
            if acc + L >= width:
                strip.append(a_.lerp(b_, (width - acc) / L)); break
            acc += L; strip.append(b_)
        out.append(strip if side == 0 else strip[::-1])
    n = min(len(r) for r in out)
    return [r[:n] if side == 0 else r[-n:] for r in out]


def build_canopy_fd32():
    """windscreen (fixed glass + flat frame bands) and the canopy (glass shell + flat frame bands + rear plate: one closed piece,
    jettisoned whole; tilts up on the ground about the back of its rear end)."""
    ws_g, ws_f, cf, cg = MeshBuf(), MeshBuf(), MeshBuf(), MeshBuf()
    yf, yr = FS.HOOD_Y
    N = 16
    front = canopy_ring(yf, -0.002, N)

    def deck(x, y):
        return ST.fus_z(abs(x), y, top=True) - 0.003
    base = [V((p.x * 0.96, FS.WS_BASE_Y, max(deck(p.x * 0.96, FS.WS_BASE_Y), FS.HOOD_SILL_Z - 0.03))) for p in front]
    midr = [a_.lerp(b_, 0.5) + V((0, 0, 0.01)) for a_, b_ in zip(base, front)]
    wrings = [base, midr, front]
    loft(ws_g, wrings, 'glass', closed=False)
    # round 3 v2 look: one-piece wrap windscreen (no centre post), 35 mm side posts, 30 mm arch (stock canopies: thin frames)
    for sd in (0, 1):
        r_ = edge_strip(wrings, sd, 0.035)
        band(ws_f, r_, 0, len(r_[0]) - 1)
    band(ws_f, [canopy_ring(yf + 0.03, -0.002, N), canopy_ring(yf - 0.006, -0.002, N)], 0, N)     # round 7: overlaps the canopy hoop (no sliver)
    # round 7 (in-game 1.5.2: bright unglazed slots beside the panel): side skirts under the windscreen's side edges, from the glass
    # edge down 15 mm into the fuselage deck, from the windscreen base aft past the canopy front (closed 4 mm slabs, metal_dark)
    for sd in (0, -1):
        tops = [r[sd] for r in wrings] + [canopy_ring(yf - 0.004, -0.002, N)[sd]]   # (the canopy's own skirt starts at yf - 0.005)
        sx = 1 if tops[0].x > 0 else -1
        for t0, t1 in zip(tops, tops[1:]):
            b0 = V((t0.x, t0.y, ST.fus_z(min(abs(t0.x), 0.9 * ST.fus_params(t0.y)[0]), t0.y, top=True) - 0.015))
            b1 = V((t1.x, t1.y, ST.fus_z(min(abs(t1.x), 0.9 * ST.fus_params(t1.y)[0]), t1.y, top=True) - 0.015))
            if min(t0.z - b0.z, t1.z - b1.z) < 0.002:
                continue
            io = V((-sx * 0.004, 0, 0))
            oriented_quad(ws_f, [t0, t1, b1, b0], 'metal_dark', V((sx, 0, 0)))
            oriented_quad(ws_f, [t0 + io, t1 + io, b1 + io, b0 + io], 'metal_dark', V((-sx, 0, 0)))
            oriented_quad(ws_f, [t0, t1, t1 + io, t0 + io], 'metal_dark', V((0, 0, 1)))
            oriented_quad(ws_f, [b0, b1, b1 + io, b0 + io], 'metal_dark', V((0, 0, -1)))
            oriented_quad(ws_f, [t0, b0, b0 + io, t0 + io], 'metal_dark', t0 - t1)
            oriented_quad(ws_f, [t1, b1, b1 + io, t1 + io], 'metal_dark', t1 - t0)
    ys = [yf - 0.005 - (yf - 0.005 - yr) * k / 10 for k in range(11)]
    rings = [canopy_ring(y, 0.0, N) for y in ys]
    loft(cg, rings, 'glass', closed=False)
    # round 3 v2 look: a bubble with a 30 mm front hoop, a 40 mm rear hoop and 30 mm sill rails (was 3 hoops ~14 cm and ~7.5 cm rails)
    band(cf, [canopy_ring(ys[0], 0.0, N), canopy_ring(ys[0] - 0.03, 0.0, N)], 0, N)
    band(cf, [canopy_ring(ys[-1] + 0.04, 0.0, N), rings[-1]], 0, N)
    for sd in (0, 1):
        r_ = edge_strip(rings, sd, 0.03)
        band(cf, r_, 0, len(r_[0]) - 1)
    # round 3 v2 look: a skirt from each sill rail down to the deck skin (the tub rim showed through the gap under the glass)
    for sd in (0, 1):
        top_ = [(r[0] if sd == 0 else r[-1]) for r in rings[:-1]]
        sx = 1 if top_[0].x > 0 else -1
        bot = [V((p.x, p.y, min(p.z, ST.fus_z(abs(p.x), p.y, top=True) + 0.002))) for p in top_]
        for (t0, t1, b0, b1) in zip(top_, top_[1:], bot, bot[1:]):
            if min(t0.z - b0.z, t1.z - b1.z) < 0.002:
                continue
            io = V((-sx * 0.004, 0, 0))
            oriented_quad(cf, [t0, t1, b1, b0], 'metal_dark', V((sx, 0, 0)))
            oriented_quad(cf, [t0 + io, t1 + io, b1 + io, b0 + io], 'metal_dark', V((-sx, 0, 0)))
            oriented_quad(cf, [b0, b1, b1 + io, b0 + io], 'metal_dark', V((0, 0, -1)))
            oriented_quad(cf, [t0, b0, b0 + io, t0 + io], 'metal_dark', t0 - t1)       # segment ends closed (each segment a box)
            oriented_quad(cf, [t0, t1, t1 + io, t0 + io], 'metal_dark', V((0, 0, 1)))
            oriented_quad(cf, [t1, b1, b1 + io, t1 + io], 'metal_dark', t1 - t0)
    rr = rings[-1]
    cdeck = sum(rr, V()) / len(rr)
    fan_cap(cf, rr, cdeck, 'paint', V((0, -1, 0)))
    rri = [p + V((0, 0.003, 0)) for p in rr]
    fan_cap(cf, rri, cdeck + V((0, 0.003, 0)), 'paint', V((0, 1, 0)))
    loft(cf, [rr, rri], 'paint', closed=True)                       # rim: the rear plate is a closed 3 mm slab
    build_canopy_fd32.hinge = V((0, yr - 0.005, canopy_section(yr)[1]))      # top of the rear end: everything below it swings forward-up
    return ws_g, ws_f, cf, cg


# =========================================================================================== round 3: gear-down light strips (GA-25X slimelights)
def slimelights():
    out = []
    for s, L in ((-1, 'L'), (1, 'R')):
        mb = MeshBuf()
        y0, y1, z = -0.05, -0.75, -0.30
        pts = []
        for k in range(9):
            y = y0 + (y1 - y0) * k / 8
            pts.append(V((s * (ST.fus_half_width(y, z) + 0.002), y, z)))
        n_ = V((s, 0, 0))
        for a_, b_ in zip(pts, pts[1:]):
            q = [a_ + V((0, 0, -0.012)), b_ + V((0, 0, -0.012)), b_ + V((0, 0, 0.012)), a_ + V((0, 0, 0.012))]
            oriented_quad(mb, q, 'light_off', n_)
            for e0, e1, dz in ((q[0], q[1], -1), (q[2], q[3], 1)):
                oriented_quad(mb, [e0, e1, e1 - n_ * 0.006, e0 - n_ * 0.006], 'light_off', V((0, 0, dz)))
        for p, dy in ((pts[0], 1), (pts[-1], -1)):
            oriented_quad(mb, [p + V((0, 0, -0.012)), p + V((0, 0, 0.012)), p + V((-s * 0.006, 0, 0.012)), p + V((-s * 0.006, 0, -0.012))], 'light_off', V((0, dy, 0)))
        out.append(Part(f'slimelight_fus_{L}', 'fus_center', pts[4], mb, info=dict(kind='gear_light', note='green gear-down strip (stock slimelight_on while the gear is down)')))
    if MORE_STRIPS:
        out += more_strips()
    return out


# 1.8.0 (user: "only one pair, under the cockpit, the worst and least visible place possible"): more strips in the same stock light
# material, where they are seen: rear fuselage sides at mid height, the spine behind the canopy, the upper wing tips (top surface) and both
# sides of the fin. Same section as the first pair (24 mm wide, 6 mm deep, 2 mm proud); each is its own object on the part it sits on.
MORE_STRIPS = True


def _strip(pts, nrms, name, parent):
    mb = MeshBuf()
    w = 0.012
    for (a_, b_), (na, nb) in zip(zip(pts, pts[1:]), zip(nrms, nrms[1:])):
        t = (b_ - a_).normalized()
        sa, sb = na.cross(t).normalized() * w, nb.cross(t).normalized() * w
        A, B = a_ + na * 0.002, b_ + nb * 0.002
        q = [A - sa, B - sb, B + sb, A + sa]
        oriented_quad(mb, q, 'light_off', (na + nb).normalized())
        for e0, e1, sg in ((A - sa, B - sb, -1), (A + sa, B + sb, 1)):
            oriented_quad(mb, [e0, e1, e1 - nb * 0.006, e0 - na * 0.006], 'light_off', (sa + sb).normalized() * sg)
    for p_, n_, t_ in ((pts[0], nrms[0], (pts[0] - pts[1]).normalized()), (pts[-1], nrms[-1], (pts[-1] - pts[-2]).normalized())):
        s_ = n_.cross(t_).normalized() * w; P0 = p_ + n_ * 0.002
        oriented_quad(mb, [P0 - s_, P0 + s_, P0 + s_ - n_ * 0.006, P0 - s_ - n_ * 0.006], 'light_off', t_)
    mid = pts[len(pts) // 2]
    return Part(name, parent, mid, mb, info=dict(kind='gear_light', note='1.8.0 green strip (stock slimelight_on while the gear is down)'))


def more_strips():
    out = []
    # rear fuselage sides at mid height (behind the cockpit, above the lower wing's shadow)
    y0 = S.CENTRE_AFT_Y - 0.15
    for s_, L in ((-1, 'L'), (1, 'R')):
        pts, nrs = [], []
        for k in range(9):
            y = y0 - 0.85 * k / 8; z = 0.12
            x = ST.fus_half_width(y, z)
            p = V((s_ * x, y, z)); pts.append(p)
            dz = (ST.fus_half_width(y, z + 0.01) - ST.fus_half_width(y, z - 0.01)) / 0.02
            nrs.append(V((s_, 0, -s_ * dz * s_)).normalized() if abs(dz) < 5 else V((s_, 0, 0)))
        out.append(_strip(pts, nrs, f'slimelight_side_{L}', 'fus_rear'))
    # spine behind the canopy (top centreline of the turtle deck)
    pts, nrs = [], []
    ys0 = FS.HOOD_Y[1] - 0.20 if not CAN.ENABLED else S.CENTRE_AFT_Y - 0.15     # 1.8.3: all of it on fus_rear's spine
    for k in range(9):
        y = ys0 - 1.0 * k / 8
        if CAN.ENABLED:                                        # 1.8.3: on the raised spine's top line
            sec, c_ = CAN.spine_section(y)
            top = max(sec, key=lambda q: q.z)
            pts.append(V((0, y, top.z + 0.0005))); nrs.append(V((0, 0, 1)))
        else:
            z = ST.fus_z(0.0, y, top=True)
            pts.append(V((0, y, z))); nrs.append(V((0, 0, 1)))
    out.append(_strip(pts, nrs, 'slimelight_spine', 'fus_rear'))
    # upper wing tips, top surface, chordwise near the tip
    for s_, L in ((-1, 'L'), (1, 'R')):
        ax = S.UP_TIP_X - 0.55
        st = NP.wing_station(s_ * ax, S.UP_LE, S.UP_TE, NP.upper_z(ax))
        pts = [st.point(f, True) for f in (0.15, 0.25, 0.35, 0.45, 0.55, 0.65)]
        nrs = [st.up.normalized() for _ in pts]
        out.append(_strip(pts, nrs, f'slimelight_wing_{L}', f'wing_upper_{L}'))
    # fin, both sides, along the forward third (vertical)
    for s_, L in ((-1, 'L'), (1, 'R')):
        pts, nrs = [], []
        for k in range(7):
            z = 0.42 + 0.48 * k / 6
            d = FS.STRETCH_L if getattr(S, '_fd32_stretched', False) else 0.0      # the fin LE table is pre-stretch, FIN_HINGE is shifted
            le = N4.interp(S.FIN_LE_TABLE, z)
            st = Station(z, V((0, le, z)), V((0, -1, 0)), V((1, 0, 0)), max(le - (S.FIN_HINGE + d), 0.03), N4.FIN_T, m=0.0)
            p = st.point(0.30, True)
            pts.append(V((s_ * abs(p.x), p.y - d, z))); nrs.append(V((s_, 0, 0)))
        out.append(_strip(pts, nrs, f'slimelight_fin_{L}', 'fin'))
    return out


# =========================================================================================== sensor ball (fal)
def sensor_ball_mesh():
    """fal sensor turret, flange up, scaled so the ball is BALL_R; modelled STOWED (centre BALL_Z_STOWED)."""
    mb = MeshBuf()
    pts, tris = PR.load('sensorball')
    lo, hi = K.bbox(pts)
    ext = hi - lo
    s = 2 * FS.BALL_R / max(ext.x, ext.y)
    cen = V(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z + max(ext.x, ext.y) / 2))
    c_w = V((0, FS.BALL_Y, FS.BALL_Z_STOWED))
    Rz = Matrix.Rotation(math.pi, 3, 'Z')
    for vs, uvs in tris:
        w = [c_w + Rz @ ((V(v) - cen) * s) for v in vs]
        if ((w[1] - w[0]).cross(w[2] - w[0])).length < 1e-12:
            continue
        mb.face([mb.v(p) for p in w], 'pr_sensor', [tuple(x) for x in uvs], smooth=True)
    orient_islands(mb)
    return mb, (lo, hi, s)


# =========================================================================================== assemble
def no_fittings(mb):
    return None


def build_exterior():
    """the Mk I generator with the FD-32 changes (round 3: single-leg retractable main gear, fal tailwheel instead of the skid, belly
    hook slot, no lifting hooks). Returns the parts BEFORE the fuselage stretch; build_fd32 stretches them and adds finish_exterior()."""
    N4.radiator_v140 = sensor_bay
    N4.oil_cooler = no_cooler
    NP.add_exhausts = exhaust_ports
    NP.gun_parts = guns_127
    NP.lower_panel = lower_panel_fd32
    NP.build_prop = build_prop_fd32
    NP.main_gear = main_gear_fd32
    NP.centre_fittings = no_fittings
    NP.HOOK_SLOT = True
    NP.RUDDER_BALANCE = False                                  # round 9/10: a 2080s aircraft has no aerial mast / external mass balance
    NP.ENGINE_BODY = IN.fd32_power                             # 1.8.3: turbo-electric power plant in fus_engine_struct (stock internals)
    EXTRA.clear()
    sl = G6.hook_slot(hook_mesh_fd32())                       # round 6: slot from the hook's swept envelope (pre-stretch frame)
    print('[fd32] hook slot y %.3f .. %.3f, half width %.3f (pre-stretch)' % sl)
    if not getattr(NP.fus_stations, '_fd32', False):           # the slot ends are fuselage stations (the Mk I keep() drops whole cells only)
        _fs0 = NP.fus_stations

        def _fs():
            return sorted(set(_fs0()) | {round(NP.SLOT_Y[0], 3), round(NP.SLOT_Y[1], 3)}, reverse=True)
        _fs._fd32 = True
        NP.fus_stations = _fs
    parts = NP.build_exterior()
    drop = {'sight_ringbead', 'hp_bomb_L', 'hp_bomb_R', 'hook_visual', 'hook_fittings', 'gear_tail_skid'}
    parts = [p for p in parts if p.name not in drop]
    for p in parts:
        if p.parent == 'NIMROD1_root':
            p.parent = 'FD32_root'
    by = {p.name: p for p in parts}
    for side, L in ((-1, 'L'), (1, 'R')):
        by[f'gear_main_{L}_strut'].pivot = main_gear_fd32.root[side]
    st, wh, axle = NP.tail_gear()
    tg = by['gear_tail_strut']; tw = by['gear_tail_wheel']
    tg.mesh = st
    tg.pivot = V((0, axle.y, ST.fus_z(0.0, axle.y, top=False) + 0.04))
    tw.mesh = wh
    tw.info = dict(kind='wheel', radius=S.TAILWHEEL_R, note='round 6: FIXED tailwheel (fal wheel), Mk I axle')
    for side, L in ((-1, 'L'), (1, 'R')):
        am, nose, hin, hout = EXTRA[('flaperon', side)]
        axis = (hout - hin).normalized() * side
        parts.append(Part(f'flaperon_{L}', f'wing_lower_{L}', hin, am, frame=NP.frame_x(axis),
                          info=dict(kind='control', hinge_axis=tuple(axis), note='lower-wing flaperon: roll + flap droop (ControlSurface flap mode on a pivot above it)')))
        parts.append(Part(f'flaperon_{L}_nose', f'flaperon_{L}', hin, nose, frame=NP.frame_x(axis),
                          info=dict(kind='control_nose', note='round nose concentric with the hinge; not in the flaperon collider')))
        for kind in ('inner', 'outer'):
            pm, hp = pylon_mesh(side, FS.PYLONS[kind])
            parts.append(Part(f'pylon_{kind}_{L}', f'wing_lower_{L}', (side * FS.PYLONS[kind], FS.PYLON_Y, hp.z + 0.06), pm,
                              info=dict(kind='pylon', note='faired pylon; not in the wing collider')))
            parts.append(Part(f'hp_{kind}_{L}', f'wing_lower_{L}', hp, info=dict(kind='hardpoint', note='pylon bottom face (stock mount convention)')))
        parts.append(Part(f'flare_{L}', 'fus_rear', (side * 0.20, -2.60, ST.fus_z(0.20, -2.60, top=False) - 0.01), info=dict(kind='flare_ejector')))
    for side, L in ((-1, 'L'), (1, 'R')):                      # round 6: trunnion mounts under the lower wing
        mm, mc = G6.gear_mount(side)
        parts.append(Part(f'gear_mount_{L}', f'wing_lower_{L}', mc, mm, info=dict(kind='gear_mount', note='round 6: trunnion lug + boss of the aft-swinging main leg; not in the wing collider')))
    fc_ = by['fus_center']                                     # the mounts' connectivity records (NP copied ATTACH before they existed)
    known = {(o, q) for o, q, t in fc_.info.get('attach', [])}
    fc_.info['attach'] = fc_.info.get('attach', []) + [r for r in NP.ATTACH if (r[0], r[1]) not in known]
    parts.append(Part('hook_channel', 'fus_rear', V((0, (G6.SLOT['y0'] + G6.SLOT['y1']) / 2, -0.2)), G6.hook_channel(),
                      info=dict(kind='hook_channel', note='round 6: lined channel over the belly hook slot')))
    sb, _ = sensor_ball_mesh()
    parts.append(Part('sensor_mount', 'fus_engine', (0, FS.BALL_Y, FS.BALL_Z_STOWED), None,
                      info=dict(kind='sensor_mount', stowed_z=FS.BALL_Z_STOWED, deployed_z=FS.BALL_Z_DEPLOYED, note='HighLiftDevice moving part (localPosition)')))
    parts.append(Part('sensor_ball', 'sensor_mount', (0, FS.BALL_Y, FS.BALL_Z_STOWED), sb, info=dict(kind='sensor', note='fal EO ball; TargetCam / TargetDetector point')))
    return parts


def finish_exterior(parts):
    """after the stretch (S constants already shifted by FS.apply_stretch): canopy, modern hook mesh, gear-down light strips."""
    by = {p.name: p for p in parts}
    if CAN.ENABLED:                                            # 1.8.3: new canopy, rebuilt opening, spine (fd32_canopy183)
        out, info, hull_mb = CAN.finish(parts)
        finish_exterior.info = info
        finish_exterior.hull_mb = hull_mb
    else:
        ws_g, ws_f, cf, cg = build_canopy_fd32()
        hinge_p = build_canopy_fd32.hinge
        out = [Part('windscreen', 'fus_center', (0, FS.WS_BASE_Y, FS.HOOD_SILL_Z), ws_g, info=dict(kind='glass')),
               Part('windscreen_frame', 'fus_center', (0, FS.WS_BASE_Y, FS.HOOD_SILL_Z), ws_f),
               Part('canopy_slide_hinge', 'fus_center', hinge_p, None, frame=NP.frame_x(V((1, 0, 0))),
                    info=dict(kind='hatch_hinge', open_deg=FS.HOOD_OPEN_DEG, note='Canopy hinge at the back of the canopy: tilts up on the ground, jettisoned whole on ejection')),
               Part('canopy_slide', 'canopy_slide_hinge', hinge_p, cf, frame=NP.frame_x(V((1, 0, 0))), info=dict(kind='canopy', note='canopy frame bands + rear plate (Canopy component)')),
               Part('canopy_slide_glass', 'canopy_slide', hinge_p, cg, frame=NP.frame_x(V((1, 0, 0))), info=dict(kind='glass'))]
        finish_exterior.info = None
        finish_exterior.hull_mb = None
    th = by['tailhook']
    th.mesh = hook_mesh_fd32()
    th.info = dict(th.info or {}, note='round 6: modern hook (fal); hinge near the CG height (Mk I line-of-pull lesson), runs in a belly slot computed from its swept envelope')
    return out + slimelights()
