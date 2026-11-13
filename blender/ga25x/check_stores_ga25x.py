"""Clearance check of the 4-per-wing pylon layout with proxy store boxes (visual pass, 2026-10-31).

  blender --background <ga25x.blend> --python blender/ga25x/check_stores_ga25x.py -- <out.json> [<render.png>]

Store proxies are the axis-aligned bounding boxes of the stock mount prefabs in their mount frame (Unity, metres),
measured read-only from the user's AssetRipper export with blender/v2/study/stock.py (tree + mesh bboxes; rolled
missiles of the triple racks use their rotated mesh boxes, so the boxes are conservative). Only these numbers are kept;
no game geometry is copied. Unity mount frame -> Blender: x -> x, y (up) -> z, z (forward) -> y.

Checks (all must be clear):
  1. every option on every pylon vs the airframe: fuselage, nacelles, wings and other pylons, gear struts / wheels /
     doors as posed in the file (extended / open), flaps and ailerons swung to +-45 / +-30 deg, bomb doors swung +-92 deg,
     the prop disc (cylinder R 1.95 m, 0.5 m deep at the prop plane);
  2. every option pair on neighbouring pylons (root-inner are far apart; inner-mid, mid-outer) does not overlap, with the
     lateral gap reported.
"""
import bpy, bmesh, sys, os, json, math, itertools
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:]
out_json = os.path.abspath(argv[0])
render = os.path.abspath(argv[1]) if len(argv) > 1 else None

# mount bboxes, Unity mount frame (min xyz, max xyz); source: stock.py tree/mesh on the user's export (2026-10-31)
MOUNTS = {
    'AGM_heavy_single':      ('AGM-68',       (-0.247, -0.556, -1.160), (0.247, 0.021, 1.311)),
    'AGM1_triple':           ('AGM-48 x3',    (-0.391, -0.541, -0.775), (0.391, 0.002, 1.146)),
    'Rocket2_4Podx3':        ('AGR-24 x12',   (-0.415, -0.561, -1.091), (0.415, 0.052, 1.088)),
    'Rocket2_4Pod':          ('AGR-24 x4',    (-0.195, -0.491, -1.091), (0.195, 0.052, 1.088)),
    'AAM1_single':           ('MMR-S3',       (-0.176, -0.387, -1.233), (0.176, 0.035, 1.638)),
    'bomb_250_glide_single': ('PAB-250LR',    (-0.142, -0.453, -1.212), (0.142, 0.046, 1.054)),
}
OPTIONS = {   # proposed per-pylon option sets (docs/ga25x_visual_pass_generator_changes.md)
    'root':  ['AGM_heavy_single', 'AGM1_triple', 'Rocket2_4Podx3', 'Rocket2_4Pod', 'AAM1_single', 'bomb_250_glide_single'],
    'inner': ['AGM_heavy_single', 'AGM1_triple', 'Rocket2_4Podx3', 'bomb_250_glide_single'],
    'mid':   ['AGM_heavy_single', 'Rocket2_4Pod', 'AAM1_single', 'bomb_250_glide_single'],
    'outer': ['AGM1_triple', 'Rocket2_4Pod', 'AAM1_single'],
}
WORST = {'root': 'Rocket2_4Podx3', 'inner': 'Rocket2_4Podx3', 'mid': 'AGM_heavy_single', 'outer': 'AGM1_triple'}
O = bpy.data.objects
dg = bpy.context.evaluated_depsgraph_get()


VERTS = {}      # id(bvh) -> world vertices (containment test: a small obstacle fully inside a store box has no face crossing)


def world_bvh(o, extra=Matrix.Identity(4)):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(extra @ o.matrix_world)
    t = BVHTree.FromBMesh(bm)
    VERTS[id(t)] = [v.co.copy() for v in bm.verts]
    bm.free()
    return t


def hits(box_tree, mn, mx, t):
    if box_tree.overlap(t):
        return True
    return any(mn[0] < p.x < mx[0] and mn[1] < p.y < mx[1] and mn[2] < p.z < mx[2] for p in VERTS.get(id(t), ()))


def box_bvh(mn, mx):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((mn[0] + mx[0]) / 2 + v.co.x * (mx[0] - mn[0]), (mn[1] + mx[1]) / 2 + v.co.y * (mx[1] - mn[1]),
                       (mn[2] + mx[2]) / 2 + v.co.z * (mx[2] - mn[2])))
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def cyl_bvh(c, axis, r, depth, N=48):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=N, radius1=r, radius2=r, depth=depth)
    rot = Vector((0, 0, 1)).rotation_difference(axis).to_matrix().to_4x4()
    bm.transform(Matrix.Translation(c) @ rot)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def store_box(hp, key):
    _, a, b = MOUNTS[key]
    p = O[hp].matrix_world.translation
    mn = (p.x + a[0], p.y + a[2], p.z + a[1])
    mx = (p.x + b[0], p.y + b[2], p.z + b[1])
    return mn, mx


def swung(o, deg):
    """matrix that rotates object o about its own local X axis through its origin (hinge) by deg."""
    M = o.matrix_world
    piv = M.translation
    ax = (M.to_3x3() @ Vector((1, 0, 0))).normalized()
    return Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-piv)


def hinge_swung(o, axis, deg):
    piv = o.matrix_world.translation
    return Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg), 4, Vector(axis).normalized()) @ Matrix.Translation(-piv)


parts_info = {}
pt = os.path.join(os.path.dirname(bpy.data.filepath), 'ga25x_parts.json')
if os.path.exists(pt):
    parts_info = {r['name']: r.get('info', {}) for r in json.load(open(pt))}

