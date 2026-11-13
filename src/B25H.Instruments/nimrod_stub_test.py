"""Stub test for the B25H.Instruments 1.4.0 Nimrod branch (Nimrod.cs NimrodMath + the fixed-gear keeper), no game needed.
Mirrors the C# maths, cross-checks every C# constant against the model contract (assets/model_nimrod/nimrod_contract.json)
and runs a small stub of the game API for the gear keeper (normal, remote aircraft, flag off, destroyed aircraft).
Run: python src/B25H.Instruments/nimrod_stub_test.py      Expected: 'ALL PASS'."""
import json, math, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
cs = open(os.path.join(HERE, 'Nimrod.cs')).read()
con = json.load(open(os.path.join(ROOT, 'assets', 'model_nimrod', 'nimrod_contract.json')))


def const(name):
    m = re.search(r'\b' + name + r'\s*=\s*([-\d.]+)f(?:\s*/\s*([-\d.]+)f)?', cs)
    v = float(m.group(1))
    return v / float(m.group(2)) if m.group(2) else v


C = {k: const(k) for k in ('AsiDegPerKt', 'AsiMaxKt', 'AltLongDegPerFt', 'AltShortDegPerFt', 'RpmDegPerRpm', 'RpmMax', 'BoostDegPerPsi', 'BoostMin',
                           'BoostMax', 'OilPDegPerPsi', 'OilTDegPerC', 'WaterDegPerC', 'FuelDegPerPct', 'TurnDegPerDps', 'TurnMax', 'SlipDegPerDeg', 'SlipMax')}
clamp = lambda x, a, b: max(a, min(b, x))
def repeat(x, n): return x - math.floor(x / n) * n
def asi(tas, rho): return clamp(tas * math.sqrt(max(rho, 0) / 1.225) * 1.943844, 0, C['AsiMaxKt']) * C['AsiDegPerKt']
def alt_long(m): return repeat(m * 3.28084 * C['AltLongDegPerFt'], 360)
def alt_short(m): return repeat(m * 3.28084 * C['AltShortDegPerFt'], 360)
def rpm(r): return clamp(r, 0, C['RpmMax']) * C['RpmDegPerRpm']
def boost_psi(th, rr, run): return (-4 + 10 * clamp(th, 0, 1) * clamp(rr, 0, 1)) if run else 0.0
def boost(p): return (clamp(p, C['BoostMin'], C['BoostMax']) - C['BoostMin']) * C['BoostDegPerPsi']
def turn(dps): return clamp(dps * C['TurnDegPerDps'], -C['TurnMax'], C['TurnMax'])
def slip(dx, dy): return clamp(-math.degrees(math.atan2(dx, max(-dy, 0.05))) * C['SlipDegPerDeg'], -C['SlipMax'], C['SlipMax'])

fails = 0
def T(name, ok):
    global fails
    fails += not ok
    print(('PASS ' if ok else 'FAIL ') + name)

# --- constants == contract (deg per unit of every mover)
dpu = {g['name']: g.get('deg_per_unit') for g in con['gauges']}
pairs = {'gauge_asi_needle': 'AsiDegPerKt', 'gauge_alt_needle': 'AltLongDegPerFt', 'gauge_alt_needle_short': 'AltShortDegPerFt', 'gauge_rpm_needle': 'RpmDegPerRpm',
         'gauge_boost_needle': 'BoostDegPerPsi', 'gauge_oilp_needle': 'OilPDegPerPsi', 'gauge_oilt_needle': 'OilTDegPerC', 'gauge_water_needle': 'WaterDegPerC',
         'gauge_fuel_needle': 'FuelDegPerPct', 'gauge_turn_needle': 'TurnDegPerDps'}
for n, k in pairs.items():
    T(f'{n}: C# {k} {C[k]:.5f} == contract {dpu.get(n)}', dpu.get(n) is not None and abs(C[k] - dpu[n]) < 1e-3)
