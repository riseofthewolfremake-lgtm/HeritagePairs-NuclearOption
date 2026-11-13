"""B-17G review renders (milestone 1). Output goes OUTSIDE the repo (nuclearoption-ref/study/b17g/renders/m1).

  blender --background assets/model_b17g/b17g.blend --python blender/b17g/render_b17g.py -- --out <dir> --tex assets/textures_b17g
          [--ref <WT obj>] [--barrel <stock barrel obj from blender/v2/study/stock.py, scratch only>] [--only views,props,...]

Every review view is rendered for our model and, with --ref, for the War Thunder reference from the SAME camera (the reference is
imported in memory only, scaled to the real span; its render stays outside the repo). The stock 12.7 mm barrel (the mesh the Unity
build puts on every gun slot) is shown on the gun slots when --barrel is given (decoded to scratch, never saved in the .blend).
"""
import bpy, sys, os, math, json
from mathutils import Vector as V, Euler, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
OUT, TEX, REF, BARREL = os.path.abspath(arg('--out', '.')), arg('--tex'), arg('--ref'), arg('--barrel')
ONLY = set(arg('--only', 'views,props,gear,bay,turrets,liveries,cockpit').split(','))
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
K = 31.62 / 31.258
ours = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.endswith('_hullsrc')]
for o in bpy.data.objects:          # 1.8.3 collider sources (deleted in Unity) are never drawn
    if o.name.endswith('_hullsrc'):
        o.hide_render = True

sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
w = sc.world or bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get('Background'); bg.inputs[0].default_value = (0.62, 0.70, 0.80, 1); bg.inputs[1].default_value = 0.9
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.5; sun.rotation_euler = Euler((math.radians(40), math.radians(15), math.radians(35)))
fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill)
fill.data.energy = 1.2; fill.rotation_euler = Euler((math.radians(130), 0, math.radians(-140)))
try:
    sc.view_settings.view_transform = 'Standard'
except Exception:
    pass


def img(path, nonc=False):
    if not path or not os.path.exists(path):
        return None
    im = bpy.data.images.load(path, check_existing=True)
    if nonc:
        im.colorspace_settings.name = 'Non-Color'
    return im


def set_tex(mat, b, n=None, m=None, uv='livery', scale=1.0):
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        if nd.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(nd)
    bs = nt.nodes.get('Principled BSDF')
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uv
    src = uvn.outputs[0]
    if scale != 1.0:
        mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale, scale, 1)
        nt.links.new(src, mp.inputs[0]); src = mp.outputs[0]
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = b; nt.links.new(src, t.inputs[0]); nt.links.new(t.outputs[0], bs.inputs['Base Color'])
    if n is not None:
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = n; nt.links.new(src, tn.inputs[0])
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.uv_map = uv
        nt.links.new(tn.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], bs.inputs['Normal'])
    if m is not None:
        tm = nt.nodes.new('ShaderNodeTexImage'); tm.image = m; nt.links.new(src, tm.inputs[0])
        sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(tm.outputs[0], sp.inputs[0])
        nt.links.new(sp.outputs[0], bs.inputs['Metallic'])
        inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        nt.links.new(tm.outputs[1], inv.inputs[1]); nt.links.new(inv.outputs[0], bs.inputs['Roughness'])


T = os.path.abspath(TEX) if TEX else None
LIV = json.load(open(os.path.join(T, 'b17g_liveries.json'))) if T and os.path.exists(os.path.join(T, 'b17g_liveries.json')) else {}
paint = bpy.data.materials.get('paint')
NMAP = img(os.path.join(T, 'b17g_skin_n.png'), True) if T else None
if T:
    for k in ('structure', 'interior', 'well', 'gear', 'tyre', 'cowl', 'turret'):
        mt = bpy.data.materials.get(k); b = img(os.path.join(T, f'b17g_tile_{k}_b.png'))
        if mt and b:
            set_tex(mt, b, img(os.path.join(T, f'b17g_tile_{k}_n.png'), True), uv='detail', scale=1.0)


gl = bpy.data.materials.get('glass')      # glazing reads as glass: faint blue tint, glossy coat highlight
if gl:
    gl.use_nodes = True
    bs = gl.node_tree.nodes.get('Principled BSDF')
    for k, v in (('Base Color', (0.80, 0.88, 0.95, 1)), ('Alpha', 0.20), ('Roughness', 0.03), ('Coat Weight', 1.0), ('Coat Roughness', 0.02), ('Specular IOR Level', 1.0)):
        try:
            bs.inputs[k].default_value = v
        except Exception:
            pass
    try:
        gl.surface_render_method = 'BLENDED'
    except Exception:
        pass
