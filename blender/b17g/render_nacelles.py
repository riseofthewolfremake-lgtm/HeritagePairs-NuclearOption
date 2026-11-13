"""B-17G nacelle review renders (1.8.3): our model and the War Thunder reference from the SAME cameras, gear UP.

  blender --background <b17g.blend> --python blender/b17g/render_nacelles.py -- --out <dir> --tag <before|after> --tex assets/textures_b17g
          [--ref <WT obj>] [--grey]

Output goes OUTSIDE the repo (nuclearoption-ref/study/b17g/nac183). The reference is imported in memory only (Blender OBJ importer,
own textures, scaled to the real span) and rendered to <dir>/<view>_ref.png; it is never saved or exported. With --grey both models
are drawn in one neutral grey (shape comparison).
"""
import bpy, sys, os, math, json
from mathutils import Vector as V, Euler, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
OUT, TAG, TEX, REF = os.path.abspath(arg('--out', '.')), arg('--tag', 'ours'), arg('--tex'), arg('--ref')
GREY = '--grey' in argv
ONLY = arg('--only')
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
K = 31.62 / 31.258
ours = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.endswith('_hullsrc')]
for o in bpy.data.objects:          # 1.8.3 collider sources (deleted in Unity) are never drawn
    if o.name.endswith('_hullsrc'):
        o.hide_render = True

sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
w = sc.world or bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get('Background'); bg.inputs[0].default_value = (0.62, 0.70, 0.80, 1); bg.inputs[1].default_value = 0.9
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.5; sun.rotation_euler = Euler((math.radians(40), math.radians(15), math.radians(35)))
fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill)
fill.data.energy = 1.6; fill.rotation_euler = Euler((math.radians(150), 0, math.radians(-140)))
try:
    sc.view_settings.view_transform = 'Standard'
except Exception:
    pass
for attr, val in (('use_raytracing', True), ('use_gtao', True)):
    try:
        setattr(sc.eevee, attr, val)
    except Exception:
        pass


def img(path, nonc=False):
    if not path or not os.path.exists(path):
        return None
    im = bpy.data.images.load(path, check_existing=True)
    if nonc:
        im.colorspace_settings.name = 'Non-Color'
    return im


def set_tex(mat, b, n=None, uv='livery'):
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        if nd.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(nd)
    bs = nt.nodes.get('Principled BSDF')
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uv
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = b; nt.links.new(uvn.outputs[0], t.inputs[0]); nt.links.new(t.outputs[0], bs.inputs['Base Color'])
    if n is not None:
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = n; nt.links.new(uvn.outputs[0], tn.inputs[0])
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.uv_map = uv
        nt.links.new(tn.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], bs.inputs['Normal'])


grey = bpy.data.materials.new('cmp_grey'); grey.use_nodes = True
grey.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.55, 0.56, 0.55, 1)
grey.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.6
if GREY:
    for o in ours:
        for k in range(len(o.data.materials)):
            o.data.materials[k] = grey
elif TEX:
    T = os.path.abspath(TEX)
    LIV = json.load(open(os.path.join(T, 'b17g_liveries.json'))) if os.path.exists(os.path.join(T, 'b17g_liveries.json')) else {}
    paint = bpy.data.materials.get('paint')
    key = 'usaaf_nm' if 'usaaf_nm' in LIV else (list(LIV)[0] if LIV else None)
    if paint and key:
        set_tex(paint, img(os.path.join(T, LIV[key]['texture'])), img(os.path.join(T, 'b17g_skin_n.png'), True))
    for k in ('structure', 'interior', 'well', 'gear', 'tyre', 'cowl', 'turret'):
        mt = bpy.data.materials.get(k); b = img(os.path.join(T, f'b17g_tile_{k}_b.png'))
        if mt and b:
            set_tex(mt, b, img(os.path.join(T, f'b17g_tile_{k}_n.png'), True), uv='detail')

# the Unity build tints the fal R-1820 face (B17G_pr_r1820 base colour 0.46): same here
for m in bpy.data.materials:
    if m.name.startswith('pr_r1820') and m.use_nodes:
        bs = m.node_tree.nodes.get('Principled BSDF')
        if bs and bs.inputs['Base Color'].is_linked:
            lk = bs.inputs['Base Color'].links[0]
            mul = m.node_tree.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
            mul.inputs[7].default_value = (0.46, 0.46, 0.47, 1)
            m.node_tree.links.new(lk.from_socket, mul.inputs[6]); m.node_tree.links.new(mul.outputs[2], bs.inputs['Base Color'])
# gear up (as the reference, which is modelled retracted)
for o in bpy.data.objects:
    info = json.loads(o.get('b25_info') or '{}') if o.get('b25_info') else {}
    if info.get('kind') == 'gear':
        deg = info['fold_deg'] * (1 if info.get('fold_sense') == 'forward-up' else -1)
        o.rotation_euler = Euler((math.radians(deg), 0, 0))
bpy.context.view_layer.update()

ref = []
if REF:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=REF)
    ref = [o for o in bpy.data.objects if o not in before]
    # importer: file (x, y, z) -> blender (x, -z, y); our frame wants (-x, z, y) * K = rotate 180 deg about Z, scale K
    M = Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Scale(K, 4)
    for o in ref:
        o.matrix_world = M @ o.matrix_world
        o.hide_render = True
        if GREY and o.type == 'MESH':
            for k in range(len(o.data.materials)):
                o.data.materials[k] = grey


