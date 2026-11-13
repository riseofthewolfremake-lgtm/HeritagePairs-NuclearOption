// 1.9.11 (user: "the FD-32 spawns on a carrier's elevator, the tail rudder gets damaged, sometimes it snaps off"): build check for the
// spawn position of the two taildraggers on the stock carrier lifts.
//
// Two stock lifts (hangar_R1 of the Annex and of the Hyperion) carry an invisible solid box named "backstop" behind the spawn point.
// The game spawns an aircraft at spawnTransform + up * spawnOffset.y + forward * spawnOffset.z, rotated by restRotation, and the lift starts
// to rise in the same frame. A low tail that reaches back over the backstop comes down on it. This check measures, from the rudder's
// collider mesh and from the stock carrier prefabs (Blueprinter placeholder copies of the user's own game; nothing of them is stored), how
// far the rudder's aft end is AHEAD of each backstop's front-most point, in plan view (heights do not enter: the margin holds for any
// tail-down attitude and is the distance the aircraft may roll back before the rudder is over the box).
//
// Used by FD32Build / NimrodBuild check rows: margin >= MinMargin on every stock backstop.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;

namespace B25HTools
{
    public static class LiftSpawn1911
    {
        public const float MinMargin = 0.30f;      // m, rudder aft end ahead of the nearest backstop face in the spawn pose
        static readonly string[] Carriers = { "AssaultCarrier1", "FleetCarrier1", "SmallCarrier1" };
        const string DNS = "Assets/Blueprinter/_donotship";

        static object F(object o, string n)
        {
            for (var t = o.GetType(); t != null; t = t.BaseType)
            {
                var f = t.GetField(n, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (f != null) return f.GetValue(o);
            }
            return null;
        }

        /// every stock lift backstop: (carrier / hangar name, front-most z of the box in the hangar's spawn frame, its top above the spawn point)
        public static List<(string name, float faceZ, float topY)> Backstops()
        {
            var list = new List<(string, float, float)>();
            foreach (var c in Carriers)
            {
                var go = AssetDatabase.LoadAssetAtPath<GameObject>($"{DNS}/GameObject/{c}_PLACEHOLDER.prefab");
                if (go == null) continue;
                foreach (var h in go.GetComponentsInChildren<Hangar>(true))
                {
                    var st = F(h, "spawnTransform") as Transform;
                    var doors = F(h, "doors") as IEnumerable;
                    if (st == null || doors == null) continue;
                    foreach (var d in doors)
                    {
                        var dt = d == null ? null : F(d, "transform") as Transform;
                        if (dt == null) continue;
                        foreach (var box in dt.GetComponentsInChildren<BoxCollider>(true).Where(b => b.name == "backstop" && !b.isTrigger && b.enabled))
                        {
                            float z = float.NegativeInfinity, y = float.NegativeInfinity;
                            for (int i = 0; i < 8; i++)
                            {
                                var corner = box.center + Vector3.Scale(box.size * 0.5f, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                                var p = st.InverseTransformPoint(box.transform.TransformPoint(corner));
                                z = Mathf.Max(z, p.z); y = Mathf.Max(y, p.y);
                            }
                            list.Add(($"{c}/{h.name}", z, y));
                        }
                    }
                }
            }
            return list;
        }

        /// aft-most z of the part's solid colliders in the spawn pose (spawn frame: origin at the hangar's spawn point, z forward)
        public static float AftEnd(Transform root, Transform part, Vector3 spawnOffset, Vector3 restRotation)
        {
            var q = Quaternion.Euler(restRotation);
            float z = float.PositiveInfinity;
            foreach (var mc in part.GetComponents<MeshCollider>().Where(m => m.enabled && !m.isTrigger && m.sharedMesh != null))
                foreach (var v in mc.sharedMesh.vertices)
                    z = Mathf.Min(z, (q * root.InverseTransformPoint(mc.transform.TransformPoint(v))).z + spawnOffset.z);
            return z;
        }

        /// (ok, text): the rudder's aft end is at least MinMargin ahead of every stock backstop; fails when fewer than two backstops are found
        /// (the stock carriers changed: measure again)
        public static (bool, string) Check(Transform root, Transform rudder, Vector3 spawnOffset, Vector3 restRotation)
        {
            var bs = Backstops();
            if (rudder == null) return (false, "no rudder");
            float aft = AftEnd(root, rudder, spawnOffset, restRotation);
            var rows = bs.Select(b => (b.name, margin: aft - b.faceZ, b.faceZ, b.topY)).ToList();
            bool ok = bs.Count >= 2 && !float.IsInfinity(aft) && rows.All(r => r.margin >= MinMargin);
            return (ok, $"spawnOffset.z {spawnOffset.z:F2}: rudder aft end z {aft:F3}; " + string.Join("; ", rows.Select(r => $"{r.name} backstop face z {r.faceZ:F3} (top {r.topY:F2} m) margin {r.margin:F3} m")) +
                $" ({bs.Count} stock backstops, need >= {MinMargin:F2} m)");
        }
    }
}
