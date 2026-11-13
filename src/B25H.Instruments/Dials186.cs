// B25H.Instruments 1.8.6 (offline G, 2026-11-08): device discovery that cannot miss, and the two needles the in-game round could not see move.
//
// In game (1.8.4 / 1.8.5, nuclearoption-ref\study\ingame_185\b25h_hld.txt): the B-25H has four flap HighLiftDevices (flap_outer_L/R area
// 0.6, flap_inner_L/R area 0.4, position ~1.0 at rest) but the plugin logged "0 flap devices" on every attach.
// Cause (fact, reproduced offline with the same compiler and file order, tools/stub_tests_186g.py row "static-init order"): Plugin.BFI was a
// `static readonly` field in Plugin.cs, and Dials184.cs initialised `HldArea = typeof(HighLiftDevice).GetField("deployedArea", BFI)` in
// ITS static initialiser. Roslyn runs the static initialisers of a partial class file by file in compile order (build_instruments.sh
// passes the files alphabetically: B17G.cs, Dials184.cs, FD32Tac.cs, Nimrod.cs, Plugin.cs), so BFI was still 0 when Dials184.cs ran,
// GetField(name, 0) returned null, the `HldArea != null` filter dropped every flap and HldPosition was null too. 1.8.6: BFI is a const and
// the two fields spell their flags out.
//
// Also here: devices are recognised by what they are (HighLiftDevice with deployedArea > 0 OR a GameObject name containing "flap"; the
// cockpit ASI device has area 0 and is not a flap), read at use time, and every device list that is still empty after the attach is
// re-scanned on each 2 s scan (up to RescanLimit times) for the B-25H / GA-25X extras, the Mk I / FD-32 engine + prop and the B-17G
// engine_1..4 / prop_1..4 slots - a part registering late can no longer leave a dial dead for the session.
// Hydraulic (B-25H): the pump stops with the ignition, and gear OR flap travel dips the pressure (Dials184.cs DriveB25HExtras).
// Fuel pressure (B-17G EGU x4): the engine-driven pump needs ignition + fuel + an operable engine; it falls with a 1.5 s lag (B17G.cs).
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public partial class Plugin
    {
        public const int RescanLimit = 60;          // 60 scans x 2 s = 2 min after the attach
        public const float FlapMovingRate = 0.05f;  // HighLiftDevice.position units per second (full travel = 1 / s in the game)

        // a HighLiftDevice is a flap if it adds area (the B-25H ASI device on fus_cockpit has 0) or sits on a flap part
        public static bool IsFlapDevice(string goName, float deployedArea) => deployedArea > 0f || (goName != null && goName.ToLowerInvariant().Contains("flap"));

        static float HldAreaOf(HighLiftDevice h)
        {
            try { return HldArea != null ? (float)HldArea.GetValue(h) : 0f; } catch { return 0f; }
        }

        // engines, props, flaps of a B-25H / GA-25X (ExtraDials); returns true if a list grew
        static bool CollectDevices(ExtraDials g)
        {
            int e0 = g.engines.Count, p0 = g.props.Count, f0 = g.flaps.Count;
            g.engines.RemoveAll(x => x == null); g.props.RemoveAll(x => x == null); g.flaps.RemoveAll(x => x == null);
            foreach (var tr in AllTransforms(g.aircraft))
            {
                if (tr == null) continue;
                var te = tr.GetComponent<TurbineEngine>(); if (te != null && !g.engines.Contains(te)) g.engines.Add(te);
                var cp = tr.GetComponent<ConstantSpeedProp>(); if (cp != null && !g.props.Contains(cp)) g.props.Add(cp);
                foreach (var h in tr.GetComponents<HighLiftDevice>())
                    if (h != null && !g.flaps.Contains(h) && IsFlapDevice(h.gameObject.name, HldAreaOf(h))) g.flaps.Add(h);
            }
            return g.engines.Count > e0 || g.props.Count > p0 || g.flaps.Count > f0;
        }

        static bool NeedsRescan(ExtraDials g) => g.engines.Count == 0 || g.props.Count == 0 || (g.key == JsonKey && g.flaps.Count == 0);

        // flap position (0 retracted .. 1 deployed) = the most deployed flap; 0 if none found
        static float FlapPosition(ExtraDials g)
        {
            float flap = 0f;
            if (HldPosition == null) return flap;
            foreach (var f in g.flaps)
                if (f != null) { try { flap = Mathf.Max(flap, (float)HldPosition.GetValue(f)); } catch { } }
            return flap;
        }

        static bool FlapMoving(ExtraDials g, float flap, float dt)
        {
            if (g.flapPrev < 0f) { g.flapPrev = flap; return false; }
            g.flapRate = DialMath.Lag(g.flapRate, Mathf.Abs(flap - g.flapPrev) / Mathf.Max(dt, 1e-4f), dt, 0.3f);
            g.flapPrev = flap;
            return g.flapRate > FlapMovingRate;
        }

        // ---- engine-driven pumps: ignition on, engine operable, fuel available (TurbineEngine.Update's own run condition, TurbineEngine.cs:273)
        static FieldInfo teOperable, teHasFuel; static bool teFieldsLooked;
        public static bool EngineLive(Aircraft a, TurbineEngine en)
        {
            if (a == null || en == null || !a.Ignition) return false;
            if (!teFieldsLooked)
            {
                teFieldsLooked = true;
                teOperable = typeof(TurbineEngine).GetField("operable", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
                teHasFuel = typeof(TurbineEngine).GetField("hasFuel", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            }
            try
            {
                if (teOperable != null && !(bool)teOperable.GetValue(en)) return false;
                if (teHasFuel != null && !(bool)teHasFuel.GetValue(en)) return false;
            }
            catch { }
            return true;
        }

        readonly Dictionary<Aircraft, int> devRescans = new Dictionary<Aircraft, int>();

        // called from ScanExtras every 2 s: fill device lists that are still empty
        void RescanDevices186()
        {
            try
            {
                foreach (var kv in extras)
                {
                    var g = kv.Value;
                    if (kv.Key == null || !NeedsRescan(g) || g.rescans >= RescanLimit) continue;
                    g.rescans++;
                    if (CollectDevices(g))
                        Logger.LogInfo($"1.8.6 dials: {kv.Key.name} ({g.key}) re-scan {g.rescans}: {g.engines.Count} engines, {g.props.Count} props, {g.flaps.Count} flap devices");
                }
                foreach (var kv in nimrods)
                {
                    var g = kv.Value;
                    if (kv.Key == null || (g.engine != null && g.prop != null)) continue;
                    devRescans.TryGetValue(kv.Key, out var n); if (n >= RescanLimit) continue; devRescans[kv.Key] = n + 1;
                    bool had = g.engine != null, hadP = g.prop != null;
                    foreach (var tr in AllTransforms(kv.Key))
                    {
                        if (tr == null) continue;
                        if (g.engine == null) g.engine = tr.GetComponent<TurbineEngine>();
                        if (g.prop == null) g.prop = tr.GetComponent<ConstantSpeedProp>();
                    }
                    if ((!had && g.engine != null) || (!hadP && g.prop != null))
                        Logger.LogInfo($"1.8.6 dials: {kv.Key.name} re-scan {n + 1}: engine {g.engine != null}, prop {g.prop != null}");
                }
                foreach (var kv in b17gs)
                {
                    var g = kv.Value;
                    bool missing = false; for (int i = 1; i <= 4; i++) missing |= g.eng[i] == null || g.prop[i] == null;
                    if (kv.Key == null || !missing) continue;
                    devRescans.TryGetValue(kv.Key, out var n); if (n >= RescanLimit) continue; devRescans[kv.Key] = n + 1;
                    int before = 0, after = 0;
                    for (int i = 1; i <= 4; i++) before += (g.eng[i] != null ? 1 : 0) + (g.prop[i] != null ? 1 : 0);
                    foreach (var tr in AllTransforms(kv.Key))
                    {
                        if (tr == null) continue;
                        if (tr.name.StartsWith("engine_") && tr.name.Length == 8 && int.TryParse(tr.name.Substring(7), out int en) && en >= 1 && en <= 4 && g.eng[en] == null)
                            g.eng[en] = tr.GetComponent<TurbineEngine>();
                        if (tr.name.StartsWith("prop_") && tr.name.Length == 6 && int.TryParse(tr.name.Substring(5), out int pn) && pn >= 1 && pn <= 4 && g.prop[pn] == null)
                            g.prop[pn] = tr.GetComponent<ConstantSpeedProp>();
                    }
                    for (int i = 1; i <= 4; i++) after += (g.eng[i] != null ? 1 : 0) + (g.prop[i] != null ? 1 : 0);
                    if (after > before) Logger.LogInfo($"1.8.6 dials: {kv.Key.name} (B17G) re-scan {n + 1}: {after}/8 engines + props");
                }
                List<Aircraft> gone = null;
                foreach (var a in devRescans.Keys) if (a == null) (gone = gone ?? new List<Aircraft>()).Add(a);
                if (gone != null) foreach (var a in gone) devRescans.Remove(a);
            }
            catch (System.Exception e) { Logger.LogWarning("1.8.6 device re-scan: " + e.Message); }
        }
    }
}
