"""1.9.12 review render: the MSB-17 formation-light strips beside a STOCK aircraft's strips at the same scale (are 10 cm strips too heavy?).

  blender -b <msb1780.blend> -P blender/msb1780/render_stripcmp1912.py -- --out <dir outside the repo> [--prefab EW1] [--tex assets/textures_msb1780]

The stock aircraft is read from the user's own AssetRipper export at render time (prefab transforms + mesh assets), built in memory as
objects named stock_* and never saved: nothing of the game enters the repo or the .blend. Stock meshes are shown in flat grey (no stock
texture is read); its strips and ours use the same two materials (stock light_green_off colour unlit, slimelight_on emission lit).
Orthographic cameras, so both aircraft are drawn at exactly the same metres per pixel.
"""
import bpy, sys, os, re, struct, math, json
from mathutils import Vector as V, Matrix, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return argv[argv.index(k) + 1] if k in argv else d


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.abspath(arg('--out', '.')); os.makedirs(OUT, exist_ok=True)
TEX = os.path.abspath(arg('--tex', os.path.join(ROOT, 'assets', 'textures_msb1780')))
PREFAB = arg('--prefab', 'EW1')
A = arg('--export', r'C:\Users\User\nuclearoption-ref\tools\assetripper\NUCLEAROPTIONEXPORTS\ExportedProject\Assets')
SKIP = ('lod1', 'lod2', 'lod3', 'collider', 'debris', 'destroyed', 'shadow', 'proxy', 'dmg', 'damage')


def read_mesh(path):
    txt = open(path, encoding='utf-8', errors='ignore').read()
    vc = int(re.search(r'm_VertexCount: (\d+)', txt).group(1))
    chans = [tuple(map(int, c)) for c in re.findall(r'- stream: (\d+)\s+offset: (\d+)\s+format: (\d+)\s+dimension: (\d+)', txt)]
    m = re.search(r'_typelessdata: ([0-9a-f]+)', txt)
    if not m or not vc:
        return [], []
    data = bytes.fromhex(m.group(1))
    size = {0: 4, 1: 2, 2: 1, 3: 1, 4: 2, 5: 2}
    stride = 0
    for s, off, fmt, dim in chans:
        if s == 0 and dim:
            stride = max(stride, off + (dim & 0xF) * size.get(fmt, 4))
    pos = chans[0]
    if not (pos[2] == 0 and (pos[3] & 0xF) == 3):
        return [], []
    verts = [struct.unpack_from('<3f', data, i * stride + pos[1]) for i in range(vc)]
    ib = bytes.fromhex(re.search(r'm_IndexBuffer: ([0-9a-f]*)', txt).group(1))
    fmt32 = int(re.search(r'm_IndexFormat: (\d)', txt).group(1)) == 1
    tris = []
    for fb, ic, top, bv in re.findall(r'firstByte: (\d+)\s+indexCount: (\d+)\s+topology: (\d+)\s+baseVertex: (\d+)', txt):
        fb, ic, bv = int(fb), int(ic), int(bv)
        idx = struct.unpack_from(('<%dI' if fmt32 else '<%dH') % ic, ib, fb)
        tris += [(idx[k] + bv, idx[k + 1] + bv, idx[k + 2] + bv) for k in range(0, ic - 2, 3)]
    return verts, tris


