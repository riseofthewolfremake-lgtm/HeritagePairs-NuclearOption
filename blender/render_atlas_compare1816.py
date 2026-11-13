"""1.8.16 re-bake proof: render a model with each of its livery textures from six fixed cameras (same light for every build).

  blender --background <model.blend> --python-exit-code 1 --python blender/render_atlas_compare1816.py -- <tex_dir> <prefix> <out_dir> [--res 720]

For every <tex_dir>/<prefix>_livery_*.png: the `paint` faces show that texture on the `livery` UV (Principled, roughness 0.55, no
normal / AO maps so only the colour layout is compared); every other material is a flat mid grey. Cameras from the model's bounding
box: front, rear, left, right, top (orthographic) and a front-left three-quarter view (perspective). Writes <out_dir>/<livery>_<view>.png.
Run it on the 1.8.12 model + 1.8.12 textures and on the current model + re-baked textures, then tools/compose_atlas_compare1816.py.
"""
import bpy, sys, os, glob, math
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
TEX, PREFIX, OUT = os.path.abspath(argv[0]), argv[1], os.path.abspath(argv[2])
RES = int(argv[argv.index('--res') + 1]) if '--res' in argv else 720
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene

# ------------------------------------------------------------------ materials
img_node = None
grey = bpy.data.materials.new('cmp_grey')
grey.use_nodes = True
grey.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.35, 0.35, 0.35, 1)
for m in list(bpy.data.materials):
    if m is grey:
        continue
    if m.name == 'paint':
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
        bs.inputs['Roughness'].default_value = 0.55
        uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'livery'
        img_node = nt.nodes.new('ShaderNodeTexImage'); img_node.interpolation = 'Linear'
        nt.links.new(uv.outputs['UV'], img_node.inputs['Vector'])
        nt.links.new(img_node.outputs['Color'], bs.inputs['Base Color'])
        nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
for o in bpy.data.objects:
    if o.type == 'MESH':
        for i, s in enumerate(o.material_slots):
            if s.material is None or s.material.name != 'paint':
                s.material = grey
assert img_node is not None, 'no paint material'

# ------------------------------------------------------------------ hide helpers, frame
for o in bpy.data.objects:
    if o.type not in ('MESH',) or o.hide_render:
        continue
    if o.name.endswith('_hullsrc') or o.name.startswith(('collider', 'col_')):
        o.hide_render = True
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render and o.visible_get()]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
C = (lo + hi) / 2; D = hi - lo; R = D.length / 2
print('[cmp] bbox', tuple(round(v, 2) for v in lo), tuple(round(v, 2) for v in hi))

sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x = RES; sc.render.resolution_y = int(RES * 0.66)
sc.render.film_transparent = True
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'Standard'
try:
    sc.eevee.taa_render_samples = 16
except Exception:
    pass
w = bpy.data.worlds.new('cmp_world'); w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.57, 0.6, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.9
sc.world = w
for o in [o for o in bpy.data.objects if o.type == 'LIGHT']:
    o.hide_render = True
for rot, e in (((math.radians(50), 0, math.radians(30)), 2.6), ((math.radians(-120), 0, math.radians(-150)), 0.8)):
    ld = bpy.data.lights.new('cmp_sun', 'SUN'); ld.energy = e
    lo_ = bpy.data.objects.new('cmp_sun', ld); lo_.rotation_euler = rot; sc.collection.objects.link(lo_)

cam_d = bpy.data.cameras.new('cmp_cam'); cam = bpy.data.objects.new('cmp_cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam


def look(pos, target):
    cam.location = pos
    cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()


aspect = sc.render.resolution_x / sc.render.resolution_y
VIEWS = [  # name, direction from the centre (Blender: x right, y forward, z up), ortho half-extents (horizontal, vertical)
    ('front', Vector((0, 1, 0)), (D.x, D.z)), ('rear', Vector((0, -1, 0)), (D.x, D.z)),
    ('left', Vector((-1, 0, 0)), (D.y, D.z)), ('right', Vector((1, 0, 0)), (D.y, D.z)),
    ('top', Vector((0, 0, 1)), (D.x, D.y)), ('threequarter', Vector((-0.75, 0.9, 0.55)).normalized(), None)]


def frame(view):
    name, d, ext = view
    if ext is None:
        cam_d.type = 'PERSP'; cam_d.lens = 50
        look(C + d * R * 2.05, C)
    else:
        cam_d.type = 'ORTHO'
        cam_d.ortho_scale = max(ext[0], ext[1] * aspect) * 1.08
        up = Vector((0, 1, 0)) if name == 'top' else Vector((0, 0, 1))
        cam.location = C + d * R * 3
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y' if name != 'top' else 'Y').to_euler()
        if name == 'top':     # nose up in the picture
            cam.rotation_euler = (0, 0, 0)
    cam_d.clip_end = R * 10


livs = sorted(glob.glob(os.path.join(TEX, PREFIX + '_livery_*.png')))
print('[cmp] liveries', [os.path.basename(p) for p in livs])
for p in livs:
    key = os.path.basename(p)[len(PREFIX) + 8:-4]
    im = bpy.data.images.load(p, check_existing=False)
    img_node.image = im
    for v in VIEWS:
        frame(v)
        sc.render.filepath = os.path.join(OUT, f'{key}_{v[0]}.png')
        bpy.ops.render.render(write_still=True)
    bpy.data.images.remove(im)
    print('[cmp] done', key, flush=True)
