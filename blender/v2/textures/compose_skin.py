"""Compose the per-aircraft skin maps of the B-25H v2 from the bake cache.

  blender --background --factory-startup --python blender/v2/textures/compose_skin.py -- <cache_dir> [--out <dir>]

Writes (4096^2 PNG, conventions measured from the stock A-19 / CI-22 textures, see README in this folder):
  b25h_skin_n.png      tangent-space normal, OpenGL (+Y = +v), panel lines / rivets / fasteners / fabric ribs
  b25h_skin_m.png      RGB = metallic (0 painted, bare metal where paint is chipped), A = smoothness
  b25h_skin_ao.png     baked AO (flight pose) x seam cavities, grey in RGB
  b25h_skin_dmg_b.png  RGB = multiplicative soot / burn / holes (white = unchanged), A = damage-order mask
  b25h_skin_dmg_n.png  normal: skin detail + dents, bullet and shell holes, torn skin
and caches the surface features (features.npz) for compose_liveries.py.
"""
import bpy, sys, os, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_lib as T
import features as FT

argv = sys.argv[sys.argv.index('--') + 1:]
cache = os.path.abspath(argv[0])
out = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else T.OUT
os.makedirs(out, exist_ok=True)
F32 = np.float32
t0 = time.time()


def log(*a):
    print(f'[{time.time() - t0:6.1f}s]', *a, flush=True)


G = T.Geo(cache)
log('geo', G.res, 'texels', G.K)
F = FT.compute(G, log)
np.savez(os.path.join(cache, 'features.npz'), **{k: v.astype(np.float16) if k not in ('H',) else v
                                                 for k, v in F.items()})
log('features cached')
R = G.res
maskM, maskX = G.maskM, G.maskX
ts = G.ts

# ------------------------------------------------------------------ normal
Hf = G.full(F['H'])
n = T.normal_from_height(Hf, ts, strength=3.0)   # x3: stock normals carry far more relief than true rivet heights
n[~maskX] = (0, 0, 1)
T.save_png(T.encode_normal(n), os.path.join(out, 'b25h_skin_n.png'))
del n

# ------------------------------------------------------------------ metallic / smoothness
chip, fab, walk, exh, grime, seam = F['chip'], F['fabric'], F['walk'], F['exhaust'], F['grime'], F['seam']
metal = 0.85 * chip
smooth = 0.34 - 0.07 * fab - 0.18 * walk - 0.16 * exh - 0.09 * grime - 0.08 * seam + 0.04 * (F['panel'] - 0.5)
smooth = np.where(chip > 0.5, 0.58, smooth)
HG = T.hinge_gap(G)                             # seam fix: control-surface noses in the hinge gap = matte, dark
smooth = smooth * (1 - HG) + 0.04 * HG
mimg = np.dstack([G.full(metal)] * 3)
aimg = G.full(np.clip(smooth, 0.02, 0.95), fill=0.3)
mimg = T.fill_outside(mimg, maskX, 8)
T.save_png(mimg, os.path.join(out, 'b25h_skin_m.png'), alpha=aimg)
del mimg, aimg

# ------------------------------------------------------------------ AO
ao = G.ao_full.copy()
ao = T.blur(np.where(maskX, ao, 1.0), 1)
ao = np.clip(ao, 0, 1) ** 0.85
ao *= 1 - 0.30 * G.full(seam) - 0.10 * G.full(F['rivet'])
ao *= 1 - 0.85 * G.full(HG)
ao = np.where(maskX, ao, 1.0)
T.save_png(ao, os.path.join(out, 'b25h_skin_ao.png'))
del ao

# ------------------------------------------------------------------ damage
rng = np.random.default_rng(1944)
P, N = G.P, G.N
f_sc = T.fbm(P, 0.7, 4, seed=71)
f_ed = T.fbm(P, 6.0, 3, seed=72)
fs = f_sc + 0.08 * (f_ed - 0.5)
burn = T.smoothstep(0.56, 0.74, fs)            # soot core
heat = T.smoothstep(0.48, 0.58, fs) * (1 - burn)  # heat-tinted rim
soot = np.array([0.09, 0.085, 0.08], F32)
tint = np.array([0.78, 0.66, 0.52], F32)
rgb = np.ones((G.K, 3), F32)
rgb = rgb * (1 - heat[:, None] * 0.6) + tint * heat[:, None] * 0.6
rgb = rgb * (1 - burn[:, None] * 0.92) + soot * burn[:, None] * 0.92
# light soot speckle across damaged-prone areas
speck = T.smoothstep(0.72, 0.8, T.fbm(P, 22.0, 2, seed=73)) * T.smoothstep(0.42, 0.6, fs)
rgb *= (1 - 0.6 * speck)[:, None]
alpha = 0.62 - 0.30 * burn - 0.12 * heat + 0.04 * (f_ed - 0.5)
Hd = F['H'] + (T.fbm(P, 2.2, 3, seed=74) - 0.5) * 0.006 * (0.3 + burn + heat) \
    + (T.fbm(P, 9.0, 2, seed=75) - 0.5) * 0.0012 * burn

