"""Rebuild the whole B-25H v2 texture set (run with any Python 3; it drives Blender headless).

  python blender/v2/textures/build_textures.py [--cache <dir>] [--res 4096] [--skip-bake] [--skip-previews]

Steps: bake_maps (Cycles, geometry maps on the livery atlas) -> compose_skin (n, m, ao, dmg) ->
compose_liveries (8 liveries: 4 US-style + 4 BDF/PALA faction, + skin_b + b25h_liveries.json) -> b25h_atlas_manifest.json (1.8.16) -> make_gauges -> make_tiling -> make_propblur ->
render_previews -> ui/make_ui_art (map icon, status display). The bake cache (~0.5 GB of EXR at 4096) lives outside the repo (default %TEMP%).
fal tiles are read from assets/textures_v2/fal_raw (generated once, logged in assets/fal_manifest.jsonl);
without them the build falls back to procedural noise for the triplanar overlays.
"""
import os, sys, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
BLEND = os.path.join(ROOT, 'assets', 'model_v2', 'b25h_v2.blend')
BLENDER = os.environ.get('BLENDER', r'C:\Users\User\Mod Tools for Total War Also Blender\tools\blender-5.2.2-stage'
                                    r'\blender-5.2.2-windows-x64\blender.exe')


def run(args):
    print('>>', ' '.join(os.path.basename(a) for a in args[:4]), flush=True)
    r = subprocess.run([BLENDER, '--background'] + args)
    if r.returncode:
        sys.exit(f'step failed: {args}')


def main():
    a = sys.argv
    cache = a[a.index('--cache') + 1] if '--cache' in a else os.path.join(tempfile.gettempdir(), 'b25h_tex_cache')
    res = a[a.index('--res') + 1] if '--res' in a else '4096'
    os.makedirs(cache, exist_ok=True)
    if '--skip-bake' not in a:
        run([BLEND, '--python', os.path.join(HERE, 'bake_maps.py'), '--', cache, '--res', res])
    fs = ['--factory-startup', '--python']
    run(fs + [os.path.join(HERE, 'compose_skin.py'), '--', cache])
    run(fs + [os.path.join(HERE, 'compose_liveries.py'), '--', cache])
    # 1.8.16 guard: manifest of the atlas the skin / liveries were painted on (model checks + Unity CHECK ALL compare against it)
    sys.path.insert(0, os.path.join(ROOT, 'blender'))
    import atlas_guard as AG
    AG.manifest_from_cache(cache, os.path.join(ROOT, 'assets', 'textures_v2'), 'b25h', 'B25H', 'blender/v2/textures/build_textures.py')
    run(fs + [os.path.join(HERE, 'make_gauges.py')])
    run(fs + [os.path.join(HERE, 'make_tiling.py')])
    run(fs + [os.path.join(HERE, 'make_propblur.py')])
    # 2026-11-01 cockpit rebuild: fal cockpit art atlas, quilt / olive-drab tiles, fal prop textures
    r = subprocess.run([sys.executable, os.path.join(HERE, 'make_cockpit_art_b25h.py')])
    if r.returncode:
        sys.exit('make_cockpit_art_b25h failed')
    if '--skip-previews' not in a:
        run([BLEND, '--python', os.path.join(HERE, 'render_previews.py')])
    # UI art (map icon + damage status display) from the same model; check with blender/v2/ui/check_ui_art.py
    run([BLEND, '--python', os.path.join(HERE, '..', 'ui', 'make_ui_art.py')])


if __name__ == '__main__':
    main()