for attr, val in (('use_raytracing', True), ('use_gtao', True)):
    try:
        setattr(sc.eevee, attr, val)
    except Exception:
        pass


def use_livery(key):
    if key in LIV:
        set_tex(paint, img(os.path.join(T, LIV[key]['texture'])), NMAP, img(os.path.join(T, LIV[key]['metal']), True))


# stock barrel on every gun slot (render only)
if BARREL and os.path.exists(BARREL):
    vs, fs = [], []
    for l in open(BARREL):
        if l.startswith('v '):
            x, y, z = map(float, l.split()[1:4]); vs.append((-x, y, z))          # Unity (left-handed) -> slot frame (x left)
        elif l.startswith('f '):
            fs.append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
    me = bpy.data.meshes.new('stock_barrel'); me.from_pydata(vs, [], fs)
    mb = bpy.data.materials.new('barrel'); mb.use_nodes = True; mb.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.04, 0.04, 0.045, 1); me.materials.append(mb)
    for o in list(bpy.data.objects):
        if o.type == 'EMPTY' and '_gun' in o.name:
            b = bpy.data.objects.new('barrel_' + o.name, me); sc.collection.objects.link(b)
            b.parent = o; b.matrix_parent_inverse = Matrix.Identity(4)
            # slot frame: local x = side, y = up, z = fwd (contract); the stock mesh is +Z fwd, +Y up
            b.matrix_basis = Matrix.Identity(4)

ref = None
if REF:
    verts, faces = [], []
    for l in open(REF, encoding='utf-8', errors='ignore'):
        if l.startswith('v '):
            x, y, z = map(float, l.split()[1:4]); verts.append((-x * K, z * K, y * K))
        elif l.startswith('f '):
            faces.append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
    me = bpy.data.meshes.new('wt_ref'); me.from_pydata(verts, [], faces)
    mr = bpy.data.materials.new('wt_grey'); mr.use_nodes = True
    mr.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.62, 0.63, 0.65, 1)
    me.materials.append(mr)
    ref = bpy.data.objects.new('wt_ref', me); sc.collection.objects.link(ref); ref.hide_render = True


