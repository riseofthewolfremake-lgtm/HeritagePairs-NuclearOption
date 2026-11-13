"""1.8.3 offline B: cross-sections of every mesh through planes y = const (and the x = 0 profile) -> JSON for plotting (study only).

  blender --background <model.blend> --python blender/fd32/section_r183.py -- --out <json> --y -0.5,-0.8 [--x0]
"""
import bpy, sys, json, bmesh
from mathutils import Vector as V
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[argv.index('--out') + 1]
ys = [float(v) for v in argv[argv.index('--y') + 1].split(',')]
res = {}
dg = bpy.context.evaluated_depsgraph_get()
def cut(co, no):
    segs = {}
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.name.startswith(('chk_', 'cooper_', 'wt_')):
            continue
        bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
        mats = [m.name if m else '' for m in o.data.materials]
        L = []
        for f in bm.faces:
            ds = [(v.co - co).dot(no) for v in f.verts]
            if min(ds) > 0 or max(ds) < 0:
                continue
            pts = []
            n = len(f.verts)
            for i in range(n):
                a, b = f.verts[i].co, f.verts[(i + 1) % n].co
                da, db = ds[i], ds[(i + 1) % n]
                if (da <= 0 < db) or (db <= 0 < da):
                    t = da / (da - db); p = a.lerp(b, t); pts.append([round(p.x, 4), round(p.y, 4), round(p.z, 4)])
            if len(pts) >= 2:
                L.append([pts[0], pts[1], mats[f.material_index] if f.material_index < len(mats) else ''])
        bm.free()
        if L:
            segs[o.name] = L
    return segs
for y in ys:
    res[f'y{y}'] = cut(V((0, y, 0)), V((0, 1, 0)))
if '--x0' in argv:
    res['x0'] = cut(V((0.0005, 0, 0)), V((1, 0, 0)))
json.dump(res, open(out, 'w'))
print('[sec] wrote', out)
