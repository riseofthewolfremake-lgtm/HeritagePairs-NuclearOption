// 1.8.9 (offline J, 2026-11-08): proof of the B-17G control column / wheel motion on the BUILT prefab. Run after FamilyBuild.BuildAll:
//   unity.sh - <log> -executeMethod B25HTools.ColumnCheck189.Run
// User on 1.8.8: "The WHEEL moves, the stick does not" (the wheels sat on Cockpit.joysticks at their hubs). 1.8.9: no joysticks; the
// B25H.Instruments B17G branch sets column.localRotation = rest * AngleAxis(+pitch * 12, right) (1.8.12; was -pitch, backwards) and wheel.localRotation = rest *
// AngleAxis(roll * 30, right) (B17G.cs B17GMath.ColumnDeg / WheelDeg; the constants are copied here and compared by tools/stub_tests_189j.py).
// Rows: pitch +1 (push) moves the wheel hub FORWARD about the floor pivot and +1 aft, by the column length x sin 12; roll +1 turns the wheel
// clockwise seen by the pilot (its top goes right), the hub and the wheel axis stay put (no yaw); pitch keeps the wheel axis in the
// column's pitch plane (no yaw); no Cockpit.joysticks entry and no ControlSurface left on the columns / wheels.
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace B25HTools
{
    public static class ColumnCheck189
    {
        public const float ColumnRange = 12f, WheelRange = 30f;     // = B17GMath.ColumnRange / WheelRange
        static float ColumnDeg(float pitch) => Mathf.Clamp(pitch, -1f, 1f) * ColumnRange;     // 1.8.12: + pitch = PUSH (stock CI-22 stick sign)
        static float WheelDeg(float roll) => Mathf.Clamp(roll, -1f, 1f) * WheelRange;

        public static void Run()
        {
            var path = FamilyBuild.FamilyRoot + "/b17g/B17G.prefab";
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            var rows = new List<(bool, string)>();
            if (prefab == null) { Debug.Log("[B25H] COLUMN189 FAIL no prefab " + path); return; }
            var inst = (GameObject)Object.Instantiate(prefab);
            try
            {
                inst.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                var all = inst.GetComponentsInChildren<Transform>(true);
                var ck = inst.GetComponentInChildren<Cockpit>(true);
                var js = ck == null ? null : new SerializedObject(ck).FindProperty("joysticks");
                rows.Add(Row("no Cockpit.joysticks entry (the plugin moves columns and wheels)", js != null && js.arraySize == 0, $"{(js == null ? -1 : js.arraySize)}"));
                foreach (var side in new[] { "L", "R" })
                {
                    var col = all.FirstOrDefault(t => t.name == "cockpit_column_" + side);
                    var yk = all.FirstOrDefault(t => t.name == "cockpit_yoke_" + side);
                    if (col == null || yk == null) { rows.Add(Row($"{side}: column and wheel present", false, "missing")); continue; }
                    rows.Add(Row($"{side}: wheel is a child of the column (the column carries it)", yk.IsChildOf(col), yk.parent.name));
                    rows.Add(Row($"{side}: no ControlSurface on the column / wheel", col.GetComponents<ControlSurface>().Length == 0 && yk.GetComponents<ControlSurface>().Length == 0, ""));
                    var cRest = col.localRotation; var yRest = yk.localRotation;
                    Vector3 piv0 = col.position, hub0 = yk.position, ax0 = yk.right, top0 = yk.position + yk.up * 0.1f;
                    float L = Vector3.Distance(piv0, hub0);
                    System.Func<float, float, (Vector3 piv, Vector3 hub, Vector3 ax, Vector3 top, float wheelAng)> pose = (p, r) =>
                    {
                        col.localRotation = cRest * Quaternion.AngleAxis(ColumnDeg(p), Vector3.right);
                        yk.localRotation = yRest * Quaternion.AngleAxis(WheelDeg(r), Vector3.right);
                        var res = (col.position, yk.position, yk.right, yk.position + yk.up * 0.1f, 0f);
                        col.localRotation = cRest; yk.localRotation = yRest;
                        return res;
                    };
                    var push = pose(1, 0); var pull = pose(-1, 0);
                    float dz = push.hub.z - hub0.z, dzp = pull.hub.z - hub0.z, expect = L * Mathf.Sin(ColumnRange * Mathf.Deg2Rad);
                    rows.Add(Row($"{side}: pitch +1 (push) -> hub FORWARD {dz * 1000:F0} mm, -1 (pull) -> aft {dzp * 1000:F0} mm (column {L:F2} m x sin 12 = {expect * 1000:F0} mm), floor pivot still",
                        dz > 0.7f * expect && dzp < -0.7f * expect && (push.piv - piv0).magnitude < 1e-4f && Mathf.Abs(push.hub.x - hub0.x) < 0.002f, $"hub x shift {(push.hub.x - hub0.x) * 1000:F1} mm"));
                    float axYawPush = Vector3.Angle(Vector3.ProjectOnPlane(push.ax, Vector3.up), Vector3.ProjectOnPlane(ax0, Vector3.up));
                    rows.Add(Row($"{side}: pitch keeps the wheel axis in the fore-aft plane (no yaw): axis x {ax0.x:F3} -> {push.ax.x:F3} / {pull.ax.x:F3}",
                        Mathf.Abs(push.ax.x - ax0.x) < 0.005f && Mathf.Abs(pull.ax.x - ax0.x) < 0.005f, $"plan-view axis turn {axYawPush:F2} deg"));
                    var rr = pose(0, 1); var rl = pose(0, -1);
                    float turn = Vector3.SignedAngle(top0 - hub0, rr.top - rr.hub, ax0);
                    rows.Add(Row($"{side}: roll +1 -> wheel top moves RIGHT {(rr.top.x - top0.x) * 1000:F1} mm (clockwise seen by the pilot), roll -1 left {(rl.top.x - top0.x) * 1000:F1} mm, {Mathf.Abs(turn):F1} deg about the hub axis",
                        rr.top.x - top0.x > 0.02f && rl.top.x - top0.x < -0.02f && Mathf.Abs(Mathf.Abs(turn) - WheelRange) < 0.5f, ""));
                    rows.Add(Row($"{side}: roll moves neither the hub nor the wheel axis (no stray yaw / pitch)", (rr.hub - hub0).magnitude < 1e-4f && Vector3.Angle(rr.ax, ax0) < 0.01f, $"hub {(rr.hub - hub0).magnitude * 1000:F2} mm, axis {Vector3.Angle(rr.ax, ax0):F3} deg"));
                    var both = pose(1, 1);     // push + roll right
                    rows.Add(Row($"{side}: push + roll right together: hub forward {(both.hub.z - hub0.z) * 1000:F0} mm and the wheel top right of the pushed pose",
                        both.hub.z - hub0.z > 0.7f * expect && (both.top - both.hub).x > (push.top - push.hub).x + 0.02f, ""));
                }
            }
            finally { Object.DestroyImmediate(inst); }
            foreach (var r in rows) Debug.Log("[B25H] COLUMN189 " + r.Item2);
            int pass = rows.Count(r => r.Item1);
            Debug.Log($"[B25H] COLUMN189 {pass}/{rows.Count} {(pass == rows.Count ? "PASS" : "FAIL")}");
        }

        static (bool, string) Row(string what, bool ok, string detail) => (ok, $"{(ok ? "PASS" : "FAIL")} {what} : {detail}");
    }
}
