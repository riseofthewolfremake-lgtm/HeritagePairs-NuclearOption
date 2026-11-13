"""FD-32 model pipeline: build (.blend + contract) -> FBX export (+ parts table) -> textures -> prop textures -> checks [-> renders].

  python blender/fd32/run_fd32.py [--renders]

As the Mk I pipeline (blender/nimrod/run_nimrod.py): any change of paint faces repacks the livery atlas, so the textures are always
rebuilt here. fal props must be processed first (blender/fd32/props/process_props_fd32.py) - they are inputs, not rebuilt here.
"""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
BLENDER = r"C:\Users\User\Mod Tools for Total War Also Blender\tools\blender-5.2.2-stage\blender-5.2.2-windows-x64\blender.exe"
MODEL = os.path.join(ROOT, 'assets', 'model_fd32')
BLEND = os.path.join(MODEL, 'fd32.blend')
TEX = os.path.join(ROOT, 'assets', 'textures_fd32')
REVIEW = r"C:\Users\User\nuclearoption-ref\study\fd32\renders\pipeline"


def run(args):
    print('>>', ' '.join(os.path.basename(a) if os.path.isabs(a) else a for a in args[:6]), '...')
    r = subprocess.run(args, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if any(k in line for k in ('[fd32]', '[ftex]', '[fart]', '[export]', '[render]', '[check]', 'Error', 'Traceback', 'FAIL', 'PASS')):
            print('   ', line[:300])
    if r.returncode != 0:
        print((r.stdout + r.stderr)[-4000:])
        sys.exit(r.returncode)


def blender(script, blend=None, *extra):
    a = [BLENDER, '--background']
    a.append(blend if blend else '--factory-startup')
    a += ['--python-exit-code', '1', '--python', os.path.join(HERE, script), '--'] + list(extra)
    run(a)


if __name__ == '__main__':
    blender('build_fd32.py', None, '--out', BLEND)
    blender('export_fd32.py', BLEND, '--fbx', os.path.join(MODEL, 'fd32.fbx'), '--table', os.path.join(MODEL, 'fd32_parts'))
    blender(os.path.join('textures', 'build_textures_fd32.py'), BLEND, '--out', TEX)
    run([sys.executable, os.path.join(HERE, 'textures', 'make_art_fd32.py'), '--out', TEX])
    blender('check_fd32_model.py', BLEND, '--out', os.path.join(MODEL, 'fd32_check.json'))
    if '--renders' in sys.argv:
        for liv in ('bdf_mattegrey', 'bdf_temperate', 'pala_desert'):
            blender('render_fd32.py', BLEND, '--out', REVIEW, '--tex', TEX, '--livery', liv, '--views', 'front3q,rear3q,side,top,below')
        blender('render_fd32.py', BLEND, '--out', REVIEW, '--tex', TEX, '--views', 'cockpit,nose,canopy')
