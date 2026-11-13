"""B-17G fal 3D props (copy of process_props_fd32.py with the B-17G paths and budgets) -> game-budget GLBs (2026-11-02 rebuild).

Source: assets/model_nimrod/src/fal/remesh/<name>_remesh.glb (fal: concept image -> tripo3d/h3.1/image-to-3d -> tripo3d/tripo/remesh,
every call in that folder's fal_manifest.jsonl). Each prop is joined, welded, its small holes filled (closed shells: no see-through
from any side), decimated to its triangle budget, normals recalculated outward, and its decimation crumbs (< 12 vertex islands)
dropped. The tail wheel is split into its two islands: the wheel (spins, LandingGear.wheels) and the fork (strut).
Output: assets/model_nimrod/src/fal/opt/<name>.glb (read by nimrod_props.py).

  blender --background --factory-startup --python blender/fd32/props/process_props_fd32.py
"""
import bpy, bmesh, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FAL = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'assets', 'model_b17g', 'src', 'fal'))
SRC, OUT = os.path.join(FAL, 'remesh'), os.path.join(FAL, 'opt')
SMOOTH = ('prop3', 'mainwheel', 'ck_seat', 'ck_yoke2', 'ck_quadrant2', 'ck_column', 'ck_c1')   # round 2: ck_yoke / ck_quadrant / ck_lever_* replaced
TINT = dict(ck_quadrant2=(0.30, 0.31, 0.26), ck_column=(0.42, 0.52, 0.34), ck_yoke2=(0.40, 0.40, 0.40))
BUDGET = dict(prop3=4200, r1820=5000, ck_seat=3500, ck_yoke2=3000, ck_quadrant2=3500, ck_column=800, ck_c1=1800, mainwheel=5200, tailwheel=2000, topturret_ng=3600, ballturret_ng=3600, chinturret_ng=3200, tailmantlet=2400)


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def islands(bm):
    bm.verts.ensure_lookup_table()
    lab, out = {}, []
    for v in bm.verts:
        if v.index in lab:
            continue
        cur, st = [], [v]; lab[v.index] = len(out)
        while st:
            u = st.pop(); cur.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in lab:
                    lab[w.index] = len(out); st.append(w)
        out.append(cur)
    return out


def export(o, name):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, name + '.glb'), export_format='GLB', export_yup=True, export_apply=True, use_selection=True)


TEX_OUT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'assets', 'textures_b17g'))


def save_basecolor(name):
    """the generated model's own base-colour texture -> assets/textures_b17g/b17g_pr_<name>_b.png (1024; used by the pr_<name> material)"""
    best = None
    for im in bpy.data.images:
        if im.size[0] < 64:
            continue
        n = im.name.lower()
        score = (2 if ('base' in n or 'color' in n or 'albedo' in n or 'diffuse' in n) else 0) + (0 if ('normal' in n or 'rough' in n or 'metal' in n) else 1)
        if best is None or score > best[0]:
            best = (score, im)
    if best is None:
        print(f'[props] {name}: no base-colour image'); return
    im = best[1]
    if im.size[0] > 1024:
        im.scale(1024, 1024)
    if name in TINT:      # tripo returned an untinted grey body: paint it (black / olive drab, photos 106 / 109)
        import array
        px = array.array('f', [0.0]) * (im.size[0] * im.size[1] * 4); im.pixels.foreach_get(px)
        t = TINT[name]
        for c in range(3):
            px[c::4] = array.array('f', [v * t[c] for v in px[c::4]])
        im.pixels.foreach_set(px)
    im.filepath_raw = os.path.join(TEX_OUT, f'b17g_pr_{name}_b.png'); im.file_format = 'PNG'; im.save()
    print(f'[props] {name}: base colour -> b17g_pr_{name}_b.png')


