"""MSB-17/80 model checks. Writes assets/model_msb1780/msb1780_check.json ({name: {ok, detail}}).

  blender --background assets/model_msb1780/msb1780.blend --python-exit-code 1 --python blender/msb1780/check_msb1780_model.py -- [--out ...]

The B-17G checks (blender/b17g/check_b17g_model.py) are run by exec with the MSB names where they test what the MSB keeps from the B-17G
(connectivity, see-through, winding, prop discs, gear swing, stance, z-fighting, flaps, interior seen from outside, budget, the 1.8.17 nose,
the 1.8.18 astrodome ring, the 1.8.16 livery-atlas guard), plus the MSB rows:
  (g) bay: every stock store of every bay arrangement inside the 5.7 m bay; side-bay stores inside the side bays and the skin
  (k) turrets: azimuth body + elevating parts + the twin 20 mm swept through traverse x elevation, no face crosses the static airframe;
      the cannon never crosses its own azimuth housing (the Blender side of the clearance sweep; Unity repeats it on the built prefab)
  (r) contra-rotating rows: no blade of one row meets a blade of the other at any relative angle
  (s) ejection paths: from each crew eye the seat column (5 lines, +-0.18 m across, +-0.15 m along) rises 6 m through its own hatch only
  (j) screens: from each crew eye the centre of every screen of its station is the first thing hit
"""
import bpy, sys, os, json, math
from mathutils import Vector as V, Matrix, Euler
from mathutils.bvhtree import BVHTree
HERE = os.path.dirname(os.path.abspath(__file__))
B17 = os.path.abspath(os.path.join(HERE, '..', 'b17g'))
for p_ in (os.path.join(HERE, '..', 'v2'), os.path.join(HERE, '..', 'nimrod'), B17, HERE):
    p_ = os.path.abspath(p_)
    if p_ not in sys.path:
        sys.path.insert(0, p_)
import b17g_spec as S
import msb_spec as M
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT_ = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'model_msb1780', 'msb1780_check.json')
# the B-17G checks read these keys (radio hatch / cheek guns the MSB does not have): far away, never hit
for k_ in ('radio', 'cheek_R', 'cheek_L'):
    S.TURRETS[k_] = dict(pos=(0.0, -99.0, 1.78), fwd=(0, 1, 0), guns=[], station='-', trav=0.0, emin=0.0, emax=0.0)
src = open(os.path.join(B17, 'check_b17g_model.py'), encoding='utf-8').read()
i_only = src.index("ONLY = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None")
i_n17 = src.index('def check_nose1817():')
i_end = src.index('check_nose1817(); check_dome1818(); check_budget();')
code = src[:i_only] + src[i_n17:i_end]
for a, b in ((r"OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(HERE, '..', '..', 'assets', 'model_b17g', 'b17g_check.json')", "OUT = OUT_"),
             ("'b17g_contract.json'", "'msb1780_contract.json'"),
             ("o.name.startswith(('fus_', 'B17G', 'tail_gun')) and not o.name.startswith('B17G_root')", "o.name.startswith(('fus_', 'MSB17', 'tail_gun')) and not o.name.startswith('MSB17_root')"),
             # the MSB has no K-5 cheek frames (S.NOSE1817_K5 = []), so the 7,200 seam rays do not exist: the grid alone (3,887 inside points x 3 rays)
             ("not miss and n > 10000, f'{n} points", "not miss and n > (10000 if S.NOSE1817_K5 else 3500), f'{n} points"),
             # grid points INSIDE the WSO console (a closed solid box on the nose floor, not a hull gap) see its back faces: skipped
             ("                p = V((x, y, z)); n += 1",
              "                p = V((x, y, z))\n                if _in_wso_console(p):\n                    continue\n                n += 1")):
    assert a in code, a[:60]
    code = code.replace(a, b)
WSO_SOLIDS = ('cockpit_wso_console', 'cockpit_wso_side_L', 'cockpit_wso_side_R', 'cockpit_wso_seatbase')


