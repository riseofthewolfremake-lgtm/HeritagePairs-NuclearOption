"""Rebuild the GA-25X texture set (run with any Python 3; it drives Blender headless).

  python blender/ga25x/textures/build_textures_ga25x.py [--cache <dir>] [--res 4096] [--skip-bake] [--blend <ga25x.blend>] [--out <dir>]
                                                          [--previews]

Steps (B-25H texture scripts reused unchanged, pointed at the GA-25X model and output folder):
  bake_maps.py (Cycles geometry maps on the GA-25X livery atlas) -> compose_skin.py (n, m, ao, dmg_b, dmg_n) ->
  compose_liveries_ga25x.py (4 liveries + ga25x_skin_b + ga25x_liveries.json) -> rename b25h_skin_* -> ga25x_skin_*.
Tiling detail textures, gauge atlas and prop-blur atlas are shared with the B-25H (assets/textures_v2, read only).
Rule (as the B-25H MODLOG): re-run this after ANY change of paint faces in the GA-25X model (the atlas is repacked).
The bake cache (~0.5 GB EXR at 4096) lives outside the repo (default %TEMP%\\ga25x_tex_cache).
"""
import os, sys, subprocess, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
V2T = os.path.join(ROOT, 'blender', 'v2', 'textures')
BLEND = os.path.join(ROOT, 'assets', 'model_ga25x', 'ga25x.blend')
OUT = os.path.join(ROOT, 'assets', 'textures_ga25x')
BLENDER = os.environ.get('BLENDER', r'C:\Users\User\Mod Tools for Total War Also Blender\tools\blender-5.2.2-stage'
                                    r'\blender-5.2.2-windows-x64\blender.exe')


def run(args):
    print('>>', ' '.join(os.path.basename(a) for a in args[:4]), flush=True)
    r = subprocess.run([BLENDER, '--background', '--python-exit-code', '1'] + args)
    if r.returncode:
        sys.exit(f'step failed: {args}')


def main():
    a = sys.argv
    cache = a[a.index('--cache') + 1] if '--cache' in a else os.path.join(tempfile.gettempdir(), 'ga25x_tex_cache')
    res = a[a.index('--res') + 1] if '--res' in a else '4096'
    global BLEND, OUT
    if '--blend' in a:
        BLEND = os.path.abspath(a[a.index('--blend') + 1])
    if '--out' in a:
        OUT = os.path.abspath(a[a.index('--out') + 1])
    os.makedirs(cache, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    if '--skip-bake' not in a:
        run([BLEND, '--python', os.path.join(V2T, 'bake_maps.py'), '--', cache, '--res', res])
    fs = ['--factory-startup', '--python']
    run(fs + [os.path.join(V2T, 'compose_skin.py'), '--', cache, '--out', OUT])
    for m in ('n', 'm', 'ao', 'dmg_b', 'dmg_n'):
        src, dst = os.path.join(OUT, f'b25h_skin_{m}.png'), os.path.join(OUT, f'ga25x_skin_{m}.png')
        if os.path.exists(src):
            shutil.move(src, dst)
    run(fs + [os.path.join(HERE, 'compose_liveries_ga25x.py'), '--', cache, '--out', OUT])
    # 1.8.16 guard: manifest of the atlas the skin / liveries were painted on (model checks + Unity CHECK ALL compare against it)
    sys.path.insert(0, os.path.join(ROOT, 'blender'))
    import atlas_guard as AG
    AG.manifest_from_cache(cache, OUT, 'ga25x', 'GA25X', 'blender/ga25x/textures/build_textures_ga25x.py')
    # visual pass: own grey interior / cockpit / prop tiles and the modern standby-display gauge atlas
    r = subprocess.run([sys.executable, os.path.join(HERE, 'make_tiles_ga25x.py'), '--out', OUT])
    if r.returncode:
        sys.exit('make_tiles_ga25x failed')
    # 0.3.2: cockpit panel-art atlas (ga25x_ckart_b/_n) from the fal-generated panel art in assets/textures_ga25x/fal_raw_cockpit
    r = subprocess.run([sys.executable, os.path.join(HERE, 'make_cockpit_art_ga25x.py'), '--out', OUT])
    if r.returncode:
        sys.exit('make_cockpit_art_ga25x failed')
    if '--previews' in a:
        run([BLEND, '--python', os.path.join(HERE, 'render_liveries_ga25x.py'), '--', OUT, os.path.join(OUT, 'previews')])
    print('textures in', OUT, sorted(os.listdir(OUT)))


if __name__ == '__main__':
    main()
