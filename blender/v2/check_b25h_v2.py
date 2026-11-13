"""Verify the exported B-25H v2 FBX by importing it back into an empty Blender scene.

  blender --background --factory-startup --python blender/v2/check_b25h_v2.py -- assets/model_v2/b25h_v2.fbx [--json out.json]

Two imports:
  1. RAW (manual orientation = identity): Blender coords == FBX file coords; Unity = (-X, Y, Z).
     Used for: orientation in Unity, root rotation, bbox, pivots.
  2. Normal import (the file's own axis settings): back in the authoring frame for geometry checks.
Exit code 1 if any hard check fails.
"""
import bpy, bmesh, sys, os, json, math, random
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:]
fbx = argv[0]
jout = argv[argv.index('--json') + 1] if '--json' in argv else None

REQUIRED = (['B25H_root', 'fus_nose', 'fus_cockpit', 'fus_forward', 'fus_center', 'fus_rear', 'fus_tail',
             'canopy_glass', 'canopy_frame', 'turret_dorsal', 'turret_dorsal_guns', 'tail_guns', 'hatch_waist_L',
             'hatch_waist_R', 'waist_gun_L', 'waist_gun_R', 'nose_guns', 'cannon', 'package_guns_L', 'package_guns_R',
             'gear_nose_strut', 'gear_nose_wheel', 'gear_door_nose_L', 'gear_door_nose_R', 'bomb_door_L', 'bomb_door_R',
             'hp_bombbay', 'muzzle_cannon', 'cockpit_eye', 'cockpit_interior', 'cockpit_seat_L', 'cockpit_seat_R',
             'cockpit_yoke_L', 'cockpit_rudder_pedals_L', 'cockpit_gauges'] +
            [f'muzzle_nose_{k}' for k in range(1, 5)] + ['muzzle_package_L1', 'muzzle_package_L2', 'muzzle_package_R1',
             'muzzle_package_R2', 'muzzle_turret_L', 'muzzle_turret_R', 'muzzle_tail_L', 'muzzle_tail_R'])
for L in 'LR':
    REQUIRED += [f'wing_inner_{L}', f'wing_outer_{L}', f'wing_tip_{L}', f'aileron_{L}', f'flap_inner_{L}', f'flap_outer_{L}',
                 f'nacelle_{L}', f'engine_{L}', f'exhaust_{L}', f'prop_hub_{L}', f'stab_{L}', f'elevator_{L}', f'fin_{L}',
                 f'rudder_{L}', f'gear_main_{L}_strut', f'gear_main_{L}_wheel', f'gear_door_main_{L}_a', f'gear_door_main_{L}_b',
                 f'hp_wingrack_{L}'] + [f'prop_{L}_blade{k}' for k in (1, 2, 3)] + [f'hp_rail_{L}{k}' for k in range(1, 5)] + \
                [f'cowl_flap_{L}_{k:02d}' for k in range(1, 15)] +                 ([f'cockpit_column_{L}', f'cockpit_yoke_{L}', f'cockpit_rudder_pedals_{L}'] if L == 'L' else []) + [f'cockpit_seat_{L}', f'pylon_wingrack_{L}',
                 f'hatch_waist_{L}_hinge', f'waist_gun_{L}_mount', f'waist_gun_{L}_az', f'gun_waist_{L}', f'muzzle_waist_{L}',
                 f'prop_disc_{L}', f'gun_turret_{L}', f'gun_tail_{L}'] + [f'pylon_rail_{L}{k}' for k in range(1, 5)]
# v3 objects (contract)
REQUIRED += ['hatch_cockpit_top', 'hatch_cockpit_top_hinge', 'hatch_entry_fwd', 'hatch_entry_fwd_hinge', 'hatch_entry_rear',
             'hatch_entry_rear_hinge', 'turret_dorsal_mount', 'tail_turret_mount', 'tail_turret_az', 'mfd_center', 'mfd_left',
             'mfd_right', 'gunsight_pilot', 'gunsight_combiner', 'crew_navigator_eye', 'crew_engineer_eye', 'crew_radio_eye',
             'crew_tail_eye', 'crew_seat_radio', 'crew_seat_tail'] +             [f'gauge_{g}_needle' for g in ('airspeed', 'altimeter', 'vsi', 'fuel', 'manifold_L', 'manifold_R', 'rpm_L', 'rpm_R')] +             ['gauge_altimeter_needle_short', 'gauge_attitude_card', 'gauge_heading_card']
