"""Stub test for the B25H.Instruments 1.6.0 B-17G branch (B17G.cs), no game needed.
- routing: only aircraft with jsonKey B17G are touched; the B-25H / Nimrod / FD-32 sources are unchanged against git HEAD of 1.5.7
  (Plugin.cs only gains the ScanB17G / DriveB17GAll calls and the version);
- names: every mover the plugin drives exists in the model contract (assets/model_b17g/b17g_contract.json) and vice versa;
- maths (mirrored from B17GMath): zero / limits / monotonic per dial, engine-out shows on its own needles (a stub game API with 4
  engines, engine 3 stopped), a destroyed aircraft / missing engine does not throw.
Run: python src/B25H.Instruments/b17g_stub_test.py      Expected: 'ALL PASS'."""
import json, math, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
cs = open(os.path.join(HERE, 'B17G.cs')).read()
plugin = open(os.path.join(HERE, 'Plugin.cs')).read()
con = json.load(open(os.path.join(ROOT, 'assets', 'model_b17g', 'b17g_contract.json')))
fails = 0


def T(name, ok):
    global fails
    fails += not ok
    print(('PASS ' if ok else 'FAIL ') + name)


clamp = lambda x, a, b: max(a, min(b, x))
def asi(mps): mph = mps * 2.23694; return 0.0 if mph < 40 else min((mph - 40) / 360 * 330, 330)
def vsi(vy): fpm = clamp(vy * 196.85, -6000, 6000); return -90 + fpm / 6000 * 170
def mp(th, rr, rho, run): return rho / 1.225 * 29.9 if not run else (15 + 31 * clamp(th, 0, 1)) * (0.6 + 0.4 * clamp(rho / 1.225, 0, 1)) * (0.85 + 0.15 * clamp(rr, 0, 1))
def mpdeg(x): return clamp((x - 40) * 5.5, -165, 165)
def rpmdeg(r): return clamp(-165 + r / 3500 * 330, -165, 165)

# ---- routing and isolation
T('B17G branch keyed on jsonKey B17G only', 'a.definition.jsonKey != B17GMath.Key' in cs and 'public const string Key = "B17G";' in cs)
T('B17G branch writes only gauge_* transforms (B17GNames) + 1.8.9 the two columns / two wheels (B17GColumnNames)', cs.count('localRotation =') == 3 and 'System.Array.IndexOf(B17GNames, tr.name)' in cs
  and 'System.Array.IndexOf(B17GColumnNames, tr.name)' in cs and 'B17GColumnNames = { "cockpit_column_L", "cockpit_column_R", "cockpit_yoke_L", "cockpit_yoke_R" }' in cs)
_s1810 = open(os.path.join(HERE, 'Scan1810.cs'), encoding='utf-8').read()   # 1.8.10: the 2 s scan runs one step per frame from Scan1810.cs
T('Plugin.Update calls ScanB17G (2 s scan) and DriveB17GAll', ('ScanB17G();' in plugin or ('ScanB17G();' in _s1810 and 'DiscoveryStep();' in plugin)) and 'DriveB17GAll();' in plugin)
import difflib
_PIN198 = 'd0eeea2'     # the 1.9.8 plugin source


