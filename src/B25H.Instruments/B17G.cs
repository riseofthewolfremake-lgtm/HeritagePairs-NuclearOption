// B25H.Instruments 1.6.0: B-17G Flying Fortress (jsonKey B17G) cockpit needles and cards. Separate from every other branch:
// B-25H (Plugin.cs), Nimrod Mk I / FD-32 (Nimrod.cs, FD32Tac.cs) are unchanged. Reads only the B-17G's own public state and writes only
// transforms named gauge_* inside a B17G aircraft (B-25H convention: local +X points at the pilot, rest = 12 o'clock, +deg about +X =
// clockwise seen by the pilot). Per-engine needles read each engine's own TurbineEngine (part engine_1..4), so an engine-out shows.
using System.Collections.Generic;
using UnityEngine;

namespace B25H.Instruments
{
    public static class B17GMath
    {
        public const string Key = "B17G";
        // 1.8.9 (offline J, user on 1.8.8: "The WHEEL moves, the stick does not"): the control columns pitch about their floor pivot and carry
        // the wheel; the wheel turns for roll about its own hub axis. Both transforms come from the model with local +X = the rotation axis
        // (column: the lateral axis through the floor pivot, b17g_cockpit.anchors axis_frame((1, 0, 0)); wheel: the hub axis toward the
        // pilot, axis_frame(toward)). The build no longer puts the wheels on Cockpit.joysticks (b17g_joystick.cs ColumnPlugin189), so
        // nothing else writes them. Signs (unity/Editor/ColumnCheck189.cs proves them on the built prefab): ControlInputs.pitch +1 = pull
        // was WRONG in 1.8.9-1.8.11 (user on 1.8.11: pull moved the column forward). 1.8.12: ControlInputs.pitch > 0 = PUSH (ControlsFilter 241 vs
        // localAngularVelocity.x, +X rotation = nose down; the stock CI-22 Cockpit.Joystick uses localEulerAngles.x = +pitch x range), and a
        // Unity +angle about the right axis tilts the top forward -> column = +pitch x range (push = forward, pull = aft);
        // + angle about the axis toward the pilot = clockwise seen by the pilot -> wheel = +roll x range (roll right = clockwise).
        public const float ColumnRange = 12f, WheelRange = 30f;
        public static float ColumnDeg(float pitch) => Mathf.Clamp(pitch, -1f, 1f) * ColumnRange;
        public static float WheelDeg(float roll) => Mathf.Clamp(roll, -1f, 1f) * WheelRange;
        // dial calibrations matched to the fal dial faces (b17g_gauges atlas)
        public static float Asi(float mps) { float mph = mps * 2.23694f; return mph < 40f ? 0f : Mathf.Min((mph - 40f) / 360f * 330f, 330f); }
        public static float AltLong(float m) => Mathf.Repeat(m * 3.28084f * 0.36f, 360f);          // 1,000 ft per turn
        public static float AltShort(float m) => Mathf.Repeat(m * 3.28084f * 0.036f, 360f);        // 10,000 ft per turn
        public static float Vsi(float vy) { float fpm = Mathf.Clamp(vy * 196.85f, -6000f, 6000f); return -90f + fpm / 6000f * 170f; }   // 0 at 9 o'clock
        public static float Turn(float yawDegPerS) => Mathf.Clamp(yawDegPerS * 10f, -45f, 45f);
        public static float Card(float headingDeg) => -headingDeg;
        public static float Mp(float throttle, float rpmRatio, float density, bool running)
        {   // inHg: idle ~15, take-off 46 at sea level, falling with density (no turbo-supercharger in the game)
            if (!running) return density / 1.225f * 29.9f;
            return Mathf.Lerp(15f, 46f, Mathf.Clamp01(throttle)) * Mathf.Lerp(0.6f, 1f, Mathf.Clamp01(density / 1.225f)) * Mathf.Lerp(0.85f, 1f, Mathf.Clamp01(rpmRatio));
        }
        public static float MpDeg(float inHg) => Mathf.Clamp((inHg - 40f) * 5.5f, -165f, 165f);   // 40 inHg at 12 o'clock
        public static float RpmDeg(float rpm) => Mathf.Clamp(-165f + rpm / 3500f * 330f, -165f, 165f);
        public const float RatedRpm = 2500f;     // 1.8.4: R-1820-97 take-off rpm at prop rpm ratio 1 (governed)
        // 1.8.4 formerly static dials (fal faces without needles; angles measured on the b17g_gauges cells, clockwise from 12 o'clock)
        static readonly float[] SucV = { 0f, 1f, 2f, 4f, 5f, 6f, 7f, 8f, 9f, 10f }, SucA = { -142f, -106f, -74f, -39f, 0f, 37f, 72f, 109f, 142f, 180f };
        public static float SuctionDeg(float inHg)
        {
            float v = Mathf.Clamp(inHg, 0f, 10f);
            for (int i = 1; i < SucV.Length; i++) if (v <= SucV[i]) return Mathf.Lerp(SucA[i - 1], SucA[i], (v - SucV[i - 1]) / (SucV[i] - SucV[i - 1]));
            return SucA[SucA.Length - 1];
        }
        public static float EguFuelDeg(float psi) => DialMath.Lin(psi, 0f, 20f, -78f, 156f);
        public static float EguOilPDeg(float psi) => DialMath.Lin(psi, 0f, 100f, -149f, 282f);
        public static float EguOilTDeg(float c) => DialMath.Lin(c, 0f, 140f, -149f, 282f);
        public static float OilTDeg(float c) => DialMath.Lin(c, -70f, 150f, -140f, 280f);
        public static float FuelPsi(float rpmRatio, bool running) => running ? 15f * Mathf.Clamp01(rpmRatio / 0.5f) : 0f;
        public const float FuelTau = 1.5f;      // 1.8.6: s, pressure lag of the EGU fuel needles (now the rise only)
        // 1.8.7 (in game 1.8.6, ingame_18617fp.txt: 5.5 / 2.0 / 0.5 / 0.0 psi at +2.7 / +3.9 / +6.3 / +9.8 s after ignition off = the 1.5 s exponential
        // after ~1.2 s of command / sync delay): with the pump stopped the pressure bleeds at a fixed rate, 15 psi -> 0 in 1.0 s
        public const float FuelFallPsiPerS = 15f;
        public static float FuelStep(float cur, float target, float dt) => target < cur ? Mathf.MoveTowards(cur, target, FuelFallPsiPerS * dt) : Lag(cur, target, dt, FuelTau);
        public static float OilTTarget(float powerRatio, bool running, float oat) => running ? 50f + 35f * Mathf.Clamp01(powerRatio) : oat;
        public static float ChtTarget(float powerRatio, bool running) => running ? 120f + 110f * Mathf.Clamp01(powerRatio) : 15f;
        public static float ChtDeg(float c) => Mathf.Clamp(-135f + c / 350f * 270f, -135f, 135f);
        public static float Lag(float v, float target, float dt, float tau) => v + (target - v) * Mathf.Clamp01(dt / tau);
    }