MATS = {'paint', 'interior', 'structure', 'glass', 'metal_dark', 'rubber', 'prop', 'prop_tip', 'cockpit', 'gauges', 'screen'}
EXTERIOR_MATS = {'paint', 'glass', 'rubber', 'metal_dark', 'prop', 'prop_tip'}

res = {'checks': [], 'fail': 0}


def check(name, ok, detail=''):
    res['checks'].append(dict(name=name, ok=bool(ok), detail=detail))
    if not ok:
        res['fail'] += 1
    print(('PASS ' if ok else 'FAIL ') + name + (' : ' + str(detail) if detail else ''))


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def wbbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


# ------------------------------------------------------------------ 1. RAW import (FBX/Unity frame)
clear()
bpy.ops.import_scene.fbx(filepath=fbx, use_manual_orientation=True, axis_forward='Y', axis_up='Z', global_scale=1.0,
                         bake_space_transform=False, use_custom_normals=True)
O = bpy.data.objects
U = lambda v: Vector((-v[0], v[1], v[2]))      # FBX (right-handed) -> Unity (left-handed): negate X
names = {o.name for o in O}
# 1.8.16 livery-atlas guard on the FBX that Unity imports (B-25H textures_v2 / GA-25X textures_ga25x by the FBX folder)
_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(fbx)), '..', '..'))   # <repo>/assets/model_*/x.fbx (also for the GA-25X temp copy)
sys.path.insert(0, os.path.join(_REPO, 'blender'))
import atlas_guard as AG
_ga = os.path.basename(fbx).lower().startswith('ga25x')
_mf = os.path.join(_REPO, 'assets', 'textures_ga25x' if _ga else 'textures_v2', ('ga25x' if _ga else 'b25h') + '_atlas_manifest.json')
check('1.8.16 livery atlas == texture manifest (skin / liveries / damage painted on this atlas; re-bake the textures when it fails)', *AG.check_row(_mf))
missing = [n for n in REQUIRED if n not in names]
check('required object names present', not missing, f'missing={missing}' if missing else f'{len(REQUIRED)} names')
root = O.get('B25H_root')
if root:
    rq = root.matrix_world.to_quaternion()
    check('root has no rotation (identity)', abs(abs(rq.w) - 1) < 1e-4, f'quat={tuple(round(x, 5) for x in rq)}')
    check('root scale 1', all(abs(s - 1) < 1e-4 for s in root.matrix_world.to_scale()), str(tuple(root.matrix_world.to_scale())))
mesh_objs = [o for o in O if o.type == 'MESH']
a, b = wbbox(mesh_objs)
ua, ub = U(a), U(b)
size = Vector((abs(ub.x - ua.x), b.y - a.y, b.z - a.z))   # Unity: x span, y height, z length
res['bbox_unity_size'] = tuple(round(v, 3) for v in size)
check('bbox span ~20.60 m (Unity X)', abs(size.x - 20.60) < 0.05, f'{size.x:.3f}')
check('bbox height ~4.98 m on gear (Unity Y)', abs(size.y - 4.98) < 0.06, f'{size.y:.3f}')
print('INFO bbox length incl. gun barrels (Unity Z) =', round(size.z, 3))


def upos(n):
    return U(O[n].matrix_world.translation)


if all(n in names for n in ('muzzle_cannon', 'muzzle_tail_L', 'wing_tip_R', 'wing_tip_L', 'fin_R')):
    check('nose points +Z in Unity', upos('muzzle_cannon').z > upos('muzzle_tail_L').z + 10, f"cannon z={upos('muzzle_cannon').z:.2f} tail z={upos('muzzle_tail_L').z:.2f}")
    wr = wbbox([O['wing_tip_R']])
    check('right wing on +X in Unity', U((wr[0] + wr[1]) / 2).x > 5, f"wing_tip_R centre x={U((wr[0] + wr[1]) / 2).x:.2f}")
    fr = wbbox([O['fin_R']])
    check('up is +Y in Unity (fin top above wheels)', fr[1].y > wbbox([O['gear_main_R_wheel']])[0].y + 4.0)
    # cockpit eye on the left (pilot) side
    check('cockpit_eye on the left (Unity x<0)', upos('cockpit_eye').x < -0.2, str(tuple(round(v, 3) for v in upos('cockpit_eye'))))
