"""B-17G 1.8.8 proof renders: our model and the War Thunder reference from the SAME cameras, gear UP, with a 1 m grid.

  blender --background <b17g.blend> --python blender/b17g/render_proof188.py -- --out <dir> --tag <before|after> \
          --tex assets/textures_b17g --ref <WT obj> [--grey] [--only v1,v2] [--livery usaaf_od]

Output goes OUTSIDE the repo (nuclearoption-ref/study/b17g_188). The reference is imported in memory only (Blender OBJ importer, its
own textures, rotated 180 deg about Z and scaled to the real 31.62 m span = the frame every B-17G number was measured in) and rendered
to <dir>/<view>_ref[_grey].png; it is never saved, exported or copied into our model. Grid: red lines every metre of y (blue every 5 m,
green y = 0), yellow every metre of z, drawn behind the aircraft in the side / under / top / rear views.
"""
import bpy, sys, os, math, json
from mathutils import Vector as V, Euler, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
OUT, TAG, TEX, REF = os.path.abspath(arg('--out', '.')), arg('--tag', 'ours'), arg('--tex'), arg('--ref')
GREY = '--grey' in argv
ONLY = arg('--only')
LIV_KEY = arg('--livery', 'usaaf_od')
SUFFIX = '_grey' if GREY else ''
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene

ours = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.endswith('_hullsrc')]
for o in bpy.data.objects:
    if o.name.endswith('_hullsrc'):      # collider sources (deleted in Unity) are never drawn
        o.hide_render = True

sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
w = sc.world or bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get('Background'); bg.inputs[0].default_value = (0.62, 0.70, 0.80, 1); bg.inputs[1].default_value = 0.9
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.0; sun.rotation_euler = Euler((math.radians(40), math.radians(15), math.radians(35)))
fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill)
fill.data.energy = 1.8; fill.rotation_euler = Euler((math.radians(150), 0, math.radians(-140)))
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


def set_tex(mat, b, n=None, uv='livery'):
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


