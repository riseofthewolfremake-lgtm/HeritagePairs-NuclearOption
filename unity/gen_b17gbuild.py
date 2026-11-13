"""Generate unity/Editor/B17GBuild.cs from B25HBuild.cs + the B-17G section files in unity/b17g_sections/ (B-25H code reused by copy,
B25HBuild.cs untouched). Run after editing a section:  python unity/gen_b17gbuild.py   (then copy to the Blueprinter project's Assets/Editor).
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
SEC = os.path.join(HERE, 'b17g_sections')
ED = os.path.join(HERE, 'Editor')
s = open(os.path.join(ED, 'B25HBuild.cs'), encoding='utf-8').read()
s = s.replace('public static class B25HBuild', 'public static class B17GBuild').replace('B25HBuild.', 'B17GBuild.')
s = s.replace('static void L(string s) { log.Add(s); Debug.Log("[B25H] " + s); }', 'static void L(string s) { log.Add(s); Debug.Log("[B25H] B17G " + s); }')
s = s.replace('"B25H_', '"B17G_').replace('b25h_', 'b17g_').replace('"B25H"', '"B17G"')
s = s.replace('Folder + "/B25H', 'Folder + "/B17G').replace('/Generated/B25H_meshes', '/Generated/B17G_meshes').replace('("B25H",', '("B17G",')


def rd(n):
    return open(os.path.join(SEC, n), encoding='utf-8').read()


def splice(start, end, new):
    global s
    a = s.index(start); b = s.index(end, a + len(start))
    s = s[:a] + new + s[b:]


def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, 1)


a = s.index("        // ------------------------------------------------------------------ state for one build")
s = rd('b17g_head.cs') + s[a:]
splice("        static readonly string[] SkinMaps", "        static Texture2D FallbackTexture(string n)", rd('b17g_tex.cs'))
splice("        static void BuildMaterials()", "        static Material Tiled(Material m", rd('b17g_mat.cs'))
splice("        static void BuildPrefab()", "        static void AddJoints(List<PartSpec> specs)", rd('b17g_prefab.cs'))
splice("        static void ControlSurfaces()", "        // hingeA: fixed, local Z = hinge axis;", rd('b17g_cs_gear.cs'))
splice("        static void Engines()", "        static Mesh TruncatedBlade(Mesh src", rd('b17g_eng.cs'))
splice("        static WeaponMount ammoCannon, ammo50;", "        static WeaponMount Mount(string n)", rd('b17g_weap.cs'))
splice("        // --- defensive turrets: built-in Turret like the AttackHelo1", "        // ------------------------------------------------------------------ root systems", rd('b17g_tur.cs'))
splice("        static void FlyByWire(LandingGear noseGear)", "        // =================================================================== damage diagram", rd('b17g_fbw.cs'))
splice("        static GameObject SaveEverything()", "        // b17g_liveries.json (textures worker)", rd('b17g_save.cs'))
a = s.index("        static bool RunCheck(GameObject prefab)")
s = s[:a] + rd('b17g_check.cs')
rep("            FlyByWire(gears[0]);\n", "            FlyByWire(gears[0]);\n            ComputeSpawn(gears);\n")
a = s.index('            var copyNames = new List<string> { "cockpit_interior"'); b = s.index('            foreach (var n in copyNames.Distinct())')
s = s[:a] + rd('b17g_copynames.cs') + s[b:]
rep('var screen = NewGO("screen_dummy", cp.transform, Find("cockpit_gauges").position', 'var screen = NewGO("screen_dummy", cp.transform, Find("cockpit_interior").position')
rep('S(ck, "engineSources", new[] { parts["engine_L"].gameObject, parts["engine_R"].gameObject });', 'S(ck, "engineSources", EngineNums.Select(n => parts["engine_" + n].gameObject).ToArray());')
rep('var tcF = NewGO("targetCamForward", nose.transform, new Vector3(0, -0.45f, 5.75f)', 'var tcF = NewGO("targetCamForward", nose.transform, root.transform.TransformPoint(new Vector3(0, -0.85f, 5.95f))')
rep('var tcR = NewGO("targetCamRear", parts["fus_tail"].transform, new Vector3(0, -0.2f, -10.4f)', 'var tcR = NewGO("targetCamRear", parts["fus_tail"].transform, root.transform.TransformPoint(new Vector3(0, 0.0f, -15.9f))')
rep('var tcL = NewGO("landingCamPoint", nose.transform, new Vector3(0, -0.8f, 5.0f)', 'var tcL = NewGO("landingCamPoint", nose.transform, root.transform.TransformPoint(new Vector3(0, -1.1f, 5.5f))')
rep('if (c.role == "tail" && TailCrewScale < 0.999f)\n            {\n                fig.transform.localScale *= TailCrewScale;',
    'float crewScale = c.role == "tail" ? TailCrewScale : c.role == "ball" ? BallCrewScale : 1f;\n            if (crewScale < 0.999f)\n            {\n                fig.transform.localScale *= crewScale;')
rep('                    float range = (float)drv["range"];\n                    var d = DrivenFrame(t);\n', rd('b17g_throttle.cs'))
rep('        static readonly List<string> cockpitAnimLog = new List<string>();', '        static readonly List<string> cockpitAnimLog = new List<string>();\n        static readonly Dictionary<string, float> throttleForward = new Dictionary<string, float>();')
rep('S(power, "powerSources", new[] { parts["engine_L"].gameObject, parts["engine_R"].gameObject });', 'S(power, "powerSources", EngineNums.Select(n => parts["engine_" + n].gameObject).ToArray());')
# round 5: fuel tanks on every tank-carrying part (AB-4 settings, linked) + the engine fire effect (wreck fire): b17g_fuel.cs
splice("            // fuel: B-25H main tanks in the inner wing", "            // nav lights: our own small lenses", rd('b17g_fuel.cs') + "\n")
# 1.8.3: B25HBuild loads FastBomber1 itself now (its tanks use the AB-4 wing-tank settings)
assert 'foreach (var n in new[] { "COIN", "CAS1", "EW1", "turret_57mm_SideMount", "gun_12.7mm_internal", "turret_12.7mm_door", "FastBomber1" })' in s
rep('                foreach (var s in new[] { "L", "R" })\n                {\n                    var n = parts["nacelle_" + s];', '                foreach (var s in new[] { "2", "3" })\n                {\n                    var n = parts["nacelle_" + s];')
rep('foreach (var s in new[] { "L", "R" }) { doppler.Add(', 'foreach (var s in EngineNums) { doppler.Add(')
rep('aircraft.maxRadius = 11f;', 'aircraft.maxRadius = 16.5f;')
rep('aircraft.obstacleTop = 2.4f;', 'aircraft.obstacleTop = 5.1f;')
rep('static readonly string[] FailureIndicators = { "LEFT ENGINE FAILURE", "RIGHT ENGINE FAILURE" };', 'static readonly string[] FailureIndicators = { "ENGINE 1 FIRE", "ENGINE 2 FIRE", "ENGINE 3 FIRE", "ENGINE 4 FIRE" };')
rep('var part = "engine_" + (fname.StartsWith("LEFT") ? "L" : "R");', 'var part = "engine_" + fname.Substring(7, 1);')
# 1.6.1: wheels on Cockpit.joysticks (b17g_joystick.cs) after the stock cockpit animation setup
rep("            if (CockpitAnimators) CockpitAnimation(ck, cp);\n", "            if (CockpitAnimators)\n            {\n            CockpitAnimation(ck, cp);\n" + rd('b17g_joystick.cs') + "            }\n")
rep("        const float ColumnPitchSign = +1f;", "        const float ColumnPitchSign = +1f;\n        const float YokeJoystickRange = 30f;   // 1.6.1: wheel roll / tilt range (deg)")
# 1.6.1: convex part colliders from <= 96 support points (Player.log 1.6.0: 'Couldn't create a Convex Mesh ... within the maximum
# polygons limit (256). The partial hull will be used' for B17G_col, fus_nose_col, fus_cockpit_col, nacelle_1-4_col, tail_gun_col):
# the hull of 96 points has at most 2 x 96 - 4 = 188 faces
rep("""            var m = new Mesh { name = name, indexFormat = v.Count > 65000 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16 };
            m.SetVertices(v); m.SetTriangles(tri, 0); m.RecalculateBounds();
            generatedMeshes.Add(m);
            return m;
        }""", """            var hull = HullSupportPoints(v, 96);
            var ht = new List<int>(); for (int i = 1; i + 1 < hull.Count; i++) ht.AddRange(new[] { 0, i, i + 1 });
            var m = new Mesh { name = name };
            m.SetVertices(hull); m.SetTriangles(ht, 0); m.RecalculateBounds();
            generatedMeshes.Add(m);
            return m;
        }

        // support points of the vertex cloud in n Fibonacci directions (+ the 6 axis extremes): their convex hull is the part's hull
        // within a few cm and PhysX cooks it without the 255-polygon cap
        static List<Vector3> HullSupportPoints(List<Vector3> v, int n)
        {
            var dirs = new List<Vector3> { Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back };
            float ga = Mathf.PI * (3f - Mathf.Sqrt(5f));
            for (int i = 0; i < n - 6; i++) { float y = 1f - 2f * (i + 0.5f) / (n - 6), r = Mathf.Sqrt(1f - y * y), a = ga * i; dirs.Add(new Vector3(Mathf.Cos(a) * r, y, Mathf.Sin(a) * r)); }
            var pts = new List<Vector3>();
            foreach (var d in dirs)
            {
                var best = v[0]; float bd = float.MinValue;
                foreach (var p in v) { float x = Vector3.Dot(p, d); if (x > bd) { bd = x; best = p; } }
                if (!pts.Any(q => (q - best).sqrMagnitude < 1e-6f)) pts.Add(best);
            }
            return pts;
        }""")
# 1.6.1: crew legs (in game 1.6.0 the seated stock figures' legs hung out under the nose glazing, the waist windows, the tail and
# near the radio room): their thigh bones (pilot_armature > thigh_L / thigh_R > shin > foot) are folded to 2 % for the standing /
# kneeling positions; the check proves every crew vertex is inside the hull.
rep("""            foreach (var comp in fig.GetComponentsInChildren<Component>(true)) if (comp != null) Remap(comp);
            var pc = fig.GetComponent<Pilot>();""", """            if (LegsTucked.Contains(c.role))
                foreach (var th in fig.GetComponentsInChildren<Transform>(true).Where(x => x.name == "thigh_L" || x.name == "thigh_R"))
                {   // round 5: the figure's Animator plays the stock 'seated' clip (PilotController default state), which keys every leg
                    // bone's rotation AND scale each frame (seated.anim m_ScaleCurves pilot_armature/thigh_L ~1.0): in game the 0.02 fold was
                    // undone, the legs came back (user review 2: 01/02/04/09). Generic clips bind by transform path, so the renamed thigh
                    // (and its shin / foot below it) are no longer driven and keep the fold; the upper body still plays seated / dead.
                    th.localScale *= 0.02f; th.name = th.name + "_tucked";
                }
            foreach (var comp in fig.GetComponentsInChildren<Component>(true)) if (comp != null) Remap(comp);
            var pc = fig.GetComponent<Pilot>();""")
# 1.8.1: the B-25H canopy-glass change (CanopyGlassInterior181) stays out of the B-17G (it has its own glass_ck as "glass_int")
rep('if (src.sharedMaterials.All(m => m == mats["glass"]) && !(CanopyGlassInterior181 && n == "canopy_glass")) continue;', 'if (src.sharedMaterials.All(m => m == mats["glass"])) continue;')
rep('cr.sharedMaterials = src.sharedMaterials.Select(m => m == mats["glass"] ? glassInCockpit : m).ToArray();', 'cr.sharedMaterials = src.sharedMaterials.Select(m => m == mats["glass"] ? mats["glass_int"] : m).ToArray();')
rep('n == "canopy_frame" || n == "hatch_cockpit_top" || n == "canopy_glass"))', 'n == "canopy_frame" || n == "hatch_cockpit_top"))')
# 1.8.3: the engine collider keeps the 1.8.2 turbo (engine_n_hullsrc child, b17g_nacelle.py): baked in, then the child is deleted
rep("""                mc.sharedMesh = BakeCollider(go.transform, s.name + "_col", own);""",
    """                var hullSrc = go.transform.Find(s.name + "_hullsrc");
                mc.sharedMesh = hullSrc != null ? BakeCollider(go.transform, s.name + "_col", own, hullSrc.GetComponent<MeshFilter>()) : BakeCollider(go.transform, s.name + "_col", own);
                if (hullSrc != null) { L($"{s.name}: collider includes {hullSrc.name} (the 1.8.2 turbo), child deleted"); Object.DestroyImmediate(hullSrc.gameObject); }""")
s = s.replace('b17g_v2_contract.json', 'b17g_contract.json')
open(os.path.join(ED, 'B17GBuild.cs'), 'w', encoding='utf-8').write(s)
print('B17GBuild.cs', len(s.splitlines()), 'lines')
