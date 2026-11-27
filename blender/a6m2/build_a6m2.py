"""Build the A6M2 Zero Model 21 model (round 1, our own procedural geometry) and save it as a .blend + contract json.

  blender --background --factory-startup --python-exit-code 1 --python blender/a6m2/build_a6m2.py -- --out assets/model_a6m2/a6m2.blend

Blender space: nose +Y, up +Z, right wing +X, metres, flight attitude, GEAR DOWN. Paint faces share one packed UV atlas `livery`;
every face also has a tiling UV `detail`. The root empty A6M2_root sits at the computed CoM (combat trim) and becomes the FBX / Unity
origin (export_a6m2.py). Reuses the B-25H v2 pipeline functions (pack_livery, create_objects, make_materials) read-only.
No file under nuclearoption-ref\\refs is opened: every number comes from a6m2_spec.py.
"""
import bpy, sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.abspath(os.path.join(HERE, '..', 'v2'))
for p in (HERE, V2):
    if p not in sys.path:
        sys.path.insert(0, p)
for m in ('a6m2_spec', 'a6m2_parts'):
    sys.modules.pop(m, None)
from mathutils import Vector as V
import build_b25h_v2 as B
from b25h_parts import Part
import a6m2_spec as S
import a6m2_parts as AP

MATERIALS = {   # name: (base colour RGBA, metallic, roughness); Unity builds its own materials per name
    'paint': ((0.66, 0.64, 0.54, 1.0), 0.2, 0.5),          # placeholder ame-iro grey (round 1: one simple livery)
    'interior': ((0.345, 0.404, 0.333, 1.0), 0.15, 0.55),  # Mitsubishi cockpit green #586755 (r4c: own tile with seams / rivets / wear in Unity)
    'ck_panel': ((0.06, 0.062, 0.06, 1.0), 0.2, 0.35),    # r4c: semi-gloss black instrument panel
    'structure': ((0.55, 0.56, 0.56, 1.0), 0.6, 0.45),
    'metal_dark': ((0.06, 0.06, 0.065, 1.0), 0.6, 0.45),
    'tank': ((0.55, 0.56, 0.52, 1.0), 0.35, 0.60),          # r8o: fuel / oil tank cells, plain metal (no aircraft_structure pattern); round 2: = Unity A6M2_tank (plain LitMat 0.55 grey, no tile)
    'engine': ((0.18, 0.18, 0.19, 1.0), 0.7, 0.45),
    'exhaust': ((0.20, 0.13, 0.09, 1.0), 0.5, 0.7),
    'gunmetal': ((0.12, 0.12, 0.13, 1.0), 0.8, 0.35),
    'glass': ((0.93, 0.96, 0.98, 0.07), 0.0, 0.05),        # r4c: clear (no blue tint over the cockpit); Unity uses the stock COIN glass
    'well': ((0.17, 0.42, 0.44, 1.0), 0.1, 0.6),
    'well_dark': ((0.085, 0.22, 0.235, 1.0), 0.1, 0.7),     # r8l: the well ceiling panels between the ribs (= A6M2Build.WellAotakeDark)           # aotake (r8k: lighter, = A6M2Build.WellAotake; r6-r8j 0.07/0.20/0.22 read near-black in game)
    'gear': ((0.30, 0.31, 0.30, 1.0), 0.6, 0.45),
    'chrome': ((0.80, 0.81, 0.82, 1.0), 1.0, 0.15),
    'rubber': ((0.025, 0.025, 0.025, 1.0), 0.0, 0.9),
    'hub': ((0.55, 0.56, 0.54, 1.0), 0.5, 0.5),
    'hook': ((0.20, 0.20, 0.21, 1.0), 0.6, 0.5),
    'hookyellow': ((0.80, 0.62, 0.08, 1.0), 0.1, 0.5),
    'spinner': ((0.75, 0.76, 0.78, 1.0), 0.8, 0.30),
    'prop': ((0.55, 0.56, 0.57, 1.0), 0.75, 0.5),   # r8b: duller natural metal          # aluminium blades (one material, design 9.1)
    'navred': ((0.85, 0.08, 0.06, 1.0), 0.0, 0.08),
    'navgreen': ((0.10, 0.72, 0.55, 1.0), 0.0, 0.08),
    'wire': ((0.05, 0.05, 0.05, 1.0), 0.5, 0.5),
    'ck_black': ((0.055, 0.055, 0.058, 1.0), 0.2, 0.55),   # r8b: dark grey, not pure black
    'ck_dark': ((0.22, 0.27, 0.22, 1.0), 0.1, 0.6),        # r8b: shaded cockpit green (floor, lips, plates; Unity: the ckgreen tile x 0.62)
    'ck_leather': ((0.13, 0.08, 0.05, 1.0), 0.0, 0.6),     # r8b: leather (coaming pad, stick boot / grip, radio housing)
    'ck_blue': ((0.12, 0.32, 0.62, 1.0), 0.1, 0.4),        # r8b: mixture lever handle, cowl-flap lever tip (WT)
    'alu': ((0.70, 0.71, 0.72, 1.0), 0.85, 0.35),
    'bomb': ((0.16, 0.17, 0.16, 1.0), 0.3, 0.55),          # round 2: IJN bomb body (dark grey)
    'bombband': ((0.62, 0.08, 0.05, 1.0), 0.1, 0.5),       # nose band
    'gauges': ((0.9, 0.9, 0.9, 1.0), 0.0, 0.5),            # round 4: dial atlas (own UVs)
    'reticle': ((1.0, 0.45, 0.10, 1.0), 0.0, 0.5),         # Type 98 sight reticle (emissive in Unity)
    'sightglass': ((0.80, 0.92, 0.86, 0.12), 0.0, 0.05),   # r8: Type 98 reflector, faint green-tinted transparent (Unity A6M2_sightglass)
    'ck_wood': ((0.26, 0.13, 0.06, 1.0), 0.0, 0.45),      # r8b: dark-brown wood (WT knobs; r8 tan)        # charging-handle knobs
    'ck_gun': ((0.17, 0.175, 0.18, 1.0), 0.3, 0.45),      # r8b: dark gunmetal, not black     # r6: cockpit gun receivers, dark gunmetal (own tile with edge wear in Unity)
    'ck_white': ((0.82, 0.80, 0.74, 1.0), 0.0, 0.45),       # r6: white lever knobs
}

FUEL_FRACTION = 0.7          # combat trim for the root / CoM (design 5.3: 2,350 kg combat trim)


def uv_group(name):
    if name.startswith(('fus_', 'fillet_', 'wing_C')):
        return 'fuselage'
    if name.startswith(('wing_', 'aileron_', 'flap_')):
        return 'wing_' + name[-1]
    if name.startswith(('stab_', 'elevator_', 'fin', 'rudder')):
        return 'tail'
    return name


MESH_OF = {'A6M2': ['fus_center', 'wing_C', 'fillet_L', 'fillet_R'], 'prop': ['prop_hub']}   # (Part meshes; r8e: unified into fus_center after create_objects)   # = the Unity colliders (A6M2Build.MakeAeroPart)
FUEL_PARTS = [('fuel_fus', 104.0, 'A6M2'), ('fuel_wing_L', 140.0, 'wing_inner_L'), ('fuel_wing_R', 140.0, 'wing_inner_R')]   # A6M2Build FuelTanks


def com(parts, fuel=FUEL_FRACTION):
    """the Unity CHECK rule (A6M2Build.RunCheck): every AeroPart's mass at its collider-bounds centre + each FuelTank's fuel (x fraction) at its
    part's centre. Pilot / oil / ammo have no mass in the game build; they are reported separately as 'loads' only."""
    byname = {p.name: p for p in parts}
    tot = 0.0
    acc = V()
    rows = []
    centre = {}
    for nm, kg in S.MASSES.items():
        vs = [v for n in MESH_OF.get(nm, [nm]) for v in byname[n].mesh.verts]
        c = V(((min(v.x for v in vs) + max(v.x for v in vs)) / 2, (min(v.y for v in vs) + max(v.y for v in vs)) / 2,
               (min(v.z for v in vs) + max(v.z for v in vs)) / 2))
        centre[nm] = c
        acc += c * kg
        tot += kg
        rows.append((nm, kg, tuple(round(x, 3) for x in c)))
    for nm, kg, part in FUEL_PARTS:
        k = kg * fuel
        acc += centre[part] * k
        tot += k
        rows.append((nm, round(k, 1), tuple(round(x, 3) for x in centre[part])))
    return acc / tot, tot, rows


