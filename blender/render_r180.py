"""Heritage Pairs 1.8.0 before / after render pairs (offline worker). Renders only; nothing here changes a model.

  blender --background <model.blend> --python blender/render_r180.py -- --mode <mode> --out <png prefix> [options]

modes
  geom      --cams <set> [--ref <WT obj>] [--glow]   Workbench, material colours (geometry: cockpit opening, tail window, strip lights)
  albedo    --tex <dir> --gain 0|1                   Eevee, B-25H cockpit from the pilot eye with the textures x the 1.8.0 Unity gains
  dg        --tex <dir>                              Eevee, B-17G directional-gyro card straight on, atlas as emission
  guns      --barrel <stock mesh .asset> --variant old|new   B-17G gun stations with the stock barrel placed as the Unity build does
  dmg       --tex <dir> --variant before|after       Eevee, B-17G skin at ~15 % hit points (livery x damage map, AircraftSkin-like blend)
The stock barrel mesh is read from the user's Blueprinter project placeholder (in memory only, never saved).
"""
import bpy, sys, os, math, re, struct
from mathutils import Vector as V, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d
MODE, OUT = arg('--mode', 'geom'), arg('--out')
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
sc = bpy.context.scene
for o in bpy.data.objects:
    if o.name.startswith(('cooper_', 'wt_')):
        o.hide_render = True


def look(loc, tgt, lens=40, name='cam', up=V((0, 0, 1))):
    c = bpy.data.cameras.new(name); c.lens = lens; c.clip_start = 0.005; c.clip_end = 300
    o = bpy.data.objects.new(name, c); sc.collection.objects.link(o)
    o.location = V(loc)
    d = (V(tgt) - V(loc)).normalized()
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def render(path, cam, res=(1400, 900)):
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('[r180]', path)


def workbench():
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.cavity_type = 'BOTH'
    sh.show_object_outline = False; sh.show_backface_culling = True
    sc.display.render_aa = '8'


def eevee(world=0.9):
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            sc.render.engine = eng; break
        except Exception:
            pass
    w = bpy.data.worlds.new('w'); w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (world, world, world, 1); sc.world = w
    sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 3.0
    so = bpy.data.objects.new('sun', sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(40), math.radians(15), math.radians(30))
    sc.view_settings.view_transform = 'Standard'


def img(path):
    return bpy.data.images.load(path, check_existing=True)


def lin_mean(im):
    import numpy as np
    a = np.array(im.pixels[:], dtype=np.float32).reshape(-1, 4)[::7, :3]
    a = a ** 2.2
    return float((a @ np.array([0.2126, 0.7152, 0.0722], np.float32)).mean())


def tex_mat(name, image, uv, gain=1.0, scale=1.0, emit=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uv
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale, scale, 1)
    ti = nt.nodes.new('ShaderNodeTexImage'); ti.image = image
    mul = nt.nodes.new('ShaderNodeMixRGB'); mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    mul.inputs[2].default_value = (gain, gain, gain, 1)
    nt.links.new(uvn.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], ti.inputs[0]); nt.links.new(ti.outputs[0], mul.inputs[1])
    if emit:
        sh = nt.nodes.new('ShaderNodeEmission'); nt.links.new(mul.outputs[0], sh.inputs[0])
    else:
        sh = nt.nodes.new('ShaderNodeBsdfPrincipled'); nt.links.new(mul.outputs[0], sh.inputs['Base Color']); sh.inputs['Roughness'].default_value = 0.7
    nt.links.new(sh.outputs[0], out.inputs[0])
    return m


def swap(matname, new):
    for o in bpy.data.objects:
        if o.type == 'MESH':
            for i, s in enumerate(o.material_slots):
                if s.material and s.material.name == matname:
                    o.material_slots[i].material = new


def import_ref(path):
    verts, faces = [], []
    for l in open(path):
        if l.startswith('v '):
            x, y, z = map(float, l.split()[1:4]); verts.append((-x, z, y))
        elif l.startswith('f '):
            faces.append([int(t.split('/')[0]) - 1 for t in l.split()[1:]])
    me = bpy.data.meshes.new('wtref'); me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new('wtref', me); sc.collection.objects.link(ob)
    return ob


