# Heritage Pairs 1.9.13

Text for the GitHub release `v1.9.13`. Attach only `HeritagePairs_1.9.13.zip` to the release.

---

> This project is an unofficial community modification and is not affiliated with, sponsored by, or endorsed by Shockfront Studios Pty Ltd. Original Nuclear Option assets, vehicle designs, audio, and code are Copyright (c) 2026 Shockfront Studios Pty Ltd. All rights reserved. Nuclear Option and Shockfront Studios are trademarks or registered trademarks of Shockfront Studios Pty Ltd. Original mod content and all other trademarks belong to their respective owners.

**Made with AI.** The models, textures, liveries, flight models and all code in this mod were made with Claude Code (an AI coding
agent), directed and tested by a human. Part of the art was generated with AI image and 3D models on fal.ai. Details are in the
README ("AI assistance") and in CREDITS.md.

## What changed

- **FD-32 and Nimrod Mk I upper wing.** In hard pulls and rolls at speed the outer panels of the upper wing could kink at
  their joint with the centre section, one side more than the other (reported on Discord for the FD-32). Each wing panel is
  a separate part held to its neighbours by the game's physics joints, and the game solved these joints 6 times per physics
  step, which was not enough to hold the light upper wing against its lift. The wing joints of both biplanes are now solved
  100 times per step, using the game's own setting for this (the stock A-19 uses 12 on its outer wing joints).
- **Dark seam backing.** Where an outer panel meets the centre section, the cut ends of the wing skin and the short spar and
  stringer stubs that cross the joint were light grey, so any small opening during a hard pull showed as a thin light line
  with light specks. Those cut ends and stubs are now drawn in the same dark matte colour as the control-surface gaps, and a
  thin dark band sits hidden just under the skin on both sides of each joint, so that looking into an opening shows dark
  instead of light or sky (offline pictures with the joint opened or stepped 1.2 mm and 5 mm: a dark line, no light specks).
  This changes no texture and no livery; at rest the band is completely covered by the skin. The band is made of two halves:
  the outer half belongs to the outer panel, so if a panel is shot off it goes with that panel and leaves no band edge on the
  centre section. The centre section's own short spar stubs still stick out of the broken end, as in 1.9.12, now dark instead
  of light grey.
- **Measured in the game so far** (FD-32 full pull at about 8-9 g, one aircraft in the mission; the right upper outer panel at
  the joint):
  - 1.9.12 (6 solves per step): 2.21 degrees and a 99 mm step at 8.3 g.
  - 20 solves (first 1.9.13 test build): 0.41 degrees and an 18 mm step; a wide light seam in the chase picture.
  - 60 solves (set during flight on that test build): under about 0.04 degrees (the limit of what our measuring tool can read)
    and a 1.2 mm step; in the green "BDF Temperate Camo" livery a thin light hairline could still show.
  - 100 solves (set during flight on that test build): 0.00 degrees and 0 mm.
  - Nimrod Mk I: 0.5 to 0.7 degrees on 1.9.12, under 0.05 degrees at 20 solves. The 20-solve figure is from a test build; the final download (100) is below.
  - Frame time: with one aircraft in flight, 30, 40, 60 or 100 solves per step cost nothing we could measure against 20
    (measured on the test build). A mission with many FD-32s or Mk Is has not been measured.
  These figures come from test builds with the setting changed during flight, not from this download.
