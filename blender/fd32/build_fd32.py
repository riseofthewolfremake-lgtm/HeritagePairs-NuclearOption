"""Build the FD-32 Nimrod model and save it as a .blend + contract json (derived from blender/nimrod/build_nimrod.py; that file is
untouched and still builds the Mk I).

  blender --background --factory-startup --python-exit-code 1 --python blender/fd32/build_fd32.py -- --out assets/model_fd32/fd32.blend

Blender space: nose +Y, up +Z, right wing +X, metres, flight attitude (fixed gear). Root empty FD32_root = CG (50 % fuel) = the FBX /
Unity origin. Exterior = blender/fd32/fd32_parts.py (the Mk I generator with the FD-32 changes), cockpit = fd32_cockpit.py.
"""
import bpy, sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
NIM = os.path.abspath(os.path.join(HERE, '..', 'nimrod'))
V2 = os.path.abspath(os.path.join(HERE, '..', 'v2'))
for p in (HERE, NIM, V2):
    if p not in sys.path:
        sys.path.insert(0, p)
from mathutils import Vector as V
import build_b25h_v2 as B
from b25h_parts import Part
import build_nimrod as BN          # first: it re-imports the Nimrod modules; fd32_parts then patches those instances
import fd32_spec as FS
import fd32_parts as FP
import fd32_cockpit as FC
import nimrod_spec as S
import nimrod_structure as STU
import fd32_canopy183 as CAN
import internals_r183 as IN

MATERIALS = dict(BN.MATERIALS)
MATERIALS.update({
    'paint': ((0.42, 0.44, 0.46, 1.0), 0.15, 0.6),           # composite / RAM skin (livery atlas)
    'ck_modern': ((0.20, 0.21, 0.22, 1.0), 0.1, 0.75),       # anti-glare cockpit paint (fal ck_modern)
    'ck_mat': ((0.05, 0.05, 0.05, 1.0), 0.0, 0.9),           # floor mat (fal ck_mat)
    'pr_prop4': ((0.5, 0.5, 0.5, 1.0), 0.2, 0.5),            # fal 4-blade prop (own baked texture)
    'pr_sensor': ((0.5, 0.5, 0.5, 1.0), 0.3, 0.45),          # fal sensor ball (own baked texture)
    'exhaust': ((0.10, 0.09, 0.085, 1.0), 0.5, 0.6),
    'pr_hook2': ((0.5, 0.5, 0.5, 1.0), 0.3, 0.5),            # round 3: fal modern hook
    'pr_throttle': ((0.5, 0.5, 0.5, 1.0), 0.2, 0.5),         # round 3: fal throttle lever
    'light_off': ((0.10, 0.22, 0.12, 1.0), 0.0, 0.3),        # gear-down strips unlit (Unity: stock light_green_off / slimelight_on)
    'tacscreen': ((0.02, 0.05, 0.04, 1.0), 0.0, 0.2),        # Unity: stock tacScreenDisplay
})
COCKPIT_ONLY = {'cockpit_interior', 'cockpit_panel', 'cockpit_floor', 'cockpit_stickboot', 'cockpit_quadrant', 'cockpit_console_L',
                'cockpit_console_R', 'cockpit_throttle', 'cockpit_console_fwd', 'mfd_map', 'mfd_power', 'mfd_flight', 'mfd_engine'}


def uv_group(name):
    if name.startswith('flaperon'):
        return 'lower_' + name.split('_')[1]
    if name.startswith('pylon_'):
        return 'pylons'
    if name.startswith(('canopy_slide', 'windscreen')):
        return 'canopy'
    if name.startswith('slimelight'):
        return 'lights'
    return BN.uv_group(name)


