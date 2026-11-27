// FD-32 Nimrod (Heritage Pairs, fourth aircraft, jsonKey FD32): the 2080s rebuild of the Hawker Nimrod Mk I. Builds the Blueprinter
// prefab + assets from our own procedural model (blender/fd32, derived from blender/nimrod) into heritage_pairs/fd32 (FamilyBuild.cs).
//
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FD32Build.Build fd32_build      (build + check + family pack)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FD32Build.Check fd32_check      (check only)
//   bash C:/Users/User/nuclearoption-ref/unity.sh - family_build -executeMethod B25HTools.FamilyBuild.BuildAll   (all four + pack)
//
// A COPY of NimrodBuild.cs (the GA-25X precedent: copy, not refactor; NimrodBuild.cs is untouched) with the FD-32 changes
// (docs/fd32_design.md): electric TurbineEngine + stock afterburner-style BOOST detent (GA-25X HybridBoost), 4-blade fal prop,
// 12.7 mm guns, 4 pylons with stock stores, flaperons on all four panels (ControlSurface roll + HighLiftDevice droop pivot / area),
// enclosed tilt-up hood + stock ejection seat (GA-25X EjectionSeats / StockCockpitKit), modern kitbash cockpit (stock SFB-81 stick /
// throttle, stock tac + target-cam screens), retractable sensor ball (HighLiftDevice mover) with the TargetDetector / TargetCam, a stock
// Radar (VT-7 values), lowest IR, radarSize 0.25, 48 flares, both-faction liveries. Kept from the Mk I 1.4.x: crash impact damage per
// part, stiff gear with a stock-like break limit, aileron airfoil, gentle wing stall, alpha limiter + incidence = wing CLmax angle.
// Helper sections marked "from B25HBuild.cs" are verbatim copies (renamed outputs only).
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
    public static class FD32Build
    {
        // ------------------------------------------------------------------ paths and identity
        const string ModName = "fd32";
        const string DisplayName = "FD-32 Nimrod";
        const string Version = "2.5.0";   // round 11: sensor bay cut open, ball stowed inside a closed well   // round 10: CI-22 single throttle (slides), Mk I-only fin horn / mast fix
        const bool SensorWithGearUp = true;     // round 9 (user: the ball was backwards): the ball is lowered by the left main LandingGear's movingParts (gear up = out), not by a speed HLD
        const bool StockThrottle = true;        // round 9: stock SFB-81 sfb_throttle on cockpit_throttle, range from Darkreach (52), sign checked (grips forward)
        const bool StockStructure = true;       // 1.8.3 (user: "look at how stock aircraft use internal parts"): our 'structure' submeshes (break faces, engine body, tank) drawn with the stock aircraft_structure (Lit_vertexcolor, vertex colour 92 = stock exterior structure, UV0 = detail x 1.25)
        const bool RootColliderHull182 = true;  // 1.8.3: the FD32 root collider is baked from the contract's collider_fus_center (the 1.8.2 fus_center skin hull) so the rebuilt cockpit opening does not move the root body's CoM / inertia
        const float SensorArm = 3.0f;           // m: pivot of the ball arm ahead of the ball (round 11: stowed fully inside the cut-open bay, travel 0.375 m -> 7.2 deg, drift 23 mm); = fd32_spec.SENSOR_ARM   // round 7: tilted-axis gear (wheel flat under the wing root), faint cockpit glass, windscreen side skirts
        const bool InwardCockpitGlass = true;   // round 6: cockpit-layer glass copies built with reversed winding (COIN glass_int culls back faces; our glass faces out)
        const bool FixedTailwheel = true;
        // 1.8.7 offline G (in-game 1.8.6: the windscreen-base / hood-outline line is the stock glass's sharp reflection of the probe's sunlit
        // ground at grazing angles; 1,243 / 1,268 yellow px at smoothness 0.95, 0 / 29 at 0.3 via matset): the FD-32's own exterior glass
        // FD32_glass gets a lower smoothness, chosen in the offline reflection model (scratch_G2\sweep); metallic, colour, texture, alpha and
        // the stock shader stay. Cockpit-layer copies (glass_ck / glass_int) unchanged. false = 1.8.6 (stock 0.95).
        const bool GlassGloss187 = true;
        public const float GlassSmooth187 = 0.45f;
        const bool TiltedGearAxis = true;       // round 7: mains fold about the contract axis (an axis frame above the LandingGear hinge); false = lateral axis
        const bool FaintCockpitGlass = true;    // round 7: cockpit-layer glass = a faint URP-Lit transparent (COIN prop-disc material values), NOT the canopy_int shader (B-25H 2026-10-30 lesson: it darkens the view)       // round 6: the tailwheel never retracts (foldDegrees 0.5, no drag change)
        const string Folder = FamilyBuild.Combined ? FamilyBuild.FamilyRoot + "/fd32" : "Assets/Blueprinter/Mods/" + ModName;
        const string RepoModel = @"C:\Users\User\Nuclear Option B-25\assets\model_fd32\fd32.fbx";
        const string RepoTextures = @"C:\Users\User\Nuclear Option B-25\assets\textures_fd32";
        const string SrcDir = "Assets/FD32Source";
        const string DNS = "Assets/Blueprinter/_donotship";
        const string JsonKey = "FD32";
        const string LogPath = @"C:\Users\User\nuclearoption-ref\unitylogs\fd32_check_table.txt";

        // ------------------------------------------------------------------ feature flags (ON = in the build for the live probe; each restores a plainer variant when false)
        const bool OwnVickersInfo = false;      // (Mk I) FD-32: stock Gun12.7mm info
        const bool SyncMuzzlesAhead = true;     // synchroniser: bullet origins ahead of the prop plane (BulletSim Linecasts hit our prop-strike trigger otherwise)
        const bool GunsAirOnlyForAI = false;
        const bool CooperBombs = false;         // (Mk I) no Cooper racks on the FD-32
        const bool OwnTailHookMount = true;     // own hook mount (stock TailHook values, Mk I pattern)
        const bool AllHangarTypes = true;       // hangar_med, revetment1, shelter1, Cursor LFD, Annex R1-R3 + M, Hyperion R1-R3
        const bool TacScreen = true;            // mfd_center = stock tacScreenDisplay
        const bool KeepFlareEjector = true;
        const bool StockHUDExtras = true;       // HUD extras: stock Multirole1 (KR-67) = throttle bar with the divided afterburner (BOOST) section (GA-25X JetThrottleHUD)
        const bool HybridBoost = true;          // BOOST detent: a ~0 N stock Turbojet + JetNozzle whose Afterburner adds BoostThrust from 90 % throttle (GA-25X)
        const bool Flaperons = true;            // lower-wing flaperons (roll) + HighLiftDevice droop on all four panels; false = ailerons only, no flap area
        const bool SensorBall = true;           // sensor ball moved by a HighLiftDevice (down below SensorDownSpeed); TargetDetector scanner + TargetCam in the ball
        const bool WingRadar = true;            // stock Radar (VTOLTrainer1 values, 35 km); false = no radar (CI-22 has none)
        const bool EjectionSeats = true;        // Pilot.ejectionSeat true; the hood is a stock Canopy (jettisoned first)
        const bool StockCockpitKit = true;      // stock SFB-81 joystick on our empty; stock seat on the figure; round 3: our fal throttle lever in a quadrant
        const bool NoNavLights = false;         // FD-32: stock-style nav lights (Point light 0.40 m outboard, short range: Mk I 1.3.2 layout)
        const float QuiltTiling = 1f;

        // ------------------------------------------------------------------ FD-32 numbers (docs/fd32_design.md 4; tools/flightmodel/fd32_fm.py keeps the same values)
        const float WingIncidence = 1.5f;   // deg (Mk I)
        const float StabIncidence = -0.5f;
        const float EnginePower = 480e3f;   // W game "thrust power" = 600 kW motor continuous x 0.80 (fd32_fm.P_CONT)
        const float BoostThrust = 4000f;    // N afterburner-style BOOST from 90 % throttle, x clamp(airDensity, 0.4, 1). Round 3: 2.6 kN was not felt (user); fd32_fm: +87 km/h, climb +12 m/s
        const float BoostFuel = 0.06f;      // kg/s extra at full boost (the fuel cost of BOOST)
        const float BoostIR = 0.1f;         // Afterburner.IRIntensity (electric: almost nothing)
        const float BladeEfficiency = 0.125f; // Mk I 1.2.2 game calibration (static thrust, roll)
        const float PropTargetAoA = 8f;
        const float TailSteeringLock = -40f;   // 1.8.1: -50 -> -40 (taildragger_ground.py: 10 m/s full-rudder turn body slip 45 -> 35 deg with the 0.35 side grip, taxi 7 m/s 6 s 167 deg, no roll-over; -35 gave 30 deg but a wider AI taxi radius at the K92 corner). Was:   // 1.7.12: -30 -> -50 as the Mk I 1.7.5 (AI taxi turns at the K92 runway corner)
        // 1.8.0 (user on 1.7.13: "keep spinning out on runways"): split main wheel, see NimrodBuild.cs and GripGear.cs. Both LandingGears per wheel
        // frictionCoef 0.8 (stock); the braked one carries MainBrakeShare of the spring -> braking 0.20 x load as 1.7.13, side grip 0.8 x load.
        const float MainGearFriction = 0.8f;    // 1.8.0: stock; 1.7.13 0.20 (one gear per wheel)
        const float MainBrakeShare = 0.25f;
        // 1.8.1 (in game 1.8.0: Mk I flipped 2/2 under full brakes at 2.8 m/s2, keyboard-rudder take-offs ground-looped, taxi turns rolled onto a
        // wing tip; tools/flightmodel/taildragger_ground.py, validated on the 1.7.13 AND 1.8.0 wheel logs for turns, taxi and braking): the grip
        // leg's own friction 0.20 (side grip 0.8 x 0.25 + 0.20 x 0.75 = 0.35 x load, 1.75x 1.7.13; 0.8 gave 0.51 g lateral = past the 0.5 g
        // roll-over limit of a 1.8 m track under a 1.8 m CoM); rolling resistance moved onto the braked leg (0.20 x 0.25 = the 1.7.13 0.05 x
        // load, absorbed under the braked leg's cap when braking) and none on the grip leg, so full braking is exactly 1.7.13's 0.20 x load.
        const float GripFriction = 0.20f, BrakedRolling = 0.20f, GripRolling = 0f;     // 1.8.0
        const bool SplitMainGear = true;        // 1.8.0: false = the 1.7.13 single gear per wheel (then set MainGearFriction 0.20)
        // 1.8.0 (user: "when a wing is lost the landing gear stays on the aircraft"): the main legs hang from the lower-wing roots (gear_mount_L/R
        // is part of wing_lower_L/R), so the gear is now built on wing_lower_L/R (attachedPart, hinge parent) like the B-25H gear on its nacelles
        // and the B-17G gear on wing_inner: LandingGear subscribes to attachedPart.onParentDetached and breaks off with that wing. Each wing now
        // carries half of MainGearDrag while the gear is down (the pair used to write the root).
        const bool GearOnLowerWing = true;
        // 1.8.2 (offline worker; in game 1.8.0 / 1.8.1 the FD-32's wheel loads alternate every 1/60 s physics step - rest: mains 4.1 + 12.3 kN per
        // side with the tail wheel at -1.6 kN, next step mains ~0 with the tail at +4.1; the mean of the two applied totals, (32.7 + 4.1) / 2 =
        // 18.4 kN, is the weight, and the wheel log's 0.1 s rows (6 steps) always caught the same phase, so the loads "did not add up" and the
        // tail wheel read "never loaded"). Cause: since 1.8.0 the main legs push on the 51 kg lower-wing bodies (the game gives every part of a
        // locally simulated aircraft its own Rigidbody + FixedJoint: AeroPart.CreateRB / CreateJoints). Per physics step their damper is
        // c dt / m = 20000 / 60 / 51 = 6.5 and the spring k dt^2 / m = 1.09, outside every gear body that runs smoothly in game (Mk I root
        // 300 kg: 2.2 / 0.37; FD-32 1.7.13 root: 2.0 / 0.34; B-25H nacelle 300 kg: 3.3 / 0.69; B-17G wing 1500 kg: 1.4 / 0.30; tail wheels on
        // 50-55 kg tail cones: 2.7-3.0 / 0.6). Fix kept on the wing (it still breaks off with it): lower-wing parts 51 -> 100 kg, taken from
        // fus_engine (805 -> 707, same total, CoM 6 cm aft / 2 cm down: tail share 0.173 -> 0.182, roll inertia +27 %, unity GroundPhysX), and
        // the main damping 20000 -> 13000 N s/m (heave damping ratio ~0.79 -> ~0.51): 2.17 / 0.56, inside the proven envelope.
        const bool WingGearStiffBody = true;          // false = the 1.8.1 masses and damping
        // 1.8.3 offline D (in game 1.8.2, probe P1: at rest the wheel loads still flip every 1/60 s step - tail +6.90 / total 11.2 kN, then
        // -0.47 / 25.25 kN, pitch 13.3 / 13.5; study\ingame_182 p1_summary.txt). Live setf on that aircraft: tail-leg dampingRate 9000 -> 6750
        // OR all four main legs x 0.75 (3250 / 9750 -> 2437 / 7312) each stops it (tail 3.4 kN, total 18.3-18.6 kN), and the 1.8.2 values bring
        // it back within 4 s; tail 6750 alone still left a steady +-0.18 kN two-step ripple (p1x_tail6750.csv: on the edge), mains x 0.75 alone
        // +-0.01 kN. So 1.8.2 sits just past a stability boundary that both dampers feed (explicit damper on light part bodies: per step
        // c dt / m). Both reduced x 0.75: a boundary linear in the two damping scales that passes through the in-game edge (mains 1, tail 0.75)
        // and leaves (0.75, 1) inside puts (0.75, 0.75) 14-25 % inside it (tools/flightmodel/fd32_gear_damping.py). Heave damping ratio
        // mains ~0.52 -> ~0.39, tail ~0.68 -> ~0.51; 8 m/s touchdown peak 0.25 -> 0.30 m of the 0.50 m break (leg breaks from a ~13.5 m/s
        // sink, was ~16.5), 3 m/s rebound +30 %; hook arrest / brake pitch unchanged in the arrest model (same script). Springs, masses,
        // friction and geometry unchanged. false = the 1.8.2 damping.
        const bool GearDamping183D = true;
        const float GearDampingScale183D = GearDamping183D ? 0.75f : 1f;
        const float WingLowerMass = WingGearStiffBody ? 100f : 51f;
        const float EngineMass = 805f - 2f * (WingLowerMass - 51f);
        // 1.8.2: the BOOST JetNozzle's thrustTransform sat on the exhaust pipe, 0.47 m right of the centreline (dump_fd32_after181 4867-4972;
        // JetNozzle applies its thrust there, decompile JetNozzle.cs 409): from throttle 0.9 the 4 kN boost yawed the FD-32 with ~1.9 kN m on
        // every full-throttle take-off (the FD-32's one-way gentle swing, 7.3 deg in 1.7.13; the Mk I has no boost and swings 0.2). Now on the
        // centreline at the same height and station (the boost has no visible flame; the IR source stays the TurbineEngine's exhaust_point).
        const bool BoostOnCentreline = true;
        // 1.8.0 (user: remove the "capacitor" from the FD-32 UI): the HUD line "CAPACITOR x kJ" is the stock ChargeIndicator, shown while the
        // aircraft's PowerSupply has a user; our stock Radar is its only user and Radar.powerRatio is never read (fd32_design 21.3). No
        // PowerSupply on the FD-32 now: ChargeIndicator / Radar null-check it; jammers, lasers, energy weapons (which do need it) are not fitted.
        const bool CapacitorPowerSupply = false;
        const float MainContactForward = 0f;   // 1.7.13: 0.20 -> 0 (1.7.12 forward ground contact removed with the 0.30 friction; the code path is kept)
        const float MainSideResponse = 1.0f;   // 1.8.0: stock 1 (1.7.13 1.5 had no measurable effect in game). 1.7.13 note: LandingGear.response on the braked mains 1 -> 1.5. Rolling side force = clamp(slip deg x response x (0.2 + 0.01 x wheel speed)) x frictionCoef x load, capped at frictionCoef x load; braking = brake x frictionCoef x load. So response x friction = 0.30 gives the 1.7.12 cornering stiffness (the K92 corner taxi: 2 of 2 at friction 0.30) while braking, the side-grip cap and the < 1 m/s contact patch stay at 0.20 (1.7.11 nose-over behaviour)
        // 1.8.8 (user on 1.8.7: line up, full throttle, no input -> the B-17G and both Nimrods veer left or right, "propeller pull is not the
        // cause"): castoring mains (GripGear.Castor; tools/flightmodel/taildragger_track.py). It is not the prop: a gripping wheel AHEAD of the
        // CoM is directionally unstable under LandingGear's side force (627-656); stock tricycles grip behind the CoM and castor the wheel in
        // front (aligningStrength 5). Here the mains are ahead (the CoM sits 0.62-1.10 m behind them) and the tail wheel loses its load at
        // ~23 m/s (1.8.2 logs), leaving ~1 s on the mains alone before they unload. Mirrored stock arrangement: the mains castor within
        // +-MainCastorRange (steeringSpeed 0), the tail wheel stays the locked, gripping wheel. Model (FD-32): no input, 90 % heading 0.17 -> 0.12 deg; gusts 3.61 -> 2.32 deg (stock CI-22 3.17); wheel-landing roll-out 4.75 -> 0.20 deg; taxi 7 m/s 6 s 172 -> 172 deg. false = the 1.8.7 behaviour.
        const bool MainCastor188 = true;
        const float MainCastorRange = 6f, MainCastorAlign = 5f;
        // pre-1.7.12 note: round 9 (user: tips over on landings / spawn): tan-1(0.20) = 11.3 deg < tail-up CoM angle ~16.5 deg (fd32_design 21.4); was 0.3
        const bool NoGearSafety = true;
        const float AlphaLimiter = 15.5f;    // Mk I 1.4.2: limiter + incidence = the wing's CLmax angle (17.0)
        const bool HyperionR2Only = false;
        const int TracerRatio = 5; const float TracerSize = 1.0f;   // stock 12.7 mm
        const float PropRpm = 1640f;
        const float FuelKg = 280f;
        const float FuelBurn = 0.096f;      // kg/s at full continuous power (TurbineEngine burns x (P/Pmax)^2): fd32_fm 750 km at 280 km/h
        const float GunFireRate = 900f;     // rounds/min per gun (stock 12.7 mm)
        const int GunRounds = 400;          // per gun
        const float IRMin = 0.3f, IRMax = 0.6f;   // lowest in the game (stock minimum 1 / 1.6, Mk I 0.6 / 0.9)
        const float RadarSize = 0.25f;
        const float ValueM = 9.8f;
        const int Flares = 48;
        const float FBWgLimit = 8f;         // HUD ~ gLimit + 1 = ~9 g (GA-25X fbw.py)
        const float FBWCorner = 86f;
        // flaperons: HighLiftDevice per wing panel (+area, droop pivot on the panel's control surface), fd32_fm FLAP_AREA / stall
        const float FlapAreaPerPanel = 0f;          // round 3: no HighLiftDevice area (stock flap pattern instead: ControlSurface flap mode on the droop pivots); fd32_fm.FLAP_AREA 0
        const float FlapSpeedDeployed = 33f, FlapSpeedRetracted = 50f;   // m/s: full droop below 120 km/h, none above 180
        const float SensorDownSpeed = 70f, SensorUpSpeed = 85f;          // m/s: ball down below 250 km/h, stowed above 305
        const bool CockpitV2 = true;
        static Vector3 bombCentre = Vector3.zero;
        const float SpawnLift = 0.03f;
        const float NavLightOutboard = 0.40f, NavLightRange = 0.55f;
        const bool TailSkid = true;
        const bool HookVisualAFrame = false;   // round 3: the modern fal hook IS the functional hook mesh (rendered); no Mk I A-frame
        const bool OwnWeaponIcons = false;
        const bool CrashImpactDamage = true;
        // 1.9.11 (user: on a carrier lift the FD-32's rudder gets damaged, sometimes it snaps off): two stock lifts (hangar_R1 of the Annex and the Hyperion) carry an
        // invisible 'backstop' box behind the spawn point; a low taildragger rudder that reaches back over it lands on it in the spawn drop while the lift starts rising.
        // (a) spawn further forward with the game's own field spawnOffset.z (stock: CI-22 +0.42, helicopters +1.0), so the rudder's aft end is at least 0.3 m AHEAD of both
        //     backstop faces in plan view (LiftSpawn1911.cs measures it against the stock carrier prefabs at build time);
        // (b) the rudder takes no impact damage, exactly as every stock rudder is set (threshold 0, multiplier 0): a touch can no longer destroy a 6 kg part. It still comes
        //     off in a crash through its joints (break force unchanged), through weapon damage, or together with the fin / rear fuselage, which keep their impact damage.
        // false = the 1.9.10 values (spawnOffset.z 0, rudder impact damage as every other airframe part).
        public const bool LiftSpawnFix1911 = true;
        public const float SpawnForward1911 = 1.2f;   // m: rudder aft end 0.39 m ahead of the Annex backstop face, 0.61 m ahead of the Hyperion one (0.6 m would leave it 0.21 m BEHIND the Annex face, clear only by height)
        // 1.9.12 (user: the upgraded aircraft get real airbrake panels "in the appropriate places" that deploy when the aircraft is airbraking): two small
        // flank panels on fus_rear (Blender y -2.47 .. -3.05, z -0.32 .. +0.05: aft of the faction mark, under the green side strip, ahead of the serial / naval
        // title, above the flare ejectors and the hook slot), front-hinged on a vertical hinge line, driven by ONE stock Airbrake on the root (Airbrake.cs: opens
        // at throttle 0 over 1 / openSpeed s, rotates every transform +maxAngle about its local X, force = dragAmount x rho x V^2 on part.rb). The panels come from
        // their own FBX (assets\model_fd32\fd32_airbrake.fbx + fd32_airbrake.json, blender\fd32\run_airbrake1912_fd32.py; the main model is not rebuilt): thin
        // plates 4.2 mm proud of the uncut skin carrying the skin's own atlas texels, no collider, not parts; fus_rear's mesh and hull are untouched.
        // false = 1.9.11 (no FBX import, no objects, no Airbrake). Round 2 (user: "whenever the throttle is below 5 % the airbrakes are on,
        // does not matter if it is on the ground or sky"): nothing here gates the brake; the throttle threshold is the plugin's (AirBrake1912.cs). The panels stand open
        // when parked at idle. Seam band, rim and hinge knuckles are FD32_cove (dark matte, non-metallic): a thin dark line and two dark blocks on every livery.
        const bool AirbrakePanels1912 = true;
        const float AirbrakeDrag1912 = 0.5f, AirbrakeMaxAngle1912 = 55f, AirbrakeOpenSpeed1912 = 1.0f, AirbrakeMinEdgeOut1912 = 0.15f;
        static readonly string[] AirbrakeSides1912 = { "L", "R" };
        // 1.9.12 (user: naval liveries for both factions): "BDF Navy Hex" / "PALA Navy Splinter" (fd32_livery_bdf_navy / _pala_navy, baked by
        // build_textures_fd32.py --liveries-only). They are APPENDED after the four 1.9.11 entries (saved missions store the list index): indexes 0-3 keep
        // their 1.9.11 names, 4 = BDF Navy Hex, 5 = PALA Navy Splinter. false = the json's naval entries are ignored (list and textures = 1.9.11).
        // 1.9.13 (Discord report via the user: "when the plane rolls or pulls up at speed, the top wings shift at the break off points"): under local
        // simulation every AeroPart is its own Rigidbody joined by plain FixedJoints (Aircraft.SetComplexPhysics -> AeroPart.CreateRB / CreateJoints),
        // which PhysX solves with the project default of 6 position iterations. The left-over joint error of the light upper wing (32 kg centre
        // section between the root and two 62 kg panels carrying 20-30 g of lift each) shows as a one-sided hinge at the C / outer break and a sag
        // of the whole upper wing (offline PhysX benches, study\fd32_wingflex_1913*: 1.8-2.8 deg at 6-9 g). PartJoint.solverIterations != 6 sets
        // rb.solverIterations of the joint's OWNER (AeroPart.CreateJoints); stock precedent: A-19 (CAS1) wing3 joints 12, VTOLTrainer1 wing joints 12.
        // true = every joint OWNED by a wing_* part (wing_upper_C, wing_upper_L/R, wing_lower_L/R) carries WingSolverIterations1913; every other
        // joint, every break force / tensor / mass / centre of mass / aero value is unchanged. false = 1.9.12 (all joints 6).
        public const bool WingSolver1913 = true;
        // 1.9.13 in-game sweep (2026-11-16, study\ingame_1913\test, FD-32 only, one aircraft in the mission, 8.1-8.9 g at 122-159 m/s; the pass count
        // was set at runtime on the five wing bodies of the 20-pass test build, peak at the right upper break): 20 -> 0.41 deg kink / 0.58 deg / 18 mm
        // step, wide light seam in the chase shot; 40 -> 0.12-0.14 deg / 3-4 mm, thin light hairline; 60 -> under ~0.04 deg (the readout's floor) /
        // 1.2 mm, no light line on the hex livery but a thin light hairline still seen on the green livery (SeamCove1913 below); 100 -> 0.00 deg / 0 mm.
        // Frame time: no difference measurable with one aircraft (10 s windows, noise 0.1-0.7 ms); a mission with many FD-32 / Mk I was not measured.
        // Velocity iterations stay at the default 1 (not tried other than 1). Round 4 (final): 100.
        public const int WingSolverIterations1913 = 100;
        static bool WingSolverOwner1913(string part) => part.StartsWith("wing_");
        // 1.9.13 final (seam cosmetics, SeamCove1913.cs): (A) wing_upper_C/L/R_struct triangles at the break planes x = +-0.80 (end faces
        // within 1 mm of the plane; round 5: also the break-seam stringer stubs that cross the cut, 0.4-3.3 mm under the skin, and their end caps)
        // move into a last submesh drawn with FD32_cove; (B) round 5: two dark FD32_cove band halves per cut, all round the aerofoil, no collider,
        // no shadows: the inner half (20 mm inboard to the cut, 4.5 mm under the skin) is a child of wing_upper_C, the outer half (8 mm inboard of
        // the cut under the centre skin to 20 mm outboard, 5.0 mm under) a child of wing_upper_L/R, so each half leaves with its own part when a
        // panel is shot off (round 4 had one band under wing_upper_C: a 20 mm dark lip after a panel loss). No texture, atlas, paint mesh,
        // collider or physics change. false = 1.9.12 meshes.
        public const bool SeamCove1913 = true;
        const float SeamBreakX1913 = 0.80f;
        const bool NavalLiveries1912 = true;
        const float NavalGloss1912 = 0.0f;      // round 2: LiveryData.Glossiness of the two naval liveries = the stock naval liveries' value (the other four keep 0.2); the JSON carries it
        static bool IsNaval1912(string file) => file.EndsWith("_navy");
        static readonly string[] Liveries1911 = { "BDF Matte Gray", "BDF Temperate Camo", "PALA Desert Camo", "PALA Matte Black" };
        const float FabricImpactG = 25f, FabricImpactMult = 1.2f, MetalImpactG = 30f, MetalImpactMult = 1f;   // composite airframe: between the Mk I fabric and metal values
        const bool CooperPivotCentred = true; const float CooperMass = 9.1f, CooperYield = 7.3f;   // unused (Cooper off)
        // stock stores per pylon (docs/fd32_design.md 3; blender/fd32/check_fd32_model.py store boxes): AGR-24 x4 inner only (user decision),
        // IRM-S1 x2 outer only (0.33 m half width: inside the prop-disc radius on the inner pylon)
        static readonly string[] InnerStores = { "RocketPod1_single", "Rocket2_4Pod", "IRMS1_single", "AAM3_single", "ATGM1_quad", "bomb_glide1_single", "bomb_125_single" };
        static readonly string[] OuterStores = { "RocketPod1_single", "IRMS1_single", "IRMS1_double", "AAM3_single", "bomb_glide1_single", "bomb_125_single" };

        static readonly BindingFlags BF = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        // ------------------------------------------------------------------ part table
        enum Lift { Own, Wing, Stab, Fin, Hinge }
        class PartSpec
        {
            public string name, parent, mesh, template; public float mass, wingArea, dragArea, dihedral; public int airfoil; public Lift lift; public float joint;
            public PartSpec(string n, string p, string m, string t, float mass, float wa, float da, int af, Lift l, float j, float dih = 0f)
            { name = n; parent = p; mesh = m; template = t; this.mass = mass; wingArea = wa; dragArea = da; airfoil = af; lift = l; joint = j; dihedral = dih; }
        }

        // Masses (blender/fd32/fd32_spec.py MASSES): parts 1,496 kg (empty ~1,500 with the battery packs / motor / turbogenerator in fus_engine).
        // Areas: the Mk I 25.6 m^2 (lower panel 5.40 split 4.20 + flaperon 1.20); rudder 0.75 -> 0.86 (chord x 1.15). dragArea: composite skin,
        // faired struts, no radiator: the Mk I values x ~0.78 (fd32_fm DRAG 0.80 vs the Mk I 1.025).
        // round 6: FD32 / fus_engine 255 / 805 kg = the Blender MASSES table (were 315 / 745): Unity CoM 0.06 m forward, back to the v1
        // CoM-to-axle relation (v1 1.5.0: 0.48 m; 1.5.1 r3 with the stretch: 0.55 m)
        static List<PartSpec> Parts()
        {
            var l = new List<PartSpec>
            {
                new PartSpec("FD32",         null,          "fus_center",   "COIN:COIN",        255, 0.40f, 0.20f, 1, Lift.Own,  0),
                new PartSpec("fus_engine",   "FD32",        "fus_engine",   "COIN:fuselage",    EngineMass, 0.20f, 0.10f, 1, Lift.Own,  90000),
                new PartSpec("prop",         "fus_engine",  null,           "COIN:propHub",      45, 0.00f, 0.02f, 1, Lift.Own,  20000),
                new PartSpec("fus_rear",     "FD32",        "fus_rear",     "COIN:tailboom_L",   55, 0.30f, 0.04f, 1, Lift.Own,  50000),
                new PartSpec("wing_upper_C", "FD32",        "wing_upper_C", "COIN:wing1_L",      32, 2.00f, 0.025f, 0, Lift.Wing, 40000, 0f),
                new PartSpec("fin",          "fus_rear",    "fin",          "COIN:vstab1_L",      8, 0.75f, 0.008f, 1, Lift.Fin,  12000),
                new PartSpec("rudder",       "fin",         "rudder",       "COIN:rudder_L",      6, 0.86f, 0.004f, 1, Lift.Hinge, 8000),
            };
            foreach (var s in new[] { "L", "R" })
            {
                l.Add(new PartSpec("wing_upper_" + s, "wing_upper_C",   "wing_upper_" + s, "COIN:wing2_" + s,   62, 5.10f, 0.045f, 0, Lift.Wing,  50000, 1.0f));
                l.Add(new PartSpec("aileron_" + s,    "wing_upper_" + s, "aileron_" + s,   "COIN:aileron_" + s,  5, 1.30f, 0.004f, 2, Lift.Hinge, 15000));
                l.Add(new PartSpec("wing_lower_" + s, "FD32",           "wing_lower_" + s, "COIN:wing3_" + s,   WingLowerMass, Flaperons ? 4.20f : 5.40f, 0.09f, 0, Lift.Wing,  50000, 2.0f));
                if (Flaperons) l.Add(new PartSpec("flaperon_" + s, "wing_lower_" + s, "flaperon_" + s, "COIN:aileron_" + s, 5, 1.20f, 0.004f, 2, Lift.Hinge, 15000));
                l.Add(new PartSpec("stab_" + s,       "fus_rear",       "stab_" + s,       "COIN:hstab",        12, 0.85f, 0.008f, 1, Lift.Stab,  15000));
                l.Add(new PartSpec("elevator_" + s,   "stab_" + s,      "elevator_" + s,   "COIN:elevator",      5, 0.80f, 0.004f, 1, Lift.Hinge, 10000));
            }
            return l;
        }
        // biplane truss: the interplane struts tie each outer upper panel to its lower wing (extra joint, breaks with either wing)
        static readonly (string a, string b, float force)[] StrutJoints = { ("wing_upper_L", "wing_lower_L", 30000f), ("wing_upper_R", "wing_lower_R", 30000f) };

        // ------------------------------------------------------------------ state for one build
        static GameObject root;
        static readonly Dictionary<string, GameObject> tpl = new Dictionary<string, GameObject>();
        static readonly HashSet<Transform> tplRoots = new HashSet<Transform>();
        static readonly Dictionary<string, AeroPart> parts = new Dictionary<string, AeroPart>();
        static readonly Dictionary<string, GameObject> partGO = new Dictionary<string, GameObject>();
        static readonly Dictionary<string, Transform> liftNormals = new Dictionary<string, Transform>();
        static readonly List<Mesh> generatedMeshes = new List<Mesh>();
        static readonly Dictionary<string, Material> mats = new Dictionary<string, Material>();
        static readonly List<string> log = new List<string>();
        static readonly List<ParticleSystem> ourParticles = new List<ParticleSystem>();
        static Aircraft aircraft; static ControlsFilter controlsFilter; static WeaponManager weaponManager;
        static Newtonsoft.Json.Linq.JObject contract;

        static void L(string s) { log.Add(s); Debug.Log("[B25H] FD32 " + s); }

        // =================================================================== entry points
        public static void Build()
        {
            bool ok = BuildAssets();
            if (FamilyBuild.Combined) { FamilyBuild.Pack(); return; }
            Directory.CreateDirectory(@"C:\Users\User\nuclearoption-ref\build\fd32");
            Blueprinter.ModBuilder.Build(ModName, DisplayName, Version, @"C:\Users\User\nuclearoption-ref\build\fd32");
            L($"BUILD DONE check={(ok ? "PASS" : "FAIL")}");
        }

        public static bool BuildAssets()
        {
            bool ok = false;
            log.Clear(); tpl.Clear(); tplRoots.Clear(); parts.Clear(); partGO.Clear(); aircraft = null; controlsFilter = null; weaponManager = null;
            liftNormals.Clear(); generatedMeshes.Clear(); mats.Clear(); ourParticles.Clear(); crew.Clear();
            bombCentre = Vector3.zero; hookGO = null; hookMount = null; bombGO = null; mountGO = null; cooperMount = null; cooperInfo = null; cooperDef = null; ammoVickers = null; bombMesh = null; rackMesh = null;
            try
            {
                PrepareFolders();
                contract = LoadContract();
                var model = ImportModel();
                ImportTextures();
                LoadTemplates();
                BuildMaterials();
                root = (GameObject)Object.Instantiate(model);
                root.name = "FD32";
                AddAirbrakePanels1912();
                BuildPrefab();
                var prefab = SaveEverything();
                DestroyTemplates();
                Object.DestroyImmediate(root);
                AssetDatabase.SaveAssets();
                ok = RunCheck(prefab);
                L($"ASSETS DONE check={(ok ? "PASS" : "FAIL")} folder={Folder}");
            }
            finally { DestroyTemplates(); if (bombGO) Object.DestroyImmediate(bombGO); if (mountGO) Object.DestroyImmediate(mountGO); if (hookGO) Object.DestroyImmediate(hookGO); File.AppendAllText(LogPath, string.Join("\n", log) + "\n"); }
            return ok;
        }

        public static void BuildOnly() => BuildAssets();   // assets + check, no pack (fast iteration)

        public static void Check()
        {
            log.Clear();
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Folder + "/FD32.prefab");
            if (prefab == null) throw new Exception("prefab not built");
            RunCheck(prefab);
            File.WriteAllText(LogPath, string.Join("\n", log) + "\n");
        }

        // =================================================================== import
        static void PrepareFolders()
        {
            if (AssetDatabase.IsValidFolder(Folder)) AssetDatabase.DeleteAsset(Folder);
            foreach (var f in new[] { Folder, Folder + "/Textures", Folder + "/Materials", Folder + "/Generated", Folder + "/Liveries", SrcDir })
                Blueprinter.BlueprinterAssets.EnsureFolder(f);
            File.WriteAllText(LogPath, $"FD32 build {DateTime.Now:s}\n");
        }

        static Newtonsoft.Json.Linq.JObject LoadContract()
        {
            var p = Path.Combine(Path.GetDirectoryName(RepoModel), "fd32_contract.json");
            if (!File.Exists(p)) throw new Exception("no model contract " + p);
            return Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(p));
        }

        static GameObject ImportModel()
        {
            var dst = SrcDir + "/fd32.fbx";
            File.Copy(RepoModel, dst, true);
            AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
            var mi = (ModelImporter)AssetImporter.GetAtPath(dst);
            mi.isReadable = true; mi.importAnimation = false; mi.importCameras = false; mi.importLights = false;
            mi.globalScale = 1f; mi.useFileScale = true; mi.importBlendShapes = false;
            mi.SaveAndReimport();
            L($"model imported {dst} ({new FileInfo(RepoModel).Length} bytes)");
            airbrakeModel1912 = null; airbrakeJson1912 = null;
            if (AirbrakePanels1912)
            {   // 1.9.12 airbrake add-on: same exporter, same import settings as the main model (same frame, CG at the origin)
                var asrc = Path.Combine(Path.GetDirectoryName(RepoModel), "fd32_airbrake.fbx");
                var ajs = Path.Combine(Path.GetDirectoryName(RepoModel), "fd32_airbrake.json");
                if (!File.Exists(asrc) || !File.Exists(ajs)) throw new Exception("AirbrakePanels1912: " + asrc + " / .json missing (python blender/fd32/run_airbrake1912_fd32.py)");
                var adst = SrcDir + "/fd32_airbrake.fbx";
                File.Copy(asrc, adst, true);
                AssetDatabase.ImportAsset(adst, ImportAssetOptions.ForceUpdate);
                var ami = (ModelImporter)AssetImporter.GetAtPath(adst);
                ami.isReadable = true; ami.importAnimation = false; ami.importCameras = false; ami.importLights = false;
                ami.globalScale = 1f; ami.useFileScale = true; ami.importBlendShapes = false;
                ami.SaveAndReimport();
                airbrakeModel1912 = AssetDatabase.LoadAssetAtPath<GameObject>(adst);
                airbrakeJson1912 = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(ajs));
                L($"airbrake add-on imported {adst} ({new FileInfo(asrc).Length} bytes) + fd32_airbrake.json");
            }
            return AssetDatabase.LoadAssetAtPath<GameObject>(dst);
        }

        // ------------------------------------------------------------------ 1.9.12 airbrake panels
        static GameObject airbrakeModel1912;
        static Newtonsoft.Json.Linq.JObject airbrakeJson1912;
        static AeroPart OwningPart1912(Transform t) { for (var x = t; x != null; x = x.parent) { var ap = x.GetComponent<AeroPart>(); if (ap != null) return ap; } return null; }
        static Vector3 V3Json1912(Newtonsoft.Json.Linq.JToken a) => new Vector3((float)a[0], (float)a[1], (float)a[2]);

        /// how far the panel's free (aft) edge moves away from the aircraft centre line when the hinge is turned by `deg` about its local X
        /// exactly as the stock Airbrake does (localEulerAngles = base, then Rotate(deg, 0, 0) in Space.Self). The hinge is restored.
        static float AirbrakeOpenGain1912(Transform hinge, Transform centre, float deg)
        {
            var mf = hinge.GetComponentsInChildren<MeshFilter>(true).FirstOrDefault(m => m.name == hinge.name.Replace("_hinge", ""));
            if (mf == null || mf.sharedMesh == null) return float.NaN;
            // free edge = the mesh vertices farthest aft of the hinge line in the hinge frame (hinge-local -Z)
            var pts = mf.sharedMesh.vertices.Select(v => hinge.InverseTransformPoint(mf.transform.TransformPoint(v))).ToList();
            float zmin = pts.Min(p => p.z);
            var edge = pts.Where(p => p.z < zmin + 0.01f).ToList();
            var free = new Vector3(edge.Average(p => p.x), edge.Max(p => p.y), zmin);
            var keep = hinge.localRotation;
            float shut = Mathf.Abs(centre.InverseTransformPoint(hinge.TransformPoint(free)).x);
            hinge.Rotate(new Vector3(deg, 0f, 0f), Space.Self);
            float open = Mathf.Abs(centre.InverseTransformPoint(hinge.TransformPoint(free)).x);
            hinge.localRotation = keep;
            return open - shut;
        }

        /// Adds the panels of fd32_airbrake.fbx under the fus_rear model object, BEFORE BuildPrefab: the panels then get our meshes /
        /// materials with every other renderer, land in fus_rear's livery list (paint first) and stay out of its collider (own mesh only).
        /// The hinge frame comes from fd32_airbrake.json (the numbers the Blender checks and renders used): position, forward along the
        /// skin (Z), outward (Y); X = the vertical hinge line. The imported hinge empty must be at the same place (1 mm).
        static void AddAirbrakePanels1912()
        {
            if (!AirbrakePanels1912) return;
            var inst = (GameObject)Object.Instantiate(airbrakeModel1912);
            inst.transform.SetPositionAndRotation(root.transform.position, root.transform.rotation);
            var all = inst.GetComponentsInChildren<Transform>(true);
            Transform Get(string n) => all.FirstOrDefault(t => t.name == n) ?? throw new Exception("fd32_airbrake.fbx: no object " + n);
            var fusRear = Find("fus_rear");
            foreach (var s in AirbrakeSides1912)
            {
                var srcHinge = Get($"airbrake_{s}_hinge"); var panel = Get($"airbrake_{s}"); var tray = Get($"airbrake_tray_{s}");
                var js = airbrakeJson1912["sides"][s];
                var hl = V3Json1912(js["hinge_unity"]); var fwdL = V3Json1912(js["forward_unity"]); var outL = V3Json1912(js["outward_unity"]);
                var got = root.transform.InverseTransformPoint(srcHinge.position);
                if ((got - hl).magnitude > 0.001f) throw new Exception($"airbrake_{s}_hinge: FBX position {got.ToString("F4")} != fd32_airbrake.json {hl.ToString("F4")} (FBX and json from different runs?)");
                if (Mathf.Abs(Vector3.Dot(fwdL, outL)) > 1e-4f || outL.x * Mathf.Sign(hl.x) <= 0f) throw new Exception($"airbrake_{s}: json frame not orthogonal / not outward");
                var rot = root.transform.rotation * Quaternion.LookRotation(fwdL, outL);
                var hinge = NewGO($"airbrake_{s}_hinge", fusRear, root.transform.TransformPoint(hl), rot);
                panel.SetParent(hinge.transform, true);
                tray.SetParent(fusRear, true);
                float gain = AirbrakeOpenGain1912(hinge.transform, root.transform, AirbrakeMaxAngle1912);
                if (!(gain >= AirbrakeMinEdgeOut1912)) throw new Exception($"airbrake_{s}: +{AirbrakeMaxAngle1912} deg about the hinge X moves the free edge {gain:F3} m outward (>= {AirbrakeMinEdgeOut1912} expected): hinge frame wrong");
                var pmesh = panel.GetComponent<MeshFilter>().sharedMesh;
                L($"airbrake panel {s}: hinge {hl.ToString("F3")} (root frame), X {(Quaternion.Inverse(root.transform.rotation) * hinge.transform.right).ToString("F3")}, outward {outL.ToString("F3")}, " +
                  $"panel {pmesh.vertexCount} v / {pmesh.triangles.Length / 3} tris, free edge +{gain:F3} m outward at {AirbrakeMaxAngle1912} deg (Blender: +{(float)js["free_edge_gain_abs_x_m"]:F3})");
            }
            Object.DestroyImmediate(inst);
        }

        /// one stock Airbrake on the root: transforms = the two hinges, drag on the root part. Field set as on the MSB-17 (msb_root.cs, in
        /// game since 1.9.2) plus the transforms and the angle.
        static void AirbrakeComponent1912()
        {
            if (!AirbrakePanels1912) return;
            var hinges = AirbrakeSides1912.Select(s => Find($"airbrake_{s}_hinge")).ToArray();
            var ab = root.AddComponent<global::Airbrake>();
            S(ab, "transforms", hinges); S(ab, "dragAmount", AirbrakeDrag1912); S(ab, "maxAngle", AirbrakeMaxAngle1912); S(ab, "openSpeed", AirbrakeOpenSpeed1912);
            S(ab, "part", parts["FD32"]); S(ab, "airbrakeSound", null); S(ab, "constraints", new UnityEngine.Animations.AimConstraint[0]);
            S(ab, "volumeMultiplier", 0f); S(ab, "aircraft", aircraft);
            L($"airbrake: stock Airbrake on the root, {hinges.Length} hinges, dragAmount {AirbrakeDrag1912} (rho V^2: {AirbrakeDrag1912 * 1.225f * 80f * 80f / 1000f:F1} kN at 80 m/s SL), maxAngle {AirbrakeMaxAngle1912}, opens at throttle 0 in {1f / AirbrakeOpenSpeed1912:F1} s");
        }

        static readonly string[] SkinMaps = { "b", "n", "m", "ao", "dmg_b", "dmg_n" };
        // tiling materials (blender/fd32/textures/build_textures_fd32.py tiles(): fal composite / carbon / cockpit tiles + the Mk I fal tiles)
        static readonly string[] TileMats = { "interior", "tube", "alu", "ck_grey", "rubber", "gunmetal", "structure", "fabric_in", "exhaust", "metal_dark" };
        // fal 3D props with their own baked textures (fd32_pr_<key>_b / _n; blender/fd32/textures/make_art_fd32.py)
        static readonly string[] PropMats = { "pr_prop4", "pr_sensor", "pr_wheel", "pr_tailwheel", "pr_hook", "pr_hook2", "pr_throttle" };
        // modern cockpit tiles (fal ck_modern / ck_mat + the Mk I crinkle / rubber): name -> (tiling, metallic, smoothness)
        static readonly Dictionary<string, (float scale, float met, float sm)> CockpitTiles = new Dictionary<string, (float, float, float)> {
            { "ck_modern", (4f, 0.10f, 0.30f) }, { "ck_mat", (6f, 0f, 0.15f) }, { "ck_crinkle", (8f, 0.10f, 0.30f) }, { "ck_lining", (4f, 0.10f, 0.25f) }, { "ck_rubber", (8f, 0f, 0.25f) } };
        static readonly List<(string file, string label, string faction, bool both)> Liveries = new List<(string, string, string, bool)>();
        static readonly Dictionary<string, Texture2D> tex = new Dictionary<string, Texture2D>();

        static void LoadLiveryTable()
        {
            Liveries.Clear();
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(Path.Combine(RepoTextures, "fd32_liveries.json")));
            foreach (var kv in jo)
            {
                var e = (Newtonsoft.Json.Linq.JObject)kv.Value;
                var file = Path.GetFileNameWithoutExtension((string)e["texture"]);
                if (!NavalLiveries1912 && IsNaval1912(file)) { L($"livery table: {file} skipped (NavalLiveries1912 off)"); continue; }
                Liveries.Add((file, (string)e["name"], ((string)e["faction"]).ToUpperInvariant().Contains("PALA") ? "PALA" : "BDF", e["both"] != null && (bool)e["both"]));
                L($"livery table: {file} '{(string)e["name"]}' ({(string)e["faction"]}{(e["both"] != null && (bool)e["both"] ? ", both factions" : " only")})");
            }
        }

        static void ImportTextures()
        {
            tex.Clear();
            LoadLiveryTable();
            var want = SkinMaps.Select(m => "fd32_skin_" + m).Concat(Liveries.Select(l => l.file))
                .Concat(TileMats.SelectMany(t => new[] { $"fd32_tile_{t}_b", $"fd32_tile_{t}_n" }))
                .Concat(PropMats.SelectMany(t => new[] { $"fd32_{t}_b", $"fd32_{t}_n" })).ToList();
            if (CockpitV2) want.AddRange(CockpitTiles.Keys.SelectMany(t => new[] { $"fd32_tile_{t}_b", $"fd32_tile_{t}_n" }));
            foreach (var n in want)
            {
                var src = Path.Combine(RepoTextures, n + ".png");
                if (!File.Exists(src)) throw new Exception("missing texture " + src + " (run blender/fd32/run_fd32.py)");
                var dst = $"{Folder}/Textures/{n}.png";
                File.Copy(src, dst, true);
                AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
                var ti = (TextureImporter)AssetImporter.GetAtPath(dst);
                bool normal = n.EndsWith("_n");
                bool linear = n.EndsWith("_m") || n.EndsWith("_ao") || normal;
                ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                ti.sRGBTexture = !linear; ti.mipmapEnabled = true; ti.maxTextureSize = 2048;
                ti.textureCompression = TextureImporterCompression.Compressed;
                ti.SaveAndReimport();
                tex[n] = AssetDatabase.LoadAssetAtPath<Texture2D>(dst);
            }
            L($"textures: {tex.Count} from {RepoTextures}");
        }

        // =================================================================== stock templates (starting values only)
        static void LoadTemplates()
        {
            foreach (var n in new[] { "COIN", "CAS1", "gun_12.7mm_internal", "TailHook_Multirole1", "Fighter1", "VTOLTrainer1" })
            {
                var p = AssetDatabase.LoadAssetAtPath<GameObject>($"{DNS}/GameObject/{n}_PLACEHOLDER.prefab");
                if (p == null) throw new Exception("missing placeholder " + n);
                var inst = (GameObject)Object.Instantiate(p);
                inst.name = "TEMPLATE_" + n;
                inst.SetActive(false);
                tpl[n] = inst; tplRoots.Add(inst.transform);
            }
        }

        // =================================================================== materials
        static void BuildMaterials()
        {
            var skin = Asset<Shader>("Shader/Shader Graphs_AircraftSkin_PLACEHOLDER.shader");
            var paint = new Material(skin) { name = "FD32_paint" };
            paint.SetTexture("_Basecolor", tex["fd32_skin_b"]);
            paint.SetTexture("_Normal", tex["fd32_skin_n"]);
            paint.SetTexture("_Metallic", tex["fd32_skin_m"]);
            paint.SetTexture("_AO", tex["fd32_skin_ao"]);
            paint.SetTexture("_BasecolorDmg", tex["fd32_skin_dmg_b"]);
            paint.SetTexture("_NormalDmg", tex["fd32_skin_dmg_n"]);
            paint.SetTexture("_Livery", tex["fd32_skin_b"]);
            paint.SetFloat("_Glossiness", 0.2f);
            paint.SetFloat("_HitPoints", 100f);
            Save(paint, "paint");
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            if (lit == null) throw new Exception("URP Lit shader not found");
            foreach (var t in TileMats)
            {
                float met = t == "alu" ? 0.85f : t == "gunmetal" ? 0.8f : t == "tube" ? 0.3f : t == "structure" ? 0.3f : t == "metal_dark" ? 0.6f : t == "exhaust" ? 0.5f : 0.05f,
                      sm = t == "alu" ? 0.6f : t == "gunmetal" ? 0.55f : t == "structure" ? 0.55f : t == "tube" ? 0.55f : t == "metal_dark" ? 0.45f : t == "exhaust" ? 0.3f : t == "fabric_in" ? 0.2f : 0.3f;
                Save(Tiled(LitMat(lit, "FD32_" + t, Color.white, met, sm), $"fd32_tile_{t}_b", $"fd32_tile_{t}_n"), t);
            }
            if (CockpitV2)
            {
                foreach (var kv in CockpitTiles)
                {
                    var tm = Tiled(LitMat(lit, "FD32_" + kv.Key, Color.white, kv.Value.met, kv.Value.sm), $"fd32_tile_{kv.Key}_b", $"fd32_tile_{kv.Key}_n");
                    tm.SetTextureScale("_BaseMap", new Vector2(kv.Value.scale, kv.Value.scale)); tm.SetTextureScale("_MainTex", new Vector2(kv.Value.scale, kv.Value.scale));
                    Save(tm, kv.Key);
                }
            }
            Save(LitMat(lit, "FD32_cove", new Color(0.045f, 0.045f, 0.048f), 0f, 0.1f), "cove");   // 1.3.1: hinge coves, control-surface fronts (dark matte)
            Save(LitMat(lit, "FD32_tank", new Color(0.55f, 0.55f, 0.55f), 0.3f, 0.4f), "tank");   // 2026-11-22: fuel tank metal (the r8o tank metal; was the light structure look)
            foreach (var pm in PropMats)
                Save(Tiled(LitMat(lit, "FD32_" + pm, Color.white, pm == "pr_sensor" ? 0.4f : pm == "pr_wheel" || pm == "pr_tailwheel" ? 0.1f : 0.25f, 0.45f), $"fd32_{pm}_b", $"fd32_{pm}_n"), pm);
            Save(LitMat(lit, "FD32_radiator", new Color(0.10f, 0.10f, 0.09f), 0.6f, 0.4f), "radiator");
            Save(LitMat(lit, "FD32_spinner", new Color(0.75f, 0.76f, 0.78f), 0.85f, 0.7f), "spinner");
            Save(LitMat(lit, "FD32_hookyellow", new Color(0.80f, 0.62f, 0.08f), 0.1f, 0.5f), "hookyellow");
            Save(LitMat(lit, "FD32_brass", new Color(0.72f, 0.52f, 0.20f), 0.9f, 0.7f), "brass");
            Save(LitMat(lit, "FD32_red", new Color(0.55f, 0.06f, 0.04f), 0.1f, 0.5f), "red");
            Save(LitMat(lit, "FD32_ck_black", new Color(0.025f, 0.025f, 0.028f), 0.2f, 0.45f), "ck_black");
            Save(LitMat(lit, "FD32_bomb", new Color(0.20f, 0.22f, 0.14f), 0.3f, 0.5f), "bomb");
            Save(LitMat(lit, "FD32_bombband", new Color(0.80f, 0.62f, 0.08f), 0.1f, 0.5f), "bombband");
            Save(LitMat(lit, "FD32_navlight", new Color(0.3f, 0.3f, 0.3f), 0f, 0.8f), "navlight");
            Save(LitMat(lit, "FD32_navred", new Color(0.55f, 0.03f, 0.02f), 0f, 0.9f), "navred");       // 1.4.0 period lamp glass, not emissive
            Save(LitMat(lit, "FD32_navgreen", new Color(0.03f, 0.42f, 0.10f), 0f, 0.9f), "navgreen");
            Save(LitMat(lit, "FD32_screen", Color.black, 0f, 0.5f), "screen");
            mats["light_off"] = Asset<Material>("Material/light_green_off_PLACEHOLDER.mat");   // round 3: gear-down strips unlit (GA-25X / AB-4 stock material)
            mats["tacscreen"] = Asset<Material>("Material/tacScreenDisplay_PLACEHOLDER.mat");  // round 3: the 4-island stock tac-screen mesh
            var glass = new Material(Asset<Material>("Material/COIN_glass_PLACEHOLDER.mat")) { name = "FD32_glass" };
            if (GlassGloss187) glass.SetFloat("_Smoothness", GlassSmooth187);   // 1.8.7: no grazing ground-reflection line on the curved glass
            Save(glass, "glass");
            var glassInt = new Material(Asset<Material>("Material/COIN_glass_int_PLACEHOLDER.mat")) { name = "FD32_glass_int" };
            Save(glassInt, "glass_int");
            // round 7: faint clear cockpit glass (seen from inside on the reversed-winding copies): the stock CI-22 prop-disc material is URP Lit
            // transparent (alpha blend, no depth write); our copy has no texture, a pale tint at alpha 0.06 and high smoothness (a faint sheen)
            var gck = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "FD32_glass_ck" };
            gck.SetTexture("_BaseMap", null); gck.SetTexture("_MainTex", null); gck.SetTexture("_OcclusionMap", null); gck.DisableKeyword("_OCCLUSIONMAP");
            gck.SetColor("_BaseColor", new Color(0.86f, 0.92f, 0.97f, 0.06f)); gck.SetColor("_Color", new Color(0.86f, 0.92f, 0.97f, 0.06f));
            gck.SetFloat("_Smoothness", 0.95f); gck.SetFloat("_Metallic", 0f); gck.SetFloat("_Cull", 2f);
            Save(gck, "glass_ck");
            // prop blur: our 2-blade atlas (texture build), stock CI-22 disc material settings, alpha in the texture (B-25H 1.1.0 fix)
            var disc = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "FD32_propdisc" };
            var bp = $"{Folder}/Textures/fd32_propblur.png";
            File.Copy(Path.Combine(RepoTextures, "fd32_propblur.png"), bp, true); AssetDatabase.ImportAsset(bp, ImportAssetOptions.ForceUpdate);
            var bti = (TextureImporter)AssetImporter.GetAtPath(bp); bti.alphaIsTransparency = true; bti.wrapMode = TextureWrapMode.Clamp; bti.SaveAndReimport();
            var blur = AssetDatabase.LoadAssetAtPath<Texture2D>(bp);
            disc.SetTexture("_BaseMap", blur); disc.SetTexture("_MainTex", blur);
            disc.SetTexture("_OcclusionMap", null); disc.DisableKeyword("_OCCLUSIONMAP");
            disc.SetColor("_BaseColor", Color.white); disc.SetColor("_Color", Color.white);
            disc.SetFloat("_Smoothness", 0.63f); disc.SetFloat("_Cull", 0f);
            Save(disc, "propdisc");
            if (StockStructure) mats["structure"] = B25HTools.StockStructure.LookMaterial(Asset<Material>("Material/aircraft_structure_PLACEHOLDER.mat"), Folder, "FD32");
            L("materials: " + string.Join(", ", mats.Keys));
        }

        // =================================================================== the prefab
        static void BuildPrefab()
        {
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                var mr = mf.GetComponent<MeshRenderer>();
                var names = mr.sharedMaterials.Select(m => m ? m.name.Replace(" (Instance)", "") : "null").ToArray();
                mf.sharedMesh = CopyMesh(mf.sharedMesh, mf.name, names, out var ordered);
                mr.sharedMaterials = ordered.Select(n => mats.TryGetValue(n, out var m) ? m : throw new Exception($"no material '{n}' for {mf.name}")).ToArray();
            }
            foreach (var t in root.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = 14;
            GameObjectUtility.RemoveMonoBehavioursWithMissingScript(root);
            root.AddComponent<Mirage.NetworkIdentity>();
            var rb = root.AddComponent<Rigidbody>();
            EditorUtility.CopySerialized(tpl["COIN"].GetComponent<Rigidbody>(), rb);
            CloneComp(tpl["COIN"].GetComponent<Aircraft>(), root);

            var specs = Parts();
            foreach (var s in specs) MakePartObject(s);
            foreach (var s in specs) MakeAeroPart(s);
            AddJoints(specs);

            var cockpitGO = parts["FD32"].gameObject;
            controlsFilter = CloneComp(TplComp<ControlsFilter>("COIN:cockpit_F"), cockpitGO);
            weaponManager = CloneComp(TplComp<WeaponManager>("COIN:cockpit_F"), cockpitGO);
            CloneComp(TplComp<AutopilotPlane>("COIN:cockpit_F"), cockpitGO);
            Remap(aircraft); Remap(controlsFilter); Remap(weaponManager);

            ControlSurfaces();
            if (Flaperons) FlaperonDroop();
            var gears = Gear();
            Engine();
            Weapons();
            Cockpit();
            RootSystems(gears);
            FlyByWire(gears[0]);

            if (SeamCove1913) ApplySeamCove1913();   // 1.9.13 final: last, so the bands are the last children of wing_upper_C / L / R (no sibling index moves)
            int dropped = 0;
            foreach (var c in root.GetComponentsInChildren<Component>(true))
            {
                if (c == null) continue;
                var so = new SerializedObject(c); var it = so.GetIterator(); bool enter = true, changed = false;
                while (it.Next(enter))
                {
                    enter = true;
                    if (it.propertyType == SerializedPropertyType.ObjectReference && it.objectReferenceValue != null && IsTemplateObject(it.objectReferenceValue))
                    { L($"WARN dropped stale stock ref {c.GetType().Name}@{c.name}.{it.propertyPath} -> {it.objectReferenceValue.name}"); it.objectReferenceValue = null; dropped++; changed = true; }
                }
                if (changed) so.ApplyModifiedPropertiesWithoutUndo();
            }
            L($"final sweep dropped {dropped} stock refs");
        }

        // 1.9.13 final: dark end faces + dark backing band at the upper-wing break lines (SeamCove1913.cs)
        static void ApplySeamCove1913()
        {
            var sl = new List<string>();
            B25HTools.SeamCove1913.Apply(root.transform, Find, mats["cove"], generatedMeshes, sl, SeamBreakX1913);
            foreach (var s in sl) L(s);
        }

        // ------------------------------------------------------------------ parts
        static void MakePartObject(PartSpec s)
        {
            GameObject go;
            if (s.name == "FD32") go = root;
            else if (s.name == "prop") go = Find("prop").gameObject;
            else if (s.lift == Lift.Hinge)
            {
                var mesh = Find(s.mesh);
                mesh.name = s.name + "_visible";
                Quaternion rot = s.name == "rudder" ? Quaternion.LookRotation(Vector3.forward, Vector3.left) : mesh.rotation;
                go = NewGO(s.name, mesh.parent, mesh.position, rot);
                var hinge = NewGO(s.name + "_hinge", go.transform, mesh.position, rot);
                mesh.SetParent(hinge.transform, true);
                liftNormals[s.name] = hinge.transform;
            }
            else go = Find(s.mesh).gameObject;
            go.name = s.name;
            if (s.parent != null) go.transform.SetParent(partGO[s.parent].transform, true);
            parts[s.name] = null;
            partGO[s.name] = go;
        }

        static void MakeAeroPart(PartSpec s)
        {
            var go = partGO[s.name];
            var ap = CloneComp(TplComp<AeroPart>(s.template), go);
            parts[s.name] = ap;
            S(ap, "parentUnit", aircraft);
            ap.mass = s.mass;
            S(ap, "criticalPart", false);
            S(ap, "wingArea", s.wingArea);
            ap.dragArea = s.dragArea;
            S(ap, "airfoil", s.airfoil);
            S(ap, "disintegrateObjects", new GameObject[0]);
            S(ap, "centerOfMass", null);
            S(ap, "connectedAnchor", null);
            S(ap, "joints", new PartJoint[0]);
            if (CrashImpactDamage && s.name != "prop")
            {
                // a new ImpactDamage per part (the cloned field would share the template's instance)
                var idf = Fld(ap.GetType(), "impactDamage");
                var id = System.Activator.CreateInstance(idf.FieldType);
                bool metal = s.name == "FD32" || s.name == "fus_engine";   // battery box / motor bay: the stiff structure
                S(id, "threshold", metal ? MetalImpactG : FabricImpactG); S(id, "multiplier", metal ? MetalImpactMult : FabricImpactMult);
                if (LiftSpawnFix1911 && s.name == "rudder") { S(id, "threshold", 0f); S(id, "multiplier", 0f); }   // 1.9.11: as every stock rudder
                idf.SetValue(ap, id);
            }
            MeshFilter own = s.name == "FD32" ? Find("fus_center").GetComponent<MeshFilter>()
                : s.lift == Lift.Hinge ? Find(s.name + "_visible").GetComponent<MeshFilter>()
                : s.mesh != null ? go.GetComponent<MeshFilter>() : null;
            if (own != null)
            {
                var mc = go.AddComponent<MeshCollider>();
                mc.sharedMesh = BakeCollider(go.transform, s.name + "_col", own);
                var hull = s.name == "FD32" && RootColliderHull182 ? contract["collider_fus_center"] : null;
                if (hull != null)
                {
                    // 1.8.3: root collider = the 1.8.2 fus_center skin hull (contract points are root-relative, Unity frame) - same CoM / inertia
                    var hv = ((Newtonsoft.Json.Linq.JArray)hull["verts"]).Select(a => go.transform.InverseTransformPoint(root.transform.TransformPoint(new Vector3((float)a[0], (float)a[1], (float)a[2])))).ToArray();
                    var ht = ((Newtonsoft.Json.Linq.JArray)hull["tris"]).SelectMany(a => new[] { (int)a[0], (int)a[1], (int)a[2] }).ToArray();
                    var hm = new Mesh { name = s.name + "_col182" }; hm.SetVertices(hv); hm.SetTriangles(ht, 0); hm.RecalculateBounds();
                    generatedMeshes.Add(hm);
                    mc.sharedMesh = hm;
                    L($"1.8.3 FD32 root collider from the 1.8.2 fus_center hull: {hv.Length} verts, bounds {hm.bounds}");
                }
                mc.convex = true;
            }
            Transform ln = null;
            if (s.lift == Lift.Hinge) ln = liftNormals[s.name];
            else if (s.lift == Lift.Wing || s.lift == Lift.Stab || s.lift == Lift.Fin)
            {
                Quaternion q;
                if (s.lift == Lift.Fin) q = Quaternion.LookRotation(Vector3.forward, Vector3.left);
                else
                {
                    float side = s.name.EndsWith("_L") ? -1f : 1f;
                    var x = new Vector3(side, Mathf.Tan(s.dihedral * Mathf.Deg2Rad), 0f).normalized; if (x.x < 0) x = -x;
                    var y = Vector3.Cross(Vector3.forward, x).normalized;
                    q = Quaternion.LookRotation(Vector3.forward, y);
                    float inc = s.lift == Lift.Wing ? WingIncidence : StabIncidence;
                    q = Quaternion.AngleAxis(-inc, q * Vector3.right) * q;
                }
                ln = NewGO(s.name + "_liftNormal", go.transform, go.transform.position, q).transform;
                liftNormals[s.name] = ln;
            }
            S(ap, "liftNormal", ln);
            Vector3 col = Vector3.zero;
            if (s.wingArea > 0.5f && own != null && ln != null)
            {
                var b = own.sharedMesh.bounds;
                var lePt = own.transform.TransformPoint(new Vector3(b.center.x, b.center.y, b.max.z));
                var tePt = own.transform.TransformPoint(new Vector3(b.center.x, b.center.y, b.min.z));
                var qc = Vector3.Lerp(lePt, tePt, 0.25f);
                var centroid = go.transform.TransformPoint(go.GetComponent<MeshCollider>().sharedMesh.bounds.center);
                col = ln.InverseTransformVector(qc - centroid);
            }
            S(ap, "centerOfLift", col);
            L($"part {s.name}: mass {s.mass} wingArea {s.wingArea} drag {s.dragArea} airfoil {s.airfoil} lift {(ln ? ln.name : "own")} col {col.ToString("F2")}");
            var rends = PartRenderers(go).Where(r => r.sharedMaterials.Length > 0 && r.sharedMaterials[0] == mats["paint"]).Cast<Renderer>().ToList();
            S(G(ap, "damageMaterial"), "renderers", rends);
        }

        static void AddJoints(List<PartSpec> specs)
        {
            var bySpec = specs.ToDictionary(s => s.name);
            var joined = new HashSet<(string, string)>();
            var jl = specs.ToDictionary(s => s.name, s => new List<PartJoint>());
            var breakSnd = TplComp<AeroPart>("CAS1:wing2_L").Joints[0].breakSound;
            PartJoint J(string owner, string to, string tensor, float force) => new PartJoint { connectedPart = parts[to], tensor = tensor == null ? null : parts[tensor],
                solverIterations = WingSolver1913 && WingSolverOwner1913(owner) ? WingSolverIterations1913 : 6, breakForce = force, breakTorque = force, breakSound = breakSnd };
            void Add(string a, string b, string tensor, float f) { jl[a].Add(J(a, b, tensor, f)); joined.Add((a, b)); joined.Add((b, a)); }
            foreach (var s in specs)
            {
                if (s.parent == null) continue;
                Add(s.name, s.parent, null, s.joint);
                var gp = bySpec[s.parent].parent;
                if (gp != null) Add(s.name, gp, s.parent, s.joint * 0.5f);
            }
            foreach (var (a, b, f) in StrutJoints) { Add(a, b, b, f); L($"strut joint {a} -> {b} ({f})"); }
            var names = specs.Select(s => s.name).ToList();
            int extra = 0;
            for (int i = 0; i < names.Count; i++)
                for (int j = i + 1; j < names.Count; j++)
                {
                    var a = names[i]; var b = names[j];
                    if (joined.Contains((a, b))) continue;
                    var ca = parts[a].GetComponent<MeshCollider>(); var cb = parts[b].GetComponent<MeshCollider>();
                    if (ca == null || cb == null) continue;
                    var ba = WorldBounds(ca); var bb = WorldBounds(cb);
                    ba.Expand(-0.02f); bb.Expand(-0.02f);
                    if (!ba.Intersects(bb)) continue;
                    int da = Depth(bySpec, a), db = Depth(bySpec, b);
                    var owner = da >= db ? a : b; var other = owner == a ? b : a;
                    Add(owner, other, other == "FD32" ? bySpec[owner].parent : other, Mathf.Min(bySpec[a].joint == 0 ? 1e6f : bySpec[a].joint, bySpec[b].joint == 0 ? 1e6f : bySpec[b].joint) * 0.3f);
                    extra++; L($"overlap joint {owner} -> {other}");
                }
            foreach (var s in specs) S(parts[s.name], "joints", jl[s.name].ToArray());
            L($"joints: {jl.Values.Sum(x => x.Count)} total, {extra} anti-overlap");
        }
        static int Depth(Dictionary<string, PartSpec> by, string n) { int d = 0; while (by[n].parent != null) { n = by[n].parent; d++; } return d; }

        // ------------------------------------------------------------------ control surfaces (B-25H sign conventions: hinge local X ~ +X, rudder X = up)
        static void ControlSurfaces()
        {
            foreach (var side in new[] { "L", "R" })
            {
                float sgn = side == "L" ? -1f : 1f;
                CS("aileron_" + side, "COIN:aileron_" + side, 0, 18f * sgn, 0, 70f);
                if (Flaperons) CS("flaperon_" + side, "COIN:aileron_" + side, 0, 18f * sgn, 0, 70f);   // same hinge-axis convention as the upper ailerons
                CS("elevator_" + side, "CAS1:elevator_" + side, -26f, 0, 0, 60f);
            }
            CS("rudder", "CAS1:rudder_L", 0, 0, -25f, 60f);
        }

        // Flaperons on all four panels (docs/fd32_design.md 1): NOT ControlSurface.flap (ControlSurfaceJob_Math: a flap follows gearState and
        // the fixed gear is always LockedExtended). Roll = the ControlSurface above; flap = a HighLiftDevice on each wing panel (stock CAS1 /
        // Multirole1 pattern, GA-25X StolFlaps): +FlapAreaPerPanel below FlapSpeedDeployed, none above FlapSpeedRetracted; its moving part is a
        // 'droop' pivot inserted ABOVE the control surface's driven frame (the lift frame the ControlSurface turns), so droop and roll add:
        // DROOP_DEG trailing edge down with the slotted-flap shift (blender/fd32 check: clear of the cove at droop + full roll).
        static void FlaperonDroop()
        {
            // round 3 (user: real flaps once the gear retracts): the stock flap pattern - a ControlSurface in flap mode (ControlSurfaceJob_Math:
            // currentPitch runs to -pitchRange while the gear is Extending / LockedExtended, back to 0 when it is up) on a 'droop' pivot that sits
            // DROOP_PIVOT_BELOW under the hinge line ABOVE the roll surface's driven frame, so flap droop and roll add (and the drooped surface also
            // moves ~3 cm aft: clear of the cove, blender check). The pivot's local X is oriented so a NEGATIVE rotation is trailing edge down.
            var dr = contract["droop"];
            float below = (float)dr["pivot_below"];
            var tplCS = TplComp<ControlSurface>("COIN:aileron_L");
            foreach (var cs in new[] { "aileron_L", "aileron_R", "flaperon_L", "flaperon_R" })
            {
                float deg = cs.StartsWith("aileron") ? (float)dr["deg_upper"] : (float)dr["deg"];
                var hinge = liftNormals[cs];
                var mesh = hinge.GetComponentsInChildren<MeshFilter>(true).First(m => m.name == cs + "_visible");
                var axis = hinge.right;
                var verts = mesh.sharedMesh.vertices.Select(v => mesh.transform.TransformPoint(v)).ToList();
                var te = verts.OrderByDescending(v => Vector3.ProjectOnPlane(v - hinge.position, axis).sqrMagnitude).First();
                var arm = Vector3.ProjectOnPlane(te - hinge.position, axis);
                var up = Vector3.Cross(axis, arm.normalized).normalized; if (up.y < 0) up = -up;
                var rot = hinge.rotation;
                if ((Quaternion.AngleAxis(-5f, axis) * arm).y > arm.y) rot = rot * Quaternion.AngleAxis(180f, Vector3.up);   // -X rotation must lower the TE
                var droop = NewGO(cs + "_droop", hinge.parent, hinge.position - up * below, rot);
                hinge.SetParent(droop.transform, true);
                var c = droop.AddComponent<ControlSurface>(); EditorUtility.CopySerialized(tplCS, c); Remap(c);
                S(c, "pitchRange", deg); S(c, "rollRange", 0f); S(c, "yawRange", 0f); S(c, "brakeRange", 0f);
                S(c, "attachedSurface", parts[cs]); S(c, "visibleMesh", droop); S(c, "flap", true); S(c, "servoSpeed", 12f);
                S(c, "splitDrag", 0f); S(c, "maxSplit", 0f); S(c, "yawSplitFactor", 0f); S(c, "splitUpper", null); S(c, "splitLower", null); S(c, "splitSound", null);
                L($"flap {cs}: ControlSurface flap mode, pitchRange {deg} on {droop.name} ({below} m under the hinge), follows the gear");
            }
        }

        static void CS(string part, string template, float pitch, float roll, float yaw, float servo)
        {
            var c = CloneComp(TplComp<ControlSurface>(template), parts[part].gameObject);
            S(c, "pitchRange", pitch); S(c, "rollRange", roll); S(c, "yawRange", yaw); S(c, "brakeRange", 0f);
            S(c, "attachedSurface", parts[part]);
            S(c, "visibleMesh", liftNormals[part].gameObject);
            S(c, "flap", false); S(c, "servoSpeed", servo);
            S(c, "splitDrag", 0f); S(c, "maxSplit", 0f); S(c, "yawSplitFactor", 0f);
            S(c, "splitUpper", null); S(c, "splitLower", null); S(c, "splitSound", null);
        }

        // ------------------------------------------------------------------ landing gear: two braked mains (fixed) + steerable tailwheel
        class GearSpec { public string strut, wheel, part; public float fold, yaw, travel, k, c, maxComp, mass, drag, retractedDrag; public bool steer, brake, fwd; public float diff; public Vector3? axis, stowed; }

        // 1.4.2: the gear broke on every landing. LandingGear.FixedUpdate breaks a leg when compressionDistance > maxCompression; ours was soft
        // (120 kN/m, damping ratio 0.45) and broke at 0.30 of 0.575 m travel (52 %): ~5 m/s sink bottomed it. Stock COIN: 200-250 kN/m,
        // 20 kN s/m, break at 72-83 % of travel. Now main 200 kN/m, 20 kN s/m (damping ratio ~0.8), break at 0.50 m (87 %): peak compression
        // ~0.18 m at 5 m/s sink, 0.26 at 8 m/s; a crash (> ~15 m/s) still breaks it. Tail 120 kN/m, 9 kN s/m, break 0.27 of 0.31 m.
        const float GearMainK = 200000f, GearMainC = WingGearStiffBody ? 13000f : 20000f, GearMainMaxComp = 0.50f;   // 1.8.2: C 20000 -> 13000 (see WingGearStiffBody)
        const float GearTailK = 120000f, GearTailC = 9000f, GearTailMaxComp = 0.27f;

        // round 3: LandingGear.Awake stores attachedPart.dragArea as its (non-serialized) retractedDrag and writes extendedDrag while the gear
        // is down (LandingGear.il, OnSetGear). The part dragArea is the clean (gear-up) value fd32_fm models; the gear adds its drag when down.
        // Both mains write the same part, so MainGearDrag is the pair.
        const float MainGearDrag = 0.08f, TailGearDrag = 0.01f;

        static List<LandingGear> Gear()
        {
            // round 3 (user: weapons safety + real flaps need a retract state): the main legs fold forward about their roots (the wheel tucks up
            // beside the lower cowl), the tailwheel folds aft-up into the tail cone (contract "retract"; blender check: clear of wings, wires, prop)
            var rt = contract["retract"];
            var list = new List<LandingGear>();
            foreach (var s in new[] { "L", "R" })
                list.Add(MakeGear(new GearSpec { axis = TiltedGearAxis && rt["main_axis_" + s] != null ? J3(rt["main_axis_" + s]) : (Vector3?)null, stowed = rt["main_stowed_wheel_" + s] != null ? J3(rt["main_stowed_wheel_" + s]) : (Vector3?)null,
                    strut = $"gear_main_{s}_strut", wheel = $"gear_main_{s}_wheel", part = GearOnLowerWing ? "wing_lower_" + s : "FD32", fold = (float)rt["main_fold_deg"], yaw = (float)rt["main_fold_yaw_deg"], fwd = !(rt["main_fold_aft"] != null && (bool)rt["main_fold_aft"]), retractedDrag = parts[GearOnLowerWing ? "wing_lower_" + s : "FD32"].dragArea, travel = 0.355f + 0.22f, k = GearMainK, c = GearMainC * GearDampingScale183D, maxComp = GearMainMaxComp,
                    mass = 25f, drag = GearOnLowerWing ? parts["wing_lower_" + s].dragArea + 0.5f * MainGearDrag : parts["FD32"].dragArea + MainGearDrag, steer = false, brake = true, diff = s == "L" ? -1f : 1f }, "CAS1:gear_" + s + "_sprung", "COIN:wheel_" + s));
            // round 6: FIXED tailwheel (user: the retracting tailwheel made the tail drag): foldDegrees 0.5 (0 divides by zero in MoveGear, the
            // Mk I fixed-gear value) and extendedDrag = the part's own dragArea, so a "retracted" state changes neither the look nor the drag
            bool tailFixed = FixedTailwheel && rt["tail_fixed"] != null && (bool)rt["tail_fixed"];
            list.Add(MakeGear(new GearSpec { strut = "gear_tail_strut", wheel = "gear_tail_wheel", part = "fus_rear", fold = tailFixed ? 0.5f : Mathf.Max(0.5f, (float)rt["tail_fold_deg"]), fwd = false, retractedDrag = parts["fus_rear"].dragArea, travel = 0.11f + 0.20f, k = GearTailK, c = GearTailC * GearDampingScale183D, maxComp = GearTailMaxComp,
                mass = 6f, drag = parts["fus_rear"].dragArea + (tailFixed ? 0f : TailGearDrag), steer = true, brake = false, diff = 0f }, "CAS1:gear_F_sprung", "COIN:wheel_F"));
            return list;
        }

        // fixed gear: foldDegrees 0.5 (a 0 fold divides by zero in LandingGear.MoveGear) and extendedDrag = the part's own dragArea, so a
        // "retracted" state changes neither the look nor the drag (the gear's drag is already in the part's dragArea)
        static LandingGear MakeGear(GearSpec g, string tplGear, string tplWheel)
        {
            var strut = Find(g.strut); var wheel = Find(g.wheel); var part = parts[g.part];
            // 1.4.0 tail skid: the contact frame is an empty (no mesh); radius = the 1.2.3 tailwheel radius from the contract (same contact point)
            float r = wheel.GetComponent<MeshFilter>() != null ? wheel.GetComponent<MeshFilter>().sharedMesh.bounds.extents.y : (float)contract["gear"]["tail_r"];
            Vector3 axle = wheel.position;
            // round 3 v2: LandingGear sets gearHinge.localEulerAngles = hingeBaseAngles + (foldDegrees, 0, 0) (LandingGear.il OnSetGear), so a
            // base YAW turns the fold axis in the horizontal plane: the mains fold forward-up-in. Yaw sign: the one that brings the folded
            // wheel closest to the centreline (checked below with the fold sign).
            Quaternion hRot = part.transform.rotation;
            if (g.yaw != 0f)
            {
                var wv0 = axle - strut.position; float bestX = float.MaxValue;
                foreach (var ys in new[] { 1f, -1f })
                {
                    var q = part.transform.rotation * Quaternion.Euler(0f, ys * g.yaw, 0f); var ax = q * Vector3.right;
                    foreach (var fs in new[] { 1f, -1f })
                    {
                        var wf = Quaternion.AngleAxis(fs * g.fold, ax) * wv0;
                        var lp = part.transform.InverseTransformDirection(wf); var l0 = part.transform.InverseTransformDirection(wv0);
                        if (lp.z <= l0.z) continue;                                  // forward folds only
                        float x = Mathf.Abs(part.transform.InverseTransformPoint(strut.position + wf).x);
                        if (x < bestX) { bestX = x; hRot = q; }
                    }
                }
            }
            // round 7: TILTED fold axis. LandingGear turns gearHinge about its PARENT's X (localEulerAngles = base + (fold, 0, 0)) and measures
            // the current angle as Angle(hinge.forward, parent.forward) (LandingGear.cs 341, 371): an axis frame whose +X = the contract axis
            // (root-relative = part frame at build time) is the hinge's parent; the hinge rests at identity under it (base angles 0).
            Transform hingeParent = part.transform;
            if (g.axis.HasValue)
            {
                var axW = root.transform.TransformDirection(g.axis.Value.normalized);
                var fr = NewGO(g.strut.Replace("_strut", "_axisframe"), part.transform, strut.position, Quaternion.FromToRotation(Vector3.right, axW) * Quaternion.identity);
                hingeParent = fr.transform; hRot = fr.transform.rotation;
            }
            var hinge = NewGO(g.strut.Replace("_strut", "_hinge"), hingeParent, strut.position, hRot);
            strut.SetParent(hinge.transform, true);
            var sprung = NewGO(g.strut.Replace("_strut", "_leg"), hinge.transform, strut.position, part.transform.rotation);
            var unsprung = NewGO(g.strut.Replace("_strut", "_unsprung"), sprung.transform, axle, part.transform.rotation);
            wheel.SetParent(unsprung.transform, true);
            var bump = NewGO(g.strut.Replace("_strut", "_bumpstop"), sprung.transform, axle + Vector3.up * (g.travel - r), part.transform.rotation);
            var dust = CopyParticle(TplFind(tplWheel).GetComponent<ParticleSystem>(), unsprung.transform, axle - Vector3.up * r, g.strut + "_dust");
            var skid = TailSkid ? TryFind(g.strut.Replace("_strut", "_skid")) : null;
            if (skid != null) skid.SetParent(unsprung.transform, true);          // the shoe rides the suspension; the arm stays on the strut
            var tw = TplFind(tplWheel).GetComponents<AudioSource>();
            var a0 = CloneComp(tw[0], wheel.gameObject); var a1 = CloneComp(tw[1], wheel.gameObject);
            var box = sprung.AddComponent<BoxCollider>();
            var sb = strut.GetComponent<MeshFilter>().sharedMesh.bounds;
            box.center = sprung.transform.InverseTransformPoint(strut.TransformPoint(sb.center)); box.size = sb.size; box.enabled = false;
            var lg = CloneComp(TplComp<LandingGear>(tplGear), sprung);
            S(lg, "attachedPart", part); S(lg, "aircraft", aircraft);
            S(lg, "extendedDrag", g.drag);
            S(lg, "bumpStop", bump); S(lg, "unsprung", unsprung);
            S(lg, "suspensionTravel", g.travel); S(lg, "springRate", g.k); S(lg, "dampingRate", g.c);
            Transform cast = bump.transform;
            if (g.brake && MainContactForward != 0f)
            {   // 1.7.12: the contact point (LandingGear linecasts from castPoint and applies all wheel forces at the hit) sits ahead of the tyre; the visible wheel still follows bumpStop
                cast = NewGO(g.strut.Replace("_strut", "_contact"), sprung.transform, bump.transform.position + part.transform.forward * MainContactForward, bump.transform.rotation).transform;
            }
            S(lg, "castPoint", cast); S(lg, "wheelRadius", r);
            S(lg, "wheels", new[] { wheel }); S(lg, "axle", unsprung.transform);
            SetSeq(lg, "joints", new object[0]);
            S(lg, "tireNoiseSound", a0); S(lg, "tireSkidSound", a1);
            S(lg, "maxCompression", g.maxComp); S(lg, "mass", g.mass); S(lg, "gearCollider", box);
            S(lg, "gearHinge", hinge.transform); S(lg, "hingeFoldMotion", Vector3.zero);
            // fold sign: LandingGear.MoveGear turns gearHinge.localEulerAngles.x by +-foldDegrees; pick the sign that sends the wheel forward (mains)
            // or aft (tailwheel). strutRotationTransform must exist (MoveGear writes it every frame): an idle child with strutRotation 0.
            var wv = axle - hinge.transform.position;
            float sgnF = (Quaternion.AngleAxis(g.fold, hinge.transform.right) * wv).z > wv.z ? 1f : -1f;
            if (!g.fwd) sgnF = -sgnF;
            if (g.stowed.HasValue)      // round 7: the sign that lands the wheel on the contract's stowed position (Blender -> Unity flips handedness)
            {
                var want = root.transform.TransformPoint(g.stowed.Value);
                float dP = (hinge.transform.position + Quaternion.AngleAxis(g.fold, hinge.transform.right) * wv - want).magnitude;
                float dN = (hinge.transform.position + Quaternion.AngleAxis(-g.fold, hinge.transform.right) * wv - want).magnitude;
                sgnF = dP < dN ? 1f : -1f;
                L($"gear {g.strut}: tilted axis {hinge.transform.right.ToString("F3")}, stowed wheel miss {Mathf.Min(dP, dN):F3} m (other sign {Mathf.Max(dP, dN):F3})");
            }
            S(lg, "foldDegrees", sgnF * g.fold); S(lg, "foldSpeed", 25f);
            var srt = NewGO(g.strut.Replace("_strut", "_strutrot"), sprung.transform, sprung.transform.position, sprung.transform.rotation);
            S(lg, "strutRotationTransform", srt.transform); S(lg, "strutRotation", 0f);
            S(lg, "retractedDrag", g.retractedDrag);
            SetSeq(lg, "movingParts", new object[0]);
            S(lg, "steering", g.steer); S(lg, "braked", g.brake);
            S(lg, "steeringLock", g.steer ? TailSteeringLock : 0f);
            if (g.brake) S(lg, "frictionCoef", MainGearFriction);
            if (g.brake) S(lg, "response", MainSideResponse); S(lg, "steeringSpeed", g.steer ? 90f : 0f); S(lg, "aligningStrength", g.steer ? 8f : 0f);   // round 9: stiffer tailwheel centring (FD-32 swung 20 deg left at 0.4 throttle)
            S(lg, "differentialBrakeFactor", g.diff);
            S(lg, "dust", dust);
            S(lg, "gearDoors", new List<LandingGear.GearDoor>());
            L($"gear {g.strut}: r={r:F3} axle={axle.ToString("F3")} travel={g.travel} k={g.k} foldDegrees={G(lg, "foldDegrees")} ({(g.fwd ? "forward" : "aft")}) retractedDrag={g.retractedDrag:F3} steer={g.steer} brake={g.brake} part={part.name}");
            if (g.brake && SplitMainGear) GripGear.Add(lg, MainBrakeShare, MainGearFriction, GripFriction, BrakedRolling, GripRolling, L);
            if (g.brake && MainCastor188) GripGear.Castor(lg, MainCastorRange, MainCastorAlign, L);     // after the split: the grip leg copies `axle`, not `steering`
            return lg;
        }

        // ------------------------------------------------------------------ engine + propeller (B-25H/CI-22 component path, once)
        static void Engine()
        {
            var startup = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), parts["FD32"].gameObject);
            var eng = parts["fus_engine"].gameObject;
            var turb = CloneComp(TplAudio("COIN:COIN", "cricket_turbine"), eng);
            // electric motor + turbogenerator as one stock TurbineEngine (stock drive only, user decision): power x airDensity / 1.225 as every stock engine
            var te = CloneComp(TplComp<TurbineEngine>("CAS1:engine_L"), eng);
            te.maxRPM = 2600f; te.minRPM = 500f; te.maxPower = EnginePower; te.spoolUpTime = 1.0f; S(te, "startupTime", 3f);
            S(te, "pitch", 0.22f); S(te, "volume", 0.05f);
            S(te, "startupAudio", startup); te.aircraft = aircraft;
            S(te, "heatHazeParticles", new ParticleSystem[0]);
            S(te, "maxFuelConsumption", FuelBurn); S(te, "IRMin", IRMin); S(te, "IRMax", IRMax);
            S(te, "IRSourceTransform", Find("exhaust_point"));
            S(te, "criticalParts", new UnitPart[] { parts["fus_engine"], parts["prop"] });
            S(te, "criticalDamageThreshold", 40f);
            try { S(te, "failureMessage", "ENGINE FAILURE"); S(te, "failureMessageAudio", null); } catch { }
            S(te, "failureTransform", NewGO("engine_fail", eng.transform, eng.transform.position + new Vector3(0, 0.3f, 0.2f), Quaternion.identity).transform);
            var tr = CloneComp(TplComp<Transmission>("COIN:COIN"), eng);
            S(tr, "powerSources", new[] { eng });

            var propGO = parts["prop"].gameObject;
            var hubVis = Find("prop_hub");
            var pa = CloneComp(TplAudio("COIN:propHub", "cricket_exterior"), propGO);
            var csp = CloneComp(TplComp<ConstantSpeedProp>("COIN:propHub"), propGO);
            S(csp, "unitPart", parts["prop"]); S(csp, "transmission", tr); S(csp, "oppositeCorner", null);
            var fTurn = Fld(typeof(ConstantSpeedProp), "turnDirection"); fTurn.SetValue(csp, Enum.ToObject(fTurn.FieldType, 1));
            var fPitch = Fld(typeof(ConstantSpeedProp), "pitchDirection"); fPitch.SetValue(csp, Enum.ToObject(fPitch.FieldType, -1));
            var blades = new List<object>(); var dmg = new List<Mesh>(); float R = 0f;
            foreach (var bmf in hubVis.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.Contains("_blade")).OrderBy(m => m.name).ToList())
            {
                var radial = bmf.transform.up;
                float tip = bmf.sharedMesh.bounds.max.y; R = Mathf.Max(R, tip);
                var F = propGO.transform.forward;
                var broot = NewGO(bmf.name + "_root", hubVis, hubVis.position, Quaternion.LookRotation(radial, Vector3.Cross(radial, -F)));
                bmf.transform.SetParent(broot.transform, true);
                var tang = Vector3.Cross(-F, radial);
                var lt = NewGO(bmf.name + "_lift", broot.transform, hubVis.position + radial * tip, Quaternion.LookRotation(tang, F));
                var b = New(typeof(ConstantSpeedProp.PropBlade));
                S(b, "transform", broot.transform); S(b, "liftTransform", lt.transform); S(b, "mass", 6f);   // composite blade
                ((ConstantSpeedProp.PropBlade)b).renderer = bmf.GetComponent<MeshRenderer>();
                ((ConstantSpeedProp.PropBlade)b).bladeMeshFilter = bmf;
                blades.Add(b);
                if (dmg.Count == 0) foreach (var f in new[] { 0.25f, 0.5f, 0.75f, 0.95f }) dmg.Add(TruncatedBlade(bmf.sharedMesh, tip * f, $"{bmf.name}_dmg{(int)(f * 100)}"));
            }
            SetSeq(csp, "blades", blades);
            S(csp, "hubVisible", hubVis.gameObject);
            var disc = NewGO("prop_disc", hubVis, hubVis.position + hubVis.forward * 0.01f, hubVis.rotation);
            disc.AddComponent<MeshFilter>(); var dr = disc.AddComponent<MeshRenderer>(); dr.sharedMaterial = mats["propdisc"]; dr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            S(csp, "propDisc", disc.GetComponent<MeshFilter>());
            S(csp, "bladeDamageMeshes", dmg.ToArray());
            S(csp, "fragmentPrefab", null);
            SetSeq(csp, "propDiscMeshes", new Mesh[] { null, BlurStageMesh("prop_blur1", R * 1.01f, 0.5f), BlurStageMesh("prop_blur2", R * 1.01f, 0f) });
            S(csp, "propDiskThicknessMin", 1f); S(csp, "propDiskThicknessMax", 1f);
            S(csp, "propBlurLightsMaterial", null);
            var strikeGO = NewGO("prop_strike", propGO.transform, hubVis.position, propGO.transform.rotation, 15);
            var smc = strikeGO.AddComponent<MeshCollider>(); smc.sharedMesh = CylinderMesh("prop_strike", R, 0.06f, 24); smc.convex = true; smc.isTrigger = true;
            var psd = CloneComp(TplComp<PropStrikeDetector>("COIN:propDiscCollider"), strikeGO);
            S(psd, "currentRadius", R); S(psd, "propCollider", smc);
            S(csp, "propDiscCollider", smc); S(csp, "propStrikeDetector", psd);
            S(csp, "momentOfInertia", 24f); S(csp, "bladeLength", R); S(csp, "hubRadius", 0.22f);
            S(csp, "rpmLimit", PropRpm); S(csp, "nominalPower", EnginePower); S(csp, "propTorqueLimit", 8000f);
            S(csp, "bladeEfficiency", BladeEfficiency); S(csp, "targetAOA", PropTargetAoA);
            S(csp, "propAudio", pa);
            L($"prop: radius {R:F3} m, {blades.Count} blades, rpmLimit {PropRpm}, power {EnginePower / 1000f} kW, hub {hubVis.position.ToString("F3")}");
            if (HybridBoost) Boost(eng);
        }

        // BOOST detent (GA25XBuild.cs Boost, adapted to one engine): stock Turbojet.FixedUpdate -> JetNozzle.Thrust(..., allowAfterburner) ->
        // Afterburner.Run(throttle * (rpmRatio > 0.85)): amount = (throttle - 0.9) / 0.1, thrust x clamp(airDensity, 0.4, 1) on the nozzle part.
        // The Turbojet itself makes ~0 N and burns no fuel; Afterburner.Run is not null-safe (renderers, audio source): mesh-less / clip-less.
        static void Boost(GameObject eng)
        {
            var tjSrc = tpl["Fighter1"].GetComponentInChildren<Turbojet>(true);
            var jnSrc = tpl["Fighter1"].GetComponentInChildren<JetNozzle>(true);
            var fwd = parts["prop"].transform.forward;
            var bpos = Find("exhaust_point").position;
            if (BoostOnCentreline) { var lp = root.transform.InverseTransformPoint(bpos); lp.x = 0f; bpos = root.transform.TransformPoint(lp); }   // 1.8.2
            var bg = NewGO("boost", eng.transform, bpos, Quaternion.LookRotation(fwd, Vector3.up));
            var silent = CloneComp(TplAudio("COIN:COIN", "cricket_turbine"), bg); silent.volume = 0f; silent.playOnAwake = false;
            var abSrc = bg.AddComponent<AudioSource>(); abSrc.clip = null; abSrc.playOnAwake = false; abSrc.volume = 0f; abSrc.spatialBlend = 1f;
            var fx = NewGO("boost_fx", bg.transform, bg.transform.position, bg.transform.rotation);
            fx.AddComponent<MeshFilter>();
            var fxr = fx.AddComponent<MeshRenderer>(); fxr.sharedMaterial = mats["propdisc"]; fxr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; fxr.enabled = false;
            var tj = CloneComp(tjSrc, bg);
            var jn = CloneComp(jnSrc, bg);
            tj.maxThrust = 1f;
            S(tj, "turbineAudio", silent); S(tj, "nozzles", new[] { jn }); S(tj, "vectoringTransforms", new Transform[0]);
            S(tj, "thrustVectoring", Vector3.zero); S(tj, "splitThrustFactor", 0f);
            S(tj, "fuelConsumptionMin", 0f); S(tj, "fuelConsumptionMax", 0f);
            S(tj, "criticalParts", new UnitPart[] { parts["fus_engine"], parts["prop"] });
            S(tj, "failureMessage", ""); S(tj, "failureMessageAudio", null);
            S(jn, "part", parts["fus_engine"]); S(jn, "turbojet", tj); S(jn, "engine", null);
            S(jn, "thrustTransform", bg.transform); S(jn, "vectorTransforms", new Transform[0]); S(jn, "glow", null);
            S(jn, "thrustAudio", silent); S(jn, "thrustMaxVolume", 0f); S(jn, "IRMin", 0f); S(jn, "IRMax", 0f);
            S(jn, "thrustProportion", 1f); S(jn, "pitchThrust", 0f); S(jn, "rollThrust", 0f);
            var abs = (Array)G(jn, "afterburners");
            var ab = abs.Length > 0 ? abs.GetValue(0) : NewElem(jn, "afterburners");
            S(ab, "flameRenderer", fxr); S(ab, "nozzleGlowRenderer", fxr); S(ab, "thrustDirection", bg.transform); S(ab, "source", abSrc);
            S(ab, "throttleStart", 0.9f); S(ab, "throttleEnd", 1f); S(ab, "thrust", BoostThrust); S(ab, "fuelConsumption", BoostFuel);
            S(ab, "flameBrightness", 0f); S(ab, "nozzleGlowBrightness", 0f); S(ab, "temperature", 0f); S(ab, "IRIntensity", BoostIR);
            var arr = Array.CreateInstance(ab.GetType(), 1); arr.SetValue(ab, 0); S(jn, "afterburners", arr);
            L($"boost: Turbojet+JetNozzle on {bg.name}, afterburner {BoostThrust} N from throttle 0.9, fuel {BoostFuel} kg/s, IR {BoostIR}");
        }

        // One single-sided disc in the hub's XY plane mapped onto one half of the blur atlas (vBase 0 = disc, 0.5 = smear). From B25HBuild.cs.
        static Mesh BlurStageMesh(string name, float R, float vBase, int seg = 64)
        {
            var v = new List<Vector3> { Vector3.zero }; var uv = new List<Vector2> { new Vector2(0.5f, vBase + 0.25f) }; var t = new List<int>();
            for (int i = 0; i <= seg; i++)
            {
                float a = i * Mathf.PI * 2f / seg;
                v.Add(new Vector3(Mathf.Cos(a) * R, Mathf.Sin(a) * R, 0));
                uv.Add(new Vector2(0.5f + 0.5f * Mathf.Cos(a), vBase + 0.25f + 0.25f * Mathf.Sin(a)));
            }
            for (int i = 1; i <= seg; i++) t.AddRange(new[] { 0, i + 1, i });
            return NewMesh(name, v.ToArray(), t.ToArray(), uv.ToArray());
        }

        // ------------------------------------------------------------------ weapons
        static WeaponMount ammoVickers, hookMount, cooperMount; static WeaponInfo vickersInfo, cooperInfo; static MissileDefinition cooperDef;
        static GameObject hookGO, bombGO, mountGO; static Mesh bombMesh, rackMesh; static Material[] bombMats, rackMats; static Vector3 bombPivot, rackPivot;
        static readonly List<HardpointSet> sets = new List<HardpointSet>();

        static Hardpoint HP(Transform t, AeroPart part, Weapon[] builtIn = null)
        {
            var h = new Hardpoint { transform = t, part = part, bayDoors = new BayDoor[0], doorOpenDuration = 1f, BuiltInWeapons = builtIn ?? new Weapon[0], BuiltInTurrets = new Turret[0] };
            S(h, "pylonOptions", Array.CreateInstance(Elem(Fld(typeof(Hardpoint), "pylonOptions")), 0));
            return h;
        }
        static HardpointSet Set(string name, IEnumerable<WeaponMount> options, params Hardpoint[] hps)
        {
            var hs = new HardpointSet { name = name, precludingHardpointSets = new List<byte>(), SymmetryWithPrev = false, SymmetryName = "", weaponOptions = new List<WeaponMount> { null }, hardpoints = hps.ToList() };
            hs.weaponOptions.AddRange(options);
            sets.Add(hs); return hs;
        }

        static void Weapons()
        {
            sets.Clear();
            var eng = parts["fus_engine"];
            // ---- 12.7 mm x2 (synchronised): one Gun (stock gun_12.7mm_internal values + stock Gun12.7mm info), two muzzles AHEAD of the prop disc
            var g12 = tpl["gun_12.7mm_internal"].GetComponentInChildren<Gun>(true);
            vickersInfo = Asset<WeaponInfo>("MonoBehaviour/Gun12.7mm_PLACEHOLDER.asset");
            var mL = Find("muzzle_gun_L"); var mR = Find("muzzle_gun_R");
            if (!SyncMuzzlesAhead) { mL.position = Find("flash_gun_L").position; mR.position = Find("flash_gun_R").position; }
            var gunGO = NewGO("guns_127", eng.transform, (Find("flash_gun_L").position + Find("flash_gun_R").position) / 2, Quaternion.identity);
            foreach (var a in g12.GetComponents<AudioSource>()) CloneComp(a, gunGO).loop = false;
            var gun = CloneComp(g12, gunGO);
            gun.attachedUnit = aircraft; gun.info = vickersInfo;
            S(gun, "magazineCapacity", GunRounds); S(gun, "magazines", 0); S(gun, "startLoaded", true);
            S(gun, "fireRate", GunFireRate); S(gun, "muzzles", new[] { mL, mR });
            // Gun.SpawnBullet fires EVERY muzzle per shot and decrements bulletsLoaded once (Mk I finding): 400 = 400 rounds per gun
            S(gun, "tracerRatio", TracerRatio); S(gun, "tracerSize", TracerSize);
            S(gun, "recoilTransform", null); S(gun, "spinTransform", null);
            var ps = new List<ParticleSystem>();
            foreach (var fl in new[] { Find("flash_gun_L"), Find("flash_gun_R") }) ps.AddRange(CopyMuzzleParticles(g12, fl));
            // round 3 (user: the 12.7 mm smoke blinds the pilot "like black powder"): the stock nose-gun effect sits 2 m in front of the eye here,
            // so every smoke system is dropped and the flash halved (stock fighters' nose guns sit far below / beside the canopy)
            var keep = new List<ParticleSystem>();
            foreach (var p_ in ps)
            {
                if (p_ == null) continue;
                // the stock "muzzle" system IS the smoke (renderer material smoke_foreground, 0.25-0.5 s life); "muzzleFlash" is the flash
                var pr_ = p_.GetComponent<ParticleSystemRenderer>();
                bool smoky = p_.name.ToLowerInvariant().Contains("smoke") || (pr_ != null && pr_.sharedMaterials.Any(m => m != null && m.name.ToLowerInvariant().Contains("smoke")));
                if (smoky)
                { L($"muzzle: dropped smoke system {p_.name}"); Object.DestroyImmediate(p_.gameObject); continue; }
                var mm = p_.main; mm.startSizeMultiplier *= 0.5f; keep.Add(p_);
            }
            ps = keep;
            L($"muzzle particles kept: {string.Join(", ", ps.Select(q => q.name))}");
            S(gun, "muzzleParticles", ps.ToArray());
            var ammoPrefabGO = new GameObject("FD32_internal_ammo");
            var ammoPrefab = PrefabUtility.SaveAsPrefabAsset(ammoPrefabGO, Folder + "/FD32_internal_ammo.prefab");
            Object.DestroyImmediate(ammoPrefabGO);
            var tAmmo = Asset<WeaponMount>("MonoBehaviour/gun_ammo_35mm_720_PLACEHOLDER.asset");
            ammoVickers = Object.Instantiate(tAmmo); ammoVickers.name = "FD32_ammo_127";
            ammoVickers.prefab = ammoPrefab; ammoVickers.jsonKey = "FD32_ammo_127"; ammoVickers.info = vickersInfo;
            ammoVickers.mountName = "12.7mm x2 (400 rpg)"; ammoVickers.ammo = GunRounds; ammoVickers.GunAmmo = true; ammoVickers.mass = 2 * GunRounds * 0.12f;
            if (NoGearSafety) ammoVickers.GearSafety = false;
            AssetDatabase.CreateAsset(ammoVickers, Folder + "/FD32_ammo_127.asset");
            Set("Guns", new[] { ammoVickers }, HP(gunGO.transform, eng, new Weapon[] { gun }));

            // ---- 4 pylons (stock stores, stock mounts; hardpoints on the pylon bottom faces)
            Set("Inner Pylons", InnerStores.Select(Mount), HP(Find("hp_inner_L"), parts["wing_lower_L"]), HP(Find("hp_inner_R"), parts["wing_lower_R"]));
            Set("Outer Pylons", OuterStores.Select(Mount), HP(Find("hp_outer_L"), parts["wing_lower_L"]), HP(Find("hp_outer_R"), parts["wing_lower_R"]));

            // ---- tail hook (Mk I pattern)
            var hookT = Find("tailhook");
            if (OwnTailHookMount)
            {
                hookMount = Object.Instantiate(Mount("TailHook_Multirole1")); hookMount.name = "FD32_tailhook";
                hookMount.jsonKey = "FD32_tailhook"; hookMount.mountName = "Arrestor Hook"; hookMount.tailHook = true; hookMount.prefab = null;
                AssetDatabase.CreateAsset(hookMount, Folder + "/FD32_tailhook.asset");
                hookGO = BuildTailHookObject(hookT);
            }
            else { hookMount = Mount("TailHook_Multirole1"); Object.DestroyImmediate(hookT.gameObject); }
            Set("Tail Hook", new[] { hookMount }, HP(Find("hp_tailhook"), parts["FD32"]));

            var all = sets.SelectMany(x => x.hardpoints).OrderByDescending(h => h.transform.position.x).ThenByDescending(h => h.transform.position.z).ToList();
            for (int i = 0; i < all.Count; i++) all[i].HardpointIndex = i;
            weaponManager.hardpointSets = sets.ToArray();
            S(weaponManager, "aircraft", aircraft);
            L($"hardpoint sets: {string.Join(" | ", sets.Select(x => $"{x.name} ({x.hardpoints.Count} hp, {x.weaponOptions.Count - 1} options: {string.Join(",", x.weaponOptions.Where(o => o != null).Select(o => o.jsonKey))})"))}");
            L($"guns: muzzles L {mL.position.ToString("F3")} R {mR.position.ToString("F3")}, flashes at {Find("flash_gun_L").position.ToString("F3")}; prop plane z {Find("prop_hub").position.z:F3}");
        }

        // Our bomb: our mesh + the stock PAB-125 component values (Missile, OpticalSeekerBomb, MissileNetworkTransform), references re-wired.
        static GameObject BuildBombObject()
        {
            var t = tpl["bomb_125_1"];
            var go = new GameObject("FD32_cooper") { layer = t.layer };
            go.AddComponent<MeshFilter>().sharedMesh = bombMesh;
            go.AddComponent<MeshRenderer>().sharedMaterials = bombMats;
            go.AddComponent<Mirage.NetworkIdentity>();
            var rb = go.AddComponent<Rigidbody>(); EditorUtility.CopySerialized(t.GetComponent<Rigidbody>(), rb); rb.mass = CooperMass;
            var cc = go.AddComponent<CapsuleCollider>(); EditorUtility.CopySerialized(t.GetComponent<CapsuleCollider>(), cc);
            var b = bombMesh.bounds; cc.center = b.center; cc.direction = 2; cc.radius = 0.06f; cc.height = b.size.z;
            var mis = (Missile)go.AddComponent(t.GetComponent<Missile>().GetType());
            EditorUtility.CopySerialized(t.GetComponent<Missile>(), mis);
            var so = new SerializedObject(mis); var it = so.GetIterator(); bool enter = true;
            while (it.Next(enter)) { enter = true; if (it.propertyType == SerializedPropertyType.ObjectReference && it.objectReferenceValue != null && IsTemplateObject(it.objectReferenceValue)) it.objectReferenceValue = null; }
            so.ApplyModifiedPropertiesWithoutUndo();
            mis.definition = cooperDef;
            S(mis, "mass", CooperMass); S(mis, "blastYield", CooperYield); S(mis, "pierceDamage", 40f); S(mis, "finArea", 0.012f); S(mis, "info", cooperInfo);
            var so2 = new SerializedObject(mis);
            void Eff(string p, string asset) { var sp = so2.FindProperty("warhead." + p); if (sp != null) sp.objectReferenceValue = Asset<GameObject>($"GameObject/{asset}_PLACEHOLDER.prefab"); }
            // 1.4.0: the stock effect family for this yield (AGM2 yield 8, AAM3 6.5: explosion_10kg / _10kg_armor / _10kg_dusty / WaterSurfaceExplosion_10kg)
            Eff("airEffect", "explosion_10kg"); Eff("armorEffect", "explosion_10kg_armor"); Eff("terrainEffect", "explosion_10kg_dusty");
            Eff("waterSurfaceEffect", "WaterSurfaceExplosion_10kg"); Eff("underwaterEffect", "WaterSurfaceExplosion_10kg");
            so2.ApplyModifiedPropertiesWithoutUndo();
            var seekT = t.GetComponent<OpticalSeekerBomb>();
            var seek = (OpticalSeekerBomb)go.AddComponent(seekT.GetType()); EditorUtility.CopySerialized(seekT, seek); S(seek, "missile", mis);
            var mntT = t.GetComponent<NuclearOption.NetworkTransforms.MissileNetworkTransform>();
            var mnt = go.AddComponent<NuclearOption.NetworkTransforms.MissileNetworkTransform>(); EditorUtility.CopySerialized(mntT, mnt); S(mnt, "Missile", mis);
            L($"bomb object: mesh {bombMesh.vertexCount} v, length {b.size.z:F2} m, mass {CooperMass} kg, blastYield {CooperYield}, effects explosion_10kg; pivot centred {CooperPivotCentred} (offset {bombCentre.ToString("F3")}), capsule centre {cc.center.ToString("F3")} r {cc.radius}");
            return go;
        }

        static GameObject BuildCooperMountObject()
        {
            var go = new GameObject("FD32_cooper_x2");
            go.AddComponent<MeshFilter>().sharedMesh = rackMesh; go.AddComponent<MeshRenderer>().sharedMaterials = rackMats;
            var tb = TplFind("bomb_125_double:bomb (1)");
            for (int k = 0; k < 2; k++)
            {
                var c = new GameObject($"bomb ({k + 1})"); c.transform.SetParent(go.transform, false);
                c.transform.localPosition = new Vector3(k == 0 ? -0.16f : 0.16f, -0.040f, 0f) + bombCentre;
                c.AddComponent<MeshFilter>().sharedMesh = bombMesh; c.AddComponent<MeshRenderer>().sharedMaterials = bombMats;
                var bc = c.AddComponent<BoxCollider>(); bc.center = bombMesh.bounds.center; bc.size = bombMesh.bounds.size;
                var au = c.AddComponent<AudioSource>(); EditorUtility.CopySerialized(tb.GetComponent<AudioSource>(), au);
                var mmT = tb.GetComponent<MountedMissile>();
                var mm = (MountedMissile)c.AddComponent(mmT.GetType()); EditorUtility.CopySerialized(mmT, mm);
                S(mm, "info", cooperInfo); S(mm, "attachedUnit", null);
            }
            return go;
        }

        // Own tail-hook mount (GA25XBuild.cs pattern): root TailHook / hinge / hook (localEulerAngles.x driven) / our mesh / hookEnd / castPoint.
        static GameObject BuildTailHookObject(Transform hookT)
        {
            var th = contract["tailhook"];
            float len = (float)th["length"], stow = (float)th["stowed_up_deg"], dep = (float)th["deployed_deg"];
            var go = new GameObject("FD32_tailhook_mount");
            var hinge = new GameObject("hinge"); hinge.transform.SetParent(go.transform, false);
            var hook = new GameObject("hook"); hook.transform.SetParent(hinge.transform, false);
            var mesh = new GameObject("hook_mesh"); mesh.transform.SetParent(hook.transform, false);
            // the model's hook mesh is modelled STOWED (tip up by stow deg); the hook frame sits at +stow when stowed, so undo it here
            mesh.transform.localRotation = Quaternion.Euler(-stow, 0, 0);
            mesh.AddComponent<MeshFilter>().sharedMesh = hookT.GetComponent<MeshFilter>().sharedMesh;
            if (!HookVisualAFrame) mesh.AddComponent<MeshRenderer>().sharedMaterials = hookT.GetComponent<MeshRenderer>().sharedMaterials;   // 1.4.0: hidden (hook_visual shows the hook)
            var end = new GameObject("hookEnd"); end.transform.SetParent(hook.transform, false); end.transform.localPosition = new Vector3(0, 0, -len);
            var cast = new GameObject("castPoint"); cast.transform.SetParent(end.transform, false);
            cast.transform.localPosition = new Vector3(0, 0, 0.887f * len); cast.transform.localRotation = Quaternion.Euler(180f, 0, 0);
            var t = go.AddComponent<TailHook>();
            EditorUtility.CopySerialized(TplComp<TailHook>("TailHook_Multirole1:TailHook_Multirole1"), t);
            Remap(t);
            S(t, "hinge", hinge.transform); S(t, "hook", hook.transform); S(t, "castPoint", cast.transform); t.hookEnd = end.transform;
            // TailHook writes hook.localEulerAngles.x = Lerp(stowed, deployed); Unity +x rotation lifts an aft-pointing tip
            S(t, "stowedAngle", stow); S(t, "deployedAngle", dep);
            hook.transform.localEulerAngles = new Vector3(stow, 0, 0);
            Object.DestroyImmediate(hookT.gameObject);
            int dropped = 0;
            foreach (var pp in parts.Values) { var lst = (List<Renderer>)G(G(pp, "damageMaterial"), "renderers"); dropped += lst.RemoveAll(r => r == null); }
            L($"tail hook mount: length {len:F2} m, stowed {stow} deg, deployed {dep} deg; {dropped} destroyed renderer(s) removed from part lists");
            return go;
        }


        // ------------------------------------------------------------------ cockpit, pilot, hood (GA-25X 0.3.x kitbash: stock seat / stick / throttle / screens)
        static readonly List<Pilot> crew = new List<Pilot>();
        static Transform helmetCam;
        static Canopy hood;
        static void Cockpit()
        {
            var cp = parts["FD32"];
            var eye = Find("cockpit_eye");
            var fig = (GameObject)Object.Instantiate(TplFind("COIN:pilot").gameObject);
            fig.SetActive(true); fig.name = "pilot";
            foreach (var t in fig.GetComponentsInChildren<Transform>(true).Where(t => t.name == "EjectionSeat").ToList())
            {
                if (!EjectionSeats || !StockCockpitKit) { Object.DestroyImmediate(t.gameObject); continue; }
                // GA-25X 0.3.1: keep the figure's stock seat (COIN / SFB-81: mesh ejectionSeat, material Seats): it leaves with the pilot
                t.GetComponent<MeshFilter>().sharedMesh = Asset<Mesh>("Mesh/ejectionSeat_PLACEHOLDER.asset");
                t.GetComponent<MeshRenderer>().sharedMaterials = new[] { Asset<Material>("Material/Seats_PLACEHOLDER.mat") };
                var sc = t.GetComponent<MeshCollider>(); if (sc != null) sc.sharedMesh = Asset<Mesh>("Mesh/ejectionSeat_PLACEHOLDER.asset");
                L($"pilot: stock EjectionSeat kept at {t.localPosition.ToString("F4")} in the figure");
            }
            fig.transform.SetParent(eye.parent, false);
            var cam = fig.GetComponentsInChildren<Transform>(true).First(t => t.name == "helmetCamPoint");
            fig.transform.rotation = Quaternion.LookRotation(Vector3.forward, Vector3.up);
            fig.transform.position += eye.position - cam.position;
            foreach (var comp in fig.GetComponentsInChildren<Component>(true)) if (comp != null) Remap(comp);
            var pc = fig.GetComponent<Pilot>();
            S(pc, "aircraft", aircraft); S(pc, "unitPart", cp); S(pc, "ejectionSeat", EjectionSeats); S(pc, "autoTrimmer", controlsFilter);
            S(pc, "pilotCollider", fig.GetComponent<CapsuleCollider>());
            pc.exitDirection = Pilot.ExitDirection.Left;
            helmetCam = cam; crew.Add(pc);
            L($"pilot eye {cam.position.ToString("F3")} vs cockpit_eye {eye.position.ToString("F3")}, ejection seat {EjectionSeats}");

            // ---- hood: stock Canopy (COIN canopyFrame_F values); opens by tilting up about the back of its fairing (canopy_slide_hinge, local X),
            // jettisoned before the seat fires (Aircraft.EjectionSequence). The opening sign is the one that lifts the hood's front.
            var hoodT = Find("canopy_slide"); var hingeT = Find("canopy_slide_hinge");
            var glassR = new[] { Find("canopy_slide_glass").GetComponent<MeshRenderer>() };
            float openDeg = (float)contract["canopy"]["open_deg"];
            var hmf = hoodT.GetComponent<MeshFilter>();
            var front = hmf.sharedMesh.vertices.Select(v => hoodT.TransformPoint(v)).OrderByDescending(v => v.z).First();
            float sgn = (Quaternion.AngleAxis(openDeg, hingeT.right) * (front - hingeT.position)).y > (Quaternion.AngleAxis(-openDeg, hingeT.right) * (front - hingeT.position)).y ? 1f : -1f;
            var ej = NewGO("canopy_eject", hingeT.parent, hingeT.position, Quaternion.LookRotation(Vector3.forward, Vector3.up));
            hingeT.SetParent(ej.transform, true);
            var box = hoodT.gameObject.AddComponent<BoxCollider>(); box.center = hmf.sharedMesh.bounds.center; box.size = hmf.sharedMesh.bounds.size; box.enabled = false;
            hood = CloneComp(TplComp<Canopy>("COIN:canopyFrame_F"), hingeT.gameObject);
            hood.ejectionTransform = ej.transform; hood.attachedPart = cp; hood.mass = 40f; hood.ejectionCollider = box;
            S(hood, "ejectionForce", new Vector3(0f, 4000f, 0f)); S(hood, "forcePosition", new Vector3(0f, 0f, 0.2f));
            var hh = NewElem(hood, "canopyHinges"); S(hh, "transform", DrivenFrame(hingeT)); S(hh, "hingeAngle", sgn * openDeg);
            SetSeq(hood, "canopyHinges", new[] { hh });
            S(hood, "fireTime", 0.2f); S(hood, "openSpeed", 0.6f);
            S(hood, "glassRenderers", glassR);
            S(aircraft, "canopies", new[] { hood });
            L($"hood: Canopy on {hingeT.name} at {hingeT.position.ToString("F3")}, hingeAngle {sgn * openDeg} (front lifts), jettison 4000 N on 40 kg");

            // ---- stock SFB-81 joystick / throttle meshes on our empties (GA-25X 0.3.1)
            foreach (var key in StockThrottle && contract["controls"]["throttle"]["stock_mesh"] != null ? new[] { "stick", "throttle" } : new[] { "stick" })
            {
                var c = contract["controls"][key];
                var t = Find((string)c["name"]);
                var mf = t.GetComponent<MeshFilter>(); if (mf == null) mf = t.gameObject.AddComponent<MeshFilter>();   // Unity fake-null: no ?? on components
                mf.sharedMesh = Asset<Mesh>("Mesh/" + (string)c["stock_mesh"] + "_PLACEHOLDER.asset");
                var mr = t.GetComponent<MeshRenderer>(); if (mr == null) mr = t.gameObject.AddComponent<MeshRenderer>();
                mr.sharedMaterials = ((Newtonsoft.Json.Linq.JArray)c["stock_materials"]).Select(x => Asset<Material>("Material/" + (string)x + "_PLACEHOLDER.mat")).ToArray();
                mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                L($"stock part {t.name}: {(string)c["stock_mesh"]} at {t.position.ToString("F3")}");
            }

            // cockpit-layer copies (the cockpit camera's near plane; exterior originals hidden in cockpit view)
            var cockpitR = new List<Renderer>(); var exteriorR = new List<Renderer>();
            var copyNames = new List<string> { "cockpit_interior", "cockpit_stick", "cockpit_throttle", "mfd_map", "mfd_power", "mfd_flight", "mfd_engine", "fus_center", "fus_engine", "canopy_slide", "canopy_slide_glass", "windscreen", "windscreen_frame" };
            copyNames.AddRange(new[] { "canopy_rail", "coaming_wall", "spine_fwd" });   // 1.8.3: sill rails, coaming wall, spine front (near the eye)
            copyNames.AddRange(root.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.StartsWith("cockpit_") && !m.name.EndsWith("_int")).Select(m => m.name));
            foreach (var n in copyNames.Distinct())
            {
                var orig = TryFind(n);
                if (orig == null || orig.GetComponent<MeshRenderer>() == null) continue;
                var src = orig.GetComponent<MeshRenderer>();
                var copy = NewGO(n + "_int", orig, orig.position, orig.rotation, 3);
                bool glassOnly = src.sharedMaterials.All(m => m == mats["glass"]);
                // round 6 (fault 5): COIN_glass_int culls back faces (_Cull 2) and our glass faces OUT, so the plain copy drew nothing from the
                // eye; the cockpit copy of a glass object is the same mesh with reversed winding (faces toward the pilot)
                copy.AddComponent<MeshFilter>().sharedMesh = InwardCockpitGlass && glassOnly ? InwardMesh(orig.GetComponent<MeshFilter>().sharedMesh, n + "_inward") : orig.GetComponent<MeshFilter>().sharedMesh;
                var cr = copy.AddComponent<MeshRenderer>();
                cr.sharedMaterials = src.sharedMaterials.Select(m => m == mats["glass"] ? (FaintCockpitGlass && glassOnly ? mats["glass_ck"] : mats["glass_int"]) : m).ToArray();
                cr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                cr.enabled = false;
                cockpitR.Add(cr); exteriorR.Add(src);
                if (!(n == "fus_center" || n == "fus_engine")) src.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                if (src.sharedMaterials[0] == mats["paint"])
                {
                    var owner = parts.Values.First(p => PartRenderers(p.gameObject).Contains(src));
                    ((List<Renderer>)G(G(owner, "damageMaterial"), "renderers")).Add(cr);
                }
            }
            S(aircraft, "cockpitRenderers", cockpitR.ToArray());
            S(aircraft, "exteriorRenderers", exteriorR.ToArray());

            // round 6 screens (fault 6: the 4-island 'tacscreen' mesh lost its UVs in export + CopyMesh): four quads (material 'screen', whose
            // UVs survive both), each mapping one region of the tac-page render texture; every renderer (and its cockpit copy) gets the stock
            // tacScreenDisplay material. GA-25X lesson: separate screen renderers all show the one tac page (TacScreen.renderTexture is a project
            // asset). Cockpit.tacScreenRender = TargetCam.targetScreenRenderer = the big map screen.
            Renderer tacR = null;
            foreach (var mj in (Newtonsoft.Json.Linq.JArray)contract["mfds"])
            {
                var t = Find((string)mj["name"]);
                foreach (var r in t.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.transform == t || r.name == t.name + "_int"))
                { r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.sharedMaterials = Enumerable.Repeat(mats["tacscreen"], r.sharedMaterials.Length).ToArray(); }
                if (mj["main"] != null && (bool)mj["main"]) tacR = t.GetComponent<MeshRenderer>();
            }
            L($"screens: {string.Join(", ", ((Newtonsoft.Json.Linq.JArray)contract["mfds"]).Select(m => (string)m["name"]))} = stock tacScreenDisplay; main (tacScreenRender / targetScreenRenderer) {tacR?.name}");

            var interior = Find("cockpit_interior").gameObject;
            var ck = CloneComp(TplComp<global::Cockpit>("COIN:cockpit_F_interior"), interior);
            S(ck, "tacScreenRender", tacR); S(ck, "aircraft", aircraft);
            S(ck, "engineSources", new[] { parts["fus_engine"].gameObject });
            var js = NewElem(ck, "joysticks"); S(js, "transform", DrivenFrame(Find("cockpit_stick"))); S(js, "range", (float)contract["controls"]["stick"]["range"]);
            SetSeq(ck, "joysticks", new[] { js });
            // round 9: stock SFB-81 throttle; Cockpit.Throttle writes localEulerAngles.x = throttle * range (Cockpit.cs 39-41). The drive frame is
            // aircraft-aligned; the sign is the one that moves the grips FORWARD (the user: the round-6 fal lever turned the wrong way)
            // round 10: the CI-22 single throttle (COIN_throttle, hotas), mounted as COIN.prefab: identity frame, Cockpit.Throttle MOTION
            // (localPosition = (0, 0, throttle * range), Cockpit.cs 43-45), range 0.22 m; the sign is the one that moves it FORWARD
            var thC = contract["controls"]["throttle"]; bool thMotion = thC["motion"] != null && (bool)thC["motion"];
            // Cockpit.Throttle MOTION writes localPosition = (0, 0, throttle * range): the driven transform needs its own zero-position parent
            // (DrivenFrame returns the transform itself when its local rotation is identity, which would send it to its parent's origin)
            Transform thDrv;
            if (thMotion)
            {
                var thT0 = Find("cockpit_throttle");
                var frame = NewGO("cockpit_throttle_frame", thT0.parent, thT0.position, root.transform.rotation, thT0.gameObject.layer);
                var drv = NewGO("cockpit_throttle_drive", frame.transform, thT0.position, root.transform.rotation, thT0.gameObject.layer);
                thT0.SetParent(drv.transform, true); thDrv = drv.transform;
            }
            else thDrv = DrivenFrame(Find("cockpit_throttle"));
            float thRange = StockThrottle ? (float)thC["range"] : 30f;
            {
                var thT = Find("cockpit_throttle"); var q0 = root.transform.InverseTransformPoint(thT.position);
                var lp0 = thDrv.localPosition; thDrv.localPosition = new Vector3(0f, 0f, thRange);
                var q1 = root.transform.InverseTransformPoint(thT.position); thDrv.localPosition = lp0;
                if (thMotion && q1.z < q0.z) thRange = -thRange;
                L($"throttle: stock {(string)thC["stock_mesh"]}, {(thMotion ? "motion" : "rotation")} range {thRange}: full throttle moves it {(q1 - q0).ToString("F3")} in the aircraft frame{(q1.z < q0.z ? " (flipped)" : "")}, idle local {lp0.ToString("F3")}");
            }
            var th = NewElem(ck, "throttles"); S(th, "rotation", !thMotion); S(th, "motion", thMotion); S(th, "transform", thDrv); S(th, "range", thRange);
            SetSeq(ck, "throttles", new[] { th });
            L($"cockpit: stock stick (Joystick {contract["controls"]["stick"]["range"]}), stock throttle (rotation 30), {cockpitR.Count} cockpit-layer copies; no pedals");

            // target camera + laser designator in the sensor ball (moves with the ball), rear view from the tail
            var nose = parts["fus_engine"];
            var ball = Find("sensor_ball"); var mount = Find("sensor_mount");
            float br = (float)contract["sensor"]["radius"];
            var tcF = NewGO("targetCamForward", mount, mount.position + Vector3.down * (br + 0.02f), Quaternion.identity, 0);
            var tcR = NewGO("targetCamRear", parts["fus_rear"].transform, new Vector3(0, 0.30f, Find("rudder").position.z - 0.6f), Quaternion.LookRotation(Vector3.back), 0);
            var tcL = NewGO("landingCamPoint", nose.transform, mount.position + Vector3.down * (br + 0.05f), Quaternion.LookRotation(new Vector3(0, -0.3f, 1f)), 0);
            var tc = CloneComp(TplComp<TargetCam>("COIN:nose"), nose.gameObject);
            S(tc, "currentMount", tcF.transform); S(tc, "camMountForward", tcF.transform); S(tc, "camMountRear", tcR.transform); S(tc, "camMountLanding", tcL.transform);
            S(tc, "attachedPart", nose); S(tc, "targetScreenRenderer", tacR);
            var ld = CloneComp(TplComp<LaserDesignator>("COIN:nose"), nose.gameObject);
            S(ld, "unitPart", nose); S(ld, "aircraft", aircraft);

            aircraft.cockpitViewPoint = helmetCam;
            aircraft.pilots = crew.ToArray();
            aircraft.targetCam = tc;
            aircraft.weaponManager = weaponManager;
            aircraft.cockpit = cp;
            S(aircraft, "controlsFilter", controlsFilter);
            S(aircraft, "groundEquipment", new GameObject[0]);
        }

        // ------------------------------------------------------------------ root systems
        static void RootSystems(List<LandingGear> gears)
        {
            var coin = tpl["COIN"];
            var ball = Find("sensor_ball"); var mount = Find("sensor_mount");
            var detector = CloneComp(coin.GetComponent<TargetDetector>(), root);
            S(detector, "attachedUnit", aircraft); S(detector, "scanner", SensorBall ? ball : parts["FD32"].transform);
            aircraft.EOTS = detector;
            if (CapacitorPowerSupply)
            {
                var cap = CloneComp(TplAudio("COIN:COIN", "capacitor"), root);
                var power = CloneComp(coin.GetComponent<PowerSupply>(), root);
                S(power, "powerSources", new[] { parts["fus_engine"].gameObject });
                S(power, "source", cap); S(power, "aircraft", aircraft);
                S(aircraft, "powerSupply", power);
            }
            else S(aircraft, "powerSupply", null);
            if (WingRadar)
            {
                // stock Radar (VT-7 Vagrant: radarCone 30, maxRange 35 km, minSignal 0.7); scanner at the upper centre-section leading edge (the four LE
                // arrays are drawn in the livery; every stock aircraft has one Radar)
                var rsrc = tpl["VTOLTrainer1"].GetComponentInChildren<Radar>(true);
                var radarGO = NewGO("radar_arrays", parts["wing_upper_C"].transform, parts["wing_upper_C"].transform.position + new Vector3(0, 0, 0.75f), Quaternion.identity);
                var radar = CloneComp(rsrc, radarGO);
                S(radar, "attachedUnit", aircraft); S(radar, "scanner", radarGO.transform);
                try { S(aircraft, "radar", radar); } catch (Exception e) { L("WARN aircraft.radar: " + e.Message); }
                L($"radar: stock Radar (VTOLTrainer1) maxRange {radar.RadarParameters.maxRange} cone {G(radar, "radarCone")} power {G(radar, "powerDraw")}");
            }
            CloneComp(coin.GetComponent<NuclearOption.NetworkTransforms.AircraftNetworkTransform>(), root);
            var ft = CloneComp(coin.GetComponent<FuelTank>(), parts["fus_engine"].gameObject);
            S(ft, "fuelCapacity", FuelKg); S(ft, "fuelMass", FuelKg); S(ft, "part", parts["fus_engine"]); SetSeq(ft, "connectedTanks", new object[0]);
            var nl = CloneComp(coin.GetComponent<NavLights>(), root);
            var entries = new List<object>();
            void Nav(string name, AeroPart part, Vector3 pos, string litMat, Color col, float outboard)
            {
                var g = NewGO(name + "_lens", part.transform, pos, Quaternion.identity);
                g.AddComponent<MeshFilter>().sharedMesh = OctaMesh(name, 0.035f);
                var r = g.AddComponent<MeshRenderer>(); r.sharedMaterial = mats["navlight"];
                var lg = NewGO(name + "_light", g.transform, pos + new Vector3(outboard * NavLightOutboard, 0f, 0f), Quaternion.identity);
                var li = lg.AddComponent<Light>(); li.type = LightType.Point; li.color = col; li.range = NavLightRange; li.intensity = 2f; lg.SetActive(false);
                var e = NewElem(nl, "navLights");
                S(e, "renderer", r); S(e, "objects", new[] { lg }); S(e, "litMaterial", Asset<Material>($"Material/{litMat}_PLACEHOLDER.mat"));
                S(e, "part", part); S(e, "gear", null);
                var fcs = Fld(e.GetType(), "controlState"); fcs.SetValue(e, Enum.ToObject(fcs.FieldType, 1));
                entries.Add(e);
            }
            if (!NoNavLights)
            {
                Nav("navLight_L", parts["wing_upper_L"], Find("navlight_L").position, "navlight_L", Color.red, -1f);
                Nav("navLight_R", parts["wing_upper_R"], Find("navlight_R").position, "navlight_R", Color.green, 1f);
            }
            // round 3: green gear-down strips (GA-25X 0.3.0 pattern): our strip meshes in the stock light_green_off, whole-renderer swap to the stock
            // slimelight_on while the gear is down (NavLights entry, controlState Auto, gear = null)
            var slimeOn = Asset<Material>("Material/slimelight_on_PLACEHOLDER.mat");
            foreach (var nm in contract["lights"]["gear"].Select(x => (string)x))
            {
                var t = TryFind(nm); var r = t != null ? t.GetComponent<MeshRenderer>() : null;
                if (r == null) { L($"WARN gear light {nm} missing"); continue; }
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                var e = NewElem(nl, "navLights");
                S(e, "renderer", r); S(e, "objects", new GameObject[0]); S(e, "litMaterial", slimeOn);
                AeroPart own = null; for (var x = t; x != null && own == null; x = x.parent) own = x.GetComponent<AeroPart>();
                S(e, "part", own != null ? own : parts["FD32"]); S(e, "gear", null);   // 1.8.0: the part the strip sits on (wing / fin / rear fuselage strips)
                var fcs = Fld(e.GetType(), "controlState"); fcs.SetValue(e, Enum.ToObject(fcs.FieldType, 1));
                entries.Add(e);
            }
            L($"gear lights: {contract["lights"]["gear"].Count()} slimelight strips (NavLights Auto, slimelight_on)");
            if (GearLight1914.Enabled)
            {   // 1.9.14: gear light = a modelled lamp clamped to each main strut (tail-wheel aircraft: aimed 5 deg down at the ground attitude)
                float gp = GearLight1914.GroundPitch(root.transform, new[] { gears[0], gears[1] }, gears[2]);
                foreach (var (mg, sd) in new[] { (gears[0], "L"), (gears[1], "R") })
                {
                    var b = GearLight1914.Make(DNS, mg, Find($"gear_main_{sd}_strut"), root.transform, "main_" + sd, gp, mats["metal_dark"], mats["navlight"], generatedMeshes);
                    var e1 = NewElem(nl, "navLights"); var e2 = NewElem(nl, "navLights");
                    GearLight1914.Entries(e1, e2, b, (UnitPart)G(mg, "attachedPart"), mg, DNS);
                    entries.Add(e1); entries.Add(e2);
                    L($"gear light: lamp {b.lamp.name} on {b.lamp.transform.parent.name}, lens at {b.lensCentre.ToString("F3")}, ground pitch {gp:F1}, aim {b.pitchDown:F1} deg down");
                }
            }
            SetSeq(nl, "navLights", entries);
            S(nl, "aircraft", aircraft);
            if (KeepFlareEjector)
            {
                var fe = CloneComp(coin.GetComponent<FlareEjector>(), root);
                S(fe, "ammo", Flares);
                var pts = new List<object>();
                foreach (var nm in new[] { "flare_L", "flare_R" })
                {
                    var part = parts["fus_rear"];
                    var g = NewGO("flareEjector_" + nm.Substring(6), part.transform, Find(nm).position, Quaternion.LookRotation(Vector3.down));
                    var a = CloneComp(TplAudio("COIN:flareEjector_L", "flare"), g);
                    var ep = NewElem(fe, "ejectionPoints");
                    S(ep, "part", part); S(ep, "transform", g.transform); S(ep, "sound", a);
                    pts.Add(ep);
                }
                SetSeq(fe, "ejectionPoints", pts);
                foreach (var f in new[] { "doors", "flareDoors" }) { try { SetSeq(fe, f, new object[0]); } catch { } }
                S(fe, "aircraft", aircraft);
            }
            if (SensorBall && SensorWithGearUp)
            {
                // round 9 (user: the ball came out for landing and went in for flight): an arm pivoted SensorArm m ahead of the ball, turned by the
                // left main LandingGear's movingParts (GearPart.foldAngles x foldAmount, LandingGear.cs 460-476): gear DOWN (foldAmount 0) = stowed,
                // gear UP (1) = out. The turn is the one that lowers the ball by the contract travel.
                var sp = contract["sensor"];
                var st0 = J3(sp["stowed"]); var dp0 = J3(sp["deployed"]);
                float travel = (dp0 - st0).magnitude; float ang = 2f * Mathf.Asin(Mathf.Clamp01(travel / (2f * SensorArm))) * Mathf.Rad2Deg;
                var arm = NewGO("sensor_arm", mount.parent, mount.position + root.transform.forward * SensorArm, root.transform.rotation);
                mount.SetParent(arm.transform, true);
                var y0 = mount.position.y; var r0 = arm.transform.localRotation;
                arm.transform.localEulerAngles = new Vector3(ang, 0f, 0f); bool down = mount.position.y < y0; arm.transform.localRotation = r0;
                var fold = new Vector3(down ? ang : -ang, 0f, 0f);
                var lgL = root.GetComponentsInChildren<LandingGear>(true).First(g => g.name.Contains("gear_main_L") && !g.name.EndsWith(GripGear.Suffix));
                var gp = new GearPart { transform = arm.transform, target = null, foldAngles = fold };
                var cur = ((GearPart[])G(lgL, "movingParts")) ?? new GearPart[0];
                S(lgL, "movingParts", cur.Concat(new[] { gp }).ToArray());
                L($"sensor ball: arm {SensorArm} m ahead, {fold.x:F1} deg with the left main gear's fold (gear up = out, travel {travel:F3} m); EOTS scanner = {ball.name}");
            }
            else if (SensorBall)
            {
                var sp = contract["sensor"];
                var dWorld = new Vector3((float)sp["deployed"][0], (float)sp["deployed"][1], (float)sp["deployed"][2]) - new Vector3((float)sp["stowed"][0], (float)sp["stowed"][1], (float)sp["stowed"][2]);
                var mp = NewElem(TplComp<HighLiftDevice>("COIN:flap_L"), "movingParts");
                S(mp, "move", true); S(mp, "rotate", false); S(mp, "transform", mount);
                S(mp, "positionRetracted", mount.localPosition); S(mp, "positionDeployed", mount.localPosition + mount.parent.InverseTransformVector(dWorld));
                S(mp, "anglesRetracted", Vector3.zero); S(mp, "anglesDeployed", Vector3.zero);
                var h = CloneComp(TplComp<HighLiftDevice>("COIN:flap_L"), parts["fus_engine"].gameObject);
                S(h, "aeroPart", parts["fus_engine"]); S(h, "swingWingController", null);
                S(h, "speedDeployed", SensorDownSpeed); S(h, "speedRetracted", SensorUpSpeed);
                S(h, "alphaMin", 0f); S(h, "alphaFactor", 0f); S(h, "deployedArea", 0f);
                var arr = Array.CreateInstance(mp.GetType(), 1); arr.SetValue(mp, 0); S(h, "movingParts", arr);
            }
            var sparks = CopyParticle(TplFind("COIN:contactSparks").GetComponent<ParticleSystem>(), root.transform, root.transform.position, "contactSparks");
            S(aircraft, "sparksEmitter", sparks);
            var sgp = root.AddComponent<SetGlobalParticles>();
            S(sgp, "systems", ourParticles.Where(q => q != null).ToList());   // round 3: dropped smoke systems are destroyed
            S(aircraft, "dopplerSounds", new List<AudioSource> { parts["fus_engine"].GetComponent<AudioSource>(), parts["prop"].GetComponent<AudioSource>() });
            aircraft.maxRadius = 5.6f;
            aircraft.obstacleTop = 1.4f;
            AirbrakeComponent1912();
        }

        static void FlyByWire(LandingGear mainGear)
        {
            var so = new SerializedObject(controlsFilter);
            void F(string p, float v) { var sp = so.FindProperty("flyByWire." + p); if (sp == null) throw new Exception("no flyByWire." + p); sp.floatValue = v; }
            F("gLimitPositive", FBWgLimit); F("cornerSpeed", FBWCorner); F("postStallManeuverSpeed", 0f); F("maxRollSpeed", 70f);
            F("takeoffSpeed", 26f); F("pidTransitionSpeed", 55f); F("alphaLimiter", AlphaLimiter);
            int n = 0; var it = so.GetIterator();
            while (it.Next(true)) if (it.name == "noseGear" && it.propertyType == SerializedPropertyType.ObjectReference) { it.objectReferenceValue = mainGear; n++; }
            so.ApplyModifiedPropertiesWithoutUndo();
            var ap = parts["FD32"].GetComponent<AutopilotPlane>();
            var so2 = new SerializedObject(ap);
            var rs = so2.FindProperty("forwardFlightController.referenceAirspeed"); if (rs != null) rs.floatValue = 70f;
            var pi = so2.FindProperty("preventInvertedFlight"); if (pi != null) pi.boolValue = false;
            so2.ApplyModifiedPropertiesWithoutUndo();
            L($"FBW: g {FBWgLimit}, corner {FBWCorner}, alpha limiter {AlphaLimiter}, takeoff 26; noseGear refs -> {mainGear.name} ({n})");
        }

        // =================================================================== assets
        static (float t, float v)[] WingCL => new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.95f), (-0.36f, -0.75f), (-0.2945f, -0.95f), (0f, 0.18f), (0.1473f, 0.92f),
            (0.2454f, 1.36f), (0.2945f, 1.38f), (0.3436f, 1.34f), (0.4418f, 1.24f), (0.6f, 1.10f), (0.785f, 0.95f), (1.571f, 0f), (3.142f, 0f) };
        // 1.4.2: post-stall softened (was 1.20 at 19.7 / 1.05 at 25.3 deg: a 13 % lift drop 3 deg past CLmax made turns snap; the Fury / Nimrod
        // were known for a gentle, forgiving stall). Aileron airfoil: the game rotates the aileron part's lift normal by the full deflection,
        // so a down aileron at 18 deg on a wing at 12 deg AoA saw 31.5 deg on the wing curve, made LESS lift than neutral and reversed the roll.
        // A deflected aileron is a plain flap on the wing (more camber: CLmax rises, ~+0.5 at 18 deg), so its own curve keeps rising past the
        // plain wing's stall to 1.85 at 30 deg (wing 12 + aileron 18) and only then falls; its drag is a flap's, not a stalled wing's.
        static (float t, float v)[] AileronCL => new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -1.10f), (-0.62f, -1.30f), (-0.52f, -1.35f), (-0.40f, -1.25f), (-0.2945f, -0.95f), (0f, 0.18f), (0.1473f, 0.92f),
            (0.2454f, 1.36f), (0.2945f, 1.45f), (0.40f, 1.70f), (0.52f, 1.85f), (0.62f, 1.80f), (0.785f, 1.40f), (1.571f, 0f), (3.142f, 0f) };
        static readonly (float, float)[] AileronCD = { (0f, 0.011f), (0.2f, 0.05f), (0.35f, 0.10f), (0.5f, 0.16f), (0.62f, 0.22f), (0.785f, 0.40f), (1.51f, 1.7f), (3.14159f, 0f) };
        static AnimationCurve WingDragN() => DragCurve(new[] { (0f, 0.011f), (0.06f, 0.026f), (0.1f, 0.045f), (0.2f, 0.10f), (0.28f, 0.16f), (0.35f, 0.28f), (0.5f, 0.52f), (1.51f, 1.7f), (3.14159f, 0f) });
        static AnimationCurve DragCurve((float, float)[] pts)
        {   // tools/flightmodel/fd32_fm.py WING_CD / AIL_CD (thick biplane section; struts and wires are in the parts' dragArea)
            var keys = new List<Keyframe>();
            foreach (var (t, v) in pts.Reverse()) if (t > 0f) keys.Add(new Keyframe(-t, v));
            foreach (var (t, v) in pts) keys.Add(new Keyframe(t, v));
            var c = new AnimationCurve(keys.ToArray());
            for (int i = 0; i < c.length; i++) c.SmoothTangents(i, 0f);
            return c;
        }

        static GameObject SaveEverything()
        {
            var bank = Folder + "/Generated/FD32_meshes.asset";
            AssetDatabase.CreateAsset(generatedMeshes[0], bank);
            foreach (var m in generatedMeshes.Skip(1)) AssetDatabase.AddObjectToAsset(m, bank);
            if (hookGO != null)
            {
                var hp = PrefabUtility.SaveAsPrefabAsset(hookGO, Folder + "/FD32_tailhook_mount.prefab");
                Object.DestroyImmediate(hookGO); hookGO = null;
                hookMount.prefab = hp; EditorUtility.SetDirty(hookMount);
            }

            var coinParams = Asset<AircraftParameters>("MonoBehaviour/COINParameters_PLACEHOLDER.asset");
            var drag = coinParams.airfoils[0].dragCoef;
            var wing = new Airfoil { name = "FD32_wing", liftCoef = Mirror(WingCL), dragCoef = WingDragN() };
            var tail = new Airfoil { name = "FD32_tail", liftCoef = Mirror(new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.9f), (-0.45f, -0.8f), (-0.3f, -1.1f), (0f, 0f), (0.3f, 1.1f), (0.45f, 0.8f), (0.785f, 0.9f), (1.571f, 0f), (3.142f, 0f) }), dragCoef = new AnimationCurve(drag.keys) };

            // liveries: BOTH factions always (user rule); BDF Matte Gray is offered to both, PALA lists PALA Desert first (PALA mostly flies desert)
            var facBDF = coinParams.liveries[0].faction; var facPALA = coinParams.liveries[2].faction;
            var livs = new List<AircraftParameters.Livery>(); var livGuid = new Dictionary<string, string>();
            foreach (var (file, label, fac, _) in Liveries)
            {
                var ld = ScriptableObject.CreateInstance<LiveryData>();
                var (gloss, cols) = LiveryJson(file);
                ld.Texture = tex[file]; ld.Glossiness = gloss; ld.Colors = cols;
                var p = $"{Folder}/Liveries/{file}.asset";
                AssetDatabase.CreateAsset(ld, p);
                livGuid[file] = AssetDatabase.AssetPathToGUID(p);
            }
            foreach (var side in new[] { "BDF", "PALA" })
            {
                var own = Liveries.Where(x => x.faction == side && !IsNaval1912(x.file)).ToList();   // 1.9.12: the 1.9.11 loop over the 1.9.11 entries: same list, same indexes
                var shared = new List<(string file, string label, string faction, bool both)>();   // round 3 (user): each faction only its own liveries
                foreach (var (file, label, fac, _) in own.Concat(shared))
                    livs.Add(new AircraftParameters.Livery { name = label, faction = side == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(livGuid[file]) });
            }
            foreach (var side in new[] { "BDF", "PALA" })   // 1.9.12: naval liveries appended at the END (BDF then PALA)
                foreach (var (file, label, fac, _) in Liveries.Where(x => x.faction == side && IsNaval1912(x.file)))
                    livs.Add(new AircraftParameters.Livery { name = label, faction = side == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(livGuid[file]) });

            var prm = Object.Instantiate(coinParams);
            prm.HUDExtras = StockHUDExtras ? Asset<GameObject>("GameObject/Multirole1_HUDExtras_PLACEHOLDER.prefab") : null;
            prm.name = "FD32_Parameters";
            BuildDiagramSprites();
            prm.StatusDisplay = BuildStatusDisplayPrefab();
            prm.aircraftName = DisplayName; prm.rankRequired = 0;
            var ail = new Airfoil { name = "FD32_flaperon", liftCoef = Mirror(AileronCL), dragCoef = DragCurve(AileronCD) };
            prm.airfoils = new[] { wing, tail, ail };   // index 2 = ailerons + flaperons
            prm.liveries = livs;
            int nSets = sets.Count;
            NuclearOption.SavedMission.Loadout LO(string inner, string outer)
            {
                var w = new List<WeaponMount>();
                foreach (var s in sets) w.Add(s.name == "Guns" ? ammoVickers : s.name == "Tail Hook" ? hookMount : s.name == "Inner Pylons" ? (inner != null ? Mount(inner) : null) : s.name == "Outer Pylons" ? (outer != null ? Mount(outer) : null) : null);
                return new NuclearOption.SavedMission.Loadout { weapons = w };
            }
            prm.loadouts = new List<NuclearOption.SavedMission.Loadout> { new NuclearOption.SavedMission.Loadout { weapons = Enumerable.Repeat<WeaponMount>(null, nSets).ToList() }, LO("IRMS1_single", "IRMS1_double") };
            prm.StandardLoadouts = new[] {
                new StandardLoadout { Name = "Fleet defence (IRM-S2 x2, IRM-S1 x4)", loadout = LO("AAM3_single", "IRMS1_double"), FuelRatio = 0.8f },
                new StandardLoadout { Name = "Helicopter hunter (IRM-S1 x4, AGR-18 x14)", loadout = LO("RocketPod1_single", "IRMS1_double"), FuelRatio = 0.8f },
                new StandardLoadout { Name = "Strike (PAB-80LR x2, AGR-18 x14)", loadout = LO("bomb_glide1_single", "RocketPod1_single"), FuelRatio = 0.8f },
                new StandardLoadout { Name = "Picket (IRM-S1 x2)", loadout = LO(null, "IRMS1_single"), FuelRatio = 1.0f } };
            prm.DefaultFuelLevel = 0.8f;
            prm.aircraftGLimit = 9.0f; prm.PIDReferenceAirspeed = 70f; prm.maxSpeed = 105f; prm.takeoffSpeed = 28f; prm.takeoffDistance = 120f;
            prm.turningRadius = 300f; prm.cornerSpeed = FBWCorner; prm.approachSpeed = 34f; prm.landingSpeed = 29f; prm.shortLandingSpeed = 27f;
            prm.cruiseThrottle = 0.70f; prm.minimumRadarAlt = 60f; prm.groundTurningRadius = 8f;
            AssetDatabase.CreateAsset(prm, Folder + "/FD32_Parameters.asset");

            float total = parts.Values.Sum(p => p.mass);
            var def = Object.Instantiate(Asset<AircraftDefinition>("MonoBehaviour/CI-22_PLACEHOLDER.asset"));
            def.name = "FD32";
            def.jsonKey = JsonKey; def.WorkshopTag = DisplayName; def.unitName = DisplayName; def.code = "FD-32"; def.bogeyName = "";
            def.description = "Fleet defence fighter rebuilt on the Nimrod airframe with composite skins, fly-by-wire and a quiet electric drive with a " +
                "boost setting. Carries light air-to-air missiles, guided rockets and small guided bombs on four pylons. Slow but very agile, with the " +
                "lowest heat signature of any aircraft; flies from short strips, shelters and every carrier deck.";
            def.length = 8.4f; def.width = 10.3f; def.height = 3.0f; ((UnitDefinition)def).mass = total;
            def.value = ValueM; def.radarSize = RadarSize; def.visibleRange = 3200f; def.manpower = 1;
            def.roleIdentity.antiAir = 0.6f; def.roleIdentity.antiSurface = 0.4f;
            float contactH = (float)contract["level_wheel_contact_height"];
            def.spawnOffset = new Vector3(0f, contactH + SpawnLift, LiftSpawnFix1911 ? SpawnForward1911 : 0f);   // 1.9.11: z forward of the hangar's spawn point (was 0)
            def.restRotation = new Vector3(-14f, 0f, 0f);
            def.aircraftParameters = prm;
            def.mapIcon = mapIconSprite; def.mapIconSize = 0.85f; def.mapOrient = true;
            def.aircraftInfo = new AircraftInfo { emptyWeight = 1500f, maxSpeed = 380f, stallSpeed = 95f, maneuverability = 9f, maxWeight = 2600f };
            def.unitPrefab = null;
            AssetDatabase.CreateAsset(def, Folder + "/FD32.asset");
            foreach (var u in root.GetComponentsInChildren<Unit>(true)) u.definition = def;
            root.GetComponent<Rigidbody>().mass = total;
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, Folder + "/FD32.prefab");
            def.unitPrefab = prefab;
            EditorUtility.SetDirty(def);

            var op = ScriptableObject.CreateInstance<Blueprinter.OpAddAircraftToHangars>();
            op.aircraftJsonKey = JsonKey;
            foreach (var (unit, names) in HangarTargets())
                op.hangars.Add(new Blueprinter.OpAddAircraftToHangars.HangarTarget { hangarUnitJsonKey = unit, hangarNames = names.ToList() });
            AssetDatabase.CreateAsset(op, Folder + "/OpAddAircraftToHangars.asset");
            AssetDatabase.SaveAssets();
            L($"saved prefab, definition (parts {total} kg), {livs.Count} livery entries ({string.Join(", ", livs.Select(l => l.name + "/" + (l.faction == facBDF ? "BDF" : "PALA")))}), {generatedMeshes.Count} meshes, hangar targets {op.hangars.Sum(h => h.hangarNames.Count)}");
            return prefab;
        }

        // docs/fd32_design.md 4: every hangar that offers a fixed-wing aircraft; helicopter pads (hangar_F, Destroyer, Frigate, Helipad) excluded
        static IEnumerable<(string, string[])> HangarTargets()
        {
            yield return ("hangar_med", new[] { "hangar_med" });
            yield return ("revetment1", new[] { "revetment1" });
            if (!AllHangarTypes) yield break;
            yield return ("shelter1", new[] { "shelter1" });
            yield return ("SmallCarrier1", new[] { "hangar" });
            yield return ("AssaultCarrier1", new[] { "hangar_R1", "hangar_R2", "hangar_R3", "hangar_M" });
            yield return ("FleetCarrier1", HyperionR2Only ? new[] { "hangar_R2" } : new[] { "hangar_R1", "hangar_R2", "hangar_R3" });
        }

        static (float, LiveryData.TextureColor[]) LiveryJson(string file)
        {
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(Path.Combine(RepoTextures, "fd32_liveries.json")));
            foreach (var kv in jo)
            {
                var e = (Newtonsoft.Json.Linq.JObject)kv.Value;
                if (Path.GetFileNameWithoutExtension((string)e["texture"]) != file) continue;
                var cols = new List<LiveryData.TextureColor>();
                foreach (var c in (Newtonsoft.Json.Linq.JArray)e["colors"])
                {
                    var h = ((string)c["color"]).TrimStart('#'); if (h.Length == 6) h += "FF";
                    byte B(int o) => Convert.ToByte(h.Substring(o, 2), 16);
                    cols.Add(new LiveryData.TextureColor { Color = new Color32(B(0), B(2), B(4), B(6)), Count = (int)c["count"] });
                }
                return ((float)e["glossiness"], cols.ToArray());
            }
            return (0.3f, new LiveryData.TextureColor[0]);
        }

        static AnimationCurve Mirror((float t, float v)[] phys)
        {
            var keys = phys.Select(k => (t: -k.t, v: -k.v)).OrderBy(k => k.t).GroupBy(k => k.t).Select(g => g.First()).Select(k => new Keyframe(k.t, k.v)).ToArray();
            var c = new AnimationCurve(keys);
            for (int i = 0; i < c.length; i++) AnimationUtility.SetKeyLeftTangentMode(c, i, AnimationUtility.TangentMode.Linear);
            for (int i = 0; i < c.length; i++) AnimationUtility.SetKeyRightTangentMode(c, i, AnimationUtility.TangentMode.Linear);
            return c;
        }


        // =================================================================== offline check
        static bool RunCheck(GameObject prefab)
        {
            var rows = new List<(string name, bool ok, string detail)>();
            void R(string n, bool ok, string d) => rows.Add((n, ok, d));
            var inst = (GameObject)Object.Instantiate(prefab);
            try
            {
                {   // 1.8.16 livery-atlas guard (AtlasGuard1816.cs = blender/atlas_guard.py): the skin / livery / damage textures were painted on THIS UV0 atlas
                    // 1.9.12: the airbrake panels are not atlas parts (they borrow fus_rear's texels; own row below): the guard sees the model without them
                    var agInst = inst;
                    if (AirbrakePanels1912)
                    {
                        agInst = (GameObject)Object.Instantiate(inst);
                        foreach (var zt in agInst.GetComponentsInChildren<Transform>(true).Where(t => t.name.StartsWith("airbrake_") && t.name.EndsWith("_hinge")).ToList()) Object.DestroyImmediate(zt.gameObject);
                    }
                    var ag = AtlasGuard1816.Check(agInst, mats["paint"], Path.Combine(RepoTextures, "fd32_atlas_manifest.json"), null);
                    if (agInst != inst) Object.DestroyImmediate(agInst);   // 1.9.12: the copy without the airbrake panels
                    R("1.8.16 livery atlas: UV0 of the paint meshes == the texture manifest (textures painted on this atlas, files unchanged)", ag.Item1, ag.Item2);
                }
                var ac = inst.GetComponent<Aircraft>();
                var aps = inst.GetComponentsInChildren<AeroPart>(true);
                Transform T(string n) => inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == n);
                AeroPart P(string n) => aps.FirstOrDefault(p => p.name == n);
                // propulsion
                var props = inst.GetComponentsInChildren<ConstantSpeedProp>(true);
                var tr = props.Length == 1 ? (Transmission)G(props[0], "transmission") : null;
                var te = tr != null ? tr.GetComponent<TurbineEngine>() : null;
                R("one ConstantSpeedProp, 4 blades, own Transmission + TurbineEngine", props.Length == 1 && ((IList)G(props[0], "blades")).Count == 4 && te != null,
                    props.Length == 1 ? $"blades {((IList)G(props[0], "blades")).Count}, engine {(te ? te.maxPower : 0)} W, rpmLimit {G(props[0], "rpmLimit")}" : $"{props.Length} props");
                R($"engine 480 kW thrust power (600 kW motor), prop rpm 1640, blade efficiency {BladeEfficiency}, blade length 1.45-1.55 m", te != null && Mathf.Abs(te.maxPower - EnginePower) < 1 && Mathf.Abs((float)G(props[0], "rpmLimit") - PropRpm) < 1 && (float)G(props[0], "bladeLength") > 1.45f && (float)G(props[0], "bladeLength") < 1.55f
                    && Mathf.Abs((float)G(props[0], "bladeEfficiency") - BladeEfficiency) < 1e-4f, props.Length == 1 ? $"bladeLength {G(props[0], "bladeLength")}" : "");
                R($"lowest IR: TurbineEngine IRMin {IRMin} / IRMax {IRMax} (stock minimum 1 / 1.6); fuel burn {FuelBurn} kg/s, fuel {FuelKg} kg", te != null && Mathf.Abs((float)G(te, "IRMin") - IRMin) < 1e-4f && Mathf.Abs((float)G(te, "IRMax") - IRMax) < 1e-4f
                    && Mathf.Abs((float)G(te, "maxFuelConsumption") - FuelBurn) < 1e-5f && inst.GetComponentsInChildren<FuelTank>(true).Sum(f => f.GetCapacity()) == FuelKg, "");
                var jns = inst.GetComponentsInChildren<JetNozzle>(true); var tjs = inst.GetComponentsInChildren<Turbojet>(true);
                R($"BOOST: one ~0 N Turbojet + JetNozzle afterburner {BoostThrust} N from throttle 0.9 on fus_engine; HUD extras Multirole1 (BOOST bar)",
                    !HybridBoost || (tjs.Length == 1 && jns.Length == 1 && ((Array)G(jns[0], "afterburners")).Length == 1 && Mathf.Abs((float)G(((Array)G(jns[0], "afterburners")).GetValue(0), "thrust") - BoostThrust) < 1f
                        && (G(jns[0], "part") as UnitPart)?.name == "fus_engine" && tjs[0].maxThrust <= 1f), $"{tjs.Length} turbojet, {jns.Length} nozzle");
                R("prop strike detector: trigger on layer 15", props.Length == 1 && G(props[0], "propStrikeDetector") is PropStrikeDetector d && d.gameObject.layer == 15 && ((Collider)G(props[0], "propDiscCollider")).isTrigger, "");
                // guns
                var guns = inst.GetComponentsInChildren<Gun>(true);
                var hub = T("prop_hub");
                var gun = guns.FirstOrDefault(g => g.name == "guns_127");
                var muz = gun != null ? (Transform[])G(gun, "muzzles") : new Transform[0];
                R($"12.7 mm: one Gun, 2 muzzles, {GunFireRate} rpm, {GunRounds} rounds per gun, stock info 12.7mm Machine Gun", guns.Length == 1 && gun != null && muz.Length == 2 && Mathf.Abs((float)G(gun, "fireRate") - GunFireRate) < 1 && (int)G(gun, "magazineCapacity") == GunRounds && gun.info != null && gun.info.name.Contains("12.7"),
                    gun != null ? $"fireRate {G(gun, "fireRate")}, magazine {G(gun, "magazineCapacity")}, info {gun.info?.name}" : "missing");
                var mps = gun != null ? ((ParticleSystem[])G(gun, "muzzleParticles") ?? new ParticleSystem[0]) : new ParticleSystem[0];
                var smokeL = inst.GetComponentsInChildren<ParticleSystemRenderer>(true).Where(r => r.name.StartsWith("flash_gun_") && r.sharedMaterials.Any(m => m != null && m.name.ToLowerInvariant().Contains("smoke"))).ToList();
                R("12.7 mm muzzle: flash only, NO smoke system (user: the smoke blinded the pilot); flash particles halved", gun != null && mps.Length == 2 && mps.All(q => q != null && q.name.Contains("muzzleFlash")) && smokeL.Count == 0,
                    string.Join(", ", mps.Where(q => q != null).Select(q => $"{q.name} size x{q.main.startSizeMultiplier:F2}")) + $"; smoke renderers {smokeL.Count}");
                float propZ = hub != null ? hub.position.z : 0f;
                R("synchroniser: bullet origins >= 0.12 m ahead of the prop plane, outside the spinner", muz.Length == 2 && muz.All(m => m.position.z - propZ >= 0.12f && new Vector2(m.position.x, m.position.y - hub.position.y).magnitude > 0.3f),
                    string.Join(" ", muz.Select(m => $"{m.name} dz {m.position.z - propZ:F3} r {new Vector2(m.position.x, m.position.y - hub.position.y).magnitude:F3}")));
                var wm = inst.GetComponentInChildren<WeaponManager>(true);
                R("hardpoint sets: Guns, Inner Pylons, Outer Pylons, Tail Hook", wm.hardpointSets.Select(s => s.name).SequenceEqual(new[] { "Guns", "Inner Pylons", "Outer Pylons", "Tail Hook" }),
                    string.Join(" | ", wm.hardpointSets.Select(s => $"{s.name}: {string.Join(",", s.weaponOptions.Where(o => o != null).Select(o => o.jsonKey))}")));
                var inner = wm.hardpointSets.FirstOrDefault(s => s.name == "Inner Pylons"); var outer = wm.hardpointSets.FirstOrDefault(s => s.name == "Outer Pylons");
                R("pylon stores = the checked lists (AGR-24 x4 inner only, IRM-S1 x2 outer only), stock mounts, 2 hardpoints each on the lower wings",
                    inner != null && outer != null && inner.weaponOptions.Where(o => o != null).Select(o => o.jsonKey).SequenceEqual(InnerStores) && outer.weaponOptions.Where(o => o != null).Select(o => o.jsonKey).SequenceEqual(OuterStores)
                    && inner.hardpoints.Concat(outer.hardpoints).All(h => h.part.name.StartsWith("wing_lower_")) && inner.hardpoints.Count == 2 && outer.hardpoints.Count == 2, "");
                float R0 = (float)contract["prop"]["radius"];
                R("every pylon hardpoint outside the prop-disc radius + 0.25 m (store launch paths clear the disc; Blender store-box check has the per-store margins)",
                    inner != null && outer != null && inner.hardpoints.Concat(outer.hardpoints).All(h => Mathf.Abs(h.transform.position.x) > R0 + 0.25f),
                    inner != null ? string.Join(" ", inner.hardpoints.Concat(outer.hardpoints).Select(h => h.transform.position.x.ToString("F2"))) : "");
                var ammo = wm.hardpointSets[0].weaponOptions.LastOrDefault();
                R("gun ammo mount: 400 rounds, GunAmmo, own jsonKey, no gear safety", ammo != null && ammo.ammo == GunRounds && ammo.GunAmmo && ammo.jsonKey == "FD32_ammo_127" && (!NoGearSafety || !ammo.GearSafety), ammo != null ? $"{ammo.jsonKey} ammo {ammo.ammo} mass {ammo.mass}" : "");
                var hk = wm.hardpointSets.Last().weaponOptions.LastOrDefault();
                var hookTH = hk != null && hk.prefab != null ? hk.prefab.GetComponent<TailHook>() : null;
                var hv = T("hook_visual");
                bool hvOk = hv != null && hv.GetComponent<MeshRenderer>() != null && hv.GetComponentInParent<AeroPart>() != null && hv.GetComponentInParent<AeroPart>().name == "fus_rear";
                bool fnHidden = hookTH == null || hookTH.GetComponentsInChildren<MeshRenderer>(true).Length == 0;
                R("hook (round 3): modern fal hook = the functional hook mesh, rendered (pr_hook2); no Mk I A-frame; mount.tailHook, stowed > deployed", hv == null && hookTH != null && hookTH.GetComponentsInChildren<MeshRenderer>(true).Any(r => r.sharedMaterials.Any(m => m != null && m.name.Contains("pr_hook2"))) && hk.tailHook && (float)G(hookTH, "stowedAngle") > (float)G(hookTH, "deployedAngle") && (float)G(hookTH, "deployedAngle") < -40f,
                    hookTH != null ? $"stowed {G(hookTH, "stowedAngle")} deployed {G(hookTH, "deployedAngle")}" : "missing");
                var hpT = wm.hardpointSets.Last().hardpoints.FirstOrDefault()?.transform;
                var rearC = P("fus_rear")?.GetComponent<MeshCollider>();
                var rootC = inst.GetComponent<MeshCollider>();
                bool hookIn = false; string hookD = "missing";
                if (hpT != null && rearC != null && rootC != null)
                {
                    var hkL = rearC.transform.InverseTransformPoint(hpT.position); var hkR = rootC.transform.InverseTransformPoint(hpT.position);
                    var hkB = rearC.sharedMesh.bounds; var hkO = rootC.sharedMesh.bounds;
                    hookIn = hkB.Contains(hkL) && hkL.z < hkB.max.z - 0.1f && hkL.y > hkB.min.y + 0.1f && hkL.y < hkB.max.y - 0.1f && (!hkO.Contains(hkR) || hkR.z < hkO.min.z);
                    hookD = $"hinge {hpT.position.ToString("F3")}; fus_rear bounds z {hkB.min.z:F2}..{hkB.max.z:F2} y {hkB.min.y:F2}..{hkB.max.y:F2}";
                }
                R("tail hook hinge inside the fus_rear collider bounds (>= 0.1 m in) and aft of the root collider (Linecast origin)", hookIn, hookD);
                // control surfaces + flaperons
                var css = inst.GetComponentsInChildren<ControlSurface>(true);
                R("control surfaces: 2 ailerons + 2 flaperons (roll 18), 2 elevators, rudder (+ 4 flap-mode droop surfaces)", css.Count(c => Mathf.Abs((float)G(c, "rollRange")) > 17f && !(bool)G(c, "flap")) == (Flaperons ? 4 : 2) && css.Count(c => !(bool)G(c, "flap") && Mathf.Abs((float)G(c, "pitchRange")) > 1f) == 2 && css.Any(c => Mathf.Abs((float)G(c, "yawRange")) > 1f),
                    string.Join(", ", css.Select(c => $"{c.name} r{G(c, "rollRange")} p{G(c, "pitchRange")} y{G(c, "yawRange")}")));
                var hlds = inst.GetComponentsInChildren<HighLiftDevice>(true);
                var flapCS = css.Where(c => (bool)G(c, "flap")).ToList();
                R("flaps (round 3, stock pattern): 4 ControlSurfaces in flap mode (follow the gear) on droop pivots above the 4 roll surfaces' frames (lower 18, upper 14 deg); no flap HighLiftDevice",
                    !Flaperons || (flapCS.Count == 4 && flapCS.All(c => c.name.EndsWith("_droop") && (GameObject)G(c, "visibleMesh") == c.gameObject && c.GetComponentsInChildren<Transform>(true).Any(t => t.name.EndsWith("_visible")) && (float)G(c, "pitchRange") >= 14f)
                        && !hlds.Any(h => (G(h, "aeroPart") as AeroPart)?.name.StartsWith("wing_") == true)),
                    string.Join(", ", flapCS.Select(c => $"{c.name} {G(c, "pitchRange")}")));
                R("flaperons use the aileron airfoil (index 2 of 3)", aps.Where(p => p.name.StartsWith("aileron") || p.name.StartsWith("flaperon")).All(p => System.Convert.ToInt32(G(p, "airfoil")) == 2), "");
                // gear
                var lgs = inst.GetComponentsInChildren<LandingGear>(true).Where(g => !g.name.EndsWith(GripGear.Suffix)).ToArray();   // 1.8.0: grip partners checked in their own row
                bool GearOk(LandingGear g)
                {
                    bool tail = IsTailW(g);
                    float mc = System.Convert.ToSingle(G(g, "maxCompression")), k = System.Convert.ToSingle(G(g, "springRate"));
                    return tail ? Mathf.Abs(mc - GearTailMaxComp) < 1e-3f && Mathf.Abs(k - GearTailK) < 1f : Mathf.Abs(mc - GearMainMaxComp) < 1e-3f && Mathf.Abs(k - GearMainK * (SplitMainGear ? MainBrakeShare : 1f)) < 1f;
                }
                R("gear (Mk I 1.4.2): main 200 kN/m breaks at 0.50 m (87 % travel), tail 120 kN/m at 0.27 m; 2 braked mains, steerable tail (lock -30)", lgs.Length == 3 && lgs.All(GearOk) && lgs.Count(g => (bool)G(g, "braked")) == 2 && lgs.Count(g => IsTailW(g)) == 1
                    && lgs.Where(g => IsTailW(g)).All(g => (float)G(g, "steeringLock") < 0f), string.Join(", ", lgs.Select(g => $"{g.name} k {G(g, "springRate")} max {G(g, "maxCompression")}")));
                // round 3: the gear RETRACTS (weapon safety / flaps / HUD work as on every stock aircraft): mains fold forward, tail aft, strut-rotation frame present
                bool FoldOk(LandingGear g)
                {
                    var hg = (Transform)G(g, "gearHinge"); var ax = ((Transform)G(g, "axle")).position; float f = (float)G(g, "foldDegrees");
                    var v = ax - hg.position; var vf = Quaternion.AngleAxis(f, hg.right) * v;
                    bool tail = IsTailW(g);
                    if (tail) return Mathf.Abs(f) < 1f && Mathf.Approximately(((AeroPart)G(g, "attachedPart")).dragArea, (float)G(g, "extendedDrag"));   // round 6: fixed tailwheel
                    var lp = inst.transform.InverseTransformDirection(vf); var l0 = inst.transform.InverseTransformDirection(v);
                    bool way = lp.z < l0.z - 0.6f && lp.y > l0.y + 0.4f;    // mains swing AFT and up (wheel under the lower wing)
                    var rtj = contract["retract"]; var sk = "main_stowed_wheel_" + (inst.transform.InverseTransformPoint(hg.position).x < 0 ? "L" : "R");
                    bool onTarget = rtj[sk] == null || (inst.transform.InverseTransformPoint(hg.position + vf) - J3(rtj[sk])).magnitude < 0.03f;   // round 7: the tilted-axis stowed position
                    bool parentOk = !TiltedGearAxis || hg.parent.name.EndsWith("_axisframe");
                    return Mathf.Abs(f) >= 60f && onTarget && parentOk && G(g, "strutRotationTransform") != null && way && ((AeroPart)G(g, "attachedPart")).dragArea < (float)G(g, "extendedDrag");   // retractedDrag = the part's dragArea at Awake
                }
                string Folded(LandingGear g)
                {
                    var hg = (Transform)G(g, "gearHinge"); var v = ((Transform)G(g, "axle")).position - hg.position;
                    return inst.transform.InverseTransformPoint(hg.position + Quaternion.AngleAxis((float)G(g, "foldDegrees"), hg.right) * v).ToString("F2");
                }
                R("gear (round 7, semi-retractable): mains swing AFT about the contract's TILTED axis (axis frame above the hinge) and land within 3 cm of the contract's stowed wheel position (flat under the wing root); tailwheel FIXED (fold < 1 deg, no drag change); mains extendedDrag = part (clean) drag + gear drag",
                    lgs.Length == 3 && lgs.All(FoldOk), string.Join(", ", lgs.Select(g => $"{g.name} fold {G(g, "foldDegrees")} wheel up at {Folded(g)} drag down {G(g, "extendedDrag")} / up {((AeroPart)G(g, "attachedPart")).dragArea}")));
                var nlc = inst.GetComponentInChildren<NavLights>(true);
                var strips = nlc != null ? ((IEnumerable)G(nlc, "navLights")).Cast<object>().Where(e => G(e, "renderer") is Renderer rr && rr.name.StartsWith("slimelight_")).ToList() : new List<object>();
                R("1.8.0 gear-down lights: 9 green strips (2 under the cockpit + rear fuselage sides, spine, upper wing tips, fin sides; stock light_green_off, slimelight_on while the gear is down; GA-25X pattern)", strips.Count == 9 && strips.All(e => AssetDatabase.GetAssetPath((Material)G(e, "litMaterial")).Contains("slimelight_on")
                    && ((Renderer)G(e, "renderer")).sharedMaterials.All(m => AssetDatabase.GetAssetPath(m).Contains("light_green_off"))), $"{strips.Count} strips");
                { bool glOk = GearLight1914.Check(inst, GearLight1914.Enabled ? 2 : 0, out var glMsg); R("1.9.14 gear lights: the stock CI-22 gear light (spot + glow, lights_runway) on each main leg, NavLights Never (on with the gear)", glOk, glMsg); }
                R("weapons arm with the gear up: stock pylon mounts keep GearSafety (as on every stock aircraft), the gear can retract", inner != null && inner.weaponOptions.Where(o => o != null).All(o => o.GearSafety) && lgs.Where(g => !IsTailW(g)).All(g => Mathf.Abs((float)G(g, "foldDegrees")) >= 20f), "");
                R("crash impact damage (Mk I 1.4.1): every airframe part has its own impactDamage (1.9.11: the rudder's is switched off)", !CrashImpactDamage || parts.Where(kv => kv.Key != "prop" && !(LiftSpawnFix1911 && kv.Key == "rudder")).All(kv => { var dd = G(kv.Value, "impactDamage"); return dd != null && (float)G(dd, "threshold") > 0f && (float)G(dd, "multiplier") > 0f; }) && parts.Where(kv => kv.Key != "prop").Select(kv => G(kv.Value, "impactDamage")).Distinct().Count() == parts.Count - 1, "");
                // mass, CoM, wing geometry
                float mass = aps.Sum(p => p.mass);
                Vector3 com = Vector3.zero;
                foreach (var p in aps) { var mc = p.GetComponent<MeshCollider>(); var c = mc != null ? p.transform.TransformPoint(mc.sharedMesh.bounds.center) : p.transform.position; com += c * p.mass; }
                com /= mass;
                var mainAx = lgs.Where(g => (bool)G(g, "braked")).Select(g => ((Transform)G(g, "axle")).position).ToList();
                var tailAx = lgs.Where(g => IsTailW(g)).Select(g => ((Transform)G(g, "axle")).position).FirstOrDefault();
                float mainZ = mainAx.Count > 0 ? mainAx.Average(v => v.z) : 0;
                {   // 1.7.12: brake nose-over over the real contact point (castPoint, MainContactForward ahead of the tyre): tail-up CoM angle - atan(frictionCoef) >= 3.5 deg
                    var cps = lgs.Where(g => (bool)G(g, "braked")).Select(g => ((Transform)G(g, "castPoint")).position).ToList();
                    float wr = (float)G(lgs.First(g => (bool)G(g, "braked")), "wheelRadius");
                    float cz = cps.Average(v => v.z), cy = cps.Average(v => v.y) - ((float)G(lgs.First(g => (bool)G(g, "braked")), "suspensionTravel") - wr) - wr;
                    float muB = MainGearFriction * (SplitMainGear ? MainBrakeShare : 1f);
                    float ang = Mathf.Atan2(cz - com.z, com.y - cy) * Mathf.Rad2Deg, muDeg = Mathf.Atan(muB) * Mathf.Rad2Deg;
                    R($"1.7.12/1.8.0 brake nose-over: CoM angle over the main contact {ang:F1} deg >= atan(braking friction {muB:F2} = {MainGearFriction} x share) {muDeg:F1} + 3.5; contact {MainContactForward} m ahead of the axle, tailwheel lock {TailSteeringLock}",
                        ang - muDeg >= 3.5f && Mathf.Abs(cz - mainZ - MainContactForward) < 0.02f, $"contact z {cz:F3} (axle {mainZ:F3}), ground y {cy:F3}, CoM ({com.z:F3}, {com.y:F3})");
                }
                {
                    bool gok = GripGear.Verify(inst, MainBrakeShare, MainGearFriction, GripFriction, BrakedRolling, GripRolling, GearMainK, out string gd);
                    R($"1.8.1 split mains: braked leg frictionCoef {MainGearFriction} share {MainBrakeShare} rolling {BrakedRolling} + unbraked grip leg {GripFriction} rolling {GripRolling} on one contact -> braking {MainGearFriction * MainBrakeShare:F2} x load and rolling {BrakedRolling * MainBrakeShare:F2} x load (= 1.7.13), side grip {MainGearFriction * MainBrakeShare + GripFriction * (1 - MainBrakeShare):F2} x load (1.7.13 0.20, 1.8.0 0.80)", !SplitMainGear || (gok && Mathf.Abs(BrakedRolling * MainBrakeShare - 0.05f) < 1e-4f && MainGearFriction * MainBrakeShare + GripFriction * (1 - MainBrakeShare) <= 0.40f), gd);
                    var mains = lgs.Where(g => (bool)G(g, "braked")).ToList();
                    bool onWing = mains.Count == 2 && mains.All(g => { var ap = (AeroPart)G(g, "attachedPart"); var hn = (Transform)G(g, "gearHinge"); return ap != null && ap.name == (g.name.Contains("_L_") ? "wing_lower_L" : "wing_lower_R") && hn.IsChildOf(ap.transform) && ((Transform[])G(g, "wheels")).All(w => w.IsChildOf(ap.transform)); });
                    R("1.8.0 main gear hangs from its lower wing (attachedPart, hinge, leg, wheel under wing_lower_L/R): it breaks off with that wing (LandingGear.onParentDetached)", !GearOnLowerWing || onWing,
                        string.Join(", ", mains.Select(g => $"{g.name} on {((AeroPart)G(g, "attachedPart"))?.name}")));
                    // 1.8.2: per physics step (1/60 s) the gear's damper and spring against the mass of the body it pushes, all legs on that body
                    // all legs, grip partners included
                    var perBody = inst.GetComponentsInChildren<LandingGear>(true).GroupBy(g => (AeroPart)G(g, "attachedPart")).Select(gr => { float m = (float)G(gr.Key, "mass"); float c = gr.Sum(g => (float)G(g, "dampingRate")), k = gr.Sum(g => (float)G(g, "springRate"));
                        return (name: gr.Key.name, m, cr: c / 60f / m, kr: k / 3600f / m); }).ToList();
                    var mainBodies = perBody.Where(b => b.name.StartsWith("wing_lower") || b.name == "FD32").ToList();
                    R("1.8.2 main gear body inside the in-game smooth envelope: damper c dt / m <= 2.25 and spring k dt^2 / m <= 0.6 per body (Mk I root 2.2 / 0.37, B-25H nacelle 3.3 / 0.69; FD-32 1.8.1 wing 6.5 / 1.09 jittered)",
                        !WingGearStiffBody || (mainBodies.Count == 2 && mainBodies.All(b => b.cr <= 2.25f && b.kr <= 0.6f)), string.Join(", ", perBody.Select(b => $"{b.name} {b.m:F0} kg c {b.cr:F2} k {b.kr:F2}")));
                    // 1.8.3 offline D: both dampers x 0.75 (in game each alone stops the 1.8.2 period-2 jitter; tail alone sits on the edge)
                    var tailBody = perBody.FirstOrDefault(b => b.name == "fus_rear");
                    float mainC = inst.GetComponentsInChildren<LandingGear>(true).Where(g => g.name.StartsWith("gear_main_L")).Sum(g => (float)G(g, "dampingRate"));
                    float tailC = inst.GetComponentsInChildren<LandingGear>(true).Where(g => g.name.StartsWith("gear_tail")).Sum(g => (float)G(g, "dampingRate"));
                    R("1.8.3D gear damping x0.75 (per side 13000 -> 9750 N s/m, tail 9000 -> 6750): per-step c dt / m main bodies <= 1.65 (1.8.2 2.17), tail body <= 2.05 (1.8.2 2.73); spring k dt^2 / m unchanged (0.56 / 0.61)",
                        !GearDamping183D || (mainBodies.Count == 2 && mainBodies.All(b => b.cr <= 1.65f && Mathf.Abs(b.kr - 0.5556f) < 0.01f) && tailBody.name != null && tailBody.cr <= 2.05f && Mathf.Abs(tailBody.kr - 0.6061f) < 0.01f
                            && Mathf.Abs(mainC - 9750f) < 1f && Mathf.Abs(tailC - 6750f) < 1f),
                        $"main side c {mainC:F0}, tail c {tailC:F0}; " + string.Join(", ", perBody.Select(b => $"{b.name} {b.m:F0} kg c dt/m {b.cr:F2} k dt2/m {b.kr:F3}")));
                    float wl = (float)G(aps.First(p => p.name == "wing_lower_L"), "mass"), en = (float)G(aps.First(p => p.name == "fus_engine"), "mass");
                    R($"1.8.2 lower wings {WingLowerMass} kg each from fus_engine {EngineMass} kg (1.8.1: 51 / 805, same total)", !WingGearStiffBody || (Mathf.Abs(wl - WingLowerMass) < 1e-3f && Mathf.Abs(en - EngineMass) < 1e-3f && Mathf.Abs(2 * wl + en - (2 * 51f + 805f)) < 1e-3f), $"wing_lower {wl}, fus_engine {en}");
                    var jn = inst.GetComponentsInChildren<JetNozzle>(true).FirstOrDefault();
                    float bx = jn != null ? inst.transform.InverseTransformPoint(((Transform)G(jn, "thrustTransform")).position).x : 99f;
                    R("1.8.2 BOOST thrust on the centreline (JetNozzle.thrustTransform x 0; 1.8.1 0.47 m right = ~1.9 kN m of yaw at full throttle)", !BoostOnCentreline || Mathf.Abs(bx) < 0.01f, $"thrustTransform x {bx:F3}");
                }
                {   // 1.8.3 root collider from the 1.8.2 hull
                    var rc = inst.GetComponent<MeshCollider>();
                    var hj = contract["collider_fus_center"];
                    int hn = hj != null ? ((Newtonsoft.Json.Linq.JArray)hj["verts"]).Count : -1;
                    R("1.8.3 FD32 root collider = convex hull of the 1.8.2 fus_center skin (contract collider_fus_center): the rebuilt opening / canopy / spine do not move the root body's CoM or inertia",
                        !RootColliderHull182 || (rc != null && rc.sharedMesh != null && rc.sharedMesh.vertexCount == hn && rc.convex), $"collider {(rc != null && rc.sharedMesh != null ? rc.sharedMesh.name + " " + rc.sharedMesh.vertexCount : "none")} verts, contract {hn}");
                }
                {   // 1.8.5 offline E (in-game 1.8.3 F1): internals look - stock vertex colours kept, drawn with the stock textures on the matte look material
                    bool okL = B25HTools.StockStructure.CheckLook(inst, out string msgL);
                    R("1.8.5 E internals look: every internals submesh carries a stock exterior-structure vertex grey (87-118, alpha 255) and is drawn with <prefix>_structure_look (URP Lit, the stock aircraft_structure_b / _n / _ao textures, neutral light grey, metallic <= 0.15); none left on the reflective stock material",
                        okL, msgL);
                }
                {   // 1.8.7 offline G: exterior glass gloss (windscreen-base line)
                    var gms = new[] { "windscreen", "canopy_slide_glass" }.Select(n => inst.GetComponentsInChildren<MeshRenderer>(true).FirstOrDefault(r => r.name == n && r.gameObject.layer != 3)).ToList();
                    var gm = gms.Where(r => r != null).SelectMany(r => r.sharedMaterials).Distinct().ToList();
                    bool okG = gms.All(r => r != null) && gm.Count == 1 && gm[0].name == "FD32_glass" && gm[0].shader == Asset<Material>("Material/COIN_glass_PLACEHOLDER.mat").shader
                        && Mathf.Abs(gm[0].GetFloat("_Smoothness") - (GlassGloss187 ? GlassSmooth187 : 0.95f)) < 1e-4f;
                    R($"1.8.7 G FD-32 exterior glass: windscreen + hood on FD32_glass (stock glass shader), smoothness {(GlassGloss187 ? GlassSmooth187 : 0.95f):F2} (stock 0.95)",
                        okG, string.Join("; ", gm.Select(m => $"{m.name} {m.shader.name} smooth {m.GetFloat("_Smoothness"):F2} q {m.renderQueue}")));
                }
                {   // 1.8.3 internals the stock way + ground values fingerprint (compare with the 1.8.2 dump: masses, legs, tail wheel, BOOST point)
                    var stR = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.sharedMaterials.Any(mm => B25HTools.StockStructure.IsStructMat(mm))).ToList();
                    var esT = inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "fus_engine_struct");
                    var esM = esT != null ? esT.GetComponent<MeshFilter>()?.sharedMesh : null;
                    int esTris = 0; bool esCol = false;
                    if (esM != null) { var esR = esT.GetComponent<MeshRenderer>(); int si = Array.FindIndex(esR.sharedMaterials, mm => B25HTools.StockStructure.IsStructMat(mm)); if (si >= 0) { var ix = esM.GetIndices(si); esTris = ix.Length / 3; var c32 = esM.colors32; esCol = c32.Length == esM.vertexCount && c32[ix[0]].r == 92; } }
                    var fts = inst.GetComponentsInChildren<FuelTank>(true);
                    {   // 1.8.9 (offline J; docs/damage_model_study.md): the dmg_b ALPHA is the AircraftSkin hole map (discard below 0.52 - 0.02 / D);
                        // the 1.5.x map had a flat 0.6 (no hole ever opened, parts only darkened)
                        var dmgTex = AssetDatabase.LoadAssetAtPath<Texture2D>(Folder + "/Textures/fd32_skin_dmg_b.png");
                        var hc = DamageHoles189.Check(Path.Combine(RepoTextures, "fd32_skin_dmg_b.png"), dmgTex);
                        R("1.8.9 skin damage HOLES: dmg_b alpha opens 5-13 / 10-27 / 15-30 % of the skin at HP 80 / 50 / 0 (stock bands), alpha kept on import", hc.Item1, hc.Item2);
                    }
                    R("1.8.3 internals the stock way: structure submeshes on the stock aircraft_structure (vertex colour 92), engine body + tank in fus_engine_struct, FuelTank on fus_engine (unchanged)",
                        !StockStructure || (stR.Count >= 6 && esTris >= 400 && esCol && fts.Length == 1 && fts[0].gameObject.name == "fus_engine"), $"{stR.Count} renderers with aircraft_structure, fus_engine_struct {esTris} tris colour ok {esCol}, FuelTank on {string.Join(",", fts.Select(f => f.gameObject.name))}");
                    var fp = string.Join("; ", inst.GetComponentsInChildren<AeroPart>(true).OrderBy(p => p.name).Select(p => $"{p.name} {(float)G(p, "mass"):F2}"))
                        + " | " + string.Join("; ", inst.GetComponentsInChildren<LandingGear>(true).OrderBy(g => g.name).Select(g => $"{g.name} k {G(g, "springRate")} c {G(g, "dampingRate")} f {G(g, "frictionCoef")} al {G(g, "aligningStrength")} lock {G(g, "steeringLock")} at {inst.transform.InverseTransformPoint(g.transform.position).ToString("F4")}"));
                    L("1.8.3 ground fingerprint " + fp);
                    R("1.8.3 ground values logged for the 1.8.2 comparison (part masses, every leg's spring / damping / friction / castering / position)", fp.Length > 100, $"{fp.Length} chars (see the log line '1.8.3 ground fingerprint')");
                }
                R("1.8.0 no PowerSupply / capacitor (the HUD's CAPACITOR line is the stock ChargeIndicator; no jammer, laser or energy weapon fitted)",
                    CapacitorPowerSupply || (inst.GetComponentsInChildren<PowerSupply>(true).Length == 0 && G(inst.GetComponent<Aircraft>(), "powerSupply") == null
                        && inst.GetComponentsInChildren<JammingPod>(true).Length == 0 && inst.GetComponentsInChildren<Laser>(true).Length == 0),
                    $"PowerSupply components {inst.GetComponentsInChildren<PowerSupply>(true).Length}");
                R($"1.8.0 mains side response {MainSideResponse} (stock), tail wheel response 1; contact on the tyre",
                    lgs.Where(g => (bool)G(g, "braked")).All(g => Mathf.Abs((float)G(g, "response") - MainSideResponse) < 1e-4f && (Transform)G(g, "castPoint") == ((GameObject)G(g, "bumpStop")).transform) && lgs.Where(g => IsTailW(g)).All(g => Mathf.Abs((float)G(g, "response") - 1f) < 1e-4f),
                    string.Join(", ", lgs.Select(g => $"{g.name} response {G(g, "response")} friction {G(g, "frictionCoef")}")));
                {   // 1.8.8: castoring mains (GripGear.Castor; tools/flightmodel/taildragger_track.py), the tail wheel the only other steering gear (locked sense)
                    bool cok = GripGear.VerifyCastor(inst, MainCastorRange, MainCastorAlign, out string cdet);
                    bool off = inst.GetComponentsInChildren<LandingGear>(true).Where(g => (bool)G(g, "braked")).All(g => !(bool)G(g, "steering"));
                    R($"1.8.8 castoring mains: both braked mains steering + aligningStrength {MainCastorAlign}, steeringSpeed 0, range +-{MainCastorRange} on their own unsprung = axle (identity rotation), grip partners on the same axle and not steering; tail wheel the only other steering gear, lock < 0",
                        MainCastor188 ? cok : off, cdet);
                }
                R("parts mass 1,450-1,560 kg (empty ~1,500; + gear 56, fuel 280, ammo 96 = ~1,930 combat)", mass > 1450 && mass < 1560, $"{mass} kg");
                float mainY = mainAx.Count > 0 ? mainAx.Average(v => v.y) : 0f; float hCom = com.y - (mainY - (float)contract["gear"]["wheel_r"]);
                float tailUpDeg = Mathf.Atan2(mainZ - com.z, hCom) * Mathf.Rad2Deg;
                R($"CoM behind the main axles at a tail-up angle of 15-20 deg (round 9: {tailUpDeg:F1} deg; was 12.7 and nosed over under brakes 0.3 - fd32_design 21.4) and ahead of the tailwheel", tailUpDeg >= 15f && tailUpDeg <= 20f && com.z > tailAx.z, $"CoM z {com.z:F3} y {com.y:F3}, main axle z {mainZ:F3}, tail axle z {tailAx.z:F3}");
                float area = aps.Sum(p => (float)G(p, "wingArea"));
                var up = aps.Where(p => p.name.StartsWith("wing_upper")).ToList(); var lo = aps.Where(p => p.name.StartsWith("wing_lower")).ToList();
                Vector3 LP(AeroPart p) { var mc = p.GetComponent<MeshCollider>(); var ln = (Transform)G(p, "liftNormal"); return p.transform.TransformPoint(mc.sharedMesh.bounds.center) + ln.rotation * (Vector3)G(p, "centerOfLift"); }
                float upZ = up.Average(p => LP(p).z), loZ = lo.Average(p => LP(p).z), upY = up.Average(p => LP(p).y), loY = lo.Average(p => LP(p).y);
                R("biplane: upper lift points 0.7-1.1 m ahead (stagger) and 1.3-1.5 m above (gap) the lower", upZ - loZ > 0.7f && upZ - loZ < 1.1f && upY - loY > 1.3f && upY - loY < 1.5f, $"stagger {upZ - loZ:F3}, gap {upY - loY:F3}, total lifting area {area:F2} m^2");
                R("wing areas: upper 14.8 (centre + panels + ailerons) + lower 10.8 (panels + flaperons) = 25.6 m^2 (round 3: no HighLiftDevice flap area; flaps are the 4 flap-mode droop surfaces)", Mathf.Abs(up.Sum(p => (float)G(p, "wingArea")) + aps.Where(p => p.name.StartsWith("aileron")).Sum(p => (float)G(p, "wingArea")) - 14.8f) < 0.2f
                    && Mathf.Abs(lo.Sum(p => (float)G(p, "wingArea")) + aps.Where(p => p.name.StartsWith("flaperon")).Sum(p => (float)G(p, "wingArea")) - 10.8f) < 0.1f, "");
                R("joints: every part joined; strut joints upper <-> lower each side", aps.All(p => p.gameObject == inst || ((PartJoint[])G(p, "joints")).Length > 0) && new[] { "L", "R" }.All(s => ((PartJoint[])G(aps.First(p => p.name == "wing_upper_" + s), "joints")).Any(j => j.connectedPart != null && j.connectedPart.name == "wing_lower_" + s)), $"{aps.Sum(p => ((PartJoint[])G(p, "joints")).Length)} joints");
                {   // 1.9.13 wing joint solver iterations (fails on 1.9.12: every joint 6)
                    var zj = aps.SelectMany(p => ((PartJoint[])G(p, "joints")).Select(j => (owner: p.gameObject == inst ? "FD32" : p.name, j))).ToList();
                    var zWingOwners = new[] { "wing_upper_C", "wing_upper_L", "wing_upper_R", "wing_lower_L", "wing_lower_R" };
                    var zBad = zj.Where(x => x.j.solverIterations != (WingSolver1913 && WingSolverOwner1913(x.owner) ? WingSolverIterations1913 : 6)).Select(x => $"{x.owner}->{(x.j.connectedPart ? x.j.connectedPart.name : "null")} {x.j.solverIterations}").ToList();
                    var zUC = zj.Where(x => x.owner == "wing_upper_C").ToList();
                    bool zOwnersOk = zWingOwners.All(o => zj.Any(x => x.owner == o)) && zj.Where(x => WingSolverOwner1913(x.owner)).All(x => zWingOwners.Contains(x.owner));
                    R($"1.9.13 wing joints: every joint owned by wing_upper_C / wing_upper_L/R / wing_lower_L/R has solverIterations {(WingSolver1913 ? WingSolverIterations1913 : 6)} (AeroPart.CreateJoints -> rb.solverIterations; PhysX solves the aircraft's island at the largest), "
                        + "every other joint 6; wing_upper_C -> FD32 present; 33 joints as in 1.9.12",
                        zBad.Count == 0 && zOwnersOk && zj.Count == 33 && zUC.Any(x => x.j.connectedPart != null && x.j.connectedPart.gameObject == inst),
                        zBad.Count == 0 ? $"{zj.Count(x => x.j.solverIterations != 6)} of {zj.Count} joints at {WingSolverIterations1913}: " + string.Join(", ", zj.Where(x => x.j.solverIterations != 6).Select(x => $"{x.owner}->{x.j.connectedPart.name}")) : "wrong: " + string.Join("; ", zBad.Take(8)));
                }
                {   // 1.9.13 final seam cosmetics (fails on 1.9.12: light end faces, no band)
                    var sIt = inst.GetComponentsInChildren<Transform>(true);
                    Transform sT(string n) => sIt.First(t => t.name == n);
                    var sCove = AssetDatabase.LoadAssetAtPath<Material>($"{Folder}/Materials/FD32_cove.mat");
                    var sStructs = new[] { "wing_upper_C_struct", "wing_upper_L_struct", "wing_upper_R_struct" }.Select(n => sT(n).GetComponent<MeshRenderer>()).ToList();
                    var sStrips = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name.Contains(B25HTools.SeamCove1913.StripSuffix)).ToList();
                    if (SeamCove1913)
                    {
                        var sAll = B25HTools.SeamCove1913.CheckAll(inst.transform, sCove, "FD32_fabric_in", SeamBreakX1913);
                        R("1.9.13 seam cove: wing_upper_C/L/R_struct end faces at x = +-0.80 and the stringer-stub faces / end caps at the cut drawn with FD32_cove (last submesh, material[0] unchanged, none left light); "
                            + "four FD32_cove band halves per aircraft: inner under wing_upper_C (x 0.78-0.80, ends at the cut), outer under wing_upper_L/R (x 0.792-0.82), 3.9-6.5 mm inside the paint skin and enclosed by it, no collider, no shadows",
                            sAll.ok, sAll.msg);
                    }
                    else R("1.9.13 seam cove off: no band, no FD32_cove on the wing struct renderers (= 1.9.12)", sStrips.Count == 0 && sStructs.All(r => !r.sharedMaterials.Contains(sCove)), $"{sStrips.Count} bands");
                }
                // crew, hood, cockpit, sensors, HUD
                var cans = (Canopy[])G(ac, "canopies");
                R("1 pilot with the stock ejection seat (EjectionSeat child, Seats material); 1 Canopy (hood) jettisoned first; cockpit view point set",
                    ac.pilots.Length == 1 && (bool)G(ac.pilots[0], "ejectionSeat") == EjectionSeats && ac.pilots[0].GetComponentsInChildren<Transform>(true).Any(t => t.name == "EjectionSeat") && cans.Length == 1 && cans[0].ejectionTransform != null && ac.cockpitViewPoint != null,
                    $"eye {ac.cockpitViewPoint?.position.ToString("F3")}, canopies {cans.Length}");
                var hh = cans.Length == 1 ? ((Array)G(cans[0], "canopyHinges")).GetValue(0) : null;
                R("hood opens by tilting up (hinge angle lifts the front)", hh != null && Mathf.Abs((float)G(hh, "hingeAngle")) > 20f, hh != null ? $"hingeAngle {G(hh, "hingeAngle")}" : "");
                var cr = (Renderer[])G(ac, "cockpitRenderers");
                R("cockpit-layer copies on layer 3 (tub, panel, consoles, stock stick + throttle, screens, hood frame, fuselage)", cr.Length >= 12 && cr.All(r => r.gameObject.layer == 3), $"{cr.Length} renderers");
                var badInt = new List<string>();
                foreach (var r in cr)
                {
                    var o = r.transform.parent;
                    var mo = o != null ? o.GetComponent<MeshFilter>()?.sharedMesh : null; var mi = r.GetComponent<MeshFilter>()?.sharedMesh;
                    bool ok = o != null && r.name == o.name + "_int" && mo != null && mi != null && (mi == mo || (mi.name == r.name + "_tac" && mo.name == o.name + "_tac" && mi.vertexCount == mo.vertexCount)
                        || (InwardCockpitGlass && mi.name == o.name + "_inward" && mi.vertexCount == mo.vertexCount));   // round 6: reversed-winding glass copy
                    if (ok) { var a = r.transform.localToWorldMatrix; var b = o.localToWorldMatrix; for (int i = 0; i < 16 && ok; i++) ok = Mathf.Abs(a[i] - b[i]) < 1e-5f; }
                    if (!ok) badInt.Add(r.name);
                }
                var strayL3 = inst.GetComponentsInChildren<Renderer>(true).Where(r => r.gameObject.layer == 3 && !cr.Contains(r)).Select(r => r.name).ToList();
                R("cockpit-layer copies: each _int copy = its original's mesh and world transform; no other renderer on layer 3", badInt.Count == 0 && strayL3.Count == 0, $"mismatched [{string.Join(", ", badInt)}]; stray [{string.Join(", ", strayL3)}]");
                var ck = inst.GetComponentInChildren<global::Cockpit>(true);
                var stickMesh = T("cockpit_stick")?.GetComponent<MeshFilter>()?.sharedMesh; var thrMesh = T("cockpit_throttle")?.GetComponent<MeshFilter>()?.sharedMesh;
                // round 6 (fault 6): four screens on the stock tac material, each UV0 inside its tac-page region after CopyMesh
                var scrBad = new List<string>();
                foreach (var mj in (Newtonsoft.Json.Linq.JArray)contract["mfds"])
                {
                    var t = T((string)mj["name"]); var uvr = ((Newtonsoft.Json.Linq.JArray)mj["uv"]).Select(x => (float)x).ToArray();
                    var mr = t?.GetComponent<MeshRenderer>(); var mm = t?.GetComponent<MeshFilter>()?.sharedMesh;
                    if (mr == null || mm == null) { scrBad.Add((string)mj["name"] + " missing"); continue; }
                    var uvs = mm.uv;
                    bool inR = uvs.Length > 0 && uvs.All(u => u.x >= uvr[0] - 1e-3f && u.x <= uvr[1] + 1e-3f && u.y >= uvr[2] - 1e-3f && u.y <= uvr[3] + 1e-3f) && uvs.Max(u => u.x) - uvs.Min(u => u.x) > 0.9f * (uvr[1] - uvr[0]);
                    bool mat = mr.sharedMaterials.All(m => m != null && m.name.Contains("tacScreen"));
                    var ic = t.Find(t.name + "_int");
                    bool copyOk = ic != null && ic.gameObject.layer == 3 && ic.GetComponent<MeshRenderer>().sharedMaterials.All(m => m != null && m.name.Contains("tacScreen"));
                    if (!inR || !mat || !copyOk) scrBad.Add($"{t.name} uv {(uvs.Length > 0 ? $"{uvs.Min(u => u.x):F3}-{uvs.Max(u => u.x):F3} x {uvs.Min(u => u.y):F3}-{uvs.Max(u => u.y):F3}" : "none")} mat {mat} copy {copyOk}");
                }
                R("screens (round 6): mfd_map + power / flight / engine on the stock tac material, UV0 inside each tac-page region after import, cockpit copies too",
                    scrBad.Count == 0 && ((Newtonsoft.Json.Linq.JArray)contract["mfds"]).Count == 4, scrBad.Count == 0 ? "4 screens ok" : string.Join("; ", scrBad));
                // round 6 (fault 5): every glass object has a layer-3 copy whose triangles face the eye
                var eyeP = ac.cockpitViewPoint.position; var glassBad = new List<string>();
                foreach (var gn in new[] { "windscreen", "canopy_slide_glass" })
                {
                    var go = T(gn); var gi = go != null ? go.Find(gn + "_int") : null;
                    if (gi == null || gi.gameObject.layer != 3) { glassBad.Add(gn + ": no layer-3 copy"); continue; }
                    var gm = gi.GetComponent<MeshFilter>().sharedMesh; var gv = gm.vertices; var gt = gm.triangles; int toward = 0, n3 = gt.Length / 3;
                    for (int i = 0; i < gt.Length; i += 3)
                    {
                        var a0 = gi.TransformPoint(gv[gt[i]]); var a1 = gi.TransformPoint(gv[gt[i + 1]]); var a2 = gi.TransformPoint(gv[gt[i + 2]]);
                        var nrm = Vector3.Cross(a1 - a0, a2 - a0);     // Unity front face = clockwise seen from the viewer: normal points TO the viewer
                        if (Vector3.Dot(nrm, eyeP - (a0 + a1 + a2) / 3f) > 0f) toward++;
                    }
                    if (toward < 0.95f * n3) glassBad.Add($"{gn}: {toward}/{n3} triangles face the eye");
                    if (!gi.GetComponent<MeshRenderer>().sharedMaterials.All(m => m == (FaintCockpitGlass ? mats["glass_ck"] : mats["glass_int"]))) glassBad.Add(gn + ": copy not the faint glass");
                    var gmat = gi.GetComponent<MeshRenderer>().sharedMaterials[0];
                    if (FaintCockpitGlass && (gmat.shader.name.Contains("canopy") || gmat.GetColor("_BaseColor").a > 0.10f || gmat.renderQueue < 2500)) glassBad.Add($"{gn}: copy shader {gmat.shader.name} alpha {gmat.GetColor("_BaseColor").a:F2} queue {gmat.renderQueue} (must be transparent, alpha <= 0.10, not canopy_int)");
                }
                R("canopy glass seen from inside (round 7): windscreen + canopy glass have a layer-3 copy whose triangles face the eye (>= 95 %), faint transparent URP Lit (alpha <= 0.10), not the darkening canopy_int shader", glassBad.Count == 0, glassBad.Count == 0 ? "ok" : string.Join("; ", glassBad));
                {
                    var ckT = inst.GetComponentInChildren<global::Cockpit>(true); var thE = ckT != null ? ((IList)G(ckT, "throttles"))[0] : null;
                    var thD = thE != null ? (Transform)G(thE, "transform") : null; var thM = T("cockpit_throttle");
                    string thInfo = "missing"; bool thOk = false;
                    if (thD != null && thM != null)
                    {
                        var a0 = inst.transform.InverseTransformPoint(thM.position); var lp = thD.localPosition;
                        thD.localPosition = new Vector3(0f, 0f, (float)G(thE, "range")); var a1 = inst.transform.InverseTransformPoint(thM.position); thD.localPosition = lp;
                        var dlt = a1 - a0; thOk = (bool)G(thE, "motion") && lp.sqrMagnitude < 1e-8f && Mathf.Abs(dlt.z - 0.22f) < 0.005f && Mathf.Abs(dlt.x) < 0.005f && Mathf.Abs(dlt.y) < 0.005f;
                        thInfo = $"idle local {lp.ToString("F4")}, full-throttle move {dlt.ToString("F3")}";
                    }
                    R("throttle (round 10): the CI-22 throttle slides 0.22 m straight FORWARD at full throttle from its idle spot (no jump)", thOk, thInfo);
                }
                R("Cockpit (round 10): stock SFB-81 stick, the CI-22 single throttle COIN_throttle (Cockpit.Throttle motion, forward), Cockpit.tacScreenRender = TargetCam.targetScreenRenderer = mfd_map, no targetCamDisplay mesh, no pedals",
                    ck != null && ((IList)G(ck, "joysticks")).Count == 1 && ((IList)G(ck, "throttles")).Count == 1 && G(ck, "tacScreenRender") is Renderer tr2 && tr2.name == "mfd_map" && tr2.sharedMaterials.All(m => m != null && m.name.Contains("tacScreen"))
                    && (Renderer)G(ac.targetCam, "targetScreenRenderer") == tr2
                    && !inst.GetComponentsInChildren<MeshRenderer>(true).Any(r => r.sharedMaterials.Any(m => m != null && m.name.Contains("targetCam")))
                    && stickMesh != null && stickMesh.name.Contains("sfb_joystick") && thrMesh != null && (StockThrottle ? thrMesh.name.Contains("COIN_throttle") : thrMesh.name.StartsWith("cockpit_throttle"))
                    && !inst.GetComponentsInChildren<Transform>(true).Any(t => t.name.Contains("pedal") || t.name.Contains("rudderbar")), $"{stickMesh?.name} / {thrMesh?.name}");
                var tcam = ac.targetCam; var ball = T("sensor_ball");
                var sensH = hlds.FirstOrDefault(h => (G(h, "aeroPart") as AeroPart)?.name == "fus_engine");
                {
                    var lgL = lgs.FirstOrDefault(g => g.name.Contains("gear_main_L"));
                    var gpArr = lgL != null ? (GearPart[])G(lgL, "movingParts") : null;
                    var gpBall = gpArr?.FirstOrDefault(gp => gp.transform != null && gp.transform.name == "sensor_arm");
                    string ballInfo = "none"; bool ballOk = false;
                    if (gpBall != null)
                    {
                        var armT = gpBall.transform; var r0 = armT.localRotation; var b0 = ball.position;
                        armT.localEulerAngles = gpBall.foldAngles; var b1 = ball.position; armT.localRotation = r0;
                        float drop = b0.y - b1.y, drift = Vector3.ProjectOnPlane(b1 - b0, inst.transform.up).magnitude;
                        ballOk = drop > 0.2f && drift < 0.04f;
                        ballInfo = $"gear-up turn {gpBall.foldAngles.x:F1} deg: ball drops {drop:F3} m, drift {drift:F3} m";
                    }
                    R("sensor ball (round 9): out with the gear UP (left main gear movingParts turn the ball arm: drop >= 0.20 m, drift < 0.04 m), stowed with the gear down; EOTS scanner = the ball; TargetCam forward mount rides on sensor_mount; no speed HLD",
                        !SensorBall || (ac.EOTS != null && (Transform)G(ac.EOTS, "scanner") == ball && tcam != null && ((Transform)G(tcam, "camMountForward")).parent == T("sensor_mount") && (!SensorWithGearUp || (ballOk && sensH == null))), ballInfo);
                }
                var radar = inst.GetComponentInChildren<Radar>(true);
                R("radar: one stock Radar (VT-7 values, 35 km), attached to the aircraft", !WingRadar || (radar != null && Mathf.Abs(radar.RadarParameters.maxRange - 35000f) < 1f && inst.GetComponentsInChildren<Radar>(true).Length == 1), radar != null ? $"maxRange {radar.RadarParameters.maxRange}" : "none");
                var fe = inst.GetComponentInChildren<FlareEjector>(true);
                R($"flares: {Flares} (= CI-22), two ejection points under the rear fuselage", fe != null && System.Convert.ToInt32(G(fe, "ammo")) == Flares && ((IList)G(fe, "ejectionPoints")).Count == 2, fe != null ? $"ammo {G(fe, "ammo")}" : "");
                var nls = inst.GetComponentsInChildren<Light>(true).Where(l => l.type == LightType.Point && l.name.StartsWith("navLight")).ToList();
                R("nav lights: 2 Point lights 0.40 m outboard of the tip lenses, range 0.55 (Mk I 1.3.2 layout; the hinge slots stay unlit)", NoNavLights || (nls.Count == 2 && nls.All(l => Mathf.Abs(l.range - NavLightRange) < 1e-4f)), $"{nls.Count} point lights");
                var prm = ((AircraftDefinition)ac.definition).aircraftParameters;
                R("HUD extras = stock Multirole1 (BOOST throttle bar), status display, map icon", prm.HUDExtras != null && AssetDatabase.GetAssetPath(prm.HUDExtras).Contains("Multirole1_HUDExtras") && prm.StatusDisplay != null && ac.definition.mapIcon != null, prm.HUDExtras ? AssetDatabase.GetAssetPath(prm.HUDExtras) : "none");
                var lv = prm.liveries;
                var facs = lv.Select(l => l.faction).Distinct().ToList();
                var zBdf = NavalLiveries1912 ? new[] { "BDF Matte Gray", "BDF Temperate Camo", "BDF Navy Hex" } : new[] { "BDF Matte Gray", "BDF Temperate Camo" };
                var zPala = NavalLiveries1912 ? new[] { "PALA Desert Camo", "PALA Matte Black", "PALA Navy Splinter" } : new[] { "PALA Desert Camo", "PALA Matte Black" };
                R("liveries per faction ONLY its own (round 3): BDF = Matte Gray, Temperate" + (NavalLiveries1912 ? ", Navy Hex" : "") + "; PALA = Desert (first), Matte Black" + (NavalLiveries1912 ? ", Navy Splinter (1.9.12)" : ""), facs.Count == 2
                    && lv.Where(l => l.faction == facs[0]).Select(l => l.name).SequenceEqual(zBdf)
                    && lv.Where(l => l.faction == facs[1]).Select(l => l.name).SequenceEqual(zPala),
                    string.Join(", ", lv.Select(l => l.name)));
                {   // 1.9.12: saved missions store the livery list index
                    var zNames = lv.Select(l => l.name).ToList();
                    var zWant = NavalLiveries1912 ? Liveries1911.Concat(new[] { "BDF Navy Hex", "PALA Navy Splinter" }).ToArray() : Liveries1911;
                    bool zNavOk = !NavalLiveries1912 || (lv.Count == 6 && lv[4].faction == facs[0] && lv[5].faction == facs[1]
                        && new[] { 4, 5 }.All(i => { var ld = AssetDatabase.LoadAssetAtPath<LiveryData>(AssetDatabase.GUIDToAssetPath(lv[i].assetReference.AssetGUID)); return ld != null && ld.Texture != null && ld.Texture.name == (i == 4 ? "fd32_livery_bdf_navy" : "fd32_livery_pala_navy") && Mathf.Abs(ld.Glossiness - NavalGloss1912) < 1e-4f && ld.Colors != null && ld.Colors.Length > 0; }));
                    R("1.9.12 livery list: indexes 0-3 are the 1.9.11 names in the 1.9.11 order (saved missions keep their livery)" + (NavalLiveries1912 ? "; 4 = BDF Navy Hex (BDF), 5 = PALA Navy Splinter (PALA), each with its own texture, glossiness " + NavalGloss1912.ToString("F1") + " (stock naval) and colour list" : "; no naval entry (flag off)"),
                        zNames.SequenceEqual(zWant) && zNavOk, string.Join(" | ", zNames.Select((n, i) => i + " " + n)));
                }
                // ---- 1.9.12 airbrake panels
                {
                    var zAbs = inst.GetComponentsInChildren<global::Airbrake>(true);
                    var zHinges = inst.GetComponentsInChildren<Transform>(true).Where(t => t.name.StartsWith("airbrake_") && t.name.EndsWith("_hinge")).OrderBy(t => t.name).ToList();
                    var zTrays = inst.GetComponentsInChildren<Transform>(true).Where(t => t.name == "airbrake_tray_L" || t.name == "airbrake_tray_R").ToList();
                    if (!AirbrakePanels1912)
                        R("1.9.12 airbrake panels off (flag): no Airbrake component, no airbrake_* object (= 1.9.11)", zAbs.Length == 0 && zHinges.Count == 0 && zTrays.Count == 0, $"{zAbs.Length} Airbrake, {zHinges.Count} hinges, {zTrays.Count} trays");
                    else
                    {
                        bool zOur(Object o) => AssetDatabase.GetAssetPath(o).StartsWith(Folder);
                        var zAb = zAbs.FirstOrDefault();
                        var zTr = zAb != null ? ((Transform[])G(zAb, "transforms")).ToList() : new List<Transform>();
                        var zCon = zAb != null ? (UnityEngine.Animations.AimConstraint[])G(zAb, "constraints") : null;
                        R($"1.9.12 airbrake: ONE stock Airbrake on the root, part = the root part, dragAmount {AirbrakeDrag1912}, maxAngle {AirbrakeMaxAngle1912}, openSpeed {AirbrakeOpenSpeed1912} (opens in {1f / AirbrakeOpenSpeed1912:F0} s), transforms = airbrake_L_hinge + airbrake_R_hinge, no sound, constraints empty (not null), aircraft set",
                            zAbs.Length == 1 && zAb.gameObject == inst && (G(zAb, "part") as UnitPart) == inst.GetComponent<AeroPart>() && Mathf.Approximately((float)G(zAb, "dragAmount"), AirbrakeDrag1912)
                                && Mathf.Approximately((float)G(zAb, "maxAngle"), AirbrakeMaxAngle1912) && Mathf.Approximately((float)G(zAb, "openSpeed"), AirbrakeOpenSpeed1912)
                                && zTr.Count == 2 && zTr.All(t => t != null) && zTr.Select(t => t.name).OrderBy(n => n).SequenceEqual(new[] { "airbrake_L_hinge", "airbrake_R_hinge" })
                                && (G(zAb, "airbrakeSound") as AudioSource) == null && zCon != null && zCon.Length == 0 && (G(zAb, "aircraft") as Aircraft) == ac,
                            zAb == null ? $"{zAbs.Length} Airbrake components" : $"{zAbs.Length} on {zAb.name}: drag {G(zAb, "dragAmount")}, maxAngle {G(zAb, "maxAngle")}, openSpeed {G(zAb, "openSpeed")}, transforms [{string.Join(", ", zTr.Select(t => t ? t.name : "null"))}], part {(G(zAb, "part") as UnitPart)?.name}");
                        // structure: hinge under fus_rear (not a capsule part), one panel mesh child with paint first, nothing but Transform / MeshFilter / MeshRenderer, no collider, no part
                        var zBad = new List<string>();
                        foreach (var zh in zHinges)
                        {
                            var zp = zh.Find(zh.name.Replace("_hinge", ""));
                            var zmr = zp ? zp.GetComponent<MeshRenderer>() : null; var zmf = zp ? zp.GetComponent<MeshFilter>() : null;
                            if (zmr == null || zmf == null || zmf.sharedMesh == null) { zBad.Add(zh.name + ": no panel mesh child"); continue; }
                            if (zmr.sharedMaterials.Length == 0 || zmr.sharedMaterials[0] != mats["paint"]) zBad.Add(zp.name + ": paint is not material 0");
                            if (!zOur(zmf.sharedMesh)) zBad.Add(zp.name + ": mesh not ours");
                            var zOwn = OwningPart1912(zh);
                            if (zOwn == null || zOwn.name != "fus_rear") zBad.Add(zh.name + ": owning part " + zOwn?.name);
                            if (zh.GetComponentsInParent<Component>(true).Any(c => c != null && c.GetType().Name == "EscapeCapsule")) zBad.Add(zh.name + ": under an escape capsule part");
                            if (zh.GetComponentsInChildren<Collider>(true).Length > 0) zBad.Add(zh.name + ": collider under the hinge");
                            if (zh.GetComponentsInChildren<UnitPart>(true).Length > 0) zBad.Add(zh.name + ": UnitPart under the hinge");
                            foreach (var zc in zh.GetComponentsInChildren<Component>(true))
                                if (zc == null || !(zc is Transform || zc is MeshFilter || zc is MeshRenderer)) zBad.Add(zh.name + ": extra component " + (zc == null ? "missing script" : zc.GetType().Name));
                            if (Mathf.Abs(Vector3.Dot(zh.right, inst.transform.up)) < 0.9999f) zBad.Add(zh.name + ": hinge line (local X) not vertical");
                            if (zOwn != null)
                            {
                                var zdm = ((IList)G(G(zOwn, "damageMaterial"), "renderers")).Cast<Object>().ToList();
                                if (!zdm.Contains(zmr)) zBad.Add(zp.name + ": not in fus_rear's livery / damage renderer list");
                            }
                        }
                        foreach (var zt in zTrays)
                        {
                            if (zt.GetComponentsInChildren<Collider>(true).Length > 0) zBad.Add(zt.name + ": collider");
                            if (zt.GetComponentsInChildren<MeshRenderer>(true).Any(r => r.sharedMaterials.Contains(mats["paint"]))) zBad.Add(zt.name + ": paint on the well");
                            var zOwnT = OwningPart1912(zt);
                            if (zOwnT == null || zOwnT.name != "fus_rear" || zt.parent != zOwnT.transform) zBad.Add(zt.name + ": not a direct child of fus_rear");
                        }
                        R("1.9.12 airbrake panels: two hinges under fus_rear (no escape-capsule parent), hinge line vertical, each with one panel mesh child (our mesh, paint = material 0, in fus_rear's livery list), only Transform / MeshFilter / MeshRenderer under a hinge, no collider, no part; two fixed wells without paint or collider",
                            zHinges.Count == 2 && zTrays.Count == 2 && zBad.Count == 0, zBad.Count == 0 ? string.Join(", ", zHinges.Select(t => t.name).Concat(zTrays.Select(t => t.name))) : string.Join("; ", zBad.Take(8)));
                        // fus_rear itself is the 1.9.11 part: its collider is baked from its own mesh only
                        {
                            var zfr = P("fus_rear"); var zmc = zfr != null ? zfr.GetComponent<MeshCollider>() : null; var zfmr = zfr != null ? zfr.GetComponent<MeshFilter>() : null;
                            var zcb = zmc != null && zmc.sharedMesh != null ? zmc.sharedMesh.bounds : new Bounds(); var zmb = zfmr != null && zfmr.sharedMesh != null ? zfmr.sharedMesh.bounds : new Bounds();
                            R("1.9.12 airbrake panels leave fus_rear alone: one MeshCollider on fus_rear whose bounds lie inside its own mesh bounds (the panels stand 4 mm proud and open 0.48 m outward: they are not in the hull)",
                                zmc != null && zfmr != null && zcb.min.x >= zmb.min.x - 0.002f && zcb.max.x <= zmb.max.x + 0.002f && zcb.min.z >= zmb.min.z - 0.002f && zcb.max.z <= zmb.max.z + 0.002f && zfr.GetComponents<Collider>().Length == 1,
                                zmc != null ? $"collider x {zcb.min.x:F3}..{zcb.max.x:F3}, mesh x {zmb.min.x:F3}..{zmb.max.x:F3}" : "no collider");
                        }
                        // opening sense and travel, exactly the stock call
                        var zGain = zHinges.Select(zh => AirbrakeOpenGain1912(zh, inst.transform, AirbrakeMaxAngle1912)).ToList();
                        R($"1.9.12 airbrake panels: the stock rotation (+{AirbrakeMaxAngle1912} deg about the hinge's local X) moves each free edge outward by >= {AirbrakeMinEdgeOut1912} m, left = right",
                            zGain.Count == 2 && zGain.All(g => g >= AirbrakeMinEdgeOut1912) && Mathf.Abs(zGain[0] - zGain[1]) < 0.01f, string.Join(" / ", zGain.Select(g => g.ToString("F3") + " m")));
                        // paint texels: every panel paint vertex takes the atlas texel of the fus_rear skin point 3-5 mm under it
                        {
                            var zfm = P("fus_rear").GetComponent<MeshFilter>(); var zsm = zfm.sharedMesh;
                            var zsv = zsm.vertices.Select(v => zfm.transform.TransformPoint(v)).ToArray(); var zsu = zsm.uv; var zst = zsm.GetTriangles(0);
                            int zn = 0, zmiss = 0; float zdMin = float.MaxValue, zdMax = 0f;
                            foreach (var zh in zHinges)
                            {
                                var zp = zh.Find(zh.name.Replace("_hinge", "")); if (zp == null) continue;
                                var zpm = zp.GetComponent<MeshFilter>().sharedMesh; var zpu = zpm.uv; var zpv = zpm.vertices;
                                foreach (var zi in zpm.GetTriangles(0).Distinct())
                                {
                                    zn++; var zu = zpu[zi]; var zw = zp.TransformPoint(zpv[zi]); float best = float.MaxValue;
                                    for (int k = 0; k < zst.Length; k += 3)
                                    {
                                        Vector2 a = zsu[zst[k]], b = zsu[zst[k + 1]], c = zsu[zst[k + 2]];
                                        float den = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y); if (Mathf.Abs(den) < 1e-12f) continue;
                                        float l0 = ((b.y - c.y) * (zu.x - c.x) + (c.x - b.x) * (zu.y - c.y)) / den, l1 = ((c.y - a.y) * (zu.x - c.x) + (a.x - c.x) * (zu.y - c.y)) / den, l2 = 1f - l0 - l1;
                                        if (l0 < -0.02f || l1 < -0.02f || l2 < -0.02f) continue;
                                        best = Mathf.Min(best, Vector3.Distance(zw, l0 * zsv[zst[k]] + l1 * zsv[zst[k + 1]] + l2 * zsv[zst[k + 2]]));
                                    }
                                    if (best == float.MaxValue) { zmiss++; continue; }
                                    zdMin = Mathf.Min(zdMin, best); zdMax = Mathf.Max(zdMax, best);
                                }
                            }
                            R("1.9.12 airbrake panels carry the livery: every panel paint vertex has the atlas UV0 of the fus_rear skin point 3-5 mm under it (same texels as the skin beneath; the atlas is not re-packed, the manifest row above is checked without the panels)",
                                zn > 0 && zmiss == 0 && zdMin >= 0.003f && zdMax <= 0.005f, $"{zn} paint vertices, {zmiss} with a UV outside fus_rear's paint triangles, skin point {zdMin * 1000f:F2}..{zdMax * 1000f:F2} mm away");
                        }
                        // clear of the green strips, shut and through the whole opening: bounds of the panels (aircraft frame) against the bounds of every strip
                        {
                            var zStrips = inst.GetComponentsInChildren<MeshFilter>(true).Where(r => r.name.StartsWith("slimelight_") && r.sharedMesh != null).ToList();
                            Bounds zB(MeshFilter m) { var vs = m.sharedMesh.vertices; var bb = new Bounds(inst.transform.InverseTransformPoint(m.transform.TransformPoint(vs[0])), Vector3.zero); foreach (var v in vs) bb.Encapsulate(inst.transform.InverseTransformPoint(m.transform.TransformPoint(v))); return bb; }
                            var zSB = zStrips.Select(m => (m.name, zB(m))).ToList();
                            var zKeep = zHinges.Select(t => t.localRotation).ToList(); var zHit = new List<string>(); float zGap = float.MaxValue;
                            try
                            {
                                for (int zdeg = 0; zdeg <= (int)AirbrakeMaxAngle1912; zdeg += 5)
                                {
                                    for (int zi = 0; zi < zHinges.Count; zi++) { zHinges[zi].localRotation = zKeep[zi]; zHinges[zi].Rotate(new Vector3(zdeg, 0f, 0f), Space.Self); }
                                    foreach (var zh in zHinges) foreach (var zmf in zh.GetComponentsInChildren<MeshFilter>(true))
                                    {
                                        var zb = zB(zmf);
                                        foreach (var (zsn, zsb) in zSB)
                                        {
                                            if (zb.Intersects(zsb)) zHit.Add($"{zmf.name} x {zsn} at {zdeg} deg");
                                            zGap = Mathf.Min(zGap, Mathf.Sqrt(zb.SqrDistance(zsb.ClosestPoint(zb.center))));
                                        }
                                    }
                                }
                            }
                            finally { for (int zi = 0; zi < zHinges.Count; zi++) zHinges[zi].localRotation = zKeep[zi]; }
                            R("1.9.12 airbrake panels clear of the 9 green gear-down strips, shut and at every 5 deg of the opening (bounds of the panels in the aircraft frame against the bounds of every strip, >= 30 mm)",
                                zStrips.Count == 9 && zHit.Count == 0 && zGap >= 0.03f, zHit.Count == 0 ? $"nearest strip bounds {zGap * 1000f:F0} mm from a panel's bounds" : string.Join("; ", zHit.Take(4)));
                        }
                    }
                }
                var stockMesh = inst.GetComponentsInChildren<MeshFilter>(true).Where(m => m.sharedMesh != null && !AssetDatabase.GetAssetPath(m.sharedMesh).StartsWith(Folder) && !AssetDatabase.GetAssetPath(m.sharedMesh).StartsWith(DNS)).Select(m => m.name).ToList();
                R("every mesh is ours (mesh bank in the mod folder) or a stock placeholder (seat, stick, throttle)", stockMesh.Count == 0, string.Join(", ", stockMesh.Take(6)));
                var def = (AircraftDefinition)ac.definition;
                R($"definition: FD32, value {ValueM}, rank 0, radarSize {RadarSize}, g 9, spawn offset = level wheel contact, rest rotation -14", def.jsonKey == JsonKey && Mathf.Abs(def.value - ValueM) < 1e-4f && prm.rankRequired == 0 && Mathf.Abs(def.radarSize - RadarSize) < 1e-5f && Mathf.Abs(prm.aircraftGLimit - 9f) < 1e-4f
                    && Mathf.Abs(def.spawnOffset.y - ((float)contract["level_wheel_contact_height"] + SpawnLift)) < 0.001f && def.restRotation.x < -10f && !string.IsNullOrEmpty(def.description), $"spawnOffset {def.spawnOffset.ToString("F3")}, mass {((UnitDefinition)def).mass}");
                {   // 1.9.11 carrier-lift spawn (LiftSpawn1911.cs)
                    var rud = P("rudder"); var rid = rud != null ? G(rud, "impactDamage") : null;
                    var others = aps.Where(p => p.name != "rudder" && p.name != "prop").Select(p => G(p, "impactDamage")).ToList();
                    R("1.9.11 rudder: impact damage off as on every stock rudder (threshold 0, multiplier 0, its own instance); every other airframe part keeps its impact damage; rudder joints unchanged (8000 / 4000)",
                        !LiftSpawnFix1911 || (rid != null && (float)G(rid, "threshold") == 0f && (float)G(rid, "multiplier") == 0f && others.All(o => o != null && !ReferenceEquals(o, rid) && (float)G(o, "threshold") > 0f)
                            && ((PartJoint[])G(rud, "joints")).Select(j => j.breakForce).OrderBy(x => x).SequenceEqual(new[] { 4000f, 8000f })),
                        rid != null ? $"rudder {G(rid, "threshold")} x {G(rid, "multiplier")}, mass {rud.mass}, joints {string.Join(" / ", ((PartJoint[])G(rud, "joints")).Select(j => j.breakForce))}; {others.Count} other parts on" : "no rudder");
                    var ls = LiftSpawn1911.Check(inst.transform, rud != null ? rud.transform : null, def.spawnOffset, def.restRotation);
                    R($"1.9.11 spawn: spawnOffset.z {SpawnForward1911} m forward; the rudder's aft end in the spawn pose is at least {LiftSpawn1911.MinMargin} m ahead of the nearest stock lift backstop face (Annex and Hyperion hangar_R1, measured on the stock prefabs)",
                        !LiftSpawnFix1911 || (Mathf.Abs(def.spawnOffset.z - SpawnForward1911) < 1e-5f && def.spawnOffset.x == 0f && ls.Item1), ls.Item2);
                }
                var op = AssetDatabase.LoadAssetAtPath<Blueprinter.OpAddAircraftToHangars>(Folder + "/OpAddAircraftToHangars.asset");
                R("hangars: medium hangar, revetment, shelter, Cursor LFD, Annex R1-R3 + M, Hyperion R1-R3 (11 hangar names)", op != null && op.hangars.Sum(h => h.hangarNames.Count) == 11,
                    op != null ? string.Join("; ", op.hangars.Select(h => h.hangarUnitJsonKey + ":" + string.Join(",", h.hangarNames))) : "missing");
                var cfso = new SerializedObject(inst.GetComponentInChildren<ControlsFilter>(true));
                R($"FBW: gLimit {FBWgLimit} (HUD ~9 g), corner {FBWCorner}, alpha limiter {AlphaLimiter} (+ incidence 1.5 = wing CLmax 17.0 deg)", Mathf.Abs(cfso.FindProperty("flyByWire.gLimitPositive").floatValue - FBWgLimit) < 0.01f
                    && Mathf.Abs(cfso.FindProperty("flyByWire.alphaLimiter").floatValue - AlphaLimiter) < 0.01f && Mathf.Abs(AlphaLimiter + WingIncidence - 17.0f) < 0.11f, "");
                R("jsonKeys: FD32 / FD32_* only (no clash with B25H*, GA25X*, NIMROD1*)", AssetDatabase.FindAssets("t:WeaponMount", new[] { Folder }).Select(g => AssetDatabase.LoadAssetAtPath<WeaponMount>(AssetDatabase.GUIDToAssetPath(g))).All(m => m.jsonKey.StartsWith("FD32_")), "");
            }
            finally { Object.DestroyImmediate(inst); }
            bool all = rows.All(r => r.ok);
            foreach (var r in rows) L($"CHECK {(r.ok ? "PASS" : "FAIL")} {r.name}: {r.detail}");
            L($"CHECK {(all ? "ALL PASS" : "FAILED")} ({rows.Count(r => r.ok)}/{rows.Count})");
            return all;
        }

        // ------------------------------------------------------------------ from B25HBuild.cs: templates, reflection
        static void DestroyTemplates()
        {
            foreach (var g in tpl.Values) if (g != null) Object.DestroyImmediate(g);
            tpl.Clear(); tplRoots.Clear();
        }

        static Transform TplFind(string spec) // "CAS1:wing1_L"
        {
            var parts2 = spec.Split(':');
            var r = tpl[parts2[0]].transform;
            if (r.name == parts2[1] || parts2[1] == parts2[0]) return r;
            var t = r.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == parts2[1]);
            if (t == null) throw new Exception("template object not found " + spec);
            return t;
        }

        static T TplComp<T>(string spec) where T : Component
        {
            var c = TplFind(spec).GetComponent<T>();
            if (c == null) throw new Exception($"template {spec} has no {typeof(T).Name}");
            return c;
        }

        static AudioSource TplAudio(string spec, string clipName)
        {
            var srcs = TplFind(spec).GetComponents<AudioSource>();
            var a = srcs.FirstOrDefault(s => s.clip != null && s.clip.name.StartsWith(clipName)) ?? (clipName == "" ? srcs.FirstOrDefault() : null);
            if (a == null) throw new Exception($"template audio {spec}/{clipName} not found (have {string.Join(",", srcs.Select(s => s.clip ? s.clip.name : "null"))})");
            return a;
        }

        static T Asset<T>(string rel) where T : Object
        {
            var a = AssetDatabase.LoadAssetAtPath<T>($"{DNS}/{rel}");
            if (a == null) throw new Exception("missing placeholder asset " + rel);
            return a;
        }

        // Copy a stock component onto our object, then drop every reference that points into a stock prefab
        // (our singletons are re-wired; the rest is set explicitly by the caller).
        static T CloneComp<T>(T src, GameObject dst) where T : Component
        {
            var c = dst.AddComponent(src.GetType()) as T;
            EditorUtility.CopySerialized(src, c);
            if (c is Aircraft a) aircraft = a;            // our singletons replace their stock counterparts
            else if (c is ControlsFilter cf) controlsFilter = cf;
            else if (c is WeaponManager w) weaponManager = w;
            Remap(c);
            return c;
        }

        static void Remap(Object c)
        {
            var so = new SerializedObject(c);
            var it = so.GetIterator();
            bool enter = true, changed = false;
            while (it.Next(enter))
            {
                enter = true;
                if (it.propertyType != SerializedPropertyType.ObjectReference) continue;
                if (it.propertyPath == "m_Script" || it.propertyPath == "m_GameObject") continue;
                var v = it.objectReferenceValue;
                if (v == null || !IsTemplateObject(v)) continue;
                Object repl = null;
                if (v is Aircraft || v is Unit) repl = aircraft;
                else if (v is ControlsFilter) repl = controlsFilter;
                else if (v is WeaponManager) repl = weaponManager;
                it.objectReferenceValue = repl; changed = true;
            }
            if (changed) so.ApplyModifiedPropertiesWithoutUndo();
        }

        static bool IsTemplateObject(Object o)
        {
            Transform t = o is GameObject g ? g.transform : o is Component c ? c.transform : null;
            return t != null && tplRoots.Contains(t.root);
        }

        // =================================================================== reflection helpers
        static FieldInfo Fld(Type t, string n)
        {
            for (var x = t; x != null; x = x.BaseType)
            {
                var f = x.GetField(n, BF | BindingFlags.DeclaredOnly);
                if (f != null) return f;
            }
            throw new Exception($"field {t.Name}.{n} not found");
        }
        static void S(object o, string n, object v) => Fld(o.GetType(), n).SetValue(o, v);
        static object G(object o, string n) => Fld(o.GetType(), n).GetValue(o);
        // 1.8.8: the mains steer too now (castoring, GripGear.Castor), so "the tail wheel" = the steering gear that is not braked
        static bool IsTailW(object g) => (bool)G(g, "steering") && !(bool)G(g, "braked");
        static object New(Type t) => Activator.CreateInstance(t, true);
        static Type Elem(FieldInfo f) => f.FieldType.IsArray ? f.FieldType.GetElementType() : f.FieldType.GetGenericArguments()[0];
        static object NewElem(object owner, string field) => New(Elem(Fld(owner.GetType(), field)));
        static void SetSeq(object o, string n, IEnumerable items)
        {
            var f = Fld(o.GetType(), n);
            var list = items.Cast<object>().ToList();
            var et = Elem(f);
            if (f.FieldType.IsArray)
            {
                var a = Array.CreateInstance(et, list.Count);
                for (int i = 0; i < list.Count; i++) a.SetValue(list[i], i);
                f.SetValue(o, a);
            }
            else
            {
                var l = (IList)Activator.CreateInstance(f.FieldType);
                foreach (var x in list) l.Add(x);
                f.SetValue(o, l);
            }
        }

        // ------------------------------------------------------------------ from B25HBuild.cs: materials + meshes
        static Material Tiled(Material m, string b, string n = null)
        {
            m.SetTexture("_BaseMap", tex[b]); m.SetTexture("_MainTex", tex[b]);
            if (n != null) { m.SetTexture("_BumpMap", tex[n]); m.EnableKeyword("_NORMALMAP"); }
            return m;
        }

        static Material LitMat(Shader s, string name, Color c, float metal, float smooth)
        {
            var m = new Material(s) { name = name };
            m.SetColor("_BaseColor", c); m.SetColor("_Color", c);
            m.SetFloat("_Metallic", metal); m.SetFloat("_Smoothness", smooth);
            return m;
        }

        static void Save(Material m, string key)
        {
            AssetDatabase.CreateAsset(m, $"{Folder}/Materials/{m.name}.mat");
            mats[key] = m;
        }

        // =================================================================== meshes
        static Mesh CopyMesh(Mesh src, string name, string[] matNames, out string[] orderedNames)
        {
            var m = Object.Instantiate(src);
            m.name = name;
            orderedNames = matNames;
            int paintIdx = Array.IndexOf(matNames, "paint");
            if (paintIdx > 0)
            {
                // The game applies liveries to material[0] of each part renderer: move the paint submesh first.
                var order = new List<int> { paintIdx };
                order.AddRange(Enumerable.Range(0, matNames.Length).Where(i => i != paintIdx));
                var subs = order.Select(i => src.GetIndices(i)).ToArray();
                var topo = order.Select(i => src.GetTopology(i)).ToArray();
                m.subMeshCount = subs.Length;
                for (int i = 0; i < subs.Length; i++) m.SetIndices(subs[i], topo[i], i);
                orderedNames = order.Select(i => matNames[i]).ToArray();
            }
            // URP Lit samples UV0; our tiling textures are laid out on UV1 ('detail'). Vertices not used by the paint
            // submesh get UV0 = UV1 (paint keeps the livery atlas on UV0).
            var uv1 = new List<Vector2>(); m.GetUVs(1, uv1);
            if (uv1.Count == m.vertexCount)
            {
                var uv0 = new List<Vector2>(); m.GetUVs(0, uv0);
                var paintV = new HashSet<int>();
                int pi = Array.IndexOf(orderedNames, "paint"), gi = Array.IndexOf(orderedNames, "gauges"), gl = Array.IndexOf(orderedNames, "glass"), sc = Array.IndexOf(orderedNames, "screen");
                if (pi >= 0) foreach (var i in m.GetIndices(pi)) paintV.Add(i);
                if (gi >= 0) foreach (var i in m.GetIndices(gi)) paintV.Add(i);   // gauges use their own 0-1 cells on UV0
                if (gl >= 0) foreach (var i in m.GetIndices(gl)) paintV.Add(i);
                if (sc >= 0) foreach (var i in m.GetIndices(sc)) paintV.Add(i);   // MFD quads keep their 0-1 screen UVs
                for (int k = 0; k < orderedNames.Length; k++)                    // 2026-11-01 cockpit art atlas + fal props keep their own UVs
                    if (orderedNames[k] == "bk_art" || orderedNames[k] == "ck_art" || orderedNames[k].StartsWith("pr_")) foreach (var i in m.GetIndices(k)) paintV.Add(i);
                if (uv0.Count == m.vertexCount)
                {
                    for (int i = 0; i < uv0.Count; i++) if (!paintV.Contains(i)) uv0[i] = uv1[i];
                    m.SetUVs(0, uv0);
                }
                // 1.8.3: stock aircraft_structure tints by vertex colour (stock exterior structure submeshes: 92/92/92, smallFighter1 fuselage /
                // intake); stock texel scale ~1.2-2 m per UV unit, our detail UV is 2 m per unit -> x 1.25 (GA-25X 0.3.1 cabin precedent)
                int ks = Array.IndexOf(orderedNames, "structure");
                if (StockStructure && ks >= 0 && uv0.Count == m.vertexCount)
                {
                    var cols = Enumerable.Repeat(new Color32(255, 255, 255, 255), m.vertexCount).ToArray();
                    foreach (var i in new HashSet<int>(m.GetIndices(ks))) { cols[i] = new Color32(92, 92, 92, 255); if (!paintV.Contains(i)) uv0[i] = uv1[i] * 1.25f; }
                    m.colors32 = cols; m.SetUVs(0, uv0);
                }
            }
            generatedMeshes.Add(m);
            return m;
        }

        static Mesh NewMesh(string name, Vector3[] v, int[] tri, Vector2[] uv = null)
        {
            var m = new Mesh { name = name, vertices = v, triangles = tri };
            if (uv != null) m.uv = uv;
            m.RecalculateNormals(); m.RecalculateBounds();
            generatedMeshes.Add(m);
            return m;
        }

        // Convex collider source: the part's own render mesh baked into the part's frame (no stock collider meshes).
        static Mesh BakeCollider(Transform part, string name, params MeshFilter[] mfs)
        {
            var v = new List<Vector3>(); var tri = new List<int>();
            foreach (var mf in mfs)
            {
                var sm = mf.sharedMesh; int b = v.Count;
                foreach (var p in sm.vertices) v.Add(part.InverseTransformPoint(mf.transform.TransformPoint(p)));
                for (int s = 0; s < sm.subMeshCount; s++) tri.AddRange(sm.GetTriangles(s).Select(i => i + b));
            }
            var m = new Mesh { name = name, indexFormat = v.Count > 65000 ? UnityEngine.Rendering.IndexFormat.UInt32 : UnityEngine.Rendering.IndexFormat.UInt16 };
            m.SetVertices(v); m.SetTriangles(tri, 0); m.RecalculateBounds();
            generatedMeshes.Add(m);
            return m;
        }

        static Mesh DiscMesh(string name, float r, int seg)
        {
            var v = new List<Vector3> { Vector3.zero }; var uv = new List<Vector2> { new Vector2(0.5f, 0.5f) }; var t = new List<int>();
            for (int i = 0; i <= seg; i++)
            {
                float a = i * Mathf.PI * 2f / seg;
                v.Add(new Vector3(Mathf.Cos(a) * r, Mathf.Sin(a) * r, 0)); uv.Add(new Vector2(0.5f + Mathf.Cos(a) * 0.5f, 0.5f + Mathf.Sin(a) * 0.5f));
            }
            for (int i = 1; i <= seg; i++) { t.AddRange(new[] { 0, i, i + 1 }); t.AddRange(new[] { 0, i + 1, i }); }
            return NewMesh(name, v.ToArray(), t.ToArray(), uv.ToArray());
        }

        static Mesh CylinderMesh(string name, float r, float halfT, int seg)
        {
            var v = new List<Vector3>(); var t = new List<int>();
            for (int i = 0; i < seg; i++)
            {
                float a = i * Mathf.PI * 2f / seg;
                v.Add(new Vector3(Mathf.Cos(a) * r, Mathf.Sin(a) * r, -halfT)); v.Add(new Vector3(Mathf.Cos(a) * r, Mathf.Sin(a) * r, halfT));
            }
            for (int i = 0; i < seg; i++)
            {
                int a = 2 * i, b = 2 * ((i + 1) % seg);
                t.AddRange(new[] { a, b, a + 1, b, b + 1, a + 1 });
                if (i > 0 && i < seg - 1) { t.AddRange(new[] { 0, b, 2 * (i + 2) % (2 * seg) }); }
            }
            return NewMesh(name, v.ToArray(), t.ToArray());
        }

        static Mesh OctaMesh(string name, float r)
        {
            var v = new[] { new Vector3(r, 0, 0), new Vector3(-r, 0, 0), new Vector3(0, r, 0), new Vector3(0, -r, 0), new Vector3(0, 0, r), new Vector3(0, 0, -r) };
            var t = new[] { 0, 2, 4, 2, 1, 4, 1, 3, 4, 3, 0, 4, 2, 0, 5, 1, 2, 5, 3, 1, 5, 0, 3, 5 };
            return NewMesh(name, v, t);
        }

        // The tac-screen UI renders to a 1024x512 texture: the map/radar fills u 0-0.79, and the strip u 0.79-1 holds the
        // side panels rotated +90 deg (tacScreen_cricket EngPanel/BasicFlightInstrument/propGauge). The CI-22's screen mesh
        // (COIN_targetScreen) shows the map on one quad and each panel on its own small quad with rotated UVs; a plain 0-1
        // quad shows the panels on their side. This rebuilds a 0-1 screen quad the same way: the map letterboxed on the
        // left, the three panels stacked upright on the right (prop/fuel, engines, attitude top to bottom), and a black
        // backing (submesh 1) behind the gaps.
        static Mesh TacScreenMesh(Mesh src, string name)
        {
            var sv = src.vertices; var suv = src.uv;
            int Near(Vector2 q) { int b = 0; for (int i = 1; i < suv.Length; i++) if ((suv[i] - q).sqrMagnitude < (suv[b] - q).sqrMagnitude) b = i; return b; }
            Vector3 o = sv[Near(Vector2.zero)], ex = sv[Near(Vector2.right)] - o, ey = sv[Near(Vector2.up)] - o;
            float W = ex.magnitude, H = ey.magnitude;
            var st = src.GetTriangles(0);
            var n = Vector3.Cross(sv[st[1]] - sv[st[0]], sv[st[2]] - sv[st[0]]).normalized;   // the side the source triangles face
            bool flip = Vector3.Dot(Vector3.Cross(ex, ey), n) < 0;
            const float lift = 0.0006f;   // content sits just in front of the black backing
            // texture regions: (u lo, u hi, v lo, v hi); panels rotated: screen right -> +v, screen up -> -u
            var panels = new[] { (0.802f, 0.983f, 0.718f, 0.979f), (0.801f, 0.985f, 0.390f, 0.697f), (0.789f, 0.983f, 0.025f, 0.341f) };   // attitude u lo 0.802 -> 0.789: live RT dump (1.1.1 test) shows its frame and heading text from u 0.793
            float Aspect((float, float, float, float) r) => (r.Item4 - r.Item3) * 512f / ((r.Item2 - r.Item1) * 1024f);
            float g = 0.004f, sumInv = panels.Sum(p => 1f / Aspect(p));
            float ws = (H - 4 * g) / sumInv;                             // panel column width
            float wm = W - ws - 3 * g, hm = Mathf.Min(H - 2 * g, wm / (0.79f * 1024f / 512f));
            var v = new List<Vector3>(); var uv = new List<Vector2>(); var t0 = new List<int>(); var t1 = new List<int>();
            Vector3 P(float x, float y, float z) => o + ex * (x / W) + ey * (y / H) + n * z;
            void Quad(List<int> tris, float x0, float y0, float x1, float y1, float z, Vector2 a, Vector2 b, Vector2 c, Vector2 d)
            {
                int i = v.Count;
                v.Add(P(x0, y0, z)); v.Add(P(x1, y0, z)); v.Add(P(x1, y1, z)); v.Add(P(x0, y1, z));
                uv.Add(a); uv.Add(b); uv.Add(c); uv.Add(d);
                if (flip) tris.AddRange(new[] { i, i + 2, i + 1, i, i + 3, i + 2 }); else tris.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
            }
            Quad(t1, 0, 0, W, H, 0, Vector2.zero, Vector2.right, Vector2.one, Vector2.up);
            float my = (H - hm) / 2;
            Quad(t0, g, my, g + wm, my + hm, lift, new Vector2(0.001f, 0), new Vector2(0.791f, 0), new Vector2(0.791f, 1), new Vector2(0.001f, 1));
            float px = W - g - ws, y = H - g;
            foreach (var r in panels)
            {
                float h = ws / Aspect(r);
                // corners (x0,y0),(x1,y0),(x1,y1),(x0,y1) -> (u hi, v lo),(u hi, v hi),(u lo, v hi),(u lo, v lo)
                Quad(t0, px, y - h, px + ws, y, lift, new Vector2(r.Item2, r.Item3), new Vector2(r.Item2, r.Item4), new Vector2(r.Item1, r.Item4), new Vector2(r.Item1, r.Item3));
                y -= h + g;
            }
            var m = new Mesh { name = name };
            m.SetVertices(v); m.SetUVs(0, uv); m.subMeshCount = 2; m.SetTriangles(t0, 0); m.SetTriangles(t1, 1);
            m.RecalculateNormals(); m.RecalculateTangents(); m.RecalculateBounds();
            generatedMeshes.Add(m);
            return m;
        }

        // round 6: the same mesh with every triangle's winding reversed and normals negated (cockpit-layer glass seen from inside)
        static Mesh InwardMesh(Mesh src, string name)
        {
            var m = Object.Instantiate(src); m.name = name;
            for (int sm = 0; sm < m.subMeshCount; sm++) { var t = m.GetTriangles(sm); for (int i = 0; i < t.Length; i += 3) { var x = t[i + 1]; t[i + 1] = t[i + 2]; t[i + 2] = x; } m.SetTriangles(t, sm); }
            var nn = m.normals; for (int i = 0; i < nn.Length; i++) nn[i] = -nn[i]; m.normals = nn;
            m.RecalculateBounds();
            generatedMeshes.Add(m);
            return m;
        }

        static Vector3 J3(Newtonsoft.Json.Linq.JToken t) => new Vector3((float)t[0], (float)t[1], (float)t[2]);

        static Mesh QuadMesh(string name, float w, float h)
        {
            return NewMesh(name, new[] { new Vector3(-w, -h, 0), new Vector3(w, -h, 0), new Vector3(w, h, 0), new Vector3(-w, h, 0) },
                new[] { 0, 2, 1, 0, 3, 2 }, new[] { Vector2.zero, Vector2.right, Vector2.one, Vector2.up });
        }

        // ------------------------------------------------------------------ from B25HBuild.cs: model lookup
        static Transform ContractFind(params string[] names)
        {
            var all = root.GetComponentsInChildren<Transform>(true);
            foreach (var n in names) { var t = all.FirstOrDefault(x => x.name == n); if (t != null) return t; }
            return null;
        }

        static Transform Find(string n)
        {
            var t = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == n);
            if (t == null) throw new Exception("model object not found: " + n);
            return t;
        }

        static GameObject NewGO(string name, Transform parent, Vector3 worldPos, Quaternion worldRot, int layer = 14)
        {
            var g = new GameObject(name) { layer = layer };
            g.transform.SetParent(parent, false);
            g.transform.SetPositionAndRotation(worldPos, worldRot);
            return g;
        }
        // ------------------------------------------------------------------ from B25HBuild.cs: part renderers
        static IEnumerable<MeshRenderer> PartRenderers(GameObject partGo)
        {
            var result = new List<MeshRenderer>();
            void Walk(Transform t)
            {
                if (t != partGo.transform && t.GetComponent<AeroPart>() != null) return;
                if (t != partGo.transform && partGO.Values.Contains(t.gameObject)) return;
                var r = t.GetComponent<MeshRenderer>(); if (r) result.Add(r);
                foreach (Transform c in t) Walk(c);
            }
            Walk(partGo.transform);
            return result;
        }
        // ------------------------------------------------------------------ from B25HBuild.cs: bounds
        static Bounds WorldBounds(MeshCollider c)
        {
            var b = c.sharedMesh.bounds; var t = c.transform;
            var wb = new Bounds(t.TransformPoint(b.center), Vector3.zero);
            for (int i = 0; i < 8; i++)
                wb.Encapsulate(t.TransformPoint(b.center + Vector3.Scale(b.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1))));
            return wb;
        }

        // ------------------------------------------------------------------ from B25HBuild.cs: particles
        static ParticleSystem CopyParticle(ParticleSystem src, Transform parent, Vector3 pos, string name)
        {
            var g = NewGO(name, parent, pos, parent.rotation * Quaternion.Inverse(src.transform.parent ? src.transform.parent.rotation : Quaternion.identity) * src.transform.rotation);
            g.transform.rotation = src.transform.rotation; // keep the stock emitter's orientation (they are authored in aircraft space)
            var ps = g.AddComponent<ParticleSystem>();
            EditorUtility.CopySerialized(src, ps);
            Remap(ps);
            var psr = g.GetComponent<ParticleSystemRenderer>();
            EditorUtility.CopySerialized(src.GetComponent<ParticleSystemRenderer>(), psr);
            Remap(psr);
            ourParticles.Add(ps);
            return ps;
        }

        // ------------------------------------------------------------------ from B25HBuild.cs: blade damage
        static Mesh TruncatedBlade(Mesh src, float maxY, string name)
        {
            var m = Object.Instantiate(src); m.name = name;
            m.vertices = src.vertices.Select(v => new Vector3(v.x, Mathf.Min(v.y, maxY), v.z)).ToArray();
            m.RecalculateBounds(); generatedMeshes.Add(m);
            return m;
        }
        // ------------------------------------------------------------------ from B25HBuild.cs: mounts + muzzle particles
        static WeaponMount Mount(string n) => Asset<WeaponMount>($"MonoBehaviour/{n}_PLACEHOLDER.asset");

        static ParticleSystem[] CopyMuzzleParticles(Gun template, Transform muzzle)
        {
            var src = (ParticleSystem[])G(template, "muzzleParticles") ?? new ParticleSystem[0];
            return src.Where(p => p != null).Select(p => CopyParticle(p, muzzle, muzzle.position, muzzle.name + "_" + p.name)).Select(p => { p.transform.rotation = muzzle.rotation; return p; }).ToArray();
        }

        // ------------------------------------------------------------------ from B25HBuild.cs: lookups
        static Transform TryFind(string n) => n == null ? null : root.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == n);

        // Components that write localEulerAngles ABSOLUTELY (Cockpit.Throttle, HighLiftDevice moving parts) need the
        // driven transform to rest at identity in its parent. If the model object does not, insert a static frame
        // (same pose) and a driven child (identity) above it.
        static Transform DrivenFrame(Transform t)
        {
            if (Quaternion.Angle(t.localRotation, Quaternion.identity) < 0.01f) return t;
            var frame = NewGO(t.name + "_frame", t.parent, t.position, t.rotation, t.gameObject.layer);
            var drv = NewGO(t.name + "_drive", frame.transform, t.position, t.rotation, t.gameObject.layer);
            t.SetParent(drv.transform, true);
            return drv.transform;
        }
        // ------------------------------------------------------------------ from B25HBuild.cs: damage diagram + map icon
        // =================================================================== damage diagram + map icon (generated from our model)
        // Stock pattern (CAS1_statusDisplay.prefab, StatusDisplay.cs, PartStatusDisplay.cs): a 300x300 UI prefab parented to
        // FlightHud.statusAnchor; root Image = line-art background (StatusDisplay.aircraftBackground); one Image per part whose
        // GameObject NAME equals the UnitPart's GameObject name (PartStatusDisplay.FindPart); the game sets each part image's
        // green channel/alpha from part hit points (yellow -> red), and a detached part turns (0.7, 0, 0.25). Failure indicators
        // are GameObjects named after IReportDamage failure messages ("LEFT ENGINE FAILURE"...), shown on report.
        // Map icon (UnitDefinition.mapIcon, UnitMapIcon.cs:53): white silhouette on transparent, 256x256, nose up, tinted by IFF.
        const string RepoIcons = @"C:\Users\User\Nuclear Option B-25\assets\ui";       // 1.4.0 weapon icons (blender/nimrod/make_weapon_icons.py)
        const string RepoUI = @"C:\Users\User\Nuclear Option B-25\assets\ui_fd32";   // no hand art: generated from the model
        static Rect diagramFrame;  // world XZ square drawn by the diagram/icon

        class Raster
        {
            public int n; public float[] depth; public short[] id;
            public Raster(int n) { this.n = n; depth = Enumerable.Repeat(float.NegativeInfinity, n * n).ToArray(); id = Enumerable.Repeat((short)-1, n * n).ToArray(); }
            public void Tri(Vector3 a, Vector3 b, Vector3 c, short pid)
            {
                Vector2 P(Vector3 w) => new Vector2((w.x - diagramFrame.xMin) / diagramFrame.width * n, (w.z - diagramFrame.yMin) / diagramFrame.height * n);
                Vector2 pa = P(a), pb = P(b), pc = P(c);
                float area = (pb.x - pa.x) * (pc.y - pa.y) - (pc.x - pa.x) * (pb.y - pa.y);
                if (Mathf.Abs(area) < 1e-6f) return;
                int x0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(pa.x, Mathf.Min(pb.x, pc.x)))), x1 = Mathf.Min(n - 1, Mathf.CeilToInt(Mathf.Max(pa.x, Mathf.Max(pb.x, pc.x))));
                int y0 = Mathf.Max(0, Mathf.FloorToInt(Mathf.Min(pa.y, Mathf.Min(pb.y, pc.y)))), y1 = Mathf.Min(n - 1, Mathf.CeilToInt(Mathf.Max(pa.y, Mathf.Max(pb.y, pc.y))));
                for (int y = y0; y <= y1; y++)
                    for (int x = x0; x <= x1; x++)
                    {
                        float px = x + 0.5f, py = y + 0.5f;
                        float w0 = ((pb.x - px) * (pc.y - py) - (pc.x - px) * (pb.y - py)) / area;
                        float w1 = ((pc.x - px) * (pa.y - py) - (pa.x - px) * (pc.y - py)) / area;
                        float w2 = 1f - w0 - w1;
                        if (w0 < 0f || w1 < 0f || w2 < 0f) continue;
                        float h = w0 * a.y + w1 * b.y + w2 * c.y;
                        int i = y * n + x;
                        if (h > depth[i]) { depth[i] = h; id[i] = pid; }
                    }
            }
        }

        // world-space (root frame) triangles of one part's own render meshes (not child parts, not cockpit-layer copies, not glass)
        static IEnumerable<(Vector3, Vector3, Vector3)> PartTriangles(AeroPart p)
        {
            foreach (var mr in PartRenderers(p.gameObject))
            {
                if (mr.gameObject.layer == 3) continue;
                if (SeamCove1913 && mr.name.Contains(B25HTools.SeamCove1913.StripSuffix)) continue;   // 1.9.13: the hidden seam band stays out of the damage diagram / map icon
                if (mr.name.StartsWith("airbrake_")) continue;   // 1.9.12: the damage diagram and the map icon are drawn from the 1.9.11 meshes only (the airbrake panels and wells are 2-5 mm proud plates on fus_rear; with them a few edge pixels of three sprites moved)
                var mf = mr.GetComponent<MeshFilter>(); if (mf == null || mf.sharedMesh == null) continue;
                if (mr.sharedMaterials.Length > 0 && mr.sharedMaterials[0] == mats["propdisc"]) continue;
                var m = mf.sharedMesh; var v = m.vertices; var tr = mf.transform;
                var w = v.Select(x => root.transform.InverseTransformPoint(tr.TransformPoint(x))).ToArray();
                for (int s = 0; s < m.subMeshCount; s++)
                {
                    if (s < mr.sharedMaterials.Length && mr.sharedMaterials[s] == mats["glass"]) continue;
                    if (m.GetTopology(s) != MeshTopology.Triangles) continue;
                    var t = m.GetTriangles(s);
                    for (int i = 0; i + 2 < t.Length; i += 3) yield return (w[t[i]], w[t[i + 1]], w[t[i + 2]]);
                }
            }
        }

        // A PNG from the repo (texture worker's UI art) copied into the mod folder and imported as a sprite.
        static Sprite ImportRepoSprite(string src, string name)
        {
            var path = $"{Folder}/Textures/{name}.png";
            File.Copy(src, path, true);
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
            var ti = (TextureImporter)AssetImporter.GetAtPath(path);
            ti.textureType = TextureImporterType.Sprite; ti.spriteImportMode = SpriteImportMode.Single; ti.alphaIsTransparency = true;
            ti.mipmapEnabled = false; ti.wrapMode = TextureWrapMode.Clamp; ti.spritePixelsPerUnit = 100;
            ti.textureCompression = TextureImporterCompression.Uncompressed;
            ti.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Sprite>(path);
        }

        static Sprite SaveSprite(Color32[] px, int n, string name, bool compress)
        {
            var t = new Texture2D(n, n, TextureFormat.RGBA32, false); t.SetPixels32(px); t.Apply();
            var path = $"{Folder}/Textures/{name}.png";
            File.WriteAllBytes(path, t.EncodeToPNG());
            Object.DestroyImmediate(t);
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
            var ti = (TextureImporter)AssetImporter.GetAtPath(path);
            ti.textureType = TextureImporterType.Sprite; ti.spriteImportMode = SpriteImportMode.Single; ti.alphaIsTransparency = true;
            ti.mipmapEnabled = false; ti.wrapMode = TextureWrapMode.Clamp; ti.spritePixelsPerUnit = 100;
            ti.textureCompression = compress ? TextureImporterCompression.Compressed : TextureImporterCompression.Uncompressed;
            ti.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Sprite>(path);
        }

        // Supersampled mask -> white RGBA with coverage alpha
        static Color32[] Downsample(Func<int, bool> on, int big, int f)
        {
            int n = big / f; var px = new Color32[n * n];
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    int c = 0;
                    for (int j = 0; j < f; j++) for (int i = 0; i < f; i++) if (on((y * f + j) * big + x * f + i)) c++;
                    px[y * n + x] = new Color32(255, 255, 255, (byte)(255 * c / (f * f)));
                }
            return px;
        }

        static Sprite statusBackground; static readonly Dictionary<string, Sprite> statusParts = new Dictionary<string, Sprite>(); static Sprite mapIconSprite;
        static readonly Dictionary<string, Vector2> diagramPos = new Dictionary<string, Vector2>(); // part centre in diagram units (-0.5..0.5)

        static void BuildDiagramSprites()
        {
            statusParts.Clear(); diagramPos.Clear();
            var plist = parts.Values.ToList();
            // frame: square around the aircraft's top-down bounds (+4 % margin), centred
            var all = plist.SelectMany(PartTriangles).SelectMany(t => new[] { t.Item1, t.Item2, t.Item3 }).ToList();
            float minX = all.Min(v => v.x), maxX = all.Max(v => v.x), minZ = all.Min(v => v.z), maxZ = all.Max(v => v.z);
            float S = Mathf.Max(maxX - minX, maxZ - minZ) * 1.04f;
            diagramFrame = new Rect((minX + maxX) / 2 - S / 2, (minZ + maxZ) / 2 - S / 2, S, S);
            L($"diagram frame: {S:F2} m square centred ({diagramFrame.center.x:F2}, {diagramFrame.center.y:F2}); aircraft span {maxX - minX:F2} m, length {maxZ - minZ:F2} m");

            // union (depth-sorted part ids) at 1024 -> outline at 512 (part boundaries + silhouette edge)
            const int BIG = 1024;
            var u = new Raster(BIG);
            for (short k = 0; k < plist.Count; k++) foreach (var (a, b, c) in PartTriangles(plist[k])) u.Tri(a, b, c, k);
            bool Edge(int i)
            {
                int x = i % BIG, y = i / BIG, me = u.id[i];
                if (me < 0) return false;
                for (int d = 1; d <= 2; d++)
                    foreach (var (dx, dy) in new[] { (d, 0), (-d, 0), (0, d), (0, -d) })
                    {
                        int xx = x + dx, yy = y + dy;
                        if (xx < 0 || yy < 0 || xx >= BIG || yy >= BIG) return true;
                        if (u.id[yy * BIG + xx] != me) return true;
                    }
                return false;
            }
            var bgPx = Downsample(Edge, BIG, 2);
            for (int i = 0; i < bgPx.Length; i++) bgPx[i].a = (byte)Mathf.Min(255, bgPx[i].a * 2);
            // texture worker's diagram art (assets/ui) when present: fitted bbox-to-bbox onto the same frame
            var art = Directory.Exists(RepoUI) && !File.Exists(Path.Combine(RepoUI, "fd32_status_layout.json")) ? Directory.GetFiles(RepoUI, "*.png").FirstOrDefault(f => { var n = Path.GetFileName(f).ToLowerInvariant(); return n.Contains("diagram") || n.Contains("status") || n.Contains("damage"); }) : null;
            if (art != null)
            {
                var fitted = FitArt(art, 512, u, BIG);
                if (fitted != null) { bgPx = fitted; L($"status background: texture worker art {Path.GetFileName(art)} (bbox-fitted to the model frame)"); }
            }
            else L("status background: generated line art from the model (no assets/ui diagram art)");
            statusBackground = SaveSprite(bgPx, 512, "fd32_status", false);

            // one filled sprite per part (256, 2x supersampled)
            const int PB = 512;
            for (short k = 0; k < plist.Count; k++)
            {
                var r = new Raster(PB);
                foreach (var (a, b, c) in PartTriangles(plist[k])) r.Tri(a, b, c, k);
                var px = Downsample(i => r.id[i] >= 0, PB, 2);
                statusParts[plist[k].name] = SaveSprite(px, 256, "fd32_status_" + plist[k].name, true);
                // centre of the part's own silhouette, for failure indicators
                double sx = 0, sy = 0; int cnt = 0;
                for (int i = 0; i < r.id.Length; i++) if (r.id[i] >= 0) { sx += i % PB; sy += i / PB; cnt++; }
                diagramPos[plist[k].name] = cnt > 0 ? new Vector2((float)(sx / cnt / PB - 0.5), (float)(sy / cnt / PB - 0.5)) : Vector2.zero;
            }

            // map icon: filled silhouette, 256 (texture worker's icon when present)
            var icon = Path.Combine(RepoUI, "fd32_map_icon.png");
            if (File.Exists(icon)) { mapIconSprite = ImportRepoSprite(icon, "fd32_mapicon"); L("map icon: texture worker art fd32_map_icon.png"); }
            else { mapIconSprite = SaveSprite(Downsample(i => u.id[i] >= 0, BIG, 4), 256, "fd32_mapicon", false); L("map icon: generated silhouette from the model"); }
            L($"diagram: background + {statusParts.Count} part sprites + map icon");
        }

        // Load an art PNG, take its opaque bounding box and fit it onto the model silhouette's bounding box in an n x n frame.
        static Color32[] FitArt(string file, int n, Raster u, int big)
        {
            var src = new Texture2D(2, 2, TextureFormat.RGBA32, false);
            if (!src.LoadImage(File.ReadAllBytes(file))) return null;
            var sp = src.GetPixels32(); int w = src.width, h = src.height;
            int ax0 = w, ay0 = h, ax1 = -1, ay1 = -1;
            for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) if (sp[y * w + x].a > 20) { ax0 = Mathf.Min(ax0, x); ax1 = Mathf.Max(ax1, x); ay0 = Mathf.Min(ay0, y); ay1 = Mathf.Max(ay1, y); }
            int mx0 = big, my0 = big, mx1 = -1, my1 = -1;
            for (int i = 0; i < u.id.Length; i++) if (u.id[i] >= 0) { int x = i % big, y = i / big; mx0 = Mathf.Min(mx0, x); mx1 = Mathf.Max(mx1, x); my0 = Mathf.Min(my0, y); my1 = Mathf.Max(my1, y); }
            if (ax1 < 0 || mx1 < 0) { Object.DestroyImmediate(src); return null; }
            var px = new Color32[n * n];
            float f = (float)n / big;
            for (int y = 0; y < n; y++)
                for (int x = 0; x < n; x++)
                {
                    float cx = x + 0.5f, cy = y + 0.5f;
                    if (cx < mx0 * f || cx > (mx1 + 1) * f || cy < my0 * f || cy > (my1 + 1) * f) continue;
                    float fx = Mathf.InverseLerp(mx0 * f, (mx1 + 1) * f, cx), fy = Mathf.InverseLerp(my0 * f, (my1 + 1) * f, cy);
                    int sx = Mathf.Clamp(Mathf.RoundToInt(Mathf.Lerp(ax0, ax1, fx)), 0, w - 1), sy = Mathf.Clamp(Mathf.RoundToInt(Mathf.Lerp(ay0, ay1, fy)), 0, h - 1);
                    var c = sp[sy * w + sx];
                    px[y * n + x] = new Color32(255, 255, 255, c.a); // the game tints: keep white, alpha from the art
                }
            Object.DestroyImmediate(src);
            return px;
        }

        // Our StatusDisplay prefab, built from scratch with the stock CAS1 layout values (CAS1_statusDisplay.prefab: root 300x300,
        // anchor (1,0), pivot (1,-0.05), position (0,-30.1); part images colour (1,1,0,1), redStatusThreshold 30, material
        // Text_additive). The placeholder prefab itself cannot be copied: its UI Image components reference the game's
        // UnityEngine.UI.dll by fileID and are missing scripts in this editor project.
        static readonly string[] FailureIndicators = { "ENGINE FAILURE" }; // TurbineEngine.failureMessage (set in Engine())
        static GameObject BuildStatusDisplayPrefab()
        {
            var uiMat = Asset<Material>("Material/Text_additive_PLACEHOLDER.mat");
            UnityEngine.UI.Image Img(GameObject g, Sprite sp, Color c)
            {
                g.AddComponent<CanvasRenderer>();
                var im = g.AddComponent<UnityEngine.UI.Image>();
                im.sprite = sp; im.color = c; im.material = uiMat; im.raycastTarget = false; im.preserveAspect = true;
                return im;
            }
            var inst = new GameObject("FD32_statusDisplay", typeof(RectTransform)) { layer = 5 };
            var rt = (RectTransform)inst.transform;
            rt.anchorMin = rt.anchorMax = new Vector2(1f, 0f); rt.pivot = new Vector2(1f, -0.05f); rt.sizeDelta = new Vector2(300f, 300f); rt.anchoredPosition = new Vector2(0f, -30.1f);
            var list = new List<PartStatusDisplay>();
            var failures = new List<GameObject>();
            UnityEngine.UI.Image rootImg;
            StatusDisplay sd;
            Vector2 V2(Newtonsoft.Json.Linq.JToken t) => new Vector2((float)t[0], (float)t[1]);
            var layoutPath = Path.Combine(RepoUI, "fd32_status_layout.json");
            var covered = new HashSet<string>();
            if (File.Exists(layoutPath))
            {
                // texture worker's art + layout (assets/ui/fd32_status_layout.json): stock-style per-part sprites, mirrored L/R
                var lay = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(layoutPath));
                var spriteCache = new Dictionary<string, Sprite>();
                Sprite Spr(string rel)
                {
                    if (rel == null) return null;
                    if (!spriteCache.TryGetValue(rel, out var sp)) spriteCache[rel] = sp = ImportRepoSprite(Path.Combine(RepoUI, rel), Path.GetFileNameWithoutExtension(rel));
                    return sp;
                }
                rootImg = Img(inst, Spr((string)lay["root"]["sprite"]), Color.white);
                sd = inst.AddComponent<StatusDisplay>();
                float thrL = lay["redStatusThreshold"] != null ? (float)lay["redStatusThreshold"] : 30f;
                foreach (var pj in (Newtonsoft.Json.Linq.JArray)lay["parts"])
                {
                    var pn = (string)pj["name"];
                    if (!statusParts.ContainsKey(pn)) { L($"WARN status layout part {pn} is not a part of this build, skipped"); continue; }
                    var g = new GameObject(pn, typeof(RectTransform)) { layer = 5 };
                    var grt = (RectTransform)g.transform; grt.SetParent(rt, false);
                    grt.anchorMin = grt.anchorMax = pj["anchor"] != null ? V2(pj["anchor"]) : new Vector2(0.5f, 0.5f);
                    grt.pivot = pj["pivot"] != null ? V2(pj["pivot"]) : new Vector2(0.5f, 0.5f);
                    grt.sizeDelta = V2(pj["sizeDelta"]); grt.anchoredPosition = V2(pj["anchoredPosition"]);
                    var sc = pj["localScale"]; grt.localScale = new Vector3((float)sc[0], (float)sc[1], (float)sc[2]);
                    var im = Img(g, Spr((string)pj["sprite"]), new Color(1f, 1f, 0f, 1f)); im.preserveAspect = false;
                    list.Add(new PartStatusDisplay { partImage = im, redStatusThreshold = thrL });
                    covered.Add(pn);
                }
                var fl = lay["failure_indicators"] as Newtonsoft.Json.Linq.JArray;
                if (fl != null)
                    foreach (var fj in fl)
                    {
                        var g = new GameObject((string)fj["name"], typeof(RectTransform)) { layer = 5 };
                        var grt = (RectTransform)g.transform; grt.SetParent(rt, false);
                        grt.anchorMin = grt.anchorMax = new Vector2(0.5f, 0.5f);
                        grt.sizeDelta = V2(fj["sizeDelta"]); grt.anchoredPosition = V2(fj["anchoredPosition"]);
                        if (fj["localScale"] != null) { var sc = fj["localScale"]; grt.localScale = new Vector3((float)sc[0], (float)sc[1], (float)sc[2]); }
                        Img(g, null, Color.red).preserveAspect = false;
                        failures.Add(g);
                    }
                L($"status display: texture worker layout ({covered.Count} parts, {failures.Count} failure indicators)");
            }
            else
            {
                rootImg = Img(inst, statusBackground, Color.white);
                sd = inst.AddComponent<StatusDisplay>();
            }
            S(sd, "aircraftBackground", rootImg);
            foreach (var kv in statusParts.Where(k => !covered.Contains(k.Key)).OrderBy(k => k.Key == "B25H" ? 0 : 1))
            {
                if (covered.Count > 0) L($"WARN status layout has no image for part {kv.Key}: using the generated full-frame sprite");
                var g = new GameObject(kv.Key, typeof(RectTransform)) { layer = 5 };
                var grt = (RectTransform)g.transform; grt.SetParent(rt, false);
                grt.anchorMin = Vector2.zero; grt.anchorMax = Vector2.one; grt.sizeDelta = Vector2.zero; grt.anchoredPosition = Vector2.zero; grt.pivot = new Vector2(0.5f, 0.5f);
                list.Add(new PartStatusDisplay { partImage = Img(g, kv.Value, new Color(1f, 1f, 0f, 1f)), redStatusThreshold = 30f });
            }
            SetSeq(sd, "statusDisplays", list);
            foreach (var fname in failures.Count > 0 ? new string[0] : FailureIndicators)
            {
                var g = new GameObject(fname, typeof(RectTransform)) { layer = 5 };
                var grt = (RectTransform)g.transform; grt.SetParent(rt, false);
                grt.anchorMin = grt.anchorMax = new Vector2(0.5f, 0.5f); grt.sizeDelta = new Vector2(10f, 18f);
                var part = "fus_engine";
                grt.anchoredPosition = diagramPos.TryGetValue(part, out var dp) ? dp * rt.sizeDelta.x : Vector2.zero;
                Img(g, null, Color.red).preserveAspect = false;
                failures.Add(g);
            }
            SetSeq(sd, "failureIndicators", failures);
            var fnames = string.Join(", ", failures.Select(f => f.name));
            var prefab = PrefabUtility.SaveAsPrefabAsset(inst, Folder + "/FD32_statusDisplay.prefab");
            Object.DestroyImmediate(inst);
            L($"status display prefab: {list.Count} part images, failure indicators {fnames}");
            return prefab;
        }

    }
}
