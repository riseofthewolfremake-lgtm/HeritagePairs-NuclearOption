"""1.8.3 offline B: vertices of other objects that poke through (or sit within 1 mm under) a skin object = the 'dark specks' on the
side skin (inner parts showing through the paint). Study + check helper.

  blender --background <blend> --python blender/nimrod/poke_scan_r183.py -- --skin fus_center[,fus_engine,...] [--margin 0.001] [--json out]
A vertex counts when its nearest skin point is within 12 mm, on a skin face ('paint'), and it lies less than `margin` inside the skin
(signed distance along that face's outward normal > -margin). Children that are meant to sit on the skin (strips, fittings, the
leather roll, canopy rails, glass, frames, struts) are skipped by name.
"""
import bpy, bmesh, sys, json
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
skins = argv[argv.index('--skin') + 1].split(',') if '--skin' in argv else ['fus_center']
margin = float(argv[argv.index('--margin') + 1]) if '--margin' in argv else 0.001
SKIP = ('cockpit_coaming', 'slimelight', 'canopy', 'windscreen', 'cabane', 'strut', 'wire', 'rigging', 'fus_', 'wing_', 'gear_', 'hook',
        'tailhook', 'prop', 'stab', 'fin', 'rudder', 'elevator', 'aileron', 'flaperon', 'pylon', 'chk_', 'cooper_', 'sight', 'exhaust',
        'r183_', 'spine', 'coaming_', 'sensor', 'radiator', 'oil_', 'louvre', 'gun', 'muzzle', 'flash', 'hp_', 'nav', 'lamp', 'pitot', 'lifting')
out = {}
for sn in skins:
    so = bpy.data.objects.get(sn)
    if so is None:
        continue
    bm = bmesh.new(); bm.from_mesh(so.data); bm.transform(so.matrix_world); bm.normal_update()
    mats = [m.name if m else '' for m in so.data.materials]
    keep = [f for f in bm.faces if mats[f.material_index] != 'paint']
    bmesh.ops.delete(bm, geom=keep, context='FACES')
    bm.faces.ensure_lookup_table()
    bvh = BVHTree.FromBMesh(bm)
    for o in bpy.data.objects:
        if o.type != 'MESH' or o is so or o.name.startswith(SKIP) or o.hide_render:
            continue
        M = o.matrix_world
        hits = []
        for v in o.data.vertices:
            p = M @ v.co
            loc, nrm, idx, d = bvh.find_nearest(p, 0.012)
            if loc is None:
                continue
            sd = (p - loc).dot(nrm)
            if sd > -margin:
                hits.append([round(p.x, 3), round(p.y, 3), round(p.z, 3), round(sd * 1000, 2)])
        if hits:
            out.setdefault(sn, {})[o.name] = hits
    bm.free()
for sn, d in out.items():
    for o, h in sorted(d.items(), key=lambda kv: -len(kv[1])):
        print('[poke]', sn, o, len(h), 'max out %.2f mm' % max(x[3] for x in h), h[:5])
print('[poke] total', sum(len(h) for d in out.values() for h in d.values()))
if '--json' in argv:
    json.dump(out, open(argv[argv.index('--json') + 1], 'w'))
