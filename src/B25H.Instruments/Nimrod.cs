// B25H.Instruments 1.5.5 (1.5.5: NIMROD1 uses the game's gear logic ("lie to the game": fixed-gear keeper / HUD hacks off), hook deploy logic sized for NIMROD1 / FD32; 1.5.1: the FD-32 v2 has RETRACTING gear - it leaves every fixed-gear path, NIMROD1 unchanged; 1.5.0: the same fixed-gear logic for the FD-32 Nimrod, jsonKey FD32, NIMROD1 unchanged; 1.4.2: + gear guard / break log; 1.4.1: combat HUD with fixed gear; 1.4.0: hook A-frame driver + Cooper detonation log): Hawker Nimrod Mk I (jsonKey NIMROD1) branch. Separate from the B-25H path (Plugin.cs), which is unchanged.
//
// 1. Gauges: every needle/card of the Nimrod panel (model contract assets/model_nimrod/nimrod_contract.json "gauges"; mover local
//    +X toward the pilot, rest 12 o'clock, + angle = clockwise as seen by the pilot - the B-25H convention, verified in game).
//    The value -> angle maps are in NimrodMath (pure functions, mirrored by stub_test.py).
// 2. Fixed undercarriage: the Nimrod's gear cannot retract (its LandingGear fold is 0.5 deg), but the game's gear toggle (G key,
//    air spawn, AI after take-off) still sets "retracted", which disables the wheels' ground contact. For an aircraft we simulate
//    locally (LocalSim) and whose gear is up, this sets it down again. Config [Nimrod] FixedGear (default true).
// 3. (1.4.0) Visible arrester hook: the model's A-frame `hook_visual` (under the belly) follows the game's functional TailHook, whose own mesh
//    is hidden: deployed amount = InverseLerp(stowedAngle, deployedAngle, hook.localEulerAngles.x) (TailHook.FixedUpdate writes exactly
//    that angle, incl. the trailing while hooked), visual angle = HookVisualDeg(amount) about the A-frame's local X. Config [Nimrod] HookVisual.
// Reads only the aircraft's own public state; writes only transforms named gauge_* / hook_visual inside a NIMROD1 aircraft and its gear state.
// 1.5.0: the FD-32 (jsonKey FD32: the Mk I airframe with the same fixed gear, A-frame hook and fus_engine / root split) gets the fixed-gear keeper,
//        the combat-HUD fix, the crash rule and the gear guard through IsFixedGear(); its hook A-frame reads the stow angle from its own TailHook.
//        It has no needle gauges (modern cockpit: stock screens). Every NIMROD1 path is unchanged (IsFixedGear is true for NIMROD1 as before).
// 1.5.1: the FD-32 v2 retracts its gear like every stock aircraft, so IsFixedGearKey is NIMROD1 only again: no keeper, no HUD fix,
//        no crash rule, no gear guard for FD32 (stock gear logic). NIMROD1 behaviour is byte-identical to 1.5.0.
using System.Collections.Generic;
using UnityEngine;

namespace B25H.Instruments
{
    public static class NimrodMath
    {
        public const float AsiDegPerKt = 330f / 260f, AsiMaxKt = 260f;
        public const float AltLongDegPerFt = 0.36f, AltShortDegPerFt = 0.036f;
        public const float RpmDegPerRpm = 0.1f, RpmMax = 3000f;          // 0..3000 over 300 deg
        public const float RatedRpm = 2600f;                              // 1.8.4: Kestrel rated rpm at prop rpm ratio 1 (governed)
        public const float BoostDegPerPsi = 22.5f, BoostMin = -4f, BoostMax = 8f;
        public const float OilPDegPerPsi = 2.7f, OilTDegPerC = 2.7f, WaterDegPerC = 270f / 140f, FuelDegPerPct = 2.7f;
        public const float TurnDegPerDps = 10f, TurnMax = 45f;          // rate one (3 deg/s) = 30 deg
        public const float SlipDegPerDeg = 1.5f, SlipMax = 28f;

