"""Build the GA-25X model (procedural) and save it as a .blend. Reuses the B-25H v2/v3 builders by import with the
GA-25X spec applied in memory (ga25x_spec.apply); new parts come from ga25x_parts.

  blender --background --factory-startup --python blender/ga25x/build_ga25x.py -- --out assets/model_ga25x/ga25x.blend

Blender space: nose +Y, up +Z, right wing +X, metres. Gear extended, gear doors open, bomb doors closed. All exterior
paint faces share one packed UV atlas `livery` (own atlas: the GA-25X textures are baked for this model only).
"""
import bpy, sys, os, json, math, importlib

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.join(HERE, '..', 'v2')
sys.path.insert(0, HERE)
sys.path.insert(1, V2)
# 1. the B-25H build module (it re-imports a fresh b25h_spec and the builders)
for m in ('build_b25h_v2', 'ga25x_spec', 'ga25x_parts', 'ga25x_visual', 'ga25x_cockpit'):
    sys.modules.pop(m, None)
import build_b25h_v2 as B
import b25h_spec as S
import ga25x_spec as G
# 2. GA-25X values into the shared spec module, then reload every builder that read the spec at import time
G.apply(S)
import b25h_geom, b25h_parts, b25h_v3, b25h_v3_cockpit, b25h_v3_arms, b25h_interior
for mod in (b25h_parts, b25h_v3, b25h_v3_cockpit, b25h_v3_arms, b25h_interior):
    importlib.reload(mod)
P, V3, C3, A3, I = b25h_parts, b25h_v3, b25h_v3_cockpit, b25h_v3_arms, b25h_interior
B.P = P
import ga25x_parts as X
import ga25x_visual as VX
ENGINE_CORE_183 = True     # 1.8.3: turboprop core inside the cowl (False = 1.8.2: empty closed cowl)
import ga25x_cockpit as CX
# the B-25H tail cap (glazing with a gun opening) is called from inside build_fuselage: use the sensor tail cone
A3.tail_cap = VX.tailcone
from b25h_geom import V

ROOT_NAME = 'GA25X_root'
MATERIALS = dict(B.MATERIALS)
MATERIALS['paint'] = ((0.30, 0.31, 0.32, 1.0), 0.0, 0.55)       # neutral grey (liveries are textures)
MATERIALS['sensor'] = ((0.03, 0.035, 0.04, 1.0), 0.3, 0.15)     # dielectric sensor windows / panels
MATERIALS['glass'] = ((0.86, 0.66, 0.26, 0.38), 0.6, 0.05)      # gold-film canopy coating (Unity: FastBomber1 gold glass copy)
# visual pass: modern grey primer instead of the WWII zinc-chromate green (Unity: ga25x_interior_b / ga25x_cockpit_b tiles)
MATERIALS['interior'] = ((0.40, 0.415, 0.425, 1.0), 0.0, 0.7)
MATERIALS['cockpit'] = ((0.085, 0.09, 0.095, 1.0), 0.0, 0.8)
MATERIALS['prop'] = ((0.06, 0.065, 0.07, 1.0), 0.2, 0.5)        # composite blades (dark grey)
# 0.3.0: formation / gear-down strips (slimelight_*): unlit look of the AB-4 light_green_off (generator: NavLights entry, lit
# material slimelight_on). NEW material name: GA25XBuild.cs must create mats['light_off'] (see docs/ga25x_v030_model_changes.md)
MATERIALS['light_off'] = ((0.47, 0.61, 0.54, 1.0), 0.0, 0.4)
# 0.3.1 cockpit kitbash (ga25x_cockpit.py): plain cabin materials, no tiles. ck_struct = generator: stock aircraft_structure
# (vertex colour 56/56/56 like the SFB-81 tub); ck_panel = plain dark grey; ck_black = plain matte black (bezels, glareshield)
MATERIALS['ck_struct'] = ((0.055, 0.057, 0.06, 1.0), 0.0, 0.7)
MATERIALS['ck_panel'] = ((0.030, 0.031, 0.034, 1.0), 0.0, 0.6)
MATERIALS['ck_black'] = ((0.006, 0.006, 0.007, 1.0), 0.0, 0.5)
# 0.3.2: panel art (fal atlas ga25x_ckart_b/_n, own UVs on the livery layer; ga25x_ckart_layout.py)
MATERIALS['ck_art'] = ((0.20, 0.205, 0.215, 1.0), 0.0, 0.5)
# 0.3.4: fal-generated split throttle handle (own UVs; Unity: ga25x_throttle_b/_n baked by tripo)
MATERIALS['ck_throttle'] = ((0.12, 0.12, 0.13, 1.0), 0.3, 0.5)


