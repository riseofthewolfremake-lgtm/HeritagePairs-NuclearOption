// B25H.Instruments 1.9.15 AiGroundWatch1915: host-side watchdog for AI aircraft on the ground in the stock taxi / take-off states
// (bugs 1-3 of 2026-11-26: "crew refuse to bail out, blocking airfields"; "stuck turning in a circle ... never take off and never bail out";
// "stuck together ... crew refuse to bailout").
//
// Stock gaps (decompiled AIPilotTaxiState / AIPilotTakeoffState, MODLOG "Bug repro 11-26"): the taxi state listens for damage on the ROOT part
// only (Taxi_OnTakeDamage), nothing on the ground checks for detached parts, and the stuck timers are reset by the bang-bang brake, by
// brakeUrgency and by Wait(): a tailless B-17G drove off for 284 s, two never ejected; a CI-22 circled 19+ times in 1,100 s; two aircraft
// wedged together are each other's obstacle (brakeUrgency >= 1 -> throttle < 0.1 zeroes both timers every frame).
// Acts only when ALL hold: the server (IsServer); no Player and no player-flown pilot seat (AiOnly1915, every pilot); radarAlt < 2 m; the
// current state is the stock taxi or take-off state (parked is never touched); in the take-off state only until it first passes 40 m/s.
// Triggers, evaluated once a second per aircraft:
//   W1 structural (our seven aircraft): a detached part (partDamageTracker.GetDetachedRatio() > 0; after a landing only a part lost since the
//      state began), a wheel leg that was live when the state began and is gone / disabled on two evaluations in a row, or any part that
//      lost >= 10 hit points since the 20 s spawn grace ended (round 2; round 1: >= 1 hp with no grace - a scrape bailed out a healthy crew;
//      damage inside the grace becomes the new baseline) -> eject. The detach and wheel rules have no grace (the B-17G tail went at 0.85 s).
//   W2 no progress: net displacement < 10 m over 60 s (240 s while brakeUrgency held it in the last 60 s; 180 s on a carrier), never while
//      waiting for take-off clearance / at a runway crossing / yielding, 20 s spawn grace; in the take-off state only above 1 m/s.
//   W3 orbit: cumulative |heading change| > 540 deg in 45 s while the progress (taxi: distance to the destination; take-off: distance along
//      the runway) improved by < 10 m; in the take-off state only before the take-off run.
//   W2 / W3 escalate in the taxi state, one step per 45 s without progress: 1 re-path (ClearDestination + Pathfind), 2 head straight for the
//      destination (moving target, AiTaxiDeadEnd1915), 3 hand over to the take-off state if bound for the runway and < 80 m from its start,
//      4 eject. In the take-off state they eject. Round 2: step 3 only through HandOverClear1915 (stock clearance check + on the runway
//      polygon or < 12 m); held by the queue / an obstacle it waits another step (at most 3 times), off the runway it ejects.
//   W4 contact: in contact with another aircraft (ContactProbe1915 on every part body, or a wheel standing on it) for > 10 of the last 15 s
//      with both under 3 m/s or moving together -> eject this one, and the other too when it is AI-flown, on the ground and in the stock taxi
//      state or the take-off state below 40 m/s (stock included: it is stuck to ours; round 2: never parked or another state). A
//      player-flown aircraft is never touched.
// Eject action: throttle 0 + brake 1 every frame; leave the take-off queue; taxi state: the stock Disembark (disembarking = true, ejects
//   below 1 m/s), and after 10 s still >= 1 m/s StartEjectionSequence directly; take-off state: StartEjectionSequence below 2 m/s or after
//   10 s. The stock sequence returns the aircraft to inventory (< 2 m/s near a friendly airbase) or disables and removes it: the spot clears.
// Round 3 (code review of round 2): (2) an aircraft held by the obstacle brake behind another aircraft of its airbase that is queued, waiting
//   or moving (< 60 m ahead) is in a queue: W2 / W3 restart, the ladder never runs (QueueLeader1915); (3) the other aircraft of a stuck pair
//   always gets an ejecting watch (throttle 0 / brake 1 every frame, the 10 s fallback), also a stock aircraft with scope Ours; (4) contact
//   probes are added on every machine and lazily when a watch starts, and record only on the server.
// Round 4 (round-3 acceptance run: "FD32 held behind MSB17" and "MSB17 held behind FD32" in the same second): a held-behind chain that
//   comes back to the aircraft itself (A behind B behind A, or a longer circle; held-behind records live 3 s) is not a queue - the leader is
//   skipped, so one of the pair runs W2 / W3 and the ladder breaks the tie; and a queue hold that lasted > 300 s with < 10 m moved since it
//   began no longer restarts W2 / W3. Counters (d): ejects per trigger, each with a "suspected false eject" flag (W1 from light damage only:
//   no part off, no wheel lost, < 25 hp; W2 / W3 with the obstacle brake or a wait in the last 60 s, or an aircraft of the airbase < 60 m
//   ahead), the forced ejection sequences, queue holds and mutual / expired holds ignored - in the log line of each eject and in the 120 s
//   "1.9.15 counters" summary (Bugs1915.cs).
// Round 8 (round-7 acceptance: Mk I #-712656 circled its stock yield point for 435 game s after landing, csv yielding = True throughout, and
//   no rule fired): (1) the stock yield counts as a wait only for its first YieldWaitMax s (a stock yield is a ~50 m pull-aside, ~8 s); until
//   round 7 "yielding" restarted W2 / W3 every second for as long as it lasted; (2) W3's progress is the window minimum of the destination
//   distance against the minimum before the window (with nothing before it: the second half of the window against the first half; round 7
//   took the window's FIRST sample - the far side of an off-centre circle gave ~40 m of "progress" every lap); (3) W5 heading orbit (taxi
//   state): cumulative |heading change| > 720 deg in 90 s while every sample stayed within 60 m of the window centroid and the window made
//   < 10 m of progress - regardless of the target geometry, waits, yields, queue holds and a hand-over held off the runway; (4) a yielding
//   aircraft that W2 / W3 / W5 find stuck gets the yield's own stock end (the disembark) at once: re-path / direct steering cannot act while
//   the stock yield branch steers. Queue / mutual / expired / yield lines have their own log budget (WQLog1915).
// Config [Ground] AiGroundWatch1915 = Auto (on) / On / Off; AiGroundWatchScope = Ours (default: W2-W4 on our seven) / All (W2-W4 on every AI
// aircraft; W1 is always ours only). One log line per trigger. Round 5: an exception drops the watch of that aircraft only; 20 exceptions
// switch the whole watch off for the session (round 1-4: the first exception did).
using System;
using System.Collections.Generic;
using UnityEngine;

