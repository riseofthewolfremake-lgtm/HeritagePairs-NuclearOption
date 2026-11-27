// Mitsubishi A6M2 Zero Model 21 (Heritage Pairs, first post-release aircraft, jsonKey A6M2): builds the Blueprinter prefab + assets from our
// own procedural model (blender/a6m2) into the family addon folder heritage_pairs/a6m2 (FamilyBuild.cs). Design: docs/a6m2_design.md.
//
// Released in 1.9.15 (user approval 2026-11-27 after testing the r8 dev pack): FamilyBuild.BuildAll builds this aircraft in every build.
// From 2026-11-18 to 1.9.15 it was ship-gated (built only for dev packs; memory new-aircraft-ship-gate, HOW_TO_RELEASE.md "Ship gate").
//
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FamilyBuild.BuildAll family_build              (all seven + pack)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 A6M2Build.BuildOnly a6m2_build     (assets + check, no pack)
//
// Round 1 (design 10): skeleton, airframe, flight model, guns. Every new piece is behind a flag below; the Round-1 defaults are what the
// design asks for. Same rules as NimrodBuild.cs (this file follows its structure; helpers marked "from NimrodBuild.cs" are copies with the
// outputs renamed): stock components are STARTING VALUES copied onto our own objects; stock assets that stay referenced are Blueprinter
// placeholders the game resolves to its own copies. Values: docs/a6m2_design.md 2.2, 5.3; tools/flightmodel/a6m2_fm.py keeps the same.
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
    public static class A6M2Build
    {
        // ------------------------------------------------------------------ paths and identity
        const string ModName = "a6m2";
        const string DisplayName = "A6M2 Zero";
        public const string Folder = FamilyBuild.FamilyRoot + "/a6m2";
        const string RepoModel = @"C:\Users\User\Nuclear Option B-25\assets\model_a6m2\a6m2.fbx";
        const string RepoTextures = @"C:\Users\User\Nuclear Option B-25\assets\textures_a6m2";
        const string RepoTilesNimrod = @"C:\Users\User\Nuclear Option B-25\assets\textures_nimrod";   // our own fal tiles (Nimrod 1.3.0), reused read-only
        const string SrcDir = "Assets/A6M2Source";
        const string DNS = "Assets/Blueprinter/_donotship";
        public const string JsonKey = "A6M2";
        const string LogPath = @"C:\Users\User\nuclearoption-ref\unitylogs\a6m2_check_table.txt";
        public static string lastCheck = "";

        // ------------------------------------------------------------------ round-1 flags (ON = in the build for the live probes; false restores a plainer variant)
        const bool SyncMuzzlesAhead = true;     // Type 97 bullet origins 0.19 m ahead of the blade plane (synchroniser; BulletSim linecasts hit our prop trigger otherwise)
        const bool OwnGunInfos = true;          // own WeaponInfo for the Type 97 and Type 99 (copies of Gun7.5mm / Gun20mm_Pod with our values); false = the stock infos
        const bool StockStructure = true;       // 'structure' submeshes drawn with the stock aircraft_structure look (NimrodBuild 1.8.3)
        const bool OwnTailHookMount = true;     // own hook mount with OUR A-frame (rendered: visible stowed in the belly recess)
        const bool AllHangarTypes = true;       // the Mk I hangar set (design 4)
        const bool KeepFlareEjector = true;
        const bool StockHUDExtras = true;       // COIN_HUDExtras
        const bool CrashImpactDamage = true;    // own ImpactDamage on every part (airframe-build-lessons)
        public const bool InvisibleAirbrake = true;   // 1.9.12 rule (memory airbrake-works-on-landing): stock Airbrake on the root, drag only; plugin widens to < 5 %
        public const float InvisibleAirbrakeDrag = 0.4f, InvisibleAirbrakeOpenSpeed = 1.0f;
        public const int WingSolverIterations = 100;  // memory multipart-wing-joint-solver: every joint OWNED by a wing_* part
        static bool WingSolverOwner(string part) => part.StartsWith("wing_");
        const bool RetractingMains = true;      // inward retraction about the measured axis (design 0.1 #7); false = fixed mains (0.5 deg)
        static readonly float[] WellAotakeDark = { 0.085f, 0.22f, 0.235f };   // r8l: the well ceiling panels (Blender 'well_dark')
        static readonly float[] WellAotake = { 0.17f, 0.42f, 0.44f };   // r8k (r6..r8j: 0.07 / 0.20 / 0.22 - near-black navy under the wing in game)
        const bool InnerWellDoors = true;       // LandingGear.gearDoors: the inner well doors (open 85 deg with the gear down, closed after retraction)
        const bool SplitFlaps = true;           // HighLiftDevice on flap_L/R: visual 60 deg, lift frame 15 deg, deployedArea 1.2 (design 5.3)
        const bool NoNavLights = true;          // period tip lenses only (nimrod-user-review-2)
        // ------------------------------------------------------------------ round-1b flags: fixes from the first in-game run of r1 (study\a6m2\r1_game, MODLOG 2026-11-18 09:30;
        // coordinator: speed first, FM changes allowed for these items only). false = the r1 value (each noted on its constant).
        const bool R1bLoads = true;        // spawn mass 1,985 kg vs design 2,350: the game counts only part masses + fuel + ammo (LandingGear.mass is not added,
                                           // LandingGear.cs:507 only subtracts it on a break; no pilot / oil). + pilot 80 (root), oil + engine accessories 150
                                           // (fus_engine), main gear 40 + 40 (wing_inner), tail wheel 8 (fus_tail): parts 1,641 -> 1,959 kg, spawn ~2,300 kg at 80 % fuel;
                                           // CoM 28.8 % MAC (check rule, 70 % fuel) / 29.3 % (80 %) / 30.4 % (full), r1 29.1 %
        const bool R1bTailGear = true;     // tail wheel lost after a 41 m/s grass run + brake 0.5 with no detach line = LandingGear.BreakWheel (compression >
                                           // maxCompression or grass drag > springRate, LandingGear.cs:620): spring 90k -> 150k, damper 7k -> 9k, break 0.20 -> 0.22 of 0.24
                                           // (break load 18 -> 33 kN = 14 x the static 2.4 kN, Nimrod 120k / 9k / 0.27 of 0.31), contactArea 0.02 -> 0.05 (B-25H 1.8.6F)
        const bool R1bTakeoff = true;      // tail up from 23 m/s, elevator full up from 33 m/s could not hold it (a6m2_ground.py): FBW takeoffSpeed 32 -> 15
                                           // (B-17G 1.6.5: the FBW holds the attitude from 15 m/s instead of a neutral elevator to 32) + elevator throw 28 -> 32
        const bool R1bTaxiThrust = true;   // taxi break-away at 33 % throttle: thrust at low throttle = throttle x targetAOA (ConstantSpeedProp.cs:654):
                                           // targetAOA 5 -> 8 (Nimrod / FD-32; COIN 7), bladeEfficiency 0.20 -> 0.24: T/W at 15 % 0.08 -> 0.15 (Nimrod 0.14);
                                           // level speed unchanged in the model (527 km/h at 4,550 m, rpm-limited), SL climb 19.7 -> 20.3 m/s (user Q2: speed wins, climb accepted)
        // ------------------------------------------------------------------ round 2 / 3 (design 2, 3; coordinator brief 2026-11-18)
        const bool Round2Stores = true;    // No.6 60 kg bombs on our wing racks ("Bombs" set); false = no Bombs / Special sets (the r1b station list)
        const bool Kamikaze = true;        // 250 kg special-attack charge, Event Content ("Special" set, precluding Bombs); needs Round2Stores
        const bool OwnWeaponIcons = true;  // own HUD icons for all four weapons (assets/ui/a6m2_icon_*.png, blender/a6m2/make_weapon_icons_a6m2.py)
        const bool OwnGunSounds = true;    // Type 97: the stock 12.7 mm set pitched x1.15 (the Nimrod Vickers keeps it at x1); Type 99: one source, one shot per round, x0.9
        public const float NO6Mass = 60f, NO6Yield = 48f;               // stock unguided rule blastYield = 0.8 x mass (NimrodBuild 1.4.0)
        public const float TokkoMass = 250f, TokkoYield = 200f, TokkoTimeFuse = 0.02f;   // design 3.4: yield 200 = the BlastFrag ceiling; 0.02 s fuse = bursts within ~4 m
        // ------------------------------------------------------------------ round 4 (design 8; coordinator brief 2026-11-18)
        const bool PeriodCockpit = true;   // our period cockpit (blender/a6m2/a6m2_cockpit.py): dials on the gauge atlas, Type 98 sight, breeches, seat,
                                           // stick (Cockpit.Joystick), throttle (Cockpit.Throttle); every cockpit_* / gauge_* mesh copied onto the cockpit layer
        const bool SlidingHood = true;     // the hood is a stock Canopy: it slides aft (a hinge 8 m below the hood: 3.6 deg = 0.50 m, 16 mm drop) and is
                                           // jettisoned before the bail-out (Aircraft.EjectionSequence); r1-r3 bailed out through the glass (canopies empty)
        public const float HoodSlide = 0.50f, HoodPivotDrop = 8.0f;
        // ------------------------------------------------------------------ r4b: fixes from the r1b flight test (MODLOG 2e5c376; coordinator brief; top speed untouched)
        const bool R4bPitch = true;   // full aft stick capped at AoA 6-7 deg at 40 m/s EAS, tail up on the roll, flat 178 km/h lift-off: the game's elevator does
                                      // 0.4 x the model's (fit, tools/flightmodel/a6m2_ground.py). Stab wingArea 0.96 -> 0.63 (tail_k 0.33), elevator 0.56 -> 1.12 per
                                      // side: model (game-calibrated) full aft trims to AoA 15 (> limiter 14.5) at 40 m/s EAS, static margin 16 % MAC, tail-low
                                      // lift-off 148 km/h. AeroPart drag of a surface is dragCoef x q x wingArea near zero AoA: the area swap is drag-neutral
        const bool R4bRoll = true;    // roll 89 / 109 / 108 deg/s at 430 / 514 / 596 km/h, no heaviness: the FBW rate loop (target maxRollAngularVel 6, unclamped
                                      // before the lerp, ControlsFilter.cs:287-297) drove full aileron at every speed. maxRollAngularVel 4, maxRollSpeed 1.0,
                                      // rollTightness 0.5: tools/flightmodel/a6m2_roll.py peaks 80 deg/s at 400 km/h, 59 at 600
        const bool R4bFlaps = true;   // flaps 0.39-0.45 at 40 m/s EAS at 4-5 km: HighLiftDevice schedules on aircraft.speed = TAS (HighLiftDevice.cs:84), 51 m/s
                                      // there. speedDeployed 45 -> 50, speedRetracted 55 -> 60 (TAS): full flap at the stall speed up to ~5 km
        public const float StabArea = R4bPitch ? 0.63f : 0.96f, ElevArea = R4bPitch ? 1.12f : 0.56f;
        public const float FbwMaxRollAngVel = R4bRoll ? 4f : 6f, FbwMaxRollSpeed = R4bRoll ? 1.0f : 1.92f, FbwRollTightness = R4bRoll ? 0.5f : 1f;
        const bool ZeroFlares = false;     // r8 (user review 1): every historical aircraft of the pack carries 48 flares (B-25H, Nimrod, B-17G); r1-r7 had 0
        // ------------------------------------------------------------------ r8 (user review 1 of r7b, 2026-11-19)
        // r8c cockpit atlas (coordinator r8c item 3: the cockpit read uniformly lit pale sage; WT is darker and grimier low down): the faces the
        // pilot can see carry a third UV set 'ckatlas' (UV2, blender/a6m2/a6m2_ck_atlas.py); they move to ONE material A6M2_ckatlas = URP Lit with
        // a baked base / normal / metallic-smoothness / occlusion set on UV0 = UV2, the exact form of every stock cockpit material (SFB_cockpit,
        // COIN_cockpit, smallFighter1_cockpit ...: _BaseMap, _BumpMap, _MetallicGlossMap, _OcclusionMap, keywords _METALLICSPECGLOSSMAP _NORMALMAP
        // _OCCLUSIONMAP; study/a6m2/r8c/ckmat.py). AO + grime + wear + frame rivets: blender/a6m2/textures/bake_ck_atlas_a6m2.py. false = r8b tiles.
        public const bool R8cCockpitAtlas = true;
        static readonly string[] CkAtlasMats = { "interior", "ck_dark", "ck_panel", "ck_gun", "gear", "ck_black", "ck_leather", "ck_blue", "ck_wood", "ck_white" };
        public const bool R8CockpitCanopy = true;  // cockpit view: the exterior canopy hidden (exteriorRenderers), the ck canopy (WT cockpit-model stations, own
                                                   // mesh ckcanopy_fixed / ckcanopy_hood) on the cockpit layer; every cockpit-layer glass = faint glass_ck (B-25H 1.8.1
                                                   // lesson: COIN_glass_int darkens the view - the r7b 'opaque black square' sight)
        public const bool R8SightGlass = true;     // Type 98 reflector on its own faint tinted transparent material (A6M2_sightglass, alpha 0.12)
        public const bool R8WingFold = true;       // folding tips: wing_fold_L/R render under a hinge pivot (wing_fold_X_hinge, local X = fold axis, + = tip up);
                                                   // the plugin (A6M2WingFold.cs, config [A6M2] WingFold) folds them on a ground spawn and unfolds them as the stock
                                                   // RotorShaft does for rotor blades (RotorShaft.cs:383-466). No stock fixed-wing fold component exists in 0.34.6.
        public const float WingFoldDeg = 90f;

        // ------------------------------------------------------------------ numbers (design 5.3; tools/flightmodel/a6m2_fm.py)
        public const float EnginePower = 650e3f;      // W (TurbineEngine maxPower); F1 settles it
        public const float EngineRpm = 2550f;
        public const float PropRpm = 1753f;          // 2,550 x 0.6875 reduction
        public const float BladeLength = 1.45f, HubRadius = 0.20f;
        public const float BladeEfficiency = R1bTaxiThrust ? 0.24f : 0.20f, PropTargetAoA = R1bTaxiThrust ? 8f : 5f, PropMoI = 35f;
        public const float WingIncidence = 1.5f, TipIncidence = 1.0f, StabIncidence = 0f;
        public const float AlphaLimiter = 14.5f;     // limiter + incidence = CLmax angle 16 (airframe-build-lessons)
        const float FuelKg = 384f, FuelFusKg = 104f, FuelWingKg = 140f;   // 518 L: fuselage 104 + wings 2 x 140 (design 7.1)
        const float SpawnLift = 0.03f;
        public const float SpawnForward = 1.35f;     // LiftSpawn1911 check: 0.7 (Mk I) left the rudder 0.32 m short of the Annex backstop margin; probe C1 re-measures
        const float FlapVisualDeg = 60f, FlapLiftDeg = 15f, FlapDeployedArea = 1.2f, FlapSpeedDeployed = R4bFlaps ? 50f : 45f, FlapSpeedRetracted = R4bFlaps ? 60f : 55f;
        // Type 97 7.7 mm (design 2.2)
        public const float T97Rate = 650f; public const int T97Rounds = 500;
        // r8n (user, r8m in game: only ONE Type 97 ever showed fire, R for BDF / L for PALA): Gun.SpawnBullet (Gun.cs 609-634) fires every muzzle each shot
        // but steps ONE tracerSeed per muzzle (tracerSeed++; > tracerRatio -> tracer); Awake seeds it Random.Range(0, 6). Two muzzles + ratio 4 (even)
        // put every tracer on the same muzzle for the whole sortie (seed parity, which follows the map / faction draw order). The other gun fired
        // invisibly. An odd ratio (stock 12.7 mm / FD-32 = 5) alternates the tracers L, R, L, R: 1 tracer per 5 rounds on each barrel.
        public const int T97TracerRatio = 5;
        // Type 99-1 20 mm
        public const float T99Rate = 520f; public const int T99RoundsPerGun = 60;
        public static bool T99FireSoundFix = true;     // r6: see Weapons(); W1 in game: 0 rounds fired before this fix
        // r6 (AI take-off / landing vs the r4b figures): AircraftParameters.takeoffSpeed drives the AI rotation (pull from 0.7 x, AIPilotTakeoffState.cs:97 / 137)
        // and the AI landing speed (AIPilotCombatModes.cs:389 LandingSpeed = takeoffSpeed; AIPilotShortLandingState approach lerp). r4b model: tail-low
        // lift-off 148 km/h = 41 m/s, stall 120 km/h = 33 m/s. 36 m/s put the AI approach at 1.09 x stall; 41 m/s = 1.24 x stall, rotation from 29 m/s.
        public static bool R6AiSpeeds = true; public const float AiTakeoffSpeedR6 = 41f;
        public static bool HoodCanopyOnEject = true;   // r7: Canopy component on the ejection transform (hood centre), not on the 8 m slide hinge
        public static bool PropTipStripes = true;      // r7: red tip stripes painted through the blade's own UV (one material, one renderer per blade)
        // ground stack (Mk I / FD-32 accepted values, design 6)
        const float TailAligning = 8f, TailSteeringLock = -40f;
        const float MainGearFriction = 0.8f, MainBrakeShare = 0.25f, GripFriction = 0.20f, BrakedRolling = 0.20f, GripRolling = 0f;
        const bool SplitMainGear = true, MainCastor = true;
        const float MainCastorRange = 6f, MainCastorAlign = 5f;
        const float GearMainK = 200000f, GearMainC = 20000f, GearMainMaxComp = 0.35f, GearMainTravel = 0.40f;
        const float GearTailK = R1bTailGear ? 150000f : 90000f, GearTailC = R1bTailGear ? 9000f : 7000f, GearTailMaxComp = R1bTailGear ? 0.22f : 0.20f, GearTailTravel = 0.24f;
        const float GearTailContactArea = 0.05f;     // R1bTailGear (CAS1 gear_F template 0.02)
        public const float FbwTakeoffSpeed = R1bTakeoff ? 15f : 32f, ElevatorThrow = R1bTakeoff ? 32f : 28f;
        public const int FlareCount = ZeroFlares ? 0 : 48;   // r8: 48 as B-25H / Nimrod / B-17G
        const float MainGearDrag = 0.12f;            // per leg, extended (design 5.3: ~0.25 total)
        const float MetalImpactG = 30f, MetalImpactMult = 1f;

        static readonly BindingFlags BF = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        // ------------------------------------------------------------------ part table (design 5.3 areas; masses = a6m2_spec.MASSES)
        enum Lift { Own, Wing, Stab, Fin, Hinge }
        class PartSpec
        {
            public string name, parent, mesh, template; public float mass, wingArea, dragArea, dihedral, incidence; public int airfoil; public Lift lift; public float joint;
            public PartSpec(string n, string p, string m, string t, float mass, float wa, float da, int af, Lift l, float j, float dih = 0f, float inc = float.NaN)
            { name = n; parent = p; mesh = m; template = t; this.mass = mass; wingArea = wa; dragArea = da; airfoil = af; lift = l; joint = j; dihedral = dih; incidence = inc; }
        }
        // airfoils: 0 wing, 1 tail / body, 2 aileron, 3 elevator. Areas per side; wing total 22.47 m^2 (stub: a6m2_fm.py).
        static List<PartSpec> Parts()
        {
            var l = new List<PartSpec>
            {
                new PartSpec("A6M2",       null,         "fus_center", "COIN:COIN",       R1bLoads ? 240 : 160, 2.91f, 0.05f, 0, Lift.Wing, 0, 0f),        // centre section on the root
                new PartSpec("fus_engine", "A6M2",       "fus_engine", "COIN:fuselage",   R1bLoads ? 895 : 745, 0.30f, 0.03f, 1, Lift.Own, 90000),
                new PartSpec("prop",       "fus_engine", null,         "COIN:propHub",    145, 0.00f, 0.00f, 1, Lift.Own, 20000),
                new PartSpec("fus_rear",   "A6M2",       "fus_rear",   "COIN:tailboom_L",  45, 0.40f, 0.01f, 1, Lift.Own, 50000),
                new PartSpec("fus_tail",   "fus_rear",   "fus_tail",   "COIN:tailboom_L",  R1bLoads ? 42 : 34, 0.10f, 0.01f, 1, Lift.Own, 30000),
                new PartSpec("fin",        "fus_tail",   "fin",        "COIN:vstab1_L",    12, 0.70f, 0.00f, 1, Lift.Fin, 12000),
                new PartSpec("rudder",     "fin",        "rudder",     "COIN:rudder_L",     8, 0.55f, 0.00f, 1, Lift.Hinge, 8000),
            };
            foreach (var s in new[] { "L", "R" })
            {
                l.Add(new PartSpec("wing_inner_" + s, "A6M2",           "wing_inner_" + s, "COIN:wing1_" + s, R1bLoads ? 165 : 125, 3.99f, 0.0f, 0, Lift.Wing, 60000, 5.6f));
                l.Add(new PartSpec("wing_mid_" + s,   "wing_inner_" + s, "wing_mid_" + s,   "COIN:wing2_" + s,  60, 2.78f, 0.0f, 0, Lift.Wing, 45000, 5.6f));
                l.Add(new PartSpec("wing_tip_" + s,   "wing_mid_" + s,   "wing_tip_" + s,   "COIN:wing3_" + s,  14, 0.54f, 0.0f, 0, Lift.Wing, 20000, 5.6f, TipIncidence));
                l.Add(new PartSpec("wing_fold_" + s,  "wing_tip_" + s,   "wing_fold_" + s,  "COIN:wing3_" + s,  10, 0.54f, 0.0f, 0, Lift.Wing, 15000, 5.6f, TipIncidence));
                l.Add(new PartSpec("aileron_" + s,    "wing_mid_" + s,   "aileron_" + s,    "COIN:aileron_" + s, 12, 1.19f, 0.0f, 2, Lift.Hinge, 15000));
                l.Add(new PartSpec("flap_" + s,       "wing_inner_" + s, "flap_" + s,       "COIN:flap_" + s,    8, 0.74f, 0.0f, 0, Lift.Hinge, 12000));
                l.Add(new PartSpec("stab_" + s,       "fus_tail",        "stab_" + s,       "COIN:hstab",        12, StabArea, 0.0f, 1, Lift.Stab, 15000));   // r1: 1.92 x 0.5 (no downwash in game); r4b 0.63
                l.Add(new PartSpec("elevator_" + s,   "stab_" + s,       "elevator_" + s,   "COIN:elevator",      5, ElevArea, 0.0f, 3, Lift.Hinge, 10000));   // r4b 1.12 (r1: 0.56)
            }
            return l;
        }

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

        static void L(string s) { log.Add(s); Debug.Log("[B25H] A6M2 " + s); }

        // =================================================================== entry points
        public static void BuildOnly() => BuildAssets();

        public static bool BuildAssets()
        {
            bool ok = false;
            log.Clear(); tpl.Clear(); tplRoots.Clear(); parts.Clear(); partGO.Clear(); aircraft = null; controlsFilter = null; weaponManager = null;
            ckAtlasTris = 0;
            liftNormals.Clear(); generatedMeshes.Clear(); mats.Clear(); ourParticles.Clear(); crew.Clear(); sets.Clear(); gearHinges.Clear();
            hookGO = null; hookMount = null; ammo97 = null; ammo99 = null;
            stores.Clear(); no6Mount = tokkoMount = null; no6Info = tokkoInfo = null; no6Def = tokkoDef = null; no6BombGO = no6MountGO = tokkoBombGO = tokkoMountGO = null; setBombs = setSpecial = -1;
            try
            {
                PrepareFolders();
                contract = LoadContract();
                var model = ImportModel();
                ImportTextures();
                LoadTemplates();
                BuildMaterials();
                root = (GameObject)Object.Instantiate(model);
                root.name = "A6M2";
                BuildPrefab();
                var prefab = SaveEverything();
                DestroyTemplates();
                Object.DestroyImmediate(root);
                AssetDatabase.SaveAssets();
                ok = RunCheck(prefab);
                L($"ASSETS DONE check={(ok ? "PASS" : "FAIL")} folder={Folder}");
            }
            finally
            {
                DestroyTemplates(); if (hookGO) Object.DestroyImmediate(hookGO);
                foreach (var g in new[] { no6BombGO, no6MountGO, tokkoBombGO, tokkoMountGO }) if (g) Object.DestroyImmediate(g);
                File.AppendAllText(LogPath, string.Join("\n", log) + "\n");
            }
            return ok;
        }

        public static void Check()
        {
            log.Clear();
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Folder + "/A6M2.prefab");
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
            File.WriteAllText(LogPath, $"A6M2 build {DateTime.Now:s}\n");
        }

        static Newtonsoft.Json.Linq.JObject LoadContract()
        {
            var p = Path.Combine(Path.GetDirectoryName(RepoModel), "a6m2_contract.json");
            if (!File.Exists(p)) throw new Exception("no model contract " + p);
            return Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(p));
        }

        static GameObject ImportModel()
        {
            var dst = SrcDir + "/a6m2.fbx";
            File.Copy(RepoModel, dst, true);
            AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
            var mi = (ModelImporter)AssetImporter.GetAtPath(dst);
            mi.isReadable = true; mi.importAnimation = false; mi.importCameras = false; mi.importLights = false;
            mi.globalScale = 1f; mi.useFileScale = true; mi.importBlendShapes = false;
            mi.SaveAndReimport();
            L($"model imported {dst} ({new FileInfo(RepoModel).Length} bytes)");
            return AssetDatabase.LoadAssetAtPath<GameObject>(dst);
        }

        static readonly string[] SkinMaps = { "b", "n", "m", "ao", "dmg_b", "dmg_n" };
        // tiling materials of the model (blender/a6m2/build_a6m2.py MATERIALS) -> our Nimrod fal tile (texture name) or a plain colour
        static readonly Dictionary<string, (string tile, Color col, float met, float sm)> TileMats = new Dictionary<string, (string, Color, float, float)> {
            { "interior", ("ckgreen", Color.white, 0.05f, 0.3f) }, { "ck_dark", ("ckgreen", new Color(0.62f, 0.64f, 0.62f), 0.05f, 0.25f) }, { "ck_panel", ("ckpanel", Color.white, 0.1f, 0.5f) }, { "ck_gun", ("ckgun", new Color(2.35f, 2.35f, 2.42f), 0.75f, 0.66f) }, { "structure", ("structure", Color.white, 0.5f, 0.45f) },   // r4c: interior / ck_panel = our own A6M2 cockpit tiles (make_ck_tiles_a6m2.py)
            { "metal_dark", ("metal_dark", Color.white, 0.6f, 0.45f) }, { "engine", ("gunmetal", new Color(0.55f, 0.55f, 0.58f), 0.7f, 0.5f) },
            { "exhaust", ("exhaust", Color.white, 0.5f, 0.3f) }, { "gunmetal", ("gunmetal", Color.white, 0.8f, 0.55f) },
            { "gear", ("metal_dark", new Color(0.9f, 0.92f, 0.9f), 0.6f, 0.45f) }, { "rubber", ("rubber", Color.white, 0.0f, 0.2f) },
            { "alu", ("alu", Color.white, 0.85f, 0.6f) } };
        // r8o round 2 (review: the r8o tank was the near-black Nimrod gunmetal tile (mean 0.12) x 0.62 = albedo ~0.075, not the grey metal the
        // renders showed): the fuel / oil tank cells are a PLAIN lit mid-grey metal, no tile (no aircraft_structure pattern either)
        static readonly Color TankAlbedo = new Color(0.55f, 0.56f, 0.52f);
        static readonly List<(string file, string label, string faction, bool both)> Liveries = new List<(string, string, string, bool)>();
        static readonly Dictionary<string, Texture2D> tex = new Dictionary<string, Texture2D>();

        static void LoadLiveryTable()
        {
            Liveries.Clear();
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(Path.Combine(RepoTextures, "a6m2_liveries.json")));
            foreach (var kv in jo)
            {
                var e = (Newtonsoft.Json.Linq.JObject)kv.Value;
                Liveries.Add((Path.GetFileNameWithoutExtension((string)e["texture"]), (string)e["name"], ((string)e["faction"]).ToUpperInvariant().Contains("PALA") ? "PALA" : "BDF", e["both"] != null && (bool)e["both"]));
            }
        }

        static Texture2D ImportTex(string src, string name)
        {
            if (!File.Exists(src)) throw new Exception("missing texture " + src + " (run blender/a6m2/run_a6m2.py)");
            var dst = $"{Folder}/Textures/{name}.png";
            File.Copy(src, dst, true);
            AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
            var ti = (TextureImporter)AssetImporter.GetAtPath(dst);
            bool normal = name.EndsWith("_n");
            bool linear = name.EndsWith("_m") || name.EndsWith("_ao") || normal;
            ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            ti.sRGBTexture = !linear; ti.mipmapEnabled = true; ti.maxTextureSize = 2048;
            ti.textureCompression = TextureImporterCompression.Compressed;
            ti.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(dst);
        }

        static void ImportTextures()
        {
            tex.Clear();
            LoadLiveryTable();
            foreach (var m in SkinMaps) tex["a6m2_skin_" + m] = ImportTex(Path.Combine(RepoTextures, $"a6m2_skin_{m}.png"), "a6m2_skin_" + m);
            foreach (var lv in Liveries) tex[lv.file] = ImportTex(Path.Combine(RepoTextures, lv.file + ".png"), lv.file);
            foreach (var t in TileMats.Values.Select(v => v.tile).Distinct())
            {
                foreach (var sfx in new[] { "b", "n" })
                {
                    var own = Path.Combine(RepoTextures, $"a6m2_tile_{t}_{sfx}.png");          // r4c: own A6M2 tiles first, else our Nimrod tile
                    tex[$"a6m2_tile_{t}_{sfx}"] = ImportTex(File.Exists(own) ? own : Path.Combine(RepoTilesNimrod, $"nimrod_tile_{t}_{sfx}.png"), $"a6m2_tile_{t}_{sfx}");
                }
            }
            if (PeriodCockpit) tex["a6m2_gauges"] = ImportTex(Path.Combine(RepoTextures, "a6m2_gauges.png"), "a6m2_gauges");
            if (R8cCockpitAtlas)
                foreach (var sfx in new[] { "b", "n", "m", "ao" }) tex["a6m2_ck_" + sfx] = ImportTex(Path.Combine(RepoTextures, $"a6m2_ck_{sfx}.png"), "a6m2_ck_" + sfx);
            if (PropTipStripes)
            {
                tex["a6m2_prop_tips"] = ImportTex(Path.Combine(RepoTextures, "a6m2_prop_tips.png"), "a6m2_prop_tips");
                tex["a6m2_prop_tips_m"] = ImportTex(Path.Combine(RepoTextures, "a6m2_prop_tips_m.png"), "a6m2_prop_tips_m");   // r7b: linear (name ends _m)
            }
            L($"textures: {tex.Count} from {RepoTextures} (+ our Nimrod tiles)");
        }

        // =================================================================== stock templates (starting values only)
        static void LoadTemplates()
        {
            foreach (var n in new[] { "COIN", "CAS1", "gun_12.7mm_internal", "gun_20mm_pod", "TailHook_Multirole1", "bomb_125_1", "bomb_125_single", "bomb_250_1", "bomb_250_single", "AIR-2_Genie" })
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
            var paint = new Material(skin) { name = "A6M2_paint" };
            paint.SetTexture("_Basecolor", tex["a6m2_skin_b"]); paint.SetTexture("_Normal", tex["a6m2_skin_n"]);
            paint.SetTexture("_Metallic", tex["a6m2_skin_m"]); paint.SetTexture("_AO", tex["a6m2_skin_ao"]);
            paint.SetTexture("_BasecolorDmg", tex["a6m2_skin_dmg_b"]); paint.SetTexture("_NormalDmg", tex["a6m2_skin_dmg_n"]);
            paint.SetTexture("_Livery", tex["a6m2_skin_b"]);
            paint.SetFloat("_Glossiness", 0.35f); paint.SetFloat("_HitPoints", 100f);
            Save(paint, "paint");
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            if (lit == null) throw new Exception("URP Lit shader not found");
            foreach (var kv in TileMats)
                Save(Tiled(LitMat(lit, "A6M2_" + kv.Key, kv.Value.col, kv.Value.met, kv.Value.sm), $"a6m2_tile_{kv.Value.tile}_b", $"a6m2_tile_{kv.Value.tile}_n"), kv.Key);
            Save(LitMat(lit, "A6M2_tank", TankAlbedo, 0.35f, 0.40f), "tank");   // r8o round 2: plain mid-grey metal (see TankAlbedo)
            Save(LitMat(lit, "A6M2_well", new Color(WellAotake[0], WellAotake[1], WellAotake[2]), 0.1f, 0.4f), "well");   // r8k: lighter aotake (game r8j: wells read near-black navy in the wing's shade; WT wells read mid teal)
            Save(LitMat(lit, "A6M2_well_dark", new Color(WellAotakeDark[0], WellAotakeDark[1], WellAotakeDark[2]), 0.1f, 0.3f), "well_dark");   // r8l: well ceiling between the ribs (darker recesses)
            Save(LitMat(lit, "A6M2_chrome", new Color(0.80f, 0.81f, 0.82f), 1.0f, 0.85f), "chrome");
            Save(LitMat(lit, "A6M2_hub", new Color(0.55f, 0.56f, 0.54f), 0.5f, 0.5f), "hub");
            Save(LitMat(lit, "A6M2_hook", new Color(0.20f, 0.20f, 0.21f), 0.6f, 0.5f), "hook");
            Save(LitMat(lit, "A6M2_hookyellow", new Color(0.80f, 0.62f, 0.08f), 0.1f, 0.5f), "hookyellow");
            Save(LitMat(lit, "A6M2_spinner", new Color(0.75f, 0.76f, 0.78f), 0.85f, 0.7f), "spinner");
            {   // r7: tip stripes on the ONE blade material (texture on the blade's radial livery UV, build_a6m2.prop_tip_uvs)
                var pm = LitMat(lit, "A6M2_prop", new Color(0.58f, 0.59f, 0.60f), 0.8f, 0.45f);   // r8b: duller natural metal
                if (PropTipStripes)
                {
                    pm.SetTexture("_BaseMap", tex["a6m2_prop_tips"]); pm.SetTexture("_MainTex", tex["a6m2_prop_tips"]);
                    // r7b: the stripes are paint, not metal: per-texel metallic (R) / smoothness (A) map, else metallic 0.8 hides the red albedo
                    pm.SetTexture("_MetallicGlossMap", tex["a6m2_prop_tips_m"]); pm.EnableKeyword("_METALLICSPECGLOSSMAP");
                    pm.SetFloat("_Smoothness", 1f); pm.SetFloat("_Metallic", 1f); pm.SetFloat("_SmoothnessTextureChannel", 0f);
                }
                Save(pm, "prop");
            }
            Save(LitMat(lit, "A6M2_navred", new Color(0.85f, 0.08f, 0.06f), 0f, 0.9f), "navred");     // r8b: lens colours, not near-black
            Save(LitMat(lit, "A6M2_navgreen", new Color(0.10f, 0.72f, 0.55f), 0f, 0.9f), "navgreen");
            Save(LitMat(lit, "A6M2_wire", new Color(0.05f, 0.05f, 0.05f), 0.5f, 0.5f), "wire");
            Save(LitMat(lit, "A6M2_ck_black", new Color(0.055f, 0.055f, 0.058f), 0.2f, 0.45f), "ck_black");   // r8b: dark grey
            Save(LitMat(lit, "A6M2_ck_leather", new Color(0.13f, 0.08f, 0.05f), 0f, 0.35f), "ck_leather");     // r8b
            Save(LitMat(lit, "A6M2_ck_blue", new Color(0.12f, 0.32f, 0.62f), 0.1f, 0.6f), "ck_blue");         // r8b
            Save(LitMat(lit, "A6M2_bomb", new Color(0.16f, 0.17f, 0.16f), 0.3f, 0.45f), "bomb");           // round 2 stores
            if (PeriodCockpit)
            {
                var gm = LitMat(lit, "A6M2_gauges", Color.white, 0f, 0.55f);
                gm.SetTexture("_BaseMap", tex["a6m2_gauges"]); gm.SetTexture("_MainTex", tex["a6m2_gauges"]);
                Save(gm, "gauges");
                var rt = LitMat(lit, "A6M2_reticle", new Color(1f, 0.45f, 0.10f), 0f, 0.5f);
                rt.EnableKeyword("_EMISSION"); rt.SetColor("_EmissionColor", new Color(2.2f, 0.9f, 0.18f));
                rt.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
                Save(rt, "reticle");
                Save(LitMat(lit, "A6M2_ck_wood", new Color(0.26f, 0.13f, 0.06f), 0f, 0.5f), "ck_wood");   // r8b: dark-brown wood
                Save(LitMat(lit, "A6M2_ck_white", new Color(0.82f, 0.80f, 0.74f), 0f, 0.5f), "ck_white");          // r6: lever knobs
            }
            Save(LitMat(lit, "A6M2_bombband", new Color(0.62f, 0.08f, 0.05f), 0.1f, 0.5f), "bombband");
            Save(LitMat(lit, "A6M2_screen", Color.black, 0f, 0.5f), "screen");
            Save(new Material(Asset<Material>("Material/COIN_glass_PLACEHOLDER.mat")) { name = "A6M2_glass" }, "glass");
            Save(new Material(Asset<Material>("Material/COIN_glass_int_PLACEHOLDER.mat")) { name = "A6M2_glass_int" }, "glass_int");
            {   // r8: cockpit-layer glass = faint transparent Lit (B25H_glass_ck / B17G pattern, a copy of the stock prop-disc material) and the Type 98 reflector
                var gck = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "A6M2_glass_ck" };
                gck.SetTexture("_BaseMap", null); gck.SetTexture("_MainTex", null);
                gck.SetColor("_BaseColor", new Color(0.86f, 0.92f, 0.97f, 0.06f)); gck.SetColor("_Color", new Color(0.86f, 0.92f, 0.97f, 0.06f));
                gck.SetFloat("_Smoothness", 0.95f); gck.SetFloat("_Cull", 0f);
                gck.SetTexture("_OcclusionMap", null); gck.DisableKeyword("_OCCLUSIONMAP");
                Save(gck, "glass_ck");
                var sg = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "A6M2_sightglass" };
                sg.SetTexture("_BaseMap", null); sg.SetTexture("_MainTex", null);
                sg.SetColor("_BaseColor", new Color(0.80f, 0.93f, 0.86f, 0.12f)); sg.SetColor("_Color", new Color(0.80f, 0.93f, 0.86f, 0.12f));
                sg.SetFloat("_Smoothness", 0.95f); sg.SetFloat("_Cull", 0f);
                sg.SetTexture("_OcclusionMap", null); sg.DisableKeyword("_OCCLUSIONMAP");
                Save(sg, "sightglass");
            }
            var disc = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "A6M2_propdisc" };
            var bp = $"{Folder}/Textures/a6m2_propblur.png";
            File.Copy(Path.Combine(RepoTextures, "a6m2_propblur.png"), bp, true); AssetDatabase.ImportAsset(bp, ImportAssetOptions.ForceUpdate);
            var bti = (TextureImporter)AssetImporter.GetAtPath(bp); bti.alphaIsTransparency = true; bti.wrapMode = TextureWrapMode.Clamp; bti.SaveAndReimport();
            var blur = AssetDatabase.LoadAssetAtPath<Texture2D>(bp);
            disc.SetTexture("_BaseMap", blur); disc.SetTexture("_MainTex", blur);
            disc.SetTexture("_OcclusionMap", null); disc.DisableKeyword("_OCCLUSIONMAP");
            disc.SetColor("_BaseColor", Color.white); disc.SetColor("_Color", Color.white);
            disc.SetFloat("_Smoothness", 0.15f); disc.SetFloat("_Glossiness", 0.15f); disc.SetFloat("_Cull", 0f);   // r8e: 0.63 gave a pale sky sheen (game r8d sheet_prop_zoom)
            Save(disc, "propdisc");
            if (R8cCockpitAtlas)
            {   // r8c: the stock cockpit material form (URP Lit, unique-UV base / normal / metallic-gloss / occlusion maps)
                var ck = new Material(lit) { name = "A6M2_ckatlas" };
                ck.SetTexture("_BaseMap", tex["a6m2_ck_b"]); ck.SetTexture("_MainTex", tex["a6m2_ck_b"]);
                ck.SetColor("_BaseColor", Color.white); ck.SetColor("_Color", Color.white);
                ck.SetTexture("_BumpMap", tex["a6m2_ck_n"]); ck.SetFloat("_BumpScale", 1f); ck.EnableKeyword("_NORMALMAP");
                ck.SetTexture("_MetallicGlossMap", tex["a6m2_ck_m"]); ck.EnableKeyword("_METALLICSPECGLOSSMAP");
                ck.SetFloat("_SmoothnessTextureChannel", 0f); ck.SetFloat("_Metallic", 1f); ck.SetFloat("_Smoothness", 1f); ck.SetFloat("_GlossMapScale", 1f);
                ck.SetTexture("_OcclusionMap", tex["a6m2_ck_ao"]); ck.SetFloat("_OcclusionStrength", 1f); ck.EnableKeyword("_OCCLUSIONMAP");
                ck.SetFloat("_WorkflowMode", 1f); ck.SetFloat("_Surface", 0f); ck.SetFloat("_Cull", 2f);
                Save(ck, "ckatlas");
            }
            if (StockStructure) mats["structure"] = B25HTools.StockStructure.LookMaterial(Asset<Material>("Material/aircraft_structure_PLACEHOLDER.mat"), Folder, "A6M2");
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
            TakeStores();                     // round 2 / 3: store meshes leave the aircraft before any part / collider is built

            GameObjectUtility.RemoveMonoBehavioursWithMissingScript(root);
            root.AddComponent<Mirage.NetworkIdentity>();
            var rb = root.AddComponent<Rigidbody>();
            EditorUtility.CopySerialized(tpl["COIN"].GetComponent<Rigidbody>(), rb);
            CloneComp(tpl["COIN"].GetComponent<Aircraft>(), root);

            var specs = Parts();
            foreach (var s in specs) MakePartObject(s);
            foreach (var s in specs) MakeAeroPart(s);
            AddJoints(specs);

            var cockpitGO = parts["A6M2"].gameObject;
            controlsFilter = CloneComp(TplComp<ControlsFilter>("COIN:cockpit_F"), cockpitGO);
            weaponManager = CloneComp(TplComp<WeaponManager>("COIN:cockpit_F"), cockpitGO);
            CloneComp(TplComp<AutopilotPlane>("COIN:cockpit_F"), cockpitGO);
            Remap(aircraft); Remap(controlsFilter); Remap(weaponManager);

            ControlSurfaces();
            if (SplitFlaps) Flaps();
            var gears = Gear();
            Engine();
            Weapons();
            Cockpit();
            if (R8WingFold) WingFold();
            RootSystems();
            if (InvisibleAirbrake) AddInvisibleAirbrake(parts["A6M2"], InvisibleAirbrakeDrag, InvisibleAirbrakeOpenSpeed);
            FlyByWire(gears[0]);

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

        // ------------------------------------------------------------------ parts
        static void MakePartObject(PartSpec s)
        {
            GameObject go;
            if (s.name == "A6M2") go = root;
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
                var idf = Fld(ap.GetType(), "impactDamage");
                var id = System.Activator.CreateInstance(idf.FieldType);
                S(id, "threshold", MetalImpactG); S(id, "multiplier", MetalImpactMult);       // all-metal stressed skin
                if (s.name == "rudder") { S(id, "threshold", 0f); S(id, "multiplier", 0f); }  // as every stock rudder (1.9.11)
                idf.SetValue(ap, id);
            }
            // collider = own render meshes (the root also takes the wing centre section and the root fairings)
            var own = new List<MeshFilter>();
            if (s.name == "A6M2") own.AddRange(new[] { "fus_center", "wing_C", "fillet_L", "fillet_R" }.Select(n => TryFind(n)).Where(t => t != null).Select(t => t.GetComponent<MeshFilter>()).Where(m => m != null));   // r8e: wing_C / fillets are unified into fus_center
            else if (s.lift == Lift.Hinge) own.Add(Find(s.name + "_visible").GetComponent<MeshFilter>());
            else if (s.mesh != null) own.Add(go.GetComponent<MeshFilter>());
            if (own.Count > 0)
            {
                var mc = go.AddComponent<MeshCollider>();
                mc.sharedMesh = BakeCollider(go.transform, s.name + "_col", own.ToArray());
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
                    float inc = s.lift == Lift.Wing ? (float.IsNaN(s.incidence) ? WingIncidence : s.incidence) : StabIncidence;
                    q = Quaternion.AngleAxis(-inc, q * Vector3.right) * q;
                }
                ln = NewGO(s.name + "_liftNormal", go.transform, go.transform.position, q).transform;
                liftNormals[s.name] = ln;
            }
            S(ap, "liftNormal", ln);
            // lift point: the quarter chord of the part's lifting mesh (root: the centre section), as a centerOfLift offset from the collider centroid
            Vector3 col = Vector3.zero;
            var liftMesh = s.name == "A6M2" ? TryFind("wing_C")?.GetComponent<MeshFilter>() : own.FirstOrDefault();
            var qcMark = s.name == "A6M2" ? TryFind("wing_C_qc") : null;            // r8e: the unified root marks the centre-section quarter chord
            if (s.wingArea > 0.5f && (liftMesh != null || qcMark != null) && ln != null && go.GetComponent<MeshCollider>() != null)
            {
                Vector3 qc;
                if (liftMesh != null)
                {
                    var b = liftMesh.sharedMesh.bounds;
                    var lePt = liftMesh.transform.TransformPoint(new Vector3(b.center.x, b.center.y, b.max.z));
                    var tePt = liftMesh.transform.TransformPoint(new Vector3(b.center.x, b.center.y, b.min.z));
                    qc = Vector3.Lerp(lePt, tePt, 0.25f);
                }
                else qc = qcMark.position;
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
                solverIterations = WingSolverOwner(owner) ? WingSolverIterations : 6, breakForce = force, breakTorque = force, breakSound = breakSnd };
            void Add(string a, string b, string tensor, float f) { jl[a].Add(J(a, b, tensor, f)); joined.Add((a, b)); joined.Add((b, a)); }
            foreach (var s in specs)
            {
                if (s.parent == null) continue;
                Add(s.name, s.parent, null, s.joint);
                var gp = bySpec[s.parent].parent;
                if (gp != null) Add(s.name, gp, s.parent, s.joint * 0.5f);
            }
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
                    Add(owner, other, other == "A6M2" ? bySpec[owner].parent : other, Mathf.Min(bySpec[a].joint == 0 ? 1e6f : bySpec[a].joint, bySpec[b].joint == 0 ? 1e6f : bySpec[b].joint) * 0.3f);
                    extra++; L($"overlap joint {owner} -> {other}");
                }
            foreach (var s in specs) S(parts[s.name], "joints", jl[s.name].ToArray());
            L($"joints: {jl.Values.Sum(x => x.Count)} total, {extra} anti-overlap");
        }
        static int Depth(Dictionary<string, PartSpec> by, string n) { int d = 0; while (by[n].parent != null) { n = by[n].parent; d++; } return d; }

        // ------------------------------------------------------------------ control surfaces (NimrodBuild sign conventions; probe F2 verifies the sense)
        static void ControlSurfaces()
        {
            foreach (var side in new[] { "L", "R" })
            {
                float sgn = side == "L" ? -1f : 1f;
                CS("aileron_" + side, "COIN:aileron_" + side, 0, 18f * sgn, 0, 70f);
                CS("elevator_" + side, "CAS1:elevator_" + side, -ElevatorThrow, 0, 0, 60f);
            }
            CS("rudder", "CAS1:rudder_L", 0, 0, -25f, 60f);
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

        // ------------------------------------------------------------------ split flaps: HighLiftDevice (B17GBuild pattern) moving the plate 60 deg and a separate lift frame 15 deg
        static readonly Dictionary<string, float> flapSign = new Dictionary<string, float>();
        static void Flaps()
        {
            foreach (var side in new[] { "L", "R" })
            {
                var f = "flap_" + side; var ap = parts[f];
                var hinge = liftNormals[f];                                 // parent of the visible plate, identity local rotation
                var vis = Find(f + "_visible");
                // the plate must swing DOWN: pick the sign of the hinge's local-X rotation that lowers the plate's centre
                var c0 = vis.GetComponent<MeshFilter>().sharedMesh.bounds.center;
                Vector3 Centre(float deg) { hinge.localRotation = Quaternion.Euler(deg, 0, 0); var w = vis.TransformPoint(c0); hinge.localRotation = Quaternion.identity; return w; }
                float sg = Centre(30f).y < Centre(-30f).y ? 1f : -1f;
                flapSign[f] = sg;
                var lf = NewGO(f + "_liftFrame", ap.transform, hinge.position, hinge.rotation);          // the flap's lift normal (rotates 15 deg, not 60)
                S(ap, "liftNormal", lf.transform); liftNormals[f + "_lift"] = lf.transform;
                var h = CloneComp(TplComp<HighLiftDevice>("COIN:flap_L"), ap.gameObject);
                S(h, "aeroPart", ap); S(h, "swingWingController", null);
                S(h, "speedDeployed", FlapSpeedDeployed); S(h, "speedRetracted", FlapSpeedRetracted);
                S(h, "alphaMin", 0f); S(h, "alphaFactor", 0f);
                S(h, "deployedArea", FlapDeployedArea);
                var mpV = NewElem(h, "movingParts");
                S(mpV, "move", false); S(mpV, "rotate", true); S(mpV, "transform", hinge);
                S(mpV, "positionRetracted", Vector3.zero); S(mpV, "positionDeployed", Vector3.zero);
                S(mpV, "anglesRetracted", Vector3.zero); S(mpV, "anglesDeployed", new Vector3(sg * FlapVisualDeg, 0, 0));
                var mpL = NewElem(h, "movingParts");
                S(mpL, "move", false); S(mpL, "rotate", true); S(mpL, "transform", lf.transform);
                S(mpL, "positionRetracted", Vector3.zero); S(mpL, "positionDeployed", Vector3.zero);
                S(mpL, "anglesRetracted", Vector3.zero); S(mpL, "anglesDeployed", new Vector3(sg * FlapLiftDeg, 0, 0));
                SetSeq(h, "movingParts", new[] { mpV, mpL });
                L($"flap {f}: HighLiftDevice plate {sg * FlapVisualDeg} / lift frame {sg * FlapLiftDeg} deg (local X), deployedArea {FlapDeployedArea}, down below {FlapSpeedDeployed} m/s, up above {FlapSpeedRetracted}");
            }
        }

        // ------------------------------------------------------------------ landing gear: two retracting mains (inward, measured axis) + doors; fixed castoring tail wheel
        class GearSpec { public string strut, wheel, part; public float fold, travel, k, c, maxComp, mass, drag; public bool steer, brake; public float diff; public Vector3 axis; }
        static readonly Dictionary<LandingGear, Transform> gearHinges = new Dictionary<LandingGear, Transform>();

        static List<LandingGear> Gear()
        {
            var list = new List<LandingGear>();
            foreach (var s in new[] { "L", "R" })
            {
                var gm = contract["gear"]["main"][s];
                var ax = new Vector3((float)gm["axis_unity"][0], (float)gm["axis_unity"][1], (float)gm["axis_unity"][2]);
                float deg = (float)gm["retract_deg"];
                list.Add(MakeGear(new GearSpec { strut = $"gear_main_{s}_strut", wheel = $"gear_main_{s}_wheel", part = "wing_inner_" + s, fold = RetractingMains ? deg : 0.5f,
                    travel = GearMainTravel, k = GearMainK, c = GearMainC, maxComp = GearMainMaxComp, mass = 40f, drag = MainGearDrag, steer = false, brake = true, diff = s == "L" ? -1f : 1f, axis = ax },
                    "CAS1:gear_" + s + "_sprung", "COIN:wheel_" + s));
            }
            list.Add(MakeGear(new GearSpec { strut = "gear_tail_strut", wheel = "gear_tail_wheel", part = "fus_tail", fold = 0.5f, travel = GearTailTravel, k = GearTailK, c = GearTailC,
                maxComp = GearTailMaxComp, mass = 8f, drag = 0f, steer = true, brake = false, diff = 0f, axis = Vector3.right }, "CAS1:gear_F_sprung", "COIN:wheel_F"));
            return list;
        }

        static LandingGear MakeGear(GearSpec g, string tplGear, string tplWheel)
        {
            var strut = Find(g.strut); var wheel = Find(g.wheel); var part = parts[g.part];
            float r = wheel.GetComponent<MeshFilter>().sharedMesh.bounds.extents.y;
            Vector3 axle = wheel.position;
            // frame: local X = the retraction axis; hinge = identity child, so LandingGear's (fold, 0, 0) euler is a pure rotation about that axis
            var frame = NewGO(g.strut.Replace("_strut", "_frame"), part.transform, strut.position, Quaternion.FromToRotation(Vector3.right, g.axis.normalized));
            var hinge = NewGO(g.strut.Replace("_strut", "_hinge"), frame.transform, strut.position, frame.transform.rotation);
            strut.SetParent(hinge.transform, true);
            var sprung = NewGO(g.strut.Replace("_strut", "_leg"), hinge.transform, strut.position, part.transform.rotation);
            var unsprung = NewGO(g.strut.Replace("_strut", "_unsprung"), sprung.transform, axle, part.transform.rotation);
            wheel.SetParent(unsprung.transform, true);
            var bump = NewGO(g.strut.Replace("_strut", "_bumpstop"), sprung.transform, axle + Vector3.up * (g.travel - r), part.transform.rotation);
            var dust = CopyParticle(TplFind(tplWheel).GetComponent<ParticleSystem>(), unsprung.transform, axle - Vector3.up * r, g.strut + "_dust");
            var tw = TplFind(tplWheel).GetComponents<AudioSource>();
            var a0 = CloneComp(tw[0], wheel.gameObject); var a1 = CloneComp(tw[1], wheel.gameObject);
            var box = sprung.AddComponent<BoxCollider>();
            var sb = strut.GetComponent<MeshFilter>().sharedMesh.bounds;
            box.center = sprung.transform.InverseTransformPoint(strut.TransformPoint(sb.center)); box.size = sb.size; box.enabled = false;
            var lg = CloneComp(TplComp<LandingGear>(tplGear), sprung);
            S(lg, "attachedPart", part); S(lg, "aircraft", aircraft);
            S(lg, "extendedDrag", part.dragArea + g.drag);       // LandingGear.Start takes retractedDrag = the part's own dragArea
            S(lg, "bumpStop", bump); S(lg, "unsprung", unsprung);
            S(lg, "suspensionTravel", g.travel); S(lg, "springRate", g.k); S(lg, "dampingRate", g.c);
            S(lg, "castPoint", bump.transform); S(lg, "wheelRadius", r);
            S(lg, "wheels", new[] { wheel }); S(lg, "axle", unsprung.transform);
            SetSeq(lg, "joints", new object[0]);
            S(lg, "tireNoiseSound", a0); S(lg, "tireSkidSound", a1);
            S(lg, "maxCompression", g.maxComp); S(lg, "mass", g.mass); S(lg, "gearCollider", box);
            S(lg, "gearHinge", hinge.transform); S(lg, "hingeFoldMotion", Vector3.zero);
            // fold sign: the one that takes the wheel to the contract's stowed position
            float fold = g.fold;
            if (g.brake && RetractingMains)
            {
                var side = g.strut.Contains("_L_") ? "L" : "R";
                var up = UnityPos(contract["gear"]["main"][side]["wheel_up"]);
                float Err(float f) { hinge.transform.localRotation = Quaternion.Euler(f, 0, 0); var w = wheel.position; hinge.transform.localRotation = Quaternion.identity; return (w - up).magnitude; }
                fold = Err(g.fold) <= Err(-g.fold) ? g.fold : -g.fold;
                L($"gear {g.strut}: fold {fold:F1} deg puts the wheel {Err(fold) * 1000:F0} mm from the stowed target (other sense {Err(-fold) * 1000:F0} mm)");
            }
            S(lg, "foldDegrees", fold); S(lg, "foldSpeed", 30f);
            S(lg, "strutRotationTransform", null); S(lg, "strutRotation", 0f);
            SetSeq(lg, "movingParts", new object[0]);
            S(lg, "steering", g.steer); S(lg, "braked", g.brake);
            S(lg, "steeringLock", g.steer ? TailSteeringLock : 0f);
            if (g.brake) { S(lg, "frictionCoef", MainGearFriction); S(lg, "response", 1f); }
            if (!g.brake && R1bTailGear) S(lg, "contactArea", GearTailContactArea);
            S(lg, "steeringSpeed", g.steer ? 60f : 0f); S(lg, "aligningStrength", g.steer ? TailAligning : 0f);
            S(lg, "differentialBrakeFactor", g.diff);
            S(lg, "dust", dust);
            var doors = new List<LandingGear.GearDoor>();
            if (g.brake && InnerWellDoors)
            {
                var side = g.strut.Contains("_L_") ? "L" : "R";
                var hb = DoorHinge(Find($"gear_door_{side}"), contract["gear"]["main"][side]["door"]);
                doors.Add(new LandingGear.GearDoor { transform = hb.Item1, closedAngle = Vector3.zero, openAngle = new Vector3(0, 0, hb.Item2) });
            }
            S(lg, "gearDoors", doors);
            gearHinges[lg] = hinge.transform;
            L($"gear {g.strut}: r={r:F3} axle={axle.ToString("F3")} travel={g.travel} k={g.k} fold={fold} steer={g.steer} brake={g.brake} part={part.name} doors={doors.Count}");
            if (g.brake && SplitMainGear) GripGear.Add(lg, MainBrakeShare, MainGearFriction, GripFriction, BrakedRolling, GripRolling, L);
            if (g.brake && MainCastor) GripGear.Castor(lg, MainCastorRange, MainCastorAlign, L);
            return lg;
        }

        // door modelled OPEN in the file (gear down): hingeA local Z = hinge axis, hingeB animated (localEulerAngles.z); the door re-posed CLOSED under hingeB.
        // Blender +a about b = Unity AngleAxis(-a, u(b)), so the file's open pose is AngleAxis(-open, axis) from closed.
        static (Transform, float) DoorHinge(Transform door, Newtonsoft.Json.Linq.JToken dj)
        {
            var axisW = new Vector3((float)dj["axis_unity"][0], (float)dj["axis_unity"][1], (float)dj["axis_unity"][2]).normalized;
            float open = (float)dj["open_deg"];
            var parent = door.parent;
            var perp = Vector3.Cross(axisW, Vector3.right).sqrMagnitude > 0.01f ? Vector3.Cross(axisW, Vector3.right).normalized : Vector3.up;
            var qa = Quaternion.LookRotation(axisW, perp);
            var ha = NewGO(door.name + "_hingeA", parent, door.position, qa);
            var hb = NewGO(door.name + "_hingeB", ha.transform, door.position, qa);
            var mf = door.GetComponent<MeshFilter>(); var c0 = mf.sharedMesh.bounds.center;
            float openSigned = -open;
            // verify the closed pose is the higher one (flush in the well); flip the sense if the conversion assumption is wrong
            var w0 = door.TransformPoint(c0);
            var closedRot = Quaternion.AngleAxis(-openSigned, axisW);
            var w1 = door.position + closedRot * (w0 - door.position);
            var w2 = door.position + Quaternion.AngleAxis(openSigned, axisW) * (w0 - door.position);
            if (w2.y > w1.y) { openSigned = -openSigned; closedRot = Quaternion.AngleAxis(-openSigned, axisW); }
            door.rotation = closedRot * door.rotation;
            door.SetParent(hb.transform, true);
            hb.transform.localEulerAngles = new Vector3(0, 0, openSigned);
            L($"door {door.name}: axis {axisW.ToString("F3")} open {openSigned:F1} deg about local Z; closed centre y {Mathf.Max(w1.y, w2.y):F3} vs open {w0.y:F3}");
            return (hb.transform, openSigned);
        }

        static Vector3 UnityPos(Newtonsoft.Json.Linq.JToken t) => new Vector3((float)t[0], (float)t[1], (float)t[2]);

        // ------------------------------------------------------------------ engine + propeller (NimrodBuild path; 3 blades)
        static void Engine()
        {
            var startup = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), parts["A6M2"].gameObject);
            var eng = parts["fus_engine"].gameObject;
            CloneComp(TplAudio("COIN:COIN", "cricket_turbine"), eng);
            var te = CloneComp(TplComp<TurbineEngine>("CAS1:engine_L"), eng);
            te.maxRPM = EngineRpm; te.minRPM = 500f; te.maxPower = EnginePower; te.spoolUpTime = 1.6f; S(te, "startupTime", 5f);
            S(te, "pitch", 0.16f); S(te, "volume", 0.08f);
            S(te, "startupAudio", startup); te.aircraft = aircraft;
            S(te, "heatHazeParticles", new ParticleSystem[0]);
            S(te, "maxFuelConsumption", 0.065f); S(te, "IRMin", 0.6f); S(te, "IRMax", 0.9f);
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
                S(b, "transform", broot.transform); S(b, "liftTransform", lt.transform); S(b, "mass", 14f);
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
            S(csp, "momentOfInertia", PropMoI); S(csp, "bladeLength", BladeLength); S(csp, "hubRadius", HubRadius);
            S(csp, "rpmLimit", PropRpm); S(csp, "nominalPower", EnginePower); S(csp, "propTorqueLimit", 9000f);
            S(csp, "bladeEfficiency", BladeEfficiency); S(csp, "targetAOA", PropTargetAoA);
            S(csp, "propAudio", pa);
            L($"prop: mesh tip radius {R:F3} m, {blades.Count} blades, bladeLength {BladeLength}, rpmLimit {PropRpm}, power {EnginePower / 1000f} kW, hub {hubVis.position.ToString("F3")}");
        }

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

        // ------------------------------------------------------------------ weapons (design 2.2 / 2.4): Type 97 x2 (one Gun, 2 muzzles), Type 99 x2 (one Gun per wing), tail hook
        static WeaponMount ammo97, ammo99, hookMount; static WeaponInfo info97, info99;
        static GameObject hookGO;
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

        static WeaponInfo OwnInfo(string stock, string name, string wname, string sname, string desc, float v0, float drag, float pierce, float blast, float mass, float range, float aSurf, float aAir)
        {
            var wi = Asset<WeaponInfo>($"MonoBehaviour/{stock}_PLACEHOLDER.asset");
            if (!OwnGunInfos) return wi;
            wi = Object.Instantiate(wi); wi.name = name;
            wi.weaponName = wname; wi.shortName = sname; wi.description = desc;
            wi.muzzleVelocity = v0; wi.maxSpeed = v0; wi.dragCoef = drag; wi.pierceDamage = pierce; wi.blastDamage = blast;
            wi.massPerRound = mass; wi.boresight = true; wi.targetRequirements.maxRange = range;
            wi.effectiveness.antiSurface = aSurf; wi.effectiveness.antiAir = aAir;
            AssetDatabase.CreateAsset(wi, $"{Folder}/{name}.asset");
            return wi;
        }

        static WeaponMount AmmoMount(string key, string label, WeaponInfo info, int rounds, float mass)
        {
            var go = new GameObject(key + "_prefab");
            var pf = PrefabUtility.SaveAsPrefabAsset(go, $"{Folder}/{key}_prefab.prefab");
            Object.DestroyImmediate(go);
            var m = Object.Instantiate(Asset<WeaponMount>("MonoBehaviour/gun_ammo_35mm_720_PLACEHOLDER.asset")); m.name = key;
            m.prefab = pf; m.jsonKey = key; m.info = info; m.mountName = label; m.ammo = rounds; m.GunAmmo = true; m.mass = mass;
            m.GearSafety = false;                // guns fire with the gear down too (stock gun ammo behaviour; FD-32 v1 lesson)
            AssetDatabase.CreateAsset(m, $"{Folder}/{key}.asset");
            return m;
        }

        static int Gcd(int a, int b) { a = Math.Abs(a); b = Math.Abs(b); while (b != 0) { int t = a % b; a = b; b = t; } return a; }
        static Gun MakeGun(string name, Gun template, Transform parent, Vector3 at, Transform[] muzzles, Transform[] flashes, WeaponInfo info, float rate, int rounds, int tracerRatio, float tracerSize, Color tracer, float spread)
        {
            var go = NewGO(name, parent, at, Quaternion.identity);
            foreach (var a in template.GetComponents<AudioSource>()) CloneComp(a, go).loop = false;   // Gun.Awake makes source[1] its sustained loop
            var gun = CloneComp(template, go);
            gun.attachedUnit = aircraft; gun.info = info;
            S(gun, "magazineCapacity", rounds); S(gun, "magazines", 0); S(gun, "startLoaded", true);
            S(gun, "fireRate", rate); S(gun, "muzzles", muzzles);
            S(gun, "tracerRatio", tracerRatio); S(gun, "tracerSize", tracerSize); S(gun, "tracerColor", tracer);
            S(gun, "bulletSpread", spread);
            S(gun, "recoilTransform", null); S(gun, "spinTransform", null);
            try { S(gun, "heatEnabled", false); } catch { }
            var ps = new List<ParticleSystem>();
            foreach (var fl in flashes) ps.AddRange(CopyMuzzleParticles(template, fl));
            S(gun, "muzzleParticles", ps.ToArray());
            return gun;
        }

        static void Weapons()
        {
            sets.Clear();
            var eng = parts["fus_engine"];
            var g12 = tpl["gun_12.7mm_internal"].GetComponentInChildren<Gun>(true);
            var g20 = tpl["gun_20mm_pod"].GetComponentInChildren<Gun>(true);
            info97 = OwnInfo("Gun7.5mm", "A6M2_type97_info", "Type 97 7.7mm MG", "TYPE97 7.7MM",
                "Two synchronised Type 97 7.7 mm machine guns in the cowling troughs, firing through the propeller arc, 500 rounds each.", 745f, 0.30f, 90f, 0f, 0.025f, 800f, 0.08f, 0.06f);
            info99 = OwnInfo("Gun20mm_Pod", "A6M2_type99_info", "Type 99 20mm Cannon", "TYPE99 20MM",
                "Two Type 99-1 Mk.3 20 mm cannon in the wings outside the propeller arc, 60-round drums: slow, heavy shells with a visible lob.", 600f, 0.27f, 300f, 0.025f, 0.20f, 1000f, 0.15f, 0.20f);
            if (OwnWeaponIcons)
            {
                S(info97, "weaponIcon", ImportRepoSprite(Path.Combine(RepoIcons, "a6m2_icon_type97.png"), "a6m2_icon_type97")); EditorUtility.SetDirty(info97);
                S(info99, "weaponIcon", ImportRepoSprite(Path.Combine(RepoIcons, "a6m2_icon_type99.png"), "a6m2_icon_type99")); EditorUtility.SetDirty(info99);
            }
            // ---- Type 97 x2: one Gun on fus_engine, two muzzles 0.19 m ahead of the blade plane, flashes in the troughs
            var mL = Find("muzzle_gun_L"); var mR = Find("muzzle_gun_R");
            if (!SyncMuzzlesAhead) { mL.position = Find("flash_gun_L").position; mR.position = Find("flash_gun_R").position; }
            var gun97 = MakeGun("guns_type97", g12, eng.transform, (Find("flash_gun_L").position + Find("flash_gun_R").position) / 2, new[] { mL, mR },
                new[] { Find("flash_gun_L"), Find("flash_gun_R") }, info97, T97Rate, T97Rounds, T97TracerRatio, 1.0f, new Color(20f, 16f, 5f), 1.5f);
            if (OwnGunSounds) S(gun97, "pitch", (float)G(gun97, "pitch") * 1.15f);
            ammo97 = AmmoMount("A6M2_ammo_type97", "Type 97 7.7mm x2 (500 rpg)", info97, T97Rounds, 25f);
            Set("Type 97 7.7mm MGs", new[] { ammo97 }, HP(gun97.transform, eng, new Weapon[] { gun97 }));
            // ---- Type 99 x2: one Gun per wing_inner (each cannon leaves with its wing), one set, one ammo mount (2 x 60)
            var hps = new List<Hardpoint>();
            foreach (var s in new[] { "L", "R" })
            {
                var w = parts["wing_inner_" + s];
                var g = MakeGun("cannon_type99_" + s, g20, w.transform, Find("cannon_body_" + s).position, new[] { Find("muzzle_cannon_" + s) },
                    new[] { Find("flash_cannon_" + s) }, info99, T99Rate, T99RoundsPerGun, 3, 1.6f, new Color(32f, 4f, 0.3f), 2.0f);
                if (OwnGunSounds)
                {   // one AudioSource => Gun.Awake sets no sustained loop: one fire sound per round (B-25H T13E1 pattern)
                    foreach (var a in g.GetComponents<AudioSource>().Skip(1).ToList()) Object.DestroyImmediate(a);
                    S(g, "pitch", (float)G(g, "pitch") * 0.9f);
                    // r6 (W1: the cannons fired 0 rounds): with ONE AudioSource Gun.ShotSound plays fireSounds[Random.Range(0, fireSounds.Length)]
                    // (Gun.cs 515-532), but the stock 20 mm pod gun has fireSounds: [] (it uses fireStart / fireSustained / fireEnd) ->
                    // IndexOutOfRange inside SpawnBullet before ammo-- / bulletsLoaded--, every shot. Give the single-source gun its fire clip.
                    if (T99FireSoundFix) S(g, "fireSounds", new[] { (AudioClip)G(g, "fireStart") });
                }
                hps.Add(HP(g.transform, w, new Weapon[] { g }));
            }
            ammo99 = AmmoMount("A6M2_ammo_type99", "Type 99 20mm x2 (60 rpg)", info99, 2 * T99RoundsPerGun, 36f);
            Set("Type 99 20mm Cannons", new[] { ammo99 }, hps.ToArray());
            // ---- tail hook (own mount, our A-frame rendered: visible stowed in the belly recess)
            var hookT = Find("tailhook");
            hookMount = Object.Instantiate(Mount("TailHook_Multirole1")); hookMount.name = "A6M2_tailhook";
            hookMount.jsonKey = "A6M2_tailhook"; hookMount.mountName = "Arrestor Hook"; hookMount.tailHook = true; hookMount.prefab = null;
            AssetDatabase.CreateAsset(hookMount, Folder + "/A6M2_tailhook.asset");
            hookGO = BuildTailHookObject(hookT);
            Set("Tail Hook", new[] { hookMount }, HP(Find("hp_tailhook"), parts["fus_tail"]));
            if (Round2Stores) Stores();
            else foreach (var n in new[] { "hp_bomb_L", "hp_bomb_R", "hp_special" }) Object.DestroyImmediate(Find(n).gameObject);
            var all = sets.SelectMany(x => x.hardpoints).OrderByDescending(h => h.transform.position.x).ThenByDescending(h => h.transform.position.z).ToList();
            for (int i = 0; i < all.Count; i++) all[i].HardpointIndex = i;
            weaponManager.hardpointSets = sets.ToArray();
            S(weaponManager, "aircraft", aircraft);
            L($"hardpoint sets: {string.Join(" | ", sets.Select(x => $"{x.name} ({x.hardpoints.Count} hp, {x.weaponOptions.Count - 1} options)"))}");
            L($"guns: T97 muzzles {mL.position.ToString("F3")} / {mR.position.ToString("F3")}, T99 muzzles {Find("muzzle_cannon_L").position.ToString("F3")} / {Find("muzzle_cannon_R").position.ToString("F3")}; prop plane z {Find("prop_hub").position.z:F3}");
        }

        // =================================================================== round 2 / 3 stores (design 2.2-2.4, 3.3-3.4)
        // Store models come in the FBX (blender/a6m2/a6m2_parts.build_stores, once at the right / centre hardpoint) and are taken OUT of the
        // aircraft before the parts are built: the bomb and rack meshes go into our own mount prefabs (NimrodBuild Cooper pattern).
        class StoreMesh { public Mesh mesh; public Material[] mats; public Vector3 localPos; public Quaternion localRot; }
        static readonly Dictionary<string, StoreMesh> stores = new Dictionary<string, StoreMesh>();
        static WeaponMount no6Mount, tokkoMount; static WeaponInfo no6Info, tokkoInfo; static MissileDefinition no6Def, tokkoDef;
        static GameObject no6BombGO, no6MountGO, tokkoBombGO, tokkoMountGO;
        static int setBombs = -1, setSpecial = -1;

        static void TakeStores()
        {
            stores.Clear();
            foreach (var (n, hp) in new[] { ("store_no6_bomb", "hp_bomb_R"), ("store_no6_rack", "hp_bomb_R"), ("store_tokko_bomb", "hp_special"), ("store_tokko_rack", "hp_special") })
            {
                var t = Find(n); var h = Find(hp);
                var mesh = t.GetComponent<MeshFilter>().sharedMesh;
                if (n.EndsWith("_bomb"))
                {   // pivot = the bomb's bounds centre (= its capsule centre): Missile.DetectCollisions linecasts from transform.position (Nimrod 1.4.0)
                    var c = mesh.bounds.center;
                    var mc = Object.Instantiate(mesh); mc.name = mesh.name + "_centred";
                    mc.vertices = mesh.vertices.Select(v => v - c).ToArray(); mc.RecalculateBounds();
                    generatedMeshes.Add(mc);
                    stores[n] = new StoreMesh { mesh = mc, mats = t.GetComponent<MeshRenderer>().sharedMaterials, localPos = h.InverseTransformPoint(t.TransformPoint(c)), localRot = Quaternion.Inverse(h.rotation) * t.rotation };
                }
                else stores[n] = new StoreMesh { mesh = mesh, mats = t.GetComponent<MeshRenderer>().sharedMaterials, localPos = h.InverseTransformPoint(t.position), localRot = Quaternion.Inverse(h.rotation) * t.rotation };
            }
            foreach (var n in stores.Keys.ToList()) Object.DestroyImmediate(Find(n).gameObject);
            L($"stores taken out of the aircraft: {string.Join(", ", stores.Select(kv => $"{kv.Key} {kv.Value.mesh.vertexCount} v at {kv.Value.localPos.ToString("F3")}"))}");
        }

        // Our bomb object: our mesh + the stock bomb's component values (Missile, seeker, MissileNetworkTransform), references re-wired.
        // seekerFrom = null keeps the stock OpticalSeekerBomb; else an OpticalSeeker copied from that template (the Genie's, design 3.4).
        static GameObject BuildBombObject(string name, string tplName, StoreMesh sm, MissileDefinition def, WeaponInfo info, float mass, float yield, float pierce, float finArea,
            float armDelay, string seekerFrom, float timeFuse)
        {
            var t = tpl[tplName];
            var go = new GameObject(name) { layer = t.layer };
            go.AddComponent<MeshFilter>().sharedMesh = sm.mesh;
            go.AddComponent<MeshRenderer>().sharedMaterials = sm.mats;
            go.AddComponent<Mirage.NetworkIdentity>();
            var rb = go.AddComponent<Rigidbody>(); EditorUtility.CopySerialized(t.GetComponent<Rigidbody>(), rb); rb.mass = mass;
            var cc = go.AddComponent<CapsuleCollider>(); EditorUtility.CopySerialized(t.GetComponent<CapsuleCollider>(), cc);
            var b = sm.mesh.bounds; cc.center = b.center; cc.direction = 2; cc.radius = Mathf.Min(b.extents.x, b.extents.y) * 0.85f; cc.height = b.size.z;
            var mis = (Missile)go.AddComponent(t.GetComponent<Missile>().GetType());
            EditorUtility.CopySerialized(t.GetComponent<Missile>(), mis);
            var so = new SerializedObject(mis); var it = so.GetIterator(); bool enter = true;
            while (it.Next(enter)) { enter = true; if (it.propertyType == SerializedPropertyType.ObjectReference && it.objectReferenceValue != null && IsTemplateObject(it.objectReferenceValue)) it.objectReferenceValue = null; }
            so.ApplyModifiedPropertiesWithoutUndo();
            mis.definition = def;
            S(mis, "mass", mass); S(mis, "blastYield", yield); S(mis, "pierceDamage", pierce); S(mis, "finArea", finArea); S(mis, "info", info);
            if (seekerFrom == null)
            {
                var seekT = t.GetComponent<OpticalSeekerBomb>();
                var seek = (OpticalSeekerBomb)go.AddComponent(seekT.GetType()); EditorUtility.CopySerialized(seekT, seek); S(seek, "missile", mis);
                S(seek, "armDelay", armDelay); S(seek, "altitudeFuseHeight", 0f); S(seek, "triggerMissileWarning", false);
            }
            else
            {
                var seekT = tpl[seekerFrom].GetComponentInChildren<OpticalSeeker>(true);
                if (seekT == null) throw new Exception("no OpticalSeeker on template " + seekerFrom);
                var seek = (OpticalSeeker)go.AddComponent(seekT.GetType()); EditorUtility.CopySerialized(seekT, seek);
                var so3 = new SerializedObject(seek); var it3 = so3.GetIterator(); bool en3 = true;
                while (it3.Next(en3)) { en3 = true; if (it3.propertyType == SerializedPropertyType.ObjectReference && it3.objectReferenceValue != null && IsTemplateObject(it3.objectReferenceValue)) it3.objectReferenceValue = null; }
                so3.ApplyModifiedPropertiesWithoutUndo();
                S(seek, "missile", mis);
                S(seek, "timeFuse", timeFuse); S(seek, "armDelay", 0f); S(seek, "tangibleDelay", 5f); S(seek, "proximityFuse", false); S(seek, "triggerMissileWarning", false);
            }
            var mntT = t.GetComponent<NuclearOption.NetworkTransforms.MissileNetworkTransform>();
            var mnt = go.AddComponent<NuclearOption.NetworkTransforms.MissileNetworkTransform>(); EditorUtility.CopySerialized(mntT, mnt); S(mnt, "Missile", mis);
            L($"bomb object {name}: {sm.mesh.vertexCount} v, length {b.size.z:F2} m (bounds {b.size.ToString("F2")}), mass {mass}, yield {yield}, pierce {pierce}, " +
              (seekerFrom == null ? $"OpticalSeekerBomb armDelay {armDelay}" : $"OpticalSeeker ({seekerFrom}) timeFuse {timeFuse}"));
            return go;
        }

        // Single-store mount object: our rack at the hardpoint, one child with the bomb mesh + the stock single mount's MountedMissile / AudioSource.
        static GameObject BuildSingleMountObject(string name, StoreMesh rack, StoreMesh bomb, string tplChild, WeaponInfo info)
        {
            var go = new GameObject(name);
            var rk = new GameObject("rack"); rk.transform.SetParent(go.transform, false);
            rk.transform.localPosition = rack.localPos; rk.transform.localRotation = rack.localRot;
            rk.AddComponent<MeshFilter>().sharedMesh = rack.mesh; rk.AddComponent<MeshRenderer>().sharedMaterials = rack.mats;
            var tb = TplFind(tplChild);
            var c = new GameObject("bomb (1)"); c.transform.SetParent(go.transform, false);
            c.transform.localPosition = bomb.localPos; c.transform.localRotation = bomb.localRot;
            c.AddComponent<MeshFilter>().sharedMesh = bomb.mesh; c.AddComponent<MeshRenderer>().sharedMaterials = bomb.mats;
            var bc = c.AddComponent<BoxCollider>(); bc.center = bomb.mesh.bounds.center; bc.size = bomb.mesh.bounds.size;
            var src = tb.GetComponent<AudioSource>();
            if (src != null) { var au = c.AddComponent<AudioSource>(); EditorUtility.CopySerialized(src, au); }
            var mmT = tb.GetComponent<MountedMissile>();
            var mm = (MountedMissile)c.AddComponent(mmT.GetType()); EditorUtility.CopySerialized(mmT, mm);
            S(mm, "info", info); S(mm, "attachedUnit", null);
            Remap(mm);
            return go;
        }

        static void Stores()
        {
            // ---- Type 97 No.6 60 kg (design 2.2): own info / definition / bomb / single mount with our rack, one per wing_inner
            no6Info = Object.Instantiate(Asset<WeaponInfo>("MonoBehaviour/info_bomb_125_1_PLACEHOLDER.asset")); no6Info.name = "A6M2_no6_info";
            no6Info.weaponName = "Type 97 No.6 60 kg"; no6Info.shortName = "NO.6 60KG";
            no6Info.description = "Type 97 No.6 60 kg land bomb, one under each wing on the Zero's own rack: impact fuze, light blast for strafing-run targets.";
            no6Info.massPerRound = NO6Mass; no6Info.costPerRound = no6Info.costPerRound * 0.5f;
            S(no6Info, "weaponIcon", ImportRepoSprite(Path.Combine(RepoIcons, "a6m2_icon_no6.png"), "a6m2_icon_no6"));
            AssetDatabase.CreateAsset(no6Info, Folder + "/A6M2_no6_info.asset");
            no6Def = Object.Instantiate(Asset<MissileDefinition>("MonoBehaviour/Bomb_125_1_PLACEHOLDER.asset")); no6Def.name = "A6M2_no6";
            no6Def.jsonKey = "A6M2_no6"; no6Def.unitName = "Type 97 No.6 60 kg"; no6Def.code = "NO.6"; ((UnitDefinition)no6Def).mass = NO6Mass; no6Def.unitPrefab = null;
            AssetDatabase.CreateAsset(no6Def, Folder + "/A6M2_no6.asset");
            no6BombGO = BuildBombObject("A6M2_no6", "bomb_125_1", stores["store_no6_bomb"], no6Def, no6Info, NO6Mass, NO6Yield, 120f, 0.05f, 2.0f, null, 0f);
            no6MountGO = BuildSingleMountObject("A6M2_no6_x1", stores["store_no6_rack"], stores["store_no6_bomb"], "bomb_125_single:bomb (1)", no6Info);
            no6Mount = Object.Instantiate(Mount("bomb_125_single")); no6Mount.name = "A6M2_no6_x1";
            no6Mount.jsonKey = "A6M2_no6_x1"; no6Mount.info = no6Info; no6Mount.mountName = "Type 97 No.6 60 kg"; no6Mount.ammo = 1;
            no6Mount.mass = NO6Mass + 4f; no6Mount.drag = 0.08f; no6Mount.RCS = 0.015f; no6Mount.prefab = null;
            AssetDatabase.CreateAsset(no6Mount, Folder + "/A6M2_no6_x1.asset");
            setBombs = sets.Count;
            Set("Bombs", new[] { no6Mount }, HP(Find("hp_bomb_L"), parts["wing_inner_L"]), HP(Find("hp_bomb_R"), parts["wing_inner_R"]));

            // ---- 250 kg special-attack charge (design 3.3-3.4): Event Content on the mount AND the definition; never in a loadout list
            if (Kamikaze)
            {
                tokkoInfo = Object.Instantiate(Asset<WeaponInfo>("MonoBehaviour/info_bomb_250_1_PLACEHOLDER.asset")); tokkoInfo.name = "A6M2_tokko_info";
                tokkoInfo.weaponName = "250 kg Special Attack"; tokkoInfo.shortName = "250KG SA";
                tokkoInfo.description = "Event Content. A 250 kg charge fixed under the centre section: it bursts when triggered with the gear up in flight, and when the aircraft crashes or is shot down (plugin).";
                tokkoInfo.massPerRound = TokkoMass;
                tokkoInfo.bomb = false; tokkoInfo.missile = false; tokkoInfo.gun = false; tokkoInfo.nuclear = false; tokkoInfo.boresight = true;
                tokkoInfo.effectiveness = new RoleIdentity { antiSurface = 1f };
                tokkoInfo.targetRequirements.maxAltitude = -1f;          // CombatAI.AnalyzeTarget scores every target zero: the AI never picks or fires it
                S(tokkoInfo, "weaponIcon", ImportRepoSprite(Path.Combine(RepoIcons, "a6m2_icon_tokko.png"), "a6m2_icon_tokko"));
                AssetDatabase.CreateAsset(tokkoInfo, Folder + "/A6M2_tokko_info.asset");
                tokkoDef = Object.Instantiate(Asset<MissileDefinition>("MonoBehaviour/Bomb_250_1_PLACEHOLDER.asset")); tokkoDef.name = "A6M2_tokko_charge";
                tokkoDef.jsonKey = "A6M2_tokko_charge"; tokkoDef.unitName = "250 kg Special Attack Charge"; tokkoDef.code = "250SA"; ((UnitDefinition)tokkoDef).mass = TokkoMass;
                tokkoDef.unitPrefab = null; tokkoDef.dontAutomaticallyAddToEncyclopedia = true; S(tokkoDef, "isEventContent", true);
                AssetDatabase.CreateAsset(tokkoDef, Folder + "/A6M2_tokko_charge.asset");
                tokkoBombGO = BuildBombObject("A6M2_tokko_charge", "bomb_250_1", stores["store_tokko_bomb"], tokkoDef, tokkoInfo, TokkoMass, TokkoYield, 350f, 0.08f, 0f, "AIR-2_Genie", TokkoTimeFuse);
                tokkoMountGO = BuildSingleMountObject("A6M2_tokko_x1", stores["store_tokko_rack"], stores["store_tokko_bomb"], "bomb_250_single:bomb", tokkoInfo);
                foreach (var mm in tokkoMountGO.GetComponentsInChildren<MountedMissile>(true)) { try { S(mm, "railLength", 0f); } catch { } try { S(mm, "railDelay", 0f); } catch { } }
                tokkoMount = Object.Instantiate(Mount("bomb_250_single")); tokkoMount.name = "A6M2_tokko_x1";
                tokkoMount.jsonKey = "A6M2_tokko_x1"; tokkoMount.info = tokkoInfo; tokkoMount.mountName = "250 kg Special Attack (Event)"; tokkoMount.ammo = 1;
                tokkoMount.mass = TokkoMass + 12f; tokkoMount.drag = 0.12f; tokkoMount.RCS = 0.03f; tokkoMount.prefab = null;
                tokkoMount.GearSafety = true; tokkoMount.GroundSafety = true; tokkoMount.dontAutomaticallyAddToEncyclopedia = true;
                S(tokkoMount, "isEventContent", true);
                AssetDatabase.CreateAsset(tokkoMount, Folder + "/A6M2_tokko_x1.asset");
                setSpecial = sets.Count;
                Set("Special", new[] { tokkoMount }, HP(Find("hp_special"), parts["A6M2"]));
                sets[setBombs].precludingHardpointSets.Add((byte)setSpecial);
                sets[setSpecial].precludingHardpointSets.Add((byte)setBombs);
            }
            L($"stores: Bombs set {setBombs} (No.6 x1 per wing, yield {NO6Yield}), Special set {setSpecial} (charge yield {TokkoYield}, event content, precluding each other)");
        }

        static void SaveStorePrefabs()
        {
            foreach (var (go, def, info) in new[] { (no6BombGO, no6Def, no6Info), (tokkoBombGO, tokkoDef, tokkoInfo) })
            {
                if (go == null) continue;
                var bp = PrefabUtility.SaveAsPrefabAsset(go, $"{Folder}/{go.name}_bomb.prefab");
                Object.DestroyImmediate(go);
                def.unitPrefab = bp; EditorUtility.SetDirty(def);
                info.weaponPrefab = bp; EditorUtility.SetDirty(info);       // MountedMissile.RailLaunch spawns info.weaponPrefab (MountedMissile.cs:163)
            }
            no6BombGO = tokkoBombGO = null;
            foreach (var (go, mount) in new[] { (no6MountGO, no6Mount), (tokkoMountGO, tokkoMount) })
            {
                if (go == null) continue;
                var mp = PrefabUtility.SaveAsPrefabAsset(go, $"{Folder}/{go.name}.prefab");
                Object.DestroyImmediate(go);
                mount.prefab = mp; EditorUtility.SetDirty(mount);
            }
            no6MountGO = tokkoMountGO = null;
        }

        static GameObject BuildTailHookObject(Transform hookT)
        {
            var th = contract["tailhook"];
            float len = (float)th["length"], stow = (float)th["stowed_up_deg"], dep = (float)th["deployed_deg"];
            var go = new GameObject("A6M2_tailhook_mount");
            var hinge = new GameObject("hinge"); hinge.transform.SetParent(go.transform, false);
            var hook = new GameObject("hook"); hook.transform.SetParent(hinge.transform, false);
            var mesh = new GameObject("hook_mesh"); mesh.transform.SetParent(hook.transform, false);
            mesh.transform.localRotation = Quaternion.Euler(-stow, 0, 0);
            mesh.AddComponent<MeshFilter>().sharedMesh = hookT.GetComponent<MeshFilter>().sharedMesh;
            mesh.AddComponent<MeshRenderer>().sharedMaterials = hookT.GetComponent<MeshRenderer>().sharedMaterials;
            var end = new GameObject("hookEnd"); end.transform.SetParent(hook.transform, false); end.transform.localPosition = new Vector3(0, 0, -len);
            var cast = new GameObject("castPoint"); cast.transform.SetParent(end.transform, false);
            cast.transform.localPosition = new Vector3(0, 0, 0.887f * len); cast.transform.localRotation = Quaternion.Euler(180f, 0, 0);
            var t = go.AddComponent<TailHook>();
            EditorUtility.CopySerialized(TplComp<TailHook>("TailHook_Multirole1:TailHook_Multirole1"), t);
            Remap(t);
            S(t, "hinge", hinge.transform); S(t, "hook", hook.transform); S(t, "castPoint", cast.transform); t.hookEnd = end.transform;
            S(t, "stowedAngle", stow); S(t, "deployedAngle", dep);
            hook.transform.localEulerAngles = new Vector3(stow, 0, 0);
            Object.DestroyImmediate(hookT.gameObject);
            foreach (var pp in parts.Values) ((List<Renderer>)G(G(pp, "damageMaterial"), "renderers")).RemoveAll(r => r == null);
            L($"tail hook mount: length {len:F2} m, stowed {stow} deg, deployed {dep} deg, our A-frame rendered");
            return go;
        }

        // ------------------------------------------------------------------ cockpit (round 1 placeholder: stock pilot figure, bail-out; the real cockpit is round 4)
        static readonly List<Pilot> crew = new List<Pilot>();
        static Transform helmetCam;
        static void Cockpit()
        {
            var cp = parts["A6M2"];
            var eye = Find("cockpit_eye");
            var fig = (GameObject)Object.Instantiate(TplFind("COIN:pilot").gameObject);
            fig.SetActive(true); fig.name = "pilot";
            foreach (var t in fig.GetComponentsInChildren<Transform>(true).ToList()) if (t != null && t.name == "EjectionSeat") Object.DestroyImmediate(t.gameObject);
            fig.transform.SetParent(eye.parent, false);
            var cam = fig.GetComponentsInChildren<Transform>(true).First(t => t.name == "helmetCamPoint");
            fig.transform.rotation = Quaternion.LookRotation(Vector3.forward, Vector3.up);
            fig.transform.position += eye.position - cam.position;
            foreach (var comp in fig.GetComponentsInChildren<Component>(true)) if (comp != null) Remap(comp);
            var pc = fig.GetComponent<Pilot>();
            S(pc, "aircraft", aircraft); S(pc, "unitPart", cp); S(pc, "ejectionSeat", false); S(pc, "autoTrimmer", controlsFilter);
            S(pc, "pilotCollider", fig.GetComponent<CapsuleCollider>());
            pc.exitDirection = Pilot.ExitDirection.Left;
            helmetCam = cam; crew.Add(pc);
            if (SlidingHood) BuildHood(cp);
            else S(aircraft, "canopies", new Canopy[0]);
            L($"pilot eye {cam.position.ToString("F3")} vs cockpit_eye {eye.position.ToString("F3")}");

            // cockpit-layer copies (exterior originals hidden in cockpit view); glass copies use the stock cockpit-side glass
            var cockpitR = new List<Renderer>(); var exteriorR = new List<Renderer>();
            var copyNames = new List<string> { "fus_center", "fus_engine", "wing_C" };
            if (!R8CockpitCanopy) copyNames.AddRange(new[] { "canopy_windscreen", "canopy_hood", "canopy_rear" });
            if (PeriodCockpit)
            {
                copyNames.AddRange(root.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.StartsWith("gauge_")).Select(m => m.name));
                copyNames.AddRange(root.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.StartsWith("cockpit_") && !m.name.EndsWith("_int")).Select(m => m.name));
            }
            foreach (var n in copyNames.Distinct())
            {
                var orig = TryFind(n);
                if (orig == null || orig.GetComponent<MeshRenderer>() == null) continue;
                var src = orig.GetComponent<MeshRenderer>();
                var copy = NewGO(n + "_int", orig, orig.position, orig.rotation, 3);
                copy.AddComponent<MeshFilter>().sharedMesh = orig.GetComponent<MeshFilter>().sharedMesh;
                var cr = copy.AddComponent<MeshRenderer>();
                cr.sharedMaterials = src.sharedMaterials.Select(m => m == mats["glass"] ? (R8CockpitCanopy ? mats["glass_ck"] : mats["glass_int"]) : m).ToArray();
                cr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                cr.enabled = false;
                cockpitR.Add(cr); exteriorR.Add(src);
                if (src.sharedMaterials[0] == mats["paint"])
                {
                    var owner = parts.Values.First(p => PartRenderers(p.gameObject).Contains(src));
                    ((List<Renderer>)G(G(owner, "damageMaterial"), "renderers")).Add(cr);
                }
            }
            if (R8CockpitCanopy)
            {   // r8: exterior canopy hidden in the cockpit view; the cockpit-view canopy (WT cockpit-model stations) shown there only
                foreach (var n in new[] { "canopy_windscreen", "canopy_hood", "canopy_rear" })
                { var r = TryFind(n)?.GetComponent<MeshRenderer>(); if (r != null && !exteriorR.Contains(r)) exteriorR.Add(r); }
                foreach (var n in new[] { "ckcanopy_fixed", "ckcanopy_hood" })
                {
                    var t = TryFind(n); var r = t?.GetComponent<MeshRenderer>();
                    if (r == null) throw new Exception("r8 cockpit canopy missing: " + n);
                    t.gameObject.layer = 3;
                    r.sharedMaterials = r.sharedMaterials.Select(m => m == mats["glass"] ? mats["glass_ck"] : m).ToArray();
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.enabled = false;
                    cockpitR.Add(r);
                    foreach (var pp in parts.Values) ((List<Renderer>)G(G(pp, "damageMaterial"), "renderers")).Remove(r);
                }
            }
            S(aircraft, "cockpitRenderers", cockpitR.ToArray());
            S(aircraft, "exteriorRenderers", exteriorR.ToArray());
            var screen = NewGO("screen_dummy", cp.transform, eye.position + new Vector3(0, -0.6f, 0.5f), Quaternion.identity, 3);
            screen.AddComponent<MeshFilter>().sharedMesh = QuadMesh("screen_dummy", 0.01f, 0.01f);
            var sr = screen.AddComponent<MeshRenderer>(); sr.sharedMaterial = mats["screen"]; sr.enabled = false;
            var ckGO = NewGO("cockpit", cp.transform, eye.position, Quaternion.identity);
            var ck = CloneComp(TplComp<global::Cockpit>("COIN:cockpit_F_interior"), ckGO);
            S(ck, "tacScreenRender", sr); S(ck, "aircraft", aircraft);
            S(ck, "engineSources", new[] { parts["fus_engine"].gameObject });
            if (PeriodCockpit)
            {   // NimrodBuild 1102-1105: stick = Cockpit.Joystick (range 14), throttle lever = Cockpit.Throttle (rotation, range 40)
                var js = NewElem(ck, "joysticks"); S(js, "transform", DrivenFrame(Find("cockpit_stick"))); S(js, "range", 14f);
                SetSeq(ck, "joysticks", new[] { js });
                var th = NewElem(ck, "throttles"); S(th, "rotation", true); S(th, "motion", false); S(th, "transform", DrivenFrame(Find("cockpit_throttle"))); S(th, "range", 40f);
                SetSeq(ck, "throttles", new[] { th });
            }
            else { SetSeq(ck, "joysticks", new object[0]); SetSeq(ck, "throttles", new object[0]); }
            L($"cockpit: {(PeriodCockpit ? "period cockpit (dials, sight, breeches, seat, stick, throttle)" : "placeholder")}, {cockpitR.Count} cockpit-layer copies");

            var nose = parts["fus_engine"];
            var tcF = NewGO("targetCamForward", nose.transform, new Vector3(0, -0.70f, 1.60f), Quaternion.identity, 0);
            var tcR = NewGO("targetCamRear", parts["fus_tail"].transform, new Vector3(0, 0.30f, -5.8f), Quaternion.LookRotation(Vector3.back), 0);
            var tcL = NewGO("landingCamPoint", nose.transform, new Vector3(0, -0.80f, 1.30f), Quaternion.LookRotation(new Vector3(0, -0.3f, 1f)), 0);
            var tc = CloneComp(TplComp<TargetCam>("COIN:nose"), nose.gameObject);
            S(tc, "currentMount", tcF.transform); S(tc, "camMountForward", tcF.transform); S(tc, "camMountRear", tcR.transform); S(tc, "camMountLanding", tcL.transform);
            S(tc, "attachedPart", nose); S(tc, "targetScreenRenderer", sr);
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

        // Sliding hood (design 8 C10) with stock code only: Canopy.CanopyHinge sets localEulerAngles = right * hingeAngle * openAmount, so the hood hangs
        // under a hinge HoodPivotDrop below it; HoodSlide / HoodPivotDrop rad of rotation moves it ~HoodSlide aft with a drop of D(1 - cos) = 16 mm.
        // The hinge hangs under an 'eject' frame AT the hood (FD-32 pattern) that Canopy.EjectionSequence detaches and pushes (4000 N on 40 kg): the hood leaves
        // before the bail-out, so the pilot no longer goes through the glass.
        static Canopy hood;
        // r8: folding tips (user review 1). The game has no fixed-wing fold component (decompile of the installed 0.34.6 Assembly-CSharp:
        // only RotorShaft.RotorHinge folds anything at spawn, and SwingWingController sweeps by Mach). The part keeps its collider and
        // joints; its RENDER mesh moves under wing_fold_X_hinge (on the fold line, local X = fold axis, + angle = tip up) so the plugin can
        // turn it without fighting the physics joint. Contract 'wing_fold' gives the hinge line (Blender a6m2_parts.build_wings).
        static void WingFold()
        {
            foreach (var side in new[] { "L", "R" })
            {
                var part = parts["wing_fold_" + side];
                var go = part.gameObject;
                var mf = go.GetComponent<MeshFilter>(); var mr = go.GetComponent<MeshRenderer>();
                if (mf == null || mr == null) throw new Exception("wing fold: no mesh on " + go.name);
                var j = contract["wing_fold"][side];
                var a = root.transform.TransformPoint(UnityPos(j["hinge_le"])); var b = root.transform.TransformPoint(UnityPos(j["hinge_te"]));
                var axis = (b - a).normalized;
                var tip = mr.bounds.center;
                var mid = (a + b) * 0.5f;
                if ((Quaternion.AngleAxis(WingFoldDeg, axis) * (tip - mid)).y < (tip - mid).y) axis = -axis;    // + angle must lift the tip
                var hinge = NewGO(go.name + "_hinge", go.transform, mid, Quaternion.identity);
                hinge.transform.rotation = Quaternion.FromToRotation(Vector3.right, axis);
                var vis = NewGO(go.name + "_vis", hinge.transform, go.transform.position, go.transform.rotation);
                vis.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
                var vr = vis.AddComponent<MeshRenderer>(); vr.sharedMaterials = mr.sharedMaterials;
                var dl = (List<Renderer>)G(G(part, "damageMaterial"), "renderers");
                int i = dl.IndexOf(mr); if (i >= 0) dl[i] = vr; else if (mr.sharedMaterials.Length > 0 && mr.sharedMaterials[0] == mats["paint"]) dl.Add(vr);
                Object.DestroyImmediate(mr); Object.DestroyImmediate(mf);
                L($"wing fold {side}: hinge {hinge.transform.localPosition.ToString("F3")} axis {go.transform.InverseTransformDirection(axis).ToString("F3")} (part local), {WingFoldDeg} deg up");
            }
        }

        static void BuildHood(AeroPart cp)
        {
            var hoodT = Find("canopy_hood");
            var hmf = hoodT.GetComponent<MeshFilter>();
            var hc = hoodT.TransformPoint(hmf.sharedMesh.bounds.center);
            var ej = NewGO("canopy_eject", hoodT.parent, hc, Quaternion.LookRotation(Vector3.forward, Vector3.up));            // rb + push at the hood
            var hinge = NewGO("canopy_slide_hinge", ej.transform, hc + Vector3.down * HoodPivotDrop, Quaternion.LookRotation(Vector3.forward, Vector3.up));
            hoodT.SetParent(hinge.transform, true);
            float deg = HoodSlide / HoodPivotDrop * Mathf.Rad2Deg;
            float sgn = (Quaternion.AngleAxis(deg, hinge.transform.right) * (hc - hinge.transform.position)).z < (Quaternion.AngleAxis(-deg, hinge.transform.right) * (hc - hinge.transform.position)).z ? 1f : -1f;
            var box = hoodT.gameObject.AddComponent<BoxCollider>(); box.center = hmf.sharedMesh.bounds.center; box.size = hmf.sharedMesh.bounds.size; box.enabled = false;
            // r7 (game: the bail-out went through the closed glass): Canopy.EjectionSequence moves the ejection rigidbody to the CANOPY COMPONENT's
            // own position (rb.MovePosition(TransformPoint(InverseTransformPoint(base.transform.position))), Canopy.cs 100-123). r4-r6 had the
            // component on the slide hinge 8 m below the hood, so the jettisoned hood was teleported 8 m down into / under the fuselage.
            // Now the component sits on the ejection transform at the hood centre; the hinge stays in canopyHinges (the slide is unchanged).
            hood = CloneComp(TplComp<Canopy>("COIN:canopyFrame_F"), HoodCanopyOnEject ? ej : hinge);
            hood.ejectionTransform = ej.transform; hood.attachedPart = cp; hood.mass = 40f; hood.ejectionCollider = box;
            S(hood, "ejectionForce", new Vector3(0f, 4000f, 0f)); S(hood, "forcePosition", new Vector3(0f, 0f, 0.2f));
            var hh = NewElem(hood, "canopyHinges"); S(hh, "transform", hinge.transform); S(hh, "hingeAngle", sgn * deg);
            SetSeq(hood, "canopyHinges", new[] { hh });
            S(hood, "fireTime", 0.2f); S(hood, "openSpeed", 0.6f);
            S(hood, "glassRenderers", new Renderer[] { hoodT.GetComponent<MeshRenderer>() });
            S(aircraft, "canopies", new[] { hood });
            L($"hood: Canopy, hinge {HoodPivotDrop} m below the hood centre {hc.ToString("F3")}, hingeAngle {sgn * deg:F2} deg (= {HoodSlide} m aft), jettison 4000 N on 40 kg");
        }

        static void AddInvisibleAirbrake(AeroPart rootPart, float drag, float openSpeed)
        {
            var ab = root.AddComponent<global::Airbrake>();
            S(ab, "transforms", new Transform[0]); S(ab, "dragAmount", drag); S(ab, "maxAngle", 0f); S(ab, "openSpeed", openSpeed);
            S(ab, "part", rootPart); S(ab, "airbrakeSound", null); S(ab, "constraints", new UnityEngine.Animations.AimConstraint[0]);
            S(ab, "volumeMultiplier", 0f); S(ab, "aircraft", aircraft);
            L($"invisible airbrake: stock Airbrake on the root, dragAmount {drag}, no transforms (plugin AirBrake1912 widens throttle == 0 to < 5 %)");
        }

        // ------------------------------------------------------------------ root systems
        static void RootSystems()
        {
            var coin = tpl["COIN"];
            var detector = CloneComp(coin.GetComponent<TargetDetector>(), root);
            S(detector, "attachedUnit", aircraft); S(detector, "scanner", parts["A6M2"].transform);
            aircraft.EOTS = detector;
            var cap = CloneComp(TplAudio("COIN:COIN", "capacitor"), root);
            var power = CloneComp(coin.GetComponent<PowerSupply>(), root);
            S(power, "powerSources", new[] { parts["fus_engine"].gameObject });
            S(power, "source", cap); S(power, "aircraft", aircraft);
            S(aircraft, "powerSupply", power);
            CloneComp(coin.GetComponent<NuclearOption.NetworkTransforms.AircraftNetworkTransform>(), root);
            // design 7.1: fuselage tank (104 kg) on the root, one wing tank (140 kg) on each wing_inner; linked so the engine draws from all three
            var tanks = new List<FuelTank>();
            foreach (var (pn, kg) in new[] { ("A6M2", FuelFusKg), ("wing_inner_L", FuelWingKg), ("wing_inner_R", FuelWingKg) })
            {
                var ft = CloneComp(coin.GetComponent<FuelTank>(), parts[pn].gameObject);
                S(ft, "fuelCapacity", kg); S(ft, "fuelMass", kg); S(ft, "part", parts[pn]);
                tanks.Add(ft);
            }
            foreach (var ft in tanks) SetSeq(ft, "connectedTanks", tanks.Where(t => t != ft).Cast<object>());
            var nl = CloneComp(coin.GetComponent<NavLights>(), root);
            SetSeq(nl, "navLights", new object[0]);      // period tip lenses only; the list stays (the nav-light key looks it up)
            S(nl, "aircraft", aircraft);
            if (KeepFlareEjector)
            {
                var fe = CloneComp(coin.GetComponent<FlareEjector>(), root);
                var pts = new List<object>();
                foreach (var sx in new[] { -1f, 1f })
                {
                    var part = parts["fus_rear"];
                    var g = NewGO("flareEjector_" + (sx < 0 ? "L" : "R"), part.transform, new Vector3(sx * 0.2f, -0.45f, -3.2f), Quaternion.LookRotation(Vector3.down));
                    var a = CloneComp(TplAudio("COIN:flareEjector_L", "flare"), g);
                    var ep = NewElem(fe, "ejectionPoints");
                    S(ep, "part", part); S(ep, "transform", g.transform); S(ep, "sound", a);
                    pts.Add(ep);
                }
                SetSeq(fe, "ejectionPoints", pts);
                foreach (var f in new[] { "doors", "flareDoors" }) { try { SetSeq(fe, f, new object[0]); } catch { } }
                S(fe, "aircraft", aircraft);
                if (FlareCount >= 0) fe.ammo = FlareCount;
            }
            var sparks = CopyParticle(TplFind("COIN:contactSparks").GetComponent<ParticleSystem>(), root.transform, root.transform.position, "contactSparks");
            S(aircraft, "sparksEmitter", sparks);
            var sgp = root.AddComponent<SetGlobalParticles>();
            S(sgp, "systems", ourParticles.ToList());
            S(aircraft, "dopplerSounds", new List<AudioSource> { parts["fus_engine"].GetComponent<AudioSource>(), parts["prop"].GetComponent<AudioSource>() });
            aircraft.maxRadius = 6.3f;
            aircraft.obstacleTop = 1.5f;
        }

        static void FlyByWire(LandingGear mainGear)
        {
            var so = new SerializedObject(controlsFilter);
            void F(string p, float v) { var sp = so.FindProperty("flyByWire." + p); if (sp == null) throw new Exception("no flyByWire." + p); sp.floatValue = v; }
            F("gLimitPositive", 7.0f); F("cornerSpeed", 88f); F("postStallManeuverSpeed", 0f); F("maxRollSpeed", FbwMaxRollSpeed); F("maxRollAngularVel", FbwMaxRollAngVel); F("rollTightness", FbwRollTightness);
            F("takeoffSpeed", FbwTakeoffSpeed); F("pidTransitionSpeed", 70f); F("alphaLimiter", AlphaLimiter);
            int n = 0; var it = so.GetIterator();
            while (it.Next(true)) if (it.name == "noseGear" && it.propertyType == SerializedPropertyType.ObjectReference) { it.objectReferenceValue = mainGear; n++; }
            so.ApplyModifiedPropertiesWithoutUndo();
            var ap = parts["A6M2"].GetComponent<AutopilotPlane>();
            var so2 = new SerializedObject(ap);
            var rs = so2.FindProperty("forwardFlightController.referenceAirspeed"); if (rs != null) rs.floatValue = 88f;
            var pi = so2.FindProperty("preventInvertedFlight"); if (pi != null) pi.boolValue = false;
            so2.ApplyModifiedPropertiesWithoutUndo();
            L($"FBW: g 7.0, corner 88, maxRollSpeed {FbwMaxRollSpeed}, maxRollAngularVel {FbwMaxRollAngVel}, rollTightness {FbwRollTightness}, alpha limiter {AlphaLimiter}, takeoff {FbwTakeoffSpeed}; noseGear refs -> {mainGear.name} ({n})");
        }

        // =================================================================== aero curves (tools/flightmodel/a6m2_fm.py: WING_CL / WING_CD / AIL_CL / TAIL_CL / ELEV_CL)
        public static readonly (float t, float v)[] WingCL = { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.95f), (-0.36f, -0.80f), (-0.27f, -1.00f), (0f, 0.17f), (0.1473f, 0.91f), (0.2454f, 1.40f),
            (0.2793f, 1.45f), (0.3142f, 1.42f), (0.40f, 1.28f), (0.6f, 1.10f), (0.785f, 0.95f), (1.571f, 0f), (3.142f, 0f) };
        public static readonly (float, float)[] WingCD = { (0f, 0.0070f), (0.06f, 0.020f), (0.1f, 0.036f), (0.2f, 0.085f), (0.28f, 0.14f), (0.35f, 0.26f), (0.5f, 0.5f), (1.51f, 1.7f), (3.14159f, 0f) };
        public static readonly (float t, float v)[] AileronCL = { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -1.10f), (-0.62f, -1.30f), (-0.52f, -1.40f), (-0.40f, -1.30f), (-0.2945f, -1.0f), (0f, 0.17f), (0.1473f, 0.91f),
            (0.2454f, 1.40f), (0.2945f, 1.50f), (0.40f, 1.72f), (0.52f, 1.85f), (0.62f, 1.80f), (0.785f, 1.40f), (1.571f, 0f), (3.142f, 0f) };
        public static readonly (float t, float v)[] TailCL = { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.9f), (-0.45f, -0.8f), (-0.3f, -1.1f), (0f, 0f), (0.3f, 1.1f), (0.45f, 0.8f), (0.785f, 0.9f), (1.571f, 0f), (3.142f, 0f) };
        public static readonly (float t, float v)[] ElevCL = { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -1.2f), (-0.6f, -1.5f), (-0.45f, -1.55f), (-0.3f, -1.2f), (0f, 0f), (0.3f, 1.2f), (0.45f, 1.55f), (0.6f, 1.5f),
            (0.785f, 1.2f), (1.571f, 0f), (3.142f, 0f) };
        static AnimationCurve DragCurve((float, float)[] pts)
        {
            var keys = new List<Keyframe>();
            foreach (var (t, v) in pts.Reverse()) if (t > 0f) keys.Add(new Keyframe(-t, v));
            foreach (var (t, v) in pts) keys.Add(new Keyframe(t, v));
            var c = new AnimationCurve(keys.ToArray());
            for (int i = 0; i < c.length; i++) c.SmoothTangents(i, 0f);
            return c;
        }
        static AnimationCurve Mirror((float t, float v)[] phys)
        {
            var keys = phys.Select(k => (t: -k.t, v: -k.v)).OrderBy(k => k.t).GroupBy(k => k.t).Select(g => g.First()).Select(k => new Keyframe(k.t, k.v)).ToArray();
            var c = new AnimationCurve(keys);
            for (int i = 0; i < c.length; i++) AnimationUtility.SetKeyLeftTangentMode(c, i, AnimationUtility.TangentMode.Linear);
            for (int i = 0; i < c.length; i++) AnimationUtility.SetKeyRightTangentMode(c, i, AnimationUtility.TangentMode.Linear);
            return c;
        }

        // =================================================================== save
        static GameObject SaveEverything()
        {
            var bank = Folder + "/Generated/A6M2_meshes.asset";
            AssetDatabase.CreateAsset(generatedMeshes[0], bank);
            foreach (var m in generatedMeshes.Skip(1)) AssetDatabase.AddObjectToAsset(m, bank);
            if (hookGO != null)
            {
                var hp = PrefabUtility.SaveAsPrefabAsset(hookGO, Folder + "/A6M2_tailhook_mount.prefab");
                Object.DestroyImmediate(hookGO); hookGO = null;
                hookMount.prefab = hp; EditorUtility.SetDirty(hookMount);
            }
            SaveStorePrefabs();
            var coinParams = Asset<AircraftParameters>("MonoBehaviour/COINParameters_PLACEHOLDER.asset");
            var tdrag = coinParams.airfoils[0].dragCoef;
            var wing = new Airfoil { name = "A6M2_wing", liftCoef = Mirror(WingCL), dragCoef = DragCurve(WingCD) };
            var tail = new Airfoil { name = "A6M2_tail", liftCoef = Mirror(TailCL), dragCoef = new AnimationCurve(tdrag.keys) };
            var ail = new Airfoil { name = "A6M2_aileron", liftCoef = Mirror(AileronCL), dragCoef = DragCurve(WingCD) };
            var elev = new Airfoil { name = "A6M2_elevator", liftCoef = Mirror(ElevCL), dragCoef = new AnimationCurve(tdrag.keys) };

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
                foreach (var (file, label, fac, both) in Liveries.Where(x => x.both || x.faction == side))
                    livs.Add(new AircraftParameters.Livery { name = label, faction = side == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(livGuid[file]) });

            var prm = Object.Instantiate(coinParams);
            prm.HUDExtras = StockHUDExtras ? Asset<GameObject>("GameObject/COIN_HUDExtras_PLACEHOLDER.prefab") : null;
            prm.name = "A6M2_Parameters";
            BuildDiagramSprites();
            prm.StatusDisplay = BuildStatusDisplayPrefab();
            prm.aircraftName = DisplayName; prm.rankRequired = 0;
            prm.airfoils = new[] { wing, tail, ail, elev };
            prm.liveries = livs;
            int nSets = sets.Count;
            NuclearOption.SavedMission.Loadout LO(bool hook, bool bombs = false)
            {   // the Special set (the charge) is ALWAYS null here: design 3.2, no loadout list ever references A6M2_tokko_x1
                var w = new List<WeaponMount>();
                foreach (var s in sets) w.Add(s.name.StartsWith("Type 97") ? ammo97 : s.name.StartsWith("Type 99") ? ammo99 : s.name == "Tail Hook" ? (hook ? hookMount : null)
                    : s.name == "Bombs" ? (bombs ? no6Mount : null) : null);
                return new NuclearOption.SavedMission.Loadout { weapons = w };
            }
            // design 3.2: loadouts[1] is read unvetted as the fallback / first default: guns + hook. Never anything event-content.
            prm.loadouts = new List<NuclearOption.SavedMission.Loadout> { new NuclearOption.SavedMission.Loadout { weapons = Enumerable.Repeat<WeaponMount>(null, nSets).ToList() }, LO(true) };
            prm.StandardLoadouts = Round2Stores
                ? new[] { new StandardLoadout { Name = "Fighter", loadout = LO(true), FuelRatio = 0.8f }, new StandardLoadout { Name = "Fighter-bomber", loadout = LO(true, true), FuelRatio = 0.8f } }
                : new[] { new StandardLoadout { Name = "Fighter", loadout = LO(true), FuelRatio = 0.8f } };
            prm.DefaultFuelLevel = 0.8f;
            prm.aircraftGLimit = 7.0f; prm.PIDReferenceAirspeed = 88f; prm.maxSpeed = 145f; prm.takeoffSpeed = R6AiSpeeds ? AiTakeoffSpeedR6 : 36f; prm.takeoffDistance = 220f;
            prm.turningRadius = 350f; prm.cornerSpeed = 88f; prm.approachSpeed = 44f; prm.landingSpeed = 36f; prm.shortLandingSpeed = 34f;
            prm.cruiseThrottle = 0.85f; prm.minimumRadarAlt = 60f; prm.groundTurningRadius = 8f;
            AssetDatabase.CreateAsset(prm, Folder + "/A6M2_Parameters.asset");

            float total = parts.Values.Sum(p => p.mass);
            var def = Object.Instantiate(Asset<AircraftDefinition>("MonoBehaviour/CI-22_PLACEHOLDER.asset"));
            def.name = "A6M2";
            def.jsonKey = JsonKey; def.WorkshopTag = DisplayName; def.unitName = DisplayName; def.code = "A6M2"; def.bogeyName = "";
            def.description = "Mitsubishi A6M2 Zero Model 21, 1940. The Imperial Japanese Navy's carrier fighter: Nakajima Sakae 12 radial, two Type 97 " +
                "7.7 mm guns in the cowling and two Type 99 20 mm cannon in the wings, an arrestor hook and very long range. Light, agile at low speed, " +
                "heavy on the ailerons when fast.";
            def.length = 9.06f; def.width = 12.0f; def.height = 3.05f; ((UnitDefinition)def).mass = total;
            def.value = 9f; def.radarSize = 0.47f; def.visibleRange = 3500f; def.manpower = 1;
            def.roleIdentity.antiAir = 0.8f; def.roleIdentity.antiSurface = 0.4f;
            float contactH = (float)contract["level_wheel_contact_height"];
            def.spawnOffset = new Vector3(0f, contactH + SpawnLift, SpawnForward);
            def.restRotation = new Vector3(-(float)contract["three_point_deg"], 0f, 0f);
            def.aircraftParameters = prm;
            def.mapIcon = mapIconSprite; def.mapIconSize = 0.85f; def.mapOrient = true;
            def.aircraftInfo = new AircraftInfo { emptyWeight = 1680f, maxSpeed = 533f, stallSpeed = 120f, maneuverability = 8f, maxWeight = 2796f };
            def.unitPrefab = null;
            AssetDatabase.CreateAsset(def, Folder + "/A6M2.asset");
            foreach (var u in root.GetComponentsInChildren<Unit>(true)) u.definition = def;
            root.GetComponent<Rigidbody>().mass = total;
            {   // r8e (game r8d: a light-grey slab under the tailplane on the dark liveries): the game sets _Livery only on the renderers in
                // each part's damageMaterial.renderers (UnitPart.SetLivery). A paint renderer left out of every list keeps the default
                // texture (a6m2_skin_b, light grey). Every paint renderer joins the list of its nearest part ancestor.
                var listed = new HashSet<Renderer>();
                var aps_ = root.GetComponentsInChildren<AeroPart>(true);
                foreach (var pp in aps_) foreach (var r in (List<Renderer>)G(G(pp, "damageMaterial"), "renderers")) if (r != null) listed.Add(r);
                var added = new List<string>();
                foreach (var r in root.GetComponentsInChildren<MeshRenderer>(true))
                {
                    if (r.sharedMaterials.Length == 0 || r.sharedMaterials[0] != mats["paint"] || listed.Contains(r) || r.gameObject.layer == 3) continue;
                    var owner = r.GetComponentInParent<AeroPart>(true);
                    if (owner == null) continue;
                    ((List<Renderer>)G(G(owner, "damageMaterial"), "renderers")).Add(r); added.Add(r.name + "->" + owner.name);
                }
                L($"r8e livery renderers: {added.Count} paint renderers added to their part's damageMaterial list: {string.Join(", ", added)}");
            }
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, Folder + "/A6M2.prefab");
            def.unitPrefab = prefab;
            EditorUtility.SetDirty(def);

            var op = ScriptableObject.CreateInstance<Blueprinter.OpAddAircraftToHangars>();
            op.aircraftJsonKey = JsonKey;
            foreach (var (unit, names) in HangarTargets())
                op.hangars.Add(new Blueprinter.OpAddAircraftToHangars.HangarTarget { hangarUnitJsonKey = unit, hangarNames = names.ToList() });
            AssetDatabase.CreateAsset(op, Folder + "/OpAddAircraftToHangars.asset");
            AssetDatabase.SaveAssets();
            L($"saved prefab, definition (parts {total} kg), {livs.Count} livery entries, {generatedMeshes.Count} meshes, hangar targets {op.hangars.Sum(h => h.hangarNames.Count)}");
            return prefab;
        }

        static IEnumerable<(string, string[])> HangarTargets()
        {
            yield return ("hangar_med", new[] { "hangar_med" });
            yield return ("revetment1", new[] { "revetment1" });
            if (!AllHangarTypes) yield break;
            yield return ("shelter1", new[] { "shelter1" });
            yield return ("SmallCarrier1", new[] { "hangar" });
            yield return ("AssaultCarrier1", new[] { "hangar_R1", "hangar_R2", "hangar_R3", "hangar_M" });
            yield return ("FleetCarrier1", new[] { "hangar_R1", "hangar_R2", "hangar_R3" });
        }

        static (float, LiveryData.TextureColor[]) LiveryJson(string file)
        {
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(Path.Combine(RepoTextures, "a6m2_liveries.json")));
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

        // =================================================================== offline check (design 10 round 1 CHECK ALL rows)
        static bool RunCheck(GameObject prefab)
        {
            var rows = new List<(string name, bool ok, string detail)>();
            void R(string n, bool ok, string d) => rows.Add((n, ok, d));
            var inst = (GameObject)Object.Instantiate(prefab);
            try
            {
                {
                    var ag = AtlasGuard1816.Check(inst, mats["paint"], Path.Combine(RepoTextures, "a6m2_atlas_manifest.json"), new Dictionary<string, string> { { "wing_fold_L_vis", "wing_fold_L" }, { "wing_fold_R_vis", "wing_fold_R" } });   // r8: the fold render meshes carry the parts' livery UV
                    R("livery atlas guard: UV0 of the paint meshes == the texture manifest", ag.Item1, ag.Item2);
                }
                var ac = inst.GetComponent<Aircraft>();
                var aps = inst.GetComponentsInChildren<AeroPart>(true);
                {   // r8e: every exterior paint renderer gets the livery (is in some part's damageMaterial.renderers)
                    var lst = new HashSet<Renderer>(aps.SelectMany(pp => ((List<Renderer>)G(G(pp, "damageMaterial"), "renderers")).Where(r => r != null)));
                    var miss = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.sharedMaterials.Length > 0 && r.sharedMaterials[0] == mats["paint"]
                        && r.gameObject.layer != 3 && !lst.Contains(r)).Select(r => r.name).ToArray();
                    R("liveries reach every exterior paint renderer (r8e: light-grey tailplane on dark liveries)", miss.Length == 0, miss.Length == 0 ? $"{lst.Count} renderers listed" : "missing: " + string.Join(", ", miss));
                }
                Transform T(string n) => inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == n);
                AeroPart P(string n) => aps.FirstOrDefault(p => (p.gameObject == inst ? "A6M2" : p.name) == n);
                // ---- propulsion
                var props = inst.GetComponentsInChildren<ConstantSpeedProp>(true);
                var tr = props.Length == 1 ? (Transmission)G(props[0], "transmission") : null;
                var te = tr != null ? tr.GetComponent<TurbineEngine>() : null;
                var bl = props.Length == 1 ? ((IList)G(props[0], "blades")).Cast<ConstantSpeedProp.PropBlade>().ToList() : new List<ConstantSpeedProp.PropBlade>();
                R($"engine + prop: one ConstantSpeedProp, 3 blades, TurbineEngine {EnginePower / 1000f} kW at {EngineRpm} rpm, prop {PropRpm} rpm, bladeLength {BladeLength}, efficiency {BladeEfficiency}, targetAOA {PropTargetAoA}",
                    props.Length == 1 && bl.Count == 3 && te != null && Mathf.Abs(te.maxPower - EnginePower) < 1f && Mathf.Abs(te.maxRPM - EngineRpm) < 1f && Mathf.Abs((float)G(props[0], "rpmLimit") - PropRpm) < 1f
                    && Mathf.Abs((float)G(props[0], "bladeLength") - BladeLength) < 1e-4f && Mathf.Abs((float)G(props[0], "bladeEfficiency") - BladeEfficiency) < 1e-4f && Mathf.Abs((float)G(props[0], "targetAOA") - PropTargetAoA) < 1e-4f,
                    props.Length == 1 ? $"blades {bl.Count}, power {te?.maxPower}, rpm {te?.maxRPM}, rpmLimit {G(props[0], "rpmLimit")}" : $"{props.Length} props");
                {   // memory prop-blade-one-renderer: ConstantSpeedProp toggles only blade.renderer; any other renderer under a blade stays over the blur
                    var bad = new List<string>();
                    foreach (var b in bl)
                    {
                        var bt = (Transform)G(b, "transform");
                        var rs = bt.GetComponentsInChildren<Renderer>(true);
                        if (rs.Length != 1 || rs[0] != b.renderer) bad.Add($"{bt.name}: {rs.Length} renderers");
                        if (b.renderer != null && b.renderer.sharedMaterials.Any(m => B25HTools.StockStructure.IsStructMat(m) || m.name != "A6M2_prop")) bad.Add($"{bt.name}: material {string.Join(",", b.renderer.sharedMaterials.Select(m => m?.name))}");
                    }
                    R("blades: each blade transform holds exactly ONE renderer (the blade's own), material A6M2_prop only, no internals", bl.Count == 3 && bad.Count == 0, bad.Count == 0 ? "3 x 1 renderer" : string.Join("; ", bad));
                    if (PropTipStripes)
                    {   // r7: the stripe texture reads the blade's radial UV0 (u 0 at the hub .. ~1 at the tip)
                        var spans = bl.Select(bb => { var mf = bb.renderer.GetComponent<MeshFilter>(); var uv = mf != null && mf.sharedMesh != null ? mf.sharedMesh.uv : new Vector2[0];
                            return uv.Length > 0 ? (uv.Min(q => q.x), uv.Max(q => q.x)) : (1f, 0f); }).ToList();
                        var pmat = bl.Count > 0 ? bl[0].renderer.sharedMaterial : null;
                        R("r7 prop tip stripes: one material with the stripe texture + r7b metallic map (paint stripes not metallic), every blade's UV0 u runs hub -> tip (max >= 0.95, min <= 0.35)",
                            pmat != null && pmat.GetTexture("_BaseMap") != null && pmat.GetTexture("_MetallicGlossMap") != null && pmat.IsKeywordEnabled("_METALLICSPECGLOSSMAP")
                            && spans.All(t => t.Item2 >= 0.95f && t.Item1 <= 0.35f),
                            string.Join("; ", spans.Select(t => $"u {t.Item1:F2}..{t.Item2:F2}")) + $", texture {(pmat != null && pmat.GetTexture("_BaseMap") != null ? pmat.GetTexture("_BaseMap").name : "none")}");
                    }
                }
                R("prop strike detector: trigger on layer 15; engine critical parts = engine section + prop", props.Length == 1 && G(props[0], "propStrikeDetector") is PropStrikeDetector d && d.gameObject.layer == 15 && ((Collider)G(props[0], "propDiscCollider")).isTrigger
                    && te != null && ((UnitPart[])G(te, "criticalParts")).Select(p => p.name).OrderBy(x => x).SequenceEqual(new[] { "fus_engine", "prop" }), "");
                // ---- guns
                var guns = inst.GetComponentsInChildren<Gun>(true);
                var g97 = guns.FirstOrDefault(g => g.name == "guns_type97");
                var g99 = guns.Where(g => g.name.StartsWith("cannon_type99_")).ToList();
                var m97 = g97 != null ? (Transform[])G(g97, "muzzles") : new Transform[0];
                R($"Type 97: one Gun on fus_engine, 2 muzzles, {T97Rate} rpm, {T97Rounds} rounds, info 'Type 97 7.7mm MG' (v0 745, pierce 90), tracer every {T97TracerRatio}th",
                    g97 != null && m97.Length == 2 && g97.GetComponentInParent<AeroPart>().name == "fus_engine" && Mathf.Abs((float)G(g97, "fireRate") - T97Rate) < 1 && (int)G(g97, "magazineCapacity") == T97Rounds
                    && (!OwnGunInfos || (g97.info.weaponName == "Type 97 7.7mm MG" && Mathf.Abs(g97.info.muzzleVelocity - 745f) < 0.1f && Mathf.Abs(g97.info.pierceDamage - 90f) < 0.1f)) && (int)G(g97, "tracerRatio") == T97TracerRatio,
                    g97 != null ? $"fireRate {G(g97, "fireRate")} mag {G(g97, "magazineCapacity")} info {g97.info?.weaponName} v0 {g97.info?.muzzleVelocity} pierce {g97.info?.pierceDamage}" : "missing");
                R($"Type 99: two Guns, one per wing_inner part (each leaves with its wing), {T99Rate} rpm, {T99RoundsPerGun} rounds each, info 'Type 99 20mm Cannon' (v0 600, pierce 300, blast 0.025), tracer every 3rd",
                    g99.Count == 2 && g99.Select(g => g.GetComponentInParent<AeroPart>().name).OrderBy(x => x).SequenceEqual(new[] { "wing_inner_L", "wing_inner_R" })
                    && g99.All(g => Mathf.Abs((float)G(g, "fireRate") - T99Rate) < 1 && (int)G(g, "magazineCapacity") == T99RoundsPerGun && (int)G(g, "tracerRatio") == 3
                    && (!OwnGunInfos || (g.info.weaponName == "Type 99 20mm Cannon" && Mathf.Abs(g.info.muzzleVelocity - 600f) < 0.1f && Mathf.Abs(g.info.blastDamage - 0.025f) < 1e-4f))),
                    string.Join(" | ", g99.Select(g => $"{g.name} on {g.GetComponentInParent<AeroPart>().name} rate {G(g, "fireRate")} mag {G(g, "magazineCapacity")} {g.info?.weaponName}")));
                // r8n: a Gun steps one tracerSeed per muzzle; with n muzzles and gcd(tracerRatio, n) > 1 every tracer lands on the same muzzle(s) for the
                // whole sortie and the other barrel looks dead (r8m Type 97: 2 muzzles, ratio 4). Every multi-muzzle Gun needs gcd(ratio, n) == 1, and the
                // tracer sequence over 2 x n x ratio rounds from every start seed 0..5 must reach every muzzle.
                {
                    var t8bad = new List<string>(); var t8rep = new List<string>();
                    foreach (var t8g in guns)
                    {
                        var t8mz = (Transform[])G(t8g, "muzzles"); int t8n = t8mz?.Length ?? 0, t8r = (int)G(t8g, "tracerRatio");
                        int t8min = int.MaxValue;
                        for (int t8s0 = 0; t8s0 < 6; t8s0++)
                        {
                            int t8s = t8s0; var t8hit = new int[Math.Max(t8n, 1)];
                            for (int t8k = 0; t8k < 2 * Math.Max(t8r, 1) * Math.Max(t8n, 1) + 6; t8k++)
                                for (int t8m = 0; t8m < t8n; t8m++) { t8s++; if (t8s > t8r) { t8s -= t8r; t8hit[t8m]++; } }   // Gun.cs 613-619
                            t8min = Math.Min(t8min, t8n > 0 ? t8hit.Min() : 0);
                        }
                        t8rep.Add($"{t8g.name} n{t8n} r{t8r} gcd{Gcd(t8r, Math.Max(t8n, 1))} minTracers/muzzle {t8min}");
                        if (t8n > 1 && (Gcd(t8r, t8n) != 1 || t8min == 0)) t8bad.Add(t8g.name);
                    }
                    R("r8n tracers: every multi-muzzle Gun has gcd(tracerRatio, muzzles) == 1 and puts tracers on every muzzle from any start seed 0..5 (Gun.cs tracerSeed per muzzle)",
                        t8bad.Count == 0 && g97 != null && m97.Length == 2 && Gcd((int)G(g97, "tracerRatio"), 2) == 1, string.Join(" | ", t8rep) + $"; bad [{string.Join(", ", t8bad)}]");
                    // the r8n fix touches only tracerRatio: two muzzles L / R, two flashes, fire rate / rounds unchanged, muzzles still ahead of the blade plane
                    var ps97 = g97 != null ? (((ParticleSystem[])G(g97, "muzzleParticles")) ?? new ParticleSystem[0]).Where(t8p => t8p != null).ToList() : new List<ParticleSystem>();
                    var fl97 = g97 != null ? new[] { "flash_gun_L", "flash_gun_R" }.Count(t8f => ps97.Any(t8p => t8p.name.StartsWith(t8f) || (t8p.transform.parent != null && t8p.transform.parent.name == t8f))) : -1;
                    R("r8n Type 97 pair: muzzles [muzzle_gun_L, muzzle_gun_R], muzzle flashes under flash_gun_L and flash_gun_R, one Gun (fire rate / rounds / muzzles unchanged; only tracerRatio 4 -> 5)",
                        g97 != null && m97.Select(t8t => t8t.name).SequenceEqual(new[] { "muzzle_gun_L", "muzzle_gun_R" }) && fl97 == 2 && guns.Count(t8x => t8x.name == "guns_type97") == 1
                        && Mathf.Abs((float)G(g97, "fireRate") - T97Rate) < 1 && (int)G(g97, "magazineCapacity") == T97Rounds,
                        g97 != null ? $"muzzles [{string.Join(", ", m97.Select(t8t => t8t.name))}] flashes {fl97} ratio {G(g97, "tracerRatio")}" : "missing");
                }
                // r6: Gun.ShotSound with fewer than 2 AudioSources indexes fireSounds -> it must be non-empty (and not null), else no round leaves the gun
                var badSound = guns.Where(g => g.GetComponents<AudioSource>().Length < 2 && (((AudioClip[])G(g, "fireSounds")) == null || ((AudioClip[])G(g, "fireSounds")).Length == 0
                    || ((AudioClip[])G(g, "fireSounds")).Any(c => c == null))).Select(g => g.name).ToList();
                R("every Gun can play its shot sound (ShotSound: < 2 AudioSources -> fireSounds[random] must exist; W1: the Type 99 fired 0 rounds without it)",
                    badSound.Count == 0, $"guns {guns.Length}; single-source guns {string.Join(", ", guns.Where(g => g.GetComponents<AudioSource>().Length < 2).Select(g => g.name + " clips " + (((AudioClip[])G(g, "fireSounds"))?.Length ?? -1)))}; bad [{string.Join(", ", badSound)}]");
                var hub = T("prop_hub");
                float bladeFront = bl.Count > 0 ? bl.Max(b => b.renderer.bounds.max.z) : 0f;
                float tipR = bl.Count > 0 ? bl.Max(b => b.renderer.GetComponent<MeshFilter>().sharedMesh.bounds.max.y) : 1.5f;
                R("synchroniser: Type 97 bullet origins >= 0.15 m ahead of the blades' front and outside the spinner",
                    m97.Length == 2 && m97.All(m => m.position.z - bladeFront >= 0.15f && new Vector2(m.position.x, m.position.y - hub.position.y).magnitude > 0.30f),
                    string.Join(" ", m97.Select(m => $"{m.name} dz {m.position.z - bladeFront:F3} r {new Vector2(m.position.x, m.position.y - hub.position.y).magnitude:F3}")));
                var m99 = g99.SelectMany(g => (Transform[])G(g, "muzzles")).ToList();
                var wingCols = new[] { "wing_inner_L", "wing_inner_R" }.Select(n => P(n)?.GetComponent<MeshCollider>()).Where(c => c != null).ToList();
                Physics.SyncTransforms();
                bool InsideCol(MeshCollider c, Vector3 p) => (c.ClosestPoint(p) - p).sqrMagnitude < 1e-8f;
                R("Type 99 origins outside the wing colliders and > 0.3 m outside the prop disc",
                    m99.Count == 2 && m99.All(m => wingCols.All(c => !InsideCol(c, m.position)) && new Vector2(m.position.x, m.position.y - hub.position.y).magnitude > tipR + 0.3f),
                    string.Join(" ", m99.Select(m => $"{m.name} r {new Vector2(m.position.x, m.position.y - hub.position.y).magnitude:F3} (disc {tipR:F3}) inside wing {wingCols.Any(c => InsideCol(c, m.position))}")));
                {   // FireClear (fixed guns): from every bullet origin, 60 m along the bore, nothing of ours is hit (BulletSim casts include triggers)
                    var ours = new HashSet<Collider>(inst.GetComponentsInChildren<Collider>(true));
                    var hits = new List<string>();
                    foreach (var m in m97.Concat(m99))
                        foreach (var h in Physics.RaycastAll(m.position, m.forward, 60f, ~0, QueryTriggerInteraction.Collide))
                            if (ours.Contains(h.collider)) hits.Add($"{m.name} -> {h.collider.name} at {h.distance:F2} m");
                    R("FireClear: every gun's bore line (60 m from the bullet origin, triggers included) hits nothing of the aircraft", hits.Count == 0 && m97.Concat(m99).Count() == 4,
                        hits.Count == 0 ? $"{m97.Concat(m99).Count()} bores clear; bore directions {string.Join(" ", m97.Concat(m99).Select(m => m.forward.ToString("F2")))}" : string.Join("; ", hits.Take(6)));
                }
                var wm = inst.GetComponentInChildren<WeaponManager>(true);
                var wantSets = new List<string> { "Type 97 7.7mm MGs", "Type 99 20mm Cannons", "Tail Hook" };
                if (Round2Stores) wantSets.Add("Bombs");
                if (Round2Stores && Kamikaze) wantSets.Add("Special");
                R($"hardpoint sets (design 2.4 HUD order): {string.Join(" | ", wantSets)}", wm.hardpointSets.Select(s => s.name).SequenceEqual(wantSets),
                    string.Join(" | ", wm.hardpointSets.Select(s => $"{s.name}: {string.Join(",", s.weaponOptions.Where(o => o != null).Select(o => $"{o.jsonKey} x{o.ammo}"))}")));
                R("ammo mounts: A6M2_ammo_type97 500, A6M2_ammo_type99 120 (2 x 60), gun ammo, no gear safety",
                    wm.hardpointSets[0].weaponOptions.Last() is WeaponMount a97 && a97.jsonKey == "A6M2_ammo_type97" && a97.ammo == T97Rounds && a97.GunAmmo && !a97.GearSafety
                    && wm.hardpointSets[1].weaponOptions.Last() is WeaponMount a99 && a99.jsonKey == "A6M2_ammo_type99" && a99.ammo == 2 * T99RoundsPerGun && a99.GunAmmo && wm.hardpointSets[1].hardpoints.Count == 2, "");
                // ---- hook
                var hk = wm.hardpointSets[2].weaponOptions.LastOrDefault();
                var hookTH = hk != null && hk.prefab != null ? hk.prefab.GetComponent<TailHook>() : null;
                R("tail hook: own mount (tailHook), our A-frame rendered (visible stowed), stowed > 0 > deployed", hk != null && hk.tailHook && hookTH != null && (float)G(hookTH, "stowedAngle") > 0f && (float)G(hookTH, "deployedAngle") < 0f
                    && hookTH.GetComponentsInChildren<MeshRenderer>(true).Length == 1, hookTH != null ? $"stowed {G(hookTH, "stowedAngle")} deployed {G(hookTH, "deployedAngle")}, renderers {hookTH.GetComponentsInChildren<MeshRenderer>(true).Length}" : "missing");
                {
                    var hpT = wm.hardpointSets[2].hardpoints.FirstOrDefault()?.transform;
                    var tailC = P("fus_tail")?.GetComponent<MeshCollider>();
                    bool inTail = hpT != null && tailC != null && tailC.sharedMesh.bounds.Contains(tailC.transform.InverseTransformPoint(hpT.position));
                    R("tail hook hinge inside the fus_tail collider bounds (Linecast origin)", inTail, hpT != null ? $"hinge {hpT.position.ToString("F3")}" : "missing");
                }
                // ---- gear
                var lgs = inst.GetComponentsInChildren<LandingGear>(true).Where(g => !g.name.EndsWith(GripGear.Suffix)).ToArray();
                var mains = lgs.Where(g => (bool)G(g, "braked")).ToList();
                var tailG = lgs.FirstOrDefault(g => IsTailW(g));
                {
                    var det = new List<string>(); bool ok = mains.Count == 2 && tailG != null;
                    foreach (var g in mains)
                    {
                        var side = g.name.Contains("_L_") ? "L" : "R";
                        var hinge = (Transform)G(g, "gearHinge"); float f = (float)G(g, "foldDegrees");
                        var wheel = ((Transform[])G(g, "wheels"))[0];
                        var save = hinge.localRotation; hinge.localRotation = Quaternion.Euler(f, 0, 0);
                        var up = wheel.position; hinge.localRotation = save;
                        var want = UnityPos(contract["gear"]["main"][side]["wheel_up"]);
                        float err = (up - want).magnitude;
                        ok &= Mathf.Abs(Mathf.Abs(f) - (float)contract["gear"]["main"][side]["retract_deg"]) < 0.5f && err < 0.03f && Mathf.Abs(Quaternion.Angle(hinge.localRotation, Quaternion.identity)) < 0.01f;
                        var doors = (List<LandingGear.GearDoor>)G(g, "gearDoors");
                        ok &= !InnerWellDoors || (doors.Count == 1 && doors[0].transform != null && Mathf.Abs(Mathf.Abs(doors[0].openAngle.z) - 85f) < 0.5f);
                        det.Add($"{g.name} fold {f:F1} stowed wheel {err * 1000:F0} mm from target, doors {doors.Count} open {(doors.Count > 0 ? doors[0].openAngle.z : 0):F1}, extendedDrag {G(g, "extendedDrag")}");
                    }
                    ok &= tailG != null && (float)G(tailG, "foldDegrees") < 1f;
                    R("gear: two retracting mains (inward about the measured axis, 84.7 deg, stowed wheel within 30 mm of the contract), inner well doors 85 deg; fixed castoring tail wheel",
                        ok, string.Join(" | ", det) + $" | tail fold {(tailG != null ? G(tailG, "foldDegrees") : "-")}");
                }
                {
                    bool gok = GripGear.Verify(inst, MainBrakeShare, MainGearFriction, GripFriction, BrakedRolling, GripRolling, GearMainK, out string gd);
                    R($"split mains (Mk I / FD-32 accepted stack): braked leg {MainGearFriction} share {MainBrakeShare} + grip leg {GripFriction}", gok, gd);
                    bool cok = GripGear.VerifyCastor(inst, MainCastorRange, MainCastorAlign, out string cdet);
                    R($"castoring mains +-{MainCastorRange} align {MainCastorAlign}; tail wheel lock {TailSteeringLock}, aligning {TailAligning}, steeringSpeed 60",
                        cok && tailG != null && Mathf.Abs((float)G(tailG, "steeringLock") - TailSteeringLock) < 1e-4f && Mathf.Abs((float)G(tailG, "aligningStrength") - TailAligning) < 1e-4f, cdet);
                }
                // ---- mass, CoM (parts at collider-bounds centres + fuel at its tank, the NimrodBuild rule), MAC
                float mass = aps.Sum(p => p.mass);
                Vector3 com = Vector3.zero; float mt = 0f;
                foreach (var p in aps) { var mc = p.GetComponent<MeshCollider>(); var c = mc != null ? p.transform.TransformPoint(mc.sharedMesh.bounds.center) : p.transform.position; com += c * p.mass; mt += p.mass; }
                foreach (var ft in inst.GetComponentsInChildren<FuelTank>(true)) { float fm = (float)G(ft, "fuelCapacity") * 0.7f; var pc = ft.GetComponent<MeshCollider>(); var c = pc != null ? ft.transform.TransformPoint(pc.sharedMesh.bounds.center) : ft.transform.position; com += c * fm; mt += fm; }
                com /= mt;
                L("CoM rows (part, kg, collider-bounds centre z / y): " + string.Join("; ", aps.Select(p => { var mc = p.GetComponent<MeshCollider>(); var c = mc != null ? p.transform.TransformPoint(mc.sharedMesh.bounds.center) : p.transform.position; return $"{(p.gameObject == inst ? "A6M2" : p.name)} {p.mass} {c.z:F3} {c.y:F3}"; })));
                {   // GroundGrip189 IzzFor(A6M2): the root rigidbody's yaw inertia of the built prefab with every collider on it (the Nimrod method)
                    var rbi = inst.GetComponent<Rigidbody>(); Physics.SyncTransforms();
                    L($"Izz (root rigidbody inertiaTensor, all colliders, mass {rbi.mass:F0} kg): {rbi.inertiaTensor.ToString("F0")} rotation {rbi.inertiaTensorRotation.eulerAngles.ToString("F1")}");
                }
                float macLe = (float)contract["mac"]["le_z"], mac = (float)contract["mac"]["len"];
                float pct = (macLe - com.z) / mac;
                R("CoM 27-30 % MAC (parts at collider-bounds centres + fuel 70 % in its tank's part)", pct >= 0.27f && pct <= 0.30f, $"CoM z {com.z:F3} y {com.y:F3}, MAC LE z {macLe:F3} len {mac:F3}: {pct * 100:F1} % MAC; total {mt:F0} kg");
                R(R1bLoads ? "parts mass 1,950-1,970 kg (r1b: structure 1,641 + pilot 80 + oil / accessories 150 + gear 88 as part mass; LandingGear.mass is never added by the game)"
                           : "parts mass 1,600-1,700 kg (structure 1,641 per a6m2_spec.MASSES; gear 88 kg as LandingGear.mass)",
                    R1bLoads ? mass > 1950 && mass < 1970 : mass > 1600 && mass < 1700, $"{mass} kg");
                {
                    var mainAx = mains.Select(g => ((Transform)G(g, "axle")).position).ToList();
                    float mz = mainAx.Average(v => v.z);
                    var cps = mains.Select(g => ((Transform)G(g, "castPoint")).position).ToList();
                    float wr = (float)G(mains[0], "wheelRadius");
                    float cy = cps.Average(v => v.y) - ((float)G(mains[0], "suspensionTravel") - wr) - wr;
                    float muB = MainGearFriction * MainBrakeShare;
                    float ang = Mathf.Atan2(cps.Average(v => v.z) - com.z, com.y - cy) * Mathf.Rad2Deg, muDeg = Mathf.Atan(muB) * Mathf.Rad2Deg;
                    R($"brake nose-over: CoM angle over the main contact {ang:F1} deg >= atan(braking friction {muB:F2}) {muDeg:F1} + 3.5; CoM aft of the mains", ang - muDeg >= 3.5f && mz > com.z,
                        $"main axle z {mz:F3}, CoM ({com.z:F3}, {com.y:F3}), ground y {cy:F3}; CoM {mz - com.z:F2} m behind the axle");
                }
                float area = aps.Sum(p => (float)G(p, "wingArea"));
                float wingA = aps.Where(p => p.gameObject == inst || p.name.StartsWith("wing_") || p.name.StartsWith("aileron_") || p.name.StartsWith("flap_")).Sum(p => (float)G(p, "wingArea"));
                R("wing area 22.47 m^2 (centre 2.91 + 2 x (inner 3.99 + mid 2.78 + tip 0.54 + fold 0.54 + aileron 1.19 + flap 0.74)) +- 0.1", Mathf.Abs(wingA - 22.47f) < 0.1f, $"wing {wingA:F2}, all lifting {area:F2}");
                {
                    var bad = new List<string>(); int nj = 0, n100 = 0;
                    foreach (var p in aps)
                    {
                        var owner = p.gameObject == inst ? "A6M2" : p.name;
                        var js = (PartJoint[])G(p, "joints"); nj += js.Length;
                        if (owner != "A6M2" && js.Length == 0) bad.Add(owner + " unjoined");
                        foreach (var j in js) { int want = WingSolverOwner(owner) ? WingSolverIterations : 6; if (j.solverIterations != want) bad.Add($"{owner}->{j.connectedPart?.name} {j.solverIterations}"); if (j.solverIterations == WingSolverIterations) n100++; }
                    }
                    R($"joints: every part joined; every joint owned by a wing_* part solverIterations {WingSolverIterations} (memory multipart-wing-joint-solver), others 6", bad.Count == 0 && n100 > 0, bad.Count == 0 ? $"{nj} joints, {n100} at {WingSolverIterations}" : string.Join("; ", bad.Take(8)));
                }
                R("crash impact damage: every airframe part has its own ImpactDamage (rudder off, as stock)", aps.Where(p => p.name != "prop" && p.name != "rudder").All(p => { var d = G(p, "impactDamage"); return d != null && (float)G(d, "threshold") > 0f; })
                    && aps.Where(p => p.name != "prop").Select(p => G(p, "impactDamage")).Distinct().Count() == aps.Count(p => p.name != "prop"), "");
                // ---- flaps
                {
                    var hl = inst.GetComponentsInChildren<HighLiftDevice>(true);
                    var det = new List<string>(); bool ok = !SplitFlaps || hl.Length == 2;
                    foreach (var h in hl)
                    {
                        var mps = ((IList)G(h, "movingParts")).Cast<object>().ToList();
                        var vis = (Transform)G(mps[0], "transform"); var ang = (Vector3)G(mps[0], "anglesDeployed");
                        var plate = vis.GetComponentInChildren<MeshRenderer>(true);
                        var c0 = plate.bounds.center.y; vis.localEulerAngles = ang; var c1 = plate.bounds.center.y; vis.localEulerAngles = Vector3.zero;
                        ok &= c1 < c0 - 0.05f && Mathf.Abs((float)G(h, "deployedArea") - FlapDeployedArea) < 1e-4f && mps.Count == 2;
                        det.Add($"{h.name}: plate {ang.x:F0} deg lowers its centre {(c0 - c1) * 1000:F0} mm, lift frame {((Vector3)G(mps[1], "anglesDeployed")).x:F0}, area {G(h, "deployedArea")}");
                    }
                    R("split flaps: HighLiftDevice per side, the plate swings DOWN 60 deg, lift frame 15 deg, deployedArea 1.2", ok, string.Join(" | ", det));
                }
                // ---- crew, cockpit, HUD
                R("1 pilot (bail-out), cockpit view point set (round-1 placeholder cockpit)", ac.pilots.Length == 1 && !(bool)G(ac.pilots[0], "ejectionSeat") && ac.cockpitViewPoint != null, $"eye {ac.cockpitViewPoint?.position.ToString("F3")}");
                var cr = (Renderer[])G(ac, "cockpitRenderers");
                R("cockpit-layer copies on layer 3 (fuselage, engine, centre section, canopy glass as the stock cockpit-side glass)", cr.Length >= 5 && cr.All(r => r.gameObject.layer == 3), $"{cr.Length} renderers");
                var prm = ((AircraftDefinition)ac.definition).aircraftParameters;
                R("HUD extras (COIN_HUDExtras), status display, map icon", prm.HUDExtras != null && prm.StatusDisplay != null && ac.definition.mapIcon != null, "");
                R($"r6 AI speeds: takeoffSpeed {(R6AiSpeeds ? AiTakeoffSpeedR6 : 36f)} m/s (AI rotation from 0.7 x, AI landing speed = takeoffSpeed; r4b lift-off 41, stall 33 m/s)",
                    Mathf.Abs(prm.takeoffSpeed - (R6AiSpeeds ? AiTakeoffSpeedR6 : 36f)) < 0.01f && (!R6AiSpeeds || prm.takeoffSpeed >= 1.2f * 33f), $"takeoffSpeed {prm.takeoffSpeed}, PIDref {prm.PIDReferenceAirspeed}, maxSpeed {prm.maxSpeed}");
                {   // round 5 (design 9.2): 8 rows, 4 per faction, IJN first on both, exact names in menu order
                    var want = new[] { "IJN Grey-White (1941)", "BDF Temperate Camo", "BDF Matte Gray", "BDF Navy", "IJN Grey-White (1941)", "PALA Desert Camo", "PALA Matte Black", "PALA Navy Splinter" };
                    var got = prm.liveries.Select(l => l.name).ToArray();
                    var facs = prm.liveries.Select(l => l.faction).ToArray();
                    R("liveries (round 5): 8 rows, 4 per faction, IJN Grey-White first on both, design 9.2 names and order", got.SequenceEqual(want)
                        && facs.Take(4).Distinct().Count() == 1 && facs.Skip(4).Distinct().Count() == 1 && facs[0] != facs[4], string.Join(", ", got));
                }
                R("loadouts: loadouts[0] empty, loadouts[1] = guns + hook (read unvetted as the fallback, design 3.2); StandardLoadouts[0] 'Fighter'",
                    prm.loadouts.Count >= 2 && prm.loadouts[1].weapons.Count(w => w != null) == 3 && prm.StandardLoadouts.Length >= 1, $"{prm.loadouts.Count} loadouts, {prm.StandardLoadouts.Length} standard");
                // ---- round 2 / 3 stores (design 2.2-2.4, 3.2-3.4, build plan rounds 2-3)
                if (Round2Stores)
                {
                    var hsB = wm.hardpointSets.FirstOrDefault(h => h.name == "Bombs");
                    var nm = hsB?.weaponOptions.LastOrDefault();
                    var ni = nm?.info; var nbp = ni?.weaponPrefab;
                    var nmis = nbp?.GetComponent<Missile>(); var ncap = nbp?.GetComponent<CapsuleCollider>(); var nseek = nbp?.GetComponent<OpticalSeekerBomb>();
                    var nmf = nbp?.GetComponent<MeshFilter>();
                    bool pivotIn = ncap != null && Mathf.Abs(ncap.center.z) < ncap.height / 2f - 0.01f && ncap.center.magnitude < 0.02f;
                    bool axisZ = nmf != null && nmf.sharedMesh.bounds.size.z > 2f * nmf.sharedMesh.bounds.size.x && nmf.sharedMesh.bounds.size.z > 2f * nmf.sharedMesh.bounds.size.y;
                    R($"60 kg No.6: Bombs set on both wing_inner parts, own mount / info / definition / prefab, yield {NO6Yield}, armDelay 2.0, pivot inside its capsule (> 10 mm), long axis = forward",
                        hsB != null && hsB.hardpoints.Count == 2 && hsB.hardpoints.All(h => h.part.name.StartsWith("wing_inner_")) && nm != null && nm.jsonKey == "A6M2_no6_x1" && nm.ammo == 1 && nm.prefab != null
                        && ni != null && ni.name == "A6M2_no6_info" && nmis != null && Mathf.Approximately((float)G(nmis, "blastYield"), NO6Yield) && nmis.definition != null && nmis.definition.jsonKey == "A6M2_no6"
                        && nseek != null && Mathf.Approximately((float)G(nseek, "armDelay"), 2.0f) && pivotIn && axisZ && nm.prefab.GetComponentsInChildren<MountedMissile>(true).Length == 1,
                        $"mount {nm?.jsonKey} prefab {nm?.prefab?.name}, info {ni?.name}, bomb {nbp?.name}, yield {(nmis != null ? G(nmis, "blastYield") : "-")}, capsule c {ncap?.center.ToString("F3")} h {ncap?.height:F2}, axisZ {axisZ}, mass {nm?.mass}");
                }
                if (Round2Stores && Kamikaze)
                {
                    var hsS = wm.hardpointSets.FirstOrDefault(h => h.name == "Special");
                    var hsB = wm.hardpointSets.FirstOrDefault(h => h.name == "Bombs");
                    int iB = Array.IndexOf(wm.hardpointSets, hsB), iS = Array.IndexOf(wm.hardpointSets, hsS);
                    var tm = hsS?.weaponOptions.LastOrDefault(); var ti = tm?.info; var tbp = ti?.weaponPrefab;
                    var tmis = tbp?.GetComponent<Missile>(); var tseek = tbp?.GetComponent<OpticalSeeker>();
                    bool mountEvent = tm != null && (bool)G(tm, "isEventContent") && !tm.IsAllowed(false) && tm.IsAllowed(true);
                    var tdef = tmis?.definition;
                    bool defEvent = tdef != null && (bool)G(tdef, "isEventContent") && tdef.dontAutomaticallyAddToEncyclopedia;
                    bool acNotEvent = ac.definition.IsAllowed(false);
                    R("charge: Special set (centre, root part, LAST row) precludes Bombs and the reverse; mount and definition are Event Content; the A6M2 definition is not",
                        hsS != null && iS == wm.hardpointSets.Length - 1 && hsS.hardpoints.Count == 1 && hsS.hardpoints[0].part.gameObject == inst && hsS.precludingHardpointSets.SequenceEqual(new[] { (byte)iB })
                        && hsB.precludingHardpointSets.SequenceEqual(new[] { (byte)iS }) && mountEvent && defEvent && acNotEvent && tm.jsonKey == "A6M2_tokko_x1",
                        $"Bombs {iB} precl [{string.Join(",", hsB?.precludingHardpointSets ?? new List<byte>())}], Special {iS} precl [{string.Join(",", hsS?.precludingHardpointSets ?? new List<byte>())}], mount event {mountEvent}, def event {defEvent}, A6M2 allowed without event {acNotEvent}");
                    R("charge: GearSafety + GroundSafety on, AI never fires it (targetRequirements.maxAltitude -1), boresight, not bomb / missile / gun / nuclear",
                        tm != null && tm.GearSafety && tm.GroundSafety && ti != null && ti.targetRequirements.maxAltitude == -1f && ti.boresight && !ti.bomb && !ti.missile && !ti.gun && !ti.nuclear,
                        $"gear {tm?.GearSafety} ground {tm?.GroundSafety} maxAlt {ti?.targetRequirements.maxAltitude} boresight {ti?.boresight}");
                    R($"charge prefab: yield {TokkoYield}, pierce 350, OpticalSeeker (Genie set-up) timeFuse {TokkoTimeFuse}, armDelay 0, no proximity fuse, no OpticalSeekerBomb, pivot inside its capsule",
                        tmis != null && Mathf.Approximately((float)G(tmis, "blastYield"), TokkoYield) && Mathf.Approximately((float)G(tmis, "pierceDamage"), 350f) && tseek != null
                        && Mathf.Approximately((float)G(tseek, "timeFuse"), TokkoTimeFuse) && (float)G(tseek, "armDelay") == 0f && !tseek.proximityFuse && tbp.GetComponent<OpticalSeekerBomb>() == null
                        && tbp.GetComponent<CapsuleCollider>() != null && tbp.GetComponent<CapsuleCollider>().center.magnitude < 0.02f,
                        $"{tbp?.name}: yield {(tmis != null ? G(tmis, "blastYield") : "-")}, seeker {tseek?.GetType().Name} timeFuse {(tseek != null ? G(tseek, "timeFuse") : "-")}");
                    var refs = new List<string>();
                    for (int i = 0; i < prm.loadouts.Count; i++) if (prm.loadouts[i].weapons.Any(w => w != null && w.jsonKey == "A6M2_tokko_x1")) refs.Add($"loadouts[{i}]");
                    foreach (var sl in prm.StandardLoadouts) if (sl.loadout.weapons.Any(w => w != null && w.jsonKey == "A6M2_tokko_x1")) refs.Add("StandardLoadout " + sl.Name);
                    R("design 3.2: NO loadouts entry and NO StandardLoadout references the charge; loadouts.Count >= 2; StandardLoadouts exist (the editor seeds from [0])",
                        refs.Count == 0 && prm.loadouts.Count >= 2 && prm.StandardLoadouts.Length >= 1 && prm.loadouts.All(l => l.weapons.Count == wm.hardpointSets.Length) && prm.StandardLoadouts.All(l => l.loadout.weapons.Count == wm.hardpointSets.Length),
                        refs.Count == 0 ? $"{prm.loadouts.Count} loadouts, standard [{string.Join(", ", prm.StandardLoadouts.Select(l => l.Name))}]" : "REFERENCED: " + string.Join(", ", refs));
                }
                if (OwnWeaponIcons)
                {
                    var infos = wm.hardpointSets.SelectMany(h => h.weaponOptions).Where(o => o != null && o.info != null && !o.tailHook).Select(o => o.info).Distinct().ToList();
                    var bad = infos.Where(i => i.weaponIcon == null || !i.weaponIcon.name.StartsWith("a6m2_icon_") || i.weaponIcon.rect.width != 512 || i.weaponIcon.rect.height != 256).Select(i => i.name).ToList();
                    R("own HUD icons on every weapon (512 x 256, our models): Type 97, Type 99, No.6, charge", bad.Count == 0 && infos.Count == (Round2Stores ? (Kamikaze ? 4 : 3) : 2),
                        string.Join(", ", infos.Select(i => $"{i.name}:{i.weaponIcon?.name}")) + (bad.Count > 0 ? " BAD " + string.Join(",", bad) : ""));
                }
                string abBad = InvisibleAirbrakeProblems(inst, InvisibleAirbrake, InvisibleAirbrakeDrag, InvisibleAirbrakeOpenSpeed, out string abDet);
                R($"invisible airbrake (memory airbrake-works-on-landing): one stock Airbrake on the root, drag {InvisibleAirbrakeDrag}, no transforms", abBad == "", abDet + (abBad == "" ? "" : "; WRONG: " + abBad));
                var stockMesh = inst.GetComponentsInChildren<MeshFilter>(true).Where(m => m.sharedMesh != null && !AssetDatabase.GetAssetPath(m.sharedMesh).StartsWith(Folder)).Select(m => m.name).ToList();
                R("every mesh is ours (mesh bank in the mod folder)", stockMesh.Count == 0, string.Join(", ", stockMesh.Take(6)));
                {
                    var bad = new List<string>();
                    foreach (var o in inst.GetComponentsInChildren<Component>(true).Where(c => c != null))
                    {
                        var so = new SerializedObject(o); var it = so.GetIterator();
                        while (it.NextVisible(true)) if (it.propertyType == SerializedPropertyType.ObjectReference && it.objectReferenceValue != null)
                            { var p = AssetDatabase.GetAssetPath(it.objectReferenceValue); if (p.ToLowerInvariant().Contains("wt_a6m2") || p.ToLowerInvariant().Contains("/refs/")) bad.Add(p); }
                    }
                    R("no reference into nuclearoption-ref\\refs (WT reference) anywhere in the prefab", bad.Count == 0, bad.Count == 0 ? "none" : string.Join(", ", bad.Distinct().Take(5)));
                }
                var def = (AircraftDefinition)ac.definition;
                R("definition: A6M2, 12.0 x 9.06 x 3.05 m, spawn offset = level wheel contact + 0.03 / z +0.7, rest rotation = 3-point attitude",
                    def.jsonKey == JsonKey && Mathf.Abs(def.width - 12f) < 0.01f && Mathf.Abs(def.length - 9.06f) < 0.01f && Mathf.Abs(def.spawnOffset.y - ((float)contract["level_wheel_contact_height"] + SpawnLift)) < 0.001f
                    && Mathf.Abs(def.restRotation.x + (float)contract["three_point_deg"]) < 0.01f, $"spawnOffset {def.spawnOffset.ToString("F3")}, restRotation {def.restRotation.ToString("F2")}, mass {((UnitDefinition)def).mass}");
                {
                    var rud = aps.FirstOrDefault(p => p.name == "rudder");
                    var ls = LiftSpawn1911.Check(inst.transform, rud != null ? rud.transform : null, def.spawnOffset, def.restRotation);
                    R($"carrier-lift spawn: rudder aft end >= {LiftSpawn1911.MinMargin} m ahead of the stock lift backstops (Annex / Hyperion hangar_R1)", ls.Item1, ls.Item2);
                }
                var op = AssetDatabase.LoadAssetAtPath<Blueprinter.OpAddAircraftToHangars>(Folder + "/OpAddAircraftToHangars.asset");
                R("hangars: medium hangar, revetment, shelter, Cursor LFD, Annex R1-R3 + M, Hyperion R1-R3 (11 names)", op != null && op.hangars.Sum(h => h.hangarNames.Count) == 11,
                    op != null ? string.Join("; ", op.hangars.Select(h => h.hangarUnitJsonKey + ":" + string.Join(",", h.hangarNames))) : "missing");
                {
                    var so = new SerializedObject(inst.GetComponentInChildren<ControlsFilter>(true));
                    float Fv(string n) => so.FindProperty("flyByWire." + n).floatValue;
                    R($"FBW: g 7, corner 88, alpha limiter {AlphaLimiter}, maxRollSpeed {FbwMaxRollSpeed}, maxRollAngularVel {FbwMaxRollAngVel}, rollTightness {FbwRollTightness}, takeoff {FbwTakeoffSpeed}", Mathf.Abs(Fv("gLimitPositive") - 7f) < 0.01f && Mathf.Abs(Fv("cornerSpeed") - 88f) < 0.01f
                        && Mathf.Abs(Fv("alphaLimiter") - AlphaLimiter) < 0.01f && Mathf.Abs(Fv("maxRollSpeed") - FbwMaxRollSpeed) < 0.001f && Mathf.Abs(Fv("maxRollAngularVel") - FbwMaxRollAngVel) < 0.001f && Mathf.Abs(Fv("rollTightness") - FbwRollTightness) < 0.001f && Mathf.Abs(Fv("takeoffSpeed") - FbwTakeoffSpeed) < 0.01f, "");
                }
                if (PeriodCockpit)
                {   // ---- round 4 cockpit (design 8)
                    var want = new[] { "gauge_asi_needle", "gauge_alt_needle", "gauge_alt_needle_short", "gauge_vsi_needle", "gauge_rpm_needle", "gauge_boost_needle",
                        "gauge_oilp_needle", "gauge_oilt_needle", "gauge_fuel_needle", "gauge_turn_needle", "gauge_turn_slip", "gauge_horizon_card", "gauge_compass_card" };
                    var allT = inst.GetComponentsInChildren<Transform>(true);
                    var missing = want.Where(n => !allT.Any(t => t.name == n)).ToList();
                    var noCopy = want.Where(n => { var t = allT.FirstOrDefault(x => x.name == n); return t == null || !t.GetComponentsInChildren<MeshRenderer>(true).Any(r => r.gameObject.layer == 3); }).ToList();
                    R("period dials: 13 movers (ASI, altimeter 2 hands, climb, rpm, boost, oil P / T, fuel, turn + slip, horizon card, compass card), each with its cockpit-layer copy",
                        missing.Count == 0 && noCopy.Count == 0, $"missing [{string.Join(",", missing)}] no copy [{string.Join(",", noCopy)}]");
                    var ckc = inst.GetComponentInChildren<global::Cockpit>(true);
                    bool parts4 = new[] { "cockpit_panel", "cockpit_breech_L", "cockpit_breech_R", "cockpit_sight", "cockpit_seat", "cockpit_stick", "cockpit_stick_base", "cockpit_throttle", "cockpit_consoles" }.All(n => allT.Any(t => t.name == n));
                    bool noModern = !allT.Any(t => { var n = t.name.ToLowerInvariant(); return n.Contains("pedal") || n.Contains("rudderbar") || n.StartsWith("mfd") || n == "ejectionseat"; });
                    var rmat = mats.TryGetValue("reticle", out var rm) ? rm : null;
                    R("period cockpit: panel, Type 97 breeches, Type 98 sight (emissive reticle), seat, stick (Cockpit.Joystick), throttle (Cockpit.Throttle), consoles; no pedals, no MFD, no stock ejection seat",
                        parts4 && noModern && ckc != null && ((IList)G(ckc, "joysticks")).Count == 1 && ((IList)G(ckc, "throttles")).Count == 1 && rmat != null && rmat.IsKeywordEnabled("_EMISSION")
                        && mats["gauges"].GetTexture("_BaseMap") != null, $"parts {parts4}, no modern {noModern}, joysticks {(ckc != null ? ((IList)G(ckc, "joysticks")).Count : -1)}, throttles {(ckc != null ? ((IList)G(ckc, "throttles")).Count : -1)}");
                }
                if (SlidingHood)
                {
                    var cans = (Canopy[])G(ac, "canopies");
                    var cn = cans != null && cans.Length == 1 ? cans[0] : null;
                    string det = "no canopy"; bool ok = false;
                    if (cn != null)
                    {
                        var hgs = (Array)G(cn, "canopyHinges");
                        var hg = hgs.Length == 1 ? (Transform)G(hgs.GetValue(0), "transform") : null;
                        float ang = hgs.Length == 1 ? (float)G(hgs.GetValue(0), "hingeAngle") : 0f;
                        var hoodR = inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "canopy_hood")?.GetComponent<MeshRenderer>();
                        if (hg != null && hoodR != null)
                        {
                            var c0 = hoodR.bounds.center; var save = hg.localEulerAngles;
                            hg.localEulerAngles = Vector3.right * ang; var c1 = hoodR.bounds.center; hg.localEulerAngles = save;
                            float aft = c0.z - c1.z, drop = c0.y - c1.y;
                            ok = aft > 0.45f && aft < 0.55f && Mathf.Abs(drop) < 0.03f && cn.ejectionTransform != null && cn.attachedPart != null && cn.ejectionCollider != null && !cn.ejectionCollider.enabled
                                 && ((Renderer[])G(cn, "glassRenderers")).Length == 1;
                            det = $"open: {aft * 1000:F0} mm aft, {drop * 1000:F0} mm down; eject frame {cn.ejectionTransform.name}, mass {cn.mass}";
                        }
                    }
                    R($"sliding hood = stock Canopy: opens {HoodSlide} m aft (hinge {HoodPivotDrop} m below), jettisoned before the bail-out (pilot no longer exits through the glass)", ok, det);
                    if (cn != null)
                    {   // r7: Canopy.EjectionSequence moves the ejection body to the Canopy component's own position -> the component must sit at the hood
                        var hoodR2 = inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "canopy_hood")?.GetComponent<MeshRenderer>();
                        float dj = hoodR2 != null ? Vector3.Distance(cn.transform.position, hoodR2.bounds.center) : 99f;
                        R("r7 hood jettison: the Canopy component sits on the ejection transform at the hood centre (the jettison moves the hood to the component's position)",
                            cn.transform == cn.ejectionTransform && dj < 0.3f, $"component on {cn.transform.name}, {dj:F2} m from the hood centre, eject frame {cn.ejectionTransform?.name}");
                    }
                }
                {   // r4b fixes from the r1b flight test: tail areas, FBW roll law (row above), flap schedule
                    var stabs = aps.Where(p => p.name.StartsWith("stab_")).ToList(); var elevs = aps.Where(p => p.name.StartsWith("elevator_")).ToList();
                    var hlds = inst.GetComponentsInChildren<HighLiftDevice>(true);
                    bool ok = stabs.Count == 2 && elevs.Count == 2 && stabs.All(p => Mathf.Abs((float)G(p, "wingArea") - StabArea) < 1e-4f) && elevs.All(p => Mathf.Abs((float)G(p, "wingArea") - ElevArea) < 1e-4f)
                        && hlds.Length == 2 && hlds.All(h => Mathf.Abs((float)G(h, "speedDeployed") - FlapSpeedDeployed) < 1e-4f && Mathf.Abs((float)G(h, "speedRetracted") - FlapSpeedRetracted) < 1e-4f);
                    R($"r4b: stab {StabArea} / elevator {ElevArea} m^2 per side (game elevator 0.4 x the model), flaps full below {FlapSpeedDeployed} m/s TAS, up above {FlapSpeedRetracted}", ok,
                        $"stab {string.Join("/", stabs.Select(p => G(p, "wingArea")))}, elev {string.Join("/", elevs.Select(p => G(p, "wingArea")))}, flaps {string.Join("/", hlds.Select(h => G(h, "speedDeployed") + "-" + G(h, "speedRetracted")))}");
                }
                {   // r1b fixes from the first in-game run (flags R1bLoads / R1bTailGear / R1bTakeoff / R1bTaxiThrust / ZeroFlares)
                    var det = new List<string>(); bool ok = true;
                    var tg = inst.GetComponentsInChildren<LandingGear>(true).FirstOrDefault(g => !g.name.EndsWith(GripGear.Suffix) && IsTailW(g));
                    if (tg != null)
                    {
                        ok &= Mathf.Approximately((float)G(tg, "springRate"), GearTailK) && Mathf.Approximately((float)G(tg, "dampingRate"), GearTailC)
                            && Mathf.Approximately((float)G(tg, "maxCompression"), GearTailMaxComp) && (!R1bTailGear || Mathf.Approximately((float)G(tg, "contactArea"), GearTailContactArea));
                        det.Add($"tail k {G(tg, "springRate")} c {G(tg, "dampingRate")} break {G(tg, "maxCompression")} area {G(tg, "contactArea")}");
                    }
                    else { ok = false; det.Add("no tail wheel"); }
                    var fe = inst.GetComponentInChildren<FlareEjector>(true);
                    ok &= fe != null && (FlareCount < 0 || fe.ammo == FlareCount); det.Add($"flares {(fe != null ? fe.ammo.ToString() : "none")}");
                    var els = inst.GetComponentsInChildren<ControlSurface>(true).Where(c => c.name.StartsWith("elevator_")).ToList();
                    ok &= els.Count == 2 && els.All(c => Mathf.Abs(Mathf.Abs((float)G(c, "pitchRange")) - ElevatorThrow) < 0.01f); det.Add($"elevator throw {string.Join("/", els.Select(c => G(c, "pitchRange")))}");
                    float partKg = inst.GetComponentsInChildren<UnitPart>(true).Sum(u => u.mass);
                    ok &= !R1bLoads || Mathf.Abs(partKg - 1959f) < 1f; det.Add($"part masses {partKg:F0} kg (+ fuel {FuelKg} + ammo at spawn)");
                    ok &= Mathf.Abs(PropTargetAoA - (R1bTaxiThrust ? 8f : 5f)) < 1e-4f; det.Add($"prop targetAOA {PropTargetAoA} eff {BladeEfficiency}");
                    R($"r1b in-game fixes: tail wheel {GearTailK}/{GearTailC}/{GearTailMaxComp}, {FlareCount} flares (r8), elevator {ElevatorThrow} deg, FBW takeoff {FbwTakeoffSpeed}, loads, taxi thrust", ok, string.Join("; ", det));
                }
                {   // r8 rows (user review 1)
                    var allT8 = inst.GetComponentsInChildren<Transform>(true);
                    var ckR = (Renderer[])G(ac, "cockpitRenderers"); var exR = (Renderer[])G(ac, "exteriorRenderers");
                    Renderer RT(string n) => allT8.FirstOrDefault(t => t.name == n)?.GetComponent<MeshRenderer>();
                    var ckf = RT("ckcanopy_fixed"); var ckh = RT("ckcanopy_hood");
                    var hoodT = allT8.FirstOrDefault(t => t.name == "canopy_hood");
                    bool canOk = !R8CockpitCanopy || (ckf != null && ckh != null && hoodT != null && ckR.Contains(ckf) && ckR.Contains(ckh) && !ckf.enabled && !ckh.enabled
                        && ckf.gameObject.layer == 3 && ckh.gameObject.layer == 3 && ckh.transform.IsChildOf(hoodT)
                        && new[] { "canopy_windscreen", "canopy_hood", "canopy_rear" }.All(n => exR.Contains(RT(n)))
                        && ckR.All(r => r.sharedMaterials.All(m => m != mats["glass_int"] && m != mats["glass"])));
                    R("r8 cockpit view: exterior canopy in exteriorRenderers (hidden in the cockpit), WT-cockpit-station canopy ckcanopy_fixed / ckcanopy_hood on layer 3 in cockpitRenderers (hood one slides with the hood), every cockpit-layer glass the faint A6M2_glass_ck (no COIN glass_int)",
                        canOk, $"ck fixed {ckf != null}, ck hood {ckh != null}, cockpit renderers {ckR.Length}, exterior renderers {exR.Length}");
                    var sr = RT("cockpit_sight"); var sri = RT("cockpit_sight_int");
                    var sgm = mats.TryGetValue("sightglass", out var sgm_) ? sgm_ : null;
                    bool sOk = !R8SightGlass || (sgm != null && sgm.GetColor("_BaseColor").a <= 0.15f && sgm.renderQueue >= 2500 && sr != null && sr.sharedMaterials.Contains(sgm)
                        && sri != null && sri.sharedMaterials.Contains(sgm) && !sri.sharedMaterials.Contains(mats["glass_int"]) && Mathf.Abs(sr.bounds.center.x - inst.transform.position.x) < 0.01f);
                    R("r8 Type 98 sight: reflector on the faint tinted transparent A6M2_sightglass (alpha <= 0.15, transparent queue), no glass_int, sight on the centreline",
                        sOk, $"sightglass alpha {(sgm != null ? sgm.GetColor("_BaseColor").a : -1):F2} queue {(sgm != null ? sgm.renderQueue : -1)}, sight x {(sr != null ? sr.bounds.center.x : 99):F3}");
                    var eyeT = allT8.FirstOrDefault(t => t.name == "cockpit_eye"); var stickT = allT8.FirstOrDefault(t => t.name == "cockpit_stick"); var seatR = RT("cockpit_seat");
                    float x0 = inst.transform.position.x;
                    R("r8 centreline: eye, stick pivot, seat on x = 0 (+-5 mm; user review 1: WT's +32 mm headPos had put them off centre)",
                        eyeT != null && stickT != null && seatR != null && Mathf.Abs(eyeT.position.x - x0) < 0.005f && Mathf.Abs(stickT.position.x - x0) < 0.005f && Mathf.Abs(seatR.bounds.center.x - x0) < 0.005f,
                        $"eye x {(eyeT != null ? eyeT.position.x - x0 : 99):F3}, stick x {(stickT != null ? stickT.position.x - x0 : 99):F3}, seat x {(seatR != null ? seatR.bounds.center.x - x0 : 99):F3}");
                    // r8m (user review r8l: the stick base moved with the stick): fixed floor mount outside the Joystick transform; the moving
                    // cockpit_stick pivots at the gimbal 54 mm above the base origin (floor datum), on x = 0, rest identity (Cockpit.cs:18 is absolute)
                    var stB = allT8.FirstOrDefault(t => t.name == "cockpit_stick_base"); var ckc8 = inst.GetComponentInChildren<global::Cockpit>(true);
                    var jsL8 = ckc8 != null ? (IList)G(ckc8, "joysticks") : null;
                    var jsT = jsL8 != null && jsL8.Count > 0 ? G(jsL8[0], "transform") as Transform : null;
                    R("r8m stick: fixed cockpit_stick_base (not under the Joystick transform), Joystick transform = cockpit_stick at the gimbal on x = 0, rest identity",
                        stB != null && jsT != null && jsT.name == "cockpit_stick" && !stB.IsChildOf(jsT) && Mathf.Abs(jsT.position.x - x0) < 0.005f && Quaternion.Angle(jsT.localRotation, Quaternion.identity) < 0.01f
                        && Mathf.Abs(jsT.position.y - stB.position.y - 0.054f) < 0.003f,
                        $"base {stB != null}, js {(jsT != null ? jsT.name : "none")}, gimbal above base {(jsT != null && stB != null ? jsT.position.y - stB.position.y : -1):F3}");
                    // r8o (user test r8n: a SOLID metal disc closed every break; a 'box' in the structure texture through the holes ahead of the cockpit):
                    // the tanks are their own plain metal (A6M2_tank, not the stock aircraft_structure look) on fus_center, fus_engine and both
                    // wing_inner; fus_center draws structure only at its two end frames + stubs (no tank box, no break disc); the re-baked liveries /
                    // damage textures are the ones the atlas manifest names (paint faces untouched; the model atlas cells are the manifest's)
                    {
                        var tk = mats.TryGetValue("tank", out var tk_) ? tk_ : null;
                        var tkUsers = allT8.Select(t => t.GetComponent<MeshRenderer>()).Where(r => r != null && tk != null && r.sharedMaterials.Contains(tk)).Select(r => r.name).Distinct().OrderBy(n => n).ToList();
                        bool tkOk = tk != null && tk.name == "A6M2_tank" && tk != mats["structure"] && !B25HTools.StockStructure.IsStructMat(tk)
                            && new[] { "fus_center", "fus_engine", "wing_inner_L", "wing_inner_R" }.All(n => tkUsers.Contains(n));
                        R("r8o tanks: the fuel / oil tank cells are on A6M2_tank (plain metal, not the aircraft_structure look) in fus_center, fus_engine and both wing_inner",
                            tkOk, $"A6M2_tank {(tk != null ? tk.name : "none")} on [{string.Join(", ", tkUsers)}]");
                        // r8o round 2: the tank's EFFECTIVE albedo (tile mean x _BaseColor) is a mid-grey metal (luminance >= 0.30) and stands
                        // clear of A6M2_metal_dark (straps, firewall) - r8o round 1 drew it with the near-black gunmetal tile (~0.075)
                        {
                            float tkL = EffLuma(tk), mdL = EffLuma(mats["metal_dark"]);
                            R("r8o tank albedo: A6M2_tank effective albedo (tile mean x _BaseColor) luminance >= 0.30 and >= 0.20 above A6M2_metal_dark (straps / firewall stay readable)",
                                tk != null && tkL >= 0.30f && tkL - mdL >= 0.20f, $"tank {tkL:F3} (tile {(tk != null && tk.GetTexture("_BaseMap") != null ? tk.GetTexture("_BaseMap").name : "none")}), metal_dark {mdL:F3}");
                        }
                        var fc8 = RT("fus_center"); var fr8 = RT("fus_rear");
                        var bad8 = new List<string>(); int nS8 = 0; float zR = fr8 != null ? fr8.bounds.max.z : 0f, zF = zR + 3.6707f;
                        if (fc8 != null && fr8 != null)
                        {
                            var mf8 = fc8.GetComponent<MeshFilter>(); var m8 = mf8.sharedMesh; var v8 = m8.vertices;
                            for (int k = 0; k < fc8.sharedMaterials.Length && k < m8.subMeshCount; k++)
                            {
                                if (fc8.sharedMaterials[k] != mats["structure"]) continue;
                                foreach (var vi in new HashSet<int>(m8.GetTriangles(k)))
                                {
                                    var w = fc8.transform.TransformPoint(v8[vi]);
                                    if (Mathf.Abs(w.x - x0) > 0.5f) continue;            // the wing_C root rib / stiffeners at |x| 0.86 are wing structure
                                    nS8++;
                                    if (!((w.z >= zR - 0.001f && w.z <= zR + 0.16f) || (w.z >= zF - 0.16f && w.z <= zF + 0.001f))) bad8.Add($"z {w.z - zR:F3}");
                                }
                            }
                        }
                        R("r8o fus_center: inside the body (|x| < 0.5) structure only at the two end frames + stubs (<= 0.16 m from the joints at y 0.955 / -2.715), none past a joint",
                            fc8 != null && fr8 != null && nS8 > 100 && bad8.Count == 0, $"{nS8} structure vertices, outside the end zones {bad8.Count} {string.Join(", ", bad8.Distinct().Take(4))}");
                        // r8o round 3 (review of round 2: from the aft engine break the firewall was a full disc with a light structure
                        // stiffener lattice): fus_engine draws structure only at its open aft end frame + stubs (<= 0.16 m from the joint);
                        // the firewall 0.38 m in is plain A6M2_metal_dark, the mount truss gear
                        var feR3 = RT("fus_engine");
                        var badR3 = new List<string>(); int nSR3 = 0, nFWR3 = 0;
                        if (feR3 != null && fr8 != null)
                        {
                            var mR3 = feR3.GetComponent<MeshFilter>().sharedMesh; var vR3 = mR3.vertices;
                            for (int k = 0; k < feR3.sharedMaterials.Length && k < mR3.subMeshCount; k++)
                            {
                                bool stR3 = feR3.sharedMaterials[k] == mats["structure"], mdR3 = feR3.sharedMaterials[k] == mats["metal_dark"];
                                if (!stR3 && !mdR3) continue;
                                foreach (var vi in new HashSet<int>(mR3.GetTriangles(k)))
                                {
                                    var w = feR3.transform.TransformPoint(vR3[vi]);
                                    if (Mathf.Abs(w.x - x0) > 0.5f) continue;
                                    if (mdR3 && w.z >= zF + 0.375f && w.z <= zF + 0.395f) nFWR3++;
                                    if (!stR3) continue;
                                    nSR3++;
                                    if (!(w.z >= zF - 0.001f && w.z <= zF + 0.16f)) badR3.Add($"z {w.z - zF:F3}");
                                }
                            }
                        }
                        R("r8o round 3 fus_engine: structure only at the open aft end frame + stubs (<= 0.16 m from the joint at y 0.955), the firewall 0.38 m in is plain metal_dark",
                            feR3 != null && nSR3 > 100 && badR3.Count == 0 && nFWR3 > 50, $"{nSR3} structure vertices, outside the end zone {badR3.Count} {string.Join(", ", badR3.Distinct().Take(4))}; metal_dark firewall vertices {nFWR3}");
                        string mtxt = File.ReadAllText(Path.Combine(RepoTextures, "a6m2_atlas_manifest.json"));
                        var mj = Newtonsoft.Json.Linq.JObject.Parse(mtxt);
                        string ah = (string)mj["atlas_hash"]; var bad9 = new List<string>(); int n9 = 0;
                        using (var sha = System.Security.Cryptography.SHA256.Create())
                            foreach (var kv in (Newtonsoft.Json.Linq.JObject)mj["textures"])
                            {
                                var f9 = Path.Combine(RepoTextures, kv.Key); n9++;
                                string h9 = File.Exists(f9) ? BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(f9))).Replace("-", "").ToLowerInvariant().Substring(0, 12) : "missing";
                                if (h9 != (string)kv.Value["sha"] || (string)kv.Value["atlas"] != ah) bad9.Add(kv.Key);
                            }
                        R("r8o liveries / damage: every livery, skin and damage texture is the file the atlas manifest names, all baked on one atlas",
                            n9 >= 13 && bad9.Count == 0 && !string.IsNullOrEmpty(ah), $"atlas {ah}, {n9} textures, mismatched [{string.Join(", ", bad9)}]");
                    }
                    var fe8 = inst.GetComponentInChildren<FlareEjector>(true);
                    R("r8 flares: 48 (as B-25H / Nimrod / B-17G)", fe8 != null && fe8.ammo == 48, $"flares {(fe8 != null ? fe8.ammo.ToString() : "none")}");
                    if (R8cCockpitAtlas)
                    {   // r8c: the cockpit atlas in the stock cockpit-material form, on the cockpit-view renderers
                        var cka = mats.TryGetValue("ckatlas", out var cka_) ? cka_ : null;
                        var ckUsers = allT8.Select(t => t.GetComponent<MeshRenderer>()).Where(r => r != null && cka != null && r.sharedMaterials.Contains(cka)).ToList();
                        bool kw = cka != null && cka.shader.name == "Universal Render Pipeline/Lit" && cka.IsKeywordEnabled("_NORMALMAP") && cka.IsKeywordEnabled("_METALLICSPECGLOSSMAP") && cka.IsKeywordEnabled("_OCCLUSIONMAP")
                            && cka.GetTexture("_BaseMap") != null && cka.GetTexture("_BumpMap") != null && cka.GetTexture("_MetallicGlossMap") != null && cka.GetTexture("_OcclusionMap") != null;
                        bool onCk = ckUsers.Any(r => r.name.StartsWith("cockpit_panel")) && ckUsers.Any(r => r.name.StartsWith("ckcanopy_")) && ckUsers.Any(r => r.name.StartsWith("cockpit_breech"))
                            && ckUsers.Any(r => r.name.StartsWith("fus_center"));
                        R("r8c cockpit atlas: A6M2_ckatlas = URP Lit + base / normal / metallic-gloss / occlusion maps and the three stock cockpit keywords; drawn on the panel, breeches, cockpit-view canopy and the tub walls (fus_center)",
                            kw && onCk && ckAtlasTris > 1000, $"keywords+maps {kw}, renderers {ckUsers.Count} ({string.Join(",", ckUsers.Select(r => r.name).Distinct().Take(6))}...), atlas tris {ckAtlasTris}");
                    }
                    bool wf = true; var wdet = new List<string>();
                    foreach (var sd in new[] { "L", "R" })
                    {
                        var h = allT8.FirstOrDefault(t => t.name == $"wing_fold_{sd}_hinge"); var v = allT8.FirstOrDefault(t => t.name == $"wing_fold_{sd}_vis");
                        var vr = v != null ? v.GetComponent<MeshRenderer>() : null;
                        if (h == null || vr == null) { wf = false; wdet.Add($"{sd}: rig missing"); continue; }
                        var c0 = vr.bounds.center; var save = h.localRotation;
                        h.localRotation = save * Quaternion.AngleAxis(WingFoldDeg, Vector3.right); var c1 = vr.bounds.center; h.localRotation = save;
                        float rise = c1.y - c0.y, inb = Mathf.Abs(c0.x - x0) - Mathf.Abs(c1.x - x0);
                        bool ok = rise > 0.15f && inb > 0.15f && h.parent.name == $"wing_fold_{sd}" && h.parent.GetComponent<MeshRenderer>() == null && h.parent.GetComponent<MeshCollider>() != null;
                        wf &= ok; wdet.Add($"{sd}: +{WingFoldDeg} deg lifts the tip {rise:F2} m, inboard {inb:F2} m");
                    }
                    R("r8 folding tips: wing_fold_L/R render under a hinge on the fold line (+90 deg about local X lifts the tip up and inboard); the part keeps its collider / joints",
                        !R8WingFold || wf, string.Join("; ", wdet));
                }
                R("released 1.9.15: the A6M2 is not ship-gated (FamilyBuild.ShipGated has no A6M2 entry; every pack builds it)", !FamilyBuild.ShipGated.Any(ga => ga.Key.StartsWith("A6M2")), $"gated: {FamilyBuild.ShipGated.Length}");
            }
            finally { Object.DestroyImmediate(inst); }
            bool all = rows.All(r => r.ok);
            foreach (var r in rows) L($"CHECK {(r.ok ? "PASS" : "FAIL")} {r.name}: {r.detail}");
            lastCheck = $"{rows.Count(r => r.ok)}/{rows.Count}";
            L($"CHECK {(all ? "ALL PASS" : "FAILED")} ({lastCheck})");
            return all;
        }

        static string InvisibleAirbrakeProblems(GameObject inst, bool on, float drag, float openSpeed, out string detail)
        {
            var abs = inst.GetComponentsInChildren<global::Airbrake>(true);
            detail = $"{abs.Length} Airbrake component(s)";
            if (!on) return abs.Length == 0 ? "" : "flag off but an Airbrake is present";
            if (abs.Length != 1) return "expected exactly one Airbrake";
            var ab = abs[0]; var bad = new List<string>();
            var tr = G(ab, "transforms") as Transform[]; var part = G(ab, "part") as UnitPart;
            detail = $"on {ab.name}, part {(part != null ? part.name : "null")}, dragAmount {G(ab, "dragAmount")}, transforms {(tr == null ? "null" : tr.Length.ToString())}";
            if (ab.gameObject != inst) bad.Add("not on the root object");
            if (part != inst.GetComponent<AeroPart>()) bad.Add("part is not the root part");
            if (!Mathf.Approximately((float)G(ab, "dragAmount"), drag)) bad.Add("dragAmount");
            if (tr == null || tr.Length != 0) bad.Add("transforms");
            if (G(ab, "constraints") == null) bad.Add("constraints null");
            return string.Join(", ", bad);
        }

        // ------------------------------------------------------------------ from NimrodBuild.cs (outputs renamed): templates, reflection
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

        // r8o round 2: effective albedo luminance of a lit material = mean of its base-map PNG (read from the source file, sRGB) x _BaseColor
        static float EffLuma(Material m)
        {
            if (m == null) return -1f;
            Color c = m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor") : Color.white;
            var t = m.HasProperty("_BaseMap") ? m.GetTexture("_BaseMap") : null;
            Color mean = Color.white;
            if (t != null)
            {
                string tn = t.name;                                  // a6m2_tile_<tile>_b -> own A6M2 tile or our Nimrod tile (ImportTextures)
                string src = Path.Combine(RepoTextures, tn + ".png");
                if (!File.Exists(src) && tn.StartsWith("a6m2_tile_")) src = Path.Combine(RepoTilesNimrod, "nimrod_tile_" + tn.Substring(10) + ".png");
                if (!File.Exists(src)) return -1f;
                var tx = new Texture2D(2, 2);
                ImageConversion.LoadImage(tx, File.ReadAllBytes(src));
                var px = tx.GetPixels32(); double r = 0, g = 0, b = 0;
                foreach (var p in px) { r += p.r; g += p.g; b += p.b; }
                mean = new Color((float)(r / px.Length / 255.0), (float)(g / px.Length / 255.0), (float)(b / px.Length / 255.0));
                Object.DestroyImmediate(tx);
            }
            return 0.2126f * mean.r * c.r + 0.7152f * mean.g * c.g + 0.0722f * mean.b * c.b;
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
                    if (orderedNames[k] == "bk_art" || orderedNames[k] == "ck_art" || orderedNames[k].StartsWith("pr_") || (PropTipStripes && orderedNames[k] == "prop")) foreach (var i in m.GetIndices(k)) paintV.Add(i);
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
            // r8c cockpit atlas: triangles of the cockpit materials whose UV2 ('ckatlas') lies in the atlas move to one submesh drawn with
            // A6M2_ckatlas, with UV0 = UV2 on their vertices (FBX import splits the vertices there: UV2 differs from the faces outside, (-1, -1))
            var uv2 = new List<Vector2>(); m.GetUVs(2, uv2);
            if (R8cCockpitAtlas && uv2.Count == m.vertexCount)
            {
                var uv0b = new List<Vector2>(); m.GetUVs(0, uv0b);
                var atlasTris = new List<int>();
                var subs = new List<int[]>(); var names = new List<string>();
                for (int k = 0; k < orderedNames.Length; k++)
                {
                    var tri = m.GetTriangles(k);
                    if (Array.IndexOf(CkAtlasMats, orderedNames[k]) < 0) { subs.Add(tri); names.Add(orderedNames[k]); continue; }
                    var keep = new List<int>();
                    for (int i = 0; i < tri.Length; i += 3)
                    {
                        bool inA = uv2[tri[i]].x >= 0f && uv2[tri[i + 1]].x >= 0f && uv2[tri[i + 2]].x >= 0f;
                        (inA ? atlasTris : keep).AddRange(new[] { tri[i], tri[i + 1], tri[i + 2] });
                    }
                    if (keep.Count > 0) { subs.Add(keep.ToArray()); names.Add(orderedNames[k]); }
                }
                if (atlasTris.Count > 0)
                {
                    foreach (var i in atlasTris) uv0b[i] = uv2[i];
                    m.SetUVs(0, uv0b);
                    subs.Add(atlasTris.ToArray()); names.Add("ckatlas");
                    m.subMeshCount = subs.Count;
                    for (int k = 0; k < subs.Count; k++) m.SetTriangles(subs[k], k);
                    orderedNames = names.ToArray();
                    ckAtlasTris += atlasTris.Count / 3;
                }
            }
            generatedMeshes.Add(m);
            return m;
        }
        static int ckAtlasTris;

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
        const string RepoIcons = @"C:\Users\User\Nuclear Option B-25\assets\ui";       // weapon icons (round 2)
        const string RepoUI = @"C:\Users\User\Nuclear Option B-25\assets\ui_a6m2";   // no hand art: generated from the model
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
            var art = Directory.Exists(RepoUI) && !File.Exists(Path.Combine(RepoUI, "a6m2_status_layout.json")) ? Directory.GetFiles(RepoUI, "*.png").FirstOrDefault(f => { var n = Path.GetFileName(f).ToLowerInvariant(); return n.Contains("diagram") || n.Contains("status") || n.Contains("damage"); }) : null;
            if (art != null)
            {
                var fitted = FitArt(art, 512, u, BIG);
                if (fitted != null) { bgPx = fitted; L($"status background: texture worker art {Path.GetFileName(art)} (bbox-fitted to the model frame)"); }
            }
            else L("status background: generated line art from the model (no assets/ui diagram art)");
            statusBackground = SaveSprite(bgPx, 512, "a6m2_status", false);

            // one filled sprite per part (256, 2x supersampled)
            const int PB = 512;
            for (short k = 0; k < plist.Count; k++)
            {
                var r = new Raster(PB);
                foreach (var (a, b, c) in PartTriangles(plist[k])) r.Tri(a, b, c, k);
                var px = Downsample(i => r.id[i] >= 0, PB, 2);
                statusParts[plist[k].name] = SaveSprite(px, 256, "a6m2_status_" + plist[k].name, true);
                // centre of the part's own silhouette, for failure indicators
                double sx = 0, sy = 0; int cnt = 0;
                for (int i = 0; i < r.id.Length; i++) if (r.id[i] >= 0) { sx += i % PB; sy += i / PB; cnt++; }
                diagramPos[plist[k].name] = cnt > 0 ? new Vector2((float)(sx / cnt / PB - 0.5), (float)(sy / cnt / PB - 0.5)) : Vector2.zero;
            }

            // map icon: filled silhouette, 256 (texture worker's icon when present)
            var icon = Path.Combine(RepoUI, "a6m2_map_icon.png");
            if (File.Exists(icon)) { mapIconSprite = ImportRepoSprite(icon, "a6m2_mapicon"); L("map icon: texture worker art a6m2_map_icon.png"); }
            else { mapIconSprite = SaveSprite(Downsample(i => u.id[i] >= 0, BIG, 4), 256, "a6m2_mapicon", false); L("map icon: generated silhouette from the model"); }
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
            var inst = new GameObject("A6M2_statusDisplay", typeof(RectTransform)) { layer = 5 };
            var rt = (RectTransform)inst.transform;
            rt.anchorMin = rt.anchorMax = new Vector2(1f, 0f); rt.pivot = new Vector2(1f, -0.05f); rt.sizeDelta = new Vector2(300f, 300f); rt.anchoredPosition = new Vector2(0f, -30.1f);
            var list = new List<PartStatusDisplay>();
            var failures = new List<GameObject>();
            UnityEngine.UI.Image rootImg;
            StatusDisplay sd;
            Vector2 V2(Newtonsoft.Json.Linq.JToken t) => new Vector2((float)t[0], (float)t[1]);
            var layoutPath = Path.Combine(RepoUI, "a6m2_status_layout.json");
            var covered = new HashSet<string>();
            if (File.Exists(layoutPath))
            {
                // texture worker's art + layout (assets/ui/a6m2_status_layout.json): stock-style per-part sprites, mirrored L/R
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
            var prefab = PrefabUtility.SaveAsPrefabAsset(inst, Folder + "/A6M2_statusDisplay.prefab");
            Object.DestroyImmediate(inst);
            L($"status display prefab: {list.Count} part images, failure indicators {fnames}");
            return prefab;
        }

    }
}
