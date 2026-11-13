"""Preview renders of the GA-25X liveries on the model (workbench, texture colour on the `livery` UVs).

  blender --background assets/model_ga25x/ga25x.blend --python blender/ga25x/textures/render_liveries_ga25x.py -- <textures_dir> <out_dir>
"""
import bpy, sys, os, json
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
tdir, out = os.path.abspath(argv[0]), os.path.abspath(argv[1])
os.makedirs(out, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.show_backface_culling = True
sh.background_type = 'VIEWPORT'
sh.background_color = (0.55, 0.6, 0.65)
scene.render.resolution_x, scene.render.resolution_y = 1400, 900
scene.render.resolution_percentage = 60
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
O = bpy.data.objects
for o in O:
    if o.users_collection and o.users_collection[0].name == 'GA25X_extras':
        o.hide_render = True
C = O['GA25X_root'].matrix_world.translation
mat = bpy.data.materials['paint']
nt = mat.node_tree
img_node = nt.nodes.new('ShaderNodeTexImage')
nt.nodes.active = img_node
bsdf = nt.nodes.get('Principled BSDF')
nt.links.new(img_node.outputs['Color'], bsdf.inputs['Base Color'])


def look(loc, target, lens):
    cam.location = Vector(loc)
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


meta = json.load(open(os.path.join(tdir, 'ga25x_liveries.json')))
for key, e in meta.items():
    img = bpy.data.images.load(os.path.join(tdir, e['texture']), check_existing=True)
    img_node.image = img
    for shot, loc, tgt, lens in (('34', C + Vector((-15, 15, 6)), C + Vector((0, 0, 0)), 35),
                                 ('top', C + Vector((0, -1.5, 40)), C + Vector((0, -1.5, 0)), 45),
                                 ('side', C + Vector((30, -1.0, 0.5)), C + Vector((0, -1.8, 0.3)), 50),
                                 ('close', C + Vector((-6.5, 9.0, 2.2)), C + Vector((-0.4, 2.6, 0.3)), 40),
                                 ('rear_close', C + Vector((6.5, -9.5, 1.8)), C + Vector((0.3, -4.5, 0.4)), 40)):
        look(loc, tgt, lens)
        scene.render.resolution_percentage = 90 if 'close' in shot else 60
        scene.render.filepath = os.path.join(out, f'livery_{key}_{shot}.png')
        bpy.ops.render.render(write_still=True)
    print('[livery preview]', key)
