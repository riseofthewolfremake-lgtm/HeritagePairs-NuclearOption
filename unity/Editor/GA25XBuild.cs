// GA-25X for Nuclear Option: builds the GA-25X (the upgraded B-25H airframe) from our own GA-25X model into the family addon
// `heritage_pairs` (subfolder ga25x, FamilyBuild.cs; FamilyBuild.Combined = false: its own addon `ga25x` as in 0.1.0).
//
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FamilyBuild.BuildAll family_build   (B-25H + GA-25X + family .nobp)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 GA25XBuild.Build ga25x_build   (GA-25X assets + check + re-pack the family)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 GA25XBuild.Check ga25x_check   (check only)
//
// A COPY of B25HBuild.cs (not a refactor: the B-25H generator is left untouched), changed for the GA-25X. Everything is
// generated from the user's own files at build time:
//   - our model:    <repo>\assets\model_ga25x\ga25x.fbx (+ ga25x_propdisc.fbx, ga25x_contract.json), copied into
//                   Assets/GA25XSource, which is NOT part of the mod
//   - our textures: <repo>\assets\textures_ga25x (skin + liveries); shared tiling/gauge/prop-blur art from assets\textures_v2
//   - stock game components (AssetRipper placeholders in _donotship) are used only as STARTING VALUES (same method as
//     the B-25H); stock assets that stay referenced (audio, effects, weapon mounts/infos, laser beam mesh/material, pilot
//     figure, tac-screen UI) are placeholders that Blueprinter resolves to the game's own copies at runtime.
// Design, every value and its stock source: <repo>\docs\ga25x_design.md
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
    public static class GA25XBuild
    {
        // ------------------------------------------------------------------ paths and identity
        const string ModName = "ga25x";
        const string DisplayName = "GA-25X";
        const string Version = "0.3.0";
        const string Folder = FamilyBuild.Combined ? FamilyBuild.FamilyRoot + "/ga25x" : "Assets/Blueprinter/Mods/" + ModName;   // one family addon (FamilyBuild.cs) or the old single addon
        const string OutFolder = @"C:\Users\User\nuclearoption-ref\build\ga25x";
        const string RepoModel = @"C:\Users\User\Nuclear Option B-25\assets\model_ga25x\ga25x.fbx";
        const string RepoTextures = @"C:\Users\User\Nuclear Option B-25\assets\textures_ga25x";
        const string RepoSharedTextures = @"C:\Users\User\Nuclear Option B-25\assets\textures_v2"; // our own B-25H tiling/gauge/prop-blur art (read only)
        const string SrcDir = "Assets/GA25XSource"; // model import lives outside the mod folder, never shipped
        const string DNS = "Assets/Blueprinter/_donotship";
        const string JsonKey = "GA25X";
        const string LogPath = @"C:\Users\User\nuclearoption-ref\unitylogs\ga25x_check_table.txt";

        // ------------------------------------------------------------------ feature flags
        // Spec items built from mechanisms already proven (stock aircraft or the B-25H) are ON; mechanisms not proven on an
        // aircraft yet are marked "probe" so the game worker can switch them independently. Speculative extras default OFF.
        const bool OwnCannonWeaponInfo = true;   // own copy of Gun76mm_Guided ("76mm Cannon"), boresight on (fixed nose gun)
        const bool KeepFlareEjector = true;
        const bool StockHUDExtras = true;        // CI-22 COIN_HUDExtras (prop aircraft HUD apps), as the B-25H
        const bool OwnPropBlur = true;
        const bool CockpitEmission1914 = true;      // 1.9.14: lit annunciator lamps / LED digits of the panel art glow (emission map)
        const float CockpitEmissionGain1914 = 0.9f;
        const bool CockpitAnimators = true;      // side sticks (Cockpit.Joystick), pedals (ControlSurface yaw), throttle levers
        const bool MFDScreens = true;
        const bool TwoCrew = true;               // pilot + weapons officer, bail-out hatches as stock Canopy components
        // 1.8.0 (user: the AI never uses the cannon or guns on ground targets; the stock A-19 strafes fine): both false, as the stock A-19 gun
        // (Gun30mm_Rotary targetRequirements.minAltitude 0). AI floor minimumRadarAlt 300 (GunshipAITuning) kept; see B25HBuild.cs 1.8.0 note.
        const bool FixedGunsAirOnlyForAI = false; // 1.8.0: false (true = 20 mm info minAltitude 150)
        const bool CannonAirOnlyForAI = false;    // 1.8.0: false. Old note:    // 76 mm vs ground targets makes the AI strafe (UsingFixedGuns): in game 0.1.0 the "Gunship" AI pulled out of its 3rd 76 mm pass at 3 m AGL and was lost. true = B-25H-safe (AI: 76 mm only vs aircraft)
        const bool TacScreenPanels = true;
        const bool LaserTurret = true;           // dorsal Turret + stock Laser values (LaserTrailer1 pattern on our airframe; probe)
        const bool LaserOnlyDefensive = true;
        const bool CockpitHideCanopyGlass = true; // in game 0.1.0 the gold exterior canopy glass (FastBomber1 values) was near-opaque from inside: the cockpit view was black. Hide it in cockpit view (exteriorRenderers), no interior copy
        const bool AutopilotCAS1Gains = false;   // (not needed: the AI spiral seen in game was the test helper overriding every GA-25X's inputs) AI flight-controller PIDs + reference airspeed of the stock A-19 (CAS1, 170 m/s) instead of the CI-22 (90): in game the GA-25X AI (up to 220 m/s) spiralled into the ground with the CI-22 gains
        const bool LaserAsMountPrefab = true;    // the Laser lives in the GA25X_laser mount prefab spawned on the turret aperture: Hardpoint.SpawnMount casts every BuiltInWeapon to Gun (InvalidCastException in game 0.1.0, aborted the whole weapon spawn)    // Turret.onlyDefensive: engage only missiles aimed at us
        const bool RadarInSkin = true;           // Radar (EW1 values, 40 km)
        const bool RadarJammerEW = true;         // RadarJammer (EW1 values: intensity 8, 50 kW)
        const bool OwnTailHookMount = true;      // own mount prefab (our hook mesh + stock TailHook values); false = stock TailHook_Multirole1 mount (probe)
        const bool HybridBoost = true;           // electric boost as a stock afterburner: per engine a Turbojet (~0 N) + JetNozzle whose Afterburner adds BoostThrust from 90 % throttle (stock jet detent), extra fuel, low IR, no flame
        const bool BoostInMaxPower = false;      // true: TurbineEngine.maxPower = turbine + motor (3.3 MW); false: 2.4 MW (the game has no boost)
        const bool ReverseThrustAI = false;      // ControlsFilter.ReverseThrust: AI landing goes FULL throttle after touchdown (only safe if props really reverse)
        const bool OwnStatusDisplay = true;
        const bool OwnMapIcon = true;
        // 1.8.1 (in game 1.8.0: the 76 mm info is the VL-49 Tarantula turret's, maxRange 25000; with gunsLinked every fixed gun fires
        // with it, so the 20 mm fired 932 / 956 rounds at > 2 km, up to 13.9 km, and the pass climb logic lifted the GA-25X to 800-1350 m
        // -> 28 deg dives; one GA-25X got down to 1 m at 65 m/s and was lost). true = 76 mm maxRange 3000 (stock A-19 Gun30mm_Rotary) and
        // AI floor 120 (stock A-19 50 / CI-22 30 start passes below slope 0.1; tools/flightmodel/gunpass.py). false = 25000 / 300.
        const bool GunRangeStock181 = true;
        const bool AIFloorStock181 = true;
        const bool GunshipAITuning = true;
        // 1.8.3 offline D (in game 1.8.2 probe P7: 0 x 76 mm / 0 x 20 mm at ground targets). The AI's station choice is effectiveness x
        // (0.5 beyond 1.2 x maxRange) (CombatAI.ChooseHQTarget / AnalyzeTarget): the stock AGM1 (0.643, 10 km) beat the 76 mm (0.63) even
        // inside 3.6 km, then the rockets / bombs outscored the halved 76 mm beyond 3.6 km; both GA-25X were lost before those ran out.
        // true = the 76 mm info's antiSurface 0.63 -> 1.2 (AI choice weight only): 76 mm inside 3.6 km and beyond 12 km, AGM1 at 3.6-12 km,
        // never rockets / bombs while the 76 mm has rounds (tools/flightmodel/ai_weapon_choice.py). Fire window 3000, floor 120 unchanged.
        const bool CannonGroundPriority183D = true;
        // 1.8.6 offline F (in game 1.8.4: an AI B-25H, same nose leg template, broke its nose leg taxiing on dirt at K92). Off tarmac
        // LandingGear breaks a leg when the dirt drag 2.5 depth^2 |v| (load / (contactArea x 1e4))^2 exceeds springRate; the AI taxis off
        // the paved surface with bang-bang full braking. Our nose kept the CAS1 template's contactArea 0.02 m2: full brake on dirt from
        // 10 m/s breaks it in the model (tools/flightmodel/nose_soft_ground.py). true = 0.05 (dirt only; tarmac / deck / runway and the
        // crash-landing compression break unchanged). The AI terrain values stay (min 37-61 m in game 1.8.4). false = 1.8.5.
        const bool NoseContact186F = true;
        const float NoseContactArea186F = 0.05f;
        // 1.8.7 offline F (in game 1.8.6 run 1: an AI GA-25X hit the ground pulling out of a strafing dive at 163 m/s, no damage first).
        // AIPilotCombatModes.UseFixedGuns is entered inside 2 x maxRange and left again beyond maxRange; in that band it climbs (height /
        // distance < 0.1 starts the climb, > 0.2 stops it) and NoTarget aims 11 deg up, so the real pass starts at 0.25-0.36 height /
        // distance (868 m at 2.4 km), the gravity lead of the 76 mm steepens it to ~30 deg, and the fixed 2 s break-off leaves ~134 m.
        // The pull-out was the FBW cap gLimitPositive 4 (pitch rate 4 g / V = 14 deg/s at 160 m/s). true = gLimitPositive 5 (the 0.1.0
        // value of the GA-25X's 5 g airframe): +12-15 m on the logged geometry in tools/flightmodel/ai_takeoff.py. Player: 25 % more pull
        // authority (HUD ~6 g). false = 1.8.6.
        const bool PullOut187F = true;
        const bool NuclearOptions = true;        // GPO-N (1.5 kt) in the bay (spec)
        // 0.2.0 (offline worker 2026-10-31; predictions: tools/flightmodel/ga25x_fm.py + fbw.py, docs/ga25x_design.md section 9).
        // ON because the next live test is exactly their probe (brief); each one switches back to the 0.1.0 behaviour.
        const bool FourPylonsPerWing = true;     // visual pass: Root + Mid pylon sets (appended after the 0.1.0 sets: loadout indices 0-7 unchanged)
        const bool LowDragAirframe = true;       // top speed: wing CD0 0.008 -> 0.0068, nacelle/engine/root drag areas -0.12 m^2, blade efficiency 0.38 -> 0.42
        const bool StolFlaps = true;             // flaps: HighLiftDevice on the wing panels (stock CAS1 wing2 / Multirole1 wing1 pattern: +area, lift frame +4 deg); the
                                                 // flap parts only animate (0.1.0 rotated the flap's own lift frame 25 deg = past its stall: the flaps LOST lift)
        const bool OwnElevatorAirfoil = true;    // slotted elevator: own airfoil (stall 25 deg instead of the tail's 17) + 30 deg travel: nose wheel lifts from ~37 m/s (0.1.0 ~57 at 17.5 t)
        const bool GentleStall = true;           // wing CLmax 1.52 on a chart sample, flat post-stall curve, 2 deg tip washout; FBW alpha limiter 10 deg x 0.25
        const bool FBWg5 = true;                 // FBW gLimitPositive 5 -> 4: the stock law holds pitch rate = gLimit * g / V, i.e. HUD load ~gLimit + 1
        // 0.3.0 (game worker 2026-10-31; docs/ga25x_v030_research.md + ga25x_v030_model_changes.md). false = the 0.2.0 behaviour.
        const bool JetThrottleHUD = true;        // HUDExtras = stock Multirole1 (KR-67): throttle bar with the divided afterburner section (boost from 0.90) and its label
        const bool EjectionSeats = true;         // Pilot.ejectionSeat true for both crew; canopies = canopy_jettison_L/R with the COIN canopy values; our seats ride out with the crew
        const bool FormationLights = true;       // 8 slimelight_* strips: NavLights entries (stock slimelight_on), lit while the gear is extended
        // 1.9.7 (user on 1.9.6: 'the lasers can and WILL fire through the aircraft'): the stock Laser_EW1 steers its beam up to maxAngle 30 deg
        // off the Laser's forward (= our turret bore) and Turret.AimTurret ignores the elevation error for a non-gun, non-boresight weapon, so
        // with the belly turret on its -2 deg limit the beam still reached +28 deg: the wings. maxAngle 1 = the beam is the bore line the envelope
        // scan certifies (+-2 deg). Nothing else on the GA-25X changes. false = the 1.9.6 laser (maxAngle 30). Sweep: LaserSweep197.cs.
        const bool LaserBeam197 = true;
        const float LaserBeamAngle197 = 1f;
        const bool BellyLaser = true;            // laser FiringCone from the mount (down for a ventral turret), 90 + maxElevation + 1; exclusion cones only for real collider self-hits
        const bool TouchscreenOff = true;        // tac-screen backing + the two aux panes on the stock Touchscreen_off dark glass
        // 0.3.1 cockpit kitbash (offline worker 2026-11-01; blender/ga25x/ga25x_cockpit.py). ON by default although not yet probed in
        // game: the 0.3.1 model has no custom seat / stick / throttle any more, so OFF would leave the cabin without them.
        const bool StockCockpitKit = true;       // crew figures keep their stock EjectionSeat child (seat in the cockpit = the seat that fires); stick_L/R + cockpit_throttle get the stock SFB-81 sfb_joystick / sfb_throttle meshes (Cockpit.joysticks 12, throttles rotation 52)
        const bool CockpitPanelArt = true;       // 0.3.2 cockpit rebuild: ck_art material (fal panel-art atlas ga25x_ckart_b/_n, own UVs) on the switch panels, bezels, annunciators, consoles, pedestal (geometry is in the FBX; false = plain ck_panel grey on those faces)
        const bool CockpitLights = false;
        const bool WsoScreenTacPage = true;      // 0.3.3 FIX (user: the WSO screen froze on the last target-cam frame after deselect). Stock aircraft never put targetCamDisplay on a mesh: TargetCam only enables/disables its camera (CancelTarget / camTimeout, TargetCam.cs 482-525) and fires onCamToggle, which ONLY TacScreen listens to (TacScreen.cs 89, 242-256) to show / hide its own targetCamDisplay child inside the tac page. A mesh with targetCamDisplay keeps the render texture's last frame. So mfd_right shows the stock tac screen too (tacScreenDisplay): the target video appears inside the tac page while a target is selected and the page returns to the map when it is dropped, exactly as the stock MFDs
        const bool StockThrottleMesh = false;    // 0.3.3 user design: no stock sfb_throttle levers; our split lever (cockpit_throttle_arm, child of cockpit_throttle) is driven by Cockpit.throttles        // 0.3.2 NEW, OFF until probed in game: two cockpit spot lights (OA-27 / MC-260 pattern: CockpitLighting_01/02 under the cockpit) on the Cockpit layer
        const bool StockCabinStructure = true;   // ck_struct faces: stock aircraft_structure material (Lit_vertexcolor) with vertex colour 56/56/56 and UV0 = detail UV x 1.25 (SFB-81 tub look); false = plain dark grey

        // ------------------------------------------------------------------ GA-25X numbers (sources in docs/ga25x_design.md)
        const float WingIncidence = 2.0f;        // as the B-25H (same wing)
        const float StabIncidence = -1.0f;
        // W per engine. Spec 2.4 MW. 0.1.0 in game: 2.4 MW -> 574 km/h / climb 17.2, 2.25 MW -> 562 / 16.1. 0.2.0 = spec power + LowDragAirframe:
        // predicted 592 km/h at 500 m and at SL, climb ~18 (model 16.0 x 1.15 calibration), boost ~680 km/h. Climb above the spec 14 was accepted for
        // the headline 590 (brief); a 590 km/h AND 14 m/s pair needs ~2.0 MW plus ~30 % less drag (tools/flightmodel scan).
        const float EnginePower = 2.4e6f;
        const float ElevatorArea = 4.4f;         // m^2 per side (0.1.0: 3.4 = elevator-limited at AoA 11.5 / 3.2 g at 135 m/s; spec 5 g)
        const float ElevatorDeflection = OwnElevatorAirfoil ? -30f : -28f;   // deg (0.1.0: -25, then -28)
        const float TipIncidence = GentleStall ? 0f : WingIncidence;          // washout: tips 2 deg below the inner panels
        const float FlapVisualDeg = 35f;         // StolFlaps: drawn flap angle (no aero effect)
        const float FlapLiftFrameDeg = 4f;       // StolFlaps: wing-panel lift frame rotation when deployed (camber)
        const float FlapAreaInner = 11.0f, FlapAreaOuter = 12.5f;   // StolFlaps: HighLiftDevice.deployedArea per panel (m^2): flapped 1-g stall 146 km/h at 14.7 t (spec 145)
        const float FlapSpeedDeployed = 55f, FlapSpeedRetracted = 95f; // m/s (HighLiftDevice: full below 55, none above 95; a narrower band makes lift flat with speed: q x area ~constant over 62-85)
        const float BoostPower = 0.9e6f;         // W, motor-generator per engine (spec; see BoostInMaxPower)
        const float BoostThrust = 6000f;         // N per engine at 100 % throttle (Afterburner.thrust; x clamp(airDensity, 0.4, 1)); ~900 kW at 150 m/s
        const float BoostFuel = 0.10f;           // kg/s per engine extra at full boost (Afterburner.fuelConsumption)
        const float BoostIR = 0.3f;              // Afterburner.IRIntensity (exhaust coolers; Fighter1 4.5)
        const float PropRpm = 1100f;             // 6-blade 3.90 m: tip 225 m/s static
        const bool BomberFuelTanks183 = true;   // 1.8.3: AB-4 wing-tank settings + inner <-> outer links (false = CI-22 tanks as 1.8.2)
        // 1.9.12 (user: the upgraded aircraft get real airbrake panels that deploy when the aircraft is airbraking): two SHOULDER panels on
        // fus_rear (the stock FS-12 layout: one curved panel each side of the upper fuselage, front-hinged on a hinge line tilted over the
        // shoulder), above the faction marks of every livery, driven by ONE stock Airbrake on the root (Airbrake.cs: opens at throttle 0
        // over 1 / openSpeed s, rotates every transform +maxAngle about its local X, force = dragAmount x rho x V^2 on part.rb). The panels
        // come from their own FBX (assets\model_ga25x\ga25x_airbrake.fbx, blender\ga25x\run_airbrake1912.py; the main model is not
        // rebuilt): plates 4.9 mm proud of the uncut skin carrying the skin's own atlas texels, inner face and well in the dark `cockpit`
        // finish with light `structure` frames / stringers, no collider, not parts; fus_rear's mesh and hull are untouched.
        // false = 1.9.11 (no FBX import, no objects, no Airbrake). When the brake works: throttle under 5 %, ground or air (stock rule at exactly 0, widened by the plugin, AirBrake1912.cs); the panels stand open when parked at idle.
        const bool AirbrakePanels1912 = true;
        const float AirbrakeDrag1912 = 2.0f, AirbrakeMaxAngle1912 = 55f, AirbrakeOpenSpeed1912 = 1.0f;
        static readonly string[] AirbrakeSides1912 = { "L", "R" };
        const float FuelKg = 3800f;              // spec, wing tanks
        const float SpawnHeight = 2.62f;         // same gear as the B-25H
        const float TurbineMaxRPM = 3000f;       // TurbineEngine RPM scale (A-19 turboprop value)
        const float PowerChargePerRPM = 0.3f;    // kW per rpm per engine: 900 kW per motor-generator at full rpm (spec)
        const float PowerMaxCharge = 1500f;      // kJ capacitor (spec; EW-25 1,070)
        const float LaserPowerKW = 120f;         // stock Laser_EW1 power
        const float JammerPowerKW = 50f;         // stock EW1 RadarJammer powerUsage
        const float RadarRange = 40000f;         // m (spec; EW-25 50 km)
        const int FlareCount = 96;               // spec (EW-25 86)
        const int CannonRounds = 96;             // spec
        const int Gun20Rounds = 250;             // per gun (spec)
        const int LaserDesignatorTargets = 4;    // LaserDesignator.maxTargets (spec "laser designators 4")
        const float OpticsRange = 10000f;        // TargetDetector.visualRange (spec)
        const float OpticsZoom = 3f;
        const float RadarSize = 0.40f;           // 0.3.0: RAM + skin radar (research 6): hangar ~0.44 with the default loadout (B-25H 0.94, CI-22 0.5, A-19 0.6); 0.2.0 1.4             // TargetDetector.magnification (spec "optics x3")

        static readonly BindingFlags BF = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        // ------------------------------------------------------------------ part table
        enum Lift { Own, Wing, Stab, Fin, Hinge }
        class PartSpec
        {
            public string name, parent, mesh, template; public float mass, wingArea, dragArea; public int airfoil; public Lift lift;
            public float joint; // primary joint break strength (x10 N in game)
            public PartSpec(string n, string p, string m, string t, float mass, float wa, float da, int af, Lift l, float j)
            { name = n; parent = p; mesh = m; template = t; this.mass = mass; wingArea = wa; dragArea = da; airfoil = af; lift = l; joint = j; }
        }

        // Masses sum to 9,600 kg (spec empty weight). Wing parts + body = 57.2 m^2 (spec 57.4). Joints x1.4 the B-25H (g 5 vs 3.5).
        // Drag areas ~25 % below the B-25H (no turrets/blisters/glazed nose, slim nacelles, composite skin).
        const float J = 1.4f;
        static List<PartSpec> Parts()
        {
            var l = new List<PartSpec>
            {
                new PartSpec("GA25X",       null,          "fus_center",  "CAS1:CAS1",       1500, 2.0f, LowDragAirframe ? 0.18f : 0.20f, 1, Lift.Own,    0),
                new PartSpec("fus_forward", "GA25X",       "fus_forward", "CAS1:fuselage_F",  700, 0.0f, 0.07f, 1, Lift.Own,    150000 * J),
                new PartSpec("fus_cockpit", "fus_forward", "fus_cockpit", "CAS1:cockpit",    1000, 0.5f, 0.08f, 1, Lift.Own,    150000 * J),
                new PartSpec("fus_nose",    "fus_cockpit", "fus_nose",    "CAS1:nose",       1000, 0.3f, 0.09f, 1, Lift.Own,    60000 * J),
                new PartSpec("fus_rear",    "GA25X",       "fus_rear",    "CAS1:fuselage_R",  410, 0.5f, 0.09f, 1, Lift.Own,    120000 * J),
                new PartSpec("fus_tail",    "fus_rear",    "fus_tail",    "CAS1:tail",        260, 0.0f, 0.06f, 1, Lift.Own,    100000 * J),
            };
            foreach (var s in new[] { "L", "R" })
            {
                l.Add(new PartSpec("stab_" + s,        "fus_tail",       "stab_" + s,        "CAS1:hstab_" + s,      80, 1.6f, 0.01f, 1, Lift.Stab,  40000 * J));
                l.Add(new PartSpec("elevator_" + s,    "stab_" + s,      "elevator_" + s,    "CAS1:elevator_" + s,   25, ElevatorArea, 0.01f, OwnElevatorAirfoil ? 2 : 1, Lift.Hinge, 30000 * J));
                l.Add(new PartSpec("fin_" + s,         "stab_" + s,      "fin_" + s,         "CAS1:vstab_" + s,      50, 1.6f, 0.01f, 1, Lift.Fin,   30000 * J));
                l.Add(new PartSpec("rudder_" + s,      "fin_" + s,       "rudder_" + s,      "CAS1:rudder_" + s,     25, 1.5f, 0.01f, 1, Lift.Hinge, 20000 * J));
                l.Add(new PartSpec("wing_inner_" + s,  "GA25X",          "wing_inner_" + s,  "CAS1:wing1_" + s,     470, 6.2f, 0.02f, 0, Lift.Wing,  200000 * J));
                l.Add(new PartSpec("flap_inner_" + s,  "wing_inner_" + s,"flap_inner_" + s,  "CAS1:flap_" + s,       25, 1.7f, 0.01f, 0, Lift.Hinge, 30000 * J));
                l.Add(new PartSpec("nacelle_" + s,     "wing_inner_" + s,"nacelle_" + s,     "CAS1:engineMount_" + s,300, 0.5f, LowDragAirframe ? 0.09f : 0.12f, 1, Lift.Own,  80000 * J));
                l.Add(new PartSpec("engine_" + s,      "nacelle_" + s,   "engine_" + s,      "CAS1:engine_" + s,    820, 0.0f, LowDragAirframe ? 0.06f : 0.08f, 1, Lift.Own,   60000 * J));
                l.Add(new PartSpec("prop_" + s,        "engine_" + s,    null,               "COIN:propHub",        160, 0.0f, 0.03f, 1, Lift.Own,   30000 * J));
                l.Add(new PartSpec("wing_outer_" + s,  "wing_inner_" + s,"wing_outer_" + s,  "CAS1:wing2_" + s,     250, 7.8f, 0.01f, 0, Lift.Wing,  120000 * J));
                l.Add(new PartSpec("flap_outer_" + s,  "wing_outer_" + s,"flap_outer_" + s,  "CAS1:flap_" + s,       30, 2.3f, 0.01f, 0, Lift.Hinge, 30000 * J));
                l.Add(new PartSpec("wing_tip_" + s,    "wing_outer_" + s,"wing_tip_" + s,    "CAS1:wing3_" + s,     105, 6.8f, 0.01f, 0, Lift.Wing,  80000 * J));
                l.Add(new PartSpec("aileron_" + s,     "wing_tip_" + s,  "aileron_" + s,     "CAS1:aileron_" + s,    25, 2.3f, 0.01f, 0, Lift.Hinge, 40000 * J));
            }
            return l;
        }

        // ------------------------------------------------------------------ state for one build
        static GameObject root;
        static readonly Dictionary<string, GameObject> tpl = new Dictionary<string, GameObject>(); // stock template instances
        static readonly HashSet<Transform> tplRoots = new HashSet<Transform>();
        static readonly Dictionary<string, AeroPart> parts = new Dictionary<string, AeroPart>();
        static readonly Dictionary<string, Transform> liftNormals = new Dictionary<string, Transform>();
        static readonly List<Mesh> generatedMeshes = new List<Mesh>();
        static readonly Dictionary<string, Material> mats = new Dictionary<string, Material>();
        static readonly List<string> log = new List<string>();
        static readonly List<ParticleSystem> ourParticles = new List<ParticleSystem>();
        static Aircraft aircraft; static ControlsFilter controlsFilter; static WeaponManager weaponManager;

        static void L(string s) { log.Add(s); Debug.Log("[GA25X] " + s); }

        // =================================================================== entry points
        // Build = assets + check + pack. Combined (FamilyBuild.Combined): the family addon is re-packed with every aircraft
        // built in it; otherwise this aircraft's own addon as before.
        public static void Build()
        {
            bool ok = BuildAssets();
            if (FamilyBuild.Combined) { FamilyBuild.Pack(); return; }
            Directory.CreateDirectory(OutFolder);
            Blueprinter.ModBuilder.Build(ModName, DisplayName, Version, OutFolder);
            var nobp = Directory.GetFiles(OutFolder, "*.nobp").OrderByDescending(File.GetLastWriteTimeUtc).FirstOrDefault();
            log.Clear(); L($"BUILD DONE check={(ok ? "PASS" : "FAIL")} nobp={nobp} size={(nobp != null ? new FileInfo(nobp).Length : 0)}");
            File.AppendAllText(LogPath, string.Join("\n", log) + "\n");
        }

        // Everything except packing: prefab, assets, check. Writes only this aircraft's own mod (sub)folder.
        public static bool BuildAssets()
        {
            bool ok = false;
            log.Clear(); tpl.Clear(); tplRoots.Clear(); parts.Clear(); partGO.Clear(); aircraft = null; controlsFilter = null; weaponManager = null; liftNormals.Clear(); generatedMeshes.Clear(); mats.Clear(); ourParticles.Clear();
            try
            {
                PrepareFolders();
                crew.Clear(); laserTurret = null; laserGO = null; hookGO = null; hookMount = null; laserAmmo = null; laserInfo = null;
                contract = LoadContract();
                var model = ImportModel();
                ImportTextures();
                LoadTemplates();
                BuildMaterials();
                root = (GameObject)Object.Instantiate(model);
                root.name = "GA25X";
                DropPedals();
                AddAirbrakePanels1912();
                BuildPrefab();
                var prefab = SaveEverything();
                DestroyTemplates();
                Object.DestroyImmediate(root);
                AssetDatabase.SaveAssets();
                ok = RunCheck(prefab);
                L($"ASSETS DONE check={(ok ? "PASS" : "FAIL")} folder={Folder}");
            }
            finally { DestroyTemplates(); File.AppendAllText(LogPath, string.Join("\n", log) + "\n"); }
            return ok;
        }

        public static void Check()
        {
            log.Clear();
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Folder + "/GA25X.prefab");
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
            File.WriteAllText(LogPath, $"GA25X build {DateTime.Now:s}\n");
        }

        static Mesh modelBlur, modelFull;
        // 2026-11-02 (user review 2, Nimrod: "you fundamentally misunderstand what pedals are ... Remove them from all 3 aircraft"):
        // the rudder pedal objects are dropped at the Unity build step (the Blender model is not regenerated); nothing else changes.
        // The pedal bars stood on the footwell floor, which is a separate mesh and stays whole (no hole).
        const bool RemovePedals = true;
        static int DropPedals()
        {
            if (!RemovePedals) return 0;
            var ped = root.GetComponentsInChildren<Transform>(true).Where(t => t.name.StartsWith("cockpit_rudder_pedals")).ToList();
            foreach (var t in ped) if (t != null) Object.DestroyImmediate(t.gameObject);
            L($"rudder pedals removed: {ped.Count} object(s)");
            return ped.Count;
        }

        static GameObject ImportModel()
        {
            var dst = SrcDir + "/ga25x.fbx";
            File.Copy(RepoModel, dst, true);
            AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
            var mi = (ModelImporter)AssetImporter.GetAtPath(dst);
            mi.isReadable = true; mi.importAnimation = false; mi.importCameras = false; mi.importLights = false;
            mi.globalScale = 1f; mi.useFileScale = true; mi.importBlendShapes = false;
            mi.SaveAndReimport();
            L($"model imported {dst} ({new FileInfo(RepoModel).Length} bytes)");
            // prop blur stage meshes (model worker, separate FBX so the main model never shows an unwired disc)
            modelBlur = modelFull = null;
            var extra = Path.Combine(Path.GetDirectoryName(RepoModel), "ga25x_propdisc.fbx");
            if (File.Exists(extra))
            {
                var edst = SrcDir + "/ga25x_propdisc.fbx";
                File.Copy(extra, edst, true);
                AssetDatabase.ImportAsset(edst, ImportAssetOptions.ForceUpdate);
                var emi = (ModelImporter)AssetImporter.GetAtPath(edst);
                emi.isReadable = true; emi.importAnimation = false; emi.importCameras = false; emi.importLights = false; emi.globalScale = 1f; emi.useFileScale = true;
                emi.SaveAndReimport();
                var ms = AssetDatabase.LoadAllAssetsAtPath(edst).OfType<Mesh>().ToList();
                Mesh Take(string n) { var m = ms.FirstOrDefault(x => x.name == n); if (m == null) return null; var c = Object.Instantiate(m); c.name = "ga25x_" + n; generatedMeshes.Add(c); return c; }
                modelBlur = Take("propdisc_blur"); modelFull = Take("propdisc_full");
                L($"prop disc meshes from {extra}: blur {(modelBlur ? modelBlur.vertexCount + " v" : "missing")}, full {(modelFull ? modelFull.vertexCount + " v" : "missing")}");
            }
            airbrakeModel1912 = null;
            if (AirbrakePanels1912)
            {   // 1.9.12 airbrake add-on: same exporter, same import settings as the main model (same frame, CG at the origin)
                var asrc = Path.Combine(Path.GetDirectoryName(RepoModel), "ga25x_airbrake.fbx");
                if (!File.Exists(asrc)) throw new Exception("AirbrakePanels1912: " + asrc + " missing (python blender/ga25x/run_airbrake1912.py)");
                var adst = SrcDir + "/ga25x_airbrake.fbx";
                File.Copy(asrc, adst, true);
                AssetDatabase.ImportAsset(adst, ImportAssetOptions.ForceUpdate);
                var ami = (ModelImporter)AssetImporter.GetAtPath(adst);
                ami.isReadable = true; ami.importAnimation = false; ami.importCameras = false; ami.importLights = false;
                ami.globalScale = 1f; ami.useFileScale = true; ami.importBlendShapes = false;
                ami.SaveAndReimport();
                airbrakeModel1912 = AssetDatabase.LoadAssetAtPath<GameObject>(adst);
                L($"airbrake add-on imported {adst} ({new FileInfo(asrc).Length} bytes)");
            }
            return AssetDatabase.LoadAssetAtPath<GameObject>(dst);
        }

        // ------------------------------------------------------------------ 1.9.12 airbrake panels
        static GameObject airbrakeModel1912;

        /// how far the panel's free (aft) edge moves away from the aircraft's long axis (centre-local Z) when the hinge is turned by `deg`
        /// about its local X exactly as the stock Airbrake does (localEulerAngles = base, then Rotate(deg, 0, 0) in Space.Self). The hinge is restored.
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
            float Radial(Vector3 p) { var c = centre.InverseTransformPoint(p); return Mathf.Sqrt(c.x * c.x + c.y * c.y); }
            float shut = Radial(hinge.TransformPoint(free));
            hinge.Rotate(new Vector3(deg, 0f, 0f), Space.Self);
            float open = Radial(hinge.TransformPoint(free));
            hinge.localRotation = keep;
            return open - shut;
        }

        /// Adds the panels of ga25x_airbrake.fbx under the fus_rear model object, BEFORE BuildPrefab: the panels then get our meshes /
        /// materials with every other renderer, land in fus_rear's livery list (paint first) and stay out of its collider (own mesh only).
        static void AddAirbrakePanels1912()
        {
            if (!AirbrakePanels1912) return;
            var inst = (GameObject)Object.Instantiate(airbrakeModel1912);
            inst.transform.SetPositionAndRotation(root.transform.position, root.transform.rotation);
            var all = inst.GetComponentsInChildren<Transform>(true);
            Transform Get(string n) => all.FirstOrDefault(t => t.name == n) ?? throw new Exception("ga25x_airbrake.fbx: no object " + n);
            var fusRear = Find("fus_rear");
            foreach (var s in AirbrakeSides1912)
            {
                var srcHinge = Get($"airbrake_{s}_hinge"); var panel = Get($"airbrake_{s}"); var tray = Get($"airbrake_tray_{s}");
                // hinge frame built here from three imported POSITIONS (not from the imported empty's axes): the hinge and the two marker
                // empties 1 m from it along the hinge line (airbrake_<s>_axis) and along the outward normal (airbrake_<s>_out). X = hinge
                // line, Y = outward, Z = X x Y = forward along the skin. The stock +angle about X then swings the aft edge outward.
                var pos = srcHinge.position;
                var pmesh = panel.GetComponent<MeshFilter>().sharedMesh;
                var hl = root.transform.InverseTransformPoint(pos);
                var xL = root.transform.InverseTransformPoint(Get($"airbrake_{s}_axis").position) - hl;
                var outL = root.transform.InverseTransformPoint(Get($"airbrake_{s}_out").position) - hl;
                if (Mathf.Abs(xL.magnitude - 1f) > 0.002f || Mathf.Abs(outL.magnitude - 1f) > 0.002f || Mathf.Abs(Vector3.Dot(xL.normalized, outL.normalized)) > 0.002f)
                    throw new Exception($"airbrake_{s}: frame markers not 1 m from the hinge at right angles (axis {xL.magnitude:F4} m, out {outL.magnitude:F4} m, dot {Vector3.Dot(xL.normalized, outL.normalized):F4})");
                xL.Normalize(); outL.Normalize();
                var fwdL = Vector3.Cross(xL, outL);
                if (fwdL.z < 0.9f || outL.x * Mathf.Sign(hl.x) <= 0f || outL.y <= 0f)
                    throw new Exception($"airbrake_{s}: hinge frame not forward / outward / up (forward {fwdL.ToString("F3")}, outward {outL.ToString("F3")})");
                var rot = root.transform.rotation * Quaternion.LookRotation(fwdL, outL);
                var hinge = NewGO($"airbrake_{s}_hinge", fusRear, pos, rot);
                panel.SetParent(hinge.transform, true);
                tray.SetParent(fusRear, true);
                float gain = AirbrakeOpenGain1912(hinge.transform, root.transform, AirbrakeMaxAngle1912);
                if (!(gain >= 0.2f)) throw new Exception($"airbrake_{s}: +{AirbrakeMaxAngle1912} deg about the hinge X moves the free edge {gain:F3} m outward (>= 0.2 expected): hinge frame wrong");
                var xGot = Quaternion.Inverse(root.transform.rotation) * hinge.transform.right;
                if (Vector3.Dot(xGot, xL) < 0.9999f) throw new Exception($"airbrake_{s}: hinge local X {xGot.ToString("F4")} is not the marker hinge line {xL.ToString("F4")}");
                L($"airbrake panel {s}: hinge {hl.ToString("F3")} (root frame), X {xGot.ToString("F3")}, outward {outL.ToString("F3")}, forward {fwdL.ToString("F3")}, " +
                  $"panel {pmesh.vertexCount} v / {pmesh.triangles.Length / 3} tris, free edge +{gain:F3} m away from the long axis at {AirbrakeMaxAngle1912} deg");
            }
            Object.DestroyImmediate(inst);
        }

        /// one stock Airbrake on the root: transforms = the two hinges, drag on the root part (no yaw / roll moment). Field set as on the
        /// MSB-17 (msb_root.cs, in game since 1.9.2) plus the transforms and the angle.
        static void AirbrakeComponent1912()
        {
            if (!AirbrakePanels1912) return;
            var hinges = AirbrakeSides1912.Select(s => Find($"airbrake_{s}_hinge")).ToArray();
            var ab = root.AddComponent<global::Airbrake>();
            S(ab, "transforms", hinges); S(ab, "dragAmount", AirbrakeDrag1912); S(ab, "maxAngle", AirbrakeMaxAngle1912); S(ab, "openSpeed", AirbrakeOpenSpeed1912);
            S(ab, "part", parts["GA25X"]); S(ab, "airbrakeSound", null); S(ab, "constraints", new UnityEngine.Animations.AimConstraint[0]);
            S(ab, "volumeMultiplier", 0f); S(ab, "aircraft", aircraft);
            L($"airbrake: stock Airbrake on the root, {hinges.Length} hinges, dragAmount {AirbrakeDrag1912} (rho V^2: {AirbrakeDrag1912 * 1.225f * 100f * 100f / 1000f:F1} kN at 100 m/s SL), maxAngle {AirbrakeMaxAngle1912}, opens at throttle 0 in {1f / AirbrakeOpenSpeed1912:F1} s");
        }

        static readonly string[] SkinMaps = { "b", "n", "m", "ao", "dmg_b", "dmg_n" };
        // GA-25X liveries: every entry of ga25x_liveries.json (texture worker step compose_liveries_ga25x.py), each offered to its
        // own faction only (the GA-25X is a PALA design; BDF flies it in its standard camouflage). The default scheme comes first.
        static readonly List<(string file, string label, string faction, bool isDefault)> Liveries = new List<(string, string, string, bool)>();
        static void LoadLiveryTable()
        {
            Liveries.Clear();
            var path = Path.Combine(RepoTextures, "ga25x_liveries.json");
            if (!File.Exists(path))
            {
                L("WARN no ga25x_liveries.json: two flat fallback liveries");
                Liveries.Add(("ga25x_livery_pala_twotone", "PALA Two-Tone Grey", "PALA", true));
                Liveries.Add(("ga25x_livery_bdf_temperate", "BDF Temperate Camo", "BDF", false));
                return;
            }
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(path));
            foreach (var kv in jo)
            {
                if (!(kv.Value is Newtonsoft.Json.Linq.JObject e)) continue;
                var file = Path.GetFileNameWithoutExtension((string)e["texture"] ?? ("ga25x_livery_" + kv.Key + ".png"));
                var fac = ((string)e["faction"] ?? "").ToUpperInvariant().Contains("BDF") ? "BDF" : "PALA";
                if (!File.Exists(Path.Combine(RepoTextures, file + ".png"))) { L($"WARN livery {kv.Key}: texture missing, skipped"); continue; }
                Liveries.Add((file, (string)e["name"] ?? kv.Key, fac, e["default"] != null && (bool)e["default"]));
                L($"livery table: + {file} '{(string)e["name"]}' ({fac})");
            }
        }
        static readonly Dictionary<string, Color32> LiveryFallback = new Dictionary<string, Color32>
        {
            { "ga25x_livery_pala_twotone", new Color32(84, 88, 92, 255) }, { "ga25x_livery_bdf_temperate", new Color32(92, 98, 84, 255) },
            { "ga25x_skin_b", new Color32(84, 88, 92, 255) },
        };
        // tiling detail textures + gauge atlas: our own B-25H art (assets/textures_v2, b25h_* names), shared read-only
        static readonly string[] Tiles = { "ga25x_interior_b", "ga25x_structure_b", "ga25x_metal_dark_b", "ga25x_rubber_b", "ga25x_rubber_n", "ga25x_prop_b" };   // 0.3.1: ga25x_cockpit_b (crosshatch noise) dropped
        static readonly Dictionary<string, Texture2D> tex = new Dictionary<string, Texture2D>();

        static string TextureSource(string n)
        {
            var own = Path.Combine(RepoTextures, n + ".png");
            if (File.Exists(own)) return own;
            var shared = Path.Combine(RepoSharedTextures, "b25h_" + n.Substring("ga25x_".Length) + ".png");
            if ((Tiles.Contains(n) || n == "ga25x_gauges") && File.Exists(shared)) return shared;
            return null;
        }

        static void ImportTextures()
        {
            tex.Clear();
            LoadLiveryTable();
            var want = SkinMaps.Select(m => "ga25x_skin_" + m).Concat(Liveries.Select(l => l.file)).Concat(new[] { "ga25x_gauges" }).Concat(Tiles).Concat(CockpitPanelArt ? new[] { "ga25x_ckart_b", "ga25x_ckart_n", "ga25x_throttle_b", "ga25x_throttle_n" }.Concat(CockpitEmission1914 ? new[] { "ga25x_ckart_e" } : new string[0]).ToArray() : new string[0]).Distinct().ToList();
            foreach (var n in want)
            {
                var src = TextureSource(n);
                var dst = $"{Folder}/Textures/{n}.png";
                bool real = src != null;
                if (real) File.Copy(src, dst, true);
                else File.WriteAllBytes(dst, FallbackTexture(n).EncodeToPNG());
                AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
                var ti = (TextureImporter)AssetImporter.GetAtPath(dst);
                bool normal = n.EndsWith("_n");
                bool linear = n.EndsWith("_m") || n.EndsWith("_ao") || normal;
                ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                ti.sRGBTexture = !linear; ti.mipmapEnabled = true; ti.maxTextureSize = 4096;
                ti.textureCompression = TextureImporterCompression.Compressed;
                ti.SaveAndReimport();
                tex[n] = AssetDatabase.LoadAssetAtPath<Texture2D>(dst);
                L($"texture {n}: {(real ? "from " + src : "generated flat fallback")}");
            }
        }

        static Texture2D FallbackTexture(string n)
        {
            Color32 c;
            if (LiveryFallback.TryGetValue(n, out var lc)) c = lc;
            else if (n.EndsWith("_dmg_b")) c = new Color32(40, 36, 32, 255);
            else if (n.EndsWith("_n")) c = new Color32(128, 128, 255, 255);
            else if (n.EndsWith("_m")) c = new Color32(0, 0, 0, 90);
            else if (n.EndsWith("_ao")) c = new Color32(255, 255, 255, 255);
            else if (n == "ga25x_gauges") c = new Color32(22, 22, 22, 255);
            else c = new Color32(235, 235, 235, 255);
            var t = new Texture2D(8, 8, TextureFormat.RGBA32, false);
            t.SetPixels32(Enumerable.Repeat(c, 64).ToArray()); t.Apply();
            return t;
        }

        // Prop blur atlas (generated, our own art): 512 x 1024, upper half = 3-blade smear (stage 1, low rpm), lower half =
        // full disc (stage 2, high rpm). Black blades with yellow tips, alpha in the texture.
        static Texture2D PropBlurTexture()
        {
            const int W = 512, H = 1024;
            var px = new Color32[W * H];
            // 1.9.14: no yellow tip band. The GA-25X blades are black composite with a grey sheath and black tips; the old
            // yellow ring (r > 0.92, +0.16 alpha) showed over the blur disc as "the blade tips are still there" (user report).
            Color dark = new Color(0.07f, 0.07f, 0.07f), tipC = dark;
            for (int y = 0; y < H; y++)
                for (int x = 0; x < W; x++)
                {
                    bool smear = y >= H / 2;
                    float cx = (x + 0.5f - 256f) / 250f, cy = (y + 0.5f - (smear ? 768f : 256f)) / 250f;
                    float r = Mathf.Sqrt(cx * cx + cy * cy);
                    float a = 0f; Color c = r > 0.92f ? tipC : dark;
                    if (r <= 1f && r > 0.11f)
                    {
                        float edge = Mathf.Clamp01((1f - r) * 60f) * Mathf.Clamp01((r - 0.11f) * 30f);
                        if (smear)
                        {
                            float th = Mathf.Atan2(cy, cx) * Mathf.Rad2Deg;
                            float d = 999f;
                            for (int b = 0; b < 6; b++) d = Mathf.Min(d, Mathf.Abs(Mathf.DeltaAngle(th, b * 60f)));   // 6 blades
                            float w = 5f + 13f * r;  // angular half-width of the smeared blade, wider at the tip
                            a = 0.08f + 0.62f * Mathf.Exp(-(d / w) * (d / w));
                        }
                        else
                        {
                            a = 0.20f + 0.03f * Mathf.Sin(r * 60f);   // 1.9.14: no brighter tip ring
                        }
                        a *= edge;
                    }
                    var col = (Color32)new Color(c.r, c.g, c.b, a);
                    px[y * W + x] = col;
                }
            var t = new Texture2D(W, H, TextureFormat.RGBA32, false);
            t.SetPixels32(px); t.Apply();
            var path = $"{Folder}/Textures/ga25x_propblur.png";
            File.WriteAllBytes(path, t.EncodeToPNG());
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
            var ti = (TextureImporter)AssetImporter.GetAtPath(path);
            ti.alphaIsTransparency = true; ti.wrapMode = TextureWrapMode.Clamp; ti.mipmapEnabled = true;
            ti.textureCompression = TextureImporterCompression.Compressed; ti.SaveAndReimport();
            L("generated prop blur atlas ga25x_propblur.png (512x1024)");
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        // One single-sided disc in the hub's XY plane mapped onto one half of the blur atlas (vBase 0 = disc, 0.5 = smear).
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

        // =================================================================== stock templates (starting values only)
        static void LoadTemplates()
        {
            foreach (var n in new[] { "COIN", "CAS1", "EW1", "turret_76mm_SideMount", "gun_20mm_internal", "gun_20mm_pod", "Laser_EW1", "LaserTrailer1", "TailHook_Multirole1", "Fighter1", "FastBomber1" })
            {
                var p = AssetDatabase.LoadAssetAtPath<GameObject>($"{DNS}/GameObject/{n}_PLACEHOLDER.prefab");
                if (p == null) throw new Exception("missing placeholder " + n);
                var inst = (GameObject)Object.Instantiate(p);
                inst.name = "TEMPLATE_" + n;
                inst.SetActive(false);
                tpl[n] = inst; tplRoots.Add(inst.transform);
            }
        }

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

        // =================================================================== materials
        static void BuildMaterials()
        {
            var skin = Asset<Shader>("Shader/Shader Graphs_AircraftSkin_PLACEHOLDER.shader");
            var paint = new Material(skin) { name = "GA25X_paint" };
            paint.SetTexture("_Basecolor", tex["ga25x_skin_b"]);
            paint.SetTexture("_Normal", tex["ga25x_skin_n"]);
            paint.SetTexture("_Metallic", tex["ga25x_skin_m"]);
            paint.SetTexture("_AO", tex["ga25x_skin_ao"]);
            paint.SetTexture("_BasecolorDmg", tex["ga25x_skin_dmg_b"]);
            paint.SetTexture("_NormalDmg", tex["ga25x_skin_dmg_n"]);
            paint.SetTexture("_Livery", tex["ga25x_skin_b"]); // skin _b is the full painted base colour (= od_plain)
            paint.SetFloat("_Glossiness", 0.35f);
            paint.SetFloat("_HitPoints", 100f);
            Save(paint, "paint");

            var lit = Shader.Find("Universal Render Pipeline/Lit");
            if (lit == null) throw new Exception("URP Lit shader not found");
            Save(Tiled(LitMat(lit, "GA25X_interior", Color.white, 0.0f, 0.25f), "ga25x_interior_b"), "interior");
            Save(Tiled(LitMat(lit, "GA25X_structure", Color.white, 0.6f, 0.35f), "ga25x_structure_b"), "structure");
            Save(Tiled(LitMat(lit, "GA25X_metal_dark", Color.white, 0.7f, 0.40f), "ga25x_metal_dark_b"), "metal_dark");
            Save(Tiled(LitMat(lit, "GA25X_rubber", Color.white, 0.0f, 0.15f), "ga25x_rubber_b", "ga25x_rubber_n"), "rubber");
            Save(Tiled(LitMat(lit, "GA25X_prop", Color.white, 0.2f, 0.30f), "ga25x_prop_b"), "prop");
            Save(LitMat(lit, "GA25X_prop_tip", new Color(0.85f, 0.70f, 0.05f), 0.0f, 0.30f), "prop_tip");
            Save(LitMat(lit, "GA25X_cockpit", new Color(0.20f, 0.205f, 0.215f), 0.1f, 0.25f), "cockpit");   // 0.3.1: plain (no crosshatch tile); fuselage inner faces
            // 0.3.1 cabin (kitbash): stock structure texturing on the tub, plain greys elsewhere, no tiles
            if (StockCabinStructure) mats["ck_struct"] = Asset<Material>("Material/aircraft_structure_PLACEHOLDER.mat");
            else Save(LitMat(lit, "GA25X_ck_struct", new Color(0.22f, 0.225f, 0.235f), 0.1f, 0.3f), "ck_struct");
            Save(LitMat(lit, "GA25X_ck_panel", new Color(0.16f, 0.165f, 0.175f), 0.1f, 0.3f), "ck_panel");
            Save(LitMat(lit, "GA25X_ck_black", new Color(0.035f, 0.035f, 0.04f), 0.0f, 0.35f), "ck_black");
            // 0.3.2: panel art (our fal-generated atlas) on its own UVs (UV0 = the 'livery' layer, like the gauge atlas)
            if (CockpitPanelArt) { var art = LitMat(lit, "GA25X_ck_art", Color.white, 0.15f, 0.35f); Tiled(art, "ga25x_ckart_b", "ga25x_ckart_n"); art.SetFloat("_BumpScale", 1.0f);
                if (CockpitEmission1914)
                {   // 1.9.14 (user suggestion): the painted lit lamps glow - MASTER CAUTION, GEAR, the green LED digits (ga25x_ckart_e: base colour
                    // where lit, black elsewhere; blender/ga25x/textures/make_ckart_emission1914.py). Placards and hazard stripes stay unlit.
                    art.SetTexture("_EmissionMap", tex["ga25x_ckart_e"]); art.EnableKeyword("_EMISSION");
                    art.SetColor("_EmissionColor", Color.white * CockpitEmissionGain1914); art.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
                }
                Save(art, "ck_art"); }
            else mats["ck_art"] = mats["ck_panel"];
            // 0.3.4: fal-generated split throttle handle (tripo bake: base colour + normal, own UVs on UV0)
            if (CockpitPanelArt) { var th = LitMat(lit, "GA25X_ck_throttle", Color.white, 0.3f, 0.45f); Tiled(th, "ga25x_throttle_b", "ga25x_throttle_n"); Save(th, "ck_throttle"); }
            else mats["ck_throttle"] = mats["ck_black"];
            var gauges = LitMat(lit, "GA25X_gauges", Color.white, 0f, 0.6f);
            gauges.SetTexture("_BaseMap", tex["ga25x_gauges"]); gauges.SetTexture("_MainTex", tex["ga25x_gauges"]);
            Save(gauges, "gauges");
            Save(LitMat(lit, "GA25X_navlight", new Color(0.3f, 0.3f, 0.3f), 0f, 0.8f), "navlight");
            Save(LitMat(lit, "GA25X_screen", Color.black, 0f, 0.5f), "screen");
            mats["light_off"] = Asset<Material>("Material/light_green_off_PLACEHOLDER.mat");   // slimelight_* strips unlit (AB-4 light_green_off, stock reference)
            mats["touch_off"] = Asset<Material>("Material/Touchscreen_off_PLACEHOLDER.mat");   // stock dark display glass (EW-25)
            // Canopy: gold-film tint = our copy of the stock FastBomber1 glass material values (the only stock canopy with a gold tint).
            var glass = new Material(Asset<Material>("Material/FastBomber1_glass_PLACEHOLDER.mat")) { name = "GA25X_glass" };
            Save(glass, "glass");
            var glassInt = new Material(Asset<Material>("Material/FastBomber1_glass_int_PLACEHOLDER.mat")) { name = "GA25X_glass_int" };
            Save(glassInt, "glass_int");
            Save(LitMat(lit, "GA25X_sensor", new Color(0.03f, 0.035f, 0.04f), 0.3f, 0.85f), "sensor");
            // Prop blur: the CI-22 disc material is URP Lit transparent with _BaseColor alpha 0.10 and a blur atlas mapped onto a
            // 5,760-vertex stack of blade ghosts (COIN.prefab propHub, COIN_propdisc1/2 meshes); a single flat disc with that
            // material is ~invisible, which is why the 1.0 props "vanished" above ~15 % rpm (ConstantSpeedProp.PropAnimate hides
            // the blades whenever propDiscMeshes[index] != stage 0). Same shader settings, our own atlas, alpha in the texture.
            var disc = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "GA25X_propdisc" };
            if (OwnPropBlur)
            {
                // texture worker's 3-blade blur atlas (same layout: top half smear, bottom half disc) when present
                var workerBlur = Directory.Exists(RepoTextures) ? Directory.GetFiles(RepoTextures, "ga25x_prop*blur*.png").FirstOrDefault() : null;
                Texture2D blur;
                if (workerBlur != null)
                {
                    var bp = $"{Folder}/Textures/{Path.GetFileName(workerBlur)}";
                    File.Copy(workerBlur, bp, true); AssetDatabase.ImportAsset(bp, ImportAssetOptions.ForceUpdate);
                    var bti = (TextureImporter)AssetImporter.GetAtPath(bp); bti.alphaIsTransparency = true; bti.wrapMode = TextureWrapMode.Clamp; bti.SaveAndReimport();
                    blur = AssetDatabase.LoadAssetAtPath<Texture2D>(bp); L($"prop blur atlas: texture worker {Path.GetFileName(workerBlur)}");
                }
                else blur = PropBlurTexture();
                disc.SetTexture("_BaseMap", blur); disc.SetTexture("_MainTex", blur);
                disc.SetTexture("_OcclusionMap", null); disc.DisableKeyword("_OCCLUSIONMAP");
                disc.SetColor("_BaseColor", Color.white); disc.SetColor("_Color", Color.white);
                disc.SetFloat("_Smoothness", 0.63f); // as stock
                // _BaseColor alpha 1 (stock 0.102): the stock disc meshes stack ~20 ghost layers, ours are one disc, so the texture
                // alpha (blur ~0.2, disc ~0.3) must carry the opacity alone; 0.102 x 0.2 = invisible, the 1.0 bug.
                // the model's stage meshes are thin closed discs (front + back faces): cull back faces as the CI-22 material;
                // our generated fallback discs are single-sided: draw both faces
                disc.SetFloat("_Cull", File.Exists(Path.Combine(Path.GetDirectoryName(RepoModel), "ga25x_propdisc.fbx")) ? 2f : 0f);
            }
            Save(disc, "propdisc");
            L("materials: " + string.Join(", ", mats.Keys) + $" (glass shader {glass.shader.name}, disc shader {disc.shader.name})");
        }

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
                int ai = Array.IndexOf(orderedNames, "ck_art");
                if (ai >= 0) foreach (var i in m.GetIndices(ai)) paintV.Add(i);   // 0.3.2 panel art keeps its atlas UVs on UV0
                int ti = Array.IndexOf(orderedNames, "ck_throttle");
                if (ti >= 0) foreach (var i in m.GetIndices(ti)) paintV.Add(i);   // 0.3.4 throttle handle keeps the model's UVs
                if (gl >= 0) foreach (var i in m.GetIndices(gl)) paintV.Add(i);
                if (sc >= 0) foreach (var i in m.GetIndices(sc)) paintV.Add(i);   // MFD quads keep their 0-1 screen UVs
                if (uv0.Count == m.vertexCount)
                {
                    for (int i = 0; i < uv0.Count; i++) if (!paintV.Contains(i)) uv0[i] = uv1[i];
                    m.SetUVs(0, uv0);
                }
            }
            // 0.3.1: stock aircraft_structure (Shader Graphs/Lit_vertexcolor) tints by vertex colour: the SFB-81 tub (sfb_cockpit_int)
            // uses 56/56/56 on its structure submesh. ck_struct vertices get that colour and UV0 = detail UV x 1.25 (stock texel
            // scale ~1.6 m per UV unit; our detail UV is 2 m per unit); all other vertices white (URP Lit ignores vertex colour).
            int ks = Array.IndexOf(orderedNames, "ck_struct");
            if (ks >= 0 && StockCabinStructure && uv1.Count == m.vertexCount)
            {
                var cols = Enumerable.Repeat(new Color32(255, 255, 255, 255), m.vertexCount).ToArray();
                var uvs0 = new List<Vector2>(); m.GetUVs(0, uvs0);
                foreach (var i in new HashSet<int>(m.GetIndices(ks))) { cols[i] = new Color32(56, 56, 56, 255); uvs0[i] = uv1[i] * 1.25f; }
                m.colors32 = cols; m.SetUVs(0, uvs0);
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

        // tac-screen mesh (TacScreenMesh vertex order: 0-3 backing quad, 4-7 map quad): map height / screen height
        static float MapFill(Mesh m)
        {
            var v = m.vertices; if (v.Length < 8) return 0f;
            float Ext(int a) { float lo = Mathf.Min(v[a].y, v[a + 1].y, v[a + 2].y, v[a + 3].y), hi = Mathf.Max(v[a].y, v[a + 1].y, v[a + 2].y, v[a + 3].y); return hi - lo; }
            return Ext(0) > 0 ? Ext(4) / Ext(0) : 0f;
        }

        static Mesh QuadMesh(string name, float w, float h)
        {
            return NewMesh(name, new[] { new Vector3(-w, -h, 0), new Vector3(w, -h, 0), new Vector3(w, h, 0), new Vector3(-w, h, 0) },
                new[] { 0, 2, 1, 0, 3, 2 }, new[] { Vector2.zero, Vector2.right, Vector2.one, Vector2.up });
        }

        // =================================================================== the prefab
        // First object of the model whose name matches one of the candidates (model-contract names first), or null.
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

        static void BuildPrefab()
        {
            // 1. our meshes and materials on every renderer
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                var mr = mf.GetComponent<MeshRenderer>();
                var names = mr.sharedMaterials.Select(m => m ? m.name.Replace(" (Instance)", "") : "null").ToArray();
                mf.sharedMesh = CopyMesh(mf.sharedMesh, mf.name, names, out var ordered);
                mr.sharedMaterials = ordered.Select(n => mats.TryGetValue(n, out var m) ? m : throw new Exception($"no material '{n}' for {mf.name}")).ToArray();
            }
            foreach (var t in root.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = 14;

            // 2. root components first (network identity + rigidbody before the NetworkBehaviours)
            GameObjectUtility.RemoveMonoBehavioursWithMissingScript(root);
            root.AddComponent<Mirage.NetworkIdentity>();
            var rb = root.AddComponent<Rigidbody>();
            EditorUtility.CopySerialized(tpl["COIN"].GetComponent<Rigidbody>(), rb);
            CloneComp(tpl["COIN"].GetComponent<Aircraft>(), root);

            // 3. structure: aero parts, re-parented so each part's transform parent is its parent part
            var specs = Parts();
            foreach (var s in specs) MakePartObject(s);
            foreach (var s in specs) MakeAeroPart(s);
            AddJoints(specs);

            // 4. systems on the cockpit part (as CI-22 cockpit_F)
            var cockpitGO = parts["fus_cockpit"].gameObject;
            controlsFilter = CloneComp(TplComp<ControlsFilter>("COIN:cockpit_F"), cockpitGO);
            weaponManager = CloneComp(TplComp<WeaponManager>("COIN:cockpit_F"), cockpitGO);
            CloneComp(TplComp<AutopilotPlane>("COIN:cockpit_F"), cockpitGO);
            Remap(aircraft); Remap(controlsFilter); Remap(weaponManager);

            ControlSurfaces();
            Flaps();
            var gears = Gear();
            Engines();
            var weapons = Weapons();
            Cockpit(gears);
            RootSystems(gears);
            FlyByWire(gears[0]);

            // final sweep: nothing may point into a stock prefab
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
            // 1.8.3: internals the stock way (StockStructure.cs): break-seam frames / ribs / stringer stubs and the firewall details drawn
            // with the stock aircraft_structure material (vertex colour 93), after the colliders are baked; paint renderers keep their data
            var ss = StockStructure.Apply(root, StockStructure.LookMaterial(Asset<Material>("Material/aircraft_structure_PLACEHOLDER.mat"), Folder, "GA25X"),
                new Dictionary<Material, Color32> { { mats["structure"], StockStructure.StockGrey } }, 1f, generatedMeshes);
            L($"stock structure: {ss.renderers} renderers, {ss.triangles} tris, {ss.children} structure children");
        }

        // ------------------------------------------------------------------ parts
        static void MakePartObject(PartSpec s)
        {
            GameObject go;
            if (s.name == "GA25X") go = root;
            else if (s.name.StartsWith("prop_"))
            {
                var hub = Find("prop_hub_" + s.name.Substring(5));
                go = NewGO(s.name, hub.parent, hub.position, Quaternion.identity);
                hub.SetParent(go.transform, true);
            }
            else if (s.lift == Lift.Hinge)
            {
                // control surface: part object at the hinge (local X = hinge axis); the mesh rotates under a hinge child
                var mesh = Find(s.mesh);
                mesh.name = s.name + "_visible";
                Quaternion rot = s.name.StartsWith("rudder") ? Quaternion.LookRotation(Vector3.forward, Vector3.left) : mesh.rotation;
                go = NewGO(s.name, mesh.parent, mesh.position, rot);
                var hinge = NewGO(s.name + "_hinge", go.transform, mesh.position, rot);
                mesh.SetParent(hinge.transform, true);
                liftNormals[s.name] = hinge.transform;
            }
            else go = Find(s.mesh).gameObject;
            go.name = s.name;
            if (s.parent != null)
            {
                go.transform.SetParent(partGO[s.parent].transform, true);
            }
            parts[s.name] = null;
            partGO[s.name] = go;
        }
        static readonly Dictionary<string, GameObject> partGO = new Dictionary<string, GameObject>();

        static void MakeAeroPart(PartSpec s)
        {
            var go = partGO[s.name];
            var src = TplComp<AeroPart>(s.template);
            var ap = CloneComp(src, go);
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

            // collider: convex hull of our own mesh, baked into the part frame
            MeshFilter own = s.name == "GA25X" ? Find("fus_center").GetComponent<MeshFilter>()
                : s.lift == Lift.Hinge ? Find(s.name + "_visible").GetComponent<MeshFilter>()
                : s.mesh != null ? go.GetComponent<MeshFilter>() : null;
            if (own != null)
            {
                var mc = go.AddComponent<MeshCollider>();
                mc.sharedMesh = BakeCollider(go.transform, s.name + "_col", own);
                mc.convex = true;
            }

            // lift frame
            Transform ln = null;
            if (s.lift == Lift.Hinge) ln = liftNormals[s.name];
            else if (s.lift == Lift.Wing || s.lift == Lift.Stab || s.lift == Lift.Fin)
            {
                Vector3 x = Vector3.right;
                if (s.lift == Lift.Wing) x = SpanDir(s.name);
                Quaternion q;
                if (s.lift == Lift.Fin) q = Quaternion.LookRotation(Vector3.forward, Vector3.left);
                else
                {
                    var y = Vector3.Cross(Vector3.forward, x).normalized;
                    q = Quaternion.LookRotation(Vector3.forward, y);
                    float inc = s.lift == Lift.Wing ? (s.name.StartsWith("wing_tip") ? TipIncidence : WingIncidence) : StabIncidence;
                    q = Quaternion.AngleAxis(-inc, q * Vector3.right) * q;
                }
                ln = NewGO(s.name + "_liftNormal", go.transform, go.transform.position, q).transform;
                // StolFlaps: the AeroPart reads a driven child (identity at rest) that the wing panel's HighLiftDevice rotates by FlapLiftFrameDeg
                if (StolFlaps && (s.name.StartsWith("wing_inner") || s.name.StartsWith("wing_outer")))
                    ln = NewGO(s.name + "_liftNormal_flap", ln, ln.position, ln.rotation).transform;
                liftNormals[s.name] = ln;
            }
            S(ap, "liftNormal", ln);

            // lift acts at the quarter chord of our own surface (offset from the part's collider centroid)
            Vector3 col = Vector3.zero;
            if (s.wingArea > 0.9f && own != null && ln != null)
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

            // livery/damage renderers: the paint renderers that belong to this part (not to child parts)
            var rends = PartRenderers(go).Where(r => r.sharedMaterials.Length > 0 && r.sharedMaterials[0] == mats["paint"]).Cast<Renderer>().ToList();
            var dm = G(ap, "damageMaterial");
            S(dm, "renderers", rends);
        }

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

        static Vector3 SpanDir(string name)
        {
            // panel span from our pivots (B-25 gull wing: inner panels ~5 deg dihedral, outer ~0)
            string side = name.Substring(name.Length - 1);
            Vector3 a, b;
            if (name.StartsWith("wing_inner")) { a = partGO[name].transform.position; b = partGO["wing_outer_" + side].transform.position; }
            else { a = partGO["wing_outer_" + side].transform.position; b = partGO["wing_tip_" + side].transform.position; }
            var d = b - a; d.z = 0; d.Normalize();
            if (d.x < 0) d = -d; // +X on both sides, like the stock wings
            return d;
        }

        static void AddJoints(List<PartSpec> specs)
        {
            var bySpec = specs.ToDictionary(s => s.name);
            var joined = new HashSet<(string, string)>();
            var jointLists = specs.ToDictionary(s => s.name, s => new List<PartJoint>());
            var breakSnd = TplComp<AeroPart>("CAS1:wing2_L").Joints[0].breakSound;
            PartJoint J(string to, string tensor, float force) => new PartJoint
            { connectedPart = parts[to], tensor = tensor == null ? null : parts[tensor], solverIterations = 6, breakForce = force, breakTorque = force, breakSound = breakSnd };
            void Add(string a, string b, string tensor, float f) { jointLists[a].Add(J(b, tensor, f)); joined.Add((a, b)); joined.Add((b, a)); }
            foreach (var s in specs)
            {
                if (s.parent == null) continue;
                Add(s.name, s.parent, null, s.joint);                     // primary (also the detach link)
                var gp = bySpec[s.parent].parent;
                if (gp != null) Add(s.name, gp, s.parent, s.joint * 0.5f); // to the grandparent, breaks with the parent (stock pattern)
            }
            // Unity only skips contacts between directly jointed bodies: join every other pair whose hulls may touch.
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
                    // owner = the deeper part; tensor = the other part, so the link goes when either one breaks off
                    int da = Depth(bySpec, a), db = Depth(bySpec, b);
                    var owner = da >= db ? a : b; var other = owner == a ? b : a;
                    Add(owner, other, other == "GA25X" ? bySpec[owner].parent : other, Mathf.Min(bySpec[a].joint == 0 ? 1e6f : bySpec[a].joint, bySpec[b].joint == 0 ? 1e6f : bySpec[b].joint) * 0.3f);
                    extra++; L($"overlap joint {owner} -> {other}");
                }
            foreach (var s in specs) S(parts[s.name], "joints", jointLists[s.name].ToArray());
            L($"joints: {jointLists.Values.Sum(x => x.Count)} total, {extra} anti-overlap");
        }

        static int Depth(Dictionary<string, PartSpec> by, string n) { int d = 0; while (by[n].parent != null) { n = by[n].parent; d++; } return d; }

        static Bounds WorldBounds(MeshCollider c)
        {
            var b = c.sharedMesh.bounds; var t = c.transform;
            var wb = new Bounds(t.TransformPoint(b.center), Vector3.zero);
            for (int i = 0; i < 8; i++)
                wb.Encapsulate(t.TransformPoint(b.center + Vector3.Scale(b.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1))));
            return wb;
        }

        // ------------------------------------------------------------------ control surfaces (CAS1 values, our hinges)
        static void ControlSurfaces()
        {
            foreach (var side in new[] { "L", "R" })
            {
                float sgn = side == "L" ? -1f : 1f;
                // signs as CAS1 for the same hinge-axis convention (local X ~ +X on both sides; rudder X = up)
                CS("aileron_" + side, "CAS1:aileron_" + side, 0, 20f * sgn, 0, 60f);
                CS("elevator_" + side, "CAS1:elevator_" + side, ElevatorDeflection, 0, 0, 40f);
                CS("rudder_" + side, "CAS1:rudder_L", 0, 0, -18f, 45f);
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

        // ------------------------------------------------------------------ flaps: CI-22 style HighLiftDevice on each flap part
        // 0.1.0: CI-22 style HighLiftDevice on each flap part whose moving part was the flap's own lift frame (hinge): +25 deg aoa on the
        // flap = past its stall (wing curve peak 16 deg), so the flaps cut lift (in game: flapped minimum ~199 km/h vs clean 184-208).
        // StolFlaps (0.2.0): the stock wing-panel pattern (CAS1 wing2_L: HLD on the wing AeroPart, +2 m^2 on 6; Multirole1 wing1: +6 on 10;
        // FastBomber1 flap: +5 on 4): a HighLiftDevice on each inner/outer wing panel adds area and turns the panel's lift frame by
        // FlapLiftFrameDeg (camber); the flap parts keep their lift frame and only draw the flap (visual pivot under the hinge).
        static void Flaps()
        {
            object MP(Transform t, float deg)
            {
                var mp = NewElem(TplComp<HighLiftDevice>("COIN:flap_L"), "movingParts");
                S(mp, "move", false); S(mp, "rotate", true); S(mp, "transform", t);
                S(mp, "positionRetracted", Vector3.zero); S(mp, "positionDeployed", Vector3.zero);
                S(mp, "anglesRetracted", Vector3.zero); S(mp, "anglesDeployed", new Vector3(-deg, 0, 0)); // -X = TE down / nose up
                return mp;
            }
            HighLiftDevice HLD(AeroPart part, float area, float vDep, float vRet, object movingPart)
            {
                var h = CloneComp(TplComp<HighLiftDevice>("COIN:flap_L"), part.gameObject);
                S(h, "aeroPart", part); S(h, "swingWingController", null);
                S(h, "speedDeployed", vDep); S(h, "speedRetracted", vRet);
                S(h, "alphaMin", 0f); S(h, "alphaFactor", 0f);
                S(h, "deployedArea", area);
                var arr = Array.CreateInstance(movingPart.GetType(), 1); arr.SetValue(movingPart, 0); S(h, "movingParts", arr);
                return h;
            }
            foreach (var f in new[] { "flap_inner_L", "flap_inner_R", "flap_outer_L", "flap_outer_R" })
            {
                if (!StolFlaps)
                {
                    HLD(parts[f], f.Contains("inner") ? 0.4f : 0.6f, 55f, 68f, MP(liftNormals[f], 25f));   // B-25 flap limit 150 mph = 67 m/s
                    continue;
                }
                // visual pivot between the hinge (= the flap's lift frame, left alone) and the flap mesh
                var hinge = liftNormals[f];
                var vis = NewGO(f + "_flapvis", hinge, hinge.position, hinge.rotation);
                foreach (var c in hinge.Cast<Transform>().Where(c => c != vis.transform).ToList()) c.SetParent(vis.transform, true);
                HLD(parts[f], 0f, FlapSpeedDeployed, FlapSpeedRetracted, MP(vis.transform, FlapVisualDeg));
            }
            if (!StolFlaps) return;
            foreach (var side in new[] { "L", "R" })
                foreach (var (w, area) in new[] { ("wing_inner_" + side, FlapAreaInner), ("wing_outer_" + side, FlapAreaOuter) })
                {
                    var ln = liftNormals[w];   // the driven _liftNormal_flap child (identity in its static frame)
                    HLD(parts[w], area, FlapSpeedDeployed, FlapSpeedRetracted, MP(ln, FlapLiftFrameDeg));
                    L($"flap HLD on {w}: +{area} m^2, lift frame {ln.name} +{FlapLiftFrameDeg} deg, full below {FlapSpeedDeployed} m/s, none above {FlapSpeedRetracted}");
                }
        }

        // ------------------------------------------------------------------ landing gear
        class GearSpec { public string strut, wheel, part; public float fold, travel, k, c, maxComp, mass, drag; public bool steer, brake; public float diff; public (string door, Vector3 axis, float open)[] doors; }

        static List<LandingGear> Gear()
        {
            // door hinge axes (parent space, Unity) and opening angles from the model contract (B-25H values as fallback: same wells)
            var dmap = new Dictionary<string, (Vector3 axis, float open)>();
            foreach (var d in JList("doors")) dmap[(string)d["name"]] = (J3(d["axis_unity"]), (float)d["open_unity"]);
            (string, Vector3, float) D(string n, Vector3 fa, float fo) => dmap.TryGetValue(n, out var v) ? (n, v.axis, v.open) : (n, fa, fo);
            var list = new List<LandingGear>();
            // strengthened gear (spec): springs/dampers +30 % over the B-25H (MTOW 17.5 t vs 15.9 t, short-field and carrier landings)
            var nose = new GearSpec
            {
                strut = "gear_nose_strut", wheel = "gear_nose_wheel", part = "fus_cockpit", fold = 110f, travel = 0.379f + 0.25f, k = 850000f, c = 52000f, maxComp = 0.40f,
                mass = 140f, drag = 0.4f, steer = true, brake = false, diff = 0f,
                doors = new[] { D("gear_door_nose_L", new Vector3(-0.0002f, 0.0084f, 1.0f), -95f), D("gear_door_nose_R", new Vector3(0.0002f, 0.0084f, 1.0f), 95f) }
            };
            list.Add(MakeGear(nose, "CAS1:gear_F_sprung", "COIN:wheel_F"));
            foreach (var s in new[] { "L", "R" })
            {
                var m = new GearSpec
                {
                    strut = $"gear_main_{s}_strut", wheel = $"gear_main_{s}_wheel", part = "nacelle_" + s, fold = 88f, travel = 0.595f + 0.30f, k = 980000f, c = 78000f, maxComp = 0.45f,
                    mass = 290f, drag = 0.8f, steer = false, brake = true, diff = s == "L" ? -1f : 1f,
                    doors = s == "L"
                        ? new[] { D("gear_door_main_L_a", new Vector3(0.0195f, -0.0878f, 0.9959f), 95f), D("gear_door_main_L_b", new Vector3(-0.0195f, -0.0878f, 0.9959f), -95f) }
                        : new[] { D("gear_door_main_R_a", new Vector3(-0.0195f, -0.0878f, 0.9959f), -95f), D("gear_door_main_R_b", new Vector3(0.0195f, -0.0878f, 0.9959f), 95f) }
                };
                list.Add(MakeGear(m, "CAS1:gear_" + s + "_sprung", "COIN:wheel_" + s));
            }
            return list;
        }

        static LandingGear MakeGear(GearSpec g, string tplGear, string tplWheel)
        {
            var strut = Find(g.strut); var wheel = Find(g.wheel); var part = parts[g.part];
            float r = wheel.GetComponent<MeshFilter>().sharedMesh.bounds.extents.y;
            Vector3 axle = wheel.position;
            var hinge = NewGO(g.strut.Replace("_strut", "_hinge"), part.transform, strut.position, part.transform.rotation);
            strut.SetParent(hinge.transform, true);
            var sprung = NewGO(g.strut.Replace("_strut", "_leg"), hinge.transform, strut.position, part.transform.rotation);
            var unsprung = NewGO(g.strut.Replace("_strut", "_unsprung"), sprung.transform, axle, part.transform.rotation);
            wheel.SetParent(unsprung.transform, true);
            var bump = NewGO(g.strut.Replace("_strut", "_bumpstop"), sprung.transform, axle + Vector3.up * (g.travel - r), part.transform.rotation);
            // wheel effects/sound copied from the CI-22 wheels (dust particle + rolling/skid loops)
            var dust = CopyParticle(TplFind(tplWheel).GetComponent<ParticleSystem>(), unsprung.transform, axle - Vector3.up * r, g.strut + "_dust");
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
            S(lg, "castPoint", bump.transform); S(lg, "wheelRadius", r);
            S(lg, "wheels", new[] { wheel }); S(lg, "axle", unsprung.transform);
            SetSeq(lg, "joints", new object[0]);
            S(lg, "tireNoiseSound", a0); S(lg, "tireSkidSound", a1);
            S(lg, "maxCompression", g.maxComp); S(lg, "mass", g.mass); S(lg, "gearCollider", box);
            if (NoseContact186F && g.strut == "gear_nose_strut") S(lg, "contactArea", NoseContactArea186F);   // 1.8.6F: dirt drag only
            S(lg, "gearHinge", hinge.transform); S(lg, "hingeFoldMotion", Vector3.zero);
            S(lg, "foldDegrees", g.fold); S(lg, "foldSpeed", 15f);
            S(lg, "strutRotationTransform", null); S(lg, "strutRotation", 0f);
            SetSeq(lg, "movingParts", new object[0]);
            S(lg, "steering", g.steer); S(lg, "braked", g.brake);
            S(lg, "steeringLock", g.steer ? 30f : 0f); S(lg, "steeringSpeed", g.steer ? 40f : 0f); S(lg, "aligningStrength", g.steer ? 5f : 0f);
            S(lg, "differentialBrakeFactor", g.diff);
            S(lg, "dust", dust);
            var doors = new List<LandingGear.GearDoor>();
            foreach (var (dn, axis, open) in g.doors)
            {
                var hb = DoorHinge(Find(dn), axis.normalized, open, true);
                doors.Add(new LandingGear.GearDoor { transform = hb, closedAngle = Vector3.zero, openAngle = new Vector3(0, 0, open) });
            }
            S(lg, "gearDoors", doors);
            L($"gear {g.strut}: r={r:F3} axle={axle.ToString("F3")} travel={g.travel} k={g.k} fold={g.fold}");
            return lg;
        }

        // hingeA: fixed, local Z = hinge axis; hingeB: animated (localEulerAngles.z), holds the door in its CLOSED pose.
        static Transform DoorHinge(Transform door, Vector3 axisParent, float openDeg, bool openInFile)
        {
            var parent = door.parent;
            var axisW = parent.TransformDirection(axisParent).normalized;
            var perp = Vector3.Cross(axisW, Vector3.right).sqrMagnitude > 0.01f ? Vector3.Cross(axisW, Vector3.right).normalized : Vector3.up;
            var qa = Quaternion.LookRotation(axisW, perp);
            var ha = NewGO(door.name + "_hingeA", parent, door.position, qa);
            var hb = NewGO(door.name + "_hingeB", ha.transform, door.position, qa);
            if (openInFile) door.rotation = Quaternion.AngleAxis(-openDeg, axisW) * door.rotation; // back to closed
            door.SetParent(hb.transform, true);
            hb.transform.localEulerAngles = new Vector3(0, 0, openInFile ? openDeg : 0f);   // show as in file
            L($"door {door.name}: hinge axis {axisW.ToString("F3")} open {openDeg} closed-pose deviation from identity {Quaternion.Angle(Quaternion.Inverse(parent.rotation) * Quaternion.AngleAxis(-(openInFile ? openDeg : 0f), axisW) * door.rotation, Quaternion.identity):F2} deg");
            return hb.transform;
        }

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

        // ------------------------------------------------------------------ engines and propellers (CI-22 style, twice)
        static void Engines()
        {
            var startup = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), parts["fus_cockpit"].gameObject);
            foreach (var s in new[] { "L", "R" })
            {
                var eng = parts["engine_" + s].gameObject;
                // engine sound: CI-22 turbine loop as the turbine whine source (TurbineEngine wants its own AudioSource)
                var turb = CloneComp(TplAudio("COIN:COIN", "cricket_turbine"), eng);
                var te = CloneComp(TplComp<TurbineEngine>("CAS1:engine_" + s), eng);
                te.maxRPM = TurbineMaxRPM; te.minRPM = 0.2f * TurbineMaxRPM; te.maxPower = EnginePower + (BoostInMaxPower ? BoostPower : 0f); te.spoolUpTime = 3.0f; S(te, "startupTime", 8f);
                S(te, "pitch", 0.15f); S(te, "volume", 0.20f);   // turbine whine (CI-22 clip), louder than the B-25H radial
                S(te, "startupAudio", startup); te.aircraft = aircraft;
                S(te, "heatHazeParticles", new ParticleSystem[0]);
                S(te, "maxFuelConsumption", 0.19f); S(te, "IRMin", 1.0f); S(te, "IRMax", 1.3f);   // 2.4 MW at ~0.28 kg/kWh; exhaust coolers: half the A-19 turboprop IR (2.0/2.5)
                S(te, "IRSourceTransform", Find("exhaust_" + s));
                S(te, "criticalParts", new UnitPart[] { parts["engine_" + s], parts["prop_" + s] });
                S(te, "criticalDamageThreshold", 40f);
                S(te, "failureTransform", NewGO("engine_" + s + "_fail", eng.transform, eng.transform.position + new Vector3(0, 0.3f, 0.4f), Quaternion.identity).transform);
                var tr = CloneComp(TplComp<Transmission>("COIN:COIN"), eng);
                if (HybridBoost) Boost(s, eng);
                S(tr, "powerSources", new[] { eng });

                // propeller part: ConstantSpeedProp on its own hub, driving its own hub mesh
                var propGO = parts["prop_" + s].gameObject;
                var hubVis = Find("prop_hub_" + s);
                var pa = CloneComp(TplAudio("COIN:propHub", "cricket_exterior"), propGO);
                var csp = CloneComp(TplComp<ConstantSpeedProp>("COIN:propHub"), propGO);
                S(csp, "unitPart", parts["prop_" + s]); S(csp, "transmission", tr); S(csp, "oppositeCorner", null);
                // TurnDirection.clockwise (1) = clockwise seen from behind for a forward-facing hub (both R-2600s)
                var fTurn = Fld(typeof(ConstantSpeedProp), "turnDirection"); fTurn.SetValue(csp, Enum.ToObject(fTurn.FieldType, 1));
                var fPitch = Fld(typeof(ConstantSpeedProp), "pitchDirection"); fPitch.SetValue(csp, Enum.ToObject(fPitch.FieldType, -1)); // as CI-22 (forward thrust)
                var blades = new List<object>(); var dmgMeshes = new List<Mesh>();
                float R = 0f;
                var bladeMFs = hubVis.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.Contains("_blade")).OrderBy(m => m.name).ToList();
                foreach (var bmf in bladeMFs)
                {
                    var radial = bmf.transform.up; // blade meshes point along their local +Y
                    float tip = bmf.sharedMesh.bounds.max.y; R = Mathf.Max(R, tip);
                    var F = propGO.transform.forward;
                    var broot = NewGO(bmf.name + "_root", hubVis, hubVis.position, Quaternion.LookRotation(radial, Vector3.Cross(radial, -F)));
                    bmf.transform.SetParent(broot.transform, true);
                    var tang = Vector3.Cross(-F, radial); // motion direction for turnDirection = 1
                    var lt = NewGO(bmf.name + "_lift", broot.transform, hubVis.position + radial * tip, Quaternion.LookRotation(tang, F));
                    var b = New(typeof(ConstantSpeedProp.PropBlade));
                    S(b, "transform", broot.transform); S(b, "liftTransform", lt.transform); S(b, "mass", 18f);   // composite blade
                    ((ConstantSpeedProp.PropBlade)b).renderer = bmf.GetComponent<MeshRenderer>();
                    ((ConstantSpeedProp.PropBlade)b).bladeMeshFilter = bmf;
                    blades.Add(b);
                    if (dmgMeshes.Count == 0)
                        foreach (var frac in new[] { 0.25f, 0.5f, 0.75f, 0.95f }) dmgMeshes.Add(TruncatedBlade(bmf.sharedMesh, tip * frac, $"{bmf.name}_dmg{(int)(frac * 100)}"));
                }
                SetSeq(csp, "blades", blades);
                S(csp, "hubVisible", hubVis.gameObject);
                // blur disc holder: the model's own disc object when the contract provides one (its mesh is replaced by the
                // stage meshes; ConstantSpeedProp swaps propDisc.mesh between propDiscMeshes[0..2] by rpm), else a new child.
                var modelDisc = ContractFind("prop_disc_" + s, "propdisc_" + s, "prop_blur_" + s, "prop_" + s + "_disc_model");
                GameObject disc;
                if (modelDisc != null)
                {
                    disc = modelDisc.gameObject; // contract slot: child of prop_hub, local +Z = spin axis (kept as authored)
                    if (disc.transform.parent != hubVis) disc.transform.SetParent(hubVis, true);
                    if (disc.GetComponent<MeshFilter>() == null) disc.AddComponent<MeshFilter>();
                    if (disc.GetComponent<MeshRenderer>() == null) disc.AddComponent<MeshRenderer>();
                    disc.GetComponent<MeshRenderer>().sharedMaterials = new[] { mats["propdisc"] };
                    L($"prop {s}: using model disc object {modelDisc.name} as the blur holder");
                }
                else
                {
                    disc = NewGO("prop_" + s + "_disc", hubVis, hubVis.position + hubVis.forward * 0.02f, hubVis.rotation);
                    disc.AddComponent<MeshFilter>(); disc.AddComponent<MeshRenderer>().sharedMaterial = mats["propdisc"];
                }
                var dr = disc.GetComponent<MeshRenderer>(); dr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                disc.GetComponent<MeshFilter>().sharedMesh = null; // stage 0 (stopped / slow): blades only
                Mesh stage1, stage2;
                bool modelStages = OwnPropBlur && modelBlur != null && modelFull != null && modelDisc != null;
                if (modelStages) { stage1 = modelBlur; stage2 = modelFull; }
                else if (OwnPropBlur) { stage1 = BlurStageMesh("prop_blur1_" + s, R * 1.01f, 0.5f); stage2 = BlurStageMesh("prop_blur2_" + s, R * 1.01f, 0f); }
                else { stage1 = stage2 = DiscMesh("prop_disc_" + s, R, 48); }
                S(csp, "propDisc", disc.GetComponent<MeshFilter>());
                S(csp, "bladeDamageMeshes", dmgMeshes.ToArray());
                S(csp, "fragmentPrefab", null);
                // index = floor(3 * (rpm/rpmLimit * 0.55 * timeScale + 0.25)): stage 1 from 15 % rpm, stage 2 from 76 % (ConstantSpeedProp.cs:630)
                SetSeq(csp, "propDiscMeshes", new Mesh[] { null, stage1, stage2 });
                if (modelStages) { S(csp, "propDiskThicknessMin", 0.5f); S(csp, "propDiskThicknessMax", 3f); } // CI-22 values (contract: 8 mm discs)
                else { S(csp, "propDiskThicknessMin", 1f); S(csp, "propDiskThicknessMax", 1f); } // flat generated discs: keep z scale 1
                L($"prop {s}: blur stages {(modelStages ? "model propdisc_blur/full" : "generated")} on {disc.name}");
                S(csp, "propBlurLightsMaterial", null);
                var strikeGO = NewGO("prop_" + s + "_strike", propGO.transform, hubVis.position, propGO.transform.rotation, 15);
                var smc = strikeGO.AddComponent<MeshCollider>(); smc.sharedMesh = CylinderMesh("prop_strike_" + s, R, 0.06f, 24); smc.convex = true; smc.isTrigger = true;
                var psd = CloneComp(TplComp<PropStrikeDetector>("COIN:propDiscCollider"), strikeGO);
                S(psd, "currentRadius", R); S(psd, "propCollider", smc);
                S(csp, "propDiscCollider", smc); S(csp, "propStrikeDetector", psd);
                S(csp, "momentOfInertia", 120f); S(csp, "bladeLength", R); S(csp, "hubRadius", 0.34f);
                S(csp, "rpmLimit", PropRpm); S(csp, "nominalPower", EnginePower + (BoostInMaxPower ? BoostPower : 0f)); S(csp, "propTorqueLimit", 30000f);   // 2.4 MW / 115 rad/s = 21 kN m
                if (LowDragAirframe) S(csp, "bladeEfficiency", 0.42f);   // composite scimitar blades (CI-22 template 0.38); ConstantSpeedProp blade normal force scales with it
                // reverse pitch: the CI-22 reversePitchBraking (12) is kept from the template; docs/ga25x_design.md explains why it is inert in the stock code
                S(csp, "propAudio", pa);
                L($"prop {s}: radius {R:F3} m, {blades.Count} blades, rpmLimit {PropRpm}, hub {hubVis.position.ToString("F3")}");
            }
        }


        // Electric boost (spec: +900 kW motor per engine, "like an afterburner"). Stock mechanism: Turbojet.FixedUpdate ->
        // JetNozzle.Thrust(..., allowAfterburner) -> Afterburner.Run(throttle * (rpmRatio > 0.85)): amount = (throttle - 0.9) / 0.1,
        // thrust * clamp(airDensity, 0.4, 1) applied on the nozzle part, afterburner fuel added to the Turbojet's fuel use.
        // Values start from the stock Fighter1 Turbojet/JetNozzle; the Turbojet itself makes ~0 thrust and uses no fuel.
        // Afterburner.Run is not null-safe (flame/glow renderers, audio source): mesh-less renderers and a clip-less source.
        static void Boost(string s, GameObject eng)
        {
            var tjSrc = tpl["Fighter1"].GetComponentInChildren<Turbojet>(true);
            var jnSrc = tpl["Fighter1"].GetComponentInChildren<JetNozzle>(true);
            var fwd = parts["prop_" + s].transform.forward;
            var bg = NewGO("boost_" + s, eng.transform, Find("exhaust_" + s).position, Quaternion.LookRotation(fwd, Vector3.up));
            var silent = CloneComp(TplAudio("COIN:COIN", "cricket_turbine"), bg); silent.volume = 0f; silent.playOnAwake = false;
            var abSrc = bg.AddComponent<AudioSource>(); abSrc.clip = null; abSrc.playOnAwake = false; abSrc.volume = 0f; abSrc.spatialBlend = 1f;
            var fx = NewGO("boost_" + s + "_fx", bg.transform, bg.transform.position, bg.transform.rotation);
            fx.AddComponent<MeshFilter>();
            var fxr = fx.AddComponent<MeshRenderer>(); fxr.sharedMaterial = mats["propdisc"]; fxr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; fxr.enabled = false;
            var tj = CloneComp(tjSrc, bg);
            var jn = CloneComp(jnSrc, bg);
            tj.maxThrust = 1f; // ~0 N; non-zero keeps GetThrustRatio finite
            S(tj, "turbineAudio", silent); S(tj, "nozzles", new[] { jn }); S(tj, "vectoringTransforms", new Transform[0]);
            S(tj, "thrustVectoring", Vector3.zero); S(tj, "splitThrustFactor", 0f);
            S(tj, "fuelConsumptionMin", 0f); S(tj, "fuelConsumptionMax", 0f);
            S(tj, "criticalParts", new UnitPart[] { parts["engine_" + s], parts["prop_" + s] });
            S(tj, "failureMessage", ""); S(tj, "failureMessageAudio", null);
            S(jn, "part", parts["engine_" + s]); S(jn, "turbojet", tj); S(jn, "engine", null);
            S(jn, "thrustTransform", bg.transform); S(jn, "vectorTransforms", new Transform[0]); S(jn, "glow", null);
            S(jn, "thrustAudio", silent); S(jn, "thrustMaxVolume", 0f); S(jn, "IRMin", 0f); S(jn, "IRMax", 0f);
            S(jn, "thrustProportion", 1f); S(jn, "pitchThrust", 0f); S(jn, "rollThrust", 0f);
            var abs = (Array)G(jn, "afterburners");
            var ab = abs.Length > 0 ? abs.GetValue(0) : NewElem(jn, "afterburners");
            S(ab, "flameRenderer", fxr); S(ab, "nozzleGlowRenderer", fxr); S(ab, "thrustDirection", bg.transform); S(ab, "source", abSrc);
            S(ab, "throttleStart", 0.9f); S(ab, "throttleEnd", 1f); S(ab, "thrust", BoostThrust); S(ab, "fuelConsumption", BoostFuel);
            S(ab, "flameBrightness", 0f); S(ab, "nozzleGlowBrightness", 0f); S(ab, "temperature", 0f); S(ab, "IRIntensity", BoostIR);
            var arr = Array.CreateInstance(ab.GetType(), 1); arr.SetValue(ab, 0); S(jn, "afterburners", arr);
            L($"boost {s}: Turbojet+JetNozzle on {bg.name}, afterburner {BoostThrust} N from throttle 0.9, fuel {BoostFuel} kg/s, IR {BoostIR}, failureEffect {(G(jn, "failureEffect") as Object)?.name}");
        }

        static Mesh TruncatedBlade(Mesh src, float maxY, string name)
        {
            var m = Object.Instantiate(src); m.name = name;
            m.vertices = src.vertices.Select(v => new Vector3(v.x, Mathf.Min(v.y, maxY), v.z)).ToArray();
            m.RecalculateBounds(); generatedMeshes.Add(m);
            return m;
        }

        // ------------------------------------------------------------------ weapons
        // Wing drag (incl. induced) vs AoA in rad. Up to ~6 deg it matches the CI-22 curve used before (so cruise and max
        // speed are unchanged); above that it follows CD0 + CL^2/(pi*AR*e) for AR 7.5, e 0.8 instead of the CI-22's
        // 0.15 at 11.5 deg / 0.26 at 16 deg, which made L/D ~3.5 near CLmax: in game (2026-10-30) the AI rotated at
        // 48 m/s and then could not accelerate or climb at 52 m/s / 15 deg nose-up with full power.
        static AnimationCurve WingDrag()
        {
            // LowDragAirframe: composite skin, only the low-alpha end changes (CD0 0.008 -> 0.0068, 0.021 -> 0.0192 at 3.4 deg)
            var pts = LowDragAirframe
                ? new[] { (0f, 0.0068f), (0.06f, 0.0192f), (0.1f, 0.034f), (0.2f, 0.082f), (0.28f, 0.13f), (0.35f, 0.25f), (0.5f, 0.5f), (1.51f, 1.7f), (3.14159f, 0f) }
                : new[] { (0f, 0.008f), (0.06f, 0.021f), (0.1f, 0.036f), (0.2f, 0.082f), (0.28f, 0.13f), (0.35f, 0.25f), (0.5f, 0.5f), (1.51f, 1.7f), (3.14159f, 0f) };
            var keys = new List<Keyframe>();
            foreach (var (t, v) in pts.Reverse()) if (t > 0f) keys.Add(new Keyframe(-t, v));
            foreach (var (t, v) in pts) keys.Add(new Keyframe(t, v));
            var c = new AnimationCurve(keys.ToArray());
            for (int i = 0; i < c.length; i++) c.SmoothTangents(i, 0f);
            return c;
        }

        static WeaponMount ammoCannon, ammo20, laserAmmo, hookMount;
        static int weaponManagerSetCount;
        static GameObject laserGO;                // laser mount object (Laser + beam), saved as the GA25X_laser prefab
        static GameObject hookGO;                 // own tail-hook mount object, saved as a prefab after the mesh bank exists
        static WeaponInfo laserInfo;
        static List<Gun> Weapons()
        {
            var nose = parts["fus_nose"]; var cockpit = parts["fus_cockpit"];
            // ---- 76 mm: Gun copied from the stock VL-49 Tarantula side mount (turret_76mm_SideMount/.../gun: guidedProjectile =
            // Shell_76mm_guided, 60 rpm, autoloader sounds), fixed forward on our nose axis, 96 rounds.
            var cannon = Find("cannon");
            var cannonMount = NewGO("cannon_mount", nose.transform, cannon.position, Quaternion.identity);
            var cannonRecoil = NewGO("cannon_recoil", cannonMount.transform, cannon.position, Quaternion.identity);
            cannon.SetParent(cannonRecoil.transform, true);
            var t76 = tpl["turret_76mm_SideMount"].GetComponentInChildren<Gun>(true);
            foreach (var a in t76.GetComponents<AudioSource>()) CloneComp(a, cannonMount).loop = false;
            var gun76 = CloneComp(t76, cannonMount);
            gun76.attachedUnit = aircraft;
            S(gun76, "magazineCapacity", CannonRounds); S(gun76, "magazines", 0); S(gun76, "startLoaded", true);
            S(gun76, "muzzles", new[] { Find("muzzle_cannon") });
            S(gun76, "recoilTransform", cannonRecoil.transform); S(gun76, "recoilTravel", 0.25f);
            S(gun76, "recoilSound", null); S(gun76, "reloadSound", null); S(gun76, "spinTransform", null);
            S(gun76, "ejectionTransform", null); S(gun76, "ejectionPrefab", null);   // autoloader keeps the casings
            S(gun76, "muzzleParticles", CopyMuzzleParticles(t76, Find("muzzle_cannon")));
            S(gun76, "heatEnabled", false);   // the stock heat model's steam/sound objects live in the Tarantula mount, not on our airframe
            var info76 = t76.info;
            if (OwnCannonWeaponInfo)
            {
                var own = Object.Instantiate(info76); own.name = "GA25X_76mm_info";
                own.boresight = true;          // fixed forward gun (the Tarantula's info is a turret's: boresight 0)
                if (GunRangeStock181) own.targetRequirements.maxRange = 3000f;   // 1.8.1: AI fire window as the stock A-19 30 mm (was 25000)
                if (CannonAirOnlyForAI) own.targetRequirements.minAltitude = 150f;
                if (CannonGroundPriority183D) own.effectiveness.antiSurface = 1.2f;   // 1.8.3D: AI ground-weapon choice (0.63 = the Tarantula's)
                AssetDatabase.CreateAsset(own, Folder + "/GA25X_76mm_info.asset");
                info76 = own;
            }
            gun76.info = info76;

            // ---- 20 mm: one Gun per package fairing, copied from the stock gun_20mm_pod ("20mm Autocannon", CI-22 / A-19 gun pod), 250 rounds each
            var g20 = tpl["gun_20mm_pod"].GetComponentInChildren<Gun>(true);
            var info20 = Object.Instantiate(g20.info); info20.name = "GA25X_20mm_info";
            info20.boresight = true;
            if (FixedGunsAirOnlyForAI) info20.targetRequirements.minAltitude = 150f;
            AssetDatabase.CreateAsset(info20, Folder + "/GA25X_20mm_info.asset");
            Gun Gun20(string side)
            {
                var at = Find("package_guns_" + side); var mz = Find("muzzle_package_" + side + "1");
                var go = NewGO("gun20_" + side, cockpit.transform, mz.position, Quaternion.identity);
                foreach (var a in g20.GetComponents<AudioSource>()) CloneComp(a, go).loop = false;
                var g = CloneComp(g20, go);
                g.attachedUnit = aircraft; g.info = info20;
                S(g, "magazineCapacity", Gun20Rounds); S(g, "magazines", 0); S(g, "startLoaded", true);
                S(g, "muzzles", new[] { mz });
                S(g, "recoilTransform", null); S(g, "spinTransform", null); S(g, "ejectionTransform", null); S(g, "ejectionPrefab", null);
                S(g, "muzzleParticles", CopyMuzzleParticles(g20, mz));
                S(g, "heatEnabled", false);
                return g;
            }
            var gL = Gun20("L"); var gR = Gun20("R");

            // ---- ammunition mounts (our own WeaponMount assets; info = the stock-derived infos above)
            var ammoPrefabGO = new GameObject("GA25X_internal_ammo");
            var ammoPrefab = PrefabUtility.SaveAsPrefabAsset(ammoPrefabGO, Folder + "/GA25X_internal_ammo.prefab");
            Object.DestroyImmediate(ammoPrefabGO);
            var tAmmo = Asset<WeaponMount>("MonoBehaviour/gun_ammo_35mm_720_PLACEHOLDER.asset");
            ammoCannon = Object.Instantiate(tAmmo); ammoCannon.name = "GA25X_ammo_76mm";
            ammoCannon.prefab = ammoPrefab; ammoCannon.jsonKey = "GA25X_ammo_76mm"; ammoCannon.info = info76; ammoCannon.mountName = $"76mm Guided x{CannonRounds}";
            ammoCannon.ammo = CannonRounds; ammoCannon.GunAmmo = true; ammoCannon.mass = CannonRounds * 12f;   // 6.5 kg projectile + case
            AssetDatabase.CreateAsset(ammoCannon, Folder + "/GA25X_ammo_76mm.asset");
            ammo20 = Object.Instantiate(tAmmo); ammo20.name = "GA25X_ammo_20mm";
            ammo20.prefab = ammoPrefab; ammo20.jsonKey = "GA25X_ammo_20mm"; ammo20.info = info20;
            ammo20.mountName = $"20mm x2 ({Gun20Rounds} rpg)"; ammo20.ammo = 2 * Gun20Rounds; ammo20.GunAmmo = true; ammo20.mass = 2 * Gun20Rounds * 0.26f;
            AssetDatabase.CreateAsset(ammo20, Folder + "/GA25X_ammo_20mm.asset");

            // ---- hardpoints
            var sets = new List<HardpointSet>();
            HardpointSet Set(string name, IEnumerable<WeaponMount> options, params Hardpoint[] hps)
            {
                var hs = new HardpointSet { name = name, precludingHardpointSets = new List<byte>(), SymmetryWithPrev = false, SymmetryName = "", weaponOptions = new List<WeaponMount> { null }, hardpoints = hps.ToList() };
                hs.weaponOptions.AddRange(options);
                sets.Add(hs); return hs;
            }
            Hardpoint HP(Transform t, AeroPart part, Weapon[] builtIn = null, BayDoor[] doors = null, float doorTime = 1f)
            {
                var h = new Hardpoint { transform = t, part = part, bayDoors = doors ?? new BayDoor[0], doorOpenDuration = doorTime, BuiltInWeapons = builtIn ?? new Weapon[0], BuiltInTurrets = new Turret[0] };
                S(h, "pylonOptions", Array.CreateInstance(Elem(Fld(typeof(Hardpoint), "pylonOptions")), 0));
                return h;
            }
            Set("76mm Cannon", new[] { ammoCannon }, HP(cannonMount.transform, nose, new Weapon[] { gun76 }));
            Set("20mm Cannons", new[] { ammo20 }, HP(gL.transform, cockpit, new Weapon[] { gL }), HP(gR.transform, cockpit, new Weapon[] { gR }));

            // bomb bay: two doors (EW1 BayDoor values, our hinges); door axes from the contract
            var bay = Find("hp_bombbay");
            var doorAudio = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), bay.gameObject);
            doorAudio.clip = null; doorAudio.loop = false; doorAudio.playOnAwake = false; doorAudio.volume = 0.8f;
            var dmap = new Dictionary<string, (Vector3 axis, float open)>();
            foreach (var d in JList("doors")) dmap[(string)d["name"]] = (J3(d["axis_unity"]), (float)d["open_unity"]);
            var bayDoors = new List<BayDoor>();
            foreach (var (dn, fa, fo) in new[] { ("bomb_door_L", new Vector3(-0.0009f, -0.0021f, 1.0f), -92f), ("bomb_door_R", new Vector3(0.0009f, -0.0021f, 1.0f), 92f) })
            {
                var (axis, open) = dmap.TryGetValue(dn, out var v) ? v : (fa, fo);
                var hb = DoorHinge(Find(dn), axis.normalized, open, false);
                var bd = CloneComp(TplComp<BayDoor>("EW1:weapon_door_hinge_L"), hb.gameObject);
                S(bd, "hingeAngle", open); S(bd, "openSpeed", 1.2f); S(bd, "closeSpeed", 0.8f); S(bd, "doorAudioSource", doorAudio);
                bayDoors.Add(bd);
            }
            // Spec bay loads. One centre hardpoint for the single-mount loads, two side-by-side racks (x +-0.33) for the
            // paired ones; the two sets preclude each other (stock pattern: Darkreach "Inner Weapon Bays (Combined/Front/Rear)").
            var bayCentre = new List<WeaponMount> { Mount("bomb_500_internalx2"), Mount("bomb_125_internalx6") };
            if (NuclearOptions) bayCentre.Add(Mount("nuclearBomb1_internal"));
            var sBay = Set("Bomb Bay", bayCentre, HP(bay, parts["GA25X"], null, bayDoors.ToArray(), 1.5f));
            var sRacks = Set("Bomb Bay Racks", new[] { Mount("bomb_250_internalx2"), Mount("bomb_250_glide_internalx2"), Mount("bomb_glide1_quad_internal") },
                HP(Find("hp_bay_L"), parts["GA25X"], null, bayDoors.ToArray(), 1.5f), HP(Find("hp_bay_R"), parts["GA25X"], null, bayDoors.ToArray(), 1.5f));
            sBay.precludingHardpointSets.Add((byte)sets.IndexOf(sRacks)); sRacks.precludingHardpointSets.Add((byte)sets.IndexOf(sBay));
            // wing pylons (visual pass, user decision): root |x| 1.55 (wing_inner), inner 4.10, mid 4.95, outer 5.80 (wing_outer); clearance proof
            // blender/ga25x/check_stores_ga25x.py. Inner/outer keep set indices 4/5; root/mid are appended after the laser (indices 8/9).
            Set("Inner Pylons", new[] { Mount("AGM_heavy_single"), Mount("AGM1_triple"), Mount("Rocket2_4Podx3"), Mount("bomb_250_glide_single") },
                HP(Find("hp_inner_L"), parts["wing_outer_L"]), HP(Find("hp_inner_R"), parts["wing_outer_R"]));
            Set("Outer Pylons", new[] { Mount("AGM1_triple"), Mount("Rocket2_4Pod"), Mount("AAM1_single") },
                HP(Find("hp_outer_L"), parts["wing_outer_L"]), HP(Find("hp_outer_R"), parts["wing_outer_R"]));

            // tail hook (carrier landing): WeaponMount.tailHook = true is what WeaponManager.HasTailHook() reads
            var hookT = Find("tailhook");
            if (OwnTailHookMount)
            {
                hookMount = Object.Instantiate(Mount("TailHook_Multirole1")); hookMount.name = "GA25X_tailhook";
                hookMount.jsonKey = "GA25X_tailhook"; hookMount.mountName = "Tail Hook"; hookMount.tailHook = true;
                hookMount.prefab = null;   // set in SaveEverything (the prefab references meshes from the bank saved there)
                AssetDatabase.CreateAsset(hookMount, Folder + "/GA25X_tailhook.asset");
                hookGO = BuildTailHookObject(hookT);
            }
            else
            {
                hookMount = Mount("TailHook_Multirole1");
                Object.DestroyImmediate(hookT.gameObject);
            }
            Set("Tail Hook", new[] { hookMount }, HP(Find("hp_tailhook"), parts["fus_tail"]));

            // dorsal 120 kW laser turret (built-in; anti-missile)
            if (LaserTurret && contract != null)
            {
                BuildLaserTurret();
                if (laserTurret != null)
                {
                    laserAmmo = Object.Instantiate(tAmmo); laserAmmo.name = "GA25X_laser";
                    laserAmmo.prefab = ammoPrefab; laserAmmo.jsonKey = "GA25X_laser"; laserAmmo.info = laserInfo; laserAmmo.mountName = "120kW Laser Turret";
                    laserAmmo.ammo = 1; laserAmmo.GunAmmo = false; laserAmmo.mass = 0f;
                    AssetDatabase.CreateAsset(laserAmmo, Folder + "/GA25X_laser.asset");
                    var lt = laserTurret.Value;
                    var h = LaserAsMountPrefab ? HP(TryFind((string)contract["laser_turret"]["muzzle"]["name"]), lt.part) : HP(lt.mount, lt.part, new Weapon[] { lt.laser });
                    h.BuiltInTurrets = new[] { lt.turret };
                    Set("Belly Laser", new[] { laserAmmo }, h);
                }
            }
            if (FourPylonsPerWing)
            {   // appended AFTER the 0.1.0 sets so saved loadouts (index = set) stay valid; mid = single stores only (neighbour clearance)
                Set("Root Pylons", new[] { Mount("AGM_heavy_single"), Mount("AGM1_triple"), Mount("Rocket2_4Podx3"), Mount("Rocket2_4Pod"), Mount("AAM1_single"), Mount("bomb_250_glide_single") },
                    HP(Find("hp_root_L"), parts["wing_inner_L"]), HP(Find("hp_root_R"), parts["wing_inner_R"]));
                Set("Mid Pylons", new[] { Mount("AGM_heavy_single"), Mount("Rocket2_4Pod"), Mount("AAM1_single"), Mount("bomb_250_glide_single") },
                    HP(Find("hp_mid_L"), parts["wing_outer_L"]), HP(Find("hp_mid_R"), parts["wing_outer_R"]));
            }

            var all = sets.SelectMany(x => x.hardpoints).Distinct().OrderByDescending(h => h.transform.position.x).ThenByDescending(h => h.transform.position.z).ToList();
            for (int i = 0; i < all.Count; i++) all[i].HardpointIndex = i;
            weaponManagerSetCount = sets.Count;
            weaponManager.hardpointSets = sets.ToArray();
            S(weaponManager, "aircraft", aircraft);
            L($"hardpoint sets: {string.Join(" | ", sets.Select(x => $"{x.name} ({x.hardpoints.Count} hp, {x.weaponOptions.Count - 1} options, precludes [{string.Join(",", x.precludingHardpointSets)}])"))}");
            return new List<Gun> { gun76, gL, gR };
        }

        // Own tail-hook mount: root TailHook (stock TailHook_Multirole1 values) / hinge (identity) / hook (localEulerAngles.x driven)
        // / our hook mesh (child, -8.5 deg so that hook angle 0 = straight aft) / hookEnd at (0, 0, -L) / castPoint (stock layout).
        // Angles: Unity +x rotation lifts an aft-pointing hook tip; stowed +8.5 (flush), deployed from the contract (tip 0.15 m
        // below the deck in level attitude).
        static GameObject BuildTailHookObject(Transform hookT)
        {
            var th = contract?["tailhook"];
            float len = th != null ? (float)th["length"] : 2.3f, stow = th != null ? (float)th["stowed_up_deg"] : 8.5f;
            var pv = hookT.position;
            float ground = -2.588f;
            float dep = -Mathf.Asin(Mathf.Clamp01((pv.y - ground + 0.15f) / len)) * Mathf.Rad2Deg;
            var root = new GameObject("GA25X_tailhook_mount");
            var hinge = new GameObject("hinge"); hinge.transform.SetParent(root.transform, false);
            var hook = new GameObject("hook"); hook.transform.SetParent(hinge.transform, false);
            var mesh = new GameObject("hook_mesh"); mesh.transform.SetParent(hook.transform, false);
            mesh.transform.localRotation = Quaternion.Euler(-stow, 0, 0);
            mesh.AddComponent<MeshFilter>().sharedMesh = hookT.GetComponent<MeshFilter>().sharedMesh;
            mesh.AddComponent<MeshRenderer>().sharedMaterials = hookT.GetComponent<MeshRenderer>().sharedMaterials;
            var end = new GameObject("hookEnd"); end.transform.SetParent(hook.transform, false); end.transform.localPosition = new Vector3(0, 0, -len);
            var cast = new GameObject("castPoint"); cast.transform.SetParent(end.transform, false);
            cast.transform.localPosition = new Vector3(0, 0, 0.887f * len); cast.transform.localRotation = Quaternion.Euler(180f, 0, 0);
            var t = root.AddComponent<TailHook>();
            EditorUtility.CopySerialized(TplComp<TailHook>("TailHook_Multirole1:TailHook_Multirole1"), t);
            Remap(t);
            S(t, "hinge", hinge.transform); S(t, "hook", hook.transform); S(t, "castPoint", cast.transform); t.hookEnd = end.transform;
            S(t, "stowedAngle", stow); S(t, "deployedAngle", dep);
            hook.transform.localEulerAngles = new Vector3(stow, 0, 0);
            Object.DestroyImmediate(hookT.gameObject);   // the airframe keeps only the hardpoint; the hook comes with the mount
            // the hook mesh was a paint renderer of fus_tail: drop the destroyed entry (in game 0.1.0 it made UnitPart.SetLivery throw an NRE)
            int dropped = 0;
            foreach (var pp in parts.Values) { var lst = (List<Renderer>)G(G(pp, "damageMaterial"), "renderers"); dropped += lst.RemoveAll(r => r == null); }
            L($"tail hook: removed {dropped} destroyed renderer(s) from part damage/livery lists");
            L($"tail hook mount: length {len:F2} m, pivot y {pv.y:F3}, stowed {stow} deg, deployed {dep:F1} deg (end {(pv.y - len * Mathf.Sin(-dep * Mathf.Deg2Rad)):F3} vs ground {ground})");
            return root;
        }

        static WeaponMount Mount(string n) => Asset<WeaponMount>($"MonoBehaviour/{n}_PLACEHOLDER.asset");

        static ParticleSystem[] CopyMuzzleParticles(Gun template, Transform muzzle)
        {
            var src = (ParticleSystem[])G(template, "muzzleParticles") ?? new ParticleSystem[0];
            return src.Where(p => p != null).Select(p => CopyParticle(p, muzzle, muzzle.position, muzzle.name + "_" + p.name)).Select(p => { p.transform.rotation = muzzle.rotation; return p; }).ToArray();
        }

        // ------------------------------------------------------------------ cockpit, crew, canopy
        // Model contract (model worker): assets/model_v2/ga25x_v2_contract.json - object names, pivots, axes, limits.
        static Newtonsoft.Json.Linq.JObject contract;
        static Newtonsoft.Json.Linq.JObject LoadContract()
        {
            var p = Path.Combine(Path.GetDirectoryName(RepoModel), "ga25x_contract.json");
            if (!File.Exists(p)) { L("WARN no model contract: crew/turrets/hatches/gauges/MFDs that need new geometry are skipped"); return null; }
            var c = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(p));
            L($"model contract {p} generated {(string)c["meta"]?["generated"]}");
            return c;
        }
        static Vector3 J3(Newtonsoft.Json.Linq.JToken t) => new Vector3((float)t[0], (float)t[1], (float)t[2]);
        static IEnumerable<Newtonsoft.Json.Linq.JToken> JList(string a, string b = null)
        {
            if (contract == null) return new Newtonsoft.Json.Linq.JToken[0];
            var t = b == null ? contract[a] : contract[a]?[b];
            return t is Newtonsoft.Json.Linq.JArray arr ? arr : (IEnumerable<Newtonsoft.Json.Linq.JToken>)new Newtonsoft.Json.Linq.JToken[0];
        }
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

        // Stock input signs (decompiled): ControlsFilter.cs:241 targetPitchAngVel = pitch * gLimit * g / v, compared with
        // localAngularVelocity.x, and a positive Unity rotation about +X turns +Z towards -Y (nose DOWN), so pitch > 0 =
        // PUSH; the CI-22 stick (Cockpit.Joystick, localEulerAngles.x = pitch * range) has range +12 = stick top forward on
        // push. The model contract assumed pitch > 0 = pull (column pitchRange -12); we use +|range|. Live probe settles it.
        const float ColumnPitchSign = +1f;
        static readonly List<string> cockpitAnimLog = new List<string>();

        static Transform helmetCam;
        static void Cockpit(List<LandingGear> gears)
        {
            var cp = parts["fus_cockpit"];
            var eye = Find("cockpit_eye");

            // ---- crew: pilot + weapons officer (contract stations)
            crew.Clear();
            var stations = TwoCrew ? JList("crew", "stations").ToList() : new List<Newtonsoft.Json.Linq.JToken>();
            if (stations.Count == 0)
                crew.Add(MakeCrewMember(new CrewSpec { role = "pilot", part = "fus_cockpit", eye = eye, exit = Pilot.ExitDirection.Left, hatch = null }, 0));
            else
            {
                int i = 0;
                foreach (var st in stations)
                {
                    var e = TryFind((string)st["eye"]["name"]);
                    if (e == null) { L($"WARN crew {(string)st["role"]}: eye missing, skipped"); continue; }
                    var exit = e.position.x > 0.05f ? Pilot.ExitDirection.Right : Pilot.ExitDirection.Left;
                    var es = st["ejection_seat"] as Newtonsoft.Json.Linq.JObject;   // 0.3.0 own seat object; 0.3.1 kitbash: none (stock seat on the figure)
                    var seatName = es != null ? (string)es["name"] : (st["seat"] != null && st["seat"].Type == Newtonsoft.Json.Linq.JTokenType.String ? (string)st["seat"] : null);
                    crew.Add(MakeCrewMember(new CrewSpec { role = (string)st["role"], part = (string)st["part"], eye = e, exit = exit, hatch = (string)st["exit_hatch"], seat = seatName }, i));
                    i++;
                }
            }
            L($"pilot eye {helmetCam.position.ToString("F3")} vs cockpit_eye {eye.position.ToString("F3")}");

            // ---- bail-out hatches (stock Canopy), from the contract
            var canopies = new List<Canopy>();
            if (TwoCrew)
                foreach (var h in JList("hatches", "hatches"))
                {
                    var hatch = TryFind((string)h["hatch"]["name"]); var hinge = TryFind((string)h["hinge"]["name"]);
                    var pp = (string)h["parent_part"];
                    if (hatch == null || hinge == null || !parts.ContainsKey(pp)) { L($"WARN hatch {(string)h["hatch"]["name"]} missing, skipped"); continue; }
                    var glass = hatch.GetComponent<MeshRenderer>() != null && hatch.GetComponent<MeshRenderer>().sharedMaterials.Contains(mats["glass"]) ? new Renderer[] { hatch.GetComponent<MeshRenderer>() } : new Renderer[0];
                    canopies.Add(MakeHatchFromContract(hatch, hinge, (float)h["hingeAngle"], parts[pp], glass));
                }
            S(aircraft, "canopies", canopies.ToArray());

            // ---- 0.3.1 kitbash: stock SFB-81 stick / throttle meshes on the stick_L/R + cockpit_throttle empties (stock pivots, identity frames)
            if (StockCockpitKit)
                foreach (var o in JList("controls", "sticks").Concat(JList("controls", "levers")))
                {
                    var t = TryFind((string)o["name"]); var sm = (string)o["stock_mesh"];
                    if (t == null || sm == null) continue;
                    var mf = t.GetComponent<MeshFilter>(); if (mf == null) mf = t.gameObject.AddComponent<MeshFilter>();
                    mf.sharedMesh = Asset<Mesh>("Mesh/" + sm + "_PLACEHOLDER.asset");
                    var mr = t.GetComponent<MeshRenderer>(); if (mr == null) mr = t.gameObject.AddComponent<MeshRenderer>();
                    mr.sharedMaterials = ((Newtonsoft.Json.Linq.JArray)o["stock_materials"]).Select(x => Asset<Material>("Material/" + (string)x + "_PLACEHOLDER.mat")).ToArray();
                    mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    L($"stock part {t.name}: {sm} [{string.Join(", ", mr.sharedMaterials.Select(m => m.name))}] at {t.position.ToString("F3")} rot {t.rotation.eulerAngles.ToString("F1")} in {t.parent.name}");
                }

            // ---- cockpit-only copies on the Cockpit layer (3); exterior originals hidden in cockpit view (stock pattern)
            var cockpitR = new List<Renderer>(); var exteriorR = new List<Renderer>();
            var copyNames = new List<string> { "cockpit_interior", "cockpit_gauges", "cockpit_seat_L", "cockpit_seat_R", "stick_L", "stick_R",
                "cockpit_rudder_pedals_L", "cockpit_rudder_pedals_R", "canopy_frame", "fus_cockpit", "fus_forward", "gunsight_pilot", "gunsight_combiner",
                "mfd_center", "mfd_left", "mfd_right", "mfd_wso", "canopy_jettison_L", "canopy_jettison_R", "quadrant_throttle_L", "quadrant_throttle_R", "cockpit_throttle",
                "cockpit_throttle_arm" };   // 0.3.2: our throttle stalk (child of cockpit_throttle, rotates with it)
            copyNames.AddRange(new[] { "gauge_isis_att_card", "gauge_isis_hdg_card", "gauge_isis_tq_L_needle", "gauge_isis_tq_R_needle", "gauge_isis_fuel_bar" });   // 1.8.4 (offline C): ISIS movers driven by B25H.Instruments
            if (CockpitHideCanopyGlass) copyNames.Add("canopy_glass");
            foreach (var n in copyNames.Distinct())
            {
                var orig = TryFind(n);
                if (orig == null || orig.GetComponent<MeshRenderer>() == null) continue;
                var src = orig.GetComponent<MeshRenderer>();
                if (src.sharedMaterials.All(m => m == mats["glass"])) { if (CockpitHideCanopyGlass) exteriorR.Add(src); continue; }
                var copy = NewGO(n + "_int", orig, orig.position, orig.rotation, 3);
                copy.AddComponent<MeshFilter>().sharedMesh = orig.GetComponent<MeshFilter>().sharedMesh;
                var cr = copy.AddComponent<MeshRenderer>();
                cr.sharedMaterials = src.sharedMaterials.Select(m => m == mats["glass"] ? mats["glass_int"] : m).ToArray();
                cr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                cr.enabled = false;
                cockpitR.Add(cr); exteriorR.Add(src);
                if (src.sharedMaterials[0] == mats["paint"])
                {
                    var owner = parts.Values.First(p => PartRenderers(p.gameObject).Contains(src));
                    ((List<Renderer>)G(G(owner, "damageMaterial"), "renderers")).Add(cr);
                }
            }
            S(aircraft, "cockpitRenderers", cockpitR.ToArray());
            S(aircraft, "exteriorRenderers", exteriorR.ToArray());

            // ---- screens: mfd_center = tac screen (Cockpit.tacScreenRender + TargetCam.targetScreenRenderer, CI-22 pattern);
            // mfd_left + mfd_wso = the tac screen again; mfd_right (weapons officer main) = target-camera feed (targetCamDisplay)
            Renderer tacR = null;
            var tacMat = Asset<Material>("Material/tacScreenDisplay_PLACEHOLDER.mat");
            var camMat = Asset<Material>("Material/targetCamDisplay_PLACEHOLDER.mat");
            foreach (var mj in JList("mfds"))
            {
                var n = (string)mj["name"]; var t = TryFind(n); if (t == null || !MFDScreens) continue;
                bool tac = (string)mj["role"] == "tac" || (WsoScreenTacPage && n == "mfd_right");
                bool aux = TouchscreenOff && (n == "mfd_left" || n == "mfd_wso");   // 0.3.0: small aux panes = dark glass (a 0.12 m map is unreadable)
                if (aux) { foreach (var r in t.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.transform == t || r.name == n + "_int")) { r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.sharedMaterials = Enumerable.Repeat(mats["touch_off"], r.sharedMaterials.Length).ToArray(); } continue; }
                foreach (var r in t.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.transform == t || r.name == n + "_int"))
                {
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    if (tac && TacScreenPanels) { var mf = r.GetComponent<MeshFilter>(); mf.sharedMesh = TacScreenMesh(mf.sharedMesh, n + "_tac"); r.sharedMaterials = new[] { tacMat, TouchscreenOff ? mats["touch_off"] : mats["screen"] }; }
                    else r.sharedMaterials = Enumerable.Repeat(tac ? tacMat : camMat, r.sharedMaterials.Length).ToArray();
                }
                if (n == "mfd_center") tacR = t.GetComponent<MeshRenderer>();
            }
            if (tacR == null)
            {
                var screen = NewGO("screen_dummy", cp.transform, Find("cockpit_gauges").position + new Vector3(0, -0.2f, -0.05f), Quaternion.identity, 3);
                screen.AddComponent<MeshFilter>().sharedMesh = QuadMesh("screen_dummy", 0.01f, 0.01f);
                var sr = screen.AddComponent<MeshRenderer>(); sr.sharedMaterial = mats["screen"]; sr.enabled = false;
                tacR = sr; L("WARN screens: no mfd_center, hidden dummy screen");
            }
            else L("screens: " + string.Join(", ", JList("mfds").Select(m => $"{(string)m["name"]}={(string)m["role"]}")));

            var interior = Find("cockpit_interior").gameObject;
            var ck = CloneComp(TplComp<global::Cockpit>("COIN:cockpit_F_interior"), interior);
            if (CockpitLights)
            {
                // OA-27 / MC-260 pattern (Aryx cockpits: CockpitLighting_01/02 spot lights under the cockpit object); ours: one over each
                // crew station, aimed down-forward at the panel, Cockpit layer only, no shadows
                foreach (var (nm, x) in new[] { ("cockpit_light_L", -0.36f), ("cockpit_light_R", 0.36f) })
                {
                    var lg = NewGO(nm, interior.transform, interior.transform.TransformPoint(new Vector3(x, 0.80f, 0.55f)), interior.transform.rotation * Quaternion.Euler(35f, 0f, 0f), 3);
                    var li = lg.AddComponent<Light>(); li.type = LightType.Spot; li.range = 2.0f; li.spotAngle = 95f; li.intensity = 0.6f;
                    li.color = new Color(0.85f, 0.92f, 1f); li.shadows = LightShadows.None; li.cullingMask = 1 << 3;
                }
                L("cockpit lights: 2 spot lights (CockpitLights flag)");
            }
            S(ck, "tacScreenRender", tacR); S(ck, "aircraft", aircraft);
            S(ck, "engineSources", new[] { parts["engine_L"].gameObject, parts["engine_R"].gameObject });
            SetSeq(ck, "joysticks", new object[0]);
            SetSeq(ck, "throttles", new object[0]);
            if (CockpitAnimators) CockpitAnimation(ck, cp);

            // target camera at the chin EO/IR ball, rear view from the tail sensors; laser designator (spec: 4 targets)
            var nose = parts["fus_nose"];
            var tcp = Find("targetcam_point"); var mws = Find("mws_tail");
            var tcF = NewGO("targetCamForward", nose.transform, tcp.position, Quaternion.identity, 0);
            var tcR = NewGO("targetCamRear", parts["fus_tail"].transform, mws.position, Quaternion.LookRotation(Vector3.back), 0);
            var tcL = NewGO("landingCamPoint", nose.transform, tcp.position + new Vector3(0, -0.1f, 0), Quaternion.LookRotation(new Vector3(0, -0.3f, 1f)), 0);
            var tc = CloneComp(TplComp<TargetCam>("COIN:nose"), nose.gameObject);
            S(tc, "currentMount", tcF.transform); S(tc, "camMountForward", tcF.transform); S(tc, "camMountRear", tcR.transform); S(tc, "camMountLanding", tcL.transform);
            S(tc, "attachedPart", nose); S(tc, "targetScreenRenderer", tacR);
            var ld = CloneComp(TplComp<LaserDesignator>("COIN:nose"), nose.gameObject);
            S(ld, "unitPart", nose); S(ld, "aircraft", aircraft); S(ld, "maxTargets", LaserDesignatorTargets);

            aircraft.cockpitViewPoint = helmetCam;
            aircraft.pilots = crew.ToArray();
            aircraft.targetCam = tc;
            aircraft.weaponManager = weaponManager;
            aircraft.cockpit = cp;
            S(aircraft, "controlsFilter", controlsFilter);
            S(aircraft, "groundEquipment", new GameObject[0]);
        }

        // Hatch per contract: hatch_* rests identity under hatch_*_hinge (local +X = hinge axis). Canopy.CanopyHinge on the
        // hatch (absolute localEulerAngles = right * hingeAngle * open). For the jettison push (Canopy.FixedUpdate adds
        // ejectionForce along ejectionTransform.up/forward) an 'eject' frame whose +Y points out of the fuselage is placed
        // above the hinge and used as Canopy.ejectionTransform (it gets the Rigidbody and carries hinge + hatch away).
        static Canopy MakeHatchFromContract(Transform hatch, Transform hinge, float hingeAngle, AeroPart part, Renderer[] glass)
        {
            var mf = hatch.GetComponent<MeshFilter>();
            var centre = mf != null && mf.sharedMesh != null ? hatch.TransformPoint(mf.sharedMesh.bounds.center) : hatch.position;
            var pc = part.GetComponent<MeshCollider>() != null ? part.transform.TransformPoint(part.GetComponent<MeshCollider>().sharedMesh.bounds.center) : part.transform.position;
            var outward = centre - pc; outward.z = 0f; if (outward.sqrMagnitude < 1e-4f) outward = Vector3.up; outward.Normalize();
            var ej = NewGO(hatch.name + "_eject", hinge.parent, hinge.position, Quaternion.LookRotation(Vector3.ProjectOnPlane(Vector3.forward, outward).normalized, outward));
            hinge.SetParent(ej.transform, true);
            var box = hatch.gameObject.AddComponent<BoxCollider>();
            if (mf != null && mf.sharedMesh != null) { box.center = mf.sharedMesh.bounds.center; box.size = Vector3.Max(mf.sharedMesh.bounds.size, Vector3.one * 0.04f); }
            box.enabled = false;
            var drv = DrivenFrame(hatch);
            var cn = CloneComp(TplComp<Canopy>("COIN:canopyFrame_F"), hatch.gameObject);
            bool jett = EjectionSeats && hatch.name.StartsWith("canopy_jettison");   // 0.3.0 canopy panels: stock COIN canopy values
            cn.ejectionTransform = ej.transform; cn.attachedPart = part; cn.mass = jett ? 50f : 20f; cn.ejectionCollider = box;
            S(cn, "ejectionForce", new Vector3(0f, jett ? 4000f : 800f, 0f)); // hatches: 800 N for fireTime 0.2 s on 20 kg = ~8 m/s out of the fuselage; canopies (COIN) 4000 N on 50 kg = ~16 m/s
            S(cn, "forcePosition", jett ? new Vector3(0f, 0f, 0.2f) : Vector3.zero);
            var h = NewElem(cn, "canopyHinges"); S(h, "transform", drv); S(h, "hingeAngle", hingeAngle);
            SetSeq(cn, "canopyHinges", new[] { h });
            S(cn, "fireTime", 0.2f); S(cn, "openSpeed", jett ? 1f : 0.6f);
            S(cn, "glassRenderers", glass);
            L($"hatch {hatch.name}: part {part.name}, hinge {hinge.position.ToString("F3")} axis {hinge.right.ToString("F2")} angle {hingeAngle}, eject push along {outward.ToString("F2")}, glass {glass.Length}");
            return cn;
        }

        // Cockpit animation with stock drivers only: side sticks = Cockpit.Joystick (CI-22 stick: localEulerAngles = (pitch*range,
        // 0, -roll*range)); pedals = visual ControlSurface (yaw); throttle levers = Cockpit.Throttle (rotation).
        static void CockpitAnimation(global::Cockpit ck, AeroPart cp)
        {
            cockpitAnimLog.Clear();
            var sticks = new List<object>();
            foreach (var o in JList("controls", "sticks"))
            {
                var t = TryFind((string)o["name"]); if (t == null) continue;
                var js = NewElem(ck, "joysticks"); S(js, "transform", DrivenFrame(t)); S(js, "range", (float)o["drive"]["range"]);
                sticks.Add(js); cockpitAnimLog.Add($"{t.name}: Cockpit.Joystick range {(float)o["drive"]["range"]}");
            }
            SetSeq(ck, "joysticks", sticks);
            var tplCS = TplComp<ControlSurface>("CAS1:elevator_L");
            foreach (var o in JList("controls", "pedals"))
            {
                var t = TryFind((string)o["name"]); if (t == null) continue;
                var cs = t.gameObject.AddComponent<ControlSurface>();
                EditorUtility.CopySerialized(tplCS, cs); Remap(cs);
                S(cs, "pitchRange", 0f); S(cs, "rollRange", 0f); S(cs, "yawRange", (float)o["drive"]["value"]); S(cs, "brakeRange", 0f);
                S(cs, "attachedSurface", cp); S(cs, "visibleMesh", t.gameObject); S(cs, "flap", false); S(cs, "servoSpeed", (float)o["drive"]["servoSpeed"]);
                S(cs, "splitDrag", 0f); S(cs, "maxSplit", 0f); S(cs, "yawSplitFactor", 0f); S(cs, "splitUpper", null); S(cs, "splitLower", null); S(cs, "splitSound", null);
                cockpitAnimLog.Add($"{t.name}: ControlSurface.yawRange {(float)o["drive"]["value"]}");
            }
            var throttles = new List<object>();
            foreach (var o in JList("controls", "levers"))
            {
                var t = TryFind((string)o["name"]); if (t == null) continue;
                var th = NewElem(ck, "throttles");
                S(th, "rotation", true); S(th, "motion", false); S(th, "transform", DrivenFrame(t)); S(th, "range", (float)o["drive"]["range"]);
                throttles.Add(th); cockpitAnimLog.Add($"{t.name}: Cockpit.Throttle rotation range {(float)o["drive"]["range"]}");
            }
            SetSeq(ck, "throttles", throttles);
            foreach (var s in cockpitAnimLog) L("cockpit anim " + s);
        }

        // =================================================================== 1.1.0: crew, hatches, turrets, cockpit animation
        // A pivot whose local X is the given world axis (ControlSurface, Canopy hinges and Cockpit throttles all rotate about
        // local X). 'up' is a hint for the pivot's local Y.
        static Quaternion AxisX(Vector3 axisW, Vector3 upHint)
        {
            var x = axisW.normalized;
            var y = Vector3.ProjectOnPlane(upHint, x); if (y.sqrMagnitude < 1e-6f) y = Vector3.ProjectOnPlane(Vector3.up, x); if (y.sqrMagnitude < 1e-6f) y = Vector3.ProjectOnPlane(Vector3.forward, x);
            y.Normalize();
            return Quaternion.LookRotation(Vector3.Cross(x, y), y);
        }

        // Insert a pivot above 'moving' (same parent, at 'pivotPos', local X = axis) and re-parent 'moving' under it.
        static Transform Pivot(Transform moving, Vector3 pivotPos, Vector3 axisW, Vector3 upHint, string name = null)
        {
            var pv = NewGO(name ?? moving.name + "_pivot", moving.parent, pivotPos, AxisX(axisW, upHint), moving.gameObject.layer);
            moving.SetParent(pv.transform, true);
            return pv.transform;
        }

        // --- crew of five (stock multi-crew: Aircraft.pilots[], Pilot.ejectionSeat false = bail-out; Aircraft.EjectionSequence
        // jettisons every Canopy, then spawns one PilotDismounted per live crew member from the last to the first, 1 s apart,
        // placed 2 m beside its UnitPart (PilotDismounted.FindDismountSpot, alternating sides from Pilot.exitDirection).
        class CrewSpec { public string role, part, hatch, seat; public Transform eye; public Pilot.ExitDirection exit; }
        static readonly List<Pilot> crew = new List<Pilot>();

        static Pilot MakeCrewMember(CrewSpec c, int index)
        {
            var src = index == 0 ? TplFind("COIN:pilot") : TplFind("COIN:WSO");
            var fig = (GameObject)Object.Instantiate(src.gameObject);
            fig.SetActive(true); fig.name = index == 0 ? "pilot" : "crew_" + c.role;
            foreach (var t in fig.GetComponentsInChildren<Transform>(true).Where(t => t.name == "EjectionSeat").ToList())
            {
                if (!StockCockpitKit || !EjectionSeats) { Object.DestroyImmediate(t.gameObject); continue; }
                // 0.3.1: keep the figure's stock seat exactly as COIN / SFB-81 (child of the Pilot at (0, 0.0218, -0.041), mesh ejectionSeat,
                // material Seats): it is hidden with the figure when the crew member ejects, and the seat that fires is the same model
                t.GetComponent<MeshFilter>().sharedMesh = Asset<Mesh>("Mesh/ejectionSeat_PLACEHOLDER.asset");
                t.GetComponent<MeshRenderer>().sharedMaterials = new[] { Asset<Material>("Material/Seats_PLACEHOLDER.mat") };
                var sc = t.GetComponent<MeshCollider>();   // COIN: convex, disabled (kept as the stock figure has it)
                if (sc != null) { sc.sharedMesh = Asset<Mesh>("Mesh/ejectionSeat_PLACEHOLDER.asset"); L($"crew {index}: stock EjectionSeat collider convex {sc.convex} enabled {sc.enabled}"); }
                L($"crew {index}: stock EjectionSeat kept at {t.localPosition.ToString("F4")} in the figure");
            }
            var part = parts[c.part];
            fig.transform.SetParent(c.eye.parent, false); // the engineer's eye turns with the dorsal turret
            var cam = fig.GetComponentsInChildren<Transform>(true).First(t => t.name == "helmetCamPoint");
            // face along the eye's forward (contract eye frames; identity = +Z)
            fig.transform.rotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(c.eye.forward, Vector3.up).sqrMagnitude > 1e-4f ? Vector3.ProjectOnPlane(c.eye.forward, Vector3.up) : Vector3.forward, Vector3.up);
            fig.transform.position += c.eye.position - cam.position;
            foreach (var comp in fig.GetComponentsInChildren<Component>(true)) if (comp != null) Remap(comp);
            var pc = fig.GetComponent<Pilot>();
            S(pc, "aircraft", aircraft); S(pc, "unitPart", part); S(pc, "ejectionSeat", EjectionSeats); S(pc, "autoTrimmer", controlsFilter);
            if (EjectionSeats && c.seat != null)
            {   // our cockpit seat takes the place of the stock figure's plain EjectionSeat mesh child (CI-22 pattern): it is hidden with the
                // figure when the crew member ejects (PilotDismounted.Setup: pilots[n].gameObject.SetActive(false)), so no seat stays behind
                var seatT = TryFind(c.seat);
                if (seatT != null) { seatT.SetParent(fig.transform, true); L($"crew {index}: seat {c.seat} re-parented under {fig.name} (leaves with the crew member)"); }
                else L($"WARN crew {index}: seat {c.seat} missing");
            }
            S(pc, "pilotCollider", fig.GetComponent<CapsuleCollider>());
            pc.exitDirection = c.exit;
            L($"crew {index} {c.role}: part {c.part}, eye {c.eye.position.ToString("F3")}, figure eye {cam.position.ToString("F3")}, exit {c.exit}, hatch {c.hatch}");
            if (index == 0) helmetCam = cam;
            return pc;
        }

        static AeroPart OwningPart(Transform t) { for (var x = t; x != null; x = x.parent) { var ap = x.GetComponent<AeroPart>(); if (ap != null) return ap; } return null; }

        // --- dorsal laser turret: stock anti-missile laser pattern of the HLT laser trailer (LaserTrailer1.prefab: Turret on the
        // traverse object with its own TargetDetector, targetAcquisitionMode 1 = assignedTargetDetectors, Laser on the elevation
        // object = Turret.elevationTransform) with the aircraft laser's values (Laser_EW1.prefab: power 120 kW, maxAngle 30,
        // range curve to 15 km, vehicularPowerSupply false = draws from the aircraft PowerSupply). Our own turret meshes; the
        // beam is the stock laserCone mesh + material (referenced, resolved at runtime like the B-25H turret barrel mesh).
        // Turret.FixedUpdate fires only while on target (aim error < 1 deg for lockTime) AND a 200 m linecast from the elevation
        // pivot is clear, so the 7.5 deg minimum elevation (B-25H dorsal safe envelope at this ring) keeps the beam off our airframe.
        static (Turret turret, Laser laser, AeroPart part, Transform mount)? laserTurret;
        static readonly (string name, float az, float el, float half)[] LaserExclusions = new (string, float, float, float)[0];
        static void BuildLaserTurret()
        {
            laserTurret = null;
            var lt = contract["laser_turret"];
            var mount = TryFind((string)lt["mount"]["name"]); var az = TryFind((string)lt["az"]["name"]); var el = TryFind((string)lt["el"]["name"]);
            var mz = TryFind((string)lt["muzzle"]["name"]);
            if (mount == null || az == null || el == null || mz == null) { L("WARN laser turret objects missing, skipped"); return; }
            var part = OwningPart(mount);
            var tLaser = tpl["Laser_EW1"].GetComponent<Laser>();
            laserInfo = Object.Instantiate(tLaser.info); laserInfo.name = "GA25X_laser_info";   // stock values ("120kw Laser", antiMissile 0.2, 15 km)
            AssetDatabase.CreateAsset(laserInfo, Folder + "/GA25X_laser_info.asset");
            Transform lroot = mz;
            if (LaserAsMountPrefab) { laserGO = new GameObject("GA25X_laser_mount") { layer = 14 }; lroot = laserGO.transform; }   // at origin; spawned as a child of the aperture (local identity)
            var laser = CloneComp(tLaser, LaserAsMountPrefab ? laserGO : el.gameObject);
            laser.attachedUnit = LaserAsMountPrefab ? null : aircraft; laser.info = laserInfo;
            if (LaserBeam197) S(laser, "maxAngle", LaserBeamAngle197);   // 1.9.7: beam = bore line (stock 30)
            // beam: stock laserCone mesh/material on our aim transform (= Laser.directionTransform, at the aperture)
            var tBeam = TplFind("Laser_EW1:beam");
            var beam = NewGO("laser_beam", lroot, lroot.position, lroot.rotation);
            beam.transform.localScale = tBeam.localScale;
            beam.AddComponent<MeshFilter>().sharedMesh = tBeam.GetComponent<MeshFilter>().sharedMesh;
            var br = beam.AddComponent<MeshRenderer>(); br.sharedMaterials = tBeam.GetComponent<MeshRenderer>().sharedMaterials; br.enabled = false;
            br.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            S(laser, "beamRenderer", br); S(laser, "directionTransform", lroot);
            var aimPS = TplFind("Laser_EW1:aimTransform").GetComponent<ParticleSystem>();
            var lmps = aimPS != null ? new[] { CopyParticle(aimPS, lroot, lroot.position, "laser_muzzle") } : new ParticleSystem[0];
            S(laser, "muzzleParticles", lmps);
            if (LaserAsMountPrefab)
            {   // the muzzle particle lives in the mount prefab: keep it out of the aircraft's SetGlobalParticles list (a missing entry = NRE in SetGlobalParticles.Start, seen in game) and give the prefab its own
                foreach (var ps in lmps) ourParticles.Remove(ps);
                if (lmps.Length > 0) S(laserGO.AddComponent<SetGlobalParticles>(), "systems", lmps.ToList());
            }
            S(laser, "vehicularPowerSupply", false);
            // turret
            var tTur = tpl["LaserTrailer1"].GetComponentInChildren<Turret>(true);
            var tr = CloneComp(tTur, az.gameObject);
            S(tr, "attachedUnit", aircraft);
            var fMode = Fld(typeof(Turret), "targetAcquisitionMode"); fMode.SetValue(tr, Enum.ToObject(fMode.FieldType, 1)); // assignedTargetDetectors
            var tDet = tTur.GetComponent<TargetDetector>();
            var det = CloneComp(tDet, az.gameObject);
            S(det, "attachedUnit", aircraft); S(det, "scanner", el); S(det, "part", part);
            S(det, "visualRange", 15000f);   // = the laser's reach (stock trailer 6 km)
            SetSeq(tr, "targetDetectors", new[] { det });
            S(tr, "fireControl", null); S(tr, "firesWithoutAiming", false);
            var ws = (WeaponStation)System.Runtime.Serialization.FormatterServices.GetUninitializedObject(typeof(WeaponStation));
            // Turret.Awake reads weaponStations[0].Weapons[0].info (ArgumentOutOfRange in game with an empty list): with the laser in the
            // mount prefab the station starts with a plain base-class Weapon (Fire() does nothing) carrying the laser info; the spawned
            // Laser joins the same station at SpawnMount (WeaponManager.RegisterWeapon matches by WeaponInfo) and WeaponStation.Fire fires both.
            Weapon proxy = null;
            if (LaserAsMountPrefab) { proxy = el.gameObject.AddComponent<Weapon>(); proxy.attachedUnit = aircraft; proxy.info = laserInfo; proxy.Rearmable = false; }
            ws.Weapons = LaserAsMountPrefab ? new List<Weapon> { proxy } : new List<Weapon> { laser }; ws.Turrets = new List<Turret> { tr };
            ws.WeaponInfo = laserInfo;   // Turret.AttachToWeaponManager registers this station; the spawned laser joins it by WeaponInfo (WeaponManager.RegisterWeapon)
            SetSeq(tr, "weaponStations", new[] { ws });
            S(tr, "aimSafetyWeapon", LaserAsMountPrefab ? null : laser);   // null: Turret.GetWeapon() falls back to weaponStations[0].Weapons[0]
            var T = lt["Turret"];
            float emin = (float)T["minElevation"], emax = (float)T["maxElevation"];
            S(tr, "traverseRate", (float)T["traverseRate"]); S(tr, "traverseRange", 999999f);
            S(tr, "elevationRate", (float)T["elevationRate"]); S(tr, "minElevation", emin); S(tr, "maxElevation", emax);
            S(tr, "elevationTransform", el);
            // inclusion cone about the mount's up (dorsal) or down (ventral, minElevation < 0): 0.2.0 hard-coded world-up with 90 - emin + 1
            // (= 181 deg for the belly turret: no limit at all). Ventral: axis -mount.up, half-angle 90 + maxElevation + 1 (-2 -> 89 deg).
            bool ventral = BellyLaser && emin < 0f;
            var coneAxis = ventral ? -mount.up : (BellyLaser ? mount.up : Vector3.up);
            var cg = NewGO(mount.name + "_cone", mount.parent, mount.position, Quaternion.LookRotation(coneAxis, mount.forward));
            float coneAngle = ventral ? 90f + emax + 1f : 90f - emin + 1f;
            var fc = New(typeof(FiringCone)); S(fc, "transform", cg.transform); S(fc, "coneAngle", coneAngle); S(fc, "exclusion", false);
            var cones = new List<object> { fc };
            // exclusion cones: only toward real self-hits found by the Check envelope scan (gear down, bay doors open, hook down).
            // Each entry: (name, aim direction in the mount frame (az deg, el deg), half-angle deg). 0.3.0 scan: none needed (see MODLOG).
            foreach (var (cn, caz, cel, cha) in LaserExclusions)
            {
                var d = mount.rotation * Quaternion.Euler(0, caz, 0) * Quaternion.Euler(-cel, 0, 0) * Vector3.forward;
                var xg = NewGO(mount.name + "_excl_" + cn, mount.parent, mount.position, Quaternion.LookRotation(d, mount.up));
                var xc = New(typeof(FiringCone)); S(xc, "transform", xg.transform); S(xc, "coneAngle", cha); S(xc, "exclusion", true);
                cones.Add(xc);
            }
            SetSeq(tr, "firingCones", cones);
            L($"laser cones: inclusion axis {coneAxis.ToString("F2")} half-angle {coneAngle}; exclusions {LaserExclusions.Length} {string.Join(" ", LaserExclusions.Select(x => $"{x.name}({x.az},{x.el},{x.half})"))}");
            S(tr, "criticalParts", new UnitPart[] { part });
            S(tr, "manual", false); S(tr, "stowed", false); S(tr, "onlyDefensive", LaserOnlyDefensive);
            laserTurret = (tr, laser, part, mount);
            L($"laser turret: part {part.name}, el {emin}..{emax}, traverse rate {(float)T["traverseRate"]}, power {G(laser, "power")} kW, maxAngle {G(laser, "maxAngle")}, onlyDefensive {LaserOnlyDefensive}, detector range 15 km");
        }

        // ------------------------------------------------------------------ root systems
        static void RootSystems(List<LandingGear> gears)
        {
            var coin = tpl["COIN"]; var ew1 = tpl["EW1"];
            // EO/IR optics (spec: x3, 10 km) = the aircraft EOTS (TargetDetector), scanner at the chin ball
            var detector = CloneComp(coin.GetComponent<TargetDetector>(), root);
            S(detector, "attachedUnit", aircraft); S(detector, "scanner", Find("chin_turret"));
            S(detector, "visualRange", OpticsRange); S(detector, "magnification", OpticsZoom);
            aircraft.EOTS = detector;
            if (RadarInSkin)
            {   // EW-25 radar values, 40 km (spec); conformal array in the nose skin
                var radar = CloneComp(ew1.GetComponent<Radar>(), root);
                S(radar, "attachedUnit", aircraft); S(radar, "scanner", Find("radar_antenna"));
                var so = new SerializedObject(radar); var mr = so.FindProperty("RadarParameters.maxRange"); if (mr != null) { mr.floatValue = RadarRange; so.ApplyModifiedPropertiesWithoutUndo(); }
                try { S(aircraft, "radar", radar); } catch (Exception e) { L("note: no Unit.radar field to set (" + e.Message + ")"); }
            }
            // power: capacitor charged by the two motor-generators (PowerSupply: charge += chargePerRPM * engine rpm per second)
            var cap = CloneComp(TplAudio("COIN:COIN", "capacitor"), root);
            var power = CloneComp(ew1.GetComponent<PowerSupply>(), root);
            S(power, "powerSources", new[] { parts["engine_L"].gameObject, parts["engine_R"].gameObject });
            S(power, "maxCharge", PowerMaxCharge); S(power, "chargePerRPM", PowerChargePerRPM); S(power, "maxPower", LaserPowerKW + JammerPowerKW);
            S(power, "source", cap); S(power, "aircraft", aircraft);
            S(aircraft, "powerSupply", power);
            if (RadarJammerEW)
            {
                var jam = CloneComp(ew1.GetComponent<RadarJammer>(), root);   // powerUsage 50, jammingIntensity 8, capacitance 100 (EW-25)
                S(jam, "aircraft", aircraft); S(jam, "powerUsage", JammerPowerKW);
            }
            CloneComp(coin.GetComponent<NuclearOption.NetworkTransforms.AircraftNetworkTransform>(), root);

            // fuel 3,800 kg in the wings
            // 1.8.3: as the B-25H (the reference pair): AB-4 (FastBomber1) wing-tank settings, inner <-> outer linked; same parts, same capacities
            var tplTank = BomberFuelTanks183 ? TplComp<FuelTank>("FastBomber1:wingroot_L") : coin.GetComponent<FuelTank>();
            var tanks = new Dictionary<string, FuelTank>();
            foreach (var (p, kg) in new[] { ("wing_inner_L", 1200f), ("wing_inner_R", 1200f), ("wing_outer_L", 700f), ("wing_outer_R", 700f) })
            {
                var ft = CloneComp(tplTank, parts[p].gameObject);
                S(ft, "fuelCapacity", kg); S(ft, "fuelMass", kg); S(ft, "part", parts[p]); SetSeq(ft, "connectedTanks", new object[0]);
                tanks[p] = ft;
            }
            if (BomberFuelTanks183)
                foreach (var sd in new[] { "L", "R" })
                {
                    S(tanks["wing_inner_" + sd], "connectedTanks", new[] { tanks["wing_outer_" + sd] });
                    S(tanks["wing_outer_" + sd], "connectedTanks", new[] { tanks["wing_inner_" + sd] });
                }
            L($"fuel tanks ({(BomberFuelTanks183 ? "AB-4 wing-tank settings, linked" : "CI-22")}): " + string.Join(", ", tanks.Select(kv => $"{kv.Key} {G(kv.Value, "fuelCapacity")} kg")));

            var nl = CloneComp(coin.GetComponent<NavLights>(), root);
            var entries = new List<object>();
            void Nav(string name, AeroPart part, Vector3 pos, string litMat, Color col)
            {
                var g = NewGO(name, part.transform, pos, Quaternion.identity);
                g.AddComponent<MeshFilter>().sharedMesh = OctaMesh(name, 0.06f);
                var r = g.AddComponent<MeshRenderer>(); r.sharedMaterial = mats["navlight"];
                var lg = NewGO(name + "_light", g.transform, pos, Quaternion.identity);
                var li = lg.AddComponent<Light>(); li.type = LightType.Point; li.color = col; li.range = 6f; li.intensity = 2f; lg.SetActive(false);
                var e = NewElem(nl, "navLights");
                S(e, "renderer", r); S(e, "objects", new[] { lg }); S(e, "litMaterial", Asset<Material>($"Material/{litMat}_PLACEHOLDER.mat"));
                S(e, "part", part); S(e, "gear", null);
                var fcs = Fld(e.GetType(), "controlState"); fcs.SetValue(e, Enum.ToObject(fcs.FieldType, 1));
                entries.Add(e);
            }
            var tipL = parts["wing_tip_L"]; var tipR = parts["wing_tip_R"];
            Nav("navLight_L", tipL, TipPoint(tipL, -1), "navlight_L", Color.red);
            Nav("navLight_R", tipR, TipPoint(tipR, 1), "navlight_R", Color.green);
            if (FormationLights)
            {   // 0.3.0: green formation / gear-down strips (stock slimelight pattern, research 3): the model's own strip meshes (material
                // light_off), whole-renderer material swap to the stock slimelight_on while the gear is extended (NavLights Auto)
                var slimeOn = Asset<Material>("Material/slimelight_on_PLACEHOLDER.mat");
                int nStrips = 0;
                foreach (var lj in JList("lights", "formation"))
                {
                    var t = TryFind((string)lj["name"]); var r = t != null ? t.GetComponent<MeshRenderer>() : null;
                    if (r == null) { L($"WARN formation light {(string)lj["name"]} missing"); continue; }
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    var part = OwningPart(t);
                    var e = NewElem(nl, "navLights");
                    S(e, "renderer", r); S(e, "objects", new GameObject[0]); S(e, "litMaterial", slimeOn);
                    S(e, "part", part); S(e, "gear", null);
                    var fcs = Fld(e.GetType(), "controlState"); fcs.SetValue(e, Enum.ToObject(fcs.FieldType, 1));
                    entries.Add(e); nStrips++;
                }
                L($"formation lights: {nStrips} slimelight strips (NavLights Auto, litMaterial slimelight_on)");
            }
            if (GearLight1914.Enabled)
            {   // 1.9.14: gear light = a modelled lamp clamped to the nose strut (GearLight1914: lens + stock glow + spot that skips aircraft layers)
                var ng = gears[0];
                var b = GearLight1914.Make(DNS, ng, Find("gear_nose_strut"), root.transform, "nose", 1f, mats["metal_dark"], mats["navlight"], generatedMeshes, 0.040f, 0.16f, false);
                var e1 = NewElem(nl, "navLights"); var e2 = NewElem(nl, "navLights");
                GearLight1914.Entries(e1, e2, b, (UnitPart)G(ng, "attachedPart"), ng, DNS);
                entries.Add(e1); entries.Add(e2);
                L($"gear light: lamp {b.lamp.name} on gear_nose_strut, lens at {b.lensCentre.ToString("F3")}, aim {b.pitchDown:F1} deg down");
            }
            SetSeq(nl, "navLights", entries);
            S(nl, "aircraft", aircraft);

            // countermeasures: 96 IR flares from the waist dispensers and the tail cone (EW-25 FlareEjector values)
            if (KeepFlareEjector)
            {
                var fe = CloneComp(ew1.GetComponent<FlareEjector>(), root);
                S(fe, "ammo", FlareCount);
                var pts = new List<object>();
                foreach (var fj in JList("flares"))
                {
                    var t = TryFind((string)fj["name"]); if (t == null) continue;
                    var part = OwningPart(t);
                    var g = NewGO(t.name + "_ejector", t.parent, t.position, Quaternion.LookRotation(Vector3.ProjectOnPlane(t.up, Vector3.forward).normalized + Vector3.down * 0.2f));
                    var a = CloneComp(TplAudio("COIN:flareEjector_L", "flare"), g);
                    var ep = NewElem(fe, "ejectionPoints");
                    S(ep, "part", part); S(ep, "transform", g.transform); S(ep, "sound", a);
                    pts.Add(ep);
                }
                SetSeq(fe, "ejectionPoints", pts);
                foreach (var f in new[] { "doors", "flareDoors" }) { try { SetSeq(fe, f, new object[0]); } catch { } }
                S(fe, "aircraft", aircraft);
            }

            var sparks = CopyParticle(TplFind("COIN:contactSparks").GetComponent<ParticleSystem>(), root.transform, root.transform.position, "contactSparks");
            S(aircraft, "sparksEmitter", sparks);
            var sgp = root.AddComponent<SetGlobalParticles>();
            S(sgp, "systems", ourParticles.ToList());
            var doppler = new List<AudioSource>();
            foreach (var s in new[] { "L", "R" }) { doppler.Add(parts["engine_" + s].GetComponent<AudioSource>()); doppler.Add(parts["prop_" + s].GetComponent<AudioSource>()); }
            S(aircraft, "dopplerSounds", doppler);
            aircraft.maxRadius = 11f;
            aircraft.obstacleTop = 2.4f;
            AirbrakeComponent1912();
        }

        static Vector3 TipPoint(AeroPart tip, float side)
        {
            var b = WorldBounds(tip.GetComponent<MeshCollider>());
            return new Vector3(side > 0 ? b.max.x - 0.05f : b.min.x + 0.05f, b.center.y, b.center.z + 0.2f);
        }

        static void FlyByWire(LandingGear noseGear)
        {
            var so = new SerializedObject(controlsFilter);
            void F(string p, float v) { var sp = so.FindProperty("flyByWire." + p); if (sp == null) throw new Exception("no flyByWire." + p); sp.floatValue = v; }
            // fly-by-light: g +5.0 (spec), corner 125 m/s, stall 145-190 km/h (40-53 m/s) -> take-off 47 m/s
            // 0.2.0 (fbw.py, the stock law simulated on this airframe): target pitch rate = input * gLimit * g / max(V, 0.75 corner), held by an
            // integrator, so the HUD load (GIndicators: pilot accel + 1 g along up) settles at ~gLimit + 1 in a pull: gLimit 4 = 5 g. Alpha
            // limiter (below corner EAS only): rate x (1 - (alpha - 10) * 0.25) -> zero at 14 deg body, below the clean stall at ~15-16.
            F("gLimitPositive", FBWg5 ? 4.0f : 5.0f); F("cornerSpeed", 125f); F("postStallManeuverSpeed", 0f); F("maxRollSpeed", 90f);
            if (PullOut187F) F("gLimitPositive", 5.0f);   // 1.8.7F: strafing pull-out
            F("takeoffSpeed", StolFlaps ? 38f : 47f); F("pidTransitionSpeed", 110f); F("alphaLimiter", GentleStall ? 10f : 15f);
            if (GentleStall) F("alphaLimiterStrength", 0.25f);
            so.FindProperty("flyByWire.noseGear").objectReferenceValue = noseGear;
            var rt = so.FindProperty("ReverseThrust"); if (rt != null) rt.boolValue = ReverseThrustAI;
            so.ApplyModifiedPropertiesWithoutUndo();
            var ap = parts["fus_cockpit"].GetComponent<AutopilotPlane>();
            var so2 = new SerializedObject(ap);
            var rs = so2.FindProperty("forwardFlightController.referenceAirspeed"); if (rs != null) rs.floatValue = AutopilotCAS1Gains ? 170f : 130f;
            if (AutopilotCAS1Gains)
            {   // stock CAS1 (A-19) forwardFlightController values (AssetRipper placeholder CAS1 prefab)
                void P(string n, Vector3 v) { var sp = so2.FindProperty("forwardFlightController." + n + ".PID"); if (sp == null) throw new Exception("no PID " + n); sp.vector3Value = v; }
                P("pitchFlightPID", new Vector3(0.04f, 0.02f, 0.01f)); P("yawFlightPID", new Vector3(0.05f, 0.01f, 0f)); P("rollFlightPID", new Vector3(0.007f, 0f, 0.002f));
            }
            if (GunshipAITuning) { var pi = so2.FindProperty("preventInvertedFlight"); if (pi != null) pi.boolValue = true; }
            so2.ApplyModifiedPropertiesWithoutUndo();
        }

        // =================================================================== damage diagram + map icon (generated from our model)
        // Stock pattern (CAS1_statusDisplay.prefab, StatusDisplay.cs, PartStatusDisplay.cs): a 300x300 UI prefab parented to
        // FlightHud.statusAnchor; root Image = line-art background (StatusDisplay.aircraftBackground); one Image per part whose
        // GameObject NAME equals the UnitPart's GameObject name (PartStatusDisplay.FindPart); the game sets each part image's
        // green channel/alpha from part hit points (yellow -> red), and a detached part turns (0.7, 0, 0.25). Failure indicators
        // are GameObjects named after IReportDamage failure messages ("LEFT ENGINE FAILURE"...), shown on report.
        // Map icon (UnitDefinition.mapIcon, UnitMapIcon.cs:53): white silhouette on transparent, 256x256, nose up, tinted by IFF.
        const string RepoUI = @"C:\Users\User\Nuclear Option B-25\assets\ui_ga25x";   // no GA-25X UI art yet: diagram + icon are generated from the model
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
            var art = Directory.Exists(RepoUI) && !File.Exists(Path.Combine(RepoUI, "ga25x_status_layout.json")) ? Directory.GetFiles(RepoUI, "*.png").FirstOrDefault(f => { var n = Path.GetFileName(f).ToLowerInvariant(); return n.Contains("diagram") || n.Contains("status") || n.Contains("damage"); }) : null;
            if (art != null)
            {
                var fitted = FitArt(art, 512, u, BIG);
                if (fitted != null) { bgPx = fitted; L($"status background: texture worker art {Path.GetFileName(art)} (bbox-fitted to the model frame)"); }
            }
            else L("status background: generated line art from the model (no assets/ui diagram art)");
            statusBackground = SaveSprite(bgPx, 512, "ga25x_status", false);

            // one filled sprite per part (256, 2x supersampled)
            const int PB = 512;
            for (short k = 0; k < plist.Count; k++)
            {
                var r = new Raster(PB);
                foreach (var (a, b, c) in PartTriangles(plist[k])) r.Tri(a, b, c, k);
                var px = Downsample(i => r.id[i] >= 0, PB, 2);
                statusParts[plist[k].name] = SaveSprite(px, 256, "ga25x_status_" + plist[k].name, true);
                // centre of the part's own silhouette, for failure indicators
                double sx = 0, sy = 0; int cnt = 0;
                for (int i = 0; i < r.id.Length; i++) if (r.id[i] >= 0) { sx += i % PB; sy += i / PB; cnt++; }
                diagramPos[plist[k].name] = cnt > 0 ? new Vector2((float)(sx / cnt / PB - 0.5), (float)(sy / cnt / PB - 0.5)) : Vector2.zero;
            }

            // map icon: filled silhouette, 256 (texture worker's icon when present)
            var icon = Path.Combine(RepoUI, "ga25x_map_icon.png");
            if (File.Exists(icon)) { mapIconSprite = ImportRepoSprite(icon, "ga25x_mapicon"); L("map icon: texture worker art ga25x_map_icon.png"); }
            else { mapIconSprite = SaveSprite(Downsample(i => u.id[i] >= 0, BIG, 4), 256, "ga25x_mapicon", false); L("map icon: generated silhouette from the model"); }
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
        static readonly string[] FailureIndicators = { "LEFT ENGINE FAILURE", "RIGHT ENGINE FAILURE" }; // TurbineEngine.failureMessage (from CAS1)
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
            var inst = new GameObject("GA25X_statusDisplay", typeof(RectTransform)) { layer = 5 };
            var rt = (RectTransform)inst.transform;
            rt.anchorMin = rt.anchorMax = new Vector2(1f, 0f); rt.pivot = new Vector2(1f, -0.05f); rt.sizeDelta = new Vector2(300f, 300f); rt.anchoredPosition = new Vector2(0f, -30.1f);
            var list = new List<PartStatusDisplay>();
            var failures = new List<GameObject>();
            UnityEngine.UI.Image rootImg;
            StatusDisplay sd;
            Vector2 V2(Newtonsoft.Json.Linq.JToken t) => new Vector2((float)t[0], (float)t[1]);
            var layoutPath = Path.Combine(RepoUI, "ga25x_status_layout.json");
            var covered = new HashSet<string>();
            if (File.Exists(layoutPath))
            {
                // texture worker's art + layout (assets/ui/ga25x_status_layout.json): stock-style per-part sprites, mirrored L/R
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
            foreach (var kv in statusParts.Where(k => !covered.Contains(k.Key)).OrderBy(k => k.Key == "GA25X" ? 0 : 1))
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
                var part = "engine_" + (fname.StartsWith("LEFT") ? "L" : "R");
                grt.anchoredPosition = diagramPos.TryGetValue(part, out var dp) ? dp * rt.sizeDelta.x : Vector2.zero;
                Img(g, null, Color.red).preserveAspect = false;
                failures.Add(g);
            }
            SetSeq(sd, "failureIndicators", failures);
            var fnames = string.Join(", ", failures.Select(f => f.name));
            var prefab = PrefabUtility.SaveAsPrefabAsset(inst, Folder + "/GA25X_statusDisplay.prefab");
            Object.DestroyImmediate(inst);
            L($"status display prefab: {list.Count} part images, failure indicators {fnames}");
            return prefab;
        }

        // =================================================================== assets
        static GameObject SaveEverything()
        {
            // mesh bank (one asset, our meshes as sub-assets)
            var bank = Folder + "/Generated/GA25X_meshes.asset";
            AssetDatabase.CreateAsset(generatedMeshes[0], bank);
            foreach (var m in generatedMeshes.Skip(1)) AssetDatabase.AddObjectToAsset(m, bank);

            // airfoils: chart convention measured from AeroJob_Math: alpha = atan2(v.y, v.z) of the part's motion in the
            // liftNormal frame, lift = -cross(v, right) * CL, so nose-up angles are NEGATIVE alpha and lift-up needs
            // NEGATIVE CL. Physical curves below are written nose-up-positive and mirrored (t,v) -> (-t,-v).
            var coinParams = Asset<AircraftParameters>("MonoBehaviour/COINParameters_PLACEHOLDER.asset");
            var drag = coinParams.airfoils[0].dragCoef;
            // GentleStall: keys on the game's chart samples (Airfoil.BuildLiftChart, step 0.04908734 rad) so the peak is not clipped (0.1.0's 1.45 at
            // 0.28 rad charted as 1.38), CLmax 1.52 at 16.9 deg, then a flat top (1.48 / 1.34 / 1.18) instead of 0.1.0's drop to 1.10 at 20 deg.
            var wingCL = GentleStall
                ? new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.95f), (-0.36f, -0.80f), (-0.2945f, -0.95f), (0f, 0.15f), (0.1473f, 0.85f), (0.2945f, 1.52f), (0.3436f, 1.48f), (0.4418f, 1.34f), (0.5400f, 1.18f), (0.785f, 0.95f), (1.571f, 0f), (3.142f, 0f) }
                : new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.95f), (-0.36f, -0.80f), (-0.24f, -0.95f), (0f, 0.15f), (0.15f, 0.85f), (0.28f, 1.45f), (0.35f, 1.10f), (0.5f, 0.90f), (0.785f, 0.95f), (1.571f, 0f), (3.142f, 0f) };
            var wing = new Airfoil { name = "GA25X_NACA23017", liftCoef = Mirror(wingCL), dragCoef = WingDrag() };
            var tail = new Airfoil { name = "GA25X_tail", liftCoef = Mirror(new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.9f), (-0.45f, -0.8f), (-0.3f, -1.1f), (0f, 0f), (0.3f, 1.1f), (0.45f, 0.8f), (0.785f, 0.9f), (1.571f, 0f), (3.142f, 0f) }), dragCoef = new AnimationCurve(drag.keys) };

            if (laserGO != null)
            {
                var lp = PrefabUtility.SaveAsPrefabAsset(laserGO, Folder + "/GA25X_laser_mount.prefab");
                Object.DestroyImmediate(laserGO); laserGO = null;
                laserAmmo.prefab = lp; EditorUtility.SetDirty(laserAmmo);
                L("laser mount prefab saved (Laser + beam, spawned on the turret aperture)");
            }
            // own tail-hook mount prefab (needs the mesh bank saved above)
            if (hookGO != null)
            {
                var hp = PrefabUtility.SaveAsPrefabAsset(hookGO, Folder + "/GA25X_tailhook_mount.prefab");
                Object.DestroyImmediate(hookGO); hookGO = null;
                hookMount.prefab = hp; EditorUtility.SetDirty(hookMount);
                L("tail hook mount prefab saved");
            }

            // liveries (mod-local LiveryData), each offered to its own faction, the default first
            var facBDF = coinParams.liveries[0].faction; var facPALA = coinParams.liveries[2].faction;
            var livs = new List<AircraftParameters.Livery>();
            foreach (var (file, label, fac, isDefault) in Liveries.OrderByDescending(l => l.isDefault))
            {
                var ld = ScriptableObject.CreateInstance<LiveryData>();
                var (gloss, cols) = LiveryJson(file);
                ld.Texture = tex[file]; ld.Glossiness = gloss; ld.Colors = cols;
                var p = $"{Folder}/Liveries/{file}.asset";
                AssetDatabase.CreateAsset(ld, p);
                livs.Add(new AircraftParameters.Livery { name = label, faction = fac == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(AssetDatabase.AssetPathToGUID(p)) });
            }

            // twin-turboprop attack aircraft parameters (A-19) as the starting point; prop-aircraft HUD apps (CI-22)
            var prm = Object.Instantiate(Asset<AircraftParameters>("MonoBehaviour/CAS1Parameters_PLACEHOLDER.asset"));
            prm.HUDExtras = !StockHUDExtras ? null : Asset<GameObject>(JetThrottleHUD ? "GameObject/Multirole1_HUDExtras_PLACEHOLDER.prefab" : "GameObject/COIN_HUDExtras_PLACEHOLDER.prefab");
            prm.name = "GA25X_Parameters";
            if (OwnStatusDisplay || OwnMapIcon) BuildDiagramSprites();
            if (OwnStatusDisplay) prm.StatusDisplay = BuildStatusDisplayPrefab();
            prm.aircraftName = DisplayName; prm.rankRequired = 2;
            // OwnElevatorAirfoil: slotted elevator, tail-like slope, stall at 25 deg (CL 1.45) instead of 17 (1.10): with 30 deg travel at the ground
            // attitude the 0.1.0 elevator sat past its stall (CL 0.79) and could lift the nose wheel only from ~57 m/s at 17.5 t (fm model; game 0.1.0: lift-off 69 m/s)
            var elev = new Airfoil { name = "GA25X_elevator", liftCoef = Mirror(new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.9f), (-0.6381f, -1.0f), (-0.5400f, -1.30f), (-0.4418f, -1.45f), (-0.3927f, -1.40f), (-0.2945f, -1.08f), (-0.1473f, -0.54f), (0f, 0f), (0.1473f, 0.54f), (0.2945f, 1.08f), (0.3927f, 1.40f), (0.4418f, 1.45f), (0.5400f, 1.30f), (0.6381f, 1.0f), (0.785f, 0.9f), (1.571f, 0f), (3.142f, 0f) }), dragCoef = new AnimationCurve(drag.keys) };
            prm.airfoils = OwnElevatorAirfoil ? new[] { wing, tail, elev } : new[] { wing, tail };
            prm.liveries = livs;
            // loadout index = hardpoint set index: 0 cannon, 1 20mm, 2 bay, 3 bay racks, 4 inner, 5 outer, 6 hook, 7 laser, 8 root, 9 mid (FourPylonsPerWing)
            WeaponMount M(string n) => Mount(n);
            var setCount = weaponManagerSetCount;
            NuclearOption.SavedMission.Loadout LO(params WeaponMount[] w) => new NuclearOption.SavedMission.Loadout { weapons = w.Concat(Enumerable.Repeat<WeaponMount>(null, Math.Max(0, setCount - w.Length))).Take(setCount).ToList() };
            var laser = laserAmmo;
            prm.loadouts = new List<NuclearOption.SavedMission.Loadout>
            {
                LO(),
                LO(ammoCannon, ammo20, M("bomb_500_internalx2"), null, M("AGM1_triple"), M("Rocket2_4Pod"), null, laser),
            };
            prm.StandardLoadouts = new[]
            {
                new StandardLoadout { Name = "Gunship", loadout = FourPylonsPerWing
                    ? LO(ammoCannon, ammo20, null, null, M("Rocket2_4Podx3"), M("Rocket2_4Pod"), null, laser, M("AGM1_triple"), M("Rocket2_4Pod"))
                    : LO(ammoCannon, ammo20, null, null, M("Rocket2_4Podx3"), M("Rocket2_4Pod"), null, laser), FuelRatio = 0.7f },
                new StandardLoadout { Name = "Armed overwatch", loadout = FourPylonsPerWing
                    ? LO(ammoCannon, ammo20, null, M("bomb_250_glide_internalx2"), M("AGM1_triple"), M("AAM1_single"), null, laser, M("AGM_heavy_single"), M("AAM1_single"))
                    : LO(ammoCannon, ammo20, null, M("bomb_250_glide_internalx2"), M("AGM1_triple"), M("AAM1_single"), null, laser), FuelRatio = 0.8f },
                new StandardLoadout { Name = "Maritime strike", loadout = FourPylonsPerWing
                    ? LO(ammoCannon, ammo20, M("bomb_500_internalx2"), null, M("AGM_heavy_single"), M("AGM1_triple"), hookMount, laser, M("AGM_heavy_single"), M("AGM_heavy_single"))
                    : LO(ammoCannon, ammo20, M("bomb_500_internalx2"), null, M("AGM_heavy_single"), M("AGM1_triple"), hookMount, laser), FuelRatio = 0.8f },
                new StandardLoadout { Name = "Carrier patrol", loadout = FourPylonsPerWing
                    ? LO(ammoCannon, ammo20, null, null, M("AGM1_triple"), M("AAM1_single"), hookMount, laser, M("AAM1_single"), M("AAM1_single"))
                    : LO(ammoCannon, ammo20, null, null, M("AGM1_triple"), M("AAM1_single"), hookMount, laser), FuelRatio = 0.6f },
            };
            prm.DefaultFuelLevel = 0.7f;
            // flight envelope (spec): 590 km/h = 164 m/s, cruise 480 km/h = 133 m/s, stall 190 / 145 km/h = 53 / 40 m/s, g +5,
            // take-off roll ~350 m at MTOW
            prm.aircraftGLimit = 5.0f; prm.PIDReferenceAirspeed = 130f; prm.maxSpeed = 164f; prm.takeoffSpeed = StolFlaps ? 44f : 47f; prm.takeoffDistance = 350f;   // AI rotates at takeoffSpeed (StolFlaps: nose wheel lifts from ~37, lift-off ~46-50 at 17.5 t)
            prm.turningRadius = 1200f; prm.cornerSpeed = 125f; prm.approachSpeed = 58f; prm.landingSpeed = 46f; prm.shortLandingSpeed = 42f;
            prm.cruiseThrottle = 0.65f; prm.minimumRadarAlt = 120f; prm.groundTurningRadius = 20f;
            if (GunshipAITuning)
            {
                // B-25H findings (in game 1.1.0): a heavy twin needs a higher AI floor than the stock 30-100 m; the GA-25X pulls
                // 5 g (B-25H 3.5), so 300 m instead of 450 m. landingSpeed scales every AI terrain-following height
                // (AutopilotPlane.AutoAim: full height from ~1.9 x landingSpeed = 87 m/s).
                prm.minimumRadarAlt = AIFloorStock181 ? 120f : 300f;   // 1.8.1: see AIFloorStock181
                prm.turningRadius = 1500f;
            }
            AssetDatabase.CreateAsset(prm, Folder + "/GA25X_Parameters.asset");

            float total = parts.Values.Sum(p => p.mass);
            var def = Object.Instantiate(Asset<AircraftDefinition>("MonoBehaviour/CI-22_PLACEHOLDER.asset"));
            def.name = "GA25X";
            def.jsonKey = JsonKey; def.WorkshopTag = DisplayName; def.unitName = DisplayName; def.code = "GA-25X"; def.bogeyName = "";
            def.description = "Rebuilt by PALA from a century-old bomber, the GA-25X is a heavy gunship for armed overwatch and maritime strike. " +
                "A guided 76 mm nose gun picks apart vehicles and small vessels, while a laser turret burns down incoming missiles. " +
                "Short take-off and a tail hook let it fly from rough strips and carrier decks; the BDF operates it too.";
            def.length = 16.13f; def.width = 20.6f; def.height = 4.98f; def.mass = total;
            def.value = 33f; def.radarSize = RadarSize; def.visibleRange = 4500f; def.manpower = 2;
            def.roleIdentity.antiSurface = 0.8f; def.roleIdentity.antiAir = 0.2f; def.roleIdentity.antiMissile = 0.3f;
            def.spawnOffset = new Vector3(0f, SpawnHeight, 0f);
            def.restRotation = Vector3.zero;
            def.aircraftParameters = prm;
            if (OwnMapIcon) { def.mapIcon = mapIconSprite; def.mapIconSize = 1.2f; def.mapOrient = true; }
            def.aircraftInfo = new AircraftInfo { emptyWeight = 9600f, maxSpeed = 590f, stallSpeed = 190f, maneuverability = 5.0f, maxWeight = 17500f };
            def.unitPrefab = null;
            AssetDatabase.CreateAsset(def, Folder + "/GA25X.asset");

            foreach (var u in root.GetComponentsInChildren<Unit>(true)) u.definition = def;
            var rb = root.GetComponent<Rigidbody>(); rb.mass = total;
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, Folder + "/GA25X.prefab");
            def.unitPrefab = prefab;
            EditorUtility.SetDirty(def);

            // take-off locations (spec): medium hangar + revetment; NOT carriers (landing on carriers works through the tail hook)
            var op = ScriptableObject.CreateInstance<Blueprinter.OpAddAircraftToHangars>();
            op.aircraftJsonKey = JsonKey;
            op.hangars.Add(new Blueprinter.OpAddAircraftToHangars.HangarTarget { hangarUnitJsonKey = "hangar_med", hangarNames = { "hangar_med" } });
            op.hangars.Add(new Blueprinter.OpAddAircraftToHangars.HangarTarget { hangarUnitJsonKey = "revetment1", hangarNames = { "revetment1" } });
            AssetDatabase.CreateAsset(op, Folder + "/OpAddAircraftToHangars.asset");
            AssetDatabase.SaveAssets();
            L($"saved prefab, definition (mass {total} kg), parameters, {livs.Count} liveries, {generatedMeshes.Count} meshes");
            return prefab;
        }

        // ga25x_liveries.json: {"pala_twotone": {"name":..., "faction":..., "texture":..., "glossiness":..., "colors": [...]}, ...}
        static (float, LiveryData.TextureColor[]) LiveryJson(string file)
        {
            var path = Path.Combine(RepoTextures, "ga25x_liveries.json");
            if (!File.Exists(path)) return (0.1f, new LiveryData.TextureColor[0]);
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(path));
            Newtonsoft.Json.Linq.JObject e = null;
            foreach (var kv in jo)
                if (kv.Value is Newtonsoft.Json.Linq.JObject o && Path.GetFileNameWithoutExtension((string)o["texture"] ?? "") == file) { e = o; break; }
            if (e == null) return (0.1f, new LiveryData.TextureColor[0]);
            float gloss = e["glossiness"] != null ? (float)e["glossiness"] : 0.1f;
            var cols = new List<LiveryData.TextureColor>();
            if (e["colors"] is Newtonsoft.Json.Linq.JArray arr)
                foreach (var c in arr)
                {
                    var h = ((string)c["color"] ?? "#000000FF").TrimStart('#'); if (h.Length == 6) h += "FF";
                    byte B(int o) => Convert.ToByte(h.Substring(o, 2), 16);
                    cols.Add(new LiveryData.TextureColor { Color = new Color32(B(0), B(2), B(4), B(6)), Count = c["count"] != null ? (int)c["count"] : 1 });
                }
            L($"livery {file}: glossiness {gloss}, {cols.Count} colours");
            return (gloss, cols.ToArray());
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
        static readonly string[] ExpectedSets = FourPylonsPerWing
            ? new[] { "76mm Cannon", "20mm Cannons", "Bomb Bay", "Bomb Bay Racks", "Inner Pylons", "Outer Pylons", "Tail Hook", "Belly Laser", "Root Pylons", "Mid Pylons" }
            : new[] { "76mm Cannon", "20mm Cannons", "Bomb Bay", "Bomb Bay Racks", "Inner Pylons", "Outer Pylons", "Tail Hook", "Belly Laser" };
        static readonly Dictionary<string, string[]> ExpectedOptions = new Dictionary<string, string[]>
        {   // spec loadout table -> stock WeaponMount jsonKeys (docs/ga25x_design.md)
            { "Bomb Bay", new[] { "bomb_500_internalx2", "bomb_125_internalx6", "nuclearBomb1_internal" } },
            { "Bomb Bay Racks", new[] { "bomb_250_internalx2", "bomb_250_glide_internalx2", "bomb_glide1_quad_inernal" } },
            { "Inner Pylons", new[] { "AGM_heavy_single", "AGM1_triple", "Rocket2_4Podx3", "bomb_250_glide_single" } },
            { "Outer Pylons", new[] { "AGM1_triple", "Rocket2_4Pod", "AAM1_single" } },
            { "Root Pylons", new[] { "AGM_heavy_single", "AGM1_triple", "Rocket2_4Podx3", "Rocket2_4Pod", "AAM1_single", "bomb_250_glide_single" } },
            { "Mid Pylons", new[] { "AGM_heavy_single", "Rocket2_4Pod", "AAM1_single", "bomb_250_glide_single" } },
        };
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
                    var ag = AtlasGuard1816.Check(agInst, mats["paint"], Path.Combine(RepoTextures, "ga25x_atlas_manifest.json"), new Dictionary<string, string> { { "hook_mesh", "tailhook" } },
                        AssetDatabase.LoadAssetAtPath<GameObject>(Folder + "/GA25X_tailhook_mount.prefab"));   // the hook is its own mount prefab
                    if (agInst != inst) Object.DestroyImmediate(agInst);   // 1.9.12: the copy without the airbrake panels
                    R("1.8.16 livery atlas: UV0 of the paint meshes == the texture manifest (textures painted on this atlas, files unchanged)", ag.Item1, ag.Item2);
                }
                var ac = inst.GetComponent<Aircraft>();
                var allParts = inst.GetComponentsInChildren<AeroPart>(true);
                bool OurAsset(Object o) { var p = AssetDatabase.GetAssetPath(o); return p.StartsWith(Folder); }

                {
                    var badDm = allParts.Where(ap => G(ap, "damageMaterial") == null || ((IList)G(G(ap, "damageMaterial"), "renderers")).Cast<Object>().Any(r => r == null)).Select(ap => ap.name).ToList();
                    R("every part's livery/damage renderer list has no missing entries (UnitPart.SetLivery NRE)", badDm.Count == 0, badDm.Count == 0 ? $"{allParts.Length} parts" : string.Join(",", badDm));
                }
                {
                    var exR = (Renderer[])G(ac, "exteriorRenderers"); var cg = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name == "canopy_glass").ToList();
                    R("canopy glass hidden in cockpit view (exteriorRenderers, flag)", !CockpitHideCanopyGlass || (cg.Count > 0 && cg.All(r => exR.Contains(r))), $"{cg.Count} canopy_glass renderer(s)");
                }
                {
                    var sg = inst.GetComponentsInChildren<SetGlobalParticles>(true);
                    R("SetGlobalParticles lists have no missing systems", sg.All(x => ((List<ParticleSystem>)G(x, "systems")).All(ps => ps != null)), $"{sg.Length} components, {sg.Sum(x => ((List<ParticleSystem>)G(x, "systems")).Count)} systems");
                }
                // ---- propulsion
                var props = inst.GetComponentsInChildren<ConstantSpeedProp>(true);
                var hubs = props.Select(p => (GameObject)G(p, "hubVisible")).ToList();
                R("two ConstantSpeedProps, distinct hubs, 6 blades each", props.Length == 2 && hubs.All(h => h != null) && hubs.Distinct().Count() == 2 && props.All(p => ((IList)G(p, "blades")).Count == 6),
                    string.Join(", ", props.Select(p => $"{p.name}->{((GameObject)G(p, "hubVisible"))?.name} blades={((IList)G(p, "blades")).Count} rpmLimit={G(p, "rpmLimit")} nominal={G(p, "nominalPower")} reversePitchBraking={G(p, "reversePitchBraking")}")));
                var trs = props.Select(p => (Transmission)G(p, "transmission")).ToList();
                var tes = trs.Select(t => t?.GetComponent<TurbineEngine>()).ToList();
                R("each prop has its own Transmission + TurbineEngine (EnginePower: spec 2.4 MW; boost flag)", trs.Distinct().Count() == 2 && tes.All(t => t != null && Mathf.Abs(t.maxPower - (EnginePower + (BoostInMaxPower ? BoostPower : 0f))) < 1f),
                    string.Join(", ", tes.Select(t => $"{t?.name} maxPower {t?.maxPower / 1e6f:F2} MW maxRPM {t?.maxRPM} IR {G(t, "IRMin")}/{G(t, "IRMax")}")));
                {
                    var tjs = inst.GetComponentsInChildren<Turbojet>(true); var jns = inst.GetComponentsInChildren<JetNozzle>(true);
                    R("hybrid boost: per engine a ~0 N Turbojet + JetNozzle afterburner on the engine part (flag)", !HybridBoost ? tjs.Length == 0 :
                        tjs.Length == 2 && jns.Length == 2 && jns.All(j => G(j, "part") is UnitPart up && up.name.StartsWith("engine_") && G(j, "failureEffect") != null && ((Array)G(j, "afterburners")).Length == 1
                            && ((Array)G(j, "afterburners")).Cast<object>().All(a => G(a, "flameRenderer") != null && G(a, "nozzleGlowRenderer") != null && G(a, "source") != null))
                        && tjs.All(t => t.maxThrust <= 1f && ((UnitPart[])G(t, "criticalParts")).Length == 2 && G(t, "turbineAudio") != null),
                        string.Join(", ", jns.Select(j => $"{j.name}: part {(G(j, "part") as UnitPart)?.name} ab {string.Join("/", ((Array)G(j, "afterburners")).Cast<object>().Select(a => $"{G(a, "thrust")} N from {G(a, "throttleStart")} fuel {G(a, "fuelConsumption")}"))}")));
                }
                R("each prop has its own PropStrikeDetector (trigger, layer 15)", props.All(p => G(p, "propStrikeDetector") is PropStrikeDetector d && d.gameObject.layer == 15 && ((Collider)G(p, "propDiscCollider")).isTrigger), "");
                foreach (var p in props)
                    foreach (var b in (IList)G(p, "blades"))
                    {
                        var bt = (Transform)G(b, "transform"); var lt = (Transform)G(b, "liftTransform");
                        if (bt.parent != ((GameObject)G(p, "hubVisible")).transform || Mathf.Abs(lt.localPosition.x) > 1e-3f || lt.localPosition.z < 1.5f)
                            R($"blade {bt.name} geometry", false, $"parent {bt.parent.name} lift local {lt.localPosition}");
                    }
                var blurOk = props.All(p =>
                {
                    var dm = (List<Mesh>)G(p, "propDiscMeshes"); var pd = (MeshFilter)G(p, "propDisc"); var mr = pd ? pd.GetComponent<MeshRenderer>() : null;
                    return dm.Count == 3 && dm[0] == null && dm[1] != null && dm[2] != null && OurAsset(dm[1]) && mr != null && OurAsset(mr.sharedMaterial) && pd.sharedMesh == null;
                });
                R("prop blur: stage meshes [none, smear, disc], own material", !OwnPropBlur || blurOk, string.Join(" | ", props.Select(p => string.Join(",", ((List<Mesh>)G(p, "propDiscMeshes")).Select(m => m ? m.name : "null")))));
                var cf = inst.GetComponentInChildren<ControlsFilter>(true);
                R("ControlsFilter.ReverseThrust off (AI landing would go full throttle; props do not reverse in the stock code)", cf != null && cf.ReverseThrust == ReverseThrustAI, $"ReverseThrust {cf?.ReverseThrust}");

                // ---- gear
                foreach (var g in inst.GetComponentsInChildren<LandingGear>(true))
                {
                    var wheel = ((Transform[])G(g, "wheels"))[0]; var axle = (Transform)G(g, "axle");
                    var mb = wheel.GetComponent<MeshFilter>().sharedMesh.bounds;
                    float dPivot = Vector3.Distance(wheel.position, axle.position), dMesh = Vector3.Distance(wheel.TransformPoint(mb.center), wheel.position);
                    float r = (float)G(g, "wheelRadius");
                    R($"wheel {wheel.name} centred on axle", dPivot < 0.01f && dMesh < 0.01f, $"r={r:F3}, bottom y={axle.position.y - r:F3}, k={G(g, "springRate")}");
                    var doors = (List<LandingGear.GearDoor>)G(g, "gearDoors");
                    R($"gear {g.name} doors", doors.Count == 2 && doors.All(d => d.transform != null), string.Join(", ", doors.Select(d => $"{d.transform.name} open {d.openAngle.z}")));
                }
                var steer = inst.GetComponentsInChildren<LandingGear>(true).Where(x => (bool)G(x, "steering")).ToList();
                R("nose wheel steers, mains brake", steer.Count == 1 && steer[0].name.Contains("nose") && inst.GetComponentsInChildren<LandingGear>(true).Count(x => (bool)G(x, "braked")) == 2, "");

                // ---- weapons
                var wm = ac.weaponManager;
                R("every hardpoint has a part + transform", wm.hardpointSets.All(s => s.hardpoints.All(h => h.part != null && h.transform != null)),
                    string.Join(" | ", wm.hardpointSets.Select(s => $"{s.name}: " + string.Join(",", s.hardpoints.Select(h => $"{h.transform?.name}@{h.part?.name}")))));
                R("hardpoint sets (loadout order; root/mid appended after the 0.1.0 sets)", wm.hardpointSets.Select(s => s.name).SequenceEqual(LaserTurret ? ExpectedSets : ExpectedSets.Where(x => x != "Belly Laser")),
                    string.Join(", ", wm.hardpointSets.Select(s => $"{s.name}[{string.Join("/", s.weaponOptions.Skip(1).Select(o => o ? o.jsonKey : "null"))}]")));
                foreach (var kv in ExpectedOptions.Where(k => FourPylonsPerWing || !k.Key.StartsWith("Root") && !k.Key.StartsWith("Mid")))
                {
                    var s = wm.hardpointSets.FirstOrDefault(x => x.name == kv.Key);
                    var have = s == null ? new List<string>() : s.weaponOptions.Where(o => o).Select(o => o.jsonKey).ToList();
                    R($"options '{kv.Key}' = spec", s != null && kv.Value.All(have.Contains) && have.Count == kv.Value.Length, string.Join("/", have));
                }
                var sb = wm.hardpointSets.FirstOrDefault(s => s.name == "Bomb Bay"); var sr = wm.hardpointSets.FirstOrDefault(s => s.name == "Bomb Bay Racks");
                int ib = Array.IndexOf(wm.hardpointSets, sb), ir = Array.IndexOf(wm.hardpointSets, sr);
                R("bay sets preclude each other (stock Darkreach pattern), both use the 2 bay doors", sb != null && sr != null && sb.precludingHardpointSets.Contains((byte)ir) && sr.precludingHardpointSets.Contains((byte)ib)
                    && sb.hardpoints.Concat(sr.hardpoints).All(h => h.bayDoors.Length == 2 && h.bayDoors.All(d => d != null)) && sr.hardpoints.Count == 2, $"bay {ib} <-> racks {ir}");
                var hookSet = wm.hardpointSets.FirstOrDefault(s => s.name == "Tail Hook");
                var hm = hookSet?.weaponOptions.LastOrDefault();
                var hookTH = hm != null && hm.prefab != null ? hm.prefab.GetComponent<TailHook>() : null;
                R("tail hook: mount.tailHook = true (WeaponManager.HasTailHook), prefab with TailHook (stowed > 0 > deployed)", hm != null && hm.tailHook && hookTH != null && (!OwnTailHookMount || ((float)G(hookTH, "stowedAngle") > 0f && (float)G(hookTH, "deployedAngle") < 0f && hookTH.hookEnd != null && OurAsset(hm.prefab))),
                    hm == null ? "missing" : $"{hm.jsonKey} prefab {AssetDatabase.GetAssetPath(hm.prefab)} stowed {(hookTH ? G(hookTH, "stowedAngle") : "-")} deployed {(hookTH ? G(hookTH, "deployedAngle") : "-")}");
                var guns = inst.GetComponentsInChildren<Gun>(true);
                var loopers = new List<string>();
                foreach (var gn in guns) foreach (var a in gn.GetComponents<AudioSource>()) if (a.loop) loopers.Add($"{gn.name}:{a.clip?.name}");
                R("no gun AudioSource has loop=true", loopers.Count == 0, loopers.Count == 0 ? $"{guns.Length} guns" : string.Join(",", loopers));
                var g76 = guns.FirstOrDefault(g => g.name == "cannon_mount");
                R("76 mm: stock Tarantula gun values, guided projectile, 96 rounds, fixed (boresight) info", g76 != null && G(g76, "guidedProjectile") != null && (int)G(g76, "magazineCapacity") == CannonRounds && g76.info != null && g76.info.boresight,
                    g76 == null ? "missing" : $"{g76.info?.weaponName} ({AssetDatabase.GetAssetPath(g76.info)}), guided {((Object)G(g76, "guidedProjectile"))?.name}, fireRate {G(g76, "fireRate")}, rounds {G(g76, "magazineCapacity")}, maxRange {g76.info.targetRequirements.maxRange}, AI minAlt {g76.info.targetRequirements.minAltitude}");
                var g20s = guns.Where(g => g.name.StartsWith("gun20_")).ToList();
                R("20 mm: two guns x 250 rounds", g20s.Count == 2 && g20s.All(g => (int)G(g, "magazineCapacity") == Gun20Rounds), string.Join(", ", g20s.Select(g => $"{g.name} {G(g, "magazineCapacity")} {g.info?.weaponName}")));

                // ---- laser turret
                var tlist = inst.GetComponentsInChildren<Turret>(true);
                var lasers = inst.GetComponentsInChildren<Laser>(true);
                if (LaserAsMountPrefab && laserAmmo != null && laserAmmo.prefab != null)
                {
                    var lpL = laserAmmo.prefab.GetComponentsInChildren<Laser>(true);
                    var hpLaser = ac.weaponManager.hardpointSets.FirstOrDefault(h => h.name == "Belly Laser")?.hardpoints.FirstOrDefault();
                    R("laser as mount prefab: no built-in Laser, mount prefab has 1 Laser + beam, hardpoint = aperture on the elevation object, no non-Gun built-in weapons anywhere",
                        lasers.Length == 0 && lpL.Length == 1 && G(lpL[0], "beamRenderer") != null && lpL[0].info == laserInfo && hpLaser != null && hpLaser.BuiltInWeapons.Length == 0 && hpLaser.BuiltInTurrets.Length == 1
                            && hpLaser.transform.IsChildOf((Transform)G(hpLaser.BuiltInTurrets[0], "elevationTransform"))
                            && ac.weaponManager.hardpointSets.SelectMany(h => h.hardpoints).All(h => h.BuiltInWeapons.All(w => w is Gun))
                            && ((WeaponStation[])G(hpLaser.BuiltInTurrets[0], "weaponStations"))[0].WeaponInfo == laserInfo,
                        $"hardpoint {hpLaser?.transform?.name}, prefab lasers {lpL.Length}");
                    lasers = lpL;
                }
                R("dorsal laser: 1 Turret + 1 Laser (elevation object), own TargetDetector (assigned), onlyDefensive, energy info", !LaserTurret || (tlist.Length == 1 && lasers.Length == 1 && tlist.All(t =>
                    {
                        var st = (WeaponStation[])G(t, "weaponStations");
                        return st.Length == 1 && (LaserAsMountPrefab ? st[0].Weapons.Count == 1 && st[0].Weapons[0] != null && st[0].Weapons[0].GetType() == typeof(Weapon) && st[0].Weapons[0].info == laserInfo : st[0].Weapons.Count == 1 && st[0].Weapons[0] == lasers[0] && (Transform)G(t, "elevationTransform") == lasers[0].transform)
                            && G(t, "targetAcquisitionMode").ToString() == "assignedTargetDetectors" && ((IList)G(t, "targetDetectors")).Count == 1 && (bool)G(t, "onlyDefensive") == LaserOnlyDefensive
                            && lasers[0].info.energy && OurAsset(lasers[0].info) && G(lasers[0], "beamRenderer") != null && G(lasers[0], "directionTransform") != null && !(bool)G(lasers[0], "vehicularPowerSupply");
                    })),
                    lasers.Length == 0 ? "none" : $"{lasers[0].info.weaponName}: power {G(lasers[0], "power")} kW, maxAngle {G(lasers[0], "maxAngle")}, el {G(tlist[0], "minElevation")}..{G(tlist[0], "maxElevation")}, antiMissile {lasers[0].info.effectiveness.antiMissile}, range {lasers[0].info.targetRequirements.maxRange}");
                // strict self-fire scan (as the B-25H turrets): pivot + aperture, +-2 deg, 60 m, every aim direction the firing cones allow.
                // 0.3.0 worst-case pose: bay doors open, gear extended, hook deployed. The real scan counts only colliders that exist in game; gear leg boxes
                // (enabled by the game only after a leg breaks off), a hook capsule and the door/gear meshes are a second, VISUAL scan.
                // Self-hits = our colliders (Laser.Linecast damages what it hits). Doors/wheels/struts have no colliders: they are scanned
                // separately as VISUAL obstructions (temporary mesh colliders, beam drawn through them, no damage) and only logged.
                var zTemp = new List<Collider>();
                foreach (var zBd in inst.GetComponentsInChildren<BayDoor>(true)) zBd.transform.localEulerAngles = new Vector3(0, 0, (float)G(zBd, "hingeAngle"));
                foreach (var zLg in inst.GetComponentsInChildren<LandingGear>(true)) foreach (var zBc in zLg.GetComponents<BoxCollider>()) if (!zBc.enabled) zTemp.Add(zBc);
                {
                    var zHj = contract?["tailhook"]; var zHp = zHj != null ? J3(zHj["pivot"]) : new Vector3(0, -0.677f, -7.346f);
                    var zTail = allParts.First(zp => zp.name == "fus_tail").transform;
                    var zHk = new GameObject("scan_hook"); zHk.transform.SetParent(inst.transform, false);
                    zHk.transform.position = inst.transform.TransformPoint(zHp); zHk.transform.rotation = inst.transform.rotation * Quaternion.Euler(40f, 180f, 0f);  // 40 deg below the aft horizontal
                    zHk.transform.SetParent(zTail, true);
                    var zCc = zHk.AddComponent<CapsuleCollider>(); zCc.direction = 2; zCc.radius = 0.08f; zCc.height = 2.3f; zCc.center = new Vector3(0, 0, 1.15f);
                    zCc.enabled = false; zTemp.Add(zCc);
                }
                var zVis = new List<MeshCollider>();
                foreach (var zMr in inst.GetComponentsInChildren<MeshRenderer>(true).Where(zr => zr.name.StartsWith("bomb_door_") || zr.name.StartsWith("gear_")))
                {
                    var zMf = zMr.GetComponent<MeshFilter>(); if (zMf == null || zMf.sharedMesh == null || zMr.GetComponent<Collider>() != null) continue;
                    var zMc = zMr.gameObject.AddComponent<MeshCollider>(); zMc.sharedMesh = zMf.sharedMesh; zMc.enabled = false; zVis.Add(zMc);
                }
                Physics.SyncTransforms();
                int unsafeTotal = 0;
                foreach (var t in tlist)
                {
                    var el = (Transform)G(t, "elevationTransform"); var parent = t.transform.parent; var q0 = t.transform.localRotation;
                    float emin = (float)G(t, "minElevation"), emax = (float)G(t, "maxElevation");
                    var origins = new List<Transform> { el }; if (LaserAsMountPrefab) { var hpl = ac.weaponManager.hardpointSets.FirstOrDefault(h => h.name == "Belly Laser")?.hardpoints.FirstOrDefault(); if (hpl != null) origins.Add(hpl.transform); } else if (lasers.Length > 0) origins.Add((Transform)G(lasers[0], "directionTransform"));
                    var cells = new List<string>(); var zVisCells = new List<string>(); int zSkip = 0;
                    var zCones = ((IEnumerable)G(t, "firingCones")).Cast<FiringCone>().ToArray();
                    for (float a = -180f; a < 180f; a += 5f)
                        for (float e = emin; e <= emax + 0.01f; e += 2.5f)
                        {
                            var zD = parent.rotation * q0 * Quaternion.Euler(0, a, 0) * Quaternion.Euler(-e, 0, 0) * Vector3.forward;
                            if (BellyLaser && zCones.Length > 0 && !FiringConeChecker.VectorWithinFiringCones(zCones, zD, out _)) { zSkip++; continue; }
                            {   // visual obstructions (no damage): doors / gear meshes only
                                foreach (var zv in zVis) zv.enabled = true; foreach (var zt in zTemp) zt.enabled = true;
                                bool zIsVis = false;
                                foreach (var zo in origins) foreach (var zh in Physics.RaycastAll(zo.position - zD * 0.05f, zD, 60f, ~0, QueryTriggerInteraction.Ignore)) if ((zh.collider is MeshCollider zvmc && zVis.Contains(zvmc)) || zTemp.Contains(zh.collider)) zIsVis = true;
                                foreach (var zv in zVis) zv.enabled = false; foreach (var zt in zTemp) zt.enabled = false;
                                if (zIsVis) zVisCells.Add($"({a:F0},{e:F1})");
                            }
                            bool hitOwn = false;
                            foreach (var j in new[] { new Vector2(0, 0), new Vector2(2, 0), new Vector2(-2, 0), new Vector2(0, 2), new Vector2(0, -2) })
                            {
                                var d = parent.rotation * q0 * Quaternion.Euler(0, a + j.x, 0) * Quaternion.Euler(-(e + j.y), 0, 0) * Vector3.forward;
                                foreach (var o in origins)
                                    foreach (var h in Physics.RaycastAll(o.position - d * 0.05f, d, 60f, ~0, QueryTriggerInteraction.Ignore))
                                        if (h.collider.enabled && h.collider.transform.IsChildOf(inst.transform) && !h.collider.transform.IsChildOf(t.transform)) hitOwn = true;
                            }
                            if (hitOwn) cells.Add($"({a:F0},{e:F1})");
                        }
                    unsafeTotal += cells.Count;
                    L($"  laser envelope {t.name}: el {emin}..{emax}, {zCones.Length} cones ({zSkip} cells outside them): {cells.Count} unsafe cells {string.Join(" ", cells.Take(40))}");
                    L($"  laser envelope {t.name}: VISUAL only (doors open, gear meshes + leg boxes, hook capsule: no collider in game while attached, no damage): {zVisCells.Count} cells {string.Join(" ", zVisCells.Take(60))}");
                }
                foreach (var zc in zTemp) { if (zc is BoxCollider) zc.enabled = false; else Object.DestroyImmediate(zc.gameObject); }
                foreach (var zc in zVis) Object.DestroyImmediate(zc);
                foreach (var zBd in inst.GetComponentsInChildren<BayDoor>(true)) zBd.transform.localEulerAngles = Vector3.zero;
                if (BellyLaser && tlist.Length == 1)
                {
                    var zC0 = ((IEnumerable)G(tlist[0], "firingCones")).Cast<FiringCone>().First();
                    var zMt = tlist[0].transform.parent;
                    R("belly laser: el -90..-2, inclusion cone about -mount.up, half-angle 89 (no world-up cone)", Mathf.Approximately((float)G(tlist[0], "minElevation"), -90f) && Mathf.Approximately((float)G(tlist[0], "maxElevation"), -2f) && Vector3.Angle(zC0.GetDirection(), -zMt.up) < 0.5f && Mathf.Approximately(zC0.GetAngle(), 89f) && OwningPart(tlist[0].transform).name == "fus_rear",
                        $"cone axis {zC0.GetDirection().ToString("F2")} angle {zC0.GetAngle()}, part {OwningPart(tlist[0].transform)?.name}");
                }
                R("laser envelope: no aim direction into our own airframe (pivot + aperture, +-2 deg, 60 m; doors open, gear down, hook down)", unsafeTotal == 0, unsafeTotal == 0 ? "all clean" : $"{unsafeTotal} unsafe cells (see log)");
                if (LaserBeam197)
                {   // 1.9.7: BEAM-line sweep (LaserSweep197.cs): target directions over the whole sphere, the game's cone checker + the settled turret pose + the stock laser gate
                    float zMa = lasers.Length > 0 ? (float)G(lasers[0], "maxAngle") : -1f;
                    var zAfter = LaserSweep197.CheckInstance(inst, LaserBeamAngle197); var zBefore = LaserSweep197.CheckInstance(inst, LaserSweep197.StockAngle);
                    foreach (var zr in zBefore) L("  1.9.7 beam sweep BEFORE " + zr);
                    foreach (var zr in zAfter) L("  1.9.7 beam sweep AFTER  " + zr);
                    R($"1.9.7 laser beam = bore line: Laser.maxAngle {LaserBeamAngle197} (stock Laser_EW1 30); beam sweep over every target direction: 0 damage lines (solid own colliders) on the turret's own fire path; the pilot / AI trigger path keeps only the elevation-clamp residual (<= 12 lines, the plugin guard's job) against hundreds at 30",
                        Mathf.Approximately(zMa, LaserBeamAngle197) && zAfter.Count == 1 && zAfter.All(LaserSweep197.Clean) && zBefore.Sum(zr => zr.pilotCol) > 50 * Mathf.Max(1, zAfter.Sum(zr => zr.pilotCol)),
                        $"maxAngle {zMa}; after: {string.Join("; ", zAfter)} | at the 1.9.6 angle 30: turret path {zBefore.Sum(zr => zr.turretCol)} damage / {zBefore.Sum(zr => zr.turretDisc)} prop-disc / {zBefore.Sum(zr => zr.turretMesh)} mesh-only lines, pilot path {zBefore.Sum(zr => zr.pilotCol)} / {zBefore.Sum(zr => zr.pilotDisc)} / {zBefore.Sum(zr => zr.pilotMesh)} [{string.Join(" ", zBefore.Select(zr => zr.Top))}]");
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
                            if (!OurAsset(zmf.sharedMesh)) zBad.Add(zp.name + ": mesh not ours");
                            if (OwningPart(zh) == null || OwningPart(zh).name != "fus_rear") zBad.Add(zh.name + ": owning part " + OwningPart(zh)?.name);
                            if (zh.GetComponentsInParent<Component>(true).Any(c => c != null && c.GetType().Name == "EscapeCapsule")) zBad.Add(zh.name + ": under an escape capsule part");
                            if (zh.GetComponentsInChildren<Collider>(true).Length > 0) zBad.Add(zh.name + ": collider under the hinge");
                            if (zh.GetComponentsInChildren<UnitPart>(true).Length > 0) zBad.Add(zh.name + ": UnitPart under the hinge");
                            foreach (var zc in zh.GetComponentsInChildren<Component>(true))
                                if (zc == null || !(zc is Transform || zc is MeshFilter || zc is MeshRenderer)) zBad.Add(zh.name + ": extra component " + (zc == null ? "missing script" : zc.GetType().Name));
                            // shoulder panels: hinge line square to the long axis and tilted over the shoulder (up-and-inboard on the left, the mirror image on the right), outward = up and away from the centre line, forward = forward
                            var zx = inst.transform.InverseTransformDirection(zh.right); var zy = inst.transform.InverseTransformDirection(zh.up); var zf = inst.transform.InverseTransformDirection(zh.forward);
                            float zs = Mathf.Sign(inst.transform.InverseTransformPoint(zh.position).x);
                            if (Mathf.Abs(zx.z) > 0.001f || zx.x < 0.5f || zx.y * zs > -0.3f) zBad.Add(zh.name + ": hinge line (local X) " + zx.ToString("F3") + " not square to the long axis / not tilted over the shoulder");
                            if (zy.y < 0.5f || zy.x * zs < 0.3f || zf.z < 0.99f) zBad.Add(zh.name + ": outward " + zy.ToString("F3") + " / forward " + zf.ToString("F3"));
                            var zmn = zmr.sharedMaterials.Select(zq => zq != null ? zq.name : "null").ToList();
                            if (!zmr.sharedMaterials.Contains(mats["cockpit"]) || !zmr.sharedMaterials.Contains(mats["metal_dark"])) zBad.Add(zp.name + ": inner face not on the dark cockpit finish / no metal_dark (" + string.Join(", ", zmn) + ")");
                            if (zh.GetComponentsInChildren<MeshRenderer>(true).Count(r => r.sharedMaterials.Any(StockStructure.IsStructMat)) != 1) zBad.Add(zh.name + ": frames / stringers not on the internals look material (one child renderer expected)");
                            var zdm = ((IList)G(G(OwningPart(zh), "damageMaterial"), "renderers")).Cast<Object>().ToList();
                            if (!zdm.Contains(zmr)) zBad.Add(zp.name + ": not in fus_rear's livery / damage renderer list");
                        }
                        foreach (var zt in zTrays)
                        {
                            if (zt.GetComponentsInChildren<Collider>(true).Length > 0) zBad.Add(zt.name + ": collider");
                            if (zt.GetComponentsInChildren<MeshRenderer>(true).Any(r => r.sharedMaterials.Contains(mats["paint"]))) zBad.Add(zt.name + ": paint on the well");
                            var ztr = zt.GetComponent<MeshRenderer>();
                            if (ztr == null || !ztr.sharedMaterials.Contains(mats["cockpit"])) zBad.Add(zt.name + ": well floor not on the dark cockpit finish");
                            if (inst.GetComponentsInChildren<Transform>(true).Any(t => t.name.StartsWith("airbrake_") && (t.name.EndsWith("_axis") || t.name.EndsWith("_out")))) zBad.Add("frame marker left in the prefab");
                            if (OwningPart(zt) == null || OwningPart(zt).name != "fus_rear" || zt.parent != OwningPart(zt).transform) zBad.Add(zt.name + ": not a direct child of fus_rear");
                        }
                        R("1.9.12 airbrake panels: two hinges under fus_rear (no escape-capsule parent), hinge line square to the long axis and tilted over the shoulder, each with one panel mesh child (our mesh, paint = material 0, in fus_rear's livery list, inner face on the dark cockpit finish, frames on the internals look material), only Transform / MeshFilter / MeshRenderer under a hinge, no collider, no part; two fixed wells with a dark floor, without paint or collider; no frame marker in the prefab",
                            zHinges.Count == 2 && zTrays.Count == 2 && zBad.Count == 0, zBad.Count == 0 ? string.Join(", ", zHinges.Select(t => t.name).Concat(zTrays.Select(t => t.name))) : string.Join("; ", zBad.Take(8)));
                        // opening sense and travel, exactly the stock call
                        var zGain = zHinges.Select(zh => AirbrakeOpenGain1912(zh, inst.transform, AirbrakeMaxAngle1912)).ToList();
                        R($"1.9.12 airbrake panels: the stock rotation (+{AirbrakeMaxAngle1912} deg about the hinge's local X) moves each free edge outward by >= 0.2 m (away from the long axis), left = right",
                            zGain.Count == 2 && zGain.All(g => g >= 0.2f) && Mathf.Abs(zGain[0] - zGain[1]) < 0.01f, string.Join(" / ", zGain.Select(g => g.ToString("F3") + " m")));
                        // paint texels: every panel paint vertex takes the atlas texel of the fus_rear skin point 3-6 mm under it
                        {
                            var zfm = allParts.First(p => p.name == "fus_rear").GetComponent<MeshFilter>(); var zsm = zfm.sharedMesh;
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
                            R("1.9.12 airbrake panels carry the livery: every panel paint vertex has the atlas UV0 of the fus_rear skin point 3-6 mm under it (same texels as the skin beneath; the atlas is not re-packed, the manifest row above is checked without the panels)",
                                zn > 0 && zmiss == 0 && zdMin >= 0.003f && zdMax <= 0.006f, $"{zn} paint vertices, {zmiss} with a UV outside fus_rear's paint triangles, skin point {zdMin * 1000f:F2}..{zdMax * 1000f:F2} mm away");
                        }
                        // belly laser against the panels-open pose: the 1.9.7 beam sweep (every visible mesh is an obstacle there) with both panels at maxAngle
                        if (LaserBeam197)
                        {
                            var zKeep = zHinges.Select(t => t.localRotation).ToList();
                            List<LaserSweep197.Result> zOpen;
                            try
                            {
                                foreach (var zh in zHinges) zh.Rotate(new Vector3(AirbrakeMaxAngle1912, 0f, 0f), Space.Self);
                                Physics.SyncTransforms();
                                zOpen = LaserSweep197.CheckInstance(inst, LaserBeamAngle197);
                            }
                            finally { for (int zi = 0; zi < zHinges.Count; zi++) zHinges[zi].localRotation = zKeep[zi]; Physics.SyncTransforms(); }
                            var zShut = LaserSweep197.CheckInstance(inst, LaserBeamAngle197);
                            foreach (var zr in zOpen) L("  1.9.12 beam sweep, airbrake panels OPEN " + zr);
                            var zOnPanel = zOpen.SelectMany(zr => zr.by.Where(k => k.Key.StartsWith("airbrake"))).ToList();
                            float zLaserY = inst.GetComponentsInChildren<Transform>(true).First(t => t.name == "muzzle_laser").position.y;
                            float zPanelLow = float.MaxValue;
                            foreach (var zh in zHinges) foreach (var zmf in zh.GetComponentsInChildren<MeshFilter>(true)) foreach (var zv in zmf.sharedMesh.vertices) zPanelLow = Mathf.Min(zPanelLow, zmf.transform.TransformPoint(zv).y);
                            R("1.9.12 belly laser with the airbrake panels OPEN: beam sweep over every target direction meets no panel (not even as a mesh-only line), stays clean, same line counts as with the panels shut; the panels are above the laser aperture",
                                zOpen.Count == 1 && zOpen.All(LaserSweep197.Clean) && zOnPanel.Count == 0 && zShut.Count == 1 && zOpen[0].pilotCol == zShut[0].pilotCol && zOpen[0].pilotMesh == zShut[0].pilotMesh && zOpen[0].turretMesh == zShut[0].turretMesh && zPanelLow > zLaserY + 0.5f,
                                $"open: {string.Join("; ", zOpen)} | shut: pilot path {zShut.Sum(zr => zr.pilotCol)} / {zShut.Sum(zr => zr.pilotDisc)} / {zShut.Sum(zr => zr.pilotMesh)} | lines on a panel {zOnPanel.Sum(k => k.Value)} | panel lowest y {zPanelLow:F3}, aperture y {zLaserY:F3}");
                        }
                    }
                }

                // ---- sensors, power, countermeasures
                var tc = ac.targetCam; var ldz = inst.GetComponentInChildren<LaserDesignator>(true);
                R("optics: EOTS x3 / 10 km, TargetCam at the chin ball, laser designator 4 targets", ac.EOTS != null && Mathf.Approximately((float)G(ac.EOTS, "magnification"), OpticsZoom) && Mathf.Approximately((float)G(ac.EOTS, "visualRange"), OpticsRange) && tc != null && ldz != null && (int)G(ldz, "maxTargets") == LaserDesignatorTargets,
                    $"EOTS {G(ac.EOTS, "visualRange")} m x{G(ac.EOTS, "magnification")}, designator {(ldz ? G(ldz, "maxTargets") : "-")}");
                var radar = inst.GetComponent<Radar>();
                R("radar in the skin: Radar 40 km (EW-25 values otherwise)", !RadarInSkin || (radar != null && Mathf.Approximately(new SerializedObject(radar).FindProperty("RadarParameters.maxRange").floatValue, RadarRange)),
                    radar == null ? "none" : $"maxRange {new SerializedObject(radar).FindProperty("RadarParameters.maxRange").floatValue}, cone {G(radar, "radarCone")}");
                var jam = inst.GetComponent<RadarJammer>();
                R("radar jammer: intensity 8, 50 kW (EW-25 values)", !RadarJammerEW || (jam != null && Mathf.Approximately((float)G(jam, "jammingIntensity"), 8f) && Mathf.Approximately((float)G(jam, "powerUsage"), JammerPowerKW)), jam == null ? "none" : $"intensity {G(jam, "jammingIntensity")}, power {G(jam, "powerUsage")} kW");
                var ps = inst.GetComponent<PowerSupply>();
                R("power: 1,500 kJ capacitor, two motor-generators x 900 kW at full rpm", ps != null && Mathf.Approximately((float)G(ps, "maxCharge"), PowerMaxCharge) && ((GameObject[])G(ps, "powerSources")).Length == 2 && Mathf.Abs((float)G(ps, "chargePerRPM") * TurbineMaxRPM - 900f) < 1f,
                    ps == null ? "none" : $"maxCharge {G(ps, "maxCharge")} kJ, chargePerRPM {G(ps, "chargePerRPM")} x {TurbineMaxRPM} rpm");
                var fe = inst.GetComponent<FlareEjector>();
                R("flares: 96, 4 ejection points (waist dispensers + tail cone)", fe != null && (int)G(fe, "ammo") == FlareCount && ((IList)G(fe, "ejectionPoints")).Count == 4, fe == null ? "none" : $"ammo {G(fe, "ammo")}, points {((IList)G(fe, "ejectionPoints")).Count}");

                // ---- renderers / colliders
                var bad = new List<string>();
                foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
                {
                    if (r is ParticleSystemRenderer) continue;
                    if (r is SkinnedMeshRenderer && r.GetComponentInParent<Pilot>() != null) continue;
                    bool StockOk(Object o) { var ap = AssetDatabase.GetAssetPath(o); return ap.Contains("tacScreenDisplay_PLACEHOLDER") || ap.Contains("targetCamDisplay_PLACEHOLDER") || ap.Contains("laserCone_PLACEHOLDER") || ap.Contains("Touchscreen_off_PLACEHOLDER") || ap.Contains("light_green_off_PLACEHOLDER")
                        || (StockCockpitKit && new[] { "ejectionSeat_PLACEHOLDER", "Seats_PLACEHOLDER", "sfb_joystick_PLACEHOLDER", "sfb_throttle_PLACEHOLDER", "hotas_PLACEHOLDER", "SFB_cockpit_PLACEHOLDER", "aircraft_structure_PLACEHOLDER" }.Any(ap.Contains)); }
                    foreach (var m in r.sharedMaterials) if (m == null || !(OurAsset(m) || StockOk(m))) bad.Add($"{r.name}:mat {(m ? AssetDatabase.GetAssetPath(m) : "null")}");
                    var mf = r.GetComponent<MeshFilter>();
                    if (mf != null && mf.sharedMesh != null && !(OurAsset(mf.sharedMesh) || StockOk(mf.sharedMesh))) bad.Add($"{r.name}:mesh {AssetDatabase.GetAssetPath(mf.sharedMesh)}");
                }
                R("every airframe renderer uses our meshes + materials (stock: screens, Touchscreen_off, light_green_off strips, laser beam" + (StockCockpitKit ? ", 0.3.1 kitbash: seat, stick, throttle, aircraft_structure)" : ")"), bad.Count == 0, bad.Count == 0 ? $"{inst.GetComponentsInChildren<MeshRenderer>(true).Length} mesh renderers" : string.Join("; ", bad.Take(20)));
                // 0.3.1: the stock seat on each crew figure keeps the COIN figure's own collider (convex, DISABLED, stock ejectionSeat mesh)
                bool StockSeatCol(MeshCollider c) => StockCockpitKit && c.name == "EjectionSeat" && c.convex && !c.enabled && AssetDatabase.GetAssetPath(c.sharedMesh).Contains("ejectionSeat_PLACEHOLDER");
                var colsBad = inst.GetComponentsInChildren<MeshCollider>(true).Where(c => !StockSeatCol(c) && (!c.convex || !OurAsset(c.sharedMesh))).Select(c => c.name).ToList();
                R("every MeshCollider convex, from our meshes" + (StockCockpitKit ? " (stock seats: COIN collider, convex, disabled)" : ""), colsBad.Count == 0, string.Join(",", colsBad));

                // ---- mass / balance / structure
                float total = allParts.Sum(p => p.mass);
                var def = ac.definition as AircraftDefinition;
                R("total mass = definition = 9,600 kg (spec empty weight)", Mathf.Abs(total - def.mass) < 1f && Mathf.Abs(total - 9600f) < 1f, $"parts {total} kg, {allParts.Length} parts");
                Vector3 com = Vector3.zero;
                foreach (var p in allParts) { var c = p.GetComponent<MeshCollider>(); com += (c != null ? p.transform.TransformPoint(c.sharedMesh.bounds.center) : p.transform.position) * p.mass; }
                com /= total;
                var mainAxle = inst.GetComponentsInChildren<LandingGear>(true).Where(x => (bool)G(x, "braked")).Select(x => ((Transform)G(x, "axle")).position).ToList();
                var noseAxle = inst.GetComponentsInChildren<LandingGear>(true).First(x => (bool)G(x, "steering"));
                float mainZ = mainAxle.Average(p => p.z), groundY = mainAxle.Average(p => p.y) - 0.597f, noseZ = ((Transform)G(noseAxle, "axle")).position.z;
                float tip = Mathf.Atan2(com.z - mainZ, com.y - groundY) * Mathf.Rad2Deg;
                R("CoM well ahead of main wheels (tip-back > 10 deg)", tip > 10f, $"empty CoM {com.ToString("F3")} (collider-centroid estimate), {com.z - mainZ:F2} m ahead of main axle, tip-back {tip:F1} deg, nose wheel load {(com.z - mainZ) / (noseZ - mainZ) * 100:F0}%");
                var prm = def.aircraftParameters;
                var livBad = prm.liveries.Where(l => !AssetDatabase.GUIDToAssetPath(l.assetReference.AssetGUID).StartsWith(Folder)).Select(l => l.name).ToList();
                var facs = prm.liveries.Select(l => l.faction?.name).Distinct().ToList();
                R("liveries mod-local, both factions (PALA design; BDF flies it in its standard camouflage)", prm.liveries.Count >= 2 && livBad.Count == 0 && facs.Count == 2, string.Join(", ", prm.liveries.Select(l => $"{l.name} ({l.faction?.name})")));
                R("every AeroPart parent is a part (detach works)", allParts.All(p => p.transform == inst.transform || p.transform.parent.GetComponent<AeroPart>() != null), "");
                R("every Unit.definition set", inst.GetComponentsInChildren<Unit>(true).All(u => u.definition == def), "");
                R("NetworkIdentity present (real Mirage)", inst.GetComponent<Mirage.NetworkIdentity>() != null, "");
                var csurf = inst.GetComponentsInChildren<ControlSurface>(true);
                var aeroCS = csurf.Where(c => ((GameObject)G(c, "visibleMesh")).name.EndsWith("_hinge")).ToArray();
                R("control surfaces (aerodynamic)", aeroCS.Length == 6, string.Join(", ", aeroCS.Select(c => c.name)));
                {
                    var hlds = inst.GetComponentsInChildren<HighLiftDevice>(true);
                    string Desc(HighLiftDevice h) { var mp = ((Array)G(h, "movingParts")).GetValue(0); var t = (Transform)G(mp, "transform"); var ap = (AeroPart)G(h, "aeroPart"); return $"{ap?.name}+{G(h, "deployedArea")}@{t?.name}{G(mp, "anglesDeployed")}"; }
                    bool ok = !StolFlaps ? hlds.Count(h => (float)G(h, "deployedArea") > 0f) == 4
                        : hlds.Length == 8 && hlds.Count(h => (float)G(h, "deployedArea") > 0f) == 4 && hlds.Where(h => (float)G(h, "deployedArea") > 0f).All(h =>
                            {   // area devices sit on the wing panels and turn exactly that panel's lift frame
                                var ap = (AeroPart)G(h, "aeroPart"); var t = (Transform)G(((Array)G(h, "movingParts")).GetValue(0), "transform");
                                return ap != null && (ap.name.StartsWith("wing_inner") || ap.name.StartsWith("wing_outer")) && t == (Transform)G(ap, "liftNormal") && Quaternion.Angle(t.localRotation, Quaternion.identity) < 0.01f;
                            })
                          && hlds.Where(h => (float)G(h, "deployedArea") == 0f).All(h =>
                            {   // flap parts only draw: their moving part is NOT their lift frame
                                var ap = (AeroPart)G(h, "aeroPart"); var t = (Transform)G(((Array)G(h, "movingParts")).GetValue(0), "transform");
                                return ap != null && ap.name.StartsWith("flap_") && t != (Transform)G(ap, "liftNormal") && t.GetComponentsInChildren<MeshRenderer>(true).Length > 0;
                            });
                    R(StolFlaps ? "flaps: 4 wing-panel HighLiftDevices (+area, own lift frame) + 4 visual flap devices (lift frame untouched)" : "flaps (HighLiftDevice with area)", ok, string.Join(", ", hlds.Select(Desc)));
                }
                R("airfoils (wing, tail" + (OwnElevatorAirfoil ? ", elevator: only the 2 elevators use it)" : ")"), prm.airfoils.Length == (OwnElevatorAirfoil ? 3 : 2) && allParts.All(p => (int)G(p, "airfoil") < prm.airfoils.Length)
                    && (!OwnElevatorAirfoil || allParts.Where(p => (int)G(p, "airfoil") == 2).Select(p => p.name).OrderBy(x => x).SequenceEqual(new[] { "elevator_L", "elevator_R" })),
                    string.Join(", ", prm.airfoils.Select(a => $"{a.name} CLmax {Enumerable.Range(0, 128).Max(i => -a.liftCoef.Evaluate((i - 64) * 0.04908734f)):F2}")));
                {
                    var tips = allParts.Where(p => p.name.StartsWith("wing_tip")).ToList(); var inner = allParts.First(p => p.name == "wing_inner_L");
                    float Inc(AeroPart p) { var ln = (Transform)G(p, "liftNormal"); return Vector3.SignedAngle(Vector3.ProjectOnPlane(p.transform.forward, ln.right), ln.forward, ln.right); }
                    R("wing washout: tips " + (WingIncidence - TipIncidence) + " deg below the panels", tips.All(t => Mathf.Abs(Mathf.Abs(Inc(inner)) - Mathf.Abs(Inc(t)) - (WingIncidence - TipIncidence)) < 0.2f), $"inner {Inc(inner):F2}, tips {string.Join("/", tips.Select(t => Inc(t).ToString("F2")))} deg");
                }
                {
                    var fso = new SerializedObject(cf);
                    float FB(string n) => fso.FindProperty("flyByWire." + n).floatValue;
                    R("fly-by-wire: gLimit (HUD ~gLimit+1), alpha limiter, take-off speed", Mathf.Approximately(FB("gLimitPositive"), PullOut187F ? 5f : FBWg5 ? 4f : 5f) && Mathf.Approximately(FB("alphaLimiter"), GentleStall ? 10f : 15f) && (!GentleStall || Mathf.Approximately(FB("alphaLimiterStrength"), 0.25f)),
                        $"gLimit {FB("gLimitPositive")}, corner {FB("cornerSpeed")}, alphaLimiter {FB("alphaLimiter")} x {FB("alphaLimiterStrength")}, takeoffSpeed {FB("takeoffSpeed")}, pF {FB("pFactorFast")} dF {FB("dFactorFast")}");
                }
                {
                    // standard loadouts: every mount is an option of its set, and the take-off mass stays within the spec MTOW (17.5 t)
                    var sets = wm.hardpointSets; var badLo = new List<string>(); var masses = new List<string>();
                    float fuelCap = inst.GetComponentsInChildren<FuelTank>(true).Sum(f => (float)G(f, "fuelCapacity"));
                    foreach (var sl in prm.StandardLoadouts)
                    {
                        float m = allParts.Sum(p => p.mass) + fuelCap * sl.FuelRatio;
                        for (int i = 0; i < sl.loadout.weapons.Count; i++)
                        {
                            var wmt = sl.loadout.weapons[i]; if (wmt == null) continue;
                            if (i >= sets.Length || !sets[i].weaponOptions.Contains(wmt)) badLo.Add($"{sl.Name}[{i}] {wmt.jsonKey}");
                            m += wmt.mass * (i < sets.Length ? sets[i].hardpoints.Count : 1);
                        }
                        masses.Add($"{sl.Name} {m / 1000f:F1} t");
                        if (m > 17500f) badLo.Add($"{sl.Name} {m:F0} kg > MTOW");
                    }
                    R("standard loadouts: valid options per set, take-off mass <= 17.5 t (mount mass x hardpoints + fuel ratio)", badLo.Count == 0 && prm.loadouts.All(l => l.weapons.Count == sets.Length) && prm.StandardLoadouts.All(l => l.loadout.weapons.Count == sets.Length), (badLo.Count > 0 ? "BAD " + string.Join("; ", badLo) + " | " : "") + string.Join(", ", masses));
                }
                R("fuel 3,800 kg in the wings", Mathf.Abs(inst.GetComponentsInChildren<FuelTank>(true).Sum(f => (float)G(f, "fuelCapacity")) - FuelKg) < 1f, $"{inst.GetComponentsInChildren<FuelTank>(true).Length} tanks");
                {   // 1.8.3 (user review item 9): stock internals
                    var ftk = inst.GetComponentsInChildren<FuelTank>(true);
                    bool linked = ftk.Length == 4 && ftk.All(f => ((FuelTank[])G(f, "connectedTanks")).Length == 1) && ftk.All(f => (float)G(f, "ruptureGMin") >= 49f && (float)G(f, "ruptureGMin") <= 51f);
                    R("1.8.3 fuel: 4 wing tanks (inner / outer, both sides) with the AB-4 wing-tank settings (rupture 50 g), inner <-> outer linked",
                      !BomberFuelTanks183 || linked, string.Join("; ", ftk.Select(f => $"{f.name} {G(f, "fuelCapacity")} kg rupt {G(f, "ruptureGMin")} links {((FuelTank[])G(f, "connectedTanks")).Length}")));
                    var rs_ = inst.GetComponentsInChildren<MeshRenderer>(true);
                    var ourStruct = rs_.Where(r_ => r_.gameObject.layer != 3 && !r_.name.Contains("_blade") && r_.sharedMaterials.Any(m_ => m_ != null && m_.name == "GA25X_structure")).Select(r_ => r_.name).ToList();   // 1.9.14: blades keep their tip sheath in one renderer
                    // 1.9.14 (user report: blade tips visible over the blur disc): each ConstantSpeedProp blade is ONE renderer, nothing under it
                    var bladeExtra = inst.GetComponentsInChildren<ConstantSpeedProp>(true).SelectMany(p_ => ((IEnumerable)G(p_, "blades")).Cast<ConstantSpeedProp.PropBlade>())
                        .SelectMany(b_ => b_.renderer.GetComponentsInChildren<Renderer>(true).Where(x_ => x_ != b_.renderer).Select(x_ => x_.name)).ToList();
                    var bladeCount = inst.GetComponentsInChildren<ConstantSpeedProp>(true).Sum(p_ => ((IEnumerable)G(p_, "blades")).Cast<object>().Count());
                    R("1.9.14 prop blades: one renderer per blade, no child renderer left visible when the blur disc shows", bladeExtra.Count == 0 && bladeCount == 12,
                      $"{bladeCount} blades, extra renderers: {string.Join(", ", bladeExtra.Take(6))}");
                    // 1.9.14 (in game r6: a yellow ring over the blur disc at the tip radius): the blur atlas carries no coloured tip band
                    var pbPath = $"{Folder}/Textures/ga25x_propblur.png"; var pb = new Texture2D(2, 2);
                    int pbYellow = -1, pbRing = -1;
                    if (File.Exists(pbPath) && pb.LoadImage(File.ReadAllBytes(pbPath)))
                    {
                        var pbp = pb.GetPixels32();
                        pbYellow = pbp.Count(c_ => c_.a > 8 && c_.r - c_.b > 40);
                        // disc half (y < 512): mean alpha just inside vs at the tip radius must not jump
                        float A(float r0, float r1) { var v_ = new List<float>(); for (int y_ = 0; y_ < 512; y_++) for (int x_ = 0; x_ < 512; x_++) { float cx_ = (x_ + 0.5f - 256f) / 250f, cy_ = (y_ + 0.5f - 256f) / 250f, rr_ = Mathf.Sqrt(cx_ * cx_ + cy_ * cy_); if (rr_ > r0 && rr_ < r1) v_.Add(pbp[y_ * 512 + x_].a); } return v_.Average(); }
                        pbRing = Mathf.RoundToInt(A(0.93f, 0.97f) - A(0.85f, 0.90f));
                    }
                    R("1.9.14 prop blur: no yellow / brighter ring at the tip radius on the GA-25X blur disc", pbYellow == 0 && pbRing <= 15,   // old ring = +41
                      $"coloured px {pbYellow}, tip-ring alpha step {pbRing}");
                    var ckArt = rs_.SelectMany(r_ => r_.sharedMaterials).FirstOrDefault(m_ => m_ != null && m_.name == "GA25X_ck_art");
                    R("1.9.14 cockpit: the painted lit lamps / LED digits glow (ck_art emission map ga25x_ckart_e)", !CockpitEmission1914 || (ckArt != null && ckArt.IsKeywordEnabled("_EMISSION") && ckArt.GetTexture("_EmissionMap") != null),
                      ckArt == null ? "no ck_art" : $"emission {ckArt.IsKeywordEnabled("_EMISSION")}, map {ckArt.GetTexture("_EmissionMap")?.name}, colour {ckArt.GetColor("_EmissionColor")}");
                    bool glOk = GearLight1914.Check(inst, GearLight1914.Enabled ? 1 : 0, out var glMsg);
                    R("1.9.14 gear light: the stock CI-22 gear light (spot + glow, lights_runway) on the nose leg, NavLights Never (on with the gear)", glOk, glMsg);
                    var stockStruct = rs_.Where(r_ => r_.sharedMaterials.Any(m_ => StockStructure.IsStructMat(m_))).ToList();
                    bool vcolS = stockStruct.All(r_ => { var mm = r_.GetComponent<MeshFilter>().sharedMesh; return mm.colors32.Length == mm.vertexCount; });
                    R("1.8.3 internals: frames / ribs / stubs drawn with the stock aircraft_structure (vertex colour), none left on our tiled structure material",
                      !StockStructure.Enabled || (ourStruct.Count == 0 && stockStruct.Count > 0 && vcolS), $"{stockStruct.Count} stock-structure renderers ({stockStruct.Sum(r_ => r_.GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3)} tris), our structure left on: {string.Join(", ", ourStruct.Take(6))}");
                }
                {   // 1.8.5 offline E (in-game 1.8.3 F1): internals look - stock vertex colours kept, drawn with the stock textures on the matte look material
                    bool okL = B25HTools.StockStructure.CheckLook(inst, out string msgL, "cockpit_interior");
                    R("1.8.5 E internals look: every internals submesh carries a stock exterior-structure vertex grey (87-118, alpha 255) and is drawn with <prefix>_structure_look (URP Lit, the stock aircraft_structure_b / _n / _ao textures, neutral light grey, metallic <= 0.15); none left on the reflective stock material",
                        okL, msgL);
                }
                var eye = inst.GetComponentsInChildren<Transform>(true).First(t => t.name == "cockpit_eye");
                R("cockpit view point at cockpit_eye", Vector3.Distance(ac.cockpitViewPoint.position, eye.position) < 0.01f, $"{ac.cockpitViewPoint.position.ToString("F3")}");
                var canopies = (Canopy[])G(ac, "canopies");
                bool StockSeat(Pilot p) { var es = p.transform.Find("EjectionSeat"); return es != null && es.GetComponent<MeshFilter>() != null && AssetDatabase.GetAssetPath(es.GetComponent<MeshFilter>().sharedMesh).Contains("ejectionSeat_PLACEHOLDER")
                        && es.GetComponent<MeshRenderer>().sharedMaterials.Length == 1 && AssetDatabase.GetAssetPath(es.GetComponent<MeshRenderer>().sharedMaterials[0]).Contains("Seats_PLACEHOLDER") && (es.localPosition - new Vector3(0f, 0.0218f, -0.041f)).magnitude < 0.002f; }
                R(EjectionSeats ? (StockCockpitKit ? "crew of 2 (pilot + weapons officer, ejection seats; stock EjectionSeat child under each Pilot, SFB-81 offset)" : "crew of 2 (pilot + weapons officer, ejection seats, figures carry our seats)") : "crew of 2 (pilot + weapons officer, bail-out, figures)", !TwoCrew || (ac.pilots.Length == 2 && ac.pilots.All(p => p != null && (bool)G(p, "ejectionSeat") == EjectionSeats && G(p, "skinnedMeshRenderer") != null
                        && (!EjectionSeats || (StockCockpitKit ? StockSeat(p) : p.GetComponentsInChildren<Transform>(true).Any(t => t.name.StartsWith("cockpit_seat_") && !t.name.EndsWith("_int")))))),
                    string.Join(", ", ac.pilots.Select(p => $"{p.name}@{((UnitPart)G(p, "unitPart"))?.name} exit {p.exitDirection}")));
                R(EjectionSeats ? "canopies: 2 jettison panels (COIN values 50 kg / 4000 N) + entry hatch (stock Canopy)" : "bail-out hatches (stock Canopy)", !TwoCrew || (canopies != null && canopies.Length == (EjectionSeats ? 3 : 2) && canopies.All(c => c != null && c.attachedPart != null && c.ejectionTransform != null && !c.ejectionCollider.enabled)
                        && (!EjectionSeats || canopies.Count(c => c.name.StartsWith("canopy_jettison") && Mathf.Approximately(c.mass, 50f) && Mathf.Approximately(((Vector3)G(c, "ejectionForce")).y, 4000f)) == 2)),
                    canopies == null ? "none" : string.Join(", ", canopies.Select(c => $"{c.name}@{c.attachedPart?.name} {c.mass} kg")));

                if (FormationLights)
                {
                    var nlc = inst.GetComponent<NavLights>(); var nle = ((IEnumerable)G(nlc, "navLights")).Cast<object>().ToList();
                    var strips = nle.Where(ze => { var zr2 = (Renderer)G(ze, "renderer"); return zr2 != null && zr2.name.StartsWith("slimelight_"); }).ToList();
                    var liv = new HashSet<Renderer>(allParts.SelectMany(ap => ((IList)G(G(ap, "damageMaterial"), "renderers")).Cast<Renderer>()));
                    R("formation lights: 8 slimelight strips, NavLights Auto, litMaterial slimelight_on, unlit light_green_off, none in a livery list", strips.Count == 8 && strips.All(ze => AssetDatabase.GetAssetPath((Material)G(ze, "litMaterial")).Contains("slimelight_on") && G(ze, "controlState").ToString() == "Auto"
                        && ((Renderer)G(ze, "renderer")).sharedMaterials.All(m => AssetDatabase.GetAssetPath(m).Contains("light_green_off")) && !liv.Contains((Renderer)G(ze, "renderer")) && G(ze, "part") != null),
                        string.Join(",", strips.Select(ze => ((Renderer)G(ze, "renderer")).name + "@" + ((Object)G(ze, "part"))?.name)));
                }
                // ---- HUD, screens, cockpit animation
                R(JetThrottleHUD ? "HUD: HUDExtras = stock Multirole1_HUDExtras (afterburner throttle regions = boost from 0.90)" : "HUD: HUDExtras = stock COIN_HUDExtras", !StockHUDExtras || (prm.HUDExtras != null && AssetDatabase.GetAssetPath(prm.HUDExtras).Contains(JetThrottleHUD ? "Multirole1_HUDExtras" : "COIN_HUDExtras")), prm.HUDExtras ? AssetDatabase.GetAssetPath(prm.HUDExtras) : "none");
                var ck = inst.GetComponentInChildren<global::Cockpit>(true);
                var tacR = ck == null ? null : (Renderer)G(ck, "tacScreenRender");
                var tcR = tc == null ? null : (Renderer)G(tc, "targetScreenRenderer");
                R("Cockpit + TargetCam wired like the CI-22 (one tac screen renderer, stock tacScreenDisplay)", ck != null && G(ck, "tacScreenUIPrefab") != null && tacR != null && tacR == tcR && tacR.enabled && AssetDatabase.GetAssetPath(tacR.sharedMaterials[0]).Contains("tacScreenDisplay"),
                    $"tacScreenRender {tacR?.name}");
                var screens = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.gameObject.layer != 3 && r.sharedMaterials.Length > 0 && r.sharedMaterials[0] != null && (AssetDatabase.GetAssetPath(r.sharedMaterials[0]).Contains("tacScreenDisplay") || AssetDatabase.GetAssetPath(r.sharedMaterials[0]).Contains("targetCamDisplay"))).ToList();
                var auxOff = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.gameObject.layer != 3 && (r.name == "mfd_left" || r.name == "mfd_wso") && r.sharedMaterials.All(m => AssetDatabase.GetAssetPath(m).Contains("Touchscreen_off"))).ToList();
                var tacMeshes = screens.Where(r => r.GetComponent<MeshFilter>().sharedMesh.subMeshCount == 2).ToList();
                R(TouchscreenOff ? (WsoScreenTacPage ? "MFDs: 2 wide stock tac screens (pilot + WSO; target video inside the tac page, no stale render texture), Touchscreen_off backing, map >= 95 % of the height + 2 dark aux panes" : "MFDs: 1 wide tac screen (upright side panels, Touchscreen_off backing, map >= 95 % of the height) + 1 wide target camera + 2 dark aux panes") : "4 MFDs: 3 tac screens (upright side panels) + 1 target camera",
                    !MFDScreens || (TouchscreenOff ? screens.Count == 2 && tacMeshes.Count == (WsoScreenTacPage ? 2 : 1) && auxOff.Count == 2 && (!WsoScreenTacPage || screens.All(r => !AssetDatabase.GetAssetPath(r.sharedMaterials[0]).Contains("targetCamDisplay"))) && tacMeshes.All(r => AssetDatabase.GetAssetPath(r.sharedMaterials[1]).Contains("Touchscreen_off") && MapFill(r.GetComponent<MeshFilter>().sharedMesh) >= 0.95f)
                        : screens.Count == 4 && tacMeshes.Count == 3), string.Join(", ", screens.Select(r => r.name)) + "; aux " + string.Join(",", auxOff.Select(r => r.name)) + "; map fill " + string.Join(",", tacMeshes.Select(r => MapFill(r.GetComponent<MeshFilter>().sharedMesh).ToString("F3"))));
                var js = ck == null ? new List<object>() : ((IEnumerable)G(ck, "joysticks")).Cast<object>().ToList();
                var thr = ck == null ? new List<object>() : ((IEnumerable)G(ck, "throttles")).Cast<object>().ToList();
                var pedals = csurf.Where(c => ((GameObject)G(c, "visibleMesh")).name.StartsWith("cockpit_rudder_pedals")).ToList();
                string MeshOf(object e) { var t = (Transform)G(e, "transform"); var mf = t == null ? null : t.GetComponentInChildren<MeshFilter>(true); return mf == null ? "" : AssetDatabase.GetAssetPath(mf.sharedMesh); }
                R(StockCockpitKit ? (StockThrottleMesh ? "cockpit animated: 2 stock SFB-81 sticks (sfb_joystick, Joystick range 12), 1 stock throttle (sfb_throttle, rotation 52), " + (RemovePedals ? "no pedals" : "2 pedal bars") : "cockpit animated: 2 stock SFB-81 sticks (sfb_joystick, Joystick range 12), 1 throttle pivot carrying our split lever cockpit_throttle_arm (rotation 52, no stock lever mesh), " + (RemovePedals ? "no pedals" : "2 pedal bars")) : "cockpit animated: 2 side sticks (Joystick), 2 throttle levers, " + (RemovePedals ? "no pedals" : "2 pedal bars"),
                    !CockpitAnimators || (StockCockpitKit ? js.Count == 2 && js.All(j => MeshOf(j).Contains("sfb_joystick_PLACEHOLDER") && Mathf.Approximately((float)G(j, "range"), 12f))
                        && thr.Count == 1 && (StockThrottleMesh ? MeshOf(thr[0]).Contains("sfb_throttle_PLACEHOLDER") : ((Transform)G(thr[0], "transform")).GetComponentsInChildren<MeshFilter>(true).Any(mf => mf.name.StartsWith("cockpit_throttle_arm")) && ((Transform)G(thr[0], "transform")).GetComponent<MeshFilter>() == null)
                        && (bool)G(thr[0], "rotation") && Mathf.Approximately((float)G(thr[0], "range"), 52f) && pedals.Count == (RemovePedals ? 0 : 2)
                        : js.Count == 2 && thr.Count == 2 && pedals.Count == (RemovePedals ? 0 : 2)),
                    $"sticks {string.Join(",", js.Select(j => ((Transform)G(j, "transform"))?.name + ":" + Path.GetFileNameWithoutExtension(MeshOf(j))))}; throttles {string.Join(",", thr.Select(j => ((Transform)G(j, "transform"))?.name + ":" + Path.GetFileNameWithoutExtension(MeshOf(j))))}; pedals {pedals.Count}");
                if (StockCockpitKit)
                {
                    var allT = inst.GetComponentsInChildren<Transform>(true);
                    var custom = allT.Where(t => t.name.StartsWith("cockpit_seat_") || t.name.StartsWith("quadrant_throttle_") || t.name.StartsWith("ejection_rail_")).Select(t => t.name).ToList();
                    var stockCtl = allT.Where(t => (t.name == "stick_L" || t.name == "stick_R" || t.name == "cockpit_throttle") && t.GetComponent<MeshFilter>() != null).ToList();
                    var rotBad = stockCtl.Where(t => Quaternion.Angle(t.rotation, inst.transform.rotation) > 0.5f).Select(t => t.name).ToList();
                    R("no custom seat / stick / throttle geometry left; stick_L/R + cockpit_throttle carry only the stock meshes, upright in the aircraft frame",
                        custom.Count == 0 && stockCtl.Count == (StockThrottleMesh ? 3 : 2) && stockCtl.All(t => AssetDatabase.GetAssetPath(t.GetComponent<MeshFilter>().sharedMesh).Contains("_PLACEHOLDER")) && rotBad.Count == 0,
                        $"custom {string.Join(",", custom)}; stock {string.Join(",", stockCtl.Select(t => t.name + ":" + t.GetComponent<MeshFilter>().sharedMesh.name))}; tilted {string.Join(",", rotBad)}");
                    var cabinR = ((Renderer[])G(ac, "cockpitRenderers")).Where(r => r != null && !r.name.StartsWith("fus_") && !r.name.StartsWith("canopy_")).ToList();
                    var badTex = new List<string>();
                    foreach (var r in cabinR)
                        foreach (var m in r.sharedMaterials.Where(m => m != null))
                        {
                            var texs = m.GetTexturePropertyNames().Select(n => m.GetTexture(n)).Where(t => t != null).Select(t => t.name).ToList();
                            if (texs.Any(t => t.StartsWith("ga25x_") || t.StartsWith("b25h_")) && texs.Any(t => t.Contains("cockpit_b") || t.Contains("rubber") || t.Contains("interior_b")) || m.name.Contains("prop_tip") || m.name.Contains("rubber")) badTex.Add(r.name + ":" + m.name);
                        }
                    var ckT = allT.First(t => t.name == "cockpit_interior");
                    var ckInt = ckT.GetComponent<MeshFilter>().sharedMesh;
                    bool vcol = !StockCabinStructure || (ckInt.colors32.Length == ckInt.vertexCount && ckInt.colors32.Any(c => c.r == 56 && c.g == 56 && c.b == 56));
                    R("cabin: no crosshatch / rubber / interior tile, no yellow on any cockpit renderer; tub on the stock aircraft_structure with vertex colour 56",
                        badTex.Count == 0 && vcol && (!StockCabinStructure || ckT.GetComponent<MeshRenderer>().sharedMaterials.Any(m => AssetDatabase.GetAssetPath(m).Contains("aircraft_structure_PLACEHOLDER"))),
                        $"{cabinR.Count} cabin renderers; bad {string.Join(",", badTex.Take(8))}; vertex colours {vcol}");
                }

                // ---- AI + definition
                var app = inst.GetComponentInChildren<AutopilotPlane>(true);
                {   // 1.8.0: AI strafes ground targets with the 76 mm and the 20 mm like the stock A-19 (Gun30mm_Rotary minAltitude 0), floor 300 kept
                    var fixedGuns = inst.GetComponentsInChildren<Gun>(true).Where(g => g.info != null && g.info.boresight).ToList();
                    R("1.8.0/1.8.1 AI uses the 76 mm and the 20 mm on ground targets (boresight infos, minAltitude 0, maxRange <= 3000 as the stock A-19 Gun30mm_Rotary / Gun20mm_Pod 2000); AI floor 120 (1.8.1 AIFloorStock181) or 300",
                        (FixedGunsAirOnlyForAI && CannonAirOnlyForAI) || (fixedGuns.Count >= 3 && fixedGuns.All(g => g.info.targetRequirements.minAltitude == 0f && (!GunRangeStock181 || g.info.targetRequirements.maxRange <= 3000f)) && Mathf.Approximately(prm.minimumRadarAlt, AIFloorStock181 ? 120f : 300f)),
                        string.Join(", ", fixedGuns.Select(g => $"{g.name}: {g.info.name} minAlt {g.info.targetRequirements.minAltitude} maxRange {g.info.targetRequirements.maxRange}")) + $"; minRadarAlt {prm.minimumRadarAlt}");
                    // 1.8.3D: the 76 mm outscores AGM1 inside 3.6 km and the rockets / bombs at every range (ChooseHQTarget)
                    var c76 = fixedGuns.FirstOrDefault(g => g.info != null && g.info.name == "GA25X_76mm_info");
                    R("1.8.3D AI ground-weapon priority: 76 mm info antiSurface 1.2 (> AGM1 0.643 inside 3.6 km; halved 0.60 > rockets 0.55 / bombs 0.51, < AGM1 at 3.6-12 km), boresight, maxRange 3000, minAltitude 0; floor 120",
                        !CannonGroundPriority183D || (c76 != null && Mathf.Approximately(c76.info.effectiveness.antiSurface, 1.2f) && c76.info.boresight && Mathf.Approximately(c76.info.targetRequirements.maxRange, 3000f)
                            && c76.info.targetRequirements.minAltitude == 0f && Mathf.Approximately(prm.minimumRadarAlt, 120f)),
                        c76 == null ? "76 mm gun not found" : $"{c76.info.name}: antiSurface {c76.info.effectiveness.antiSurface} antiAir {c76.info.effectiveness.antiAir} maxRange {c76.info.targetRequirements.maxRange}");
                }
                R("AI/flight parameters (g 5, 164 m/s, take-off speed / 350 m, floor 300 m / 1.8.1 120 m)", Mathf.Approximately(prm.aircraftGLimit, 5f) && Mathf.Approximately(prm.maxSpeed, 164f) && Mathf.Approximately(prm.takeoffDistance, 350f) && Mathf.Approximately(prm.takeoffSpeed, StolFlaps ? 44f : 47f) && (!GunshipAITuning || prm.minimumRadarAlt >= (AIFloorStock181 ? 120f : 300f)),
                    $"gLimit {prm.aircraftGLimit}, maxSpeed {prm.maxSpeed}, takeoff {prm.takeoffSpeed}/{prm.takeoffDistance}, minRadarAlt {prm.minimumRadarAlt}, turningRadius {prm.turningRadius}, preventInverted {(app ? G(app, "preventInvertedFlight") : "-")}");
                {   // 1.8.6 offline F: nose leg on dirt (tools/flightmodel/nose_soft_ground.py)
                    var lgs186 = inst.GetComponentsInChildren<LandingGear>(true).ToList();
                    var nose186 = lgs186.FirstOrDefault(g => g.name == "gear_nose_leg");
                    var mains186 = lgs186.Where(g => g.name.StartsWith("gear_main_")).ToList();
                    R("1.8.6F nose leg contactArea 0.05 (dirt drag only; CAS1 template 0.02); spring 850000 / damper 52000 / maxCompression 0.40 as 1.8.5; mains unchanged (0.04, 980000, 0.45)",
                        !NoseContact186F || (nose186 != null && Mathf.Approximately((float)G(nose186, "contactArea"), NoseContactArea186F) && Mathf.Approximately((float)G(nose186, "springRate"), 850000f)
                            && Mathf.Approximately((float)G(nose186, "dampingRate"), 52000f) && Mathf.Approximately((float)G(nose186, "maxCompression"), 0.40f)
                            && mains186.Count == 2 && mains186.All(g => Mathf.Approximately((float)G(g, "contactArea"), 0.04f) && Mathf.Approximately((float)G(g, "springRate"), 980000f) && Mathf.Approximately((float)G(g, "maxCompression"), 0.45f))),
                        string.Join("; ", lgs186.Select(g => $"{g.name} area {G(g, "contactArea")} k {G(g, "springRate")} c {G(g, "dampingRate")} max {G(g, "maxCompression")}")));
                }
                R("definition: GA25X, rank 2, $33m, RCS 0.40, crew 2, 590 km/h, stall 190, 5 g, 9.6 / 17.5 t", def.jsonKey == JsonKey && prm.rankRequired == 2 && Mathf.Approximately(def.value, 33f) && Mathf.Approximately(def.radarSize, 0.40f) && def.manpower == 2
                    && Mathf.Approximately(def.aircraftInfo.maxSpeed, 590f) && Mathf.Approximately(def.aircraftInfo.stallSpeed, 190f) && Mathf.Approximately(def.aircraftInfo.maneuverability, 5f) && Mathf.Approximately(def.aircraftInfo.maxWeight, 17500f),
                    $"{def.unitName} ({def.code})");
                var sdp = prm.StatusDisplay; var sdc = sdp ? sdp.GetComponent<StatusDisplay>() : null;
                var sdParts = sdc == null ? new List<PartStatusDisplay>() : ((IEnumerable)G(sdc, "statusDisplays")).Cast<PartStatusDisplay>().ToList();
                var partNames = new HashSet<string>(allParts.Select(p => p.name == inst.name ? "GA25X" : p.name));
                R("own damage diagram (one image per part) + own map icon", (!OwnStatusDisplay || (sdp != null && OurAsset(sdp) && partNames.All(n => sdParts.Any(s => s.partImage != null && s.partImage.name == n)))) && (!OwnMapIcon || (def.mapIcon != null && OurAsset(def.mapIcon))),
                    $"{sdParts.Count} part images");

                // ---- references
                var stray = new List<string>();
                foreach (var c in inst.GetComponentsInChildren<Component>(true))
                {
                    if (c == null) { stray.Add("missing script"); continue; }
                    var so = new SerializedObject(c); var it = so.GetIterator(); bool enter = true;
                    while (it.Next(enter))
                    {
                        enter = true;
                        if (it.propertyType != SerializedPropertyType.ObjectReference || it.objectReferenceValue == null) continue;
                        var v = it.objectReferenceValue;
                        Transform t = v is GameObject go ? go.transform : v is Component cc ? cc.transform : null;
                        if (t != null && !EditorUtility.IsPersistent(v) && t.root != inst.transform) stray.Add($"{c.GetType().Name}@{c.name}.{it.propertyPath}");
                    }
                }
                R("no references outside the prefab / no missing scripts", stray.Count == 0, string.Join("; ", stray.Take(10)));
                var jointPairs = new HashSet<(AeroPart, AeroPart)>();
                foreach (var p in allParts) foreach (var j in p.Joints) { jointPairs.Add((p, (AeroPart)j.connectedPart)); jointPairs.Add(((AeroPart)j.connectedPart, p)); }
                var unjoined = new List<string>();
                for (int i = 0; i < allParts.Length; i++) for (int j = i + 1; j < allParts.Length; j++)
                    {
                        var a = allParts[i].GetComponent<MeshCollider>(); var b = allParts[j].GetComponent<MeshCollider>();
                        if (a == null || b == null) continue;
                        var ba = WorldBounds(a); var bb = WorldBounds(b); ba.Expand(-0.02f); bb.Expand(-0.02f);
                        if (ba.Intersects(bb) && !jointPairs.Contains((allParts[i], allParts[j]))) unjoined.Add($"{allParts[i].name}/{allParts[j].name}");
                    }
                R("every overlapping hull pair is jointed", unjoined.Count == 0, string.Join(",", unjoined));
            }
            finally { Object.DestroyImmediate(inst); }

            int w = rows.Max(r => r.name.Length);
            L("CHECK TABLE");
            foreach (var r in rows) L($"  {(r.ok ? "PASS" : "FAIL")}  {r.name.PadRight(w)}  {r.detail}");
            bool all = rows.All(r => r.ok);
            L($"CHECK {(all ? "ALL PASS" : "FAILURES: " + rows.Count(r => !r.ok))}");
            return all;
        }
    }
}
