// A6M2 round 4 (offline worker, 2026-11-18): the A6M2 Zero's period dials (Nimrod pattern, Nimrod.cs ScanNimrod / DriveNimrod).
//
// Movers (model: blender/a6m2/a6m2_cockpit.py, layout a6m2_ck_layout.py): gauge_<id>_needle (asi, alt (+ _needle_short), vsi, rpm, boost,
// oilp, oilt, fuel, turn), gauge_turn_slip (ball), gauge_horizon_card (rolls with the bank, slides with the pitch), gauge_compass_card
// (drum, local +X = up). Needles: local +X (Unity) toward the pilot, rest = the scale's first value, + angle = clockwise as seen by the pilot.
// Value -> angle maps in A6M2Math (pure functions, mirrored in tools/stub_tests_a6m2_r4.py against a6m2_ck_layout.SCALES / DIALS).
// Sources: TAS + air density (EAS), altitude (GlobalY), rb velocity (climb), the propeller's governed rpm ratio (TurbineEngine rpm is constant
// while running, Dials184.cs), throttle x rpm (boost), lagged power (oil temperature), fuel level, yaw rate, apparent gravity (slip), attitude.
// Registered by the 2 s discovery pass (Scan1810.cs step 6); no scene search of its own. Reads only the aircraft's own state; writes only
// transforms named gauge_* inside an A6M2.
// Flag: config [A6M2] Dials = Auto (build default OFF until probe P2 passes) / On / Off. Any exception detaches that aircraft.
// SHIP GATE: file named A6M2* (left out of the public tree); called through partial methods declared in Nimrod.cs.
using System.Collections.Generic;
using UnityEngine;

namespace B25H.Instruments
{
    public static class A6M2Math
    {
        public const string Key = "A6M2";
        public const float AsiSweep = 330f, AsiMaxKt = 350f;
        public const float RpmSweep = 300f, RpmMax = 3500f, RatedRpm = 2550f;
        public const float BoostSweep = 270f, BoostMin = -400f, BoostMax = 200f;      // mmHg
        public const float OilPSweep = 270f, OilPMax = 10f, OilTSweep = 270f, OilTMax = 120f, FuelSweep = 270f;
        public const float VsiDegPerMs = 7.5f, VsiMax = 20f;
        public const float TurnDegPerDps = 10f, TurnMax = 45f, SlipDegPerDeg = 1.5f, SlipMax = 28f;
        public const float HorizonMPerDeg = -0.0006f, HorizonPitchMax = 25f;

        static float Lin(float v, float v0, float v1, float sweep) => Mathf.Clamp01((v - v0) / (v1 - v0)) * sweep;
        public static float Asi(float tas, float rho) => Lin(tas * Mathf.Sqrt(Mathf.Max(rho, 0f) / 1.225f) * 1.943844f, 0f, AsiMaxKt, AsiSweep);
        public static float AltLong(float altM) => Mathf.Repeat(altM * 0.36f, 360f);           // 1,000 m a turn
        public static float AltShort(float altM) => Mathf.Repeat(altM * 0.036f, 360f);         // 10,000 m a turn
        public static float Vsi(float vs) => Mathf.Clamp(vs, -VsiMax, VsiMax) * VsiDegPerMs;
        public static float Rpm(float rpm) => Lin(rpm, 0f, RpmMax, RpmSweep);
        /// manifold pressure (mmHg, relative): idle -350, full +150 at the rated rpm (no supercharger model in the game)
        public static float BoostMmHg(float throttle, float rpmRatio, bool running) => running ? Mathf.Lerp(-350f, 150f, Mathf.Clamp01(throttle) * Mathf.Clamp01(rpmRatio)) : 0f;
        public static float Boost(float mm) => Lin(mm, BoostMin, BoostMax, BoostSweep);
        public static float OilKg(float rpmRatio, bool running) => running ? 2f + 4f * Mathf.Clamp01(rpmRatio) : 0f;
        public static float OilP(float kg) => Lin(kg, 0f, OilPMax, OilPSweep);
        public static float OilTTarget(float powerRatio, bool running) => running ? 50f + 35f * Mathf.Clamp01(powerRatio) : 15f;
        public static float OilT(float c) => Lin(c, 0f, OilTMax, OilTSweep);
        public static float Fuel(float level) => Mathf.Clamp01(level) * FuelSweep;
        public static float Turn(float yawRateDps) => Mathf.Clamp(yawRateDps * TurnDegPerDps, -TurnMax, TurnMax);
        public static float Slip(float downX, float downY) => Mathf.Clamp(-Mathf.Atan2(downX, Mathf.Max(-downY, 0.05f)) * Mathf.Rad2Deg * SlipDegPerDeg, -SlipMax, SlipMax);
        // r7 (game: heading 117 read "24 W" = 360 - 117): the drum's local +X rotation runs the other way from the Blender build's strip
        // (u = heading / 360 increasing to the pilot's right); +heading brings u = heading to the lubber line.
        public static float Compass(float headingDeg) => headingDeg;
        /// horizon card: rolls opposite the bank (the card stays level), slides down when the nose is up
        public static float HorizonRoll(float bankDeg) => -bankDeg;
        public static float HorizonOffset(float pitchDeg) => Mathf.Clamp(pitchDeg, -HorizonPitchMax, HorizonPitchMax) * HorizonMPerDeg;
        public static float Lag(float v, float target, float dt, float tau) => v + (target - v) * Mathf.Clamp01(dt / tau);
    }

