"""1.8.16: check a built pack (.nobp) against the texture atlas manifests, from the pack itself (UnityPy).

  <venv>/python tools/atlas_pack_check1816.py <pack.nobp> [--old <older pack.nobp>] [--json out.json] [--manifest KEY=<manifest.json> ...]

Per aircraft (B25H, GA25X, NIMROD1, FD32, B17G): every MeshRenderer whose material is <KEY>_paint -> the paint sub-mesh triangles ->
their UV0 points -> the blender/atlas_guard.py part hash (same recipe as AtlasGuard1816.cs) -> compared with
assets/textures_*/<prefix>_atlas_manifest.json. With --old: which <prefix>_skin_* / livery textures changed between the two packs
(image bytes of the decoded Texture2D).
UnityPy reads the pack only (no game files are written). Use the study venv (UnityPy): C:\\Users\\User\\nuclearoption-ref\\study\\venv.
"""
import os, sys, json, hashlib, collections
import UnityPy
from UnityPy.helpers.MeshHelper import MeshHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'blender'))
import atlas_guard as AG

AC = dict(B25H=('textures_v2', 'b25h', {}), GA25X=('textures_ga25x', 'ga25x', {'hook_mesh': 'tailhook'}), NIMROD1=('textures_nimrod', 'nimrod', {}),
          FD32=('textures_fd32', 'fd32', {}), B17G=('textures_b17g', 'b17g', {'fus_center': 'B17G'}),
          MSB17=('textures_msb1780', 'msb17', {'fus_center': 'MSB17'}))     # 1.9.0; 1.9.9: key MSB17 (folder name kept)


def load(p):
    env = UnityPy.load(p)
    byid = {}
    for o in env.objects:
        byid[o.path_id] = o
    return env, byid


def paint_parts(env, byid):
    mats = {}
    for o in env.objects:
        if o.type.name == 'Material':
            n = o.read().m_Name
            for k in AC:
                if n == k + '_paint':
                    mats[o.path_id] = k
    pts = {k: collections.defaultdict(set) for k in AC}
    cache = {}
    for o in env.objects:
        if o.type.name != 'MeshRenderer':
            continue
        r = o.read()
        ms = [m.path_id for m in r.m_Materials]
        hit = [(i, mats[m]) for i, m in enumerate(ms) if m in mats]
        if not hit:
            continue
        go = r.m_GameObject.read()
        mf = None
        for c in go.m_Components:
            cid = c.component.path_id if hasattr(c, 'component') else c.path_id
            co = byid.get(cid)
            if co is not None and co.type.name == 'MeshFilter':
                mf = co.read()
        if mf is None or mf.m_Mesh.path_id == 0:
            continue
        mid = mf.m_Mesh.path_id
        if mid not in cache:
            mesh = byid[mid].read()
            h = MeshHandler(mesh); h.process()
            cache[mid] = (h.m_UV0, h.get_triangles())
        uv, tris = cache[mid]
        for sm, key in hit:
            if sm >= len(tris):
                continue
            s = pts[key][go.m_Name]
            for t in tris[sm]:
                for i in t:
                    s.add((float(uv[i][0]), float(uv[i][1])))
    return pts


def part_name(unity_name, rename, known):
    """AtlasGuard1816.PartName: rename map, then '<part>_visible' / '<part>_int' -> '<part>' when the manifest knows the part"""
    if unity_name in rename:
        return rename[unity_name]
    if unity_name in known:
        return unity_name
    for suf in ('_visible', '_int'):
        if unity_name.endswith(suf) and unity_name[:-len(suf)] in known:
            return unity_name[:-len(suf)]
    return unity_name


