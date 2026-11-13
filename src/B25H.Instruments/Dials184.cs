// B25H.Instruments 1.8.4 (offline C, 2026-11-08): the dials the 1.8.2 in-game round found dead.
//
// Causes (decompiled game 0.34.6, nuclearoption-ref\decomp_0346):
//  * TurbineEngine.Update (TurbineEngine.cs:286) spools currentRPM to maxRPM * (condition * 0.5 + 0.5) whatever the throttle: GetRPM /
//    GetRPMRatio are CONSTANT while an engine runs. Every rpm / oil-pressure needle fed from TurbineEngine sat still (Mk I rpm + oil P,
//    B-17G rpm 1-4), and the stock tac-page turbine panel reads 100 % (FD-32). The rpm that varies is the ConstantSpeedProp's
//    (ConstantSpeedProp.cs:750, RPM from the shaft's angular velocity; GetRPMRatio = RPM / rpmLimit, :623).
//  * GA-25X tac page: PropGauge / EngineTelemetry find their source by part NAME ("propHub" / "COIN", PropGauge.cs:37, EngineTelemetry.cs
//    Start); the GA-25X parts are prop_L / engine_L, so they never bound (the FD32Tac.cs cause, FD32 only until now).
//  * B-25H: the clock, suction, ammeter, carburettor / free-air temperature, compass, de-icer, oxygen, brake-pressure and volt dials were
//    painted into the fal panel art (b25h_cockpit_layout.DECO) and oil P / oil T / CHT / hydraulic / flaps / gear were dial faces with a
//    baked needle and no mover. 1.8.4 models a real dial (bezel, needle-free face, needle / card mover) over each; this file drives them.
//  * GA-25X standby attitude / compass were static atlas cells; 1.8.4 adds a horizon card and a heading card in front of them.
// Every value -> angle map is a pure function in DialMath (mirrored by tools/dials184_stub_test.py). Writes only transforms named gauge_*
// inside B25H / GA25X aircraft and, on FD32 / GA25X tac pages, the turbine panel's own rpm reading / needle (after the stock Update).
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class DialMath
    {
        // standard atmosphere (the game has no air-temperature model: no temperature field in Aircraft / LevelInfo / WeatherSet)
        public static float IsaC(float altM) => 15f - 0.0065f * Mathf.Clamp(altM, -500f, 11000f);
        // free-air (indicated) temperature: ISA + ram rise v^2 / (2 cp) with recovery 0.9
        public static float OatC(float altM, float tas) => IsaC(altM) + 0.9f * tas * tas / 2010f;
        // engine rpm from the propeller's governed rpm ratio (RPM / rpmLimit), rated rpm at ratio 1
        public static float EngineRpm(float propRatio, float rated) => Mathf.Clamp(propRatio, 0f, 1.3f) * rated;
        public static float Lin(float v, float v0, float v1, float a0, float sweep) => a0 + Mathf.Clamp01((v - v0) / (v1 - v0)) * sweep;
        public static float Lag(float v, float target, float dt, float tau) => v + (target - v) * Mathf.Clamp01(dt / tau);
        // engine-driven vacuum pump: regulated 4.8 inHg above ~60 % rpm
        public static float Suction(float rpmRatio) => 4.8f * Mathf.Clamp01(rpmRatio / 0.6f);
        public static float OilPsi(float rpmRatio, bool running, float idle, float rated) => running ? Mathf.Lerp(idle, rated, Mathf.Clamp01(rpmRatio)) : 0f;
        public static float DeicerPsi(float rpmRatio) => 8f * Mathf.Clamp01(rpmRatio / 0.6f);
        // generator load (A): base 30, + electric load with power (fuel pumps, turrets, lights), small ripple; 0 with no engine turning
        public static float Ammeter(bool running, float power01, float t) => running ? 30f + 25f * Mathf.Clamp01(power01) + 2.5f * Mathf.Sin(t * 0.7f) + 1.5f * Mathf.Sin(t * 2.3f) : 0f;
        public static float Volts(bool running, float amps) => running ? 28.2f - 0.01f * amps : 24f;
        // hydraulic (engine-driven pump): 1,050 psi with the pump turning, 600 while gear / flaps move (1.8.6: was 800, a 34 deg dip
        // the in-game probe never caught); 0 target with the pump stopped (ignition off), bled slowly. Lag time constants per case.
        public static float HydPsi(bool pumpOn, bool moving) => pumpOn ? (moving ? 600f : 1050f) : 0f;
        public static float HydTau(bool pumpOn, bool moving, float current, float target) => !pumpOn ? 8f : moving || target < current ? 0.8f : 2f;
        // clock from the game's time of day (hours)
        public static float ClockHourDeg(float h) => Mathf.Repeat(h, 12f) * 30f;
        public static float ClockMinDeg(float h) => Mathf.Repeat(h, 1f) * 360f;
        public static float ClockSecDeg(float h) => Mathf.Repeat(h * 60f, 1f) * 360f;
        // turboprop gas-generator speed: 62 % at flight idle .. 100 % at rated power (the game's TurbineEngine rpm is the constant
        // free-turbine speed); power normalised by the density factor TurbineEngine applies (TurbineEngine.cs:288)
        public static float NgPct(float rpmRatio, float power, float maxPower, float density)
        {
            float pf = maxPower > 0f ? Mathf.Clamp01(power / (maxPower * Mathf.Max(density / 1.225f, 0.05f))) : 0f;
            return Mathf.Clamp01(rpmRatio) * 62f + (rpmRatio > 0.5f ? 38f * Mathf.Sqrt(pf) : 0f);
        }
        public static float Oxygen(float psi, float altM, float dt) => altM > 3000f ? Mathf.Max(psi - dt / 60f, 0f) : psi;   // 1 psi per minute above 10,000 ft
    }

    public partial class Plugin
    {
        // B-25H 1.8.4 dials: id -> (v0, v1, a0 deg at v0 clockwise from 12 o'clock, sweep deg). Same table in
        // blender/v2/b25h_dials184.py (faces + contract) - the stub test compares them.
        public static readonly Dictionary<string, float[]> B25HScales = new Dictionary<string, float[]>
        {
            { "oil_press", new[] { 0f, 200f, -135f, 270f } }, { "oil_temp", new[] { -50f, 150f, -135f, 270f } },
            { "cyl_temp", new[] { 0f, 350f, -135f, 270f } }, { "hydraulic", new[] { 0f, 2000f, -135f, 270f } },
            { "flaps_pos", new[] { 0f, 1f, -90f, 180f } }, { "gear_pos", new[] { 0f, 1f, -90f, 180f } },
            { "suction", new[] { 0f, 10f, -135f, 270f } }, { "ammeter", new[] { 0f, 150f, -135f, 270f } },
            { "brake_press", new[] { 0f, 1500f, -135f, 270f } }, { "volts", new[] { 0f, 30f, -135f, 270f } },
            { "carb_temp", new[] { -50f, 50f, -135f, 270f } }, { "free_air", new[] { -50f, 50f, -135f, 270f } },
            { "deicer", new[] { 0f, 20f, -135f, 270f } }, { "oxygen", new[] { 0f, 500f, -135f, 270f } },
        };
        public static readonly string[] B25HExtraNames = {
            "gauge_oil_press_needle", "gauge_oil_temp_needle", "gauge_cyl_temp_needle", "gauge_hydraulic_needle", "gauge_flaps_pos_needle", "gauge_gear_pos_needle",
            "gauge_clock_needle", "gauge_clock_needle_short", "gauge_suction_L_needle", "gauge_suction_C_needle", "gauge_ammeter_needle", "gauge_brake_press_needle",
            "gauge_volts_needle", "gauge_carb_temp_L_needle", "gauge_carb_temp_R_needle", "gauge_free_air_L_needle", "gauge_free_air_R_needle",
            "gauge_compass_card", "gauge_deicer_L_needle", "gauge_deicer_R_needle", "gauge_oxygen_needle" };
        public static readonly string[] GA25XExtraNames = { "gauge_isis_att_card", "gauge_isis_hdg_card", "gauge_isis_tq_L_needle", "gauge_isis_tq_R_needle", "gauge_isis_fuel_bar" };
        public static float TorqueDeg(float power, float maxPower, float density) => DialMath.Lin(maxPower > 0f ? power / (maxPower * Mathf.Max(density / 1.225f, 0.05f)) : 0f, 0f, 1f, -120f, 240f);
        public static string ScaleKey(string gaugeName)
        {   // gauge_<id>[_L|_R|_C]_needle -> scale id
            var s = gaugeName.Substring(6);
            s = s.EndsWith("_needle") ? s.Substring(0, s.Length - 7) : s;
            if (s.EndsWith("_L") || s.EndsWith("_R") || s.EndsWith("_C")) s = s.Substring(0, s.Length - 2);
            return s;
        }
        public static float B25HAngle(string gaugeName, float value)
        {
            if (!B25HScales.TryGetValue(ScaleKey(gaugeName), out var sc)) return 0f;
            return DialMath.Lin(value, sc[0], sc[1], sc[2], sc[3]);
        }

        class ExtraDials
        {
            public Aircraft aircraft; public string key;
            public readonly Dictionary<string, Transform> t = new Dictionary<string, Transform>();
            public readonly Dictionary<string, Quaternion> rest = new Dictionary<string, Quaternion>();
            public readonly Dictionary<string, Vector3> restPos = new Dictionary<string, Vector3>();
            public readonly Dictionary<string, Vector3> restScale = new Dictionary<string, Vector3>();
            public readonly List<TurbineEngine> engines = new List<TurbineEngine>();
            public readonly List<ConstantSpeedProp> props = new List<ConstantSpeedProp>();
            public readonly List<Component> flaps = new List<Component>();
            public float oilT = 15f, cht = 15f, hyd, brake, oxy = 425f, compass, carbL = 15f, carbR = 15f, gearPos = 1f; public bool haveCompass;
            public float flapPrev = -1f, flapRate; public int rescans;   // 1.8.6: flap travel (hydraulic dip) and device re-scans (Dials186.cs)
        }
        readonly Dictionary<Aircraft, ExtraDials> extras = new Dictionary<Aircraft, ExtraDials>();
        readonly Dictionary<Aircraft, int> extraMisses = new Dictionary<Aircraft, int>();
        // 1.8.6: BFI is a const now (Plugin.cs); before, these two were initialised while BFI was still 0 -> null -> "0 flap devices"
        static readonly FieldInfo HldPosition = typeof(HighLiftDevice).GetField("position", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
        static readonly FieldInfo HldArea = typeof(HighLiftDevice).GetField("deployedArea", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);

        static IEnumerable<Transform> AllTransforms(Aircraft a)
        {
            var all = new HashSet<Transform>(a.GetComponentsInChildren<Transform>(true));
            if (a.partLookup != null)
                foreach (var part in a.partLookup)
                    if (part != null) foreach (var pt in part.GetComponentsInChildren<Transform>(true)) all.Add(pt);
            return all;
        }

        void ScanExtras()
        {
            RescanDevices186();   // 1.8.6: fill device lists still empty after an attach (Dials186.cs)
            foreach (var a in PassAircraft())
            {
                if (a != null && a.definition != null) RegisterGrip(a);   // 1.8.9: ground grip registration rides on this 2 s pass (GroundGrip189.cs)
                if (a == null || extras.ContainsKey(a) || a.definition == null) continue;
                var k = a.definition.jsonKey;
                var names = k == JsonKey ? B25HExtraNames : k == BoostJsonKey ? GA25XExtraNames : null;
                if (names == null) continue;
                var g = new ExtraDials { aircraft = a, key = k };
                foreach (var tr in AllTransforms(a))
                {
                    if (System.Array.IndexOf(names, tr.name) >= 0 && !g.t.ContainsKey(tr.name)) { g.t[tr.name] = tr; g.rest[tr.name] = tr.localRotation; g.restPos[tr.name] = tr.localPosition; g.restScale[tr.name] = tr.localScale; }
                }
                CollectDevices(g);   // 1.8.6 (Dials186.cs): engines, props, flaps; re-scanned on later scans while any list is empty
                if (g.t.Count == 0)
                {
                    extraMisses.TryGetValue(a, out var m); extraMisses[a] = m + 1;
                    if (m + 1 < 10) continue;
                }
                extras[a] = g;
                Logger.LogInfo($"1.8.7 dials attached to {a.name} ({k}): {g.t.Count}/{names.Length} movers, {g.engines.Count} engines, {g.props.Count} props, {g.flaps.Count} flap devices");
            }
        }

        void DriveExtrasAll()
        {
            if (extras.Count == 0) return;
            List<Aircraft> dead = null;
            foreach (var kv in extras)
            {
                if (kv.Key == null) { (dead = dead ?? new List<Aircraft>()).Add(kv.Key); continue; }
                try { if (kv.Value.key == JsonKey) DriveB25HExtras(kv.Value); else DriveGA25XStandby(kv.Value); }
                catch (System.Exception e) { Logger.LogWarning("1.8.4 dials: " + e.Message); (dead = dead ?? new List<Aircraft>()).Add(kv.Key); }
            }
            if (dead != null) foreach (var a in dead) extras.Remove(a);
        }

        static void SetX(ExtraDials g, string n, float deg)
        {
            if (g.t.TryGetValue(n, out var tr) && tr != null) tr.localRotation = g.rest[n] * Quaternion.AngleAxis(deg, Vector3.right);
        }

        public static float TimeOfDayHours()
        {
            try { var li = NetworkSceneSingleton<LevelInfo>.i; if (li != null) return li.timeOfDay; } catch { }
            var n = System.DateTime.Now; return n.Hour + n.Minute / 60f + n.Second / 3600f;
        }

        void DriveB25HExtras(ExtraDials g)
        {
            var a = g.aircraft;
            if (a.disabled) return;
            float dt = Mathf.Max(Time.deltaTime, 1e-4f), altM = a.transform.position.GlobalY();
            float pr = 0f, pw = 0f; int n = 0; bool running = false;
            foreach (var p in g.props) if (p != null) { pr = Mathf.Max(pr, p.GetRPMRatio()); n++; }
            foreach (var e in g.engines) if (e != null) { pw = Mathf.Max(pw, Mathf.Sqrt(Mathf.Max(e.powerRatio, 0f))); running |= e.GetRPMRatio() > 0.3f && pr > 0.05f; }
            if (n == 0) running = false;
            float oat = DialMath.OatC(altM, a.speed);
            SetX(g, "gauge_oil_press_needle", B25HAngle("gauge_oil_press_needle", DialMath.OilPsi(pr, running, 40f, 82f)));
            g.oilT = DialMath.Lag(g.oilT, running ? 55f + 25f * pw : oat, dt, 60f);
            SetX(g, "gauge_oil_temp_needle", B25HAngle("gauge_oil_temp_needle", g.oilT));
            g.cht = DialMath.Lag(g.cht, running ? 120f + 110f * pw : oat, dt, 50f);
            SetX(g, "gauge_cyl_temp_needle", B25HAngle("gauge_cyl_temp_needle", g.cht));
            bool gearMoving = a.gearState == LandingGear.GearState.Extending || a.gearState == LandingGear.GearState.Retracting;
            float gearTarget = a.gearState == LandingGear.GearState.LockedRetracted || a.gearState == LandingGear.GearState.Retracting ? 0f : 1f;
            g.gearPos = Mathf.MoveTowards(g.gearPos, gearTarget, dt / 6f);
            SetX(g, "gauge_gear_pos_needle", B25HAngle("gauge_gear_pos_needle", g.gearPos));
            float flap = FlapPosition(g);   // 1.8.6: read at use time from the flap HighLiftDevices (Dials186.cs)
            SetX(g, "gauge_flaps_pos_needle", B25HAngle("gauge_flaps_pos_needle", flap));
            bool flapMoving = FlapMoving(g, flap, dt);
            bool pumpOn = running && a.Ignition;    // 1.8.6: the engine-driven pump stops with the ignition (the turbine rpm decays for ~30 s)
            float hydT = DialMath.HydPsi(pumpOn, gearMoving || flapMoving);
            g.hyd = DialMath.Lag(g.hyd, hydT, dt, DialMath.HydTau(pumpOn, gearMoving || flapMoving, g.hyd, hydT));
            SetX(g, "gauge_hydraulic_needle", B25HAngle("gauge_hydraulic_needle", g.hyd));
            var ci = a.GetInputs();
            g.brake = DialMath.Lag(g.brake, running ? 1000f - 300f * Mathf.Clamp01(ci != null ? ci.brake : 0f) : g.brake * 0.999f, dt, 2f);
            SetX(g, "gauge_brake_press_needle", B25HAngle("gauge_brake_press_needle", g.brake));
            float h = TimeOfDayHours();
            SetX(g, "gauge_clock_needle", DialMath.ClockMinDeg(h));
            SetX(g, "gauge_clock_needle_short", DialMath.ClockHourDeg(h));
            float suc = DialMath.Suction(pr);
            SetX(g, "gauge_suction_L_needle", B25HAngle("gauge_suction_L_needle", suc));
            SetX(g, "gauge_suction_C_needle", B25HAngle("gauge_suction_C_needle", suc));
            float amps = DialMath.Ammeter(running, pw, Time.time);
            SetX(g, "gauge_ammeter_needle", B25HAngle("gauge_ammeter_needle", amps));
            SetX(g, "gauge_volts_needle", B25HAngle("gauge_volts_needle", DialMath.Volts(running, amps)));
            g.carbL = DialMath.Lag(g.carbL, oat + (running ? 12f + 18f * pw : 0f), dt, 20f);
            SetX(g, "gauge_carb_temp_L_needle", B25HAngle("gauge_carb_temp_L_needle", g.carbL));
            SetX(g, "gauge_carb_temp_R_needle", B25HAngle("gauge_carb_temp_R_needle", g.carbL));
            SetX(g, "gauge_free_air_L_needle", B25HAngle("gauge_free_air_L_needle", oat));
            SetX(g, "gauge_free_air_R_needle", B25HAngle("gauge_free_air_R_needle", oat));
            float de = running ? DialMath.DeicerPsi(pr) : 0f;
            SetX(g, "gauge_deicer_L_needle", B25HAngle("gauge_deicer_L_needle", de));
            SetX(g, "gauge_deicer_R_needle", B25HAngle("gauge_deicer_R_needle", de));
            g.oxy = DialMath.Oxygen(g.oxy, altM, dt);
            SetX(g, "gauge_oxygen_needle", B25HAngle("gauge_oxygen_needle", g.oxy));
            // standby magnetic compass: the card lags the heading (1.5 s), card angle = -heading as the B-25H heading card
            float hdg = a.transform.eulerAngles.y;
            if (!g.haveCompass) { g.compass = hdg; g.haveCompass = true; }
            g.compass += Mathf.DeltaAngle(g.compass, hdg) * Mathf.Clamp01(dt / 1.5f);
            SetX(g, "gauge_compass_card", -g.compass);
        }

        // GA-25X ISIS standby: horizon card rolls with bank (B-25H attitude convention) and shifts with pitch; heading card = -heading
        public const float IsisPitchMetresPerDeg = -0.0006f;
        void DriveGA25XStandby(ExtraDials g)
        {
            var a = g.aircraft;
            if (a.disabled) return;
            var e = a.transform.eulerAngles;
            float bank = e.z > 180f ? e.z - 360f : e.z, pitchUp = -(e.x > 180f ? e.x - 360f : e.x);
            const string att = "gauge_isis_att_card";
            if (g.t.TryGetValue(att, out var tr) && tr != null)
            {
                tr.localRotation = g.rest[att] * Quaternion.AngleAxis(bank, Vector3.right);
                tr.localPosition = g.restPos[att] + g.rest[att] * (Vector3.up * Mathf.Clamp(pitchUp, -20f, 20f) * IsisPitchMetresPerDeg);
            }
            SetX(g, "gauge_isis_hdg_card", -e.y);
            foreach (var en in g.engines)
            {
                if (en == null) continue;
                var side = en.name.EndsWith("_L") ? "L" : en.name.EndsWith("_R") ? "R" : null;
                if (side != null) SetX(g, $"gauge_isis_tq_{side}_needle", TorqueDeg(en.GetPower(), en.GetMaxPower(), a.airDensity));
            }
            const string bar = "gauge_isis_fuel_bar";
            if (g.t.TryGetValue(bar, out var fb) && fb != null)
            {
                var sc = g.restScale[bar]; sc.y *= Mathf.Max(Mathf.Clamp01(a.GetFuelLevel()), 0.001f); fb.localScale = sc;
            }
        }

        // ---- tac pages (FD32 + GA25X): bind the stock panels (FD32Tac.cs) and show gas-generator speed instead of the constant turbine rpm
        public static bool IsNgKey(string k) => k == TacKeyFD32 || k == BoostJsonKey;
        class NgPanel { public EngineTelemetry tel; public TurbineEngine eng; public Transform needle; public Component reading; public PropertyInfo text; public Aircraft a; }
        readonly List<NgPanel> ngPanels = new List<NgPanel>();
        bool ngBroken;

        void RegisterNg(EngineTelemetry t, TurbineEngine eng, Aircraft a)
        {
            if (ngBroken || t == null || eng == null) return;
            try
            {
                var gauge = typeof(EngineTelemetry).GetField("rpmGauge", BFI)?.GetValue(t);
                if (gauge == null) return;
                var needle = gauge.GetType().GetField("needle", BFI)?.GetValue(gauge) as Transform;
                var reading = gauge.GetType().GetField("reading", BFI)?.GetValue(gauge) as Component;
                ngPanels.Add(new NgPanel { tel = t, eng = eng, needle = needle, reading = reading, text = reading?.GetType().GetProperty("text"), a = a });
                Logger.LogInfo($"{a.definition.jsonKey} tac page: turbine rpm panel shows gas-generator speed (Ng) from {eng.name}");
            }
            catch (System.Exception ex) { ngBroken = true; Logger.LogWarning("Ng display disabled: " + ex.Message); }
        }

        void LateUpdate()
        {
            if (ngBroken || ngPanels.Count == 0) return;
            try
            {
                ngPanels.RemoveAll(p => p.tel == null || p.eng == null || p.a == null);
                foreach (var p in ngPanels)
                {
                    if (!p.tel.isActiveAndEnabled) continue;
                    float ng = DialMath.NgPct(p.eng.GetRPMRatio(), p.eng.GetPower(), p.eng.GetMaxPower(), p.a.airDensity);
                    if (p.needle != null) p.needle.localEulerAngles = Vector3.forward * (ng / 100f) * -300f;   // EngineTelemetry.Gauge.UpdateRPM scale
                    if (p.reading != null && p.text != null) p.text.SetValue(p.reading, $"{ng:F0}%");
                }
            }
            catch (System.Exception ex) { ngBroken = true; Logger.LogWarning("Ng display disabled: " + ex.Message); }
        }
    }
}
