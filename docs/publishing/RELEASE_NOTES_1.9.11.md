# Heritage Pairs 1.9.11

Text for the GitHub release `v1.9.11`. Attach only `HeritagePairs_1.9.11.zip` to the release.

---

> This project is an unofficial community modification and is not affiliated with, sponsored by, or endorsed by Shockfront Studios Pty Ltd. Original Nuclear Option assets, vehicle designs, audio, and code are Copyright (c) 2026 Shockfront Studios Pty Ltd. All rights reserved. Nuclear Option and Shockfront Studios are trademarks or registered trademarks of Shockfront Studios Pty Ltd. Original mod content and all other trademarks belong to their respective owners.

**Made with AI.** The models, textures, liveries, flight models and all code in this mod were made with Claude Code (an AI coding
agent), directed and tested by a human. Part of the art was generated with AI image and 3D models on fal.ai. Details are in the
README ("AI assistance") and in CREDITS.md.

## What changed

- Fixed: the FD-32's rudder was damaged, and sometimes torn off, when the aircraft came up on a carrier's lift. On the aft lifts
  of the Annex and the Hyperion its tail was placed over a raised stop at the back of the lift. The FD-32 now appears 1.2 m
  further forward, clear of it; the Nimrod Mk I appears 0.7 m further forward.
- The rudders of the FD-32 and the Nimrod Mk I no longer take damage from light bumps, the same as the rudders of the game's
  own aircraft. They can still be shot off or torn off in a crash.
- Nothing else changed. Missions, saves and settings from 1.9.10 keep working.

## Requirements

- Nuclear Option 0.34.6 (the version this release was built and tested against)
- BepInEx 5 (5.4.x, Windows x64)
- Blueprinter 2.1.1 by nikkorap (`com.nikkorap.blueprinter`)

## Install

With NOMM (Nuclear Option Mod Manager): update "Heritage Pairs".

By hand: unpack `HeritagePairs_1.9.11.zip` into
`Nuclear Option\BepInEx\plugins\com.nikkorap.blueprinter\addons\HeritagePairs\`, so that the folder holds
`Heritage Pairs_1.9.11.nobp` and `B25H.Instruments.dll`. Remove the 1.9.10 files from that folder first: two packs in the folder
load the mod twice.

The download is about 240 MB.

## File

`HeritagePairs_1.9.11.zip`, 249,421,859 bytes

sha256: `ff1a332df7deee467f1ebee9346dd9ffc272c495e04efa4491e6abe7b391b064`

It holds two files: `Heritage Pairs_1.9.11.nobp` (the aircraft pack) and `B25H.Instruments.dll` (the companion plugin; its
source is in this repository under `src/B25H.Instruments`, MIT).

## Known issues

See "Known issues" in the README. In short: multiplayer and mission-editor placement have not been tested; the Nimrod Mk I
tipped onto its nose in the one scripted carrier landing; the B-25H needs back stick to lift off.

## Licence

Code: MIT. Art and pack content made for this mod: CC0 1.0; LICENSE-ASSETS and the README say what that
does not cover (the game and settings copied from its stock parts, real maker names) and how the faction emblems and national
insignia on the liveries are treated (free to use and share on the liveries; the designs remain their owners'). The mod is free and
non-commercial, as the game's EULA requires.