def cam(loc, tgt, lens=40, ortho=None):
    c = bpy.data.cameras.new('c'); c.clip_start = 0.02; c.clip_end = 400
    if ortho:
        c.type = 'ORTHO'; c.ortho_scale = ortho
    else:
        c.lens = lens
    o = bpy.data.objects.new('c', c); sc.collection.objects.link(o)
    o.location = V(loc); o.rotation_euler = (V(tgt) - V(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def shot(name, c, res=(1600, 1000), with_ref=True):
    sc.camera = c; sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, f'{name}_ours.png'); bpy.ops.render.render(write_still=True)
    if ref is not None and with_ref:
        hide = {o: o.hide_render for o in bpy.data.objects}
        for o in bpy.data.objects:
            if o.type in ('MESH',) and o is not ref:
                o.hide_render = True
        ref.hide_render = False
        sc.render.filepath = os.path.join(OUT, f'{name}_ref.png'); bpy.ops.render.render(write_still=True)
        for o, h in hide.items():
            o.hide_render = h
        ref.hide_render = True
    print('[render]', name)


def set_gear(f):
    """f = 0 down, 1 up (fold about the leg frame's local X, as the Unity LandingGear hinge)."""
    for o in bpy.data.objects:
        info = json.loads(o.get('b25_info') or '{}') if o.get('b25_info') else {}
        if info.get('kind') == 'gear':
            deg = info['fold_deg'] * (1 if info.get('fold_sense') == 'forward-up' else -1)
            o.rotation_euler = Euler((math.radians(deg * f), 0, 0))
    bpy.context.view_layer.update()


def set_bay(open_):
    for o in bpy.data.objects:
        if o.name.startswith('bay_door_'):
            info = json.loads(o['b25_info'])
            o.rotation_euler = Euler((0, math.radians(info['open_deg'] * (1 if open_ else 0)), 0))
    bpy.context.view_layer.update()


first = 'usaaf_nm' if 'usaaf_nm' in LIV else (list(LIV)[0] if LIV else None)
if first:
    use_livery(first)
if 'views' in ONLY:
    for n, (loc, tgt, lens, ortho) in {'side': ((45, -4, 0.8), (0, -4, 0.8), 50, 26), 'top': ((0, -4, 50), (0, -4.0001, 0), 50, 34),
                                        'front': ((0, 45, 0.6), (0, 0, 0.6), 50, 34), '34': ((17, 19, 7), (0, -2, 0.5), 35, None),
                                        'below': ((12, -4, -24), (0, -3, 0), 40, None)}.items():
        shot('view_' + n, cam(loc, tgt, lens, ortho))
if 'props' in ONLY:
    shot('prop_front', cam((3.1, 8.5, 0.6), (3.1, 4.6, 0.05), 40))
    shot('prop_back', cam((4.6, 1.0, 1.6), (3.1, 4.6, 0.05), 40))
if 'gear' in ONLY:
    for f, nm in ((0.0, 'down'), (0.5, 'mid'), (1.0, 'up')):
        set_gear(f)
        shot('gear_' + nm, cam((8.5, 6.5, -1.6), (3.2, 2.0, -0.9), 35), with_ref=(nm == 'up'))
        shot('gear_side_' + nm, cam((12, 2.0, -1.0), (3.2, 1.8, -1.0), 50), with_ref=(nm == 'up'))
        shot('tailwheel_' + nm, cam((3.5, -7.5, -0.6), (0, -9.6, -0.1), 40), with_ref=(nm == 'up'))
    set_gear(0.0)
if 'tailsteer' in ONLY:     # round 3: the tyre spins alone; tyre + fork steer about the vertical through the axle
    wt, fk = bpy.data.objects.get('wheel_tail'), bpy.data.objects.get('fork_tail')
    shot('tailwheel_close_rest', cam((1.6, -8.6, -0.35), (0, -9.95, -0.30), 45), with_ref=False)
    if wt and fk:
        ax = wt.matrix_world.translation.copy()
        Rz = Matrix.Translation(ax) @ Matrix.Rotation(math.radians(30), 4, 'Z') @ Matrix.Translation(-ax)
        w0, f0 = wt.matrix_world.copy(), fk.matrix_world.copy()
        wt.matrix_world = Rz @ w0 @ Matrix.Rotation(math.radians(70), 4, 'X'); fk.matrix_world = Rz @ f0
        bpy.context.view_layer.update()
        shot('tailwheel_close_steer30_spin70', cam((1.6, -8.6, -0.35), (0, -9.95, -0.30), 45), with_ref=False)
        wt.matrix_world, fk.matrix_world = w0, f0
        bpy.context.view_layer.update()
if 'bay' in ONLY:
    set_bay(True)
    shot('bay_open', cam((3.0, 3.5, -5.5), (0, 0.3, -0.4), 30), with_ref=False)
    set_bay(False)
    shot('bay_closed', cam((3.0, 3.5, -5.5), (0, 0.3, -0.4), 30))
if 'turrets' in ONLY:
    for n, (loc, tgt) in {'chin': ((2.2, 8.8, -0.9), (0, 6.2, -0.55)), 'top': ((3.0, 4.5, 3.6), (0, 2.1, 2.2)), 'ball': ((2.6, -1.4, -2.0), (0, -3.95, -0.8)),
                          'tail': ((2.6, -17.6, 1.6), (0, -14.9, 0.85)), 'cheek': ((3.0, 8.0, 1.4), (0, 6.1, 0.6)), 'waist_R': ((4.0, -4.0, 1.6), (1.0, -5.2, 0.7)),
                          'waist_L': ((-4.0, -5.5, 1.6), (-1.0, -6.7, 0.7)), 'radio': ((2.8, -1.0, 3.6), (0, -3.0, 1.6))}.items():
        shot('turret_' + n, cam(loc, tgt, 35), res=(1200, 900))
# fal props carry their own baked base colour (b17g_pr_<name>_b.png on the GLB UV)
if T:
    for m in bpy.data.materials:
        if m.name.startswith('pr_'):
            b = img(os.path.join(T, f'b17g_{m.name}_b.png'))
            if b:
                set_tex(m, b, uv='UVMap')
    for k in ('ck_panel', 'ck_wall', 'ck_od', 'ck_floor', 'ck_black', 'ck_bezel'):
        mt = bpy.data.materials.get(k); b = img(os.path.join(T, f'b17g_tile_{k}_b.png'))
        if mt and b:
            set_tex(mt, b, uv='detail', scale=2.0)
    g = bpy.data.materials.get('gauges'); b = img(os.path.join(T, 'b17g_gauges.png'))
    if g and b:
        set_tex(g, b, uv='livery')


POSE0 = {}


def pose(name, deg):
    """rotate about the object's own local +X from its rest rotation (the yoke frames are not identity)."""
    o = bpy.data.objects.get(name)
    if o is not None:
        if name not in POSE0:
            POSE0[name] = o.rotation_euler.to_quaternion()
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = POSE0[name] @ Euler((math.radians(deg), 0, 0)).to_quaternion()
        bpy.context.view_layer.update()


if 'cockpit' in ONLY:
    sun.data.energy = 4.0; sun.rotation_euler = Euler((math.radians(35), math.radians(-10), math.radians(160)))
    _h = os.path.dirname(os.path.abspath(__file__))
    for _d in (_h, os.path.join(_h, '..', 'v2'), os.path.join(_h, '..', 'nimrod')):
        if _d not in sys.path: sys.path.insert(0, os.path.abspath(_d))
    import b17g_cockpit as CKM
    eyeL = V(CKM.EYE_L); eyeR = V(CKM.EYE_R)
    def ckcam(loc, d, fov=80):
        c = cam(loc, V(loc) + V(d), 20)
        c.data.sensor_width = 36; c.data.lens = 18 / math.tan(math.radians(fov) / 2)
        return c
    for o in bpy.data.objects:          # cockpit view: no external glass reflections blocking (as the game's cockpit layer)
        pass
    shot('ck_pilot_eye', ckcam(eyeL, (0.15, 1.0, -0.42), 85), with_ref=False)
    shot('ck_copilot_eye', ckcam(eyeR, (-0.15, 1.0, -0.42), 85), with_ref=False)
    shot('ck_panel_close', ckcam(V((0.0, 3.50, 1.45)), (0, 1.0, -0.30), 75), with_ref=False)
    for k in range(1, 5):
        pose(f'cockpit_throttle_{k}', 0.0)
    shot('ck_pedestal_idle', ckcam(V((0.35, 3.40, 1.45)), (-0.40, 0.75, -0.75), 50), with_ref=False)
    for k in range(1, 5):
        pose(f'cockpit_throttle_{k}', -40.0)            # Blender -X rotation = grip forward (full throttle)
    shot('ck_pedestal_full', ckcam(V((0.35, 3.40, 1.45)), (-0.40, 0.75, -0.75), 50), with_ref=False)
    for k in range(1, 5):
        pose(f'cockpit_throttle_{k}', 0.0)
    pose('cockpit_yoke_L', 45.0); pose('cockpit_yoke_R', 45.0)
    shot('ck_yokes_roll', ckcam(V((0.0, 3.0, 1.75)), (0, 1.0, -0.42), 75), with_ref=False)
    pose('cockpit_yoke_L', 0.0); pose('cockpit_yoke_R', 0.0)
    shot('ck_interior_wide', ckcam(V((0.0, 2.99, 1.88)), (0, 1.0, -0.30), 100), with_ref=False)
    shot('ck_rear_bulkhead', ckcam(eyeL, (0.35, -1.0, -0.25), 85), with_ref=False)      # 1.6.1: the pilot's rear view (1.6.0: black void)


if 'm3' in ONLY:     # 1.6.1 review set
    def m3(name, loc, tgt, lens=40):
        shot(name, cam(loc, tgt, lens), res=(1400, 900), with_ref=False)
    # nose from 3 angles (anchored glazing, small framed cheek windows)
    m3('m3_nose_front34', (3.2, 9.6, 1.4), (0, 6.2, 0.45), 45)
    m3('m3_nose_side_R', (4.2, 6.0, 0.7), (0, 6.1, 0.45), 45)
    m3('m3_nose_under_L', (-2.4, 8.4, -1.6), (0, 6.2, 0.1), 45)
    # waist windows, radio hatch, tail position
    m3('m3_waist_R', (3.6, -4.2, 1.2), (0.9, -5.2, 0.7), 40)
    m3('m3_waist_L', (-3.6, -5.6, 1.2), (-0.9, -6.7, 0.7), 40)
    m3('m3_radio', (2.4, -0.8, 3.6), (0, -3.0, 1.7), 40)
    m3('m3_tail_rear34', (3.0, -18.6, 1.8), (0, -14.6, 0.9), 40)
    # tail wheel well (gear down) from behind and below
    m3('m3_tailwell', (1.2, -12.6, -1.8), (0, -9.8, -0.2), 40)
    # bomb bay doors closed from below (the 1.6.0 seam slit)
    m3('m3_bay_closed', (2.6, 2.8, -4.6), (0, 0.3, -0.5), 32)
    # NM livery with the shared (default livery) metal map, as the game renders every livery
    if 'usaaf_nm' in LIV:
        set_tex(paint, img(os.path.join(T, LIV['usaaf_nm']['texture'])), NMAP, img(os.path.join(T, LIV['usaaf_od']['metal']), True))
        m3('m3_nm_front34', (17, 19, 7), (0, -2, 0.5), 35)
        m3('m3_nm_side', (22, -3, 2.0), (0, -3, 0.6), 35)
        use_livery('usaaf_od')

if 'm4' in ONLY:     # 1.6.2 review set (NM livery: the shared metal map, as in game)
    if 'usaaf_nm' in LIV:
        set_tex(paint, img(os.path.join(T, LIV['usaaf_nm']['texture'])), NMAP, img(os.path.join(T, LIV['usaaf_od']['metal']), True))
    for nm, loc, tgt, lens in (('m4_wingroot_below_L', (-3.6, -0.6, -4.2), (-1.0, -0.2, -0.45), 32), ('m4_wingroot_below_R', (3.6, -0.6, -4.2), (1.0, -0.2, -0.45), 32),
                               ('m4_ball_turret', (1.9, -2.6, -2.4), (0, -3.95, -0.8), 38), ('m4_nose_close', (2.2, 8.4, 1.3), (0, 6.0, 0.9), 40)):
        shot(nm, cam(loc, tgt, lens), res=(1400, 900), with_ref=False)
    use_livery('usaaf_od')

if 'r5' in ONLY:     # round 5 review set (user review 2): every fixed item, ours vs the reference from the SAME camera
    use_livery('usaaf_od' if 'usaaf_od' in LIV else first)
    if T:          # the procedural prop / cockpit-free props use the livery UV for their pr_ cells
        hs = bpy.data.materials.get('pr_hsprop'); b = img(os.path.join(T, 'b17g_pr_hsprop_b.png'))
        if hs and b:
            set_tex(hs, b, uv='livery')
    def r5(name, loc, tgt, lens=40, res=(1400, 1000), ref_too=True):
        shot('r5_' + name, cam(loc, tgt, lens), res=res, with_ref=ref_too)
    def ortho(name, loc, tgt, scale, res=(1600, 1000)):
        shot('r5_' + name, cam(loc, tgt, 50, scale), res=res)
    ortho('front', (0, 45, 0.6), (0, 0, 0.6), 34)
    ortho('side', (45, -4, 0.8), (0, -4, 0.8), 26)
    ortho('top', (0, -4, 50), (0, -4.0001, 0), 34)
    ortho('under', (0, -4, -50), (0, -4.0001, 0), 34)
    r5('34_front', (17, 19, 7), (0, -2, 0.5), 35)
    r5('34_rear', (-15, -26, 6), (0, -5, 0.8), 35)
    r5('under_34', (12, -4, -24), (0, -3, 0), 40)
    r5('under_nacelles', (4.0, 0.0, -5.5), (4.5, 0.5, -0.4), 35)
    r5('chin_front34', (1.6, 8.6, -0.9), (0, 6.1, -0.55)); r5('chin_side', (2.8, 6.1, -0.55), (0, 6.1, -0.55)); r5('chin_below', (0.5, 6.4, -3.0), (0, 6.1, -0.55))
    r5('ball_side', (2.8, -3.95, -0.8), (0, -3.95, -0.8)); r5('ball_front34', (1.6, -1.6, -1.6), (0, -3.95, -0.8)); r5('ball_below', (0.6, -3.6, -3.2), (0, -3.95, -0.8))
    r5('tail_side', (2.2, -14.7, 0.9), (0, -14.7, 0.9)); r5('tail_rear', (0, -18.5, 1.0), (0, -14.7, 0.9)); r5('tail_below34', (1.6, -16.4, -0.4), (0, -14.7, 0.8))
    r5('top_side', (3.2, 2.1, 2.2), (0, 2.1, 2.1)); r5('top_front', (0, 5.6, 2.6), (0, 2.1, 2.1)); r5('top_34', (2.4, 4.2, 3.2), (0, 2.1, 2.1)); r5('top_above', (0.4, 2.2, 4.6), (0, 2.1, 2.1))
    r5('roof_rear34', (2.5, -0.5, 3.2), (0, 3.0, 1.8), 35); r5('roof_front', (0, 7.5, 3.2), (0, 2.5, 1.9), 35)
    # prop hub with the spin axis drawn (red rod along prop_n local Y through the hub)
    axm = bpy.data.materials.new('axis_red'); axm.use_nodes = True
    axm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.9, 0.05, 0.05, 1)
    axm.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.9, 0.05, 0.05, 1)
    axm.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
    rods = []
    for n_ in (1, 2, 3, 4):
        p_ = bpy.data.objects.get(f'prop_{n_}')
        if p_ is None:
            continue
        import bmesh
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.012, radius2=0.012, depth=2.4)
        me = bpy.data.meshes.new('rod'); bm.to_mesh(me); bm.free(); me.materials.append(axm)
        me.transform(Matrix.Rotation(-math.pi / 2, 4, 'X'))       # cone along Z -> along local Y (the spin axis)
        rod = bpy.data.objects.new(f'axis_{n_}', me); sc.collection.objects.link(rod)
        rod.matrix_world = p_.matrix_world.copy(); rods.append(rod)
    r5('prop_front', (3.1, 8.5, 0.05), (3.1, 4.6, 0.05), 40)
    r5('prop_side', (5.5, 4.6, 0.05), (3.1, 4.6, 0.05), 40)
    r5('prop_hub_close', (3.75, 5.75, 0.55), (3.1, 4.62, 0.05), 40)
    # spin test: every blade + hub rotated 60 deg about the prop axis: the hub must not move (overlay of 0 and 60 deg is one hub)
    for n_ in (3,):
        p_ = bpy.data.objects.get(f'prop_{n_}')
        h_ = bpy.data.objects.get(f'prop_hub_{n_}')
        if p_ and h_:
            b0 = h_.matrix_basis.copy()
            h_.matrix_basis = b0 @ Matrix.Rotation(math.radians(60), 4, 'Y')
            bpy.context.view_layer.update()
            shot('r5_prop_front_spun60', cam((3.1, 8.5, 0.05), (3.1, 4.6, 0.05), 40), res=(1400, 1000), with_ref=False)
            h_.matrix_basis = b0
            bpy.context.view_layer.update()
    for r_ in rods:
        r_.hide_render = True
    # nacelle / flap at 0 and 28 deg
    flaps = [o for o in bpy.data.objects if o.name.startswith('flap_')]
    for deg in (0, 28):
        for fl in flaps:
            if 'b0' not in fl:
                fl['b0'] = [v for row in fl.matrix_basis for v in row]
            M0 = Matrix([fl['b0'][0:4], fl['b0'][4:8], fl['b0'][8:12], fl['b0'][12:16]])
            fl.matrix_basis = M0 @ Matrix.Rotation(math.radians(deg), 4, 'X')
        bpy.context.view_layer.update()
        r5(f'nacelle_flap_{deg}_below', (5.5, -5.0, -3.0), (3.1, -2.4, -0.3), 35, ref_too=(deg == 0))
        r5(f'nacelle_flap_{deg}_rear', (3.6, -7.0, 0.2), (3.1, -2.6, -0.1), 35, ref_too=(deg == 0))
        r5(f'nacelle_flap_{deg}_inboard', (1.4, -2.0, -1.4), (3.1, -2.2, -0.4), 30, ref_too=(deg == 0))
    for fl in flaps:
        M0 = Matrix([fl['b0'][0:4], fl['b0'][4:8], fl['b0'][8:12], fl['b0'][12:16]])
        fl.matrix_basis = M0
    bpy.context.view_layer.update()
    # cockpit pedestal (06 flicker) from the user's camera direction
    sun.data.energy = 4.0
    shot('r5_pedestal', cam((0.30, 3.25, 1.55), (0.0, 3.95, 0.80), 30), res=(1400, 1000), with_ref=False)
    # X-ray / cutaway: the skin, glazing and inner skin made faint, the internals solid
    for nm_ in ('paint', 'interior', 'glass', 'cove'):
        m_ = bpy.data.materials.get(nm_)
        if m_ is None:
            continue
        m_.use_nodes = True
        bs_ = m_.node_tree.nodes.get('Principled BSDF')
        bs_.inputs['Alpha'].default_value = 0.07
        try:
            m_.surface_render_method = 'BLENDED'
        except Exception:
            m_.blend_method = 'BLEND'
    for o in bpy.data.objects:
        if o.type == 'MESH' and (o.name.startswith(('cockpit_', 'gauge_')) or o.name.startswith('engine_face')):
            o.hide_render = o.name.startswith(('cockpit_', 'gauge_'))
    shot('r5_xray_34', cam((17, 19, 9), (0, -2, 0.5), 35), res=(1800, 1100), with_ref=False)
    shot('r5_xray_top', cam((0, -4, 50), (0, -4.0001, 0), 50, 34), res=(1800, 1100), with_ref=False)
    shot('r5_xray_wing', cam((9, 5, 6), (5, -0.5, 0.3), 35), res=(1600, 1000), with_ref=False)
    shot('r5_xray_tail', cam((6, -6, 4), (0, -10, 1.0), 35), res=(1600, 1000), with_ref=False)

