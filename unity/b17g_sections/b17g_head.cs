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
        // 1.9.12 (user: the historical aircraft get an "airbrake" effect WITHOUT airbrake parts; "whenever the throttle is below 5% the airbrakes are on, ground or sky"): the stock
        // Airbrake on the root part, drag only, no transforms (B25HBuild.AddInvisibleAirbrake, called at the end of RootSystems; the MSB-17
        // block of 1.9.2 with the same dragAmount 3.0 on the same airframe size: 1.10 m/s2 at 90 m/s, 0.49 at 60 m/s on 27 t at sea level).
        // No ground gate anywhere; the plugin (AirBrake1912.cs) only widens "throttle == 0" to "throttle under 5 %". false = 1.9.11 (no component).
        const bool InvisibleAirbrake1912 = true;
        const float InvisibleAirbrakeDrag = 3.0f, InvisibleAirbrakeOpenSpeed = 1.0f;

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

