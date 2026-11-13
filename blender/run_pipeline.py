"""Rebuild the B-25H model end to end: build -> export -> check (-> render with --render).

  python blender/run_pipeline.py [--render] [--blender PATH]
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, 'assets', 'model')
DEFAULT_BLENDER = r"C:\Users\User\Mod Tools for Total War Also Blender\tools\blender-5.2.2-stage\blender-5.2.2-windows-x64\blender.exe"


def run(cmd):
    print('>', ' '.join(f'"{c}"' if ' ' in c else c for c in cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if line.startswith('[') or 'Error' in line or 'Traceback' in line or 'PASS' in line or 'FAIL' in line \
                or line.startswith(('objects', 'bbox', 'size', '  -')):
            print('   ', line)
    if r.returncode != 0:
        sys.exit(f'failed: {cmd[0]} (exit {r.returncode})')


def main():
    blender = sys.argv[sys.argv.index('--blender') + 1] if '--blender' in sys.argv else os.environ.get('BLENDER', DEFAULT_BLENDER)
    blend = os.path.join(OUT, 'b25h.blend')
    run([blender, '--background', '--factory-startup', '--python', os.path.join(HERE, 'build_b25h.py'), '--', '--out', blend])
    run([blender, '--background', blend, '--python', os.path.join(HERE, 'export_b25h.py'), '--',
         '--out', os.path.join(OUT, 'b25h_model.json'), '--parts', os.path.join(OUT, 'b25h_parts.md')])
    if '--render' in sys.argv:
        run([blender, '--background', blend, '--python', os.path.join(HERE, 'render_previews.py'), '--', '--outdir', OUT])
    run([sys.executable, '-I', os.path.join(HERE, 'check_b25h_json.py'), os.path.join(OUT, 'b25h_model.json')])


if __name__ == '__main__':
    main()