def contract(parts, root_c, mass, rows):
    byname = {p.name: p for p in parts}

    def U(v):
        d = V(v) - root_c
        return [round(d.x, 4), round(d.z, 4), round(d.y, 4)]

    def Ud(v):
        return [round(v[0], 5), round(v[2], 5), round(v[1], 5)]
    gear = {}
    for L in ('L', 'R'):
        leg = byname[f'gear_main_{L}_strut']
        gear[L] = dict(pivot=U(leg.info['pivot']), axis_unity=Ud(leg.info['retract_axis_world']), retract_deg=round(leg.info['retract_deg'], 2),
                       wheel_down=U(byname[f'gear_main_{L}_wheel'].pivot), wheel_up=U(leg.info['wheel_up']),
                       door=dict(hinge=U(byname[f'gear_door_{L}'].pivot), axis_unity=Ud(byname[f'gear_door_{L}'].info['hinge_axis']),
                                 open_deg=S.INNER_DOOR_OPEN))
    wheel_r = S.WHEEL_D / 2 * S.K
    wc = byname['gear_main_R_wheel'].pivot
    tc = byname['gear_tail_wheel'].pivot
    tr = S.TAIL_WHEEL_D / 2 * S.K
    # 3-point attitude from the wheel bottoms
    ang = math.degrees(math.atan2((wc.z - wheel_r) - (tc.z - tr), wc.y - tc.y))
    lvl = root_c.z - (wc.z - wheel_r)
    hook = byname['tailhook']
    c = dict(meta=dict(generator='blender/a6m2/build_a6m2.py', aircraft='Mitsubishi A6M2 Zero Model 21', jsonKey='A6M2', round=1,
                       frame='Unity: x right, y up, z forward; origin = A6M2_root = CoM at combat trim (fuel 70 %)'),
             cg_blender=[round(x, 4) for x in root_c], parts_mass_kg=round(mass, 1), mass_rows=rows,
             three_point_deg=round(ang, 2), level_wheel_contact_height=round(lvl, 4),
             gear=dict(main=gear, wheel_r=round(wheel_r, 4), tail_axle=U(tc), tail_r=round(tr, 4), tail_pivot=U(byname['gear_tail_strut'].pivot)),
             tailhook=dict(name='tailhook', pivot=U(hook.pivot), length=round(hook.info['length'], 4), stowed_up_deg=hook.info['stowed_up_deg'],
                           deployed_deg=hook.info['deployed_deg']),
             prop=dict(tip_radius=round(S.PROP_TIP_R * S.K, 4), plane=U(byname['prop'].pivot), blades=3,
                       spinner_back_y=round(S.SPINNER[0][0] * S.K - root_c.y, 4)),
             guns=dict(type97=dict(muzzles=['muzzle_gun_L', 'muzzle_gun_R'], flashes=['flash_gun_L', 'flash_gun_R'], bullet_z=U(byname['muzzle_gun_R'].pivot)[2]),
                       type99=dict(muzzles=['muzzle_cannon_L', 'muzzle_cannon_R'], flashes=['flash_cannon_L', 'flash_cannon_R'])),
             eye=U(byname['cockpit_eye'].pivot), mac=dict(len=round(S.MAC, 4), le_z=round(S.MAC_LE_Y * S.K - root_c.y, 4)),
             canopy=dict(hood='canopy_hood', slide_m=round(S.CANOPY_SLIDE * S.K, 4)),
             attach=[dict(obj=o, p=list(p), to=t) for o, p, t in AP.ATTACH],
             wing_fold=fold_hinges(U))
    return c


def fold_hinges(U):
    """r8: folding-tip hinge line per side (upper skin at the fold break |x| 5.195 pre-scale, 2 % / 98 % chord), Unity frame."""
    xb = S.span_built(S.WING_BREAKS[3])
    out = {}
    for side, L in ((1, 'R'), (-1, 'L')):
        st = AP.wing_station(xb, side)
        out[L] = dict(hinge_le=U(st.point(0.02, True)), hinge_te=U(st.point(0.98, True)), fold_deg=90.0)
    return out


def flip_backside_uvs(parts):
    """round 5: a paint face whose UV is the default planar_uv (dominant normal axis) gets its u mirrored when the normal points down
    that axis. Without it the two faces of a thin closed shell (rudder, wing_C, fillets) shared metre-UVs along their common edges,
    pack_livery welded them into ONE island and the two sides overlapped in the atlas (r1-r4: 80 % of the rudder, 95 % of wing_C):
    a marking painted on one side showed mirrored on the other."""
    from b25h_geom import planar_uv
    n_ = 0
    for p in parts:
        if p.mesh is None:
            continue
        for f in p.mesh.faces:
            if f['mat'] != 'paint' or not f['uv']:
                continue
            pts = [p.mesh.verts[i] for i in f['idx']]
            nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
            if nrm.length < 1e-12 and len(pts) > 3:
                nrm = (pts[2] - pts[0]).cross(pts[3] - pts[0])
            if nrm.length < 1e-12:
                continue
            ax = max(range(3), key=lambda i: abs(nrm[i]))
            if nrm[ax] >= 0:
                continue
            if all(abs(u[0] - q[0]) < 1e-6 and abs(u[1] - q[1]) < 1e-6 for u, q in zip(f['uv'], (planar_uv(v, nrm) for v in pts))):
                f['uv'] = [(-u[0], u[1]) for u in f['uv']]
                n_ += 1
    return n_


def prop_tip_uvs(objs):
    """r7: tip stripes on the ONE blade material: every 'prop' face of prop_blade_* gets livery UV u = radius / tip radius (v 0.5), so the
    prop material's 1-D texture (textures/make_prop_tips_a6m2.py) paints the stripes; still one material and one renderer per blade."""
    bpy.context.view_layer.update()
    hub = None
    for n in ('prop_hub', 'prop'):
        if n in bpy.data.objects:
            hub = bpy.data.objects[n].matrix_world.translation.copy(); break
    if hub is None:
        return
    for name, ob in objs.items():
        if not name.startswith('prop_blade_') or ob.type != 'MESH':
            continue
        me = ob.data
        mw = ob.matrix_world
        liv = me.uv_layers.get('livery')
        if liv is None:
            continue
        rad = lambda co: math.hypot((mw @ co).x - hub.x, (mw @ co).z - hub.z)
        R = max(rad(v.co) for v in me.vertices)
        for poly in me.polygons:
            if me.materials[poly.material_index].name != 'prop':
                continue
            # r8d: v = 0.25 on the blade's rear face (normal aft, toward the cockpit: the dark anti-glare finish), 0.75 on the front (metal)
            ny = (mw.to_3x3() @ poly.normal).y
            vv = 0.25 if ny < 0 else 0.75
            for li, vi in zip(poly.loop_indices, poly.vertices):
                liv.data[li].uv = (min(rad(me.vertices[vi].co) / R, 0.999), vv)


SKIN_PREFIX = ('wing_', 'fus_', 'fillet_', 'stab_', 'elevator_', 'fin', 'rudder', 'aileron_', 'flap_')


FAIRING_TIP_BLEND = False  # r8g (game r8f: a light flat wedge on the wing at the LE root): the r8f tip blend took the FUSELAGE side
                           # normals (pointing -x) for fairing faces lying on top of the wing - loop normals 90 deg off their faces. Off.
ROOT_NORMAL_RELAX = True   # r8f: two relaxation passes of the root-zone loop normals (blotchy fillet shading in game)
ROOT_NORMAL_GAUSS = (0.018, 0.045, 50.0)   # r8j: (sigma m, radius m, cone deg) - spatial normal smoothing of the root zone; None = off
ROOT_NORMAL_GAUSS_MIN_UP = 0.35            # r8j: only up-facing loops (the fillet-wing seam, the LE bulge); the fillet top got saw-teeth
ROOT_NORMAL_GAUSS_FILLET_CONE = 50.0       # r8j: the cone for fillet (src 2) loops (75 tried: 31 shading seams at the fillet tip)
ROOT_SMOOTH_DEG = 35.0   # r8e value (r8f tried 80: no visible change on the ledge under the LE root)


