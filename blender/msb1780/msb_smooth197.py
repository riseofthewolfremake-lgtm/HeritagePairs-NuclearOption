"""1.9.7: curved MSB-17/80 surfaces shade smooth in game (user on 1.9.6: 'visible polygons ... most notably the defensive bays').

Cause (facet_scan197.py on the 1.9.6 model): faces that the builder makes with their OWN vertices (MeshBuf.poly / take_faces: the doors and
hatches taken out of the fuselage skin - bay_door_L/R 28.7 m of facet edges each, side_bay_door_L/R 11.0 m each, the hatches, rings, cut
pieces round the nose windows) share no vertex with their neighbours, so the exported corner normals are the flat face normals: every quad
of the curved fuselage side is lit on its own. The skin beside them (lofted, shared vertices) is smooth, which makes the doors stand out.

Fix, no topology change (vertex / face counts, UVs and the livery atlas are untouched): custom split normals. Every corner of an outside
material gets the area-weighted mean of the face normals of all faces of the SAME material that have a corner at the same world position
and are joined to this face through edges flatter than CREASE (smoothing groups by position) - across objects, so a closed door carries
the normals of the skin round it. CREASE is the builder's own crease rule (38 deg): designed corners stay sharp. Run before b17g_normals.apply (the analytic normals near the turret
openings and the nose windows win where they are set).
"""
import math
from mathutils import Vector as V

CREASE = 38.0
OUTSIDE = ('paint', 'metal_dark', 'glass', 'gear', 'tyre', 'chrome', 'engine', 'exhaust', 'cove')
SKIP_PREFIX = ('cockpit_', 'crew', 'seat')


def _key(w):
    return (round(w.x, 4), round(w.y, 4), round(w.z, 4))


def apply(objs, crease=CREASE, log=print):
    """smoothing groups by position (Blender's own sharp-edge rule, extended to faces that do not share vertices): round each corner
    position the faces of one material form a graph - two faces are joined when they share an EDGE there (a second common position) and
    their dihedral angle is below the crease; a corner gets the area-weighted mean normal of its connected component."""
    cosc = math.cos(math.radians(crease))
    groups = {}          # (material, position) -> [[world normal, weighted normal, prev key, next key]]
    work = []
    for o in objs:
        if o.type != 'MESH' or o.name.startswith(SKIP_PREFIX) or not len(o.data.polygons):
            continue
        me = o.data; M = o.matrix_world; R = M.to_3x3()
        mats = [m.name if m else '' for m in me.materials]
        rec = []
        for p in me.polygons:
            mn = mats[p.material_index] if mats else ''
            if not (mn in OUTSIDE or mn.startswith('pr_')) or not p.use_smooth:
                continue
            nw = (R @ p.normal).normalized()
            wn = nw * max(p.area, 1e-9)
            li = list(p.loop_indices); n = len(li)
            ks = [_key(M @ me.vertices[me.loops[l].vertex_index].co) for l in li]
            for i in range(n):
                g = groups.setdefault((mn, ks[i]), [])
                g.append((nw, wn, ks[i - 1], ks[(i + 1) % n]))
                rec.append((li[i], (mn, ks[i]), len(g) - 1))
        if rec:
            work.append((o, rec))
    solved = {}
    def solve(k):
        g = groups[k]; m = len(g); par = list(range(m))
        def find(a):
            while par[a] != a:
                par[a] = par[par[a]]; a = par[a]
            return a
        for i in range(m):
            for j in range(i + 1, m):
                if g[i][0].dot(g[j][0]) < cosc:
                    continue
                if g[i][2] in (g[j][2], g[j][3]) or g[i][3] in (g[j][2], g[j][3]):
                    par[find(i)] = find(j)
        sums = {}
        for i in range(m):
            r = find(i); sums[r] = sums.get(r, V((0.0, 0.0, 0.0))) + g[i][1]
        return [sums[find(i)] for i in range(m)]
    changed = {}
    for o, rec in work:
        me = o.data; Ri = o.matrix_world.to_3x3().inverted()
        cn = [V(l.vector) for l in me.corner_normals]
        n = 0
        for li, k, gi in rec:
            if len(groups[k]) < 2:
                continue
            if k not in solved:
                solved[k] = solve(k)
            s = solved[k][gi]
            if s.length < 1e-12:
                continue
            new = (Ri @ s).normalized()
            if new.dot(cn[li]) < 0.99999:
                cn[li] = new; n += 1
        if n:
            me.normals_split_custom_set(cn)
            changed[o.name] = n
    log(f'[smooth197] custom normals on {len(changed)} objects, {sum(changed.values())} corners (crease {crease} deg)')
    return changed
