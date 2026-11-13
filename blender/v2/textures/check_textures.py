"""Offline checks of the B-25H v2 texture set.

  blender --background --factory-startup --python blender/v2/textures/check_textures.py -- [<tex_dir>] [--json out.json]

Checks sizes, value ranges and the channel conventions measured on the stock A-19/CI-22 skins:
  _n:      OpenGL tangent normal, B ~ 1, R/G mean ~ 0.5, unit length after decode
  _m:      R == G == B (metallic), A = smoothness in a plausible range
  _ao:     grey, mean 0.6-0.95
  _dmg_b:  multiplicative look (most texels white), A mid-grey with low values at damage
  liveries: opaque RGB, paint texels differ between schemes, insignia blue/white present only on usaaf_*
  faction liveries (bdf_* / pala_*): own roundel colours present, the other faction's and the US blue absent,
            median paint colour near the stock scheme of the same name, json entry has name + faction tag
  gauges:  2048^2, the v3 cockpit cells (0-17, needles 62/63) have bright markings, all other cells blank
"""
import bpy, sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_lib as T

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
pos = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] != '--json')]
d = os.path.abspath(pos[0]) if pos else T.OUT
res = {}
fails = []


def check(name, ok, info=''):
    res[name] = dict(ok=bool(ok), info=info)
    print(('PASS ' if ok else 'FAIL ') + name + ('  ' + info if info else ''))
    if not ok:
        fails.append(name)


def L(n):
    p = os.path.join(d, n)
    if not os.path.exists(p):
        check(f'{n} exists', False)
        return None
    return T.load_image(p)


skin = ['b25h_skin_b.png', 'b25h_skin_n.png', 'b25h_skin_m.png', 'b25h_skin_ao.png', 'b25h_skin_dmg_b.png',
        'b25h_skin_dmg_n.png']
livs = ['usaaf_od', 'usaaf_metal', 'od_plain', 'darkgrey_plain']
fac_livs = ['bdf_mattegrey', 'bdf_temperate', 'pala_matteblack', 'pala_desert']
imgs = {}
for n in skin + [f'b25h_livery_{l}.png' for l in livs + fac_livs]:
    a = L(n)
    if a is None:
        continue
    imgs[n] = a
    check(f'{n} 4096x4096', a.shape[:2] == (4096, 4096), str(a.shape[:2]))
    check(f'{n} finite', np.isfinite(a).all())

for n in ('b25h_skin_n.png', 'b25h_skin_dmg_n.png'):
    a = imgs.get(n)
    if a is None:
        continue
    v = a[..., :3] * 2 - 1
    ln = np.linalg.norm(v, axis=-1)
    check(f'{n} unit length', abs(float(np.median(ln)) - 1) < 0.02, f'median |n| {np.median(ln):.3f}')
    check(f'{n} B mostly up', float(a[..., 2].mean()) > 0.95, f'B mean {a[..., 2].mean():.3f}')
    check(f'{n} R,G centred', abs(a[..., 0].mean() - 0.5) < 0.02 and abs(a[..., 1].mean() - 0.5) < 0.02,
          f'R {a[..., 0].mean():.3f} G {a[..., 1].mean():.3f}')
    check(f'{n} has detail', float(a[..., 0].std()) > 0.004, f'R std {a[..., 0].std():.4f}')
a = imgs.get('b25h_skin_m.png')
if a is not None:
    check('m R==G==B', float(np.abs(a[..., 0] - a[..., 1]).max()) < 0.01 and float(np.abs(a[..., 0] - a[..., 2]).max()) < 0.01)
    check('m metallic mostly 0', float((a[..., 0] < 0.1).mean()) > 0.9, f'{(a[..., 0] < 0.1).mean():.3f}')
    check('m smoothness range', 0.15 < float(a[..., 3].mean()) < 0.6, f'A mean {a[..., 3].mean():.3f}')
a = imgs.get('b25h_skin_ao.png')
if a is not None:
    check('ao grey', float(np.abs(a[..., 0] - a[..., 2]).max()) < 0.01)
    check('ao mean', 0.6 < float(a[..., 0].mean()) < 0.97, f'{a[..., 0].mean():.3f}')
a = imgs.get('b25h_skin_dmg_b.png')
if a is not None:
    w = float((a[..., :3].min(-1) > 0.98).mean())
    check('dmg_b mostly white (multiplicative)', w > 0.4, f'white frac {w:.3f}, mean {a[..., :3].mean():.3f}')
    check('dmg_b alpha mid-grey', 0.4 < float(a[..., 3].mean()) < 0.75, f'A mean {a[..., 3].mean():.3f}')
# liveries: insignia colours present / absent
blue = np.array([0.11, 0.155, 0.30], np.float32)
for l in livs:
    a = imgs.get(f'b25h_livery_{l}.png')
    if a is None:
        continue
    db = np.abs(a[::2, ::2, :3] - blue).max(-1) < 0.05
    n_blue = int(db.sum())
    if l.startswith('usaaf'):
        check(f'{l} insignia blue present', n_blue > 2000, f'{n_blue} texels (1/4 sampled)')
    else:
        check(f'{l} no insignia blue', n_blue < 200, f'{n_blue} texels (1/4 sampled)')
    check(f'{l} opaque', float(a[..., 3].min()) > 0.99)