    public partial class Plugin
    {
        const bool A6M2DialsDefault = A6M2DefaultsMath.On;   // r7: off unless built with A6M2_DEFAULTS_ON (handover build), A6M2Defaults.cs
        static BepInEx.Configuration.ConfigEntry<string> a6m2DialMode;
        static readonly string[] A6M2Names = { "gauge_asi_needle", "gauge_alt_needle", "gauge_alt_needle_short", "gauge_vsi_needle", "gauge_rpm_needle",
            "gauge_boost_needle", "gauge_oilp_needle", "gauge_oilt_needle", "gauge_fuel_needle", "gauge_turn_needle", "gauge_turn_slip",
            "gauge_horizon_card", "gauge_compass_card" };

        class A6M2Gauges
        {
            public Aircraft aircraft;
            public readonly Dictionary<string, Transform> t = new Dictionary<string, Transform>();
            public readonly Dictionary<string, Quaternion> rest = new Dictionary<string, Quaternion>();
            public Vector3 horizonPos;
            public TurbineEngine engine; public ConstantSpeedProp prop;
            public float oilT = 15f, slip; public Vector3 vPrev; public bool havePrev;
        }
        readonly Dictionary<Aircraft, A6M2Gauges> a6m2s = new Dictionary<Aircraft, A6M2Gauges>();
        readonly Dictionary<Aircraft, int> a6m2Misses = new Dictionary<Aircraft, int>();

        static bool A6M2DialsOn
        {
            get { var m = a6m2DialMode != null ? a6m2DialMode.Value : "Auto"; return m == "On" || (m != "Off" && A6M2DialsDefault); }
        }

        partial void ScanA6M2()
        {
            if (a6m2DialMode == null) { a6m2DialMode = Config.Bind("A6M2", "Dials", "Auto", "A6M2: drive the period cockpit dials. " + A6M2DefaultsMath.AutoText); A6M2MigrateKey(a6m2DialMode); }
            if (!A6M2DialsOn) return;
            foreach (var a in PassAircraft())
            {
                if (a == null || a6m2s.ContainsKey(a) || a.definition == null || a.definition.jsonKey != A6M2Math.Key) continue;
                var g = new A6M2Gauges { aircraft = a };
                var all = new HashSet<Transform>(a.GetComponentsInChildren<Transform>(true));
                if (a.partLookup != null) foreach (var part in a.partLookup) if (part != null) foreach (var pt in part.GetComponentsInChildren<Transform>(true)) all.Add(pt);
                foreach (var tr in all)
                {
                    if (System.Array.IndexOf(A6M2Names, tr.name) >= 0 && !g.t.ContainsKey(tr.name)) { g.t[tr.name] = tr; g.rest[tr.name] = tr.localRotation; if (tr.name == "gauge_horizon_card") g.horizonPos = tr.localPosition; }
                    if (g.engine == null) g.engine = tr.GetComponent<TurbineEngine>();
                    if (g.prop == null) g.prop = tr.GetComponent<ConstantSpeedProp>();
                }
                if (g.t.Count == 0) { a6m2Misses.TryGetValue(a, out var m); a6m2Misses[a] = m + 1; if (m + 1 < 10) continue; }
                a6m2s[a] = g;
                Logger.LogInfo($"A6M2 dials attached to {a.name}: {g.t.Count}/{A6M2Names.Length} movers, engine {(g.engine != null)}, prop {(g.prop != null)}");
            }
        }

