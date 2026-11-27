# Changelog

Heritage Pairs, newest first. Versions before 1.9.10 were private test builds and were never released.

## 1.9.15

New aircraft:

- **Mitsubishi A6M2 Zero Model 21** (key `A6M2`), the historical carrier fighter of the fourth pair (its rebuilt 2080s twin is not
  made yet and is not in this release). Own model, period cockpit with working dials, flight model tuned for top speed (about
  520 km/h at 4.5 km), retracting main gear and tail wheel, arrester hook, folding wing tips, damage model with open break ends
  and internals; it takes off from airfields and carriers. Its four weapons are made by this mod from stock parts: two
  Type 97 7.7 mm machine guns in the cowl (500 rounds each, with tracers), two Type 99 20 mm cannons in the wings (60 rounds
  each), two Type 97 No.6 60 kg bombs under the wings, and a fixed 250 kg special-attack charge. The charge is **Event
  Content**, like the game's own UFO and AIR-2 Genie: it shows in the loadout only when the mission's Event Content box is
  ticked, it is never part of a standard loadout, and it goes off when fired, when the aircraft crashes, is shot down or is
  abandoned, not when parked. Seven liveries: IJN Grey-White (1941) for both factions; BDF Temperate Camo, BDF Matte Gray and
  BDF Navy; PALA Desert Camo, PALA Matte Black and PALA Navy Splinter.

Bug fixes (all in the companion plugin unless said otherwise; reported by the owner on 2026-11-26):

- **B-17G tail falling off while taxiing** (8 of 11 computer-flown B-17Gs lost it on the ground; the B-25H and GA-25X could drop
  an engine nacelle, the Nimrod its engine). The cause was a weak extra joint that only keeps parts from rubbing: it snapped under
  normal ground loads, and the game's rule "when a part's joint breaks, loosen everything that leans on it" then dropped the whole
  tail. These weak joints are now removed when the physics starts, an aircraft's own parts no longer collide with each other,
  and the second joint every part has to the part two steps up can no longer break while the part is undamaged. Real damage still
  breaks parts off as before. In the game tests of the final fix rounds every computer-flown B-17G taxied out and took off with its tail on (before the fix
  8 of 11 lost it).
- **Computer-flown aircraft taxiing in circles.** This is a bug of the game itself (stock CI-22 and VT-7 do it too): when the taxi
  path runs out the AI never plans a new one, and its "pull aside" step can aim at a point it cannot reach. Now an AI aircraft that
  circles is caught (circling its target, circling its pull-aside point, or more than two full turns in 90 s in a small area),
  re-plans its route at a crawl, and if it still cannot get there it stops and parks the game's own way. An aircraft that waits
  beside the runway start for over a minute without getting onto it gets a new route. This applies to every computer-flown
  aircraft, stock ones included. In the last game test no aircraft circled without being caught in 48 game minutes.
- **Stuck-together and wrecked aircraft now get their crews out.** A computer-flown aircraft on the ground that loses a part or a
  wheel, or is damaged (10 hit points or more after its first 20 s), bails out at once; one that makes no progress, or is stuck
  against another aircraft for 10 s, is re-routed, sent on to take off, or bails out, so the spot clears. A wheel standing on
  another aircraft is no longer treated as a moving carrier deck (that held the pair together). Aircraft in a normal take-off
  queue and parked aircraft are left alone. **Player-flown aircraft are never touched.**
- **The mod's light bombs can be shot down.** The Nimrod Mk I's 20 lb Cooper bomb and the Zero's No.6 60 kg bomb can now be
  destroyed by lasers and anti-air blasts, like stock missiles; one destroyed before it arms shows a small puff. The game's own
  bombs are unchanged (lasers cannot hurt them in the game either).
- AI take-off: an AI aircraft is handed over to its take-off run only when it is actually on the runway and the runway is free;
  the runway line-up of the FD-32, Mk I, B-17G, MSB-17 and Zero also works on a second take-off after a resupply.
- **Nimrod Mk I and FD-32 break ends** (pack change): when these biplanes break apart, the broken ends are open like the game's
  own aircraft (dark edges, a set-back frame or rib, short stubs, the fuel tank, radio, oxygen bottle and battery in their bays)
  instead of solid metal discs. Paint and liveries are unchanged.