def unify_skin_normals(objs, angle=38.0):
    """r8b (critique: tone steps / creases at the wing-fold, root and tailplane cuts): the outer skin is split into separate objects
    (break lines), so each object smoothed its own normals and the shading jumped at every cut. Custom split normals for every paint
    loop of the skin objects = the area-weighted average of the face normals of ALL skin objects' paint faces at that vertex position
    (0.1 mm), within `angle` of the loop's own face (sharp edges such as the trailing edge stay sharp). FBX exports them; Unity imports them."""
    import collections
    cos_a = math.cos(math.radians(angle))
    acc = collections.defaultdict(list)
    data = []
    for name, ob in objs.items():
        if ob.type != 'MESH' or not name.startswith(SKIN_PREFIX):
            continue
        me = ob.data
        mats = [m.name if m else '' for m in me.materials]
        if 'paint' not in mats:
            continue
        pi = mats.index('paint')
        M = ob.matrix_world; R3 = M.to_3x3()
        for poly in me.polygons:
            if poly.material_index != pi:
                continue
            n = (R3 @ poly.normal).normalized() * poly.area
            for vi in poly.vertices:
                w = M @ me.vertices[vi].co
                acc[(round(w.x, 4), round(w.y, 4), round(w.z, 4))].append(n)
        data.append((ob, pi))
    n_set = 0
    cos_root = math.cos(math.radians(ROOT_SMOOTH_DEG))     # r8e (60) / r8f (80): the unified root mesh blends its fairing / LE root over up to 60 deg (TE / well lips stay sharp)
    for ob, pi in data:
        me = ob.data
        M = ob.matrix_world; R3i = M.to_3x3().inverted()
        cos_o = cos_root if ob.name == 'fus_center' else cos_a
        custom = []
        for poly in me.polygons:
            fn = (M.to_3x3() @ poly.normal).normalized()
            if poly.material_index == pi and poly.area < 0.02 * max(
                    (me.vertices[poly.vertices[k]].co - me.vertices[poly.vertices[k - 1]].co).length_squared for k in range(len(poly.vertices))):
                # r8e: a boolean sliver (long thin triangle): its own normal is noise and would keep its loops out of the smoothing
                # (a dark facet). Reference = the largest face at its first vertex instead.
                w0 = M @ me.vertices[poly.vertices[0]].co
                # r8g: only faces within 75 deg of the sliver's own plane qualify (the largest face at a junction vertex can be the
                # perpendicular fuselage side - that turned slivers on the wing sideways)
                big = max([n for n in acc[(round(w0.x, 4), round(w0.y, 4), round(w0.z, 4))] if n.length > 1e-12 and n.normalized().dot(fn) > 0.26],
                          key=lambda n: n.length, default=None)
                if big is not None and big.length > 1e-12:
                    fn = big.normalized()
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                if poly.material_index != pi:
                    custom.append(V((0, 0, 0)))                         # zero = keep the computed normal
                    continue
                w = M @ me.vertices[vi].co
                tot = V((0, 0, 0))
                for n in acc[(round(w.x, 4), round(w.y, 4), round(w.z, 4))]:
                    if n.length > 1e-12 and n.normalized().dot(fn) >= cos_o:
                        tot += n
                custom.append((R3i @ tot).normalized() if tot.length > 1e-12 else V((0, 0, 0)))
                n_set += 1
        if ob.name == 'fus_center' and me.attributes.get('src') is not None:
            # r8f (0.5 m sheet r8e: a faint light band along the fairing's front tip): ahead of y 0.25 the fading fairing (src 2) is a thin
            # sliver whose faces tilt up and catch the light. Its paint loops take the area-weighted normal of the surrounding fuselage /
            # wing faces (src 0 / 1) within 60 mm (70 %), so the tip shades like the surface it grows out of.
            from mathutils.kdtree import KDTree
            srcv = [a.value for a in me.attributes['src'].data]
            base = [p_ for p_ in me.polygons if p_.material_index == pi and srcv[p_.index] in (0, 1)]
            kd = KDTree(len(base))
            for i_, p_ in enumerate(base):
                kd.insert(M @ p_.center, i_)
            kd.balance()
            R3 = M.to_3x3(); nb = 0
            for poly in me.polygons:
                if not FAIRING_TIP_BLEND or poly.material_index != pi or srcv[poly.index] != 2 or (M @ poly.center).y < 0.25:
                    continue
                for li in poly.loop_indices:
                    w = M @ me.vertices[me.loops[li].vertex_index].co
                    tot = V((0, 0, 0))
                    for co_, i_, d_ in kd.find_range(w, 0.06):
                        tot += (R3 @ base[i_].normal).normalized() * base[i_].area
                    if tot.length < 1e-12:
                        continue
                    own = R3 @ custom[li] if custom[li].length > 1e-12 else (R3 @ poly.normal)
                    custom[li] = (R3i @ (tot.normalized() * 0.7 + own.normalized() * 0.3)).normalized(); nb += 1
            print('[a6m2] r8f: fairing front-tip loops shaded with the surrounding surface:', nb)
            if ROOT_NORMAL_RELAX:
                # r8f (game r8e: 'slightly blotchy' shading on the LE fillet): the boolean leaves irregular triangles there and the
                # area-weighted vertex normals jump between neighbours. Two relaxation passes over the root zone (|x| 0.2-0.95,
                # y -2.4..0.95): each paint loop takes the mean of its vertex's and the 1-ring vertices' loop normals that lie within
                # 25 deg of it (creases, the TE and the well lips stay sharp).
                vn = {}                                              # vertex index -> list of loop indices (paint)
                for poly in me.polygons:
                    if poly.material_index != pi:
                        continue
                    for li in poly.loop_indices:
                        vn.setdefault(me.loops[li].vertex_index, []).append(li)
                nbr = {}
                for e in me.edges:
                    a_, b_ = e.vertices
                    nbr.setdefault(a_, []).append(b_); nbr.setdefault(b_, []).append(a_)
                zone = set()
                for vi in vn:
                    w = M @ me.vertices[vi].co
                    if 0.10 < abs(w.x) < 0.95 and -2.4 < w.y < 0.95 and w.z < 0.10:
                        zone.add(vi)
                cos25 = math.cos(math.radians(25.0)); nrel = 0
                for _ in range(2):
                    new = {}
                    for vi in zone:
                        cand = [li2 for vj in [vi] + nbr.get(vi, []) for li2 in vn.get(vj, []) if custom[li2].length > 1e-12]
                        for li in vn[vi]:
                            c0 = custom[li]
                            if c0.length < 1e-12:
                                continue
                            acc_ = V((0, 0, 0))
                            for li2 in cand:
                                if custom[li2].normalized().dot(c0.normalized()) >= cos25:
                                    acc_ += custom[li2].normalized()
                            if acc_.length > 1e-12:
                                new[li] = acc_.normalized()
                    for li, nv in new.items():
                        custom[li] = nv
                    nrel = len(new)
                print('[a6m2] r8f: root-zone normal relaxation on', nrel, 'loops')
                if ROOT_NORMAL_GAUSS:
                    # r8j (in game r8i: lumpy shading creases on the fillet bulge over the LE; offline: a saw-tooth light / dark line along the
                    # fillet-wing seam with the exported normals, shadows off): the 1-ring passes follow the boolean triangulation, so the
                    # tone boundary steps with the triangles. Each zone loop now takes the Gaussian-weighted (sigma, within radius), area-weighted
                    # mean of the paint FACE normals around its vertex that lie within cone deg of its current normal: shading set by the
                    # surface, not by the triangles (creases > cone stay sharp).
                    sig_, rad_, cone_ = ROOT_NORMAL_GAUSS
                    R3g = M.to_3x3()
                    fpaint = [p_ for p_ in me.polygons if p_.material_index == pi]
                    kdf = KDTree(len(fpaint))
                    for i_, p_ in enumerate(fpaint):
                        kdf.insert(M @ p_.center, i_)
                    kdf.balance()
                    fnw = [((R3g @ p_.normal).normalized(), p_.area) for p_ in fpaint]
                    cosc = math.cos(math.radians(cone_)); ng = 0
                    cosf = math.cos(math.radians(ROOT_NORMAL_GAUSS_FILLET_CONE))
                    lpoly = {}
                    for poly in me.polygons:
                        if poly.material_index == pi:
                            for li in poly.loop_indices:
                                lpoly[li] = poly.index
                    newg = {}
                    for vi in zone:
                        w = M @ me.vertices[vi].co
                        near = kdf.find_range(w, rad_)
                        for li in vn[vi]:
                            c0 = custom[li]
                            if c0.length < 1e-12:
                                continue
                            c0w = (R3g @ c0).normalized()
                            if c0w.z < ROOT_NORMAL_GAUSS_MIN_UP:
                                continue      # the fillet top / fuselage side (normals near horizontal): smoothing there made saw-teeth
                            # the fillet (src 2) is one smooth blend: its crinkled front tip (rows wrapping the LE nose at 4-10 mm radius,
                            # face normals alternating ~60 deg) averages over a wider cone
                            cc_ = cosf if srcv[lpoly[li]] == 2 else cosc
                            cch_ = math.cos(0.5 * math.acos(max(-1.0, min(1.0, cc_))))
                            acc_ = V((0, 0, 0))
                            for co_, i_, d_ in near:
                                n_, a_ = fnw[i_]
                                dd_ = n_.dot(c0w)
                                if dd_ >= cc_:
                                    # soft cone: full weight inside half the cone angle, fading to 0 at the cone edge (a hard edge
                                    # toggled faces in and out along the fillet top: periodic lumps)
                                    tw_ = min(1.0, (dd_ - cc_) / max(cch_ - cc_, 1e-6))
                                    acc_ += n_ * (a_ * tw_ * tw_ * (3 - 2 * tw_) * math.exp(-0.5 * (d_ / sig_) ** 2))
                            if acc_.length > 1e-12:
                                newg[li] = (R3i @ acc_).normalized()
                    for li, nv in newg.items():
                        custom[li] = nv; ng += 1
                    print('[a6m2] r8j: root-zone Gaussian normal smoothing on', ng, 'loops', ROOT_NORMAL_GAUSS)
                # r8g: shading seams on smooth surface - two faces meeting at < 20 deg whose loop normals at a shared vertex still differ
                # by > 20 deg (different neighbour pools) - get the mean of the two loops (3 passes)
                lo = {}
                for poly in me.polygons:
                    if poly.material_index == pi:
                        for li in poly.loop_indices:
                            lo[(poly.index, me.loops[li].vertex_index)] = li
                em = {}
                for poly in me.polygons:
                    if poly.material_index == pi:
                        for ek in poly.edge_keys:
                            em.setdefault(ek, []).append(poly.index)
                c20 = math.cos(math.radians(20.0)); nseam = 0
                for _ in range(6 if ROOT_NORMAL_GAUSS else 3):      # r8j: 6 passes (the Gaussian pass leaves a few seams where its cones differ)
                    for ek, fl in em.items():
                        if len(fl) != 2 or not (ek[0] in zone or ek[1] in zone):
                            continue
                        pa, pb = me.polygons[fl[0]], me.polygons[fl[1]]
                        if pa.normal.dot(pb.normal) < c20:
                            continue
                        for v in ek:
                            la, lb = lo[(pa.index, v)], lo[(pb.index, v)]
                            if custom[la].length < 1e-12 or custom[lb].length < 1e-12:
                                continue
                            if custom[la].normalized().dot(custom[lb].normalized()) < c20:
                                m_ = (custom[la].normalized() + custom[lb].normalized()).normalized()
                                custom[la] = m_; custom[lb] = m_; nseam += 1
                print('[a6m2] r8g: root-zone shading seams welded:', nseam)
                # r8h guard: a loop normal more than 60 deg off its own face (a pool across a crease met by a tiny face) takes the face normal
                nclamp = 0
                for poly in me.polygons:
                    if poly.material_index != pi:
                        continue
                    for li in poly.loop_indices:
                        if me.loops[li].vertex_index in zone and custom[li].length > 1e-12 and custom[li].normalized().dot(poly.normal) < 0.5:
                            custom[li] = poly.normal.copy(); nclamp += 1
                print('[a6m2] r8h: root-zone loop normals clamped to their face:', nclamp)
                if ROOT_NORMAL_GAUSS:
                    # r8j: pairwise welds do not converge round a vertex where 3+ small faces meet (a fan cycle), and
                    # normals_split_custom_set then splits the fan with a sharp edge (a shading seam). Per zone vertex, the paint faces of one
                    # smooth fan share the mean of their loop normals.
                    # (Blender keeps ONE normal per smooth fan - faces joined by non-sharp edges - so the cluster is the fan)
                    sh_ = me.attributes.get('sharp_edge')
                    eidx_ = {tuple(sorted(e.vertices)): e.index for e in me.edges}

                    def smooth_edge(ek, fl):
                        ei_ = eidx_.get(tuple(sorted(ek)))
                        if sh_ is not None and ei_ is not None:
                            return not sh_.data[ei_].value
                        return me.polygons[fl[0]].normal.dot(me.polygons[fl[1]].normal) >= c20
                    vfaces = {}
                    for ek, fl in em.items():
                        if len(fl) == 2 and smooth_edge(ek, fl):
                            for v in ek:
                                if v in zone:
                                    vfaces.setdefault(v, []).append((fl[0], fl[1]))
                    ncl = nsplit = 0
                    if sh_ is None:
                        sh_ = me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
                    for v, pairs in vfaces.items():
                        par = {}

                        def fnd(a):
                            while par.setdefault(a, a) != a:
                                par[a] = par[par[a]]; a = par[a]
                            return a
                        for a, b in pairs:
                            ra, rb = fnd(a), fnd(b)
                            if ra != rb:
                                par[ra] = rb
                        cl = {}
                        for f_ in par:
                            cl.setdefault(fnd(f_), []).append(f_)
                        for fs_ in cl.values():
                            fs_ = [f_ for f_ in fs_ if (f_, v) in lo and custom[lo[(f_, v)]].length > 1e-12]
                            if len(fs_) < 2:
                                continue
                            inl = list(fs_)
                            for _ in range(3):        # mean of the inliers; a crinkle face > 60 deg off the mean is split off
                                m_ = sum((custom[lo[(f_, v)]].normalized() for f_ in inl), V((0, 0, 0)))
                                if m_.length < 1e-12:
                                    break
                                m_.normalize()
                                inl2 = [f_ for f_ in fs_ if m_.dot(me.polygons[f_].normal) >= 0.5]
                                if inl2 == inl or not inl2:
                                    break
                                inl = inl2
                            if m_.length < 1e-12 or not inl:
                                continue
                            for f_ in inl:
                                custom[lo[(f_, v)]] = m_
                            for f_ in fs_:
                                if f_ in inl or sh_ is None:
                                    continue
                                for ek in me.polygons[f_].edge_keys:
                                    if v in ek and tuple(sorted(ek)) in eidx_:
                                        sh_.data[eidx_[tuple(sorted(ek))]].value = True; nsplit += 1
                            ncl += 1
                    print('[a6m2] r8j: smooth face clusters given one normal per zone vertex:', ncl, '- crinkle faces split off (edges):', nsplit)
        try:
            me.normals_split_custom_set(custom)
        except Exception as e:
            print('[a6m2] custom normals failed on', ob.name, e)
        if ROOT_NORMAL_GAUSS and ob.name == 'fus_center' and me.attributes.get('src') is not None:
            fan_seam_fix(me, M, pi)
    return n_set


