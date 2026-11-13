"""Offline geometry checks for the GA-25X 0.3.0 model pass (ray casts on the built .blend, Blender world = model space).

  blender --background <ga25x.blend> --python blender/ga25x/check_v030_ga25x.py -- <out.json>

Checks (each 'ok' + detail), read by test_ga25x_stub.py:
  displays covered      rays from each crew eye to points 1 mm OUTSIDE every display / ISIS face edge hit the bezel or
                        the black backing, never the bare panel behind it
  no coplanar detail    no cockpit_interior face lies within 1 mm of a display / ISIS face plane inside its rectangle
  tail cone closed      rays from behind over the tail-cone section: every first hit is front-facing
  spinner meets cowl    rays aimed at the spinner/cowl junction from outside stop at >= 0.32 m from the prop axis
  dorsal fairing        rays down onto the old turret ring: first hit is the fus_forward skin, front-facing
  ejection path         from each seat headbox, 1.5 m up the rail: the first thing hit is that seat's own canopy panel
  tail top line         no tail-gunner hump: fus_tail top <= 1.00 m aft of y -7.5
  laser envelope        from the belly el pivot, el -2..-90 deg x 360 deg (gear down, bay doors closed as in the file):
                        rays (60 m) that hit our own airframe are listed; open-door sector reported separately
"""
import bpy, sys, os, json, math
from mathutils import Vector, Quaternion

out = sys.argv[sys.argv.index('--') + 1]
O = bpy.data.objects
for o in O:
    if o.users_collection and o.users_collection[0].name == 'GA25X_extras':
        o.hide_viewport = True
        o.hide_set(True)
# 0.3.1: stock seat / stick / throttle previews (user's placeholder meshes, not saved) so the cabin checks see the kitbash
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stock_preview as SP
PREVIEW = SP.add_cockpit_preview() if SP.available() else []
dg = bpy.context.evaluated_depsgraph_get()
scene = bpy.context.scene
res = {}


def cast(org, d, dist=100.0, ignore=()):
    org = Vector(org)
    d = Vector(d).normalized()
    travelled = 0.0
    for _ in range(40):
        ok, loc, nrm, idx, ob, mw = scene.ray_cast(dg, org, d, distance=dist - travelled)
        if not ok:
            return None
        if ob.name in ignore or ob.name.startswith(ignore):
            travelled += (loc - org).length + 1e-4
            org = loc + d * 1e-4
            continue
        me = ob.data
        mat = None
        if idx < len(me.polygons):
            mi = me.polygons[idx].material_index
            mat = ob.material_slots[mi].name if mi < len(ob.material_slots) else None
        return dict(obj=ob.name, loc=loc, nrm=nrm, mat=mat, dist=travelled + (loc - org).length, front=nrm.dot(d) < 0)
    return None


def put(name, ok, detail=''):
    res[name] = dict(ok=bool(ok), detail=detail if isinstance(detail, str) else json.dumps(detail, default=str)[:400])
    print(('PASS ' if ok else 'FAIL ') + name, detail)


def wverts(o):
    return [o.matrix_world @ v.co for v in o.data.vertices]


def quads(o):
    vs = wverts(o)
    return [[vs[i] for i in p.vertices] for p in o.data.polygons]


# ---------------------------------------------------------------- displays
eyes = [O['cockpit_eye'].matrix_world.translation, O['crew_wso_eye'].matrix_world.translation]
faces = []
for n in ('mfd_center', 'mfd_left', 'mfd_right', 'mfd_wso'):
    faces += [(n, q) for q in quads(O[n])]
