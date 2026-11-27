"""Build the Hawker Nimrod Mk I model (procedural, our own geometry) and save it as a .blend + contract json.

  blender --background --factory-startup --python-exit-code 1 --python blender/nimrod/build_nimrod.py -- --out assets/model_nimrod/nimrod.blend

Blender space: nose +Y, up +Z, right wing +X, metres, flight attitude (gear fixed). Paint faces share one packed UV atlas
`livery`; every face also has a tiling UV `detail`. The root empty NIMROD1_root sits at the computed CG (50 % fuel) and
becomes the FBX/Unity origin (export_nimrod.py). Reuses the B-25H v2 pipeline functions (pack_livery, create_objects)
read-only; nothing of the B-25H is modified.
"""
import bpy, sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.abspath(os.path.join(HERE, '..', 'v2'))
for p in (HERE, V2):
    if p not in sys.path:
        sys.path.insert(0, p)
for m in ('nimrod_spec', 'nimrod_structure', 'nimrod_props', 'nimrod_parts', 'nimrod_ck_layout', 'nimrod_cockpit'):
    sys.modules.pop(m, None)
from mathutils import Vector as V
import build_b25h_v2 as B           # pack_livery / create_objects / make_materials (generic)
from b25h_parts import Part
import nimrod_spec as S
import nimrod_parts as NP
import nimrod_cockpit as NC