def fan_seam_fix(me, M, pi, passes=3):
    """r8j: normals_split_custom_set splits a smooth fan with a sharp edge wherever the loops given at a vertex differ, so a tiny face at the
    fillet front (an ngon from the slit seal) kept a seam on a 4 deg edge. Root zone, paint: unflag sharp edges between faces < 20 deg
    apart, then give each smooth fan at a vertex the mean of its loop normals (faces > 60 deg off that mean are left alone) and set again."""
    c20 = math.cos(math.radians(20.0))
    for _ in range(passes):
        sh_ = me.attributes.get('sharp_edge')
        eidx_ = {tuple(sorted(e.vertices)): e.index for e in me.edges}
        zone = {v.index for v in me.vertices if 0.10 < abs((M @ v.co).x) < 0.95 and -2.4 < (M @ v.co).y < 0.95 and (M @ v.co).z < 0.10}
        em = {}
        for p_ in me.polygons:
            if p_.material_index == pi:
                for ek in p_.edge_keys:
                    em.setdefault(ek, []).append(p_.index)
        nun = 0
        if sh_ is not None:
            for ek, fl in em.items():
                if len(fl) == 2 and (ek[0] in zone or ek[1] in zone) and me.polygons[fl[0]].normal.dot(me.polygons[fl[1]].normal) >= c20:
                    ei_ = eidx_[tuple(sorted(ek))]
                    if sh_.data[ei_].value:
                        sh_.data[ei_].value = False; nun += 1
        cust = [c.vector.copy() for c in me.corner_normals]
        lo = {}
        for p_ in me.polygons:
            if p_.material_index == pi:
                for li in p_.loop_indices:
                    lo[(p_.index, me.loops[li].vertex_index)] = li
        vp = {}
        for ek, fl in em.items():
            if len(fl) == 2 and not (sh_ is not None and sh_.data[eidx_[tuple(sorted(ek))]].value):
                for v in ek:
                    if v in zone:
                        vp.setdefault(v, []).append(fl)
        nset = 0
        for v, pairs in vp.items():
            par = {}

            def fnd(a):
                while par.setdefault(a, a) != a:
                    par[a] = par[par[a]]; a = par[a]
                return a
            for a, b in pairs:
                ra, rb = fnd(a), fnd(b)
                if ra != rb:
                    par[ra] = rb
            cl = {}
            for f_ in par:
                cl.setdefault(fnd(f_), []).append(f_)
            for fs_ in cl.values():
                ls_ = [lo[(f_, v)] for f_ in fs_]
                m_ = sum((cust[l_] for l_ in ls_), V((0, 0, 0)))
                if m_.length < 1e-12:
                    continue
                m_.normalize()
                if all(m_.dot(me.polygons[f_].normal) >= 0.5 for f_ in fs_):
                    for l_ in ls_:
                        cust[l_] = m_
                    nset += 1
        me.normals_split_custom_set(cust)
        print('[a6m2] r8j: fan seam fix pass: sharp unflagged', nun, 'fans set', nset)