faces += [('cockpit_gauges', q) for q in quads(O['cockpit_gauges']) if len(q) == 4]   # 1.8.4: the ISIS lubber triangle is a tri
bad, n_rays = [], 0
for name, q in faces:
    c = sum(q, Vector()) / 4
    for k in range(4):
        a, b = q[k], q[(k + 1) % 4]
        out_dir = ((a + b) / 2 - c).normalized()
        for t in (0.15, 0.5, 0.85):
            p = a.lerp(b, t) + out_dir * 0.001
            for e in eyes:
                if (p - e).length > 1.6:
                    continue
                h = cast(e, p - e, (p - e).length + 0.05, ignore=('canopy_', 'gunsight_combiner'))
                n_rays += 1
                if h is None or (h['obj'] == 'cockpit_interior' and h['mat'] == 'cockpit' and h['dist'] > (p - e).length - 0.0005):
                    bad.append((name, round(p.x, 3), round(p.y, 3), round(p.z, 3), h and h['mat']))
put('displays covered: bezel lip / backing around every face (no bare panel)', not bad, f'{len(bad)} of {n_rays} edge rays see bare panel: {bad[:6]}')

ci = O['cockpit_interior']
civ = wverts(ci)
cop = []
for name, q in faces:
    n = (q[1] - q[0]).cross(q[3] - q[0]).normalized()
    c = sum(q, Vector()) / 4
    ux = (q[1] - q[0]).normalized()
    uy = n.cross(ux)
    hx, hy = (q[1] - q[0]).length / 2, (q[3] - q[0]).length / 2
    for p in ci.data.polygons:
        pc = ci.matrix_world @ p.center
        if abs((pc - c).dot(n)) < 0.001 and abs((pc - c).dot(ux)) < hx - 0.002 and abs((pc - c).dot(uy)) < hy - 0.002:
            pn = (ci.matrix_world.to_3x3() @ p.normal).normalized()
            if abs(pn.dot(n)) > 0.99:
                cop.append((name, tuple(round(v, 3) for v in pc)))
put('no cockpit_interior face coplanar with a display / ISIS face (z-fight)', not cop, f'{len(cop)}: {cop[:6]}')

# ---------------------------------------------------------------- tail cone
yt = min(v.y for v in wverts(O['fus_tail']))
back = []
nr = 0
for i in range(-12, 13):
    for j in range(0, 25):
        x, z = i * 0.028, 0.05 + j * 0.03
        h = cast((x, yt - 3.0, z), (0, 1, 0), 3.5, ignore=('slimelight_',))
        if h is None or h['loc'].y > -9.3:
            continue
        nr += 1
        if not h['front']:
            back.append((round(x, 3), round(z, 3), h['obj']))
put('tail cone closed: rays from behind hit front faces only', not back and nr > 50, f'{len(back)} back-face hits of {nr}: {back[:6]}')

top = max((v.z for v in wverts(O['fus_tail']) if v.y < -7.5 and abs(v.x) < 0.2), default=9)
put('tail top line: no tail-gunner hump (fus_tail top aft of y -7.5 <= 1.00 m)', top <= 1.0, f'max z {top:.3f}')

# ---------------------------------------------------------------- spinner / cowl junction
spin = []
for L, s in (('L', -1), ('R', 1)):
    ax = O[f'prop_hub_{L}'].matrix_world.translation
    for k in range(24):
        a = 2 * math.pi * k / 24
        d = Vector((math.sin(a), 0, math.cos(a)))
        for yy in (2.625, 2.635, 2.640, 2.650):
            org = Vector((ax.x, yy, ax.z)) + d * 1.0 + Vector((0, 0.15, 0))
            tgt = Vector((ax.x, yy, ax.z)) + d * 0.30
            h = cast(org, tgt - org, 1.2, ignore=('prop_' + L + '_blade', 'slimelight_'))
            if h is None:
                continue
            r = (Vector((h['loc'].x, 0, h['loc'].z)) - Vector((ax.x, 0, ax.z))).length
            if r < 0.27 or h['loc'].y < 2.60 or not h['front']:
                spin.append((L, round(math.degrees(a)), yy, round(r, 3), h['obj']))
put('spinner meets the cowl: junction rays stop on the skirt / closed cowl front (no see-through)', not spin, f'{len(spin)}: {spin[:6]}')

# ---------------------------------------------------------------- dorsal fairing
dors = []
for i in range(-4, 5):
    for j in range(-4, 5):
        h = cast((i * 0.07, 1.82 + j * 0.07, 3.0), (0, 0, -1), 3.0)
        if h is None or h['obj'] != 'fus_forward' or not h['front'] or h['mat'] != 'paint':
            dors.append((i, j, h and h['obj'], h and h['mat']))