- Every new plugin piece has its own setting (`Auto` = on, `On`, `Off`) in `b25h.instruments.cfg`, sections `[Ground]`,
  `[Physics]` and `[Weapons]`, and switches itself off for the rest of the session if it ever hits an error. The plugin writes a
  short "1.9.15 counters" line to the BepInEx log every two minutes while something has changed.
- Nothing else changed: the B-25H, GA-25X, B-17G and MSB-17 models, all flight models, masses, weapons and liveries of the six
  1.9.14 aircraft are those of 1.9.14.

## 1.9.14

- GA-25X propellers: when the propellers switched to their blur disc, pieces of the blade tips stayed visible and kept
  spinning (reported by players). The grey metal band near each blade tip was a separate part, and the game hides only the
  blade itself when the blur disc shows; the band is now part of the blade and hides with it. Tried in the game: with the
  propellers spinning, all twelve blades and their tip bands are hidden. Also changed: the blur disc no longer has a yellow
  band at the tip radius (a leftover from the B-25H's yellow-tipped propeller; the GA-25X blades have no yellow).
- GA-25X cockpit art (reported by players with pictures): the painted panels and the modelled switches and knobs did not
  line up. Every modelled switch, knob, guard and button on both side consoles, the radio panel, the HUD panel and the plates
  beside the main panel now sits on its painted counterpart (measured within 2 mm on the model). The painted levers under
  modelled toggle switches were removed from the art, so each switch shows one lever; doubled labels were removed; the radio
  is relabelled (FREQ, VOL, SQL, PWR, TEST, T/R+G); the LIGHTS plate, which was hidden behind the side console, was moved up
  so all three plates by the main panel read whole; the caution boxes on the glare shield show whole MASTER CAUTION and
  FIRE R lamps; the placards on the rear bulkhead now face the crew. Controls that were painted only (ignition, de-ice,
  battery, flaps, engine start, the keypad) are now modelled. The liveries are not affected: the cockpit art is a separate
  texture, and only the cockpit mesh of the GA-25X changed.
- Cockpit lamps glow (player suggestion): on the GA-25X the painted warning lamps (MASTER CAUTION, GEAR) and the green
  frequency and counter digits now give off a little light; placards and labels do not.
- Gear lights on the GA-25X (nose leg), FD-32 and MSB-17 (both main legs) (player suggestion), using the game's own gear
  light from the CI-22: a small lamp housing with a lens on the front of the leg, a lens glow and a spot light that is on
  while the gear is down. The light does not shine on the aircraft itself. The FD-32 and MSB-17 sit nose-up on their tail
  wheel, so their lights are aimed down to light the ground ahead rather than the sky.
- Nothing else changed: flight models, masses, weapons, liveries and the plugin's behaviour are those of 1.9.13. The B-25H,
  Nimrod Mk I and B-17G are identical to 1.9.13.

## 1.9.13

- FD-32 and Nimrod Mk I: the outer panels of the upper wing kinked at the joint with the centre section when the aircraft
  rolled or pulled up hard at speed (reported on Discord for the FD-32). Each wing panel is a separate part held to its
  neighbours by the game's physics joints; the game solved these joints 6 times per physics step, which was not enough to
  hold the light upper wing against its lift. The wing joints of both biplanes are now solved 100 times per step, the game's
  own setting for this (the stock A-19 uses 12 on its outer wing joints).
- Dark seam backing at the same joints: the cut ends of the wing skin and the short spar / stringer stubs that cross the
  joint are now dark matte instead of light grey, and a thin dark band hidden just under the skin on both sides of each joint
  means a small opening in a hard pull shows dark, not a light line or light specks (offline pictures, 1.2 mm and 5 mm gap or
  step). No texture or livery changed; at rest the band is covered by the skin. The band is in two halves and the outer half
  belongs to the outer panel, so a shot-off panel takes it along and leaves no band edge on the centre section; the centre
  section's own spar stubs still stick out of the broken end as in 1.9.12, now dark.
- Measured in the game so far (FD-32 full pull at 8-9 g, one aircraft): 1.9.12 2.21 degrees with a 99 mm step at 8.3 g; the
  first test build (20 solves) 0.41 degrees / 18 mm; with the setting changed during flight on that test build, 60 solves gave
  under about 0.04 degrees / 1.2 mm (a thin light hairline could still show in BDF Temperate Camo) and 100 solves
  0.00 degrees / 0 mm. The Nimrod Mk I went from 0.5-0.7 degrees to under 0.05 at 20 solves; on the final download (100) it reads 0.0019 degrees or less at 6.5 g.
  With one aircraft there was no measurable frame-time cost up to 100; many aircraft were not measured.
- Tried in the game on the final download (pack sha256 db92912e41ed..., one aircraft): it loads once with no errors; 100 solves
  read on the five wing parts of the FD-32 and the Mk I. FD-32 parked: no line or band at the joint. FD-32 full pull at 8.07 g
  (BDF Temperate Camo) and 8.10 g (BDF Navy Hex): right upper panel 0.0072 / 0.0069 degrees, 0.24 mm; the chase pictures show
  a closed seam, no light line or specks. Mk I at 6.5 g: 0.0019 degrees / 0.2 mm or less. Panel shot off at 122 m/s: panel
  and aileron come off, the centre section's broken end shows a grey ribbed face with no dark strip. Take-off FD-32 5.3 s /
  65 m, Mk I 6.2 s / 88 m. The previous candidate with the same wing joints (only the seam backing differs) gave 0.0072
  degrees at 8.1 g, straight taxi for both aircraft and no frame-time cost (4.07 vs 4.06 ms); its two scripted landings did
  not reach the runway (our approach script, not the aircraft), so a landing has not been shown. Landings, carrier traps, PALA
  liveries at the joint, a Mk I panel shot off and missions with many FD-32s or Mk Is were not tried on any 1.9.13 build.
- Nothing else changed: masses, centre of gravity, flight models, joint break strengths, weapons, liveries, textures and the
  plugin's behaviour are those of 1.9.12. The other four aircraft are byte-identical to 1.9.12.

## 1.9.12

- Air brakes on all six aircraft. Whenever the throttle is below 5 % the air brake is on, on the ground as well as in the
  air, and the throttle gauge reads AIRBRAKE; at 5 % and above it closes again (about a second, the game's own opening
  speed). (The game's own aircraft open theirs only at exactly 0.)
  - B-25H, Nimrod Mk I and B-17G: the braking has no visible parts.
  - GA-25X: a panel on each upper shoulder of the rear fuselage opens upward and outward. The faction emblems on the
    fuselage sides stay where they are.
  - FD-32: a small panel on each side of the rear fuselage, behind the faction emblem.
  - MSB-17: six spoiler panels on top of the wing, three on each side, ahead of the flaps. The MSB-17 already braked at
    throttle 0; it now shows it.
- The brake has no ground exception: it also works on the landing roll, and an aircraft parked at idle stands with its
  brake on. On the GA-25X, FD-32 and MSB-17 the panels therefore stand open while parked at idle.
- MSB-17: eight green formation-light strips, as on the game's own aircraft and on the GA-25X and FD-32: under the cockpit
  side windows, on the waist, on both sides of the fin and on the wing tips. They are lit with the landing gear down or with
  the navigation lights switched on.
- Naval liveries for the carrier aircraft: Nimrod Mk I "BDF Navy Gray" and "PALA Navy", FD-32 "BDF Navy Hex" and
  "PALA Navy Splinter". They are added at the end of each list, so missions and saves keep the liveries they had.
  Computer-flown aircraft can now appear in the naval liveries too: the game picks from the whole list of a faction.
- New settings in `b25h.instruments.cfg`, section `[Airbrake]`: `AirbrakeIdle1912` (Off = the brake opens only at exactly 0,
  as on the game's own aircraft), `AirbrakeThrottle1912` (the limit, 0.05 = 5 %; 0 to 0.2) and `HudAirbrake1912`
  (Off = the gauge texts of 1.9.11).
- Nothing else changed: flight models, weapons and the existing liveries and textures are those of 1.9.11.
- Tried in the game: the air brake and gauge text on all six aircraft, the panels, braking in flight, a GA-25X landing roll
  with the brake open to the stop, FD-32 and Nimrod Mk I idling on a moving carrier, the naval liveries in both factions'
  lists. Not tried: B-17G and MSB-17 landings with the brake, AI taxi and landings, multiplayer.
- Holding the throttle exactly at 5 % makes the brake open and close about once a second.

## 1.9.11

- Fixed: the FD-32's rudder was damaged, and sometimes torn off, when the aircraft came up on a carrier's lift. On the aft
  lifts of the Annex and the Hyperion its tail was placed over a raised stop at the back of the lift. The FD-32 now appears
  1.2 m further forward, clear of it. The Nimrod Mk I, whose tail was close to the same stop, appears 0.7 m further forward.
  This applies to every hangar, shelter and deck spot; both aircraft still have plenty of room in front.
- The rudders of the FD-32 and the Nimrod Mk I no longer take damage from light bumps, the same as the rudders of the
  game's own aircraft. They can still be shot off or torn off in a crash.
- Nothing else changed; the plugin only carries the new version number.

## 1.9.10 (first public release)

- Two logo-like marks removed from cockpit placards: the winged emblem on the B-17G data plate and the triangle emblem on the
  GA-25X data plate. The plates keep their text. Nothing else in the aircraft changed from 1.9.9.
- The plugin now shows in the BepInEx log as "Heritage Pairs Instruments" (was "B-25H Instruments"). Its GUID and its config
  file `b25h.instruments.cfg` are unchanged, so settings carry over.
- Licence and credits now say exactly what is and is not ours: component settings copied from the game's stock prefabs and
  real maker names are not covered; the faction emblems and national insignia on the liveries remain their owners' designs while
  the liveries stay free to use and share; AI-generated files are offered as-is.
- README: tested and untested things stated as they are (carrier landings, multiplayer, mission editor), build versions recorded.

## 1.9.9 (release candidate, not released)

- The MSB-17/80 is now called **MSB-17**. Its internal key changed from `MSB1780` to `MSB17`: missions and saves made with an
  earlier test build that contain it need the aircraft placed again.
- The mod id and install folder are now `HeritagePairs`.
- Plugin cleaned up for the public release: two unused pieces removed (an old Nimrod fixed-gear / HUD workaround that had been
  off by default since 1.5.5, and a bomb-detonation log line). Flying and handling are unchanged from 1.9.8.
- Licence, credits and this changelog added.

## 1.9.8

- Nimrod Mk I and FD-32 no longer creep while parked on a moving carrier or its lift. Opening the throttle releases them.

## 1.9.7

- GA-25X and MSB-17 lasers can no longer burn their own aircraft.
- Nimrod Mk I and FD-32 no longer slide off a moving carrier deck.
- MSB-17: tail windows plated over, doors and hatches shade smoothly, throttle levers sit in a proper quadrant.

## 1.9.0 to 1.9.6

- New aircraft: **MSB-17** (then MSB-17/80), the rebuilt B-17G: four turboshafts with contra-rotating propellers, weapons bay,
  side bays, wing pylons, two twin 20 mm turrets, two anti-missile lasers, crew of four in ejection seats.
- Its own two-pilot flight deck with stock sticks, throttle, seats and screens, plus weapon-officer and electronic-warfare stations.
- Fixes from its first flights: level speed, straight take-off run, gentler computer-flown landings, control with one engine out.

## 1.8.0 to 1.8.18

- B-17G: new nose, engine nacelles, tail and turrets; our own .50 calibre guns on the B-25H and B-17G; control columns that
  move the right way; every cockpit dial driven.
- Tail-wheel aircraft (B-17G, Nimrod Mk I, FD-32): straight take-off runs without input, taxi turns without skidding, brakes
  that do not nose the aircraft over.
- B-25H: computer-flown aircraft follow terrain and no longer stall on climb-out. GA-25X: pulls out of strafing runs in time.
- A lag that grew during long matches (caused by this mod's plugin) is fixed.
- Skins re-baked; damage holes show the structure inside.

## 1.6.0 to 1.7.13

- New aircraft: **B-17G Flying Fortress**, with thirteen guns, bomb bay, ten crew and a period cockpit.
- Take-off, landing and computer-flown handling tuned over several rounds.

## 1.5.0 to 1.5.7

- New aircraft: **FD-32 Nimrod**, the rebuilt Nimrod: electric drive, retracting gear, glass cockpit, four pylons, tail hook.
- Nimrod Mk I uses the game's normal gear logic; tail hooks stow again after a carrier approach is abandoned.

## 1.1.0 to 1.4.2

- New aircraft: **Hawker Nimrod Mk I**, with working period instruments, Vickers guns, 20 lb bombs and an arrester hook; flies
  from every carrier.
- Undercarriage no longer breaks on normal landings.

## 0.1 to 1.0

- **B-25H Mitchell** and **GA-25X**: the first pair. Both cockpits rebuilt; liveries for both factions.