def well_detail(objs):
    """r8l: ribs and a rim lip inside each main well (a6m2_parts.well_detail_segments), joined to the root mesh (fus_center) as closed
    bars in 'well' (src 3), and the well ceiling between them in 'well_dark' (darker recesses). A segment is dropped if the main leg or
    wheel touches it at any retraction step (0..retract every 5 deg), so the gear still retracts and stows clear."""
    import bmesh, json
    from mathutils import Quaternion
    from mathutils.bvhtree import BVHTree
    fc = objs['fus_center']
    gear = {}
    for L in 'LR':
        s_ = objs.get(f'gear_main_{L}_strut')
        if s_ is None:
            continue
        inf = json.loads(s_['b25_info'])
        piv = V(inf['pivot']); ax = V(inf['retract_axis_world'])
        obs = [s_] + [o for o in s_.children_recursive if o.type == 'MESH']
        tri = []
        for o in obs:
            me = o.data; me.calc_loop_triangles(); mw = o.matrix_world
            vs = [mw @ v.co for v in me.vertices]
            tri.append((vs, [tuple(t.vertices) for t in me.loop_triangles]))
        trees = []
        degs = list(range(0, int(inf['retract_deg']) + 1, 5)) + [inf['retract_deg']]
        for dg in degs:
            q = Quaternion(ax, math.radians(dg))
            for vs, ts in tri:
                trees.append(BVHTree.FromPolygons([piv + q @ (v - piv) for v in vs], ts))
        gear[-1 if L == 'L' else 1] = trees
    bpy.context.view_layer.update()
    mb = AP.MeshBuf(); kept = {}; dropped = {}
    for side in (1, -1):
        for p0, p1, w, h, up, kind in AP.well_detail_segments(side):
            # full depth; ceiling ribs that the gear would touch are tried at a shallow depth (hung from the same ceiling line) first
            tries = [(p0, p1, h)]
            if kind != 'lip':
                h2 = AP.WELL_BURY + 0.005
                tries.append((p0 + up * (h / 2 - h2 / 2), p1 + up * (h / 2 - h2 / 2), h2))
            for k_, (a_, b_, hh) in enumerate(tries):
                one = AP.MeshBuf()
                AP.bar(one, a_, b_, w, hh, up, 'well')
                t_ = BVHTree.FromPolygons(one.verts, [f['idx'] for f in one.faces])
                if not any(t_.overlap(g) for g in gear.get(side, [])):
                    AP.bar(mb, a_, b_, w, hh, up, 'well')
                    kn = kind if k_ == 0 else kind + '_shallow'
                    kept[kn] = kept.get(kn, 0) + 1
                    break
            else:
                dropped[kind] = dropped.get(kind, 0) + 1
    mats = [m.name if m else '' for m in fc.data.materials]
    for mn in ('well', 'well_dark'):
        if mn not in mats and bpy.data.materials.get(mn):
            fc.data.materials.append(bpy.data.materials[mn]); mats.append(mn)
    wi, wd = mats.index('well'), mats.index('well_dark')
    inv = fc.matrix_world.inverted(); R3 = fc.matrix_world.to_3x3()
    bm = bmesh.new(); bm.from_mesh(fc.data)
    src_l = bm.faces.layers.int.get('src') or bm.faces.layers.int.new('src')
    # darker recesses: the ceiling of each well (faces down, inside the opening, high in the well)
    ndark = 0
    for f in bm.faces:
        if f.material_index != wi:
            continue
        c_ = fc.matrix_world @ f.calc_center_median(); n_ = (R3 @ f.normal).normalized()
        if n_.z < -0.85 and AP.in_opening(c_) and c_.z > AP.lower_z(c_.x, c_.y) + 0.12:
            f.material_index = wd; ndark += 1
    vv = [bm.verts.new(inv @ p) for p in mb.verts]
    nf = 0
    for f in mb.faces:
        try:
            nf_ = bm.faces.new([vv[i] for i in f['idx']])
        except ValueError:
            continue
        nf_.material_index = wi; nf_[src_l] = 3; nf_.smooth = False; nf += 1
    bm.to_mesh(fc.data); bm.free()
    return dict(kept=kept, dropped=dropped, faces=nf, dark_ceiling_faces=ndark)