def _in_wso_console(p, pad=0.03):
    """p inside the world bounding box (+pad) of one of the WSO station's closed solids (console, side consoles, seat base): furniture,
    its inside sees back faces by construction (1.9.1: one object per solid, so no box spans the open cabin)."""
    from mathutils import Vector as _V
    for n_ in WSO_SOLIDS:
        o = bpy.data.objects.get(n_)
        if o is None or o.type != 'MESH':
            continue
        vs = [o.matrix_world @ _V(c) for c in o.bound_box]
        lo = _V((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))); hi = _V((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        if all(lo[i] - pad <= p[i] <= hi[i] + pad for i in range(3)):
            return True
    return False


ns = {'__name__': 'msb_check', '__file__': os.path.join(B17, 'check_b17g_model.py'), 'OUT_': OUT_, '_in_wso_console': _in_wso_console}
exec(compile(code, 'check_b17g_model.py (MSB-17/80)', 'exec'), ns)
R, meshes, bvh_of, descendants, info = ns['R'], ns['meshes'], ns['bvh_of'], ns['descendants'], ns['info']
RES = ns['RES']


def obj(n):
    return bpy.data.objects.get(n)


# ------------------------------------------------------------------------------------------- (g) bay + side bays
def check_bay_msb():
    import b17g_parts as P
    bad = []; n = 0
    for hp, stores in M.STORES.items():
        hx, hy, hz = M.BAY_HP[hp]
        for key, (x0, x1, y0, y1, z0, z1) in stores.items():
            n += 1
            X0, X1, Y0, Y1, Z0, Z1 = hx + x0, hx + x1, hy + y0, hy + y1, hz + z0, hz + z1
            bel = max(P.belly_z(abs(X0), (Y0 + Y1) / 2), P.belly_z(abs(X1), (Y0 + Y1) / 2))
            ok = X0 > -(S.BAY_HALF_W - 0.03) and X1 < S.BAY_HALF_W - 0.03 and Y0 > S.BAY_Y[0] + 0.02 and Y1 < S.BAY_Y[1] - 0.02 and Z1 < S.BAY_ROOF_Z - 0.03 and Z0 > bel - 0.06
            if not ok:
                bad.append(f'{hp}/{key}: x {X0:.2f}..{X1:.2f} y {Y0:.2f}..{Y1:.2f} z {Z0:.2f}..{Z1:.2f} (belly {bel:.2f})')
    R(f'g bay: every stock store of the three bay arrangements fits the 5.7 m bay (walls +-{S.BAY_HALF_W - 0.03:.2f}, bulkheads, roof {S.BAY_ROOF_Z}, not below the belly line)',
      not bad, f'{n} stores; {bad}')
    sb = M.SIDE_BAY; bad = []
    x0, x1, y0, y1, z0, z1 = sb['env']          # mount frame (x lateral, y along, z up/down) -> rolled: mount down = outboard
    for sx in (-1, 1):
        hx = sx * sb['hp_x']
        out_ = [hx + sx * (-z0), hx + sx * (-z1)]          # mount z0 (down, -0.32) -> outboard
        X_out, X_in = max(abs(v) for v in out_), min(abs(v) for v in out_)
        Ys = (sb['hp_y'] + y0, sb['hp_y'] + y1); Zs = (sb['hp_z'] + x0, sb['hp_z'] + x1)
        skin = min(P.fus_skin_x(y, z, 0.0) for y in (Ys[0], (Ys[0] + Ys[1]) / 2, Ys[1]) for z in Zs)
        ok = X_out < skin + 0.005 and X_in > sb['liner_x'] and sb['y'][0] <= Ys[0] and Ys[1] <= sb['y'][1] and sb['z'][0] <= Zs[0] and Zs[1] <= sb['z'][1]
        if not ok:
            bad.append(f'side {sx}: |x| {X_in:.2f}..{X_out:.2f} (skin {skin:.2f}) y {Ys[0]:.2f}..{Ys[1]:.2f} z {Zs[0]:.2f}..{Zs[1]:.2f}')
    R(f'g2 side bays: 2 x MMR-S3 inside each side bay (liner wall |x| {sb["liner_x"]}, inside the skin, inside the door outline)', not bad, f'{bad}')


# ------------------------------------------------------------------------------------------- (k) turret sweeps
def check_turrets_msb():
    bad = []; det = []
    for t in ('chin', 'tail', 'top', 'ball'):
        az, el, mount = obj(f'{t}_az'), obj(f'{t}_el'), obj(f'{t}_mount')
        if not (az and el and mount):
            bad.append(f'{t}: frames missing'); continue
        own = set(o.name for o in descendants(mount))
        az_objs = [o for o in descendants(az) if o.type == 'MESH' and o not in descendants(el) and not o.name.endswith('_race')]   # the B-17G chin race: a bearing ring inside the skin, reused as built
        el_objs = [o for o in descendants(el) if o.type == 'MESH']
        gun = [o for o in el_objs if o.name.endswith('_gun0')]
        static = [o for o in meshes() if o.name not in own and not o.name.startswith(('cockpit_', 'crew_'))]
        ts = bvh_of(static, skip_glass=False)[0]
        SN = [o.name for o in static for _ in o.data.loop_triangles]
        spec = S.TURRETS[t]
        tr = spec['trav']
        azs = list(range(0, 360, 10)) if tr >= 180 else [tr * k / 6 for k in range(-6, 7)]
        els = [spec['emin'] + (spec['emax'] - spec['emin']) * k / 8 for k in range(9)]
        b0a, b0e = az.matrix_basis.copy(), el.matrix_basis.copy()
        hits, self_hits, poses = [], [], 0
        for a in azs:
            for e in els:
                az.matrix_basis = b0a @ Matrix.Rotation(math.radians(a), 4, 'Z')
                el.matrix_basis = b0e @ Matrix.Rotation(math.radians(e), 4, 'X')
                bpy.context.view_layer.update(); poses += 1
                mv = bvh_of(az_objs + el_objs)[0]
                ov = mv.overlap(ts) if mv else []
                if ov:
                    nm = sorted({SN[j] for _, j in ov[:400]})[:3]
                    hits.append((round(a), round(e), len(ov), nm))
                if gun:
                    gt = bvh_of(gun)[0]; hb = bvh_of(az_objs)[0] if az_objs else None
                    so = gt.overlap(hb) if (gt and hb) else []
                    if so:
                        self_hits.append((round(a), round(e), len(so)))
        az.matrix_basis = b0a; el.matrix_basis = b0e
        bpy.context.view_layer.update()
        det.append(f'{t}: {poses} poses, airframe {len(hits)} {hits[:3]}, own housing {len(self_hits)} {self_hits[:3]}')
        if hits or self_hits:
            bad.append(t)
    R('k turrets: azimuth body + elevating parts + the twin 20 mm swept over traverse x elevation (10 deg / 9 steps): no face crosses the static airframe, the cannon never crosses its own housing',
      not bad, '; '.join(det))


# ------------------------------------------------------------------------------------------- (r) contra-rotating rows
def check_rows():
    bad = []
    for n in (1, 2, 3, 4):
        fh, ah = obj(f'prop_hub_{n}'), obj(f'prop_hub_{n}_aft')
        if not (fh and ah):
            bad.append(f'{n}: hubs missing'); continue
        fb = [o for o in fh.children if '_blade' in o.name]; ab = [o for o in ah.children if '_blade' in o.name]
        ax = (fh.matrix_world.translation - ah.matrix_world.translation).normalized()
        c = ah.matrix_world.translation
        tf = bvh_of(fb)[0]
        for k in range(12):
            ang = math.radians(5 * k)
            Rm = Matrix.Translation(c) @ Matrix.Rotation(ang, 4, ax) @ Matrix.Translation(-c)
            ta = bvh_of(ab, [Rm @ o.matrix_world for o in ab])[0]
            if ta.overlap(tf):
                bad.append(f'{n} at {5 * k} deg'); break
        gap = (fh.matrix_world.translation - ah.matrix_world.translation).length
        if gap < 0.45:
            bad.append(f'{n}: rows {gap:.2f} m apart')
    R('r contra-rotating rows: 6 + 6 blades, 0.50 m apart, no blade of one row meets the other at any relative angle (5 deg steps)', not bad, f'{bad}')


# ------------------------------------------------------------------------------------------- (s) ejection paths
def check_eject():
    if M.STOCK_DECK or getattr(M, 'DECK195', False):
        stock_kit(True)          # 1.9.1: the stock tub / sticks / throttle are in the seats' way too; 1.9.5: the single stock parts
    allm = [o for o in meshes() if not o.name.startswith(('hatch_', 'crew_'))]
    tree = bvh_of(allm)[0]
    names = []
    for o in allm:
        names += [o.name] * len(o.data.loop_triangles)
    hatch_tree = bvh_of([o for o in meshes() if o.name.startswith('hatch_')])[0]
    det = []; bad = []
    for role, eye in (('pilot', M.EYE_PILOT), ('copilot', M.EYE_COPILOT), ('wso', M.EYE_WSO), ('ewo', M.EYE_EWO)):
        e = V(eye)
        hits = []; through = 0
        for dx, dy in ((0, 0), (0.14, 0), (-0.14, 0), (0, 0.12), (0, -0.12)):
            o = e + V((dx, dy, -0.05))
            h = tree.ray_cast(o, V((0, 0, 1)), 6.0)
            if h[0] is not None:
                hits.append((names[h[2]], round(h[3], 2)))
            hh = hatch_tree.ray_cast(o, V((0, 0, 1)), 6.0) if hatch_tree else (None,)
            through += hh[0] is not None
        ok = not hits and through == 5
        det.append(f'{role}: {"clear" if not hits else hits[:3]}, {through}/5 lines through a hatch')
        if not ok:
            bad.append(role)
    stock_kit(False)
    R('s ejection paths: from each crew eye the seat column (+-0.14 m across, +-0.12 m along: the seat / headrest) rises 6 m through its own hatch and nothing else', not bad, '; '.join(det))


# ------------------------------------------------------------------------------------------- 1.9.1 stock EW-25 flight deck (in memory only)
_stock_objs = []


def stock_kit(on):
    """load (on=True) / remove the stock parts the contract places (stock_mesh.py reads the user's Blueprinter project; never saved)."""
    import stock_mesh as SMK
    global _stock_objs
    if on and not _stock_objs:
        con = json.load(open(os.path.join(ROOT, 'assets', 'model_msb1780', 'msb1780_contract.json')))
        for sp in con.get('stock_parts', []):
            _stock_objs.append(SMK.load(sp['mesh'], obj_name='stock_' + sp['name'], matrix=Matrix.Translation(V(sp['pos']))))
        bpy.context.view_layer.update()
    elif not on:
        for o in _stock_objs:
            me = o.data
            bpy.data.objects.remove(o)
            bpy.data.meshes.remove(me)
        _stock_objs = []


def check_stock_fit():
    """(q) the stock parts (1.9.1: EW-25 tub / tac screen / sticks / throttle; 1.9.5: sticks, throttle, lamps + our own deck parts) sit inside
    the hull: every 3rd vertex has airframe outboard (+-x) and above it; and the stock parts do not cross our deck parts."""
    deck195 = getattr(M, 'DECK195', False)
    if not (M.STOCK_DECK or deck195):
        return
    stock_kit(True)
    try:
        air = [o for o in meshes() if o.name.startswith(('fus_', 'MSB17', 'hatch_', 'top_')) and not o.name.startswith('MSB17_root')]
        tr = bvh_of(air)[0]                           # 1.9.5: + the dorsal laser turret (the 1.9.1 bay bulkhead top sits under its race)
        out = []
        n = 0
        ours = [o for o in meshes() if o.name in DECK_PARTS] if deck195 else []
        for o in _stock_objs + ours:
            for v in list(o.data.vertices)[::3]:
                p = o.matrix_world @ v.co
                n += 1
                if tr.ray_cast(p, V((1 if p.x >= 0 else -1, 0, 0)), 4.0)[0] is None or tr.ray_cast(p, V((0, 0, 1)), 4.0)[0] is None:
                    out.append((o.name, tuple(round(c, 2) for c in p)))
        hits = []
        if deck195:
            for so in _stock_objs:
                sb = bvh_of([so])[0]
                for o in meshes():
                    if o.name.startswith('cockpit_') or o.name.startswith(('hatch_', 'fus_cockpit')):
                        if sb.overlap(bvh_of([o])[0]):
                            hits.append((so.name, o.name))
            R('q 1.9.5 deck inside the hull (our panel / glare shield / pedestal / consoles / floor and the stock sticks / throttle / lamps: airframe outboard and above every sampled vertex), the stock parts cross none of our parts',
              not out and not hits and n > 3000, f'{n} vertices, outside {len(out)} {out[:4]}; overlaps {hits[:6]}')
            return
        tub = [o for o in _stock_objs if o.name == 'stock_cockpit_ew1_tub']
        if tub:
            tb = bvh_of(tub)[0]
            for o in meshes():
                if o.name in ('cockpit_overhead', 'cockpit_interior') or o.name.startswith(('hatch_pilot', 'cockpit_ewo_')):
                    if tb.overlap(bvh_of([o])[0]):
                        hits.append(o.name)
        R('q stock EW-25 flight deck inside the hull (tub, tac screen, sticks, throttle: airframe outboard and above every sampled vertex), clear of our deck parts',
          not out and not hits and n > 1000, f'{n} vertices, outside {len(out)} {out[:4]}; overlaps {hits}')
    finally:
        stock_kit(False)


DECK_PARTS = ('cockpit_interior', 'cockpit_panel', 'cockpit_glareshield', 'cockpit_pedestal', 'cockpit_console_L', 'cockpit_console_R')
ALLOWED_STOCK195 = {'sfb_joystick', 'sfb_throttle', 'EW1_warningLights'}     # single stock parts (memory kitbash-stock-parts); seats ride on the figures


def _seats():
    """the stock ejection seats where the crew figures put them (COIN figure: seat = helmet eye + (0, +0.0241 fwd, -0.6929 up), turned with
    the figure: the EWO faces +x); in memory only."""
    import stock_mesh as SMK
    con = json.load(open(os.path.join(ROOT, 'assets', 'model_msb1780', 'msb1780_contract.json')))
    out = []
    for role, e in con['eyes'].items():
        fwd = V((1, 0, 0)) if role == 'ewo' else V((0, 1, 0))
        rot = Matrix.Rotation(-math.pi / 2, 4, 'Z') if role == 'ewo' else Matrix.Identity(4)
        pos = V(e) + fwd * 0.0241 + V((0, 0, -0.6929))
        out.append(SMK.load('ejectionSeat', obj_name='stock_seat_' + role, matrix=Matrix.Translation(pos) @ rot))
    bpy.context.view_layer.update()
    return out


def _drop(objs):
    for o in objs:
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)


def check_deck195():
    """(t) the 1.9.5 own flight deck: only single stock parts; the stock seats / sticks / throttle / lamps cross none of our parts, also with
    the sticks at full deflection and the throttle from idle to full; the glare shield ends at the panel ends and stays under both pilots'
    sight line to the windscreen bottom; the MFD units sit inside the panel face."""
    if not getattr(M, 'DECK195', False):
        return
    import msb_deck195 as MDK
    con = json.load(open(os.path.join(ROOT, 'assets', 'model_msb1780', 'msb1780_contract.json')))
    meshes_ = {sp['mesh'] for sp in con.get('stock_parts', [])}
    R('t1 1.9.5 no whole stock cockpit: the contract places only single stock parts (sfb_joystick x2, sfb_throttle x1, EW1_warningLights x2)',
      meshes_ <= ALLOWED_STOCK195 and len(con['stock_parts']) == 5 and not any('cockpit' in m or 'Screen' in m or 'tacscreen' in m.lower() for m in meshes_),
      f"{[(sp['name'], sp['mesh']) for sp in con['stock_parts']]}")
    stock_kit(True)
    seats = _seats()
    try:
        ours = [o for o in meshes() if o.name.startswith('cockpit_') or o.name in ('fus_cockpit',) or o.name.startswith('hatch_')]
        ours_t = {o.name: bvh_of([o])[0] for o in ours}

        def crossing(objs):
            hits = []
            for so in objs:
                sb = bvh_of([so])[0]
                for n_, t_ in ours_t.items():
                    if t_ is not None and sb.overlap(t_):
                        hits.append((so.name, n_))
            return hits
        hs = crossing(seats)
        R('t2 1.9.5 stock ejection seats (4, on the figures) cross none of our parts (deck, consoles, pedestal, stations, hatches, cabin skin)', not hs, f'{hs[:8]}')
        # sticks: pitch +-12, roll +-12 (Cockpit.Joystick: localEulerAngles (pitch x 12, 0, -roll x 12) about the mesh origin = the anchor);
        # Unity -> Blender is a mirror (y <-> z): Unity +x rotation (top forward) = Blender -x rotation; Unity -z roll (top right) = Blender +y
        # rotation by the roll angle (top toward +x). Throttle: rotation about x by throttle x 52 (lever tops forward).
        bad = []
        poses = 0
        for so in [o for o in _stock_objs if o.name.startswith(('stock_stick_', 'stock_cockpit_throttle'))]:
            m0 = so.matrix_world.copy()
            piv = m0.translation.copy()
            angs = [(p_, r_) for p_ in (-12, 0, 12) for r_ in (-12, 0, 12)] if 'stick' in so.name else [(a, 0) for a in (0, 13, 26, 39, 52)]
            for pa, ra in angs:
                rot = Matrix.Rotation(math.radians(-pa), 4, 'X') @ Matrix.Rotation(math.radians(ra), 4, 'Y')
                so.matrix_world = Matrix.Translation(piv) @ rot
                bpy.context.view_layer.update()
                poses += 1
                sb = bvh_of([so])[0]
                for h in crossing([so]) + [(so.name, s_.name) for s_ in seats if sb.overlap(bvh_of([s_])[0])]:
                    bad.append((h, pa, ra))
            so.matrix_world = m0
        bpy.context.view_layer.update()
        R('t3 1.9.5 sticks at full deflection (pitch / roll +-12 deg) and the throttle from idle to full (0..52 deg): no contact with our parts or the seats',
          not bad and poses == 2 * 9 + 5, f'{poses} poses; contacts {bad[:6]}')
        # glare shield ends at the panel ends; under the pilots' sight line to the windscreen bottom
        gs, pn = obj('cockpit_glareshield'), obj('cockpit_panel')
        gx = max(abs((gs.matrix_world @ v.co).x) for v in gs.data.vertices)
        px = max(abs((pn.matrix_world @ v.co).x) for v in pn.data.vertices)
        worst, wat = 9.0, None
        for e in (M.EYE_PILOT, M.EYE_COPILOT):
            for v in gs.data.vertices:                # the sight line from the eye to the windscreen bottom at the vertex's own x
                p = gs.matrix_world @ v.co
                zs = MDK.interp(MDK.SILL, p.x)
                if True:
                    t_ = (p.y - e[1]) / (4.55 - e[1])
                    if 0 < t_ < 1:
                        zl = e[2] + (zs - e[2]) * t_
                        if zl - p.z < worst:
                            worst, wat = zl - p.z, (round(e[0], 2), round(p.x, 2), round(p.y, 2), round(p.z, 3))
        R("t4 1.9.5 glare shield stops at the panel ends and stays under both pilots' sight line to the windscreen bottom",
          gx <= px + 0.001 and worst >= 0.0, f'shield |x| max {gx:.3f}, panel {px:.3f}; min gap under the sight line {worst * 1000:.0f} mm at (eye x, x, y, z) {wat}')
        bad_u = []
        for role, x, z, w, h, c in MDK.MFDS:
            W, H = w + 2 * MDK.BEZEL, h + 2 * MDK.BEZEL
            for dx in (-W / 2, W / 2):
                for dz in (-H / 2, H / 2):
                    xx, zz = x + dx, z + dz
                    if abs(xx) > MDK.PANEL_X - 0.01 or zz < MDK.PANEL_ZB + 0.01 or zz > MDK.z_top(xx) - 0.01:
                        bad_u.append(role)
        R('t5 1.9.5 MFD units (screen + bezel) inside the panel face, >= 1 cm from its edges', not bad_u, f'{sorted(set(bad_u))}')
        if getattr(M, 'DETAIL196', False):      # 1.9.6: the annunciator lamps / backlit legends on the panel are seen (not hidden under the glare-shield lip)
            allm = [o for o in meshes() if not o.name.startswith('crew_')] + seats
            tree, _, _ = bvh_of(allm)
            names = []
            for o in allm:
                names += [o.name] * len(o.data.loop_triangles)
            pn = obj('cockpit_panel'); me = pn.data; me.calc_loop_triangles()
            lamps = [t for t in me.loop_triangles if me.materials[t.material_index].name.startswith(('ck_amber', 'ck_green'))]
            seen = 0
            for t in lamps:
                c = pn.matrix_world @ t.center
                nw = (pn.matrix_world.to_3x3() @ t.normal).normalized()
                vis = False
                for e in (V(M.EYE_PILOT), V(M.EYE_COPILOT)):
                    if nw.dot(e - c) <= 0:
                        continue
                    d = c - e
                    h = tree.ray_cast(e, d.normalized(), d.length + 0.01)
                    if h[0] is not None and names[h[2]] == 'cockpit_panel' and (h[0] - c).length < 0.004:
                        vis = True
                seen += vis
            R('t6 1.9.6 panel annunciator / gear lamps seen from a pilot eye (not under the glare-shield lip, not behind a stick)', lamps and seen >= 0.9 * len(lamps), f'{seen}/{len(lamps)} lamp triangles seen')
    finally:
        _drop(seats)
        stock_kit(False)


def check_blades():
    """(p) 1.9.1 prop blades: no self-intersection (triangle pairs that share no vertex never cross), the twist falls monotonically root ->
    tip past the shank, both rows present (the aft row mirrored: counter-rotation kept)."""
    import msb_parts as MPX
    from mathutils.bvhtree import BVHTree as _B
    rings, xcs, rs = MPX.blade_sections()
    bad = []; crumple = []
    sample = [o for o in meshes() if '_blade' in o.name and '_aft' not in o.name][:3] + [o for o in meshes() if '_aft_blade' in o.name][:3]
    for o in sample:
        me = o.data
        me.calc_loop_triangles()
        key = {}
        weld = [key.setdefault((round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5)), len(key)) for v in me.vertices]   # caps / fans have own vertices
        vs = [None] * len(key)
        for v, w_ in zip(me.vertices, weld):
            vs[w_] = v.co.copy()
        tris = [tuple(weld[i] for i in t.vertices) for t in me.loop_triangles]
        t = _B.FromPolygons(vs, tris, all_triangles=True)
        cross = [(a, b) for a, b in t.overlap(t) if a < b and not set(tris[a]) & set(tris[b])]
        if cross:
            bad.append((o.name, len(cross)))
        # crumple measure: the dihedral across chordwise edges (between radial stations) on the paddle (r 0.5-1.55): a smooth twisted
        # blade turns a few degrees per station; kinks / crumples show as large angles
        far = max(vs, key=lambda q: q.length)
        rad = far.normalized()
        nrm = [((vs[c] - vs[a_]).cross(vs[b_] - vs[a_])).normalized() for a_, b_, c in [(tr[0], tr[1], tr[2]) for tr in tris]]
        nrm = [((vs[tr[1]] - vs[tr[0]]).cross(vs[tr[2]] - vs[tr[0]])) for tr in tris]
        nrm = [n_.normalized() if n_.length > 1e-12 else n_ for n_ in nrm]
        edges = {}
        for fi, tr in enumerate(tris):
            for e_ in ((tr[0], tr[1]), (tr[1], tr[2]), (tr[2], tr[0])):
                edges.setdefault(tuple(sorted(e_)), []).append(fi)
        angs = []
        for (ia, ib), fs in edges.items():
            if len(fs) != 2:
                continue
            d = vs[ib] - vs[ia]
            r_ = (vs[ia] + vs[ib]).dot(rad) / 2
            if d.length < 1e-6 or abs(d.normalized().dot(rad)) > 0.3 or not (0.5 < r_ < 1.55):
                continue
            n1, n2 = nrm[fs[0]], nrm[fs[1]]
            if n1.length < 0.5 or n2.length < 0.5:
                continue
            angs.append(math.degrees(n1.angle(n2)))
        angs.sort()
        crumple.append((o.name, round(angs[int(0.95 * (len(angs) - 1))], 1) if angs else -1, round(angs[-1], 1) if angs else -1))
    n = len(rings[0])
    betas = []
    for ring, r in zip(rings, rs):
        if r < 0.55:                                  # the round shank / blend has no chord line
            continue
        d = ring[n // 2] - ring[0]                    # trailing edge -> leading edge
        betas.append(math.degrees(math.atan2(d.y, d.x)))
    mono = all(b1 <= b0 + 0.3 for b0, b1 in zip(betas, betas[1:]))
    rows = bool([o for o in meshes() if '_aft_blade' in o.name]) and bool([o for o in meshes() if '_blade' in o.name and '_aft' not in o.name])
    R('p prop blades clean: no self-intersecting triangles, no crumple (dihedral across chordwise edges on the paddle <= 25 deg), twist falls monotonically root -> tip, both rows present (counter-rotating)',
      not bad and mono and rows and len(sample) == 6 and all(0 <= c[2] <= 25.0 for c in crumple), f'self-crossing {bad}; chordwise-edge dihedral p95 / max {crumple[:2]}; twist {betas[0]:.1f} -> {betas[-1]:.1f} deg (monotonic {mono}); {len(rs)} stations x {n} points')


# ------------------------------------------------------------------------------------------- (j) screens seen from the eyes
def check_screens():
    deck = ['stock_cockpit_ew1_tacscreen'] if M.STOCK_DECK else ['mfd_left', 'cockpit_screen_pilot', 'mfd_center', 'cockpit_screen_copilot', 'mfd_right']
    deckL = deckR = deck
    if getattr(M, 'DECK195', False):        # 1.9.5: each pilot's own map + systems MFDs and the shared centre stack
        deckL = ['cockpit_screen_deck_mapL', 'cockpit_screen_deck_sysL', 'cockpit_screen_deck_attC', 'cockpit_screen_deck_stbyC']
        deckR = ['cockpit_screen_deck_mapR', 'cockpit_screen_deck_sysR', 'cockpit_screen_deck_attC', 'cockpit_screen_deck_stbyC']
    if M.STOCK_DECK or getattr(M, 'DECK195', False):
        stock_kit(True)                     # the stock sticks / throttle may stand in a sight line
    stations = {'pilot': deckL,
                'copilot': deckR,
                'wso': ['cockpit_screen_wso1', 'cockpit_screen_wso2'], 'ewo': ['cockpit_screen_ewo1', 'cockpit_screen_ewo2']}
    allm = [o for o in meshes() if not o.name.startswith(('crew_',))]
    tree = bvh_of(allm)[0]
    names = []
    for o in allm:
        names += [o.name] * len(o.data.loop_triangles)
    eyes = {'pilot': M.EYE_PILOT, 'copilot': M.EYE_COPILOT, 'wso': M.EYE_WSO, 'ewo': M.EYE_EWO}
    bad = []; n = 0
    for role, scr in stations.items():
        e = V(eyes[role])
        for s in scr:
            o = obj(s)
            if o is None:
                bad.append(f'{role}: {s} missing'); continue
            me_ = o.data; me_.calc_loop_triangles()
            tri_ = sorted(me_.loop_triangles, key=lambda t: -t.area)[:max(3, len(me_.loop_triangles) // 4)]
            vis = 0
            for t_ in tri_:                           # 1.9.1: the share of the screen's larger triangles seen from the eye (>= 60 %)
                c = o.matrix_world @ t_.center
                d = (c - e)
                h = tree.ray_cast(e, d.normalized(), d.length + 0.05)
                vis += h[0] is not None and names[h[2]] == s
            n += 1
            if vis < 0.6 * len(tri_):
                bad.append(f'{role} -> {s}: {vis}/{len(tri_)} seen')
    stock_kit(False)
    R('j screens: from each crew eye the centre of every screen of its station is the first thing hit', not bad, f'{n} sight lines; {bad[:6]}')


# ------------------------------------------------------------------------------------------- run
sys.path.insert(0, os.path.join(HERE, '..'))
import atlas_guard as AG
R('1.8.16 livery atlas == texture manifest (skin / liveries / damage painted on this atlas; re-bake the textures when it fails)',
  *AG.check_row(os.path.join(ROOT, 'assets', 'textures_msb1780', 'msb17_atlas_manifest.json')))
def check_props_msb():
    """(d) both rows of every engine: disc points (0.6 / 0.8 / 1.0 R, 72 around) >= 0.15 m from the fuselage (unsigned distance), and no other
    part (wing, nacelles of the neighbour, other props; the own spinner / cowl excepted) within 5 cm of a disc."""
    fus = [o for o in meshes() if o.name.startswith(('fus_', 'MSB17', 'tail_gun', 'hatch_')) and not o.name.startswith('MSB17_root')]
    tf = bvh_of(fus)[0]
    worst = 9.0; others = []
    for p in [o for o in bpy.data.objects if o.type == 'EMPTY' and o.name.startswith('prop_') and info(o).get('kind') in ('prop', 'prop_row')]:
        num = info(p).get('engine')
        rest = [o for o in meshes() if not o.name.startswith(('prop_hub_', f'engine_{num}', f'nacelle_{num}', 'gear_', 'wheel_', 'tyre_', f'exhaust_{num}'))]
        tr = bvh_of(rest)[0]
        c = p.matrix_world.translation
        for k in range(72):
            a = 2 * math.pi * k / 72
            for rf in (0.6, 0.8, 1.0):
                q = c + V((math.cos(a), 0, math.sin(a))) * S.PROP_R * rf
                h = tf.find_nearest(q)
                if h[0] is not None:
                    worst = min(worst, h[3])
                if tr.find_nearest(q, 0.05)[0] is not None:
                    others.append(p.name)
    R('d prop discs (both rows) >= 0.15 m from the fuselage', worst >= 0.15, f'min clearance {worst:.3f} m')
    R('d2 prop discs clear of every other part (wing, other props, neighbour nacelles)', not others, f'{sorted(set(others))[:6]}')


_meshes0 = meshes
def _nose_check():
    """the B-17G nose rows look at the nose skin / glazing: the chin cannon (the yoke plate under the cone) and the props parked beside the
    navigator windows are not nose skin"""
    ns['meshes'] = lambda: [o for o in _meshes0() if not o.name.startswith(('prop_hub_', 'chin_gun', 'chin_ball', 'chin_muzzle'))]
    try:
        ns['check_nose1817']()
    finally:
        ns['meshes'] = _meshes0
ns['check_nose_msb'] = _nose_check
ns['check_props_msb'] = check_props_msb
ONLY_ = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
if ONLY_:
    loc = {f.__name__: f for f in (check_bay_msb, check_turrets_msb, check_rows, check_eject, check_screens, check_stock_fit, check_blades, check_deck195)}
    for f_ in ONLY_:
        (loc.get(f_) or ns.get(f_) or globals()[f_])()
    for k, v in RES.items():
        print('[only]', 'PASS' if v['ok'] else 'FAIL', k[:80], '|', v['detail'][:500])
    raise SystemExit(0)
for fn in ('check_zfight', 'check_flaps', 'check_interior_visible', 'check_nose_msb', 'check_dome1818', 'check_budget', 'check_stance', 'check_props_msb',
           'check_gear', 'check_winding', 'check_see_through', 'check_connect'):
    try:
        ns[fn]()
    except Exception as ex:
        import traceback; traceback.print_exc()
        R(f'{fn} ran', False, f'{type(ex).__name__}: {ex}')
def check_197():
    """1.9.7 rows: (u) faceting, (v) tail windows plated, (t7) throttle levers in the quadrant gate."""
    import facet_scan197 as FS
    import stock_mesh as SMESH
    res = FS.scan([o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('stock_')])
    tot = sum(v['facet_len'] for v in res.values()); worst = max(res.items(), key=lambda kv: kv[1]['facet_len'])
    worst_d = max((v['worst'] for v in res.values()), default=0.0)
    R('u 1.9.7 faceting: no surface meant to be curved shades as separate polygons (same-material faces meeting at 4-38 deg whose corner normals '
      'differ by > 4 deg): every object <= 0.3 m of facet edges, total <= 1.0 m (1.9.6: 141.3 m; bay doors 28.7 m each, side-bay doors 11.0 m each)',
      M.SMOOTH197 and tot <= 1.0 and worst[1]['facet_len'] <= 0.3, f"total {tot:.2f} m over {sum(1 for v in res.values() if v['facet_edges'])} objects, worst {worst[0]} {worst[1]['facet_len']:.2f} m, max facet dihedral {worst_d:.1f} deg")
    # (v) tail: no glass left in the tail cab / tail cone; the cab is skin
    gl = {}
    for n in ('tail_gun', 'fus_tail'):
        o = bpy.data.objects.get(n)
        if o is None:
            continue
        mats = [m.name if m else '' for m in o.data.materials]
        gl[n] = (sum(1 for p_ in o.data.polygons if mats[p_.material_index] == 'glass'), sum(1 for p_ in o.data.polygons if mats[p_.material_index] == 'paint'))
    C = S.TAIL_CAB
    o = bpy.data.objects.get('tail_gun'); pane = 0
    if o is not None:
        mats = [m.name if m else '' for m in o.data.materials]
        for p_ in o.data.polygons:
            c = o.matrix_world @ p_.center
            if mats[p_.material_index] == 'paint' and C['z_sill'] < c.z < C['z_top'] and C['main'][0] < c.y < C['main'][1] and abs(c.x) > 0.15 and (o.matrix_world.to_3x3() @ p_.normal).x * c.x > 0:
                pane += 1
    R('v 1.9.7 tail windows plated: no glass face in tail_gun / fus_tail (no human tail gunner), the former main side panes are outer paint skin',
      M.TAIL_PLATED197 and all(g == 0 for g, _ in gl.values()) and len(gl) == 2 and pane >= 4, f'glass / paint faces {gl}; outer paint faces on the former main panes {pane}')
    # (t7) throttle levers stand in the quadrant gate
    verts, _t = SMESH.read('sfb_throttle')
    bv = [(x, z, y) for x, y, z in verts]                      # Blender frame, lever-local (pivot at the origin)
    rr = [math.hypot(p_[1], p_[2]) for p_ in bv]; rmin = min(rr)
    foot = [p_ for p_, r_ in zip(bv, rr) if r_ < rmin + 0.02]
    knob = [r_ for p_, r_ in zip(bv, rr) if abs(p_[0]) < M.QUAD_SLOT_X[0] - 0.001 or abs(p_[0]) > M.QUAD_SLOT_X[1] + 0.001]
    ax0, ax1 = min(abs(p_[0]) for p_ in foot), max(abs(p_[0]) for p_ in foot)
    fa = [math.degrees(math.atan2(p_[1], p_[2])) for p_ in foot]
    import msb_deck195 as DK
    k0, k1 = M.QUAD_SLOT_K
    step = (DK.GATE_A1 - DK.GATE_A0) / 24.0; s0, s1 = DK.GATE_A0 + k0 * step, DK.GATE_A0 + k1 * step
    marg = min(min(fa) - s0, s1 - (max(fa) + M.SFB_THROTTLE_RANGE))
    side = min(ax0 - M.QUAD_SLOT_X[0], M.QUAD_SLOT_X[1] - ax1)
    ped = bpy.data.objects.get('cockpit_pedestal'); ty, tz = M.throttle_anchor()[1], M.throttle_anchor()[2]
    top_r = 0.0; in_slot = 0
    if ped is not None:
        for p_ in ped.data.polygons:
            c = ped.matrix_world @ p_.center; n_ = ped.matrix_world.to_3x3() @ p_.normal
            r_ = math.hypot(c.y - ty, c.z - tz)
            if r_ < 0.15 or r_ > 0.26 or abs(c.x) > 0.12:      # the quadrant housing only (the forward deck / aft extension lie outside)
                continue
            rad = V((0, c.y - ty, c.z - tz)).normalized()
            if n_.dot(rad) < 0.9:
                continue
            top_r = max(top_r, r_)
            ang = math.degrees(math.atan2(c.y - ty, c.z - tz))
            if r_ > rmin and M.QUAD_SLOT_X[0] < abs(c.x) < M.QUAD_SLOT_X[1] and s0 < ang < s1:
                in_slot += 1
    R('t7 1.9.7 throttle levers stand IN the quadrant gate from idle to full: housing top >= 12 mm above the arm foot, >= 3 mm of slot each side of the arm, '
      'slot longer than the arm travel by >= 2 deg each end, no housing-top face inside a slot, knobs >= 20 mm above the top',
      M.QUADRANT197 and top_r - rmin >= 0.012 and side >= 0.003 and marg >= 2.0 and in_slot == 0 and min(knob) - top_r >= 0.020,
      f'arm foot r {rmin * 1000:.0f} mm |x| {ax0 * 1000:.0f}-{ax1 * 1000:.0f}, angles {min(fa):.1f}..{max(fa):.1f} idle (+{M.SFB_THROTTLE_RANGE:.0f} full); housing top r {top_r * 1000:.0f} mm, '
      f'slot |x| {M.QUAD_SLOT_X[0] * 1000:.0f}-{M.QUAD_SLOT_X[1] * 1000:.0f}, {s0:.1f}..{s1:.1f} deg (margin {marg:.1f}); side clearance {side * 1000:.0f} mm; knob {min(knob) * 1000:.0f} mm; top faces in a slot {in_slot}')


for f_ in (check_bay_msb, check_turrets_msb, check_rows, check_eject, check_screens, check_stock_fit, check_blades, check_deck195, check_197):
    try:
        f_()
    except Exception as ex:
        import traceback; traceback.print_exc()
        R(f'{f_.__name__} ran', False, f'{type(ex).__name__}: {ex}')
json.dump(RES, open(OUT_, 'w'), indent=1)
n_ok = sum(v['ok'] for v in RES.values())
print(f'[check] {n_ok}/{len(RES)} PASS -> {OUT_}')
