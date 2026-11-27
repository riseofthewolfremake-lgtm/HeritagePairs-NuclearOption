"""Review renders of the A6M2 model at the War Thunder reference camera angles (round 1).

  blender --background assets/model_a6m2/a6m2.blend --python blender/a6m2/render_a6m2.py -- --out <dir> [--mode views|silhouettes]

views: the same direction / lens / margin / fit rule as nuclearoption-ref/refs/wt_a6m2/scripts/render_ref.py (directions converted to our
frame: WT (x fwd, y left, z up) -> ours (x = -y, y = x, z)), 1600 x 1000, EEVEE, light grey world + four suns; gear-down and gear-up
(the legs rotated by their retract angle about the contract axis, doors closed) variants. The .blend is not saved.
silhouettes: flat white masks with FIXED orthographic cameras (side / top / front) for the numeric outline comparison
(study/a6m2/r1/wt_silhouettes.py renders the reference with the same cameras).
"""
import bpy, sys, os, math, json
from mathutils import Vector, Matrix, Quaternion
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1])
MODE = argv[argv.index('--mode') + 1] if '--mode' in argv else 'views'
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene

# fixed silhouette cameras (ours frame): name -> (view direction from the camera, up, centre, ortho scale)
SIL = {'side': (Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, -2.10, 0.0)), 10.0),
       'top': (Vector((0, 0, -1)), Vector((0, 1, 0)), Vector((0, -2.10, 0.0)), 13.0),
       'front': (Vector((0, -1, 0)), Vector((0, 0, 1)), Vector((0, 0, -0.10)), 13.0)}


def wt_dir(d):
    return Vector((-d[1], d[0], d[2]))


VIEWS = [   # (file, WT direction, ortho, lens, margin, up(WT), gear, fit objects or None)
    ('ext_34_front_left_gear_down', (1.0, 0.95, 0.45), False, 50, 1.08, None, 'down', None),
    ('ext_34_rear_right_stored', (-1.0, -0.95, 0.5), False, 50, 1.08, None, 'up', None),
    ('ext_side_left_gear_down', (0, 1, 0), True, 50, 1.05, None, 'down', None),
    ('ext_side_left_stored', (0, 1, 0), True, 50, 1.05, None, 'up', None),
    ('ext_top', (0, 0, 1), True, 50, 1.04, (1, 0, 0), 'up', None),
    ('ext_front_gear_down', (1, 0, 0), True, 50, 1.04, None, 'down', None),
    ('ext_bottom_gear_down', (0, 0, -1), True, 50, 1.04, (1, 0, 0), 'down', None),
    ('ext_bottom_stored', (0, 0, -1), True, 50, 1.04, (1, 0, 0), 'up', None),
    ('closeup_cowl_prop', (1.0, 0.75, 0.3), False, 50, 1.10, None, 'down', ['prop_hub', 'prop_blade_0', 'prop_blade_1', 'prop_blade_2']),
    ('closeup_main_gear_left', (0.9, 0.9, -0.12), False, 50, 1.25, None, 'down', ['gear_main_L_strut', 'gear_main_L_wheel', 'gear_door_L']),
    ('closeup_main_gear_left_up', (0.9, 0.9, -0.40), False, 50, 1.6, None, 'up', ['gear_main_L_strut', 'gear_main_L_wheel', 'gear_door_L']),
    ('closeup_tail_hook', (-0.6, 0.9, -0.25), False, 50, 1.15, None, 'down', ['fin', 'rudder', 'stab_L', 'tailhook', 'gear_tail_strut']),
    ('closeup_nose_side', (0, 1, 0.0), False, 50, 1.15, None, 'down', ['prop_hub', 'fus_engine']),
    ('ext_34_rear_right_gear_down', (-1.0, -0.95, 0.5), False, 50, 1.08, None, 'down', None),
    ('closeup_stores', (0.9, 0.9, -0.30), False, 50, 1.25, None, 'down', ['store_no6_bomb', 'store_no6_rack', 'store_tokko_bomb', 'store_tokko_rack', 'wing_inner_R']),
    ('closeup_cowl_prop_40', (1.0, 0.75, 0.3), False, 50, 1.10, None, 'down', ['prop_hub', 'prop_blade_0', 'prop_blade_1', 'prop_blade_2']),
    ('dbg_root_top', (0.2, 0.1, 1), False, 50, 1.1, None, 'down', ['wing_C', 'wing_inner_L', 'wing_inner_R', 'fillet_L', 'fillet_R']),
    ('dbg_root_bottom', (0.1, 0.2, -1), False, 50, 1.1, None, 'up', ['wing_C', 'wing_inner_L', 'wing_inner_R']),
    ('dbg_root_bottom_down', (0.1, 0.2, -1), False, 50, 1.1, None, 'down', ['wing_C', 'wing_inner_L', 'wing_inner_R']),
    ('dbg_tail_side', (0, 1, 0.1), False, 50, 1.1, None, 'down', ['fin', 'rudder', 'fus_tail', 'gear_tail_strut', 'tailhook']),
]


