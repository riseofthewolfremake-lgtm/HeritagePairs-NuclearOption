"""STUDY ONLY: per-channel statistics of stock Nuclear Option skin / livery textures, to learn the
AircraftSkin channel conventions. Reads the user's private reference files, prints numbers and
writes small channel previews to an OUTSIDE-the-repo folder. Nothing it reads is copied into the repo.

  blender --background --factory-startup --python blender/v2/textures/study_conventions.py -- <out_dir> <png> [<png> ...]
"""
import bpy, sys, os, json
import numpy as np

argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]
os.makedirs(out, exist_ok=True)


def load(p):
    im = bpy.data.images.load(p, check_existing=False)
    im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    bpy.data.images.remove(im)
    return a


def down(a, n=512):
    h, w = a.shape[:2]
    f = max(1, h // n)
    return a[:h // f * f, :w // f * f].reshape(h // f, f, w // f, f, -1).mean(axis=(1, 3))


def save(a, path):
    h, w = a.shape[:2]
    im = bpy.data.images.new('o', w, h, alpha=True)
    im.colorspace_settings.name = 'Non-Color'
    if a.ndim == 2:
        a = np.dstack([a, a, a, np.ones_like(a)])
    im.pixels.foreach_set(a.astype(np.float32).ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def highpass(l):
    # luminance minus a 9x9 box blur (via cumulative sums), for detail correlation
    k = 9
    p = np.pad(l, k, mode='edge')
    c = p.cumsum(0).cumsum(1)
    s = c[k:-k, k:-k] - c[:-2 * k, k:-k] - c[k:-k, :-2 * k] + c[:-2 * k, :-2 * k]
    return l - s / (k * k)


res = {}
cache = {}
for p in argv[1:]:
    a = load(p)
    name = os.path.basename(p)
    cache[name] = a
    st = {'size': list(a.shape[:2])}
    for i, ch in enumerate('RGBA'):
        c = a[..., i]
        st[ch] = dict(mean=round(float(c.mean()), 3), std=round(float(c.std()), 3),
                      p1=round(float(np.percentile(c, 1)), 3), p50=round(float(np.percentile(c, 50)), 3),
                      p99=round(float(np.percentile(c, 99)), 3),
                      frac_lt_0_5=round(float((c < 0.5).mean()), 3), frac_eq_1=round(float((c > 0.996).mean()), 3))
    # inter-channel correlation
    flat = a.reshape(-1, 4)[::97]
    cc = np.corrcoef(flat.T)
    st['corr_RG_RB_GB_RA'] = [round(float(cc[0, 1]), 3), round(float(cc[0, 2]), 3), round(float(cc[1, 2]), 3),
                              round(float(cc[0, 3]), 3) if np.isfinite(cc[0, 3]) else None]
    res[name] = st
    d = down(a)
    base = os.path.splitext(name)[0]
    save(np.dstack([d[..., 0], d[..., 1], d[..., 2], np.ones(d.shape[:2])]), os.path.join(out, base + '_rgb.png'))
    for i, ch in enumerate('RGBA'):
        save(d[..., i], os.path.join(out, base + '_' + ch + '.png'))

# pairwise detail correlation between textures of the same aircraft
names = list(cache)
pairs = {}
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        A, B = cache[names[i]], cache[names[j]]
        if A.shape != B.shape:
            # resample B to A by striding
            f = B.shape[0] / A.shape[0]
            if f >= 1:
                B = B[::int(f), ::int(f)]
            else:
                continue
        la = A[..., :3].mean(-1)
        lb = B[..., :3].mean(-1)
        ha, hb = highpass(la), highpass(lb)
        s = (slice(None, None, 3), slice(None, None, 3))
        r = np.corrcoef(ha[s].ravel(), hb[s].ravel())[0, 1]
        r0 = np.corrcoef(la[s].ravel(), lb[s].ravel())[0, 1]
        pairs[names[i] + ' | ' + names[j]] = dict(lum_corr=round(float(r0), 3), detail_corr=round(float(r), 3))
res['_pairs'] = pairs
with open(os.path.join(out, 'stats.json'), 'w') as f:
    json.dump(res, f, indent=1)
print('STATS', json.dumps(res, indent=1))
