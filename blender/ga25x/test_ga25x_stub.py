"""Offline stub test for the GA-25X: the contract + parts table (Blender export) and the numbers in
unity/Editor/GA25XBuild.cs, run against small re-implementations of the stock game code the build relies on
(decompiled sources quoted in docs/ga25x_design.md). Normal, failure and release paths.

  python blender/ga25x/test_ga25x_stub.py assets/model_ga25x

Exit code 0 = all pass. Nothing here runs the game; "PASS" means consistent with the stock code as read, not "works in game".
"""
import sys, os, json, math, re

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'model_ga25x'))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CS = os.path.join(ROOT, 'unity', 'Editor', 'GA25XBuild.cs')
DNS = r'C:\Users\User\nuclearoption-ref\BlueprinterProject\Blueprinter-Editor\Assets\Blueprinter\_donotship\MonoBehaviour'

con = json.load(open(os.path.join(OUT, 'ga25x_contract.json')))
parts = {r['name']: r for r in json.load(open(os.path.join(OUT, 'ga25x_parts.json')))}
res = []


def check(name, ok, detail=''):
    res.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + (f' : {detail}' if detail else ''))


# ------------------------------------------------------------------ vector helpers (Unity conventions, left-handed)
def rotx(v, deg):   # Unity Quaternion.Euler(deg, 0, 0) * v
    a = math.radians(deg); x, y, z = v
    return (x, y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a))


def roty(v, deg):
    a = math.radians(deg); x, y, z = v
    return (x * math.cos(a) + z * math.sin(a), y, -x * math.sin(a) + z * math.cos(a))


def rotz(v, deg):
    a = math.radians(deg); x, y, z = v
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z)


def sub(a, b): return tuple(p - q for p, q in zip(a, b))
def add(a, b): return tuple(p + q for p, q in zip(a, b))
def dot(a, b): return sum(p * q for p, q in zip(a, b))
def norm(a): return math.sqrt(dot(a, a))
def unit(a): n = norm(a); return tuple(p / n for p in a)
def ang(a, b): return math.degrees(math.acos(max(-1, min(1, dot(unit(a), unit(b))))))


# ------------------------------------------------------------------ 1. contract integrity
names = []


def walk(x):
    if isinstance(x, dict):
        if isinstance(x.get('name'), str) and 'pivot' in x:
            names.append(x['name'])
        for v in x.values():
            walk(v)
    elif isinstance(x, list):
        for v in x:
            walk(v)


walk(con)
missing = sorted({n for n in names if n not in parts})
check('every contract object exists in the exported parts table', not missing, missing or f'{len(set(names))} objects')
bad_parent = [n for n, r in parts.items() if r['parent'] and r['parent'] not in parts]
check('every parent in the parts table exists', not bad_parent, bad_parent)
check('object names unique', len(parts) == len({r['name'] for r in parts.values()}), len(parts))

# ------------------------------------------------------------------ 2. laser turret (Turret.cs absolute angles + Laser.cs cone)
lt = con['laser_turret']
idn = lambda ax: all(abs(a - b) < 1e-3 for a, b in zip(ax['x'] + ax['y'] + ax['z'], (1, 0, 0, 0, 1, 0, 0, 0, 1)))
check('laser az/el rest identity (Turret writes absolute local euler)', idn(lt['az']['local_axes']) and idn(lt['el']['local_axes']) and idn(lt['mount']['local_axes']))
mz = sub(lt['muzzle']['pivot'], lt['el']['pivot'])
check('laser aperture on the el forward axis (+Z)', mz[2] > 0.25 and abs(mz[0]) < 1e-3 and abs(mz[1]) < 1e-3, mz)
T = lt['Turret']


def turret_aim(target_dir):
    """Turret.AimTurret (Turret.cs ~697-720): traverse unlimited (360), elevation clamped to [minElevation, maxElevation]
    (localEuler.x in [-max, -min], Unity +X = muzzle down); onTarget = aim error + traverse/elevation error < 1 deg.
    Turret.FixedUpdate fires the station only after timeOnTarget > lockTime, i.e. only while onTarget."""
    x, y, z = target_dir
    trav = math.degrees(math.atan2(x, z))
    el = math.degrees(math.atan2(y, math.hypot(x, z)))
    el_c = max(T['minElevation'], min(T['maxElevation'], el))
    fwd = roty(rotx((0, 0, 1), -el_c), trav)
    return fwd, el_c, el, abs(el - el_c) < 1.0


