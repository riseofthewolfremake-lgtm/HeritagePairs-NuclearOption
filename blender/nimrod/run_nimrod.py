"""Nimrod model pipeline: build (.blend + contract) -> FBX export (+ parts table) -> textures -> checks [-> renders].

  python blender/nimrod/run_nimrod.py [--renders] [--ref <WT nimrod_mk1.obj>]

Rule (as the B-25H): ANY change of paint faces repacks the livery atlas, so the textures are always rebuilt here.
"""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
BLENDER = r"C:\Users\User\Mod Tools for Total War Also Blender\tools\blender-5.2.2-stage\blender-5.2.2-windows-x64\blender.exe"
MODEL = os.path.join(ROOT, 'assets', 'model_nimrod')
BLEND = os.path.join(MODEL, 'nimrod.blend')
TEX = os.path.join(ROOT, 'assets', 'textures_nimrod')
MEDIA = os.path.join(ROOT, 'media', 'nimrod_v2')


def run(args):
    print('>>', ' '.join(os.path.basename(a) if os.path.isabs(a) else a for a in args[:6]), '...')
    r = subprocess.run(args, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if any(k in line for k in ('[nimrod]', '[ntex]', '[ckart]', '[export]', '[render]', '[check]', 'Error', 'Traceback', 'FAIL', 'PASS')):
            print('   ', line[:300])
    if r.returncode != 0:
        print((r.stdout + r.stderr)[-4000:])
        sys.exit(r.returncode)


def blender(script, blend=None, *extra):
    a = [BLENDER, '--background']
    if blend:
        a.append(blend)
    else:
        a.append('--factory-startup')
    a += ['--python-exit-code', '1', '--python', os.path.join(HERE, script), '--'] + list(extra)
    run(a)


if __name__ == '__main__':
    blender('build_nimrod.py', None, '--out', BLEND)
    blender('export_nimrod.py', BLEND, '--fbx', os.path.join(MODEL, 'nimrod.fbx'), '--table', os.path.join(MODEL, 'nimrod_parts'))
    blender(os.path.join('textures', 'build_textures_nimrod.py'), BLEND, '--out', TEX)
    run([sys.executable, os.path.join(HERE, 'textures', 'make_cockpit_art_nimrod.py'), '--out', TEX])     # cockpit v2 art (PIL)
    blender('check_nimrod_model.py', BLEND, '--out', os.path.join(MODEL, 'nimrod_check.json'))
    if '--renders' in sys.argv:
        ref = sys.argv[sys.argv.index('--ref') + 1] if '--ref' in sys.argv else None
        if ref:
            blender('render_nimrod.py', BLEND, '--mode', 'silhouettes', '--out', MEDIA, '--ref', ref)
            run([sys.executable, os.path.join(HERE, 'compose_overlays.py'), MEDIA])
        blender('render_nimrod.py', BLEND, '--mode', 'exterior', '--tex', TEX, '--out', MEDIA)
        blender('render_nimrod.py', BLEND, '--mode', 'cockpit', '--tex', TEX, '--out', MEDIA)