namespace B25H.Instruments
{
    public static class GroundWatchMath1915
    {
        public const float AltMax = 2f, TakeoffSpeedMax = 40f, HpLoss = 10f;   // round 2: 10 hp (round 1: 1 hp), counted after the spawn grace
        public const int MaxDefer = 3;                                          // round 2: ladder hand-over held by the queue / an obstacle: at most 3 waits
        public const float ProgressDist = 10f, Window = 60f, UrgentWindow = 240f, CarrierWindow = 180f, UrgentMemory = 60f, SpawnGrace = 20f;
        public const float TakeoffCreep = 1f;
        public const float OrbitDeg = 540f, OrbitWindow = 45f, OrbitGain = 10f, StepTime = 45f, HandOverDist = 80f, LadderReset = 135f;
        public const int ContactWindow = 15, ContactNeed = 10;
        public const float ContactSlow = 3f, ContactTogether = 1.5f;
        public const float EjectFallback = 10f, TaxiEjectBelow = 1f, TakeoffEjectBelow = 2f;
        /// round 5: exceptions before the whole watch switches off (one exception drops only that aircraft's watch)
        public const int MaxWatchErrors = 20;
        public static bool WatchDisable(int errors) => errors >= MaxWatchErrors;

        /// W1: structural damage since the state began
        public static bool Structural(float detachedRatio, int gearLostTwice, float worstHpLoss) => detachedRatio > 0f || gearLostTwice > 0 || worstHpLoss >= HpLoss;
        /// round 2: the hit-point rule only counts after the spawn grace; damage taken inside it is the new baseline (settling / a first scrape)
        public static bool HpRuleActive(float now, float graceEnd) => now >= graceEnd;
        /// round 2 ladder step 3: a hand-over held by the queue / an obstacle waits one more step, at most MaxDefer times; off the runway: no
        public static bool DeferHandOver(bool clearanceBlock, int deferrals) => clearanceBlock && deferrals < MaxDefer;
        /// round 2: the other aircraft of a stuck pair is only ejected from the stock taxi state, or the take-off state below 40 m/s - never
        /// parked, never in the air / another state
        public static bool OtherEjectable(bool taxiState, bool takeoffState, float speed) => taxiState || (takeoffState && speed <= TakeoffSpeedMax);
        /// round 3 (review 2): an aircraft held by the stock obstacle brake behind another aircraft of the same airbase that is itself queued,
        /// waiting or moving is in a queue, not stuck: W2 / W3 restart and the ladder never runs (no moving target off the taxi network, no eject)
        public const float QueueGap = 60f, QueueMoving = 0.5f, QueueUrgency = 0.1f;
        public static bool Advancing(float speed, bool takeoffState, bool queuedOrWaiting) => speed > QueueMoving || takeoffState || queuedOrWaiting;
        public static bool QueueHeld(float brakeUrgency, float aheadDot, float gap, bool leaderAdvancing) => brakeUrgency > QueueUrgency && aheadDot >= 0f && gap < QueueGap && leaderAdvancing;
        /// round 4: held-behind records live HeldMemory s; a chain is followed for CycleHops; a queue hold expires after QueueHoldMax s with
        /// less than ProgressDist moved since it began
        public const float HeldMemory = 3f, QueueHoldMax = 300f, SuspectHp = 25f;
        public const int CycleHops = 8;
        /// round 4: the held-behind chain from `start` (next(x) = the aircraft x is held behind, null = none) comes back to `self`: a mutual /
        /// circular hold, not a queue (the round-3 FD32 <-> MSB17 pair would reset W2 / W3 for both, for ever)
        public static bool HoldCycle<T>(Func<T, T> next, T start, T self, int maxHops) where T : class
        {
            var x = start;
            for (int h = 0; h < maxHops && x != null; h++) { if (ReferenceEquals(x, self)) return true; x = next(x); }
            return false;
        }
        /// round 4: a queue hold that lasted > QueueHoldMax with < ProgressDist moved since it began is not a queue any more
        public static bool QueueHoldExpired(float heldFor, float moved) => heldFor > QueueHoldMax && moved < ProgressDist;
        /// round 4 (d): suspected false ejects (counted, logged; the eject still happens)
        public static bool SuspectW1(float detachedDelta, int wheelsLost, float worstHpLoss) => detachedDelta <= 0f && wheelsLost == 0 && worstHpLoss < SuspectHp;
        public static bool SuspectStuck(bool urgentRecently, bool waitedRecently, bool aircraftAhead) => urgentRecently || waitedRecently || aircraftAhead;
        /// W2 window (s)
        /// round 8: the stock yield is a wait only for its first YieldWaitMax s (round 1-7: for as long as it lasted - the Mk I yield orbit)
        public const float YieldWaitMax = 30f;
        public static bool YieldWait(float yieldingFor) => yieldingFor <= YieldWaitMax;
        /// round 8: W3 progress (prog = -destination distance, so a max is the window minimum of the distance): the window's best against the
        /// best before it; with no sample before the window, the second half's best against the first half's (round 7: the first sample)
        public static float OrbitProgress(bool haveBefore, float bestBefore, float bestFirstHalf, float bestSecondHalf) =>
            haveBefore ? Mathf.Max(bestFirstHalf, bestSecondHalf) - bestBefore : bestSecondHalf - bestFirstHalf;
        /// round 8 W5 heading orbit (taxi state, any wait / yield / queue / target geometry)
        public const float HeadingOrbitDeg = 720f, HeadingOrbitWindow = 90f, HeadingOrbitSpan = 60f;
        public static bool HeadingOrbit(float covered, float cumHeadingDeg, float span, float progressGain) =>
            covered >= HeadingOrbitWindow - 1f && cumHeadingDeg > HeadingOrbitDeg && span < HeadingOrbitSpan && progressGain < OrbitGain;
        public static float NoProgressWindow(bool carrier, bool urgentRecently) => carrier ? CarrierWindow : urgentRecently ? UrgentWindow : Window;
        /// W2: covered = seconds the conditions have held (since the grace / last wait), displacement over the window (m)
        public static bool NoProgress(float covered, float window, float displacement) => covered >= window && displacement < ProgressDist;
        /// W3: cumulative heading change over the last OrbitWindow s and the progress gain over it (m)
        public static bool Orbit(float covered, float cumHeadingDeg, float progressGain) => covered >= OrbitWindow - 1f && cumHeadingDeg > OrbitDeg && progressGain < OrbitGain;
        /// W4: contact seconds in the last ContactWindow samples, speeds and relative speed (m/s)
        public static bool StuckPair(int contactSeconds, float va, float vb, float vrel) => contactSeconds > ContactNeed && ((va < ContactSlow && vb < ContactSlow) || vrel < ContactTogether);
        /// taxi ladder: 1 re-path, 2 moving target, 3 hand-over (to the runway and close to its start), 4 eject
        public static int NextStep(int step, bool toRunway, float destDist)
        {
            if (step <= 0) return 1;
            if (step == 1) return 2;
            if (step == 2) return toRunway && destDist < HandOverDist ? 3 : 4;
            return 4;
        }
        /// taxi eject: the stock Disembark stops and ejects below 1 m/s; ours forces it after EjectFallback s
        public static bool ForceEject(bool takeoff, float speed, float sinceEject) => takeoff ? speed < TakeoffEjectBelow || sinceEject > EjectFallback : speed >= TaxiEjectBelow && sinceEject > EjectFallback;
    }

