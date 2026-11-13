"""Run every offline check of the texture + UI art set (any Python 3 with numpy + Pillow; drives Blender for the
texture checks).

  python blender/v2/textures/check_all.py
"""
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_textures import BLENDER

rc = 0
r = subprocess.run([BLENDER, '--background', '--factory-startup', '--python', os.path.join(HERE, 'check_textures.py')],
                   capture_output=True, text=True)
lines = [l for l in r.stdout.splitlines() if l.startswith(('FAIL', 'SUMMARY'))]
print('\n'.join(['[textures] ' + l for l in lines]) or r.stdout[-2000:])
rc |= int(not any(l.startswith('SUMMARY') and ' 0 fail' in l for l in lines))
r = subprocess.run([sys.executable, os.path.join(HERE, '..', 'ui', 'check_ui_art.py')], capture_output=True, text=True)
print('\n'.join('[ui] ' + l for l in r.stdout.splitlines() if l.startswith(('FAIL', 'SUMMARY'))))
rc |= r.returncode
print('ALL PASS' if rc == 0 else 'SOME CHECKS FAILED')
sys.exit(rc)
