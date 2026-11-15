"""1.9.12 review renders of the MSB-17: spoiler panels shut / open, formation-light strips unlit / lit, every livery (Blender EEVEE, NOT the
game shaders). Output OUTSIDE the repo.

  blender -b assets/model_msb1780/msb1780.blend -P blender/msb1780/render_1912.py -- --out <dir> [--tex assets/textures_msb1780] [--tag x]
          [--only liveries,closeups,night] [--liveries key,key] [--views side,top] [--cu name,name] [--res 1500x850]

Per livery: side, rear quarter, top - once shut + unlit, once open + lit. Close-ups (first livery): each spoiler pair shut and open, each
strip pair unlit and lit. Night: rear quarter and side with the strips lit (dark world), to judge how they read.
"""
import bpy, sys, os, math, json
from mathutils import Vector as V, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.abspath(arg('--out', '.')); TEX = os.path.abspath(arg('--tex', os.path.join(ROOT, 'assets', 'textures_msb1780')))
TAG = arg('--tag', '1912'); ONLY = set(arg('--only', 'liveries,closeups,night').split(','))
ANGLE = float(arg('--angle', '55'))
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene
for o in bpy.data.objects:
    if o.name.endswith('_hullsrc'):
        o.hide_render = True
ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in ids else 'BLENDER_EEVEE_NEXT'
w = sc.world or bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
BG = w.node_tree.nodes.get('Background')
try:
    sc.view_settings.view_transform = 'Standard'
except Exception:
    pass
for attr, val in (('use_raytracing', True), ('use_gtao', True)):
    try:
        setattr(sc.eevee, attr, val)
    except Exception:
        pass
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = (int(v) for v in arg('--res', '1500x850').split('x'))


def img(path, nonc=False):
    if not path or not os.path.exists(path):
        return None
    im = bpy.data.images.load(path, check_existing=True)
    if nonc:
        im.colorspace_settings.name = 'Non-Color'
    return im


def set_tex(mat, b, n=None, m=None, uv='livery'):
    mat.use_nodes = True
    nt = mat.node_tree
    for nd in list(nt.nodes):
        if nd.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(nd)
    bs = nt.nodes.get('Principled BSDF')
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uv
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = b; nt.links.new(uvn.outputs[0], t.inputs[0]); nt.links.new(t.outputs[0], bs.inputs['Base Color'])
    if n is not None:
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = n; nt.links.new(uvn.outputs[0], tn.inputs[0])
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.uv_map = uv
        nt.links.new(tn.outputs[0], nm.inputs['Color']); nt.links.new(nm.outputs[0], bs.inputs['Normal'])
    if m is not None:
        tm = nt.nodes.new('ShaderNodeTexImage'); tm.image = m; nt.links.new(uvn.outputs[0], tm.inputs[0])
        sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(tm.outputs[0], sp.inputs[0])
        nt.links.new(sp.outputs[0], bs.inputs['Metallic'])
        inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        nt.links.new(tm.outputs[1], inv.inputs[1]); nt.links.new(inv.outputs[0], bs.inputs['Roughness'])


LIV = json.load(open(os.path.join(TEX, 'msb17_liveries.json')))
keys = [k for k in (arg('--liveries').split(',') if arg('--liveries') else LIV) if k in LIV]
paint = bpy.data.materials.get('paint')
NMAP = img(os.path.join(TEX, 'msb17_skin_n.png'), True)
# round 2: the materials as Unity REALLY builds them (unity/b17g_sections/b17g_mat.cs, used by the MSB with its own tiles): URP Lit with the
# tile as base map on the detail UV, NO normal map (Tiled(m, tile)), metallic / smoothness from the table; `cove` is LitMat colour 0.05 -
# a Unity Color is an sRGB value, 0.05 sRGB = 0.0039 linear (the first build's renders used 0.05 LINEAR, four tones lighter: the bed looked grey)
UNITY_TILES = {'structure': (0.5, 0.35), 'interior': (0.1, 0.25), 'well': (0.2, 0.3), 'gear': (0.6, 0.45), 'tyre': (0.0, 0.1), 'cowl': (0.4, 0.4), 'turret': (0.2, 0.3)}
for k, (metal, smooth) in UNITY_TILES.items():
    mt = bpy.data.materials.get(k); b = img(os.path.join(TEX, f'msb17_tile_{k}_b.png'))
    if mt and b:
        set_tex(mt, b, None, uv='detail')
        bs = mt.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Metallic'].default_value = metal; bs.inputs['Roughness'].default_value = 1.0 - smooth


def srgb(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


cv = bpy.data.materials.get('cove')
if cv:
    cv.use_nodes = True
    bs = cv.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (srgb(0.05), srgb(0.05), srgb(0.05), 1); bs.inputs['Metallic'].default_value = 0.0; bs.inputs['Roughness'].default_value = 0.9
gl = bpy.data.materials.get('glass')
if gl:
    bs = gl.node_tree.nodes.get('Principled BSDF')
    for k, v in (('Base Color', (0.10, 0.14, 0.18, 1)), ('Alpha', 0.75), ('Roughness', 0.05)):
        try:
            bs.inputs[k].default_value = v
        except Exception:
            pass


def use_livery(key):
    set_tex(paint, img(os.path.join(TEX, LIV[key]['texture'])), NMAP, img(os.path.join(TEX, LIV[key]['metal']), True))


# strips: unlit = the stock light_green_off colour (0.473, 0.612, 0.537), smoothness 0.594; lit = the stock slimelight_on emission (0.047, 2.996, 0.329)
LO = bpy.data.materials.get('light_off')


def lights(on):
    if LO is None:
        return
    LO.use_nodes = True
    bs = LO.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1) if on else (0.473, 0.612, 0.537, 1)
    bs.inputs['Roughness'].default_value = 0.5 if on else 0.406
    try:
        bs.inputs['Emission Color'].default_value = (0.047, 1.0, 0.11, 1); bs.inputs['Emission Strength'].default_value = 3.0 if on else 0.0
    except Exception:
        pass


