# How to release a new version of Heritage Pairs

For the person who publishes (the repository owner). Every step that uploads something is done by hand, by the owner.
`X.Y.Z` stands for the new version, for example `1.9.11`.

## 1. Build

1. Set the version in three places, all to the same number:
   - `unity/Editor/FamilyBuild.cs`: `FamilyVersion = "X.Y.Z"` and the path in `InstrumentsDll` (`build\instruments_X.Y.Z\...`);
   - `src/B25H.Instruments/Plugin.cs`: the third argument of `[BepInPlugin(...)]`;
   - `src/B25H.Instruments/AssemblyInfo.cs`: `AssemblyVersion`, `AssemblyFileVersion` (`X.Y.Z.0`) and
     `AssemblyInformationalVersion` (`X.Y.Z`).
   Do not change the plugin GUID `b25h.instruments`: the players' config file is named after it.
2. Build the plugin: `bash tools/build_instruments.sh <build>\instruments_X.Y.Z`.
3. Build the pack: copy `unity/Editor/*.cs` into the Blueprinter project's `Assets/Editor`, then run Unity in batch mode with
   `-executeMethod B25HTools.FamilyBuild.BuildAll`. All seven aircraft must report `CHECK ALL PASS` (since 1.9.15 the
   A6M2 is one of them). The result is `Heritage Pairs_X.Y.Z.nobp` and an install folder with the pack, the DLL and `meta.json`.
   **Ship gate:** the pack must go to `build\heritage_pairs` (not a `build\heritage_pairs_dev*` folder) and its `FAMILY PACK` line must
   not say `DEV`; if an unreleased aircraft is listed in `FamilyBuild.ShipGated`, the `FAMILY CHECKS ...` line ends with
   `<key> not built (release: ship gate)`. See "Ship gate (unreleased aircraft)" below.
4. Run the tests (README, "Build from source", step 4) and try the build in the game before releasing it.

## 2. Freeze and zip

1. Copy `Heritage Pairs_X.Y.Z.nobp`, `B25H.Instruments.dll` and `meta.json` into a folder that is never changed again
   (`frozen_X.Y.Z`).
2. Make the release zip: `python tools/make_release_zip.py <frozen_X.Y.Z> <release_X.Y.Z> X.Y.Z`.
   It writes `HeritagePairs_X.Y.Z.zip` and prints its sha256. The zip holds exactly two files at its root, the `.nobp` and
   the DLL, with no folder and no `meta.json`: NOMM unpacks the archive as it is into the mod's folder and writes its own
   `meta.json`. Do not add a readme or licence file to the zip.
3. Write the asset inventory: `python tools/pack_asset_report.py <the .nobp> ...` to `docs/publishing/pack_asset_report_X.Y.Z.txt`.

## 3. Repository

1. Update `CHANGELOG.md`, the known issues in `README.md`, and in the README's build section the DLL sha256 and the versions
   it was built with.
2. Update `docs/publishing/HeritagePairs.json` only as your own record (file name, version, download URL, hash). After the
   mod is listed, NOMNOM maintains its own copy of the manifest and adds new versions to it by itself (step 5).
3. Commit and push. Build the release DLL from the commit you tag: NOMNOM requires that the released DLL matches the
   published source.

## 4. GitHub release

1. Create the tag `vX.Y.Z` on that commit and a GitHub release for it. The tag must be `v` followed by plain numbers; do not
   append `-beta` or similar.
2. **Upload ONLY `HeritagePairs_X.Y.Z.zip` as the single release asset.** NOMNOM's updater takes the first asset of a release
   (`Assets[0]`). A second file, such as a `.sha256` file or a screenshot, could be registered as the mod instead.
3. Put into the release description: what changed, the requirements (game version, BepInEx 5, Blueprinter version), the
   sha256 of the zip as text, a pointer to the known issues, the Shockfront notice from the README word for word, and the AI
   declaration. `docs/publishing/RELEASE_NOTES_1.9.10.md` is the pattern.
4. Publish it as a normal release. A release marked "pre-release" is listed by NOMNOM in the category `preRelease`. A draft
   is ignored by NOMNOM until it is published.
5. After publishing, compare GitHub's own digest of the asset (shown on the release page) with the sha256 you wrote down.

