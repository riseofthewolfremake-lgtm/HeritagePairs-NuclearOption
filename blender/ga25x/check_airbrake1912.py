"""1.9.12 offline check of the GA-25X airbrake add-on: the two FBX files exactly as Unity gets them, re-imported side by side.

  blender --background --factory-startup --python blender/ga25x/check_airbrake1912.py -- <ga25x.fbx> <ga25x_airbrake.fbx> <ga25x_airbrake.json> <out.json>

Rows (all measured on the re-imported meshes; frame = the Blender frame with the CG at the origin):
  objects / hierarchy / materials, no paint on the tray, triangle counts
  shut: every paint vertex and paint face centre of a panel is 3-5 mm outside the fus_rear skin (no poke-through either way)
  paint texels: the livery UV of every panel paint vertex == the UV of the skin point under it (<= 0.5 texel of the 4096 atlas);
                the skin quads under the panel give the same UV on either diagonal (Unity may triangulate them the other way)
  hinge frame: Unity local X = hinge line (square to the long axis, tilted over the shoulder), Y = outward, Z = forward; the two marker
               empties sit 1 m along X and Y (GA25XBuild.cs builds the frame from the three positions); +55 deg about local X (the stock
               Airbrake call) moves the free edge away from the long axis by >= 0.2 m, the same left and right
  well: floor and stringers above the skin and under the shut panel's face (never the outermost surface when shut)
  open sweep 0..55 deg: the panel meets nothing of the model except fus_rear within 60 mm of the hinge line (its inner box, inside)
  belly laser: at every opening angle the whole panel is above the laser's elevation axis; the lowest sight line from the laser to a
               panel is far above the highest beam (turret limit -2 deg + 1 deg beam freedom); rays at <= +1 deg from the aperture orbit
               hit nothing
  site: clear of the sensor pads, flare ejectors, rear hatch, flaps, stabiliser and the fus_rear break; the panel's lower edge is above the
        faction mark boxes of both factions (the texel test on every livery is site_scan1912.py)
"Outside the skin" is measured radially from the fuselage axis (Blender z 0.30), so the rows hold on the flank and on the shoulder.
"""
import bpy, sys, os, json, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airbrake1912 as AB

argv = sys.argv[sys.argv.index('--') + 1:]
fbx, abfbx, abjson, out = [os.path.abspath(a) for a in argv[:4]]
rep = json.load(open(abjson))
bpy.ops.wm.read_factory_settings(use_empty=True)
for f in (fbx, abfbx):
    bpy.ops.import_scene.fbx(filepath=f, use_manual_orientation=True, axis_forward='Y', axis_up='Z', global_scale=1.0)
bpy.context.view_layer.update()
O = bpy.data.objects
rows = []
# The import leaves the data in the file's own space (the exporter wrote Blender (x, y, z) as (-x, z, y), object matrices conjugated).
# CONV turns it back into the Blender frame (it is its own inverse); the origin stays the CG.
CONV = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def W(o):
    return CONV @ o.matrix_world @ CONV


def P(o):            # world position of an object origin, Blender frame
    return CONV @ o.matrix_world.translation


def R(name, ok, detail=''):
    rows.append(dict(name=name, ok=bool(ok), detail=str(detail)))
    print(('PASS  ' if ok else 'FAIL  ') + name + '  ' + str(detail))


def base(n):
    i = n.rfind('.')
    return n[:i] if i > 0 and n[i + 1:].isdigit() else n


by = {}
for o in O:
    by.setdefault(base(o.name), []).append(o)
MARKERS = ['airbrake_L_axis', 'airbrake_L_out', 'airbrake_R_axis', 'airbrake_R_out']
NAMES = ['airbrake_L_hinge', 'airbrake_R_hinge', 'airbrake_L', 'airbrake_R', 'airbrake_tray_L', 'airbrake_tray_R'] + MARKERS
miss = [n for n in NAMES if n not in by]
R('add-on FBX: two hinges, two panels, two trays, four frame markers', not miss and all(len(by[n]) == 1 for n in NAMES), miss or 'ten objects')
if miss:
    json.dump(dict(ok=False, rows=rows), open(out, 'w'), indent=1)
    sys.exit(1)