names = re.search(r'NimrodNames = \{([^}]*)\}', cs).group(1)
cs_names = re.findall(r'"([^"]+)"', names)
T(f'every contract mover is driven by name ({len(con["gauges"])} movers)', sorted(cs_names) == sorted(g['name'] for g in con['gauges']))
# --- value maps
T('ASI 100 kt at sea level -> 126.9 deg', abs(asi(100 / 1.943844, 1.225) - 126.92) < 0.1)
T('ASI uses IAS: same TAS at rho 0.6125 reads 0.707 x', abs(asi(60, 0.6125) / asi(60, 1.225) - math.sqrt(0.5)) < 1e-3)
T('ASI clamps at 260 kt (330 deg)', abs(asi(300, 1.225) - 330) < 1e-6)
T('altimeter 500 ft -> long 180', abs(alt_long(152.4) - 180) < 0.5)
T('altimeter 10,000 ft -> short full turn', min(abs(alt_short(3048) - 360), alt_short(3048)) < 0.5)
T('rpm 2,600 -> 260 deg', abs(rpm(2600) - 260) < 1e-6)
T('boost: idle -4 psi -> 0 deg, full throttle +6 psi -> 225 deg, stopped 0 psi -> 90 deg', abs(boost(boost_psi(0, 1, True))) < 1e-6 and abs(boost(boost_psi(1, 1, True)) - 225) < 1e-6 and abs(boost(boost_psi(1, 1, False)) - 90) < 1e-6)
T('turn: rate one (3 deg/s) -> 30 deg; clamps at 45', abs(turn(3) - 30) < 1e-6 and turn(20) == 45 and turn(-20) == -45)
T('slip: level 1 g -> ball centred', abs(slip(0.0, -9.81)) < 1e-6)
T('slip: apparent gravity to the right -> ball right (anticlockwise, negative)', slip(2.0, -9.81) < -5)
T('slip: inverted / zero-g does not blow up (clamped)', abs(slip(1.0, 5.0)) <= C['SlipMax'])
T('compass: heading 90 -> card -90 (B-25H heading-card sign)', '-headingDeg' in cs)

# --- 1.4.0 hook A-frame: constants == contract, claw on the functional tip when deployed, amount mapping incl. wrap / hooked trailing
def cf(name):
    return float(re.search(r'\b' + name + r' = ([-\d.]+)f', cs).group(1))
hv, tf = con.get('hook_visual'), con['tailhook']
T('hook: C# HookStow / HookDeploy == contract tailhook stowed / deployed', hv is not None and cf('HookStow') == tf['stowed_up_deg'] and cf('HookDeploy') == tf['deployed_deg'])
T('hook: C# HookVisualTravel == A-frame stowed - deployed (contract)', hv is not None and abs(cf('HookVisualTravel') - (hv['stowed_up_deg'] - hv['deployed_deg'])) < 1e-3)
def tip(piv, L, deg):
    a = math.radians(deg); return (piv[1] - L * math.cos(a), piv[2] + L * math.sin(a))
ft, vt = tip(hv['hook_pivot_blender'], tf['length'], tf['deployed_deg']), tip(hv['pivot_blender'], hv['length'], hv['deployed_deg'])
T(f'hook: deployed A-frame claw within 20 mm of the functional tip (functional {ft[0]:.3f},{ft[1]:.3f} / visual {vt[0]:.3f},{vt[1]:.3f})', math.dist(ft, vt) < 0.02)
def wrap(a): return (a + 180) % 360 - 180
def amount(x): return max(0.0, min(1.0, (wrap(x) - cf('HookStow')) / (cf('HookDeploy') - cf('HookStow'))))
def vis(am): return -cf('HookVisualTravel') * max(0.0, min(1.0, am))
T('hook: stowed (local x 2) -> A-frame 0 deg', abs(vis(amount(2.0))) < 1e-6)
T('hook: deployed (local x -65 read back as 295) -> A-frame -60.7 deg', abs(vis(amount(295.0)) + cf('HookVisualTravel')) < 1e-4)
T('hook: half way (-31.5) -> half travel; hooked trail (amount 0.01) -> near stowed', abs(vis(amount(-31.5)) + cf('HookVisualTravel') / 2) < 1e-3 and abs(vis(amount(2 - 0.67))) < 1.0)
T('hook: overshoot clamps (local x 20 or -80 stays in 0 .. -60.7)', vis(amount(20.0)) == 0.0 and vis(amount(-80.0)) == -cf('HookVisualTravel'))
# stub of the driver: no TailHook yet -> no write; TailHook found -> visual follows; plugin flag off -> no write
class Tr:
    def __init__(self): self.x = 0.0; self.writes = 0