    /// W4 sensor: records collisions of a part body with another aircraft (one per part rigidbody)
    public class ContactProbe1915 : MonoBehaviour
    {
        public Aircraft self;
        Collider lastCol; Aircraft lastOther;

        void OnCollisionStay(Collision col)
        {
            // round 3 (review 4): probes are added on every machine (IsServer may not be set yet at the first SetComplexPhysics, from
            // SetLocalSim during the spawn); only the server records contacts
            if (self == null || col == null || !self.IsServer) return;
            var c = col.collider;
            if (!ReferenceEquals(c, lastCol)) { lastCol = c; lastOther = Plugin.OtherAircraftOf1915(c, self); }
            if (lastOther != null) Plugin.NoteContact1915(self, lastOther);
        }
    }

    public partial class Plugin
    {
        const bool AiGroundWatchDefault1915 = true;
        static BepInEx.Configuration.ConfigEntry<string> aiWatchMode1915, aiWatchScope1915;
        static bool watchBroken1915;
        static int watchLogs1915;
        static float nextWatchPrune1915;

        static bool AiWatchOn1915 => Mode1915.On(aiWatchMode1915 != null ? aiWatchMode1915.Value : "Auto", AiGroundWatchDefault1915);
        static bool WatchAll1915 => aiWatchScope1915 != null && aiWatchScope1915.Value == "All";

        struct Sample1915 { public float t, hdg, prog; public Vector3 pos; }

        class Watch1915
        {
            public Aircraft a; public PilotBaseState st; public bool takeoff, ours;
            public float t0, graceEnd, nextEval, maxSpeed, progressSince = -1f, lastUrgent = -1e9f;
            public readonly List<Sample1915> samples = new List<Sample1915>();
            public LandingGear[] gear; public bool[] gearOn; public int[] gearMiss;
            public UnitPart[] parts; public float[] hp0; public float det0;   // det0: detached ratio at entry (counted only after a landing)
            public int step, defer; public float stepT; public Vector3 stepPos;
            public bool ejecting; public float ejectT; public bool forced; public bool queueLogged;
            public float lastWait = -1e9f, queueSince = -1f; public Vector3 queuePos; public bool mutualLogged, expiredLogged; public Airbase ab;   // round 4
            public float w1Det, w1Loss; public int w1Lost;                                                                                          // round 4 (d)
            public float yieldSince = -1f; public bool yielding, yieldLogged;                                                                        // round 8
            public readonly bool[] contact = new bool[GroundWatchMath1915.ContactWindow]; public int contactIdx; public Aircraft other;
        }

        static readonly Dictionary<Aircraft, Watch1915> watches1915 = new Dictionary<Aircraft, Watch1915>();
        static readonly Dictionary<Aircraft, KeyValuePair<float, Aircraft>> contacts1915 = new Dictionary<Aircraft, KeyValuePair<float, Aircraft>>();
        static readonly HashSet<Aircraft> otherSkipLogged1915 = new HashSet<Aircraft>();
        /// round 4: who is held behind whom (time, leader), for the mutual-hold test
        static readonly Dictionary<Aircraft, KeyValuePair<float, Aircraft>> heldBehind1915 = new Dictionary<Aircraft, KeyValuePair<float, Aircraft>>();
        // round 4 (d): counters (read by the test helper and Counters1915)
        internal static readonly Dictionary<string, int[]> ejectCount1915 = new Dictionary<string, int[]>();   // trigger -> { ejects, suspected false }
        internal static int queueHolds1915, mutualHolds1915, expiredHolds1915, forcedSeq1915;
        internal static int headingOrbits1915, yieldStuck1915;   // round 8

        static void CountEject1915(string trig, bool suspect)
        {
            string k = trig.StartsWith("W4") && trig.Contains("other") ? "W4other" : trig.Length >= 2 ? trig.Substring(0, 2) : trig;
            if (!ejectCount1915.TryGetValue(k, out var c)) ejectCount1915[k] = c = new int[2];
            c[0]++; if (suspect) c[1]++;
        }

        internal static string EjectSummary1915()
        {
            if (ejectCount1915.Count == 0) return "none";
            var parts = new List<string>();
            foreach (var kv in ejectCount1915) parts.Add($"{kv.Key} {kv.Value[0]} (suspected false {kv.Value[1]})");
            parts.Sort(string.CompareOrdinal);
            return string.Join(", ", parts) + $", ejection sequence forced {forcedSeq1915}";
        }

        static Aircraft HeldBehind1915(Aircraft x, float now) => x != null && heldBehind1915.TryGetValue(x, out var r) && now - r.Key <= GroundWatchMath1915.HeldMemory ? r.Value : null;

        void PatchAiGroundWatch1915()
        {
            aiWatchMode1915 = Config.Bind("Ground", "AiGroundWatch1915", "Auto", "1.9.15: host-side watchdog for AI aircraft taxiing or starting the take-off: a part off, a wheel gone or damage -> the crew bail out at once; no progress, circling or stuck against another aircraft -> re-route, hand over to the take-off, or bail out, so the spot clears. Never touches a player-flown aircraft. Auto = build default (on), On, Off.");
            aiWatchScope1915 = Config.Bind("Ground", "AiGroundWatchScope", "Ours", "1.9.15: which AI aircraft the no-progress / circling / contact rules of AiGroundWatch1915 watch: Ours (the six Heritage Pairs aircraft) or All (every AI aircraft). The damage rule is always ours only.");
            if (!AiWatchOn1915) { Logger.LogInfo("1.9.15 AI ground watch: off (config [Ground] AiGroundWatch1915)"); return; }
            try
            {
                if (!Taxi1915.Init()) { watchBroken1915 = true; Logger.LogWarning("1.9.15 AI ground watch disabled: stock AI state fields not found"); return; }
                var tx = HarmonyLib.AccessTools.Method(typeof(AIPilotTaxiState), "FixedUpdateState");
                var tk = HarmonyLib.AccessTools.Method(typeof(AIPilotTakeoffState), "FixedUpdateState");
                H1915.Patch(tx, postfix: HM1915(nameof(WatchTaxiPostfix1915), HarmonyLib.Priority.Last));
                H1915.Patch(tk, postfix: HM1915(nameof(WatchTakeoffPostfix1915), HarmonyLib.Priority.Last));
                // the pilot reuses its AIPilotTaxiState after every landing: a new entry starts a new watch (samples, hit points, wheel legs)
                H1915.Patch(HarmonyLib.AccessTools.Method(typeof(AIPilotTaxiState), "EnterState"), postfix: HM1915(nameof(WatchEnterPostfix1915)));
                H1915.Patch(HarmonyLib.AccessTools.Method(typeof(AIPilotTakeoffState), "EnterState"), postfix: HM1915(nameof(WatchEnterPostfix1915)));
                Logger.LogInfo($"1.9.15 AI ground watch on (server, AI only; scope {(WatchAll1915 ? "All" : "Ours")})");
            }
            catch (Exception e) { watchBroken1915 = true; Logger.LogWarning("1.9.15 AI ground watch disabled: " + e.Message); }
        }

