"""1.8.16 livery-atlas guard: a texture set is only valid for the livery-atlas UV it was painted on.

Why (1.8.14 bug, user report 2026-11-09): every model rebuild re-runs the global atlas pack (build_b25h_v2.pack_livery ->
bpy.ops.uv.pack_islands, reused by the B-17G / GA-25X / FD-32 builders). A geometry change anywhere moves EVERY island, so the
old skin / livery / damage textures land on the wrong parts (camo blotches on plain olive drab, olive patches on natural metal).

The guard:
  * every texture build writes <prefix>_atlas_manifest.json next to its textures: a hash of the atlas UV per part;
  * the Blender model checks and the Unity CHECK ALL (unity/Editor/AtlasGuard1816.cs) recompute the hash from the model they check
    and FAIL when it differs from the manifest (= the textures must be re-baked: python <the aircraft's texture builder>).

Hash (identical here and in AtlasGuard1816.cs): per part (mesh object), the SET of distinct atlas UV points of its paint faces,
each coordinate quantised q = floor(u * 65536) (exact for float32 values in both float64 implementations), sorted, packed as
little-endian int32 pairs, sha1 -> first 16 hex. A set, so it does not depend on island / face / vertex order, triangulation or
vertex splitting (Blender loops vs Unity vertices). Atlas hash = sha1 of the sorted "name:hash" lines (first 16 hex).

Unity side: the FBX import drops degenerate triangles (GA-25X fus_nose: the 14 nose-pole UV corners of its collapsed quads are not in
the imported mesh), so an exact per-part hash of the IMPORTED mesh can differ with nothing wrong. The manifest therefore also carries
each part's texel cells (UV points on the 4096 grid, cell = floor(u*4096) << 16 | floor(v*4096), sorted uint32, raw deflate, base64):
the Unity row (and tools/atlas_pack_check1816.py) passes a part when >= 99 % of its imported texel cells are manifest cells of that part
and >= 95 % of the manifest cells are present. A re-pack moves the islands, so the overlap drops to a few % (measured in the stubs).

Pure-python core (no bpy) at the top so the stubs can import it; the bpy helpers import bpy lazily.
"""
import hashlib, json, math, os, struct, zlib, base64, array

Q = 65536.0
CELL = 4096
MANIFEST_VERSION = 2
COVER_MODEL, COVER_MANIFEST = 0.99, 0.95      # Unity-side coverage rule (see above)


def quant(u):
    return int(math.floor(float(u) * Q))


def part_hash(points):
    """points: iterable of (u, v) floats -> (hash16, n_distinct)"""
    s = sorted({(quant(u), quant(v)) for u, v in points})
    h = hashlib.sha1()
    for a, b in s:
        h.update(struct.pack('<ii', a, b))
    return h.hexdigest()[:16], len(s)


def part_cells(points):
    """-> sorted list of texel cells (uint32) of the points on the CELL grid"""
    return sorted({((int(math.floor(float(u) * CELL)) & 0xFFFF) << 16) | (int(math.floor(float(v) * CELL)) & 0xFFFF) for u, v in points})


def encode_cells(cells):
    a = array.array('I', cells)
    if a.itemsize != 4:
        raise RuntimeError('uint32 array expected')
    b = a.tobytes() if struct.pack('=I', 1) == struct.pack('<I', 1) else array.array('I', [struct.unpack('>I', struct.pack('<I', c))[0] for c in cells]).tobytes()
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(co.compress(b) + co.flush()).decode()


