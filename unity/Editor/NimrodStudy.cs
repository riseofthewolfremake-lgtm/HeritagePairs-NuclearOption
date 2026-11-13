// Study tool (offline worker, Nimrod design): load an installed community Blueprinter addon (.nobp = UnityFS bundle) read-only
// and dump how its aircraft is set up (taildragger gear, spawn offset / rest rotation, prop, engine, aero parts, FBW, AI
// parameters). Nothing is copied into our project; the dump is text in nuclearoption-ref\unitylogs.
//
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 NimrodStudy.DumpCamel nimrod_study_camel
using System;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class NimrodStudy
    {
        const string Camel = @"C:\Program Files (x86)\Steam\steamapps\common\Nuclear Option\BepInEx\disabledPlugins\CI23Camel\CI-23.Camel_1.2.2.nobp";
        const string Out = @"C:\Users\User\nuclearoption-ref\unitylogs\nimrod_study_camel.txt";

        public static void DumpCamel() => Dump(Camel, Out);

        static void Props(StringBuilder sb, Object o, string indent, int maxLines = 400)
        {
            var so = new SerializedObject(o); var it = so.GetIterator(); bool enter = true; int n = 0;
            while (it.Next(enter) && n < maxLines)
            {
                enter = it.propertyType != SerializedPropertyType.String && it.propertyType != SerializedPropertyType.AnimationCurve;
                if (it.propertyPath.StartsWith("m_") && it.depth == 0 && it.propertyPath != "m_Name") continue;
                string val;
                switch (it.propertyType)
                {
                    case SerializedPropertyType.ObjectReference: val = it.objectReferenceValue ? it.objectReferenceValue.name + " (" + it.objectReferenceValue.GetType().Name + ")" : "null"; enter = false; break;
                    case SerializedPropertyType.Float: val = it.floatValue.ToString("R"); break;
                    case SerializedPropertyType.Integer: val = it.longValue.ToString(); break;
                    case SerializedPropertyType.Boolean: val = it.boolValue ? "1" : "0"; break;
                    case SerializedPropertyType.String: val = it.stringValue; break;
                    case SerializedPropertyType.Enum: val = it.enumValueIndex.ToString(); break;
                    case SerializedPropertyType.Vector3: val = it.vector3Value.ToString("F3"); enter = false; break;
                    case SerializedPropertyType.Vector2: val = it.vector2Value.ToString("F3"); enter = false; break;
                    case SerializedPropertyType.Quaternion: val = it.quaternionValue.eulerAngles.ToString("F2"); enter = false; break;
                    case SerializedPropertyType.AnimationCurve: val = string.Join(" ", it.animationCurveValue.keys.Select(k => $"({k.time:F3},{k.value:F3})")); break;
                    case SerializedPropertyType.ArraySize: val = it.intValue.ToString(); break;
                    case SerializedPropertyType.Generic: continue;
                    default: val = "(" + it.propertyType + ")"; enter = false; break;
                }
                sb.Append(indent).Append(it.propertyPath).Append(" = ").Append(val).Append('\n'); n++;
            }
        }

        public static void Dump(string bundlePath, string outFile)
        {
            var sb = new StringBuilder();
            AssetBundle.UnloadAllAssetBundles(true);
            var ab = AssetBundle.LoadFromFile(bundlePath);
            if (ab == null) throw new Exception("could not load " + bundlePath);
            try
            {
                var names = ab.GetAllAssetNames();
                sb.Append("assets ").Append(names.Length).Append('\n');
                foreach (var n in names) sb.Append("  ").Append(n).Append('\n');
                foreach (var def in ab.LoadAllAssets<AircraftDefinition>())
                {
                    sb.Append("\n##### AircraftDefinition ").Append(def.name).Append('\n');
                    Props(sb, def, "  ");
                    if (def.aircraftParameters != null) { sb.Append("  --- parameters\n"); Props(sb, def.aircraftParameters, "    ", 300); }
                    var pf = def.unitPrefab;
                    if (pf == null) continue;
                    sb.Append("  --- prefab ").Append(pf.name).Append('\n');
                    foreach (var t in pf.GetComponentsInChildren<Transform>(true))
                    {
                        var path = AnimationUtility.CalculateTransformPath(t, pf.transform);
                        var comps = t.GetComponents<Component>().Where(c => c != null && !(c is Transform) && !(c is MeshFilter) && !(c is MeshRenderer)).ToList();
                        var mf = t.GetComponent<MeshFilter>();
                        sb.Append($"  [{path}] pos {pf.transform.InverseTransformPoint(t.position).ToString("F3")} rot {t.rotation.eulerAngles.ToString("F1")} {(mf && mf.sharedMesh ? "mesh " + mf.sharedMesh.name + " v" + mf.sharedMesh.vertexCount : "")} : {string.Join(", ", comps.Select(c => c.GetType().Name))}\n");
                        foreach (var c in comps)
                        {
                            var tn = c.GetType().Name;
                            if (tn == "AeroPart" || tn == "LandingGear" || tn == "ConstantSpeedProp" || tn == "TurbineEngine" || tn == "ControlsFilter" || tn == "ControlSurface" || tn == "Gun" || tn == "TailHook" || tn == "Transmission" || tn == "PistonEngine" || tn == "FuelTank" || tn == "Rigidbody" || tn == "HighLiftDevice" || tn == "AutopilotPlane" || tn == "PropFan")
                            { sb.Append("    <").Append(tn).Append(">\n"); Props(sb, c, "      ", 250); }
                        }
                    }
                }
            }
            finally { ab.Unload(true); }
            File.WriteAllText(outFile, sb.ToString());
            Debug.Log("[B25H] NIMROD STUDY dump " + bundlePath + " -> " + outFile);
        }
    }
}
