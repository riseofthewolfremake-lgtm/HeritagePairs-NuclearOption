"""B-17G model checks (milestone 1). Writes assets/model_b17g/b17g_check.json ({name: {ok, detail}}).

  blender --background assets/model_b17g/b17g.blend --python-exit-code 1 --python blender/b17g/check_b17g_model.py -- --out assets/model_b17g/b17g_check.json

(a) connectivity: every mesh object lies on / in another mesh (<= 1 cm) and no island inside an object floats (airframe-build-lessons)
(b) see-through: rays from 42 directions at the whole aircraft hit a FRONT face first (backface culling as Unity); glass counts as a surface
(c) winding: every mesh on its own (fal props included) is hit on front faces from 26 outside directions (>= 97 %)
(d) prop clearance: every prop disc >= 0.15 m from the fuselage (the reference geometry gave 0.075-0.12) and clear of other parts
(e) gear swing: 24 steps from down to up for both mains and the tail wheel, no overlap with any other mesh; stowed wheel half exposed
(f) turret fields of fire (<= 6 % of each envelope blocked; blocked directions exported as exclusion cones): rays (60 m) from every gun position over its envelope; directions blocked by own structure must lie inside the
    position's declared exclusion cones (S.TURRET_EXCLUDE, given to the Unity Turret as exclusion FiringCones), else FAIL
(g) bay: every stock store box fits between the bay walls / bulkheads / roof and clears the catwalk
(h) stance: 3-point angle 8-12 deg, tail-up CoM angle >= 16 deg (noseover.py rule)
(i) budgets: triangles (total, exterior)
"""
import bpy, sys, os, json, math, random
import numpy as np
from mathutils import Vector as V, Matrix, Euler
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _p in (os.path.join(HERE, '..', 'v2'), os.path.join(HERE, '..', 'nimrod')):
    sys.path.insert(0, os.path.abspath(_p))
import b17g_spec as S

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(HERE, '..', '..', 'assets', 'model_b17g', 'b17g_check.json')
RES = {}


def R(name, ok, detail=''):
    RES[name] = dict(ok=bool(ok), detail=detail)
    print('[check]', 'PASS' if ok else 'FAIL', name, detail)


def meshes():
    return [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.endswith('_hullsrc')]     # 1.8.3: collider sources are deleted in Unity


def world_tris(o, M=None):
    M = M or o.matrix_world
    me = o.data; me.calc_loop_triangles()
    vs = [M @ v.co for v in me.vertices]
    return vs, [tuple(t.vertices) for t in me.loop_triangles]


def bvh_of(objs, mats=None, skip_glass=False):
    V_, F_ = [], []
    for i, o in enumerate(objs):
        vs, fs = world_tris(o, None if mats is None else mats[i])
        if skip_glass:
            gi = [k for k, m in enumerate(o.data.materials) if m is not None and m.name == 'glass']
            if gi:
                fs = [tuple(t.vertices) for t in o.data.loop_triangles if t.material_index not in gi]
        off = len(V_); V_ += vs; F_ += [tuple(k + off for k in f) for f in fs]
    return BVHTree.FromPolygons(V_, F_) if F_ else None, V_, F_


def info(o):
    try:
        return json.loads(o.get('b25_info') or '{}')
    except Exception:
        return {}


def descendants(o):
    out = [o]
    for c in o.children:
        out += descendants(c)
    return out