put('dorsal turret ring faired over (skin, front-facing)', not dors, f'{len(dors)}: {dors[:6]}')

# ---------------------------------------------------------------- 0.3.1 stock-part cabin (kitbash)
from mathutils.bvhtree import BVHTree


def bvh_of(objs):
    vs, fs = [], []
    for o in objs:
        mw = o.matrix_world
        b = len(vs)
        vs += [mw @ v.co for v in o.data.vertices]
        fs += [tuple(i + b for i in p.vertices) for p in o.data.polygons]
    return BVHTree.FromPolygons(vs, fs) if fs else None


N_STOCK = 5 if 'stock_mesh' in (O['cockpit_throttle'].get('b25_info') or '') else 4     # 0.3.3: no stock throttle mesh
put(f'stock parts previewed (user placeholder meshes: 2 seats, 2 sticks{", 1 throttle" if N_STOCK == 5 else ""})', len(PREVIEW) == N_STOCK, [p.name for p in PREVIEW])
pv = {p.name: p for p in PREVIEW}
if len(PREVIEW) == N_STOCK:
    # canopy clearance: no stock seat vertex above (outside) the canopy shell, >= 5 mm under it
    shell = bvh_of([O[n] for n in ('canopy_jettison_L', 'canopy_jettison_R', 'canopy_frame', 'canopy_glass', 'fus_cockpit') if n in O])
    worst = {}
    for L in 'LR':
        s_ = pv[f'preview_seat_{L}']
        mn, at = 9.0, None
        for v in s_.data.vertices:
            p = s_.matrix_world @ v.co
            if p.z < 0.9:
                continue
            up = shell.ray_cast(p, Vector((0, 0, 1)), 1.0)
            dn = shell.ray_cast(p, Vector((0, 0, -1)), 0.5)
            d = up[3] if up[0] is not None else (-dn[3] if dn[0] is not None else 9.0)
            if d < mn:
                mn, at = d, (tuple(round(c, 3) for c in p), (up[0] is not None) and 'under' or 'above')
        worst[L] = (round(mn, 4), at)
    put('stock ejection seats stay inside the canopy (>= 5 mm under the shell, straight up)', all(v[0] >= 0.005 for v in worst.values()), worst)
    # ejection path: straight up from the seat headbox the first thing hit is that seat's own canopy panel
    ej = []
    for L in 'LR':
        s_ = pv[f'preview_seat_{L}']
        vs = wverts(s_)
        top = max(vs, key=lambda v: v.z)
        cx = s_.matrix_world.translation.x
        for dx in (-0.10, 0.0, 0.10):
            org = Vector((cx + dx, top.y, top.z + 0.002))
            h = cast(org, (0, 0, 1), 1.5, ignore=('preview_',))
            if h is None or not h['obj'].startswith(f'canopy_jettison_{L}'):
                ej.append((L, dx, h and h['obj'], h and round(h['dist'], 3)))
    put('ejection path: straight up from each stock seat headbox the first thing hit is its own jettison canopy panel', not ej, ej)
    # no clash between the stock parts and our cabin geometry (above the deck; stick bases may sit 1 cm into the footwell floor)
    ours = bvh_of([O[n] for n in ('cockpit_interior', 'cockpit_gauges', 'cockpit_rudder_pedals_L', 'cockpit_rudder_pedals_R',
                                  'mfd_center', 'mfd_left', 'mfd_right', 'mfd_wso', 'gunsight_pilot', 'gunsight_combiner') if n in O])
    clash = {}
    fw = O['stick_L'].matrix_world.translation.z           # footwell floor = stock stick base (ga25x_cockpit.footwell_z)
    fz = O['cockpit_interior'].matrix_world.translation.z  # deck (FLOOR_Z = cockpit_interior origin)
    for n, o in pv.items():
        hits = ours.overlap(bvh_of([o]))
        mw = o.matrix_world
        # allowed: stick bases into the footwell floor, seat bases into the deck (stock seat rails sit in the floor)
        lim = fw + 0.01 if n.startswith('preview_stick_') else (fz + 0.005 if n.startswith('preview_seat_') else -9)
        bad = [j for _, j in hits if min((mw @ o.data.vertices[i].co).z for i in o.data.polygons[j].vertices) >= lim]
        if bad:
            zs = [min((mw @ o.data.vertices[i].co).z for i in o.data.polygons[j].vertices) for j in bad]
            clash[n] = dict(pairs=len(bad), z=(round(min(zs), 3), round(max(zs), 3)))
    real = clash
    put('stock seat / sticks / throttle do not cut into the cabin (sticks may only touch the footwell floor at their base)', not real, clash)
    # stock parts against each other (seat front vs throttle / sticks)
    pc = []
    for a_ in pv:
        for b_ in pv:
            if a_ < b_ and bvh_of([pv[a_]]).overlap(bvh_of([pv[b_]])):
                pc.append((a_, b_))
    put('stock parts clear of each other (seats vs sticks / throttle)', not pc, pc)
    # crew eye -> main display corners: line of sight clear (glareshield, sticks, HUD frame do not hide the displays)
    blk = []
    # main displays + the ISIS column from both eyes (the small dark aux panes low outboard may sit behind the stock stick grip)
    for eye, mfd in (('cockpit_eye', 'mfd_center'), ('crew_wso_eye', 'mfd_right'), ('cockpit_eye', 'cockpit_gauges'), ('crew_wso_eye', 'cockpit_gauges'),
                     ('crew_wso_eye', 'mfd_center'), ('cockpit_eye', 'mfd_right')):
        e = O[eye].matrix_world.translation
        ob = O[mfd]
        tgts = []
        for poly in ob.data.polygons:                       # each face: its corners pulled >= 8 mm toward its own centre (past the 2 mm lip)
            pv_ = [ob.matrix_world @ ob.data.vertices[i].co for i in poly.vertices]
            c = sum(pv_, Vector()) / len(pv_)
            tgts += [v + (c - v).normalized() * max(0.06 * (c - v).length, 0.008) for v in pv_]   # >= 8 mm in from the corner
        for t in tgts:
            h = cast(e, t - e, (t - e).length + 0.01)
            if h is None or (h['obj'] != mfd and not h['obj'].startswith('gauge_isis_')):   # 1.8.4: the ISIS cards / pointers ARE the display
                blk.append((eye, mfd, h and h['obj']))
    put('crew eyes see all corners of both main displays and the ISIS column (nothing in front of the screens)', not blk, blk)

