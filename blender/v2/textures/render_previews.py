"""Render the textured B-25H v2 for every livery (Cycles) and a cockpit-eye view with the gauges.

  blender --background <b25h_v2.blend> --python blender/v2/textures/render_previews.py -- [--tex <dir>] [--out <dir>]
        [--liveries a,b] [--views front34,left,right,top,bottom] [--res 960] [--samples 48] [--no-cockpit]

The preview shader approximates the game: albedo = livery x AO, tangent normal map (OpenGL),
metallic = _m.R, roughness = 1 - _m.A (raised a little by the livery Glossiness). Not the game's shader.
Per livery it writes previews/<livery>_<view>.png and a contact sheet previews/<livery>.png.
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_lib as T

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
TEX = os.path.abspath(opt('--tex', T.OUT))
OUTD = os.path.abspath(opt('--out', os.path.join(T.OUT, 'previews')))
os.makedirs(OUTD, exist_ok=True)
LIVS = opt('--liveries', 'usaaf_od,usaaf_metal,od_plain,darkgrey_plain,bdf_mattegrey,bdf_temperate,pala_matteblack,pala_desert').split(',')
VIEWS = opt('--views', 'front34,left,right,top,bottom,rear34').split(',')
RES = int(opt('--res', '960'))
SAMPLES = int(opt('--samples', '48'))
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
cp = bpy.context.preferences.addons['cycles'].preferences
try:
    cp.compute_device_type = 'OPTIX'
    cp.get_devices()
    for d in cp.devices:
        d.use = d.type == 'OPTIX'
    scene.cycles.device = 'GPU'
except Exception:
    pass
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = RES, int(RES * 0.625)
scene.render.film_transparent = False
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.render.image_settings.file_format = 'PNG'

world = bpy.data.worlds.new('pv') if not scene.world else scene.world
scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    wn.nodes.remove(n)
bg = wn.nodes.new('ShaderNodeBackground')
bg.inputs['Color'].default_value = (0.42, 0.48, 0.56, 1)
bg.inputs['Strength'].default_value = 0.9
wo = wn.nodes.new('ShaderNodeOutputWorld')
wn.links.new(bg.outputs[0], wo.inputs[0])
sun_d = bpy.data.lights.new('sun', 'SUN')
sun_d.energy = 3.2
sun_d.angle = math.radians(3)
sun = bpy.data.objects.new('sun', sun_d)
scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(40), math.radians(-25), math.radians(35))


def img(name, nonc=False):
    p = os.path.join(TEX, name)
    if not os.path.exists(p):
        return None
    im = bpy.data.images.load(p, check_existing=True)
    if nonc:
        im.colorspace_settings.name = 'Non-Color'
    return im


def tex_node(nt, image, uv):
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = image
    u = nt.nodes.new('ShaderNodeUVMap')
    u.uv_map = uv
    nt.links.new(u.outputs[0], t.inputs[0])
    return t


def setup_paint(mat, livery, gloss):
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bs.outputs[0], out.inputs[0])
    col = tex_node(nt, img(f'b25h_livery_{livery}.png'), 'livery')
    ao = tex_node(nt, img('b25h_skin_ao.png', True), 'livery')
    mul = nt.nodes.new('ShaderNodeMix')
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    nt.links.new(col.outputs['Color'], mul.inputs['A'])
    nt.links.new(ao.outputs['Color'], mul.inputs['B'])
    nt.links.new(mul.outputs['Result'], bs.inputs['Base Color'])
    nm = tex_node(nt, img('b25h_skin_n.png', True), 'livery')
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nmap.uv_map = 'livery'
    nt.links.new(nm.outputs['Color'], nmap.inputs['Color'])
    nt.links.new(nmap.outputs['Normal'], bs.inputs['Normal'])
    mm = tex_node(nt, img('b25h_skin_m.png', True), 'livery')
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(mm.outputs['Color'], sep.inputs[0])
    nt.links.new(sep.outputs[0], bs.inputs['Metallic'])
    ma = nt.nodes.new('ShaderNodeMath')
    ma.operation = 'MULTIPLY_ADD'
    ma.inputs[1].default_value = -1.0
    ma.inputs[2].default_value = 1.0 - 0.5 * gloss
    nt.links.new(mm.outputs['Alpha'], ma.inputs[0])
    nt.links.new(ma.outputs[0], bs.inputs['Roughness'])


def setup_tiled(mat, name, rough=0.7, metal=0.0):
    im = img(name)
    if im is None:
        return
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bs.outputs[0], out.inputs[0])
    t = tex_node(nt, im, 'detail')
    nt.links.new(t.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal


def setup_gauges(mat):
    im = img('b25h_gauges.png')
    if im is None:
        return
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bs.outputs[0], out.inputs[0])
    t = tex_node(nt, im, 'livery')
    nt.links.new(t.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.35
    em = nt.nodes.new('ShaderNodeMix')


M = bpy.data.materials
setup_tiled(M['interior'], 'b25h_interior_b.png', 0.75)
setup_tiled(M['structure'], 'b25h_structure_b.png', 0.5, 0.6)
setup_tiled(M['metal_dark'], 'b25h_metal_dark_b.png', 0.55, 0.3)
setup_tiled(M['rubber'], 'b25h_rubber_b.png', 0.9)
setup_tiled(M['prop'], 'b25h_prop_b.png', 0.6)
setup_tiled(M['cockpit'], 'b25h_cockpit_b.png', 0.8)
setup_gauges(M['gauges'])
# extras that are not part of the airframe (prop disc meshes from the propdisc FBX sit at the origin)
for o in bpy.data.objects:
    if o.name.startswith('propdisc'):
        o.hide_render = True

cam_d = bpy.data.cameras.new('pc')
cam = bpy.data.objects.new('pc', cam_d)
scene.collection.objects.link(cam)
scene.camera = cam


def look(loc, target, lens=50, ortho=None):
    loc, target = Vector(loc), Vector(target)
    cam.location = loc
    cam.rotation_euler = (target - loc).to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam_d.type = 'ORTHO'
        cam_d.ortho_scale = ortho
    else:
        cam_d.type = 'PERSP'
        cam_d.lens = lens
    cam_d.clip_start, cam_d.clip_end = 0.05, 300


VIEWDEF = {
    'front34': ((-17, 21, 8), (0, -1.0, 0.2), 50, None),
    'rear34': ((16, -22, 9), (0, -1.0, 0.3), 50, None),
    'left': ((-40, -1.8, 0.6), (0, -1.8, 0.6), None, 17.5),
    'right': ((40, -1.8, 0.6), (0, -1.8, 0.6), None, 17.5),
    'top': ((0, -1.8, 40), (0, -1.8, 0), None, 21.5),
    'bottom': ((0, -1.8, -40), (0, -1.8, 0), None, 21.5),
    'close_nacelle': ((-6.5, 4.5, 2.2), (-2.6, 0.3, 0.0), 50, None),
    'close_nose': ((-4.2, 7.5, 1.2), (0, 3.6, 0.3), 50, None),
    'close_tail': ((-5.5, -11.0, 2.6), (-1.5, -7.6, 1.2), 50, None),
}
paint = M['paint']
meta = {}
mp = os.path.join(TEX, 'b25h_liveries.json')
if os.path.exists(mp):
    with open(mp) as f:
        meta = json.load(f)
for liv in LIVS:
    if not os.path.exists(os.path.join(TEX, f'b25h_livery_{liv}.png')):
        print('skip', liv)
        continue
    setup_paint(paint, liv, meta.get(liv, {}).get('glossiness', 0.0))
    tiles = []
    for v in VIEWS:
        loc, tgt, lens, ortho = VIEWDEF[v]
        if v == 'bottom':
            cam.rotation_mode = 'XYZ'
        look(loc, tgt, lens or 50, ortho)
        if v in ('top', 'bottom'):
            cam.rotation_euler = (0 if v == 'top' else math.pi, 0, 0 if v == 'top' else math.pi)
        p = os.path.join(OUTD, f'{liv}_{v}.png')
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles.append(p)
        print('[pv] rendered', p)
    # contact sheet (2 columns)
    ims = [T.load_image(p)[..., :3] for p in tiles]
    h, w = ims[0].shape[:2]
    rows = (len(ims) + 1) // 2
    sheet = np.ones((rows * h, 2 * w, 3), np.float32)
    for k, a in enumerate(ims):
        r, c = k // 2, k % 2
        sheet[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w] = a
    T.save_png(sheet, os.path.join(OUTD, f'{liv}.png'))

if '--no-cockpit' not in argv:
    eye = bpy.data.objects.get('cockpit_eye')
    loc = eye.matrix_world.translation if eye else Vector((-0.36, 3.42, 1.10))
    look(loc, loc + Vector((0.12, 1.0, -0.38)), 18)
    scene.render.resolution_x, scene.render.resolution_y = 1280, 800
    p = os.path.join(OUTD, 'cockpit_eye.png')
    scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    print('[pv] rendered', p)
