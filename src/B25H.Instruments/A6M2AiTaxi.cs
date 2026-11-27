// A6M2 r6 (offline worker, 2026-11-18): AI taxi speed cap for the A6M2 taildragger.
//
// Game probes on r1b (MODLOG 05b88a5 / bcaa642, study\a6m2\r1_game\logs\ai_k92a.log): an AI Zero in AIPilotTaxiState reached 28-33 m/s on the
// taxi path (revetment: wing into the walls at 32.3 m/s; K92: lifted off and climbed out still in the taxi state, then flew into rising ground).
// Stock taxi law (AIPilotTaxiState.cs 384-409, 0.34.6): target speed num3 = (15 / (1 + 0.02 x next-waypoint angle) + min(sqrt(steer distance), 15))
// / (1 + 0.02 x heading error), i.e. up to 30 m/s on a straight leg; throttle up to 0.5, brake bang-bang above the target. That suits the stock
// tricycles; on the Zero the tail-wheel load is gone by ~26 m/s and the tail lifts from ~17-23 m/s (r1b tolog, a6m2_ground.py), so above that
// speed it cannot steer the path's next corner, and at 0.5 throttle it is close to lift-off speed by the end of a long straight.
// Fix (server, AI only, A6M2 only): Harmony postfix on AIPilotTaxiState.FixedUpdateState caps the taxi speed: above CapSpeed the throttle goes
// to idle and the brake on; between SoftSpeed and CapSpeed the throttle is limited. It acts after the state wrote its inputs (controlInputs is
// the aircraft's own ControlInputs object, PilotBaseState.cs:55), so the stock state's steering, queueing and hand-over (12 m from the runway
// start -> AIPilotTakeoffState, AIPilotTaxiState.cs:144-151) are untouched; the take-off roll itself (takeoff state) is not capped.
// r7: plus the take-off line-up hold (A6M2AiTaxiMath.HoldForLineUp) on AIPilotTakeoffState, same flag.
// Flag: config [A6M2] AiTaxiCap = Auto (build default OFF until the live probe passes) / On / Off. Any exception switches it off for the session.
// SHIP GATE: file name starts with A6M2 (make_public_tree leaves it out); called through a partial method declared in Nimrod.cs.
using System;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class A6M2AiTaxiMath
    {
        public const float CapSpeed = 12f;      // m/s: above this, idle + brake (r1b: tail-wheel load falls off from ~13 m/s at taxi thrust, gone at 26)
        public const float SoftSpeed = 9f;      // m/s: above this the throttle is limited to SoftThrottle
        public const float SoftThrottle = 0.2f;
        public const float CapBrake = 0.6f;

        // r7 deck line-up (take-off state): stock AIPilotTakeoffState goes to full throttle at once when the aircraft is NOT on the runway
        // polygon (flag2 = ... || !flag, AIPilotTakeoffState.cs:137), e.g. Annex R3 spawned 46 deg across the deck (r1b probe: over the edge at
        // 3 m/s). Its own runway branch waits for dot(forward, runway) > 0.95 (18 deg) before the full-throttle run. For the A6M2 on the
        // ground and slow, the same rule: throttle <= LineUpThrottle and no brake while the heading is more than LineUpDeg off the runway
        // direction (runwayVector), so the stock AutoAim steers the tail wheel round first.
        public const float LineUpDeg = 15f, LineUpThrottle = 0.30f, LineUpMaxSpeed = 12f;

        public static bool HoldForLineUp(float headingErrorDeg, float speed, float radarAlt) => radarAlt < 1f && speed < LineUpMaxSpeed && headingErrorDeg > LineUpDeg;

        // r8f (game r8e: an AI A6M2 off the Annex lift, 66 deg off the runway, sat at 0 m/s on the deck under the 0.30 line-up cap - on the
        // moving deck 0.30 did not break it away, so it could not turn): below BreakawaySpeed the cap is BreakawayThrottle (the stock taxi
        // maximum), and the hold ends for good LineUpMaxHold s after it first acted on that aircraft (then the stock take-off state rules).
        public const float BreakawaySpeed = 1.0f, BreakawayThrottle = 0.50f, LineUpMaxHold = 15f;

        /// throttle ceiling while the line-up hold acts; heldFor = seconds since the hold first acted on this aircraft (< 0: never released)
        public static float LineUpCap(float speed, float heldFor) => heldFor > LineUpMaxHold ? 1f : speed < BreakawaySpeed ? BreakawayThrottle : LineUpThrottle;

        /// returns (throttle, brake) after the cap; inputs = what the stock taxi state wrote
        public static void Cap(float speed, ref float throttle, ref float brake)
        {
            if (speed > CapSpeed) { throttle = 0.01f; brake = Mathf.Max(brake, CapBrake); }
            else if (speed > SoftSpeed) throttle = Mathf.Min(throttle, SoftThrottle);
        }
    }

    public partial class Plugin
    {
        const bool AiTaxiCapDefault = A6M2DefaultsMath.On;  // r7: off unless built with A6M2_DEFAULTS_ON (handover build), A6M2Defaults.cs
        static BepInEx.Configuration.ConfigEntry<string> aiTaxiMode;
        static bool aiTaxiBroken;
        static int aiTaxiLogs;

        static bool AiTaxiOn
        {
            get { var m = aiTaxiMode != null ? aiTaxiMode.Value : "Auto"; return m == "On" || (m != "Off" && AiTaxiCapDefault); }
        }

        partial void PatchA6M2AiTaxi()
        {
            aiTaxiMode = Config.Bind("A6M2", "AiTaxiCap", "Auto", "A6M2: AI taxi speed cap (12 m/s) for the taildragger. " + A6M2DefaultsMath.AutoText);
            A6M2MigrateKey(aiTaxiMode);
            if (!AiTaxiOn) { Logger.LogInfo("A6M2 AI taxi cap: off (config [A6M2] AiTaxiCap)"); return; }
            try
            {
                var m = typeof(AIPilotTaxiState).GetMethod("FixedUpdateState", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (m == null) { Logger.LogWarning("A6M2 AI taxi cap disabled: AIPilotTaxiState.FixedUpdateState not found"); return; }
                new HarmonyLib.Harmony("b25h.instruments.a6m2aitaxi").Patch(m, postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(AiTaxiPostfix), BindingFlags.Static | BindingFlags.NonPublic)));
                var tk = typeof(AIPilotTakeoffState).GetMethod("FixedUpdateState", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                aiRunwayVector = typeof(AIPilotTakeoffState).GetField("runwayVector", BindingFlags.Instance | BindingFlags.NonPublic);
                if (tk != null && aiRunwayVector != null)
                    new HarmonyLib.Harmony("b25h.instruments.a6m2aitaxi.lineup").Patch(tk, postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(AiLineUpPostfix), BindingFlags.Static | BindingFlags.NonPublic)));
                Logger.LogInfo($"A6M2 AI taxi cap on: idle + brake above {A6M2AiTaxiMath.CapSpeed} m/s, throttle <= {A6M2AiTaxiMath.SoftThrottle} above {A6M2AiTaxiMath.SoftSpeed} m/s; take-off line-up hold {(aiRunwayVector != null ? "on" : "unavailable")} (> {A6M2AiTaxiMath.LineUpDeg} deg off the runway: throttle <= {A6M2AiTaxiMath.LineUpThrottle})");
            }
            catch (Exception e) { aiTaxiBroken = true; Logger.LogWarning("A6M2 AI taxi cap disabled: " + e.Message); }
        }

        static FieldInfo aiRunwayVector;
        // 1.9.15 round 2: keyed by the take-off state object (a new AIPilotTakeoffState every take-off), not the aircraft: the hold acts again after a resupply
        static readonly System.Collections.Generic.Dictionary<AIPilotTakeoffState, float> aiLineUpStart = new System.Collections.Generic.Dictionary<AIPilotTakeoffState, float>();
        static readonly System.Collections.Generic.HashSet<AIPilotTakeoffState> aiLineUpReleased = new System.Collections.Generic.HashSet<AIPilotTakeoffState>();
        static int aiLineUpLogs;

        static void AiLineUpPostfix(AIPilotTakeoffState __instance, Pilot pilot)
        {
            if (aiTaxiBroken || pilot == null || aiRunwayVector == null) return;
            try
            {
                var a = pilot.aircraft;
                if (a == null || a.definition == null || a.definition.jsonKey != KamikazeFuzeMath.Key || !a.IsServer) return;
                var rv = (Vector3)aiRunwayVector.GetValue(__instance);
                rv.y = 0f;
                var fw = a.transform.forward; fw.y = 0f;
                if (rv.sqrMagnitude < 1e-4f || fw.sqrMagnitude < 1e-4f) return;
                float err = Vector3.Angle(fw, rv);
                if (!A6M2AiTaxiMath.HoldForLineUp(err, a.speed, a.radarAlt)) return;
                var id = __instance;
                if (!aiLineUpStart.TryGetValue(id, out float t0)) { if (aiLineUpStart.Count > 256) { aiLineUpStart.Clear(); aiLineUpReleased.Clear(); } t0 = Time.time; aiLineUpStart[id] = t0; }
                float cap = A6M2AiTaxiMath.LineUpCap(a.speed, Time.time - t0);
                if (cap >= 1f)
                {
                    if (aiLineUpReleased.Add(id)) Log.LogInfo($"A6M2 AI line-up: {a.name} hold released after {A6M2AiTaxiMath.LineUpMaxHold} s ({err:F0} deg off at {a.speed:F1} m/s): stock take-off state");
                    return;
                }
                var ci = a.GetInputs();
                if (ci.throttle > cap && aiLineUpLogs++ < 10) Log.LogInfo($"A6M2 AI line-up: {a.name} {err:F0} deg off the runway at {a.speed:F1} m/s: throttle {ci.throttle:F2} -> {cap:F2}");
                ci.throttle = Mathf.Min(ci.throttle, cap); ci.brake = 0f;
            }
            catch (Exception e) { aiTaxiBroken = true; Log.LogWarning("A6M2 AI line-up off: " + e.Message); }
        }

        static void AiTaxiPostfix(Pilot pilot)
        {
            if (aiTaxiBroken || pilot == null) return;
            try
            {
                var a = pilot.aircraft;
                if (a == null || a.definition == null || a.definition.jsonKey != KamikazeFuzeMath.Key || !a.IsServer) return;
                var ci = a.GetInputs();
                if (ci == null) return;
                float t = ci.throttle, b = ci.brake;
                A6M2AiTaxiMath.Cap(a.speed, ref t, ref b);
                if (t != ci.throttle && aiTaxiLogs++ < 10) Log.LogInfo($"A6M2 AI taxi cap: {a.name} at {a.speed:F1} m/s, throttle {ci.throttle:F2} -> {t:F2}, brake {ci.brake:F2} -> {b:F2}");
                ci.throttle = t; ci.brake = b;
            }
            catch (Exception e) { aiTaxiBroken = true; Log.LogWarning("A6M2 AI taxi cap off: " + e.Message); }
        }
    }
}
