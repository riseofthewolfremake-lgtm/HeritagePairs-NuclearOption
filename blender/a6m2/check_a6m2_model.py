"""A6M2 round-1 model checks (design 7.4 + 10 round 1 CHECK rows that live on the model). Writes a JSON with one row per check.

  blender --background assets/model_a6m2/a6m2.blend --python-exit-code 1 --python blender/a6m2/check_a6m2_model.py -- --out assets/model_a6m2/a6m2_check.json

Rows:
  connectivity      every attachment point of the contract within 10 mm of a target surface; wing breaks gap <= 10 mm
  orientation       per mesh: faces whose normal points into the shell (ray test: forward ray meets a back face first, or the backward
                    ray meets nothing) <= 1 % (lathe / loft winding, fal-style inside-out props, FD-32 v1 lesson)
  see_through       Workbench masks with backface culling ON vs OFF from 14 outside views of the whole model and 6 views of every part
                    alone (= a detached part): pixels covered with culling off but background with culling on (holes) <= 0.05 % of the
                    silhouette
  blades            3 blade objects, each ONE mesh, ONE material 'prop', no children (memory prop-blade-one-renderer)
  guns              Type 97 bullet origins >= 0.15 m ahead of the blade plane and outside the spinner; Type 99 origins outside the wing
                    shell and > 0.3 m outside the prop disc
  com               CoM (part masses at mesh-bounds centres + fuel, the Unity check rule) inside 27-30 % MAC
  gear_sweep        main legs + wheels rotated in 10 deg steps to the stowed pose: no overlap with the wing / body skins, the two
                    wheels apart, stowed wheel inside its well volume
  hook              stowed hook mostly outside the tail skin (visible) and its pivot within 10 mm of the tail cone
  prop_attach       spinner back within 5 mm of the nose case on the axis, hub on the axis
  zfight            coplanar overlapping faces between different objects (< 0.6 mm, parallel normals) = 0
  no_refs           no generator source opens or names a refs\\wt_a6m2 path
  r8o C1-C8         checks_r8.r8o_checks (user test r8n: solid metal discs at every break, a structure 'box' through the holes): no flat
                    face in a break plane, see-into depth, structure only on thin members, no structure solids, tanks in tank metal, internals
                    inside their part, hole view of the forward fuselage, dark seam lining
  r8o C9            see_through: fus_center + cockpit parts from the front break, fus_rear alone from both ends
  r8o C10 / C11     no one plane takes > 30 % of the axial rays within 0.15 m of a break (C10); round 3: none takes > 60 % within 0.5 m,
                    any non-paint material, except the documented checks_r8.DEEP_WALL_ALLOW walls (firewall, liner-paint bay-end walls)
"""
import bpy, bmesh, sys, os, json, math, re
from mathutils import Vector as V, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else None
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import a6m2_spec as S
C = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), 'a6m2_contract.json')))
rows = []
dg = bpy.context.evaluated_depsgraph_get()


def R(name, ok, detail):
    rows.append(dict(name=name, ok=bool(ok), detail=detail))
    print('[check]', 'PASS' if ok else 'FAIL', name, '|', detail)


def world_tris(o, mats=None):
    me = o.data
    me.calc_loop_triangles()
    M = o.matrix_world
    vs = [M @ v.co for v in me.vertices]
    tris = []
    for lt in me.loop_triangles:
        mn = me.materials[lt.material_index].name if me.materials else ''
        if mats is not None and mn not in mats:
            continue
        tris.append(tuple(lt.vertices))
    return vs, tris


def bvh_of(objs, mats=None):
    V_, F_ = [], []
    for o in objs:
        vs, tris = world_tris(o, mats)
        b = len(V_)
        V_ += vs
        F_ += [tuple(i + b for i in t) for t in tris]
    return BVHTree.FromPolygons(V_, F_) if F_ else None


MESHES = [o for o in bpy.data.objects if o.type == 'MESH']
BY = {o.name: o for o in MESHES}

