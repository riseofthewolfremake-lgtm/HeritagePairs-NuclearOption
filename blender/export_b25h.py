"""Export the B-25H scene to the runtime JSON format (Unity space).

  blender --background assets/model/b25h.blend --python blender/export_b25h.py -- \
      --out assets/model/b25h_model.json --parts assets/model/b25h_parts.md

Blender: right-handed, +Y forward, +Z up, +X right.
Unity:   left-handed,  +Z forward, +Y up, +X right.
Mapping  unity = (x_b, z_b, y_b)  (a mirror, det = -1), so
  * positions / normals / axis directions: swap y and z
  * triangle winding: reversed (swap 2nd and 3rd index)
  * rotations: R_u = M R_b M  ->  quaternion (w,x,y,z)_b  ->  (x, z, y, -w) in Unity (x,y,z,w) order
This file verifies the quaternion rule numerically before exporting.
"""
import bpy, sys, os, json, math, random
from mathutils import Vector, Quaternion, Matrix

REQUIRED = ['B25H_root', 'fuselage', 'nose_guns', 'cannon', 'canopy_glass', 'turret_dorsal', 'turret_dorsal_guns',
            'tail_guns', 'waist_blister_L', 'waist_blister_R', 'wing_L', 'wing_R', 'aileron_L', 'aileron_R', 'flap_L',
            'flap_R', 'nacelle_L', 'nacelle_R', 'cowling_L', 'cowling_R', 'prop_hub_L', 'prop_hub_R',
            'prop_L_blade1', 'prop_L_blade2', 'prop_L_blade3', 'prop_R_blade1', 'prop_R_blade2', 'prop_R_blade3',
            'stab_h', 'elevator_L', 'elevator_R', 'fin_L', 'fin_R', 'rudder_L', 'rudder_R', 'gear_nose_strut',
            'gear_nose_wheel', 'gear_main_L_strut', 'gear_main_L_wheel', 'gear_main_R_strut', 'gear_main_R_wheel',
            'bomb_door_L', 'bomb_door_R']

M = Matrix(((1, 0, 0), (0, 0, 1), (0, 1, 0)))


def v_u(v):
    return [v[0], v[2], v[1]]


def q_u(q):
    """Blender quaternion -> Unity [x, y, z, w]"""
    q = q.normalized()
    return [q.x, q.z, q.y, -q.w]


def quat_xyzw_to_matrix(x, y, z, w):
    # standard formula -- Unity uses the same component algebra (handedness only affects how it looks)
    return Matrix(((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
                   (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
                   (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))))


def verify_quaternion_rule():
    rnd = random.Random(7)
    worst = 0.0
    for _ in range(200):
        q = Quaternion((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))).normalized()
        v = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        vb = q @ v                                  # rotate in Blender
        ux, uy, uz, uw = q_u(q)
        vu = quat_xyzw_to_matrix(ux, uy, uz, uw) @ (M @ v)   # rotate the converted vector in Unity
        worst = max(worst, (M @ vb - vu).length)
    assert worst < 1e-6, f'quaternion rule failed: {worst}'
    return worst


def r5(x):
    v = round(x, 5)
    return 0.0 if v == 0 else v


def describe_motion(axis_u, centroid_u):
    """what a small positive Unity rotation about axis_u does to the part's centroid (left-hand rule)"""
    a = Vector(axis_u)
    c = Vector(centroid_u)
    d = a.cross(c)   # component formula identical in Unity
    if d.length < 1e-6:
        return 'spins in place'
    names = {0: ('right(+X)', 'left(-X)'), 1: ('up(+Y)', 'down(-Y)'), 2: ('forward(+Z)', 'aft(-Z)')}
    k = max(range(3), key=lambda i: abs(d[i]))
    return 'centroid moves ' + (names[k][0] if d[k] > 0 else names[k][1])


