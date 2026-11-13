// B-25H Mitchell for Nuclear Option: builds the Blueprinter mod `b25h_mitchell` from our own v2 model.
// Since 2026-10-31 it writes into the family addon `heritage_pairs` (subfolder b25h, FamilyBuild.cs); FamilyBuild.Combined = false restores b25h_mitchell.
//
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 B25HBuild.Build b25h_build   (build + check + .nobp)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 B25HBuild.Check b25h_check   (check only)
//
// Everything is generated from the user's own files at build time:
//   - our model:   <repo>\assets\model_v2\b25h_v2.fbx (copied into Assets/B25HSource, which is NOT part of the mod)
//   - our textures <repo>\assets\textures_v2\*.png when present, flat generated colours otherwise
//   - stock game components (AssetRipper placeholders in _donotship) are used only as STARTING VALUES:
//     each component is created fresh on our hierarchy, its serialized values copied from a stock component,
//     every reference into the stock prefab is dropped and re-wired to our own objects. No stock mesh is used
//     on the airframe; stock assets referenced by the mod (audio clips, effect prefabs, weapon mounts, the pilot
//     figure, the tac-screen UI) are placeholders that Blueprinter resolves to the game's own copies at runtime.
// Notes on every value and where it came from: <repo>\docs\b25h_prefab_build.md
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
    public static class B25HBuild
    {
        // ------------------------------------------------------------------ paths and identity
        const string ModName = "b25h_mitchell";
        const string DisplayName = "B-25H Mitchell";
        const string Version = "1.1.1";
        const string Folder = FamilyBuild.Combined ? FamilyBuild.FamilyRoot + "/b25h" : "Assets/Blueprinter/Mods/" + ModName;   // one family addon (FamilyBuild.cs) or the old single addon
        const string OutFolder = @"C:\Users\User\nuclearoption-ref\build\b25h";
        const string RepoModel = @"C:\Users\User\Nuclear Option B-25\assets\model_v2\b25h_v2.fbx";
        const string RepoTextures = @"C:\Users\User\Nuclear Option B-25\assets\textures_v2";
        const string SrcDir = "Assets/B25HSource"; // model import lives outside the mod folder, never shipped
        const string DNS = "Assets/Blueprinter/_donotship";
        const string JsonKey = "B25H";
        const string LogPath = @"C:\Users\User\nuclearoption-ref\unitylogs\b25h_check_table.txt";

        // ------------------------------------------------------------------ feature flags
        // Features the user asked for in the 1.1.0 brief are ON so the game worker can test them; each can be switched off
        // independently if its live probe fails. Speculative extras default OFF.
        // Own WeaponInfo for the 75 mm T13E1 (a copy of the stock 57 mm aerial gun's info with the T13E1/M5 name/ballistics).
        // Off = use the stock Gun57mm_Aerial info unchanged (HUD then says "57mm Cannon").
        const bool OwnCannonWeaponInfo = true;  // ON since 2026-10-30 in-game test (HUD must not show the stock "57mm Cannon")
        // Countermeasures: every stock aircraft has a FlareEjector and the HUD/AI code paths assume a station.
        // A WW2 bomber had none; kept ON (hidden in the nacelles) because removing it is untested.
        const bool KeepFlareEjector = true;
        const bool ANM2Guns = true;              // 1.8.13 (offline L): our own AN/M2 on the turret / waist gun slots (ANM2Gun.cs); false = the stock door-gun barrel
        const bool FireClear1814On = true;       // 1.8.14 (offline M): exclusion FiringCones from a 1 deg bore-line sweep against our own airframe (FireClear1814.cs); false = 1.8.13 cones
        const string FireClearJson = "C:/Users/User/Nuclear Option B-25/assets/model_v2/b25h_fireclear_1814.json";
        // 1.1.0 (brief items 1-10)
        const bool StockHUDExtras = true;      // AircraftParameters.HUDExtras = CI-22's COIN_HUDExtras (speed/alt/throttle/AoA/fuel/G HUD apps)
        const bool OwnPropBlur = true;          // own blur-stage meshes + own blur texture on the prop disc (stock disc swap logic)
        const bool CockpitRebuild = true;        // 2026-11-01 historical B-25 cockpit rebuild: fal art atlas (bk_art), quilted / olive-drab tiles (bk_quilt, bk_od), fal 3D props (pr_<name>, own baked textures). The geometry is in the FBX; false = plain colours on those faces
        const bool WsoScreenTacPage = true;      // 2026-11-01 FIX (same bug as the GA-25X 0.3.2, user-confirmed fixed there): targetCamDisplay on a mesh keeps the render texture's last frame after deselect (TargetCam.CancelTarget only disables the camera; only TacScreen reacts to onCamToggle). mfd_right shows the stock tac screen, whose page shows the target video while a target is selected
        const bool CockpitPropsNoShadow = true; // performance pass 2026-11-01: exterior copies of cockpit-only meshes cast no shadows
        // 1.8.0 (user on 1.7.13: "the B-25H cockpit is much darker than other aircraft"). Same shader as stock cockpits (URP Lit; stock
        // CAS1_cockpit / COIN_cockpit / FastBomber1_cockpit / EW1 / QuadVTOL1 use it with metallic + occlusion maps), same renderer settings
        // (shadows, probes on; ExposureController is per camera, not per aircraft). The difference is albedo: stock cockpit base maps average
        // 0.10-0.14 linear luminance (AssetRipper export, measured), ours 0.05-0.10 (quilt 0.053, olive drab 0.073, panel art 0.095, inner skin
        // 0.088, props 0.06-0.13) and the panel / walls are 4-10 m2 each. CockpitAlbedoTarget lifts each cockpit material by a _BaseColor
        // factor (texture mean measured at build time, capped at CockpitAlbedoMaxGain) so its mean reaches the stock range; the panel black
        // and the instrument art keep their contrast (same factor over the whole map). Metallic on the panel / walls 0.1 -> 0 (stock base 0).
        const bool CockpitBrighten = true;
        // 1.8.1 (in game 1.8.0: cockpit frame brightness B-25H 35.8 vs GA-25X 74.5 / A-19 55.2; hiding canopy_glass gave 32.6 -> 71.8):
        // the exterior canopy_glass (B25H_glass, COIN_glass values) was the one exterior glass NOT in exteriorRenderers, so it was drawn from
        // the pilot's eye. Stock COIN.prefab: canopy_glass_R_exterior / canopyGlass_F_exterior are in exteriorRenderers (hidden in cockpit
        // view) and a *_interior copy on layer 3 is in cockpitRenderers. true = the same: canopy_glass hidden in cockpit view, a cockpit-layer
        // copy with the B-17G / FD-32 faint glass (stock prop-disc transparent Lit, alpha 0.06; COIN_glass_int made our canopy a dark shell
        // on 2026-10-30), and the top hatch copy's glass on that material too. false = 1.8.0.
        const bool CanopyGlassInterior181 = true;
        const float CockpitAlbedoTarget = 0.12f, CockpitAlbedoMaxGain = 2.5f, CockpitBlackSrgb = 0.07f;
        const float QuiltTiling = 5f;           // v3: detail UV = 2 m per unit -> 0.4 m tile, ~10 cm quilt cells (photos); pass 1 had 3
        static readonly string[] PropNames = { "yoke", "column", "throttle", "proplever", "mixture", "trimwheel", "pedal", "seat", "boot", "footrest", "loom" };   // v3: column boot, navigator footrest, wiring looms
        const bool CockpitAnimators = true;     // yoke column / wheel / pedals / throttle levers / needles driven by stock components
        const bool MFDScreens = true;           // stock tac-screen material on the model's screen quads (replaces the hidden dummy screen)
        const bool FiveCrew = true;             // 5 Pilot components, bail-out hatches as stock Canopy components
        const float TailCrewScale = 0.6f;       // tail gunner figure scale about its eye (legs stuck out of the tail cone at 1.0)
        // 1.8.0 (user on 1.7.13: "the AI never uses its cannon or guns on ground targets"; "the A-19 strafes fine"): false. The stock A-19
        // gun info (Gun30mm_Rotary) has targetRequirements.minAltitude 0; the game breaks every gun pass off 2 s before a ground target
        // (AIPilotCombatModes.UseFixedGuns) and keeps the dive between ~6 and 11 deg (climb below 0.1, stop climbing above 0.2 height / distance),
        // so the pull-out needs ~10 m at 3.5 g. The 1.1.0 crashes came from passes begun at 70-150 m AGL with the old 300 m floor; the AI floor
        // stays minimumRadarAlt 450 (BomberAITuning) as the stock way to give a 3.5 g airframe its room. The own infos stay (boresight 75 mm).
        const bool FixedGunsAirOnlyForAI = false; // 1.8.0: false (true = own fixed-gun infos with minAltitude 150: AI guns vs aircraft only)
        const bool TacScreenPanels = true;      // tac screens remapped like COIN_targetScreen: map area upright, the UI's 90-deg-rotated side panels shown upright beside it
        const bool DefensiveTurrets = true;     // 4 built-in turrets (AttackHelo1 chin-turret pattern), stock M2 gun mesh + values
        const bool TurretAntiMissile = false;   // turret WeaponInfo antiMissile 0.05 (stock Gun12.7mm_Rotary). OFF: CombatAI.ChooseHQTarget could then make the AI PILOT pick the turret station against a missile
        const bool NuclearOptions = true;       // GPO-N (1.5 kt) wherever a GPO-500 fits, GPO-2P Auger on bay/racks
        const bool StrategicGPON = false;       // also offer GPO-N (250 kt) - not asked for, off
        const bool OwnStatusDisplay = true;     // own damage diagram (prefab + per-part sprites generated from our model)
        const bool OwnMapIcon = true;           // own top-down map icon generated from our model (white on transparent, as stock)
        const bool BomberAITuning = true;       // minimumRadarAlt / turningRadius / preventInvertedFlight (see docs)
        // 1.8.1 (in game 1.8.0: a B-25H flew into the ground on a 75 mm pass begun at 1371 m / 444 m AGL, -22 deg; another in the turn
        // after a pass at -33 deg). The game aims a gun pass straight at the target and only climbs it when height / dist < 0.1 (stops at
        // 0.2, AIPilotCombatModes.UseFixedGuns); a re-attack from the 450 m floor at ~1.4 km is a 0.32 slope (18-22 deg) with 1.5x the
        // stock terrain-warning pull and a missed 15 deg break-off gate. The stock A-19 / CI-22 start from 50 / 30 m (slope < 0.1, the
        // climb logic then holds 0.1-0.2). tools/flightmodel/gunpass.py. true = floor 150 (stock bombers 100 x 5 g / 3.5 g); false = 450.
        const bool AIFloorStock181 = true;
        // 1.8.3 offline D (in game 1.8.2 probe P7: 0 x 75 mm / 0 fixed .50 at ground targets in 13 min, 104 rockets). The AI picks the
        // station per target by effectiveness x (0.5 beyond 1.2 x maxRange) (CombatAI.ChooseHQTarget / AnalyzeTarget): at 3.6-7.2 km the
        // stock rockets (0.55, maxRange 6000) beat the halved 75 mm (0.376), and UseLaserGuided turns away after each salvo, so the next
        // assessment is again 4-7 km out -> rockets until they run out (1.8.0 fired its guns only after 52 of 56 rockets; 1.8.2's B-25Hs
        // were lost or ended with rockets left). tools/flightmodel/ai_weapon_choice.py replays both logs (97-98 % agreement).
        // true = the 75 mm info's antiSurface 0.752 -> 1.2 (AI choice weight only; a gun is always HUD GUN mode): the 75 mm with the
        // linked fixed .50s is the AI's ground weapon at every range until its 21 rounds are gone, then rockets / bombs. Fire window
        // (maxRange 3000), floor 150 and every flight value unchanged. false = 1.8.3.
        const bool CannonGroundPriority183D = true;
        // 1.8.6 offline F (in game 1.8.4: AI B-25Hs flew FlyingToTarget legs at 10-30 m AGL for 10-40 s; GA-25X 37-150 m). The game AI
        // points the NOSE / gun boresight (aimVelocity false in FlyToTarget until a break-off) at a terrain waypoint aircraftGLimit-scaled
        // ahead (Autopilot.TerrainWaypoint: max(V,100) x 6 x 9 / aircraftGLimit; AircraftParameters.aircraftGLimit is used for nothing
        // else), held targetHeight x lerp(0.1, 1, (V - 0.9 landingSpeed) / landingSpeed) above the ground there. The aircraft flies its body
        // alpha below that line, so it settles alpha x look-ahead lower: at 51-85 m/s (the slow climb-out after the take-off hand-over at
        // 75 m AGL) 1543 m x 3-9 deg = 70-230 m, more than the hold. true = aircraftGLimit 3.5 -> 9 (the AircraftParameters default and the
        // stock Trainer / fighters; look-ahead 600 m, 6 s) and minimumRadarAlt 150 -> 250 (gun re-attack slope 0.17, inside the stock
        // 0.1-0.2 band). The airframe's pull limit is flyByWire.gLimitPositive 3.5, unchanged (player feel unchanged).
        // tools/flightmodel/ai_terrain.py: replays the 1.8.4 legs (model 18 / 21 m vs logged 15 / 10 m) -> 48 / 56 m; ensemble worst
        // 0 -> 20 m; mountains from cruise 13-89 -> 103-207 m. The 1.8.4 crash (t 280.8) was battle damage: its right main leg broke at
        // 254 m AGL with the gear UP (only a detached nacelle_R does that, LandingGear.OnPartDetached) 9 s before impact. false = 1.8.5.
        const bool AITerrain186F = true;
        const float AIGLimit186F = 9f, AIFloor186F = 250f;
        // 1.8.6 offline F (in game 1.8.4: an AI B-25H broke its nose leg taxiing at K92, 9.9 m/s, compression 0.134 of 0.40). Off tarmac
        // LandingGear.FixedUpdate sinks a wheel by pressure = load / (contactArea x 1e4) and breaks the leg when the dirt drag
        // 2.5 depth^2 |v| pressure^2 exceeds springRate; the AI taxis off the paved surface (stayOnRoad false) with bang-bang full braking,
        // which puts ~45 % of the weight on the nose. The nose kept the CAS1 template's contactArea 0.02 m2 (stock FastBomber1 nose 0.04,
        // QuadVTOL1 0.07). true = nose contactArea 0.05 (drag x 1/39; used ONLY on dirt: tarmac / deck / runway behaviour and the crash-
        // landing compression break unchanged). tools/flightmodel/nose_soft_ground.py. false = 1.8.5.
        const bool NoseContact186F = true;
        const float NoseContactArea186F = 0.05f;
        // 1.8.7 offline F (in game 1.8.5 / 1.8.6: AI B-25Hs from Maris into the ground ~20 s after lift-off, 5 losses, no damage first).
        // AIPilotTakeoffState holds a fixed 9.46 deg climb path (own position + 300 m ahead + 50 m up, aimVelocity) with the gear down
        // until radarAlt > 75 m. A 12.8 t B-25H lifting off at 56-58 m/s cannot hold that; the AI keeps pulling and the FlyByWire alpha
        // limiter (COIN template: 14 deg x 0.1, the command reaches zero only at 24 deg body alpha) lets it pull past our wing's CL peak
        // (16 deg wing = 14 deg body) into the stall: in game 23-26 deg pitch at 49-52 m/s, then a mush into the ground short of 75 m.
        // true = alphaLimiter 10 x 0.25 (the GA-25X values on the same wing): zero command at 14 deg body alpha, nose-down above it, so the
        // AI climbs on the lift curve; the hand-over speed rises to ~56-57 m/s (the K92 climb-outs at 53-56 m/s gave 57-65 m lows: issue 2).
        // Below the corner speed only; a player gets the GA-25X's stall stop. tools/flightmodel/ai_takeoff.py. false = 1.8.6.
        const bool StallLimiter187F = true;

        // ------------------------------------------------------------------ B-25H numbers (sources in docs)
        const float WingIncidence = 2.0f;   // deg, nose up, all wing panels (liftNormal tilt)
        const float StabIncidence = -1.0f;  // deg; CoM (~16% MAC) sits on the wing quarter chord and the game has no downwash, so near-zero tail load trims cruise
        const float EnginePower = 1.27e6f;  // W, Wright R-2600-13 take-off rating 1,700 hp
        const float PropRpm = 1450f;        // prop rpm (2,600 engine rpm x 0.5625 reduction)
        const bool BomberFuelTanks183 = true;   // 1.8.3: AB-4 wing-tank settings + inner <-> outer links (false = CI-22 tanks as 1.8.2)
        const float FuelKg = 1872f;         // 2,600 L avgas x 0.72 (brief); 974 US gal would be 2,650 kg
        const float SpawnHeight = 2.62f;    // root above ground: wheels touch at 2.588 m, static sag ~3-5 cm

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

        // Masses sum to 9,300 kg (B-25H empty 9,060 kg + crew/armour). Areas sum to 54.4 m^2 of wing (gross 56.7 m^2).
        static List<PartSpec> Parts()
        {
            var l = new List<PartSpec>
            {
                new PartSpec("B25H",        null,          "fus_center",  "CAS1:CAS1",       1100, 2.0f, 0.25f, 1, Lift.Own,    0),
                new PartSpec("fus_forward", "B25H",        "fus_forward", "CAS1:fuselage_F",  550, 0.0f, 0.10f, 1, Lift.Own,    150000),
                new PartSpec("fus_cockpit", "fus_forward", "fus_cockpit", "CAS1:cockpit",     750, 0.5f, 0.10f, 1, Lift.Own,    150000),
                new PartSpec("fus_nose",    "fus_cockpit", "fus_nose",    "CAS1:nose",       1050, 0.3f, 0.12f, 1, Lift.Own,    60000),
                new PartSpec("fus_rear",    "B25H",        "fus_rear",    "CAS1:fuselage_R",  450, 0.5f, 0.12f, 1, Lift.Own,    120000),
                new PartSpec("fus_tail",    "fus_rear",    "fus_tail",    "CAS1:tail",        300, 0.0f, 0.08f, 1, Lift.Own,    100000),
            };
            foreach (var s in new[] { "L", "R" })
            {
                l.Add(new PartSpec("stab_" + s,        "fus_tail",       "stab_" + s,        "CAS1:hstab_" + s,      90, 1.6f, 0.01f, 1, Lift.Stab,  40000));
                // Tail area split 1.6 fixed / 3.4 moving (was 2.6 / 2.4): the game deflects only the elevator part, so a real
                // elevator's camber effect on the whole tail is modelled by giving the moving part more of the (unchanged) 5 m^2.
                // In-game 2026-10-30: with 2.6/2.4 full up elevator only rotated the aircraft at 63 m/s (lift-off 82 m/s).
                l.Add(new PartSpec("elevator_" + s,    "stab_" + s,      "elevator_" + s,    "CAS1:elevator_" + s,   30, 3.4f, 0.01f, 1, Lift.Hinge, 30000));
                l.Add(new PartSpec("fin_" + s,         "stab_" + s,      "fin_" + s,         "CAS1:vstab_" + s,      60, 1.6f, 0.01f, 1, Lift.Fin,   30000));
                l.Add(new PartSpec("rudder_" + s,      "fin_" + s,       "rudder_" + s,      "CAS1:rudder_" + s,     30, 1.5f, 0.01f, 1, Lift.Hinge, 20000));
                l.Add(new PartSpec("wing_inner_" + s,  "B25H",           "wing_inner_" + s,  "CAS1:wing1_" + s,     450, 5.8f, 0.02f, 0, Lift.Wing,  200000));
                l.Add(new PartSpec("flap_inner_" + s,  "wing_inner_" + s,"flap_inner_" + s,  "CAS1:flap_" + s,       25, 1.7f, 0.01f, 0, Lift.Hinge, 30000));
                l.Add(new PartSpec("nacelle_" + s,     "wing_inner_" + s,"nacelle_" + s,     "CAS1:engineMount_" + s,300, 0.5f, 0.15f, 1, Lift.Own,  80000));
                l.Add(new PartSpec("engine_" + s,      "nacelle_" + s,   "engine_" + s,      "CAS1:engine_" + s,    950, 0.0f, 0.12f, 1, Lift.Own,   60000));
                l.Add(new PartSpec("prop_" + s,        "engine_" + s,    null,               "COIN:propHub",        180, 0.0f, 0.04f, 1, Lift.Own,   30000));
                l.Add(new PartSpec("wing_outer_" + s,  "wing_inner_" + s,"wing_outer_" + s,  "CAS1:wing2_" + s,     260, 7.0f, 0.01f, 0, Lift.Wing,  120000));
                l.Add(new PartSpec("flap_outer_" + s,  "wing_outer_" + s,"flap_outer_" + s,  "CAS1:flap_" + s,       30, 2.3f, 0.01f, 0, Lift.Hinge, 30000));
                l.Add(new PartSpec("wing_tip_" + s,    "wing_outer_" + s,"wing_tip_" + s,    "CAS1:wing3_" + s,     120, 6.0f, 0.01f, 0, Lift.Wing,  80000));
                l.Add(new PartSpec("aileron_" + s,     "wing_tip_" + s,  "aileron_" + s,     "CAS1:aileron_" + s,    25, 2.3f, 0.01f, 0, Lift.Hinge, 40000));
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

        static void L(string s) { log.Add(s); Debug.Log("[B25H] " + s); }

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
                root.name = "B25H";
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
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Folder + "/B25H.prefab");
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
            var dst = SrcDir + "/b25h_v2.fbx";
            File.Copy(RepoModel, dst, true);
            AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
            var mi = (ModelImporter)AssetImporter.GetAtPath(dst);
            mi.isReadable = true; mi.importAnimation = false; mi.importCameras = false; mi.importLights = false;
            mi.globalScale = 1f; mi.useFileScale = true; mi.importBlendShapes = false;
            mi.SaveAndReimport();
            L($"model imported {dst} ({new FileInfo(RepoModel).Length} bytes)");
            // prop blur stage meshes (model worker, separate FBX so the main model never shows an unwired disc)
            modelBlur = modelFull = null;
            var extra = Path.Combine(Path.GetDirectoryName(RepoModel), "b25h_v2_propdisc.fbx");
            if (File.Exists(extra))
            {
                var edst = SrcDir + "/b25h_v2_propdisc.fbx";
                File.Copy(extra, edst, true);
                AssetDatabase.ImportAsset(edst, ImportAssetOptions.ForceUpdate);
                var emi = (ModelImporter)AssetImporter.GetAtPath(edst);
                emi.isReadable = true; emi.importAnimation = false; emi.importCameras = false; emi.importLights = false; emi.globalScale = 1f; emi.useFileScale = true;
                emi.SaveAndReimport();
                var ms = AssetDatabase.LoadAllAssetsAtPath(edst).OfType<Mesh>().ToList();
                Mesh Take(string n) { var m = ms.FirstOrDefault(x => x.name == n); if (m == null) return null; var c = Object.Instantiate(m); c.name = "b25h_" + n; generatedMeshes.Add(c); return c; }
                modelBlur = Take("propdisc_blur"); modelFull = Take("propdisc_full");
                L($"prop disc meshes from {extra}: blur {(modelBlur ? modelBlur.vertexCount + " v" : "missing")}, full {(modelFull ? modelFull.vertexCount + " v" : "missing")}");
            }
            return AssetDatabase.LoadAssetAtPath<GameObject>(dst);
        }

        static readonly string[] SkinMaps = { "b", "n", "m", "ao", "dmg_b", "dmg_n" };
        // The four 1.0 liveries (offered to both factions, each faction's own two first: unchanged since 1.0) ...
        static readonly (string file, string label, string faction)[] BaseLiveries =
        {
            ("b25h_livery_od_plain",      "Olive Drab (plain)",   "BDF"),   // default (= skin _b), first livery
            ("b25h_livery_usaaf_od",      "USAAF Olive Drab",     "BDF"),
            ("b25h_livery_usaaf_metal",   "USAAF Natural Metal",  "PALA"),
            ("b25h_livery_darkgrey_plain","Dark Grey (plain)",    "PALA"),
        };
        // ... plus faction-only liveries found in b25h_liveries.json (texture worker, 1.1.0: BDF Matte Grey, BDF temperate
        // camo, PALA Matte Black, PALA desert camo). Filled by LoadLiveryTable(); both = offered to both factions.
        static readonly List<(string file, string label, string faction, bool both)> Liveries = new List<(string, string, string, bool)>();
        static readonly Dictionary<string, (string label, string faction)> ExpectedNewLiveries = new Dictionary<string, (string, string)>
        {   // key fragment in the json key or texture name -> label, faction (used when the json entry has no label/faction)
            { "bdf_grey", ("BDF Matte Grey", "BDF") }, { "bdf_matte_grey", ("BDF Matte Grey", "BDF") }, { "bdf_temperate", ("BDF Temperate Camo", "BDF") },
            { "pala_black", ("PALA Matte Black", "PALA") }, { "pala_matte_black", ("PALA Matte Black", "PALA") }, { "pala_desert", ("PALA Desert Camo", "PALA") },
        };

        static void LoadLiveryTable()
        {
            Liveries.Clear();
            foreach (var b in BaseLiveries) Liveries.Add((b.file, b.label, b.faction, true));
            var path = Path.Combine(RepoTextures, "b25h_liveries.json");
            if (!File.Exists(path)) { L("WARN no b25h_liveries.json"); return; }
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(path));
            foreach (var kv in jo)
            {
                if (!(kv.Value is Newtonsoft.Json.Linq.JObject e)) continue;
                var texName = ((string)e["texture"] ?? ("b25h_livery_" + kv.Key + ".png"));
                var file = Path.GetFileNameWithoutExtension(texName);
                if (Liveries.Any(l => l.file == file)) continue;
                string label = (string)e["label"] ?? (string)e["name"] ?? (string)e["displayName"];
                string fac = (string)e["faction"];
                var key = (kv.Key + " " + file).ToLowerInvariant().Replace("-", "_");
                foreach (var x in ExpectedNewLiveries) if (key.Contains(x.Key)) { label = label ?? x.Value.label; fac = fac ?? x.Value.faction; }
                if (fac == null) fac = key.Contains("pala") ? "PALA" : key.Contains("bdf") ? "BDF" : null;
                if (fac == null) { L($"WARN livery {kv.Key}: no faction, skipped"); continue; }
                fac = fac.ToUpperInvariant().Contains("PALA") || fac.ToLowerInvariant().Contains("primeva") ? "PALA" : "BDF";
                if (!File.Exists(Path.Combine(RepoTextures, file + ".png"))) { L($"WARN livery {kv.Key}: texture {file}.png missing, skipped"); continue; }
                Liveries.Add((file, label ?? kv.Key, fac, false));
                L($"livery table: + {file} '{label ?? kv.Key}' ({fac} only)");
            }
        }
        static readonly Dictionary<string, Color32> LiveryFallback = new Dictionary<string, Color32>
        {
            { "b25h_livery_usaaf_od", new Color32(83, 86, 52, 255) }, { "b25h_livery_usaaf_metal", new Color32(178, 180, 182, 255) },
            { "b25h_livery_od_plain", new Color32(74, 78, 46, 255) }, { "b25h_livery_darkgrey_plain", new Color32(64, 66, 70, 255) },
        };
        // tiling detail textures (UV1 'detail' set, copied to UV0 on vertices that no paint submesh uses)
        static readonly string[] Tiles = { "b25h_interior_b", "b25h_structure_b", "b25h_metal_dark_b", "b25h_rubber_b", "b25h_rubber_n", "b25h_prop_b", "b25h_cockpit_b" };
        static readonly Dictionary<string, Texture2D> tex = new Dictionary<string, Texture2D>();

        static void ImportTextures()
        {
            tex.Clear();
            LoadLiveryTable();
            var want = SkinMaps.Select(m => "b25h_skin_" + m).Concat(Liveries.Select(l => l.file)).Concat(new[] { "b25h_gauges" }).Concat(Tiles)
                .Concat(CockpitRebuild ? new[] { "b25h_ckart_b", "b25h_ckart_n", "b25h_quilt_b", "b25h_quilt_n", "b25h_od_b", "b25h_od_n" }.Concat(PropNames.SelectMany(p => new[] { $"b25h_pr_{p}_b", $"b25h_pr_{p}_n" })) : new string[0]).ToList();
            foreach (var n in want)
            {
                var src = Path.Combine(RepoTextures, n + ".png");
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
            else if (n == "b25h_gauges") c = new Color32(22, 22, 22, 255);
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
            var path = $"{Folder}/Textures/b25h_propblur.png";
            File.WriteAllBytes(path, t.EncodeToPNG());
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
            var ti = (TextureImporter)AssetImporter.GetAtPath(path);
            ti.alphaIsTransparency = true; ti.wrapMode = TextureWrapMode.Clamp; ti.mipmapEnabled = true;
            ti.textureCompression = TextureImporterCompression.Compressed; ti.SaveAndReimport();
            L("generated prop blur atlas b25h_propblur.png (512x1024)");
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
            var paint = new Material(skin) { name = "B25H_paint" };
            paint.SetTexture("_Basecolor", tex["b25h_skin_b"]);
            paint.SetTexture("_Normal", tex["b25h_skin_n"]);
            paint.SetTexture("_Metallic", tex["b25h_skin_m"]);
            paint.SetTexture("_AO", tex["b25h_skin_ao"]);
            paint.SetTexture("_BasecolorDmg", tex["b25h_skin_dmg_b"]);
            paint.SetTexture("_NormalDmg", tex["b25h_skin_dmg_n"]);
            paint.SetTexture("_Livery", tex["b25h_skin_b"]); // skin _b is the full painted base colour (= od_plain)
            paint.SetFloat("_Glossiness", 0.35f);
            paint.SetFloat("_HitPoints", 100f);
            Save(paint, "paint");

            var lit = Shader.Find("Universal Render Pipeline/Lit");
            if (lit == null) throw new Exception("URP Lit shader not found");
            var interior = Tiled(LitMat(lit, "B25H_interior", Color.white, 0.0f, 0.25f), "b25h_interior_b");
            Save(CockpitBrighten ? Bright(interior, "b25h_interior_b") : interior, "interior");   // 1.8.0: the cockpit's inner skin (21 m2 of fus_cockpit)
            Save(Tiled(LitMat(lit, "B25H_structure", Color.white, 0.6f, 0.35f), "b25h_structure_b"), "structure");
            Save(Tiled(LitMat(lit, "B25H_metal_dark", Color.white, 0.7f, 0.40f), "b25h_metal_dark_b"), "metal_dark");
            Save(Tiled(LitMat(lit, "B25H_rubber", Color.white, 0.0f, 0.15f), "b25h_rubber_b", "b25h_rubber_n"), "rubber");
            Save(Tiled(LitMat(lit, "B25H_prop", Color.white, 0.2f, 0.30f), "b25h_prop_b"), "prop");
            Save(LitMat(lit, "B25H_prop_tip", new Color(0.85f, 0.70f, 0.05f), 0.0f, 0.30f), "prop_tip");
            Save(Tiled(LitMat(lit, "B25H_cockpit", Color.white, 0.1f, 0.25f), "b25h_cockpit_b"), "cockpit");
            var gauges = LitMat(lit, "B25H_gauges", Color.white, 0f, 0.6f);
            gauges.SetTexture("_BaseMap", tex["b25h_gauges"]); gauges.SetTexture("_MainTex", tex["b25h_gauges"]);
            Save(gauges, "gauges");
            Save(LitMat(lit, "B25H_navlight", new Color(0.3f, 0.3f, 0.3f), 0f, 0.8f), "navlight");
            Save(LitMat(lit, "B25H_screen", Color.black, 0f, 0.5f), "screen");
            if (CockpitRebuild && CockpitBrighten)
            {
                Save(Bright(Tiled(LitMat(lit, "B25H_bk_art", Color.white, 0.0f, 0.35f), "b25h_ckart_b", "b25h_ckart_n"), "b25h_ckart_b"), "bk_art");
                var q = Bright(Tiled(LitMat(lit, "B25H_bk_quilt", Color.white, 0f, 0.1f), "b25h_quilt_b", "b25h_quilt_n"), "b25h_quilt_b"); q.SetTextureScale("_BaseMap", new Vector2(QuiltTiling, QuiltTiling)); q.SetTextureScale("_BumpMap", new Vector2(QuiltTiling, QuiltTiling)); Save(q, "bk_quilt");
                var od = Bright(Tiled(LitMat(lit, "B25H_bk_od", Color.white, 0.0f, 0.3f), "b25h_od_b", "b25h_od_n"), "b25h_od_b"); od.SetTextureScale("_BaseMap", new Vector2(2f, 2f)); od.SetTextureScale("_BumpMap", new Vector2(2f, 2f)); Save(od, "bk_od");
                Save(LitMat(lit, "B25H_bk_black", new Color(CockpitBlackSrgb, CockpitBlackSrgb, CockpitBlackSrgb * 1.1f), 0f, 0.3f), "bk_black");
                foreach (var p in PropNames) Save(Bright(Tiled(LitMat(lit, "B25H_pr_" + p, Color.white, 0.1f, 0.4f), $"b25h_pr_{p}_b", $"b25h_pr_{p}_n"), $"b25h_pr_{p}_b"), "pr_" + p);
            }
            else if (CockpitRebuild)
            {
                Save(Tiled(LitMat(lit, "B25H_bk_art", Color.white, 0.1f, 0.35f), "b25h_ckart_b", "b25h_ckart_n"), "bk_art");
                var q = Tiled(LitMat(lit, "B25H_bk_quilt", Color.white, 0f, 0.1f), "b25h_quilt_b", "b25h_quilt_n"); q.SetTextureScale("_BaseMap", new Vector2(QuiltTiling, QuiltTiling)); q.SetTextureScale("_BumpMap", new Vector2(QuiltTiling, QuiltTiling)); Save(q, "bk_quilt");
                var od = Tiled(LitMat(lit, "B25H_bk_od", Color.white, 0.1f, 0.3f), "b25h_od_b", "b25h_od_n"); od.SetTextureScale("_BaseMap", new Vector2(2f, 2f)); od.SetTextureScale("_BumpMap", new Vector2(2f, 2f)); Save(od, "bk_od");
                Save(LitMat(lit, "B25H_bk_black", new Color(0.03f, 0.03f, 0.035f), 0f, 0.3f), "bk_black");
                foreach (var p in PropNames) Save(Tiled(LitMat(lit, "B25H_pr_" + p, Color.white, 0.2f, 0.4f), $"b25h_pr_{p}_b", $"b25h_pr_{p}_n"), "pr_" + p);
            }
            // The game's own canopy glass shader, via our own material instances (copied property values).
            var glass = new Material(Asset<Material>("Material/COIN_glass_PLACEHOLDER.mat")) { name = "B25H_glass" };
            Save(glass, "glass");
            var glassInt = new Material(Asset<Material>("Material/COIN_glass_int_PLACEHOLDER.mat")) { name = "B25H_glass_int" };
            Save(glassInt, "glass_int");
            // 1.8.1 cockpit-layer glass (B-17G B17G_glass_ck pattern): faint transparent Lit from the stock prop-disc material
            var glassCk = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "B25H_glass_ck" };
            glassCk.SetTexture("_BaseMap", null); glassCk.SetTexture("_MainTex", null);
            glassCk.SetColor("_BaseColor", new Color(0.86f, 0.92f, 0.97f, 0.06f)); glassCk.SetColor("_Color", new Color(0.86f, 0.92f, 0.97f, 0.06f));
            glassCk.SetFloat("_Smoothness", 0.95f); glassCk.SetFloat("_Cull", 0f);
            Save(glassCk, "glass_ck");
            // Prop blur: the CI-22 disc material is URP Lit transparent with _BaseColor alpha 0.10 and a blur atlas mapped onto a
            // 5,760-vertex stack of blade ghosts (COIN.prefab propHub, COIN_propdisc1/2 meshes); a single flat disc with that
            // material is ~invisible, which is why the 1.0 props "vanished" above ~15 % rpm (ConstantSpeedProp.PropAnimate hides
            // the blades whenever propDiscMeshes[index] != stage 0). Same shader settings, our own atlas, alpha in the texture.
            var disc = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "B25H_propdisc" };
            if (OwnPropBlur)
            {
                // texture worker's 3-blade blur atlas (same layout: top half smear, bottom half disc) when present
                var workerBlur = Directory.Exists(RepoTextures) ? Directory.GetFiles(RepoTextures, "b25h_prop*blur*.png").FirstOrDefault() : null;
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
                disc.SetFloat("_Cull", File.Exists(Path.Combine(Path.GetDirectoryName(RepoModel), "b25h_v2_propdisc.fbx")) ? 2f : 0f);
            }
            Save(disc, "propdisc");
            L("materials: " + string.Join(", ", mats.Keys) + $" (glass shader {glass.shader.name}, disc shader {disc.shader.name})");
        }

        // 1.8.0: mean linear luminance of a repo texture (sRGB decode), every 7th pixel
        static readonly Dictionary<string, float> albedoMean = new Dictionary<string, float>();
        static float TexLinearMean(string name)
        {
            if (albedoMean.TryGetValue(name, out var v)) return v;
            var t = new Texture2D(2, 2); t.LoadImage(File.ReadAllBytes(Path.Combine(RepoTextures, name + ".png")));
            var px = t.GetPixels32(); double sum = 0; int n = 0;
            for (int i = 0; i < px.Length; i += 7) { var c = px[i]; sum += 0.2126 * Math.Pow(c.r / 255.0, 2.2) + 0.7152 * Math.Pow(c.g / 255.0, 2.2) + 0.0722 * Math.Pow(c.b / 255.0, 2.2); n++; }
            Object.DestroyImmediate(t);
            return albedoMean[name] = (float)(sum / n);
        }
        static Material Bright(Material m, string texName)
        {
            float mean = TexLinearMean(texName), gain = Mathf.Clamp(CockpitAlbedoTarget / Mathf.Max(mean, 1e-4f), 1f, CockpitAlbedoMaxGain);
            var c = new Color(gain, gain, gain, 1f); m.SetColor("_BaseColor", c); m.SetColor("_Color", c);
            L($"cockpit albedo {m.name}: texture {texName} mean {mean:F3} linear x {gain:F2} -> {mean * gain:F3} (stock cockpits 0.10-0.14)");
            return m;
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
            var ss = StockStructure.Apply(root, StockStructure.LookMaterial(Asset<Material>("Material/aircraft_structure_PLACEHOLDER.mat"), Folder, "B25H"),
                new Dictionary<Material, Color32> { { mats["structure"], StockStructure.StockGrey } }, 1f, generatedMeshes);
            L($"stock structure: {ss.renderers} renderers, {ss.triangles} tris, {ss.children} structure children");
        }

        // ------------------------------------------------------------------ parts
        static void MakePartObject(PartSpec s)
        {
            GameObject go;
            if (s.name == "B25H") go = root;
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
            MeshFilter own = s.name == "B25H" ? Find("fus_center").GetComponent<MeshFilter>()
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
                    float inc = s.lift == Lift.Wing ? WingIncidence : StabIncidence;
                    q = Quaternion.AngleAxis(-inc, q * Vector3.right) * q;
                }
                ln = NewGO(s.name + "_liftNormal", go.transform, go.transform.position, q).transform;
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
                    Add(owner, other, other == "B25H" ? bySpec[owner].parent : other, Mathf.Min(bySpec[a].joint == 0 ? 1e6f : bySpec[a].joint, bySpec[b].joint == 0 ? 1e6f : bySpec[b].joint) * 0.3f);
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
                CS("elevator_" + side, "CAS1:elevator_" + side, -25f, 0, 0, 40f);
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
        static void Flaps()
        {
            foreach (var f in new[] { "flap_inner_L", "flap_inner_R", "flap_outer_L", "flap_outer_R" })
            {
                var h = CloneComp(TplComp<HighLiftDevice>("COIN:flap_L"), parts[f].gameObject);
                S(h, "aeroPart", parts[f]); S(h, "swingWingController", null);
                S(h, "speedDeployed", 55f); S(h, "speedRetracted", 68f);   // B-25 flap limit 150 mph = 67 m/s
                S(h, "alphaMin", 0f); S(h, "alphaFactor", 0f);
                S(h, "deployedArea", f.Contains("inner") ? 0.4f : 0.6f);
                var mp = NewElem(h, "movingParts");
                S(mp, "move", false); S(mp, "rotate", true); S(mp, "transform", liftNormals[f]);
                S(mp, "positionRetracted", Vector3.zero); S(mp, "positionDeployed", Vector3.zero);
                S(mp, "anglesRetracted", Vector3.zero); S(mp, "anglesDeployed", new Vector3(-25f, 0, 0)); // TE down
                SetSeq(h, "movingParts", new[] { mp });
            }
        }

        // ------------------------------------------------------------------ landing gear
        class GearSpec { public string strut, wheel, part; public float fold, travel, k, c, maxComp, mass, drag; public bool steer, brake; public float diff; public (string door, Vector3 axis, float open)[] doors; }

        static List<LandingGear> Gear()
        {
            var list = new List<LandingGear>();
            var nose = new GearSpec
            {
                strut = "gear_nose_strut", wheel = "gear_nose_wheel", part = "fus_cockpit", fold = 110f, travel = 0.379f + 0.25f, k = 650000f, c = 40000f, maxComp = 0.40f,
                mass = 120f, drag = 0.4f, steer = true, brake = false, diff = 0f,
                doors = new[] { ("gear_door_nose_L", new Vector3(-0.0002f, 0.0084f, 1.0f), -95f), ("gear_door_nose_R", new Vector3(0.0002f, 0.0084f, 1.0f), 95f) }
            };
            list.Add(MakeGear(nose, "CAS1:gear_F_sprung", "COIN:wheel_F"));
            foreach (var s in new[] { "L", "R" })
            {
                var m = new GearSpec
                {
                    strut = $"gear_main_{s}_strut", wheel = $"gear_main_{s}_wheel", part = "nacelle_" + s, fold = 88f, travel = 0.595f + 0.30f, k = 750000f, c = 60000f, maxComp = 0.45f,
                    mass = 250f, drag = 0.8f, steer = false, brake = true, diff = s == "L" ? -1f : 1f,
                    doors = s == "L"
                        ? new[] { ("gear_door_main_L_a", new Vector3(0.0195f, -0.0878f, 0.9959f), 95f), ("gear_door_main_L_b", new Vector3(-0.0195f, -0.0878f, 0.9959f), -95f) }
                        : new[] { ("gear_door_main_R_a", new Vector3(-0.0195f, -0.0878f, 0.9959f), -95f), ("gear_door_main_R_b", new Vector3(0.0195f, -0.0878f, 0.9959f), 95f) }
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
                te.maxRPM = 2600f; te.minRPM = 600f; te.maxPower = EnginePower; te.spoolUpTime = 2.5f; S(te, "startupTime", 6f);
                S(te, "pitch", 0.15f); S(te, "volume", 0.08f);
                S(te, "startupAudio", startup); te.aircraft = aircraft;
                S(te, "heatHazeParticles", new ParticleSystem[0]);
                S(te, "maxFuelConsumption", 0.11f); S(te, "IRMin", 1.2f); S(te, "IRMax", 1.6f);
                S(te, "IRSourceTransform", Find("exhaust_" + s));
                S(te, "criticalParts", new UnitPart[] { parts["engine_" + s], parts["prop_" + s] });
                S(te, "criticalDamageThreshold", 40f);
                S(te, "failureTransform", NewGO("engine_" + s + "_fail", eng.transform, eng.transform.position + new Vector3(0, 0.3f, 0.4f), Quaternion.identity).transform);
                var tr = CloneComp(TplComp<Transmission>("COIN:COIN"), eng);
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
                    S(b, "transform", broot.transform); S(b, "liftTransform", lt.transform); S(b, "mass", 40f);
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
                S(csp, "momentOfInertia", 150f); S(csp, "bladeLength", R); S(csp, "hubRadius", 0.25f);
                S(csp, "rpmLimit", PropRpm); S(csp, "nominalPower", EnginePower); S(csp, "propTorqueLimit", 15000f);
                S(csp, "propAudio", pa);
                L($"prop {s}: radius {R:F3} m, {blades.Count} blades, rpmLimit {PropRpm}, hub {hubVis.position.ToString("F3")}");
            }
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
        static List<Gun> Weapons()
        {
            var nose = parts["fus_nose"]; var cockpit = parts["fus_cockpit"];
            // 75 mm T13E1 (M5 gun): single-shot cannon like the stock 57 mm side mount (one AudioSource => one fire sound per round, no loop)
            var cannon = Find("cannon");
            var cannonMount = NewGO("cannon_mount", nose.transform, cannon.position, Quaternion.identity);
            var cannonRecoil = NewGO("cannon_recoil", cannonMount.transform, cannon.position, Quaternion.identity);
            cannon.SetParent(cannonRecoil.transform, true);
            var t57 = tpl["turret_57mm_SideMount"].GetComponentInChildren<Gun>(true);
            var a57 = t57.GetComponents<AudioSource>()[0];
            CloneComp(a57, cannonMount).loop = false;
            var cannon75 = CloneComp(t57, cannonMount);
            cannon75.attachedUnit = aircraft;
            S(cannon75, "magazineCapacity", 1); S(cannon75, "magazines", 20); S(cannon75, "reloadTime", 3.0f); S(cannon75, "startLoaded", true); // hand-loaded: 21 rounds
            S(cannon75, "fireRate", 60f); S(cannon75, "bulletSpread", 0.35f); S(cannon75, "muzzles", new[] { Find("muzzle_cannon") });
            S(cannon75, "recoilTransform", cannonRecoil.transform); S(cannon75, "recoilImpulse", 4200f); S(cannon75, "recoilTravel", 0.25f);
            S(cannon75, "recoilRate", 10f); S(cannon75, "recoilReturnRate", 1.2f);
            S(cannon75, "recoilSound", null); S(cannon75, "reloadSound", null); S(cannon75, "spinTransform", null);
            S(cannon75, "ejectionTransform", null); S(cannon75, "ejectionPrefab", null);
            S(cannon75, "fireSustained", null); S(cannon75, "fireEnd", null);
            S(cannon75, "muzzleParticles", CopyMuzzleParticles(t57, Find("muzzle_cannon")));
            S(cannon75, "heatEnabled", false);

            // .50 cal M2: 4 fixed nose guns + 4 package guns, two Gun components (one per mounting part) in one set
            var g12 = tpl["gun_12.7mm_internal"].GetComponentInChildren<Gun>(true);
            // Own copy of the stock 12.7 mm info for the fixed guns, usable by the AI against AIRBORNE targets only
            // (TargetRequirements.minAltitude: CombatAI.AnalyzeTarget rejects targets lower than minAltitude x dist / maxRange;
            // buildings report radarAlt = half their height, so 5 was not enough: 150 -> 25 m at 500 m, 75 m at 1.5 km).
            // In game (1.1.0 test) every AI strafing run with fixed guns (UsingFixedGuns: collisions ignored, break-off 2 s before
            // the target) ended in the ground: a 3.5 g bomber cannot pull out in 2 s. Ground attack then uses bombs and the
            // laser-guided rockets; the player can still fire the guns at anything.
            WeaponInfo fixedInfo = null;
            if (FixedGunsAirOnlyForAI)
            {
                fixedInfo = Object.Instantiate(Asset<WeaponInfo>("MonoBehaviour/Gun12.7mm_PLACEHOLDER.asset")); fixedInfo.name = "B25H_fixed_50cal_info";
                fixedInfo.targetRequirements.minAltitude = 150f;
                AssetDatabase.CreateAsset(fixedInfo, Folder + "/B25H_fixed_50cal_info.asset");
            }
            Gun Fifties(string name, AeroPart part, Transform at, Transform[] muzzles)
            {
                var go = NewGO(name, part.transform, at.position, Quaternion.identity);
                foreach (var a in g12.GetComponents<AudioSource>()) CloneComp(a, go).loop = false; // Gun.Awake makes source[1] its sustained loop and stops it itself
                var g = CloneComp(g12, go);
                g.attachedUnit = aircraft; if (fixedInfo != null) g.info = fixedInfo;
                S(g, "magazineCapacity", 400); S(g, "magazines", 0); S(g, "startLoaded", true); // 400 rounds per barrel (each cycle fires every muzzle)
                S(g, "fireRate", 800f); S(g, "muzzles", muzzles);
                S(g, "recoilTransform", null); S(g, "spinTransform", null);
                var ps = new List<ParticleSystem>();
                foreach (var mz in muzzles) ps.AddRange(CopyMuzzleParticles(g12, mz));
                S(g, "muzzleParticles", ps.ToArray());
                return g;
            }
            var nGun = Fifties("guns_nose_50cal", nose, Find("nose_guns"), new[] { "muzzle_nose_1", "muzzle_nose_2", "muzzle_nose_3", "muzzle_nose_4" }.Select(Find).ToArray());
            var pGun = Fifties("guns_package_50cal", cockpit, Find("package_guns_L"), new[] { "muzzle_package_L1", "muzzle_package_L2", "muzzle_package_R1", "muzzle_package_R2" }.Select(Find).ToArray());

            // ammunition mounts (our own WeaponMount assets; info = stock weapon definitions)
            var cannonInfo = Asset<WeaponInfo>("MonoBehaviour/Gun57mm_Aerial_PLACEHOLDER.asset");
            if (OwnCannonWeaponInfo)
            {
                var own = Object.Instantiate(cannonInfo); own.name = "B25H_T13E1_75mm_info";
                own.weaponName = "75mm T13E1 Cannon"; own.muzzleVelocity = 619f;
                // The 57 mm Aerial source is a side-firing gunship gun: boresight 0, maxRange 9000. Our cannon is fixed and
                // forward-firing. Without boresight the AI never enters UsingFixedGuns (AIPilotCombatModes.FlyToTarget) and
                // circled its ground target at 50-87 deg bank, sinking (in game, 1.1.0 test). Range as the stock fixed 30 mm.
                own.boresight = true;
                own.targetRequirements.maxRange = 3000f;
                if (FixedGunsAirOnlyForAI) own.targetRequirements.minAltitude = 150f; // see fixedInfo: no AI strafing of ground targets
                if (CannonGroundPriority183D) own.effectiveness.antiSurface = 1.2f;   // 1.8.3D: AI ground-weapon choice (0.752 = the 57 mm Aerial's)
                AssetDatabase.CreateAsset(own, Folder + "/B25H_T13E1_75mm_info.asset");
                cannonInfo = own;
            }
            if (OwnCannonWeaponInfo) cannon75.info = cannonInfo; // the built-in gun carries the same info as its ammo mount
            var ammoPrefabGO = new GameObject("B25H_internal_ammo");
            var ammoPrefab = PrefabUtility.SaveAsPrefabAsset(ammoPrefabGO, Folder + "/B25H_internal_ammo.prefab");
            Object.DestroyImmediate(ammoPrefabGO);
            var tAmmo = Asset<WeaponMount>("MonoBehaviour/gun_ammo_35mm_720_PLACEHOLDER.asset");
            ammoCannon = Object.Instantiate(tAmmo); ammoCannon.name = "B25H_ammo_T13E1_75mm";
            ammoCannon.prefab = ammoPrefab; ammoCannon.jsonKey = "B25H_ammo_T13E1_75mm"; ammoCannon.info = cannonInfo; ammoCannon.mountName = "75mm T13E1 x21";
            ammoCannon.ammo = 21; ammoCannon.GunAmmo = true; ammoCannon.mass = 21 * 6.8f;
            AssetDatabase.CreateAsset(ammoCannon, Folder + "/B25H_ammo_T13E1_75mm.asset");
            ammo50 = Object.Instantiate(tAmmo); ammo50.name = "B25H_ammo_50cal";
            ammo50.prefab = ammoPrefab; ammo50.jsonKey = "B25H_ammo_50cal"; ammo50.info = fixedInfo != null ? fixedInfo : Asset<WeaponInfo>("MonoBehaviour/Gun12.7mm_PLACEHOLDER.asset");
            ammo50.mountName = ".50 cal M2 x8 (400 rpg)"; ammo50.ammo = 800; ammo50.GunAmmo = true; ammo50.mass = 3200 * 0.11f;
            AssetDatabase.CreateAsset(ammo50, Folder + "/B25H_ammo_50cal.asset");

            // hardpoints
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
            Set("75mm T13E1 Cannon", new[] { ammoCannon }, HP(cannonMount.transform, nose, new Weapon[] { cannon75 }));
            Set("Internal guns", new[] { ammo50 }, HP(nGun.transform, nose, new Weapon[] { nGun }), HP(pGun.transform, cockpit, new Weapon[] { pGun }));

            // bomb bay with two doors (EW1 BayDoor values, our hinges)
            var bay = Find("hp_bombbay");
            var doorAudio = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), bay.gameObject);
            doorAudio.clip = null; doorAudio.loop = false; doorAudio.playOnAwake = false; doorAudio.volume = 0.8f;
            var bayDoors = new List<BayDoor>();
            foreach (var (dn, axis, open) in new[] { ("bomb_door_L", new Vector3(-0.0009f, -0.0021f, 1.0f), -92f), ("bomb_door_R", new Vector3(0.0009f, -0.0021f, 1.0f), 92f) })
            {
                var hb = DoorHinge(Find(dn), axis.normalized, open, false);
                var bd = CloneComp(TplComp<BayDoor>("EW1:weapon_door_hinge_L"), hb.gameObject);
                S(bd, "hingeAngle", open); S(bd, "openSpeed", 1.2f); S(bd, "closeSpeed", 0.8f); S(bd, "doorAudioSource", doorAudio);
                bayDoors.Add(bd);
            }
            // GPO-N wherever a GPO-500 fits (bay x2 / x1, wing racks single) and the GPO-2P Auger (bay x2, racks single).
            // Stock mounts only (MonoBehaviour/*.asset in _donotship); the single external Auger mount's placeholder sits in
            // MonoBehaviour/__dedupe/ because its file name collides with the Bomb_penetrator1 MissileDefinition.
            var bayOpts = new List<string> { "bomb_250_internalx3", "bomb_500_internalx2", "bomb_500_internal", "bomb_cluster1_dual_internal" };
            var rackOpts = new List<string> { "bomb_125_single", "bomb_250_single", "bomb_500_single", "bomb_cluster1_single" };
            if (NuclearOptions)
            {
                bayOpts.AddRange(new[] { "nuclearBomb1_internalx2", "nuclearBomb1_internal", "bomb_penetrator1_internalx2" });
                rackOpts.AddRange(new[] { "nuclearBomb1_external", "__dedupe/bomb_penetrator1" });
                if (StrategicGPON) { bayOpts.AddRange(new[] { "nuclearBomb1_strategic_internalx2", "nuclearBomb1_strategic_internal" }); rackOpts.Add("nuclearBomb1_strategic_external"); }
            }
            Set("Bomb Bay", bayOpts.Select(Mount), HP(bay, parts["B25H"], null, bayDoors.ToArray(), 1.5f));
            Set("Wing Racks", rackOpts.Select(Mount),
                HP(Find("hp_wingrack_L"), parts["wing_inner_L"]), HP(Find("hp_wingrack_R"), parts["wing_inner_R"]));
            var rails = new List<Hardpoint>();
            foreach (var s in new[] { "L", "R" }) for (int i = 1; i <= 4; i++) rails.Add(HP(Find($"hp_rail_{s}{i}"), parts["wing_outer_" + s]));
            Set("Rocket Rails", new[] { "RocketPod1_single" }.Select(Mount), rails.ToArray());

            // defensive turrets (built-in, AttackHelo1 chin-turret pattern) - own station identity: a mod-local copy of the
            // stock Gun12.7mm info (same M2 ballistics) so the 4 turrets do not join the fixed nose .50s' station
            // (Turret.AttachToWeaponManager joins the first station with the same WeaponInfo) and boresight = false like
            // every stock turret gun info (the AI pilot then never tries to point the airframe for them).
            if (DefensiveTurrets && contract != null)
            {
                turretInfo = Object.Instantiate(Asset<WeaponInfo>("MonoBehaviour/Gun12.7mm_PLACEHOLDER.asset")); turretInfo.name = "B25H_turret_50cal_info";
                turretInfo.weaponName = "12.7mm Defensive Turrets"; turretInfo.shortName = "TURRETS 12.7MM"; turretInfo.boresight = false;
                if (TurretAntiMissile) turretInfo.effectiveness.antiMissile = 0.05f;
                AssetDatabase.CreateAsset(turretInfo, Folder + "/B25H_turret_50cal_info.asset");
                BuildTurrets();
                if (turrets.Count > 0)
                {
                    ammoTurrets = Object.Instantiate(tAmmo); ammoTurrets.name = "B25H_ammo_turrets";
                    ammoTurrets.prefab = ammoPrefab; ammoTurrets.jsonKey = "B25H_ammo_turrets"; ammoTurrets.info = turretInfo;
                    int perCycle = turrets.Sum(t => (int)G(t.gun, "magazineCapacity")), barrels = turrets.Sum(t => ((Transform[])G(t.gun, "muzzles")).Length);
                    ammoTurrets.ammo = perCycle; ammoTurrets.GunAmmo = true; ammoTurrets.mass = turrets.Sum(t => (int)G(t.gun, "magazineCapacity") * ((Transform[])G(t.gun, "muzzles")).Length) * 0.11f;
                    ammoTurrets.mountName = $".50 cal turrets x{barrels}";
                    AssetDatabase.CreateAsset(ammoTurrets, Folder + "/B25H_ammo_turrets.asset");
                    Set("Defensive turrets", new[] { ammoTurrets }, turrets.Select(t => { var h = HP(t.mount, t.part, new Weapon[] { t.gun }); h.BuiltInTurrets = new[] { t.turret }; return h; }).ToArray());
                }
            }

            // HardpointIndex: right-to-left like the stock aircraft
            var all = sets.SelectMany(x => x.hardpoints).OrderByDescending(h => h.transform.position.x).ThenByDescending(h => h.transform.position.z).ToList();
            for (int i = 0; i < all.Count; i++) all[i].HardpointIndex = i;
            weaponManager.hardpointSets = sets.ToArray();
            S(weaponManager, "aircraft", aircraft);
            L($"hardpoint sets: {string.Join(" | ", sets.Select(x => $"{x.name} ({x.hardpoints.Count} hp, {x.weaponOptions.Count - 1} options)"))}");
            return new List<Gun> { cannon75, nGun, pGun };
        }

        static WeaponMount Mount(string n) => Asset<WeaponMount>($"MonoBehaviour/{n}_PLACEHOLDER.asset");

        static ParticleSystem[] CopyMuzzleParticles(Gun template, Transform muzzle)
        {
            var src = (ParticleSystem[])G(template, "muzzleParticles") ?? new ParticleSystem[0];
            return src.Where(p => p != null).Select(p => CopyParticle(p, muzzle, muzzle.position, muzzle.name + "_" + p.name)).Select(p => { p.transform.rotation = muzzle.rotation; return p; }).ToArray();
        }

        // ------------------------------------------------------------------ cockpit, crew, canopy
        // Model contract (model worker): assets/model_v2/b25h_v2_contract.json - object names, pivots, axes, limits.
        static Newtonsoft.Json.Linq.JObject contract;
        static Newtonsoft.Json.Linq.JObject LoadContract()
        {
            var p = Path.Combine(Path.GetDirectoryName(RepoModel), "b25h_v2_contract.json");
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
            var copyNames = new List<string> { "cockpit_interior", "cockpit_gauges", "cockpit_seat_L", "cockpit_seat_R", "cockpit_yoke_L", "cockpit_rudder_pedals_L", "canopy_frame", "fus_cockpit", "fus_forward" };
            // canopy_glass is deliberately NOT copied: the stock interior glass shader (Shader Graphs/canopy_int) rendered our
            // canopy as an opaque dark shell from the pilot's eye (in-game test 2026-10-30).
            copyNames.AddRange(new[] { "cockpit_column_L", "cockpit_column_R", "cockpit_yoke_R", "cockpit_rudder_pedals_R", "gunsight_pilot", "gunsight_combiner", "mfd_center", "mfd_left", "mfd_right", "hatch_cockpit_top" });
            copyNames.AddRange(root.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.StartsWith("gauge_") || m.name.StartsWith("quadrant_")).Select(m => m.name));
            if (CanopyGlassInterior181) copyNames.Add("canopy_glass");   // 1.8.1: stock pattern, with the faint glass_ck (not canopy_int)
            var glassInCockpit = CanopyGlassInterior181 ? mats["glass_ck"] : mats["glass_int"];
            foreach (var n in copyNames.Distinct())
            {
                var orig = TryFind(n);
                if (orig == null || orig.GetComponent<MeshRenderer>() == null) continue;
                var src = orig.GetComponent<MeshRenderer>();
                if (src.sharedMaterials.All(m => m == mats["glass"]) && !(CanopyGlassInterior181 && n == "canopy_glass")) continue;
                var copy = NewGO(n + "_int", orig, orig.position, orig.rotation, 3);
                copy.AddComponent<MeshFilter>().sharedMesh = orig.GetComponent<MeshFilter>().sharedMesh;
                var cr = copy.AddComponent<MeshRenderer>();
                cr.sharedMaterials = src.sharedMaterials.Select(m => m == mats["glass"] ? glassInCockpit : m).ToArray();
                cr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                cr.enabled = false; // the game enables cockpit renderers (and hides the exterior ones) in cockpit view
                cockpitR.Add(cr); exteriorR.Add(src);
                // performance pass: the exterior originals of cockpit-only meshes (hidden in cockpit view, inside the closed
                // fuselage in external view) cast no shadows; the fuselage / canopy / hatch keep theirs
                if (CockpitPropsNoShadow && !(n == "fus_cockpit" || n == "fus_forward" || n == "canopy_frame" || n == "hatch_cockpit_top" || n == "canopy_glass"))
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
                var screen = NewGO("screen_dummy", cp.transform, Find("cockpit_gauges").position + new Vector3(0, -0.2f, -0.05f), Quaternion.identity, 3);
                screen.AddComponent<MeshFilter>().sharedMesh = QuadMesh("screen_dummy", 0.01f, 0.01f);
                var sr = screen.AddComponent<MeshRenderer>(); sr.sharedMaterial = mats["screen"]; sr.enabled = false;
                tacR = sr;
                L("WARN screens: no mfd_center in the model, hidden dummy screen (1.0 behaviour)");
            }

            var interior = Find("cockpit_interior").gameObject;
            var ck = CloneComp(TplComp<global::Cockpit>("COIN:cockpit_F_interior"), interior);
            S(ck, "tacScreenRender", tacR); S(ck, "aircraft", aircraft);
            S(ck, "engineSources", new[] { parts["engine_L"].gameObject, parts["engine_R"].gameObject });
            SetSeq(ck, "joysticks", new object[0]);   // the yoke is driven by ControlSurfaces below (column pitch, wheel roll)
            SetSeq(ck, "throttles", new object[0]);
            if (CockpitAnimators) CockpitAnimation(ck, cp);
            else
            {   // 1.0: whole yoke as a stick
                var js = NewElem(ck, "joysticks"); S(js, "transform", Find("cockpit_yoke_L")); S(js, "range", 12f);
                SetSeq(ck, "joysticks", new[] { js });
            }

            // target camera + laser designator on the nose (game systems the HUD and tac screen expect)
            var nose = parts["fus_nose"];
            var tcF = NewGO("targetCamForward", nose.transform, new Vector3(0, -0.45f, 5.75f), Quaternion.identity, 0);
            var tcR = NewGO("targetCamRear", parts["fus_tail"].transform, new Vector3(0, -0.2f, -10.4f), Quaternion.LookRotation(Vector3.back), 0);
            var tcL = NewGO("landingCamPoint", nose.transform, new Vector3(0, -0.8f, 5.0f), Quaternion.LookRotation(new Vector3(0, -0.3f, 1f)), 0);
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
            if (c.role == "tail" && TailCrewScale < 0.999f)
            {
                fig.transform.localScale *= TailCrewScale;
                fig.transform.position += c.eye.position - cam.position;
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

        // --- defensive turrets: built-in Turret like the AttackHelo1 chin turret (Hardpoint.BuiltInTurrets + BuiltInWeapons,
        // Turret.weaponStations[0] = {Weapons = [gun], Turrets = [this]}); target source = the aircraft's TargetDetector
        // (targetAcquisitionMode 0 = parentUnitTargetDetector, as the UH-90 door gun turret_12.7mm_door and the CI-22
        // ventral turret_20mm_rotary); M2 values (900 rpm, spread 2, audio) from turret_12.7mm_door; stock barrel mesh.
        // Turret.cs writes az localEulerAngles = (0, trav, 0) and el = (elev, 0, 0) absolutely: the model's az/el rest at
        // identity under *_mount (contract), checked below. Self-hit protection is stock: Turret.FixedUpdate fires only when
        // a 200 m linecast from the elevation pivot hits nothing nearer than the target (own airframe included); firing
        // cones keep the AI from even trying to aim through the airframe.
        static readonly Dictionary<string, int> TurretRounds = new Dictionary<string, int>
        {   // rounds per gun (one Gun cycle fires every muzzle and costs 1 round, as the fixed .50s)
            { "turret_dorsal_mount", 400 }, { "tail_turret_mount", 500 }, { "waist_gun_L_mount", 300 }, { "waist_gun_R_mount", 300 },
        };
        // Safe aim envelopes (traverse +-, min/max elevation, degrees): all turrets share ONE weapon station, and
        // WeaponStation.Fire fires every gun of the station when any one turret's own clear-shot linecast passes, so a gun
        // parked at a limit that looks into our own airframe also fires (in game 1.1.0: left waist gun hit nacelle_L 11x).
        // These limits keep every gun's line of fire (pivot and muzzles, +-2 deg spread) off the airframe at any angle;
        // values from the Check's envelope scan ("turret envelope" lines). null = contract values.
        static readonly Dictionary<string, (float trav, float emin, float emax)> TurretSafeLimits = new Dictionary<string, (float, float, float)>
        {   // strict scan (Check, build v110j): dorsal unsafe below +5 deg aft over the fins and at -5 deg abeam (wing/nacelle);
            // waist guns unsafe over the whole forward half (wing, nacelle, flaps) below +10 deg; tail turret clean.
            // 1.8.13 r2: 7.5 -> 10 - the AN/M2 pivot sits 0.10 m lower in the dome (receivers clear the dome top at 85 deg), so at +-160 the
            // muzzles looked into the fins at 7.5 deg (strict scan SUGGEST trav 180 el 10..85)
            { "turret_dorsal_mount", (180f, ANM2Guns ? 10f : 7.5f, 85f) },
            { "waist_gun_L_mount", (17.5f, -30f, 40f) },
            { "waist_gun_R_mount", (17.5f, -30f, 40f) },
        };
        // Waist mounts are turned aft so the symmetric traverse covers only the clean aft-abeam sector (contract: abeam,
        // +-40). Measured clean: left a in [-40, -5], right a in [+5, +40] (traverse sign: + = toward the nose for the left
        // gun, toward the tail for the right gun). Centre 22.5 deg aft, +-17.5.
        static readonly Dictionary<string, float> TurretMountYaw = new Dictionary<string, float>
        {
            { "waist_gun_L_mount", -22.5f }, { "waist_gun_R_mount", 22.5f },
        };
        static WeaponInfo turretInfo; static WeaponMount ammoTurrets;
        static readonly List<(Turret turret, Gun gun, AeroPart part, Transform mount)> turrets = new List<(Turret, Gun, AeroPart, Transform)>();

        static AeroPart OwningPart(Transform t) { for (var x = t; x != null; x = x.parent) { var ap = x.GetComponent<AeroPart>(); if (ap != null) return ap; } return null; }

        static void BuildTurrets()
        {
            turrets.Clear();
            var doorTpl = tpl["turret_12.7mm_door"];
            var tplTurret = doorTpl.GetComponentInChildren<Turret>(true);
            var tplGun = doorTpl.GetComponentInChildren<Gun>(true);
            var barrelMesh = Asset<Mesh>("Mesh/50cal_doorGun_barrel_PLACEHOLDER.asset");
            var barrelMat = Asset<Material>("Material/utilityHelo1_attachments_PLACEHOLDER.mat");
            // 1.8.13 (offline L): our own AN/M2 (ANM2Gun.cs) instead of the stock door-gun barrel: bore through the contract muzzle, tip on it,
            // dorsal twin gun_L / gun_R without grips, tail twin L / R with grips, waist singles with grips (feed on the forward wall-box side)
            var anm2 = ANM2Guns ? ANM2Gun.Load(Folder, "B25H") : null;
            foreach (var tj in JList("turrets", "turrets"))
            {
                var mount = TryFind((string)tj["mount"]["name"]); var az = TryFind((string)tj["az"]["name"]); var el = TryFind((string)tj["el"]["name"]);
                if (mount == null || az == null || el == null) { L($"WARN turret {(string)tj["mount"]["name"]}: objects missing, skipped"); continue; }
                var part = OwningPart(mount);
                if (TurretMountYaw.TryGetValue(mount.name, out var myaw))
                {
                    mount.localRotation = mount.localRotation * Quaternion.Euler(0f, myaw, 0f);
                    L($"turret {mount.name}: mount turned {myaw} deg about its up axis (safe sector), fwd now {mount.forward.ToString("F2")}");
                }
                if (Quaternion.Angle(az.localRotation, Quaternion.identity) > 0.01f || Quaternion.Angle(el.localRotation, Quaternion.identity) > 0.01f)
                    L($"WARN turret {mount.name}: az/el do not rest at identity ({az.localEulerAngles} / {el.localEulerAngles}); Turret will snap them");
                var muzzles = new List<Transform>();
                foreach (var g in (Newtonsoft.Json.Linq.JArray)tj["guns"])
                {
                    var gb = TryFind((string)g["gun"]["name"]); var mz = TryFind((string)g["muzzle"]["name"]);
                    if (gb == null || mz == null) continue;
                    if (anm2 != null)
                    {
                        var (right, grips) = ANM2Gun.Variant(gb.name, gb, el, ((Newtonsoft.Json.Linq.JArray)tj["guns"]).Count > 1);
                        var gt = ANM2Gun.Place(anm2, gb, mz, el, right, grips);
                        L($"AN/M2 {gb.name}: {(right ? "gun_R" : "gun_L")}{(grips ? " + grips" : "")}, gun at slot ({gt.localPosition.x:F3}, {gt.localPosition.y:F3}, {gt.localPosition.z:F3})");
                        muzzles.Add(mz);
                        continue;
                    }
                    // stock M2 barrel mesh on our gun body transform (contract: fits 1:1, origin, +Z fwd, +Y up)
                    var mf = gb.GetComponent<MeshFilter>(); var mr = gb.GetComponent<MeshRenderer>();
                    if (mf != null && mr != null) { mf.sharedMesh = barrelMesh; mr.sharedMaterials = new[] { barrelMat }; }
                    muzzles.Add(mz);
                }
                var tl = tj["Turret"];
                int rounds = TurretRounds.TryGetValue(mount.name, out var rr) ? rr : 300;
                // gun on the elevation object (stock door gun: Gun on the barrel = elevationTransform)
                foreach (var a in tplGun.GetComponents<AudioSource>()) CloneComp(a, el.gameObject).loop = false;
                var gun = CloneComp(tplGun, el.gameObject);
                gun.attachedUnit = aircraft; gun.info = turretInfo;
                S(gun, "muzzles", muzzles.ToArray());
                S(gun, "magazineCapacity", rounds); S(gun, "magazines", 0); S(gun, "startLoaded", true);
                S(gun, "recoilTransform", null); S(gun, "spinTransform", null); S(gun, "ejectionTransform", null); S(gun, "ejectionPrefab", null);
                var ps = new List<ParticleSystem>(); foreach (var mz in muzzles) ps.AddRange(CopyMuzzleParticles(tplGun, mz));
                S(gun, "muzzleParticles", ps.ToArray());
                // turret
                var tr = CloneComp(tplTurret, az.gameObject);
                S(tr, "attachedUnit", aircraft);
                var fMode = Fld(typeof(Turret), "targetAcquisitionMode"); fMode.SetValue(tr, Enum.ToObject(fMode.FieldType, 0)); // parentUnitTargetDetector
                S(tr, "fireControl", null); S(tr, "firesWithoutAiming", false);
                SetSeq(tr, "targetDetectors", new TargetDetector[0]);
                var ws = (WeaponStation)System.Runtime.Serialization.FormatterServices.GetUninitializedObject(typeof(WeaponStation));
                ws.Weapons = new List<Weapon> { gun }; ws.Turrets = new List<Turret> { tr };
                SetSeq(tr, "weaponStations", new[] { ws });
                S(tr, "aimSafetyWeapon", gun);
                float trav = (float)tl["traverseRange"];
                float eminC = (float)tl["minElevation"], emaxC = (float)tl["maxElevation"];
                if (TurretSafeLimits.TryGetValue(mount.name, out var lim))
                {
                    L($"turret {mount.name}: safe envelope override trav {trav}->{lim.trav}, el {eminC}..{emaxC} -> {lim.emin}..{lim.emax}");
                    trav = lim.trav; eminC = lim.emin; emaxC = lim.emax;
                }
                S(tr, "traverseRate", (float)tl["traverseRate"]); S(tr, "traverseRange", trav >= 180f ? 999999f : trav);
                S(tr, "elevationRate", (float)tl["elevationRate"]); S(tr, "minElevation", eminC); S(tr, "maxElevation", emaxC);
                S(tr, "elevationTransform", el);
                // firing cone: one inclusion cone about the mount's forward (or straight up for a 360 deg turret) that
                // covers the traverse x elevation box; the stock linecast handles the rest of the airframe
                Vector3 fwd = mount.forward, up = mount.up; float cone;
                float emin = eminC, emax = emaxC;
                if (trav >= 180f) { fwd = up; cone = 90f - emin + 1f; }
                else cone = Mathf.Rad2Deg * Mathf.Acos(Mathf.Cos(trav * Mathf.Deg2Rad) * Mathf.Cos(Mathf.Max(Mathf.Abs(emin), Mathf.Abs(emax)) * Mathf.Deg2Rad)) + 1f;
                var cg = NewGO(mount.name + "_cone", mount.parent, mount.position, Quaternion.LookRotation(fwd, Mathf.Abs(Vector3.Dot(fwd, Vector3.up)) > 0.99f ? Vector3.forward : Vector3.up));
                var fc = New(typeof(FiringCone)); S(fc, "transform", cg.transform); S(fc, "coneAngle", cone); S(fc, "exclusion", false);
                SetSeq(tr, "firingCones", new[] { fc });
                S(tr, "criticalParts", new UnitPart[] { part });
                S(tr, "manual", false); S(tr, "stowed", false);
                turrets.Add((tr, gun, part, mount));
                L($"turret {az.name}: part {part.name}, mount fwd {mount.forward.ToString("F2")}, traverse {trav}, el {emin}..{emax}, {muzzles.Count} gun(s) x {rounds} rds, cone {cone:F0} deg about {fwd.ToString("F2")}");
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
            S(power, "powerSources", new[] { parts["engine_L"].gameObject, parts["engine_R"].gameObject });
            S(power, "source", cap); S(power, "aircraft", aircraft);
            S(aircraft, "powerSupply", power);
            CloneComp(coin.GetComponent<NuclearOption.NetworkTransforms.AircraftNetworkTransform>(), root);

            // fuel: B-25H main tanks in the inner wing, auxiliaries in the outer wing (2,600 L total)
            // 1.8.3 (user review item 9, stock internals study): the four tanks take the AB-4 (FastBomber1) wing-tank settings (the stock
            // bomber's fire / fireball effects and rupture / ignition thresholds) instead of the CI-22 light-aircraft tank, and a detaching
            // wing panel punctures its neighbour (inner <-> outer), as the B-17G since 1.7.6. Same parts, same capacities.
            var tplTank = BomberFuelTanks183 ? TplComp<FuelTank>("FastBomber1:wingroot_L") : coin.GetComponent<FuelTank>();
            var tanks = new Dictionary<string, FuelTank>();
            foreach (var (p, kg) in new[] { ("wing_inner_L", 600f), ("wing_inner_R", 600f), ("wing_outer_L", 336f), ("wing_outer_R", 336f) })
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
                foreach (var s in new[] { "L", "R" })
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
            foreach (var s in new[] { "L", "R" }) { doppler.Add(parts["engine_" + s].GetComponent<AudioSource>()); doppler.Add(parts["prop_" + s].GetComponent<AudioSource>()); }
            S(aircraft, "dopplerSounds", doppler);
            aircraft.maxRadius = 11f;
            aircraft.obstacleTop = 2.4f; // fin tips above the root
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
            F("gLimitPositive", 3.5f); F("cornerSpeed", 110f); F("postStallManeuverSpeed", 0f); F("maxRollSpeed", 60f);
            F("takeoffSpeed", 55f); F("pidTransitionSpeed", 100f); F("alphaLimiter", 14f);
            if (StallLimiter187F) { F("alphaLimiter", 10f); F("alphaLimiterStrength", 0.25f); }   // 1.8.7F: stall stop at the CL peak
            so.FindProperty("flyByWire.noseGear").objectReferenceValue = noseGear;
            so.ApplyModifiedPropertiesWithoutUndo();
            var ap = parts["fus_cockpit"].GetComponent<AutopilotPlane>();
            var so2 = new SerializedObject(ap);
            var rs = so2.FindProperty("forwardFlightController.referenceAirspeed"); if (rs != null) rs.floatValue = 110f;
            if (BomberAITuning)
            {
                // as the stock FastBomber1 autopilot: AutopilotPlane.AutoAim caps the AI bank at 135 deg (x0.6..1.2 by altitude)
                var pi = so2.FindProperty("preventInvertedFlight"); if (pi != null) pi.boolValue = true;
                // AoA limiter (AI pitch effort): COIN 8/12 kept; our wing stalls at 16 deg
            }
            so2.ApplyModifiedPropertiesWithoutUndo();
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
            var art = Directory.Exists(RepoUI) && !File.Exists(Path.Combine(RepoUI, "b25h_status_layout.json")) ? Directory.GetFiles(RepoUI, "*.png").FirstOrDefault(f => { var n = Path.GetFileName(f).ToLowerInvariant(); return n.Contains("diagram") || n.Contains("status") || n.Contains("damage"); }) : null;
            if (art != null)
            {
                var fitted = FitArt(art, 512, u, BIG);
                if (fitted != null) { bgPx = fitted; L($"status background: texture worker art {Path.GetFileName(art)} (bbox-fitted to the model frame)"); }
            }
            else L("status background: generated line art from the model (no assets/ui diagram art)");
            statusBackground = SaveSprite(bgPx, 512, "b25h_status", false);

            // one filled sprite per part (256, 2x supersampled)
            const int PB = 512;
            for (short k = 0; k < plist.Count; k++)
            {
                var r = new Raster(PB);
                foreach (var (a, b, c) in PartTriangles(plist[k])) r.Tri(a, b, c, k);
                var px = Downsample(i => r.id[i] >= 0, PB, 2);
                statusParts[plist[k].name] = SaveSprite(px, 256, "b25h_status_" + plist[k].name, true);
                // centre of the part's own silhouette, for failure indicators
                double sx = 0, sy = 0; int cnt = 0;
                for (int i = 0; i < r.id.Length; i++) if (r.id[i] >= 0) { sx += i % PB; sy += i / PB; cnt++; }
                diagramPos[plist[k].name] = cnt > 0 ? new Vector2((float)(sx / cnt / PB - 0.5), (float)(sy / cnt / PB - 0.5)) : Vector2.zero;
            }

            // map icon: filled silhouette, 256 (texture worker's icon when present)
            var icon = Path.Combine(RepoUI, "b25h_map_icon.png");
            if (File.Exists(icon)) { mapIconSprite = ImportRepoSprite(icon, "b25h_mapicon"); L("map icon: texture worker art b25h_map_icon.png"); }
            else { mapIconSprite = SaveSprite(Downsample(i => u.id[i] >= 0, BIG, 4), 256, "b25h_mapicon", false); L("map icon: generated silhouette from the model"); }
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
            var inst = new GameObject("B25H_statusDisplay", typeof(RectTransform)) { layer = 5 };
            var rt = (RectTransform)inst.transform;
            rt.anchorMin = rt.anchorMax = new Vector2(1f, 0f); rt.pivot = new Vector2(1f, -0.05f); rt.sizeDelta = new Vector2(300f, 300f); rt.anchoredPosition = new Vector2(0f, -30.1f);
            var list = new List<PartStatusDisplay>();
            var failures = new List<GameObject>();
            UnityEngine.UI.Image rootImg;
            StatusDisplay sd;
            Vector2 V2(Newtonsoft.Json.Linq.JToken t) => new Vector2((float)t[0], (float)t[1]);
            var layoutPath = Path.Combine(RepoUI, "b25h_status_layout.json");
            var covered = new HashSet<string>();
            if (File.Exists(layoutPath))
            {
                // texture worker's art + layout (assets/ui/b25h_status_layout.json): stock-style per-part sprites, mirrored L/R
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
                var part = "engine_" + (fname.StartsWith("LEFT") ? "L" : "R");
                grt.anchoredPosition = diagramPos.TryGetValue(part, out var dp) ? dp * rt.sizeDelta.x : Vector2.zero;
                Img(g, null, Color.red).preserveAspect = false;
                failures.Add(g);
            }
            SetSeq(sd, "failureIndicators", failures);
            var fnames = string.Join(", ", failures.Select(f => f.name));
            var prefab = PrefabUtility.SaveAsPrefabAsset(inst, Folder + "/B25H_statusDisplay.prefab");
            Object.DestroyImmediate(inst);
            L($"status display prefab: {list.Count} part images, failure indicators {fnames}");
            return prefab;
        }

        // =================================================================== assets
        static GameObject SaveEverything()
        {
            // mesh bank (one asset, our meshes as sub-assets)
            var bank = Folder + "/Generated/B25H_meshes.asset";
            AssetDatabase.CreateAsset(generatedMeshes[0], bank);
            foreach (var m in generatedMeshes.Skip(1)) AssetDatabase.AddObjectToAsset(m, bank);

            // airfoils: chart convention measured from AeroJob_Math: alpha = atan2(v.y, v.z) of the part's motion in the
            // liftNormal frame, lift = -cross(v, right) * CL, so nose-up angles are NEGATIVE alpha and lift-up needs
            // NEGATIVE CL. Physical curves below are written nose-up-positive and mirrored (t,v) -> (-t,-v).
            var coinParams = Asset<AircraftParameters>("MonoBehaviour/COINParameters_PLACEHOLDER.asset");
            var drag = coinParams.airfoils[0].dragCoef;
            var wing = new Airfoil { name = "B25H_NACA23017", liftCoef = Mirror(new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.95f), (-0.36f, -0.80f), (-0.24f, -0.95f), (0f, 0.15f), (0.15f, 0.85f), (0.28f, 1.45f), (0.35f, 1.10f), (0.5f, 0.90f), (0.785f, 0.95f), (1.571f, 0f), (3.142f, 0f) }), dragCoef = WingDrag() };
            var tail = new Airfoil { name = "B25H_tail", liftCoef = Mirror(new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.9f), (-0.45f, -0.8f), (-0.3f, -1.1f), (0f, 0f), (0.3f, 1.1f), (0.45f, 0.8f), (0.785f, 0.9f), (1.571f, 0f), (3.142f, 0f) }), dragCoef = new AnimationCurve(drag.keys) };

            // liveries (mod-local LiveryData, referenced by GUID)
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
            // every livery is offered to both factions (the hangar only lists the player's faction's entries, so with one
            // faction per livery a BDF player saw 2 of the 4); each faction's own two come first so its default is unchanged
            foreach (var side in new[] { "BDF", "PALA" })
                foreach (var (file, label, fac, _) in Liveries.Where(x => x.both && x.faction == side).Concat(Liveries.Where(x => x.both && x.faction != side)).Concat(Liveries.Where(x => !x.both && x.faction == side)))
                    livs.Add(new AircraftParameters.Livery { name = label, faction = side == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(livGuid[file]) });

            // twin-engine attack aircraft parameters (A-19) as the starting point: twin-engine status display, AoA audio
            var prm = Object.Instantiate(Asset<AircraftParameters>("MonoBehaviour/CAS1Parameters_PLACEHOLDER.asset"));
            // HUD readouts (speed, radar/baro altitude, climb, AoA, throttle, fuel, G, gear, weapon, countermeasures, bearing) are
            // HUDApps inside the per-aircraft HUDExtras prefab, instantiated under FlightHud's HUD centre by
            // Aircraft.SetupLocalPlayerAndUI (Aircraft.cs:1281). 1.0 set it to null => only the pitch ladder/heading tape remained.
            // The CI-22 (prop aircraft) uses COIN_HUDExtras (HUDAppManager + SpeedGauge, Altitude, Climbrate, AoADisplay,
            // ThrottleGauge, FuelGauge, GIndicators, GearIndicator, WeaponIndicator, CountermeasureIndicator, RadarWarning, Bearing...).
            prm.HUDExtras = StockHUDExtras ? Asset<GameObject>("GameObject/COIN_HUDExtras_PLACEHOLDER.prefab") : null;
            prm.name = "B25H_Parameters";
            if (OwnStatusDisplay || OwnMapIcon) BuildDiagramSprites();
            if (OwnStatusDisplay) prm.StatusDisplay = BuildStatusDisplayPrefab(); // 1.0 kept the A-19 diagram (CAS1_statusDisplay)
            prm.aircraftName = DisplayName; prm.rankRequired = 2;
            prm.airfoils = new[] { wing, tail };
            prm.liveries = livs;
            var bombs = Mount("bomb_500_internalx2"); var pods = Mount("RocketPod1_single"); var rack250 = Mount("bomb_250_single");
            // one entry per hardpoint set; the turret set (if built) is last so 1.0 loadout indices are unchanged
            NuclearOption.SavedMission.Loadout LO(params WeaponMount[] w) => new NuclearOption.SavedMission.Loadout { weapons = (ammoTurrets != null ? w.Concat(new[] { ammoTurrets }) : w).ToList() };
            prm.loadouts = new List<NuclearOption.SavedMission.Loadout>
            {
                new NuclearOption.SavedMission.Loadout { weapons = Enumerable.Repeat<WeaponMount>(null, ammoTurrets != null ? 6 : 5).ToList() },
                LO(ammoCannon, ammo50, bombs, null, pods),
            };
            prm.StandardLoadouts = new[]
            {
                new StandardLoadout { Name = "Gunship", loadout = LO(ammoCannon, ammo50, null, null, pods), FuelRatio = 0.6f },
                new StandardLoadout { Name = "Low-level bomber", loadout = LO(ammoCannon, ammo50, bombs, rack250, null), FuelRatio = 0.6f },
                new StandardLoadout { Name = "Anti-shipping", loadout = LO(ammoCannon, ammo50, bombs, null, pods), FuelRatio = 0.7f },
            };
            prm.DefaultFuelLevel = 0.6f;
            prm.aircraftGLimit = 3.5f; prm.PIDReferenceAirspeed = 110f; prm.maxSpeed = 123f; prm.takeoffSpeed = 55f; prm.takeoffDistance = 700f;
            prm.turningRadius = 1600f; prm.cornerSpeed = 110f; prm.approachSpeed = 70f; prm.landingSpeed = 58f; prm.shortLandingSpeed = 55f;
            prm.cruiseThrottle = 0.85f; prm.minimumRadarAlt = 120f; prm.groundTurningRadius = 20f;
            if (BomberAITuning)
            {
                // AI altitude floor: AIPilotCombatModes.ManageAltitude lerps the AI's target height up to minimumRadarAlt every
                // second, and an attack run with a visible ground target otherwise sinks it by 5-10 m/s down to that floor; it is
                // the cruise/attack height above terrain (followTerrain) for every non-evasive mode. Stock: CI-22 30, A-19 50,
                // Darkreach (FastBomber1) / SFB 100. A 3.5 g bomber needs more margin over ridges.
                // 450 since the 1.1.0 test: with the fixed cannon usable (boresight) the AI strafes; its next pass starts from
                // the speed-scaled hold height (AutoAim, ~0.65 x at 80 m/s), which at 300 was 70-150 m AGL, and a pass begun at
                // 70 m ended in the ground at the target. From 600 m the first pass broke off at 170 m AGL. 450 -> ~290 m.
                prm.minimumRadarAlt = AIFloorStock181 ? 150f : 450f;   // 1.8.1: see AIFloorStock181
                // turningRadius: RetreatToStandoff distance (2x) and the landing pattern (glideslope aimpoint 3x, AIPilotLandingState).
                prm.turningRadius = 2000f;
                // aircraftGLimit stays 3.5: TerrainWarningSystem looks ahead max(speed,100) * 6 * (9 / gLimit) m, i.e. 15 s at 3.5 g.
                // landingSpeed also scales every AI terrain-following height: AutopilotPlane.AutoAim multiplies altitudeHold by
                // lerp(0.1, 1, (airspeed - 0.9 landingSpeed) / landingSpeed), full only above 1.9 x landingSpeed. At 58 that is
                // 110 m/s (our cruise), and just after take-off (60-75 m/s) the AI held 0.2-0.45 of its target height: in game
                // (1.1.0 test) it sank from 77 m to 20-30 m AGL and flew the landing pattern at 20-40 m AGL. 52 (CI-22: 50) gives
                // full height from 99 m/s; landing approach = sqrt(m/mMax) x 52 = 47-52 m/s (flaps down), the middle between 50 and 58.
                prm.landingSpeed = 52f;
                // 1.8.6F: the 3.5 look-ahead above was the cause of the low legs (the AI flies alpha x look-ahead below its hold; see
                // AITerrain186F). Look-ahead 600 m (aircraftGLimit 9, terrain look-ahead only) and floor 250; landingSpeed stays 52.
                if (AITerrain186F) { prm.aircraftGLimit = AIGLimit186F; prm.minimumRadarAlt = AIFloor186F; }
            }
            AssetDatabase.CreateAsset(prm, Folder + "/B25H_Parameters.asset");

            float total = parts.Values.Sum(p => p.mass);
            var def = Object.Instantiate(Asset<AircraftDefinition>("MonoBehaviour/CI-22_PLACEHOLDER.asset"));
            def.name = "B25H";
            def.jsonKey = JsonKey; def.WorkshopTag = DisplayName; def.unitName = DisplayName; def.code = "B-25H"; def.bogeyName = "";
            def.description = "North American B-25H Mitchell, 1944. The solid-nose gunship Mitchell built for low-level attack on ships and " +
                "ground targets: a 75 mm T13E1 (M5) cannon fed by hand (21 rounds), four fixed .50 calibre guns in the nose and four in fuselage " +
                "packages, a bomb bay for up to 3,000 lb and eight 5-inch HVAR rails under the wings. Two 1,700 hp Wright R-2600 Cyclones, " +
                "a gull wing and twin fins make it stable and forgiving; crew of five.";
            def.length = 15.54f; def.width = 20.6f; def.height = 4.98f; def.mass = total;
            def.value = 24f; def.radarSize = 0.9f; def.visibleRange = 4500f; def.manpower = 5;
            def.roleIdentity.antiSurface = 0.85f; def.roleIdentity.antiAir = 0.15f;
            def.spawnOffset = new Vector3(0f, SpawnHeight, 0f);
            def.restRotation = Vector3.zero;
            def.aircraftParameters = prm;
            if (OwnMapIcon) { def.mapIcon = mapIconSprite; def.mapIconSize = 1.2f; def.mapOrient = true; } // 1.0 kept the CI-22 icon (mapIcon_cricket); A-19 uses 1.1
            def.aircraftInfo = new AircraftInfo { emptyWeight = 9060f, maxSpeed = 443f, stallSpeed = 150f, maneuverability = 4f, maxWeight = 15900f };
            def.unitPrefab = null;
            AssetDatabase.CreateAsset(def, Folder + "/B25H.asset");


            foreach (var u in root.GetComponentsInChildren<Unit>(true)) u.definition = def;
            var rb = root.GetComponent<Rigidbody>(); rb.mass = total;
            if (FireClear1814On && DefensiveTurrets) FireClear1814.Apply(root, L, FireClearJson);   // 1.8.14: after colliders / meshes / guns are final
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, Folder + "/B25H.prefab");
            def.unitPrefab = prefab;
            EditorUtility.SetDirty(def);

            var op = ScriptableObject.CreateInstance<Blueprinter.OpAddAircraftToHangars>();
            op.aircraftJsonKey = JsonKey;
            op.hangars.Add(new Blueprinter.OpAddAircraftToHangars.HangarTarget { hangarUnitJsonKey = "hangar_med", hangarNames = { "hangar_med" } });
            op.hangars.Add(new Blueprinter.OpAddAircraftToHangars.HangarTarget { hangarUnitJsonKey = "revetment1", hangarNames = { "revetment1" } });
            AssetDatabase.CreateAsset(op, Folder + "/OpAddAircraftToHangars.asset");
            AssetDatabase.SaveAssets();
            L($"saved prefab, definition (mass {total} kg), parameters, {livs.Count} liveries, {generatedMeshes.Count} meshes");
            return prefab;
        }

        // b25h_liveries.json (textures worker): {"usaaf_od": {"texture":..., "glossiness": 0.0, "colors": [{"color":"#RRGGBBAA","count":n},...]}, ...}
        static (float, LiveryData.TextureColor[]) LiveryJson(string file)
        {
            var path = Path.Combine(RepoTextures, "b25h_liveries.json");
            if (!File.Exists(path)) return (0.2f, new LiveryData.TextureColor[0]);
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(path));
            Newtonsoft.Json.Linq.JObject e = null;
            foreach (var kv in jo)
                if (kv.Value is Newtonsoft.Json.Linq.JObject o && (kv.Key == file.Replace("b25h_livery_", "") || Path.GetFileNameWithoutExtension((string)o["texture"] ?? "") == file)) { e = o; break; }
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
                    var ag = AtlasGuard1816.Check(inst, mats["paint"], Path.Combine(RepoTextures, "b25h_atlas_manifest.json"), null);
                    R("1.8.16 livery atlas: UV0 of the paint meshes == the texture manifest (textures painted on this atlas, files unchanged)", ag.Item1, ag.Item2);
                }
                var ac = inst.GetComponent<Aircraft>();
                var allParts = inst.GetComponentsInChildren<AeroPart>(true);
                var modFolderAbs = Folder;
                bool OurAsset(Object o) { var p = AssetDatabase.GetAssetPath(o); return p.StartsWith(Folder) ; }

                // props
                var props = inst.GetComponentsInChildren<ConstantSpeedProp>(true);
                var hubs = props.Select(p => (GameObject)G(p, "hubVisible")).ToList();
                R("two ConstantSpeedProps drive two distinct hubs", props.Length == 2 && hubs.All(h => h != null) && hubs.Distinct().Count() == 2,
                    string.Join(", ", props.Select(p => $"{p.name}->{((GameObject)G(p, "hubVisible"))?.name} turn={G(p, "turnDirection")} blades={((IList)G(p, "blades")).Count} transmission={((Transmission)G(p, "transmission"))?.name}")));
                var trs = props.Select(p => (Transmission)G(p, "transmission")).ToList();
                R("each prop has its own Transmission + TurbineEngine", trs.Distinct().Count() == 2 && trs.All(t => t != null && t.GetComponent<TurbineEngine>() != null && ((GameObject[])G(t, "powerSources")).Single() == t.gameObject), string.Join(", ", trs.Select(t => t?.name)));
                R("each prop has its own PropStrikeDetector (trigger, layer 15)", props.All(p => G(p, "propStrikeDetector") is PropStrikeDetector d && d.gameObject.layer == 15 && ((Collider)G(p, "propDiscCollider")).isTrigger), "");
                foreach (var p in props)
                    foreach (var b in (IList)G(p, "blades"))
                    {
                        var bt = (Transform)G(b, "transform"); var lt = (Transform)G(b, "liftTransform");
                        if (bt.parent != ((GameObject)G(p, "hubVisible")).transform || Mathf.Abs(lt.localPosition.x) > 1e-3f || lt.localPosition.z < 1.5f)
                        { R($"blade {bt.name} geometry", false, $"parent {bt.parent.name} lift local {lt.localPosition}"); }
                    }

                // wheels
                foreach (var g in inst.GetComponentsInChildren<LandingGear>(true))
                {
                    var wheel = ((Transform[])G(g, "wheels"))[0];
                    var axle = (Transform)G(g, "axle");
                    var mb = wheel.GetComponent<MeshFilter>().sharedMesh.bounds;
                    float dPivot = Vector3.Distance(wheel.position, axle.position);
                    float dMesh = Vector3.Distance(wheel.TransformPoint(mb.center), wheel.position);
                    var bump = ((GameObject)G(g, "bumpStop")).transform;
                    float r = (float)G(g, "wheelRadius"), travel = (float)G(g, "suspensionTravel");
                    float bottom = axle.position.y - r;
                    R($"wheel {wheel.name} centred on axle", dPivot < 0.01f && dMesh < 0.01f, $"pivot-axle {dPivot * 1000:F1} mm, mesh centre-pivot {dMesh * 1000:F1} mm, r={r:F3}, bottom y={bottom:F3}, bumpstop-axle {(bump.position - axle.position).y:F3} (travel-r {travel - r:F3}), hinge euler {((Transform)G(g, "gearHinge")).localEulerAngles}");
                    var doors = (List<LandingGear.GearDoor>)G(g, "gearDoors");
                    R($"gear {g.name} doors", doors.Count == 2 && doors.All(d => d.transform != null), string.Join(", ", doors.Select(d => $"{d.transform.name} open {d.openAngle.z}")));
                }
                var steer = inst.GetComponentsInChildren<LandingGear>(true).Where(x => (bool)G(x, "steering")).ToList();
                R("nose wheel steers, mains brake", steer.Count == 1 && steer[0].name.Contains("nose") && inst.GetComponentsInChildren<LandingGear>(true).Count(x => (bool)G(x, "braked")) == 2, "");

                // hardpoints
                var wm = ac.weaponManager;
                bool hpOk = wm.hardpointSets.All(s => s.hardpoints.All(h => h.part != null && h.transform != null));
                R("every hardpoint has a part + transform", hpOk, string.Join(" | ", wm.hardpointSets.Select(s => $"{s.name}: " + string.Join(",", s.hardpoints.Select(h => $"{h.transform?.name}@{h.part?.name}")))));
                var bayset = wm.hardpointSets.FirstOrDefault(s => s.name == "Bomb Bay");
                R("bomb bay hardpoint has 2 bay doors", bayset != null && bayset.hardpoints[0].bayDoors.Length == 2 && bayset.hardpoints[0].bayDoors.All(d => d != null), bayset == null ? "" : string.Join(",", bayset.hardpoints[0].bayDoors.Select(d => $"{d.name} hinge {G(d, "hingeAngle")}")));
                R("loadout sets", wm.hardpointSets.Select(s => s.name).SequenceEqual(new[] { "75mm T13E1 Cannon", "Internal guns", "Bomb Bay", "Wing Racks", "Rocket Rails" }.Concat(DefensiveTurrets ? new[] { "Defensive turrets" } : new string[0])), string.Join(", ", wm.hardpointSets.Select(s => $"{s.name}[{string.Join("/", s.weaponOptions.Skip(1).Select(o => o ? o.name.Replace("_PLACEHOLDER", "") : "null"))}]")));

                // gun audio
                var guns = inst.GetComponentsInChildren<Gun>(true);
                var loopers = new List<string>();
                foreach (var gn in guns) foreach (var a in gn.GetComponents<AudioSource>()) if (a.loop) loopers.Add($"{gn.name}:{a.clip?.name}");
                var cannon75 = guns.FirstOrDefault(g => g.name == "cannon_mount");
                R("no gun AudioSource has loop=true", loopers.Count == 0, loopers.Count == 0 ? $"{guns.Length} guns" : string.Join(",", loopers));
                R("T13E1 cannon is single-shot (1 AudioSource, fireSounds)", cannon75 != null && cannon75.GetComponents<AudioSource>().Length == 1 && ((AudioClip[])G(cannon75, "fireSounds")).Length > 0,
                    cannon75 == null ? "missing" : $"sources {cannon75.GetComponents<AudioSource>().Length}, fireSounds {string.Join("/", ((AudioClip[])G(cannon75, "fireSounds")).Select(c => c ? c.name : "null"))}, ammo {(int)G(cannon75, "magazineCapacity") * (1 + (int)G(cannon75, "magazines"))}");
                R(".50s: 8 barrels, 400 rpg", guns.Where(g => g.name.Contains("50cal")).Sum(g => ((Transform[])G(g, "muzzles")).Length) == 8 && guns.Where(g => g.name.Contains("50cal")).All(g => (int)G(g, "magazineCapacity") == 400), "");
                if (ANM2Guns)
                {   // 1.8.13: 6 AN/M2 bodies on the turret / waist slots (dorsal twin L + R no grips, tail twin L + R with grips, waist singles with grips), no stock door-gun barrel
                    var ab = inst.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("B25H_anm2_") && !f.sharedMesh.name.EndsWith("grips")).ToList();
                    bool kinds = ab.All(f => f.name.StartsWith("gun_turret_") == f.sharedMesh.name.Contains("_turret_"));     // round 2: dorsal = turret guns, tail / waist = flexible
                    int ag = inst.GetComponentsInChildren<MeshFilter>(true).Count(f => f.sharedMesh != null && (f.sharedMesh.name == "B25H_anm2_grips" || f.sharedMesh.name == "B25H_anm2_twin_grips"));   // r3: waists 2 + the tail's one shared set
                    bool noStock = !inst.GetComponentsInChildren<MeshFilter>(true).Any(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("50cal"));
                    bool dorsal = ab.Count(f => f.name.StartsWith("gun_turret_") && f.transform.childCount == 0) == 2 && ab.Any(f => f.name.StartsWith("gun_turret_L") && f.sharedMesh.name.EndsWith("_L")) && ab.Any(f => f.name.StartsWith("gun_turret_R") && f.sharedMesh.name.EndsWith("_R"));
                    R("1.8.13 AN/M2 on the 6 turret / waist slots (dorsal twin L + R without grips, tail twin with one shared grip set, waists with grips), no stock door-gun barrel left", ab.Count == 6 && ag == 3 && noStock && dorsal && kinds,
                        $"{ab.Count} bodies, {ag} grips, stock barrels {(noStock ? 0 : 1)}: " + string.Join(", ", ab.Select(f => f.name + "=" + f.sharedMesh.name.Substring(f.sharedMesh.name.Length - 1))));
                }
                var otherLoops = inst.GetComponentsInChildren<AudioSource>(true).Where(a => a.loop).Select(a => $"{a.name}:{a.clip?.name}").ToList();
                L("looping AudioSources (expected: engines, props, tyres, capacitor): " + string.Join(", ", otherLoops));

                // renderers: our materials, our meshes (exempt: crew figure, particle effects)
                var bad = new List<string>();
                foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
                {
                    if (r is ParticleSystemRenderer) continue;
                    if (r is SkinnedMeshRenderer && r.GetComponentInParent<Pilot>() != null) continue;
                    // allowed stock assets: the M2 barrel mesh + its material on the turret guns, the tac-screen material on the MFDs
                    bool StockOk(Object o) { var ap = AssetDatabase.GetAssetPath(o); return ap.Contains("50cal_doorGun_barrel_PLACEHOLDER") || ap.Contains("utilityHelo1_attachments_PLACEHOLDER") || ap.Contains("tacScreenDisplay_PLACEHOLDER") || ap.Contains("targetCamDisplay_PLACEHOLDER") || (StockStructure.Enabled && ap.Contains("aircraft_structure_PLACEHOLDER")); }   // 1.8.3: stock internals material
                    foreach (var m in r.sharedMaterials) if (m == null || !(OurAsset(m) || StockOk(m))) bad.Add($"{r.name}:mat {(m ? AssetDatabase.GetAssetPath(m) : "null")}");
                    var mf = r.GetComponent<MeshFilter>();
                    if (mf != null && mf.sharedMesh != null && !(OurAsset(mf.sharedMesh) || StockOk(mf.sharedMesh))) bad.Add($"{r.name}:mesh {AssetDatabase.GetAssetPath(mf.sharedMesh)}");
                }
                R("every airframe renderer uses our meshes + materials", bad.Count == 0, bad.Count == 0 ? $"{inst.GetComponentsInChildren<MeshRenderer>(true).Length} mesh renderers" : string.Join("; ", bad.Take(20)));
                foreach (var cs in inst.GetComponentsInChildren<ConstantSpeedProp>(true))
                    foreach (var m in (Mesh[])G(cs, "bladeDamageMeshes")) if (!OurAsset(m)) bad.Add("blade damage mesh " + m.name);
                var colsBad = inst.GetComponentsInChildren<MeshCollider>(true).Where(c => !c.convex || !OurAsset(c.sharedMesh)).Select(c => c.name).ToList();
                R("every MeshCollider convex, from our meshes", colsBad.Count == 0, $"{inst.GetComponentsInChildren<MeshCollider>(true).Length} mesh colliders {string.Join(",", colsBad)}");

                // mass and balance
                float total = allParts.Sum(p => p.mass);
                var def = ac.definition as AircraftDefinition;
                R("total mass matches definition (9,300 kg target)", Mathf.Abs(total - def.mass) < 1f && Mathf.Abs(total - 9300f) < 50f, $"parts {total} kg, def {def.mass} kg, {allParts.Length} parts");
                Vector3 com = Vector3.zero;
                foreach (var p in allParts)
                {
                    var c = p.GetComponent<MeshCollider>();
                    var pos = c != null ? p.transform.TransformPoint(c.sharedMesh.bounds.center) : p.transform.position;
                    com += pos * p.mass;
                }
                com /= total;
                float mainZ = -0.3461f, groundY = -2.588f;
                float tip = Mathf.Atan2(com.z - mainZ, com.y - groundY) * Mathf.Rad2Deg;
                R("CoM well ahead of main wheels (tip-back > 10 deg)", tip > 10f, $"empty CoM {com.ToString("F3")} (collider-centroid estimate), {com.z - mainZ:F2} m ahead of main axle, tip-back angle {tip:F1} deg, nose wheel load {(com.z - mainZ) / (4.0539f - mainZ) * 100:F0}%");

                // liveries mod-local
                var prm = def.aircraftParameters;
                var livBad = prm.liveries.Where(l => !AssetDatabase.GUIDToAssetPath(l.assetReference.AssetGUID).StartsWith(Folder)).Select(l => l.name).ToList();
                R("liveries are mod-local LiveryData", prm.liveries.Count > 0 && livBad.Count == 0, string.Join(", ", prm.liveries.Select(l => $"{l.name} ({l.faction?.name})")));

                // structure
                R("every AeroPart parent is a part (detach works)", allParts.All(p => p.transform == inst.transform || p.transform.parent.GetComponent<AeroPart>() != null), string.Join(",", allParts.Where(p => p.transform != inst.transform && p.transform.parent.GetComponent<AeroPart>() == null).Select(p => p.name)));
                R("every Unit.definition set", inst.GetComponentsInChildren<Unit>(true).All(u => u.definition == def), "");
                R("NetworkIdentity present (real Mirage)", inst.GetComponent<Mirage.NetworkIdentity>() != null, "");
                var csurf = inst.GetComponentsInChildren<ControlSurface>(true);
                var aeroCS = csurf.Where(c => ((GameObject)G(c, "visibleMesh")).name.Contains("liftNormal") || ((GameObject)G(c, "visibleMesh")).name.EndsWith("_hinge")).ToArray();
                R("control surfaces (aerodynamic)", aeroCS.Length == 6, string.Join(", ", aeroCS.Select(c => $"{c.name} p{G(c, "pitchRange")} r{G(c, "rollRange")} y{G(c, "yawRange")} axis{((GameObject)G(c, "visibleMesh")).transform.right.ToString("F2")}")));
                R("flaps (HighLiftDevice with area)", inst.GetComponentsInChildren<HighLiftDevice>(true).Count(h => (float)G(h, "deployedArea") > 0f) == 4, "");
                R("airfoils", prm.airfoils.Length == 2 && allParts.All(p => (int)G(p, "airfoil") < 2), string.Join(", ", prm.airfoils.Select(a => $"{a.name}: CL(0)={a.liftCoef.Evaluate(0):F2} CL(-0.28)={a.liftCoef.Evaluate(-0.28f):F2} CL(+0.24)={a.liftCoef.Evaluate(0.24f):F2}")));
                R("fuel", Mathf.Abs(inst.GetComponentsInChildren<FuelTank>(true).Sum(f => (float)G(f, "fuelCapacity")) - FuelKg) < 1f, $"{inst.GetComponentsInChildren<FuelTank>(true).Length} tanks");
                {   // 1.8.3 (user review item 9): stock internals
                    var ftk = inst.GetComponentsInChildren<FuelTank>(true);
                    bool linked = ftk.Length == 4 && ftk.All(f => ((FuelTank[])G(f, "connectedTanks")).Length == 1) && ftk.All(f => (float)G(f, "ruptureGMin") >= 49f && (float)G(f, "ruptureGMin") <= 51f);
                    R("1.8.3 fuel: 4 wing tanks (inner / outer, both sides) with the AB-4 wing-tank settings (rupture 50 g), inner <-> outer linked",
                      !BomberFuelTanks183 || linked, string.Join("; ", ftk.Select(f => $"{f.name} {G(f, "fuelCapacity")} kg rupt {G(f, "ruptureGMin")} links {((FuelTank[])G(f, "connectedTanks")).Length}")));
                    var rs_ = inst.GetComponentsInChildren<MeshRenderer>(true);
                    var ourStruct = rs_.Where(r_ => r_.gameObject.layer != 3 && r_.sharedMaterials.Any(m_ => m_ != null && m_.name == "B25H_structure")).Select(r_ => r_.name).ToList();
                    var stockStruct = rs_.Where(r_ => r_.sharedMaterials.Any(m_ => StockStructure.IsStructMat(m_))).ToList();
                    bool vcolS = stockStruct.All(r_ => { var mm = r_.GetComponent<MeshFilter>().sharedMesh; return mm.colors32.Length == mm.vertexCount; });
                    R("1.8.3 internals: frames / ribs / stubs drawn with the stock aircraft_structure (vertex colour), none left on our tiled structure material",
                      !StockStructure.Enabled || (ourStruct.Count == 0 && stockStruct.Count > 0 && vcolS), $"{stockStruct.Count} stock-structure renderers ({stockStruct.Sum(r_ => r_.GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3)} tris), our structure left on: {string.Join(", ", ourStruct.Take(6))}");
                }
                {   // 1.8.5 offline E (in-game 1.8.3 F1): internals look - stock vertex colours kept, drawn with the stock textures on the matte look material
                    bool okL = B25HTools.StockStructure.CheckLook(inst, out string msgL);
                    R("1.8.5 E internals look: every internals submesh carries a stock exterior-structure vertex grey (87-118, alpha 255) and is drawn with <prefix>_structure_look (URP Lit, the stock aircraft_structure_b / _n / _ao textures, neutral light grey, metallic <= 0.15); none left on the reflective stock material",
                        okL, msgL);
                }
                var eye = inst.GetComponentsInChildren<Transform>(true).First(t => t.name == "cockpit_eye");
                {   // 1.8.1: no exterior glass drawn in cockpit view in front of the pilot; cockpit-layer glass is the faint glass_ck, never canopy_int
                    var ackR = (Renderer[])G(ac, "cockpitRenderers"); var aexR = (Renderer[])G(ac, "exteriorRenderers");
                    var cgl = inst.GetComponentsInChildren<MeshRenderer>(true).FirstOrDefault(r => r.name == "canopy_glass");
                    var cglInt = ackR.FirstOrDefault(r => r != null && r.name == "canopy_glass_int");
                    var ckGlass = ackR.Where(r => r != null).SelectMany(r => r.sharedMaterials).Where(m => m != null && m.name.Contains("glass")).Select(m => m.name).Distinct().ToList();
                    R("1.8.1 canopy glass as stock COIN: exterior canopy_glass in exteriorRenderers (hidden in cockpit view), canopy_glass_int on layer 3 with B25H_glass_ck (alpha <= 0.08), no B25H_glass_int in the cockpit",
                        !CanopyGlassInterior181 || (cgl != null && aexR.Contains(cgl) && cglInt != null && cglInt.gameObject.layer == 3 && cglInt.sharedMaterials.All(m => m.name == "B25H_glass_ck" && m.GetColor("_BaseColor").a <= 0.08f) && !ckGlass.Contains("B25H_glass_int")),
                        $"canopy_glass {(cgl == null ? "missing" : aexR.Contains(cgl) ? "in exteriorRenderers" : "NOT hidden")}, copy {(cglInt == null ? "none" : cglInt.gameObject.layer + " " + string.Join("/", cglInt.sharedMaterials.Select(m => m.name)))}; cockpit glass materials {string.Join(", ", ckGlass)}");
                }
                R("cockpit view point at cockpit_eye", Vector3.Distance(ac.cockpitViewPoint.position, eye.position) < 0.01f && Vector3.Angle(ac.cockpitViewPoint.forward, Vector3.forward) < 2f, $"{ac.cockpitViewPoint.name} {ac.cockpitViewPoint.position.ToString("F3")}");
                var pilot = ac.pilots[0];
                R("pilot: bail-out (no ejection seat), figure present", !(bool)G(pilot, "ejectionSeat") && G(pilot, "skinnedMeshRenderer") != null && G(pilot, "animator") != null, "");
                // ================= 1.1.0 rows
                // 1 HUD + screens
                var hx = prm.HUDExtras;
                R("HUD: HUDExtras = stock COIN_HUDExtras (speed/alt/AoA/throttle/fuel/G apps)", !StockHUDExtras || (hx != null && AssetDatabase.GetAssetPath(hx).Contains("COIN_HUDExtras")), hx == null ? "null" : AssetDatabase.GetAssetPath(hx));
                var ck = inst.GetComponentInChildren<global::Cockpit>(true);
                var tacR = ck == null ? null : (Renderer)G(ck, "tacScreenRender");
                var tcam = ac.targetCam;
                var tcR = tcam == null ? null : (Renderer)G(tcam, "targetScreenRenderer");
                bool stockScreenMat(Renderer r) => r != null && r.sharedMaterials.Length > 0 && r.sharedMaterials[0] != null && AssetDatabase.GetAssetPath(r.sharedMaterials[0]).Contains("tacScreenDisplay");
                R("Cockpit + TargetCam wired like the CI-22 (one real screen, stock tacScreenDisplay material, tac-screen UI prefab)",
                    ck != null && G(ck, "tacScreenUIPrefab") != null && tacR != null && tacR == tcR && (!MFDScreens || (stockScreenMat(tacR) && tacR.enabled)) && inst.GetComponentsInChildren<Transform>(true).All(t => t.name != "screen_dummy"),
                    $"tacScreenRender {tacR?.name} ({(tacR ? AssetDatabase.GetAssetPath(tacR.sharedMaterial) : "-")}, enabled {tacR?.enabled}), targetScreenRenderer {tcR?.name}, ui {(ck ? ((GameObject)G(ck, "tacScreenUIPrefab"))?.name : "-")}");
                var screens = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.gameObject.layer != 3 && stockScreenMat(r)).ToList();
                R("MFD screen quads show the tac screen", !MFDScreens || screens.Count >= 1, string.Join(", ", screens.Select(r => r.name)));
                var tacMeshes = screens.Select(r => r.GetComponent<MeshFilter>()?.sharedMesh).Where(m => m != null).ToList();
                R("tac screens show the side panels upright (map quad + 3 rotated-UV panel quads + black backing)",
                    !TacScreenPanels || (tacMeshes.Count >= 2 && tacMeshes.All(m => m.subMeshCount == 2 && m.GetTriangles(0).Length == 24 && m.uv.Any(u => u.x > 0.95f))),
                    string.Join(", ", tacMeshes.Select(m => $"{m.name} sub {m.subMeshCount} tris {m.GetTriangles(0).Length / 3}")));
                R("TargetCam + LaserDesignator + TargetDetector (EOTS) present", tcam != null && inst.GetComponentInChildren<LaserDesignator>(true) != null && ac.EOTS != null, "");

                // 2 cockpit animation
                var visCS = csurf.Where(c => !(((GameObject)G(c, "visibleMesh")).name.Contains("liftNormal") || ((GameObject)G(c, "visibleMesh")).name.EndsWith("_hinge"))).ToList();
                var pedObjs = inst.GetComponentsInChildren<Transform>(true).Count(t => t.name.StartsWith("cockpit_rudder_pedals"));
                R("no rudder pedals (user review 2: removed from all three aircraft)", !RemovePedals || pedObjs == 0, $"{pedObjs} pedal objects");
                R(RemovePedals ? "cockpit controls animated (ControlSurface visual pivots: columns pitch, yokes roll)" : "cockpit controls animated (ControlSurface visual pivots: columns pitch, yokes roll, pedals yaw)", !CockpitAnimators || visCS.Count >= (RemovePedals ? 2 : 3),
                    string.Join(", ", visCS.Select(c => $"{((GameObject)G(c, "visibleMesh")).name} p{G(c, "pitchRange")} r{G(c, "rollRange")} y{G(c, "yawRange")}")));
                var needleHLD = inst.GetComponentsInChildren<HighLiftDevice>(true).Where(h => Mathf.Approximately((float)G(h, "deployedArea"), 0f)).ToList();
                var thr = ck == null ? new List<object>() : ((IEnumerable)G(ck, "throttles")).Cast<object>().ToList();
                R("instruments bound (airspeed needle via HighLiftDevice, throttle-driven levers/needles via Cockpit.throttles)", !CockpitAnimators || (needleHLD.Count >= 1 && thr.Count >= 1),
                    $"airspeed: {string.Join(",", needleHLD.Select(h => ((IEnumerable)G(h, "movingParts")).Cast<object>().Select(mp => ((Transform)G(mp, "transform"))?.name).FirstOrDefault()))}; throttles: {string.Join(",", thr.Select(t => ((Transform)G(t, "transform"))?.name + "(" + G(t, "range") + ")"))}; joysticks {((IEnumerable)G(ck, "joysticks")).Cast<object>().Count()}");
                // airspeed needle mapping (HighLiftDevice.FixedUpdate: pos = clamp01(1 - max(v - vDep, 0) / (vRet - vDep)))
                foreach (var h in needleHLD)
                {
                    float vd = (float)G(h, "speedDeployed"), vr = (float)G(h, "speedRetracted");
                    var mp = ((IEnumerable)G(h, "movingParts")).Cast<object>().First();
                    Vector3 aR = (Vector3)G(mp, "anglesRetracted"), aD = (Vector3)G(mp, "anglesDeployed");
                    string Ang(float v) { float pos = Mathf.Clamp01(1f - Mathf.Max(v - vd, 0f) / (vr - vd)); return Vector3.Lerp(aR, aD, pos).x.ToString("F0"); }
                    L($"  airspeed needle {((Transform)G(mp, "transform")).name}: 0 m/s -> {Ang(0)} deg, 50 m/s (112 mph) -> {Ang(50)}, 100 m/s (224 mph) -> {Ang(100)}, 150 m/s -> {Ang(150)} (local X toward the pilot, + = clockwise seen by the pilot)");
                }

                // 3 prop blur
                var blurOk = props.All(p =>
                {
                    var dm = (List<Mesh>)G(p, "propDiscMeshes"); var pd = (MeshFilter)G(p, "propDisc");
                    var mr = pd ? pd.GetComponent<MeshRenderer>() : null;
                    return dm.Count == 3 && dm[0] == null && dm[1] != null && dm[2] != null && dm[1] != dm[2] && OurAsset(dm[1]) && mr != null && mr.sharedMaterial != null && OurAsset(mr.sharedMaterial)
                        && mr.sharedMaterial.GetTexture("_BaseMap") != null && OurAsset(mr.sharedMaterial.GetTexture("_BaseMap")) && mr.sharedMaterial.GetColor("_BaseColor").a > 0.9f && pd.sharedMesh == null;
                });
                float Stage(ConstantSpeedProp p, float rpm) => Mathf.FloorToInt(Mathf.Clamp(3f * (rpm / (float)G(p, "rpmLimit") * 0.55f + 0.25f), 0f, 2f));
                R("prop blur: stage meshes [none, smear, disc], own blur material (alpha in texture), disc empty at rest", !OwnPropBlur || blurOk,
                    string.Join(" | ", props.Select(p => $"{p.name}: {string.Join(",", ((List<Mesh>)G(p, "propDiscMeshes")).Select(m => m ? m.name : "null"))} holder {((MeshFilter)G(p, "propDisc"))?.name}; stage at 100/330/900/1450 rpm = {Stage(p, 100)}/{Stage(p, 330)}/{Stage(p, 900)}/{Stage(p, 1450)}")));

                // 4 crew + hatches
                var canopies = (Canopy[])G(ac, "canopies");
                R("crew of 5 (Pilot components, bail-out, own parts, figures)", !FiveCrew || (ac.pilots.Length == 5 && ac.pilots.All(p => p != null && !(bool)G(p, "ejectionSeat") && G(p, "unitPart") != null && G(p, "skinnedMeshRenderer") != null && p.aircraft == ac) && ac.pilots.Distinct().Count() == 5),
                    string.Join(", ", ac.pilots.Select(p => $"{p.name}@{((UnitPart)G(p, "unitPart"))?.name} exit {p.exitDirection}")));
                R("bail-out hatches (stock Canopy: detach + push in flight, hinge open on the ground)", !FiveCrew || (canopies != null && canopies.Length >= 1 && canopies.All(c => c != null && c.attachedPart != null && c.ejectionTransform != null && c.ejectionCollider != null && !c.ejectionCollider.enabled && ((IEnumerable)G(c, "canopyHinges")).Cast<object>().Count() == 1)),
                    canopies == null ? "none" : string.Join(", ", canopies.Select(c => $"{c.name}@{c.attachedPart?.name} eject {c.ejectionTransform?.name} mass {c.mass}")));
                var crewParts = ac.pilots.Select(p => (UnitPart)G(p, "unitPart")).ToList();
                R("every crew member's part (or its parent chain) carries a hatch", !FiveCrew || crewParts.All(cp => canopies.Any(c => c.attachedPart == cp || c.attachedPart.transform.IsChildOf(cp.transform) || cp.transform.IsChildOf(c.attachedPart.transform))),
                    string.Join(", ", crewParts.Select(cp => cp?.name)));

                // 5 turrets
                var tlist = inst.GetComponentsInChildren<Turret>(true);
                var tset = wm.hardpointSets.FirstOrDefault(s => s.name == "Defensive turrets");
                R("4 turrets: Turret + Gun(s) + elevation pivot + firing cones + critical part", !DefensiveTurrets || (tlist.Length == 4 && tlist.All(t =>
                    {
                        var st = (WeaponStation[])G(t, "weaponStations");
                        return st.Length == 1 && st[0].Weapons.Count == 1 && st[0].Weapons[0] is Gun && st[0].Turrets.Count == 1 && st[0].Turrets[0] == t && G(t, "aimSafetyWeapon") == (object)st[0].Weapons[0]
                            && G(t, "elevationTransform") != null && ((IEnumerable)G(t, "firingCones")).Cast<object>().Any() && ((UnitPart[])G(t, "criticalParts")).Length == 1;
                    })),
                    string.Join(" | ", tlist.Select(t => { var g = (Gun)((WeaponStation[])G(t, "weaponStations"))[0].Weapons[0]; return $"{t.name}: {((Transform[])G(g, "muzzles")).Length} gun(s) x {G(g, "magazineCapacity")} rds, trav +-{G(t, "traverseRange")}, el {G(t, "minElevation")}..{G(t, "maxElevation")}, cones {((IEnumerable)G(t, "firingCones")).Cast<object>().Count()}"; })));
                R("turrets AI-operated (mode parentUnitTargetDetector = aircraft EOTS, not manual, not stowed) and selectable (own station info, boresight off)", !DefensiveTurrets || (ac.EOTS != null && tlist.All(t => G(t, "targetAcquisitionMode").ToString() == "parentUnitTargetDetector" && !(bool)G(t, "manual") && !(bool)G(t, "stowed"))
                        && tlist.All(t => ((WeaponStation[])G(t, "weaponStations"))[0].Weapons[0].info is WeaponInfo wi && OurAsset(wi) && !wi.boresight && wi.gun)),
                    tlist.Length == 0 ? "" : $"info {((WeaponStation[])G(tlist[0], "weaponStations"))[0].Weapons[0].info?.weaponName}, antiMissile {((WeaponStation[])G(tlist[0], "weaponStations"))[0].Weapons[0].info?.effectiveness.antiMissile}");
                R("turret muzzles: dorsal 2, tail 2, waist 1 + 1", !DefensiveTurrets || tlist.Select(t => ((Transform[])G((Gun)((WeaponStation[])G(t, "weaponStations"))[0].Weapons[0], "muzzles")).Length).OrderBy(x => x).SequenceEqual(new[] { 1, 1, 2, 2 }), "");
                R("hardpoint set 'Defensive turrets': 4 hardpoints, each 1 built-in turret + its gun, turret ammo option", !DefensiveTurrets || (tset != null && tset.hardpoints.Count == 4 && tset.hardpoints.All(h => h.BuiltInTurrets.Length == 1 && h.BuiltInWeapons.Length == 1 && h.part != null) && tset.weaponOptions.Count == 2),
                    tset == null ? "missing" : string.Join(", ", tset.hardpoints.Select(h => $"{h.transform.name}@{h.part.name}")) + $"; option {tset.weaponOptions.Last()?.mountName} ({tset.weaponOptions.Last()?.ammo})");
                // self-fire geometry: fraction of allowed aim directions (traverse x elevation grid, inside the firing cones)
                // whose 60 m ray from the elevation pivot hits our own airframe colliders (stock Turret blocks those shots)
                Physics.SyncTransforms();
                int strictUnsafeTotal = 0; var strictUnsafeWho = new List<string>();
                foreach (var t in tlist)
                {
                    var el = (Transform)G(t, "elevationTransform"); var cones = ((IEnumerable)G(t, "firingCones")).Cast<object>().ToList();
                    float tr = Mathf.Min((float)G(t, "traverseRange"), 180f), emin = (float)G(t, "minElevation"), emax = (float)G(t, "maxElevation");
                    int allowed = 0, blocked = 0; var parent = t.transform.parent;
                    var q0 = t.transform.localRotation;
                    for (float a = -tr; a <= tr + 0.01f; a += 10f)
                        for (float e = emin; e <= emax + 0.01f; e += 5f)
                        {
                            var dir = parent.rotation * q0 * Quaternion.Euler(0, a, 0) * Quaternion.Euler(-e, 0, 0) * Vector3.forward;
                            bool ok = true;
                            foreach (var c in cones)
                            {
                                var ct = (Transform)G(c, "transform"); float ca = (float)G(c, "coneAngle"); bool ex = (bool)G(c, "exclusion");
                                float ang = Vector3.Angle(dir, ct.forward);
                                if ((!ex && ang > ca) || (ex && ang < ca)) { ok = false; break; }
                            }
                            if (!ok) continue;
                            allowed++;
                            var hits = Physics.RaycastAll(el.position, dir, 60f, ~0, QueryTriggerInteraction.Collide);
                            if (hits.Any(h => h.collider.transform.root == inst.transform && h.collider.enabled)) blocked++;
                        }
                    L($"  turret {t.name}: {allowed} allowed aim directions, {blocked} ({(allowed > 0 ? 100f * blocked / allowed : 0):F0} %) blocked by own airframe within 60 m (stock linecast holds fire there)");
                    // strict scan: pivot + every muzzle, +-2 deg spread, 60 m; any own collider (part of 'inst') = unsafe
                    var gunT = (Gun)((WeaponStation[])G(t, "weaponStations"))[0].Weapons[0];
                    var origins = new List<Transform> { el }; origins.AddRange((Transform[])G(gunT, "muzzles"));
                    bool Unsafe(float a, float e)
                    {
                        foreach (var j in new[] { new Vector2(0, 0), new Vector2(2, 0), new Vector2(-2, 0), new Vector2(0, 2), new Vector2(0, -2) })
                        {
                            var d = parent.rotation * q0 * Quaternion.Euler(0, a + j.x, 0) * Quaternion.Euler(-(e + j.y), 0, 0) * Vector3.forward;
                            foreach (var o in origins)
                            {
                                var start = o.position - d * 0.05f;
                                foreach (var h in Physics.RaycastAll(start, d, 60f, ~0, QueryTriggerInteraction.Ignore))
                                    if (h.collider.enabled && h.collider.transform.IsChildOf(inst.transform) && !h.collider.transform.IsChildOf(t.transform)) return true;
                            }
                        }
                        return false;
                    }
                    var unsafeCells = new List<(float a, float e)>();
                    for (float a = -tr; a <= tr + 0.01f; a += 5f) for (float e = emin; e <= emax + 0.01f; e += 2.5f) if (Unsafe(a, e)) unsafeCells.Add((a, e));
                    strictUnsafeTotal += unsafeCells.Count; if (unsafeCells.Count > 0) strictUnsafeWho.Add($"{t.name} {unsafeCells.Count}");
                    L($"  turret envelope {t.name}: trav +-{tr} el {emin}..{emax}: {unsafeCells.Count} unsafe cells (strict){(unsafeCells.Count > 0 ? ": " + string.Join(" ", unsafeCells.Select(b => $"({b.a:F0},{b.e:F1})")) : "")}");
                    if (unsafeCells.Count > 0)
                    {
                        // greedy shrink (5 deg traverse / 2.5 deg elevation steps), keep the largest area with no unsafe cell
                        float ga = tr, gmin = emin, gmax = emax;
                        for (int it = 0; it < 80; it++)
                        {
                            var left = unsafeCells.Where(b => Mathf.Abs(b.a) <= ga + 0.01f && b.e >= gmin - 0.01f && b.e <= gmax + 0.01f).ToList();
                            if (left.Count == 0) break;
                            var cands = new List<(float a, float mn, float mx)> { (ga - 5f, gmin, gmax), (ga, gmin + 2.5f, gmax), (ga, gmin, gmax - 2.5f) };
                            var best = cands.Where(c => c.a >= 0 && c.mn < c.mx).OrderBy(c => unsafeCells.Count(b => Mathf.Abs(b.a) <= c.a + 0.01f && b.e >= c.mn - 0.01f && b.e <= c.mx + 0.01f)).ThenByDescending(c => (c.a + 1f) * (c.mx - c.mn)).First();
                            ga = best.a; gmin = best.mn; gmax = best.mx;
                        }
                        L($"  turret envelope {t.name}: SUGGEST trav {ga} el {gmin}..{gmax}");
                    }
                }
                R("turret envelopes: no aim direction into our own airframe (pivot + muzzles, +-2 deg, 60 m; all turrets share one station and fire together)", strictUnsafeTotal == 0, strictUnsafeWho.Count == 0 ? "all clean" : string.Join(", ", strictUnsafeWho));
                if (FireClear1814On && DefensiveTurrets)
                {   // 1.8.14 (offline M): the saved cones re-swept on this instance with the game's own FiringConeChecker
                    var fc14 = FireClear1814.CheckInstance(inst);
                    R("1.8.14 fire clearance: no aim direction where a turret may fire into our own airframe (game FiringConeChecker + 1 deg onTarget; colliders, meshes, prop discs; 1 deg grid, posed muzzles)", fc14.bad == 0, fc14.detail);
                }
                var turretLoops = tlist.SelectMany(t => t.GetComponentsInChildren<AudioSource>(true)).Where(a => a.loop).ToList();
                R("turret guns: no AudioSource with loop=true (Gun.Awake owns the sustained loop and stops it)", turretLoops.Count == 0, string.Join(",", turretLoops.Select(a => a.name)));

                // 6 cannon
                var cannon = guns.FirstOrDefault(g => g.name == "cannon_mount");
                var cset = wm.hardpointSets.FirstOrDefault(s => s.name == "75mm T13E1 Cannon");
                R("75 mm T13E1 (M5): name, 21 rounds, only custom weapon info", cannon != null && cset != null && cset.weaponOptions[1].info.weaponName == "75mm T13E1 Cannon" && cset.weaponOptions[1].ammo == 21 && (int)G(cannon, "magazineCapacity") * (1 + (int)G(cannon, "magazines")) == 21,
                    cset == null ? "missing" : $"{cset.weaponOptions[1].mountName} / {cset.weaponOptions[1].info.weaponName}");

                // 7 nuclear options
                var bayO = wm.hardpointSets.FirstOrDefault(s => s.name == "Bomb Bay")?.weaponOptions.Where(o => o).Select(o => o.jsonKey).ToList() ?? new List<string>();
                var rackO = wm.hardpointSets.FirstOrDefault(s => s.name == "Wing Racks")?.weaponOptions.Where(o => o).Select(o => o.jsonKey).ToList() ?? new List<string>();
                R("GPO-N where GPO-500 fits (bay x2/x1, racks) + GPO-2P Auger (bay x2, racks)", !NuclearOptions || (bayO.Contains("nuclearBomb1_internalx2") && bayO.Contains("nuclearBomb1_internal") && bayO.Contains("bomb_penetrator1_internalx2") && rackO.Contains("nuclearBomb1_external") && rackO.Any(k => k.StartsWith("bomb_penetrator1"))),
                    $"bay: {string.Join("/", bayO)}; racks: {string.Join("/", rackO)}");

                // 8/9 diagram + icon
                var sdp = prm.StatusDisplay; var sdc = sdp ? sdp.GetComponent<StatusDisplay>() : null;
                var sdParts = sdc == null ? new List<PartStatusDisplay>() : ((IEnumerable)G(sdc, "statusDisplays")).Cast<PartStatusDisplay>().ToList();
                var partNames = new HashSet<string>(allParts.Select(p => p.name == inst.name ? "B25H" : p.name));
                R("own damage diagram: our prefab, one image per part (names = our parts), background set", !OwnStatusDisplay || (sdp != null && OurAsset(sdp) && G(sdc, "aircraftBackground") != null && partNames.All(n => sdParts.Any(s => s.partImage != null && s.partImage.name == n)) && sdParts.All(s => s.partImage != null && partNames.Contains(s.partImage.name))),
                    sdp == null ? "none" : $"{AssetDatabase.GetAssetPath(sdp)}: {sdParts.Count} images, missing [{string.Join(",", partNames.Where(n => !sdParts.Any(s => s.partImage != null && s.partImage.name == n)))}], failures [{string.Join(",", ((IEnumerable)G(sdc, "failureIndicators")).Cast<GameObject>().Select(g => g.name))}]");
                R("own map icon (mod-local sprite)", !OwnMapIcon || (def.mapIcon != null && OurAsset(def.mapIcon)), def.mapIcon == null ? "none" : $"{AssetDatabase.GetAssetPath(def.mapIcon)} {def.mapIcon.rect.width}x{def.mapIcon.rect.height}, size {def.mapIconSize}");

                // 10 AI
                var app = inst.GetComponentInChildren<AutopilotPlane>(true);
                {   // 1.8.0: AI strafes ground targets with the fixed guns like the stock A-19 (Gun30mm_Rotary minAltitude 0), floor 450 kept
                    var fixedGuns = inst.GetComponentsInChildren<Gun>(true).Where(g => g.info != null && g.info.boresight).ToList();
                    R("1.8.0/1.8.1 AI uses the fixed .50s and the 75 mm on ground targets (boresight infos, minAltitude 0 and maxRange <= 3000 as the stock A-19 Gun30mm_Rotary / Gun12.7mm 1800); AI floor 250 (1.8.6F AITerrain186F) / 150 (1.8.1 AIFloorStock181) or 450",
                        FixedGunsAirOnlyForAI || (fixedGuns.Count >= 3 && fixedGuns.All(g => g.info.targetRequirements.minAltitude == 0f && g.info.targetRequirements.maxRange <= 3000f) && Mathf.Approximately(prm.minimumRadarAlt, AITerrain186F ? AIFloor186F : AIFloorStock181 ? 150f : 450f)),
                        string.Join(", ", fixedGuns.Select(g => $"{g.name}: {g.info.name} minAlt {g.info.targetRequirements.minAltitude} maxRange {g.info.targetRequirements.maxRange}")) + $"; minRadarAlt {prm.minimumRadarAlt}");
                    // 1.8.3D: the 75 mm outscores the stock rockets (0.55) / bombs (0.51) even when halved beyond 3.6 km (ChooseHQTarget)
                    var c75 = fixedGuns.FirstOrDefault(g => g.info != null && g.info.name == "B25H_T13E1_75mm_info");
                    R("1.8.3D AI ground-weapon priority: 75 mm info antiSurface 1.2 (halved 0.60 > rockets 0.55 / bombs 0.51), antiAir 0.76, boresight, maxRange 3000, minAltitude 0; floor 150 (1.8.6F: 250)",
                        !CannonGroundPriority183D || (c75 != null && Mathf.Approximately(c75.info.effectiveness.antiSurface, 1.2f) && Mathf.Approximately(c75.info.effectiveness.antiAir, 0.76f) && c75.info.boresight
                            && Mathf.Approximately(c75.info.targetRequirements.maxRange, 3000f) && c75.info.targetRequirements.minAltitude == 0f && Mathf.Approximately(prm.minimumRadarAlt, AITerrain186F ? AIFloor186F : 150f)),
                        c75 == null ? "75 mm gun not found" : $"{c75.info.name}: antiSurface {c75.info.effectiveness.antiSurface} antiAir {c75.info.effectiveness.antiAir} maxRange {c75.info.targetRequirements.maxRange}");
                }
                {   // 1.8.0: cockpit albedo in the stock range (stock cockpit base maps 0.10-0.14 linear)
                    var keys = new[] { ("bk_quilt", "b25h_quilt_b"), ("bk_od", "b25h_od_b"), ("bk_art", "b25h_ckart_b"), ("interior", "b25h_interior_b") };
                    var eff = keys.Where(k => mats.ContainsKey(k.Item1)).Select(k => (k.Item1, v: TexLinearMean(k.Item2) * mats[k.Item1].GetColor("_BaseColor").r)).ToList();
                    R("1.8.0 cockpit albedo (panel art, quilt, olive drab, inner skin) >= 0.10 linear like stock cockpits (0.10-0.14); panel black lifted to sRGB 0.07",
                        !CockpitBrighten || (eff.Count == 4 && eff.All(e => e.v >= 0.10f && e.v <= 0.16f) && mats["bk_black"].GetColor("_BaseColor").r >= 0.06f),
                        string.Join(", ", eff.Select(e => $"{e.Item1} {e.v:F3}")) + $", bk_black {mats["bk_black"].GetColor("_BaseColor").r:F2}");
                }
                R("bomber AI tuning (minimumRadarAlt 450 / 1.8.1 150 / 1.8.6F 250, turningRadius 2000, look-ahead g 3.5 / 1.8.6F 9, preventInvertedFlight)", !BomberAITuning || (prm.minimumRadarAlt >= (AIFloorStock181 ? 150f : 450f) && prm.turningRadius >= 2000f && Mathf.Approximately(prm.aircraftGLimit, AITerrain186F ? AIGLimit186F : 3.5f) && app != null && (bool)G(app, "preventInvertedFlight")),
                    $"minRadarAlt {prm.minimumRadarAlt}, turningRadius {prm.turningRadius}, cornerSpeed {prm.cornerSpeed}, gLimit {prm.aircraftGLimit}, cruiseThrottle {prm.cruiseThrottle}, preventInverted {(app ? G(app, "preventInvertedFlight") : "-")}");
                {   // 1.8.6 offline F: AI terrain look-ahead / floor (tools/flightmodel/ai_terrain.py) and the nose leg on dirt (nose_soft_ground.py)
                    var cf186 = inst.GetComponentInChildren<ControlsFilter>(true);
                    float fbwG = cf186 == null ? -1f : new SerializedObject(cf186).FindProperty("flyByWire.gLimitPositive").floatValue;
                    R("1.8.6F AI terrain following: aircraftGLimit (terrain look-ahead only) 9 -> 600 m, minimumRadarAlt 250, landingSpeed 52 kept; airframe pull limit flyByWire.gLimitPositive 3.5 unchanged",
                        !AITerrain186F || (Mathf.Approximately(prm.aircraftGLimit, AIGLimit186F) && Mathf.Approximately(prm.minimumRadarAlt, AIFloor186F) && Mathf.Approximately(prm.landingSpeed, 52f) && Mathf.Approximately(fbwG, 3.5f)),
                        $"aircraftGLimit {prm.aircraftGLimit} (look-ahead {600f * 9f / prm.aircraftGLimit:F0} m at <= 100 m/s), minRadarAlt {prm.minimumRadarAlt}, landingSpeed {prm.landingSpeed}, FBW gLimitPositive {fbwG}");
                    float fbwA = cf186 == null ? -1f : new SerializedObject(cf186).FindProperty("flyByWire.alphaLimiter").floatValue;
                    float fbwS = cf186 == null ? -1f : new SerializedObject(cf186).FindProperty("flyByWire.alphaLimiterStrength").floatValue;
                    R("1.8.7F FBW stall stop: alphaLimiter 10 x 0.25 (zero pitch command at 14 deg body alpha = the wing's CL peak; GA-25X values), gLimitPositive 3.5 / cornerSpeed 110 / takeoffSpeed 55 kept",
                        !StallLimiter187F || (Mathf.Approximately(fbwA, 10f) && Mathf.Approximately(fbwS, 0.25f) && Mathf.Approximately(fbwG, 3.5f)
                            && Mathf.Approximately(new SerializedObject(cf186).FindProperty("flyByWire.takeoffSpeed").floatValue, 55f) && Mathf.Approximately(prm.takeoffSpeed, 55f)),
                        $"alphaLimiter {fbwA} x {fbwS}, gLimitPositive {fbwG}, FBW takeoffSpeed {(cf186 == null ? -1f : new SerializedObject(cf186).FindProperty("flyByWire.takeoffSpeed").floatValue)}, AI takeoffSpeed {prm.takeoffSpeed}");
                    var lgs186 = inst.GetComponentsInChildren<LandingGear>(true).ToList();
                    var nose186 = lgs186.FirstOrDefault(g => g.name == "gear_nose_leg");
                    var mains186 = lgs186.Where(g => g.name.StartsWith("gear_main_")).ToList();
                    R("1.8.6F nose leg contactArea 0.05 (dirt drag only; CAS1 template 0.02); spring 650000 / damper 40000 / maxCompression 0.40 / travel 0.629 as 1.8.2; mains unchanged (0.04, 750000, 0.45)",
                        !NoseContact186F || (nose186 != null && Mathf.Approximately((float)G(nose186, "contactArea"), NoseContactArea186F) && Mathf.Approximately((float)G(nose186, "springRate"), 650000f)
                            && Mathf.Approximately((float)G(nose186, "dampingRate"), 40000f) && Mathf.Approximately((float)G(nose186, "maxCompression"), 0.40f) && Mathf.Abs((float)G(nose186, "suspensionTravel") - 0.629f) < 1e-4f
                            && mains186.Count == 2 && mains186.All(g => Mathf.Approximately((float)G(g, "contactArea"), 0.04f) && Mathf.Approximately((float)G(g, "springRate"), 750000f) && Mathf.Approximately((float)G(g, "maxCompression"), 0.45f))),
                        string.Join("; ", lgs186.Select(g => $"{g.name} area {G(g, "contactArea")} k {G(g, "springRate")} c {G(g, "dampingRate")} max {G(g, "maxCompression")} travel {G(g, "suspensionTravel")}")));
                }

                // liveries: the four 1.0 ones to both factions as before + two faction-only ones each
                string Fac(AircraftParameters.Livery l) => l.faction == null ? "?" : l.faction.name;
                var bdf = prm.liveries.Where(l => Fac(l) == prm.liveries[0].faction.name).Select(l => l.name).ToList();
                var pala = prm.liveries.Where(l => Fac(l) != prm.liveries[0].faction.name).Select(l => l.name).ToList();
                var distinct = prm.liveries.Select(l => l.assetReference.AssetGUID).Distinct().Count();
                R("8 liveries: BDF = 4 old + BDF Matte Gray + BDF Temperate Camo, PALA = 4 old + PALA Matte Black + PALA Desert Camo", distinct == 8 && bdf.Count == 6 && pala.Count == 6
                        && BaseLiveries.All(b => bdf.Contains(b.label) && pala.Contains(b.label)) && bdf.Any(n => n.Contains("Matte Gr")) && bdf.Any(n => n.Contains("Temperate")) && pala.Any(n => n.Contains("Matte Black")) && pala.Any(n => n.Contains("Desert")),
                    $"BDF: {string.Join(", ", bdf)} | PALA: {string.Join(", ", pala)}");


                // nothing inside the prefab points to an object outside it except assets
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
                // overlapping hulls are jointed (approximate: AABB)
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
