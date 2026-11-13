"""Seamless 1024^2 tiling textures for the non-livery materials (sampled on the `detail` UV map:
box-projected, 1 UV unit = 2 m, so one tile spans 2 m).

  blender --background --factory-startup --python blender/v2/textures/make_tiling.py -- [--out <dir>]

b25h_interior_b.png    interior green (zinc chromate tinted) with grime   (from fal zinc_chromate tile)
b25h_structure_b.png   bare aluminium structure                          (from fal bare_aluminium tile)
b25h_metal_dark_b.png  dark painted steel / gunmetal                      (from fal dark_metal tile)
b25h_rubber_b.png / _n.png  tyre rubber with a diamond tread             (procedural)
b25h_prop_b.png        flat black propeller paint with light wear         (procedural)
b25h_cockpit_b.png     dull black-green cockpit crinkle finish            (procedural)
All operations are point-wise or periodic so the fal tiles stay seamless.
"""
import bpy, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_lib as T

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else T.OUT
F32 = np.float32
S = 1024


def fal_tile(name):
    a = T.load_image(os.path.join(T.FAL, name + '.png'))[..., :3]
    h = a.shape[0]
    if h != S:
        f = h / S
        idx = (np.arange(S) * f).astype(int)
        a = a[idx][:, idx]
    return a.astype(F32)


def pnoise(period, seed, octaves=4):
    """periodic value noise on the S x S tile (period = lattice cells across the tile)."""
    acc = np.zeros((S, S), F32)
    amp, tot = 1.0, 0.0
    rng = np.random.default_rng(seed)
    p = period
    for o in range(octaves):
        lat = rng.random((p, p)).astype(F32)
        x = np.arange(S) / S * p
        i0 = np.floor(x).astype(int)
        f = (x - i0).astype(F32)
        f = f * f * (3 - 2 * f)
        i1 = (i0 + 1) % p
        a = lat[i0][:, i0] * (1 - f)[None, :] + lat[i0][:, i1] * f[None, :]
        b = lat[i1][:, i0] * (1 - f)[None, :] + lat[i1][:, i1] * f[None, :]
        acc += amp * (a * (1 - f)[:, None] + b * f[:, None])
        tot += amp
        amp *= 0.5
        p *= 2
    return acc / tot


def lum(a):
    return a @ np.array([0.2126, 0.7152, 0.0722], F32)


def recolour(a, target, contrast=1.0):
    l = lum(a)
    d = (l / max(l.mean(), 1e-3) - 1) * contrast + 1
    return np.clip(target[None, None, :] * d[..., None], 0, 1)


def save(name, img):
    T.save_png(np.clip(img, 0, 1), os.path.join(out, name))


# interior green
zc = fal_tile('zinc_chromate')
g = recolour(zc, np.array([0.33, 0.37, 0.20], F32), 1.4)
g *= (0.86 + 0.18 * pnoise(4, 11))[..., None]
save('b25h_interior_b.png', g)
# structure: bare aluminium
al = fal_tile('bare_aluminium')
l = lum(al)
s = np.clip(0.62 + (l[..., None] - l.mean()) * 0.8 + 0 * al, 0, 1) * np.array([0.98, 0.99, 1.0], F32)
save('b25h_structure_b.png', s)
# metal dark
dm = fal_tile('dark_metal')
save('b25h_metal_dark_b.png', recolour(dm, np.array([0.085, 0.087, 0.092], F32), 1.2))
# rubber: diamond tread, 4 cm pitch (tile = 2 m -> 50 pitches)
v, u = (np.mgrid[0:S, 0:S].astype(F32) + 0.5) / S
n = 50
d1 = np.abs(((u + v) * n) % 1.0 - 0.5)
d2 = np.abs(((u - v) * n) % 1.0 - 0.5)
gro = np.maximum(T.smoothstep(0.42, 0.47, d1), T.smoothstep(0.42, 0.47, d2))
H = -gro * 0.002 + (pnoise(32, 21) - 0.5) * 0.0003
rub = np.full((S, S, 3), 0.045, F32) * (1 - 0.45 * gro)[..., None] * (0.9 + 0.2 * pnoise(8, 22))[..., None]
save('b25h_rubber_b.png', rub)
nrm = T.normal_from_height(H, 2.0 / S, 1.0)
save('b25h_rubber_n.png', T.encode_normal(nrm))
# prop: flat black with light wear
pr = np.full((S, S, 3), 0.035, F32) * (0.85 + 0.35 * pnoise(16, 31))[..., None]
save('b25h_prop_b.png', pr)
# cockpit crinkle finish
ck = np.array([0.075, 0.085, 0.065], F32)[None, None, :] * (0.8 + 0.4 * pnoise(128, 41, 2))[..., None]
save('b25h_cockpit_b.png', ck)
