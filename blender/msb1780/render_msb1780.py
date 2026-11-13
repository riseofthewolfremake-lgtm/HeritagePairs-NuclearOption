"""MSB-17/80 review renders (Blender EEVEE, NOT the game shaders). Output OUTSIDE the repo (nuclearoption-ref/study/msb1780/...).

  blender -b assets/model_msb1780/msb1780.blend -P blender/msb1780/render_msb1780.py -- --out <dir> [--tex assets/textures_msb1780]
          [--prefix msb] [--only views,liveries,cockpit,turrets,gun,bay] [--res 1200]
The same script renders the B-17G blend (--prefix b17g --tex assets/textures_b17g --only views) from the same cameras for the side-by-side
sheet (blender/msb1780/compose_msb1780.py). Liveries: every entry of <prefix>_liveries.json.
"""
import bpy, sys, os, math, json
from mathutils import Vector as V, Euler, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
OUT = os.path.abspath(arg('--out', '.')); TEX = arg('--tex'); PFX = arg('--prefix', 'msb'); RES = int(arg('--res', '1200'))
ONLY = set(arg('--only', 'views,liveries,cockpit,turrets,gun,bay').split(','))
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for o in bpy.data.objects:
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
for attr, val in (('use_raytracing', True), ('use_gtao', True)):
    try:
        setattr(sc.eevee, attr, val)
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
LIV = {}
if T:
    lj = os.path.join(T, f'{PFX}_liveries.json')
    LIV = json.load(open(lj)) if os.path.exists(lj) else {}
paint = bpy.data.materials.get('paint')
NMAP = img(os.path.join(T, f'{PFX}_skin_n.png'), True) if T else None
if T:
    for k in ('structure', 'interior', 'well', 'gear', 'tyre', 'cowl', 'turret', 'ck_panel', 'ck_wall', 'ck_floor', 'ck_black', 'ck_bezel', 'ck_od'):
        mt = bpy.data.materials.get(k); b = img(os.path.join(T, f'{PFX}_tile_{k}_b.png'))
        if mt and b:
            set_tex(mt, b, img(os.path.join(T, f'{PFX}_tile_{k}_n.png'), True), uv='detail', scale=1.0)
    pr = bpy.data.materials.get('pr_hsprop'); pb = img(os.path.join(T, f'{PFX}_pr_hsprop_b.png'))
    if pr and pb:
        set_tex(pr, pb, uv='livery')        # the prop texture is a 4-cell sheet laid out on the livery UV (build_textures write_prop_texture)
gl = bpy.data.materials.get('glass')
if gl:
    gl.use_nodes = True
    bs = gl.node_tree.nodes.get('Principled BSDF')
    for k, v in (('Base Color', (0.80, 0.88, 0.95, 1)), ('Alpha', 0.20), ('Roughness', 0.03), ('Coat Weight', 1.0), ('Coat Roughness', 0.02)):
        try:
            bs.inputs[k].default_value = v
        except Exception:
            pass
    try:
        gl.surface_render_method = 'BLENDED'
    except Exception:
        pass
scr = bpy.data.materials.get('screen')
if scr:       # screens: a dim tac-page green so the renders show where they are (the game draws the stock tac page)
    scr.use_nodes = True
    bs = scr.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (0.02, 0.06, 0.04, 1)
    try:
        bs.inputs['Emission Color'].default_value = (0.10, 0.45, 0.25, 1); bs.inputs['Emission Strength'].default_value = 1.2
    except Exception:
        pass


def use_livery(key):
    if key in LIV:
        set_tex(paint, img(os.path.join(T, LIV[key]['texture'])), NMAP, img(os.path.join(T, LIV[key]['metal']), True))


first = next(iter(LIV), None)
if first:
    use_livery(first)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
sc.render.resolution_x = RES; sc.render.resolution_y = int(RES * 0.62); sc.render.film_transparent = False


def shot(name, loc, look, lens=50.0, ortho=None, res=None, clip=0.05):
    cam.location = V(loc)
    d = V(look) - V(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_start = clip; cam.data.clip_end = 400
    if ortho:
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'; cam.data.lens = lens
    if res:
        sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, f'{PFX}_{name}.png')
    bpy.ops.render.render(write_still=True)
    sc.render.resolution_x = RES; sc.render.resolution_y = int(RES * 0.62)
    print('[render]', sc.render.filepath)


C = V((0, -3.6, 0.6))
VIEWS = [('side', (-60, -3.6, 0.6), C, 30.0), ('top', (0, -3.6, 60), C, 36.0), ('front', (0, 60, 0.4), V((0, -3.6, 0.4)), 34.0),
         ('under', (0, -3.6, -60), C, 36.0)]
