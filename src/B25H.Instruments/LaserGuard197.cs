// B25H.Instruments 1.9.7: the GA-25X / MSB-17/80 lasers never fire through their own aircraft.
//
// Cause of the 1.9.6 self-hits (game 0.34.6, read as reference only): Laser.FixedUpdate steers its beam (directionTransform) up to maxAngle
// (30 deg on the stock Laser_EW1 we cloned) away from the Laser's own forward toward the target and then damages the FIRST collider on the
// line from the aperture to the target, with no own-aircraft filter. The EW-25's laser looks straight out of the nose, so that 30 deg cone holds
// no airframe. Ours sit on turrets: the beam is not the bore line, the turret reports "on target" without the elevation error for a weapon
// that is neither gun nor boresight, and the pilot's own trigger / the AI can fire the station wherever the turret points. The 1.8.14 fire-cone
// fit swept the BORE line only, so it found 0 blocked cells.
// Fix in the pack (1.9.7): maxAngle 30 -> LaserBeamAngle197 so the beam is the bore line the fit certifies (dilated). This guard is the second
// layer for what data cannot know: gear down, bay doors open, stores, damaged / shifted parts, the stowed pose.
//
// Guard: Harmony prefix on Laser.FixedUpdate, only for lasers whose unit is one of ours (cached per Laser). While fire is commanded it rebuilds
// the beam line with the game's own rule and holds the beam for this physics step (fireCommanded = false: the stock code then switches the beam
// off and draws no power) if any collider of OUR OWN unit lies on the line before the target. One RaycastNonAlloc per firing laser per step, no
// scene search, no allocation. Missiles are not our unit, so interception is untouched whenever the line is clear.
// Flag: config [Laser] LaserGuard197 = Auto (build default) / On / Off. Any exception disables the guard for the session (stock behaviour).
using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class LaserGuardMath
    {
        public static bool IsGuardKey(string key) => key == "GA25X" || key == "MSB17";   // 1.9.9: was "MSB1780"
        /// the game's beam direction: the Laser's forward turned toward the target by at most maxAngle (Vector3.RotateTowards)
        public static Vector3 BeamDir(Vector3 forward, Vector3 toTarget, float maxAngleDeg) => Vector3.RotateTowards(forward, toTarget, maxAngleDeg * Mathf.Deg2Rad, 0f);
        /// the stock fire gate: fire only while the beam is within 1 deg of the target line
        public static bool WouldFire(Vector3 beamDir, Vector3 toTarget) => Vector3.Angle(beamDir, toTarget) < 1f;
        /// hold when an own collider lies on the line nearer than the target (ownHit < 0 = none)
        public static bool Hold(float ownHit, float targetDistance) => ownHit >= 0f && ownHit < targetDistance;
    }

    public partial class Plugin
    {
        const bool LaserGuardDefault197 = true;
        static BepInEx.Configuration.ConfigEntry<string> laserGuardMode;
        static bool laserGuardBroken;
        static int laserGuardHolds, laserGuardLogs;
        static FieldInfo lgFire, lgTargetT, lgTarget, lgDir, lgMaxAngle;
        static readonly Dictionary<Laser, bool> laserOurs = new Dictionary<Laser, bool>();

        static bool LaserGuardOn
        {
            get { var m = laserGuardMode != null ? laserGuardMode.Value : "Auto"; return m == "On" || (m != "Off" && LaserGuardDefault197); }
        }

        void PatchLaserGuard()
        {
            laserGuardMode = Config.Bind("Laser", "LaserGuard197", "Auto", "1.9.7: the GA-25X / MSB-17 lasers hold their beam whenever its line crosses their own aircraft. Auto = build default, On, Off.");
            if (!LaserGuardOn) { Logger.LogInfo("1.9.7 laser guard: off (config [Laser] LaserGuard197)"); return; }
            try
            {
                const BindingFlags f = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
                lgFire = typeof(Laser).GetField("fireCommanded", f); lgTargetT = typeof(Laser).GetField("currentTargetTransform", f);
                lgTarget = typeof(Weapon).GetField("currentTarget", f); lgDir = typeof(Laser).GetField("directionTransform", f); lgMaxAngle = typeof(Laser).GetField("maxAngle", f);
                var m = typeof(Laser).GetMethod("FixedUpdate", f);
                if (lgFire == null || lgTargetT == null || lgTarget == null || lgDir == null || lgMaxAngle == null || m == null) { Logger.LogWarning("1.9.7 laser guard disabled: Laser members not found"); return; }
                new HarmonyLib.Harmony("b25h.instruments.laserguard197").Patch(m, prefix: new HarmonyLib.HarmonyMethod(typeof(Plugin).GetMethod(nameof(LaserGuardPrefix), BindingFlags.Static | BindingFlags.NonPublic)));
                Logger.LogInfo("1.9.7 laser guard on (GA25X, MSB17): beam held while its line crosses the own aircraft");
            }
            catch (Exception e) { Logger.LogWarning("1.9.7 laser guard disabled: " + e.Message); }
        }

        static bool LaserGuardPrefix(Laser __instance)
        {
            if (laserGuardBroken) return true;
            try
            {
                var unit = __instance.attachedUnit;
                if (unit == null) return true;
                if (!laserOurs.TryGetValue(__instance, out var ours))
                {
                    if (laserOurs.Count > 256) laserOurs.Clear();
                    var ac = unit as Aircraft;
                    ours = ac != null && ac.definition != null && LaserGuardMath.IsGuardKey(ac.definition.jsonKey);
                    laserOurs[__instance] = ours;
                }
                if (!ours || !(bool)lgFire.GetValue(__instance)) return true;
                var dirT = lgDir.GetValue(__instance) as Transform;
                if (dirT == null) return true;
                var self = __instance.transform;
                var tt = lgTargetT.GetValue(__instance) as Transform; var target = lgTarget.GetValue(__instance) as Unit;
                // the game's own target point (Laser.FixedUpdate): the tracked part, or the faction's known position when the target is not tracked
                Vector3 aim = tt != null ? tt.position : self.position + self.forward * 20000f;
                if (target != null && unit.NetworkHQ != null && !unit.NetworkHQ.IsTargetBeingTracked(target) && unit.NetworkHQ.TryGetKnownPosition(target, out var known)) aim = known.ToLocalPosition();
                Vector3 to = aim - self.position;
                var dir = LaserGuardMath.BeamDir(self.forward, to, (float)lgMaxAngle.GetValue(__instance));
                if (!LaserGuardMath.WouldFire(dir, to)) return true;                 // the stock code does not fire this step
                float dist = Vector3.Distance(dirT.position, aim);
                // the game's own cast (Laser.FixedUpdate): the first collider on the line aperture -> target takes the damage. Hold only when that
                // collider is ours, so a clear line - or one that ends on anything else first - is left exactly as stock.
                float own = -1f;
                if (Physics.Linecast(dirT.position, aim, out var hit, ~(1 << 13)) && hit.collider != null)   // 13 = ExclusionZones, the game's own mask
                {
                    var part = hit.collider.GetComponentInParent<UnitPart>();
                    bool mine = part != null ? part.parentUnit == unit : hit.collider.transform.IsChildOf(unit.transform);
                    if (mine) own = hit.distance;
                }
                if (!LaserGuardMath.Hold(own, dist)) return true;
                lgFire.SetValue(__instance, false);                                  // stock FixedUpdate now takes its "not firing" branch: beam off, no power, no damage
                laserGuardHolds++;
                if (laserGuardLogs < 10 && (laserGuardHolds == 1 || laserGuardHolds % 500 == 0)) { laserGuardLogs++; Log.LogInfo($"1.9.7 laser guard: beam held on {unit.name} (own collider at {own:F1} m on the line); holds so far {laserGuardHolds}"); }
            }
            catch (Exception e) { laserGuardBroken = true; Log.LogWarning("1.9.7 laser guard disabled: " + e.Message); }
            return true;
        }
    }
}
