// Heritage Pairs 1.9.7: no laser fires through its own aircraft (GA-25X belly laser, MSB-17/80 dorsal + ventral lasers).
//
// Why 1.9.6 burned its own wings (game 0.34.6 read as reference; nothing copied):
//   * Laser.FixedUpdate turns the beam (directionTransform) up to Laser.maxAngle away from the Laser's forward toward the target and fires when
//     the beam is within 1 deg of the target line; the damage goes to the FIRST collider on the line aperture -> target, own aircraft included.
//     The stock Laser_EW1 has maxAngle 30: on the EW-25 it looks straight out of the nose, a 30 deg cone with no airframe in it.
//   * On our turrets the Laser's forward is the turret bore. Turret.AimTurret drops the elevation error from "on target" for a weapon that is
//     neither gun nor boresight (the laser), and Turret's own line-of-fire Linecast runs along the BORE, 200 m. So with the turret at its
//     elevation limit (GA-25X belly: -2 deg; MSB dorsal 0, ventral 0) the beam still swings up to 30 deg past the limit - into the wings.
//     The pilot's trigger / the AI can also fire the laser station at any target within 31 deg of wherever the turret points.
//   * The 1.8.14 fire-cone fit (FireClear1814) and the GA-25X envelope scan test the BORE line only: 0 blocked.
// Fix in the data (the EW-25's own mechanism: a beam cone that holds no airframe): Laser.maxAngle = BeamAngle (1 deg), so the beam is the bore
// line +- 1 deg, inside the 2 deg the fit dilates every blocked cell by. The plugin guard (LaserGuard197.cs) covers what data cannot.
//
// This file sweeps BEAM lines, not bore lines. For every target direction on a 2 deg sphere grid in the mount frame:
//   aim vector -> the game's FiringConeChecker (nearest allowed vector) -> the settled turret pose (traverse free, elevation clamped to the
//   limits, posed exactly as Turret.AimTurret) -> stock laser gate (angle bore..target < maxAngle + 1) -> beam = RotateTowards(bore, target,
//   maxAngle) -> ray from the aperture, 45 m, against FireClear1814's obstacles: solid own colliders (= damage), prop strike discs (triggers: the
//   beam ends there, no damage), every visible mesh (the beam drawn across the airframe, no damage).
//   turret path = the turret itself commands fire (cone error < 1 deg);  pilot path = fire commanded from the station (player / AI / the 0.2 s
//   the beam lingers after the last command) with the turret settled on that target.
//   slew = bore cells inside the limits that are blocked (the bore crossing them while fire is commanded): only the plugin guard stops these.
// Run: unity.sh LaserSweep197.Run lasersweep197   (after BuildAll; writes unitylogs\lasersweep197.json and a table in the log)
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class LaserSweep197
    {
        public const float BeamAngle = 1f;        // the 1.9.7 Laser.maxAngle on our turrets (GA25XBuild.LaserBeamAngle197, msb_head LaserBeamAngle197)
        public const float StockAngle = 30f;      // Laser_EW1
        public const float GridStep = 2f, Range = 45f;
        /// the data fix passes when the turret's own fire path has no damage line and the pilot / AI trigger path keeps at most a residual:
        /// lines where the elevation clamp parks the bore on a blocked bore cell (a target inside an exclusion cone at the elevation limit).
        /// No beam angle removes those (they exist at angle 0); the plugin guard (LaserGuard197.cs) holds them.
        public const int PilotResidualMax = 12;
        public static bool Clean(Result r) => r.turretCol == 0 && r.pilotCol >= 0 && r.pilotCol <= PilotResidualMax;
        const BindingFlags BF = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        static object G(object o, string n) { for (var t = o.GetType(); t != null; t = t.BaseType) { var f = t.GetField(n, BF); if (f != null) return f.GetValue(o); } throw new Exception("no field " + n); }

        public class Result
        {
            public string name; public float maxAngle, apertureAxisErr; public int dirs, fired, turretCol, turretDisc, turretMesh, pilotCol, pilotDisc, pilotMesh, slewBlocked;
            public Dictionary<string, int> by = new Dictionary<string, int>();
            public List<string> samples = new List<string>();     // first self-hit lines: target (az, el) in the mount frame, bore (az, el), cone error, what was hit
            public string Top => string.Join(" ", by.OrderByDescending(k => k.Value).Take(6).Select(k => $"{k.Key} {k.Value}"));
            public override string ToString() => $"{name} @ maxAngle {maxAngle:F0}: {dirs} target dirs, laser gate open on {fired}; turret path {turretCol} damage / {turretDisc} prop-disc / {turretMesh} mesh-only lines, pilot path {pilotCol} / {pilotDisc} / {pilotMesh}, blocked bore cells {slewBlocked}{(by.Count > 0 ? " [" + Top + "]" : "")}";
        }

        public static Transform Aperture(Turret t)
        {
            var mount = t.transform.parent != null ? t.transform.parent : t.transform;
            return mount.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name.EndsWith("_aperture") || x.name == "muzzle_laser");
        }

        static readonly RaycastHit[] buf = new RaycastHit[256];
        // what the beam line meets on our own aircraft (not the turret's own moving part), within Range:
        //   2 = a solid own collider (a UnitPart collider: the game's Linecast lands on it and the part takes the laser damage)
        //   1 = at most a prop strike disc (a trigger without a damage receiver: the stock beam ends there, nothing is damaged)
        //   0 = only a visible mesh without a collider (the beam is drawn across it, nothing is damaged);  -1 = nothing
        static (string who, int kind) Hit(FireClear1814.Obstacles ob, Transform own, Vector3 o, Vector3 d)
        {
            int n = Physics.RaycastNonAlloc(o, d, buf, Range, ~0, QueryTriggerInteraction.Collide);
            float best = float.MaxValue; string who = null; int kind = -1;
            for (int i = 0; i < n; i++)
            {
                var h = buf[i];
                if (!ob.src.TryGetValue(h.collider, out var s)) continue;
                bool disc = ob.propDiscs.Contains(h.collider);
                if (h.collider.isTrigger && !disc) continue;
                if (s == own || s.IsChildOf(own)) continue;
                int k = h.collider.transform.parent == ob.tempRoot.transform ? 0 : disc ? 1 : 2;
                if (k > kind) { kind = k; best = float.MaxValue; }
                if (k == kind && h.distance < best) { best = h.distance; who = s.name; }
            }
            return (who, kind);
        }

        public static Result Sweep(GameObject inst, Turret t, FireClear1814.Obstacles ob, float maxAngle)
        {
            var az = t.transform; var el = (Transform)G(t, "elevationTransform"); var mount = az.parent; var ap = Aperture(t);
            var cones = ((IEnumerable)G(t, "firingCones")).Cast<FiringCone>().ToArray();
            float emin = (float)G(t, "minElevation"), emax = (float)G(t, "maxElevation");
            var r = new Result { name = mount != null ? mount.name.Replace("_mount", "") : az.name, maxAngle = maxAngle };
            if (ap == null) { r.name += " (NO APERTURE)"; r.pilotCol = -1; return r; }
            var qa = az.localRotation; var qe = el.localRotation;
            try
            {
                az.localEulerAngles = Vector3.zero; el.localEulerAngles = Vector3.zero;
                r.apertureAxisErr = Vector3.Angle(ap.forward, el.forward);
                var mrot = mount.rotation; var minv = Quaternion.Inverse(mrot);
                for (float te = -88f; te <= 88.01f; te += GridStep)
                    for (float ta = -180f; ta < 179.99f; ta += GridStep)
                    {
                        var tw = mrot * (Quaternion.Euler(0f, ta, 0f) * Quaternion.Euler(-te, 0f, 0f) * Vector3.forward);
                        r.dirs++;
                        bool permitted = FiringConeChecker.VectorWithinFiringCones(cones, tw, out var fin);
                        var v = permitted ? tw : fin;
                        float num = Vector3.Angle(tw, v);
                        var vl = minv * v.normalized;
                        float a = Mathf.Atan2(vl.x, vl.z) * Mathf.Rad2Deg, e = Mathf.Clamp(Mathf.Asin(Mathf.Clamp(vl.y, -1f, 1f)) * Mathf.Rad2Deg, emin, emax);
                        az.localEulerAngles = new Vector3(0f, a, 0f); el.localEulerAngles = new Vector3(-e, 0f, 0f);
                        var bore = ap.forward;
                        if (Vector3.Angle(bore, tw) >= maxAngle + 1f) continue;      // stock laser gate: no fire
                        r.fired++;
                        var beam = Vector3.RotateTowards(bore, tw, maxAngle * Mathf.Deg2Rad, 0f).normalized;
                        var (who, kind) = Hit(ob, az, ap.position + beam * 0.02f, beam);
                        if (who == null) continue;
                        if (kind == 2) r.pilotCol++; else if (kind == 1) r.pilotDisc++; else r.pilotMesh++;
                        if (r.samples.Count < 16) r.samples.Add($"t({ta:F0},{te:F0}) bore({a:F1},{e:F1}) coneErr {num:F1} {(kind == 2 ? "DAMAGE" : kind == 1 ? "disc" : "mesh")} {who}");
                        if (num < 1f) { if (kind == 2) r.turretCol++; else if (kind == 1) r.turretDisc++; else r.turretMesh++; }
                        r.by.TryGetValue(who, out var c); r.by[who] = c + 1;
                    }
            }
            finally { az.localRotation = qa; el.localRotation = qe; }
            var keep = FireClear1814.MuzzleOverride;
            FireClear1814.MuzzleOverride = tr => { var x = Aperture(tr); return x != null ? new[] { x } : null; };
            try { r.slewBlocked = FireClear1814.Sweep(inst, t, ob).blocked.Count(b => b); } finally { FireClear1814.MuzzleOverride = keep; }
            return r;
        }

        static bool IsLaserTurret(Turret t) => G(t, "aimSafetyWeapon") as Gun == null && Aperture(t) != null && !(t.transform.parent != null && t.transform.parent.GetComponentsInChildren<Gun>(true).Length > 0);

        /// every laser turret of a built aircraft at the given beam angle (the check rows call this on the prefab instance)
        public static List<Result> CheckInstance(GameObject inst, float maxAngle)
        {
            var res = new List<Result>();
            using (var ob = FireClear1814.BuildObstacles(inst))
                foreach (var t in inst.GetComponentsInChildren<Turret>(true))
                    if (IsLaserTurret(t)) res.Add(Sweep(inst, t, ob, maxAngle));
            return res;
        }

        public static void Run()
        {
            var open1912 = new StringBuilder();
            var sb = new StringBuilder("{\"grid_deg\": " + GridStep + ", \"range_m\": " + Range + ", \"aircraft\": [\n"); bool first = true; bool ok = true;
            foreach (var (key, prefab, mountGlob) in new[] { ("GA25X", FamilyBuild.FamilyRoot + "/ga25x/GA25X.prefab", FamilyBuild.FamilyRoot + "/ga25x"), ("MSB17", FamilyBuild.FamilyRoot + "/msb17/MSB17.prefab", FamilyBuild.FamilyRoot + "/msb17") })
            {
                var pf = AssetDatabase.LoadAssetAtPath<GameObject>(prefab);
                if (pf == null) { Debug.Log($"[B25H] LaserSweep197 {key}: prefab missing {prefab}"); ok = false; continue; }
                var saved = AssetDatabase.FindAssets("t:Prefab", new[] { mountGlob }).Select(AssetDatabase.GUIDToAssetPath).Select(p => AssetDatabase.LoadAssetAtPath<GameObject>(p))
                    .Where(g => g != null).SelectMany(g => g.GetComponentsInChildren<Laser>(true)).Select(l => (float)G(l, "maxAngle")).ToList();
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(pf);
                try
                {
                    inst.transform.position = Vector3.zero; inst.transform.rotation = Quaternion.identity; Physics.SyncTransforms();
                    var before = CheckInstance(inst, StockAngle); var after = CheckInstance(inst, BeamAngle);
                    bool angOk = saved.Count > 0 && saved.All(m => Mathf.Approximately(m, BeamAngle));
                    foreach (var r in before) Debug.Log($"[B25H] LaserSweep197 {key} BEFORE {r}");
                    foreach (var r in after) Debug.Log($"[B25H] LaserSweep197 {key} AFTER  {r}; aperture axis vs bore {r.apertureAxisErr:F2} deg");
                    foreach (var r in after) if (r.samples.Count > 0) Debug.Log($"[B25H] LaserSweep197 {key} AFTER  {r.name} lines: {string.Join(" | ", r.samples)}");
                    foreach (var ang in new[] { 0.25f, 0.5f, 0.75f, 2f, 5f, 10f })      // information: how the residual depends on the beam angle
                        foreach (var r in CheckInstance(inst, ang)) Debug.Log($"[B25H] LaserSweep197 {key} SCAN   {r}");
                    // 1.9.12: the same beam sweep with the airbrake panels fully OPEN (the stock Airbrake pose: each hinge rotated maxAngle about its local X).
                    // Panels carry no collider, so the damage and prop-disc counts must equal the shut pose; no beam line may end on a panel mesh either.
                    bool openOk = true;
                    var ab1912 = inst.GetComponentInChildren<Airbrake>(true);
                    var hinges1912 = ab1912 != null ? ((Transform[])G(ab1912, "transforms") ?? new Transform[0]) : new Transform[0];
                    if (hinges1912.Length > 0)
                    {
                        float oa = (float)G(ab1912, "maxAngle"); var keepRot = hinges1912.Select(x => x.localRotation).ToArray(); List<Result> open;
                        try { foreach (var x in hinges1912) x.Rotate(new Vector3(oa, 0f, 0f), Space.Self); Physics.SyncTransforms(); open = CheckInstance(inst, BeamAngle); }
                        finally { for (int i = 0; i < hinges1912.Length; i++) hinges1912[i].localRotation = keepRot[i]; Physics.SyncTransforms(); }
                        openOk = open.Count == after.Count;
                        for (int i = 0; i < open.Count && i < after.Count; i++)
                        {
                            var o = open[i]; var c = after[i];
                            int onPanel = o.by.Where(k => k.Key.StartsWith("airbrake") || k.Key.StartsWith("spoiler")).Sum(k => k.Value);
                            bool rowOk = Clean(o) && o.turretCol == c.turretCol && o.pilotCol == c.pilotCol && o.turretDisc == c.turretDisc && o.pilotDisc == c.pilotDisc && onPanel == 0;
                            openOk &= rowOk;
                            Debug.Log($"[B25H] LaserSweep197 {key} OPEN   {o}; panels open {oa:F0} deg ({hinges1912.Length} hinges): {onPanel} beam lines on a panel; shut pose damage {c.turretCol} / {c.pilotCol}, disc {c.turretDisc} / {c.pilotDisc}, mesh {c.turretMesh} / {c.pilotMesh} -> {(rowOk ? "PASS" : "FAIL")}");
                            open1912.Append((open1912.Length > 0 ? ",\n" : "") + $"  {{\"aircraft\": \"{key}\", \"turret\": \"{o.name}\", \"open_deg\": {oa}, \"hinges\": {hinges1912.Length}, \"turret_damage\": {o.turretCol}, \"turret_disc\": {o.turretDisc}, \"turret_mesh\": {o.turretMesh}, \"pilot_damage\": {o.pilotCol}, \"pilot_disc\": {o.pilotDisc}, \"pilot_mesh\": {o.pilotMesh}, \"lines_on_panel\": {onPanel}, \"shut_turret_mesh\": {c.turretMesh}, \"shut_pilot_mesh\": {c.pilotMesh}, \"pass\": {(rowOk ? "true" : "false")}}}");
                        }
                        Debug.Log($"[B25H] LaserSweep197 {key}: panels-open sweep {(openOk ? "PASS" : "FAIL")}");
                    }
                    else Debug.Log($"[B25H] LaserSweep197 {key}: no Airbrake hinges (airbrake panels flag off): no panels-open sweep");
                    bool clean = after.Count > 0 && after.All(Clean) && before.Sum(r => r.pilotCol) > 50 * Mathf.Max(1, after.Sum(r => r.pilotCol));
                    Debug.Log($"[B25H] LaserSweep197 {key}: saved Laser.maxAngle [{string.Join(", ", saved)}] {(angOk ? "OK" : "FAIL")}; beam sweep {(clean ? "PASS" : "FAIL")} ({after.Count} laser turrets)");
                    ok &= angOk && clean && openOk;
                    foreach (var (tag, list) in new[] { ("before_30", before), ("after", after) })
                        foreach (var r in list)
                        {
                            if (!first) sb.Append(",\n"); first = false;
                            sb.Append($"  {{\"aircraft\": \"{key}\", \"turret\": \"{r.name}\", \"case\": \"{tag}\", \"max_angle\": {r.maxAngle}, \"dirs\": {r.dirs}, \"gate_open\": {r.fired}, \"turret_damage\": {r.turretCol}, \"turret_disc\": {r.turretDisc}, \"turret_mesh\": {r.turretMesh}, \"pilot_damage\": {r.pilotCol}, \"pilot_disc\": {r.pilotDisc}, \"pilot_mesh\": {r.pilotMesh}, \"blocked_bore_cells\": {r.slewBlocked}, \"hit_by\": {{{string.Join(", ", r.by.OrderByDescending(k => k.Value).Select(k => $"\"{k.Key}\": {k.Value}"))}}}}}");
                        }
                }
                finally { Object.DestroyImmediate(inst); }
            }
            sb.Append("\n], \"pass\": " + (ok ? "true" : "false") + "}\n");
            File.WriteAllText(@"C:\Users\User\nuclearoption-ref\unitylogs\lasersweep197.json", sb.ToString());
            File.WriteAllText(@"C:\Users\User\nuclearoption-ref\unitylogs\lasersweep1912_open.json", "{\"rows\": [\n" + open1912 + "\n]}\n");   // 1.9.12 (the 1.9.7 json above keeps its form)
            Debug.Log($"[B25H] LaserSweep197 {(ok ? "ALL PASS" : "FAIL")}");
        }
    }
}
