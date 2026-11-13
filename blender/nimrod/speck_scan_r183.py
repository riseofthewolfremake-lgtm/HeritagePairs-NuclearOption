"""1.8.3 offline B: hunt the 'small dark specks' on the Mk I / FD-32 side skin near the cockpit (study + check helper).

  blender --background <blend> --python blender/nimrod/speck_scan_r183.py -- [--obj fus_center] [--json out]
Reports, for the skin object, in the box around the cockpit (y -1.6..0.1, z > 0): inward-facing faces (normal vs the section's outward
direction), sliver / tiny faces, boundary (open) edges not on the cockpit hole, non-manifold edges, duplicate (coincident) faces,
and faces of OTHER objects lying within 1.5 mm outside the skin (z-fight candidates).
"""
import bpy, bmesh, sys, json, math
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
name = argv[argv.index('--obj') + 1] if '--obj' in argv else 'fus_center'
Y0, Y1 = float(argv[argv.index('--y0') + 1]) if '--y0' in argv else -1.9, float(argv[argv.index('--y1') + 1]) if '--y1' in argv else 0.2
ob = bpy.data.objects[name]
bm = bmesh.new(); bm.from_mesh(ob.data); bm.transform(ob.matrix_world)
bm.faces.ensure_lookup_table(); bm.normal_update()
mats = [m.name if m else '' for m in ob.data.materials]
SPLITS = [float(v) for v in (argv[argv.index('--splits') + 1].split(',') if '--splits' in argv else ['0', '-1.5'])]
res = dict(inward=[], tiny=[], open=[], nonmanifold=[], dup=[], zfight=[])
def box(c):
    return Y0 < c.y < Y1 and c.z > -0.1
for f in bm.faces:
    c = f.calc_center_median()
    if not box(c) or mats[f.material_index] != 'paint':
        continue
    out = V((c.x, 0, c.z - 0.0))
    if out.length > 1e-6 and f.normal.dot(out.normalized()) < -0.2:
        res['inward'].append([round(c.x, 3), round(c.y, 3), round(c.z, 3), round(f.calc_area() * 1e6)])
    a = f.calc_area()
    if a < 2e-6:
        res['tiny'].append([round(c.x, 3), round(c.y, 3), round(c.z, 3), round(a * 1e6, 2)])
for e in bm.edges:
    c = (e.verts[0].co + e.verts[1].co) / 2
    if not box(c):
        continue
    lf = [f for f in e.link_faces if mats[f.material_index] == 'paint']
    if len(lf) == 1 and min(abs(c.y - ys) for ys in SPLITS) > 0.002:
        res['open'].append([round(c.x, 3), round(c.y, 3), round(c.z, 3)])
    elif len(lf) > 2:
        res['nonmanifold'].append([round(c.x, 3), round(c.y, 3), round(c.z, 3), len(lf)])
seen = {}
for f in bm.faces:
    if mats[f.material_index] != 'paint':
        continue
    k = tuple(sorted((round(v.co.x, 4), round(v.co.y, 4), round(v.co.z, 4)) for v in f.verts))
    if k in seen:
        c = f.calc_center_median(); res['dup'].append([round(c.x, 3), round(c.y, 3), round(c.z, 3)])
    seen[k] = 1
skin_faces = [f for f in bm.faces if mats[f.material_index] == 'paint' and box(f.calc_center_median())]
bvh = BVHTree.FromBMesh(bm)
for o in bpy.data.objects:
    if o.type != 'MESH' or o is ob or o.name.startswith(('chk_', 'cooper_')):
        continue
    b2 = bmesh.new(); b2.from_mesh(o.data); b2.transform(o.matrix_world); b2.normal_update()
    m2 = [m.name if m else '' for m in o.data.materials]
    n = 0; ex = None
    for f in b2.faces:
        c = f.calc_center_median()
        if not box(c):
            continue
        loc, nrm, idx, d = bvh.find_nearest(c)
        if loc is None or d > 0.0015:
            continue
        sd = (c - loc).dot(nrm)
        if sd > -0.0006:
            n += 1; ex = (ex or []) + [[round(c.x, 3), round(c.y, 3), round(c.z, 3), round(sd * 1000, 2), round(f.normal.dot(nrm), 2), m2[f.material_index] if f.material_index < len(m2) else '']]
    if n:
        res['zfight'].append([o.name, n, ex])
    b2.free()
summ = {k: len(v) for k, v in res.items()}
print('[speck]', name, json.dumps(summ))
for k, v in res.items():
    print('[speck]', k, v[:12])
if '--json' in argv:
    json.dump(res, open(argv[argv.index('--json') + 1], 'w'))