if 'views' in ONLY:
    for n, loc, look, osc in VIEWS:
        if n in ('top', 'under'):
            cam.data.type = 'ORTHO'
            cam.location = V(loc); cam.rotation_euler = Euler((0, 0, 0)) if n == 'top' else Euler((math.pi, 0, 0))
            cam.data.ortho_scale = osc; cam.data.clip_end = 400
            sc.render.filepath = os.path.join(OUT, f'{PFX}_{n}.png'); bpy.ops.render.render(write_still=True)
        else:
            shot(n, loc, look, ortho=osc)
    shot('q34f', (-24, 22, 9), (0, -2.5, 0.3), lens=42)
    shot('q34r', (22, -34, 10), (0, -2.5, 0.6), lens=42)
if 'liveries' in ONLY:
    for key in LIV:
        use_livery(key)
        shot(f'livery_{key}_q34f', (-24, 22, 9), (0, -2.5, 0.3), lens=42)
        shot(f'livery_{key}_q34r', (22, -34, 10), (0, -2.5, 0.6), lens=42)
    if first:
        use_livery(first)


def hide(prefixes, state=True):
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith(prefixes):
            o.hide_render = state


if 'cockpit' in ONLY:
    hide(('hatch_pilot', 'fus_cockpit', 'wing_inner', 'nacelle'), True)
    shot('cockpit_overview', (0, 2.45, 2.45), (0, 4.2, 1.05), lens=18)
    hide(('hatch_pilot', 'fus_cockpit', 'wing_inner', 'nacelle'), False)
    shot('cockpit_pilot_eye', (-0.45, 3.32, 1.70), (-0.25, 4.6, 1.30), lens=16)
    shot('cockpit_panel', (0.0, 3.10, 1.62), (0.0, 4.2, 1.15), lens=20)
    hide(('MSB17',), True)
    shot('station_ewo', (-0.25, 2.30, 1.75), (0.95, 2.62, 1.20), lens=18)
    hide(('MSB17',), False)
    hide(('fus_nose', 'hatch_wso'), True)
    shot('station_wso', (0.0, 5.60, 1.25), (0.0, 6.75, 0.55), lens=18)
    shot('station_wso_side', (-2.2, 6.2, 1.0), (0.0, 6.4, 0.5), lens=30)
    hide(('fus_nose', 'hatch_wso'), False)
if 'turrets' in ONLY:
    shot('turret_chin', (-2.2, 8.4, -1.4), (0, 6.30, -0.85), lens=45)
    shot('turret_chin_side', (-3.0, 6.3, -0.85), (0, 6.30, -0.85), lens=45)
    shot('turret_tail', (2.4, -17.2, 1.4), (0, -14.95, 0.70), lens=45)
    shot('turret_tail_side', (-3.0, -15.0, 0.9), (0, -15.0, 0.75), lens=45)
    shot('turret_dorsal', (-2.4, 4.2, 3.6), (0, 2.08, 2.30), lens=45)
    shot('turret_ventral', (-2.6, -2.2, -2.4), (0, -4.35, -0.85), lens=45)
    shot('nacelle_props', (-8.0, 9.0, 1.4), (-4.8, 4.6, 0.2), lens=40)
if 'gun' in ONLY:
    g = bpy.data.objects.get('chin_gun0')
    if g:
        keep = {g.name}
        state = {o.name: o.hide_render for o in bpy.data.objects}
        for o in bpy.data.objects:
            if o.type == 'MESH':
                o.hide_render = o.name not in keep
        c = g.matrix_world.translation
        f = g.matrix_world.to_3x3() @ V((0, 1, 0))
        shot('gun20_q34', c + V((-1.0, 0.9, 0.55)), c + f * 0.45, lens=35)
        shot('gun20_side', c + V((-2.3, 0.65, 0.0)), c + f * 0.65, lens=35)
        shot('gun20_top', c + V((0.0, 0.65, 2.0)), c + f * 0.65, lens=35)
        shot('gun20_muzzle', c + f * 1.62 + V((-0.35, 0.30, 0.15)), c + f * 1.50, lens=40)
        for o in bpy.data.objects:
            o.hide_render = state.get(o.name, o.hide_render)