def flat(name, rgba, rough=0.6, emit=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    bs = m.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value = rgba; bs.inputs['Roughness'].default_value = rough
    if emit:
        bs.inputs['Emission Color'].default_value = rgba; bs.inputs['Emission Strength'].default_value = 1.0
    return m


grey = flat('cmp_grey', (0.55, 0.56, 0.55, 1))
glass_grey = flat('cmp_glass', (0.25, 0.32, 0.38, 1), 0.1)
if GREY:
    for o in ours:
        for k in range(len(o.data.materials)):
            mt = o.data.materials[k]
            o.data.materials[k] = glass_grey if (mt and mt.name.startswith('glass')) else grey
elif TEX:
    T = os.path.abspath(TEX)
    LIV = json.load(open(os.path.join(T, 'b17g_liveries.json'))) if os.path.exists(os.path.join(T, 'b17g_liveries.json')) else {}
    paint = bpy.data.materials.get('paint')
    key = LIV_KEY if LIV_KEY in LIV else (list(LIV)[0] if LIV else None)
    if paint and key:
        set_tex(paint, img(os.path.join(T, LIV[key]['texture'])), img(os.path.join(T, 'b17g_skin_n.png'), True))
    for k in ('structure', 'interior', 'well', 'gear', 'tyre', 'cowl', 'turret'):
        mt = bpy.data.materials.get(k); b = img(os.path.join(T, f'b17g_tile_{k}_b.png'))
        if mt and b:
            set_tex(mt, b, img(os.path.join(T, f'b17g_tile_{k}_n.png'), True), uv='detail')
    gl = bpy.data.materials.get('glass')
    if gl and gl.use_nodes:
        bs = gl.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value = (0.30, 0.38, 0.44, 1); bs.inputs['Roughness'].default_value = 0.05
        try:
            bs.inputs['Alpha'].default_value = 0.55; gl.surface_render_method = 'BLENDED'
        except Exception:
            pass

# gear up (as the reference, which is modelled retracted)
for o in bpy.data.objects:
    info = json.loads(o.get('b25_info') or '{}') if o.get('b25_info') else {}
    if info.get('kind') == 'gear':
        deg = info['fold_deg'] * (1 if info.get('fold_sense') == 'forward-up' else -1)
        o.rotation_euler = Euler((math.radians(deg), 0, 0))
bpy.context.view_layer.update()

ref = []
if REF:
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(filepath=REF)
    ref = [o for o in bpy.data.objects if o not in before]
    pts = [o.matrix_world @ v.co for o in ref if o.type == 'MESH' and 'wing_' in o.name for v in o.data.vertices]
    K = 31.62 / (max(p.x for p in pts) - min(p.x for p in pts))
    M = Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Scale(K, 4)
    for o in ref:
        if o.parent is None:
            o.matrix_world = M @ o.matrix_world
        o.hide_render = True
        if o.type == 'MESH' and any(s in o.name for s in ('us_250', 'antenna')):
            o.hide_render = True
        if GREY and o.type == 'MESH':
            for k in range(len(o.data.materials)):
                o.data.materials[k] = grey
REF_HIDE = ('us_250', 'antenna')

# ---------------------------------------------------------------- grid (thin emissive bars, behind the aircraft for each view)
GRID = []
red, blue, green, yel = (flat('g_r', (0.9, 0.1, 0.1, 1), emit=True), flat('g_b', (0.1, 0.3, 1.0, 1), emit=True),
                         flat('g_g', (0.1, 0.9, 0.1, 1), emit=True), flat('g_y', (0.85, 0.8, 0.1, 1), emit=True))


def bar(p, size, mat, tag):
    bpy.ops.mesh.primitive_cube_add(location=p); g = bpy.context.object; g.scale = size
    g.data.materials.append(mat); g['grid'] = tag; g.hide_render = True; GRID.append(g)


for yy in range(-17, 9):
    m = green if yy == 0 else (blue if yy % 5 == 0 else red)
    bar((0, yy, -8.0), (20, 0.008, 0.008), m, 'under')         # under views: below the aircraft (camera below looks up through it? no: behind = above)
    bar((0, yy, 9.0), (20, 0.008, 0.008), m, 'top_behind_under')
    bar((-14.0, yy, 1.0), (0.008, 0.008, 8), m, 'side')          # side views from +x: grid on the far side (x = -14)
for zz in range(-3, 7):
    bar((-14.0, -4.0, zz), (0.008, 14, 0.006), yel, 'side')
for xx in range(-16, 17):
    bar((xx, -25.0, 1.0), (0.008, 0.008, 6), yel if xx % 5 else blue, 'rear')   # rear views from -y: grid ahead of the nose
for zz in range(-3, 7):
    bar((0, -25.0 if False else 25.0, zz), (17, 0.008, 0.006), yel, 'rear')
for g in GRID:
    if g['grid'] == 'rear':
        g.location.y = 25.0
bpy.context.view_layer.update()


def cam(loc, tgt, lens=40, ortho=None, up=None):
    c = bpy.data.cameras.new('c'); c.clip_start = 0.05; c.clip_end = 400
    if ortho:
        c.type = 'ORTHO'; c.ortho_scale = ortho
    else:
        c.lens = lens
    o = bpy.data.objects.new('c', c); sc.collection.objects.link(o)
    o.location = V(loc)
    d = (V(tgt) - V(loc)).normalized()
    if d.z < -0.99:          # looking down: nose (+y) up in the frame, right wing right
        o.rotation_euler = Euler((0, 0, 0))
    elif d.z > 0.99:         # looking up from below: nose up in the frame (left wing on the right)
        o.rotation_euler = Euler((math.pi, 0, math.pi))
    else:                    # camera local Y toward world +Z
        o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def shot(name, c, grid=None, res=(1600, 1000), clip=None):
    sc.camera = c; sc.render.resolution_x, sc.render.resolution_y = res
    if clip:
        c.data.clip_start = clip
    for g in GRID:
        g.hide_render = (g['grid'] != grid)
    for who, objs, others in (('ours', ours, ref), ('ref', ref, ours)):
        if who == 'ref' and not ref:
            continue
        for o in others:
            o.hide_render = True
        for o in objs:
            o.hide_render = (o.name.endswith('_hullsrc') or any(s in o.name for s in REF_HIDE))
        sc.render.filepath = os.path.join(OUT, f'{name}_{TAG if who == "ours" else "ref"}{SUFFIX}.png')
        bpy.ops.render.render(write_still=True)
    for o in ours:
        o.hide_render = o.name.endswith('_hullsrc')
    print('[render]', name)


# views: (camera location, target, lens or None, ortho scale or None, grid tag, near clip)
VIEWS = {
    # nacelles, left wing (engines 1 outer, 2 inner): from below (looking up, nose up in the frame), from outboard, top
    'nac_L_under': ((-4.85, 1.2, -12.0), (-4.85, 1.2, 0.0), None, 9.5, 'top_behind_under', None),
    'nac_R_under': ((4.85, 1.2, -12.0), (4.85, 1.2, 0.0), None, 9.5, 'top_behind_under', None),
    'nac_L_top': ((-4.85, 1.2, 12.0), (-4.85, 1.2, 0.0), None, 9.5, 'under', None),
    'nac_outer_side': ((-20.0, 1.0, 0.2), (0.0, 1.0, 0.2), None, 7.0, None, 20.0 - 7.45),
    'nac_inner_side': ((-20.0, 1.2, 0.0), (0.0, 1.2, 0.0), None, 7.0, None, 20.0 - 3.95),
    'nac_under34': ((-10.5, -1.5, -6.5), (-4.6, 1.5, -0.4), 30, None, None, None),
    'nac_rear34': ((-9.6, -5.8, -1.6), (-4.8, 0.8, -0.2), 30, None, None, None),
    'nac_front34': ((-9.8, 8.8, -1.8), (-4.8, 2.4, 0.0), 30, None, None, None),
    # tail
    'tail_side': ((12.0, -13.6, 1.0), (0.0, -13.6, 1.0), None, 4.2, 'side', 12.0 - 1.3),
    'tail_rear34': ((3.6, -20.5, 2.4), (0.0, -14.6, 0.95), 40, None, None, None),
    'tail_rear': ((0.0, -30.0, 1.0), (0.0, -14.0, 1.0), None, 3.2, 'rear', None),
    'tail_top': ((0.0, -13.6, 12.0), (0.0, -13.6, 0.0), None, 4.2, 'under', None),
    'tail_under34': ((2.8, -19.0, -1.4), (0.0, -14.5, 0.7), 40, None, None, None),
    'tail_close': ((1.9, -17.2, 1.7), (0.0, -14.8, 0.95), 50, None, None, None),
    'nac_inner_end': ((-4.6, -2.6, -1.9), (-3.1, -0.4, -0.35), 40, None, None, None),
    'full_side': ((40.0, -3.8, 1.0), (0.0, -3.8, 1.0), None, 24.5, 'side', None),
}
for g in GRID:      # the side grid sits on the far side of the camera (x = -14 for views from +x, x = +14 from -x)
    pass
for nm, (loc, tgt, lens, ortho, grid, clip) in VIEWS.items():
    if ONLY and nm not in ONLY.split(','):
        continue
    if grid == 'side':
        for g in GRID:
            if g['grid'] == 'side':
                g.location.x = -14.0 if loc[0] > 0 else 14.0
    if nm in ('nac_outer_side', 'nac_inner_side'):
        grid = 'side'
        for g in GRID:
            if g['grid'] == 'side':
                g.location.x = 14.0
    c = cam(loc, tgt, lens or 40, ortho)
    shot(nm, c, grid, clip=clip)