res['pivots_unity'] = {o.name: tuple(round(v, 4) for v in U(o.matrix_world.translation)) for o in O if o.type in ('MESH', 'EMPTY')}
# local rotations of wheels/struts should be identity-ish relative to the root (pivots on axles)
for w in ('gear_nose_wheel', 'gear_main_L_wheel', 'gear_main_R_wheel'):
    if w in names:
        o = O[w]
        a, b = wbbox([o])
        c = (a + b) / 2
        d = (c - o.matrix_world.translation).length
        check(f'{w} pivot at wheel bbox centre (<2 mm)', d < 0.002, f'{d * 1000:.2f} mm')
for L in 'LR':
    h = f'prop_hub_{L}'
    if h in names:
        o = O[h]
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        c = sum(vs, Vector()) / len(vs)          # hub is 3-fold symmetric: vertex mean lies on the axis
        p = o.matrix_world.translation
        # spin axis = Unity +Z = FBX +Z; check hub bbox centre on the axis through the pivot (x,y)
        off = math.hypot(c.x - p.x, c.y - p.y)
        check(f'{h} pivot on prop axis (<2 mm)', off < 0.002, f'{off * 1000:.2f} mm')
        fwd = o.matrix_world.to_3x3() @ Vector((0, 0, 1))
        check(f'{h} local +Z (Unity) = forward spin axis', fwd.z > 0.999, str(tuple(round(v, 4) for v in fwd)))
        for k in (1, 2, 3):
            bl = O[f'prop_{L}_blade{k}']
            dd = (bl.matrix_world.translation - p).length
            check(f'prop_{L}_blade{k} pivot at hub centre', dd < 0.002, f'{dd * 1000:.2f} mm')
        b1 = wbbox([O[f'prop_{L}_blade1']])
        check(f'prop_{L}_blade1 points up', (b1[0].y + b1[1].y) / 2 > p.y + 0.5)

# ------------------------------------------------------------------ 2. normal import (authoring frame) - geometry checks
clear()
bpy.ops.import_scene.fbx(filepath=fbx, use_custom_normals=True)
O = bpy.data.objects
mesh_objs = [o for o in O if o.type == 'MESH']
mats = set()
ngons = 0
tris = 0
groups = {}
uv_missing = []
for o in mesh_objs:
    me = o.data
    mats |= {m.name.split('.')[0] for m in me.materials if m}
    if 'livery' not in me.uv_layers or 'detail' not in me.uv_layers:
        uv_missing.append(o.name)
    t = 0
    for p in me.polygons:
        if len(p.vertices) > 4:
            ngons += 1
        t += len(p.vertices) - 2
    tris += t
    n = o.name
    g = ('fuselage' if n.startswith('fus_') else 'wings+controls' if n.startswith(('wing', 'aileron', 'flap')) else
         'nacelles' if n.startswith('nacelle') else 'engines+cowl flaps+exhaust' if n.startswith(('engine', 'cowl_flap', 'exhaust')) else
         'props' if n.startswith('prop') else 'tail' if n.startswith(('stab', 'elevator', 'fin', 'rudder')) else
         'gear+doors' if n.startswith(('gear', 'bomb_door')) else 'cockpit' if n.startswith('cockpit') or n.startswith('canopy') else
         'armament+glazing')
    groups[g] = groups.get(g, 0) + t
res['tris_total'] = tris
res['tris_by_group'] = groups
check('materials named exactly', MATS <= mats, f'present={sorted(mats)}')
check('no n-gons', ngons == 0, f'{ngons}')
check('both UV maps (livery, detail) on every mesh', not uv_missing, str(uv_missing[:5]))
check('triangle budget (<= 180k incl. interiors)', tris <= 180000, f'{tris}')

