"""Rebuild everything for the B-25H v2 model.

  python blender/v2/run_v2.py [--ref <reference.obj>] [--skip-renders]

Steps: build (.blend) -> export (main FBX + b25h_v2_propdisc.fbx + parts table) -> FBX re-import check ->
contract (b25h_v2_contract.json/.md) -> mechanics check (b25h_v2_mechanics.json) -> contract stub test -> renders.

Env BLENDER overrides the Blender path. The reference OBJ is only used for the comparison
renders (never copied); composites go to assets/model_v2/compare_*.png, raw reference renders stay
in a temp folder outside the repo.
"""
import os, sys, subprocess, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
V2 = os.path.join(ROOT, 'blender', 'v2')
OUT = os.path.join(ROOT, 'assets', 'model_v2')
BLENDER = os.environ.get('BLENDER', r'C:\Users\User\Mod Tools for Total War Also Blender\tools\blender-5.2.2-stage'
                                    r'\blender-5.2.2-windows-x64\blender.exe')


def run(args):
    print('>>', ' '.join(args[:6]), '...')
    r = subprocess.run([BLENDER, '--background'] + args)
    if r.returncode:
        sys.exit(f'step failed: {args}')


def main():
    os.makedirs(OUT, exist_ok=True)
    blend = os.path.join(OUT, 'b25h_v2.blend')
    fbx = os.path.join(OUT, 'b25h_v2.fbx')
    run(['--factory-startup', '--python', os.path.join(V2, 'build_b25h_v2.py'), '--', '--out', blend])
    run([blend, '--python', os.path.join(V2, 'export_b25h_v2.py'), '--', '--fbx', fbx,
         '--table', os.path.join(OUT, 'b25h_v2_parts')])
    run(['--factory-startup', '--python', os.path.join(V2, 'check_b25h_v2.py'), '--', fbx,
         '--json', os.path.join(OUT, 'b25h_v2_check.json')])
    # v3: build contract, mechanical connectivity check, offline stub test of the contract
    run([blend, '--python', os.path.join(V2, 'contract_b25h_v2.py'), '--', '--out', os.path.join(OUT, 'b25h_v2_contract')])
    run([blend, '--python', os.path.join(V2, 'check_v3_mechanics.py'), '--', '--json', os.path.join(OUT, 'b25h_v2_mechanics.json')])
    # 2026-11-01 cockpit rebuild checks (report only here: the known open items are listed in MODLOG; see b25h_cockpit_check.json)
    subprocess.run([BLENDER, '--background', blend, '--python', os.path.join(V2, 'check_cockpit_b25h.py'), '--', os.path.join(OUT, 'b25h_cockpit_check.json')])
    subprocess.run([sys.executable, os.path.join(V2, 'check_cockpit_art_b25h.py'), os.path.join(OUT, 'b25h_cockpit_check.json')])   # check 7 (PIL)
    r = subprocess.run([sys.executable, os.path.join(V2, 'test_contract_stub.py'), OUT])
    if r.returncode:
        sys.exit('contract stub test failed')
    if '--skip-renders' in sys.argv:
        return
    run(['--factory-startup', '--python', os.path.join(V2, 'render_b25h_v2.py'), '--', blend, os.path.join(OUT, 'renders')])
    if '--ref' in sys.argv:
        ref = sys.argv[sys.argv.index('--ref') + 1]
        tmp = tempfile.mkdtemp(prefix='b25cmp_')
        run(['--factory-startup', '--python', os.path.join(V2, 'compare_ref.py'), '--', ref, blend, tmp,
             '--composite-dir', OUT])


if __name__ == '__main__':
    main()