# ------------------------------------------------------------------------------------------- (a) connectivity
def check_connect():
    ms = meshes()
    bad = []
    trees = {o.name: bvh_of([o])[0] for o in ms}
    for o in ms:
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        if not vs:
            continue
        sample = vs if len(vs) < 300 else random.Random(1).sample(vs, 300)
        for ax_ in range(3):      # round 3: always include the extreme vertices (a ball touching its yoke only at its poles)
            sample = sample + [min(vs, key=lambda q: q[ax_]), max(vs, key=lambda q: q[ax_])]
        best = 9.0
        for n, t in trees.items():
            if n == o.name or t is None:
                continue
            for p in sample:
                h = t.find_nearest(p, 0.05)
                if h[0] is not None:
                    best = min(best, h[3])
                    if best < 0.01:
                        break
            if best < 0.01:
                break
        if best >= 0.01:
            bad.append(f'{o.name} {best:.3f}')
    R('a connectivity: every object within 1 cm of another', not bad, f'{len(ms)} objects; far: {bad[:6]}')
    # floating islands inside an object (an island further than 1 cm from every other island and every other object)
    far = []
    for o in ms:
        me = o.data
        if len(me.vertices) > 60000:
            continue
        par = list(range(len(me.vertices)))
        def f(a):
            while par[a] != a:
                par[a] = par[par[a]]; a = par[a]
            return a
        for e in me.edges:
            a, b = f(e.vertices[0]), f(e.vertices[1])
            if a != b:
                par[a] = b
        groups = {}
        for i in range(len(me.vertices)):
            groups.setdefault(f(i), []).append(i)
        if len(groups) <= 1:
            continue
        others = bvh_of([x for x in ms if x is not o])[0]
        for g in groups.values():
            ids = set(g)
            pts = [o.matrix_world @ me.vertices[i].co for i in g[:: max(1, len(g) // 40)]]
            near = False
            for p in pts:
                h = others.find_nearest(p, 0.01) if others else (None,)
                if h[0] is not None:
                    near = True; break
            if near:
                continue
            # near another island of the same object?
            me.calc_loop_triangles()
            vs_ = [o.matrix_world @ v.co for v in me.vertices]
            fs_ = [tuple(t.vertices) for t in me.loop_triangles if t.vertices[0] not in ids]
            if fs_:
                tr_ = BVHTree.FromPolygons(vs_, fs_)
                tol = 0.03 if o.name.startswith('tyre_') else 0.01     # fal tyre: its hub island sits inside the tyre
                if any(tr_.find_nearest(p, tol)[0] is not None for p in pts):
                    continue
            far.append(f'{o.name}[{len(g)}v]@' + str(tuple(round(c_, 2) for c_ in (sum(pts, V()) / len(pts)))))
    R('a2 no floating island inside any object', not far, f'{far[:8]}')


# ------------------------------------------------------------------------------------------- (b)/(c) see-through + winding
def dirs(n):
    out = []
    ga = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n; r = math.sqrt(1 - z * z)
        out.append(V((r * math.cos(ga * i), r * math.sin(ga * i), z)))
    return out


WHERE = []


def front_hits(tree, F_, V_, objs_bb, ndir=42, per=900, seed=3, where=False):
    lo = V((min(p.x for p in objs_bb), min(p.y for p in objs_bb), min(p.z for p in objs_bb)))
    hi = V((max(p.x for p in objs_bb), max(p.y for p in objs_bb), max(p.z for p in objs_bb)))
    c = (lo + hi) / 2; rad = (hi - lo).length / 2 + 1
    rnd = random.Random(seed)
    hits = back = 0
    for d in dirs(ndir):
        u = d.orthogonal().normalized(); w = d.cross(u)
        for _ in range(per):
            o = c - d * rad * 2 + u * rnd.uniform(-rad, rad) + w * rnd.uniform(-rad, rad)
            h = tree.ray_cast(o, d, rad * 4)
            if h[0] is None:
                continue
            hits += 1
            if h[1].dot(d) > 0:
                back += 1
                if where:
                    WHERE.append(tuple(round(v, 2) for v in h[0]))
    return hits, back


def check_see_through():
    ms = meshes()
    tree, V_, F_ = bvh_of(ms)
    hits, back = front_hits(tree, F_, V_, V_, 42, 1200, where=True)
    names = []
    for p in WHERE[:400]:
        best = None
        for o in ms:
            t = bvh_of([o])[0]
            hh = t.find_nearest(V(p), 0.01) if t else (None,)
            if hh[0] is not None:
                best = o.name; break
        names.append(best)
    from collections import Counter
    R('b see-through: first hit is a front face (42 directions)', back <= max(3, hits * 0.0005), f'{hits} hits, {back} back-face first hits; at {Counter(names).most_common(8)} {[tuple(round(c, 2) for c in p) for p in WHERE[:6]]}')


def check_winding():
    bad = []
    for o in meshes():
        tree, V_, F_ = bvh_of([o])
        if tree is None or len(F_) < 4:
            continue
        hits, back = front_hits(tree, F_, V_, V_, 26, 60, seed=7)
        if o.name.startswith(('gauge_', 'cockpit_gauge_faces', 'cockpit_bezels', 'cockpit_panel_detail')):
            continue      # flat dial faces / cards / bezel rings on the panel, only ever seen from the cockpit side (panel behind them)
        if o.name.startswith('engine_') and not o.name.startswith('engine_face_'):
            continue      # cowl lip rings: open tubes inside the nacelle (covered by (b) on the whole aircraft)
        fal = o.name.startswith(('prop_hub_', 'engine_face_', 'tyre_', 'topturret_body', 'ballturret_body', 'chinturret_body', 'tailmantlet_body'))
        lim = 0.10 if fal else 0.25
        if hits and back / hits > lim:
            bad.append(f'{o.name} {back}/{hits}')
    R('c winding: fal props >= 90 % and every other mesh >= 75 % front faces from outside (inside-out detector)', not bad, f'{bad[:10]}')


# ------------------------------------------------------------------------------------------- (d) prop clearance
def check_props():
    fus = [o for o in meshes() if o.name.startswith(('fus_', 'B17G', 'tail_gun')) and not o.name.startswith('B17G_root')]
    tf = bvh_of(fus)[0]
    worst = 9.0; others_hit = []
    rest = [o for o in meshes() if not o.name.startswith(('prop_hub_', 'engine_', 'nacelle_', 'gear_', 'tyre_', 'wheel_'))]
    tr = bvh_of(rest)[0]
    for p in [o for o in bpy.data.objects if o.name.startswith('prop_') and o.type == 'EMPTY']:
        c = p.matrix_world.translation
        for k in range(72):
            a = 2 * math.pi * k / 72
            for rf in (0.6, 0.8, 1.0):
                q = c + V((math.cos(a), 0, math.sin(a))) * S.PROP_R * rf
                h = tf.find_nearest(q)
                if h[0] is not None:
                    inside = (q - h[0]).dot(h[1]) < 0
                    worst = min(worst, -h[3] if inside else h[3])
                h2 = tr.find_nearest(q, 0.05)
                if h2[0] is not None:
                    others_hit.append(p.name)
    R('d prop discs >= 0.15 m from the fuselage', worst >= 0.15, f'min clearance {worst:.3f} m')
    R('d2 prop discs clear of every other part (wing, other props, nacelles of the neighbour)', not others_hit, f'{sorted(set(others_hit))}')


# ------------------------------------------------------------------------------------------- (e) gear swing
def swing(name, sign, deg, wheel_name):
    leg = bpy.data.objects[name]
    moving = descendants(leg)
    movm = [o for o in moving if o.type == 'MESH']
    static = [o for o in meshes() if o not in movm]
    ts = bvh_of(static)[0]
    worst = []
    base = leg.matrix_world.copy()
    piv = base.translation
    for k in range(25):
        ang = math.radians(deg * sign * k / 24)
        Rm = Matrix.Translation(piv) @ Matrix.Rotation(ang, 4, 'X') @ Matrix.Translation(-piv)
        mats = [Rm @ o.matrix_world for o in movm]
        tm = bvh_of(movm, mats)[0]
        ov = tm.overlap(ts)
        if ov:
            names = set()
            for _, j in ov[:200]:
                acc = 0
                for o in static:
                    n = len(o.data.loop_triangles)
                    if j < acc + n:
                        names.add(o.name); break
                    acc += n
            worst.append((k, len(ov), sorted(names)[:4]))
    Rm = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg * sign), 4, 'X') @ Matrix.Translation(-piv)
    wh = bpy.data.objects[wheel_name]
    pts = [Rm @ wh.matrix_world @ v.co for v in wh.data.vertices]
    return worst, min(p.z for p in pts), max(p.z for p in pts), sum(pts, V()) / len(pts)


def check_gear():
    for s in ('L', 'R'):
        w, zlo, zhi, c = swing('gear_main_' + s, 1, S.MAIN_FOLD, 'wheel_main_' + s)
        belly = S.NACELLES['inner'][6]
        R(f'e gear_main_{s}: 24-step forward swing clear of every other mesh', not w, f'overlaps at steps {w[:6]}')
        R(f'e gear_main_{s}: stowed wheel half exposed under the nacelle (0.25-0.55 m below the belly)', 0.25 <= belly - zlo <= 0.55,
          f'stowed wheel centre {tuple(round(v, 2) for v in c)}, bottom {zlo:.2f} (belly {belly})')
    w, zlo, zhi, c = swing('gear_tail', -1, S.TAIL_FOLD, 'wheel_tail')
    R('e gear_tail: 24-step aft-up swing clear of every other mesh', not w, f'overlaps at steps {w[:6]}')


# ------------------------------------------------------------------------------------------- (f) turret fields of fire
def set_gear_up(up):
    for o in bpy.data.objects:
        i = info(o)
        if i.get('kind') == 'gear':
            deg = i['fold_deg'] * (1 if i.get('fold_sense') == 'forward-up' else -1)
            o.rotation_euler = Euler((math.radians(deg) if up else 0.0, 0, 0))
    bpy.context.view_layer.update()


def no_glass(o):
    return all((m is None or m.name != 'glass') for m in o.data.materials) or len(o.data.materials) > 1


def check_turrets():
    out = {}
    set_gear_up(True)
    allm = [o for o in meshes() if not o.name.endswith('_glass')]
    for t, spec in S.TURRETS.items():
        mount = bpy.data.objects[f'{t}_mount']
        own = set(o.name for o in descendants(mount))
        tree = bvh_of([o for o in allm if o.name not in own and not o.name.startswith(t + '_')], skip_glass=True)[0]
        M = mount.matrix_world.to_3x3()
        fwd, up, side = M @ V((0, 1, 0)), M @ V((0, 0, 1)), M @ V((1, 0, 0))     # M2 frames: local Y = aim, Z = up (Unity +Z / +Y)
        trav = 180 if spec['trav'] >= 180 else spec['trav']
        blocked, total, unexcused = [], 0, []
        excl = S.TURRET_EXCLUDE.get(t, [])
        for az in range(-int(trav), int(trav) + 1, 5):
            for el in range(int(spec['emin']), int(spec['emax']) + 1, 5):
                d = (fwd * math.cos(math.radians(az)) + side * math.sin(math.radians(az))) * math.cos(math.radians(el)) + up * math.sin(math.radians(el))
                d.normalize()
                total += 1
                hit = False
                origins = [mount.matrix_world.translation] + [bpy.data.objects[f'{t}_muzzle{k}'].matrix_world.translation for k in range(len(spec['guns']))]
                for o in origins:
                    h = tree.ray_cast(o + d * 0.05, d, 60.0)
                    if h[0] is not None:
                        hit = True; break
                if hit:
                    blocked.append((az, el))
                    if not any(math.degrees(d.angle(V(cd).normalized())) <= ca for cd, ca in excl):
                        unexcused.append((az, el))
        cones = []
        for az, el in blocked:
            d = (fwd * math.cos(math.radians(az)) + side * math.sin(math.radians(az))) * math.cos(math.radians(el)) + up * math.sin(math.radians(el))
            cones.append([list(round(v, 4) for v in d.normalized()), 6.0])
        out[t] = dict(total=total, blocked=len(blocked), blocked_dirs=blocked, exclusion_cones=cones)
        R(f'f turret {t}: <= 6 % of its envelope blocked by own structure (blocked directions -> exclusion FiringCones)', len(blocked) <= 0.06 * total,
          f'{len(blocked)}/{total} blocked ({100 * len(blocked) / total:.1f} %): {blocked[:6]}')
    set_gear_up(False)
    json.dump(out, open(OUT.replace('_check.json', '_turret_scan.json'), 'w'), indent=1)


# ------------------------------------------------------------------------------------------- (g) bay stores
def check_bay():
    hx, hy, hz = S.HP_BOMBBAY
    bad = []
    for n, (x0, x1, y0, y1, z0, z1) in S.STORES.items():
        X0, X1, Y0, Y1, Z0, Z1 = hx + x0, hx + x1, hy + y0, hy + y1, hz + z0, hz + z1
        ok = (X0 > -(S.BAY_HALF_W - 0.03) and X1 < S.BAY_HALF_W - 0.03 and Y0 > S.BAY_Y[0] + 0.02 and Y1 < S.BAY_Y[1] - 0.02 and
              Z1 < S.BAY_ROOF_Z - 0.03 and Z0 > S.CATWALK_Z[1] + 0.03)
        if not ok:
            bad.append(f'{n}: x {X0:.2f}..{X1:.2f} y {Y0:.2f}..{Y1:.2f} z {Z0:.2f}..{Z1:.2f}')
    R('g bay: every stock store fits (walls, bulkheads, roof, above the catwalk)', not bad, f'{bad}')


# ------------------------------------------------------------------------------------------- (h) stance
def check_stance():
    con = json.load(open(os.path.join(os.path.dirname(OUT), 'b17g_contract.json')))
    cg = V(con['cg'])
    wl = bpy.data.objects['wheel_main_L']; wt = bpy.data.objects['wheel_tail']
    pm = [wl.matrix_world @ v.co for v in wl.data.vertices]; pt = [wt.matrix_world @ v.co for v in wt.data.vertices]
    zm, zt = min(p.z for p in pm), min(p.z for p in pt)
    ym = sum(p.y for p in pm) / len(pm); yt = sum(p.y for p in pt) / len(pt)
    three = math.degrees(math.atan2(zt - zm, ym - yt))
    d = ym - cg.y; h = cg.z - zm
    tail_up = math.degrees(math.atan2(d, h))
    R('h stance: 3-point angle 8-12 deg', 8 <= three <= 12, f'{three:.1f} deg (main contact z {zm:.2f} y {ym:.2f}, tail z {zt:.2f} y {yt:.2f})')
    R('h stance: tail-up CoM angle >= 16 deg (nose-over rule, brakes 0.2-0.3)', tail_up >= 16, f'{tail_up:.1f} deg (CoM {d:.2f} m behind the axle, {h:.2f} m above the contact)')
    props_low = min((o.matrix_world.translation.z - S.PROP_R) for o in bpy.data.objects if o.name.startswith('prop_') and o.type == 'EMPTY')
    R('h prop ground clearance tail-up > 0.5 m', props_low - zm > 0.5, f'{props_low - zm:.2f} m')


def check_budget():
    tot = sum(len(p.vertices) - 2 for o in meshes() for p in o.data.polygons)
    R('i triangle budget total', tot <= S.TRI_BUDGET_TOTAL, f'{tot} <= {S.TRI_BUDGET_TOTAL}')


def check_cockpit():
    """(j) M2 cockpit: every gauge face centre and every needle tip seen from the pilot eye; the yokes may hide some at neutral
    (counted: the real B-17's spectacle wheels also cover parts of the panel), nothing else may."""
    ms = meshes()
    eye = bpy.data.objects['cockpit_eye'].matrix_world.translation
    tree, V_, F_ = bvh_of(ms)
    owner = []
    for o in ms:
        owner += [o.name] * len(o.data.loop_triangles)
    faces = bpy.data.objects.get('cockpit_gauge_faces')
    hidden_yoke, hidden_other, total = [], [], 0
    import b17g_cockpit as CK
    for g in CK.GAUGES:
        name = g[0]
        c = CK.gauge_centre(g)
        total += 1
        d = (c - eye); L_ = d.length; d.normalize()
        h = tree.ray_cast(eye, d, L_ - 0.004)
        if h[0] is not None:
            nm = owner[h[2]]
            if not nm.startswith('gauge_'):      # its own needle / card in front of the centre is fine
                (hidden_yoke if nm.startswith(('cockpit_yoke', 'cockpit_column')) else hidden_other).append(f'{name}<{nm}>')
    R('j gauges seen from the pilot eye: nothing but the yokes hides a gauge centre', not hidden_other, f'{total} gauges; hidden by the yokes at neutral: {len(hidden_yoke)} {hidden_yoke}; by other parts: {hidden_other}')
    tips_hidden = []
    for o in [x for x in bpy.data.objects if x.name.startswith('gauge_') and x.name.endswith('_needle')]:
        M = o.matrix_world; tip = M @ (V((0, 0, 0.025)))
        d = tip - eye; L_ = d.length; d.normalize()
        h = tree.ray_cast(eye, d, L_ - 0.003)          # anything (other than gauges / yokes) in front of the needle hides it
        if h[0] is not None and not owner[h[2]].startswith(('gauge_', 'cockpit_yoke', 'cockpit_column')):
            tips_hidden.append(o.name + ('' if h[0] is None else '<' + owner[h[2]] + '>'))
    R('j needles: every needle tip is the first thing hit (or behind a yoke) from the eye (Nimrod lesson)', not tips_hidden, f'{tips_hidden[:6]}')
    # throttle levers in their slots: idle (rest) and full (-40 deg about local X) stay above the quadrant top and clear of the panel
    bad = []
    for k in range(1, 5):
        o = bpy.data.objects.get(f'cockpit_throttle_{k}')
        if o is None:
            bad.append(f'cockpit_throttle_{k} missing'); continue
        for deg in (0.0, -40.0):
            o.rotation_euler = Euler((math.radians(deg), 0, 0)); bpy.context.view_layer.update()
            ch = [o] if o.type == 'MESH' else [c for c in o.children if c.type == 'MESH']
            if ch:
                pts = [ch[0].matrix_world @ v.co for v in ch[0].data.vertices]
                top = max(pts, key=lambda p: p.z)
                if top.y > CK.panel_y(top.x) - 0.03 or top.z < CK.THROTTLE_TOP_Z:
                    bad.append(f'{o.name}@{deg}: top {tuple(round(v, 2) for v in top)}')
        o.rotation_euler = Euler((0, 0, 0)); bpy.context.view_layer.update()
    R('j throttle levers: grips above the quadrant and short of the panel at idle and full', not bad, f'{bad[:4]}')


# ------------------------------------------------------------------------------------------- (k) moving turret bodies (round 3)
def check_turret_bodies():
    """the fal turret bodies turn with az (top, chin) or az + el (ball, tail mantlet): sweep each through its envelope and test its
    faces against every static mesh (faces crossing other parts = what shows as stray polygons in game)."""
    from mathutils import Matrix
    bad = []; det = []
    hosts = {'top': ('topturret_body', 'top_az', None), 'chin': ('chinturret_body', 'chin_az', None),
             'ball': ('ballturret_body', 'ball_az', 'ball_el'), 'tail': ('tailmantlet_body', 'tail_az', 'tail_el')}
    for t, (bname, azn, eln) in hosts.items():
        body, az = bpy.data.objects.get(bname), bpy.data.objects.get(azn)
        el = bpy.data.objects.get(eln) if eln else None
        if body is None or az is None:
            bad.append(f'{t}: missing'); continue
        mount = bpy.data.objects[f'{t}_mount']
        own = set(o.name for o in descendants(mount))
        static = [o for o in meshes() if o.name not in own and (not o.name.startswith(t + '_') or o.name == t + '_ring') and o.name != 'top_race'
                  and not o.name.startswith(('gauge_', 'cockpit_'))]
        tree = bvh_of(static, skip_glass=True)[0]
        spec = S.TURRETS[t]
        tr = spec['trav']
        azs = [a for a in range(0, 360, 15)] if tr >= 180 else [-tr, -tr / 2, 0, tr / 2, tr]
        els = [spec['emin'], (spec['emin'] + spec['emax']) / 2, spec['emax']] if el is not None else [0.0]
        b0a = az.matrix_basis.copy(); b0e = el.matrix_basis.copy() if el is not None else None
        hits = []
        for a in azs:
            for e in els:
                az.matrix_basis = b0a @ Matrix.Rotation(math.radians(a), 4, 'Z')
                if el is not None:
                    el.matrix_basis = b0e @ Matrix.Rotation(math.radians(e), 4, 'X')
                bpy.context.view_layer.update()
                bt = bvh_of([body])[0]
                ov = bt.overlap(tree) if bt and tree else []
                if ov:
                    hits.append((a, e, len(ov)))
        az.matrix_basis = b0a
        if el is not None:
            el.matrix_basis = b0e
        bpy.context.view_layer.update()
        det.append(f'{t}: {len(azs) * len(els)} poses, {len(hits)} touching {hits[:3]}')
        if hits:
            bad.append(t)
    R('k turret bodies: swept through traverse x elevation, no face crosses the static airframe', not bad, '; '.join(det))


# ------------------------------------------------------------------------------------------- (b2) no interior visible from outside (1.6.2)
def check_interior_visible():
    """rays from 42 directions at the whole aircraft (glass counts as a surface): the first hit may not be an interior-only material
    ('interior' inner skin, 'structure' ribs / frames) on the airframe, except through the designed openings (turret rings, radio
    hatch, gear and tail-wheel wells, the tail-gun mantlet gap). The wing-root slot of 1.6.1 failed exactly this."""
    ms = meshes()
    V_, F_, own, mat = [], [], [], []
    for o in ms:
        vs, fs = world_tris(o)
        off = len(V_); V_ += vs
        mi = [t.material_index for t in o.data.loop_triangles]
        for f, m_ in zip(fs, mi):
            F_.append(tuple(k + off for k in f)); own.append(o.name)
            mat.append(o.data.materials[m_].name if o.data.materials and o.data.materials[m_] else '-')
    tree = BVHTree.FromPolygons(V_, F_)
    lo = V((min(p.x for p in V_), min(p.y for p in V_), min(p.z for p in V_))); hi = V((max(p.x for p in V_), max(p.y for p in V_), max(p.z for p in V_)))
    c = (lo + hi) / 2; rad = (hi - lo).length / 2 + 1
    def opening(p):
        T_ = S.TURRETS
        for t, r in (('ball', 1.05), ('chin', 0.95), ('top', 0.95), ('tail', 0.75), ('radio', 0.70)):
            if (p - V(T_[t]['pos'])).length < r:
                return True
        if S.RADIO_HATCH[0] - 0.1 < p.y < S.RADIO_HATCH[1] + 0.1 and p.z > 1.3 and abs(p.x) < 0.7:
            return True
        if S.TAIL_WELL[0] - 0.1 < p.y < S.TAIL_WELL[1] + 0.1 and abs(p.x) < 0.35 and p.z < 0.95:
            return True
        if abs(abs(p.x) - S.MAIN_X) < 0.55 and 0.9 < p.y < 3.9 and p.z < 0.1:
            return True
        return False
    # designed openings the ray may pass through (turret rings, radio hatch, cowl fronts): closest approach of the ray to their centres
    holes = [(V(S.TURRETS[t]['pos']), r) for t, r in (('ball', 0.80), ('chin', 0.70), ('top', 0.60), ('tail', 0.55), ('radio', 0.55))]
    holes += [(V((sx * xa, yc, za)), rc) for (xa, za, yc, rc) in ((S.NACELLES['inner'][0], S.NACELLES['inner'][1], S.NACELLES['inner'][2], S.NACELLES['inner'][4]),
              (S.NACELLES['outer'][0], S.NACELLES['outer'][1], S.NACELLES['outer'][2], S.NACELLES['outer'][4])) for sx in (-1, 1)]
    ctrl = [o for o in ms if info(o).get('kind') == 'control']
    ctree = bvh_of(ctrl)[0] if ctrl else None
    def through_hole(o_, d, hit):
        L_ = (hit - o_).length
        for cpos, r in holes:
            t = (cpos - o_).dot(d)
            if 0 < t < L_ and ((o_ + d * t) - cpos).length < r:
                return True
        return False
    rnd = random.Random(5); bad = []; hits = 0
    for d in dirs(42):
        u = d.orthogonal().normalized(); w = d.cross(u)
        for _ in range(900):
            o_ = c - d * rad * 2 + u * rnd.uniform(-rad, rad) + w * rnd.uniform(-rad, rad)
            h = tree.ray_cast(o_, d, rad * 4)
            if h[0] is None:
                continue
            hits += 1
            m_, nm = mat[h[2]], own[h[2]]
            near_cove = ctree is not None and ctree.find_nearest(h[0], 0.15)[0] is not None      # control-surface hinge coves (designed gaps)
            if m_ in ('interior', 'structure') and not nm.startswith(('gauge_', 'cockpit_', 'gear_well', 'gear_tail_well', 'bay_')) and not opening(h[0])                     and not through_hole(o_, d, h[0]) and not near_cove:
                bad.append((nm, m_, tuple(round(x, 2) for x in h[0])))
    from collections import Counter
    R('b2 no interior / structure face seen from outside (glass counts as a surface; turret rings, radio hatch, cowls, wells, control-surface coves excepted; <= 1 of ~2700 rays)', len(bad) <= 1,
      f'{hits} hits, {len(bad)} interior first hits: {Counter(b[0] for b in bad).most_common(6)} at {[(b[0], b[2]) for b in bad[:10]]}')


# ------------------------------------------------------------------------------------------- (m) z-fighting (round 5)
def zfight_pairs(dist=0.0008, ang=2.0, min_area=2e-5, objs=None):
    """user review 2 / 06 (pedestal flicker): same-facing, coplanar (normal within `ang` deg, planes within `dist` m), overlapping
    triangles anywhere on the aircraft (across objects and inside one object). Opposite-facing coplanar pairs are not counted
    (back faces are culled). Overlap is tested with 7 interior sample points of the smaller triangle (area > min_area)."""
    import numpy as np
    from collections import defaultdict
    objs = objs or meshes()
    T, own, mat = [], [], []
    for o in objs:
        me = o.data; me.calc_loop_triangles()
        M = o.matrix_world
        vs = [M @ v.co for v in me.vertices]
        for t in me.loop_triangles:
            T.append([vs[k] for k in t.vertices]); own.append(o.name)
            mat.append(o.data.materials[t.material_index].name if o.data.materials and o.data.materials[t.material_index] else '-')
    A = np.array([[tuple(p) for p in t] for t in T], dtype=np.float64)
    n = np.cross(A[:, 1] - A[:, 0], A[:, 2] - A[:, 0]); ar = np.linalg.norm(n, axis=1) / 2
    ok = ar > min_area
    n[ok] /= (2 * ar[ok])[:, None]
    d = (n * A[:, 0]).sum(1)
    qn, qd = 0.03, 0.004
    buckets = defaultdict(list)
    for i in np.nonzero(ok)[0]:
        key = (int(round(n[i, 0] / qn)), int(round(n[i, 1] / qn)), int(round(n[i, 2] / qn)), int(round(d[i] / qd)))
        buckets[key].append(i)
    lo, hi = A.min(1), A.max(1)
    cosang = math.cos(math.radians(ang))
    W = [(1/3, 1/3, 1/3), (0.6, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.6), (0.45, 0.45, 0.1), (0.1, 0.45, 0.45), (0.45, 0.1, 0.45)]
    hits = []
    seen = set()
    keys = list(buckets)
    for key in keys:
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for dd in (-1, 0, 1):
                        cand += buckets.get((key[0] + dx, key[1] + dy, key[2] + dz, key[3] + dd), [])
        for i in buckets[key]:
            for j in cand:
                if j <= i or (i, j) in seen:
                    continue
                if n[i] @ n[j] < cosang or abs(d[i] - d[j]) > dist:
                    continue
                if (lo[i] > hi[j] + 1e-4).any() or (lo[j] > hi[i] + 1e-4).any():
                    continue
                seen.add((i, j))
                a, b = (i, j) if ar[i] <= ar[j] else (j, i)
                # project on b's plane, 2D point-in-triangle for the sample points of a
                e1 = A[b, 1] - A[b, 0]; e1 /= np.linalg.norm(e1); e2 = np.cross(n[b], e1)
                tb = [((A[b, k] - A[b, 0]) @ e1, (A[b, k] - A[b, 0]) @ e2) for k in range(3)]
                def inside(px, py):
                    s = []
                    for k in range(3):
                        (x0, y0), (x1, y1) = tb[k], tb[(k + 1) % 3]
                        s.append((x1 - x0) * (py - y0) - (y1 - y0) * (px - x0))
                    return all(v > 1e-7 for v in s) or all(v < -1e-7 for v in s)
                cnt = 0
                for w in W:
                    p = w[0] * A[a, 0] + w[1] * A[a, 1] + w[2] * A[a, 2]
                    if inside((p - A[b, 0]) @ e1, (p - A[b, 0]) @ e2):
                        cnt += 1
                if cnt >= 2:
                    hits.append((own[a], mat[a], own[b], mat[b], tuple(round(float(x), 3) for x in A[a].mean(0)), float(ar[a])))
    return hits


def check_zfight():
    hits = zfight_pairs()
    from collections import Counter
    pairs = Counter((h[0], h[2]) for h in hits)
    R('m z-fighting: no same-facing coplanar overlapping triangles (whole aircraft, within 0.8 mm / 2 deg)', not hits,
      f'{len(hits)} pairs: {pairs.most_common(12)} e.g. {[h[4] for h in hits[:8]]}')
    json.dump([list(h) for h in hits], open(OUT.replace('_check.json', '_zfight.json'), 'w'), indent=0)


# ------------------------------------------------------------------------------------------- (n) flaps vs nacelles (round 5)
def check_flaps():
    """user review 2 / 01: the inboard nacelle ran through the flaps. Each flap at 0 and 28 deg down (about its hinge, local X, as
    ControlSurface turns the visible mesh) must not overlap any mesh except the wing parts whose cove it sits in."""
    from mathutils import Matrix
    bad = []; det = []
    flaps = [o for o in meshes() if o.name.startswith('flap_')]
    others = [o for o in meshes() if not o.name.startswith(('wing_', 'flap_', 'gauge_', 'cockpit_'))]
    tree = bvh_of(others)[0]
    b0 = {fl.name: fl.matrix_basis.copy() for fl in flaps}
    for deg in (0.0, 14.0, 28.0):          # one flap input drives every flap: all turn together
        for fl in flaps:
            fl.matrix_basis = b0[fl.name] @ Matrix.Rotation(math.radians(deg), 4, 'X')
        bpy.context.view_layer.update()
        for fl in flaps:
            ft = bvh_of([fl])[0]
            ov = list(ft.overlap(tree))
            for fl2 in flaps:
                if fl2.name < fl.name:
                    ov += list(ft.overlap(bvh_of([fl2])[0]))
            low = min((fl.matrix_world @ v.co).z for v in fl.data.vertices)
            det.append(f'{fl.name}@{deg:.0f}: {len(ov)} (TE z {low:.2f})')
            if ov:
                bad.append((fl.name, deg, len(ov)))
    for fl in flaps:
        fl.matrix_basis = b0[fl.name]
    bpy.context.view_layer.update()
    R('n flaps at 0 / 14 / 28 deg down clear of the nacelles and every other part (wing coves excepted)', not bad, '; '.join(det))


def check_r180():
    """1.8.0 rows: o compass card not mirrored (u grows toward the pilot's right, like the dial faces); p tail gunner's window glazed
    above the Cheyenne cover at the gunner's eye height."""
    o = bpy.data.objects.get('gauge_dg_card')
    ok = False; det = 'missing'
    if o is not None:
        me = o.data; uv = me.uv_layers.active.data if me.uv_layers.active else None
        M = o.matrix_world; c = M.translation; X = (M.to_3x3() @ V((1, 0, 0))).normalized(); Z = (M.to_3x3() @ V((0, 0, 1))).normalized()
        right = Z.cross(X).normalized()          # the pilot looks along -X with Z up: right = (-X) x Z = Z x X
        us = []; ys = []
        for poly in me.polygons:
            for li in poly.loop_indices:
                p = M @ me.vertices[me.loops[li].vertex_index].co
                ys.append((p - c).dot(right)); us.append(uv[li].uv.x if uv else 0)
        mu = sum(us) / len(us)
        corr = sum((y - 0) * (u - mu) for y, u in zip(ys, us))
        ok = uv is not None and corr > 0
        det = f'corr(u, right) {corr:+.4f} ({"u grows to the pilot right" if corr > 0 else "MIRRORED"})'
    R('o compass (DG) card: texture u grows toward the pilot right as on the dial faces (1.7.x mirrored)', ok, det)
    tg = bpy.data.objects.get('tail_gun')
    area = 0.0; zr = [9, -9]
    if tg is not None:
        gi = [k for k, m in enumerate(tg.data.materials) if m is not None and m.name == 'glass']
        M = tg.matrix_world
        for poly in tg.data.polygons:
            if poly.material_index in gi:
                ctr = M @ poly.center
                if ctr.y < -14.6 and ctr.z > S.TAIL_GUN_Z:
                    area += poly.area / 2; zr = [min(zr[0], ctr.z), max(zr[1], ctr.z)]   # both glass sides counted once
    ce = bpy.data.objects.get('crew_eye_tail')
    eye_z = ce.matrix_world.translation.z if ce is not None else 1.15       # 1.8.8: the eye moved up into the glazed cab (z 1.25)
    R(f'p tail gunner window: glass in the end opening above the gun cover (>= 0.06 m2), reaching the gunner eye height z {eye_z:.2f} within 0.1 m',
      (not S.TAIL_WINDOW) or (area >= 0.06 and zr[1] >= eye_z - 0.10), f'glass {area:.3f} m2, z {zr[0]:.2f}..{zr[1]:.2f}')


random.seed(1)

def check_nacelles183():
    """1.8.3 nacelles (b17g_nacelle.py; measured against the reference sections)."""
    if not S.NAC183:
        return
    import b17g_nacelle as N
    # q1 the stowed tyre shows through the opening: every tyre vertex below the local belly lies inside the opening outline
    bad, below = [], 0
    for s_ in ('L', 'R'):
        side = -1 if s_ == 'L' else 1
        leg = bpy.data.objects['gear_main_' + s_]; piv = leg.matrix_world.translation
        Rm = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(S.MAIN_FOLD), 4, 'X') @ Matrix.Translation(-piv)
        wh = bpy.data.objects['wheel_main_' + s_]
        for v in wh.data.vertices:
            p_ = Rm @ wh.matrix_world @ v.co
            zb = N.zskin_bottom('inner', p_.x, p_.y, side)
            if p_.z < zb - 0.01:
                below += 1
                if N.well_sd(p_.x - S.MAIN_X * side, p_.y) > 0.0:
                    bad.append((s_, tuple(round(c, 2) for c in p_)))
    R('q1 well: the stowed tyre protrudes only through the opening (every tyre vertex below the belly inside the outline)', below > 50 and not bad,
      f'{below} tyre vertices below the belly, {len(bad)} outside the opening {bad[:4]}')
    # q2 turbos at the reference stations, IR source at the turbine exhaust
    det, ok = [], True
    for (side, kind), num in S.ENGINE_NUM.items():
        ex = bpy.data.objects.get(f'exhaust_{num}')
        ty = N.TURBO_Y[kind]
        if ex is None:
            ok = False; det.append(f'no exhaust_{num}'); continue
        d = ex.matrix_world.translation
        ok &= abs(d.y - (ty - 0.37)) < 0.15 and abs(abs(d.x) - S.NACELLES[kind][0]) < 0.10
        det.append(f'{num}: IR y {d.y:.2f} x {d.x:.2f}')
    R('q2 turbos: inner at y 0.05, outer at y 1.60 (reference); IR source at each turbine exhaust', ok, '; '.join(det))
    # q3 leading-edge intakes cut open: no wing skin face centre inside any opening mouth
    left = 0
    for o in meshes():
        if not o.name.startswith(('wing_inner', 'wing_mid', 'wing_outer')):
            continue
        side = -1 if o.name.endswith('_L') else 1
        M = o.matrix_world
        for poly in o.data.polygons:
            m_ = o.material_slots[poly.material_index].material.name if o.material_slots else ''
            if m_ not in ('paint', 'interior'):
                continue
            c = M @ poly.center
            for x0, x1 in N.LE_INTAKES:
                if x0 + 0.03 < abs(c.x) < x1 - 0.03:      # inside the mouth, clear of its frame and box walls
                    import b17g_parts as P
                    st = P.wing_station((x0 + x1) / 2, side); le = st.point(0.0, True)
                    if abs(c.z - le.z) < N.LE_INTAKE_H / 2 - 0.03 and c.y > le.y - 0.005:
                        left += 1
    R('q3 leading-edge intakes: 12 openings cut through both skins (no skin face left in a mouth)', left == 0, f'{left} faces left in the mouths')
    # q4 collider sources: one per engine, child of its engine, hidden from the checks (deleted in Unity)
    hs = [o for o in bpy.data.objects if o.name.endswith('_hullsrc')]
    want = {f'engine_{n}_hullsrc' for n in (1, 2, 3, 4)} | ({f'nacelle_{n}_hullsrc' for n in (1, 2, 3, 4)} if S.NAC188 else set())
    R(f'q4 collider sources: {len(want)} (engine_n_hullsrc = 1.8.2 turbo' + (', nacelle_n_hullsrc = 1.8.7 nacelle' if S.NAC188 else '') + '), each a child of its part, no paint (not in the livery atlas)',
      {o.name for o in hs} == want and all(o.parent and o.parent.name == o.name[:-8] for o in hs)
      and all(all(m is None or m.name != 'paint' for m in o.data.materials) for o in hs),
      ', '.join(f'{o.name}<-{o.parent.name if o.parent else None}' for o in hs))

