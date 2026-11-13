"""B-25H cockpit rebuild renders (2026-11-01): pilot eye, navigator eye, pedestal close-up, panel, side views.

  blender --background assets/model_v2/b25h_v2.blend --python blender/v2/render_cockpit_b25h.py -- <out dir>

Materials previewed with their real textures: bk_art (b25h_ckart), bk_quilt / bk_od tiles (detail UV), pr_<name> (fal props'
baked textures), gauges (b25h_gauges). Screens: an offline stand-in picture (env SCREEN_STANDIN), NOT the game's display.
"""
import bpy, sys, os, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, '..', '..', 'assets', 'textures_v2')
out = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out, exist_ok=True)
O = bpy.data.objects
sc = bpy.context.scene


def textured(mname, base, normal=None, uvmap='livery', scale=1.0, emit=0.0):
    m = bpy.data.materials.get(mname)
    if m is None:
        return
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uvmap
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale, scale, 1)
    nt.links.new(uvn.outputs['UV'], mp.inputs['Vector'])
    tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = bpy.data.images.load(os.path.join(TEX, base), check_existing=True)
    nt.links.new(mp.outputs['Vector'], tb.inputs['Vector'])
    nt.links.new(tb.outputs['Color'], bsdf.inputs['Base Color'])
    if emit:
        nt.links.new(tb.outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = emit
    if normal and os.path.exists(os.path.join(TEX, normal)):
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(TEX, normal), check_existing=True)
        tn.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.uv_map = uvmap
        nt.links.new(mp.outputs['Vector'], tn.inputs['Vector'])
        nt.links.new(tn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])


textured('bk_art', 'b25h_ckart_b.png', 'b25h_ckart_n.png')
bl = bpy.data.materials.get('bk_black')
if bl is not None and bl.use_nodes and bl.node_tree.nodes.get('Principled BSDF'):
    bl.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.025, 0.025, 0.027, 1)
textured('bk_quilt', 'b25h_quilt_b.png', 'b25h_quilt_n.png', uvmap='detail', scale=5.0)
textured('bk_od', 'b25h_od_b.png', 'b25h_od_n.png', uvmap='detail', scale=2.0)
textured('gauges', 'b25h_gauges.png', emit=0.4)
for m in list(bpy.data.materials):
    if m.name.startswith('pr_'):
        textured(m.name, f'b25h_{m.name}_b.png', f'b25h_{m.name}_n.png')
g = bpy.data.materials.get('glass')
if g is not None:
    g.use_nodes = True
    nt = g.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    o_ = nt.nodes.new('ShaderNodeOutputMaterial'); t_ = nt.nodes.new('ShaderNodeBsdfTransparent')
    nt.links.new(t_.outputs[0], o_.inputs[0])
for o in O:
    if o.users_collection and o.users_collection[0].name.endswith('_extras'):
        o.hide_render = True
    if o.name.startswith(('canopy_glass',)):
        o.hide_render = True
sp = os.environ.get('SCREEN_STANDIN')
for nm in ('mfd_center', 'mfd_left', 'mfd_right'):
    o = O.get(nm)
    if o and sp and os.path.exists(sp):
        mm = bpy.data.materials.new(nm + '_preview'); mm.use_nodes = True
        b = mm.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (0, 0, 0, 1)
        ti = mm.node_tree.nodes.new('ShaderNodeTexImage'); ti.image = bpy.data.images.load(sp, check_existing=True)
        uvs = mm.node_tree.nodes.new('ShaderNodeUVMap'); uvs.uv_map = 'livery'
        mm.node_tree.links.new(uvs.outputs['UV'], ti.inputs['Vector'])
        mm.node_tree.links.new(ti.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 1.0
        o.data.materials.clear(); o.data.materials.append(mm)
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1600, 900
w = sc.world or bpy.data.worlds.new('w'); sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.55, 0.62, 0.72, 1); bg.inputs['Strength'].default_value = 1.2
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3.0
sun.rotation_euler = (math.radians(35), math.radians(-20), math.radians(30)); sc.collection.objects.link(sun)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
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
ne = O['crew_navigator_eye'].matrix_world.translation
shot('pilot_eye', pe, pe + Vector((0.20, 1.0, -0.40)), 14)
shot('navigator_eye', ne, ne + Vector((-0.20, 1.0, -0.40)), 14)
shot('pedestal_close', (0.30, 3.62, 0.85), (0.0, 4.05, 0.40), 20, hide=('canopy_', 'hatch_cockpit', 'cockpit_seat'))
shot('panel_front', (0.0, 3.45, 0.90), (0.0, 4.25, 0.70), 16, hide=('canopy_', 'hatch_cockpit', 'cockpit_yoke', 'cockpit_column'))
shot('three_quarter', (0.95, 2.60, 1.55), (0.0, 3.85, 0.40), 18, hide=('canopy_', 'wing_', 'nacelle_', 'engine_', 'prop_', 'hatch_cockpit', 'fus_forward'))
shot('left_wall', (0.15, 3.45, 0.95), (-0.66, 3.75, 0.62), 18, hide=('canopy_', 'hatch_cockpit', 'cockpit_seat'))
shot('footwell', (-0.12, 3.78, 0.42), (-0.40, 4.32, -0.14), 14, hide=('canopy_', 'hatch_cockpit', 'cockpit_seat', 'cockpit_yoke'))