        internal static Aircraft OtherAircraftOf1915(Collider c, Aircraft self) => OtherAircraft1915(c, self);
        internal static void NoteContact1915(Aircraft self, Aircraft other) { contacts1915[self] = new KeyValuePair<float, Aircraft>(Time.time, other); }

        /// one probe per part body: from the SetComplexPhysics postfix (OverlapJoint1915.cs, our aircraft) and, round 3 (review 4), lazily from
        /// NewWatch1915 on the server (any watched aircraft; idempotent). No IsServer test here: the probe itself only acts on the server.
        static void AddContactProbes1915(Aircraft a)
        {
            if (!AiWatchOn1915 || watchBroken1915 || a == null || a.partLookup == null) return;
            var bodies = new HashSet<Rigidbody>();
            foreach (var up in a.partLookup)
            {
                if (up == null || up.rb == null || !bodies.Add(up.rb)) continue;
                var go = up.rb.gameObject;
                var pr = go.GetComponent<ContactProbe1915>();
                if (pr == null) pr = go.AddComponent<ContactProbe1915>();
                pr.self = a;
            }
        }

        static void WatchEnterPostfix1915(Pilot pilot) { try { if (pilot != null && pilot.aircraft != null) watches1915.Remove(pilot.aircraft); } catch { } }
        static void WatchTaxiPostfix1915(AIPilotTaxiState __instance, Pilot pilot) => WatchStep1915(__instance, pilot, false);
        static void WatchTakeoffPostfix1915(AIPilotTakeoffState __instance, Pilot pilot) => WatchStep1915(__instance, pilot, true);

        static void WLog1915(string s) { if (watchLogs1915++ < 300) Log.LogInfo("1.9.15 AI ground watch: " + s); }
        /// round 8: queue / mutual / expired-hold / yield notes have their own budget (the ladder and eject lines keep WLog1915's 300)
        static int watchQLogs1915;
        static void WQLog1915(string s) { if (watchQLogs1915++ < 200) Log.LogInfo("1.9.15 AI ground watch: " + s); }

        static void WatchStep1915(PilotBaseState st, Pilot pilot, bool takeoff)
        {
            if (watchBroken1915 || pilot == null || !AiWatchOn1915) return;
            Aircraft a = null;
            try
            {
                float now = Time.time;
                if (now >= nextWatchPrune1915) PruneWatches1915(now);
                a = pilot.aircraft;
                if (a == null || a.definition == null || a.rb == null || a.disabled || !a.IsServer) return;
                if (watchFailed1915.Contains(a)) return;                                // round 5: this aircraft threw before; the others keep their watch
                if (!ReferenceEquals(pilot.currentState, st)) return;                  // the stock state already switched (take-off / parked)
                bool ours = AirbrakeIdleMath.IsKey(a.definition.jsonKey);
                // round 3 (review 3): the other aircraft of a stuck pair gets an ejecting watch (EjectOther1915) even when this scope does not
                // watch it: the throttle 0 / brake 1 frame and the 10 s fallback run for it too
                if (!ours && !WatchAll1915)
                {
                    if (watches1915.TryGetValue(a, out var ow) && ow.ejecting && ReferenceEquals(ow.st, st) && AiOnly1915(a)) EjectFrame1915(ow, pilot, now);
                    return;
                }
                if (!AiOnly1915(a)) { watches1915.Remove(a); return; }
                if (!watches1915.TryGetValue(a, out var w) || !ReferenceEquals(w.st, st)) watches1915[a] = w = NewWatch1915(a, st, pilot, takeoff, ours, now);
                if (w.ejecting) { EjectFrame1915(w, pilot, now); return; }
                if (a.radarAlt >= GroundWatchMath1915.AltMax) return;
                if (takeoff) { w.maxSpeed = Mathf.Max(w.maxSpeed, a.speed); if (w.maxSpeed > GroundWatchMath1915.TakeoffSpeedMax) return; }
                if (now < w.nextEval) return;
                w.nextEval = now + 1f;
                Evaluate1915(w, pilot, now);
            }
            catch (Exception e) { WatchFailed1915(a, e); }
        }

        /// round 5 (round-4 acceptance: one NRE switched the whole watch off for the session): an exception drops the watch of THAT aircraft
        /// only (it is skipped from then on, counted, logged with the trace for the first few); the whole watch goes off only after
        /// GroundWatchMath1915.MaxWatchErrors exceptions (a systematic fault)
        static readonly HashSet<Aircraft> watchFailed1915 = new HashSet<Aircraft>();
        internal static int watchErrors1915;
        static void WatchFailed1915(Aircraft a, Exception e)
        {
            watchErrors1915++;
            try { if (a != null) { watchFailed1915.Add(a); watches1915.Remove(a); heldBehind1915.Remove(a); } } catch { }
            string who = "?";
            try { who = a != null ? $"{a.name} ({(a.definition != null ? a.definition.jsonKey : "?")})" : "(no aircraft)"; } catch { }
            if (watchErrors1915 <= 5) Log.LogWarning($"1.9.15 AI ground watch: exception {watchErrors1915} on {who}, watch dropped for that aircraft only: " + e);
            if (GroundWatchMath1915.WatchDisable(watchErrors1915)) { watchBroken1915 = true; Log.LogWarning($"1.9.15 AI ground watch disabled: {watchErrors1915} exceptions (last on {who}): " + e.Message); }
        }