# livery overlap (paint faces only), raster 2048
N = 2048
cnt = bytearray(N * N)
covered = over = 0
paint_area = 0.0
for o in mesh_objs:
    me = o.data
    if 'livery' not in me.uv_layers:
        continue
    lay = me.uv_layers['livery'].data
    me.calc_loop_triangles()
    for tri in me.loop_triangles:
        mat = me.materials[tri.material_index]
        if not mat or not mat.name.startswith('paint'):
            continue
        A, B, C = (lay[li].uv for li in tri.loops)
        paint_area += abs((B.x - A.x) * (C.y - A.y) - (C.x - A.x) * (B.y - A.y)) / 2
        xs = [A.x * N, B.x * N, C.x * N]
        ys = [A.y * N, B.y * N, C.y * N]
        x0, x1 = max(0, int(min(xs))), min(N - 1, int(max(xs)) + 1)
        y0, y1 = max(0, int(min(ys))), min(N - 1, int(max(ys)) + 1)
        ax, ay, bx, by, cx, cy = xs[0], ys[0], xs[1], ys[1], xs[2], ys[2]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        for py in range(y0, y1 + 1):
            fy = py + 0.5
            for px in range(x0, x1 + 1):
                fx = px + 0.5
                l1 = ((by - cy) * (fx - cx) + (cx - bx) * (fy - cy)) / den
                l2 = ((cy - ay) * (fx - cx) + (ax - cx) * (fy - cy)) / den
                l3 = 1 - l1 - l2
                e = -1e-9
                if l1 > e and l2 > e and l3 > e:
                    k = py * N + px
                    if cnt[k] == 1:
                        over += 1
                    if cnt[k] < 255:
                        cnt[k] += 1
                    if cnt[k] == 1:
                        covered += 1
frac = over / max(covered, 1)
res['livery_uv_usage'] = round(paint_area, 4)
res['livery_overlap_pixels_frac'] = round(frac, 5)
check('livery UVs non-overlapping (raster 2048, <0.3% overlap px)', frac < 0.003, f'overlap {over} px of {covered} ({frac * 100:.3f}%)')
check('livery UV usage >= 70%', paint_area >= 0.70, f'{paint_area * 100:.1f}%')
oob = 0
for o in mesh_objs:
    if 'livery' in o.data.uv_layers:
        for d in o.data.uv_layers['livery'].data:
            if not (-1e-4 <= d.uv.x <= 1.0001 and -1e-4 <= d.uv.y <= 1.0001):
                oob += 1
check('livery UVs inside 0-1', oob == 0, f'{oob} loops outside')

# exterior normals: rays from a sphere around the aircraft; the first surface hit must be front-facing
dg = bpy.context.evaluated_depsgraph_get()
bvhs = []
for o in mesh_objs:
    bm = bmesh.new()
    bm.from_object(o, dg)
    bm.transform(o.matrix_world)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    mats_f = [o.material_slots[f.material_index].material.name.split('.')[0] if o.material_slots and o.material_slots[f.material_index].material else '' for f in bm.faces]
    bvhs.append((o.name, BVHTree.FromBMesh(bm), mats_f, [f.normal.copy() for f in bm.faces]))
    bm.free()
rnd = random.Random(3)
nray = 6000
back = {}
hits = 0
ba, bb = wbbox(mesh_objs)
centre = (ba + bb) / 2
half = (bb - ba) / 2
for i in range(nray):
    d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
    origin = centre + d * 30
    tgt = centre + Vector((rnd.uniform(-half.x, half.x), rnd.uniform(-half.y, half.y), rnd.uniform(-half.z, half.z)))
    ray = (tgt - origin).normalized()
    best = None
    for name, t, mf, nf in bvhs:
        loc, nrm, idx, dist = t.ray_cast(origin, ray)
        if loc is not None and (best is None or dist < best[0]):
            best = (dist, name, idx, mf[idx], nf[idx], loc, t)
    if best is None:
        continue
    hits += 1
    if best[4].dot(ray) > 0:
        # a deliberately double-sided wall has a coincident front-facing twin: accept it
        twin = False
        for name, t, mf, nf in bvhs:
            for co, nn, ii, dd in t.find_nearest_range(best[5], 2e-4):
                if nf[ii].dot(ray) < 0 and abs(nf[ii].dot(best[4]) + 1) < 1e-3:
                    twin = True
        if twin:
            continue
        k = f'{best[1]}:{best[3]}'
        back[k] = back.get(k, 0) + 1
        res.setdefault('backface_samples', []).append((k, tuple(round(v, 2) for v in best[5]), tuple(round(v, 2) for v in ray)))
