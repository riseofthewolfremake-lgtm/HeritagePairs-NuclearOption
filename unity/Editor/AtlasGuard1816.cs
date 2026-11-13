// 1.8.16 livery-atlas guard (blender/atlas_guard.py is the reference implementation; the hash here is the same, bit for bit).
// Why: every model rebuild re-runs the global atlas pack (bpy.ops.uv.pack_islands), so a geometry change anywhere moves every island
// in UV0; in 1.8.13 / 1.8.14 the B-25H / B-17G skin and liveries (painted on the 1.8.12 atlas) landed on the wrong parts in game.
// Each texture build writes <prefix>_atlas_manifest.json next to its textures; this row recomputes the hash from the meshes the build
// actually imported (UV0 of the paint sub-meshes) and FAILS when any part moved, a part is missing / new, a texture in the manifest was
// painted on another atlas (partial re-bake), or a texture file is not the one the manifest recorded.
// Hash per part: the SET of distinct UV0 points of its paint triangles, q = floor(u * 65536) in double (exact for float32), sorted
// (u, then v), little-endian int32 pairs, SHA-1, first 16 hex. Atlas = SHA-1 of the ordinal-sorted "name:hash" lines joined by '\n'.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

namespace B25HTools
{
    public static class AtlasGuard1816
    {
        public const double Q = 65536.0;

        public static string PartHash(IEnumerable<Vector2> uvs, out int n)
        {
            var set = new HashSet<long>();
            foreach (var u in uvs)
            {
                long a = (long)Math.Floor((double)u.x * Q), b = (long)Math.Floor((double)u.y * Q);
                set.Add((a << 32) ^ (b & 0xffffffffL));
            }
            var list = set.Select(k => ((int)(k >> 32), (int)(k & 0xffffffffL))).OrderBy(p => p.Item1).ThenBy(p => p.Item2).ToList();
            n = list.Count;
            var buf = new byte[list.Count * 8];
            for (int i = 0; i < list.Count; i++)
            {
                BitConverter.GetBytes(list[i].Item1).CopyTo(buf, i * 8);       // little-endian on every Unity editor platform we use
                BitConverter.GetBytes(list[i].Item2).CopyTo(buf, i * 8 + 4);
            }
            using (var sha = SHA1.Create()) return Hex(sha.ComputeHash(buf)).Substring(0, 16);
        }

        public static string AtlasHash(IDictionary<string, string> parts)
        {
            var lines = parts.Select(kv => kv.Key + ":" + kv.Value).ToList();
            lines.Sort(string.CompareOrdinal);
            using (var sha = SHA1.Create()) return Hex(sha.ComputeHash(Encoding.UTF8.GetBytes(string.Join("\n", lines)))).Substring(0, 16);
        }

        static string Hex(byte[] b) => string.Concat(b.Select(x => x.ToString("x2")));

        static string Sha12(string path)
        {
            using (var sha = SHA256.Create()) return Hex(sha.ComputeHash(File.ReadAllBytes(path))).Substring(0, 12);
        }

        public const int Cell = 4096;
        public const float CoverModel = 0.99f, CoverManifest = 0.95f;

        static uint CellOf(Vector2 u) => ((uint)((long)Math.Floor((double)u.x * Cell) & 0xFFFF) << 16) | (uint)((long)Math.Floor((double)u.y * Cell) & 0xFFFF);

        public static HashSet<uint> DecodeCells(string b64)
        {
            var set = new HashSet<uint>();
            if (string.IsNullOrEmpty(b64)) return set;
            using (var ds = new DeflateStream(new MemoryStream(Convert.FromBase64String(b64)), CompressionMode.Decompress))
            using (var ms = new MemoryStream())
            {
                ds.CopyTo(ms);
                var b = ms.ToArray();
                for (int i = 0; i + 3 < b.Length; i += 4) set.Add(BitConverter.ToUInt32(b, i));
            }
            return set;
        }

        static string PartName(string unityName, IDictionary<string, string> rename, ICollection<string> known)
        {
            if (rename != null && rename.TryGetValue(unityName, out var rn)) return rn;
            if (known.Contains(unityName)) return unityName;
            foreach (var suf in new[] { "_visible", "_int" })
                if (unityName.EndsWith(suf) && known.Contains(unityName.Substring(0, unityName.Length - suf.Length))) return unityName.Substring(0, unityName.Length - suf.Length);
            return unityName;
        }

