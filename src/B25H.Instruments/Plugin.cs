// B25H.Instruments: optional companion plugin for the B-25H Mitchell Blueprinter mod (b25h_mitchell .nobp).
// Drives the cockpit needles/cards that have no stock driver (altimeter, VSI, fuel, attitude card, heading card) on
// aircraft whose definition jsonKey is "B25H". Reads only the aircraft's own public state; touches only transforms
// named gauge_* inside that aircraft. The aircraft is fully usable without it (HUD + tac screen carry the data).
// Airspeed (HighLiftDevice) and manifold/rpm (Cockpit.Throttle) needles are driven by stock components in the prefab
// and are NOT touched here.
//
// Conventions (model contract b25h_v2_contract.json, "gauges"): each mover's local +X points at the pilot, rest pose =
// 12 o'clock, +angle about local +X = clockwise as seen by the pilot, angle = (value - v0) * deg_per_unit.
using System.Collections.Generic;
using System.Reflection;
using BepInEx;
using UnityEngine;

namespace B25H.Instruments
{
    [BepInPlugin("b25h.instruments", "Heritage Pairs Instruments", "1.9.14")]   // 1.9.10: display name was "B-25H Instruments"; the GUID (and so the config file b25h.instruments.cfg) is unchanged
    // Heritage Pairs companion plugin: cockpit dials and tac-page panels the stock components do not drive, taildragger ground handling
    // (grip, taxi turn, moving-deck hold), the Nimrod / FD-32 hook and gear rules and the laser beam guard. One partial class, one file per
    // piece; each piece acts only on our own aircraft (matched by definition.jsonKey), has a config switch and disables itself on an
    // exception. Version history: CHANGELOG.md.
    public partial class Plugin : BaseUnityPlugin
    {
        public const string JsonKey = "B25H";

        // name -> deg per unit (contract)
        const float AltLongDegPerFt = 0.36f;     // 1000 ft per turn
        const float AltShortDegPerFt = 0.036f;   // 10000 ft per turn
        const float VsiDegPerFpm = 0.028333f;    // 6000 ft/min over 170 deg, descent anticlockwise
        const float VsiMaxFpm = 6000f;
        const float FuelDegPerPct = 2.7f;        // 0..100 % over 270 deg
        const float CardMetresPerDegPitch = -0.0015f; // attitude card local +Y offset per deg of pitch up

        class Gauges
        {
            public Aircraft aircraft;
            public Transform altLong, altShort, vsi, fuel, attitude, heading;
            public Quaternion rAltLong, rAltShort, rVsi, rFuel, rAtt, rHead;
            public Vector3 pAtt;
        }

        readonly Dictionary<Aircraft, Gauges> tracked = new Dictionary<Aircraft, Gauges>();
        readonly Dictionary<Aircraft, int> misses = new Dictionary<Aircraft, int>();
        float nextScan;

        void Update()
        {
            DiscoveryStep();         // 1.8.10 (Scan1810.cs): every 2 s, one step per frame, aircraft from UnitRegistry (was: 6 scene searches in one frame)
            DriveExtrasAll();
            DriveNimrodAll();
            DriveB17GAll();
            DriveAirbrake1912();     // 1.9.12 (AirBrake1912.cs): airbrake on under 5 % throttle (ground and air), HUD airbrake text
            List<Aircraft> dead = null;
            foreach (var kv in tracked)
            {
                if (kv.Key == null) { (dead = dead ?? new List<Aircraft>()).Add(kv.Key); continue; }
                Drive(kv.Value);
            }
            if (dead != null) foreach (var a in dead) tracked.Remove(a);
        }

        void Scan()
        {
            foreach (var a in PassAircraft())
            {
                if (a == null || tracked.ContainsKey(a) || a.definition == null || a.definition.jsonKey != JsonKey) continue;
                var g = new Gauges { aircraft = a };
                // UnitParts are separate hierarchies at runtime (the cockpit gauges live under fus_cockpit), so search
                // the aircraft root plus every part in partLookup.
                var all = new HashSet<Transform>(a.GetComponentsInChildren<Transform>(true));
                if (a.partLookup != null)
                    foreach (var part in a.partLookup)
                        if (part != null) foreach (var pt in part.GetComponentsInChildren<Transform>(true)) all.Add(pt);
                foreach (var t in all)
                {
                    switch (t.name)
                    {
                        case "gauge_altimeter_needle": g.altLong = t; g.rAltLong = t.localRotation; break;
                        case "gauge_altimeter_needle_short": g.altShort = t; g.rAltShort = t.localRotation; break;
                        case "gauge_vsi_needle": g.vsi = t; g.rVsi = t.localRotation; break;
                        case "gauge_fuel_needle": g.fuel = t; g.rFuel = t.localRotation; break;
                        case "gauge_attitude_card": g.attitude = t; g.rAtt = t.localRotation; g.pAtt = t.localPosition; break;
                        case "gauge_heading_card": g.heading = t; g.rHead = t.localRotation; break;
                    }
                }
                bool any = g.altLong != null || g.vsi != null || g.fuel != null || g.attitude != null || g.heading != null;
                if (!any)
                {
                    // parts not set up yet (or a preview without cockpit): retry on the next scan, give up after 10 tries
                    misses.TryGetValue(a, out var m);
                    misses[a] = m + 1;
                    if (m + 1 < 10) continue;
                }
                tracked[a] = g;
                Logger.LogInfo($"B-25H instruments attached to {a.name}: alt {(g.altLong != null)}, vsi {(g.vsi != null)}, fuel {(g.fuel != null)}, attitude {(g.attitude != null)}, heading {(g.heading != null)}");
            }
        }

