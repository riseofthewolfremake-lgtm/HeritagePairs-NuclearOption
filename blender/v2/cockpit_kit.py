"""Cockpit kit (B-25H cockpit rebuild, 2026-11-01): fal-generated 3D props (GLB) placed into MeshBufs, plus panel-art helpers.

Props come from the Universal Modder pipeline (concept google/nano-banana-2.1 -> tripo3d/h3.1 image-to-3D -> tripo3d/tripo/remesh,
assets/model_v2/src/props_gen/<name>_remesh.glb, every call in assets/fal_manifest.jsonl). Each prop keeps its own baked texture:
material 'pr_<name>' (Unity: b25h_pr_<name>_b / _n, extracted from the GLB by textures/make_cockpit_art_b25h.py).
Axes after reading: glTF Y-up -> Blender Z-up ((x, y, z) -> (x, -z, y)); UV v -> 1 - v.
"""
import os, json, struct, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
PROPS = os.path.join(HERE, '..', '..', 'assets', 'model_v2', 'src', 'props_gen')
V = Vector


def glb_path(name):
    """<name>_remesh.glb (fal tripo remesh); v3 fallback <name>_dec.glb (fal tripo raw model decimated locally by
    blender/v2/props/decimate_raw_prop.py, used where the fal remesh call could not run: account balance exhausted)."""
    o = os.path.abspath(os.path.join(PROPS, 'opt', f'{name}.glb'))      # performance pass: welded + decimated to budget
    if os.path.exists(o) and os.environ.get('B25H_PROPS_FULL') != '1':
        return o
    p = os.path.abspath(os.path.join(PROPS, f'{name}_remesh.glb'))
    return p if os.path.exists(p) else os.path.abspath(os.path.join(PROPS, f'{name}_dec.glb'))


def read_glb(path):
    d = open(path, 'rb').read()
    L = struct.unpack('<III', d[:12])[2]
    off, chunks = 12, []
    while off < L:
        cl, ct = struct.unpack('<II', d[off:off + 8]); chunks.append(d[off + 8:off + 8 + cl]); off += 8 + cl
    js, bn = json.loads(chunks[0]), chunks[1]
    assert all(k in ('mesh', 'name') for n in js['nodes'] for k in n), 'node transforms not supported'

    def acc(i):
        a = js['accessors'][i]; bv = js['bufferViews'][a['bufferView']]
        o = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        nc = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}[a['type']]
        fmt = {5126: 'f', 5123: 'H', 5125: 'I'}[a['componentType']]
        sz = struct.calcsize(fmt)
        stride = bv.get('byteStride', sz * nc)
        return [struct.unpack_from('<' + fmt * nc, bn, o + k * stride) for k in range(a['count'])]
    pts, tris = [], []
    for mesh in js['meshes']:
        for pr in mesh['primitives']:
            P_ = [V((x, -z, y)) for x, y, z in acc(pr['attributes']['POSITION'])]
            T_ = [(u, 1.0 - v) for u, v in acc(pr['attributes']['TEXCOORD_0'])]
            I_ = [i[0] for i in acc(pr['indices'])]
            pts += P_
            for k in range(0, len(I_), 3):
                a, b, c = I_[k], I_[k + 1], I_[k + 2]
                tris.append(([P_[a], P_[b], P_[c]], [T_[a], T_[b], T_[c]]))
    return pts, tris


def bbox(pts):
    return V([min(p[i] for p in pts) for i in range(3)]), V([max(p[i] for p in pts) for i in range(3)])


def basis(x_to, y_to, z_to):
    """3x3 matrix whose columns are the world directions of the model's +X, +Y, +Z (must be right-handed)."""
    M = Matrix((V(x_to).normalized(), V(y_to).normalized(), V(z_to).normalized())).transposed()
    assert M.determinant() > 0.99, f'left-handed prop basis (det {M.determinant():.3f})'
    return M