        partial void DriveA6M2All()
        {
            if (a6m2s.Count == 0) return;
            List<Aircraft> dead = null;
            foreach (var kv in a6m2s)
            {
                if (kv.Key == null) { (dead = dead ?? new List<Aircraft>()).Add(kv.Key); continue; }
                try { DriveA6M2(kv.Value); } catch (System.Exception e) { Logger.LogWarning("A6M2 dials: " + e.Message); (dead = dead ?? new List<Aircraft>()).Add(kv.Key); }
            }
            if (dead != null) foreach (var a in dead) a6m2s.Remove(a);
        }

        static void SetA(A6M2Gauges g, string n, float deg)
        {
            if (g.t.TryGetValue(n, out var tr) && tr != null) tr.localRotation = g.rest[n] * Quaternion.AngleAxis(deg, Vector3.right);
        }

        void DriveA6M2(A6M2Gauges g)
        {
            var a = g.aircraft;
            if (a.disabled) return;
            var tr = a.transform;
            float dt = Mathf.Max(Time.deltaTime, 1e-4f);
            SetA(g, "gauge_asi_needle", A6M2Math.Asi(a.speed, a.airDensity));
            float altM = tr.position.GlobalY();
            SetA(g, "gauge_alt_needle", A6M2Math.AltLong(altM));
            SetA(g, "gauge_alt_needle_short", A6M2Math.AltShort(altM));
            var e = g.engine;
            float rpmRatio = g.prop != null ? g.prop.GetRPMRatio() : e != null ? e.GetRPMRatio() : 0f;
            bool running = e != null && e.GetRPMRatio() > 0.05f && rpmRatio > 0.05f;
            SetA(g, "gauge_rpm_needle", A6M2Math.Rpm(DialMath.EngineRpm(rpmRatio, A6M2Math.RatedRpm)));
            SetA(g, "gauge_boost_needle", A6M2Math.Boost(A6M2Math.BoostMmHg(e != null ? e.throttle : 0f, rpmRatio, running)));
            SetA(g, "gauge_oilp_needle", A6M2Math.OilP(A6M2Math.OilKg(rpmRatio, running)));
            g.oilT = A6M2Math.Lag(g.oilT, A6M2Math.OilTTarget(e != null ? e.powerRatio : 0f, running), dt, 60f);
            SetA(g, "gauge_oilt_needle", A6M2Math.OilT(g.oilT));
            SetA(g, "gauge_fuel_needle", A6M2Math.Fuel(a.GetFuelLevel()));
            var rb = a.rb;
            if (rb != null)
            {
                SetA(g, "gauge_vsi_needle", A6M2Math.Vsi(rb.velocity.y));
                SetA(g, "gauge_turn_needle", A6M2Math.Turn(rb.angularVelocity.y * Mathf.Rad2Deg));
                var v = rb.velocity;
                var acc = g.havePrev ? (v - g.vPrev) / dt : Vector3.zero;
                g.vPrev = v; g.havePrev = true;
                var down = tr.InverseTransformDirection(Physics.gravity - acc);
                g.slip = Mathf.Lerp(g.slip, A6M2Math.Slip(down.x, down.y), Mathf.Clamp01(dt * 4f));
                SetA(g, "gauge_turn_slip", g.slip);
            }
            var eu = tr.eulerAngles;
            float bank = Mathf.DeltaAngle(0f, eu.z), pitch = -Mathf.DeltaAngle(0f, eu.x);
            if (g.t.TryGetValue("gauge_horizon_card", out var hc) && hc != null)
            {
                hc.localRotation = g.rest["gauge_horizon_card"] * Quaternion.AngleAxis(A6M2Math.HorizonRoll(-bank), Vector3.right);
                hc.localPosition = g.horizonPos + hc.parent.InverseTransformDirection(tr.up) * A6M2Math.HorizonOffset(pitch);
            }
            SetA(g, "gauge_compass_card", A6M2Math.Compass(eu.y));
        }
    }
}
