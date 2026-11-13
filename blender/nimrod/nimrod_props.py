"""fal 3D props for the Nimrod (2026-11-02 rebuild): placement into MeshBufs.

Pipeline (Universal Modder, every call logged in assets/model_nimrod/src/fal/*/fal_manifest.jsonl):
  concept image (fal-ai/nano-banana-2) -> tripo3d/h3.1/image-to-3d -> tripo3d/tripo/remesh -> blender/nimrod/props/process_props_nimrod.py
  (weld, hole fill, decimate to budget) -> assets/model_nimrod/src/fal/opt/<name>.glb.
Each prop keeps its own baked texture: material 'pr_<key>' (Unity: NIMROD1_pr_<key>, textures nimrod_pr_<key>_b / _n written by
textures/build_textures_nimrod.py from the same GLB). Faces carry the prop's own UVs (layer 'livery', as the B-25H props).

Model frame = the GLB read by cockpit_kit.read_glb (glTF Y-up -> Blender Z-up). A placement is a map model -> world:
  world = anchor_world + R @ (S(p) - anchor_model) where S is an optional per-axis piecewise-linear remap of the model coordinates
  (stretch the middle of the hook bar, keep the claw and the hinge fitting at their own scale).
"""
import os, sys, math
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'v2'))
import cockpit_kit as K

OPT = os.path.abspath(os.path.join(HERE, '..', '..', 'assets', 'model_nimrod', 'src', 'fal', 'opt'))
V = Vector
# prop file -> material key (pr_<key>) ; the two tail-wheel islands share one texture
MAT = {'vickers': 'pr_vickers', 'exhaust': 'pr_exhaust', 'tailhook_v2': 'pr_hook', 'wheel': 'pr_wheel', 'tailwheel_wheel': 'pr_tailwheel',
       'tailwheel_fork': 'pr_tailwheel', 'pedals': 'pr_pedals', 'pedals_lp': 'pr_pedals', 'cooper_single': 'pr_cooper'}
SRC_GLB = {'pr_vickers': 'vickers', 'pr_exhaust': 'exhaust', 'pr_hook': 'tailhook_v2', 'pr_wheel': 'wheel', 'pr_tailwheel': 'tailwheel_wheel',
           'pr_pedals': 'pedals_lp', 'pr_cooper': 'cooper_single'}
_cache = {}


def load(name):
    if name not in _cache:
        _cache[name] = K.read_glb(os.path.join(OPT, name + '.glb'))
    return _cache[name]


def bbox(name):
    return K.bbox(load(name)[0])


def piecewise(knots):
    """knots: [(model value, new value), ...] sorted by model value; linear between, linear extrapolation outside."""
    def f(x):
        if x <= knots[0][0]:
            (a, A), (b, B) = knots[0], knots[1]
        elif x >= knots[-1][0]:
            (a, A), (b, B) = knots[-2], knots[-1]
        else:
            for (a, A), (b, B) in zip(knots, knots[1:]):
                if a <= x <= b:
                    break
        return A + (B - A) * (x - a) / (b - a)
    return f


def place(mb, name, R, anchor_model, anchor_world, remap=None, clip=None, mat=None, cross=None, warp=None, keep=None):
    """add prop `name` to MeshBuf mb. R: 3x3 (may include scale and a mirror; a mirror flips the winding back).
    remap: {axis: f} per model axis applied first. cross: (axis, f(a) -> scale) scales the two other model axes about
    the anchor by a factor depending on the coordinate along `axis` (thin the receiver, keep the jacket).
    clip: list of (axis, min, max) in MODEL coordinates: triangles entirely outside are dropped (no splitting).
    Returns the world bbox (lo, hi) of what was added."""
    pts, tris = load(name)
    am = V(anchor_model)
    mirror = R.determinant() < 0
    for f in (remap or {}).values():          # a decreasing remap is a reflection too
        if f(1.0) < f(0.0):
            mirror = not mirror
    m = mat or MAT[name]
    lo = V((1e9, 1e9, 1e9)); hi = -lo
    out = []

    def S(p):
        if warp is not None:
            p = warp(V(p))
        q = V(p)
        if cross is not None:
            ax, fs = cross
            s = fs(p[ax])
            for i in range(3):
                if i != ax:
                    q[i] = am[i] + (p[i] - am[i]) * s
        if remap:
            for ax, f in remap.items():
                q[ax] = f(p[ax])
        return q
    for vs, uvs in tris:
        if clip is not None and any(all(not (mn <= v[ax] <= mx) for v in vs) for ax, mn, mx in clip):
            continue
        if keep is not None and not keep(vs):
            continue
        w = [V(anchor_world) + R @ (S(v) - am) for v in vs]
        u = list(uvs)
        if mirror:
            w = [w[0], w[2], w[1]]; u = [u[0], u[2], u[1]]
        n = (w[1] - w[0]).cross(w[2] - w[0])
        if n.length < 1e-12:
            continue
        out.append((w, u))
    # z-fight guard: generated shells contain doubled, same-facing coplanar sheets; drop the smaller triangle of every same-facing
    # overlap closer than 0.3 mm (the reversed twins face the other way and stay)
    from mathutils.bvhtree import BVHTree
    vv = [p for w, u in out for p in w]
    ff = [(3 * k, 3 * k + 1, 3 * k + 2) for k in range(len(out))]
    drop = set()
    if ff:
        tb = BVHTree.FromPolygons(vv, ff)
        na = []
        for w, u in out:
            n = (w[1] - w[0]).cross(w[2] - w[0])
            na.append((n.normalized(), n.length / 2))
        for i, (w, u) in enumerate(out):
            if i in drop:
                continue
            c = (w[0] + w[1] + w[2]) / 3
            for (co, no, j, d) in tb.find_nearest_range(c, 0.0012):
                if j is None or j == i or j in drop:
                    continue
                if na[i][0].dot(na[j][0]) > 0.999 and abs((c - co).dot(na[j][0])) < 0.0003:
                    drop.add(i if na[i][1] <= na[j][1] else j)
                    if i in drop:
                        break
    for k, (w, u) in enumerate(out):
        if k in drop:
            continue
        mb.face([mb.v(p) for p in w], m, [tuple(x) for x in u], smooth=True)
        for p in w:
            for i in range(3):
                lo[i] = min(lo[i], p[i]); hi[i] = max(hi[i], p[i])
    return lo, hi


def axes(x_to, y_to, z_to, sx=1.0, sy=1.0, sz=1.0):
    """3x3 whose columns are where the model +X/+Y/+Z go (unit directions) times per-axis scales."""
    M = Matrix((V(x_to).normalized() * sx, V(y_to).normalized() * sy, V(z_to).normalized() * sz)).transposed()
    return M
