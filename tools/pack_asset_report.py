r"""Asset report of a built pack (.nobp): what is inside, by type, name and size, and where each object comes from.

  <venv>/python tools/pack_asset_report.py <pack.nobp> --out <report.txt> [--json <summary.json>]
                                           [--game-export <AssetRipper .../ExportedProject/Assets>]

Reads the pack only (UnityPy). Writes a text report: no game data, no pixels, no vertices; names, sizes and counts only.
For every Mesh, Texture2D, Sprite, AudioClip, Shader, MonoScript, TextAsset, Material, AnimationClip, Font and other payload object:
  type, name, serialized size, key numbers (vertices / triangles, width x height / format / streamed bytes) and its ORIGIN:
    ours:<aircraft>   stored under the pack's own folder for that aircraft (assets/blueprinter/mods/heritage_pairs/<aircraft>/...): written
                      there by our Unity generators from assets/model_* (our FBX), assets/textures_* (our PNG) or generated in the build
    placeholder       a Blueprinter *_PLACEHOLDER stub (a name the game resolves to its own asset at load; no game data in the pack)
    script-ref        a MonoScript: the NAME of a script class (game, Unity or Blueprinter) that a component refers to; it holds no code
    blueprinter       Blueprinter's own manifest / patch data
    unity             a shader of Unity's Universal Render Pipeline package or a Unity built-in (Unity Technologies; not a game asset): the
                      asset-bundle build includes the shader our own materials use
    UNKNOWN           anything else (must be 0 for a release)
Also counted: components that point OUT of the pack (MeshFilter / renderer / material references with a non-zero file id): those are the
placeholder references the game fills in; nothing of them is in the pack.

--game-data <your install's NuclearOption_Data> (optional, read only): counts the pack's ParticleSystems whose serialized settings equal a
stock one's (the build copies stock emitter settings; see SCOPE AND LIMITS in the report). Only counts and object names are written.

--game-export (optional; needs your own export of your own game): flags any object of ours whose NAME equals a game asset's name, and any
mesh that also has that game mesh's vertex count. Only names and counts are read and written.

Exit code 1 when anything is UNKNOWN, when an AudioClip, non-Unity Shader, compute shader, video, or .cs / .dll / .il TextAsset is found,
when a placeholder carries a real payload, or when a mesh of ours has a game mesh's name and vertex count.
Use the study venv: C:\Users\User\nuclearoption-ref\study\venv.
"""
import sys, os, json, re, collections
import UnityPy

PAYLOAD = ('Mesh', 'Texture2D', 'Sprite', 'AudioClip', 'Shader', 'ComputeShader', 'MonoScript', 'TextAsset', 'Material', 'AnimationClip', 'Font', 'VideoClip',
           'Cubemap', 'Texture3D', 'RenderTexture', 'AnimatorController', 'PhysicMaterial')
FORBIDDEN = ('AudioClip', 'ComputeShader', 'VideoClip')
UNITY_SHADERS = ('Universal Render Pipeline/', 'Hidden/Universal Render Pipeline/', 'Hidden/Core/', 'Hidden/InternalErrorShader', 'Sprites/', 'UI/')
OURS = ('b25h', 'ga25x', 'nimrod', 'fd32', 'b17g', 'msb17', 'anm2')
PLACEHOLDER_MAX = 4096      # a placeholder stub is a name and a few fields
VC = re.compile(r'm_VertexCount: (\d+)')