        public static float Asi(float tas, float rho) { float kt = tas * Mathf.Sqrt(Mathf.Max(rho, 0f) / 1.225f) * 1.943844f; return Mathf.Clamp(kt, 0f, AsiMaxKt) * AsiDegPerKt; }
        public static float AltLong(float altM) => Mathf.Repeat(altM * 3.28084f * AltLongDegPerFt, 360f);
        public static float AltShort(float altM) => Mathf.Repeat(altM * 3.28084f * AltShortDegPerFt, 360f);
        public static float Rpm(float rpm) => Mathf.Clamp(rpm, 0f, RpmMax) * RpmDegPerRpm;
        // manifold boost (lb/in2) from throttle x rpm (no supercharger model in game): idle -4, full +6 at sea level
        public static float BoostPsi(float throttle, float rpmRatio, bool running) => running ? Mathf.Lerp(-4f, 6f, Mathf.Clamp01(throttle) * Mathf.Clamp01(rpmRatio)) : 0f;
        public static float Boost(float psi) => (Mathf.Clamp(psi, BoostMin, BoostMax) - BoostMin) * BoostDegPerPsi;
        public static float OilPsi(float rpmRatio, bool running) => running ? 15f + 55f * Mathf.Clamp01(rpmRatio) : 0f;
        public static float OilTTarget(float powerRatio, bool running) => running ? 40f + 35f * Mathf.Clamp01(powerRatio) : 15f;
        public static float WaterTarget(float powerRatio, bool running) => running ? 70f + 40f * Mathf.Clamp01(powerRatio) : 15f;
        public static float Lag(float current, float target, float dt, float tau) => current + (target - current) * Mathf.Clamp01(dt / tau);
        public static float Turn(float yawRateDps) => Mathf.Clamp(yawRateDps * TurnDegPerDps, -TurnMax, TurnMax);
        // ball: apparent gravity in the aircraft frame (x right, y up); ball to the right (+x) = negative (anticlockwise) needle angle
        public static float Slip(float downX, float downY) => Mathf.Clamp(-Mathf.Atan2(downX, Mathf.Max(-downY, 0.05f)) * Mathf.Rad2Deg * SlipDegPerDeg, -SlipMax, SlipMax);
        public static float Compass(float headingDeg) => -headingDeg;
        // hook A-frame (model contract "hook_visual" / "tailhook"): functional stowed +2 / deployed -65 deg (TailHook, Unity +X lifts the tip);
        // the A-frame is modelled stowed, its deployed pose is 60.7 deg further down (claw on the functional tip)
        public const float HookStow = 2f, HookDeploy = -65f, HookVisualTravel = 60.7f;
        public static float Wrap180(float a) => Mathf.Repeat(a + 180f, 360f) - 180f;
        public static float HookAmount(float hookLocalX) => Mathf.Clamp01((Wrap180(hookLocalX) - HookStow) / (HookDeploy - HookStow));
        public static float HookVisualDeg(float amount) => -HookVisualTravel * Mathf.Clamp01(amount);
        // 1.5.0: the same mapping from the aircraft's own TailHook stowed angle (FD-32: 1 deg); with stow = HookStow it is HookAmount exactly
        public static float HookAmountFrom(float hookLocalX, float stow) => Mathf.Clamp01((Wrap180(hookLocalX) - stow) / (HookDeploy - stow));
    }

    public partial class Plugin
    {
        public const string NimrodKey = "NIMROD1";
        public const string FD32Key = "FD32";          // 1.5.0 fixed-gear key; 1.5.1: unused on the fixed-gear paths (the v2 retracts)
        public static bool IsFixedGearKey(string k) => k == NimrodKey;   // 1.5.1: NIMROD1 only (the FD-32 v2 retracts its gear)
        static readonly string[] NimrodNames = { "gauge_asi_needle", "gauge_alt_needle", "gauge_alt_needle_short", "gauge_rpm_needle", "gauge_boost_needle",
            "gauge_oilp_needle", "gauge_oilt_needle", "gauge_water_needle", "gauge_fuel_needle", "gauge_turn_needle", "gauge_slip_needle", "gauge_compass_card" };

        class NimrodGauges
        {
            public Aircraft aircraft;
            public readonly Dictionary<string, Transform> t = new Dictionary<string, Transform>();
            public readonly Dictionary<string, Quaternion> rest = new Dictionary<string, Quaternion>();
            public TurbineEngine engine;
            public ConstantSpeedProp prop;   // 1.8.4: the rpm source (TurbineEngine rpm is constant while running)
            public float oilT = 15f, water = 15f, slip;
            public Vector3 vPrev; public bool havePrev;
            public Transform hookVis, hookFn; public Quaternion hookVisRest; public float nextHookScan;
            public float hookStow = NimrodMath.HookStow;   // 1.5.0: from the aircraft's TailHook.stowedAngle (NIMROD1: 2 = the constant)
        }

