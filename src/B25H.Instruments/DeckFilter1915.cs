// B25H.Instruments 1.9.15 DeckFilter1915 (bug 3 of 2026-11-26: "they crash and become stuck together").
//
// Our side of it (MODLOG "Bug repro 11-26"): DeckRelative197 in GroundGrip189.cs took ANY loaded wheel contact with an attachedRigidbody as a
// "deck" - another aircraft included. Live log: "1.9.7 deck mode ON on <our aircraft>: surface velocity 17.7 m/s" right after it landed into a
// T/A-30 (and the user's earlier logs show deck mode on the Mk I and the B-17G on land). With deck mode on, the grip works relative to the other aircraft and DeckHold198 (throttle < 0.1, < 2 m/s relative) springs the
// aircraft to an anchor that MOVES WITH the other aircraft: it is carried at > 1 m/s and the stock eject gate (< 1 m/s) never passes.
// Fix: a wheel contact whose collider belongs to another Aircraft is static ground (vSurf 0): no deck mode, no hold (DeckHold198 releases on
// the same frame because deck goes false). One capped log line "1.9.15 deck: contact on aircraft <other> ignored". The test is cached per
// leg with the contact collider (GroundGrip's lastCol). Pure rule: DeckFilterMath1915.CountsAsDeck (mirrored in tools/stub_tests_bugs_1126.py).
// And the Mk I gear guard (Nimrod.cs BreakWheelPrefix) lets a leg break when it stands on another aircraft: that is a jam, not a landing.
// Config [Ground] DeckAircraft1915 = Auto (on) / On / Off (Off = the 1.9.14 deck rule and gear guard). Carrier decks and lifts are ships, not
// aircraft: unchanged.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace B25H.Instruments
{
    public static class DeckFilterMath1915
    {
        /// a loaded wheel contact counts as a (possibly moving) deck: it has a rigidbody and is not another aircraft (unless the filter is off)
        public static bool CountsAsDeck(bool hasBody, bool onOtherAircraft, bool filterOn) => hasBody && !(onOtherAircraft && filterOn);
        /// the Mk I gear guard: a break is a jam (allowed) when the leg stands on another aircraft
        public static bool GearJam(bool onOtherAircraft, bool filterOn) => onOtherAircraft && filterOn;
    }

    public partial class Plugin
    {
        const bool DeckAircraftDefault1915 = true;
        static BepInEx.Configuration.ConfigEntry<string> deckAircraftMode1915;
        static bool deckAircraftOn1915 = DeckAircraftDefault1915;
        static float nextDeckModeRead1915;
        static int deckAcLogs1915;
        static readonly HashSet<long> deckAcLogged1915 = new HashSet<long>();
        static Func<LandingGear, Collider> gContact1915;

        static bool DeckAircraftOn1915
        {
            get
            {
                if (Time.unscaledTime >= nextDeckModeRead1915) { nextDeckModeRead1915 = Time.unscaledTime + 2f; deckAircraftOn1915 = Mode1915.On(deckAircraftMode1915 != null ? deckAircraftMode1915.Value : "Auto", DeckAircraftDefault1915); }
                return deckAircraftOn1915;
            }
        }

        void BindDeckFilter1915()
        {
            deckAircraftMode1915 = Config.Bind("Ground", "DeckAircraft1915", "Auto", "1.9.15: a wheel standing on another aircraft is treated as ground, never as a moving carrier deck (so a crashed pair is no longer held and carried together), and the Mk I gear guard lets a leg jammed on another aircraft break. Carrier decks and lifts are unchanged. Auto = build default (on), On, Off (= 1.9.14).");
            try { gContact1915 = FGet1915<LandingGear, Collider>("contactCollider"); }
            catch (Exception e) { Logger.LogWarning("1.9.15 deck filter: contactCollider getter unavailable: " + e.Message); }
            Logger.LogInfo($"1.9.15 deck filter: {(DeckAircraftOn1915 ? "on" : "off (config [Ground] DeckAircraft1915)")}");
        }

        /// GroundGrip189: a loaded wheel of `g` stands on collider `c` of another aircraft (called on frames the filter acts)
        void DeckOnAircraft1915(Grip g, Collider c)
        {
            var o = OtherAircraft1915(c, g.a);
            long key = ((long)g.a.GetInstanceID() << 32) ^ (o != null ? (uint)o.GetInstanceID() : 0u);
            if (deckAcLogs1915 < 40 && deckAcLogged1915.Add(key))
            {
                deckAcLogs1915++;
                Logger.LogInfo($"1.9.15 deck: contact on aircraft {(o != null ? o.name : c.name)} ignored ({g.a.name}: ground, not a deck{(g.hold ? "; deck hold released" : "")})");
            }
        }

        /// Nimrod.cs gear guard: the leg stands on another aircraft
        static bool GearJam1915(LandingGear lg, Aircraft a)
        {
            try
            {
                if (gContact1915 == null || lg == null) return false;
                return DeckFilterMath1915.GearJam(OtherAircraft1915(gContact1915(lg), a) != null, DeckAircraftOn1915);
            }
            catch { return false; }
        }
    }
}