res['exterior_ray_hits'] = hits
res['exterior_backface_hits'] = back
nb = sum(back.values())
check('exterior normals: first hit from outside is front-facing (6000 rays)', nb <= max(3, hits * 0.001), f'{nb} back-face hits of {hits}: {dict(list(back.items())[:8])}')

# ------------------------------------------------------------------ 1.8.14 (offline M): roof skin round the dorsal opening, torn seams
# authoring frame from two fuselage pivots (fus_forward (0, 2.62, 0.25), fus_cockpit (0, 4.55, 0.25) in b25h_v2 build)
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location('b25h_spec', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'b25h_spec.py'))
SS = _ilu.module_from_spec(_spec); _spec.loader.exec_module(SS)
_pf, _pc = O['fus_forward'].matrix_world.translation, O['fus_cockpit'].matrix_world.translation
_sy = (4.55 - 2.62) / (_pc.y - _pf.y)
_cy, _cz = 2.62 - _sy * _pf.y, 0.25 - _pf.z
A_ = lambda v: Vector((v.x, _sy * v.y + _cy, v.z + _cz))
_fus = [o for o in mesh_objs if o.name.startswith('fus_')]
_bm = {}
for o in _fus:
    bm = bmesh.new(); bm.from_object(o, dg); bm.transform(o.matrix_world); bm.normal_update(); bm.faces.ensure_lookup_table()
    mf = [o.material_slots[f.material_index].material.name.split('.')[0] if o.material_slots and o.material_slots[f.material_index].material else '' for f in bm.faces]
    _bm[o.name] = (bm, mf)
_K = lambda p: (round(p.x, 4), round(p.y, 4), round(p.z, 4))
TC = Vector(SS.TURRET_C)
# R1: boundary edges of the welded fus_* paint skin near the dorsal opening
_eu = {}
for nm, (bm, mf) in _bm.items():
    for f, m in zip(bm.faces, mf):
        if m != 'paint':
            continue
        vs = [A_(v.co) for v in f.verts]
        for a_, b_ in zip(vs, vs[1:] + vs[:1]):
            k = tuple(sorted((_K(a_), _K(b_))))
            _eu[k] = _eu.get(k, 0) + 1
_open, _other = [], []
for k, n in _eu.items():
    if n != 1:
        continue
    m = (Vector(k[0]) + Vector(k[1])) / 2
    r = math.hypot(m.x, m.y - TC.y)
    if r <= 0.90 and m.z > 0.95:
        (_open if r < 0.62 else _other).append((round(m.x, 3), round(m.y, 3), round(m.z, 3), round(r, 3)))
_deg = {}
for k, n in _eu.items():
    if n == 1:
        m = (Vector(k[0]) + Vector(k[1])) / 2
        if math.hypot(m.x, m.y - TC.y) < 0.62 and m.z > 0.95:
            for q in k:
                _deg[q] = _deg.get(q, 0) + 1
_odd = sum(1 for d in _deg.values() if d % 2)
res['roof_dorsal_boundary_1814'] = dict(opening_edges=len(_open), other_edges=_other[:20], odd_vertices=_odd)
check('1.8.14 roof skin round the dorsal opening: no open edge except the opening itself (welded fus_* paint, r <= 0.90 m, roof)',
      not _other and len(_open) > 0 and _odd == 0, f'opening {len(_open)} edges (all r < 0.62, under the trim ring), other open edges {len(_other)} {_other[:4]}, odd-degree opening vertices {_odd}')
# R2 / R3: torn seams - dark lap strip under every two-sided seam edge, no structure within 2.5 mm of the outer skin, lap under the skin
def _bvh(sel):
    vs, fs = [], []
    for nm, (bm, mf) in _bm.items():
        for f, m in zip(bm.faces, mf):
            if sel(nm, m, f):
                b0 = len(vs); vs += [v.co.copy() for v in f.verts]; fs.append(list(range(b0, b0 + len(f.verts))))
    return BVHTree.FromPolygons(vs, fs) if fs else None