    public partial class Plugin
    {
        class B17GGauges
        {
            public Aircraft aircraft;
            public readonly Dictionary<string, Transform> t = new Dictionary<string, Transform>();
            public readonly Dictionary<string, Quaternion> rest = new Dictionary<string, Quaternion>();
            public readonly TurbineEngine[] eng = new TurbineEngine[5];
            public readonly ConstantSpeedProp[] prop = new ConstantSpeedProp[5];   // 1.8.4: rpm source
            public readonly float[] oilT = { 15f, 15f, 15f, 15f, 15f };
            public readonly float[] cht = { 15f, 15f, 15f, 15f, 15f };
            public readonly float[] fuelP = new float[5];   // 1.8.6: lagged EGU fuel pressure (psi)
            public readonly Transform[] col = new Transform[2], yoke = new Transform[2];     // 1.8.9: L, R
            public readonly Quaternion[] colRest = new Quaternion[2], yokeRest = new Quaternion[2];
        }
        static readonly string[] B17GColumnNames = { "cockpit_column_L", "cockpit_column_R", "cockpit_yoke_L", "cockpit_yoke_R" };
        static readonly string[] B17GNames = {
            "gauge_asi_needle", "gauge_alt_needle", "gauge_alt_needle_short", "gauge_vsi_needle", "gauge_turn_needle", "gauge_dg_card", "gauge_att_card",
            "gauge_mp_1_needle", "gauge_mp_2_needle", "gauge_mp_3_needle", "gauge_mp_4_needle", "gauge_rpm_1_needle", "gauge_rpm_2_needle", "gauge_rpm_3_needle", "gauge_rpm_4_needle",
            "gauge_cht_1_needle", "gauge_cht_2_needle", "gauge_cht_3_needle", "gauge_cht_4_needle",
            // 1.8.4: the formerly static dials (21)
            "gauge_suction_needle", "gauge_hyd_needle", "gauge_clock_needle", "gauge_clock_needle_short", "gauge_clock_sec_needle",
            "gauge_egu_1_fuel_needle", "gauge_egu_1_oilp_needle", "gauge_egu_1_oilt_needle", "gauge_egu_2_fuel_needle", "gauge_egu_2_oilp_needle", "gauge_egu_2_oilt_needle",
            "gauge_egu_3_fuel_needle", "gauge_egu_3_oilp_needle", "gauge_egu_3_oilt_needle", "gauge_egu_4_fuel_needle", "gauge_egu_4_oilp_needle", "gauge_egu_4_oilt_needle",
            "gauge_oilt_1_needle", "gauge_oilt_2_needle", "gauge_oilt_3_needle", "gauge_oilt_4_needle" };
        readonly Dictionary<Aircraft, B17GGauges> b17gs = new Dictionary<Aircraft, B17GGauges>();
        readonly Dictionary<Aircraft, int> b17gMisses = new Dictionary<Aircraft, int>();