Never replace the zip of a release that is already published: NOMNOM has recorded its hash, and NOMM refuses a download whose
hash differs. Publish a new version instead.

## 5. NOMNOM

- **First time only:** fork `KopterBuzz/NOMNOM`, add `docs/publishing/HeritagePairs.json` as `modManifests/HeritagePairs.json`
  and open a pull request. The download URL and the hash in it must already exist, so the GitHub release comes first.
- **Every later version:** nothing to do. NOMNOM's hourly job looks at the repository's releases and adds any release whose
  version is higher than the newest one it knows, taking file name, URL and hash from GitHub. It copies the game version,
  the type and the Blueprinter version from the newest entry it already has.
- A changed game version or Blueprinter version is not picked up automatically. The game version is changed through
  NOMNOM's issue template (`Docs/HOWTO_UPDATE_GAMEVERSION.md` in its repository); the Blueprinter version (`extends`) needs
  a pull request to the manifest.

## 6. Hiding or removing a release

- **Before NOMNOM has seen it** (its job runs once an hour): set the GitHub release back to draft, or delete the release and
  its tag. NOMNOM skips drafts and never learns of it.
- **After NOMNOM has listed it:** NOMNOM only ever adds entries; deleting the GitHub release does not remove the entry, it
  only breaks its download. To withdraw a version, either publish a higher version that fixes the problem (mod managers offer
  the newest), or open a pull request to NOMNOM that removes that entry from `modManifests/HeritagePairs.json`, or ask the
  NOMNOM maintainers to remove it. Then delete the GitHub release.
- **Removing the mod altogether:** ask the NOMNOM maintainers, or open a pull request that deletes
  `modManifests/HeritagePairs.json`; then delete the releases or make the repository private.
- GitHub keeps a deleted release's tag unless you delete the tag too. A deleted tag name can be used again, but do not reuse
  a version number that players may already have installed.

## Ship gate (unreleased aircraft)

An aircraft the user has not yet called done never goes into a release. **The A6M2 Zero (jsonKey `A6M2`) was gated from 2026-11-18 and
was released in 1.9.15** (user approval 2026-11-27, after testing the r8 dev pack). Its modernised twin and any later aircraft are gated
the same way until the user says that aircraft is done. Since 1.9.15 the gate is a list that is empty:

- **`unity/Editor/FamilyBuild.cs`:** `ShipGated` lists each unreleased aircraft as `new GatedAircraft(key, folder, generatorType)`.
  The generator is called by name, so the public tree compiles without its source. `ReleasedKeys` lists the definitions every release
  pack must contain (1.9.15: the seven aircraft and the mod's own weapon definitions); add a released aircraft's keys there.
- **Building a dev pack (development only):** set the environment variable `HP_DEV=1` (the older `HP_DEV_A6M2=1` still works) for the
  Unity run, or call `B25HTools.FamilyBuild.EnableDevPack` once (EditorPrefs `HeritagePairs.DevPack`; `DisableDevPack` switches it off).
  A dev pack builds the gated aircraft too, goes to `build\heritage_pairs_dev` (or `HP_DEV_OUT`), may carry a dev DLL (`HP_DEV_DLL`)
  and says `DEV (NOT FOR RELEASE)` in its `FAMILY PACK` line. Never freeze, zip or upload a pack from a dev folder.
- **Release builds:** no switch is set. `BuildAll` deletes each gated aircraft's folder before packing; `FamilyBuild.Pack` stops with
  `SHIP GATE: ...` when any asset under the family folder belongs to a gated aircraft (its folder, or a definition / mount jsonKey
  starting with its key) and deletes a pack that lists a gated definition or misses a released one.
- **Check on the built file:** `tools/pack_asset_report.py` (step 2.3) prints `SHIP GATE: unreleased-aircraft assets in the pack: N`
  for the folder names in its `SHIP_GATED` list (empty since 1.9.15) and exits 1 when N is not 0 (`--allow-dev` for a dev report).
- **Public tree:** add the aircraft's path patterns to `EXCLUDE` in `tools/make_public_tree.py` while it is gated, and keep its plugin
  hooks out of shared files (or behind partial methods in its own files), so the public source still builds the released DLL. Since
  1.9.15 nothing is excluded for the A6M2: the public tree is the repository's files as they are, and it builds the released DLL.
