// Heritage Pairs 1.9.13 study (FD-32 upper-wing "hinge" at the break line, Discord report 2026-11-16): offline PhysX oracle in Unity's own
// PhysX (edit mode, Physics.Simulate at the game's 1/60 s step, PGS, 6/1 iterations = the game's DynamicsManager). It rebuilds the
// per-part rigid bodies and FixedJoints the game makes for a locally simulated aircraft (Aircraft.SetComplexPhysics -> AeroPart.CreateRB:
// own Rigidbody per part, mass = part mass, drag / angularDrag 0, automatic inertia from the colliders; AeroPart.CreateJoints: one
// FixedJoint per PartJoint, anchor = PartJoint.anchor world offset or the part origin, break x10, rb.solverIterations = PartJoint value
// when != 6), then loads the wing parts the way AeroJob_Math does (force at the body CoM + torque centerOfLift x F) in a steady pull-up
// and in a roll, and measures how far each outer panel moves against its inboard neighbour at the break line. Nothing of the game's
// code is copied; the prefabs are only read for their numbers. Read only: nothing is written into any prefab.
//
//   Unity -batchmode -projectPath <project> -executeMethod B25HTools.WingFlexPhysX.All [-unitylogs <dir>]   -> <LogDir>/wingflex.txt (see LogDir)
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class WingFlexPhysX
    {
        public const float DT = 1f / 60f;
        // Output folder (1.9.13 r5: no machine path in the source): "-unitylogs <dir>" on the Unity command line, else the environment variable
        // HP_UNITYLOGS, else "unitylogs" three levels above the project's Assets folder (<work>/BlueprinterProject/<project>/Assets -> <work>/unitylogs).
        public static string LogDir
        {
            get
            {
                var args = Environment.GetCommandLineArgs(); int k = Array.IndexOf(args, "-unitylogs");
                string d = k >= 0 && k + 1 < args.Length ? args[k + 1] : Environment.GetEnvironmentVariable("HP_UNITYLOGS");
                if (string.IsNullOrEmpty(d)) d = Path.Combine(Application.dataPath, "..", "..", "..", "unitylogs");
                d = Path.GetFullPath(d); Directory.CreateDirectory(d); return d;
            }
        }
        static string Out => Path.Combine(LogDir, "wingflex.txt");

        static FieldInfo Fld(Type t, string n)
        {
            for (var tt = t; tt != null; tt = tt.BaseType)
            {
                var f = tt.GetField(n, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (f != null) return f;
            }
            throw new Exception("WingFlexPhysX: no field " + n + " on " + t.Name);
        }
        static object G(object o, string n) => Fld(o.GetType(), n).GetValue(o);
        static float Gf(object o, string n) => Convert.ToSingle(G(o, n));

        public class Config
        {
            public string name;
            public float g = 6f;                  // steady load factor (pull-up)
            public float roll = 0f;               // > 0: roll case, lift on the left panels x (1 + roll), right x (1 - roll), at g
            public int iterations = 0;            // > 0: rb.solverIterations of every body (PhysX uses the island's largest)
            public string[] iterParts = null;     // with iterations: only these parts' bodies (= PartJoint.solverIterations on their joints, the data-only route)
            public Dictionary<string, float> mass = new Dictionary<string, float>();   // part -> kg; the difference comes from / goes to massFrom
            public string massFrom = null;
            public bool noStrut = false;          // drop the upper <-> lower strut joints
            public bool noGrand = false;          // drop the outer upper -> root joints (tensor wing_upper_C)
            public bool seamAnchor = false;       // outer upper panel joints anchored at the break line instead of the part origin
            public bool noCol = false;            // centerOfLift = 0 (force at the body CoM only)
            public float inertiaMul = 1f;         // x inertia tensor of the wing bodies (wings only)
            public float massScale = 1f;          // FixedJoint.massScale on joints whose own body is a wing part (connectedMassScale 1)
            public bool merge = false;            // outer upper panels have no body: welded into wing_upper_C (mass, forces, colliders)
            public float aileron = 0f;            // N: extra lift on aileron_L / flaperon_L (+) and aileron_R / flaperon_R (-) = a full roll input at speed
            public float onset = 0.5f;            // s: ramp time of the load factor (and aileron force)
            public float seconds = 2.5f;
            public float speed = 0f;              // > 0 m/s: aero feedback - each part's lift = q S (CL0 + 5.7 dAlpha), dAlpha = its own pitch vs the root (as the game's
                                                  //   AeroJob reads the AoA in the part's own liftNormal frame), CL clamped +-1.6; CL0 sets the mean load factor
            public bool selfCollide = false;      // true = the game's layer matrix (layer 14 collides with 14: only directly jointed pairs are skipped)
        }

        static readonly (string inner, string outer)[] FdSeams = { ("wing_upper_C", "wing_upper_L"), ("wing_upper_C", "wing_upper_R"), ("FD32", "wing_lower_L"), ("FD32", "wing_upper_C") };

        public static void All()
        {
            var sb = new StringBuilder();
            sb.Append($"# WingFlexPhysX {DateTime.Now:s} Unity {Application.unityVersion} default iterations {Physics.defaultSolverIterations}/{Physics.defaultSolverVelocityIterations}, dt {DT:F5}\n");
            sb.Append("# per seam: dz = step at the break line (outer panel inboard edge vs the same point on the inner part), mm, up +; ang = relative rotation deg (dih = about fore-aft, twist = about span);\n");
            sb.Append("#           'hold' = mean of the last 0.5 s, 'osc' = peak-to-peak of the last 0.5 s, 'max' = largest |value| over the run\n");
            var fd = FamilyBuild.FamilyRoot + "/fd32/FD32.prefab";
            var nim = FamilyBuild.FamilyRoot + "/nimrod/NIMROD1.prefab";
            var coin = "Assets/Blueprinter/_donotship/GameObject/COIN_PLACEHOLDER.prefab";
            var fdExtra = new[] { ("fus_engine", 280f), ("fus_engine", 96f), ("FD32", 75f) };
            var C120 = new Dictionary<string, float> { ["wing_upper_C"] = 120f, ["wing_upper_L"] = 100f, ["wing_upper_R"] = 100f };
            var AIL25 = new Dictionary<string, float> { ["aileron_L"] = 25f, ["aileron_R"] = 25f, ["flaperon_L"] = 25f, ["flaperon_R"] = 25f };
            var BOTH = C120.Concat(AIL25).ToDictionary(kv => kv.Key, kv => kv.Value);
            var cfgs = new List<Config>
            {
                new Config { name = "no load (rest offsets)", g = 0f },
                new Config { name = "as built 1 g", g = 1f },
                new Config { name = "as built 3 g", g = 3f },
                new Config { name = "as built 6 g" },
                new Config { name = "as built 9 g yank (0.1 s onset)", g = 9f, onset = 0.1f },
                new Config { name = "as built roll: aileron +-10 kN at 1 g", g = 1f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "as built roll: aileron +-10 kN at 4 g", g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "as built roll: lift +-30 % L/R at 3 g", g = 3f, roll = 0.3f },
                new Config { name = "iterations 12, 9 g yank", iterations = 12, g = 9f, onset = 0.1f },
                new Config { name = "iterations 12, roll aileron 10 kN 4 g", iterations = 12, g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "iterations 20, 9 g yank", iterations = 20, g = 9f, onset = 0.1f },
                new Config { name = "iterations 20, roll aileron 10 kN 4 g", iterations = 20, g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "iterations 30, roll aileron 10 kN 4 g", iterations = 30, g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "no strut joint, 9 g yank", noStrut = true, g = 9f, onset = 0.1f },
                new Config { name = "no grandparent joint, 9 g yank", noGrand = true, g = 9f, onset = 0.1f },
                new Config { name = "seam anchors, 9 g yank", seamAnchor = true, g = 9f, onset = 0.1f },
                new Config { name = "centerOfLift 0, 9 g yank", noCol = true, g = 9f, onset = 0.1f },
                new Config { name = "wing inertia x4, 9 g yank", inertiaMul = 4f, g = 9f, onset = 0.1f },
                new Config { name = "C 120 / outer 100 kg, 9 g yank", mass = C120, massFrom = "fus_engine", g = 9f, onset = 0.1f },
                new Config { name = "C 120 / outer 100 kg, roll aileron 10 kN 4 g", mass = C120, massFrom = "fus_engine", g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "ailerons/flaperons 25 kg, roll aileron 10 kN 4 g", mass = AIL25, massFrom = "fus_engine", g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "C 120 / outer 100 / surfaces 25 kg, 9 g yank", mass = BOTH, massFrom = "fus_engine", g = 9f, onset = 0.1f },
                new Config { name = "C 120 / outer 100 / surfaces 25 kg, roll aileron 10 kN 4 g", mass = BOTH, massFrom = "fus_engine", g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "C 120 / outer 100 / surfaces 25 kg + iterations 12, 9 g yank", mass = BOTH, massFrom = "fus_engine", iterations = 12, g = 9f, onset = 0.1f },
                new Config { name = "C 120 / outer 100 / surfaces 25 kg + iterations 12, roll aileron 10 kN 4 g", mass = BOTH, massFrom = "fus_engine", iterations = 12, g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "AERO FEEDBACK 6 g at 80 m/s", speed = 80f },
                new Config { name = "AERO FEEDBACK 6 g at 120 m/s", speed = 120f },
                new Config { name = "AERO FEEDBACK 6 g at 160 m/s", speed = 160f },
                new Config { name = "AERO FEEDBACK 9 g yank at 160 m/s", speed = 160f, g = 9f, onset = 0.1f },
                new Config { name = "AERO FEEDBACK roll aileron 10 kN 4 g at 160 m/s", speed = 160f, g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "AERO FEEDBACK 6 g at 160 m/s, iterations 12", speed = 160f, iterations = 12 },
                new Config { name = "AERO FEEDBACK 6 g at 160 m/s, iterations 20", speed = 160f, iterations = 20 },
                new Config { name = "AERO FEEDBACK 6 g at 160 m/s, centerOfLift 0", speed = 160f, noCol = true },
                new Config { name = "AERO FEEDBACK 6 g at 160 m/s, C 120 / outer 100 / surfaces 25", speed = 160f, mass = BOTH, massFrom = "fus_engine" },
                new Config { name = "AERO FEEDBACK 6 g at 160 m/s, C 120 / outer 100 / surfaces 25 + iterations 12", speed = 160f, mass = BOTH, massFrom = "fus_engine", iterations = 12 },
                new Config { name = "AERO FEEDBACK 6 g at 160 m/s, wing inertia x4", speed = 160f, inertiaMul = 4f },
                new Config { name = "AERO FEEDBACK 6 g at 160 m/s, upper wing welded", speed = 160f, merge = true },
                new Config { name = "DATA ROUTE: PartJoint.solverIterations 12 on wing_upper_C only, 9 g yank at 160 m/s", speed = 160f, g = 9f, onset = 0.1f, iterations = 12, iterParts = new[] { "wing_upper_C" } },
                new Config { name = "DATA ROUTE: PartJoint.solverIterations 20 on wing_upper_C only, 9 g yank at 160 m/s", speed = 160f, g = 9f, onset = 0.1f, iterations = 20, iterParts = new[] { "wing_upper_C" } },
                new Config { name = "DATA ROUTE: PartJoint.solverIterations 20 on wing_upper_C only, roll aileron 10 kN 4 g at 160 m/s", speed = 160f, g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f, iterations = 20, iterParts = new[] { "wing_upper_C" } },
                new Config { name = "DATA ROUTE: PartJoint.solverIterations 30 on wing_upper_C only, 9 g yank at 160 m/s", speed = 160f, g = 9f, onset = 0.1f, iterations = 30, iterParts = new[] { "wing_upper_C" } },
                new Config { name = "SELF-COLLISION ON (game layer matrix), no load", g = 0f, selfCollide = true },
                new Config { name = "SELF-COLLISION ON, 9 g yank", g = 9f, onset = 0.1f, selfCollide = true },
                new Config { name = "SELF-COLLISION ON, roll aileron 10 kN 4 g", g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f, selfCollide = true },
                new Config { name = "upper wing welded (one body), 9 g yank", merge = true, g = 9f, onset = 0.1f },
                new Config { name = "upper wing welded (one body), roll aileron 10 kN 4 g", merge = true, g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
            };
            foreach (var c in cfgs)
            {
                try { sb.Append(Run(fd, c, fdExtra, FdSeams)); }
                catch (Exception e) { sb.Append($"\n== FD32 {c.name}: EXCEPTION {e}\n"); }
            }
            foreach (var c in new[] { new Config { name = "Mk I no load", g = 0f }, new Config { name = "Mk I as built 9 g yank", g = 9f, onset = 0.1f }, new Config { name = "Mk I roll aileron 10 kN 4 g", g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f }, new Config { name = "Mk I AERO FEEDBACK 6 g at 160 m/s", speed = 160f }, new Config { name = "Mk I DATA ROUTE: solverIterations 20 on wing_upper_C, 9 g yank at 160 m/s", speed = 160f, g = 9f, onset = 0.1f, iterations = 20, iterParts = new[] { "wing_upper_C" } } })
            {
                try { sb.Append(Run(nim, c, new (string, float)[0], new[] { ("wing_upper_C", "wing_upper_L"), ("wing_upper_C", "wing_upper_R"), ("NIMROD1", "wing_lower_L") })); }
                catch (Exception e) { sb.Append($"\n== NIMROD1 {c.name}: EXCEPTION {e}\n"); }
            }
            foreach (var c in new[] { new Config { name = "stock CI-22 no load", g = 0f }, new Config { name = "stock CI-22 9 g yank", g = 9f, onset = 0.1f }, new Config { name = "stock CI-22 roll aileron 10 kN 4 g", g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f }, new Config { name = "stock CI-22 AERO FEEDBACK 6 g at 160 m/s", speed = 160f } })
            {
                try { sb.Append(Run(coin, c, new (string, float)[0], new[] { ("wing1_L", "wing2_L"), ("wing2_L", "wing3_L"), ("COIN_PLACEHOLDER", "wing1_L") })); }
                catch (Exception e) { sb.Append($"\n== COIN {c.name}: EXCEPTION {e}\n"); }
            }
            File.WriteAllText(Out, sb.ToString());
            Debug.Log("[B25H] WingFlexPhysX -> " + Out + "\n" + sb);
        }

        /// <summary>1.9.13 build oracle: the FD-32 and Mk I EXACTLY as built (no override: rb.solverIterations comes from the prefab's PartJoint values),
        /// pull and roll cases; run after a flags-off build (= 1.9.12 joints) and after the flags-on build. tools/stub_tests_1913.py reads both files.</summary>
        public static void Built1913()
        {
            string outB = Path.Combine(LogDir, "wingflex_built.txt");
            var sb = new StringBuilder($"# WingFlexPhysX.Built1913 {DateTime.Now:s} Unity {Application.unityVersion} default iterations {Physics.defaultSolverIterations}/{Physics.defaultSolverVelocityIterations}, dt {DT:F5}; as built, no override\n");
            var fd = FamilyBuild.FamilyRoot + "/fd32/FD32.prefab"; var nim = FamilyBuild.FamilyRoot + "/nimrod/NIMROD1.prefab";
            var fdExtra = new[] { ("fus_engine", 280f), ("fus_engine", 96f), ("FD32", 75f) };
            var nimSeams = new[] { ("wing_upper_C", "wing_upper_L"), ("wing_upper_C", "wing_upper_R"), ("NIMROD1", "wing_lower_L"), ("NIMROD1", "wing_upper_C") };
            Config[] Cases() => new[]
            {
                new Config { name = "BUILT no load", g = 0f },
                new Config { name = "BUILT 1 g", g = 1f },
                new Config { name = "BUILT 6 g", g = 6f },
                new Config { name = "BUILT 9 g yank", g = 9f, onset = 0.1f },
                new Config { name = "BUILT roll aileron 10 kN 4 g", g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
                new Config { name = "BUILT AERO FEEDBACK 9 g yank at 160 m/s", speed = 160f, g = 9f, onset = 0.1f },
                new Config { name = "BUILT AERO FEEDBACK roll aileron 10 kN 4 g at 160 m/s", speed = 160f, g = 4f, aileron = 10000f, onset = 0.1f, seconds = 1.5f },
            };
            foreach (var c in Cases())
            {
                try { sb.Append(Run(fd, c, fdExtra, FdSeams)); } catch (Exception e) { sb.Append($"\n== FD32 {c.name}: EXCEPTION {e}\n"); }
            }
            foreach (var c in Cases())
            {
                try { sb.Append(Run(nim, c, new (string, float)[0], nimSeams)); } catch (Exception e) { sb.Append($"\n== NIMROD1 {c.name}: EXCEPTION {e}\n"); }
            }
            File.WriteAllText(outB, sb.ToString());
            Debug.Log("[B25H] WingFlexPhysX.Built1913 -> " + outB + "\n" + sb);
        }

        /// <summary>Ground side effect of the fix: GroundPhysX (the 1.8.2 wheel oracle) as built vs every body at the shipped wing count (FD32Build.WingSolverIterations1913).</summary>
        public static void Ground()
        {
            string outG = Path.Combine(LogDir, "wingflex_ground.txt");
            var sb = new StringBuilder($"# WingFlexPhysX.Ground {DateTime.Now:s}\n");
            var fd = FamilyBuild.FamilyRoot + "/fd32/FD32.prefab"; var nim = FamilyBuild.FamilyRoot + "/nimrod/NIMROD1.prefab";
            var fdExtra = new[] { ("fus_engine", 280f), ("fus_engine", 96f), ("FD32", 75f) };
            foreach (var it in new[] { 0, FD32Build.WingSolverIterations1913 })
            {
                try
                {
                    sb.Append(GroundPhysX.Run(fd, new GroundPhysX.Config { name = $"FD-32 kick, allIterations {it}", kick = 1f, allIterations = it }, fdExtra));
                    sb.Append(GroundPhysX.Run(fd, new GroundPhysX.Config { name = $"FD-32 roll 6 kN, allIterations {it}", thrust = 6000f, seconds = 12f, allIterations = it }, fdExtra));
                    sb.Append(GroundPhysX.Run(nim, new GroundPhysX.Config { name = $"Mk I kick, allIterations {it}", kick = 1f, allIterations = it }, new (string, float)[0]));
                }
                catch (Exception e) { sb.Append("EXCEPTION " + e + "\n"); }
            }
            File.WriteAllText(outG, sb.ToString());
            Debug.Log("[B25H] WingFlexPhysX.Ground -> " + outG);
        }

        static float Alpha(Transform ln, Transform root) { var f = ln.forward; return Mathf.Atan2(Vector3.Dot(f, root.up), Vector3.Dot(f, root.forward)) * Mathf.Rad2Deg; }
        static bool IsWingPart(string n) => n.StartsWith("wing") || n.StartsWith("aileron") || n.StartsWith("flap");
        static bool IsLeft(string n) => n.EndsWith("_L");
        static bool IsRight(string n) => n.EndsWith("_R");

        public static string Run(string prefabPath, Config cfg, (string part, float kg)[] extraMass, (string inner, string outer)[] seams)
        {
            var sb = new StringBuilder();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Physics.simulationMode = SimulationMode.Script;
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (prefab == null) throw new Exception("no prefab " + prefabPath);
            var inst = (GameObject)Object.Instantiate(prefab);
            inst.name = prefab.name;
            inst.transform.SetPositionAndRotation(new Vector3(0f, 3000f, 0f), Quaternion.identity);
            foreach (var mb in inst.GetComponentsInChildren<MonoBehaviour>(true)) if (mb != null) mb.enabled = false;
            Physics.SyncTransforms();

            var aps = inst.GetComponentsInChildren<AeroPart>(true);
            var rootAp = inst.GetComponent<AeroPart>();
            string Nm(AeroPart a) => a == rootAp ? prefab.name : a.name;
            var byName = aps.ToDictionary(Nm);
            var parentOf = new Dictionary<AeroPart, AeroPart>();
            foreach (var ap in aps) if (ap != rootAp) parentOf[ap] = ap.transform.parent.GetComponentInParent<AeroPart>();

            // the seam point: the outer part's collider bounds face nearest the inner part, at its centre (aircraft frame = world here)
            var seamPt = new Dictionary<(string, string), Vector3>();
            foreach (var (i, o) in seams)
            {
                if (!byName.ContainsKey(i) || !byName.ContainsKey(o)) continue;
                var bo = byName[o].GetComponent<Collider>().bounds; var ci = byName[i].GetComponent<Collider>().bounds.center;
                float x = Mathf.Abs(bo.min.x - ci.x) < Mathf.Abs(bo.max.x - ci.x) ? bo.min.x : bo.max.x;
                if (o.StartsWith("wing_upper_C") || o == "wing1_L" && i != "wing1_L") x = bo.center.x;   // centre section / root panel: its middle
                seamPt[(i, o)] = new Vector3(x, bo.center.y, bo.center.z);
            }

            // merge: the outer upper panels become children of wing_upper_C (no body, no joints); their lift goes onto C's body at their point
            var merged = new HashSet<AeroPart>();
            if (cfg.merge)
                foreach (var s in new[] { "wing_upper_L", "wing_upper_R", "aileron_L", "aileron_R" })
                    if (byName.TryGetValue(s, out var ap)) merged.Add(ap);

            var rbOf = new Dictionary<AeroPart, Rigidbody>();
            var rootRb = inst.GetComponent<Rigidbody>();
            rootRb.mass = Gf(rootAp, "mass"); rootRb.drag = 0f; rootRb.angularDrag = 0f; rootRb.useGravity = false; rootRb.isKinematic = false; rootRb.sleepThreshold = 0f;
            rbOf[rootAp] = rootRb;
            var upperC = byName.TryGetValue("wing_upper_C", out var uc) ? uc : null;
            foreach (var ap in aps)
            {
                if (ap == rootAp || merged.Contains(ap)) continue;
                ap.transform.SetParent(null, true);
                var rb = ap.gameObject.AddComponent<Rigidbody>();
                rb.mass = Gf(ap, "mass"); rb.drag = 0f; rb.angularDrag = 0f; rb.sleepThreshold = 0f; rb.useGravity = false;
                rbOf[ap] = rb;
            }
            foreach (var ap in merged) { ap.transform.SetParent(upperC.transform, true); rbOf[upperC].mass += Gf(ap, "mass"); }
            Rigidbody BodyOf(AeroPart a) => merged.Contains(a) ? rbOf[upperC] : rbOf[a];
            foreach (var em in extraMass) BodyOf(byName[em.part]).mass += em.kg;
            foreach (var kv in cfg.mass)
            {
                var rb = BodyOf(byName[kv.Key]); float d = kv.Value - rb.mass; rb.mass = kv.Value;
                BodyOf(byName[cfg.massFrom ?? prefab.name]).mass -= d;
            }
            Physics.SyncTransforms();
            foreach (var kv in rbOf) if (IsWingPart(Nm(kv.Key)) && cfg.inertiaMul != 1f) kv.Value.inertiaTensor *= cfg.inertiaMul;

            int nj = 0; var jointList = new List<string>();
            foreach (var ap in aps)
            {
                if (ap == rootAp) continue;
                var own = BodyOf(ap);
                var pjs = (Array)G(ap, "joints");
                foreach (var pj in pjs)
                {
                    var cp = (AeroPart)G(pj, "connectedPart") ?? parentOf[ap];
                    var tensor = (UnitPart)G(pj, "tensor");
                    string a = Nm(ap), b = Nm(cp);
                    if (cfg.noStrut && a.StartsWith("wing_upper_") && b.StartsWith("wing_lower_")) continue;
                    if (cfg.noGrand && a.StartsWith("wing_upper_") && a != "wing_upper_C" && cp == rootAp) continue;
                    var other = BodyOf(cp);
                    if (other == own) continue;
                    var fj = own.gameObject.AddComponent<FixedJoint>();
                    var anchor = (Transform)G(pj, "anchor");
                    if (anchor != null) fj.anchor = anchor.position - own.position;   // the game's own (world-offset) form
                    if (cfg.seamAnchor && !merged.Contains(ap) && seamPt.TryGetValue(("wing_upper_C", a), out var sp)) fj.anchor = ap.transform.InverseTransformPoint(sp);
                    fj.connectedBody = other; fj.enableCollision = false;
                    fj.breakForce = Gf(pj, "breakForce") * 10f; fj.breakTorque = Gf(pj, "breakTorque") * 10f;
                    if (cfg.massScale != 1f && IsWingPart(a)) fj.massScale = cfg.massScale;
                    int it = Convert.ToInt32(G(pj, "solverIterations"));
                    if (it != 6) own.solverIterations = it;
                    nj++; jointList.Add($"{a}->{b}{(tensor ? "(t " + tensor.name + ")" : "")}");
                }
            }
            if (cfg.iterations > 0) foreach (var kv in rbOf) if (cfg.iterParts == null || cfg.iterParts.Contains(Nm(kv.Key))) kv.Value.solverIterations = cfg.iterations;
            // self-collision off between the aircraft's own colliders (FixedJoint only skips directly jointed pairs)
            var cols = inst.GetComponentsInChildren<Collider>(true).Concat(aps.SelectMany(a => a.GetComponentsInChildren<Collider>(true))).Distinct().ToList();
            if (!cfg.selfCollide) for (int i = 0; i < cols.Count; i++) for (int j = i + 1; j < cols.Count; j++) Physics.IgnoreCollision(cols[i], cols[j], true);
            else
            {
                // report the non-jointed body pairs whose colliders touch at rest (they push each other in the game)
                var touching = new List<string>();
                for (int i = 0; i < cols.Count; i++) for (int j = i + 1; j < cols.Count; j++)
                {
                    var a = cols[i]; var b = cols[j]; if (a.isTrigger || b.isTrigger || a.attachedRigidbody == b.attachedRigidbody) continue;
                    if (Physics.ComputePenetration(a, a.transform.position, a.transform.rotation, b, b.transform.position, b.transform.rotation, out var _, out var dist))
                        touching.Add($"{a.name}({a.attachedRigidbody?.name})~{b.name}({b.attachedRigidbody?.name}) {dist * 1000f:F0} mm");
                }
                sb.Append($"   self-collision ON; overlapping collider pairs at rest: {touching.Count}{(touching.Count > 0 ? ": " + string.Join(", ", touching.Take(30)) : "")}\n");
            }
            Physics.SyncTransforms();

            float totalMass = rbOf.Values.Sum(r => r.mass);
            // lifting parts: wings + ailerons / flaps; share by wing area
            var lifters = aps.Where(a => IsWingPart(Nm(a)) && Gf(a, "wingArea") > 0.1f).ToList();
            float area = lifters.Sum(a => Gf(a, "wingArea"));
            sb.Append($"\n== {prefab.name}: {cfg.name}\n");
            sb.Append($"   bodies {rbOf.Count}, joints {nj}, total mass {totalMass:F0} kg, lifting area {area:F1} m2, island iterations {rbOf.Values.Max(r => r.solverIterations)}\n");
            sb.Append("   wing bodies: " + string.Join(", ", rbOf.Where(kv => IsWingPart(Nm(kv.Key))).Select(kv => $"{Nm(kv.Key)} {kv.Value.mass:F0} kg I({kv.Value.inertiaTensor.x:F0},{kv.Value.inertiaTensor.y:F0},{kv.Value.inertiaTensor.z:F0})")) + "\n");
            if (cfg.name.StartsWith("no load") || cfg.name.StartsWith("Mk I no") || cfg.name.StartsWith("stock CI-22 no")) sb.Append("   joints: " + string.Join(", ", jointList) + "\n");

            // reference: seam points in both bodies' frames, relative rotations at rest
            var refs = seams.Where(s => seamPt.ContainsKey(s)).Select(s =>
            {
                var ti = BodyOf(byName[s.inner]).transform; var to = BodyOf(byName[s.outer]).transform;
                return (s, pi: ti.InverseTransformPoint(seamPt[s]), po: to.InverseTransformPoint(seamPt[s]), q0: Quaternion.Inverse(ti.rotation) * to.rotation, ti, to);
            }).ToList();

            int steps = Mathf.RoundToInt(cfg.seconds / DT), tail = Mathf.RoundToInt(0.5f / DT);
            var alpha0 = lifters.ToDictionary(a => a, a => { var ln = (Transform)G(a, "liftNormal"); if (!ln) ln = a.transform; return Alpha(ln, inst.transform); });
            float maxDA = 0f; string maxDAPart = "";
            var dz = refs.Select(_ => new List<float>()).ToList(); var dih = refs.Select(_ => new List<float>()).ToList(); var tw = refs.Select(_ => new List<float>()).ToList();
            float maxRollRate = 0f;
            for (int s = 0; s < steps; s++)
            {
                float t = s * DT, ramp = Mathf.Clamp01(t / cfg.onset), n = cfg.g * ramp;
                var up = inst.transform.up;
                float W = totalMass * 9.81f;
                Vector3 net = Vector3.zero, comSum = Vector3.zero; float mSum = 0f;
                foreach (var r in rbOf.Values) { comSum += r.worldCenterOfMass * r.mass; mSum += r.mass; }
                var com = comSum / mSum; Vector3 moment = Vector3.zero;
                foreach (var a in lifters)
                {
                    string nm = Nm(a); float k = 1f;
                    if (cfg.roll > 0f) k = IsLeft(nm) ? 1f + cfg.roll : IsRight(nm) ? 1f - cfg.roll : 1f;
                    var ln = (Transform)G(a, "liftNormal"); if (!ln) ln = a.transform;
                    var F = up * (n * W * Gf(a, "wingArea") / area * k);
                    if (cfg.speed > 0f)
                    {
                        float q = 0.5f * 1.225f * cfg.speed * cfg.speed, cl0 = n * W / (q * area);
                        float da = Mathf.DeltaAngle(alpha0[a], Alpha(ln, inst.transform)) * Mathf.Deg2Rad;
                        if (Mathf.Abs(da) * Mathf.Rad2Deg > maxDA) { maxDA = Mathf.Abs(da) * Mathf.Rad2Deg; maxDAPart = nm; }
                        F = up * (q * Gf(a, "wingArea") * Mathf.Clamp(cl0 * k + 5.7f * da * ramp, -1.6f, 1.6f));
                    }
                    if (cfg.aileron != 0f && (nm.StartsWith("aileron") || nm.StartsWith("flaperon") || nm.StartsWith("flap_"))) F += up * (cfg.aileron * ramp * (IsLeft(nm) ? 1f : IsRight(nm) ? -1f : 0f));
                    var rb = BodyOf(a);
                    var col = cfg.noCol ? Vector3.zero : (Vector3)G(a, "centerOfLift");
                    // the game: force at the body CoM + torque centerOfLift(world, by the lift frame) x F; a welded panel's force acts at its own CoM point
                    Vector3 at = merged.Contains(a) ? a.transform.TransformPoint(a.GetComponent<Collider>() is MeshCollider mc && mc.sharedMesh ? mc.sharedMesh.bounds.center : Vector3.zero) : rb.worldCenterOfMass;
                    var cw = ln.rotation * col;
                    if (merged.Contains(a)) rb.AddForceAtPosition(F, at + cw);
                    else { rb.AddForce(F); if (cw != Vector3.zero) rb.AddTorque(Vector3.Cross(cw, F)); }
                    moment += Vector3.Cross(at + cw - com, F); net += F;
                }
                // tail trim: cancel the pitch / yaw moment on the root (only roll stays, for the roll case)
                var fwd = inst.transform.forward;
                var trim = -(moment - Vector3.Dot(moment, fwd) * fwd);
                rootRb.AddTorque(trim);
                if (cfg.roll <= 0f) rootRb.AddTorque(-Vector3.Dot(moment, fwd) * fwd);
                Physics.Simulate(DT);
                maxRollRate = Mathf.Max(maxRollRate, Mathf.Abs(Vector3.Dot(rootRb.angularVelocity, fwd)) * Mathf.Rad2Deg);
                for (int i = 0; i < refs.Count; i++)
                {
                    var R = refs[i];
                    var wi = R.ti.TransformPoint(R.pi); var wo = R.to.TransformPoint(R.po);
                    dz[i].Add(Vector3.Dot(wo - wi, R.ti.up) * 1000f);
                    var dq = Quaternion.Inverse(R.q0) * (Quaternion.Inverse(R.ti.rotation) * R.to.rotation);   // in the outer body's rest frame ~ aircraft frame
                    var e = dq.eulerAngles; float ex = e.x > 180f ? e.x - 360f : e.x, ez = e.z > 180f ? e.z - 360f : e.z;
                    dih[i].Add(ez); tw[i].Add(ex);
                }
            }
            string St(List<float> v) { var l = v.Skip(v.Count - tail).ToList(); return $"hold {l.Average(),7:F1} osc {l.Max() - l.Min(),6:F1} max {v.Max(x => Mathf.Abs(x)),7:F1}"; }
            for (int i = 0; i < refs.Count; i++)
                sb.Append($"   {refs[i].s.inner,-16} | {refs[i].s.outer,-14}  dz mm {St(dz[i])} | dih deg {St(dih[i])} | twist deg {St(tw[i])}\n");
            if (cfg.speed > 0f) sb.Append($"   largest own-AoA change of a lifting part {maxDA:F1} deg ({maxDAPart})\n");
            if (cfg.roll > 0f) sb.Append($"   roll rate reached {maxRollRate:F0} deg/s\n");
            var broken = rbOf.Values.SelectMany(r => r.GetComponents<FixedJoint>()).Count();
            if (broken < nj) sb.Append($"   JOINTS BROKEN: {nj - broken} of {nj}\n");
            return sb.ToString();
        }
    }
}