        void ScanB17G()
        {
            foreach (var a in PassAircraft())
            {
                if (a == null || b17gs.ContainsKey(a) || a.definition == null || a.definition.jsonKey != B17GMath.Key) continue;
                var g = new B17GGauges { aircraft = a };
                var all = new HashSet<Transform>(a.GetComponentsInChildren<Transform>(true));
                if (a.partLookup != null)
                    foreach (var part in a.partLookup)
                        if (part != null) foreach (var pt in part.GetComponentsInChildren<Transform>(true)) all.Add(pt);
                foreach (var tr in all)
                {
                    if (System.Array.IndexOf(B17GNames, tr.name) >= 0 && !g.t.ContainsKey(tr.name)) { g.t[tr.name] = tr; g.rest[tr.name] = tr.localRotation; }
                    int ci = System.Array.IndexOf(B17GColumnNames, tr.name);     // 1.8.9 columns / wheels (the originals; their _int copies are children)
                    if (ci >= 0 && ci < 2 && g.col[ci] == null) { g.col[ci] = tr; g.colRest[ci] = tr.localRotation; }
                    if (ci >= 2 && g.yoke[ci - 2] == null) { g.yoke[ci - 2] = tr; g.yokeRest[ci - 2] = tr.localRotation; }
                    if (tr.name.StartsWith("engine_") && tr.name.Length == 8 && int.TryParse(tr.name.Substring(7), out int n) && n >= 1 && n <= 4)
                    { var te = tr.GetComponent<TurbineEngine>(); if (te != null) g.eng[n] = te; }
                    if (tr.name.StartsWith("prop_") && tr.name.Length == 6 && int.TryParse(tr.name.Substring(5), out int pn) && pn >= 1 && pn <= 4)
                    { var cp = tr.GetComponent<ConstantSpeedProp>(); if (cp != null) g.prop[pn] = cp; }
                }
                if (g.t.Count == 0)
                {
                    b17gMisses.TryGetValue(a, out var m); b17gMisses[a] = m + 1;
                    if (m + 1 < 10) continue;
                }
                b17gs[a] = g;
                int engines = 0, props = 0; for (int i = 1; i <= 4; i++) { if (g.eng[i] != null) engines++; if (g.prop[i] != null) props++; }
                Logger.LogInfo($"B-17G instruments attached to {a.name}: {g.t.Count}/{B17GNames.Length} movers, {engines}/4 engines, {props}/4 props, columns {(g.col[0] != null ? 1 : 0) + (g.col[1] != null ? 1 : 0)}/2, wheels {(g.yoke[0] != null ? 1 : 0) + (g.yoke[1] != null ? 1 : 0)}/2");
            }
        }

        void DriveB17GAll()
        {
            if (b17gs.Count == 0) return;
            List<Aircraft> dead = null;
            foreach (var kv in b17gs)
            {
                if (kv.Key == null) { (dead = dead ?? new List<Aircraft>()).Add(kv.Key); continue; }
                try { DriveB17G(kv.Value); } catch (System.Exception e) { Logger.LogWarning("B-17G gauges: " + e.Message); (dead = dead ?? new List<Aircraft>()).Add(kv.Key); }
            }
            if (dead != null) foreach (var a in dead) b17gs.Remove(a);
        }

        static void SetB(B17GGauges g, string n, float deg)
        {
            if (g.t.TryGetValue(n, out var tr) && tr != null) tr.localRotation = g.rest[n] * Quaternion.AngleAxis(deg, Vector3.right);
        }

