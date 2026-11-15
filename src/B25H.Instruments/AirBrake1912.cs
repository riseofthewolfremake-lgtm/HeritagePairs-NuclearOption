// 1.9.12 AirbrakeIdle1912 + HudAirbrake1912: the stock Airbrake of our six aircraft is on whenever the throttle is under 5 %, and the HUD says so.
//
// The owner's rule: "whenever the throttle is below 5 % the airbrakes are on, does not matter if it is on the ground or sky".
//
// The game (decompiled Airbrake.cs, read for this file): Airbrake.Update opens the brake while ControlInputs.throttle == 0 EXACTLY (openAmount
// moves by openSpeed x dt, 0..1, anything else closes it at the same rate) and turns its hinge transforms; Airbrake.FixedUpdate applies
// dragAmount x airDensity x V^2 x openAmount against the part's world velocity. There is no ground test in the game and none here: a parked
// aircraft at idle stands with the brake open (as every stock aircraft with an airbrake does), it is open on the landing roll, on the lift
// and on the deck. The pack (1.9.12) puts that stock component on all six of our aircraft.
//
// Rule: a Harmony prefix on Airbrake.Update, for aircraft whose definition.jsonKey is one of ours only. While 0 < throttle < threshold the
// prefix adds 2 x openSpeed x dt to openAmount; the stock Update then takes 1 x openSpeed x dt off (its "throttle is not 0" branch) and clamps:
// the net result is the stock "throttle exactly 0" behaviour (opens at openSpeed, stays at 1, panels out, constraints and sound on, drag from
// the stock FixedUpdate). At throttle exactly 0 and at throttle >= threshold the prefix adds nothing: the stock code alone decides. Nothing is
// replaced: the stock Update and FixedUpdate run every frame, the prefix touches one private float and no transform (so an Airbrake with zero
// transforms is fine), and it only READS the shared ControlInputs, so the player, the AI and the autopilot are treated alike (whatever wrote
// the throttle). No weight-on-wheels, no radar altitude, no state between frames.
//
// HUD: ThrottleGauge.UpdateThrottleDisplay (decompiled) prints "AIRBRAKE" only at throttle == 0 exactly: the COIN gauge (B25H / NIMROD1 /
// B17G / MSB17: no regions) when its serialized flag ThrottleGauge.airbrake is set, the KR-67 gauge (GA25X / FD32) from its region that is
// active at 0 and is called "AIRBRAKE". Both are kept (flag set / region name kept, so throttle 0 reads AIRBRAKE with stock code alone), and
// a Harmony postfix on UpdateThrottleDisplay overwrites the reading with the same text while 0 <= throttle < threshold on OUR registered
// gauges: the text always agrees with what the brake is told to do. Up to 1.9.11 GA25X / FD32 read "IDLE" there (no airbrake); an aircraft
// WITHOUT an Airbrake component (pack built with the airbrake flags off) still gets exactly the 1.9.11 texts ("0%" / "IDLE").
//
// Config [Airbrake]: AirbrakeIdle1912 (Auto = build default = on, On, Off = stock: opens at throttle exactly 0 only), AirbrakeThrottle1912
// (0.05; 0..0.2; 0 = stock exact-zero behaviour), HudAirbrake1912 (Auto / On / Off = the 1.9.11 texts). Any exception switches that piece
// off for the session and leaves the stock component running. Pure laws in AirbrakeIdleMath (mirrored in tools/stub_tests_1912_plugin.py).
using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class AirbrakeIdleMath
    {
        public const float DefaultThreshold = 0.05f;   // the owner's 5 %
        public const float MaxThreshold = 0.2f;        // config clamp; the stock parking brake / DeckHold198 let go at 0.1
        public const string HudText = "AIRBRAKE";      // the game's own text (ThrottleGauge.UpdateThrottleDisplay)

        public static bool IsKey(string k) => k == "B25H" || k == "GA25X" || k == "NIMROD1" || k == "FD32" || k == "B17G" || k == "MSB17";
        /// the four on the stock COIN HUD (no throttle regions): the gauge's airbrake flag is set
        public static bool IsCoinHudKey(string k) => k == "B25H" || k == "NIMROD1" || k == "B17G" || k == "MSB17";

        /// the threshold in force: 0 (= stock) with the switch off or a bad value, else the config value clamped to 0..MaxThreshold
        public static float Threshold(bool on, float cfg) => !on || float.IsNaN(cfg) ? 0f : Mathf.Clamp(cfg, 0f, MaxThreshold);
        /// is the brake told to open: the stock test (exactly 0) or under the threshold. NaN = no.
        public static bool Commanded(float throttle, float threshold) => throttle == 0f || (threshold > 0f && throttle < threshold);
        /// what the prefix adds to Airbrake.openAmount before the stock Update takes openSpeed x dt off (only where stock would close and the rule opens)
        public static float Lift(float throttle, float threshold, float openSpeed, float dt) => throttle != 0f && threshold > 0f && throttle < threshold ? 2f * openSpeed * dt : 0f;
        /// HUD: does the postfix overwrite the reading (throttle 0 itself is the stock flag / region; overwriting it with the same text is harmless)
        public static bool HudOverrides(bool hudOn, float throttle, float threshold) => hudOn && threshold > 0f && throttle < threshold;
    }

    public partial class Plugin
    {
        const bool AirbrakeIdleDefault1912 = true;    // build flag AirbrakeIdle1912
        const bool HudAirbrakeDefault1912 = true;     // build flag HudAirbrake1912
        const string IdleText1912 = "IDLE";           // the 1.2.0 text of the KR-67 gauge's 0 region on an aircraft without an airbrake
        BepInEx.Configuration.ConfigEntry<string> airbrakeIdleMode, hudAirbrakeMode;
        BepInEx.Configuration.ConfigEntry<float> airbrakeThrottle;
        static float brakeThr1912;                    // the threshold in force this frame (0 = stock): switch, config, hook state
        static bool brakeBroken1912, brakeHooked1912, hudTextOn1912, hudTextBroken1912;
        bool hudBrakeBroken1912, brakePatched1912;
        static int brakeNewLogs1912, brakeLogs1912;

        bool AirbrakeIdleOn { get { var m = airbrakeIdleMode != null ? airbrakeIdleMode.Value : "Auto"; return m == "On" || (m != "Off" && AirbrakeIdleDefault1912); } }
        bool HudAirbrakeOn { get { var m = hudAirbrakeMode != null ? hudAirbrakeMode.Value : "Auto"; return m == "On" || (m != "Off" && HudAirbrakeDefault1912); } }

        class Idle1912 { public Aircraft a; public bool cmd, seen; public int logs; }
        static readonly Dictionary<Airbrake, Idle1912> idleOf1912 = new Dictionary<Airbrake, Idle1912>();   // value null = not one of ours (stock: untouched)
        float nextBrakePrune1912;

        /// once, from the first Update (the first frame after load, in the menu; Nimrod.cs with Awake stays byte-identical to 1.9.11): bind the
        /// config entries (so they appear in the cfg at load) and hook Airbrake.Update and ThrottleGauge.UpdateThrottleDisplay
        void PatchAirbrake1912()
        {
            airbrakeIdleMode = Config.Bind("Airbrake", "AirbrakeIdle1912", "Auto", "1.9.12: the airbrake of the six Heritage Pairs aircraft is on whenever the throttle is under AirbrakeThrottle1912 (5 %), on the ground and in the air alike, player and AI (the game opens it at exactly 0 % only). Stock aircraft are not touched. Auto = build default (on), On, Off (= stock: opens at exactly 0 % only).");
            airbrakeThrottle = Config.Bind("Airbrake", "AirbrakeThrottle1912", AirbrakeIdleMath.DefaultThreshold, new BepInEx.Configuration.ConfigDescription("1.9.12: throttle under which the airbrake of the Heritage Pairs aircraft is on (0.05 = 5 %). 0 = the game's own behaviour (exactly 0 % only). At this value and above it closes, as stock.", new BepInEx.Configuration.AcceptableValueRange<float>(0f, AirbrakeIdleMath.MaxThreshold)));
            hudAirbrakeMode = Config.Bind("Airbrake", "HudAirbrake1912", "Auto", "1.9.12: the throttle gauge of the Heritage Pairs aircraft that have an airbrake reads AIRBRAKE whenever the airbrake is on (throttle under AirbrakeThrottle1912), on the ground and in the air (B-25H, Nimrod Mk I, B-17G, MSB-17: instead of 0% .. 4%; GA-25X, FD-32: instead of IDLE). Auto = build default (on), On, Off (= the 1.9.11 texts).");
            try
            {
                var t = typeof(Airbrake);
                var m = HarmonyLib.AccessTools.Method(t, "Update");
                string missing = m == null ? "Update" : null;
                foreach (var f in new[] { "openAmount", "openSpeed", "attachedAircraft", "controlInputs" })
                    if (t.GetField(f, BFI) == null) missing = (missing == null ? "" : missing + ", ") + f;
                if (missing != null) Logger.LogWarning("1.9.12 airbrake idle rule disabled: Airbrake." + missing + " not found (the airbrake stays stock: it opens at throttle exactly 0 only)");
                else
                {
                    new HarmonyLib.Harmony("b25h.instruments.airbrake1912").Patch(m, prefix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(AirbrakeUpdatePrefix1912), BindingFlags.Static | BindingFlags.NonPublic)));
                    brakeHooked1912 = true;
                }
            }
            catch (Exception e) { Logger.LogWarning("1.9.12 airbrake idle rule disabled: " + e.Message); }
            try
            {
                var m = HarmonyLib.AccessTools.Method(typeof(ThrottleGauge), "UpdateThrottleDisplay");
                if (m == null || tgInputs1912 == null || tgReading1912 == null) { hudTextBroken1912 = true; Logger.LogWarning("1.9.12 HUD airbrake text under the threshold disabled: ThrottleGauge.UpdateThrottleDisplay / inputs / throttleReading not found (the gauge reads AIRBRAKE at throttle exactly 0 only)"); }
                else new HarmonyLib.Harmony("b25h.instruments.airbrakehud1912").Patch(m, postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(ThrottleTextPostfix1912), BindingFlags.Static | BindingFlags.NonPublic)));
            }
            catch (Exception e) { hudTextBroken1912 = true; Logger.LogWarning("1.9.12 HUD airbrake text under the threshold disabled: " + e.Message); }
            brakeThr1912 = ThresholdNow1912();
            Logger.LogInfo($"1.9.12 airbrake idle rule {(brakeHooked1912 ? "hooked on Airbrake.Update" : "NOT hooked")} (B25H, GA25X, NIMROD1, FD32, B17G, MSB17 only): {(brakeThr1912 > 0f ? $"ON, the brake is on under throttle {brakeThr1912:F3}, ground and air" : "OFF (switch, threshold 0 or no hook), stock airbrake: throttle exactly 0 only")}; HUD airbrake text {(HudAirbrakeOn ? (hudTextBroken1912 ? "ON at throttle 0 only (no gauge hook)" : "ON") : "OFF by config")}");
        }

        float ThresholdNow1912() => brakeHooked1912 && !brakeBroken1912 ? AirbrakeIdleMath.Threshold(AirbrakeIdleOn, airbrakeThrottle != null ? airbrakeThrottle.Value : AirbrakeIdleMath.DefaultThreshold) : 0f;

        static void AirbrakeUpdatePrefix1912(Airbrake __instance, ref float ___openAmount, float ___openSpeed, Aircraft ___attachedAircraft, ControlInputs ___controlInputs)
        {
            if (brakeBroken1912) return;
            try
            {
                if (!idleOf1912.TryGetValue(__instance, out var s))
                {
                    var a = ___attachedAircraft;
                    if (a == null || a.definition == null) return;                 // Start has not run / no definition yet: decide on a later frame
                    s = AirbrakeIdleMath.IsKey(a.definition.jsonKey) ? new Idle1912 { a = a } : null;
                    idleOf1912[__instance] = s;
                }
                if (s == null || ___controlInputs == null) return;                 // a stock aircraft, or no inputs: stock
                float thr = ___controlInputs.throttle, lim = brakeThr1912;
                bool cmd = AirbrakeIdleMath.Commanded(thr, lim);
                if (!s.seen)
                {
                    s.seen = true; s.cmd = cmd;
                    if (brakeNewLogs1912++ < 30) Log.LogInfo($"1.9.12 airbrake on {(s.a != null ? s.a.name : "?")} ({(s.a != null && s.a.definition != null ? s.a.definition.jsonKey : "?")}): on under throttle {lim:F3}; now throttle {thr:F3}, {(cmd ? "ON" : "off")}");
                }
                else if (cmd != s.cmd)
                {
                    s.cmd = cmd;
                    if (s.logs < 6 && brakeLogs1912 < 60 && s.a != null)
                    {
                        s.logs++; brakeLogs1912++;
                        Log.LogInfo($"1.9.12 airbrake {s.a.name}: {(cmd ? "ON" : "off")} at throttle {thr:F3} (limit {lim:F3}), open {___openAmount:F2}, speed {s.a.speed:F1} m/s, radar alt {s.a.radarAlt:F1} m");
                    }
                }
                ___openAmount += AirbrakeIdleMath.Lift(thr, lim, ___openSpeed, Time.deltaTime);
            }
            catch (Exception e) { brakeBroken1912 = true; brakeThr1912 = 0f; Log.LogWarning("1.9.12 airbrake idle rule disabled (the airbrake is stock from here: throttle exactly 0 only): " + e.Message); }
        }

        static bool HasAirbrake1912(Aircraft a)
        {
            if (a.GetComponentInChildren<Airbrake>(true) != null) return true;
            if (a.partLookup != null) foreach (var p in a.partLookup) if (p != null && p.GetComponentInChildren<Airbrake>(true) != null) return true;
            return false;
        }

        // ---- HUD
        class BrakeHud1912
        {
            public ThrottleGauge g; public Aircraft ac; public string key;
            public object region; public FieldInfo nameField; public string stockName;   // KR-67 gauge: the region at 0. null = COIN gauge (airbrake flag)
            public bool shows;                                                            // the gauge names the airbrake now (false = the 1.9.11 texts)
        }
        readonly List<BrakeHud1912> brakeHuds1912 = new List<BrakeHud1912>();
        static readonly Dictionary<ThrottleGauge, BrakeHud1912> brakeHudOf1912 = new Dictionary<ThrottleGauge, BrakeHud1912>();
        static readonly FieldInfo tgAircraft1912 = typeof(ThrottleGauge).GetField("aircraft", BFI), tgAirbrake1912 = typeof(ThrottleGauge).GetField("airbrake", BFI), tgPrev1912 = typeof(ThrottleGauge).GetField("throttlePrev", BFI),
            tgInputs1912 = typeof(ThrottleGauge).GetField("inputs", BFI), tgReading1912 = typeof(ThrottleGauge).GetField("throttleReading", BFI);
        static PropertyInfo tgText1912;

        /// after the gauge's own UpdateThrottleDisplay (it runs when the throttle changed): on OUR registered gauges the reading is the airbrake
        /// text while the throttle is under the threshold. Everything else (bar, pointer, colour, every other gauge) is as the game drew it.
        static void ThrottleTextPostfix1912(ThrottleGauge __instance)
        {
            if (hudTextBroken1912 || !hudTextOn1912 || brakeThr1912 <= 0f) return;
            try
            {
                if (!brakeHudOf1912.TryGetValue(__instance, out var e) || !e.shows) return;   // a stock aircraft's gauge, or ours without an Airbrake
                var ci = tgInputs1912.GetValue(__instance) as ControlInputs;
                if (ci == null || !AirbrakeIdleMath.HudOverrides(true, ci.throttle, brakeThr1912)) return;
                var reading = tgReading1912.GetValue(__instance);
                if (reading == null) return;
                if (tgText1912 == null) tgText1912 = reading.GetType().GetProperty("text", BindingFlags.Instance | BindingFlags.Public);
                tgText1912.SetValue(reading, e.region != null && !string.IsNullOrEmpty(e.stockName) ? e.stockName : AirbrakeIdleMath.HudText, null);
            }
            catch (Exception ex) { hudTextBroken1912 = true; Log.LogWarning("1.9.12 HUD airbrake text under the threshold disabled (AIRBRAKE at throttle exactly 0 only): " + ex.Message); }
        }

        /// from BoostLabels, once per gauge. region == null: a COIN gauge of B25H / NIMROD1 / B17G / MSB17. Returns true when the gauge is driven here
        /// (the caller then leaves a region called AIRBRAKE alone instead of renaming it IDLE).
        bool RegisterBrakeHud1912(ThrottleGauge g, Aircraft ac, object region, FieldInfo nameField)
        {
            if (hudBrakeBroken1912 || !HudAirbrakeOn) return false;
            try
            {
                if (!HasAirbrake1912(ac)) return false;                           // pack without the airbrake: the 1.9.11 texts
                if (region == null && tgAirbrake1912 == null) { hudBrakeBroken1912 = true; Logger.LogWarning("1.9.12 HUD airbrake text disabled: ThrottleGauge.airbrake not found"); return false; }
                var e = new BrakeHud1912 { g = g, ac = ac, key = ac.definition.jsonKey, region = region, nameField = nameField, shows = true };
                if (region != null) e.stockName = nameField.GetValue(region) as string;
                else tgAirbrake1912.SetValue(g, true);                           // stock text "AIRBRAKE" at throttle exactly 0
                brakeHuds1912.Add(e); brakeHudOf1912[g] = e;
                tgPrev1912?.SetValue(g, -1f);                                     // redraw on the gauge's next Refresh
                Logger.LogInfo($"1.9.12 HUD: {e.key} throttle gauge reads AIRBRAKE while the airbrake is on (throttle under {brakeThr1912:F3}{(brakeThr1912 > 0f ? "" : " = exactly 0 only")}), ground and air {(region != null ? "(stock region name kept, no IDLE)" : "(stock COIN gauge flag set)")}");
                return true;
            }
            catch (Exception ex) { hudBrakeBroken1912 = true; Logger.LogWarning("1.9.12 HUD airbrake text disabled: " + ex.Message); return false; }
        }

        void SetBrakeHud1912(BrakeHud1912 e, bool shows)
        {
            if (e.region != null) e.nameField.SetValue(e.region, shows ? e.stockName : IdleText1912);
            else tgAirbrake1912.SetValue(e.g, shows);
            e.shows = shows;
            tgPrev1912?.SetValue(e.g, -1f);                                        // redraw on the gauge's next Refresh
        }

        /// every frame from Update: the threshold in force, HUD switch, housekeeping
        void DriveAirbrake1912()
        {
            if (!brakePatched1912) { brakePatched1912 = true; PatchAirbrake1912(); }
            float thr = ThresholdNow1912();
            bool hudOn = HudAirbrakeOn;
            bool redraw = thr != brakeThr1912 || hudOn != hudTextOn1912;           // the gauge redraws only when the throttle changes: force it
            brakeThr1912 = thr; hudTextOn1912 = hudOn;
            if (Time.unscaledTime >= nextBrakePrune1912)
            {
                nextBrakePrune1912 = Time.unscaledTime + 5f;
                List<Airbrake> dead = null;
                foreach (var k in idleOf1912.Keys) if (k == null) (dead = dead ?? new List<Airbrake>()).Add(k);
                if (dead != null) foreach (var k in dead) idleOf1912.Remove(k);
            }
            if (hudBrakeBroken1912 || brakeHuds1912.Count == 0) return;
            try
            {
                for (int i = brakeHuds1912.Count - 1; i >= 0; i--)
                {
                    var e = brakeHuds1912[i];
                    if (e.g == null) { brakeHuds1912.RemoveAt(i); List<ThrottleGauge> gone = null; foreach (var k in brakeHudOf1912.Keys) if (k == null) (gone = gone ?? new List<ThrottleGauge>()).Add(k); if (gone != null) foreach (var k in gone) brakeHudOf1912.Remove(k); continue; }
                    var now = tgAircraft1912?.GetValue(e.g) as Aircraft;
                    if (e.ac == null || !ReferenceEquals(now, e.ac))
                    {
                        // the gauge was handed to another aircraft (or ours is gone): give it back as stock made it and let BoostLabels see it again
                        if (e.region != null) e.nameField.SetValue(e.region, e.stockName); else tgAirbrake1912.SetValue(e.g, false);
                        tgPrev1912?.SetValue(e.g, -1f);
                        relabelled.Remove(e.g);
                        brakeHudOf1912.Remove(e.g);
                        brakeHuds1912.RemoveAt(i);
                        continue;
                    }
                    if (hudOn != e.shows) SetBrakeHud1912(e, hudOn);
                    else if (redraw) tgPrev1912?.SetValue(e.g, -1f);
                }
            }
            catch (Exception ex) { hudBrakeBroken1912 = true; hudTextOn1912 = false; Logger.LogWarning("1.9.12 HUD airbrake text disabled: " + ex.Message); }
        }
    }
}
