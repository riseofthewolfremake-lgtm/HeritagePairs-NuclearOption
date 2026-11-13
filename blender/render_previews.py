"""Render preview PNGs of the B-25H model.

  blender --background assets/model/b25h.blend --python blender/render_previews.py -- --outdir assets/model [--views a,b]
"""
import bpy, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
outdir = argv[argv.index('--outdir') + 1] if '--outdir' in argv else '.'
only = argv[argv.index('--views') + 1].split(',') if '--views' in argv else None
res = int(argv[argv.index('--res') + 1]) if '--res' in argv else 1280

sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'MATERIAL'
sc.display.shading.show_cavity = True
sc.display.shading.cavity_type = 'BOTH'
sc.display.shading.show_object_outline = False
sc.display.shading.show_specular_highlight = True
sc.render.resolution_x = res
sc.render.resolution_y = int(res * 0.5625)
sc.render.film_transparent = False
sc.render.image_settings.file_format = 'PNG'
world = sc.world or bpy.data.worlds.new('World')
sc.world = world
world.color = (0.72, 0.78, 0.85)
sc.display.shading.background_type = 'WORLD' if hasattr(sc.display.shading, 'background_type') else None

cam_data = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam

# ground reference plane at the wheel contact level
gz = -bpy.data.objects['B25H_root'].get('ground_offset', 2.45)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, gz))
plane = bpy.context.active_object
pm = bpy.data.materials.new('ground_preview')
pm.diffuse_color = (0.55, 0.55, 0.52, 1)
plane.data.materials.append(pm)

VIEWS = {
    # name: (location, target, ortho_scale or None, lens)
    'threequarter': (Vector((-17, 19, 7.5)), Vector((0, 0, -0.3)), None, 40),
    'side': (Vector((-40, -1.5, 0.2)), Vector((0, -1.5, 0.2)), 17.0, None),
    'top': (Vector((0, -1.5, 40)), Vector((0, -1.5, 0)), 22.0, None),
    'front': (Vector((0, 40, 0.2)), Vector((0, 0, 0.2)), 22.5, None),
    'rear34': (Vector((14, -18, 6)), Vector((0, -1.5, 0)), None, 40),
    'closeup_nose': (Vector((-5, 11, 1.2)), Vector((0, 4.5, -0.2)), None, 40),
}
for name, (loc, tgt, ortho, lens) in VIEWS.items():
    if only and name not in only:
        continue
    cam.location = loc
    d = (tgt - loc)
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    if name == 'top':   # straight down, nose up in the image (frame is made taller below)
        from mathutils import Euler
        cam.rotation_quaternion = Euler((0, 0, 0)).to_quaternion()
    sc.render.resolution_y = int(res * (0.8 if name == 'top' else 0.5625))
    if ortho:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = ortho
        plane.hide_render = name in ('top',)
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = lens
        plane.hide_render = False
    if name == 'top':
        plane.hide_render = True
    cam_data.clip_end = 200
    sc.render.filepath = os.path.join(os.path.abspath(outdir), f'preview_{name}.png')
    bpy.ops.render.render(write_still=True)
    print('[render]', sc.render.filepath)