def cg(parts, fuel_frac=0.5):
    byname = {p.name: p for p in parts}
    mesh_of = {'FD32': 'fus_center', 'prop': 'prop_hub'}
    tot = 0.0; acc = V()
    rows = []
    for nm, kg in FS.MASSES.items():
        p = byname[mesh_of.get(nm, nm)]
        vs = p.mesh.verts
        lo = V((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        hi = V((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        c = (lo + hi) / 2
        acc += c * kg; tot += kg
        rows.append((nm, kg, tuple(round(x, 3) for x in c)))
    eng = byname['fus_engine'].mesh.verts
    ce = V((0, (max(v.y for v in eng) + min(v.y for v in eng)) / 2, 0))
    acc += ce * (FS.FUEL_KG * fuel_frac); tot += FS.FUEL_KG * fuel_frac
    return acc / tot, tot, rows


def contract(parts, root_c, mass, rows, objs):
    def U(v):
        d = V(v) - root_c
        return [round(d.x, 4), round(d.z, 4), round(d.y, 4)]

    def UD(v):                                   # a direction (no origin shift)
        return [v.x, v.z, v.y]
    by = {p.name: p for p in parts}
    yf, yr = FS.HOOD_Y
    c = dict(meta=dict(generator='blender/fd32/build_fd32.py', aircraft='FD-32 Nimrod', jsonKey='FD32',
                       frame='Unity: x right, y up, z forward; origin = FD32_root = CG at 50 % fuel'),
             cg_blender=[round(x, 4) for x in root_c], parts_mass_kg=round(mass, 1), mass_rows=rows,
             three_point_deg=round(S.THREE_POINT_DEG, 2), level_wheel_contact_height=round(root_c.z - S.GROUND_LEVEL_Z, 4),
             gear=dict(main_axle_L=U((-S.MAIN_AXLE[0], S.MAIN_AXLE[1], S.MAIN_AXLE[2])), main_axle_R=U(S.MAIN_AXLE), wheel_r=S.WHEEL_R,
                       tail_axle=U(S.TAIL_AXLE), tail_r=S.TAILWHEEL_R),
             tailhook=dict(name='tailhook', pivot=U(S.HOOK_PIVOT), length=S.HOOK_LEN, stowed_up_deg=S.HOOK_STOW_UP, deployed_deg=S.HOOK_DEPLOY),
             retract=dict(main_fold_deg=round(FP.G6.fold_axis_angle(1)[1], 3), main_fold_yaw_deg=FS.GEAR_FOLD_YAW, main_fold_aft=FS.GEAR_FOLD_AFT, main_fold='round 7: aft about a TILTED axis (Unity main_axis_L/R): the leg ends flat along the wing-root underside, the wheel flat under it (semi-retractable)', main_axis_L=[round(c, 5) for c in UD(FP.G6.fold_axis_angle(-1)[0])], main_axis_R=[round(c, 5) for c in UD(FP.G6.fold_axis_angle(1)[0])], main_stowed_wheel_L=U(FP.G6.fold_matrix(-1) @ V((-S.MAIN_AXLE[0], S.MAIN_AXLE[1], S.MAIN_AXLE[2]))), main_stowed_wheel_R=U(FP.G6.fold_matrix(1) @ V(S.MAIN_AXLE)), tail_fold_deg=FS.TAIL_FOLD_DEG, tail_fixed=True,
                          tail_fold='fixed (no retraction)', main_root_L=U(by['gear_main_L_strut'].pivot), main_root_R=U(by['gear_main_R_strut'].pivot),
                          tail_root=U(by['gear_tail_strut'].pivot)),
             stretch=dict(y_cut_blender=FS.STRETCH_Y, length=FS.STRETCH_L, note='round 3: fuselage lengthened aft of the cockpit'),
             lights=dict(gear=[p.name for p in parts if p.name.startswith('slimelight_')]),
             prop=dict(radius=FS.PROP_R, plane=U((0, S.PROP_Y, 0)), blades=FS.BLADES),
             guns=dict(muzzles=['muzzle_gun_L', 'muzzle_gun_R'], flashes=['flash_gun_L', 'flash_gun_R'], muzzle_y=U((0, S.MUZZLE_Y, 0))[2]),
             cockpit_only=sorted(COCKPIT_ONLY), eye=U(S.EYE),
             controls=dict(stick=dict(name='cockpit_stick', stock_mesh='sfb_joystick', stock_materials=['hotas', 'SFB_cockpit'], range=12.0),
                           throttle=dict(name='cockpit_throttle', stock_mesh='COIN_throttle', stock_materials=['hotas'], motion=True, range=0.22, note='round 10: the CI-22 single throttle, mounted as COIN.prefab: identity frame, Cockpit.Throttle motion +Z, range 0.22 m')),
             mfds=[dict(name='mfd_' + k, role='tac', main=(k == 'map'), width=v[2], uv=list(v[3]), rotated=v[4]) for k, v in FC.SCREENS.items()],
             canopy=dict(hood='canopy_slide', glass='canopy_slide_glass', hinge='canopy_slide_hinge', open_deg=FS.HOOD_OPEN_DEG,
                         hinge_pivot=U(by['canopy_slide_hinge'].pivot), hood_y=[U((0, yf, 0))[2], U((0, yr, 0))[2]], windscreen='windscreen',
                         note='closed canopy, jettisoned whole; tilts up on the ground about its rear end (Canopy hinge, local +X = Blender +X)'),
             droop=dict(deg=FS.DROOP_DEG, deg_upper=FS.DROOP_DEG_UPPER, pivot_below=FS.DROOP_PIVOT_BELOW, surfaces=['aileron_L', 'aileron_R', 'flaperon_L', 'flaperon_R'],
                        note='round 3: stock flap pattern (ControlSurface flap mode, follows the gear) on a pivot DROOP_PIVOT_BELOW under each hinge line'),
             sensor=dict(mount='sensor_mount', ball='sensor_ball', stowed=U((0, FS.BALL_Y, FS.BALL_Z_STOWED)), deployed=U((0, FS.BALL_Y, FS.BALL_Z_DEPLOYED)),
                         radius=FS.BALL_R),
             hardpoints={f'hp_{k}_{s}': U(by[f'hp_{k}_{s}'].pivot) for k in ('inner', 'outer') for s in 'LR'},
             pylon_x=FS.PYLONS, flaperon_x=list(FS.FLAP_LO_X),
             flares=[U(by['flare_L'].pivot), U(by['flare_R'].pivot)],
             stock_seat_note='stock EjectionSeat on the COIN pilot figure (GA-25X 0.3.1 pattern)')
    return c


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.abspath(os.path.join(HERE, '..', '..', 'assets', 'model_fd32', 'fd32.blend'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    B.MATERIALS = MATERIALS
    mats = B.make_materials()
    parts = FP.build_exterior() + FC.build_cockpit()
    if CAN.ENABLED:
        print('[fd32] 1.8.3 skin rings captured (pre-stretch):', CAN.capture())
    nmv = FP.stretch(parts, FS.STRETCH_Y, FS.STRETCH_L)                 # round 3: longer fuselage
    FS.apply_stretch()
    print(f'[fd32] stretch: {nmv} vertices moved {FS.STRETCH_L} m aft of y {FS.STRETCH_Y}; 3-point {S.THREE_POINT_DEG:.2f} deg')
    parts += FP.finish_exterior(parts)
    zf = {}
    for p in parts:
        if p.mesh is not None and p.name in ('cockpit_panel', 'cockpit_floor', 'cockpit_console_L', 'cockpit_console_R'):
            k = STU.unfight(p.mesh, push=0.0008)
            if k:
                zf[p.name] = k
    print('[fd32] z-fight fix (islands moved 0.8 mm):', zf)
    for p in parts:
        if p.name == 'cockpit_interior' and p.mesh is not None:
            STU.clip_faces(p.mesh, (0, -0.068, 0), (0, -1, 0))   # (lining forward edge; the stretch only moved geometry aft of -1.02)
            STU.twin_faces(p.mesh, lambda c: c.z > 0.44)
    for p in parts:
        p.uv_group = uv_group(p.name)
    root_c, mass, rows = cg(parts)
    print(f'[fd32] CG {tuple(round(c, 4) for c in root_c)} parts {mass:.0f} kg (Mk I 1.2.3 CG {S.CG_123})')
    # 1.8.3: the visual rebuild must not move the functional frame (the 1.8.2 ground values are being verified in game): the 1.8.2 CG is
    # kept exactly as long as the recomputed one is within 5 mm (else the build stops), as the Mk I keeps its 1.2.3 CG
    if (root_c - V(FS.CG_182)).length > 0.005:
        raise SystemExit(f'[fd32] CG moved {(root_c - V(FS.CG_182)).length * 1000:.1f} mm from 1.8.2: {tuple(root_c)}')
    print(f'[fd32] 1.8.3 CG recomputed {tuple(round(c, 4) for c in root_c)}, kept 1.8.2 CG {FS.CG_182} (delta {(root_c - V(FS.CG_182)).length * 1000:.2f} mm)')
    if (root_c - V(FS.CG_182)).length > 0.0001:     # identical bounds give the identical (unrounded) CG; else pin the 1.8.2 value
        root_c = V(FS.CG_182)
    root = Part('FD32_root', None, tuple(root_c), None, info=dict(note=f'CG (50 % fuel) parts {mass:.0f} kg'))
    parts.insert(0, root)
    usage, m_per_uv = B.pack_livery(parts)
    coll = bpy.data.collections.new('FD32')
    sc.collection.children.link(coll)
    objs = B.create_objects(parts, mats, coll)
    # round 11 (user: the stowed sensor ball clipped the belly): the Mk I's belly skin and inner skin ran straight through the bay (only a
    # collar and a well were added in round 2). Open them: the skin faces near the bay are subdivided to ~1 cm, then every face with a vertex
    # inside the liner radius goes; the remaining edge lies within ~1.5 cm outside the liner, under the collar ring (no see-through).
    import bmesh as _bm, nimrod_structure as _NS
    zsk = _NS.fus_z(0.0, FS.BALL_Y, top=False)
    def _r(co):
        return math.hypot(co.x, co.y - FS.BALL_Y)
    for nm in ('fus_engine', 'fus_engine_struct'):
        ob = objs.get(nm)
        if ob is None:
            continue
        bm = _bm.new(); bm.from_mesh(ob.data)
        mw = ob.matrix_world; mwi = mw.inverted()
        def near(f, rr):
            return any(_r(mw @ v.co) < rr and (mw @ v.co).z < zsk + 0.08 for v in f.verts) and abs(f.normal.z) > 0.5
        n0 = len(bm.faces)
        for _ in range(4):                                             # refine the faces that reach into r < 0.30 until edges are <= 1.2 cm
            keep_m0 = {i for i, m in enumerate(ob.data.materials) if m is not None and m.name in ('metal_dark', 'cove')}
            edges = {e for f in bm.faces if f.material_index not in keep_m0 and near(f, 0.30) for e in f.edges if e.calc_length() > 0.012}
            if not edges:
                break
            _bm.ops.subdivide_edges(bm, edges=list(edges), cuts=1, use_grid_fill=True)
        keep_m = {i for i, m in enumerate(ob.data.materials) if m is not None and m.name in ('metal_dark', 'cove')}      # the bay collar / liner stay
        kill = [f for f in bm.faces if f.material_index not in keep_m and abs(f.normal.z) > 0.3 and all((mw @ v.co).z < zsk + 0.03 for v in f.verts) and any(_r(mw @ v.co) < FS.BAY_R + 0.001 for v in f.verts)]
        _bm.ops.delete(bm, geom=kill, context='FACES')
        bm.to_mesh(ob.data); bm.free()
        print(f'[fd32] bay opened in {nm}: {n0} -> {len(ob.data.polygons)} faces ({len(kill)} removed inside r {FS.BAY_R:.3f})')
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
            if ob.name == 'sensor_ball':          # round generated shell: fully smooth (no angle-based sharp edges)
                for e in ob.data.edges:
                    e.use_edge_sharp = False
                ob.data.shade_smooth()
            else:
                ob.data.set_sharp_from_angle(angle=math.radians(38))
        except Exception:
            pass
    BN.SPLITS[:] = [(a_, b_, ax_, (S.CENTRE_AFT_Y if (a_, b_) == ('fus_center', 'fus_rear') else v_)) for a_, b_, ax_, v_ in BN.SPLITS]   # stretched split plane
    # round 3: close the open boundaries of the split / imported meshes (prop blades cut from the hub, fal wheel / lever / hook crumbs)
    # and make their winding consistent outward: rays from outside must meet front faces
    filled = {}
    for ob in objs.values():
        if ob.type != 'MESH' or not (ob.name.startswith(('prop_', 'gear_tail_', 'cockpit_throttle', 'tailhook')) or ob.name in ('sensor_ball',)):
            continue
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bnd = [e for e in bm.edges if len(e.link_faces) == 1]
        if bnd:
            r = bmesh.ops.holes_fill(bm, edges=bnd, sides=0)
            filled[ob.name] = len(r.get('faces', []))
        if not any(len(e.link_faces) == 1 for e in bm.edges):
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(ob.data); bm.free()
    print('[fd32] holes filled (faces):', filled)
    seam = BN.seam_normals(objs)
    print('[fd32] seam normals:', seam)
    tk = IN.tuck(objs)                  # 1.8.3: cockpit parts poking through the (rebuilt) skin
    for _ in range(3):
        if not IN.poke_count(objs):
            break
        for k_, v_ in IN.tuck(objs).items():
            tk[k_] = tk.get(k_, 0) + v_
    print('[fd32] 1.8.3 inner parts tucked under the skin (vertices moved):', tk)
    tris = sum(p.mesh.tri_count() for p in parts if p.mesh is not None)
    vfinal = sum(len(o.data.vertices) for o in objs.values() if o.type == 'MESH')
    ck = [o for o in objs.values() if o.type == 'MESH' and o.name.startswith(('cockpit_', 'mfd_'))]
    ck_tris = sum(len(p.vertices) - 2 for o in ck for p in o.data.polygons)
    stats = dict(cockpit_objects=len(ck), cockpit_tris=ck_tris, objects=len(objs), tris=tris, verts_welded=vfinal, welded=welded,
                 livery_usage=round(usage, 4), metres_per_uv=round(m_per_uv, 3), cg_blender=[round(x, 3) for x in root_c], parts_mass=round(mass, 1),
                 three_point_deg=round(S.THREE_POINT_DEG, 2))
    sc['b25_build_stats'] = json.dumps(stats)
    print('[fd32] ' + json.dumps(stats))
    con = contract(parts, root_c, mass, rows, objs)
    if CAN.ENABLED:
        con['canopy183'] = FP.finish_exterior.info
        con['collider_fus_center'] = CAN.hull_of(FP.finish_exterior.hull_mb, root_c)     # FD32Build bakes the root collider from it
        print('[fd32] 1.8.3 canopy', json.dumps(FP.finish_exterior.info), 'root collider hull', len(con['collider_fus_center']['verts']), 'verts')
    with open(os.path.join(os.path.dirname(out), 'fd32_contract.json'), 'w') as f:
        json.dump(con, f, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('[fd32] saved', out)


if __name__ == '__main__':
    main()