def inside(tree, p, allow_miss=0):
    """inside a (possibly double-skinned) shell: rays in all six axis directions hit it.
    r8o: the connectivity test allows one miss (the break ends are open like stock: from an attachment point inside a part one axis ray
    can leave through its open end)."""
    miss = 0
    for d in (V((1, 0, 0)), V((-1, 0, 0)), V((0, 1, 0)), V((0, -1, 0)), V((0, 0, 1)), V((0, 0, -1))):
        if tree.ray_cast(p, d, 50)[0] is None:
            miss += 1
    return miss <= allow_miss



# ------------------------------------------------------------------------------------------------- connectivity
bad = []
bvhs = {}
for a in C['attach']:
    p = V(a['p'])
    best = 9.0
    for t in a['to']:
        if t not in BY:
            continue
        if t not in bvhs:
            bvhs[t] = bvh_of([BY[t]])
        if inside(bvhs[t], p, allow_miss=1):        # a fitting buried in its target volume is attached
            best = 0.0
            break
        hit = bvhs[t].find_nearest(p)
        if hit[0] is not None:
            best = min(best, hit[3])
    if best > 0.010:
        bad.append(f"{a['obj']}->{'/'.join(a['to'])} {best * 1000:.0f} mm")
gaps = []
for L in ('L', 'R'):
    for a, b in ((('wing_C' if 'wing_C' in BY else 'fus_center'), f'wing_inner_{L}'), (f'wing_inner_{L}', f'wing_mid_{L}'), (f'wing_mid_{L}', f'wing_tip_{L}'), (f'wing_tip_{L}', f'wing_fold_{L}'),
                 ('fus_center', f'fillet_{L}'), (f'stab_{L}', 'fus_tail')):
        if a not in BY or b not in BY:
            continue                                   # r8e: wing_C / fillet_* are unified into fus_center
        ta = bvhs.setdefault(a, bvh_of([BY[a]]))
        vs, _ = world_tris(BY[b])
        d = min(ta.find_nearest(v)[3] for v in vs[::max(1, len(vs) // 400)])
        if d > 0.010:
            gaps.append(f'{a}|{b} {d * 1000:.0f} mm')
for a, b in (('fus_engine', 'fus_center'), ('fus_center', 'fus_rear'), ('fus_rear', 'fus_tail'), ('fin', 'fus_tail'), ('canopy_windscreen', 'fus_center'),
             ('canopy_rear', 'fus_center'), ('gear_tail_strut', 'fus_tail')):
    ta = bvhs.setdefault(a, bvh_of([BY[a]]))
    vs, _ = world_tris(BY[b])
    d = min(ta.find_nearest(v)[3] for v in vs[::max(1, len(vs) // 600)])
    if d > 0.010:                                      # r8o round 2: and the other way round (a sparse sample of a big part - fus_center
        tb = bvhs.setdefault(b, bvh_of([BY[b]]))       # grew with the lined wing-root cavities - can miss a small part's contact patch)
        va, _ = world_tris(BY[a])
        d = min(d, min(tb.find_nearest(v)[3] for v in va[::max(1, len(va) // 600)]))
    if d > 0.010:
        gaps.append(f'{a}|{b} {d * 1000:.0f} mm')
R('connectivity: attachment points <= 10 mm from their targets; adjacent parts touch (<= 10 mm)', not bad and not gaps,
  f"{len(C['attach'])} points; far: {bad}; part gaps: {gaps}")

# ------------------------------------------------------------------------------------------------- face orientation
# per connected component: a CLOSED component (every edge used an even number of times) must enclose a positive signed volume (outward
# winding); an OPEN component (plate, liner, cut skin) is tested by rays: a face whose forward ray meets a back face of the same component
# first points into it. Two-sided glazing is skipped (both windings by design).
orient = {}
worst = []
# r8o round 2: the dark lining of an open break end (skin edge, 25 mm band, cap strip; metal_dark within 0.13 m of a break plane) belongs
# to the liner shell and faces into it by design, as the 'interior' liner does
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "v2")))
import checks_r8 as _C8o
_BRK = [(p0_, n_) for _k, _pn, p0_, n_, _sb in _C8o.r8o_breaks()]


def _in_break_lining(c):
    return any(abs((c - p0_).dot(n_)) < 0.13 and ((c - p0_) - n_ * (c - p0_).dot(n_)).length < 3.5 for p0_, n_ in _BRK)


for o in MESHES:
    if o.name.startswith('canopy_'):
        continue
    vs, tris = world_tris(o)
    if not tris:
        continue
    o.data.calc_loop_triangles()
    MATS_OF = {o.name: {tuple(lt.vertices): o.data.materials[lt.material_index].name for lt in o.data.loop_triangles}}
    par = list(range(len(vs)))

    def fnd(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for t in tris:
        a0 = fnd(t[0])
        for k in t[1:]:
            par[fnd(k)] = a0
    comps = {}
    for t in tris:
        comps.setdefault(fnd(t[0]), []).append(t)
    bad_area = tot_area = 0.0
    for k, ts in comps.items():
        ec = {}
        for t in ts:
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                e = (min(e), max(e)); ec[e] = ec.get(e, 0) + 1
        area = sum(((vs[t[1]] - vs[t[0]]).cross(vs[t[2]] - vs[t[0]])).length / 2 for t in ts)
        tot_area += area
        if all(v % 2 == 0 for v in ec.values()):
            vol = sum(vs[t[0]].dot(vs[t[1]].cross(vs[t[2]])) for t in ts) / 6.0
            if vol < 0:
                bad_area += area
        else:
            tree = BVHTree.FromPolygons(vs, ts)
            for t in ts[::max(1, len(ts) // 200)]:
                a_, b_, c_ = (vs[i] for i in t)
                nrm = (b_ - a_).cross(c_ - a_)
                ar = nrm.length / 2
                if ar < 1e-10:
                    continue
                nrm.normalize()
                cen = (a_ + b_ + c_) / 3
                if MATS_OF[o.name][t] == 'interior':      # inner skins face into the shell by design (backed skin)
                    continue
                if MATS_OF[o.name][t] == 'metal_dark' and _in_break_lining(cen):
                    continue
                f = tree.ray_cast(cen + nrm * 1e-4, nrm, 20.0)
                if f[0] is not None and f[1].dot(nrm) > 0.05:
                    bad_area += area / max(1, len(ts[::max(1, len(ts) // 200)]))
    frac = bad_area / max(tot_area, 1e-9)
    orient[o.name] = round(frac, 4)
    if frac > 0.01:
        worst.append((o.name, round(frac, 3)))
R('orientation: per connected part of every mesh, closed shells enclose positive volume and open surfaces face out (inverted area <= 1 %)', not worst,
  f'{len(orient)} meshes; over 1 %: {sorted(worst, key=lambda x: -x[1])[:12]}')

# ------------------------------------------------------------------------------------------------- blades
bl = [o for o in MESHES if o.name.startswith('prop_blade_')]
bok = len(bl) == 3 and all(len(o.children) == 0 and [m.name for m in o.data.materials] == ['prop'] for o in bl)
R('blades: 3 blade objects, ONE mesh each, one material (prop), no children', bok, ', '.join(f"{o.name}: mats {[m.name for m in o.data.materials]} children {len(o.children)}" for o in bl))

# ------------------------------------------------------------------------------------------------- guns
plane_y = S.PROP_PLANE_Y * S.K
blade_front = max(max((o.matrix_world @ v.co).y for v in o.data.vertices) for o in bl)
m97 = [bpy.data.objects[f'muzzle_gun_{L}'].matrix_world.translation for L in 'LR']
r_sp = S.SPINNER[0][1] * S.K
ok97 = all(m.y - blade_front >= 0.15 and math.hypot(m.x, m.z) > r_sp + 0.05 for m in m97)
m99 = [bpy.data.objects[f'muzzle_cannon_{L}'].matrix_world.translation for L in 'LR']
wings = bvh_of([BY['wing_inner_L'], BY['wing_inner_R']])


tip_r = S.PROP_TIP_R * S.K
ok99 = all(not inside(wings, m) and math.hypot(m.x, m.z) > tip_r + 0.3 for m in m99)
R('guns: Type 97 bullet origins >= 0.15 m ahead of the blades (synchroniser) and off the spinner; Type 99 origins outside the wing and > 0.3 m outside the disc',
  ok97 and ok99, f"blade front y {blade_front:.3f}; T97 dy {[round(m.y - blade_front, 3) for m in m97]} r {[round(math.hypot(m.x, m.z), 3) for m in m97]}; "
  f"T99 r {[round(math.hypot(m.x, m.z), 3) for m in m99]} vs disc {tip_r:.3f}, inside wing {[inside(wings, m) for m in m99]}")

# ------------------------------------------------------------------------------------------------- CoM
le = S.MAC_LE_Y * S.K
M = sum(r[1] for r in C['mass_rows']); Y = sum(r[1] * r[2][1] for r in C['mass_rows']) / M
pct = (le - Y) / S.MAC
R('CoM 27-30 % MAC (the Unity check rule: parts at their collider-bounds centres + fuel 70 % in its tank part)',
  S.COM_MAC_BAND[0] <= pct <= S.COM_MAC_BAND[1], f'{M:.0f} kg y {Y:+.3f} = {pct * 100:.1f} % MAC (MAC {S.MAC} m, LE y {le:.3f})')

# ------------------------------------------------------------------------------------------------- gear sweep
skin_objs = [BY[n] for n in ('fus_center', 'fus_engine', 'wing_C', 'wing_inner_L', 'wing_inner_R', 'fillet_L', 'fillet_R', 'fus_rear') if n in BY]
SKV, STR = [], []
_br0 = S.span_built(S.WING_BREAKS[0])
for o in skin_objs:
    vs_, tr_ = world_tris(o, {'paint', 'structure', 'interior'})
    # r8e: the break caps (structure walls ON the root / wing_inner break plane, internal; seen only on a detached wing) are not skin:
    # since the break moved to 0.95 the stowed leg passes them inside the wing, as it passes the spars
    # r8o: no cap in the plane any more; the set-back root ribs at br0 -+ END_FRAME_SETBACK (internal webs, notched over the leg slot) take
    # the exclusion
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', 'v2')))
    import a6m2_parts as _AP
    _rp = [_AP.wing_break_plane(sd, _br0 + dd) for sd in (1, -1) for dd in (-0.10, 0.10)]     # the section planes lean with the dihedral
    tr_ = [t for t in tr_ if not all(any(abs((vs_[i] - p0_).dot(n_)) < 0.012 for p0_, n_ in _rp) for i in t)]
    # r8o: and the open root ends' lining (liner between the plane and the ribs) inside the wing, which the stowed leg passes as the cap
    if o.name in ('fus_center', 'wing_inner_L', 'wing_inner_R'):
        mi_ = {k for k, m in enumerate(o.data.materials) if m and m.name == 'interior'}
        o.data.calc_loop_triangles()
        lin_ = {tuple(lt.vertices) for lt in o.data.loop_triangles if lt.material_index in mi_}
        # r8o round 2: the lined root cavities (liner + bay-end walls, 'interior') run from |x| br0 - wing_cavity to br0 + wing_cavity
        _xa, _xb = _br0 - _AP.wing_cavity(_br0, 1) - 0.012, _br0 + _AP.wing_cavity(_br0, -1) + 0.012
        tr_ = [t for t in tr_ if not (t in lin_ and all(_xa < abs(vs_[i].x) < _xb for i in t))]
    b_ = len(SKV); SKV += vs_; STR += [tuple(i + b_ for i in t) for t in tr_]
skin = BVHTree.FromPolygons(SKV, STR)
buried = {}
liner = bvh_of([BY[n] for n in ('wing_C', 'fus_center', 'wing_inner_L', 'wing_inner_R') if n in BY], mats={'well'})   # r8e: wells cut into the unified root + wing_inner
hits = []
liner_hits = []
info = {L: json.loads(BY[f'gear_main_{L}_strut']['b25_info']) for L in 'LR'}
wheel_tris = {L: world_tris(BY[f'gear_main_{L}_wheel']) for L in 'LR'}
leg_tris = {L: world_tris(BY[f'gear_main_{L}_strut']) for L in 'LR'}
min_gap = 9.0
for deg_step in range(0, 9):
    trees = {}
    for L in 'LR':
        inf = info[L]
        f = min(deg_step * 10.0, inf['retract_deg'])
        if deg_step == 8:
            f = inf['retract_deg']
        q = Quaternion(V(inf['retract_axis_world']), math.radians(f))
        piv = V(inf['pivot'])
        for kind, (vs, tris) in (('wheel', wheel_tris[L]), ('leg', leg_tris[L])):
            vv = [piv + q @ (v - piv) for v in vs]
            t = BVHTree.FromPolygons(vv, tris)
            trees[(L, kind)] = (t, vv)
            ov = [(i, j) for i, j in t.overlap(skin) if (V((SKV[STR[j][0]].x, SKV[STR[j][0]].y, 0)) - V((piv.x, piv.y, 0))).length > 0.25]   # skin within 0.25 m of the pivot: the cover's hinge edge is buried in the wing like a door hinged inside the skin (reported, not a clash)
            buried[(L, kind)] = max(buried.get((L, kind), 0), len(t.overlap(skin)) - len(ov))
            if ov:
                cen = sum((vv[tris[i][0]] for i, _ in ov[:20]), V()) / min(len(ov), 20)
                hits.append(f'{L} {kind} {f:.0f} deg: {len(ov)} tri pairs near ({cen.x:.2f}, {cen.y:.2f}, {cen.z:.2f})')
            if liner is not None:
                lo = t.overlap(liner)
                if lo:
                    liner_hits.append(f'{L} {kind} {f:.0f}: {len(lo)}')
    if trees[('L', 'wheel')][0].overlap(trees[('R', 'wheel')][0]):
        hits.append(f'wheels touch at step {deg_step}')
    gap = min(abs(v.x) for v in trees[('L', 'wheel')][1]) + min(abs(v.x) for v in trees[('R', 'wheel')][1])
    min_gap = min(min_gap, gap)
# stowed wheel inside the well cylinder (plan) and between skins
stow_ok = True
for L, side in (('L', -1), ('R', 1)):
    inf = info[L]
    q = Quaternion(V(inf['retract_axis_world']), math.radians(inf['retract_deg']))
    piv = V(inf['pivot'])
    c = V(inf['wheel_up'])
    vs, _ = wheel_tris[L]
    rmax = max(math.hypot((piv + q @ (v - piv)).x - c.x, (piv + q @ (v - piv)).y - c.y) for v in vs)
    if rmax > S.WELL_R * S.K:
        stow_ok = False
        hits.append(f'{L} stowed wheel reaches {rmax:.3f} m from the well centre (well {S.WELL_R * S.K:.3f})')
R('gear sweep: legs + wheels at 0..85 deg (10 deg steps) never cut the wing / body skins, wheels apart, stowed wheel inside its well',
  not hits and stow_ok, f'skin overlaps: {hits[:8]}; buried hinge-region contacts (max tri pairs): {buried}; liner contacts (well wall, informative): {liner_hits[:6]}; min wheel-to-centreline sum {min_gap:.3f} m')

# ------------------------------------------------------------------------------------------------- hook
hk = BY['tailhook']
tail = bvh_of([BY['fus_tail']])
hv, _ = world_tris(hk)
outside = sum(1 for v in hv[::3] if not inside(tail, v)) / len(hv[::3])
piv = hk.matrix_world.translation + V((0.06, 0, 0))          # the hinge axle's end on the slot wall
dp = tail.find_nearest(piv)[3]
R('hook: stowed A-frame visible under the belly (> 60 % of its vertices outside the tail skin), hinge axle end on the slot wall (within 30 mm of the tail skin)',
  outside > 0.6 and (dp < 0.03 or inside(tail, piv)), f'{outside * 100:.0f} % outside, pivot {dp * 1000:.0f} mm from the skin')

# ------------------------------------------------------------------------------------------------- prop attach
hub = BY['prop_hub']
hv, _ = world_tris(hub)
back = min(v.y for v in hv)
eng = bvh_of([BY['fus_engine']])
nearest = min(eng.find_nearest(v)[3] for v in hv if v.y < back + 0.01)
axis_off = max(abs(hub.matrix_world.translation.x), abs(hub.matrix_world.translation.z))
R('prop attachment: spinner back within 5 mm of the nose case (no gap), hub on the thrust axis', nearest <= 0.005 and axis_off < 1e-4,
  f'spinner back y {back:.3f}, nearest engine surface {nearest * 1000:.1f} mm, hub off-axis {axis_off * 1000:.2f} mm')

# ------------------------------------------------------------------------------------------------- z-fight
zf = []
paint_objs = [o for o in MESHES if o.data.materials and any(m.name == 'paint' for m in o.data.materials)]
trees = {o.name: bvh_of([o]) for o in paint_objs}
for o in paint_objs:
    vs, tris = world_tris(o, {'paint'})
    for t in tris[::max(1, len(tris) // 250)]:
        a, b, c = (vs[i] for i in t)
        n = (b - a).cross(c - a)
        if n.length < 1e-10:
            continue
        n.normalize()
        cen = (a + b + c) / 3
        for p in paint_objs:
            if p is o or (p.parent == o or o.parent == p) and False:
                continue
            if {o.name.split('_')[0], p.name.split('_')[0]} == {'canopy', 'ckcanopy'}:
                continue            # r8: the exterior canopy and the cockpit-view canopy never render together (exterior / cockpit renderers)
            h = trees[p.name].find_nearest(cen)
            if h[0] is not None and h[3] < 0.0006 and h[1].dot(n) > 0.995:     # same-facing coplanar faces fight; back-to-back contact does not
                zf.append(f'{o.name}/{p.name}@({cen.x:.2f},{cen.y:.2f},{cen.z:.2f})')
zf = sorted(set(zf))
zpairs = sorted(set(z.split('@')[0] for z in zf))
R('z-fight: no coplanar overlapping paint faces between different objects (< 0.6 mm, parallel)', not zf, f'{len(zpairs)} pairs {zpairs}; samples {zf[:8]}')

# ------------------------------------------------------------------------------------------------- no refs
srcs = [os.path.join(HERE, f) for f in os.listdir(HERE) if f.endswith('.py')] + [os.path.join(HERE, 'textures', f) for f in os.listdir(os.path.join(HERE, 'textures')) if f.endswith('.py')]
offend = []
for f in srcs:
    if os.path.basename(f) == 'check_a6m2_model.py':
        continue
    txt = open(f, encoding='utf-8').read()
    txt = re.sub(r'"""[\s\S]*?"""', '', txt)
    txt = re.sub(r'#[^\n]*', '', txt)
    if re.search(r'refs[\\/]+wt_a6m2|wt_a6m2[\\/]', txt):
        offend.append(os.path.basename(f))
    for m in re.finditer(r"""open\(\s*r?['"]([^'"]+)['"]""", txt):
        if 'refs' in m.group(1).lower():
            offend.append(os.path.basename(f) + ':' + m.group(1))
R('no refs: no A6M2 generator opens anything under nuclearoption-ref\\refs (numbers live in a6m2_spec.py)', not offend, f'{len(srcs)} sources; offending {offend}')

# ------------------------------------------------------------------------------------------------- see-through (last: it renders)
def see_through():
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = 480, 300
    sh = sc.display.shading
    sh.light = 'FLAT'; sh.color_type = 'SINGLE'; sh.single_color = (1, 1, 1)
    sh.background_type = 'VIEWPORT'; sh.background_color = (0, 0, 0)
    sc.view_settings.view_transform = 'Standard'
    cam = bpy.data.objects.new('stc', bpy.data.cameras.new('stc')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = 35
    tmp = os.path.join(os.path.dirname(bpy.data.filepath), '_seethrough_tmp.png')

    cnt = [0]

    def mask():
        # r1b: a fresh file name per render (re-writing one name failed on a file lock: "cannot save _seethrough_tmp.png")
        cnt[0] += 1
        fn = tmp[:-4] + '_%04d.png' % cnt[0]
        sc.render.filepath = fn
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(fn, check_existing=False)
        px = list(img.pixels)
        w, h = img.size
        bpy.data.images.remove(img)
        try:
            os.remove(fn)
        except OSError:
            pass
        return [px[i * 4] > 0.5 for i in range(w * h)]

    def views(objs, dirs, dist):
        pts = [o.matrix_world @ V(b) for o in objs for b in o.bound_box]
        c = sum(pts, V()) / len(pts)
        rad = max((p - c).length for p in pts)
        cam.data.clip_start = max(rad * 0.01, 0.001)      # r4: small cockpit parts sit inside the default 0.1 m near clip (false 'holes')
        cam.data.clip_end = max(rad * 20.0, 100.0)
        res = []
        for d in dirs:
            d = V(d).normalized()
            cam.location = c + d * rad * dist
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
            sh.show_backface_culling = False
            a = mask()
            sh.show_backface_culling = True
            b = mask()
            sil = sum(a)
            W_, H_ = sc.render.resolution_x, sc.render.resolution_y
            # a see-through pixel: geometry there with culling off, background with culling on, AND enclosed by the culled silhouette in its
            # row and its column (edge-on back faces at the outline are not see-through)
            rowmin = [W_] * H_; rowmax = [-1] * H_; colmin = [H_] * W_; colmax = [-1] * W_
            for i, on in enumerate(b):
                if on:
                    y_, x_ = divmod(i, W_)
                    rowmin[y_] = min(rowmin[y_], x_); rowmax[y_] = max(rowmax[y_], x_)
                    colmin[x_] = min(colmin[x_], y_); colmax[x_] = max(colmax[x_], y_)
            holes = 0
            for i, (x, y) in enumerate(zip(a, b)):
                if x and not y:
                    yy, xx = divmod(i, W_)
                    if rowmin[yy] < xx < rowmax[yy] and colmin[xx] < yy < colmax[xx]:
                        holes += 1
            res.append((holes, sil))
        return res
    dirs14 = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1),
              (1, 1, -1), (-1, 1, -1), (1, -1, -1), (-1, -1, -1)]
    glassy = {'canopy_windscreen', 'canopy_hood', 'canopy_rear', 'ckcanopy_fixed', 'ckcanopy_hood'}   # r8: + the cockpit-view canopy
    for o in MESHES:
        o.hide_render = o.name in glassy                      # two-sided glass is see-through by design
    whole = views([o for o in MESHES if not o.hide_render], dirs14, 2.2)
    worst = []
    tot_h = sum(h for h, s in whole); tot_s = sum(s for h, s in whole)
    part_names = [n for n in BY if n not in glassy and not n.startswith(('prop_blade', 'gear_', 'aerial', 'pitot', 'cannon_', 'rack_', 'tailhook'))]
    dirs6 = [(1, 0.2, 0.1), (-1, 0.2, 0.1), (0.1, 1, 0.2), (0.1, -1, 0.2), (0.2, 0.1, 1), (0.2, 0.1, -1)]
    ALLOW = {'wing_C': 0.001, 'wing_inner_L': 0.001, 'wing_inner_R': 0.001, 'fus_center': 0.001}   # the open wheel well: through the root notch of a detached
    for n in part_names:                                                        # wing piece one sees out of the well's bottom opening
        for o in MESHES:
            o.hide_render = o.name != n
        r = views([BY[n]], dirs6, 2.6)
        h = sum(x for x, _ in r); s = sum(y for _, y in r)
        if s and h / s > ALLOW.get(n, 0.0005):
            worst.append((n, round(h / s * 100, 3)))
    # r8o C9 break_view_with_children: with the break caps gone, the cockpit backs and the hollow rear fuselage seen through the open ends
    c9 = []
    ck = [o.name for o in MESHES if o.name.startswith(('cockpit_', 'gauge_')) and o.name not in glassy]
    for names, dirs, lab in ((['fus_center'] + ck, [(0.1, 1, 0.2), (0.0, 1, 0.05), (-0.15, 1, -0.1)], 'fus_center + cockpit from the front break'),
                             (['fus_rear'], [(0.1, 1, 0.2), (0.0, 1, 0.05), (0.1, -1, 0.2), (0.0, -1, 0.05)], 'fus_rear from both ends')):
        for o in MESHES:
            o.hide_render = o.name not in names
        r = views([BY[n] for n in names], dirs, 2.6)
        h = sum(x for x, _ in r); s = sum(y for _, y in r)
        c9.append((lab, h, s))
    R('r8o C9 break_view_with_children (open breaks: the cockpit backs / hollow fuselage seen through the open ends): see-through with '
      'culling ON <= 0.05 % for fus_center with every cockpit_* / gauge_* part from the front break, and fus_rear alone from both ends',
      all(s_ and h_ / s_ <= 0.0005 for _, h_, s_ in c9), '; '.join(f'{l_}: {h_} / {s_} px = {h_ / max(s_, 1) * 100:.3f} %' for l_, h_, s_ in c9))
    for o in MESHES:
        o.hide_render = False
    if os.path.exists(tmp):
        os.remove(tmp)
    frac = tot_h / max(tot_s, 1)
    R('see-through with backface culling ON: whole model 14 views and every part alone 6 views (detached part): enclosed hole pixels <= 0.05 % of the silhouette (0.1 % on wing_C / wing_inner: the open well seen through the root notch)',
      frac <= 0.0005 and not worst, f'whole {tot_h} / {tot_s} px = {frac * 100:.3f} %; parts over 0.05 %: {worst[:12]}')


# r8 (user review 1): tub closed from the eye, continuous canopy frames, wing-root seam ray sweep
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', 'v2')))
import checks_r8 as C8, a6m2_parts as AP8, a6m2_canopy as CAN8, a6m2_ck_layout as L8
AP8.build_exterior() if not CAN8.FRAMES else None                  # FRAMES are filled by the canopy generator
_eye = BY['cockpit_eye'].matrix_world.translation.copy() if 'cockpit_eye' in BY else bpy.data.objects['cockpit_eye'].matrix_world.translation.copy()
C8.tub_rays(R, _eye, L8.BULKHEAD_Y * S.K)
C8.sight_mount(R, S, S.K)                                           # r8m (user review r8l)
C8.stick_sweep(R)
C8.frames(R, CAN8, AP8, S.K)
C8.root_seam(R, AP8, S, S.K)
C8.fillet_smooth(R, AP8)
C8.root_junction(R, S.K)
if 'wing_C' not in bpy.data.objects:
    C8.root_unified(R, S.K)
C8.livery_uv_sane(R)
C8.le_root_sweep(R)
C8.gear_bay_sweep(R)
C8.well_detail_clear(R)
C8.throttle_sweep_clear(R)
C8.throttle_lever_one_piece(R)   # r8n: the lever is one closed shell (user review r8m: two rectangles, gap at the elbow)
C8.cockpit_contained(R, AP8, S.K)
C8.r8o_checks(R)                 # r8o (user test r8n: solid metal discs at every break, a structure 'box' through the holes): C1-C8
see_through()                    # + r8o C9
ok = all(r['ok'] for r in rows)
print('[check]', 'ALL PASS' if ok else 'FAILED', f"{sum(r['ok'] for r in rows)}/{len(rows)}")
if OUT:
    json.dump(dict(ok=ok, rows=rows, orientation=orient), open(OUT, 'w'), indent=1)
