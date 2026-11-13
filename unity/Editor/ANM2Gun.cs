// Heritage Pairs 1.8.13 (offline L): our own AN/M2 .50 on the B-25H and B-17G gun slots, replacing the stock UH-90 door-gun barrel
// placeholder (Mesh/50cal_doorGun_barrel_PLACEHOLDER + utilityHelo1_attachments material: its bore sat 0.04-0.22 m off its origin and its
// mount block clipped the turrets / windows).
//
// Source (round 2): assets/model_anm2/anm2_mesh.json + anm2_b.png (albedo) + anm2_n.png (normal) + anm2_jacket.png (perforated jacket,
// alpha cut-out) from blender/anm2/anm2_model.py: flex_L / flex_R (hand-held: charging lever + wooden knob, sights), turret_L / turret_R
// (short slide, buffer stub), each L + baked mirror R, and grips; Unity gun frame, origin ON THE BORE at the trunnion, +Z = fire, tip at
// spec.tip_z (0.725).
// Placement: per slot from the War Thunder reference (Mounts: height + distance ahead of the elevation pivot; across = the slot's own x,
// where our housings' slots / ports are), identity rotation under the slot, the muzzle Transform moved exactly to the bore tip. Muzzle
// count, Gun, Turret, WeaponInfo, rounds, sounds and particles are not touched; the guns stay children of the elevation objects.
//
// Variants (who gets what): twins = gun_L on the slot left of the bore pair, gun_R on the right (feed / charging handle outboard);
// powered turrets (B-17G chin / top / ball, B-25H dorsal) no grips; hand-held positions (tails, waists, cheeks, radio) with grips;
// single hand-held guns feed from the side of the ammunition box on the fuselage wall: waist L -> gun_R (its right = forward wall box),
// waist R -> gun_L, cheek L -> gun_L, cheek R -> gun_R (outboard nose-wall boxes), radio -> gun_R.
//
// ANM2Gun.Clearance: sweeps every Turret over its traverse / elevation limits and reports the minimum distance from the gun surfaces to the
// aircraft's skin / glass / structure meshes (everything except the turret's own moving parts, crew figures, cockpit-layer copies and
// other guns) and whether any gun edge passes through them (= clips).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class ANM2Gun
    {
        public const string Src = @"C:\Users\User\Nuclear Option B-25\assets\model_anm2";
        /// round 2: flexible body (hand-held: charging lever + wooden knob, sights) and turret body (short slide, buffer-tube stub), each
        /// left-feed (L) and its baked mirror (R); grips separate. Materials: [0] steel / wood / dark (albedo + normal map), [1] the perforated
        /// barrel jacket (alpha cut-out, both faces: the barrel shows through the holes).
        public class Set { public Mesh FL, FR, TL, TR, Grips, GripsTwin; public Material[] Mats; public float TipZ; }
        static readonly HashSet<string> HandHeld = new HashSet<string> { "tail", "cheek_L", "cheek_R", "waist_L", "waist_R", "radio",   // B-17G stations
                                                                         "gun_tail_L", "gun_tail_R", "gun_waist_L", "gun_waist_R" };          // B-25H slots
        static readonly HashSet<string> TwinLeverOut = new HashSet<string> { "gun_tail_L", "gun_tail_R" };
        // r3: the B-25H tail guns are 0.17 m apart - one shared spade-grip set centred between them (two sets overlapped on the centre line)
        static readonly HashSet<string> TwinSharedGrips = new HashSet<string> { "gun_tail_L", "gun_tail_R" };
        static readonly Dictionary<string, bool> SingleRight = new Dictionary<string, bool> {
            { "waist_L", true }, { "waist_R", false }, { "cheek_L", false }, { "cheek_R", true }, { "radio", true },                   // B-17G
            { "gun_waist_L", true }, { "gun_waist_R", false } };                                                                     // B-25H

        public static Set Load(string folder, string prefix)
        {
            var spec = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(Path.Combine(Src, "anm2_mesh.json")));
            var dir = folder + "/ANM2";
            if (!AssetDatabase.IsValidFolder(dir)) AssetDatabase.CreateFolder(folder, "ANM2");
            var s = new Set { TipZ = (float)spec["spec"]["tip_z"] };
            s.FL = MakeMesh(spec["flex_L"], prefix + "_anm2_flex_L", dir); s.FR = MakeMesh(spec["flex_R"], prefix + "_anm2_flex_R", dir);
            s.TL = MakeMesh(spec["turret_L"], prefix + "_anm2_turret_L", dir); s.TR = MakeMesh(spec["turret_R"], prefix + "_anm2_turret_R", dir);
            s.Grips = MakeMesh(spec["grips"], prefix + "_anm2_grips", dir);
            s.GripsTwin = MakeMesh(spec["grips_twin"], prefix + "_anm2_twin_grips", dir);     // r3: one shared set for a close twin
            Texture2D Tex(string key, bool normal, int max)
            {
                var dst = $"{dir}/{prefix}_{(string)spec["spec"][key]}";
                File.Copy(Path.Combine(Src, (string)spec["spec"][key]), dst, true);
                AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
                var ti = (TextureImporter)AssetImporter.GetAtPath(dst);
                if (normal) ti.textureType = TextureImporterType.NormalMap; else ti.sRGBTexture = true;
                ti.mipmapEnabled = true; ti.maxTextureSize = max; ti.alphaIsTransparency = false; ti.SaveAndReimport();
                return AssetDatabase.LoadAssetAtPath<Texture2D>(dst);
            }
            var tb = Tex("tex", false, 1024); var tn = Tex("normal_tex", true, 1024); var tj = Tex("jacket_tex", false, 512);
            var m = new Material(Shader.Find("Universal Render Pipeline/Lit")) { name = prefix + "_anm2" };
            m.SetTexture("_BaseMap", tb); m.SetTexture("_MainTex", tb); m.SetColor("_BaseColor", Color.white); m.SetColor("_Color", Color.white);
            m.SetTexture("_BumpMap", tn); m.SetFloat("_BumpScale", 1f); m.EnableKeyword("_NORMALMAP");
            m.SetFloat("_Metallic", 0.25f); m.SetFloat("_Smoothness", 0.35f);       // parkerized steel: matte (stock door gun: metallic 0, smoothness 0.45)
            AssetDatabase.CreateAsset(m, $"{dir}/{m.name}.mat");
            var j = new Material(Shader.Find("Universal Render Pipeline/Lit")) { name = prefix + "_anm2_jacket" };
            j.SetTexture("_BaseMap", tj); j.SetTexture("_MainTex", tj); j.SetColor("_BaseColor", Color.white); j.SetColor("_Color", Color.white);
            j.SetFloat("_Metallic", 0.25f); j.SetFloat("_Smoothness", 0.35f);
            j.SetFloat("_AlphaClip", 1f); j.SetFloat("_Cutoff", 0.5f); j.EnableKeyword("_ALPHATEST_ON"); j.renderQueue = (int)UnityEngine.Rendering.RenderQueue.AlphaTest;
            j.SetFloat("_Cull", 0f); j.doubleSidedGI = true;                         // both faces: the inside of the jacket shows through the holes
            AssetDatabase.CreateAsset(j, $"{dir}/{j.name}.mat");
            s.Mats = new[] { m, j };
            return s;
        }

        static Mesh MakeMesh(Newtonsoft.Json.Linq.JToken j, string name, string dir)
        {
            var v = j["v"].Select(p => new Vector3((float)p[0], (float)p[1], (float)p[2])).ToArray();
            var n = j["n"].Select(p => new Vector3((float)p[0], (float)p[1], (float)p[2])).ToArray();
            var uv = j["uv"].Select(p => new Vector2((float)p[0], (float)p[1])).ToArray();
            var mesh = new Mesh { name = name };
            mesh.vertices = v; mesh.normals = n; mesh.uv = uv;
            var tj = j["t_jacket"] != null ? j["t_jacket"].Select(t => (int)t).ToArray() : new int[0];
            mesh.subMeshCount = tj.Length > 0 ? 2 : 1;
            mesh.SetTriangles(j["t"].Select(t => (int)t).ToArray(), 0);
            if (tj.Length > 0) mesh.SetTriangles(tj, 1);
            mesh.RecalculateBounds(); mesh.RecalculateTangents();
            AssetDatabase.CreateAsset(mesh, $"{dir}/{name}.asset");
            return mesh;
        }

        /// key: the B-17G station object name (e.g. "waist_L") or the B-25H slot name (e.g. "gun_waist_L"); twin = more than one gun on the turret
        public static (bool right, bool grips) Variant(string key, Transform slot, Transform el, bool twin)
        {
            bool grips = HandHeld.Contains(key);
            bool right = twin ? el.InverseTransformPoint(slot.position).x > 0f : (SingleRight.TryGetValue(key, out var r) && r);
            if (TwinLeverOut.Contains(key)) right = !right;     // r2: B-25H tail guns are 0.20 m apart: charging levers outboard (inboard they met)
            return (right, grips);
        }

        public const float TrunnionAhead = 0.10f;   // fallback only (a slot missing from Mounts)
        // round 2: every gun placed from the reference. Trunnion (gun origin) in the ELEVATION frame (Unity: x right, y up, z = rest aim) =
        // the War Thunder B-17G gun's muzzle - 0.725 m on its bore, measured from our elevation pivot in a frame-free way (along the bore d, the
        // gun's right x, its up y; blender/anm2/measure_wt_mounts.py on b17g.blend, WT -> ours (-x K, z K, y K), K 31.62 / 31.258). The WT
        // top / ball turrets face aft in the export and the cheek guns sit 11-14 deg off our rest aim: only d / x / y are used, our rest aim
        // is kept. Cheeks: the two WT cheek pivots disagree with ours (x 0.17 on the left) -> x 0, d = the mean -0.06. The B-25H has no
        // reference guns: dorsal as the B-17G top (Bendix / Sperry: receivers round the pivot inside the dome), waist / tail as the B-17G waist.
        // r4c: lateral trims on top of the slot's x (el-local, + = the gun's right)
        public static readonly Dictionary<string, float> MountsDx = new Dictionary<string, float> { { "cheek_R_gun0", -0.010f } };
        // 1.8.17 (B-17G nose to the reference): the cheek guns sit in the K-5 sockets of the projecting cheek frames - the bore runs through
        // the elevation pivot (= the socket centre on the frame's front face), so the jacket crosses the face at the hole centre at every
        // pose; receiver / grips 0.25 m inside as before. Overrides the r4c heights / trim for those two slots. False = the 1.8.13 placement.
        public const bool Nose1817 = true;
        public static readonly Dictionary<string, Vector3> MountsNose1817 = new Dictionary<string, Vector3>
        {
            { "cheek_L_gun0", new Vector3(0f, 0f, -0.250f) }, { "cheek_R_gun0", new Vector3(0f, 0f, -0.250f) },
        };
        public static readonly Dictionary<string, Vector3> Mounts = new Dictionary<string, Vector3>
        {
            { "chin_gun0", new Vector3(-0.234f, 0.035f, 0.330f) }, { "chin_gun1", new Vector3(0.234f, 0.035f, 0.330f) },   // WT y -0.008 d 0.288: our drum is 0.40 deep at the gun line, receiver + buffer fit 4 cm further forward; bore 4 cm up (r3) keeps the receiver rears in the drum at +20 deg and the block off the slot foot at -26
            { "top_gun0", new Vector3(-0.285f, -0.014f, 0.260f) }, { "top_gun1", new Vector3(0.285f, -0.014f, 0.260f) },     // WT 0.292; 0.26 with the guns at +-0.15 under the 6 cm taller dome: front inside at 85 deg, rear inside at 0
            { "ball_gun0", new Vector3(-0.354f, -0.042f, 0.421f) }, { "ball_gun1", new Vector3(0.354f, -0.042f, 0.421f) },
            { "tail_gun0", new Vector3(-0.095f, 0.006f, 0.380f) }, { "tail_gun1", new Vector3(0.095f, 0.006f, 0.380f) },   // WT 0.575: our accepted cover is 0.45 deep, receivers stay inside it
            { "radio_gun0", new Vector3(0f, -0.037f, -0.174f) },
            { "waist_L_gun0", new Vector3(0f, -0.010f, 0.143f) }, { "waist_R_gun0", new Vector3(0f, -0.011f, 0.150f) },
            { "cheek_L_gun0", new Vector3(0f, -0.020f, -0.250f) }, { "cheek_R_gun0", new Vector3(0f, -0.040f, -0.250f) },   // r4c: the right gun 2 cm lower and 1 cm inboard (MountsDx): between the skin above (-20) and below (+20)
              // r3: receiver 0.25 inside the window socket (nose floor 7 cm lower; at -0.06 it touched the glazing; deeper = more inboard traverse but lower grips at +20)
            { "gun_turret_L", new Vector3(-0.130f, -0.010f, 0.330f) }, { "gun_turret_R", new Vector3(0.130f, -0.010f, 0.330f) },   // B-25H dorsal (pivot 4 cm over the dome centre in r2): front under the dome top at 85 deg, rear inside the dome at 0
            { "gun_tail_L", new Vector3(-0.100f, 0.000f, 0.220f) }, { "gun_tail_R", new Vector3(0.100f, 0.000f, 0.220f) },   // B-25H tail: grips clear of the narrow fuselage at +-20 deg
            { "gun_waist_L", new Vector3(0f, 0f, -0.120f) }, { "gun_waist_R", new Vector3(0f, 0f, -0.120f) },   // ball socket = the pivot: jacket through it, receiver inboard
        };

        /// put the gun (+ grips) on the slot: trunnion on the bore line TrunnionAhead ahead of the elevation pivot (the receiver and grips
        /// behind it, inside the turret / cabin, as on the real mounts), the muzzle Transform moved to the tip; removes any mesh on the slot
        public static Transform Place(Set s, Transform slot, Transform muzzle, Transform el, bool right, bool grips)
        {
            var mf = slot.GetComponent<MeshFilter>(); var mr = slot.GetComponent<MeshRenderer>();
            if (mr != null) Object.DestroyImmediate(mr);
            if (mf != null) Object.DestroyImmediate(mf);
            var go = new GameObject(slot.name + "_anm2" + (right ? "R" : "L")) { layer = slot.gameObject.layer };
            go.transform.SetParent(slot, false);
            Vector3 tl;                                                          // trunnion in the slot frame
            Vector3 m;
            bool nose17 = Nose1817 && MountsNose1817.TryGetValue(slot.name, out m);
            if (nose17 || Mounts.TryGetValue(slot.name, out m))
            {   // round 2: x (across) = the slot's own x - our housings' slots / ports are cut there; the reference gives the height (y) and how
                // far ahead of the elevation pivot the trunnion sits (z); a turret facing aft (B-25H tail) has its "L" slot on el's +x
                m.x = el.InverseTransformPoint(slot.position).x + (!nose17 && MountsDx.TryGetValue(slot.name, out var dx_) ? dx_ : 0f);
                tl = slot.InverseTransformPoint(el.TransformPoint(m));
            }
            else { var ml = slot.InverseTransformPoint(muzzle.position); tl = new Vector3(ml.x, ml.y, slot.InverseTransformPoint(el.position).z + TrunnionAhead); }
            go.transform.localPosition = tl; go.transform.localRotation = Quaternion.identity; go.transform.localScale = Vector3.one;
            muzzle.position = slot.TransformPoint(tl + new Vector3(0f, 0f, s.TipZ));    // the muzzle exactly at the bore tip
            var body = grips ? (right ? s.FR : s.FL) : (right ? s.TR : s.TL);           // hand-held = flexible gun, powered turret = turret gun
            go.AddComponent<MeshFilter>().sharedMesh = body; go.AddComponent<MeshRenderer>().sharedMaterials = body.subMeshCount > 1 ? s.Mats : new[] { s.Mats[0] };
            if (grips)
            {
                bool shared = TwinSharedGrips.Contains(slot.name);
                float ex = el.InverseTransformPoint(go.transform.position).x;
                if (!shared || ex < 0f)          // shared: the set rides on the gun left of the centre line, offset to the centre line
                {
                    var g = new GameObject(slot.name + "_grips") { layer = slot.gameObject.layer };
                    g.transform.SetParent(go.transform, false);
                    if (shared) g.transform.localPosition = go.transform.InverseTransformVector(el.TransformVector(new Vector3(-ex, 0f, 0f)));
                    g.AddComponent<MeshFilter>().sharedMesh = shared ? s.GripsTwin : s.Grips; g.AddComponent<MeshRenderer>().sharedMaterial = s.Mats[0];
                }
            }
            return go.transform;
        }

        // ============================================================================================ clearance sweep
        public class Row { public string turret; public float minRest, minSweep, twin; public int clipPoses, poses; public string worstPose, worstAgainst, restAgainst; public List<string> clips = new List<string>(); public Dictionary<string, int> clipBy = new Dictionary<string, int>(); public int glassPoses;
            public Dictionary<string, Bounds> hitBox = new Dictionary<string, Bounds>(); public Dictionary<string, Vector2> hitZ = new Dictionary<string, Vector2>(); public string map = ""; }   // r2: where it clips (world box per obstacle, gun-frame z range) + az x el map
        static string Zone(float z) => GunTag != "_anm2" ? "gun" : z > 0.02f ? "barrel" : z > -0.645f ? "receiver" : "grips";

        class TriGrid
        {
            public readonly List<Vector3> a = new List<Vector3>(), b = new List<Vector3>(), c = new List<Vector3>(); public readonly List<string> owner = new List<string>();
            readonly Dictionary<long, List<int>> cells = new Dictionary<long, List<int>>(); const float Cell = 0.06f;
            static long Key(int x, int y, int z) => ((long)(x + 100000) * 200003L + (y + 100000)) * 200003L + (z + 100000);
            public void Add(Vector3 p, Vector3 q, Vector3 r, string who)
            {
                int i = a.Count; a.Add(p); b.Add(q); c.Add(r); owner.Add(who);
                var lo = Vector3.Min(p, Vector3.Min(q, r)); var hi = Vector3.Max(p, Vector3.Max(q, r));
                for (int x = Mathf.FloorToInt(lo.x / Cell); x <= Mathf.FloorToInt(hi.x / Cell); x++)
                    for (int y = Mathf.FloorToInt(lo.y / Cell); y <= Mathf.FloorToInt(hi.y / Cell); y++)
                        for (int z = Mathf.FloorToInt(lo.z / Cell); z <= Mathf.FloorToInt(hi.z / Cell); z++)
                        { var k = Key(x, y, z); if (!cells.TryGetValue(k, out var l)) cells[k] = l = new List<int>(); l.Add(i); }
            }
            /// nearest triangle distance to p (searching the 27 cells round p; beyond that returns >= Cell)
            public float Nearest(Vector3 p, out int best)
            {
                best = -1; float d = Cell;
                int cx = Mathf.FloorToInt(p.x / Cell), cy = Mathf.FloorToInt(p.y / Cell), cz = Mathf.FloorToInt(p.z / Cell);
                for (int x = cx - 1; x <= cx + 1; x++) for (int y = cy - 1; y <= cy + 1; y++) for (int z = cz - 1; z <= cz + 1; z++)
                        if (cells.TryGetValue(Key(x, y, z), out var l))
                            foreach (var i in l) { float e = (ClosestOnTri(p, a[i], b[i], c[i]) - p).magnitude; if (e < d) { d = e; best = i; } }
                return d;
            }
        }

        static Vector3 ClosestOnTri(Vector3 p, Vector3 a, Vector3 b, Vector3 c)
        {   // Ericson, Real-Time Collision Detection 5.1.5
            Vector3 ab = b - a, ac = c - a, ap = p - a; float d1 = Vector3.Dot(ab, ap), d2 = Vector3.Dot(ac, ap);
            if (d1 <= 0f && d2 <= 0f) return a;
            Vector3 bp = p - b; float d3 = Vector3.Dot(ab, bp), d4 = Vector3.Dot(ac, bp);
            if (d3 >= 0f && d4 <= d3) return b;
            float vc = d1 * d4 - d3 * d2; if (vc <= 0f && d1 >= 0f && d3 <= 0f) return a + ab * (d1 / (d1 - d3));
            Vector3 cp = p - c; float d5 = Vector3.Dot(ab, cp), d6 = Vector3.Dot(ac, cp);
            if (d6 >= 0f && d5 <= d6) return c;
            float vb = d5 * d2 - d1 * d6; if (vb <= 0f && d2 >= 0f && d6 <= 0f) return a + ac * (d2 / (d2 - d6));
            float va = d3 * d6 - d5 * d4; if (va <= 0f && (d4 - d3) >= 0f && (d5 - d6) >= 0f) return b + (c - b) * ((d4 - d3) / ((d4 - d3) + (d5 - d6)));
            float den = 1f / (va + vb + vc); return a + ab * (vb * den) + ac * (vc * den);
        }

        /// surface samples of a mesh in its local frame: vertices + points along every triangle edge every 'step' m
        static List<Vector3> Samples(Mesh m, float step)
        {
            var v = m.vertices; var t = m.triangles; var o = new List<Vector3>(v);
            for (int k = 0; k < t.Length; k += 3)
                for (int e = 0; e < 3; e++)
                {
                    var p = v[t[k + e]]; var q = v[t[k + (e + 1) % 3]]; int n = Mathf.CeilToInt((q - p).magnitude / step);
                    for (int i = 1; i < n; i++) o.Add(Vector3.Lerp(p, q, (float)i / n));
                }
            return o;
        }

        public static string GunTag = "_anm2";   // which gun meshes the sweep follows ("50cal_doorGun" = the 1.8.12 stock door gun, baseline)
        public const float ClipDist = 0.004f;     // a sampled surface point closer than 4 mm to an obstacle triangle = touching / passing through

        /// sweep every Turret of the instance; obstacles = every MeshRenderer that is not under the turret's elevation object, not the
        /// turret's own guns, not a crew figure, not a cockpit-layer (3) copy, not a prop disc / effect
        public static List<Row> Clearance(GameObject inst, Func<string, bool> obstacleFilter = null)
        {
            var rows = new List<Row>();
            var turretsAll = inst.GetComponentsInChildren<Turret>(true);
            var gunMeshes = inst.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh != null && f.sharedMesh.name.Contains(GunTag)).ToList();
            foreach (var tr in turretsAll)
            {
                var az = tr.transform; var el = (Transform)Get(tr, "elevationTransform"); if (el == null) continue;
                var row = new Row { turret = az.parent != null ? az.parent.name : az.name };
                var guns = gunMeshes.Where(f => f.transform.IsChildOf(el)).ToList();
                var bodies = guns.Where(f => !f.sharedMesh.name.EndsWith("grips")).ToList();
                if (guns.Count == 0) continue;
                // obstacles in world space at rest (az / el at identity); the az-only bodies move with the traverse: they are re-added per pose
                az.localRotation = Quaternion.identity; el.localRotation = Quaternion.identity;
                var statics = new TriGrid(); var glassG = new TriGrid(); var azBodies = new List<MeshFilter>();
                var centre = el.position; float reach = 2.2f;
                foreach (var mr in inst.GetComponentsInChildren<MeshRenderer>(true))
                {
                    var f = mr.GetComponent<MeshFilter>(); if (f == null || f.sharedMesh == null || !mr.enabled && mr.gameObject.layer == 3) continue;
                    var t = mr.transform;
                    if (t.IsChildOf(el) || mr.gameObject.layer == 3 || f.sharedMesh.name.Contains(GunTag) || t.GetComponentInParent<Pilot>() != null) continue;
                    var nm = t.name.ToLowerInvariant();
                    if (nm.Contains("propdisc") || nm.Contains("prop_disc") || nm.Contains("muzzle") || nm.Contains("_cone") || nm.Contains("light") || nm.Contains("flare")) continue;
                    if (obstacleFilter != null && !obstacleFilter(t.name)) continue;
                    if (!f.sharedMesh.bounds.size.Equals(Vector3.zero))
                    {
                        var wb = new Bounds(t.TransformPoint(f.sharedMesh.bounds.center), Vector3.zero);
                        foreach (var corner in Corners(f.sharedMesh.bounds)) wb.Encapsulate(t.TransformPoint(corner));
                        if (wb.SqrDistance(centre) > reach * reach) continue;
                    }
                    if (t.IsChildOf(az)) { azBodies.Add(f); continue; }
                    AddMesh(statics, f, null, 1); AddMesh(glassG, f, null, 2);
                }
                var samples = guns.Select(g => (g, Samples(g.sharedMesh, 0.01f))).ToList();
                // twin partner clearance at rest (static relative to each other)
                row.twin = float.PositiveInfinity;
                if (bodies.Count >= 2)
                {
                    var pg = new TriGrid(); AddMesh(pg, bodies[1], null);
                    foreach (var p in Samples(bodies[0].sharedMesh, 0.01f)) { float d = pg.Nearest(bodies[0].transform.TransformPoint(p), out _); row.twin = Mathf.Min(row.twin, d); }
                }
                float trav = Mathf.Min((float)Get(tr, "traverseRange"), 180f), e0 = (float)Get(tr, "minElevation"), e1 = (float)Get(tr, "maxElevation");
                bool full = (float)Get(tr, "traverseRange") >= 180f;
                var azs = new List<float>(); if (full) for (float a = 0f; a < 360f; a += 15f) azs.Add(a); else for (int i = 0; i <= 6; i++) azs.Add(-trav + 2f * trav * i / 6f);
                var els = new List<float>(); for (int i = 0; i <= 5; i++) els.Add(e0 + (e1 - e0) * i / 5f);
                if (e0 < 0f && e1 > 0f && !els.Contains(0f)) { els.Add(0f); els.Sort(); }      // r2: the rest pose is always in the grid
                var grid = new Dictionary<(float, float), bool>();
                row.minRest = Pose(tr, az, el, 0f, 0f, statics, glassG, azBodies, samples, out var rw, out var rz, out var rgl); row.minSweep = row.minRest; row.worstPose = "rest"; row.worstAgainst = rw + " / " + Zone(rz); row.restAgainst = row.worstAgainst;
                foreach (var a in azs) foreach (var e in els)
                    {
                        hits.Clear();
                        float d = Pose(tr, az, el, a, e, statics, glassG, azBodies, samples, out var who, out var zone, out var gl); row.poses++;
                        grid[(a, e)] = d < ClipDist;
                        foreach (var (hw, hp, hz) in hits)
                        {
                            var lp = inst.transform.InverseTransformDirection(hp - el.position);     // from the elevation pivot, aircraft axes (x right, y up, z fwd)
                            if (row.hitBox.TryGetValue(hw, out var bb)) { bb.Encapsulate(lp); row.hitBox[hw] = bb; row.hitZ[hw] = new Vector2(Mathf.Min(row.hitZ[hw].x, hz), Mathf.Max(row.hitZ[hw].y, hz)); }
                            else { row.hitBox[hw] = new Bounds(lp, Vector3.zero); row.hitZ[hw] = new Vector2(hz, hz); }
                        }
                        if (gl < ClipDist) row.glassPoses++;
                        if (d < row.minSweep) { row.minSweep = d; row.worstPose = $"az {a:F0} el {e:F0}"; row.worstAgainst = who + " / " + Zone(zone); }
                        if (d < ClipDist) { row.clipPoses++; var k = who + " / " + Zone(zone); row.clipBy[k] = row.clipBy.TryGetValue(k, out var c) ? c + 1 : 1; if (row.clips.Count < 4) row.clips.Add($"az {a:F0} el {e:F0} {Zone(zone)} vs {who} ({d * 1000:F0} mm)"); }
                    }
                az.localRotation = Quaternion.identity; el.localRotation = Quaternion.identity;
                if (row.clipPoses > 0)
                    row.map = string.Join(" ", els.AsEnumerable().Reverse().Select(e => $"el{e:F0}:" + new string(azs.Select(a => grid[(a, e)] ? 'X' : '.').ToArray())));
                rows.Add(row);
            }
            return rows;
        }

        static readonly List<(string, Vector3, float)> hits = new List<(string, Vector3, float)>();
        static float Pose(Turret tr, Transform az, Transform el, float a, float e, TriGrid statics, TriGrid glassG, List<MeshFilter> azBodies, List<(MeshFilter g, List<Vector3> s)> samples, out string who, out float zone, out float glassD)
        {
            az.localRotation = Quaternion.Euler(0f, a, 0f); el.localRotation = Quaternion.Euler(-e, 0f, 0f);
            TriGrid moving = null, movingGlass = null;
            if (azBodies.Count > 0) { moving = new TriGrid(); movingGlass = new TriGrid(); foreach (var f in azBodies) { AddMesh(moving, f, null, 1); AddMesh(movingGlass, f, null, 2); } }
            float best = TriGridMax; who = "-"; zone = 0f; glassD = TriGridMax;
            foreach (var (g, s) in samples)
                foreach (var p in s)
                {
                    var w = g.transform.TransformPoint(p);
                    float zg = g.sharedMesh.name.EndsWith("grips") ? -1f : p.z;
                    float d = statics.Nearest(w, out int i);
                    if (d < best) { best = d; who = i >= 0 ? statics.owner[i] : who; zone = zg; }
                    if (d < ClipDist && i >= 0) hits.Add((statics.owner[i], w, zg));
                    if (moving != null) { float d2 = moving.Nearest(w, out int j); if (d2 < best) { best = d2; who = j >= 0 ? moving.owner[j] : who; zone = zg; } if (d2 < ClipDist && j >= 0) hits.Add((moving.owner[j], w, zg)); }
                    float gd = glassG.Nearest(w, out int gi); if (movingGlass != null) { float gd2 = movingGlass.Nearest(w, out int gj); if (gd2 < gd) { gd = gd2; gi = -2 - gj; } }
                    glassD = Mathf.Min(glassD, gd);
                    // r2: only the barrel / jacket may pass through glazing (its socket or slot); a receiver or grip touching glass is a clip
                    if (zg <= 0.02f && gd < best) { best = gd; who = gi >= 0 ? glassG.owner[gi] : gi <= -2 ? movingGlass.owner[-2 - gi] : who; zone = zg; }
                    if (zg <= 0.02f && gd < ClipDist && gi != -1) hits.Add((gi >= 0 ? glassG.owner[gi] : movingGlass.owner[-2 - gi], w, zg));
                }
            return best;
        }
        const float TriGridMax = 0.06f;    // distances are only resolved inside one grid cell (>= 6 cm reads as 6 cm = clear)

        /// mode 0 = every submesh, 1 = all but glass, 2 = glass only (a gun through window / dome glazing = its socket or slot, reported apart)
        static void AddMesh(TriGrid g, MeshFilter f, string tag, int mode = 0)
        {
            var m = f.sharedMesh; Vector3[] v;
            try { v = m.vertices; } catch { return; }
            if (v == null || v.Length == 0) return;
            var mr = f.GetComponent<MeshRenderer>(); var mats = mr != null ? mr.sharedMaterials : new Material[0];
            var w = v.Select(p => f.transform.TransformPoint(p)).ToArray();
            for (int sm = 0; sm < m.subMeshCount; sm++)
            {
                var mn = sm < mats.Length && mats[sm] != null ? mats[sm].name : "";
                bool glass = mn.ToLowerInvariant().Contains("glass") || mn.ToLowerInvariant().Contains("canopy");
                if (mode == 1 && glass || mode == 2 && !glass) continue;
                int[] t; try { t = m.GetTriangles(sm); } catch { continue; }
                var who = (tag ?? f.name) + (glass ? ":glass" : "");
                for (int k = 0; k + 2 < t.Length; k += 3) g.Add(w[t[k]], w[t[k + 1]], w[t[k + 2]], who);
            }
        }

        static IEnumerable<Vector3> Corners(Bounds b) { for (int i = 0; i < 8; i++) yield return new Vector3((i & 1) == 0 ? b.min.x : b.max.x, (i & 2) == 0 ? b.min.y : b.max.y, (i & 4) == 0 ? b.min.z : b.max.z); }

        static object Get(object o, string f) => o.GetType().GetField(f, System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public)?.GetValue(o);

        // ============================================================================================ entry point (after BuildAll)
        /// baseline: the 1.8.12 stock door gun (Mesh/50cal_doorGun_barrel_PLACEHOLDER, whole M2 + ammo can) in its 1.8.12 placement
        /// (build with ANM2Guns = false first); same sweep, same obstacles
        public static void RunClearanceStock() { GunTag = "50cal_doorGun"; try { RunClearance(); } finally { GunTag = "_anm2"; } }
        /// the stock door-gun mesh is not readable (m_IsReadable 0): a readable copy for the sweep (scene instance only, nothing saved),
        /// positions + 16 / 32-bit index buffer read from the asset's own serialized data (as B17GBuild.AssetVertices)
        static readonly Dictionary<Mesh, Mesh> readable = new Dictionary<Mesh, Mesh>();
        static Mesh Readable(Mesh m)
        {
            try { if (m.isReadable) return m; } catch { }
            if (readable.TryGetValue(m, out var r)) return r;
            var y = File.ReadAllText(AssetDatabase.GetAssetPath(m));
            var RX = (Func<string, string>)(pat => System.Text.RegularExpressions.Regex.Match(y, pat, System.Text.RegularExpressions.RegexOptions.Singleline).Groups[1].Value);
            int vc = int.Parse(RX(@"m_VertexCount: (\d+)"));
            var pc = System.Text.RegularExpressions.Regex.Match(RX(@"m_Channels:(.*?)m_DataSize"), @"stream: (\d+)\s+offset: (\d+)\s+format: (\d+)\s+dimension: (\d+)");
            Func<string, byte[]> Hex = h => { var d = new byte[h.Length / 2]; for (int i = 0; i < d.Length; i++) d[i] = Convert.ToByte(h.Substring(2 * i, 2), 16); return d; };
            var data = Hex(RX(@"_typelessdata: ([0-9a-f]+)")); var ib = Hex(RX(@"m_IndexBuffer: ([0-9a-f]+)"));
            bool i32 = RX(@"m_IndexFormat: (\d+)") == "1";
            int stride = data.Length / vc, off = int.Parse(pc.Groups[2].Value);
            var v = new Vector3[vc];
            for (int i = 0; i < vc; i++) { int o = i * stride + off; v[i] = new Vector3(BitConverter.ToSingle(data, o), BitConverter.ToSingle(data, o + 4), BitConverter.ToSingle(data, o + 8)); }
            var t = new int[i32 ? ib.Length / 4 : ib.Length / 2];
            for (int i = 0; i < t.Length; i++) t[i] = i32 ? BitConverter.ToInt32(ib, 4 * i) : BitConverter.ToUInt16(ib, 2 * i);
            r = new Mesh { name = m.name + "_readable", indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 }; r.vertices = v; r.triangles = t; r.RecalculateBounds();
            Debug.Log($"[B25H] STOCKCLEAR readable copy of {m.name}: {vc} verts, {t.Length / 3} tris, bounds {r.bounds.min} .. {r.bounds.max}");
            return readable[m] = r;
        }
        public static void RunClearance()
        {
            foreach (var (key, path) in new[] { ("B25H", FamilyBuild.FamilyRoot + "/b25h/B25H.prefab"), ("B17G", FamilyBuild.FamilyRoot + "/b17g/B17G.prefab") })
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
                if (prefab == null) { Debug.Log($"[B25H] {(GunTag == "_anm2" ? "ANM2CLEAR" : "STOCKCLEAR")} {key} FAIL no prefab {path}"); continue; }
                var inst = (GameObject)Object.Instantiate(prefab);
                try
                {
                    inst.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                    if (GunTag != "_anm2") foreach (var f in inst.GetComponentsInChildren<MeshFilter>(true)) if (f.sharedMesh != null && f.sharedMesh.name.Contains(GunTag)) f.sharedMesh = Readable(f.sharedMesh);
                    int clips = 0;
                    foreach (var r in Clearance(inst))
                    {
                        clips += r.clipPoses;
                        Debug.Log($"[B25H] {(GunTag == "_anm2" ? "ANM2CLEAR" : "STOCKCLEAR")} {key} {r.turret}: rest {Mm(r.minRest)} ({r.restAgainst}), sweep min {Mm(r.minSweep)} at {r.worstPose} vs {r.worstAgainst ?? "-"}, twin gap {Mm(r.twin)}, clipping poses {r.clipPoses}/{r.poses} (through glazing {r.glassPoses})"
                            + (r.clipBy.Count > 0 ? " by " + string.Join(", ", r.clipBy.OrderByDescending(k => k.Value).Select(k => $"{k.Key} x{k.Value}")) : "") + (r.clips.Count > 0 ? "; e.g. " + string.Join("; ", r.clips) : ""));
                        if (r.clipPoses > 0)
                            Debug.Log($"[B25H] {(GunTag == "_anm2" ? "ANM2CLEAR" : "STOCKCLEAR")} {key} {r.turret} WHERE map (az left to right) {r.map}; hits (from the el pivot, aircraft axes x right / y up / z fwd; gun z): "
                                + string.Join("; ", r.hitBox.Select(kv => $"{kv.Key} ({kv.Value.min.x:F2},{kv.Value.min.y:F2},{kv.Value.min.z:F2})..({kv.Value.max.x:F2},{kv.Value.max.y:F2},{kv.Value.max.z:F2}) z {r.hitZ[kv.Key].x:F2}..{r.hitZ[kv.Key].y:F2}")));
                    }
                    Debug.Log($"[B25H] {(GunTag == "_anm2" ? "ANM2CLEAR" : "STOCKCLEAR")} {key} {(clips == 0 ? "NO CLIPS" : clips + " CLIPPING POSES")}");
                }
                finally { Object.DestroyImmediate(inst); }
            }
        }
        /// study: shift every gun of a turret along its bore (trunnion at pivot + d) and sweep again, d = -0.30 .. +0.60 m
        public static void RunClearanceScan()
        {
            foreach (var (key, path) in new[] { ("B25H", FamilyBuild.FamilyRoot + "/b25h/B25H.prefab"), ("B17G", FamilyBuild.FamilyRoot + "/b17g/B17G.prefab") })
            {
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path); if (prefab == null) continue;
                var inst = (GameObject)Object.Instantiate(prefab);
                try
                {
                    inst.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                    var bodies = inst.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh != null && f.sharedMesh.name.Contains("_anm2") && !f.sharedMesh.name.EndsWith("grips")).ToList();
                    var z0 = bodies.ToDictionary(b => b, b => b.transform.localPosition.z);
                    var res = new Dictionary<string, List<string>>();
                    foreach (var d in new[] { -0.30f, -0.15f, 0f, 0.15f, 0.30f, 0.45f, 0.60f })
                    {
                        foreach (var b in bodies) { var p = b.transform.localPosition; p.z = z0[b] + (d - TrunnionAhead); b.transform.localPosition = p; }
                        foreach (var r in Clearance(inst))
                        {
                            if (!res.TryGetValue(r.turret, out var l)) res[r.turret] = l = new List<string>();
                            l.Add($"d {d:+0.00;-0.00}: clip {r.clipPoses}/{r.poses} glass {r.glassPoses} rest {Mm(r.minRest)} min {Mm(r.minSweep)} top {(r.clipBy.Count > 0 ? r.clipBy.OrderByDescending(k => k.Value).First().Key : "-")}");
                        }
                    }
                    foreach (var kv in res) Debug.Log($"[B25H] ANM2SCAN {key} {kv.Key}: " + string.Join(" | ", kv.Value));
                }
                finally { Object.DestroyImmediate(inst); }
            }
        }

        static string Mm(float d) => float.IsInfinity(d) ? "-" : d >= TriGridMax - 1e-4f ? ">= 60 mm" : $"{d * 1000:F0} mm";
    }
}
