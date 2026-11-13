"""Read a stock Nuclear Option mesh from the user's own Blueprinter project (AssetRipper placeholder .asset, Unity YAML) into Blender
for CHECKS and REVIEW RENDERS ONLY. Nothing is copied into the repo: the objects this module creates are named 'stock_*' and the
build never saves them (build_msb1780.py does not import this module; the check / render scripts add them to the scene in memory).

Unity mesh (serializedVersion 11, uncompressed): m_VertexData channels (stream 0, float32), _typelessdata hex, m_IndexBuffer hex
(m_IndexFormat 0 = uint16, 1 = uint32), m_SubMeshes firstByte / indexCount. Unity is left-handed (x right, y up, z forward); the
MSB Blender frame is x right, y forward, z up: blender = (x, z, y), and the triangle winding flips.

    import stock_mesh as SM
    o = SM.load('EW1_cockpit_int', name='stock_ew1_cockpit', matrix=<Blender Matrix placing the mesh>)
"""
import os, re, struct
try:
    import bpy
    from mathutils import Matrix, Vector
except ImportError:          # plain python (read() only)
    bpy = None

DNS = r'C:\Users\User\nuclearoption-ref\BlueprinterProject\Blueprinter-Editor\Assets\Blueprinter\_donotship\Mesh'


def read(name):
    p = os.path.join(DNS, name + '_PLACEHOLDER.asset')
    txt = open(p, encoding='utf-8', errors='ignore').read()
    vc = int(re.search(r'm_VertexCount: (\d+)', txt).group(1))
    chans = re.findall(r'- stream: (\d+)\s+offset: (\d+)\s+format: (\d+)\s+dimension: (\d+)', txt)
    chans = [tuple(map(int, c)) for c in chans]
    data = bytes.fromhex(re.search(r'_typelessdata: ([0-9a-f]+)', txt).group(1))
    size = {0: 4, 1: 2, 2: 1, 3: 1, 4: 2, 5: 2}
    stride = 0
    for s, off, fmt, dim in chans:
        if s == 0 and dim:
            stride = max(stride, off + dim * size.get(fmt, 4))
    pos = chans[0]
    assert pos[2] == 0 and pos[3] == 3, 'position channel must be float3'
    verts = [struct.unpack_from('<3f', data, i * stride + pos[1]) for i in range(vc)]
    ib = bytes.fromhex(re.search(r'm_IndexBuffer: ([0-9a-f]*)', txt).group(1))
    fmt32 = int(re.search(r'm_IndexFormat: (\d)', txt).group(1)) == 1
    subs = re.findall(r'firstByte: (\d+)\s+indexCount: (\d+)\s+topology: (\d+)\s+baseVertex: (\d+)', txt)
    tris = []
    for sub_i, (fb, ic, top, bv) in enumerate(subs):
        fb, ic, bv = int(fb), int(ic), int(bv)
        n = 4 if fmt32 else 2
        idx = struct.unpack_from(('<%dI' if fmt32 else '<%dH') % ic, ib, fb)
        for k in range(0, ic - 2, 3):
            tris.append((idx[k] + bv, idx[k + 1] + bv, idx[k + 2] + bv, sub_i))
    return verts, tris


def load(name, obj_name=None, matrix=None, mats=None):
    """add the stock mesh as an object; matrix = Blender-frame placement of the mesh's Unity origin. mats: per-submesh material names."""
    verts, tris = read(name)
    bv = [Vector((x, z, y)) for x, y, z in verts]                       # Unity (x, y, z) -> Blender (x, z, y)
    faces = [(a, c, b) for a, b, c, s in tris]                            # handedness flip
    me = bpy.data.meshes.new('stock_' + name)
    me.from_pydata(bv, [], faces)
    nsub = max((s for *_, s in tris), default=0) + 1
    for s in range(nsub):
        mn = (mats[s] if mats and s < len(mats) else f'stock_{name}_{s}')
        m = bpy.data.materials.get(mn) or bpy.data.materials.new(mn)
        me.materials.append(m)
    for poly, (*_, s) in zip(me.polygons, tris):
        poly.material_index = s
    me.update()
    o = bpy.data.objects.new(obj_name or 'stock_' + name, me)
    bpy.context.scene.collection.objects.link(o)
    if matrix is not None:
        o.matrix_world = matrix
    return o
