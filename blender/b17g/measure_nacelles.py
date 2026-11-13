"""Measure nacelle sections (numbers only) of our model and, with --ref, of the War Thunder reference (imported in memory only).

  blender --background <b17g.blend> --python blender/b17g/measure_nacelles.py -- --out <json> [--ref <WT obj>]

Per nacelle (right side: inner x 3.10, outer x 6.575) and station y: bottom z and top z on the nacelle axis plane, and the half-width
at three heights (axis - 0.40, axis, axis + 0.25) measured from outboard and inboard. Ours: the nacelle_n + engine_n + wing meshes;
reference: its wing_r (which carries the nacelles) + the cowl-flap ('radiator') objects.
"""
import bpy, sys, os, math, json
from mathutils import Vector as V, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
OUT, REF = arg('--out'), arg('--ref')
K = 31.62 / 31.258
dg = bpy.context.evaluated_depsgraph_get()


def bvh_of(objs):
    vs, fs = [], []
    for o in objs:
        me = o.evaluated_get(dg).to_mesh()
        M = o.matrix_world; b = len(vs)
        vs += [M @ v.co for v in me.vertices]
        fs += [[b + i for i in p.vertices] for p in me.polygons]
        o.evaluated_get(dg).to_mesh_clear()
    return BVHTree.FromPolygons(vs, fs)


def first(t, o, d, L=20.0):
    h = t.ray_cast(V(o), V(d).normalized(), L)
    return h[0]


def profile(t, xa, za):
    rows = []
    y = 4.8
    while y > -2.01:
        r = dict(y=round(y, 2))
        b = first(t, (xa, y, -6), (0, 0, 1)); tp = first(t, (xa, y, 6), (0, 0, -1))
        r['bot'] = round(b.z, 3) if b else None; r['top'] = round(tp.z, 3) if tp else None
        for nm, dz in (('lo', -0.40), ('mid', 0.0), ('hi', 0.25)):
            ho = first(t, (xa + 3, y, za + dz), (-1, 0, 0), 3.0); hi = first(t, (xa - 3, y, za + dz), (1, 0, 0), 3.0)
            r['w_' + nm] = [round(xa - hi.x, 3) if hi else None, round(ho.x - xa, 3) if ho else None]
        rows.append(r); y -= 0.1
    return rows


res = {}
ours = [o for o in bpy.data.objects if o.type == 'MESH']
for kind, num, xa, za in (('inner', 3, 3.10, 0.05), ('outer', 4, 6.575, 0.30)):
    sel = [o for o in ours if o.name in (f'nacelle_{num}', f'engine_{num}') or o.name.startswith('wing_inner_R') or o.name.startswith('wing_mid_R')]
    sel = [o for o in sel if o.name.split('.')[0] in (f'nacelle_{num}', f'engine_{num}', 'wing_inner_R', 'wing_mid_R')]
    res[f'ours_{kind}'] = profile(bvh_of(sel), xa, za)
if REF:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=REF)
    ref = [o for o in bpy.data.objects if o not in before]
    M = Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Scale(K, 4)
    for o in ref:
        o.matrix_world = M @ o.matrix_world
    bpy.context.view_layer.update()
    sel = [o for o in ref if o.type == 'MESH' and ('wing_r' in o.name or 'radiator3' in o.name or 'radiator4' in o.name)]
    t = bvh_of(sel)
    for kind, xa, za in (('inner', 3.10, 0.05), ('outer', 6.575, 0.30)):
        res[f'ref_{kind}'] = profile(t, xa, za)
    # the cowl-flap rings: y range and radius about each axis
    for grp, xa, za in (('radiator3', 3.10, 0.05), ('radiator4', 6.575, 0.30)):
        pts = []
        for o in ref:
            if o.type == 'MESH' and grp in o.name:
                pts += [o.matrix_world @ v.co for v in o.data.vertices]
        if pts:
            rr = [math.hypot(p.x - xa, p.z - za) for p in pts]
            res[grp] = dict(y=[round(min(p.y for p in pts), 3), round(max(p.y for p in pts), 3)], r=[round(min(rr), 3), round(max(rr), 3)],
                            cx=round(sum(p.x for p in pts) / len(pts), 3), cz=round(sum(p.z for p in pts) / len(pts), 3), n=len(pts))
json.dump(res, open(OUT, 'w'), indent=0)
print('[measure] written', OUT)
