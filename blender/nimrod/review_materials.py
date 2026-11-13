"""Apply the Nimrod's built textures to the .blend materials for review renders, the way NimrodBuild.cs maps them in Unity:
paint = livery atlas (UV 'livery') + skin normal/metal maps; tiles nimrod_tile_<mat>_b/_n on UV 'detail' (x the Unity tile
scale for the cockpit ck_* tiles); ck_art / gauges / pr_<prop> on their own UVs (layer 'livery')."""
import bpy, os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def img(path, nonc=False):
    if not os.path.exists(path):
        return None
    im = bpy.data.images.load(path, check_existing=True)
    if nonc:
        im.colorspace_settings.name = 'Non-Color'
    return im


def setup(mat, b, n=None, m=None, uv='livery', scale=1.0, met=None, rough=None):
    mat.use_nodes = True
    nt = mat.node_tree
    bs = nt.nodes.get('Principled BSDF')
    if bs is None:
        return
    for nd in list(nt.nodes):
        if nd.type not in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL'):
            nt.nodes.remove(nd)
    uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = uv
    src = uvn.outputs[0]
    if scale != 1.0:
        mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (scale, scale, 1)
        nt.links.new(uvn.outputs[0], mp.inputs[0]); src = mp.outputs[0]
    tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = b
    nt.links.new(src, tb.inputs[0]); nt.links.new(tb.outputs[0], bs.inputs['Base Color'])
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
    else:
        if met is not None:
            bs.inputs['Metallic'].default_value = met
        if rough is not None:
            bs.inputs['Roughness'].default_value = rough


def apply(T, livery=None):
    try:
        import nimrod_ck_layout as CL
        scales, pbr = CL.TILE_SCALE, CL.TILE_PBR
    except Exception:
        scales, pbr = {}, {}
    liv = json.load(open(os.path.join(T, 'nimrod_liveries.json'))) if os.path.exists(os.path.join(T, 'nimrod_liveries.json')) else {}
    lk = livery if livery in liv else (list(liv)[0] if liv else None)
    for mat in bpy.data.materials:
        n = mat.name
        if n == 'paint' and lk:
            setup(mat, img(os.path.join(T, liv[lk]['texture'])), img(os.path.join(T, 'nimrod_skin_n.png'), True), img(os.path.join(T, 'nimrod_skin_m.png'), True))
        elif n == 'ck_art' and img(os.path.join(T, 'nimrod_ckart_b.png')):
            setup(mat, img(os.path.join(T, 'nimrod_ckart_b.png')), img(os.path.join(T, 'nimrod_ckart_n.png'), True), met=0.1, rough=0.55)
        elif n == 'gauges' and img(os.path.join(T, 'nimrod_gauges.png')):
            setup(mat, img(os.path.join(T, 'nimrod_gauges.png')), rough=0.45)
        elif n.startswith('pr_') and img(os.path.join(T, f'nimrod_{n}_b.png')):
            setup(mat, img(os.path.join(T, f'nimrod_{n}_b.png')), img(os.path.join(T, f'nimrod_{n}_n.png'), True), met=0.3, rough=0.5)
        elif img(os.path.join(T, f'nimrod_tile_{n}_b.png')):
            met, sm = pbr.get(n, (None, None))
            setup(mat, img(os.path.join(T, f'nimrod_tile_{n}_b.png')), img(os.path.join(T, f'nimrod_tile_{n}_n.png'), True), uv='detail',
                  scale=scales.get(n, 1.0), met=met, rough=(1 - sm) if sm is not None else None)
    return lk
