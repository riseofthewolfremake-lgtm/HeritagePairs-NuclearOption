"""Renders for the Nimrod (media/nimrod_v1).

  blender --background <nimrod.blend> --python blender/nimrod/render_nimrod.py -- --mode silhouettes --out <dir> [--ref <wt obj>]
      side/top/front orthographic silhouette masks of OUR model and (optional) of the WT reference (imported in memory only,
      scaled 1:1, aligned at the propeller tip / spinner), composed into overlays by compose_overlays.py
  ... --mode exterior --tex <assets/textures_nimrod> --out <dir>      3/4 views per livery (textures applied to the paint faces)
  ... --mode cockpit --tex <dir> --out <dir>                           pilot-eye and close-up views
"""
import bpy, sys, os, math, json
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
MODE, OUT, REF, TEX = arg('--mode', 'silhouettes'), os.path.abspath(arg('--out', '.')), arg('--ref'), arg('--tex')
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
ours = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('cooper_')]
for _o in bpy.data.objects:
    if _o.name.startswith('cooper_'):
        _o.hide_render = True
COCKPIT_ONLY_PREFIX = ('cockpit_', 'gauge_', 'mfd_')


def cam(name, loc, rot, ortho=None, lens=50):
    c = bpy.data.cameras.new(name)
    if ortho:
        c.type = 'ORTHO'; c.ortho_scale = ortho
    else:
        c.lens = lens
    c.clip_start = 0.01; c.clip_end = 200
    o = bpy.data.objects.new(name, c)
    sc.collection.objects.link(o)
    o.location = loc; o.rotation_euler = Euler(rot)
    return o


def workbench_flat(color=(0, 0, 0)):
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'FLAT'; sh.color_type = 'SINGLE'; sh.single_color = color
    sc.render.film_transparent = True
    sc.world = sc.world or bpy.data.worlds.new('w')


def render(path, cam_obj, res=(1600, 900)):
    sc.camera = cam_obj
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[render]', path)


def import_ref(path):
    verts = []; faces = []
    for l in open(path):
        if l.startswith('v '):
            x, y, z = map(float, l.split()[1:4]); verts.append((-x, z, y))
        elif l.startswith('f '):
            faces.append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
    me = bpy.data.meshes.new('wt_ref'); me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new('wt_ref', me); sc.collection.objects.link(ob)
    return ob


if MODE == 'silhouettes':
    workbench_flat()
    views = {'side': ((12, 0.0, 0.0), (math.radians(90), 0, math.radians(90)), 9.5),
             'top': ((0, 0.0, 12), (0, 0, 0), 11.0),
             'front': ((0, 12, 0.0), (math.radians(90), 0, math.radians(180)), 11.0)}
    # our model is in the root-at-CG frame in the .blend? No: the .blend keeps Blender world coordinates (root at the CG point)
    ref = import_ref(REF) if REF else None
    for vname, (loc, rot, osz) in views.items():
        c = cam('cam_' + vname, Vector(loc) + Vector((0, -1.2, 0.3)) * (0 if vname != 'front' else 0), rot, ortho=osz)
        if vname == 'side':
            c.location = Vector((12, -1.2, 0.0))
        elif vname == 'top':
            c.location = Vector((0, -1.2, 12))
        else:
            c.location = Vector((0, 12, -0.2))
        for o in ours:
            o.hide_render = o.name.startswith(COCKPIT_ONLY_PREFIX)
        if ref: ref.hide_render = True
        render(os.path.join(OUT, f'_sil_ours_{vname}.png'), c)
        if ref:
            for o in ours: o.hide_render = True
            ref.hide_render = False
            render(os.path.join(OUT, f'_sil_ref_{vname}.png'), c)
            for o in ours: o.hide_render = False
    json.dump(dict(views=list(views)), open(os.path.join(OUT, '_sil_index.json'), 'w'))