def contract():
    p = os.path.join(os.path.dirname(bpy.data.filepath), 'a6m2_contract.json')
    return json.load(open(p))


def set_gear(state):
    """'down' = as built; 'up' = legs rotated by the retract angle about their axis, doors closed."""
    for L in ('L', 'R'):
        leg = bpy.data.objects[f'gear_main_{L}_strut']
        info = json.loads(leg['b25_info'])
        if '_rest' not in leg:
            leg['_rest'] = [list(r) for r in leg.matrix_world]
        door = bpy.data.objects[f'gear_door_{L}']
        dinfo = json.loads(door['b25_info'])
        if '_rest' not in door:
            door['_rest'] = [list(r) for r in door.matrix_world]
        Ml = Matrix(leg['_rest'])
        Md = Matrix(door['_rest'])
        if state == 'up':
            piv = Vector(info['pivot']); ax = Vector(info['retract_axis_world'])
            R = Matrix.Translation(piv) @ Quaternion(ax, math.radians(info['retract_deg'])).to_matrix().to_4x4() @ Matrix.Translation(-piv)
            leg.matrix_world = R @ Ml
            hp = Md.translation.copy(); hax = Vector(dinfo['hinge_axis'])
            Rd = Matrix.Translation(hp) @ Quaternion(hax, -math.radians(dinfo['open_deg'])).to_matrix().to_4x4() @ Matrix.Translation(-hp)
            door.matrix_world = Rd @ Md
        else:
            leg.matrix_world = Ml
            door.matrix_world = Md
    bpy.context.view_layer.update()


def setup_render():
    sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    sc.view_settings.view_transform = 'AgX'
    w = bpy.data.worlds.new('w'); sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.62, 0.62, 0.62, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
    for name, rot, e in (('key', (50, 0, 40), 3.0), ('fill', (60, 0, -130), 1.2), ('rim', (-60, 0, 180), 1.5), ('under', (180, 0, 0), 0.6)):
        l = bpy.data.lights.new(name, 'SUN'); l.energy = e
        o = bpy.data.objects.new(name, l); sc.collection.objects.link(o)
        o.rotation_euler = [math.radians(a) for a in rot]
    for m in bpy.data.materials:
        if m.name == 'glass':
            m.diffuse_color = (0.93, 0.96, 0.98, 0.07)
    for o in bpy.data.objects:                 # r8: the cockpit-view canopy only shows in the cockpit view (cockpit_views swaps)
        if o.name.startswith('ckcanopy_'):
            o.hide_render = True


def look_rot(view, up):
    z = -Vector(view).normalized()
    y = Vector(up); y = (y - z * y.dot(z)).normalized()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed().to_euler()


def world_pts(objs):
    pts = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type != 'MESH' or o.hide_render:
            continue
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        pts += [o.matrix_world @ v.co for v in list(me.vertices)[::3]]
        e.to_mesh_clear()
    return pts