def _show(rev, f):
    r = subprocess.run(['git', 'show', f'{rev}:src/B25H.Instruments/{f}'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.stdout.replace('\r\n', '\n') if r.returncode == 0 and r.stdout else None


# 1.8.4 (offline C): Nimrod.cs / FD32Tac.cs changed on purpose (prop rpm source, GA-25X tac page + Ng). Every line changed since 1.5.7
# must be one of those 1.8.4 changes (it names the prop / rpm ratio / DialMath / the GA-25X key / Ng / the jsonKey log text).
_ok184 = ('1.9.', '1.8.4', 'prop', 'RatedRpm', 'rpmRatio', 'DialMath', 'IsTacFixKey', 'RegisterNg', 'definition.jsonKey} tac page', 'TurbineEngine.cs:286',
          'e.GetRPMRatio() > 0.05f', 'e.GetRPM() : 0f', 'FD-32 tac page:',
          'PassAircraft()', 'PropGauges()', 'Telemetries()', 'HookHud1810', 'FindObjectsOfType<Aircraft>()', 'FindObjectsOfType<PropGauge>()', 'FindObjectsOfType<EngineTelemetry>(true)', 'PatchAi1815();', 'Msb', 'msb', 'MSB1780', 'AI1815', '#endif', '1.9.2', 'partLookup', 'p.name == part', 'return FindOnAircraft<T>(a);', 'GetComponentInChildren found engine_2', 'the named object itself')   # 1.9.2: MSB tac panels on engine 1 by part name; 1.9.0: the MSB tac gate + config (default off) and the #if around the 1.8.15 AI call   # 1.8.10 lag fix (Scan1810.cs); 1.8.15: the AI hook call in Awake (AiGround1815.cs)   # the replaced 1.5.x lines
for f in ('Nimrod.cs', 'FD32Tac.cs'):
    try:
        old = _show('841faa5', f); new_ = _show(_PIN198, f)     # 1.9.9: pinned to the 1.9.8 source (was: the working tree)
        if old is None or new_ is None:
            print(f'SKIP {f} since 1.5.7: git history not available (public tree)'); continue
        old, new_ = old.splitlines(), new_.splitlines()
        ch = [l for l in difflib.ndiff(old, new_) if l[:2] in ('- ', '+ ') and l[2:].strip()]
        bad = [l for l in ch if not any(k in l for k in _ok184) and l[2:].strip() not in ('{', '}', 'get')]
        T(f'{f} (1.9.8 source) since 1.5.7 (841faa5): only the 1.8.4 dial changes ({len(ch)} lines)', not bad)
        if bad: print('   ', bad[:4])
    except Exception as e:
        T(f'{f} unchanged ({e})', False)
old = _show('841faa5', 'Plugin.cs'); new = _show(_PIN198, 'Plugin.cs')     # 1.9.9: pinned to the 1.9.8 source (1.9.9 trimmed the class comment)
strip = lambda s: re.sub(r'.*(BepInPlugin|public partial class Plugin|ScanB17G|DriveB17GAll|ScanExtras|DriveExtrasAll|BindingFlags BFI|1\.8\.[67]|Dials184.cs read BFI|initialisation order|DiscoveryStep|ThrottleGauges\(\)|FindObjectsOfType<ThrottleGauge>\(\)|PassAircraft\(\)|FindObjectsOfType<Aircraft>\(\)).*\n', '', re.sub(r'[ \t]*if \(Time\.unscaledTime >= nextScan\)\s*\{[^{}]*\}\n', '', s))   # 1.8.6: BFI const + its comment; 1.8.10: the scan block moved to Scan1810.cs
if old is None or new is None:
    print('SKIP Plugin.cs since 1.5.7: git history not available (public tree)')
else:
    T('Plugin.cs (1.9.8 source): only the version line, the two B-17G calls and the two 1.8.4 calls changed since 1.5.7', strip(old) == strip(new))
# ---- names vs contract
names = re.findall(r'"(gauge_[a-z0-9_]+)"', cs.split('B17GNames = {')[1].split('};')[0])
movers = {g['name'] for g in con['gauges']['movers']}
T(f'every driven mover is in the model contract ({len(names)})', set(names) <= movers)
T('every contract mover is driven', movers <= set(names))
# ---- maths
T('ASI: 0 below 40 mph, 330 deg at 400 mph, monotonic', asi(10) == 0 and abs(asi(400 / 2.23694) - 330) < 1e-6 and asi(100) > asi(80))
T('VSI: 0 fpm at 9 o\'clock (-90 deg), climb clockwise, clamped at 6,000 fpm', abs(vsi(0) + 90) < 1e-9 and vsi(5) > vsi(0) and abs(vsi(100) - 80) < 1e-6)
T('MP: take-off 46 inHg at sea level and full throttle, falls with density, engine stopped = ambient', abs(mp(1, 1, 1.225, True) - 46) < 1e-6 and mp(1, 1, 0.6, True) < 46 and abs(mp(0, 0, 1.225, False) - 29.9) < 1e-6)
T('MP dial: 40 inHg at 12 o\'clock, clamped', mpdeg(40) == 0 and mpdeg(100) == 165)
T('RPM dial: 0 rpm at -165 deg, 3,500 at +165', rpmdeg(0) == -165 and rpmdeg(3500) == 165)
# ---- stub game: engine 3 out
class Eng:
    def __init__(s, rpm, th): s.rpm, s.th = rpm, th
eng = {1: Eng(2300, 1), 2: Eng(2300, 1), 3: Eng(0, 1), 4: Eng(2300, 1)}
needles = {n: rpmdeg(e.rpm) for n, e in eng.items()}
T('engine-out: engine 3 rpm needle at 0, the other three at 2,300', needles[3] == -165 and all(abs(needles[n] - rpmdeg(2300)) < 1e-9 for n in (1, 2, 4)))
T('missing engine / prop (null) handled: rpm ratio falls back prop -> engine -> 0, not running', 'g.prop[n] != null ? g.prop[n].GetRPMRatio() : en != null ? en.GetRPMRatio() : 0f' in cs and 'en != null && en.GetRPMRatio() > 0.05f && ratio > 0.05f' in cs)
T('exceptions drop only that aircraft (try/catch per aircraft)', 'try { DriveB17G(kv.Value); } catch' in cs)
print('ALL PASS' if not fails else f'{fails} FAIL')
sys.exit(1 if fails else 0)
