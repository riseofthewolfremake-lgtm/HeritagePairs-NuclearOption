// Heritage Pairs 1.8.2 offline oracle: run a built aircraft prefab on the ground in Unity's own PhysX (edit mode, Physics.Simulate at the
// game's 1/60 s step), with the per-part rigid bodies and FixedJoints the game builds for a locally simulated aircraft (Aircraft.
// SetComplexPhysics -> AeroPart.CreateRB / CreateJoints: own Rigidbody per part, mass = part mass, FixedJoint to each PartJoint's part,
// break force x10) and a wheel force model written from the LandingGear behaviour notes in MODLOG / GripGear.cs (spring + damper along the
// hit normal from the attached body's point velocity, the < 1 m/s contact patch, the rolling slip-angle side force, braking, all capped at
// load x frictionCoef). Nothing of the game's code is copied; the LandingGear components on the prefab are only read for their numbers.
//
// What it answers: do the wheel loads at rest add up to the weight, and does the tail wheel carry its share, when the mains are on the root
// part (1.7.13, Nimrod Mk I) versus on the 51 kg lower-wing parts (FD-32 1.8.0 / 1.8.1)? And which data-only change fixes it.
//
//   bash nuclearoption-ref/unity.sh - ground_physx -executeMethod B25HTools.GroundPhysX.All   -> unitylogs\ground_physx.txt
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
    public static class GroundPhysX
    {
        public static bool ReversedFriction = true;
        public const float DT = 1f / 60f;          // the game's fixed step (TimeManager, tools/flightmodel/b17g_lateral.py)
        const string Out = @"C:\Users\User\nuclearoption-ref\unitylogs\ground_physx.txt";

        static FieldInfo Fld(Type t, string n)
        {
            for (var tt = t; tt != null; tt = tt.BaseType)
            {
                var f = tt.GetField(n, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (f != null) return f;
            }
            throw new Exception("GroundPhysX: no field " + n + " on " + t.Name);
        }
        static object G(object o, string n) => Fld(o.GetType(), n).GetValue(o);
        static float Gf(object o, string n) => Convert.ToSingle(G(o, n));

        public class Config
        {
            public string name;
            public bool gearOnRoot;            // apply the wheel forces to the root body (1.7.13 layout) instead of the LandingGear's attachedPart body
            public int partIterations = 6;     // rb.solverIterations of the gear-carrying non-root parts (PartJoint.solverIterations; game default 6)
            public int allIterations = 0;      // > 0: every body (the island uses the largest anyway)
            public float gearPartMass = -1f;   // > 0: the gear-carrying non-root parts' mass (kg); the root gives up the difference (same total)
            public float dampScale = 1f;       // main gear dampingRate x
            public float thrust = 0f;          // N forward at the prop body for the roll test (no aero)
            public float seconds = 8f;
            public float drop = 0.01f;         // m above first contact at release
            public float kick = 0f;            // m/s downward velocity given to the gear-carrying parts at t = 1 s (a bump)
            public bool tailOnOwn = true;      // with gearOnRoot: the tail wheel stays on its own part (1.7.13 had the tail on fus_rear)
            public float rootMass = -1f;       // > 0: root body mass override (kg), the difference is not given anywhere (total changes)
            public string massFrom = null;     // with gearPartMass: the part that gives up the added mass (default the root)
        }

        class Gear
        {
            public string name; public Rigidbody rb; public Transform cast, axle; public float travel, k, c, mu, resp, roll, radius;
            public bool braked; public float brake, ws; public bool hasPatch; public Vector3 patchLocal; public Collider patchCol;
            public List<float> loads = new List<float>(); public string hit = "";
        }

        public static void All()
        {
            var sb = new StringBuilder();
            sb.Append($"# GroundPhysX {DateTime.Now:s} Unity {Application.unityVersion} solverType {Physics.defaultSolverIterations}/{Physics.defaultSolverVelocityIterations} iterations, dt {DT:F5}\n");
            var fd = FamilyBuild.FamilyRoot + "/fd32/FD32.prefab";
            var nim = FamilyBuild.FamilyRoot + "/nimrod/NIMROD1.prefab";
            var extra = new Dictionary<string, (string part, float kg)[]>
            {
                // full fuel + 12.7 mm ammo on fus_engine, the hook mount on the root (dump_fd32_after181: FuelTank 280 kg, ammo 96 kg, hook 75 kg)
                ["FD32"] = new[] { ("fus_engine", 280f), ("fus_engine", 96f), ("FD32", 75f) },
                ["NIMROD1"] = new (string, float)[0],
            };
            try
            {
                foreach (var cfg in new[] {
                    new Config { name = "Mk I as built", kick = 1f },
                    new Config { name = "Mk I as built, roll 6 kN", thrust = 6000f, seconds = 12f } })
                    sb.Append(Run(nim, cfg, extra["NIMROD1"]));
                // the built FD-32 (1.8.2: wing_lower 100 kg, fus_engine 707, main damping 13000) and the 1.8.1 numbers rebuilt on it for comparison
                foreach (var cfg in new[] {
                    new Config { name = "FD-32 as built", kick = 1f },
                    new Config { name = "FD-32 with the 1.8.1 masses / damping (wing 51 kg, fus_engine 805, c 20000)", kick = 1f, gearPartMass = 51f, massFrom = "fus_engine", dampScale = 20000f / 13000f },
                    new Config { name = "FD-32 mains on root (1.7.13 layout)", kick = 1f, gearOnRoot = true },
                    new Config { name = "FD-32 as built, roll 6 kN", thrust = 6000f, seconds = 12f },
                })
                    sb.Append(Run(fd, cfg, extra["FD32"]));
            }
            catch (Exception e) { sb.Append("EXCEPTION " + e + "\n"); }
            File.WriteAllText(Out, sb.ToString());
            Debug.Log("[B25H] GroundPhysX -> " + Out + "\n" + sb);
        }

        /// <summary>1.8.8 baseline for the taildragger tracking study (tools/flightmodel/taildragger_track.py): wheel geometry about the CoM,
        /// static loads, yaw inertia and the LandingGear steering / grip numbers of the stock CI-22 (COIN) and A-19 (CAS1) placeholders and of
        /// our five built prefabs -> unitylogs\ground_geometry.txt. Read only: nothing is written into any prefab; derived from the install.</summary>
        public static void Baseline()
        {
            const string outGeo = @"C:\Users\User\nuclearoption-ref\unitylogs\ground_geometry.txt";
            var sb = new StringBuilder();
            sb.Append($"# GroundPhysX.Baseline {DateTime.Now:s} Unity {Application.unityVersion}\n");
            var list = new[] {
                ("CI-22 (COIN, stock)", "Assets/Blueprinter/_donotship/GameObject/COIN_PLACEHOLDER.prefab"),
                ("A-19 (CAS1, stock)", "Assets/Blueprinter/_donotship/GameObject/CAS1_PLACEHOLDER.prefab"),
                ("B-17G", FamilyBuild.FamilyRoot + "/b17g/B17G.prefab"),
                ("Nimrod Mk I", FamilyBuild.FamilyRoot + "/nimrod/NIMROD1.prefab"),
                ("FD-32", FamilyBuild.FamilyRoot + "/fd32/FD32.prefab"),
                ("B-25H", FamilyBuild.FamilyRoot + "/b25h/B25H.prefab"),
                ("GA-25X", FamilyBuild.FamilyRoot + "/ga25x/GA25X.prefab"),
            };
            foreach (var (nm, path) in list)
            {
                try
                {
                    if (AssetDatabase.LoadAssetAtPath<GameObject>(path) == null) { sb.Append($"\n== {nm}: no prefab at {path}\n"); continue; }
                    sb.Append(Run(path, new Config { name = nm + " at rest", seconds = 4f }, new (string, float)[0]));
                }
                catch (Exception e) { sb.Append($"\n== {nm}: EXCEPTION {e.Message}\n"); }
            }
            File.WriteAllText(outGeo, sb.ToString());
            Debug.Log("[B25H] GroundPhysX.Baseline -> " + outGeo);
        }

        public static string Run(string prefabPath, Config cfg, (string part, float kg)[] extraMass)
        {
            var sb = new StringBuilder();
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            Physics.simulationMode = SimulationMode.Script;
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (prefab == null) throw new Exception("no prefab " + prefabPath);
            var inst = (GameObject)Object.Instantiate(prefab);
            inst.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            foreach (var mb in inst.GetComponentsInChildren<MonoBehaviour>(true)) if (mb != null) mb.enabled = false;   // nothing of the game runs; data only
            var ground = GameObject.CreatePrimitive(PrimitiveType.Cube);
            ground.name = "ground"; ground.transform.localScale = new Vector3(4000f, 1f, 4000f); ground.transform.position = new Vector3(0f, -0.5f, 1500f);

            // ---- complex physics: one body per AeroPart (root keeps the prefab Rigidbody), FixedJoints per PartJoint
            var aps = inst.GetComponentsInChildren<AeroPart>(true);
            var allGear = inst.GetComponentsInChildren<LandingGear>(true);     // before the parts leave the hierarchy
            var rootAp = inst.GetComponent<AeroPart>();
            var parentOf = new Dictionary<AeroPart, AeroPart>();
            foreach (var ap in aps) if (ap != rootAp) parentOf[ap] = ap.transform.parent.GetComponentInParent<AeroPart>();
            var rbOf = new Dictionary<AeroPart, Rigidbody>();
            var rootRb = inst.GetComponent<Rigidbody>();
            rootRb.mass = Gf(rootAp, "mass"); rootRb.drag = 0f; rootRb.angularDrag = 0f; rootRb.useGravity = true; rootRb.isKinematic = false; rootRb.sleepThreshold = 0f;
            rbOf[rootAp] = rootRb;
            foreach (var ap in aps)
            {
                if (ap == rootAp) continue;
                ap.transform.SetParent(null, true);
                var rb = ap.gameObject.AddComponent<Rigidbody>();
                rb.mass = Gf(ap, "mass"); rb.drag = 0f; rb.angularDrag = 0f; rb.sleepThreshold = 0f; rb.useGravity = true;
                rbOf[ap] = rb;
            }
            foreach (var em in extraMass)
            {
                var ap = aps.First(a => a.name == em.part || (a == rootAp && inst.name.StartsWith(em.part))); rbOf[ap].mass += em.kg;
            }
            int nj = 0;
            foreach (var ap in aps)
            {
                if (ap == rootAp) continue;
                var pjs = (Array)G(ap, "joints");
                foreach (var pj in pjs)
                {
                    var cp = (AeroPart)G(pj, "connectedPart") ?? parentOf[ap];
                    var fj = ap.gameObject.AddComponent<FixedJoint>();
                    var anchor = (Transform)G(pj, "anchor");
                    if (anchor != null) fj.anchor = anchor.position - rbOf[ap].position;   // the game's own (world-offset) form
                    fj.connectedBody = rbOf[cp]; fj.enableCollision = false;
                    fj.breakForce = Gf(pj, "breakForce") * 10f; fj.breakTorque = Gf(pj, "breakTorque") * 10f;
                    int it = Convert.ToInt32(G(pj, "solverIterations"));
                    if (it != 6) rbOf[ap].solverIterations = it;
                    nj++;
                }
            }

            // ---- gears
            var gears = new List<Gear>();
            var gearParts = new HashSet<AeroPart>();
            foreach (var lg in allGear)
            {
                var ap = (AeroPart)G(lg, "attachedPart");
                var g = new Gear
                {
                    name = lg.name, rb = cfg.gearOnRoot && !(cfg.tailOnOwn && (bool)G(lg, "steering") && !(bool)G(lg, "braked")) ? rootRb : rbOf[ap],
                    cast = CastOf(lg), axle = (Transform)G(lg, "axle"),
                    travel = Gf(lg, "suspensionTravel"), k = Gf(lg, "springRate"), c = Gf(lg, "dampingRate"), mu = Gf(lg, "frictionCoef"),
                    resp = Gf(lg, "response"), roll = Gf(lg, "rollingResistance"), radius = Gf(lg, "wheelRadius"), braked = (bool)G(lg, "braked"),
                };
                if (g.braked || g.name.EndsWith(GripGear.Suffix)) g.c *= cfg.dampScale;
                gears.Add(g);
                if (ap != rootAp && (g.braked || g.name.EndsWith(GripGear.Suffix))) gearParts.Add(ap);
            }
            foreach (var ap in gearParts)
            {
                if (cfg.partIterations != 6) rbOf[ap].solverIterations = cfg.partIterations;
                if (cfg.gearPartMass > 0f)
                {
                    float d = cfg.gearPartMass - rbOf[ap].mass; rbOf[ap].mass = cfg.gearPartMass;
                    var from = cfg.massFrom == null ? rootRb : rbOf[aps.First(a => a.name == cfg.massFrom)]; from.mass -= d;
                }
            }
            if (cfg.allIterations > 0) foreach (var rb in rbOf.Values) rb.solverIterations = cfg.allIterations;
            if (cfg.rootMass > 0f) rootRb.mass = cfg.rootMass;
            float totalMass = rbOf.Values.Sum(r => r.mass), weight = totalMass * 9.81f;

            // drop height: the lowest cast end 1 cm above the ground
            float lift = gears.Max(g => -(g.cast.position.y - g.travel)) + cfg.drop;
            foreach (var rb in rbOf.Values) rb.transform.position += Vector3.up * lift;
            Physics.SyncTransforms();
            var prop = aps.FirstOrDefault(a => a.name == "prop");

            sb.Append($"\n== {Path.GetFileNameWithoutExtension(prefabPath)}: {cfg.name}\n");
            sb.Append($"   bodies {rbOf.Count}, joints {nj}, total mass {totalMass:F0} kg (weight {weight / 1000f:F2} kN); gear bodies: {string.Join(", ", gears.Select(g => $"{g.name}->{g.rb.name} {g.rb.mass:F0} kg it {g.rb.solverIterations}"))}\n");

            {
                Physics.SyncTransforms();
                var com = rbOf.Values.Aggregate(Vector3.zero, (acc, r) => acc + r.worldCenterOfMass * r.mass) / totalMass;
                // inertia about the aircraft CoM in the aircraft frame (x right = roll axis is z fwd in Unity: Ixx here = pitch, Izz = roll)
                var I = new double[3]; var axes = new[] { inst.transform.right, inst.transform.up, inst.transform.forward };
                foreach (var r in rbOf.Values)
                {
                    var R = Matrix4x4.Rotate(r.rotation * r.inertiaTensorRotation);
                    for (int ax = 0; ax < 3; ax++)
                    {
                        var a = axes[ax]; var la = (Vector3)(R.inverse.MultiplyVector(a)); double own = la.x * la.x * r.inertiaTensor.x + la.y * la.y * r.inertiaTensor.y + la.z * la.z * r.inertiaTensor.z;
                        var d = r.worldCenterOfMass - com; var dp = d - Vector3.Dot(d, a) * a; I[ax] += own + r.mass * dp.sqrMagnitude;
                    }
                }
                sb.Append($"   inertia about the CoM: pitch {I[0]:F0}, yaw {I[1]:F0}, roll {I[2]:F0} kg m2; CoM {Vector3.Dot(com - inst.transform.position, inst.transform.forward):F3} m fwd / {Vector3.Dot(com - inst.transform.position, inst.transform.up):F3} m up of the root origin\n");
                sb.Append("   bodies: " + string.Join(", ", rbOf.Values.OrderByDescending(r => r.mass).Select(r => { var d = inst.transform.InverseTransformDirection(r.worldCenterOfMass - com); return $"{r.name.Replace("(Clone)", "")} {r.mass:F0} kg at x {d.x:F2} y {d.y:F2} z {d.z:F2}"; })) + "\n");
                // 1.8.8: wheel geometry about the CoM + the LandingGear numbers that set the ground yaw stability (taildragger_track.py)
                foreach (var lg in allGear)
                {
                    var c = CastOf(lg);
                    var d = inst.transform.InverseTransformDirection(c.position - com);
                    sb.Append($"   GEO {lg.name} fwd {d.z:F3} right {d.x:F3} up {d.y:F3} | mu {Gf(lg, "frictionCoef")} resp {Gf(lg, "response")} braked {G(lg, "braked")} steering {G(lg, "steering")} lock {Gf(lg, "steeringLock")} speed {Gf(lg, "steeringSpeed")} align {Gf(lg, "aligningStrength")} diff {Gf(lg, "differentialBrakeFactor")} k {Gf(lg, "springRate")} travel {Gf(lg, "suspensionTravel")} rolling {Gf(lg, "rollingResistance")}\n");
                }
                sb.Append($"   GEO mass {totalMass:F0} yaw {I[1]:F0} pitch {I[0]:F0}\n");
            }
            int steps = Mathf.RoundToInt(cfg.seconds / DT), tail = Mathf.RoundToInt(2f / DT);
            var sums = new List<float>(); var rows = new List<string>();
            for (int s = 0; s < steps; s++)
            {
                float sum = 0f;
                foreach (var g in gears) { float n = Wheel(g, rootRb, cfg.thrust > 0f ? 0f : 1f); g.loads.Add(n); sum += Mathf.Max(n, 0f); }
                sums.Add(sum);
                if (cfg.thrust > 0f && prop != null) rbOf[prop].AddForce(rbOf[prop].transform.forward * cfg.thrust);
                if (cfg.kick != 0f && s == Mathf.RoundToInt(1f / DT)) foreach (var r in gears.Select(g => g.rb).Distinct()) r.velocity += Vector3.down * cfg.kick;
                Physics.Simulate(DT);
                if (cfg.thrust > 0f && s % 60 == 0)
                    rows.Add($"   t {s * DT,5:F1} v {rootRb.velocity.magnitude,5:F1} pitch {-rootRb.rotation.eulerAngles.x:F1} " + string.Join(" ", gears.Select(g => $"{Short(g.name)} {g.loads[s] / 1000f,6:F2}")) + $" sum {sum / 1000f:F2} kN");
            }
            {   // own colliders near the ground at the end (a part resting on the runway would carry load the wheels do not report)
                var low = new List<string>();
                foreach (var rb in rbOf.Values) foreach (var col in rb.GetComponentsInChildren<Collider>(false))
                    if (col.enabled && !col.isTrigger && col.attachedRigidbody == rb && col.bounds.min.y < 0.25f)
                        low.Add($"{col.name} ({col.GetType().Name}, body {rb.name}, layer {col.gameObject.layer}) min y {col.bounds.min.y:F3}");
                sb.Append($"   colliders within 0.25 m of the ground: {(low.Count == 0 ? "none" : string.Join("; ", low))}; layer 14 vs ground layer 0 ignored: {Physics.GetIgnoreLayerCollision(14, 0)}\n");
            }
            if (cfg.thrust > 0f) { sb.Append(string.Join("\n", rows)).Append('\n'); }
            else
            {
                var last = Enumerable.Range(steps - tail, tail).ToList();
                foreach (var g in gears)
                {
                    var L = last.Select(i => g.loads[i]).ToList();
                    sb.Append($"   {g.name,-28} mean {L.Average() / 1000f,7:F2} kN  min {L.Min() / 1000f,7:F2}  max {L.Max() / 1000f,7:F2}  every-6th-step {string.Join(" ", Enumerable.Range(0, 8).Select(j => (g.loads[steps - 1 - 6 * j] / 1000f).ToString("F2")))}  hit {g.hit}\n");
                }
                float mean = last.Average(i => sums[i]);
                float sampled = Enumerable.Range(0, 20).Average(j => sums[steps - 1 - 6 * j]);
                var mains = gears.Where(g => !g.name.Contains("tail")).ToList();
                sb.Append($"   sum of loads: mean {mean / 1000f:F2} kN, sampled every 0.1 s {sampled / 1000f:F2} kN, weight {weight / 1000f:F2} kN -> ratio {mean / weight:F3} (sampled {sampled / weight:F3}); tail share {gears.Where(g => g.name.Contains("tail")).Sum(g => last.Average(i => g.loads[i])) / weight:F3}\n");
                sb.Append($"   end: root v {rootRb.velocity.magnitude:F3} m/s w {rootRb.angularVelocity.magnitude * Mathf.Rad2Deg:F2} deg/s pitch {-rootRb.rotation.eulerAngles.x:F1}; gear bodies v " +
                    string.Join(", ", gears.Select(g => g.rb).Distinct().Select(r => $"{r.name} {r.velocity.magnitude:F3} m/s")) + "\n");
                // period-2 test: step-to-step sign changes of the main loads' deviation from the mean
                foreach (var g in mains.Take(1))
                {
                    var L = last.Select(i => g.loads[i]).ToList(); float m = L.Average(); int flips = 0;
                    for (int i = 2; i < L.Count; i++) if (Mathf.Sign(L[i] - m) != Mathf.Sign(L[i - 1] - m)) flips++;
                    sb.Append($"   {g.name}: deviation sign flips {flips} of {L.Count - 2} steps (period-2 jitter ~ all), rms {Mathf.Sqrt(L.Average(x => (x - m) * (x - m))) / 1000f:F2} kN\n");
                }
            }
            Object.DestroyImmediate(inst);
            foreach (var rb in rbOf.Values) if (rb != null) Object.DestroyImmediate(rb.gameObject);
            Object.DestroyImmediate(ground);
            return sb.ToString();
        }

        // Unity fake-null: an unassigned castPoint (stock COIN) is not C# null, so ?? does not fall back to the bump stop (LandingGear uses castPoint)
        static Transform CastOf(LandingGear lg) { var c = (Transform)G(lg, "castPoint"); return c != null ? c : ((GameObject)G(lg, "bumpStop")).transform; }

        static string Short(string n) => n.Replace("gear_", "").Replace("_leg", "").Replace("_grip", "g").Replace("_sprung", "");

        // one wheel, one step; returns the load (spring + damper, as the in-game wlog "load")
        static float Wheel(Gear g, Rigidbody root, float brakeCmd)
        {
            var p0 = g.cast.position; var dn = -g.cast.up;
            if (!Physics.Linecast(p0, p0 + dn * g.travel, out RaycastHit hit)) { g.hasPatch = false; g.hit = "none"; return 0f; }
            g.hit = hit.collider.name + (hit.collider.attachedRigidbody != null ? "(own body)" : "") + $" d {hit.distance:F3}";
            if (hit.collider.attachedRigidbody != null) { g.hasPatch = false; return 0f; }
            var pv = g.rb.GetPointVelocity(hit.point);
            float x = Mathf.Max(g.travel - hit.distance, 0f);
            float n = g.k * x - Vector3.Dot(hit.normal, pv) * g.c;
            float cap = n * g.mu;
            float gs = Vector3.Dot(pv, g.axle.forward);
            g.brake = Mathf.Lerp(g.brake, g.braked ? brakeCmd : 0f, DT * 5f);
            g.ws += Mathf.Clamp(gs - g.ws, -100f * DT, 100f * DT);
            var dir = Vector3.ProjectOnPlane(pv, hit.normal).normalized;
            Vector3 fr;
            if (Mathf.Abs(gs) < 1f)
            {
                float patch = g.radius * 0.5f;
                if (!g.hasPatch || g.patchCol != hit.collider || (hit.collider.transform.TransformPoint(g.patchLocal) - hit.point).magnitude > patch)
                { g.patchLocal = hit.collider.transform.InverseTransformPoint(hit.point); g.patchCol = hit.collider; g.hasPatch = true; }
                var v7 = (hit.collider.transform.TransformPoint(g.patchLocal) - hit.point) / patch - pv;
                var lat = Vector3.Project(v7, g.axle.right);
                var lon = Vector3.Project(v7, -Mathf.Sign(g.ws == 0f ? 1f : g.ws) * g.axle.forward) * (g.brake + 0.05f);
                fr = Vector3.ClampMagnitude(lat + lon, 1f) * cap;
            }
            else
            {
                g.hasPatch = false;
                var side = Vector3.Cross(dir, hit.normal).normalized;
                var fwd = g.axle.forward * Mathf.Sign(g.ws);
                float slip = Mathf.Clamp(Vector3.SignedAngle(Vector3.ProjectOnPlane(fwd, hit.normal), dir, hit.normal), -10f, 10f);
                var f1 = Mathf.Clamp(slip * g.resp * (0.2f + Mathf.Abs(g.ws) * 0.01f), -1f, 1f) * cap * side;
                var f2 = Mathf.Clamp01(Mathf.Abs(Vector3.Dot(g.axle.forward, side))) * cap * -dir;
                var f3 = -dir * g.brake * cap;
                var f4 = -dir * g.roll * n;
                fr = Vector3.ClampMagnitude(f1 + f2 + f3 + f4, cap);
            }
            // LandingGear behaviour (MODLOG 1.8.2): only the normal force is clamped at >= 0; the friction cap is load x frictionCoef WITHOUT a
            // clamp, so a wheel whose damper term makes the load negative (moving up fast) gets its contact-patch / side / brake / rolling force
            // REVERSED (ClampMagnitude with a negative length flips the vector). Mode 1 = the game's form, 0 = friction only while loaded.
            if (ReversedFriction || n > 0f) g.rb.AddForceAtPosition(hit.normal * Mathf.Max(n, 0f) + fr, hit.point);
            return n;
        }
    }
}