def laser_on_target(fwd, target_dir, max_angle=30.0):
    """Laser.FixedUpdate: direction = RotateTowards(transform.forward, target, maxAngle); beam only within 1 deg."""
    a = ang(fwd, target_dir)
    return max(a - max_angle, 0) < 1.0


# 0.3.0: belly turret, upright mount (identity), elevation range below the turret plane (minElevation -90, maxElevation -2)
check('laser turret elevation limits are below the horizon (ventral turret)', T['minElevation'] <= -60 and T['maxElevation'] < 0,
      (T['minElevation'], T['maxElevation']))
ok_cases = []
for d in [(0, -0.2, 1), (1, -0.15, 0), (-0.5, -0.6, -1), (0, -1, 0.01), (0.3, -0.14, -1)]:
    fwd, elc, el, on = turret_aim(d)
    ok_cases.append(on and laser_on_target(fwd, d))
check('laser: turret on target + beam within the 30 deg Laser cone for threats below -2 deg, all bearings', all(ok_cases), ok_cases)
blocked = []
for d in [(0, 0.6, 1), (1, 0.2, 0), (0, 0.5, -1)]:
    fwd, elc, el, on = turret_aim(d)
    blocked.append(not on)
check('laser release path: threats above the turret plane never put the ventral turret on target (left to flares / jammer)',
      all(blocked), blocked)
check('laser on the belly: mount under fus_rear, el pivot below the fuselage bottom, behind the bomb bay',
      lt['mount']['parent'] == 'fus_rear' and lt['el']['pivot'][1] < -1.0 and lt['mount']['pivot'][2] < con['bay']['y'][0],
      (lt['mount']['parent'], lt['el']['pivot'], con['bay']['y']))

# ------------------------------------------------------------------ 3. side sticks (Cockpit.Joystick)
for s in con['controls']['sticks']:
    rng = s['drive']['range']
    top = (0, 1, 0)
    push = rotx(top, 1.0 * rng)
    right = rotz(top, -1.0 * rng)
    check(f"{s['name']}: push moves the top forward, right roll moves it right (CI-22 Joystick math)", push[2] > 0.1 and right[0] > 0.1,
          f'push {tuple(round(v, 3) for v in push)} right {tuple(round(v, 3) for v in right)}')
for lv in con['controls']['levers']:
    check(f"{lv['name']}: Cockpit.throttles rotation range > 0", lv['drive']['range'] > 0, lv['drive']['range'])

# ------------------------------------------------------------------ 4. hatches (Canopy hinge) and crew
for h in con['hatches']['hatches']:
    c0, c1 = h['probe_closed'], h['probe_open']
    moved = sub(c1, c0)
    outward = 'top' in h['hatch']['name'] or 'canopy' in h['hatch']['name']
    check(f"hatch {h['hatch']['name']}: opening moves it {'up' if outward else 'down'}", (moved[1] > 0.05) if outward else (moved[1] < -0.05), moved)
st = con['crew']['stations']
hn = {h['hatch']['name']: h for h in con['hatches']['hatches']}
check('crew of 2: pilot left, weapons officer right, each with its own jettison canopy panel above the seat',
      len(st) == 2 and st[0]['eye']['pivot'][0] < -0.2 and st[1]['eye']['pivot'][0] > 0.2 and
      [x['exit_hatch'] for x in st] == ['canopy_jettison_L', 'canopy_jettison_R'] and all(x['exit_hatch'] in hn for x in st),
      [(x['role'], x['exit_hatch']) for x in st])
# 0.3.1 kitbash: the seat is the stock EjectionSeat child of each crew figure (no seat object in the model); the jettison
# panel above each eye must be on that crew member's side and above the eye
ss = con['crew'].get('stock_seat', {})
check('stock ejection seat declared (mesh ejectionSeat + Seats, COIN/SFB offset in the figure), no custom seat objects',
      ss.get('mesh') == 'ejectionSeat' and ss.get('material') == 'Seats' and all(x.get('seat') is None for x in st)
      and not any(n.startswith(('cockpit_seat_', 'ejection_rail_', 'quadrant_throttle_')) for n in parts), ss)