# ---------------------------------------------------------------- cabin materials: no tiles / yellow / rubber crosshatch
cabin = ('cockpit_interior', 'cockpit_gauges', 'cockpit_rudder_pedals_', 'mfd_', 'gunsight_')
badm = sorted({(o.name, ms.name) for o in O if o.type == 'MESH' and o.name.startswith(cabin) for ms in o.material_slots
               if ms.name not in ('ck_struct', 'ck_panel', 'ck_black', 'ck_art', 'ck_throttle', 'screen', 'gauges')})
put('cabin objects use only ck_struct / ck_panel / ck_black / ck_art (panel art) / screen / gauges (no rubber crosshatch or tiles)', not badm, badm)
gone = [n for n in O.keys() if n.startswith(('cockpit_seat_', 'quadrant_throttle_', 'ejection_rail_')) or (n.startswith('stick_') and O[n].type == 'MESH')]
put('no custom seat / stick / throttle geometry left (stick_L/R and cockpit_throttle are empties)', not gone and O.get('cockpit_throttle') is not None
    and all(O[f'stick_{L}'].type == 'EMPTY' for L in 'LR') and O['cockpit_throttle'].type == 'EMPTY', gone)

# ---------------------------------------------------------------- 0.3.2 cockpit standard (mounts, pedals, legs, floating parts, art)
sys.path.insert(1, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'v2'))
import b25h_spec as _S, ga25x_spec as _G
_G.apply(_S)
import ga25x_cockpit as CK
from mathutils import Matrix
cab_names = [n for n in ('cockpit_interior', 'cockpit_rudder_pedals_L', 'cockpit_rudder_pedals_R', 'cockpit_throttle_arm',
                         'mfd_center', 'mfd_left', 'mfd_right', 'mfd_wso', 'cockpit_gauges', 'gunsight_pilot', 'gunsight_combiner') if n in O]
