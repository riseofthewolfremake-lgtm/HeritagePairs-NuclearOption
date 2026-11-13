"""Round 6 (FD-32 1.5.2) review renders: the views the round-6 brief asks for (docs/fd32_design.md 19).

  blender --background assets/model_fd32/fd32.blend --python blender/fd32/render_v7_fd32.py -- --out <folder> --tex assets/textures_fd32

Review material only (nuclearoption-ref\\study\\fd32\\renders\\v7, never git):
  v7_gear_swing_sheet       side view, main gear at 0 / 25 / 50 / 75 / 100 % of the aft swing
  v7_gear_down/up_side|below
  v7_hook_swing_sheet       side + below, hook at 0 / 25 / 50 / 75 / 100 %
  v7_prop_side              prop / nose close-up from the side (blades stopped and hidden = the blurred look)
  v7_cockpit_eye            the pilot's eye; screens show a UV TEST PATTERN (map / power / flight / engine regions), not game art
  v7_canopy_left/right      from the eye looking left / right (glass drawn from inside, as the Unity cockpit-layer copy)
  v7_stick_throttle_side    stick base + throttle console from the side (seat previewed)
  v7_throttle_vs_stock      our fal lever in its quadrant beside the stock SFB-81 throttle mesh
Stock meshes come from the user's Blueprinter placeholders through blender/ga25x/stock_preview.py (read only, nothing saved).
"""
import bpy, sys, os, math
from mathutils import Vector, Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'ga25x'))
sys.path.insert(0, os.path.join(HERE, '..', 'nimrod'))
sys.path.insert(0, os.path.join(HERE, '..', 'v2'))
sys.path.insert(0, HERE)
import stock_preview as SPV
import nimrod_spec as S
import fd32_spec as FS
FS.apply(); FS.apply_stretch()
import fd32_cockpit as FC
import fd32_gear6 as G6

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1])
TEX = os.path.abspath(argv[argv.index('--tex') + 1])
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
O = bpy.data.objects
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x, sc.render.resolution_y = 1200, 800


def bsdf(m):
    return next((x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'), None) if m.use_nodes else None


for m in bpy.data.materials:
    n = m.name; path = None; uvl = None
    if n.startswith('pr_'):
        path, uvl = os.path.join(TEX, f'fd32_{n}_b.png'), 'livery'
    elif n == 'paint':
        path, uvl = os.path.join(TEX, 'fd32_livery_%s.png' % (argv[argv.index('--livery') + 1] if '--livery' in argv else 'bdf_mattegrey')), 'livery'
    elif os.path.exists(os.path.join(TEX, f'fd32_tile_{n}_b.png')):
        path, uvl = os.path.join(TEX, f'fd32_tile_{n}_b.png'), 'detail'
    bs = bsdf(m)
    if not path or not os.path.exists(path) or bs is None:
        continue
    t = m.node_tree.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path, check_existing=True)
    uv = m.node_tree.nodes.new('ShaderNodeUVMap'); uv.uv_map = uvl
    m.node_tree.links.new(uv.outputs['UV'], t.inputs['Vector']); m.node_tree.links.new(t.outputs['Color'], bs.inputs['Base Color'])
for m in bpy.data.materials:
    m.use_backface_culling = True
# glass: drawn from both sides (Unity: exterior glass outside + the reversed-winding cockpit-layer copy inside), light blue tint
g = bpy.data.materials.get('glass')
if g is not None and bsdf(g) is not None:
    g.use_backface_culling = False
    b = bsdf(g); b.inputs['Base Color'].default_value = (0.55, 0.75, 0.85, 1); b.inputs['Alpha'].default_value = 0.35
    b.inputs['Roughness'].default_value = 0.05
    try:
        g.surface_render_method = 'BLENDED'
    except Exception:
        g.blend_method = 'BLEND'
# screens: a UV TEST PATTERN of the 1024 x 512 tac page made by compose_v7_fd32.py --pattern (Blender has no PIL)
pp = os.path.join(OUT, '_tac_test_pattern.png')
scr = bpy.data.materials.get('screen')
if scr is not None and bsdf(scr) is not None:
    t = scr.node_tree.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(pp)
    uv = scr.node_tree.nodes.new('ShaderNodeUVMap'); uv.uv_map = 'livery'
    b = bsdf(scr)
    scr.node_tree.links.new(uv.outputs['UV'], t.inputs['Vector']); scr.node_tree.links.new(t.outputs['Color'], b.inputs['Base Color'])
    key = 'Emission Color' if 'Emission Color' in b.inputs else 'Emission'
    scr.node_tree.links.new(t.outputs['Color'], b.inputs[key]); b.inputs['Emission Strength'].default_value = 1.5
lt = bpy.data.materials.get('light_off')
if lt is not None and bsdf(lt) is not None:
    b = bsdf(lt); key = 'Emission Color' if 'Emission Color' in b.inputs else 'Emission'
    b.inputs[key].default_value = (0.1, 1.0, 0.2, 1)


def strips(on):
    if lt is not None and bsdf(lt) is not None:
        bsdf(lt).inputs['Emission Strength'].default_value = 8.0 if on else 0.0


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
    for o in sorted([o for o in O if o.name in REST], key=depth):
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


ONLY = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None


def shoot(name, pos, tgt, fov=35, hide=(), res=None):
    if ONLY and not any(name.startswith(k) for k in ONLY):
        return os.path.join(OUT, name + '.png')
    for o in O:
        o.hide_render = any(o.name == h or (h.endswith('*') and o.name.startswith(h[:-1])) for h in hide)
    cam.location = Vector(pos); d = Vector(tgt) - Vector(pos)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); cam.data.angle = math.radians(fov); cam.data.clip_start = 0.02
    sc.render.resolution_x, sc.render.resolution_y = res or (1200, 800)
    p = os.path.join(OUT, name + '.png')
    sc.render.filepath = p; bpy.ops.render.render(write_still=True); print('[render]', p)
    return p


