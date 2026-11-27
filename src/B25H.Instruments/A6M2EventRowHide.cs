// A6M2 round 3 (offline worker, 2026-11-18): hide the A6M2 "Special" loadout row when the mission does not allow Event Content.
//
// Design: docs/a6m2_design.md 3.6. Game 0.34.6 read as reference only: without Event Content the stock dropdown already leaves the charge out
// of the Special row (WeaponMount.IsAllowed, WeaponChecker.MountAllowedHQ -> WeaponSelector options), so the row shows only "Empty" (harmless).
// Stock has WeaponSelector.SetHidden(bool) (WeaponSelector.cs:185-188, SetActive(!hidden)) and never calls it. Postfix on
// LoadoutSelector.ShowHardpoints (LoadoutSelector.cs:54-86): for an A6M2 with MissionManager.AllowEventContent false, SetHidden(true) on the
// selector of the set named "Special". The selector stays in weaponSelectors, so GenerateLoadoutFromDropdowns (:205-213) still reads every
// row (the hidden one returns Empty) and the indices stay aligned with hardpointSets.
// Flag: config [A6M2] EventRowHide = Auto (build default OFF until probe K1 passes) / On / Off. Any exception switches it off.
using System;
using System.Collections.Generic;
using System.Reflection;

namespace B25H.Instruments
{
    public static class EventRowHideMath
    {
        public const string Key = "A6M2";
        public const string SpecialSet = "Special";
        /// hide the row of set i when the aircraft is ours, the mission has no Event Content and the set is the Special set
        public static bool Hide(string aircraftKey, bool allowEventContent, string setName) => aircraftKey == Key && !allowEventContent && setName == SpecialSet;
    }

    public partial class Plugin
    {
        const bool EventRowHideDefault = A6M2DefaultsMath.On;   // r7: off unless built with A6M2_DEFAULTS_ON (handover build), A6M2Defaults.cs
        static BepInEx.Configuration.ConfigEntry<string> eventRowMode;
        static bool eventRowBroken;
        static FieldInfo erSelectors, erAircraft;

        static bool EventRowOn
        {
            get { var m = eventRowMode != null ? eventRowMode.Value : "Auto"; return m == "On" || (m != "Off" && EventRowHideDefault); }
        }

        partial void PatchEventRowHide()
        {
            eventRowMode = Config.Bind("A6M2", "EventRowHide", "Auto", "A6M2: hide the Special (Event Content) loadout row when the mission does not allow Event Content. " + A6M2DefaultsMath.AutoText);
            A6M2MigrateKey(eventRowMode);
            if (!EventRowOn) { Logger.LogInfo("A6M2 event row hide: off (config [A6M2] EventRowHide)"); return; }
            try
            {
                const BindingFlags f = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
                erSelectors = typeof(LoadoutSelector).GetField("weaponSelectors", f);
                erAircraft = typeof(LoadoutSelector).GetField("aircraft", f);
                var m = typeof(LoadoutSelector).GetMethod("ShowHardpoints", f);
                if (erSelectors == null || erAircraft == null || m == null) { Logger.LogWarning("A6M2 event row hide disabled: LoadoutSelector members not found"); return; }
                new HarmonyLib.Harmony("b25h.instruments.a6m2eventrow").Patch(m, postfix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(EventRowPostfix), BindingFlags.Static | BindingFlags.NonPublic)));
                Logger.LogInfo("A6M2 event row hide on");
            }
            catch (Exception e) { eventRowBroken = true; Logger.LogWarning("A6M2 event row hide disabled: " + e.Message); }
        }

        static void EventRowPostfix(LoadoutSelector __instance)
        {
            if (eventRowBroken) return;
            try
            {
                var a = erAircraft.GetValue(__instance) as Aircraft;
                if (a == null || a.definition == null || a.weaponManager == null) return;
                var sel = erSelectors.GetValue(__instance) as List<WeaponSelector>;
                if (sel == null) return;
                var hs = a.weaponManager.hardpointSets;
                bool allow = MissionManager.AllowEventContent;
                for (int i = 0; i < hs.Length && i < sel.Count; i++)
                    if (sel[i] != null && EventRowHideMath.Hide(a.definition.jsonKey, allow, hs[i].name)) sel[i].SetHidden(true);
            }
            catch (Exception e) { eventRowBroken = true; Log.LogWarning("A6M2 event row hide off: " + e.Message); }
        }
    }
}