def unify_root(objs):
    """r8e (coordinator: the root was a stack of overlapping sheets; patching four meshes did not converge): ONE root mesh.
    fus_center UNION wing_C (0..0.95) UNION fillet_L / fillet_R (EXACT boolean, hole tolerant: the fuselage shell is open at the cockpit),
    then the wheel wells are SUBTRACTED (cutter = a6m2_parts.well_cutter, material 'well') from the root mesh and from wing_inner_L/R.
    Face attribute 'src' (0 fuselage, 1 wing centre, 2 fairing) keeps where each face came from (livery groups in the textures). The
    merged objects' children are re-parented to fus_center; wing_C / fillet_* objects are removed (their Parts stay in the contract).
    An empty 'wing_C_qc' marks the centre-section quarter chord (Unity: the root lift point)."""
    import bmesh
    import a6m2_parts as AP_
    fc = objs['fus_center']
    merge = [objs[n] for n in ('wing_C', 'fillet_L', 'fillet_R') if n in objs]
    for ob in [fc] + merge + [objs[n] for n in ('wing_inner_L', 'wing_inner_R') if n in objs]:
        bm = bmesh.new(); bm.from_mesh(ob.data)                  # weld first: wing_C's two halves meet at x = 0 (closed solid for the boolean)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bm.to_mesh(ob.data); bm.free()
    for ob, v in [(fc, 0)] + [(o, 1 if o.name == 'wing_C' else 2) for o in merge]:
        at = ob.data.attributes.get('src') or ob.data.attributes.new('src', 'INT', 'FACE')
        at.data.foreach_set('value', [v] * len(ob.data.polygons))
    vl = bpy.context.view_layer

    def apply_bool(target, operands, op):
        coll = bpy.data.collections.new('ops_' + target.name)
        bpy.context.scene.collection.children.link(coll)
        for o in operands:
            coll.objects.link(o)
        m = target.modifiers.new('r8e_bool', 'BOOLEAN')
        m.operation = op; m.solver = 'EXACT'; m.operand_type = 'COLLECTION'; m.collection = coll
        m.use_hole_tolerant = True; m.use_self = False
        try:
            m.material_mode = 'TRANSFER'
        except Exception:
            pass
        for o in bpy.context.scene.objects:
            o.select_set(False)
        target.hide_set(False); target.select_set(True); vl.objects.active = target
        bpy.ops.object.modifier_apply(modifier=m.name)
        for o in list(coll.objects):
            coll.objects.unlink(o)
        bpy.data.collections.remove(coll)
    # the fuselage SKIN (paint faces) as a closed solid: split it off, fill its open rings (cockpit opening, the joints to the cowl and
    # the rear fuselage) with temporary caps (src 9), union, drop the caps, join the rest of fus_center (tub, internals) back unchanged
    mats_fc = [m.name if m else '' for m in fc.data.materials]
    bm = bmesh.new(); bm.from_mesh(fc.data)
    pi_ = mats_fc.index('paint')
    rest = [f for f in bm.faces if f.material_index != pi_]
    bm_rest = bmesh.new(); bm_rest.from_mesh(fc.data)
    bmesh.ops.delete(bm_rest, geom=[f for f in bm_rest.faces if f.material_index == pi_], context='FACES')
    bmesh.ops.delete(bm, geom=rest, context='FACES')
    src_l = bm.faces.layers.int.get('src')
    edges = [e for e in bm.edges if e.is_boundary]
    res = bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    newf = res.get('faces', [])
    for f in newf:
        f[src_l] = 9
    bmesh.ops.triangulate(bm, faces=newf)
    skin_me = bpy.data.meshes.new('fus_skin_tmp'); bm.to_mesh(skin_me); bm.free()
    for m in fc.data.materials:
        skin_me.materials.append(m)
    rest_me = bpy.data.meshes.new('fus_rest_tmp'); bm_rest.to_mesh(rest_me); bm_rest.free()
    for m in fc.data.materials:
        rest_me.materials.append(m)
    old_me = fc.data
    fc.data = skin_me
    apply_bool(fc, merge, 'UNION')
    # leftovers the hole-tolerant classification kept INSIDE the fuselage (wing / fairing faces under the capped cockpit opening): removed
    bm = bmesh.new(); bm.from_mesh(fc.data); bm.transform(fc.matrix_world)
    src_l = bm.faces.layers.int.get('src')
    gone = []
    for f in bm.faces:
        if f[src_l] not in (1, 2):
            continue
        c = f.calc_center_median()
        zt_, zb_ = AP_.body_params(c.y)[0], AP_.body_params(c.y)[1]
        if zb_ + 0.006 < c.z < zt_ - 0.006 and abs(c.x) < AP_.body_ring_x(c.y, c.z) - 0.006:
            gone.append(f)
    bmesh.ops.delete(bm, geom=gone, context='FACES')
    bm.transform(fc.matrix_world.inverted()); bm.to_mesh(fc.data); bm.free()
    print('[a6m2] r8e: removed', len(gone), 'wing / fairing faces left inside the fuselage by the boolean')
    for o in merge:
        for ch in list(o.children):
            mw = ch.matrix_world.copy(); ch.parent = fc; ch.matrix_world = mw
    for o in merge:
        objs.pop(o.name, None)
        bpy.data.objects.remove(o, do_unlink=True)
    # wells: cutters per side, subtracted from the (still capped, closed) root skin and from the side's wing_inner
    well_mat = bpy.data.materials.get('well')
    cutters = {}
    for side in (1, -1):
        bot, top = AP_.well_cutter(side)
        bm = bmesh.new()
        vb = [bm.verts.new(p) for p in bot]; vt = [bm.verts.new(p) for p in top]
        n = len(vb)
        fb = bm.faces.new(list(reversed(vb))); ft = bm.faces.new(vt)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([vb[i], vb[j], vt[j], vt[i]])
        bmesh.ops.triangulate(bm, faces=[fb, ft])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(f'well_cut_{side}'); bm.to_mesh(me); bm.free()
        if well_mat:
            me.materials.append(well_mat)
        ob = bpy.data.objects.new(f'well_cut_{side}', me)
        bpy.context.scene.collection.objects.link(ob)
        cutters[side] = ob
    apply_bool(fc, list(cutters.values()), 'DIFFERENCE')
    for side, L in ((1, 'R'), (-1, 'L')):
        wi = objs.get(f'wing_inner_{L}')
        if wi is not None:
            apply_bool(wi, [cutters[side]], 'DIFFERENCE')
    for ob in cutters.values():
        bpy.data.objects.remove(ob, do_unlink=True)
    # drop the temporary caps, join the tub / internals back (same material slot order: TRANSFER only appends)
    bm = bmesh.new(); bm.from_mesh(fc.data)
    src_l = bm.faces.layers.int.get('src')
    # the wing centre section runs forward through the cowl-joint plane under the chin: dropping the caps opens the wing's cross-section
    # there (a hole in the pocket behind the oil-cooler scoop). That loop - the boundary edges under the belly ring at the joint - is
    # closed again as a dark firewall plate (inside the scoop pocket, never seen against the sky).
    mats_now = [m.name if m else '' for m in fc.data.materials]
    dk = mats_now.index('ck_dark') if 'ck_dark' in mats_now else 0
    Mw = fc.matrix_world
    drop = [f for f in bm.faces if f[src_l] == 9]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    def _w(e):
        return Mw @ ((e.verts[0].co + e.verts[1].co) / 2)
    chin_e = [e for e in bm.edges if e.is_boundary and abs(_w(e).x) < 0.26 and 0.68 < _w(e).y < 0.84 and _w(e).z < -0.40]
    fw = bmesh.ops.edgeloop_fill(bm, edges=chin_e, mat_nr=dk).get('faces', []) if chin_e else []
    if not fw and chin_e:
        fw = bmesh.ops.holes_fill(bm, edges=chin_e, sides=0).get('faces', [])
    for f in fw:
        f[src_l] = 0; f.material_index = dk
    if fw:
        bmesh.ops.triangulate(bm, faces=fw)
    print('[a6m2] r8e: chin firewall plate', len(chin_e), 'boundary edges ->', len(fw), 'faces')
    bm.from_mesh(rest_me)
    bm.to_mesh(fc.data); bm.free()
    bpy.data.meshes.remove(rest_me); bpy.data.meshes.remove(old_me)
    for ob in [fc] + [objs[n] for n in ('wing_inner_L', 'wing_inner_R') if n in objs]:     # boolean slivers (0.2 mm2 faces, zero-length edges)
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=5e-5)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-4)
        # zero-thickness double sheets (a fuselage face and a wing face on the same vertices, opposite normals, where the two skins
        # coincide): both are internal - removed (they made the >2-face edges of the root_unified check)
        seen = {}
        dup = set()
        for f in bm.faces:
            key = frozenset(v.index for v in f.verts)
            if key in seen:
                dup.add(f); dup.add(seen[key])
            else:
                seen[key] = f
        bmesh.ops.delete(bm, geom=list(dup), context='FACES')
        fold = set()                               # folded pairs on a >2-face edge: coplanar, opposite normals (the same double sheet, split differently)
        for e in bm.edges:
            lf = list(e.link_faces)
            if len(lf) <= 2:
                continue
            for i in range(len(lf)):
                for j in range(i + 1, len(lf)):
                    if lf[i].normal.dot(lf[j].normal) < -0.98:
                        fold.add(lf[i]); fold.add(lf[j])
        M_ = ob.matrix_world

        def inside(pw):                            # inside the fuselage hull or the wing (world point)
            zt_, zb_ = AP_.body_params(pw.y)[0], AP_.body_params(pw.y)[1]
            if zb_ < pw.z < zt_ and abs(pw.x) < AP_.body_ring_x(pw.y, pw.z):
                return True
            st_ = AP_.wing_station(min(abs(pw.x), 6.0), 1)
            s_ = (st_.le.y - pw.y) / st_.chord
            return 0.0 < s_ < 1.0 and AP_.lower_z(abs(pw.x), pw.y) < pw.z < AP_.upper_z(abs(pw.x), pw.y)
        drop = []
        for f in fold:                             # of each folded pair keep the face whose front looks OUT of the solid
            c = M_ @ f.calc_center_median()
            nw = (M_.to_3x3() @ f.normal).normalized()
            if inside(c + nw * 0.003):
                drop.append(f)
        bmesh.ops.delete(bm, geom=drop, context='FACES')
        # seal the boolean's millimetre slits (T-junction vertices left apart where the well walls meet the skin, the chin fold): weld
        # skin boundary vertices within 1.5 mm, then fill boundary loops of at most 10 edges. The designed rings have hundreds of edges.
        mats_o = [m.name if m else '' for m in ob.data.materials]
        skin_i = {i for i, n in enumerate(mats_o) if n in ('paint', 'well')}
        bv = list({v for e in bm.edges if e.is_boundary and any(f.material_index in skin_i for f in e.link_faces) for v in e.verts})
        bmesh.ops.remove_doubles(bm, verts=bv, dist=0.0015)
        def _ends():                               # ends of open boundary chains (a slit whose mouth did not weld)
            return [v for v in bm.verts if v.is_valid and sum(1 for e in v.link_edges if e.is_boundary
                    and any(f.material_index in skin_i for f in e.link_faces)) == 1]
        ends = _ends(); used = set()
        for v in ends:
            if v in used:
                continue
            best = min((w for w in ends if w is not v and w not in used), key=lambda w: (w.co - v.co).length, default=None)
            joined = best is not None and any(best in e.verts for e in v.link_edges)   # the slit's mouth is one fold edge: collapse it
            if best is not None and ((best.co - v.co).length < 0.006 or (joined and (best.co - v.co).length < 0.015)):
                used.add(v); used.add(best)
                bmesh.ops.pointmerge(bm, verts=[v, best], merge_co=(v.co + best.co) / 2)
        be = [e for e in bm.edges if e.is_boundary and any(f.material_index in skin_i for f in e.link_faces)]
        sealed = bmesh.ops.holes_fill(bm, edges=be, sides=10).get('faces', [])
        for f in sealed:
            nb = [g for e in f.edges for g in e.link_faces if g is not f]
            if nb:
                f.material_index = nb[0].material_index
                if src_ob := bm.faces.layers.int.get('src'):
                    f[src_ob] = nb[0][src_ob]
                # r8h: a filled slit has no UVs of its own - its loops took UVs from vertices of DIFFERENT atlas islands and the face
                # spanned the atlas (the livery bake then painted it across other islands: a bite out of the IJN fuselage hinomaru).
                # Every UV layer of the patch takes the neighbour's UV at a shared vertex (one texel colour = the neighbour's paint)
                for uvl in bm.loops.layers.uv.values():
                    ref = None
                    for lp in nb[0].loops:
                        if lp.vert in f.verts:
                            ref = lp[uvl].uv.copy(); break
                    if ref is None:
                        ref = nb[0].loops[0][uvl].uv.copy()
                    for lp in f.loops:
                        lp[uvl].uv = ref
        if sealed:
            bmesh.ops.triangulate(bm, faces=sealed)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-4)
        # r8h: zero-area needle triangles (long edges, no height) survive dissolve_degenerate and read as flipped faces: collapse their
        # shortest edge
        ncol = 0
        for _ in range(3):
            nd = [f for f in bm.faces if f.is_valid and f.calc_area() < 1e-6 and f.calc_area() < 0.01 * max(e.calc_length() for e in f.edges) ** 2]
            if not nd:
                break
            es = []
            for f in nd:
                e = min(f.edges, key=lambda e: e.calc_length())
                if e.is_valid and e not in es:
                    es.append(e)
            try:
                bmesh.ops.collapse(bm, edges=es, uvs=False); ncol += len(es)   # uvs=False: averaging UVs across islands made atlas-spanning faces
            except Exception:
                break
        print('[a6m2] r8h:', ob.name, 'needle triangles collapsed', ncol)
        print('[a6m2] r8e:', ob.name, 'sealed', len(sealed), 'slit faces;', len(bv), 'boundary verts welded within 1.5 mm')
        bm.to_mesh(ob.data); bm.free()
    # r8f (game r8e z_L0_lowR: a small light notch at the inboard end of the lower flap-cove line): the cove's inboard end wall
    # (src 1, facing outboard at the flap's inboard end x 0.70) showed through the gap at the flap end in livery paint. It is aotake
    # ('well', dark) like the cove ceiling.
    import a6m2_spec as SP_
    xf0 = SP_.span_built(SP_.FLAP_X[0])
    mats_fc = [m.name if m else '' for m in fc.data.materials]
    if 'well' in mats_fc and 'paint' in mats_fc:
        wi_, pi_ = mats_fc.index('well'), mats_fc.index('paint')
        srcA = fc.data.attributes.get('src'); R3 = fc.matrix_world.to_3x3(); Mw = fc.matrix_world; nwall = 0
        for poly in fc.data.polygons:
            if poly.material_index != pi_ or srcA is None or srcA.data[poly.index].value != 1:
                continue
            c = Mw @ poly.center; n = (R3 @ poly.normal).normalized()
            if abs(abs(c.x) - xf0) < 0.015 and abs(n.x) > 0.9 and c.z < AP_.upper_z(abs(c.x), c.y) - 0.008:
                poly.material_index = wi_; nwall += 1
        print('[a6m2] r8f: flap-cove inboard end walls in aotake:', nwall, 'faces')
    # the root lift point for Unity (was wing_C's mesh bounds)
    st = AP_.wing_station(0.0, 1)
    qc = st.le + st.cdir * (0.25 * st.chord)
    e = bpy.data.objects.new('wing_C_qc', None); bpy.context.scene.collection.objects.link(e)
    for c in fc.users_collection:
        if e.name not in c.objects:
            c.objects.link(e)
    bpy.context.scene.collection.objects.unlink(e)
    e.matrix_world = __import__('mathutils').Matrix.Translation(qc)
    mw = e.matrix_world.copy(); e.parent = fc; e.matrix_world = mw
    objs['wing_C_qc'] = e
    return len(fc.data.polygons)


