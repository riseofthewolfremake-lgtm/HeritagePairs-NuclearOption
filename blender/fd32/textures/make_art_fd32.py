"""FD-32 prop textures (plain Python: PIL + numpy).

  python blender/fd32/textures/make_art_fd32.py [--out assets/textures_fd32]

- The new fal 3D props (4-blade prop, sensor ball) carry their own baked base colour + normal from their optimised GLB
  (assets/model_fd32/src/fal/opt, the same method as make_cockpit_art_nimrod.prop_textures): fd32_pr_<key>_b / _n.
- The Mk I fal props kept on the FD-32 airframe (main wheels, tail-skid fork / wheel, hook) reuse the Mk I baked textures unchanged
  (same GLBs, same UVs): copied from assets/textures_nimrod as fd32_pr_<key>_b / _n.
"""
import os, sys, json, io, struct, shutil
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
argv = sys.argv[1:]
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_fd32')
os.makedirs(OUT, exist_ok=True)
OPT = os.path.join(ROOT, 'assets', 'model_fd32', 'src', 'fal', 'opt')
NIM_TEX = os.path.join(ROOT, 'assets', 'textures_nimrod')
NEW = {'pr_prop4': 'prop4', 'pr_sensor': 'sensorball', 'pr_hook2': 'hook_modern', 'pr_throttle': 'throttle_v7'}   # round 6: new fal lever (concept throttle_v7_2)
KEEP = ('pr_wheel', 'pr_tailwheel', 'pr_hook')


def glb_textures(path):
    d = open(path, 'rb').read()
    L = struct.unpack('<III', d[:12])[2]
    off, ch = 12, []
    while off < L:
        cl, ct = struct.unpack('<II', d[off:off + 8]); ch.append(d[off + 8:off + 8 + cl]); off += 8 + cl
    js, bn = json.loads(ch[0]), ch[1]
    mat = js['materials'][0]

    def img(ti):
        im = js['images'][js['textures'][ti]['source']]
        bv = js['bufferViews'][im['bufferView']]
        o = bv.get('byteOffset', 0)
        return Image.open(io.BytesIO(bn[o:o + bv['byteLength']])).convert('RGB')
    b = img(mat['pbrMetallicRoughness']['baseColorTexture']['index'])
    nt = mat.get('normalTexture')
    nm = img(nt['index']) if nt else Image.new('RGB', b.size, (128, 128, 255))
    return b, nm


def main():
    for key, glb in NEW.items():
        b, nm = glb_textures(os.path.join(OPT, glb + '.glb'))
        b.resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, f'fd32_{key}_b.png'))
        nm.resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, f'fd32_{key}_n.png'))
    for key in KEEP:
        for sfx in ('_b', '_n'):
            shutil.copyfile(os.path.join(NIM_TEX, f'nimrod_{key}{sfx}.png'), os.path.join(OUT, f'fd32_{key}{sfx}.png'))
    print('[fart] prop textures:', ', '.join(list(NEW) + list(KEEP)))


if __name__ == '__main__':
    main()
