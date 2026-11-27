"""Stub test for B25H.Instruments 1.5.3 FD32Tac.cs (FD-32 tac-page power / engine panels), no game needed.

(1) C# routing: FD32 only (IsTacFixKey), scanned from the 2 s Update scan, names mapped COIN -> TurbineEngine, propHub ->
    ConstantSpeedProp, bound panels / other aircraft untouched, exceptions disable the feature; the stock prefab names the panels look
    for are the ones read from tacScreen_cricket (constants below, from the user's own export, not shipped).
(2) Python stub of the binder over a fake game API: FD32 + NIMROD1 + GA25X + another aircraft; an uninitialised panel (retry), an
    already-bound panel (left alone), an EngineTelemetry that disabled itself (re-enabled), a missing prop (skipped), the boost Turbojet
    present on the same part (never chosen), a destroyed panel (released from the set), and an exception (feature off, nothing else changes).
Run: python src/B25H.Instruments/fd32tac_stub_test.py      Expected: 'ALL PASS'."""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
cs = open(os.path.join(HERE, 'FD32Tac.cs'), encoding='utf-8').read()
plug = open(os.path.join(HERE, 'Plugin.cs'), encoding='utf-8').read()
fails = 0


def T(name, ok):
    global fails
    fails += not ok
    print(('PASS ' if ok else 'FAIL ') + name)