def cam(loc, tgt, lens=40, ortho=None, up='Y'):
    c = bpy.data.cameras.new('c'); c.clip_start = 0.05; c.clip_end = 400
    if ortho:
        c.type = 'ORTHO'; c.ortho_scale = ortho
    else:
        c.lens = lens
    o = bpy.data.objects.new('c', c); sc.collection.objects.link(o)
    o.location = V(loc); o.rotation_euler = (V(tgt) - V(loc)).to_track_quat('-Z', up).to_euler()
    return o


def shot(name, c, res=(1400, 1000)):
    sc.camera = c; sc.render.resolution_x, sc.render.resolution_y = res
    for o in ref:
        o.hide_render = True
    for o in ours:
        o.hide_render = False
    sc.render.filepath = os.path.join(OUT, f'{name}_{TAG}.png'); bpy.ops.render.render(write_still=True)
    if ref:
        for o in ours:
            o.hide_render = True
        for o in ref:
            o.hide_render = False
        sc.render.filepath = os.path.join(OUT, f'{name}_ref.png'); bpy.ops.render.render(write_still=True)
        for o in ours:
            o.hide_render = False
        for o in ref:
            o.hide_render = True
    print('[render]', name)


VIEWS = {   # right wing (engines 3 inner, 4 outer); the reference is the same aircraft in the same frame
    'in_front34_low': ((6.4, 9.6, -2.4), (3.1, 2.6, -0.35), 32, None, 'Z'),
    'in_side': ((12.0, 1.2, -0.3), (0.0, 1.2, -0.3), 0, 8.4, 'Z'),
    'in_under': ((3.1, 1.0, -9.0), (3.1, 1.0, 0.0), 0, 8.0, 'Y'),
    'in_rear34': ((6.3, -5.6, -2.0), (3.1, 0.8, -0.45), 32, None, 'Z'),
    'in_front': ((3.1, 11.0, -0.1), (3.1, 3.0, -0.1), 60, None, 'Z'),
    'in_well_close': ((4.3, 1.4, -2.6), (3.2, 2.5, -0.6), 30, None, 'Z'),
    'out_front34_low': ((9.6, 8.6, -2.0), (6.575, 2.2, 0.0), 32, None, 'Z'),
    'out_side': ((12.0, 0.9, 0.0), (0.0, 0.9, 0.0), 0, 7.6, 'Z'),
    'out_under': ((6.575, 0.9, -9.0), (6.575, 0.9, 0.0), 0, 7.0, 'Y'),
    'out_rear34': ((9.5, -5.6, -1.6), (6.575, 0.6, -0.1), 32, None, 'Z'),
    'both_under34': ((10.5, -1.5, -6.5), (4.6, 1.5, -0.4), 30, None, 'Z'),
    'in_turbo': ((4.6, -1.6, -2.2), (3.1, 0.4, -0.55), 30, None, 'Z'),
    'out_turbo': ((8.2, 0.0, -2.0), (6.575, 1.6, -0.45), 30, None, 'Z'),
    'le_front': ((5.0, 30.0, 0.2), (5.0, 0.0, 0.2), 0, 10.5, 'Z'),
    'in_cowl_close': ((4.6, 6.4, -0.9), (3.1, 3.9, 0.0), 30, None, 'Z'),
}
if '--sections' in argv:      # cut views (grey): long section through each nacelle axis + cross-sections, camera far, near plane = the cut
    VIEWS = {}
    for kind, xa, za in (('in', 3.10, 0.05), ('out', 6.575, 0.30)):
        VIEWS[f'sec_{kind}_long'] = ((xa + 30.0, 1.4, za - 0.3), (xa - 10, 1.4, za - 0.3), 0, 7.6, 'Z', 30.0)
        for y in (4.25, 3.9, 3.6, 3.3, 3.0, 2.6, 2.2, 1.6, 1.0, 0.4, -0.2, -0.8):
            VIEWS[f'sec_{kind}_y{y:+.1f}'] = ((xa, y + 30.0, za - 0.3), (xa, y - 10, za - 0.3), 0, 3.6, 'Z', 30.0)
    VIEWS = {k: v[:5] for k, v in VIEWS.items()} | {}
    CLIP = {k: 30.0 for k in VIEWS}
else:
    CLIP = {}
for nm, (loc, tgt, lens, ortho, up) in VIEWS.items():
    if ONLY and nm not in ONLY.split(','):
        continue
    if up == 'Z' or ortho is None:
        c = cam(loc, tgt, lens or 40, ortho)
    else:
        c = cam(loc, tgt, lens or 40, ortho)
        c.rotation_euler = Euler((0, math.pi, 0))      # looking up (+Z), nose (+Y) at the top of the frame
        c.rotation_euler = (V((0, 0, 1))).to_track_quat('-Z', 'Y').to_euler()
    if ortho and nm.endswith('_side'):
        c.data.clip_start = loc[0] - (3.95 if nm.startswith('in') else 7.42)
    if nm in CLIP:
        c.data.clip_start = CLIP[nm]
    shot(nm, c)