SHEETS = {}


def sheet(files, name, cols=5):
    SHEETS[name] = (cols, files)          # composed by compose_v7_fd32.py (sheets.json)


eye = O['cockpit_eye'].matrix_world.translation.copy()
stock = SPV.available()
if stock:
    SPV.add_stock('ejectionSeat', SPV.seat_origin_blender(eye), 'preview_seat')
    SPV.add_stock('sfb_joystick', O['cockpit_stick'].matrix_world.translation.copy(), 'preview_stick')
    SPV.add_stock('COIN_throttle', O['cockpit_throttle'].matrix_world.translation.copy(), 'preview_thr', mats=['hotas'])        # round 10: CI-22 throttle at idle
    SPV.add_stock('COIN_throttle', O['cockpit_throttle'].matrix_world.translation.copy() + Vector((0, 0.22, 0)), 'preview_thr_full', mats=['hotas'])   # and at full (slides 0.22 m forward)
BLADES = tuple(o.name for o in O if o.name.startswith('prop_blade'))
MAINS = {L: [f'gear_main_{L}_strut', f'gear_main_{L}_wheel'] for L in 'LR'}


def gear(frac):
    reset()
    for L in 'LR':
        Rm = G6.fold_matrix(-1 if L == 'L' else 1, frac)
        for n in MAINS[L]:
            o = O[n]
            if o.parent is not None and o.parent.name in MAINS[L]:
                continue
            o.matrix_world = Rm @ o.matrix_world
    bpy.context.view_layer.update()


hk = O['tailhook']; hpv = hk.matrix_world.translation.copy()


def hook(frac):
    turn(['tailhook'], hpv, -(S.HOOK_DEPLOY - S.HOOK_STOW_UP) * frac, 'X')


# ---------------------------------------------------------------- gear swing sheet (side, left side of the aircraft)
files = []
for f in (0, 0.25, 0.5, 0.75, 1.0):
    gear(f); strips(f == 0)
    files.append(shoot(f'_gs_{int(f * 100):03d}', (-4.2, 0.0, -1.0), (0, 0.0, -0.95), 40, BLADES, (700, 520)))
