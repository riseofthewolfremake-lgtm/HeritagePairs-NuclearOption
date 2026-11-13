"""1.8.18 close-up proof renders of the B-17G nose: the NM anti-glare panel edge from outside and the astrodome opening from inside.

  blender --background <b17g.blend> --python blender/b17g/render_fix1818.py -- --out <dir> --tag <before|after> --tex <textures dir>
          [--livery usaaf_nm] [--only v1,v2] [--res 1600x1000]

Renders only (no model change). Output goes OUTSIDE the repo (nuclearoption-ref/study/b17g_nose/fix1818). The paint texture is sampled
with 'Closest' interpolation in the edge close-ups (`*_px` views) so the texel staircase shows the way a magnified game view shows it,
and with 'Linear' (the game's bilinear) in the others.
"""
import bpy, sys, os, math, json
from mathutils import Vector as V, Euler

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


OUT, TAG, TEX = os.path.abspath(arg('--out', '.')), arg('--tag', 'ours'), arg('--tex')
LIV_KEY = arg('--livery', 'usaaf_nm')
ONLY = arg('--only')
RES = tuple(int(v) for v in arg('--res', '1600x1000').split('x'))
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for o in bpy.data.objects:
    if o.name.endswith('_hullsrc'):
        o.hide_render = True
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
w = sc.world or bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get('Background'); bg.inputs[0].default_value = (0.62, 0.70, 0.80, 1); bg.inputs[1].default_value = 0.9
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.0; sun.rotation_euler = Euler((math.radians(40), math.radians(15), math.radians(35)))
fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill)
fill.data.energy = 1.8; fill.rotation_euler = Euler((math.radians(150), 0, math.radians(-140)))
inl = bpy.data.objects.new('inl', bpy.data.lights.new('inl', 'POINT')); sc.collection.objects.link(inl)     # a lamp in the nose for the inside views
inl.data.energy = 25.0; inl.location = V((0.25, 5.15, 0.75)); inl.data.shadow_soft_size = 0.3
try:
    sc.view_settings.view_transform = 'Standard'
except Exception:
    pass


def img(path, nonc=False):
    if not path or not os.path.exists(path):
        return None
    im = bpy.data.images.load(path, check_existing=True)
    if nonc:
        im.colorspace_settings.name = 'Non-Color'
    return im


PAINT_TEX = []


def set_tex(mat, b, n=None, uv='livery', paint=False):
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        if nd.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(nd)
    bs = nt.nodes.get('Principled BSDF')
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uv
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = b; nt.links.new(uvn.outputs[0], t.inputs[0]); nt.links.new(t.outputs[0], bs.inputs['Base Color'])
    if paint:
        PAINT_TEX.append(t)
    if n is not None:
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = n; nt.links.new(uvn.outputs[0], tn.inputs[0])
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.uv_map = uv
        nt.links.new(tn.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], bs.inputs['Normal'])
    return bs, uvn


T = os.path.abspath(TEX)
LIV = json.load(open(os.path.join(T, 'b17g_liveries.json')))
paint = bpy.data.materials.get('paint')
bs, uvn = set_tex(paint, img(os.path.join(T, LIV[LIV_KEY]['texture'])), img(os.path.join(T, 'b17g_skin_n.png'), True), paint=True)
mimg = img(os.path.join(T, LIV[LIV_KEY]['metal']), True)
if mimg is not None:        # metallic (R) / smoothness (A) map as the game's AircraftSkin reads it
    nt = paint.node_tree
    tm = nt.nodes.new('ShaderNodeTexImage'); tm.image = mimg; nt.links.new(uvn.outputs[0], tm.inputs[0]); PAINT_TEX.append(tm)
    sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(tm.outputs[0], sep.inputs[0]); nt.links.new(sep.outputs[0], bs.inputs['Metallic'])
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(tm.outputs['Alpha'], inv.inputs[1]); nt.links.new(inv.outputs[0], bs.inputs['Roughness'])
for k in ('structure', 'interior', 'well', 'gear', 'tyre', 'cowl', 'turret'):
    mt = bpy.data.materials.get(k); b = img(os.path.join(T, f'b17g_tile_{k}_b.png'))
    if mt and b:
        set_tex(mt, b, img(os.path.join(T, f'b17g_tile_{k}_n.png'), True), uv='detail')
gl = bpy.data.materials.get('glass')
if gl and gl.use_nodes:
    g = gl.node_tree.nodes.get('Principled BSDF')
    g.inputs['Base Color'].default_value = (0.30, 0.38, 0.44, 1); g.inputs['Roughness'].default_value = 0.05
    try:
        g.inputs['Alpha'].default_value = 0.35; gl.surface_render_method = 'BLENDED'
    except Exception:
        pass
for m in bpy.data.materials:      # game: back faces culled (Unity Standard / AircraftSkin)
    try:
        m.use_backface_culling = True
    except Exception:
        pass


def cam(loc, tgt, lens=40):
    c = bpy.data.cameras.new('c'); c.clip_start = 0.01; c.clip_end = 200; c.lens = lens
    o = bpy.data.objects.new('c', c); sc.collection.objects.link(o)
    o.location = V(loc)
    o.rotation_euler = (V(tgt) - V(loc)).normalized().to_track_quat('-Z', 'Y').to_euler()
    return o


VIEWS = {   # name: (camera, target, lens, paint interpolation)
    # anti-glare panel: rounded front edge round the astrodome (the in-game p5_dome_out angle: above right, ahead)
    'glare_out': ((0.95, 6.25, 2.15), (0.15, 5.45, 1.50), 30, 'Linear'),
    'glare_out_px': ((0.62, 5.95, 1.95), (0.42, 5.62, 1.62), 40, 'Closest'),
    'glare_top': ((0.0, 5.45, 3.6), (0.0, 5.45, 1.4), 35, 'Linear'),
    # astrodome opening from inside the nose (the p5_dome_close angle: navigator's place, looking up / sideways)
    'dome_in': ((0.30, 5.10, 0.95), (0.0, 5.40, 1.55), 22, 'Linear'),
    'dome_in_side': ((0.55, 5.38, 1.00), (-0.05, 5.38, 1.55), 22, 'Linear'),
    'dome_in_up': ((0.02, 5.38, 0.95), (0.0, 5.385, 1.70), 24, 'Linear'),
}
for nm, (loc, tgt, lens, interp) in VIEWS.items():
    if ONLY and nm not in ONLY.split(','):
        continue
    for t in PAINT_TEX:
        t.interpolation = interp
    sc.camera = cam(loc, tgt, lens); sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.filepath = os.path.join(OUT, f'{nm}_{TAG}.png')
    bpy.ops.render.render(write_still=True)
    print('[render1818]', nm)