def mesh_payload(ob, dg):
    ob_eval = ob.evaluated_get(dg)
    me = ob_eval.to_mesh()
    me.calc_loop_triangles()
    cn = me.corner_normals
    uvl = me.uv_layers.active.data if me.uv_layers.active else None
    verts, norms, uvs = [], [], []
    keymap = {}
    subs = {}
    mats = [s.material.name if s.material else 'default' for s in ob.material_slots] or ['default']
    for tri in me.loop_triangles:
        mi = min(tri.material_index, len(mats) - 1)
        idxs = []
        for li in tri.loops:
            vi = me.loops[li].vertex_index
            n = cn[li].vector
            uv = uvl[li].uv if uvl else (0.0, 0.0)
            key = (vi, round(n.x, 4), round(n.y, 4), round(n.z, 4), round(uv[0], 5), round(uv[1], 5))
            j = keymap.get(key)
            if j is None:
                j = len(verts) // 3
                keymap[key] = j
                co = me.vertices[vi].co
                verts += [r5(c) for c in v_u(co)]
                nn = Vector(v_u(n)).normalized()
                norms += [r5(c) for c in nn]
                uvs += [r5(uv[0]), r5(uv[1])]
            idxs.append(j)
        a, b, c = idxs
        subs.setdefault(mats[mi], []).extend([a, c, b])      # reversed winding for Unity
    ob_eval.to_mesh_clear()
    return {'vertices': verts, 'normals': norms, 'uvs': uvs,
            'submeshes': [{'material': m, 'triangles': t} for m, t in subs.items()]}


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[argv.index('--out') + 1]
    parts = argv[argv.index('--parts') + 1] if '--parts' in argv else None
    err = verify_quaternion_rule()
    print(f'[export] quaternion rule verified on 200 random rotations, max error {err:.2e}')

    dg = bpy.context.evaluated_depsgraph_get()
    root = bpy.data.objects['B25H_root']
    # order: parents before children
    order = []

    def walk(o):
        order.append(o)
        for ch in sorted(o.children, key=lambda c: c.name):
            walk(ch)
    walk(root)
    missing = [n for n in REQUIRED if n not in bpy.data.objects]
    assert not missing, f'missing objects: {missing}'

    objs, rows = [], []
    total_tris = 0
    for ob in order:
        if ob.type not in ('MESH', 'EMPTY'):
            continue
        par = ob.parent
        mw = ob.matrix_world.copy()
        local = (par.matrix_world.inverted() @ mw) if par else mw
        loc, rot, sca = local.decompose()
        assert max(abs(s - 1) for s in sca) < 1e-5, f'{ob.name} has scale {sca}; apply scale first'
        entry = {'name': ob.name, 'parent': par.name if par else None,
                 'position': [r5(c) for c in v_u(loc)],
                 'rotation': [r5(c) for c in q_u(rot)],
                 'scale': [1.0, 1.0, 1.0],
                 'mesh': None}
        tris = 0
        centroid_u = None
        if ob.type == 'MESH':
            entry['mesh'] = mesh_payload(ob, dg)
            tris = sum(len(s['triangles']) for s in entry['mesh']['submeshes']) // 3
            vs = entry['mesh']['vertices']
            n = len(vs) // 3
            centroid_u = [sum(vs[0::3]) / n, sum(vs[1::3]) / n, sum(vs[2::3]) / n]
        total_tris += tris
        if 'hinge_axis' in ob:
            ax_b = Vector(ob['hinge_axis'])
            # hinge axes were stored in the object's own local frame (identical to world for unrotated parts)
            ax_u = [r5(c) for c in Vector(v_u(ax_b)).normalized()]
            entry['hingeAxis'] = ax_u
            entry['hingeKind'] = ob.get('hinge_kind', 'hinge')
            entry['positiveRotation'] = describe_motion(ax_u, centroid_u) if centroid_u else ''
        objs.append(entry)
        wpos = v_u(mw.translation)
        rows.append((ob.name, entry['parent'], wpos, tris, entry.get('hingeAxis'), entry.get('hingeKind', ''),
                     entry.get('positiveRotation', ''), [len(s['triangles']) // 3 for s in entry['mesh']['submeshes']] if entry['mesh'] else None,
                     [s['material'] for s in entry['mesh']['submeshes']] if entry['mesh'] else None))

    data = {'version': 1, 'unit': 'm', 'groundOffset': r5(root.get('ground_offset', 0.0)),
            'source': 'blender/build_b25h.py (procedural, original geometry)',
            'coordinateSystem': 'Unity: +Z forward, +Y up, +X right (left-handed); converted from Blender (+Y fwd, +Z up)',
            'objects': objs}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w') as f:
        json.dump(data, f, separators=(',', ':'))
    print(f'[export] wrote {out}  objects={len(objs)}  triangles={total_tris}  size={os.path.getsize(out) / 1e6:.2f} MB')

    if parts:
        L = ['# B-25H model parts', '',
             'Generated by `blender/export_b25h.py` from `assets/model/b25h.blend` (built by `blender/build_b25h.py`).', '',
             'Coordinates are Unity space (+Z forward, +Y up, +X right, metres), relative to `B25H_root`',
             f'(aircraft CG, 30% MAC, wing-root chord plane). Ground (wheel contact) is {data["groundOffset"]} m below the root.', '',
             'Hinge axes are unit vectors in the part\'s parent frame (no part is rotated except the propeller blades,',
             'whose axis is in their own local frame). "Positive rotation" says where a small positive rotation about',
             'that axis (Unity left-hand rule, e.g. `transform.localRotation = rest * Quaternion.AngleAxis(+deg, axis)`) moves the part\'s centroid.', '',
             f'Total triangles: **{total_tris}**', '',
             '| object | parent | pivot (world, Unity x,y,z) | tris | hinge axis (Unity) | kind | positive rotation | materials |',
             '|---|---|---|---|---|---|---|---|']
        for name, parent, wp, tris, ax, kind, pos, subt, subm in rows:
            mats = ', '.join(f'{m}:{t}' for m, t in zip(subm, subt)) if subm else '(empty)'
            axs = '({:+.3f}, {:+.3f}, {:+.3f})'.format(*ax) if ax else ''
            L.append(f'| `{name}` | {parent or "-"} | ({wp[0]:+.3f}, {wp[1]:+.3f}, {wp[2]:+.3f}) | {tris} | {axs} | {kind} | {pos} | {mats} |')
        with open(parts, 'w') as f:
            f.write('\n'.join(L) + '\n')
        print(f'[export] wrote {parts}')


main()
