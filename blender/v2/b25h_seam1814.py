"""Heritage Pairs 1.8.14 (offline M): B-25H torn fuselage seams without a light line.

In game 1.8.13 a thin stepped light line crossed the roof between the dorsal trim ring and the cockpit glazing
(study/ingame_1813_anm2 t7_dors_e10_a45_top_crop, t7_ring_above). It is the jagged torn split at y 2.62 between fus_forward
and fus_cockpit (FUS_TORN, b25h_v3.tear_fuselage), the same at y 1.30 beside the ring. The two skins share every seam
vertex (boundary-edge scan: no open edge in 1.8.12 or 1.8.13, seam geometry identical in both), but they are separate
meshes, and each one closes its torn end with a light 'structure' wall that runs from the outer skin surface down to the
inner skin. Anything that opens the shared edge by a fraction of a pixel in game shows that wall (or the sky / interior)
as a light line.

Fix, B-25H only, shape unchanged (nothing moves on the outside):
  * lap strip: part a (the forward part of each torn split) gets a 'metal_dark' ribbon 1.5 mm under the outer skin that
    follows the jagged seam, 2 cm under its own skin and 2.5 cm under the neighbour's (clamped to 0.6 x the distance to
    the next station), only where both sides are skin. A crack between the meshes now shows dark metal, like a panel line.
  * torn-end walls start 4.5 mm (along the wall; >= 2.5 mm normal to the skin) under the outer skin (their outer edge moved toward the inner skin), so no light face
    touches the outer surface at the seam. A broken-off part shows its skin edge, the dark lip and the structure wall.

Call collect() BEFORE V3.tear_fuselage (it records the on-plane vertices), apply() right after it.
B-17G / FD-32 / GA-25X builders do not call this (they have their own collect step).
"""
import math
from b25h_geom import V, oriented_quad
import b25h_spec as S

LAP_DEPTH = 0.0015       # m under the outer skin
LAP_OWN = 0.020          # m under the own skin (part a)
LAP_NEIGH = 0.025        # m under the neighbour's skin (part b)
WALL_DROP = 0.0045       # m along the wall (slanted walls: >= 2.5 mm normal to the skin): torn-end wall top under the outer skin
PLANE_EPS = 2e-5         # same as b25h_v3.tear_mesh


def _on_plane(mb, y):
    return {i for i, v in enumerate(mb.verts) if abs(v.y - y) < PLANE_EPS}


def collect(byname):
    rec = []
    for y, (a, b) in S.FUS_TORN.items():
        side = {}
        for nm in (a, b):
            mb = byname[nm].mesh
            on = _on_plane(mb, y)
            paint = [k for k, f in enumerate(mb.faces) if f['mat'] == 'paint' and sum(1 for i in f['idx'] if i in on) >= 2]
            walls = [k for k, f in enumerate(mb.faces) if f['mat'] == 'structure' and len(f['idx']) >= 3 and all(i in on for i in f['idx'])]
            side[nm] = dict(on=on, paint=paint, walls=walls)
        rec.append(dict(y=y, a=a, b=b, side=side))
    return rec


def _newell(pts):
    n = V((0, 0, 0))
    for p, q in zip(pts, pts[1:] + pts[:1]):
        n += V(((p.y - q.y) * (p.z + q.z), (p.z - q.z) * (p.x + q.x), (p.x - q.x) * (p.y + q.y)))
    return n.normalized() if n.length > 1e-12 else n


def _key(p):
    return (round(p.x, 5), round(p.y, 5), round(p.z, 5))


