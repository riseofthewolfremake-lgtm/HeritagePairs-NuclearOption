"""Build the B-17G airframe (Phase B milestone 1): procedural structure + fal props, saved as a .blend + contract json.

  blender --background --factory-startup --python-exit-code 1 --python blender/b17g/build_b17g.py -- --out assets/model_b17g/b17g.blend

Blender space: nose +Y, up +Z, right wing +X, metres, real size, gear DOWN, bay doors closed. Paint faces share one packed livery atlas
`livery`; every face also has a tiling UV `detail`. Reuses the B-25H v2 pipeline functions (pack_livery, create_objects) and the
Nimrod structure helpers read-only; nothing of the other aircraft is modified.
"""
import bpy, sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.abspath(os.path.join(HERE, '..', 'v2'))
NIM = os.path.abspath(os.path.join(HERE, '..', 'nimrod'))
for p in (HERE, NIM, V2):
    if p not in sys.path:
        sys.path.insert(0, p)
for m in ('b17g_spec', 'b17g_parts', 'b17g_props', 'b17g_cockpit', 'b17g_detail', 'b17g_nacelle'):
    sys.modules.pop(m, None)
from mathutils import Vector as V, Matrix
import build_b25h_v2 as B
from b25h_parts import Part
import b17g_spec as S
import b17g_parts as P
import b17g_props as PR
import b17g_cockpit as CK
import b17g_detail as D

MATERIALS = {   # name: (base colour RGBA, metallic, roughness) - Unity builds its own materials per name
    'paint': ((0.29, 0.30, 0.20, 1.0), 0.1, 0.6),           # olive drab (the livery atlas replaces it)
    'interior': ((0.30, 0.34, 0.22, 1.0), 0.1, 0.75),       # bronze green / zinc chromate inside
    'structure': ((0.55, 0.57, 0.45, 1.0), 0.5, 0.5),        # primed aluminium frames
    'glass': ((0.70, 0.80, 0.85, 0.20), 0.0, 0.05),
    'cove': ((0.05, 0.05, 0.05, 1.0), 0.0, 0.9),
    'well': ((0.22, 0.24, 0.16, 1.0), 0.2, 0.7),
    'gear': ((0.35, 0.36, 0.30, 1.0), 0.6, 0.45),
    'chrome': ((0.85, 0.86, 0.88, 1.0), 1.0, 0.15),
    'cowl': ((0.10, 0.10, 0.10, 1.0), 0.4, 0.5),
    'metal_dark': ((0.06, 0.06, 0.065, 1.0), 0.7, 0.4),
    'exhaust': ((0.13, 0.075, 0.05, 1.0), 0.4, 0.6),         # 1.8.3: heat-rusted turbo / exhaust (reference: brown)
    'turbo': ((0.26, 0.13, 0.06, 1.0), 0.15, 0.7),           # 1.8.5 E: turbo housing + volute, lighter rust (faces down into shade)
    'cowl_ring': ((0.24, 0.25, 0.15, 1.0), 0.1, 0.6),        # 1.8.3: olive-drab anti-glare cowl lip ring (reference)
    'prop': ((0.03, 0.03, 0.03, 1.0), 0.2, 0.5), 'engine': ((0.3, 0.3, 0.3, 1.0), 0.8, 0.4),
    'tyre': ((0.03, 0.03, 0.03, 1.0), 0.0, 0.9), 'turret': ((0.29, 0.30, 0.20, 1.0), 0.2, 0.6),
    'pr_hsprop': ((0.04, 0.04, 0.04, 1.0), 0.3, 0.5),        # round 5: procedural Hamilton Standard prop (own 4-cell texture b17g_pr_hsprop_b.png)
    # M2 cockpit (tiles from fal: assets/textures_b17g/b17g_tile_ck_*; gauges = the fal dial atlas b17g_gauges.png on the livery UV)
    'ck_panel': ((0.035, 0.035, 0.038, 1.0), 0.1, 0.6), 'ck_wall': ((0.27, 0.33, 0.24, 1.0), 0.1, 0.6), 'ck_od': ((0.25, 0.27, 0.17, 1.0), 0.1, 0.6),
    'ck_floor': ((0.20, 0.22, 0.17, 1.0), 0.1, 0.8), 'ck_black': ((0.02, 0.02, 0.022, 1.0), 0.1, 0.6), 'ck_bezel': ((0.10, 0.10, 0.10, 1.0), 0.6, 0.4),
    'gauges': ((0.85, 0.85, 0.80, 1.0), 0.0, 0.4), 'needle': ((0.92, 0.92, 0.88, 1.0), 0.0, 0.5),
}
MASS = {   # kg (part masses for the CG estimate and later Unity; empty ~16.4 t + crew / fuel 50 % / ammo; CG near 25-30 % MAC)
    'fus_nose': 1300, 'fus_cockpit': 1900, 'B17G': 3200, 'fus_radio': 450, 'fus_waist': 650, 'fus_tail': 300, 'tail_gun': 220,
    'wing_inner': 1500, 'wing_mid': 900, 'wing_outer': 420, 'wing_tip': 50, 'nacelle': 250, 'engine': 1350, 'prop': 330,
    'stab': 100, 'elevator': 35, 'fin': 150, 'rudder': 45, 'flap_inner': 60, 'flap_outer': 70, 'aileron': 65, 'gear_main': 480, 'gear_tail': 80,
}