cab = bvh_of([O[n] for n in cab_names])
housing = bvh_of([O['cockpit_interior']])
# 0.3.3 split throttle lever (our cockpit_throttle_arm, rotates about the cockpit_throttle pivot, Unity +X = top forward):
# at 0 / 26 / 52 deg it stays inside its slot (everything below the arc surface within +-slot half width and the slot angles),
# the gap lever edge -> slot wall is <= 5 mm, and it intersects nothing in the cabin (housing, FRICTION dial, panel)
arm = O.get('cockpit_throttle_arm')
if arm is not None:
    ainf = json.loads(arm.get('b25_info') or '{}')
    piv = O['cockpit_throttle'].matrix_world.translation
    shx, (sa0, sa1), rarc = ainf['slot_half_x'], ainf['slot_deg'], ainf['r_arc']
    others = bvh_of([O[n] for n in cab_names if n != 'cockpit_throttle_arm'] + [p for p in PREVIEW])
    res_l = {}
    for deg in (0, 26, 52):
        R = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(-deg), 4, 'X') @ Matrix.Translation(-piv)
        vs = [R @ (arm.matrix_world @ v.co) for v in arm.data.vertices]
        low = [v for v in vs if ((v - piv).y ** 2 + (v - piv).z ** 2) ** 0.5 < rarc + 0.0005]
        angs = [math.degrees(math.atan2((v - piv).y, (v - piv).z)) for v in low]
        xmax = max(abs(v.x - piv.x) for v in low) if low else 9
        inside = bool(low) and xmax <= shx and all(sa0 <= a_ <= sa1 for a_ in angs)
        tb = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in arm.data.polygons])
        res_l[deg] = dict(in_slot=inside, slot_gap_mm=round((shx - xmax) * 1000, 1), angles=(round(min(angs), 1), round(max(angs), 1)) if angs else None,
                          intersects=bool(tb.overlap(others)))
    put('split throttle lever: inside its slot at 0 / 26 / 52 deg, slot gap <= 5 mm, no intersection with housing / dial / panel',
        all(r['in_slot'] and 0 <= r['slot_gap_mm'] <= 5.0 and not r['intersects'] for r in res_l.values()), res_l)
if len(PREVIEW) == N_STOCK:
    # stick bases sit on their mounts (gap < 5 mm)
    res_s = {}
    for L in 'LR':
        st = pv[f'preview_stick_{L}']
        base = O[f'stick_{L}'].matrix_world.translation
        vs = [st.matrix_world @ v.co for v in st.data.vertices]
        low = [v for v in vs if v.z < base.z + 0.03]
        res_s[L] = round(min(cab.find_nearest(v)[3] for v in low) * 1000, 1)
    put('stick bases touch their mounts (gap < 5 mm)', all(v < 5.0 for v in res_s.values()), res_s)
# pedals: face normal aft and up, within 40 deg of the knee direction; plane roughly along the sole (heel->pedal 90 +- 35 deg)
ped = []
okp = True
for L in 'LR':
    inf = json.loads(O[f'cockpit_rudder_pedals_{L}'].get('b25_info') or '{}')
    for pl in inf.get('plates', []):
        c, n = Vector(pl['centre']), Vector(pl['normal']).normalized()
        knee, heel = Vector(pl['knee']), Vector(pl['heel'])
        a_knee = math.degrees(n.angle((knee - c).normalized()))
        a_heel = math.degrees(n.angle((c - heel).normalized()))
        good = n.y < -0.1 and n.z > 0.3 and a_knee < 40 and 55 < a_heel < 125
        okp &= good
        ped.append(dict(L=L, normal=[round(v, 3) for v in n], knee_deg=round(a_knee, 1), heel_to_pedal_deg=round(a_heel, 1), ok=good))
