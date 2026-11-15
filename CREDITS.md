# Credits

## The game

**Nuclear Option** is made by Shockfront Studios Pty Ltd. This mod needs a legally acquired copy of the game.

No game mesh, texture, audio clip, shader, prefab file, game DLL or decompiled game code is in this repository or in the
released pack. The pack names the game's own parts (stock weapons, mounts, ejection seats, sticks, throttles, displays,
materials, sounds) through Blueprinter placeholders, and the game supplies them when it loads the mod.

**The pack does contain component settings that were copied from the game's stock prefabs.** The build scripts make each of
our aircraft by copying the settings of stock components onto our own objects (`EditorUtility.CopySerialized` in
`unity/Editor/*Build.cs`, from the Blueprinter placeholder copies of the stock prefabs) and then changing what our aircraft
needs. What stays in the released pack from those copies:

- **Particle effects:** 105 of the pack's 107 particle systems are byte-identical to stock ones (`CopyParticle` in the build
  scripts): muzzle flash, muzzle smoke, contact sparks, wheel dust, sabots, ejection smoke, laser muzzle. They are parameter
  blocks of about 7 kB each, about 0.8 MB together; they hold no texture or mesh.
- **Audio-source settings and material parameter blocks:** largely the stock values (among the materials, the glass and
  propeller-disc materials are value copies of stock ones). The sounds and the stock materials themselves are not in the pack.
- **Starting values of other game components** on our aircraft and weapons (weapon and missile components of the guns and
  the 20 lb bomb, control surfaces, rigid bodies, the tail hook): copied from a stock part and then overwritten for the most
  part by our own numbers.

These settings remain Shockfront's. They are not covered by this repository's MIT or CC0 terms.

The asset inventory of the released file is in `docs/publishing/pack_asset_report_<version>.txt`. It lists every object in the
pack by type, name and size and shows that the meshes, textures, sprites and materials are ours; it does not compare component
settings, which is why the paragraph above is stated here.

**Faction emblems.** The BDF and PALA faction emblems on the liveries are Shockfront Studios' designs, redrawn here
(`blender/v2/textures/faction_marks.py`: shapes re-entered as coordinates, no game image copied) and used as Shockfront allows
for custom liveries, the same way Steam Workshop liveries use them. You may use and share these liveries freely with the
emblems on them. The emblem designs themselves remain Shockfront's, so our CC0 dedication covers our paintwork, not ownership
of the emblems.

## Tools this mod depends on

