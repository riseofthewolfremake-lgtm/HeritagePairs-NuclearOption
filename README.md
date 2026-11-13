# Heritage Pairs

Six new flyable aircraft for [Nuclear Option](https://store.steampowered.com/app/2168680/Nuclear_Option/), in three pairs: a
historical aircraft and its rebuild with the game's 2080s technology.

> This project is an unofficial community modification and is not affiliated with, sponsored by, or endorsed by Shockfront Studios Pty Ltd. Original Nuclear Option assets, vehicle designs, audio, and code are Copyright (c) 2026 Shockfront Studios Pty Ltd. All rights reserved. Nuclear Option and Shockfront Studios are trademarks or registered trademarks of Shockfront Studios Pty Ltd. Original mod content and all other trademarks belong to their respective owners.

**Made with AI.** The models, textures, liveries, flight models and all code in this mod were made with Claude Code (an AI coding
agent), directed and tested by a human. Part of the art was generated with AI image and 3D models on fal.ai. Details are in
[AI assistance](#ai-assistance) and [CREDITS.md](CREDITS.md).

## The aircraft

| Historical | Rebuilt |
|---|---|
| **B-25H Mitchell** (1944): twin-engine gunship with a 75 mm nose cannon, eight forward .50 guns, bombs and rockets | **GA-25X**: heavy gunship with a guided 76 mm nose gun, a belly laser turret against missiles, tail hook |
| **Hawker Nimrod Mk I** (1932): carrier biplane fighter with two Vickers guns, four 20 lb bombs, arrester hook | **FD-32 Nimrod**: fleet-defence biplane with electric drive, retracting gear, light missiles and guided bombs |
| **B-17G Flying Fortress** (1944): four-engine heavy bomber with thirteen .50 guns in turrets and flexible mounts | **MSB-17**: four-turboshaft heavy strike aircraft with a weapons bay, wing pylons, two 20 mm turrets, two lasers |

Every aircraft is a new unit added beside the stock aircraft; nothing in the game is replaced. Each has its own model, cockpit with
working instruments or screens, damage model, flight model and liveries for both factions. Weapons are the game's own, except
the 75 mm cannon, the Vickers guns, the 20 lb bomb and the twin 20 mm turret, which are defined by this mod from stock parts.

## Requirements

- Nuclear Option 0.34.6. This release was built and tested against game 0.34.6. The manifest inside the pack, which the
  Blueprinter editor project writes, says 0.34.3 (the game version that project was set up with); Blueprinter compares only the
  first two numbers, so it raises no warning on 0.34.6.
- [BepInEx 5](https://github.com/BepInEx/BepInEx) (5.4.x, Windows x64; tested with 5.4.23.5)
- [Blueprinter](https://github.com/nikkorap/NOBlueprinter-Releases) 2.1.1 by nikkorap (`com.nikkorap.blueprinter`)

The download is about 240 MB.

## Install

**With NOMM (Nuclear Option Mod Manager):** find "Heritage Pairs" in the list and install it. NOMM installs Blueprinter with it.
(NOMM's own install of this mod has not been tested yet; the manual install below is the tested one.)

**By hand:**

1. Install BepInEx 5 and Blueprinter 2.1.1.
2. Download `HeritagePairs_<version>.zip` from the
   [Releases page](https://github.com/riseofthewolfremake-lgtm/HeritagePairs-NuclearOption/releases).
3. Unpack it into `Nuclear Option\BepInEx\plugins\com.nikkorap.blueprinter\addons\HeritagePairs\`, so that the folder holds
   `Heritage Pairs_<version>.nobp` and `B25H.Instruments.dll`. Remove the files of an older version from that folder first.
4. Start the game. The aircraft appear in the aircraft selection of airbases, shelters and carriers.

To remove the mod, delete that folder. Settings are in `BepInEx\config\b25h.instruments.cfg`. The plugin shows in the BepInEx
log as "Heritage Pairs Instruments".

## Multiplayer

**Multiplayer has not been tested with this mod.** What follows is the expected behaviour of Blueprinter aircraft mods, not a
test result: every player in a lobby and the host need the same version of the mod, and a player without it is not expected to
be able to join or see a game that uses these aircraft correctly. The mod is not meant to give an advantage over players of the
same lobby: the aircraft and weapons exist for everyone who has the mod.

## Known issues

- **Not tested:** multiplayer; placing these aircraft in the mission editor; NOMM's own install of the zip.
- Carrier landings: the FD-32 catches a wire and stops (tested with a scripted approach). The Nimrod Mk I catches a wire but
  tipped onto its nose in the one scripted test, in which the stick was held back; a hand-flown landing has not been tested.
  The arrester hook is an item of the loadout (Tail Hook slot): an aircraft spawned with an empty loadout has no hook. Parking,
  riding the lift, taxiing and deck take-offs work.
- The B-25H needs back stick to lift off; it does not fly itself off the runway at full throttle.
- Computer-flown tail-wheel aircraft (B-17G, MSB-17, both Nimrods) push the stick forward while taxiing, so the tail can lift
  during AI taxi. Computer-flown Nimrod Mk I aircraft can get stuck circling at the K92 highway strip.
- The MSB-17 has not been tested at its heaviest take-off weight (42 t), with its bays open in flight, or with one engine out
  below 75 m/s.
- The GA-25X belly laser only looks downward: it does not engage missiles that come in level or from above.
- The MSB-17 lasers hold their beam whenever the aircraft's own structure is in the way, so some missiles from directly
  behind the fin are not engaged.
- The small backlit labels in the MSB-17 cockpit are lit bars, not readable text.
- The MSB-17 was called MSB-17/80 in private pre-release builds, with the key `MSB1780`. Missions and saves made with those
  builds are expected not to find the aircraft (the key is `MSB17` now; this was not tried). Place it again.

## AI assistance

This mod is declared AI-assisted.

- **Code:** the plugin, the Unity build scripts, the Blender model scripts and the test scripts were written by Claude Code
  (Anthropic), working from a human's instructions and reviews.
- **Models:** the airframes are built by Python scripts in Blender (procedural geometry). Some detail parts (propellers, wheels,
  turrets, engines, cockpit props) started as AI-generated 3D models and were cleaned up and fitted by script.
- **Textures and liveries:** painted by script; tiling surface textures and cockpit panel art were generated with AI image models.
- **AI models used through fal.ai:** `fal-ai/nano-banana-2`, `fal-ai/nano-banana-2/edit`, `google/nano-banana-2.1`,
  `google/nano-banana-2.1/edit`, `fal-ai/z-image/turbo/tiling`, `tripo3d/h3.1/image-to-3d`, `tripo3d/tripo/remesh`,
  `fal-ai/hunyuan-3d/v3.1/pro/image-to-3d`. Every call is logged in `assets/fal_manifest.jsonl` and the `fal_manifest.jsonl`
  files in the per-aircraft folders.
- A human chose what to build, flew every aircraft in the game and accepted or rejected each version.

## Build from source

You need your own copy of the game; no game file is in this repository.

1. **Plugin:** `bash tools/build_instruments.sh <out_dir>` compiles `src/B25H.Instruments` with the C# compiler that ships with
   Unity 2022.3.62f2, against the game's own `Managed` DLLs and BepInEx 5 on your PC (read-only references). This script is
   the supported build. The `B25H.Instruments.csproj` beside the source is a convenience for IDEs; it has not been built with
   a .NET SDK and is not expected to give the same bytes.
   The build is deterministic: the same source, compiler and reference DLLs give the same DLL bytes. The released
   `B25H.Instruments.dll` 1.9.10 has sha256 `2a7cda29cf2e10e734b100b2227f5b4634905fbabd9f4800bf121e324498bea5` and was built with:
   - Nuclear Option 0.34.6, Steam build id 26327221 (`Assembly-CSharp.dll` sha256 `babdd626bbab...813c2bce`);
   - BepInEx 5.4.23.5 (`BepInEx.dll` sha256 `8255b2890288...ef14ce70`, `0Harmony.dll` sha256 `1a21cc03424f...285c1031`);
   - Unity 2022.3.62f2: its Roslyn `csc.dll` 4.3.1-3.22526.13 (41a5af9d), run by its bundled .NET runtime 6.0.21.

   With another game build, BepInEx version or compiler the DLL works the same but its hash differs.
2. **Models and textures:** the `blender/` scripts build each aircraft in Blender 5.2 (`build_*.py`, `build_textures_*.py`,
   `export_*.py`, `check_*_model.py`). The built models and textures are in `assets/`.
3. **Pack:** set up the Blueprinter editor project (Unity 2022.3.62f2, Blueprinter editor package, your game's assemblies
   imported by Blueprinter's setup window), copy `unity/Editor/*.cs` into its `Assets/Editor`, and run
   `Unity -batchmode -executeMethod B25HTools.FamilyBuild.BuildAll`. It builds the six aircraft, runs their checks and writes the
   `.nobp`.
4. **Tests:** the plugin's offline tests are `src/B25H.Instruments/stub_test.py`, `nimrod_stub_test.py`, `fd32_stub_test.py`,
   `fd32tac_stub_test.py` and `b17g_stub_test.py` (run each with `python`). Rows that compare against earlier private builds
   are skipped when that history is not on your PC.

The build scripts contain the paths of the PC they were written on (`C:\Users\User\...`, and the default Unity and Steam install
folders under `C:\Program Files`); change them to yours. Folders and scripts named `msb1780` belong to the MSB-17 (its former
working name). Some comments mention design notes and study folders that are private and not published.

## Licence

- **Code** (everything under `src/`, `unity/`, `blender/`, `tools/`): MIT, see [LICENSE](LICENSE).
- **Art and pack content we made** (models, textures, liveries, cockpit art, the built `.nobp` content that is ours): CC0 1.0,
  see [LICENSE-ASSETS](LICENSE-ASSETS). You may repackage it, change it, and publish your own versions and updates without asking.
  Files generated by AI models (listed in the `fal_manifest.jsonl` files) are offered as-is: the dedication applies to whatever
  rights the author holds in them, which may be none, and their use also falls under fal.ai's terms and the terms of each
  model's provider.
- **Not ours to license, and not covered by either file:**
  - the game Nuclear Option, its assets and its code (Shockfront Studios Pty Ltd);
  - **component settings copied from the game's stock prefabs.** The pack contains no game mesh, texture, audio clip, shader
    or code, but its build copies the settings of some stock components onto our own objects (see
    [CREDITS.md](CREDITS.md), "The game"): above all the particle effects (muzzle flash and smoke, sparks, wheel dust, sabots,
    ejection smoke, laser muzzle), which are in the pack unchanged. These settings remain Shockfront's;
  - the names of real aircraft, engines, weapons, instruments and their manufacturers, on placards and elsewhere, which are
    used only to describe historical subjects and remain the trademarks of their owners;
  - Blueprinter (nikkorap), BepInEx and Harmony.
- **Emblems on the liveries:** the BDF and PALA faction emblems are Shockfront Studios' designs, redrawn here and used as
  Shockfront allows for custom liveries (the same way Steam Workshop liveries use them). You may use and share these liveries
  freely with the emblems on them; the emblem designs themselves remain Shockfront's, so our CC0 dedication covers our
  paintwork, not ownership of the emblems. In the same way, the national insignia of real air forces on the historical
  liveries (RAF roundel and fin flash, US star-and-bar) remain their owners'; our dedication covers our paintwork.

  The pack refers to the game's own parts (stock weapons, seats, displays, materials, sounds) by name and the game supplies
  them at load; they are not contained in it.

Mods of Nuclear Option are also subject to the game's EULA: they must stay free and non-commercial.

## Credits

See [CREDITS.md](CREDITS.md). Version history: [CHANGELOG.md](CHANGELOG.md).