_struct = _bvh(lambda nm, m, f: m == 'structure')
_paint = _bvh(lambda nm, m, f: m == 'paint')
_tears = {y: ab for y, ab in SS.FUS_TORN.items()}
_lap = _bvh(lambda nm, m, f: m == 'metal_dark' and any(abs(A_(f.calc_center_median()).y - y) < 0.10 for y in _tears))
seam_rows, bad_s, bad_l, nsamp = {}, [], [], 0
for y, (a, b) in _tears.items():
    ea, eb = {}, {}
    for nm, store in ((a, ea), (b, eb)):
        bm, mf = _bm[nm]
        for f, m in zip(bm.faces, mf):
            if m != 'paint':
                continue
            vs = list(f.verts)
            for i in range(len(vs)):
                p0, p1 = vs[i].co, vs[(i + 1) % len(vs)].co
                if abs(A_(p0).y - y) < 0.075 and abs(A_(p1).y - y) < 0.075:
                    k = tuple(sorted((_K(p0), _K(p1))))
                    store.setdefault(k, []).append(f.normal.copy())
    common = [k for k in ea if k in eb]
    _use = {}
    for k in common:
        for q in k:
            _use[q] = _use.get(q, 0) + 1
    ns = nb_ = 0
    for k in common:
        n = (sum(ea[k], Vector()) + sum(eb[k], Vector())).normalized()
        for t in (0.0, 0.5, 1.0):
            if (t == 0.0 and _use[k[0]] == 1) or (t == 1.0 and _use[k[1]] == 1):
                continue                    # run end = corner of a hole (nose well, canopy): its structure rim is the hole's own edge
            p = Vector(k[0]).lerp(Vector(k[1]), t)
            nsamp += 1; ns += 1
            ds = _struct.find_nearest(p)[3] if _struct else 9
            dl = _lap.find_nearest(p)[3] if _lap else 9
            if ds is not None and ds < 0.0025:
                bad_s.append((y, tuple(round(v, 3) for v in A_(p)), round(ds * 1000, 2)))
            if dl is None or dl > 0.0025:
                bad_l.append((y, tuple(round(v, 3) for v in A_(p)), None if dl is None else round(dl * 1000, 2)))
    seam_rows[str(y)] = dict(seam_edges=len(common), samples=ns)
# lap vertices under the skin: a ray outward from each lap vertex meets the paint skin within 0.5-3.5 mm
lap_v, lap_bad = 0, []
for nm, (bm, mf) in _bm.items():
    for f, m in zip(bm.faces, mf):
        if m != 'metal_dark' or not any(abs(A_(f.calc_center_median()).y - y) < 0.10 for y in _tears):
            continue
        for v in f.verts:
            lap_v += 1
            hit = _paint.ray_cast(v.co + f.normal * 1e-5, f.normal, 0.01)
            if hit[0] is None or not (0.0004 <= hit[3] <= 0.0035):
                lap_bad.append((nm, tuple(round(c, 3) for c in A_(v.co)), None if hit[0] is None else round(hit[3] * 1000, 2)))
res['seams_1814'] = dict(per_seam=seam_rows, samples=nsamp, structure_near_skin=bad_s[:20], no_lap=bad_l[:20], lap_vertices=lap_v, lap_not_under_skin=lap_bad[:20])
check('1.8.14 torn fuselage seams: dark lap strip <= 2.5 mm under every two-sided seam edge, no structure face within 2.5 mm of the outer skin',
      nsamp > 0 and not bad_s and not bad_l, f'{nsamp} samples on {sum(r["seam_edges"] for r in seam_rows.values())} seam edges ({seam_rows}); structure near the skin {len(bad_s)} {bad_s[:3]}; no lap {len(bad_l)} {bad_l[:3]}')
check('1.8.14 lap strips stay under the skin: every lap vertex 0.4-3.5 mm below the outer skin along its normal',
      lap_v > 0 and not lap_bad, f'{lap_v} lap vertices, {len(lap_bad)} not under the skin {lap_bad[:4]}')
for bm, mf in _bm.values():
    bm.free()

print('SUMMARY', json.dumps({k: v for k, v in res.items() if k not in ('checks', 'pivots_unity')}))
if jout:
    with open(jout, 'w') as f:
        json.dump(res, f, indent=1)
sys.exit(1 if res['fail'] else 0)
