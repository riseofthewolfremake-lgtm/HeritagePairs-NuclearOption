"""Round 3 (FD-32 v2) review renders - the views the v2 brief asks to look at, with stock parts previewed where they exist.

  blender --background assets/model_fd32/fd32.blend --python blender/fd32/render_r3_fd32.py -- --out <folder> --tex assets/textures_fd32

Views (review material: nuclearoption-ref, never git):
  r3_cockpit_eye            the pilot's eye (stock ejection seat + SFB-81 stick previewed, our fal throttle, the 4-island tac screen)
  r3_stick_seat_side/_top   stock seat vs stock stick, fuselage / canopy hidden, stick at 0 and +-12 deg pitch (ghost copies)
  r3_canopy_closed/_open    canopy closed, tilted open (contract open sign / angle)
  r3_canopy_eject           canopy jettisoned 1.5 m up and the seat 1.5 m up the ejection column
  r3_prop_front/_back       close-ups of the hub + blades (backface culling visible as holes if any face is inverted)
  r3_prop_stock             the CI-22 hub + blade beside ours
  r3_hook_stowed/_deployed  the modern fal hook
  r3_gear_down/_up          gear down with the green strips lit / gear folded (75 fwd mains, 35 aft tail) with the strips dark
  r3_livery_<key>           each livery, faction in the file name order: BDF matte grey, BDF temperate, PALA desert, PALA matte black
Stock meshes come from the user's Blueprinter placeholders through blender/ga25x/stock_preview.py (read only, nothing saved).
"""
import bpy, sys, os, math, json
from mathutils import Vector, Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'ga25x'))
sys.path.insert(0, os.path.join(HERE, '..', 'nimrod'))
sys.path.insert(0, HERE)
import stock_preview as SPV
import fd32_spec as FS

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1])
TEX = os.path.abspath(argv[argv.index('--tex') + 1])
ONLY = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
O = bpy.data.objects
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x, sc.render.resolution_y = 1400, 900
paint_tex = {}
for m in bpy.data.materials:
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
    if n == 'paint':
        paint_tex['node'] = t
for m in bpy.data.materials:                    # Unity draws with backface culling: so do the renders (inverted faces show as holes)
    m.use_backface_culling = True
light = bpy.data.materials.get('light_off')
light_bs = next((x for x in light.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'), None) if light and light.use_nodes else None


def lights(on):
    if light_bs is None:
        return
    light_bs.inputs['Base Color'].default_value = (0.1, 1.0, 0.2, 1) if on else (0.05, 0.12, 0.06, 1)
    key = 'Emission Color' if 'Emission Color' in light_bs.inputs else 'Emission'
    light_bs.inputs[key].default_value = (0.1, 1.0, 0.2, 1)
    light_bs.inputs['Emission Strength'].default_value = 8.0 if on else 0.0


w = sc.world or bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get('Background')
if bg: bg.inputs['Color'].default_value = (0.62, 0.66, 0.72, 1); bg.inputs['Strength'].default_value = 1.0
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3.0; sc.collection.objects.link(sun)
sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(35))
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
REST = {o.name: o.matrix_world.copy() for o in O}


def depth(o):
    d = 0
    while o.parent is not None:
        o = o.parent; d += 1
    return d


def reset():
    for o in sorted([o for o in O if o.name in REST], key=depth):    # parents first, then children back to their rest pose
        o.matrix_world = REST[o.name]
    bpy.context.view_layer.update()


def turn(names, piv, deg, axis='X'):
    Rm = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-piv)
    for n in names:
        if n in O:
            o = O[n]
            if o.parent is not None and o.parent.name in names:
                continue
            o.matrix_world = Rm @ o.matrix_world
    bpy.context.view_layer.update()


def shoot(name, pos, tgt, fov=35, hide=()):
    if ONLY and not any(name.startswith(k) for k in ONLY):
        return
    for o in O:
        o.hide_render = any(o.name == h or (h.endswith('*') and o.name.startswith(h[:-1])) for h in hide)
    cam.location = Vector(pos); d = Vector(tgt) - Vector(pos)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); cam.data.angle = math.radians(fov); cam.data.clip_start = 0.02
    sc.render.filepath = os.path.join(OUT, name + '.png'); bpy.ops.render.render(write_still=True); print('[render]', sc.render.filepath)