for x in st:
    pc = hn[x['exit_hatch']]['probe_closed']
    e = x['eye']['pivot']
    check(f"{x['role']}: the canopy panel above the seat is on the ejection path (same side, above the eye)",
          (pc[0] * e[0] > 0) and pc[1] > e[1], (pc, e))
ct = con['controls']
check('controls: 2 stock sticks (sfb_joystick, range 12) + 1 throttle pivot (rotation range 52; 0.3.3: no stock mesh, our split lever child), all empties with identity frames',
      [s_['stock_mesh'] for s_ in ct['sticks']] == ['sfb_joystick'] * 2 and all(s_['drive']['range'] == 12.0 and s_['type'] == 'EMPTY' for s_ in ct['sticks'])
      and len(ct['levers']) == 1 and ct['levers'][0].get('stock_mesh') is None and ct['levers'][0]['drive']['range'] == 52.0
      and all(o['local_axes']['x'] == [1.0, 0.0, 0.0] and o['local_axes']['y'] == [0.0, 1.0, 0.0] for o in ct['sticks'] + ct['levers']),
      [(o['name'], o['type'], o['drive']['range']) for o in ct['sticks'] + ct['levers']])

# ------------------------------------------------------------------ 5. tail hook (TailHook.cs): reach and stow
th = con['tailhook']
L = th['length']
piv = th['pivot']
GROUND_Y = -2.588           # wheels-on-ground plane below the root (gear axles - radius; same gear as the B-25H)
ax = con['gear']['axles']
ground = min(ax['gear_main_L_wheel'][1] - con['gear']['main_wheel_r'], ax['gear_nose_wheel'][1] - con['gear']['nose_wheel_r'])
check('ground plane from the wheels matches the B-25H value (same gear)', abs(ground - GROUND_Y) < 0.03, f'{ground:.3f}')


def hook_end(angle):
    return add(piv, rotx((0, 0, -L), angle))


stow = th['stowed_up_deg']
deployed = -math.degrees(math.asin(min(1.0, (piv[1] - ground + 0.15) / L)))
e_st, e_dep = hook_end(stow), hook_end(deployed)
check('hook stowed: end tucked under the tail (above the ground by > 1.5 m)', e_st[1] - ground > 1.5, f'end {tuple(round(v, 3) for v in e_st)}')
check('hook deployed angle reaches 0.15 m below the deck in level attitude', abs(e_dep[1] - (ground - 0.15)) < 0.01 and deployed > -80,
      f'deployed {deployed:.1f} deg, end y {e_dep[1]:.3f}')


def hook_sequence(states):
    """TailHook.CheckDeployConditions every 1 s: deploy if 30 < radarAlt < 120 and speed < 100 and descending;
    retract when speed > 100 or speed < 2."""
    deployed_ = False
    log = []
    for alt, spd, vy in states:
        if 30 < alt < 120 and spd < 100 and vy < 0 and not deployed_:
            deployed_ = True
        if (spd > 100 or spd < 2) and deployed_:
            deployed_ = False
        log.append(deployed_)
    return log


seq = hook_sequence([(400, 120, -3), (100, 75, -4), (40, 62, -3), (0, 55, 0), (0, 20, 0), (0, 1, 0)])
check('hook deploys on approach (alt 30-120 m, < 100 m/s), stays down on the roll-out, retracts at < 2 m/s', seq == [False, True, True, True, True, False], seq)
seq2 = hook_sequence([(100, 75, -4), (150, 110, 5)])
check('hook release path: bolter/go-around above 100 m/s retracts it', seq2 == [True, False], seq2)

# ------------------------------------------------------------------ 6. numbers in GA25XBuild.cs (masses, power, fuel)
if not os.path.exists(CS):
    check('GA25XBuild.cs present', False, CS)
