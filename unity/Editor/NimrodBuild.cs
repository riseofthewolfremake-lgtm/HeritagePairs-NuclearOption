// Hawker Nimrod Mk I (Heritage Pairs, third aircraft, jsonKey NIMROD1): builds the Blueprinter prefab + assets from our own
// procedural model (blender/nimrod) into the family addon folder heritage_pairs/nimrod (FamilyBuild.cs).
//
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 NimrodBuild.Build nimrod_build    (build + check + family pack)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 NimrodBuild.Check nimrod_check    (check only)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FamilyBuild.BuildAll family_build (B-25H + GA-25X + Nimrod + pack)
//
// Same rules as B25HBuild.cs: everything is generated at build time from the user's own files; stock components are used only
// as STARTING VALUES (copied onto our own objects, every reference into a stock prefab dropped and re-wired); stock assets that
// stay referenced (audio, effects, the pilot figure, the tac-screen material, HUD prefab, mount placeholders) are Blueprinter
// placeholders the game resolves to its own copies. Design and every value's source: <repo>\docs\nimrod_design.md.
// Helper sections marked "from B25HBuild.cs" are verbatim copies (renamed outputs only), so the B-25H file stays untouched.
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
    public static class NimrodBuild
    {
        // ------------------------------------------------------------------ paths and identity
        const string ModName = "nimrod";
        const string DisplayName = "Hawker Nimrod Mk I";
        const string Version = "1.0.0";
        const string Folder = FamilyBuild.Combined ? FamilyBuild.FamilyRoot + "/nimrod" : "Assets/Blueprinter/Mods/" + ModName;
        const string RepoModel = @"C:\Users\User\Nuclear Option B-25\assets\model_nimrod\nimrod.fbx";
        const string RepoTextures = @"C:\Users\User\Nuclear Option B-25\assets\textures_nimrod";
        const string SrcDir = "Assets/NimrodSource";
        const string DNS = "Assets/Blueprinter/_donotship";
        const string JsonKey = "NIMROD1";
        const string LogPath = @"C:\Users\User\nuclearoption-ref\unitylogs\nimrod_check_table.txt";

        // ------------------------------------------------------------------ feature flags (ON = in the build for the live probe; each restores a plainer variant when false)
        const bool OwnVickersInfo = true;       // own WeaponInfo "Vickers .303" (copy of the stock 7.5 mm LMG info); false = stock Gun7.5mm info
        const bool SyncMuzzlesAhead = true;     // synchroniser: bullet origins 0.19 m ahead of the prop plane (BulletSim Linecasts hit our prop-strike trigger otherwise)
        const bool GunsAirOnlyForAI = false;    // the B-25H's AI strafing guard (minAltitude 150); a light biplane can pull out, so off
        const bool CooperBombs = true;          // own MissileDefinition + bomb prefab + Cooper x2 rack mount; false = no bomb racks
        const bool StockStructure = true;       // 1.8.3 (user: "look at how stock aircraft use internal parts"): our 'structure' submeshes (break faces, engine body, tank) drawn with the stock aircraft_structure (Lit_vertexcolor, vertex colour 92 = stock exterior structure, UV0 = detail x 1.25)
        const bool OwnTailHookMount = true;     // own hook mount (our mesh, stock TailHook values); false = stock TailHook_Multirole1 mount
        const bool AllHangarTypes = true;       // hangar_med, revetment1, shelter1, Cursor LFD, Annex R1-R3 + M, Hyperion R1-R3; false = hangar_med + revetment1 only
        const bool TacScreen = true;            // one compact retrofit tac screen (stock tacScreenDisplay) on the lower panel
        const bool KeepFlareEjector = true;     // as the B-25H: every stock aircraft has one; removing it is untested
        const bool StockHUDExtras = true;       // COIN_HUDExtras (speed/alt/throttle/AoA/fuel/G)
        const float QuiltTiling = 1f;

        // ------------------------------------------------------------------ Nimrod numbers (docs/nimrod_design.md 5; tools/flightmodel/nimrod_fm.py keeps the same values)
        const float WingIncidence = 1.5f;   // deg, wing liftNormal tilt
        const float StabIncidence = -0.5f;
        const float EnginePower = 330e3f;   // W "thrust power" (1.2.1: 300 -> 330 with the absorption-limited prop below; level ~292 km/h)
        // 1.2.1 fixes from the first in-game test (MODLOG "Nimrod Mk I 1.1.0 first in-game test"); each verified live by setf or settled offline
        const float BladeEfficiency = 0.125f; // ConstantSpeedProp.bladeEfficiency (COIN 0.38): the game prop has no induced velocity, so 0.38 gave
                                             // 21.4 kN static (T/W 1.25); 1.2.1's 0.09 measured 10.25 kN and a 148 m roll; 1.2.2 0.125 -> 13.1 kN,
                                             // ~127 m roll, level speed unchanged (power-limited above ~60 m/s; nimrod_fm calibrated to the game)
        const float PropTargetAoA = 8f;      // ConstantSpeedProp.targetAOA, now explicit (COIN 7; the flight model always assumed 8)
        // 1.7.5 (user 11-06: "incapable of turning ... while taxiing"): -30 -> -50. In game 1.7.4: full rudder 6 s at 7 m/s turned 102-111 deg
        // (1.2.1 with mains friction 0.3: 147); the 1.5.5 mains friction 0.20 (nose-over fix) caps the mains' side grip, so the turn came from
        // the tail wheel alone. Live pokes (Maris rwy 0, 7 m/s, full right 6 s): -45 144, -50 159, -60 200 deg; braking unchanged (2.2 m/s2).
        // 1.8.2 (in game 1.8.1: keyboard-rudder take-off 18.8 deg, target <= 15): tail-wheel castering (LandingGear.aligningStrength) 4 -> 8,
        // the FD-32's value since round 9 (taxi, carrier and K92 AI proven with it in game). tools/flightmodel/taildragger_yaw.py (fitted to the
        // keyboard runs of 1.7.13 / 1.8.0 / 1.8.1, ensemble of 36): keyboard median 12.1 -> 2.0 deg, 80 % 44.6 -> 10.1, ground loops 19 -> 3 %;
        // taxi 7 m/s 6 s and the 10 m/s 90 deg turn unchanged in the model (the servo still reaches the lock at taxi speed).
        const float TailAligning = 8f;   // was 4 (1.8.1); false-safe: set 4 for the 1.8.1 behaviour
        const float TailSteeringLock = -40f;   // 1.8.1: -50 -> -40 (taildragger_ground.py: 10 m/s full-rudder turn body slip 45 -> 35 deg with the 0.35 side grip, taxi 7 m/s 6 s 167 deg, no roll-over; -35 gave 30 deg but a wider AI taxi radius at the K92 corner). Was: // tailwheel behind the CG: +30 steered like a nose wheel (reversed); negative = correct sense
        // 1.8.0 (user on 1.7.13: "keep spinning out on runways"; low friction "an excuse more than a fix"): each main wheel is split into the
        // braked LandingGear + an unbraked "grip" LandingGear on the same contact (GripGear.cs). Both run the stock frictionCoef 0.8; the braked one
        // carries MainBrakeShare of the spring, so braking / the brake hold stay 0.8 x 0.25 = 0.20 x load (the 1.7.13 value that passed the deck
        // and full-brake landing probes) while the side grip is the stock 0.8 x load. Moving the CoM was studied and rejected (groundcom.py: the
        // prop pulls at the prop part's CoM, so a lower CoM tips it on a brake run-up, and lowering the thrust too pitches it up in flight).
        const float MainGearFriction = 0.8f;    // 1.8.0: stock; 1.7.13 0.20 (one gear per wheel)
        const float MainBrakeShare = 0.25f;
        // 1.8.1 (in game 1.8.0: Mk I flipped 2/2 under full brakes at 2.8 m/s2, keyboard-rudder take-offs ground-looped, taxi turns rolled onto a
        // wing tip; tools/flightmodel/taildragger_ground.py, validated on the 1.7.13 AND 1.8.0 wheel logs for turns, taxi and braking): the grip
        // leg's own friction 0.20 (side grip 0.8 x 0.25 + 0.20 x 0.75 = 0.35 x load, 1.75x 1.7.13; 0.8 gave 0.51 g lateral = past the 0.5 g
        // roll-over limit of a 1.8 m track under a 1.8 m CoM); rolling resistance moved onto the braked leg (0.20 x 0.25 = the 1.7.13 0.05 x
        // load, absorbed under the braked leg's cap when braking) and none on the grip leg, so full braking is exactly 1.7.13's 0.20 x load.
        const float GripFriction = 0.20f, BrakedRolling = 0.20f, GripRolling = 0f;     // 1.8.0: braked gear's share of the main spring -> braking 0.20 x load
        const bool SplitMainGear = true;        // 1.8.0: false = the 1.7.13 single gear per wheel (then set MainGearFriction 0.20)
        const float MainContactForward = 0f;   // 1.7.13: 0.20 -> 0 (1.7.12 forward ground contact removed with the 0.30 friction; the code path is kept)
        const float MainSideResponse = 1.0f;   // 1.8.0: stock 1 (1.7.13 1.5 on the 0.20 mains; no measurable effect in game)
        // 1.8.8 (user on 1.8.7: line up, full throttle, no input -> the B-17G and both Nimrods veer left or right, "propeller pull is not the
        // cause"): castoring mains (GripGear.Castor; tools/flightmodel/taildragger_track.py). It is not the prop: a gripping wheel AHEAD of the
        // CoM is directionally unstable under LandingGear's side force (627-656); stock tricycles grip behind the CoM and castor the wheel in
        // front (aligningStrength 5). Here the mains are ahead (the CoM sits 0.57-1.06 m behind them) and the tail wheel loses its load at
        // ~23 m/s (1.8.2 logs), leaving ~1 s on the mains alone before they unload. Mirrored stock arrangement: the mains castor within
        // +-MainCastorRange (steeringSpeed 0), the tail wheel stays the locked, gripping wheel. Model (Mk I): no input, 90 % heading 0.24 -> 0.15 deg; gusts (1 m/s + steady +-1) 4.66 -> 2.53 deg (stock CI-22 3.17); wheel-landing roll-out 4.84 -> 0.22 deg; taxi 7 m/s 6 s 166 -> 166 deg. false = the 1.8.7 behaviour.
        const bool MainCastor188 = true;
        const float MainCastorRange = 6f, MainCastorAlign = 5f;
        // pre-1.7.12 note: LandingGear.frictionCoef on the braked mains (0.8 nosed it over; 0.3 still did on landings / spawn: round 9, tan-1(0.20) = 11.3 deg < tail-up CoM angle ~16 deg with the axle 0.15 m forward)
        const bool NoGearSafety = true;      // WeaponMount.GearSafety = false on the gun ammo + Cooper mounts (fixed gear stays LockedExtended)
        const float AlphaLimiter = 15.5f;    // 1.4.2: 15.5 = wing 17.0 with the 1.5 incidence = CLmax (16.5 let the wing reach 18, past it). FBW alpha limiter. It only SCALES a commanded pitch rate (ControlsFilter.FlyByWire.Filter, 0.34.6), using
                                             // the root's (fuselage) AoA: 15.5 deg at the 3-point attitude, wing 17.0 (CLmax at 16.9). 16.5 stays clear
                                             // of the 3-point attitude and starts just past CLmax in the air (1.2.1: 18; 1.1.0: 15). The stick-neutral
                                             // nose drop from 24 m/s in the 1.2.1 test is the tail lifting aerodynamically, NOT this limiter.
        const bool HyperionR2Only = false;   // 1.2.2: offer only hangar_R2 on the Hyperion. R1 / R3 spawns taxi across the deck toward the port side to a
                                             // ski-jump start; the AI hands over to take-off 12 m from the start and, once > width/2 + maxRadius (15 m)
                                             // off the centre line, AIPilotTakeoffState runs full throttle along its velocity (SkiJump branch): one AI
                                             // Nimrod went over the port side in the 1.2.1 test. false = R1-R3 as in 1.2.1
        const int TracerRatio = 3; const float TracerSize = 1.5f;   // explicit tracer settings (stock 12.7 mm: 5 / 1.0)
        const float PropRpm = 1640f;        // 2,600 engine rpm x 0.632 reduction
        const float FuelKg = 165f;          // 50 gal
        const float GunFireRate = 850f;     // rounds/min per gun (synchronised Vickers)
        const int GunRounds = 600;          // per gun
        const float CooperMass = 9.1f;      // kg, 20 lb
        const bool CooperPivotCentred = true;   // 1.4.0: bomb pivot = capsule centre (the lug pivot sat outside its own capsule -> airbursts over land)
        const float CooperYield = 7.3f;         // 1.4.0: stock unguided-bomb rule blastYield = 0.8 x mass (PAB-125 125 kg -> 100, 250 -> 200, 500 -> 400); 1.3.x 4.5
        static Vector3 bombCentre = Vector3.zero;
        const float SpawnLift = 0.03f;      // spawnOffset.y above the level wheel-contact height
        const float NavLightOutboard = 0.40f, NavLightRange = 0.55f;   // 1.3.2 (stock CAS1: 0.40 m outboard of the lens)
        // 1.4.0 (user review 2). Defaults ON because the user asked for each of these; set false to get the 1.3.2 behaviour back.
        const bool NoNavLights = true;          // no Point lights / lit lenses at all ('modern LED nav lights on a 1930s biplane'); the model has period tip lamps
        const bool TailSkid = true;             // tail skid model: gear_tail_wheel is an empty, wheel radius from the contract (contact point unchanged)
        const bool HookVisualAFrame = true;     // functional hook mesh hidden; the A-frame `hook_visual` is driven by B25H.Instruments 1.4.0
        const bool OwnWeaponIcons = true;       // own HUD icons for the Vickers and the Cooper (repo assets/ui/nimrod_icon_*.png)
        // 1.4.1 crash damage: the stock COIN templates have impactDamage.threshold 0 (= no impact damage) on everything but the fuselage, so a
        // 500 km/h dive into the ground only knocked the engine section off. AeroPart.OnCollisionEnter: damage = (impulse / dt / (mass g)
        // - threshold) x multiplier; at hitPoints <= structuralThreshold the part's joints go to 0 and it comes off. Fabric parts weaker
        // than the metal front (stock COIN fuselage 30 / 1).
        const bool CrashImpactDamage = true;
        // 1.9.11 (user: on a carrier lift the FD-32's rudder gets damaged, sometimes it snaps off; the Mk I has the same low rudder, 0.45 m shorter): two stock lifts (hangar_R1 of the Annex and the Hyperion) carry an
        // invisible 'backstop' box behind the spawn point; a low taildragger rudder that reaches back over it lands on it in the spawn drop while the lift starts rising.
        // (a) spawn further forward with the game's own field spawnOffset.z (stock: CI-22 +0.42, helicopters +1.0), so the rudder's aft end is at least 0.3 m AHEAD of both
        //     backstop faces in plan view (LiftSpawn1911.cs measures it against the stock carrier prefabs at build time);
        // (b) the rudder takes no impact damage, exactly as every stock rudder is set (threshold 0, multiplier 0): a touch can no longer destroy a 5 kg part. It still comes
        //     off in a crash through its joints (break force unchanged), through weapon damage, or together with the fin / rear fuselage, which keep their impact damage.
        // false = the 1.9.10 values (spawnOffset.z 0, rudder impact damage as every other airframe part).
        public const bool LiftSpawnFix1911 = true;
        public const float SpawnForward1911 = 0.7f;   // m: at 0 the Mk I's rudder aft end is 0.36 m BEHIND the Annex backstop face and 0.13 m behind the Hyperion one (clear by 0.31 / 0.24 m in height only); +0.7 puts it 0.34 / 0.57 m ahead
        // 1.9.12 (user: the historical aircraft get an "airbrake" effect WITHOUT airbrake parts; "whenever the throttle is below 5% the airbrakes are on, ground or sky"). The stock
        // Airbrake component (opens while ControlInputs.throttle == 0 over 1 / openSpeed s; force = dragAmount x airDensity x V^2 against the
        // velocity of its part's rigidbody) on the root object with an empty transforms array: drag only, nothing moves, nothing to see (the
        // stock UFO carries it the same way; our MSB-17 since 1.9.2). No ground gate anywhere; the plugin (AirBrake1912.cs) only widens "throttle == 0" to
        // "throttle under 5 %". 0.4: 0.49 x V^2 N at sea level = 1.2 kN at 50 m/s, 0.74 m/s2 on the 1,650 kg Mk I (2.4 at 90 m/s). false = 1.9.11.
        public const bool InvisibleAirbrake1912 = true;
        public const float InvisibleAirbrakeDrag = 0.4f, InvisibleAirbrakeOpenSpeed = 1.0f;
        // 1.9.12 (user: naval liveries for both factions): the two entries of nimrod_liveries.json whose file ends in _navy ("BDF Navy Gray",
        // "PALA Navy") are APPENDED after the six 1.9.11 list entries, BDF then PALA (saved missions store the list index: 0-5 must not move).
        // false = they are not imported and not listed (the pack = 1.9.11 even with the entries and PNGs present in the repo).
        public const bool NavalLiveries1912 = true;
        // 1.9.13 (the FD-32 Discord report: upper outer wing panels "shift at the break off points" in rolls / pulls): same airframe layout and joint code
        // as the FD-32 (30 kg wing_upper_C between the root and two 60 kg panels, every joint solverIterations 6); the offline PhysX benches
        // (study\fd32_wingflex_1913*) show the same one-sided hinge, about half the FD-32 value (0.7-1.0 deg at 6-9 g). PartJoint.solverIterations
        // != 6 sets rb.solverIterations of the joint's OWNER (AeroPart.CreateJoints); stock: A-19 wing3 joints 12. true = every joint OWNED by a
        // wing_* part carries WingSolverIterations1913; nothing else changes. false = 1.9.12 (all joints 6).
        public const bool WingSolver1913 = true;
        // 1.9.13 in game (2026-11-16, study\ingame_1913\test): the Mk I itself was flown at 6 and 20 passes only (6.0-6.15 g at ~102 m/s: upper kink
        // 0.50 deg / lower 0.74 deg on 1.9.12 -> under 0.05 deg / 1-2 mm at 20); it was NOT flown at 60 or 100. The pass count follows the FD-32 sweep
        // (FD-32 only, one aircraft, runtime setting on the 20-pass test build): 20 -> 0.41 deg / 18 mm, 60 -> under ~0.04 deg / 1.2 mm, 100 -> 0.00 deg / 0 mm;
        // no frame cost measurable with one aircraft, many aircraft not measured. Velocity iterations stay 1. Round 4 (final): 100.
        public const int WingSolverIterations1913 = 100;
        static bool WingSolverOwner1913(string part) => part.StartsWith("wing_");
        // 1.9.13 final (seam cosmetics, SeamCove1913.cs; same double-skin construction as the FD-32, break planes x = +-0.80 measured on the built
        // prefab): (A) wing_upper_C/L/R_struct triangles at the break planes x = +-0.80 (end faces
        // within 1 mm of the plane; round 5: also the break-seam stringer stubs that cross the cut, 0.4-3.3 mm under the skin, and their end caps)
        // move into a last submesh drawn with NIMROD1_cove; (B) round 5: two dark NIMROD1_cove band halves per cut, all round the aerofoil, no collider,
        // no shadows: the inner half (20 mm inboard to the cut, 4.5 mm under the skin) is a child of wing_upper_C, the outer half (8 mm inboard of
        // the cut under the centre skin to 20 mm outboard, 5.0 mm under) a child of wing_upper_L/R, so each half leaves with its own part when a
        // panel is shot off (round 4 had one band under wing_upper_C: a 20 mm dark lip after a panel loss). No texture, atlas, paint mesh,
        // collider or physics change. false = 1.9.12 meshes.
        public const bool SeamCove1913 = true;
        const float SeamBreakX1913 = 0.80f;
        static readonly string[] LiveryList1911 = { "FAA Silver (1934)", "BDF Matte Gray", "BDF Temperate Camo", "FAA Silver (1934)", "PALA Matte Black", "PALA Desert Camo" };
        static readonly string[] LiveryListNaval1912 = { "BDF Navy Gray", "PALA Navy" };
        static bool IsNaval(string file) => file.EndsWith("_navy");
        const float FabricImpactG = 20f, FabricImpactMult = 1.5f, MetalImpactG = 30f, MetalImpactMult = 1f;

        static readonly BindingFlags BF = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        // ------------------------------------------------------------------ part table
        enum Lift { Own, Wing, Stab, Fin, Hinge }
        class PartSpec
        {
            public string name, parent, mesh, template; public float mass, wingArea, dragArea, dihedral; public int airfoil; public Lift lift; public float joint;
            public PartSpec(string n, string p, string m, string t, float mass, float wa, float da, int af, Lift l, float j, float dih = 0f)
            { name = n; parent = p; mesh = m; template = t; this.mass = mass; wingArea = wa; dragArea = da; airfoil = af; lift = l; joint = j; dihedral = dih; }
        }

        // Masses 1,650 kg (empty 1,410 + pilot + guns + oil; spec gross 1,840 with fuel/ammo/bombs). Areas 25.6 m^2 of wing (27.96 gross;
        // biplane interference). dragArea carries the struts, flying wires and the fixed gear (game drag = 0.25 rho V^2 x dragArea).
        static List<PartSpec> Parts()
        {
            var l = new List<PartSpec>
            {
                new PartSpec("NIMROD1",      null,          "fus_center",   "COIN:COIN",        300, 0.40f, 0.26f, 1, Lift.Own,  0),
                new PartSpec("fus_engine",   "NIMROD1",     "fus_engine",   "COIN:fuselage",    850, 0.20f, 0.14f, 1, Lift.Own,  90000),
                new PartSpec("prop",         "fus_engine",  null,           "COIN:propHub",      50, 0.00f, 0.02f, 1, Lift.Own,  20000),
                new PartSpec("fus_rear",     "NIMROD1",     "fus_rear",     "COIN:tailboom_L",   50, 0.30f, 0.05f, 1, Lift.Own,  50000),
                new PartSpec("wing_upper_C", "NIMROD1",     "wing_upper_C", "COIN:wing1_L",      30, 2.00f, 0.03f, 0, Lift.Wing, 40000, 0f),
                new PartSpec("fin",          "fus_rear",    "fin",          "COIN:vstab1_L",      8, 0.75f, 0.01f, 1, Lift.Fin,  12000),
                new PartSpec("rudder",       "fin",         "rudder",       "COIN:rudder_L",      5, 0.75f, 0.005f, 1, Lift.Hinge, 8000),
            };
            foreach (var s in new[] { "L", "R" })
            {
                l.Add(new PartSpec("wing_upper_" + s, "wing_upper_C",   "wing_upper_" + s, "COIN:wing2_" + s,   60, 5.10f, 0.06f, 0, Lift.Wing,  50000, 1.0f));
                l.Add(new PartSpec("aileron_" + s,    "wing_upper_" + s, "aileron_" + s,   "COIN:aileron_" + s,  5, 1.30f, 0.005f, 2, Lift.Hinge, 15000));
                l.Add(new PartSpec("wing_lower_" + s, "NIMROD1",        "wing_lower_" + s, "COIN:wing3_" + s,   55, 5.40f, 0.12f, 0, Lift.Wing,  50000, 2.0f));
                l.Add(new PartSpec("stab_" + s,       "fus_rear",       "stab_" + s,       "COIN:hstab",        12, 0.85f, 0.01f, 1, Lift.Stab,  15000));
                l.Add(new PartSpec("elevator_" + s,   "stab_" + s,      "elevator_" + s,   "COIN:elevator",      5, 0.80f, 0.005f, 1, Lift.Hinge, 10000));
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

        static void L(string s) { log.Add(s); Debug.Log("[B25H] NIMROD " + s); }

        // =================================================================== entry points
        public static void Build()
        {
            bool ok = BuildAssets();
            if (FamilyBuild.Combined) { FamilyBuild.Pack(); return; }
            Directory.CreateDirectory(@"C:\Users\User\nuclearoption-ref\build\nimrod");
            Blueprinter.ModBuilder.Build(ModName, DisplayName, Version, @"C:\Users\User\nuclearoption-ref\build\nimrod");
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
                root.name = "NIMROD1";
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
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Folder + "/NIMROD1.prefab");
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
            File.WriteAllText(LogPath, $"NIMROD build {DateTime.Now:s}\n");
        }

        static Newtonsoft.Json.Linq.JObject LoadContract()
        {
            var p = Path.Combine(Path.GetDirectoryName(RepoModel), "nimrod_contract.json");
            if (!File.Exists(p)) throw new Exception("no model contract " + p);
            return Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(p));
        }

        static GameObject ImportModel()
        {
            var dst = SrcDir + "/nimrod.fbx";
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
        static readonly string[] TileMats = { "interior", "tube", "alu", "leather", "wood", "prop", "ck_grey", "rubber", "gunmetal", "structure", "fabric_in", "exhaust", "metal_dark" };   // 1.3.0: all from fal tiles; structure / fabric_in (inner skins) / exhaust / metal_dark now tiled
        // 1.3.0 (2026-11-02 rebuild): fal 3D props with their own baked textures (nimrod_pr_<key>_b / _n; material pr_<key> keeps its own UV0)
        static readonly string[] PropMats = { "pr_vickers", "pr_exhaust", "pr_hook", "pr_wheel", "pr_tailwheel", "pr_pedals", "pr_cooper" };
        // cockpit v2 (blender/nimrod/nimrod_ck_layout.py TILE_SCALE / TILE_PBR): name -> (tiling, metallic, smoothness)
        static readonly Dictionary<string, (float scale, float met, float sm)> CockpitTiles = new Dictionary<string, (float, float, float)> {
            { "ck_paint", (4f, 0.15f, 0.40f) }, { "ck_crinkle", (8f, 0.10f, 0.30f) }, { "ck_brass", (8f, 0.90f, 0.62f) }, { "ck_leather", (6f, 0f, 0.45f) },
            { "ck_wood", (4f, 0f, 0.55f) }, { "ck_floor", (4f, 0f, 0.20f) }, { "ck_alu", (4f, 0.85f, 0.55f) }, { "ck_tube", (8f, 0.35f, 0.40f) },
            { "ck_canvas", (10f, 0f, 0.10f) }, { "ck_red", (6f, 0.05f, 0.50f) }, { "ck_lining", (4f, 0f, 0.15f) }, { "ck_rubber", (8f, 0f, 0.25f) } };
        const bool CockpitV2 = true;            // cockpit v2 materials (tiles + ck_art atlas); the v2 FBX needs them
        static readonly List<(string file, string label, string faction, bool both)> Liveries = new List<(string, string, string, bool)>();
        static readonly Dictionary<string, Texture2D> tex = new Dictionary<string, Texture2D>();

        static void LoadLiveryTable()
        {
            Liveries.Clear();
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(Path.Combine(RepoTextures, "nimrod_liveries.json")));
            foreach (var kv in jo)
            {
                var e = (Newtonsoft.Json.Linq.JObject)kv.Value;
                var file = Path.GetFileNameWithoutExtension((string)e["texture"]);
                if (IsNaval(file) && !NavalLiveries1912) { L($"livery table: {file} skipped (NavalLiveries1912 off)"); continue; }
                Liveries.Add((file, (string)e["name"], ((string)e["faction"]).ToUpperInvariant().Contains("PALA") ? "PALA" : "BDF", e["both"] != null && (bool)e["both"]));
                L($"livery table: {file} '{(string)e["name"]}' ({(string)e["faction"]}{(e["both"] != null && (bool)e["both"] ? ", both factions" : " only")})");
            }
        }

        static void ImportTextures()
        {
            tex.Clear();
            LoadLiveryTable();
            var want = SkinMaps.Select(m => "nimrod_skin_" + m).Concat(Liveries.Select(l => l.file)).Concat(new[] { "nimrod_gauges" })
                .Concat(TileMats.SelectMany(t => new[] { $"nimrod_tile_{t}_b", $"nimrod_tile_{t}_n" }))
                .Concat(PropMats.SelectMany(t => new[] { $"nimrod_{t}_b", $"nimrod_{t}_n" })).ToList();
            if (CockpitV2) want.AddRange(CockpitTiles.Keys.SelectMany(t => new[] { $"nimrod_tile_{t}_b", $"nimrod_tile_{t}_n" }).Concat(new[] { "nimrod_ckart_b", "nimrod_ckart_n" }));
            foreach (var n in want)
            {
                var src = Path.Combine(RepoTextures, n + ".png");
                if (!File.Exists(src)) throw new Exception("missing texture " + src + " (run blender/nimrod/run_nimrod.py)");
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
            foreach (var n in new[] { "COIN", "CAS1", "gun_12.7mm_internal", "TailHook_Multirole1", "bomb_125_1", "bomb_125_double" })
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
            var paint = new Material(skin) { name = "NIMROD1_paint" };
            paint.SetTexture("_Basecolor", tex["nimrod_skin_b"]);
            paint.SetTexture("_Normal", tex["nimrod_skin_n"]);
            paint.SetTexture("_Metallic", tex["nimrod_skin_m"]);
            paint.SetTexture("_AO", tex["nimrod_skin_ao"]);
            paint.SetTexture("_BasecolorDmg", tex["nimrod_skin_dmg_b"]);
            paint.SetTexture("_NormalDmg", tex["nimrod_skin_dmg_n"]);
            paint.SetTexture("_Livery", tex["nimrod_skin_b"]);
            paint.SetFloat("_Glossiness", 0.45f);
            paint.SetFloat("_HitPoints", 100f);
            Save(paint, "paint");
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            if (lit == null) throw new Exception("URP Lit shader not found");
            foreach (var t in TileMats)
            {
                float met = t == "alu" ? 0.85f : t == "gunmetal" ? 0.8f : t == "tube" ? 0.5f : t == "structure" ? 0.5f : t == "metal_dark" ? 0.6f : t == "exhaust" ? 0.5f : 0.05f,
                      sm = t == "alu" ? 0.6f : t == "prop" ? 0.65f : t == "wood" ? 0.6f : t == "gunmetal" ? 0.55f : t == "structure" ? 0.45f : t == "metal_dark" ? 0.45f : t == "exhaust" ? 0.3f : t == "fabric_in" ? 0.15f : 0.3f;
                Save(Tiled(LitMat(lit, "NIMROD1_" + t, Color.white, met, sm), $"nimrod_tile_{t}_b", $"nimrod_tile_{t}_n"), t);
            }
            if (CockpitV2)
            {
                foreach (var kv in CockpitTiles)
                {
                    var tm = Tiled(LitMat(lit, "NIMROD1_" + kv.Key, Color.white, kv.Value.met, kv.Value.sm), $"nimrod_tile_{kv.Key}_b", $"nimrod_tile_{kv.Key}_n");
                    tm.SetTextureScale("_BaseMap", new Vector2(kv.Value.scale, kv.Value.scale)); tm.SetTextureScale("_MainTex", new Vector2(kv.Value.scale, kv.Value.scale));
                    Save(tm, kv.Key);
                }
                Save(Tiled(LitMat(lit, "NIMROD1_ck_art", Color.white, 0.1f, 0.45f), "nimrod_ckart_b", "nimrod_ckart_n"), "ck_art");
            }
            Save(LitMat(lit, "NIMROD1_cove", new Color(0.045f, 0.045f, 0.048f), 0f, 0.1f), "cove");   // 1.3.1: hinge coves, control-surface fronts (dark matte)
            foreach (var pm in PropMats)
                Save(Tiled(LitMat(lit, "NIMROD1_" + pm, Color.white, pm == "pr_vickers" ? 0.6f : pm == "pr_wheel" || pm == "pr_tailwheel" ? 0.1f : 0.35f, 0.45f), $"nimrod_{pm}_b", $"nimrod_{pm}_n"), pm);
            Save(LitMat(lit, "NIMROD1_radiator", new Color(0.10f, 0.10f, 0.09f), 0.6f, 0.4f), "radiator");
            Save(LitMat(lit, "NIMROD1_spinner", new Color(0.75f, 0.76f, 0.78f), 0.85f, 0.7f), "spinner");
            Save(LitMat(lit, "NIMROD1_hookyellow", new Color(0.80f, 0.62f, 0.08f), 0.1f, 0.5f), "hookyellow");
            Save(LitMat(lit, "NIMROD1_brass", new Color(0.72f, 0.52f, 0.20f), 0.9f, 0.7f), "brass");
            Save(LitMat(lit, "NIMROD1_red", new Color(0.55f, 0.06f, 0.04f), 0.1f, 0.5f), "red");
            Save(LitMat(lit, "NIMROD1_ck_black", new Color(0.025f, 0.025f, 0.028f), 0.2f, 0.45f), "ck_black");
            Save(LitMat(lit, "NIMROD1_bomb", new Color(0.20f, 0.22f, 0.14f), 0.3f, 0.5f), "bomb");
            Save(LitMat(lit, "NIMROD1_bombband", new Color(0.80f, 0.62f, 0.08f), 0.1f, 0.5f), "bombband");
            var gauges = LitMat(lit, "NIMROD1_gauges", Color.white, 0f, 0.6f);
            gauges.SetTexture("_BaseMap", tex["nimrod_gauges"]); gauges.SetTexture("_MainTex", tex["nimrod_gauges"]);
            Save(gauges, "gauges");
            Save(LitMat(lit, "NIMROD1_navlight", new Color(0.3f, 0.3f, 0.3f), 0f, 0.8f), "navlight");
            Save(LitMat(lit, "NIMROD1_navred", new Color(0.55f, 0.03f, 0.02f), 0f, 0.9f), "navred");       // 1.4.0 period lamp glass, not emissive
            Save(LitMat(lit, "NIMROD1_navgreen", new Color(0.03f, 0.42f, 0.10f), 0f, 0.9f), "navgreen");
            Save(LitMat(lit, "NIMROD1_screen", Color.black, 0f, 0.5f), "screen");
            var glass = new Material(Asset<Material>("Material/COIN_glass_PLACEHOLDER.mat")) { name = "NIMROD1_glass" };
            Save(glass, "glass");
            var glassInt = new Material(Asset<Material>("Material/COIN_glass_int_PLACEHOLDER.mat")) { name = "NIMROD1_glass_int" };
            Save(glassInt, "glass_int");
            // prop blur: our 2-blade atlas (texture build), stock CI-22 disc material settings, alpha in the texture (B-25H 1.1.0 fix)
            var disc = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "NIMROD1_propdisc" };
            var bp = $"{Folder}/Textures/nimrod_propblur.png";
            File.Copy(Path.Combine(RepoTextures, "nimrod_propblur.png"), bp, true); AssetDatabase.ImportAsset(bp, ImportAssetOptions.ForceUpdate);
            var bti = (TextureImporter)AssetImporter.GetAtPath(bp); bti.alphaIsTransparency = true; bti.wrapMode = TextureWrapMode.Clamp; bti.SaveAndReimport();
            var blur = AssetDatabase.LoadAssetAtPath<Texture2D>(bp);
            disc.SetTexture("_BaseMap", blur); disc.SetTexture("_MainTex", blur);
            disc.SetTexture("_OcclusionMap", null); disc.DisableKeyword("_OCCLUSIONMAP");
            disc.SetColor("_BaseColor", Color.white); disc.SetColor("_Color", Color.white);
            disc.SetFloat("_Smoothness", 0.63f); disc.SetFloat("_Cull", 0f);
            Save(disc, "propdisc");
            if (StockStructure) mats["structure"] = B25HTools.StockStructure.LookMaterial(Asset<Material>("Material/aircraft_structure_PLACEHOLDER.mat"), Folder, "NIMROD1");
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
            // store meshes (bomb, rack): taken out of the aircraft before anything else
            bombMesh = Find("cooper_bomb").GetComponent<MeshFilter>().sharedMesh; bombMats = Find("cooper_bomb").GetComponent<MeshRenderer>().sharedMaterials;
            if (CooperPivotCentred)
            {
                // 1.4.0 airburst fix: the model's pivot is the suspension lug ON the bomb's top skin, i.e. outside (0.5 mm) its own capsule. Missile.DetectCollisions
                // Linecasts from transform.position along the velocity; once tangible (layer Default, mask ~ExclusionZones) the cast meets the bomb's OWN capsule
                // first whenever the velocity points a little below the nose, and that hit is skipped (attachedRigidbody = own rb, same velocity -> return), so the
                // ground is never seen. The bomb then strikes the terrain physically (no impact fuse path: Missile has no OnCollisionEnter), rebounds, and
                // OpticalSeekerBomb.SlowChecks detonates it near the top of the rebound (armed, speed < 30, radarAlt < 30): 3-5 m above the ground. Over water the
                // sea check (transform.y < sea) comes before the Linecast, so it bursts on the surface. Stock bomb_125_1: capsule centred ON the pivot (inside).
                // Fix: the bomb mesh is re-centred on its bounds centre (pivot = capsule centre, as stock); the rack children carry the offset.
                bombCentre = bombMesh.bounds.center;
                var mc = Object.Instantiate(bombMesh); mc.name = "NIMROD1_cooper_centred";
                mc.vertices = bombMesh.vertices.Select(v => v - bombCentre).ToArray(); mc.RecalculateBounds();
                generatedMeshes.Add(mc); bombMesh = mc;
            }
            rackMesh = Find("cooper_rack").GetComponent<MeshFilter>().sharedMesh; rackMats = Find("cooper_rack").GetComponent<MeshRenderer>().sharedMaterials;
            bombPivot = Find("cooper_bomb").localPosition; rackPivot = Find("cooper_rack").localPosition;
            Object.DestroyImmediate(Find("cooper_bomb").gameObject); Object.DestroyImmediate(Find("cooper_rack").gameObject);

            GameObjectUtility.RemoveMonoBehavioursWithMissingScript(root);
            root.AddComponent<Mirage.NetworkIdentity>();
            var rb = root.AddComponent<Rigidbody>();
            EditorUtility.CopySerialized(tpl["COIN"].GetComponent<Rigidbody>(), rb);
            CloneComp(tpl["COIN"].GetComponent<Aircraft>(), root);

            var specs = Parts();
            foreach (var s in specs) MakePartObject(s);
            foreach (var s in specs) MakeAeroPart(s);
            AddJoints(specs);

            var cockpitGO = parts["NIMROD1"].gameObject;
            controlsFilter = CloneComp(TplComp<ControlsFilter>("COIN:cockpit_F"), cockpitGO);
            weaponManager = CloneComp(TplComp<WeaponManager>("COIN:cockpit_F"), cockpitGO);
            CloneComp(TplComp<AutopilotPlane>("COIN:cockpit_F"), cockpitGO);
            Remap(aircraft); Remap(controlsFilter); Remap(weaponManager);

            ControlSurfaces();
            var gears = Gear();
            Engine();
            Weapons();
            Cockpit();
            RootSystems();
            if (InvisibleAirbrake1912) AddInvisibleAirbrake(parts["NIMROD1"], InvisibleAirbrakeDrag, InvisibleAirbrakeOpenSpeed);
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
            if (s.name == "NIMROD1") go = root;
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
                bool metal = s.name == "NIMROD1" || s.name == "fus_engine";
                S(id, "threshold", metal ? MetalImpactG : FabricImpactG); S(id, "multiplier", metal ? MetalImpactMult : FabricImpactMult);
                if (LiftSpawnFix1911 && s.name == "rudder") { S(id, "threshold", 0f); S(id, "multiplier", 0f); }   // 1.9.11: as every stock rudder
                idf.SetValue(ap, id);
            }
            MeshFilter own = s.name == "NIMROD1" ? Find("fus_center").GetComponent<MeshFilter>()
                : s.lift == Lift.Hinge ? Find(s.name + "_visible").GetComponent<MeshFilter>()
                : s.mesh != null ? go.GetComponent<MeshFilter>() : null;
            if (own != null)
            {
                var mc = go.AddComponent<MeshCollider>();
                mc.sharedMesh = BakeCollider(go.transform, s.name + "_col", own);
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
                    Add(owner, other, other == "NIMROD1" ? bySpec[owner].parent : other, Mathf.Min(bySpec[a].joint == 0 ? 1e6f : bySpec[a].joint, bySpec[b].joint == 0 ? 1e6f : bySpec[b].joint) * 0.3f);
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
                CS("elevator_" + side, "CAS1:elevator_" + side, -26f, 0, 0, 60f);
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

        // ------------------------------------------------------------------ landing gear: two braked mains (fixed) + steerable tailwheel
        class GearSpec { public string strut, wheel, part; public float fold, travel, k, c, maxComp, mass, drag; public bool steer, brake; public float diff; }

        // 1.4.2: the gear broke on every landing. LandingGear.FixedUpdate breaks a leg when compressionDistance > maxCompression; ours was soft
        // (120 kN/m, damping ratio 0.45) and broke at 0.30 of 0.575 m travel (52 %): ~5 m/s sink bottomed it. Stock COIN: 200-250 kN/m,
        // 20 kN s/m, break at 72-83 % of travel. Now main 200 kN/m, 20 kN s/m (damping ratio ~0.8), break at 0.50 m (87 %): peak compression
        // ~0.18 m at 5 m/s sink, 0.26 at 8 m/s; a crash (> ~15 m/s) still breaks it. Tail 120 kN/m, 9 kN s/m, break 0.27 of 0.31 m.
        const float GearMainK = 200000f, GearMainC = 20000f, GearMainMaxComp = 0.50f;
        const float GearTailK = 120000f, GearTailC = 9000f, GearTailMaxComp = 0.27f;

        static List<LandingGear> Gear()
        {
            var list = new List<LandingGear>();
            foreach (var s in new[] { "L", "R" })
                list.Add(MakeGear(new GearSpec { strut = $"gear_main_{s}_strut", wheel = $"gear_main_{s}_wheel", part = "NIMROD1", fold = 0.5f, travel = 0.355f + 0.22f, k = GearMainK, c = GearMainC, maxComp = GearMainMaxComp,
                    mass = 25f, drag = parts["NIMROD1"].dragArea, steer = false, brake = true, diff = s == "L" ? -1f : 1f }, "CAS1:gear_" + s + "_sprung", "COIN:wheel_" + s));
            list.Add(MakeGear(new GearSpec { strut = "gear_tail_strut", wheel = "gear_tail_wheel", part = "fus_rear", fold = 0.5f, travel = 0.11f + 0.20f, k = GearTailK, c = GearTailC, maxComp = GearTailMaxComp,
                mass = 6f, drag = parts["fus_rear"].dragArea, steer = true, brake = false, diff = 0f }, "CAS1:gear_F_sprung", "COIN:wheel_F"));
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
            var hinge = NewGO(g.strut.Replace("_strut", "_hinge"), part.transform, strut.position, part.transform.rotation);
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
            S(lg, "foldDegrees", g.fold); S(lg, "foldSpeed", 15f);
            S(lg, "strutRotationTransform", null); S(lg, "strutRotation", 0f);
            SetSeq(lg, "movingParts", new object[0]);
            S(lg, "steering", g.steer); S(lg, "braked", g.brake);
            S(lg, "steeringLock", g.steer ? TailSteeringLock : 0f);
            if (g.brake) S(lg, "frictionCoef", MainGearFriction);
            if (g.brake) S(lg, "response", MainSideResponse); S(lg, "steeringSpeed", g.steer ? 60f : 0f); S(lg, "aligningStrength", g.steer ? TailAligning : 0f);
            S(lg, "differentialBrakeFactor", g.diff);
            S(lg, "dust", dust);
            S(lg, "gearDoors", new List<LandingGear.GearDoor>());
            L($"gear {g.strut}: r={r:F3} axle={axle.ToString("F3")} travel={g.travel} k={g.k} fold={g.fold} steer={g.steer} brake={g.brake}");
            if (g.brake && SplitMainGear) GripGear.Add(lg, MainBrakeShare, MainGearFriction, GripFriction, BrakedRolling, GripRolling, L);
            if (g.brake && MainCastor188) GripGear.Castor(lg, MainCastorRange, MainCastorAlign, L);     // after the split: the grip leg copies `axle`, not `steering`
            return lg;
        }

        // ------------------------------------------------------------------ engine + propeller (B-25H/CI-22 component path, once)
        static void Engine()
        {
            var startup = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), parts["NIMROD1"].gameObject);
            var eng = parts["fus_engine"].gameObject;
            var turb = CloneComp(TplAudio("COIN:COIN", "cricket_turbine"), eng);
            var te = CloneComp(TplComp<TurbineEngine>("CAS1:engine_L"), eng);
            te.maxRPM = 2600f; te.minRPM = 500f; te.maxPower = EnginePower; te.spoolUpTime = 1.6f; S(te, "startupTime", 5f);
            S(te, "pitch", 0.18f); S(te, "volume", 0.07f);
            S(te, "startupAudio", startup); te.aircraft = aircraft;
            S(te, "heatHazeParticles", new ParticleSystem[0]);
            S(te, "maxFuelConsumption", 0.040f); S(te, "IRMin", 0.6f); S(te, "IRMax", 0.9f);
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
                S(b, "transform", broot.transform); S(b, "liftTransform", lt.transform); S(b, "mass", 12f);
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
            S(csp, "momentOfInertia", 30f); S(csp, "bladeLength", R); S(csp, "hubRadius", 0.22f);
            S(csp, "rpmLimit", PropRpm); S(csp, "nominalPower", EnginePower); S(csp, "propTorqueLimit", 6000f);
            S(csp, "bladeEfficiency", BladeEfficiency); S(csp, "targetAOA", PropTargetAoA);
            S(csp, "propAudio", pa);
            L($"prop: radius {R:F3} m, {blades.Count} blades, rpmLimit {PropRpm}, power {EnginePower / 1000f} kW, hub {hubVis.position.ToString("F3")}");
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
            // ---- Vickers Mk III x2: one Gun, two muzzles (bullet origins ahead of the prop disc), flashes at the trough exits
            var g12 = tpl["gun_12.7mm_internal"].GetComponentInChildren<Gun>(true);
            vickersInfo = Asset<WeaponInfo>("MonoBehaviour/Gun7.5mm_PLACEHOLDER.asset");
            if (OwnVickersInfo)
            {
                vickersInfo = Object.Instantiate(vickersInfo); vickersInfo.name = "NIMROD1_vickers303_info";
                vickersInfo.weaponName = "Vickers .303 Mk III"; vickersInfo.shortName = "VICKERS .303";
                vickersInfo.description = "Two synchronised Vickers Mk III .303 machine guns firing through the propeller arc, 600 rounds each.";
                vickersInfo.muzzleVelocity = 745f; vickersInfo.maxSpeed = 745f; vickersInfo.pierceDamage = 95f; vickersInfo.dragCoef = 0.32f;
                vickersInfo.massPerRound = 0.025f; vickersInfo.boresight = true; vickersInfo.targetRequirements.maxRange = 900f;
                if (GunsAirOnlyForAI) vickersInfo.targetRequirements.minAltitude = 150f;
                // 1.4.0: own HUD icon (stock format 512 x 256, white line drawing on black, muzzle left) drawn from our Vickers model
                if (OwnWeaponIcons) S(vickersInfo, "weaponIcon", ImportRepoSprite(Path.Combine(RepoIcons, "nimrod_icon_vickers.png"), "nimrod_icon_vickers"));
                AssetDatabase.CreateAsset(vickersInfo, Folder + "/NIMROD1_vickers303_info.asset");
            }
            var mL = Find("muzzle_gun_L"); var mR = Find("muzzle_gun_R");
            if (!SyncMuzzlesAhead) { mL.position = Find("flash_gun_L").position; mR.position = Find("flash_gun_R").position; }
            var gunGO = NewGO("guns_vickers", eng.transform, (Find("flash_gun_L").position + Find("flash_gun_R").position) / 2, Quaternion.identity);
            foreach (var a in g12.GetComponents<AudioSource>()) CloneComp(a, gunGO).loop = false;
            var gun = CloneComp(g12, gunGO);
            gun.attachedUnit = aircraft; gun.info = vickersInfo;
            S(gun, "magazineCapacity", GunRounds); S(gun, "magazines", 0); S(gun, "startLoaded", true);
            S(gun, "fireRate", GunFireRate); S(gun, "muzzles", new[] { mL, mR });
            // Gun.SpawnBullet fires EVERY muzzle per shot and decrements bulletsLoaded once (Gun.cs 0.34.6 decompile: foreach muzzles :610,
            // bulletsLoaded-- :732): fireRate 850 = 850 rpm per gun, magazineCapacity 600 = 600 rounds per gun (the HUD counts pairs).
            S(gun, "tracerRatio", TracerRatio); S(gun, "tracerSize", TracerSize);
            S(gun, "recoilTransform", null); S(gun, "spinTransform", null);
            var ps = new List<ParticleSystem>();
            foreach (var fl in new[] { Find("flash_gun_L"), Find("flash_gun_R") }) ps.AddRange(CopyMuzzleParticles(g12, fl));
            S(gun, "muzzleParticles", ps.ToArray());
            var ammoPrefabGO = new GameObject("NIMROD1_internal_ammo");
            var ammoPrefab = PrefabUtility.SaveAsPrefabAsset(ammoPrefabGO, Folder + "/NIMROD1_internal_ammo.prefab");
            Object.DestroyImmediate(ammoPrefabGO);
            var tAmmo = Asset<WeaponMount>("MonoBehaviour/gun_ammo_35mm_720_PLACEHOLDER.asset");
            ammoVickers = Object.Instantiate(tAmmo); ammoVickers.name = "NIMROD1_ammo_vickers";
            ammoVickers.prefab = ammoPrefab; ammoVickers.jsonKey = "NIMROD1_ammo_vickers"; ammoVickers.info = vickersInfo;
            ammoVickers.mountName = "Vickers .303 x2 (600 rpg)"; ammoVickers.ammo = GunRounds; ammoVickers.GunAmmo = true; ammoVickers.mass = 2 * GunRounds * 0.025f;
            if (NoGearSafety) ammoVickers.GearSafety = false;
            AssetDatabase.CreateAsset(ammoVickers, Folder + "/NIMROD1_ammo_vickers.asset");
            Set("Vickers Guns", new[] { ammoVickers }, HP(gunGO.transform, eng, new Weapon[] { gun }));

            // ---- 20 lb Cooper bombs: Cooper x2 rack under each lower wing (objects built here, prefabs saved after the mesh bank)
            if (CooperBombs)
            {
                cooperInfo = Object.Instantiate(Asset<WeaponInfo>("MonoBehaviour/info_bomb_125_1_PLACEHOLDER.asset")); cooperInfo.name = "NIMROD1_cooper_info";
                cooperInfo.weaponName = "20 lb Cooper"; cooperInfo.shortName = "COOPER 20LB";
                cooperInfo.description = "20 lb Cooper light fragmentation bomb, carried in fours under the lower wings of interwar fighters.";
                cooperInfo.massPerRound = CooperMass; cooperInfo.costPerRound = cooperInfo.costPerRound * 0.1f;
                if (OwnWeaponIcons) S(cooperInfo, "weaponIcon", ImportRepoSprite(Path.Combine(RepoIcons, "nimrod_icon_cooper.png"), "nimrod_icon_cooper"));   // 1.4.0 (was the PAB-125 icon)
                AssetDatabase.CreateAsset(cooperInfo, Folder + "/NIMROD1_cooper_info.asset");
                cooperDef = Object.Instantiate(Asset<MissileDefinition>("MonoBehaviour/Bomb_125_1_PLACEHOLDER.asset")); cooperDef.name = "NIMROD1_cooper";
                cooperDef.jsonKey = "NIMROD1_cooper"; cooperDef.unitName = "20 lb Cooper"; cooperDef.code = "COOPER"; ((UnitDefinition)cooperDef).mass = CooperMass;
                cooperDef.unitPrefab = null;
                AssetDatabase.CreateAsset(cooperDef, Folder + "/NIMROD1_cooper.asset");
                bombGO = BuildBombObject();
                mountGO = BuildCooperMountObject();
                cooperMount = Object.Instantiate(Mount("bomb_125_double")); cooperMount.name = "NIMROD1_cooper_x2";
                cooperMount.jsonKey = "NIMROD1_cooper_x2"; cooperMount.info = cooperInfo; cooperMount.mountName = "20 lb Cooper x2";
                if (NoGearSafety) cooperMount.GearSafety = false;
                cooperMount.ammo = 2; cooperMount.mass = 2 * CooperMass + 3f; cooperMount.drag = 0.03f; cooperMount.prefab = null;
                AssetDatabase.CreateAsset(cooperMount, Folder + "/NIMROD1_cooper_x2.asset");
                Set("Bomb Racks", new[] { cooperMount }, HP(Find("hp_bomb_L"), parts["wing_lower_L"]), HP(Find("hp_bomb_R"), parts["wing_lower_R"]));
            }
            else foreach (var n in new[] { "hp_bomb_L", "hp_bomb_R" }) Object.DestroyImmediate(Find(n).gameObject);

            // ---- tail hook (GA-25X pattern)
            var hookT = Find("tailhook");
            if (OwnTailHookMount)
            {
                hookMount = Object.Instantiate(Mount("TailHook_Multirole1")); hookMount.name = "NIMROD1_tailhook";
                hookMount.jsonKey = "NIMROD1_tailhook"; hookMount.mountName = "Arrestor Hook"; hookMount.tailHook = true; hookMount.prefab = null;
                AssetDatabase.CreateAsset(hookMount, Folder + "/NIMROD1_tailhook.asset");
                hookGO = BuildTailHookObject(hookT);
            }
            else { hookMount = Mount("TailHook_Multirole1"); Object.DestroyImmediate(hookT.gameObject); }
            Set("Tail Hook", new[] { hookMount }, HP(Find("hp_tailhook"), parts["NIMROD1"]));

            var all = sets.SelectMany(x => x.hardpoints).OrderByDescending(h => h.transform.position.x).ThenByDescending(h => h.transform.position.z).ToList();
            for (int i = 0; i < all.Count; i++) all[i].HardpointIndex = i;
            weaponManager.hardpointSets = sets.ToArray();
            S(weaponManager, "aircraft", aircraft);
            L($"hardpoint sets: {string.Join(" | ", sets.Select(x => $"{x.name} ({x.hardpoints.Count} hp, {x.weaponOptions.Count - 1} options)"))}");
            L($"guns: muzzles L {mL.position.ToString("F3")} R {mR.position.ToString("F3")}, flashes at {Find("flash_gun_L").position.ToString("F3")}; prop plane z {Find("prop_hub").position.z:F3}");
        }

        // Our bomb: our mesh + the stock PAB-125 component values (Missile, OpticalSeekerBomb, MissileNetworkTransform), references re-wired.
        static GameObject BuildBombObject()
        {
            var t = tpl["bomb_125_1"];
            var go = new GameObject("NIMROD1_cooper") { layer = t.layer };
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
            var go = new GameObject("NIMROD1_cooper_x2");
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
            var go = new GameObject("NIMROD1_tailhook_mount");
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


        // ------------------------------------------------------------------ cockpit, pilot (open cockpit: no canopy; bail-out)
        static readonly List<Pilot> crew = new List<Pilot>();
        static Transform helmetCam;
        static void Cockpit()
        {
            var cp = parts["NIMROD1"];
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
            S(aircraft, "canopies", new Canopy[0]);
            L($"pilot eye {cam.position.ToString("F3")} vs cockpit_eye {eye.position.ToString("F3")}");

            // cockpit-layer copies (the cockpit camera's near plane; exterior originals hidden in cockpit view)
            var cockpitR = new List<Renderer>(); var exteriorR = new List<Renderer>();
            var copyNames = new List<string> { "cockpit_interior", "cockpit_seat", "cockpit_stick", "cockpit_rudderbar", "cockpit_throttle", "mfd_center", "fus_center", "fus_engine", "sight_ringbead" };
            copyNames.AddRange(root.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.StartsWith("gauge_")).Select(m => m.name));
            copyNames.AddRange(root.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.StartsWith("cockpit_") && !m.name.EndsWith("_int")).Select(m => m.name));   // cockpit v2 props
            foreach (var n in copyNames.Distinct())
            {
                var orig = TryFind(n);
                if (orig == null || orig.GetComponent<MeshRenderer>() == null) continue;
                var src = orig.GetComponent<MeshRenderer>();
                var copy = NewGO(n + "_int", orig, orig.position, orig.rotation, 3);
                copy.AddComponent<MeshFilter>().sharedMesh = orig.GetComponent<MeshFilter>().sharedMesh;
                var cr = copy.AddComponent<MeshRenderer>();
                cr.sharedMaterials = src.sharedMaterials.Select(m => m == mats["glass"] ? mats["glass_int"] : m).ToArray();
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

            // compact retrofit tac screen (stock tacScreenDisplay, map + 3 upright panels as on the B-25H)
            Renderer tacR = null;
            var mfd = TryFind("mfd_center");
            if (TacScreen && mfd != null)
            {
                var tacMat = Asset<Material>("Material/tacScreenDisplay_PLACEHOLDER.mat");
                foreach (var r in mfd.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.transform == mfd || r.name == "mfd_center_int"))
                {
                    var mf = r.GetComponent<MeshFilter>();
                    mf.sharedMesh = TacScreenMesh(mf.sharedMesh, r.name + "_tac");
                    r.sharedMaterials = new[] { tacMat, mats["screen"] };
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                }
                tacR = mfd.GetComponent<MeshRenderer>();
                L("screen: mfd_center = tacScreenDisplay (map + 3 upright side panels)");
            }
            else
            {
                var screen = NewGO("screen_dummy", cp.transform, Find("cockpit_eye").position + new Vector3(0, -0.6f, 0.5f), Quaternion.identity, 3);
                screen.AddComponent<MeshFilter>().sharedMesh = QuadMesh("screen_dummy", 0.01f, 0.01f);
                var sr = screen.AddComponent<MeshRenderer>(); sr.sharedMaterial = mats["screen"]; sr.enabled = false;
                tacR = sr;
            }

            // Cockpit component: stick (Cockpit.Joystick), throttle lever (Cockpit.Throttle rotation), rudder bar (ControlSurface yaw)
            var interior = Find("cockpit_interior").gameObject;
            var ck = CloneComp(TplComp<global::Cockpit>("COIN:cockpit_F_interior"), interior);
            S(ck, "tacScreenRender", tacR); S(ck, "aircraft", aircraft);
            S(ck, "engineSources", new[] { parts["fus_engine"].gameObject });
            var js = NewElem(ck, "joysticks"); S(js, "transform", DrivenFrame(Find("cockpit_stick"))); S(js, "range", 14f);
            SetSeq(ck, "joysticks", new[] { js });
            var th = NewElem(ck, "throttles"); S(th, "rotation", true); S(th, "motion", false); S(th, "transform", DrivenFrame(Find("cockpit_throttle"))); S(th, "range", 40f);
            SetSeq(ck, "throttles", new[] { th });
            var tplCS = TplComp<ControlSurface>("CAS1:elevator_L");
            var rbT = TryFind("cockpit_rudderbar");      // 1.4.0: removed from the model (user review 2: no pedals in any of the three aircraft)
            if (rbT != null)
            {
                var cs = rbT.gameObject.AddComponent<ControlSurface>(); EditorUtility.CopySerialized(tplCS, cs); Remap(cs);
                S(cs, "pitchRange", 0f); S(cs, "rollRange", 0f); S(cs, "yawRange", -15f); S(cs, "brakeRange", 0f);
                S(cs, "attachedSurface", cp); S(cs, "visibleMesh", rbT.gameObject); S(cs, "flap", false); S(cs, "servoSpeed", 90f);
                S(cs, "splitDrag", 0f); S(cs, "maxSplit", 0f); S(cs, "yawSplitFactor", 0f); S(cs, "splitUpper", null); S(cs, "splitLower", null); S(cs, "splitSound", null);
            }
            L($"cockpit: stick (Joystick 14), throttle (rotation 40), rudder bar {(rbT != null ? "yaw -15" : "none (1.4.0)")}, {cockpitR.Count} cockpit-layer copies");

            // target camera + laser designator (systems the HUD / tac screen expect) on the engine section
            var nose = parts["fus_engine"];
            var tcF = NewGO("targetCamForward", nose.transform, new Vector3(0, -0.55f, 1.85f), Quaternion.identity, 0);
            var tcR = NewGO("targetCamRear", parts["fus_rear"].transform, new Vector3(0, 0.30f, -4.95f), Quaternion.LookRotation(Vector3.back), 0);
            var tcL = NewGO("landingCamPoint", nose.transform, new Vector3(0, -0.75f, 1.5f), Quaternion.LookRotation(new Vector3(0, -0.3f, 1f)), 0);
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

        // 1.9.12: the stock Airbrake on the root object, drag only (the block the MSB-17 has shipped since 1.9.2, every field set: no
        // transforms, maxAngle 0, no sound, empty constraints array (Airbrake.Update iterates it: it must not be null), aircraft set)
        static void AddInvisibleAirbrake(AeroPart rootPart, float drag, float openSpeed)
        {
            var ab = root.AddComponent<global::Airbrake>();
            S(ab, "transforms", new Transform[0]); S(ab, "dragAmount", drag); S(ab, "maxAngle", 0f); S(ab, "openSpeed", openSpeed);
            S(ab, "part", rootPart); S(ab, "airbrakeSound", null); S(ab, "constraints", new UnityEngine.Animations.AimConstraint[0]);
            S(ab, "volumeMultiplier", 0f); S(ab, "aircraft", aircraft);
            L($"1.9.12 invisible airbrake: stock Airbrake on the root, part {rootPart.name}, dragAmount {drag} (rho V^2: {drag * 1.225f * 50f * 50f / 1000f:F2} kN at 50 m/s SL), no transforms, opens at throttle 0 in {1f / openSpeed:F1} s");
        }

        // 1.9.12 check row: "" when the prefab carries exactly the airbrake the flag asks for (on: ONE Airbrake in the whole prefab, on the
        // root object, values, part = the root part, constraints not null; off: none at all), else what is wrong
        static string InvisibleAirbrakeProblems(GameObject inst, bool on, float drag, float openSpeed, out string detail)
        {
            var abs = inst.GetComponentsInChildren<global::Airbrake>(true);
            detail = $"{abs.Length} Airbrake component(s)";
            if (!on) return abs.Length == 0 ? "" : "flag off but an Airbrake is present";
            if (abs.Length != 1) return "expected exactly one Airbrake";
            var ab = abs[0]; var bad = new List<string>();
            var tr = G(ab, "transforms") as Transform[]; var cons = G(ab, "constraints") as UnityEngine.Animations.AimConstraint[];
            var part = G(ab, "part") as UnitPart; var rootPart = inst.GetComponent<AeroPart>();
            var snd = G(ab, "airbrakeSound") as AudioSource; var abAc = G(ab, "aircraft") as Aircraft;
            detail = $"on {ab.name}, part {(part != null ? part.name : "null")}, dragAmount {G(ab, "dragAmount")}, maxAngle {G(ab, "maxAngle")}, openSpeed {G(ab, "openSpeed")}, transforms {(tr == null ? "null" : tr.Length.ToString())}, constraints {(cons == null ? "null" : cons.Length.ToString())}, sound {(snd != null ? "set" : "none")}, volumeMultiplier {G(ab, "volumeMultiplier")}, aircraft {(abAc != null ? "set" : "null")}";
            if (ab.gameObject != inst) bad.Add("not on the root object");
            if (!ab.enabled) bad.Add("disabled");
            if (rootPart == null || part != rootPart) bad.Add("part is not the root part");
            if (!Mathf.Approximately((float)G(ab, "dragAmount"), drag)) bad.Add("dragAmount");
            if (!Mathf.Approximately((float)G(ab, "openSpeed"), openSpeed) || openSpeed <= 0f) bad.Add("openSpeed");
            if (!Mathf.Approximately((float)G(ab, "maxAngle"), 0f)) bad.Add("maxAngle");
            if (tr == null || tr.Length != 0) bad.Add("transforms not an empty array");
            if (cons == null) bad.Add("constraints null");
            if (snd != null) bad.Add("sound set");
            if (!Mathf.Approximately((float)G(ab, "volumeMultiplier"), 0f)) bad.Add("volumeMultiplier");
            if (abAc == null || abAc != inst.GetComponent<Aircraft>()) bad.Add("aircraft is not the root Aircraft");
            return string.Join(", ", bad);
        }

        // ------------------------------------------------------------------ root systems
        static void RootSystems()
        {
            var coin = tpl["COIN"];
            var detector = CloneComp(coin.GetComponent<TargetDetector>(), root);
            S(detector, "attachedUnit", aircraft); S(detector, "scanner", parts["NIMROD1"].transform);
            aircraft.EOTS = detector;
            var cap = CloneComp(TplAudio("COIN:COIN", "capacitor"), root);
            var power = CloneComp(coin.GetComponent<PowerSupply>(), root);
            S(power, "powerSources", new[] { parts["fus_engine"].gameObject });
            S(power, "source", cap); S(power, "aircraft", aircraft);
            S(aircraft, "powerSupply", power);
            CloneComp(coin.GetComponent<NuclearOption.NetworkTransforms.AircraftNetworkTransform>(), root);
            var ft = CloneComp(coin.GetComponent<FuelTank>(), parts["fus_engine"].gameObject);
            S(ft, "fuelCapacity", FuelKg); S(ft, "fuelMass", FuelKg); S(ft, "part", parts["fus_engine"]); SetSeq(ft, "connectedTanks", new object[0]);
            var nl = CloneComp(coin.GetComponent<NavLights>(), root);
            var entries = new List<object>();
            // 1.3.2: stock NavLights setup (AssetRipper COIN / CAS1 prefabs): the Point light sits OUTBOARD of the tip lens (COIN 0.15 m,
            // CAS1 0.40 m in x; range 4, intensity 8, near-pure red / green). Here: 0.40 m outboard and range 0.55 m, so it glows on the wing
            // tip and lens only; the aileron hinge slot (>= 0.57 m from the light) gets no light (1.3.1 game test: the 5 m light at the lens lit
            // the slot faces as a red / green line). The emissive lens (stock litMaterial) is unchanged.
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
            // 1.4.0: NavLights stays with an EMPTY list: Aircraft.ToggleNavLights (the nav-light key) looks it up and would throw without it
            SetSeq(nl, "navLights", entries);
            S(nl, "aircraft", aircraft);
            if (KeepFlareEjector)
            {
                var fe = CloneComp(coin.GetComponent<FlareEjector>(), root);
                var pts = new List<object>();
                foreach (var sx in new[] { -1f, 1f })
                {
                    var part = parts["fus_rear"];
                    var g = NewGO("flareEjector_" + (sx < 0 ? "L" : "R"), part.transform, new Vector3(sx * 0.2f, -0.45f, -2.6f), Quaternion.LookRotation(Vector3.down));
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
            S(aircraft, "dopplerSounds", new List<AudioSource> { parts["fus_engine"].GetComponent<AudioSource>(), parts["prop"].GetComponent<AudioSource>() });
            aircraft.maxRadius = 5.6f;
            aircraft.obstacleTop = 1.4f;
        }

        static void FlyByWire(LandingGear mainGear)
        {
            var so = new SerializedObject(controlsFilter);
            void F(string p, float v) { var sp = so.FindProperty("flyByWire." + p); if (sp == null) throw new Exception("no flyByWire." + p); sp.floatValue = v; }
            F("gLimitPositive", 6.0f); F("cornerSpeed", 60f); F("postStallManeuverSpeed", 0f); F("maxRollSpeed", 50f);
            F("takeoffSpeed", 27f); F("pidTransitionSpeed", 55f); F("alphaLimiter", AlphaLimiter);
            // taildragger: every "noseGear" reference (FBW pitch clamp on the ground, the Trim helper) = a main wheel (weight-on-wheels only)
            int n = 0; var it = so.GetIterator();
            while (it.Next(true)) if (it.name == "noseGear" && it.propertyType == SerializedPropertyType.ObjectReference) { it.objectReferenceValue = mainGear; n++; }
            so.ApplyModifiedPropertiesWithoutUndo();
            var ap = parts["NIMROD1"].GetComponent<AutopilotPlane>();
            var so2 = new SerializedObject(ap);
            var rs = so2.FindProperty("forwardFlightController.referenceAirspeed"); if (rs != null) rs.floatValue = 60f;
            var pi = so2.FindProperty("preventInvertedFlight"); if (pi != null) pi.boolValue = false;
            so2.ApplyModifiedPropertiesWithoutUndo();
            L($"FBW: g 6.0, corner 60, alpha limiter {AlphaLimiter}, takeoff 27; noseGear refs -> {mainGear.name} ({n})");
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
        {   // tools/flightmodel/nimrod_fm.py WING_CD / AIL_CD (thick biplane section; struts and wires are in the parts' dragArea)
            var keys = new List<Keyframe>();
            foreach (var (t, v) in pts.Reverse()) if (t > 0f) keys.Add(new Keyframe(-t, v));
            foreach (var (t, v) in pts) keys.Add(new Keyframe(t, v));
            var c = new AnimationCurve(keys.ToArray());
            for (int i = 0; i < c.length; i++) c.SmoothTangents(i, 0f);
            return c;
        }

        static GameObject SaveEverything()
        {
            var bank = Folder + "/Generated/NIMROD1_meshes.asset";
            AssetDatabase.CreateAsset(generatedMeshes[0], bank);
            foreach (var m in generatedMeshes.Skip(1)) AssetDatabase.AddObjectToAsset(m, bank);
            if (hookGO != null)
            {
                var hp = PrefabUtility.SaveAsPrefabAsset(hookGO, Folder + "/NIMROD1_tailhook_mount.prefab");
                Object.DestroyImmediate(hookGO); hookGO = null;
                hookMount.prefab = hp; EditorUtility.SetDirty(hookMount);
            }
            if (bombGO != null)
            {
                var bp = PrefabUtility.SaveAsPrefabAsset(bombGO, Folder + "/NIMROD1_cooper_bomb.prefab");
                Object.DestroyImmediate(bombGO); bombGO = null;
                cooperDef.unitPrefab = bp; EditorUtility.SetDirty(cooperDef);
                cooperInfo.weaponPrefab = bp; EditorUtility.SetDirty(cooperInfo);
                var mp = PrefabUtility.SaveAsPrefabAsset(mountGO, Folder + "/NIMROD1_cooper_x2.prefab");
                Object.DestroyImmediate(mountGO); mountGO = null;
                cooperMount.prefab = mp; EditorUtility.SetDirty(cooperMount);
                L($"Cooper: bomb prefab {AssetDatabase.GetAssetPath(bp)}, mount prefab {AssetDatabase.GetAssetPath(mp)}");
            }

            var coinParams = Asset<AircraftParameters>("MonoBehaviour/COINParameters_PLACEHOLDER.asset");
            var drag = coinParams.airfoils[0].dragCoef;
            var wing = new Airfoil { name = "NIMROD1_RAF28", liftCoef = Mirror(WingCL), dragCoef = WingDragN() };
            var tail = new Airfoil { name = "NIMROD1_tail", liftCoef = Mirror(new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.9f), (-0.45f, -0.8f), (-0.3f, -1.1f), (0f, 0f), (0.3f, 1.1f), (0.45f, 0.8f), (0.785f, 0.9f), (1.571f, 0f), (3.142f, 0f) }), dragCoef = new AnimationCurve(drag.keys) };

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
            // 1.9.12: the 1.9.11 list first, built exactly as before from the entries that are not naval; then the naval entries in file order
            // (BDF, PALA), each for its own faction only. Indexes 0-5 stay what saved missions hold.
            var oldLiv = Liveries.Where(x => !IsNaval(x.file)).ToList();
            foreach (var side in new[] { "BDF", "PALA" })
                foreach (var (file, label, fac, _) in oldLiv.Where(x => x.both).Concat(oldLiv.Where(x => !x.both && x.faction == side)))
                    livs.Add(new AircraftParameters.Livery { name = label, faction = side == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(livGuid[file]) });
            foreach (var (file, label, fac, _) in Liveries.Where(x => IsNaval(x.file)))   // 1.9.12: the naval liveries, appended after the 1.9.11 list
                livs.Add(new AircraftParameters.Livery { name = label, faction = fac == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(livGuid[file]) });

            var prm = Object.Instantiate(coinParams);
            prm.HUDExtras = StockHUDExtras ? Asset<GameObject>("GameObject/COIN_HUDExtras_PLACEHOLDER.prefab") : null;
            prm.name = "NIMROD1_Parameters";
            BuildDiagramSprites();
            prm.StatusDisplay = BuildStatusDisplayPrefab();
            prm.aircraftName = DisplayName; prm.rankRequired = 0;
            var ail = new Airfoil { name = "NIMROD1_aileron", liftCoef = Mirror(AileronCL), dragCoef = DragCurve(AileronCD) };
            prm.airfoils = new[] { wing, tail, ail };   // index 2 = ailerons (1.4.2)
            prm.liveries = livs;
            int nSets = sets.Count;
            NuclearOption.SavedMission.Loadout LO(bool bombs)
            {
                var w = new List<WeaponMount>();
                foreach (var s in sets) w.Add(s.name == "Vickers Guns" ? ammoVickers : s.name == "Tail Hook" ? hookMount : s.name == "Bomb Racks" ? (bombs ? cooperMount : null) : null);
                return new NuclearOption.SavedMission.Loadout { weapons = w };
            }
            prm.loadouts = new List<NuclearOption.SavedMission.Loadout> { new NuclearOption.SavedMission.Loadout { weapons = Enumerable.Repeat<WeaponMount>(null, nSets).ToList() }, LO(false) };
            var std = new List<StandardLoadout> { new StandardLoadout { Name = "Fighter", loadout = LO(false), FuelRatio = 0.8f } };
            if (CooperBombs) std.Add(new StandardLoadout { Name = "Light bombing (Cooper x4)", loadout = LO(true), FuelRatio = 0.8f });
            prm.StandardLoadouts = std.ToArray();
            prm.DefaultFuelLevel = 0.8f;
            prm.aircraftGLimit = 6.0f; prm.PIDReferenceAirspeed = 60f; prm.maxSpeed = 85f; prm.takeoffSpeed = 28f; prm.takeoffDistance = 90f;
            prm.turningRadius = 450f; prm.cornerSpeed = 60f; prm.approachSpeed = 36f; prm.landingSpeed = 30f; prm.shortLandingSpeed = 28f;
            prm.cruiseThrottle = 0.85f; prm.minimumRadarAlt = 60f; prm.groundTurningRadius = 8f;
            AssetDatabase.CreateAsset(prm, Folder + "/NIMROD1_Parameters.asset");

            float total = parts.Values.Sum(p => p.mass);
            var def = Object.Instantiate(Asset<AircraftDefinition>("MonoBehaviour/CI-22_PLACEHOLDER.asset"));
            def.name = "NIMROD1";
            def.jsonKey = JsonKey; def.WorkshopTag = DisplayName; def.unitName = DisplayName; def.code = "NIMROD"; def.bogeyName = "";
            def.description = "Hawker Nimrod Mk I, 1932. The Fleet Air Arm's single-seat carrier fighter, a navalised Fury: Rolls-Royce Kestrel V-12, " +
                "two synchronised Vickers .303 guns firing through the propeller, four 20 lb Cooper bombs under the lower wings and an arrestor hook. " +
                "Light, slow and very agile; it flies from airfields, revetments, shelters and every carrier deck, the Cursor class LFD included.";
            def.length = 8.18f; def.width = 10.26f; def.height = 3.0f; ((UnitDefinition)def).mass = total;
            def.value = 6f; def.radarSize = 0.45f; def.visibleRange = 3500f; def.manpower = 1;
            def.roleIdentity.antiAir = 0.6f; def.roleIdentity.antiSurface = 0.3f;
            float contactH = (float)contract["level_wheel_contact_height"];
            def.spawnOffset = new Vector3(0f, contactH + SpawnLift, LiftSpawnFix1911 ? SpawnForward1911 : 0f);   // 1.9.11: z forward of the hangar's spawn point (was 0)
            def.restRotation = new Vector3(-14f, 0f, 0f);
            def.aircraftParameters = prm;
            def.mapIcon = mapIconSprite; def.mapIconSize = 0.85f; def.mapOrient = true;
            def.aircraftInfo = new AircraftInfo { emptyWeight = 1410f, maxSpeed = 311f, stallSpeed = 100f, maneuverability = 7f, maxWeight = 1840f };
            def.unitPrefab = null;
            AssetDatabase.CreateAsset(def, Folder + "/NIMROD1.asset");
            foreach (var u in root.GetComponentsInChildren<Unit>(true)) u.definition = def;
            root.GetComponent<Rigidbody>().mass = total;
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, Folder + "/NIMROD1.prefab");
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

        // docs/nimrod_design.md 4: every hangar that offers a fixed-wing aircraft; helicopter pads (hangar_F, Destroyer, Frigate, Helipad) excluded
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
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(Path.Combine(RepoTextures, "nimrod_liveries.json")));
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
                    var ag = AtlasGuard1816.Check(inst, mats["paint"], Path.Combine(RepoTextures, "nimrod_atlas_manifest.json"), null);
                    R("1.8.16 livery atlas: UV0 of the paint meshes == the texture manifest (textures painted on this atlas, files unchanged)", ag.Item1, ag.Item2);
                }
                var ac = inst.GetComponent<Aircraft>();
                var aps = inst.GetComponentsInChildren<AeroPart>(true);
                Transform T(string n) => inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == n);
                // propulsion
                var props = inst.GetComponentsInChildren<ConstantSpeedProp>(true);
                var tr = props.Length == 1 ? (Transmission)G(props[0], "transmission") : null;
                var te = tr != null ? tr.GetComponent<TurbineEngine>() : null;
                R("one ConstantSpeedProp, 2 blades, own Transmission + TurbineEngine", props.Length == 1 && ((IList)G(props[0], "blades")).Count == 2 && te != null,
                    props.Length == 1 ? $"blades {((IList)G(props[0], "blades")).Count}, engine {(te ? te.maxPower : 0)} W, rpmLimit {G(props[0], "rpmLimit")}" : $"{props.Length} props");
                R($"engine power 330 kW thrust power, prop rpm 1640, blade efficiency {BladeEfficiency} / AoA 8, blade length 1.6-1.7 m", te != null && Mathf.Abs(te.maxPower - EnginePower) < 1 && Mathf.Abs((float)G(props[0], "rpmLimit") - PropRpm) < 1 && (float)G(props[0], "bladeLength") > 1.6f && (float)G(props[0], "bladeLength") < 1.7f
                    && Mathf.Abs((float)G(props[0], "bladeEfficiency") - BladeEfficiency) < 1e-4f && Mathf.Abs((float)G(props[0], "targetAOA") - PropTargetAoA) < 1e-4f,
                    props.Length == 1 ? $"bladeLength {G(props[0], "bladeLength")}" : "");
                R("prop strike detector: trigger on layer 15", props.Length == 1 && G(props[0], "propStrikeDetector") is PropStrikeDetector d && d.gameObject.layer == 15 && ((Collider)G(props[0], "propDiscCollider")).isTrigger, "");
                R("engine critical parts = engine section + prop", te != null && ((UnitPart[])G(te, "criticalParts")).Select(p => p.name).OrderBy(x => x).SequenceEqual(new[] { "fus_engine", "prop" }), "");
                // guns
                var guns = inst.GetComponentsInChildren<Gun>(true);
                var hub = T("prop_hub");
                var gun = guns.FirstOrDefault(g => g.name == "guns_vickers");
                var muz = gun != null ? (Transform[])G(gun, "muzzles") : new Transform[0];
                R("Vickers: one Gun, 2 muzzles, 850 rpm, 600 rounds, info 'Vickers .303'", guns.Length == 1 && gun != null && muz.Length == 2 && Mathf.Abs((float)G(gun, "fireRate") - GunFireRate) < 1 && (int)G(gun, "magazineCapacity") == GunRounds && gun.info != null && gun.info.weaponName.Contains("Vickers"),
                    gun != null ? $"fireRate {G(gun, "fireRate")}, magazine {G(gun, "magazineCapacity")}, info {gun.info?.name} v0 {gun.info?.muzzleVelocity} pierce {gun.info?.pierceDamage}" : "missing");
                float propZ = hub != null ? hub.position.z : 0f;
                R("synchroniser: bullet origins >= 0.12 m ahead of the prop plane, outside the spinner (r 0.275)", muz.Length == 2 && muz.All(m => m.position.z - propZ >= 0.12f && new Vector2(m.position.x, m.position.y - hub.position.y).magnitude > 0.3f),
                    string.Join(" ", muz.Select(m => $"{m.name} dz {m.position.z - propZ:F3} r {new Vector2(m.position.x, m.position.y - hub.position.y).magnitude:F3}")));
                var wm = inst.GetComponentInChildren<WeaponManager>(true);
                R("hardpoint sets: Vickers Guns, Bomb Racks, Tail Hook", wm.hardpointSets.Select(s => s.name).SequenceEqual(CooperBombs ? new[] { "Vickers Guns", "Bomb Racks", "Tail Hook" } : new[] { "Vickers Guns", "Tail Hook" }),
                    string.Join(" | ", wm.hardpointSets.Select(s => $"{s.name}: {string.Join(",", s.weaponOptions.Where(o => o != null).Select(o => o.jsonKey))}")));
                var ammo = wm.hardpointSets[0].weaponOptions.LastOrDefault();
                R("gun ammo mount: 600 rounds, GunAmmo, own jsonKey, no gear safety", ammo != null && ammo.ammo == GunRounds && ammo.GunAmmo && ammo.jsonKey == "NIMROD1_ammo_vickers" && (!NoGearSafety || !ammo.GearSafety), ammo != null ? $"{ammo.jsonKey} ammo {ammo.ammo} mass {ammo.mass}" : "");
                if (CooperBombs)
                {
                    var cm = wm.hardpointSets[1].weaponOptions.LastOrDefault();
                    var mms = cm != null && cm.prefab != null ? cm.prefab.GetComponentsInChildren<MountedMissile>(true) : new MountedMissile[0];
                    var info = cm?.info;
                    var bp = info != null ? info.weaponPrefab : null;
                    var mis = bp != null ? bp.GetComponent<Missile>() : null;
                    var md = mis != null ? mis.definition as MissileDefinition : null;
                    R("Cooper mount: 2 MountedMissile with our info, 2 racks (one per lower wing), no gear safety", cm != null && mms.Length == 2 && mms.All(m => G(m, "info") == (object)info) && wm.hardpointSets[1].hardpoints.Count == 2 && (!NoGearSafety || !cm.GearSafety),
                        cm != null ? $"{cm.jsonKey} '{cm.mountName}' ammo {cm.ammo} mass {cm.mass}, mounted {mms.Length}" : "missing");
                    R("Cooper bomb prefab: Missile 9.1 kg, blast 7.3 (0.8 x mass), own MissileDefinition NIMROD1_cooper (unitPrefab = this prefab), NetworkIdentity", mis != null && md != null && md.jsonKey == "NIMROD1_cooper" && md.unitPrefab == bp && Mathf.Abs((float)G(mis, "mass") - CooperMass) < 0.01f && bp.GetComponent<Mirage.NetworkIdentity>() != null && bp.GetComponent<OpticalSeekerBomb>() != null,
                        mis != null ? $"mass {G(mis, "mass")} blastYield {G(mis, "blastYield")} def {md?.jsonKey} prefab {AssetDatabase.GetAssetPath(bp)}" : "missing");
                    // 1.4.0 airburst fix: the bomb's transform (DetectCollisions' Linecast origin) must lie INSIDE its own capsule (stock bomb_125_1: centred)
                    var bcc = bp.GetComponent<CapsuleCollider>();
                    Vector3 cpos = bcc != null ? bcc.center : Vector3.one;
                    float axial = bcc != null ? Mathf.Max(Mathf.Abs(cpos.z) - (bcc.height / 2f - bcc.radius), 0f) : 9f;
                    bool pivotInside = bcc != null && new Vector2(cpos.x, cpos.y).magnitude + axial < bcc.radius - 0.01f;
                    R("Cooper: pivot inside its own capsule by > 10 mm (Linecast origin; 1.3.x lug pivot sat outside -> airbursts), yield 7.3, explosion_10kg family, altitude fuse off",
                        pivotInside && Mathf.Abs((float)G(mis, "blastYield") - CooperYield) < 1e-4f && (float)G(bp.GetComponent<OpticalSeekerBomb>(), "altitudeFuseHeight") == 0f,
                        bcc != null ? $"capsule centre {cpos.ToString("F3")} r {bcc.radius} h {bcc.height:F2}; yield {G(mis, "blastYield")}; arm delay {G(bp.GetComponent<OpticalSeekerBomb>(), "armDelay")}" : "no capsule");
                    R("Cooper bomb components wired to the bomb itself (seeker.missile, network transform)", mis != null && G(bp.GetComponent<OpticalSeekerBomb>(), "missile") == (object)mis && bp.GetComponent<NuclearOption.NetworkTransforms.MissileNetworkTransform>().Missile == mis, "");
                    var hpb = wm.hardpointSets[1].hardpoints;
                    R("bomb racks under the lower wings (below the wing, inboard of the struts)", hpb.All(h => h.part.name.StartsWith("wing_lower_") && Mathf.Abs(h.transform.position.x) < 2.2f && h.transform.position.y < -0.5f), string.Join(" ", hpb.Select(h => h.transform.position.ToString("F2"))));
                }
                var hk = wm.hardpointSets.Last().weaponOptions.LastOrDefault();
                var hookTH = hk != null && hk.prefab != null ? hk.prefab.GetComponent<TailHook>() : null;
                // 1.4.0: visible A-frame (hook_visual, child of fus_rear, pivot = contract) and the functional hook mesh not rendered
                var hv = T("hook_visual");
                bool hvOk = hv != null && hv.GetComponent<MeshRenderer>() != null && hv.GetComponentInParent<AeroPart>() != null && hv.GetComponentInParent<AeroPart>().name == "fus_rear";
                bool fnHidden = hookTH == null || hookTH.GetComponentsInChildren<MeshRenderer>(true).Length == 0;
                R("hook: visible A-frame hook_visual on fus_rear; the functional hook mesh is not rendered (1.4.0)", !HookVisualAFrame || (hvOk && fnHidden),
                    hv != null ? $"hook_visual at {hv.position.ToString("F3")}, functional renderers {(hookTH != null ? hookTH.GetComponentsInChildren<MeshRenderer>(true).Length : -1)}" : "hook_visual missing");
                var vInfo = AssetDatabase.LoadAssetAtPath<WeaponInfo>(Folder + "/NIMROD1_vickers303_info.asset");
                var cInfo = AssetDatabase.LoadAssetAtPath<WeaponInfo>(Folder + "/NIMROD1_cooper_info.asset");
                Sprite Icon(WeaponInfo wi) => wi == null ? null : (Sprite)G(wi, "weaponIcon");
                R("own HUD icons (1.4.0): Vickers and Cooper sprites 512 x 256 from our models, not the stock 12.7 mm / PAB-125",
                    !OwnWeaponIcons || (Icon(vInfo) != null && Icon(vInfo).name == "nimrod_icon_vickers" && Icon(vInfo).rect.width == 512 && Icon(cInfo) != null && Icon(cInfo).name == "nimrod_icon_cooper"),
                    $"{Icon(vInfo)?.name} {Icon(vInfo)?.rect.size} / {Icon(cInfo)?.name}");
                R("tail hook: mount.tailHook, prefab TailHook stowed > 0 > deployed", hk != null && hk.tailHook && hookTH != null && (float)G(hookTH, "stowedAngle") > 0f && (float)G(hookTH, "deployedAngle") < 0f,
                    hookTH != null ? $"stowed {G(hookTH, "stowedAngle")} deployed {G(hookTH, "deployedAngle")}" : "missing");
                // 1.2.2 hook: TailHook trails the hook along the cable (ApplyForce), so the line of pull passes the hinge; the hinge is also the Linecast
                // origin and must lie inside the fus_rear collider (a cast starting inside a collider ignores it) and outside the root's
                var hpT = wm.hardpointSets.Last().hardpoints.FirstOrDefault()?.transform;
                var rearC = aps.FirstOrDefault(p => p.name == "fus_rear")?.GetComponent<MeshCollider>();
                var rootC = inst.GetComponent<MeshCollider>();
                if (hpT != null && rearC != null && rootC != null)
                {
                    var hkL = rearC.transform.InverseTransformPoint(hpT.position); var hkR = rootC.transform.InverseTransformPoint(hpT.position);
                    var hkB = rearC.sharedMesh.bounds; var hkO = rootC.sharedMesh.bounds;
                    bool inRear = hkB.Contains(hkL) && hkL.z < hkB.max.z - 0.1f && hkL.y > hkB.min.y + 0.1f && hkL.y < hkB.max.y - 0.1f;
                    bool outRoot = !hkO.Contains(hkR) || hkR.z < hkO.min.z;
                    R("tail hook hinge inside the fus_rear collider bounds (>= 0.1 m in) and aft of the root collider (Linecast origin)", inRear && outRoot,
                        $"hinge {hpT.position.ToString("F3")}; fus_rear bounds z {hkB.min.z:F2}..{hkB.max.z:F2} y {hkB.min.y:F2}..{hkB.max.y:F2}; root min z {hkO.min.z:F2}");
                }
                else R("tail hook hinge inside the fus_rear collider bounds (>= 0.1 m in) and aft of the root collider (Linecast origin)", false, "hook hardpoint / colliders missing");
                // gear
                var lgs = inst.GetComponentsInChildren<LandingGear>(true).Where(g => !g.name.EndsWith(GripGear.Suffix)).ToArray();   // 1.8.0: grip partners checked in their own row
                var lg142 = lgs;
                bool GearOk(LandingGear g)
                {
                    bool tail = IsTailW(g);
                    float mc = System.Convert.ToSingle(G(g, "maxCompression")), k = System.Convert.ToSingle(G(g, "springRate"));
                    return tail ? Mathf.Abs(mc - GearTailMaxComp) < 1e-3f && Mathf.Abs(k - GearTailK) < 1f : Mathf.Abs(mc - GearMainMaxComp) < 1e-3f && Mathf.Abs(k - GearMainK * (SplitMainGear ? MainBrakeShare : 1f)) < 1f;
                }
                R("1.4.2 ailerons use the aileron airfoil (index 2 of 3)", System.Convert.ToInt32(G(parts["aileron_L"], "airfoil")) == 2 && System.Convert.ToInt32(G(parts["aileron_R"], "airfoil")) == 2,
                    $"aileron airfoils {G(parts["aileron_L"], "airfoil")}/{G(parts["aileron_R"], "airfoil")}");
                R("1.4.2 gear: main 200 kN/m breaks at 0.50 m, tail 120 kN/m at 0.27 m", lg142.Length == 3 && lg142.All(GearOk),
                    string.Join(", ", lg142.Select(g => $"{g.name} steer {G(g, "steering")} k {G(g, "springRate")} max {G(g, "maxCompression")} ok {GearOk(g)}")));
                R("crash impact damage (1.4.1): every airframe part has its own impactDamage (fabric 20 g x1.5, metal 30 g x1; 1.9.11: the rudder's is switched off)", !CrashImpactDamage || parts.Where(kv => kv.Key != "prop" && !(LiftSpawnFix1911 && kv.Key == "rudder")).All(kv => { var d = G(kv.Value, "impactDamage"); return d != null && (float)G(d, "threshold") > 0f && (float)G(d, "multiplier") > 0f; }) && parts.Where(kv => kv.Key != "prop").Select(kv => G(kv.Value, "impactDamage")).Distinct().Count() == parts.Count - 1, "");
                R("gear: 2 braked mains (fixed, friction MainGearFriction), 1 steerable tailwheel (lock -30: behind the CG); fold < 1 deg; extendedDrag = part dragArea", lgs.Length == 3 && lgs.Count(g => (bool)G(g, "braked")) == 2 && lgs.Count(g => IsTailW(g)) == 1 && lgs.All(g => (float)G(g, "foldDegrees") < 1f && Mathf.Abs((float)G(g, "extendedDrag") - ((AeroPart)G(g, "attachedPart")).dragArea) < 1e-4f)
                    && lgs.Where(g => IsTailW(g)).All(g => (float)G(g, "steeringLock") < 0f) && lgs.Where(g => (bool)G(g, "braked")).All(g => Mathf.Abs((float)G(g, "frictionCoef") - MainGearFriction) < 1e-4f),
                    string.Join(" | ", lgs.Select(g => $"{g.name} k {G(g, "springRate")} travel {G(g, "suspensionTravel")} part {((AeroPart)G(g, "attachedPart")).name}")));
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
                    R($"1.8.1 split mains: braked leg frictionCoef {MainGearFriction} share {MainBrakeShare} rolling {BrakedRolling} + unbraked grip leg {GripFriction} rolling {GripRolling} on one contact -> braking {MainGearFriction * MainBrakeShare:F2} x load and rolling {BrakedRolling * MainBrakeShare:F2} x load (= 1.7.13), side grip {MainGearFriction * MainBrakeShare + GripFriction * (1 - MainBrakeShare):F2} x load (1.7.13 0.20, 1.8.0 0.80); springs sum to {GearMainK}", !SplitMainGear || (gok && Mathf.Abs(BrakedRolling * MainBrakeShare - 0.05f) < 1e-4f && MainGearFriction * MainBrakeShare + GripFriction * (1 - MainBrakeShare) <= 0.40f), gd);
                }
                R($"1.8.0 mains side response {MainSideResponse} (stock), tail wheel response 1; contact on the tyre",
                    lgs.Where(g => (bool)G(g, "braked")).All(g => Mathf.Abs((float)G(g, "response") - MainSideResponse) < 1e-4f && (Transform)G(g, "castPoint") == ((GameObject)G(g, "bumpStop")).transform) && lgs.Where(g => IsTailW(g)).All(g => Mathf.Abs((float)G(g, "response") - 1f) < 1e-4f),
                    string.Join(", ", lgs.Select(g => $"{g.name} response {G(g, "response")} friction {G(g, "frictionCoef")}")));
                {   // 1.8.8: castoring mains (GripGear.Castor; tools/flightmodel/taildragger_track.py), the tail wheel the only other steering gear (locked sense)
                    bool cok = GripGear.VerifyCastor(inst, MainCastorRange, MainCastorAlign, out string cdet);
                    bool off = inst.GetComponentsInChildren<LandingGear>(true).Where(g => (bool)G(g, "braked")).All(g => !(bool)G(g, "steering"));
                    R($"1.8.8 castoring mains: both braked mains steering + aligningStrength {MainCastorAlign}, steeringSpeed 0, range +-{MainCastorRange} on their own unsprung = axle (identity rotation), grip partners on the same axle and not steering; tail wheel the only other steering gear, lock < 0",
                        MainCastor188 ? cok : off, cdet);
                }
                R($"1.8.2 tail-wheel castering aligningStrength {TailAligning} (the FD-32's value; 1.8.1 4), steeringSpeed 60, lock {TailSteeringLock}",
                    lgs.Where(g => IsTailW(g)).All(g => Mathf.Abs((float)G(g, "aligningStrength") - TailAligning) < 1e-4f && Mathf.Abs((float)G(g, "steeringSpeed") - 60f) < 1e-4f && Mathf.Abs((float)G(g, "steeringLock") - TailSteeringLock) < 1e-4f) && lgs.Count(g => IsTailW(g)) == 1,
                    string.Join(", ", lgs.Where(g => IsTailW(g)).Select(g => $"{g.name} align {G(g, "aligningStrength")} speed {G(g, "steeringSpeed")} lock {G(g, "steeringLock")}")));
                {   // 1.8.5 offline E (in-game 1.8.3 F1): internals look - stock vertex colours kept, drawn with the stock textures on the matte look material
                    bool okL = B25HTools.StockStructure.CheckLook(inst, out string msgL);
                    R("1.8.5 E internals look: every internals submesh carries a stock exterior-structure vertex grey (87-118, alpha 255) and is drawn with <prefix>_structure_look (URP Lit, the stock aircraft_structure_b / _n / _ao textures, neutral light grey, metallic <= 0.15); none left on the reflective stock material",
                        okL, msgL);
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
                        var dmgTex = AssetDatabase.LoadAssetAtPath<Texture2D>(Folder + "/Textures/nimrod_skin_dmg_b.png");
                        var hc = DamageHoles189.Check(Path.Combine(RepoTextures, "nimrod_skin_dmg_b.png"), dmgTex);
                        R("1.8.9 skin damage HOLES: dmg_b alpha opens 5-13 / 10-27 / 15-30 % of the skin at HP 80 / 50 / 0 (stock bands), alpha kept on import", hc.Item1, hc.Item2);
                    }
                    R("1.8.3 internals the stock way: structure submeshes on the stock aircraft_structure (vertex colour 92), engine body + tank in fus_engine_struct, FuelTank on fus_engine (unchanged)",
                        !StockStructure || (stR.Count >= 6 && esTris >= 400 && esCol && fts.Length == 1 && fts[0].gameObject.name == "fus_engine"), $"{stR.Count} renderers with aircraft_structure, fus_engine_struct {esTris} tris colour ok {esCol}, FuelTank on {string.Join(",", fts.Select(f => f.gameObject.name))}");
                    var fp = string.Join("; ", inst.GetComponentsInChildren<AeroPart>(true).OrderBy(p => p.name).Select(p => $"{p.name} {(float)G(p, "mass"):F2}"))
                        + " | " + string.Join("; ", inst.GetComponentsInChildren<LandingGear>(true).OrderBy(g => g.name).Select(g => $"{g.name} k {G(g, "springRate")} c {G(g, "dampingRate")} f {G(g, "frictionCoef")} al {G(g, "aligningStrength")} lock {G(g, "steeringLock")} at {inst.transform.InverseTransformPoint(g.transform.position).ToString("F4")}"));
                    L("1.8.3 ground fingerprint " + fp);
                    R("1.8.3 ground values logged for the 1.8.2 comparison (part masses, every leg's spring / damping / friction / castering / position)", fp.Length > 100, $"{fp.Length} chars (see the log line '1.8.3 ground fingerprint')");
                }
                R("parts mass 1,500-1,650 kg (empty 1,410 + pilot, guns, oil; + gear 56, fuel 165, ammo 30 = ~1,820 gross, spec 1,840)", mass > 1500 && mass < 1650, $"{mass} kg");
                var tlg = lgs.FirstOrDefault(g => IsTailW(g));
                Transform UnsprungT(object lg) { var u = G(lg, "unsprung"); return u is GameObject ug ? ug.transform : u as Transform; }
                var skidT = T("gear_tail_skid");
                R("tail skid (1.4.0): contact radius = contract tail_r (ground attitude unchanged), skid shoe on the unsprung frame, no wheel mesh",
                    !TailSkid || (tlg != null && Mathf.Abs((float)G(tlg, "wheelRadius") - (float)contract["gear"]["tail_r"]) < 1e-4f && skidT != null && skidT.parent == UnsprungT(tlg) && T("gear_tail_wheel").GetComponent<MeshFilter>() == null),
                    tlg != null ? $"r {G(tlg, "wheelRadius")}, skid parent {(skidT != null && skidT.parent != null ? skidT.parent.name : "-")}" : "no tail gear");
                var nls = inst.GetComponentsInChildren<Light>(true).Where(l => l.type == LightType.Point && l.name.StartsWith("navLight")).ToList();
                R("no nav-light Point lights (1.4.0: period lamps only); NavLights present with an empty list (nav-light key safe)",
                    !NoNavLights || (nls.Count == 0 && inst.GetComponentInChildren<NavLights>(true) != null && ((System.Array)G(inst.GetComponentInChildren<NavLights>(true), "navLights")).Length == 0), $"{nls.Count} point lights");
                R("CoM aft of the main axles by 0.2-0.6 m and ahead of the tailwheel (taildragger)", mainZ - com.z > 0.2f && mainZ - com.z < 0.6f && com.z > tailAx.z, $"CoM z {com.z:F3}, main axle z {mainZ:F3}, tail axle z {tailAx.z:F3}");
                float area = aps.Sum(p => (float)G(p, "wingArea"));
                var up = aps.Where(p => p.name.StartsWith("wing_upper")).ToList(); var lo = aps.Where(p => p.name.StartsWith("wing_lower")).ToList();
                Vector3 LP(AeroPart p) { var mc = p.GetComponent<MeshCollider>(); var ln = (Transform)G(p, "liftNormal"); return p.transform.TransformPoint(mc.sharedMesh.bounds.center) + ln.rotation * (Vector3)G(p, "centerOfLift"); }
                float upZ = up.Average(p => LP(p).z), loZ = lo.Average(p => LP(p).z), upY = up.Average(p => LP(p).y), loY = lo.Average(p => LP(p).y);
                R("biplane: upper lift points 0.7-1.0 m ahead (stagger) and 1.3-1.5 m above (gap) the lower", upZ - loZ > 0.7f && upZ - loZ < 1.0f && upY - loY > 1.3f && upY - loY < 1.5f, $"stagger {upZ - loZ:F3}, gap {upY - loY:F3}, total lifting area {area:F2} m^2");
                R("wing areas: upper 14.8 (centre + panels + ailerons) + lower 10.8 = 25.6 m^2", Mathf.Abs(up.Sum(p => (float)G(p, "wingArea")) + aps.Where(p => p.name.StartsWith("aileron")).Sum(p => (float)G(p, "wingArea")) - 14.8f) < 0.2f && Mathf.Abs(lo.Sum(p => (float)G(p, "wingArea")) - 10.8f) < 0.1f, "");
                R("joints: every part joined; strut joints upper <-> lower each side", aps.All(p => p.gameObject == inst || ((PartJoint[])G(p, "joints")).Length > 0) && new[] { "L", "R" }.All(s => ((PartJoint[])G(aps.First(p => p.name == "wing_upper_" + s), "joints")).Any(j => j.connectedPart != null && j.connectedPart.name == "wing_lower_" + s)), $"{aps.Sum(p => ((PartJoint[])G(p, "joints")).Length)} joints");
                {   // 1.9.13 wing joint solver iterations (fails on 1.9.12: every joint 6)
                    var zj = aps.SelectMany(p => ((PartJoint[])G(p, "joints")).Select(j => (owner: p.gameObject == inst ? "NIMROD1" : p.name, j))).ToList();
                    var zWingOwners = new[] { "wing_upper_C", "wing_upper_L", "wing_upper_R", "wing_lower_L", "wing_lower_R" };
                    var zBad = zj.Where(x => x.j.solverIterations != (WingSolver1913 && WingSolverOwner1913(x.owner) ? WingSolverIterations1913 : 6)).Select(x => $"{x.owner}->{(x.j.connectedPart ? x.j.connectedPart.name : "null")} {x.j.solverIterations}").ToList();
                    var zUC = zj.Where(x => x.owner == "wing_upper_C").ToList();
                    bool zOwnersOk = zWingOwners.All(o => zj.Any(x => x.owner == o)) && zj.Where(x => WingSolverOwner1913(x.owner)).All(x => zWingOwners.Contains(x.owner));
                    R($"1.9.13 wing joints: every joint owned by wing_upper_C / wing_upper_L/R / wing_lower_L/R has solverIterations {(WingSolver1913 ? WingSolverIterations1913 : 6)} (AeroPart.CreateJoints -> rb.solverIterations; PhysX solves the aircraft's island at the largest), "
                        + "every other joint 6; wing_upper_C -> NIMROD1 present; 31 joints as in 1.9.12",
                        zBad.Count == 0 && zOwnersOk && zj.Count == 31 && zUC.Any(x => x.j.connectedPart != null && x.j.connectedPart.gameObject == inst),
                        zBad.Count == 0 ? $"{zj.Count(x => x.j.solverIterations != 6)} of {zj.Count} joints at {WingSolverIterations1913}: " + string.Join(", ", zj.Where(x => x.j.solverIterations != 6).Select(x => $"{x.owner}->{x.j.connectedPart.name}")) : "wrong: " + string.Join("; ", zBad.Take(8)));
                }
                {   // 1.9.13 final seam cosmetics (fails on 1.9.12: light end faces, no band)
                    var sIt = inst.GetComponentsInChildren<Transform>(true);
                    Transform sT(string n) => sIt.First(t => t.name == n);
                    var sCove = AssetDatabase.LoadAssetAtPath<Material>($"{Folder}/Materials/NIMROD1_cove.mat");
                    var sStructs = new[] { "wing_upper_C_struct", "wing_upper_L_struct", "wing_upper_R_struct" }.Select(n => sT(n).GetComponent<MeshRenderer>()).ToList();
                    var sStrips = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name.Contains(B25HTools.SeamCove1913.StripSuffix)).ToList();
                    if (SeamCove1913)
                    {
                        var sAll = B25HTools.SeamCove1913.CheckAll(inst.transform, sCove, "NIMROD1_fabric_in", SeamBreakX1913);
                        R("1.9.13 seam cove: wing_upper_C/L/R_struct end faces at x = +-0.80 and the stringer-stub faces / end caps at the cut drawn with NIMROD1_cove (last submesh, material[0] unchanged, none left light); "
                            + "four NIMROD1_cove band halves per aircraft: inner under wing_upper_C (x 0.78-0.80, ends at the cut), outer under wing_upper_L/R (x 0.792-0.82), 3.9-6.5 mm inside the paint skin and enclosed by it, no collider, no shadows",
                            sAll.ok, sAll.msg);
                    }
                    else R("1.9.13 seam cove off: no band, no NIMROD1_cove on the wing struct renderers (= 1.9.12)", sStrips.Count == 0 && sStructs.All(r => !r.sharedMaterials.Contains(sCove)), $"{sStrips.Count} bands");
                }
                // crew, cockpit, HUD
                R("1 pilot (bail-out, no canopy), cockpit view point set", ac.pilots.Length == 1 && !(bool)G(ac.pilots[0], "ejectionSeat") && ac.cockpitViewPoint != null && ((Canopy[])G(ac, "canopies")).Length == 0, $"eye {ac.cockpitViewPoint?.position.ToString("F3")}");
                var cr = (Renderer[])G(ac, "cockpitRenderers");
                R("cockpit-layer copies on layer 3 (cockpit, seat, stick, rudder bar, throttle, gauges, screen, fuselage)", cr.Length >= 20 && cr.All(r => r.gameObject.layer == 3), $"{cr.Length} renderers");
                // 1.2.2: every cockpit-layer (_int) copy sits exactly on its original (same world matrix, same mesh), and no other renderer is on layer 3
                var badInt = new List<string>();
                foreach (var r in cr)
                {
                    var o = r.transform.parent;
                    var mo = o != null ? o.GetComponent<MeshFilter>()?.sharedMesh : null; var mi = r.GetComponent<MeshFilter>()?.sharedMesh;
                    // the tac screen pair (mfd_center / _int) each get their own TacScreenMesh copy (same geometry, "<name>_tac")
                    bool ok = o != null && r.name == o.name + "_int" && mo != null && mi != null && (mi == mo || (mi.name == r.name + "_tac" && mo.name == o.name + "_tac" && mi.vertexCount == mo.vertexCount));
                    if (ok) { var a = r.transform.localToWorldMatrix; var b = o.localToWorldMatrix; for (int i = 0; i < 16 && ok; i++) ok = Mathf.Abs(a[i] - b[i]) < 1e-5f; }
                    if (!ok) badInt.Add(r.name);
                }
                var strayL3 = inst.GetComponentsInChildren<Renderer>(true).Where(r => r.gameObject.layer == 3 && !cr.Contains(r)).Select(r => r.name).ToList();
                R("cockpit-layer copies: each _int copy = its original's mesh and world transform; no other renderer on layer 3 (no fin / tail copy)", badInt.Count == 0 && strayL3.Count == 0 && cr.All(r => !r.name.StartsWith("fin") && !r.name.StartsWith("fus_rear") && !r.name.StartsWith("rudder") && !r.name.StartsWith("stab")),
                    $"{cr.Length} copies; mismatched [{string.Join(", ", badInt)}]; stray layer-3 [{string.Join(", ", strayL3)}]");
                var ck = inst.GetComponentInChildren<global::Cockpit>(true);
                R("Cockpit: joystick (stick) + throttle lever + tac screen renderer with the stock tac material", ck != null && ((IList)G(ck, "joysticks")).Count == 1 && ((IList)G(ck, "throttles")).Count == 1 && G(ck, "tacScreenRender") is Renderer tr2 && tr2.sharedMaterials[0] != null && tr2.sharedMaterials[0].name.Contains("tacScreen"), "");
                var gmov = contract["gauges"].Select(g => (string)g["name"]).ToList();
                var missing = gmov.Where(n => T(n) == null).ToList();
                R("instrument movers present (B25H.Instruments NIMROD1 branch drives them by name)", missing.Count == 0 && gmov.Count >= 11, $"{gmov.Count} movers; missing [{string.Join(", ", missing)}]");
                var prm = ((AircraftDefinition)ac.definition).aircraftParameters;
                R("HUD extras (COIN_HUDExtras), status display, map icon", prm.HUDExtras != null && prm.StatusDisplay != null && ac.definition.mapIcon != null, "");
                // liveries
                var lv = prm.liveries;
                R("liveries: 3 per faction (FAA Silver first for both + 2 faction schemes)", lv.Count(l => l.faction == lv[0].faction) >= 3 && lv.Count >= 6 && lv[0].name.Contains("FAA"), string.Join(", ", lv.Select(l => l.name).Distinct()));
                {   // 1.9.12: saved missions store the list index, so the six 1.9.11 entries keep their indexes; the naval pair is appended
                    var names = lv.Select(l => l.name).ToList();
                    var want = NavalLiveries1912 ? LiveryList1911.Concat(LiveryListNaval1912).ToList() : LiveryList1911.ToList();
                    bool facOk = lv.Count == want.Count && Enumerable.Range(0, lv.Count).All(i => (lv[i].faction == lv[0].faction) == (i < 3 || i == 6));
                    bool refOk = lv.All(l => l.assetReference != null && !string.IsNullOrEmpty(l.assetReference.AssetGUID) && AssetDatabase.LoadAssetAtPath<LiveryData>(AssetDatabase.GUIDToAssetPath(l.assetReference.AssetGUID)) is LiveryData d && d.Texture != null);
                    R(NavalLiveries1912 ? "1.9.12 liveries: indexes 0-5 = the 1.9.11 list (names and factions), 6 'BDF Navy Gray' (BDF), 7 'PALA Navy' (PALA), every entry with a LiveryData + texture"
                                        : "1.9.12 liveries: flag off, the list = the six 1.9.11 entries",
                      names.SequenceEqual(want) && facOk && refOk, string.Join(" | ", names.Select((n, i) => $"{i} {n}")) + (facOk ? "" : "; WRONG faction order") + (refOk ? "" : "; WRONG: an entry without LiveryData / texture"));
                    string abBad = InvisibleAirbrakeProblems(inst, InvisibleAirbrake1912, InvisibleAirbrakeDrag, InvisibleAirbrakeOpenSpeed, out string abDet);
                    string abName = InvisibleAirbrake1912 ? $"exactly one stock Airbrake, on the root object, part = the root part, dragAmount {InvisibleAirbrakeDrag}, openSpeed {InvisibleAirbrakeOpenSpeed}, maxAngle 0, no transforms (drag only, no parts), no sound, constraints not null, aircraft set" : "flag off, no Airbrake in the prefab";
                    R("1.9.12 invisible airbrake: " + abName, abBad == "", abDet + (abBad == "" ? "" : "; WRONG: " + abBad));
                }
                // ours only
                var stockMesh = inst.GetComponentsInChildren<MeshFilter>(true).Where(m => m.sharedMesh != null && !AssetDatabase.GetAssetPath(m.sharedMesh).StartsWith(Folder)).Select(m => m.name).ToList();
                R("every mesh is ours (mesh bank in the mod folder)", stockMesh.Count == 0, string.Join(", ", stockMesh.Take(6)));
                // definition
                var def = (AircraftDefinition)ac.definition;
                R("definition: NIMROD1, 10.26 x 8.18 x 3.0 m, spawn offset = level wheel contact, rest rotation -14", def.jsonKey == JsonKey && Mathf.Abs(def.width - 10.26f) < 0.01f && Mathf.Abs(def.spawnOffset.y - ((float)contract["level_wheel_contact_height"] + SpawnLift)) < 0.001f && def.restRotation.x < -10f,
                    $"spawnOffset {def.spawnOffset.ToString("F3")}, mass {((UnitDefinition)def).mass}");
                {   // 1.9.11 carrier-lift spawn (LiftSpawn1911.cs)
                    var rud = inst.GetComponentsInChildren<AeroPart>(true).FirstOrDefault(p => p.name == "rudder"); var rid = rud != null ? G(rud, "impactDamage") : null;
                    var others = inst.GetComponentsInChildren<AeroPart>(true).Where(p => p.name != "rudder" && p.name != "prop").Select(p => G(p, "impactDamage")).ToList();
                    R("1.9.11 rudder: impact damage off as on every stock rudder (threshold 0, multiplier 0, its own instance); every other airframe part keeps its impact damage; rudder joints unchanged",
                        !LiftSpawnFix1911 || (rid != null && (float)G(rid, "threshold") == 0f && (float)G(rid, "multiplier") == 0f && others.All(o => o != null && !ReferenceEquals(o, rid) && (float)G(o, "threshold") > 0f)),
                        rid != null ? $"rudder {G(rid, "threshold")} x {G(rid, "multiplier")}, mass {rud.mass}, joints {string.Join(" / ", ((PartJoint[])G(rud, "joints")).Select(j => j.breakForce))}; {others.Count} other parts on" : "no rudder");
                    var ls = LiftSpawn1911.Check(inst.transform, rud != null ? rud.transform : null, def.spawnOffset, def.restRotation);
                    R($"1.9.11 spawn: spawnOffset.z {SpawnForward1911} m forward; the rudder's aft end in the spawn pose is at least {LiftSpawn1911.MinMargin} m ahead of the nearest stock lift backstop face (Annex and Hyperion hangar_R1, measured on the stock prefabs)",
                        !LiftSpawnFix1911 || (Mathf.Abs(def.spawnOffset.z - SpawnForward1911) < 1e-5f && def.spawnOffset.x == 0f && ls.Item1), ls.Item2);
                }
                var op = AssetDatabase.LoadAssetAtPath<Blueprinter.OpAddAircraftToHangars>(Folder + "/OpAddAircraftToHangars.asset");
                R($"hangars: medium hangar, revetment, shelter, Cursor LFD, Annex R1-R3 + M, Hyperion {(HyperionR2Only ? "R2 (9" : "R1-R3 (11")} hangar names)", op != null && op.hangars.Sum(h => h.hangarNames.Count) == (AllHangarTypes ? (HyperionR2Only ? 9 : 11) : 2),
                    op != null ? string.Join("; ", op.hangars.Select(h => h.hangarUnitJsonKey + ":" + string.Join(",", h.hangarNames))) : "missing");
                R($"FBW: g 6, corner 60, alpha limiter {AlphaLimiter}", Mathf.Abs(new SerializedObject(inst.GetComponentInChildren<ControlsFilter>(true)).FindProperty("flyByWire.gLimitPositive").floatValue - 6f) < 0.01f
                    && Mathf.Abs(new SerializedObject(inst.GetComponentInChildren<ControlsFilter>(true)).FindProperty("flyByWire.alphaLimiter").floatValue - AlphaLimiter) < 0.01f, "");
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
        const string RepoUI = @"C:\Users\User\Nuclear Option B-25\assets\ui_nimrod";   // no hand art: generated from the model
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
            var art = Directory.Exists(RepoUI) && !File.Exists(Path.Combine(RepoUI, "nimrod_status_layout.json")) ? Directory.GetFiles(RepoUI, "*.png").FirstOrDefault(f => { var n = Path.GetFileName(f).ToLowerInvariant(); return n.Contains("diagram") || n.Contains("status") || n.Contains("damage"); }) : null;
            if (art != null)
            {
                var fitted = FitArt(art, 512, u, BIG);
                if (fitted != null) { bgPx = fitted; L($"status background: texture worker art {Path.GetFileName(art)} (bbox-fitted to the model frame)"); }
            }
            else L("status background: generated line art from the model (no assets/ui diagram art)");
            statusBackground = SaveSprite(bgPx, 512, "nimrod_status", false);

            // one filled sprite per part (256, 2x supersampled)
            const int PB = 512;
            for (short k = 0; k < plist.Count; k++)
            {
                var r = new Raster(PB);
                foreach (var (a, b, c) in PartTriangles(plist[k])) r.Tri(a, b, c, k);
                var px = Downsample(i => r.id[i] >= 0, PB, 2);
                statusParts[plist[k].name] = SaveSprite(px, 256, "nimrod_status_" + plist[k].name, true);
                // centre of the part's own silhouette, for failure indicators
                double sx = 0, sy = 0; int cnt = 0;
                for (int i = 0; i < r.id.Length; i++) if (r.id[i] >= 0) { sx += i % PB; sy += i / PB; cnt++; }
                diagramPos[plist[k].name] = cnt > 0 ? new Vector2((float)(sx / cnt / PB - 0.5), (float)(sy / cnt / PB - 0.5)) : Vector2.zero;
            }

            // map icon: filled silhouette, 256 (texture worker's icon when present)
            var icon = Path.Combine(RepoUI, "nimrod_map_icon.png");
            if (File.Exists(icon)) { mapIconSprite = ImportRepoSprite(icon, "nimrod_mapicon"); L("map icon: texture worker art nimrod_map_icon.png"); }
            else { mapIconSprite = SaveSprite(Downsample(i => u.id[i] >= 0, BIG, 4), 256, "nimrod_mapicon", false); L("map icon: generated silhouette from the model"); }
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
            var inst = new GameObject("NIMROD1_statusDisplay", typeof(RectTransform)) { layer = 5 };
            var rt = (RectTransform)inst.transform;
            rt.anchorMin = rt.anchorMax = new Vector2(1f, 0f); rt.pivot = new Vector2(1f, -0.05f); rt.sizeDelta = new Vector2(300f, 300f); rt.anchoredPosition = new Vector2(0f, -30.1f);
            var list = new List<PartStatusDisplay>();
            var failures = new List<GameObject>();
            UnityEngine.UI.Image rootImg;
            StatusDisplay sd;
            Vector2 V2(Newtonsoft.Json.Linq.JToken t) => new Vector2((float)t[0], (float)t[1]);
            var layoutPath = Path.Combine(RepoUI, "nimrod_status_layout.json");
            var covered = new HashSet<string>();
            if (File.Exists(layoutPath))
            {
                // texture worker's art + layout (assets/ui/nimrod_status_layout.json): stock-style per-part sprites, mirrored L/R
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
            var prefab = PrefabUtility.SaveAsPrefabAsset(inst, Folder + "/NIMROD1_statusDisplay.prefab");
            Object.DestroyImmediate(inst);
            L($"status display prefab: {list.Count} part images, failure indicators {fnames}");
            return prefab;
        }

    }
}