MATERIALS = {   # name: (base colour RGBA, metallic, roughness)  - Unity builds its own materials per name
    'paint': ((0.72, 0.73, 0.74, 1.0), 0.3, 0.45),        # aluminium dope
    'structure': ((0.55, 0.56, 0.56, 1.0), 0.6, 0.45),
    'metal_dark': ((0.08, 0.08, 0.085, 1.0), 0.6, 0.45),
    'exhaust': ((0.20, 0.13, 0.09, 1.0), 0.5, 0.7),
    'radiator': ((0.10, 0.10, 0.09, 1.0), 0.6, 0.5),
    'gunmetal': ((0.12, 0.12, 0.13, 1.0), 0.8, 0.35),
    'rubber': ((0.025, 0.025, 0.025, 1.0), 0.0, 0.9),
    'prop': ((0.33, 0.20, 0.10, 1.0), 0.0, 0.35),          # varnished laminated wood
    'spinner': ((0.75, 0.76, 0.78, 1.0), 0.8, 0.30),
    'hookyellow': ((0.80, 0.62, 0.08, 1.0), 0.1, 0.5),
    'glass': ((0.70, 0.80, 0.85, 0.20), 0.0, 0.05),
    'interior': ((0.40, 0.43, 0.39, 1.0), 0.0, 0.85),       # grey-green interior dope
    'tube': ((0.20, 0.21, 0.20, 1.0), 0.5, 0.5),
    'alu': ((0.70, 0.71, 0.72, 1.0), 0.85, 0.35),
    'leather': ((0.19, 0.11, 0.06, 1.0), 0.0, 0.7),
    'wood': ((0.30, 0.16, 0.08, 1.0), 0.0, 0.4),
    'brass': ((0.72, 0.52, 0.20, 1.0), 0.9, 0.3),
    'red': ((0.55, 0.06, 0.04, 1.0), 0.1, 0.5),
    'ck_grey': ((0.47, 0.49, 0.50, 1.0), 0.2, 0.55),
    'ck_black': ((0.025, 0.025, 0.028, 1.0), 0.2, 0.55),
    'gauges': ((0.85, 0.85, 0.80, 1.0), 0.0, 0.4),
    'screen': ((0.02, 0.03, 0.03, 1.0), 0.0, 0.3),
    # cockpit v2 (tiling textures nimrod_tile_ck_*; own-UV atlas ck_art = panel faces / placards / seat skin)
    'ck_paint': ((0.46, 0.48, 0.49, 1.0), 0.15, 0.6),
    'ck_crinkle': ((0.035, 0.035, 0.037, 1.0), 0.1, 0.7),
    'ck_brass': ((0.70, 0.52, 0.24, 1.0), 0.9, 0.38),
    'ck_leather': ((0.03, 0.028, 0.026, 1.0), 0.0, 0.55),
    'ck_wood': ((0.32, 0.17, 0.08, 1.0), 0.0, 0.45),
    'ck_floor': ((0.20, 0.07, 0.06, 1.0), 0.0, 0.8),
    'ck_alu': ((0.70, 0.71, 0.72, 1.0), 0.85, 0.45),
    'ck_tube': ((0.10, 0.10, 0.10, 1.0), 0.35, 0.6),
    'ck_canvas': ((0.55, 0.50, 0.38, 1.0), 0.0, 0.9),
    'ck_red': ((0.75, 0.22, 0.08, 1.0), 0.05, 0.5),
    'ck_lining': ((0.16, 0.17, 0.16, 1.0), 0.0, 0.85),
    'ck_rubber': ((0.03, 0.03, 0.03, 1.0), 0.0, 0.75),
    'ck_art': ((0.5, 0.5, 0.5, 1.0), 0.1, 0.6),
    'bomb': ((0.20, 0.22, 0.14, 1.0), 0.3, 0.5),
    # 2026-11-02 rebuild: back of the doped fabric (inner skins) and the fal 3D props (own baked textures, nimrod_pr_<key>_b/_n)
    'fabric_in': ((0.62, 0.58, 0.48, 1.0), 0.0, 0.85),
    'cove': ((0.045, 0.045, 0.048, 1.0), 0.0, 0.9),          # 1.3.1: hinge coves / control-surface fronts, dark matte
    'pr_vickers': ((0.5, 0.5, 0.5, 1.0), 0.6, 0.45), 'pr_exhaust': ((0.5, 0.5, 0.5, 1.0), 0.5, 0.6), 'pr_hook': ((0.5, 0.5, 0.5, 1.0), 0.3, 0.5),
    'pr_wheel': ((0.5, 0.5, 0.5, 1.0), 0.1, 0.7), 'pr_tailwheel': ((0.5, 0.5, 0.5, 1.0), 0.2, 0.6), 'pr_pedals': ((0.5, 0.5, 0.5, 1.0), 0.6, 0.4),
    'pr_cooper': ((0.5, 0.5, 0.5, 1.0), 0.3, 0.5),
    'bombband': ((0.80, 0.62, 0.08, 1.0), 0.1, 0.5),
    'navred': ((0.55, 0.03, 0.02, 1.0), 0.0, 0.08),          # 1.4.0 period wing-tip lamp glass (no light source)
    'navgreen': ((0.03, 0.42, 0.10, 1.0), 0.0, 0.08),
    'tank': ((0.55, 0.55, 0.55, 1.0), 0.3, 0.5),             # 2026-11-22: fuel tank metal (Unity <prefix>_tank, plain lit grey)
}
COCKPIT_ONLY = {'cockpit_interior', 'cockpit_seat', 'cockpit_throttle', 'cockpit_stick', 'cockpit_rudderbar', 'mfd_center', 'windscreen',
                'cockpit_coaming', 'cockpit_frame', 'cockpit_panel', 'cockpit_compass', 'cockpit_breech_L', 'cockpit_breech_R', 'cockpit_quadrant',
                'cockpit_trimwheel', 'cockpit_wall_L', 'cockpit_wall_R', 'cockpit_floor', 'cockpit_sight'}


def uv_group(name):
    if name.startswith('fus_'):
        return 'fuselage'
    if name.startswith(('wing_upper', 'aileron')):
        return 'upper_' + name[-1]
    if name.startswith('wing_lower'):
        return 'lower_' + name[-1]
    if name.startswith(('stab_', 'elevator_', 'fin', 'rudder')):
        return 'tail'
    return name


