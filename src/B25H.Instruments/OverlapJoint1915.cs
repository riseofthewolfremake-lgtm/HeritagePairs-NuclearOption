// B25H.Instruments 1.9.15 OverlapJoint1915 (bug 1 of 2026-11-26: "aircraft fall apart during taxi"; the B-17G tail ALWAYS fell off).
//
// Measured in game on 1.9.14 (MODLOG "Bug repro 11-26"): the family builders add "anti-overlap" FixedJoints between parts whose collider bounds
// intersect but are not parent / child (B17GBuild / B25HBuild / GA25XBuild / MSB1780Build / NimrodBuild / FD32Build AddJoints, force and
// torque 0.3 x the weaker real joint). They make the airframe statically indeterminate: settling under complex physics they carry torque
// through long lever arms and snap at rest (B-17G fus_waist / flap_inner 182-195 k against 180 k, 0.85 s after complex physics at 0 m/s;
// GA-25X nacelle 341,757 > 336,000; B-25H 240,768 > 240,000; Mk I 285 k > 117 k). The stock code cannot tell WHICH joint of a part broke:
// UnitPart.OnJointBreak raises onJointBroken(part) for any joint, and AeroPart.Part_OnTensorBreak then zeroes every joint whose tensor is
// that part - so a broken flap overlap joint reads as "fus_waist broke off", the tail's grandparent joints go to 0, the primary joints are
// overloaded and the whole tail is gone in ~50 ms; the loose parts then hit each other (impact damage 228-2,382 hp).
//
// Fix (no asset rebuild, works on the released 1.9.14 packs): Harmony postfix on Aircraft.SetComplexPhysics (runs after AeroPart.CreateJoints).
// For every AeroPart p of our seven aircraft and every PartJoint pj with a live joint:
//   parent = p.attachInfo.parentPart; primary: pj.connectedPart == parent; grandparent: pj.tensor == parent && pj.connectedPart == the
//   parent's parent; anything else is an anti-overlap joint (OverlapJointMath.Classify). Index 0 (the primary / detach link) is never removed,
//   and a part without attach info is left alone.
//   Each anti-overlap joint: breakForce / breakTorque = +Infinity (it cannot break and fire the cascade before it is gone), Destroy(joint),
//   pj.joint = null (Part_OnTensorBreak, ApplyDamage, SpawnFragments, MergeWithParent all skip null joints), and Physics.IgnoreCollision on
//   every collider pair of the two parts (the joint's purpose: no self-contact).
//   Exception: the biplane interplane brace wing_upper_X <-> wing_lower_X (Mk I / FD-32) carries the struts: it is kept, unbreakable at rest
//   (ApplyDamage on the part restores the stock strength; the tensor rule still releases it when the other wing goes) - OverlapJointMath.IsBrace.
//   Self-collision: every pair of the aircraft's own part colliders is ignored (stock parts do not overlap and never need it; our debris
//   passing through its own airframe is cosmetic). Runs again on every simple -> complex switch (CreateJoints re-creates the joints).
//   Round 2 (review of round 1): colliders are collected only when enabled and active in the hierarchy (no "Ignore collision failed"
//   errors), and a pair Physics.GetIgnoreCollision already reports as ignored is skipped, so a later physics LOD switch only does new pairs.
// Multiplayer: joints are simulated by the LocalSim owner (the server for AI, the owning client for a player's aircraft): this runs on every
// machine, deterministic and idempotent. Real damage still breaks parts: ApplyDamage scales the remaining (primary + grandparent) joints.
// Config [Physics] OverlapJoint1915 = Auto (on) / On / Off. Any exception switches it off for the session.
//
// Round 3 (acceptance run of round 2, 2026-11-27 02:42-02:45): 0 parts lost without damage and every B-17G tail stayed on, but 2 GRANDPARENT
// joints broke at hp 100 with no earlier damage: B-25H fus_nose -> fus_forward F 331,753 > bf 300,000 in taxi at 6.8 m/s while its primary
// fus_nose -> fus_cockpit pulled the other way (326,288 of 600,000); GA-25X fus_nose -> fus_forward 423,786 > 420,000 in flight (primary
// 439,480 of 840,000). The primary and the grandparent joint (builder: 0.5 x the primary, tensor = the parent, the stock pattern) are both
// rigid FixedJoints on the same part, so the solver makes them fight; the highest ground loads (1 Hz) were grandparent joints too: GA-25X
// fus_nose -> fus_forward 1.00, the dev aircraft's prop -> root 0.89, B-25H prop_L -> nacelle_L 0.81, B-17G engine_3 -> wing_inner_R 0.66. A grandparent
// break also fires the stock cascade (UnitPart.OnJointBreak -> onJointBroken(part) -> Part_OnTensorBreak zeroes the children's grandparent
// joints). GrandJoint1915 (config [Physics] GrandJoint1915 = Auto (on) / On / Off), our seven aircraft, wherever the aircraft is simulated:
//   G1 at SetComplexPhysics: every grandparent joint of an UNDAMAGED part (hp >= 100) is held: breakForce / breakTorque = +Infinity. It keeps
//      its stiffness (no break-line kinks, 1.9.13) but the fight can no longer break it.
//   G2 AeroPart.ApplyDamage postfix: the stock code restores every live joint of the part to the stock strength x the hit-point factor; a part
//      still at hp >= 100 (a zero-damage call) is held again. A damaged part keeps the stock values: damage detachment is as in 1.9.14.
//   G3 UnitPart.OnJointBreak prefix (Unity calls it before it removes the joint; the broken joint is the one over its limit whose current force
//      or torque equals the reported force, GrandJointMath.BrokenJoint):
//      - a grandparent joint broke while the part's primary joint is live and not over its own limit (a damaged part, or the tensor rule
//        after the parent went): the part is still attached by its primary joint, so the stock onJointBroken(part) is NOT raised - no
//        cascade into the children (the round-2 failure);
//      - the primary joint broke while a grandparent joint is held: the held joints get their stock strength back (breakForce x 10, the
//        CreateJoints value) and the stock cascade runs, so a part pulled off by load at full hit points still comes off as in 1.9.14;
//      - anything else: stock.
//   The parent breaking off still releases the grandparent joint (the stock tensor rule sets breakForce 0 on the live joint).
// Round 3 (code review): the aircraft-selection preview (networked = false) is skipped.
// Round 4 (the round-3 acceptance run 04:04-04:35 and the round-3 code review):
//   (a) G3 is fail-safe: the OnJointBreak prefix no longer decides from the force match (round 3 could Suppress on a held grandparent or with no
//       joint over its limit, and a primary break misread as a grandparent break left the part on a held joint). For a tracked part it records
//       the part and a snapshot of its live Joint objects and returns false; the first FixedUpdate of a LATER frame (Runner1915, Bugs1915.cs;
//       Unity destroys a broken joint after the callback) looks at which joint is really gone (GrandJointMath.Confirm):
//       - the primary gone, or already gone at the snapshot -> every held joint of the part (grandparent / interplane brace at +Infinity) gets
//         the stock strength back and the stock onJointBroken(part) is raised (cascade): a part is never left on an unbreakable joint;
//       - only grandparent joints gone while the primary is still live (GrandJoint1915 on) -> no cascade (the round-3 intent);
//       - anything else (an overlap / brace joint gone, nothing seen gone after 3 frames) -> the stock cascade.
//       No runner (destroyed) -> the held joints of the part are released at once and the stock code runs.
//   (b) the hold survives light damage: GrandJointMath.Hold = hp > 90 (round 3: hp 100, so a scratch restored the strengths that were measured
//       breaking at rest). AeroPart.ApplyDamage prefix: a held joint the stock tensor rule zeroed (breakForce 0, the parent went) marks the part
//       released for good; the postfix re-holds the grandparent joints (GrandJoint1915) and the interplane brace (OverlapJoint1915) while
//       hp > 90, the primary is live and the parent is still attached. Damage below hp 90 keeps the stock values (1.9.14 detachment).
//   (c) GrandJoint1915 and OverlapJoint1915 are independent: the SetComplexPhysics pass classifies the joints when either one (or NoseJoint1915)
//       is on; removal / self-collision only with OverlapJoint1915, the grandparent holds only with GrandJoint1915. The OnJointBreak / ApplyDamage
//       hooks are patched when either is on (the braces need the release path too).
//   nose (NoseJoint1915, [Physics], Auto on): the B-25H / GA-25X fus_nose -> fus_forward grandparent joint closes a rigid loop with the two
//       primaries fus_nose -> fus_cockpit -> fus_forward; the solver fight held the nose primary at 0.58 / 0.54 of its limit at rest / taxi in the
//       round-3 run (round 2: it broke the grandparent at hp 100), far above the nose's own load (1,050 / 1,000 kg). At SetComplexPhysics, while
//       the nose is undamaged (hp > 90) with a live primary, that one joint is removed (no loop, no fight) and the fus_nose / fus_forward
//       colliders keep ignoring each other (the joint's enableCollision = false did that). The nose then hangs on its primary only (stock
//       strength x hit-point factor: damage still breaks it off; 0.5 x primary less total hold than with the grandparent). No Build.cs change.
//   (e) timing: a Stopwatch over the whole pass per aircraft (first pass and every physics LOD switch), collider pairs checked / newly ignored,
//       counters (passCount1915 / passLod1915 / passMsMax1915 ...) and a summary line every 120 s when they changed (Counters1915, Bugs1915.cs).
// Round 7 (the code review of round 6): the round-6 re-hold of the children after a Stock outcome ran straight after the stock cascade and wrote
//   +Infinity back onto the grandparent joints (tensor == the part) that Part_OnTensorBreak had just zeroed, in the same FixedUpdate, before the
//   physics step: the stock cascade on the children was cancelled. Now HoldNow1915 never writes +Infinity onto a zeroed joint, and a pre-released
//   child with a zeroed held joint is released for good (cg.released, round 4 b) and counted (grandStockCascade1915); only a child the cascade
//   did not reach is held again (grandStockReheld1915). The Stock outcome is the stock cascade, as in 1.9.14.
using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class OverlapJointMath
    {
        public enum Kind { Primary, Grandparent, Overlap, Keep }

        /// joint index i of a part whose attach parent is `parent` (null: no attach info) and grandparent `grand`
        public static Kind Classify(int index, object connected, object tensor, object parent, object grand)
        {
            if (parent == null) return Kind.Keep;                                       // no attach info: never touched
            if (ReferenceEquals(connected, parent)) return Kind.Primary;
            if (grand != null && ReferenceEquals(tensor, parent) && ReferenceEquals(connected, grand)) return Kind.Grandparent;
            if (index == 0) return Kind.Keep;                                           // the detach link (CreateRB fills joints[0].connectedPart): never removed
            return Kind.Overlap;
        }

        /// biplane interplane brace (Mk I / FD-32 wing_upper_X <-> wing_lower_X): the only anti-overlap joint that carries real structure (the
        /// struts; 1.9.13 wing stiffness). Kept, unbreakable at rest; ApplyDamage on its part restores the stock strength, and the stock tensor
        /// rule still lets it go when the other wing breaks off.
        /// round 2: a collider IgnoreCollision may be called on (exists, enabled, active in the hierarchy)
        public static bool LiveCollider(bool exists, bool enabled, bool activeInHierarchy) => exists && enabled && activeInHierarchy;

        public static bool IsBrace(string owner, string other)
        {
            if (owner == null || other == null) return false;
            bool a = owner.StartsWith("wing_upper_") && other.StartsWith("wing_lower_"), b = owner.StartsWith("wing_lower_") && other.StartsWith("wing_upper_");
            return (a || b) && owner.Substring(owner.Length - 2) == other.Substring(other.Length - 2);
        }
    }

    /// round 3: grandparent joints (G1-G3 in the header); round 4: Hold above 90 hp, Confirm one frame later
    public static class GrandJointMath
    {
        public enum Action { Stock, Suppress, Release }
        public const float HoldHp = 90f;                 // round 4 (b): held while hp > 90 (round 3: hp 100)
        public const int ConfirmTries = 3;               // round 4 (a): frames to wait for the broken joint to be destroyed
        public const int ChainHops = 32;                 // round 5: attach-chain walk limit (ChainAttached1915)

        /// G1 / G2: a grandparent joint (and the interplane brace) is held unbreakable while its part is undamaged or lightly damaged
        public static bool Hold(float hitPoints) => hitPoints > HoldHp;

        /// the index of the joint Unity reports as broken (the reported force = its current force or torque). Joints over their limit
        /// (current >= 0.999 x limit; a zeroed joint always is) are preferred; among them the closest match. NaN force = no live joint
        /// there. -1 when there is none. Round 4: used for the log line only (the decision is Confirm, from the joints really gone).
        public static int BrokenJoint(float reported, float[] force, float[] breakForce, float[] torque, float[] breakTorque)
        {
            int best = -1; bool bestOver = false; float bestErr = float.MaxValue;
            float scale = Math.Max(Math.Abs(reported), 1f);
            for (int i = 0; i < force.Length; i++)
            {
                if (float.IsNaN(force[i])) continue;
                bool over = force[i] >= breakForce[i] * 0.999f || torque[i] >= breakTorque[i] * 0.999f;
                float err = Math.Min(Math.Abs(force[i] - reported), Math.Abs(torque[i] - reported)) / scale;
                if (best < 0 || (over && !bestOver) || (over == bestOver && err < bestErr)) { best = i; bestOver = over; bestErr = err; }
            }
            return best;
        }

        /// round 4 (a): G3 decision a frame after the break, from the joints that are really gone (destroyed by Unity).
        /// primaryWasLive: the primary joint existed at the break; primaryGone: it is destroyed now; grandGone / otherGone: a grandparent /
        /// any other joint of the part is destroyed now; suppressOn: GrandJoint1915 is on.
        public static Action Confirm(bool primaryWasLive, bool primaryGone, bool grandGone, bool otherGone, bool suppressOn)
        {
            if (!primaryWasLive || primaryGone) return Action.Release;               // the part is off its primary: nothing may hold it unbreakably
            if (suppressOn && grandGone && !otherGone) return Action.Suppress;       // only a grandparent went, the primary holds: no cascade
            return Action.Stock;                                                     // overlap / brace joint, or nothing seen gone: stock cascade
        }

        /// round 6 (defect 2): the pre-released children are held again after a Stock outcome while the part is still on its live primary
        public static bool StockReHold(bool primaryLive, bool detached) => primaryLive && !detached;

        /// round 7 (review of round 6): a joint the stock tensor rule zeroed (AeroPart.Part_OnTensorBreak: breakForce = breakTorque = 0)
        public static bool CascadeZeroed(float breakForce, float breakTorque) => breakForce == 0f || breakTorque == 0f;

        /// round 7: what happens to one pre-released child after a Stock outcome. The stock cascade (raised first) zeroed the child's joints
        /// with tensor == the part - every grandparent joint of a child by definition - so such a child is released for good (round 4 b, as
        /// GrandDamagePrefix1915) and never held again; only a child with no zeroed held joint may be re-held (ReHold rules)
        public enum ChildOutcome { Skip, ReleasedForGood, ReHeld }
        public static ChildOutcome StockChild(bool anyHeldZeroed, float hitPoints, bool released, bool primaryLive, bool chainAttached)
        {
            if (released) return ChildOutcome.Skip;
            if (anyHeldZeroed) return ChildOutcome.ReleasedForGood;
            return ReHold(hitPoints, released, primaryLive, chainAttached) ? ChildOutcome.ReHeld : ChildOutcome.Skip;
        }

        /// round 4 (a): wait another frame when nothing is seen gone yet (Unity destroys the joint after the callback)
        public static bool Wait(bool anyGone, int tries) => !anyGone && tries < ConfirmTries;

        /// round 4 (b): may G2 hold the part's joints again after an ApplyDamage? (the tensor rule zeroed one: released for good)
        public static bool ReHold(float hitPoints, bool released, bool primaryLive, bool parentAttached) => Hold(hitPoints) && !released && primaryLive && parentAttached;

        /// the stock strength of a joint (AeroPart.CreateJoints / ApplyDamage): stored x 10 x the hit-point factor
        public static float StockStrength(float stored, float hitPoints, float structuralThreshold)
        {
            float num = Math.Max((hitPoints - structuralThreshold) / Math.Max(100f - structuralThreshold, 1e-3f), 0f);
            return stored * num * 10f;
        }
    }

    /// round 4: the measured rigid loop on the nose (B-25H / GA-25X fus_nose -> fus_forward grandparent with the primaries
    /// fus_nose -> fus_cockpit -> fus_forward); removed at SetComplexPhysics while the nose is undamaged (NoseJoint1915)
    public static class NoseJointMath1915
    {
        public static bool Decouple(string key, string part, string connected) => (key == "B25H" || key == "GA25X") && part == "fus_nose" && connected == "fus_forward";
    }

    public partial class Plugin
    {
        const bool OverlapJointDefault1915 = true;
        const bool GrandJointDefault1915 = true;
        const bool NoseJointDefault1915 = true;
        static BepInEx.Configuration.ConfigEntry<string> grandJointMode1915, noseJointMode1915;
        static bool grandBroken1915;
        static bool grandHooked1915;   // round 4: the release hooks are patched (no joint is ever held without them, e.g. after a config change at run time)
        static int grandLogs1915;
        static FieldInfo structThrF1915, onJointBrokenF1915;
        /// per part of our aircraft: the primary joint index, the grandparent and brace joint indices (rebuilt on every SetComplexPhysics)
        internal class GrandInfo1915 { public int primary = -1; public int[] grand; public int[] brace; public bool released; public UnitPart parent; }
        internal static readonly Dictionary<AeroPart, GrandInfo1915> grandInfo1915 = new Dictionary<AeroPart, GrandInfo1915>();
        internal static int grandSuppressed1915, grandReleased1915, grandStock1915, grandWaited1915, grandReheld1915, noseRemoved1915;   // read by the test helper
        static float nextGrandPrune1915;
        static bool GrandJointOn1915 => Mode1915.On(grandJointMode1915 != null ? grandJointMode1915.Value : "Auto", GrandJointDefault1915);
        static bool NoseJointOn1915 => Mode1915.On(noseJointMode1915 != null ? noseJointMode1915.Value : "Auto", NoseJointDefault1915);
        static BepInEx.Configuration.ConfigEntry<string> overlapJointMode1915;
        static bool overlapBroken1915;
        static int overlapLogs1915;
        static FieldInfo attachInfoF1915, parentPartF1915;
        static readonly HashSet<int> overlapLogged1915 = new HashSet<int>();
        internal static readonly Dictionary<Aircraft, int> overlapRemoved1915 = new Dictionary<Aircraft, int>();   // read by the test helper
        // round 4 (e): pass timing (first pass and every physics LOD switch), read by the test helper and Counters1915
        internal static int passCount1915, passLod1915; internal static double passMsTotal1915, passMsMax1915, passMsLodMax1915; internal static string passMaxWho1915 = "";
        internal static long pairsChecked1915; internal static int pairsMax1915;

        static bool OverlapJointOn1915 => Mode1915.On(overlapJointMode1915 != null ? overlapJointMode1915.Value : "Auto", OverlapJointDefault1915);

        void PatchOverlapJoint1915()
        {
            overlapJointMode1915 = Config.Bind("Physics", "OverlapJoint1915", "Auto", "1.9.15: remove the breakable anti-overlap joints between non-adjacent parts of the six Heritage Pairs aircraft when complex physics starts, and ignore collisions between the aircraft's own parts (their break under normal ground load dropped the B-17G tail, GA-25X / B-25H nacelles and the Mk I engine while taxiing). Real damage still breaks parts off. Auto = build default (on), On, Off.");
            noseJointMode1915 = Config.Bind("Physics", "NoseJoint1915", "Auto", "1.9.15: on the B-25H and GA-25X, remove the nose's second joint (fus_nose to fus_forward) while the nose is undamaged when complex physics starts: it closed a rigid loop with the nose and cockpit joints that loaded the nose joint to over half its strength at rest. Damage still breaks the nose off. Auto = build default (on), On, Off.");
            try
            {
                attachInfoF1915 = HarmonyLib.AccessTools.Field(typeof(UnitPart), "attachInfo");
                parentPartF1915 = attachInfoF1915 != null ? HarmonyLib.AccessTools.Field(attachInfoF1915.FieldType, "parentPart") : null;
                var m = HarmonyLib.AccessTools.Method(typeof(Aircraft), "SetComplexPhysics");
                if (m == null || attachInfoF1915 == null || parentPartF1915 == null) { overlapBroken1915 = true; Logger.LogWarning("1.9.15 overlap joints: disabled (Aircraft.SetComplexPhysics / UnitPart.attachInfo not found)"); return; }
                H1915.Patch(m, postfix: HM1915(nameof(ComplexPhysicsPostfix1915)));
                Logger.LogInfo($"1.9.15 overlap joints: {(OverlapJointOn1915 ? "on" : "off (config [Physics] OverlapJoint1915)")}; nose joints: {(NoseJointOn1915 ? "on" : "off (config [Physics] NoseJoint1915)")}");
            }
            catch (Exception e) { overlapBroken1915 = true; Logger.LogWarning("1.9.15 overlap joints disabled: " + e.Message); }
            PatchGrandJoint1915();
        }

        /// round 3: G2 / G3 hooks (G1 runs in the SetComplexPhysics pass); round 4 (c): patched when GrandJoint1915 OR OverlapJoint1915 is on
        /// (the interplane braces OverlapJoint1915 holds need the same release path), independent of each other
        void PatchGrandJoint1915()
        {
            grandJointMode1915 = Config.Bind("Physics", "GrandJoint1915", "Auto", "1.9.15: the second joint of each part of the six Heritage Pairs aircraft (to its grandparent part) cannot break while the part has more than 90 hit points, and when it breaks on a part still held by its own joint it no longer releases the joints of the parts behind it (the B-25H / GA-25X nose broke at full hit points). Real damage still breaks parts off. Independent of OverlapJoint1915. Auto = build default (on), On, Off.");
            Logger.LogInfo($"1.9.15 grandparent joints: {(GrandJointOn1915 ? "on" : "off (config [Physics] GrandJoint1915)")}");
            if (!GrandJointOn1915 && !OverlapJointOn1915) { Logger.LogInfo("1.9.15 grandparent joints: no joint is held (GrandJoint1915 and OverlapJoint1915 off): stock OnJointBreak / ApplyDamage"); return; }
            try
            {
                structThrF1915 = HarmonyLib.AccessTools.Field(typeof(UnitPart), "structuralThreshold");
                onJointBrokenF1915 = HarmonyLib.AccessTools.Field(typeof(UnitPart), "onJointBroken");   // the event's backing field (raised a frame later, round 4)
                var ad = HarmonyLib.AccessTools.Method(typeof(AeroPart), "ApplyDamage", new[] { typeof(float), typeof(float), typeof(float), typeof(float) });
                var jb = HarmonyLib.AccessTools.Method(typeof(UnitPart), "OnJointBreak", new[] { typeof(float) });
                if (ad == null || jb == null || structThrF1915 == null || onJointBrokenF1915 == null || attachInfoF1915 == null) { grandBroken1915 = true; Logger.LogWarning("1.9.15 grandparent joints: disabled (AeroPart.ApplyDamage / UnitPart.OnJointBreak / structuralThreshold / onJointBroken / attachInfo not found)"); return; }
                EnsureRunner1915();
                H1915.Patch(ad, prefix: HM1915(nameof(GrandDamagePrefix1915)), postfix: HM1915(nameof(GrandDamagePostfix1915)));
                H1915.Patch(jb, prefix: HM1915(nameof(GrandJointBreakPrefix1915), HarmonyLib.Priority.Last));
                grandHooked1915 = true;
                Logger.LogInfo($"1.9.15 grandparent joints: hooks on ({(GrandJointOn1915 ? "grandparent joints held while hp > 90" : "grandparent joints stock")}, {(OverlapJointOn1915 ? "interplane braces held while hp > 90" : "braces stock")}); a joint break is confirmed a frame later from the joint really gone");
            }
            catch (Exception e) { grandBroken1915 = true; Logger.LogWarning("1.9.15 grandparent joints disabled: " + e.Message); }
        }

        static void GLog1915(string s) { if (grandLogs1915++ < 120) Log.LogInfo("1.9.15 grandparent joints: " + s); }

        static IEnumerable<int> HeldIdx1915(GrandInfo1915 gi)
        {
            if (gi.grand != null) foreach (int i in gi.grand) yield return i;
            if (gi.brace != null) foreach (int i in gi.brace) yield return i;
        }

        static bool PrimaryLive1915(AeroPart p, GrandInfo1915 gi)
        {
            var js = p.Joints;
            return js != null && gi.primary >= 0 && gi.primary < js.Length && js[gi.primary] != null && js[gi.primary].joint != null;
        }

        /// round 4 (b): the parent is still on the aircraft (the root has no attach parent: always)
        static bool ParentAttached1915(UnitPart parent)
        {
            if (parent == null) return true;
            if (parent.IsDetached()) return false;
            var ap = parent as AeroPart;
            return ap == null || !grandInfo1915.TryGetValue(ap, out var pg) || PrimaryLive1915(ap, pg);
        }

        /// round 5 (review minor 1): the part itself and its WHOLE attach chain up to the root are on the aircraft (each ancestor not detached,
        /// a tracked ancestor's primary live) - a chunk that departed (its own grandparent break suppressed, then its parent off) is debris and
        /// must never be re-held at +Infinity
        static bool ChainAttached1915(AeroPart p, GrandInfo1915 gi)
        {
            if (p == null || p.IsDetached()) return false;
            UnitPart x = gi != null ? gi.parent : AttachParent1915(p);
            for (int h = 0; h < GrandJointMath.ChainHops && x != null; h++)
            {
                if (!ParentAttached1915(x)) return false;
                x = AttachParent1915(x);
            }
            return true;
        }

        /// hold the grandparent joints (GrandJoint1915) / interplane braces (OverlapJoint1915) of a part at +Infinity now; true if any
        static bool HoldNow1915(AeroPart p, GrandInfo1915 gi)
        {
            var js = p.Joints; if (js == null) return false;
            bool any = false;
            // round 7 (review of round 6): a joint the stock tensor rule zeroed is never written back to +Infinity (round 4 b)
            if (GrandJointOn1915 && gi.grand != null)
                foreach (int i in gi.grand) if (i < js.Length && js[i] != null && js[i].joint != null && !GrandJointMath.CascadeZeroed(js[i].joint.breakForce, js[i].joint.breakTorque)) { js[i].joint.breakForce = float.PositiveInfinity; js[i].joint.breakTorque = float.PositiveInfinity; any = true; }
            if (OverlapJointOn1915 && gi.brace != null)
                foreach (int i in gi.brace) if (i < js.Length && js[i] != null && js[i].joint != null && !GrandJointMath.CascadeZeroed(js[i].joint.breakForce, js[i].joint.breakTorque)) { js[i].joint.breakForce = float.PositiveInfinity; js[i].joint.breakTorque = float.PositiveInfinity; any = true; }
            return any;
        }

        /// round 7: any held joint of the part zeroed by the stock tensor rule (breakForce 0 or breakTorque 0)
        static bool ZeroedHeld1915(AeroPart p, GrandInfo1915 gi)
        {
            var js = p.Joints; if (js == null) return false;
            foreach (int i in HeldIdx1915(gi))
            {
                var j = i < js.Length && js[i] != null ? js[i].joint : null;
                if (j != null && GrandJointMath.CascadeZeroed(j.breakForce, j.breakTorque)) return true;
            }
            return false;
        }

        /// round 5 (review item 3): the feature switches itself off -> ONE sweep releases every held joint of every tracked part and every
        /// recorded break gets its release + stock cascade now, so no part is left on a +Infinity joint after the feature is gone
        internal static int grandDisableReleased1915;
        static void GrandDisable1915(string why)
        {
            bool first = !grandBroken1915;
            grandBroken1915 = true;
            if (!first) return;
            int parts = 0, joints = 0, cascades = 0;
            try
            {
                foreach (var kv in grandInfo1915)
                {
                    if (kv.Key == null || kv.Value == null) continue;
                    try { int n = ReleaseHeld1915(kv.Key, kv.Value); if (n > 0) { parts++; joints += n; } } catch { }
                }
            }
            catch { }
            var pend = new List<GrandPending1915>(grandPending1915);
            grandPending1915.Clear(); grandPendingSet1915.Clear();
            foreach (var pd in pend)
            {
                try { if (pd.p != null) { if (pd.gi != null) joints += ReleaseHeld1915(pd.p, pd.gi); RaiseJointBroken1915(pd.p); cascades++; } } catch { }
            }
            grandDisableReleased1915 += joints;
            Log.LogWarning($"1.9.15 grandparent joints disabled: {why}; released {joints} held joints on {parts} parts, {cascades} recorded breaks given the stock cascade");
        }

        /// the held (+Infinity) joints of the part back to the stock strength (never leave a part on an unbreakable joint); round 5:
        /// permanent = false for the short pre-release of a break's children (they may be held again when the break is a suppressed one)
        static int ReleaseHeld1915(AeroPart p, GrandInfo1915 gi, bool permanent = true)
        {
            var js = p.Joints; if (js == null) return 0;
            float thr = structThrF1915 != null ? (float)structThrF1915.GetValue(p) : 0f;
            int n = 0;
            foreach (int i in HeldIdx1915(gi))
            {
                var j = i < js.Length && js[i] != null ? js[i].joint : null;
                if (j == null || !(float.IsPositiveInfinity(j.breakForce) || float.IsPositiveInfinity(j.breakTorque))) continue;
                j.breakForce = GrandJointMath.StockStrength(js[i].breakForce, p.hitPoints, thr);
                j.breakTorque = GrandJointMath.StockStrength(js[i].breakTorque, p.hitPoints, thr);
                n++;
            }
            if (permanent) gi.released = true;
            return n;
        }

        /// round 4 (b): a held joint the stock tensor rule zeroed (its parent went) is released for good - G2 must never hold it again
        static void GrandDamagePrefix1915(AeroPart __instance)
        {
            if (grandBroken1915 || __instance == null) return;
            try
            {
                if (!grandInfo1915.TryGetValue(__instance, out var gi) || gi.released) return;
                var js = __instance.Joints; if (js == null) return;
                foreach (int i in HeldIdx1915(gi))
                {
                    var j = i < js.Length && js[i] != null ? js[i].joint : null;
                    if (j != null && (j.breakForce == 0f || j.breakTorque == 0f)) { gi.released = true; return; }
                }
            }
            catch (Exception e) { GrandDisable1915("ApplyDamage prefix: " + e.Message); }
        }

        /// G2: the stock ApplyDamage just restored stock x hit-point values on every live joint; round 4 (b): the grandparent joints (GrandJoint1915)
        /// and the interplane brace (OverlapJoint1915) are held again while hp > 90, the primary is live and the parent is still attached
        static void GrandDamagePostfix1915(AeroPart __instance)
        {
            if (grandBroken1915 || __instance == null) return;
            try
            {
                if (!grandInfo1915.TryGetValue(__instance, out var gi)) return;
                if (grandPendingSet1915.Contains(__instance)) return;                  // round 5: a recorded break is being decided: no re-hold before it
                // round 5 (review minor 1): the whole attach chain, not only the direct parent (no debris chunk re-held at +Infinity)
                if (!GrandJointMath.ReHold(__instance.hitPoints, gi.released, PrimaryLive1915(__instance, gi), ChainAttached1915(__instance, gi))) return;
                if (HoldNow1915(__instance, gi) && __instance.hitPoints < 99.999f) grandReheld1915++;
            }
            catch (Exception e) { GrandDisable1915("ApplyDamage postfix: " + e.Message); }
        }

        /// round 4 (a): one OnJointBreak of a tracked part, decided a frame later
        internal class GrandPending1915 { public AeroPart p; public GrandInfo1915 gi; public int frame, tries; public float force; public Joint[] snap; public bool[] live; public string info; public List<AeroPart> children; }
        static readonly List<GrandPending1915> grandPending1915 = new List<GrandPending1915>();
        static readonly HashSet<AeroPart> grandPendingSet1915 = new HashSet<AeroPart>();
        internal static int GrandPendingCount1915 => grandPending1915.Count;   // read by the test helper

        /// G3 (round 4): true = run the stock OnJointBreak now; false = recorded, decided by GrandConfirmStep1915 in a later frame
        static bool GrandJointBreakPrefix1915(UnitPart __instance, float breakForce)
        {
            if (grandBroken1915)
            {
                // round 5 (review item 3): never stock-break a tracked part while it still has a +Infinity joint
                try { var bp = __instance as AeroPart; if (bp != null && grandInfo1915.TryGetValue(bp, out var bgi)) ReleaseHeld1915(bp, bgi); } catch { }
                return true;
            }
            try
            {
                var p = __instance as AeroPart;
                if (p == null || !grandInfo1915.TryGetValue(p, out var gi)) return true;
                var js = p.Joints;
                if (js == null || js.Length == 0) return true;
                if (!RunnerAlive1915) { ReleaseHeld1915(p, gi); return true; }          // no later frame to decide in: release now, stock cascade
                if (grandPendingSet1915.Contains(p)) return false;                       // another joint of the same part in the same step: one decision
                int n = js.Length;
                var pd = new GrandPending1915 { p = p, gi = gi, frame = Time.frameCount, force = breakForce, snap = new Joint[n], live = new bool[n] };
                float[] f = new float[n], bf = new float[n], t = new float[n], bt = new float[n];
                for (int i = 0; i < n; i++)
                {
                    var j = js[i] != null ? js[i].joint : null;
                    pd.snap[i] = j; pd.live[i] = j != null;
                    if (j == null) { f[i] = float.NaN; continue; }
                    f[i] = j.currentForce.magnitude; t[i] = j.currentTorque.magnitude; bf[i] = j.breakForce; bt[i] = j.breakTorque;
                }
                int b = GrandJointMath.BrokenJoint(breakForce, f, bf, t, bt);               // log only
                pd.info = b >= 0 ? $"reported F {breakForce:F0}, closest {p.name} -> {(js[b].connectedPart != null ? js[b].connectedPart.name : "?")} (F {f[b]:F0} / {bf[b]:F0}, T {t[b]:F0} / {bt[b]:F0})" : $"reported F {breakForce:F0}";
                grandPending1915.Add(pd); grandPendingSet1915.Add(p);
                // round 5 (review minor 2): the children's held grandparent joints (child -> this part's parent) go back to the stock strength
                // NOW, not 1-3 frames later with the cascade - a departing part is never tied to the airframe through a child; a suppressed
                // break holds them again (ReHoldChildren1915)
                pd.children = PreReleaseChildren1915(p);
                return false;
            }
            catch (Exception e)
            {
                // round 5 (review item 3): release this part before the stock break, then the one-sweep disable
                try { var ep = __instance as AeroPart; if (ep != null && grandInfo1915.TryGetValue(ep, out var egi)) ReleaseHeld1915(ep, egi); } catch { }
                GrandDisable1915("OnJointBreak prefix: " + e.Message);
                return true;
            }
        }

        /// round 5: the tracked children of p (gi.parent == p) with held joints: released (not permanently), returned for a re-hold
        static List<AeroPart> PreReleaseChildren1915(AeroPart p)
        {
            List<AeroPart> kids = null;
            foreach (var kv in grandInfo1915)
            {
                if (kv.Key == null || kv.Value == null || !ReferenceEquals(kv.Value.parent, p) || kv.Value.released) continue;
                if (ReleaseHeld1915(kv.Key, kv.Value, permanent: false) > 0) { (kids = kids ?? new List<AeroPart>()).Add(kv.Key); grandChildPre1915++; }
            }
            return kids;
        }

        /// round 5: after a suppressed break (p stays on its primary) the pre-released children are held again where G2 would hold them
        /// round 7 (review of round 6): a child whose held joint the stock cascade has already zeroed (Part_OnTensorBreak, tensor == the
        /// broken part) is marked released for good (round 4 b, as GrandDamagePrefix1915) and never written back to +Infinity
        static int ReHoldChildren1915(List<AeroPart> kids) => ReHoldChildren1915(kids, out _);
        static int ReHoldChildren1915(List<AeroPart> kids, out int releasedForGood)
        {
            releasedForGood = 0;
            if (kids == null) return 0;
            int n = 0;
            foreach (var c in kids)
            {
                if (c == null || !grandInfo1915.TryGetValue(c, out var cg)) continue;
                var o = GrandJointMath.StockChild(ZeroedHeld1915(c, cg), c.hitPoints, cg.released, PrimaryLive1915(c, cg), ChainAttached1915(c, cg));
                if (o == GrandJointMath.ChildOutcome.ReleasedForGood) { cg.released = true; releasedForGood++; continue; }
                if (o == GrandJointMath.ChildOutcome.ReHeld && HoldNow1915(c, cg)) n++;
            }
            return n;
        }
        internal static int grandChildPre1915, grandStockReheld1915;   // round 6: children held again after a Stock outcome
        internal static int grandStockCascade1915;                     // round 7: children released for good by the stock cascade of a Stock outcome

        /// raise the stock UnitPart.onJointBroken(part) (the body of the stock OnJointBreak) - the tensor cascade
        static void RaiseJointBroken1915(UnitPart p)
        {
            var d = onJointBrokenF1915 != null ? onJointBrokenF1915.GetValue(p) as Action<UnitPart> : null;
            d?.Invoke(p);
        }

        static readonly List<GrandPending1915> grandReady1915 = new List<GrandPending1915>();

        /// round 4 (a): from Runner1915.FixedUpdate - decide every recorded break of an EARLIER frame from the joints really gone
        internal static void GrandConfirmStep1915()
        {
            if (grandPending1915.Count == 0) return;
            int frame = Time.frameCount;
            grandReady1915.Clear();
            foreach (var pd in grandPending1915) if (frame > pd.frame) grandReady1915.Add(pd);
            foreach (var pd in grandReady1915)
            {
                if (!grandPending1915.Contains(pd)) continue;                           // round 5: already flushed by GrandDisable1915
                try
                {
                    var p = pd.p;
                    var ac = p != null ? p.parentUnit as Aircraft : null;
                    // part gone, merged back (simple physics: MergeWithParent destroyed every joint) or joints re-created (a new SetComplexPhysics): no decision
                    if (p == null || ac == null || ac.simplePhysics || !grandInfo1915.TryGetValue(p, out var gi) || !ReferenceEquals(gi, pd.gi)) { Drop1915(pd); continue; }
                    // round 5 (review item 3): release before the stock cascade (GrandDisable1915 normally empties the list first)
                    if (grandBroken1915) { Drop1915(pd); ReleaseHeld1915(p, gi); RaiseJointBroken1915(p); continue; }
                    bool Gone(int i) => i >= 0 && i < pd.snap.Length && pd.live[i] && !pd.snap[i];   // destroyed by Unity (Object == null)
                    bool primaryWasLive = gi.primary >= 0 && gi.primary < pd.live.Length && pd.live[gi.primary];
                    bool primaryGone = Gone(gi.primary);
                    bool grandGone = false, otherGone = false, any = false;
                    for (int i = 0; i < pd.snap.Length; i++)
                    {
                        if (!Gone(i)) continue;
                        any = true;
                        if (i == gi.primary) continue;
                        if (gi.grand != null && Array.IndexOf(gi.grand, i) >= 0) grandGone = true; else otherGone = true;
                    }
                    if (GrandJointMath.Wait(any, pd.tries) && primaryWasLive) { pd.tries++; pd.frame = frame; grandWaited1915++; continue; }
                    Drop1915(pd);
                    string ac0 = ac.name;
                    var act = GrandJointMath.Confirm(primaryWasLive, primaryGone, grandGone, otherGone, GrandJointOn1915);
                    if (act == GrandJointMath.Action.Suppress)
                    {
                        grandSuppressed1915++;
                        int rh = ReHoldChildren1915(pd.children);
                        GLog1915($"{ac0}: {p.name} grandparent joint gone, primary still live (hp {p.hitPoints:F0}; {pd.info}): no tensor cascade{(rh > 0 ? $", {rh} children held again" : "")}");
                        continue;
                    }
                    if (act == GrandJointMath.Action.Release)
                    {
                        grandReleased1915++;
                        int r = ReleaseHeld1915(p, gi);
                        GLog1915($"{ac0}: {p.name} primary joint {(primaryWasLive ? "broke" : "was already gone")} (hp {p.hitPoints:F0}; {pd.info}): {r} held joints back to the stock strength, stock cascade");
                    }
                    else
                    {
                        grandStock1915++;
                        if (grandStock1915 <= 20) GLog1915($"{ac0}: {p.name} {(any ? (otherGone ? "overlap / brace joint gone" : "joint gone") : "no joint seen gone")} (hp {p.hitPoints:F0}; {pd.info}): stock cascade");
                    }
                    RaiseJointBroken1915(p);
                    // round 6 (review of round 5, defect 2) + round 7 (review of round 6): on the Stock outcome (an overlap / brace joint or
                    // nothing seen gone) p is still on its primary. The stock cascade just raised (Part_OnTensorBreak, synchronous) zeroed every
                    // joint with tensor == p - each child's grandparent joint - but detaches nothing in this frame. Those children are released
                    // for good (cg.released, round 4 b) and keep the zeroed joint: the Stock outcome IS the stock cascade, as in 1.9.14. Only a
                    // pre-released child the cascade did not reach (no zeroed held joint) is held again where G2 would hold it.
                    if (act == GrandJointMath.Action.Stock && GrandJointMath.StockReHold(PrimaryLive1915(p, gi), p.IsDetached()))
                    {
                        int srh = ReHoldChildren1915(pd.children, out int scas);
                        grandStockReheld1915 += srh; grandStockCascade1915 += scas;
                        if ((srh > 0 || scas > 0) && grandStock1915 <= 20) GLog1915($"{ac0}: {p.name} stock outcome, primary still live: {scas} children released for good by the stock cascade, {srh} held again");
                    }
                }
                catch (Exception e)
                {
                    // round 5 (review item 3): never drop a recorded break silently - release the part's held joints, raise the stock cascade,
                    // then the one-sweep disable
                    Drop1915(pd);
                    try { if (pd.p != null) { if (pd.gi != null) ReleaseHeld1915(pd.p, pd.gi); RaiseJointBroken1915(pd.p); } } catch { }
                    GrandDisable1915("confirm step: " + e.Message);
                }
            }
        }

        static void Drop1915(GrandPending1915 pd) { grandPending1915.Remove(pd); if (pd.p != null) grandPendingSet1915.Remove(pd.p); else grandPendingSet1915.RemoveWhere(x => x == null); }

        /// G1 (from the JointPass1915 pass): records the part's primary / grandparent / brace indices and holds the grandparent joints (GrandJoint1915)
        /// of a part above 90 hp with a live primary. Returns the number held.
        static int HoldGrand1915(AeroPart p, UnitPart parent, int primary, List<int> grand, List<int> brace, bool holdGrand)
        {
            if (grandBroken1915) return 0;
            float now = Time.time;
            if (now >= nextGrandPrune1915)
            {
                nextGrandPrune1915 = now + 30f;
                List<AeroPart> dead = null;
                foreach (var kv in grandInfo1915) if (kv.Key == null) (dead = dead ?? new List<AeroPart>()).Add(kv.Key);
                if (dead != null) foreach (var k in dead) grandInfo1915.Remove(k);
            }
            var gi = new GrandInfo1915 { primary = primary, parent = parent, grand = grand.Count > 0 ? grand.ToArray() : null, brace = brace.Count > 0 ? brace.ToArray() : null };
            grandInfo1915[p] = gi;
            if (!holdGrand || !GrandJointMath.Hold(p.hitPoints) || !PrimaryLive1915(p, gi)) return 0;
            int n = 0;
            foreach (int i in grand)
            {
                var j = p.Joints[i].joint;
                if (j == null) continue;
                j.breakForce = float.PositiveInfinity; j.breakTorque = float.PositiveInfinity; n++;
            }
            return n;
        }

        static UnitPart AttachParent1915(UnitPart p)
        {
            var ai = p != null ? attachInfoF1915.GetValue(p) : null;               // UnitPart.AttachInfo is a protected nested class: reflection
            return ai != null ? parentPartF1915.GetValue(ai) as UnitPart : null;
        }

        static void ComplexPhysicsPostfix1915(Aircraft __instance)
        {
            var a = __instance;
            // round 3 (code review): the aircraft-selection preview (networked = false, AircraftSelectionMenu.cs:465) is never touched, so it
            // can never switch the fix off for the session
            if (overlapBroken1915 || a == null || !a.networked || a.definition == null || !AirbrakeIdleMath.IsKey(a.definition.jsonKey)) return;
            try
            {
                if (OverlapJointOn1915 || (GrandJointOn1915 && !grandBroken1915) || NoseJointOn1915) JointPass1915(a);   // round 4 (c): independent toggles
                AddContactProbes1915(a);                                                 // W4 (AiGroundWatch1915.cs); round 3: on every machine, the probe acts on the server only
            }
            catch (Exception e) { overlapBroken1915 = true; Log.LogWarning("1.9.15 overlap joints disabled: " + e.Message); }
        }

        /// one SetComplexPhysics pass (CreateJoints just re-created every joint): classify, nose loop, overlap removal, braces, grandparent holds,
        /// self-collision; round 4 (e): timed
        static void JointPass1915(Aircraft a)
        {
            if (a.partLookup == null) return;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            bool ovOn = OverlapJointOn1915, gOn = GrandJointOn1915 && !grandBroken1915, nOn = NoseJointOn1915, track = (gOn || ovOn) && grandHooked1915 && !grandBroken1915;
            string key = a.definition.jsonKey;
            int removed = 0, pairs = 0, kept = 0, braces = 0, already = 0, held = 0, nose = 0, self = 0;
            long checkedPairs = 0;
            var cols = new Dictionary<UnitPart, Collider[]>();
            // round 2 (review of round 1): only enabled colliders on active GameObjects (IgnoreCollision on an inactive / disabled collider
            // logs "Ignore collision failed. Both colliders need to be activated" each call), and a pair that is already ignored (an earlier
            // SetComplexPhysics: CheckPhysicsLod switches back whenever the camera comes within 10 km) is skipped - no repeat work, no log
            Collider[] Cols(UnitPart p) { if (!cols.TryGetValue(p, out var c)) cols[p] = c = LiveColliders1915(p); return c; }
            void Ignore(Collider c1, Collider c2, ref int n) { checkedPairs++; if (Physics.GetIgnoreCollision(c1, c2)) { already++; return; } Physics.IgnoreCollision(c1, c2, true); n++; }
            foreach (var up in a.partLookup)
            {
                var p = up as AeroPart;
                if (p == null || p.Joints == null) continue;
                var parent = AttachParent1915(p);
                var grand = parent != null ? AttachParent1915(parent) : null;
                var js = p.Joints;
                int primary = -1; var grandIdx = new List<int>(); var braceIdx = new List<int>();
                for (int i = 0; i < js.Length && primary < 0; i++)
                    if (js[i] != null && js[i].joint != null && OverlapJointMath.Classify(i, js[i].connectedPart, js[i].tensor, parent, grand) == OverlapJointMath.Kind.Primary) primary = i;
                for (int i = 0; i < js.Length; i++)
                {
                    var pj = js[i];
                    if (pj == null || pj.joint == null) continue;
                    var k = OverlapJointMath.Classify(i, pj.connectedPart, pj.tensor, parent, grand);
                    if (k == OverlapJointMath.Kind.Grandparent)
                    {
                        // round 4: the nose loop (B-25H / GA-25X fus_nose -> fus_forward), removed while the nose is undamaged and on its primary
                        if (nOn && primary >= 0 && GrandJointMath.Hold(p.hitPoints) && NoseJointMath1915.Decouple(key, p.name, pj.connectedPart != null ? pj.connectedPart.name : null))
                        {
                            pj.joint.breakForce = float.PositiveInfinity; pj.joint.breakTorque = float.PositiveInfinity;   // cannot fire OnJointBreak before it is gone
                            UnityEngine.Object.Destroy(pj.joint);
                            pj.joint = null;
                            nose++; noseRemoved1915++;
                            if (pj.connectedPart != null)                                                                // its enableCollision = false kept them apart
                                foreach (var c1 in Cols(p)) foreach (var c2 in Cols(pj.connectedPart))
                                    if (c1 != null && c2 != null && c1 != c2) Ignore(c1, c2, ref pairs);
                            continue;
                        }
                        grandIdx.Add(i);
                    }
                    if (k != OverlapJointMath.Kind.Overlap || !ovOn) { kept++; continue; }
                    if (OverlapJointMath.IsBrace(p.name, pj.connectedPart != null ? pj.connectedPart.name : null))
                    {
                        braceIdx.Add(i); braces++;
                        if (track && parent != null && GrandJointMath.Hold(p.hitPoints)) { pj.joint.breakForce = float.PositiveInfinity; pj.joint.breakTorque = float.PositiveInfinity; }   // interplane brace: kept, unbreakable while hp > 90
                        continue;
                    }
                    pj.joint.breakForce = float.PositiveInfinity;
                    pj.joint.breakTorque = float.PositiveInfinity;
                    UnityEngine.Object.Destroy(pj.joint);
                    pj.joint = null;
                    removed++;
                    if (pj.connectedPart != null)
                        foreach (var c1 in Cols(p)) foreach (var c2 in Cols(pj.connectedPart))
                            if (c1 != null && c2 != null && c1 != c2) Ignore(c1, c2, ref pairs);
                }
                if (parent != null && track) held += HoldGrand1915(p, parent, primary, grandIdx, braceIdx, gOn);   // round 3: G1; round 4: GrandJoint1915 holds, braces recorded for G2 / G3
            }
            // self-collision: every pair of the aircraft's own part colliders (bodies of different parts) - OverlapJoint1915 only
            int colCount = 0;
            if (ovOn)
            {
                var all = new List<Collider>();
                var seen = new HashSet<Collider>();
                foreach (var up in a.partLookup) if (up != null) foreach (var c in Cols(up)) if (c != null && !c.isTrigger && seen.Add(c)) all.Add(c);
                colCount = all.Count;
                for (int i = 0; i < all.Count; i++)
                    for (int j = i + 1; j < all.Count; j++)
                    {
                        var ra = all[i].attachedRigidbody; var rb = all[j].attachedRigidbody;
                        if (ra != null && ReferenceEquals(ra, rb)) continue;               // same body: PhysX never pairs them
                        Ignore(all[i], all[j], ref self);
                    }
                overlapRemoved1915[a] = removed;
            }
            sw.Stop();
            double ms = sw.Elapsed.TotalMilliseconds;
            bool first = overlapLogged1915.Add(a.GetInstanceID());
            passCount1915++; if (!first) passLod1915++;
            passMsTotal1915 += ms; pairsChecked1915 += checkedPairs; if (checkedPairs > pairsMax1915) pairsMax1915 = (int)checkedPairs;
            if (ms > passMsMax1915) { passMsMax1915 = ms; passMaxWho1915 = $"{a.name} ({key}, {(first ? "first pass" : "LOD switch")}, {checkedPairs} pairs)"; }
            if (!first && ms > passMsLodMax1915) passMsLodMax1915 = ms;
            if (first && overlapLogs1915++ < 60)
                Log.LogInfo($"1.9.15 overlap joints: {removed} removed, {pairs} collider pairs ignored on {a.name} ({key}; {kept} primary / grandparent joints kept, {braces} interplane braces kept unbreakable at rest, {held} grandparent joints held while undamaged, {nose} nose grandparent joints removed, {self} own collider pairs ignored, {already} already ignored, {colCount} active colliders; pass {ms:F2} ms, {checkedPairs} pairs checked)");
            else if (!first && (self + pairs > 0 || ms > 2.0) && overlapLogs1915++ < 120)
                Log.LogInfo($"1.9.15 overlap joints: physics LOD switch on {a.name}: {removed} removed, {pairs + self} new collider pairs ignored, {already} already ignored, {nose} nose grandparent joints removed; pass {ms:F2} ms, {checkedPairs} pairs checked");
        }

        /// round 2: the part's colliders that PhysX can pair now (enabled, on an active GameObject)
        static Collider[] LiveColliders1915(UnitPart p)
        {
            var all = p.GetComponentsInChildren<Collider>(false);                  // false: active GameObjects only
            int n = 0;
            for (int i = 0; i < all.Length; i++) if (OverlapJointMath.LiveCollider(all[i] != null, all[i] != null && all[i].enabled, all[i] != null && all[i].gameObject.activeInHierarchy)) all[n++] = all[i];
            if (n == all.Length) return all;
            var r = new Collider[n]; Array.Copy(all, r, n); return r;
        }
    }
}
