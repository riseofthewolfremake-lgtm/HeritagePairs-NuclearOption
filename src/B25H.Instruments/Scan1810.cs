// B25H.Instruments 1.8.10: cheap discovery (the lag fix).
//
// Why (in game 1.8.8 / 1.8.9, Confrontation, study\ingame_189_lag): with the plugin loaded every 10 s window had a 28-37 ms frame, without
// it 11-21 ms. The 2 s discovery pass called Object.FindObjectsOfType six times in ONE frame (Aircraft x4 for Scan / ScanNimrod / ScanB17G /
// ScanExtras, ThrottleGauge, PropGauge, EngineTelemetry incl. inactive). Its cost grows with every object in the scene, and a match keeps
// adding objects (about +130 GameObjects a minute, with or without the plugin), so the hitch grew the longer a match ran.
//
// Now:
//   * aircraft come from the game's own list UnitRegistry.allAircraft (every aircraft registers there on spawn, player and AI, and leaves
//     it when disabled); one snapshot per pass, shared by all four aircraft scans. No scene search.
//   * ThrottleGauge / PropGauge (HUD apps) and EngineTelemetry (tac page) are recorded by Harmony postfixes on their own Initialize(Aircraft)
//     / Start, the moments they bind to an aircraft. No scene search.
//   * the pass is spread over successive frames (one step per frame) instead of all in one frame.
//   * the per-aircraft miss counters drop destroyed aircraft.
// Fallback: if UnitRegistry or a hook is missing in a future game version, that piece uses the old FindObjectsOfType path (logged once).
using System.Collections.Generic;
using UnityEngine;

namespace B25H.Instruments
{
    public partial class Plugin
    {
        static readonly List<ThrottleGauge> throttleSeen = new List<ThrottleGauge>();
        static readonly List<PropGauge> propSeen = new List<PropGauge>();
        static readonly List<EngineTelemetry> telemSeen = new List<EngineTelemetry>();
        static bool hudHooked, registryBroken;
        Aircraft[] passAircraft = new Aircraft[0];
        int scanStep = -1;                       // -1 = idle; 0..ScanSteps-1 = next step of the current pass
        const int ScanSteps = 8;                 // A6M2 round 4: + step 6 (ScanA6M2)

        static void ThrottleInitPostfix(ThrottleGauge __instance) { if (__instance != null) throttleSeen.Add(__instance); }
        static void PropInitPostfix(PropGauge __instance) { if (__instance != null) propSeen.Add(__instance); }
        static void TelemStartPostfix(EngineTelemetry __instance) { if (__instance != null) telemSeen.Add(__instance); }

        void HookHud1810()
        {
            try
            {
                var h = new HarmonyLib.Harmony("b25h.instruments.hudseen");
                var flags = System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic;
                var mt = HarmonyLib.AccessTools.Method(typeof(ThrottleGauge), "Initialize", new[] { typeof(Aircraft) });
                var mp = HarmonyLib.AccessTools.Method(typeof(PropGauge), "Initialize", new[] { typeof(Aircraft) });
                var me = HarmonyLib.AccessTools.Method(typeof(EngineTelemetry), "Start");
                if (mt == null || mp == null || me == null) { Logger.LogWarning("1.8.10 HUD hooks: method not found, using the scene search"); return; }
                h.Patch(mt, postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(ThrottleInitPostfix), flags)));
                h.Patch(mp, postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(PropInitPostfix), flags)));
                h.Patch(me, postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(TelemStartPostfix), flags)));
                hudHooked = true;
                Logger.LogInfo("1.8.10 discovery: aircraft from UnitRegistry.allAircraft, HUD gauges from Initialize / Start hooks (no scene search)");
            }
            catch (System.Exception e) { hudHooked = false; Logger.LogWarning("1.8.10 HUD hooks failed, using the scene search: " + e.Message); }
        }

        static T[] Seen<T>(List<T> l) where T : Object { l.RemoveAll(x => x == null); return l.ToArray(); }
        ThrottleGauge[] ThrottleGauges() => hudHooked ? Seen(throttleSeen) : FindObjectsOfType<ThrottleGauge>();
        PropGauge[] PropGauges() => hudHooked ? Seen(propSeen) : FindObjectsOfType<PropGauge>();
        EngineTelemetry[] Telemetries() => hudHooked ? Seen(telemSeen) : FindObjectsOfType<EngineTelemetry>(true);

        // one snapshot per discovery pass, shared by the four aircraft scans
        Aircraft[] TakeAircraftSnapshot()
        {
            if (!registryBroken)
            {
                try { return UnitRegistry.allAircraft.ToArray(); }
                catch (System.Exception e) { registryBroken = true; Logger.LogWarning("1.8.10 UnitRegistry.allAircraft unavailable, using the scene search: " + e.Message); }
            }
            // Fallback only: reached when UnitRegistry.allAircraft threw once (a game update renamed or removed it). The scene search is the
            // slow path this file replaced (see the header); it keeps the dials working on such a game version instead of going dark.
            return FindObjectsOfType<Aircraft>();
        }
        Aircraft[] PassAircraft() => passAircraft;

        static void PruneDead(Dictionary<Aircraft, int> d)
        {
            if (d.Count == 0) return;
            List<Aircraft> dead = null;
            foreach (var k in d.Keys) if (k == null) (dead = dead ?? new List<Aircraft>()).Add(k);
            if (dead != null) foreach (var k in dead) d.Remove(k);
        }

        // called every frame from Update: starts a pass every 2 s and runs one step of it per frame
        void DiscoveryStep()
        {
            if (scanStep < 0)
            {
                if (Time.unscaledTime < nextScan) return;
                nextScan = Time.unscaledTime + 2f;
                scanStep = 0;
            }
            switch (scanStep)
            {
                case 0: passAircraft = TakeAircraftSnapshot(); PruneDead(misses); PruneDead(b17gMisses); PruneDead(nimrodMisses); PruneDead(extraMisses); PruneDead(devRescans); Scan(); break;
                case 1: BoostLabels(); break;
                case 2: ScanNimrod(); break;
                case 3: FD32TacPanels(); break;
                case 4: ScanB17G(); break;          // 1.6.0: B-17G (B17G.cs, jsonKey B17G only)
                case 5: ScanExtras(); break;        // 1.8.4: B-25H extra dials + GA-25X standby cards (Dials184.cs); 1.8.9 grip registration
                case 6: ScanA6M2(); break;          // A6M2 round 4 dials (A6M2Cockpit.cs; partial method, dropped from the public build)
                default: break;
            }
            scanStep++;
            if (scanStep >= ScanSteps - 1) { scanStep = -1; passAircraft = new Aircraft[0]; }
        }
    }
}