ob = {n: by[n][0] for n in NAMES}
fr = [o for o in by['fus_rear'] if o.type == 'MESH'][0]
ab_root = ob['airbrake_L_hinge'].parent


def mats(o):
    return [base(m.name) for m in o.data.materials]


def faces(o, mat=None, world=None):
    me = o.data
    M = (world @ CONV) if world is not None else (CONV @ o.matrix_world)      # mesh data is in file space: W_blender @ CONV = CONV @ W_file
    names = mats(o)
    uv = me.uv_layers[0].data if me.uv_layers else None
    res = []
    for p in me.polygons:
        if mat is not None and names[p.material_index] != mat:
            continue
        res.append(([M @ me.vertices[v].co for v in p.vertices], [tuple(uv[li].uv) for li in p.loop_indices] if uv else None, names[p.material_index]))
    return res


def bvh(fs):
    verts, polys = [], []
    for vs, _, _ in fs:
        polys.append(list(range(len(verts), len(verts) + len(vs))))
        verts += [tuple(v) for v in vs]
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0)


R('hierarchy: panel under its hinge; hinges, trays and markers on the add-on root (Unity re-parents hinges and trays under fus_rear and drops the markers)',
  all(ob[f'airbrake_{S}'].parent == ob[f'airbrake_{S}_hinge'] for S in 'LR') and ab_root is not None and base(ab_root.name) == 'GA25X_root'
  and all(ob[n].parent == ab_root for n in ['airbrake_R_hinge', 'airbrake_tray_L', 'airbrake_tray_R'] + MARKERS) and all(ob[n].type == 'EMPTY' for n in MARKERS),
  ', '.join(f"{n} <- {base(ob[n].parent.name) if ob[n].parent else None}" for n in NAMES))
R('materials: panel [paint first, cockpit (dark inner face), structure (frames / stringers), metal_dark (seam, rim, hinge arms)], well [cockpit floor, structure stringers] without paint; UV layers livery + detail',
  all(mats(ob[f'airbrake_{S}'])[0] == 'paint' and set(mats(ob[f'airbrake_{S}'])) == {'paint', AB.MAT_FACE, AB.MAT_RIB, AB.MAT_ARM} for S in 'LR')
  and all(set(mats(ob[f'airbrake_tray_{S}'])) == {AB.MAT_FACE, AB.MAT_RIB} for S in 'LR')
  and all([l.name for l in ob[n].data.uv_layers] == ['livery', 'detail'] for n in NAMES if ob[n].type == 'MESH'),
  ' | '.join(f"{n} {mats(ob[n])}" for n in NAMES if ob[n].type == 'MESH'))
tri = {n: sum(len(p.vertices) - 2 for p in ob[n].data.polygons) for n in NAMES if ob[n].type == 'MESH'}
R(f'triangles: each panel <= {AB.TRI_PANEL_MAX}, each well <= {AB.TRI_TRAY_MAX} (stock panels 120-474; ours follow the skin facets of the curved shoulder on the outer face, the inner face and every frame / stringer)',
  all(tri[f'airbrake_{S}'] <= AB.TRI_PANEL_MAX and tri[f'airbrake_tray_{S}'] <= AB.TRI_TRAY_MAX for S in 'LR'), tri)
# inner finish: how much of the inner face / the well is dark (by area), and that the members stand out in relief
fin = {}
for S in 'LR':
    a = {}
    for vs, _, m in faces(ob[f'airbrake_{S}']):
        a[m] = a.get(m, 0.0) + AB.poly_area([tuple(v) for v in vs])
    t = {}
    for vs, _, m in faces(ob[f'airbrake_tray_{S}']):
        t[m] = t.get(m, 0.0) + AB.poly_area([tuple(v) for v in vs])
    fin[S] = dict(inner_dark=round(a[AB.MAT_FACE], 3), inner_light=round(a[AB.MAT_RIB], 3), well_dark=round(t[AB.MAT_FACE], 3), well_light=round(t[AB.MAT_RIB], 3))
