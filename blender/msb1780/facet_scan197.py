"""1.9.7 faceting scan of the MSB-17/80 model: which surfaces meant to be curved shade as visible polygons.

  blender --background assets/model_msb1780/msb1780.blend --python-exit-code 1 --python blender/msb1780/facet_scan197.py -- [--out facet.json] [--limit 0.5]

A 'facet edge' is measured on what the game shades with, the exported corner normals: two faces of the same outside material that meet
along an edge (matched by POSITION, so faces built with their own vertices count) with a dihedral angle between LO and HI degrees (a bend
that belongs to a curved surface; from 38 deg the builder marks a designed crease) and whose corner normals at a shared end point differ
by more than TOL degrees - the light breaks along that edge although the surface is meant to be continuous. Smooth-shaded, welded or
analytic-normal surfaces score 0. Per object: facet edges, their total length (m), the worst dihedral.
Used by check_msb1780_model.py (row u: every object, outside materials) and tools/stub_tests_197.py.
"""
import bpy, sys, json, math

LO, HI, TOL = 4.0, 38.0, 4.0
OUTSIDE = ('paint', 'metal_dark', 'glass', 'gear', 'tyre', 'chrome', 'engine', 'exhaust', 'cove')


def _key(co):
    return (round(co[0], 4), round(co[1], 4), round(co[2], 4))


def scan_mesh(me, lo=LO, hi=HI, tol=TOL, mats_ok=OUTSIDE):
    mats = [m.name if m else '' for m in me.materials]
    cn = me.corner_normals
    edges = {}
    for p in me.polygons:
        mn = mats[p.material_index] if mats else ''
        if not (mn in mats_ok or mn.startswith('pr_')):
            continue
        li = list(p.loop_indices)
        ks = [_key(me.vertices[me.loops[l].vertex_index].co) for l in li]
        n = len(li)
        for i in range(n):
            a, b = ks[i], ks[(i + 1) % n]
            if a == b:
                continue
            ek = (a, b) if a < b else (b, a)
            na, nb = cn[li[i]].vector.copy(), cn[li[(i + 1) % n]].vector.copy()
            edges.setdefault(ek, []).append((p.index, mn, p.normal.copy(), (na, nb) if a < b else (nb, na)))
    cnt = 0; length = 0.0; worst = 0.0
    for (a, b), fl in edges.items():
        if len(fl) != 2:
            continue
        (i0, m0, n0, c0), (i1, m1, n1, c1) = fl
        if m0 != m1:
            continue
        try:
            d = math.degrees(n0.angle(n1))
        except ValueError:
            continue
        if d < lo or d >= hi:
            continue
        try:
            mis = max(math.degrees(c0[0].angle(c1[0])), math.degrees(c0[1].angle(c1[1])))
        except ValueError:
            continue
        if mis <= tol:
            continue
        cnt += 1; worst = max(worst, d)
        length += math.dist(a, b)
    return dict(facet_edges=cnt, facet_len=round(length, 3), worst=round(worst, 1), faces=len(me.polygons))


def scan(objs=None):
    res = {}
    for o in (objs if objs is not None else bpy.data.objects):
        if o.type == 'MESH' and len(o.data.polygons):
            res[o.name] = scan_mesh(o.data)
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    res = scan()
    lim = float(argv[argv.index('--limit') + 1]) if '--limit' in argv else 0.0
    tot = 0.0
    for k, v in sorted(res.items(), key=lambda kv: -kv[1]['facet_len']):
        tot += v['facet_len']
        if v['facet_len'] > lim:
            print(f"[facet] {k:28s} edges {v['facet_edges']:5d} len {v['facet_len']:8.2f} m worst {v['worst']:5.1f} faces {v['faces']}")
    print(f"[facet] TOTAL {tot:.1f} m over {sum(1 for v in res.values() if v['facet_edges'])} objects")
    if '--out' in argv:
        json.dump(res, open(argv[argv.index('--out') + 1], 'w'), indent=1)