def decode_cells(s):
    b = zlib.decompress(base64.b64decode(s), -15)
    return set(struct.unpack('<%dI' % (len(b) // 4), b))


def coverage(model_cells, manifest_cells):
    """-> (share of model cells that are manifest cells, share of manifest cells present in the model)"""
    a, b = set(model_cells), set(manifest_cells)
    i = len(a & b)
    return (i / len(a) if a else 0.0), (i / len(b) if b else 0.0)


def atlas_hash(parts):
    """parts: {name: hash16 or {'hash': ...}}"""
    lines = sorted(f'{n}:{(v["hash"] if isinstance(v, dict) else v)}' for n, v in parts.items())
    return hashlib.sha1('\n'.join(lines).encode()).hexdigest()[:16]


def compare(model_parts, manifest, tex_dir=None):
    """model_parts {name: {'hash','n'}} vs a manifest dict -> (ok, detail dict). Fails on any moved / missing / extra part, on a
    texture painted on another atlas (partial re-bake) and, with tex_dir, on a texture file that is not the one the manifest names."""
    mp = manifest.get('parts', {})
    moved = sorted(n for n in model_parts if n in mp and model_parts[n]['hash'] != mp[n]['hash'])
    missing = sorted(n for n in mp if n not in model_parts)       # in the textures, gone from the model
    extra = sorted(n for n in model_parts if n not in mp)         # new paint part the textures never saw
    tex = manifest.get('textures', {})
    stale = sorted(t for t, v in tex.items() if v.get('atlas') != manifest.get('atlas_hash'))
    changed = []
    if tex_dir:
        changed = sorted(t for t, v in tex.items() if not os.path.exists(os.path.join(tex_dir, t)) or sha12(os.path.join(tex_dir, t)) != v.get('sha'))
    ok = not moved and not missing and not extra and not stale and not changed and len(model_parts) > 0 and len(tex) > 0         and atlas_hash(mp) == manifest.get('atlas_hash')
    return ok, dict(model_atlas=atlas_hash(model_parts), manifest_atlas=manifest.get('atlas_hash'), parts=len(model_parts),
                    manifest_parts=len(mp), moved=len(moved), missing=len(missing), extra=len(extra), textures=len(tex),
                    stale=stale[:6], changed=changed[:6],
                    moved_examples=moved[:6], missing_examples=missing[:4], extra_examples=extra[:4])


def summary(ok, d, manifest_path):
    if ok:
        return f'atlas {d["model_atlas"]} == manifest ({d["parts"]} paint parts, {d["textures"]} textures) {os.path.basename(manifest_path)}'
    return (f'atlas {d["model_atlas"]} vs manifest {d["manifest_atlas"]}: {d["moved"]} parts moved {d["moved_examples"]}, '
            f'{d["missing"]} missing {d["missing_examples"]}, {d["extra"]} new {d["extra_examples"]}; textures on another atlas {d["stale"]}, '
            f'files changed since the manifest {d["changed"]} - re-bake the textures')


def sha12(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:12]


def write_manifest(path, aircraft, model_parts, model_file, textures=(), written_by='', note=''):
    """textures: paths of the files THIS build painted on the atlas; each is recorded with its sha256[:12] and the atlas it was painted
    on. Entries of an existing manifest for files this build did not write are kept with THEIR atlas (a partial re-bake, e.g.
    --dmg-only after a model change, then fails the guard until the rest is re-baked too)."""
    ah = atlas_hash(model_parts)
    tex = {}
    if os.path.exists(path):
        try:
            tex = dict(json.load(open(path)).get('textures', {}))
        except ValueError:
            tex = {}
    for t in sorted(textures):
        if os.path.exists(t):
            tex[os.path.basename(t)] = dict(sha=sha12(t), atlas=ah)
    m = dict(version=MANIFEST_VERSION, aircraft=aircraft, uv='livery', material='paint', quant=int(Q),
             atlas_hash=ah, model=os.path.basename(model_file) if model_file else '', written_by=written_by, note=note,
             textures=dict(sorted(tex.items())),
             parts={n: dict(hash=v['hash'], n=v['n'], cells=v.get('cells', '')) for n, v in sorted(model_parts.items())})
    with open(path, 'w') as f:
        json.dump(m, f, indent=1)
    return m


def atlas_textures(tex_dir, prefix):
    """the files a texture build paints on the livery atlas: <prefix>_skin_*.png and <prefix>_livery_*.png"""
    import glob
    return sorted(glob.glob(os.path.join(tex_dir, prefix + '_skin_*.png')) + glob.glob(os.path.join(tex_dir, prefix + '_livery_*.png')))


def manifest_from_cache(cache, tex_dir, prefix, aircraft, written_by, files=None):
    """B-25H / GA-25X drivers (bake_maps -> compose_*): the cache's atlas.json (written by bake_maps from the model) -> the manifest."""
    a = os.path.join(cache, 'atlas.json')
    if not os.path.exists(a):
        raise SystemExit(f'{a} missing: the bake cache predates the 1.8.16 guard - re-bake (drop --skip-bake)')
    j = json.load(open(a))
    m = write_manifest(os.path.join(tex_dir, prefix + '_atlas_manifest.json'), aircraft, j['parts'], j.get('model', ''),
                       atlas_textures(tex_dir, prefix) if files is None else files, written_by=written_by)
    print('[atlas] manifest', m['atlas_hash'], len(m['parts']), 'parts,', len(m['textures']), 'textures')
    return m


def load_manifest(path):
    return json.load(open(path))


# ------------------------------------------------------------------ Blender side
def _is_paint(mat):
    return mat is not None and (mat.name == 'paint' or mat.name.startswith('paint.'))


def _base(name):
    """FBX re-imports into a non-empty scene get .001 suffixes; the part name is the part before it."""
    i = name.rfind('.')
    return name[:i] if i > 0 and name[i + 1:].isdigit() else name


def scene_parts(objects=None, uv='livery', rename=None):
    """{part name: {'hash','n'}} from the loaded scene (a .blend or an FBX import): the `uv` layer of every face whose material is
    'paint'. rename maps object names to part names (e.g. the B-17G root object 'B17G' -> 'fus_center' in Unity, done there)."""
    import bpy
    rename = rename or {}
    out = {}
    for ob in (objects if objects is not None else bpy.data.objects):
        if ob.type != 'MESH':
            continue
        me = ob.data
        pis = {i for i, m in enumerate(me.materials) if _is_paint(m)}
        if not pis or uv not in me.uv_layers:
            continue
        data = me.uv_layers[uv].data
        pts = []
        for p in me.polygons:
            if p.material_index in pis:
                for li in p.loop_indices:
                    c = data[li].uv
                    pts.append((c[0], c[1]))
        if not pts:
            continue
        name = rename.get(_base(ob.name), _base(ob.name))
        if name in out:
            raise ValueError(f'two paint objects map to the part name {name!r}')
        h, n = part_hash(pts)
        out[name] = dict(hash=h, n=n, cells=encode_cells(part_cells(pts)))
    return out


def check_row(manifest_path, objects=None, uv='livery'):
    """-> (ok, detail str) for a model-check row; a missing manifest fails (textures of unknown provenance)."""
    if not os.path.exists(manifest_path):
        return False, f'no texture manifest {manifest_path}: re-bake the textures (the builders write it)'
    mp = scene_parts(objects, uv)
    ok, d = compare(mp, load_manifest(manifest_path), os.path.dirname(manifest_path))
    return ok, summary(ok, d, manifest_path)