        /// UV0 points of the paint sub-meshes under root, per Blender part name (a mesh used by several renderers counts once).
        public static Dictionary<string, HashSet<Vector2>> ModelPoints(GameObject root, Material paint, IDictionary<string, string> rename, ICollection<string> known, params GameObject[] extra)
        {
            var acc = new Dictionary<string, HashSet<Vector2>>();
            var done = new HashSet<(Mesh, int, string)>();
            foreach (var mr in new[] { root }.Concat(extra ?? new GameObject[0]).Where(g => g != null).SelectMany(g => g.GetComponentsInChildren<MeshRenderer>(true)))
            {
                var mf = mr.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                var mats = mr.sharedMaterials;
                var name = PartName(mr.name, rename, known);
                for (int sm = 0; sm < mats.Length && sm < mf.sharedMesh.subMeshCount; sm++)
                {
                    if (mats[sm] != paint || !done.Add((mf.sharedMesh, sm, name))) continue;
                    if (!acc.TryGetValue(name, out var pts)) acc[name] = pts = new HashSet<Vector2>();
                    var uv = mf.sharedMesh.uv;
                    foreach (var i in mf.sharedMesh.GetIndices(sm)) pts.Add(uv[i]);
                }
            }
            return acc;
        }

        /// -> (ok, detail) for a CHECK ALL row
        /// extraRoots: paint parts that live in their own prefab (GA-25X tail-hook mount, spawned on its mount at run time)
        public static (bool, string) Check(GameObject root, Material paint, string manifestPath, IDictionary<string, string> rename = null, params GameObject[] extraRoots)
        {
            if (!File.Exists(manifestPath)) return (false, "no texture manifest " + manifestPath + " - re-bake the textures (the builders write it)");
            var m = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(manifestPath));
            var mpj = ((Newtonsoft.Json.Linq.JObject)m["parts"]).Properties().ToList();
            var mp = mpj.ToDictionary(p => p.Name, p => (string)p.Value["hash"]);
            var pts = ModelPoints(root, paint, rename, mp.Keys, extraRoots);
            var exact = 0; var bad = new List<string>(); var noCells = 0; float worst = 1f;
            foreach (var p in mpj)
            {
                if (!pts.TryGetValue(p.Name, out var set)) continue;
                if (PartHash(set, out _) == (string)p.Value["hash"]) { exact++; continue; }
                var mc = DecodeCells((string)p.Value["cells"]);
                if (mc.Count == 0) { noCells++; bad.Add(p.Name + " (no cells)"); continue; }
                var uc = new HashSet<uint>(set.Select(CellOf));
                int inter = uc.Count(c => mc.Contains(c));
                float cu = uc.Count > 0 ? (float)inter / uc.Count : 0f, cm = (float)inter / mc.Count;
                worst = Mathf.Min(worst, Mathf.Min(cu / CoverModel, cm / CoverManifest));
                if (cu < CoverModel || cm < CoverManifest) bad.Add($"{p.Name} {100 * cu:F0}/{100 * cm:F0} %");
            }
            var missing = mp.Keys.Where(k => !pts.ContainsKey(k)).OrderBy(x => x, StringComparer.Ordinal).ToList();
            var extra = pts.Keys.Where(k => !mp.ContainsKey(k)).OrderBy(x => x, StringComparer.Ordinal).ToList();
            string atlas = (string)m["atlas_hash"];
            var tex = ((Newtonsoft.Json.Linq.JObject)m["textures"]).Properties().ToList();
            var dir = Path.GetDirectoryName(manifestPath);
            var stale = tex.Where(t => (string)t.Value["atlas"] != atlas).Select(t => t.Name).ToList();
            var changed = tex.Where(t => !File.Exists(Path.Combine(dir, t.Name)) || Sha12(Path.Combine(dir, t.Name)) != (string)t.Value["sha"]).Select(t => t.Name).ToList();
            bool ok = pts.Count > 0 && tex.Count > 0 && bad.Count == 0 && missing.Count == 0 && extra.Count == 0 && stale.Count == 0 && changed.Count == 0
                      && AtlasHash(mp) == atlas;
            var d = $"manifest {atlas} ({Path.GetFileName(manifestPath)}): {mp.Count} parts, exact UV0 hash {exact}, texel-cell match {mp.Count - exact - missing.Count - bad.Count}, " +
                    $"moved {bad.Count} [{string.Join(", ", bad.Take(6))}], missing {missing.Count} [{string.Join(", ", missing.Take(4))}], new {extra.Count} [{string.Join(", ", extra.Take(4))}], " +
                    $"{tex.Count} textures: on another atlas [{string.Join(", ", stale.Take(4))}], files changed [{string.Join(", ", changed.Take(4))}]" + (ok ? "" : " - re-bake the textures");
            return (ok, d);
        }
    }
}
