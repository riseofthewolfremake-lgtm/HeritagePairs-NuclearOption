"""Write the build contract for B25HBuild.cs: every new / changed object with parent, pivot and axes in Unity
coordinates, driver axis / sign / range, plus probe points the offline stub test uses to verify the sign claims.

  blender --background assets/model_v2/b25h_v2.blend --python blender/v2/contract_b25h_v2.py -- --out assets/model_v2/b25h_v2_contract

Coordinates: Unity, x right, y up, z forward (nose), metres, relative to B25H_root (= CG = FBX origin, gear down).
Rotation rule (export_b25h_v2.py): Blender +a about axis (x, y, z) == Unity Quaternion.AngleAxis(-a, (x, z, y)).
"""
import bpy, sys, os, json, math, datetime
from mathutils import Vector, Quaternion, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = os.path.abspath(argv[argv.index('--out') + 1])
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b25h_spec as S

O = bpy.data.objects
C = O['B25H_root'].matrix_world.translation.copy()
INFO = {o.name: (json.loads(o['b25_info']) if o.get('b25_info') else {}) for o in O}


def u(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def up_(v):
    return u(Vector(v) - C)


def axes(o):
    R = o.matrix_world.to_3x3().normalized()
    return dict(x=u(R.col[0]), y=u(R.col[2]), z=u(R.col[1]))


def wverts(o):
    return [o.matrix_world @ v.co for v in o.data.vertices] if o.type == 'MESH' else []


def obj(name, **extra):
    o = O[name]
    d = dict(name=name, parent=o.parent.name if o.parent else None, type=o.type, pivot=up_(o.matrix_world.translation),
             local_axes=axes(o))
    inf = {k: v for k, v in INFO.get(name, {}).items() if k not in ('hinge_axis',)}
    d.update(inf)
    d.update(extra)
    return d


def far_probe(name, pick=None):
    o = O[name]
    p = o.matrix_world.translation
    vs = wverts(o)
    if not vs:
        return None
    v = max(vs, key=pick) if pick else max(vs, key=lambda q: (q - p).length)
    return up_(v)


def centroid(name):
    vs = wverts(O[name])
    return sum(vs, Vector()) / len(vs)


def rot_world_about(o_name, axis_world, deg, pts):
    piv = O[o_name].matrix_world.translation
    q = Quaternion(Vector(axis_world), math.radians(deg))
    return [piv + q @ (p - piv) for p in pts]


con = dict(
    meta=dict(generated=datetime.datetime.now().isoformat(timespec='seconds'), model='assets/model_v2/b25h_v2.fbx',
              extras_fbx='assets/model_v2/b25h_v2_propdisc.fbx',
              coords='Unity: x right, y up, z forward (nose); metres; relative to B25H_root (CG, FBX origin, gear down)',
              rotation_rule='Blender +a about (x,y,z) == Unity Quaternion.AngleAxis(-a, (x,z,y)); all angles below are UNITY angles',
              unity_angle_sense='Quaternion.AngleAxis(+90, X) * Y = +Z (standard right-hand formula on Unity numbers)',
              status='built and checked offline (Blender re-import + mechanics check + stub test); NOT verified in game'),
)

# ------------------------------------------------------------------ renames / removals / moves
con['renames'] = [
    dict(old='waist_blister_L', new='hatch_waist_L', note='waist window is now a hinged, jettisonable hatch with a ball socket'),
    dict(old='waist_blister_R', new='hatch_waist_R', note='as above'),
]
con['changed_meaning'] = [
    dict(name='cockpit_yoke_L', was='whole yoke (column + wheel) pivoting at the floor; B25HBuild Cockpit.joysticks[0]',
         now='the WHEEL only, child of cockpit_column_L, pivot at the hub, local +X = hub axis',
         build_action='drive cockpit_column_L (pitch) and cockpit_yoke_L (roll) separately (see controls); B25HBuild.cs:1196'),
    dict(name='turret_dorsal', was='static dome + ring', now='azimuth body (drum, dome, cradle supports, gunner seat), child of turret_dorsal_mount'),
    dict(name='turret_dorsal_guns', was='static twin guns', now='elevation cradle; guns are gun_turret_L/R'),
    dict(name='tail_guns', was='static twin guns at y=-9.42', now='elevation cradle at the trunnion, child of tail_turret_az; '
         'muzzles moved (pivot y -9.55)'),
    dict(name='waist_gun_L / waist_gun_R', was='static gun inside the fuselage', now='elevation part of the ball mount in the hatch glass'),
    dict(name='cannon', was='75 mm M4 shape', now='75 mm T13E1 (lighter barrel, concentric recoil sleeve, vertical sliding block)',
         build_action='optional: rename HUD label "75mm M4 Cannon" -> "75mm T13E1" (OwnM4WeaponInfo)'),
    dict(name='hp_rail_*, hp_wingrack_*, hp_bombbay', was='floating 0.12-0.15 m under the wing / in the bay roof',
         now='at the bottom face of the new pylons; hp_bombbay lowered 0.23 m under a carrier beam'),
    dict(name='canopy_glass / canopy_frame', was='faceted per-quad plates', now='smooth shared-vertex grid + swept bars; the roof hatch is cut out of canopy_glass'),
    dict(name='cockpit_gauges', was='29 flat faces', now='16 dial faces (8x8 cell atlas); movers are separate gauge_* objects'),
    dict(name='fus_* split ends, wing_inner/outer/tip split ends', was='flat capped bulkhead webs / ribs',
         now='torn: jagged complementary skin edges, set-back frame/rib, stringer/spar stubs (material structure)'),
]

# ------------------------------------------------------------------ controls
ctl = []
for L in 'LR':
    for nm in (f'cockpit_column_{L}', f'cockpit_yoke_{L}', f'cockpit_rudder_pedals_{L}'):
        if nm not in O:
            continue
        o = O[nm]
        inf = INFO[nm]
        if 'column' in nm:
            probe = far_probe(nm, pick=lambda q: q.z)
            drive = dict(component='ControlSurface', field='pitchRange', value=-12.0, servoSpeed=60,
                         alt='Cockpit.Joystick on this transform drives X=pitch*range but ALSO Z=-roll*range; use ControlSurface')
        elif 'yoke' in nm:
            probe = far_probe(nm, pick=lambda q: (q - o.matrix_world.translation).dot(o.matrix_world.to_3x3() @ Vector((0, 0, 1))))
            drive = dict(component='ControlSurface', field='rollRange', value=45.0, servoSpeed=120)
        else:
            probe = far_probe(nm, pick=lambda q: q.x)
            drive = dict(component='ControlSurface', field='yawRange', value=-15.0, servoSpeed=60)
        ctl.append(obj(nm, drive=drive, probe=probe,
                       attachedSurface='any AeroPart of the aircraft (only used for parentUnit / IsDetached), e.g. fus_cockpit'))
con['controls'] = dict(
    note='ControlSurface rotates visibleMesh by rest * AngleAxis(pitch*pitchRange + roll*rollRange + yaw*yawRange, Vector3.right) '
         '(ControlSurfaceJob_Math.cs:75); one ControlSurface per transform, its attachedSurface = fus_cockpit. '
         'Input signs: ControlsFilter.cs:241 uses pitch * gLimitPositive, so pitch > 0 = pull; Cockpit.Joystick (Cockpit.cs:20) '
         'uses Z = -roll*range, so roll > 0 = right. Values below assume those signs (live probe 1 settles them).',
    objects=ctl)

# ------------------------------------------------------------------ gauges
gauges = []
for o in sorted([o for o in O if o.name.startswith('gauge_') and o.type == 'MESH'], key=lambda o: o.name):
    inf = INFO[o.name]
    g = obj(o.name, probe=far_probe(o.name))
    if o.name.startswith(('gauge_manifold', 'gauge_rpm')):
        full = (44 - inf['v0']) * inf['deg_per_unit'] if 'manifold' in o.name else 2600 * inf['deg_per_unit']
        g['stock_driver'] = dict(component='Cockpit.throttles[] entry', rotation=True, motion=False, transform=o.name,
                                 range=round(full, 1), note='needle = throttle * range (full throttle = 44 inHg / 2600 rpm); '
                                 'approximation: no stock component reads engine rpm or manifold pressure into a transform')
    else:
        g['stock_driver'] = None
    gauges.append(g)
con['gauges'] = dict(
    note='No stock aircraft has 3D needle instruments: stock flight data is drawn by the tac-screen UI (BasicFlightInstruments '
         'in tacScreen_*.prefab: airspeed/altitude/climb/heading as text, horizon as an image). The only stock component that '
         'can turn a transform from a flight value is Cockpit.Throttle (rotation mode, throttle only). The other needles need a '
         'runtime component or stay at rest. Each needle/card: local +X = toward the pilot, rest = 12 o\'clock; '
         'Unity +angle about local +X = clockwise as seen by the pilot; angle = (value - v0) * deg_per_unit.',
    texture='b25h_gauges: 8 x 8 cells, cell k at column k % 8, row k // 8 (row 0 at v = 0). Faces: 0 airspeed, 1 attitude bezel, '
            '2 altimeter, 3 heading bezel, 4 vsi, 5 fuel, 6/7 manifold L/R, 8/9 rpm L/R, 10 attitude card (horizon), 11 compass card, '
            '12 oil press, 13 oil temp, 14 cyl temp, 15 hydraulic, 16 flaps, 17 gear; 62 = needle (white, tip at the top of '
            'the cell), 63 = short needle. Scales start at 12 o\'clock and run clockwise over the sweep in the list.',
    faces=obj('cockpit_gauges'), movers=gauges)

# ------------------------------------------------------------------ throttle levers (quadrant)
levers = []
for nm in ('quadrant_throttle_L', 'quadrant_throttle_R'):
    if nm not in O:
        continue
    g = obj(nm, probe=far_probe(nm))
    g['stock_driver'] = dict(component='Cockpit.throttles[] entry', rotation=True, motion=False, transform=nm,
                             range=INFO[nm]['range_deg'], note='lever = throttle * range about local X; modelled at idle')
    levers.append(g)
con['levers'] = dict(note='Throttle levers: Cockpit.Throttle rotation (localEulerAngles = (throttle * range, 0, 0)), '
                          'local X = lateral, +angle = lever top forward. Prop and mixture levers are static in cockpit_interior.',
                     movers=levers)

# ------------------------------------------------------------------ MFDs, gunsight
con['mfds'] = [obj(n, corners=[up_(v) for v in wverts(O[n])]) for n in ('mfd_center', 'mfd_left', 'mfd_right')]
con['mfd_note'] = ('Stock: one tac screen per cockpit (CI-22 targetScreen 0.39 x 0.29 m, CAS1 tacscreen 0.60 x 0.34 m) whose '
                   'renderer is Cockpit.tacScreenRender; the TacScreen UI renders to a RenderTexture shown with tacScreenDisplay.mat. '
                   'Use mfd_center as tacScreenRender; mfd_left/right have no stock driver (static screen material or a second '
                   'camera/texture). Material slot name `screen` (already in B25HBuild mats).')
con['gunsight'] = [obj('gunsight_pilot'), obj('gunsight_combiner')]

# ------------------------------------------------------------------ turrets
tur = []
for mount, az, el, guns in (('turret_dorsal_mount', 'turret_dorsal', 'turret_dorsal_guns', ('gun_turret_L', 'gun_turret_R')),
                            ('tail_turret_mount', 'tail_turret_az', 'tail_guns', ('gun_tail_L', 'gun_tail_R')),
                            ('waist_gun_L_mount', 'waist_gun_L_az', 'waist_gun_L', ('gun_waist_L',)),
                            ('waist_gun_R_mount', 'waist_gun_R_az', 'waist_gun_R', ('gun_waist_R',))):
    ia, ie = INFO[az], INFO[el]
    gl = []
    for g in guns:
        mz = 'muzzle' + g[3:]
        gl.append(dict(gun=obj(g), muzzle=obj(mz)))
    tur.append(dict(mount=obj(mount), az=obj(az), el=obj(el), guns=gl,
                    Turret=dict(transform=az, elevationTransform=el, traverseRange=ia['traverseRange'], traverseRate=ia['traverseRate'],
                                minElevation=ie['minElevation'], maxElevation=ie['maxElevation'], elevationRate=ie['elevationRate']),
                    probe_muzzle=up_(O['muzzle' + guns[0][3:]].matrix_world.translation)))
con['turrets'] = dict(
    note='Turret.cs sets turret.localEulerAngles = (0, traverse, 0) and elevationTransform.localEulerAngles = (elev, 0, 0) '
         'ABSOLUTELY (Turret.cs:715-716) and clamps elev to [-maxElevation, -minElevation] (Turret.cs:714): Unity +X = muzzle '
         'down. Our az/el rest with identity local rotation, the orientation lives in *_mount. Gun bodies gun_* are our own M2 '
         'meshes placed at the stock UH-90 door-gun barrel origin (turret_12.7mm_door/traverse/barrel, mesh 50cal_doorGun_barrel, '
         'muzzle at local (0, 0.046, 1.200)): swap the mesh to the stock one 1:1 or keep ours. Gun component: like '
         'turret_12.7mm_door barrel (Gun.cs on the barrel object, muzzles = muzzle_*).',
    turrets=tur)

# ------------------------------------------------------------------ crew
crew = []
eyes = dict(pilot='cockpit_eye', navigator='crew_navigator_eye', engineer='crew_engineer_eye', radio='crew_radio_eye', tail='crew_tail_eye')
seats = dict(pilot='cockpit_seat_L', navigator='cockpit_seat_R', engineer='turret_dorsal', radio='crew_seat_radio', tail='crew_seat_tail')
for role, c in S.CREW.items():
    crew.append(dict(role=role, eye=obj(eyes[role]), seat=seats[role], part=c['part'], exit_hatch=c['hatch']))
con['crew'] = dict(
    note='Stock multi-crew aircraft (EW-25 4 crew, FastBomber1 / Darkreach 2, UH-90 2) mark each crew member with a GameObject '
         'carrying Pilot.cs + CapsuleCollider whose figure has a helmetCamPoint; Aircraft.pilots[] bails them out one by one '
         '(Aircraft.cs:150-230, 500 ms apart without ejection seat) after RpcJettisonCanopy ejects every Canopy in the air '
         '(Aircraft.cs:2777). There is no separate exit point: the figure leaves from its own transform. Place one Pilot per '
         'crew_*_eye (helmetCamPoint on the eye, as done for the pilot), ejectionSeat = false.',
    stations=crew)

# ------------------------------------------------------------------ hatches
hat = []
for h in ('hatch_cockpit_top', 'hatch_entry_fwd', 'hatch_entry_rear', 'hatch_waist_L', 'hatch_waist_R'):
    inf = INFO[h]
    hinge = O[h + '_hinge']
    ax_b = hinge.matrix_world.to_3x3() @ Vector((1, 0, 0))
    c0 = centroid(h)
    c1 = rot_world_about(h, ax_b, inf['open_deg_blender'], [c0])[0]
    hat.append(dict(hatch=obj(h), hinge=obj(h + '_hinge'), parent_part=hinge.parent.name, axis_parent_space=u(ax_b.normalized()),
                    hingeAngle=round(-inf['open_deg_blender'], 1), probe_closed=up_(c0), probe_open=up_(c1)))
con['hatches'] = dict(
    note='Canopy.cs: CanopyHinge.Animate sets transform.localEulerAngles = right * hingeAngle * openAmount (absolute) -> use '
         'hatch_* as the CanopyHinge transform (it rests identity under hatch_*_hinge whose local +X = hinge axis). '
         'In flight RpcJettisonCanopy calls Canopy.Eject: set ejectionTransform = hatch_* (gets its own Rigidbody, mass ~15 kg, '
         'ejectionCollider = a small box on it); on the ground OpenHinges() swings them to hingeAngle. hingeAngle is the Unity '
         'angle about the hinge axis (local +X of the hinge empty); axis_parent_space is also given for B25HBuild DoorHinge-style '
         'wiring (parents are unrotated, so parent space = root space).',
    hatches=hat)

# ------------------------------------------------------------------ prop discs
con['prop_discs'] = dict(
    slots=[obj('prop_disc_L'), obj('prop_disc_R')],
    meshes=dict(file='b25h_v2_propdisc.fbx', objects=['propdisc_blur', 'propdisc_full'], frame='hub frame, Unity +Z = spin axis',
                radius=S.PROP_R, hub_radius=0.17, uv='propdisc_blur: v 0.5-1 (top half), propdisc_full: v 0-0.5 (bottom half), '
                'u 0-1 across; matches the CI-22 COIN_propblur_b layout (512 x 1024)'),
    ConstantSpeedProp=dict(propDisc='MeshFilter on prop_disc_L/R (add MeshFilter + MeshRenderer with the propdisc material)',
                           propDiscMeshes=[None, 'propdisc_blur', 'propdisc_full'], propDiskThicknessMin=0.5, propDiskThicknessMax=3.0,
                           note='ConstantSpeedProp.PropAnimate (ConstantSpeedProp.cs:623-639): index = floor(Count * (rpmRatio*0.55 + 0.25)); '
                                'blades render only at index 0; localScale.z = lerp(min, max, pitch/90) (our discs are 8 mm thick)'),
    likely_cause_of_vanishing_props='B25HBuild.DiscMesh maps the WHOLE 0-1 square onto the disc, but the CI-22 blur texture holds '
                                    'the blade blur in the top half and the disc in the bottom half; the disc centre samples the '
                                    'transparent band between them, so with blades hidden (index >= 1) the prop is nearly invisible. '
                                    'Inference from the code and texture, not observed in game.')

# ------------------------------------------------------------------ pylons / hardpoints
hps = []
for p in sorted([o for o in O if o.name.startswith('pylon_')], key=lambda o: o.name):
    hp = 'hp_' + p.name[6:]
    hps.append(dict(hardpoint=obj(hp), pylon=obj(p.name), part=p.parent.name))
hps.append(dict(hardpoint=obj('hp_bombbay'), pylon=None, part='B25H (fus_center)'))
con['hardpoints'] = dict(
    note='Stock pattern (CAS1): the WeaponManager hardpoint transform IS the pylon object, whose mesh origin is its bottom face '
         '(CAS1_pylon1 mesh y 0..0.242). Stock mount tops sit above the hardpoint: RocketPod1_single rail mesh top +0.055, '
         'bomb_*_single launchpylon1 top +0.030 (500 lb, cluster) / +0.050 (125/250 lb); internal mounts hang bombs 0.15 m below. '
         'So our hardpoints sit on the pylon bottom faces and the stock rails sink 3-5.5 cm into the pylon.',
    hardpoints=hps)

# ------------------------------------------------------------------ break parts
parent_map = {}
for nm in ('fus_center', 'fus_forward', 'fus_cockpit', 'fus_nose', 'fus_rear', 'fus_tail'):
    parent_map[nm] = O[nm].parent.name if O[nm].parent else None
for L in 'LR':
    for nm in (f'wing_inner_{L}', f'wing_outer_{L}', f'wing_tip_{L}', f'nacelle_{L}', f'engine_{L}', f'stab_{L}', f'fin_{L}',
               f'elevator_{L}', f'rudder_{L}', f'flap_inner_{L}', f'flap_outer_{L}', f'aileron_{L}'):
        parent_map[nm] = O[nm].parent.name
con['breaks'] = dict(
    parent_map=parent_map,
    torn_planes=dict(fuselage={str(k): v for k, v in S.FUS_TORN.items()}, wings={str(k): v for k, v in S.WING_TORN.items()},
                     amplitude_m=dict(fuselage=S.TEAR_AMP_FUS, wing=S.TEAR_AMP_WING), setback_m=S.TEAR_SETBACK),
    note='Part split and names unchanged (B25HBuild PartSpec list). Each tear plane is shared by the two parts with identical, '
         'complementary jagged skin edges (no gap while intact); behind each edge sits a set-back frame (fuselage) or closed rib '
         '(wing) and stringer / spar stubs that reach through the plane into the mating part. Break faces use the existing '
         '`structure` material (tiled, UV1) like the stock jet_mechanical submesh; skin damage stays on the paint shader '
         '(_HitPoints). No separate damaged meshes are needed (the stock aircraft have none).')

con['build_actions'] = [
    'Cockpit: wire cockpit_column_L/R (pitch), cockpit_yoke_L/R (roll), cockpit_rudder_pedals_L/R (yaw) with one ControlSurface '
    'each (attachedSurface = fus_cockpit part); remove the Cockpit.joysticks entry on cockpit_yoke_L (B25HBuild.cs:1196).',
    'Cockpit view copies (B25HBuild.cs:1163): add cockpit_column_L/R, cockpit_yoke_R, cockpit_rudder_pedals_R, gauge_* (meshes), '
    'mfd_*, gunsight_*; keep canopy_glass off the cockpit layer as now.',
    'Cockpit.tacScreenRender = mfd_center renderer (replaces screen_dummy, B25HBuild.cs:1188).',
    'Throttle-driven needles: Cockpit.throttles += {rotation: true, transform: gauge_manifold_L_needle ...} (see gauges).',
    'Turrets: Turret on turret_dorsal / tail_turret_az / waist_gun_*_az with elevationTransform = the el object; Gun on gun_* '
    'with muzzles = muzzle_*; WeaponStations as turret_12.7mm_door. AI gunners: TargetDetector per turret (stock door gun).',
    'Hatches: one Canopy per hatch (CanopyHinge.transform = hatch_*, hingeAngle from the table, ejectionTransform = hatch_*).',
    'Crew: Pilot objects at crew_*_eye (4 more besides the pilot), ejectionSeat = false.',
    'Prop: import b25h_v2_propdisc.fbx meshes; ConstantSpeedProp.propDisc = MeshFilter on prop_disc_L/R, '
    'propDiscMeshes = [null, propdisc_blur, propdisc_full]; drop DiscMesh().',
    'Materials: new slot `screen` (exists in B25HBuild mats), `propdisc` only in the extras FBX. CopyMesh '
    '(B25HBuild.cs:445-447) keeps UV0 only for paint/gauges/glass: add `screen` there, or the MFD 0-1 UVs are replaced by UV1.',
    'Hardpoints: no code change (same names); re-check the loadout preview: mounts now touch the pylons.',
]

with open(out + '.json', 'w') as f:
    json.dump(con, f, indent=1)


def md_table(rows, cols):
    s = '| ' + ' | '.join(c for c, _ in cols) + ' |\n|' + '---|' * len(cols) + '\n'
    for r in rows:
        s += '| ' + ' | '.join(str(fn(r)) for _, fn in cols) + ' |\n'
    return s


with open(out + '.md', 'w', encoding='utf-8') as f:
    f.write('# B-25H v2 build contract (generated by blender/v2/contract_b25h_v2.py)\n\n')
    f.write(f"Generated {con['meta']['generated']}. {con['meta']['coords']}. {con['meta']['rotation_rule']}. "
            f"Status: {con['meta']['status']}.\n\nMachine-readable twin: `b25h_v2_contract.json` (also has probe points).\n\n")
    f.write('## Renames and changed meaning\n\n')
    f.write(md_table(con['renames'], [('old', lambda r: r['old']), ('new', lambda r: r['new']), ('note', lambda r: r['note'])]))
    f.write('\n' + md_table(con['changed_meaning'], [('object', lambda r: r['name']), ('was', lambda r: r['was']), ('now', lambda r: r['now']),
                                                      ('build', lambda r: r.get('build_action', ''))]))
    f.write('\n## Control column, yoke, pedals\n\n' + con['controls']['note'] + '\n\n')
    f.write(md_table(con['controls']['objects'], [('object', lambda r: r['name']), ('parent', lambda r: r['parent']), ('pivot', lambda r: r['pivot']),
                                                  ('local X (axis)', lambda r: r['local_axes']['x']), ('drive', lambda r: f"{r['drive']['component']}.{r['drive']['field']} = {r['drive']['value']}"),
                                                  ('sign', lambda r: r['sign'])]))
    f.write('\n## Gauges\n\n' + con['gauges']['note'] + '\n\n' + con['gauges']['texture'] + '\n\n')
    f.write(md_table(con['gauges']['movers'], [('object', lambda r: r['name']), ('parent', lambda r: r['parent']), ('pivot', lambda r: r['pivot']),
                                               ('local X', lambda r: r['local_axes']['x']), ('value', lambda r: r.get('value', '')),
                                               ('range', lambda r: f"{r.get('v0', '')}..{r.get('v1', '')} {r.get('unit', '')}"),
                                               ('deg/unit', lambda r: r.get('deg_per_unit', r.get('note', ''))),
                                               ('stock driver', lambda r: (f"Cockpit.throttles rotation, range {r['stock_driver']['range']}" if r['stock_driver'] else 'none (custom)'))]))
    f.write('\n## MFD screens\n\n' + con['mfd_note'] + '\n\n')
    f.write(md_table(con['mfds'], [('object', lambda r: r['name']), ('parent', lambda r: r['parent']), ('centre', lambda r: r['pivot']),
                                   ('size m', lambda r: r['size_m']), ('normal', lambda r: r['normal_unity']), ('uv', lambda r: r['uv']), ('use', lambda r: r['note'])]))
    f.write('\nGunsight: `gunsight_pilot` (body) and `gunsight_combiner` (glass quad, reticle material slot) at ' +
            str(con['gunsight'][1]['pivot']) + '.\n')
    f.write('\n## Turrets and guns\n\n' + con['turrets']['note'] + '\n\n')
    rows = []
    for t in con['turrets']['turrets']:
        T = t['Turret']
        rows.append(dict(mount=t['mount']['name'], az=f"{t['az']['name']} @ {t['az']['pivot']}", el=f"{t['el']['name']} @ {t['el']['pivot']}",
                         fwd=t['mount']['local_axes']['z'], lim=f"traverse +-{T['traverseRange']} @ {T['traverseRate']}/s, el {T['minElevation']}..{T['maxElevation']} @ {T['elevationRate']}/s",
                         guns=', '.join(f"{g['gun']['name']} (muzzle {g['muzzle']['name']} @ {g['muzzle']['pivot']})" for g in t['guns'])))
    f.write(md_table(rows, [(k, (lambda r, k=k: r[k])) for k in ('mount', 'az', 'el', 'fwd', 'lim', 'guns')]))
    f.write('\n## Crew stations\n\n' + con['crew']['note'] + '\n\n')
    f.write(md_table(con['crew']['stations'], [('role', lambda r: r['role']), ('eye', lambda r: r['eye']['name']), ('eye pos', lambda r: r['eye']['pivot']),
                                               ('look (+Z)', lambda r: r['eye']['local_axes']['z']), ('eye parent', lambda r: r['eye']['parent']),
                                               ('seat', lambda r: r['seat']), ('exit hatch', lambda r: r['exit_hatch'])]))
    f.write('\n## Hatches\n\n' + con['hatches']['note'] + '\n\n')
    f.write(md_table(con['hatches']['hatches'], [('hatch', lambda r: r['hatch']['name']), ('hinge empty', lambda r: r['hinge']['name']),
                                                 ('parent', lambda r: r['parent_part']), ('pivot', lambda r: r['hinge']['pivot']),
                                                 ('axis (parent space)', lambda r: r['axis_parent_space']), ('hingeAngle (Unity)', lambda r: r['hingeAngle']),
                                                 ('note', lambda r: r['hatch'].get('note', ''))]))
    pdc = con['prop_discs']
    f.write('\n## Prop discs\n\n' + json.dumps(pdc['meshes']) + '\n\n' + json.dumps(pdc['ConstantSpeedProp']) + '\n\n'
            'Likely cause of the vanishing props: ' + pdc['likely_cause_of_vanishing_props'] + '\n\n')
    f.write(md_table(pdc['slots'], [('slot', lambda r: r['name']), ('parent', lambda r: r['parent']), ('pivot', lambda r: r['pivot']),
                                    ('spin axis (+Z)', lambda r: r['local_axes']['z'])]))
    f.write('\n## Pylons and hardpoints\n\n' + con['hardpoints']['note'] + '\n\n')
    f.write(md_table(con['hardpoints']['hardpoints'], [('hardpoint', lambda r: r['hardpoint']['name']), ('position', lambda r: r['hardpoint']['pivot']),
                                                       ('pylon', lambda r: r['pylon']['name'] if r['pylon'] else '-'), ('part', lambda r: r['part'])]))
    f.write('\n## Break parts\n\n' + con['breaks']['note'] + '\n\n')
    f.write(md_table(list(con['breaks']['parent_map'].items()), [('part', lambda r: r[0]), ('parent', lambda r: r[1])]))
    f.write('\nTorn planes: ' + json.dumps(con['breaks']['torn_planes']) + '\n')
    f.write('\n## Build actions (for B25HBuild.cs)\n\n' + ''.join(f'- {a}\n' for a in con['build_actions']))
print('[contract] wrote', out + '.json', out + '.md')
