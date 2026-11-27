"""A6M2 model pipeline (round 1): build (.blend + contract) -> FBX export (+ parts table) -> placeholder textures -> model checks [-> renders].

  python blender/a6m2/run_a6m2.py [--renders <out dir>]

Rule (memory geometry-change-rebakes-skin): ANY geometry change repacks the livery atlas, so the textures are always rebuilt here.
"""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
BLENDER = r"C:\Users\User\Mod Tools for Total War Also Blender\tools\blender-5.2.2-stage\blender-5.2.2-windows-x64\blender.exe"
MODEL = os.path.join(ROOT, 'assets', 'model_a6m2')
BLEND = os.path.join(MODEL, 'a6m2.blend')
TEX = os.path.join(ROOT, 'assets', 'textures_a6m2')


def run(args):
    print('>>', ' '.join(os.path.basename(a) if os.path.isabs(a) else a for a in args[:6]), '...')
    r = subprocess.run(args, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if any(k in line for k in ('[a6m2]', '[a6tex]', '[a6ck]', '[export]', '[render]', '[check]', 'Error', 'Traceback', 'FAIL', 'PASS')):
            print('   ', line[:300])
    if r.returncode != 0:
        print((r.stdout + r.stderr)[-4000:])
        sys.exit(r.returncode)


def blender(script, blend=None, *extra):
    a = [BLENDER, '--background', blend if blend else '--factory-startup', '--python-exit-code', '1', '--python', os.path.join(HERE, script), '--'] + list(extra)
    run(a)


if __name__ == '__main__':
    blender('build_a6m2.py', None, '--out', BLEND)
    blender('export_a6m2.py', BLEND, '--fbx', os.path.join(MODEL, 'a6m2.fbx'), '--table', os.path.join(MODEL, 'a6m2_parts'))
    run([sys.executable, os.path.join(HERE, 'textures', 'make_cockpit_art_a6m2.py'), '--out', TEX])     # r4c: dial atlas + cockpit tiles (PIL)
    run([sys.executable, os.path.join(HERE, 'textures', 'make_ck_tiles_a6m2.py'), '--out', TEX])
    run([sys.executable, os.path.join(HERE, 'textures', 'make_prop_tips_a6m2.py'), '--out', TEX])   # r7: blade tip stripes
    blender(os.path.join('textures', 'build_textures_a6m2.py'), BLEND, '--out', TEX)          # round 5: the seven liveries (r1: build_textures_a6m2_r1.py)
    blender(os.path.join('textures', 'bake_ck_atlas_a6m2.py'), BLEND, '--out', TEX)          # r8c: the cockpit atlas (AO, grime, wear, frame rivets; the blend is not saved)
    blender('check_a6m2_model.py', BLEND, '--out', os.path.join(MODEL, 'a6m2_check.json'))
    if '--renders' in sys.argv:
        out = sys.argv[sys.argv.index('--renders') + 1]
        blender('render_a6m2.py', BLEND, '--out', out, '--mode', 'views')
        blender('render_a6m2.py', BLEND, '--out', out, '--mode', 'silhouettes')
