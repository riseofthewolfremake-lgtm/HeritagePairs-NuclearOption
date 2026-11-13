"""Mechanical connectivity check for the articulated v3 objects (offline, on the .blend).

  blender --background assets/model_v2/b25h_v2.blend --python blender/v2/check_v3_mechanics.py -- [--json out.json]

For every driven pair (child, parent) the child is rotated through its whole range about its own driver axis
(ControlSurface / Turret / Canopy conventions, see b25h_v3.py) and the two meshes must stay in contact
(triangles intersect, or the closest vertex gap <= TOL). Also checks muzzle offsets against the stock M2 layout,
hardpoints at pylon bottoms, and that gauge needles stay on their dial.
Exit code 1 if any check fails.
"""
import bpy, bmesh, sys, json, math
from mathutils import Vector, Quaternion, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
jout = argv[argv.index('--json') + 1] if '--json' in argv else None
O = bpy.data.objects
TOL = 0.003
res = {'checks': [], 'fail': 0}


def check(name, ok, detail=''):
    res['checks'].append(dict(name=name, ok=bool(ok), detail=detail))
    if not ok:
        res['fail'] += 1
    print(('PASS ' if ok else 'FAIL ') + name + (' : ' + str(detail) if detail else ''))


def bvh_world(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(o.matrix_world)
    bm.verts.ensure_lookup_table()
    t = BVHTree.FromBMesh(bm)
    vs = [v.co.copy() for v in bm.verts]
    bm.free()
    return t, vs


def gap(a, b):
    ta, va = bvh_world(O[a])
    tb, vb = bvh_world(O[b])
    if ta.overlap(tb):
        return 0.0
    best = 1e9
    for v in va[::max(1, len(va) // 1500)]:
        r = tb.find_nearest(v)
        if r[0] is not None:
            best = min(best, r[3])
    for v in vb[::max(1, len(vb) // 1500)]:
        r = ta.find_nearest(v)
        if r[0] is not None:
            best = min(best, r[3])
    return best


BASE = {}


def set_rot(name, axis_local, deg):
    o = O[name]
    if name not in BASE:
        BASE[name] = o.matrix_basis.copy()
    R = Quaternion(Vector(axis_local), math.radians(deg)).to_matrix().to_4x4()
    o.matrix_basis = BASE[name] @ R
    bpy.context.view_layer.update()


def reset(*names):
    for n in names:
        if n in BASE:
            O[n].matrix_basis = BASE[n].copy()
    bpy.context.view_layer.update()


def sweep(child, parent, axis, angles, extra=()):
    worst = 0.0
    for a in angles:
        set_rot(child, axis, a)
        g = gap(child, parent)
        worst = max(worst, g)
    reset(child)
    return worst


# --- cockpit controls (Blender local axes: column/yoke/pedals local X is the driver axis)
for L in 'LR':
    c, y, p = f'cockpit_column_{L}', f'cockpit_yoke_{L}', f'cockpit_rudder_pedals_{L}'
    if c not in O:
        continue
    w = sweep(c, 'cockpit_interior', (1, 0, 0), (-12, -6, 0, 6, 12))
    check(f'{c} stays on its floor pin through pitch +-12 deg', w <= TOL, f'worst gap {w * 1000:.1f} mm')
    worst = 0.0
    for cp in (-12, 0, 12):
        set_rot(c, (1, 0, 0), cp)
        worst = max(worst, sweep(y, c, (1, 0, 0), (-45, -20, 0, 20, 45)))
    reset(c)
    check(f'{y} stays on the column hub through roll +-45 at pitch -12/0/12', worst <= TOL, f'worst gap {worst * 1000:.1f} mm')
    w = sweep(p, 'cockpit_interior', (1, 0, 0), (-15, 0, 15))
    check(f'{p} stays in its floor socket through yaw +-15', w <= TOL, f'worst gap {w * 1000:.1f} mm')

# --- turrets: az about local Z (Blender) = Unity +Y, el about local X
w = sweep('turret_dorsal', 'fus_forward', (0, 0, 1), range(0, 360, 45))
check('turret_dorsal (az) rests on the turret ring for all azimuths', w <= TOL, f'worst gap {w * 1000:.1f} mm')
worst = 0.0
for az in (0, 90, 200):
    set_rot('turret_dorsal', (0, 0, 1), az)
    worst = max(worst, sweep('turret_dorsal_guns', 'turret_dorsal', (1, 0, 0), (-5, 20, 50, 85)))
reset('turret_dorsal')
check('turret_dorsal_guns (el) stays in the side plates for el -5..85', worst <= TOL, f'worst gap {worst * 1000:.1f} mm')
w = sweep('tail_turret_az', 'fus_tail', (0, 0, 1), (-20, 0, 20))
check('tail_turret_az stays on its pedestal for az +-20', w <= TOL, f'worst gap {w * 1000:.1f} mm')
w = sweep('tail_guns', 'tail_turret_az', (1, 0, 0), (-25, 0, 25))
check('tail_guns (el) stays in the yoke for el +-25', w <= TOL, f'worst gap {w * 1000:.1f} mm')
for L in 'LR':
    w = sweep(f'waist_gun_{L}_az', f'hatch_waist_{L}', (0, 0, 1), (-40, 0, 40))
    check(f'waist_gun_{L}_az ball stays in the hatch socket for az +-40', w <= TOL, f'worst gap {w * 1000:.1f} mm')
    w = sweep(f'waist_gun_{L}', f'waist_gun_{L}_az', (1, 0, 0), (-30, 0, 40))
    check(f'waist_gun_{L} (el) stays on the ball for el -30..40', w <= TOL, f'worst gap {w * 1000:.1f} mm')
for g, par in (('gun_turret_L', 'turret_dorsal_guns'), ('gun_turret_R', 'turret_dorsal_guns'), ('gun_tail_L', 'tail_guns'),
               ('gun_tail_R', 'tail_guns'), ('gun_waist_L', 'waist_gun_L'), ('gun_waist_R', 'waist_gun_R')):
    w = gap(g, par)
    check(f'{g} attached to {par}', w <= TOL, f'gap {w * 1000:.1f} mm')
    m = O['muzzle' + g[3:]]
    loc = O[g].matrix_world.inverted() @ m.matrix_world.translation
    check(f'{m.name} at the stock M2 muzzle offset (0, 1.200, 0.046) in the gun frame', (loc - Vector((0, 1.2, 0.046))).length < 1e-3,
          str(tuple(round(v, 4) for v in loc)))

# --- hatches: the hinge edge stays on the opening at the open angle
for h in ('hatch_cockpit_top', 'hatch_entry_fwd', 'hatch_entry_rear', 'hatch_waist_L', 'hatch_waist_R'):
    info = json.loads(O[h]['b25_info'])
    par = O[h + '_hinge'].parent.name
    g0 = gap(h, par if h != 'hatch_cockpit_top' else 'canopy_glass')
    set_rot(h, (1, 0, 0), info['open_deg_blender'])
    g1 = gap(h, par if h != 'hatch_cockpit_top' else 'canopy_glass')
    c_open = sum((O[h].matrix_world @ v.co for v in O[h].data.vertices), Vector()) / len(O[h].data.vertices)
    reset(h)
    c_shut = sum((O[h].matrix_world @ v.co for v in O[h].data.vertices), Vector()) / len(O[h].data.vertices)
    d = c_open - c_shut
    check(f'{h} closed sits in its opening and keeps its hinge edge when open', g0 <= TOL and g1 <= 0.03,
          f'closed gap {g0 * 1000:.1f} mm, open gap {g1 * 1000:.1f} mm, centroid moves {tuple(round(v, 2) for v in d)}')
    want = {'hatch_cockpit_top': d.z > 0.15, 'hatch_entry_fwd': d.z < -0.1, 'hatch_entry_rear': d.z < -0.1,
            'hatch_waist_L': d.x < -0.1, 'hatch_waist_R': d.x > 0.1}[h]
    check(f'{h} opens the right way', want, str(tuple(round(v, 3) for v in d)))

# --- hardpoints at pylon bottoms
for o in [o for o in O if o.name.startswith('pylon_')]:
    hp = 'hp_' + o.name[6:]
    zmin = min((o.matrix_world @ v.co).z for v in o.data.vertices)
    zmax = max((o.matrix_world @ v.co).z for v in o.data.vertices)
    hpz = O[hp].matrix_world.translation.z
    wing = O[o.parent.name]
    tw, _ = bvh_world(wing)
    tp, _ = bvh_world(o)
    check(f'{hp} on the bottom face of {o.name}; pylon reaches into the wing skin',
          abs(hpz - zmin) < 1e-4 and tw.overlap(tp), f'hp z {hpz:.3f}, pylon z {zmin:.3f}..{zmax:.3f}')

# --- gauge needles stay on their dial at any angle
for o in [o for o in O if o.name.startswith('gauge_') and o.type == 'MESH']:
    w = sweep(o.name, 'cockpit_gauges', (1, 0, 0), (0, 90, 180, 270))
    check(f'{o.name} over its dial face at all angles (<= 6 mm)', w <= 0.006, f'worst gap {w * 1000:.1f} mm')

print('SUMMARY', json.dumps({'fail': res['fail'], 'checks': len(res['checks'])}))
if jout:
    with open(jout, 'w') as f:
        json.dump(res, f, indent=1)
sys.exit(1 if res['fail'] else 0)
