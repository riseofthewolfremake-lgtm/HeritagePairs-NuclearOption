"""Measure the War Thunder Nimrod reference (REFERENCE ONLY: nothing of it is written to the repo except the
numbers printed here). Imports the OBJ, converts WT axes (x left, y up, z fwd) to ours (Blender: x right, y fwd,
z up) and ray-casts profiles: fuselage top/bottom/half-width per station, wing and tail planforms.

  blender --background --factory-startup --python blender/nimrod/measure_wt.py -- --ref <nimrod_mk1.obj> --out <json>
"""
import bpy, sys, json, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
argv = sys.argv[sys.argv.index('--') + 1:]
ref = argv[argv.index('--ref') + 1]; out = argv[argv.index('--out') + 1]
objs = {}; cur = None; verts = []
for l in open(ref):
    if l.startswith('o '): cur = l[2:].strip().split('#')[-1].rsplit('_', 1)[0]; objs.setdefault(cur, [])
    elif l.startswith('v '):
        x, y, z = map(float, l.split()[1:4]); verts.append((-x, z, y))
    elif l.startswith('f '):
        objs[cur].append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
def bvh(names):
    used = sorted({i for n in names for f in objs[n] for i in f}); rm = {o: k for k, o in enumerate(used)}
    return BVHTree.FromPolygons([verts[i] for i in used], [[rm[i] for i in f] for n in names for f in objs[n]])
res = {'objects': list(objs)}
fus = bvh(['fuse']); allb = bvh(list(objs))
def hit(tree, o, d):
    h = tree.ray_cast(Vector(o), Vector(d), 20.0)
    return h[0]
prof = []
for k in range(0, 61):
    y = 2.9 - k * 0.13
    top = hit(fus, (0, y, 5), (0, 0, -1)); bot = hit(fus, (0, y, -5), (0, 0, 1))
    if top is None: continue
    zc = (top.z + bot.z) / 2
    side = hit(fus, (5, y, zc), (-1, 0, 0))
    hw = side.x if side else None
    # max half width over heights
    mw = 0.0
    for j in range(12):
        z = bot.z + (top.z - bot.z) * (j + 0.5) / 12
        s = hit(fus, (5, y, z), (-1, 0, 0))
        if s: mw = max(mw, s.x)
    prof.append(dict(y=round(y, 3), top=round(top.z, 3), bot=round(bot.z, 3), hw_mid=round(hw, 3) if hw else None, hw_max=round(mw, 3)))
res['fuselage'] = prof
def planform(names, zlo, zhi):
    t = bvh(names); rows = []
    for k in range(0, 54):
        x = 0.05 + k * 0.1
        le = te = None
        for j in range(0, 200):
            y = 3.0 - j * 0.04
            h = t.ray_cast(Vector((x, y, zhi)), Vector((0, 0, -1)), zhi - zlo)
            if h[0] is not None and zlo <= h[0].z <= zhi:
                le = y if le is None else le; te = y
        if le is not None: rows.append(dict(x=round(x, 2), le=round(le, 3), te=round(te, 3)))
    return rows
res['upper_wing'] = planform(['wing_l', 'wing_r', 'aileron_l', 'aileron_r'], 0.5, 1.5)
res['lower_wing'] = planform(['wing_l', 'wing_r'], -0.7, -0.15)
res['tailplane'] = planform(['tail', 'elevator0', 'elevator1'], 0.0, 0.45)
fin = []
tt = bvh(['tail', 'rudder'])
for k in range(0, 24):
    z = -0.5 + k * 0.08
    le = te = None
    for j in range(0, 120):
        y = -2.0 - j * 0.03
        h = tt.ray_cast(Vector((0.6, y, z)), Vector((-1, 0, 0)), 1.2)
        if h[0] is not None: le = y if le is None else le; te = y
    if le is not None: fin.append(dict(z=round(z, 3), le=round(le, 3), te=round(te, 3)))
res['fin'] = fin
def bb(names):
    vs = [verts[i] for n in names for f in objs[n] for i in f]
    return [round(min(v[i] for v in vs), 3) for i in range(3)], [round(max(v[i] for v in vs), 3) for i in range(3)]
res['bbox'] = {n: bb([n]) for n in objs if objs[n]}
res['bbox_all'] = bb([n for n in objs if objs[n]])
json.dump(res, open(out, 'w'), indent=1)
print('[measure] wrote', out)
