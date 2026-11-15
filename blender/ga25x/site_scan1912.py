r"""1.9.12 round 2: where on the GA-25X rear fuselage can an airbrake panel stand clear of the faction mark? Read-only measurement.

  blender --background assets/model_ga25x/ga25x.blend --python blender/ga25x/site_scan1912.py -- <textures_dir> <out.json>

Measured on the shipped model and the shipped livery textures (nothing is written but the json):
  1 the faction mark of EVERY livery on both flanks: the fus_rear / fus_tail paint faces are sampled every ~12 mm, each sample looks up
    its texel in the livery; a sample is "mark" when its colour is one the camouflage of no livery has (PALA: the red of the roundel,
    BDF: the blue of the badge) -> box of the mark colour in (y, z) per livery and side, compared with the composer's box
    (compose_liveries_ga25x.py: centre y -4.9, z = section centre, BDF 1.30 x 0.76, PALA 0.98 x 1.00);
  2 everything else on or near the rear fuselage (objects with a box inside |x| < 1.2, y -7.4 .. -2.3);
  3 the candidate sites: developed skin area per side, what each one hits, and the mark-colour samples under it in every livery.
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airbrake1912 as AB

argv = sys.argv[sys.argv.index('--') + 1:]
tdir, out = os.path.abspath(argv[0]), os.path.abspath(argv[1])
O = bpy.data.objects
STEP = 0.012
FIRST_AREA = 1.4939          # the first build's flank panel, m2 per side (ga25x_airbrake.json of that build)


def paint_tris(name):
    ob = O[name]
    me = ob.data
    M = ob.matrix_world
    N3 = M.to_3x3()
    pi = {i for i, m in enumerate(me.materials) if m is not None and m.name == 'paint'}
    uv = me.uv_layers['livery'].data
    tris = []
    for p in me.polygons:
        if p.material_index not in pi:
            continue
        c = M @ p.center
        n = (N3 @ p.normal).normalized()
        if not (-7.4 < c.y < -2.3) or n.x * c.x + n.z * (c.z - 0.30) < 0.2 * math.hypot(c.x, c.z - 0.30):
            continue
        pts = [(tuple(M @ me.vertices[me.loops[li].vertex_index].co), tuple(uv[li].uv)) for li in p.loop_indices]
        for k in range(1, len(pts) - 1):
            tris.append((pts[0], pts[k], pts[k + 1]))
    return tris


TRIS = {n: paint_tris(n) for n in ('fus_rear', 'fus_tail')}
ALL = TRIS['fus_rear'] + TRIS['fus_tail']
# samples: position + uv
P, U = [], []
for (a, ua), (b, ub), (c, uc) in ALL:
    a3, b3, c3 = np.array(a), np.array(b), np.array(c)
    n = max(2, int(max(np.linalg.norm(b3 - a3), np.linalg.norm(c3 - a3), np.linalg.norm(c3 - b3)) / STEP) + 1)
    for i in range(n + 1):
        for j in range(n + 1 - i):
            u, v = i / n, j / n
            w = 1 - u - v
            P.append(w * a3 + u * b3 + v * c3)
            U.append(w * np.array(ua) + u * np.array(ub) + v * np.array(uc))
P, U = np.array(P), np.array(U)
print(f'[site] {len(ALL)} outer paint triangles on fus_rear + fus_tail, {len(P)} samples')

meta = json.load(open(os.path.join(tdir, 'ga25x_liveries.json')))
rep = dict(marks={}, obstacles={}, sites={}, composer=AB.MARKS, first_area_m2=FIRST_AREA)
MARKCOL = {}
for key, e in meta.items():
    img = bpy.data.images.load(os.path.join(tdir, e['texture']), check_existing=True)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = (px.reshape(h, w, 4)[:, :, :3] * 255.0)
    ix = np.clip((U[:, 0] * w).astype(int), 0, w - 1)
    iy = np.clip((U[:, 1] * h).astype(int), 0, h - 1)
    col = px[iy, ix]
    r, g, b = col[:, 0], col[:, 1], col[:, 2]
    if e['faction'] == 'PALA':
        m = (r > 120) & (g < 0.45 * r) & (b < 0.45 * r)            # roundel red
    else:
        m = (b > 110) & (b > r + 45) & (b > g + 10)                # badge blue
    MARKCOL[key] = m
    d = dict(faction=e['faction'], samples=int(m.sum()))
    for S, side in (('L', -1), ('R', 1)):
        sel = m & (P[:, 0] * side > 0)
        if sel.any():
            q = P[sel]
            d[S] = dict(y=[round(float(q[:, 1].max()), 3), round(float(q[:, 1].min()), 3)], z=[round(float(q[:, 2].min()), 3), round(float(q[:, 2].max()), 3)], n=int(sel.sum()))
    mw, mh = AB.MARKS[e['faction']]
    d['composer_box'] = dict(y=[AB.MARKS['y'] + mw / 2, AB.MARKS['y'] - mw / 2], z=[AB.MARKS['z'] - mh / 2, AB.MARKS['z'] + mh / 2])
    rep['marks'][key] = d
    print('[site] mark', key, d)
    bpy.data.images.remove(img)

for o in O:
    if o.type not in ('MESH', 'EMPTY') or o.name in ('GA25X_root', 'fus_rear', 'fus_tail'):
        continue
    wm = o.matrix_world
    pts = [wm @ Vector(bb) for bb in o.bound_box] if o.type == 'MESH' else [wm.translation]
    lo = [min(p[k] for p in pts) for k in range(3)]; hi = [max(p[k] for p in pts) for k in range(3)]
    if hi[1] > -7.4 and lo[1] < -2.3 and lo[0] < 1.2 and hi[0] > -1.2:
        rep['obstacles'][o.name] = dict(lo=[round(a, 3) for a in lo], hi=[round(a, 3) for a in hi], parent=o.parent.name if o.parent else None, type=o.type,
                                        coll=o.users_collection[0].name if o.users_collection else None)
for k, v in sorted(rep['obstacles'].items()):
    print('[site] near', k, v)


def patch(planes, tris):
    polys, _ = AB.skin_patch(tris, planes)
    return sum(AB.poly_area([q[0] for q in p]) for p in polys), polys


def in_planes(planes):
    m = np.ones(len(P), bool)
    for n, d, _ in planes:
        m &= (P @ np.array(n) >= d - 1e-9)
    return m


def cand(name, planes_R, part, note):
    """planes for the RIGHT side; the left is the mirror image"""
    area, polys = patch(planes_R, TRIS[part])
    hit = {k: int((MARKCOL[k] & in_planes(planes_R)).sum()) for k in MARKCOL}
    box = {}
    for k, d in rep['marks'].items():
        cb = d['composer_box']
        # does the composer's mark box (flank, y-z) overlap the y-z shadow of the patch?
        pts = [q[0] for p in polys for q in p]
        if pts:
            ys = [q[1] for q in pts]; zs = [q[2] for q in pts]
            box[k] = not (min(ys) > cb['y'][0] or max(ys) < cb['y'][1] or min(zs) > cb['z'][1] or max(zs) < cb['z'][0])
    rep['sites'][name] = dict(area_m2=round(area, 4), share_of_first=round(area / FIRST_AREA, 3), mark_colour_samples=hit, composer_box_overlap=box, part=part, note=note)
    print(f'[site] {name}: {area:.3f} m2 per side = {100 * area / FIRST_AREA:.0f} % of the first panel; mark-colour samples under it {hit}; overlaps a composer mark box {box}; {note}')


def flank(y0, y1, z0, z1):
    return [AB.ax(1, y0, False), AB.ax(1, y1, True), AB.ax(2, z0, True), AB.ax(2, z1, False), AB.ax(0, 0.45, True)]


def shoulder(y0, y1, z_lo, x_in):
    return AB.region(dict(y_hinge=y0, y_aft=y1, z_lo=z_lo, x_in=x_in), 1)


cand('A first build: flank, on the mark', flank(-4.20, -5.62, -0.29, 0.76), 'fus_rear', 'the mark rides out on the panel')
cand('B flank ahead of the mark (between the sensor pad end -3.95 and the BDF mark front -4.25, 20 mm clear each)', flank(-3.97, -4.23, -0.29, 0.76), 'fus_rear', 'only 0.26 m long')
cand('C flank behind the mark (BDF mark aft -5.55 .. 0.20 m ahead of the fus_rear break -6.10)', flank(-5.57, -5.90, -0.29, 0.76), 'fus_rear', 'only 0.33 m long')
cand('D flank below the mark (PALA bottom -0.26; the side ends where the belly radius starts, z about -0.44)', flank(-4.20, -5.62, -0.44, -0.28), 'fus_rear', 'a 0.16 m strip')
cand('E flank on fus_tail, ahead of the stabiliser root (0.20 m behind the break .. 0.10 m ahead of the stabiliser leading edge -6.885)', flank(-6.30, -6.78, -0.20, 0.66), 'fus_tail',
     'other part (fus_tail); opens under the stabiliser')
cand('B + C + E together (three small panels per side)', flank(-3.97, -4.23, -0.29, 0.76), 'fus_rear', 'see B, C, E: sum below')
cand('F shoulder, 60 mm above the tallest mark to 50 mm from the centre line, y -4.20 .. -5.80 (BUILT)', shoulder(AB.SITE['y_hinge'], AB.SITE['y_aft'], AB.SITE['z_lo'], AB.SITE['x_in']), 'fus_rear',
     'stock FS-12 / T-A-30 layout')
cand('G one dorsal saddle over both shoulders (both halves of F and the 0.10 m between them)', shoulder(-4.20, -5.80, 0.80, 0.0), 'fus_rear', 'per side = half the saddle; front edge sagitta about 0.4 m')
cand('H shoulder further forward (y -2.60 .. -4.20, over the wing trailing edge and the sensor pads)', shoulder(-2.60, -4.20, 0.86, 0.05), 'fus_rear', 'hidden over the wing from the chase view; 0.2 m behind the wing fillet')
s = rep['sites']
tot = sum(s[k]['area_m2'] for k in s if k[0] in 'BCE' and '+' not in k)
s['B + C + E together (three small panels per side)'].update(area_m2=round(tot, 4), share_of_first=round(tot / FIRST_AREA, 3))
print(f'[site] B + C + E together: {tot:.3f} m2 per side = {100 * tot / FIRST_AREA:.0f} % of the first panel')
# clearances of the built site
st = AB.SITE
top = {k: max((d.get(S, {}).get('z', [0, -9])[1] for S in 'LR'), default=None) for k, d in rep['marks'].items()}
rep['built'] = dict(site=st, mark_colour_top_z=top, composer_top_z={k: d['composer_box']['z'][1] for k, d in rep['marks'].items()},
                    lower_edge_above_tallest_mark_m=round(st['z_lo'] - max(d['composer_box']['z'][1] for d in rep['marks'].values()), 3))
print('[site] built site', rep['built'])
json.dump(rep, open(out, 'w'), indent=1)