def fit(cam, direction, pts, margin, up_hint):
    d = Vector(direction).normalized(); v = -d
    eul = look_rot(v, up_hint or Vector((0, 0, 1)))
    R = eul.to_matrix(); ax, ay = R.col[0], R.col[1]
    c = sum(pts, Vector()) / len(pts)
    w, h = sc.render.resolution_x, sc.render.resolution_y
    xs = [(p - c).dot(ax) for p in pts]; ys = [(p - c).dot(ay) for p in pts]
    c = c + ax * (max(xs) + min(xs)) / 2 + ay * (max(ys) + min(ys)) / 2
    cam.rotation_euler = eul
    if cam.data.type == 'ORTHO':
        cam.data.ortho_scale = max(max(xs) - min(xs), (max(ys) - min(ys)) * w / h) * margin
        cam.location = c + d * 40
        return
    th = math.tan(cam.data.angle_x / 2) / margin; tv = th * h / w
    D = 0.0
    for p in pts:
        r = p - c; f = r.dot(v)
        D = max(D, abs(r.dot(ax)) / th - f, abs(r.dot(ay)) / tv - f)
    cam.location = c - v * D
    tan_h = math.tan(cam.data.angle_x / 2); tan_v = tan_h * h / w
    for _ in range(8):
        Minv = (Matrix.Translation(cam.location) @ R.to_4x4()).inverted()
        X, Y = [], []
        for p in pts:
            q = Minv @ p
            X.append(q.x / -q.z / (2 * tan_h) + 0.5); Y.append(q.y / -q.z / (2 * tan_v) + 0.5)
        dist = (c - cam.location).dot(v)
        dx, dy = (min(X) + max(X)) / 2 - 0.5, (min(Y) + max(Y)) / 2 - 0.5
        size = max(max(X) - min(X), max(Y) - min(Y))
        cam.location = cam.location + ax * dx * 2 * dist * tan_h + ay * dy * 2 * dist * tan_v
        cam.location = cam.location + v * dist * (1 - size * margin)


def camera(ortho, lens):
    cam = bpy.data.objects.get('rcam')
    if cam is None:
        cam = bpy.data.objects.new('rcam', bpy.data.cameras.new('rcam')); sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    cam.data.lens = lens; cam.data.sensor_fit = 'HORIZONTAL'; cam.data.sensor_width = 36
    cam.data.clip_start, cam.data.clip_end = 0.05, 200
    sc.camera = cam
    return cam


def render(name):
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)
    print('[render]', name)


STORES = '--stores' in argv          # round 2: the store models (moved into mount prefabs by Unity) are hidden unless --stores
for _o in bpy.data.objects:
    if _o.name.startswith('store_'):
        _o.hide_render = not STORES


