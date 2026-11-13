"""Bake geometry maps of the B-25H v2 model into its `livery` UV atlas (paint faces only).

  blender --background <b25h_v2.blend> --python blender/v2/textures/bake_maps.py -- <cache_dir> [--res 4096] [--ao-samples 256] [--cpu] [--skip pos,nrm,oid,ao]

Writes into <cache_dir> (float OpenEXR, linear):
  pos.exr     world position (Blender metres, x right, y forward, z up); alpha = 1 where a paint texel exists
  nrm.exr     smooth world normal
  oid.exr     R = object pass index; objects.json maps index -> object name and world matrix
  ao.exr      ambient occlusion (gear, props and glazing removed, gear doors closed = flight pose)
The working copy is never saved; the .blend is untouched.
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index('--') + 1:]
cache = os.path.abspath(argv[0])
RES = int(argv[argv.index('--res') + 1]) if '--res' in argv else 4096
AO_SAMPLES = int(argv[argv.index('--ao-samples') + 1]) if '--ao-samples' in argv else 256
os.makedirs(cache, exist_ok=True)
scene = bpy.context.scene
O = bpy.data.objects
# 1.8.16 guard: the atlas this cache is baked on (before the flight-pose edits below); the texture drivers put it in the manifest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')))
import atlas_guard as AG
_parts = AG.scene_parts()
with open(os.path.join(cache, 'atlas.json'), 'w') as f:
    json.dump(dict(model=bpy.data.filepath, atlas_hash=AG.atlas_hash(_parts), parts=_parts), f, indent=0)
print('[bake] atlas', AG.atlas_hash(_parts), len(_parts), 'paint parts')


def info(o):
    s = o.get('b25_info')
    return json.loads(s) if s else {}


# ------------------------------------------------------------------ flight pose: close gear doors
def close_door(o):
    """Rotate a door from its open file pose back into its hull opening: the inverse of the open pose. By construction
    (b25h_parts.door_from_holes / open_pose, build scripts) the pivot lies on the hinge, hinge_axis is a world axis and
    open_deg is the SIGNED opening angle about it, so closed = rotation by -open_deg about hinge_axis through the pivot.
    v0.3.2 fix: the old rule tried both senses and kept the one with the highest lowest point; that is the 190 deg
    over-rotated pose (door folded up through the nacelle), so the AO / normal / position texels of every gear door were
    baked from a door lying inside the nacelle: the dark, polygon-blocky patch under the nacelles in game (all liveries,
    both aircraft; diagnosis renders media/ga25x_v032_cockpit/nacelle_*)."""
    inf = info(o)
    ax = Vector(inf['hinge_axis']).normalized()
    ang = math.radians(inf['open_deg'])
    p = o.matrix_world.translation.copy()
    o.matrix_world = Matrix.Translation(p) @ Matrix.Rotation(-ang, 4, ax) @ Matrix.Translation(-p) @ o.matrix_world
    print(f'[bake] close {o.name}: {-inf["open_deg"]:+.1f} deg about the hinge, lowest point z '
          f'{min((o.matrix_world @ v.co).z for v in o.data.vertices):.3f}')


for o in list(O):
    if o.name.startswith('gear_door_'):
        close_door(o)
bpy.context.view_layer.update()

# ------------------------------------------------------------------ remove non-flight occluders
kill = [o for o in O if o.name.startswith(('gear_main_', 'gear_nose_', 'prop_', 'canopy_glass'))]
for o in kill:
    bpy.data.objects.remove(o, do_unlink=True)
for o in O:
    if o.type != 'MESH':
        continue
    me = o.data
    gi = [i for i, m in enumerate(me.materials) if m and m.name == 'glass']
    if gi:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in gi], context='FACES')
        bm.to_mesh(me)
        bm.free()

meshes = [o for o in O if o.type == 'MESH' and len(o.data.polygons)]
objects = {}
for i, o in enumerate(sorted(meshes, key=lambda o: o.name)):
    o.pass_index = i + 1
    objects[i + 1] = dict(name=o.name, matrix_world=[list(r) for r in o.matrix_world])
with open(os.path.join(cache, 'objects.json'), 'w') as f:
    json.dump(objects, f, indent=0)
# exhaust stub outlets: per nacelle, the aft-most vertex of each angular cluster (angle about nacelle axis)
exh = {}
for o in O:
    if not o.name.startswith('exhaust_') or o.type != 'MESH':
        continue
    side = o.name[-1]
    cx = o.matrix_world.translation.x
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    zc = sum(p.z for p in pts) / len(pts)
    bins = {}
    for p in pts:
        a = round(math.degrees(math.atan2(p.x - cx, p.z - (-0.0))) / 15.0)
        if a not in bins or p.y < bins[a].y:
            bins[a] = p
    exh[side] = [list(p) for p in bins.values()]
with open(os.path.join(cache, 'exhaust.json'), 'w') as f:
    json.dump(exh, f)

# ------------------------------------------------------------------ bake setup
scene.render.engine = 'CYCLES'
cp = bpy.context.preferences.addons['cycles'].preferences
use_gpu = '--cpu' not in argv
if use_gpu:
    try:
        cp.compute_device_type = 'OPTIX'
        cp.get_devices()
        for d in cp.devices:
            d.use = d.type == 'OPTIX'
        scene.cycles.device = 'GPU'
    except Exception as e:
        print('GPU unavailable, CPU bake', e)
        scene.cycles.device = 'CPU'
scene.cycles.use_denoising = False
scene.render.bake.use_selected_to_active = False
scene.render.bake.use_clear = True
if not scene.world:
    scene.world = bpy.data.worlds.new('w')


def new_img(name, res=RES):
    im = bpy.data.images.new(name, res, res, alpha=True, float_buffer=True)
    im.colorspace_settings.name = 'Non-Color'
    im.generated_color = (0, 0, 0, 0)
    return im


dummy = bpy.data.images.new('_dummy', 8, 8, float_buffer=True)


def bake_mat(name, target, mode):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 1.0
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    if mode == 'pos':
        nt.links.new(geo.outputs['Position'], em.inputs['Color'])
    elif mode == 'nrm':
        nt.links.new(geo.outputs['Normal'], em.inputs['Color'])
    elif mode == 'oid':
        oi = nt.nodes.new('ShaderNodeObjectInfo')
        cx = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(oi.outputs['Object Index'], cx.inputs['X'])
        nt.links.new(cx.outputs['Vector'], em.inputs['Color'])
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = target
    nt.nodes.active = tex
    return m


orig_slots = {o.name: [s.material.name if s.material else '' for s in o.material_slots] for o in meshes}


def assign(target, mode):
    mp = bake_mat('_bk_paint_' + mode, target, mode)
    mo = bake_mat('_bk_other_' + mode, dummy, mode)
    for o in meshes:
        for k, s in enumerate(o.material_slots):
            s.material = mp if orig_slots[o.name][k] == 'paint' else mo
        o.data.uv_layers.active = o.data.uv_layers['livery']


def select_all():
    for o in O:
        o.select_set(False)
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]


def save_exr(im, name):
    p = os.path.join(cache, name)
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    scene.render.image_settings.exr_codec = 'ZIP'
    im.save_render(p, scene=scene)
    print('[bake] wrote', p)


def bake(kind, mode, margin, fname, samples=1):
    im = new_img(fname)
    assign(im, mode)
    select_all()
    scene.cycles.samples = samples
    scene.render.bake.margin = margin
    scene.render.bake.margin_type = 'EXTEND'
    if kind == 'AO':
        bpy.ops.object.bake(type='AO', margin=margin, use_clear=True)
    else:
        bpy.ops.object.bake(type='EMIT', margin=margin, use_clear=True)
    save_exr(im, fname)


scene.view_settings.view_transform = 'Standard'
scene.display_settings.display_device = 'sRGB'
# margin 0 everywhere: with several objects sharing one image Cycles applies the margin per object,
# so one object's margin overwrites neighbouring islands of other objects. Dilation is done in numpy.
skip = set(argv[argv.index('--skip') + 1].split(',')) if '--skip' in argv else set()
for mode in ('pos', 'nrm', 'oid'):
    if mode not in skip:
        bake('EMIT', mode, 0, mode + '.exr')
scene.world.light_settings.distance = 2.5
if 'ao' not in skip:
    bake('AO', 'pos', 0, 'ao.exr', samples=AO_SAMPLES)
print('[bake] done')
