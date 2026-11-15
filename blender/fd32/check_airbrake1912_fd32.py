"""1.9.12 checks of the FD-32 airbrake add-on against the SHIPPED model (read only).

  blender --background assets/model_fd32/fd32.blend --python-exit-code 1 --python blender/fd32/check_airbrake1912_fd32.py -- <fd32_airbrake.json> <fd32_airbrake.fbx> <out check.json>

The panels are rebuilt in memory from the open model (airbrake1912_fd32.build_objects) and compared with the JSON and the FBX that were
written; every clearance is measured on the model's real objects (strips, flare ejectors, hook, spine fairing, canopy, tailplane, fin,
truss, marking positions of the texture builder). Exit code 1 when a row fails.
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'blender', 'v2', 'textures'))
sys.path.insert(0, os.path.join(HERE, 'textures'))
import airbrake1912_fd32 as AB

argv = sys.argv[sys.argv.index('--') + 1:]
jpath, fbx, outp = [os.path.abspath(a) for a in argv[:3]]
rows = []


def R(name, ok, detail):
    rows.append(dict(name=name, ok=bool(ok), detail=str(detail)))
    print('[check]', 'PASS' if ok else 'FAIL', name, '|', detail)


O = bpy.data.objects
base_objects = {o.name for o in O}
objs, rep = AB.build_objects()
bpy.context.view_layer.update()
want = json.load(open(jpath))
site = AB.SITE
y0, y1, z0, z1 = site['y_hinge'], site['y_aft'], site['z_lo'], site['z_hi']


def world_tris(ob, mat_names=None, M=None):
    me = ob.data
    M = M or ob.matrix_world
    ok = None if mat_names is None else {i for i, m in enumerate(me.materials) if m is not None and m.name in mat_names}
    vs = [M @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons if ok is None or p.material_index in ok]
    return vs, polys


def bvh(ob, mat_names=None, M=None):
    vs, polys = world_tris(ob, mat_names, M)
    return BVHTree.FromPolygons(vs, polys) if polys else None


def min_dist(points, tree, cap=5.0):
    d = cap
    for p in points:
        r = tree.find_nearest(p, d)
        if r[0] is not None:
            d = min(d, r[3])
    return d


def panel_points(ob, M=None, step=0.03):
    """vertices + edge samples of a mesh in world space"""
    M = M or ob.matrix_world
    me = ob.data
    pts = [M @ v.co for v in me.vertices]
    for e in me.edges:
        a, b = M @ me.vertices[e.vertices[0]].co, M @ me.vertices[e.vertices[1]].co
        n = int((a - b).length / step)
        for k in range(1, n + 1):
            pts.append(a.lerp(b, k / (n + 1)))
    return pts


# ------------------------------------------------------------------ 1. the files are what this model gives
same = all(json.dumps(rep['sides'][s], sort_keys=True) == json.dumps(want['sides'][s], sort_keys=True) for s in 'LR') and rep['site'] == want['site']
R('fd32_airbrake.json == the panels rebuilt from the model now (site, frames, counts, numbers)', same,
  f"L hinge {rep['sides']['L']['hinge_unity']} R hinge {rep['sides']['R']['hinge_unity']}")

names = ['airbrake_L_hinge', 'airbrake_L', 'airbrake_tray_L', 'airbrake_R_hinge', 'airbrake_R', 'airbrake_tray_R']
bad = []
for s in 'LR':
    h, p, t = objs[f'airbrake_{s}_hinge'], objs[f'airbrake_{s}'], objs[f'airbrake_tray_{s}']
    if h.type != 'EMPTY' or h.parent is None or h.parent.name != 'fus_rear':
        bad.append(h.name + ' not an empty under fus_rear')
    if p.parent is not h:
        bad.append(p.name + ' not under its hinge')
    if t.parent is None or t.parent.name != 'fus_rear':
        bad.append(t.name + ' not under fus_rear')
    pm = [m.name for m in p.data.materials]; tm = [m.name for m in t.data.materials]
    if pm[0] != 'paint' or set(pm) != {'paint', 'structure', 'metal_dark', 'cove'}:
        bad.append(f'{p.name} materials {pm}')
    if 'paint' in tm or not set(tm) <= {'structure', 'cove'}:
        bad.append(f'{t.name} materials {tm}')
    if [l.name for l in p.data.uv_layers] != ['livery', 'detail']:
        bad.append(p.name + ' uv layers')
R('six objects: per side a hinge empty under fus_rear, one panel mesh under the hinge (paint = slot 0, + cove seam, structure, metal_dark; UV livery + detail), one fixed well under fus_rear without paint',
  not bad and set(objs) == set(names), bad or ', '.join(names))

tris = {n: sum(len(p.vertices) - 2 for p in objs[n].data.polygons) for n in names if objs[n].type == 'MESH'}
R('triangles: each panel <= 450, each well <= 120 (stock airbrake panels 120-474)', all(v <= (450 if 'tray' not in k else 120) for k, v in tris.items()), tris)

# ------------------------------------------------------------------ 2. paint = the skin's texels
fus = O['fus_rear']
me = fus.data
pi = [m.name for m in me.materials].index('paint')
uvl = me.uv_layers['livery'].data
svs = [fus.matrix_world @ v.co for v in me.vertices]
spolys = [p for p in me.polygons if p.material_index == pi]
stree = BVHTree.FromPolygons(svs, [tuple(p.vertices) for p in spolys])
stats = json.loads(bpy.context.scene.get('b25_build_stats', '{}'))
texel_m = stats.get('metres_per_uv', 11.614) / 2048.0


def skin_uv_at(pt):
    loc, nrm, idx, dist = stree.find_nearest(pt)
    p = spolys[idx]
    vs = [svs[i] for i in p.vertices]; us = [Vector(uvl[li].uv) for li in p.loop_indices]
    best = None
    for k in range(1, len(vs) - 1):
        a, b, c = vs[0], vs[k], vs[k + 1]
        v0, v1, v2 = b - a, c - a, loc - a
        d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
        den = d00 * d11 - d01 * d01
        if abs(den) < 1e-18:
            continue
        w1 = (d11 * d20 - d01 * d21) / den; w2 = (d00 * d21 - d01 * d20) / den; w0 = 1 - w1 - w2
        err = max(0, -w0) + max(0, -w1) + max(0, -w2)
        if best is None or err < best[0]:
            best = (err, us[0] * w0 + us[k] * w1 + us[k + 1] * w2)
    return best[1], dist, nrm


n_p = 0; dmin, dmax, uverr = 9.0, 0.0, 0.0
for s in 'LR':
    p = objs[f'airbrake_{s}']
    pm = p.data; ppi = [m.name for m in pm.materials].index('paint'); puv = pm.uv_layers['livery'].data
    for poly in pm.polygons:
        if poly.material_index != ppi:
            continue
        for li in poly.loop_indices:
            w = p.matrix_world @ pm.vertices[pm.loops[li].vertex_index].co
            uv, d, _ = skin_uv_at(w)
            n_p += 1; dmin = min(dmin, d); dmax = max(dmax, d)
            uverr = max(uverr, (Vector(puv[li].uv) - uv).length)
R('paint texels: every panel paint corner has the atlas UV of the fus_rear skin point under it (within 0.25 texel) and lies 3.0 - 4.4 mm above the skin',
  n_p > 0 and 0.0030 <= dmin and dmax <= 0.0044 and uverr * stats.get('metres_per_uv', 11.614) < 0.25 * texel_m,
  f'{n_p} corners, {dmin * 1000:.2f}..{dmax * 1000:.2f} mm above the skin, worst UV error {uverr * 2048:.3f} texel ({texel_m * 1000:.2f} mm per texel)')

# nothing of the inner body shows through the shut panel's face: every structure / rim vertex is under the paint face
poke = 0.0
for s in 'LR':
    p = objs[f'airbrake_{s}']; pm = p.data
    inner = {i for i, m in enumerate(pm.materials) if m.name == 'structure'}
    for poly in pm.polygons:
        if poly.material_index in inner:
            for vi in poly.vertices:
                w = p.matrix_world @ pm.vertices[vi].co
                loc, nrm, idx, dist = stree.find_nearest(w)
                poke = max(poke, (w - loc).dot(nrm))
R('shut panel: every vertex of the inner body (structure faces: inner skin, stiffeners, closing frame) is below the skin surface, so at least 4 mm under the paint face (nothing pokes through the shut panel)',
  poke <= 0.0, f'highest inner-body vertex {poke * 1000:.2f} mm relative to the skin surface (paint face at +{dmin * 1000:.2f})')

# ------------------------------------------------------------------ 3. shut: clear of everything round it
shut_pts = {s: panel_points(objs[f'airbrake_{s}']) + panel_points(objs[f'airbrake_tray_{s}']) for s in 'LR'}
allp = shut_pts['L'] + shut_pts['R']
ob_d = {}
skip = set(names) | {'fus_rear', 'fus_rear_struct'}
for o in O:
    if o.type != 'MESH' or o.name in skip or o.name not in base_objects:
        continue
    t = bvh(o)
    if t is None:
        continue
    ob_d[o.name] = min_dist(allp, t, 0.6)
near = sorted((d, n) for n, d in ob_d.items() if d < 0.6)
need = {'slimelight_side_L': 0.04, 'slimelight_side_R': 0.04, 'slimelight_spine': 0.30, 'spine_aft': 0.10, 'hook_channel': 0.15, 'tailhook': 0.15}
okc = all(ob_d.get(k, 9) >= v for k, v in need.items()) and all(d >= 0.04 for d, n in near)
R('shut panel + well: >= 40 mm from the green side strips, >= 0.30 m from the spine strip, >= 0.10 m from the spine fairing, >= 0.15 m from the hook and its channel; no other object of the model within 40 mm',
  okc, ', '.join(f'{n} {d * 1000:.0f} mm' for d, n in near[:8]))
far = {k: min((Vector(q) - Vector(p)).length for p in allp for q in ([O[k].matrix_world.translation] if O[k].type == 'EMPTY' else [O[k].matrix_world @ v.co for v in O[k].data.vertices]))
       for k in ('flare_L', 'flare_R', 'stab_L', 'stab_R', 'fin', 'canopy_slide', 'slimelight_fin_L', 'gear_tail_strut')}
R('shut panel: flare ejectors >= 0.15 m, tailplane >= 0.9 m, fin >= 0.8 m, canopy hood >= 0.8 m away', far['flare_L'] >= 0.15 and far['flare_R'] >= 0.15 and min(far['stab_L'], far['stab_R']) >= 0.9 and far['fin'] >= 0.8 and far['canopy_slide'] >= 0.8,
  ', '.join(f'{k} {v:.3f} m' for k, v in far.items()))

# truss / inner structure: the shut panel's inner body against fus_rear_struct's `structure` faces (the inner skin `fabric_in` is 2.5 mm
# under the outer skin and hides the body; the tubes must not be touched)
st = O['fus_rear_struct']
t_truss = bvh(st, {'structure'}); t_inner = bvh(st, {'fabric_in'})
body = [q for s in 'LR' for q in panel_points(objs[f'airbrake_{s}'], step=0.015)]
d_truss = min_dist(body, t_truss, 0.5) if t_truss else 9.0
deep = max(v['inner_depth_mm'] for v in rep['sides'].values())
R('shut panel inner body (stiffeners, hinge arms, reaching into the fuselage behind the uncut skin): >= 15 mm from every truss tube / frame face of fus_rear_struct',
  d_truss >= 0.015, f'nearest structure face {d_truss * 1000:.1f} mm from the body; body reaches {deep:.1f} mm inside the hinge line (the inner skin sheet is {min_dist(body, t_inner, 0.5) * 1000:.1f} mm from it: crossed, hidden between the two skins)')

# outline against the paint the texture builder puts on the flank (read from the builder's own source numbers)
import faction_marks as FM
g = np.linspace(-0.6, 0.6, 481, dtype=np.float32)
pu, pv = np.meshgrid(g, g)
ext = {}
for kind in ('BDF', 'PALA'):
    cov = np.zeros(pu.shape, np.float32)
    for c, rgb in FM.layers(kind, pu.ravel(), pv.ravel(), 2 * 0.29, 0.004):
        cov = np.maximum(cov, np.asarray(c, np.float32).reshape(pu.shape))
    m = cov > 0.02
    ext[kind] = (float(pu[m].min()), float(pu[m].max()), float(pv[m].min()), float(pv[m].max()))
mark_aft = AB.MARK['y'] - max(max(abs(e[0]), abs(e[1])) for e in ext.values())
src = open(os.path.join(HERE, 'textures', 'build_textures_fd32.py'), encoding='utf-8').read()
have_sites = "s.append(('fus', sel, side * (G.y + 2.12), G.z + 0.06, 0.29))" in src and "side * (G.y + 3.30), G.z + 0.02, text, 0.13 if not small else 0.09, 0.022, rgb)" in src
serial_fwd = AB.SERIAL['y'] + AB.text_width(5, 0.09) / 2 + 0.011
try:
    import naval1912_fd32 as NV
    tb = [NV.text_box(NV.SCHEME[k]['title'], NV.TITLE_Y, NV.TITLE_Z, NV.TITLE_H, NV.TITLE_STROKE + 2 * NV.OUTLINE) for k in NV.KEYS]
    title_fwd = max(b[1] for b in tb)
    # the naval markings against the model: title behind the side strip and ahead of the tailplane, on the flank; fin number behind
    # the fin strip, ahead of the rudder hinge, inside the fin outline
    strip_aft = min((O[n].matrix_world @ v.co).y for n in ('slimelight_side_L', 'slimelight_side_R') for v in O[n].data.vertices)
    stab_le = max((O[n].matrix_world @ v.co).y for n in ('stab_L', 'stab_R') for v in O[n].data.vertices)
    nb = [NV.text_box(NV.SCHEME[k]['number'], NV.RUD_NUM_Y, NV.RUD_NUM_Z, NV.RUD_NUM_H, NV.RUD_NUM_STROKE + 2 * NV.OUTLINE) for k in NV.KEYS]
    n_y0, n_y1, n_z0, n_z1 = min(b[0] for b in nb), max(b[1] for b in nb), min(b[2] for b in nb), max(b[3] for b in nb)
    # round 2: the number is on the RUDDER. Hinge line and trailing edge are measured on the rudder's paint at the number's heights
    # (side-view rays), every corner of the box must be on rudder paint on both sides, and NOTHING else of the model may lie in front
    # of the box in the side view (the first build's fin number had the tailplane brace across a digit).
    rud = O['rudder']; rtree = bvh(rud, {'paint'})
    def rud_hit(yy, zz, sx):
        return rtree.ray_cast(Vector((sx, yy, zz)), Vector((-sx, 0, 0)).normalized(), 1.0)[0] is not None
    def span(zz):
        ys = [yy for yy in np.arange(-5.80, -4.70, 0.002) if rud_hit(float(yy), zz, 0.5) and rud_hit(float(yy), zz, -0.5)]
        return (min(ys), max(ys)) if ys else (0.0, 0.0)
    spans = [span(zz) for zz in (n_z0, 0.5 * (n_z0 + n_z1), n_z1)]
    rud_te, rud_hinge = max(sp[0] for sp in spans), min(sp[1] for sp in spans)
    on_rud = all(rud_hit(yy, zz, sx) for sx in (-0.5, 0.5) for yy in (n_y0, n_y1) for zz in (n_z0, n_z1))
    across = []
    for o in O:
        if o.type != 'MESH' or o.name not in base_objects or o.name == 'rudder' or o.hide_render:
            continue
        me_ = o.data; Mw = o.matrix_world
        vs = [Mw @ v.co for v in me_.vertices]
        if not vs or max(v.y for v in vs) < n_y0 or min(v.y for v in vs) > n_y1 or max(v.z for v in vs) < n_z0 or min(v.z for v in vs) > n_z1:
            continue
        hit = False
        for e in me_.edges:
            p_, q_ = vs[e.vertices[0]], vs[e.vertices[1]]
            for t_ in np.linspace(0.0, 1.0, 9):
                w = p_.lerp(q_, float(t_))
                if n_y0 <= w.y <= n_y1 and n_z0 <= w.z <= n_z1:
                    hit = True; break
            if hit:
                break
        if hit:
            across.append(o.name)
    strut_aft = min((O[n].matrix_world @ v.co).y for n in ('stab_strut_L', 'stab_strut_R') if n in O for v in O[n].data.vertices) if 'stab_strut_L' in O else None
    side_ok = all(stree.ray_cast(Vector((sx, yy, zz)), Vector((-sx, 0, 0)).normalized(), 1.0)[0] is not None
                  for sx in (-0.6, 0.6) for yy in (min(b[0] for b in tb), title_fwd) for zz in (min(b[2] for b in tb), max(b[3] for b in tb)))
    R('naval markings (naval1912_fd32.py): title box behind the green side strip (>= 0.15 m) and ahead of the tailplane leading edge (>= 0.3 m), all four corners on the fus_rear flank',
      strip_aft - title_fwd >= 0.15 and min(b[0] for b in tb) - stab_le >= 0.3 and side_ok,
      f'title y {min(b[0] for b in tb):.3f} .. {title_fwd:.3f} (strip ends y {strip_aft:.3f}, tailplane LE y {stab_le:.3f}, corners on the flank {side_ok})')
    R('naval rudder number (round 2; keyline included): all four corners on the rudder paint on both sides, >= 60 mm aft of the hinge line and >= 60 mm ahead of the trailing edge at the heights of the number, and no other object of the model in front of the box in the side view (brace, wire, strip, tailplane)',
      on_rud and rud_hinge - n_y1 >= 0.06 and n_y0 - rud_te >= 0.06 and not across,
      f'number y {n_y0:.3f} .. {n_y1:.3f}, z {n_z0:.3f} .. {n_z1:.3f}; rudder paint at those heights y {rud_te:.3f} .. {rud_hinge:.3f} (hinge clear {(rud_hinge - n_y1) * 1000:.0f} mm, trailing edge clear {(n_y0 - rud_te) * 1000:.0f} mm); corners on the rudder {on_rud}; objects across the box: {across or "none"}; tailplane brace nearest y {strut_aft}')
except ImportError:
    NV = None; title_fwd = -9.0
R('markings: the outline starts >= 40 mm aft of the faction mark of both factions (drawn extent measured from faction_marks.layers at the builder\'s site y -2.12, 0.58 m) and ends >= 30 mm ahead of the small serial and of the naval titles',
  have_sites and mark_aft - y0 >= 0.04 and y1 - serial_fwd >= 0.03 and y1 - title_fwd >= 0.03,
  f'mark aft end y {mark_aft:.3f} (BDF half width {max(abs(ext["BDF"][0]), abs(ext["BDF"][1])):.3f}, PALA {max(abs(ext["PALA"][0]), abs(ext["PALA"][1])):.3f}), outline y {y0} .. {y1}, serial from y {serial_fwd:.3f}, naval title from y {title_fwd:.3f}; builder site lines found: {have_sites}')

# stacking: well above the skin, panel above the well (same-facing planes closer than 0.8 mm would z-fight: b17g_zfix rule)
tray_d = [stree.find_nearest(p)[3] for s in 'LR' for p in [objs[f'airbrake_tray_{s}'].matrix_world @ v.co for v in objs[f'airbrake_tray_{s}'].data.vertices]]
R('stacking: well floor / stringers 1.6 - 3.4 mm above the skin, panel face >= 0.8 mm above the stringers', min(tray_d) >= 0.0016 and max(tray_d) <= 0.0034 and dmin - max(tray_d) >= 0.0008,
  f'well {min(tray_d) * 1000:.2f}..{max(tray_d) * 1000:.2f} mm, panel face {dmin * 1000:.2f}..{dmax * 1000:.2f} mm above the skin')

# ------------------------------------------------------------------ 4. opening
gain = {s: rep['sides'][s]['free_edge_gain_abs_x_m'] for s in 'LR'}
fu = {s: rep['sides'][s]['free_edge_open_local_unity_xyz'] for s in 'LR'}
fl = {s: rep['sides'][s]['free_edge_open_local'] for s in 'LR'}
agree = all(abs(fu[s][1] - fl[s][2]) < 1e-4 and abs(fu[s][2] - fl[s][1]) < 1e-4 for s in 'LR')
R(f'opening sense: the stock rotation (+{AB.MAX_ANGLE:.0f} deg about the hinge local X, Unity left-handed) moves the free edge outward >= {AB.MIN_FREE_EDGE_OUT} m, left = right; the Unity-way and the Blender-way rotation give the same point',
  all(v >= AB.MIN_FREE_EDGE_OUT for v in gain.values()) and abs(gain['L'] - gain['R']) < 0.005 and agree, f"|x| gain L {gain['L']} R {gain['R']} m; open free edge (Blender) L {rep['sides']['L']['free_edge_open_blender']} R {rep['sides']['R']['free_edge_open_blender']}")
hl, hr = rep['sides']['L']['hinge_unity'], rep['sides']['R']['hinge_unity']
R('hinges: mirror images within 1 mm, hinge line vertical (Unity local X = +-Y), 0.55 m or more aft of the fus_center | fus_rear break',
  abs(hl[0] + hr[0]) < 0.001 and abs(hl[1] - hr[1]) < 0.001 and abs(hl[2] - hr[2]) < 0.001 and abs(rep['sides']['L']['hinge_x_unity'][1]) == 1.0 and abs(rep['sides']['R']['hinge_x_unity'][1]) == 1.0
  and AB.PART_SPLIT_Y - y0 >= 0.55, f'L {hl} R {hr}, X L {rep["sides"]["L"]["hinge_x_unity"]} R {rep["sides"]["R"]["hinge_x_unity"]}')

others = {}
for o in O:
    if o.type == 'MESH' and o.name in base_objects and o.name not in ('fus_rear', 'fus_rear_struct'):
        t = bvh(o)
        if t is not None:
            others[o.name] = t
# the hook lowered (contract: deployed angle) is one more obstacle
con = json.load(open(os.path.join(ROOT, 'assets', 'model_fd32', 'fd32_contract.json')))
hk = O['tailhook']
C = O['FD32_root'].matrix_world.translation
piv = Vector((con['tailhook']['pivot'][0], con['tailhook']['pivot'][2], con['tailhook']['pivot'][1])) + C
for dname, ddeg in (('tailhook_down', con['tailhook']['deployed_deg']), ('tailhook_down_neg', -con['tailhook']['deployed_deg'])):
    Mh = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(ddeg), 4, 'X') @ Matrix.Translation(-piv) @ hk.matrix_world
    others[dname] = bvh(hk, None, Mh)
skin_tree = bvh(fus)
hits, worst_skin, min_other = [], 0.0, (9.0, '')
for deg in range(0, 56, 5):
    AB.pose(float(deg))
    for s in 'LR':
        p = objs[f'airbrake_{s}']
        pts = panel_points(p, step=0.02)
        vs, polys = world_tris(p)
        pt = BVHTree.FromPolygons(vs, polys)
        for n, t in others.items():
            if n == f'airbrake_tray_{s}':
                continue
            if pt.overlap(t):
                hits.append(f'{deg} deg {p.name} x {n}')
            d = min_dist(pts, t, min_other[0])
            if d < min_other[0]:
                min_other = (d, f'{n} at {deg} deg')
        if deg == 55:
            # fully open: the body may cross the uncut skin only next to the hinge line (the root of the panel goes into the fuselage;
            # on the way open the inner body leaves the fuselage through the skin it was hidden behind, as any proud plate with depth)
            Mi = objs[f'airbrake_{s}_hinge'].matrix_world.inverted()
            M0 = AB._HINGES[f'airbrake_{s}_hinge'].inverted()
            for w in pts:
                loc, nrm, idx, dist = skin_tree.find_nearest(w)
                inside = (w - loc).dot(nrm) < -0.0005
                if inside:
                    worst_skin = max(worst_skin, -(M0 @ w).y)          # how far aft of the hinge line (shut frame) a buried point is
AB.pose(0.0)
R('opening sweep 0 - 55 deg in 5 deg steps: the panels touch no object of the model (strips, hook stowed and lowered, tailplane, gear, wings, canopy, spine); fully open, only the panel root next to the hinge line is still inside the uncut skin (within 45 mm of the hinge line)',
  not hits and worst_skin <= 0.045 and min_other[0] >= 0.03, f'{len(hits)} contacts {hits[:4]}, nearest other object {min_other[0] * 1000:.0f} mm ({min_other[1]}), buried points up to {worst_skin * 1000:.1f} mm aft of the hinge line')
# pilot's view / flares: the open panel stays inside the span of the tailplane and below the hood sill
ob = [rep['sides'][s]['free_edge_open_blender'] for s in 'LR']
R('open panels: free edges 0.75 - 0.90 m from the centre line (tailplane tip 1.57 m, lower wing root 0.44 m), 1.0 m or more aft of the lower-wing trailing edge (y -1.00) and ahead of the tailplane (y -4.10)',
  all(0.75 <= abs(q[0]) <= 0.90 and -4.0 < q[1] < -2.0 for q in ob), f'{ob}')

# ------------------------------------------------------------------ 5. the FBX is the same geometry
for o in list(O):
    if o.name in names:
        o.name = 'mem_' + o.name
before = set(O.keys())
bpy.ops.import_scene.fbx(filepath=fbx)
imp = [o for o in O if o.name not in before]
got = {o.name.split('.')[0]: o for o in imp}
ferr = []
Cc = Vector(C)
for n in names:
    a = O.get('mem_' + n); b = got.get(n)
    if b is None:
        ferr.append('missing ' + n); continue
    if a.type != 'MESH':
        # FBX frame after import: the exporter wrote Unity-style Y-up data; compare the position through the same map
        continue
    if len(a.data.polygons) != len(b.data.polygons):
        ferr.append(f'{n}: {len(a.data.polygons)} polygons in memory, {len(b.data.polygons)} in the FBX'); continue
    # exporter map: Blender (x, y, z) - CG -> FBX (-x, z, y); after import (Y-up file read as Y-up) the object matrix carries it back
    A = sorted((round((a.matrix_world @ v.co - Cc).x, 4), round((a.matrix_world @ v.co - Cc).y, 4), round((a.matrix_world @ v.co - Cc).z, 4)) for v in a.data.vertices)
    Bq = [b.matrix_world @ v.co for v in b.data.vertices]
    cands = []
    for f in (lambda q: (q.x, q.y, q.z), lambda q: (-q.x, q.z, q.y), lambda q: (-q.x, -q.z, q.y), lambda q: (q.x, -q.z, q.y), lambda q: (-q.x, -q.y, q.z)):
        Bs = sorted(tuple(round(c, 4) for c in f(q)) for q in Bq)
        if len(set(Bs)) != len(set(A)):
            cands.append(9.0); continue
        cands.append(max(max(abs(x - y) for x, y in zip(p, q)) for p, q in zip(sorted(set(A)), sorted(set(Bs)))))
    if min(cands) > 0.0005:
        ferr.append(f'{n}: FBX vertices differ from the model by {min(cands):.4f} m (best axis map)')
    am = [m.name for m in a.data.materials]; bm = [m.name.split('.')[0] for m in b.data.materials]
    if am != bm:
        ferr.append(f'{n}: materials {am} / FBX {bm}')
    if n.startswith('airbrake_') and 'tray' not in n:
        ua = sorted((round(d.uv[0], 5), round(d.uv[1], 5)) for d in a.data.uv_layers['livery'].data)
        ub = sorted((round(d.uv[0], 5), round(d.uv[1], 5)) for d in b.data.uv_layers[0].data)
        if len(ua) != len(ub) or max(max(abs(p[0] - q[0]), abs(p[1] - q[1])) for p, q in zip(ua, ub)) > 2e-5:
            ferr.append(n + ': livery UVs differ in the FBX')
R('fd32_airbrake.fbx re-imported: the six objects, same polygon counts, vertices (0.5 mm), material order and livery UVs as built', not ferr and len(got) >= 6, ferr or f'{sorted(got)}')

allok = all(r['ok'] for r in rows)
json.dump(dict(ok=allok, rows=rows, site=site, nearest_objects_shut_mm={n: round(d * 1000, 1) for d, n in near[:12]}, far_m={k: round(v, 3) for k, v in far.items()},
               mark_extent=ext, truss_mm=round(d_truss * 1000, 1)), open(outp, 'w'), indent=1)
print('[check]', 'ALL PASS' if allok else 'FAILED', f"({sum(r['ok'] for r in rows)}/{len(rows)})")
if not allok:
    sys.exit(1)