def apply_textures():
    """r6: the IJN skin atlas on paint, the dial atlas and our cockpit tiles - for the exterior views too (r4/r4c views were untextured)."""
    tex_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'assets', 'textures_a6m2')
    for mname, fn in (('gauges', 'a6m2_gauges.png'), ('paint', 'a6m2_skin_b.png'), ('prop', 'a6m2_prop_tips.png')):      # atlases on the livery UV (Unity UV0)
        m = bpy.data.materials.get(mname)
        if m is None or not os.path.exists(os.path.join(tex_dir, fn)):
            continue
        m.use_nodes = True
        nt = m.node_tree
        bsdf = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'][0]
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(tex_dir, fn), check_existing=True)
        uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'livery'
        nt.links.new(uvn.outputs['UV'], tn.inputs['Vector']); nt.links.new(tn.outputs['Color'], bsdf.inputs['Base Color'])
    for mname, fn in (('interior', 'a6m2_tile_ckgreen'), ('ck_panel', 'a6m2_tile_ckpanel'), ('ck_gun', 'a6m2_tile_ckgun')):   # r4c: our tiles on the detail UV (Unity UV1 -> UV0)
        m = bpy.data.materials.get(mname)
        if m is None or not os.path.exists(os.path.join(tex_dir, fn + '_b.png')):
            continue
        m.use_nodes = True
        nt = m.node_tree
        bsdf = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'][0]
        uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'detail'
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = bpy.data.images.load(os.path.join(tex_dir, fn + '_b.png'), check_existing=True)
        nt.links.new(uvn.outputs['UV'], tn.inputs['Vector']); nt.links.new(tn.outputs['Color'], bsdf.inputs['Base Color'])
        nn = nt.nodes.new('ShaderNodeTexImage'); nn.image = bpy.data.images.load(os.path.join(tex_dir, fn + '_n.png'), check_existing=True)
        nn.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(uvn.outputs['UV'], nn.inputs['Vector']); nt.links.new(nn.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    rm = bpy.data.materials.get('reticle')
    if rm is not None and rm.use_nodes:
        b_ = [n for n in rm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
        b_.inputs['Emission Color'].default_value = (1.0, 0.45, 0.10, 1); b_.inputs['Emission Strength'].default_value = 3.0


def views():
    setup_render()
    apply_textures()
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render]
    only = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
    for name, d, ortho, lens, margin, up, gear, fitobjs in VIEWS:
        if only and name not in only:
            continue
        set_gear(gear)
        cam = camera(ortho, lens)
        objs = [bpy.data.objects[n] for n in fitobjs] if fitobjs else meshes
        fit(cam, wt_dir(d), world_pts(objs), margin, wt_dir(up) if up else None)
        render(name)
    set_gear('down')


def silhouettes():
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = 2000, 1250
    sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'SINGLE'
    sc.display.shading.single_color = (1, 1, 1)
    sc.display.shading.background_type = 'VIEWPORT'; sc.display.shading.background_color = (0, 0, 0)
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('w'); sc.world = w; w.color = (0, 0, 0)
    for gear in ('down',):
        set_gear(gear)
        for k, (vd, up, c, s) in SIL.items():
            cam = camera(True, 50)
            cam.rotation_euler = look_rot(vd, up)
            cam.location = c - vd * 40
            cam.data.ortho_scale = s
            render(f'sil_{k}_ours')


# round 4: cockpit cameras = render_ref.py's ckpt shots (WT frame: x fwd, y left, z up), converted with a6m2_spec.wt_to_ours
WT_EYE = (-1.025, -0.032, 0.79)
CKPT = [   # (file, location (WT), target (WT), lens, hide canopy)
    ('cockpit_pilot_eye_forward', WT_EYE, (WT_EYE[0] + 1.0, WT_EYE[1], WT_EYE[2] - 0.16), 16, False),
    ('cockpit_left_console', (WT_EYE[0] + 0.05, WT_EYE[1] + 0.02, WT_EYE[2] - 0.02), (-0.68, 0.32, 0.28), 18, False),
    ('cockpit_right_console', (WT_EYE[0] + 0.05, WT_EYE[1] - 0.02, WT_EYE[2] - 0.02), (-0.55, -0.32, 0.22), 18, False),
    ('cockpit_wide_from_above_no_canopy', (-2.45, 0.5, 2.25), (-0.55, 0, 0.3), 24, True),
]


def cockpit_views():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import a6m2_spec as S
    setup_render()
    set_gear('down')
    apply_textures()
    only = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
    for name, loc, tgt, lens, hide in CKPT:
        if only and name not in only:
            continue
        for o in bpy.data.objects:
            if o.name.startswith('canopy_'):
                o.hide_render = True                 # r8: exterior canopy hidden in the cockpit view (exteriorRenderers)
            if o.name.startswith('ckcanopy_'):
                o.hide_render = hide
        cam = camera(False, lens)
        cam.data.clip_start = 0.02
        L_, T_ = Vector(S.wt_to_ours(loc, False)), Vector(S.wt_to_ours(tgt, False))
        cam.location = L_
        cam.rotation_euler = look_rot(T_ - L_, Vector((0, 0, 1)))
        render(name)
    for o in bpy.data.objects:
        if o.name.startswith('canopy_'):
            o.hide_render = False


if MODE == 'views':
    views()
elif MODE == 'cockpit':
    cockpit_views()
else:
    silhouettes()
