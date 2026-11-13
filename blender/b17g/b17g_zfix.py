"""1.7.11: resolve every z-fighting pair the Blender check (m) finds, at build time, by moving one face of the pair off the shared plane.

Detection = check_b17g_model.zfight_pairs (same-facing, normals within 2 deg, planes within 0.8 mm, overlapping: >= 2 of 7 sample
points of the smaller triangle inside the larger), but with the Blender polygon behind each triangle so it can be edited.
Resolution per pair: the SMALLER polygon is split off its neighbours (its own corner vertices) and moved by MOVE along its normal:
forward (towards its own front side) if its material should be the visible one of the two (PRIO), else backward. Same priority
(true duplicates inside one mesh, e.g. the fal engine faces, two bezel rings) -> backward. A polygon of a mesh shared by several
objects is moved once. The log (part, material, location, area, action) goes to b17g_zfix.json next to the blend.
"""
import math, json
import bpy, bmesh
import numpy as np
from collections import defaultdict
from mathutils import Vector as V

MOVE = 0.003           # m: well clear of the 0.8 mm check and of depth-buffer precision at cockpit / turret distances
PRIO = {'paint': 6, 'glass': 4, 'structure': 3, 'interior': 2, 'ck_wall': 2, 'cove': 2, 'well': 2, 'rubber': 2}
DEFAULT_PRIO = 5       # small details (bezels, metal, chrome, cockpit parts, fal props) sit in front of walls / skins, behind paint


def prio(mat):
    return PRIO.get(mat, DEFAULT_PRIO)


def detect(objs, dist=0.0008, ang=2.0, min_area=2e-5):
    T, own, poly, mat = [], [], [], []
    for o in objs:
        me = o.data; me.calc_loop_triangles(); M = o.matrix_world
        vs = [M @ v.co for v in me.vertices]
        for t in me.loop_triangles:
            T.append([vs[k] for k in t.vertices]); own.append(o.name); poly.append(t.polygon_index)
            mat.append(me.materials[t.material_index].name if me.materials and me.materials[t.material_index] else '-')
    if not T:
        return []
    A = np.array([[tuple(p) for p in t] for t in T], dtype=np.float64)
    n = np.cross(A[:, 1] - A[:, 0], A[:, 2] - A[:, 0]); ar = np.linalg.norm(n, axis=1) / 2
    ok = ar > min_area
    n[ok] /= (2 * ar[ok])[:, None]
    d = (n * A[:, 0]).sum(1)
    qn, qd = 0.03, 0.004
    buckets = defaultdict(list)
    for i in np.nonzero(ok)[0]:
        buckets[(int(round(n[i, 0] / qn)), int(round(n[i, 1] / qn)), int(round(n[i, 2] / qn)), int(round(d[i] / qd)))].append(i)
    lo, hi = A.min(1), A.max(1)
    cosang = math.cos(math.radians(ang))
    W = [(1/3, 1/3, 1/3), (0.6, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.6), (0.45, 0.45, 0.1), (0.1, 0.45, 0.45), (0.45, 0.1, 0.45)]
    hits, seen = [], set()
    for key in list(buckets):
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for dd in (-1, 0, 1):
                        cand += buckets.get((key[0] + dx, key[1] + dy, key[2] + dz, key[3] + dd), [])
        for i in buckets[key]:
            for j in cand:
                if j <= i or (i, j) in seen:
                    continue
                if n[i] @ n[j] < cosang or abs(d[i] - d[j]) > dist:
                    continue
                if (lo[i] > hi[j] + 1e-4).any() or (lo[j] > hi[i] + 1e-4).any():
                    continue
                seen.add((i, j))
                a, b = (i, j) if ar[i] <= ar[j] else (j, i)
                e1 = A[b, 1] - A[b, 0]; e1 /= np.linalg.norm(e1); e2 = np.cross(n[b], e1)
                tb = [((A[b, k] - A[b, 0]) @ e1, (A[b, k] - A[b, 0]) @ e2) for k in range(3)]

                def inside(px, py):
                    s = [(tb[(k + 1) % 3][0] - tb[k][0]) * (py - tb[k][1]) - (tb[(k + 1) % 3][1] - tb[k][1]) * (px - tb[k][0]) for k in range(3)]
                    return all(v > 1e-7 for v in s) or all(v < -1e-7 for v in s)
                cnt = sum(1 for w in W if inside(((w[0] * A[a, 0] + w[1] * A[a, 1] + w[2] * A[a, 2]) - A[b, 0]) @ e1,
                                                 ((w[0] * A[a, 0] + w[1] * A[a, 1] + w[2] * A[a, 2]) - A[b, 0]) @ e2))
                if cnt >= 2:
                    hits.append(dict(a=(own[a], poly[a], mat[a]), b=(own[b], poly[b], mat[b]), at=[round(float(x), 3) for x in A[a].mean(0)],
                                     area=float(ar[a])))
    return hits


def poly_area(o, pi):
    M = o.matrix_world; p = o.data.polygons[pi]
    vs = [M @ o.data.vertices[k].co for k in p.vertices]
    return sum(((vs[k] - vs[0]).cross(vs[k + 1] - vs[0])).length for k in range(1, len(vs) - 1)) / 2


def resolve(objs, log_path=None, passes=4):
    log = []
    for ps in range(passes):
        hits = detect(objs)
        print(f'[zfix] pass {ps + 1}: {len(hits)} pairs')
        if not hits:
            break
        moves = {}                       # (mesh name, polygon) -> (object, signed distance in its local normal direction)
        for h in hits:
            oa, ob = bpy.data.objects[h['a'][0]], bpy.data.objects[h['b'][0]]
            Aa, Ab = poly_area(oa, h['a'][1]), poly_area(ob, h['b'][1])
            mv, other = (h['a'], h['b']) if Aa <= Ab else (h['b'], h['a'])
            o = bpy.data.objects[mv[0]]
            key = (o.data.name, mv[1])
            if key in moves:
                continue
            sgn = 1.0 if prio(mv[2]) > prio(other[2]) else -1.0
            moves[key] = (o, sgn)
            log.append(dict(pass_=ps + 1, part=mv[0], material=mv[2], other_part=other[0], other_material=other[2], at=h['at'],
                            area_m2=round(h['area'], 6), action=('forward' if sgn > 0 else 'back') + f' {MOVE * 1000:.0f} mm'))
        by_mesh = defaultdict(list)
        for (mname, pi), (o, sgn) in moves.items():
            by_mesh[mname].append((o, pi, sgn))
        for mname, lst in by_mesh.items():
            o = lst[0][0]; me = o.data
            bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
            # world MOVE -> local distance (objects may be scaled)
            sc = o.matrix_world.to_scale(); s_ = (abs(sc.x) + abs(sc.y) + abs(sc.z)) / 3 or 1.0
            faces = [(bm.faces[pi], sgn) for _, pi, sgn in lst]
            for f, sgn in faces:
                nrm = f.normal.copy()
                res = bmesh.ops.split(bm, geom=[f], use_only_faces=True)
                nf = [g for g in res['geom'] if isinstance(g, bmesh.types.BMFace)]
                nv = {v for g in nf for v in g.verts}
                for v in nv:
                    v.co += nrm * (sgn * MOVE / s_)
            bm.to_mesh(me); bm.free(); me.update()
    left = detect(objs)
    print(f'[zfix] {len(log)} faces moved; {len(left)} pairs left')
    if log_path:
        import os
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        json.dump(dict(moved=log, left=left), open(log_path, 'w'), indent=1)
    return log, left