DRUM_BACK_MAT = 'interior'   # r8o round 3 (round 2: 'metal_dark' = a black box in the fus_center wing-root view)


def _clip_z(pts, zc, below=True, f=None):
    """r8o round 3: the part of a convex polygon where f(p) <= zc (below) or >= zc (Sutherland-Hodgman, one plane; f default p.z)."""
    f = f or (lambda p: p.z)
    ins = (lambda p: f(p) <= zc) if below else (lambda p: f(p) >= zc)
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if ins(a):
            out.append(a)
        fa, fb = f(a), f(b)
        if ins(a) != ins(b) and abs(fb - fa) > 1e-12:
            out.append(a + (b - a) * ((zc - fa) / (fb - fa)))
    return [p for k, p in enumerate(out) if k == 0 or (p - out[k - 1]).length > 1e-7]


def open_root_breaks(objs):
    """r8o (user test r8n: solid metal discs at every break): the wing parts that go through unify_root's booleans kept a temporary fan
    cap (a6m2_parts.WING_CAP_MAT) in the root break plane |x| = br0, so the booleans saw closed solids; the caps are removed here (wing_C's
    in fus_center: src 1; wing_inner_L / R) and the open ends a6m2_parts.POST_ADD (dark skin edge, liner, set-back rib, stubs) are added.
    Returns (removed cap faces, added faces)."""
    import bmesh
    import a6m2_parts as AP_
    from b25h_geom import planar_uv
    bpy.context.view_layer.update()
    br0 = S.span_built(S.WING_BREAKS[0])
    removed = 0
    for name in ('fus_center', 'wing_inner_L', 'wing_inner_R'):
        ob = objs.get(name)
        if ob is None:
            continue
        me = ob.data
        mats_ = [m.name if m else '' for m in me.materials]
        if AP_.WING_CAP_MAT not in mats_:
            continue
        mi = mats_.index(AP_.WING_CAP_MAT)
        bm = bmesh.new(); bm.from_mesh(me)
        src_l = bm.faces.layers.int.get('src')
        M = ob.matrix_world; R3 = M.to_3x3()
        planes = {sd: AP_.wing_break_plane(sd, br0) for sd in (1, -1)}      # the section plane leans with the dihedral (+-20 mm in x)
        gone = []
        for f in bm.faces:
            if f.material_index != mi:
                continue
            if src_l is not None and f[src_l] != 1:
                continue
            ws = [M @ v.co for v in f.verts]
            nn = (R3 @ f.normal).normalized()
            p0, pn = planes[1 if sum(w.x for w in ws) > 0 else -1]
            if abs(nn.dot(pn)) > 0.95 and all(abs((w - p0).dot(pn)) < 0.002 for w in ws):
                gone.append(f)
        bmesh.ops.delete(bm, geom=gone, context='FACES')
        removed += len(gone)
        bm.to_mesh(me); bm.free()
    added = 0
    for name, mbuf in AP_.POST_ADD.items():
        ob = objs.get(name)
        if ob is None or not mbuf.faces:
            continue
        me = ob.data
        mats_ = [m.name if m else '' for m in me.materials]
        for f in mbuf.faces:
            if f['mat'] not in mats_:
                me.materials.append(bpy.data.materials[f['mat']]); mats_.append(f['mat'])
        bm = bmesh.new(); bm.from_mesh(me)
        inv = ob.matrix_world.inverted()
        liv = bm.loops.layers.uv.get('livery'); det = bm.loops.layers.uv.get('detail')
        vmap = {}
        for f in mbuf.faces:
            vs = []
            for i in f['idx']:
                if i not in vmap:
                    vmap[i] = bm.verts.new(inv @ mbuf.verts[i])
                vs.append(vmap[i])
            try:
                face = bm.faces.new(vs)
            except ValueError:
                continue
            face.material_index = mats_.index(f['mat']); face.smooth = f['smooth']
            pts = [mbuf.verts[i] for i in f['idx']]
            n = (pts[1] - pts[0]).cross(pts[-1] - pts[0])
            for k, lp in enumerate(face.loops):
                if liv is not None:
                    lp[liv].uv = (0.0, 0.0)
                if det is not None:
                    du = planar_uv(pts[k], n)
                    lp[det].uv = (du[0] * 0.5, du[1] * 0.5)
            added += 1
        bm.to_mesh(me); bm.free()
    # r8o round 2: the lined break cavities at the wing root (wing_C in fus_center to |x| 0.535, wing_inner to 0.85 m) are crossed by the
    # wheel-well drum / leg-slot walls ('well', boolean-cut, facing into the well): from the cavity one saw their back faces (culled ->
    # the sky through the well). Each such wall face gets a back 1 mm outside the well (reversed).
    # r8o round 3 (review of round 2: from the fus_center wing root the drum backs read as a large black box): the backs are in the liner's
    # interior paint (DRUM_BACK_MAT), so the drum reads as the curved inboard wall of the lined bay, not a black block.
    backs = 0
    for name in ('fus_center', 'wing_inner_L', 'wing_inner_R'):
        ob = objs.get(name)
        if ob is None:
            continue
        me = ob.data
        mats_ = [m.name if m else '' for m in me.materials]
        if 'well' not in mats_:
            continue
        if DRUM_BACK_MAT not in mats_:
            me.materials.append(bpy.data.materials[DRUM_BACK_MAT]); mats_.append(DRUM_BACK_MAT)
        if 'metal_dark' not in mats_:
            me.materials.append(bpy.data.materials['metal_dark']); mats_.append('metal_dark')
        wi, mdi, mdk = mats_.index('well'), mats_.index(DRUM_BACK_MAT), mats_.index('metal_dark')
        lo_, hi_ = ((br0 - AP_.wing_cavity(br0, 1) - 0.01, br0) if name == 'fus_center' else (br0, br0 + AP_.wing_cavity(br0, -1) + 0.01))
        bm = bmesh.new(); bm.from_mesh(me)
        det = bm.loops.layers.uv.get('detail'); liv = bm.loops.layers.uv.get('livery')
        M = ob.matrix_world; R3 = M.to_3x3(); inv = M.inverted()
        new = []
        for f in list(bm.faces):
            if f.material_index != wi or f.calc_area() < 1e-9:
                continue
            ws = [M @ v.co for v in f.verts]
            c = sum(ws, V()) / len(ws)
            nn = (R3 @ f.normal).normalized()
            if abs(nn.z) > 0.7 or not (lo_ <= abs(c.x) <= hi_):
                continue
            # round 3: within 35 mm of the root plane (seam band, C8) or 60 mm of the lower wing skin (seen past the well rim from outside,
            # root_seam) the back stays metal_dark: the face is clipped at z = lower skin + 0.06 into a dark lower and a lined upper piece
            try:
                zcut = AP_.lower_z(abs(c.x), c.y) + 0.06
            except Exception:
                zcut = 9.0
            ax_ = lambda p: abs(p.x)
            xb_ = br0 - 0.035 if name == 'fus_center' else br0 + 0.035          # the 35 mm band next to the root plane
            near = _clip_z(ws, xb_, below=(name != 'fus_center'), f=ax_)
            far = _clip_z(ws, xb_, below=(name == 'fus_center'), f=ax_)
            pieces = [(near, True), (_clip_z(far, zcut, below=True), True)] if len(far) >= 3 else [(near, True)]
            if len(far) >= 3:
                pieces.append((_clip_z(far, zcut, below=False), False))
            for piece, dark in pieces:
                if len(piece) >= 3:
                    rv = list(reversed(piece))
                    new.append(([inv @ (w - nn * 0.001) for w in rv], -nn, rv, dark))
        for pts, nn, ws, dark in new:
            try:
                face = bm.faces.new([bm.verts.new(p) for p in pts])
            except ValueError:
                continue
            face.material_index = mdk if dark else mdi
            for k, lp in enumerate(face.loops):
                if liv is not None:
                    lp[liv].uv = (0.0, 0.0)
                if det is not None:
                    du = planar_uv(ws[k], nn)
                    lp[det].uv = (du[0] * 0.5, du[1] * 0.5)
            backs += 1
        bm.to_mesh(me); bm.free()
    print('[a6m2] r8o round 3: backs (' + DRUM_BACK_MAT + ') on the well / slot walls in the root cavities', backs)
    return removed, added