else:
    src = open(CS, encoding='utf-8').read()
    consts = {m.group(1): float(m.group(2).rstrip('f')) for m in re.finditer(r'const float (\w+) = ([-0-9.e]+f?);', src)}
    ints = {m.group(1): int(m.group(2)) for m in re.finditer(r'const int (\w+) = (\d+);', src)}
    specs = re.findall(r'new PartSpec\("(\w+)"(?:\s*\+\s*s)?,\s*[^,]+,\s*[^,]+,\s*[^,]+,\s*([0-9.]+)f?,\s*([\w.]+?)f?,', src)
    per_side = re.findall(r'new PartSpec\("(\w+)" \+ s,\s*[^,]+,\s*[^,]+,\s*[^,]+,\s*([0-9.]+)f?,\s*([\w.]+?)f?,', src)   # area may be a const (ElevatorArea)
    single = [s for s in specs if s[0] not in {p[0] for p in per_side}]
    mass = sum(float(m) for _, m, _ in single) + 2 * sum(float(m) for _, m, _ in per_side)
    wingish = ('wing_', 'flap_', 'aileron_', 'nacelle_')
    fa = lambda a: consts[a] if a in consts else float(a)
    area = sum(fa(a) for n, _, a in single if n == 'GA25X') + 2 * sum(fa(a) for n, _, a in per_side if n.startswith(wingish))
    check('part masses sum to the 9,600 kg empty weight (spec)', abs(mass - 9600) < 1, f'{mass:.0f} kg from {len(single)} + 2x{len(per_side)} parts')
    check('wing area ~57.4 m^2 (spec; wing panels, flaps, ailerons, nacelles + body)', abs(area - 57.4) < 1.0, f'{area:.1f} m^2')
    fuel = consts.get('FuelKg', 0)
    check('internal fuel 3,800 kg (spec)', abs(fuel - 3800) < 1, fuel)
    mtow = 9600 + fuel
    check('empty + full fuel leaves >= 4,000 kg payload under the 17,500 kg MTOW', 17500 - mtow >= 4000, f'{17500 - mtow:.0f} kg')
    # PowerSupply.FixedUpdate: charge += chargePerRPM * engineRPM * dt per engine; DrawPower(kW) * supplyAtCharge(charge/max)
    cpr, rpm, cap = consts.get('PowerChargePerRPM', 0), consts.get('TurbineMaxRPM', 0), consts.get('PowerMaxCharge', 0)
    gen_kw = cpr * rpm
    check('each motor-generator charges 900 kW at full rpm (spec)', abs(gen_kw - 900) < 1, f'{cpr} kW/rpm x {rpm} rpm = {gen_kw:.0f} kW')
    check('capacitor 1,500 kJ (spec)', abs(cap - 1500) < 1, cap)

    def sim_power(engines_rpm, draw_kw, seconds, charge0, dt=0.02):
        ch = charge0
        starved = 0.0
        global first_starve
        first_starve = None
        for _ in range(int(seconds / dt)):
            for r in engines_rpm:
                ch += cpr * r * dt
            ch = min(ch, cap)
            supply = min(1.0, (ch / cap) / 0.7) if ch > 0 else 0.0     # stock supplyAtCharge: 0 at 0, ~1 from 0.7 (EW1 curve)
            got = draw_kw * supply
            ch = max(0.0, ch - got * dt)
            if got < draw_kw * 0.99:
                starved += dt
                if first_starve is None:
                    first_starve = _ * dt
        return ch, starved
    laser, jam = consts.get('LaserPowerKW', 0), consts.get('JammerPowerKW', 0)
    ch, st_ = sim_power([rpm, rpm], laser + jam, 60, cap)
    check('normal: laser (120 kW) + jammer (50 kW) run continuously on two engines', st_ == 0 and ch > 0.99 * cap, f'charge {ch:.0f} kJ, starved {st_:.1f} s')
    ch, st_ = sim_power([0.6 * rpm], laser + jam, 60, cap)
    check('failure: one engine out at 60 % rpm still carries laser + jammer', st_ == 0, f'charge {ch:.0f} kJ, starved {st_:.1f} s')
    ch, st_ = sim_power([0, 0], laser + jam, 30, cap)
    check('failure: both engines out -> the capacitor alone gives full laser + jammer power for > 2 s (stock supply curve), then fades to 0',
          first_starve is not None and first_starve > 2.0 and ch < 0.02 * cap, f'full power for {first_starve:.1f} s, charge {ch:.1f} kJ at 30 s')
    t_ready = (0.6 * cap) / (2 * cpr * 0.25 * rpm)
    check('release: from empty, 2 engines at 25 % rpm reach the AI energy threshold (60 % charge) in < 5 s', t_ready < 5, f'{t_ready:.1f} s')
    check('flares 96 (spec)', ints.get('FlareCount') == 96, ints.get('FlareCount'))
    check('76 mm: 96 rounds; 20 mm: 250 per gun (spec)', ints.get('CannonRounds') == 96 and ints.get('Gun20Rounds') == 250,
          (ints.get('CannonRounds'), ints.get('Gun20Rounds')))
    # stock mounts named in the build exist in the user's install (Blueprinter placeholders)
    mounts = sorted(set(re.findall(r'(?<![A-Za-z])Mount\("([\w/]+)"\)', src)))
    if os.path.isdir(DNS):
        miss = [m for m in mounts if not os.path.exists(os.path.join(DNS, m + '_PLACEHOLDER.asset'))]
        check('every stock WeaponMount the build names exists in the user install (_donotship)', not miss, miss or f'{len(mounts)} mounts')
    else:
        print('SKIP stock mount presence (no Blueprinter project on this machine)')

