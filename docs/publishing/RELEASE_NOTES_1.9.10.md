# Heritage Pairs 1.9.10

Text for the GitHub release `v1.9.10`. Attach only `HeritagePairs_1.9.10.zip` to the release.

---

> This project is an unofficial community modification and is not affiliated with, sponsored by, or endorsed by Shockfront Studios Pty Ltd. Original Nuclear Option assets, vehicle designs, audio, and code are Copyright (c) 2026 Shockfront Studios Pty Ltd. All rights reserved. Nuclear Option and Shockfront Studios are trademarks or registered trademarks of Shockfront Studios Pty Ltd. Original mod content and all other trademarks belong to their respective owners.

**Made with AI.** The models, textures, liveries, flight models and all code in this mod were made with Claude Code (an AI coding
agent), directed and tested by a human. Part of the art was generated with AI image and 3D models on fal.ai. Details are in the
README ("AI assistance") and in CREDITS.md.

## What it is

First public release. Six new flyable aircraft for Nuclear Option, in three pairs, a historical aircraft and its rebuild with
the game's 2080s technology:

- B-25H Mitchell and GA-25X
- Hawker Nimrod Mk I and FD-32 Nimrod
- B-17G Flying Fortress and MSB-17

Each is a new unit beside the stock aircraft, with its own model, cockpit, flight and damage model and liveries for both
factions. Nothing in the game is replaced.

## Requirements

- Nuclear Option 0.34.6 (the version this release was built and tested against)
- BepInEx 5 (5.4.x, Windows x64)
- Blueprinter 2.1.1 by nikkorap (`com.nikkorap.blueprinter`)

## Install

With NOMM (Nuclear Option Mod Manager): find "Heritage Pairs" and install it.

By hand: unpack `HeritagePairs_1.9.10.zip` into
`Nuclear Option\BepInEx\plugins\com.nikkorap.blueprinter\addons\HeritagePairs\`, so that the folder holds
`Heritage Pairs_1.9.10.nobp` and `B25H.Instruments.dll`. To remove the mod, delete that folder.

The download is about 240 MB.

## File

`HeritagePairs_1.9.10.zip`, 249,585,177 bytes

sha256: `1eda2cab98f8ea4d1ec9d58eb0ba6799b3d07bb0f8bd78bdba3fd93094fde8be`

It holds two files: `Heritage Pairs_1.9.10.nobp` (the aircraft pack) and `B25H.Instruments.dll` (the companion plugin; its
source is in this repository under `src/B25H.Instruments`, MIT).

## Known issues

See "Known issues" in the README. In short: multiplayer and mission-editor placement have not been tested; the Nimrod Mk I
tipped onto its nose in the one scripted carrier landing; the B-25H needs back stick to lift off.

## Licence

Code: MIT. Art and pack content made for this mod: CC0 1.0; LICENSE-ASSETS and the README say what that
does not cover (the game and settings copied from its stock parts, real maker names) and how the faction emblems and national
insignia on the liveries are treated (free to use and share on the liveries; the designs remain their owners'). The mod is free and
non-commercial, as the game's EULA requires.