def make_materials():
    B.MATERIALS.clear()
    B.MATERIALS.update(MATERIALS)
    return B.make_materials()


def collect_parts():
    parts = []
    fus, holes = P.build_fuselage()
    fus['fus_center'].parent = ROOT_NAME
    fus['fus_forward'].parent = 'fus_center'
    fus['fus_cockpit'].parent = 'fus_forward'
    fus['fus_nose'].parent = 'fus_cockpit'
    fus['fus_rear'].parent = 'fus_center'
    fus['fus_tail'].parent = 'fus_rear'
    parts += list(fus.values())
    P.open_profile_box(fus['fus_center'].mesh, [(S.BAY_Y[1] - 0.01, -0.83), (S.BAY_Y[1] - 0.01, -0.05), (0.70, -0.05), (0.70, 1.05),
                       (-0.86, 1.05), (-0.86, -0.05), (S.BAY_Y[0] + 0.01, -0.05), (S.BAY_Y[0] + 0.01, -0.83)],
                       -(S.BAY_HALF_X - 0.005), S.BAY_HALF_X - 0.005, 'interior')
    door_axes = {}
    for tag, nm, par, pose_open in (('bayL', 'bomb_door_L', 'fus_center', False), ('bayR', 'bomb_door_R', 'fus_center', False),
                                    ('nwL', 'gear_door_nose_L', 'fus_cockpit', True), ('nwR', 'gear_door_nose_R', 'fus_cockpit', True)):
        qs = holes[tag]
        d = P.door_from_holes(nm, par, qs, lambda p: abs(p.x), 0.0, '')
        op = P.open_pose(d, qs, 92.0 if 'bomb' in nm else 95.0)
        ang = math.degrees(op.angle) * (1 if op.axis.dot(V(d.info['hinge_axis'])) > 0 else -1)
        d.info['open_deg'] = round(ang, 1)
        if pose_open:
            d.pose = op
        parts.append(d)
    parts += VX.build_canopy()
    parts += V3.hatch_from_holes('hatch_entry_fwd', 'fus_forward', holes['hatchFwd'], 100.0,
                                 'weapons officer escape / entry hatch under the capsule; hinged at its front edge')
    parts += V3.hatch_from_holes('hatch_entry_rear', 'fus_rear', holes['hatchRear'], 100.0,
                                 'rear maintenance hatch (avionics bay); not a crew exit')
    for side in (-1, 1):
        parts += P.build_wing(side)
        nac, doors = VX.build_nacelle(side)
        parts += [nac] + doors
        eng, exh = VX.build_turboprop(side)
        if ENGINE_CORE_183:      # 1.8.3: engine body inside the cowl (ga25x_internals; outside look and collider hull unchanged)
            import ga25x_internals as GI
            eng.mesh.extend(GI.turboprop_core(side))
        parts += [eng, exh]
        parts += VX.build_prop6(side)
        parts += P.build_tail(side)
        parts += P.main_strut(side)
        parts += VX.build_package_fairing(side)
        L = 'L' if side < 0 else 'R'
        parts.append(P.Part(f'prop_disc_{L}', f'prop_hub_{L}', (side * S.NAC_X, S.PROP_Y, 0.0), None,
                            info=dict(kind='prop_disc', note='MeshFilter slot for ConstantSpeedProp.propDisc; meshes in '
                                      'ga25x_propdisc.fbx (propdisc_blur, propdisc_full); local +Z (Unity) = spin axis')))
    parts += P.nose_strut()
    parts += X.build_cannon()
    parts += VX.build_chin_turret()
    parts += CX.build_cockpit()       # 0.3.0 cockpit (replaces X.build_cockpit + VX.modern_cockpit)
    parts += VX.build_pylons()
    parts += VX.tailcone_parts()
    parts += X.build_tailhook()
    parts += X.bay_hardpoints()
    byname = {p.name: p for p in parts}
    I.add_forward_compartment(byname['fus_forward'].mesh)
    I.add_center_compartment(byname['fus_center'].mesh, P.wing_station(0.62, 1))
    X.add_bay_carrier(byname['fus_center'].mesh)
    # B-25H rear compartment (floor, racks); its 'waist ammo boxes' are placed from the waist window ranges, which the
    # GA-25X spec moved out of the fuselage (no windows): use the B-25H ranges for these interior boxes only
    S.WAIST_L_Y, S.WAIST_R_Y = (-3.40, -2.85), (-3.95, -3.40)
    I.add_rear_compartment(byname['fus_rear'].mesh)
    S.WAIST_L_Y, S.WAIST_R_Y = G.CHANGES['WAIST_L_Y'], G.CHANGES['WAIST_R_Y']
    parts += VX.add_sensor_panels(byname['fus_rear'].mesh)
    # 0.3.0: dorsal laser ring faired over (the B-25H turret hole is plated with skin), laser turret under the belly
    P.plate(byname['fus_forward'].mesh, holes.pop('turret', []))
    parts += VX.build_laser_belly(byname['fus_rear'].mesh)
    parts += VX.build_slimelights()
    y0, y1 = S.NOSE_WELL_Y
    hx = S.NOSE_WELL_HALF_X - 0.01
    # 0.3.2: top-front corner chamfered (ga25x_cockpit.WELL_CHAMFER): the stock crew figures' inner shins pass in front of it
    P.open_profile_box(byname['fus_cockpit'].mesh, [(y1, -0.84), (y1, CX.WELL_CHAMFER[1]), (CX.WELL_CHAMFER[0], 0.06), (y0, 0.06), (y0, -0.84)], -hx, hx, 'interior')
    tear_report = {}
    if S.FEATURES.get('torn_breaks'):
        tear_report['fuselage'] = V3.tear_fuselage(byname)
        tear_report['wings'] = V3.tear_wings(byname)
    print('[build] tear', tear_report)
    for p in parts:
        n = p.name
        if n.startswith('fus_') or n.startswith(('bomb_door', 'gear_door_nose', 'hatch_entry')):
            p.uv_group = 'fuselage'
        elif n.startswith(('nacelle_', 'gear_door_main_')):
            p.uv_group = 'nacelle_' + n.split('_')[-2 if n.startswith('gear') else -1]
        elif n.startswith(('wing_inner_', 'wing_outer_', 'wing_tip_')):
            p.uv_group = 'wing_' + n[-1]
    mac, le_mac, x_mac, cg_y = B.mac_and_cg()
    root = P.Part(ROOT_NAME, None, (0.0, cg_y, 0.25), None,
                  info=dict(note=f'CG at 27% MAC: MAC={mac:.3f} m, LE(MAC) y={le_mac:.3f} at |x|={x_mac:.2f}'))
    parts.insert(0, root)
    parts.append(P.Part('cockpit_eye', 'fus_cockpit', S.CREW['pilot']['eye'], info=dict(kind='crew_eye', crew='pilot')))
    extras = []
    for nm, mb in A3.prop_disc_meshes(R=S.PROP_R, r0=0.34).items():
        e = P.Part(nm, None, (0, 0, 0), mb, info=dict(kind='prop_disc_mesh', note='hub frame; Unity +Z = spin axis; '
                                                      'UV: blur = v 0.5-1, full disc = v 0-0.5'))
        e.own_uv = True
        extras.append(e)
    return parts, holes, extras


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(HERE, '..', '..', 'assets', 'model_ga25x', 'ga25x.blend')
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    mats = make_materials()
    parts, holes, extras = collect_parts()
    usage, m_per_uv = B.pack_livery(parts)
    coll = bpy.data.collections.new('GA25X')
    scene.collection.children.link(coll)
    objs = B.create_objects(parts, mats, coll)
    xc = bpy.data.collections.new('GA25X_extras')
    scene.collection.children.link(xc)
    B.create_objects(extras, mats, xc)
    tris = sum(p.mesh.tri_count() for p in parts if p.mesh is not None)
    left_holes = {k: len(v) for k, v in holes.items() if k not in ('bayL', 'bayR', 'nwL', 'nwR', 'hatchFwd', 'hatchRear', 'canopy', 'turret')}
    stats = dict(objects=len(objs), tris=tris, livery_usage=round(usage, 4), metres_per_uv=round(m_per_uv, 3),
                 unconsumed_holes=left_holes, spec=dict(nose_tip_y=S.NOSE_TIP_Y, bay_y=S.BAY_Y, bay_half_x=S.BAY_HALF_X,
                                                        prop_r=S.PROP_R))
    scene['b25_build_stats'] = json.dumps(stats)
    print('[build] ' + json.dumps(stats))
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print('[build] saved', out)


if __name__ == '__main__':
    main()