else:
    # ------------------------------------------------------------ textured renders (EEVEE)
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
    sc.render.film_transparent = False
    w = sc.world or bpy.data.worlds.new('w'); sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs[0].default_value = (0.55, 0.65, 0.78, 1); bg.inputs[1].default_value = 0.9
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 4.0; sun.rotation_euler = Euler((math.radians(50), math.radians(15), math.radians(35)))
    fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill)
    fill.data.energy = 1.2; fill.rotation_euler = Euler((math.radians(120), 0, math.radians(-140)))
    try:
        sc.view_settings.view_transform = 'Standard'
    except Exception:
        pass

    def img(path, nonc=False):
        if not os.path.exists(path): return None
        im = bpy.data.images.load(path, check_existing=True)
        if nonc: im.colorspace_settings.name = 'Non-Color'
        return im

    def set_tex(mat, b, n=None, m=None, uv='livery', rough=None):
        mat.use_nodes = True
        nt = mat.node_tree; bs = nt.nodes.get('Principled BSDF')
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = b
        uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uv
        nt.links.new(uvn.outputs[0], tex.inputs[0]); nt.links.new(tex.outputs[0], bs.inputs['Base Color'])
        if n is not None:
            tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = n; nt.links.new(uvn.outputs[0], tn.inputs[0])
            nm = nt.nodes.new('ShaderNodeNormalMap'); nm.uv_map = uv
            nt.links.new(tn.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], bs.inputs['Normal'])
        if m is not None:
            tm = nt.nodes.new('ShaderNodeTexImage'); tm.image = m; nt.links.new(uvn.outputs[0], tm.inputs[0])
            sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(tm.outputs[0], sp.inputs[0])
            nt.links.new(sp.outputs[0], bs.inputs['Metallic'])
            inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
            nt.links.new(tm.outputs[1], inv.inputs[1]); nt.links.new(inv.outputs[0], bs.inputs['Roughness'])
        elif rough is not None:
            bs.inputs['Roughness'].default_value = rough

    T = os.path.abspath(TEX) if TEX else None
    if T:
        for name in ('interior', 'tube', 'alu', 'leather', 'wood', 'prop', 'ck_grey', 'rubber', 'gunmetal'):
            mt = bpy.data.materials.get(name)
            b = img(os.path.join(T, f'nimrod_tile_{name}_b.png'))
            if mt and b: set_tex(mt, b, img(os.path.join(T, f'nimrod_tile_{name}_n.png'), True), uv='detail')
        g = bpy.data.materials.get('gauges')
        if g and img(os.path.join(T, 'nimrod_gauges.png')):
            set_tex(g, img(os.path.join(T, 'nimrod_gauges.png')), uv='livery', rough=0.35)
    liveries = json.load(open(os.path.join(T, 'nimrod_liveries.json'))) if T and os.path.exists(os.path.join(T, 'nimrod_liveries.json')) else {}
    paint = bpy.data.materials.get('paint')
    nmap = img(os.path.join(T, 'nimrod_skin_n.png'), True) if T else None
    mmap = img(os.path.join(T, 'nimrod_skin_m.png'), True) if T else None

    if MODE == 'exterior':
        for o in ours:
            o.hide_render = o.name.startswith(('gauge_', 'mfd_'))
        shots = {'34front': ((7.5, 8.5, 2.6), 'front'), '34rear': ((-8.0, -9.0, 3.5), 'rear'), 'side_low': ((10.5, 0.8, -0.2), 'side')}
        keys = list(liveries) or ['default']
        for lk in keys:
            if T and lk in liveries:
                for nd in list(paint.node_tree.nodes):
                    if nd.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
                        paint.node_tree.nodes.remove(nd)
                set_tex(paint, img(os.path.join(T, liveries[lk]['texture'])), nmap, mmap)
            for sname, (loc, tag) in shots.items():
                if lk != keys[0] and sname != '34front':
                    continue
                c = cam('c_' + lk + sname, Vector(loc), (0, 0, 0), lens=55)
                d = Vector((0, 0.2, 0.2)) - c.location
                c.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
                render(os.path.join(OUT, f'ext_{lk}_{sname}.png'), c, res=(1600, 1000))
    elif MODE == 'cockpit':
        # cockpit v2: tiling ck_* materials (detail UV x TILE_SCALE, as Unity), ck_art + gauges atlases on the livery UV
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import nimrod_ck_layout as CL
        if T and liveries:
            lk = list(liveries)[0]
            set_tex(paint, img(os.path.join(T, liveries[lk]['texture'])), nmap, mmap)
        def ck_mat(mat, b, n, scale, met, sm, uv):
            mat.use_nodes = True
            nt = mat.node_tree; bs = nt.nodes.get('Principled BSDF')
            uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uv
            src = uvn.outputs[0]
            if scale != 1.0:
                mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale, scale, 1)
                nt.links.new(uvn.outputs[0], mp.inputs[0]); src = mp.outputs[0]
            tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = b; nt.links.new(src, tb.inputs[0]); nt.links.new(tb.outputs[0], bs.inputs['Base Color'])
            if n is not None:
                tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = n; nt.links.new(src, tn.inputs[0])
                nm = nt.nodes.new('ShaderNodeNormalMap'); nm.uv_map = uv
                nt.links.new(tn.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], bs.inputs['Normal'])
            bs.inputs['Metallic'].default_value = met
            bs.inputs['Roughness'].default_value = 1 - sm
        for k, sc_ in CL.TILE_SCALE.items():
            mt = bpy.data.materials.get(k)
            b = img(os.path.join(T, f'nimrod_tile_{k}_b.png'))
            if mt and b:
                met, sm = CL.TILE_PBR[k]
                ck_mat(mt, b, img(os.path.join(T, f'nimrod_tile_{k}_n.png'), True), sc_, met, sm, 'detail')
        if bpy.data.materials.get('ck_art'):
            ck_mat(bpy.data.materials['ck_art'], img(os.path.join(T, 'nimrod_ckart_b.png')), img(os.path.join(T, 'nimrod_ckart_n.png'), True), 1.0, 0.1, 0.45, 'livery')
        g = bpy.data.materials.get('gauges')
        if g and img(os.path.join(T, 'nimrod_gauges.png')):
            ck_mat(g, img(os.path.join(T, 'nimrod_gauges.png')), None, 1.0, 0.0, 0.55, 'livery')
        try:
            sc.eevee.use_shadows = True
        except Exception:
            pass
        for attr, val in (('use_raytracing', True), ('use_gtao', True)):
            try:
                setattr(sc.eevee, attr, val)
            except Exception:
                pass
        sun.data.energy = 5.0; sun.rotation_euler = Euler((math.radians(35), math.radians(-12), math.radians(20)))
        sun.data.angle = math.radians(2)
        sc.render.film_transparent = False
        eye = Vector(json.loads(arg('--eye', '[0, -0.92, 0.745]')))
        # name: (camera position, look direction, horizontal FOV deg)
        shots = {'pilot_eye': (eye, (0, 1.0, -0.62), 90), 'panel_close': (eye + Vector((0, 0.22, -0.16)), (0, 1.0, -0.62), 62),
                 'left_wall': (eye + Vector((0.10, 0.02, -0.04)), (-0.75, 0.25, -0.75), 85), 'right_wall': (eye + Vector((-0.10, 0.02, -0.04)), (0.75, 0.25, -0.75), 85),
                 'floor': (eye + Vector((0, -0.05, 0.05)), (0, 0.45, -1.0), 88), 'above': (Vector((0.35, -1.75, 1.55)), (-0.22, 0.75, -0.75), 55)}
        for sname, (loc, d, fov) in shots.items():
            c = cam('ck_' + sname, loc, (0, 0, 0))
            c.data.sensor_width = 36; c.data.lens = 18 / math.tan(math.radians(fov) / 2)
            c.rotation_euler = Vector(d).to_track_quat('-Z', 'Y').to_euler()
            render(os.path.join(OUT, f'cockpit_{sname}.png'), c, res=(1600, 900))