CAMS = {
    'nimrod_ck': {'ck34': ((-1.7, -2.5, 1.85), (0, -0.72, 0.52), 45), 'cktop': ((0.0, -0.73, 3.6), (0, -0.72, 0.5), 45),
                  'ckside': ((-2.6, -0.55, 1.15), (0, -0.72, 0.55), 45), 'ckrear': ((0.6, -3.1, 1.45), (0, -0.70, 0.55), 45)},
    'fd32_ck': {'ck34': ((-1.7, -2.7, 1.9), (0, -0.85, 0.55), 40), 'cktop': ((0.0, -0.9, 3.8), (0, -0.9, 0.5), 40),
                'ckside': ((-2.7, -0.7, 1.2), (0, -0.85, 0.6), 40)},
    'fd32_lights': {'l34rear': ((-5.5, -7.5, 3.0), (0, -1.6, 0.4), 32), 'lside': ((-8.5, -1.6, 0.6), (0, -1.6, 0.4), 32),
                    'ltop': ((0.0, -1.5, 9.0), (0, -1.5, 0.3), 30), 'l34front': ((-5.0, 4.0, 2.2), (0, -1.0, 0.4), 32)},
    'b17_tail': {'rear34': ((2.6, -17.6, 1.6), (0, -14.9, 0.85), 35), 'rear': ((0.0, -18.2, 1.05), (0, -14.9, 0.85), 35),
                 'side': ((3.6, -14.8, 0.95), (0, -14.8, 0.85), 35), 'eye': ((0.0, -14.15, 1.15), (0, -16.0, 1.0), 30)},
}

if MODE == 'geom':
    workbench()
    ref = import_ref(arg('--ref')) if arg('--ref') else None
    if '--glow' in argv:
        for m in bpy.data.materials:
            if m.name == 'light_off':
                m.diffuse_color = (0.15, 1.0, 0.25, 1.0)
    for k, (loc, tgt, lens) in CAMS[arg('--cams')].items():
        c = look(loc, tgt, lens, k)
        if ref is not None:
            ref.hide_render = True
        render(f'{OUT}_{k}.png', c)
        if ref is not None:
            for o in bpy.data.objects:
                if o.type == 'MESH' and o is not ref:
                    o.hide_render = True
            ref.hide_render = False
            render(f'{OUT}_{k}_ref.png', c)
            for o in bpy.data.objects:
                if o.type == 'MESH' and o is not ref and not o.name.startswith(('cooper_', 'wt_')):
                    o.hide_render = False

elif MODE == 'albedo':
    # B-25H cockpit from the pilot eye; the cockpit materials get their textures (UV as the Unity build: tiles on 'detail', art / props on
    # 'livery') x the 1.8.0 gain (target 0.12 linear, cap 2.5) when --gain 1
    eevee(0.8)
    tex = arg('--tex'); g_on = arg('--gain', '0') == '1'
    def gain(im):
        return min(max(0.12 / max(lin_mean(im), 1e-4), 1.0), 2.5) if g_on else 1.0
    tiles = {'interior': ('b25h_interior_b', 'detail', 1.0), 'bk_quilt': ('b25h_quilt_b', 'detail', 5.0), 'bk_od': ('b25h_od_b', 'detail', 2.0),
             'bk_art': ('b25h_ckart_b', 'livery', 1.0), 'structure': ('b25h_structure_b', 'detail', 1.0), 'cockpit': ('b25h_cockpit_b', 'detail', 1.0),
             'gauges': ('b25h_gauges', 'livery', 1.0)}
    for p in ('yoke', 'column', 'throttle', 'proplever', 'mixture', 'trimwheel', 'pedal', 'seat', 'boot', 'footrest', 'loom'):
        tiles['pr_' + p] = (f'b25h_pr_{p}_b', 'livery', 1.0)
    rep = []
    for mname, (tn, uv, sc_) in tiles.items():
        f = os.path.join(tex, tn + '.png')
        if not os.path.exists(f) or mname not in bpy.data.materials:
            continue
        im = img(f); gn = gain(im) if mname not in ('gauges', 'structure', 'cockpit') else 1.0
        swap(mname, tex_mat(mname + '_r', im, uv, gn, sc_)); rep.append(f'{mname} x{gn:.2f}')
    if 'bk_black' in bpy.data.materials:
        bpy.data.materials['bk_black'].use_nodes = False
        v = (0.07 if g_on else 0.03); v = v ** 2.2
        bpy.data.materials['bk_black'].diffuse_color = (v, v, v * 1.1, 1)
    print('[r180] gains', rep)
    eye = bpy.data.objects['cockpit_eye'].matrix_world.translation
    for k, (d, lens) in {'eye_fwd': (V((0.15, 1.0, -0.30)), 26), 'eye_left': (V((-1.0, 0.6, -0.35)), 26)}.items():
        render(f'{OUT}_{k}.png', look(eye, eye + d, lens, k))