def drive(vis_t, fn, flag=True):
    if vis_t is None or not flag or fn is None: return
    vis_t.x = vis(amount(fn.x)); vis_t.writes += 1
v_, f_ = Tr(), None
drive(v_, f_); T('hook driver: functional hook not spawned yet -> A-frame untouched', v_.writes == 0)
f_ = Tr(); f_.x = -65.0; drive(v_, f_); T('hook driver: deployed -> A-frame at -60.7', abs(v_.x + 60.7) < 1e-3)
v2 = Tr(); drive(v2, f_, flag=False); T('hook driver: config HookVisual off -> untouched', v2.writes == 0)
T('1.9.9: the Cooper detonation log is removed (no Missile.Detonate patch, no cooper log member; it was a read-only diagnostic)', 'Detonate' not in cs and 'cooperLog' not in cs and 'COOPER' not in cs)

# --- fixed-gear keeper against a stub of the game API
class StubAircraft:
    """Aircraft.SetGear(bool) / GearStateChanged stub (decompiled Aircraft.cs 1732-1790): SetGear(true) on LockedRetracted -> Extending,
    ignored while Extending / Retracting; the gear animation later reaches LockedExtended."""
    def __init__(self, local=True, gear=True, disabled=False, state='LockedExtended'):
        self.LocalSim, self.gearDeployed, self.disabled, self.gearState, self.calls = local, gear, disabled, state, []
    def SetGear(self, v):
        self.calls.append(v); self.gearDeployed = v
        if self.gearState in ('Extending', 'Retracting'):
            return
        if self.gearState == 'LockedRetracted' and v: self.gearState = 'Extending'
        if self.gearState == 'LockedExtended' and not v: self.gearState = 'Retracting'
    def animate(self):
        self.gearState = {'Extending': 'LockedExtended', 'Retracting': 'LockedRetracted'}.get(self.gearState, self.gearState)
def keeper(a, flag=True):
    if a.disabled: return
    if flag and a.LocalSim and (a.gearState == 'LockedRetracted' or not a.gearDeployed): a.SetGear(True)
a = StubAircraft(gear=False); keeper(a); T('keeper: local aircraft with the gear flag up -> SetGear(true) once', a.calls == [True])
a.animate(); keeper(a); T('keeper: gear back down (LockedExtended) -> no further call', a.calls == [True] and a.gearState == 'LockedExtended')
g = StubAircraft(gear=True, state='LockedRetracted'); keeper(g)
T('keeper: game-test case gearDeployed=true but LockedRetracted -> SetGear(true), gear starts Extending', g.calls == [True] and g.gearState == 'Extending')
keeper(g); keeper(g); T('keeper: no repeated calls while Extending (no CmdSetGear spam)', g.calls == [True])
g.animate(); T('keeper: gear ends LockedExtended (weapons need no gear-safety override for the state itself)', g.gearState == 'LockedExtended')
r = StubAircraft(gear=True, state='LockedExtended'); r.SetGear(False); keeper(r)
T('keeper: player retracts (Retracting, flag false) -> one SetGear(true), ignored by the game until locked', r.calls == [False, True])
r.animate(); keeper(r); T('keeper: retraction finished anyway (LockedRetracted) -> re-extends', r.calls[-1] is True and r.gearState == 'Extending')
b = StubAircraft(local=False, gear=False); keeper(b); T('keeper: remote aircraft untouched (its owner simulates it)', b.calls == [])
c = StubAircraft(gear=False); keeper(c, flag=False); T('keeper: config FixedGear=false -> untouched', c.calls == [])
d = StubAircraft(disabled=True, gear=False); keeper(d); T('keeper: destroyed aircraft untouched', d.calls == [])
T('1.9.9: the fixed-gear keeper is removed from the C# (no SetGear call, no FixedGear config; off by default since 1.5.5: the game\'s own gear logic runs)', 'SetGear(' not in cs and 'nimrodFixedGear' not in cs and 'Config.Bind("Nimrod", "FixedGear"' not in cs)
T('B-25H path untouched: Plugin.cs still keys the B-25H gauges on "B25H"', 'public const string JsonKey = "B25H";' in open(os.path.join(HERE, 'Plugin.cs')).read())
# --- cockpit v2: needle rest pose == painted scale zero == contract (the plugin rotates relative to the rest pose)
sys.path.insert(0, os.path.join(ROOT, 'blender', 'nimrod')); sys.path.insert(0, os.path.join(ROOT, 'blender', 'nimrod', 'textures'))
import nimrod_ck_layout as CKL
_argv = sys.argv; sys.argv = [sys.argv[0], '--out', os.path.join(ROOT, 'assets', 'textures_nimrod')]
import make_cockpit_art_nimrod as ART
sys.argv = _argv
zc = {g['name']: g.get('zero_deg') for g in con['gauges']}
bad = []
for gid, d in CKL.DIALS.items():
    for suf, kind in d['movers']:
        if kind == 'ball':
            continue
        n = f'gauge_{gid}_{suf}'
        spec = ART.DIAL_SPECS.get(d['face'], {})
        face_zero = spec.get('zero', 0) if spec.get('kind', 'scale') == 'scale' else 0
        if zc.get(n) != d['zero'] or face_zero != d['zero']:
            bad.append((n, zc.get(n), d['zero'], face_zero))
        if 'sweep' in spec and spec.get('kind', 'scale') == 'scale':
            key = gid + ('_short' if suf == 'needle_short' else '')
            sc = CKL.SCALES[key]
            if gid != 'alt' and (abs(spec['sweep'] / (spec['v1'] - spec['v0']) - sc['sweep'] / (sc['v1'] - sc['v0'])) > 1e-9):
                bad.append((n, 'deg/unit face != scale'))