        readonly Dictionary<Aircraft, NimrodGauges> nimrods = new Dictionary<Aircraft, NimrodGauges>();
        readonly Dictionary<Aircraft, int> nimrodMisses = new Dictionary<Aircraft, int>();
        BepInEx.Configuration.ConfigEntry<bool> nimrodHookVisual;
        static readonly System.Reflection.FieldInfo HookField = typeof(TailHook).GetField("hook", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public);
        static readonly System.Reflection.FieldInfo StowField = typeof(TailHook).GetField("stowedAngle", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public);
        static BepInEx.Logging.ManualLogSource Log;
        // A6M2 pieces (A6M2KamikazeFuze.cs, A6M2EventRowHide.cs; ship-gated, absent from the public tree): partial methods, dropped when not implemented
        partial void PatchKamikazeFuze();
        partial void PatchEventRowHide();
        partial void KamikazeStep();
        partial void ScanA6M2();               // A6M2Cockpit.cs (round 4 dials)
        partial void DriveA6M2All();
        partial void PatchA6M2AiTaxi();        // A6M2 r6: AI taxi speed cap (A6M2AiTaxi.cs)
        partial void PatchA6M2RollQ();         // A6M2 r7: aileron authority vs dynamic pressure (A6M2RollQ.cs)
        partial void PatchA6M2WingFold();      // A6M2 r8: folding tips, spawn folded on the ground (A6M2WingFold.cs)

        void Awake()
        {
            Log = Logger;
            HookHud1810();           // 1.8.10: HUD gauge discovery hooks (Scan1810.cs)
            PatchCrashGear();
            PatchGearGuard();
            PatchHookDeploy();
            Patch1915();             // 1.9.15: the bug list of 2026-11-26 (Bugs1915.cs: overlap joints, AI ground watch / taxi dead end / line-up, deck filter, bomb armour)
            PatchLaserGuard();       // 1.9.7: GA-25X / MSB lasers never fire through their own aircraft (LaserGuard197.cs)
            PatchKamikazeFuze();     // A6M2 round 3: crash / shoot-down fuze for the Event Content charge (A6M2KamikazeFuze.cs)
            PatchEventRowHide();     // A6M2 round 3: Special row hidden when the mission has no Event Content (A6M2EventRowHide.cs)
            PatchA6M2AiTaxi();       // A6M2 r6: AI taxi speed cap for the taildragger (A6M2AiTaxi.cs)
            PatchA6M2RollQ();        // A6M2 r7: aileron authority falls with dynamic pressure (A6M2RollQ.cs)
            PatchA6M2WingFold();     // A6M2 r8: folding tips (A6M2WingFold.cs)
        }

        static bool IsNimrod(Aircraft a) => a != null && a.definition != null && a.definition.jsonKey == NimrodKey;
        static bool IsFixedGear(Aircraft a) => a != null && a.definition != null && IsFixedGearKey(a.definition.jsonKey);   // 1.5.0: NIMROD1 or FD32
        // 1.5.5: the Mk I uses the game's own gear logic (its LandingGear folds 0.5 deg, so gear up / down works like any stock aircraft).
        // 1.9.9: the older fixed-gear keeper and combat-HUD workaround (off by default since 1.5.5) are removed; the crash rule and the gear guard stay.

        // 6. (1.4.1) Crash gear: the main legs hang on the fuselage centre (the root part, which never detaches), so a ground impact never broke
        //    them. One impact on the centre / engine section of >= CrashGearImpact damage (Pack impactDamage) breaks every wheel and the skid
        //    through the game's own LandingGear.BreakWheel. Runs where ApplyDamage runs (every client, from RpcDamage). Config [Nimrod] CrashBreaksGear.
        //    1.4.2: lower wings no longer trigger it, threshold 40 -> 100 (the user's log: lower-wing hits of 61 / 140 after a leg had already gone).
        const float CrashGearImpact = 100f;
        static readonly Dictionary<Aircraft, float> crashTime = new Dictionary<Aircraft, float>();
        static readonly System.Reflection.MethodInfo BreakWheelM = typeof(LandingGear).GetMethod("BreakWheel", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public);

