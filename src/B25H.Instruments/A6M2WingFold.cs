// A6M2 r8 (offline worker, 2026-11-19): folding wing tips, spawned folded on the ground, unfolded a few seconds later.
//
// Evidence (decompile of the INSTALLED game, nuclearoption-ref\decomp_current_20261119, Assembly-CSharp sha256 babdd626bbab5f01, game 0.34.6,
// byte-identical to decomp_0346): no fixed-wing fold component exists. The one spawn-fold mechanism is RotorShaft.RotorHinge (the stock
// UtilityHelo1 rotor blades, RotorShaft.cs:9-33): on aircraft.onInitialize (RotorShaft.cs:254) a spawn with radarAlt > spawnOffset.y + 1
// starts unfolded, any other spawn starts folded (foldAmount 1, RotorShaft.cs:383-404); UnfoldRotors (RotorShaft.cs:428-466) waits 1000 ms,
// then waits in 1000 ms steps while rb.velocity.y > 1 (a carrier lift still moving), then runs foldAmount -= foldSpeed x dt with the hinge at
// foldAngle x SmoothStep(0, 1, foldAmount) until 0. SwingWingController (FastBomber1 rudder fold hinges) is a Mach-driven sweep, not a spawn fold.
// This piece reuses that exact law for the A6M2's tips: A6M2Build puts each wing_fold_X render mesh under wing_fold_X_hinge (local X = the
// fold line, + angle = tip up, 90 deg = folded); the part's collider and joint are not moved (visual only, like the rotor blades' hinges).
// Hook: postfix on Unit.InitializeUnit (Unit.cs:742; Aircraft calls it from its start path, Aircraft.cs:1240) - the moment RotorShaft's
// onInitialize handler runs. Flag: config [A6M2] WingFold = Auto (build default; ON in the handover build) / On / Off.
// SHIP GATE: A6M2* file.
using System;
using System.Collections;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class A6M2WingFoldMath
    {
        public const float FoldDeg = 90f;          // A6M2Build.WingFoldDeg
        // r8c (game r8b: an AI on the carrier lift taxied off 0.5 s after spawn with the tips folded; the unfold came ~13 s later because the
        // stock-law wait polled in 1 s steps while the lift rose): unfold as soon as the aircraft has SETTLED - |vertical speed| under SettleVy
        // for SettleTime - after a short FirstDelay, or at MaxWait whatever the lift does; an AI A6M2 is held at idle + brakes until the
        // unfold has finished (FoldHoldPostfix on the AI taxi / take-off states, next to A6M2AiTaxi).
        public const float FirstDelay = 0.5f;      // r8b: 1.0 (RotorShaft.UnfoldRotors: UniTask.Delay(1000))
        public const float SettleVy = 0.3f;        // m/s
        public const float SettleTime = 0.3f;      // s
        public const float MaxWait = 4.0f;         // s after spawn
        public const float LiftWait = 1.0f;        // r8b law (kept for the stub's comparison)
        public const float LiftVy = 1.0f;

        /// r8c: one wait step; settled = seconds the aircraft has been still. True when the unfold may start.
        public static bool ReadyToUnfold(float sinceSpawn, float vy, float dt, ref float settled)
        {
            settled = Mathf.Abs(vy) < SettleVy ? settled + dt : 0f;
            if (sinceSpawn < FirstDelay) return false;
            return settled >= SettleTime || sinceSpawn >= MaxWait;
        }

        /// r8c: an AI A6M2 is held (idle + full brake) while its tips are folded or unfolding
        public static bool HoldAi(float amount) => amount > 0f;
        public const float FoldSpeed = 0.33f;      // per second (3 s to unfold). INFERENCE: the stock foldSpeed of UtilityHelo1 was not read
                                                   // (serialized in resources.assets without a type tree); the probe times it in game.

        /// spawn rule: folded unless spawned in the air (RotorShaft_OnSpawnedInPosition)
        public static bool StartFolded(float radarAlt, float spawnOffsetY) => !(radarAlt > spawnOffsetY + 1f);

        /// hinge angle (deg, + = tip up) for a fold amount 0..1 (RotorHinge.Unfold: foldAngle x SmoothStep(0, 1, amount))
        public static float Angle(float amount) => FoldDeg * Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(amount));

        /// one unfold step (RotorHinge.Unfold); returns the new amount
        public static float Step(float amount, float speed, float dt) => Mathf.Max(0f, amount - speed * dt);
    }

    public class A6M2WingFoldDriver : MonoBehaviour
    {
        public Aircraft aircraft;
        public Transform[] hinges;
        public Quaternion[] rest;
        public float amount;
        public string state = "init";

        void Apply()
        {
            for (int i = 0; i < hinges.Length; i++)
                if (hinges[i] != null) hinges[i].localRotation = rest[i] * Quaternion.AngleAxis(A6M2WingFoldMath.Angle(amount), Vector3.right);
        }

        public void Begin(bool folded)
        {
            amount = folded ? 1f : 0f;
            Apply();
            if (folded) StartCoroutine(Unfold()); else state = "unfolded (air spawn)";
        }

        IEnumerator Unfold()
        {
            state = "folded";
            float t0 = Time.time, settled = 0f;
            while (aircraft != null)
            {
                float vy = aircraft.rb != null ? aircraft.rb.velocity.y : 0f;
                if (A6M2WingFoldMath.ReadyToUnfold(Time.time - t0, vy, Time.deltaTime, ref settled)) break;
                state = Time.time - t0 < A6M2WingFoldMath.FirstDelay ? "folded" : "waiting to settle";
                yield return null;
            }
            if (aircraft == null) yield break;
            Plugin.LogA6M2Fold($"A6M2 wing fold: {aircraft.name} unfold starts {Time.time - t0:F1} s after spawn");
            state = "unfolding";
            while (amount > 0f)
            {
                if (aircraft == null) yield break;               // destroyed: stop (RotorShaft: cancellation token)
                amount = A6M2WingFoldMath.Step(amount, A6M2WingFoldMath.FoldSpeed, Time.deltaTime);
                Apply();
                yield return null;
            }
            state = "unfolded";
            Plugin.LogA6M2Fold($"A6M2 wing fold: {aircraft?.name} unfolded");
        }
    }

    public partial class Plugin
    {
        const bool WingFoldDefault = A6M2DefaultsMath.On;
        static BepInEx.Configuration.ConfigEntry<string> wingFoldMode;
        static bool wingFoldBroken;
        static bool WingFoldOn { get { var m = wingFoldMode != null ? wingFoldMode.Value : "Auto"; return m == "On" || (m != "Off" && WingFoldDefault); } }
        internal static void LogA6M2Fold(string s) { try { Log?.LogInfo(s); } catch { } }

        partial void PatchA6M2WingFold()
        {
            wingFoldMode = Config.Bind("A6M2", "WingFold", "Auto", "A6M2: wing tips spawn folded on the ground (carrier or runway) and unfold after the stock rotor-blade delay. " + A6M2DefaultsMath.AutoText);
            A6M2MigrateKey(wingFoldMode);
            if (!WingFoldOn) { Logger.LogInfo("A6M2 wing fold: off (config [A6M2] WingFold)"); return; }
            try
            {
                var m = typeof(Unit).GetMethod("InitializeUnit", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (m == null) { Logger.LogWarning("A6M2 wing fold disabled: Unit.InitializeUnit not found"); return; }
                new HarmonyLib.Harmony("b25h.instruments.a6m2wingfold").Patch(m,
                    postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(WingFoldPostfix), BindingFlags.Static | BindingFlags.NonPublic)));
                var hp = new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(FoldHoldPostfix), BindingFlags.Static | BindingFlags.NonPublic)) { priority = HarmonyLib.Priority.Last };
                int held = 0;
                foreach (var st in new[] { typeof(AIPilotTaxiState), typeof(AIPilotTakeoffState) })
                {
                    var fm = st.GetMethod("FixedUpdateState", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                    if (fm != null) { new HarmonyLib.Harmony("b25h.instruments.a6m2wingfold.hold").Patch(fm, postfix: hp); held++; }
                }
                Logger.LogInfo($"A6M2 wing fold on: ground spawns start folded {A6M2WingFoldMath.FoldDeg} deg, unfold when settled ({A6M2WingFoldMath.SettleVy} m/s for {A6M2WingFoldMath.SettleTime} s, after {A6M2WingFoldMath.FirstDelay} s, at the latest {A6M2WingFoldMath.MaxWait} s) at {A6M2WingFoldMath.FoldSpeed}/s; AI hold on {held} states");
            }
            catch (Exception e) { wingFoldBroken = true; Logger.LogWarning("A6M2 wing fold disabled: " + e.Message); }
        }

        /// r8b (game r8: "0 hinges found"): at spawn the game moves the AeroParts out of the aircraft's hierarchy (each part its own
        /// rigidbody root), so the hinges are searched under the aircraft AND under every part of Unit.partLookup (the test helper's AllT).
        internal static System.Collections.Generic.List<Transform> FindFoldHinges(Aircraft a)
        {
            var hl = new System.Collections.Generic.List<Transform>();
            var roots = new System.Collections.Generic.List<Transform> { a.transform };
            if (a.partLookup != null)
                foreach (var p in a.partLookup) if (p != null && !roots.Contains(p.transform)) roots.Add(p.transform);
            foreach (var r in roots)
                foreach (var t in r.GetComponentsInChildren<Transform>(true))
                    if ((t.name == "wing_fold_L_hinge" || t.name == "wing_fold_R_hinge") && !hl.Contains(t)) hl.Add(t);
            return hl;
        }

        static int foldHoldLogs;

        /// r8c: AI A6M2 at idle + full brake while its tips are folded / unfolding (runs after the stock state and A6M2AiTaxi's caps)
        static void FoldHoldPostfix(Pilot pilot)
        {
            if (wingFoldBroken || pilot == null) return;
            try
            {
                var a = pilot.aircraft;
                if (a == null || a.definition == null || a.definition.jsonKey != KamikazeFuzeMath.Key || !a.IsServer) return;
                var d = a.GetComponent<A6M2WingFoldDriver>();
                if (d == null || !A6M2WingFoldMath.HoldAi(d.amount)) return;
                var ci = a.GetInputs();
                if (ci == null) return;
                if (ci.throttle > 0.02f && foldHoldLogs++ < 10) Log.LogInfo($"A6M2 wing fold: AI {a.name} held (tips {d.state}, amount {d.amount:F2}): throttle {ci.throttle:F2} -> 0, brake 1");
                ci.throttle = 0f; ci.brake = 1f;
            }
            catch (Exception e) { wingFoldBroken = true; Log.LogWarning("A6M2 wing fold hold off: " + e.Message); }
        }

        static void WingFoldPostfix(Unit __instance)
        {
            if (wingFoldBroken) return;
            try
            {
                var a = __instance as Aircraft;
                if (a == null || a.definition == null || a.definition.jsonKey != KamikazeFuzeMath.Key) return;
                if (a.GetComponent<A6M2WingFoldDriver>() != null) return;
                var hl = FindFoldHinges(a);
                if (hl.Count != 2) { Log.LogWarning($"A6M2 wing fold: {hl.Count} hinges found on {a.name} (want 2), skipped"); return; }
                var d = a.gameObject.AddComponent<A6M2WingFoldDriver>();
                d.aircraft = a; d.hinges = hl.ToArray(); d.rest = new Quaternion[hl.Count];
                for (int i = 0; i < hl.Count; i++) d.rest[i] = hl[i].localRotation;
                bool folded = A6M2WingFoldMath.StartFolded(a.radarAlt, a.definition.spawnOffset.y);
                d.Begin(folded);
                Log.LogInfo($"A6M2 wing fold: {a.name} spawned {(folded ? "folded" : "unfolded")} (radarAlt {a.radarAlt:F1} m, spawnOffset.y {a.definition.spawnOffset.y:F2})");
            }
            catch (Exception e) { wingFoldBroken = true; Log.LogWarning("A6M2 wing fold off: " + e.Message); }
        }
    }
}