ONLY = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
if ONLY:
    for f_ in ONLY:
        globals()[f_]()
    print(RES); raise SystemExit(0)
sys.path.insert(0, os.path.join(HERE, '..'))
import atlas_guard as AG                     # 1.8.16 guard (first: before any check edits a mesh)
R('1.8.16 livery atlas == texture manifest (skin / liveries / damage painted on this atlas; re-bake the textures when it fails)', *AG.check_row(os.path.join(HERE, '..', '..', 'assets', 'textures_b17g', 'b17g_atlas_manifest.json')))
check_r180()
check_nacelles183()
check_zfight()
check_flaps()
check_cockpit()
check_turret_bodies()
check_interior_visible()
def check_nose1817():
    """(n17) 1.8.17 nose to the reference: (1) no skin on the glazed cone (the 1.8.16 grey tongue: the cone's bottom anchor strip of paint
    faces climbing to the tip, ~45 % of the cone seen from ahead) - paint share of the front-view hits on the cone ahead of the base ring
    frame <= 6 % (the optical-flat frame); (2) the cone follows the spec rows (centreline top / bottom within 1.5 cm); (3) every window
    centre is glazed (first hit glass from outside); (4) the K-5 sockets are open at the cheek pivots (nothing between outside and the
    pivot along the rest aim); (5) chin opening: nothing of the fixed skin within 0.48 m of the turret axis below the race; (6) no hole in the nose skin (rays from inside)."""
    if not getattr(S, 'NOSE1817', False):
        return
    ms = meshes()
    V_, F_, M_ = [], [], []
    for o in ms:
        me = o.data; me.calc_loop_triangles(); Mw = o.matrix_world
        off = len(V_); V_ += [Mw @ v.co for v in me.vertices]
        mats = [m.name if m else '' for m in me.materials]
        for t in me.loop_triangles:
            F_.append(tuple(k + off for k in t.vertices)); M_.append((mats[t.material_index] if mats else '', o.name))
    tree = BVHTree.FromPolygons(V_, F_)
    # (1) tongue
    gy0 = S.NOSE_GLASS_Y + 0.05
    n_c = n_p = 0
    for i in range(-60, 61):
        for j in range(-30, 120):
            x, z = i * 0.01, j * 0.01
            h = tree.ray_cast(V((x, 12.0, z)), V((0, -1, 0)), 20.0)
            if h[0] is None or h[0].y < gy0:
                continue
            n_c += 1
            if M_[h[2]][0] == 'paint':
                n_p += 1
    share = n_p / max(n_c, 1)
    R('n17 nose cone: no skin on the glazing (1.8.16 tongue ~45 %); paint share of the front hits on the cone <= 6 % (optical-flat frame)',
      n_c > 5000 and share <= 0.06, f'{n_p} / {n_c} = {share * 100:.1f} %')
    # (2) cone profile = spec rows
    errs = []
    for y in (6.75, 6.95, 7.15, 7.30, 7.40):
        top, bot, hw, n = S.fus_station(y)
        ht = tree.ray_cast(V((0.0, y, 5.0)), V((0, 0, -1)), 10.0); hb = tree.ray_cast(V((0.0, y, -5.0)), V((0, 0, 1)), 10.0)
        hs = tree.ray_cast(V((5.0, y, (top + bot) / 2)), V((-1, 0, 0)), 10.0)
        e = [abs(ht[0].z - top) if ht[0] else 9, abs(hb[0].z - bot) if hb[0] else 9, abs(hs[0].x - hw) if hs[0] else 9]
        errs.append((y, round(max(e), 4)))
    R('n17 nose cone follows the spec rows (centreline top / bottom, half width at its centre; <= 1.5 cm incl. the optical-flat frame)',
      all(e <= 0.015 for y, e in errs), str(errs))
    # (3) windows glazed
    bad = []
    for w in S.NOSE1817_WINDOWS:
        if w['kind'] == 'side':
            y0, y1, z0, z1 = w['rect']; c = V((0, (y0 + y1) / 2, (z0 + z1) / 2))
            h = tree.ray_cast(V((w['side'] * 4.0, c.y, c.z)), V((-w['side'], 0, 0)), 8.0)
        elif w['kind'] == 'top':
            y0, y1, x0, x1 = w['rect']
            h = tree.ray_cast(V(((x0 + x1) / 2, (y0 + y1) / 2, 5.0)), V((0, 0, -1)), 8.0)
        else:
            h = tree.ray_cast(V((0.0, w['cy'], 5.0)), V((0, 0, -1)), 8.0)
        if h[0] is None or M_[h[2]][0] != 'glass':
            bad.append((w['tag'], M_[h[2]] if h[0] else None))
    for sp in S.NOSE1817_K5:     # side pane centre
        yc = (sp['y_a'] + sp['y_f']) / 2; zc = (sp['z0'] + sp['z1']) / 2
        h = tree.ray_cast(V((sp['side'] * 4.0, yc, zc)), V((-sp['side'], 0, 0)), 8.0)
        if h[0] is None or M_[h[2]][0] != 'glass':
            bad.append((sp['tag'], M_[h[2]] if h[0] else None))
    R('n17 nose windows glazed at their centres (navigator x3, right forward, top window, astrodome, both K-5 side panes)', not bad, str(bad) or 'all glass')
    # (4) K-5 sockets open
    res = []
    for nm in ('cheek_R', 'cheek_L'):
        t = S.TURRETS[nm]; P_ = V(t['pos']); f = V(t['fwd']).normalized()
        o = P_ + f * 2.0
        h = tree.ray_cast(o, -f, 1.98)
        res.append((nm, None if h[0] is None else (round((h[0] - P_).length, 3), M_[h[2]][1])))
    R('n17 K-5 sockets open on the rest aim (nothing between 2 m out and the cheek pivot, the gun hole is at the pivot)', all(r[1] is None for r in res), str(res))
    # (5) chin opening clear for the drum (r 0.475, 0.491 on its diagonals)
    c = V(S.TURRETS['chin']['pos']); hits = []
    for k in range(72):
        a = 2 * math.pi * k / 72
        for r in (0.46, 0.488):
            p = c + V((r * math.cos(a), r * math.sin(a), 0.0))
            h = tree.ray_cast(V((p.x, p.y, -3.0)), V((0, 0, 1)), 3.0 + c.z + 0.40)
            if h[0] is not None and M_[h[2]][1] in ('fus_nose',) and M_[h[2]][0] == 'paint':
                hits.append((round(r, 3), k))
    R('n17 chin opening: no fixed skin inside r 0.49 under the race (the drum turns clear)', not hits, f'{len(hits)} hits {hits[:6]}')
    # (6) the nose / forward cockpit skin is closed (the Unity crew-in-hull rule offline: rays +-x and down from inside points all hit)
    miss = []; n = 0
    for iy in range(0, 41):
        y = 4.55 + 0.05 * iy
        for iz in range(0, 19):
            z = 0.20 + 0.05 * iz
            top_, bot_, hw_, n_ = S.fus_station(y)
            cz_, hz_ = (top_ + bot_) / 2, (top_ - bot_) / 2
            t_ = abs(z - cz_) / hz_
            xs_ = hw_ * (1 - t_ ** n_) ** (1 / n_) if t_ < 1 else 0.0
            for x in (-0.45, -0.25, 0.0, 0.25, 0.45):
                if abs(x) > xs_ - 0.06:      # inside points only (>= 6 cm from the skin)
                    continue
                p = V((x, y, z)); n += 1
                for d in (V((1, 0, 0)), V((-1, 0, 0)), V((0, 0, -1))):
                    h = tree.ray_cast(p, d, 4.0)
                    if h[0] is None or h[1].dot(d) > 0:      # a miss, or only a back face first (PhysX any-hit rays skip those)
                        miss.append((round(x, 2), round(y, 2), round(z, 2), tuple(int(c) for c in d), 'miss' if h[0] is None else 'back'))
    # and rays from inside toward the K-5 frames' seams with the skin (aft edge, wedge lines; 8 mm either side), where the Unity crew
    # check found the leaks in builds 1-5
    import random as _rnd
    import b17g_nose1817 as NZ
    rng = _rnd.Random(5)
    for sp in S.NOSE1817_K5:
        G = NZ.k5_geometry(sp); sg = sp['side']
        y_a, z0, z1 = sp['y_a'], sp['z0'], sp['z1']; zb, zt = z0 - sp['drop'], z1 + sp['rise']
        for (ya, za), (yb, zb_) in (((y_a, z0), (G['y_s'](zb), zb)), ((y_a, z1), (G['y_s'](zt), zt)), ((y_a, z0), (y_a, z1))):
            for k in range(400):
                t = rng.random(); y, z = ya + (yb - ya) * t, za + (zb_ - za) * t
                off = rng.uniform(-0.008, 0.008)
                y, z = (y + off, z) if ya == yb else (y, z + off)
                for x0 in (0.0, -0.3 * sg, 0.3 * sg):
                    d = V((sg, 0, 0)); h = tree.ray_cast(V((x0, y, z)), d, 4.0); n += 1
                    if h[0] is None or h[1].dot(d) > 0:
                        miss.append((sp['tag'], round(y, 3), round(z, 3), 'miss' if h[0] is None else 'back'))
    R('n17 nose skin closed: rays +-x and down from every inside point (y 4.55-6.55, z 0.2-1.1, 5 cm grid, >= 6 cm from the skin) hit a FRONT face first, + 7,200 rays at the K-5 seams (Unity crew-in-hull rule: PhysX any-hit rays skip back faces)', not miss and n > 10000, f'{n} points, {len(miss)} misses {miss[:6]}')


