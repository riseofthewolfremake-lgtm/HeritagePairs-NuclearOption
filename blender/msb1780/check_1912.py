"""1.9.12 MSB-17 model rows (called by check_msb1780_model.py): the spoiler panels (x1-x3), the formation-light strips (y1-y3) and the
z-fighting rows of the new plates (z, z2, z3: true distances; row m leaves the plates out).
Everything is MEASURED on the saved .blend (BVH of the built meshes), not recomputed from the spec formulas.
"""
import math, json
import bpy
from mathutils import Vector as V, Matrix
from mathutils.bvhtree import BVHTree
import b17g_spec as S
import msb_spec as M


def _tri_bvh(o, mats=None, with_uv=False):
    """BVH of the world-space EXPORT triangles of o (bmesh.ops.triangulate with its defaults = blender/b17g/export_b17g.py) whose material
    is in mats; with_uv -> also the livery UV of each triangle corner."""
    import bmesh
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.verts.ensure_lookup_table()
    names = [m.name if m else '' for m in o.data.materials]
    uvl = bm.loops.layers.uv.get('livery')
    Mw = o.matrix_world
    vs = [Mw @ v.co for v in bm.verts]
    fs, uvs = [], []
    for f in bm.faces:
        if mats is not None and names[f.material_index] not in mats:
            continue
        fs.append(tuple(v.index for v in f.verts))
        if with_uv and uvl is not None:
            uvs.append([tuple(l[uvl].uv) for l in f.loops])
    bm.free()
    return (BVHTree.FromPolygons(vs, fs) if fs else None), vs, fs, uvs


def _bary(p, a, b, c):
    v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-18:
        return 1.0, 0.0, 0.0
    v = (d11 * d20 - d01 * d21) / den; w = (d00 * d21 - d01 * d20) / den
    return 1 - v - w, v, w


def _world_polys(o):
    names = [m.name if m else '' for m in o.data.materials]
    Mw = o.matrix_world; R3 = Mw.to_3x3()
    for p in o.data.polygons:
        yield p, names[p.material_index], [Mw @ o.data.vertices[i].co for i in p.vertices], (R3 @ p.normal).normalized()


def _want_panels():
    return {f'airbrake_{k}_{s}': M.SPOILER_PART[k] + s for k in M.SPOILER_X for s in ('L', 'R')}


