// B25H.Instruments 1.9.15 AiLineUp1915 (bug 2 of 2026-11-26, FD-32 named by the user): take-off line-up hold for the taildraggers
// FD-32, Nimrod Mk I, B-17G and MSB-17.
//
// The stock AIPilotTakeoffState goes to full throttle at once when the aircraft is NOT on the runway polygon (flag2 = ... || !flag,
// AIPilotTakeoffState.cs:137); its own runway branch waits for dot(forward, runway) > 0.95 (18 deg) before the full-throttle run. With the
// 1.9.15 hand-over from up to 25 m off the runway start (AiTaxiDeadEnd1915) a taildragger would otherwise go to full throttle in a turn.
// Rule (the same law as the line-up hold of the ship-gated dev aircraft, r7 / r8f, game-tested there): on the ground (radarAlt < 1 m), slower
// than 12 m/s and more than 15 deg off the runway direction (runwayVector): throttle <= 0.30 (0.50 below 1 m/s, the stock taxi maximum, to
// break away) and brake 0, so the stock AutoAim steers the tail wheel round first; released for good 15 s after it first acted.
// Server only, AI only. Config [Ground] AiLineUp1915 = Auto (on) / On / Off. Any exception switches it off for the session.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace B25H.Instruments
{
    public static class LineUpMath1915
    {
        public const float LineUpDeg = 15f, LineUpThrottle = 0.30f, LineUpMaxSpeed = 12f;
        public const float BreakawaySpeed = 1.0f, BreakawayThrottle = 0.50f, LineUpMaxHold = 15f;

        public static bool IsKey(string k) => k == "FD32" || k == "NIMROD1" || k == "B17G" || k == "MSB17";
        public static bool HoldForLineUp(float headingErrorDeg, float speed, float radarAlt) => radarAlt < 1f && speed < LineUpMaxSpeed && headingErrorDeg > LineUpDeg;
        /// throttle ceiling while the hold acts; heldFor = seconds since it first acted on this aircraft
        public static float LineUpCap(float speed, float heldFor) => heldFor > LineUpMaxHold ? 1f : speed < BreakawaySpeed ? BreakawayThrottle : LineUpThrottle;
    }

    public partial class Plugin
    {
        const bool AiLineUpDefault1915 = true;
        static BepInEx.Configuration.ConfigEntry<string> lineUpMode1915;
        static bool lineUpBroken1915;
        static int lineUpLogs1915;
        // round 2 (review of round 1): keyed by the take-off state object, not the aircraft - every take-off gets a new AIPilotTakeoffState
        // (AIPilotTaxiState.cs 150, Pilot.cs 277, HandOver1915), so after a resupply the hold acts again; also cleared on EnterState
        static readonly Dictionary<AIPilotTakeoffState, float> lineUpStart1915 = new Dictionary<AIPilotTakeoffState, float>();
        static readonly HashSet<AIPilotTakeoffState> lineUpReleased1915 = new HashSet<AIPilotTakeoffState>();
        static readonly HashSet<AIPilotTakeoffState> lineUpLogged1915 = new HashSet<AIPilotTakeoffState>();   // round 3: one log line per take-off state

        static bool LineUpOn1915 => Mode1915.On(lineUpMode1915 != null ? lineUpMode1915.Value : "Auto", AiLineUpDefault1915);

        void PatchAiLineUp1915()
        {
            lineUpMode1915 = Config.Bind("Ground", "AiLineUp1915", "Auto", "1.9.15: AI FD-32, Mk I, B-17G and MSB-17 turn onto the runway at part throttle (more than 15 deg off: throttle <= 30 %, at most 15 s) instead of going to full throttle in a turn. Auto = build default (on), On, Off.");
            if (!LineUpOn1915) { Logger.LogInfo("1.9.15 AI line-up: off (config [Ground] AiLineUp1915)"); return; }
            try
            {
                if (!Taxi1915.Init()) { lineUpBroken1915 = true; Logger.LogWarning("1.9.15 AI line-up disabled: stock AI state fields not found"); return; }
                H1915.Patch(HarmonyLib.AccessTools.Method(typeof(AIPilotTakeoffState), "FixedUpdateState"), postfix: HM1915(nameof(LineUpPostfix1915)));
                H1915.Patch(HarmonyLib.AccessTools.Method(typeof(AIPilotTakeoffState), "EnterState"), postfix: HM1915(nameof(LineUpEnterPostfix1915)));
                Logger.LogInfo($"1.9.15 AI line-up on: FD32 / NIMROD1 / B17G / MSB17 more than {LineUpMath1915.LineUpDeg} deg off the runway below {LineUpMath1915.LineUpMaxSpeed} m/s -> throttle <= {LineUpMath1915.LineUpThrottle}");
            }
            catch (Exception e) { lineUpBroken1915 = true; Logger.LogWarning("1.9.15 AI line-up disabled: " + e.Message); }
        }

        /// round 2: a (re-)entered take-off state starts a fresh hold; the tables never grow past one entry per live take-off
        static void LineUpEnterPostfix1915(AIPilotTakeoffState __instance)
        {
            if (lineUpBroken1915) return;
            lineUpStart1915.Remove(__instance); lineUpReleased1915.Remove(__instance); lineUpLogged1915.Remove(__instance);
            if (lineUpStart1915.Count > 256) lineUpStart1915.Clear();
            if (lineUpReleased1915.Count > 256) lineUpReleased1915.Clear();
            if (lineUpLogged1915.Count > 256) lineUpLogged1915.Clear();
        }

        static void LineUpPostfix1915(AIPilotTakeoffState __instance, Pilot pilot)
        {
            if (lineUpBroken1915 || pilot == null) return;
            try
            {
                var a = pilot.aircraft;
                if (a == null || a.definition == null || !LineUpMath1915.IsKey(a.definition.jsonKey) || !a.IsServer || !AiOnly1915(a)) return;
                if (!ReferenceEquals(pilot.currentState, __instance)) return;
                var rv = Taxi1915.tkRunwayVector(__instance);
                rv.y = 0f;
                var fw = a.transform.forward; fw.y = 0f;
                if (rv.sqrMagnitude < 1e-4f || fw.sqrMagnitude < 1e-4f) return;
                float err = Vector3.Angle(fw, rv);
                if (!LineUpMath1915.HoldForLineUp(err, a.speed, a.radarAlt)) return;
                var id = __instance;
                if (!lineUpStart1915.TryGetValue(id, out float t0)) { t0 = Time.time; lineUpStart1915[id] = t0; }
                float cap = LineUpMath1915.LineUpCap(a.speed, Time.time - t0);
                if (cap >= 1f)
                {
                    if (lineUpReleased1915.Add(id)) Log.LogInfo($"1.9.15 AI line-up: {a.name} hold released after {LineUpMath1915.LineUpMaxHold} s ({err:F0} deg off at {a.speed:F1} m/s): stock take-off state");
                    return;
                }
                var ci = a.GetInputs();
                if (ci == null) return;
                // round 3: one line per take-off state (round 2 logged every frame while it acted, ~30 lines per take-off)
                if (ci.throttle > cap && lineUpLogged1915.Add(id) && lineUpLogs1915++ < 200) Log.LogInfo($"1.9.15 AI line-up: {a.name} ({a.definition.jsonKey}) {err:F0} deg off the runway at {a.speed:F1} m/s: throttle {ci.throttle:F2} -> {cap:F2}");
                ci.throttle = Mathf.Min(ci.throttle, cap); ci.brake = 0f;
            }
            catch (Exception e) { lineUpBroken1915 = true; Log.LogWarning("1.9.15 AI line-up disabled: " + e.Message); }
        }
    }
}