panel_area = {S: rep['sides'][S]['area_m2'] for S in 'LR'}
R('inner finish: the inner face is the dark `cockpit` finish over the whole panel (>= 93 % of the outer area: it lies 22 mm inside a convex skin); the light `structure` members, tops and side walls together, are 15-75 % of the panel area (about 30 % seen square-on); the well floor is dark, its light stringers <= 25 % of the floor',
  all(fin[S]['inner_dark'] >= 0.93 * panel_area[S] and 0.15 * panel_area[S] <= fin[S]['inner_light'] <= 0.75 * panel_area[S] and fin[S]['well_dark'] >= 0.9 * panel_area[S]
      and 0 < fin[S]['well_light'] <= 0.25 * fin[S]['well_dark'] for S in 'LR'), f'{fin} m2; panel area {panel_area}')

# ---- skin under the panels
skin = faces(fr, 'paint')
skin_tris = []
for vs, uvs, _ in skin:
    for k in range(1, len(vs) - 1):
        skin_tris.append(((vs[0], vs[k], vs[k + 1]), (uvs[0], uvs[k], uvs[k + 1])))
tri_bvh = BVHTree.FromPolygons([tuple(v) for t in skin_tris for v in t[0]], [[3 * i, 3 * i + 1, 3 * i + 2] for i in range(len(skin_tris))], epsilon=0.0)


def bary_uv(p, i):
    (a, b, c), (ua, ub, uc) = skin_tris[i]
    v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
    den = d00 * d11 - d01 * d01
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    u = 1 - v - w
    return (u * ua[0] + v * ub[0] + w * uc[0], u * ua[1] + v * ub[1] + w * uc[1])


s = rep['site']
cg = Vector(rep['cg_blender'])
AXIS_Z = 0.30 - cg.z          # the fuselage axis in the check frame (CG at the origin)


def outside(v, loc):
    """is v outside the skin point loc, seen from the fuselage axis"""
    return (v - loc).x * loc.x + (v - loc).z * (loc.z - AXIS_Z) > 0
quad_dev, quads = 0.0, 0
for vs, uvs, _ in skin:
    c = sum(vs, Vector()) / len(vs) + cg
    if len(vs) == 4 and s['y_aft'] < c.y < s['y_hinge'] and c.z > s['z_lo'] and abs(c.x) > s['x_in']:
        quads += 1
        quad_dev = max(quad_dev, 4096 * max(abs((uvs[0][k] + uvs[2][k]) / 2 - (uvs[1][k] + uvs[3][k]) / 2) for k in range(2)))
out_d, uv_err, n_pts = [], 0.0, 0
uv_box = {}
for S in 'LR':
    p = ob[f'airbrake_{S}']
    side = -1 if S == 'L' else 1
    for vs, uvs, _ in faces(p, 'paint'):
        pts = list(zip(vs, uvs)) + [(sum(vs, Vector()) / len(vs), None)]
        for v, u in pts:
            loc, nrm, idx, dist = tri_bvh.find_nearest(v)
            out_d.append(dist * (1 if outside(v, loc) else -1) * 1000)
            if u is not None:
                su = bary_uv(loc, idx)
                uv_err = max(uv_err, 4096 * max(abs(su[0] - u[0]), abs(su[1] - u[1])))
                n_pts += 1
                b = uv_box.setdefault(S, [1, 1, 0, 0])
                b[0], b[1], b[2], b[3] = min(b[0], u[0]), min(b[1], u[1]), max(b[2], u[0]), max(b[3], u[1])
seam = {}
for S in 'LR':
    side = -1 if S == 'L' else 1
    # outer face = the faces 3 mm or more outside the skin; the band is measured along the outline's own axes (y, y, z, |x|)
    box, pbox = [1e9, 1e9, 1e9, -1e9], [1e9, 1e9, 1e9, -1e9]            # min |x|, min z, min y, max y
    for vs, _, m in faces(ob[f'airbrake_{S}']):
        if m not in ('paint', AB.MAT_ARM):
            continue
        c = sum(vs, Vector()) / len(vs)
        loc, nrm, idx, dist = tri_bvh.find_nearest(c)
        if not (outside(c, loc) and dist > 0.003):
            continue
        for v in vs:
            b = pbox if m == 'paint' else box
            w = v + cg
            b[0], b[1], b[2], b[3] = min(b[0], abs(w.x)), min(b[1], w.z), min(b[2], w.y), max(b[3], w.y)
    seam[S] = [round((box[3] - pbox[3]) * 1000, 1), round((pbox[2] - box[2]) * 1000, 1), round((pbox[1] - box[1]) * 1000, 1), round((pbox[0] - box[0]) * 1000, 1)]