- **Tried in the game on the final download** (this zip's pack, `Heritage Pairs_1.9.13.nobp` sha256 db92912e41ed..., game
  0.34.6, one launch on 16 November, Free Flight at Maris Airport, one aircraft in the mission):
  - The pack loads once with no errors in the whole session. The game reads 100 solves per step on the five wing parts of both
    the FD-32 and the Mk I (6 on every other part).
  - FD-32 parked in BDF Temperate Camo: no line and no band at the joint; hiding the seam band changes nothing along the joint.
  - FD-32 full pull: 8.07 g in BDF Temperate Camo and 8.10 g in BDF Navy Hex at 131-151 m/s. The right upper outer panel moved
    at most 0.0072 and 0.0069 degrees, 0.24 mm at the joint. The chase pictures show a closed seam; neither livery shows a
    light line or light specks there.
  - Nimrod Mk I full pull at 6.5 g (95-115 m/s): every wing joint 0.0019 degrees / 0.2 mm or less; no light line at the joint
    in the chase picture.
  - FD-32 right upper outer panel shot off at 122 m/s: the panel and its aileron come off; the broken end of the centre section
    shows its mid-grey ribbed end face, with no dark strip along the chord.
  - Take-off at full throttle with no input: FD-32 lift-off after 5.3 s / 65 m, Mk I after 6.2 s / 88 m (1.9.12: 5.2 s / 61 m
    and 6.2 s / 89 m).
  - The previous candidate with the same wing joints (100 solves; only the seam backing differs) was tried earlier the same
    day: FD-32 8.1 g pull 0.0072 degrees / 0.27 mm, roll and pull at 5 g 0.003 degrees or less, Mk I 6 g pull 0.0020 degrees
    or less; both aircraft taxi straight out of the shelter; frame time 4.07 ms at 6 solves and 4.06 ms at 100 with one
    aircraft. Its two scripted landings did not reach the runway (the Mk I touched down 1 km beside it and flipped, the
    FD-32 touched down 6 km long and stopped intact on grass): that is our test script's approach, not the aircraft, but it
    means a landing has not been shown on 1.9.13.
- Nothing else changed: masses, centre of gravity, flight models, joint break strengths, weapons, liveries, textures and the
  plugin's behaviour are those of 1.9.12. The B-25H, GA-25X, B-17G and MSB-17 are identical to 1.9.12.

## Requirements

- Nuclear Option 0.34.6 (the version this release was built against)
- BepInEx 5 (5.4.x, Windows x64)
- Blueprinter 2.1.1 by nikkorap (`com.nikkorap.blueprinter`)

## Install

With NOMM (Nuclear Option Mod Manager): update "Heritage Pairs".

By hand: unpack `HeritagePairs_1.9.13.zip` into
`Nuclear Option\BepInEx\plugins\com.nikkorap.blueprinter\addons\HeritagePairs\`, so that the folder holds
`Heritage Pairs_1.9.13.nobp` and `B25H.Instruments.dll`. Remove the 1.9.12 files from that folder first: two packs in the folder
load the mod twice.

The download is about 243 MB.

## File

`HeritagePairs_1.9.13.zip`, 255,292,397 bytes

sha256: `f99437b7b380fd0d361d5c6e4780a12da398ba3e53b990ab5fc5a7982534e8e0`

It holds two files: `Heritage Pairs_1.9.13.nobp` (the aircraft pack) and `B25H.Instruments.dll` (the companion plugin; its
source is in this repository under `src/B25H.Instruments`, MIT).

## Known issues

See "Known issues" in the README. In short: the final 1.9.13 download was tried in the game (see "Tried in the game on the
final download" above); the figures in "Measured in the game so far" come from test builds with the setting changed during
flight (the 60-solve test build: under 0.04 degrees / 1.2 mm, with a thin light hairline in BDF Temperate Camo). Landings,
carrier traps, PALA liveries at the joint, a Mk I panel shot off and a mission with many FD-32s or Mk Is were not tried on any 1.9.13 build; multiplayer and mission-editor placement have
not been tested; the Nimrod Mk I tipped onto its nose in the one scripted carrier landing; the B-25H needs back stick to
lift off; computer-flown aircraft are expected to open and close their air-brake panels while taxiing; holding the throttle
exactly at 5 % makes the brake open and close about once a second. On the FD-32 the texture has little room beside the
cockpit, at the wing, tail and rudder tips and on part of the belly, so there both naval patterns fade to a plain colour
(blue-grey on BDF Navy Hex, mid-grey on PALA Navy Splinter); both naval patterns on both aircraft have one straight seam along
the belly centreline.

## Licence

Code: MIT. Art and pack content made for this mod: CC0 1.0; LICENSE-ASSETS and the README say what that
does not cover (the game and settings copied from its stock parts, real maker names) and how the faction emblems and national
insignia on the liveries are treated (free to use and share on the liveries; the designs remain their owners'). The mod is free and
non-commercial, as the game's EULA requires.
