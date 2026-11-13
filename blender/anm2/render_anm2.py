"""1.8.13 (offline L, round 2) study renders of our AN/M2 (written outside the repo, nothing here ships):
  guns   : our gun, the War Thunder reference gun (local study extraction) and the stock game door gun (AssetRipper export of the user's
           install, read-only) one by one in the SAME camera per view (side / top / front / rear / q34) -> one sheet per pairing
           (cmp_<tag>_<view>.png + sheet_<tag>.png): flex single (flex + grips vs WT gun6 vs stock), turret twin (turret L + R vs WT gun2)
  b17g / b25h : every turret with our guns placed exactly as ANM2Gun.Place does (per-slot Mounts table, el-local), at rest and at the
           corners of its limits: 'o' opaque skin from outside, 'x' x-ray (skin at alpha 0.25), 'i' from the gunner's eye inside (cabins)

  blender -b -P blender/anm2/render_anm2.py -- <out_dir> [--part guns|b17g|b25h] [--mesh <anm2_mesh.json dir>]
Gun meshes: assets/model_anm2/anm2_mesh.json (Unity gun frame x right, y up, z fire) -> Blender (x, z, y), winding reversed.
"""
import bpy, sys, os, math, json, re
import numpy as np
from mathutils import Vector, Matrix

a = sys.argv[sys.argv.index('--') + 1:]
OUT = a[0]
PART = a[a.index('--part') + 1] if '--part' in a else 'all'
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
MESHDIR = a[a.index('--mesh') + 1] if '--mesh' in a else os.path.join(ROOT, 'assets', 'model_anm2')
B17G_BLEND = a[a.index('--b17g') + 1] if '--b17g' in a else os.path.join(ROOT, 'assets', 'model_b17g', 'b17g.blend')
B25H_BLEND = a[a.index('--b25h') + 1] if '--b25h' in a else os.path.join(ROOT, 'assets', 'model_v2', 'b25h_v2.blend')
REF = r'C:\Users\User\nuclearoption-ref\study\anm2_ref'
STOCK = r'C:\Users\User\nuclearoption-ref\tools\assetripper\NUCLEAROPTIONEXPORTS\ExportedProject\Assets'
SPEC = json.load(open(os.path.join(MESHDIR, 'anm2_mesh.json')))
TIP = SPEC['spec']['tip_z']
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, 'tools'))


def scene_setup(res=(1600, 900)):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.55, 0.57, 0.6, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3.5; sun.rotation_euler = (0.75, 0.25, 0.9); sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    return sc, cam


_mat = {}


