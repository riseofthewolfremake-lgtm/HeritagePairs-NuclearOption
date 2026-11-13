"""Write the GA-25X build contract for unity/Editor/GA25XBuild.cs: objects the build wires (crew, hatches, controls,
screens, laser turret, doors, hardpoints, sensors, tail hook) with parent, pivot and axes in Unity coordinates, plus
probe points the offline stub test uses.

  blender --background assets/model_ga25x/ga25x.blend --python blender/ga25x/contract_ga25x.py -- --out assets/model_ga25x/ga25x_contract

Coordinates: Unity, x right, y up, z forward (nose), metres, relative to GA25X_root (= CG = FBX origin, gear down).
Rotation rule: Blender +a about (x, y, z) == Unity Quaternion.AngleAxis(-a, (x, z, y)).
"""
import bpy, sys, os, json, math, datetime
from mathutils import Vector, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = os.path.abspath(argv[argv.index('--out') + 1])
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ga25x_spec as G

O = bpy.data.objects
C = O['GA25X_root'].matrix_world.translation.copy()
INFO = {o.name: (json.loads(o['b25_info']) if o.get('b25_info') else {}) for o in O}


def u(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def up_(v):
    return u(Vector(v) - C)


def axes(o):
    R = o.matrix_world.to_3x3().normalized()
    return dict(x=u(R.col[0]), y=u(R.col[2]), z=u(R.col[1]))


def obj(name, **extra):
    o = O[name]
    d = dict(name=name, parent=o.parent.name if o.parent else None, type=o.type, pivot=up_(o.matrix_world.translation),
             local_axes=axes(o))
    d.update({k: v for k, v in INFO.get(name, {}).items() if k not in ('hinge_axis',)})
    d.update(extra)
    return d


def wverts(o):
    return [o.matrix_world @ v.co for v in o.data.vertices] if o.type == 'MESH' else []


def centroid(name):
    vs = wverts(O[name])
    return sum(vs, Vector()) / len(vs)


con = dict(meta=dict(generated=datetime.datetime.now().isoformat(timespec='seconds'), model='assets/model_ga25x/ga25x.fbx',
                     extras_fbx='assets/model_ga25x/ga25x_propdisc.fbx',
                     coords='Unity: x right, y up, z forward (nose); metres; relative to GA25X_root (CG, FBX origin, gear down)',
                     status='built and checked offline (FBX re-import check + stub test); NOT verified in game'))

# ---- crew: pilot (left) + weapons officer (right), both in fus_cockpit (armoured capsule)
con['crew'] = dict(stations=[
    dict(role='pilot', eye=obj('cockpit_eye'), seat=None, part='fus_cockpit', exit_hatch='canopy_jettison_L'),
    dict(role='wso', eye=obj('crew_wso_eye'), seat=None, part='fus_cockpit', exit_hatch='canopy_jettison_R')],
    stock_seat=dict(mesh='ejectionSeat', material='Seats', in_figure=[0.0, 0.0218, -0.041], figure_eye_to_root=[0.0, -0.7147, 0.0651]),
    note='0.3.1: ejection seats (Pilot.ejectionSeat true, generator flag) = the STOCK seat each crew figure carries as its '
         'EjectionSeat child (COIN / SFB-81 pattern); no seat object in our model. Eyes at the figure helmetCamPoint.')

# ---- hatches (stock Canopy): same rule as the B-25H contract (hingeAngle = Unity angle about the hinge empty's local X)
hat = []
for h in ('canopy_jettison_L', 'canopy_jettison_R', 'hatch_entry_fwd'):
    inf = INFO[h]
    hinge = O[h + '_hinge']
    ax_b = hinge.matrix_world.to_3x3() @ Vector((1, 0, 0))
    c0 = centroid(h)
    piv = O[h].matrix_world.translation
    c1 = piv + Quaternion(ax_b, math.radians(inf['open_deg_blender'])) @ (c0 - piv)
    hat.append(dict(hatch=obj(h), hinge=obj(h + '_hinge'), parent_part=hinge.parent.name, axis_parent_space=u(ax_b.normalized()),
                    hingeAngle=round(-inf['open_deg_blender'], 1), probe_closed=up_(c0), probe_open=up_(c1)))
con['hatches'] = dict(hatches=hat, note='0.3.0: canopy_jettison_L/R = jettisonable canopy panels over each seat (COIN values: mass 50, '
                                          'ejectionForce (0,4000,0)); hatch_entry_fwd = ground entry door')

# ---- 0.3.0 formation / gear-down light strips (stock NavLights entries, lit material slimelight_on)
con['lights'] = dict(formation=[obj(n, part=O[n].parent.name, material='light_off') for n in sorted(o.name for o in O if o.name.startswith('slimelight_'))],
                     note='separate quad meshes 3 mm proud of the skin; NavLights controlState 1 (Auto): on with the gear down')

# ---- controls: side sticks (Cockpit.Joystick), pedals (ControlSurface yaw), throttle levers (Cockpit.throttles)
con['controls'] = dict(
    sticks=[obj(f'stick_{L}', stock_mesh='sfb_joystick', stock_materials=['hotas', 'SFB_cockpit'],
                drive=dict(component='Cockpit.joysticks', range=INFO[f'stick_{L}']['range_deg'])) for L in 'LR'],
    pedals=[obj(f'cockpit_rudder_pedals_{L}', drive=dict(component='ControlSurface', field='yawRange', value=-15.0, servoSpeed=60)) for L in 'LR'],
    # 0.3.3: no stock throttle mesh when the cockpit part says so (our split lever cockpit_throttle_arm is its child)
    levers=[obj('cockpit_throttle', **(dict(stock_mesh='sfb_throttle', stock_materials=['SFB_cockpit']) if INFO['cockpit_throttle'].get('stock_mesh') else {}),
                drive=dict(component='Cockpit.throttles', rotation=True, range=INFO['cockpit_throttle']['range_deg']))],
    note='0.3.1 kitbash: stick_L/R and cockpit_throttle are EMPTIES at the stock SFB-81 pivots (Unity identity frame); the generator '
         'adds the stock meshes. Cockpit.Joystick: localEulerAngles = (pitch*range, 0, -roll*range) (range 12 = SFB-81); '
         'Cockpit.Throttle rotation range 52 (= SFB-81). pitch > 0 = push (ControlsFilter.cs:241), roll > 0 = right.')

# ---- screens
roles = dict(mfd_center='tac', mfd_left='tac', mfd_right='targetcam', mfd_wso='tac')
con['mfds'] = [obj(n, role=roles[n], corners=[up_(v) for v in wverts(O[n])]) for n in ('mfd_center', 'mfd_left', 'mfd_right', 'mfd_wso')]

# ---- laser turret (Turret + Laser; Turret.cs writes az (0,trav,0) and el (elev,0,0) ABSOLUTELY)
ia, ie = INFO['laser_turret_az'], INFO['laser_turret_el']
con['laser_turret'] = dict(mount=obj('laser_turret_mount'), az=obj('laser_turret_az'), el=obj('laser_turret_el'),
                           muzzle=obj('muzzle_laser'),
                           Turret=dict(traverseRange=ia['traverseRange'], traverseRate=ia['traverseRate'],
                                       minElevation=ie['minElevation'], maxElevation=ie['maxElevation'], elevationRate=ie['elevationRate']))

# ---- doors (gear + bay): hinge axis in parent space (Unity) and the Unity opening angle (B25HBuild DoorHinge convention)
doors = []
for n in sorted(o.name for o in O if o.name.startswith(('gear_door_', 'bomb_door_')) and o.type == 'MESH'):
    inf = INFO[n]
    doors.append(dict(name=n, parent=O[n].parent.name, axis_unity=u(inf['hinge_axis']), open_unity=round(-inf['open_deg'], 1),
                      open_in_file=not n.startswith('bomb_door')))
con['doors'] = doors

# ---- hardpoints, sensors, flares, tail hook
con['hardpoints'] = [obj(n) for n in ('hp_bombbay', 'hp_bay_L', 'hp_bay_R', 'hp_inner_L', 'hp_inner_R', 'hp_outer_L', 'hp_outer_R', 'hp_tailhook')]
# visual pass: 4 pylons per wing; the two new stations are listed separately so the 0.1.0 list stays as it was
con['hardpoints_added'] = [obj(n) for n in ('hp_root_L', 'hp_root_R', 'hp_mid_L', 'hp_mid_R') if n in O]
con['bay'] = dict(y=[round(G.CHANGES['BAY_Y'][0] - C.y, 4), round(G.CHANGES['BAY_Y'][1] - C.y, 4)], half_x=G.CHANGES['BAY_HALF_X'],
                  note='bomb bay extent along Unity z (relative to the root) and half width')
con['sensors'] = dict(targetcam=obj('targetcam_point'), radar=obj('radar_antenna'), tail=obj('mws_tail'), chin=obj('chin_turret'))
con['flares'] = [obj(n) for n in ('flare_L', 'flare_R', 'flare_tail_L', 'flare_tail_R')]
th = obj('tailhook')
th['end'] = obj('tailhook_end')
con['tailhook'] = th
con['guns'] = dict(cannon=obj('cannon'), muzzle_cannon=obj('muzzle_cannon'),
                   package=[obj('package_guns_L'), obj('package_guns_R')], muzzles_package=[obj('muzzle_package_L1'), obj('muzzle_package_R1')])
con['prop_discs'] = dict(slots=[obj('prop_disc_L'), obj('prop_disc_R')], meshes=['propdisc_blur', 'propdisc_full'])
wheels = {n: up_(O[n].matrix_world.translation) for n in ('gear_nose_wheel', 'gear_main_L_wheel', 'gear_main_R_wheel')}
con['gear'] = dict(axles=wheels, main_wheel_r=0.597, nose_wheel_r=0.38)

with open(out + '.json', 'w') as f:
    json.dump(con, f, indent=1)
with open(out + '.md', 'w', encoding='utf-8') as f:
    f.write('# GA-25X build contract (generated by blender/ga25x/contract_ga25x.py)\n\n')
    f.write(f"Generated {con['meta']['generated']}. {con['meta']['coords']}. Status: {con['meta']['status']}.\n\n"
            'Machine-readable twin: `ga25x_contract.json`. Consumed by `unity/Editor/GA25XBuild.cs`.\n\n')
    f.write('| section | objects |\n|---|---|\n')
    for k in ('crew', 'hatches', 'controls', 'mfds', 'lights', 'laser_turret', 'doors', 'hardpoints', 'sensors', 'flares', 'tailhook', 'guns'):
        v = con[k]
        names = []

        def walk(x):
            if isinstance(x, dict):
                if 'name' in x and isinstance(x['name'], str):
                    names.append(f"{x['name']} {x.get('pivot', '')}")
                for vv in x.values():
                    if isinstance(vv, (dict, list)):
                        walk(vv)
            elif isinstance(x, list):
                for vv in x:
                    walk(vv)
        walk(v)
        f.write(f"| {k} | {'; '.join(names)} |\n")
print('[contract] wrote', out + '.json')
