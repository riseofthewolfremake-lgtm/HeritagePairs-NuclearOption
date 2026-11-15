"""1.9.12 review renders of Mk I liveries: nine views per livery (left, right, top, below, front, front 3/4 and rear 3/4 from both sides).

  blender --background assets/model_nimrod/nimrod.blend --python-exit-code 1 --python blender/nimrod/render_naval1912.py -- <out_dir> [--keys bdf_navy,pala_navy] [--res 1100] [--tex assets/textures_nimrod] [--closeups]

Same idea as blender/render_atlas_compare1816.py (paint faces show the livery PNG on the `livery` UV, everything else flat grey, fixed
lights), plus an underside view, three-quarter views from both sides and, with --closeups, perspective close-ups of the rear fuselage / tail from
each side (title + rudder number; `tailbeam_*` exactly on the beam: wires and rudder post against the digits), the mid fuselage and the nose. Writes <out_dir>/<key>_<view>.png. Changes nothing in the .blend on disk.
"""
import bpy, sys, os, math
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(argv[0])
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
TEX = os.path.abspath(argv[argv.index('--tex') + 1]) if '--tex' in argv else os.path.join(ROOT, 'assets', 'textures_nimrod')
KEYS = argv[argv.index('--keys') + 1].split(',') if '--keys' in argv else ['bdf_navy', 'pala_navy']
RES = int(argv[argv.index('--res') + 1]) if '--res' in argv else 1100
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene

img_node = None
grey = bpy.data.materials.new('cmp_grey'); grey.use_nodes = True
grey.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.30, 0.30, 0.30, 1)
for m in list(bpy.data.materials):
    if m is not grey and m.name == 'paint':
        m.use_nodes = True
        nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial'); bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
        bs.inputs['Roughness'].default_value = 0.6
        uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'livery'
        img_node = nt.nodes.new('ShaderNodeTexImage'); img_node.interpolation = 'Linear'
        nt.links.new(uv.outputs['UV'], img_node.inputs['Vector'])
        nt.links.new(img_node.outputs['Color'], bs.inputs['Base Color'])
        nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
assert img_node is not None, 'no paint material'
for o in bpy.data.objects:
    if o.type == 'MESH':
        for s in o.material_slots:
            if s.material is None or s.material.name != 'paint':
                s.material = grey
        if o.name.endswith('_hullsrc') or o.name.startswith(('collider', 'col_')):
            o.hide_render = True
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render and o.visible_get()]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
C = (lo + hi) / 2; D = hi - lo; R = D.length / 2

sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x = RES; sc.render.resolution_y = int(RES * 0.66)
sc.render.film_transparent = False
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
sc.view_settings.view_transform = 'Standard'
try:
    sc.eevee.taa_render_samples = 16
except Exception:
    pass
w = bpy.data.worlds.new('cmp_world'); w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.57, 0.6, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
sc.world = w
for o in [o for o in bpy.data.objects if o.type == 'LIGHT']:
    o.hide_render = True
for rot, e in (((math.radians(50), 0, math.radians(30)), 2.4), ((math.radians(-120), 0, math.radians(-150)), 1.0)):
    ld = bpy.data.lights.new('cmp_sun', 'SUN'); ld.energy = e
    lo_ = bpy.data.objects.new('cmp_sun', ld); lo_.rotation_euler = rot; sc.collection.objects.link(lo_)
cam_d = bpy.data.cameras.new('cmp_cam'); cam = bpy.data.objects.new('cmp_cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
aspect = sc.render.resolution_x / sc.render.resolution_y


def look(pos, target, up='Y'):
    cam.location = pos
    cam.rotation_euler = (target - pos).to_track_quat('-Z', up).to_euler()


def ortho(d, ext, roll_top=None):
    cam_d.type = 'ORTHO'; cam_d.ortho_scale = max(ext[0], ext[1] * aspect) * 1.06
    cam.location = C + d * R * 3
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    if roll_top == 'top':
        cam.rotation_euler = (0, 0, math.radians(-90))            # nose to the right
    elif roll_top == 'below':
        cam.rotation_euler = (math.radians(180), 0, math.radians(-90))


def persp(d, dist=2.05, target=None, lens=50):
    cam_d.type = 'PERSP'; cam_d.lens = lens
    t = target if target is not None else C
    look(t + d.normalized() * R * dist, t)


VIEWS = [('left', lambda: ortho(Vector((-1, 0, 0)), (D.y, D.z))), ('right', lambda: ortho(Vector((1, 0, 0)), (D.y, D.z))),
         ('top', lambda: ortho(Vector((0, 0, 1)), (D.y, D.x), 'top')), ('below', lambda: ortho(Vector((0, 0, -1)), (D.y, D.x), 'below')),
         ('front3q', lambda: persp(Vector((-0.75, 0.9, 0.55)))), ('rear3q', lambda: persp(Vector((0.8, -0.9, 0.45)))),
         ('front3q_r', lambda: persp(Vector((0.75, 0.9, 0.55)))), ('rear3q_l', lambda: persp(Vector((-0.8, -0.9, 0.45)))),
         ('front', lambda: persp(Vector((0.0, 1.0, 0.12)), 1.75))]
if '--closeups' in argv:
    tail = Vector((0, -4.05, 0.40))
    VIEWS += [('tail_left', lambda: persp(Vector((-1, -0.30, 0.12)), 0.80, tail, 60)), ('tail_right', lambda: persp(Vector((1, -0.30, 0.12)), 0.80, tail, 60)),
              ('mid_left', lambda: persp(Vector((-1, 0.25, 0.45)), 0.9, Vector((0, -1.2, 0.2)), 60)),
              # round 2: the tail exactly on the beam from each side (bracing wires / rudder post against the number), and a nose close-up
              ('tailbeam_left', lambda: persp(Vector((-1, 0, 0)), 0.50, Vector((0, -4.3, 0.55)), 60)),
              ('tailbeam_right', lambda: persp(Vector((1, 0, 0)), 0.50, Vector((0, -4.3, 0.55)), 60)),
              ('nose_right', lambda: persp(Vector((1, 0.35, 0.40)), 0.8, Vector((0, 1.0, 0.1)), 60))]
cam_d.clip_end = R * 10
for key in KEYS:
    p = os.path.join(TEX, f'nimrod_livery_{key}.png')
    im = bpy.data.images.load(p, check_existing=False)
    img_node.image = im
    for name, setup in VIEWS:
        setup()
        sc.render.filepath = os.path.join(OUT, f'{key}_{name}.png')
        bpy.ops.render.render(write_still=True)
    bpy.data.images.remove(im)
    print('[render] done', key, flush=True)
