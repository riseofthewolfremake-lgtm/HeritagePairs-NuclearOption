// B25H.Instruments 1.9.15 BombArmor1915 (bug 4 of 2026-11-26: "Custom bombs are impossible to destroy, so even if a missile or laser
// intercepts them it does nothing").
//
// Measured (MODLOG "Bug repro 11-26"): our bombs are field-for-field clones of the stock PAB-125 (fire armour 3.5, fire tolerance 0.3, blast
// armour 150). A tank laser tick deals 2.5 fire, under the 3.5 armour (Missile.TakeDamage returns unless some damage beats its armour): laser
// hits with no effect on the Cooper 53 of 66 - and 125 of 127 on the stock PAB-125: the stock game makes dumb bombs laser-proof. Interception
// does work (an AeroSentry killed a targeted bomb), but a bomb killed before it arms shows nothing: its warhead's fizzleEffect is null
// (Missile.Warhead.Detonate, unarmed branch), which reads as "nothing happened".
// Fix (our bombs only; stock bombs unchanged): Harmony postfix on Missile.Awake (and a prefix on Missile.TakeDamage, so a bomb whose
// definition arrives late is covered before its first hit) sets the instance's armorProperties of the listed keys:
//   Cooper (NIMROD1_cooper): fireArmor 1.0, fireTolerance 0.2, blastArmor 30 (stock clone 3.5 / 0.3 / 150); pierce armour unchanged.
//   (the dev aircraft's light bomb is registered by its own ship-gated file through RegisterDevBombArmor1915)
//   A 2.5-fire laser tick then takes (2.5 - 1.0) / 0.2 = 7.5 hp (14 ticks from 100 hp); interceptor blast lands on a thin-cased light bomb.
//   fizzleEffect: when null, a stock missile prefab's fizzle (the first bomb in the Encyclopedia that has one, else any missile) so an
//   unarmed kill is visible. Round 5: no stock missile has one (round-4 game log) -> the air-burst effect of the stock warhead with the
//   smallest yield whose prefab has no Shockwave (visual only; the blast damage is DamageEffects.BlastFrag, not the prefab).
// Unchanged: warhead, blast yield, pierce on impact, interception priority, the owner check (a bomb is never hurt by its own aircraft's
// explosions: Missile.TakeDamage skips dealerID == ownerID), every stock bomb. Damage is resolved on the server; the values are the same on
// every machine. Config [Weapons] BombArmor1915 = Auto (on) / On / Off. Any exception switches it off for the session.
using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class BombArmorMath1915
    {
        public const string CooperKey = "NIMROD1_cooper";
        public const float CooperFire = 1.0f, CooperFireTol = 0.2f, CooperBlast = 30f;
        /// round 5: a stock air-burst effect may stand in for the missing fizzle from any warhead with a positive yield (the SMALLEST one is
        /// taken; a prefab with a Shockwave is never used - it deals damage)
        public static bool FizzleCandidate(float blastYield) => blastYield > 0f && !float.IsInfinity(blastYield);
        /// Missile.TakeDamage: hit points taken by one hit (0 when no damage beats its armour)
        public static float HpTaken(float pierce, float blast, float amount, float fire, float pierceArmor, float blastArmor, float fireArmor, float pierceTol, float blastTol, float fireTol)
        {
            if (!(pierce > pierceArmor) && !(blast > blastArmor) && !(fire > fireArmor)) return 0f;
            return Mathf.Max(pierce - pierceArmor, 0f) / Mathf.Max(pierceTol, 0.1f) + Mathf.Max(blast - blastArmor, 0f) * amount / Mathf.Max(blastTol, 0.1f)
                + Mathf.Max(fire - fireArmor, 0f) / Mathf.Max(fireTol, 0.1f);
        }
    }

    public partial class Plugin
    {
        const bool BombArmorDefault1915 = true;
        static BepInEx.Configuration.ConfigEntry<string> bombArmorMode1915;
        static bool bombArmorBroken1915, fizzleSearched1915;
        static GameObject stockFizzle1915;
        static FieldInfo armorF1915, warheadF1915, fizzleF1915;
        /// jsonKey -> (fireArmor, fireTolerance, blastArmor)
        static Dictionary<string, Vector3> bombArmor1915;
        static readonly HashSet<int> bombDone1915 = new HashSet<int>();
        static readonly HashSet<string> bombLogged1915 = new HashSet<string>();

        partial void RegisterDevBombArmor1915();

        static bool BombArmorOn1915 => Mode1915.On(bombArmorMode1915 != null ? bombArmorMode1915.Value : "Auto", BombArmorDefault1915);

        void PatchBombArmor1915()
        {
            bombArmorMode1915 = Config.Bind("Weapons", "BombArmor1915", "Auto", "1.9.15: the Heritage Pairs light bombs (Cooper) are thin-cased: lasers and interceptor blasts can destroy them in the air (as clones of the stock 125 kg bomb they could not be hurt by a laser), and a bomb killed before it arms shows a small fizzle. Stock bombs are unchanged. Auto = build default (on), On, Off.");
            bombArmor1915 = new Dictionary<string, Vector3> { [BombArmorMath1915.CooperKey] = new Vector3(BombArmorMath1915.CooperFire, BombArmorMath1915.CooperFireTol, BombArmorMath1915.CooperBlast) };
            RegisterDevBombArmor1915();
            if (!BombArmorOn1915) { Logger.LogInfo("1.9.15 bomb armour: off (config [Weapons] BombArmor1915)"); return; }
            try
            {
                armorF1915 = HarmonyLib.AccessTools.Field(typeof(Missile), "armorProperties");
                warheadF1915 = HarmonyLib.AccessTools.Field(typeof(Missile), "warhead");
                fizzleF1915 = warheadF1915 != null ? HarmonyLib.AccessTools.Field(warheadF1915.FieldType, "fizzleEffect") : null;
                var aw = HarmonyLib.AccessTools.Method(typeof(Missile), "Awake");
                var td = HarmonyLib.AccessTools.Method(typeof(Missile), "TakeDamage");
                if (armorF1915 == null || aw == null || td == null) { bombArmorBroken1915 = true; Logger.LogWarning("1.9.15 bomb armour disabled: Missile.armorProperties / Awake / TakeDamage not found"); return; }
                H1915.Patch(aw, postfix: HM1915(nameof(MissileAwakePostfix1915)));
                H1915.Patch(td, prefix: HM1915(nameof(MissileTakeDamagePrefix1915)));
                Logger.LogInfo($"1.9.15 bomb armour on: {string.Join(", ", bombArmor1915.Keys)}{(fizzleF1915 == null ? " (fizzle field not found: armour only)" : "")}");
            }
            catch (Exception e) { bombArmorBroken1915 = true; Logger.LogWarning("1.9.15 bomb armour disabled: " + e.Message); }
        }

        static void MissileAwakePostfix1915(Missile __instance) => ApplyBombArmor1915(__instance);
        static void MissileTakeDamagePrefix1915(Missile __instance) => ApplyBombArmor1915(__instance);

        static void ApplyBombArmor1915(Missile m)
        {
            if (bombArmorBroken1915 || m == null || !BombArmorOn1915) return;
            try
            {
                int id = m.GetInstanceID();
                if (bombDone1915.Contains(id)) return;
                var key = m.definition != null ? m.definition.jsonKey : null;
                if (key == null) return;                                               // not known yet: the TakeDamage prefix tries again
                bombDone1915.Add(id);
                if (bombDone1915.Count > 4096) bombDone1915.Clear();                   // missiles are pooled / destroyed; ids are only a cache
                if (!bombArmor1915.TryGetValue(key, out var v)) return;
                var ar = armorF1915.GetValue(m) as ArmorProperties;
                if (ar == null) return;
                float f0 = ar.fireArmor, t0 = ar.fireTolerance, b0 = ar.blastArmor;
                ar.fireArmor = v.x; ar.fireTolerance = v.y; ar.blastArmor = v.z;
                string fz = "kept";
                if (fizzleF1915 != null)
                {
                    var wh = warheadF1915.GetValue(m);
                    if (wh != null && fizzleF1915.GetValue(wh) as GameObject == null)
                    {
                        var s = StockFizzle1915();
                        if (s != null) { fizzleF1915.SetValue(wh, s); fz = "stock " + s.name; } else fz = "none found";
                    }
                }
                if (bombLogged1915.Add(key))
                    Log.LogInfo($"1.9.15 bomb armour: {key}: fire armour {f0} -> {ar.fireArmor}, fire tolerance {t0} -> {ar.fireTolerance}, blast armour {b0} -> {ar.blastArmor}; fizzle {fz}");
            }
            catch (Exception e) { bombArmorBroken1915 = true; Log.LogWarning("1.9.15 bomb armour disabled: " + e.Message); }
        }

        /// a stock fizzle effect: the first stock bomb with one, else the first stock missile with one (searched once)
        static GameObject StockFizzle1915()
        {
            if (fizzleSearched1915) return stockFizzle1915;
            fizzleSearched1915 = true;
            GameObject any = null, bomb = null; string from = "";
            var enc = Encyclopedia.i;
            if (enc != null && enc.missiles != null)
                foreach (var md in enc.missiles)
                {
                    if (md == null || md.unitPrefab == null || md.jsonKey == null || bombArmor1915.ContainsKey(md.jsonKey)) continue;
                    var sm = md.unitPrefab.GetComponent<Missile>();
                    var wh = sm != null ? warheadF1915.GetValue(sm) : null;
                    var fz = wh != null ? fizzleF1915.GetValue(wh) as GameObject : null;
                    if (fz == null) continue;
                    if (any == null) { any = fz; from = md.jsonKey; }
                    if (bomb == null && md.jsonKey.IndexOf("bomb", StringComparison.OrdinalIgnoreCase) >= 0) { bomb = fz; from = md.jsonKey; break; }
                }
            stockFizzle1915 = bomb ?? any;
            if (stockFizzle1915 == null) stockFizzle1915 = SmallAirEffect1915(out from);
            Log.LogInfo($"1.9.15 bomb armour: stock fizzle effect {(stockFizzle1915 != null ? stockFizzle1915.name + " from " + from : "not found (no stock missile has one, no small air burst either)")}");
            return stockFizzle1915;
        }

        /// round 5 (round-4 acceptance: "no stock missile has" a fizzleEffect - the unarmed kill showed nothing): the air-burst effect
        /// (Warhead.airEffect) of the stock missile with the SMALLEST blast yield whose effect prefab has no Shockwave (Shockwave.cs deals
        /// overpressure damage itself; Detonate's damage is BlastFrag, not the prefab) - a small puff, purely visual. Stock prefabs only.
        static GameObject SmallAirEffect1915(out string from)
        {
            from = "";
            var airF = warheadF1915 != null ? HarmonyLib.AccessTools.Field(warheadF1915.FieldType, "airEffect") : null;
            var yieldF = HarmonyLib.AccessTools.Field(typeof(Missile), "blastYield");
            var enc = Encyclopedia.i;
            if (airF == null || yieldF == null || enc == null || enc.missiles == null) return null;
            GameObject best = null; float bestY = float.MaxValue;
            foreach (var md in enc.missiles)
            {
                if (md == null || md.unitPrefab == null || md.jsonKey == null || bombArmor1915.ContainsKey(md.jsonKey)) continue;
                var sm = md.unitPrefab.GetComponent<Missile>();
                var wh = sm != null ? warheadF1915.GetValue(sm) : null;
                var ae = wh != null ? airF.GetValue(wh) as GameObject : null;
                if (ae == null || ae.GetComponentInChildren<Shockwave>(true) != null) continue;
                float y = (float)yieldF.GetValue(sm);
                if (!BombArmorMath1915.FizzleCandidate(y)) continue;
                if (y < bestY) { bestY = y; best = ae; from = $"{md.jsonKey} air burst (yield {y:F0}, no shockwave)"; }
            }
            return best;
        }
    }
}
