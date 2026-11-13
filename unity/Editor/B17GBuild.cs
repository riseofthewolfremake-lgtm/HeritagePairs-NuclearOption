// B-17G Flying Fortress for Nuclear Option (Heritage Pairs 1.6.0): builds the B-17G into the family addon `heritage_pairs`
// (subfolder b17g, FamilyBuild.cs). A copy of B25HBuild.cs (crew, turrets, bomb bay, multi-engine pattern) adapted to four engines,
// a taildragger with forward-retracting mains, five gun stations and the period cockpit; B25HBuild.cs itself is untouched.
//
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FamilyBuild.BuildAll family_build_160
//
// Everything is generated from the user's own files at build time:
//   - our model:   <repo>\assets\model_b17g\b17g.fbx (blender/b17g/export_b17g.py; copied into Assets/B17GSource, NOT part of the mod)
//   - our textures <repo>\assets\textures_b17g\*.png (liveries, skin maps, fal tiles, gauge atlas, fal prop base colours)
//   - stock game components (AssetRipper placeholders in _donotship) are used only as STARTING VALUES (B-25H method).
// Notes: <repo>\docs\b17g_design.md
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
    public static class B17GBuild
    {
        // ------------------------------------------------------------------ paths and identity
        const string ModName = "b17g";
        const string DisplayName = "B-17G Flying Fortress";
        const string Version = "1.6.0";
        const string Folder = FamilyBuild.FamilyRoot + "/b17g";
        const string OutFolder = @"C:\Users\User\nuclearoption-ref\build\b17g";
        const string RepoModel = @"C:\Users\User\Nuclear Option B-25\assets\model_b17g\b17g.fbx";
        const string RepoTextures = @"C:\Users\User\Nuclear Option B-25\assets\textures_b17g";
        const string SrcDir = "Assets/B17GSource";
        const string DNS = "Assets/Blueprinter/_donotship";
        const string JsonKey = "B17G";
        const string LogPath = @"C:\Users\User\nuclearoption-ref\unitylogs\b17g_check_table.txt";

        // ------------------------------------------------------------------ feature flags (B-25H names kept where the code is shared)
        const bool OwnCannonWeaponInfo = false;
        const bool KeepFlareEjector = true;     // hidden under the inner nacelles; every stock aircraft has one (HUD / AI code paths)
        const bool StockHUDExtras = true;       // keep the game HUD (COIN_HUDExtras, prop aircraft)
        const bool OwnPropBlur = true;
        const bool CockpitRebuild = false;      // B-25H atlas path off; the B-17G cockpit uses its own ck_* / gauges / pr_* materials
        const bool WsoScreenTacPage = true;
        const bool CockpitPropsNoShadow = true;
        const float QuiltTiling = 5f;
        static readonly string[] PropNames = new string[0];
        const bool ClusterBombOption = true;    // 1.6.1: own enabled copy of the stock (disabled) CBO-400 x2 bay mount; unverified in game until probed
        const bool CockpitAnimators = true;     // columns / yokes (ControlSurface), 4 throttles (Cockpit.throttles)
        const bool MFDScreens = false;          // period cockpit: no screens (hidden dummy tac screen as the B-25H 1.0)
        const bool FiveCrew = true;             // crew of TEN from the contract (Pilot components, bail-out)
        const float TailCrewScale = 0.6f;
        const float BallCrewScale = 0.5f;       // the ball gunner sits curled in the ball (stock seated figure scaled about its eye)
        static readonly string[] LegsTucked = { "bombardier", "navigator", "radio", "waist_R", "waist_L", "tail", "ball" };   // 1.6.2: + ball (286 vertices outside the ball in 1.6.1)   // 1.6.1: thighs folded (legs hung outside in 1.6.0)
        const bool FixedGunsAirOnlyForAI = true;
        const bool TacScreenPanels = false;
        const bool DefensiveTurrets = true;     // 13 x stock 12.7 mm in 5 stations (Chin / Top / Ball / Tail / Flexible)
        const bool TurretAntiMissile = false;
        const bool TurretExclusionCones = true; // b17g_turret_scan.json blocked directions -> exclusion FiringCones (offline scan); replaced by FireClear1814 when on
        const bool FireClear1814On = true;      // 1.8.14 (offline M): exclusion FiringCones from a 1 deg bore-line sweep of the BUILT aircraft (FireClear1814.cs); false = 1.8.13 cones
        const string FireClearJson = "C:/Users/User/Nuclear Option B-25/assets/model_b17g/b17g_fireclear_1814.json";
        const bool NuclearOptions = true;       // GPO-N in the bay (user decision)
        const bool StrategicGPON = false;
        const bool OwnStatusDisplay = true;
        const bool OwnMapIcon = true;
        const bool BomberAITuning = true;
        const bool CrashImpactDamage = true;    // Nimrod lesson: every part gets its own ImpactDamage (stock templates have threshold 0)
        const bool AB4EngineMessages = true;    // "ENGINE n FIRE" + the AB-4's voice clips (FastBomber1 placeholder)
        const bool OwnFlapAirfoil = true;       // 1.6.3: flaps get their own curve (airfoil 3): CL ~2.0 at flap AoA ~33 deg, low drag (wing curve: post-stall airbrake, 27 kN at 50 m/s)
        const bool OwnAileronAirfoil = true;    // Nimrod lesson: ailerons as separate parts need a flap-like curve or they reverse roll
        const bool SpawnThreePoint = true;      // restRotation = the 3-point attitude (Hangar.cs:649 applies it on the host spawn)

        // ------------------------------------------------------------------ B-17G numbers (tools/flightmodel/b17g_estimate.py, docs/b17g_design.md)
        const float WingIncidence = 3.5f;       // deg, liftNormal tilt of the wing panels (1.6.3: 2.5 -> 3.5, the real B-17 root incidence; take-off lift)
        const float StabIncidence = -2.0f;      // 1.6.4: -1 -> -2 (more tail-down force on the take-off roll)
        // 1.6.8: part drag areas x 0.5 (in game 1.6.7: level 420 km/h at 1.8 km, equivalent drag area 4.98 m2 incl. the real-size tail;
        // the game scales power with air density, so the real 460 km/h at 7.6 km has to come from sea-level drag/power)
        const float PartDragScale = 0.5f;
        // 1.7.8: 1.6 -> 1.5 MW. The 1.7.7 procedural props (blades on the shaft axis) give the full blade-model thrust (in game 132 / 103 kN at
        // 25 / 44 m/s vs 102 / 91 with the off-axis fal props the power was tuned on); the ConstantSpeedProp blade model
        // (tools/flightmodel/b17g_lateral.prop_thrust, reproduces both 1.7.7 numbers within 3 %) puts 1.6 MW at ~473 km/h with the
        // 1.6.8 drag (463 km/h measured), 1.5 MW at ~463. Climb / take-off thrust stay above 1.7.5 (129 kN at 25 m/s).
        const float EnginePower = 1.25e6f;     // W per engine (1.7.10: 1.5 MW with the 1.7.6 props measured 491 km/h level at 1.7 km, still rising, climb 8.7 m/s; (462/495)^3 -> 1.25 MW for ~460 km/h and ~5-6 m/s climb; 1.6.8: 1.6 MW; 1.6.7: 1.55 MW for ~450 km/h level (1.3 MW measured 425 km/h at 1 km, climb 8-9 m/s), with the B-17 wing drag curve below to hold the climb near 7 m/s; 1.6.5: 1.3; 1.6.3: game power for B-17 performance; user 2026-11-06 "a supercharger just makes the engine more powerful"; 1.6.2 had the real 0.895 MW: 331 km/h, no take-off)
        const float PropRpm = 1294f;            // 2,300 engine rpm x 0.5625 reduction
        const float WingCLmaxDeg = 16f;         // wing curve peak (B17G_wing)
        // 1.6.5: ControlsFilter (FBW) take-off logic: below takeoffSpeed it bleeds off its own pitch correction and below 1.5 x takeoffSpeed it
        // never resists a nose-down rotation (nose-wheel logic). With 46 the tail came up at ~35 m/s and the nose sank to a 2 deg attitude
        // (wing AoA 5.5): no lift-off below 72 m/s with neutral stick. With 15 the FBW holds the 3-point attitude from 23 m/s on.
        // 1.7.2: AiCornerSpeed 80 -> 100. AutopilotPlane scales the AI's control effort by airspeed / cornerSpeed: with 80 the AI banked
        // 45-60 deg at 70 m/s straight after take-off and sank into the ground (1.7.0 player-AI run 2); 1.6.x (95) never did.
        // 1.7.0 AI pattern / landing numbers (stock heavies: SFB-81 turningRadius 1500, minimumRadarAlt 100, cruiseThrottle 1)
        const float AiTurningRadius = 1500f, AiCornerSpeed = 100f, AiLandingSpeed = 47f, AiMinRadarAlt = 3000f, AiCruiseThrottle = 1.0f;
        // 1.7.5 AI role (user: "treated like low flying attack planes"): AIPilotCombatModes.ManageAltitude pulls targetHeight down to
        // aircraftParameters.minimumRadarAlt (-10 m/s when nothing calls for a climb) and FlyToTarget terrain-follows at it; the only other
        // climb is the Bombing-mode pop-up (+0.12 rad path from radarAlt x 2 + 5 km out). Stock AB-4 is 100 too (it is fast, so its pop-up
        // ends high). minimumRadarAlt is read only by the combat state (not landing / taxi): 150 -> 3000 m AGL cruise and bombing height.
        // 1.7.0 gear-down drag area (LandingGear.extendedDrag replaces the attached part's dragArea while down): mains 1.2 -> 4.0, tail 0.2 -> 0.5
        const float MainGearDrag = 4.0f, TailGearDrag = 0.5f;
        // 1.7.4 lateral (in game 1.7.3, roll hands-off): at 70 m/s full power the FBW roll trim (template limit 0.05) saturated
        // against the four same-way props and the bank ran 7 -> 57 deg in 2 min; with the trim free it still drifted 1 -> 11 deg
        // in 2 min (spiral). Trim limit 0.3 / rate 0.1, aero dihedral 8 deg.
        // 1.7.8 spiral (in game 1.7.7 / 1.7.5: hands-off at 70 m/s full power the bank doubled every ~25-30 s, either way, 0.7 -> 61 deg in
        // 3 min; live pokes of dihedral 12, rollTightness 1, trim 0.5 / 0.5 all failed). Mechanism (ControlsFilter.FlyByWire.Filter +
        // tools/flightmodel/b17g_lateral.py, which reproduces it): the roll trim INTEGRATES the body-axis roll rate (rollTrim += p_cmd - p,
        // while |q| < 0.1 rad/s). Nose up by theta in a turn, the body roll rate is p = phi_dot - psi_dot sin(theta), so holding p = 0
        // means phi_dot = psi_dot sin(theta) = g tan(phi) sin(theta) / V: the trim itself banks the aircraft further into every climbing
        // turn, time constant V / (g sin theta) = 33-40 s at 70 m/s / 10-12 deg (measured: dphi / dpsi = 0.2 = sin 12 deg). No aero
        // setting can stop an unsaturated integrator; the trim was only needed because four same-way props put ~47 kN m of torque on the
        // airframe (trim sat at ~0.11). Now: handed props (no net torque, PropTurn), roll trim off, and aero dihedral 8 -> 10 for spiral
        // margin at 50-55 m/s full power (stub: 5 deg -> 2.3 deg in 3 min at 50 m/s, -> 0.3 deg at 70 m/s; dihedral 8: 5 -> 23 at 55 m/s).
        const float FbwRollTrimLimit = 0.0f, FbwRollTrimRate = 0.0f, AeroDihedralDeg = 10f;
        // 1.7.8 handed props: engines 1-2 (left) turnDirection 1 as before, 3-4 (right) -1 with mirrored blades (b17g_spec.PROP_TURN);
        // the real R-1820s all turned clockwise - a deliberate deviation so that no trim is needed (above). Revert = all 1 + the 1.7.7 trim.
        static readonly System.Collections.Generic.Dictionary<int, int> PropTurn = new System.Collections.Generic.Dictionary<int, int> { { 1, 1 }, { 2, 1 }, { 3, -1 }, { 4, -1 } };
        // 1.7.8 AI weave (in game 1.7.7: bank +-30-55 deg, roll input saturated, ~20 s period while climbing to minimumRadarAlt). AutopilotPlane
        // turns a heading error into a bank target with a high gain (bank = atan(lateral / vertical) of the aim vector), the B-17G rolls
        // only 6-10 deg/s at 55-70 m/s with full aileron, and the template roll PID (0.02, 0.001, 0.01 per deg) gave a ~9 s bank lag;
        // the FBW trim drift (above) and waypoint height jumps (1.8 km look-ahead over terrain) kept it cycling. Stub (b17g_lateral.py):
        // D 0.05 + no trim + look-ahead 6.75 km: bank rms 0.1 deg after capture vs 10.5 on 1.7.7. aircraftGLimit is read ONLY by
        // TerrainWarningSystem.GetFollowTerrainWaypoint (look-ahead = max(V, 100) x 6 x 9 / gLimit): 3 -> 0.8 = 1.8 -> 6.75 km. It also sets the
        // climb speed: the AI aims at the waypoint at minimumRadarAlt x lerp(0.1, 1, (V - 0.9 landingSpeed) / landingSpeed), so it slows until
        // that height is only look-ahead x climb gradient above it (1.7.7: 46-60 m/s below 1 km; 6.75 km: ~62-70 m/s, pitch ~10 deg).
        // 1.7.12 (in game 1.7.10 P5: steady-climb bank rms 5.9 / max 15.1 deg, stick bang-bang +-1): the stub (b17g_lateral.py) did not reproduce
        // it until the AI's destination moves (moving / threat-shifted targets: the 6.75 km look-ahead leaves a small vertical aim component, so a
        // 2-5 deg bearing change asks for 30-70 deg of bank); with that excitation 1.7.10 gives rms 7.3 / max 19 (game 6.5 / 15). The bank error's
        // D term is what damps the heading-bank loop: 0.05 -> 0.20 gives rms 2.8 / max 7 in the worst case (stub), P and I kept.
        // 1.7.13: D back to 0.05. In game (1.7.12 P5/P6) D 0.20 made it worse: climb bank rms 7.2 / max 22 (1.7.10: 6.4 / 15) and both AI landings
        // crashed after 50-70 deg banks on the go-around; the same build poked live to D 0.05 landed 2 of 2 and parked. The climb weave stays open.
        static readonly Vector3 AiRollPID = new Vector3(0.03f, 0.002f, 0.05f);
        const float AiLookaheadGLimit = 0.8f;
        const float FbwTakeoffSpeed = 15f;
        // 1.6.6 pitch authority (in game 1.6.5: full up elevator could not hold the take-off attitude above ~47 m/s; the 1.6.0 stall test
        // never got past AoA 8.9): the elevators flew on the stab airfoil, which stalls at 17 deg local AoA (stab AoA + deflection), so
        // more throw gave less force. Now the flap-like aileron curve (airfoil 2), 32 deg up, the real horizontal-tail area (30.8 m2 =
        // 2 x (7.5 stab + 8.0 elevator), was 23) and a stiffer FBW pitch loop (pFactorFast 10 -> 25; 30 held the attitude in game).
        const float StabArea = 7.5f, ElevatorArea = 8.0f, ElevatorUp = 32f, FbwPitchP = 25f;
        // 1.7.5 AI pitch oscillation (in game 1.7.4, Confrontation, 2 AI B-17Gs): pitch rate +-15 deg/s at a ~0.8-1 s period, elevator +-0.3-0.4,
        // pitch +-3 deg, in cruise and on the bombing run. The FBW pitch loop integrates pFactorFast x rate error into the elevator; the template
        // damping dFactorFast 0.4 is too small for 25. Live poke on one of two AI: d 3 (p 25): rate-sign changes 10 vs 56 in 40 s (the other
        // aircraft); p 10: 93 vs 171 in 60 s and smooth in the bombing run. d keeps p 25, which holds the 3-point take-off attitude.
        const float FbwPitchD = 3f;
        const int ElevatorAirfoil = 2;
        const float AlphaLimiter = 12.5f;       // lesson: limiter + incidence = the wing's CLmax angle (12.5 + 3.5 = 16)
        const float FuelKg = 4600f;             // 1,700 US gal normal load
        const float MetalImpactG = 30f, MetalImpactMult = 1f, FabricImpactG = 20f, FabricImpactMult = 1.5f;
        const float ThreePointDeg = 8.7f;       // blender/b17g/check_b17g_model.py (h) stance

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

        // Masses (blender/b17g/build_b17g.py MASS, CG 21.7 % MAC) sum ~23.9 t with crew, ammo and 50 % fuel in the parts; empty 16.4 t
        // shown in the encyclopedia (AircraftInfo). Wing area 131.9 m^2 real: panels 2 x (16 + 15 + 18 + 2.5) + flaps / ailerons 2 x 12.3.
        // Joints ~2.5 x the B-25H's (25 t on the same structure scheme). Airfoil 0 wing, 1 tail, 2 aileron.
        static List<PartSpec> Parts()
        {
            var l = new List<PartSpec>
            {
                new PartSpec("B17G",        null,          "fus_center",  "CAS1:CAS1",       4200, 4.0f, 0.55f, 1, Lift.Own,    0),
                new PartSpec("fus_cockpit", "B17G",        "fus_cockpit", "CAS1:cockpit",    1900, 0.5f, 0.15f, 1, Lift.Own,    400000),
                new PartSpec("fus_nose",    "fus_cockpit", "fus_nose",    "CAS1:nose",       1300, 0.3f, 0.12f, 1, Lift.Own,    200000),
                new PartSpec("fus_radio",   "B17G",        "fus_radio",   "CAS1:fuselage_R",  450, 0.4f, 0.10f, 1, Lift.Own,    350000),
                new PartSpec("fus_waist",   "fus_radio",   "fus_waist",   "CAS1:fuselage_R",  650, 1.0f, 0.18f, 1, Lift.Own,    300000),
                new PartSpec("fus_tail",    "fus_waist",   "fus_tail",    "CAS1:tail",        300, 0.6f, 0.10f, 1, Lift.Own,    250000),
                new PartSpec("tail_gun",    "fus_tail",    "tail_gun",    "CAS1:tail",        220, 0.0f, 0.05f, 1, Lift.Own,    100000),
                new PartSpec("fin",         "fus_tail",    "fin",         "CAS1:vstab_L",     150, 6.5f, 0.02f, 1, Lift.Fin,    150000),
                new PartSpec("rudder",      "fin",         "rudder",      "CAS1:rudder_L",     45, 3.5f, 0.01f, 1, Lift.Hinge,  60000),
            };
            foreach (var s in new[] { "L", "R" })
            {
                int inner = s == "L" ? 2 : 3, outer = s == "L" ? 1 : 4;
                l.Add(new PartSpec("stab_" + s,        "fus_tail",       "stab_" + s,        "CAS1:hstab_" + s,     100, StabArea, 0.02f, 1, Lift.Stab,  120000));
                l.Add(new PartSpec("elevator_" + s,    "stab_" + s,      "elevator_" + s,    "CAS1:elevator_" + s,   35, ElevatorArea, 0.01f, ElevatorAirfoil, Lift.Hinge, 60000));
                l.Add(new PartSpec("wing_inner_" + s,  "B17G",           "wing_inner_" + s,  "CAS1:wing1_" + s,    1500, 16.0f, 0.04f, 0, Lift.Wing, 600000));
                l.Add(new PartSpec("flap_inner_" + s,  "wing_inner_" + s,"flap_inner_" + s,  "CAS1:flap_" + s,       60, 4.6f, 0.01f, OwnFlapAirfoil ? 3 : 0, Lift.Hinge, 60000));
                l.Add(new PartSpec("nacelle_" + inner, "wing_inner_" + s,"nacelle_" + inner, "CAS1:engineMount_" + s,250, 0.3f, 0.18f, 1, Lift.Own,  200000));
                l.Add(new PartSpec("engine_" + inner,  "nacelle_" + inner,"engine_" + inner, "CAS1:engine_" + s,   1350, 0.0f, 0.15f, 1, Lift.Own,   150000));
                l.Add(new PartSpec("prop_" + inner,    "engine_" + inner, null,              "COIN:propHub",        330, 0.0f, 0.05f, 1, Lift.Own,   80000));
                l.Add(new PartSpec("wing_mid_" + s,    "wing_inner_" + s,"wing_mid_" + s,    "CAS1:wing2_" + s,     900, 15.0f, 0.03f, 0, Lift.Wing, 450000));
                l.Add(new PartSpec("flap_outer_" + s,  "wing_mid_" + s,  "flap_outer_" + s,  "CAS1:flap_" + s,       70, 5.3f, 0.01f, OwnFlapAirfoil ? 3 : 0, Lift.Hinge, 60000));
                l.Add(new PartSpec("nacelle_" + outer, "wing_mid_" + s,  "nacelle_" + outer, "CAS1:engineMount_" + s,250, 0.3f, 0.18f, 1, Lift.Own,  200000));
                l.Add(new PartSpec("engine_" + outer,  "nacelle_" + outer,"engine_" + outer, "CAS1:engine_" + s,   1350, 0.0f, 0.15f, 1, Lift.Own,   150000));
                l.Add(new PartSpec("prop_" + outer,    "engine_" + outer, null,              "COIN:propHub",        330, 0.0f, 0.05f, 1, Lift.Own,   80000));
                l.Add(new PartSpec("wing_outer_" + s,  "wing_mid_" + s,  "wing_outer_" + s,  "CAS1:wing3_" + s,     420, 15.5f, 0.02f, 0, Lift.Wing, 300000));
                l.Add(new PartSpec("aileron_" + s,     "wing_outer_" + s,"aileron_" + s,     "CAS1:aileron_" + s,    65, 5.0f, 0.01f, 2, Lift.Hinge, 80000));
                l.Add(new PartSpec("wing_tip_" + s,    "wing_outer_" + s,"wing_tip_" + s,    "CAS1:wingtip_" + s,    50, 1.8f, 0.01f, 0, Lift.Wing,  100000));
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

        static void L(string s) { log.Add(s); Debug.Log("[B25H] B17G " + s); }

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
                crew.Clear(); turrets.Clear(); turretInfo = null; ammoTurrets = null;
                contract = LoadContract();
                var model = ImportModel();
                ImportTextures();
                LoadTemplates();
                BuildMaterials();
                root = (GameObject)Object.Instantiate(model);
                root.name = "B17G";
                DropPedals();
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
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Folder + "/B17G.prefab");
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
            File.WriteAllText(LogPath, $"B25H build {DateTime.Now:s}\n");
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
            var dst = SrcDir + "/b17g_v2.fbx";
            File.Copy(RepoModel, dst, true);
            AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
            var mi = (ModelImporter)AssetImporter.GetAtPath(dst);
            mi.isReadable = true; mi.importAnimation = false; mi.importCameras = false; mi.importLights = false;
            mi.globalScale = 1f; mi.useFileScale = true; mi.importBlendShapes = false;
            mi.SaveAndReimport();
            L($"model imported {dst} ({new FileInfo(RepoModel).Length} bytes)");
            // prop blur stage meshes (model worker, separate FBX so the main model never shows an unwired disc)
            modelBlur = modelFull = null;
            var extra = Path.Combine(Path.GetDirectoryName(RepoModel), "b17g_v2_propdisc.fbx");
            if (File.Exists(extra))
            {
                var edst = SrcDir + "/b17g_v2_propdisc.fbx";
                File.Copy(extra, edst, true);
                AssetDatabase.ImportAsset(edst, ImportAssetOptions.ForceUpdate);
                var emi = (ModelImporter)AssetImporter.GetAtPath(edst);
                emi.isReadable = true; emi.importAnimation = false; emi.importCameras = false; emi.importLights = false; emi.globalScale = 1f; emi.useFileScale = true;
                emi.SaveAndReimport();
                var ms = AssetDatabase.LoadAllAssetsAtPath(edst).OfType<Mesh>().ToList();
                Mesh Take(string n) { var m = ms.FirstOrDefault(x => x.name == n); if (m == null) return null; var c = Object.Instantiate(m); c.name = "b17g_" + n; generatedMeshes.Add(c); return c; }
                modelBlur = Take("propdisc_blur"); modelFull = Take("propdisc_full");
                L($"prop disc meshes from {extra}: blur {(modelBlur ? modelBlur.vertexCount + " v" : "missing")}, full {(modelFull ? modelFull.vertexCount + " v" : "missing")}");
            }
            return AssetDatabase.LoadAssetAtPath<GameObject>(dst);
        }

        static readonly string[] SkinMaps = { "b", "n", "m", "ao", "dmg_b", "dmg_n" };
        static readonly (string file, string label, string faction)[] BaseLiveries = new (string, string, string)[0];
        // b17g_liveries.json (blender/b17g/textures/build_textures_b17g.py): faction BOTH = offered to both factions (the two historical
        // USAAF schemes, user decision 2026-11-03), BDF / PALA = that faction only.
        static readonly List<(string file, string label, string faction, bool both)> Liveries = new List<(string, string, string, bool)>();

        static void LoadLiveryTable()
        {
            Liveries.Clear();
            var path = Path.Combine(RepoTextures, "b17g_liveries.json");
            if (!File.Exists(path)) throw new Exception("no b17g_liveries.json");
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(path));
            int bothCount = 0;
            foreach (var kv in jo)
            {
                if (!(kv.Value is Newtonsoft.Json.Linq.JObject e)) continue;
                var file = Path.GetFileNameWithoutExtension((string)e["texture"]);
                var fac = ((string)e["faction"] ?? "").ToUpperInvariant();
                bool both = fac == "BOTH";
                if (both) fac = (bothCount++ % 2 == 0) ? "BDF" : "PALA";     // ordering only (each faction's own first)
                Liveries.Add((file, (string)e["name"] ?? kv.Key, fac, both));
                L($"livery table: {file} '{(string)e["name"]}' ({(both ? "both factions" : fac + " only")})");
            }
        }
        static readonly Dictionary<string, Color32> LiveryFallback = new Dictionary<string, Color32>();
        static readonly string[] Tiles = { "b17g_tile_structure_b", "b17g_tile_interior_b", "b17g_tile_well_b", "b17g_tile_gear_b", "b17g_tile_tyre_b", "b17g_tile_cowl_b",
            "b17g_tile_turret_b", "b17g_tile_ck_panel_b", "b17g_tile_ck_wall_b", "b17g_tile_ck_od_b", "b17g_tile_ck_floor_b", "b17g_tile_ck_black_b", "b17g_tile_ck_bezel_b" };
        static readonly List<string> PrTextures = new List<string>();
        static readonly Dictionary<string, Texture2D> tex = new Dictionary<string, Texture2D>();

        static void ImportTextures()
        {
            tex.Clear(); PrTextures.Clear();
            LoadLiveryTable();
            foreach (var f in Directory.GetFiles(RepoTextures, "b17g_pr_*_b.png")) PrTextures.Add(Path.GetFileNameWithoutExtension(f));
            var want = SkinMaps.Select(m => "b17g_skin_" + m).Concat(Liveries.Select(l => l.file)).Concat(new[] { "b17g_gauges" }).Concat(Tiles).Concat(PrTextures).ToList();
            foreach (var n in want)
            {
                var src = Path.Combine(RepoTextures, n + ".png");
                if (n == "b17g_skin_m" && !File.Exists(src)) src = Path.Combine(RepoTextures, "b17g_skin_m_usaaf_od.png");   // per-livery metal maps: the default livery's
                var dst = $"{Folder}/Textures/{n}.png";
                bool real = File.Exists(src);
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
                L($"texture {n}: {(real ? "from repo" : "generated flat fallback")}");
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
            else if (n == "b17g_gauges") c = new Color32(22, 22, 22, 255);
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
            Color dark = new Color(0.07f, 0.07f, 0.07f), tipC = new Color(0.86f, 0.70f, 0.06f);
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
                            for (int b = 0; b < 3; b++) d = Mathf.Min(d, Mathf.Abs(Mathf.DeltaAngle(th, b * 120f)));
                            float w = 9f + 26f * r;  // angular half-width of the smeared blade, wider at the tip
                            a = 0.08f + 0.62f * Mathf.Exp(-(d / w) * (d / w));
                        }
                        else
                        {
                            a = 0.20f + 0.03f * Mathf.Sin(r * 60f) + (r > 0.92f ? 0.16f : 0f);
                        }
                        a *= edge;
                    }
                    var col = (Color32)new Color(c.r, c.g, c.b, a);
                    px[y * W + x] = col;
                }
            var t = new Texture2D(W, H, TextureFormat.RGBA32, false);
            t.SetPixels32(px); t.Apply();
            var path = $"{Folder}/Textures/b17g_propblur.png";
            File.WriteAllBytes(path, t.EncodeToPNG());
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
            var ti = (TextureImporter)AssetImporter.GetAtPath(path);
            ti.alphaIsTransparency = true; ti.wrapMode = TextureWrapMode.Clamp; ti.mipmapEnabled = true;
            ti.textureCompression = TextureImporterCompression.Compressed; ti.SaveAndReimport();
            L("generated prop blur atlas b17g_propblur.png (512x1024)");
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
            foreach (var n in new[] { "COIN", "CAS1", "EW1", "turret_57mm_SideMount", "gun_12.7mm_internal", "turret_12.7mm_door", "FastBomber1" })
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
            var paint = new Material(skin) { name = "B17G_paint" };
            paint.SetTexture("_Basecolor", tex["b17g_skin_b"]);
            paint.SetTexture("_Normal", tex["b17g_skin_n"]);
            paint.SetTexture("_Metallic", tex["b17g_skin_m"]);
            paint.SetTexture("_AO", tex["b17g_skin_ao"]);
            paint.SetTexture("_BasecolorDmg", tex["b17g_skin_dmg_b"]);
            paint.SetTexture("_NormalDmg", tex["b17g_skin_dmg_n"]);
            paint.SetTexture("_Livery", tex["b17g_skin_b"]);
            paint.SetFloat("_Glossiness", 0.2f);
            paint.SetFloat("_HitPoints", 100f);
            Save(paint, "paint");

            var lit = Shader.Find("Universal Render Pipeline/Lit");
            if (lit == null) throw new Exception("URP Lit shader not found");
            // tiled materials (detail UV moved to UV0 by CopyMesh), colours baked into the fal tiles
            foreach (var (key, tile, metal, smooth) in new[] {
                ("structure", "b17g_tile_structure_b", 0.5f, 0.35f), ("interior", "b17g_tile_interior_b", 0.1f, 0.25f), ("well", "b17g_tile_well_b", 0.2f, 0.3f),
                ("gear", "b17g_tile_gear_b", 0.6f, 0.45f), ("tyre", "b17g_tile_tyre_b", 0.0f, 0.1f), ("cowl", "b17g_tile_cowl_b", 0.4f, 0.4f),
                ("turret", "b17g_tile_turret_b", 0.2f, 0.3f), ("ck_panel", "b17g_tile_ck_panel_b", 0.1f, 0.35f), ("ck_wall", "b17g_tile_ck_wall_b", 0.1f, 0.3f),
                ("ck_od", "b17g_tile_ck_od_b", 0.1f, 0.3f), ("ck_floor", "b17g_tile_ck_floor_b", 0.1f, 0.2f), ("ck_black", "b17g_tile_ck_black_b", 0.1f, 0.3f),
                ("ck_bezel", "b17g_tile_ck_bezel_b", 0.6f, 0.5f) })
            {
                var m = Tiled(LitMat(lit, "B17G_" + key, Color.white, metal, smooth), tile);
                if (key.StartsWith("ck_")) { m.SetTextureScale("_BaseMap", new Vector2(2f, 2f)); }
                Save(m, key);
            }
            Save(LitMat(lit, "B17G_cove", new Color(0.05f, 0.05f, 0.05f), 0f, 0.1f), "cove");
            Save(LitMat(lit, "B17G_chrome", new Color(0.85f, 0.86f, 0.88f), 1f, 0.85f), "chrome");
            Save(LitMat(lit, "B17G_metal_dark", new Color(0.06f, 0.06f, 0.065f), 0.7f, 0.6f), "metal_dark");
            Save(LitMat(lit, "B17G_exhaust", new Color(0.13f, 0.075f, 0.05f), 0.4f, 0.35f), "exhaust");       // 1.8.3: heat-rusted turbo / exhaust (reference)
            Save(LitMat(lit, "B17G_turbo", new Color(0.26f, 0.13f, 0.06f), 0.15f, 0.30f), "turbo");          // 1.8.5 offline E (F2): turbo housing + volute, lighter rust than the pipes (faces down into shade)
            Save(LitMat(lit, "B17G_cowl_ring", new Color(0.24f, 0.25f, 0.15f), 0.1f, 0.35f), "cowl_ring");  // 1.8.3: olive-drab anti-glare cowl lip
            Save(LitMat(lit, "B17G_prop", new Color(0.03f, 0.03f, 0.03f), 0.2f, 0.5f), "prop");
            Save(LitMat(lit, "B17G_engine", new Color(0.3f, 0.3f, 0.3f), 0.8f, 0.6f), "engine");
            Save(LitMat(lit, "B17G_needle", new Color(0.92f, 0.92f, 0.88f), 0f, 0.5f), "needle");
            var gauges = LitMat(lit, "B17G_gauges", Color.white, 0f, 0.55f);
            gauges.SetTexture("_BaseMap", tex["b17g_gauges"]); gauges.SetTexture("_MainTex", tex["b17g_gauges"]);
            Save(gauges, "gauges");
            Save(LitMat(lit, "B17G_navlight", new Color(0.3f, 0.3f, 0.3f), 0f, 0.8f), "navlight");
            Save(LitMat(lit, "B17G_screen", Color.black, 0f, 0.5f), "screen");
            foreach (var t in PrTextures)      // fal props: their own base colour on the generated UV (CopyMesh keeps UV0 for pr_*)
            {
                var key = t.Replace("b17g_", "").Replace("_b", "");
                if (t.EndsWith("_b")) key = t.Substring("b17g_".Length, t.Length - "b17g_".Length - 2);
                var m = LitMat(lit, "B17G_" + key, key == "pr_r1820" ? new Color(0.46f, 0.46f, 0.47f) : Color.white, key == "pr_r1820" ? 0.6f : 0.2f, 0.35f);   // 1.8.3: R-1820 face steel-dark as the reference
                m.SetTexture("_BaseMap", tex[t]); m.SetTexture("_MainTex", tex[t]);
                Save(m, key);
            }
            var glass = new Material(Asset<Material>("Material/COIN_glass_PLACEHOLDER.mat")) { name = "B17G_glass" };
            Save(glass, "glass");
            // FD-32 lesson (canopy_int darkened the whole view): the cockpit-layer glass copies use a faint transparent URP Lit
            // (a copy of the stock prop-disc material: transparent queue), not COIN_glass_int
            var glassCk = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "B17G_glass_ck" };
            glassCk.SetTexture("_BaseMap", null); glassCk.SetTexture("_MainTex", null);
            glassCk.SetColor("_BaseColor", new Color(0.86f, 0.92f, 0.97f, 0.06f)); glassCk.SetColor("_Color", new Color(0.86f, 0.92f, 0.97f, 0.06f));
            glassCk.SetFloat("_Smoothness", 0.95f); glassCk.SetFloat("_Cull", 0f);
            Save(glassCk, "glass_int");
            var disc = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "B17G_propdisc" };
            var blur = PropBlurTexture();
            disc.SetTexture("_BaseMap", blur); disc.SetTexture("_MainTex", blur);
            disc.SetTexture("_OcclusionMap", null); disc.DisableKeyword("_OCCLUSIONMAP");
            disc.SetColor("_BaseColor", Color.white); disc.SetColor("_Color", Color.white);
            disc.SetFloat("_Smoothness", 0.63f); disc.SetFloat("_Cull", 0f);
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
                if (gl >= 0) foreach (var i in m.GetIndices(gl)) paintV.Add(i);
                if (sc >= 0) foreach (var i in m.GetIndices(sc)) paintV.Add(i);   // MFD quads keep their 0-1 screen UVs
                for (int k = 0; k < orderedNames.Length; k++)                    // 2026-11-01 cockpit art atlas + fal props keep their own UVs
                    if (orderedNames[k] == "bk_art" || orderedNames[k].StartsWith("pr_")) foreach (var i in m.GetIndices(k)) paintV.Add(i);
                if (uv0.Count == m.vertexCount)
                {
                    for (int i = 0; i < uv0.Count; i++) if (!paintV.Contains(i)) uv0[i] = uv1[i];
                    m.SetUVs(0, uv0);
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
            var hull = HullSupportPoints(v, 96);
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
            // the FBX root (B17G_root at the CG) is the prefab root; the centre fuselage mesh object is called B17G in the model
            var centre = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t != root.transform && t.name == "B17G");
            if (centre == null) throw new Exception("centre fuselage object B17G missing");
            centre.name = "fus_center";
            // 1. our meshes and materials on every renderer
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                var mr = mf.GetComponent<MeshRenderer>();
                var names = mr.sharedMaterials.Select(m => m ? m.name.Replace(" (Instance)", "") : "null").ToArray();
                mf.sharedMesh = CopyMesh(mf.sharedMesh, mf.name, names, out var ordered);
                mr.sharedMaterials = ordered.Select(n => mats.TryGetValue(n, out var m) ? m : throw new Exception($"no material '{n}' for {mf.name}")).ToArray();
            }
            foreach (var t in root.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = 14;

            // 2. root components first
            GameObjectUtility.RemoveMonoBehavioursWithMissingScript(root);
            root.AddComponent<Mirage.NetworkIdentity>();
            var rb = root.AddComponent<Rigidbody>();
            EditorUtility.CopySerialized(tpl["COIN"].GetComponent<Rigidbody>(), rb);
            CloneComp(tpl["COIN"].GetComponent<Aircraft>(), root);

            // 3. structure
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
            Weapons();
            Cockpit(gears);
            RootSystems(gears);
            FlyByWire(gears[0]);
            ComputeSpawn(gears);

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
            // 1.8.3: internals the stock way (StockStructure.cs): frames, ribs, spars, stringers, engine mounts / accessory sections drawn
            // with the stock aircraft_structure material (vertex colour 93 / engines 99), after the colliders are baked
            var ss = StockStructure.Apply(root, StockStructure.LookMaterial(Asset<Material>("Material/aircraft_structure_PLACEHOLDER.mat"), Folder, "B17G"),
                new Dictionary<Material, Color32> { { mats["structure"], StockStructure.StockGrey }, { mats["engine"], StockStructure.StockEngineGrey } }, 1f, generatedMeshes);
            L($"stock structure: {ss.renderers} renderers, {ss.triangles} tris, {ss.children} structure children");
        }

        // ------------------------------------------------------------------ parts
        static void MakePartObject(PartSpec s)
        {
            GameObject go;
            if (s.name == "B17G") go = root;
            else if (s.name.StartsWith("prop_")) go = Find(s.name).gameObject;        // model empty at the hub (prop_hub_n + blades under it)
            else if (s.lift == Lift.Hinge)
            {
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
            if (s.parent != null) go.transform.SetParent(partGO[s.parent].transform, true);
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
            ap.dragArea = s.dragArea * PartDragScale;
            S(ap, "airfoil", s.airfoil);
            S(ap, "disintegrateObjects", new GameObject[0]);
            S(ap, "centerOfMass", null);
            S(ap, "connectedAnchor", null);
            S(ap, "joints", new PartJoint[0]);
            if (CrashImpactDamage && !s.name.StartsWith("prop_"))
            {   // Nimrod 1.4.1 lesson: a new ImpactDamage per part (stock templates: threshold 0 = no crash damage except the fuselage)
                var idf = Fld(ap.GetType(), "impactDamage");
                var id = Activator.CreateInstance(idf.FieldType);
                bool fabric = s.name.StartsWith("aileron") || s.name.StartsWith("elevator") || s.name.StartsWith("rudder");
                S(id, "threshold", fabric ? FabricImpactG : MetalImpactG); S(id, "multiplier", fabric ? FabricImpactMult : MetalImpactMult);
                idf.SetValue(ap, id);
            }
            MeshFilter own = s.name == "B17G" ? Find("fus_center").GetComponent<MeshFilter>()
                : s.lift == Lift.Hinge ? Find(s.name + "_visible").GetComponent<MeshFilter>()
                : s.mesh != null ? go.GetComponent<MeshFilter>() : null;
            if (own != null)
            {
                var mc = go.AddComponent<MeshCollider>();
                var hullSrc = go.transform.Find(s.name + "_hullsrc");
                mc.sharedMesh = hullSrc != null ? BakeCollider(go.transform, s.name + "_col", own, hullSrc.GetComponent<MeshFilter>()) : BakeCollider(go.transform, s.name + "_col", own);
                if (hullSrc != null) { L($"{s.name}: collider includes {hullSrc.name} (the 1.8.2 turbo), child deleted"); Object.DestroyImmediate(hullSrc.gameObject); }
                mc.convex = true;
            }
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
                    float inc = s.lift == Lift.Wing ? WingIncidence : StabIncidence;
                    q = Quaternion.AngleAxis(-inc, q * Vector3.right) * q;
                }
                ln = NewGO(s.name + "_liftNormal", go.transform, go.transform.position, q).transform;
                liftNormals[s.name] = ln;
            }
            S(ap, "liftNormal", ln);
            Vector3 col = Vector3.zero;
            if (s.wingArea > 0.9f && own != null && ln != null)
            {
                var b = own.sharedMesh.bounds;
                var lePt = own.transform.TransformPoint(new Vector3(b.center.x, b.center.y, b.max.z));
                var tePt = own.transform.TransformPoint(new Vector3(b.center.x, b.center.y, b.min.z));
                var qc = Vector3.Lerp(lePt, tePt, 0.25f);
                var centroid = go.transform.TransformPoint(go.GetComponent<MeshCollider>().sharedMesh.bounds.center);
                col = ln.InverseTransformVector(qc - centroid);
                // 1.6.4: a flap's lift increment acts near the wing's mid-chord, not on the flap itself (1.6.3 in game: the flap lift
                // behind the main wheels pitched the take-off roll down to 2 deg, wing AoA 5.5, no lift-off below 72 m/s)
                if (s.name.StartsWith("flap_")) col += ln.InverseTransformVector(Vector3.forward * FlapLiftForward);
            }
            S(ap, "centerOfLift", col);
            L($"part {s.name}: mass {s.mass} wingArea {s.wingArea} drag {s.dragArea} airfoil {s.airfoil} lift {(ln ? ln.name : "own")} col {col.ToString("F2")}");
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

        // span direction of a wing panel: 4 deg dihedral (blender/b17g/b17g_spec.py DIHEDRAL), +X on both sides like the stock wings
        static Vector3 SpanDir(string name)
        {
            float d = AeroDihedralDeg * Mathf.Deg2Rad;   // 1.7.4: aero dihedral 4 -> 8 deg (lift normals only; the model keeps its 4 deg)
            return name.EndsWith("_R") ? new Vector3(Mathf.Cos(d), Mathf.Sin(d), 0f) : new Vector3(Mathf.Cos(d), -Mathf.Sin(d), 0f);
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
                    Add(owner, other, other == "B17G" ? bySpec[owner].parent : other, Mathf.Min(bySpec[a].joint == 0 ? 1e6f : bySpec[a].joint, bySpec[b].joint == 0 ? 1e6f : bySpec[b].joint) * 0.3f);
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
                CS("aileron_" + side, "CAS1:aileron_" + side, 0, 18f * sgn, 0, 50f);
                CS("elevator_" + side, "CAS1:elevator_" + side, -ElevatorUp, 0, 0, 35f);
            }
            CS("rudder", "CAS1:rudder_L", 0, 0, -22f, 40f);
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

        // flaps: speed-scheduled HighLiftDevice on each flap part (B-25H method), split-flap travel 40 deg, down below 140 mph
        // 1.6.3 (in-game take-off test of 1.6.2): with the wing curve a 35 deg flap sat post-stall (flap AoA ~42 deg: CD 0.79, CL 0.95):
        // 27 kN of drag at 50 m/s for almost no lift, so the roll stalled at 51 m/s. Now airfoil 3 (B17G_flap), 28 deg, more area.
        const float FlapDeg = 28f, FlapAreaInner = 3.6f, FlapAreaOuter = 3.9f, FlapLiftForward = 1.6f;
        static void Flaps()
        {
            foreach (var f in new[] { "flap_inner_L", "flap_inner_R", "flap_outer_L", "flap_outer_R" })
            {
                var h = CloneComp(TplComp<HighLiftDevice>("COIN:flap_L"), parts[f].gameObject);
                S(h, "aeroPart", parts[f]); S(h, "swingWingController", null);
                S(h, "speedDeployed", 52f); S(h, "speedRetracted", 63f);
                S(h, "alphaMin", 0f); S(h, "alphaFactor", 0f);
                S(h, "deployedArea", f.Contains("inner") ? FlapAreaInner : FlapAreaOuter);
                var mp = NewElem(h, "movingParts");
                S(mp, "move", false); S(mp, "rotate", true); S(mp, "transform", liftNormals[f]);
                S(mp, "positionRetracted", Vector3.zero); S(mp, "positionDeployed", Vector3.zero);
                S(mp, "anglesRetracted", Vector3.zero); S(mp, "anglesDeployed", new Vector3(-FlapDeg, 0, 0));
                SetSeq(h, "movingParts", new[] { mp });
            }
        }

        // ------------------------------------------------------------------ landing gear (forward-retracting mains, retracting tailwheel)
        // Model: gear_main_L/R (leg, pivot = trunnion) > wheel_main_L/R (round tyre, pivot = axle); gear_tail > wheel_tail (round tyre) + fork_tail.
        // LandingGear spins every transform in `wheels` about its local X (LandingGear.cs 556-558) and steers `unsprung` about its local Y
        // (LandingGear.cs 718-724): the wheel transform carries the tyre ONLY; the tail fork rides on unsprung (steers, never spins).
        // Round 3 (user: whole tail assembly spun, no steering): the fal tail wheel was one mesh (wheel + fork) under wheel_tail; the tail
        // lock was +35 (B-25H nose-wheel sign; a wheel behind the CG steers the other way: Nimrod / FD-32 use -30, verified live) and its
        // frictionCoef 0.1 (stock CAS1 gear_F 0.8, CAS1.prefab:8697): no side grip to turn 25 t.
        // LandingGear folds gearHinge about its local X by foldDegrees (LandingGear.cs OnSetGear). Blender forward-up +90 about +X is
        // Unity -90 (handedness flip, export_b17g.py rule); the check verifies the stowed wheel moves FORWARD and UP.
        // Springs sized for 25 t: static load per main ~11 t -> k 1.6 MN/m gives ~6.9 cm static sag; damping ~0.35 critical.
        class GearSpec { public string leg, wheel, part, fork; public float fold, travel, k, c, maxComp, mass, drag, r; public bool steer, brake; public float diff; }
        const float MainK = 1.6e6f, MainC = 1.3e5f, MainMaxComp = 0.45f, TailK = 3.5e5f, TailC = 3.0e4f;
        // 1.6.1 ground handling (in game 1.6.0: no steering, 1.74 m/s2 braking, nose-over on grass at 119 km/h):
        // - BrakeFriction 0.29 (was 0.20): braking ~2.6 m/s2, holds ~62 kN (0.6 throttle ~53 kN); nose-over margin kept >= 3 deg by the
        //   10.4 deg forward leg rake (b17g_spec.MAIN_RAKE 0.25 m: tail-up CoM angle ~19.4 deg vs atan 0.29 = 16.2 deg);
        // - MainContactArea 0.09 m2 (was CAS1's 0.04): LandingGear.cs 334-342 sinks a wheel into soft ground by pressure
        //   (load / (contactArea x 1e4)) and drags it with 2.5 depth^2 |v| pressure^2: at 115 kN per main and 33 m/s that is ~200 kN per
        //   wheel with 0.04 (the grass nose-over) and ~9 kN with 0.09 (a 56 in tyre's real patch is ~0.2 m2);
        // - MainRolling 0.02 (CAS1 0.05; AB-4 0.01): concrete rolling resistance of big low-pressure tyres;
        // - DiffBrake 2.0 (was 1): LandingGear.cs 551-553 adds Clamp01(yaw x 0.3 x factor) brake on the inside main between 3 and 30 m/s.
        // 1.7.3: 0.29 -> 0.22. In game (1.7.2) a full-brake stop from a 68 m/s tail-up touchdown nosed over (pitch -36 deg at 7 m/s,
        // tail gun and rudder broke off on the fall back); margin now atan 0.22 = 12.4 deg vs the 19.4 deg tail-up CoM angle.
        // 1.7.12 (in game 1.7.10 P6: 1 of 3 landed AI B-17Gs circled its exit-taxi point at 9 m/s, r ~50 m, for 10+ min): the mains' side grip is
        // frictionCoef x load = 0.22 g (the 1.7.3 brake nose-over value), so at 9 m/s no turn tighter than v^2 / (0.22 g) ~ 38 m is possible and
        // the exit point (arrival < 20 m, AIPilotTaxiState) stays inside the circle. Brake friction stays (nose-over); instead the inner-wheel
        // differential brake (LandingGear: + Clamp01(yaw x 0.3 x factor) between 3 and 30 m/s) 2 -> 3.5 slows it in hard taxi turns
        // (yaw 0.6: 0.36 -> 0.63 brake on the inner main) and the tail-wheel lock -30 -> -45 tightens the steered radius.
        // 1.8.0 (user on 1.7.13: "keep spinning out on runways"): split main wheel (GripGear.cs, groundcom.py): the braked LandingGear and an
        // unbraked grip LandingGear on the same contact, both frictionCoef MainFriction 0.8 (stock); the braked one carries MainBrakeShare of the
        // spring, so braking stays BrakeFriction 0.22 x load (= 0.8 x 0.275, the 1.7.3 nose-over value) and the side grip is 0.8 x load (the
        // 1.7.10 exit-taxi circle: a 9 m/s turn now needs ~10 m instead of ~38 m).
        const float MainFriction = 0.8f, MainBrakeShare = 0.275f;
        const bool SplitMainGear = true;
        // 1.8.8 (user on 1.8.7: line up, full throttle, no input -> veers left or right after ~100 m, onto the grass): castoring mains
        // (GripGear.Castor; tools/flightmodel/taildragger_track.py). The 1.8.3 take-off log: the tail wheel's load falls with V^2 (32.8 kN at rest,
        // 0 from 30.8 m/s ~110 m) and the heading starts to move right then (yaw rate x2.5 per second); from there only the mains, 1.4 m AHEAD of
        // the CoM, grip, and a gripping wheel ahead of the CoM is directionally unstable (LandingGear side force, 627-656). Stock tricycles keep
        // their gripping wheels behind the CoM and castor the one in front (aligningStrength 5); this is that arrangement mirrored: the mains
        // castor within +-MainCastorRange, the tail wheel stays locked (TailAligning 0). Model, no input: 90 % heading change 9.8 -> 0.09 deg,
        // lateral 32.6 -> 0.34 m (stock A-19 0.08 deg / 0.61 m); taxi 7 m/s 6 s 164 -> 156 deg. false = the 1.8.7 behaviour.
        const bool MainCastor188 = true;
        const bool ColumnPlugin189 = true;
        const bool ANM2Guns = true;             // 1.8.13 (offline L): our own AN/M2 on every gun slot (ANM2Gun.cs); false = the stock door-gun barrel      // 1.8.9 (offline J): the columns / wheels are moved by B25H.Instruments (b17g_joystick.cs), no Cockpit.joysticks
        const float MainCastorRange = 6f, MainCastorAlign = 5f;
        const float BrakeFriction = 0.22f, MainContactArea = 0.09f, MainRolling = 0.02f, DiffBrake = 3.5f, MainFoldDeg = 79.7f;
        // tail wheel behind the CG: negative lock (rudder right -> wheel left -> tail swings left -> nose right). aligningStrength 0: no
        // castering (LandingGear.cs 602-606 turns the wheel toward the ground track), so the wheel stays at yaw x lock and resists a swing
        // like the B-17's locked tailwheel; full lock radius about the main-gear centre = wheelbase 11.8 m / tan 30 = 20 m.
        const float TailSteeringLock = -45f, TailSteeringSpeed = 60f, TailAligning = 0f, TailFriction = 0.8f;   // 1.7.12: -30 -> -45 (exit-taxi circle)
        static readonly Dictionary<LandingGear, Transform> gearWheelVisual = new Dictionary<LandingGear, Transform>();

        static List<LandingGear> Gear()
        {
            gearWheelVisual.Clear();
            var list = new List<LandingGear>();
            foreach (var s in new[] { "L", "R" })
                list.Add(MakeGear(new GearSpec { leg = "gear_main_" + s, wheel = "wheel_main_" + s, part = "wing_inner_" + s, fold = -MainFoldDeg, travel = 0.711f + 0.35f, k = MainK, c = MainC,
                    maxComp = MainMaxComp, mass = 450f, drag = MainGearDrag, r = 0.711f, steer = false, brake = true, diff = s == "L" ? -DiffBrake : DiffBrake }, "CAS1:gear_" + s + "_sprung", "COIN:wheel_" + s));
            list.Add(MakeGear(new GearSpec { leg = "gear_tail", wheel = "wheel_tail", part = "fus_tail", fold = 27f, travel = 0.33f + 0.20f, k = TailK, c = TailC,
                maxComp = 0.30f, mass = 80f, drag = TailGearDrag, r = 0.33f, steer = true, brake = false, diff = 0f, fork = "fork_tail" }, "CAS1:gear_F_sprung", "COIN:wheel_F"));
            return list;
        }

        static LandingGear MakeGear(GearSpec g, string tplGear, string tplWheel)
        {
            var leg = Find(g.leg); var wheel = Find(g.wheel); var part = parts[g.part];
            float r = g.r;
            Vector3 axle = wheel.position;
            var hinge = NewGO(g.leg + "_hinge", part.transform, leg.position, part.transform.rotation);
            leg.SetParent(hinge.transform, true);
            var sprung = NewGO(g.leg + "_sprung", hinge.transform, leg.position, part.transform.rotation);
            var unsprung = NewGO(g.leg + "_unsprung", sprung.transform, axle, part.transform.rotation);
            wheel.SetParent(unsprung.transform, true);
            if (!string.IsNullOrEmpty(g.fork)) Find(g.fork).SetParent(unsprung.transform, true);      // steers with the wheel, does not spin
            var bump = NewGO(g.leg + "_bumpstop", sprung.transform, axle + Vector3.up * (g.travel - r), part.transform.rotation);
            var dust = CopyParticle(TplFind(tplWheel).GetComponent<ParticleSystem>(), unsprung.transform, axle - Vector3.up * r, g.leg + "_dust");
            var tw = TplFind(tplWheel).GetComponents<AudioSource>();
            var a0 = CloneComp(tw[0], wheel.gameObject); var a1 = CloneComp(tw[1], wheel.gameObject);
            var box = sprung.AddComponent<BoxCollider>();
            var lmf = leg.GetComponent<MeshFilter>();
            var sb = lmf != null ? lmf.sharedMesh.bounds : new Bounds(Vector3.zero, Vector3.one * 0.1f);
            box.center = sprung.transform.InverseTransformPoint(leg.TransformPoint(sb.center)); box.size = sb.size; box.enabled = false;
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
            S(lg, "gearHinge", hinge.transform); S(lg, "hingeFoldMotion", Vector3.zero);
            S(lg, "foldDegrees", g.fold); S(lg, "foldSpeed", 12f);
            S(lg, "strutRotationTransform", null); S(lg, "strutRotation", 0f);
            SetSeq(lg, "movingParts", new object[0]);
            S(lg, "steering", g.steer); S(lg, "braked", g.brake);
            S(lg, "steeringLock", g.steer ? TailSteeringLock : 0f); S(lg, "steeringSpeed", g.steer ? TailSteeringSpeed : 0f); S(lg, "aligningStrength", g.steer ? TailAligning : 0f);
            S(lg, "differentialBrakeFactor", g.diff);
            S(lg, "frictionCoef", g.brake ? (SplitMainGear ? MainFriction : BrakeFriction) : TailFriction);
            if (g.brake) { S(lg, "contactArea", MainContactArea); S(lg, "rollingResistance", MainRolling); }
            S(lg, "dust", dust);
            S(lg, "gearDoors", new List<LandingGear.GearDoor>());
            gearWheelVisual[lg] = wheel;
            L($"gear {g.leg}: r={r:F3} axle={axle.ToString("F3")} travel={g.travel} k={g.k} c={g.c} fold={g.fold}");
            if (g.brake && SplitMainGear) GripGear.Add(lg, MainBrakeShare, MainFriction, L);
            if (g.brake && MainCastor188) GripGear.Castor(lg, MainCastorRange, MainCastorAlign, L);     // after the split: the grip leg copies `axle`, not `steering`
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
        // four engines: the B-25H's per-engine set (TurbineEngine + own Transmission on engine_n, ConstantSpeedProp + PropStrikeDetector on
        // prop_n), so an engine kill stops only its own prop; asymmetric thrust comes from the physics. AB-4 messages "ENGINE n FIRE".
        static readonly int[] EngineNums = { 1, 2, 3, 4 };
        static void Engines()
        {
            var startup = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), parts["fus_cockpit"].gameObject);
            var ab4 = AB4EngineMessages ? AB4Messages() : new Dictionary<int, (string, AudioClip)>();
            foreach (var n in EngineNums)
            {
                var side = n <= 2 ? "L" : "R";
                var eng = parts["engine_" + n].gameObject;
                CloneComp(TplAudio("COIN:COIN", "cricket_turbine"), eng);
                var te = CloneComp(TplComp<TurbineEngine>("CAS1:engine_" + side), eng);
                te.maxRPM = 2300f; te.minRPM = 550f; te.maxPower = EnginePower; te.spoolUpTime = 3f; S(te, "startupTime", 6f + n * 0.8f);
                S(te, "pitch", 0.15f); S(te, "volume", 0.06f);
                S(te, "startupAudio", startup); te.aircraft = aircraft;
                S(te, "heatHazeParticles", new ParticleSystem[0]);
                S(te, "maxFuelConsumption", 0.075f); S(te, "IRMin", 1.2f); S(te, "IRMax", 1.6f);
                S(te, "IRSourceTransform", Find("exhaust_" + n));
                S(te, "criticalParts", new UnitPart[] { parts["engine_" + n], parts["prop_" + n] });
                S(te, "criticalDamageThreshold", 40f);
                if (ab4.TryGetValue(n, out var msg)) { S(te, "failureMessage", msg.Item1); S(te, "failureMessageAudio", msg.Item2); }
                else S(te, "failureMessage", $"ENGINE {n} FIRE");
                S(te, "failureTransform", NewGO("engine_" + n + "_fail", eng.transform, eng.transform.position + new Vector3(0, 0.3f, -0.4f), Quaternion.identity).transform);
                var tr = CloneComp(TplComp<Transmission>("COIN:COIN"), eng);
                S(tr, "powerSources", new[] { eng });

                var propGO = parts["prop_" + n].gameObject;
                var hubVis = Find("prop_hub_" + n);
                var pa = CloneComp(TplAudio("COIN:propHub", "cricket_exterior"), propGO);
                var csp = CloneComp(TplComp<ConstantSpeedProp>("COIN:propHub"), propGO);
                S(csp, "unitPart", parts["prop_" + n]); S(csp, "transmission", tr); S(csp, "oppositeCorner", null);
                var fTurn = Fld(typeof(ConstantSpeedProp), "turnDirection"); fTurn.SetValue(csp, Enum.ToObject(fTurn.FieldType, PropTurn[n]));   // 1.7.8: handed (3-4 turn the other way, mirrored blades): no net torque
                var fPitch = Fld(typeof(ConstantSpeedProp), "pitchDirection"); fPitch.SetValue(csp, Enum.ToObject(fPitch.FieldType, -1));
                var blades = new List<object>(); var dmgMeshes = new List<Mesh>();
                float R = 0f;
                var bladeMFs = hubVis.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.Contains("_blade")).OrderBy(m => m.name).ToList();
                foreach (var bmf in bladeMFs)
                {
                    var radial = bmf.transform.up;
                    float tip = bmf.sharedMesh.bounds.max.y; R = Mathf.Max(R, tip);
                    var F = propGO.transform.forward;
                    var broot = NewGO(bmf.name + "_root", hubVis, hubVis.position, Quaternion.LookRotation(radial, Vector3.Cross(radial, -F)));
                    bmf.transform.SetParent(broot.transform, true);
                    var tang = Vector3.Cross(-F, radial) * PropTurn[n];     // the blade's motion direction (ConstantSpeedProp: Cross(-hub.fwd, blade.fwd) x turnDirection)
                    var lt = NewGO(bmf.name + "_lift", broot.transform, hubVis.position + radial * tip, Quaternion.LookRotation(tang, F));
                    var b = New(typeof(ConstantSpeedProp.PropBlade));
                    S(b, "transform", broot.transform); S(b, "liftTransform", lt.transform); S(b, "mass", 60f);
                    ((ConstantSpeedProp.PropBlade)b).renderer = bmf.GetComponent<MeshRenderer>();
                    ((ConstantSpeedProp.PropBlade)b).bladeMeshFilter = bmf;
                    blades.Add(b);
                    if (dmgMeshes.Count == 0)
                        foreach (var frac in new[] { 0.25f, 0.5f, 0.75f, 0.95f }) dmgMeshes.Add(TruncatedBlade(bmf.sharedMesh, tip * frac, $"{bmf.name}_dmg{(int)(frac * 100)}"));
                }
                if (R < 1f) R = 1.765f;
                SetSeq(csp, "blades", blades);
                S(csp, "hubVisible", hubVis.gameObject);
                var disc = NewGO("prop_" + n + "_disc", hubVis, hubVis.position + propGO.transform.forward * 0.02f, Quaternion.LookRotation(propGO.transform.forward, Vector3.up));
                disc.AddComponent<MeshFilter>(); var dr = disc.AddComponent<MeshRenderer>(); dr.sharedMaterial = mats["propdisc"];
                dr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                disc.GetComponent<MeshFilter>().sharedMesh = null;
                var stage1 = BlurStageMesh("prop_blur1_" + n, R * 1.01f, 0.5f); var stage2 = BlurStageMesh("prop_blur2_" + n, R * 1.01f, 0f);
                S(csp, "propDisc", disc.GetComponent<MeshFilter>());
                S(csp, "bladeDamageMeshes", dmgMeshes.ToArray());
                S(csp, "fragmentPrefab", null);
                SetSeq(csp, "propDiscMeshes", new Mesh[] { null, stage1, stage2 });
                S(csp, "propDiskThicknessMin", 1f); S(csp, "propDiskThicknessMax", 1f);
                S(csp, "propBlurLightsMaterial", null);
                var strikeGO = NewGO("prop_" + n + "_strike", propGO.transform, hubVis.position, Quaternion.LookRotation(propGO.transform.forward, Vector3.up), 15);
                var smc = strikeGO.AddComponent<MeshCollider>(); smc.sharedMesh = CylinderMesh("prop_strike_" + n, R, 0.06f, 24); smc.convex = true; smc.isTrigger = true;
                var psd = CloneComp(TplComp<PropStrikeDetector>("COIN:propDiscCollider"), strikeGO);
                S(psd, "currentRadius", R); S(psd, "propCollider", smc);
                S(csp, "propDiscCollider", smc); S(csp, "propStrikeDetector", psd);
                S(csp, "momentOfInertia", 180f); S(csp, "bladeLength", R); S(csp, "hubRadius", 0.30f);
                S(csp, "rpmLimit", PropRpm); S(csp, "nominalPower", EnginePower); S(csp, "propTorqueLimit", 15000f);
                S(csp, "propAudio", pa);
                L($"prop {n}: radius {R:F3} m, {blades.Count} blades, turn {PropTurn[n]}, rpmLimit {PropRpm}, hub {hubVis.position.ToString("F3")}{(ab4.ContainsKey(n) ? ", AB-4 message '" + ab4[n].Item1 + "'" : "")}");
            }
        }

        // the AB-4 (FastBomber1) failure messages + voice clips: the component that carries failureMessage "ENGINE n FIRE"
        static Dictionary<int, (string, AudioClip)> AB4Messages()
        {
            var d = new Dictionary<int, (string, AudioClip)>();
            var p = AssetDatabase.LoadAssetAtPath<GameObject>($"{DNS}/GameObject/FastBomber1_PLACEHOLDER.prefab");
            if (p == null) { L("WARN AB-4 placeholder missing: plain ENGINE n FIRE text"); return d; }
            foreach (var c in p.GetComponentsInChildren<Component>(true))
            {
                if (c == null) continue;
                FieldInfo fm = null, fa = null;
                for (var t = c.GetType(); t != null && fm == null; t = t.BaseType) { fm = t.GetField("failureMessage", BF | BindingFlags.DeclaredOnly); fa = t.GetField("failureMessageAudio", BF | BindingFlags.DeclaredOnly); }
                if (fm == null) continue;
                var m = fm.GetValue(c) as string;
                if (m == null || !m.StartsWith("ENGINE ") || !m.EndsWith(" FIRE")) continue;
                if (int.TryParse(m.Substring(7, 1), out int n)) d[n] = (m, fa != null ? fa.GetValue(c) as AudioClip : null);
            }
            L($"AB-4 engine messages: {string.Join(", ", d.OrderBy(k => k.Key).Select(k => k.Value.Item1 + (k.Value.Item2 ? " (voice)" : "")))}");
            return d;
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
            var pts = new[] { (0f, 0.008f), (0.06f, 0.021f), (0.1f, 0.036f), (0.2f, 0.082f), (0.28f, 0.13f), (0.35f, 0.25f), (0.5f, 0.5f), (1.51f, 1.7f), (3.14159f, 0f) };
            var keys = new List<Keyframe>();
            foreach (var (t, v) in pts.Reverse()) if (t > 0f) keys.Add(new Keyframe(-t, v));
            foreach (var (t, v) in pts) keys.Add(new Keyframe(t, v));
            var c = new AnimationCurve(keys.ToArray());
            for (int i = 0; i < c.length; i++) c.SmoothTangents(i, 0f);
            return c;
        }

        static WeaponMount ammoCannon, ammo50;
        static readonly List<(string station, WeaponMount ammo, HardpointSet set)> stationSets = new List<(string, WeaponMount, HardpointSet)>();
        static HardpointSet baySet;
        static List<Gun> Weapons()
        {
            stationSets.Clear();
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
            // bomb bay: centre hardpoint, two doors hinged at the outer edges (EW1 BayDoor values, B-25H method). Blender +92 deg about +Y (L)
            // = Unity -92 about +Z; the check verifies both doors swing DOWN and OUT.
            var bay = Find("hp_bombbay");
            var doorAudio = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), bay.gameObject);
            doorAudio.clip = null; doorAudio.loop = false; doorAudio.playOnAwake = false; doorAudio.volume = 0.8f;
            var bayDoors = new List<BayDoor>();
            foreach (var (dn, open) in new[] { ("bay_door_L", -92f), ("bay_door_R", 92f) })
            {
                var hb = DoorHinge(Find(dn), Vector3.forward, open, false);
                var bd = CloneComp(TplComp<BayDoor>("EW1:weapon_door_hinge_L"), hb.gameObject);
                S(bd, "hingeAngle", open); S(bd, "openSpeed", 1.0f); S(bd, "closeSpeed", 0.7f); S(bd, "doorAudioSource", doorAudio);
                bayDoors.Add(bd);
            }
            // user decision 2026-11-03: 8 x PAB-250 (default), 4 x GPO-500 (stacked, bay lengthened to 2.95 m), 2 x CBO-400, GPO-N; no wing racks
            // 1.6.1: the stock CBO-400 mounts are switched off in the game data (bomb_cluster1_dual_internal.asset 'disabled: 1'; WeaponChecker
            // .MountAllowedHQ -> WeaponMount.IsAllowed drops them, WeaponMount.cs 93-97), so 1.6.0 showed no CBO-400. The B-17G carries its
            // own enabled copy (same prefab, info and 2 bombs). GPO-N stays the stock mount: the hangar offers a nuclear mount only when the
            // mission allows tactical weapons, the player's rank reaches tacticalMinRank and the airbase holds the warheads
            // (WeaponChecker.MountAllowedNuclear, WeaponChecker.cs 184-199) - mission rules, not the aircraft.
            var bayMounts = new List<WeaponMount> { Mount("bomb_250_internalx8"), Mount("bomb_500_internalx4_stack") };
            if (ClusterBombOption)
            {
                var cbo = Object.Instantiate(Mount("bomb_cluster1_dual_internal")); cbo.name = "B17G_cbo400_x2"; cbo.jsonKey = cbo.name; cbo.mountName = "CBO-400 x2";
                S(cbo, "disabled", false);
                AssetDatabase.CreateAsset(cbo, Folder + "/" + cbo.name + ".asset");
                bayMounts.Add(cbo);
            }
            if (NuclearOptions) bayMounts.Add(Mount("nuclearBomb1_internal"));
            baySet = Set("Bomb Bay", bayMounts, HP(bay, parts["B17G"], null, bayDoors.ToArray(), 1.5f));

            // gun stations: 13 stock 12.7 mm in 9 positions. One renamed copy of the stock Gun12.7mm info per STATION (stations are keyed by
            // WeaponInfo: WeaponManager.cs:403-438, Turret.cs:242), so a power turret never fires because a waist gun saw a target
            // (WeaponStation.Fire fires every gun of its station, WeaponStation.cs:523).
            var tAmmo = Asset<WeaponMount>("MonoBehaviour/gun_ammo_35mm_720_PLACEHOLDER.asset");
            var ammoPrefabGO = new GameObject("B17G_internal_ammo");
            var ammoPrefab = PrefabUtility.SaveAsPrefabAsset(ammoPrefabGO, Folder + "/B17G_internal_ammo.prefab");
            Object.DestroyImmediate(ammoPrefabGO);
            if (DefensiveTurrets && contract != null)
            {
                BuildTurrets();
                foreach (var g in turrets.GroupBy(t => t.station).OrderBy(g => Array.IndexOf(StationOrder, g.Key)))
                {
                    var info = stationInfos[g.Key];
                    var ammo = Object.Instantiate(tAmmo); ammo.name = "B17G_ammo_" + g.Key.ToLowerInvariant();
                    ammo.prefab = ammoPrefab; ammo.jsonKey = ammo.name; ammo.info = info;
                    int perCycle = g.Sum(t => (int)G(t.gun, "magazineCapacity")), barrels = g.Sum(t => ((Transform[])G(t.gun, "muzzles")).Length);
                    ammo.ammo = perCycle; ammo.GunAmmo = true; ammo.mass = g.Sum(t => (int)G(t.gun, "magazineCapacity") * ((Transform[])G(t.gun, "muzzles")).Length) * 0.11f;
                    ammo.mountName = $".50 cal {g.Key} x{barrels}";
                    AssetDatabase.CreateAsset(ammo, Folder + "/" + ammo.name + ".asset");
                    var hs = Set(g.Key + " guns", new[] { ammo }, g.Select(t => { var h = HP(t.mount, t.part, new Weapon[] { t.gun }); h.BuiltInTurrets = new[] { t.turret }; return h; }).ToArray());
                    stationSets.Add((g.Key, ammo, hs));
                }
            }
            var all = sets.SelectMany(x => x.hardpoints).OrderByDescending(h => h.transform.position.x).ThenByDescending(h => h.transform.position.z).ToList();
            for (int i = 0; i < all.Count; i++) all[i].HardpointIndex = i;
            weaponManager.hardpointSets = sets.ToArray();
            S(weaponManager, "aircraft", aircraft);
            L($"hardpoint sets: {string.Join(" | ", sets.Select(x => $"{x.name} ({x.hardpoints.Count} hp, {x.weaponOptions.Count - 1} options)"))}");
            return turrets.Select(t => t.gun).ToList();
        }

        static WeaponMount Mount(string n) => Asset<WeaponMount>($"MonoBehaviour/{n}_PLACEHOLDER.asset");

        static ParticleSystem[] CopyMuzzleParticles(Gun template, Transform muzzle)
        {
            var src = (ParticleSystem[])G(template, "muzzleParticles") ?? new ParticleSystem[0];
            return src.Where(p => p != null).Select(p => CopyParticle(p, muzzle, muzzle.position, muzzle.name + "_" + p.name)).Select(p => { p.transform.rotation = muzzle.rotation; return p; }).ToArray();
        }

        // ------------------------------------------------------------------ cockpit, crew, canopy
        // Model contract (model worker): assets/model_v2/b17g_contract.json - object names, pivots, axes, limits.
        static Newtonsoft.Json.Linq.JObject contract;
        static Newtonsoft.Json.Linq.JObject LoadContract()
        {
            var p = Path.Combine(Path.GetDirectoryName(RepoModel), "b17g_contract.json");
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
        const float YokeJoystickRange = 30f;   // 1.6.1: wheel roll / tilt range (deg)
        static readonly List<string> cockpitAnimLog = new List<string>();
        static readonly Dictionary<string, float> throttleForward = new Dictionary<string, float>();

        static Transform helmetCam;
        static void Cockpit(List<LandingGear> gears)
        {
            var cp = parts["fus_cockpit"];
            var eye = Find("cockpit_eye");

            // ---- crew: pilot (+4 with FiveCrew)
            crew.Clear();
            var stations = FiveCrew ? JList("crew", "stations").ToList() : new List<Newtonsoft.Json.Linq.JToken>();
            if (stations.Count == 0)
                crew.Add(MakeCrewMember(new CrewSpec { role = "pilot", part = "fus_cockpit", eye = eye, exit = Pilot.ExitDirection.Left, hatch = null }, 0));
            else
            {
                int i = 0;
                foreach (var st in stations)
                {
                    var e = TryFind((string)st["eye"]["name"]);
                    if (e == null) { L($"WARN crew {(string)st["role"]}: eye {(string)st["eye"]["name"]} not in the model, skipped"); continue; }
                    var exit = e.position.x > 0.05f ? Pilot.ExitDirection.Right : e.position.x < -0.05f ? Pilot.ExitDirection.Left : (i % 2 == 0 ? Pilot.ExitDirection.Left : Pilot.ExitDirection.Right);
                    crew.Add(MakeCrewMember(new CrewSpec { role = (string)st["role"], part = (string)st["part"], eye = e, exit = exit, hatch = (string)st["exit_hatch"] }, i));
                    i++;
                }
            }
            L($"pilot eye {helmetCam.position.ToString("F3")} vs cockpit_eye {eye.position.ToString("F3")}");

            // ---- bail-out hatches (stock Canopy), from the contract
            var canopies = new List<Canopy>();
            if (FiveCrew)
                foreach (var h in JList("hatches", "hatches"))
                {
                    var hatch = TryFind((string)h["hatch"]["name"]); var hinge = TryFind((string)h["hinge"]["name"]);
                    var pp = (string)h["parent_part"];
                    if (hatch == null || hinge == null || !parts.ContainsKey(pp)) { L($"WARN hatch {(string)h["hatch"]["name"]} missing, skipped"); continue; }
                    var glass = hatch.GetComponent<MeshRenderer>() != null && hatch.GetComponent<MeshRenderer>().sharedMaterials.Contains(mats["glass"]) ? new Renderer[] { hatch.GetComponent<MeshRenderer>() } : new Renderer[0];
                    canopies.Add(MakeHatchFromContract(hatch, hinge, (float)h["hingeAngle"], parts[pp], glass));
                }
            S(aircraft, "canopies", canopies.ToArray());

            // ---- cockpit-only copies on the Cockpit layer (3); exterior originals hidden in cockpit view (stock pattern)
            var cockpitR = new List<Renderer>(); var exteriorR = new List<Renderer>();
            var copyNames = new List<string> { "fus_cockpit" };
            copyNames.AddRange(root.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.StartsWith("cockpit_") || m.name.StartsWith("gauge_")).Select(m => m.name));
            foreach (var n in copyNames.Distinct())
            {
                var orig = TryFind(n);
                if (orig == null || orig.GetComponent<MeshRenderer>() == null) continue;
                var src = orig.GetComponent<MeshRenderer>();
                if (src.sharedMaterials.All(m => m == mats["glass"])) continue;
                var copy = NewGO(n + "_int", orig, orig.position, orig.rotation, 3);
                copy.AddComponent<MeshFilter>().sharedMesh = orig.GetComponent<MeshFilter>().sharedMesh;
                var cr = copy.AddComponent<MeshRenderer>();
                cr.sharedMaterials = src.sharedMaterials.Select(m => m == mats["glass"] ? mats["glass_int"] : m).ToArray();
                cr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                cr.enabled = false; // the game enables cockpit renderers (and hides the exterior ones) in cockpit view
                cockpitR.Add(cr); exteriorR.Add(src);
                // performance pass: the exterior originals of cockpit-only meshes (hidden in cockpit view, inside the closed
                // fuselage in external view) cast no shadows; the fuselage / canopy / hatch keep theirs
                if (CockpitPropsNoShadow && !(n == "fus_cockpit" || n == "fus_forward" || n == "canopy_frame" || n == "hatch_cockpit_top"))
                    src.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                if (src.sharedMaterials[0] == mats["paint"])
                {
                    var owner = parts.Values.First(p => PartRenderers(p.gameObject).Contains(src));
                    ((List<Renderer>)G(G(owner, "damageMaterial"), "renderers")).Add(cr);
                }
            }
            S(aircraft, "cockpitRenderers", cockpitR.ToArray());
            S(aircraft, "exteriorRenderers", exteriorR.ToArray());

            // ---- screens: mfd_center = the tac screen (Cockpit.tacScreenRender + TargetCam.targetScreenRenderer, as the
            // CI-22's single targetScreen renderer); mfd_left = the tac screen again; mfd_right = the target-camera feed
            // (stock targetCamDisplay material = TargetWindowRender RT, drawn by the tac-screen UI while the camera is up).
            // Without the model screens: a small hidden quad (1.0 behaviour).
            Renderer tacR = null;
            var mfdC = MFDScreens ? TryFind("mfd_center") : null;
            if (mfdC != null && mfdC.GetComponent<MeshRenderer>() != null)
            {
                var tacMat = Asset<Material>("Material/tacScreenDisplay_PLACEHOLDER.mat");
                var camMat = Asset<Material>("Material/targetCamDisplay_PLACEHOLDER.mat");
                foreach (var (n, m) in new[] { ("mfd_center", tacMat), ("mfd_left", tacMat), ("mfd_right", WsoScreenTacPage ? tacMat : camMat) })
                {
                    var t = TryFind(n); if (t == null) continue;
                    foreach (var r in t.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.transform == t || r.name == n + "_int"))
                    { r.sharedMaterials = Enumerable.Repeat(m, r.sharedMaterials.Length).ToArray(); r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; }
                }
                if (TacScreenPanels)
                    foreach (var n in WsoScreenTacPage ? new[] { "mfd_center", "mfd_left", "mfd_right" } : new[] { "mfd_center", "mfd_left" })
                    {
                        var t = TryFind(n); if (t == null) continue;
                        foreach (var r in t.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.transform == t || r.name == n + "_int"))
                        {
                            var mf = r.GetComponent<MeshFilter>();
                            mf.sharedMesh = TacScreenMesh(mf.sharedMesh, n + "_tac");
                            r.sharedMaterials = new[] { tacMat, mats["screen"] };
                        }
                    }
                tacR = mfdC.GetComponent<MeshRenderer>();
                L($"screens: mfd_center/mfd_left = tacScreenDisplay{(TacScreenPanels ? " (map + 3 upright side panels)" : "")}, mfd_right = {(WsoScreenTacPage ? "tacScreenDisplay (target video inside the tac page)" : "targetCamDisplay")}");
            }
            else
            {
                var screen = NewGO("screen_dummy", cp.transform, Find("cockpit_interior").position + new Vector3(0, -0.2f, -0.05f), Quaternion.identity, 3);
                screen.AddComponent<MeshFilter>().sharedMesh = QuadMesh("screen_dummy", 0.01f, 0.01f);
                var sr = screen.AddComponent<MeshRenderer>(); sr.sharedMaterial = mats["screen"]; sr.enabled = false;
                tacR = sr;
                L("WARN screens: no mfd_center in the model, hidden dummy screen (1.0 behaviour)");
            }

            var interior = Find("cockpit_interior").gameObject;
            var ck = CloneComp(TplComp<global::Cockpit>("COIN:cockpit_F_interior"), interior);
            S(ck, "tacScreenRender", tacR); S(ck, "aircraft", aircraft);
            S(ck, "engineSources", EngineNums.Select(n => parts["engine_" + n].gameObject).ToArray());
            SetSeq(ck, "joysticks", new object[0]);   // the yoke is driven by ControlSurfaces below (column pitch, wheel roll)
            SetSeq(ck, "throttles", new object[0]);
            if (CockpitAnimators)
            {
            CockpitAnimation(ck, cp);
            // 1.6.1 (in game 1.6.0 the ControlSurface-driven columns / wheels never moved, 07_yoke_*): each wheel rode a Cockpit.joysticks
            // entry at its hub (Cockpit.cs 16-19: localEulerAngles = (pitch x range, 0, -roll x range)): the wheel tilted at the hub and the
            // column never moved. 1.8.9 (offline J; user on 1.8.8: "The WHEEL moves, the stick does not"): ColumnPlugin189 = no joystick entry;
            // the B25H.Instruments B17G branch (B17G.cs ColumnDeg / WheelDeg) pitches cockpit_column_L/R about their floor pivots (local +X =
            // lateral) and turns cockpit_yoke_L/R about their hub axes (local +X = toward the pilot); the wheels stay children of the columns,
            // so the column carries the wheel. A two-joystick hierarchy cannot do it: the stock driver writes pitch AND roll on every entry, so a
            // column entry would also roll the column (and the wheel with it) about the column frame's Z: a stray yaw of the wheel.
            // unity/Editor/ColumnCheck189.cs proves pitch / roll / no-yaw on the built prefab with the plugin's formula.
            {
                var js = new List<object>();
                foreach (var side in new[] { "L", "R" })
                {
                    var y = TryFind("cockpit_yoke_" + side); var col = TryFind("cockpit_column_" + side);
                    if (y == null) continue;
                    foreach (var c in new[] { y, col }) if (c != null) foreach (var cs in c.GetComponents<ControlSurface>()) Object.DestroyImmediate(cs);
                    if (ColumnPlugin189)
                    {
                        cockpitAnimLog.Add($"{y.name}: no Cockpit.joysticks (1.8.9: B25H.Instruments turns it about its hub axis {y.right.ToString("F2")}); {(col != null ? col.name : "-")}: pitched by the plugin about {(col != null ? col.right.ToString("F2") : "-")}");
                        continue;
                    }
                    var fwd = -y.right; var up = Vector3.ProjectOnPlane(root.transform.up, fwd).normalized;
                    var frame = NewGO(y.name + "_jsframe", y.parent, y.position, Quaternion.LookRotation(fwd, up), y.gameObject.layer);
                    var drv = NewGO(y.name + "_jsdrive", frame.transform, y.position, frame.transform.rotation, y.gameObject.layer);
                    y.SetParent(drv.transform, true);
                    var e = NewElem(ck, "joysticks"); S(e, "transform", drv.transform); S(e, "range", YokeJoystickRange); js.Add(e);
                    cockpitAnimLog.Add($"{y.name}: Cockpit.joysticks range {YokeJoystickRange} (column axis {fwd.ToString("F2")})");
                }
                SetSeq(ck, "joysticks", js);
            }
            }
            else
            {   // 1.0: whole yoke as a stick
                var js = NewElem(ck, "joysticks"); S(js, "transform", Find("cockpit_yoke_L")); S(js, "range", 12f);
                SetSeq(ck, "joysticks", new[] { js });
            }

            // target camera + laser designator on the nose (game systems the HUD and tac screen expect)
            var nose = parts["fus_nose"];
            var tcF = NewGO("targetCamForward", nose.transform, root.transform.TransformPoint(new Vector3(0, -0.85f, 5.95f)), Quaternion.identity, 0);
            var tcR = NewGO("targetCamRear", parts["fus_tail"].transform, root.transform.TransformPoint(new Vector3(0, 0.0f, -15.9f)), Quaternion.LookRotation(Vector3.back), 0);
            var tcL = NewGO("landingCamPoint", nose.transform, root.transform.TransformPoint(new Vector3(0, -1.1f, 5.5f)), Quaternion.LookRotation(new Vector3(0, -0.3f, 1f)), 0);
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
            cn.ejectionTransform = ej.transform; cn.attachedPart = part; cn.mass = 20f; cn.ejectionCollider = box;
            S(cn, "ejectionForce", new Vector3(0f, 800f, 0f)); // 800 N for fireTime 0.2 s on 20 kg = ~8 m/s out of the fuselage
            S(cn, "forcePosition", Vector3.zero);
            var h = NewElem(cn, "canopyHinges"); S(h, "transform", drv); S(h, "hingeAngle", hingeAngle);
            SetSeq(cn, "canopyHinges", new[] { h });
            S(cn, "fireTime", 0.2f); S(cn, "openSpeed", 0.6f);
            S(cn, "glassRenderers", glass);
            L($"hatch {hatch.name}: part {part.name}, hinge {hinge.position.ToString("F3")} axis {hinge.right.ToString("F2")} angle {hingeAngle}, eject push along {outward.ToString("F2")}, glass {glass.Length}");
            return cn;
        }

        // Cockpit animation with stock drivers only:
        //  - columns / wheels / pedals: ControlSurface with attachedSurface = fus_cockpit and visibleMesh = the control
        //    (ControlSurfaceJob_Math: rotation = rest * AngleAxis(pitch*pR + roll*rR + yaw*yR, X); visual only - the aero
        //    effect of real surfaces comes from their liftNormal being the visibleMesh, Aircraft.controlSurfaces only runs
        //    split-drag aero when maxSplit > 0);
        //  - manifold pressure and rpm needles: Cockpit.Throttle (rotation, localEulerAngles.x = throttle * range);
        //  - airspeed needle: HighLiftDevice with deployedArea 0 (position = 1 - v / vRet, linear in airspeed; rate 1/s).
        //  Altimeter, VSI, fuel, attitude and compass cards have no stock driver and stay at rest.
        static void CockpitAnimation(global::Cockpit ck, AeroPart cp)
        {
            cockpitAnimLog.Clear();
            var tplCS = TplComp<ControlSurface>("CAS1:elevator_L");
            foreach (var o in JList("controls", "objects"))
            {
                if (RemovePedals && ((string)o["name"]).StartsWith("cockpit_rudder_pedals")) continue;      // removed (DropPedals)
                var t = TryFind((string)o["name"]); if (t == null) { L($"WARN control {(string)o["name"]} not in the model"); continue; }
                var field = (string)o["drive"]["field"]; float val = (float)o["drive"]["value"];
                if (field == "pitchRange") val = ColumnPitchSign * Mathf.Abs(val);
                float servo = o["drive"]["servoSpeed"] != null ? (float)o["drive"]["servoSpeed"] : 90f;
                var cs = t.gameObject.AddComponent<ControlSurface>();
                EditorUtility.CopySerialized(tplCS, cs); Remap(cs);
                S(cs, "pitchRange", 0f); S(cs, "rollRange", 0f); S(cs, "yawRange", 0f); S(cs, "brakeRange", 0f);
                S(cs, field, val);
                S(cs, "attachedSurface", cp); S(cs, "visibleMesh", t.gameObject); S(cs, "flap", false); S(cs, "servoSpeed", servo);
                S(cs, "splitDrag", 0f); S(cs, "maxSplit", 0f); S(cs, "yawSplitFactor", 0f); S(cs, "splitUpper", null); S(cs, "splitLower", null); S(cs, "splitSound", null);
                cockpitAnimLog.Add($"{t.name}: ControlSurface.{field} {val} (axis {t.right.ToString("F2")})");
            }
            var throttles = new List<object>();
            foreach (var g in JList("gauges", "movers").Concat(JList("levers", "movers")))   // needles + quadrant throttle levers
            {
                var t = TryFind((string)g["name"]); if (t == null) continue;
                var drv = g["stock_driver"] as Newtonsoft.Json.Linq.JObject;
                var name = (string)g["name"];
                if (drv != null && ((string)drv["component"] ?? "").Contains("throttles"))
                {
                    float range = (float)drv["range"];
                    var d = DrivenFrame(t);
                    // FD-32 lesson: the lever's grip must move FORWARD at full throttle; flip the sign if it does not
                    var grip = t.GetComponentsInChildren<MeshFilter>(true).FirstOrDefault();
                    if (grip != null)
                    {
                        var top = grip.transform.TransformPoint(grip.sharedMesh.bounds.center + Vector3.up * grip.sharedMesh.bounds.extents.y);
                        var r0 = d.localRotation; d.localEulerAngles = new Vector3(range, 0, 0);
                        var top1 = grip.transform.TransformPoint(grip.sharedMesh.bounds.center + Vector3.up * grip.sharedMesh.bounds.extents.y);
                        d.localRotation = r0;
                        if (top1.z < top.z) { range = -range; cockpitAnimLog.Add($"{name}: range sign flipped so the grip moves forward at full throttle"); }
                        throttleForward[name] = Mathf.Abs(top1.z - top.z);
                    }
                    var th = NewElem(ck, "throttles");
                    S(th, "rotation", true); S(th, "motion", false); S(th, "transform", d);
                    S(th, "range", range);
                    throttles.Add(th);
                    cockpitAnimLog.Add($"{name}: Cockpit.Throttle rotation range {range} (throttle proxy)");
                }
                else if (name == "gauge_airspeed_needle")
                {
                    // angle = mph * deg_per_unit; HighLiftDevice: pos = clamp01(1 - max(v - 0, 0) / vRet): pos 1 at 0 m/s, 0 at vRet
                    float dpu = (float)g["deg_per_unit"], v1 = (float)g["v1"];
                    float vRet = v1 * 0.44704f; // mph -> m/s
                    var d = DrivenFrame(t);
                    var h = cp.gameObject.AddComponent<HighLiftDevice>();
                    S(h, "aeroPart", cp); S(h, "swingWingController", null);
                    S(h, "speedDeployed", 0f); S(h, "speedRetracted", vRet); S(h, "alphaMin", 0f); S(h, "alphaFactor", 0f); S(h, "deployedArea", 0f);
                    var mp = NewElem(h, "movingParts");
                    S(mp, "move", false); S(mp, "rotate", true); S(mp, "transform", d);
                    S(mp, "positionRetracted", Vector3.zero); S(mp, "positionDeployed", Vector3.zero);
                    S(mp, "anglesRetracted", new Vector3(v1 * dpu, 0, 0)); S(mp, "anglesDeployed", Vector3.zero);
                    SetSeq(h, "movingParts", new[] { mp });
                    cockpitAnimLog.Add($"{name}: HighLiftDevice airspeed 0..{vRet:F1} m/s -> 0..{v1 * dpu:F0} deg");
                }
                else cockpitAnimLog.Add($"{name}: no stock driver, at rest");
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
        class CrewSpec { public string role, part, hatch; public Transform eye; public Pilot.ExitDirection exit; }
        static readonly List<Pilot> crew = new List<Pilot>();

        static Pilot MakeCrewMember(CrewSpec c, int index)
        {
            var src = index == 0 ? TplFind("COIN:pilot") : TplFind("COIN:WSO");
            var fig = (GameObject)Object.Instantiate(src.gameObject);
            fig.SetActive(true); fig.name = index == 0 ? "pilot" : "crew_" + c.role;
            foreach (var t in fig.GetComponentsInChildren<Transform>(true)) if (t.name == "EjectionSeat") Object.DestroyImmediate(t.gameObject);
            var part = parts[c.part];
            fig.transform.SetParent(c.eye.parent, false); // the engineer's eye turns with the dorsal turret
            var cam = fig.GetComponentsInChildren<Transform>(true).First(t => t.name == "helmetCamPoint");
            // face along the eye's forward (contract eye frames; identity = +Z)
            fig.transform.rotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(c.eye.forward, Vector3.up).sqrMagnitude > 1e-4f ? Vector3.ProjectOnPlane(c.eye.forward, Vector3.up) : Vector3.forward, Vector3.up);
            fig.transform.position += c.eye.position - cam.position;
            // The tail cone is too shallow for the seated stock figure: in game (1.1.0 test) its legs hung 0.5 m out of the
            // fuselage bottom (figure min y -0.78 local vs hull -0.30 at z -9.3). Scale it about the eye so it fits.
            float crewScale = c.role == "tail" ? TailCrewScale : c.role == "ball" ? BallCrewScale : 1f;
            if (crewScale < 0.999f)
            {
                fig.transform.localScale *= crewScale;
                fig.transform.position += c.eye.position - cam.position;
            }
            if (LegsTucked.Contains(c.role))
                foreach (var th in fig.GetComponentsInChildren<Transform>(true).Where(x => x.name == "thigh_L" || x.name == "thigh_R"))
                {   // round 5: the figure's Animator plays the stock 'seated' clip (PilotController default state), which keys every leg
                    // bone's rotation AND scale each frame (seated.anim m_ScaleCurves pilot_armature/thigh_L ~1.0): in game the 0.02 fold was
                    // undone, the legs came back (user review 2: 01/02/04/09). Generic clips bind by transform path, so the renamed thigh
                    // (and its shin / foot below it) are no longer driven and keep the fold; the upper body still plays seated / dead.
                    th.localScale *= 0.02f; th.name = th.name + "_tucked";
                }
            foreach (var comp in fig.GetComponentsInChildren<Component>(true)) if (comp != null) Remap(comp);
            var pc = fig.GetComponent<Pilot>();
            S(pc, "aircraft", aircraft); S(pc, "unitPart", part); S(pc, "ejectionSeat", false); S(pc, "autoTrimmer", controlsFilter);
            S(pc, "pilotCollider", fig.GetComponent<CapsuleCollider>());
            pc.exitDirection = c.exit;
            L($"crew {index} {c.role}: part {c.part}, eye {c.eye.position.ToString("F3")}, figure eye {cam.position.ToString("F3")}, exit {c.exit}, hatch {c.hatch}");
            if (index == 0) helmetCam = cam;
            return pc;
        }

        static readonly string[] StationOrder = { "Chin", "Top", "Ball", "Tail", "Flexible" };
        static readonly Dictionary<string, int> TurretRounds = new Dictionary<string, int>
        {   // rounds per gun (one Gun cycle fires every muzzle of that Gun and costs 1 round)
            { "chin_mount", 365 }, { "top_mount", 375 }, { "ball_mount", 500 }, { "tail_mount", 500 },
            { "cheek_R_mount", 250 }, { "cheek_L_mount", 250 }, { "waist_R_mount", 300 }, { "waist_L_mount", 300 }, { "radio_mount", 250 },
        };
        static readonly Dictionary<string, WeaponInfo> stationInfos = new Dictionary<string, WeaponInfo>();
        static readonly List<(Turret turret, Gun gun, AeroPart part, Transform mount, string station)> turrets = new List<(Turret, Gun, AeroPart, Transform, string)>();
        static WeaponInfo turretInfo; static WeaponMount ammoTurrets;
        static int exclusionConeCount;
        const string TurretScan = @"C:\Users\User\Nuclear Option B-25\assets\model_b17g\b17g_turret_scan.json";

        static AeroPart OwningPart(Transform t) { for (var x = t; x != null; x = x.parent) { var ap = x.GetComponent<AeroPart>(); if (ap != null) return ap; } return null; }
        static Vector3 barrelTip; static string barrelTipSource = "";
        // 1.8.0 (user: "none of the guns actually line up with where they are meant to be"): the stock barrel asset is NOT readable
        // (m_IsReadable 0), so BarrelTip fell back to the BOUNDS centre (-0.078, 0.065) instead of the bore (0.000, 0.042): every one of
        // the 13 barrels sat 8 cm to its right and 2 cm high of its slot / muzzle line. The vertices are now read from the asset's own
        // serialized vertex data (m_VertexData, float32 position stream) when the mesh API refuses; the bounds stay the last fallback.
        static Vector3[] AssetVertices(Mesh m)
        {
            try { if (m.isReadable) { barrelTipSource = "mesh API"; return m.vertices; } } catch { }
            try
            {
                var path = AssetDatabase.GetAssetPath(m);
                if (string.IsNullOrEmpty(path) || !path.EndsWith(".asset")) return new Vector3[0];
                var y = File.ReadAllText(path);
                int vc = int.Parse(System.Text.RegularExpressions.Regex.Match(y, @"m_VertexCount: (\d+)").Groups[1].Value);
                var chs = System.Text.RegularExpressions.Regex.Matches(System.Text.RegularExpressions.Regex.Match(y, @"m_Channels:(.*?)m_DataSize", System.Text.RegularExpressions.RegexOptions.Singleline).Groups[1].Value,
                    @"stream: (\d+)\s+offset: (\d+)\s+format: (\d+)\s+dimension: (\d+)");
                var hex = System.Text.RegularExpressions.Regex.Match(y, @"_typelessdata: ([0-9a-f]+)").Groups[1].Value;
                if (chs.Count == 0 || hex.Length == 0) return new Vector3[0];
                var pc = chs[0];                                    // channel 0 = position
                if (pc.Groups[1].Value != "0" || pc.Groups[3].Value != "0" || (int.Parse(pc.Groups[4].Value) & 0xf) != 3) return new Vector3[0];
                var data = new byte[hex.Length / 2];
                for (int i = 0; i < data.Length; i++) data[i] = Convert.ToByte(hex.Substring(2 * i, 2), 16);
                int stride0 = data.Length / vc;                    // single-stream layout (stock meshes): bytes per vertex
                var v = new Vector3[vc];
                for (int i = 0; i < vc; i++) { int o = i * stride0 + int.Parse(pc.Groups[2].Value); v[i] = new Vector3(BitConverter.ToSingle(data, o), BitConverter.ToSingle(data, o + 4), BitConverter.ToSingle(data, o + 8)); }
                barrelTipSource = "serialized vertex data";
                return v;
            }
            catch (Exception e) { L("WARN barrel vertices: " + e.Message); return new Vector3[0]; }
        }
        static Vector3 BarrelTip(Mesh m)
        {   // bore axis at the tip: centroid of the vertices within 3 cm of the mesh's max z (falls back to the bounds)
            var v = AssetVertices(m);
            if (v.Length == 0) { barrelTipSource = "bounds (fallback)"; var b = m.bounds; return new Vector3(b.center.x, b.center.y, b.max.z); }
            float zmax = v.Max(p => p.z); var tp = v.Where(p => p.z > zmax - 0.03f).ToList();
            return new Vector3(tp.Average(p => p.x), tp.Average(p => p.y), zmax);
        }

        static void BuildTurrets()
        {
            turrets.Clear(); stationInfos.Clear(); exclusionConeCount = 0;
            var doorTpl = tpl["turret_12.7mm_door"];
            var tplTurret = doorTpl.GetComponentInChildren<Turret>(true);
            var tplGun = doorTpl.GetComponentInChildren<Gun>(true);
            var barrelMesh = Asset<Mesh>("Mesh/50cal_doorGun_barrel_PLACEHOLDER.asset");
            var barrelMat = Asset<Material>("Material/utilityHelo1_attachments_PLACEHOLDER.mat");
            var scan = File.Exists(TurretScan) ? Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(TurretScan)) : null;
            // 1.6.1: the stock door-gun barrel mesh is NOT centred on its origin (in game mbounds x -0.08..0.52, y 0.06..0.37, z 0.43..1.54):
            // its bore axis is offset ~0.22 m right and up, so on our slot the guns sat beside the turret and the muzzles (slot +1.20 m)
            // were 0.3 m off the bore and 0.34 m short of the tip. The barrel goes on a child shifted so the bore lies on the slot axis, and
            // the muzzle moves to the bore tip (Gun.cs 634: rounds leave every muzzle along muzzle.forward).
            // 1.8.13 (offline L): our own AN/M2 (ANM2Gun.cs, blender/anm2/anm2_model.py) instead of the stock door-gun barrel: bore through the
            // contract muzzle, tip on it, gun_L / gun_R per side, spade grips on the hand-held positions. ANM2Guns false = the stock barrel.
            var anm2 = ANM2Guns ? ANM2Gun.Load(Folder, "B17G") : null;
            if (anm2 != null) L($"AN/M2: tip z {anm2.TipZ}, meshes {anm2.FL.name} / {anm2.FR.name} / {anm2.TL.name} / {anm2.TR.name} / {anm2.Grips.name}");
            barrelTip = BarrelTip(barrelMesh);
            L($"stock barrel bore at the tip: ({barrelTip.x:F3}, {barrelTip.y:F3}, {barrelTip.z:F3}) from {barrelTipSource}; bounds centre ({barrelMesh.bounds.center.x:F3}, {barrelMesh.bounds.center.y:F3})");
            foreach (var st in StationOrder)
            {
                var info = Object.Instantiate(Asset<WeaponInfo>("MonoBehaviour/Gun12.7mm_PLACEHOLDER.asset")); info.name = "B17G_turret_" + st.ToLowerInvariant() + "_info";
                info.weaponName = $"12.7mm {st} Guns"; info.shortName = $"{st.ToUpperInvariant()} 12.7MM"; info.boresight = false;
                if (TurretAntiMissile) info.effectiveness.antiMissile = 0.05f;
                // 1.6.1 AIR TARGETS ONLY (in game 1.6.0: 830+ hits on helipads / revetments, the tail turret ignored a CI-22 astern):
                // Turret.AssessTargetPriority (Turret.cs 484-486) skips a candidate whose opportunity is 0; WeaponStation.CalcOpportunityThreat
                // (WeaponStation.cs 435) = target type . WeaponInfo.effectiveness x target type . aircraft roleIdentity (RoleIdentity.cs 19-22).
                // Stock Gun12.7mm (0.12 surface / 0.12 air) x B17G role (0.9 / 0.1) made ground targets 9x more attractive than fighters.
                info.effectiveness.antiSurface = 0f; info.effectiveness.antiRadar = 0f;
                AssetDatabase.CreateAsset(info, Folder + "/" + info.name + ".asset");
                stationInfos[st] = info;
            }
            foreach (var tj in JList("turrets"))
            {
                var mount = TryFind((string)tj["mount"]["name"]); var az = TryFind((string)tj["az"]["name"]); var el = TryFind((string)tj["el"]["name"]);
                if (mount == null || az == null || el == null) { L($"WARN turret {(string)tj["mount"]["name"]}: objects missing, skipped"); continue; }
                var station = (string)tj["station"];
                var part = OwningPart(mount);
                if (Quaternion.Angle(az.localRotation, Quaternion.identity) > 0.01f || Quaternion.Angle(el.localRotation, Quaternion.identity) > 0.01f)
                    L($"WARN turret {mount.name}: az/el do not rest at identity");
                var muzzles = new List<Transform>();
                bool twin = ((Newtonsoft.Json.Linq.JArray)tj["guns"]).Count > 1;
                foreach (var g in (Newtonsoft.Json.Linq.JArray)tj["guns"])
                {
                    var gb = TryFind((string)g["gun"]["name"]); var mz = TryFind((string)g["muzzle"]["name"]);
                    if (gb == null || mz == null) continue;
                    if (anm2 != null)
                    {   // trunnion 0.10 m ahead of the elevation pivot on the contract bore line (receiver / grips inside, as the real mounts), muzzle moved to the tip
                        mz.localRotation = Quaternion.identity;
                        var (right, grips) = ANM2Gun.Variant(mount.name.Replace("_mount", ""), gb, el, twin);
                        var gt = ANM2Gun.Place(anm2, gb, mz, el, right, grips);
                        L($"AN/M2 {gb.name}: {(right ? "gun_R" : "gun_L")}{(grips ? " + grips" : "")}, gun at slot z {gt.localPosition.z:F3}, muzzle z {mz.localPosition.z:F3}");
                        muzzles.Add(mz);
                        continue;
                    }
                    var old = gb.GetComponent<MeshFilter>(); if (old != null) { var orr = gb.GetComponent<MeshRenderer>(); if (orr != null) Object.DestroyImmediate(orr); Object.DestroyImmediate(old); }
                    var bgo = NewGO(gb.name + "_barrel", gb, gb.TransformPoint(new Vector3(-barrelTip.x, -barrelTip.y, 0f)), gb.rotation);
                    bgo.AddComponent<MeshFilter>().sharedMesh = barrelMesh; bgo.AddComponent<MeshRenderer>().sharedMaterials = new[] { barrelMat };   // the stock M2 barrel, bore on the slot axis
                    mz.localPosition = new Vector3(0f, 0f, barrelTip.z); mz.localRotation = Quaternion.identity;
                    muzzles.Add(mz);
                }
                var tl = tj["Turret"];
                int rounds = TurretRounds.TryGetValue(mount.name, out var rr) ? rr : 300;
                foreach (var a in tplGun.GetComponents<AudioSource>()) CloneComp(a, el.gameObject).loop = false;
                var gun = CloneComp(tplGun, el.gameObject);
                gun.attachedUnit = aircraft; gun.info = stationInfos[station];
                S(gun, "muzzles", muzzles.ToArray());
                S(gun, "magazineCapacity", rounds); S(gun, "magazines", 0); S(gun, "startLoaded", true);
                S(gun, "recoilTransform", null); S(gun, "spinTransform", null); S(gun, "ejectionTransform", null); S(gun, "ejectionPrefab", null);
                var ps = new List<ParticleSystem>(); foreach (var mz in muzzles) ps.AddRange(CopyMuzzleParticles(tplGun, mz));
                S(gun, "muzzleParticles", ps.ToArray());
                var tr = CloneComp(tplTurret, az.gameObject);
                S(tr, "attachedUnit", aircraft);
                var fMode = Fld(typeof(Turret), "targetAcquisitionMode"); fMode.SetValue(tr, Enum.ToObject(fMode.FieldType, 0));
                S(tr, "fireControl", null); S(tr, "firesWithoutAiming", false);
                SetSeq(tr, "targetDetectors", new TargetDetector[0]);
                var ws = (WeaponStation)System.Runtime.Serialization.FormatterServices.GetUninitializedObject(typeof(WeaponStation));
                ws.Weapons = new List<Weapon> { gun }; ws.Turrets = new List<Turret> { tr };
                SetSeq(tr, "weaponStations", new[] { ws });
                S(tr, "aimSafetyWeapon", gun);
                float trav = (float)tl["traverseRange"], emin = (float)tl["minElevation"], emax = (float)tl["maxElevation"];
                S(tr, "traverseRate", (float)tl["traverseRate"]); S(tr, "traverseRange", trav >= 180f ? 999999f : trav);
                S(tr, "elevationRate", (float)tl["elevationRate"]); S(tr, "minElevation", emin); S(tr, "maxElevation", emax);
                S(tr, "elevationTransform", el);
                // inclusion cone (B-25H) + exclusion cones from the offline scan (blocked 5-deg grid directions, 6 deg each)
                Vector3 fwd = mount.forward, up = mount.up; float cone;
                if (trav >= 180f) { fwd = emax <= 0f ? -up : up; cone = 90f + Mathf.Max(Mathf.Abs(emin), Mathf.Abs(emax)) * 0f + 1f + (emax <= 0f ? emax : -emin); }
                else cone = Mathf.Rad2Deg * Mathf.Acos(Mathf.Cos(trav * Mathf.Deg2Rad) * Mathf.Cos(Mathf.Max(Mathf.Abs(emin), Mathf.Abs(emax)) * Mathf.Deg2Rad)) + 1f;
                var cones = new List<object>();
                var cg = NewGO(mount.name + "_cone", mount.parent, mount.position, Quaternion.LookRotation(fwd, Mathf.Abs(Vector3.Dot(fwd, Vector3.up)) > 0.99f ? Vector3.forward : Vector3.up));
                var fc = New(typeof(FiringCone)); S(fc, "transform", cg.transform); S(fc, "coneAngle", cone); S(fc, "exclusion", false); cones.Add(fc);
                var tname = mount.name.Replace("_mount", "");
                if (TurretExclusionCones && scan != null && scan[tname] != null)
                    foreach (var c in (Newtonsoft.Json.Linq.JArray)scan[tname]["exclusion_cones"])
                    {
                        var d = new Vector3((float)c[0][0], (float)c[0][2], (float)c[0][1]);      // Blender world dir -> Unity
                        var eg = NewGO($"{mount.name}_excl{cones.Count}", mount.parent, mount.position, Quaternion.LookRotation(d, Mathf.Abs(d.y) > 0.99f ? Vector3.forward : Vector3.up));
                        var ec = New(typeof(FiringCone)); S(ec, "transform", eg.transform); S(ec, "coneAngle", (float)c[1]); S(ec, "exclusion", true); cones.Add(ec);
                        exclusionConeCount++;
                    }
                SetSeq(tr, "firingCones", cones);
                S(tr, "criticalParts", new UnitPart[] { part });
                S(tr, "manual", false); S(tr, "stowed", false);
                turrets.Add((tr, gun, part, mount, station));
                L($"turret {tname} ({station}): part {part.name}, traverse {trav}, el {emin}..{emax}, {muzzles.Count} gun(s) x {rounds} rds, inclusion cone {cone:F0} deg, {cones.Count - 1} exclusion cones");
            }
        }

        // ------------------------------------------------------------------ root systems
        static void RootSystems(List<LandingGear> gears)
        {
            var coin = tpl["COIN"];
            var detector = CloneComp(coin.GetComponent<TargetDetector>(), root);
            S(detector, "attachedUnit", aircraft); S(detector, "scanner", parts["fus_cockpit"].transform);
            aircraft.EOTS = detector;
            var cap = CloneComp(TplAudio("COIN:COIN", "capacitor"), root);
            var power = CloneComp(coin.GetComponent<PowerSupply>(), root);
            S(power, "powerSources", EngineNums.Select(n => parts["engine_" + n].gameObject).ToArray());
            S(power, "source", cap); S(power, "aircraft", aircraft);
            S(aircraft, "powerSupply", power);
            CloneComp(coin.GetComponent<NuclearOption.NetworkTransforms.AircraftNetworkTransform>(), root);

            // round 5 (wreck fire, coordinator 2026-11-06; study: nuclearoption-ref/study/b17g/ai_round/d_ab4_fx.txt, d_stock_fx.txt):
            // stock wrecks burn through FuelTank components. A tank leaks / ignites from damage, crash g or detachment, spawns fire_med +
            // a fireball at its part's ORIGIN, burns nearby colliders (FuelTankFire) and punctures its connectedTanks when its part breaks
            // off (FuelTank.cs FuelTank_OnDetach). Unit.RpcFuelTankStatus finds the tank with part.TryGetComponent<FuelTank>(), so one tank
            // per part, on the part's own GameObject. The model puts those parts' origins on their tank (wing cells between the spars,
            // nacelle oil tanks, waist section; the centre section's origin is the datum in the bomb bay = the bay ferry tank).
            // Settings: the AB-4 (FastBomber1) heavy-bomber tanks (ruptureG 50-300, ignitionG 40-400, pierce 5-100, blast 4-100,
            // fireIntensity 1.5) instead of the CI-22 light-aircraft tank (rupture 100-500, ignition 200-500, fireIntensity 1).
            var tplWingTank = TplComp<FuelTank>("FastBomber1:wingroot_L");      // fuelLeak, fire_med, fireball_medium
            var tplBodyTank = TplComp<FuelTank>("FastBomber1:fuselage_R");      // fuelLeak, fire_med, fireball_large
            var tankKg = new List<(string part, float kg, FuelTank tpl)>();
            foreach (var sd in new[] { "L", "R" })
            {
                tankKg.Add(("wing_inner_" + sd, 1000f, tplWingTank));   // inboard engine tanks
                tankKg.Add(("wing_mid_" + sd, 650f, tplWingTank));      // outboard engine tank + feeder
                tankKg.Add(("wing_outer_" + sd, 400f, tplWingTank));    // Tokyo tanks (9 cells)
            }
            foreach (var n in EngineNums) tankKg.Add(("nacelle_" + n, 50f, tplWingTank));   // oil tank + feed lines behind the firewall
            tankKg.Add(("B17G", 200f, tplBodyTank));                     // bomb-bay ferry tank / centre-section lines (fus_center)
            tankKg.Add(("fus_waist", 100f, tplBodyTank));                // waist: transfer lines aft (fus_radio keeps the datum origin, see design 17)
            if (Mathf.Abs(tankKg.Sum(t => t.kg) - FuelKg) > 0.5f) throw new Exception($"fuel split {tankKg.Sum(t => t.kg)} != {FuelKg}");
            var tanks = new Dictionary<string, FuelTank>();
            foreach (var (p, kg, tp) in tankKg)
            {
                var ft = CloneComp(tp, parts[p].gameObject);
                S(ft, "fuelCapacity", kg); S(ft, "fuelMass", kg); S(ft, "part", parts[p]);
                tanks[p] = ft;
            }
            foreach (var t in tanks.Values) SetSeq(t, "connectedTanks", new object[0]);
            void Link(string a, string b) { var la = ((FuelTank[])G(tanks[a], "connectedTanks")).ToList(); if (!la.Contains(tanks[b])) la.Add(tanks[b]); S(tanks[a], "connectedTanks", la.ToArray()); }
            foreach (var sd in new[] { "L", "R" })
            {   // inner <-> mid <-> outer, inner <-> centre section; a detaching wing part punctures its neighbours
                Link("wing_inner_" + sd, "wing_mid_" + sd); Link("wing_mid_" + sd, "wing_inner_" + sd);
                Link("wing_mid_" + sd, "wing_outer_" + sd); Link("wing_outer_" + sd, "wing_mid_" + sd);
                Link("wing_inner_" + sd, "B17G"); Link("B17G", "wing_inner_" + sd);
            }
            L("fuel tanks: " + string.Join(", ", tanks.Select(kv => $"{kv.Key} {G(kv.Value, "fuelCapacity")} kg -> [{string.Join(" ", ((FuelTank[])G(kv.Value, "connectedTanks")).Select(c => c.name))}]")));
            // the small 'fire_tiny' damage effect: off the prop hubs (CI-22 propHub template: 3 small fires on the wreck, 11_wreck.jpg),
            // onto the engine parts (origin at the cowl) below 30 hit points
            {
                var dfl = Fld(typeof(UnitPart), "damageEffects");
                var hubFx = ((IList)dfl.GetValue(TplComp<AeroPart>("COIN:propHub"))).Cast<DamageEffect>().FirstOrDefault(d => d.prefab != null);
                foreach (var n in EngineNums)
                {
                    dfl.SetValue(parts["prop_" + n], new List<DamageEffect>());
                    var lst = new List<DamageEffect>();
                    if (hubFx != null) lst.Add(new DamageEffect { prefab = hubFx.prefab, threshold = 30f });
                    dfl.SetValue(parts["engine_" + n], lst);
                }
                L($"engine fire effect: {(hubFx != null ? hubFx.prefab.name : "NONE")} at 30 hp on engine_1..4, none on the props");
            }

            // nav lights: our own small lenses; lit materials are the game's navlight materials
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
            SetSeq(nl, "navLights", entries);
            S(nl, "aircraft", aircraft);

            // countermeasures (see flag): CI-22 flare ejector, ejection points under the nacelles
            if (KeepFlareEjector)
            {
                var fe = CloneComp(coin.GetComponent<FlareEjector>(), root);
                var pts = new List<object>();
                foreach (var s in new[] { "2", "3" })
                {
                    var n = parts["nacelle_" + s];
                    var g = NewGO("flareEjector_" + s, n.transform, n.transform.position + new Vector3(0, -0.6f, -2.5f), Quaternion.LookRotation(Vector3.down));
                    var a = CloneComp(TplAudio("COIN:flareEjector_L", "flare"), g);
                    var ep = NewElem(fe, "ejectionPoints");
                    S(ep, "part", n); S(ep, "transform", g.transform); S(ep, "sound", a);
                    pts.Add(ep);
                }
                SetSeq(fe, "ejectionPoints", pts);
                foreach (var f in new[] { "doors", "flareDoors" }) { try { SetSeq(fe, f, new object[0]); } catch { } }
                S(fe, "aircraft", aircraft);
            }

            // contact sparks + global particle space
            var sparks = CopyParticle(TplFind("COIN:contactSparks").GetComponent<ParticleSystem>(), root.transform, root.transform.position, "contactSparks");
            S(aircraft, "sparksEmitter", sparks);
            var sgp = root.AddComponent<SetGlobalParticles>();
            S(sgp, "systems", ourParticles.ToList());
            // doppler sounds: engine/prop sources (as CI-22: turbine + prop)
            var doppler = new List<AudioSource>();
            foreach (var s in EngineNums) { doppler.Add(parts["engine_" + s].GetComponent<AudioSource>()); doppler.Add(parts["prop_" + s].GetComponent<AudioSource>()); }
            S(aircraft, "dopplerSounds", doppler);
            aircraft.maxRadius = 16.5f;
            aircraft.obstacleTop = 5.1f; // fin tips above the root
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
            F("gLimitPositive", 3.0f); F("cornerSpeed", 95f); F("postStallManeuverSpeed", 0f); F("maxRollSpeed", 35f);
            F("takeoffSpeed", FbwTakeoffSpeed); F("rollTrimLimit", FbwRollTrimLimit); F("rollTrimRate", FbwRollTrimRate); F("pFactorFast", FbwPitchP); F("dFactorFast", FbwPitchD); F("pidTransitionSpeed", 90f); F("alphaLimiter", AlphaLimiter);
            so.FindProperty("flyByWire.noseGear").objectReferenceValue = noseGear;     // taildragger: a main gear stands in for weight-on-wheels (Nimrod)
            so.ApplyModifiedPropertiesWithoutUndo();
            var ap = parts["fus_cockpit"].GetComponent<AutopilotPlane>();
            var so2 = new SerializedObject(ap);
            var rs = so2.FindProperty("forwardFlightController.referenceAirspeed"); if (rs != null) rs.floatValue = 85f;
            if (BomberAITuning) { var pi = so2.FindProperty("preventInvertedFlight"); if (pi != null) pi.boolValue = true; }
            {   // 1.7.8 AI roll PID (b17g_head.cs AiRollPID: the weave)
                var sp = so2.FindProperty("forwardFlightController.rollFlightPID.PID"); if (sp == null) throw new Exception("no rollFlightPID");
                sp.vector3Value = AiRollPID;
            }
            so2.ApplyModifiedPropertiesWithoutUndo();
            L($"FBW: g 3.0, corner 95, roll 35, alpha limiter {AlphaLimiter} + incidence {WingIncidence} = CLmax angle {WingCLmaxDeg}; roll trim {FbwRollTrimLimit}/{FbwRollTrimRate}; AI roll PID {AiRollPID}");
        }

        // =================================================================== damage diagram + map icon (generated from our model)
        // Stock pattern (CAS1_statusDisplay.prefab, StatusDisplay.cs, PartStatusDisplay.cs): a 300x300 UI prefab parented to
        // FlightHud.statusAnchor; root Image = line-art background (StatusDisplay.aircraftBackground); one Image per part whose
        // GameObject NAME equals the UnitPart's GameObject name (PartStatusDisplay.FindPart); the game sets each part image's
        // green channel/alpha from part hit points (yellow -> red), and a detached part turns (0.7, 0, 0.25). Failure indicators
        // are GameObjects named after IReportDamage failure messages ("LEFT ENGINE FAILURE"...), shown on report.
        // Map icon (UnitDefinition.mapIcon, UnitMapIcon.cs:53): white silhouette on transparent, 256x256, nose up, tinted by IFF.
        const string RepoUI = @"C:\Users\User\Nuclear Option B-25\assets\ui";
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
            var art = Directory.Exists(RepoUI) && !File.Exists(Path.Combine(RepoUI, "b17g_status_layout.json")) ? Directory.GetFiles(RepoUI, "*.png").FirstOrDefault(f => { var n = Path.GetFileName(f).ToLowerInvariant(); return n.Contains("diagram") || n.Contains("status") || n.Contains("damage"); }) : null;
            if (art != null)
            {
                var fitted = FitArt(art, 512, u, BIG);
                if (fitted != null) { bgPx = fitted; L($"status background: texture worker art {Path.GetFileName(art)} (bbox-fitted to the model frame)"); }
            }
            else L("status background: generated line art from the model (no assets/ui diagram art)");
            statusBackground = SaveSprite(bgPx, 512, "b17g_status", false);

            // one filled sprite per part (256, 2x supersampled)
            const int PB = 512;
            for (short k = 0; k < plist.Count; k++)
            {
                var r = new Raster(PB);
                foreach (var (a, b, c) in PartTriangles(plist[k])) r.Tri(a, b, c, k);
                var px = Downsample(i => r.id[i] >= 0, PB, 2);
                statusParts[plist[k].name] = SaveSprite(px, 256, "b17g_status_" + plist[k].name, true);
                // centre of the part's own silhouette, for failure indicators
                double sx = 0, sy = 0; int cnt = 0;
                for (int i = 0; i < r.id.Length; i++) if (r.id[i] >= 0) { sx += i % PB; sy += i / PB; cnt++; }
                diagramPos[plist[k].name] = cnt > 0 ? new Vector2((float)(sx / cnt / PB - 0.5), (float)(sy / cnt / PB - 0.5)) : Vector2.zero;
            }

            // map icon: filled silhouette, 256 (texture worker's icon when present)
            var icon = Path.Combine(RepoUI, "b17g_map_icon.png");
            if (File.Exists(icon)) { mapIconSprite = ImportRepoSprite(icon, "b17g_mapicon"); L("map icon: texture worker art b17g_map_icon.png"); }
            else { mapIconSprite = SaveSprite(Downsample(i => u.id[i] >= 0, BIG, 4), 256, "b17g_mapicon", false); L("map icon: generated silhouette from the model"); }
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
        static readonly string[] FailureIndicators = { "ENGINE 1 FIRE", "ENGINE 2 FIRE", "ENGINE 3 FIRE", "ENGINE 4 FIRE" }; // TurbineEngine.failureMessage (from CAS1)
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
            var inst = new GameObject("B17G_statusDisplay", typeof(RectTransform)) { layer = 5 };
            var rt = (RectTransform)inst.transform;
            rt.anchorMin = rt.anchorMax = new Vector2(1f, 0f); rt.pivot = new Vector2(1f, -0.05f); rt.sizeDelta = new Vector2(300f, 300f); rt.anchoredPosition = new Vector2(0f, -30.1f);
            var list = new List<PartStatusDisplay>();
            var failures = new List<GameObject>();
            UnityEngine.UI.Image rootImg;
            StatusDisplay sd;
            Vector2 V2(Newtonsoft.Json.Linq.JToken t) => new Vector2((float)t[0], (float)t[1]);
            var layoutPath = Path.Combine(RepoUI, "b17g_status_layout.json");
            var covered = new HashSet<string>();
            if (File.Exists(layoutPath))
            {
                // texture worker's art + layout (assets/ui/b17g_status_layout.json): stock-style per-part sprites, mirrored L/R
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
            foreach (var kv in statusParts.Where(k => !covered.Contains(k.Key)).OrderBy(k => k.Key == "B17G" ? 0 : 1))
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
                var part = "engine_" + fname.Substring(7, 1);
                grt.anchoredPosition = diagramPos.TryGetValue(part, out var dp) ? dp * rt.sizeDelta.x : Vector2.zero;
                Img(g, null, Color.red).preserveAspect = false;
                failures.Add(g);
            }
            SetSeq(sd, "failureIndicators", failures);
            var fnames = string.Join(", ", failures.Select(f => f.name));
            var prefab = PrefabUtility.SaveAsPrefabAsset(inst, Folder + "/B17G_statusDisplay.prefab");
            Object.DestroyImmediate(inst);
            L($"status display prefab: {list.Count} part images, failure indicators {fnames}");
            return prefab;
        }

        // =================================================================== assets
        static GameObject SaveEverything()
        {
            var bank = Folder + "/Generated/B17G_meshes.asset";
            AssetDatabase.CreateAsset(generatedMeshes[0], bank);
            foreach (var m in generatedMeshes.Skip(1)) AssetDatabase.AddObjectToAsset(m, bank);

            // airfoils (AeroJob_Math sign convention: physical curves mirrored, B-25H): 0 wing (Boeing 103-like, CLmax 1.45 at 16 deg,
            // gentle post-stall), 1 tail (symmetric), 2 aileron (Nimrod 1.4.2 lesson: a deflected aileron is a plain flap)
            var coinParams = Asset<AircraftParameters>("MonoBehaviour/COINParameters_PLACEHOLDER.asset");
            var drag = coinParams.airfoils[0].dragCoef;
            var wing = new Airfoil { name = "B17G_wing", liftCoef = Mirror(WingCL), dragCoef = B17GWingDrag() };
            var tail = new Airfoil { name = "B17G_tail", liftCoef = Mirror(new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.9f), (-0.45f, -0.8f), (-0.3f, -1.1f), (0f, 0f), (0.3f, 1.1f), (0.45f, 0.8f), (0.785f, 0.9f), (1.571f, 0f), (3.142f, 0f) }), dragCoef = new AnimationCurve(drag.keys) };
            var ail = new Airfoil { name = "B17G_aileron", liftCoef = Mirror(OwnAileronAirfoil ? AileronCL : WingCL), dragCoef = WingDrag() };
            var flp = new Airfoil { name = "B17G_flap", liftCoef = Mirror(FlapCL), dragCoef = FlapDrag() };

            var facBDF = coinParams.liveries[0].faction; var facPALA = coinParams.liveries[2].faction;
            var livs = new List<AircraftParameters.Livery>();
            var livGuid = new Dictionary<string, string>();
            foreach (var (file, label, fac, _) in Liveries)
            {
                var ld = ScriptableObject.CreateInstance<LiveryData>();
                var (gloss, cols) = LiveryJson(file);
                ld.Texture = tex[file]; ld.Glossiness = gloss; ld.Colors = cols;
                var p = $"{Folder}/Liveries/{file}.asset";
                AssetDatabase.CreateAsset(ld, p);
                livGuid[file] = AssetDatabase.AssetPathToGUID(p);
            }
            // user decision: the two USAAF schemes for both factions, two own schemes per faction (own faction's first)
            foreach (var side in new[] { "BDF", "PALA" })
                foreach (var (file, label, fac, both) in Liveries.Where(x => !x.both && x.faction == side).Concat(Liveries.Where(x => x.both)))
                    livs.Add(new AircraftParameters.Livery { name = label, faction = side == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(livGuid[file]) });

            var prm = Object.Instantiate(Asset<AircraftParameters>("MonoBehaviour/CAS1Parameters_PLACEHOLDER.asset"));
            prm.HUDExtras = StockHUDExtras ? Asset<GameObject>("GameObject/COIN_HUDExtras_PLACEHOLDER.prefab") : null;
            prm.name = "B17G_Parameters";
            if (OwnStatusDisplay || OwnMapIcon) BuildDiagramSprites();
            if (OwnStatusDisplay) prm.StatusDisplay = BuildStatusDisplayPrefab();
            prm.aircraftName = DisplayName; prm.rankRequired = 3;
            prm.airfoils = new[] { wing, tail, ail, flp };
            prm.liveries = livs;
            // loadouts: one entry per hardpoint set (Bomb Bay, then the gun stations in StationOrder)
            var ammo = stationSets.Select(x => x.ammo).ToList();
            NuclearOption.SavedMission.Loadout LO(WeaponMount bay) => new NuclearOption.SavedMission.Loadout { weapons = new[] { bay }.Concat(ammo).ToList() };
            prm.loadouts = new List<NuclearOption.SavedMission.Loadout>
            {
                new NuclearOption.SavedMission.Loadout { weapons = Enumerable.Repeat<WeaponMount>(null, 1 + ammo.Count).ToList() },
                LO(Mount("bomb_250_internalx8")),
            };
            prm.StandardLoadouts = new[]
            {
                new StandardLoadout { Name = "General purpose (8 x PAB-250)", loadout = LO(Mount("bomb_250_internalx8")), FuelRatio = 0.6f },
                new StandardLoadout { Name = "Heavy (4 x GPO-500)", loadout = LO(Mount("bomb_500_internalx4_stack")), FuelRatio = 0.5f },
                new StandardLoadout { Name = "Area (2 x CBO-400)", loadout = LO(Mount("bomb_cluster1_dual_internal")), FuelRatio = 0.6f },
            };
            prm.DefaultFuelLevel = 0.6f;
            prm.PIDReferenceAirspeed = 85f; prm.maxSpeed = 100f; prm.takeoffSpeed = 47f; prm.takeoffDistance = 1150f;
            prm.aircraftGLimit = AiLookaheadGLimit;   // 1.7.8: 3 -> 0.8 (terrain-follow look-ahead only; b17g_head.cs). 1.7.10: the line above was swallowed by this comment in 1.7.8/1.7.9 (template 180/215/80/500 in game)
            // 1.7.0 AI landing (AIPilotLandingState): pattern speed = cornerSpeed + 0.02 x distance, glideslope aimpoint 3 x turningRadius out,
            // final speed = sqrt(m / maxWeight) x landingSpeed + 0.015 x (distance - 500). 1.6.9 flew the pattern at 100-111 m/s, 7.5 km
            // out over the Maris hills, could not slow down and went around / flew into the ridge. Stock heavy SFB-81: turningRadius 1500.
            prm.turningRadius = AiTurningRadius; prm.cornerSpeed = AiCornerSpeed; prm.approachSpeed = 58f; prm.landingSpeed = AiLandingSpeed; prm.shortLandingSpeed = AiLandingSpeed;
            // cruiseThrottle is also the AI landing-state throttle cap (0.55 in 1.6.8 left an AI B-17 mushing into a hill); stock heavies 1.0.
            // 1.6.9 bug: a // comment swallowed minimumRadarAlt / groundTurningRadius (CAS1 template values were used).
            prm.cruiseThrottle = AiCruiseThrottle; prm.minimumRadarAlt = AiMinRadarAlt; prm.groundTurningRadius = 30f;
            AssetDatabase.CreateAsset(prm, Folder + "/B17G_Parameters.asset");

            float total = parts.Values.Sum(p => p.mass);
            var def = Object.Instantiate(Asset<AircraftDefinition>("MonoBehaviour/CI-22_PLACEHOLDER.asset"));
            def.name = "B17G";
            def.jsonKey = JsonKey; def.WorkshopTag = DisplayName; def.unitName = DisplayName; def.code = "B-17G"; def.bogeyName = "";
            def.description = "Boeing B-17G Flying Fortress, 1944. A four-engine heavy bomber built to fight its way to the target: thirteen " +
                ".50 calibre guns in chin, top, ball and tail turrets and flexible cheek, waist and radio positions, a bomb bay for up to 4,400 lb, " +
                "and four 1,200 hp Wright R-1820 Cyclones. Slow and steady, it takes punishment no other bomber can; crew of ten.";
            def.length = 22.66f; def.width = 31.62f; def.height = 5.82f; def.mass = total;
            def.value = 45f; def.radarSize = 3.0f; def.visibleRange = 7000f; def.manpower = 10;
            def.roleIdentity.antiSurface = 0.9f; def.roleIdentity.antiAir = 0.1f;
            def.spawnOffset = new Vector3(0f, spawnHeight, 0f);
            def.restRotation = SpawnThreePoint ? new Vector3(-ThreePointDeg, 0f, 0f) : Vector3.zero;
            def.aircraftParameters = prm;
            if (OwnMapIcon) { def.mapIcon = mapIconSprite; def.mapIconSize = 1.3f; def.mapOrient = true; }
            def.aircraftInfo = new AircraftInfo { emptyWeight = 16390f, maxSpeed = 460f, stallSpeed = 150f, maneuverability = 3f, maxWeight = 29700f };
            def.unitPrefab = null;
            AssetDatabase.CreateAsset(def, Folder + "/B17G.asset");
            foreach (var u in root.GetComponentsInChildren<Unit>(true)) u.definition = def;
            var rb = root.GetComponent<Rigidbody>(); rb.mass = total;
            if (FireClear1814On && DefensiveTurrets) FireClear1814.Apply(root, L, FireClearJson);   // 1.8.14: after colliders / meshes / guns are final
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, Folder + "/B17G.prefab");
            def.unitPrefab = prefab;
            EditorUtility.SetDirty(def);
            var op = ScriptableObject.CreateInstance<Blueprinter.OpAddAircraftToHangars>();
            op.aircraftJsonKey = JsonKey;
            op.hangars.Add(new Blueprinter.OpAddAircraftToHangars.HangarTarget { hangarUnitJsonKey = "hangar_med", hangarNames = { "hangar_med" } });
            AssetDatabase.CreateAsset(op, Folder + "/OpAddAircraftToHangars.asset");
            AssetDatabase.SaveAssets();
            L($"saved prefab, definition (mass {total} kg, spawn y {spawnHeight:F3}, rest {def.restRotation}), parameters, {livs.Count} liveries, {generatedMeshes.Count} meshes");
            return prefab;
        }

        static (float t, float v)[] WingCL => new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.95f), (-0.36f, -0.75f), (-0.24f, -0.95f), (0f, 0.15f), (0.15f, 0.90f),
            (0.2443f, 1.40f), (0.2793f, 1.45f), (0.33f, 1.38f), (0.42f, 1.25f), (0.6f, 1.10f), (0.785f, 0.95f), (1.571f, 0f), (3.142f, 0f) };
        // 1.6.3 flap (airfoil 3): the wing curve up to 14 deg (retracted flaps fly as wing), then a deflected-flap section peaking ~2.0 at 34 deg
        static (float t, float v)[] FlapCL => new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.95f), (-0.36f, -0.75f), (-0.24f, -0.95f), (0f, 0.15f), (0.15f, 0.90f),
            (0.2443f, 1.40f), (0.33f, 1.62f), (0.45f, 1.85f), (0.59f, 2.0f), (0.75f, 1.7f), (1.0f, 1.15f), (1.571f, 0f), (3.142f, 0f) };
        // 1.6.7 wing drag (airfoil 0): the B-25H curve below 1.5 deg (top speed), more induced drag at climb / take-off angles (CD 0.036 at
        // 4.3 deg, 0.072 at 7.2 deg; B-25H 0.024 / 0.040) so a power that gives ~450 km/h does not climb at 10+ m/s (spec ~4.6)
        static AnimationCurve B17GWingDrag()
        {
            var pts = new[] { (0f, 0.008f), (0.025f, 0.0114f), (0.05f, 0.022f), (0.075f, 0.036f), (0.1f, 0.052f), (0.126f, 0.072f), (0.15f, 0.092f), (0.2f, 0.14f), (0.28f, 0.20f), (0.35f, 0.29f), (0.5f, 0.5f), (1.51f, 1.7f), (3.14159f, 0f) };
            var keys = new List<Keyframe>();
            foreach (var (t, v) in pts.Reverse()) if (t > 0f) keys.Add(new Keyframe(-t, v));
            foreach (var (t, v) in pts) keys.Add(new Keyframe(t, v));
            var c = new AnimationCurve(keys.ToArray());
            for (int i = 0; i < c.length; i++) c.SmoothTangents(i, 0f);
            return c;
        }
        static AnimationCurve FlapDrag()
        {
            var pts = new[] { (0f, 0.008f), (0.06f, 0.021f), (0.1f, 0.036f), (0.2f, 0.075f), (0.35f, 0.12f), (0.5f, 0.17f), (0.65f, 0.25f), (0.9f, 0.6f), (1.51f, 1.7f), (3.14159f, 0f) };
            var keys = new List<Keyframe>();
            foreach (var (t, v) in pts.Reverse()) if (t > 0f) keys.Add(new Keyframe(-t, v));
            foreach (var (t, v) in pts) keys.Add(new Keyframe(t, v));
            var c = new AnimationCurve(keys.ToArray());
            for (int i = 0; i < c.length; i++) c.SmoothTangents(i, 0f);
            return c;
        }
        static (float t, float v)[] AileronCL => new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -1.10f), (-0.62f, -1.30f), (-0.52f, -1.35f), (-0.40f, -1.25f), (-0.24f, -0.95f), (0f, 0.15f), (0.15f, 0.90f),
            (0.2793f, 1.45f), (0.40f, 1.70f), (0.52f, 1.85f), (0.62f, 1.80f), (0.785f, 1.40f), (1.571f, 0f), (3.142f, 0f) };

        // spawn: root (CG) height so that, pitched to the 3-point attitude about the root, the lowest wheel bottom touches y = 0 (+3 cm)
        static float spawnHeight = 3f;
        static void ComputeSpawn(List<LandingGear> gears)
        {
            var q = Quaternion.Euler(SpawnThreePoint ? -ThreePointDeg : 0f, 0, 0);
            float low = float.MaxValue;
            foreach (var g in gears)
            {
                var ax = root.transform.InverseTransformPoint(((Transform)G(g, "axle")).position);
                var p = q * (ax - new Vector3(0, (float)G(g, "wheelRadius"), 0));
                low = Mathf.Min(low, p.y);
            }
            spawnHeight = -low + 0.03f;
            L($"spawn: 3-point {ThreePointDeg} deg, root {spawnHeight:F3} m above ground");
        }

        // b17g_liveries.json (textures worker): {"usaaf_od": {"texture":..., "glossiness": 0.0, "colors": [{"color":"#RRGGBBAA","count":n},...]}, ...}
        static (float, LiveryData.TextureColor[]) LiveryJson(string file)
        {
            var path = Path.Combine(RepoTextures, "b17g_liveries.json");
            if (!File.Exists(path)) return (0.2f, new LiveryData.TextureColor[0]);
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(path));
            Newtonsoft.Json.Linq.JObject e = null;
            foreach (var kv in jo)
                if (kv.Value is Newtonsoft.Json.Linq.JObject o && (kv.Key == file.Replace("b17g_livery_", "") || Path.GetFileNameWithoutExtension((string)o["texture"] ?? "") == file)) { e = o; break; }
            if (e == null) return (0.2f, new LiveryData.TextureColor[0]);
            float gloss = e["glossiness"] != null ? (float)e["glossiness"] : 0.2f;
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
        static bool RunCheck(GameObject prefab)
        {
            var rows = new List<(string name, bool ok, string detail)>();
            void R(string n, bool ok, string d) => rows.Add((n, ok, d));
            var inst = (GameObject)Object.Instantiate(prefab);
            try
            {
                {   // 1.8.16 livery-atlas guard (AtlasGuard1816.cs = blender/atlas_guard.py): the skin / livery / damage textures were painted on THIS UV0 atlas
                    var ag = AtlasGuard1816.Check(inst, mats["paint"], Path.Combine(RepoTextures, "b17g_atlas_manifest.json"), new Dictionary<string, string> { { "fus_center", "B17G" } });
                    R("1.8.16 livery atlas: UV0 of the paint meshes == the texture manifest (textures painted on this atlas, files unchanged)", ag.Item1, ag.Item2);
                }
                var ac = inst.GetComponent<Aircraft>();
                var allParts = inst.GetComponentsInChildren<AeroPart>(true);
                Transform T(string n) => inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == n);
                // identity
                var def = ac.definition;
                R("definition: B17G, rank 3, $45m, 31.62 x 22.66 m, hangar_med only, 3-point rest rotation",
                    def != null && def.jsonKey == JsonKey && ((AircraftDefinition)def).aircraftParameters.rankRequired == 3 && Mathf.Abs(def.value - 45f) < 0.01f && Mathf.Abs(def.width - 31.62f) < 0.01f
                    && (!SpawnThreePoint || ((AircraftDefinition)def).restRotation.x < -5f), $"spawn y {def?.spawnOffset.y:F3}, rest {((AircraftDefinition)def)?.restRotation}");
                float m = allParts.Sum(p => p.mass);
                R("mass: parts 22-26 t (16.4 t empty + crew, ammo, 50 % fuel), encyclopedia empty 16,390 kg", m > 22000f && m < 26000f && Mathf.Abs(((AircraftDefinition)def).aircraftInfo.emptyWeight - 16390f) < 1f, $"{m:F0} kg");
                // engines / props
                var props = inst.GetComponentsInChildren<ConstantSpeedProp>(true);
                var trs = props.Select(p => (Transmission)G(p, "transmission")).ToList();
                R("4 props, 4 own Transmissions + TurbineEngines (an engine kill stops only its prop)", props.Length == 4 && trs.Distinct().Count() == 4 && trs.All(t => t != null && t.GetComponent<TurbineEngine>() != null), string.Join(", ", trs.Select(t => t?.name)));
                R("each prop: 3 blades, own trigger PropStrikeDetector (layer 15), R 1.70-1.80 m", props.All(p => ((IList)G(p, "blades")).Count == 3 && G(p, "propStrikeDetector") is PropStrikeDetector d && d.gameObject.layer == 15 && Mathf.Abs((float)G(p, "bladeLength") - 1.765f) < 0.06f),
                    string.Join(", ", props.Select(p => $"{p.name}: {((IList)G(p, "blades")).Count} blades R {(float)G(p, "bladeLength"):F2}")));
                var engs = inst.GetComponentsInChildren<TurbineEngine>(true);
                R($"engines at game power {EnginePower / 1e6f:F2} MW each (1.6.3 performance tuning), messages ENGINE 1-4 FIRE", engs.Length == 4 && engs.All(e => Mathf.Abs(e.maxPower - EnginePower) < 1f) && engs.Select(e => (string)G(e, "failureMessage")).OrderBy(x => x).SequenceEqual(new[] { "ENGINE 1 FIRE", "ENGINE 2 FIRE", "ENGINE 3 FIRE", "ENGINE 4 FIRE" }),
                    string.Join(", ", engs.Select(e => $"{e.name}:{G(e, "failureMessage")}{(G(e, "failureMessageAudio") != null ? "+voice" : "")}")));
                // prop disc vs fuselage colliders (0.15 m rule, checked on the Unity colliders)
                var fusCols = allParts.Where(p => p.name == "B17G" || p.name.StartsWith("fus_")).Select(p => p.GetComponent<MeshCollider>()).Where(c => c != null).ToList();
                float worst = 9f;
                foreach (var p in props)
                {
                    var c = p.transform.position; float Rr = (float)G(p, "bladeLength");
                    for (int k = 0; k < 72; k++)
                    {
                        float a = k * Mathf.PI * 2 / 72; var q = c + (p.transform.right * Mathf.Cos(a) + p.transform.up * Mathf.Sin(a)) * Rr;
                        foreach (var col in fusCols) { var cp = col.ClosestPoint(q); worst = Mathf.Min(worst, (cp - q).magnitude); }
                    }
                }
                {   // 1.8.9 (offline J; docs/damage_model_study.md): the damage map's ALPHA is the shader's hole map (discard below 0.52 - 0.02 / D).
                    // The 1.8.0 row only tested darkening; the 1.8.0 map had a flat alpha 0.6 (no hole ever opened). Now: skin coverage at HP 80 / 50 / 0
                    // inside the stock bands, the paint material uses the maps, the imported texture keeps its alpha.
                    var dmgPath = Path.Combine(RepoTextures, "b17g_skin_dmg_b.png");
                    var hc = DamageHoles189.Check(dmgPath, tex.ContainsKey("b17g_skin_dmg_b") ? tex["b17g_skin_dmg_b"] : null);
                    var pm = mats["paint"];
                    R("1.8.9 skin damage HOLES: dmg_b alpha opens 5-13 / 10-27 / 15-30 % of the skin at HP 80 / 50 / 0 (stock bands), paint material uses dmg_b / dmg_n, alpha kept on import",
                        hc.Item1 && File.Exists(Path.Combine(RepoTextures, "b17g_skin_dmg_n.png")) && pm.GetTexture("_BasecolorDmg") == tex["b17g_skin_dmg_b"] && pm.GetTexture("_NormalDmg") == tex["b17g_skin_dmg_n"], hc.Item2);
                }
                R(ANM2Guns ? "1.8.13 AN/M2 guns: the stock barrel no longer used (kept as the fallback; its bore read from its vertex data)" : "1.8.0 gun barrels on their slots: the stock barrel's bore read from its vertex data (not the bounds centre: 8 cm right, 2 cm high in 1.7.x); bore within 1 cm of the mesh centreline",
                    ANM2Guns || (!barrelTipSource.StartsWith("bounds") && Mathf.Abs(barrelTip.x) < 0.01f && barrelTip.y > 0f && barrelTip.y < 0.08f && barrelTip.z > 1.0f),
                    $"bore ({barrelTip.x:F3}, {barrelTip.y:F3}, {barrelTip.z:F3}) from {barrelTipSource}");
                R("prop tips >= 0.15 m from the fuselage colliders", worst >= 0.15f, $"min {worst:F3} m");
                // gear
                var gears = inst.GetComponentsInChildren<LandingGear>(true).Where(g => !g.name.EndsWith(GripGear.Suffix)).ToArray();   // 1.8.0: grip partners in their own row
                var mains = gears.Where(g => g.name.StartsWith("gear_main")).ToList(); var tailg = gears.FirstOrDefault(g => g.name.StartsWith("gear_tail"));
                {
                    bool gok = GripGear.Verify(inst, MainBrakeShare, MainFriction, MainK, out string gd);
                    R($"1.8.0 split mains: braked + unbraked grip LandingGear per wheel on one contact, frictionCoef {MainFriction} both, braked share {MainBrakeShare} -> braking {MainFriction * MainBrakeShare:F3} x load = BrakeFriction {BrakeFriction}, side grip {MainFriction} x load (1.7.13 0.22)",
                        !SplitMainGear || (gok && Mathf.Abs(MainFriction * MainBrakeShare - BrakeFriction) < 1e-4f), gd);
                }
                R("gear: 2 braked mains + 1 steerable tailwheel, k / damping sized for 25 t (k of braked + grip)", mains.Count == 2 && tailg != null && mains.All(g => (bool)G(g, "braked") && (float)G(g, "springRate") >= 1.2e6f * (SplitMainGear ? MainBrakeShare : 1f)) && (bool)G(tailg, "steering"),
                    string.Join(", ", gears.Select(g => $"{g.name} k {(float)G(g, "springRate"):F0} c {(float)G(g, "dampingRate"):F0} fold {(float)G(g, "foldDegrees")}")));
                bool foldOk = true; var foldDetail = new List<string>();
                foreach (var g in gears)
                {
                    var h = (Transform)G(g, "gearHinge"); var wv = ((Transform[])G(g, "wheels"))[0];
                    var p0 = wv.position; var r0 = h.localRotation;
                    h.localRotation = r0 * Quaternion.Euler((float)G(g, "foldDegrees"), 0, 0);
                    var p1 = wv.position; h.localRotation = r0;
                    bool fwdUp = g.name.StartsWith("gear_main") ? (p1.z > p0.z + 0.8f && p1.y > p0.y + 1.0f) : (p1.y > p0.y + 0.3f);
                    foldOk &= fwdUp; foldDetail.Add($"{g.name}: wheel moves ({p1.x - p0.x:F2}, {p1.y - p0.y:F2}, {p1.z - p0.z:F2})");
                }
                R("gear folds: mains forward + up into the nacelles, tailwheel up into the tail", foldOk, string.Join("; ", foldDetail));
                // nose-over margin (noseover.py rule) and 3-point attitude from the built prefab
                var com = inst.transform.InverseTransformPoint(allParts.Aggregate(Vector3.zero, (s, p) => s + p.transform.TransformPoint(p.GetComponent<MeshCollider>() ? p.GetComponent<MeshCollider>().sharedMesh.bounds.center : Vector3.zero) * p.mass) / m);
                var mAx = inst.transform.InverseTransformPoint(((Transform)G(mains[0], "axle")).position); var tAx = inst.transform.InverseTransformPoint(((Transform)G(tailg, "axle")).position);
                float contactY = mAx.y - 0.711f, d = mAx.z - com.z, hh = com.y - contactY;
                float tailUp = Mathf.Atan2(d, hh) * Mathf.Rad2Deg, three = Mathf.Atan2((tAx.y - 0.33f) - contactY, mAx.z - tAx.z) * Mathf.Rad2Deg;
                R($"nose-over: tail-up CoM angle >= brake friction angle + 3 deg (coordinator 1.6.1 target; noseover.py; friction {BrakeFriction})", tailUp >= Mathf.Atan(BrakeFriction) * Mathf.Rad2Deg + 3.0f, $"CoM {com.ToString("F2")} (parts collider centres), axle z {mAx.z:F2}: {tailUp:F1} deg");
                R("3-point attitude 7-11 deg (restRotation spawns in it)", three > 7f && three < 11f, $"{three:F1} deg");
                // round 3 (user: tail assembly spun, no steering). LandingGear.cs 556-558 spins every `wheels` transform about local X;
                // 718-724 steers `unsprung` about local Y. A wheel transform may only carry a round tyre about its own axle.
                {
                    var bad = new List<string>(); var det = new List<string>();
                    foreach (var g in gears)
                        foreach (var wv in (Transform[])G(g, "wheels"))
                        {
                            float rr = (float)G(g, "wheelRadius"), maxR = 0f, maxOff = 0f; int nv = 0;
                            foreach (var mf in wv.GetComponentsInChildren<MeshFilter>(true))
                            {
                                if (mf.sharedMesh == null) continue;
                                foreach (var v in mf.sharedMesh.vertices) { var lp = wv.InverseTransformPoint(mf.transform.TransformPoint(v)); maxR = Mathf.Max(maxR, new Vector2(lp.y, lp.z).magnitude); nv++; }
                                var bc = wv.InverseTransformPoint(mf.transform.TransformPoint(mf.sharedMesh.bounds.center)); maxOff = Mathf.Max(maxOff, new Vector2(bc.y, bc.z).magnitude);
                            }
                            if (nv == 0 || maxR > rr * 1.06f || maxOff > 0.03f) bad.Add(wv.name);
                            det.Add($"{wv.name}: radius {maxR:F3}/{rr:F3}, off-axle {maxOff:F3}");
                        }
                    R("wheels spin-safe: each LandingGear wheel carries only a round tyre about its own axle (no fork / strut in a spinning transform)", bad.Count == 0, string.Join("; ", det));
                }
                {
                    var tl = tailg; float lockv = (float)G(tl, "steeringLock"), fr = (float)G(tl, "frictionCoef"), al = (float)G(tl, "aligningStrength"), sp = (float)G(tl, "steeringSpeed");
                    var uns = ((GameObject)G(tl, "unsprung")).transform;
                    var fork = T("fork_tail");
                    var u0 = uns.localRotation; uns.localEulerAngles = new Vector3(0f, 1f * lockv, 0f);          // full right rudder (yaw +1)
                    float headX = inst.transform.InverseTransformDirection(uns.forward).x; uns.localRotation = u0;
                    bool behind = tAx.z < com.z;
                    bool noseRight = behind ? headX < -0.05f : headX > 0.05f;          // a wheel behind the CG must point LEFT for a right turn
                    var right = mains.FirstOrDefault(x => inst.transform.InverseTransformPoint(((Transform)G(x, "axle")).position).x > 0f);
                    bool diffOk = right != null && (float)G(right, "differentialBrakeFactor") > 0f;
                    float wb = mAx.z - tAx.z, lockAbs = Mathf.Abs(lockv), eff5 = Mathf.Min(lockAbs, sp / (0.5f * Mathf.Max(al, 0.01f)));
                    float rFull = wb / Mathf.Tan(lockAbs * Mathf.Deg2Rad), r5 = wb / Mathf.Tan(eff5 * Mathf.Deg2Rad);
                    bool forkOk = fork != null && fork.parent == uns && !((Transform[])G(tl, "wheels")).Contains(fork);
                    R("tailwheel steering (taildragger, Nimrod / FD-32 technique): lock < 0 behind the CG -> right rudder turns the nose right; stock side grip >= 0.6; fork rides unsprung; right main brakes on right rudder; turn radius <= 25 m at 5 m/s",
                        noseRight && fr >= 0.6f && forkOk && diffOk && r5 <= 25f,
                        $"lock {lockv} (wheel {(behind ? "behind" : "ahead of")} the CoM), wheel heading x {headX:F2} at yaw +1, friction {fr}, aligning {al}, speed {sp}; fork parent {(fork != null ? fork.parent.name : "missing")}; wheelbase {wb:F2} m: R {rFull:F1} m at full lock, {r5:F1} m at 5 m/s (effective {eff5:F0} deg); mains friction {BrakeFriction}");
                }
                // ===== 1.6.1 rows (in-game catalogue of 1.6.0) =====
                {   // (13) colliders: PhysX cooks a convex hull of at most 255 polygons; ours come from <= 96 support points (hull <= 188 faces)
                    var big = inst.GetComponentsInChildren<MeshCollider>(true).Where(c => c.convex && c.sharedMesh != null && c.sharedMesh.vertexCount > 100).Select(c => $"{c.name} {c.sharedMesh.vertexCount}v").ToList();
                    int n = inst.GetComponentsInChildren<MeshCollider>(true).Count(c => c.convex);
                    R("convex colliders cook whole: <= 100 hull points each (<= 196 faces, PhysX cap 255; 1.6.0 Player.log: partial hulls on 8 B17G parts)", big.Count == 0, $"{n} convex colliders; over: {string.Join(", ", big.Take(6))}");
                }
                {   // (1) ground handling numbers from the prefab (LandingGear.cs 546-555 brakes, 331-342 soft ground, 718-724 steering)
                    float mass = allParts.Sum(p => p.mass), W = mass * 9.81f;
                    float zt = tAx.z, zm = mAx.z, zc = com.z;
                    float Nt = W * (zm - zc) / (zm - zt), Nm = W - Nt;
                    float mu = BrakeFriction, decel = mu * Nm / mass, hold = mu * Nm;
                    float tailUpDeg = Mathf.Atan2(zm - zc, com.y - (mAx.y - 0.711f)) * Mathf.Rad2Deg, muDeg = Mathf.Atan(mu) * Mathf.Rad2Deg;
                    float area = (float)G(mains[0], "contactArea") / (SplitMainGear ? Mathf.Pow(MainBrakeShare, 0.75f) : 1f), press = (Nm / 2f) / (area * 1e4f), depth = press * 0.003f / 5f;
                    float grass = 2.5f * depth * depth * 33f * press * press;     // per main at 33 m/s (119 km/h), typical ground noise num3 = 5
                    float overturn = 2f * grass * (com.y - (mAx.y - 0.711f)), restore = W * (zm - zc);
                    float wb = zm - zt, lockAbs = Mathf.Abs((float)G(tailg, "steeringLock")), rTurn = wb / Mathf.Tan(lockAbs * Mathf.Deg2Rad);
                    bool ok = decel >= 1.8f && tailUpDeg - muDeg >= 3f && grass <= 0.15f * Nm / 2f && overturn < 0.5f * restore && rTurn <= 30f && (float)G(tailg, "aligningStrength") == 0f;
                    R("ground handling: braking >= 1.8 m/s2 (1.7.3), nose-over margin >= 3 deg, grass drag at 33 m/s <= 15 % of the wheel load, taxi radius <= 30 m, tailwheel not castering",
                        ok, $"mass {mass:F0} kg, mains {Nm / 1e3:F0} kN / tail {Nt / 1e3:F0} kN; braking {decel:F2} m/s2 (mu {mu}), brake hold {hold / 1e3:F0} kN; tail-up {tailUpDeg:F1} deg vs atan(mu) {muDeg:F1} (margin {tailUpDeg - muDeg:F1}); contact {area:F3} m2 (single-gear equivalent of the split) -> {press:F0} N/cm2, grass drag {grass / 1e3:F1} kN per main (pitch-down moment {overturn / 1e3:F0} vs weight {restore / 1e3:F0} kNm); full-lock radius {rTurn:F1} m");
                }
                // physics queries on the instance (bail-out spots, crew inside the hull)
                Physics.SyncTransforms();
                {   // (10) bail-out: PilotDismounted.FindDismountSpot (PilotDismounted.cs 518-540) needs a spot 2..10 m to the side of the crew
                    //      member's part with nothing above it within 10 m; the down cast (20 m) must not land it on our own wing / tail
                    var det = new List<string>(); bool ok = ac.pilots != null && ac.pilots.Length == 10;
                    foreach (var pl in ac.pilots ?? new Pilot[0])
                    {
                        var up_ = pl.GetUnitPart(); var pt = up_ != null ? up_.transform : null;
                        if (pt == null) { ok = false; det.Add($"{pl.name}: no part"); continue; }
                        int sign = pl.exitDirection != Pilot.ExitDirection.Left ? 1 : -1; Vector3 spot = pt.position; int k = 1; bool found = false;
                        for (; k < 10; k++)
                        {
                            spot = pt.position + pt.right * (k + 1) * sign;
                            if (!Physics.Linecast(spot + Vector3.up * 10f, spot)) { found = true; break; }
                            sign = -sign;
                        }
                        bool landsOnUs = Physics.Linecast(spot, spot - Vector3.up * 20f, out var hdn) && hdn.collider != null && hdn.collider.transform.IsChildOf(inst.transform);
                        bool okp = !landsOnUs; ok &= okp;
                        det.Add($"{pl.name}:{(found ? $"{k + 1}m" : "NONE")}{(landsOnUs ? " ON " + hdn.collider.name : "")}");
                    }
                    R("bail-out: 10 crew; FindDismountSpot (incl. its 10 m fallback when every spot has airframe above) never drops a crew member onto our own airframe (spot found / NONE = fallback)", ok, string.Join(", ", det));
                }
                {   // (4) every crew vertex inside the hull: from each vertex, rays +-X and +-Y (4 m) against every airframe mesh (back faces on)
                    var tmp = new List<GameObject>(); int layer = 31;
                    var figs = new HashSet<Transform>((ac.pilots ?? new Pilot[0]).Select(p => p.transform));
                    foreach (var mf in inst.GetComponentsInChildren<MeshFilter>(true))
                    {
                        if (mf.sharedMesh == null || figs.Any(f => mf.transform.IsChildOf(f))) continue;
                        var go = new GameObject("hullprobe"); go.layer = layer; go.transform.SetPositionAndRotation(mf.transform.position, mf.transform.rotation); go.transform.localScale = mf.transform.lossyScale;
                        var mc = go.AddComponent<MeshCollider>(); mc.sharedMesh = mf.sharedMesh; mc.convex = false; tmp.Add(go);
                    }
                    Physics.SyncTransforms();
                    bool back = Physics.queriesHitBackfaces; Physics.queriesHitBackfaces = true;
                    var det = new List<string>(); bool ok = true; int mask = 1 << layer;
                    var right = inst.transform.right; var upv = inst.transform.up;
                    // round 5 (user review 2: legs still out in game after 1.6.1): the in-game pose is NOT the prefab's bind pose - each
                    // figure's Animator plays the stock PilotController 'seated' state (and 'deadCockpit' when the crew member dies). Both
                    // clips are sampled onto the figures (AnimationMode) before baking, so this check sees what the game shows.
                    var poseClips = new List<AnimationClip>();
                    foreach (var pl0 in ac.pilots ?? new Pilot[0])
                    {
                        var an0 = pl0.GetComponentInChildren<Animator>(true);
                        if (an0 != null && an0.runtimeAnimatorController != null)
                            foreach (var cl in an0.runtimeAnimatorController.animationClips)
                                if (cl != null && (cl.name.StartsWith("seated") || cl.name.StartsWith("deadCockpit")) && !poseClips.Contains(cl)) poseClips.Add(cl);
                    }
                    det.Add($"poses sampled: {(poseClips.Count > 0 ? string.Join("/", poseClips.Select(c => c.name)) : "NONE (no controller)")}");
                    ok &= poseClips.Count >= 2;
                    foreach (var poseClip in poseClips)
                    foreach (var pl in ac.pilots ?? new Pilot[0])
                    {
                        var anim = pl.GetComponentInChildren<Animator>(true);
                        if (anim != null)
                        {
                            if (!AnimationMode.InAnimationMode()) AnimationMode.StartAnimationMode();
                            AnimationMode.BeginSampling(); AnimationMode.SampleAnimationClip(anim.gameObject, poseClip, 0.03f); AnimationMode.EndSampling();
                        }
                        int outside = 0, total = 0; Vector3 worstV = Vector3.zero; string worstWhy = "";
                        var ballBody = pl.name == "crew_ball" ? inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "ball_el") : null;   // the ball gunner sits in the ball (open windows): sphere test
                        foreach (var smr in pl.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                        {
                            var baked = new Mesh(); smr.BakeMesh(baked);
                            foreach (var v in baked.vertices)
                            {
                                var p = smr.transform.position + smr.transform.rotation * v; total++;      // BakeMesh: renderer space without its scale
                                if (ballBody != null) { if ((p - ballBody.position).magnitude > 0.57f) { outside++; worstV = p; } continue; }
                                bool r1 = Physics.Raycast(p, right, 4f, mask), r2 = Physics.Raycast(p, -right, 4f, mask);
                                bool u1 = Physics.Raycast(p, upv, 4f, mask), hd = Physics.Raycast(p, -upv, 4f, mask);
                                bool hx = r1 && r2, hy = u1 || hd;
                                if (!(hx && hy && hd)) { outside++; worstV = p; worstWhy = (r1 ? "" : "R") + (r2 ? "" : "L") + (hd ? "" : "D") + (hy ? "" : "U"); }   // 1.8.17: which rays left
                            }
                            Object.DestroyImmediate(baked);
                        }
                        bool okp = total > 0 && outside == 0; ok &= okp;
                        if (!okp || pl == ac.pilots[0]) det.Add($"{poseClip.name}: {pl.name} {outside}/{total}" + (okp ? "" : $" e.g. {inst.transform.InverseTransformPoint(worstV).ToString("F2")} misses {worstWhy}"));
                    }
                    if (AnimationMode.InAnimationMode()) AnimationMode.StopAnimationMode();
                    Physics.queriesHitBackfaces = back;
                    foreach (var go in tmp) Object.DestroyImmediate(go);
                    R("crew inside the hull in the game's animated poses (seated + deadCockpit sampled): every figure vertex has airframe on both sides and below (0 outside)", ok, string.Join("; ", det));
                }
                // weapons
                var wm = ac.weaponManager;
                var bayS = wm.hardpointSets.FirstOrDefault(x => x.name == "Bomb Bay");
                R("bomb bay: 8 x PAB-250 / 4 x GPO-500 / 2 x CBO-400 (own enabled copy) / GPO-N, every non-nuclear option allowed (WeaponMount.IsAllowed), two BayDoors", bayS != null && bayS.weaponOptions.Skip(1).Select(o => o.name.Replace("_PLACEHOLDER", "")).SequenceEqual(new[] { "bomb_250_internalx8", "bomb_500_internalx4_stack", "B17G_cbo400_x2", "nuclearBomb1_internal" })
                    && bayS.weaponOptions.Skip(1).Where(o => o.info == null || !o.info.nuclear).All(o => o.IsAllowed(false))
                    && bayS.hardpoints[0].bayDoors.Length == 2, bayS == null ? "" : string.Join(", ", bayS.weaponOptions.Skip(1).Select(o => o.name)));
                bool doorsOk = true; var dd = new List<string>();
                foreach (var bd in bayS.hardpoints[0].bayDoors)
                {
                    var tr = bd.transform; var mf = tr.GetComponentInChildren<MeshFilter>(); var c0 = mf.transform.TransformPoint(mf.sharedMesh.bounds.center);
                    var r0 = tr.localRotation; tr.localEulerAngles = new Vector3(0, 0, (float)G(bd, "hingeAngle")); var c1 = mf.transform.TransformPoint(mf.sharedMesh.bounds.center); tr.localRotation = r0;
                    bool ok = c1.y < c0.y - 0.15f && Mathf.Abs(c1.x) > Mathf.Abs(c0.x) + 0.3f; doorsOk &= ok; dd.Add($"{tr.name}: centre moves ({c1.x - c0.x:F2}, {c1.y - c0.y:F2})");
                }
                R("bay doors open down and out", doorsOk, string.Join("; ", dd));
                var tur = inst.GetComponentsInChildren<Turret>(true);
                var guns = tur.SelectMany(t => ((Transform[])G((Gun)G(t, "aimSafetyWeapon"), "muzzles"))).Count();
                var infos = tur.Select(t => ((Gun)G(t, "aimSafetyWeapon")).info).Distinct().ToList();
                R("9 gun positions, 13 x 12.7 mm, 5 stations (one WeaponInfo per station)", tur.Length == 9 && guns == 13 && infos.Count == 5 && wm.hardpointSets.Count(x => x.name.EndsWith(" guns")) == 5,
                    string.Join(", ", infos.Select(i => i.weaponName)));
                R("exclusion firing cones from the offline turret scan", !TurretExclusionCones || exclusionConeCount > 0, $"{exclusionConeCount} cones");
                // round 3 turret audit (Turret.cs 715-716: az localEulerAngles = (0, trav, 0), el = (elev, 0, 0) absolutely; Gun.cs 634: bullets
                // leave every muzzle along muzzle.forward): parenting, rest frames, muzzle axis = el axis, muzzles at the stock barrel tips,
                // bodies on the moving parts, a usable share of the envelope inside the firing cones
                {
                    var det = new List<string>(); bool ok = true;
                    foreach (var t in tur)
                    {
                        var az = t.transform; var el = (Transform)G(t, "elevationTransform"); var mount = az.parent;
                        var gun = el.GetComponent<Gun>(); var mz = gun != null ? (Transform[])G(gun, "muzzles") : new Transform[0];
                        bool par = gun != null && el.parent == az && mount != null && mount.name.EndsWith("_mount") && mz.Length > 0 && mz.All(x => x.IsChildOf(el));
                        bool rest = Quaternion.Angle(az.localRotation, Quaternion.identity) < 0.5f && Quaternion.Angle(el.localRotation, Quaternion.identity) < 0.5f;
                        float dirErr = 0f, tipErr = 0f;
                        foreach (var x in mz)
                        {
                            dirErr = Mathf.Max(dirErr, Vector3.Angle(x.forward, el.forward));
                            var mf = x.parent != null ? x.parent.GetComponentsInChildren<MeshFilter>(true).FirstOrDefault(f => f.sharedMesh != null && (f.sharedMesh.name.StartsWith("50cal") || f.sharedMesh.name.Contains("_anm2_") && !f.sharedMesh.name.EndsWith("grips"))) : null;
                            if (mf != null) tipErr = Mathf.Max(tipErr, (mf.transform.TransformPoint(mf.sharedMesh.name.Contains("_anm2_") ? new Vector3(0f, 0f, mf.sharedMesh.bounds.max.z) : BarrelTip(mf.sharedMesh)) - x.position).magnitude);
                        }
                        // envelope share inside the cones (5-deg grid over traverse x elevation, as Turret.AimTurret clamps)
                        var cones = (FiringCone[])G(t, "firingCones"); int tot = 0, inside = 0;
                        float tr = Mathf.Min((float)G(t, "traverseRange"), 180f), e0 = (float)G(t, "minElevation"), e1 = (float)G(t, "maxElevation");
                        for (float a = -tr; a <= tr + 0.01f; a += 5f)
                            for (float e = e0; e <= e1 + 0.01f; e += 5f)
                            {
                                var dir = mount.rotation * (Quaternion.Euler(0f, a, 0f) * (Quaternion.Euler(-e, 0f, 0f) * Vector3.forward)); tot++;
                                if (FiringConeChecker.VectorWithinFiringCones(cones, dir, out var _)) inside++;
                            }
                        float share = tot > 0 ? (float)inside / tot : 0f;
                        bool tOk = par && rest && dirErr < 1f && tipErr < 0.12f && share >= 0.4f; ok &= tOk;
                        det.Add($"{mount?.name}: {(par ? "" : "PARENT ")}{(rest ? "" : "REST ")}muzzle axis {dirErr:F1} deg, tip {tipErr:F2} m, envelope in cones {share * 100f:F0} %");
                    }
                    var bodies = new[] { ("topturret_body", "top_az"), ("ballturret_body", "ball_el"), ("chinturret_body", "chin_az"), ("tailmantlet_body", "tail_az") };   // round 5: the Cheyenne cover turns in azimuth, the guns elevate in its slots
                    foreach (var (b, host) in bodies) { var bt = T(b); var ht = T(host); bool bo = bt != null && ht != null && bt.IsChildOf(ht); ok &= bo; if (!bo) det.Add($"{b} NOT under {host}"); }
                    R("turret kinematics: mount > az > el > gun > muzzle, az / el rest at identity, muzzles along el +Z at the stock barrel tips, bodies on az / el, >= 40 % of each envelope inside its cones", ok, string.Join("; ", det));
                }
                if (FireClear1814On && DefensiveTurrets)
                {   // 1.8.14 (offline M): the saved cones re-swept on this instance with the game's own FiringConeChecker
                    var fc14 = FireClear1814.CheckInstance(inst);
                    R("1.8.14 fire clearance: no aim direction where a turret may fire into our own airframe (game FiringConeChecker + 1 deg onTarget; colliders, meshes, prop discs; 1 deg grid, posed muzzles)", fc14.bad == 0, fc14.detail);
                }
                if (ANM2Guns)
                {   // 1.8.13: 13 AN/M2 bodies (twins L + R, singles by feed side), grips on the 7 hand-held guns (tail twin, cheeks, waists, radio), none on chin / top / ball
                    var bodies2 = inst.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("B17G_anm2_") && !f.sharedMesh.name.EndsWith("grips")).ToList();
                    // round 2: powered turrets carry the turret gun (short slide, buffer stub), hand-held positions the flexible gun (lever + knob)
                    bool kinds = bodies2.All(f => (f.name.StartsWith("chin_") || f.name.StartsWith("top_") || f.name.StartsWith("ball_")) == f.sharedMesh.name.Contains("_turret_"));
                    var gripsN = inst.GetComponentsInChildren<MeshFilter>(true).Count(f => f.sharedMesh != null && f.sharedMesh.name == "B17G_anm2_grips");
                    bool noStock = !inst.GetComponentsInChildren<MeshFilter>(true).Any(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("50cal"));
                    bool turretNoGrips = bodies2.Where(f => f.name.StartsWith("chin_") || f.name.StartsWith("top_") || f.name.StartsWith("ball_")).All(f => f.transform.childCount == 0);
                    bool twinsLR = new[] { "chin", "top", "ball", "tail" }.All(s => bodies2.Count(f => f.name.StartsWith(s + "_gun0") && f.sharedMesh.name.EndsWith("_L")) == 1 && bodies2.Count(f => f.name.StartsWith(s + "_gun1") && f.sharedMesh.name.EndsWith("_R")) == 1);
                    R("1.8.13 AN/M2 on every gun slot: 13 bodies (twins gun_L + gun_R), turret guns on chin / top / ball, flexible guns + grips on the 7 hand-held, no stock door-gun barrel left", bodies2.Count == 13 && gripsN == 7 && noStock && turretNoGrips && twinsLR && kinds,
                        $"{bodies2.Count} bodies ({bodies2.Count(f => f.sharedMesh.name.EndsWith("_L"))} L / {bodies2.Count(f => f.sharedMesh.name.EndsWith("_R"))} R), {gripsN} grips, turret / flex kinds {(kinds ? "ok" : "WRONG")}, stock barrels left {(noStock ? 0 : 1)}");
                }
                else
                R("stock 12.7 mm barrel mesh on every gun slot", tur.All(t => ((Gun)G(t, "aimSafetyWeapon")).GetComponentsInChildren<MeshFilter>(true).Any(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("50cal"))) || inst.GetComponentsInChildren<MeshFilter>(true).Count(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("50cal")) == 13,
                    $"{inst.GetComponentsInChildren<MeshFilter>(true).Count(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("50cal"))} barrels");
                // crew / cockpit
                R("crew of 10, bail-out (no ejection seats), own figures", ac.pilots.Length == 10 && ac.pilots.All(p => p != null && !(bool)G(p, "ejectionSeat")), string.Join(", ", ac.pilots.Select(p => p.name)));
                R("cockpit view point = the left-seat pilot eye", ac.cockpitViewPoint != null && ac.cockpitViewPoint.position.x < -0.2f, ac.cockpitViewPoint ? ac.cockpitViewPoint.position.ToString("F2") : "none");
                var ck = inst.GetComponentInChildren<global::Cockpit>(true);
                var thr = ck != null ? (IList)G(ck, "throttles") : null;
                R("4 throttle levers on Cockpit.throttles, grips move forward at full throttle", thr != null && thr.Count == 4 && throttleForward.Count == 4 && throttleForward.Values.All(v => v > 0.03f), string.Join(", ", throttleForward.Select(k => $"{k.Key} +{k.Value:F2} m")));
                if (ColumnPlugin189)
                {   // 1.8.9 (user on 1.8.8: "The WHEEL moves, the stick does not"): no Cockpit.joysticks; B25H.Instruments pitches the columns about
                    // their floor pivots and turns the wheels about their hub axes (B17G.cs ColumnDeg = -pitch x 12, WheelDeg = roll x 30, about local +X).
                    // Same formula here on the built instance (the full proof with no-yaw rows: unity/Editor/ColumnCheck189.cs)
                    var jl = ck != null ? ((IEnumerable)G(ck, "joysticks")).Cast<object>().ToList() : new List<object>();
                    var det = new List<string>(); bool ok = jl.Count == 0;
                    foreach (var side in new[] { "L", "R" })
                    {
                        var col = T("cockpit_column_" + side); var yk = T("cockpit_yoke_" + side);
                        if (col == null || yk == null || !yk.IsChildOf(col)) { ok = false; det.Add(side + ": column / wheel missing or not nested"); continue; }
                        var cR = col.localRotation; var yR = yk.localRotation; var hub0 = inst.transform.InverseTransformPoint(yk.position); var top0 = inst.transform.InverseTransformPoint(yk.position + yk.up * 0.1f);
                        col.localRotation = cR * Quaternion.AngleAxis(12f, Vector3.right); var hubPush = inst.transform.InverseTransformPoint(yk.position); col.localRotation = cR;
                        yk.localRotation = yR * Quaternion.AngleAxis(30f, Vector3.right); var topRoll = inst.transform.InverseTransformPoint(yk.position + yk.up * 0.1f); yk.localRotation = yR;
                        bool o = hubPush.z - hub0.z > 0.08f && topRoll.x - top0.x > 0.02f; ok &= o;
                        det.Add($"{side}: push moves the hub {(hubPush.z - hub0.z) * 1000:F0} mm forward, roll right the wheel top {(topRoll.x - top0.x) * 1000:F0} mm right");
                    }
                    bool noCS = !inst.GetComponentsInChildren<ControlSurface>(true).Any(c => c.name.StartsWith("cockpit_"));
                    R("1.8.9 columns + wheels moved by B25H.Instruments (no Cockpit.joysticks): push = column forward about the floor pivot carrying the wheel, roll right = wheel top right, no cockpit ControlSurfaces", ok && noCS, string.Join("; ", det));
                }
                else
                {   // 1.6.1: wheels on Cockpit.joysticks (stock stick driver); a full right roll turns each wheel's top to the right
                    var jl = ck != null ? ((IEnumerable)G(ck, "joysticks")).Cast<object>().ToList() : new List<object>();
                    var det = new List<string>(); bool ok = jl.Count == 2;
                    foreach (var j in jl)
                    {
                        var t = (Transform)G(j, "transform"); float rg = (float)G(j, "range");
                        var wheel = t.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name.StartsWith("cockpit_yoke_") && !x.name.Contains("_js"));
                        bool rest = Quaternion.Angle(t.localRotation, Quaternion.identity) < 0.5f;
                        var topRest = t.position + t.up * 0.2f;
                        var r0 = t.localRotation; t.localEulerAngles = new Vector3(0f, 0f, -1f * rg); var top1 = t.position + t.up * 0.2f; t.localRotation = r0;
                        var topRolled = inst.transform.InverseTransformPoint(top1).x - inst.transform.InverseTransformPoint(topRest).x;
                        bool okj = wheel != null && rest && rg >= 20f && topRolled > 0.05f; ok &= okj;
                        det.Add($"{t.name}: range {rg}, wheel {(wheel ? wheel.name : "missing")}, rest {(rest ? "identity" : "NOT identity")}, full right roll moves the wheel top {topRolled:F2} m right");
                    }
                    bool noCS = !inst.GetComponentsInChildren<ControlSurface>(true).Any(c => c.name.StartsWith("cockpit_"));
                    R("yokes: 2 wheels on Cockpit.joysticks (stock stick driver, as the Nimrod / FD-32 sticks), roll right = wheel top right, no cockpit ControlSurfaces", ok && noCS, string.Join("; ", det));
                }
                var needles = inst.GetComponentsInChildren<Transform>(true).Count(t => t.name.StartsWith("gauge_") && (t.name.EndsWith("_needle") || t.name.EndsWith("_card") || t.name.EndsWith("_short")));
                R("40 gauge movers present (B25H.Instruments 1.8.4 B17G branch drives them by name; 19 until 1.8.3 + 21 formerly static dials)", needles == 40, $"{needles}");
                R("no rudder pedals, no screens", inst.GetComponentsInChildren<Transform>(true).All(t => !t.name.Contains("pedal")) && inst.GetComponentsInChildren<Transform>(true).All(t => !t.name.StartsWith("mfd_")), "");
                var ckR = (Renderer[])G(ac, "cockpitRenderers");
                R("cockpit layer copies, glass copies use the faint glass (no canopy_int)", ckR != null && ckR.Length > 10 && ckR.All(r => r.gameObject.layer == 3) && ckR.SelectMany(r => r.sharedMaterials).All(mt => mt == null || mt.shader == null || !mt.shader.name.Contains("canopy_int")), $"{ckR?.Length} renderers");
                R("HUD kept (COIN_HUDExtras)", ((AircraftDefinition)def).aircraftParameters.HUDExtras != null, "");
                // flight model
                var prm = ((AircraftDefinition)def).aircraftParameters;
                R("airfoils: wing / tail / aileron / flap; ailerons use the aileron curve, flaps the flap curve", prm.airfoils.Length == 4 && allParts.Where(p => p.name.StartsWith("aileron")).All(p => (int)G(p, "airfoil") == 2) && allParts.Where(p => p.name.StartsWith("flap_")).All(p => (int)G(p, "airfoil") == 3), string.Join(", ", prm.airfoils.Select(a => a.name)));
                var fbw = new SerializedObject(inst.GetComponentInChildren<ControlsFilter>(true));
                float lim = fbw.FindProperty("flyByWire.alphaLimiter").floatValue;
                R("alpha limiter + wing incidence = wing CLmax angle (16 deg)", Mathf.Abs(lim + WingIncidence - WingCLmaxDeg) < 0.05f, $"{lim} + {WingIncidence}");
                {   // 1.7.8 lateral (spiral + AI weave): handed props, no FBW roll trim, AI roll PID, terrain look-ahead
                    var dirs = props.Select(p => Convert.ToInt32(G(p, "turnDirection"))).ToList();
                    float worstLt = 1f;
                    foreach (var p in props)
                    {
                        int dir = Convert.ToInt32(G(p, "turnDirection"));
                        foreach (var b in (IList)G(p, "blades"))
                        {
                            var bt = (Transform)G(b, "transform"); var lt = (Transform)G(b, "liftTransform");
                            var motion = Vector3.Cross(-p.transform.forward, bt.forward).normalized * dir;
                            worstLt = Mathf.Min(worstLt, Vector3.Dot(lt.forward, motion));
                        }
                    }
                    var ap = new SerializedObject(inst.GetComponentInChildren<AutopilotPlane>(true));
                    var pid = ap.FindProperty("forwardFlightController.rollFlightPID.PID").vector3Value;
                    float trL = fbw.FindProperty("flyByWire.rollTrimLimit").floatValue, trR = fbw.FindProperty("flyByWire.rollTrimRate").floatValue;
                    R("1.7.8 lateral: handed props (turn sum 0, left 1 / right -1, every blade lift transform along its own motion), FBW roll trim off, AI roll PID, look-ahead gLimit",
                        dirs.Sum() == 0 && dirs.Count == 4 && worstLt > 0.98f && trL == FbwRollTrimLimit && trR == FbwRollTrimRate && (pid - AiRollPID).magnitude < 1e-5f && Mathf.Abs(prm.aircraftGLimit - AiLookaheadGLimit) < 1e-5f,
                        $"turn {string.Join("/", props.Select(p => p.name + ":" + Convert.ToInt32(G(p, "turnDirection"))))}, lift-transform alignment min {worstLt:F3}, trim {trL}/{trR}, roll PID {pid}, gLimit {prm.aircraftGLimit}");
                }
                R("every part (props excepted) has its own ImpactDamage", allParts.Where(p => !p.name.StartsWith("prop_")).All(p => { var x = G(p, "impactDamage"); return x != null && (float)G(x, "threshold") > 0f; }) && allParts.Where(p => !p.name.StartsWith("prop_")).Select(p => G(p, "impactDamage")).Distinct().Count() == allParts.Count(p => !p.name.StartsWith("prop_")), "");
                var noJ = allParts.Where(p => p.transform != inst.transform && (p.Joints == null || p.Joints.Length == 0)).Select(p => p.name).ToList();
                var wr = allParts.Where(p => p.name.StartsWith("wing_inner")).Select(p => p.Joints == null || p.Joints.Length == 0 ? 0f : p.Joints.Max(j => j.breakForce)).ToList();
                R("joints: wing roots >= 450 kN class, every part jointed", wr.Count == 2 && wr.All(f => f >= 450000f) && noJ.Count == 0, $"wing roots {string.Join("/", wr)}; without joints: {string.Join(",", noJ)}");
                var fuel = inst.GetComponentsInChildren<FuelTank>(true);
                {   // round 5 (wreck fire): one AB-4-style tank per tank-carrying part, on the part's own transform, origin inside the part's
                    // own collider bounds (the fire / fireball spawn point), links inner <-> mid <-> outer and inner <-> centre section
                    var bad = new List<string>();
                    foreach (var f in fuel)
                    {
                        var up = f.GetComponent<AeroPart>();
                        if (up == null || (UnitPart)G(f, "part") != up) { bad.Add(f.name + " not on its part"); continue; }
                        var mc = up.GetComponent<MeshCollider>();
                        var b = mc != null ? mc.bounds : new Bounds(up.transform.position, Vector3.zero);
                        b.Expand(0.05f);
                        if (!b.Contains(f.transform.position)) bad.Add($"{f.name} origin outside its part {inst.transform.InverseTransformPoint(f.transform.position).ToString("F1")}");
                        if ((float)G(f, "ignitionGMin") > 45f) bad.Add(f.name + " light-aircraft settings");
                    }
                    string[] must = { "wing_inner_L", "wing_mid_L", "wing_outer_L", "wing_inner_R", "wing_mid_R", "wing_outer_R", "nacelle_1", "nacelle_2", "nacelle_3", "nacelle_4", "B17G", "fus_waist" };
                    foreach (var mn in must) if (!fuel.Any(f => f.name.Replace("(Clone)", "") == mn)) bad.Add("no tank on " + mn);
                    var wi = fuel.FirstOrDefault(f => f.name == "wing_inner_L");
                    var links = wi != null ? ((FuelTank[])G(wi, "connectedTanks")).Select(x => x.name).ToList() : new List<string>();
                    if (!(links.Contains("wing_mid_L") && links.Any(x => x.StartsWith("B17G")))) bad.Add("wing_inner_L links " + string.Join("/", links));
                    var dfl = Fld(typeof(UnitPart), "damageEffects");
                    foreach (var ap in inst.GetComponentsInChildren<AeroPart>(true))
                    {
                        var fx = (IList)dfl.GetValue(ap);
                        if (ap.name.StartsWith("prop_") && fx != null && fx.Count > 0) bad.Add(ap.name + " still carries a fire effect");
                        if (ap.name.StartsWith("engine_") && (fx == null || fx.Count == 0)) bad.Add(ap.name + " has no fire effect");
                    }
                    R("fuel 4,600 kg in 12 linked AB-4-style tanks, each on its part at the tank (fire spawn inside the part); engine fire effect on engine_n, none on the props",
                      Mathf.Abs(fuel.Sum(f => (float)G(f, "fuelCapacity")) - FuelKg) < 1f && bad.Count == 0, $"{fuel.Length} tanks {fuel.Sum(f => (float)G(f, "fuelCapacity")):F0} kg; {string.Join("; ", bad.Take(8))}");
                }
                {   // 1.8.5 offline E (in-game 1.8.3 F1): internals look - stock vertex colours kept, drawn with the stock textures on the matte look material
                    bool okL = B25HTools.StockStructure.CheckLook(inst, out string msgL);
                    R("1.8.5 E internals look: every internals submesh carries a stock exterior-structure vertex grey (87-118, alpha 255) and is drawn with <prefix>_structure_look (URP Lit, the stock aircraft_structure_b / _n / _ao textures, neutral light grey, metallic <= 0.15); none left on the reflective stock material",
                        okL, msgL);
                }
                {   // 1.8.3: internals the stock way + the nacelle rebuild kept the 1.8.2 physics
                    var rs_ = inst.GetComponentsInChildren<MeshRenderer>(true);
                    var ourStruct = rs_.Where(r_ => r_.gameObject.layer != 3 && r_.sharedMaterials.Any(m_ => m_ != null && (m_.name == "B17G_structure" || m_.name == "B17G_engine"))).Select(r_ => r_.name).ToList();
                    var stockStruct = rs_.Where(r_ => r_.sharedMaterials.Any(m_ => StockStructure.IsStructMat(m_))).ToList();
                    bool vcolS = stockStruct.All(r_ => { var mm = r_.GetComponent<MeshFilter>().sharedMesh; return mm.colors32.Length == mm.vertexCount; });
                    R("1.8.3 internals: spars, ribs, frames, stringers, engine mounts / accessory sections drawn with the stock aircraft_structure (vertex colour); none left on our structure / engine materials",
                      !StockStructure.Enabled || (ourStruct.Count == 0 && stockStruct.Count >= 20 && vcolS), $"{stockStruct.Count} stock-structure renderers ({stockStruct.Sum(r_ => r_.GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3)} tris); ours left on: {string.Join(", ", ourStruct.Take(6))}");
                    var hs = inst.GetComponentsInChildren<Transform>(true).Where(t_ => t_.name.EndsWith("_hullsrc")).Select(t_ => t_.name).ToList();
                    var engB = EngineNums.Select(en_ => { var ec_ = allParts.FirstOrDefault(p_ => p_.name == "engine_" + en_); var mc_ = ec_ != null ? ec_.GetComponent<MeshCollider>() : null; return mc_ != null ? $"e{en_} {inst.transform.InverseTransformPoint(mc_.bounds.center).ToString("F2")} {mc_.bounds.size.ToString("F2")}" : $"e{en_} ?"; }).ToList();
                    var com182 = new Vector3(0.00f, 0.02f, 0.12f);
                    R("1.8.3 nacelles: no collider-source child left; parts-collider CoM within 3.5 cm of 1.8.2 (0.00, 0.02, 0.12): engine colliders keep the 1.8.2 turbo",
                      hs.Count == 0 && (com - com182).magnitude < 0.035f, $"CoM {com.ToString("F3")}; left: {string.Join(",", hs)}; {string.Join("; ", engB)}");
                }
                {   // 1.8.8 (user 2026-11-08: engine housings / tail): nacelle bodies shaped on our wing from the reference sections (outboard
                    // underside ends y -0.20 = Unity z -0.92, inboard -1.06 = z -1.78); their colliders keep the 1.8.7 nacelle (nacelle_n_hullsrc
                    // baked in, then deleted) so the parts-collider CoM is unchanged; tail: glazed gunner's cab, Cheyenne cover centre z 0.70
                    // (Unity y 0.30), height 0.76 m, the guns in its slots (turret kinematics row)
                    var det = new List<string>(); bool ok = true;
                    foreach (var en_ in EngineNums)
                    {
                        var p_ = allParts.FirstOrDefault(q => q.name == "nacelle_" + en_);
                        var mf_ = p_ != null ? p_.GetComponent<MeshFilter>() : null; var mc_ = p_ != null ? p_.GetComponent<MeshCollider>() : null;
                        if (mf_ == null || mc_ == null || mc_.sharedMesh == null) { ok = false; det.Add($"nacelle_{en_} mesh / collider missing"); continue; }
                        float vis = mf_.sharedMesh.vertices.Min(v => inst.transform.InverseTransformPoint(mf_.transform.TransformPoint(v)).z);
                        float col = mc_.sharedMesh.vertices.Min(v => inst.transform.InverseTransformPoint(mc_.transform.TransformPoint(v)).z);
                        bool outer = en_ == 1 || en_ == 4;
                        bool o_ = outer ? (vis > -1.00f && vis < -0.85f && col < -1.95f) : (vis > -1.85f && vis < -1.70f && col < -2.05f);
                        ok &= o_; det.Add($"n{en_} visible end z {vis:F2}, collider end z {col:F2}{(o_ ? "" : " BAD")}");
                    }
                    var taz = T("tail_az"); var tb = T("tailmantlet_body"); var tg = T("tail_gun");
                    float tz = taz != null ? inst.transform.InverseTransformPoint(taz.position).y : 9f;
                    var tbm = tb != null ? tb.GetComponent<MeshFilter>() : null;
                    var tbv = tbm != null ? tbm.sharedMesh.vertices.Select(v => inst.transform.InverseTransformPoint(tb.TransformPoint(v)).y).ToList() : new List<float> { 0f };
                    float th = tbv.Max() - tbv.Min();
                    int glass = tg != null ? tg.GetComponent<MeshRenderer>().sharedMaterials.Count(m_ => m_ != null && m_.name.ToLower().Contains("glass")) : 0;
                    bool tOk = Mathf.Abs(tz - 0.303f) < 0.02f && Mathf.Abs(th - 0.76f) < 0.06f && glass > 0;
                    det.Add($"tail_az y {tz:F2}, cover height {th:F2}, tail_gun glass submeshes {glass}");
                    R("1.8.8 nacelles + tail: visible nacelle ends at the reference (outer z -0.92, inner -1.78), colliders still the 1.8.7 nacelle; Cheyenne cover at y 0.30 / 0.76 m tall, gunner's cab glazed",
                      ok && tOk, string.Join("; ", det));
                }
                // liveries
                R("AI performance parameters set (1.6.9 / 1.7.8 comment-swallow guard): PIDReferenceAirspeed 85, maxSpeed 100, takeoffSpeed 47, takeoffDistance 1150, minimumRadarAlt, groundTurningRadius 30", prm.PIDReferenceAirspeed == 85f && prm.maxSpeed == 100f && prm.takeoffSpeed == 47f && prm.takeoffDistance == 1150f && prm.minimumRadarAlt == AiMinRadarAlt && prm.groundTurningRadius == 30f, $"{prm.PIDReferenceAirspeed}/{prm.maxSpeed}/{prm.takeoffSpeed}/{prm.takeoffDistance}/{prm.minimumRadarAlt}/{prm.groundTurningRadius}");
                var liv = prm.liveries;
                R("liveries: 2 shared + 2 per faction (8 entries), none of the own ones shared", liv.Count == 8 && liv.Count(l => l.name.StartsWith("USAAF")) == 4 && liv.Where(l => l.name.StartsWith("BDF")).All(l => l.faction == liv[0].faction) && liv.Where(l => l.name.StartsWith("PALA")).All(l => l.faction != liv[0].faction),
                    string.Join(", ", liv.Select(l => l.name + "/" + (l.faction == liv[0].faction ? "BDF" : "PALA"))));
                // references
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
                // round 3 (user: rogue polygons): every exported mesh arrives whole - triangle count per object = the Blender export table
                // (b17g_parts.json, written by export_b17g.py); the stray-geometry scan of the FBX itself is blender/b17g/check_b17g_stray.py
                {
                    var tab = Newtonsoft.Json.Linq.JArray.Parse(File.ReadAllText(Path.Combine(Path.GetDirectoryName(RepoModel), "b17g_parts.json")));
                    var want = tab.Where(r => (int)r["tris"] > 0 && !((string)r["name"]).EndsWith("_hullsrc")).ToDictionary(   // 1.8.8: collider sources are deleted in Unity (8 since 1.8.8)
                        r => (string)r["name"] == "B17G" ? "fus_center" : (string)r["name"], r => (int)r["tris"]);
                    var seen = new HashSet<string>(); var bad = new List<string>(); int cmp = 0;
                    foreach (var mf in inst.GetComponentsInChildren<MeshFilter>(true))
                    {
                        if (mf.sharedMesh == null || mf.name.StartsWith("prop_") || !want.TryGetValue(mf.name, out var wt) || !seen.Add(mf.name)) continue;
                        int got = 0; for (int sm = 0; sm < mf.sharedMesh.subMeshCount; sm++) got += (int)mf.sharedMesh.GetIndexCount(sm) / 3;
                        var stc = mf.transform.Find(mf.name + "_struct");      // 1.8.3: internals moved to the stock-structure child
                        if (stc != null && stc.GetComponent<MeshFilter>() != null) got += stc.GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3;
                        cmp++; if (got != wt) bad.Add($"{mf.name} {got}/{wt}");
                    }
                    R("meshes arrive whole: Unity triangles per object = the Blender export table (no import split / loss; props are rebuilt by the prop code)", bad.Count == 0 && cmp >= want.Count - 30, $"{cmp} of {want.Count} compared; mismatches {string.Join(", ", bad.Take(8))}");
                }
            }
            finally { Object.DestroyImmediate(inst); }
            int w = rows.Max(r => r.name.Length);
            L("CHECK TABLE");
            foreach (var r in rows) L($"  {(r.ok ? "PASS" : "FAIL")}  {r.name.PadRight(w)}  {r.detail}");
            bool all = rows.All(r => r.ok);
            L($"CHECK {(all ? "ALL PASS" : "FAILURES: " + rows.Count(r => !r.ok))} ({rows.Count(r => r.ok)}/{rows.Count})");
            lastCheck = $"{rows.Count(r => r.ok)}/{rows.Count}";
            return all;
        }
        public static string lastCheck = "";
    }
}