R('shut: a dark seam band 5-9 mm wide runs round the paint face on all four edges: hinge, aft, lower, upper (the closed panel reads as a panel)', all(5.0 <= v <= 9.0 for S in 'LR' for v in seam[S]), seam)
R('shut: panel paint face 3-5 mm outside the fus_rear skin at every vertex and face centre (no poke-through)', out_d and min(out_d) >= 3.0 and max(out_d) <= 5.0,
  f'{len(out_d)} samples, {min(out_d):.2f}..{max(out_d):.2f} mm')
R('paint texels: panel livery UV == UV of the skin point under each paint vertex (<= 0.5 texel of 4096); skin quads give the same UV on either diagonal within 1 texel (4.65 mm)',
  n_pts > 0 and uv_err <= 0.5 and quad_dev <= 1.0,
  f'{n_pts} loop UVs, max {uv_err:.3f} texel; {quads} skin quads, diagonal difference max {quad_dev:.3f} texel; UV boxes {({k: [round(a, 4) for a in v] for k, v in uv_box.items()})}')

# ---- hinge frames and opening
sym, free_out = [], {}


def rad(v):          # distance from the aircraft's long axis through the CG (what GA25XBuild.cs measures)
    return math.hypot(v.x, v.z)


for S in 'LR':
    side = -1 if S == 'L' else 1
    h = ob[f'airbrake_{S}_hinge']
    M = W(h)
    x, y, z = [M.to_3x3().col[k].normalized() for k in range(3)]
    st = rep['sides'][S]
    o = M.translation
    out_dir = Vector((o.x, 0.0, o.z - AXIS_Z)).normalized()
    okf = abs(x.y) < 1e-4 and z.dot(out_dir) > 0.9 and y.y > 0.99 and abs(x.cross(y).dot(z) - 1) < 1e-4 and x.z * side < 0
    # the markers GA25XBuild.cs reads: 1 m along the hinge line / the outward normal
    mx, mz = P(ob[f'airbrake_{S}_axis']) - o, P(ob[f'airbrake_{S}_out']) - o
    okm = (mx - x).length < 1e-4 and (mz - z).length < 1e-4
    # Unity hinge-local (X, Y, Z) = Blender-local (x, z, y); then the stock Rotate(+a about X)
    fl = Vector(st['free_edge_local'])
    fu = AB.unity_rotate_x((fl.x, fl.z, fl.y), AB.MAX_ANGLE)
    fo = M @ Vector((fu[0], fu[2], fu[1]))
    fc = M @ fl
    free_out[S] = rad(fo) - rad(fc)
    sym.append((round(abs(fo.x), 4), round(fo.y, 4), round(fo.z, 4)))
    pos_ok = (o + cg - Vector(st['hinge_blender'])).length < 1e-3
    # the front edge of the panel straddles the hinge line: the same height above and below it
    pl = [M.inverted() @ v for vs, _, m in faces(ob[f'airbrake_{S}'], 'paint') for v in vs]
    fz = [q.z for q in pl if q.y > -AB.SEAM - 0.015]
    strad = abs(max(fz) + min(fz) - 2 * AB.PROUD) < 0.012
    R(f'hinge {S}: Unity X = hinge line (square to the long axis, tilted {st["hinge_tilt_deg"]} deg over the shoulder, up-and-inboard on the left / the opposite on the right), Y = outward, Z = forward, right-handed; markers 1 m along X and Y; the curved front edge straddles the hinge line',
      okf and okm and pos_ok and strad,
      f'pos {tuple(round(a, 4) for a in o)} x {tuple(round(a, 3) for a in x)} fwd {tuple(round(a, 3) for a in y)} out {tuple(round(a, 3) for a in z)}; markers off by {(mx - x).length * 1000:.3f} / {(mz - z).length * 1000:.3f} mm; front edge {min(fz) * 1000:.1f}..{max(fz) * 1000:.1f} mm from the hinge line')
