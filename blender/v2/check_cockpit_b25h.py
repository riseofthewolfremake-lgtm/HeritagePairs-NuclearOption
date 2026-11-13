"""B-25H cockpit rebuild checks (2026-11-01), ported from the GA-25X cockpit checks (check_v030_ga25x.py).

  blender --background assets/model_v2/b25h_v2.blend --python blender/v2/check_cockpit_b25h.py -- <out.json>

  * controls touch their mounts: the column base on its floor plate, each lever hub inside its slot well (< 5 mm)
  * throttle levers stay in their slots over 0..range (Cockpit.throttles), never cut the housing face
  * rudder pedal plates face aft and up (foot presses forward)
  * crew legs (COIN figure bone pose, as on the GA-25X) clear of every cabin part, for the pilot and the navigator
  * no floating cabin part (every mesh island touches / overlaps something within 3 mm)
  * z-fight: no coplanar overlapping faces (other part / island, same-facing, < 1 mm, >= 0.25 cm2)
  * the art and the dials: every real dial sits over a black hole of the fal panel art (art pixel under each dial centre is dark)
Exit code 1 on any failure.
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import b25h_spec as S
import b25h_cockpit_layout as LY
out = sys.argv[sys.argv.index('--') + 1]
O = bpy.data.objects
res = {}


def put(name, ok, detail=''):
    res[name] = dict(ok=bool(ok), detail=detail if isinstance(detail, str) else json.dumps(detail, default=str)[:600])
    print(('PASS ' if ok else 'FAIL ') + name, res[name]['detail'][:600], flush=True)


def wv(o):
    return [o.matrix_world @ v.co for v in o.data.vertices]


def bvh_of(objs, M=None):
    vs, fs = [], []
    for o in objs:
        mw = (M or Matrix.Identity(4)) @ o.matrix_world
        b = len(vs)
        vs += [mw @ v.co for v in o.data.vertices]
        fs += [tuple(i + b for i in p.vertices) for p in o.data.polygons]
    return BVHTree.FromPolygons(vs, fs) if fs else None


CAB = [n for n in O.keys() if O[n].type == 'MESH' and (n.startswith(('cockpit_', 'gauge_', 'quadrant_', 'mfd_', 'gunsight_')))]
interior = O['cockpit_interior']
house = bvh_of([interior])
# ---- controls on mounts
col = O['cockpit_column_L']
cv = wv(col)
zmin = min(v.z for v in cv)
import b25h_cockpit2 as CK2
put('column base sits on its floor plate (gap < 5 mm)', abs(zmin - CK2.PLATE_TOP) < 0.005,
    f'column lowest z {zmin:.4f} (plate top {CK2.PLATE_TOP:.3f})')
lev = {}
for L in 'LR':
    o = O[f'quadrant_throttle_{L}']
    inf = json.loads(o.get('b25_info') or '{}')
    piv = o.matrix_world.translation
    rng = inf.get('range_deg', 40)
    worst = None
    for deg in (0, rng / 2, rng):
        R = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-deg), 4, 'X') @ Matrix.Translation(-piv)
        vs = [R @ v for v in wv(o)]
        tb = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in o.data.polygons])
        ov = tb.overlap(house)
        hit = bool(ov)
        dmin = min(house.find_nearest(v)[3] for v in vs)
        worst = (deg, hit, round(dmin * 1000, 1)) if worst is None or hit else worst
        lev[f'{L}@{deg:.0f}'] = dict(intersects=hit, gap_mm=round(dmin * 1000, 1))
        if ov:
            ip = interior.data.polygons[ov[0][1]]
            lev[f'{L}@{deg:.0f}']['at'] = tuple(round(c, 3) for c in interior.matrix_world @ ip.center)
            lev[f'{L}@{deg:.0f}']['n_pairs'] = len(ov)
put('throttle levers: no intersection with the quadrant over 0 / mid / full travel, hub < 5 mm from the slot well', all(not v['intersects'] and v['gap_mm'] < 5 for v in lev.values()), lev)
# ---- pedals: the plate face normal (largest faces of the pedal props) points aft and up
pd = O['cockpit_rudder_pedals_L']
me = pd.data
ns = []
for p in me.polygons:
    if pd.material_slots[p.material_index].name == 'pr_pedal' and p.area > 0:
        ns.append(((pd.matrix_world.to_3x3() @ p.normal).normalized(), p.area))
# area-weighted mean normal of the faces that look aft/up (the plates)
acc = Vector()
for n, a in ns:
    if n.y < -0.2 and n.z > 0.0:
        acc += n * a
acc = acc.normalized() if acc.length else acc
put('rudder pedal plates face aft and up (foot presses forward)', acc.y < -0.3 and acc.z > 0.15, f'mean plate normal {tuple(round(c, 3) for c in acc)}')
# ---- legs (COIN figure bone pose relative to the figure root = eye + (0, 0.0651, -0.7147))
BONES = {'hip': (0.0917, 0.0048, -0.0235), 'knee': (0.1418, 0.4044, -0.0378), 'ankle': (0.1722, 0.5485, -0.4480), 'toe': (0.2090, 0.7623, -0.3900)}
targets = [n for n in CAB if not n.startswith('cockpit_seat_')]
tb_all = {n: bvh_of([O[n]]) for n in targets}
legs = []
for key in ('pilot', 'navigator'):
    eye = Vector(S.CREW[key]['eye'])
    r = eye + Vector((0, 0.0651, -0.7147))
    for side in (-1, 1):
        P = {k: Vector((r.x + side * x, r.y + f, r.z + u)) for k, (x, f, u) in BONES.items()}
        heel = P['ankle'] + Vector((0, -0.06, -0.08)); st = P['toe'] + Vector((0, 0.03, -0.045))
        samples = [(P['hip'].lerp(P['knee'], k / 20), 0.075) for k in range(21)] + [(P['knee'].lerp(P['ankle'], k / 20), 0.055) for k in range(21)]
        fl = (st - heel).length
        for k in range(15):
            p = heel.lerp(st, 0.028 / fl + (1 - 0.056 / fl) * k / 14) + Vector((0, 0, 0.03))
            samples.append((p, 0.028))
        for n, tb in tb_all.items():
            if tb is None:
                continue
            w = min(((tb.find_nearest(p)[3] or 9) - rr, tuple(round(c, 3) for c in p)) for p, rr in samples)
            if w[0] < 0:
                legs.append((key, side, n, round(w[0] * 1000, 1), w[1]))
put('crew legs (COIN bone pose, pilot + navigator) clear of every cabin part', not legs, legs[:8])
# ---- floating islands (v3: one BVH per object + a face -> island map; an island passes when a sample vertex lies within
# 3 mm of another part, or of a face of another island of the same object)
fl_bad, nisl = [], 0
others_all = {n: bvh_of([O[m] for m in CAB if m != n] + [O[m] for m in ('fus_cockpit', 'fus_forward') if m in O]) for n in CAB}
for n in CAB:
    o = O[n]
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    vis = {}
    isls = []
    for v in bm.verts:
        if v.index in vis:
            continue
        st_, isl = [v], []
        vis[v.index] = len(isls)
        while st_:
            u = st_.pop(); isl.append(u.index)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in vis:
                    vis[w.index] = len(isls); st_.append(w)
        isls.append(isl)
    bm.free()
    av = wv(o)
    polys = [tuple(p.vertices) for p in o.data.polygons]
    fisl = [vis[p[0]] for p in polys]
    own = BVHTree.FromPolygons(av, polys) if polys else None
    for k, isl in enumerate(isls):
        nisl += 1
        ok_ = False
        for i in isl:                       # every vertex (welded props make large islands; a sparse sample missed contacts)
            h = others_all[n].find_nearest(av[i]) if others_all[n] else (None, None, None, 9)
            if h[0] is not None and h[3] <= 0.003:
                ok_ = True
                break
            if own is not None and any(fisl[j] != k for (_c, _n, j, _d) in own.find_nearest_range(av[i], 0.003) if j is not None):
                ok_ = True
                break
        if not ok_ and n.startswith('quadrant_throttle_'):
            ok_ = True       # moving lever: it must hang free in its slot; its 3-5 mm slot clearance is the throttle check above
        if not ok_:
            fl_bad.append((n, len(isl), tuple(round(c, 3) for c in sum((av[i] for i in isl), Vector()) / len(isl))))
put('no floating cabin part (every mesh island within 3 mm of another part)', not fl_bad, dict(islands=nisl, floating=fl_bad[:8]))
# ---- z-fight
cv_, cf, cown = [], [], []
for n in CAB + ['fus_cockpit', 'fus_forward']:
    o = O.get(n)
    if o is None or o.type != 'MESH':
        continue
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    isl, cur = {}, 0
    for v in bm.verts:
        if v.index in isl:
            continue
        st_ = [v]; isl[v.index] = cur
        while st_:
            u = st_.pop()
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in isl:
                    isl[w.index] = cur; st_.append(w)
        cur += 1
    bm.free()
    mw = o.matrix_world
    b0 = len(cv_)
    cv_ += [mw @ v.co for v in o.data.vertices]
    for p in o.data.polygons:
        c = mw @ p.center
        if abs(c.x) < 0.75 and 2.62 < c.y < 4.45 and -0.9 < c.z < 1.4:
            cf.append(tuple(b0 + i for i in p.vertices)); cown.append((n, isl[p.vertices[0]]))
cb = BVHTree.FromPolygons(cv_, cf)


def fn(f):
    a, b, c = cv_[f[0]], cv_[f[1]], cv_[f[2]]
    nn = (b - a).cross(c - a)
    if nn.length < 1e-12 and len(f) > 3:
        nn = (c - a).cross(cv_[f[3]] - a)
    return nn.normalized() if nn.length > 0 else nn


cn = [fn(f) for f in cf]
pairs = {}
for i, f in enumerate(cf):
    pts = [cv_[k] for k in f]
    A = sum(((pts[k] - pts[0]).cross(pts[k + 1] - pts[0])).length / 2 for k in range(1, len(pts) - 1))
    if A < 1e-6:
        continue
    sm = []
    if len(pts) > 4:                       # v3: n-gons sampled over their real triangulation (the corner-fan samples fell outside
        from mathutils.geometry import tessellate_polygon   # concave n-gons onto the neighbouring faces)
        A = 0.0
        for t3 in tessellate_polygon([pts]):
            a0, b0, c0 = (pts[k] for k in t3)
            A += ((b0 - a0).cross(c0 - a0)).length / 2
            for a_ in (0.125, 0.375, 0.625, 0.875):
                for b_ in (0.125, 0.375, 0.625, 0.875):
                    if a_ + b_ < 1:
                        sm.append(a0 + (b0 - a0) * a_ + (c0 - a0) * b_)
    for a_ in (0.125, 0.375, 0.625, 0.875) if len(pts) <= 4 else ():
        for b_ in (0.125, 0.375, 0.625, 0.875):
            if len(pts) == 4:
                sm.append(pts[0].lerp(pts[1], a_).lerp(pts[3].lerp(pts[2], a_), b_))
            elif a_ + b_ < 1:
                sm.append(pts[0] + (pts[1] - pts[0]) * a_ + (pts[-1] - pts[0]) * b_)
    cnt = {}
    for s_ in sm:
        seen = set()
        for (co, nrm, j, d) in cb.find_nearest_range(s_, 0.001):
            if j is None or j == i or j in seen or cown[j] == cown[i]:
                continue
            if cn[i].dot(cn[j]) > 0.999:
                off = s_ - co
                if (off - cn[j] * off.dot(cn[j])).length > 0.0002:
                    continue
                seen.add(j); cnt[j] = cnt.get(j, 0) + 1
    for j, k in cnt.items():
        ov = A * k / len(sm)
        key = tuple(sorted((i, j)))
        if ov > pairs.get(key, (0,))[0]:
            pairs[key] = (ov, cown[i][0], cown[j][0], tuple(round(c, 3) for c in sum(pts, Vector()) / len(pts)))
big = sorted([v for v in pairs.values() if v[0] >= 0.25e-4], key=lambda v: -v[0])
for v in big:
    print('  zfight %.2f cm2 %s / %s at %s' % (v[0] * 1e4, v[1], v[2], v[3]), flush=True)
put('z-fight: no coplanar overlapping faces in the cabin (>= 0.25 cm2)', not big,
    dict(pairs=len(big), below=len(pairs) - len(big), worst=[(round(v[0] * 1e4, 2), v[1], v[2], v[3]) for v in big[:10]]))
# ---- art vs dials: check_cockpit_art_b25h.py (plain Python with PIL, outside Blender) adds its row to the same json
json.dump(res, open(out, 'w'), indent=1)
fails = [k for k, v in res.items() if not v['ok']]
print(f'[cockpit check] {len(res) - len(fails)}/{len(res)} PASS')
sys.exit(1 if fails else 0)
