"""B-25H cockpit performance pass (2026-11-01): game budgets for the fal 3D props. No new art: each prop's existing fal GLB
(<name>_remesh.glb, or <name>_dec.glb where the fal remesh could not run) is welded (merge by distance, UVs kept per loop) and
decimated (collapse, UVs kept) to its triangle budget, with its own baked texture; output props_gen/opt/<name>.glb, which
cockpit_kit.glb_path prefers.

  blender --background --factory-startup --python blender/v2/props/optimize_props.py
"""
import bpy, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROPS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'assets', 'model_v2', 'src', 'props_gen'))
OUT = os.path.join(PROPS, 'opt')
# triangle budgets (the coordinator's: yoke / column <= 1.5k, seat <= 2k, pedals <= 1k for the pair, loom / boot / footrest
# <= 1k each; levers and the trim wheel small)
BUDGET = dict(yoke=1400, column=1400, seat=1900, pedal=480, loom=900, boot=900, footrest=900,
              throttle=500, proplever=450, mixture=450, trimwheel=1300)


def src(name):
    for suf in ('_remesh.glb', '_dec.glb'):
        p = os.path.join(PROPS, name + suf)
        if os.path.exists(p):
            return p
    raise SystemExit('no source GLB for ' + name)


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def one(name, target):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src(name))
    ms = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for o in ms:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]
    if len(ms) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    for e in [x for x in bpy.context.scene.objects if x.type != 'MESH']:
        bpy.data.objects.remove(e)
    t0, v0 = tris(o), len(o.data.vertices)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=1e-5)
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode='OBJECT')
    v1 = len(o.data.vertices)
    t1 = tris(o)
    if t1 > target:
        d = o.modifiers.new('dec', 'DECIMATE')
        d.ratio = target / t1
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier='dec')
    # drop decimation crumbs: loose parts of < 12 vertices (collapsed rivets / slivers that float free)
    import bmesh
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    seen, kill, tiny = set(), [], set()
    for v in bm.verts:
        if v.index in seen:
            continue
        isl, st = [], [v]; seen.add(v.index)
        while st:
            u = st.pop(); isl.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in seen:
                    seen.add(w.index); st.append(w)
        if len(isl) < 12:
            kill += isl
        if len(isl) <= 6:
            tiny.update(u.index for u in isl)
    if kill and len(kill) >= 0.25 * len(bm.verts):   # fragmented source: drop only the tiniest slivers (<= 6 verts)
        kill = [v for v in kill if v.index in tiny]
    # detached pieces: small loose parts (< 15 % of the vertices) farther than 0.5 % of the prop size from the rest float free
    # in the game (e.g. the trim wheel's spinner knob, 2 cm off its wheel)
    from mathutils.bvhtree import BVHTree
    kset = set(v.index for v in kill)
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    lab = {}
    isls = []
    for v in bm.verts:
        if v.index in lab:
            continue
        cur, st = [], [v]; lab[v.index] = len(isls)
        while st:
            u = st.pop(); cur.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in lab:
                    lab[w.index] = len(isls); st.append(w)
        isls.append(cur)
    co = [v.co.copy() for v in bm.verts]
    size = max((max(c[i] for c in co) - min(c[i] for c in co)) for i in range(3))
    for k, isl in enumerate(isls):
        if len(isl) >= 0.15 * len(bm.verts) or isl[0].index in kset:
            continue
        rest = [tuple(v.index for v in f.verts) for f in bm.faces if lab[f.verts[0].index] != k]
        if not rest:
            continue
        b = BVHTree.FromPolygons(co, rest)
        if min(b.find_nearest(co[u.index])[3] for u in isl) > 0.005 * size:
            kill += isl; kset.update(u.index for u in isl)
    if kill:
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bm.to_mesh(o.data); bm.free()
    print(f'[opt] {name}: removed {len(kill)} crumb verts')
    print(f'[opt] {name}: tris {t0} -> {tris(o)}, verts {v0} -> welded {v1} -> {len(o.data.vertices)}')
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, name + '.glb'), export_format='GLB', export_yup=True, export_apply=True)


names = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else list(BUDGET)
for n in names:
    one(n, BUDGET[n])