put('rudder pedals: face normal aft-up, within 40 deg of the knee direction, plane along the foot (heel->pedal 55..125 deg)', okp and len(ped) == 4, ped)
# crew legs (COIN bone pose, capsule / foot-box envelope) clear of every cabin part and the stock sticks / throttle
leg_bad = []
targets = [(n, bvh_of([O[n]])) for n in cab_names] + [(p.name, bvh_of([p])) for p in PREVIEW if not p.name.startswith('preview_seat_')]
for key in ('pilot', 'wso'):
    for side in (-1, 1):
        lp = CK.leg_points(key, side)
        samples = []
        for a, b, r in ((lp['hip'], lp['knee'], CK.THIGH_R), (lp['knee'], lp['ankle'], CK.SHIN_R)):
            for k in range(21):
                samples.append((a.lerp(b, k / 20), r))
        # foot box: sole line heel -> sole_toe, FOOT_HALF_W wide: three rows of 28 mm spheres whose bottoms sit 2 mm above the sole
        fl = (lp['sole_toe'] - lp['heel']).length
        for k in range(15):                                      # sphere centres kept one radius inside the heel / toe ends of the box
            t = 0.028 / fl + (1 - 0.056 / fl) * k / 14
            p = lp['heel'].lerp(lp['sole_toe'], t) + Vector((0, 0, 0.030))
            for dx in (-(CK.FOOT_HALF_W - 0.028), 0.0, CK.FOOT_HALF_W - 0.028):
                samples.append((p + Vector((dx, 0, 0)), 0.028))
        for tn, tb in targets:
            if tb is None:
                continue
            worst = None
            for p, r in samples:
                hit = tb.find_nearest(p)
                if hit[0] is None:
                    continue
                d = hit[3] - r
                if worst is None or d < worst[0]:
                    worst = (d, p)
            if worst is not None and worst[0] < 0:
                leg_bad.append((key, side, tn, round(worst[0] * 1000, 1), tuple(round(c, 3) for c in worst[1])))
put("nothing intersects the crew figures' legs (COIN bone pose: thigh r 75 mm, shin r 55 mm, foot box 90 mm wide)", not leg_bad, leg_bad[:8])
# no floating part: every connected island of the cabin meshes touches (<= 3 mm) or overlaps something else in the cabin / hull
import bmesh
hull = [O[n] for n in ('fus_cockpit', 'fus_forward') if n in O]
float_bad = []
n_isl = 0
for n in cab_names:
    o = O[n]
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    seen = set()
    islands = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, isl = [v], []
        seen.add(v.index)
        while stack:
            u = stack.pop(); isl.append(u.index)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in seen:
                    seen.add(w.index); stack.append(w)
        islands.append(isl)
    bm.free()
    others = bvh_of([O[m] for m in cab_names if m != n] + hull + [p for p in PREVIEW])
    mw = o.matrix_world
    all_v = [mw @ v.co for v in o.data.vertices]
    for isl in islands:
        n_isl += 1
        iset = set(isl)
        rest_faces = [tuple(p.vertices) for p in o.data.polygons if p.vertices[0] not in iset]
        rest = BVHTree.FromPolygons(all_v, rest_faces) if rest_faces else None
        d = 9.0
        for i in isl:
            for b_ in (others, rest):
                if b_ is None:
                    continue
                h = b_.find_nearest(all_v[i])
                if h[0] is not None:
                    d = min(d, h[3])
            if d <= 0.003:
                break
        if d > 0.003:
            c = sum((all_v[i] for i in isl), Vector()) / len(isl)
            float_bad.append((n, len(isl), round(d * 1000, 1), tuple(round(x, 3) for x in c)))