# ------------------------------------------------------------------ 7. bay geometry vs measured stock store lengths
bay = con['bay']
bay_len = bay['y'][1] - bay['y'][0]
check('bomb bay expanded vs the B-25H (2.65 m x 1.20 m)', bay_len > 2.65 and bay['half_x'] > 0.60, f'{bay_len:.2f} m x {2 * bay["half_x"]:.2f} m')
hp = {h['name']: h['pivot'] for h in con['hardpoints']}
racks_ok = abs(hp['hp_bay_L'][0] + 0.33) < 1e-3 and abs(hp['hp_bay_R'][0] - 0.33) < 1e-3
# outer edge of a stock x2 internal mount (bombs at +-0.175..0.18 m, radius 0.143 m; measured, see design doc)
edge = 0.33 + 0.18 + 0.143
check('paired bay racks: two stock x2 mounts side by side fit the bay width', racks_ok and edge <= bay['half_x'], f'edge {edge:.3f} <= {bay["half_x"]}')

# ------------------------------------------------------------------ 8. visual pass (2026-10-31): 4 pylons per wing, textures
added = {h['name']: h['pivot'] for h in con.get('hardpoints_added', [])}
check('4 pylons per wing: root + mid hardpoints present (contract hardpoints_added)', sorted(added) == ['hp_mid_L', 'hp_mid_R', 'hp_root_L', 'hp_root_R'],
      sorted(added))
allhp = dict(hp, **added)
xs = {k: abs(v[0]) for k, v in allhp.items()}
order = [xs.get(f'hp_{k}_R', 0) for k in ('root', 'inner', 'mid', 'outer')]
check('pylon order root < inner < mid < outer, mirrored L/R', order == sorted(order) and all(abs(xs.get(f'hp_{k}_L', -1) - xs.get(f'hp_{k}_R', -2)) < 1e-3
      for k in ('root', 'inner', 'mid', 'outer')), [round(v, 2) for v in order])
# root stays between the open bomb-bay doors (|x| 0.66 + door) and the inboard gear door (|x| 2.30): widest option half 0.415
check('root pylon: widest option (AGR-24 x12, half 0.415 m) clears the bay doors and the gear door', 0.72 < order[0] - 0.415 and order[0] + 0.415 < 2.30,
      f'{order[0] - 0.415:.3f} .. {order[0] + 0.415:.3f}')
sc_path = os.path.join(OUT, 'ga25x_stores_check.json')
if os.path.exists(sc_path):
    sc = json.load(open(sc_path))
    check('store clash test detects a known overlap (gear wheel, prop disc positive controls)', sc.get('selftest_detects_overlap') is True)
    check('store proxies: 0 clashes with airframe / gear / flaps / doors / prop discs / neighbours', sc['ok'], sc['clashes'][:4])
    check('neighbouring pylon stores keep >= 0.10 m lateral gap (all option pairs)', sc['min_neighbour_gap_m'] >= 0.10, sc['min_neighbour_gap_m'])
    # failure path: the same box test must flag an overlap when two widest stores sit 0.70 m apart (the rejected spacing)
    a, b = sc['mounts']['Rocket2_4Podx3'], sc['mounts']['AGM1_triple']
    gap = (0.70 + b['min'][0]) - a['max'][0]
    check('failure path: 0.70 m spacing with AGR-24 x12 next to AGM-48 x3 is detected as a clash', gap <= 0, f'gap {gap:.3f}')