def add_proxy_barrels():
    """proxy M2 jackets + barrels on every gun slot (render only, never exported; the Unity build puts the stock barrel there)."""
    import bmesh, re
    gm = bpy.data.materials.new('proxy_m2'); gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.03, 0.03, 0.035, 1)
    gm.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value = 0.6
    def cyl(r0, r1, y0, y1):
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=r0, radius2=r1, depth=y1 - y0)
        me = bpy.data.meshes.new('pm2'); bm.to_mesh(me); bm.free()
        me.transform(Matrix.Translation((0, 0, (y0 + y1) / 2))); me.transform(Matrix.Rotation(-math.pi / 2, 4, 'X'))   # along local +Y (the aim)
        me.materials.append(gm); return me
    jacket, barrel = cyl(0.042, 0.042, -0.33, 0.55), cyl(0.024, 0.022, 0.55, 1.20)
    nprox = 0
    for o in list(bpy.data.objects):
        if o.type == 'EMPTY' and re.search(r'_gun\d$', o.name):        # Unity: the stock barrel's bore on this slot axis, tip at the muzzle (+1.20)
            for me_, nm_ in ((jacket, 'j'), (barrel, 'b')):
                ob = bpy.data.objects.new(f'proxy_{nm_}_{o.name}', me_); sc.collection.objects.link(ob)
                ob.parent = o; ob.matrix_parent_inverse = Matrix.Identity(4); ob.matrix_basis = Matrix.Identity(4)
            nprox += 1
    print('[render] proxy barrels on', nprox, 'gun slots')