def place(mb, name, R, scale, anchor_model, anchor_world, mat=None, clip=None, dedupe=True):
    """add prop `name` to MeshBuf mb: world = anchor_world + R @ ((p - anchor_model) * scale).
    clip = (model axis 0/1/2, min value): triangles are clipped to model[axis] >= value (hidden ends removed).
    dedupe: drop the smaller face of every same-facing coplanar overlap < 1 mm (doubled shells of generated meshes).
    Returns dict(n_faces, scale, world_bbox)."""
    pts, tris = read_glb(glb_path(name))
    am = V(anchor_model)
    out = []
    for vs, uvs in tris:
        if clip is not None:
            ax, mn = clip
            if max(v[ax] for v in vs) <= mn:
                continue
            if min(v[ax] for v in vs) < mn:
                ov, ou = [], []
                for k in range(3):
                    p0, p1, u0, u1 = vs[k], vs[(k + 1) % 3], uvs[k], uvs[(k + 1) % 3]
                    if p0[ax] >= mn:
                        ov.append(p0); ou.append(u0)
                    if (p0[ax] - mn) * (p1[ax] - mn) < 0:
                        f = (mn - p0[ax]) / (p1[ax] - p0[ax])
                        ov.append(p0.lerp(p1, f)); ou.append((u0[0] + (u1[0] - u0[0]) * f, u0[1] + (u1[1] - u0[1]) * f))
                cv, cu = [], []
                for a, b in zip(ov, ou):
                    if not cv or (a - cv[-1]).length > 1e-7:
                        cv.append(a); cu.append(b)
                if len(cv) > 1 and (cv[0] - cv[-1]).length <= 1e-7:
                    cv.pop(); cu.pop()
                for k in range(1, len(cv) - 1):
                    out.append(([cv[0], cv[k], cv[k + 1]], [cu[0], cu[k], cu[k + 1]]))
                continue
        out.append((vs, uvs))
    W = lambda p: V(anchor_world) + R @ ((p - am) * scale)
    out = [([W(v) for v in vs], uvs) for vs, uvs in out]
    drop = set()
    if dedupe and out:
        vv, ff = [], []
        for ws, _ in out:
            ff.append(tuple(range(len(vv), len(vv) + 3))); vv += ws
        bvh = BVHTree.FromPolygons(vv, ff)
        na = []
        for ws, _ in out:
            n = (ws[1] - ws[0]).cross(ws[2] - ws[0])
            na.append((n.normalized() if n.length > 0 else n, n.length / 2))
        for i, (ws, _) in enumerate(out):
            if i in drop:
                continue
            c = (ws[0] + ws[1] + ws[2]) / 3
            sps = [c] + [w.lerp(c, 0.5) for w in ws]
            for a_ in (0.125, 0.375, 0.625, 0.875):
                for b_ in (0.125, 0.375, 0.625, 0.875):
                    if a_ + b_ < 1:
                        sps.append(ws[0] + (ws[1] - ws[0]) * a_ + (ws[2] - ws[0]) * b_)
            for sp in sps:
                for (co, _n, j, dd) in bvh.find_nearest_range(sp, 0.001):
                    if j is None or j == i or j in drop or i in drop:
                        continue
                    off = sp - co
                    if na[i][0].dot(na[j][0]) > 0.999 and (off - na[j][0] * off.dot(na[j][0])).length < 0.0002:
                        drop.add(i if na[i][1] <= na[j][1] else j)
    # performance pass: drop small detached pieces (< 15 % of the faces, > 3 mm from the rest of the prop in world space):
    # decimation crumbs that would float in the game
    keep = [i for i in range(len(out)) if i not in drop]
    key = lambda w: (round(w.x, 6), round(w.y, 6), round(w.z, 6))
    par = {}
    def find(a):
        while par.setdefault(a, a) != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for i in keep:
        ks = [key(w) for w in out[i][0]]
        for k_ in ks[1:]:
            ra, rb = find(ks[0]), find(k_)
            if ra != rb:
                par[ra] = rb
    groups = {}
    for i in keep:
        groups.setdefault(find(key(out[i][0][0])), []).append(i)
    if len(groups) > 1:
        for g, fs in groups.items():
            if len(fs) >= 0.15 * len(keep):
                continue
            others = [i for i in keep if i not in set(fs) and i not in drop]
            vv, ff = [], []
            for i in others:
                ff.append(tuple(range(len(vv), len(vv) + 3))); vv += out[i][0]
            if not ff:
                continue
            bt = BVHTree.FromPolygons(vv, ff)
            if min(bt.find_nearest(w)[3] for i in fs for w in out[i][0]) > 0.003:
                drop.update(fs)
    m = mat or f'pr_{name}'
    allw = []
    weld = {}                                                  # performance pass: shared vertices (pass 1 split every face)
    for i, (ws, uvs) in enumerate(out):
        if i in drop:
            continue
        idx = []
        for w in ws:
            k = (round(w.x, 6), round(w.y, 6), round(w.z, 6))
            if k not in weld:
                weld[k] = mb.v(w)
            idx.append(weld[k])
        mb.face(idx, m, list(uvs), True)
        allw += ws
    lo, hi = bbox(allw) if allw else (V(), V())
    print(f'[kit] prop {name}: {len(out) - len(drop)} faces (dropped {len(drop)} doubled), scale {scale:.4f}, '
          f'world bbox {tuple(round(v, 3) for v in lo)} .. {tuple(round(v, 3) for v in hi)}')
    return dict(n=len(out) - len(drop), lo=lo, hi=hi)


def model_bbox(name):
    pts, _ = read_glb(glb_path(name))
    return bbox(pts)
