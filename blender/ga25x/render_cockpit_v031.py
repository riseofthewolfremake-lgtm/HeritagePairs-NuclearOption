"""GA-25X 0.3.1 cockpit renders WITH the stock kitbash parts previewed (stock_preview.py: the user's placeholder meshes for
the SFB-81 ejection seat, stick and throttle, read at run time; nothing saved). Canopy glass hidden.

  blender --background <ga25x.blend> --python blender/ga25x/render_cockpit_v031.py -- <out dir> [--fast]

Views: pilot eye, WSO eye, top-down into the cabin, 3/4 from above-aft, close-up of the centre pedestal / stick.
The crew FIGURES are not shown (skinned stock mesh); in game each stock seat carries its figure.
"""
import bpy, sys, os, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stock_preview as SP

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
fast = '--fast' in argv
os.makedirs(out, exist_ok=True)
O = bpy.data.objects
sc = bpy.context.scene
SP.add_cockpit_preview()

# ck_struct preview: the stock aircraft_structure base texture on the detail UV x 1.25, tinted by the stock vertex colour 56/255
m = bpy.data.materials.get('ck_struct')
p = os.path.join(SP.PH, 'Texture2D', 'aircraft_structure_b_PLACEHOLDER.png')
if m is not None and os.path.exists(p):
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(p, check_existing=True)
    uv = nt.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'detail'
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.25, 1.25, 1.0)
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1.0
    c = 56 / 255.0
    mix.inputs[7].default_value = (c ** 2.2, c ** 2.2, c ** 2.2, 1.0)
    nt.links.new(uv.outputs['UV'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], tx.inputs['Vector'])
    nt.links.new(tx.outputs['Color'], mix.inputs[6]); nt.links.new(mix.outputs[2], bsdf.inputs['Base Color'])
# glass invisible
g = bpy.data.materials.get('glass')
if g is not None:
    g.use_nodes = True
    nt = g.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    o_ = nt.nodes.new('ShaderNodeOutputMaterial'); t_ = nt.nodes.new('ShaderNodeBsdfTransparent')
    nt.links.new(t_.outputs[0], o_.inputs[0])
    try:
        g.surface_render_method = 'BLENDED'
    except Exception:
        pass
for o in O:
    if o.users_collection and o.users_collection[0].name == 'GA25X_extras':
        o.hide_render = True
    if o.name.startswith(('canopy_glass',)):
        o.hide_render = True
# screens: a dim blue-grey so the display areas read (in game: tac screen / target camera)
for nm, col in (('screen', (0.004, 0.006, 0.009)),):
    sm = bpy.data.materials.get(nm)
    if sm and sm.node_tree and sm.node_tree.nodes.get('Principled BSDF'):
        sm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*col, 1)
for nm in ('mfd_center', 'mfd_right'):
    o = O.get(nm)
    if o:
        mm = bpy.data.materials.new(nm + '_preview'); mm.use_nodes = True
        b = mm.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (0.02, 0.05, 0.04, 1)
        b.inputs['Emission Color'].default_value = (0.05, 0.16, 0.10, 1); b.inputs['Emission Strength'].default_value = 1.0
        o.data.materials.clear(); o.data.materials.append(mm)

sc.render.engine = 'BLENDER_EEVEE' if not fast else 'BLENDER_WORKBENCH'
if sc.render.engine == 'BLENDER_WORKBENCH':
    sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'; sc.display.shading.show_cavity = True
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
w = bpy.data.worlds.new('w') if sc.world is None else sc.world
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.55, 0.62, 0.72, 1); bg.inputs['Strength'].default_value = 1.2
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(35), math.radians(-20), math.radians(30))
sc.collection.objects.link(sun)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_start = 0.02


def shot(name, pos, tgt, lens=16, hide=()):
    hidden = []
    for o in O:
        if o.name.startswith(hide) and not o.hide_render:
            o.hide_render = True; hidden.append(o)
    cam.location = Vector(pos)
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    sc.render.filepath = os.path.join(out, name + '.png')
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    print('[render]', sc.render.filepath)


pe = O['cockpit_eye'].matrix_world.translation
we = O['crew_wso_eye'].matrix_world.translation
shot('pilot_eye', pe, pe + Vector((0.05, 1.0, -0.33)), 16)
shot('wso_eye', we, we + Vector((-0.05, 1.0, -0.33)), 16)
shot('pilot_eye_down', pe, pe + Vector((0.12, 0.8, -0.75)), 16)
shot('top_down', (0.0, 3.45, 2.6), (0.0, 3.46, 0.0), 18, hide=('canopy_', 'fus_cockpit', 'fus_forward', 'gunsight_combiner'))
shot('three_quarter', (0.95, 2.55, 1.75), (0.0, 3.75, 0.45), 20, hide=('canopy_', 'wing_', 'nacelle_', 'engine_', 'prop_', 'aileron_', 'flap_'))
shot('pedestal_close', (0.32, 3.55, 0.85), (0.0, 4.05, 0.30), 22, hide=('canopy_',))