HINGES = [o for o in bpy.data.objects if o.name.startswith('airbrake_') and o.name.endswith('_hinge')]
BASE = {o.name: o.matrix_basis.copy() for o in HINGES}


def spoilers(deg):
    for o in HINGES:
        o.matrix_basis = BASE[o.name] @ Matrix.Rotation(math.radians(-deg), 4, 'X')     # Blender: open = minus about local +X (Unity: plus)
    bpy.context.view_layer.update()


def aim(o, loc, look):
    o.location = V(loc)
    o.rotation_euler = (V(look) - V(loc)).to_track_quat('-Z', 'Y').to_euler()


def day(night=False):
    BG.inputs[0].default_value = (0.01, 0.012, 0.02, 1) if night else (0.62, 0.70, 0.80, 1)
    BG.inputs[1].default_value = 0.25 if night else 0.9
    sun.data.energy = 0.12 if night else 3.5; fill.data.energy = 0.05 if night else 1.2


def shot(name, loc, look, lens=50, sun_from=(-3, 3, 6), fill_from=(3, -4, 1)):
    aim(cam, loc, look); cam.data.lens = lens; cam.data.clip_start = 0.05; cam.data.clip_end = 400
    aim(sun, V(look) + V(sun_from), look); aim(fill, V(look) + V(fill_from), look)
    sc.render.filepath = os.path.join(OUT, f'{TAG}_{name}.png')
    bpy.ops.render.render(write_still=True)
    print('[r1912]', sc.render.filepath)


VIEWS = [('side', (-42.0, -3.0, 2.5), (0, -3.5, 1.3), 60, (-4, 2, 5), (-2, -4, -1)),
         ('rearq', (17.0, -30.0, 11.0), (0.5, -4.0, 1.0), 50, (3, -3, 6), (-4, 1, 1)),
         ('top', (0.0, -4.0, 52.0), (0, -3.9, 0), 60, (-2, 2, 6), (3, -3, 2)),
         # round 2: whole-aircraft views a player has on the landing roll / fly-by (do the spoilers read as airbrakes?)
         ('rear', (0.0, -40.0, 7.5), (0, -3.0, 1.2), 50, (2, -4, 6), (-3, 2, 1)),
         ('frontq', (-21.0, 27.0, 9.0), (0, -1.5, 1.0), 50, (-3, 4, 6), (4, -2, 1))]
if arg('--views'):
    VIEWS = [v for v in VIEWS if v[0] in arg('--views').split(',')]
if 'liveries' in ONLY:
    for key in keys:
        use_livery(key)
        for state, deg, lit in (('shut_unlit', 0.0, False), ('open_lit', ANGLE, True)):
            spoilers(deg); lights(lit); day()
            for v, loc, look, lens, sf, ff in VIEWS:
                shot(f'{key}_{state}_{v}', loc, look, lens, sf, ff)
if 'closeups' in ONLY:
    use_livery(keys[0]); day()
    CU = [('spoiler_in_R', (4.9, -5.6, 3.0), (2.05, -1.45, 0.40), 50), ('spoiler_mid_R', (9.0, -6.2, 3.6), (5.9, -1.35, 0.62), 50),
          ('spoiler_out_R', (11.0, -5.8, 3.6), (8.1, -1.25, 0.72), 50),
          ('spoilers_L_rear', (-4.6, -10.5, 3.6), (-4.9, -1.3, 0.5), 35), ('spoilers_R_rear', (4.6, -10.5, 3.6), (4.9, -1.3, 0.5), 35),
          ('spoilers_R_graze', (12.0, -2.9, 1.7), (4.5, -1.3, 0.5), 50), ('spoilers_R_frontq', (10.5, 8.5, 6.0), (5.0, -1.3, 0.5), 50),
          ('bed_mid_R', (6.3, -4.4, 2.6), (5.9, -1.55, 0.60), 50), ('bed_in_R_top', (2.05, -2.6, 4.2), (2.05, -1.75, 0.40), 50),
          ('strip_fwd_L', (-6.5, 4.6, 1.9), (-1.1, 3.8, 1.15), 60), ('strip_aft_R', (6.5, -8.0, 2.2), (0.93, -7.2, 1.1), 60),
          ('strip_fin_L', (-7.0, -13.0, 4.6), (-0.12, -11.6, 4.3), 60), ('strip_tip_R', (17.6, -3.6, 3.2), (15.05, -0.3, 1.12), 60)]
    if arg('--cu'):
        CU = [c for c in CU if c[0] in arg('--cu').split(',')]
    for state, deg, lit in (('shut_unlit', 0.0, False), ('open_lit', ANGLE, True)):
        spoilers(deg); lights(lit)
        for n, loc, look, lens in CU:
            shot(f'cu_{n}_{state}', loc, look, lens, (-2, -2, 6) if 'spoiler' in n else (V(loc) - V(look)).normalized() * 4 + V((0, 0, 4)), (3, 3, 1))
if 'night' in ONLY:
    use_livery(keys[0]); spoilers(0.0); lights(True); day(True)
    for v, loc, look, lens, sf, ff in VIEWS:
        shot(f'night_lit_{v}', loc, look, lens, sf, ff)
    shot('night_lit_frontq', (-16.0, 22.0, 6.0), (0, 0.0, 1.2), 50)
spoilers(0.0); lights(False)
