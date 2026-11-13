// Offline cockpit screenshots of the BUILT GA-25X prefab in the Unity editor (offline worker, 0.3.1 cockpit kitbash).
// Needs a graphics device: run Unity in batch mode WITHOUT -nographics, e.g.
//   "C:\Program Files\Unity 2022.3.62f2\Editor\Unity.exe" -batchmode -quit -projectPath <Blueprinter-Editor>
//       -executeMethod B25HTools.GA25XCockpitShot.Shoot -logFile <log> -shotDir <folder>
// Shows the cockpit renderers (Aircraft.cockpitRenderers on, exteriorRenderers off, as in cockpit view), hides the crew
// figures' bodies (the stock seats stay), and renders from the pilot and WSO eyes plus an overview with the canopy hidden.
// Placeholder shaders/materials render as the Blueprinter project has them (editor preview), not exactly as in game.
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class GA25XCockpitShot
    {
        public static void Shoot()
        {
            var args = Environment.GetCommandLineArgs();
            int k = Array.IndexOf(args, "-shotDir");
            var dir = k >= 0 ? args[k + 1] : Path.GetFullPath("cockpit_shots");
            Directory.CreateDirectory(dir);
            ShaderUtil.allowAsyncCompilation = false;   // batch mode: compile every shader variant before the first Camera.Render
            var path = FamilyBuild.FamilyRoot + "/ga25x/GA25X.prefab";
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (prefab == null) throw new Exception("no prefab " + path);
            var inst = (GameObject)Object.Instantiate(prefab);
            inst.transform.position = Vector3.zero; inst.transform.rotation = Quaternion.identity;
            var ac = inst.GetComponent<Aircraft>();
            foreach (var r in ((Renderer[])Get(ac, "exteriorRenderers")).Where(r => r != null)) r.enabled = false;
            foreach (var r in ((Renderer[])Get(ac, "cockpitRenderers")).Where(r => r != null)) r.enabled = true;
            foreach (var p in ac.pilots) foreach (var sr in p.GetComponentsInChildren<SkinnedMeshRenderer>(true)) sr.enabled = false;
            // The Blueprinter placeholder for Shader Graphs/Lit_vertexcolor is an unlit texture preview (no vertex colour): for these
            // shots only, the stock aircraft_structure faces get a URP Lit stand-in tinted by the stock vertex colour 56/255
            // (approximation of the game shader; not saved, not in the prefab)
            foreach (var mr in inst.GetComponentsInChildren<MeshRenderer>(true).Where(x => x.name.StartsWith("cockpit_interior")))
            {
                var mesh = mr.GetComponent<MeshFilter>().sharedMesh;
                var vs = mesh.vertices;
                for (int si = 0; si < mesh.subMeshCount; si++)
                {
                    var ix = mesh.GetIndices(si); var b = new Bounds(vs[ix[0]], Vector3.zero); foreach (var q in ix) b.Encapsulate(vs[q]);
                    int nearPanel = ix.Where((q, n) => n % 3 == 0).Count(q => vs[q].z > 3.95f && vs[q].z < 4.02f && vs[q].y > 0.3f && vs[q].y < 0.65f && Mathf.Abs(vs[q].x) < 0.3f);
                    Debug.Log($"[GA25XCockpitShot] {mr.name} sub {si} bounds {b.min.ToString("F3")}..{b.max.ToString("F3")} tris near panel face {nearPanel}");
                }
                Debug.Log($"[GA25XCockpitShot] {mr.name} enabled {mr.enabled} layer {mr.gameObject.layer} mesh {mesh.name} subs {mesh.subMeshCount} mats {string.Join(",", mr.sharedMaterials.Select(m => m.name))} idx {string.Join(",", Enumerable.Range(0, mesh.subMeshCount).Select(i => mesh.GetIndexCount(i)))}");
            }
            Material stand = null;
            foreach (var r in inst.GetComponentsInChildren<MeshRenderer>(true))
            {
                var ms = r.sharedMaterials;
                for (int i = 0; i < ms.Length; i++)
                {
                    if (ms[i] == null || !AssetDatabase.GetAssetPath(ms[i]).Contains("aircraft_structure_PLACEHOLDER")) continue;
                    if (stand == null)
                    {
                        stand = new Material(Shader.Find("Universal Render Pipeline/Lit"));
                        var bt = ms[i].GetTexture("_Basecolor"); stand.SetTexture("_BaseMap", bt); stand.SetTexture("_MainTex", bt);
                        stand.SetColor("_BaseColor", Environment.GetCommandLineArgs().Contains("-redStruct") ? Color.red : new Color(56f / 255f, 56f / 255f, 56f / 255f)); stand.SetFloat("_Smoothness", 0.3f);
                    }
                    ms[i] = stand;
                }
                r.sharedMaterials = ms;
            }
            var lgo = new GameObject("shot_sun"); var lt = lgo.AddComponent<Light>(); lt.type = LightType.Directional; lt.intensity = 1.3f;
            lgo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat; RenderSettings.ambientLight = new Color(0.55f, 0.58f, 0.62f);
            var cgo = new GameObject("shot_cam"); var cam = cgo.AddComponent<Camera>();
            cam.nearClipPlane = 0.02f; cam.farClipPlane = 500f; cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.62f, 0.68f, 0.76f);
            cam.fieldOfView = 62f;
            var eyeP = ac.cockpitViewPoint;
            var eyeW = inst.GetComponentsInChildren<Transform>(true).First(t => t.name == "crew_wso_eye");
            Shot(cam, eyeP.position, eyeP.position + new Vector3(0.05f, -0.33f, 1f), Path.Combine(dir, "unity_pilot_eye.png"));
            Shot(cam, eyeW.position, eyeW.position + new Vector3(-0.05f, -0.33f, 1f), Path.Combine(dir, "unity_wso_eye.png"));
            Shot(cam, eyeP.position, eyeP.position + new Vector3(0.12f, -0.75f, 0.8f), Path.Combine(dir, "unity_pilot_eye_down.png"));
            foreach (var r in inst.GetComponentsInChildren<Renderer>(true).Where(r => r.name.StartsWith("canopy_"))) r.enabled = false;
            Shot(cam, eyeP.position + new Vector3(1.3f, 0.9f, -1.0f), eyeP.position + new Vector3(0.36f, -0.45f, 0.5f), Path.Combine(dir, "unity_three_quarter.png"));
            Debug.Log("[GA25XCockpitShot] wrote shots to " + dir);
            Object.DestroyImmediate(inst); Object.DestroyImmediate(cgo); Object.DestroyImmediate(lgo);
        }

        static object Get(object o, string f)
        {
            for (var t = o.GetType(); t != null; t = t.BaseType)
            {
                var fi = t.GetField(f, System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic);
                if (fi != null) return fi.GetValue(o);
            }
            throw new Exception("no field " + f);
        }

        static void Shot(Camera cam, Vector3 pos, Vector3 target, string file)
        {
            cam.transform.position = pos; cam.transform.rotation = Quaternion.LookRotation(target - pos, Vector3.up);
            var rt = new RenderTexture(1600, 900, 24, RenderTextureFormat.ARGB32); rt.antiAliasing = 4;
            cam.targetTexture = rt; cam.Render(); cam.Render();
            RenderTexture.active = rt;
            var tex = new Texture2D(1600, 900, TextureFormat.RGB24, false); tex.ReadPixels(new Rect(0, 0, 1600, 900), 0, 0); tex.Apply();
            File.WriteAllBytes(file, tex.EncodeToPNG());
            RenderTexture.active = null; cam.targetTexture = null; Object.DestroyImmediate(rt); Object.DestroyImmediate(tex);
            Debug.Log("[GA25XCockpitShot] " + file);
        }
    }
}