        static void PruneWatches1915(float now)
        {
            nextWatchPrune1915 = now + 10f;
            List<Aircraft> dead = null;
            foreach (var kv in watches1915) if (kv.Key == null || kv.Key.disabled) (dead = dead ?? new List<Aircraft>()).Add(kv.Key);
            if (dead != null) foreach (var k in dead) watches1915.Remove(k);
            dead = null;
            foreach (var kv in contacts1915) if (kv.Key == null || now - kv.Value.Key > 30f) (dead = dead ?? new List<Aircraft>()).Add(kv.Key);
            if (dead != null) foreach (var k in dead) contacts1915.Remove(k);
            otherSkipLogged1915.RemoveWhere(x => x == null || x.disabled);
            watchFailed1915.RemoveWhere(x => x == null || x.disabled);
            dead = null;
            foreach (var kv in heldBehind1915) if (kv.Key == null || now - kv.Value.Key > 30f) (dead = dead ?? new List<Aircraft>()).Add(kv.Key);
            if (dead != null) foreach (var k in dead) heldBehind1915.Remove(k);
        }

        static LandingGear[] GearOf1915(Aircraft a)
        {
            var gear = new List<LandingGear>(a.GetComponentsInChildren<LandingGear>(true));
            if (a.partLookup != null) foreach (var p in a.partLookup) if (p != null) foreach (var lg in p.GetComponentsInChildren<LandingGear>(true)) if (!gear.Contains(lg)) gear.Add(lg);
            return gear.ToArray();
        }

        static Watch1915 NewWatch1915(Aircraft a, PilotBaseState st, Pilot pilot, bool takeoff, bool ours, float now)
        {
            var w = new Watch1915 { a = a, st = st, takeoff = takeoff, ours = ours, t0 = now, nextEval = now + 1f };
            AddContactProbes1915(a);                                                   // round 3 (review 4): lazily, on the server
            float sinceSpawn = pilot.flightInfo != null ? Time.timeSinceLevelLoad - pilot.flightInfo.spawnTime : 1e6f;   // FlightInfo.spawnTime is in timeSinceLevelLoad
            w.graceEnd = now + Mathf.Max(0f, GroundWatchMath1915.SpawnGrace - sinceSpawn);
            w.gear = GearOf1915(a);
            w.gearOn = new bool[w.gear.Length]; w.gearMiss = new int[w.gear.Length];
            for (int i = 0; i < w.gear.Length; i++) w.gearOn[i] = w.gear[i] != null && w.gear[i].isActiveAndEnabled;
            w.parts = a.partLookup != null ? a.partLookup.ToArray() : new UnitPart[0];
            w.hp0 = new float[w.parts.Length];
            for (int i = 0; i < w.parts.Length; i++) w.hp0[i] = w.parts[i] != null ? w.parts[i].hitPoints : 100f;
            // a fresh spawn (not yet flown) must have every part; after a landing only a part lost on the ground counts (a battle-damaged
            // aircraft may still taxi to resupply)
            bool flown = pilot.flightInfo != null && pilot.flightInfo.HasTakenOff;
            w.det0 = flown && a.partDamageTracker != null ? a.partDamageTracker.GetDetachedRatio() : 0f;
            return w;
        }

