// Heritage Pairs 1.9.13 (final): dark seam at the upper-wing break lines of the FD-32 and Nimrod Mk I (both builders call Apply / Check
// behind their own switch SeamCove1913; nothing here runs when it is false).
//
// Why (study\seam_1913, renders of the built 1.9.13 prefab): at rest the C / outer paint edges meet within 0.0001 mm. Under load the
// joint can still open about 1 mm; through that slot the eye sees (1) the 4 mm end faces of the double skin (edge strips at x = +-0.80,
// drawn with <prefix>_structure_look = light grey), (2) the break-seam stringer stubs (short bars, about 150 mm long, 0.4-3.3 mm under
// the skin, that cross the cut: light specks in the slot) and (3) straight through the hollow wing to the sky or the far inner skin.
// (A) DarkenEndFaces: every triangle of a *_struct renderer that is (a) an end face (all three vertices within PlaneBand of a break plane),
//     or (b) a face of a bar at the cut: not submesh 0 (the inner skin, <prefix>_fabric_in), all vertices within BarSlab of the plane,
//     spanning more than PlaneBand along x and reaching the plane band (rule (a) never saw these: their vertices are 17-75 mm from the
//     plane, only the face crosses it), or (c) the end cap of such a bar (a face at one x where a (b) face ends, inside the bars' y-z box).
//     They move into a new LAST submesh drawn with the existing dark matte <prefix>_cove material. Same vertices, same triangles,
//     material[0] unchanged.
// (B) AddBand, two halves per cut so each half leaves with its own part when a panel is shot off:
//     inner half: child of wing_upper_C, from StripHalfSpan inboard of the cut to the cut, InnerDepth under the outer skin;
//     outer half: child of wing_upper_L / R, from OuterOverlap inboard of the cut (under the centre section's skin, so a gap at the cut
//     still has dark behind it) to StripHalfSpan outboard, OuterDepth under the skin (0.5 mm behind the inner half: no z-fight).
//     Both all the way round the aerofoil, dark cove material, no collider, no shadow casting. Built from the paint meshes at build time.
// Limits: does not close the gap (only the joint solver does that). The centre section's own stringer stubs (up to 75 mm outboard of
// the cut, 1.9.12 geometry) still stick out of it after a panel breaks off; they are now dark. The detached panel carries 8 mm of its
// band sticking out of its inboard end (dark). A step larger than OuterDepth (5 mm) would bring the overlap to the centre skin.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace B25HTools
{
    public static class SeamCove1913
    {
        public const float PlaneBand = 0.001f;       // m: "within 1 mm of the break plane"
        public const float BarSlab = 0.080f;         // m: a bar at the cut lies wholly within 80 mm of the plane (the stubs are 0.725-0.875)
        public const float InnerDepth = 0.0045f;     // m under the outer skin (inner skin at 4.0): inner half
        public const float OuterDepth = 0.0050f;     // m: outer half (behind the inner half where they overlap)
        public const float StripHalfSpan = 0.020f;   // m either side of the cut
        public const float OuterOverlap = 0.008f;    // m: the outer half reaches this far inboard of the cut, under the centre section
        public const float MinClear = 0.0039f, MaxClear = 0.0065f;   // m: every band vertex this far inside the paint skin
        public const string StripSuffix = "_seam1913";

        // ---------------------------------------------------------------- builder entry
        /// both cuts at x = +-xb: (A) on the three upper struct renderers, (B) inner + outer half per side. find = the builder's Find.
        public static void Apply(Transform root, Func<string, Transform> find, Material cove, List<Mesh> generated, List<string> log, float xb)
        {
            var C = find("wing_upper_C"); var cmf = C.GetComponent<MeshFilter>();
            var cx = cmf.sharedMesh.vertices.Select(v => root.InverseTransformPoint(cmf.transform.TransformPoint(v)).x).ToArray();
            if (Mathf.Abs(cx.Max() - xb) > 0.0005f || Mathf.Abs(cx.Min() + xb) > 0.0005f)
                throw new Exception($"SeamCove1913: wing_upper_C paint spans x {cx.Min():F4}..{cx.Max():F4}, expected +-{xb}");
            var planes = new[] { -xb, xb };
            foreach (var n in new[] { "wing_upper_C_struct", "wing_upper_L_struct", "wing_upper_R_struct" })
                DarkenEndFaces(root, find(n).GetComponent<MeshRenderer>(), planes, cove, log);
            foreach (var side in new[] { -1, 1 })
            {
                var O = find(side > 0 ? "wing_upper_R" : "wing_upper_L"); var omf = O.GetComponent<MeshFilter>(); string tag = side > 0 ? "_R" : "_L";
                AddBand(root, C, C.name + StripSuffix + tag, cmf, omf, side * xb, side, new[] { -StripHalfSpan, 0f }, InnerDepth, cove, generated, log);
                AddBand(root, O, O.name + StripSuffix + tag, cmf, omf, side * xb, side, new[] { -OuterOverlap, 0f, StripHalfSpan }, OuterDepth, cove, generated, log);
            }
        }

        // ---------------------------------------------------------------- (A)
        enum Kind { None, End, Bar, Cap }

        /// per triangle of submeshes [0, n): End / Bar / Cap / None (see the header). Submeshes drawn with `skip` are classed None.
        static Kind[][] Classify(Mesh me, Vector3[] w, float[] planesX, int n, Func<int, bool> skip)
        {
            var tris = Enumerable.Range(0, n).Select(s => me.GetTriangles(s)).ToArray();
            var kind = tris.Select(t => new Kind[t.Length / 3]).ToArray();
            var bars = new List<(float x0, float x1, Vector2 lo, Vector2 hi)>();
            for (int s = 0; s < n; s++)
            {
                if (skip(s)) continue;
                var t = tris[s];
                for (int i = 0; i < t.Length; i += 3)
                {
                    var P = new[] { w[t[i]], w[t[i + 1]], w[t[i + 2]] };
                    float x0 = P.Min(p => p.x), x1 = P.Max(p => p.x);
                    foreach (var xb in planesX)
                    {
                        if (P.All(p => Mathf.Abs(p.x - xb) < PlaneBand)) { kind[s][i / 3] = Kind.End; break; }
                        if (s > 0 && P.All(p => Mathf.Abs(p.x - xb) < BarSlab) && x1 - x0 > PlaneBand && x0 <= xb + PlaneBand && x1 >= xb - PlaneBand)
                        {
                            kind[s][i / 3] = Kind.Bar;
                            bars.Add((x0, x1, new Vector2(P.Min(p => p.y), P.Min(p => p.z)), new Vector2(P.Max(p => p.y), P.Max(p => p.z))));
                            break;
                        }
                    }
                }
            }
            for (int s = 1; s < n; s++)
            {
                if (skip(s)) continue;
                var t = tris[s];
                for (int i = 0; i < t.Length; i += 3)
                {
                    if (kind[s][i / 3] != Kind.None) continue;
                    var P = new[] { w[t[i]], w[t[i + 1]], w[t[i + 2]] };
                    float x0 = P.Min(p => p.x), x1 = P.Max(p => p.x);
                    if (x1 - x0 > 0.0001f || !planesX.Any(xb => Mathf.Abs(x0 - xb) < BarSlab)) continue;
                    Vector2 lo = new Vector2(P.Min(p => p.y), P.Min(p => p.z)), hi = new Vector2(P.Max(p => p.y), P.Max(p => p.z));
                    // the bar faces ending at this x and touching this face's y-z box; the cap must lie inside their union (+-1 mm)
                    var at = bars.Where(b => (Mathf.Abs(b.x0 - x0) < 0.0001f || Mathf.Abs(b.x1 - x0) < 0.0001f)
                                             && b.lo.x <= hi.x + 0.001f && b.hi.x >= lo.x - 0.001f && b.lo.y <= hi.y + 0.001f && b.hi.y >= lo.y - 0.001f).ToList();
                    if (at.Count == 0) continue;
                    float ylo = at.Min(b => b.lo.x), zlo = at.Min(b => b.lo.y), yhi = at.Max(b => b.hi.x), zhi = at.Max(b => b.hi.y);
                    if (lo.x >= ylo - 0.001f && lo.y >= zlo - 0.001f && hi.x <= yhi + 0.001f && hi.y <= zhi + 0.001f) kind[s][i / 3] = Kind.Cap;
                }
            }
            return kind;
        }

        /// moves every End / Bar / Cap triangle of r into a new last submesh drawn with cove. Returns the number of triangles moved (0: untouched).
        public static int DarkenEndFaces(Transform root, MeshRenderer r, float[] planesX, Material cove, List<string> log)
        {
            var mf = r.GetComponent<MeshFilter>(); var me = mf.sharedMesh;
            var w = me.vertices.Select(v => root.InverseTransformPoint(mf.transform.TransformPoint(v))).ToArray();
            var mats = r.sharedMaterials;
            int n = Math.Min(mats.Length, me.subMeshCount);
            for (int s = 0; s < n; s++) if (me.GetTopology(s) != MeshTopology.Triangles) throw new Exception($"SeamCove1913: {r.name} submesh {s} is not triangles");
            var kind = Classify(me, w, planesX, n, s => false);
            var keep = new List<int[]>(); var moved = new List<int>(); var per = new List<string>(); var byKind = new Dictionary<Kind, int>();
            for (int s = 0; s < n; s++)
            {
                var t = me.GetTriangles(s); var k = new List<int>(); int m0 = moved.Count;
                for (int i = 0; i < t.Length; i += 3)
                {
                    var kd = kind[s][i / 3];
                    if (kd != Kind.None) { moved.Add(t[i]); moved.Add(t[i + 1]); moved.Add(t[i + 2]); byKind[kd] = byKind.TryGetValue(kd, out int c) ? c + 1 : 1; }
                    else { k.Add(t[i]); k.Add(t[i + 1]); k.Add(t[i + 2]); }
                }
                keep.Add(k.ToArray()); per.Add($"{(mats[s] ? mats[s].name : "null")} {(moved.Count - m0) / 3}");
            }
            if (moved.Count == 0) { log.Add($"1.9.13 seam cove: {r.name} nothing at the break planes"); return 0; }
            me.subMeshCount = n + 1;
            for (int s = 0; s < n; s++) me.SetTriangles(keep[s], s, false);
            me.SetTriangles(moved.ToArray(), n, false);
            me.RecalculateBounds();
            r.sharedMaterials = mats.Take(n).Concat(new[] { cove }).ToArray();
            log.Add($"1.9.13 seam cove: {r.name} {moved.Count / 3} triangles -> submesh {n} ({cove.name}): end faces {Cnt(byKind, Kind.End)}, stub faces at the cut {Cnt(byKind, Kind.Bar)}, stub end caps {Cnt(byKind, Kind.Cap)}; from {string.Join(", ", per)}");
            return moved.Count / 3;
        }
        static int Cnt(Dictionary<Kind, int> d, Kind k) => d.TryGetValue(k, out int c) ? c : 0;

        // ---------------------------------------------------------------- (B)
        /// one band half at the break x = xb (side +1 right, -1 left): a closed loop round the aerofoil at each station dx (side-relative,
        /// negative = inboard of the cut on the centre paint cPaint, 0 = the break ring, positive = outboard on the panel paint oPaint),
        /// offset `depth` inward; parented to `parent`. Returns the new renderer.
        public static MeshRenderer AddBand(Transform root, Transform parent, string name, MeshFilter cPaint, MeshFilter oPaint, float xb, int side, float[] stations, float depth, Material cove, List<Mesh> generated, List<string> log)
        {
            var cw = World(root, cPaint); var ow = World(root, oPaint);
            var cn = Normals(root, cPaint);
            // 1. the break ring on the centre paint: unique positions on the plane, 2D (y, z) normals averaged over split vertices
            var ring = new List<Vector3>(); var rn = new List<Vector3>(); var idOf = new Dictionary<int, int>();
            for (int i = 0; i < cw.Length; i++)
            {
                if (Mathf.Abs(cw[i].x - xb) > 1e-4f) continue;
                int j = ring.FindIndex(p => (p - cw[i]).sqrMagnitude < 1e-10f);
                var n2 = new Vector3(0f, cn[i].y, cn[i].z);
                if (j < 0) { j = ring.Count; ring.Add(cw[i]); rn.Add(n2); } else rn[j] += n2;
                idOf[i] = j;
            }
            for (int j = 0; j < rn.Count; j++) rn[j] = rn[j].normalized;
            if (ring.Count < 8) throw new Exception($"SeamCove1913: only {ring.Count} break vertices at x {xb}");
            // 2. ring order from the paint edges that lie in the plane (a closed loop)
            var adj = Enumerable.Range(0, ring.Count).Select(_ => new HashSet<int>()).ToList();
            var ct = cPaint.sharedMesh.triangles;
            for (int i = 0; i < ct.Length; i += 3)
                for (int e = 0; e < 3; e++)
                {
                    int a = ct[i + e], b = ct[i + (e + 1) % 3];
                    if (idOf.TryGetValue(a, out int ja) && idOf.TryGetValue(b, out int jb) && ja != jb) { adj[ja].Add(jb); adj[jb].Add(ja); }
                }
            var order = new List<int> { 0 }; int prev = -1, cur = 0;
            while (true)
            {
                int nx = adj[cur].Where(x => x != prev).DefaultIfEmpty(-1).First();
                if (nx < 0 || nx == 0) break;
                if (order.Contains(nx)) throw new Exception("SeamCove1913: break ring is not a simple loop");
                order.Add(nx); prev = cur; cur = nx;
            }
            if (order.Count != ring.Count || adj.Any(a => a.Count != 2)) throw new Exception($"SeamCove1913: break ring walk {order.Count} of {ring.Count} (degrees {string.Join(",", adj.Select(a => a.Count).Distinct())})");
            // 3. stations along the span (spanwise paint edges from the ring: centre paint inboard, outer paint outboard)
            int K = stations.Length, N = order.Count;
            var st = new Vector3[K][]; var sn = new Vector3[K][]; var rnO = new Vector3[N];
            for (int k = 0; k < K; k++) { st[k] = new Vector3[N]; sn[k] = new Vector3[N]; }
            for (int oi = 0; oi < N; oi++)
            {
                int j = order[oi]; rnO[oi] = rn[j];
                for (int k = 0; k < K; k++)
                {
                    float dx = side * stations[k];
                    st[k][oi] = stations[k] == 0f ? ring[j] : stations[k] < 0f ? AlongSpan(ring[j], cw, cPaint.sharedMesh.triangles, dx) : AlongSpan(ring[j], ow, oPaint.sharedMesh.triangles, dx);
                }
            }
            for (int k = 0; k < K; k++)
                for (int oi = 0; oi < N; oi++)
                {   // ring normal at the cut; elsewhere from the station polygon itself, oriented like the ring normal
                    if (stations[k] == 0f) { sn[k][oi] = rnO[oi]; continue; }
                    var a = st[k][(oi + N - 1) % N]; var b = st[k][(oi + 1) % N];
                    var tg = b - a; var n2 = new Vector3(0f, -tg.z, tg.y).normalized;
                    if (Vector3.Dot(n2, rnO[oi]) < 0) n2 = -n2;
                    sn[k][oi] = Vector3.Dot(n2, rnO[oi]) > 0.5f ? n2 : rnO[oi];
                }
            // 4. offset inward along the station normal: `depth` where the skin all round is at least that far away; in the thin trailing
            //    edge (a blunt edge about 7 mm thick, where the offset from a corner would reach the other skin) the depth along the
            //    normal (0.5-8 mm, 0.25 mm steps) that keeps the point farthest from every paint face, then a y-z grid search at the corners
            var skin = Tris(cw, cPaint.sharedMesh.triangles).Concat(Tris(ow, oPaint.sharedMesh.triangles)).ToList();
            var verts = new List<Vector3>(); var nrms = new List<Vector3>(); int moved = 0; float worst = float.MaxValue;
            for (int k = 0; k < K; k++)
                for (int oi = 0; oi < N; oi++)
                {
                    var p = st[k][oi]; var n = sn[k][oi];
                    var q = p - n * depth; float c = Clearance(q, skin);
                    if (c < depth - 0.0005f)
                    {
                        float bestC = c; var bestQ = q;
                        for (float d = 0.0005f; d <= 0.008f + 1e-6f; d += 0.00025f)
                        {
                            var q2 = p - n * d; float c2 = Mathf.Min(Clearance(q2, skin), depth);
                            if (c2 > bestC + 1e-6f || (Mathf.Abs(c2 - bestC) <= 1e-6f && Mathf.Abs(d - depth) < Mathf.Abs((bestQ - p).magnitude - depth))) { bestC = c2; bestQ = q2; }
                        }
                        if (bestC < MinClear)
                        {   // trailing-edge corners (a 7 mm blunt edge closing in a wedge): search the station's y-z plane within 10 mm of the corner
                            var near = skin.Where(t => (t.a - p).sqrMagnitude < 0.0009f || (t.b - p).sqrMagnitude < 0.0009f || (t.c - p).sqrMagnitude < 0.0009f).ToList();
                            var aim = p - n * depth;
                            for (float dy = -0.010f; dy <= 0.010f + 1e-6f; dy += 0.00025f)
                                for (float dz = -0.010f; dz <= 0.010f + 1e-6f; dz += 0.00025f)
                                {
                                    var q2 = new Vector3(p.x, p.y + dy, p.z + dz);
                                    if (FirstHit(q2, Vector3.up, near) < 0f || FirstHit(q2, Vector3.down, near) < 0f) continue;   // outside the skin
                                    float c2 = Mathf.Min(Clearance(q2, near), depth);
                                    if (c2 > bestC + 1e-5f || (Mathf.Abs(c2 - bestC) <= 1e-5f && (q2 - aim).sqrMagnitude < (bestQ - aim).sqrMagnitude)) { bestC = c2; bestQ = q2; }
                                }
                            bestC = Clearance(bestQ, skin);
                        }
                        q = bestQ; c = bestC; moved++;
                    }
                    worst = Mathf.Min(worst, c);
                    verts.Add(q); nrms.Add(n);
                }
            // 5. quads, outward-facing (front face toward the skin / the slot)
            var tri = new List<int>();
            for (int k = 0; k < K - 1; k++)
                for (int oi = 0; oi < N; oi++)
                {
                    int a = k * N + oi, b = k * N + (oi + 1) % N, c = (k + 1) * N + (oi + 1) % N, d = (k + 1) * N + oi;
                    var fn = Vector3.Cross(verts[b] - verts[a], verts[c] - verts[a]);
                    if (Vector3.Dot(fn, nrms[a] + nrms[b] + nrms[c] + nrms[d]) >= 0) tri.AddRange(new[] { a, b, c, a, c, d });
                    else tri.AddRange(new[] { a, c, b, a, d, c });
                }
            var go = new GameObject(name); go.layer = parent.gameObject.layer;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = Vector3.zero; go.transform.localRotation = Quaternion.identity; go.transform.localScale = Vector3.one;
            var lv = verts.Select(v => go.transform.InverseTransformPoint(root.TransformPoint(v))).ToList();
            var ln = nrms.Select(v => go.transform.InverseTransformDirection(root.TransformDirection(v)).normalized).ToList();
            var me = new Mesh { name = name };
            me.SetVertices(lv); me.SetNormals(ln); me.SetUVs(0, Enumerable.Repeat(Vector2.zero, lv.Count).ToList());
            me.SetTriangles(tri, 0); me.RecalculateBounds();
            generated.Add(me);
            go.AddComponent<MeshFilter>().sharedMesh = me;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = cove;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; mr.receiveShadows = true;
            log.Add($"1.9.13 seam backing: {name} under {parent.name}, ring {N} vertices, x {xb + side * stations[0]:F3}..{xb + side * stations[K - 1]:F3}, depth {depth * 1000f:F1} mm ({moved} thin-edge vertices moved to the middle, nearest paint face {worst * 1000f:F2} mm), {tri.Count / 3} triangles, {cove.name}, no collider, no shadows");
            return mr;
        }

        // ---------------------------------------------------------------- check
        public class Report { public bool ok; public string msg; }

        /// (A) struct renderers: no non-cove End / Bar / Cap triangle left, cove submesh last and non-empty, material[0] unchanged.
        public static Report CheckEndFaces(Transform root, IEnumerable<MeshRenderer> structs, float[] planesX, Material cove, string firstMat, int minMoved)
        {
            bool ok = true; var parts = new List<string>();
            foreach (var r in structs)
            {
                var mf = r.GetComponent<MeshFilter>(); var me = mf.sharedMesh;
                var w = me.vertices.Select(v => root.InverseTransformPoint(mf.transform.TransformPoint(v))).ToArray();
                var mats = r.sharedMaterials; int n = Math.Min(mats.Length, me.subMeshCount);
                var kind = Classify(me, w, planesX, n, s => mats[s] == cove);
                int left = kind.Sum(k => k.Count(x => x != Kind.None)); int inCove = 0, coveSubs = 0;
                for (int s = 0; s < n; s++) if (mats[s] == cove) { coveSubs++; inCove += me.GetTriangles(s).Length / 3; }
                bool rOk = left == 0 && coveSubs == 1 && mats[mats.Length - 1] == cove && mats.Length == me.subMeshCount && inCove >= minMoved && mats[0] != null && mats[0].name == firstMat;
                ok &= rOk; parts.Add($"{r.name} {inCove} cove tris, {left} light left, mats {string.Join("/", mats.Select(m => m ? m.name : "null"))}");
            }
            return new Report { ok = ok, msg = string.Join("; ", parts) };
        }

        /// (B) one half: parent, material, no collider, no shadows, x span [xLo, xHi], every vertex MinClear-MaxClear inside the paint skin and enclosed by it.
        public static Report CheckStrip(Transform root, MeshRenderer s, Transform wantParent, MeshFilter[] paints, float xLo, float xHi, Material cove)
        {
            var mf = s.GetComponent<MeshFilter>(); var me = mf.sharedMesh;
            var w = me.vertices.Select(v => root.InverseTransformPoint(mf.transform.TransformPoint(v))).ToArray();
            var pt = paints.SelectMany(p => Tris(World(root, p), p.sharedMesh.triangles)).ToList();
            float dmin = float.MaxValue, dmax = 0f; int open = 0;
            foreach (var v in w)
            {
                float d = pt.Min(t => (ClosestOnTri(v, t.a, t.b, t.c) - v).magnitude);
                dmin = Mathf.Min(dmin, d); dmax = Mathf.Max(dmax, d);
                // enclosed: a ray up and a ray down (root frame) both meet the paint skin
                if (FirstHit(v, Vector3.up, pt) < 0f || FirstHit(v, Vector3.down, pt) < 0f) open++;
            }
            float x0 = w.Min(v => v.x), x1 = w.Max(v => v.x);
            bool ok = s.transform.parent == wantParent && s.sharedMaterials.Length == 1 && s.sharedMaterial == cove && s.GetComponents<Collider>().Length == 0 && s.GetComponentsInChildren<Collider>(true).Length == 0
                && s.shadowCastingMode == UnityEngine.Rendering.ShadowCastingMode.Off && Mathf.Abs(x0 - xLo) < 0.0002f && Mathf.Abs(x1 - xHi) < 0.0002f
                && dmin >= MinClear && dmax <= MaxClear && open == 0;
            return new Report { ok = ok, msg = $"{s.name}: parent {s.transform.parent?.name}, {me.vertexCount} v {me.triangles.Length / 3} tris, x {x0:F4}..{x1:F4}, distance to the paint skin {dmin * 1000f:F2}-{dmax * 1000f:F2} mm, not enclosed {open}, colliders {s.GetComponentsInChildren<Collider>(true).Length}, shadows {s.shadowCastingMode}, {s.sharedMaterial?.name}" };
        }

        /// the whole 1.9.13 seam row on a built instance: (A) on the three struct renderers, four band halves (inner under wing_upper_C ending
        /// at the cut, so nothing of it sticks out when the panel goes; outer under wing_upper_L / R), each checked by CheckStrip.
        public static Report CheckAll(Transform inst, Material cove, string firstMat, float xb)
        {
            var it = inst.GetComponentsInChildren<Transform>(true);
            Transform T(string n) => it.First(t => t.name == n);
            var structs = new[] { "wing_upper_C_struct", "wing_upper_L_struct", "wing_upper_R_struct" }.Select(n => T(n).GetComponent<MeshRenderer>()).ToList();
            var bands = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name.Contains(StripSuffix)).ToList();
            var C = T("wing_upper_C"); var paints = new[] { C, T("wing_upper_L"), T("wing_upper_R") }.Select(t => t.GetComponent<MeshFilter>()).ToArray();
            var a = CheckEndFaces(inst, structs, new[] { -xb, xb }, cove, firstMat, 70);
            bool ok = cove != null && a.ok && bands.Count == 4; var msg = new List<string> { a.msg };
            foreach (var side in new[] { -1, 1 })
            {
                string tag = side > 0 ? "_R" : "_L"; var O = T(side > 0 ? "wing_upper_R" : "wing_upper_L");
                var bi = bands.FirstOrDefault(r => r.name == C.name + StripSuffix + tag); var bo = bands.FirstOrDefault(r => r.name == O.name + StripSuffix + tag);
                float x = side * xb;
                float iLo = Mathf.Min(x - side * StripHalfSpan, x), iHi = Mathf.Max(x - side * StripHalfSpan, x);
                float oLo = Mathf.Min(x - side * OuterOverlap, x + side * StripHalfSpan), oHi = Mathf.Max(x - side * OuterOverlap, x + side * StripHalfSpan);
                var ri = bi ? CheckStrip(inst, bi, C, paints, iLo, iHi, cove) : new Report { msg = "no inner band " + tag };
                var ro = bo ? CheckStrip(inst, bo, O, paints, oLo, oHi, cove) : new Report { msg = "no outer band " + tag };
                ok &= ri.ok && ro.ok; msg.Add(ri.msg); msg.Add(ro.msg);
            }
            return new Report { ok = ok, msg = string.Join(" | ", msg) };
        }

        // ---------------------------------------------------------------- geometry
        public struct T3 { public Vector3 a, b, c; }
        static Vector3[] World(Transform root, MeshFilter mf) => mf.sharedMesh.vertices.Select(v => root.InverseTransformPoint(mf.transform.TransformPoint(v))).ToArray();
        static Vector3[] Normals(Transform root, MeshFilter mf) => mf.sharedMesh.normals.Select(n => root.InverseTransformDirection(mf.transform.TransformDirection(n))).ToArray();
        static List<T3> Tris(Vector3[] w, int[] t) { var l = new List<T3>(); for (int i = 0; i < t.Length; i += 3) l.Add(new T3 { a = w[t[i]], b = w[t[i + 1]], c = w[t[i + 2]] }); return l; }

        /// the point dx along the span from ring point p, following the paint mesh edge that leaves p most nearly spanwise in that direction
        static Vector3 AlongSpan(Vector3 p, Vector3[] w, int[] t, float dx)
        {
            Vector3 best = Vector3.zero; float bestRatio = float.MaxValue; int found = 0;
            for (int i = 0; i < t.Length; i += 3)
                for (int e = 0; e < 3; e++)
                {
                    var a = w[t[i + e]];
                    if ((a - p).sqrMagnitude > 1e-9f) continue;
                    for (int f = 1; f < 3; f++)
                    {
                        var b = w[t[i + (e + f) % 3]]; var d = b - a;
                        if (d.x * dx <= 1e-6f) continue;
                        float ratio = new Vector2(d.y, d.z).magnitude / Mathf.Abs(d.x);
                        if (ratio < bestRatio) { bestRatio = ratio; best = d; found++; }
                    }
                }
            if (found == 0) throw new Exception($"SeamCove1913: no spanwise edge from {p.ToString("F4")} toward dx {dx}");
            return p + best * (dx / best.x);
        }

        static float Clearance(Vector3 v, List<T3> tris) { float m = float.MaxValue; foreach (var t in tris) m = Mathf.Min(m, (ClosestOnTri(v, t.a, t.b, t.c) - v).magnitude); return m; }

        static float FirstHit(Vector3 o, Vector3 d, List<T3> tris)
        {
            float best = -1f;
            foreach (var t in tris)
            {
                var e1 = t.b - t.a; var e2 = t.c - t.a; var p = Vector3.Cross(d, e2); float det = Vector3.Dot(e1, p);
                if (Mathf.Abs(det) < 1e-14f) continue;
                float inv = 1f / det; var s = o - t.a; float u = Vector3.Dot(s, p) * inv; if (u < 0f || u > 1f) continue;
                var q = Vector3.Cross(s, e1); float v = Vector3.Dot(d, q) * inv; if (v < 0f || u + v > 1f) continue;
                float h = Vector3.Dot(e2, q) * inv;
                if (h > 1e-6f && (best < 0f || h < best)) best = h;
            }
            return best;
        }

        static Vector3 ClosestOnTri(Vector3 p, Vector3 a, Vector3 b, Vector3 c)
        {
            var ab = b - a; var ac = c - a; var ap = p - a;
            float d1 = Vector3.Dot(ab, ap), d2 = Vector3.Dot(ac, ap); if (d1 <= 0f && d2 <= 0f) return a;
            var bp = p - b; float d3 = Vector3.Dot(ab, bp), d4 = Vector3.Dot(ac, bp); if (d3 >= 0f && d4 <= d3) return b;
            float vc = d1 * d4 - d3 * d2; if (vc <= 0f && d1 >= 0f && d3 <= 0f) return a + ab * (d1 / (d1 - d3));
            var cp = p - c; float d5 = Vector3.Dot(ab, cp), d6 = Vector3.Dot(ac, cp); if (d6 >= 0f && d5 <= d6) return c;
            float vb = d5 * d2 - d1 * d6; if (vb <= 0f && d2 >= 0f && d6 <= 0f) return a + ac * (d2 / (d2 - d6));
            float va = d3 * d6 - d5 * d4; if (va <= 0f && (d4 - d3) >= 0f && (d5 - d6) >= 0f) return b + (c - b) * ((d4 - d3) / ((d4 - d3) + (d5 - d6)));
            float den = 1f / (va + vb + vc); return a + ab * (vb * den) + ac * (vc * den);
        }
    }
}
