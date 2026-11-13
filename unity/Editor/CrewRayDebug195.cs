// 1.9.5 copy for the MSB-17/80 WSO (study tool, not called by the build; the 1.8.17 B-17G tool unchanged). 1.8.17 offline P (study tool, not called by the build): why do a few crew-in-hull rays of the B-17G check leave the nose in Unity
// while the same rays hit in Blender (blend and FBX re-import)? Casts the check's rays from given root-frame points against the same
// probes (non-convex MeshColliders on every MeshFilter, back faces on) AND against the probe meshes' triangles directly (Moller-Trumbore),
// and logs both first hits. A miss in PhysX with a triangle hit in the mesh = the collider cooking dropped / welded it.
//   Unity.exe -batchmode -nographics -quit -projectPath <Blueprinter-Editor> -executeMethod B25HTools.CrewRayDebug1817.Run -logFile <log>
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class CrewRayDebug195
    {
        static readonly Vector3[] Pts = { new Vector3(-0.16f, 0.33f, 5.68f) };   // the 1.9.5 build 1 crew-in-hull miss (WSO, seated, 'misses R')

        public static void Run()
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(FamilyBuild.FamilyRoot + "/msb17/MSB17.prefab");
            var inst = (GameObject)Object.Instantiate(prefab);
            var tmp = new List<GameObject>();
            try
            {
                inst.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                var ac = inst.GetComponent<Aircraft>();
                var figs = new HashSet<Transform>((ac.pilots ?? new Pilot[0]).Select(p => p.transform));
                var meshes = new List<(MeshFilter mf, Vector3[] v, int[] t)>();
                foreach (var mf in inst.GetComponentsInChildren<MeshFilter>(true))
                {
                    if (mf.sharedMesh == null || figs.Any(f => mf.transform.IsChildOf(f))) continue;
                    var go = new GameObject("hullprobe"); go.layer = 31; go.transform.SetPositionAndRotation(mf.transform.position, mf.transform.rotation); go.transform.localScale = mf.transform.lossyScale;
                    var mc = go.AddComponent<MeshCollider>(); mc.sharedMesh = mf.sharedMesh; mc.convex = false; tmp.Add(go);
                    try { meshes.Add((mf, mf.sharedMesh.vertices.Select(p => mf.transform.TransformPoint(p)).ToArray(), mf.sharedMesh.triangles)); } catch { }
                }
                Physics.SyncTransforms();
                bool back = Physics.queriesHitBackfaces; Physics.queriesHitBackfaces = true;
                var rng = new System.Random(195);
                var jit = new List<Vector3>();
                foreach (var pl in Pts) { jit.Add(pl); for (int k = 0; k < 400; k++) jit.Add(pl + new Vector3((float)rng.NextDouble() * 0.012f - 0.006f, (float)rng.NextDouble() * 0.012f - 0.006f, (float)rng.NextDouble() * 0.012f - 0.006f)); }
                int nmiss = 0;
                foreach (var pl in jit)
                {
                    var p = inst.transform.TransformPoint(pl);
                    foreach (var d in new[] { inst.transform.right, -inst.transform.right, -inst.transform.up })
                    {
                        if (Physics.Raycast(p, d, 4f, 1 << 31) && !Pts.Contains(pl)) continue;     // jittered: log misses only
                        if (!Pts.Contains(pl)) nmiss++;
                        if (!Pts.Contains(pl) && nmiss > 40) continue;
                        bool hit = Physics.Raycast(p, d, out var h, 4f, 1 << 31);
                        float best = 9f; string who = "-"; Vector3 a = default, b = default, c = default;
                        foreach (var (mf, v, t) in meshes)
                            for (int k = 0; k + 2 < t.Length; k += 3)
                            {
                                if (Tri(p, d, v[t[k]], v[t[k + 1]], v[t[k + 2]], out float dist) && dist < best)
                                { best = dist; who = mf.name + "#" + (k / 3); a = v[t[k]]; b = v[t[k + 1]]; c = v[t[k + 2]]; }
                            }
                        float area = Vector3.Cross(b - a, c - a).magnitude / 2f;
                        Debug.Log($"[B25H] CREWRAY {pl.ToString("F2")} dir {inst.transform.InverseTransformDirection(d).ToString("F0")}: physx {(hit ? $"{h.collider.name} {h.distance:F3}" : "MISS")}; mesh {who} {best:F3} area {area:E2} tri ({inst.transform.InverseTransformPoint(a).ToString("F4")} {inst.transform.InverseTransformPoint(b).ToString("F4")} {inst.transform.InverseTransformPoint(c).ToString("F4")})");
                    }
                }
                Debug.Log($"[B25H] CREWRAY jittered misses {nmiss} of {jit.Count - Pts.Length} x 3");
                Physics.queriesHitBackfaces = back;
            }
            finally { foreach (var g in tmp) Object.DestroyImmediate(g); Object.DestroyImmediate(inst); }
        }

        static bool Tri(Vector3 o, Vector3 d, Vector3 a, Vector3 b, Vector3 c, out float t)
        {
            t = 0; var e1 = b - a; var e2 = c - a; var pv = Vector3.Cross(d, e2); float det = Vector3.Dot(e1, pv);
            if (Mathf.Abs(det) < 1e-12f) return false;
            float inv = 1f / det; var tv = o - a; float u = Vector3.Dot(tv, pv) * inv; if (u < -1e-6f || u > 1 + 1e-6f) return false;
            var qv = Vector3.Cross(tv, e1); float w = Vector3.Dot(d, qv) * inv; if (w < -1e-6f || u + w > 1 + 1e-6f) return false;
            t = Vector3.Dot(e2, qv) * inv; return t > 0;
        }
    }
}