        static void Evaluate1915(Watch1915 w, Pilot pilot, float now)
        {
            var a = w.a;
            var taxi = w.st as AIPilotTaxiState; var tk = w.st as AIPilotTakeoffState;
            // W1 structural (ours)
            if (w.ours)
            {
                float det = a.partDamageTracker != null ? a.partDamageTracker.GetDetachedRatio() : 0f;
                int lost = 0;
                for (int i = 0; i < w.gear.Length; i++)
                {
                    if (!w.gearOn[i]) continue;
                    bool gone = w.gear[i] == null || !w.gear[i].isActiveAndEnabled;
                    w.gearMiss[i] = gone ? w.gearMiss[i] + 1 : 0;                     // two evaluations in a row (the Mk I gear guard re-enables a leg next frame)
                    if (w.gearMiss[i] >= 2) lost++;
                }
                float loss = 0f; string worst = "";
                bool hpRule = GroundWatchMath1915.HpRuleActive(now, w.graceEnd);
                for (int i = 0; i < w.parts.Length; i++)
                {
                    var p = w.parts[i];
                    if (!hpRule) { if (p != null) w.hp0[i] = p.hitPoints; continue; }   // round 2: inside the spawn grace -> new baseline
                    float l = p == null ? 100f : w.hp0[i] - p.hitPoints;
                    if (l > loss) { loss = l; worst = p != null ? p.name : "(destroyed part)"; }
                }
                w.w1Det = det - w.det0; w.w1Lost = lost; w.w1Loss = loss;
                if (GroundWatchMath1915.Structural(det - w.det0, lost, loss)) { StartEject1915(w, pilot, now, "W1 structural", $"detached {det * 100f:F0} %, wheel legs lost {lost}, worst damage {loss:F1} hp on {worst}"); return; }
            }
            // W4 contact (sample every evaluation)
            Aircraft other = null;
            if (contacts1915.TryGetValue(a, out var rec) && rec.Value != null && now - rec.Key < 1.1f) other = rec.Value;
            if (other == null && gContact1915 != null)
                foreach (var lg in w.gear) { if (lg == null || !lg.isActiveAndEnabled) continue; var o = OtherAircraft1915(gContact1915(lg), a); if (o != null) { other = o; break; } }
            w.contact[w.contactIdx] = other != null; w.contactIdx = (w.contactIdx + 1) % w.contact.Length;
            if (other != null) w.other = other;
            int cs = 0; foreach (var b in w.contact) if (b) cs++;
            if (w.other != null && cs > GroundWatchMath1915.ContactNeed)
            {
                float vb = w.other.rb != null ? w.other.rb.velocity.magnitude : 0f;
                float vrel = w.other.rb != null ? (a.rb.velocity - w.other.rb.velocity).magnitude : a.speed;
                if (GroundWatchMath1915.StuckPair(cs, a.speed, vb, vrel))
                {
                    var o = w.other;
                    StartEject1915(w, pilot, now, "W4 contact", $"against {o.name} ({(o.definition != null ? o.definition.jsonKey : "?")}) {cs} of the last {w.contact.Length} s, {a.speed:F1} / {vb:F1} m/s, relative {vrel:F1} m/s");
                    EjectOther1915(o, a, now);
                    return;
                }
            }
            // samples (airbase-local on a carrier deck)
            Airbase ab = taxi != null ? Taxi1915.airbase(taxi) : tk != null ? Taxi1915.tkAirbase(tk) : null;   // round 5: never a getter on null
            w.ab = ab;
            bool carrier = ab != null && ab.AttachedAirbase;
            var tr = carrier ? ab.transform : null;
            var pos = tr != null ? tr.InverseTransformPoint(a.transform.position) : a.transform.position;
            float hdg = (tr != null ? Quaternion.Inverse(tr.rotation) * a.transform.rotation : a.transform.rotation).eulerAngles.y;
            float prog = 0f, destDist = float.MaxValue; bool toRunway = false;
            bool heldNow = false;
            if (taxi != null)
            {
                var dest = Taxi1915.destinationPoint(taxi) ?? Taxi1915.exitTaxiPoint(taxi);
                if (dest != null) { destDist = Vector3.Distance(dest.position, a.transform.position); prog = -destDist; }
                toRunway = Taxi1915.toRunway(taxi);
                // round 8: the stock yield is a wait only for its first YieldWaitMax s (the Mk I yield orbit restarted W2 / W3 for 435 s)
                bool yieldNow = Taxi1915.yielding(taxi);
                if (!yieldNow) w.yieldSince = -1f;
                else if (w.yieldSince < 0f) w.yieldSince = now;
                w.yielding = yieldNow;
                bool yieldWait = yieldNow && GroundWatchMath1915.YieldWait(now - w.yieldSince);
                if (yieldNow && !yieldWait && !w.yieldLogged) { w.yieldLogged = true; WQLog1915($"{a.name} ({a.definition.jsonKey}) yielding for {now - w.yieldSince:F0} s: no longer a wait, no-progress and orbit rules run"); }
                if (Taxi1915.waitingForTakeoffClearance(taxi) || Taxi1915.waitingAtRunwayCrossing(taxi)) { w.progressSince = now; w.step = 0; w.lastWait = now; }
                else if (yieldWait) { w.progressSince = now; w.step = 0; }
                float urg = Taxi1915.brakeUrgency(taxi);
                if (urg > 0.1f)
                {
                    w.lastUrgent = now;
                    var lead = QueueLeader1915(a, ab, urg, w, now);                     // round 3 (review 2): held in a queue, not stuck; round 4: no mutual / circular hold
                    if (lead != null)
                    {
                        heldNow = true;
                        heldBehind1915[a] = new KeyValuePair<float, Aircraft>(now, lead);
                        if (w.queueSince < 0f || Vector3.Distance(pos, w.queuePos) >= GroundWatchMath1915.ProgressDist) { w.queueSince = now; w.queuePos = pos; }   // a new hold, or the queue moved on
                        if (GroundWatchMath1915.QueueHoldExpired(now - w.queueSince, Vector3.Distance(pos, w.queuePos)))
                        {
                            if (!w.expiredLogged) { w.expiredLogged = true; expiredHolds1915++; WQLog1915($"{a.name} ({a.definition.jsonKey}) held behind {lead.name} for {now - w.queueSince:F0} s with < {GroundWatchMath1915.ProgressDist:F0} m moved: no longer treated as a queue, no-progress and orbit rules run"); }
                        }
                        else
                        {
                            w.progressSince = now; w.step = 0; w.defer = 0;
                            if (!w.queueLogged) { w.queueLogged = true; queueHolds1915++; WQLog1915($"{a.name} ({a.definition.jsonKey}) held by the obstacle brake behind {lead.name} (queued / waiting / moving): in a queue, no-progress and orbit rules wait"); }
                        }
                    }
                }
            }
            else if (tk != null)
            {
                // round 5: the take-off branch is the else of "if (taxi != null)" again (round 4 put the heldNow line between them: the
                // take-off code ran for held TAXI aircraft with tk == null -> NRE in tkRunwayVector -> the whole watch off; and never for
                // take-off aircraft -> progressSince not refreshed at <= 1 m/s -> a W2 false-eject path on the runway)
                var rv = Taxi1915.tkRunwayVector(tk);
                if (rv.sqrMagnitude > 1e-4f) prog = Vector3.Dot(a.transform.position, rv.normalized);
                if (Taxi1915.tkStarted(tk) || a.speed <= GroundWatchMath1915.TakeoffCreep) w.progressSince = now;   // W2 / W3 only before the run and above 1 m/s
            }
            // round 5: after the whole taxi / take-off if-else (never between the two)
            if (!heldNow) { heldBehind1915.Remove(a); w.queueSince = -1f; }
            w.samples.Add(new Sample1915 { t = now, pos = pos, hdg = hdg, prog = prog });
            while (w.samples.Count > 0 && w.samples[0].t < now - GroundWatchMath1915.UrgentWindow - 10f) w.samples.RemoveAt(0);
            float from = Mathf.Max(w.graceEnd, w.progressSince);
            // W2 no progress
            float window = w.takeoff ? GroundWatchMath1915.Window : GroundWatchMath1915.NoProgressWindow(carrier, now - w.lastUrgent < GroundWatchMath1915.UrgentMemory);
            int k = -1;
            for (int i = w.samples.Count - 1; i >= 0; i--) if (w.samples[i].t <= now - window + 0.5f) { k = i; break; }
            if (k >= 0)
            {
                float disp = Vector3.Distance(pos, w.samples[k].pos);
                if (GroundWatchMath1915.NoProgress(now - from, window, disp)) { Stuck1915(w, pilot, now, "W2 no progress", $"{disp:F1} m in {window:F0} s", toRunway, destDist, pos); return; }
            }
            // W3 orbit (round 8: progress = the window minimum of the distance against the minimum before it, else second half vs first half)
            float cum = 0f, before = float.MinValue, bestA = float.MinValue, bestB = float.MinValue; int first = -1;
            float half = now - GroundWatchMath1915.OrbitWindow * 0.5f;
            for (int i = 0; i < w.samples.Count; i++)
            {
                var s = w.samples[i];
                if (s.t < from) continue;
                if (s.t < now - GroundWatchMath1915.OrbitWindow) { before = Mathf.Max(before, s.prog); continue; }
                if (first < 0) first = i; else cum += Mathf.Abs(Mathf.DeltaAngle(w.samples[i - 1].hdg, s.hdg));
                if (s.t < half) bestA = Mathf.Max(bestA, s.prog); else bestB = Mathf.Max(bestB, s.prog);
            }
            if (first >= 0)
            {
                if (bestA == float.MinValue) bestA = bestB;
                if (bestB == float.MinValue) bestB = bestA;
                float gain = GroundWatchMath1915.OrbitProgress(before != float.MinValue, before, bestA, bestB);
                float covered = now - Mathf.Max(from, w.samples[first].t);
                if (GroundWatchMath1915.Orbit(covered, cum, gain)) { Stuck1915(w, pilot, now, "W3 orbit", $"{cum:F0} deg in {GroundWatchMath1915.OrbitWindow:F0} s, progress {gain:F1} m, {a.speed:F1} m/s", toRunway, destDist, pos); return; }
            }
            // round 8 W5 heading orbit (taxi state): any wait / yield / queue hold / hand-over hold and any target geometry - only the spawn grace
            if (taxi != null) HeadingOrbitCheck1915(w, pilot, now, toRunway, destDist, pos);
        }