        // 1.2.0: the GA-25X uses the stock KR-67 HUD throttle gauge (afterburner regions from 0.90 = its electric boost). On a
        // GA-25X gauge only, rename the region texts "AFTERBURNER " -> "BOOST " and "AIRBRAKE" -> "IDLE" (it has no airbrake).
        // 1.9.12 (HudAirbrake1912, AirBrake1912.cs): an aircraft that carries a stock Airbrake keeps the region name "AIRBRAKE" (no IDLE: the gauge
        // reads AIRBRAKE whenever the throttle is under 5 %, ground and air), and the COIN gauges of B25H / NIMROD1 / B17G / MSB17 get the stock airbrake text the same way.
        // Reflection on the gauge's own serialized region names; nothing else is touched. Any failure disables this for the session.
        public const string BoostJsonKey = "GA25X";
        public const string BoostJsonKeyFD32 = "FD32";   // 1.5.1: the FD-32 boost (JetNozzle afterburner from throttle 0.90, as the GA-25X)
        public static bool IsBoostKey(string k) => k == BoostJsonKey || k == BoostJsonKeyFD32;
        readonly HashSet<ThrottleGauge> relabelled = new HashSet<ThrottleGauge>();
        bool boostLabelsBroken;
        // 1.8.6: const, not static readonly. C# runs the static field initialisers of a partial class file by file in compile order (B17G.cs,
        // Dials184.cs, ... Plugin.cs): Dials184.cs read BFI while it was still 0, GetField(name, 0) returned null and the B-25H flaps dial found
        // "0 flap devices" (in game 1.8.4 / 1.8.5). A const has no initialisation order.
        const BindingFlags BFI = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
        void BoostLabels()
        {
            if (boostLabelsBroken) return;
            try
            {
                relabelled.RemoveWhere(g => g == null);
                foreach (var g in ThrottleGauges())
                {
                    if (g == null || relabelled.Contains(g)) continue;
                    var ac = typeof(ThrottleGauge).GetField("aircraft", BFI)?.GetValue(g) as Aircraft;
                    if (ac == null || ac.definition == null) continue;            // not initialised yet: retry next scan
                    relabelled.Add(g);
                    if (AirbrakeIdleMath.IsCoinHudKey(ac.definition.jsonKey)) { RegisterBrakeHud1912(g, ac, null, null); continue; }   // 1.9.12
                    if (!IsBoostKey(ac.definition.jsonKey)) continue;
                    var regions = typeof(ThrottleGauge).GetField("throttleRegions", BFI)?.GetValue(g) as System.Array;
                    if (regions == null) continue;
                    int n = 0; bool brake = false;
                    foreach (var r in regions)
                    {
                        if (r == null) continue;
                        var f = r.GetType().GetField("name", BFI); var name = f?.GetValue(r) as string;
                        if (name == null) continue;
                        var t = name.Trim().ToUpperInvariant();
                        if (t == "AFTERBURNER") { f.SetValue(r, "BOOST "); n++; }
                        else if (t == "AIRBRAKE")
                        {
                            if (RegisterBrakeHud1912(g, ac, r, f)) brake = true;           // 1.9.12: the aircraft has an airbrake: the name stays
                            else { f.SetValue(r, "IDLE"); n++; }
                        }
                    }
                    typeof(ThrottleGauge).GetField("throttlePrev", BFI)?.SetValue(g, -1f);   // redraw on the next Refresh
                    Logger.LogInfo($"{(ac.definition.jsonKey == BoostJsonKey ? "GA-25X" : "FD-32")} throttle gauge: {n} region label(s) renamed ({(brake ? "BOOST; AIRBRAKE kept" : "BOOST / IDLE")})");
                }
            }
            catch (System.Exception e) { boostLabelsBroken = true; Logger.LogWarning("boost labels disabled: " + e.Message); }
        }

        static void Set(Transform t, Quaternion rest, float deg)
        {
            if (t != null) t.localRotation = rest * Quaternion.AngleAxis(deg, Vector3.right);
        }

        static void Drive(Gauges g)
        {
            var a = g.aircraft;
            if (a.disabled) return;
            var tr = a.transform;
            float altFt = tr.position.GlobalY() * 3.28084f;
            Set(g.altLong, g.rAltLong, Mathf.Repeat(altFt * AltLongDegPerFt, 360f));
            Set(g.altShort, g.rAltShort, Mathf.Repeat(altFt * AltShortDegPerFt, 360f));
            var rb = a.rb;
            if (rb != null && g.vsi != null)
            {
                float fpm = Mathf.Clamp(rb.velocity.y * 196.85f, -VsiMaxFpm, VsiMaxFpm);
                Set(g.vsi, g.rVsi, fpm * VsiDegPerFpm);
            }
            if (g.fuel != null) Set(g.fuel, g.rFuel, Mathf.Clamp01(a.GetFuelLevel()) * 100f * FuelDegPerPct);
            var e = tr.eulerAngles;
            float bank = e.z > 180f ? e.z - 360f : e.z;        // + = left wing down in Unity's roll sense
            float pitchUp = -(e.x > 180f ? e.x - 360f : e.x);  // Unity +X = nose down
            if (g.attitude != null)
            {
                g.attitude.localRotation = g.rAtt * Quaternion.AngleAxis(bank, Vector3.right);
                g.attitude.localPosition = g.pAtt + g.rAtt * (Vector3.up * Mathf.Clamp(pitchUp, -30f, 30f) * CardMetresPerDegPitch);
            }
            Set(g.heading, g.rHead, -e.y);
        }
    }
}