obst = []          # (label, bvh)
for o in O:
    if o.type != 'MESH' or not o.users_collection or o.users_collection[0].name != 'GA25X' or o.hide_render:
        continue
    n = o.name
    if n.startswith(('prop_', 'propdisc', 'canopy', 'cockpit', 'mfd_', 'stick_', 'quadrant', 'gunsight', 'hatch_cockpit')):
        continue
    if n.startswith(('flap_', 'aileron_')):
        lim = 45 if n.startswith('flap_') else 30
        for d in (-lim, lim):
            obst.append((f'{n}@{d:+d}', world_bvh(o, swung(o, d))))
        obst.append((n, world_bvh(o)))
    elif n.startswith('bomb_door'):
        ax = parts_info.get(n, {}).get('hinge_axis', (0, 1, 0))
        for d in (-92, 92):
            obst.append((f'{n}@{d:+d}', world_bvh(o, hinge_swung(o, ax, d))))
    else:
        obst.append((n, world_bvh(o)))
for L, s in (('L', -1), ('R', 1)):
    c = O[f'prop_disc_{L}'].matrix_world.translation
    obst.append((f'prop_disc_{L}', cyl_bvh(c, Vector((0, 1, 0)), 1.95, 0.5)))

res = dict(options=OPTIONS, mounts={k: dict(label=v[0], min=v[1], max=v[2]) for k, v in MOUNTS.items()}, pylons={}, clashes=[],
           pairs=[], ok=True)
for L in 'LR':
    for key in OPTIONS:
        hp = f'hp_{key}_{L}'
        res['pylons'][hp] = [round(v, 3) for v in O[hp].matrix_world.translation]
        for m in OPTIONS[key]:
            mn, mx = store_box(hp, m)
            b = box_bvh(mn, mx)
            for lab, t in obst:
                if lab == f'pylon_{key}_{L}':
                    continue
                if hits(b, mn, mx, t):
                    res['clashes'].append(dict(pylon=hp, store=m, obstacle=lab))
    for a, bk in (('root', 'inner'), ('inner', 'mid'), ('mid', 'outer')):
        for ma, mb_ in itertools.product(OPTIONS[a], OPTIONS[bk]):
            A, B = store_box(f'hp_{a}_{L}', ma), store_box(f'hp_{bk}_{L}', mb_)
            gap = max(B[0][0] - A[1][0], A[0][0] - B[1][0])
            if L == 'R':
                res['pairs'].append(dict(pair=f'{a}-{bk}', a=ma, b=mb_, lateral_gap_m=round(gap, 3)))
            if gap <= 0:
                res['clashes'].append(dict(pylon=f'{a}-{bk}_{L}', store=f'{ma}+{mb_}', obstacle='neighbour store'))
# positive control: a store box straddling the left gear wheel and a box inside the left prop disc must both be flagged
w = O['gear_main_L_wheel'].matrix_world.translation
ctl = box_bvh((w.x - 0.2, w.y - 0.3, w.z - 0.2), (w.x + 0.2, w.y + 0.3, w.z + 0.2))
pdc = O['prop_disc_L'].matrix_world.translation
ctl2 = box_bvh((pdc.x + 1.0, pdc.y - 0.9, pdc.z - 0.1), (pdc.x + 1.3, pdc.y - 0.1, pdc.z + 0.1))   # crosses the disc's aft face
res['selftest_detects_overlap'] = bool(any(ctl.overlap(t) for lab, t in obst if lab == 'gear_main_L_wheel') and
                                       any(ctl2.overlap(t) for lab, t in obst if lab == 'prop_disc_L'))
res['ok'] = not res['clashes'] and res['selftest_detects_overlap']
res['min_neighbour_gap_m'] = min(p['lateral_gap_m'] for p in res['pairs'])
res['obstacles_checked'] = len(obst)
json.dump(res, open(out_json, 'w'), indent=1)
print('[stores] clashes', len(res['clashes']), res['clashes'][:10], 'min gap', res['min_neighbour_gap_m'])

if render:
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light, sh.color_type, sh.show_cavity = 'STUDIO', 'MATERIAL', True
    sh.show_backface_culling = True
    sh.background_type, sh.background_color = 'VIEWPORT', (0.55, 0.6, 0.65)
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1400, 900, 70
    for o in O:
        if o.users_collection and o.users_collection[0].name == 'GA25X_extras':
            o.hide_render = True
    pm = bpy.data.materials.new('proxy')
    pm.diffuse_color = (0.75, 0.35, 0.10, 1.0)
    for L in 'LR':
        for key, m in WORST.items():
            mn, mx = store_box(f'hp_{key}_{L}', m)
            bpy.ops.mesh.primitive_cube_add(size=1, location=[(a + b) / 2 for a, b in zip(mn, mx)])
            ob = bpy.context.active_object
            ob.scale = [b - a for a, b in zip(mn, mx)]
            ob.data.materials.append(pm)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    C = O['GA25X_root'].matrix_world.translation
    for nm, loc, tgt, lens in (('pylons_loaded', C + Vector((-11, 6, -3.5)), C + Vector((-3.6, 0.2, -0.6)), 34),
                               ('pylons_front', C + Vector((-2.0, 22, -1.2)), C + Vector((-3.6, 0.0, -0.2)), 50)):
        cam.location = loc
        cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        scene.render.filepath = os.path.join(os.path.dirname(render), nm + '.png')
        bpy.ops.render.render(write_still=True)