eye = O['cockpit_eye'].matrix_world.translation.copy()
stock = SPV.available()
if stock:
    SPV.add_stock('ejectionSeat', SPV.seat_origin_blender(eye), 'preview_seat')
    stick_at = O['cockpit_stick'].matrix_world.translation.copy()
    SPV.add_stock('sfb_joystick', stick_at, 'preview_stick')
    for k, a in (('fwd', -12), ('aft', 12)):            # ghost sweep copies (Unity +pitch = top aft = Blender -X rotation? both shown)
        g = SPV.add_stock('sfb_joystick', stick_at, f'preview_stick_{k}')
        g.matrix_world = Matrix.Translation(stick_at) @ Matrix.Rotation(math.radians(a), 4, 'X') @ Matrix.Translation(-stick_at) @ g.matrix_world
else:
    print('[render] no Blueprinter placeholders: stock previews skipped')
GHOST = ('preview_stick_fwd', 'preview_stick_aft')
lights(True)

# cockpit
shoot('r3_cockpit_eye', eye, eye + Vector((0, 1, -0.38)), 80, GHOST)
shoot('r3_cockpit_over', eye + Vector((0.55, 0.15, 0.55)), eye + Vector((0, 0.35, -0.55)), 70,
      GHOST + ('canopy_slide', 'canopy_slide_glass', 'wing_upper_C', 'cabane', 'windscreen', 'windscreen_frame'))
# stick vs seat (airframe hidden)
cut = ('fus_*', 'canopy_*', 'windscreen*', 'wing_*', 'cabane*', 'wire*', 'strut*', 'prop_*', 'spinner*')
shoot('r3_stick_seat_side', eye + Vector((1.6, -0.1, -0.35)), eye + Vector((0, -0.05, -0.55)), 45, cut)
shoot('r3_stick_seat_top', eye + Vector((0.0, 0.0, 1.4)), eye + Vector((0, -0.05, -0.6)), 55, cut)
shoot('r3_stick_seat_front', eye + Vector((0.0, 1.6, -0.3)), eye + Vector((0, 0, -0.55)), 50, cut + ('cockpit_panel*', 'mfd_*'))

# the cockpit opening with the canopy removed (sill / coaming edge)
OPEN_HIDE = GHOST + ('canopy_slide', 'canopy_slide_glass', 'preview_seat', 'wing_upper_*', 'cabane*')
shoot('r3_opening_left', eye + Vector((-1.1, 0.3, 0.9)), eye + Vector((-0.3, -0.2, -0.25)), 50, OPEN_HIDE)
shoot('r3_opening_top', eye + Vector((0.0, -0.3, 1.8)), eye + Vector((0, -0.3, 0)), 50, OPEN_HIDE)
# canopy closed / open / jettisoned
cn = ['canopy_slide_hinge', 'canopy_slide', 'canopy_slide_glass']
shoot('r3_canopy_closed', eye + Vector((2.4, 1.2, 1.0)), eye + Vector((0, -0.4, 0.1)), 40, GHOST)
cj = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), 'fd32_canopy_open.json')))
hg = O['canopy_slide_hinge']; hpv = hg.matrix_world.translation.copy()
turn(cn, hpv, cj['open_sign_blender'] * cj['open_deg'])
shoot('r3_canopy_open', eye + Vector((2.4, 1.2, 1.0)), eye + Vector((0, -0.4, 0.3)), 40, GHOST)
reset()
for n in cn:
    if n in O and (O[n].parent is None or O[n].parent.name not in cn):
        O[n].matrix_world = Matrix.Translation((0, 0, 1.5)) @ O[n].matrix_world
for n in ('preview_seat',):
    if n in O:
        O[n].matrix_world = Matrix.Translation((0, 0, 1.5)) @ O[n].matrix_world
bpy.context.view_layer.update()
shoot('r3_canopy_eject', eye + Vector((4.0, 0.8, 1.6)), eye + Vector((0, -0.3, 0.9)), 45, GHOST)
if 'preview_seat' in O:
    O['preview_seat'].matrix_world = Matrix.Translation((0, 0, -1.5)) @ O['preview_seat'].matrix_world
