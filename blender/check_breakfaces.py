"""Break-face check (1.8.3, user review 2026-11-07 item 9: every visible break-off face of a detachable part must show structure, not an
empty shell). Works on any of our .blend files (B-25H v2, GA-25X, B-17G).

  blender --background <model.blend> --python blender/check_breakfaces.py -- --out <json> [--renders <dir>] [--tag <name>]

For every detachable part (fuselage sections, wing panels, nacelles, engines, tail surfaces; hinged control surfaces are closed bodies
and are skipped) and its parent part:
  - the joint = the child's vertices within 2.5 cm of the parent's surface; n = from the joint centroid toward the child;
  - a grid of rays over the joint's cross-section (inner 80 %), from 0.4 m on the parent's side along +n, is cast at the CHILD alone
    (what you see looking into the child's break face once it has gone), and the mirror set along -n at the PARENT alone;
  - first hit: 'struct' (structure / engine / metal / well / rubber: internals), 'skin' (a paint face seen from outside: a closed
    part), 'shell' (the inside of the skin: interior material or a paint back face) or 'void' (nothing within 1.5 m: see-through).
PASS per face: struct >= 0.30 of the rays and shell + void <= 0.50 (a closed skin with structure behind it is fine).
With --renders: one image per break face (the part alone, camera on the joint axis 2.5 m out, looking in).
"""
import bpy, sys, os, json, math, random
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
OUT, RDIR, TAG = arg('--out'), arg('--renders'), arg('--tag', 'model')
INTERNALS = ('structure', 'engine', 'metal_dark', 'well', 'rubber', 'cove', 'exhaust', 'gear', 'chrome')
DETACH = ('fus_', 'wing_', 'nacelle_', 'engine_', 'stab_', 'fin', 'tail_gun', 'B17G', 'B25H', 'GA25X')
SKIP = ('_hullsrc', '_int', 'engine_face', 'fin_strip', 'wing_root_strake')


def base(n):
    return n.split('.')[0]


def is_part(o):
    n = base(o.name)
    return o.type == 'MESH' and n.startswith(DETACH) and not any(k in n for k in SKIP) and not n.endswith('_root')


parts = [o for o in bpy.data.objects if is_part(o)]
names = {o.name for o in parts}


def part_parent(o):
    p = o.parent
    while p is not None and p.name not in names:
        p = p.parent
    return p


def own_objs(o):
    """the part's mesh + mesh descendants that are not parts themselves (wells, engine faces, gear wells...), hull sources excluded"""
    out = [o]
    def walk(x):
        for c in x.children:
            if c.name in names:
                continue
            if c.type == 'MESH' and '_hullsrc' not in c.name:
                out.append(c)
            walk(c)
    walk(o)
    return out


dg = bpy.context.evaluated_depsgraph_get()


def bvh(objs):
    vs, fs, mats = [], [], []
    for o in objs:
        oe = o.evaluated_get(dg); me = oe.to_mesh(); M = o.matrix_world; b = len(vs)
        vs += [M @ v.co for v in me.vertices]
        me.calc_loop_triangles()
        for t in me.loop_triangles:
            fs.append([b + i for i in t.vertices])
            mats.append(base(o.material_slots[t.material_index].material.name) if o.material_slots and o.material_slots[t.material_index].material else '-')
        oe.to_mesh_clear()
    return BVHTree.FromPolygons(vs, fs), vs, mats


def classify(tree, mats, o, d):
    h = tree.ray_cast(o, d, 1.9)
    if h[0] is None:
        return 'void'
    m = mats[h[2]]
    front = h[1].dot(d) < 0
    if any(m.startswith(k) for k in INTERNALS):
        return 'struct'
    if m == 'paint' and front:
        return 'skin'
    if m.startswith('ck_') or m.startswith('bk_') or m.startswith('pr_') or m in ('glass', 'gauges', 'cockpit', 'screen', 'prop', 'tyre'):
        return 'skin'          # cockpit kit / props / glass: solid things, not an empty shell
    return 'shell'


