// Performance audit of the built family prefabs (B-25H cockpit v3 FPS report, 2026-11-01). Read-only: instantiates each built
// prefab in the editor scene, dumps renderers / submeshes / shadow casters / colliders / rigidbodies / lights / cameras /
// materials (shader, keywords, queue) / textures (size, format, mips, read-write, compression, NPOT), then destroys the
// instance. Nothing in the project is modified.
//
//   unity.sh - audit_perf -executeMethod B25HTools.B25HAudit.Run
// Output: C:\Users\User\nuclearoption-ref\study\perf\audit_<prefab>.txt (+ a one-line summary per prefab in the Unity log).
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class B25HAudit
    {
        const string OutDir = @"C:\Users\User\nuclearoption-ref\study\perf";

        public static void Run()
        {
            Directory.CreateDirectory(OutDir);
            foreach (var p in new[] { FamilyBuild.FamilyRoot + "/b25h/B25H.prefab", FamilyBuild.FamilyRoot + "/ga25x/GA25X.prefab" })
            {
                var asset = AssetDatabase.LoadAssetAtPath<GameObject>(p);
                if (asset == null) { Debug.Log($"[AUDIT] missing {p}"); continue; }
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(asset);
                try { Dump(inst, Path.GetFileNameWithoutExtension(p)); }
                finally { Object.DestroyImmediate(inst); }
            }
        }

        static string Rel(Transform t, Transform root)
        {
            var s = t.name; while (t.parent != null && t.parent != root) { t = t.parent; s = t.name + "/" + s; }
            return s;
        }

        static void Dump(GameObject root, string name)
        {
            var sb = new StringBuilder();
            sb.AppendLine($"# audit {name}");
            var rs = root.GetComponentsInChildren<Renderer>(true);
            int[] layerDraws = new int[32], layerTris = new int[32], layerVerts = new int[32], layerCount = new int[32];
            int shadowCasters = 0, shadowTris = 0, readable = 0, idx32 = 0;
            sb.AppendLine("## renderers: layer | enabled | shadows | verts | tris | submeshes | mats | readable | index | mesh | path");
            foreach (var r in rs.OrderBy(r => r.gameObject.layer).ThenBy(r => r.name))
            {
                Mesh m = null;
                if (r is MeshRenderer) m = r.GetComponent<MeshFilter>() ? r.GetComponent<MeshFilter>().sharedMesh : null;
                else if (r is SkinnedMeshRenderer smr) m = smr.sharedMesh;
                int v = m ? m.vertexCount : 0, sub = m ? m.subMeshCount : 0, t = 0;
                if (m) for (int i = 0; i < sub; i++) t += (int)m.GetIndexCount(i) / 3;
                int L = r.gameObject.layer;
                layerCount[L]++; layerDraws[L] += Mathf.Max(sub, r.sharedMaterials.Length); layerTris[L] += t; layerVerts[L] += v;
                if (r.shadowCastingMode != ShadowCastingMode.Off) { shadowCasters++; shadowTris += t; }
                if (m && m.isReadable) readable++;
                if (m && m.indexFormat == IndexFormat.UInt32) idx32++;
                sb.AppendLine($"{L} | {r.enabled} | {r.shadowCastingMode} | {v} | {t} | {sub} | {r.sharedMaterials.Length} | {(m ? m.isReadable : false)} | {(m ? m.indexFormat.ToString() : "-")} | {(m ? m.name : "-")} | {Rel(r.transform, root.transform)} | {r.GetType().Name}");
            }
            sb.AppendLine("## per layer: layer renderers draws(submeshes) verts tris");
            for (int L = 0; L < 32; L++) if (layerCount[L] > 0) sb.AppendLine($"layer {L}: {layerCount[L]} renderers, {layerDraws[L]} draws, {layerVerts[L]} verts, {layerTris[L]} tris");
            sb.AppendLine($"shadow casters {shadowCasters} ({shadowTris} tris); readable meshes {readable}; 32-bit index meshes {idx32}");

            sb.AppendLine("## colliders");
            foreach (var c in root.GetComponentsInChildren<Collider>(true))
            {
                var mc = c as MeshCollider;
                sb.AppendLine($"{c.GetType().Name} | {Rel(c.transform, root.transform)} | layer {c.gameObject.layer} | trigger {c.isTrigger} | enabled {c.enabled}" +
                              (mc ? $" | convex {mc.convex} | mesh {(mc.sharedMesh ? mc.sharedMesh.name : "-")} verts {(mc.sharedMesh ? mc.sharedMesh.vertexCount : 0)}" : ""));
            }
            sb.AppendLine("## rigidbodies / lights / cameras / probes / particles / LOD / canvases / audio");
            foreach (var b in root.GetComponentsInChildren<Rigidbody>(true)) sb.AppendLine($"Rigidbody {Rel(b.transform, root.transform)} kinematic {b.isKinematic} interp {b.interpolation} mode {b.collisionDetectionMode}");
            foreach (var l in root.GetComponentsInChildren<Light>(true)) sb.AppendLine($"Light {Rel(l.transform, root.transform)} {l.type} shadows {l.shadows} active {l.gameObject.activeInHierarchy} enabled {l.enabled} range {l.range}");
            foreach (var c in root.GetComponentsInChildren<Camera>(true)) sb.AppendLine($"Camera {Rel(c.transform, root.transform)} enabled {c.enabled} active {c.gameObject.activeInHierarchy} target {(c.targetTexture ? c.targetTexture.name + " " + c.targetTexture.width + "x" + c.targetTexture.height : "screen")}");
            foreach (var c in root.GetComponentsInChildren<ReflectionProbe>(true)) sb.AppendLine($"ReflectionProbe {Rel(c.transform, root.transform)} mode {c.mode} refresh {c.refreshMode}");
            foreach (var c in root.GetComponentsInChildren<ParticleSystem>(true)) sb.AppendLine($"ParticleSystem {Rel(c.transform, root.transform)} max {c.main.maxParticles}");
            foreach (var c in root.GetComponentsInChildren<LODGroup>(true)) sb.AppendLine($"LODGroup {Rel(c.transform, root.transform)} lods {c.lodCount}");
            foreach (var c in root.GetComponentsInChildren<Canvas>(true)) sb.AppendLine($"Canvas {Rel(c.transform, root.transform)} mode {c.renderMode}");
            sb.AppendLine($"AudioSources {root.GetComponentsInChildren<AudioSource>(true).Length}");
            sb.AppendLine("## behaviours (type: count)");
            foreach (var g in root.GetComponentsInChildren<MonoBehaviour>(true).Where(b => b != null).GroupBy(b => b.GetType().Name).OrderByDescending(g => g.Count()))
                sb.AppendLine($"{g.Key}: {g.Count()}");

            sb.AppendLine("## materials: name | shader | queue | keywords | users | textures");
            var mats = new Dictionary<Material, int>();
            foreach (var r in rs) foreach (var m in r.sharedMaterials) if (m) mats[m] = mats.TryGetValue(m, out var k) ? k + 1 : 1;
            var texs = new HashSet<Texture>();
            foreach (var kv in mats.OrderBy(k => k.Key.name))
            {
                var m = kv.Key;
                var tn = new List<string>();
                foreach (var prop in m.GetTexturePropertyNames())
                {
                    var tx = m.GetTexture(prop); if (tx == null) continue;
                    texs.Add(tx); tn.Add($"{prop}={tx.name}");
                }
                sb.AppendLine($"{m.name} | {m.shader.name} | {m.renderQueue} | {string.Join(" ", m.shaderKeywords)} | {kv.Value} | {string.Join(", ", tn)}");
            }
            sb.AppendLine("## textures: name | size | format | mips | readable | npot | importer compression | maxSize | approx MB");
            double totalMB = 0;
            foreach (var tx in texs.OrderBy(t => t.name))
            {
                var path = AssetDatabase.GetAssetPath(tx);
                var ti = AssetImporter.GetAtPath(path) as TextureImporter;
                var t2 = tx as Texture2D;
                long bytes = UnityEngine.Profiling.Profiler.GetRuntimeMemorySizeLong(tx);
                totalMB += bytes / 1048576.0;
                bool npot = (tx.width & (tx.width - 1)) != 0 || (tx.height & (tx.height - 1)) != 0;
                sb.AppendLine($"{tx.name} | {tx.width}x{tx.height} | {(t2 ? t2.format.ToString() : tx.GetType().Name)} | {(t2 ? t2.mipmapCount : 0)} | {tx.isReadable} | {npot} | {(ti ? ti.textureCompression.ToString() : "-")} | {(ti ? ti.maxTextureSize : 0)} | {bytes / 1048576.0:F1}");
            }
            var sum = $"[AUDIT] {name}: renderers {rs.Length}; layer0 {layerCount[0]} r / {layerDraws[0]} draws / {layerTris[0]} tris; layer3 {layerCount[3]} r / {layerDraws[3]} draws / {layerTris[3]} tris / {layerVerts[3]} verts; shadow casters {shadowCasters} ({shadowTris} tris); colliders {root.GetComponentsInChildren<Collider>(true).Length} (mesh {root.GetComponentsInChildren<MeshCollider>(true).Length}); lights {root.GetComponentsInChildren<Light>(true).Length}; cameras {root.GetComponentsInChildren<Camera>(true).Length}; materials {mats.Count}; textures {texs.Count} ({totalMB:F0} MB editor size)";
            sb.AppendLine(sum);
            File.WriteAllText(Path.Combine(OutDir, $"audit_{name}.txt"), sb.ToString());
            Debug.Log(sum);
        }
    }
}