if 'r6' in ONLY:     # round 6 polish review: chin / tail / ball + full views, with proxy M2 barrels on every gun slot
    use_livery('usaaf_od' if 'usaaf_od' in LIV else first)
    if T:
        hs = bpy.data.materials.get('pr_hsprop'); b = img(os.path.join(T, 'b17g_pr_hsprop_b.png'))
        if hs and b:
            set_tex(hs, b, uv='livery')
    add_proxy_barrels()

    def r6(name, loc, tgt, lens=40, res=(1400, 1000)):
        shot('r6_' + name, cam(loc, tgt, lens), res=res, with_ref=True)
    r6('chin_front34', (1.6, 8.6, -0.9), (0, 6.1, -0.55)); r6('chin_side', (2.8, 6.1, -0.55), (0, 6.1, -0.55)); r6('chin_front', (0, 9.0, -0.6), (0, 6.1, -0.6))
    r6('chin_below', (0.5, 6.4, -3.0), (0, 6.1, -0.55))
    r6('tail_side', (2.2, -14.7, 0.9), (0, -14.7, 0.9)); r6('tail_rear', (0, -18.5, 1.0), (0, -14.7, 0.9)); r6('tail_below34', (1.6, -16.4, -0.4), (0, -14.7, 0.8))
    r6('tail_rear34', (2.0, -17.4, 1.5), (0, -14.7, 0.85))
    r6('ball_side', (2.8, -3.95, -0.8), (0, -3.95, -0.8)); r6('ball_front34', (1.6, -1.6, -1.6), (0, -3.95, -0.8))
    shot('r6_side', cam((45, -4, 0.8), (0, -4, 0.8), 50, 26), res=(1600, 1000))
    shot('r6_front', cam((0, 45, 0.6), (0, 0, 0.6), 50, 34), res=(1600, 1000))
    shot('r6_rear', cam((0, -48, 1.2), (0, 0, 1.0), 50, 34), res=(1600, 1000))
    r6('34_front', (17, 19, 7), (0, -2, 0.5), 35); r6('34_rear', (-15, -26, 6), (0, -5, 0.8), 35)