def check_aircraft(raw, man, rename):
    """mirror of AtlasGuard1816.Check (parts only): -> (ok, detail)"""
    mp = man['parts']
    pts = collections.defaultdict(set)
    for n, s in raw.items():
        pts[part_name(n, rename, mp)] |= s
    exact, bad = 0, []
    for n, v in mp.items():
        if n not in pts:
            continue
        if AG.part_hash(pts[n])[0] == v['hash']:
            exact += 1
            continue
        if not v.get('cells'):
            bad.append(n + ' (no cells)'); continue
        cu, cm = AG.coverage(AG.part_cells(pts[n]), AG.decode_cells(v['cells']))
        if cu < AG.COVER_MODEL or cm < AG.COVER_MANIFEST:
            bad.append(f'{n} {100 * cu:.0f}/{100 * cm:.0f} %')
    missing = sorted(n for n in mp if n not in pts)
    extra = sorted(n for n in pts if n not in mp)
    ok = not bad and not missing and not extra and len(pts) > 0
    return ok, dict(parts=len(mp), exact=exact, cell_match=len(mp) - exact - len(missing) - len(bad), moved=bad, missing=missing, extra=extra,
                    pack_atlas=AG.atlas_hash({n: AG.part_hash(s)[0] for n, s in pts.items()}))


def tex_hashes(env, prefix_set):
    out = {}
    for o in env.objects:
        if o.type.name != 'Texture2D':
            continue
        t = o.read()
        n = t.m_Name
        if any(n.startswith(p + '_skin_') or n.startswith(p + '_livery_') for p in prefix_set):
            out[n] = hashlib.sha256(t.image.tobytes()).hexdigest()[:12]   # decoded pixels (the data is streamed: image_data is empty)
    return out


def main():
    a = sys.argv[1:]
    pack = a[0]
    env, byid = load(pack)
    parts = paint_parts(env, byid)
    res = dict(pack=os.path.basename(pack), aircraft={})
    allok = True
    for k, (td, pre, _) in AC.items():
        mf = os.path.join(ROOT, 'assets', td, pre + '_atlas_manifest.json')
        for o in [x for i, x in enumerate(a) if i and a[i - 1] == '--manifest' and x.startswith(k + '=')]:
            mf = o.split('=', 1)[1]          # e.g. --manifest B17G=tools/fixtures/atlas1816/b17g_1.8.9_manifest.json (failure case)
        if not os.path.exists(mf):
            print(f'{k:8s} FAIL no manifest {mf}'); allok = False; res['aircraft'][k] = dict(ok=False, error='no manifest'); continue
        man = AG.load_manifest(mf)
        ok, d = check_aircraft(parts[k], man, AC[k][2])
        allok &= ok
        res['aircraft'][k] = dict(ok=ok, manifest_atlas=man['atlas_hash'], **d)
        print(f'{k:8s} {"PASS" if ok else "FAIL"} manifest {man["atlas_hash"]} parts {d["parts"]}: exact UV0 hash {d["exact"]}, texel-cell match {d["cell_match"]}, '
              f'moved {len(d["moved"])} {d["moved"][:4]}, missing {len(d["missing"])} {d["missing"][:3]}, new {len(d["extra"])} {d["extra"][:3]}')
    if '--old' in a:
        envo, _ = load(a[a.index('--old') + 1])
        pre = {v[1] for v in AC.values()}
        tn, to = tex_hashes(env, pre), tex_hashes(envo, pre | {'msb1780'})
        to = {('msb17_' + n[len('msb1780_'):] if n.startswith('msb1780_') else n): h for n, h in to.items()}   # 1.9.9: packs before the key rename name the MSB textures msb1780_*; same texture, compared under the new name
        res['textures'] = {n: dict(new=tn.get(n), old=to.get(n), changed=tn.get(n) != to.get(n)) for n in sorted(set(tn) | set(to))}
        for p in sorted(pre):
            ch = [n for n, v in res['textures'].items() if n.startswith(p + '_') and v['changed']]
            same = [n for n, v in res['textures'].items() if n.startswith(p + '_') and not v['changed']]
            print(f'textures {p}: {len(ch)} changed vs the old pack, {len(same)} identical' + (f'  identical: {same}' if ch and same else ''))
    if '--json' in a:
        json.dump(res, open(a[a.index('--json') + 1], 'w'), indent=1)
    sys.exit(0 if allok else 1)


if __name__ == '__main__':
    main()
