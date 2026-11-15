# Changelog

Heritage Pairs, newest first. Versions before 1.9.10 were private test builds and were never released.

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
