# Heritage Pairs 1.9.14

Text for the GitHub release `v1.9.14`. Attach only `HeritagePairs_1.9.14.zip` to the release.

---

> This project is an unofficial community modification and is not affiliated with, sponsored by, or endorsed by Shockfront Studios Pty Ltd. Original Nuclear Option assets, vehicle designs, audio, and code are Copyright (c) 2026 Shockfront Studios Pty Ltd. All rights reserved. Nuclear Option and Shockfront Studios are trademarks or registered trademarks of Shockfront Studios Pty Ltd. Original mod content and all other trademarks belong to their respective owners.

**Made with AI.** The models, textures, liveries, flight models and all code in this mod were made with Claude Code (an AI coding
agent), directed and tested by a human. Part of the art was generated with AI image and 3D models on fal.ai. Details are in the
README ("AI assistance") and in CREDITS.md.

## What changed

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

## Requirements

- Nuclear Option 0.34.6 (the version this release was built against)
- BepInEx 5 (5.4.x, Windows x64)
- Blueprinter 2.1.1 by nikkorap (`com.nikkorap.blueprinter`)

## Install

With NOMM (Nuclear Option Mod Manager): update "Heritage Pairs".

By hand: unpack `HeritagePairs_1.9.14.zip` into
`Nuclear Option\BepInEx\plugins\com.nikkorap.blueprinter\addons\HeritagePairs\`, so that the folder holds
`Heritage Pairs_1.9.14.nobp` and `B25H.Instruments.dll`. Remove the 1.9.13 files from that folder first: two packs in the folder
load the mod twice.

The download is about 243 MB.

## File

`HeritagePairs_1.9.14.zip`, 255,249,908 bytes

sha256: `6a10bcbb4df8dbd4ca59c9a6ab8b060cb02a92b53e51f80a5b000938b314ae04`

It holds two files: `Heritage Pairs_1.9.14.nobp` (the aircraft pack) and `B25H.Instruments.dll` (the companion plugin; its
source is in this repository under `src/B25H.Instruments`, MIT).

## Known issues

See "Known issues" in the README. New in 1.9.14: the gear lights were tried in the game on the ground by day and night;
switching off with the gear up was last checked in the air on a test build, not on this download. The IFF MODE dial in the
GA-25X cockpit reads OFF twice (a painting slip in the panel art). Multiplayer and mission-editor placement have not been
tested.

## Licence

Code: MIT. Art and pack content made for this mod: CC0 1.0; LICENSE-ASSETS and the README say what that
does not cover (the game and settings copied from its stock parts, real maker names) and how the faction emblems and national
insignia on the liveries are treated (free to use and share on the liveries; the designs remain their owners'). The mod is free and
non-commercial, as the game's EULA requires.
