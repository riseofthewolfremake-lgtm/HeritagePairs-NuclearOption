"""Before/after close-ups for the GA-25X 0.3.0 model pass (workbench, material colours, backface culling as in Unity).

  blender --background --factory-startup --python blender/ga25x/render_v030.py -- <ga25x.blend> <outdir> <prefix> [shot ...]

Writes <outdir>/<prefix>_<shot>.png and a half-size copy <prefix>_<shot>_small.png. Same camera for both builds, so a
'before' run on the 0.2.0 blend and an 'after' run on the 0.3.0 blend compare 1:1.
"""
import bpy, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
blend, out, prefix = os.path.abspath(argv[0]), os.path.abspath(argv[1]), argv[2]
only = set(argv[3:])
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_backface_culling = True
sh.show_shadows = False
sh.background_type = 'VIEWPORT'
sh.background_color = (0.55, 0.6, 0.65)
scene.render.resolution_x, scene.render.resolution_y = 1400, 900
scene.render.resolution_percentage = 100
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.clip_start = 0.02
O = bpy.data.objects
for o in O:
    if o.users_collection and o.users_collection[0].name == 'GA25X_extras':
        o.hide_render = True


def look(loc, target, lens=50):
    loc, target = Vector(loc), Vector(target)
    cam.location = loc
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (target - loc).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def shot(name, loc, target, lens=50, hide=()):
    if only and name not in only:
        return
    hidden = []
    for o in O:
        if o.type == 'MESH' and (o.name in hide or any(o.name.startswith(h) for h in hide if h.endswith('*') and False)) and not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    look(loc, target, lens)
    p = os.path.join(out, f'{prefix}_{name}.png')
    scene.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    img.scale(img.size[0] // 2, img.size[1] // 2)
    img.filepath_raw = p[:-4] + '_small.png'
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    for o in hidden:
        o.hide_render = False
    print('[render]', name)


names = {o.name for o in O}
canopy = [n for n in names if n.startswith(('canopy_', 'hatch_cockpit_top'))]
shell = ['fus_cockpit', 'fus_forward', 'fus_nose']
eye = O['cockpit_eye'].matrix_world.translation
wso = O['crew_wso_eye'].matrix_world.translation
# cockpit (crew eye views: canopy glass hidden, as in the game's cockpit view)
shot('cockpit_pilot_eye', eye + Vector((0, -0.05, 0.02)), eye + Vector((0.20, 1.0, -0.45)), 14, hide=[n for n in canopy if 'glass' in n])
shot('cockpit_wso_eye', wso + Vector((0, -0.05, 0.02)), wso + Vector((-0.30, 1.0, -0.45)), 14, hide=[n for n in canopy if 'glass' in n])
shot('cockpit_panel', eye + Vector((0.36, 0.25, -0.10)), Vector((0, 4.2, 0.72)), 24, hide=[n for n in canopy if 'glass' in n])
shot('cockpit_overview', Vector((0.0, 1.9, 2.6)), Vector((0, 3.6, 0.55)), 24, hide=canopy + shell)
shot('cockpit_side_cut', Vector((-3.2, 3.3, 0.9)), Vector((0, 3.45, 0.62)), 30, hide=canopy + shell)
shot('cockpit_rear_bulkhead', Vector((0.15, 3.9, 1.05)), Vector((0, 2.62, 0.55)), 16, hide=[n for n in canopy if 'glass' in n])
# exterior
shot('canopy_ext', Vector((-3.4, 6.2, 2.3)), Vector((0, 3.4, 1.1)), 45)
shot('nacelle_spinner', Vector((-4.6, 4.1, 0.15)), Vector((-2.95, 2.62, 0.0)), 60)
shot('tail_rear', Vector((0.0, -15.5, 0.5)), Vector((0, -9.6, 0.45)), 55)
shot('tail_side', Vector((-6.5, -8.8, 0.8)), Vector((0, -8.9, 0.6)), 45)
shot('tail_rear34_low', Vector((-2.4, -12.4, -0.7)), Vector((0, -9.6, 0.4)), 45)
shot('top_dorsal', Vector((-3.8, 0.6, 3.6)), Vector((0, 1.6, 1.2)), 40)
shot('belly_laser', Vector((-3.6, -4.8, -3.4)), Vector((0, -2.4, -0.9)), 40)
shot('ext_side', Vector((-28, -1.5, 0.5)), Vector((0, -1.5, 0.3)), 50)
shot('ext_front34', Vector((-13, 15, 4.5)), Vector((0, 0.5, 0.2)), 35)
shot('ext_rear34_low', Vector((12, -15, -3.5)), Vector((0, -1, 0)), 35)
shot('nose_side_low', Vector((-5.5, 4.5, -0.3)), Vector((0, 3.3, -0.1)), 40)