def tex_material(name, path, alpha_clip=False, metal=0.25, rough=0.65, normal=None, ao=None):     # = ANM2Gun.Load (parkerized: matte)
    if name in _mat:
        return _mat[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
    img = nt.nodes.new('ShaderNodeTexImage'); img.image = bpy.data.images.load(path)
    col = img.outputs['Color']
    if ao:
        ai = nt.nodes.new('ShaderNodeTexImage'); ai.image = bpy.data.images.load(ao); ai.image.colorspace_settings.name = 'Non-Color'
        mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs[0].default_value = 1.0
        nt.links.new(col, mx.inputs[6]); nt.links.new(ai.outputs['Color'], mx.inputs[7]); col = mx.outputs[2]
    nt.links.new(col, bsdf.inputs['Base Color'])
    if normal:
        ni = nt.nodes.new('ShaderNodeTexImage'); ni.image = bpy.data.images.load(normal); ni.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(ni.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Metallic'].default_value = metal; bsdf.inputs['Roughness'].default_value = rough
    if alpha_clip:
        nt.links.new(img.outputs['Alpha'], bsdf.inputs['Alpha'])
        if hasattr(m, 'surface_render_method'):
            m.surface_render_method = 'DITHERED'
        else:
            m.blend_method = 'CLIP'
        m.use_backface_culling = False
    _mat[name] = m
    return m


def gun_object(name, key, matrix=Matrix()):
    d = SPEC[key]
    V = [(p[0], p[2], p[1]) for p in d['v']]
    F = []; mi = []
    for sub, kk in ((0, 't'), (1, 't_jacket')):
        T = d.get(kk, [])
        for k in range(0, len(T), 3):
            F.append((T[k], T[k + 2], T[k + 1])); mi.append(sub)        # handedness change: reverse the winding
    me = bpy.data.meshes.new(name); me.from_pydata(V, [], F); me.update()
    uv = me.uv_layers.new(name='uv')
    for poly in me.polygons:
        for li, vi in zip(poly.loop_indices, poly.vertices):
            uv.data[li].uv = d['uv'][vi]
    nt_ = SPEC['spec'].get('normal_tex')
    me.materials.append(tex_material('anm2', os.path.join(MESHDIR, SPEC['spec']['tex']), normal=os.path.join(MESHDIR, nt_) if nt_ else None))
    me.materials.append(tex_material('anm2_jacket', os.path.join(MESHDIR, SPEC['spec']['jacket_tex']), alpha_clip=True))
    for poly, m_ in zip(me.polygons, mi):
        poly.material_index = m_
    # the exported per-corner normals (split at hard edges) as custom normals
    nrm = [(n[0], n[2], n[1]) for n in d['n']]
    me.normals_split_custom_set([nrm[vi] for poly in me.polygons for vi in poly.vertices])
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); o.matrix_world = matrix
    return o


def stock_object(name, matrix=Matrix()):
    """the stock game door gun (whole M2 + ammo can) from the AssetRipper export, bore moved onto ours: bore (0, 0.042) tip z 1.196
    (B17GBuild BarrelTip read the same) -> our tip; texture = its own basemap x AO, its normal map. Study only."""
    from unity_mesh_asset import read_mesh, submesh_tris
    m = read_mesh(os.path.join(STOCK, 'Mesh', '50cal_doorGun_barrel.asset'))
    P = m['pos']; V = [(p[0], p[2] - 1.196 + TIP, p[1] - 0.042) for p in P]
    F = [(int(t[0]), int(t[2]), int(t[1])) for t in submesh_tris(m, 0)]
    me = bpy.data.meshes.new(name); me.from_pydata(V, [], F); me.update()
    uv = me.uv_layers.new(name='uv')
    for poly in me.polygons:
        for li, vi in zip(poly.loop_indices, poly.vertices):
            uv.data[li].uv = (m['uv'][vi][0], m['uv'][vi][1])
    t = os.path.join(STOCK, 'Texture2D', 'utilityHelo1_attachments_')
    me.materials.append(tex_material('stock', t + 'b.png', metal=0.0, rough=0.55, normal=t + 'n.png', ao=t + 'ao.png'))
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o); o.matrix_world = matrix
    print('STOCK', name, 'verts', len(V), 'tris', len(F))
    return o


def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def place_cam(cam, lo, hi, view):
    c = (lo + hi) / 2; size = hi - lo
    cam.data.type = 'ORTHO'
    if view == 'side':  cam.location = c + Vector((5, 0, 0)); cam.rotation_euler = (math.pi / 2, 0, math.pi / 2); cam.data.ortho_scale = max(size.y, size.z * 1.78) * 1.08
    if view == 'top':   cam.location = c + Vector((0, 0, 5)); cam.rotation_euler = (0, 0, -math.pi / 2); cam.data.ortho_scale = max(size.y, size.x * 1.78) * 1.08
    if view == 'front': cam.location = c + Vector((0, 5, 0)); cam.rotation_euler = (math.pi / 2, 0, math.pi); cam.data.ortho_scale = max(size.x * 1.78, size.z) * 1.15
    if view == 'rear':  cam.location = c + Vector((0, -5, 0)); cam.rotation_euler = (math.pi / 2, 0, 0); cam.data.ortho_scale = max(size.x * 1.78, size.z) * 1.15
    if view == 'q34':
        cam.data.type = 'PERSP'; d = Vector((1.1, -1.25, 0.65)).normalized() * size.length * 1.25; cam.location = c + d
        cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = 50


def render(path):
    bpy.context.scene.render.filepath = path; bpy.ops.render.render(write_still=True)


def clear_meshes():
    for o in list(bpy.data.objects):
        if o.type in ('MESH', 'EMPTY'):
            bpy.data.objects.remove(o)