def one(name, target):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # M1 review: the remeshed prop / tyre read as blocky; they are decimated from the dense tripo output instead (smooth blades, round tyre)
    RAW = os.path.join(FAL, 'raw')
    src = os.path.join(RAW, name + '.glb') if name in SMOOTH else os.path.join(SRC, name + '_remesh.glb')
    bpy.ops.import_scene.gltf(filepath=src)
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
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    o.parent = None
    t0 = tris(o)
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-4)       # merge the near-coincident seam vertices of the generated shell
    nb0 = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if len(e.link_faces) == 1], sides=0)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(o.data); bm.free()
    if tris(o) > target:
        d = o.modifiers.new('dec', 'DECIMATE'); d.ratio = target / tris(o); d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier='dec')
    bm = bmesh.new(); bm.from_mesh(o.data)
    isl = islands(bm)
    kill = [v for i in isl if len(i) < 12 for v in i]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    if os.environ.get('B17G_PROPS_RECALC') == '1':
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # orientation per island from its signed volume (the generated shells keep their own winding; an inside-out island is flipped)
    flipped = 0
    for isl_ in islands(bm):
        ids = set(v.index for v in isl_)
        fs_ = [f for f in bm.faces if f.verts[0].index in ids]
        vol = sum(f.verts[0].co.dot(f.verts[k].co.cross(f.verts[k + 1].co)) for f in fs_ for k in range(1, len(f.verts) - 1)) / 6.0
        if vol < 0:
            bmesh.ops.reverse_faces(bm, faces=fs_); flipped += 1
    if flipped:
        print(f'[props] {name}: {flipped} inside-out island(s) flipped')
    nb1 = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    # faces within 6 % of the prop size of a remaining open edge get a reversed twin: a ray through a leftover seam meets a front face
    from mathutils.kdtree import KDTree
    bverts = {v.index for e in bm.edges if len(e.link_faces) == 1 for v in e.verts}
    twins = 0
    if bverts and name not in SMOOTH:     # the smooth props are made two-sided in b17g_props (prop) / closed by the tyre mirror
        bm.verts.ensure_lookup_table()
        kd = KDTree(len(bverts))
        for i in bverts:
            kd.insert(bm.verts[i].co, i)
        kd.balance()
        size = max((max(v.co[i] for v in bm.verts) - min(v.co[i] for v in bm.verts)) for i in range(3))
        r = 0.06 * size
        sel = [f for f in bm.faces if any(kd.find(v.co)[2] < r for v in f.verts)]
        uv = bm.loops.layers.uv.active
        for f in sel:
            old_loops = list(reversed(list(f.loops)))
            vs = [bm.verts.new(l.vert.co - f.normal * 0.0008) for l in old_loops]     # 0.8 mm (model units) inside: never coplanar with the original
            nf = bm.faces.new(vs)
            nf.material_index = f.material_index
            if uv is not None:
                for ln, lo in zip(nf.loops, old_loops):
                    ln[uv].uv = lo[uv].uv
            twins += 1
    print(f'[props] {name}: {twins} twin faces near {len(bverts)} open-edge verts')
    bm.to_mesh(o.data); bm.free()
    try:
        o.data.set_sharp_from_angle(angle=1.30 if name in SMOOTH else 0.70)
        if name in SMOOTH:
            for pg in o.data.polygons:
                pg.use_smooth = True
    except Exception:
        pass
    print(f'[props] {name}: tris {t0} -> {tris(o)}, open edges {nb0} -> {nb1}, crumbs removed {len(kill)} verts')
    os.makedirs(OUT, exist_ok=True)
    if False:
        # split: the wheel island (round, the larger) and the fork
        bm = bmesh.new(); bm.from_mesh(o.data)
        isl = sorted(islands(bm), key=len, reverse=True)
        keep_sets = {'tailwheel_wheel': set(v.index for v in isl[0]), 'tailwheel_fork': set(v.index for i in isl[1:] for v in i)}
        bm.free()
        for nm, ks in keep_sets.items():
            c = o.copy(); c.data = o.data.copy(); bpy.context.scene.collection.objects.link(c)
            b2 = bmesh.new(); b2.from_mesh(c.data); b2.verts.ensure_lookup_table()
            bmesh.ops.delete(b2, geom=[v for v in b2.verts if v.index not in ks], context='VERTS')
            b2.to_mesh(c.data); b2.free()
            print(f'[props] {nm}: {tris(c)} tris')
            export(c, nm)
    else:
        export(o, name)
    save_basecolor(name)


for n in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else list(BUDGET)):
    one(n, BUDGET[n])
