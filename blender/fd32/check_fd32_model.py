"""FD-32 model + cockpit checks (copy of blender/nimrod/check_nimrod_model.py, adapted; the Nimrod file is untouched).

  blender --background assets/model_fd32/fd32.blend --python blender/fd32/check_fd32_model.py -- --out assets/model_fd32/fd32_check.json

Kept from the Mk I set: dimensions, prop ground clearance, muzzles ahead of the disc, CG / 3-point / hook geometry and line of pull,
no pedals + closed floor, spinner outward, pilot legs clear, no floating cabin part, cockpit z-fight, budgets, closed cockpit from the
eye, view centre, near plane, connectivity of every strut / wire / gear end, root joints, no floating exterior island, see-through with
backface culling from 42 directions and inside every break, control-surface swing.
Changed: 4 blades / 3.0 m; MFDs instead of needles (nothing between the eye and any display); no throttle quadrant / Aldis (stock
throttle, game HUD); no 1.2.3 functional snapshot (new aircraft).
New (FD-32): store-box clearance of every option on every pylon against the prop disc, gear, struts, wires, wings, neighbouring stores
and the ground (3-point); the ejection path past the upper wing; the canopy slide; flaperon / aileron swing incl. the flap droop.
Exit code 1 on any failure.
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'nimrod')); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'v2'))
import nimrod_spec as S
import fd32_spec as FS
FS.apply()
FS.apply_stretch()      # round 3: the model is the stretched fuselage
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUTP = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(HERE, '..', '..', 'assets', 'model_fd32', 'fd32_check.json')
O = bpy.data.objects
res = {}


def put(name, ok, detail=''):
    res[name] = dict(ok=bool(ok), detail=detail if isinstance(detail, str) else json.dumps(detail, default=str)[:700])
    print('[check] ' + ('PASS ' if ok else 'FAIL ') + name + ' ' + res[name]['detail'][:300], flush=True)


sys.path.insert(0, os.path.join(HERE, '..'))
import atlas_guard as AG   # 1.8.16 guard (first: before any check edits a mesh)
put('1.8.16 livery atlas == texture manifest (skin / liveries / damage painted on this atlas; re-bake the textures when it fails)', *AG.check_row(os.path.join(HERE, '..', '..', 'assets', 'textures_fd32', 'fd32_atlas_manifest.json')))


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
put('length 8.7-9.2 m (Mk I 8.18 + rudder +15 % chord, fal spinner, round 3 fuselage +0.40 m)', 8.7 <= length <= 9.2, f'{length:.3f} m')
blades = [o for o in O if o.name.startswith('prop_blade_')]
R = max((v - Vector((0, S.PROP_Y, 0))).length for o in blades for v in wv(o))
put('propeller diameter 2.9-3.1 m (4 blades)', 2.9 <= 2 * R <= 3.1 and len(blades) == 4, f'{2 * R:.3f} m, {len(blades)} blades')
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
root = O['FD32_root'].matrix_world.translation
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
cgz = O['FD32_root'].matrix_world.translation
lop = [round(rot_nose_up(hp_, d_).z - rot_nose_up(cgz, d_).z, 3) for d_ in (0, 7.5, S.THREE_POINT_DEG)]
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
spm = [i for i, ms in enumerate(hub.material_slots) if ms.material and ('spinner' in ms.material.name.lower() or ms.material.name == 'metal_dark')]   # round 6: the spinner fairing is metal_dark
sp_polys = [p_ for p_ in hub.data.polygons if p_.material_index in spm]
sp_cen = sum((hmw @ p_.center for p_ in sp_polys), Vector()) / max(len(sp_polys), 1)
sp_in = sum(1 for p_ in sp_polys if (hmw.to_3x3() @ p_.normal).dot(hmw @ p_.center - sp_cen) <= 0)
put('spinner / fairing faces outward (no inside-out hub)', sp_polys and sp_in == 0, dict(faces=len(sp_polys), inward=sp_in))
ck_all = bvh_of([o for o in O if o.type == 'MESH' and (o.name.startswith(('cockpit_', 'canopy_slide', 'windscreen_frame'))) and o.name != 'canopy_slide_glass'])
eye_ = Vector(S.EYE); blocked = []
for o in O:
    if not o.name.startswith('mfd_'):
        continue
    pts_ = [o.matrix_world @ v.co for v in o.data.vertices]
    c_ = sum(pts_, Vector()) / len(pts_)
    pts_ = pts_ + [c_] + [c_.lerp(p, 0.9) for p in pts_]
    nb = 0
    for t_ in pts_:
        d_ = t_ - eye_
        if ck_all.ray_cast(eye_, d_.normalized(), d_.length - 0.008)[0] is not None:
            nb += 1
    if nb:
        blocked.append((o.name, nb, len(pts_)))
put('nothing between the eye and any display: every MFD corner / centre seen from the eye (cockpit parts, canopy frame)', not blocked and any(o.name.startswith('mfd_') for o in O), blocked)
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
# round 10: the CI-22 single throttle (COIN_throttle, the user's placeholder mesh read at run time) slides 0 .. 0.22 m forward (Cockpit.Throttle
#     motion, COIN.prefab): at 0 / 0.11 / 0.22 clear of the consoles / panel / seat / walls, sitting on the console top (bottom within 5 mm),
#     front moving forward
sys.path.insert(0, os.path.join(HERE, '..', 'ga25x'))
import stock_preview as SPV0
import fd32_cockpit as FCK
if SPV0.available():
    piv = O['cockpit_throttle'].matrix_world.translation.copy()
    thr = SPV0.add_stock(FCK.STOCK_THR['mesh'], piv, 'chk_throttle', mats=['hotas']); bpy.context.view_layer.update()
    qb = bvh_of([O['cockpit_console_L'], O['cockpit_console_fwd'], O['cockpit_panel'], O['cockpit_interior']])
    seatq = SPV0.add_stock('ejectionSeat', SPV0.seat_origin_blender(Vector(S.EYE)), 'chk_seat_q'); bpy.context.view_layer.update()
    sb_ = bvh_of([seatq])
    tbad = []; fwd = []; bot = []
    for dz_ in (0.0, 0.11, 0.22):
        vs = [v + Vector((0, dz_, 0)) for v in wv(thr)]
        t = BVHTree.FromPolygons(vs, [tuple(p_.vertices) for p_ in thr.data.polygons])
        hit_ = [n_ for n_ in ('cockpit_console_L', 'cockpit_console_fwd', 'cockpit_panel', 'cockpit_interior') if t.overlap(bvh_of([O[n_]]))] + (['seat'] if t.overlap(sb_) else [])
        if hit_:
            tbad.append((dz_, hit_))
        fwd.append(round(max(v.y for v in vs), 3)); bot.append(round(min(v.z for v in vs) - FCK.FWD_TOP, 4))
    bpy.data.objects.remove(seatq); bpy.data.objects.remove(thr)
    put('CI-22 throttle (round 10): slides 0..0.22 m forward clear of the consoles / panel / lining / seat, sits on the console top (<= 5 mm), front moves forward',
        not tbad and all(0.0 < b <= 0.006 for b in bot) and fwd == sorted(fwd), dict(contact_at=tbad, bottom_above_console=bot, front_y=fwd))
else:
    put('CI-22 throttle (round 10): placeholders not available (skipped)', True, '')
# cockpit view from the eye (1.2.1 game notes: open floor showed the ground, Aldis in the view centre, brown arc / near plane)
VIEW = [o for o in O if o.type == 'MESH' and o.name not in ('windscreen', 'canopy_slide_glass') and not o.name.startswith('prop_')]
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
json.dump(holes, open(os.path.join(os.path.dirname(os.path.abspath(OUTP)), 'fd32_eye_holes.json'), 'w'))
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
near = []
for o in ck_names + [O['fus_center'], O['fus_engine'], O['canopy_slide'], O['windscreen_frame']]:
    for v in wv(o):
        dv = v - eye
        if dv.length < 0.20 and dv.y > -0.05:       # forward half-space (+5 cm behind the eye): what the default view frustum can contain
            near.append((o.name, round(dv.length, 3)))
behind = min(((v - eye).length, o.name) for o in ck_names for v in wv(o) if (v - eye).y <= -0.05)
put('nothing inside the 0.2 m camera near plane ahead of the eye (CameraCockpitState nearClipPlane 0.2)', not near, f'{len(near)} verts {near[:4]}; nearest behind the head: {behind[1]} {behind[0]:.3f} m (only seen when looking back)')
# budget
vt = sum(len(o.data.vertices) for o in O if o.type == 'MESH')
tt = sum(len(p.vertices) - 2 for o in O if o.type == 'MESH' for p in o.data.polygons)
put('vertex/triangle budget: welded verts < 48k, tris < 75k (Mk I 1.4.2: 45k / 72k; B-25H: 117k tris)', vt < 48000 and tt < 75000, f'verts {vt}, tris {tt}')

# (b) connectivity: every strut / cabane / wire / gear-leg / stabiliser-strut end lies within 10 mm of the surface of its target part or
#     inside it (the generator records each end and its targets: nimrod_parts.ATTACH)
EXT = [o for o in O if o.type == 'MESH' and not o.name.startswith(('cockpit_', 'gauge_', 'mfd_')) and o.name not in ('windscreen', 'canopy_slide_glass')]
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
UNITY_PARTS = ['fus_center', 'fus_engine', 'fus_rear', 'wing_upper_C', 'wing_upper_L', 'wing_upper_R', 'wing_lower_L', 'wing_lower_R', 'aileron_L', 'aileron_R', 'flaperon_L', 'flaperon_R',
               'stab_L', 'stab_R', 'elevator_L', 'elevator_R', 'fin', 'rudder']


def group_of(n):
    out = [O[n]]
    st_ = list(O[n].children)
    while st_:
        c = st_.pop()
        if c.name in UNITY_PARTS or c.name.startswith(('gauge_', 'mfd_', 'prop', 'canopy_slide', 'sensor_')) or c.name in ('windscreen', 'windscreen_frame', 'canopy_rails'):
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
    if any(no.dot(d) < 0.0 for (co, no, idx, dd) in tb.find_nearest_range(hp, 0.001)):   # FD-32: any front-facing face within 1 mm of the hit (edge hits on 9 mm wires)
        return True
    p = hp
    for _ in range(4):
        h = tb.ray_cast(p + d * 2e-5, d, 0.010 - (p - hp).length)
        if h[0] is None:
            return False
        if h[1].dot(d) < -0.03:
            return True
        p = h[0]
    # FD-32 addition: a 4-sided wire (rigging, 9 mm) hit on its back face at a grazing entry - the ray met the same thin object's front
    # face within 10 mm just before (BVH ray / edge rounding); not a hole
    h = tb.ray_cast(hp - d * 0.010, d, 0.0099)
    return h[0] is not None and h[1].dot(d) < -0.03 and (h[0] - hp).length < 0.010
see = {}
inside_pts = {'fus_engine': [Vector((0, 0.03, 0.0)), Vector((0, 0.03, 0.3)), Vector((0, 0.03, -0.35))],
              'fus_center': [Vector((0, -0.03, 0.0)), Vector((0, -0.03, 0.35)), Vector((0, -1.47, 0.0)), Vector((0, -1.47, -0.4))],
              'fus_rear': [Vector((0, -1.55, 0.0)), Vector((0, -2.4, 0.0)), Vector((0, -3.4, 0.0)), Vector((0, -1.9, -0.45))],
              'wing_upper_C': []}
for side, L in ((-1, 'L'), (1, 'R')):
    inside_pts['wing_upper_' + L] = [Vector((side * 0.84, 0.75, 0.97)), Vector((side * 0.84, 0.2, 0.96))]
    inside_pts['wing_upper_C'] += [Vector((side * 0.76, 0.75, 0.97)), Vector((side * 0.76, 0.2, 0.96))]
NGRID = int(os.environ.get('FD32_SEE_GRID', '36'))
for n in UNITY_PARTS:
    grp = group_of(n)
    tb = bvh_of(grp)
    fowner = [o.name for o in grp for _p in o.data.polygons]
    gv = [v for o in grp if not o.name.startswith("spine_") for v in wv(o)]     # 1.8.3: grid bounds as 1.8.2 (the spine is still hit by the grid rays)
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
json.dump(see, open(os.path.join(os.path.dirname(os.path.abspath(OUTP)), 'fd32_seethrough.json'), 'w'), indent=1)


# (e) 1.3.1 hinge gaps + deflection clearance (game test: lit line along the aileron hinges). Every control surface (+ its nose child)
#     is turned about its hinge axis (object local X) through the NimrodBuild ranges (aileron 18, elevator 26, rudder 25 deg) and
#     must not intersect its parent surface; the visible slot (top view) is measured as the chordwise distance from the parent skin's
#     last point to the control surface's first point at the hinge.
from mathutils import Matrix as _M
CSR = {'aileron_L': ('wing_upper_L', 18), 'aileron_R': ('wing_upper_R', 18), 'flaperon_L': ('wing_lower_L', 18), 'flaperon_R': ('wing_lower_R', 18),
       'elevator_L': ('stab_L', 26), 'elevator_R': ('stab_R', 26), 'rudder': ('fin', 25)}
DROOP = FS.DROOP_DEG   # flap droop (ControlSurface flap mode on a pivot FS.DROOP_PIVOT_BELOW under the hinge), adds to the roll deflection
clash = {}; slot = {}; clash_at = {}
for cs, (par, rng) in CSR.items():
    objs = [O[cs]] + [c for c in O[cs].children if c.type == 'MESH']
    pv = O[cs].matrix_world.translation.copy(); ax = (O[cs].matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    pt = bvh_of([O[par]])
    worst = 0
    te = max(wv(O[cs]), key=lambda v: (v - pv).cross(ax).length)
    down = 1 if ((_M.Rotation(math.radians(5), 3, ax) @ (te - pv)).z < (te - pv).z) else -1
    chd = te - pv; chd = (chd - ax * chd.dot(ax)).normalized(); upd = ax.cross(chd).normalized()
    upd = upd if upd.z > 0 else -upd
    DROOP = FS.DROOP_DEG_UPPER if cs.startswith('aileron') else FS.DROOP_DEG
    angs = [(-rng, 0.0), (-rng / 2, 0.0), (rng / 2, 0.0), (rng, 0.0)]
    if cs.startswith(('aileron', 'flaperon')):      # droop pose: slotted-flap shift + droop, then roll either way on top
        angs += [(down * (DROOP + rng), 1.0), (down * DROOP, 1.0), (down * (DROOP - rng), 1.0), (down * (DROOP / 2 + rng), 0.5)]
    pvd = pv - upd * FS.DROOP_PIVOT_BELOW            # round 3: the flap (droop) pivot sits DROOP_PIVOT_BELOW under the hinge line
    for deg, sh in angs:
        dd = down * DROOP * sh                          # droop part (about pvd), the rest = roll about the hinge
        Rd = _M.Translation(pvd) @ _M.Rotation(math.radians(dd), 4, ax) @ _M.Translation(-pvd)
        Rm = Rd @ _M.Translation(pv) @ _M.Rotation(math.radians(deg - dd), 4, ax) @ _M.Translation(-pv)
        vs, fs = [], []
        for o in objs:
            b0 = len(vs); vs += [Rm @ v for v in wv(o)]; fs += [tuple(b0 + i for i in p_.vertices) for p_ in o.data.polygons]
        n_ = len(BVHTree.FromPolygons(vs, fs).overlap(pt))
        if n_:
            clash_at.setdefault(cs, []).append((round(deg, 1), sh, n_))
        worst = max(worst, n_)
    clash[cs] = worst
    # slot: shortest distance from the control surface's own mesh (plus nose) to the parent, at rest
    cb = bvh_of(objs)
    slot[cs] = round(min(cb.find_nearest(v)[3] for v in wv(O[par]) if (v - pv).length < 0.6 and abs((v - pv).dot(ax)) < 0.4) * 1000, 1)
put('control surfaces clear their parent over the full deflection range (aileron / flaperon 18 + 20 droop / elevator 26 / rudder 25 deg): no intersecting triangles',
    all(v == 0 for v in clash.values()), dict(intersecting_tri_pairs=clash, at=clash_at, min_gap_mm=slot))


# ======================================================================================== FD-32 checks
A3 = math.radians(S.THREE_POINT_DEG)        # (the see-through loop reuses the name `a`: own angle + rotation here)
def to3pt(p):
    d = p - contact
    return contact + Vector((d.x, d.y * math.cos(A3) - d.z * math.sin(A3), d.y * math.sin(A3) + d.z * math.cos(A3)))
# (f) stores: proxy boxes of the stock mount prefabs in their mount frame (Unity: x, y up, z fwd), measured read-only on the user's
#     export with blender/v2/study/stock.py (tree + mesh bboxes, rolled launchers boxed conservatively); only the numbers are kept.
MOUNTS = {
    'RocketPod1_single':  ('AGR-18 x7',  (-0.149, -0.359, -1.028), (0.149, 0.055, 1.045)),
    'Rocket2_4Pod':       ('AGR-24 x4',  (-0.195, -0.491, -1.091), (0.195, 0.052, 1.088)),
    'IRMS1_single':       ('IRM-S1',     (-0.148, -0.261, -0.854), (0.148, 0.049, 0.684)),
    'IRMS1_double':       ('IRM-S1 x2',  (-0.330, -0.300, -0.854), (0.330, 0.070, 0.684)),
    'AAM3_single':        ('IRM-S2',     (-0.114, -0.336, -1.061), (0.114, 0.035, 1.494)),
    'ATGM1_quad':         ('AT-145 x4',  (-0.191, -0.466, -0.831), (0.191, 0.000, 0.708)),
    'bomb_glide1_single': ('PAB-80LR',   (-0.170, -0.450, -0.957), (0.170, 0.050, 0.846)),
    'bomb_125_single':    ('PAB-125',    (-0.103, -0.322, -0.909), (0.103, 0.050, 0.758)),
}
OPTIONS = {'inner': ['RocketPod1_single', 'Rocket2_4Pod', 'IRMS1_single', 'AAM3_single', 'ATGM1_quad', 'bomb_glide1_single', 'bomb_125_single'],
           'outer': ['RocketPod1_single', 'IRMS1_single', 'IRMS1_double', 'AAM3_single', 'bomb_glide1_single', 'bomb_125_single']}
json.dump(dict(mounts=MOUNTS, options=OPTIONS), open(os.path.join(os.path.dirname(os.path.abspath(OUTP)), 'fd32_store_options.json'), 'w'), indent=1)


def store_box(hp, key):
    _, a, b = MOUNTS[key]
    p = O[hp].matrix_world.translation
    return Vector((p.x + a[0], p.y + a[2], p.z + a[1])), Vector((p.x + b[0], p.y + b[2], p.z + b[1]))


def box_bvh(mn, mx):
    vs = [Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return BVHTree.FromPolygons(vs, fs)


OBST = [o for o in O if o.type == 'MESH' and (o.name.startswith(('gear_', 'struts_', 'rigging_', 'fus_', 'aileron_', 'flaperon_', 'wing_upper', 'prop_'))
                                              or o.name in ('wing_lower_L_root', 'wing_lower_R_root'))]
ob_tree = {o.name: (bvh_of([o]), wv(o)) for o in OBST}
st_bad = []; st_info = {}
ground_min = 9.0
for kind, opts in OPTIONS.items():
    for L in 'LR':
        hp = f'hp_{kind}_{L}'
        for m in opts:
            mn, mx = store_box(hp, m)
            tb = box_bvh(mn, mx)
            # prop disc: the store (and its launch path straight ahead) must stay outside the disc radius + 0.08 m
            inner_edge = min(abs(mn.x), abs(mx.x))
            if inner_edge < FS.PROP_R + 0.08:
                st_bad.append((hp, m, 'inside the prop-disc radius', round(inner_edge, 3)))
            for n, (t, vs) in ob_tree.items():
                hit = bool(tb.overlap(t)) or any(mn.x <= v.x <= mx.x and mn.y <= v.y <= mx.y and mn.z <= v.z <= mx.z for v in vs[::7])
                if hit:
                    st_bad.append((hp, m, n))
            # wing: the box top may touch the pylon bottom face only (the rail sinks into the pylon, stock_damage_study 8)
            wt = bvh_of([O[f'wing_lower_{L}']])
            mn2 = Vector((mn.x, mn.y, mn.z)); mx2 = Vector((mx.x, mx.y, O[hp].matrix_world.translation.z - 0.005))
            if box_bvh(mn2, mx2).overlap(wt):
                st_bad.append((hp, m, f'wing_lower_{L}'))
            # ground, 3-point attitude (every box corner)
            gz = min(to3pt(Vector((x, y, z))).z for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)) - S.GROUND_LEVEL_Z
            ground_min = min(ground_min, gz)
            if gz < 0.10:
                st_bad.append((hp, m, 'ground (3-point)', round(gz, 3)))
        st_info[hp] = len(opts)
# neighbouring stores (inner vs outer on the same wing, every pair)
gaps = []
for L in 'LR':
    for a_ in OPTIONS['inner']:
        for b_ in OPTIONS['outer']:
            A, B = store_box(f'hp_inner_{L}', a_), store_box(f'hp_outer_{L}', b_)
            g = max(B[0].x - A[1].x, A[0].x - B[1].x)
            gaps.append(round(g, 3))
            if g < 0.05:
                st_bad.append(('pair', L, a_, b_, round(g, 3)))
put('stores: every option on every pylon clears the prop disc (radius + 0.08), gear, struts, wires, wings, fuselage, other pylon stores (>= 50 mm) and the ground in the 3-point attitude (>= 0.10 m)',
    not st_bad, dict(bad=st_bad[:12], options=st_info, min_pair_gap_m=min(gaps), min_ground_3pt_m=round(ground_min, 3)))
# positive control: a box straddling the left wheel and one inside the prop disc must be flagged
wl = O['gear_main_L_wheel'].matrix_world.translation
ctrl1 = bool(box_bvh(wl - Vector((0.1, 0.1, 0.1)), wl + Vector((0.1, 0.1, 0.1))).overlap(ob_tree['gear_main_L_wheel'][0])) or any(
    (v - wl).length < 0.12 for v in ob_tree['gear_main_L_wheel'][1])
ctrl2 = min(abs(-1.2), abs(-1.0)) < FS.PROP_R + 0.08
put('store check positive controls: a box on the left wheel and a box at x -1.0..-1.2 (inside the disc) are both flagged', ctrl1 and ctrl2, dict(wheel=ctrl1, disc=ctrl2))

# (g) ejection path: the stock seat (0.62 x 0.62 m column round the eye station) rises straight up out of the cockpit; with the hood
#     jettisoned first, nothing of the airframe may be inside that column from the sill up to 3 m (upper wing TE, cabane, wires)
ey = Vector(S.EYE)
cmn, cmx = Vector((ey.x - 0.31, ey.y - 0.31, FS.HOOD_SILL_Z + 0.02)), Vector((ey.x + 0.31, ey.y + 0.31, 3.5))
col_t = box_bvh(cmn, cmx)
ej_bad = []
for o in O:
    if o.type != 'MESH' or o.name.startswith(('cockpit_', 'mfd_', 'canopy_slide')):
        continue
    if o.name in ('windscreen', 'windscreen_frame', 'canopy_rails'):
        continue
    if o.name.startswith(('fus_', 'cockpit_')):
        continue                                   # the seat rises out of the tub as on every stock aircraft (rails behind the seat)
    t = bvh_of([o])
    if t is not None and (col_t.overlap(t) or any(cmn.x <= v.x <= cmx.x and cmn.y <= v.y <= cmx.y and cmn.z <= v.z <= cmx.z for v in wv(o)[::5])):
        ej_bad.append(o.name)
te_gap = cmn.y - max(v.y for v in wv(O['wing_upper_C']) if v.y < 0.2 and abs(v.x) < 0.8 and v.z > 0.8) if 'wing_upper_C' in O else None
put('ejection path: a 0.62 m seat column from the sill straight up (3.5 m) meets no airframe part (upper wing, cabane, wires; hood jettisoned)',
    not ej_bad, dict(hits=ej_bad, fwd_edge_y=round(cmn.y + 0.62, 3), upper_wing_te_y=round(cmn.y - te_gap + 0.62, 3) if te_gap is not None else None))

# (h) canopy: the hood opens by tilting up FS.HOOD_OPEN_DEG about its hinge (back of the rear fairing, local X); the open pose must lift the
#     front hoop >= 0.30 m and stay clear of the fuselage / windscreen (the sign that lifts the front is recorded for FD32Build)
hg = O['canopy_slide_hinge']; hpv = hg.matrix_world.translation.copy(); hax = (hg.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
hood = [O['canopy_slide']] + [c for c in O['canopy_slide'].children if c.type == 'MESH']
front0 = max((v for o in hood for v in wv(o)), key=lambda v: v.y)
best = None
for sg in (1, -1):
    Rm = Matrix.Translation(hpv) @ Matrix.Rotation(math.radians(sg * FS.HOOD_OPEN_DEG), 4, hax) @ Matrix.Translation(-hpv)
    if best is None or (Rm @ front0).z > (best[1] @ front0).z:
        best = (sg, Rm)
sg, Rm = best
vs, fs = [], []
for o in hood:
    b0 = len(vs); vs += [Rm @ v for v in wv(o)]; fs += [tuple(b0 + i for i in p_.vertices) for p_ in o.data.polygons]
ht = BVHTree.FromPolygons(vs, fs)
cl = []
for n in ('fus_center', 'fus_rear', 'windscreen', 'windscreen_frame', 'cockpit_interior', 'wing_upper_C', 'cabane'):
    if n not in O:
        continue
    far = [i for i, j in ht.overlap(bvh_of([O[n]])) if (sum((vs[k] for k in fs[i]), Vector()) / len(fs[i]) - hpv).length > 0.25]
    if far:                            # contact within 0.25 m of the hinge = the rear end resting on the deck (expected)
        cl.append((n, len(far)))
lift = (Rm @ front0).z - front0.z
put(f'canopy: the hood tilts up {FS.HOOD_OPEN_DEG} deg about its rear hinge, front lifted >= 0.30 m, clear of the fuselage / windscreen / upper wing',
    lift >= 0.30 and not cl, dict(sign=sg, front_lift_m=round(lift, 3), clash=cl))
json.dump(dict(open_sign_blender=sg, open_deg=FS.HOOD_OPEN_DEG), open(os.path.join(os.path.dirname(os.path.abspath(OUTP)), 'fd32_canopy_open.json'), 'w'))

# (i) sensor ball: retracts into its bay (deployed / stowed travel in the contract) without touching the gear legs or the bay collar
sb = O['sensor_ball']; sbv = wv(sb)
travel = FS.BALL_Z_DEPLOYED - FS.BALL_Z_STOWED
dep = [v + Vector((0, 0, travel)) for v in sbv]
gl = bvh_of([O[n] for n in O.keys() if n.startswith('gear_main_')])
dep_t = BVHTree.FromPolygons(dep, [tuple(p_.vertices) for p_ in sb.data.polygons])
st_t = BVHTree.FromPolygons(sbv, [tuple(p_.vertices) for p_ in sb.data.polygons])
hw_ball = max(abs(v.x) for v in sbv)
put('sensor ball: inside the bay radius, clear of the gear legs stowed and deployed, bottom deployed above the 3-point ground by > 0.5 m',
    hw_ball < FS.BAY_R and not dep_t.overlap(gl) and not st_t.overlap(gl) and min(to3pt(v).z for v in dep) - S.GROUND_LEVEL_Z > 0.5,
    dict(half_width=round(hw_ball, 3), bay_r=FS.BAY_R, deployed_bottom_3pt=round(min(to3pt(v).z for v in dep) - S.GROUND_LEVEL_Z, 3)))


import nimrod_structure as _NS2
ST_SKIN_Z = _NS2.fus_z(0.0, FS.BALL_Y, top=False)
# (i2) round 11 (user: the stowed ball clipped the belly): along the arm arc (Unity: pivot FS.SENSOR_ARM ahead, stowed -> deployed),
#      at stowed / mid / deployed the ball touches no fuselage skin or inner skin (the bay is cut open), and from below the bay is closed:
#      rays up inside the opening meet the ball or the dark well, never the skin, never the open fuselage
fus_sk = bvh_of([O['fus_engine'], O['fus_engine_struct']])
piv_s = Vector((0, FS.BALL_Y + FS.SENSOR_ARM, FS.BALL_Z_STOWED))
trv = FS.BALL_Z_STOWED - FS.BALL_Z_DEPLOYED
ang_s = 2 * math.asin(trv / (2 * FS.SENSOR_ARM))
bres = {}
for tag_, fr_ in (('stowed', 0.0), ('mid', 0.5), ('deployed', 1.0)):
    Rb = Matrix.Translation(piv_s) @ Matrix.Rotation(ang_s * fr_, 4, 'X') @ Matrix.Translation(-piv_s)      # pivot ahead: + turns the ball down
    bv = [Rb @ v for v in sbv]
    bt = BVHTree.FromPolygons(bv, [tuple(p_.vertices) for p_ in sb.data.polygons])
    bres[tag_] = dict(skin_hit=bool(bt.overlap(fus_sk)), gear_hit=bool(bt.overlap(gl)), bottom=round(min(v.z for v in bv), 3), drift=round((Rb @ Vector((0, FS.BALL_Y, FS.BALL_Z_STOWED))).y - FS.BALL_Y, 3))
dg_b = bpy.context.evaluated_depsgraph_get()
open_bad = []
for rr in (0.0, 0.06, 0.12, 0.17, 0.19):
    for k in range(16):
        th = 2 * math.pi * k / 16
        org = Vector((rr * math.cos(th), FS.BALL_Y + rr * math.sin(th), -1.2))
        h, loc, nn, idx, ob, mm = bpy.context.scene.ray_cast(dg_b, org, Vector((0, 0, 1)))
        if not h:
            open_bad.append(('none', rr, k)); continue
        mat_ = ob.data.materials[ob.data.polygons[idx].material_index].name if ob.data.materials else ''
        if not (ob.name == 'sensor_ball' or mat_ in ('cove', 'metal_dark')):
            open_bad.append((ob.name, mat_, rr, k))
put('sensor bay (round 11): ball clear of the skin / inner skin and the gear legs at stowed / mid / deployed along the arm arc; stowed fully inside the cut-open, closed well (80 rays from below meet the ball or the dark well)',
    all(not v['skin_hit'] and not v['gear_hit'] for v in bres.values()) and bres['stowed']['bottom'] > ST_SKIN_Z - 0.0 and not open_bad,
    dict(poses=bres, open_bad=open_bad[:6], n_bad=len(open_bad)))

# ======================================================================================== round 3 (user review fd32-1) checks
# (j) face orientation of EVERY mesh, imported ones included (the fal prop shipped inside-out twice). Exterior objects: rays from 26
#     directions x 14 x 14 at the object ALONE; the first hit must be a front face (front_partner tolerances as the see-through check).
#     Cockpit objects: rays from the eye region (the only place they are seen from). Glass is one-sided by design (Unity: interior copy
#     with the glass_int material), so glass objects are tested from outside only.
face_bad = {}
D26 = fib(26)
covered = set()
for n_ in UNITY_PARTS:
    covered |= {o.name for o in group_of(n_)}
GLASS = ('windscreen', 'canopy_slide_glass')
def own_art(o):
    return any(ms.material and ms.material.name.startswith('pr_') for ms in o.material_slots)
for o in [o for o in O if o.type == 'MESH']:
    # airframe skins inside a see-through group (openings, inner skins) are covered by check (d); everything else - props, wheels, gear,
    # canopy frame, hook, lights, pylons, every fal / imported mesh - is shot alone here
    if o.name.startswith(('cockpit_', 'mfd_', 'prop_')) or o.name in GLASS or (o.name in covered and not own_art(o)):
        continue
    tb = bvh_of([o])
    if tb is None:
        continue
    gv = wv(o)
    lo_ = Vector([min(v[i] for v in gv) for i in range(3)]); hi_ = Vector([max(v[i] for v in gv) for i in range(3)])
    cen = (lo_ + hi_) / 2; rad = (hi_ - lo_).length / 2 + 0.02
    nb = 0; first = None
    for d in D26:
        u = d.orthogonal().normalized(); w_ = d.cross(u).normalized()
        for a_ in range(14):
            for b_ in range(14):
                org = cen - d * (rad * 2.5) + u * ((a_ + 0.5) / 14 * 2 - 1) * rad + w_ * ((b_ + 0.5) / 14 * 2 - 1) * rad
                h = tb.ray_cast(org, d, rad * 5)
                if h[0] is not None and h[1].dot(d) > 0.03 and not front_partner(tb, h[0], d):
                    nb += 1
                    first = first or tuple(round(c, 3) for c in h[0])
    if nb:
        face_bad[o.name] = (nb, first)
# the propeller as it spins (hub + 4 blades together; they always render together)
pg = [o for o in O if o.type == 'MESH' and o.name.startswith('prop_')]
tb = bvh_of(pg); gv = [v for o in pg for v in wv(o)]
lo_ = Vector([min(v[i] for v in gv) for i in range(3)]); hi_ = Vector([max(v[i] for v in gv) for i in range(3)])
cen = (lo_ + hi_) / 2; rad = (hi_ - lo_).length / 2 + 0.02; nb = 0
for d in D26:
    u = d.orthogonal().normalized(); w_ = d.cross(u).normalized()
    for a_ in range(24):
        for b_ in range(24):
            org = cen - d * (rad * 2.5) + u * ((a_ + 0.5) / 24 * 2 - 1) * rad + w_ * ((b_ + 0.5) / 24 * 2 - 1) * rad
            h = tb.ray_cast(org, d, rad * 5)
            if h[0] is not None and h[1].dot(d) > 0.03 and not front_partner(tb, h[0], d):
                nb += 1
if nb:
    face_bad['propeller (hub + blades)'] = nb
eye_ = Vector(S.EYE)
for o in [o for o in O if o.type == 'MESH' and o.name.startswith(('cockpit_', 'mfd_'))]:
    tb = bvh_of([o])
    nb = 0
    for d in fib(400):
        for off in (Vector((0, 0, 0)), Vector((0.06, 0.05, 0)), Vector((-0.06, 0.05, 0))):
            h = tb.ray_cast(eye_ + off, d, 3.0)
            if h[0] is not None and h[1].dot(d) > 0.03 and not front_partner(tb, h[0], d):
                nb += 1
    if nb:
        face_bad[o.name] = (nb, 'from the eye')
for gn in GLASS:                   # glass is one-sided (Unity draws the inside with the glass_int copy): every face must point away from the cockpit
    o = O[gn]; mw = o.matrix_world; inward = 0
    for p_ in o.data.polygons:
        c_ = mw @ p_.center; n_ = (mw.to_3x3() @ p_.normal)
        ref = Vector((0, c_.y, FS.HOOD_SILL_Z - 0.10))
        if n_.dot(c_ - ref) < 0:
            inward += 1
    if inward:
        face_bad[gn] = (inward, 'glass faces pointing into the cockpit')
put('face orientation: every non-skin mesh (fal / imported, gear, prop, hook, lights, canopy frame) faces outward from every side; cockpit parts from the eye; glass points out',
    not face_bad, dict(bad=face_bad, tested_alone=len([o for o in O if o.type == 'MESH']) - len(covered)))

# (j2) round 4: prop blades closed and not textured from the fal atlas (its seam bands showed as white holes on the blades)
bl_ = {}
for o in [o for o in O if o.type == 'MESH' and o.name.startswith('prop_blade')]:
    bm_ = bmesh.new(); bm_.from_mesh(o.data)
    bl_[o.name] = dict(boundary=sum(1 for e in bm_.edges if len(e.link_faces) == 1), nonmanifold=sum(1 for e in bm_.edges if len(e.link_faces) > 2),
                       mats=sorted({o.data.materials[p_.material_index].name for p_ in o.data.polygons}))
    bm_.free()
put('prop blades: 4, each closed (0 boundary, 0 non-manifold edges) and on the fal gunmetal tile (no fal-atlas UVs)',
    len(bl_) == 4 and all(v['boundary'] == 0 and v['nonmanifold'] == 0 and v['mats'] == ['metal_dark'] for v in bl_.values()), bl_)

# (k) the stock seat and the stock stick (placeholder meshes from the user's Blueprinter project, read at run time, never saved) at the
#     FD32Build placement: seat on the COIN figure at the eye, stick on cockpit_stick; the stick swept through +-12 deg pitch and roll
#     must not touch the seat, and nothing of the cockpit may cut through the seat
sys.path.insert(0, os.path.join(HERE, '..', 'ga25x'))
import stock_preview as SPV
seat_ok = None; seat_d = {}
if SPV.available():
    seat = SPV.add_stock('ejectionSeat', SPV.seat_origin_blender(Vector(S.EYE)), 'chk_seat')
    stick = SPV.add_stock('sfb_joystick', O['cockpit_stick'].matrix_world.translation, 'chk_stick')
    bpy.context.view_layer.update()
    st_b = bvh_of([seat])
    sp = O['cockpit_stick'].matrix_world.translation
    hits = []
    for pd in (-12, 0, 12):
        for rd in (-12, 0, 12):
            Rm = Matrix.Translation(sp) @ Matrix.Rotation(math.radians(pd), 4, 'X') @ Matrix.Rotation(math.radians(rd), 4, 'Y') @ Matrix.Translation(-sp)
            vs = [Rm @ v for v in wv(stick)]
            t = BVHTree.FromPolygons(vs, [tuple(p_.vertices) for p_ in stick.data.polygons])
            gap = min(st_b.find_nearest(v)[3] or 9 for v in vs)
            if t.overlap(st_b):
                hits.append((pd, rd))
            seat_d[f'{pd},{rd}'] = round(gap * 1000)
    cab = [o for o in O if o.type == 'MESH' and o.name.startswith('cockpit_') and o.name not in ('cockpit_stick',)] + [O['canopy_slide'], O['canopy_slide_glass']]
    seat_clash = [o.name for o in cab if bvh_of([o]) is not None and bvh_of([o]).overlap(st_b)]
    seat_top = max(v.z for v in wv(seat))
    canopy_gap = min((bvh_of([O['canopy_slide_glass']]).find_nearest(v)[3] or 9) for v in wv(seat) if v.z > seat_top - 0.25)
    seat_ok = not hits and not seat_clash
    seat_d.update(stick_hits=hits, clash=seat_clash, seat_top=round(seat_top, 3), canopy_gap_mm=round(canopy_gap * 1000))
    # (k2) round 4: every screen island >= 90 % visible from the eye with the stock stick at neutral, our throttle, frames and coaming
    SCR = [o for o in O if o.type == 'MESH' and o.name.startswith('mfd_')]
    thr_k = SPV.add_stock('COIN_throttle', O['cockpit_throttle'].matrix_world.translation, 'chk_throttle', mats=['hotas']); bpy.context.view_layer.update()
    occ = [o for o in O if o.type == 'MESH' and o not in SCR and o.name not in ('windscreen', 'canopy_slide_glass', 'chk_seat') and not o.name.startswith(('prop_', 'gear_'))]   # (+ chk_throttle: the stock throttle at idle)
    ot = bvh_of(occ)
    vis = {}
    # round 8 (in-game 1.5.3: in level flight the head sits lower / further forward and the grip covered the map's bottom centre): the static
    # eye AND an eye 4 cm lower, 3 cm forward; every screen >= 95 % visible from both
    for tag_, eye_ in (('eye', Vector(S.EYE)), ('eye-4cm+3cm', Vector(S.EYE) + Vector((0, 0.03, -0.04)))):
     for mt in SCR:
        mw_ = mt.matrix_world
        p_ = mt.data.polygons[0]; vs_ = [mw_ @ mt.data.vertices[k].co for k in p_.vertices]
        n_ok = n = 0
        for a_ in range(14):
            for b_ in range(14):
                u, v = (a_ + 0.5) / 14, (b_ + 0.5) / 14
                pt = (vs_[0].lerp(vs_[1], u)).lerp(vs_[3].lerp(vs_[2], u), v)
                d_ = pt - eye_; L_ = d_.length
                h_ = ot.ray_cast(eye_, d_.normalized(), L_ - 0.004)
                n += 1; n_ok += h_[0] is None
        vis[f'{mt.name} ({tag_})'] = round(n_ok / n, 3)
    put('screens from the eye and from an eye 4 cm lower / 3 cm forward (round 8): every screen >= 95 % visible (stock stick neutral, throttle, frames, coaming)',
        len(vis) == 8 and all(v >= 0.95 for v in vis.values()), vis)
    # (k3) round 6: the stick base is small and ends at the stock stick's pivot (no gaiter column round the stem)
    sb_ = wv(O['cockpit_stickboot']); sp_ = O['cockpit_stick'].matrix_world.translation
    sb_top = max(v.z for v in sb_); sb_w = max(max(v.x for v in sb_) - min(v.x for v in sb_), max(v.y for v in sb_) - min(v.y for v in sb_))
    put('stick base: ends within 10 mm above the stock stick pivot, footprint <= 0.20 m (no gaiter column)', sb_top <= sp_.z + 0.010 and sb_w <= 0.20,
        dict(top=round(sb_top, 3), pivot_z=round(sp_.z, 3), footprint=round(sb_w, 3)))
    for o_ in (seat, stick, thr_k):
        bpy.data.objects.remove(o_)
put('stock seat vs stock stick (+-12 deg pitch / roll sweep) and vs every cockpit part + the closed canopy: no contact', bool(seat_ok), seat_d)

# (l) round 6 gear swing (docs/fd32_design.md 19 fault 1): each main leg + wheel turned aft about its pivot (lateral axis, FS.main_fold_sign)
#     in 24 steps from 0 to FS.GEAR_FOLD_DEG: at EVERY step no overlap with any other mesh (wings, fuselage, struts, wires, pylons,
#     flaperons, stab struts, sensor ball stowed AND deployed, the other leg, the trunnion mount except its coaxial boss contact).
#     Stowed: wheel 0.05-0.16 m from the lower wing / fuselage skin, behind the main axle, below the eye line. Stance: track 1.7-1.9 m,
#     CoM 0.30-0.50 m aft of the axle, tailwheel fixed (TAIL_FOLD_DEG 0).
ret = {}
import fd32_gear6 as G6_
air = [o for o in O if o.type == 'MESH' and not o.name.startswith(('cockpit_', 'mfd_', 'prop_'))]
ball = O['sensor_ball']
dz_ball = FS.BALL_Z_DEPLOYED - FS.BALL_Z_STOWED
ball_dep = BVHTree.FromPolygons([v + Vector((0, 0, dz_ball)) for v in wv(ball)], [tuple(p_.vertices) for p_ in ball.data.polygons])
for L_ in 'LR':
    grp = [f'gear_main_{L_}_strut', f'gear_main_{L_}_wheel']
    piv_ = O[grp[0]].matrix_world.translation.copy()
    side_ = -1 if L_ == 'L' else 1
    trees = [(o.name, bvh_of([o])) for o in air if o.name not in grp] + [('sensor_ball (deployed)', ball_dep)]
    # round 7 (in-game 1.5.2: the stowed tyre touched the AGR-18 x7 pod): every allowed store on both pylons of this side, as its box
    for hp_n, keys_ in ((f'hp_inner_{L_}', OPTIONS['inner']), (f'hp_outer_{L_}', OPTIONS['outer'])):
        for k_ in keys_:
            mn_, mx_ = store_box(hp_n, k_)
            trees.append((f'store {k_} on {hp_n}', box_bvh(mn_, mx_)))
    clash_ = []
    N_ = 24
    for k in range(N_ + 1):
        Rf = G6_.fold_matrix(side_, k / N_)
        mv, mf = [], []
        for n in grp:
            b0 = len(mv); mv += [Rf @ v for v in wv(O[n])]; mf += [tuple(b0 + i for i in p_.vertices) for p_ in O[n].data.polygons]
        tf = BVHTree.FromPolygons(mv, mf)
        for nm_, to in trees:
            if to is None:
                continue
            if nm_ == f'gear_mount_{L_}':
                # the leg's trunnion pin / barrel are coaxial with the mount boss: only the parts of the leg more than 0.07 m from the axis may not touch it
                far = [i for i, v in enumerate(mv) if (Vector((0, v.y - piv_.y, v.z - piv_.z))).length > 0.07]
                if any((to.find_nearest(mv[i])[3] or 9) < 0.004 for i in far):
                    clash_.append(f'{nm_} at {round(100 * k / N_)} %')
                continue
            if tf.overlap(to):
                clash_.append(f'{nm_} at {round(100 * k / N_)} %')
    Rm = G6_.fold_matrix(side_, 1.0)
    wvs = [Rm @ v for v in wv(O[grp[1]])]
    skin = bvh_of([O[f'wing_lower_{L_}'], O['fus_center'], O['fus_engine']] + ([O[f'wing_lower_{L_}_root']] if f'wing_lower_{L_}_root' in O else []))
    gap = min(skin.find_nearest(v)[3] or 9 for v in wvs)
    wc = Rm @ O[grp[1]].matrix_world.translation
    if not (0.05 <= gap <= 0.16):
        clash_.append(f'stowed wheel {gap:.3f} m from the skin (0.05-0.16)')
    axd_ = (Rm.to_3x3() @ (O[grp[1]].matrix_world.to_3x3() @ Vector((1, 0, 0)))).normalized()
    if abs(axd_.z) < 0.95:
        clash_.append(f'stowed wheel not flat (axle . z = {axd_.z:.2f})')
    wing_bot = min(v.z for v in wvs)
    if wing_bot < -0.95:
        clash_.append(f'stowed wheel hangs to z {wing_bot:.2f} (< -0.95)')
    if wc.y > O[grp[1]].matrix_world.translation.y - 0.5:
        clash_.append('stowed wheel not swung aft')
    ret[L_] = dict(clash=sorted(set(clash_)), wheel_stowed=tuple(round(c, 3) for c in wc), skin_gap_m=round(gap, 3), lowest_z=round(min(v.z for v in wvs), 3), axle_z=round(axd_.z, 3), pivot=tuple(round(c, 3) for c in piv_), fold=[round(c, 3) for c in G6_.fold_axis_angle(side_)[0]] + [round(G6_.fold_axis_angle(side_)[1], 1)])
axL, axR = O['gear_main_L_wheel'].matrix_world.translation, O['gear_main_R_wheel'].matrix_world.translation
track = axR.x - axL.x
cg_ = O['FD32_root'].matrix_world.translation
ret['track_m'] = round(track, 3); ret['com_aft_of_axle_m'] = round(axR.y - cg_.y, 3); ret['tail_fold_deg'] = FS.TAIL_FOLD_DEG
put(f'gear swing (24 steps, aft about the tilted axis): leg + wheel clear of every mesh AND every allowed store box on both pylons at every step; stowed wheel flat, 0.05-0.16 m under the skin, lowest point above z -0.95; track 1.7-1.9 m; CoM 0.45-0.70 m aft of the axle (round 9: axle 0.15 m forward, tail-up CoM angle ~16.5 deg); tailwheel fixed',
    all(not ret[k]['clash'] for k in 'LR') and 1.7 <= track <= 1.9 and 0.45 <= axR.y - cg_.y <= 0.70 and FS.TAIL_FOLD_DEG == 0, ret)

# (o) round 6 hook swing (fault 3): the hook mesh turned from stowed to deployed in 24 steps about its hinge (lateral axis) touches no other
#     mesh at any step (the slot + channel are cut from its swept envelope); the stowed hook is inside the slot / channel
hk_ = O['tailhook']; hp6 = hk_.matrix_world.translation.copy()
others_h = [(o.name, bvh_of([o])) for o in O if o.type == 'MESH' and o.name != 'tailhook' and not o.name.startswith(('cockpit_', 'mfd_'))]
hclash = []
for k in range(25):
    a6 = -math.radians((S.HOOK_DEPLOY - S.HOOK_STOW_UP) * k / 24)
    Rh = Matrix.Translation(hp6) @ Matrix.Rotation(a6, 4, 'X') @ Matrix.Translation(-hp6)
    th6 = BVHTree.FromPolygons([Rh @ v for v in wv(hk_)], [tuple(p_.vertices) for p_ in hk_.data.polygons])
    for nm_, to in others_h:
        if to is not None and th6.overlap(to):
            hclash.append(f'{nm_} at {round(100 * k / 24)} %')
put(f'hook swing (24 steps, stowed {S.HOOK_STOW_UP} -> deployed {S.HOOK_DEPLOY} deg): no contact with any mesh at any step (belly slot + channel from its swept envelope)',
    not hclash, dict(clash=hclash[:12], n=len(hclash), hinge=tuple(round(c, 3) for c in hp6)))

# (p) round 6 prop attachment (fault 4, shot 98): the hub is closed from the cowl ring to the spinner cone - radial rays toward the axis at
#     24 azimuths x 12 stations between the cowl front and the cone base meet the hub at r >= 0.27; the hub's back ring is <= 5 mm ahead
#     of the cowl front ring and within 10 mm of its radius
hubt = bvh_of([O['prop_hub']])
cw = [v for v in wv(O['fus_engine']) if v.y > 2.30]
cowl_y = max(v.y for v in cw)
cowl_r = max(math.hypot(v.x, v.z) for v in cw if v.y > cowl_y - 0.01)
hv = wv(O['prop_hub'])
hub_back_y = min(v.y for v in hv if math.hypot(v.x, v.z) > 0.30)
hub_back_r = max(math.hypot(v.x, v.z) for v in hv if v.y < hub_back_y + 0.006)
waist = []
for j in range(12):
    yj = cowl_y + 0.005 + (2.60 - cowl_y - 0.005) * j / 11
    for k in range(24):
        az = 2 * math.pi * k / 24
        d = Vector((math.cos(az), 0, math.sin(az)))
        h = hubt.ray_cast(Vector((0, yj, 0)) + d * 1.0, -d, 1.0)
        r_ = math.hypot(h[0].x, h[0].z) if h[0] is not None else 0.0
        if r_ < 0.27:
            waist.append((round(yj, 3), k, round(r_, 3)))
gap_ax = hub_back_y - cowl_y
put('prop attached: no waist between the cowl ring and the spinner cone (288 radial rays meet the hub at r >= 0.27), hub ring <= 5 mm ahead of the cowl ring, radius within 10 mm',
    not waist and -0.002 <= gap_ax <= 0.005 and abs(hub_back_r - cowl_r) <= 0.010,
    dict(waist=waist[:6], n_waist=len(waist), cowl_front_y=round(cowl_y, 4), cowl_r=round(cowl_r, 4), hub_back_y=round(hub_back_y, 4), hub_back_r=round(hub_back_r, 4), axial_gap_mm=round(gap_ax * 1000, 1)))

# (q) round 6 canopy encloses (fault 5): from the eye, rays over the hemisphere above the sill (400 directions, from the eye and +-6 cm)
#     meet canopy / windscreen glass or frame first - nothing escapes through a gap to the wings, struts or the sky
CAN = ('canopy_slide', 'canopy_slide_glass', 'windscreen', 'windscreen_frame', 'canopy_rail', 'coaming_wall', 'spine_fwd', 'spine_aft')   # 1.8.3: + sill rails, coaming wall, spine (opaque)
cang = [o for o in O if o.type == 'MESH' and (o.name in CAN or o.name.startswith(('cockpit_', 'fus_', 'mfd_')))]
dg6 = bvh_of(cang)
names6 = []
for o in cang:
    names6 += [o.name] * len(o.data.polygons)
esc = []; nray = 0
# round 7 (in-game 1.5.2: bright unglazed slots beside the panel, below the sill): a DENSE fan (0.5 deg) from the eye over elevation
# -35..+60 deg and every azimuth; nothing may escape the cockpit / canopy / windscreen / fuselage shell
for el2 in range(-70, 121):
    for az2 in range(0, 720):
        e_ = math.radians(el2 * 0.5); a_ = math.radians(az2 * 0.5)
        d = Vector((math.sin(a_) * math.cos(e_), math.cos(a_) * math.cos(e_), math.sin(e_)))
        nray += 1
        if dg6.ray_cast(Vector(S.EYE), d, 4.0)[0] is None:
            esc.append((el2 * 0.5, az2 * 0.5))
put('canopy encloses (round 7: dense 0.5 deg fan, elevation -35..+60, all azimuths): every ray from the eye meets canopy / windscreen glass or frame, cockpit or fuselage (no unglazed slot)',
    not esc, dict(rays=nray, escaped=len(esc), first=esc[:5]))

# (r) round 6 screens (fault 6): four screen quads on material 'screen' (whose face UVs survive the export), UVs inside their tac-page region
import fd32_cockpit as FC_
uvres = {}
for nm_, (dx, dy, w, r, rot) in FC_.SCREENS.items():
    o = O.get('mfd_' + nm_)
    if o is None:
        uvres[nm_] = 'missing'; continue
    mats_ = sorted({o.data.materials[p_.material_index].name for p_ in o.data.polygons})
    uvl = o.data.uv_layers['livery'].data
    us = [uvl[i].uv for i in range(len(uvl))]
    ok_ = mats_ == ['screen'] and all(r[0] - 1e-3 <= u.x <= r[1] + 1e-3 and r[2] - 1e-3 <= u.y <= r[3] + 1e-3 for u in us) and \
        (max(u.x for u in us) - min(u.x for u in us)) > 0.9 * (r[1] - r[0])
    uvres[nm_] = dict(ok=ok_, mats=mats_, u=(round(min(u.x for u in us), 3), round(max(u.x for u in us), 3)), v=(round(min(u.y for u in us), 3), round(max(u.y for u in us), 3)))
put('screens: mfd_map / power / flight / engine are separate quads on material screen with their tac-page UV regions (livery UV0)',
    all(isinstance(v, dict) and v['ok'] for v in uvres.values()) and not any(o.name == 'mfd_tac' for o in O), uvres)

# (m) ejection with the canopy: the seat column (stock seat footprint) from the seat top up is clear of everything except the canopy,
#     which is jettisoned first (Canopy.ejectionForce straight up); the jettisoned canopy (lifted 1.5 m) clears the upper wing / cabane
ey = Vector(S.EYE)
cmn2, cmx2 = Vector((ey.x - 0.30, ey.y - 0.32, 0.55)), Vector((ey.x + 0.30, ey.y + 0.25, 3.5))
col2 = box_bvh(cmn2, cmx2)
ej2 = [o.name for o in O if o.type == 'MESH' and not o.name.startswith(('cockpit_', 'mfd_', 'canopy_slide', 'fus_')) and o.name not in ('windscreen', 'windscreen_frame')
       and bvh_of([o]) is not None and col2.overlap(bvh_of([o]))]
up15 = Matrix.Translation(Vector((0, 0, 1.5)))
cv_, cf_ = [], []
for o in (O['canopy_slide'], O['canopy_slide_glass']):
    b0 = len(cv_); cv_ += [up15 @ v for v in wv(o)]; cf_ += [tuple(b0 + i for i in p_.vertices) for p_ in o.data.polygons]
jt = BVHTree.FromPolygons(cv_, cf_)
jc = [n for n in ('wing_upper_C', 'cabane', 'wing_upper_L', 'wing_upper_R') if n in O and jt.overlap(bvh_of([O[n]]))]
put('ejection: seat column clear above the cockpit (canopy jettisoned first); the canopy jettisoned 1.5 m up clears the upper wing / cabane',
    not ej2 and not jc, dict(column_hits=ej2, canopy_hits=jc))


# ===================================================================================== 1.8.3 (offline B): canopy, opening, specks, internals
import internals_r183 as IN_
pk = IN_.poke_count({o.name: o for o in O if o.type == 'MESH'})
put('1.8.3 no cockpit part pokes through the skin or sits < 1 mm under it (dark specks on the skin)', not pk, {k: (len(v), v[:3]) for k, v in pk.items()})
# engine / power plant inside the cowl (ray parity against the cowl skin, upward rays, the engine box only)
es = O.get('fus_engine_struct'); outside = []; nst = 0
if es is not None:
    sk = O['fus_engine']; skm = [m.name if m else '' for m in sk.data.materials]
    skb = BVHTree.FromPolygons(wv(sk), [tuple(p_.vertices) for p_ in sk.data.polygons if skm[p_.material_index] == 'paint'])
    def _inside(p_):
        votes = 0
        for d_ in (Vector((0, 0, 1)), Vector((0.05, 0.3, 1)).normalized(), Vector((-0.15, -0.2, 1)).normalized()):
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
        if 0.10 < p_.y < 2.32 and abs(p_.x) < 0.37 and -0.50 < p_.z < 0.38 and not _inside(p_):
            outside.append([round(p_.x, 3), round(p_.y, 3), round(p_.z, 3)])
    mi = [m.name if m else '' for m in es.data.materials]
    nst = sum(1 for pl in es.data.polygons if mi[pl.material_index] == 'structure')
put('1.8.3 internals: motor + turbogenerator + batteries + fuel tank in fus_engine_struct (structure = stock aircraft_structure in Unity), inside the cowl skin',
    es is not None and nst > 400 and not outside, dict(structure_faces=nst, outside=outside[:6]))
# canopy shape: head clearance, sill line smooth, windscreen rake, one-piece bubble, spine reaching the fin
import fd32_canopy183 as CAN_
if CAN_.ENABLED:
    hg = O['canopy_slide_glass']; gv = wv(hg)
    ey_ = Vector(S.EYE)
    top_over_eye = max(v.z for v in gv if abs(v.y - ey_.y) < 0.15 and abs(v.x) < 0.05)
    ys_ = [CAN_.WS_BASE_Y + (CAN_.HOOD_REAR_Y - CAN_.WS_BASE_Y) * k / 40 for k in range(41)]
    rb = bvh_of([O['canopy_rail']])
    zz = [(rb.ray_cast(Vector((CAN_.rail_x(y) + 0.0013, y, 2.0)), Vector((0, 0, -1)), 3.0)[0] or Vector((0, 0, -9))).z for y in ys_]
    sec2 = max(abs(zz[i - 1] - 2 * zz[i] + zz[i + 1]) for i in range(1, len(zz) - 1))
    rail_off = 0.0
    wsv = wv(O['windscreen']); top_ws = max(wsv, key=lambda v: v.z); base_ws = min((v for v in wsv if abs(v.x) < 0.03), key=lambda v: v.z)
    rake = math.degrees(math.atan2(top_ws.z - base_ws.z, base_ws.y - top_ws.y))
    spv = wv(O['spine_aft']); sp_end = min(v.y for v in spv)
    fin_le = max((v.y for v in wv(O['fin']) if v.z < 0.40), default=-9)
    ok_ = 1.03 <= top_over_eye <= 1.09 and sec2 < 0.004 and rail_off < 0.004 and 28 <= rake <= 40 and sp_end <= fin_le + 0.12
    put('1.8.3 canopy shape: hood top 1.03-1.09 over the eye (head top ~0.92), sill rail smooth in side view (2nd difference < 4 mm), windscreen rake 28-40 deg (polish: ~33), spine runs to the fin leading edge',
        ok_, dict(top_over_eye=round(top_over_eye, 3), rail_second_diff_mm=round(sec2 * 1000, 2), rail_mesh_vs_line_mm=round(rail_off * 1000, 1), rake_deg=round(rake, 1), spine_end_y=round(sp_end, 3), fin_le_y=round(fin_le, 3)))
    # opening: no skin face inside the hole outline (except the 4 mm front / rear fans) and the hole edge jumps < 6 mm between neighbours
    fc = O['fus_center']; fm = [m.name if m else '' for m in fc.data.materials]
    inside_faces = 0
    for pl in fc.data.polygons:
        if fm[pl.material_index] != 'paint':
            continue
        c_ = fc.matrix_world @ pl.center
        hx_ = CAN_.hole_hx(c_.y)
        if hx_ > 0.01 and abs(c_.x) < hx_ - 0.01 and c_.z > 0.45 and CAN_.HOLE['y_rear'] + 0.01 < c_.y < CAN_.HOLE['y_front'] - 0.01:
            inside_faces += 1
    wl = [O['coaming_wall'].matrix_world @ v.co for v in O['coaming_wall'].data.vertices]
    tops_ = {}
    for v in wl:
        if v.x > 0.30 and CAN_.HOLE['y_rear'] + 0.03 < v.y < CAN_.HOLE['y_front'] - 0.03 and abs(v.x - CAN_.hole_hx(v.y)) < 0.0005:   # the straight sides (the rounded ends fade the sill shift)
            k_ = round(v.y, 4)
            if k_ not in tops_ or v.z > tops_[k_].z:
                tops_[k_] = v                                                       # the wall's top edge = the hole edge
    top_w = [tops_[k_] for k_ in sorted(tops_, reverse=True)]
    zs_ = [v.z for v in top_w]
    z2 = max((abs(zs_[i - 1] - 2 * zs_[i] + zs_[i + 1]) for i in range(1, len(zs_) - 1)), default=1)
    put('1.8.3 cockpit opening rebuilt on the stretched skin: no skin inside the hole outline, edge on the designed outline, no steps along it (z 2nd difference < 6 mm), coaming wall down from the edge',
        inside_faces == 0 and len(top_w) >= 20 and z2 < 0.006 and len(wl) > 40, dict(skin_faces_in_hole=inside_faces, edge_pts=len(top_w), edge_z_second_diff_mm=round(z2 * 1000, 2), wall_verts=len(wl)))
    con_ = json.load(open(os.path.join(HERE, '..', '..', 'assets', 'model_fd32', 'fd32_contract.json')))
    hl = con_.get('collider_fus_center', {})
    put('1.8.3 root collider: contract carries the convex hull of the 1.8.2 fus_center skin (FD32Build bakes the FD32 collider from it: same CoM / inertia)',
        len(hl.get('verts', [])) > 50 and len(hl.get('tris', [])) > 50, dict(verts=len(hl.get('verts', [])), tris=len(hl.get('tris', []))))

os.makedirs(os.path.dirname(os.path.abspath(OUTP)), exist_ok=True)
json.dump(res, open(OUTP, 'w'), indent=1)
fails = [k for k, v in res.items() if not v['ok']]
print(f'[check] {len(res) - len(fails)}/{len(res)} PASS')
if fails:
    sys.exit(1)
