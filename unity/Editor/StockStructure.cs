// Heritage Pairs 1.8.3: internals the stock way (user review 2026-11-07 item 9: "Look at how stock aircraft models use internal parts.
// We should be doing THAT."). docs/stock_internals_study.md: stock aircraft draw their internals (frames, ribs, engine bodies seen at the
// break-off faces) as extra geometry of the part meshes with the shared stock material aircraft_structure (Shader Graphs/Lit_vertexcolor,
// white base, smoothness 1, tinted by vertex colour). Measured on the user's install (AssetRipper export, numbers only): the
// FastBomber1 structure submeshes carry vertex colour 93/93/93 (engines 92-103) and 0.3-0.6 UV units per metre.
//
// Apply(): every renderer that draws one of our internals materials (by name) gets that submesh moved into a child renderer
// "<name>_struct" drawn with the stock material, with the stock vertex colour and UV0 = our detail UV (0.5 per metre). The original
// mesh keeps its other submeshes in the same order (paint stays material 0, so liveries and damage maps are untouched) and gets no
// vertex colours: the outside look of the approved B-25H / GA-25X is unchanged by construction. Call it after the colliders are baked
// (BakeCollider reads the part's own mesh: the collider keeps the internals' vertices, as before).
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class StockStructure
    {
        public const bool Enabled = true;                                          // false = 1.8.2 (our own tiled 'structure' material)
        public static readonly Color32 StockGrey = new Color32(93, 93, 93, 255);  // FastBomber1 structure submeshes
        public static readonly Color32 StockEngineGrey = new Color32(99, 99, 99, 255);

        // 1.8.5 offline E (in-game 1.8.3 F1: break faces salmon / copper on the Mk I, FD-32 and B-17G, light grey on the B-25H / GA-25X).
        // Measured: our internals already carry exactly the stock exterior-structure vertex colours (92 / 93 / 99, alpha 255, UNorm8 x4,
        // same stream layout as FastBomber1 / SmallFighter1), the same material, renderer flags and consistent normals on all five, so the
        // vertex colour is not the cause. The stock Lit_vertexcolor multiplies its base map by the vertex colour (stock values: EW1 intakes
        // 255/125/88, SmallFighter1 ducts 23/15/13, structure 87-118) and takes metallic / smoothness from its map (mean 0.53 / 0.47): at 93
        // the base is ~0.19 linear, so what shows is mostly the reflection of the game's realtime probe (LevelInfo.UpdateReflectionProbe:
        // re-rendered every 5 s, skipped while bright lights exist) - warm fire / low sun came back salmon on some faces, grey on others.
        // MatteLook185E: the internals keep the stock textures (pattern, normal, AO: the same placeholders, resolved to the game's
        // aircraft_structure_b / _n / _ao at load as our glass materials resolve COIN_glass_b) on a URP Lit material that is nearly
        // dielectric (metallic 0.1) with a neutral light-grey base, so a face reads light grey under any light. The stock vertex colours
        // stay in the meshes. false = the 1.8.4 stock material (nothing else changes).
        public const bool MatteLook185E = true;
        public static readonly Color LookBase = new Color(0.80f, 0.80f, 0.80f, 1f);   // x base map (mean 0.74 sRGB) = ~0.31 linear albedo: light grey
        public const float LookMetallic = 0.10f, LookSmoothness = 0.35f;

        // the material our internals are drawn with: the stock aircraft_structure (flag off) or <prefix>_structure_look in <folder>/Materials
        public static Material LookMaterial(Material stock, string folder, string prefix)
        {
            if (!MatteLook185E || stock == null) return stock;
            var path = folder + "/Materials/" + prefix + "_structure_look.mat";
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null) { m = new Material(lit); AssetDatabase.CreateAsset(m, path); }
            m.shader = lit; m.name = prefix + "_structure_look";
            var b = stock.GetTexture("_Basecolor"); var n = stock.GetTexture("_Normal"); var ao = stock.GetTexture("_AO");
            m.SetTexture("_BaseMap", b); m.SetTexture("_MainTex", b); m.SetColor("_BaseColor", LookBase); m.SetColor("_Color", LookBase);
            m.SetTexture("_BumpMap", n); m.SetFloat("_BumpScale", 1f); m.EnableKeyword("_NORMALMAP");
            m.SetTexture("_OcclusionMap", ao); m.SetFloat("_OcclusionStrength", 1f); m.EnableKeyword("_OCCLUSIONMAP");
            m.SetTexture("_MetallicGlossMap", null); m.DisableKeyword("_METALLICSPECGLOSSMAP");
            m.SetFloat("_Metallic", LookMetallic); m.SetFloat("_Smoothness", LookSmoothness); m.SetFloat("_Glossiness", LookSmoothness);
            m.SetFloat("_WorkflowMode", 1f); m.SetFloat("_Surface", 0f); m.SetFloat("_Cull", 2f);
            EditorUtility.SetDirty(m);
            return m;
        }

        // the stock aircraft_structure or our look material (check rows)
        public static bool IsStructMat(Material m) => m != null && (AssetDatabase.GetAssetPath(m).Contains("aircraft_structure_PLACEHOLDER") || m.name.EndsWith("_structure_look"));

        // check row (all five): every internals renderer outside the cockpit layer is on the look material (flag on) / the stock material
        // (flag off); the look material carries the three stock textures, is neutral light grey and nearly dielectric; every internals
        // submesh carries a stock exterior-structure vertex colour (grey 87-118, alpha 255: FastBomber1 92/93/99/103, SmallFighter1
        // 92/99/103/118, Multirole1 87/89). excludeNames: renderers with their own stock use (GA-25X cabin tub, colour 56).
        public static bool CheckLook(GameObject inst, out string msg, params string[] excludeNames)
        {
            var rs = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.gameObject.layer != 3 && !excludeNames.Any(x => r.name.StartsWith(x))).ToList();
            var withStruct = rs.Where(r => r.sharedMaterials.Any(IsStructMat)).ToList();
            var onStock = withStruct.Where(r => r.sharedMaterials.Any(mm => mm != null && AssetDatabase.GetAssetPath(mm).Contains("aircraft_structure_PLACEHOLDER"))).Select(r => r.name).ToList();
            var looks = withStruct.SelectMany(r => r.sharedMaterials).Where(mm => mm != null && mm.name.EndsWith("_structure_look")).Distinct().ToList();
            bool matOk = MatteLook185E ? (onStock.Count == 0 && looks.Count == 1) : looks.Count == 0;
            string texs = "";
            if (looks.Count == 1)
            {
                var L = looks[0];
                string T(string p) { var t = L.GetTexture(p); return t == null ? "-" : t.name; }
                var c = L.GetColor("_BaseColor");
                texs = $"{L.name}: {L.shader.name} base {T("_BaseMap")} normal {T("_BumpMap")} ao {T("_OcclusionMap")} col {c.r:F2}/{c.g:F2}/{c.b:F2} metal {L.GetFloat("_Metallic"):F2} smooth {L.GetFloat("_Smoothness"):F2}";
                matOk &= L.shader.name == "Universal Render Pipeline/Lit" && T("_BaseMap").StartsWith("aircraft_structure_b") && T("_BumpMap").StartsWith("aircraft_structure_n")
                    && T("_OcclusionMap").StartsWith("aircraft_structure_ao") && Mathf.Abs(c.r - c.g) < 1e-3f && Mathf.Abs(c.g - c.b) < 1e-3f && c.r >= 0.7f && c.r <= 0.9f
                    && L.GetFloat("_Metallic") <= 0.15f && L.IsKeywordEnabled("_NORMALMAP");
            }
            int subs = 0, badCol = 0; var vals = new SortedSet<int>();
            foreach (var r in withStruct)
            {
                var mesh = r.GetComponent<MeshFilter>()?.sharedMesh; if (mesh == null) continue;
                var c32 = mesh.colors32; var mats = r.sharedMaterials;
                for (int k = 0; k < Math.Min(mats.Length, mesh.subMeshCount); k++)
                {
                    if (!IsStructMat(mats[k])) continue;
                    subs++;
                    if (c32.Length != mesh.vertexCount) { badCol++; continue; }
                    foreach (var i in new HashSet<int>(mesh.GetIndices(k)))
                    {
                        var cc = c32[i]; vals.Add(cc.r);
                        if (cc.r != cc.g || cc.g != cc.b || cc.a != 255 || cc.r < 87 || cc.r > 118) { badCol++; break; }
                    }
                }
            }
            msg = $"{withStruct.Count} internals renderers, {subs} submeshes, vertex grey {string.Join("/", vals)}, bad colour {badCol}, left on the stock material {onStock.Count} {string.Join(",", onStock.Take(4))}; {texs}";
            return matOk && subs > 0 && badCol == 0;
        }

        public class Result { public int renderers, triangles, children; public List<string> log = new List<string>(); }

        // internals: material -> vertex colour. uvScale multiplies UV0 (our detail UV: 2 m per unit = 0.5 per metre, inside the stock range).
        public static Result Apply(GameObject root, Material stock, IDictionary<Material, Color32> internals, float uvScale, List<Mesh> generated)
        {
            var res = new Result();
            if (!Enabled || stock == null) return res;
            foreach (var r in root.GetComponentsInChildren<MeshRenderer>(true).ToList())
            {
                var mf = r.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                if (r.gameObject.layer == 3) continue;     // cockpit-layer copies (*_int) keep the approved cockpit look
                // 1.9.14: never split a prop blade. ConstantSpeedProp hides only the blade's own renderer when the blur disc shows;
                // a split-off child (GA-25X nickel tip sheath, 'structure' faces at r 1.80-1.86 m) kept spinning visibly over the disc.
                if (r.gameObject.name.Contains("_blade")) { res.log.Add($"{r.gameObject.name}: prop blade, not split"); continue; }
                var mats = r.sharedMaterials;
                var idx = Enumerable.Range(0, mats.Length).Where(i => mats[i] != null && internals.ContainsKey(mats[i]) && i < mf.sharedMesh.subMeshCount).ToList();
                if (idx.Count == 0) continue;
                var src = mf.sharedMesh;
                if (idx.Count == Math.Min(mats.Length, src.subMeshCount))
                {   // internals only (no paint on this renderer): recolour in place
                    var m0 = Object.Instantiate(src); m0.name = src.name;
                    var cols = Enumerable.Repeat(StockGrey, m0.vertexCount).ToArray();
                    foreach (var k in idx) foreach (var i in m0.GetTriangles(k)) cols[i] = internals[mats[k]];
                    var u0 = new List<Vector2>(); m0.GetUVs(0, u0);
                    if (u0.Count == m0.vertexCount) { for (int i = 0; i < u0.Count; i++) u0[i] *= uvScale; m0.SetUVs(0, u0); }
                    m0.colors32 = cols;
                    generated.Add(m0); mf.sharedMesh = m0;
                    r.sharedMaterials = mats.Select(_ => stock).ToArray();
                    res.renderers++; res.triangles += idx.Sum(k => (int)m0.GetIndexCount(k) / 3);
                    res.log.Add($"{r.gameObject.name}: recoloured in place");
                    continue;
                }
                // 1. the internals mesh (one submesh per internals material, each drawn with the stock material)
                var verts = new List<Vector3>(); src.GetVertices(verts);
                var nrms = new List<Vector3>(); src.GetNormals(nrms);
                var uv0 = new List<Vector2>(); src.GetUVs(0, uv0);
                var map = new Dictionary<int, int>();
                var nv = new List<Vector3>(); var nn = new List<Vector3>(); var nu = new List<Vector2>(); var nc = new List<Color32>();
                var subs = new List<List<int>>();
                foreach (var k in idx)
                {
                    var col = internals[mats[k]];
                    var tri = new List<int>();
                    foreach (var i in src.GetTriangles(k))
                    {
                        // a vertex shared by two internals materials keeps its first colour: split it per material instead
                        int key = i * 64 + idx.IndexOf(k);
                        if (!map.TryGetValue(key, out int j))
                        {
                            j = nv.Count; map[key] = j;
                            nv.Add(verts[i]); nn.Add(i < nrms.Count ? nrms[i] : Vector3.up);
                            nu.Add(i < uv0.Count ? uv0[i] * uvScale : Vector2.zero); nc.Add(col);
                        }
                        tri.Add(j);
                    }
                    subs.Add(tri); res.triangles += tri.Count / 3;
                }
                var sm = new Mesh { name = src.name + "_struct", indexFormat = nv.Count > 65000 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16 };
                sm.SetVertices(nv); sm.SetNormals(nn); sm.SetUVs(0, nu); sm.SetColors(nc);
                // one submesh: one draw call with the stock material (the colour is per vertex)
                sm.subMeshCount = 1; sm.SetTriangles(subs.SelectMany(t => t).ToList(), 0);
                sm.RecalculateBounds(); sm.RecalculateTangents();
                generated.Add(sm);
                var go = new GameObject(r.gameObject.name + "_struct");
                go.layer = r.gameObject.layer;
                go.transform.SetParent(r.transform, false);
                go.AddComponent<MeshFilter>().sharedMesh = sm;
                var nr = go.AddComponent<MeshRenderer>();
                nr.sharedMaterial = stock;
                nr.shadowCastingMode = r.shadowCastingMode; nr.receiveShadows = r.receiveShadows;
                res.children++;
                // 2. the original mesh without those submeshes (order of the others kept: paint stays first)
                var keep = Enumerable.Range(0, Math.Min(mats.Length, src.subMeshCount)).Where(i => !idx.Contains(i)).ToList();
                {
                    var m = Object.Instantiate(src); m.name = src.name;
                    var tris = keep.Select(i => src.GetTriangles(i)).ToList();
                    m.subMeshCount = keep.Count;
                    for (int i = 0; i < keep.Count; i++) m.SetTriangles(tris[i], i);
                    generated.Add(m);
                    mf.sharedMesh = m;
                    r.sharedMaterials = keep.Select(i => mats[i]).ToArray();
                }
                res.renderers++;
                res.log.Add($"{r.gameObject.name}: {subs.Sum(t => t.Count) / 3} tris -> {go.name}");
            }
            return res;
        }
    }
}