res = {'tag': TAG, 'faces': []}
rnd = random.Random(7)
for c in sorted(parts, key=lambda o: o.name):
    p = part_parent(c)
    if p is None:
        continue
    ct, cv, cm = bvh(own_objs(c))
    pt, pv, pm = bvh(own_objs(p))
    # joint points: child vertices near the parent's surface
    joint = [v for v in cv if (pt.find_nearest(v, 0.025)[0] is not None)]
    if len(joint) < 12:
        res['faces'].append(dict(child_part=c.name, parent_part=p.name, note=f'no joint ({len(joint)} pts)'))
        continue
    jc = sum(joint, V()) / len(joint)
    ccen = sum(cv, V()) / len(cv)
    n = (ccen - jc)
    if n.length < 1e-4:
        continue
    n.normalize()
    # project the joint on the plane perpendicular to n; sample the inner 80 % of its extent
    u = n.orthogonal().normalized(); w = n.cross(u)
    pu = [(v - jc).dot(u) for v in joint]; pw = [(v - jc).dot(w) for v in joint]
    umin, umax, wmin, wmax = min(pu), max(pu), min(pw), max(pw)
    stats = {}
    for side, tree, mats, d in (('child', ct, cm, n), ('parent', pt, pm, -n)):
        cnt = {'struct': 0, 'skin': 0, 'shell': 0, 'void': 0}; tot = 0
        for _ in range(500):
            a = 0.1 + 0.8 * rnd.random(); b = 0.1 + 0.8 * rnd.random()
            q = jc + u * (umin + (umax - umin) * a) + w * (wmin + (wmax - wmin) * b)
            # only inside the joint outline: a joint point within 0.25 x the extent in the plane
            if min(((v - q) - n * (v - q).dot(n)).length for v in joint[::max(1, len(joint) // 300)]) > max(0.04, 0.12 * min(umax - umin, wmax - wmin)):
                continue
            o = q - d * 0.4
            cnt[classify(tree, mats, o, d)] += 1; tot += 1
        if tot == 0:
            stats[side] = dict(rays=0)
            continue
        fr = {k: round(v / tot, 3) for k, v in cnt.items()}
        fr['rays'] = tot
        fr['pass'] = fr['struct'] >= 0.30 and fr['shell'] + fr['void'] <= 0.50
        stats[side] = fr
    res['faces'].append(dict(child_part=c.name, parent_part=p.name, n=[round(x, 3) for x in n], centre=[round(x, 3) for x in jc], joint_pts=len(joint),
                             extent=[round(umax - umin, 2), round(wmax - wmin, 2)], **stats))
    if RDIR:
        os.makedirs(RDIR, exist_ok=True)
        sc = bpy.context.scene
        sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
        sc.render.resolution_x, sc.render.resolution_y = 900, 700
        if sc.world is None:
            sc.world = bpy.data.worlds.new('w')
        sc.world.color = (0.55, 0.62, 0.70)
        sc.world.use_nodes = False
        if 'bf_sun' not in bpy.data.objects:
            L = bpy.data.objects.new('bf_sun', bpy.data.lights.new('bf_sun', 'SUN')); sc.collection.objects.link(L); L.data.energy = 3.0
            L.rotation_euler = (0.7, 0.2, 0.6)
        for side, show, d in (('child', own_objs(c), n), ('parent', own_objs(p), -n)):
            vis = set(x.name for x in show)
            for o in bpy.data.objects:
                if o.type == 'MESH':
                    o.hide_render = o.name not in vis
            cam = bpy.data.objects.get('bf_cam')
            if cam is None:
                cam = bpy.data.objects.new('bf_cam', bpy.data.cameras.new('bf_cam')); sc.collection.objects.link(cam)
            ext = max(umax - umin, wmax - wmin, 0.5)
            cam.data.lens = 35; cam.data.clip_start = 0.02
            off = (u * 0.35 + w * 0.25).normalized()
            cam.location = jc - d * (ext * 1.6 + 0.4) + off * ext * 0.5
            cam.rotation_euler = (jc - cam.location).to_track_quat('-Z', 'Z').to_euler()
            sun = bpy.data.objects['bf_sun']; sun.data.energy = 4.0
            sun.rotation_euler = (jc - cam.location + V((0.3, 0.2, -0.4))).to_track_quat('-Z', 'Z').to_euler()   # light along the view
            sc.camera = cam
            sc.render.filepath = os.path.join(RDIR, f'{TAG}_{base(c.name)}_{side}.png')
            bpy.ops.render.render(write_still=True)
        for o in bpy.data.objects:
            if o.type == 'MESH':
                o.hide_render = '_hullsrc' in o.name
    print('[breakfaces]', c.name, '<-', p.name, {k: stats[k] for k in stats})
fails = [(f['child_part'], s_) for f in res['faces'] for s_ in ('child', 'parent') if isinstance(f.get(s_), dict) and f[s_].get('rays') and not f[s_].get('pass')]
res['fails'] = fails; res['pass'] = not fails
if OUT:
    json.dump(res, open(OUT, 'w'), indent=1)
print('[breakfaces] faces', len(res['faces']), 'fails', len(fails), fails)