R('stock Airbrake rotation (+55 deg about hinge-local X) moves the free edge away from the long axis by >= 0.2 m, left = right', all(v >= 0.2 for v in free_out.values()) and sym[0] == sym[1],
  f'outward {({k: round(v, 3) for k, v in free_out.items()})} m; free edge open at |x|, y, z {sym[0]} (CG frame)')

# ---- well
for S in 'LR':
    d = {}
    for vs, _, m in faces(ob[f'airbrake_tray_{S}']):
        for v in vs:
            loc, nrm, idx, dist = tri_bvh.find_nearest(v)
            d.setdefault(m, []).append(dist * (1 if outside(v, loc) else -1) * 1000)
    fl_, st_ = d[AB.MAT_FACE], d[AB.MAT_RIB]
    okw = min(fl_) >= 1.5 and max(st_) <= AB.PROUD * 1000 - 0.8 and min(st_) - max(fl_) >= 0.8
    R(f'well {S}: floor >= 1.5 mm above the skin, stringers >= 0.8 mm above the floor and >= 0.8 mm under the shut panel face', okw,
      f"floor {min(fl_):.2f}..{max(fl_):.2f} mm, stringers {min(st_):.2f}..{max(st_):.2f} mm, panel face {AB.PROUD * 1000:.1f} mm")

# ---- open sweep against the rest of the model
others = [o for o in O if o.type == 'MESH' and base(o.name) not in NAMES]
other_bvh = {}
for o in others:
    ys = [(CONV @ o.matrix_world @ Vector(b)).y for b in o.bound_box]
    if min(ys) < -1.0 and len(o.data.polygons) > 0:
        other_bvh[base(o.name)] = bvh(faces(o))
rest = {S: W(ob[f'airbrake_{S}_hinge']) for S in 'LR'}
hits, deep, ahead = {}, 0.0, 0.0
zmin_panel = 1e9
laser_axis = P(by['laser_turret_el'][0])
muzzle = P(by['muzzle_laser'][0])
r_muz = math.hypot(muzzle.x - laser_axis.x, muzzle.y - laser_axis.y)
min_el = 1e9
ray_hits, rays = 0, 0
for deg in range(0, int(AB.MAX_ANGLE) + 1, 5):
    for S in 'LR':
        Mw = rest[S] @ Matrix.Rotation(math.radians(-deg), 4, 'X')
        Mi = Mw.inverted()
        pf = faces(ob[f'airbrake_{S}'], world=Mw)
        pb = bvh(pf)
        for n, b in other_bvh.items():
            ov = pb.overlap(b)
            if not ov:
                continue
            if n != 'fus_rear':
                hits.setdefault(n, set()).add(deg)
        # sample points of the posed panel (vertices, edge mid points, face centres) against the skin
        side = -1 if S == 'L' else 1
        Ri = rest[S].inverted()
        for vs, _, _ in pf:
            smp = list(vs) + [(vs[k] + vs[(k + 1) % len(vs)]) / 2 for k in range(len(vs))] + [sum(vs, Vector()) / len(vs)]
            for v in smp:
                loc, nrm, idx, dist = tri_bvh.find_nearest(v)
                if dist is None or dist < 2e-4:
                    continue
                outs = outside(v, loc)
                yl = (Ri @ v).y                      # along the skin from the hinge line (rest frame): > 0 = ahead of the hinge
                if outs and yl > 0:
                    ahead = max(ahead, yl)
                if not outs and deg == int(AB.MAX_ANGLE):
                    deep = max(deep, -yl)
        for vs, _, _ in pf:
            for v in vs:
                zmin_panel = min(zmin_panel, v.z)
                dxy = math.hypot(v.x - laser_axis.x, v.y - laser_axis.y)
                min_el = min(min_el, math.degrees(math.atan2(v.z - max(laser_axis.z, muzzle.z), dxy + r_muz)))
        if deg in (0, 25, 55):
            for az in range(0, 360, 2):
                ca, sa = math.cos(math.radians(az)), math.sin(math.radians(az))
                o = Vector((laser_axis.x + sa * r_muz, laser_axis.y + ca * r_muz, muzzle.z))
                for e in (1.0, -2.0, -10.0, -30.0):
                    ce, se = math.cos(math.radians(e)), math.sin(math.radians(e))
                    rays += 1
                    if pb.ray_cast(o, Vector((sa * ce, ca * ce, se)), 45.0)[0] is not None:
                        ray_hits += 1