def mass_of(name):
    if name.startswith('prop_hub_'):       # round 5: procedural hub / blades are Parts now; the prop mass sits on prop_n
        return 0
    for k in sorted(MASS, key=len, reverse=True):
        if name == k or name.startswith(k + '_') or name.startswith(k):
            return MASS[k]
    return 0


def mac():
    xs = [S.WING_ROOT_X + (S.WING_TIP_X - S.WING_ROOT_X) * k / 400 for k in range(401)]
    num = den = 0.0
    for x in xs:
        le, te = S.wing_chord(x); c = le - te; num += c * c; den += c
    m = num / den
    for x in xs:
        le, te = S.wing_chord(x)
        if le - te <= m:
            return m, le, x
    return m, S.wing_chord(5)[0], 5


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    out = os.path.abspath(argv[argv.index('--out') + 1])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = {}
    for name, (col, met, rough) in MATERIALS.items():
        m = bpy.data.materials.new(name); m.diffuse_color = col; m.use_nodes = True
        bs = m.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value = col; bs.inputs['Metallic'].default_value = met; bs.inputs['Roughness'].default_value = rough
        if col[3] < 1:
            bs.inputs['Alpha'].default_value = col[3]
            try:
                m.surface_render_method = 'BLENDED'
            except Exception:
                m.blend_method = 'BLEND'
        mats[name] = m
    parts = []
    fus, doors = P.build_fuselage(); parts += fus
    parts += P.build_bay(doors)
    for side in (-1, 1):
        parts += P.build_wing(side)
        for kind in ('inner', 'outer'):
            parts += P.build_nacelle(kind, side)
        parts += P.main_gear(side)
    parts += P.build_tail()
    parts += P.tail_gear()
    for t in S.TURRETS:
        fr = P.turret_frames(t)
        fr[0].parent = P.TURRET_PARENT[t]
        parts += fr
    parts += P.build_turret_rings()
    # round 5 (user review 2): procedural props and turret bodies replace the fal meshes
    parts += D.build_props()
    parts += D.chin_turret() + D.ball_turret() + D.top_turret() + D.tail_turret()
    parts += CK.build_structure() + CK.build_gauges() + CK.anchors()
    # CG (50 % fuel, crew, ammo inside the part masses) and MAC
    tot = 0.0; mom = V()
    for p in parts:
        mm = mass_of(p.name)
        if mm and p.mesh is not None and p.mesh.verts:
            c = sum(p.mesh.verts, V()) / len(p.mesh.verts)
            if p.name.startswith('gear_main'):
                c = p.pivot + V((0, 0, -0.7))
            tot += mm; mom += c * mm
        elif mm and p.mesh is None:
            tot += mm; mom += p.pivot * mm
    cg = mom / tot
    m_, le_mac, x_mac = mac()
    pct = (le_mac - cg.y) / m_ * 100
    # round 5: internals are added AFTER the CG estimate (it uses part mesh centroids; the flight model was tuned on this CG)
    istats = D.add_internals(parts)      # round 5: spars, ribs, fuel cells, frames, stringers, bay structure, engines, turbos, oil tanks
    print('[b17g] internals tris per part:', {k: v for k, v in sorted(istats.items())}, 'total', sum(istats.values()))
    if S.ANM2_SLOTS:       # 1.8.13 r3: the radio gun's path - no structure in the hatch column (a 0.55 m bar crossed it 0.10 m behind the pivot)
        for p in parts:
            if p.name == 'fus_radio' and p.mesh is not None:
                def _in(f):
                    q = sum((p.mesh.verts[k] for k in f['idx']), V()) / len(f['idx'])
                    return f['mat'] == 'structure' and abs(q.x) < 0.40 and S.RADIO_HATCH[0] < q.y < S.RADIO_HATCH[1] and q.z > 1.60
                n0 = len(p.mesh.faces); p.mesh.faces = [f for f in p.mesh.faces if not _in(f)]
                print('[b17g] radio hatch column cleared:', n0 - len(p.mesh.faces), 'structure faces')
    # round 5: the root (= FBX / Unity prefab origin) stays where 1.7.4 had it; the flight model, the gear stance and every Unity-side
    # absolute point were tuned against that origin. The estimate above is printed for information only.
    cg_est = cg
    cg = V((0.00013848971866536885, 0.7153460383415222, 0.39707520604133606))
    pct = (le_mac - cg.y) / m_ * 100
    print(f'[b17g] CG estimate {tuple(round(v, 3) for v in cg_est)}; root pinned at the 1.7.4 CG {tuple(round(v, 3) for v in cg)}')
    root = Part('B17G_root', None, pivot=cg, info={'kind': 'root_at_cg'})
    parts.insert(0, root)
    for p in parts:
        if p.parent is None and p.name != 'B17G_root':
            p.parent = 'B17G_root'
    # round 5: drop zero-area faces everywhere (Unity drops them on import: the 'meshes arrive whole' triangle-count row, stray check)
    dropped = 0
    for p in parts:
        if p.mesh is None:
            continue
        keep = []
        for f in p.mesh.faces:
            P_ = [p.mesh.verts[k] for k in f['idx']]
            a2 = sum(((P_[k] - P_[0]).cross(P_[k + 1] - P_[0])).length for k in range(1, len(P_) - 1)) / 2
            if a2 > 1e-8:
                keep.append(f)
        dropped += len(p.mesh.faces) - len(keep); p.mesh.faces = keep
    print(f'[b17g] zero-area faces dropped: {dropped}')
    area, mpu = B.pack_livery(parts)
    coll = bpy.data.collections.new('B17G'); bpy.context.scene.collection.children.link(coll)
    objs = B.create_objects(parts, mats, coll)
    for p in parts:
        if p.info and 'cowl_r' in p.info:
            objs[p.name]['cowl_r'] = p.info['cowl_r']
    # fal props
    D.write_prop_texture(os.path.join(os.path.dirname(out), '..', 'textures_b17g', D.PROP_TEX))
    PR.place_engines(objs, coll, S)
    PR.place_wheels(objs, coll, S)
    PR.place_cockpit(objs, coll, S)
    for o in coll.objects:
        if o.type == 'MESH' and 'b17g_prop_mat' in o.keys():
            mn = o['b17g_prop_mat']
            if mn not in mats:
                m = bpy.data.materials.new(mn); m.use_nodes = True; mats[mn] = m
            o.data.materials.clear(); o.data.materials.append(mats[mn])
    # 1.7.11: no z-fighting anywhere (check m): move one face of every same-facing coplanar overlapping pair off the shared plane
    import b17g_zfix as ZF
    ZF.resolve([o for o in coll.objects if o.type == 'MESH' and not o.name.endswith('_hullsrc')], log_path=os.path.join(os.path.dirname(out), 'b17g_zfix.json'))
    # 1.7.12: the top / chin turret openings shade like the uncut skin (analytic fuselage normals as custom split normals)
    import b17g_normals as NRM
    NRM.apply({o.name: o for o in coll.objects})
    # contract
    tris = sum(len(pp.vertices) - 2 for o in coll.objects if o.type == 'MESH' for pp in o.data.polygons)
    contract = dict(
        aircraft='B17G', frame='blender: x right, y forward, z up; metres; gear down',
        cg=list(cg), mac=dict(length=m_, le_y=le_mac, x=x_mac), cg_pct_mac=pct, mass_kg=tot,
        prop=dict(radius=S.PROP_R, blades=S.PROP_BLADES, engines={str(v): k for k, v in S.ENGINE_NUM.items()}),
        gear=dict(main_pivot=S.MAIN_PIVOT, main_leg=S.MAIN_LEG, main_fold_deg=S.MAIN_FOLD, main_fold_sense='forward-up', wheel_r=S.WHEEL_R,
                  tail_pivot=S.TAIL_PIVOT, tail_axle_down=S.TAIL_AXLE_DOWN, tail_fold_deg=S.TAIL_FOLD, tail_fold_sense='aft-up'),
        bay=dict(y=S.BAY_Y, hardpoint=S.HP_BOMBBAY, stores=S.STORES, door_open_deg=92),
        turrets=[dict(mount=dict(name=f'{t}_mount'), az=dict(name=f'{t}_az'), el=dict(name=f'{t}_el'), station=S.TURRETS[t]['station'],
                      guns=[dict(gun=dict(name=f'{t}_gun{k}'), muzzle=dict(name=f'{t}_muzzle{k}')) for k in range(len(S.TURRETS[t]['guns']))],
                      Turret=dict(traverseRange=S.TURRETS[t]['trav'], traverseRate=45, minElevation=S.TURRETS[t]['emin'], maxElevation=S.TURRETS[t]['emax'], elevationRate=40))
                 for t in S.TURRETS],
        tris=tris, metres_per_uv=mpu, props_log=PR.LOG,
        eyes=CK.eye_contract(),
        controls=dict(objects=[dict(name=p.name, drive=p.info['drive']) for p in parts if p.info.get('kind') == 'ck_control']),
        levers=dict(movers=[dict(name=p.name, stock_driver=p.info['drive'], rest_deg=p.info['rest_deg']) for p in parts if p.info.get('kind') == 'lever']),
        gauges=dict(movers=[dict(name=p.name) for p in parts if p.info.get('kind') == 'gauge_mover']),
        crew=dict(stations=[dict(role=p.info['role'], part=p.info['part'], eye=dict(name=p.name)) for p in sorted(parts, key=lambda q: q.info.get('index', 99)) if p.info.get('kind') == 'crew_eye']),
    )
    bpy.context.scene['b25_build_stats'] = json.dumps(dict(metres_per_uv=mpu, tris=tris))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(contract, open(os.path.join(os.path.dirname(out), 'b17g_contract.json'), 'w'), indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print(f'[b17g] saved {out}: {len(coll.objects)} objects, {tris} tris, CG {tuple(round(v, 3) for v in cg)} = {pct:.1f} % MAC '
          f'(MAC {m_:.2f} m, LE {le_mac:.2f}), mass {tot:.0f} kg, {mpu:.2f} m per UV')


main()