sheet(files, 'v7_gear_swing_sheet')
for f, nm in ((0, 'down'), (1, 'up')):
    gear(f); strips(f == 0)
    shoot(f'v7_gear_{nm}_side', (-9.0, 0.3, -0.5), (0, -0.6, -0.4), 45)
    shoot(f'v7_gear_{nm}_below', (-3.0, 2.0, -5.0), (0, -0.4, -0.8), 55)
    shoot(f'v7_gear_{nm}_front3q', (-4.5, 5.5, -1.3), (0, 0, -0.7), 45)
# round 7: stowed wheel vs the biggest inner-pylon stores (proxy boxes of the stock mounts, the check's numbers: AGR-18 x7, AGR-24 x4)
gear(1.0); strips(False)
hp = O['hp_inner_R'].matrix_world.translation.copy()
pm = bpy.data.materials.new('store_proxy'); pm.diffuse_color = (0.8, 0.3, 0.1, 1)
if pm.use_nodes and bsdf(pm) is not None: bsdf(pm).inputs['Base Color'].default_value = (0.8, 0.3, 0.1, 1)
for nm_, (a_, b_) in (('AGR18x7', ((-0.149, -0.359, -1.028), (0.149, 0.055, 1.045))), ('AGR24x4', ((-0.195, -0.491, -1.091), (0.195, 0.052, 1.088)))):
    me = bpy.data.meshes.new('px_' + nm_); bpy.ops.mesh.primitive_cube_add(size=1.0)
    cb = bpy.context.active_object; cb.name = 'px_' + nm_
    cb.scale = ((b_[0] - a_[0]), (b_[2] - a_[2]), (b_[1] - a_[1]))
    cb.location = hp + Vector(((a_[0] + b_[0]) / 2, (a_[2] + b_[2]) / 2, (a_[1] + b_[1]) / 2))
    cb.data.materials.append(pm); cb.display_type = 'WIRE'
    if nm_ == 'AGR18x7':
        cb.hide_render = False
shoot('v7_gear_up_store_closeup', (2.6, -2.6, -1.7), (1.2, -0.6, -0.8), 45, ('px_AGR24x4',))
shoot('v7_gear_up_store_closeup_agr24', (2.6, -2.6, -1.7), (1.2, -0.6, -0.8), 45, ('px_AGR18x7',))
for o_ in [o for o in O if o.name.startswith('px_')]:
    bpy.data.objects.remove(o_)
reset(); strips(True)
# ---------------------------------------------------------------- hook swing
files = []
for f in (0, 0.25, 0.5, 0.75, 1.0):
    reset(); hook(f)
    files.append(shoot(f'_hs_{int(f * 100):03d}', (-3.0, -3.2, -1.0), (0, -3.3, -0.7), 45, (), (700, 520)))
for f in (0, 0.5, 1.0):
    reset(); hook(f)
    files.append(shoot(f'_hb_{int(f * 100):03d}', (-1.6, -3.0, -3.0), (0, -3.2, -0.6), 45, (), (700, 520)))