def cg(parts, fuel_frac=0.5):
    """mass-weighted centre of the parts' mesh bounds centres (Unity: collider bounds centres) + fuel + pilot + guns."""
    byname = {p.name: p for p in parts}
    mesh_of = {'NIMROD1': 'fus_center', 'prop': 'prop_hub'}
    tot = 0.0; acc = V()
    rows = []
    for nm, kg in S.MASSES.items():
        p = byname[mesh_of.get(nm, nm)]
        vs = p.mesh.verts
        lo = V((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        hi = V((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        c = (lo + hi) / 2
        acc += c * kg; tot += kg
        rows.append((nm, kg, tuple(round(x, 3) for x in c)))
    eng = byname['fus_engine'].mesh.verts
    ce = V((0, (max(v.y for v in eng) + min(v.y for v in eng)) / 2, 0))
    acc += ce * (165 * fuel_frac); tot += 165 * fuel_frac
    return acc / tot, tot, rows


def contract(parts, root_c, mass, rows):
    def U(v):   # Blender world -> Unity relative to the root
        d = V(v) - root_c
        return [round(d.x, 4), round(d.z, 4), round(d.y, 4)]
    c = dict(meta=dict(generator='blender/nimrod/build_nimrod.py', aircraft='Hawker Nimrod Mk I', jsonKey='NIMROD1',
                       frame='Unity: x right, y up, z forward; origin = NIMROD1_root = CG at 50 % fuel'),
             cg_blender=[round(x, 4) for x in root_c], parts_mass_kg=round(mass, 1), mass_rows=rows,
             three_point_deg=round(S.THREE_POINT_DEG, 2), level_wheel_contact_height=round(root_c.z - S.GROUND_LEVEL_Z, 4),
             gear=dict(main_axle_L=U((-S.MAIN_AXLE[0], S.MAIN_AXLE[1], S.MAIN_AXLE[2])), main_axle_R=U(S.MAIN_AXLE), wheel_r=S.WHEEL_R,
                       tail_axle=U(S.TAIL_AXLE), tail_r=S.TAILWHEEL_R),
             tailhook=dict(name='tailhook', pivot=U(S.HOOK_PIVOT), length=S.HOOK_LEN, stowed_up_deg=S.HOOK_STOW_UP, deployed_deg=S.HOOK_DEPLOY),
             hook_visual=dict(name='hook_visual', pivot=U(S.HOOKV_PIVOT), pivot_blender=list(S.HOOKV_PIVOT), length=S.HOOKV_LEN, stowed_up_deg=S.HOOKV_STOW,
                              deployed_deg=S.HOOKV_DEPLOY, hook_pivot_blender=list(S.HOOK_PIVOT), note='1.4.0 visible A-frame, driven by B25H.Instruments'),
             tail_skid=dict(contact_radius=S.TAILWHEEL_R, note='1.4.0 skid: gear_tail_wheel is an empty, radius from here'),
             prop=dict(radius=S.PROP_R, plane=U((0, S.PROP_Y, 0)), blades=2),
             guns=dict(muzzles=['muzzle_gun_L', 'muzzle_gun_R'], flashes=['flash_gun_L', 'flash_gun_R'], muzzle_y=U((0, S.MUZZLE_Y, 0))[2]),
             cockpit_only=sorted(COCKPIT_ONLY), eye=U(S.EYE),
             controls=dict(stick=dict(name='cockpit_stick', component='Cockpit.Joystick', range=14.0),
                           rudderbar=dict(name='cockpit_rudderbar', component='ControlSurface', field='yawRange', value=-14.0),
                           throttle=dict(name='cockpit_throttle', component='Cockpit.Throttle', range=40.0)),
             gauges=[], panel=dict(tilt_deg=NC.L.TILT_DEG, tac=NC.TAC, version='cockpit v2'))
    for p in parts:
        if p.name.startswith('gauge_') and p.mesh is not None:
            c['gauges'].append(dict(name=p.name, **{k: v for k, v in p.info.items() if k not in ('axis_local', 'sign', 'rest')}))
    return c


SPLITS = [('fus_engine', 'fus_center', 1, S.ENGINE_AFT_Y), ('fus_center', 'fus_rear', 1, S.CENTRE_AFT_Y),
          ('wing_upper_C', 'wing_upper_L', 0, -S.UP_CENTRE_X), ('wing_upper_C', 'wing_upper_R', 0, S.UP_CENTRE_X)]


def seam_normals(objs):
    """1.4.0 (user review 2: break lines visible on the intact aircraft): on every split plane the two parts' skin corner normals are
    replaced by their common average (custom split normals; exported in the FBX, imported by Unity), so the shading is continuous
    across the joint. Only smooth paint corners exactly on the plane change; everything else keeps its own normal."""
    from mathutils import Vector as Vec
    out = {}
    for a, b, ax, val in SPLITS:
        oa, ob = objs.get(a), objs.get(b)
        if oa is None or ob is None:
            continue
        acc = {}; sel = {}
        for o in (oa, ob):
            me = o.data; mw = o.matrix_world; R = mw.to_3x3().normalized()
            paint = {i for i, ms in enumerate(o.material_slots) if ms.name == 'paint'}
            cn = me.corner_normals
            lst = []
            for p in me.polygons:
                if p.material_index not in paint or not p.use_smooth:
                    continue
                for li in p.loop_indices:
                    w = mw @ me.vertices[me.loops[li].vertex_index].co
                    if abs(w[ax] - val) < 2e-4:
                        k = (round(w.x, 4), round(w.y, 4), round(w.z, 4))
                        acc[k] = acc.get(k, Vec()) + R @ cn[li].vector
                        lst.append((li, k))
            sel[o.name] = lst
        n = 0
        for o in (oa, ob):
            me = o.data; Ri = o.matrix_world.to_3x3().normalized().inverted()
            cur = [tuple(c.vector) for c in me.corner_normals]
            for li, k in sel[o.name]:
                v = acc[k]
                if v.length > 1e-9:
                    cur[li] = tuple((Ri @ v.normalized()).normalized()); n += 1
            me.normals_split_custom_set(cur)
        out[f'{a}|{b}'] = n
    return out


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.abspath(os.path.join(HERE, '..', '..', 'assets', 'model_nimrod', 'nimrod.blend'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    B.MATERIALS = MATERIALS
    mats = B.make_materials()
    parts = NP.build_exterior() + NC.build_cockpit()
    import nimrod_structure as STU
    zf = {}
    for p in parts:
        if p.mesh is not None and p.name in ('cockpit_panel', 'cockpit_floor', 'cockpit_quadrant'):      # the objects with coplanar overlaps (1.2.3 scan)
            k = STU.unfight(p.mesh, push=-0.0008 if p.name == 'cockpit_quadrant' else 0.0008)   # quadrant: the boss sinks into its plate
            if k:
                zf[p.name] = k
    print('[nimrod] z-fight fix (islands moved 0.8 mm):', zf)
    for p in parts:
        if p.name == 'cockpit_interior' and p.mesh is not None:
            import nimrod_structure as ST_
            ST_.clip_faces(p.mesh, (0, -0.068, 0), (0, -1, 0))
            ST_.twin_faces(p.mesh, lambda c: c.z > 0.44)       # lining edge under the coaming: seen from outside through the opening
        if p.name == 'cockpit_seat' and p.mesh is not None:
            import nimrod_structure as ST_
            mb = p.mesh
            def down(c, mb=mb):
                return False
            # seat-pan / bucket faces that face down are seen from above (outside, through the opening) as back faces: reversed twins
            sel = []
            for f in mb.faces:
                P = [mb.verts[i] for i in f['idx']]
                n = (P[1] - P[0]).cross(P[-1] - P[0])
                if n.length > 0 and abs(n.normalized().x) > 0.5 and abs(sum(q.x for q in P) / len(P)) > 0.15:   # bucket side walls
                    sel.append(sum(P, P[0] * 0) / len(P))
            keys = set((round(c.x, 4), round(c.y, 4), round(c.z, 4)) for c in sel)
            ST_.twin_faces(mb, lambda c: (round(c.x, 4), round(c.y, 4), round(c.z, 4)) in keys)
    for p in parts:
        p.uv_group = uv_group(p.name)
    root_c, mass, rows = cg(parts)
    # 2026-11-02 rebuild: the visual rebuild must not move the functional frame. The tear edges move the parts' mesh-bounds centres by
    # < 1 mm; the 1.2.3 CG is kept exactly (S.CG_123) as long as the recomputed one is within 5 mm (else the build stops).
    if (root_c - V(S.CG_123)).length > 0.005:
        raise SystemExit(f'[nimrod] CG moved {(root_c - V(S.CG_123)).length * 1000:.1f} mm from 1.2.3: {tuple(root_c)}')
    print(f'[nimrod] CG recomputed {tuple(round(c, 4) for c in root_c)}, kept 1.2.3 CG {S.CG_123} (delta {(root_c - V(S.CG_123)).length * 1000:.2f} mm)')
    root_c = V(S.CG_123)
    root = Part('NIMROD1_root', None, tuple(root_c), None, info=dict(note=f'CG (50 % fuel) parts {mass:.0f} kg'))
    parts.insert(0, root)
    parts += NP.cooper_parts()
    usage, m_per_uv = B.pack_livery(parts)
    coll = bpy.data.collections.new('NIMROD1')
    sc.collection.children.link(coll)
    objs = B.create_objects(parts, mats, coll)
    # weld coincident vertices (per object; loop UVs are kept), then re-mark sharp edges
    import bmesh
    welded = 0
    for ob in objs.values():
        if ob.type != 'MESH':
            continue
        bm = bmesh.new(); bm.from_mesh(ob.data)
        n0 = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        welded += n0 - len(bm.verts)
        bm.to_mesh(ob.data); bm.free()
        try:
            ob.data.set_sharp_from_angle(angle=math.radians(38))
        except Exception:
            pass
    seam = seam_normals(objs)
    print('[nimrod] seam normals (1.4.0, continuous across the splits):', seam)
    import internals_r183 as IN
    tk = IN.tuck(objs)                  # 1.8.3: cockpit walls / frame / sight / lining poked through the side skin (the dark specks)
    for _ in range(3):                  # a moved vertex can meet a new nearest skin face: repeat until nothing pokes
        if not IN.poke_count(objs):
            break
        for k_, v_ in IN.tuck(objs).items():
            tk[k_] = tk.get(k_, 0) + v_
    print('[nimrod] 1.8.3 inner parts tucked under the skin (vertices moved):', tk)
    tris = sum(p.mesh.tri_count() for p in parts if p.mesh is not None)
    verts = sum(len(p.mesh.verts) for p in parts if p.mesh is not None)
    vfinal = sum(len(o.data.vertices) for o in objs.values() if o.type == 'MESH')
    ck = [o for o in objs.values() if o.type == 'MESH' and o.name.startswith(('cockpit_', 'gauge_', 'mfd_'))]
    ck_tris = sum(len(p.vertices) - 2 for o in ck for p in o.data.polygons)
    ck_verts = sum(len(o.data.vertices) for o in ck)
    stats = dict(cockpit_objects=len(ck), cockpit_tris=ck_tris, cockpit_verts_welded=ck_verts, objects=len(objs), tris=tris, verts_raw=verts, verts_welded=vfinal, welded=welded, livery_usage=round(usage, 4), metres_per_uv=round(m_per_uv, 3),
                 cg_blender=[round(x, 3) for x in root_c], parts_mass=round(mass, 1), three_point_deg=round(S.THREE_POINT_DEG, 2))
    sc['b25_build_stats'] = json.dumps(stats)
    print('[nimrod] ' + json.dumps(stats))
    with open(os.path.join(os.path.dirname(out), 'nimrod_contract.json'), 'w') as f:
        json.dump(contract(parts, root_c, mass, rows), f, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('[nimrod] saved', out)


if __name__ == '__main__':
    main()
