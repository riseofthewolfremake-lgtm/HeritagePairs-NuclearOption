"""Close-up / cutaway / pose renders of the B-25H v2 model (workbench, material colours,
backface culling ON to match Unity's default shaders).

  blender --background --factory-startup --python blender/v2/render_b25h_v2.py -- <model.blend> <outdir> [shot ...]
"""
import bpy, sys, os, math, json
from mathutils import Vector, Matrix, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:]
blend, out = argv[0], argv[1]
only = set(argv[2:])
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'MATERIAL'
sh.show_cavity = True
sh.cavity_type = 'BOTH'
sh.show_backface_culling = True
sh.show_shadows = False
scene.render.resolution_x, scene.render.resolution_y = 1400, 900
scene.render.film_transparent = False
scene.render.resolution_percentage = 70
scene.render.image_settings.compression = 90
try:
    scene.world.color = (0.55, 0.6, 0.65)
except Exception:
    w = bpy.data.worlds.new('w')
    scene.world = w
    w.color = (0.55, 0.6, 0.65)
sh.background_type = 'VIEWPORT'
sh.background_color = (0.55, 0.6, 0.65)

cam_data = bpy.data.cameras.new('cam')
cam = bpy.data.objects.new('cam', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
O = bpy.data.objects
INFO = {o.name: (json.loads(o['b25_info']) if o.get('b25_info') else {}) for o in O}
EXTRAS = [o for o in O if o.users_collection and o.users_collection[0].name == 'B25H_extras']
for o in EXTRAS:
    o.hide_render = True


def descendants(o):
    out = [o]
    for c in o.children:
        out += descendants(c)
    return out


def look(loc, target, up=Vector((0, 0, 1))):
    loc, target = Vector(loc), Vector(target)
    d = (target - loc).normalized()
    q = d.to_track_quat('-Z', 'Y')
    cam.location = loc
    cam.rotation_mode = 'XYZ'
    cam.rotation_euler = q.to_euler()


def shot(name, loc, target, lens=50, ortho=None, clip=(0.05, 200), hide=(), res=(1400, 900), exact=False):
    if only and name not in only:
        return
    hidden = []
    for n in hide:
        if n in O:
            for o in ([O[n]] if exact else descendants(O[n])):
                if not o.hide_render:
                    o.hide_render = True
                    hidden.append(o)
    look(loc, target)
    if ortho:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = ortho
    else:
        cam_data.type = 'PERSP'
        cam_data.lens = lens
    cam_data.clip_start, cam_data.clip_end = clip
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = os.path.join(out, name + '.png')
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    print('SHOT', name)


def set_pose(name, q_local):
    o = O[name]
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = q_local


def rotate_about_local(name, axis_local, deg):
    """rotate object by deg about an axis given in its own local frame (from its current pose)."""
    o = O[name]
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = o.rotation_quaternion @ Quaternion(Vector(axis_local), math.radians(deg))


def rotate_about_world_axis(name, axis_world, deg):
    o = O[name]
    mw = o.matrix_world.copy()
    t = mw.translation.copy()
    R = Quaternion(Vector(axis_world), math.radians(deg)).to_matrix().to_4x4()
    o.matrix_world = Matrix.Translation(t) @ R @ Matrix.Translation(-t) @ mw
    bpy.context.view_layer.update()


# ---------------------------------------------------------------------------------- exterior shots
shot('overview_front34', (14, 16, 5), (0, -0.5, 0.2), lens=40)
shot('overview_rear34', (-14, -18, 7), (0, -1.0, 0.3), lens=40)
shot('closeup_nose', (2.6, 9.2, 0.6), (0, 5.3, 0.1), lens=50)
shot('closeup_nose_left', (-3.0, 8.8, -0.6), (0, 5.0, 0.0), lens=45)
shot('closeup_cockpit_turret', (-3.2, 5.6, 3.2), (0, 2.6, 1.1), lens=45)
shot('closeup_engine_prop', (-6.5, 7.0, 0.8), (-2.95, 2.4, 0.0), lens=50)
shot('closeup_gear_side', (-9.5, 1.5, -1.0), (-2.95, 0.6, -1.4), lens=40)
shot('closeup_gear_front', (0, 12, -1.6), (0, 0, -1.5), lens=35)
shot('closeup_tail', (-6.5, -12.5, 2.5), (0, -8.5, 0.9), lens=45)

# damage: rear fuselage and left outer wing broken off
shot('damage_fusrear_wingouterL', (-7.5, -6.5, 2.2), (-2.5, -1.5, 0.4), lens=35, hide=('fus_rear', 'wing_outer_L'))
shot('damage_fusrear_close', (-1.6, -4.2, 0.9), (0, -1.8, 0.2), lens=35, hide=('fus_rear',))
shot('damage_wing_close', (-7.0, 1.5, 2.6), (-2.95, -0.3, 0.4), lens=35, hide=('wing_outer_L',))
shot('damage_wing_rib', (-6.0, 1.2, 1.6), (-2.95, -0.3, 0.45), lens=40, hide=('wing_outer_L', 'nacelle_L'))
keep = {d.name for d in descendants(O['wing_outer_L'])}
shot('damage_outer_panel_root', (-0.2, 2.2, 1.6), (-3.4, -0.2, 0.5), lens=40,
     hide=[o.name for o in O if o.type == 'MESH' and o.name not in keep and o.name not in ('B25H_root',)
           ], exact=True)
shot('damage_nose_off', (1.8, 7.0, 0.8), (0, 4.4, 0.2), lens=40, hide=('fus_nose',))

# cockpit eye
if 'cockpit_eye' in O and (not only or 'cockpit_eye_view' in only):
    e = O['cockpit_eye'].matrix_world.translation
    shot('cockpit_eye_view', e, e + Vector((0, 1, -0.12)), lens=18, clip=(0.02, 500))
    shot('cockpit_eye_left', e, e + Vector((-1, 0.6, -0.1)), lens=18, clip=(0.02, 500))
    shot('cockpit_overhead_cut', (0, 3.4, 4.0), (0, 3.4, 0), ortho=2.4, clip=(4.0 - 1.30, 50), res=(1000, 1100))

# cutaways (clip plane via camera clip_start)
shot('cut_centreline', (30, -1.8, 0.3), (0, -1.8, 0.3), ortho=17.5, clip=(30.0, 80), res=(1800, 760))
shot('cut_nacelle_L', (-30, -0.3, 0.0), (-3.25, -0.3, 0.0), ortho=7.0, clip=(30 - 3.25, 80), res=(1400, 900))
for y in (5.0, 3.4, 1.8, 0.0, -3.1, -8.8):
    shot(f'cut_section_y{y:+.1f}', (0, y + 30, 0.4), (0, y, 0.4), ortho=8.0, clip=(30.0, 80), res=(1200, 900))
shot('cut_top_mid', (0, -1.8, 30), (0, -1.8, 0), ortho=17.5, clip=(30 - 0.45, 80), res=(1400, 1300))


# ---------------------------------------------------------------------------------- v3 evidence shots
def reset_pose(names):
    for n in names:
        if n in O:
            o = O[n]
            o.rotation_mode = 'QUATERNION'
            o.rotation_quaternion = BASE_ROT[n].copy()
    bpy.context.view_layer.update()


BASE_ROT = {}
for o in O:
    o.rotation_mode = 'QUATERNION'
    BASE_ROT[o.name] = o.rotation_quaternion.copy()


def rot_local(name, axis, deg):
    if name in O:
        rotate_about_local(name, axis, deg)
        bpy.context.view_layer.update()


if 'cockpit_eye' in O:
    e = O['cockpit_eye'].matrix_world.translation.copy()
    shot('v3_cockpit_panel', e + Vector((0.12, 0.05, -0.05)), Vector((0.0, 4.24, 0.70)), lens=24, clip=(0.02, 50))
    shot('v3_quadrant', e + Vector((0.10, 0.05, -0.05)), Vector((0.0, 3.84, 0.36)), lens=24, clip=(0.02, 50))
    if not only or 'v3_quadrant_full_throttle' in only:
        for n in ('quadrant_throttle_L', 'quadrant_throttle_R'):
            rot_local(n, (1, 0, 0), -40)                  # Blender -40 about X = lever top forward (Unity +range)
        shot('v3_quadrant_full_throttle', (0.42, 3.40, 0.95), (0.0, 3.86, 0.38), lens=28, clip=(0.02, 50),
             hide=('cockpit_seat_R', 'cockpit_seat_L', 'canopy_glass'), exact=True)
        reset_pose(['quadrant_throttle_L', 'quadrant_throttle_R'])
    shot('v3_quadrant_idle', (0.42, 3.40, 0.95), (0.0, 3.86, 0.38), lens=28, clip=(0.02, 50),
         hide=('cockpit_seat_R', 'cockpit_seat_L', 'canopy_glass'), exact=True)
    movers = ['cockpit_column_L', 'cockpit_yoke_L', 'cockpit_column_R', 'cockpit_yoke_R', 'cockpit_rudder_pedals_L',
              'cockpit_rudder_pedals_R'] + [o.name for o in O if o.name.startswith('gauge_') and o.type == 'MESH']
    if not only or 'v3_controls_deflected' in only:
        rot_local('cockpit_column_L', (1, 0, 0), 12)      # Blender +12 about X = column top aft (pull)
        rot_local('cockpit_yoke_L', (1, 0, 0), 40)
        rot_local('cockpit_column_R', (1, 0, 0), -12)
        rot_local('cockpit_yoke_R', (1, 0, 0), -40)
        rot_local('cockpit_rudder_pedals_L', (1, 0, 0), 15)
        for n in [o.name for o in O if o.name.startswith('gauge_') and o.name.endswith(('_needle', '_card'))]:
            rot_local(n, (1, 0, 0), -110)
        shot('v3_controls_deflected', (0.55, 2.75, 1.05), (-0.05, 3.95, 0.45), lens=24, clip=(0.02, 50),
             hide=('canopy_glass', 'canopy_frame', 'hatch_cockpit_top', 'cockpit_seat_L', 'cockpit_seat_R'), exact=True)
        reset_pose(movers)
    shot('v3_controls_rest', (0.55, 2.75, 1.05), (-0.05, 3.95, 0.45), lens=24, clip=(0.02, 50),
         hide=('canopy_glass', 'canopy_frame', 'hatch_cockpit_top', 'cockpit_seat_L', 'cockpit_seat_R'), exact=True)
    # side cut through the left station (x < -0.08 visible): column + yoke + pedals at rest and fully deflected
    shot('v3_column_side_rest', (3.0, 3.85, 0.45), (-0.36, 3.85, 0.45), ortho=1.1, clip=(3.0 + 0.08, 50), res=(900, 900))
    if not only or 'v3_column_side_deflected' in only:
        rot_local('cockpit_column_L', (1, 0, 0), 12)
        rot_local('cockpit_yoke_L', (1, 0, 0), 45)
        rot_local('cockpit_rudder_pedals_L', (1, 0, 0), 15)
        shot('v3_column_side_deflected', (3.0, 3.85, 0.45), (-0.36, 3.85, 0.45), ortho=1.1, clip=(3.0 + 0.08, 50), res=(900, 900))
        reset_pose(movers)
        rot_local('cockpit_column_L', (1, 0, 0), -12)
        rot_local('cockpit_yoke_L', (1, 0, 0), -45)
        rot_local('cockpit_rudder_pedals_L', (1, 0, 0), -15)
        shot('v3_column_side_deflected_neg', (3.0, 3.85, 0.45), (-0.36, 3.85, 0.45), ortho=1.1, clip=(3.0 + 0.08, 50), res=(900, 900))
        reset_pose(movers)

shot('v3_canopy_close', (-1.9, 5.3, 2.1), (0, 3.55, 1.15), lens=45)
shot('v3_canopy_side', (-3.2, 3.4, 1.5), (0, 3.5, 1.2), lens=50)
shot('v3_canopy_top', (0.0, 3.6, 4.5), (0, 3.6, 1.2), lens=45)
if not only or 'v3_turret_top' in only:
    shot('v3_turret_top', (-1.9, 3.6, 2.4), (0, 1.85, 1.45), lens=40)
    rot_local('turret_dorsal', (0, 0, 1), 60)
    rot_local('turret_dorsal_guns', (1, 0, 0), 35)
    shot('v3_turret_top_aimed', (-1.9, 3.6, 2.4), (0, 1.85, 1.45), lens=40)
    reset_pose(['turret_dorsal', 'turret_dorsal_guns'])
    shot('v3_turret_top_cut', (0, 1.82, 6.0), (0, 1.82, 0), ortho=1.6, clip=(6.0 - 1.62, 50), res=(900, 900))
if not only or 'v3_tail_turret' in only:
    shot('v3_tail_turret', (-1.4, -11.2, 1.0), (0, -9.6, 0.45), lens=40)
    rot_local('tail_turret_az', (0, 0, 1), 18)
    rot_local('tail_guns', (1, 0, 0), 22)
    shot('v3_tail_turret_aimed', (-1.4, -11.2, 1.0), (0, -9.6, 0.45), lens=40)
    reset_pose(['tail_turret_az', 'tail_guns'])
    shot('v3_tail_cut', (6, -9.3, 0.5), (0, -9.3, 0.5), ortho=2.2, clip=(6.0, 50), res=(1100, 900))
if not only or 'v3_waist' in only:
    shot('v3_waist_L', (-2.6, -2.2, 0.6), (-0.7, -3.1, 0.25), lens=40)
    rot_local('waist_gun_L_az', (0, 0, 1), 30)
    rot_local('waist_gun_L', (1, 0, 0), 25)
    shot('v3_waist_L_aimed', (-2.6, -2.2, 0.6), (-0.7, -3.1, 0.25), lens=40)
    reset_pose(['waist_gun_L_az', 'waist_gun_L'])
    shot('v3_waist_inside', (0.4, -2.2, 0.45), (-0.7, -3.1, 0.25), lens=24, clip=(0.02, 50))
shot('v3_pylons_L', (-6.5, 2.4, -1.4), (-4.6, 0.1, 0.2), lens=40)
shot('v3_pylon_rail_close', (-4.1, 1.9, -0.25), (-4.6, 0.15, 0.25), lens=35)
shot('v3_pylon_wingrack_close', (-1.1, 1.8, -0.6), (-1.75, 0.2, 0.05), lens=35)
shot('v3_pylons_side', (-8.8, 0.15, 0.22), (-4.85, 0.15, 0.22), ortho=2.4, clip=(8.8 - 4.30, 50), res=(1200, 700))
if not only or 'v3_hatches_open' in only:
    for n in ('hatch_cockpit_top', 'hatch_entry_fwd', 'hatch_entry_rear', 'hatch_waist_L', 'hatch_waist_R'):
        if n in O:
            rot_local(n, (1, 0, 0), INFO[n]['open_deg_blender'])
    shot('v3_hatches_open', (-7.0, -0.6, -2.6), (0, -0.6, -0.2), lens=26)
    shot('v3_hatch_top_open', (-2.2, 5.0, 2.6), (0, 3.4, 1.3), lens=40)
    shot('v3_hatches_open_below', (0.0, -1.5, -8.0), (0, -1.5, 0.0), ortho=13, res=(900, 1500))
    reset_pose(['hatch_cockpit_top', 'hatch_entry_fwd', 'hatch_entry_rear', 'hatch_waist_L', 'hatch_waist_R'])
shot('v3_crew_cut', (8, -2.5, 0.5), (0, -2.5, 0.5), ortho=14.5, clip=(8.0, 60), res=(1800, 700))

# stock-mount PROXIES (bounding boxes measured from the AssetRipper meshes, no stock geometry): RocketPod1_single =
# rocketpodMount2 (x +-0.028, Unity y -0.081..0.055, z -0.638..0.498) + rocketpod1 at (0, -0.21, 0.19) (+-0.129,
# +-0.149, z -1.218..0.855); bomb_500_single = launchpylon1 at (0, -0.085, 0.065) (+-0.074, y -0.084..0.115,
# z -1.091..0.989) + bomb_500 at (0, -0.341, 0.102) (r 0.21, z -1.367..1.364). Blender local = (x, z_unity, y_unity).
PROXY_MAT = bpy.data.materials.new('proxy')
PROXY_MAT.diffuse_color = (0.75, 0.25, 0.15, 1)


def proxy_box(name, centre, lo, hi):
    import bmesh as _bm
    me = bpy.data.meshes.new(name)
    bm = _bm.new()
    vs = [bm.verts.new(Vector(centre) + Vector((x, y, z))) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([vs[i] for i in f])
    bm.to_mesh(me)
    bm.free()
    me.materials.append(PROXY_MAT)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def mount_proxies():
    made = []
    for o in [o for o in O if o.name.startswith('hp_rail_')]:
        p = o.matrix_world.translation
        made.append(proxy_box('_px_' + o.name, p, (-0.028, -0.638, -0.081), (0.028, 0.498, 0.055)))
        made.append(proxy_box('_px_pod_' + o.name, p + Vector((0, 0.19, -0.21)), (-0.129, -1.218, -0.149), (0.129, 0.855, 0.149)))
    for o in [o for o in O if o.name.startswith('hp_wingrack_')]:
        p = o.matrix_world.translation
        made.append(proxy_box('_px_' + o.name, p + Vector((0, 0.065, -0.085)), (-0.074, -1.091, -0.084), (0.074, 0.989, 0.115)))
        made.append(proxy_box('_px_bomb_' + o.name, p + Vector((0, 0.102, -0.341)), (-0.21, -1.367, -0.21), (0.21, 1.364, 0.227)))
    if 'hp_bombbay' in O:
        p = O['hp_bombbay'].matrix_world.translation
        for x in (-0.2, 0.2):
            made.append(proxy_box('_px_bay%+.1f' % x, p + Vector((x, -0.019, -0.15)), (-0.21, -1.367, -0.21), (0.21, 1.364, 0.227)))
    return made


if not only or 'v3_pylons_proxies' in only:
    PX = mount_proxies()
    sh.show_backface_culling = False          # proxies are hollow boxes; show their inner faces in the cuts
    shot('v3_pylons_proxies', (-8.8, 0.15, 0.22), (-4.85, 0.15, 0.22), ortho=2.4, clip=(8.8 - 4.30, 50), res=(1200, 700))
    shot('v3_pylon_rail_proxy_close', (-5.4, 1.6, -0.6), (-4.6, 0.15, 0.2), lens=35)
    shot('v3_wingrack_proxy', (-0.95, 3.2, -1.25), (-1.75, 0.2, -0.05), lens=35)
    shot('v3_bombbay_proxy_below', (0.0, -0.08, -6.0), (0, -0.08, 0.0), ortho=3.6, res=(900, 1000),
         hide=('bomb_door_L', 'bomb_door_R'), exact=True)
    shot('v3_bombbay_proxy_oblique', (1.6, -2.6, -2.2), (0, -0.1, -0.3), lens=30, hide=('bomb_door_L', 'bomb_door_R'), exact=True)
    sh.show_backface_culling = True
    for ob in PX:
        bpy.data.objects.remove(ob)

# torn breaks: the piece that stays and the piece that leaves
shot('v3_tear_wing_inner', (-5.4, 2.0, 1.3), (-2.95, -0.4, 0.45), lens=35, hide=('wing_outer_L', 'nacelle_L'))
keep = {d.name for d in descendants(O['wing_outer_L'])}
shot('v3_tear_wing_outer_piece', (-1.6, 1.4, 1.2), (-3.3, -0.4, 0.45), lens=35,
     hide=[o.name for o in O if o.type == 'MESH' and o.name not in keep], exact=True)
shot('v3_tear_wingtip', (-7.2, 1.3, 1.2), (-6.15, -0.3, 0.5), lens=35, hide=('wing_tip_L',))
shot('v3_tear_fus_center', (-1.9, -4.6, 1.0), (0, -1.8, 0.25), lens=35, hide=('fus_rear',))
keep = {d.name for d in descendants(O['fus_rear'])}
shot('v3_tear_fus_rear_piece', (-1.9, 0.9, 1.0), (0, -1.9, 0.25), lens=35,
     hide=[o.name for o in O if o.type == 'MESH' and o.name not in keep], exact=True)
shot('v3_tear_nose', (1.9, 6.6, 0.9), (0, 4.5, 0.2), lens=35, hide=('fus_nose',))
shot('v3_tear_tail', (-1.8, -3.9, 1.1), (0, -6.1, 0.3), lens=35, hide=('fus_tail',))
shot('v3_cannon', (-1.6, 3.3, -1.2), (-0.40, 3.4, -0.3), lens=35, hide=('fus_cockpit', 'fus_nose'), exact=True)
# prop blur meshes (extras collection) placed on the left hub for the picture
if 'propdisc_full' in O and (not only or 'v3_prop_disc' in only):
    hub = O['prop_hub_L'].matrix_world.translation.copy()
    for n, dy in (('propdisc_full', 0.02), ('propdisc_blur', 0.0)):
        O[n].location = hub + Vector((0, dy, 0))
        O[n].hide_render = False
    for n in ('prop_L_blade1', 'prop_L_blade2', 'prop_L_blade3'):
        O[n].hide_render = True
    O['propdisc_blur'].hide_render = True
    shot('v3_prop_disc_full', (-6.2, 7.6, 1.2), (-2.95, 2.9, 0.0), lens=40)
    O['propdisc_blur'].hide_render = False
    O['propdisc_full'].hide_render = True
    shot('v3_prop_disc_blur', (-6.2, 7.6, 1.2), (-2.95, 2.9, 0.0), lens=40)
    for n in ('prop_L_blade1', 'prop_L_blade2', 'prop_L_blade3', 'propdisc_full'):
        O[n].hide_render = False
    for n in ('propdisc_full', 'propdisc_blur'):
        O[n].location = Vector((0, 0, -50))

# bomb bay open (doors rotated by their recorded open angle)
if not only or 'bombbay_open' in only:
    for n in ('bomb_door_L', 'bomb_door_R'):
        inf = INFO[n]
        rotate_about_world_axis(n, inf['hinge_axis'], inf['open_deg'])
    shot('bombbay_open', (-3.5, -3.5, -4.5), (0, -0.1, -0.4), lens=35)
    shot('bombbay_open_below', (0, -0.1, -9), (0, -0.1, 0), ortho=6.0, res=(1000, 1000))
    bpy.ops.ed.undo_push()

# livery atlas layout: one flat object per source object from its `livery` UVs (paint faces)
if not only or 'livery_layout' in only:
    made = []
    for o in [o for o in O if o.type == 'MESH']:
        me = o.data
        if 'livery' not in me.uv_layers:
            continue
        lay = me.uv_layers['livery'].data
        verts, faces = [], []
        for p in me.polygons:
            m = me.materials[p.material_index]
            if not m or m.name != 'paint':
                continue
            idx = []
            for li in p.loop_indices:
                uvv = lay[li].uv
                verts.append((uvv.x * 10, uvv.y * 10, 50.0))
                idx.append(len(verts) - 1)
            faces.append(idx)
        if not faces:
            continue
        nm = bpy.data.meshes.new('uv_' + o.name)
        nm.from_pydata(verts, [], faces)
        ob = bpy.data.objects.new('uv_' + o.name, nm)
        scene.collection.objects.link(ob)
        made.append(ob)
    sh.color_type = 'RANDOM'
    sh.show_backface_culling = False
    shot('livery_layout', (5, 5, 80), (5, 5, 50), ortho=10.2, clip=(1, 100), res=(1600, 1600),
         hide=[o.name for o in O if o.type == 'MESH' and o not in made], exact=True)
    sh.color_type = 'MATERIAL'
    sh.show_backface_culling = True
    for ob in made:
        bpy.data.objects.remove(ob)

# retracted gear (struts by their retract angle, doors closed)
if not only or 'gear_retracted' in only:
    bpy.ops.wm.open_mainfile(filepath=blend)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.show_backface_culling = True
    sh.background_type = 'VIEWPORT'; sh.background_color = (0.55, 0.6, 0.65)
    cam_data = bpy.data.cameras.new('cam2'); cam = bpy.data.objects.new('cam2', cam_data)
    scene.collection.objects.link(cam); scene.camera = cam
    O = bpy.data.objects
    INFO = {o.name: (json.loads(o['b25_info']) if o.get('b25_info') else {}) for o in O}
    for n in ('gear_main_L_strut', 'gear_main_R_strut', 'gear_nose_strut'):
        rotate_about_world_axis(n, (1, 0, 0), INFO[n]['retract_deg_blender'])
    for n in [o.name for o in O if o.name.startswith('gear_door')]:
        O[n].rotation_mode = 'QUATERNION'
        O[n].rotation_quaternion = Quaternion()
    bpy.context.view_layer.update()
    shot('gear_retracted_ext', (-9.5, 4.0, -2.5), (-1.5, 0.5, -0.4), lens=35)
    shot('gear_retracted_cut_nacelleL', (-30, -0.6, 0.0), (-3.25, -0.6, 0.0), ortho=6.0, clip=(30 - 3.25, 80))
    shot('gear_retracted_cut_centre', (30, 2.8, 0.0), (0, 2.8, 0.0), ortho=4.5, clip=(30.0, 80))
print('DONE')