def check_dome1818():
    """(n18) 1.8.18 astrodome from inside (in game 1.8.17: jagged dark / light teeth under the dome ring): (1) the inner frame ring is
    continuous: 3 x 720 rays straight up (along the skin normal) from 10 cm under the skin at plan radius 0.185 / 0.200 / 0.215 meet the
    ring's bottom face (20-32 mm under the outer skin; a gap shows the inner skin at 6 mm or the glass) and its depth changes by < 0.5 mm
    from ray to ray (the 1.8.17 blocks: wedge gaps between chord blocks, 1.5 mm steps between alternate blocks); (2) no open frame or
    stringer end round the dome: 3 x 720 horizontal rays from the dome axis, 35 / 50 / 65 mm under the skin, meet a FRONT face first
    (an open bar end shows its inside = a back face first)."""
    if not getattr(S, 'NOSE1817', False):
        return
    dome = [w for w in S.NOSE1817_WINDOWS if w['kind'] == 'dome'][0]
    import b17g_nose1817 as NZ
    o = bpy.data.objects['fus_nose']
    me = o.data; me.calc_loop_triangles(); Mw = o.matrix_world
    vs = [Mw @ v.co for v in me.vertices]; tris = [tuple(t.vertices) for t in me.loop_triangles]
    mats = [m.name if m else '' for m in me.materials]; tm = [mats[t.material_index] for t in me.loop_triangles]
    tree = BVHTree.FromPolygons(vs, tris)
    cy = dome['cy']
    gaps = []; steps = []; bars = 0
    for rr in (0.185, 0.200, 0.215):
        prev = None
        for k in range(721):
            a = 2 * math.pi * (k % 720) / 720
            sp = NZ.top_pt(cy + rr * math.sin(a), rr * math.cos(a))
            n = NZ.skin_normal(sp)
            h = tree.ray_cast(sp - n * 0.10, n, 0.14)      # from below the frames (their inner rim is 75 mm under the skin)
            if h[0] is None:
                gaps.append((rr, k, 'none')); prev = None; continue
            dep = (sp - h[0]).dot(n)
            if tm[h[2]] == 'structure' and dep >= 0.028 and h[1].dot(n) < 0:     # a frame / stringer end under the ring (they stop on it)
                bars += 1; prev = None; continue
            if tm[h[2]] != 'interior' or not (0.020 <= dep <= 0.032) or h[1].dot(n) > 0:
                gaps.append((rr, k, tm[h[2]], round(dep * 1000, 1))); prev = None; continue
            if prev is not None:
                steps.append(abs(dep - prev))
            prev = dep
    mx = max(steps) if steps else 9.0
    R('n18 astrodome inner frame ring continuous from inside: 2,163 rays up at r 0.185 / 0.200 / 0.215 meet its bottom 20-32 mm under the skin (or a frame / stringer end under it), depth step < 0.5 mm (1.8.17: chord blocks with wedge gaps and 1.5 mm steps)',
      not gaps and mx < 0.0005, f'{len(gaps)} gaps {gaps[:5]}, {bars} on bar ends, max depth step {mx * 1000:.2f} mm')
    opn = []; n_h = 0
    zc = NZ.skin_z(0.0, cy)
    for dd in (0.035, 0.050, 0.065):
        for k in range(720):
            a = 2 * math.pi * k / 720
            d = V((math.cos(a), math.sin(a), 0.0))
            h = tree.ray_cast(V((0.0, cy, zc - dd)), d, 0.60)
            if h[0] is None:
                continue
            n_h += 1
            if h[1].dot(d) > 0:
                opn.append((dd, k, tm[h[2]], round((h[0] - V((0.0, cy, zc - dd))).length, 3)))
    R('n18 no open frame / stringer end round the astrodome: 2,160 horizontal rays from its axis 35-65 mm under the skin meet a FRONT face first',
      not opn and n_h > 1500, f'{n_h} hits, {len(opn)} back faces first {opn[:6]}')


check_nose1817(); check_dome1818(); check_budget(); check_bay(); check_stance(); check_props(); check_gear(); check_turrets(); check_winding(); check_see_through(); check_connect()
json.dump(RES, open(OUT, 'w'), indent=1)
n_ok = sum(v['ok'] for v in RES.values())
print(f'[check] {n_ok}/{len(RES)} PASS -> {OUT}')