R('open sweep 0..55 deg: the panels touch no other object of the model (flaps, stabiliser, fins, hatch, hook, turret, sensor pads)', not hits,
  {k: sorted(v) for k, v in hits.items()} or f'{len(other_bvh)} objects tested at 12 angles')
R(f'open sweep: the curved front lip rides over the fixed skin ahead of the straight hinge line by at most {AB.AHEAD_MAX * 1000:.0f} mm; fully open, the part of the panel still inside the fuselage (the middle of the front edge and the frames behind it) ends within {AB.DEEP_MAX * 1000:.0f} mm of the hinge line',
  ahead <= AB.AHEAD_MAX and deep <= AB.DEEP_MAX, f'ahead of the hinge line {ahead * 1000:.1f} mm; fully open: inside the fuselage up to {deep * 1000:.0f} mm aft of the hinge line')
R('belly laser: whole panel above the laser at every opening angle; lowest sight line laser -> panel >= 10 deg above the laser horizon (turret limit -2 deg, beam +-1 deg); rays at +1 / -2 / -10 / -30 deg, every 2 deg of traverse, hit nothing',
  zmin_panel - max(laser_axis.z, muzzle.z) > 0.5 and min_el >= 10.0 and ray_hits == 0 and rays > 0,
  f'panel lowest z {zmin_panel:.3f}, laser axis z {laser_axis.z:.3f}, muzzle z {muzzle.z:.3f}, lowest elevation {min_el:.1f} deg, {rays} rays, hits {ray_hits}')

# ---- site


def wb(name):
    o = by[name][0]
    pts = [CONV @ o.matrix_world @ Vector(b) + cg for b in o.bound_box] if o.type == 'MESH' else [P(o) + cg]
    return [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]


site_bad = []
for n in ('flare_L', 'flare_R'):
    lo, hi = wb(n)
    if lo[2] > s['z_lo'] - 0.3:
        site_bad.append(n)
lo, hi = wb('hatch_entry_rear')
if hi[2] > s['z_lo'] - 0.3:
    site_bad.append('hatch_entry_rear')
for n in ('flap_inner_L', 'flap_inner_R', 'stab_L', 'stab_R'):
    lo, hi = wb(n)
    if not (lo[1] > s['y_hinge'] + 0.5 or hi[1] < s['y_aft'] - 0.5):
        site_bad.append(n)
if s['y_hinge'] > -3.95 - 0.20 + 1e-9:
    site_bad.append('sensor pad (ends y -3.95)')
if s['y_aft'] < -6.10 + 0.30 - 1e-9:
    site_bad.append('fus_rear / fus_tail break (y -6.10, tear 0.06 + ribs 0.10)')
if s['x_in'] < 0.03:
    site_bad.append('centre line')
R('site: >= 0.2 m behind the sensor pads, >= 0.3 m ahead of the fus_rear break, >= 0.3 m above the flare ejectors and the rear hatch, 0.5 m from flaps and stabiliser along the fuselage, 30 mm or more from the centre line',
  not site_bad, site_bad or s)
mk = AB.MARKS
clear = {k: round(s['z_lo'] - (mk['z'] + mk[k][1] / 2), 3) for k in ('BDF', 'PALA')}
R(f'faction marks (BDF 1.30 x 0.76, PALA 0.98 x 1.00 at y -4.9, z 0.24): the lower panel edge is >= {AB.MARK_CLEAR * 1000:.0f} mm above the top of each mark box, so the mark stays on the fixed skin when the panel opens',
  all(v >= AB.MARK_CLEAR - 1e-9 for v in clear.values()), f'lower edge z {s["z_lo"]}: above the mark box by {clear} m')

ok = all(r['ok'] for r in rows)
json.dump(dict(ok=ok, rows=rows, tris=tri), open(out, 'w'), indent=1)
print(f'[airbrake check] {sum(r["ok"] for r in rows)}/{len(rows)} ' + ('ALL PASS' if ok else 'FAILURES'))
sys.exit(0 if ok else 1)
