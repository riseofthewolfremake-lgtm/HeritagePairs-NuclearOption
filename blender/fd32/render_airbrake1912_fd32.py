"""1.9.12 review renders of the FD-32 on the shipped model: airbrake panels shut / open, every livery, lit / flat, gear down.

  blender --background assets/model_fd32/fd32.blend --python blender/fd32/render_airbrake1912_fd32.py -- <textures_dir> <out_dir>
          [--only key,key] [--no-panels] [--res 900] [--views left,right,...]

The panels are rebuilt in memory from the model (airbrake1912_fd32.build_objects); nothing is saved. Workbench, backface culling on as
in Unity, texture colour on the `livery` UVs (objects without the livery show their material colour).
  lit  = studio light, the green gear-down strips shown ON (bright green: the model is built gear down)
  flat = no shading (texture colour only), strips OFF
Six whole-aircraft views (left, right, top, below, front-left quarter, rear-right quarter) + two close-ups of the panel (rear-left,
front-right) + two fin / rudder close-ups (finL, finR: the rudder number, both sides). Round 2: the untextured materials are shown
in the colour UNITY gives them (FD32Build.cs BuildMaterials: FD32_cove = Color(0.045, 0.045, 0.048) non-metallic; FD32_metal_dark = white x
fd32_tile_metal_dark_b, whose mean is read here from the texture folder), converted sRGB -> linear: the livery texture is an sRGB image
and the first renders showed the model file's LINEAR viewport colours beside it, i.e. the dark seam and hinge blocks came out pale grey
on PALA Matte Black. `structure` is a stock material in Unity (StockStructure.LookMaterial) and keeps the model's viewport colour here.
Writes <out>/<livery>_<lit|flat>_<shut|open>_<view>.png and tiles.json (the runner makes the contact sheets).
--no-panels renders the model as shipped (1.9.11) with the same cameras: <livery>_<light>_stock_<view>.png.
"""
import bpy, sys, os, json
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airbrake1912_fd32 as AB

argv = sys.argv[sys.argv.index('--') + 1:]
tdir, out = os.path.abspath(argv[0]), os.path.abspath(argv[1])
only = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
panels = '--no-panels' not in argv
res = int(argv[argv.index('--res') + 1]) if '--res' in argv else 900
os.makedirs(out, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
sh = scene.display.shading
sh.color_type = 'TEXTURE'
sh.show_backface_culling = True
sh.background_type = 'VIEWPORT'
sh.background_color = (0.55, 0.6, 0.65)
sh.show_cavity = False
scene.render.resolution_x, scene.render.resolution_y = res, int(res * 2 / 3)
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'Standard'
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
O = bpy.data.objects
for o in O:
    if o.users_collection and o.users_collection[0].name == 'FD32_extras':
        o.hide_render = True
if panels:
    objs, rep = AB.build_objects()
mat = bpy.data.materials['paint']
mat.use_nodes = True
nt = mat.node_tree
img_node = nt.nodes.new('ShaderNodeTexImage')
nt.nodes.active = img_node
bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
nt.links.new(img_node.outputs['Color'], bs.inputs['Base Color'])
def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def unity_colour(name, srgb):
    m = bpy.data.materials.get(name)
    if m:
        m.diffuse_color = tuple(lin(c) for c in srgb) + (1.0,)


unity_colour('cove', (0.045, 0.045, 0.048))                                   # FD32Build.cs: Save(LitMat(lit, "FD32_cove", new Color(0.045f, 0.045f, 0.048f), 0f, 0.1f), "cove")
_tile = os.path.join(tdir, 'fd32_tile_metal_dark_b.png')
if not os.path.exists(_tile):
    _tile = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'assets', 'textures_fd32', 'fd32_tile_metal_dark_b.png')
_im = bpy.data.images.load(_tile)
_px = list(_im.pixels[:])                                                      # float sRGB-encoded values of an 8-bit image
_n = len(_px) // 4
unity_colour('metal_dark', tuple(sum(_px[c::4]) / _n for c in range(3)))      # FD32Build.cs TileMats: white x fd32_tile_metal_dark_b
strip = bpy.data.materials.get('light_off')
strip_off = tuple(strip.diffuse_color) if strip else None
s = AB.SITE
yc, zc = 0.5 * (s['y_hinge'] + s['y_aft']), 0.5 * (s['z_lo'] + s['z_hi'])
VIEWS = (('left', (-13.5, -1.75, 0.5), (0.0, -1.75, 0.3), 50),
         ('right', (13.5, -1.75, 0.5), (0.0, -1.75, 0.3), 50),
         ('top', (0.0, -1.75, 16.0), (0.0, -1.75, 0.0), 50),
         ('below', (0.01, -1.75, -16.0), (0.0, -1.75, 0.0), 50),
         ('frontL', (-7.5, 7.5, 3.0), (0.0, -0.4, 0.1), 42),
         ('rearR', (6.5, -10.0, 3.2), (0.0, -1.2, 0.1), 42),
         ('behind', (0.0, -15.0, 1.6), (0.0, -1.75, 0.4), 60),            # 1.9.12 fix round: straight from behind (both panels at once)
         ('closeL', (-2.6, yc - 2.6, 0.75), (-0.35, yc + 0.05, zc), 50),
         ('closeR', (2.9, yc + 1.9, 0.55), (0.35, yc - 0.1, zc), 50),
         ('shoulderL', (-2.6, -0.2, 2.4), (-0.15, -1.3, 0.25), 60),      # fuselage flank / top turn and the wing root: where the pattern changes projection
         ('shoulderR', (2.6, -3.2, 2.2), (0.15, -2.0, 0.2), 60),
         ('finL', (-4.0, -4.9, 0.72), (0.0, -4.9, 0.72), 85),
         ('finR', (4.0, -4.9, 0.72), (0.0, -4.9, 0.72), 85))
if '--views' in argv:
    keep = argv[argv.index('--views') + 1].split(',')
    VIEWS = tuple(v for v in VIEWS if v[0] in keep)


def look(loc, target, lens):
    cam.location = Vector(loc)
    cam.rotation_mode = 'XYZ'
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    cam.data.clip_start = 0.05


meta = json.load(open(os.path.join(tdir, 'fd32_liveries.json')))
files = {}
for key, e in meta.items():
    if only and key not in only:
        continue
    img_node.image = bpy.data.images.load(os.path.join(tdir, e['texture']), check_existing=True)
    for light in ('lit', 'flat'):
        sh.light = 'STUDIO' if light == 'lit' else 'FLAT'
        if strip:
            strip.diffuse_color = (0.25, 1.0, 0.35, 1.0) if light == 'lit' else strip_off
        for state, deg in ((('shut', 0.0), ('open', AB.MAX_ANGLE)) if panels else (('stock', 0.0),)):
            if panels:
                AB.pose(deg)
            for name, loc, tgt, lens in VIEWS:
                look(loc, tgt, lens)
                fp = os.path.join(out, f'{key}_{light}_{state}_{name}.png')
                scene.render.filepath = fp
                bpy.ops.render.render(write_still=True)
                files.setdefault(f'{key}_{light}_{state}', []).append(fp)
    print('[render]', key, flush=True)
tj = os.path.join(out, 'tiles.json')
old = json.load(open(tj)) if os.path.exists(tj) else {}
for k, v in files.items():                # a later run with other --views adds to a sheet, it does not replace it
    old[k] = [f for f in old.get(k, []) if f not in v] + v
json.dump(old, open(tj, 'w'), indent=1)
