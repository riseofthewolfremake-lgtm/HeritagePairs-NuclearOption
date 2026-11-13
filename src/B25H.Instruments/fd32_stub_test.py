"""Stub test for B25H.Instruments 1.5.1 (FD-32 v2), no game needed.

1.5.1: the FD-32 v2 RETRACTS its gear like every stock aircraft, so it leaves every fixed-gear path of Nimrod.cs (keeper, combat-HUD
fix, crash rule, gear guard, hook A-frame driver) and gets the GA-25X BOOST / IDLE throttle-gauge relabel (its boost is the same
JetNozzle afterburner from throttle 0.90).
Checks: (1) the C# routing: IsFixedGearKey is NIMROD1 only, every fixed-gear site still goes through IsFixedGear (so NIMROD1 keeps the
exact 1.5.0 behaviour), the NIMROD1 hook mapping is unchanged; (2) BoostLabels relabels GA25X (as before) and FD32 only; (3) a stub of the
game API for the keeper / crash rule / gear guard / relabel on FD32, NIMROD1, GA25X, another aircraft, a remote and a destroyed aircraft,
and an uninitialised gauge (failure and release paths).
Run: python src/B25H.Instruments/fd32_stub_test.py      Expected: 'ALL PASS'."""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
cs = open(os.path.join(HERE, 'Nimrod.cs'), encoding='utf-8').read()
plug = open(os.path.join(HERE, 'Plugin.cs'), encoding='utf-8').read()
fails = 0


def T(name, ok):
    global fails
    fails += not ok
    print(('PASS ' if ok else 'FAIL ') + name)


def cf(name):
    return float(re.search(r'\b' + name + r' = ([-\d.]+)f', cs).group(1))


# ---- (1) routing in the C#
T('plugin version 1.5.1+ (1.5.3: + FD32Tac.cs; 1.6.0: + B17G.cs)', re.search(r'BepInPlugin\("b25h.instruments", "(B-25H|Heritage Pairs) Instruments", "1\.(5\.[135]|6\.0|8\.([04679]|1[0125])|9.([02789]|1[01]))"\)', plug) is not None)
T('IsFixedGearKey is NIMROD1 only (FD32 retracts in v2)', re.search(r'IsFixedGearKey\(string k\) => k == NimrodKey;', cs) is not None
  and not re.search(r'IsFixedGearKey\(string k\) =>[^\n]*FD32Key', cs))
T('IsFixedGear(a) = definition key through IsFixedGearKey', 'IsFixedGear(Aircraft a) => a != null && a.definition != null && IsFixedGearKey(a.definition.jsonKey)' in cs)
for site, pat in (('crash rule', r'if \(!IsFixedGear\(a\)\) return;\s*var n = __instance\.name;'),
                  ('gear guard', r'var a = LgAcF\.GetValue\(__instance\) as Aircraft;\s*if \(!IsFixedGear\(a\)\) return true;'),
                  ('keeper / hook scan', r'!IsFixedGearKey\(a\.definition\.jsonKey\)')):
    T(f'{site} still routed through IsFixedGear (NIMROD1 unchanged, FD32 now excluded)', re.search(pat, cs) is not None)
T('no other FD32 reference on a fixed-gear path (FD32Key declared + the 1.5.5 hook-logic key only)', cs.count('FD32Key') == 2 and 'IsHookFixKey(string k) => k == NimrodKey || k == FD32Key;' in cs)
T('1.9.9: the HUD fixed-gear patches and the Cooper log are removed (they were the only other fixed-gear / NIMROD1-only sites); needle attach rule unchanged',
  'UsesFixedGearHacks' not in cs and 'NIMROD1_cooper' not in cs and 'if (g.t.Count == 0 && a.definition.jsonKey == NimrodKey)' in cs)
STOW, DEP = cf('HookStow'), cf('HookDeploy')
T('NIMROD1 hook constants unchanged (stow 2, deploy -65)', STOW == 2.0 and DEP == -65.0)

# ---- (2) BOOST labels
T('BoostJsonKey still "GA25X"; FD32 added through IsBoostKey', 'BoostJsonKey = "GA25X";' in plug and 'BoostJsonKeyFD32 = "FD32";' in plug
  and 'IsBoostKey(string k) => k == BoostJsonKey || k == BoostJsonKeyFD32;' in plug and 'if (!IsBoostKey(ac.definition.jsonKey)) continue;' in plug)
T('relabel texts unchanged (AFTERBURNER -> "BOOST ", AIRBRAKE -> "IDLE"), failure disables for the session',
  'f.SetValue(r, "BOOST ")' in plug and 'f.SetValue(r, "IDLE")' in plug and 'boostLabelsBroken = true' in plug)


