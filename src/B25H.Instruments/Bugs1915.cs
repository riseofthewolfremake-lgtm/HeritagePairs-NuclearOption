// B25H.Instruments 1.9.15 (offline, 2026-11-27): fixes for the user's bug list of 2026-11-26 (MODLOG "Bug repro 11-26" / "Bug fixes 1.9.15").
//   1. parts fall off at spawn / in taxi (B-17G tail, GA-25X / B-25H nacelles, Mk I engine) and crews that never bail out
//      -> OverlapJoint1915.cs (no breakable anti-overlap joints, no self-collision) + AiGroundWatch1915.cs (W1 structural watchdog)
//   2. AI circling in taxi -> AiTaxiDeadEnd1915.cs (stock dead end: the path runs out and nothing re-plans), AiLineUp1915.cs (line-up hold for
//      the taildraggers), AiGroundWatch1915.cs (W2 no progress, W3 orbit)
//   3. aircraft stuck together -> DeckFilter1915.cs (another aircraft under a wheel is never a deck; Mk I gear guard lets a jammed leg go) +
//      AiGroundWatch1915.cs (W4 sustained contact)
//   4. custom bombs that lasers cannot hurt -> BombArmor1915.cs (thin-cased light bombs + a visible fizzle; stock bombs unchanged)
// This file: the one patch entry (called from Awake), compiled accessors of the stock AI state fields, the AI-only and other-aircraft tests.
// Round 4: Runner1915 (a hidden component on the plugin's GameObject: FixedUpdate runs the frame-later joint-break confirmation of
// GrandJoint1915 and the 120 s counter summary "1.9.15 counters: ..." - ejects per trigger with the suspected false ejects, queue holds,
// mutual holds broken, joint-break decisions, SetComplexPhysics pass timing incl. physics LOD switches).
// Round 8 (round-7 acceptance: a natural Mk I circle of 435 game s no rule caught): the stock yield orbit (AiTaxiDeadEnd1915.cs) and the
// watch's yield / heading-orbit rules (AiGroundWatch1915.cs); Taxi1915.yieldPosition; the round-8 counters.
// Every piece has its own config key and switches itself off for the session on an exception. Nothing here is version-bumped (the BepInPlugin
// version stays 1.9.14 until a release); the log lines say "1.9.15".
using System;
using System.Collections;
using System.Linq.Expressions;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    /// round 4: hidden component on the plugin's GameObject; FixedUpdate runs the joint-break confirmation (GrandJoint1915) and the counters
    public class Runner1915 : MonoBehaviour
    {
        void FixedUpdate() => Plugin.RunnerStep1915();
    }

    public static class Mode1915
    {
        /// config value -> on: "On" always, "Off" never, anything else ("Auto") = the build default
        public static bool On(string value, bool buildDefault) => value == "On" || (value != "Off" && buildDefault);
    }

    public partial class Plugin
    {
        void Patch1915()
        {
            PatchOverlapJoint1915();     // bug 1: anti-overlap joints + self-collision
            PatchAiGroundWatch1915();    // bugs 1-3: host-side AI ground watchdog (W1-W4)
            PatchAiTaxiDeadEnd1915();    // bug 2: taxi dead end
            PatchAiLineUp1915();         // bug 2: take-off line-up hold for the taildraggers
            BindDeckFilter1915();        // bug 3: deck filter + gear jam
            PatchBombArmor1915();        // bug 4: bomb armour + fizzle
            EnsureRunner1915();          // round 4: frame-later joint-break confirmation + counter summary
        }

        static Runner1915 runner1915;
        static bool RunnerAlive1915 => runner1915 != null && runner1915.isActiveAndEnabled;
        void EnsureRunner1915()
        {
            try { if (runner1915 == null) { runner1915 = gameObject.GetComponent<Runner1915>(); if (runner1915 == null) runner1915 = gameObject.AddComponent<Runner1915>(); } }
            catch (Exception e) { Logger.LogWarning("1.9.15 runner not added: " + e.Message); }
        }

        static float nextCounters1915; static string lastCounters1915 = "";
        /// round 4 (d) / (e): one summary line every 120 s when a counter changed
        internal static void Counters1915(float now)
        {
            if (now < nextCounters1915) return;
            nextCounters1915 = now + 120f;
            string s = $"ejects {EjectSummary1915()}; queue holds {queueHolds1915}, mutual / expired holds ignored {mutualHolds1915} / {expiredHolds1915}; "
                + $"joint breaks confirmed: no cascade {grandSuppressed1915}, held released {grandReleased1915}, stock {grandStock1915}, waited {grandWaited1915} frames, re-held after light damage {grandReheld1915}, nose joints removed {noseRemoved1915}; "
                + $"complex-physics passes {passCount1915} ({passLod1915} LOD switches) mean {(passCount1915 > 0 ? passMsTotal1915 / passCount1915 : 0):F2} ms, max {passMsMax1915:F2} ms {passMaxWho1915}, LOD max {passMsLodMax1915:F2} ms, collider pairs checked {pairsChecked1915} (max {pairsMax1915} per pass); "
                + $"round 5: watch exceptions {watchErrors1915} (aircraft dropped), dead-end orbits {deadEndOrbits1915} (gave up {deadEndGiveUps1915}), children pre-released {grandChildPre1915}, released at disable {grandDisableReleased1915}; "
                + $"round 6: dead-end re-paths {deadEndRepaths1915} (crawl frames on the re-planned path {deadEndRepathCrawl1915}), children held again after a stock outcome {grandStockReheld1915}; "
                + $"round 7: children released for good by the stock cascade of a stock outcome {grandStockCascade1915}; "
                + $"round 8: stock yield orbits ended by the stock disembark {yieldOrbits1915}, heading orbits (W5) {headingOrbits1915}, yielding aircraft stuck -> disembark {yieldStuck1915}, hand-overs held off the runway too long: re-paths {heldOffRepaths1915} / gave up {heldOffGiveUps1915}";
            if (s == lastCounters1915) return;
            lastCounters1915 = s;
            Log.LogInfo("1.9.15 counters: " + s);
        }

        static HarmonyLib.Harmony harmony1915;
        static HarmonyLib.Harmony H1915 => harmony1915 ?? (harmony1915 = new HarmonyLib.Harmony("b25h.instruments.bugs1915"));

        static HarmonyLib.HarmonyMethod HM1915(string name, int priority = HarmonyLib.Priority.Normal) =>
            new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(name, BindingFlags.Static | BindingFlags.NonPublic)) { priority = priority };

        /// compiled getter of a (private) instance field; null when the field is missing
        static Func<TObj, TVal> FGet1915<TObj, TVal>(string field)
        {
            var fi = HarmonyLib.AccessTools.Field(typeof(TObj), field);
            if (fi == null) return null;
            var p = Expression.Parameter(typeof(TObj), "o");
            Expression e = Expression.Field(p, fi);
            if (fi.FieldType != typeof(TVal)) e = Expression.Convert(e, typeof(TVal));
            return Expression.Lambda<Func<TObj, TVal>>(e, p).Compile();
        }

        // AIPilotTaxiState / PathfindingAgent / AIPilotTakeoffState fields (decompiled 0.34.x, decomp_current_20261119)
        internal static class Taxi1915
        {
            internal static Func<AIPilotTaxiState, PathfindingAgent> pathfinder;
            internal static Func<AIPilotTaxiState, Transform> destinationPoint, exitTaxiPoint;
            internal static Func<AIPilotTaxiState, Airbase> airbase;
            internal static Func<AIPilotTaxiState, RoadPathfinding.RoadNetwork> taxiNetwork;
            internal static Func<AIPilotTaxiState, Airbase.Runway> takeoffRunway;
            internal static Func<AIPilotTaxiState, bool> toRunway, takeoffQueued, disembarking, waitingForTakeoffClearance, waitingAtRunwayCrossing, yielding;
            internal static Func<AIPilotTaxiState, float> brakeUrgency;
            internal static FieldInfo disembarkingF, takeoffQueuedF;
            internal static Func<PathfindingAgent, IList> waypoints, nodes;
            internal static Func<PathfindingAgent, Transform> movingTarget;
            internal static Func<AIPilotTakeoffState, Airbase> tkAirbase;
            internal static Func<AIPilotTakeoffState, Vector3> tkRunwayVector;
            internal static Func<AIPilotTakeoffState, bool> tkStarted;
            internal static Func<AIPilotTakeoffState, Airbase.Runway.RunwayUsage?> tkUsage;
            /// round 8: the stock yield point (optional: null when the field is missing - only the yield-orbit end is then off)
            internal static Func<AIPilotTaxiState, GlobalPosition> yieldPosition;
            static bool done, ok;

            /// true when every field was found (else the AI pieces stay off)
            internal static bool Init()
            {
                if (done) return ok;
                done = true;
                pathfinder = FGet1915<AIPilotTaxiState, PathfindingAgent>("pathfinder");
                destinationPoint = FGet1915<AIPilotTaxiState, Transform>("destinationPoint");
                exitTaxiPoint = FGet1915<AIPilotTaxiState, Transform>("exitTaxiPoint");
                airbase = FGet1915<AIPilotTaxiState, Airbase>("airbase");
                taxiNetwork = FGet1915<AIPilotTaxiState, RoadPathfinding.RoadNetwork>("taxiNetwork");
                takeoffRunway = FGet1915<AIPilotTaxiState, Airbase.Runway>("takeoffRunway");
                toRunway = FGet1915<AIPilotTaxiState, bool>("toRunway");
                takeoffQueued = FGet1915<AIPilotTaxiState, bool>("takeoffQueued");
                disembarking = FGet1915<AIPilotTaxiState, bool>("disembarking");
                waitingForTakeoffClearance = FGet1915<AIPilotTaxiState, bool>("waitingForTakeoffClearance");
                waitingAtRunwayCrossing = FGet1915<AIPilotTaxiState, bool>("waitingAtRunwayCrossing");
                yielding = FGet1915<AIPilotTaxiState, bool>("yielding");
                brakeUrgency = FGet1915<AIPilotTaxiState, float>("brakeUrgency");
                disembarkingF = HarmonyLib.AccessTools.Field(typeof(AIPilotTaxiState), "disembarking");
                takeoffQueuedF = HarmonyLib.AccessTools.Field(typeof(AIPilotTaxiState), "takeoffQueued");
                waypoints = FGet1915<PathfindingAgent, IList>("waypoints");
                nodes = FGet1915<PathfindingAgent, IList>("nodes");
                movingTarget = FGet1915<PathfindingAgent, Transform>("movingTarget");
                tkAirbase = FGet1915<AIPilotTakeoffState, Airbase>("airbase");
                tkRunwayVector = FGet1915<AIPilotTakeoffState, Vector3>("runwayVector");
                tkStarted = FGet1915<AIPilotTakeoffState, bool>("startedTakeoffRun");
                tkUsage = FGet1915<AIPilotTakeoffState, Airbase.Runway.RunwayUsage?>("runwayUsage");
                try { yieldPosition = FGet1915<AIPilotTaxiState, GlobalPosition>("yieldPosition"); } catch { yieldPosition = null; }   // round 8, not in `ok`
                ok = pathfinder != null && destinationPoint != null && exitTaxiPoint != null && airbase != null && taxiNetwork != null && takeoffRunway != null
                    && toRunway != null && takeoffQueued != null && disembarking != null && waitingForTakeoffClearance != null && waitingAtRunwayCrossing != null
                    && yielding != null && brakeUrgency != null && disembarkingF != null && takeoffQueuedF != null && waypoints != null && nodes != null
                    && movingTarget != null && tkAirbase != null && tkRunwayVector != null && tkStarted != null && tkUsage != null;
                return ok;
            }
        }

        /// round 4: the frame-later work of the 1.9.15 pieces (never throws into Unity)
        internal static void RunnerStep1915()
        {
            try { GrandConfirmStep1915(); } catch (Exception e) { Log.LogWarning("1.9.15 runner: " + e.Message); }
            try { Counters1915(Time.time); } catch { }
        }

        /// no human on board: no Player and no pilot seat flown by a player (checked on every pilot)
        static bool AiOnly1915(Aircraft a)
        {
            if (a == null || a.Player != null) return false;
            var ps = a.pilots;
            if (ps != null) foreach (var p in ps) if (p != null && p.playerControlled) return false;
            return true;
        }

        /// the other aircraft this collider belongs to (null: ground, a ship, a building, our own aircraft)
        static Aircraft OtherAircraft1915(Collider c, Aircraft self)
        {
            if (c == null) return null;
            var up = c.GetComponentInParent<UnitPart>();
            var u = up != null ? up.parentUnit : c.GetComponentInParent<Aircraft>();
            var o = u as Aircraft;
            return o != null && !ReferenceEquals(o, self) ? o : null;
        }

        /// round 2 (review of round 1): may a plugin hand-over happen now? The stock clearance check (Runway.IsAvailableForTakeoff, no
        /// obstacle brake: brakeUrgency < 0.1, as AIPilotTaxiState.WaitingForTakeoffClearance) AND the aircraft on the runway polygon
        /// (Runway.AircraftOnRunway) or inside the stock 12 m. The stock take-off state goes to full throttle off the polygon
        /// (AIPilotTakeoffState: flag2 = ... || !flag) and never steers back, so a hand-over from beside the runway would be a full-throttle run
        /// over grass / apron. `why` names the failed gate ("" when clear).
        static bool HandOverClear1915(AIPilotTaxiState st, Aircraft a, float destDist, out string why)
        {
            var rw = Taxi1915.takeoffRunway(st);
            if (rw == null) { why = "no take-off runway"; return false; }
            bool avail = rw.IsAvailableForTakeoff(a);
            float urg = Taxi1915.brakeUrgency(st);
            bool on = rw.AircraftOnRunway(a);
            why = DeadEndMath1915.HandOverBlock(avail, urg, on, destDist);
            return why.Length == 0;
        }

        /// hand a taxiing AI aircraft over to the stock take-off state (AIPilotTaxiState.cs 144-151: queue if not queued, new take-off state);
        /// round 2: only when HandOverClear1915 passes (every plugin hand-over goes through here)
        static bool HandOver1915(AIPilotTaxiState st, Pilot pilot, Aircraft a, float destDist, out string why)
        {
            var rw = Taxi1915.takeoffRunway(st);
            if (rw == null || pilot == null) { why = "no take-off runway"; return false; }
            if (!HandOverClear1915(st, a, destDist, out why)) return false;
            var pf = Taxi1915.pathfinder(st);
            if (pf != null && Taxi1915.movingTarget(pf) != null) pf.SetMovingTarget(null);   // no stale target if this taxi state is entered again
            deadEnd1915.Remove(st);
            if (!Taxi1915.takeoffQueued(st)) rw.QueueTakeoff(a);
            pilot.AITakeoffState = new AIPilotTakeoffState();
            pilot.SwitchState(pilot.AITakeoffState);
            return true;
        }
    }
}