def pack_ck_atlas(objs):
    """r8c: third UV set 'ckatlas' (Unity UV2) - unique packed islands on the cockpit-view faces (a6m2_ck_atlas.face_in_atlas), every
    other face (-1, -1). Smart-project (55 deg) per selection, packed across all objects in one 0-1 square with a 4 px margin at 2048."""
    import bmesh
    import a6m2_ck_atlas as CA
    targets, nface = [], 0
    for ob in objs.values():
        if ob.type != 'MESH':
            continue
        me = ob.data
        lay = me.uv_layers.get('ckatlas') or me.uv_layers.new(name='ckatlas', do_init=False)
        mats = [m.name if m else '' for m in me.materials]
        M = ob.matrix_world
        sel = set()
        for poly in me.polygons:
            c = M @ poly.center
            if CA.face_in_atlas(ob.name, mats[poly.material_index] if poly.material_index < len(mats) else '', (c.x, c.y, c.z)):
                sel.add(poly.index)
        for poly in me.polygons:
            if poly.index not in sel:
                for li in poly.loop_indices:
                    lay.data[li].uv = CA.OUTSIDE
        if sel:
            targets.append((ob, sel)); nface += len(sel)
    if not targets:
        return 0
    # only faces the pilot can see (eye + head movement), glass and the exterior canopy ignored: hidden faces keep the tiling materials
    from mathutils.bvhtree import BVHTree
    vs, ps, owner = [], [], []
    for ob in objs.values():
        if ob.type != 'MESH' or ob.name.startswith(('canopy_', 'pilot', 'store_')):
            continue
        me = ob.data; M = ob.matrix_world
        mats = [m.name if m else '' for m in me.materials]
        b0 = len(vs)
        vs.extend(M @ v.co for v in me.vertices)
        for poly in me.polygons:
            mn = mats[poly.material_index] if poly.material_index < len(mats) else ''
            if mn.startswith(('glass', 'sightglass')):
                continue
            ps.append([b0 + i for i in poly.vertices]); owner.append((ob.name, poly.index))
    bvh = BVHTree.FromPolygons(vs, ps, epsilon=0.0)
    eyes = [V((ex, -1.025 + ey, 0.79 + ez)) for ex in (-0.10, 0.0, 0.10) for ey in (-0.10, 0.10) for ez in (-0.08, 0.06)] + [V((0.0, -1.025, 0.79))]
    nface = 0
    vis_t = []
    for ob, sel in targets:
        me = ob.data; M = ob.matrix_world
        keep = set()
        for fi in sel:
            poly = me.polygons[fi]
            c0 = M @ poly.center
            samples = [c0] + [c0 + ((M @ me.vertices[vi].co) - c0) * 0.85 for vi in poly.vertices]
            seen = False
            for c in samples:
                for e in eyes:
                    d = c - e
                    L = d.length
                    if L < 1e-4:
                        continue
                    hit = bvh.ray_cast(e, d / L, L + 0.01)
                    if hit[0] is None or (hit[0] - c).length < 0.004 or owner[hit[2]] == (ob.name, fi):
                        seen = True
                        break
                if seen:
                    break
            if seen:
                keep.add(fi)
        lay = me.uv_layers['ckatlas']
        for fi in sel - keep:
            for li in me.polygons[fi].loop_indices:
                lay.data[li].uv = CA.OUTSIDE
        if keep:
            vis_t.append((ob, keep)); nface += len(keep)
    targets = vis_t
    if not targets:
        return 0
    vl = bpy.context.view_layer
    for ob in bpy.context.scene.objects:
        ob.select_set(False)
    for ob, _ in targets:
        ob.hide_set(False); ob.select_set(True)
        ob.data.uv_layers.active = ob.data.uv_layers['ckatlas']
    vl.objects.active = targets[0][0]
    bpy.ops.object.mode_set(mode='EDIT')
    for ob, sel in targets:
        bm = bmesh.from_edit_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.select_set(f.index in sel)
        bmesh.update_edit_mesh(ob.data)
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin=4.0 / CA.RES[0])
    bpy.ops.object.mode_set(mode='OBJECT')
    for ob, _ in targets:
        ob.data.uv_layers.active = ob.data.uv_layers['livery'] if 'livery' in ob.data.uv_layers else ob.data.uv_layers[0]
        ob.select_set(False)
    return nface


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.abspath(os.path.join(HERE, '..', '..', 'assets', 'model_a6m2', 'a6m2.blend'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    B.MATERIALS = MATERIALS
    mats = B.make_materials()
    parts = AP.build_exterior()
    for p in parts:
        p.uv_group = uv_group(p.name)
    root_c, mass, rows = com(parts)
    print(f'[a6m2] CoM {tuple(round(c, 4) for c in root_c)} parts+loads {mass:.0f} kg')
    parts.insert(0, Part('A6M2_root', None, tuple(root_c), None, info=dict(note=f'CoM (fuel {FUEL_FRACTION:.0%}), {mass:.0f} kg')))
    flipped = flip_backside_uvs(parts)
    print('[a6m2] round 5: planar paint UVs mirrored on', flipped, 'back-facing faces (no shared islands across thin shells)')
    usage, m_per_uv = B.pack_livery(parts)
    coll = bpy.data.collections.new('A6M2')
    sc.collection.children.link(coll)
    objs = B.create_objects(parts, mats, coll)
    print('[a6m2] r8e: unified root mesh', unify_root(objs), 'faces')
    if AP.OPEN_BREAKS:
        print('[a6m2] r8o: open root breaks (temporary cap faces removed, open-end faces added)', open_root_breaks(objs))
    if AP.WELL_DETAIL:
        print('[a6m2] r8l: well detail', well_detail(objs))
    import bmesh
    welded = 0
    for ob in objs.values():
        if ob.type != 'MESH':
            continue
        bm = bmesh.new(); bm.from_mesh(ob.data)
        n0 = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
        welded += n0 - len(bm.verts)
        bm.to_mesh(ob.data); bm.free()
        try:
            ob.data.set_sharp_from_angle(angle=math.radians(38))
        except Exception:
            pass
    prop_tip_uvs(objs)
    print('[a6m2] r8b: unified skin normals on', unify_skin_normals(objs), 'paint loops across the part cuts')
    print('[a6m2] r8c: cockpit atlas (ckatlas UV2) on', pack_ck_atlas(objs), 'faces')
    tris = sum(len(p.vertices) - 2 for o in objs.values() if o.type == 'MESH' for p in o.data.polygons)
    stats = dict(objects=len(objs), tris=tris, welded=welded, livery_usage=round(usage, 4), metres_per_uv=round(m_per_uv, 3),
                 cg_blender=[round(x, 3) for x in root_c], mass=round(mass, 1))
    sc['b25_build_stats'] = json.dumps(stats)
    print('[a6m2] ' + json.dumps(stats))
    with open(os.path.join(os.path.dirname(out), 'a6m2_contract.json'), 'w') as f:
        json.dump(contract(parts, V(root_c), mass, rows), f, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('[a6m2] saved', out)


if __name__ == '__main__':
    main()
