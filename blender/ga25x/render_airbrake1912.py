"""1.9.12 renders of the GA-25X airbrake panels on the shipped model, in every livery, shut and open, lit and unlit.

  blender --background assets/model_ga25x/ga25x.blend --python blender/ga25x/render_airbrake1912.py -- <textures_dir> <out_dir> [--site y_hinge,y_aft,z_lo,x_in] [--only <livery key>] [--no-panels]

The panels are rebuilt in memory from the model (airbrake1912.build_objects); nothing is saved. Workbench, backface culling on as in
Unity, texture colour on the `livery` UVs, view transform Standard. The untextured materials of the panels are shown in the colours the
Unity build really draws them with (GAME_COLOURS below; read from unity/Editor/GA25XBuild.cs BuildMaterials and StockStructure.cs, see
airbrake1912.py), not in the Blender viewport colours of the model file.
Views (round 2: both sides and straight behind): left side, right side, straight behind (chase height), left / right rear quarter,
whole aircraft, top, front quarter, close-up of the left well, close-up of the right panel's inner face, close-up of the left hinge line
from ahead.
lit = studio light, flat = texture / material colour only.
Writes <out>/<livery>_<lit|flat>_<shut|open>_<view>.png and tiles.json (run_airbrake1912.py makes one contact sheet per livery and light mode).
"""
import bpy, sys, os, json
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airbrake1912 as AB

argv = sys.argv[sys.argv.index('--') + 1:]
tdir, out = os.path.abspath(argv[0]), os.path.abspath(argv[1])
site = dict(AB.SITE)
if '--site' in argv:
    v = [float(a) for a in argv[argv.index('--site') + 1].split(',')]
    site = dict(y_hinge=v[0], y_aft=v[1], z_lo=v[2], x_in=v[3])
only = argv[argv.index('--only') + 1] if '--only' in argv else None
panels = '--no-panels' not in argv
os.makedirs(out, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.view_settings.view_transform = 'Standard'
sh = scene.display.shading
sh.color_type = 'TEXTURE'
sh.show_backface_culling = True
sh.background_type = 'VIEWPORT'
sh.background_color = (0.55, 0.6, 0.65)
sh.show_cavity = False
scene.render.resolution_x, scene.render.resolution_y = 900, 600
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
O = bpy.data.objects
for o in O:
    if o.users_collection and o.users_collection[0].name == 'GA25X_extras':
        o.hide_render = True


def lin(c):
    return ((c / 12.92) if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)


for name, srgb in AB.GAME_COLOURS.items():          # what Unity draws, not the model file's viewport colours
    m = bpy.data.materials.get(name)
    if m is not None:
        m.diffuse_color = (lin(srgb[0]), lin(srgb[1]), lin(srgb[2]), 1.0)
if panels:
    objs, rep = AB.build_objects(site)
mat = bpy.data.materials['paint']
nt = mat.node_tree
img_node = nt.nodes.new('ShaderNodeTexImage')
nt.nodes.active = img_node
nt.links.new(img_node.outputs['Color'], nt.nodes.get('Principled BSDF').inputs['Base Color'])
yc = 0.5 * (site['y_hinge'] + site['y_aft'])
zc = site['z_lo'] + 0.2
VIEWS = (('sideL', (-8.5, yc - 0.2, 1.3), (0.0, yc - 0.2, 0.6), 50),
         ('sideR', (8.5, yc - 0.2, 1.3), (0.0, yc - 0.2, 0.6), 50),
         ('behind', (0.0, yc - 8.5, 2.6), (0.0, yc + 1.0, 0.9), 45),
         ('rearqL', (-2.9, yc - 4.8, 2.7), (-0.2, yc, zc), 40),
         ('rearqR', (2.9, yc - 4.8, 2.7), (0.2, yc, zc), 40),
         ('whole', (-9.0, yc - 11.0, 5.5), (0.0, -2.0, 0.3), 40),
         ('top', (0.0, yc - 0.3, 9.0), (0.0, yc - 0.3, 0.0), 50),
         ('frontq', (-4.4, yc + 5.2, 2.6), (-0.3, yc - 0.3, zc), 50),
         ('wellL', (-2.2, yc - 0.2, 3.0), (-0.35, yc - 0.1, zc), 50),
         ('innerR', (0.9, yc - 3.2, 1.9), (0.7, yc - 0.2, zc + 0.5), 50),
         ('hingeL', (-1.9, site['y_hinge'] + 1.5, 2.0), (-0.4, site['y_hinge'] - 0.15, zc + 0.15), 60))


def look(loc, target, lens):
    cam.location = Vector(loc)
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


meta = json.load(open(os.path.join(tdir, 'ga25x_liveries.json')))
files = {}
for key, e in meta.items():
    if only and key != only:
        continue
    img_node.image = bpy.data.images.load(os.path.join(tdir, e['texture']), check_existing=True)
    for light in ('lit', 'flat'):
        sh.light = 'STUDIO' if light == 'lit' else 'FLAT'
        for state, deg in (('shut', 0.0), ('open', AB.MAX_ANGLE)):
            if panels:
                AB.pose(deg)
            elif state == 'open':
                continue
            for name, loc, tgt, lens in VIEWS:
                look(loc, tgt, lens)
                fp = os.path.join(out, f'{key}_{light}_{state}_{name}.png')
                scene.render.filepath = fp
                bpy.ops.render.render(write_still=True)
                files.setdefault((key, light), []).append(fp)
    print('[airbrake render]', key)
json.dump({f'{k[0]}_{k[1]}': v for k, v in files.items()}, open(os.path.join(out, 'tiles.json'), 'w'), indent=1)   # run_airbrake1912.py makes the contact sheets
