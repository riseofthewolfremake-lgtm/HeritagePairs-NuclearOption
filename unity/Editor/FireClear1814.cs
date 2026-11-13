// Heritage Pairs 1.8.14 (offline M): no turret fires into its own aircraft.
//
// In game 1.8.13 the B-17G ball turret, aimed sideways about 10 deg down (inside its limits), put a round into its own right wing tip.
// How Nuclear Option keeps a turret off its own unit (decompiled Assembly-CSharp 0.34.6, reference only):
//   * Turret.firingCones (FiringCone: transform, coneAngle, exclusion). Turret.AimTurret (both the AI path and the manual / player
//     path) runs FiringConeChecker.VectorWithinFiringCones on the aim vector; a vector inside an exclusion cone is turned to the cone
//     edge, onTarget goes false and aimSafetyWeapon.Safety = !onTarget, and Gun.Fire returns while Safety is on. The turret keeps
//     traversing (it slides round the cone); only fire is held. Stock: turret_12.7mm_door 1 inclusion + 2 exclusion cones (60 / 70 deg),
//     AttackHelo1 1 + 1, the SideMount / rotary / grenade turrets 1 + 2, Destroyer1 / Frigate1 / AssaultCarrier1 exclusion cones of 20 deg.
//   * Turret.FixedUpdate (AI only, target farther than its radius + 50 m): Physics.Linecast 200 m along the elevation transform;
//     a hit nearer than the target holds fire. Not used by the player path, and all turrets of one WeaponStation fire together.
// So the game's own mechanism for a "no fire while the bore crosses the airframe" zone is the exclusion FiringCone. This file:
//   Sweep: every Turret of the built aircraft, posed over its traverse x elevation limits on a 1 deg grid exactly as Turret.AimTurret
//     poses it (az localEulerAngles (0, a, 0), el (-e, 0, 0)); from every muzzle a ray along the bore, 45 m, against our own colliders
//     (not the turret's own moving parts, not gear legs / wheels: retracted in flight), every visible mesh (temporary mesh colliders:
//     skin, wings, tail, nacelles, other guns; glass excluded - the guns fire through their own slots / windows) and the prop discs.
//   Fit: blocked cells dilated by 2 deg must lie inside exclusion cones, and no cone may reach a direction more than 3.5 deg from a
//     blocked one (greedy cover, radii 1-25 deg); the old exclusion cones are replaced, the inclusion cone kept. The game's checker makes
//     ONE pass over the array (a vector pushed out of a later cone can land inside an earlier one), so the exclusion set is repeated
//     (passes, same transforms) until the verification below finds nothing.
//   Verify (build + check): with the turret's real cones and the game's own FiringConeChecker, for every envelope cell: a permitted
//     direction that is blocked, or a refused direction whose nearest allowed vector is within 1 deg (onTarget) and blocked, = FIRE INTO
//     OWN AIRFRAME. Reported before (the cones as built until 1.8.13) and after, as arcs.
// Traverse / elevation limits are NOT changed here.
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class FireClear1814
    {
        public const float Step = 1f, Dilate = 2f, Allow = 3.5f, Range = 45f, OnTargetDeg = 1f;
        public const int MaxPasses = 4;
        // 1.9.0 (MSB-17/80): an opt-in bore source for turrets whose weapon is not a Gun (the lasers sweep from their aperture). Null for every
        // other aircraft (the B-25H / B-17G calls never set it): the 1.8.14-1.8.18 behaviour is unchanged.
        public static Func<Turret, Transform[]> MuzzleOverride = null;
        public const float GuardDeg = 0.45f;     // > 0.26 deg (RotateTowards' same-direction epsilon) with margin
        static readonly float[] Radii = { 25f, 18f, 13f, 9f, 6f, 4f, 2.5f, 1.5f, 1.0f };
        const BindingFlags BF = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static object G(object o, string n) { for (var t = o.GetType(); t != null; t = t.BaseType) { var f = t.GetField(n, BF); if (f != null) return f.GetValue(o); } throw new Exception("no field " + n); }
        static void S(object o, string n, object v) { for (var t = o.GetType(); t != null; t = t.BaseType) { var f = t.GetField(n, BF); if (f != null) { f.SetValue(o, v); return; } } throw new Exception("no field " + n); }

        public class Grid
        {
            public string name; public Turret turret; public Transform mount; public float tr, emin, emax; public bool full; public int na, ne;
            public Vector3[] dir; public bool[] blocked; public string[] hitBy;
            public int Idx(int ia, int ie) => ie * na + ia;
            public float A(int ia) => (full ? -180f : -tr) + ia * Step;
            public float E(int ie) => emin + ie * Step;
            public int Count => na * ne;
        }

        public class StationResult
        {
            public string name; public int cells, blocked, badBefore, badAfter, conesBefore, conesAfter, clearLostBefore, clearLostAfter, passes, repairs, guards;
            public List<string> arcsBefore = new List<string>(), arcsAfter = new List<string>(), arcsBlocked = new List<string>();
            public List<(Vector3 axisLocal, float angle)> cones = new List<(Vector3, float)>();
        }

        // ------------------------------------------------------------------ obstacles
        public class Obstacles : IDisposable
        {
            public GameObject tempRoot; public Dictionary<Collider, Transform> src = new Dictionary<Collider, Transform>(); public HashSet<Collider> propDiscs = new HashSet<Collider>();
            public int meshColliders, ownColliders;
            public void Dispose() { if (tempRoot != null) Object.DestroyImmediate(tempRoot); }
        }

        static bool GearLike(Transform t, Transform root)
        {
            for (var x = t; x != null && x != root; x = x.parent)
            {
                var n = x.name.ToLowerInvariant();
                if (n.Contains("gear") || n.Contains("wheel") || n.StartsWith("crew") || n.Contains("pilot")) return true;
                if (x.GetComponent<LandingGear>() != null) return true;
            }
            return false;
        }

        public static Obstacles BuildObstacles(GameObject root)
        {
            var ob = new Obstacles();
            foreach (var c in root.GetComponentsInChildren<Collider>(true))
            {
                if (!c.enabled || !c.gameObject.activeInHierarchy || c is WheelCollider) continue;
                if (c.isTrigger) continue;
                if (GearLike(c.transform, root.transform)) continue;
                ob.src[c] = c.transform; ob.ownColliders++;
            }
            foreach (var p in root.GetComponentsInChildren<ConstantSpeedProp>(true))
            {
                Collider dc = null; try { dc = G(p, "propDiscCollider") as Collider; } catch { }
                if (dc != null) { ob.src[dc] = dc.transform; ob.propDiscs.Add(dc); }
            }
            ob.tempRoot = new GameObject("fireclear1814_tmp");
            foreach (var r in root.GetComponentsInChildren<MeshRenderer>(true))
            {
                if (!r.enabled || !r.gameObject.activeInHierarchy) continue;
                if (GearLike(r.transform, root.transform)) continue;
                var mf = r.GetComponent<MeshFilter>(); var m = mf != null ? mf.sharedMesh : null; if (m == null) continue;
                Vector3[] vs; try { vs = m.vertices; } catch { continue; }
                if (vs == null || vs.Length == 0) continue;
                var mats = r.sharedMaterials; var tris = new List<int>();
                for (int s = 0; s < m.subMeshCount; s++)
                {
                    var mat = s < mats.Length ? mats[s] : null;
                    if (mat != null && mat.name.ToLowerInvariant().Contains("glass")) continue;
                    if (m.GetTopology(s) != MeshTopology.Triangles) continue;
                    tris.AddRange(m.GetTriangles(s));
                }
                if (tris.Count < 3) continue;
                var M = r.transform.localToWorldMatrix; var wv = new Vector3[vs.Length];
                for (int i = 0; i < vs.Length; i++) wv[i] = M.MultiplyPoint3x4(vs[i]);
                var wm = new Mesh { name = r.name + "_fc", indexFormat = wv.Length > 65000 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16 };
                wm.vertices = wv; wm.triangles = tris.ToArray(); wm.RecalculateBounds();
                var go = new GameObject(r.name + "_fc"); go.transform.SetParent(ob.tempRoot.transform, false);
                var mc = go.AddComponent<MeshCollider>(); mc.convex = false;
                try { mc.sharedMesh = wm; } catch { Object.DestroyImmediate(go); continue; }
                ob.src[mc] = r.transform; ob.meshColliders++;
            }
            Physics.SyncTransforms();
            return ob;
        }

        static readonly RaycastHit[] hitBuf = new RaycastHit[256];
        static string FirstHit(Obstacles ob, Transform own, Vector3 o, Vector3 d)
        {
            int n = Physics.RaycastNonAlloc(o, d, hitBuf, Range, ~0, QueryTriggerInteraction.Collide);
            float best = float.MaxValue; string who = null;
            for (int i = 0; i < n; i++)
            {
                var h = hitBuf[i];
                if (!ob.src.TryGetValue(h.collider, out var s)) continue;
                if (h.collider.isTrigger && !ob.propDiscs.Contains(h.collider)) continue;
                if (s == own || s.IsChildOf(own)) continue;
                if (h.distance < best) { best = h.distance; who = s.name; }
            }
            return who;
        }

        // ------------------------------------------------------------------ sweep
        public static Grid Sweep(GameObject root, Turret t, Obstacles ob)
        {
            var az = t.transform; var el = (Transform)G(t, "elevationTransform");
            var gun = G(t, "aimSafetyWeapon") as Gun;
            var mz = (MuzzleOverride != null ? MuzzleOverride(t) : null) ?? (gun != null ? (Transform[])G(gun, "muzzles") : new Transform[0]);
            float trR = (float)G(t, "traverseRange");
            var g = new Grid { name = az.parent != null ? az.parent.name.Replace("_mount", "") : az.name, turret = t, mount = az.parent };
            g.full = trR >= 180f; g.tr = g.full ? 180f : trR;
            g.emin = (float)G(t, "minElevation"); g.emax = (float)G(t, "maxElevation");
            g.na = g.full ? Mathf.RoundToInt(360f / Step) : Mathf.RoundToInt(2f * g.tr / Step) + 1;
            g.ne = Mathf.RoundToInt((g.emax - g.emin) / Step) + 1;
            g.dir = new Vector3[g.Count]; g.blocked = new bool[g.Count]; g.hitBy = new string[g.Count];
            var qa = az.localRotation; var qe = el.localRotation;
            try
            {
                for (int ie = 0; ie < g.ne; ie++)
                    for (int ia = 0; ia < g.na; ia++)
                    {
                        az.localEulerAngles = new Vector3(0f, g.A(ia), 0f);
                        el.localEulerAngles = new Vector3(-g.E(ie), 0f, 0f);
                        var d = el.forward; int k = g.Idx(ia, ie); g.dir[k] = d;
                        foreach (var m in mz)
                        {
                            var who = FirstHit(ob, az, m.position + d * 0.02f, d);
                            if (who != null) { g.blocked[k] = true; g.hitBy[k] = who; break; }
                        }
                    }
            }
            finally { az.localRotation = qa; el.localRotation = qe; }
            return g;
        }

        // ------------------------------------------------------------------ dilation + cone fit
        static IEnumerable<int> Window(Grid g, int ia, int ie, float deg)
        {
            int we = Mathf.CeilToInt(deg / Step);
            for (int je = Math.Max(0, ie - we); je <= Math.Min(g.ne - 1, ie + we); je++)
            {
                float c = Mathf.Max(Mathf.Cos(g.E(je) * Mathf.Deg2Rad), Mathf.Cos(g.E(ie) * Mathf.Deg2Rad));
                int wa = c < 0.02f ? g.na : Mathf.Min(g.na, Mathf.CeilToInt(deg / Step / Mathf.Max(c, 0.02f)) + 1);
                if (g.full && 2 * wa + 1 >= g.na) { for (int ja = 0; ja < g.na; ja++) yield return g.Idx(ja, je); continue; }
                for (int dd = -wa; dd <= wa; dd++)
                {
                    int ja = ia + dd;
                    if (g.full) ja = ((ja % g.na) + g.na) % g.na; else if (ja < 0 || ja >= g.na) continue;
                    yield return g.Idx(ja, je);
                }
            }
        }

        static bool[] Near(Grid g, float deg)
        {
            var o = new bool[g.Count]; float cmin = Mathf.Cos(deg * Mathf.Deg2Rad);
            for (int k = 0; k < g.Count; k++)
            {
                if (!g.blocked[k]) continue;
                foreach (var j in Window(g, k % g.na, k / g.na, deg)) if (!o[j] && Vector3.Dot(g.dir[k], g.dir[j]) >= cmin) o[j] = true;
            }
            return o;
        }

        public static List<(Vector3 axis, float angle)> FitCones(Grid g, out int uncovered)
        {
            var need = Near(g, Dilate); var allow = Near(g, Allow);
            var cand = Enumerable.Range(0, g.Count).Where(k => need[k]).ToList();
            var rmax = new Dictionary<int, float>();
            foreach (var c in cand)
            {
                float minBad = 999f;
                foreach (var j in Window(g, c % g.na, c / g.na, Radii[0] + 0.5f))
                    if (!allow[j]) minBad = Mathf.Min(minBad, Vector3.Angle(g.dir[c], g.dir[j]));
                float r = Radii.FirstOrDefault(x => x < minBad - 0.05f);
                if (r > 0f) rmax[c] = r;
            }
            var covered = new bool[g.Count]; var cones = new List<(Vector3, float)>();
            List<int> Cov(int c) { float r = rmax[c], cmin = Mathf.Cos(r * Mathf.Deg2Rad); return Window(g, c % g.na, c / g.na, r).Where(j => need[j] && !covered[j] && Vector3.Dot(g.dir[c], g.dir[j]) >= cmin).ToList(); }
            var gain = rmax.Keys.ToDictionary(c => c, c => Cov(c).Count);
            int left = cand.Count;
            while (left > 0 && cones.Count < 400)
            {
                int best = -1, bg = 0;
                // lazy greedy: take the stale maximum, refresh it, accept when it still beats every other stale gain
                while (true)
                {
                    best = -1; bg = 0;
                    foreach (var kv in gain) if (kv.Value > bg || (kv.Value == bg && best >= 0 && rmax[kv.Key] > rmax[best])) { best = kv.Key; bg = kv.Value; }
                    if (best < 0) break;
                    int fresh = Cov(best).Count;
                    if (fresh == bg) break;
                    gain[best] = fresh;
                }
                if (best < 0 || bg == 0) break;
                var cv = Cov(best);
                foreach (var j in cv) { covered[j] = true; left--; }
                gain[best] = 0;
                cones.Add((g.dir[best], rmax[best]));
            }
            uncovered = left;
            return cones;
        }

        // ------------------------------------------------------------------ verification with the game's own FiringConeChecker
        static bool CellOf(Grid g, Vector3 world, out int k)
        {
            k = -1; if (g.mount == null) return false;
            var v = Quaternion.Inverse(g.mount.rotation) * world.normalized;
            float e = Mathf.Asin(Mathf.Clamp(v.y, -1f, 1f)) * Mathf.Rad2Deg, a = Mathf.Atan2(v.x, v.z) * Mathf.Rad2Deg;
            if (e < g.emin - 0.5f || e > g.emax + 0.5f) return false;
            if (!g.full && Mathf.Abs(a) > g.tr + 0.5f) return false;
            int ie = Mathf.Clamp(Mathf.RoundToInt((e - g.emin) / Step), 0, g.ne - 1);
            int ia = g.full ? ((Mathf.RoundToInt((a + 180f) / Step) % g.na) + g.na) % g.na : Mathf.Clamp(Mathf.RoundToInt((a + g.tr) / Step), 0, g.na - 1);
            k = g.Idx(ia, ie); return true;
        }

        public static (int bad, int clearLost, List<int> badCells) Verify(Grid g, FiringCone[] cones) => Verify(g, cones, null);
        public static (int bad, int clearLost, List<int> badCells) Verify(Grid g, FiringCone[] cones, List<int> aimedAt)
        {
            int bad = 0, lost = 0; var cells = new List<int>();
            for (int k = 0; k < g.Count; k++)
            {
                var d = g.dir[k];
                bool permitted = FiringConeChecker.VectorWithinFiringCones(cones, d, out var fin);
                bool fire = false; int kk = k;
                if (permitted) fire = true;
                else if (Vector3.Angle(d, fin) < OnTargetDeg && CellOf(g, fin, out var kf)) { fire = true; kk = kf; }
                if (!permitted && !g.blocked[k]) lost++;
                if (fire && g.blocked[kk]) { bad++; cells.Add(k); aimedAt?.Add(kk); }
            }
            return (bad, lost, cells);
        }

        static List<int> Component(Grid g, int s0)
        {   // 4-connected blocked patch containing s0 (azimuth wraps on a full-circle turret)
            var comp = new List<int>(); if (!g.blocked[s0]) return new List<int> { s0 };
            var seen = new HashSet<int> { s0 }; var q = new Queue<int>(); q.Enqueue(s0);
            while (q.Count > 0)
            {
                int c = q.Dequeue(); comp.Add(c); int ia = c % g.na, ie = c / g.na;
                foreach (var (da, de) in new[] { (1, 0), (-1, 0), (0, 1), (0, -1) })
                {
                    int ja = ia + da, je = ie + de;
                    if (je < 0 || je >= g.ne) continue;
                    if (g.full) ja = ((ja % g.na) + g.na) % g.na; else if (ja < 0 || ja >= g.na) continue;
                    int j = g.Idx(ja, je); if (g.blocked[j] && seen.Add(j)) q.Enqueue(j);
                }
            }
            return comp;
        }

        public static List<string> Arcs(Grid g, IEnumerable<int> cellsIn, int max = 12)
        {
            var set = new HashSet<int>(cellsIn); var seen = new HashSet<int>(); var outL = new List<(int n, string s)>();
            foreach (var s0 in set)
            {
                if (seen.Contains(s0)) continue;
                var q = new Queue<int>(); q.Enqueue(s0); seen.Add(s0); var comp = new List<int>();
                while (q.Count > 0)
                {
                    int c = q.Dequeue(); comp.Add(c); int ia = c % g.na, ie = c / g.na;
                    foreach (var (da, de) in new[] { (1, 0), (-1, 0), (0, 1), (0, -1) })
                    {
                        int ja = ia + da, je = ie + de;
                        if (je < 0 || je >= g.ne) continue;
                        if (g.full) ja = ((ja % g.na) + g.na) % g.na; else if (ja < 0 || ja >= g.na) continue;
                        int j = g.Idx(ja, je); if (set.Contains(j) && seen.Add(j)) q.Enqueue(j);
                    }
                }
                var azs = comp.Select(c => g.A(c % g.na)).OrderBy(x => x).ToList(); var els = comp.Select(c => g.E(c / g.na)).ToList();
                string azTxt;
                if (g.full && azs.Count > 1)
                {   // shortest arc on the circle: the largest gap between sorted azimuths is outside it
                    float gap = 360f - (azs.Last() - azs.First()); int gi = -1;
                    for (int i = 1; i < azs.Count; i++) if (azs[i] - azs[i - 1] > gap) { gap = azs[i] - azs[i - 1]; gi = i; }
                    azTxt = gi < 0 ? $"{azs.First():F0}..{azs.Last():F0}" : $"{azs[gi]:F0}..{azs[gi - 1] + 360f:F0}";
                }
                else azTxt = $"{azs.First():F0}..{azs.Last():F0}";
                var who = comp.Where(c => g.hitBy[c] != null).GroupBy(c => g.hitBy[c]).OrderByDescending(x => x.Count()).Take(3).Select(x => x.Key);
                outL.Add((comp.Count, $"az {azTxt} el {els.Min():F0}..{els.Max():F0} ({comp.Count} cells; {string.Join("/", who)})"));
            }
            return outL.OrderByDescending(x => x.n).Take(max).Select(x => x.s).ToList();
        }

        static FiringCone[] Cones(Turret t) => ((IEnumerable)G(t, "firingCones")).Cast<FiringCone>().ToArray();

        // ------------------------------------------------------------------ build step: replace the exclusion cones, report before / after
        public static List<StationResult> Apply(GameObject root, Action<string> log, string jsonPath)
        {
            var res = new List<StationResult>();
            using (var ob = BuildObstacles(root))
            {
                log($"1.8.14 fire clearance: {ob.ownColliders} own colliders, {ob.meshColliders} mesh shapes, {ob.propDiscs.Count} prop discs; grid {Step} deg, dilate {Dilate}, allow {Allow}, range {Range} m");
                foreach (var t in root.GetComponentsInChildren<Turret>(true))
                {
                    var g = Sweep(root, t, ob);
                    var sr = new StationResult { name = g.name, cells = g.Count, blocked = g.blocked.Count(b => b) };
                    var before = Cones(t); sr.conesBefore = before.Count(c => (bool)G(c, "exclusion"));
                    var vb = Verify(g, before); sr.badBefore = vb.bad; sr.clearLostBefore = vb.clearLost; sr.arcsBefore = Arcs(g, vb.badCells);
                    sr.arcsBlocked = Arcs(g, Enumerable.Range(0, g.Count).Where(k => g.blocked[k]));
                    var fit = FitCones(g, out int unc);
                    // replace: keep the inclusion cone(s), drop old exclusion cones and their transforms
                    var keep = before.Where(c => !(bool)G(c, "exclusion")).ToList();
                    foreach (var c in before.Where(c => (bool)G(c, "exclusion"))) { var ct = G(c, "transform") as Transform; if (ct != null && ct.name.Contains("_excl")) Object.DestroyImmediate(ct.gameObject); }
                    // one transform per cone (larger cones first); VectorWithinFiringCones makes ONE pass over the array, so a vector pushed out
                    // of a later cone can land in an earlier one - the exclusion set is repeated (passes) until the game's checker finds no
                    // aim direction that fires into the airframe (same transforms, no extra objects)
                    var exc = new List<FiringCone>(); int n = 0;
                    // guard cones: Vector3.RotateTowards (used by FiringCone.VectorPermitted to push a vector out of an exclusion cone) returns
                    // MoveTowards(v, axis) when v is within ~0.26 deg of the cone AXIS (dot > 1 - 1e-5): such a vector is left ON the axis, i.e.
                    // inside the blocked patch. Every cone axis therefore lies well inside a second cone with another axis (the passes then push
                    // it out); where no fitted cone does that, a small guard cone inside the first one is added.
                    var all = fit.OrderByDescending(c => c.angle).ToList();
                    var guards = new List<(Vector3 axis, float angle)>();
                    foreach (var (ax0, r0) in all)
                    {
                        if (all.Any(o => Vector3.Angle(o.axis, ax0) > GuardDeg && Vector3.Angle(o.axis, ax0) < o.angle - GuardDeg)) continue;
                        float off = Mathf.Max(GuardDeg + 0.05f, (r0 - GuardDeg) / 2f);
                        var side = Vector3.Cross(ax0, Mathf.Abs(Vector3.Dot(ax0, Vector3.up)) > 0.9f ? Vector3.forward : Vector3.up).normalized;
                        guards.Add((Quaternion.AngleAxis(off, side) * ax0, off + GuardDeg));
                    }
                    sr.guards = guards.Count;
                    foreach (var (axis, ang) in all.Concat(guards))
                    {
                        var parent = g.mount != null ? g.mount.parent : t.transform.parent;
                        var go = new GameObject($"{g.name}_fc{n++:D2}"); go.layer = t.gameObject.layer;
                        go.transform.SetParent(parent, false);
                        go.transform.position = g.mount != null ? g.mount.position : t.transform.position;
                        go.transform.rotation = Quaternion.LookRotation(axis, Mathf.Abs(Vector3.Dot(axis, Vector3.up)) > 0.99f ? Vector3.forward : Vector3.up);
                        var fc = (FiringCone)Activator.CreateInstance(typeof(FiringCone), true);
                        S(fc, "transform", go.transform); S(fc, "coneAngle", ang); S(fc, "exclusion", true);
                        exc.Add(fc);
                        sr.cones.Add((g.mount != null ? Quaternion.Inverse(g.mount.rotation) * axis : axis, ang));
                    }
                    List<FiringCone> list = null; (int bad, int clearLost, List<int> badCells) va = (0, 0, new List<int>()); int passes = 0;
                    for (passes = 1; passes <= MaxPasses; passes++)
                    {
                        list = new List<FiringCone>(keep);
                        for (int p = 0; p < (exc.Count > 0 ? passes : 1); p++) foreach (var c in exc) { var cc = (FiringCone)Activator.CreateInstance(typeof(FiringCone), true); S(cc, "transform", G(c, "transform")); S(cc, "coneAngle", G(c, "coneAngle")); S(cc, "exclusion", true); list.Add(cc); }
                        va = Verify(g, list.ToArray());
                        if (va.bad == 0 || exc.Count == 0) break;
                    }
                    passes = Math.Min(passes, MaxPasses);
                    // repair (cascades the passes do not settle, e.g. the top turret on the fin): one more cone round the WHOLE blocked
                    // patch the gun would end up pointing at, its edge >= Dilate from every blocked cell of that patch, at the end of the list
                    int repairs = 0;
                    for (int it = 0; it < 6 && va.bad > 0 && exc.Count > 0; it++)
                    {
                        var aimed = new List<int>(); Verify(g, list.ToArray(), aimed);
                        var done = new HashSet<int>();
                        foreach (var k0 in aimed)
                        {
                            if (done.Contains(k0)) continue;
                            var comp = Component(g, k0); foreach (var c in comp) done.Add(c);
                            var ax = comp.Aggregate(Vector3.zero, (acc, c) => acc + g.dir[c]).normalized;
                            float r = Mathf.Min(15f, comp.Max(c => Vector3.Angle(ax, g.dir[c])) + Dilate);
                            var parent = g.mount != null ? g.mount.parent : t.transform.parent;
                            var go = new GameObject($"{g.name}_fc{n++:D2}"); go.layer = t.gameObject.layer;
                            go.transform.SetParent(parent, false);
                            go.transform.position = g.mount != null ? g.mount.position : t.transform.position;
                            go.transform.rotation = Quaternion.LookRotation(ax, Mathf.Abs(Vector3.Dot(ax, Vector3.up)) > 0.99f ? Vector3.forward : Vector3.up);
                            var fc = (FiringCone)Activator.CreateInstance(typeof(FiringCone), true);
                            S(fc, "transform", go.transform); S(fc, "coneAngle", r); S(fc, "exclusion", true);
                            exc.Add(fc); list.Add(fc); repairs++;
                            sr.cones.Add((g.mount != null ? Quaternion.Inverse(g.mount.rotation) * ax : ax, r));
                            // and its guard (axis quirk), after it
                            float off = Mathf.Max(GuardDeg + 0.05f, (r - GuardDeg) / 2f);
                            var gside = Vector3.Cross(ax, Mathf.Abs(Vector3.Dot(ax, Vector3.up)) > 0.9f ? Vector3.forward : Vector3.up).normalized;
                            var gax = Quaternion.AngleAxis(off, gside) * ax;
                            var go2 = new GameObject($"{g.name}_fc{n++:D2}"); go2.layer = t.gameObject.layer;
                            go2.transform.SetParent(parent, false);
                            go2.transform.position = go.transform.position;
                            go2.transform.rotation = Quaternion.LookRotation(gax, Mathf.Abs(Vector3.Dot(gax, Vector3.up)) > 0.99f ? Vector3.forward : Vector3.up);
                            var fc2 = (FiringCone)Activator.CreateInstance(typeof(FiringCone), true);
                            S(fc2, "transform", go2.transform); S(fc2, "coneAngle", off + GuardDeg); S(fc2, "exclusion", true);
                            exc.Add(fc2); list.Add(fc2); list.Add(fc); repairs++;
                        }
                        va = Verify(g, list.ToArray());
                    }
                    sr.repairs = repairs;
                    var fld = typeof(Turret).GetField("firingCones", BF); fld.SetValue(t, list.ToArray());
                    sr.conesAfter = fit.Count + guards.Count + repairs; sr.passes = exc.Count > 0 ? passes : 0;
                    sr.badAfter = va.bad; sr.clearLostAfter = va.clearLost; sr.arcsAfter = Arcs(g, va.badCells);
                    res.Add(sr);
                    log($"  fire clearance {g.name}: trav +-{g.tr} el {g.emin}..{g.emax}, {g.Count} cells, {sr.blocked} blocked by own airframe; fire into own airframe BEFORE {sr.badBefore} cells ({sr.conesBefore} excl. cones) -> AFTER {sr.badAfter} ({sr.conesAfter} cones incl. {sr.guards} guard / {sr.repairs} patch cones, {sr.passes} passes, {unc} uncovered); clear directions refused {sr.clearLostBefore} -> {sr.clearLostAfter}");
                    foreach (var a in sr.arcsBlocked) log($"    blocked {g.name}: {a}");
                    foreach (var a in sr.arcsBefore) log($"    before {g.name}: {a}");
                    foreach (var a in sr.arcsAfter) log($"    AFTER {g.name}: {a}");
                    if (jsonPath != null) WriteJson(jsonPath, g, sr, list.ToArray(), res.Count == 1);
                }
            }
            if (jsonPath != null) File.AppendAllText(jsonPath, "\n]}\n");
            return res;
        }

        // check step (on the saved prefab instance): re-sweep and verify the cones as saved
        public static (int bad, string detail) CheckInstance(GameObject inst)
        {
            int bad = 0; var det = new List<string>();
            using (var ob = BuildObstacles(inst))
                foreach (var t in inst.GetComponentsInChildren<Turret>(true))
                {
                    var g = Sweep(inst, t, ob); var v = Verify(g, Cones(t)); bad += v.bad;
                    det.Add($"{g.name} {v.bad}/{g.blocked.Count(b => b)} blocked ({Cones(t).Count(c => (bool)G(c, "exclusion"))} exclusion entries, {100f * v.clearLost / Mathf.Max(1, g.Count):F0} % refused)");
                }
            return (bad, string.Join("; ", det));
        }

        static void WriteJson(string path, Grid g, StationResult sr, FiringCone[] cones, bool first)
        {
            var sb = new System.Text.StringBuilder();
            if (first) sb.Append("{\"step\": " + Step + ", \"dilate\": " + Dilate + ", \"allow\": " + Allow + ", \"range\": " + Range + ", \"on_target_deg\": " + OnTargetDeg + ", \"stations\": [\n"); else sb.Append(",\n");
            var mr = g.mount != null ? g.mount.rotation : Quaternion.identity;
            string F(float x) => x.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
            string V3(Vector3 v) => $"[{F(v.x)}, {F(v.y)}, {F(v.z)}]";
            sb.Append($"{{\"name\": \"{g.name}\", \"full\": {(g.full ? "true" : "false")}, \"trav\": {F(g.tr)}, \"emin\": {F(g.emin)}, \"emax\": {F(g.emax)}, \"na\": {g.na}, \"ne\": {g.ne}, ");
            sb.Append($"\"mount_rot_xyzw\": [{F(mr.x)}, {F(mr.y)}, {F(mr.z)}, {F(mr.w)}], ");
            sb.Append($"\"blocked_cells\": [{string.Join(", ", Enumerable.Range(0, g.Count).Where(k => g.blocked[k]))}], ");
            sb.Append($"\"cones\": [{string.Join(", ", cones.Select(c => $"{{\"axis\": {V3(((Transform)G(c, "transform")).forward)}, \"angle\": {F((float)G(c, "coneAngle"))}, \"exclusion\": {((bool)G(c, "exclusion") ? "true" : "false")}}}"))}], ");
            sb.Append($"\"bad_before\": {sr.badBefore}, \"bad_after\": {sr.badAfter}, \"cones_before\": {sr.conesBefore}, \"passes\": {sr.passes}, \"repairs\": {sr.repairs}, \"guards\": {sr.guards}, \"clear_refused_before\": {sr.clearLostBefore}, \"clear_refused_after\": {sr.clearLostAfter}, ");
            sb.Append($"\"arcs_blocked\": [{string.Join(", ", sr.arcsBlocked.Select(a => "\"" + a.Replace("\"", "'") + "\""))}], \"arcs_before\": [{string.Join(", ", sr.arcsBefore.Select(a => "\"" + a.Replace("\"", "'") + "\""))}], \"arcs_after\": [{string.Join(", ", sr.arcsAfter.Select(a => "\"" + a.Replace("\"", "'") + "\""))}]}}");
            if (first) File.WriteAllText(path, sb.ToString()); else File.AppendAllText(path, sb.ToString());
        }
    }
}
