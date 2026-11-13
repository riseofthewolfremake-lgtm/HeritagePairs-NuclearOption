"""Renders of the GA-25X model (workbench, material colours, backface culling on as in Unity).

  blender --background --factory-startup --python blender/ga25x/render_ga25x.py -- <ga25x.blend> <outdir> [shot ...]

Store shapes in the 'pylons_loaded' shot are PROXIES drawn here from the stock mount dimensions measured for the design
doc (cylinders/boxes only); no game geometry is used or saved.
"""
import bpy, sys, os, math, json
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
blend, out = os.path.abspath(argv[0]), os.path.abspath(argv[1])
only = set(argv[2:])
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
scene.render.resolution_percentage = 70
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scene.collection.objects.link(cam)
scene.camera = cam
O = bpy.data.objects
for o in O:
    if o.users_collection and o.users_collection[0].name == 'GA25X_extras':
        o.hide_render = True
C = O['GA25X_root'].matrix_world.translation


def look(loc, target, lens=50):
    loc, target = Vector(loc), Vector(target)
    cam.location = loc
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = (target - loc).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def descendants(o):
    r = [o]
    for c in o.children:
        r += descendants(c)
    return r


def proxy(name, center, length, radius, mat='metal_dark'):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=length, location=center, rotation=(math.pi / 2, 0, 0))
    ob = bpy.context.active_object
    ob.name = 'proxy_' + name
    ob.data.materials.append(bpy.data.materials.get(mat))
    return ob


def shot(name, loc, target, lens=50, hide=(), show_only=None, setup=None):
    if only and name not in only:
        return
    hidden = []
    for o in O:
        if o.type != 'MESH':
            continue
        h = o.name in hide or (show_only is not None and o.name not in show_only)
        if h and not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    extra = setup() if setup else []
    look(loc, target, lens)
    scene.render.filepath = os.path.join(out, name + '.png')
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    for o in extra:
        bpy.data.objects.remove(o)
    print('[render]', name)


def pylon_loads():
    res = []
    for L, s in (('L', -1), ('R', 1)):
        hi = O[f'hp_inner_{L}'].matrix_world.translation
        ho = O[f'hp_outer_{L}'].matrix_world.translation
        res.append(proxy(f'agm68_{L}', hi + Vector((0, 0.1, -0.30)), 3.4, 0.17))                  # AGM-68 (proxy)
        for k in (-1, 0, 1):                                                                        # AGM-48 x3 (proxy)
            res.append(proxy(f'agm48_{L}{k}', ho + Vector((k * 0.24, 0.0, -0.25 - (0.12 if k == 0 else 0))), 1.9, 0.09))
    return res


canopy = [o.name for o in O if o.name.startswith(('canopy_', 'hatch_cockpit_top'))]
# visual pass close-ups (pylons_loaded / pylons_front come from check_stores_ga25x.py with the worst-case proxy loads)
shot('ext_front34', C + Vector((-14, 16, 5)), C + Vector((0, 0.5, 0)), 35)
shot('ext_rear34', C + Vector((15, -17, 7)), C + Vector((0, -1, 0)), 35)
shot('ext_side', C + Vector((-30, 0, 0.5)), C + Vector((0, -1.8, 0.3)), 50)
shot('ext_top', C + Vector((0, -1.5, 40)), C + Vector((0, -1.5, 0)), 45)
shot('ext_front', C + Vector((0, 30, 0.4)), C + Vector((0, 0, 0.4)), 55)
shot('nose_chin', C + Vector((-3.2, 9.5, -1.0)), C + Vector((0, 5.4, -0.3)), 45)
shot('nacelle_prop6', C + Vector((-6.8, 6.6, 0.6)), C + Vector((-2.95, 2.4, 0.0)), 45)
shot('laser_turret', C + Vector((-2.6, 4.2, 3.2)), C + Vector((0, 1.82, 1.5)), 45)
shot('tailcone_hook', C + Vector((3.2, -13.5, -1.2)), C + Vector((0, -8.6, 0.0)), 45)
shot('cockpit', C + Vector((0.0, 2.4, 2.4)), C + Vector((0, 3.9, 0.7)), 26, hide=canopy + ['fus_cockpit', 'fus_forward', 'fus_nose'])
shot('gear_hook_under', C + Vector((-9, -4, -6.5)), C + Vector((0, -1.5, -1.0)), 30)

E = O['cockpit_eye'].matrix_world.translation
shot('canopy_gold', C + Vector((-3.6, 6.6, 2.4)), C + Vector((0, 3.4, 1.15)), 50)
shot('canopy_side', C + Vector((-6.5, 3.2, 1.4)), C + Vector((0, 3.4, 1.05)), 60)
shot('cockpit_pilot_eye', E + Vector((0.0, -0.05, 0.02)), E + Vector((0.12, 1.0, -0.40)), 16)
shot('cockpit_wso_eye', O['crew_wso_eye'].matrix_world.translation + Vector((0, -0.05, 0.02)),
     O['crew_wso_eye'].matrix_world.translation + Vector((-0.30, 1.0, -0.45)), 16)
shot('nacelle_side', C + Vector((-9.5, 1.2, 0.3)), C + Vector((-2.95, 0.6, 0.0)), 50)
shot('nacelle_front34', C + Vector((-5.8, 7.4, -0.9)), C + Vector((-2.95, 2.1, -0.1)), 45)
shot('laser_closeup', C + Vector((-1.7, 3.3, 2.5)), C + Vector((0, 1.82, 1.45)), 55)
shot('waist_panel', C + Vector((-4.6, -1.6, 1.5)), C + Vector((-0.7, -3.4, 0.0)), 45)
shot('tailcone_closeup', C + Vector((-1.9, -12.0, 0.2)), C + Vector((0, -9.8, 0.35)), 50)
shot('nose_top', C + Vector((-2.4, 8.4, 2.6)), C + Vector((0, 5.2, 0.4)), 45)
