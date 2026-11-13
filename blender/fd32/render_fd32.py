"""Quick review renders of the FD-32 model (workbench, material colours; or the livery atlas with --tex).

  blender --background assets/model_fd32/fd32.blend --python blender/fd32/render_fd32.py -- --out <folder> [--tex assets/textures_fd32 --livery bdf_mattegrey]
           [--views front3q,side,top,below,rear3q,cockpit,nose,canopy]
Output: <out>/fd32_<view>.png (renders are review material: they go to nuclearoption-ref, not git, unless picked for media/).
"""
import bpy, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1])
TEX = os.path.abspath(argv[argv.index('--tex') + 1]) if '--tex' in argv else None
LIV = argv[argv.index('--livery') + 1] if '--livery' in argv else 'bdf_mattegrey'
VIEWS = argv[argv.index('--views') + 1].split(',') if '--views' in argv else ['front3q', 'side', 'top', 'below', 'rear3q', 'cockpit', 'nose']
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
C = bpy.data.objects['FD32_root'].matrix_world.translation.copy()

if TEX:
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
    def img(path):
        return bpy.data.images.load(path, check_existing=True) if os.path.exists(path) else None
    for m in bpy.data.materials:
        n = m.name
        path = None; uvl = None
        if n == 'paint':
            path = os.path.join(TEX, f'fd32_livery_{LIV}.png'); uvl = 'livery'
        elif n.startswith('pr_'):
            path = os.path.join(TEX, f'fd32_{n}_b.png'); uvl = 'livery'
        elif os.path.exists(os.path.join(TEX, f'fd32_tile_{n}_b.png')):
            path = os.path.join(TEX, f'fd32_tile_{n}_b.png'); uvl = 'detail'
        im = img(path) if path else None
        if im is None or not m.use_nodes:
            continue
        nt = m.node_tree
        bs = next((x for x in nt.nodes if x.type == 'BSDF_PRINCIPLED'), None)
        if bs is None:
            continue
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = im
        uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = uvl
        nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
        nt.links.new(t.outputs['Color'], bs.inputs['Base Color'])
    world = bpy.data.worlds.new('w') if not sc.world else sc.world
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.55, 0.60, 0.68, 1); bg.inputs['Strength'].default_value = 1.0
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 3.5
    so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
else:
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'MATERIAL'
    sc.display.shading.show_cavity = True
    sc.display.shading.show_backface_culling = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
cam_d = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
VIEW = {'front3q': ((7.5, 7.5, 3.0), (0, 0, 0), 32), 'side': ((12, 0.0, 0.3), (0, -0.9, 0), 40), 'top': ((0, -0.9, 14), (0, -0.9, 0), 42),
        'below': ((0.01, -0.5, -11), (0, -0.5, 0), 42), 'rear3q': ((-7, -9, 3.5), (0, -1, 0), 34), 'nose': ((2.2, 5.0, -0.8), (0, 1.2, -0.3), 40),
        'canopy': ((2.2, 1.0, 2.2), (0, -0.8, 0.7), 45), 'cockpit': (None, None, 80)}
for v in VIEWS:
    pos, tgt, fov = VIEW[v]
    if v == 'cockpit':
        eye = bpy.data.objects['cockpit_eye'].matrix_world.translation
        cam.location = eye; d = Vector((0, 1, -0.35))
    else:
        cam.location = Vector(pos) + Vector((0, 0, 0)); d = Vector(tgt) - Vector(pos)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam_d.angle = math.radians(fov); cam_d.clip_start = 0.05
    sc.render.filepath = os.path.join(OUT, f'fd32_{v}{"_" + LIV if TEX else ""}.png')
    bpy.ops.render.render(write_still=True)
    print('[render]', sc.render.filepath)
