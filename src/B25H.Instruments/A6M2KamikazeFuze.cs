// A6M2 round 3 (offline worker, 2026-11-18): crash / shoot-down fuze for the A6M2's 250 kg special-attack charge (Event Content).
//
// Design: docs/a6m2_design.md 3.4. Game 0.34.6 read as reference only:
// - a crash or a death never detonates a carried weapon: UnitPart.TakeDamage disables the unit, Aircraft.UnitDisabled only schedules removal
//   after 30 s (Aircraft.cs:2202-2225), MountedMissile.OnDestroy only removes mass / drag / RCS. So "blows up when the plane crashes" needs code.
// - the pilot's trigger is the stock path: WeaponStation.LaunchMount (WeaponStation.cs:486-521) -> MountedMissile.Fire -> RailLaunch ->
//   Spawner.SpawnMissile (server) -> the charge's own 0.02 s time fuse (OpticalSeeker.cs:119-137) bursts it beside the aircraft.
// This piece (server / host only, A6M2 only):
// 1. arming latch per aircraft: arms once airborne (radarAlt > 30 m with the gear LockedRetracted, or 10 s off the ground); disarms on
//    IsLanded() (Aircraft.cs:1560-1567) and when the unit is Returned (ReturnToInventory, Aircraft.cs:2227-2252). A parked or landed Zero never
//    detonates.
// 2. fired guard: Harmony postfix on WeaponStation.LaunchMount records the time a charge station fired; nothing re-fires within 5 s (the
//    Infinite Ammo refill race, design K7).
// 3. Harmony postfix on Aircraft.UnitDisabled: when the Zero is disabled while armed, still carrying the charge (station Ammo > 0, weapon
//    attached), not Returned and not fired in the last 5 s: radarAlt < 15 m -> LaunchMount at once (it has hit something); higher -> watch the
//    wreck and fire on the first linecast hit along its velocity, below sea level, or after 25 s (before the stock removal at 30 s).
// No friendly-proximity gate (orchestrator 2026-11-18, design 12.Q3): the user's rule is literal.
// r6 (game probes K4 / K5 on r2, MODLOG 05b88a5): the wreck watch never ran - UnitRegistry drops a unit from allAircraft the moment it is
//   disabled (UnitRegistry.cs:26-33, Registry_OnUnitDisable), and KamikazeStep walked allAircraft, so a watched wreck was never stepped again
//   (K4 player: "watching the wreck", then nothing; the 25 s backstop lived in the same dead loop). Now the step walks our own table (kz),
//   which keeps every A6M2 it has seen, and it also notices the disabled transition itself (K5: AI crashes in the landing state logged nothing:
//   no postfix line at all, so the postfix either did not run or returned at a silent gate; every gate now logs). The watch fires on the first
//   of: linecast hit along the velocity, wreck stopped (< 3 m/s for 0.5 s), below the sea, 25 s. Disarm only on a real landing: IsLanded()
//   (radarAlt < 5 m, speed < 2.5 m/s, Aircraft.cs:1560-1567) AND no part detached; a crash with the gear down stays armed.
// Flag: config [A6M2] KamikazeFuze = Auto (build default OFF until probes K3-K7 pass) / On / Off. Any exception switches it off for the session.
// Pure laws in KamikazeFuzeMath (mirrored in tools/stub_tests_a6m2_r3.py).
// SHIP GATE: the file name starts with A6M2 so tools/make_public_tree.py leaves it out; Nimrod.cs / GroundGrip189.cs call it through
// partial methods (declared in Nimrod.cs), which the compiler drops when this file is absent.
using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class KamikazeFuzeMath
    {
        public const string Key = "A6M2";
        public const string ChargeInfo = "A6M2_tokko_info";   // WeaponInfo asset name of the charge (A6M2Build.Stores)
        public const float ArmAlt = 30f;          // m radar altitude with the gear up
        public const float ArmAirborne = 10f;     // s off the ground (radarAlt > 5) arms regardless of the gear
        public const float ImpactAlt = 15f;       // disabled below this = it has hit something: fire at once
        public const float FiredGuard = 5f;       // s
        public const float WatchTimeout = 25f;    // s (the stock removal is at 30 s)
        public const float StopSpeed = 3f;        // m/s: a wreck slower than this ...
        public const float StopHold = 0.5f;       // s ... for this long has come to rest (r6)

        /// latch: landed or returned clears it; otherwise it stays armed once the arming condition was met
        public static bool Armed(bool wasArmed, bool landed, bool returned, float radarAlt, bool gearRetracted, float airborneSeconds)
        {
            if (landed || returned) return false;
            if (wasArmed) return true;
            return (radarAlt > ArmAlt && gearRetracted) || airborneSeconds > ArmAirborne;
        }

        /// the disabled postfix acts only for an armed, server-side, not-returned aircraft still carrying an attached charge not fired just now
        public static bool ActOnDisabled(bool nowDisabled, bool server, bool returned, bool armed, int chargeAmmo, bool attached, float sinceFired)
            => nowDisabled && server && !returned && armed && chargeAmmo > 0 && attached && sinceFired > FiredGuard;

        public static bool Immediate(float radarAlt) => radarAlt < ImpactAlt;

        /// r7: one fire per guard window (the pilot's trigger postfix stamps firedAt too)
        public static bool MayFire(float sinceFired) => sinceFired > FiredGuard;

        /// watched wreck: fire on impact (linecast hit along the velocity), below the sea surface, or at the timeout
        public static bool WatchFire(bool hit, float heightAboveSea, float watchedSeconds, float stoppedSeconds) => hit || heightAboveSea < 0f || stoppedSeconds >= StopHold || watchedSeconds >= WatchTimeout;

        /// r6: a real landing (disarms) = IsLanded() and intact; a crash with the gear down is not a landing
        public static bool RealLanding(bool isLanded, bool anyPartDetached) => isLanded && !anyPartDetached;
    }

    public partial class Plugin
    {
        const bool KamikazeFuzeDefault = A6M2DefaultsMath.On;   // r7: off unless built with A6M2_DEFAULTS_ON (handover build), A6M2Defaults.cs
        static BepInEx.Configuration.ConfigEntry<string> kamikazeMode;
        static bool kamikazeBroken;
        static int kamikazeLogs;
        class KzState { public bool armed; public float airborneSince = -1f; public float firedAt = -100f; public bool watching; public float watchStart; public HashSet<Collider> own;
                        public bool handled; public float slowSince = -1f; public bool dupLogged; }
        static readonly Dictionary<Aircraft, KzState> kz = new Dictionary<Aircraft, KzState>();
        static readonly RaycastHit[] kzHits = new RaycastHit[16];
        float kzNextPrune;

        static bool KamikazeOn
        {
            get { var m = kamikazeMode != null ? kamikazeMode.Value : "Auto"; return m == "On" || (m != "Off" && KamikazeFuzeDefault); }
        }

        static bool IsKz(Aircraft a) => a != null && a.definition != null && a.definition.jsonKey == KamikazeFuzeMath.Key;

        partial void PatchKamikazeFuze()
        {
            kamikazeMode = Config.Bind("A6M2", "KamikazeFuze", "Auto", "A6M2 250 kg special-attack charge: detonate when the armed aircraft crashes or is shot down (server / host only). " + A6M2DefaultsMath.AutoText);
            A6M2MigrateKey(kamikazeMode);
            if (!KamikazeOn) { Logger.LogInfo("A6M2 kamikaze fuze: off (config [A6M2] KamikazeFuze)"); return; }
            try
            {
                const BindingFlags f = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
                var dis = typeof(Aircraft).GetMethod("UnitDisabled", f, null, new[] { typeof(bool), typeof(bool) }, null);
                var launch = typeof(WeaponStation).GetMethod("LaunchMount", f);
                if (dis == null || launch == null) { Logger.LogWarning("A6M2 kamikaze fuze disabled: Aircraft.UnitDisabled / WeaponStation.LaunchMount not found"); return; }
                var h = new HarmonyLib.Harmony("b25h.instruments.a6m2kamikaze");
                h.Patch(dis, postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(KzDisabledPostfix), BindingFlags.Static | BindingFlags.NonPublic)));
                h.Patch(launch, prefix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(KzLaunchPrefix), BindingFlags.Static | BindingFlags.NonPublic)),
                    postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(KzLaunchPostfix), BindingFlags.Static | BindingFlags.NonPublic)));
                Logger.LogInfo("A6M2 kamikaze fuze on: arming latch, 5 s fired guard, crash / shoot-down detonation (server only)");
            }
            catch (Exception e) { kamikazeBroken = true; Logger.LogWarning("A6M2 kamikaze fuze disabled: " + e.Message); }
        }

        static WeaponStation KzStation(Aircraft a)
        {
            if (a.weaponStations == null) return null;
            foreach (var s in a.weaponStations)
                if (s != null && s.WeaponInfo != null && s.WeaponInfo.name == KamikazeFuzeMath.ChargeInfo) return s;
            return null;
        }

        static bool KzAttached(WeaponStation s)
        {
            foreach (var w in s.Weapons) if (w != null && w.IsAttached()) return true;
            return false;
        }

        /// r7: a second launch of the charge station inside the guard window (Infinite Ammo refills the station at once, the trigger is still
        /// held) is skipped, so exactly one charge leaves per window; logged once per aircraft
        static bool KzLaunchPrefix(WeaponStation __instance, Unit owner)
        {
            if (kamikazeBroken) return true;
            try
            {
                if (__instance.WeaponInfo == null || __instance.WeaponInfo.name != KamikazeFuzeMath.ChargeInfo || !(owner is Aircraft a)) return true;
                if (!kz.TryGetValue(a, out var st) || KamikazeFuzeMath.MayFire(Time.time - st.firedAt)) return true;
                if (!st.dupLogged) { st.dupLogged = true; KzLog($"{a.name} second charge launch inside the {KamikazeFuzeMath.FiredGuard} s guard skipped"); }
                return false;
            }
            catch (Exception e) { kamikazeBroken = true; Log.LogWarning("A6M2 kamikaze fuze off (launch prefix): " + e.Message); return true; }
        }

        static void KzLaunchPostfix(WeaponStation __instance, Unit owner)
        {
            if (kamikazeBroken) return;
            try
            {
                if (__instance.WeaponInfo == null || __instance.WeaponInfo.name != KamikazeFuzeMath.ChargeInfo || !(owner is Aircraft a)) return;
                if (!kz.TryGetValue(a, out var st)) kz[a] = st = new KzState();
                if (KamikazeFuzeMath.MayFire(Time.time - st.firedAt) && kamikazeLogs++ < 80) Log.LogInfo($"A6M2 kamikaze fuze: {a.name} charge launched by the pilot (trigger); fuze guard {KamikazeFuzeMath.FiredGuard} s");
                st.firedAt = Time.time; st.watching = false;
            }
            catch (Exception e) { kamikazeBroken = true; Log.LogWarning("A6M2 kamikaze fuze off (launch postfix): " + e.Message); }
        }

        static void KzDisabledPostfix(Aircraft __instance, bool newState)
        {
            if (kamikazeBroken || !newState || !IsKz(__instance)) return;
            try
            {
                if (!kz.TryGetValue(__instance, out var st)) { KzLog($"{__instance.name} disabled before the fuze saw it: not armed"); return; }
                KzOnDisabled(__instance, st, "postfix");
            }
            catch (Exception e) { kamikazeBroken = true; Log.LogWarning("A6M2 kamikaze fuze off (disabled postfix): " + e.Message); }
        }

        static void KzLog(string m) { if (kamikazeLogs++ < 80) Log.LogInfo("A6M2 kamikaze fuze: " + m); }

        static bool KzAnyDetached(Aircraft a)
        {
            if (a.partLookup == null) return false;
            foreach (var p in a.partLookup) if (p != null && p.IsDetached()) return true;
            return false;
        }

        /// r6: one entry for the disabled transition (Harmony postfix OR the step noticing a.disabled), runs once per aircraft, logs every gate
        static void KzOnDisabled(Aircraft a, KzState st, string via)
        {
            if (st.handled) return;
            st.handled = true;
            var s = KzStation(a);
            bool returned = a.unitState == Unit.UnitState.Returned;
            int ammo = s != null ? s.Ammo : 0;
            bool att = s != null && KzAttached(s);
            float since = Time.time - st.firedAt;
            bool act = KamikazeFuzeMath.ActOnDisabled(a.disabled, a.IsServer, returned, st.armed, ammo, att, since);
            KzLog($"{a.name} disabled ({via}) at radarAlt {a.radarAlt:F1} m speed {a.speed:F1} m/s gear {a.gearState}: armed {st.armed}, server {a.IsServer}, returned {returned}, charge {ammo}, attached {att}, since fired {since:F0} s -> {(act ? (KamikazeFuzeMath.Immediate(a.radarAlt) ? "fire" : "watch") : "no action")}");
            if (!act) return;
            if (KamikazeFuzeMath.Immediate(a.radarAlt)) KzFire(a, s, st, "impact");
            else { st.watching = true; st.watchStart = Time.time; st.slowSince = -1f; st.own = KzColliders(a); }
        }

        static HashSet<Collider> KzColliders(Aircraft a)
        {
            var hs = new HashSet<Collider>(a.GetComponentsInChildren<Collider>(true));
            if (a.partLookup != null) foreach (var p in a.partLookup) if (p != null) foreach (var c in p.GetComponentsInChildren<Collider>(true)) hs.Add(c);
            return hs;
        }

        static void KzFire(Aircraft a, WeaponStation s, KzState st, string why)
        {
            // r7 (K7 with Infinite Ammo: a second "fired" line at the trigger moment, one blast): every fire path goes through this one guard,
            // so the fuze acts AND logs at most once per FiredGuard window, whatever path (pilot trigger, impact, watch) came first.
            if (!KamikazeFuzeMath.MayFire(Time.time - st.firedAt)) { st.watching = false; return; }
            st.watching = false;
            s.LaunchMount(a, null, a.GlobalPosition());          // the launch prefix lets this one through (guard still open), the postfix stamps firedAt
            st.firedAt = Time.time;
            if (kamikazeLogs++ < 40) Log.LogInfo($"A6M2 kamikaze fuze: {a.name} charge fired ({why}) at radarAlt {a.radarAlt:F1} m, pos {a.transform.position}");
        }

        // one step per physics frame, called first in Plugin.FixedUpdate (GroundGrip189.cs): the partial class has one FixedUpdate
        static readonly List<Aircraft> kzKeys = new List<Aircraft>();
        partial void KamikazeStep()
        {
            if (kamikazeBroken || !KamikazeOn) return;
            try
            {
                float now = Time.time;
                foreach (var a in UnitRegistry.allAircraft)                      // live, non-disabled aircraft: register them
                    if (IsKz(a) && a.IsServer && !kz.ContainsKey(a)) kz[a] = new KzState();
                kzKeys.Clear(); kzKeys.AddRange(kz.Keys);                        // r6: walk OUR table (disabled units leave allAircraft)
                foreach (var a in kzKeys)
                {
                    if (a == null || !a.IsServer) continue;
                    var st = kz[a];
                    if (!a.disabled)
                    {
                        st.handled = false; st.watching = false;                 // re-enabled (repaired / respawned object): a later disable counts again
                        bool off = a.radarAlt > 5f;
                        if (!off) st.airborneSince = -1f; else if (st.airborneSince < 0f) st.airborneSince = now;
                        st.armed = KamikazeFuzeMath.Armed(st.armed, KamikazeFuzeMath.RealLanding(a.IsLanded(), KzAnyDetached(a)), a.unitState == Unit.UnitState.Returned, a.radarAlt,
                            a.gearState == LandingGear.GearState.LockedRetracted, st.airborneSince < 0f ? 0f : now - st.airborneSince);
                        continue;
                    }
                    if (!st.handled) KzOnDisabled(a, st, "step");              // r6: the postfix may not run for every disable path
                    if (!st.watching) continue;
                    var s = KzStation(a);
                    if (s == null || s.Ammo <= 0 || !KzAttached(s) || a.unitState == Unit.UnitState.Returned)
                    {
                        st.watching = false;
                        KzLog($"{a.name} watch ended without firing: station {(s != null)}, charge {(s != null ? s.Ammo : 0)}, attached {(s != null && KzAttached(s))}, state {a.unitState}");
                        continue;
                    }
                    var v = a.rb != null ? a.rb.velocity : Vector3.zero;
                    var p = a.transform.position;
                    bool hit = false;
                    float d = v.magnitude * Time.fixedDeltaTime * 2f + 1f;
                    if (v.sqrMagnitude > 0.01f)
                    {
                        int n = Physics.RaycastNonAlloc(p, v.normalized, kzHits, d, ~0, QueryTriggerInteraction.Ignore);
                        for (int i = 0; i < n && !hit; i++) if (kzHits[i].collider != null && (st.own == null || !st.own.Contains(kzHits[i].collider))) hit = true;
                    }
                    if (v.magnitude < KamikazeFuzeMath.StopSpeed) { if (st.slowSince < 0f) st.slowSince = now; } else st.slowSince = -1f;
                    float stopped = st.slowSince < 0f ? 0f : now - st.slowSince;
                    if (KamikazeFuzeMath.WatchFire(hit, p.y - Datum.LocalSeaY, now - st.watchStart, stopped))
                        KzFire(a, s, st, hit ? "wreck impact" : (p.y < Datum.LocalSeaY ? "sea" : (stopped >= KamikazeFuzeMath.StopHold ? "wreck stopped" : "timeout")));
                }
                if (now > kzNextPrune)
                {
                    kzNextPrune = now + 10f;
                    List<Aircraft> dead = null;
                    foreach (var kv in kz) if (kv.Key == null) (dead = dead ?? new List<Aircraft>()).Add(kv.Key);
                    if (dead != null) foreach (var a in dead) kz.Remove(a);
                }
            }
            catch (Exception e) { kamikazeBroken = true; Log.LogWarning("A6M2 kamikaze fuze off (step): " + e.Message); }
        }
    }
}