else:
    check('store clearance result present (check_stores_ga25x.py)', False, sc_path)
TEX = os.path.join(ROOT, 'assets', 'textures_ga25x')
if '--textures' in sys.argv:
    TEX = os.path.abspath(sys.argv[sys.argv.index('--textures') + 1])
lj = os.path.join(TEX, 'ga25x_liveries.json')
if os.path.exists(lj):
    lv = json.load(open(lj))
    facs = sorted(v['faction'] for v in lv.values())
    check('liveries: 5 schemes, 3 PALA (incl. PALA Desert Camo) + 2 BDF, one default, textures present', len(lv) == 5 and facs == ['BDF', 'BDF', 'PALA', 'PALA', 'PALA'] and
          any(v['name'] == 'PALA Desert Camo' for v in lv.values()) and
          sum(bool(v.get('default')) for v in lv.values()) == 1 and all(os.path.exists(os.path.join(TEX, v['texture'])) for v in lv.values()),
          {k: v['name'] for k, v in lv.items()})
    check('no "captured" BDF scheme (user: BDF flies its standard camouflage)', not any('captur' in (k + v['name']).lower() for k, v in lv.items()), list(lv))
    check('own grey interior / prop tiles and gauge atlas present (TextureSource prefers them); 0.3.1: no cockpit crosshatch tile',
          all(os.path.exists(os.path.join(TEX, f'ga25x_{n}.png')) for n in ('interior_b', 'prop_b', 'gauges')))
else:
    check('livery table present', False, lj)

# ------------------------------------------------------------------ 9. 0.3.0 model pass: lights, displays, offline geometry checks
fl = con.get('lights', {}).get('formation', [])
want = {}
for L in 'LR':
    want.update({f'slimelight_nose_{L}': 'fus_cockpit', f'slimelight_tip_{L}': f'wing_tip_{L}', f'slimelight_fin_{L}': f'fin_{L}',
                 f'slimelight_nacelle_{L}': f'nacelle_{L}'})
got = {x['name']: x['part'] for x in fl}
check('8 formation/gear-down strips (slimelight_*), each a child of the part it sits on', got == want, got)
check('strips mirrored L/R (|x| equal, same height)', all(
    abs(abs(a['pivot'][0]) - abs(b['pivot'][0])) < 1e-3 and abs(a['pivot'][1] - b['pivot'][1]) < 1e-3
    for a in fl for b in fl if a['name'].endswith('_L') and b['name'] == a['name'][:-1] + 'R'))
md = {m['name']: m for m in con['mfds']}
W, H = md['mfd_center']['size_m']
g = 0.004
panels = [(0.802, 0.983, 0.718, 0.979), (0.801, 0.985, 0.390, 0.697), (0.789, 0.983, 0.025, 0.341)]   # GA25XBuild.TacScreenMesh
sum_inv = sum(1 / ((v1 - v0) * 512 / ((u1 - u0) * 1024)) for u0, u1, v0, v1 in panels)
ws = (H - 4 * g) / sum_inv
wm = W - ws - 3 * g
hm = min(H - 2 * g, wm / (0.79 * 1024 / 512))
check('main tac display fills its height (TacScreenMesh: map pane >= 95 % of H, no letterbox)', hm >= 0.95 * (H - 2 * g),
      f'{W:.3f} x {H:.3f} m: map {wm:.3f} x {hm:.3f}')
check('one wide display per crew (pilot tac, WSO target camera)', md['mfd_center']['role'] == 'tac' and md['mfd_right']['role'] == 'targetcam'
      and md['mfd_center']['pivot'][0] < -0.1 and md['mfd_right']['pivot'][0] > 0.1)
gc = os.path.join(OUT, 'ga25x_v030_check.json')
if os.path.exists(gc):
    v3 = json.load(open(gc))
    for k, v in v3['checks'].items():
        check('geometry: ' + k, v['ok'], v.get('detail', ''))
else:
    check('0.3.0 geometry check result present (check_v030_ga25x.py)', False, gc)

fails = [r for r in res if not r[1]]
print(f'\n{len(res) - len(fails)}/{len(res)} PASS')
sys.exit(1 if fails else 0)