| Tool | Author | Used for | Licence / terms |
|---|---|---|---|
| [Blueprinter](https://github.com/nikkorap/NOBlueprinter-Releases) (`com.nikkorap.blueprinter`) 2.1.1 | nikkorap | Loads the `.nobp` pack into the game; its Unity editor package builds the pack. Required at run time, not included. | MIT |
| [BepInEx](https://github.com/BepInEx/BepInEx) 5 | BepInEx contributors | Plugin loader. Required at run time, not included. | LGPL-2.1 |
| [Harmony](https://github.com/pardeike/Harmony) (ships with BepInEx) | Andreas Pardeike | Method patches in the plugin. Not included. | MIT |
| Unity 2022.3 editor, Blender 5.2 | Unity Technologies, Blender Foundation | Build tools only. The pack carries three compiled shaders of Unity's Universal Render Pipeline (Lit and two fallback shaders), as any Unity asset bundle does; nothing else of them is included. | Their own licences |

## AI tools

- **Claude Code** (Anthropic) wrote the code and the model, texture and build scripts, and ran the builds and tests.
- **fal.ai** hosted the generative models used for part of the art. Each of these endpoints was labelled "Commercial use" on its
  fal.ai model page when checked on 2026-11-13; outputs were generated under fal.ai's terms of service and the terms of each
  model's provider. Every call (endpoint, prompt, output file) is logged in the `fal_manifest.jsonl` files in `assets/`.
  Two generated placard images were edited by hand-written script afterwards to remove logo-like marks
  (`tools/paint_out_marks1910.py`).

| fal endpoint | Provider | Used for |
|---|---|---|
| `fal-ai/nano-banana-2`, `fal-ai/nano-banana-2/edit` | Google | Concept images for detail parts, cockpit panel art |
| `google/nano-banana-2.1`, `google/nano-banana-2.1/edit` | Google | Cockpit panel and texture art (B-25H, GA-25X) |
| `fal-ai/z-image/turbo/tiling` | Tongyi-MAI (Z-Image) | Tiling surface textures (metal, fabric, interior, tyres) |
| `tripo3d/h3.1/image-to-3d` | Tripo | 3D detail parts from concept images (propellers, wheels, engines, turrets, cockpit props) |
| `tripo3d/tripo/remesh` | Tripo | Reducing those parts to game-size meshes |
| `fal-ai/hunyuan-3d/v3.1/pro/image-to-3d` | Tencent Hunyuan | Two trial parts (GA-25X throttle study) |

The MSB-17 uses no new generated art: it reuses the B-17G's tiles and is otherwise procedural.
The 1.9.12 additions: the air-brake panels and the MSB-17 light strips are built by script and use no generated art. The four
naval liveries are painted by script (pattern, colours, markings); the naval colours were taken as numbers from the colour
statistics of the game's own naval liveries, and no pixel of a game texture is in them. Two AI-generated tiling dirt textures
are mixed in faintly as weathering:

| File | fal endpoint | Request, seed | Used for |
|---|---|---|---|
| `assets/textures_fd32/fal_raw/naval_grunge.png` | `fal-ai/z-image/turbo/tiling` | `01a1db35-f949-7d73-82d8-c776d797a4a4`, seed 1665911485 | FD-32 "BDF Navy Hex" and "PALA Navy Splinter": weathering at 5 % strength under the pattern |
| `assets/textures_nimrod/fal_raw/naval_grime_d.png` | `fal-ai/z-image/turbo/tiling` | `01a1dbec-9a40-7001-afe4-41618a651a9c`, seed 191204 | Nimrod Mk I "BDF Navy Gray" and "PALA Navy": grime at 5.5 % strength under the pattern and markings |

The prompts are in `assets/textures_fd32/fal_raw/fal_manifest.jsonl` and `assets/textures_nimrod/fal_raw/fal_manifest_1912.jsonl`.
Eight further trial tiles from the same endpoint were generated and discarded; they are not in the repository or the pack.

## Fonts

The text on the Nimrod Mk I cockpit placards and dial faces is drawn by script with Windows system fonts: Arial, Arial Bold,
Bahnschrift, Courier New, Courier New Bold and Consolas Bold. The GA-25X surface tiles use Pillow's built-in default font. No
font file is in this repository or in the pack, only the rendered text.

## References

- **Photographs and public documentation** of the real aircraft were used as visual reference.
- **War Thunder models (Gaijin Entertainment)** of the B-25J, Nimrod Mk I, B-17G and the .50 calibre AN/M2 gun, obtained by the
  mod's author and kept outside this repository, were used as a private reference for shape and proportion. They were looked
  at, measured and in places traced as 2D outlines: fuselage station widths and heights, nose and nacelle profiles, tail and
  fin planform outline tables, window positions, gun mount positions. **No mesh, UV layout, texture or file from War Thunder
  is in this repository or in the pack**; the reference files were never committed.
  - Files that hold numbers taken from those models: `blender/v2/b25h_spec.py`, `blender/nimrod/nimrod_spec.py`,
    `blender/nimrod/nimrod_v140.py`, `blender/b17g/b17g_spec.py`, `blender/b17g/b17g_nacelle.py`,
    `blender/b17g/b17g_nose1817.py`, `blender/b17g/b17g_detail.py`, `blender/b17g/textures/build_textures_b17g.py` (the
    outline of the anti-glare panel), `blender/anm2/anm2_model.py`, `unity/Editor/ANM2Gun.cs`.
  - Scripts that read such a model to measure it or to render it beside ours: `blender/nimrod/measure_wt.py`,
    `blender/anm2/measure_wt_mounts.py`, `blender/b17g/measure_nacelles.py`, `blender/msb1780/outline_msb1780.py`,
    `blender/v2/compare_ref.py`, and the comparison render scripts `blender/render_r180.py`, `blender/nimrod/render_nimrod.py`,
    `blender/nimrod/render_review.py`, `blender/nimrod/render_v140.py`, `blender/anm2/render_anm2.py`,
    `blender/b17g/render_b17g.py`, `blender/b17g/render_nacelles.py`, `blender/b17g/render_proof188.py`. They are included so
    this can be checked; they need a reference file that is not provided, and their output is not in this repository.

## Names and insignia

B-25 Mitchell, B-17 Flying Fortress, Hawker Nimrod, North American Aviation, Boeing, Wright, Curtiss-Wright, Rolls-Royce,
Vickers, Hamilton Standard, Bendix, Sperry, Pioneer, Kollsman, Weston, Smiths and other names of real aircraft, engines,
weapons, instruments and manufacturers are used only to identify historical subjects, in the documents, in source comments
and as text on cockpit placards and dial faces. Historical serials and unit markings on the liveries are there for period accuracy, and so are the
national insignia of real air forces on the historical liveries and instrument faces (RAF roundel and fin flash, US
star-and-bar, the US Army Air Forces crest). You may use and share the liveries with them; the names and insignia themselves
remain their owners', and this mod is not affiliated with or endorsed by any of them.