def main():
    a = sys.argv[1:]
    pack = a[0]
    out = a[a.index('--out') + 1]
    env = UnityPy.load(pack)
    path_of = {}
    for path, obj in env.container.items():
        try:
            path_of[obj.path_id] = path
        except Exception:
            pass
    rows = []
    by_type = collections.Counter(); size_by_type = collections.Counter()
    unknown, forbidden, fat_placeholder = [], [], []
    ext_refs = collections.Counter()
    for o in env.objects:
        t = o.type.name
        size = o.byte_size
        by_type[t] += 1; size_by_type[t] += size
        if t in ('MeshFilter', 'MeshRenderer', 'SkinnedMeshRenderer', 'Material', 'AudioSource', 'MeshCollider'):
            try:
                d = o.read()
                for fld in ('m_Mesh', 'm_Shader', 'm_audioClip'):
                    p = getattr(d, fld, None)
                    if p is not None and getattr(p, 'file_id', 0):
                        ext_refs[t + '.' + fld] += 1
                for m in (getattr(d, 'm_Materials', None) or []):
                    if getattr(m, 'file_id', 0):
                        ext_refs[t + '.m_Materials'] += 1
            except Exception:
                pass
        if t not in PAYLOAD:
            continue
        name, extra = '', ''
        try:
            d = o.read()
            name = getattr(d, 'm_Name', '') or ''
            if t == 'Mesh':
                vc = getattr(getattr(d, 'm_VertexData', None), 'm_VertexCount', 0)
                ic = sum(getattr(sm, 'indexCount', 0) for sm in getattr(d, 'm_SubMeshes', []))
                extra = f'{vc} verts, {ic // 3} tris'
            elif t == 'Texture2D':
                sd = getattr(d, 'm_StreamData', None)
                extra = f'{d.m_Width}x{d.m_Height} fmt {int(d.m_TextureFormat)}, {getattr(sd, "size", 0) or 0} streamed bytes'
            elif t == 'MonoScript':
                extra = f'{getattr(d, "m_AssemblyName", "")}:{getattr(d, "m_Namespace", "")}.{getattr(d, "m_ClassName", "")}'
            elif t == 'Shader':
                name = getattr(getattr(d, 'm_ParsedForm', None), 'm_Name', '') or name
            elif t == 'TextAsset':
                extra = f'{len(getattr(d, "m_Script", "") or "")} chars'
        except Exception as e:      # unreadable: still listed
            extra = 'unreadable: ' + type(e).__name__
        path = path_of.get(o.path_id, '')
        low = (path or '').lower()
        nl = name.lower()
        if t == 'MonoScript':
            origin = 'script-ref'
        elif t == 'Shader':
            origin = 'unity' if name.startswith(UNITY_SHADERS) else 'UNKNOWN'
            if origin == 'UNKNOWN':
                unknown.append((t, name, size, path)); forbidden.append((t, name, size))
        elif name.endswith('_PLACEHOLDER') or '_placeholder' in low:
            origin = 'placeholder'
            if size > PLACEHOLDER_MAX and t in ('Mesh', 'Texture2D', 'AudioClip'):
                fat_placeholder.append((t, name, size))
        elif '/mods/heritage_pairs/' in low:
            origin = 'ours:' + low.split('/mods/heritage_pairs/')[1].split('/')[0]
        elif any(k in nl for k in OURS):
            origin = 'ours:' + next(k for k in OURS if k in nl)
        elif t == 'TextAsset' and ('manifest' in nl or 'blueprint' in nl):
            origin = 'blueprinter'
        else:
            origin = 'UNKNOWN'
            unknown.append((t, name, size, path))
        if t in FORBIDDEN:
            forbidden.append((t, name, size))
        if t == 'TextAsset' and re.search(r'\.(cs|dll|il)$', nl):
            forbidden.append((t, name, size))
        rows.append((t, name, size, extra, origin, path))
    collide, same_mesh, gm, gt, gs = [], [], set(), set(), set()
    if '--game-export' in a:
        ge = a[a.index('--game-export') + 1]
        gm = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(ge, 'Mesh')) if f.endswith('.asset')}
        gt = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(ge, 'Texture2D')) if not f.endswith('.meta')}
        if os.path.isdir(os.path.join(ge, 'Sprite')):
            gs = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(ge, 'Sprite')) if not f.endswith('.meta')}
        for t, name, size, extra, origin, path in rows:
            if not origin.startswith('ours'):
                continue
            if (t == 'Mesh' and name in gm) or (t == 'Texture2D' and name in gt) or (t == 'Sprite' and name in gs):
                same = False
                if t == 'Mesh':
                    m = VC.search(open(os.path.join(ge, 'Mesh', name + '.asset'), encoding='utf-8', errors='replace').read())
                    same = bool(m) and extra.startswith(m.group(1) + ' verts')
                    if same:
                        same_mesh.append(name)
                collide.append((t, name, extra, 'SAME vertex count as the game mesh' if same else 'different data'))
    # 1.9.10: component settings are outside the object inventory above. With --game-data (your own install's NuclearOption_Data folder,
    # read only) count the pack's ParticleSystems whose serialized bytes (minus the 12-byte owner pointer) equal a stock one's.
    ps_total = by_type.get('ParticleSystem', 0); ps_bytes = size_by_type.get('ParticleSystem', 0); ps_same = ps_same_bytes = ps_cfg = None; ps_diff = []
    if '--game-data' in a:
        import hashlib
        gd = a[a.index('--game-data') + 1]
        stock = set()
        for f in sorted(os.listdir(gd)):
            fp = os.path.join(gd, f)
            if not os.path.isfile(fp) or f.lower().endswith(('.ress', '.resource', '.json', '.info', '.config')):
                continue
            try:
                ge_ = UnityPy.load(fp)
            except Exception:
                continue
            for o in ge_.objects:
                if o.type.name == 'ParticleSystem':
                    stock.add(hashlib.sha256(o.get_raw_data()[12:]).hexdigest())
        ps_same = ps_same_bytes = 0; cfgs = set()
        for o in env.objects:
            if o.type.name == 'ParticleSystem':
                raw = o.get_raw_data(); h = hashlib.sha256(raw[12:]).hexdigest()
                if h in stock:
                    ps_same += 1; ps_same_bytes += len(raw); cfgs.add(h)
                else:
                    try:
                        ps_diff.append(o.read().m_GameObject.read().m_Name)
                    except Exception:
                        ps_diff.append('?')
        ps_cfg = len(cfgs)
    rows.sort(key=lambda r: (r[0], r[4], r[1]))
    org = collections.Counter((r[0], r[4].split(':')[0]) for r in rows)
    L = []
    L.append(f'Asset report: {os.path.basename(pack)} ({os.path.getsize(pack)} bytes)')
    L.append('Made by tools/pack_asset_report.py from the pack itself. Names, sizes and counts only.')
    L.append('')
    L.append('SCOPE AND LIMITS. This report is an inventory of the payload objects in the pack (meshes, textures, sprites, materials, shaders,')
    L.append('script names, text assets). "ours" is decided by the folder the object is stored under; the optional game check compares names and')
    L.append('vertex counts. It does NOT look inside components. The pack contains COMPONENT SETTINGS COPIED FROM THE STOCK PREFABS OF THE GAME at')
    L.append('build time (EditorUtility.CopySerialized in unity/Editor/*Build.cs, from the Blueprinter placeholder prefabs): particle systems')
    L.append('(muzzle flash, muzzle smoke, contact sparks, wheel dust, sabots, ejection smoke, laser muzzle), audio-source settings, material')
    L.append('parameter blocks (glass, propeller disc), and starting values of other game components. These hold no mesh, texture, audio or code;')
    L.append('they remain the property of Shockfront (CREDITS.md, "The game"). The renderer and material references of those components point out of the pack.')
    if ps_same is not None:
        L.append(f'ParticleSystem check against the game install on the build PC (serialized bytes minus the owner pointer): {ps_same} of {ps_total} are '
                 f'byte-identical to a stock ParticleSystem ({ps_same_bytes} of {ps_bytes} bytes, {ps_cfg} distinct stock configurations); not identical: {sorted(ps_diff)}')
    else:
        L.append(f'ParticleSystem objects: {ps_total} ({ps_bytes} bytes); not compared with the game in this run (--game-data not given).')
    L.append('')
    L.append('Objects by type (count, serialized bytes; texture pixels are streamed and counted per texture below):')
    for t, n in sorted(by_type.items(), key=lambda kv: -size_by_type[kv[0]]):
        L.append(f'  {t:<24} {n:>6} {size_by_type[t]:>12}')
    L.append('')
    L.append('Payload objects by type and origin:')
    for (t, o_), n in sorted(org.items()):
        L.append(f'  {t:<16} {o_:<12} {n:>6}')
    L.append('')
    L.append('References that point out of the pack (placeholders the game fills in; nothing of them is stored here):')
    for k, n in sorted(ext_refs.items()):
        L.append(f'  {k:<34} {n:>6}')
    L.append('')
    L.append(f'UNKNOWN origin: {len(unknown)}')
    for u in unknown[:200]:
        L.append(f'  {u}')
    L.append(f'Forbidden types (audio, non-Unity shaders, compute shaders, video, source or DLL text): {len(forbidden)}')
    for u in forbidden[:200]:
        L.append(f'  {u}')
    L.append(f'Placeholders with a real payload (> {PLACEHOLDER_MAX} bytes): {len(fat_placeholder)}')
    for u in fat_placeholder[:200]:
        L.append(f'  {u}')
    if '--game-export' in a:
        L.append(f'Name check against the game export on the build PC ({len(gm)} game meshes, {len(gt)} game textures, {len(gs)} game sprites; names and vertex counts only):')
        L.append(f'  objects of ours whose NAME is also a game asset name: {len(collide)}; of those, meshes with the game mesh\'s vertex count: {len(same_mesh)}')
        for u in collide[:300]:
            L.append(f'  {u}')
    L.append('')
    L.append('type\torigin\tname\tbytes\tdetail\tpack path')
    for t, name, size, extra, origin, path in rows:
        L.append(f'{t}\t{origin}\t{name}\t{size}\t{extra}\t{path}')
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
    summ = dict(pack=os.path.basename(pack), objects=sum(by_type.values()), by_type=dict(by_type), payload=len(rows),
                origin={f'{t}/{o_}': n for (t, o_), n in sorted(org.items())}, external_refs=dict(ext_refs), unknown=len(unknown), forbidden=len(forbidden),
                fat_placeholder=len(fat_placeholder), game_export_checked='--game-export' in a, name_collisions=len(collide), same_mesh=len(same_mesh),
                particle_systems=ps_total, particle_systems_identical_to_stock=ps_same, particle_stock_configurations=ps_cfg, particle_not_identical=sorted(ps_diff))
    if '--json' in a:
        json.dump(summ, open(a[a.index('--json') + 1], 'w'), indent=1)
    print(json.dumps(summ)[:1800])
    sys.exit(1 if (unknown or forbidden or fat_placeholder or same_mesh) else 0)


if __name__ == '__main__':
    main()
