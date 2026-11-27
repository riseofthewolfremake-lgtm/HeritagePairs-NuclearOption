// 1.9.15 (offline, 2026-11-27): Unity check rows for the bug fixes of the user's list of 2026-11-26, on the BUILT prefabs (no build change).
// Run after FamilyBuild.BuildAll:   unity.sh - <log> -executeMethod B25HTools.Bugs1126Check.Run
// Rows:
//  * bug 1 (OverlapJoint1915.cs): every family aircraft prefab, every AeroPart joint classified exactly as the plugin does at runtime
//    (attach parent = the transform parent's UnitPart, as UnitPart.Awake; primary = connectedPart == parent; grandparent = tensor == parent and
//    connectedPart == the parent's parent; else anti-overlap; index 0 never removed). Every non-root part has an attach parent and keeps its
//    primary joint at index 0 (so removing the anti-overlap joints never cuts a part loose); the anti-overlap count per aircraft is logged
//    (the B-17G in-game probe: 15) and is > 0 on every aircraft built with the overlap loop.
//  * bug 1 round 3 (GrandJoint1915 in OverlapJoint1915.cs): every aircraft has grandparent joints with tensor = the attach parent and 0.5 x the
//    primary strength, and the joints measured over 0.5 of their limit / broken at hp 100 in the round-2 acceptance run are grandparent joints.
//  * bug 1 round 4 (NoseJoint1915 in OverlapJoint1915.cs): on the B-25H and GA-25X the nose's grandparent joint fus_nose -> fus_forward
//    closes a rigid loop with the primaries fus_nose -> fus_cockpit -> fus_forward (the round-3 run: nose primary at 0.58 / 0.54 of its limit
//    at rest / taxi); the plugin removes exactly that joint while the nose is undamaged. Row: the loop exists on the built prefab, under the
//    names the plugin matches (NoseJointMath1915.Decouple), with the masses and strengths logged; no other aircraft has the target.
//  * round 5 (round-4 acceptance: a dangling else in AiGroundWatch1915.Evaluate1915 compiled and passed every check, then the first taxi
//    queue hold called Taxi1915.tkRunwayVector(null) and the whole watch went off): a C#-side structure check of the plugin source - the
//    take-off branch is "else if (tk != null)" directly after the closing brace of "if (taxi != null) { ... }", every Taxi1915.tk*(tk) call
//    in Evaluate1915 sits inside that branch or behind "tk != null ?", and no closed block in the 1.9.15 files is followed by a
//    single-line "if (...) { ... }" and then an "else" line (the round-4 slip). Source = env HP_REPO or C:\Users\User\Nuclear Option B-25.
//  * round 6 (review of round 5, defect 1: the first orbit's re-path removed the moving target and the deadEnd1915 entry, so the crawl block
//    behind "if (!recovering) return;" never ran on the re-planned path): DeadEndStructure - in AiTaxiDeadEnd1915.DeadEndPostfix1915 no
//    "if (!recovering) return;" precedes the crawl block, the gate is WatchActive(recovering, repathWatch) with repathWatch from the state
//    record, and the re-path block keeps the watch (tr.repath = dest) without a return. Same source (HP_REPO); FAILS on a061964.
//  * round 7 (review of round 6, defect 2: the Stock-outcome re-hold wrote +Infinity back onto the grandparent joints the stock cascade had
//    just zeroed): StockCascadeStructure - HoldNow1915 guards both loops with CascadeZeroed, ReHoldChildren1915 releases a cascade-zeroed
//    child for good, the cascade is raised before the re-hold. Same source (HP_REPO); FAILS on 259e371.
//  * round 8 (round-7 acceptance: a natural Mk I circle round its stock yield point, 435 game s, no rule): YieldOrbitStructure - in
//    AiGroundWatch1915.Evaluate1915 the stock yield restarts W2 / W3 only through GroundWatchMath1915.YieldWait (not for as long as it lasts),
//    W3 progress goes through OrbitProgress, W5 HeadingOrbitCheck1915 runs in the taxi state, Stuck1915 sends a yielding aircraft to the stock
//    disembark; in AiTaxiDeadEnd1915.DeadEndPostfix1915 the yield-orbit step runs before the destination code and ends with disembarking;
//    a held-off-runway step and separate log budgets. Same source (HP_REPO); FAILS on 6e8282a.
//  * bug 4 (BombArmor1915.cs): every family bomb prefab with its jsonKey and armour; the Cooper is the stock PAB-125 clone (fire armour 3.5,
//    tolerance 0.3, blast armour 150), i.e. the values the plugin lowers at runtime, under the key the plugin lists.
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace B25HTools
{
    public static class Bugs1126Check
    {
        public const int B17GOverlapExpected = 15;            // in-game probe 2026-11-26 (MODLOG "Bug repro 11-26")
        public const string CooperKey = "NIMROD1_cooper";      // == BombArmorMath1915.CooperKey (stub_tests_bugs_1126 compares)

        public enum Kind { Primary, Grandparent, Overlap, Keep }

        /// == NoseJointMath1915.Decouple (plugin, round 4)
        public static bool NoseDecouple(string key, string part, string connected) => (key == "B25H" || key == "GA25X") && part == "fus_nose" && connected == "fus_forward";

        public static Kind Classify(int index, Object connected, Object tensor, Object parent, Object grand)
        {
            if (parent == null) return Kind.Keep;
            if (connected == parent) return Kind.Primary;
            if (grand != null && tensor == parent && connected == grand) return Kind.Grandparent;
            if (index == 0) return Kind.Keep;
            return Kind.Overlap;
        }

        /// == OverlapJointMath.IsBrace (plugin)
        public static bool IsBrace(string owner, string other)
        {
            if (owner == null || other == null) return false;
            bool a = owner.StartsWith("wing_upper_") && other.StartsWith("wing_lower_"), b = owner.StartsWith("wing_lower_") && other.StartsWith("wing_upper_");
            return (a || b) && owner.Substring(owner.Length - 2) == other.Substring(other.Length - 2);
        }

        static UnitPart AttachParent(UnitPart p)
        {
            var t = p.transform.parent;
            if (t == null) return null;
            var up = t.GetComponent<UnitPart>();
            if (p.parentUnit == null && t.parent != null) up = t.parent.GetComponent<UnitPart>();   // UnitPart.Awake
            return up;
        }

        static (bool, string) Row(string name, bool ok, string detail) { Debug.Log($"[B25H] BUGS1126 {(ok ? "PASS" : "FAIL")} {name}{(detail.Length > 0 ? " | " + detail : "")}"); return (ok, name); }

        public static void Run()
        {
            var rows = new List<(bool, string)>();
            var root = FamilyBuild.FamilyRoot;
            int aircraft = 0;
            foreach (var path in AssetDatabase.FindAssets("t:Prefab", new[] { root }).Select(AssetDatabase.GUIDToAssetPath).OrderBy(p => p))
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (prefab == null) continue;
                var ac = prefab.GetComponent<Aircraft>();
                if (ac != null) { aircraft++; JointRows(rows, prefab, path); continue; }
                var m = prefab.GetComponent<Missile>();
                if (m != null) BombRow(rows, m, path);
            }
            rows.Add(Row($"family aircraft prefabs found under {root}", aircraft >= 6, $"{aircraft}"));
            SourceRows(rows);
            int fail = rows.Count(r => !r.Item1);
            Debug.Log(fail == 0 ? $"[B25H] BUGS1126 CHECK ALL PASS ({rows.Count} rows)" : $"[B25H] BUGS1126 CHECK FAIL ({fail} of {rows.Count} rows)");
        }

        static void JointRows(List<(bool, string)> rows, GameObject prefab, string path)
        {
            var key = prefab.name;
            var rootPart = prefab.GetComponent<UnitPart>();
            int prim = 0, gp = 0, ov = 0, keep = 0, noParent = 0, badFirst = 0, noJoint = 0, brace = 0;
            var overlapNames = new List<string>();
            var grandNames = new HashSet<string>(); int grandBadRatio = 0, grandTensor = 0;   // round 3 (GrandJoint1915)
            int noseTargets = 0; string noseInfo = "";                                         // round 4 (NoseJoint1915)
            foreach (var p in prefab.GetComponentsInChildren<AeroPart>(true))
            {
                if (p == rootPart) continue;
                var parent = AttachParent(p);
                var grand = parent != null ? AttachParent(parent) : null;
                var js = p.Joints ?? new PartJoint[0];
                if (parent == null) { noParent++; continue; }
                if (js.Length == 0) { noJoint++; continue; }
                var k0 = Classify(0, js[0].connectedPart, js[0].tensor, parent, grand);
                if (!(js[0].connectedPart == null || k0 == Kind.Primary)) badFirst++;   // CreateRB fills a null joints[0].connectedPart with the parent
                for (int i = 0; i < js.Length; i++)
                {
                    var k = Classify(i, js[i].connectedPart, js[i].tensor, parent, grand);
                    if (k == Kind.Grandparent)
                    {
                        grandNames.Add($"{p.name}->{js[i].connectedPart.name}");
                        if (NoseDecouple(key, p.name, js[i].connectedPart.name))
                        {
                            var pjs = parent is AeroPart pa ? pa.Joints : null;
                            bool loop = parent.name == "fus_cockpit" && js[0].connectedPart == parent && pjs != null && pjs.Length > 0 && pjs[0].connectedPart == grand && grand != null && grand.name == "fus_forward";
                            if (loop) noseTargets++;
                            noseInfo = $"fus_nose {p.mass:F0} kg on fus_cockpit {parent.mass:F0} kg; primary {js[0].breakForce:F0}, grandparent {js[i].breakForce:F0} (x10 in game), cockpit primary to {(pjs != null && pjs.Length > 0 && pjs[0].connectedPart != null ? pjs[0].connectedPart.name : "?")}; loop {loop}";
                        }
                        if (js[i].tensor != parent) grandTensor++;
                        if (!(Mathf.Abs(js[i].breakForce - 0.5f * js[0].breakForce) <= 0.01f * js[0].breakForce + 1f)) grandBadRatio++;
                    }
                    if (k == Kind.Primary) prim++; else if (k == Kind.Grandparent) gp++; else if (k == Kind.Keep) keep++;
                    else { ov++; if (IsBrace(p.name, js[i].connectedPart != null ? js[i].connectedPart.name : null)) brace++; overlapNames.Add($"{p.name}->{(js[i].connectedPart != null ? js[i].connectedPart.name : "null")}"); }
                }
            }
            rows.Add(Row($"{key}: every non-root part has an attach parent (UnitPart.Awake rule) and a joint", noParent == 0 && noJoint == 0, $"no parent {noParent}, no joint {noJoint} ({path})"));
            rows.Add(Row($"{key}: joint 0 of every part is the primary joint to its attach parent (kept by OverlapJoint1915: no part is cut loose)", badFirst == 0, $"{badFirst} parts with another joint at index 0"));
            rows.Add(Row($"{key}: joints classified primary {prim} / grandparent {gp} / anti-overlap {ov} (removed at runtime: {ov - brace}; biplane interplane braces kept unbreakable: {brace}) / kept index-0 {keep}; anti-overlap joints exist (the builder's overlap loop)", ov > 0, string.Join(", ", overlapNames.Take(24))));
            if (key == "B17G") rows.Add(Row($"B17G: {ov} anti-overlap joints == {B17GOverlapExpected} (the in-game probe of 2026-11-26)", ov == B17GOverlapExpected, ""));
            // round 3: the grandparent joints GrandJoint1915 holds while the part is undamaged (builder: tensor = the parent, 0.5 x the primary)
            rows.Add(Row($"{key}: {gp} grandparent joints (held unbreakable by GrandJoint1915 while the part is undamaged), each with tensor = the attach parent and 0.5 x the primary strength (the builder's stock pattern)",
                gp > 0 && grandTensor == 0 && grandBadRatio == 0, $"tensor != parent {grandTensor}, ratio != 0.5 {grandBadRatio}"));
            // round 4 (e): the size of the O(n^2) self-collision pass of OverlapJoint1915 (every non-trigger collider of the aircraft, all parts)
            int colN = prefab.GetComponentsInChildren<Collider>(true).Count(c => !c.isTrigger);
            rows.Add(Row($"{key}: {colN} part colliders (the self-collision pass checks at most {colN * (colN - 1) / 2} pairs per SetComplexPhysics)", colN > 0, ""));
            // round 4: the nose loop NoseJoint1915 opens (B-25H / GA-25X only)
            if (key == "B25H" || key == "GA25X")
                rows.Add(Row($"{key}: the nose loop fus_nose -> fus_cockpit -> fus_forward with the grandparent fus_nose -> fus_forward exists once (the joint NoseJoint1915 removes while the nose is undamaged; round-3 nose primary 0.58 / 0.54 at rest / taxi)", noseTargets == 1, noseInfo));
            else
                rows.Add(Row($"{key}: no NoseJoint1915 target (only the B-25H / GA-25X nose is opened)", noseTargets == 0, ""));
            string[] measured = null;   // the round-2 acceptance run: joints over 0.5 of their limit on the ground, and the two hp-100 breaks
            if (key == "B25H") measured = new[] { "fus_nose->fus_forward", "prop_L->nacelle_L" };
            else if (key == "GA25X") measured = new[] { "fus_nose->fus_forward" };
            else if (key == "B17G") measured = new[] { "engine_3->wing_inner_R" };
            else if (grandNames.Any(x => x.StartsWith("prop->"))) measured = new[] { "prop->" + key };   // single-engine aircraft (the dev aircraft: 0.89)
            if (measured != null)
                rows.Add(Row($"{key}: the joints measured over 0.5 of their limit / broken at hp 100 in the round-2 run ({string.Join(", ", measured)}) are grandparent joints (held by GrandJoint1915)",
                    measured.All(grandNames.Contains), string.Join(", ", measured.Where(x => !grandNames.Contains(x)))));
        }

        /// round 5: index of the brace that closes the one at `open` (the plugin's interpolated strings use balanced {x} pairs)
        public static int MatchBrace(string t, int open)
        {
            if (open < 0) return -1;
            int d = 0;
            for (int i = open; i < t.Length; i++) { if (t[i] == '{') d++; else if (t[i] == '}' && --d == 0) return i; }
            return -1;
        }

        /// round 5: the Evaluate1915 structure ("" = fine, else what is wrong)
        public static string EvaluateStructure(string src)
        {
            int m = src.IndexOf("static void Evaluate1915(");
            if (m < 0) return "Evaluate1915 not found";
            int body = src.IndexOf('{', m), end = MatchBrace(src, body);
            if (body < 0 || end < 0) return "Evaluate1915 body not matched";
            string ev = src.Substring(body, end - body + 1);
            int ti = ev.IndexOf("if (taxi != null)");
            if (ti < 0) return "no if (taxi != null)";
            int tb = ev.IndexOf('{', ti), te = MatchBrace(ev, tb);
            if (te < 0) return "taxi block not matched";
            string after = ev.Substring(te + 1).TrimStart();
            if (!after.StartsWith("else if (tk != null)")) return "the statement after the taxi block is not 'else if (tk != null)': " + after.Substring(0, System.Math.Min(60, after.Length)).Replace("\n", " ");
            int kb = ev.IndexOf('{', te + 1), ke = MatchBrace(ev, kb);
            int at = 0;
            while ((at = ev.IndexOf("Taxi1915.tk", at)) >= 0)
            {
                int close = ev.IndexOf(')', at); string call = close > at ? ev.Substring(at, close - at + 1) : "";
                bool inside = at > kb && at < ke;
                bool guarded = ev.LastIndexOf("tk != null ?", at) > ev.LastIndexOf(';', at);
                if (call.EndsWith("(tk)") && !inside && !guarded) return "unguarded " + call;
                at += 10;
            }
            return "";
        }

        /// round 5: a closed block, a single-line "if (...) { ... }", then an "else" line (the round-4 slip) - line numbers, "" = none
        public static string DanglingElse(string src)
        {
            var lines = src.Replace("\r", "").Split('\n'); var hits = new List<string>();
            // the round-4 shape: a block closes ("}"), a single-line "if (...) { ... }" follows, then "else" (the else meant for the block's if)
            for (int i = 1; i + 1 < lines.Length; i++)
            {
                var p = lines[i - 1].Trim(); var a = lines[i].Trim(); var b = lines[i + 1].Trim();
                if (p == "}" && a.StartsWith("if (") && a.EndsWith("}") && a.Contains("{") && (b == "else" || b.StartsWith("else ") || b.StartsWith("else{"))) hits.Add((i + 1).ToString());
            }
            return string.Join(", ", hits);
        }

        /// round 6: the block of the statement starting with `head` ("" if none; a single statement up to its ';')
        static string BlockAfter(string t, string head)
        {
            int i = t.IndexOf(head);
            if (i < 0) return "";
            int k = i + head.Length;
            while (k < t.Length && char.IsWhiteSpace(t[k])) k++;
            if (k >= t.Length) return "";
            if (t[k] != '{') { int sc = t.IndexOf(';', k); return sc > k ? t.Substring(k, sc - k + 1) : ""; }
            int e = MatchBrace(t, k);
            return e > k ? t.Substring(k, e - k + 1) : "";
        }

        /// round 6 (defect 1): the crawl block of DeadEndPostfix1915 is reachable on the frames after a re-path ("" = fine)
        public static string DeadEndStructure(string src)
        {
            int m = src.IndexOf("static void DeadEndPostfix1915(");
            if (m < 0) return "DeadEndPostfix1915 not found";
            int b = src.IndexOf('{', m), e = MatchBrace(src, b);
            if (b < 0 || e < 0) return "DeadEndPostfix1915 body not matched";
            string body = src.Substring(b, e - b + 1);
            int ic = body.IndexOf("if (tr.crawl)");
            if (ic < 0) return "no crawl block";
            string pre = body.Substring(0, ic);
            if (System.Text.RegularExpressions.Regex.IsMatch(pre, @"if \(!recovering\)\s*return;")) return "the crawl block sits behind \"if (!recovering) return;\" (unreachable after a re-path)";
            if (!pre.Contains("if (!DeadEndMath1915.WatchActive(recovering, repathWatch)) return;")) return "no WatchActive(recovering, repathWatch) gate before the crawl block";
            if (!pre.Contains("bool repathWatch = !recovering && tr != null && tr.repath != null;")) return "repathWatch not derived from the state record";
            string rb = BlockAfter(body, "if (repath)");
            if (!rb.Contains("Pathfind(")) return "no re-path block";
            if (rb.Contains("return;")) return "re-path block returns";
            if (!rb.Contains("tr.repath = dest;")) return "re-path block does not keep the watch (tr.repath = dest)";
            return "";
        }

        /// round 7 (review of round 6, defect 2): the Stock-outcome re-hold of the children runs after the stock cascade (RaiseJointBroken1915)
        /// and must not undo it - HoldNow1915 skips a zeroed joint and ReHoldChildren1915 releases a child with a zeroed held joint for good
        /// ("" = fine). FAILS on 259e371 (the re-hold wrote +Infinity back onto the joints Part_OnTensorBreak had zeroed).
        public static string StockCascadeStructure(string src)
        {
            string Body(string head) { int m = src.IndexOf(head); if (m < 0) return ""; int b = src.IndexOf('{', m), e = MatchBrace(src, b); return b >= 0 && e > b ? src.Substring(b, e - b + 1) : ""; }
            string hn = Body("static bool HoldNow1915(AeroPart p, GrandInfo1915 gi)");
            if (hn.Length == 0) return "HoldNow1915 not found";
            int guards = System.Text.RegularExpressions.Regex.Matches(hn, @"!GrandJointMath\.CascadeZeroed\(js\[i\]\.joint\.breakForce, js\[i\]\.joint\.breakTorque\)").Count;
            if (guards < 2) return $"HoldNow1915 writes +Infinity without the zeroed-joint guard ({guards} of 2 loops guarded)";
            string rh = Body("static int ReHoldChildren1915(List<AeroPart> kids, out int releasedForGood)");
            if (rh.Length == 0) return "ReHoldChildren1915(kids, out releasedForGood) not found";
            if (!rh.Contains("ZeroedHeld1915(c, cg)") || !rh.Contains("cg.released = true;")) return "ReHoldChildren1915 does not release a cascade-zeroed child for good";
            string cs = Body("internal static void GrandConfirmStep1915()");
            int st = cs.IndexOf("Action.Stock && GrandJointMath.StockReHold");
            if (st < 0) return "no Stock-outcome re-hold";
            int ra = cs.IndexOf("RaiseJointBroken1915(p);\n"), rr = cs.IndexOf("ReHoldChildren1915(pd.children, out int scas);", st);
            if (rr < 0) return "the Stock-outcome re-hold does not count the cascade-released children";
            if (ra < 0 || ra > rr) return "the stock cascade is not raised before the Stock-outcome re-hold";
            if (src.Contains("the cascade took off is not re-held")) return "the wrong round-6 comment (the cascade detaches nothing in that frame) is still there";
            return "";
        }

        /// round 8 (round-7 acceptance: the stock yield orbit of a Mk I, no rule caught it): "" = fine. FAILS on 6e8282a.
        public static string YieldOrbitStructure(string watchSrc, string deadEndSrc)
        {
            string Body(string src, string head) { int m = src.IndexOf(head); if (m < 0) return ""; int b = src.IndexOf('{', m), e = MatchBrace(src, b); return b >= 0 && e > b ? src.Substring(b, e - b + 1) : ""; }
            string ev = Body(watchSrc, "static void Evaluate1915(");
            if (ev.Length == 0) return "Evaluate1915 not found";
            if (ev.Contains("Taxi1915.yielding(taxi)) { w.progressSince = now;")) return "the stock yield restarts W2 / W3 for as long as it lasts (no YieldWait limit)";
            if (!ev.Contains("GroundWatchMath1915.YieldWait(now - w.yieldSince)")) return "no YieldWait limit on the stock yield";
            if (!ev.Contains("GroundWatchMath1915.OrbitProgress(") || ev.Contains("before = w.samples[first].prog")) return "W3 progress still from the window's first sample";
            if (!ev.Contains("if (taxi != null) HeadingOrbitCheck1915(w, pilot, now, toRunway, destDist, pos);")) return "no W5 heading orbit in the taxi state";
            string sk = Body(watchSrc, "static void Stuck1915(");
            if (!sk.Contains("if (w.yielding) { yieldStuck1915++; StartEject1915(")) return "Stuck1915 runs the re-path ladder for a yielding aircraft (the yield branch steers)";
            string pf = Body(deadEndSrc, "static void DeadEndPostfix1915(");
            if (pf.Length == 0) return "DeadEndPostfix1915 not found";
            int yi = pf.IndexOf("if (Taxi1915.yieldPosition != null && Taxi1915.yielding(st)) { if (YieldOrbitStep1915(st, pf, a)) return; }");
            int di = pf.IndexOf("var dest = Taxi1915.destinationPoint(st);");
            if (yi < 0) return "no yield-orbit step in DeadEndPostfix1915";
            if (di >= 0 && yi > di) return "the yield-orbit step runs after the destination code";
            string yo = Body(deadEndSrc, "static bool YieldOrbitStep1915(");
            if (!yo.Contains("DeadEndMath1915.YieldOrbit(y.cum, y.startDist - y.bestDist)") || !yo.Contains("Taxi1915.disembarkingF.SetValue(st, true);")) return "YieldOrbitStep1915 does not end an orbiting yield with the stock disembark";
            if (!pf.Contains("if (DeadEndMath1915.OffRunway(why) && HeldOffStep1915(st, pf, a, dest, dd)) return;")) return "no held-off-runway step";
            if (deadEndSrc.Contains("deadEndLogs1915++ < 100")) return "one shared log budget (deadEndLogs1915++ < 100)";
            return "";
        }

        static void SourceRows(List<(bool, string)> rows)
        {
            var repo = System.Environment.GetEnvironmentVariable("HP_REPO"); if (string.IsNullOrEmpty(repo)) repo = @"C:\Users\User\Nuclear Option B-25";
            var dir = Path.Combine(repo, "src", "B25H.Instruments");
            var wf = Path.Combine(dir, "AiGroundWatch1915.cs");
            if (!File.Exists(wf)) { rows.Add(Row("round 5 source check: AiGroundWatch1915.cs found", false, wf)); return; }
            string ev = EvaluateStructure(File.ReadAllText(wf));
            rows.Add(Row("round 5: AiGroundWatch1915.Evaluate1915 - the take-off branch is 'else if (tk != null)' of 'if (taxi != null)' and no Taxi1915.tk*(tk) call runs with a null tk", ev.Length == 0, ev));
            var bad = new List<string>();
            foreach (var f in Directory.GetFiles(dir, "*1915.cs")) { var d = DanglingElse(File.ReadAllText(f)); if (d.Length > 0) bad.Add(Path.GetFileName(f) + " line " + d); }
            rows.Add(Row("round 5: no closed block followed by a single-line 'if (...) { ... }' and an 'else' (the round-4 dangling else) in the 1.9.15 plugin files", bad.Count == 0, string.Join("; ", bad)));
            var df = Path.Combine(dir, "AiTaxiDeadEnd1915.cs");
            string ds = File.Exists(df) ? DeadEndStructure(File.ReadAllText(df)) : "AiTaxiDeadEnd1915.cs not found";
            rows.Add(Row("round 6: AiTaxiDeadEnd1915.DeadEndPostfix1915 - the crawl / orbit watch is reachable after the re-path (no 'if (!recovering) return;' before it, WatchActive gate, the re-path keeps the watch and falls through)", ds.Length == 0, ds));
            var of = Path.Combine(dir, "OverlapJoint1915.cs");
            string sc = File.Exists(of) ? StockCascadeStructure(File.ReadAllText(of).Replace("\r", "")) : "OverlapJoint1915.cs not found";
            string yo8 = File.Exists(df) ? YieldOrbitStructure(File.ReadAllText(wf).Replace("\r", ""), File.ReadAllText(df).Replace("\r", "")) : "AiTaxiDeadEnd1915.cs not found";
            rows.Add(Row("round 8: the stock yield orbit - the yield a wait only for YieldWait, W3 window-minimum progress, W5 heading orbit, a yielding stuck aircraft disembarks; DeadEndPostfix1915 ends an orbiting yield, held-off-runway step, separate log budgets", yo8.Length == 0, yo8));
            rows.Add(Row("round 7: OverlapJoint1915 Stock outcome - the children's re-hold after the stock cascade never restores a zeroed joint (HoldNow1915 guard, cascade-zeroed child released for good, counted)", sc.Length == 0, sc));
        }

        static void BombRow(List<(bool, string)> rows, Missile m, string path)
        {
            var key = m.definition != null ? m.definition.jsonKey : "(no definition)";
            var so = new SerializedObject(m);
            float F(string f) { var pr = so.FindProperty("armorProperties." + f); return pr != null ? pr.floatValue : float.NaN; }
            float fa = F("fireArmor"), ft = F("fireTolerance"), ba = F("blastArmor"), pa = F("pierceArmor");
            var fz = so.FindProperty("warhead.fizzleEffect");
            string d = $"{key}: pierce {pa} blast {ba} fire {fa} fire tol {ft}, fizzle {(fz != null && fz.objectReferenceValue != null ? fz.objectReferenceValue.name : "null")} ({Path.GetFileName(path)})";
            bool cooper = key == CooperKey;
            bool clone = Mathf.Approximately(fa, 3.5f) && Mathf.Approximately(ft, 0.3f) && Mathf.Approximately(ba, 150f);
            if (cooper) rows.Add(Row("Cooper bomb prefab under the plugin key NIMROD1_cooper is the stock PAB-125 armour clone (3.5 / 0.3 / 150: what BombArmor1915 lowers to 1.0 / 0.2 / 30)", clone, d));
            else if (key.EndsWith("_no6")) rows.Add(Row("dev light bomb prefab (key *_no6) is the stock PAB-125 armour clone (3.5 / 0.3 / 150: lowered at runtime to 1.0 / 0.2 / 60)", clone, d));
            else Debug.Log("[B25H] BUGS1126 INFO family bomb " + d);
        }
    }
}
