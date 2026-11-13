"""B-17G stray-geometry check (round 3, after the user's first in-game try: "rogue polygons"). Runs on the .blend (source) or on the
exported FBX (what Unity imports) and writes a json report.

  blender --background assets/model_b17g/b17g.blend --python blender/b17g/check_b17g_stray.py -- --out <json>
  blender --background --factory-startup --python blender/b17g/check_b17g_stray.py -- --fbx assets/model_b17g/b17g.fbx --table assets/model_b17g/b17g_parts.json --out <json>

Per mesh object (world space):
- spikes: a triangle whose longest edge is > 5 x the largest local median edge length at its three corners and > 0.25 m AND whose
  long-edge midpoint has no other surface (sharing no corner) within max(5 cm, 25 % of the edge): it bridges empty space;
- degenerate: triangles with area < 1e-9 m^2 whose longest edge is > 5 mm (collapsed slivers that render as lines);
- far vertices: outside the 1st-99th percentile box grown by 35 % + 0.10 m (meshes with >= 300 vertices);
- far islands: a connected piece (welded by position) with < 5 % of the mesh whose nearest other vertex of the SAME mesh is > 0.25 m away;
- FBX only: per-object triangle count against the export table (an import split / loss shows here).
Exit code 0 always; the caller reads `ok` per test.
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector as V
from mathutils.kdtree import KDTree

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
arg = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
OUT, FBX, TABLE = arg('--out'), arg('--fbx'), arg('--table')
if FBX:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.fbx(filepath=os.path.abspath(FBX))
bpy.context.view_layer.update()

res = dict(source=FBX or bpy.data.filepath, spikes=[], degenerate=[], far_vertices=[], far_islands=[], tri_mismatch=[], meshes=0, tris=0)


def mesh_arrays(o):
    me = o.data
    me.calc_loop_triangles()
    M = np.array(o.matrix_world)
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    co = co @ M[:3, :3].T + M[:3, 3]
    tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64); me.loop_triangles.foreach_get('vertices', tri); tri = tri.reshape(-1, 3)
    return co, tri


for o in [x for x in bpy.data.objects if x.type == 'MESH']:
    co, tri = mesh_arrays(o)
    if len(tri) == 0:
        continue
    res['meshes'] += 1; res['tris'] += len(tri)
    # weld by position (FBX splits vertices on seams)
    key = np.round(co / 1e-5).astype(np.int64)
    _, wid = np.unique(key, axis=0, return_inverse=True)
    wid = wid.reshape(-1)
    W = np.zeros((wid.max() + 1, 3)); W[wid] = co
    T = wid[tri]
    a, b, c = W[T[:, 0]], W[T[:, 1]], W[T[:, 2]]
    e = np.stack([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)], 1)
    emax = e.max(1)
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    # local median of incident edge lengths per welded vertex
    E = np.concatenate([np.sort(T[:, [0, 1]], 1), np.sort(T[:, [1, 2]], 1), np.sort(T[:, [2, 0]], 1)])
    E = np.unique(E, axis=0)
    L = np.linalg.norm(W[E[:, 0]] - W[E[:, 1]], axis=1)
    inc = [[] for _ in range(len(W))]
    for (i, j), l in zip(E, L):
        inc[i].append(l); inc[j].append(l)
    med = np.array([np.median(x) if x else 0.0 for x in inc])
    scale = np.maximum(np.maximum(med[T[:, 0]], med[T[:, 1]]), med[T[:, 2]])
    cand = np.where((emax > 5 * scale) & (emax > 0.25))[0]
    sp = []
    if len(cand):
        # a long thin strip triangle (loft / cylinder side) has more surface right next to its long edge; a rogue polygon bridges
        # empty space: the midpoint of its long edge is > max(5 cm, 25 % of the edge) from every triangle that shares no corner
        from mathutils.bvhtree import BVHTree
        bvh = BVHTree.FromPolygons([V(p) for p in W], [tuple(int(x) for x in t) for t in T])
        for k in cand:
            i = int(np.argmax(e[k])); va, vb = T[k][i], T[k][(i + 1) % 3]
            mid = V((W[va] + W[vb]) / 2)
            rad = max(0.05, 0.25 * float(emax[k]))
            corners = set(int(x) for x in T[k])
            near = [h for h in bvh.find_nearest_range(mid, rad) if not (set(int(x) for x in T[h[2]]) & corners)]
            if near:
                continue
            # a big triangle of a FLAT region (decimated plate) is coplanar with its edge neighbours: not a bridge
            nk = np.cross(b[k] - a[k], c[k] - a[k]); nk = nk / (np.linalg.norm(nk) + 1e-12)
            flat = True
            for h in bvh.find_nearest_range(mid, rad):
                if h[2] != k and (set(int(x) for x in T[h[2]]) & corners):
                    nh = V(h[1])
                    if math.degrees(V(nk).angle(nh, 0.0)) > 5.0 and math.degrees(V(nk).angle(-nh, 0.0)) > 5.0:
                        flat = False
            if not flat:
                sp.append(k)
    sp = np.array(sp, dtype=np.int64)
    for k in sp[:5]:
        res['spikes'].append(dict(obj=o.name, centre=[round(float(v), 3) for v in (a[k] + b[k] + c[k]) / 3], edge=round(float(emax[k]), 3), local=round(float(scale[k]), 3)))
    if len(sp) > 5:
        res['spikes'].append(dict(obj=o.name, more=int(len(sp) - 5)))
    dg = np.where((area < 1e-9) & (emax > 0.005))[0]
    if len(dg):
        res['degenerate'].append(dict(obj=o.name, n=int(len(dg)), at=[round(float(v), 3) for v in (a[dg[0]] + b[dg[0]] + c[dg[0]]) / 3], edge=round(float(emax[dg[0]]), 3)))
    used = np.unique(T)
    P = W[used]
    if len(P) >= 300:
        lo, hi = np.percentile(P, 1, 0), np.percentile(P, 99, 0)
        g = (hi - lo) * 0.35 + 0.10
        out = np.where(((P < lo - g) | (P > hi + g)).any(1))[0]
        if len(out):
            res['far_vertices'].append(dict(obj=o.name, n=int(len(out)), first=[round(float(v), 3) for v in P[out[0]]], box=[[round(float(v), 2) for v in lo], [round(float(v), 2) for v in hi]]))
    # islands (union-find on welded vertices)
    par = np.arange(len(W))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for i, j in E:
        ri, rj = find(i), find(j)
        if ri != rj:
            par[ri] = rj
    roots = np.array([find(i) for i in used])
    ids, cnt = np.unique(roots, return_counts=True)
    if len(ids) > 1:
        kd = KDTree(len(used))
        for n_, p in enumerate(P):
            kd.insert(V(p), n_)
        kd.balance()
        for rid, n in zip(ids, cnt):
            if n >= 0.05 * len(used):
                continue
            mine = np.where(roots == rid)[0]
            best = 1e9
            for q in mine[:: max(1, len(mine) // 12)]:
                for (pp, idx, d) in kd.find_n(V(P[q]), min(len(used), n + 8)):
                    if roots[idx] != rid:
                        best = min(best, d); break
            if best > 0.25:
                res['far_islands'].append(dict(obj=o.name, verts=int(n), gap=round(best, 3), at=[round(float(v), 3) for v in P[mine].mean(0)]))

if FBX and TABLE:
    tab = {r['name']: r.get('tris', 0) for r in json.load(open(TABLE))}
    for o in [x for x in bpy.data.objects if x.type == 'MESH']:
        o.data.calc_loop_triangles()
        nm = o.name.split('.')[0]
        if nm in tab and tab[nm] != len(o.data.loop_triangles):
            res['tri_mismatch'].append(dict(obj=nm, blend=tab[nm], fbx=len(o.data.loop_triangles)))
    missing = sorted(set(k for k, v in tab.items() if v) - set(o.name.split('.')[0] for o in bpy.data.objects if o.type == 'MESH'))
    res['missing_in_fbx'] = missing
for k in ('spikes', 'degenerate', 'far_vertices', 'far_islands', 'tri_mismatch'):
    res[k + '_ok'] = not res[k]
print(f"[stray] {res['meshes']} meshes, {res['tris']} tris: spikes {len(res['spikes'])}, degenerate {len(res['degenerate'])}, far vertices {len(res['far_vertices'])}, "
      f"far islands {len(res['far_islands'])}, tri mismatch {len(res['tri_mismatch'])}, missing {len(res.get('missing_in_fbx', []))}")
if OUT:
    json.dump(res, open(OUT, 'w'), indent=1)