elif MODE == 'dg':
    eevee(0.6)
    o = bpy.data.objects['gauge_dg_card']
    im = img(os.path.join(arg('--tex'), 'b17g_gauges.png'))
    uv = 'livery' if 'livery' in o.data.uv_layers else o.data.uv_layers[0].name
    m = tex_mat('dg_r', im, uv, 1.0, 1.0, emit=True)
    for i, s in enumerate(o.material_slots):
        o.material_slots[i].material = m
    M = o.matrix_world; c = M.translation; X = (M.to_3x3() @ V((1, 0, 0))).normalized()
    render(OUT + '_card.png', look(c + X * 0.30, c, 50, 'dg'), (900, 900))
    pe = bpy.data.objects.get('cockpit_eye') or bpy.data.objects.get('crew_pilot_eye')
    if pe is not None:
        render(OUT + '_eye.png', look(pe.matrix_world.translation, c, 30, 'dge'), (1200, 900))

elif MODE == 'guns':
    workbench()
    # stock barrel vertices / indices from the Blueprinter placeholder asset (float32 position stream, uint16 indices)
    y = open(arg('--barrel'), encoding='utf-8').read()
    vc = int(re.search(r'm_VertexCount: (\d+)', y).group(1))
    data = bytes.fromhex(re.search(r'_typelessdata: ([0-9a-f]+)', y).group(1))
    stride = len(data) // vc
    vs = [struct.unpack_from('<3f', data, i * stride) for i in range(vc)]
    ib = bytes.fromhex(re.search(r'm_IndexBuffer: ([0-9a-f]+)', y).group(1))
    idx = struct.unpack('<%dH' % (len(ib) // 2), ib)
    tris = [idx[i:i + 3] for i in range(0, len(idx) - 2, 3)]
    xs = [v[0] for v in vs]; ys_ = [v[1] for v in vs]; zs = [v[2] for v in vs]
    zmax = max(zs); tip = [v for v in vs if v[2] > zmax - 0.03]
    bore = (sum(v[0] for v in tip) / len(tip), sum(v[1] for v in tip) / len(tip))
    bctr = ((min(xs) + max(xs)) / 2, (min(ys_) + max(ys_)) / 2)
    off = bctr if arg('--variant') == 'old' else bore
    print('[r180] barrel bore', bore, 'bounds centre', bctr, 'used', off)
    red = bpy.data.materials.new('fireline'); red.diffuse_color = (1, 0.05, 0.05, 1)
    blk = bpy.data.materials.new('barrel'); blk.diffuse_color = (0.08, 0.08, 0.08, 1)
    guns = [o for o in bpy.data.objects if re.match(r'.*_gun\d*$|.*gun_[LR]$|.*_gun_\d$', o.name) and not o.name.startswith('cockpit')]
    muzz = {o.name: o for o in bpy.data.objects if 'muzzle' in o.name}
    n_ = 0
    for g in bpy.data.objects:
        mz = None
        for cand in g.children:
            if 'muzzle' in cand.name:
                mz = cand
        if mz is None:
            continue
        P = g.matrix_world.translation; bore_d = (mz.matrix_world.translation - P).normalized()
        upw = V((0, 0, 1)) if abs(bore_d.z) < 0.9 else V((0, 1, 0))
        right = bore_d.cross(upw).normalized(); up = right.cross(bore_d).normalized()
        g.hide_render = True
        for ch in g.children_recursive:
            if ch.type == 'MESH':
                ch.hide_render = True
        base = P + right * (-off[0]) + up * (-off[1])
        verts = [base + right * v[0] + up * v[1] + bore_d * v[2] for v in vs]
        me = bpy.data.meshes.new('bar_' + g.name); me.from_pydata([tuple(v) for v in verts], [], [tuple(t) for t in tris]); me.materials.append(blk)
        ob = bpy.data.objects.new('bar_' + g.name, me); sc.collection.objects.link(ob)
        # fire line: thin box from the muzzle 1.5 m out along the bore (where the rounds fly)
        a = mz.matrix_world.translation; L = 1.5; w = 0.006
        lv = [a + right * sx * w + up * sy * w + bore_d * t for t in (0, L) for sx in (-1, 1) for sy in (-1, 1)]
        lf = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        lm = bpy.data.meshes.new('fl_' + g.name); lm.from_pydata([tuple(v) for v in lv], [], lf); lm.materials.append(red)
        lo = bpy.data.objects.new('fl_' + g.name, lm); sc.collection.objects.link(lo)
        n_ += 1
    print('[r180] guns placed', n_)
    shots = {'chin': ((1.6, 8.6, -0.3), (0, 6.2, -0.7), 35), 'cheek_R': ((2.4, 7.8, 0.9), (1.0, 5.9, 0.62), 35),
             'top': ((2.2, 4.2, 3.0), (0, 2.1, 2.2), 35), 'ball': ((1.8, -2.0, -1.6), (0, -3.95, -0.8), 35),
             'tail': ((1.6, -17.4, 1.2), (0, -14.9, 0.7), 35), 'waist_R': ((3.0, -3.6, 1.1), (0.92, -5.17, 0.7), 35),
             'waist_L': ((-3.0, -8.4, 1.1), (-0.86, -6.70, 0.7), 35), 'radio': ((1.4, -1.4, 2.6), (0, -3.0, 1.78), 35)}
    for k, (loc, tgt, lens) in shots.items():
        render(f'{OUT}_{k}.png', look(loc, tgt, lens, k), (1100, 800))

elif MODE == 'dmg':
    eevee(0.7)
    tex = arg('--tex'); after = arg('--variant') == 'after'
    liv = img(os.path.join(tex, 'b17g_skin_b.png'))
    m = bpy.data.materials.new('dmgpaint'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); bs = nt.nodes.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value = 0.6
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'livery'
    t1 = nt.nodes.new('ShaderNodeTexImage'); t1.image = liv
    mix = nt.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 0.85
    nt.links.new(uvn.outputs[0], t1.inputs[0]); nt.links.new(t1.outputs[0], mix.inputs[1])
    if after:
        t2 = nt.nodes.new('ShaderNodeTexImage'); t2.image = img(os.path.join(tex, 'b17g_skin_dmg_b.png'))
        nt.links.new(uvn.outputs[0], t2.inputs[0]); nt.links.new(t2.outputs[0], mix.inputs[2])
    else:
        mix.inputs[2].default_value = (40 / 255.0, 36 / 255.0, 32 / 255.0, 1)      # the 1.7.x flat fallback (b17g_tex.cs FallbackTexture)
    nt.links.new(mix.outputs[0], bs.inputs['Base Color']); nt.links.new(bs.outputs[0], out.inputs[0])
    swap('paint', m)
    for k, (loc, tgt, lens) in {'waist': ((5.5, -9.0, 2.2), (0, -6.0, 0.6), 35), 'nose': ((4.5, 9.0, 1.6), (0, 4.5, 0.6), 35),
                                'wing': ((-9.0, -2.0, 4.5), (-6.0, 1.0, 0.3), 35)}.items():
        render(f'{OUT}_{k}.png', look(loc, tgt, lens, k), (1200, 800))