if 'r78' in ONLY:    # 1.7.8 review: tail compartment (side / 3/4 rear / top / rear, same cameras for the reference), roof aft of the top
    # turret under a grazing light (the 1.7.7 stepped patch), handed props from behind
    use_livery('usaaf_od' if 'usaaf_od' in LIV else first)
    if T:
        hs = bpy.data.materials.get('pr_hsprop'); b = img(os.path.join(T, 'b17g_pr_hsprop_b.png'))
        if hs and b:
            set_tex(hs, b, uv='livery')
    shot('r78_tail_side', cam((30, -12.6, 0.9), (0, -12.6, 0.9), 50, 7.5), res=(1600, 1000))
    shot('r78_tail_rear34', cam((5.5, -21.0, 3.2), (0, -13.6, 0.9), 50), res=(1600, 1000))
    shot('r78_tail_top', cam((0, -12.6, 30), (0, -12.6001, 0), 50, 7.5), res=(1600, 1000))
    shot('r78_tail_rear', cam((0, -30, 0.9), (0, 0, 0.9), 50, 6.0), res=(1600, 1000))
    shot('r78_tail_below34', cam((3.0, -18.5, -1.6), (0, -13.8, 0.6), 50), res=(1600, 1000))
    sun.rotation_euler = Euler((math.radians(80), 0, math.radians(170)))      # grazing light along the roof
    shot('r78_roof_patch', cam((1.2, -1.4, 3.6), (0, 1.0, 2.0), 40), res=(1600, 1000), with_ref=False)
    sun.rotation_euler = Euler((math.radians(40), math.radians(15), math.radians(35)))
    if 'usaaf_nm' in LIV:     # the 1.7.7 in-game patch was seen on the natural-metal livery, from the left, above and ahead
        use_livery('usaaf_nm')
        shot('r78_roof_patch_nm', cam((-5.5, 6.5, 5.5), (0, 0.6, 1.9), 35), res=(1600, 1000), with_ref=False)
        use_livery('usaaf_od' if 'usaaf_od' in LIV else first)
    shot('r78_props_front', cam((0, 16, 1.2), (0, 4.3, 0.3), 30), res=(1600, 1000), with_ref=False)       # left pair = right pair mirrored (handed props)