rgb_img = G.full(rgb, fill=1.0)
a_img = G.full(alpha, fill=0.62)
h_img = G.full(Hd)
del rgb, alpha, Hd, f_sc, f_ed, fs


SC = R / 4096.0      # stamp radii below are in 4096-texel units


def stamp(cx, cy, rad, kind):
    """stamp a hole / tear into rgb_img, a_img, h_img (image space; radius in texels)."""
    rad = rad * SC
    r_out = int(rad * (3.2 if kind != 'tear' else 2.0)) + 3
    y0, y1, x0, x1 = cy - r_out, cy + r_out + 1, cx - r_out, cx + r_out + 1
    if y0 < 0 or x0 < 0 or y1 > R or x1 > R:
        return False
    if maskM[y0:y1, x0:x1].mean() < 0.97:
        return False
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dx, dy = (xx - cx).astype(F32), (yy - cy).astype(F32)
    d = np.sqrt(dx * dx + dy * dy)
    ang = np.arctan2(dy, dx)
    if kind == 'bullet':
        rr = rad
        hole = 1 - T.smoothstep(rr - 0.6, rr + 0.6, d)
        ring = np.exp(-((d - rr * 1.5) / (rr * 1.1)) ** 2) * (1 - hole)
        dh = -0.0025 * hole + 0.0007 * np.exp(-((d - rr * 1.2) / (rr * 0.5)) ** 2) - 0.0006 * np.exp(-(d / (rr * 2.5)) ** 2)
        dark, ringdark = 0.97, 0.45
    else:
        k = 5 + rng.integers(0, 5)
        ph = rng.uniform(0, 6.28)
        jag = 1 + 0.28 * np.sin(k * ang + ph) + 0.15 * np.sin((2 * k + 1) * ang + 2 * ph)
        rr = rad * jag
        hole = 1 - T.smoothstep(rr - 0.8, rr + 0.8, d)
        ring = np.exp(-((d - rr * 1.4) / (rad * 1.0)) ** 2) * (1 - hole)
        petal = np.clip(np.cos(k * ang + ph), 0, 1) ** 2 * np.exp(-((d - rr * 1.15) / (rad * 0.35)) ** 2)
        dh = -0.006 * hole + 0.0025 * petal * (1 - hole) - 0.0012 * np.exp(-(d / (rad * 2.4)) ** 2)
        dark, ringdark = 0.98, 0.6
    sl = (slice(y0, y1), slice(x0, x1))
    rgb_img[sl] *= (1 - hole[..., None] * dark) * (1 - ring[..., None] * ringdark)
    a_img[sl] = np.minimum(a_img[sl], 0.62 - 0.47 * hole - 0.2 * ring)
    h_img[sl] += dh.astype(F32)
    return True


ys, xs = np.nonzero(maskM)
counts = dict(bullet=0, shell=0, tear=0)
# bullet bursts: clusters of .50 / 20 mm strikes
for b in range(140):
    j = rng.integers(0, len(ys))
    cy, cx = ys[j], xs[j]
    for k in range(rng.integers(3, 11)):
        oy, ox = rng.normal(0, 35 * SC, 2)
        if stamp(int(cx + ox), int(cy + oy), rng.uniform(1.4, 2.6), 'bullet'):
            counts['bullet'] += 1
for b in range(70):
    j = rng.integers(0, len(ys))
    if stamp(xs[j], ys[j], rng.uniform(5, 13), 'shell'):
        counts['shell'] += 1
for b in range(14):
    j = rng.integers(0, len(ys))
    if stamp(xs[j], ys[j], rng.uniform(22, 45), 'tear'):
        counts['tear'] += 1
log('damage stamps', counts)
rgb_img[~maskX] = 1.0
a_img[~maskX] = 0.62
T.save_png(np.clip(rgb_img, 0, 1), os.path.join(out, 'b25h_skin_dmg_b.png'), alpha=np.clip(a_img, 0, 1))
nd = T.normal_from_height(h_img, ts, 3.0)
nd[~maskX] = (0, 0, 1)
T.save_png(T.encode_normal(nd), os.path.join(out, 'b25h_skin_dmg_n.png'))
log('done')