def apply(byname, rec):
    rep = {}
    for r in rec:
        y, a, b = r['y'], r['a'], r['b']
        ma, mbb = byname[a].mesh, byname[b].mesh
        # 1 torn-end walls: outer-edge corners WALL_DROP toward the inner skin (both parts)
        nwall = 0
        for nm, mb in ((a, ma), (b, mbb)):
            sd = r['side'][nm]
            outer_pos = {_key(mb.verts[i]) for k in sd['paint'] for i in mb.faces[k]['idx'] if i in sd['on']}
            for k in sd['walls']:
                f = mb.faces[k]
                idx = f['idx']
                outer = [i for i in idx if _key(mb.verts[i]) in outer_pos]
                inner = [i for i in idx if i not in outer]
                if len(outer) != 2 or len(inner) != 2:
                    continue
                for i in outer:
                    q = min(inner, key=lambda j: (mb.verts[j] - mb.verts[i]).length)
                    d = mb.verts[q] - mb.verts[i]
                    if d.length > 1e-6:
                        mb.verts[i] = mb.verts[i] + d.normalized() * min(WALL_DROP, 0.5 * d.length)
                nwall += 1
        # 2 lap strip in part a
        def seam_info(mb, sd):
            """seam vertex key -> (pos, meridian neighbour on this side, outward normal), seam edges (key pairs)."""
            norm, mer, edges = {}, {}, set()
            for k in sd['paint']:
                f = mb.faces[k]
                pts = [mb.verts[i] for i in f['idx']]
                n = _newell(pts)
                m = len(f['idx'])
                for t in range(m):
                    i, j = f['idx'][t], f['idx'][(t + 1) % m]
                    for u, w in ((i, j), (j, i)):
                        if u in sd['on']:
                            ku = _key(mb.verts[u])
                            norm.setdefault(ku, V((0, 0, 0)))
                            if w not in sd['on']:
                                d = mb.verts[w] - mb.verts[u]
                                if ku not in mer or abs(d.y) > abs(mer[ku].y):
                                    mer[ku] = d
                    if i in sd['on'] and j in sd['on']:
                        edges.add(tuple(sorted((_key(mb.verts[i]), _key(mb.verts[j])))))
                for i in f['idx']:
                    if i in sd['on']:
                        norm[_key(mb.verts[i])] += n
            pos = {}
            for k in sd['paint']:
                for i in mb.faces[k]['idx']:
                    if i in sd['on']:
                        pos[_key(mb.verts[i])] = V(mb.verts[i])
            return pos, mer, {k: (v.normalized() if v.length > 1e-12 else v) for k, v in norm.items()}, edges
        pa, mera, na, ea = seam_info(ma, r['side'][a])
        pb, merb, nb, eb = seam_info(mbb, r['side'][b])
        common = ea & eb                         # seam edges with skin on both sides
        use = {}
        for e in common:
            for k in e:
                use[k] = use.get(k, 0) + 1
        quads = 0
        for k0, k1 in sorted(common):
            pts = {}
            ok = True
            for k, ko in ((k0, k1), (k1, k0)):
                if k not in mera or k not in merb or k not in pa:
                    ok = False
                    break
                p = pa[k]
                if use[k] == 1:                  # run end at a hole edge (well, canopy): stop 15 % short, under the skin
                    p = p + (pa[ko] - p) * 0.15
                n = (na[k] + nb.get(k, V((0, 0, 0)))).normalized()
                da, db = mera[k], merb[k]
                wa = min(LAP_OWN, 0.6 * da.length)
                wb = min(LAP_NEIGH, 0.6 * db.length)
                # each ribbon line sits LAP_DEPTH under the skin face it lies under (that side's normal)
                pts[k] = (p + da.normalized() * wa - na[k] * LAP_DEPTH,
                          p - n * LAP_DEPTH,
                          p + db.normalized() * wb - nb.get(k, n) * LAP_DEPTH, n)
            if not ok:
                continue
            (a0, m0, b0, n0), (a1, m1, b1, n1) = pts[k0], pts[k1]
            out = (n0 + n1).normalized()
            oriented_quad(ma, [a0, a1, m1, m0], 'metal_dark', out, smooth=True)
            oriented_quad(ma, [m0, m1, b1, b0], 'metal_dark', out, smooth=True)
            quads += 2
        rep[f'y={y}'] = dict(walls_lowered=nwall, seam_edges_a=len(ea), seam_edges_b=len(eb), lap_edges=len(common), lap_quads=quads)
    return rep