sheet(files, 'v7_hook_swing_sheet', cols=4)
reset()
# ---------------------------------------------------------------- prop / nose close-up (blades hidden = the in-game blurred look, and with blades)
shoot('v7_prop_side_noblades', (-2.2, 2.55, 0.1), (0, 2.55, 0.0), 30, BLADES)
shoot('v7_prop_side', (-2.2, 2.55, 0.1), (0, 2.55, 0.0), 30)
# ---------------------------------------------------------------- cockpit
shoot('v7_cockpit_eye', eye, eye + Vector((0, 1, -0.38)), 80, ('preview_thr_full',))
shoot('v10_throttle_idle_full', eye + Vector((0.10, 0.0, -0.05)), O['cockpit_throttle'].matrix_world.translation + Vector((0.06, 0.12, 0.05)), 45)
shoot('v10_throttle_side', O['cockpit_throttle'].matrix_world.translation + Vector((0.55, 0.05, 0.25)), O['cockpit_throttle'].matrix_world.translation + Vector((0.0, 0.12, 0.04)), 40, ('preview_thr_full', 'cockpit_interior', 'cockpit_console_R', 'preview_seat', 'preview_stick'))
shoot('v8_cockpit_eye_low', eye + Vector((0, 0.03, -0.04)), eye + Vector((0, 1.03, -0.42)), 80)     # round 8: the in-flight head (4 cm lower, 3 cm fwd)
LIV = argv[argv.index('--livery') + 1] if '--livery' in argv else 'bdf_mattegrey'
shoot('v8_camo_flaperon_' + LIV, (1.9, -1.6, -1.6), (1.6, -0.75, -0.62), 30)                        # round 8: camo edge at the flaperon TE (below, aft)
shoot('v8_camo_chin_' + LIV, (-1.5, 1.6, -0.75), (0, 1.6, -0.35), 35)                                # round 8: camo edge at the nose chin
shoot('v7_canopy_left', eye, eye + Vector((-1, 0.25, -0.05)), 80)
shoot('v7_canopy_right', eye, eye + Vector((1, 0.25, -0.05)), 80)
shoot('v7_canopy_up_back', eye, eye + Vector((0.3, -0.6, 0.8)), 80)
CUT = ('fus_center', 'fus_engine', 'canopy_slide', 'canopy_slide_glass', 'windscreen', 'windscreen_frame', 'cockpit_interior', 'cockpit_console_L',
       'wing_lower_L', 'wing_lower_L_root', 'rigging_L', 'gear_main_L_strut', 'gear_main_L_wheel', 'gear_mount_L', 'slimelight_fus_L', 'fus_center_struct')
shoot('v7_stick_throttle_side', eye + Vector((-1.3, 0.15, -0.35)), eye + Vector((0, 0.35, -0.65)), 50, CUT)
shoot('v7_stick_throttle_over', eye + Vector((-0.2, -0.25, 0.25)), eye + Vector((-0.2, 0.40, -0.70)), 60, ('canopy_slide', 'canopy_slide_glass'))
# ---------------------------------------------------------------- our throttle vs the stock SFB-81 throttle (stock mesh beside it, same height)
if stock:
    tp = O['cockpit_throttle'].matrix_world.translation.copy()
    st_th = SPV.add_stock('sfb_throttle', tp, 'preview_throttle')
    bpy.context.view_layer.update()
    bb = [st_th.matrix_world @ Vector(c) for c in st_th.bound_box]
    lo_z = min(v.z for v in bb); cx = sum(v.x for v in bb) / 8; cy = sum(v.y for v in bb) / 8
    st_th.matrix_world = Matrix.Translation(Vector((tp.x + 0.22 - cx, tp.y - cy, tp.z - 0.02 - lo_z))) @ st_th.matrix_world   # base level with our pivot, 0.22 m inboard
    bpy.context.view_layer.update()
    print('[render] stock throttle bbox', [tuple(round(c, 3) for c in v) for v in bb[:2]])
    shoot('v7_throttle_vs_stock', tp + Vector((0.35, -0.55, 0.10)), tp + Vector((0.12, 0.0, 0.05)), 40, CUT + ('preview_seat', 'preview_stick'))
import json
if not ONLY:
    json.dump(SHEETS, open(os.path.join(OUT, '_sheets.json'), 'w'))
if stock and (not ONLY or any(k.startswith('v10_stock') for k in ONLY)):
    # round 10: the stock single-seat throttles side by side, away from the aircraft (+8 m right): COIN_throttle (CI-22), smallFighter1 (FS-12), sfb (SFB-81, the bomber one)
    base = Vector((8.0, 0.0, 0.0))
    for i, (n_, m_) in enumerate((('COIN_throttle', ['hotas']), ('smallFighter1_throttle', ['hotas']), ('sfb_throttle', ['SFB_cockpit']))):
        SPV.add_stock(n_, base + Vector((i * 0.40, 0, 0)), 'cmp_' + n_, mats=m_)
    shoot('v10_stock_throttles_COIN_FS12_SFB', base + Vector((0.40, -1.2, 0.55)), base + Vector((0.40, 0.0, 0.10)), 45)
print('[render] done')
