"""1.9.7 before / after review renders of the MSB-17/80 (tail windows, faceting). Plain glossy grey on every outside material so the
shading shows the exported normals only (no textures); glass dark. Output OUTSIDE the repo.

  blender -b <msb1780.blend> -P blender/msb1780/render_r7.py -- --out <dir> --tag 196|197
"""
import bpy, sys, os, math
from mathutils import Vector as V

argv = sys.argv[sys.argv.index('--') + 1:]
OUT = argv[argv.index('--out') + 1]; TAG = argv[argv.index('--tag') + 1]
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in ids else 'BLENDER_EEVEE_NEXT'
w = sc.world or bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get('Background'); bg.inputs[0].default_value = (0.55, 0.62, 0.72, 1); bg.inputs[1].default_value = 0.6
try:
    sc.view_settings.view_transform = 'Standard'
except Exception:
    pass


def mat(name, col, rough, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = col; b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    return m


grey = mat('r7_grey', (0.55, 0.57, 0.60, 1), 0.32, 0.35); glass = mat('r7_glass', (0.02, 0.05, 0.09, 1), 0.08); dark = mat('r7_dark', (0.10, 0.10, 0.11, 1), 0.5)
for o in bpy.data.objects:
    if o.name.endswith('_hullsrc'):
        o.hide_render = True
    if o.type != 'MESH':
        continue
    for i, s in enumerate(o.material_slots):
        n = s.material.name if s.material else ''
        s.material = glass if n == 'glass' else grey if n in ('paint', 'cove') else dark
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun); sun.data.energy = 4.0
fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill); fill.data.energy = 0.8
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = 1400, 800


def aim(o, loc, look):
    o.location = V(loc)
    o.rotation_euler = (V(look) - V(loc)).to_track_quat('-Z', 'Y').to_euler()


def shot(name, loc, look, lens, sun_from, fill_from):
    aim(cam, loc, look); cam.data.lens = lens; cam.data.clip_start = 0.05; cam.data.clip_end = 300
    aim(sun, V(look) + V(sun_from), look); aim(fill, V(look) + V(fill_from), look)
    sc.render.filepath = os.path.join(OUT, f'r7_{name}_{TAG}.png')
    bpy.ops.render.render(write_still=True)
    print('[r7]', sc.render.filepath)


# tail: left side, rear quarter, from above-behind
shot('tail_side', (-6.5, -14.3, 1.9), (0, -14.3, 1.25), 50, (-3, 2, 4), (-2, -4, -1))
shot('tail_rearq', (-3.2, -19.0, 2.6), (0, -14.4, 1.2), 55, (-3, -3, 4), (3, -2, 0))
shot('tail_top', (1.8, -17.5, 4.6), (0, -14.3, 1.3), 50, (2, -2, 5), (-3, 1, 1))
# defensive (side) bay, left: raking light along the fuselage; and both bays from below-behind
shot('sidebay_L', (-6.0, -8.6, 1.1), (-0.9, -6.5, 0.45), 60, (-1.0, 6, 1.2), (-4, -3, 0.5))
shot('sidebay_L_low', (-4.2, -10.5, -0.6), (-0.8, -6.4, 0.4), 55, (-2, -5, -0.5), (-4, 3, 2))
# bomb bay doors from below, nose from the front quarter
shot('bombbay', (-3.8, 3.2, -2.3), (0, -0.6, -0.55), 40, (-3, 4, -2), (-3, -3, -1))
shot('nose', (-4.6, 10.2, 2.2), (0, 6.2, 0.9), 50, (-3, 3, 4), (-2, 1, -2))