# ---- (1) C#
T('plugin 1.5.3+ (1.5.5, 1.6.0)', re.search(r'BepInPlugin\("b25h.instruments", "(B-25H|Heritage Pairs) Instruments", "1\.(5\.[35]|6\.0|8\.([04679]|1[0125])|9.([02789]|1[012345]))"\)', plug) is not None)
T('scanned in the 2 s scan block (1.8.10: its own frame step in Scan1810.cs)', re.search(r'ScanNimrod\(\);\s*FD32TacPanels\(\);', plug) is not None or 'case 3: FD32TacPanels(); break;' in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Scan1810.cs'), encoding='utf-8').read())
T('FD32 + GA25X (1.8.4: the GA-25X tac page had the same unbound panels)', 'IsTacFixKey(string k) => k == TacKeyFD32 || k == BoostJsonKey;' in cs and 'TacKeyFD32 = "FD32";' in cs and (cs.count('if (!IsTacFixKey(a.definition.jsonKey)) continue;') == 2 or cs.count('if (!IsTacFixKey(a.definition.jsonKey) && !(a.definition.jsonKey == MsbTacKey && MsbTacOn)) continue;') == 2))   # 1.9.0: + MSB1780 behind [Dials] MsbTac190 (default off)
T('name map COIN -> turbine, propHub -> prop', 'engineName == "COIN" ? "turbine" : engineName == "propHub" ? "prop" : null' in cs)
T('turbine role uses TurbineEngine (not the boost Turbojet)', ('role == "turbine" ? (IEngine)FindOnAircraft<TurbineEngine>(a)' in cs or 'role == "turbine" ? (IEngine)(msb ? MsbEngine1<TurbineEngine>(a, "engine_1") : FindOnAircraft<TurbineEngine>(a))' in cs) and 'Turbojet' not in cs.split('IEngine eng =')[1].split(';')[0])
T('already-bound panels left alone', cs.count('as Object != null) continue;') == 2)
T('displayPower / displayPitch as EngineTelemetry.Start; component re-enabled', 'eng is IPowerSource' in cs and 'eng is IPitchTelemetry' in cs and 't.enabled = true;' in cs)
T('exceptions disable the feature for the session', 'fd32TacBroken = true' in cs and 'if (fd32TacBroken) return;' in cs)
T('no other plugin path changed (Scan / BoostLabels / Nimrod untouched by this file)', 'tracked' not in cs and 'relabelled' not in cs and 'IsFixedGear' not in cs)
PREFAB = os.path.join(r'C:\Users\User\nuclearoption-ref\BlueprinterProject\Blueprinter-Editor\Assets\Blueprinter\_donotship\GameObject', 'tacScreen_cricket_PLACEHOLDER.prefab')
if os.path.exists(PREFAB):
    pf = open(PREFAB, encoding='utf-8', errors='ignore').read()
    T('stock tac page still looks for propHub / COIN (the names this binder maps)', 'sourceName: propHub' in pf and 'engineName: COIN' in pf and 'engineName: propHub' in pf)
else:
    print('SKIP stock prefab not present (names checked offline when it is)')


# ---- (2) stub
class Def:
    def __init__(s, k): s.jsonKey = k
class Comp:
    def __init__(s, kind, name): s.kind, s.name, s.alive = kind, name, True
class Ac:
    def __init__(s, key, comps): s.definition = Def(key) if key else None; s.comps = comps
    def find(s, kind): return next((c for c in s.comps if c.kind == kind and c.alive), None)
class PropGauge:
    def __init__(s, a): s.aircraft, s.source, s.alive = a, None, True
class Telemetry:
    def __init__(s, a, name, bound=None):
        s.aircraft, s.engineName, s.engineInterface, s.enabled, s.alive = a, name, bound, False, True
        s.displayPower = s.displayPitch = None
POWER = {'TurbineEngine'}; PITCH = {'ConstantSpeedProp'}


class Binder:
    def __init__(s): s.broken, s.bound = False, set()
    def run(s, gauges, tels, boom=False):
        if s.broken: return
        try:
            s.bound = {o for o in s.bound if o.alive}
            for g in gauges:
                if g in s.bound: continue
                a = g.aircraft
                if a is None or a.definition is None: continue
                s.bound.add(g)
                if a.definition.jsonKey != 'FD32' or g.source is not None: continue
                p = a.find('ConstantSpeedProp')
                if p is None: continue
                if boom: raise RuntimeError('reflection')
                g.source = p
            for t in tels:
                if t in s.bound: continue
                a = t.aircraft
                if a is None or a.definition is None: continue
                s.bound.add(t)
                if a.definition.jsonKey != 'FD32' or t.engineInterface is not None: continue
                role = 'turbine' if t.engineName == 'COIN' else 'prop' if t.engineName == 'propHub' else None
                e = a.find('TurbineEngine') if role == 'turbine' else a.find('ConstantSpeedProp') if role == 'prop' else None
                if e is None: continue
                t.engineInterface = e; t.displayPower = e.kind in POWER; t.displayPitch = e.kind in PITCH; t.enabled = True
        except Exception:
            s.broken = True


def fd32():
    return Ac('FD32', [Comp('Turbojet', 'fus_engine'), Comp('TurbineEngine', 'fus_engine'), Comp('ConstantSpeedProp', 'prop')])


a = fd32(); b = Binder()
pg, tc, tp = PropGauge(a), Telemetry(a, 'COIN'), Telemetry(a, 'propHub')
b.run([pg], [tc, tp])
T('FD32: power panel bound to the prop', pg.source is not None and pg.source.kind == 'ConstantSpeedProp')
T('FD32: COIN panel bound to the TurbineEngine (not the boost Turbojet), power display, re-enabled', tc.engineInterface.kind == 'TurbineEngine' and tc.displayPower and not tc.displayPitch and tc.enabled)
T('FD32: propHub panel bound to the prop, pitch display', tp.engineInterface.kind == 'ConstantSpeedProp' and tp.displayPitch and not tp.displayPower)
for key in ('NIMROD1', 'GA25X', 'B25H', 'COIN'):
    o = Ac(key, [Comp('TurbineEngine', 'x'), Comp('ConstantSpeedProp', 'y')]); g2 = PropGauge(o); t2 = Telemetry(o, 'COIN'); b2 = Binder(); b2.run([g2], [t2])
    T(f'{key}: untouched', g2.source is None and t2.engineInterface is None and not t2.enabled)
u = PropGauge(Ac(None, [])); b3 = Binder(); b3.run([u], [])
T('uninitialised panel: not marked, retried next scan', u not in b3.bound)
pre = Comp('ConstantSpeedProp', 'stock'); g4 = PropGauge(fd32()); g4.source = pre; Binder().run([g4], [])
T('already-bound panel left alone', g4.source is pre)
noprop = Ac('FD32', [Comp('TurbineEngine', 'fus_engine')]); g5 = PropGauge(noprop); Binder().run([g5], [])
T('missing prop: skipped, no error', g5.source is None)
pg.alive = False; b.run([], []); T('destroyed panel released', pg not in b.bound)
b6 = Binder(); g6 = PropGauge(fd32()); b6.run([g6], [], boom=True); g7 = PropGauge(fd32()); b6.run([g7], [])
T('exception: feature off for the session, nothing else touched', b6.broken and g7.source is None)
print('ALL PASS' if fails == 0 else f'{fails} FAIL')

import sys
sys.exit(1 if fails else 0)