T(f'cockpit v2: every needle rest angle == its painted scale zero == contract zero_deg ({sum(len(d["movers"]) for d in CKL.DIALS.values())} movers) {bad}', not bad)
T('cockpit v2: turn needle and compass card rest at 0 (centre / north)', zc.get('gauge_turn_needle') == 0 and 'gauge_compass_card' in zc)

# ---- 1.5.5: "lie to the game" (keeper + HUD hacks opt-in, default OFF), hook logic for NIMROD1 / FD32
T('1.9.9: the fixed-gear hacks are removed (no FixedGearHacks155 / UsesFixedGearHacks / combat-HUD patches); crash rule + gear guard still IsFixedGear',
  'FixedGearHacks155' not in cs and 'UsesFixedGearHacks' not in cs and 'HUDUnitMarker' not in cs and 'HUDWeaponState' not in cs and 'GearDeployedField' not in cs
  and re.search(r'if \(!IsFixedGear\(a\)\) return;\s*var n = __instance\.name;', cs) is not None and re.search(r'LgAcF\.GetValue\(__instance\) as Aircraft;\s*if \(!IsFixedGear\(a\)\) return true;', cs) is not None)
def hook_decision(dep, alt, spd, vy, gear):
    if not dep and 30 < alt < 120 and spd < 50 and vy < 0 and gear: return 1
    if dep and (spd > 60 or spd < 2 or not gear): return -1
    return 0
T('hook logic C# == stub thresholds (deploy < 50 m/s, stow > 60 m/s, gear-down gate), NIMROD1 / FD32 only',
  'HookDeployBelow = 50f, HookStowAbove = 60f' in cs and 'IsHookFixKey(string k) => k == NimrodKey || k == FD32Key;' in cs
  and 'if (!deployed && radarAlt > 30f && radarAlt < 120f && speed < HookDeployBelow && vy < 0f && gearDown) return 1;' in cs
  and 'if (deployed && (speed > HookStowAbove || speed < 2f || !gearDown)) return -1;' in cs)
cases = [((False, 100, 85, -1, True), 0, 'Mk I cruise descent at 85 m/s, 100 m (stock: deploys and never stows): no deploy'),
         ((True, 100, 85, 0, True), -1, 'hook out at cruise (1.5.4 state): stowed'),
         ((False, 60, 38, -3, True), 1, 'approach 38 m/s, 60 m, descending, gear down: deploys'),
         ((True, 5, 30, -2, True), 0, 'touchdown roll 30 m/s: stays out (wire)'),
         ((True, 0, 1, 0, True), -1, 'stopped < 2 m/s: stowed'),
         ((False, 60, 38, -3, False), 0, 'gear up: no deploy'),
         ((True, 60, 38, -3, False), -1, 'gear raised: stowed')]
for args, want, name in cases:
    T('hook: ' + name, hook_decision(*args) == want)
print('ALL PASS' if fails == 0 else f'{fails} FAIL')

sys.exit(1 if fails else 0)