reset()

# propeller
hub = O['prop_hub'].matrix_world.translation.copy()
shoot('r3_prop_front', hub + Vector((0.6, 2.4, 0.3)), hub, 45)
shoot('r3_prop_back', hub + Vector((1.2, -0.9, 0.5)), hub + Vector((0.5, 0, 0)), 50, ('fus_engine*', 'cowl*', 'wing_*', 'cabane*', 'wire*', 'strut*'))
if stock:
    at = hub + Vector((3.6, 0, 0))
    SPV.add_stock('COIN_propHub_LOD0', at, 'stock_hub', mats=['Matte_black'])
    for k in range(3):
        b = SPV.add_stock('COIN_blade', at, f'stock_blade_{k}', mats=['Matte_black'])
        b.rotation_euler = (0, math.radians(120 * k), 0)
    shoot('r3_prop_stock', hub + Vector((1.8, 6.5, 0.6)), hub + Vector((1.8, 0, 0)), 42)
    for n in ['stock_hub'] + [f'stock_blade_{k}' for k in range(3)]:
        bpy.data.objects.remove(O[n], do_unlink=True)        # (shoot() resets hide_render: remove the comparison parts)

# hook (modelled stowed at HOOK_STOW_UP; deployed = HOOK_DEPLOY, a rotation of stow - deploy about +X)
hp = O['tailhook'].matrix_world.translation.copy()
shoot('r3_hook_stowed', hp + Vector((1.6, -1.4, -0.9)), hp + Vector((0, -1.0, -0.1)), 45, GHOST)
st, dp = FS.HOOK_STOW_UP, -65.0
turn(['tailhook'], hp, st - dp)
shoot('r3_hook_deployed', hp + Vector((2.2, -1.2, -1.0)), hp + Vector((0, -1.0, -0.8)), 50, GHOST)
reset()

# gear down (strips lit) / up (strips dark)
shoot('r3_gear_down', (5.5, 4.5, -1.6), (0, -0.3, -0.4), 42, GHOST)
shoot('r3_gear_down_front3q', (5.0, 6.5, 0.4), (0, 0.4, -0.35), 36, GHOST)
shoot('r3_well_closeup_down', (2.1, 1.0, -0.15), (0.6, 1.3, -0.25), 40, GHOST)
shoot('r3_gear_down_side', (6.5, 0.6, -0.3), (0, 0.6, -0.3), 34, GHOST)
for g, deg in ((['gear_main_L_strut', 'gear_main_L_wheel'], FS.GEAR_FOLD_DEG), (['gear_main_R_strut', 'gear_main_R_wheel'], FS.GEAR_FOLD_DEG),
               (['gear_tail_strut', 'gear_tail_wheel'], -FS.TAIL_FOLD_DEG)):
    pv = O[g[0]].matrix_world.translation.copy()
    turn(g, pv, deg, FS.main_fold_axis(pv.x) if 'main' in g[0] else 'X')
lights(False)
shoot('r3_gear_up', (5.5, 4.5, -1.6), (0, -0.3, -0.4), 42, GHOST)
shoot('r3_gear_up_below', (0.01, -0.5, -10.5), (0, -0.5, 0), 44, GHOST)
shoot('r3_gear_up_front3q', (5.0, 6.5, 0.4), (0, 0.4, -0.35), 36, GHOST)
shoot('r3_gear_up_side', (6.5, 0.6, -0.3), (0, 0.6, -0.3), 34, GHOST)
shoot('r3_well_closeup_up', (2.1, 1.0, -0.15), (0.6, 1.3, -0.25), 40, GHOST)
reset(); lights(True)

# liveries per faction
for key in ('bdf_mattegrey', 'bdf_temperate', 'pala_desert', 'pala_matteblack'):
    if 'node' in paint_tex:
        paint_tex['node'].image = bpy.data.images.load(os.path.join(TEX, f'fd32_livery_{key}.png'), check_existing=True)
    shoot(f'r3_livery_{key}', (7.5, 7.5, 3.0), (0, -0.5, 0), 34, GHOST)
    shoot(f'r3_livery_{key}_top', (0, -0.9, 14), (0, -0.9, 0), 42, GHOST)