def wt_import(names):
    """WT gun(s) aligned like sheet.py: barrel along +Y (muzzle +Y), up +Z; the group's muzzle tip at our TIP, its bore through z 0."""
    before = set(bpy.data.objects)
    for n in names:
        bpy.ops.wm.obj_import(filepath=os.path.join(REF, 'obj', n + '.obj'), forward_axis='Y', up_axis='Z')
    wto = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    bpy.context.view_layer.update()
    pts = np.array([list(o.matrix_world @ v.co) for o in wto for v in o.data.vertices])
    c = pts.mean(0); u, s, vt = np.linalg.svd(pts - c, full_matrices=False); ax = Vector(vt[0])
    proj = (pts - c) @ np.array(ax); lo_, hi_ = proj.min(), proj.max()
    def spread(mask):
        q = pts[mask]; cc = q.mean(0); r = (q - cc) - np.outer((q - cc) @ np.array(ax), np.array(ax)); return np.linalg.norm(r, axis=1).mean()
    if spread(proj > hi_ - 0.3) > spread(proj < lo_ + 0.3): ax = -ax
    up = Vector((0, 1, 0)); up = (up - up.dot(ax) * ax).normalized(); x = ax.cross(up).normalized(); up = x.cross(ax)
    R = Matrix((x, ax, up)).to_4x4()
    for o in wto: o.matrix_world = R @ Matrix.Translation(-Vector(c)) @ o.matrix_world
    bpy.context.view_layer.update()
    P = np.array([list(o.matrix_world @ v.co) for o in wto for v in o.data.vertices])
    tipm = P[:, 1] > P[:, 1].max() - 0.01
    tip = P[tipm].mean(0)
    sh = Vector((0 if len(names) > 1 else -tip[0], TIP - tip[1], -tip[2]))
    for o in wto: o.matrix_world = Matrix.Translation(sh) @ o.matrix_world
    return wto


# ------------------------------------------------------------------------------------------------------------ 1 gun vs reference vs stock
def compare():
    sc, cam = scene_setup((1100, 520))
    sets = [('flex_single', ['gun6_73_0'], [('flex_L', 0.0), ('grips', 0.0)], True),
            ('turret_twin', ['gun2_77_1'], [('turret_L', -0.285), ('turret_R', 0.285)], False)]
    for tag, wt, ours, with_stock in sets:
        clear_meshes()
        groups = {'wt': wt_import(wt), 'ours': [gun_object(f'ours_{k}', k, Matrix.Translation((dx, 0, 0))) for k, dx in ours]}
        if with_stock:
            groups['stock'] = [stock_object('stock')]
        bpy.context.view_layer.update()
        lo, hi = bbox([o for g in groups.values() for o in g])
        for v in ('side', 'top', 'front', 'rear', 'q34'):
            place_cam(cam, lo, hi, v)
            for gname, objs in groups.items():
                for g2, o2 in groups.items():
                    for o in o2:
                        o.hide_render = g2 != gname
                render(os.path.join(OUT, f'cmp_{tag}_{v}_{gname}.png'))
        for g2 in groups.values():
            for o in g2:
                o.hide_render = False
        print('COMPARE', tag, 'groups', list(groups))


# ------------------------------------------------------------------------------------------------------------ 2 turrets on the aircraft
def mounts():
    """ANM2Gun.Mounts parsed from the C# (one source of truth): slot -> (x, y, z) el-local Unity."""
    src = open(os.path.join(ROOT, 'unity', 'Editor', 'ANM2Gun.cs'), encoding='utf-8').read()
    return {k: (float(x), float(y), float(z)) for k, x, y, z in re.findall(r'\{ "(\w+)", new Vector3\(([-\d.]+)f, ([-\d.]+)f, ([-\d.]+)f\) \}', src)}


