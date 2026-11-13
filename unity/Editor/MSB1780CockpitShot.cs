// Offline crew-station screenshots of the BUILT MSB-17/80 prefab in the Unity editor (Heritage Pairs 1.9.1 review: the stock EW-25 flight
// deck, seats, sticks and throttle are Unity-side parts that Blender cannot show). GA25XCockpitShot method. Needs a graphics device: run
// Unity in batch mode WITHOUT -nographics:
//   "C:\Program Files\Unity 2022.3.62f2\Editor\Unity.exe" -batchmode -quit -projectPath <Blueprinter-Editor>
//       -executeMethod B25HTools.MSB1780CockpitShot.Shoot -logFile <log> -shotDir <folder>
// Cockpit view state (Aircraft.cockpitRenderers on, exteriorRenderers off), crew figure bodies hidden (the stock ejection seats stay),
// the stock aircraft_structure placeholder shown with a flat URP Lit stand-in (as GA25XCockpitShot). Placeholder materials render as the
// Blueprinter project has them (editor preview, the tac page shows its placeholder texture), not exactly as in game. Nothing is saved.
using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class MSB1780CockpitShot
    {
        public static void Shoot()
        {
            var args = Environment.GetCommandLineArgs();
            int k = Array.IndexOf(args, "-shotDir");
            var dir = k >= 0 ? args[k + 1] : Path.GetFullPath("msb17_shots");
            Directory.CreateDirectory(dir);
            ShaderUtil.allowAsyncCompilation = false;
            var path = FamilyBuild.FamilyRoot + "/msb17/MSB17.prefab";
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (prefab == null) throw new Exception("no prefab " + path);
            var inst = (GameObject)Object.Instantiate(prefab);
            inst.transform.position = Vector3.zero; inst.transform.rotation = Quaternion.identity;
            var ac = inst.GetComponent<Aircraft>();
            var ext = ((Renderer[])Get(ac, "exteriorRenderers")).Where(r => r != null).ToList();
            var ckR = ((Renderer[])Get(ac, "cockpitRenderers")).Where(r => r != null).ToList();
            foreach (var r in ext) r.enabled = false;
            foreach (var r in ckR) r.enabled = true;
            foreach (var p in ac.pilots) foreach (var sr in p.GetComponentsInChildren<SkinnedMeshRenderer>(true)) sr.enabled = false;
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
                        stand.SetColor("_BaseColor", new Color(56f / 255f, 56f / 255f, 56f / 255f)); stand.SetFloat("_Smoothness", 0.3f);
                    }
                    ms[i] = stand;
                }
                r.sharedMaterials = ms;
            }
            foreach (var r in inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name.StartsWith("cockpit_") || r.name.StartsWith("stick_") || r.name.StartsWith("cockpit_throttle")))
                Debug.Log($"[MSB1780CockpitShot] {r.name} enabled {r.enabled} layer {r.gameObject.layer} mesh {r.GetComponent<MeshFilter>()?.sharedMesh?.name} mats {string.Join(",", r.sharedMaterials.Select(m => m != null ? m.name : "null"))}");
            var lgo = new GameObject("shot_sun"); var lt = lgo.AddComponent<Light>(); lt.type = LightType.Directional; lt.intensity = 1.2f;
            lgo.transform.rotation = Quaternion.Euler(55f, -30f, 0f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat; RenderSettings.ambientLight = new Color(0.58f, 0.60f, 0.64f);
            var cgo = new GameObject("shot_cam"); var cam = cgo.AddComponent<Camera>();
            cam.nearClipPlane = 0.02f; cam.farClipPlane = 500f; cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.62f, 0.68f, 0.76f);
            cam.fieldOfView = 70f;
            Transform E(string n) => inst.GetComponentsInChildren<Transform>(true).First(t => t.name == n);
            var eyeP = ac.cockpitViewPoint; var eyeC = E("crew_eye_copilot"); var eyeW = E("crew_eye_wso"); var eyeE = E("crew_eye_ewo");
            void Hide(params string[] pre) { foreach (var r in inst.GetComponentsInChildren<Renderer>(true).Where(r => pre.Any(p => r.name.StartsWith(p)))) r.enabled = false; }
            void Show(params string[] pre) { foreach (var r in inst.GetComponentsInChildren<Renderer>(true).Where(r => pre.Any(p => r.name.StartsWith(p)) && (ckR.Contains(r) || !ext.Contains(r)))) r.enabled = true; }
            Shot(cam, eyeP.position, eyeP.position + new Vector3(0.10f, -0.40f, 1f), Path.Combine(dir, "unity_pilot_eye.png"));
            Shot(cam, eyeC.position, eyeC.position + new Vector3(-0.10f, -0.40f, 1f), Path.Combine(dir, "unity_copilot_eye.png"));
            Shot(cam, eyeP.position, eyeP.position + new Vector3(0.30f, -0.85f, 0.75f), Path.Combine(dir, "unity_pilot_eye_down.png"));
            Shot(cam, eyeW.position, eyeW.position + new Vector3(0f, -0.55f, 1f), Path.Combine(dir, "unity_wso_eye.png"));
            Shot(cam, eyeE.position, eyeE.position + new Vector3(1f, -0.35f, 0.05f), Path.Combine(dir, "unity_ewo_eye.png"));
            Hide("fus_cockpit", "hatch_pilot", "cockpit_overhead");
            Shot(cam, eyeP.position + new Vector3(0.38f, 0.95f, -1.10f), eyeP.position + new Vector3(0.38f, -0.55f, 0.85f), Path.Combine(dir, "unity_deck_overview.png"));
            Show("fus_cockpit", "hatch_pilot", "cockpit_overhead");
            Hide("fus_nose", "hatch_wso", "chin_");
            Shot(cam, eyeW.position + new Vector3(-1.6f, 0.55f, -0.75f), eyeW.position + new Vector3(0f, -0.55f, 0.35f), Path.Combine(dir, "unity_wso_overview.png"));
            Show("fus_nose", "hatch_wso", "chin_");
            Hide("fus_center", "MSB17", "hatch_ewo", "top_");
            Shot(cam, eyeE.position + new Vector3(-0.95f, 0.55f, -0.70f), eyeE.position + new Vector3(0.65f, -0.45f, 0.05f), Path.Combine(dir, "unity_ewo_overview.png"));
            Debug.Log("[MSB1780CockpitShot] wrote shots to " + dir);
            Object.DestroyImmediate(inst); Object.DestroyImmediate(cgo); Object.DestroyImmediate(lgo);
        }

        // 1.9.5 review set (the user's order: our own flight deck with single stock parts): pilot eye, co-pilot eye, down at the sticks /
        // pedestal / throttle, the deck from behind, the overhead, + the WSO / EWO eyes; every shot twice: as the editor draws it (the tac page
        // renders black: its render texture is not driven outside the game) and '_live' with every tacScreenDisplay slot drawn flat green
        // (= a screen that shows the live tac page in game). Same cameras for any prefab (1.9.1-1.9.4 EW-25 deck or the 1.9.5 deck).
        public static void Shoot195()
        {
            var args = Environment.GetCommandLineArgs();
            int k = Array.IndexOf(args, "-shotDir");
            var dir = k >= 0 ? args[k + 1] : Path.GetFullPath("msb17_shots195");
            Directory.CreateDirectory(dir);
            ShaderUtil.allowAsyncCompilation = false;
            var path = FamilyBuild.FamilyRoot + "/msb17/MSB17.prefab";
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (prefab == null) throw new Exception("no prefab " + path);
            var inst = (GameObject)Object.Instantiate(prefab);
            inst.transform.position = Vector3.zero; inst.transform.rotation = Quaternion.identity;
            var ac = inst.GetComponent<Aircraft>();
            var ext = ((Renderer[])Get(ac, "exteriorRenderers")).Where(r => r != null).ToList();
            var ckR = ((Renderer[])Get(ac, "cockpitRenderers")).Where(r => r != null).ToList();
            foreach (var r in ext) r.enabled = false;
            foreach (var r in ckR) r.enabled = true;
            foreach (var p in ac.pilots) foreach (var sr in p.GetComponentsInChildren<SkinnedMeshRenderer>(true)) sr.enabled = false;
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
                        stand.SetColor("_BaseColor", new Color(56f / 255f, 56f / 255f, 56f / 255f)); stand.SetFloat("_Smoothness", 0.3f);
                    }
                    ms[i] = stand;
                }
                r.sharedMaterials = ms;
            }
            // warning lamps (CockpitWarningLights renderers) are off until a missile warning in game: shown here so the review sees them
            foreach (var r in inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name.StartsWith("warnlamp_"))) r.enabled = true;
            int nLive = 0;
            foreach (var r in inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.enabled || ckR.Contains(r)))
                if (r.sharedMaterials.Any(m => m != null && m.name.Contains("tacScreenDisplay"))) { nLive++; Debug.Log($"[MSB1780CockpitShot] live tac renderer {r.name} layer {r.gameObject.layer}"); }
            Debug.Log($"[MSB1780CockpitShot] {nLive} live tac renderers");
            var lgo = new GameObject("shot_sun"); var lt = lgo.AddComponent<Light>(); lt.type = LightType.Directional; lt.intensity = 1.2f;
            lgo.transform.rotation = Quaternion.Euler(55f, -30f, 0f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat; RenderSettings.ambientLight = new Color(0.58f, 0.60f, 0.64f);
            var cgo = new GameObject("shot_cam"); var cam = cgo.AddComponent<Camera>();
            cam.nearClipPlane = 0.02f; cam.farClipPlane = 500f; cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.62f, 0.68f, 0.76f);
            cam.fieldOfView = 70f;
            Transform E(string n) => inst.GetComponentsInChildren<Transform>(true).First(t => t.name == n);
            var eyeP = ac.cockpitViewPoint.position; var eyeC = E("crew_eye_copilot").position; var eyeW = E("crew_eye_wso").position; var eyeE = E("crew_eye_ewo").position;
            var mid = (eyeP + eyeC) / 2f;
            // fixed cameras for the deck-wide views (the 1.9.5 pilots sit 0.11 m forward / 0.04 m lower than 1.9.1-1.9.4): the 1.9.1 eye mid
            // point in the root frame (Blender (0, 3.45, 1.70) - the root at (0, 0.715, 0.397)), the same for every build
            var midFix = inst.transform.TransformPoint(new Vector3(0f, 1.303f, 2.735f));
            var shots = new List<(string n, Vector3 pos, Vector3 at, float fov)>
            {
                ("pilot_eye", eyeP, eyeP + new Vector3(0.10f, -0.40f, 1f), 70f),
                ("copilot_eye", eyeC, eyeC + new Vector3(-0.10f, -0.40f, 1f), 70f),
                ("down_controls", eyeP + new Vector3(0.16f, 0.02f, -0.05f), eyeP + new Vector3(0.40f, -1.05f, 0.62f), 75f),
                ("deck_behind", midFix + new Vector3(0f, 0.25f, -0.70f), midFix + new Vector3(0f, -0.75f, 0.90f), 85f),
                ("overhead", midFix + new Vector3(0f, -0.15f, 0.25f), midFix + new Vector3(0f, 0.55f, -0.45f), 80f),
                // 1.9.6 close-ups (panel, pedestal, left console), from the current eyes' mid point
                ("closeup_panel", mid + new Vector3(0f, -0.25f, 0.35f), mid + new Vector3(0f, -0.45f, 0.85f), 62f),
                ("closeup_pedestal", mid + new Vector3(0f, -0.35f, 0.05f), mid + new Vector3(0f, -0.81f, 0.39f), 60f),
                ("closeup_console_L", mid + new Vector3(-0.75f, -0.25f, 0.10f), mid + new Vector3(-0.92f, -0.68f, 0.09f), 65f),
                ("wso_eye", eyeW, eyeW + new Vector3(0f, -0.55f, 1f), 70f),
                ("ewo_eye", eyeE, eyeE + new Vector3(1f, -0.35f, 0.05f), 70f),
            };
            var green = new Material(Shader.Find("Universal Render Pipeline/Unlit")); green.SetColor("_BaseColor", new Color(0.25f, 0.95f, 0.35f));
            var saved = new Dictionary<Renderer, Material[]>();
            foreach (var pass in new[] { "", "_live" })
            {
                if (pass == "_live")
                    foreach (var r in inst.GetComponentsInChildren<MeshRenderer>(true))
                    {
                        var ms = r.sharedMaterials; bool any = false;
                        for (int i = 0; i < ms.Length; i++) if (ms[i] != null && ms[i].name.Contains("tacScreenDisplay")) { ms[i] = green; any = true; }
                        if (any) { saved[r] = r.sharedMaterials; r.sharedMaterials = ms; }
                    }
                foreach (var s in shots)
                {
                    cam.fieldOfView = s.fov; Shot(cam, s.pos, s.at, Path.Combine(dir, $"u195_{s.n}{pass}.png"));
                }
            }
            foreach (var kv in saved) kv.Key.sharedMaterials = kv.Value;
            Debug.Log("[MSB1780CockpitShot] 1.9.5 set wrote shots to " + dir);
            Object.DestroyImmediate(inst); Object.DestroyImmediate(cgo); Object.DestroyImmediate(lgo); Object.DestroyImmediate(green);
        }

        // 1.9.7: the throttle quadrant with the stock levers at idle / half / full (Cockpit.Throttle.Animate: localEulerAngles = (throttle x range, 0, 0)),
        // two cameras (a close-up of the right lever in its slot, the whole quadrant from above-behind). Run on the 1.9.6 prefab first (before), then on 1.9.7.
        //   Unity -batchmode -quit -projectPath <project> -executeMethod B25HTools.MSB1780CockpitShot.Shoot197 -logFile <log> -shotDir <folder>
        public static void Shoot197()
        {
            var args = Environment.GetCommandLineArgs();
            int k = Array.IndexOf(args, "-shotDir");
            var dir = k >= 0 ? args[k + 1] : Path.GetFullPath("msb17_shots197");
            Directory.CreateDirectory(dir);
            ShaderUtil.allowAsyncCompilation = false;
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(FamilyBuild.FamilyRoot + "/msb17/MSB17.prefab");
            if (prefab == null) throw new Exception("no MSB17 prefab");
            var inst = (GameObject)Object.Instantiate(prefab);
            inst.transform.position = Vector3.zero; inst.transform.rotation = Quaternion.identity;
            var ac = inst.GetComponent<Aircraft>();
            foreach (var r in ((Renderer[])Get(ac, "exteriorRenderers")).Where(r => r != null)) r.enabled = false;
            foreach (var r in ((Renderer[])Get(ac, "cockpitRenderers")).Where(r => r != null)) r.enabled = true;
            foreach (var p in ac.pilots) foreach (var sr in p.GetComponentsInChildren<SkinnedMeshRenderer>(true)) sr.enabled = false;
            var lgo = new GameObject("shot_sun"); var lt = lgo.AddComponent<Light>(); lt.type = LightType.Directional; lt.intensity = 1.2f;
            lgo.transform.rotation = Quaternion.Euler(55f, -30f, 0f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat; RenderSettings.ambientLight = new Color(0.58f, 0.60f, 0.64f);
            var cgo = new GameObject("shot_cam"); var cam = cgo.AddComponent<Camera>();
            cam.nearClipPlane = 0.02f; cam.farClipPlane = 500f; cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.62f, 0.68f, 0.76f);
            var ck = inst.GetComponentInChildren<Cockpit>(true);
            var so = new SerializedObject(ck); var th = so.FindProperty("throttles");
            if (th == null || th.arraySize < 1) throw new Exception("no Cockpit.throttles entry");
            var drv = (Transform)th.GetArrayElementAtIndex(0).FindPropertyRelative("transform").objectReferenceValue;
            float rg = th.GetArrayElementAtIndex(0).FindPropertyRelative("range").floatValue;
            var piv = drv.position;
            foreach (var (tag, t) in new[] { ("idle", 0f), ("mid", 0.5f), ("full", 1f) })
            {
                drv.localEulerAngles = new Vector3(t * rg, 0f, 0f);
                cam.fieldOfView = 24f; Shot(cam, piv + new Vector3(0.02f, 0.60f, -0.26f), piv + new Vector3(0.087f, 0.19f, 0.0f), Path.Combine(dir, $"u197_throttle_side_{tag}.png"));   // close-up of the right lever in its slot
                cam.fieldOfView = 45f; Shot(cam, piv + new Vector3(0.10f, 0.62f, -0.42f), piv + new Vector3(0f, 0.18f, 0.02f), Path.Combine(dir, $"u197_throttle_above_{tag}.png"));
            }
            Debug.Log("[MSB1780CockpitShot] 1.9.7 throttle set wrote shots to " + dir);
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
            Debug.Log("[MSB1780CockpitShot] " + file);
        }
    }
}
