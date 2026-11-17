// One Blueprinter addon for the whole family (B-25H + GA-25X, more pairs later): both generators write only their own
// subfolder of Assets/Blueprinter/Mods/<FamilyMod>, and one ModBuilder.Build packs the family into one .nobp.
//
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FamilyBuild.BuildAll   family_build   (B-25H + GA-25X + pack)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FamilyBuild.Pack       family_pack    (pack what is built)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FamilyBuild.DumpB25HStandalone dump_b25h_111   (semantic dump, see Dump)
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FamilyBuild.DumpB25HCombined   dump_b25h_family
//   powershell -File C:\Users\User\nuclearoption-ref\unity.ps1 FamilyBuild.AeroGA25X          aero_ga25x (part lift points, CG, airfoil charts)
//
// Combined = false puts each generator back on its own addon (b25h_mitchell / ga25x) exactly as before.
// jsonKeys are unchanged (B25H*, GA25X*), so saves and missions that reference the aircraft keep working.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace B25HTools
{
    public static class FamilyBuild
    {
        public const bool Combined = true;
        public const string FamilyMod = "heritage_pairs";
        public const string FamilyDisplay = "Heritage Pairs";
        public const string FamilyId = "HeritagePairs";   // 1.9.9: the public mod id (NOMNOM manifest id, meta.json id, NOMM install folder addons/HeritagePairs). FamilyMod stays the Unity folder / bundle name.
        public const string FamilyVersion = "1.9.14";   // 1.9.14: GA-25X prop tips no longer show over the blur disc (the nickel tip sheath was split off into a child renderer that ConstantSpeedProp never hides; StockStructure skips blades), GA-25X cockpit art fixes (glare-shield caution lights cropped on whole cells, subpanel knobs / toggles on the painted ones; only cockpit_interior patched, livery atlas unchanged), GA-25X lit lamps / LED digits glow (emission map), stock CI-22 gear light on the GA-25X nose leg and the MSB-17 / FD-32 main legs; plugin = 1.9.13 code with the version bumped. 1.9.13: FD-32 and Mk I wing joints solved with 20 PhysX iterations (PartJoint.solverIterations on every joint owned by a wing_* part) against the upper outer wing "hinge" at the break line in pulls and rolls (Discord report); nothing else in the pack; plugin = 1.9.12 code with the version bumped. 1.9.12: air brake on whenever the throttle is under 5 %, ground or air, on all six (stock Airbrake; B-25H / Mk I / B-17G without parts, GA-25X / FD-32 / MSB-17 with panels; the plugin widens the stock "throttle == 0" to "under 5 %"), MSB-17 formation-light strips, naval liveries for the Mk I and FD-32 (BDF + PALA). 1.9.11: FD-32 / Mk I carrier-lift spawn (spawnOffset.z +1.2 / +0.7 m clear of the stock lift backstops; rudder impact damage off as on stock rudders), nothing else; plugin = 1.9.10 code with the version bumped. 1.9.10 (release candidate after the pre-publish audit): two logo-like marks painted out of AI placard art (B-17G data plate -> b17g_gauges, GA-25X data plate -> ga25x_ckart_b/_n), nothing else in the pack; plugin display name "Heritage Pairs Instruments". 1.9.9: the MSB-17/80 is renamed MSB-17 and its key MSB1780 -> MSB17 (jsonKey, every in-pack name, pack subfolder msb17; repo file names keep msb1780); plugin 1.9.9 (the 1.9.8 behaviour, cleaned for review) ships in the pack; meta id HeritagePairs, gameVersion 0.34.6. 1.9.7: lasers never fire through their own aircraft (GA-25X, MSB: Laser.maxAngle 1 + plugin beam guard), taildragger ground stack deck-relative (carriers), MSB tail windows plated, smooth normals on doors / hatches, throttle quadrant housing. 1.9.6: MSB-17/80 cockpit detail pass on our own deck (offline, coordinator review of 1.9.5) - recessed screen wells, raised centre stack with gear lever, flap selector and a live standby attitude, annunciator strips, rotary selectors, push-button and toggle rows with emissive legends, glare-shield roll edge and mode-control strip, throttle quadrant surround with detents, aft pedestal with radio heads, trim wheel and speed brake, console comm / oxygen / switch panels and map pockets, overhead breaker rows; everything else = 1.9.5; the other five aircraft unchanged. 1.9.5: MSB-17/80 flight deck rebuilt as OUR OWN deck with single stock parts (user order: no whole stock cockpit) - our panel shaped to the windscreen with six MFD units (map / power + engines per pilot, attitude centre, standby), a glare shield that ends at the panel ends, centre pedestal with a throttle gate, side consoles, floor, footwells and walls; stock SFB-81 sticks x2 and its one centre throttle quadrant, two stock EW-25 missile-warning lamps, the stock ejection seats; pilots 0.11 m forward / 0.04 m down and the WSO 0.035 m up (stock seats cleared the roof / the EWO seat / the WSO floor), EWO desk edge 0.12 m outboard; flight model, weapons, outline, plugin = 1.9.4 / 1.9.2; the other five aircraft unchanged. 1.9.4: MSB-17/80 engine-out fix from the in-game test of 1.9.3 - own rudder lift curve (airfoil 4 MSB17_rudder: the tail curve to 16.9 deg, then the pack's control-surface curve instead of the tail's stall at 17 deg; the 30 deg throw gave 0.82 x of the 17 deg lift and the aircraft departed with engine 1 out at 74.8 m/s; model VMC 71 -> 56 m/s); plugin = 1.9.2; the other five aircraft unchanged. 1.9.3: MSB-17/80 fixes from the in-game test of 1.9.2 - AI touchdown (landing speed 74 -> 56.5: the AI lands near the 3-point attitude instead of a 3 deg wheel landing that bounced it over the 1 m abort limit; main damping 1.95e5 -> 2.9e5 per wheel, tail spring / damping / break 6.5e5 / 6.0e4 / 0.36), EW-25 centre screens laid out for the CI-22 page (outer = map, inner = power + engine panels, lower centre = attitude, five dark), WSO / EWO screen 1 = map and screen 2 = panels; plugin = 1.9.2; the other five aircraft unchanged. 1.9.2: MSB-17/80 fixes from the first in-game test of 1.9.0 - level speed (prop torque limit 15 -> 25 kN m per row, wing / stab aero incidence 3.5 / -2 -> 1.5 / 0), heavy take-off drift (plugin: MSB ground yaw damper 24 /s, MsbGround190 + MsbTac190 ON by default, tac panels on engine 1), WSO / EWO tac pages in the B-25H layout, stock airbrake at idle + AI landing speed 74 / approach 85 + flaps from 72 m/s, laser traverse 150 deg/s, brakes 0.285 (nose-over limit), overhead console smaller and aft of the pilots; the other five aircraft unchanged. 1.9.1: MSB-17/80 visual pass (offline, coordinator review of 1.9.0): the stock EW-25 two-pilot glass cockpit (tub with MFD glass, glare shield, pedestal, side consoles, floor; wide tac screen; sticks; throttle) kitbashed on the flight deck, an overhead console, the WSO station rebuilt (floor at the seat base, seat base, side consoles, panel on posts), the EWO console bank (desk, tilted screen panel, racks, cheeks), WSO / EWO screen 1 live tac pages, a seal ring round the ventral laser drum, clean scimitar prop blades (NACA sections, one twist law, no self-intersection); flight model, weapons, outline and plugin = 1.9.0; the other five aircraft unchanged. 1.9.0: the sixth aircraft, MSB-17/80 (MSB17: the upgraded B-17G, rank 4, contra-rotating turboprops, own twin 20 mm, two 120 kW lasers, 5.7 m bay, side bays, 4 pylons, tail wheel on the B-17G taildragger stack); plugin 1.9.0 (MSB17 in GroundGrip189 / TaxiTurn1811 behind [Ground] MsbGround190, the 1.8.15 AI code not compiled); the other five aircraft unchanged. 1.8.18: B-17G nose close-ups only (in game 1.8.17): the NM anti-glare panel edges anti-aliased at the same place (the rounded front round the astrodome was a saw-tooth texel edge), the astrodome inner frame one continuous ring with the nose frames / stringers ending on it (were chord blocks with jagged gaps and open bar ends; outside unchanged); skins re-baked; plugin = the in-game 1.8.12. 1.8.17: B-17G nose to the War Thunder reference (user: the nose did not match): a smooth pointed glazed cone (WT profile, base ring at y 6.65, tip 7.44) with a frame ring and the bombardier's optical flat instead of the bulbous dome with meridian bars; glass down to the chin turret (the grey tongue in front of the glass was the cone's bottom strip of skin faces); narrower nose ahead of the cockpit; staggered K-5 cheek windows with projecting angled frames and the guns in their sockets; navigator windows (2 left, 1 right), right forward window, top window, astrodome, nose mast; chin turret in an exact opening with the long keel fairing aft; NM anti-glare panel to the reference shape; skins re-baked on the new atlas; plugin = the in-game 1.8.12. 1.8.16: skin / livery / damage textures of the B-25H and B-17G re-baked on their current livery atlas (the 1.8.13 / 1.8.14 model rebuilds re-packed the atlas, so the 1.8.12 paint landed on the wrong parts: camo blotches on plain olive drab, olive patches on natural metal); same paint, only re-laid; livery-atlas guard (blender/atlas_guard.py, AtlasGuard1816.cs: a texture manifest per aircraft, the model checks and CHECK ALL fail when the model atlas differs from it); ships the 1.8.12 plugin that is in the game (the 1.8.15 AI plugin is not shipped: not yet tested in game); models and flight settings = 1.8.14. 1.8.15: AI fixes in B25H.Instruments 1.8.15 (AiGround1815.cs, config [AI], both OFF by default until the live probes pass): AiGroundPitch1815 = no AI nose-down stick while taxiing / rolling out on the B-17G / Mk I / FD-32 (the AI taxi nose-over), AiTurretTarget1815 = the AI B-17G pilot leaves the turret stations to the gunners (no fighter chase into the stall); models and flight settings = 1.8.14. 1.8.14: B-25H torn fuselage seams with a dark lap strip under the skin and the torn-end walls under it (the light roof line between the dorsal trim ring and the canopy; outside shape unchanged); every B-17G / B-25H turret gets exclusion FiringCones from a 1 deg bore-line sweep of the built aircraft (colliders, meshes, prop discs) so no turret fires into its own airframe (B-17G ball into its right wing tip in 1.8.13); limits unchanged; plugin unchanged. 1.8.13: our own AN/M2 .50 (blender/anm2, ANM2Gun.cs) on every B-17G / B-25H turret and hand-held gun slot instead of the stock UH-90 door-gun barrel (gun_L / gun_R baked mirror pair, spade grips on the hand-held positions, trunnion at the elevation pivot, muzzles at the bore tips); plugin unchanged. 1.8.12: B-17G control columns the right way round (pull = aft; 1.8.9-1.8.11 had the pitch sign backwards), taxi-turn fix TaxiTurn1811 ON by default (user flew it: taxi, take-off, landing, no veer, no drift); models and flight settings = 1.8.11. 1.8.11: taxi turns without the skid on the B-17G / Mk I / FD-32 (B25H.Instruments 1.8.11 TaxiTurn1811: ground grip on the fuselage (root-body) velocity with mu 1.0, main castor range 25 deg below 12 m/s back to 6 by 20 m/s, tail-wheel lock scheduled to the no-slip angle of a 0.9 rad/s turn; config [Ground] TaxiTurn1811); models and flight settings = 1.8.10. 1.8.10: lag fix in B25H.Instruments 1.8.10 (no scene searches: aircraft from UnitRegistry.allAircraft, HUD gauges from Initialize / Start hooks, the 2 s discovery pass spread over frames); models and flight settings = 1.8.9. 1.8.9: B-17G control columns pitch about the floor (plugin), wheels roll about the hub; taildragger ground grip at the CoM + ground yaw damper (B25H.Instruments 1.8.9, config [Ground] GroundGrip189) on the castoring mains (no sideways drift); B-17G / Mk I / FD-32 damage maps with a real hole-order alpha (skin cut away like stock). 1.8.8: castoring main wheels (stock nose-wheel law mirrored) on the B-17G / Mk I / FD-32 so they track straight at full throttle with no input; B-17G nacelles (outboard 3.80 m pointed, inboard square-ended fairing) and tail gunner cab + Cheyenne cover rebuilt against the reference. 1.8.7: B-25H fly-by-wire alpha limiter 10 / 0.25 (AI no longer pulls through the stall on climb-out), GA-25X gLimitPositive 5 (strafing pull-out), FD-32 exterior glass smoothness 0.45 (no reflected line at the windscreen base), B25H.Instruments 1.8.7 (B-17G fuel P falls at 15 psi/s). 1.8.6: B-25H AI terrain following (aircraftGLimit 9 look-ahead, minimumRadarAlt 250), B-25H / GA-25X nose contactArea 0.05 (no dirt break while taxiing), B25H.Instruments 1.8.6 (flaps dial found, hydraulic dips with gear / flaps, B-17G fuel P falls at engine stop). 1.8.5: internals on a matte neutral-grey structure look (stock pattern / normal / AO; was salmon in fire light), FD-32 sill rail dark metal (no camo sliver at the windscreen base), B-17G turbo housings rust. 1.8.4: every dial driven (B25H.Instruments 1.8.4: B-25H compass/clock/suction/ammeter/temps/de-icer/oxygen/etc. as real needles, GA-25X power box/turbine/ISIS/torque, Mk I + B-17G rpm from the prop, B-17G 21 new needles + brighter attitude card, FD-32/GA-25X Ng); FD-32 gear damping x0.75 (mains) + tail 6750 (P1 jitter); B-25H / GA-25X cannon antiSurface 1.2 (AI strafes ground targets with the cannon before rockets). 1.8.3: B-17G nacelles to the reference (cowl ring + flaps, open wheel wells, turbos, intakes); internals the stock way on all five (aircraft_structure engines / break faces / tanks); FD-32 canopy redesign + rebuilt cockpit opening; Nimrod Mk I cockpit-edge specks fixed; ground values = 1.8.2. 1.8.2: FD-32 lower wings 51 -> 100 kg from fus_engine (805 -> 707) and main damping 20000 -> 13000 (the period-2 wheel-load jitter of the 1.8.0 wing gear: tail wheel loaded only every other step), BOOST thrust on the centreline (was 0.47 m right: one-way full-throttle swing); Nimrod Mk I tail-wheel aligningStrength 4 -> 8 (keyboard swing); everything else as 1.8.1. 1.8.1: Nimrod Mk I / FD-32 split mains - unbraked grip leg friction 0.8 -> 0.20 (side 0.35 x load, below the 0.42 g roll-over), rolling resistance only on the braked leg (0.20 x share = 0.05: full braking back to 1.7.13), tail-wheel lock -50 -> -40; B-25H / GA-25X AI floor 450 / 300 -> 150 / 120 (stock-like shallow gun passes), GA-25X 76 mm AI range 25000 -> 3000 (stock A-19 30 mm); B-25H canopy glass hidden in cockpit view with a faint cockpit-layer copy (stock COIN pattern); B-17G unchanged; plugin B25H.Instruments 1.8.0 unchanged. 1.8.0: user bug review of 1.7.13 - Nimrod Mk I / FD-32 / B-17G split main wheels (stock friction 0.8 side grip, braking as 1.7.13); B-25H / GA-25X AI use their guns on ground targets; B-25H cockpit albedo to the stock range; FD-32 gear on the lower wings, no capacitor, 9 green strips; B-17G tail gunner window, barrels on their slots, compass card un-mirrored, real skin damage maps; Nimrod / FD-32 rounded cockpit opening; B25H.Instruments 1.8.0 shipped in the addon folder. 1.7.13: B-17G AI roll PID D back to 0.05 (D 0.20 crashed AI landings in game); Nimrod Mk I + FD-32 mains back to friction 0.20 with the contact on the tyre (1.7.12 deck nose-overs), cornering from LandingGear.response 1.5 on the mains, FD-32 tail lock -50 kept; B-17G turret normals and exit-taxi turn kept; 1.7.12: B-17G top / chin turret openings shade like the uncut skin (analytic custom normals), AI roll PID D 0.05 -> 0.20 (climb weave), exit-taxi turn (tail lock -45, inner-wheel diff brake 3.5); Nimrod Mk I + FD-32 mains frictionCoef 0.20 -> 0.30 with the ground contact 0.20 m ahead of the tyre (nose-over margin kept), FD-32 tail-wheel lock -30 -> -50 (AI taxi deadlock at K92); 1.7.11: B-17G visuals only - all 65 z-fighting face pairs resolved at build time (cockpit bezels / panel detail / throttles, fal engine faces, nose glazing frames, chin and ball ring liners, cockpit roof and window frame, fin, tail, top turret); 1.7.10: B-17G AI parameter line restored (a 1.7.8 comment swallowed PIDReferenceAirspeed / maxSpeed / takeoffSpeed / takeoffDistance), 1.25 MW (1.5 MW flew 491 km/h); 1.7.9: B-17G tail compartment to the reference outline (end slopes onto a bigger Cheyenne cover that is the end of the body; flight settings = 1.7.8); 1.7.8: B-17G lateral round (handed props + no FBW roll trim: hands-off spiral; AI roll PID 0.03/0.002/0.05 + terrain look-ahead 6.75 km: AI weave and slow climb; aero dihedral 10), tail compartment tapered to the reference sections with a fin-root pinch and a rounded end, top-turret roof patch welded (shading staircase); 1.7.7: B-17G polish (chin turret a rounded blister faired into the nose, tail end rounded with a collar round the Cheyenne cover, cut tail skin welded); 1.7.6: B-17G model round 5 (procedural props on the shaft axis, procedural chin / ball / tail / top turrets, nacelles clear of the flaps, cockpit bulkhead ears and pedestal z-fight fixed, crew legs kept tucked under the stock seated animation, underside detail, internals: spars / ribs / fuel cells / frames / stringers / engines / turbos), wreck fire (12 linked AB-4-style tanks at the tank meshes, engine fire effect on the engines); 1.7.5: Nimrod Mk I tail-wheel steering lock -30 -> -50 (taxi turns); B-17G FBW pitch damping dFactorFast 0.4 -> 3 (AI pitch oscillation), AI minimumRadarAlt 150 -> 3000 (high-altitude bomber); 1.7.4: B-17G FBW roll trim 0.3, aero dihedral 8; 1.7.3: B-17G brake friction 0.22 (full-brake nose-over in game); 1.7.2: B-17G AI cornerSpeed 100; (1.7.1 flaps 56/78, AI landing speed 44, AI g 2.5: tried in game, 2 of 2 AI B-17s flew into hills, reverted); 1.7.0: B-17G AI landing (pattern 1500 m, corner 80, landing 47, min radar alt 150, cruise throttle 1) + gear-down drag; 1.6.9: B-17G AI cruise/landing throttle cap 0.8; 1.6.8: B-17G part drag x0.5, 1.6 MW (level speed); 1.6.7: B-17G 1.55 MW + own wing drag curve, cruise throttle 0.55; 1.6.6: B-17G pitch authority (elevator airfoil, 32 deg, real tail area, FBW pitch gain 25); 1.6.5: B-17G FBW take-off speed 15 (holds the 3-point attitude), 1.3 MW, cruise throttle 0.5; 1.6.4: B-17G flap lift at mid-chord, stab incidence -2; 1.6.3: B-17G take-off round (flap airfoil + area + 28 deg, wing incidence 3.5, game engine power); 1.6.2: B-17G wing-root fillet, ball gunner legs, smoother skin, clean anti-glare edge; 1.6.1: B-17G fix round after the first in-game test (ground handling, tailwheel, turrets, crew, nose, NM, bay, cockpit, colliders); the other four unchanged; 1.6.0: + B-17G Flying Fortress (B17G, the historical heavy bomber of the third pair); the other four aircraft unchanged (semantic dumps before/after: FamilyBuild.DumpFourBefore / DumpFourAfter); 1.5.7: FD-32 round 11 (the belly skin is cut open round the sensor bay; the ball stows inside a closed well); 1.5.6: round 10 (FD-32: the CI-22 single throttle instead of the SFB-81 bomber throttle; Mk I: rudder mass-balance horn + aerial mast back, re-modelled to the reference proportions); 1.5.5: round 9 user review (FD-32 + Nimrod Mk I: axles 0.15 m forward + brakes 0.20 against nose-overs, no fin spur, FD-32 stock throttle + sensor ball out with the gear up, Mk I gear on the game logic via the plugin); B-25H / GA-25X unchanged; 1.5.4: FD-32 round 8 (stick 3 cm lower / 1 cm fwd, clear of the big screen from the in-flight eye; camo edge zone softened); 1.5.3: FD-32 round 7 (tilted-axis gear: wheel flat under the wing root; faint cockpit glass; windscreen side skirts; map raised; soft camo edge; dark console faces; B25H.Instruments 1.5.3 binds the tac-page power / engine panels); B-25H / GA-25X / Nimrod unchanged; 1.5.2: FD-32 round 6 (semi-retractable aft-swinging gear, fixed tailwheel, hook in a slot, closed spinner, cockpit glass seen from inside, four working screens, new fal throttle, small stick base); B-25H / GA-25X / Nimrod unchanged; 1.5.1: FD-32 v2 rework (retracting gear + tailwheel, gear lights, flaps, longer fuselage, enclosed canopy, modern hook, GA-25X-standard cockpit, own-faction liveries, BOOST); B-25H / GA-25X / Nimrod unchanged; 1.5.0: + FD-32 Nimrod (FD32, the 2080s rebuild of the Nimrod Mk I); B-25H / GA-25X / Nimrod unchanged; 1.4.2: Nimrod gear stiffer with a stock-like break limit, gentle wing stall, aileron airfoil (no roll reversal), alpha limiter 15.5; 1.4.1: Nimrod user review 3 (spinner faces outward, no panel cross-frame, crash impact damage on every part); 1.4.0: Nimrod user review 2 (reference tail / skid / A-frame hook / radiator + oil cooler / spinner / sights / windscreen / seams / no nav lights / Cooper airburst fix / own HUD icons) and rudder pedals removed from all three aircraft; 1.3.2: Nimrod nav-light Point lights 0.4 m outboard, range 0.55 m (stock layout); 1.3.1: Nimrod aileron hinge gap closed (round nose + cove lips), dark cove material; 1.3.0: Nimrod model + all art rebuilt with fal (user review 1); 1.2.3: Hyperion R1-R3 again (R2-only left AI stuck); 1.1.0 (2026-11-02): + Hawker Nimrod Mk I; 1.2.0: Nimrod cockpit v2; 1.2.1: Nimrod game-test fixes; 1.2.2: hook hinge, thrust, Aldis, Hyperion R2
        public const string FamilyRoot = "Assets/Blueprinter/Mods/" + FamilyMod;
        const string OutFolder = @"C:\Users\User\nuclearoption-ref\build\heritage_pairs";
        const string Logs = @"C:\Users\User\nuclearoption-ref\unitylogs";
        const string GameVersion = "0.34.6";   // 1.9.9: the installed game (was 0.34.3, the version of the export the generators were first written against)
        const string BlueprinterVersion = "2.1.1";

        public static void BuildAll()
        {
            bool b = B25HBuild.BuildAssets();
            bool g = GA25XBuild.BuildAssets();
            bool n = NimrodBuild.BuildAssets();   // 2026-11-02: third aircraft (Hawker Nimrod Mk I, NIMROD1)
            bool f = FD32Build.BuildAssets();
            bool q = B17GBuild.BuildAssets();     // 2026-11-03: fifth aircraft (B-17G Flying Fortress, B17G)     // 2026-11-02: fourth aircraft (FD-32 Nimrod, FD32: the 2080s rebuild of the Mk I)
            bool z = MSB1780Build.BuildAssets();  // 2026-11-10: sixth aircraft (MSB-17, formerly MSB-17/80, MSB17: the 2080s rebuild of the B-17G)
            Debug.Log($"[B25H] FAMILY CHECKS B25H {(b ? "CHECK ALL PASS" : "FAIL")} | GA25X {(g ? "CHECK ALL PASS" : "FAIL")} | NIMROD {(n ? "CHECK ALL PASS" : "FAIL")} | FD32 {(f ? "CHECK ALL PASS" : "FAIL")} | B17G {(q ? "CHECK ALL PASS" : "FAIL")} ({B17GBuild.lastCheck}) | MSB17 {(z ? "CHECK ALL PASS" : "FAIL")} ({MSB1780Build.lastCheck})");
            File.AppendAllText(Path.Combine(Logs, "family_pack.txt"), DateTime.Now.ToString("s") + $" checks B25H={b} GA25X={g} NIMROD={n} FD32={f} B17G={q} MSB17={z}\n");
            Pack();
        }

        // Pack the family folder into one .nobp + an install folder with meta.json (same schema as the single addons).
        public const bool ShipInstrumentsPlugin = true;     // 1.8.0
        public const string InstrumentsDll = @"C:\Users\User\nuclearoption-ref\build\instruments_1.9.14\B25H.Instruments.dll";   // 1.9.14: version only. 1.9.13: version only. 1.9.12: AirBrake1912.cs (the stock Airbrake on under 5 % throttle, ground and air, + HUD text). 1.9.11: version only. 1.9.10: same code as 1.9.9, display name + version only. 1.9.9: the 1.9.8 behaviour (DeckHold198), key MSB17, cleaned for the public release. 1.9.7: LaserGuard197 + DeckRelative197. 1.9.2: MSB pieces ON by default, MSB yaw damper 24, tac panels on engine 1; 1.8.15 AI code still not compiled.   // 1.9.0: built from the current source (1.8.12 + MSB17 ground keys; AiGround1815.cs not compiled, #if AI1815)   // 1.8.16: the plugin in the game (sha256 3ab8f673f655), not the untested 1.8.15 AI build (its source stays in src/)
        public static void Pack()
        {
            if (!AssetDatabase.IsValidFolder(FamilyRoot)) throw new Exception("family folder missing: " + FamilyRoot);
            Directory.CreateDirectory(OutFolder);
            Blueprinter.ModBuilder.Build(FamilyMod, FamilyDisplay, FamilyVersion, OutFolder);
            var nobp = Path.Combine(OutFolder, Blueprinter.BlueprinterAssets.SanitizeFileName($"{FamilyDisplay}_{FamilyVersion}") + ".nobp");
            if (!File.Exists(nobp)) throw new Exception("pack produced no .nobp: " + nobp);
            var hash = Sha256(nobp);
            var inst = Path.Combine(OutFolder, "install", FamilyId);
            if (Directory.Exists(inst)) Directory.Delete(inst, true);
            Directory.CreateDirectory(inst);
            File.Copy(nobp, Path.Combine(inst, Path.GetFileName(nobp)), true);
            var meta = "{\n    \"id\": \"" + FamilyId + "\",\n    \"artifact\": {\n        \"fileName\": \"" + Path.GetFileName(nobp) + "\",\n        \"version\": \"" + FamilyVersion +
                "\",\n        \"category\": \"release\",\n        \"type\": \"addon\",\n        \"gameVersion\": \"" + GameVersion + "\",\n        \"downloadUrl\": \"\",\n        \"hash\": \"sha256:" + hash +
                "\",\n        \"extends\": {\n            \"id\": \"com.nikkorap.blueprinter\",\n            \"version\": \"" + BlueprinterVersion + "\"\n        },\n        \"dependencies\": [],\n        \"incompatibilities\": []\n    }\n}\n";
            File.WriteAllText(Path.Combine(inst, "meta.json"), meta);
            // 1.8.0: the dial plugin ships inside the addon folder (MiG29Fulcrum pattern: <addon>.nobp + <plugin>.dll + meta.json). BepInEx 5.4.23
            // TypeLoader.FindPluginTypes scans BepInEx/plugins for *.dll with SearchOption.AllDirectories, so plugins/com.nikkorap.blueprinter/
            // addons/heritage_pairs/B25H.Instruments.dll loads like a top-level plugin. The old standalone copy must be removed on install (same GUID).
            string pluginLine = "";
            if (ShipInstrumentsPlugin)
            {
                if (!File.Exists(InstrumentsDll)) throw new Exception("plugin DLL missing: " + InstrumentsDll);
                File.Copy(InstrumentsDll, Path.Combine(inst, Path.GetFileName(InstrumentsDll)), true);
                pluginLine = $"; plugin {Path.GetFileName(InstrumentsDll)} sha256 {Sha256(InstrumentsDll)}";
            }
            var defs = AssetDatabase.FindAssets("t:UnitDefinition", new[] { FamilyRoot }).Select(g => AssetDatabase.LoadAssetAtPath<UnitDefinition>(AssetDatabase.GUIDToAssetPath(g))).Where(d => d != null).Select(d => d.jsonKey).OrderBy(x => x);
            var line = $"FAMILY PACK {FamilyMod} {FamilyVersion}: {nobp} size {new FileInfo(nobp).Length} sha256 {hash}; definitions [{string.Join(", ", defs)}]; install {inst}{pluginLine}";
            Debug.Log("[B25H] " + line);
            File.AppendAllText(Path.Combine(Logs, "family_pack.txt"), DateTime.Now.ToString("s") + " " + line + "\n");
        }

        public static string Sha256(string file)
        {
            using (var s = SHA256.Create()) using (var f = File.OpenRead(file))
                return string.Concat(s.ComputeHash(f).Select(b => b.ToString("x2")));
        }

        // =================================================================== semantic dump (B-25H identity proof)
        // Every asset under a mod folder, every component of its prefabs and every serialized field, with references
        // written as stable names: objects inside the same prefab by hierarchy path + component type, our assets by path
        // RELATIVE to the folder (+ sub-asset name/type), stock placeholders by asset path; GUID strings (Addressable
        // livery references) by the relative path they point to; meshes by a hash of their vertex/index/uv data, textures
        // by a hash of their source file. Skipped: NetworkIdentity._prefabHash (derived by Blueprinter from the asset path).
        // 1.6.0: semantic dumps of the four existing aircraft folders (identity proof around the B-17G addition)
        public static void DumpFourBefore() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_before160.txt")); }
        public static void DumpFourAfter() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after160.txt")); }
        public static void DumpFourBefore1712() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_before1712.txt")); }
        public static void DumpFourAfter1712() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after1712.txt")); }
        public static void DumpFourAfter1713() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after1713.txt")); }
        public static void DumpFiveBefore180() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_before180.txt")); }
        public static void DumpFiveAfter182() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after182.txt")); }
        public static void DumpFiveAfter181() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after181.txt")); }
        public static void DumpFiveAfter180() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after180.txt")); }
        public static void DumpFourAfter175() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after175.txt")); }
        public static void DumpFiveBefore190() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_before190.txt")); }
        public static void DumpFiveAfter190() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after190.txt")); }
        public static void DumpFiveBefore191() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_before191.txt")); }
        public static void DumpFiveAfter192() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after192.txt")); }
        public static void DumpFiveAfter193() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after193.txt")); }
        public static void DumpSixBefore199() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g", "msb1780" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_before199.txt")); }   // 1.9.9 rename: run BEFORE BuildAll (the project still holds the 1.9.7 assets)
        public static void DumpSixAfter199() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g", "msb17" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after199.txt")); }
        public static void DumpSixAfter1914() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g", "msb17" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after1914.txt")); }
        public static void DumpSixAfter1913() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g", "msb17" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after1913.txt")); }
        public static void DumpSixAfter1912() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g", "msb17" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after1912.txt")); }
        public static void DumpSixAfter1911() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g", "msb17" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after1911.txt")); }
        public static void DumpSixAfter1910() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g", "msb17" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after1910.txt")); }
        public static void DumpFiveAfter197() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after197.txt")); }
        public static void DumpFiveAfter196() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after196.txt")); }
        public static void DumpFiveAfter195() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after195.txt")); }
        public static void DumpFiveAfter194() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after194.txt")); }
        public static void DumpFiveAfter191() { foreach (var n in new[] { "b25h", "ga25x", "nimrod", "fd32", "b17g" }) Dump(FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after191.txt")); }
        public static void DumpB25HStandalone() => Dump("Assets/Blueprinter/Mods/b25h_mitchell", Path.Combine(Logs, "dump_b25h_standalone.txt"));
        public static void DumpB25HCombined() => Dump(FamilyRoot + "/b25h", Path.Combine(Logs, "dump_b25h_family.txt"));
        public static void DumpGA25XCombined() => Dump(FamilyRoot + "/ga25x", Path.Combine(Logs, "dump_ga25x_family.txt"));

        public static void Dump(string folder, string outFile)
        {
            var sb = new StringBuilder();
            var paths = AssetDatabase.FindAssets("", new[] { folder }).Select(AssetDatabase.GUIDToAssetPath).Where(p => !AssetDatabase.IsValidFolder(p)).Distinct().OrderBy(p => p, StringComparer.Ordinal).ToList();
            string Rel(string p) => p.StartsWith(folder + "/") ? p.Substring(folder.Length + 1) : p;
            var guidRel = paths.ToDictionary(p => AssetDatabase.AssetPathToGUID(p), Rel);
            string Ref(Object v, GameObject prefabRoot)
            {
                if (v == null) return "null";
                if (prefabRoot != null)
                {
                    Transform t = v is GameObject go ? go.transform : v is Component c ? c.transform : null;
                    if (t != null && t.root == prefabRoot.transform)
                    {
                        var hp = HPath(t, prefabRoot.transform);
                        if (v is GameObject) return "go:" + hp;
                        var comps = t.GetComponents(v.GetType()); int idx = Array.IndexOf(comps, (Component)v);
                        return $"comp:{hp}#{v.GetType().Name}[{idx}]";
                    }
                }
                var ap = AssetDatabase.GetAssetPath(v);
                if (string.IsNullOrEmpty(ap)) return $"scene:{v.GetType().Name}:{v.name}";
                var main = AssetDatabase.LoadMainAssetAtPath(ap) == v;
                return (ap.StartsWith(folder + "/") ? "own:" + Rel(ap) : "ext:" + ap) + (main ? "" : $"|{v.GetType().Name}:{v.name}");
            }
            void Props(Object o, GameObject prefabRoot, string indent)
            {
                var so = new SerializedObject(o); var it = so.GetIterator(); bool enter = true;
                while (it.Next(enter))
                {
                    enter = it.propertyType != SerializedPropertyType.String;
                    if (it.propertyPath == "m_Script" || it.propertyPath == "m_GameObject" || it.propertyPath == "m_CorrespondingSourceObject" || it.propertyPath == "m_PrefabInstance" || it.propertyPath == "m_PrefabAsset") continue;
                    if (it.name == "m_FileID" || it.name == "m_PathID") continue;   // instance ids (session-dependent)
                    if (it.name == "_prefabHash") { sb.Append(indent).Append(it.propertyPath).Append(" = <path-derived, skipped>\n"); continue; }
                    string val;
                    switch (it.propertyType)
                    {
                        case SerializedPropertyType.ObjectReference: val = Ref(it.objectReferenceValue, prefabRoot); enter = false; break;
                        case SerializedPropertyType.Float: val = it.floatValue.ToString("R"); break;
                        case SerializedPropertyType.Integer: val = it.longValue.ToString(); break;
                        case SerializedPropertyType.Boolean: val = it.boolValue ? "1" : "0"; break;
                        case SerializedPropertyType.String:
                            val = it.stringValue;
                            if (val != null && val.Length == 32 && guidRel.TryGetValue(val, out var rp)) val = "guid->own:" + rp;
                            else if (val != null && val.Length == 32 && val.All(ch => "0123456789abcdef".Contains(ch)) && !string.IsNullOrEmpty(AssetDatabase.GUIDToAssetPath(val))) val = "guid->ext:" + AssetDatabase.GUIDToAssetPath(val);
                            break;
                        case SerializedPropertyType.Enum: val = it.enumValueIndex.ToString(); break;
                        case SerializedPropertyType.Vector2: val = it.vector2Value.ToString("R"); enter = false; break;
                        case SerializedPropertyType.Vector3: val = it.vector3Value.ToString("R"); enter = false; break;
                        case SerializedPropertyType.Vector4: val = it.vector4Value.ToString("R"); enter = false; break;
                        case SerializedPropertyType.Quaternion: val = it.quaternionValue.ToString("R"); enter = false; break;
                        case SerializedPropertyType.Color: val = it.colorValue.ToString("R"); enter = false; break;
                        case SerializedPropertyType.Rect: val = it.rectValue.ToString("R"); enter = false; break;
                        case SerializedPropertyType.Bounds: val = it.boundsValue.ToString("R"); enter = false; break;
                        case SerializedPropertyType.AnimationCurve:
                            val = string.Join(";", it.animationCurveValue.keys.Select(k => $"{k.time:R},{k.value:R},{k.inTangent:R},{k.outTangent:R}")); enter = false; break;
                        case SerializedPropertyType.LayerMask: val = it.intValue.ToString(); break;
                        case SerializedPropertyType.ArraySize: val = it.intValue.ToString(); break;
                        case SerializedPropertyType.ManagedReference: val = "managed:" + it.managedReferenceFullTypename; break;
                        case SerializedPropertyType.Generic: continue;
                        default: val = "(" + it.propertyType + ")"; break;
                    }
                    if (it.propertyPath.Contains("m_LocalIdentfierInFile") || it.propertyPath == "m_LocalIdentfierInFile") continue;
                    sb.Append(indent).Append(it.propertyPath).Append(" = ").Append(val).Append('\n');
                }
            }
            int counts = 0;
            foreach (var p in paths)
            {
                sb.Append("##### ").Append(Rel(p)).Append('\n');
                if (p.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
                {
                    sb.Append("  file sha256 ").Append(Sha256(Path.GetFullPath(p))).Append('\n');
                    var ti = AssetImporter.GetAtPath(p) as TextureImporter;
                    if (ti != null) sb.Append($"  importer type {ti.textureType} sRGB {ti.sRGBTexture} mip {ti.mipmapEnabled} max {ti.maxTextureSize} comp {ti.textureCompression} alphaT {ti.alphaIsTransparency} wrap {ti.wrapMode} sprite {ti.spriteImportMode}\n");
                    counts++; continue;
                }
                var all = AssetDatabase.LoadAllAssetsAtPath(p).Where(a => a != null).ToList();
                var mainObj = AssetDatabase.LoadMainAssetAtPath(p);
                if (mainObj is GameObject prefab)
                {
                    foreach (var t in prefab.GetComponentsInChildren<Transform>(true).OrderBy(x => HPath(x, prefab.transform), StringComparer.Ordinal))
                    {
                        sb.Append("  [").Append(HPath(t, prefab.transform)).Append("] layer ").Append(t.gameObject.layer).Append(" active ").Append(t.gameObject.activeSelf ? 1 : 0).Append('\n');
                        var cs = t.GetComponents<Component>();
                        for (int i = 0; i < cs.Length; i++)
                        {
                            if (cs[i] == null) { sb.Append("    MISSING SCRIPT\n"); continue; }
                            sb.Append("    <").Append(cs[i].GetType().FullName).Append(">\n");
                            Props(cs[i], prefab, "      ");
                            counts++;
                        }
                    }
                    continue;
                }
                foreach (var a in all.OrderBy(a => a.GetType().Name + ":" + a.name, StringComparer.Ordinal))
                {
                    sb.Append("  {").Append(a.GetType().Name).Append(':').Append(a.name).Append("}\n");
                    if (a is Mesh m)
                    {
                        sb.Append("    mesh ").Append(MeshHash(m)).Append($" v {m.vertexCount} sub {m.subMeshCount} bounds {m.bounds.ToString("R")}\n");
                        counts++; continue;
                    }
                    if (a is Texture2D) { counts++; continue; }
                    Props(a, null, "    ");
                    counts++;
                }
            }
            File.WriteAllText(outFile, sb.ToString());
            var h = string.Concat(SHA256.Create().ComputeHash(Encoding.UTF8.GetBytes(sb.ToString())).Select(b => b.ToString("x2")));
            Debug.Log($"[B25H] DUMP {folder}: {paths.Count} assets, {counts} objects -> {outFile} (sha256 {h})");
        }

        static string HPath(Transform t, Transform root)
        {
            var parts = new List<string>();
            for (var x = t; x != null && x != root; x = x.parent) parts.Add(x.name + "@" + x.GetSiblingIndex());
            parts.Reverse();
            return root.name + (parts.Count > 0 ? "/" + string.Join("/", parts) : "");
        }

        public static string MeshHash(Mesh m)
        {
            using (var s = SHA256.Create())
            {
                var ms = new MemoryStream(); var w = new BinaryWriter(ms);
                foreach (var v in m.vertices) { w.Write(v.x); w.Write(v.y); w.Write(v.z); }
                foreach (var v in m.normals) { w.Write(v.x); w.Write(v.y); w.Write(v.z); }
                for (int ch = 0; ch < 4; ch++) { var uv = new List<Vector2>(); m.GetUVs(ch, uv); foreach (var v in uv) { w.Write(v.x); w.Write(v.y); } }
                for (int i = 0; i < m.subMeshCount; i++) { w.Write((int)m.GetTopology(i)); foreach (var x in m.GetIndices(i)) w.Write(x); }
                w.Flush();
                return string.Concat(s.ComputeHash(ms.ToArray()).Take(8).Select(b => b.ToString("x2")));
            }
        }

        // =================================================================== aero report (offline flight model inputs)
        // For every AeroPart of a built prefab: mass, wing area, drag area, airfoil, liftNormal orientation and the world
        // point the lift acts at (collider centroid + centerOfLift, AeroJob_Math), the mass-weighted CoM, and the 128-point
        // lift/drag charts of the aircraft's airfoils exactly as the game samples them (Airfoil.BuildLiftChart: t = (i-64) * 0.04908734).
        public static void AeroGA25X() => Aero(Existing(FamilyRoot + "/ga25x/GA25X.prefab", "Assets/Blueprinter/Mods/ga25x/GA25X.prefab"), Path.Combine(Logs, "aero_ga25x.txt"));
        public static void AeroNimrod() => Aero(Existing(FamilyRoot + "/nimrod/NIMROD1.prefab"), Path.Combine(Logs, "aero_nimrod.txt"));
        public static void AeroMSB1780() => Aero(Existing(FamilyRoot + "/msb17/MSB17.prefab"), Path.Combine(Logs, "aero_msb1780.txt"));   // 1.9.2: level-speed fit (tools/flightmodel/msb1780_fm.py)
        public static void AeroB17G() => Aero(Existing(FamilyRoot + "/b17g/B17G.prefab"), Path.Combine(Logs, "aero_b17g.txt"));   // 1.9.3: the B-17G touchdown comparison (tools/flightmodel/msb1780_touchdown.py)
        public static void AeroB25H() => Aero(Existing(FamilyRoot + "/b25h/B25H.prefab", "Assets/Blueprinter/Mods/b25h_mitchell/B25H.prefab"), Path.Combine(Logs, "aero_b25h.txt"));
        static string Existing(params string[] p) => p.FirstOrDefault(x => AssetDatabase.LoadAssetAtPath<GameObject>(x) != null) ?? p[0];

        static void Aero(string prefabPath, string outFile)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (prefab == null) throw new Exception("no prefab " + prefabPath);
            var inst = (GameObject)Object.Instantiate(prefab);
            var sb = new StringBuilder();
            try
            {
                var BF = System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Public;
                object F(object o, string n) { for (var t = o.GetType(); t != null; t = t.BaseType) { var f = t.GetField(n, BF | System.Reflection.BindingFlags.DeclaredOnly); if (f != null) return f.GetValue(o); } return null; }
                float mass = 0; Vector3 com = Vector3.zero;
                sb.Append("part\tmass\twingArea\tdragArea\tairfoil\tliftPoint(x,y,z)\tcentroid(x,y,z)\tliftNormal fwd\tliftNormal up\tparent\n");
                foreach (var ap in inst.GetComponentsInChildren<AeroPart>(true))
                {
                    var mc = ap.GetComponent<MeshCollider>();
                    var cen = mc != null ? ap.transform.TransformPoint(mc.sharedMesh.bounds.center) : ap.transform.position;
                    var lnObj = F(ap, "liftNormal") as Transform; var ln = lnObj != null ? lnObj : ap.transform;
                    var col = (Vector3)F(ap, "centerOfLift");
                    var lp = cen + ln.rotation * col;
                    mass += ap.mass; com += cen * ap.mass;
                    sb.Append($"{ap.name}\t{ap.mass}\t{F(ap, "wingArea")}\t{ap.dragArea}\t{F(ap, "airfoil")}\t{lp.x:F3},{lp.y:F3},{lp.z:F3}\t{cen.x:F3},{cen.y:F3},{cen.z:F3}\t{ln.forward.ToString("F3")}\t{ln.up.ToString("F3")}\t{(ap.transform.parent ? ap.transform.parent.name : "-")}\n");
                }
                com /= mass;
                sb.Append($"TOTAL mass {mass} CoM {com.x:F3},{com.y:F3},{com.z:F3}\n");
                foreach (var lg in inst.GetComponentsInChildren<LandingGear>(true)) sb.Append($"gear {lg.name} axle {((Transform)F(lg, "axle")).position.ToString("F3")} r {F(lg, "wheelRadius")}\n");
                foreach (var hp in inst.GetComponentInChildren<WeaponManager>(true).hardpointSets.SelectMany(s => s.hardpoints.Select(h => (s.name, h)))) sb.Append($"hardpoint {hp.Item1} {hp.h.transform.name} part {hp.h.part?.name} at {hp.h.transform.position.ToString("F3")}\n");
                var def = inst.GetComponent<Aircraft>().definition as AircraftDefinition;
                var prm = def.aircraftParameters;
                for (int a = 0; a < prm.airfoils.Length; a++)
                {
                    var af = prm.airfoils[a];
                    sb.Append($"airfoil {a} {af.name}\n  i\tt\tCL\tCD\n");
                    for (int i = 0; i < 128; i++) { float t = (i - 64) * 0.04908734f; sb.Append($"  {i}\t{t:F5}\t{af.liftCoef.Evaluate(t):F5}\t{af.dragCoef.Evaluate(t):F5}\n"); }
                }
            }
            finally { Object.DestroyImmediate(inst); }
            File.WriteAllText(outFile, sb.ToString());
            Debug.Log("[B25H] AERO " + prefabPath + " -> " + outFile);
        }
    }
}