# ---- (3) game-API stub
class Def:
    def __init__(s, k): s.jsonKey = k
class Ac:
    def __init__(s, k, local=True):
        s.definition = Def(k) if k else None; s.LocalSim = local; s.gearState = 'LockedRetracted'; s.gearDeployed = False; s.sets = 0; s.disabled = False
    def SetGear(s, down): s.sets += 1; s.gearState = 'Extending'; s.gearDeployed = True
def is_key(k): return k == 'NIMROD1'
def fixed(a): return a is not None and a.definition is not None and is_key(a.definition.jsonKey)
def keeper(a, flag=True):
    if a is None or a.disabled: return
    if flag and fixed(a) and a.LocalSim and (a.gearState == 'LockedRetracted' or not a.gearDeployed): a.SetGear(True)
for k, exp in (('FD32', 0), ('NIMROD1', 1), ('GA25X', 0), ('COIN', 0), (None, 0)):
    a = Ac(k); keeper(a); keeper(a)
    T(f'keeper {k}: {exp} SetGear over two frames (FD32 retracts freely)', a.sets == exp)
r = Ac('NIMROD1', local=False); keeper(r); T('keeper: remote NIMROD1 untouched', r.sets == 0)
dead = Ac('NIMROD1'); dead.disabled = True; keeper(dead); T('keeper: destroyed aircraft untouched', dead.sets == 0)
def crash(a, part, dmg, root_name):
    if dmg < 100 or not fixed(a): return False
    return part == root_name or part == 'fus_engine'
T('crash rule: NIMROD1 root 150 -> break (as 1.5.0); FD32 root 150 / fus_engine 120 -> stock (no rule)',
  crash(Ac('NIMROD1'), 'NIMROD1', 150, 'NIMROD1') and not crash(Ac('FD32'), 'FD32', 150, 'FD32') and not crash(Ac('FD32'), 'fus_engine', 120, 'FD32'))
def guard(a, crash_recent=False, detached=False, vy=0.0):
    if not fixed(a): return True
    return crash_recent or detached or abs(vy) > cf('GuardCrashVy')
T('gear guard: NIMROD1 landing break (vy 4) blocked, vy 12 allowed; FD32 / GA25X untouched (stock break)',
  not guard(Ac('NIMROD1'), vy=4) and guard(Ac('NIMROD1'), vy=12) and guard(Ac('FD32'), vy=4) and guard(Ac('GA25X'), vy=4))
def hud_gear(a, gear): return False if (gear and fixed(a)) else gear
T('combat HUD: FD32 with the gear down keeps the stock gear-down state (weapons safe until gear up); NIMROD1 forced up as before',
  hud_gear(Ac('FD32'), True) is True and hud_gear(Ac('NIMROD1'), True) is False and hud_gear(Ac('FD32'), False) is False)

def relabel(gauge, seen):
    """stub of BoostLabels: returns renamed count, None if skipped"""
    if gauge['id'] in seen: return None
    ac = gauge['ac']
    if ac is None or ac.definition is None: return None          # not initialised: retry next scan (not marked seen)
    seen.add(gauge['id'])
    if ac.definition.jsonKey not in ('GA25X', 'FD32'): return None
    n = 0
    for r in gauge['regions']:
        t = r['name'].strip().upper()
        if t == 'AFTERBURNER': r['name'] = 'BOOST '; n += 1
        elif t == 'AIRBRAKE': r['name'] = 'IDLE'; n += 1
    return n
def gauge(k, i): return dict(id=i, ac=Ac(k) if k is not None else None, regions=[dict(name='AIRBRAKE'), dict(name='MIL'), dict(name='AFTERBURNER ')])
seen = set()
res = {k: relabel(gauge(k, i), seen) for i, k in enumerate(('GA25X', 'FD32', 'COIN', 'NIMROD1'))}
T('relabel: GA25X 2 (unchanged), FD32 2 (new), COIN / NIMROD1 none', res == {'GA25X': 2, 'FD32': 2, 'COIN': None, 'NIMROD1': None})
g0 = gauge(None, 9); T('relabel: uninitialised gauge skipped and retried later', relabel(g0, seen) is None and 9 not in seen)
g0['ac'] = Ac('FD32'); T('relabel: retried gauge renamed once', relabel(g0, seen) == 2 and [r['name'] for r in g0['regions']] == ['IDLE', 'MIL', 'BOOST '])
print('ALL PASS' if not fails else f'{fails} FAIL')
raise SystemExit(1 if fails else 0)
