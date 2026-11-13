// 1.9.5 (offline, 2026-11-10): proof of the MSB-17/80 stick and throttle motion on the BUILT prefab (the ColumnCheck189 method). Run after
// FamilyBuild.BuildAll:   unity.sh - <log> -executeMethod B25HTools.ControlCheck195.Run
// The stock driver (decompiled Cockpit.cs, game 0.34.6): Joystick.Animate localEulerAngles = (pitch x range, 0, -roll x range); Throttle.Animate
// (rotation) localEulerAngles = (throttle x range, 0, 0). Stock input signs: ControlInputs.pitch > 0 = PUSH (nose down, ControlsFilter.cs 241; the
// 1.8.12 column lesson), roll > 0 = roll right, throttle 0..1 = idle..full. The SFB-81 (Darkreach) values: joysticks range 12, throttles range 52.
// Rows: two Cockpit.joysticks entries on the stock sfb_joystick meshes, range 12 (the SFB-81 value, sign NOT flipped); push = grip top FORWARD by
// L x sin 12, pull = aft, the stick foot still; roll right = grip top RIGHT, left = left; push + right together; one Cockpit.throttles entry on
// the stock sfb_throttle (rotation, range +52 = the SFB-81 value, sign NOT flipped), full throttle = both lever knobs FORWARD (more power =
// forward), idle = rest; the lever arms ride outside the gate arc at every throttle (radial distance from the pivot axis > the gate radius).
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace B25HTools
{
    public static class ControlCheck195
    {
        public const float StickRange = 12f, ThrottleRange = 52f;     // = msb_spec.SFB_STICK_RANGE / SFB_THROTTLE_RANGE (stub_tests_195 compares)
        public const float GateRadius = 0.163f;                        // = msb_deck195.GATE_R

        static Vector3 StickAngles(float pitch, float roll, float range) => new Vector3(pitch * range, 0f, -roll * range);   // Cockpit.Joystick.Animate
        static Vector3 ThrottleAngles(float thr, float range) => new Vector3(thr * range, 0f, 0f);                          // Cockpit.Throttle.Animate (rotation)

        public static void Run()
        {
            var path = FamilyBuild.FamilyRoot + "/msb17/MSB17.prefab";
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            var rows = new List<(bool, string)>();
            if (prefab == null) { Debug.Log("[B25H] CONTROL195 FAIL no prefab " + path); return; }
            var inst = (GameObject)Object.Instantiate(prefab);
            try
            {
                inst.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                var ck = inst.GetComponentInChildren<Cockpit>(true);
                var so = ck == null ? null : new SerializedObject(ck);
                var js = so?.FindProperty("joysticks"); var th = so?.FindProperty("throttles");
                rows.Add(Row("Cockpit.joysticks: 2 entries (pilot + co-pilot stick)", js != null && js.arraySize == 2, $"{(js == null ? -1 : js.arraySize)}"));
                if (js != null)
                    for (int i = 0; i < js.arraySize; i++)
                    {
                        var e = js.GetArrayElementAtIndex(i);
                        var drv = (Transform)e.FindPropertyRelative("transform").objectReferenceValue; float rg = e.FindPropertyRelative("range").floatValue;
                        var mf = drv != null ? drv.GetComponentInChildren<MeshFilter>(true) : null;
                        string mesh = mf != null && mf.sharedMesh != null ? System.IO.Path.GetFileNameWithoutExtension(AssetDatabase.GetAssetPath(mf.sharedMesh)).Replace("_PLACEHOLDER", "") : "none";
                        string side = drv != null && drv.position.x < 0 ? "L" : "R";
                        rows.Add(Row($"stick {side}: stock {mesh} on {drv?.name}, range {rg} = the SFB-81 value (stock sign, not flipped)", mesh == "sfb_joystick" && Mathf.Approximately(rg, StickRange), ""));
                        if (mf == null) continue;
                        var vs = mf.sharedMesh.vertices; int top = 0; for (int k = 1; k < vs.Length; k++) if (vs[k].y > vs[top].y) top = k;
                        var r0 = drv.localRotation; var foot0 = drv.position;
                        Vector3 Top(float p, float r) { drv.localEulerAngles = StickAngles(p, r, rg); var w = inst.transform.InverseTransformPoint(mf.transform.TransformPoint(vs[top])); drv.localRotation = r0; return w; }
                        var t0 = Top(0, 0); var push = Top(1, 0); var pull = Top(-1, 0); var right = Top(0, 1); var left = Top(0, -1); var both = Top(1, 1);
                        float L = (t0 - inst.transform.InverseTransformPoint(foot0)).magnitude, expect = L * Mathf.Sin(rg * Mathf.Deg2Rad);
                        rows.Add(Row($"stick {side}: pitch +1 (PUSH) -> grip top FORWARD {(push.z - t0.z) * 1000:F0} mm, -1 (pull) -> aft {(pull.z - t0.z) * 1000:F0} mm (lever {L:F2} m x sin 12 = {expect * 1000:F0} mm), no sideways move",
                            push.z - t0.z > 0.7f * expect && pull.z - t0.z < -0.7f * expect && Mathf.Abs(push.x - t0.x) < 0.005f, ""));
                        rows.Add(Row($"stick {side}: roll +1 (right) -> grip top RIGHT {(right.x - t0.x) * 1000:F0} mm, roll -1 left {(left.x - t0.x) * 1000:F0} mm",
                            right.x - t0.x > 0.7f * expect && left.x - t0.x < -0.7f * expect, ""));
                        rows.Add(Row($"stick {side}: push + roll right together -> top forward {(both.z - t0.z) * 1000:F0} mm and right {(both.x - t0.x) * 1000:F0} mm; the stick foot does not move",
                            both.z - t0.z > 0.6f * expect && both.x - t0.x > 0.6f * expect && (drv.position - foot0).magnitude < 1e-5f, ""));
                    }
                rows.Add(Row("Cockpit.throttles: 1 entry (the one centre quadrant)", th != null && th.arraySize == 1, $"{(th == null ? -1 : th.arraySize)}"));
                if (th != null && th.arraySize == 1)
                {
                    var e = th.GetArrayElementAtIndex(0);
                    var drv = (Transform)e.FindPropertyRelative("transform").objectReferenceValue; float rg = e.FindPropertyRelative("range").floatValue;
                    bool rot = e.FindPropertyRelative("rotation").boolValue, mot = e.FindPropertyRelative("motion").boolValue;
                    var mf = drv != null ? drv.GetComponentInChildren<MeshFilter>(true) : null;
                    string mesh = mf != null && mf.sharedMesh != null ? System.IO.Path.GetFileNameWithoutExtension(AssetDatabase.GetAssetPath(mf.sharedMesh)).Replace("_PLACEHOLDER", "") : "none";
                    rows.Add(Row($"throttle: stock {mesh} on {drv?.name}, rotation {rot}, motion {mot}, range {rg} = the SFB-81 value (+52: stock sign, not flipped)", mesh == "sfb_throttle" && rot && !mot && Mathf.Approximately(rg, ThrottleRange), ""));
                    if (mf != null)
                    {
                        var vs = mf.sharedMesh.vertices;
                        var knobs = Enumerable.Range(0, vs.Length).Where(k => vs[k].y > 0.19f).ToList();
                        var r0 = drv.localRotation;
                        Vector3 Knob(float t, bool left) { drv.localEulerAngles = ThrottleAngles(t, rg); var pts = knobs.Where(k => (vs[k].x < 0) == left).Select(k => inst.transform.InverseTransformPoint(mf.transform.TransformPoint(vs[k]))).ToList(); drv.localRotation = r0; return pts.Aggregate(Vector3.zero, (a, b) => a + b) / Mathf.Max(1, pts.Count); }
                        var l0 = Knob(0, true); var l1 = Knob(1, true); var rr0 = Knob(0, false); var rr1 = Knob(1, false); var lh = Knob(0.5f, true);
                        rows.Add(Row($"throttle FULL (1) -> both lever knobs FORWARD: L {(l1.z - l0.z) * 1000:F0} mm, R {(rr1.z - rr0.z) * 1000:F0} mm (more power = forward); half throttle in between ({(lh.z - l0.z) * 1000:F0} mm)",
                            l1.z - l0.z > 0.03f && rr1.z - rr0.z > 0.03f && lh.z > l0.z && lh.z < l1.z, $"knob height idle {l0.y:F3} full {l1.y:F3}"));
                        rows.Add(Row("throttle idle (0) = the rest pose (the lever transform at identity)", Quaternion.Angle(drv.localRotation, Quaternion.identity) < 0.01f, ""));
                        // the lever arms (vertices above the pivot) ride outside the gate arc: radial distance from the pivot axis, invariant under the rotation
                        var arms = Enumerable.Range(0, vs.Length).Where(k => vs[k].y > 0.05f).Select(k => new Vector2(vs[k].y, vs[k].z).magnitude).ToList();
                        float rmin = arms.Count > 0 ? arms.Min() : 0f;
                        rows.Add(Row($"throttle levers ride outside the gate arc at every throttle: min radius from the pivot axis {rmin * 1000:F0} mm > gate {GateRadius * 1000:F0} mm + 3", rmin > GateRadius + 0.003f, ""));
                        {   // 1.9.7: each lever arm stands IN its slot of the quadrant housing at idle / half / full: housing-top vertices (cockpit_pedestal, normal
                            // pointing away from the pivot axis) lie above the arm foot right beside the arm, and none lies in the arm's path
                            var ped = inst.GetComponentsInChildren<MeshFilter>(true).FirstOrDefault(m => m.name == "cockpit_pedestal");
                            var pm = ped != null ? ped.sharedMesh : null; bool okQ = pm != null; string detQ = "no cockpit_pedestal";
                            if (pm != null)
                            {
                                var pv = pm.vertices; var pn = pm.normals; var toDrv = drv.worldToLocalMatrix * ped.transform.localToWorldMatrix;
                                var top = new List<Vector3>();      // (x across, radius from the pivot axis, angle deg in the lever's rotation sense)
                                for (int i = 0; i < pv.Length; i++)
                                {
                                    var q = toDrv.MultiplyPoint3x4(pv[i]); var nn = toDrv.MultiplyVector(pn[i]).normalized; float rr = new Vector2(q.y, q.z).magnitude;
                                    if (rr < 0.15f || rr > 0.26f || Mathf.Abs(q.x) > 0.12f) continue;
                                    if (Vector3.Dot(nn, new Vector3(0f, q.y, q.z).normalized) < 0.9f) continue;
                                    top.Add(new Vector3(q.x, rr, Mathf.Atan2(q.z, q.y) * Mathf.Rad2Deg));
                                }
                                var foot = Enumerable.Range(0, vs.Length).Where(k2 => new Vector2(vs[k2].y, vs[k2].z).magnitude < rmin + 0.02f).ToList();
                                float ax0 = foot.Min(k2 => Mathf.Abs(vs[k2].x)), ax1 = foot.Max(k2 => Mathf.Abs(vs[k2].x));
                                float rTop = top.Count > 0 ? top.Max(t => t.y) : 0f; float worstSink = float.MaxValue; int inPath = 0;
                                foreach (var thr in new[] { 0f, 0.5f, 1f })
                                {   // Throttle.Animate: rotation about local +X by thr x range: a point at angle atan2(z, y) moves to that angle + thr x range
                                    var fa = foot.Select(k2 => Mathf.Atan2(vs[k2].z, vs[k2].y) * Mathf.Rad2Deg + thr * rg).ToList();
                                    float a0 = fa.Min(), a1 = fa.Max();
                                    var beside = top.Where(t => t.z > a0 - 6f && t.z < a1 + 6f && Mathf.Abs(Mathf.Abs(t.x) - (ax0 + ax1) / 2f) < 0.03f && (Mathf.Abs(t.x) < ax0 - 0.001f || Mathf.Abs(t.x) > ax1 + 0.001f) && t.y > rmin).ToList();
                                    worstSink = Mathf.Min(worstSink, beside.Count > 0 ? beside.Max(t => t.y) - rmin : -1f);
                                    inPath += top.Count(t => t.z > a0 + 0.5f && t.z < a1 - 0.5f && Mathf.Abs(t.x) > ax0 + 0.0005f && Mathf.Abs(t.x) < ax1 - 0.0005f && t.y > rmin);
                                }
                                okQ = worstSink >= 0.012f && inPath == 0;
                                detQ = $"arm foot r {rmin * 1000:F0} mm, |x| {ax0 * 1000:F0}-{ax1 * 1000:F0}; housing top r {rTop * 1000:F0}; arm sunk >= {worstSink * 1000:F0} mm at idle / half / full; housing-top vertices in the arm's path {inPath}";
                            }
                            rows.Add(Row("1.9.7 throttle levers stand IN the quadrant gate at idle / half / full: the housing top beside each arm is >= 12 mm above the arm foot, nothing of the top in the arm's path", okQ, detQ));
                        }
                    }
                }
            }
            finally { Object.DestroyImmediate(inst); }
            foreach (var r in rows) Debug.Log("[B25H] CONTROL195 " + r.Item2);
            int pass = rows.Count(r => r.Item1);
            Debug.Log($"[B25H] CONTROL195 {pass}/{rows.Count} {(pass == rows.Count ? "PASS" : "FAIL")}");
        }

        static (bool, string) Row(string what, bool ok, string detail) => (ok, $"{(ok ? "PASS" : "FAIL")} {what} : {detail}");
    }
}
