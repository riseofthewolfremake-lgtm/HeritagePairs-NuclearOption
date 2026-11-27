// A6M2 r7 (offline worker, 2026-11-18): aileron authority falls with dynamic pressure (the Zero's heavy ailerons at speed).
//
// Game measurement on r4c (r4b FBW roll law: maxRollAngularVel 4, maxRollSpeed 1.0, rollTightness 0.5), full stick, steady rate:
//   67 deg/s at 356 km/h, 81 at 417, 83 at 562, 79 at 587 - flat above 420 (0.95 x the peak at 587). Target (coordinator r7): peak near
//   400 km/h, under 0.8 x the peak at ~590, about 50-60 deg/s there. The FBW roll law alone does not give the fall-off in game
//   (tools/flightmodel/a6m2_roll.py predicted 59 at 600 with these numbers; the game held 79 - the model's stick-cut assumption is wrong).
// Mechanism (decompile 0.34.6): every ControlSurface copies the aircraft's ControlInputs into its job fields in UpdateJobFields
// (ControlSurface.cs:160-175; deflection = pitch x pitchRange + yaw x yawRange + roll x rollRange, ControlSurfacePhysics.cs:46). A prefix /
// postfix pair on UpdateJobFields scales controlInputs.roll by k(q) for the A6M2's surfaces only and restores it at once, so the FBW, the
// HUD and every other reader see the unscaled input. Only the ailerons have a roll range on the A6M2.
// Law (A6M2RollQMath): k = min(1, (q0 / q)^Exp) with q = 0.5 rho V^2, q0 at 420 km/h EAS; Exp 0.55 = the fit to the four game points
// (k(587) = 0.70 -> 55 deg/s, k(562) = 0.73 -> 61, peak 81 at 417 kept; tools/flightmodel/a6m2_roll.py q_table).
// Flag: config [A6M2] RollQ = Auto (build default: off; on in the handover build, A6M2Defaults.cs) / On / Off.
// SHIP GATE: A6M2* file; patched from PatchA6M2AiTaxi's sibling partial (declared in Nimrod.cs).
using System;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class A6M2RollQMath
    {
        public const float RefKmh = 420f;       // EAS where the fall-off starts (the measured / target peak)
        public const float Exp = 0.55f;         // k = (q0 / q)^Exp above q0
        public static float K(float rho, float tas)
        {
            float q = 0.5f * rho * tas * tas;
            float v0 = RefKmh / 3.6f, q0 = 0.5f * 1.225f * v0 * v0;
            return q <= q0 ? 1f : Mathf.Pow(q0 / q, Exp);
        }
    }

    public partial class Plugin
    {
        const bool RollQDefault = A6M2DefaultsMath.On;
        static BepInEx.Configuration.ConfigEntry<string> rollQMode;
        static bool rollQBroken;
        static FieldInfo csAircraft, csInputs;
        [ThreadStatic] static float rollQSaved;
        [ThreadStatic] static ControlInputs rollQCi;

        static bool RollQOn { get { var m = rollQMode != null ? rollQMode.Value : "Auto"; return m == "On" || (m != "Off" && RollQDefault); } }

        partial void PatchA6M2RollQ()
        {
            rollQMode = Config.Bind("A6M2", "RollQ", "Auto", "A6M2: aileron authority falls with dynamic pressure above 420 km/h EAS (heavy ailerons). " + A6M2DefaultsMath.AutoText);
            A6M2MigrateKey(rollQMode);
            if (!RollQOn) { Logger.LogInfo("A6M2 roll q-scaling: off (config [A6M2] RollQ)"); return; }
            try
            {
                const BindingFlags f = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
                var m = typeof(ControlSurface).GetMethod("UpdateJobFields", f);
                csAircraft = typeof(ControlSurface).GetField("aircraft", f); csInputs = typeof(ControlSurface).GetField("controlInputs", f);
                if (m == null || csAircraft == null || csInputs == null) { Logger.LogWarning("A6M2 roll q-scaling disabled: ControlSurface members not found"); return; }
                new HarmonyLib.Harmony("b25h.instruments.a6m2rollq").Patch(m,
                    prefix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(RollQPrefix), BindingFlags.Static | BindingFlags.NonPublic)),
                    postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(RollQPostfix), BindingFlags.Static | BindingFlags.NonPublic)));
                Logger.LogInfo($"A6M2 roll q-scaling on: aileron input x (q0/q)^{A6M2RollQMath.Exp} above {A6M2RollQMath.RefKmh} km/h EAS");
            }
            catch (Exception e) { rollQBroken = true; Logger.LogWarning("A6M2 roll q-scaling disabled: " + e.Message); }
        }

        static void RollQPrefix(ControlSurface __instance)
        {
            rollQCi = null;
            if (rollQBroken) return;
            try
            {
                var a = csAircraft.GetValue(__instance) as Aircraft;
                if (a == null || a.definition == null || a.definition.jsonKey != KamikazeFuzeMath.Key) return;
                var ci = csInputs.GetValue(__instance) as ControlInputs;
                if (ci == null) return;
                float k = A6M2RollQMath.K(a.GetAirDensity(), a.speed);
                if (k >= 0.999f) return;
                rollQCi = ci; rollQSaved = ci.roll; ci.roll *= k;
            }
            catch (Exception e) { rollQBroken = true; rollQCi = null; Log.LogWarning("A6M2 roll q-scaling off: " + e.Message); }
        }

        static void RollQPostfix()
        {
            if (rollQCi != null) { rollQCi.roll = rollQSaved; rollQCi = null; }
        }
    }
}