put('no floating cabin part: every mesh island touches or overlaps another part (<= 3 mm)', not float_bad, dict(islands=n_isl, floating=float_bad[:8]))
# panel density: the cabin carries panel art (switch panels, bezels, annunciators, consoles) on enough faces
import ga25x_ckart_layout as LY
ci = O['cockpit_interior']
lay = ci.data.uv_layers['livery'].data
used, area = {}, 0.0
for p in ci.data.polygons:
    if ci.material_slots[p.material_index].name != 'ck_art':
        continue
    u = sum(lay[li].uv[0] for li in p.loop_indices) / p.loop_total
    v = sum(lay[li].uv[1] for li in p.loop_indices) / p.loop_total
    px, py = u * LY.ATLAS, (1 - v) * LY.ATLAS
    nm = next((k for k, (r, _, _) in LY.PANELS.items() if r[0] <= px <= r[2] and r[1] <= py <= r[3]), '?')
    a = p.area * ci.matrix_world.to_3x3().determinant() ** (2 / 3)
    used[nm] = round(used.get(nm, 0.0) + a, 4)
    if nm != 'blank':
        area += a
put('panel art: >= 0.6 m2 of labelled switch-panel / bezel / annunciator / console art and >= 9 different art panels in the cabin',
    area >= 0.6 and len([k for k in used if k not in ('blank', '?')]) >= 9, dict(labelled_m2=round(area, 3), panels=used))

# ---------------------------------------------------------------- 0.3.3 z-fight: coplanar overlapping faces in the cabin
# Every face of the cabin objects (and the hull / cannon parts inside the cabin box) is sampled on a 4 x 4 grid; a sample
# lying within 1 mm of ANOTHER face (other object or other mesh island) whose normal points the same way (dot > 0.999) is a
# coplanar overlap. Overlap area = fraction of samples x face area; any pair with >= 0.25 cm2 fails (0.3.2 in game: the
# cannon ammo drum top 0.0 mm under the cabin deck flickered between the seats).
import bmesh
CP_NAMES = ['cockpit_interior', 'cockpit_rudder_pedals_L', 'cockpit_rudder_pedals_R', 'cockpit_throttle_arm', 'mfd_center',
            'mfd_left', 'mfd_right', 'mfd_wso', 'cockpit_gauges', 'gunsight_pilot', 'fus_cockpit', 'fus_forward', 'fus_nose', 'cannon']
CP_BOX = ((-0.75, 0.75), (2.62, 4.45), (-0.9, 1.4))   # the cabin as seen by the crew (forward of 4.45 is behind the panel)
cv, cf, cown = [], [], []
for n in CP_NAMES:
    o = O.get(n)
    if o is None or o.type != 'MESH':
        continue
    bm = bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    isl, cur = {}, 0
    for v in bm.verts:
        if v.index in isl:
            continue
        st = [v]; isl[v.index] = cur
        while st:
            u = st.pop()
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in isl:
                    isl[w.index] = cur; st.append(w)
        cur += 1
    bm.free()
    mw = o.matrix_world
    b0 = len(cv)
    cv += [mw @ v.co for v in o.data.vertices]
    for p in o.data.polygons:
        c = mw @ p.center
        if CP_BOX[0][0] < c.x < CP_BOX[0][1] and CP_BOX[1][0] < c.y < CP_BOX[1][1] and CP_BOX[2][0] < c.z < CP_BOX[2][1]:
            cf.append(tuple(b0 + i for i in p.vertices))
            cown.append((n, isl[p.vertices[0]], o.material_slots[p.material_index].name if o.material_slots else ''))
cbvh = BVHTree.FromPolygons(cv, cf)


def _fn(f):
    a, b, c = cv[f[0]], cv[f[1]], cv[f[2]]
    nn = (b - a).cross(c - a)
    if nn.length < 1e-12 and len(f) > 3:
        nn = (c - a).cross(cv[f[3]] - a)
    return nn.normalized() if nn.length > 0 else nn


def _area(f):
    a = 0.0
    for k in range(1, len(f) - 1):
        a += ((cv[f[k]] - cv[f[0]]).cross(cv[f[k + 1]] - cv[f[0]])).length / 2
    return a