        /// round 8 W5: cumulative |heading change| > 720 deg in the last 90 s, every sample within 60 m of the window centroid, progress (second
        /// half's minimum distance against the first half's) < 10 m -> the taxi ladder (a yielding aircraft: the stock disembark at once)
        static void HeadingOrbitCheck1915(Watch1915 w, Pilot pilot, float now, bool toRunway, float destDist, Vector3 pos)
        {
            float t0 = Mathf.Max(w.graceEnd, now - GroundWatchMath1915.HeadingOrbitWindow);
            float half = now - GroundWatchMath1915.HeadingOrbitWindow * 0.5f;
            float cum = 0f, bestA = float.MinValue, bestB = float.MinValue; int first = -1, n = 0; Vector3 c = Vector3.zero;
            for (int i = 0; i < w.samples.Count; i++)
            {
                var s = w.samples[i];
                if (s.t < t0) continue;
                if (first < 0) first = i; else cum += Mathf.Abs(Mathf.DeltaAngle(w.samples[i - 1].hdg, s.hdg));
                if (s.t < half) bestA = Mathf.Max(bestA, s.prog); else bestB = Mathf.Max(bestB, s.prog);
                c += s.pos; n++;
            }
            if (first < 0 || n < 2) return;
            c /= n;
            float span = 0f;
            for (int i = first; i < w.samples.Count; i++) span = Mathf.Max(span, Vector3.Distance(w.samples[i].pos, c));
            if (bestA == float.MinValue) bestA = bestB;
            if (bestB == float.MinValue) bestB = bestA;
            float gain = bestB - bestA, covered = now - w.samples[first].t;
            if (!GroundWatchMath1915.HeadingOrbit(covered, cum, span, gain)) return;
            headingOrbits1915++;
            Stuck1915(w, pilot, now, "W5 heading orbit", $"{cum:F0} deg in {GroundWatchMath1915.HeadingOrbitWindow:F0} s within {span:F0} m, progress {gain:F1} m, {w.a.speed:F1} m/s{(w.yielding ? ", yielding" : "")}", toRunway, destDist, pos);
        }

        /// round 3 (review 2): the aircraft of the same airbase ahead within the stock obstacle range (gap < 60 m) that is queued, waiting or
        /// moving (GroundWatchMath1915.QueueHeld); null when none (then W2 / W3 run as before)
        static Aircraft QueueLeader1915(Aircraft a, Airbase ab, float urgency, Watch1915 w, float now)
        {
            if (ab == null || ab.ControlledAircraft == null) return null;
            var fw = a.transform.forward;
            foreach (var o in ab.ControlledAircraft)
            {
                if (o == null || ReferenceEquals(o, a) || o.disabled) continue;
                var v = o.transform.position - a.transform.position;
                float dist = v.magnitude;
                if (dist < 1e-3f) continue;
                float dot = Vector3.Dot(v / dist, fw);
                float gap = dist - o.maxRadius - a.maxRadius;
                if (dot < 0f || gap >= GroundWatchMath1915.QueueGap) continue;
                var cs = o.pilots != null && o.pilots.Length > 0 && o.pilots[0] != null ? o.pilots[0].currentState : null;
                bool waiting = false;
                if (cs is AIPilotTaxiState ts)
                    waiting = Taxi1915.takeoffQueued(ts) || Taxi1915.waitingForTakeoffClearance(ts) || Taxi1915.waitingAtRunwayCrossing(ts) || Taxi1915.yielding(ts);
                if (!GroundWatchMath1915.QueueHeld(urgency, dot, gap, GroundWatchMath1915.Advancing(o.speed, cs is AIPilotTakeoffState, waiting))) continue;
                // round 4: o is (through a chain) held behind this aircraft: a mutual / circular hold, not a queue - skip it, so one of them runs
                // W2 / W3 (the other one, evaluated while this one is not held, keeps its hold: the tie breaks)
                if (GroundWatchMath1915.HoldCycle<Aircraft>(x => HeldBehind1915(x, now), o, a, GroundWatchMath1915.CycleHops))
                {
                    if (w != null && !w.mutualLogged) { w.mutualLogged = true; mutualHolds1915++; WQLog1915($"{a.name} ({a.definition.jsonKey}) and {o.name} hold for each other (mutual / circular hold): not a queue, no-progress and orbit rules run for {a.name}"); }
                    continue;
                }
                return o;
            }
            return null;
        }

        /// round 4 (d): any aircraft of the airbase < QueueGap ahead (any state) - for the suspected-false-eject flag
        static Aircraft AircraftAhead1915(Aircraft a, Airbase ab)
        {
            if (a == null || ab == null || ab.ControlledAircraft == null) return null;
            var fw = a.transform.forward;
            foreach (var o in ab.ControlledAircraft)
            {
                if (o == null || ReferenceEquals(o, a) || o.disabled) continue;
                var v = o.transform.position - a.transform.position;
                float dist = v.magnitude;
                if (dist < 1e-3f) continue;
                if (Vector3.Dot(v / dist, fw) >= 0f && dist - o.maxRadius - a.maxRadius < GroundWatchMath1915.QueueGap) return o;
            }
            return null;
        }