# faction liveries. Roundel colours = faction_marks.py; stock medians (sRGB 0-255, from the stock LiveryData
# textures of the same-named schemes, see docs/stock_ui_study.md): BDF Matte Gray ~(104,100,100),
# PALA Matte Black ~(30-60), desert ~(110-145, 89-121, 74-104); camo greys/greens checked via the swatch list.
import faction_marks as FM
fcol = {'PALA': [FM.PALA_RED], 'BDF': [FM.BDF_BLUE, FM.BDF_GREEN]}
stock_med = {'bdf_mattegrey': ((80, 125), (78, 122), (78, 122)), 'pala_matteblack': ((18, 62), (18, 60), (18, 60)),
             'pala_desert': ((100, 160), (80, 135), (60, 115)), 'bdf_temperate': ((60, 120), (70, 125), (45, 115))}
jpath = os.path.join(d, 'b25h_liveries.json')
meta = json.load(open(jpath)) if os.path.exists(jpath) else {}
for l in fac_livs:
    a = imgs.get(f'b25h_livery_{l}.png')
    if a is None:
        continue
    own = 'BDF' if l.startswith('bdf') else 'PALA'
    oth = 'PALA' if own == 'BDF' else 'BDF'
    sub = a[::2, ::2, :3]
    for c in fcol[own]:
        n = int((np.abs(sub - c).max(-1) < 0.05).sum())
        check(f'{l} {own} roundel colour {np.round(c * 255).astype(int).tolist()} present', n > 1500, f'{n} texels (1/4)')
    for c in fcol[oth] + [blue]:
        n = int((np.abs(sub - c).max(-1) < 0.04).sum())
        check(f'{l} foreign colour {np.round(c * 255).astype(int).tolist()} absent', n < 300, f'{n} texels (1/4)')
    check(f'{l} opaque', float(a[..., 3].min()) > 0.99)
    paint = a[..., :3][a[..., :3].sum(-1) > 0.02]
    med = np.median(paint[::7], 0) * 255
    rng = stock_med[l]
    check(f'{l} median near stock', all(lo <= m <= hi for m, (lo, hi) in zip(med, rng)), f'median {np.round(med).tolist()}')
    e = meta.get(l, {})
    check(f'{l} json entry', e.get('faction') == own and bool(e.get('name')) and len(e.get('colors', [])) == 5 and
          0 <= e.get('glossiness', -1) <= 1 and e.get('texture') == f'b25h_livery_{l}.png', str({k: e.get(k) for k in ('name', 'faction', 'glossiness')}))
if meta:
    names = [v.get('name') for v in meta.values() if v.get('name')]
    check('json livery names unique', len(names) == len(set(names)), str(names))
    check('json 8 liveries', all(k in meta for k in livs + fac_livs), str(list(meta)))
if 'b25h_skin_b.png' in imgs and 'b25h_livery_od_plain.png' in imgs:
    check('skin_b == od_plain', float(np.abs(imgs['b25h_skin_b.png'] - imgs['b25h_livery_od_plain.png']).max()) < 1 / 255)
g = L('b25h_gauges.png')
if g is not None:
    check('gauges 2048', g.shape[:2] == (2048, 2048))
    lit = []
    for k in range(64):
        r, c = k // 8, k % 8
        cell = g[r * 256:(r + 1) * 256, c * 256:(c + 1) * 256, :3]
        lit.append(float((cell.mean(-1) > 0.7).mean()))
    used = list(range(27)) + [62, 63]   # 1.8.4: + 18-26 (b25h_dials184)                 # make_gauges.GAUGES_V3 (model contract "Gauges")
    check('gauge cells 0-17, 62, 63 have markings', min(lit[k] for k in used) > 0.003, f'min lit {min(lit[k] for k in used):.4f} (attitude card = lines only)')
    free = [k for k in range(64) if k not in used]
    check('other gauge cells blank', max(lit[k] for k in free) < 0.001, f'max lit {max(lit[k] for k in free):.4f}')
for n in ('interior', 'structure', 'metal_dark', 'rubber', 'prop', 'cockpit'):
    a = L(f'b25h_{n}_b.png')
    if a is None:
        continue
    check(f'{n} 1024', a.shape[:2] == (1024, 1024))
    # seamless: compare opposite edges against interior neighbour differences
    e = float(np.abs(a[0, :, :3] - a[-1, :, :3]).mean() + np.abs(a[:, 0, :3] - a[:, -1, :3]).mean()) / 2
    i = float(np.abs(a[1, :, :3] - a[2, :, :3]).mean() + np.abs(a[:, 1, :3] - a[:, 2, :3]).mean()) / 2
    check(f'{n} tiles seamlessly', e < 3 * i + 0.01, f'edge diff {e:.4f} vs inner {i:.4f}')
pb = L('b25h_propblur.png')
if pb is not None:
    check('propblur 512x1024', pb.shape[:2] == (1024, 512), str(pb.shape))
    al = pb[..., 3]                                    # Blender rows: row 0 = v 0 (bottom = full disc)
    check('propblur corners / hub transparent', float(al[:8, :8].max()) == 0 and float(al[256, 256]) == 0 and float(al[768, 256]) == 0)
    ring = [float(al[768 + int(150 * math.sin(math.radians(a))), 256 + int(150 * math.cos(math.radians(a)))]) for a in range(0, 360, 2)]
    peaks = sum(1 for i in range(len(ring)) if ring[i] > 0.6 and ring[i] >= ring[i - 1] and ring[i] > ring[(i + 1) % len(ring)])
    check('propblur top half: 3 blurred blades', peaks == 3, f'{peaks} peaks')
    disc = float(al[256 + 120, 256])
    check('propblur bottom half: translucent disc', 0.1 < disc < 0.6, f'alpha {disc:.2f}')
print('SUMMARY', len(res) - len(fails), 'pass', len(fails), 'fail', fails)
if '--json' in argv:
    with open(argv[argv.index('--json') + 1], 'w') as f:
        json.dump(dict(results=res, fails=fails), f, indent=1)
