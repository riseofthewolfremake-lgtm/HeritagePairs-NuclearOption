# Heritage Pairs 1.9.15

Text for the GitHub release `v1.9.15`. Attach only `HeritagePairs_1.9.15.zip` to the release.

---

> This project is an unofficial community modification and is not affiliated with, sponsored by, or endorsed by Shockfront Studios Pty Ltd. Original Nuclear Option assets, vehicle designs, audio, and code are Copyright (c) 2026 Shockfront Studios Pty Ltd. All rights reserved. Nuclear Option and Shockfront Studios are trademarks or registered trademarks of Shockfront Studios Pty Ltd. Original mod content and all other trademarks belong to their respective owners.

**Made with AI.** The models, textures, liveries, flight models and all code in this mod were made with Claude Code (an AI coding
agent), directed and tested by a human. Part of the art was generated with AI image and 3D models on fal.ai. Details are in the
README ("AI assistance") and in CREDITS.md.

## What changed

**New aircraft: Mitsubishi A6M2 Zero Model 21** (key `A6M2`), the historical carrier fighter of a fourth pair. Its rebuilt 2080s twin
is not made yet and is not in this release.

- Own model, period cockpit with working dials, retracting main gear and tail wheel, arrester hook, folding wing tips, damage model with
  open break ends and internals. It takes off from airfields and carriers.
- Four weapons made by this mod from stock parts: two Type 97 7.7 mm machine guns in the cowl (500 rounds each, tracers), two Type 99
  20 mm cannons in the wings (60 rounds each), two Type 97 No.6 60 kg bombs, and a fixed 250 kg special-attack charge.
- **The special-attack charge is Event Content**, like the game's UFO and AIR-2 Genie: it shows in the loadout only when the mission's
  Event Content box is ticked and is never part of a standard loadout. It goes off when fired, when the aircraft crashes, is shot down
  or is abandoned, not when parked.
- Seven liveries: IJN Grey-White (1941) for both factions; BDF Temperate Camo, BDF Matte Gray, BDF Navy; PALA Desert Camo, PALA Matte
  Black, PALA Navy Splinter.

**Bug fixes:**

- **B-17G tail no longer falls off while taxiing.** A weak extra joint that only keeps parts from rubbing snapped under normal ground
  loads, and the game then loosened the whole tail. Those joints are removed when the physics starts and an aircraft's own parts no
  longer collide with each other. The same fault could drop a B-25H or GA-25X engine nacelle or a Nimrod's engine. Real damage still
  breaks parts off.
- **Computer-flown aircraft no longer taxi in circles.** This is a bug of the game itself (stock aircraft do it too). An AI aircraft
  that circles or makes no progress is caught, re-plans its route, and if it still cannot get there it parks the game's own way. This
  applies to every computer-flown aircraft, stock ones included.
- **Stuck-together and wrecked aircraft get their crews out.** A computer-flown aircraft on the ground that loses a part or is damaged
  bails out; two aircraft stuck against each other are re-routed or bailed out so the spot clears; a wheel resting on another aircraft
  no longer counts as standing on a moving carrier deck. Player-flown aircraft are never touched.
- **The mod's light bombs can be shot down**: the Nimrod Mk I's 20 lb Cooper and the Zero's No.6 60 kg bomb are destroyed by lasers and
  anti-air blasts, like missiles. The game's own bombs are unchanged.
- **Nimrod Mk I and FD-32 open break ends**: when they break apart, the broken ends are open like the game's own aircraft instead of
  solid metal discs. Paint and liveries are unchanged.
- Every new plugin piece has its own setting in `b25h.instruments.cfg` (`Auto` = on, `Off` = the 1.9.14 behaviour). The full list is in
  CHANGELOG.md.

Nothing else changed: the B-25H, GA-25X, B-17G and MSB-17 models and all flight models, weapons and liveries of the six earlier
aircraft are those of 1.9.14.

## Requirements

- Nuclear Option 0.34.6 (the version this release was built and tested against)
- BepInEx 5 (5.4.x, Windows x64)
- Blueprinter 2.1.1 by nikkorap (`com.nikkorap.blueprinter`); tested with 2.1.2

## Install

With NOMM (Nuclear Option Mod Manager): update "Heritage Pairs".

By hand: unpack `HeritagePairs_1.9.15.zip` into
`Nuclear Option\BepInEx\plugins\com.nikkorap.blueprinter\addons\HeritagePairs\`, so that the folder holds
`Heritage Pairs_1.9.15.nobp` and `B25H.Instruments.dll`. Remove the 1.9.14 files from that folder first: two packs in the folder
load the mod twice.

The download is about 264 MB.

## File

`HeritagePairs_1.9.15.zip`, 276,735,346 bytes

sha256: `dc550e51cb32a4c86f3d6d32ccf7304dd1e51d8ef45d7a5b240bc3aba855b0c7`

It holds two files: `Heritage Pairs_1.9.15.nobp` (the aircraft pack) and `B25H.Instruments.dll` (the companion plugin; its
source is in this repository under `src/B25H.Instruments`, MIT).

## Known issues

See "Known issues" in the README. New in 1.9.15: the Zero and the bug fixes were tried in the game on test builds with the same
aircraft and plugin code (only the version number differs); a computer-flown aircraft that is caught circling or stuck may bail out
and leave its aircraft on the taxiway for the game to clear; some of the new taxi rules (giving up after a second circle, two circles
in 90 seconds, stuck for 10 seconds) have not come up in a game test yet. Multiplayer and mission-editor placement have not been
tested.

## Licence

Code: MIT. Art and pack content made for this mod: CC0 1.0; LICENSE-ASSETS and the README say what that
does not cover (the game and settings copied from its stock parts, real maker names) and how the faction emblems and national
insignia on the liveries are treated (free to use and share on the liveries; the designs remain their owners'). The mod is free and
non-commercial, as the game's EULA requires.
