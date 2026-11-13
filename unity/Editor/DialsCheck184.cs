// 1.8.4 (offline C, 2026-11-08): dial check rows on the BUILT family prefabs. Run after FamilyBuild.BuildAll:
//   unity.sh - <log> -executeMethod B25HTools.DialsCheck184.Run
// For every dial the 1.8.2 in-game round found dead, proves that the prefab carries the mover the B25H.Instruments 1.8.4 plugin binds by
// name (a transform with a non-empty mesh + material, its cockpit-layer copy where the aircraft uses copies) and the component the plugin
// reads its value from (ConstantSpeedProp per engine for the rpm / oil-pressure needles, TurbineEngine + tac page for the Ng panels).
// The name lists equal the plugin's (src/B25H.Instruments: Dials184.cs B25HExtraNames / GA25XExtraNames, B17G.cs B17GNames, Nimrod.cs
// NimrodNames); tools/dials184_stub_test.py compares them. Writes "[B25H] DIALS184 <aircraft> <n>/<m> PASS|FAIL" and one line per row.
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace B25HTools
{
    public static class DialsCheck184
    {
        public static readonly string[] B25H = {
            "gauge_oil_press_needle", "gauge_oil_temp_needle", "gauge_cyl_temp_needle", "gauge_hydraulic_needle", "gauge_flaps_pos_needle", "gauge_gear_pos_needle",
            "gauge_clock_needle", "gauge_clock_needle_short", "gauge_suction_L_needle", "gauge_suction_C_needle", "gauge_ammeter_needle", "gauge_brake_press_needle",
            "gauge_volts_needle", "gauge_carb_temp_L_needle", "gauge_carb_temp_R_needle", "gauge_free_air_L_needle", "gauge_free_air_R_needle",
            "gauge_compass_card", "gauge_deicer_L_needle", "gauge_deicer_R_needle", "gauge_oxygen_needle" };
        public static readonly string[] GA25X = { "gauge_isis_att_card", "gauge_isis_hdg_card", "gauge_isis_tq_L_needle", "gauge_isis_tq_R_needle", "gauge_isis_fuel_bar" };
        public static readonly string[] B17G = {
            "gauge_rpm_1_needle", "gauge_rpm_2_needle", "gauge_rpm_3_needle", "gauge_rpm_4_needle", "gauge_att_card",
            "gauge_suction_needle", "gauge_hyd_needle", "gauge_clock_needle", "gauge_clock_needle_short", "gauge_clock_sec_needle",
            "gauge_egu_1_fuel_needle", "gauge_egu_1_oilp_needle", "gauge_egu_1_oilt_needle", "gauge_egu_2_fuel_needle", "gauge_egu_2_oilp_needle", "gauge_egu_2_oilt_needle",
            "gauge_egu_3_fuel_needle", "gauge_egu_3_oilp_needle", "gauge_egu_3_oilt_needle", "gauge_egu_4_fuel_needle", "gauge_egu_4_oilp_needle", "gauge_egu_4_oilt_needle",
            "gauge_oilt_1_needle", "gauge_oilt_2_needle", "gauge_oilt_3_needle", "gauge_oilt_4_needle" };
        public static readonly string[] NIMROD = { "gauge_rpm_needle", "gauge_oilp_needle" };
        static readonly List<string> log = new List<string>();

        public static void Run()
        {
            bool ok = true;
            ok &= Check("B25H", FamilyBuild.FamilyRoot + "/b25h/B25H.prefab", B25H, true, inst => new[] {
                Row("two ConstantSpeedProp (rpm / suction / oil P / de-icer source)", inst.GetComponentsInChildren<ConstantSpeedProp>(true).Length == 2, $"{inst.GetComponentsInChildren<ConstantSpeedProp>(true).Length}"),
                Row("two TurbineEngine (power: temperatures, ammeter)", inst.GetComponentsInChildren<TurbineEngine>(true).Length == 2, $"{inst.GetComponentsInChildren<TurbineEngine>(true).Length}") });
            ok &= Check("GA25X", FamilyBuild.FamilyRoot + "/ga25x/GA25X.prefab", GA25X, true, inst => new[] {
                Row("engine_L / engine_R TurbineEngine (torque pointers by name suffix, Ng panel)", inst.GetComponentsInChildren<TurbineEngine>(true).Select(t => t.name).Count(n => n.EndsWith("_L") || n.EndsWith("_R")) == 2,
                    string.Join(",", inst.GetComponentsInChildren<TurbineEngine>(true).Select(t => t.name))),
                Row("ConstantSpeedProp present (tac page power panel source)", inst.GetComponentsInChildren<ConstantSpeedProp>(true).Length >= 1, ""),
                TacRow(inst) });
            ok &= Check("B17G", FamilyBuild.FamilyRoot + "/b17g/B17G.prefab", B17G, true, inst => {
                var props = inst.GetComponentsInChildren<ConstantSpeedProp>(true).Select(p => p.name).ToList();
                return new[] { Row("prop_1..4 carry a ConstantSpeedProp (per-engine rpm source)", Enumerable.Range(1, 4).All(n => props.Contains("prop_" + n)), string.Join(",", props)) };
            });
            ok &= Check("NIMROD1", FamilyBuild.FamilyRoot + "/nimrod/NIMROD1.prefab", NIMROD, false, inst => new[] {
                Row("one ConstantSpeedProp (rpm / oil P source)", inst.GetComponentsInChildren<ConstantSpeedProp>(true).Length == 1, $"{inst.GetComponentsInChildren<ConstantSpeedProp>(true).Length}") });
            ok &= Check("FD32", FamilyBuild.FamilyRoot + "/fd32/FD32.prefab", new string[0], false, inst => new[] {
                Row("TurbineEngine present (Ng on the tac page turbine panel)", inst.GetComponentsInChildren<TurbineEngine>(true).Length >= 1, ""),
                TacRow(inst) });
            Debug.Log($"[B25H] DIALS184 ALL {(ok ? "PASS" : "FAIL")}");
        }

        static (bool, string) Row(string what, bool pass, string detail) => (pass, $"{(pass ? "PASS" : "FAIL")} {what} : {detail}");

        static (bool, string) TacRow(GameObject inst)
        {
            var ck = inst.GetComponentInChildren<Cockpit>(true);
            var tac = ck == null ? null : new SerializedObject(ck).FindProperty("tacScreenUIPrefab")?.objectReferenceValue as GameObject;
            var tels = tac == null ? new EngineTelemetry[0] : tac.GetComponentsInChildren<EngineTelemetry>(true);
            var names = tels.Select(t => new SerializedObject(t).FindProperty("engineName")?.stringValue).ToList();
            return Row("tac page has the EngineTelemetry 'COIN' (turbine) panel the plugin binds + overrides with Ng", names.Contains("COIN"), $"{tac?.name}: {string.Join(",", names)}");
        }

        static bool Check(string key, string path, string[] names, bool copies, System.Func<GameObject, (bool, string)[]> extra)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (prefab == null) { Debug.Log($"[B25H] DIALS184 {key} FAIL no prefab {path}"); return false; }
            var inst = (GameObject)Object.Instantiate(prefab);
            var rows = new List<(bool, string)>();
            try
            {
                var all = inst.GetComponentsInChildren<Transform>(true);
                foreach (var n in names)
                {
                    var t = all.FirstOrDefault(x => x.name == n);
                    var mf = t == null ? null : t.GetComponent<MeshFilter>();
                    var mr = t == null ? null : t.GetComponent<MeshRenderer>();
                    bool mesh = mf != null && mf.sharedMesh != null && mf.sharedMesh.vertexCount > 0 && mr != null && mr.sharedMaterials.Length > 0 && mr.sharedMaterials.All(m => m != null);
                    string d = t == null ? "missing" : $"verts {(mf != null && mf.sharedMesh != null ? mf.sharedMesh.vertexCount : 0)}, mat {(mr != null && mr.sharedMaterial != null ? mr.sharedMaterial.name : "-")}";
                    if (copies)
                    {
                        var c = t == null ? null : t.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == n + "_int");
                        bool cok = c != null && c.gameObject.layer == 3 && c.GetComponent<MeshRenderer>() != null;
                        rows.Add(Row($"{n}: mover with mesh + cockpit-layer copy (plugin binding by name)", mesh && cok, d + (cok ? ", _int layer 3" : ", NO _int copy on layer 3")));
                    }
                    else rows.Add(Row($"{n}: mover with mesh (plugin binding by name)", mesh, d));
                }
                rows.AddRange(extra(inst));
            }
            finally { Object.DestroyImmediate(inst); }
            int pass = rows.Count(r => r.Item1);
            foreach (var r in rows) Debug.Log($"[B25H] DIALS184 {key} {r.Item2}");
            Debug.Log($"[B25H] DIALS184 {key} {pass}/{rows.Count} {(pass == rows.Count ? "PASS" : "FAIL")}");
            return pass == rows.Count;
        }
    }
}
