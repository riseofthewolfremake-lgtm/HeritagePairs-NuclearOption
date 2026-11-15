"""1.9.12 evidence: per-object fingerprint of an MSB-17 .blend, to prove what a build changed and what it left alone.

  blender -b <file.blend> --factory-startup -P blender/msb1780/fingerprint1912.py -- --out <json>
  python blender/msb1780/fingerprint1912.py --compare <a.json> <b.json>        (pure python: lists added / removed / changed objects)

Per mesh object: world-space vertex positions (0.1 mm, sorted), triangle count, the livery UV points of its paint faces (the atlas-guard
quantisation), the corner normals (1e-3), material slots, parent, world matrix. Per empty: parent + world matrix.
"""
import sys, json, hashlib


def _h(x):
    return hashlib.sha256(repr(x).encode()).hexdigest()[:16]


def fingerprint(out):
    import bpy
    res = {}
    for o in bpy.data.objects:
        mw = [round(c, 5) for row in o.matrix_world for c in row]
        d = dict(kind=o.type.lower(), parent=o.parent.name if o.parent else None, matrix=_h(mw))
        if o.type == 'MESH':
            me = o.data
            me.calc_loop_triangles()
            vs = sorted((round(v[0], 4), round(v[1], 4), round(v[2], 4)) for v in ((o.matrix_world @ x.co) for x in me.vertices))
            mats = [m.name if m else '' for m in me.materials]
            uv = []
            if 'livery' in me.uv_layers and 'paint' in mats:
                data = me.uv_layers['livery'].data; pi = mats.index('paint')
                uv = sorted({(int(data[li].uv[0] * 65536), int(data[li].uv[1] * 65536)) for p in me.polygons if p.material_index == pi for li in p.loop_indices})
            R3 = o.matrix_world.to_3x3()
            nr = sorted((round(n[0], 3), round(n[1], 3), round(n[2], 3)) for n in ((R3 @ l.vector) for l in me.corner_normals))
            d.update(tris=len(me.loop_triangles), verts=len(me.vertices), geo=_h(vs), uv=_h(uv), uv_points=len(uv), normals=_h(nr), materials=mats)
        res[o.name] = d
    json.dump(res, open(out, 'w'), indent=0, sort_keys=True)
    print('[fingerprint1912]', len(res), 'objects ->', out)


def compare(a, b):
    A, B = json.load(open(a)), json.load(open(b))
    added = sorted(set(B) - set(A)); removed = sorted(set(A) - set(B))
    changed = {n: sorted(k for k in set(A[n]) | set(B[n]) if A[n].get(k) != B[n].get(k)) for n in sorted(set(A) & set(B)) if A[n] != B[n]}
    return dict(a=len(A), b=len(B), added=added, removed=removed, changed=changed)


if __name__ == '__main__':
    if '--compare' in sys.argv:
        i = sys.argv.index('--compare')
        r = compare(sys.argv[i + 1], sys.argv[i + 2])
        print(json.dumps(r, indent=1))
        sys.exit(0)
    argv = sys.argv[sys.argv.index('--') + 1:]
    fingerprint(argv[argv.index('--out') + 1])
