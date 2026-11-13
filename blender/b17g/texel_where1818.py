"""1.8.18: where on the airframe did a livery texture change? Texel-level compare of two textures on the SAME livery atlas, mapped to the
parts and world positions of the paint faces (the texture builder's own rasteriser).

  blender --background assets/model_b17g/b17g.blend --python blender/b17g/texel_where1818.py -- <old png> <new png> <out json> [--thr 2]

Changed = any channel differs by more than thr / 255. Counts the changed texels inside the paint islands per part (with the y / x / z
range) and those in the padding outside the islands (fill_outside gutter, only reached by mip bleeding).
"""
import bpy, sys, os, json
import numpy as np

argv = sys.argv[sys.argv.index('--') + 1:]
OLD, NEW, OUT = argv[0], argv[1], argv[2]
THR = float(argv[argv.index('--thr') + 1]) if '--thr' in argv else 2.0
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textures', 'build_textures_b17g.py'), encoding='utf-8').read()
src = src[:src.rindex('main()')]           # the builder's functions only (no texture is written)
sys.argv = [sys.argv[0], '--', '--out', os.path.join(os.path.dirname(os.path.abspath(OUT)), '_texel_where_unused')]
g = {'__name__': 'texel_where1818', '__file__': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textures', 'build_textures_b17g.py')}
exec(compile(src, 'build_textures_b17g', 'exec'), g)
pos, nrm, pid, names, mask = g['rasterise']()


def px(p):
    im = bpy.data.images.load(os.path.abspath(p)); im.colorspace_settings.name = 'Non-Color'
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], im.channels)[..., :3]
    bpy.data.images.remove(im)
    return a           # rows from the bottom = the rasteriser's v


A, B = px(OLD), px(NEW)
ch = np.abs(A - B).max(-1) * 255 > THR
parts = {}
P = pos[ch & mask]; ids = pid[ch & mask]
for k in sorted(set(ids.tolist())):
    Q = P[ids == k]
    parts[names[k]] = dict(texels=int(len(Q)), y=[round(float(Q[:, 1].min()), 3), round(float(Q[:, 1].max()), 3)],
                           x=[round(float(Q[:, 0].min()), 3), round(float(Q[:, 0].max()), 3)], z=[round(float(Q[:, 2].min()), 3), round(float(Q[:, 2].max()), 3)])
res = dict(tool='blender/b17g/texel_where1818.py', old=OLD, new=NEW, thr=THR, changed=int(ch.sum()), in_islands=int((ch & mask).sum()),
           padding=int((ch & ~mask).sum()), parts=parts)
json.dump(res, open(OUT, 'w'), indent=1)
print('[where]', json.dumps(res)[:1500])