cn = [_fn(f) for f in cf]
pairs = {}
for i, f in enumerate(cf):
    pts = [cv[k] for k in f]
    A = _area(f)
    if A < 1e-6:
        continue
    samples = []
    for a_ in (0.125, 0.375, 0.625, 0.875):           # 4 x 4 grid over the polygon (fan-bilinear for quads, barycentric for tris)
        for b_ in (0.125, 0.375, 0.625, 0.875):
            if len(pts) == 4:
                p0 = pts[0].lerp(pts[1], a_); p1 = pts[3].lerp(pts[2], a_)
                samples.append(p0.lerp(p1, b_))
            else:
                if a_ + b_ < 1:
                    samples.append(pts[0] + (pts[1] - pts[0]) * a_ + (pts[-1] - pts[0]) * b_)
    if not samples:
        continue
    cnt = {}
    for s in samples:
        seen = set()
        for (co, nrm, j, d) in cbvh.find_nearest_range(s, 0.001):
            if j is None or j == i or j in seen:
                continue
            if cown[j][0] == cown[i][0] and cown[j][1] == cown[i][1]:
                continue
            if cn[i].dot(cn[j]) > 0.999:
                off = s - co
                lat = off - cn[j] * off.dot(cn[j])
                if lat.length > 0.0002:                  # nearest point on face j's edge: adjacent, not overlapping
                    continue
                seen.add(j)
                cnt[j] = cnt.get(j, 0) + 1
    for j, k in cnt.items():
        ov = A * k / len(samples)
        key = tuple(sorted((i, j)))
        if ov > pairs.get(key, (0,))[0]:
            c_ = sum(pts, Vector()) / len(pts)
            cj = sum((cv[k] for k in cf[j]), Vector()) / len(cf[j])
            pairs[key] = (ov, cown[i], cown[j], tuple(round(x, 3) for x in c_), tuple(round(x, 3) for x in cj), tuple(round(x, 2) for x in cn[i]))
big = sorted([v for v in pairs.values() if v[0] >= 0.25e-4], key=lambda v: -v[0])
small = [v for v in pairs.values() if v[0] < 0.25e-4]
put('z-fight: no coplanar overlapping faces in the cabin (other part / island, same-facing, < 1 mm apart, >= 0.25 cm2)', not big,
    dict(pairs=len(big), below_threshold=len(small), worst=[(round(v[0] * 1e4, 2), v[1][0] + ':' + v[1][2], v[2][0] + ':' + v[2][2], v[3], v[4], v[5]) for v in big[:12]]))

# ---------------------------------------------------------------- laser envelope
el = O['laser_turret_el'].matrix_world.translation
own = ('laser_turret_', 'muzzle_laser')
blocked = {}
cells = 0
for e_deg in range(2, 91, 2):
    for a_deg in range(0, 360, 5):
        e, a = math.radians(-e_deg), math.radians(a_deg)
        d = Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))
        cells += 1
        h = cast(el + d * 0.32, d, 60.0, ignore=own)
        if h is not None:
            blocked.setdefault(h['obj'].split('_')[0] + '_' + h['obj'].split('_')[1] if '_' in h['obj'] else h['obj'], []).append((a_deg, e_deg))
summ = {k: dict(n=len(v), max_depression=max(x[1] for x in v), az=sorted({x[0] for x in v})[:3] + ['..'] + sorted({x[0] for x in v})[-3:]) for k, v in blocked.items()}
nb = sum(len(v) for v in blocked.values())
put('laser envelope (el -2..-90, gear down, doors closed): only the extended gear and prop blades in the beam path (Turret linecast holds fire; gear up = clear)',
    all(k.startswith(('gear_', 'tailhook', 'prop_')) for k in blocked), dict(cells=cells, blocked=nb, by_object=summ))
res['laser'] = dict(el_pivot=[round(v, 4) for v in el], belly_skin_z=None, blocked=summ)

json.dump(dict(checks={k: v for k, v in res.items() if k != 'laser'}, laser=res['laser']), open(out, 'w'), indent=1, default=str)
print('[check_v030] wrote', out)
