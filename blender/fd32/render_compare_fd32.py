"""Review renders: the new fal FD-32 assets next to the matching stock assets, and the cockpit with the stock kit previewed.

  blender --background assets/model_fd32/fd32.blend --python blender/fd32/render_compare_fd32.py -- --out <folder> --tex assets/textures_fd32

Stock meshes are read at run time from the user's Blueprinter placeholders (blender/ga25x/stock_preview.py, read-only, never saved):
  prop      fal 4-blade prop (prop_hub + prop_blade_*)  vs  CI-22 COIN_propHub_LOD0 + COIN_blade (x3, the CI-22 3-blade pusher)
  sensor    fal sensor ball                             vs  CI-22 COIN_targetCam (its EO turret)
  cockpit   our tub / panel / consoles + stock ejectionSeat / sfb_joystick / sfb_throttle at the contract positions
Output: fd32_cmp_prop.png, fd32_cmp_sensor.png, fd32_cmp_cockpit.png (review material: nuclearoption-ref, not git).
"""
import bpy, sys, os, math
from mathutils import Vector, Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'ga25x'))
import stock_preview as SPV

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1])
TEX = os.path.abspath(argv[argv.index('--tex') + 1])
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
O = bpy.data.objects
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x, sc.render.resolution_y = 1400, 900
for m in bpy.data.materials:                          # textured own materials (same mapping as render_fd32.py)
    n = m.name; path = None; uvl = None
    if n.startswith('pr_'):
        path, uvl = os.path.join(TEX, f'fd32_{n}_b.png'), 'livery'
    elif n == 'paint':
        path, uvl = os.path.join(TEX, 'fd32_livery_bdf_mattegrey.png'), 'livery'
    elif os.path.exists(os.path.join(TEX, f'fd32_tile_{n}_b.png')):
        path, uvl = os.path.join(TEX, f'fd32_tile_{n}_b.png'), 'detail'
    if not path or not os.path.exists(path) or not m.use_nodes:
        continue
    bs = next((x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'), None)
    if bs is None:
        continue
    t = m.node_tree.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path, check_existing=True)
    uv = m.node_tree.nodes.new('ShaderNodeUVMap'); uv.uv_map = uvl
    m.node_tree.links.new(uv.outputs['UV'], t.inputs['Vector']); m.node_tree.links.new(t.outputs['Color'], bs.inputs['Base Color'])
w = sc.world or bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg: bg.inputs['Color'].default_value = (0.62, 0.66, 0.72, 1); bg.inputs['Strength'].default_value = 1.0
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3.0; sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(35))
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam


def shoot(name, pos, tgt, fov=35, hide=()):
    for o in O:
        o.hide_render = o.name in hide
    cam.location = Vector(pos); d = Vector(tgt) - Vector(pos)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); cam.data.angle = math.radians(fov); cam.data.clip_start = 0.02
    sc.render.filepath = os.path.join(OUT, name); bpy.ops.render.render(write_still=True); print('[render]', sc.render.filepath)


if SPV.available():
    hub = O['prop_hub'].matrix_world.translation
    # stock CI-22 prop (3 blades, R 1.2 x ~1) beside ours, 4 m to the right, same height
    at = hub + Vector((4.0, 0, 0))
    SPV.add_stock('COIN_propHub_LOD0', at, 'stock_hub', mats=['Matte_black'])
    for k in range(3):
        b = SPV.add_stock('COIN_blade', at, f'stock_blade_{k}', mats=['Matte_black'])
        b.rotation_euler = (0, math.radians(120 * k), 0)
    shoot('fd32_cmp_prop.png', hub + Vector((2.0, 7.5, 0.6)), hub + Vector((2.0, 0, 0)), 40)
    ball = O['sensor_ball'].matrix_world.translation
    st = SPV.add_stock('COIN_targetCam', ball + Vector((0.8, 0, 0)), 'stock_targetcam', mats=['Matte_black'])
    st.data.shade_smooth()                                     # the placeholder carries no normals: smooth for a fair comparison
    shoot('fd32_cmp_sensor.png', ball + Vector((0.45, 2.2, -0.5)), ball + Vector((0.4, 0, 0)), 35)
    shoot('fd32_cmp_sensor_close.png', ball + Vector((0.0, 0.75, -0.45)), ball + Vector((0, 0, -0.05)), 30, ('stock_targetcam',))
    SPV.add_cockpit_preview() if False else None
    eye = O['cockpit_eye'].matrix_world.translation
    SPV.add_stock('ejectionSeat', SPV.seat_origin_blender(eye), 'preview_seat')
    SPV.add_stock('sfb_joystick', O['cockpit_stick'].matrix_world.translation, 'preview_stick')
    SPV.add_stock('sfb_throttle', O['cockpit_throttle'].matrix_world.translation, 'preview_throttle')
    hide = ('canopy_slide', 'canopy_slide_glass', 'wing_upper_C', 'cabane', 'windscreen')
    shoot('fd32_cmp_cockpit.png', eye + Vector((0.55, 0.15, 0.55)), eye + Vector((0, 0.35, -0.55)), 70, hide)
    shoot('fd32_cmp_cockpit_eye.png', eye, eye + Vector((0, 1, -0.4)), 80)
else:
    print('[render] no Blueprinter placeholders: comparison skipped')
