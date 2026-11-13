"""Nacelle underside diagnosis renders (GA-25X and B-25H): the baked skin maps shown one at a time on the `livery` UVs,
gear up / gear doors closed (flight pose, as the bake), workbench, flat texture colour.

  blender --background <model.blend> --python blender/ga25x/render_nacelle_diag.py -- <textures_dir> <prefix> <out_dir> [maps...]

maps default: skin_b skin_ao skin_n ; <prefix> = ga25x or b25h (file names <prefix>_skin_*.png). Writes
<out_dir>/<prefix>_nac_<map>_<view>.png. Views: below-side of the left nacelle, straight below.
"""
import bpy, sys, os, math, json
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
tdir, prefix, out = os.path.abspath(argv[0]), argv[1], os.path.abspath(argv[2])
maps = argv[3:] or ['skin_b', 'skin_ao', 'skin_n']
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
O = bpy.data.objects


def info(o):
    s = o.get('b25_info')
    return json.loads(s) if s else {}


# flight pose: same rule as bake_maps.close_door (inverse of the open pose); NACDIAG_SIGN=+1 reproduces the pre-0.3.2 bake pose
SG = int(os.environ.get('NACDIAG_SIGN', '-1'))
for o in list(O):
    if o.name.startswith('gear_door_') and o.type == 'MESH':
        inf = info(o)
        if 'hinge_axis' not in inf or 'open_deg' not in inf:
            continue
        ax = Vector(inf['hinge_axis']).normalized(); ang = math.radians(inf['open_deg'])
        p = o.matrix_world.translation.copy()
        o.matrix_world = Matrix.Translation(p) @ Matrix.Rotation(SG * ang, 4, ax) @ Matrix.Translation(-p) @ o.matrix_world
for o in O:
    if o.name.startswith(('gear_main_', 'gear_nose_', 'prop_')) or (o.users_collection and o.users_collection[0].name.endswith('_extras')):
        o.hide_render = True
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'FLAT'
sh.color_type = 'TEXTURE'
sh.show_backface_culling = True
sh.background_type = 'VIEWPORT'
sh.background_color = (0.55, 0.6, 0.65)
sc.render.resolution_x, sc.render.resolution_y = 1200, 800
sc.view_settings.view_transform = 'Standard'
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam)
sc.camera = cam
mat = bpy.data.materials['paint']
nt = mat.node_tree
img = nt.nodes.new('ShaderNodeTexImage')
nt.nodes.active = img
uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'livery'
nt.links.new(uv.outputs['UV'], img.inputs['Vector'])
bsdf = nt.nodes.get('Principled BSDF')
nt.links.new(img.outputs['Color'], bsdf.inputs['Base Color'])
# aim at the closed main gear doors of the left nacelle (centre of their world bounding box)
dv = [o.matrix_world @ v.co for o in O if o.name.startswith('gear_door_main_L') and o.type == 'MESH' for v in o.data.vertices]
c = sum(dv, Vector()) / len(dv)
VIEWS = {'belowside': (c + Vector((-2.2, -1.6, -1.6)), c, 30),
         'below': (c + Vector((0.0, -0.4, -3.6)), c, 30),
         'below_out': (c + Vector((1.6, -0.6, -2.4)), c, 30)}
for m in maps:
    p = os.path.join(tdir, f'{prefix}_{m}.png')
    img.image = bpy.data.images.load(p, check_existing=True)
    img.image.colorspace_settings.name = 'sRGB' if m.endswith('_b') else 'Non-Color'
    for vn, (loc, tgt, lens) in VIEWS.items():
        cam.location = loc
        cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        sc.render.filepath = os.path.join(out, f'{prefix}_nac_{m}_{vn}.png')
        bpy.ops.render.render(write_still=True)
print('[nacdiag] done')