def check_spoilers(R, meshes, obj):
    con = json.load(open(bpy.path.abspath('//msb1780_contract.json')))
    panels = (con.get('airbrake') or {}).get('panels', [])
    allab = sorted(o.name for o in bpy.data.objects if o.name.startswith('airbrake_'))
    if not M.SPOILERS1912:
        R('x1 1.9.12 spoiler panels: flag off, no airbrake_* object and no contract key', not allab and 'airbrake' not in con, f'{allab[:4]}')
        return
    bad, det = [], []
    want = _want_panels()
    NP = len(want)
    if sorted(p['name'] for p in panels) != sorted(want) or len(allab) != 3 * NP:
        bad.append(f'contract panels {[p["name"] for p in panels]}, {len(allab)} airbrake_* objects ({3 * NP} expected)')
    skin_bvh = {}
    px = 1.0 / 4096.0
    worst_uv = 0.0; h_top = [9, -9]; h_bot = [9, -9]; h_bed = [9, -9]; n_uv = 0
    for name, wing in want.items():
        o, h, b, wg = obj(name), obj(name + '_hinge'), obj(name + '_bed'), obj(wing)
        if not (o and h and b and wg):
            bad.append(f'{name}: object / hinge / bed / wing missing'); continue
        if h.type != 'EMPTY' or h.parent != wg or o.parent != h or b.parent != wg or o.type != 'MESH' or b.type != 'MESH':
            bad.append(f'{name}: hierarchy (hinge under {h.parent.name if h.parent else None}, panel under {o.parent.name if o.parent else None}, bed under {b.parent.name if b.parent else None})')
        mats = [m.name for m in o.data.materials]
        if mats[:1] != ['paint'] or set(mats) != {'paint', 'cove', 'gear'} or [m.name for m in b.data.materials] != ['cove', 'gear']:
            bad.append(f'{name}: materials {mats} / bed {[m.name for m in b.data.materials]}')
        if max(abs(o.matrix_world[i][j] - h.matrix_world[i][j]) for i in range(4) for j in range(4)) > 1e-5:
            bad.append(f'{name}: the panel does not rest at identity under its hinge')
        # hinge frame: +X = hinge line (+x), +Z = skin normal (up), +Y = forward
        hx, hy, hz = (h.matrix_world.to_3x3() @ V(e) for e in ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        if hx.x < 0.95 or hz.z < 0.95 or hy.y < 0.95:
            bad.append(f'{name}: hinge frame x {tuple(round(c, 2) for c in hx)} z {tuple(round(c, 2) for c in hz)}')
        tree, vs, fs, uvs = skin_bvh.setdefault(wing, _tri_bvh(wg, ('paint',), True))
        # the paint face wears the paint of the skin under it: at every corner, the wing skin straight under it has the same atlas UV
        uvl = o.data.uv_layers['livery'].data
        for p, mn, pts, nw in _world_polys(o):
            if mn == 'paint':
                for q, li in zip(pts, p.loop_indices):
                    loc, nr, idx, d = tree.find_nearest(q)
                    sd = (q - loc).dot(nr)
                    h_top[0] = min(h_top[0], sd); h_top[1] = max(h_top[1], sd)
                    a, b_, c = (vs[k] for k in fs[idx]); w0, w1, w2 = _bary(loc, a, b_, c)
                    u = tuple(w0 * uvs[idx][0][k] + w1 * uvs[idx][1][k] + w2 * uvs[idx][2][k] for k in range(2))
                    worst_uv = max(worst_uv, math.hypot(u[0] - uvl[li].uv[0], u[1] - uvl[li].uv[1]) / px); n_uv += 1
            elif mn in ('cove', 'gear'):      # the underside (round 3: cove, was interior), its rim edges (cove, lower corners at the underside's height)
                                              # and the stiffeners under it; NOT the hinge arms (gear faces with a corner inside the wing)
                sds = []
                for q in pts:
                    loc, nr, idx, d = tree.find_nearest(q)
                    sds.append((q - loc).dot(nr))
                if mn == 'gear' and min(sds) < 0.0:
                    continue
                h_bot[0] = min(h_bot[0], min(sds)); h_bot[1] = max(h_bot[1], max(sds))
        for p, mn, pts, nw in _world_polys(b):
            for q in pts:
                loc, nr, idx, d = tree.find_nearest(q)
                sd = (q - loc).dot(nr); h_bed[0] = min(h_bed[0], sd); h_bed[1] = max(h_bed[1], sd)
    ok_h = (abs(h_top[0] - M.SPOILER_TOP) < 0.0012 and abs(h_top[1] - M.SPOILER_TOP) < 0.0012 and h_bot[0] > M.SPOILER_BED_TOP + 0.001 and h_bed[0] > 0.0005 and h_bed[1] < M.SPOILER_BOTTOM - 0.001)
    tot = sum(p['area'] for p in panels) / 2
    R(f'x1 1.9.12 spoiler panels: {NP} panels (hinge empty > panel, bed) on wing_inner / wing_mid; the panel\'s paint face lies {M.SPOILER_TOP * 1000:.0f} mm above the wing\'s own (export) triangles '
      f'everywhere and carries the atlas UV of the skin under it (<= 1.5 texel of 4096); underside and stiffeners above the bed plate, bed (plate + frame) 0.5-{M.SPOILER_BOTTOM * 1000 - 1:.0f} mm above the skin',
      not bad and ok_h and worst_uv <= 1.5 and n_uv > 100,
      f'paint face {h_top[0] * 1000:.2f}..{h_top[1] * 1000:.2f} mm, underside / stiffeners {h_bot[0] * 1000:.2f}..{h_bot[1] * 1000:.2f} mm, bed {h_bed[0] * 1000:.2f}..{h_bed[1] * 1000:.2f} mm above the skin; '
      f'panel sizes (span x chord, m2) ' + ', '.join(f'{p["name"]} {p["span"]:.2f} x {p["chord"]:.2f} = {p["area"]:.2f}' for p in panels if p['name'].endswith('_R')) + f'; {tot:.2f} m2 a side; '
      f'UV of the skin under {n_uv} corners: worst {worst_uv:.2f} texel; {bad}')
    # x2 clearances, shut: flaps, nacelles, exhaust lines, wing splits, roundels, fuselage
    bad = []; det = []
    NP = len(want)
    others = {}
    for name, wing in want.items():
        o = obj(name); b = obj(name + '_bed')
        if not o or not b:
            continue
        side = -1 if name.endswith('_L') else 1
        pts = [o.matrix_world @ v.co for v in o.data.vertices] + [b.matrix_world @ v.co for v in b.data.vertices]
        top = [q for p, mn, ps, nw in _world_polys(o) if mn in ('paint', 'cove') for q in ps] + [b.matrix_world @ v.co for v in b.data.vertices]
        ax = [abs(q.x) for q in top]
        cl = {}
        for oth in meshes():
            if oth.name.startswith(('flap_', 'nacelle_', 'engine_', 'fus_', M.KEY, 'aileron_', 'prop_', 'gear_', 'hp_', 'pylon')) and not oth.name.endswith('_root'):
                t = others.setdefault(oth.name, _tri_bvh(oth)[0])
                if t is None:
                    continue
                dmin = min((t.find_nearest(q, 1.0)[3] or 9.0) for q in top[::3])
                kind = oth.name.split('_')[0]
                cl[kind] = min(cl.get(kind, 9.0), dmin)
        xs_ex = min(min(abs(a - 3.83), abs(a - 7.20)) for a in ax)
        xs_split = min(abs(a - sp) for a in ax for sp in S.WING_SPLITS)
        xs_round = 11.5 - max(ax)
        d = dict(flap=cl.get('flap', 9), nacelle=min(cl.get('nacelle', 9), cl.get('engine', 9)), fuselage=min(cl.get('fus', 9), cl.get(M.KEY, 9)), exhaust_line=xs_ex, wing_split=xs_split, roundel=xs_round)
        det.append(name + ' ' + ', '.join(f'{k} {v:.2f}' for k, v in d.items()))
        if d['flap'] < 0.08 or d['nacelle'] < 0.15 or d['fuselage'] < 0.15 or d['exhaust_line'] < 0.30 or d['wing_split'] < 0.20 or d['roundel'] < 1.0:
            bad.append(name)
    R('x2 1.9.12 spoiler panels shut: >= 0.08 m from the flaps, >= 0.15 m from nacelles / engines / fuselage, >= 0.30 m from an exhaust line (|x| 3.83 / 7.20), >= 0.20 m from a wing split, >= 1 m inboard of the wing roundel',
      not bad and len(det) == NP, '; '.join(det))
    # x3 open: sense, height, nothing of the airframe (but its own wing and bed, which the hinge arms cross by design) is touched, both laser fields clear
    bad = []; det = []
    top_ap, ball_ap = obj('top_aperture'), obj('ball_aperture')
    zt = top_ap.matrix_world.translation.z if top_ap else S.TURRETS['top']['pos'][2]
    zb = ball_ap.matrix_world.translation.z if ball_ap else S.TURRETS['ball']['pos'][2]
    for ang in (M.SPOILER_MAX_ANGLE / 2, M.SPOILER_MAX_ANGLE):
        base = {}; rest_w = {}
        for name in want:
            h = obj(name + '_hinge')
            if h:
                base[name] = h.matrix_basis.copy(); rest_w[name] = h.matrix_world.copy()
                h.matrix_basis = base[name] @ Matrix.Rotation(math.radians(-ang), 4, 'X')
        bpy.context.view_layer.update()
        for name, wing in want.items():
            o = obj(name)
            if not o or name not in base:
                continue
            static = [m for m in meshes() if m.name not in (name, name + '_bed', wing) and not m.name.startswith(('cockpit_', 'crew_'))]
            ts, _, _, _ = _tri_bvh_many(static)
            tp = _tri_bvh(o)[0]
            ov = tp.overlap(ts) if (tp and ts) else []
            zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
            if ang == M.SPOILER_MAX_ANGLE:
                free0 = next(V(p['free_edge']) for p in panels if p['name'] == name)
                moved = obj(name + '_hinge').matrix_world @ (rest_w[name].inverted() @ free0)      # the rest free-edge point, carried by the hinge
                rise = moved.z - free0.z
                det.append(f'{name}: free edge z {free0.z:.2f} -> {moved.z:.2f} (+{rise:.2f} m), top {max(zs):.2f}')
                if rise < 0.30 or abs(moved.z - next(p['free_edge_open'][2] for p in panels if p['name'] == name)) > 0.01:
                    bad.append(f'{name}: rise {rise:.2f} m / contract free_edge_open')
            if ov:
                bad.append(f'{name} at {ang:.0f} deg crosses the airframe ({len(ov)} triangle pairs)')
            if max(zs) > zt - 0.30 or min(zs) < zb + 0.30:
                bad.append(f'{name} at {ang:.0f} deg: z {min(zs):.2f}..{max(zs):.2f} not between the laser planes {zb:.2f} / {zt:.2f}')
        for name, mb_ in base.items():
            obj(name + '_hinge').matrix_basis = mb_
        bpy.context.view_layer.update()
    R(f'x3 1.9.12 spoiler panels open {M.SPOILER_MAX_ANGLE / 2:.0f} / {M.SPOILER_MAX_ANGLE:.0f} deg (minus about the hinge\'s local +X in Blender = plus in Unity): the rear edge rises >= 0.30 m, the panel and its arms cross nothing but '
      f'their own wing skin / bed, and stay >= 0.30 m under the dorsal laser\'s horizontal plane (z {zt:.2f}, elevation >= 0) and above the ventral one\'s (z {zb:.2f}, elevation <= 0)',
      not bad and len(det) == NP, '; '.join(det) + (f' | {bad}' if bad else ''))


def _tri_bvh_many(objs):
    vs, fs = [], []
    for o in objs:
        me = o.data; me.calc_loop_triangles(); Mw = o.matrix_world
        off = len(vs); vs += [Mw @ v.co for v in me.vertices]; fs += [tuple(k + off for k in t.vertices) for t in me.loop_triangles]
    return (BVHTree.FromPolygons(vs, fs) if fs else None), vs, fs, None


def check_strips(R, meshes, obj):
    con = json.load(open(bpy.path.abspath('//msb1780_contract.json')))
    strips = (con.get('lights') or {}).get('formation', [])
    alls = sorted(o.name for o in bpy.data.objects if o.name.startswith('slimelight_'))
    if not M.STRIPS1912:
        R('y1 1.9.12 formation-light strips: flag off, no slimelight_* object, no light_off material, no contract key',
          not alls and 'lights' not in con and bpy.data.materials.get('light_off') is None, f'{alls[:4]}')
        return
    want = {'slimelight_fwd_L': 'fus_cockpit', 'slimelight_fwd_R': 'fus_cockpit', 'slimelight_aft_L': 'fus_waist', 'slimelight_aft_R': 'fus_waist',
            'slimelight_fin_L': 'fin', 'slimelight_fin_R': 'fin', 'slimelight_tip_L': 'wing_tip_L', 'slimelight_tip_R': 'wing_tip_R'}
    bad = []; det = []
    if alls != sorted(want) or sorted(s['name'] for s in strips) != sorted(want):
        bad.append(f'objects {alls}, contract {[s["name"] for s in strips]}')
    skin = {}
    allt = _tri_bvh_many([m for m in meshes() if not m.name.startswith('slimelight_')])[0]
    glass = _tri_bvh_many_mat(meshes(), ('glass',))
    hid = []
    box = {}
    for name, parent in want.items():
        o, par = obj(name), obj(parent)
        if not o or not par:
            bad.append(f'{name}: missing'); continue
        if o.parent != par or [m.name for m in o.data.materials] != ['light_off'] or 'paint' in [m.name for m in o.data.materials]:
            bad.append(f'{name}: parent {o.parent.name if o.parent else None} / materials {[m.name for m in o.data.materials]}')
        tree = skin.setdefault(parent, _tri_bvh(par, ('paint',))[0])
        fr = [9, -9]; bk = [9, -9]; nfr = 0; free = 0; area = 0.0
        for p, mn, pts, nw in _world_polys(o):
            c = sum(pts, V()) / len(pts)
            loc, nr, idx, d = tree.find_nearest(c)
            s_ = nw.dot(nr)
            for q in pts:
                l2, n2, i2, d2 = tree.find_nearest(q)
                sd = (q - l2).dot(n2)
                if s_ > 0.7:
                    fr[0] = min(fr[0], sd); fr[1] = max(fr[1], sd)
                elif s_ < -0.7:
                    bk[0] = min(bk[0], sd); bk[1] = max(bk[1], sd)
            if s_ > 0.7:
                nfr += 1; area += p.area
                hit = allt.ray_cast(c + nw * 0.002, nw, 2.0)
                if hit[0] is None:
                    free += 1
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        gd = min((glass.find_nearest(q, 2.0)[3] or 9.0) for q in vs) if glass else 9.0
        box[name] = (min(q.x for q in vs), max(q.x for q in vs), min(q.y for q in vs), max(q.y for q in vs), min(q.z for q in vs), max(q.z for q in vs))
        det.append(f'{name}: front {fr[0] * 1000:.2f}..{fr[1] * 1000:.2f} mm, back {bk[0] * 1000:.2f}..{bk[1] * 1000:.2f} mm, {area:.3f} m2, {free}/{nfr} faces see 2 m of free space, glass {gd:.3f} m')
        if abs(fr[0] - M.STRIP_LIFT) > 0.0008 or abs(fr[1] - M.STRIP_LIFT) > 0.0008 or bk[0] < 0.0004 or bk[1] > M.STRIP_LIFT - 0.001:
            bad.append(f'{name}: not {M.STRIP_LIFT * 1000:.0f} mm proud everywhere')
        if free < nfr:
            hid.append(f'{name} {nfr - free} of {nfr}')
        if gd < 0.05:
            bad.append(f'{name}: {gd:.3f} m from glass')
    R(f'y1 1.9.12 formation-light strips: 8 closed slabs, material light_off only (no paint: not in the livery atlas), children of fus_cockpit / fus_waist / fin / wing_tip; front face {M.STRIP_LIFT * 1000:.0f} mm '
      f'(+-0.8) above the part\'s own (export) triangles at every corner, back face above the skin, >= 0.05 m from any glass',
      not bad and len(det) == 8, '; '.join(det) + (f' | {bad}' if bad else ''))
    R('y2 1.9.12 formation-light strips are seen: along its own normal every front face has 2 m of free space (not behind a frame, door, nacelle or antenna)', not hid and len(det) == 8, f'hidden: {hid}')
    # y3 placement against what is on the skin (measured boxes of the built strips)
    bad = []; d3 = []
    if len(box) == 8:
        for s in ('L', 'R'):
            f, a, n, t = box[f'slimelight_fwd_{s}'], box[f'slimelight_aft_{s}'], box[f'slimelight_fin_{s}'], box[f'slimelight_tip_{s}']
            sill = 1.31 - 0.04                                   # cab window sill 1.31, frame bar from 1.27 (check_light-strips.md 1)
            door_top = 0.835                                     # side-bay door hinge line (parts table)
            c = dict(fwd_under_frame=sill - f[5], fwd_over_outer_nacelle_top=f[4] - 1.07, fwd_in_part=min(5.00 - f[3], f[2] - 2.90),
                     aft_over_door_hinge=a[4] - door_top, aft_behind_sensor_window=M.SENSOR_WIN['y'][0] - a[3], aft_ahead_of_roundel=a[2] - (-9.40 + 0.45), aft_in_part=min(-3.45 - a[3], a[2] + 8.60),
                     fin_over_serial=n[4] - 3.20, fin_ahead_of_rudder_hinge=n[2] - S.RUDDER_HINGE_Y, fin_under_tip=5.44 - n[5],
                     tip_outboard_of_aileron=min(abs(t[0]), abs(t[1])) - S.AILERON[1], tip_outboard_of_roundel=min(abs(t[0]), abs(t[1])) - 13.7, tip_inboard_of_navlight=15.74 - max(abs(t[0]), abs(t[1])))
            lim = dict(fwd_under_frame=0.05, fwd_over_outer_nacelle_top=0.02, fwd_in_part=0.10, aft_over_door_hinge=0.15, aft_behind_sensor_window=0.20, aft_ahead_of_roundel=0.80, aft_in_part=0.50,
                       fin_over_serial=0.40, fin_ahead_of_rudder_hinge=0.50, fin_under_tip=0.40, tip_outboard_of_aileron=0.20, tip_outboard_of_roundel=1.0, tip_inboard_of_navlight=0.50)
            d3.append(s + ': ' + ', '.join(f'{k} {v:.2f}' for k, v in c.items()))
            bad += [f'{s} {k} {v:.3f} < {lim[k]}' for k, v in c.items() if v < lim[k]]
        # the open side-bay door (100 deg about its hinge) stays under the aft strips
        for s, sgn in (('L', 1), ('R', -1)):
            d = obj(f'side_bay_door_{s}'); a = obj(f'slimelight_aft_{s}')
            if d is None:
                bad.append(f'side_bay_door_{s} missing'); continue
            b0 = d.matrix_basis.copy()
            inf = json.loads(d.get('b25_info') or '{}')
            worst = 9.0
            ta = _tri_bvh(a)[0]
            for ang in (25, 50, 75, 100):
                d.matrix_basis = b0 @ Matrix.Rotation(math.radians(math.copysign(ang, inf.get('open_deg', 100 * sgn))), 4, V(inf.get('hinge_axis', [0, 1, 0])))
                bpy.context.view_layer.update()
                worst = min(worst, min((ta.find_nearest(d.matrix_world @ v.co, 1.0)[3] or 9.0) for v in d.data.vertices))
            d.matrix_basis = b0; bpy.context.view_layer.update()
            d3.append(f'open side-bay door {s}: nearest {worst:.3f} m')
            if worst < 0.03:
                bad.append(f'side_bay_door_{s} comes within {worst:.3f} m of the aft strip')
    R('y3 1.9.12 formation-light strips placement (measured boxes): forward under the cab window frame and above the outer nacelle top line; waist above the side-bay door (also swung open), aft of the '
      'sensor window, ahead of the roundel; fin above the serial, on the fixed fin; tip outboard of the aileron and the wing roundel, inboard of the nav light',
      not bad and len(box) == 8, ' | '.join(d3) + (f' | {bad}' if bad else ''))


def _tri_bvh_many_mat(objs, mats):
    vs, fs = [], []
    for o in objs:
        names = [m.name if m else '' for m in o.data.materials]
        if not any(n in mats for n in names):
            continue
        me = o.data; me.calc_loop_triangles(); Mw = o.matrix_world
        off = len(vs); vs += [Mw @ v.co for v in me.vertices]; fs += [tuple(k + off for k in t.vertices) for t in me.loop_triangles if names[t.material_index] in mats]
    return BVHTree.FromPolygons(vs, fs) if fs else None


def check_zexact(R, meshes, obj):
    """row z: the z-fighting rule of row m (same-facing within 2 deg, overlapping, closer than 0.8 mm) for the 1.9.12 plates, with TRUE
    distances: every triangle of an airbrake_* / slimelight_* object against every other export triangle of the aircraft (its own object
    included). Row m itself compares plane constants, which is only a distance for parallel planes (see build_msb1780.py)."""
    import bmesh
    mine = [o for o in meshes() if o.name.startswith(('airbrake_', 'slimelight_'))]
    if not mine:
        return
    vs, fs, own, nrm = [], [], [], []
    for o in meshes():
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        Mw = o.matrix_world
        off = len(vs); vs += [Mw @ v.co for v in bm.verts]
        for f in bm.faces:
            t = tuple(v.index + off for v in f.verts)
            n = (vs[t[1]] - vs[t[0]]).cross(vs[t[2]] - vs[t[0]])
            if n.length < 4e-5:          # area < 2e-5 m2, as row m
                continue
            fs.append(t); own.append(o.name); nrm.append(n.normalized())
        bm.free()
    tree = BVHTree.FromPolygons(vs, fs)
    cosang = math.cos(math.radians(2.0))
    W = [(1 / 3, 1 / 3, 1 / 3), (0.6, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.6), (0.45, 0.45, 0.1), (0.1, 0.45, 0.45), (0.45, 0.1, 0.45)]
    names = {o.name for o in mine}
    hits = []; ntri = 0; closest = 9.0
    for i, t in enumerate(fs):
        if own[i] not in names:
            continue
        ntri += 1
        a, b, c = (vs[k] for k in t)
        cnt = {}
        for w in W:
            p = a * w[0] + b * w[1] + c * w[2]
            seen = set()
            for loc, n2, j, d in tree.find_nearest_range(p, 0.0030):
                if j == i or j in seen or nrm[j].dot(nrm[i]) < cosang:
                    continue
                seen.add(j)
                # the nearest point of j must lie UNDER / OVER p (p projects into j): a neighbour in the same plane (the other half of a
                # 1-3 mm wide rim quad, the next piece of the same face) is adjacent, not overlapping, and cannot z-fight
                off = p - loc
                if (off - nrm[j] * off.dot(nrm[j])).length > 2e-5:
                    continue
                closest = min(closest, d)
                if d <= 0.0008:
                    cnt[j] = cnt.get(j, 0) + 1
        for j, k in cnt.items():
            if k >= 2:
                hits.append((own[i], own[j], tuple(round(x, 3) for x in (a + b + c) / 3)))
    R('z 1.9.12 z-fighting, true distances: no triangle of a spoiler panel / bed / strip lies within 0.8 mm of a same-facing (2 deg) triangle of the aircraft that lies over / under it (row m\'s rule; the plates are left out of row m)',
      not hits and ntri > 500, f'{ntri} triangles of {len(mine)} objects; closest same-facing triangle {closest * 1000:.2f} mm; pairs {hits[:8]}')


def _closest_on_tris(tree, q, r=0.05):
    loc, n, i, d = tree.find_nearest(q, r)
    return d if d is not None else 9.0


def check_standoff(R, meshes, obj):
    """row z2 (review of the first build: row m leaves the plates out - show the same risk is covered with real distances).
    The stand-off of every plate against the ACTUAL built meshes, minimum over ALL vertices, both ways and whatever the facing:
      forward  every vertex of every airbrake_* / slimelight_* object -> the nearest export triangle of every other object of the aircraft
      reverse  every vertex of every other object that lies within 5 cm of a plate -> the nearest triangle of that plate
    A plate's own set (panel + its bed) is measured against each other by row z (same-facing rule); the hinge arms (material gear) CROSS
    the bed and the wing skin by design (a crossing is not a coplanar overlap) and are left out here."""
    mine = [o for o in meshes() if o.name.startswith(('airbrake_', 'slimelight_'))]
    if not mine:
        return
    others = [o for o in meshes() if not o.name.startswith(('airbrake_', 'slimelight_'))]
    t_oth = _tri_bvh_many(others)[0]
    oth_v = [(o.name, o.matrix_world @ v.co) for o in others for v in o.data.vertices]
    rows = {}; nv = 0; nrev = 0; narm = 0
    worst = (9.0, '', None)
    for o in mine:
        kind = 'strip' if o.name.startswith('slimelight_') else ('bed' if o.name.endswith('_bed') else 'panel')
        names = [m.name if m else '' for m in o.data.materials]
        Mw = o.matrix_world
        # hinge arms: the gear faces of a PANEL that reach more than 20 mm under the hinge line (panel-local z = the skin normal)
        arm = {p.index for p in o.data.polygons if kind == 'panel' and names[p.material_index] == 'gear' and min(o.data.vertices[i].co.z for i in p.vertices) < -0.020}
        narm += len(arm)
        keep = set()
        for p in o.data.polygons:
            if p.index not in arm:
                keep.update(p.vertices)
        pts = [Mw @ o.data.vertices[i].co for i in sorted(keep)]
        fwd = 9.0
        for q in pts:
            d = _closest_on_tris(t_oth, q); nv += 1
            if d < fwd:
                fwd = d
                if d < worst[0]:
                    worst = (d, o.name + ' vertex -> airframe', tuple(round(c, 3) for c in q))
        me = o.data; me.calc_loop_triangles()
        vs = [Mw @ v.co for v in me.vertices]
        fs = [tuple(t.vertices) for t in me.loop_triangles if t.polygon_index not in arm]
        tp = BVHTree.FromPolygons(vs, fs)
        lo = [min(q[k] for q in pts) - 0.05 for k in range(3)]; hi = [max(q[k] for q in pts) + 0.05 for k in range(3)]
        rev = 9.0
        for nm, q in oth_v:
            if lo[0] <= q.x <= hi[0] and lo[1] <= q.y <= hi[1] and lo[2] <= q.z <= hi[2]:
                d = _closest_on_tris(tp, q); nrev += 1
                if d < rev:
                    rev = d
                    if d < worst[0]:
                        worst = (d, f'{nm} vertex -> {o.name}', tuple(round(c, 3) for c in q))
        r = rows.setdefault(kind, [9.0, 9.0, 0])
        r[0] = min(r[0], fwd); r[1] = min(r[1], rev); r[2] += 1
    lim = 0.0008
    ok = all(r[0] >= lim - 1e-6 and r[1] >= lim - 1e-6 for r in rows.values())
    R(f'z2 1.9.12 plate stand-off, real distances over ALL vertices (not samples): every vertex of a spoiler panel / bed / strip is >= {lim * 1000:.1f} mm '
      f'(row m\'s distance) from every triangle of the rest of the aircraft, and every airframe vertex near a plate is >= {lim * 1000:.1f} mm from the plate\'s triangles (any facing; hinge arms, which cross the skin by design, left out)',
      ok and nv > 2000,
      '; '.join(f'{k} x{r[2]}: plate vertices -> airframe min {r[0] * 1000:.2f} mm, airframe vertices -> plate min {r[1] * 1000:.2f} mm' for k, r in sorted(rows.items()))
      + f'; {nv} plate vertices, {nrev} airframe vertices measured, {narm} hinge-arm faces left out; closest: {worst[0] * 1000:.2f} mm ({worst[1]} at {worst[2]})')


def check_rowm_all(R, meshes, obj, zfight_pairs):
    """row z3: row m's OWN detector run on the whole aircraft WITH the plates. Every pair it reports must involve a plate (the rest of the
    aircraft is row m itself: 0), and the plate pairs are listed: they are plane-constant coincidences of planes up to 2 deg apart, which
    rows z / z2 measure with true distances."""
    if zfight_pairs is None or not any(o.name.startswith(('airbrake_', 'slimelight_')) for o in meshes()):
        return
    hits = zfight_pairs(objs=list(meshes()))
    isp = lambda n: str(n).startswith(('airbrake_', 'slimelight_'))
    mine = [h for h in hits if any(isp(x) for x in h[:4])]
    rest = len(hits) - len(mine)
    from collections import Counter
    R('z3 1.9.12 row m\'s own detector on the whole aircraft WITH the plates (informational for the plates: plane constants within 0.8 mm, normals within 2 deg - a distance only for parallel planes): no pair without a plate; the plate pairs it reports are listed and are measured by rows z / z2',
      rest == 0, f'{len(mine)} plate pairs reported by the plane-constant test: {Counter(tuple(str(x) for x in h[:4] if isinstance(x, str)) for h in mine).most_common(8)}; pairs without a plate {rest}')


def run(R, meshes, obj, zfight_pairs=None):
    check_spoilers(R, meshes, obj)
    check_strips(R, meshes, obj)
    check_zexact(R, meshes, obj)
    check_standoff(R, meshes, obj)
    check_rowm_all(R, meshes, obj, zfight_pairs)
