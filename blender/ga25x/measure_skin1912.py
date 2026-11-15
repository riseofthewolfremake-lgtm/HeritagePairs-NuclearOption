"""1.9.12 study helper: the real fus_rear skin cross-section of the built GA-25X model (the dump the 1.9.12 panel study lacked).

  blender --background assets/model_ga25x/ga25x.blend --python blender/ga25x/measure_skin1912.py -- <out.json>

Prints, for the fus_rear OUTER paint faces on both flanks between y -6.2 and -3.9 (Blender frame: nose +Y, up +Z):
the station rows (y), the ring points per station (z, |x|), face normals, and the world boxes of everything near the flank
(flare ejectors, sensor panels, rear hatch, belly laser, stabiliser, inner flap, tail hook).
"""
import bpy, sys, json
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]
O = bpy.data.objects
fr = O['fus_rear']
me = fr.data
M = fr.matrix_world
pi = [i for i, m in enumerate(me.materials) if m.name == 'paint']
mats = [m.name for m in me.materials]
V = [M @ v.co for v in me.vertices]
N3 = M.to_3x3()
rows = {}
faces = []
for p in me.polygons:
    if p.material_index not in pi:
        continue
    c = M @ p.center
    n = (N3 @ p.normal).normalized()
    if not (-6.2 < c.y < -3.9 and abs(c.x) > 0.3 and n.x * c.x > 0):
        continue
    faces.append(dict(c=[round(a, 4) for a in c], n=[round(a, 4) for a in n], v=[[round(a, 4) for a in V[i]] for i in p.vertices]))
    if c.x > 0:
        for i in p.vertices:
            rows.setdefault(round(V[i].y, 3), set()).add((round(V[i].z, 3), round(V[i].x, 4)))
print('fus_rear materials', mats, 'world origin', tuple(round(a, 4) for a in M.translation))
for y in sorted(rows, reverse=True):
    print('station y %.3f:' % y, ' '.join('(z %.3f x %.4f)' % t for t in sorted(rows[y])))
near = {}
for o in O:
    if o.type != 'MESH' and o.type != 'EMPTY':
        continue
    w = o.matrix_world
    if o.type == 'MESH':
        pts = [w @ Vector(b) for b in o.bound_box]
        lo = [min(p[k] for p in pts) for k in range(3)]; hi = [max(p[k] for p in pts) for k in range(3)]
    else:
        lo = hi = list(w.translation)
    if hi[1] > -7.6 and lo[1] < -2.0 and o.name not in ('GA25X_root',) and not o.name.startswith(('wing_outer', 'wing_tip', 'aileron', 'prop_', 'engine', 'exhaust', 'pylon', 'hp_', 'gear_', 'flap_outer', 'nacelle', 'slimelight')):
        near[o.name] = dict(lo=[round(a, 3) for a in lo], hi=[round(a, 3) for a in hi], parent=o.parent.name if o.parent else None, type=o.type)
for k, v in sorted(near.items()):
    print('near', k, v)
json.dump(dict(rows={str(k): sorted(v) for k, v in rows.items()}, faces=faces, near=near), open(out, 'w'), indent=0)
