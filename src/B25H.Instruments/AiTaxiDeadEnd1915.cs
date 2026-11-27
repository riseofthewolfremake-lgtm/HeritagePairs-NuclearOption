// B25H.Instruments 1.9.15 AiTaxiDeadEnd1915 (bug 2 of 2026-11-26: "Aircraft can get stuck turning in a circle during taxi").
//
// A stock dead end (reproduced in game on stock aircraft, MODLOG "Bug repro 11-26": a CI-22 at Dustbowl "taxiing to resupply" circled 19+ times
// in 1,100 s; a VT-7 at Maris missed its runway start by 37 m and drove 1,188 m away holding the take-off queue): PathfindingAgent.GetSteerpoint
// drops the last waypoint when it is within 5 m, or behind the aircraft within 60 m, and from then on returns None for ever - nothing
// re-plans. AIPilotTaxiState.FixedUpdateState then returns before AutoAim (the yaw input freezes at its last value) and before the destination /
// hand-over code (the < 12 m check is never evaluated again); brake 1 resets the yaw stuck timer and the speed timer needs < 1 m/s.
// Our taildraggers' weaker brakes and turn rate make the miss more likely; the dead end itself is stock.
//
// Fix (server, AI only): Harmony postfix on AIPilotTaxiState.FixedUpdateState, acting only on frames where the stock code has no steerpoint:
//   detection: pathfinder.waypoints and .nodes empty, no moving target, a destination (or the runway-exit point) and an airbase;
//   recovery: pathfinder.SetMovingTarget(destination): from the next frame GetSteerpoint returns the direction to it, the stock code steers
//     again (no frozen yaw, its 4 m/s speed floor, its toRunway / resupply branches run again); speed while recovering: above 3 m/s throttle
//     0.01 + brake 1, below 2.5 m/s throttle 0.3 + brake 0 (a tighter turn, and it beats our weak brakes, which settle near 5 m/s against the
//     stock 0.17 throttle) - never while the stock obstacle check brakes (brakeUrgency > 0.1), waits or yields;
//   hand-over every frame instead of the stock 1 Hz: our aircraft bound for the runway at < 20 m from its start once queued; any aircraft in
//     recovery at < 25 m (both never while waiting for clearance / at a runway crossing); mirrors AIPilotTaxiState.cs 144-151;
//     round 2 (review of round 1): only when the stock clearance check passes (Runway.IsAvailableForTakeoff, brakeUrgency < 0.1) AND the
//     aircraft is on the runway polygon (Runway.AircraftOnRunway) or inside the stock 12 m - the stock take-off state goes to full throttle
//     off the polygon and never steers back (HandOverClear1915 in Bugs1915.cs); a held hand-over keeps the steering, one log line per reason;
//   a resupply / parking destination in recovery: the stock branch slows inside maxRadius x 5 and disembarks inside maxRadius x 2 (parks).
//   On a new entry into the taxi state a moving target we set is cleared (the agent is reused).
//   Round 5 (round-4 acceptance: FD32 / NIMROD1 orbited 10,759 / 7,021 deg after "heading straight for it" to a resupply spot 34-37 m away):
//   the bearing to the target is followed while recovering; > 360 deg of bearing with < 5 m distance gained = an orbit: first -> crawl
//   (<= 1.5 m/s, also while the obstacle brake acts: braking only) + re-path on the taxi network; second -> give up (stock Disembark).
//   Round 8 (round-7 acceptance: Mk I #-712656 at Maris circled 435 game s after landing, 6.5 m/s, yaw 0.40, brake 0.5, "taxiing to
//   resupply", csv yielding = True the whole time, destination 20-60 m away; no rule fired): the STOCK YIELD ORBIT. After a landing the
//   stock obstacle check (CheckObstacles) sets yielding and a yield point 50 m off; the yield branch of FixedUpdateState then AutoAims at
//   that point at 6-9 m/s (brake 0.5) and disembarks only inside maxRadius + 20 m of it (25.1 m for the Mk I) - and returns before any other
//   steering (our moving target, the destination, the hand-over). The Mk I's turn circle at the yield speed (~24-26 m radius) is just wider
//   than that ring, so it circles its yield point for ever: the bearing orbit of round 5 looked at the destination (~40 m off the circle's
//   centre: never 360 deg), the watch counted the yield as a wait (W2 / W3 restarted every second), and the stock stuck-yaw timer (60 s)
//   only calls Disembark() for one frame (ejects below 1 m/s only) and is reset by that frame's brake 1. Fix: while the stock yields, the
//   bearing to its yield point is followed (same law as round 5); > 360 deg with < 5 m gained = the yield cannot reach its ring -> the
//   yield's own stock end, disembarking = true (stops; at a friendly airbase back to the inventory). Also round 8: a hand-over held "not on
//   the runway" for 60 s (gaps < 30 s join) -> re-path on the taxi network; a second time -> give up (the stock disembark); and separate log
//   budgets (path ran out / orbits / hand-overs / held hand-overs: round 7 lost an orbit line because 86 hand-over lines used the shared 100).
//   (The "hand-over held: NIMROD1 19.9 m ... not on the runway" line the round-7 run linked to the circle was another Mk I at t = 103 s.)
// Config [Ground] AiTaxiDeadEnd1915 = Auto (= All AI aircraft: the measured circlers were stock aircraft that blocked ours and the queue) /
// Ours / Off. This is a steering fix of a stock bug, not a watchdog. Any exception switches it off for the session.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace B25H.Instruments
{
    public static class DeadEndMath1915
    {
        public const float SlowAbove = 3f, CreepBelow = 2.5f, CreepThrottle = 0.3f, MidThrottle = 0.15f, IdleThrottle = 0.01f;
        public const float HandOverOurs = 20f, HandOverRecovery = 25f;
        public const float StockHandOver = 12f, UrgencyMax = 0.1f;

        /// round 2: the gates every plugin hand-over must pass ("" = clear, else the first failed gate): the stock clearance check
        /// (IsAvailableForTakeoff and brakeUrgency < 0.1) and on the runway polygon or inside the stock 12 m hand-over distance
        public static string HandOverBlock(bool available, float brakeUrgency, bool onRunway, float destDist) =>
            !available ? "runway not available (queue / landing / other aircraft)" :
            !(brakeUrgency < UrgencyMax) ? "obstacle brake" :
            !(onRunway || destDist < StockHandOver) ? "not on the runway" : "";
        /// the hand-over is held by the queue / a landing / an obstacle (may clear by waiting), not by the position
        public static bool ClearanceBlock(string why) => why != null && (why.StartsWith("runway not available") || why == "obstacle brake");

        /// the stock dead end: no waypoint, no node, no moving target (GetSteerpoint returns None for ever)
        public static bool DeadEnd(int waypoints, int nodes, bool movingTarget) => waypoints == 0 && nodes == 0 && !movingTarget;
        /// speed law while recovering
        public static void Speed(float v, out float throttle, out float brake)
        {
            if (v > SlowAbove) { throttle = IdleThrottle; brake = 1f; }
            else if (v < CreepBelow) { throttle = CreepThrottle; brake = 0f; }
            else { throttle = MidThrottle; brake = 0f; }
        }
        /// round 5 (round-4 acceptance: FD32 / NIMROD1 orbited 10,759 / 7,021 deg at 6.5 m/s, 18.6 deg/s after "heading straight for it" toward a
        /// resupply / parking spot 34-37 m away): while recovering, the bearing to the target is followed; it turning by more than OrbitBearing
        /// deg in total while the distance improved by less than OrbitGain m since the record began is an orbit. First orbit -> crawl (speed
        /// cap CrawlAbove m/s: turn radius v / yaw rate shrinks ~4x) + re-path; second -> give up (the stock Disembark: stops, parks / leaves).
        public const float OrbitBearing = 360f, OrbitGain = 5f, OrbitSample = 0.5f;
        public const float CrawlAbove = 1.5f, CrawlBelow = 1f, CrawlThrottle = 0.2f;
        public const int OrbitGiveUp = 2;
        public static bool BearingOrbit(float cumBearingDeg, float distGain) => Mathf.Abs(cumBearingDeg) > OrbitBearing && distGain < OrbitGain;
        /// a record that made OrbitGain m of progress starts again (an approach curve is not an orbit)
        public static bool OrbitReset(float distGain) => distGain >= OrbitGain;
        /// 1 = crawl + re-path, 2 = give up (disembark)
        public static int OrbitAction(int orbits) => orbits >= OrbitGiveUp ? 2 : orbits >= 1 ? 1 : 0;
        /// round 6: the crawl / orbit block runs while recovering on the moving target OR while watching a re-planned path
        public static bool WatchActive(bool recovering, bool repathWatch) => recovering || repathWatch;
        /// crawl speed law; braking only (no throttle added) while the stock obstacle brake / a wait / a yield holds (`held`)
        public static void Crawl(float v, bool held, float throttleIn, float brakeIn, out float throttle, out float brake)
        {
            if (v > CrawlAbove) { throttle = IdleThrottle; brake = 1f; return; }
            if (held) { throttle = throttleIn; brake = brakeIn; return; }
            if (v < CrawlBelow) { throttle = CrawlThrottle; brake = 0f; }
            else { throttle = IdleThrottle * 5f; brake = 0f; }
        }
        /// hand over to the take-off state now?
        public static bool HandOver(bool toRunway, bool ours, bool queued, bool recovering, float destDist, bool waiting) =>
            toRunway && !waiting && ((ours && queued && destDist < HandOverOurs) || (recovering && destDist < HandOverRecovery));
        /// round 8: the stock yield ring (AIPilotTaxiState yield branch: Disembark inside maxRadius + 20 m of the yield point)
        public const float YieldRing = 20f;
        public static float YieldRingOf(float maxRadius) => maxRadius + YieldRing;
        /// round 8: the stock yield orbits its point: the bearing to the yield point turned > OrbitBearing deg with < OrbitGain m gained (the
        /// round-5 law, measured against the point the stock steers at - not the destination)
        public static bool YieldOrbit(float cumBearingDeg, float distGain) => BearingOrbit(cumBearingDeg, distGain);
        /// round 8: a hand-over held "not on the runway" (the position, not the queue): HeldOffMax s in total (holds less than HeldOffGap s
        /// apart join) -> 1 re-path; the HeldOffGiveUp-th time -> 2 give up (stock disembark)
        public const float HeldOffMax = 60f, HeldOffGap = 30f;
        public const int HeldOffGiveUp = 2;
        public static bool OffRunway(string why) => why == "not on the runway";
        public static bool HeldOffRestart(float sinceLast) => sinceLast > HeldOffGap;
        public static int HeldOffAction(float heldFor, int actionsSoFar) => heldFor < HeldOffMax ? 0 : actionsSoFar + 1 >= HeldOffGiveUp ? 2 : 1;
        /// round 8: separate log budgets (round 7: one shared budget of 100, 86 used by hand-over lines, the FD-32 orbit line lost)
        public const int DeadEndLogMax = 100, OrbitLogMax = 100, HandOverLogMax = 100, HandOverHeldLogMax = 100;
    }

    public partial class Plugin
    {
        static BepInEx.Configuration.ConfigEntry<string> deadEndMode1915;
        static bool deadEndBroken1915;
        static int deadEndLogs1915, handOverBlockLogs1915, orbitLogs1915, handOverLogs1915;   // round 8: four budgets (DeadEndMath1915.*LogMax)
        static bool DeadEndLog1915() => deadEndLogs1915++ < DeadEndMath1915.DeadEndLogMax;
        static bool OrbitLog1915() => orbitLogs1915++ < DeadEndMath1915.OrbitLogMax;
        static bool HandOverLog1915() => handOverLogs1915++ < DeadEndMath1915.HandOverLogMax;
        static bool HandOverHeldLog1915() => handOverBlockLogs1915++ < DeadEndMath1915.HandOverHeldLogMax;
        /// round 8: the stock yield-orbit record (bearing to the yield point) and the held-off-runway record, per taxi state
        class YieldTrack1915 { public float nextT, lastBrg = float.NaN, cum, startDist, bestDist; }
        static readonly Dictionary<AIPilotTaxiState, YieldTrack1915> yieldTrack1915 = new Dictionary<AIPilotTaxiState, YieldTrack1915>();
        class HeldOff1915 { public float first, last; public int acts; }
        static readonly Dictionary<AIPilotTaxiState, HeldOff1915> heldOff1915 = new Dictionary<AIPilotTaxiState, HeldOff1915>();
        internal static int yieldOrbits1915, heldOffRepaths1915, heldOffGiveUps1915;
        static readonly Dictionary<AIPilotTaxiState, string> heldWhy1915 = new Dictionary<AIPilotTaxiState, string>();   // one "held" line per state and reason
        internal static readonly Dictionary<AIPilotTaxiState, Transform> deadEnd1915 = new Dictionary<AIPilotTaxiState, Transform>();
        static float nextDeadEndPrune1915;
        /// round 5: bearing-orbit record per recovering taxi state
        /// round 6 (review of round 5, defect 1): `repath` = the destination the first orbit re-planned to on the taxi network. The re-path
        /// removes the moving target and the deadEnd1915 entry, so the state is no longer "recovering"; the record keyed on the state object
        /// keeps the crawl cap and the bearing-orbit check (against `repath`) running on the re-planned path - a second orbit gives up.
        /// `phase` (1 = recovering on the moving target, 2 = watching the re-planned path): a change re-initialises lastBrg / startDist / bestDist.
        class DeadEndTrack1915 { public Transform target, repath; public float nextT, lastBrg = float.NaN, cum, startDist, bestDist; public int orbits, phase; public bool crawl; }
        static readonly Dictionary<AIPilotTaxiState, DeadEndTrack1915> deadEndTrack1915 = new Dictionary<AIPilotTaxiState, DeadEndTrack1915>();
        internal static int deadEndOrbits1915, deadEndGiveUps1915, deadEndRepaths1915, deadEndRepathCrawl1915;

        static string DeadEndScope1915 { get { var m = deadEndMode1915 != null ? deadEndMode1915.Value : "Auto"; return m == "Off" ? "Off" : m == "Ours" ? "Ours" : "All"; } }

        void PatchAiTaxiDeadEnd1915()
        {
            deadEndMode1915 = Config.Bind("Ground", "AiTaxiDeadEnd1915", "Auto", "1.9.15: fixes a stock AI taxi dead end - when the taxi path runs out short of the runway start or the parking spot the game never re-plans, and the aircraft circles or drives away for ever (seen on stock CI-22 / VT-7 too). The AI then heads straight for its destination, slowly, and hands over to the take-off. Auto = All AI aircraft, Ours = only the six Heritage Pairs aircraft, Off.");
            if (DeadEndScope1915 == "Off") { Logger.LogInfo("1.9.15 taxi dead end: off (config [Ground] AiTaxiDeadEnd1915)"); return; }
            try
            {
                if (!Taxi1915.Init()) { deadEndBroken1915 = true; Logger.LogWarning("1.9.15 taxi dead end disabled: stock AI state fields not found"); return; }
                H1915.Patch(HarmonyLib.AccessTools.Method(typeof(AIPilotTaxiState), "FixedUpdateState"), postfix: HM1915(nameof(DeadEndPostfix1915), HarmonyLib.Priority.Low));
                H1915.Patch(HarmonyLib.AccessTools.Method(typeof(AIPilotTaxiState), "EnterState"), postfix: HM1915(nameof(TaxiEnterPostfix1915)));
                Logger.LogInfo($"1.9.15 taxi dead end on (server, AI only, scope {DeadEndScope1915})");
            }
            catch (Exception e) { deadEndBroken1915 = true; Logger.LogWarning("1.9.15 taxi dead end disabled: " + e.Message); }
        }

        /// steer straight for `target` and mark this state as recovering (speed law + hand-over at 25 m)
        static void SetRecovery1915(AIPilotTaxiState st, PathfindingAgent pf, Transform target)
        {
            if (st == null || pf == null || target == null) return;
            pf.SetMovingTarget(target);
            deadEnd1915[st] = target;
        }

        static void TaxiEnterPostfix1915(AIPilotTaxiState __instance)
        {
            if (deadEndBroken1915) return;
            try
            {
                heldWhy1915.Remove(__instance);
                deadEndTrack1915.Remove(__instance);
                yieldTrack1915.Remove(__instance); heldOff1915.Remove(__instance);   // round 8
                if (!deadEnd1915.TryGetValue(__instance, out var t)) return;
                deadEnd1915.Remove(__instance);
                var pf = Taxi1915.pathfinder(__instance);
                if (pf != null && t != null && ReferenceEquals(Taxi1915.movingTarget(pf), t)) pf.SetMovingTarget(null);
            }
            catch (Exception e) { deadEndBroken1915 = true; Log.LogWarning("1.9.15 taxi dead end disabled: " + e.Message); }
        }

        static void DeadEndPostfix1915(AIPilotTaxiState __instance, Pilot pilot)
        {
            if (deadEndBroken1915 || pilot == null) return;
            try
            {
                var st = __instance; var a = pilot.aircraft;
                if (a == null || a.definition == null || a.rb == null || a.disabled || !a.IsServer) return;
                if (!ReferenceEquals(pilot.currentState, st)) { deadEnd1915.Remove(st); deadEndTrack1915.Remove(st); yieldTrack1915.Remove(st); heldOff1915.Remove(st); return; }
                bool ours = AirbrakeIdleMath.IsKey(a.definition.jsonKey);
                var scope = DeadEndScope1915;
                if (scope == "Off" || (scope == "Ours" && !ours) || !AiOnly1915(a)) return;
                if (Taxi1915.disembarking(st)) return;
                if (Time.time >= nextDeadEndPrune1915) { nextDeadEndPrune1915 = Time.time + 30f; var gone = new List<AIPilotTaxiState>(); foreach (var kv in deadEnd1915) if (kv.Key == null || kv.Value == null) gone.Add(kv.Key); foreach (var g in gone) deadEnd1915.Remove(g); if (heldWhy1915.Count > 256) heldWhy1915.Clear(); gone.Clear(); foreach (var kv in deadEndTrack1915) if (kv.Key == null || (!deadEnd1915.ContainsKey(kv.Key) && !kv.Value.crawl && kv.Value.repath == null)) gone.Add(kv.Key); foreach (var g in gone) deadEndTrack1915.Remove(g); if (deadEndTrack1915.Count > 256) deadEndTrack1915.Clear(); if (yieldTrack1915.Count > 256) yieldTrack1915.Clear(); if (heldOff1915.Count > 256) heldOff1915.Clear(); }
                var ab = Taxi1915.airbase(st);
                var pf = Taxi1915.pathfinder(st);
                if (ab == null || pf == null) return;
                // round 8: the stock yield orbit (the yield branch steers at its yield point and returns before every other steering)
                if (Taxi1915.yieldPosition != null && Taxi1915.yielding(st)) { if (YieldOrbitStep1915(st, pf, a)) return; }
                else yieldTrack1915.Remove(st);
                var dest = Taxi1915.destinationPoint(st); var exit = Taxi1915.exitTaxiPoint(st);
                var mt = Taxi1915.movingTarget(pf);
                bool recovering = mt != null && deadEnd1915.TryGetValue(st, out var mine) && ReferenceEquals(mt, mine);
                if (!recovering)
                {
                    var wp = Taxi1915.waypoints(pf); var nd = Taxi1915.nodes(pf);
                    if (DeadEndMath1915.DeadEnd(wp != null ? wp.Count : 0, nd != null ? nd.Count : 0, mt != null))
                    {
                        var target = dest ?? exit;
                        if (target == null) return;
                        SetRecovery1915(st, pf, target);
                        recovering = true;
                        if (DeadEndLog1915())
                            Log.LogInfo($"1.9.15 taxi dead end: {a.name} ({a.definition.jsonKey}, {(Taxi1915.toRunway(st) ? "to the runway" : dest != null ? "to resupply / parking" : "to the runway exit")}) path ran out {Vector3.Distance(target.position, a.transform.position):F0} m from its {(dest != null ? "destination" : "exit point")} at {a.speed:F1} m/s -> heading straight for it");
                    }
                }
                bool waiting = Taxi1915.waitingForTakeoffClearance(st) || Taxi1915.waitingAtRunwayCrossing(st);
                if (dest != null && Taxi1915.toRunway(st))
                {
                    float dd = Vector3.Distance(dest.position, a.transform.position);
                    // round 2: distance rule AND the stock clearance + on-runway gates (HandOverClear1915); a blocked hand-over keeps the
                    // stock / recovery steering (the stock < 12 m hand-over still runs while the moving target gives a steerpoint)
                    if (DeadEndMath1915.HandOver(true, ours, Taxi1915.takeoffQueued(st), recovering, dd, waiting))
                    {
                        if (HandOver1915(st, pilot, a, dd, out string why))
                        {
                            heldOff1915.Remove(st);
                            if (HandOverLog1915()) Log.LogInfo($"1.9.15 taxi hand-over: {a.name} ({a.definition.jsonKey}) {dd:F1} m from the runway start{(recovering ? " (after a dead end)" : "")}, runway clear, on the runway -> take-off state");
                            return;
                        }
                        if ((!heldWhy1915.TryGetValue(st, out var lastWhy) || lastWhy != why) && HandOverHeldLog1915()) Log.LogInfo($"1.9.15 taxi hand-over held: {a.name} ({a.definition.jsonKey}) {dd:F1} m from the runway start: {why}");
                        heldWhy1915[st] = why;
                        // round 8: held off the runway too long -> re-path, then give up (a held hand-over kept the steering for ever)
                        if (DeadEndMath1915.OffRunway(why) && HeldOffStep1915(st, pf, a, dest, dd)) return;
                    }
                }
                // round 6 (defect 1): the crawl / orbit watch of a re-planned path runs BEFORE the "not recovering" return - after the first
                // orbit's re-path the state has no moving target and no deadEnd1915 entry, yet the crawl cap and the orbit check must go on
                deadEndTrack1915.TryGetValue(st, out var tr);
                bool repathWatch = !recovering && tr != null && tr.repath != null;
                if (!DeadEndMath1915.WatchActive(recovering, repathWatch)) return;
                if (repathWatch && dest != null && !ReferenceEquals(dest, tr.repath)) { deadEndTrack1915.Remove(st); return; }   // a new stock plan: the watch ends
                if (tr == null) deadEndTrack1915[st] = tr = new DeadEndTrack1915();
                int phase = recovering ? 1 : 2;
                if (tr.phase != phase) { tr.phase = phase; tr.lastBrg = float.NaN; tr.nextT = 0f; }   // re-entry: a fresh record
                var tgt = recovering ? (deadEnd1915.TryGetValue(st, out var tt) ? tt : null) : tr.repath;
                // round 5: bearing-orbit check while recovering (in any wait / brake state: the orbit is measured, not the inputs)
                if (tgt != null && Time.time >= tr.nextT)
                {
                    tr.nextT = Time.time + DeadEndMath1915.OrbitSample;
                    var dv = tgt.position - a.transform.position; dv.y = 0f;
                    float dist = dv.magnitude, brg = Mathf.Atan2(dv.x, dv.z) * Mathf.Rad2Deg;
                    if (!ReferenceEquals(tr.target, tgt) || float.IsNaN(tr.lastBrg) || DeadEndMath1915.OrbitReset(tr.startDist - Mathf.Min(tr.bestDist, dist)))
                    { tr.target = tgt; tr.cum = 0f; tr.startDist = tr.bestDist = dist; }
                    else { tr.cum += Mathf.DeltaAngle(tr.lastBrg, brg); tr.bestDist = Mathf.Min(tr.bestDist, dist); }
                    tr.lastBrg = brg;
                    if (DeadEndMath1915.BearingOrbit(tr.cum, tr.startDist - tr.bestDist))
                    {
                        tr.orbits++; deadEndOrbits1915++;
                        float c = tr.cum; tr.cum = 0f; tr.startDist = tr.bestDist = dist;
                        string where = Taxi1915.toRunway(st) ? "the runway start" : dest != null ? "the resupply / parking spot" : "the runway exit";
                        if (DeadEndMath1915.OrbitAction(tr.orbits) == 2)
                        {
                            deadEndGiveUps1915++;
                            if (OrbitLog1915()) Log.LogInfo($"1.9.15 taxi dead end: {a.name} ({a.definition.jsonKey}) orbits {where} again ({c:F0} deg of bearing, {dist:F0} m, {a.speed:F1} m/s) -> give up: the stock disembark (stops, parks / leaves)");
                            if (recovering) pf.SetMovingTarget(null); else pf.ClearDestination();
                            deadEnd1915.Remove(st); deadEndTrack1915.Remove(st);
                            if (Taxi1915.takeoffQueued(st)) { Taxi1915.takeoffRunway(st)?.DequeueTakeoff(a); Taxi1915.takeoffQueuedF.SetValue(st, false); }
                            Taxi1915.disembarkingF.SetValue(st, true);
                            var gi = a.GetInputs(); if (gi != null) { gi.throttle = 0f; gi.brake = 1f; }
                            return;
                        }
                        tr.crawl = true;
                        var net = Taxi1915.taxiNetwork(st);
                        bool repath = dest != null && net != null && net.Exists();
                        if (OrbitLog1915()) Log.LogInfo($"1.9.15 taxi dead end: {a.name} ({a.definition.jsonKey}) orbits {where} ({c:F0} deg of bearing, {dist:F0} m, {a.speed:F1} m/s) -> crawl (<= {DeadEndMath1915.CrawlAbove:F1} m/s){(repath ? " + re-path" : "")}");
                        if (repath)
                        {
                            // round 6: keep the watch on the state object (repath = dest); the next sample starts a fresh record (phase 2)
                            pf.SetMovingTarget(null); deadEnd1915.Remove(st); pf.ClearDestination(); pf.Pathfind(net, dest.GlobalPosition(), null);
                            tr.repath = dest; tr.phase = 2; tr.lastBrg = float.NaN; tr.nextT = 0f; deadEndRepaths1915++;
                            recovering = false;   // fall through: the crawl cap applies on this frame too
                        }
                    }
                }
                bool held = waiting || Taxi1915.yielding(st) || Taxi1915.brakeUrgency(st) > 0.1f;
                var ci = a.GetInputs();
                if (ci == null) return;
                if (tr.crawl)
                {
                    // round 5: after an orbit the crawl cap also holds while the stock obstacle brake / a wait acts (it only brakes harder then)
                    DeadEndMath1915.Crawl(a.speed, held, ci.throttle, ci.brake, out float ct, out float cb);
                    ci.throttle = ct; ci.brake = cb;
                    if (!recovering) deadEndRepathCrawl1915++;   // round 6: crawl frames on a re-planned path (0 on a061964: unreachable)
                    return;
                }
                if (held) return;   // an obstacle ahead: the stock brake rules
                DeadEndMath1915.Speed(a.speed, out float t, out float b);
                ci.throttle = t; ci.brake = b;
            }
            catch (Exception e) { deadEndBroken1915 = true; Log.LogWarning("1.9.15 taxi dead end disabled: " + e); }
        }

        /// round 8: one sample (every OrbitSample s) of the bearing to the stock yield point; true when the yield orbits its point and was ended
        /// the stock way (disembarking = true: the stock Disembark stops, ejects below 1 m/s, at a friendly airbase back to the inventory)
        static bool YieldOrbitStep1915(AIPilotTaxiState st, PathfindingAgent pf, Aircraft a)
        {
            if (!yieldTrack1915.TryGetValue(st, out var y)) yieldTrack1915[st] = y = new YieldTrack1915();
            if (Time.time < y.nextT) return false;
            y.nextT = Time.time + DeadEndMath1915.OrbitSample;
            Vector3 dv = Taxi1915.yieldPosition(st) - a.GlobalPosition(); dv.y = 0f;
            float dist = dv.magnitude, brg = Mathf.Atan2(dv.x, dv.z) * Mathf.Rad2Deg;
            if (float.IsNaN(y.lastBrg) || DeadEndMath1915.OrbitReset(y.startDist - Mathf.Min(y.bestDist, dist))) { y.cum = 0f; y.startDist = y.bestDist = dist; }
            else { y.cum += Mathf.DeltaAngle(y.lastBrg, brg); y.bestDist = Mathf.Min(y.bestDist, dist); }
            y.lastBrg = brg;
            if (!DeadEndMath1915.YieldOrbit(y.cum, y.startDist - y.bestDist)) return false;
            yieldOrbits1915++;
            if (OrbitLog1915()) Log.LogInfo($"1.9.15 taxi yield: {a.name} ({a.definition.jsonKey}) orbits its stock yield point ({y.cum:F0} deg of bearing, {dist:F1} m, the stock ring {DeadEndMath1915.YieldRingOf(a.maxRadius):F1} m, {a.speed:F1} m/s) -> the yield's own end: the stock disembark (stops, parks / leaves)");
            var mt = Taxi1915.movingTarget(pf);
            if (mt != null && deadEnd1915.TryGetValue(st, out var mine) && ReferenceEquals(mt, mine)) pf.SetMovingTarget(null);
            deadEnd1915.Remove(st); deadEndTrack1915.Remove(st); yieldTrack1915.Remove(st);
            if (Taxi1915.takeoffQueued(st)) { Taxi1915.takeoffRunway(st)?.DequeueTakeoff(a); Taxi1915.takeoffQueuedF.SetValue(st, false); }
            Taxi1915.disembarkingF.SetValue(st, true);
            var gi = a.GetInputs(); if (gi != null) { gi.throttle = 0f; gi.brake = 1f; }
            return true;
        }

        /// round 8: a hand-over held "not on the runway": HeldOffMax s (holds HeldOffGap s apart join) -> re-path on the taxi network (the stock
        /// path ends with the stock < 12 m hand-over); the second time -> give up (the stock disembark). True when it acted this frame.
        static bool HeldOffStep1915(AIPilotTaxiState st, PathfindingAgent pf, Aircraft a, Transform dest, float dd)
        {
            float now = Time.time;
            if (!heldOff1915.TryGetValue(st, out var h)) heldOff1915[st] = h = new HeldOff1915 { first = now, last = now };
            if (DeadEndMath1915.HeldOffRestart(now - h.last)) h.first = now;
            h.last = now;
            int act = DeadEndMath1915.HeldOffAction(now - h.first, h.acts);
            if (act == 0) return false;
            float heldFor = now - h.first;
            h.acts++; h.first = now;
            if (act == 2)
            {
                heldOffGiveUps1915++;
                if (OrbitLog1915()) Log.LogInfo($"1.9.15 taxi hand-over held off the runway again ({heldFor:F0} s, {dd:F1} m from the runway start, {a.speed:F1} m/s): {a.name} ({a.definition.jsonKey}) -> give up: the stock disembark (stops, parks / leaves)");
                var mt = Taxi1915.movingTarget(pf);
                if (mt != null && deadEnd1915.TryGetValue(st, out var mine) && ReferenceEquals(mt, mine)) pf.SetMovingTarget(null);
                deadEnd1915.Remove(st); deadEndTrack1915.Remove(st); heldOff1915.Remove(st);
                if (Taxi1915.takeoffQueued(st)) { Taxi1915.takeoffRunway(st)?.DequeueTakeoff(a); Taxi1915.takeoffQueuedF.SetValue(st, false); }
                Taxi1915.disembarkingF.SetValue(st, true);
                var gi = a.GetInputs(); if (gi != null) { gi.throttle = 0f; gi.brake = 1f; }
                return true;
            }
            heldOffRepaths1915++;
            var net = Taxi1915.taxiNetwork(st);
            bool can = dest != null && net != null && net.Exists();
            if (OrbitLog1915()) Log.LogInfo($"1.9.15 taxi hand-over held off the runway for {heldFor:F0} s: {a.name} ({a.definition.jsonKey}) {dd:F1} m from the runway start, {a.speed:F1} m/s -> {(can ? "re-path on the taxi network" : "no taxi network: steering kept")}");
            if (!can) return false;
            var mt2 = Taxi1915.movingTarget(pf);
            if (mt2 != null && deadEnd1915.TryGetValue(st, out var mine2) && ReferenceEquals(mt2, mine2)) pf.SetMovingTarget(null);
            deadEnd1915.Remove(st); pf.ClearDestination(); pf.Pathfind(net, dest.GlobalPosition(), null);
            return true;
        }
    }
}