        void PatchCrashGear()
        {
            var on = Config.Bind("Nimrod", "CrashBreaksGear", true, "Break the Nimrod's undercarriage when its fuselage or a lower wing hits the ground hard (crash), not on landings.");
            if (!on.Value || BreakWheelM == null) return;
            try
            {
                var m = typeof(AeroPart).GetMethod("ApplyDamage", new[] { typeof(float), typeof(float), typeof(float), typeof(float) });
                new HarmonyLib.Harmony("b25h.instruments.nimrodcrash").Patch(m, postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(CrashGearPostfix), System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic)));
            }
            catch (System.Exception e) { Logger.LogWarning("Nimrod crash gear disabled: " + e.Message); }
        }

        static void CrashGearPostfix(AeroPart __instance, float netImpactDamage)
        {
            try
            {
                if (netImpactDamage < CrashGearImpact || __instance == null) return;
                var a = __instance.parentUnit as Aircraft;
                if (!IsFixedGear(a)) return;
                var n = __instance.name;
                if (__instance.gameObject != a.gameObject && n != "fus_engine") return;
                crashTime[a] = Time.time;
                int k = 0;
                foreach (var lg in a.GetComponentsInChildren<LandingGear>(true)) { BreakWheelM.Invoke(lg, null); k++; }
                if (k > 0) Log.LogInfo($"Nimrod crash: {n} impact {netImpactDamage:F0}, {k} gear legs broken");
            }
            catch { }
        }

        // 7. (1.4.2) Gear guard + diagnostic: the user's legs snapped on every landing and some take-offs with no crash-rule line before the
        //    break. Every LandingGear.BreakWheel on a Nimrod is logged with the leg's compression / limit / hinge angle / speeds. It is allowed
        //    for a crash (crash rule above within 1 s, or a vertical speed > GuardCrashVy at the break, or the leg's part detached); otherwise it
        //    is skipped and the leg re-enabled on the next Update (FixedUpdate disables it after the call). Config [Nimrod] GearGuard.
        const float GuardCrashVy = 9f;
        static BepInEx.Configuration.ConfigEntry<bool> gearGuard;
        static readonly HashSet<LandingGear> guardedLegs = new HashSet<LandingGear>();
        static readonly Dictionary<LandingGear, float> lastGuardLog = new Dictionary<LandingGear, float>();   // one BLOCKED line per leg per second
        static readonly System.Reflection.FieldInfo LgCompF = HarmonyLib.AccessTools.Field(typeof(LandingGear), "compressionDistance"),
            LgMaxF = HarmonyLib.AccessTools.Field(typeof(LandingGear), "maxCompression"), LgHingeF = HarmonyLib.AccessTools.Field(typeof(LandingGear), "gearHinge"),
            LgPartF = HarmonyLib.AccessTools.Field(typeof(LandingGear), "attachedPart"), LgAcF = HarmonyLib.AccessTools.Field(typeof(LandingGear), "aircraft"),
            LgSpringF = HarmonyLib.AccessTools.Field(typeof(LandingGear), "springRate");

        void PatchGearGuard()
        {
            gearGuard = Config.Bind("Nimrod", "GearGuard", true, "Stop the Nimrod's fixed undercarriage snapping off on landings and take-offs (it still breaks in a crash). Every break is logged with its cause.");
            if (BreakWheelM == null) return;
            try
            {
                new HarmonyLib.Harmony("b25h.instruments.nimrodgear").Patch(BreakWheelM, prefix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(BreakWheelPrefix), System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic)));
            }
            catch (System.Exception e) { Logger.LogWarning("Nimrod gear guard disabled: " + e.Message); }
        }

        static bool BreakWheelPrefix(LandingGear __instance)
        {
            try
            {
                var a = LgAcF.GetValue(__instance) as Aircraft;
                if (!IsFixedGear(a)) return true;
                var part = LgPartF.GetValue(__instance) as UnitPart;
                float comp = (float)LgCompF.GetValue(__instance), max = (float)LgMaxF.GetValue(__instance);
                var hinge = LgHingeF.GetValue(__instance) as Transform;
                float hx = hinge != null ? hinge.localEulerAngles.x : 0f;
                var v = part != null && part.rb != null ? part.rb.velocity : (a.rb != null ? a.rb.velocity : Vector3.zero);
                var caller = new System.Diagnostics.StackTrace(2, false).GetFrame(0)?.GetMethod()?.Name ?? "?";
                bool crash = crashTime.TryGetValue(a, out var ct) && Time.time - ct < 1f;
                bool detached = part == null || part.IsDetached();
                bool hard = Mathf.Abs(v.y) > GuardCrashVy;
                bool allow = gearGuard == null || !gearGuard.Value || crash || detached || hard || GearJam1915(__instance, a);   // 1.9.15 (DeckFilter1915.cs): a leg standing on another aircraft is a jam, not a landing
                if (allow || !lastGuardLog.TryGetValue(__instance, out var lt) || Time.time - lt > 1f)
                {
                    lastGuardLog[__instance] = Time.time;
                    Log.LogInfo($"NIMROD GEAR BREAK {(allow ? "ALLOWED" : "BLOCKED")} {__instance.name}: compression {comp:F3} / limit {max:F2} m, hinge x {hx:F1} deg, " +
                    $"spring {(float)LgSpringF.GetValue(__instance):F0}, v {v.magnitude:F1} m/s (vy {v.y:F1}), radarAlt {a.radarAlt:F1}, crash {crash}, detached {detached}, caller {caller}");
                }
                if (allow) return true;
                guardedLegs.Add(__instance);
                return false;
            }
            catch (System.Exception e) { Log.LogWarning("Nimrod gear guard: " + e.Message); return true; }
        }

        // FixedUpdate sets enabled = false right after a (skipped) BreakWheel; switch the leg back on
        static void ReenableGuardedLegs()
        {
            if (guardedLegs.Count == 0) return;
            foreach (var lg in guardedLegs) if (lg != null) lg.enabled = true;
            guardedLegs.Clear();
        }

        // 8. (1.5.5) Tail hook in flight: TailHook.CheckDeployConditions (stock, once a second) deploys at radarAlt 30-120 m, speed < 100 m/s,
        //    descending, and stows only above 100 m/s or below 2 m/s. The Mk I (max ~82 m/s) and the FD-32 (cruise ~90 m/s) never pass 100, so
        //    the hook stayed out for the rest of the flight (user shot 102). For NIMROD1 / FD32 only: deploy at radarAlt 30-120 m, speed < 50 m/s,
        //    descending, gear down; stow above 60 m/s, with the gear up, or below 2 m/s. Other aircraft run the stock method. Config [Nimrod] HookLogic.
        public static bool IsHookFixKey(string k) => k == NimrodKey || k == FD32Key || k == "A6M2";   // 2026-11-18: + A6M2 (stock deploys in any descent under 100 m/s, gear up too; approach 44 m/s fits the 50 / 60 law)
        public const float HookDeployBelow = 50f, HookStowAbove = 60f;
        public static int HookDecision(bool deployed, float radarAlt, float speed, float vy, bool gearDown)   // +1 deploy, -1 stow, 0 keep
        {
            if (!deployed && radarAlt > 30f && radarAlt < 120f && speed < HookDeployBelow && vy < 0f && gearDown) return 1;
            if (deployed && (speed > HookStowAbove || speed < 2f || !gearDown)) return -1;
            return 0;
        }
        static readonly System.Reflection.FieldInfo ThAcF = HarmonyLib.AccessTools.Field(typeof(TailHook), "aircraft"), ThDepF = HarmonyLib.AccessTools.Field(typeof(TailHook), "deployed"),
            ThHookedF = HarmonyLib.AccessTools.Field(typeof(TailHook), "hooked");

        void PatchHookDeploy()
        {
            var on = Config.Bind("Nimrod", "HookLogic", true, "Deploy / stow the Nimrod Mk I and FD-32 tail hooks at speeds that fit these slow aircraft (the stock logic never stows them in flight).");
            if (!on.Value) return;
            try
            {
                var m = HarmonyLib.AccessTools.Method(typeof(TailHook), "CheckDeployConditions");
                new HarmonyLib.Harmony("b25h.instruments.nimrodhook").Patch(m, prefix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(HookDeployPrefix), System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic)));
            }
            catch (System.Exception e) { Logger.LogWarning("Nimrod hook logic disabled: " + e.Message); }
        }

        static bool HookDeployPrefix(TailHook __instance)
        {
            try
            {
                var a = ThAcF.GetValue(__instance) as Aircraft;
                if (a == null || a.definition == null || !IsHookFixKey(a.definition.jsonKey) || a.rb == null) return true;
                bool dep = (bool)ThDepF.GetValue(__instance);
                int d = HookDecision(dep, a.radarAlt, a.speed, a.rb.velocity.y, a.gearDeployed);
                bool mine = SceneSingleton<CombatHUD>.i != null && a == SceneSingleton<CombatHUD>.i.aircraft;
                if (d > 0)
                {
                    if (mine) SceneSingleton<AircraftActionsReport>.i.ReportText("Tail Hook Deployed", 4f);
                    ThDepF.SetValue(__instance, true); __instance.enabled = true;
                }
                else if (d < 0)
                {
                    if (mine) SceneSingleton<AircraftActionsReport>.i.ReportText("Tail Hook Retracted", 4f);
                    ThDepF.SetValue(__instance, false);
                    if ((bool)ThHookedF.GetValue(__instance)) __instance.Unhook();
                }
                return false;
            }
            catch (System.Exception e) { Log.LogWarning("Nimrod hook logic: " + e.Message); return true; }
        }

        void ScanNimrod()
        {
            if (nimrodHookVisual == null) nimrodHookVisual = Config.Bind("Nimrod", "HookVisual", true, "Move the Nimrod's visible A-frame arrester hook with the game's (hidden) functional tail hook.");
            foreach (var a in PassAircraft())
            {
                if (a == null || nimrods.ContainsKey(a) || a.definition == null || !IsFixedGearKey(a.definition.jsonKey)) continue;
                var g = new NimrodGauges { aircraft = a };
                var all = new HashSet<Transform>(a.GetComponentsInChildren<Transform>(true));
                if (a.partLookup != null)
                    foreach (var part in a.partLookup)
                        if (part != null) foreach (var pt in part.GetComponentsInChildren<Transform>(true)) all.Add(pt);
                foreach (var tr in all)
                {
                    if (System.Array.IndexOf(NimrodNames, tr.name) >= 0 && !g.t.ContainsKey(tr.name)) { g.t[tr.name] = tr; g.rest[tr.name] = tr.localRotation; }
                    if (tr.name == "hook_visual" && g.hookVis == null) { g.hookVis = tr; g.hookVisRest = tr.localRotation; }
                    if (g.engine == null) g.engine = tr.GetComponent<TurbineEngine>();
                    if (g.prop == null) g.prop = tr.GetComponent<ConstantSpeedProp>();
                }
                if (g.t.Count == 0 && a.definition.jsonKey == NimrodKey)   // 1.5.0: the FD-32 has no needles (attach at once)
                {
                    nimrodMisses.TryGetValue(a, out var m); nimrodMisses[a] = m + 1;
                    if (m + 1 < 10) continue;
                }
                nimrods[a] = g;
                Logger.LogInfo($"Nimrod instruments attached to {a.name} ({a.definition.jsonKey}): {g.t.Count}/{NimrodNames.Length} movers, engine {(g.engine != null)}");
            }
        }

        void DriveNimrodAll()
        {
            ReenableGuardedLegs();
            if (nimrods.Count == 0) return;
            List<Aircraft> dead = null;
            foreach (var kv in nimrods)
            {
                if (kv.Key == null) { (dead = dead ?? new List<Aircraft>()).Add(kv.Key); continue; }
                try { DriveNimrod(kv.Value); } catch (System.Exception e) { Logger.LogWarning("Nimrod gauges: " + e.Message); (dead = dead ?? new List<Aircraft>()).Add(kv.Key); }
            }
            if (dead != null) foreach (var a in dead) nimrods.Remove(a);
        }

        static void SetN(NimrodGauges g, string n, float deg)
        {
            if (g.t.TryGetValue(n, out var tr) && tr != null) tr.localRotation = g.rest[n] * Quaternion.AngleAxis(deg, Vector3.right);
        }

        void DriveNimrod(NimrodGauges g)
        {
            var a = g.aircraft;
            if (a.disabled) return;
            var tr = a.transform;
            float dt = Mathf.Max(Time.deltaTime, 1e-4f);
            SetN(g, "gauge_asi_needle", NimrodMath.Asi(a.speed, a.airDensity));
            float altM = tr.position.GlobalY();
            SetN(g, "gauge_alt_needle", NimrodMath.AltLong(altM));
            SetN(g, "gauge_alt_needle_short", NimrodMath.AltShort(altM));
            var e = g.engine;
            // 1.8.4 (in game 1.8.2: rpm + oil P needles fixed while the prop went 1626 -> 1523 rpm): TurbineEngine.GetRPM is maxRPM whenever
            // the engine runs (TurbineEngine.cs:286); the engine rpm the pilot reads follows the propeller shaft (ConstantSpeedProp RPM / rpmLimit)
            float rpmRatio = g.prop != null ? g.prop.GetRPMRatio() : e != null ? e.GetRPMRatio() : 0f;
            bool running = e != null && e.GetRPMRatio() > 0.05f && rpmRatio > 0.05f;
            SetN(g, "gauge_rpm_needle", NimrodMath.Rpm(DialMath.EngineRpm(rpmRatio, NimrodMath.RatedRpm)));
            SetN(g, "gauge_boost_needle", NimrodMath.Boost(NimrodMath.BoostPsi(e != null ? e.throttle : 0f, rpmRatio, running)));
            SetN(g, "gauge_oilp_needle", NimrodMath.OilPsi(rpmRatio, running) * NimrodMath.OilPDegPerPsi);
            g.oilT = NimrodMath.Lag(g.oilT, NimrodMath.OilTTarget(e != null ? e.powerRatio : 0f, running), dt, 60f);
            g.water = NimrodMath.Lag(g.water, NimrodMath.WaterTarget(e != null ? e.powerRatio : 0f, running), dt, 40f);
            SetN(g, "gauge_oilt_needle", g.oilT * NimrodMath.OilTDegPerC);
            SetN(g, "gauge_water_needle", g.water * NimrodMath.WaterDegPerC);
            SetN(g, "gauge_fuel_needle", Mathf.Clamp01(a.GetFuelLevel()) * 100f * NimrodMath.FuelDegPerPct);
            var rb = a.rb;
            if (rb != null)
            {
                SetN(g, "gauge_turn_needle", NimrodMath.Turn(rb.angularVelocity.y * Mathf.Rad2Deg));
                var v = rb.velocity;
                var acc = g.havePrev ? (v - g.vPrev) / dt : Vector3.zero;
                g.vPrev = v; g.havePrev = true;
                var down = tr.InverseTransformDirection(Physics.gravity - acc);      // apparent gravity in the aircraft frame
                g.slip = Mathf.Lerp(g.slip, NimrodMath.Slip(down.x, down.y), Mathf.Clamp01(dt * 4f));
                SetN(g, "gauge_slip_needle", g.slip);
            }
            SetN(g, "gauge_compass_card", NimrodMath.Compass(tr.eulerAngles.y));
            DriveHook(g);
        }

        // the TailHook lives on the hook WeaponMount spawned with the loadout (may appear after the first scan): looked up every 2 s until found
        void DriveHook(NimrodGauges g)
        {
            if (g.hookVis == null || nimrodHookVisual == null || !nimrodHookVisual.Value) return;
            if (g.hookFn == null)
            {
                if (Time.time < g.nextHookScan) return;
                g.nextHookScan = Time.time + 2f;
                var a = g.aircraft;
                TailHook th = a.GetComponentInChildren<TailHook>(true);
                if (th == null && a.partLookup != null)
                    foreach (var part in a.partLookup) { if (part == null) continue; th = part.GetComponentInChildren<TailHook>(true); if (th != null) break; }
                if (th == null || HookField == null) return;
                g.hookFn = HookField.GetValue(th) as Transform;
                if (g.hookFn == null) return;
                if (StowField != null && StowField.GetValue(th) is float st) g.hookStow = st;
                Logger.LogInfo($"Nimrod hook A-frame linked to {th.name}");
            }
            float amt = NimrodMath.HookAmountFrom(g.hookFn.localEulerAngles.x, g.hookStow);
            g.hookVis.localRotation = g.hookVisRest * Quaternion.AngleAxis(NimrodMath.HookVisualDeg(amt), Vector3.right);
        }
    }
}
