# Heritage Pairs 1.9.12

Text for the GitHub release `v1.9.12`. Attach only `HeritagePairs_1.9.12.zip` to the release.

---

> This project is an unofficial community modification and is not affiliated with, sponsored by, or endorsed by Shockfront Studios Pty Ltd. Original Nuclear Option assets, vehicle designs, audio, and code are Copyright (c) 2026 Shockfront Studios Pty Ltd. All rights reserved. Nuclear Option and Shockfront Studios are trademarks or registered trademarks of Shockfront Studios Pty Ltd. Original mod content and all other trademarks belong to their respective owners.

**Made with AI.** The models, textures, liveries, flight models and all code in this mod were made with Claude Code (an AI coding
agent), directed and tested by a human. Part of the art was generated with AI image and 3D models on fal.ai. Details are in the
README ("AI assistance") and in CREDITS.md.

## What changed

- **Air brakes on all six aircraft.** Whenever the throttle is below 5 % the air brake is on, on the ground as well as in the
  air, and the throttle gauge reads AIRBRAKE. At 5 % and above it closes again (about a second).
  - B-25H, Nimrod Mk I, B-17G: braking without visible parts.
  - GA-25X: a panel on each upper shoulder of the rear fuselage (the faction emblems on the sides stay in place).
  - FD-32: a small panel on each side of the rear fuselage.
  - MSB-17: six spoiler panels on top of the wing, ahead of the flaps.
- The brake has no ground exception: it works on the landing roll too, and an aircraft parked at idle stands with its
  panels open (GA-25X, FD-32, MSB-17).
- **MSB-17:** eight green formation-light strips (under the cockpit side windows, on the waist, on the fin, on the wing tips),
  lit with the landing gear down or with the navigation lights switched on.
- **Naval liveries:** Nimrod Mk I "BDF Navy Gray" and "PALA Navy"; FD-32 "BDF Navy Hex" and "PALA Navy Splinter". They are
  added at the end of each list; missions and saves keep the liveries they had. Computer-flown aircraft can now appear in
  the naval liveries too.
- New settings in `BepInEx\config\b25h.instruments.cfg`, section `[Airbrake]`: `AirbrakeIdle1912` (Off = brake only at
  exactly 0, as on the game's own aircraft), `AirbrakeThrottle1912` (the limit, 0.05) and `HudAirbrake1912` (Off = the gauge
  texts of 1.9.11).
- Nothing else changed: flight models, weapons and the existing liveries are those of 1.9.11.
- Tried in the game: the air brake and gauge text on all six aircraft, the panels, braking in flight, a GA-25X landing roll
  with the brake open to the stop, FD-32 and Nimrod Mk I idling on a moving carrier, the naval liveries in both factions'
  lists. Not tried: B-17G and MSB-17 landings with the brake, AI taxi and landings, multiplayer.

## Requirements

- Nuclear Option 0.34.6 (the version this release was built against)
- BepInEx 5 (5.4.x, Windows x64)
- Blueprinter 2.1.1 by nikkorap (`com.nikkorap.blueprinter`)

## Install

With NOMM (Nuclear Option Mod Manager): update "Heritage Pairs".

By hand: unpack `HeritagePairs_1.9.12.zip` into
`Nuclear Option\BepInEx\plugins\com.nikkorap.blueprinter\addons\HeritagePairs\`, so that the folder holds
`Heritage Pairs_1.9.12.nobp` and `B25H.Instruments.dll`. Remove the 1.9.11 files from that folder first: two packs in the folder
load the mod twice.

The download is about 243 MB.

## File

`HeritagePairs_1.9.12.zip`, 255,262,119 bytes

sha256: `98a9a101569b80c6f9a1b988ad6554769b1ac898cc2224ab6fea3b29389921d4`

It holds two files: `Heritage Pairs_1.9.12.nobp` (the aircraft pack) and `B25H.Instruments.dll` (the companion plugin; its
source is in this repository under `src/B25H.Instruments`, MIT).

## Known issues

See "Known issues" in the README. In short: multiplayer and mission-editor placement have not been tested; the Nimrod Mk I
tipped onto its nose in the one scripted carrier landing; the B-25H needs back stick to lift off; computer-flown aircraft
are expected to open and close their air-brake panels while taxiing; holding the throttle exactly at 5 % makes the brake
open and close about once a second. On the FD-32 the texture has little room beside the
cockpit, at the wing, tail and rudder tips and on part of the belly, so there both naval patterns fade to a plain colour
(blue-grey on BDF Navy Hex, mid-grey on PALA Navy Splinter); both naval patterns on both aircraft have one straight seam along
the belly centreline.

## Licence

Code: MIT. Art and pack content made for this mod: CC0 1.0; LICENSE-ASSETS and the README say what that
does not cover (the game and settings copied from its stock parts, real maker names) and how the faction emblems and national
insignia on the liveries are treated (free to use and share on the liveries; the designs remain their owners'). The mod is free and
non-commercial, as the game's EULA requires.
