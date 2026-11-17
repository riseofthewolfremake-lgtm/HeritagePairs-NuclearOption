// 1.9.14 (user suggestion: "wheel lights on the modernised aircraft, like stock"): gear lights on the GA-25X (nose strut) and the
// MSB-17 / FD-32 (each main strut).
// Stock pattern, read from COIN / Fighter1 / CAS1 / EW1 / Multirole1 / FastBomber1 / SmallFighter1 / Darkreach: a 'gearlight_F' object
// on the nose gear door / strut with a Spot Light (white, range / intensity 1000-2000, 30 deg) and a ParticleSystem glow (base material
// gearLight, lit lights_runway); one NavLights entry: renderer = that ParticleSystemRenderer, objects = [the gearlight object], part,
// gear = the LandingGear, controlState Never -> on only while the gear is extended / extending (NavLights.NavLight OnSetGear,
// OnGearBreak, OnDetachedFromUnit).
// In-game rounds 1-2 (2026-11-16): a copy of that object placed at a computed point read as "lights from thin air" (user), the
// spot lit our own nacelles / lower wing / MSB inboard prop discs, and the glow hid the MSB wheel. So now:
//   * a modelled LAMP (housing + bracket + lens) clamped to the front face of the strut mesh, child of the strut (folds with it);
//   * the glow sits on the lens (size x GlowScale); a second NavLights entry swaps the lens to the stock white lit-lens material
//     (gearLight, the white twin of the navlight_L / _R lenses) while the light is on;
//   * the Light is on a child '_beam' just ahead of the lens and its culling mask leaves out layer 14 (CockpitAndExternal: every
//     aircraft, ours included) and 3 (Cockpit): it lights the ground (0 / 6 Statics) and ships (11), never our own airframe;
//   * aim: aircraft forward, pitched down 5 deg + the aircraft's ground pitch (tail-wheel aircraft sit nose-up), so on the ground
//     the beam points 5 deg down at the runway.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class GearLight1914
    {
        public const bool Enabled = true;
        public const string Prefix = "gearlight_";
        public const float GlowScale = 0.5f;
        public const float Reach = 6f;       // m: the beam's lower edge meets the ground this far ahead (r7 MSB-17: matched the stock CI-22 at noon)
        public const float UvTile = 2.0f;    // metres per texture tile on the lamp housing (= the project's 'detail' UV scale / the struts' measured 0.47 UV per m)
        public const int CullMask = ~((1 << 14) | (1 << 3));

        public class Built { public GameObject glow, beam, lamp; public MeshRenderer lens; public Vector3 lensCentre; public float pitchDown; }

        // ground pitch (deg, nose-up positive) from the gear contact points in aircraft space: the mains' tyre bottoms and the other gear's
        public static float GroundPitch(Transform aircraftRoot, IList<LandingGear> mains, LandingGear other)
        {
            Vector3 Bottom(LandingGear g)
            {
                var w = ((Transform[])Get(g, "wheels"))[0]; float r = (float)Get(g, "wheelRadius");
                return aircraftRoot.InverseTransformPoint(w.position) - Vector3.up * r;
            }
            var m = mains.Select(Bottom).Aggregate(Vector3.zero, (a, b) => a + b) / mains.Count;
            var o = Bottom(other);
            return Mathf.Atan2(o.y - m.y, Mathf.Abs(m.z - o.z)) * Mathf.Rad2Deg;   // tail wheel bottom above the mains' -> nose-up
        }

        // the material on the strut's largest submesh, so the housing reads as part of the leg (MSB-17: plain grey strut, r6 housing was near-black)
        public static Material StrutMaterial(Transform strut, Material fallback)
        {
            var mf = strut.GetComponent<MeshFilter>(); var mr = strut.GetComponent<MeshRenderer>();
            if (mf == null || mr == null || mf.sharedMesh == null) return fallback;
            int best = -1, n = 0;
            for (int i = 0; i < mf.sharedMesh.subMeshCount && i < mr.sharedMaterials.Length; i++)
            { int c = (int)mf.sharedMesh.GetIndexCount(i); if (c > n && mr.sharedMaterials[i] != null) { n = c; best = i; } }
            if (best < 0) return fallback;
            var m = mr.sharedMaterials[best];
            // never a textured (livery / skin atlas) material: the housing's box UVs would sample a random part of the atlas
            // (a tiling texture, e.g. msb17_tile_gear_b, is fine: it maps by the 'detail' scale the box UVs use)
            var tex = m.HasProperty("_BaseMap") ? m.GetTexture("_BaseMap") : null;
            if (tex != null && !tex.name.Contains("_tile_")) return fallback;
            return m;
        }

        // the lamp's lowest point above the tyre's top at the lamp's own fore-aft station (aircraft space, m)
        public static float TyreGap(Built b, LandingGear lg, Transform aircraftRoot)
        {
            var w = ((Transform[])Get(lg, "wheels"))[0]; float wr = (float)Get(lg, "wheelRadius");
            var wl = aircraftRoot.InverseTransformPoint(w.position);
            float halfW = 0.10f;   // tyre half width from the wheel mesh (aircraft x)
            var wmf = w.GetComponent<MeshFilter>();
            if (wmf != null && wmf.sharedMesh != null)
            {
                var xs = wmf.sharedMesh.vertices.Select(v => aircraftRoot.InverseTransformPoint(w.TransformPoint(v)).x).ToList();
                halfW = (xs.Max() - xs.Min()) / 2f;
            }
            var mesh = b.lamp.GetComponent<MeshFilter>().sharedMesh;
            var pts = mesh.vertices.Select(v => aircraftRoot.InverseTransformPoint(b.lamp.transform.TransformPoint(v))).ToList();
            float gap = float.MaxValue;
            foreach (var p in pts)
            {
                if (Mathf.Abs(p.x - wl.x) > halfW) continue;   // beside the tyre, not above it
                float dz = p.z - wl.z, top = Mathf.Abs(dz) < wr ? wl.y + Mathf.Sqrt(wr * wr - dz * dz) : float.MinValue;
                gap = Mathf.Min(gap, p.y - top);
            }
            return gap;
        }

        public static Built Make(string dns, LandingGear lg, Transform strut, Transform aircraftRoot, string side, float pitchDownDeg,
                                 Material housingMat, Material lensMat, List<Mesh> generated, float housingR = 0.045f, float clearance = 0.16f, bool heightAim = true)
        {
            var p = AssetDatabase.LoadAssetAtPath<GameObject>(dns + "/GameObject/COIN_PLACEHOLDER.prefab");
            if (p == null) throw new Exception("GearLight1914: missing COIN placeholder");
            var smf = strut.GetComponent<MeshFilter>();
            if (smf == null || smf.sharedMesh == null) throw new Exception("GearLight1914: strut " + strut.name + " has no mesh");
            var wheel = ((Transform[])Get(lg, "wheels"))[0]; float wr = (float)Get(lg, "wheelRadius");

            // strut surface in aircraft space: the front-most vertex in a height band a little above the tyre
            var L = (Func<Vector3, Vector3>)(v => aircraftRoot.InverseTransformPoint(strut.TransformPoint(v)));
            var verts = smf.sharedMesh.vertices.Select(L).ToList();
            var wl = aircraftRoot.InverseTransformPoint(wheel.position);
            float ymin = verts.Min(v => v.y), ymax = verts.Max(v => v.y);
            float y = Mathf.Clamp(wl.y + wr + clearance, ymin + 0.04f, ymax - 0.04f);   // 1.9.14: MSB-17 passes more (r6: housing sat on the tyre crown)
            // r7: the strut surface where the plane at height y cuts its triangles (a long low-poly leg has no vertices mid-way)
            var band = new List<Vector3>();
            var tris = smf.sharedMesh.triangles;
            for (int t = 0; t < tris.Length; t += 3)
                for (int k = 0; k < 3; k++)
                {
                    var a = verts[tris[t + k]]; var c = verts[tris[t + (k + 1) % 3]];
                    if ((a.y - y) * (c.y - y) > 0f || Mathf.Approximately(a.y, c.y)) continue;
                    var q = Vector3.Lerp(a, c, (y - a.y) / (c.y - a.y));
                    if (Mathf.Abs(q.x - wl.x) < 0.5f) band.Add(q);
                }
            if (band.Count < 3)
                foreach (var h in new[] { 0.03f, 0.06f, 0.12f, 0.25f })
                {
                    band = verts.Where(v => Mathf.Abs(v.y - y) < h && Mathf.Abs(v.x - wl.x) < 0.5f).ToList();
                    if (band.Count >= 3) break;
                }
            if (band == null || band.Count == 0) throw new Exception("GearLight1914: no strut vertices near y " + y + " on " + strut.name);
            float front = band.Max(v => v.z);
            var nearFront = band.Where(v => v.z > front - 0.03f).ToList();
            float x = nearFront.Average(v => v.x);
            const float Lh = 0.07f, Br = 0.014f;
            var back = new Vector3(x, y, front - 0.005f);                       // bracket starts 5 mm inside the strut skin
            var hc = new Vector3(x, y, front + Br + Lh / 2f);                   // housing centre
            var lc = new Vector3(x, y, front + Br + Lh + 0.002f);               // lens centre

            var rootRot = aircraftRoot.rotation;
            var lamp = new GameObject(Prefix + side + "_lamp") { layer = strut.gameObject.layer };
            lamp.transform.SetParent(strut, false);
            lamp.transform.SetPositionAndRotation(aircraftRoot.TransformPoint(hc), rootRot);
            var mb = new MeshB();
            mb.Cylinder(new Vector3(0, 0, -Lh / 2f), new Vector3(0, 0, Lh / 2f), housingR, 16, true, true);
            mb.Box(lamp.transform.InverseTransformPoint(aircraftRoot.TransformPoint(back)) + new Vector3(0, 0, (Br + 0.005f) / 2f), new Vector3(housingR * 0.9f, housingR * 1.1f, Br + 0.005f));
            var hm = mb.ToMesh(Prefix + side + "_lamp"); generated?.Add(hm);
            lamp.AddComponent<MeshFilter>().sharedMesh = hm;
            var hr = lamp.AddComponent<MeshRenderer>(); hr.sharedMaterial = housingMat; hr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;

            var lensGo = new GameObject(Prefix + side + "_lens") { layer = lamp.layer };
            lensGo.transform.SetParent(lamp.transform, false);
            lensGo.transform.SetPositionAndRotation(aircraftRoot.TransformPoint(lc), rootRot);
            var lmb = new MeshB(); lmb.Disc(Vector3.zero, housingR * 0.85f, 16);
            var lm = lmb.ToMesh(Prefix + side + "_lens"); generated?.Add(lm);
            lensGo.AddComponent<MeshFilter>().sharedMesh = lm;
            var lens = lensGo.AddComponent<MeshRenderer>(); lens.sharedMaterial = lensMat; lens.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;

            var inst = (GameObject)Object.Instantiate(p);
            inst.SetActive(false);
            try
            {
                var src = inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "gearlight_F");
                if (src == null) throw new Exception("GearLight1914: COIN has no gearlight_F");
                var g = new GameObject(Prefix + side) { layer = lamp.layer };
                g.transform.SetParent(lamp.transform, false);
                // r7b: aim by lamp height so the beam's lower edge meets the ground Reach m ahead on every aircraft
                // (the caller passes the ground pitch; r7 aimed every lamp 1 deg below the ground line and the low FD-32 lamp lit a
                // bright cone from its own wheels at noon, 21 % of the view against the stock CI-22's 11 %)
                float half = src.GetComponent<Light>().spotAngle / 2f;
                float h = lc.y - (wl.y - wr);   // lens height above the tyre's contact point
                // (GA-25X nose, tricycle like the CI-22: heightAim false, 1 deg below the ground line, measured in game r4 as in family
                // with the CI-22 at noon and night; height aim pointed it 6.3 deg up and left only a thin far strip, r5)
                if (heightAim) pitchDownDeg += Mathf.Atan2(h, Reach) * Mathf.Rad2Deg - half;
                g.transform.SetPositionAndRotation(aircraftRoot.TransformPoint(lc + new Vector3(0, 0, 0.01f)), rootRot * Quaternion.Euler(pitchDownDeg, 0f, 0f));
                var sps = src.GetComponent<ParticleSystem>();
                if (sps == null) throw new Exception("GearLight1914: gearlight_F has no glow ParticleSystem");
                var ps = g.AddComponent<ParticleSystem>();
                EditorUtility.CopySerialized(sps, ps);
                var main = ps.main; main.startSizeMultiplier *= GlowScale;
                var psr = g.GetComponent<ParticleSystemRenderer>();
                EditorUtility.CopySerialized(src.GetComponent<ParticleSystemRenderer>(), psr);
                var beam = new GameObject(Prefix + side + "_beam") { layer = g.layer };
                beam.transform.SetParent(g.transform, false);
                beam.transform.SetPositionAndRotation(aircraftRoot.TransformPoint(lc + new Vector3(0, 0, 0.03f)), g.transform.rotation);
                var li = beam.AddComponent<Light>();
                EditorUtility.CopySerialized(src.GetComponent<Light>(), li);
                li.cullingMask = CullMask;
                return new Built { glow = g, beam = beam, lamp = lamp, lens = lens, lensCentre = lc, pitchDown = pitchDownDeg };
            }
            finally { Object.DestroyImmediate(inst); }
        }

        // the two NavLights entries for one light (elements made by the caller's reflection helper): the stock glow entry and the lens
        public static void Entries(object glowEntry, object lensEntry, Built b, UnitPart part, LandingGear gear, string dns)
        {
            var runway = AssetDatabase.LoadAssetAtPath<Material>(dns + "/Material/lights_runway_PLACEHOLDER.mat");
            var lit = AssetDatabase.LoadAssetAtPath<Material>(dns + "/Material/gearLight_PLACEHOLDER.mat");
            if (runway == null || lit == null) throw new Exception("GearLight1914: missing lights_runway / gearLight placeholder");
            Fill(glowEntry, b.glow.GetComponent<ParticleSystemRenderer>(), new[] { b.glow }, runway, part, gear);
            Fill(lensEntry, b.lens, new GameObject[0], lit, part, gear);
        }

        static void Fill(object e, Renderer r, GameObject[] objs, Material litMat, UnitPart part, LandingGear gear)
        {
            Set(e, "renderer", r); Set(e, "objects", objs); Set(e, "litMaterial", litMat); Set(e, "part", part); Set(e, "gear", gear);
            var f = e.GetType().GetField("controlState", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public);
            f.SetValue(e, Enum.ToObject(f.FieldType, 0));   // Never: follows the gear only, as stock
        }

        static void Set(object o, string n, object v) =>
            o.GetType().GetField(n, System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public).SetValue(o, v);
        static object Get(object o, string n) =>
            o.GetType().GetField(n, System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public).GetValue(o);

        // Prefab check: `want` lights; each = a glow entry (spot on a _beam child, culling mask without layers 14 / 3, lights_runway) and a
        // lens entry (gearLight), both Never with gear + part; the glow sits on the lens of a lamp that is a child of a strut mesh and
        // touches it (bracket back inside the strut's bounds); the beam aims forward 0-20 deg down.
        public static bool Check(GameObject inst, int want, out string msg)
        {
            var nl = inst.GetComponent<NavLights>();
            var all = nl == null ? new List<object>() : ((IEnumerable)Get(nl, "navLights")).Cast<object>().ToList();
            var glow = all.Where(e => Get(e, "renderer") is ParticleSystemRenderer r && r.name.StartsWith(Prefix)).ToList();
            var lens = all.Where(e => Get(e, "renderer") is MeshRenderer r && r.name.StartsWith(Prefix) && r.name.EndsWith("_lens")).ToList();
            var bad = new List<string>();
            foreach (var e in glow)
            {
                var r = (Renderer)Get(e, "renderer");
                var li = r.GetComponentInChildren<Light>(true);
                var lamp = r.transform.parent;
                var lensR = lamp != null ? lamp.GetComponentsInChildren<MeshRenderer>(true).FirstOrDefault(x => x.name.EndsWith("_lens")) : null;
                var strut = lamp != null ? lamp.parent : null;
                if (li == null || li.type != LightType.Spot || li.range < 500f || (li.cullingMask & (1 << 14)) != 0 || (li.cullingMask & 1) == 0) bad.Add(r.name + ": light / culling");
                if (!AssetDatabase.GetAssetPath((Material)Get(e, "litMaterial")).Contains("lights_runway")) bad.Add(r.name + ": litMaterial");
                if (Get(e, "gear") == null || Get(e, "part") == null || Get(e, "controlState").ToString() != "Never") bad.Add(r.name + ": gear/part/state");
                if (lamp == null || !lamp.name.EndsWith("_lamp") || lensR == null) bad.Add(r.name + ": no lamp / lens");
                else
                {
                    if (Vector3.Distance(r.transform.position, lensR.transform.position) > 0.03f) bad.Add(r.name + ": glow not on the lens");
                    var smf = strut != null ? strut.GetComponent<MeshFilter>() : null;
                    if (smf == null) bad.Add(r.name + ": lamp not on a strut mesh");
                    else
                    {
                        var b = smf.sharedMesh.bounds; b.Expand(0.02f);
                        var lampMesh = lamp.GetComponent<MeshFilter>().sharedMesh;
                        bool touches = lampMesh.vertices.Any(v => b.Contains(strut.InverseTransformPoint(lamp.TransformPoint(v))));
                        if (!touches) bad.Add(r.name + ": lamp does not touch the strut");
                        if (Get(e, "gear") is LandingGear eg)   // 1.9.14 r7: housing clear of the tyre (r6 MSB-17 sat on the crown)
                        {
                            float gap = TyreGap(new Built { lamp = lamp.gameObject }, eg, inst.transform);
                            if (gap < 0.10f) bad.Add($"{r.name}: lamp only {gap:F3} m above the tyre");
                        }
                        var luv = lampMesh.uv;   // 1.9.14: the housing must carry real UVs so the tiled metal finish maps on it
                        if (luv.Length != lampMesh.vertexCount || luv.Select(u => u.x).Distinct().Count() < 4 || luv.Select(u => u.y).Distinct().Count() < 4) bad.Add(r.name + ": lamp housing has no UVs");
                    }
                }
                if (li != null)
                {
                    float down = Vector3.SignedAngle(inst.transform.forward, li.transform.forward, inst.transform.right);
                    float yaw = Vector3.Angle(Vector3.ProjectOnPlane(li.transform.forward, inst.transform.up), inst.transform.forward);
                    if (down < -12f || down > 20f || yaw > 1f) bad.Add($"{r.name}: aim down {down:F1} yaw {yaw:F1}");
                }
            }
            foreach (var e in lens)
                if (!AssetDatabase.GetAssetPath((Material)Get(e, "litMaterial")).Contains("gearLight") || Get(e, "gear") == null || Get(e, "controlState").ToString() != "Never")
                    bad.Add(((Renderer)Get(e, "renderer")).name + ": lens entry");
            msg = $"{glow.Count} gear lights + {lens.Count} lenses ({string.Join(", ", glow.Select(e => ((Renderer)Get(e, "renderer")).name + "@" + ((Renderer)Get(e, "renderer")).transform.parent?.parent?.name))}); {(bad.Count == 0 ? "ok" : string.Join("; ", bad))}";
            return glow.Count == want && lens.Count == want && bad.Count == 0;
        }

        // tiny mesh builder (flat-shaded quads / fans, own normals)
        class MeshB
        {
            readonly List<Vector3> v = new List<Vector3>(); readonly List<Vector3> n = new List<Vector3>(); readonly List<int> t = new List<int>();
            void Tri(Vector3 a, Vector3 b, Vector3 c)
            {
                var nn = Vector3.Cross(b - a, c - a).normalized; int i = v.Count;
                v.Add(a); v.Add(b); v.Add(c); n.Add(nn); n.Add(nn); n.Add(nn); t.Add(i); t.Add(i + 1); t.Add(i + 2);
            }
            void Quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d) { Tri(a, b, c); Tri(a, c, d); }
            public void Cylinder(Vector3 p0, Vector3 p1, float r, int seg, bool cap0, bool cap1)
            {
                for (int k = 0; k < seg; k++)
                {
                    float a0 = 2 * Mathf.PI * k / seg, a1 = 2 * Mathf.PI * (k + 1) / seg;
                    var d0 = new Vector3(Mathf.Cos(a0), Mathf.Sin(a0), 0) * r; var d1 = new Vector3(Mathf.Cos(a1), Mathf.Sin(a1), 0) * r;
                    Quad(p0 + d0, p0 + d1, p1 + d1, p1 + d0);
                    if (cap0) Tri(p0, p0 + d1, p0 + d0);
                    if (cap1) Tri(p1, p1 + d0, p1 + d1);
                }
            }
            public void Disc(Vector3 c, float r, int seg)
            {
                for (int k = 0; k < seg; k++)
                {
                    float a0 = 2 * Mathf.PI * k / seg, a1 = 2 * Mathf.PI * (k + 1) / seg;
                    Tri(c, c + new Vector3(Mathf.Cos(a0), Mathf.Sin(a0), 0) * r, c + new Vector3(Mathf.Cos(a1), Mathf.Sin(a1), 0) * r);
                }
            }
            public void Box(Vector3 c, Vector3 s)
            {
                var h = s / 2f;
                Vector3 P(int x, int y, int z) => c + new Vector3(x * h.x, y * h.y, z * h.z);
                Quad(P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1)); Quad(P(1, -1, -1), P(-1, -1, -1), P(-1, 1, -1), P(1, 1, -1));
                Quad(P(-1, 1, -1), P(-1, 1, 1), P(1, 1, 1), P(1, 1, -1)); Quad(P(-1, -1, 1), P(-1, -1, -1), P(1, -1, -1), P(1, -1, 1));
                Quad(P(1, -1, 1), P(1, -1, -1), P(1, 1, -1), P(1, 1, 1)); Quad(P(-1, -1, -1), P(-1, -1, 1), P(-1, 1, 1), P(-1, 1, -1));
            }
            public Mesh ToMesh(string name)
            {
                // 1.9.14: box-projected UVs (each flat-shaded face takes the plane of its dominant normal axis), 1 tile per
                // UvTile metres, so the tiled metal_dark finish (GA-25X / FD-32 textures) maps like the strut's skin instead
                // of every vertex sampling texel (0,0).
                var uv = new List<Vector2>(v.Count);
                for (int i = 0; i < v.Count; i++)
                {
                    var a = new Vector3(Mathf.Abs(n[i].x), Mathf.Abs(n[i].y), Mathf.Abs(n[i].z)); var p = v[i] / UvTile;
                    uv.Add(a.x >= a.y && a.x >= a.z ? new Vector2(p.z, p.y) : a.y >= a.z ? new Vector2(p.x, p.z) : new Vector2(p.x, p.y));
                }
                var m = new Mesh { name = name }; m.SetVertices(v); m.SetNormals(n); m.SetUVs(0, uv); m.SetTriangles(t, 0);
                m.RecalculateBounds(); m.RecalculateTangents(); return m;
            }
        }
    }
}