def turrets(blend, gun_slots, label, views=('o', 'x', 'i'), dist=2.4, only=None, prefix='', hide=(), extra=()):
    """gun_slots: (base, [(slot, muzzle, key, grips)], az, el, (trav, emin, emax), eye) -- eye: gunner's eye in el-rest-local Blender
    coordinates (x right, y aim, z up) or None (no cabin view)."""
    bpy.ops.wm.open_mainfile(filepath=blend)
    _mat.clear()                                   # materials of the previous file are gone
    sc, cam = scene_setup((1000, 700))
    M_ = mounts()
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and ('50cal' in o.name):
            o.hide_render = True
    skin = [m for m in bpy.data.materials if m.use_nodes and m.node_tree.nodes.get('Principled BSDF') is not None]
    alpha0 = {m.name: m.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value for m in skin}
    def xray(on):
        for m in skin:
            b = m.node_tree.nodes['Principled BSDF']
            b.inputs['Alpha'].default_value = 0.25 if on else alpha0[m.name]
            if hasattr(m, 'surface_render_method'):
                m.surface_render_method = 'BLENDED' if on or alpha0[m.name] < 1 else 'DITHERED'
            else:
                m.blend_method = 'BLEND' if on or alpha0[m.name] < 1 else 'OPAQUE'
    for base, slots, azn, eln, (trav, emin, emax), eye, outdir in gun_slots:
        az, el = bpy.data.objects.get(azn), bpy.data.objects.get(eln)
        if az is None or el is None:
            print('MISSING', base); continue
        made = []
        for slot, mz, key, grips in slots:
            so, mo = bpy.data.objects.get(slot), bpy.data.objects.get(mz)
            if so is None or mo is None:
                print('MISSING slot', slot); continue
            so.hide_render = True
            R = so.matrix_world.to_3x3().normalized()
            M = R.to_4x4()
            ER = el.matrix_world
            if slot in M_:
                mx, my, mz_ = M_[slot]
                mx = (ER.inverted() @ so.matrix_world.translation).x + (-0.010 if slot == 'cheek_R_gun0' else 0.0)       # = ANM2Gun.Place (+ MountsDx)
                tr_pt = ER @ Vector((mx, mz_, my))                      # el-local Unity (x, y up, z aim) -> Blender el-local (x, aim, up)
            else:
                tr_pt = mo.matrix_world.translation - R.col[1] * TIP
            M.translation = tr_pt
            if len(slots) > 1:          # twins: = ANM2Gun.Variant (the gun on el's +x side is the right-feed mirror)
                key = key[:-1] + ('R' if (ER.inverted() @ so.matrix_world.translation).x > 0 else 'L')
                if slot in ('gun_tail_L', 'gun_tail_R'):     # = ANM2Gun.TwinLeverOut
                    key = key[:-1] + ('L' if key.endswith('R') else 'R')
            g = gun_object(f'{slot}_anm2', key, M); made.append(g)
            print('GUN', label, slot, key, 'trunnion', tuple(round(v, 3) for v in tr_pt), 'pivot', tuple(round(v, 3) for v in el.matrix_world.translation))
            ng = 0
            if grips:
                ex = (ER.inverted() @ tr_pt).x
                if slot in ('gun_tail_L', 'gun_tail_R') and 'grips_twin' in SPEC:         # = ANM2Gun.TwinSharedGrips: one set on the centre line
                    if ex < 0:
                        Mg = M.copy(); Mg.translation = ER @ Vector((0.0, (ER.inverted() @ tr_pt).y, (ER.inverted() @ tr_pt).z))
                        made.append(gun_object(f'{slot}_grips', 'grips_twin', Mg)); ng = 1
                else:
                    made.append(gun_object(f'{slot}_grips', 'grips', M)); ng = 1
            for m_ in made[-(1 + ng):]:
                mw = m_.matrix_world.copy(); m_.parent = el; m_.matrix_world = mw
        az0, el0 = az.matrix_basis.copy(), el.matrix_basis.copy()
        if 'guns' in hide:                         # r4 diagnosis renders
            for g in made:
                g.hide_render = True
        if 'glass' in hide:
            for m in bpy.data.materials:
                if 'glass' in m.name.lower() and m.use_nodes and m.node_tree.nodes.get('Principled BSDF') is not None:
                    m.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.0
                    if hasattr(m, 'surface_render_method'):
                        m.surface_render_method = 'BLENDED'
        elw0 = el.matrix_world.copy()
        tr = min(trav, 180)
        poses = [('rest', 0, 0)] + ([('az%+d_el%+d' % (a_, e_), a_, e_) for a_ in (-tr, tr) for e_ in (emin, emax)] if tr < 180 else
                                    [('az%03d_el%+d' % (a_, e_), a_, e_) for a_ in (0, 90, 180, 270) for e_ in (emin, emax)]) + list(extra)
        for name, a_, e_ in poses:
            if only is not None and name not in only:
                continue
            az.matrix_basis = az0 @ Matrix.Rotation(math.radians(-a_), 4, 'Z')
            el.matrix_basis = el0 @ Matrix.Rotation(math.radians(e_), 4, 'X')
            bpy.context.view_layer.update()
            pts = [g.matrix_world @ Vector(cn) for g in made for cn in g.bound_box]
            c = sum(pts, Vector()) / max(len(pts), 1)
            gfwd = (made[0].matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized() if made else Vector((0, 1, 0))
            side = gfwd.cross(Vector((0, 0, 1))); side = side.normalized() if side.length > 1e-3 else Vector((1, 0, 0))
            out = Vector(outdir).normalized()          # outside camera direction (world), per station
            for vn in views:
                if vn == 'i' and eye is None:
                    continue
                cam.data.type = 'PERSP'
                if vn == 'o':
                    xray(False); cam.data.lens = 35
                    cam.location = c + out * dist; look = c
                elif vn == 'x':
                    xray(True); cam.data.lens = 35
                    cam.location = c + side * 1.9 + Vector((0, 0, 1.1)) - gfwd * 0.3; look = c
                else:
                    xray(False); cam.data.lens = 24
                    # the gunner's eye: 0.40 m behind the grips, 0.15 m over the bore, in the elevation frame at rest (turns with az only)
                    d0 = M_.get(slots[0][0], (0, 0, 0.1))[2]
                    ev = Vector((0.0, d0 - 1.15, 0.15)) if eye == 'auto' else Vector(eye)
                    ef = el.matrix_world.copy()                # r3: the gunner's head behind the grips, looking down the gun at the pose (sight picture)
                    cam.location = ef @ ev
                    look = cam.location + (ef.to_3x3() @ Vector((0, 1, -0.12))).normalized()
                cam.rotation_euler = (look - cam.location).to_track_quat('-Z', 'Y').to_euler()
                render(os.path.join(OUT, f'{prefix}{label}_{base}_{name}_{vn}.png'))
        xray(False)
        az.matrix_basis = az0; el.matrix_basis = el0


# eye: el-rest-local Blender (x right, y aim, z up): behind the receiver / grips, head height
B17G_TURRETS = [
    ('chin', [('chin_gun0', 'chin_muzzle0', 'turret_L', False), ('chin_gun1', 'chin_muzzle1', 'turret_R', False)], 'chin_az', 'chin_el', (78, -26, 20), None, (0.7, 1.0, -0.5)),
    ('top', [('top_gun0', 'top_muzzle0', 'turret_L', False), ('top_gun1', 'top_muzzle1', 'turret_R', False)], 'top_az', 'top_el', (360, 0, 85), None, (0.8, 0.9, 0.9)),
    ('ball', [('ball_gun0', 'ball_muzzle0', 'turret_L', False), ('ball_gun1', 'ball_muzzle1', 'turret_R', False)], 'ball_az', 'ball_el', (360, -90, 0), None, (0.9, 0.7, -0.8)),
    ('tail', [('tail_gun0', 'tail_muzzle0', 'flex_L', True), ('tail_gun1', 'tail_muzzle1', 'flex_R', True)], 'tail_az', 'tail_el', (30, -30, 30), 'auto', (0.8, -1.0, 0.3)),
    ('cheek_L', [('cheek_L_gun0', 'cheek_L_muzzle0', 'flex_L', True)], 'cheek_L_az', 'cheek_L_el', (15, -20, 20), 'auto', (-1.0, 0.8, 0.2)),
    ('cheek_R', [('cheek_R_gun0', 'cheek_R_muzzle0', 'flex_R', True)], 'cheek_R_az', 'cheek_R_el', (15, -20, 20), 'auto', (1.0, 0.8, 0.2)),
    ('waist_L', [('waist_L_gun0', 'waist_L_muzzle0', 'flex_R', True)], 'waist_L_az', 'waist_L_el', (55, -40, 50), 'auto', (-1.0, 0.2, 0.25)),
    ('waist_R', [('waist_R_gun0', 'waist_R_muzzle0', 'flex_L', True)], 'waist_R_az', 'waist_R_el', (55, -40, 50), 'auto', (1.0, 0.2, 0.25)),
    ('radio', [('radio_gun0', 'radio_muzzle0', 'flex_R', True)], 'radio_az', 'radio_el', (30, -25, 25), 'auto', (0.7, -0.5, 1.0)),
]
B25H_TURRETS = [
    ('dorsal', [('gun_turret_L', 'muzzle_turret_L', 'turret_L', False), ('gun_turret_R', 'muzzle_turret_R', 'turret_R', False)], 'turret_dorsal', 'turret_dorsal_guns', (360, 10, 85), None, (0.8, 0.9, 0.9)),
    ('tail', [('gun_tail_L', 'muzzle_tail_L', 'flex_R', True), ('gun_tail_R', 'muzzle_tail_R', 'flex_L', True)], 'tail_turret_az', 'tail_guns', (20, -25, 25), 'auto', (0.8, -1.0, 0.3)),
    ('waist_L', [('gun_waist_L', 'muzzle_waist_L', 'flex_R', True)], 'waist_gun_L_az', 'waist_gun_L', (17.5, -30, 40), 'auto', (-1.0, 0.2, 0.25)),
    ('waist_R', [('gun_waist_R', 'muzzle_waist_R', 'flex_L', True)], 'waist_gun_R_az', 'waist_gun_R', (17.5, -30, 40), 'auto', (1.0, 0.2, 0.25)),
]

if PART in ('all', 'guns'):
    compare()
if PART in ('all', 'b17g'):
    turrets(B17G_BLEND, B17G_TURRETS, 'b17g')
if PART in ('all', 'b25h'):
    turrets(B25H_BLEND, B25H_TURRETS, 'b25h')
if PART == 'close':      # r3 close-ups: dome slots at rest / +85, tail covers and gunner views, chin ring from below
    pick = lambda T, names: [t for t in T if t[0] in names]
    turrets(B17G_BLEND, pick(B17G_TURRETS, ('top', 'tail', 'chin')), 'b17g', views=('o', 'i'), dist=1.35,
            only={'rest', 'az000_el+85', 'az+30_el+30'}, prefix='close_')
    turrets(B25H_BLEND, pick(B25H_TURRETS, ('dorsal', 'tail')), 'b25h', views=('o', 'i'), dist=1.35,
            only={'rest', 'az000_el+85', 'az+20_el+25'}, prefix='close_')
if PART == 'diag':        # r4: identify the dark shapes in the B-25H dorsal slots (guns hidden / glass hidden)
    pick = lambda T, names: [t for t in T if t[0] in names]
    for h in ((), ('guns',), ('glass',)):
        turrets(B25H_BLEND, pick(B25H_TURRETS, ('dorsal',)), 'b25h', views=('o',), dist=1.35, only={'az000_el+85'}, prefix='diag_' + '_'.join(h or ('all',)) + '_', hide=h)
if PART == 'close':      # r4: the top turret at 68 / 85 deg from the front and from the side
    for tag, od in (('front', (0.0, 1.0, 0.35)), ('side', (1.0, 0.05, 0.30))):
        T = [t[:6] + (od,) for t in B17G_TURRETS if t[0] == 'top'] + [t[:6] + (od,) for t in B25H_TURRETS if t[0] == 'dorsal']
        turrets(B17G_BLEND, T[:1], 'b17g', views=('o',), dist=1.35, only={'el68', 'el85'}, prefix=f'close_{tag}_', extra=(('el68', 0, 68), ('el85', 0, 85)))
        turrets(B25H_BLEND, T[1:], 'b25h', views=('o',), dist=1.35, only={'el68', 'el85'}, prefix=f'close_{tag}_', extra=(('el68', 0, 68), ('el85', 0, 85)))
if PART in ('close', 'chinring'):   # r3 item 5: the chin ring / nose opening edge seen from outside (below, beside) and from the bombardier's seat
    bpy.ops.wm.open_mainfile(filepath=B17G_BLEND)
    sc, cam = scene_setup((1000, 700))
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and '50cal' in o.name:
            o.hide_render = True
    cr = Vector((0.0, 6.14, -0.40))
    cam.data.type = 'PERSP'
    for nm, loc, look, lens in (('below_side', Vector((1.10, 6.00, -1.35)), cr, 35), ('below_front', Vector((0.0, 7.30, -1.20)), cr, 35),
                                ('ring_edge_close', Vector((0.75, 6.25, -0.85)), Vector((0.45, 6.10, -0.45)), 35),
                                ('bombardier_seat', Vector((0.0, 6.38, 0.83)), Vector((0.0, 6.30, -0.10)), 20)):
        cam.location = loc; cam.data.lens = lens
        cam.rotation_euler = (look - loc).to_track_quat('-Z', 'Y').to_euler()
        render(os.path.join(OUT, f'close_b17g_chinring_{nm}.png'))
print('RENDER DONE')