def load_prefab(name):
    """-> [(object name, [world points in the Unity frame], triangles)] of every enabled mesh renderer of the prefab"""
    guid2mesh = {}
    for f in os.listdir(os.path.join(A, 'Mesh')):
        if f.endswith('.asset.meta'):
            g = re.search(r'guid: (\w+)', open(os.path.join(A, 'Mesh', f)).read())
            if g:
                guid2mesh[g.group(1)] = os.path.join(A, 'Mesh', f[:-5])
    txt = open(os.path.join(A, 'GameObject', name + '.prefab'), encoding='utf-8', errors='ignore').read()
    docs = re.split(r'\n--- !u!(\d+) &(\d+)[^\n]*\n', txt)
    objs = {docs[i + 1]: (docs[i], docs[i + 2]) for i in range(1, len(docs), 3)}
    go, tr, go2tr, mf, off = {}, {}, {}, {}, set()
    f3 = r'\{x: ([-+\d.eE]+), y: ([-+\d.eE]+), z: ([-+\d.eE]+)\}'
    for k, (cls, body) in objs.items():
        if cls == '1':
            go[k] = re.search(r'm_Name: (.*)', body).group(1).strip()
            if re.search(r'm_IsActive: 0', body):
                off.add(k)
        elif cls == '4':
            g = re.search(r'm_GameObject: \{fileID: (\d+)\}', body).group(1)
            pos = tuple(map(float, re.search(r'm_LocalPosition: ' + f3, body).groups()))
            rot = tuple(map(float, re.search(r'm_LocalRotation: \{x: ([-+\d.eE]+), y: ([-+\d.eE]+), z: ([-+\d.eE]+), w: ([-+\d.eE]+)\}', body).groups()))
            sc = tuple(map(float, re.search(r'm_LocalScale: ' + f3, body).groups()))
            tr[k] = (g, pos, rot, sc, re.search(r'm_Father: \{fileID: (\d+)\}', body).group(1)); go2tr[g] = k
        elif cls == '33':
            g = re.search(r'm_GameObject: \{fileID: (\d+)\}', body).group(1)
            m = re.search(r'm_Mesh: \{fileID: \d+, guid: (\w+)', body)
            if m:
                mf[g] = m.group(1)
        elif cls == '23':
            g = re.search(r'm_GameObject: \{fileID: (\d+)\}', body).group(1)
            if re.search(r'm_Enabled: 0', body):
                off.add(g)

    def world(g):
        k = go2tr[g]; Mx = Matrix.Identity(4); hidden = False
        while k in tr:
            gg, pos, rot, sc, par = tr[k]
            hidden = hidden or gg in off
            T = Matrix.Translation(pos) @ Quaternion((rot[3], rot[0], rot[1], rot[2])).to_matrix().to_4x4() @ Matrix.Diagonal((sc[0], sc[1], sc[2], 1.0))
            Mx = T @ Mx; k = par
        return Mx, hidden

    out = []
    for g, guid in mf.items():
        nm = go.get(g, '?')
        if guid not in guid2mesh or any(s in nm.lower() for s in SKIP):
            continue
        Mx, hidden = world(g)
        if hidden:
            continue
        verts, tris = read_mesh(guid2mesh[guid])
        if verts and tris:
            out.append((nm, [Mx @ V(v) for v in verts], tris))
    return out


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

# our aircraft: the default livery on the paint material
LIV = json.load(open(os.path.join(TEX, 'msb17_liveries.json')))
key = arg('--livery', list(LIV)[0])
paint = bpy.data.materials.get('paint'); paint.use_nodes = True
nt = paint.node_tree; bs = nt.nodes.get('Principled BSDF')
uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'livery'
t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(os.path.join(TEX, LIV[key]['texture']), check_existing=True)
nt.links.new(uvn.outputs[0], t.inputs[0]); nt.links.new(t.outputs[0], bs.inputs['Base Color'])

LO = bpy.data.materials.get('light_off')
grey = bpy.data.materials.new('stock_grey'); grey.use_nodes = True
grey.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (0.19, 0.20, 0.21, 1)
grey.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = 0.7

# the stock aircraft, nose to tail AHEAD of ours (same side view, nothing hides anything)
parts = load_prefab(PREFAB)
allp = [p for _, ps, _ in parts for p in ps]
uy0 = min(p.y for p in allp); uz0, uz1 = min(p.z for p in allp), max(p.z for p in allp); ux = max(abs(p.x) for p in allp)
ours = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.endswith('_hullsrc')]
oz0 = min((o.matrix_world @ V(c)).z for o in ours for c in o.bound_box); oy1 = max((o.matrix_world @ V(c)).y for o in ours for c in o.bound_box)
shift = V((0.0, oy1 + 3.0 - uz0, oz0 - uy0))      # Unity (x, y up, z fwd) -> Blender (x, z, y): its tail 3 m ahead of our nose, wheels level
stock_strips = []
for nm, ps, tris in parts:
    me = bpy.data.meshes.new('stock_' + nm)
    me.from_pydata([V((p.x, p.z, p.y)) + shift for p in ps], [], [(a, c, b) for a, b, c in tris])
    is_strip = 'slime' in nm.lower()
    me.materials.append(LO if is_strip else grey)
    o = bpy.data.objects.new('stock_' + nm, me); sc.collection.objects.link(o)
    if is_strip:
        stock_strips.append(o)
