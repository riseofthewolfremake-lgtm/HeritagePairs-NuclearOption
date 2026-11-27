"""Nimrod model + cockpit checks (B-25H cockpit check set, ported).

  blender --background assets/model_nimrod/nimrod.blend --python blender/nimrod/check_nimrod_model.py -- --out assets/model_nimrod/nimrod_check.json

  * dimensions within 3 % of the measured reference (span 10.29, length 8.18), prop diameter 3.30
  * prop tip ground clearance in the level and the 3-point attitude; spinner clear of the bullet lines
  * gun muzzles (bullet origins) ahead of the prop plane and outside the spinner
  * CG aft of the main axle (taildragger) and ahead of the tailwheel; 3-point angle 12-17 deg
  * tail hook: deployed tip below the 3-point deck line, stowed tip above the level ground
  * rudder bar stirrups face aft and up; throttle lever clear of the quadrant over 0..40 deg
  * pilot legs (stock COIN figure bone pose) clear of every cabin part
  * no floating cabin part; zero z-fight pairs in the cockpit; vertex budget (welded) well under the B-25H
Exit code 1 on any failure.
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'v2'))
import nimrod_spec as S
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUTP = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(HERE, '..', '..', 'assets', 'model_nimrod', 'nimrod_check.json')
O = bpy.data.objects
res = {}


def put(name, ok, detail=''):
    res[name] = dict(ok=bool(ok), detail=detail if isinstance(detail, str) else json.dumps(detail, default=str)[:700])
    print('[check] ' + ('PASS ' if ok else 'FAIL ') + name + ' ' + res[name]['detail'][:300], flush=True)


sys.path.insert(0, os.path.join(HERE, '..'))
import atlas_guard as AG   # 1.8.16 guard (first: before any check edits a mesh)
put('1.8.16 livery atlas == texture manifest (skin / liveries / damage painted on this atlas; re-bake the textures when it fails)', *AG.check_row(os.path.join(HERE, '..', '..', 'assets', 'textures_nimrod', 'nimrod_atlas_manifest.json')))


def wv(o):
    return [o.matrix_world @ v.co for v in o.data.vertices]


def bvh_of(objs):
    vs, fs = [], []
    for o in objs:
        b = len(vs)
        vs += wv(o)
        fs += [tuple(i + b for i in p.vertices) for p in o.data.polygons]
    return BVHTree.FromPolygons(vs, fs) if fs else None


meshes = [o for o in O if o.type == 'MESH' and not o.name.startswith('cooper_')]
allv = [v for o in meshes for v in wv(o)]
span = max(v.x for v in allv) - min(v.x for v in allv)
length = max(v.y for v in allv) - min(v.y for v in allv)
put('span within 3 % of 10.29 m', abs(span - 10.29) / 10.29 < 0.03, f'{span:.3f} m')
put('length within 3 % of 8.18 m', abs(length - 8.18) / 8.18 < 0.03, f'{length:.3f} m')
blades = [o for o in O if o.name.startswith('prop_blade_')]
R = max((v - Vector((0, S.PROP_Y, 0))).length for o in blades for v in wv(o))
put('propeller diameter 3.2-3.4 m (2 blades)', 3.2 <= 2 * R <= 3.4 and len(blades) == 2, f'{2 * R:.3f} m')
# ground clearance
a = math.radians(S.THREE_POINT_DEG)
contact = Vector((0, S.MAIN_AXLE[1], S.GROUND_LEVEL_Z))
def to3pt(p):     # rotate nose-up about the main wheel contact line
    d = p - contact
    return contact + Vector((d.x, d.y * math.cos(a) - d.z * math.sin(a), d.y * math.sin(a) + d.z * math.cos(a)))
tipdown = Vector((0, S.PROP_Y, -R))
put('prop tip clears the ground: level > 0.12 m, 3-point > 0.30 m', tipdown.z - S.GROUND_LEVEL_Z > 0.12 and to3pt(tipdown).z - S.GROUND_LEVEL_Z > 0.30,
    f'level {tipdown.z - S.GROUND_LEVEL_Z:.3f} m, 3-point {to3pt(tipdown).z - S.GROUND_LEVEL_Z:.3f} m')
# muzzles
mz = [O[f'muzzle_gun_{L}'].matrix_world.translation for L in 'LR']
put('bullet origins ahead of the prop plane (> 0.12 m) and outside the spinner', all(m.y - S.PROP_Y > 0.12 and math.hypot(m.x, m.z) > S.SPINNER_R * 0.6 + 0.05 for m in mz),
    [tuple(round(c, 3) for c in m) for m in mz])
# CG
root = O['NIMROD1_root'].matrix_world.translation
put('CG aft of the main axle and ahead of the tailwheel (taildragger)', S.TAIL_AXLE[1] < root.y < S.MAIN_AXLE[1] - 0.15, f'CG y {root.y:.3f}, main axle {S.MAIN_AXLE[1]}, tail {S.TAIL_AXLE[1]}')
put('3-point angle 12-17 deg', 12 <= S.THREE_POINT_DEG <= 17, f'{S.THREE_POINT_DEG:.2f} deg')
tip_dep = Vector(S.HOOK_PIVOT) + Vector((0, -math.cos(math.radians(S.HOOK_DEPLOY)), math.sin(math.radians(S.HOOK_DEPLOY)))) * S.HOOK_LEN
deck_z = S.GROUND_LEVEL_Z + (tip_dep.y - S.MAIN_AXLE[1]) * -math.tan(a)
tip_st = Vector(S.HOOK_PIVOT) + Vector((0, -math.cos(math.radians(S.HOOK_STOW_UP)), math.sin(math.radians(S.HOOK_STOW_UP)))) * S.HOOK_LEN
put('hook: deployed tip below the 3-point deck line, stowed tip under the fuselage and above the ground', tip_dep.z < deck_z and tip_st.z > deck_z + 0.2,
    f'deployed tip z {tip_dep.z:.3f} vs deck {deck_z:.3f}; stowed tip z {tip_st.z:.3f}')
# hook tip below the wheel-contact plane in a level-ish touchdown (1.2.1: the game test caught no wire at -24 deg in a level attitude)
def rot_nose_up(pnt, deg):
    aa = math.radians(deg); d = pnt - contact
    return contact + Vector((d.x, d.y * math.cos(aa) - d.z * math.sin(aa), d.y * math.sin(aa) + d.z * math.cos(aa)))
hk = [round((rot_nose_up(tip_dep, p_).z - S.GROUND_LEVEL_Z) * 1000) for p_ in (0, 2, 4, 6, 8)]
put('hook tip below the wheel-contact plane at 0 / 2 / 4 / 6 / 8 deg pitch (mm above the plane, must be < 0)', all(h < 0 for h in hk), hk)
# 1.2.2 hook: hinge inside fus_rear (TailHook Linecast origin) at the CG height; the stowed bar inside the fuselage section
def fus_sec(y):
    st = sorted(S.FUS, key=lambda r: r[0])
    for a_, b_ in zip(st, st[1:]):
        if a_[0] <= y <= b_[0]:
            f_ = (y - a_[0]) / (b_[0] - a_[0]); return [a_[i] + (b_[i] - a_[i]) * f_ for i in range(1, 4)]
    return None
hp_ = Vector(S.HOOK_PIVOT); sec = fus_sec(hp_.y)
inside_h = sec is not None and hp_.y < S.CENTRE_AFT_Y - 0.10 and sec[2] + 0.10 < hp_.z < sec[1] - 0.10
stow_pts = [hp_ + Vector((0, -math.cos(math.radians(S.HOOK_STOW_UP)), math.sin(math.radians(S.HOOK_STOW_UP)))) * S.HOOK_LEN * f_ for f_ in (0.25, 0.5, 0.75, 1.0)]
stow_in = all((lambda sc: sc is not None and sc[2] + 0.04 < q.z < min(sc[1], S.FIN_ROOT_Z - 0.05 if q.y < S.FIN_LE_ROOT + 0.05 else 9) - 0.04)(fus_sec(q.y)) for q in stow_pts)
put('hook hinge inside fus_rear (>= 0.10 m behind the split, 0.10 m inside top/bottom) and the stowed bar inside the fuselage', inside_h and stow_in,
    f'hinge {tuple(round(c, 3) for c in hp_)} section {[round(c, 3) for c in sec] if sec else None}; stowed tip {tuple(round(c, 3) for c in stow_pts[-1])}')
cgz = O['NIMROD1_root'].matrix_world.translation
lop = [round(rot_nose_up(hp_, d_).z - rot_nose_up(cgz, d_).z, 3) for d_ in (0, 7.5, 15.3)]
put('line of pull (hinge) vs CG: >= -0.25 m at 0 / 7.5 deg (wheel landing), >= -0.50 m at 15.3 deg (3-point; 1.2.1: -0.59 / -0.86 / -1.13 m nosed it over)', lop[0] >= -0.25 and lop[1] >= -0.25 and lop[2] >= -0.50, lop)
# 1.4.0 (user review 2): no rudder bar / pedals in the cockpit, and the floor is whole where they stood (rays down from above the
# old pivot post all meet a front face of the floor / footboards)
ped = [o.name for o in O if o.type == 'MESH' and (('rudder' in o.name and o.name.startswith('cockpit')) or any(ms.name == 'pr_pedals' for ms in o.material_slots))]
fl = bvh_of([O['cockpit_floor'], O['cockpit_interior'], O['fus_center']])
holes_ped = []
for dx in (-0.25, -0.17, -0.08, 0.0, 0.08, 0.17, 0.25):
    for yy in (-0.30, -0.25, -0.205, -0.16, -0.12):
        o_ = Vector((dx, yy, -0.30)); h = fl.ray_cast(o_, Vector((0, 0, -1)), 2.0)
        if h[0] is None or h[1].dot(Vector((0, 0, 1))) <= 0:
            holes_ped.append((dx, yy))
put('no rudder bar / pedals in the cockpit, floor closed under where they stood (35 rays)', not ped and not holes_ped, dict(objects=ped, holes=holes_ped))
# 1.4.1 (user review 3): spinner faces outward (1.4.0 had 448 of 512 inward: see-through hub), and nothing between the eye and any dial
hub = O['prop_hub']; hmw = hub.matrix_world
spm = [i for i, ms in enumerate(hub.material_slots) if ms.material and 'spinner' in ms.material.name.lower()]
sp_polys = [p_ for p_ in hub.data.polygons if p_.material_index in spm]
sp_cen = sum((hmw @ p_.center for p_ in sp_polys), Vector()) / max(len(sp_polys), 1)
sp_in = sum(1 for p_ in sp_polys if (hmw.to_3x3() @ p_.normal).dot(hmw @ p_.center - sp_cen) <= 0)
put('spinner faces outward (no inside-out hub)', sp_polys and sp_in == 0, dict(faces=len(sp_polys), inward=sp_in))
ck_all = bvh_of([o for o in O if o.type == 'MESH' and o.name.startswith('cockpit_') and o.name not in ('cockpit_stick', 'cockpit_throttle')])
eye_ = Vector(S.EYE); blocked = []
for o in O:
    if not o.name.startswith('gauge_'):
        continue
    pts_ = [m.matrix_world @ v.co for m in [o] + list(o.children_recursive) if m.type == 'MESH' for v in m.data.vertices]
    nb = 0
    for t_ in pts_:
        d_ = t_ - eye_
        if ck_all.ray_cast(eye_, d_.normalized(), d_.length - 0.008)[0] is not None:
            nb += 1
    if nb:
        blocked.append((o.name, nb, len(pts_)))
put('every needle vertex seen from the eye with nothing in front (no cross-frame tubes over the panel; 1.4.0: boost 13/18 hidden)', not blocked, blocked)
# throttle sweep (Unity +X rotation = top forward = Blender -X rotation)
STATIC_CK = [o for o in O if o.type == 'MESH' and o.name.startswith('cockpit_') and o.name not in ('cockpit_throttle', 'cockpit_stick', 'cockpit_rudderbar', 'cockpit_seat')]
interior = O['cockpit_interior']
house = bvh_of(STATIC_CK)
th = O['cockpit_throttle']; piv = th.matrix_world.translation
bad = []
for deg in (0, 20, 40):
    M = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-deg), 4, 'X') @ Matrix.Translation(-piv)
    vs = [M @ v for v in wv(th)]
    tb = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in th.data.polygons])
    ov = tb.overlap(house)
    if ov:
        bad.append((deg, len(ov)))
    top = max(vs, key=lambda v: v.z)
put('throttle lever clear of the quadrant/cockpit over 0, 20, 40 deg', not bad, f'intersections at {bad}')
# legs (COIN pilot figure bone offsets, relative to the figure root = eye + (0, 0.0651, -0.7147)) - from the B-25H check
BONES = {'hip': (0.0917, 0.0048, -0.0235), 'knee': (0.1418, 0.4044, -0.0378), 'ankle': (0.1722, 0.5485, -0.4480), 'toe': (0.2090, 0.7623, -0.3900)}
CAB = [o for o in O if o.type == 'MESH' and o.name.startswith(('cockpit_', 'gauge_', 'mfd_')) and o.name != 'cockpit_seat']
CAB += [O['fus_center'], O['fus_engine']]
trees = {o.name: bvh_of([o]) for o in CAB}
eye = Vector(S.EYE); r0 = eye + Vector((0, 0.0651, -0.7147))
legs = []
for side in (-1, 1):
    P = {k: Vector((r0.x + side * x, r0.y + f, r0.z + u)) for k, (x, f, u) in BONES.items()}
    samples = [(P['hip'].lerp(P['knee'], k / 20), 0.07) for k in range(21)] + [(P['knee'].lerp(P['ankle'], k / 20), 0.05) for k in range(21)]
    for n, tb in trees.items():
        if tb is None:
            continue
        w = min(((tb.find_nearest(p)[3] or 9) - rr, tuple(round(c, 3) for c in p)) for p, rr in samples)
        if w[0] < 0:
            legs.append((side, n, round(w[0] * 1000, 1), w[1]))
put('pilot legs (stock COIN figure pose) clear of every cabin part', not legs, legs[:6])
# floating islands
others = {o.name: bvh_of([m for m in CAB if m is not o] + [O['wing_upper_C']]) for o in CAB}
fl_bad = []; nisl = 0
for o in CAB:
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    vis = {}; isls = []
    for v in bm.verts:
        if v.index in vis:
            continue
        st, isl = [v], []
        vis[v.index] = len(isls)
        while st:
            u = st.pop(); isl.append(u.index)
            for e in u.link_edges:
                w_ = e.other_vert(u)
                if w_.index not in vis:
                    vis[w_.index] = len(isls); st.append(w_)
        isls.append(isl)
    bm.free()
    av = wv(o); polys = [tuple(p.vertices) for p in o.data.polygons]
    fisl = [vis[p[0]] for p in polys]
    own = BVHTree.FromPolygons(av, polys) if polys else None
    rest = bvh_of([m for m in CAB if m is not o] + [O['wing_upper_C']])
    for k, isl in enumerate(isls):
        nisl += 1
        ok = False
        iset = set(isl)
        ipolys = [p for p in polys if p[0] in iset]
        opolys = [p for p in polys if p[0] not in iset]
        ib = BVHTree.FromPolygons(av, ipolys) if ipolys else None
        ob_ = BVHTree.FromPolygons(av, opolys) if opolys else None
        if ib is not None and ((rest is not None and ib.overlap(rest)) or (ob_ is not None and ib.overlap(ob_))):
            ok = True
        if not ok:
            for i in isl:
                h = rest.find_nearest(av[i]) if rest else (None, None, None, 9)
                if h[0] is not None and h[3] <= 0.004:
                    ok = True; break
                h2 = ob_.find_nearest(av[i]) if ob_ else (None, None, None, 9)
                if h2[0] is not None and h2[3] <= 0.004:
                    ok = True; break
        if not ok and (o.name in ('cockpit_throttle', 'cockpit_stick', 'cockpit_rudderbar') or o.name.startswith('gauge_')):
            ok = True       # moving controls / needles hang free by design (their mounts are checked separately)
        if not ok:
            fl_bad.append((o.name, len(isl), tuple(round(c, 3) for c in sum((av[i] for i in isl), Vector()) / len(isl))))
put('no floating cabin part (every mesh island within 4 mm of another part)', not fl_bad, dict(islands=nisl, n=len(fl_bad), floating=fl_bad[:14]))
# z-fight: coplanar overlapping faces of different objects/islands in the cockpit box
cv, cf, cown = [], [], []
for o in CAB + [O[n] for n in ('fus_center_struct', 'fus_engine_struct') if n in O]:
    b0 = len(cv); cv += wv(o)
    bm_ = bmesh.new(); bm_.from_mesh(o.data); bm_.verts.ensure_lookup_table()
    lab_ = {}; kk = 0
    for v in bm_.verts:
        if v.index in lab_:
            continue
        st_ = [v]; lab_[v.index] = kk
        while st_:
            u_ = st_.pop()
            for e_ in u_.link_edges:
                w2 = e_.other_vert(u_)
                if w2.index not in lab_:
                    lab_[w2.index] = kk; st_.append(w2)
        kk += 1
    bm_.free()
    for p in o.data.polygons:
        c = o.matrix_world @ p.center
        if abs(c.x) < 0.5 and -1.35 < c.y < -0.05 and -0.6 < c.z < 0.9:
            cf.append(tuple(b0 + i for i in p.vertices)); cown.append((o.name, lab_[p.vertices[0]]))
cb = BVHTree.FromPolygons(cv, cf)
def fnrm(f):
    a_, b_, c_ = cv[f[0]], cv[f[1]], cv[f[2]]
    n = (b_ - a_).cross(c_ - a_)
    return n.normalized() if n.length > 0 else n
pairs = set()
for i, f in enumerate(cf):
    pts = [cv[k] for k in f]
    A = sum(((pts[k] - pts[0]).cross(pts[k + 1] - pts[0])).length / 2 for k in range(1, len(pts) - 1))
    if A < 2.5e-5:
        continue
    c = sum(pts, Vector()) / len(pts); n = fnrm(f)
    for (_co, _no, j, d) in cb.find_nearest_range(c, 0.001):
        if j is None or j == i or cown[j] == cown[i]:
            continue
        if fnrm(cf[j]).dot(n) > 0.999 and abs((c - cv[cf[j][0]]).dot(n)) < 0.0003:
            pairs.add(tuple(sorted((cown[i][0], cown[j][0]))) + (tuple(round(x, 3) for x in c),))
put('zero z-fight pairs in the cockpit (coplanar overlapping faces < 0.3 mm apart, between objects AND between islands of one object; 1.2.3 had 141 in cockpit_panel / cockpit_floor)', not pairs, sorted(pairs)[:12])
# cockpit budget (task: cockpit < ~25k triangles, welded)
ckm = [o for o in O if o.type == 'MESH' and o.name.startswith(('cockpit_', 'gauge_', 'mfd_'))]
ckt = sum(len(p.vertices) - 2 for o in ckm for p in o.data.polygons); ckv = sum(len(o.data.vertices) for o in ckm)
# 2026-11-02 rebuild: + ~820 tris of reversed twins on the seat bucket walls and the lining under the coaming (see-through check); the
# fal rudder bar is 615 tris (procedural v2: 640). Budget 25k -> 26k.
put('cockpit triangle budget (< 26k tris, welded; 1.2.3: 25k)', ckt < 26000, f'{len(ckm)} objects, tris {ckt}, verts {ckv}')
# throttle lever runs in its quadrant slot: hub between the slot walls with clearance, at every sweep angle
qd = O.get('cockpit_quadrant')
if qd is not None:
    gaps = []
    qb = bvh_of([qd])
    for deg in (0, 20, 40):
        M = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-deg), 4, 'X') @ Matrix.Translation(-piv)
        g = min((qb.find_nearest(M @ v)[3] or 9) for v in wv(th))
        gaps.append(round(g * 1000, 1))
    put('throttle lever in its quadrant slot (clearance 0.5-6 mm at 0 / 20 / 40 deg)', all(0.5 <= g <= 6.0 for g in gaps), f'min gap mm {gaps}')
# cockpit view from the eye (1.2.1 game notes: open floor showed the ground, Aldis in the view centre, brown arc / near plane)
VIEW = [o for o in O if o.type == 'MESH' and not o.name.startswith('cooper_') and o.name not in ('windscreen',) and not o.name.startswith('prop_')]
vv, vf, vo = [], [], []
for o in VIEW:
    b0 = len(vv); vv += wv(o)
    for p_ in o.data.polygons:
        vf.append(tuple(b0 + i for i in p_.vertices)); vo.append(o.name)
vb = BVHTree.FromPolygons(vv, vf)
holes = []
nray = 0
for el in range(-15, -90, -5):
    for az in range(0, 360, 6):
        d = Vector((math.sin(math.radians(az)) * math.cos(math.radians(el)), math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
        nray += 1
        hit = vb.ray_cast(eye, d, 50.0)
        # a ray that crosses the sill plane inside the opening enters the cockpit and must stop on a front face; one that passes over
        # the rim leaves the aircraft (sky / ground far away is legitimate) unless it first meets a back face
        t_s = (S.COCKPIT_SILL_Z - eye.z) / d.z
        ps = eye + d * t_s
        inside = S.COCKPIT_Y[0] < ps.y < S.COCKPIT_Y[1] and abs(ps.x) < 0.29
        if hit[0] is None:
            if inside:
                holes.append((az, el, 'no hit'))
        elif hit[1].dot(d) > 0:
            holes.append((az, el, vo[hit[2]], tuple(round(c, 2) for c in hit[0])))
json.dump(holes, open(os.path.join(os.path.dirname(os.path.abspath(OUTP)), 'nimrod_eye_holes.json'), 'w'))
put('closed cockpit from the eye: every downward ray (elev -15..-85) meets a front face (no ground through the floor)', not holes, dict(rays=nray, holes=len(holes), first=holes[:6]))
ck_names = [o for o in O if o.type == 'MESH' and o.name.startswith(('cockpit_', 'gauge_', 'mfd_'))]
cb2 = bvh_of(ck_names)
blk = []
for el in (-2, 0, 2):
    for az in (-2, 0, 2):
        d = Vector((math.sin(math.radians(az)), math.cos(math.radians(az)), math.sin(math.radians(el)))).normalized()
        h = cb2.ray_cast(eye, d, 3.0)
        if h[0] is not None:
            blk.append((az, el, round((h[0] - eye).length, 2)))
put('view centre clear: no cockpit part within +-2 deg of the eye line (Aldis offset right)', not blk, blk)
# 1.2.2: the Aldis must clear the HUD text blocks. Measured on the 1.2.1 game shot ck_air2_fwd (1600x900, ladder 5 deg = 83 px,
# focal ~949 px): right block (vertical speed, altitude, throttle) az +8.4..+18.1, el -4.2..+4.2 deg; left block (speed, alpha,
# G, fuel) az -16.5..-9.6, el -5.4..+4.2 deg. Keep-out = those + ~1 deg. Rays every 0.5 deg must not meet cockpit_aldis.
ab = bvh_of([O['cockpit_aldis']]) if 'cockpit_aldis' in O else None
hud_hits = []
if ab is not None:
    for (a0, a1, e0, e1, nm) in ((7.0, 20.0, -5.0, 5.0, 'right'), (-18.0, -8.0, -6.0, 5.0, 'left')):
        k_a = a0
        while k_a <= a1 + 1e-6:
            k_e = e0
            while k_e <= e1 + 1e-6:
                d = Vector((math.tan(math.radians(k_a)), 1.0, math.tan(math.radians(k_e)))).normalized()
                if ab.ray_cast(eye, d, 3.0)[0] is not None: hud_hits.append((nm, k_a, k_e))
                k_e += 0.5
            k_a += 0.5
put('Aldis clear of the HUD text blocks (right az 7..20 / el -5..5, left az -18..-8 / el -6..5 deg from the eye)', ab is not None and not hud_hits,
    f'{len(hud_hits)} rays hit {hud_hits[:5]}' if ab is not None else 'cockpit_aldis missing')
near = []
for o in ck_names + [O['fus_center'], O['fus_engine']]:
    for v in wv(o):
        dv = v - eye
        if dv.length < 0.20 and dv.y > -0.05:       # forward half-space (+5 cm behind the eye): what the default view frustum can contain
            near.append((o.name, round(dv.length, 3)))
behind = min(((v - eye).length, o.name) for o in ck_names for v in wv(o) if (v - eye).y <= -0.05)
put('nothing inside the 0.2 m camera near plane ahead of the eye (CameraCockpitState nearClipPlane 0.2)', not near, f'{len(near)} verts {near[:4]}; nearest behind the head: {behind[1]} {behind[0]:.3f} m (only seen when looking back)')
# budget
vt = sum(len(o.data.vertices) for o in O if o.type == 'MESH')
tt = sum(len(p.vertices) - 2 for o in O if o.type == 'MESH' for p in o.data.polygons)
put('vertex/triangle budget (1.4.0: + hook A-frame, radiator slats, oil cooler, sights, skid; 2026-11-22: + the open break cavities liners, '
    'cap strips and bay-end walls, about 4.5k tris; 2026-11-27 round 2: + the fus_center bay truss / stringers / wall frames, about 1.5k tris): '
    'welded verts < 52k, tris < 83k (B-25H: 117k tris)', vt < 52000 and tt < 83000, f'verts {vt}, tris {tt}')

# ======================================================================================== 2026-11-02 rebuild (user review 1) checks
# (a) functional geometry unchanged against the 1.2.3 snapshot: every Unity part's own-mesh bounds (collider, CoM, lift point), the
#     wheel bounds (= wheel radius in LandingGear) and every functional pivot / rotation
import mathutils as _mu
FUN = json.load(open(os.path.join(HERE, '..', '..', 'assets', 'model_nimrod', 'nimrod_functional_123.json')))
dev = []; worst = (0, '')
# 1.4.0 documented changes (user review 2): tail planform / fin / rudder re-traced on the reference, elevator hinge moved to the
# reference hinge line (-4.38, horn balances), tail SKID instead of the wheel (contact point unchanged), spinner reshaped, functional
# hook mesh = hidden proxy (the visible A-frame is hook_visual). Limit per part (m) = how far the mesh bounds may move.
DOC140 = {'stab_L': 0.25, 'stab_R': 0.25, 'elevator_L': 0.35, 'elevator_R': 0.35, 'fin': 0.20, 'rudder': 0.15, 'gear_tail_strut': 0.40,
          'gear_tail_wheel': 0.0, 'tailhook': 2.5, 'prop_hub': 0.20}
doc140 = {}
DOC155 = {"gear_main_L_wheel": 0.15, "gear_main_R_wheel": 0.15}   # round 9: the main wheels move 0.15 m forward (y); the strut meshes are covered by DOC140 / tolerance
for n, b in FUN.items():
    if n.startswith('_'):
        continue
    o = O[n]
    if o.type != 'MESH' or o.data is None:
        if n in DOC140:
            doc140[n] = 'no mesh (1.4.0: skid contact frame; radius from the contract)'
            continue
        dev.append((n, 'missing mesh')); continue
    vs = wv(o)
    lo = [min(v[i] for v in vs) for i in range(3)]; hi = [max(v[i] for v in vs) for i in range(3)]
    tol = 0.025
    if n in DOC155:      # round 9 (Heritage Pairs 1.5.5, user: tips over on landings / spawn): main gear 0.15 m forward (nimrod_spec MAIN_AXLE y 0.70 -> 0.85)
        dy = max(abs((lo[1] - b['lo'][1]) - DOC155[n]), abs((hi[1] - b['hi'][1]) - DOC155[n]))
        dxz = max(max(abs(lo[i] - b['lo'][i]), abs(hi[i] - b['hi'][i])) for i in (0, 2))
        doc140[n + ' (1.5.5 axle +0.15)'] = round(max(dy, dxz), 3)
        if 'wheel' in n and (dy > 0.010 or dxz > 0.0015):     # (the 1.2.3 snapshot wheel differs by 7 mm in y from the fal wheel: tolerance 10 mm)
            dev.append((n, '1.5.5 wheel moved other than +0.15 m forward', round(dy, 4), round(dxz, 4)))
        continue
    if n in DOC140:      # 1.4.0 documented changes (user review 2): reported, limited to DOC140[n] metres
        d = max(max(abs(lo[i] - b['lo'][i]), abs(hi[i] - b['hi'][i])) for i in range(3))
        doc140[n] = round(d, 3)
        if d > DOC140[n]:
            dev.append((n, '1.4.0 change above its limit', round(d, 3), DOC140[n]))
        continue
    # documented exception (report): the fal exhaust manifolds stand up to 50 mm further out than the 1.2.3 stub boxes (x only, symmetric)
    ALLOW = {'fus_engine': (0, 0.050)}
    d = 0.0
    for i in range(3):
        di = max(abs(lo[i] - b['lo'][i]), abs(hi[i] - b['hi'][i]))
        if n in ALLOW and ALLOW[n][0] == i:
            di = 0.0 if di <= ALLOW[n][1] else di
        d = max(d, di)
    if 'wheel' in n:       # LandingGear.wheelRadius = mesh bounds extents.y (Unity y = Blender z): the vertical extent must stay exact
        dz = max(abs(lo[2] - b['lo'][2]), abs(hi[2] - b['hi'][2]))
        if dz > 0.0015:
            dev.append((n, 'wheel vertical extent', round(dz, 4)))
    worst = max(worst, (round(d, 4), n))
    if d > tol:
        dev.append((n, round(d, 4), [round(x, 3) for x in lo], [round(x, 3) for x in hi]))
PIV140 = {'elevator_L': 0.40, 'elevator_R': 0.40, 'stab_L': 0.05, 'stab_R': 0.05, 'flash_gun_L': 0.62, 'flash_gun_R': 0.62}   # 1.4.0: elevator pivots on the reference hinge line (-4.38, was -4.17; x along the axis is free), tail 45 mm lower (STAB_Z 0.16), muzzle flash at the jacket muzzle
for n, pv in FUN['_pivots'].items():
    dp = (O[n].matrix_world.translation - Vector(pv)).length if n in O else 0
    if n in PIV140 and dp <= PIV140[n] + 0.02:
        doc140[n + ' pivot'] = round(dp, 3); continue
    if n in O and dp > 0.001:
        dev.append((n, 'pivot', pv, tuple(round(c, 4) for c in O[n].matrix_world.translation)))
# documented 1.3.1 exception: the aileron / elevator hinge axes now follow the straight hinge line (1.2.3 took the outer end on the
# rounded tip station: up to 76 mm off the real hinge); allowed up to 3 deg, reported
ROT_ALLOW = {'aileron_L': 3.0, 'aileron_R': 3.0, 'elevator_L': 3.0, 'elevator_R': 3.0}
rot_changes = {}
for n, q in FUN['_rot'].items():
    if n in O:
        ang = math.degrees(O[n].matrix_world.to_quaternion().rotation_difference(_mu.Quaternion(q)).angle)
        if ang > 0.11:
            rot_changes[n] = round(ang, 2)
            if ang > ROT_ALLOW.get(n, 0.11):
                dev.append((n, 'rotation', round(ang, 2)))
put('functional geometry as 1.2.3: part mesh bounds within 25 mm (colliders, CoM, lift points), wheel vertical extent (= radius) within 1.5 mm, pivots within 1 mm',
    not dev, dict(worst_bounds=worst, deviations=dev[:20], documented_axis_changes_deg=rot_changes, documented_140=doc140))

# (b) connectivity: every strut / cabane / wire / gear-leg / stabiliser-strut end lies within 10 mm of the surface of its target part or
#     inside it (the generator records each end and its targets: nimrod_parts.ATTACH)
EXT = [o for o in O if o.type == 'MESH' and not o.name.startswith(('cockpit_', 'gauge_', 'mfd_', 'cooper_')) and o.name != 'windscreen']
trees_all = {o.name: bvh_of([o]) for o in EXT}
info = json.loads(O['fus_center'].get('b25_info') or '{}')
att = info.get('attach', [])
bad = []


def surf_dist(names, p):
    best = 9.0
    for n in names:
        t = trees_all.get(n)
        if t is None:
            continue
        co, no, idx, d = t.find_nearest(p)
        if co is None:
            continue
        inside = (p - co).dot(no) < 0 and d < 0.15
        best = min(best, 0.0 if inside else d)
    return best


for obj, p, targets in att:
    d = surf_dist(targets, Vector(p))
    if d > 0.010:
        bad.append((obj, [round(c, 3) for c in p], targets, round(d * 1000, 1)))
put(f'connectivity: all {len(att)} strut / cabane / wire / gear-leg / stab-strut ends within 10 mm of (or inside) their target surface', bool(att) and not bad,
    dict(ends=len(att), bad=bad[:10]))
joint = []
for n, tgt in (('wing_lower_L_root', ['fus_center', 'fus_engine']), ('wing_lower_R_root', ['fus_center', 'fus_engine']),
               ('stab_L_root', ['fus_rear']), ('stab_R_root', ['fus_rear']), ('fin', ['fus_rear'])):
    o = O[n]
    vs = wv(o)
    if n == 'fin':
        z0 = min(v.z for v in vs); ring = [v for v in vs if v.z < z0 + 0.002]
    else:
        x0 = min(abs(v.x) for v in vs); ring = [v for v in vs if abs(v.x) < x0 + 0.012]
    dl = [(surf_dist(tgt, v), tuple(round(c, 3) for c in v)) for v in ring]
    d, wpt = max(dl)
    if d > 0.010:
        joint.append((n, round(d * 1000, 1), wpt))
for part, fil in (('wing_lower_L', 'wing_lower_L_root'), ('wing_lower_R', 'wing_lower_R_root'), ('stab_L', 'stab_L_root'), ('stab_R', 'stab_R_root')):
    pv = wv(O[part]); x0 = min(abs(v.x) for v in pv)
    root = [v for v in pv if abs(v.x) < x0 + 0.002]
    t = bvh_of([O[fil]])
    d = max(t.find_nearest(v)[3] for v in root)
    if d > 0.002:
        joint.append((part + ' root vs fillet', round(d * 1000, 1)))
hp_ = Vector(S.HOOK_PIVOT)
co, no, idx, d = trees_all['fus_rear'].find_nearest(hp_)
if not ((hp_ - co).dot(no) < 0):
    joint.append(('hook hinge not inside fus_rear', round(d, 3)))
put('joints: lower-wing and stabiliser root fillets on the fuselage skin (<= 10 mm), fillet = part root section (<= 2 mm), fin root embedded, hook hinge inside',
    not joint, joint)

# (c) no floating objects: every mesh island of every exterior object lies within 10 mm of another island or object
fv, ff, isl_of_face = [], [], []
for o in EXT:
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    lab = {}
    k = 0
    for v in bm.verts:
        if v.index in lab:
            continue
        st_ = [v]; lab[v.index] = k
        while st_:
            u = st_.pop()
            for e in u.link_edges:
                w_ = e.other_vert(u)
                if w_.index not in lab:
                    lab[w_.index] = k; st_.append(w_)
        k += 1
    b0 = len(fv)
    fv += [o.matrix_world @ v.co for v in bm.verts]
    for f in bm.faces:
        ff.append(tuple(b0 + v.index for v in f.verts)); isl_of_face.append((o.name, lab[f.verts[0].index]))
    bm.free()
big = BVHTree.FromPolygons(fv, ff)
groups = {}
for fi, f in enumerate(ff):
    for vi in f:
        groups.setdefault(isl_of_face[fi], set()).add(vi)
floating = []
for key, vis in groups.items():
    ok = False
    vis = sorted(vis)
    step = max(1, len(vis) // 400)
    for vi in vis[::step]:
        for (co, no, idx, d) in big.find_nearest_range(fv[vi], 0.010):
            if idx is not None and isl_of_face[idx] != key:
                ok = True; break
        if ok:
            break
    if not ok:
        fl_ = [f for fi, f in enumerate(ff) if isl_of_face[fi] == key]
        it = BVHTree.FromPolygons(fv, fl_)
        ok = any(isl_of_face[j] != key for (_i, j) in it.overlap(big))
    if not ok and key[0] == 'tailhook':
        ok = True          # 1.4.0: the functional hook's proxy mesh is never rendered (Unity hides it; hook_visual is the visible hook)
    if not ok:
        c = sum((fv[v] for v in vis), Vector()) / len(vis)
        floating.append((key[0], key[1], len(vis), tuple(round(x, 3) for x in c)))
put('no floating exterior parts: every mesh island of every exterior object within 10 mm of another island / object', not floating,
    dict(islands=len(groups), floating=floating[:12]))

# (d) see-through: backface culling ON (as Unity). Every part as it falls away (its own object + the non-part children that go with it)
#     is shot with parallel rays from 42 directions (36 x 36 grid each) and from points inside it near every break; the first surface a ray
#     meets must face the ray (a back face first = a see-through hole). Grazing hits (n.d < 0.03) are ignored.
UNITY_PARTS = ['fus_center', 'fus_engine', 'fus_rear', 'wing_upper_C', 'wing_upper_L', 'wing_upper_R', 'wing_lower_L', 'wing_lower_R', 'aileron_L', 'aileron_R',
               'stab_L', 'stab_R', 'elevator_L', 'elevator_R', 'fin', 'rudder']


def group_of(n):
    out = [O[n]]
    st_ = list(O[n].children)
    while st_:
        c = st_.pop()
        if c.name in UNITY_PARTS or c.name.startswith(('gauge_', 'mfd_', 'prop')) or c.name in ('windscreen',):
            continue
        if c.type == 'MESH':
            out.append(c)
        st_ += list(c.children)
    return out


def fib(nd):
    g = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(nd):
        z = 1 - 2 * (i + 0.5) / nd
        r = math.sqrt(max(1 - z * z, 0))
        out.append(Vector((math.cos(g * i) * r, math.sin(g * i) * r, z)))
    return out


DIRS = fib(42)


def front_partner(tb, hp, d):
    """a back face hit is not a hole when, with that face culled, the ray meets a front face of the same part within 10 mm: a coplanar
    opposite wall (box hinge wall / aileron-bay rib) or an inner-skin sliver poking through the outer skin at a crease. Up to 4 culled
    faces are skipped."""
    if any(no.dot(d) < -0.03 for (co, no, idx, dd) in tb.find_nearest_range(hp, 0.0003)):
        return True
    p = hp
    for _ in range(4):
        h = tb.ray_cast(p + d * 2e-5, d, 0.010 - (p - hp).length)
        if h[0] is None:
            return False
        if h[1].dot(d) < -0.03:
            return True
        p = h[0]
    return False
see = {}
inside_pts = {'fus_engine': [Vector((0, 0.03, 0.0)), Vector((0, 0.03, 0.3)), Vector((0, 0.03, -0.35))],
              'fus_center': [Vector((0, -0.03, 0.0)), Vector((0, -0.03, 0.35)), Vector((0, -1.47, 0.0)), Vector((0, -1.47, -0.4))],
              'fus_rear': [Vector((0, -1.55, 0.0)), Vector((0, -2.4, 0.0)), Vector((0, -3.4, 0.0)), Vector((0, -1.9, -0.45))],
              'wing_upper_C': []}
for side, L in ((-1, 'L'), (1, 'R')):
    inside_pts['wing_upper_' + L] = [Vector((side * 0.84, 0.75, 0.97)), Vector((side * 0.84, 0.2, 0.96))]
    inside_pts['wing_upper_C'] += [Vector((side * 0.76, 0.75, 0.97)), Vector((side * 0.76, 0.2, 0.96))]
NGRID = int(os.environ.get('NIMROD_SEE_GRID', '36'))
for n in UNITY_PARTS:
    grp = group_of(n)
    tb = bvh_of(grp)
    fowner = [o.name for o in grp for _p in o.data.polygons]
    gv = [v for o in grp for v in wv(o)]
    lo = Vector([min(v[i] for v in gv) for i in range(3)]); hi = Vector([max(v[i] for v in gv) for i in range(3)])
    cen = (lo + hi) / 2; rad = (hi - lo).length / 2 + 0.05
    holes = []; nr = 0
    for d in DIRS:
        u = d.orthogonal().normalized(); w_ = d.cross(u).normalized()
        for a in range(NGRID):
            for b in range(NGRID):
                o = cen - d * (rad * 2.5) + u * ((a + 0.5) / NGRID * 2 - 1) * rad + w_ * ((b + 0.5) / NGRID * 2 - 1) * rad
                h = tb.ray_cast(o, d, rad * 5)
                nr += 1
                if h[0] is not None and h[1].dot(d) > 0.03 and not front_partner(tb, h[0], d):
                    holes.append(('out', fowner[h[2]], tuple(round(c, 3) for c in h[0]), tuple(round(c, 2) for c in d)))
    for p in inside_pts.get(n, []):
        for d in fib(240):
            h = tb.ray_cast(p, d, 20.0)
            nr += 1
            if h[0] is not None and h[1].dot(d) > 0.03 and not front_partner(tb, h[0], d):
                holes.append(('in', fowner[h[2]], tuple(round(c, 3) for c in p), tuple(round(c, 3) for c in h[0])))
    see[n] = dict(objects=[o.name for o in grp], rays=nr, holes=len(holes), first=holes[:12])
tot = sum(v['holes'] for v in see.values())
put('see-through (backface culling ON): zero holes from 42 directions and from inside every break, for every part as it falls away',
    tot == 0, {k: (v['holes'], v['first'][:2]) for k, v in see.items() if v['holes']} or {k: v['rays'] for k, v in see.items()})
json.dump(see, open(os.path.join(os.path.dirname(os.path.abspath(OUTP)), 'nimrod_seethrough.json'), 'w'), indent=1)


# (e) 1.3.1 hinge gaps + deflection clearance (game test: lit line along the aileron hinges). Every control surface (+ its nose child)
#     is turned about its hinge axis (object local X) through the NimrodBuild ranges (aileron 18, elevator 26, rudder 25 deg) and
#     must not intersect its parent surface; the visible slot (top view) is measured as the chordwise distance from the parent skin's
#     last point to the control surface's first point at the hinge.
from mathutils import Matrix as _M
CSR = {'aileron_L': ('wing_upper_L', 18), 'aileron_R': ('wing_upper_R', 18), 'elevator_L': ('stab_L', 26), 'elevator_R': ('stab_R', 26),
       'rudder': ('fin', 25)}
clash = {}; slot = {}
for cs, (par, rng) in CSR.items():
    objs = [O[cs]] + [c for c in O[cs].children if c.type == 'MESH']
    pv = O[cs].matrix_world.translation.copy(); ax = (O[cs].matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    pt = bvh_of([O[par]])
    worst = 0
    for deg in (-rng, -rng / 2, rng / 2, rng):
        Rm = _M.Translation(pv) @ _M.Rotation(math.radians(deg), 4, ax) @ _M.Translation(-pv)
        vs, fs = [], []
        for o in objs:
            b0 = len(vs); vs += [Rm @ v for v in wv(o)]; fs += [tuple(b0 + i for i in p_.vertices) for p_ in o.data.polygons]
        n_ = len(BVHTree.FromPolygons(vs, fs).overlap(pt))
        worst = max(worst, n_)
    clash[cs] = worst
    # slot: shortest distance from the control surface's own mesh (plus nose) to the parent, at rest
    cb = bvh_of(objs)
    slot[cs] = round(min(cb.find_nearest(v)[3] for v in wv(O[par]) if (v - pv).length < 0.6 and abs((v - pv).dot(ax)) < 0.4) * 1000, 1)
put('control surfaces clear their parent over the full deflection range (aileron 18 / elevator 26 / rudder 25 deg): no intersecting triangles',
    all(v == 0 for v in clash.values()), dict(intersecting_tri_pairs=clash, min_gap_mm=slot))


# 1.8.3 (user: "mesh issues on the cockpit/fuselage edge"; in game 1.8.0: small dark specks on the side skin): no cockpit part may poke
# through the fuselage skin or sit within 1 mm under it (the walls / frame tubes / sight base / lining did, by up to 9 mm)
import internals_r183 as IN_
pk = IN_.poke_count({o.name: o for o in O if o.type == 'MESH'})
put('1.8.3 no cockpit part pokes through the skin or sits < 1 mm under it (the dark specks on the side skin)', not pk,
    {k: (len(v), v[:3]) for k, v in pk.items()})
# 1.8.3 internals (stock way): engine body + fuel tank inside fus_engine_struct, inside the cowl, and the aft end of a torn-off engine
# section shows structure (no firewall disc on the engine side; 2026-11-22: no tank bulkhead on the fuselage side either - open ends; the
# saddle tank is in the plain 'tank' material)
es = O.get('fus_engine_struct')
nst = 0; outside = []
if es is not None:
    mi = [m.name if m else '' for m in es.data.materials]
    sk = O['fus_engine']; skm = [m.name if m else '' for m in sk.data.materials]
    svs = wv(sk); sfs = [tuple(p_.vertices) for p_ in sk.data.polygons if skm[p_.material_index] == 'paint']
    skb = BVHTree.FromPolygons(svs, sfs)
    def _inside(p_):                       # ray parity against the cowl skin, 3 directions, majority
        votes = 0
        for d_ in (Vector((0, 0, 1)), Vector((0.05, 0.3, 1)).normalized(), Vector((-0.15, -0.2, 1)).normalized()):   # upward: clear of the louvres / radiator
            n_, q_ = 0, p_
            for _ in range(20):
                h_ = skb.ray_cast(q_ + d_ * 1e-5, d_, 5.0)
                if h_[0] is None:
                    break
                n_ += 1; q_ = h_[0]
            votes += n_ % 2
        return votes >= 2
    ev = sorted({tuple(round(c, 4) for c in (es.matrix_world @ v.co)) for v in es.data.vertices})
    for c_ in ev[::3]:
        p_ = Vector(c_)
        if 0.10 < p_.y < 2.32 and abs(p_.x) < 0.37 and -0.50 < p_.z < 0.38 and not _inside(p_):     # the engine / tank box (inner skins lie outside it)
            outside.append([round(p_.x, 3), round(p_.y, 3), round(p_.z, 3)])
    nst = sum(1 for pl in es.data.polygons if mi[pl.material_index] == 'structure')
put('1.8.3 internals: Kestrel body + fuel tank in fus_engine_struct (structure material, stock aircraft_structure in Unity), every vertex inside the cowl skin',
    es is not None and nst > 400 and not outside, dict(structure_faces=nst, outside=outside[:6]))

# 2026-11-22 break faces (user: "The Nimrod and FD-32 need to be changed as well"): the r8o checks C1 / C10 / C11 / C8 / C6 on every
# break end (blender/breakface_r8o_checks.py). The 1.9.14 blend fails C1 (fin root 0.078 m2), C10 (fus_center 0.91 / 0.88, upper wing
# 0.85-0.93, fin 0.99) and C11.
import breakface_r8o_checks as BF


def break_ends(yA, yB, label_y=None):
    """the Mk I / FD-32 break ends: (key, part, plane point, normal out of the part, slice depth)."""
    def xmin(n_, axis=0):
        o_ = O.get(n_)
        if o_ is None:
            return None
        mi = [m.name if m else '' for m in o_.data.materials]
        M_ = o_.matrix_world
        return min(abs((M_ @ o_.data.vertices[i].co)[axis]) for p_ in o_.data.polygons if mi[p_.material_index] == 'paint' for i in p_.vertices)
    out = [(f'fus {yA:+.2f} aft end', 'fus_engine', Vector((0, yA, 0)), Vector((0, -1, 0)), 0.03),
           (f'fus {yA:+.2f} front end', 'fus_center', Vector((0, yA, 0)), Vector((0, 1, 0)), 0.03),
           (f'fus {yB:+.2f} aft end', 'fus_center', Vector((0, yB, 0)), Vector((0, -1, 0)), 0.03),
           (f'fus {yB:+.2f} front end', 'fus_rear', Vector((0, yB, 0)), Vector((0, 1, 0)), 0.03)]
    for sd, L in ((-1, 'L'), (1, 'R')):
        out.append((f'upper wing {L} centre end', 'wing_upper_C', Vector((sd * S.UP_CENTRE_X, 0, 0)), Vector((sd, 0, 0)), 0.03))
        out.append((f'upper wing {L} root end', f'wing_upper_{L}', Vector((sd * S.UP_CENTRE_X, 0, 0)), Vector((-sd, 0, 0)), 0.03))
        xi = xmin(f'wing_lower_{L}_root'); xr = xmin(f'wing_lower_{L}')
        out.append((f'lower wing {L} root', f'wing_lower_{L}', Vector((sd * xi, 0, 0)), Vector((-sd, 0, 0)), xr + 0.02 - xi))
        xi = xmin(f'stab_{L}_root'); xr = xmin(f'stab_{L}')
        out.append((f'stab {L} root', f'stab_{L}', Vector((sd * xi, 0, 0)), Vector((-sd, 0, 0)), xr + 0.02 - xi))
    fo = O['fin']; fmi = [m.name if m else '' for m in fo.data.materials]
    z0 = min((fo.matrix_world @ fo.data.vertices[i].co).z for p_ in fo.data.polygons if fmi[p_.material_index] == 'paint' for i in p_.vertices)
    out.append(('fin root', 'fin', Vector((0, 0, z0)), Vector((0, 0, -1)), 0.03))
    return out


BREAK_DET = set(UNITY_PARTS) | {'prop'}
# round 2 (2026-11-27, review of round 1: the break-facing cockpit walls in interior paint read as one light full-section plate, 78-95 %
# of the view, and passed C11 only by their 'cockpit' label): the cockpit wall is allowed only dark (metal_dark), over <= 85 % of the
# view, with frames / longerons / stringers in front of it on >= 10 % of the rays (C12 cockpit_wall_relief)
# round 3 (2026-11-27, review of round 2: the dark wall still covered 0.64 / 0.81 = the divider, darker): max_cover 0.50, i.e. no
# exemption is left for the cockpit walls (C11 allows them only above 0.60); C12 cockpit_wall_share holds every fuselage end to 0.50
COCKPIT_WALL_RULE = dict(max_cover=0.50, min_relief=0.10)
BREAK_ALLOW = (('fus', ('metal_dark',), 0.20, "the cockpit's own wall, dark, structure in front (0.22 m from the break; the user: the cockpit is different)", COCKPIT_WALL_RULE),
               ('upper wing', ('fabric_in', 'interior'), 0.24, 'bay-end wall of the lined wing cavity (liner paint, 0.40 m in)'),
               ('lower wing', ('fabric_in', 'interior'), 0.24, 'bay-end wall of the lined root cavity (liner paint, 0.40 m past the root)'),
               ('stab', ('fabric_in', 'interior'), 0.24, 'bay-end wall of the lined stab root cavity (liner paint)'),
               ('fin', ('fabric_in', 'interior'), 0.24, 'bay-end wall of the lined fin root cavity (liner paint)'))
if __name__ == '__main__' and not os.environ.get('BREAKFACE_SKIP'):
    bf = BF.run(put, break_ends(S.ENGINE_AFT_Y, S.CENTRE_AFT_Y), BREAK_DET, BREAK_ALLOW, label='2026-11-22 ')
    import nimrod_cockpit as NC_
    bf['eye_bay'] = BF.eye_bay(put, S.EYE, NC_.YA, NC_.YB, label='2026-11-27 ')        # round 3: no bay structure in the cockpit
    bf['poke_sky'] = BF.poke_sky(put, 'fus_center', 'fus_center_struct', 0, BREAK_DET, label='2026-11-27 ')   # round 1 baseline 0
    json.dump(bf, open(os.path.join(os.path.dirname(os.path.abspath(OUTP)), 'nimrod_breakfaces.json'), 'w'), indent=1, default=str)

os.makedirs(os.path.dirname(os.path.abspath(OUTP)), exist_ok=True)
json.dump(res, open(OUTP, 'w'), indent=1)
fails = [k for k, v in res.items() if not v['ok']]
print(f'[check] {len(res) - len(fails)}/{len(res)} PASS')
if fails:
    sys.exit(1)