        void DriveB17G(B17GGauges g)
        {
            var a = g.aircraft;
            if (a.disabled) return;
            var tr = a.transform;
            float dt = Mathf.Max(Time.deltaTime, 1e-4f);
            var ci = a.GetInputs();                                       // 1.8.9: columns pitch, wheels roll (the same inputs Cockpit.joysticks reads)
            if (ci != null)
                for (int s = 0; s < 2; s++)
                {
                    if (g.col[s] != null) g.col[s].localRotation = g.colRest[s] * Quaternion.AngleAxis(B17GMath.ColumnDeg(ci.pitch), Vector3.right);
                    if (g.yoke[s] != null) g.yoke[s].localRotation = g.yokeRest[s] * Quaternion.AngleAxis(B17GMath.WheelDeg(ci.roll), Vector3.right);
                }
            SetB(g, "gauge_asi_needle", B17GMath.Asi(a.speed));
            float altM = tr.position.GlobalY();
            SetB(g, "gauge_alt_needle", B17GMath.AltLong(altM));
            SetB(g, "gauge_alt_needle_short", B17GMath.AltShort(altM));
            var rb = a.rb;
            if (rb != null)
            {
                SetB(g, "gauge_vsi_needle", B17GMath.Vsi(rb.velocity.y));
                SetB(g, "gauge_turn_needle", B17GMath.Turn(rb.angularVelocity.y * Mathf.Rad2Deg));
            }
            var e = tr.eulerAngles;
            SetB(g, "gauge_dg_card", B17GMath.Card(e.y));
            float bank = e.z > 180f ? e.z - 360f : e.z;
            SetB(g, "gauge_att_card", bank);
            float oat = DialMath.OatC(altM, a.speed), maxRatio = 0f;
            bool anyRunning = false;
            for (int n = 1; n <= 4; n++)
            {
                var en = g.eng[n];
                // 1.8.4 (in game 1.8.2: rpm needles fixed while the props went 1291 -> 1210): TurbineEngine rpm is constant while running
                // (TurbineEngine.cs:286); the engine rpm follows the propeller shaft (ConstantSpeedProp RPM / rpmLimit)
                float ratio = g.prop[n] != null ? g.prop[n].GetRPMRatio() : en != null ? en.GetRPMRatio() : 0f;
                bool running = en != null && en.GetRPMRatio() > 0.05f && ratio > 0.05f;
                anyRunning |= running; if (running) maxRatio = Mathf.Max(maxRatio, ratio);
                SetB(g, $"gauge_mp_{n}_needle", B17GMath.MpDeg(B17GMath.Mp(en != null ? en.throttle : 0f, ratio, a.airDensity, running)));
                SetB(g, $"gauge_rpm_{n}_needle", B17GMath.RpmDeg(DialMath.EngineRpm(ratio, B17GMath.RatedRpm)));
                // 1.8.6: the engine-driven fuel pump stops with the ignition / fuel / engine (EngineLive, Dials186.cs); the prop windmills on for
                // tens of seconds after the ignition is cut (in game 1.8.4: 832 rpm at OFF + 12 s), so the rpm ratio alone kept 15 psi
                g.fuelP[n] = B17GMath.FuelStep(g.fuelP[n], B17GMath.FuelPsi(ratio, running && EngineLive(a, en)), dt);   // 1.8.7: fixed-rate fall
                SetB(g, $"gauge_egu_{n}_fuel_needle", B17GMath.EguFuelDeg(g.fuelP[n]));
                SetB(g, $"gauge_egu_{n}_oilp_needle", B17GMath.EguOilPDeg(DialMath.OilPsi(ratio, running, 45f, 75f)));
                g.oilT[n] = B17GMath.Lag(g.oilT[n], B17GMath.OilTTarget(en != null ? en.powerRatio : 0f, running, oat), dt, 60f);
                SetB(g, $"gauge_egu_{n}_oilt_needle", B17GMath.EguOilTDeg(g.oilT[n]));
                SetB(g, $"gauge_oilt_{n}_needle", B17GMath.OilTDeg(g.oilT[n]));
                g.cht[n] = B17GMath.Lag(g.cht[n], B17GMath.ChtTarget(en != null ? en.powerRatio : 0f, running), dt, 50f);
                SetB(g, $"gauge_cht_{n}_needle", B17GMath.ChtDeg(g.cht[n]));
            }
            SetB(g, "gauge_suction_needle", B17GMath.SuctionDeg(anyRunning ? DialMath.Suction(maxRatio) : 0f));
            SetB(g, "gauge_hyd_needle", B17GMath.SuctionDeg(anyRunning ? DialMath.Suction(maxRatio) : 0f));   // the far-left twin (same fal suction face)
            float h = TimeOfDayHours();
            SetB(g, "gauge_clock_needle", DialMath.ClockMinDeg(h));
            SetB(g, "gauge_clock_needle_short", DialMath.ClockHourDeg(h));
            SetB(g, "gauge_clock_sec_needle", DialMath.ClockSecDeg(h));
        }
    }
}