if 'r79' in ONLY:    # 1.7.9 tail review: EEVEE pairs with proxy barrels + flat silhouette masks (ours / ref) from the same cameras
    use_livery('usaaf_od' if 'usaaf_od' in LIV else first)
    add_proxy_barrels()
    VIEWS79 = {'tail_side': ((30, -13.4, 0.9), (0, -13.4, 0.9), 50, 5.5, None), 'tail_rear34': ((5.5, -21.0, 3.2), (0, -13.6, 0.9), 50, None, None),
               'tail_top': ((0, -13.4, 30), (0, -13.4001, 0), 50, 5.5, None), 'tail_rear': ((0, -30, 0.9), (0, 0, 0.9), 50, 4.0, None),
               'tail_rear_clip': ((0, -30, 0.9), (0, 0, 0.9), 50, 4.0, 18.5)}     # sees only y < -11.5: the tail compartment's own outline
    def cam79(loc_, tgt_, lens_, orth_, clip_):
        c_ = cam(loc_, tgt_, lens_, orth_)
        if clip_:
            c_.data.clip_end = clip_
        return c_
    for nm_, v_ in VIEWS79.items():
        if nm_ != 'tail_rear_clip':
            shot('r79_' + nm_, cam79(*v_), res=(1600, 1000))
    # masks: Workbench, flat single colour, black world; the reference gets the same treatment
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading; sh.light = 'FLAT'; sh.color_type = 'SINGLE'; sh.single_color = (1, 1, 1)
    sh.background_type = 'VIEWPORT'; sh.background_color = (0, 0, 0)
    try:
        sc.render.film_transparent = False
    except Exception:
        pass
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith(('cockpit_', 'gauge_')):
            o.hide_render = True        # inside the hull; keeps the masks cheap
    for nm_, v_ in VIEWS79.items():
        shot('m79_' + nm_, cam79(*v_), res=(1600, 1000))