if 'bay' in ONLY:
    import importlib
    loads = json.loads(arg('--loads', '[]')) if arg('--loads') else []
    hide(('bay_door_',), True)
    shot('bay_empty', (-2.6, -0.5, -3.6), (0, -0.5, -0.2), lens=24)
    con = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), 'msb1780_contract.json')))
    sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'b17g'), os.path.dirname(os.path.abspath(__file__))]
    import msb_spec as _MS                   # the stock mount envelopes (blender frame, relative to the hardpoint; the contract lists names only)
    ENV = _MS.STORES
    mat = bpy.data.materials.new('store'); mat.use_nodes = True
    bs = mat.node_tree.nodes['Principled BSDF']; bs.inputs['Base Color'].default_value = (0.75, 0.72, 0.25, 1)
    for label, sets in (('gpo500x8', {'hp_bay': 'bomb_500_internalx8'}), ('pab250_16', {'hp_bay_fwd': 'bomb_250_internalx8', 'hp_bay_aft': 'bomb_250_internalx8'}),
                        ('alm_x2', {'hp_bay': 'CruiseMissile1_internalx2'}), ('agm68_x8', {'hp_bay': 'AGM_heavy_internalx8'}), ('pab80_12', {'hp_bay_L': 'bomb_glide1_six_inernal', 'hp_bay_R': 'bomb_glide1_six_inernal'})):
        made = []
        for hp, key in sets.items():
            x0, x1, y0, y1, z0, z1 = ENV[hp][key]
            px, py, pz = con['bay']['hardpoints'][hp]
            bpy.ops.mesh.primitive_cube_add(size=1, location=(px + (x0 + x1) / 2, py + (y0 + y1) / 2, pz + (z0 + z1) / 2))
            ob = bpy.context.active_object; ob.scale = (x1 - x0, y1 - y0, z1 - z0); ob.data.materials.append(mat); made.append(ob)
        shot(f'bay_{label}', (-2.6, -0.5, -3.6), (0, -0.5, -0.2), lens=24)
        for ob in made:
            bpy.data.objects.remove(ob)
    hide(('bay_door_',), False)
# ---- 1.9.1 review set (same cameras before / after): cockpit, WSO, EWO, ventral laser ring, prop blades. --stock loads the stock parts the
# contract lists (stock_parts: EW-25 flight-deck tub, tac screen, sticks, throttle) from the user's Blueprinter project IN MEMORY (stock_mesh.py;
# never saved) with approximate flat materials; the stock crew figures / seats are not shown (Unity capture: MSB1780CockpitShot.cs)
if 'review' in ONLY:
    if '--stock' in argv:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import stock_mesh as SMK
        con = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), 'msb1780_contract.json')))
        cols = {'tacScreenDisplay': (0.10, 0.42, 0.30, 1), 'Touchscreen_off': (0.03, 0.035, 0.04, 1), 'hotas': (0.05, 0.05, 0.05, 1)}
        for sp in con.get('stock_parts', []):
            o = SMK.load(sp['mesh'], obj_name='stock_' + sp['name'], matrix=Matrix.Translation(V(sp['pos'])), mats=['stock_' + m for m in sp.get('materials', [])])
            for ms in o.data.materials:
                ms.use_nodes = True
                bs = ms.node_tree.nodes.get('Principled BSDF')
                c = next((v for k, v in cols.items() if k in ms.name), (0.16, 0.17, 0.18, 1))
                bs.inputs['Base Color'].default_value = c; bs.inputs['Roughness'].default_value = 0.6
                if 'tacScreen' in ms.name:
                    try:
                        bs.inputs['Emission Color'].default_value = c; bs.inputs['Emission Strength'].default_value = 1.0
                    except Exception:
                        pass
            for n_ in ('stick_L', 'stick_R', 'cockpit_throttle'):
                if sp['name'] == n_ and bpy.data.objects.get(n_):
                    pass
    R_ = [('ck_pilot_eye', (-0.38, 3.40, 1.72), (-0.15, 4.6, 1.15), 16, ()),
          ('ck_overview', (0.0, 2.55, 2.55), (0.0, 4.1, 0.95), 18, ('fus_cockpit', 'hatch_pilot')),
          ('ck_side', (-0.95, 3.0, 1.55), (0.3, 4.2, 1.0), 16, ('fus_cockpit', 'hatch_pilot', 'wing_inner_L', 'nacelle_2')),
          ('wso_view', (-1.7, 5.3, 1.7), (0.0, 6.35, 0.45), 22, ('fus_nose', 'hatch_wso', 'chin_')),
          ('wso_eye', (0.0, 5.75, 1.28), (0.0, 6.85, 0.55), 18, ()),
          ('ewo_view', (-0.75, 2.05, 2.25), (0.85, 2.80, 1.15), 18, ('MSB17', 'hatch_ewo', 'top_')),
          ('ewo_eye', (0.20, 2.62, 1.70), (1.0, 2.80, 1.35), 16, ()),
          ('laser_ring', (-1.5, -3.3, -2.0), (0.0, -4.35, -0.62), 40, ()),
          ('laser_ring_under', (0.0, -4.35, -3.6), (0.0, -4.34, -0.6), 40, ()),
          ('props_close', (-4.9, 6.6, 1.1), (-3.1, 4.75, 0.3), 45, ()),
          ('props_edge', (-3.1, 5.15, 2.9), (-3.1, 4.75, 0.3), 40, ())]
    for n_, loc, look, lens, hid in R_:
        hide(hid, True) if hid else None
        shot('review_' + n_, loc, look, lens=lens, clip=0.02)
        hide(hid, False) if hid else None
print('[render] done')