print(f'[cmp] stock {PREFAB}: {len(parts)} meshes, length {uz1 - uz0:.2f} m, half span {ux:.2f} m, strips {[o.name for o in stock_strips]}')
for o in stock_strips:
    vs = [v.co for v in o.data.vertices]
    d = [max(v[k] for v in vs) - min(v[k] for v in vs) for k in range(3)]
    print(f'[cmp]   {o.name}: box {d[0]:.3f} x {d[1]:.3f} x {d[2]:.3f} m, centre y {sum(v.y for v in vs) / len(vs):.2f} z {sum(v.z for v in vs) / len(vs):.2f}')

sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
fill = bpy.data.objects.new('fill', bpy.data.lights.new('fill', 'SUN')); sc.collection.objects.link(fill)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.clip_start = 0.1; cam.data.clip_end = 400


def aim(o, loc, look):
    o.location = V(loc); o.rotation_euler = (V(look) - V(loc)).to_track_quat('-Z', 'Y').to_euler()


def lights(on, night=False):
    bs = LO.node_tree.nodes.get('Principled BSDF') if LO.use_nodes else None
    if bs is None:
        LO.use_nodes = True; bs = LO.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1) if on else (0.473, 0.612, 0.537, 1)
    bs.inputs['Emission Color'].default_value = (0.047, 1.0, 0.11, 1); bs.inputs['Emission Strength'].default_value = 3.0 if on else 0.0
    BG.inputs[0].default_value = (0.01, 0.012, 0.02, 1) if night else (0.62, 0.70, 0.80, 1)
    BG.inputs[1].default_value = 0.25 if night else 0.9
    sun.data.energy = 0.12 if night else 3.5; fill.data.energy = 0.05 if night else 1.2


def shot(name, look, scale, res, dist=120.0, direction=(-1, 0, 0.06)):
    d = V(direction).normalized()
    aim(cam, V(look) + d * dist, look); cam.data.ortho_scale = scale
    aim(sun, V(look) + V((-4, 2, 5)), look); aim(fill, V(look) + V((-2, -4, -1)), look)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, f'cmp_{PREFAB}_{name}.png')
    bpy.ops.render.render(write_still=True); print('[cmp]', sc.render.filepath)


mid_y = (oy1 + 3.0 + (uz1 - uz0) + min((o.matrix_world @ V(c)).y for o in ours for c in o.bound_box)) / 2
span_y = oy1 + 3.0 + (uz1 - uz0) - min((o.matrix_world @ V(c)).y for o in ours for c in o.bound_box)
sy = sum(v.co.y for o in stock_strips for v in o.data.vertices) / max(1, sum(len(o.data.vertices) for o in stock_strips))
fwd_stock = [o for o in stock_strips if sum(v.co.y for v in o.data.vertices) / len(o.data.vertices) > sy] or stock_strips
fy = sum(v.co.y for o in fwd_stock for v in o.data.vertices) / sum(len(o.data.vertices) for o in fwd_stock)
fz = sum(v.co.z for o in fwd_stock for v in o.data.vertices) / sum(len(o.data.vertices) for o in fwd_stock)
for state, on, night in (('unlit', False, False), ('lit', True, False), ('night', True, True)):
    lights(on, night)
    shot(f'whole_side_{state}', (0, mid_y, 1.5), span_y + 4.0, (2400, 560))                 # both aircraft, same metres per pixel
    shot(f'ours_fwd_{state}', (0, 3.8, 1.15), 7.0, (1000, 560))                             # our forward strip, 7 m across
    shot(f'stock_fwd_{state}', (0, fy, fz), 7.0, (1000, 560))                               # the stock forward strip, 7 m across
    shot(f'whole_rearq_{state}', (0, mid_y, 1.5), span_y + 10.0, (2400, 900), direction=(-1.0, -0.8, 0.45))