if 'r711' in ONLY:   # 1.7.11 z-fight review: close-ups of the worst former pairs + the cockpit pedestal (no reference)
    use_livery('usaaf_od' if 'usaaf_od' in LIV else first)
    if T:
        hs = bpy.data.materials.get('pr_hsprop'); b = img(os.path.join(T, 'b17g_pr_hsprop_b.png'))
        if hs and b:
            set_tex(hs, b, uv='livery')
    for nm_, loc_, tgt_, lens_ in (('ball_ring_liner', (0.25, -4.05, 0.55), (-0.39, -4.63, -0.44), 30),
                                   ('chin_ring_liner', (0.15, 5.55, 0.55), (0.67, 6.18, -0.29), 30),
                                   ('cockpit_window_frame', (2.2, 3.0, 2.3), (0.95, 3.01, 1.66), 45),
                                   ('engine_face_1', (-6.5, 6.2, 0.7), (-6.58, 3.45, 0.15), 45),
                                   ('panel_bezels', (0.30, 3.45, 1.42), (0.40, 4.22, 1.33), 40),
                                   ('pedestal', (0.0, 3.25, 1.62), (0.0, 3.87, 1.19), 35),
                                   ('cockpit_roof', (-0.35, 3.45, 1.35), (-0.59, 3.79, 1.91), 30)):
        shot('r711_' + nm_, cam(loc_, tgt_, lens_), res=(1400, 900), with_ref=False)

if 'r712' in ONLY:   # 1.7.12 top-turret patch: the in-game camera (left, ahead, above, looking aft) on both liveries, grazing light
    for key in ('usaaf_nm', 'usaaf_od'):
        if key not in LIV:
            continue
        use_livery(key)
        for nm_, rot_ in (('graze', (math.radians(82), 0, math.radians(-100))), ('sun', (math.radians(40), math.radians(15), math.radians(35)))):
            sun.rotation_euler = Euler(rot_)
            shot(f'r712_patch_{key}_{nm_}', cam((-2.4, 3.6, 3.3), (-0.25, 1.5, 2.0), 45), res=(1400, 900), with_ref=False)
    sun.rotation_euler = Euler((math.radians(40), math.radians(15), math.radians(35)))

if 'liveries' in ONLY:
    for key in LIV:
        use_livery(key)
        shot('livery_' + key, cam((17, 19, 7), (0, -2, 0.5), 35), with_ref=False)
        shot('livery_' + key + '_below', cam((-14, -10, -12), (0, -3, 0), 35), with_ref=False)
print('[render] done')