        /// W2 / W3: the taxi ladder (one step per 45 s), or eject in the take-off state
        static void Stuck1915(Watch1915 w, Pilot pilot, float now, string trig, string nums, bool toRunway, float destDist, Vector3 pos)
        {
            if (w.takeoff) { StartEject1915(w, pilot, now, trig, nums); return; }
            // round 8: a yielding aircraft: the stock yield branch steers at its yield point and returns before any re-path / moving target can
            // act, so the ladder cannot help; the yield's own stock end (disembark) at once
            if (w.yielding) { yieldStuck1915++; StartEject1915(w, pilot, now, trig, nums + "; yielding: the stock yield never reached its point -> the yield's own end, the stock disembark"); return; }
            if (w.step > 0 && now - w.stepT < GroundWatchMath1915.StepTime) return;
            if (w.step > 0 && now - w.stepT > GroundWatchMath1915.LadderReset) { w.step = 0; w.defer = 0; }
            w.step = GroundWatchMath1915.NextStep(w.step, toRunway, destDist); w.stepT = now; w.stepPos = pos;
            var st = (AIPilotTaxiState)w.st; var a = w.a;
            var pf = Taxi1915.pathfinder(st);
            var dest = Taxi1915.destinationPoint(st); var exit = Taxi1915.exitTaxiPoint(st);
            string dd = destDist < float.MaxValue ? $"{destDist:F0} m" : "none";
            switch (w.step)
            {
                case 1:
                    if (pf != null && (dest != null || exit != null))
                    {
                        pf.ClearDestination();
                        var net = Taxi1915.taxiNetwork(st);
                        if (dest != null && net != null && net.Exists()) pf.Pathfind(net, dest.GlobalPosition(), null);
                        else SetRecovery1915(st, pf, dest ?? exit);
                        WLog1915($"{a.name} ({a.definition.jsonKey}) {trig} ({nums}; destination {dd}) -> re-path");
                        return;
                    }
                    w.step = 2; goto case 2;
                case 2:
                    if (pf != null && (dest != null || exit != null)) { SetRecovery1915(st, pf, dest ?? exit); WLog1915($"{a.name} ({a.definition.jsonKey}) {trig} ({nums}; destination {dd}) -> head straight for the destination"); return; }
                    w.step = 4; goto default;
                case 3:
                    // round 2: the hand-over passes the stock clearance check and the on-runway gate (HandOverClear1915); held by the queue /
                    // an obstacle -> wait one more step (at most MaxDefer times); not on the runway -> eject (no full-throttle run beside it)
                    if (HandOver1915(st, pilot, a, destDist, out string why)) { WLog1915($"{a.name} ({a.definition.jsonKey}) {trig} ({nums}; destination {dd}, runway clear, on the runway) -> hand over to the take-off"); return; }
                    if (GroundWatchMath1915.DeferHandOver(DeadEndMath1915.ClearanceBlock(why), w.defer))
                    {
                        w.defer++; w.step = 2;
                        WLog1915($"{a.name} ({a.definition.jsonKey}) {trig} ({nums}; destination {dd}) -> hand-over held ({why}), wait {w.defer} of {GroundWatchMath1915.MaxDefer}");
                        return;
                    }
                    nums += $"; hand-over refused: {why}";
                    w.step = 4; goto default;
                default:
                    StartEject1915(w, pilot, now, trig, nums + $"; destination {dd}; re-path / direct steering did not help");
                    return;
            }
        }

        static void StartEject1915(Watch1915 w, Pilot pilot, float now, string trig, string nums)
        {
            var a = w.a;
            w.ejecting = true; w.ejectT = now;
            // round 4 (d): suspected false ejects are counted and named (the eject still happens)
            string sus = "";
            if (trig.StartsWith("W1"))
            { if (GroundWatchMath1915.SuspectW1(w.w1Det, w.w1Lost, w.w1Loss)) sus = $"light damage only ({w.w1Loss:F1} hp, no part off, no wheel lost)"; }
            else if (trig.StartsWith("W2") || trig.StartsWith("W3"))
            {
                bool urg = now - w.lastUrgent < GroundWatchMath1915.UrgentMemory, wait = now - w.lastWait < GroundWatchMath1915.UrgentMemory;
                var ahead = AircraftAhead1915(a, w.ab);
                if (GroundWatchMath1915.SuspectStuck(urg, wait, ahead != null)) sus = (urg ? "obstacle brake in the last 60 s; " : "") + (wait ? "waited in the last 60 s; " : "") + (ahead != null ? $"{ahead.name} < {GroundWatchMath1915.QueueGap:F0} m ahead" : "");
            }
            CountEject1915(trig, sus.Length > 0);
            WLog1915($"{a.name} ({a.definition.jsonKey}) {trig} ({nums}) -> eject{(sus.Length > 0 ? " [suspected false eject: " + sus.TrimEnd(' ', ';') + "]" : "")}");
            if (w.st is AIPilotTaxiState st)
            {
                if (Taxi1915.takeoffQueued(st)) { Taxi1915.takeoffRunway(st)?.DequeueTakeoff(a); Taxi1915.takeoffQueuedF.SetValue(st, false); }
                Taxi1915.disembarkingF.SetValue(st, true);
            }
            else if (w.st is AIPilotTakeoffState tk)
            {
                var u = Taxi1915.tkUsage(tk);
                if (u.HasValue && u.Value.Runway != null) u.Value.Runway.DequeueTakeoff(a);
            }
            EjectFrame1915(w, pilot, now);
        }

        static void EjectFrame1915(Watch1915 w, Pilot pilot, float now)
        {
            var a = w.a; var ci = a.GetInputs();
            if (ci != null) { ci.throttle = 0f; ci.brake = 1f; }
            if (w.forced || !GroundWatchMath1915.ForceEject(w.takeoff, a.speed, now - w.ejectT)) return;
            w.forced = true; forcedSeq1915++;
            WLog1915($"{a.name} ({a.definition.jsonKey}) still {a.speed:F1} m/s {now - w.ejectT:F0} s after the eject order -> ejection sequence started directly");
            a.StartEjectionSequence();
            pilot.SwitchState(pilot.parkedState);
        }

        /// W4: the other aircraft of a stuck pair, when it is AI-flown and on the ground (any aircraft: it is stuck to ours)
        static void EjectOther1915(Aircraft o, Aircraft by, float now)
        {
            if (o == null || o.disabled || !o.IsServer || !AiOnly1915(o) || o.radarAlt >= GroundWatchMath1915.AltMax) return;
            if (watches1915.TryGetValue(o, out var ow) && ow.ejecting) return;
            var p = o.pilots != null && o.pilots.Length > 0 ? o.pilots[0] : null;
            var cs = p != null ? p.currentState : null;
            // round 2: never a parked aircraft or one outside the taxi / take-off states (design: "parked is never touched")
            if (!GroundWatchMath1915.OtherEjectable(cs is AIPilotTaxiState, cs is AIPilotTakeoffState, o.speed))
            {
                if (otherSkipLogged1915.Count < 256 && otherSkipLogged1915.Add(o))
                    WLog1915($"{o.name} ({(o.definition != null ? o.definition.jsonKey : "?")}) W4 contact with {by.name}: state {(cs != null ? cs.GetType().Name : "none")} -> not ejected (only taxi / take-off)");
                return;
            }
            // round 3 (review 3): always through a watch with ejecting = true (a new one when this aircraft is not watched, e.g. a stock
            // aircraft with scope Ours): the stock Disembark only ejects below 1 m/s, so a carried / jittering pair needs the per-frame
            // throttle 0 / brake 1 and the 10 s StartEjectionSequence fallback of EjectFrame1915 (WatchStep1915 runs it for any scope)
            if (p == null || !Taxi1915.Init()) { o.StartEjectionSequence(); return; }
            if (ow == null || !ReferenceEquals(ow.st, cs))
                watches1915[o] = ow = NewWatch1915(o, cs, p, cs is AIPilotTakeoffState, o.definition != null && AirbrakeIdleMath.IsKey(o.definition.jsonKey), now);
            StartEject1915(ow, p, now, "W4 contact (other)", $"stuck to {by.name}, state {cs.GetType().Name}");
        }
    }
}
