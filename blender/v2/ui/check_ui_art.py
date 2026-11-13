"""Offline check of the B-25H UI art (plain Python 3 + numpy + Pillow; no game, no Blender).

  python blender/v2/ui/check_ui_art.py [assets/ui] [--parts unity/Editor/B25HBuild.cs]

Re-composites the status display the way Unity would lay it out from b25h_status_layout.json (RectTransform centre
anchor, sizeDelta x localScale, negative X scale = mirrored sprite) and checks it against the background line art,
plus format checks against the stock conventions (docs/stock_ui_study.md):
  * map icon 256x256 RGBA, white RGB, transparent background, span within 1-4 px of the edges, nose up
  * background 1024x1024, part sprites 128/64 px, grey fill <= 219 on black
  * every UnitPart of the build script has exactly one Image (or is listed as hidden), names unique
  * every part image lands inside the drawn outline (>= 97 % of its lit pixels on the aircraft) and the part
    images tile the aircraft without large overlaps (sum of coverage / union <= 1.08)
"""
import sys, os, json, re
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
args = [a for a in sys.argv[1:]]
parts_src = args[args.index('--parts') + 1] if '--parts' in args else os.path.join(ROOT, 'unity', 'Editor', 'B25HBuild.cs')
pos = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] != '--parts')]
D = os.path.abspath(pos[0]) if pos else os.path.join(ROOT, 'assets', 'ui')
fails, n = [], 0


def check(name, ok, info=''):
    global n
    n += 1
    print(('PASS ' if ok else 'FAIL ') + name + ('  ' + str(info) if info != '' else ''))
    if not ok:
        fails.append(name)


def load(p):
    return np.asarray(Image.open(os.path.join(D, p)).convert('RGBA')).astype(np.float32) / 255


# ---------------------------------------------------------------- map icon
ic = load('b25h_map_icon.png')
check('icon 256x256', ic.shape[:2] == (256, 256), ic.shape)
a = ic[..., 3]
ys, xs = np.nonzero(a > 0.1)
check('icon white', float(ic[..., :3][a > 0.1].min()) > 0.99)
check('icon transparent corners', float(a[:8, :8].max()) == 0 and float(a[-8:, -8:].max()) == 0)
check('icon span fills width (1-4 px margin)', 1 <= xs.min() <= 4 and 251 <= xs.max() <= 254, (xs.min(), xs.max()))
check('icon left/right symmetric', abs((xs.min() + xs.max()) / 2 - 127.5) < 1.5, (xs.min(), xs.max()))
rows = (a > 0.5).sum(1)
nose = ys.min()
check('icon nose up (narrow top, wide wing row in upper half)', rows[nose:nose + 5].max() < 40 and int(np.argmax(rows)) < 128,
      (nose, int(np.argmax(rows))))

# ---------------------------------------------------------------- status layout
L = json.load(open(os.path.join(D, 'b25h_status_layout.json')))
bg = load(L['root']['sprite'])
check('background 1024x1024', bg.shape[:2] == (1024, 1024))
check('background black + grey lines', float(bg[..., :3].max()) <= 0.86 and float(np.median(bg[..., :3])) == 0.0)


def parts_from_build_script(path):
    src = open(path, encoding='utf-8').read()
    body = src[src.index('static List<PartSpec> Parts()'):]
    body = body[:body.index('return l;')]
    out = []
    for line in body.splitlines():
        m = re.search(r'new PartSpec\(\s*("[^"]+"(?:\s*\+\s*s)?)', line)
        if m:
            x = m.group(1)
            out += [eval(x.replace('+ s', f'+ "{s}"')) for s in ('L', 'R')] if '+ s' in x else [eval(x)]
    return out


want = parts_from_build_script(parts_src) if parts_src.endswith('.cs') else [p['part'] for p in json.load(open(parts_src))['parts']]
have = [e['name'] for e in L['parts']]
hidden = [e['name'] for e in L['hidden_parts']]
check('one image per UnitPart', sorted(have + hidden) == sorted(want), sorted(set(want) ^ set(have + hidden)))
check('image names unique', len(have) == len(set(have)))

S = 1024 / L['root']['size'][0]            # background px per UI unit
outline = bg[..., 0] > 0.05
# fill the outline: everything not reachable from the border through non-line pixels
inside = np.ones((1024, 1024), bool)
reach = np.zeros((1024, 1024), bool)
reach[0, :] = reach[-1, :] = reach[:, 0] = reach[:, -1] = True
reach &= ~outline
free = ~outline
for _ in range(2048):
    nr = reach.copy()
    nr[1:] |= reach[:-1]; nr[:-1] |= reach[1:]; nr[:, 1:] |= reach[:, :-1]; nr[:, :-1] |= reach[:, 1:]
    nr &= free
    if (nr == reach).all():
        break
    reach = nr
inside = ~reach
acc = np.zeros((1024, 1024), np.float32)
union = np.zeros((1024, 1024), bool)
for e in L['parts']:
    spr = load(e['sprite'])
    th, tw = spr.shape[:2]
    check(f"{e['name']} sprite size", [tw, th] == e['sizeDelta'] and max(tw, th) == 128 and min(tw, th) in (64, 128), (tw, th))
    check(f"{e['name']} grey fill on black", float(spr[..., :3].max()) <= 219 / 255 + 1e-3 and float(spr[0, 0, :3].max()) == 0)
    sx, sy = e['localScale'][:2]
    w, h = abs(sx) * tw * S, sy * th * S
    cx, cy = 512 + e['anchoredPosition'][0] * S, 512 - e['anchoredPosition'][1] * S
    img = Image.fromarray((spr[..., 0] * 255).astype(np.uint8))
    if sx < 0:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    W, H = max(1, int(round(w))), max(1, int(round(h)))
    img = np.asarray(img.resize((W, H), Image.BILINEAR)).astype(np.float32) / 255 > 0.45
    x0, y0 = int(round(cx - W / 2)), int(round(cy - H / 2))
    canvas = np.zeros((1024, 1024), bool)
    xa, ya = max(0, x0), max(0, y0)
    xb, yb = min(1024, x0 + W), min(1024, y0 + H)
    canvas[ya:yb, xa:xb] = img[ya - y0:yb - y0, xa - x0:xb - x0]
    lit = canvas.sum()
    on = (canvas & (inside | outline)).sum() / max(lit, 1)
    check(f"{e['name']} lands on the aircraft", lit > 20 and on >= 0.97, f'{on:.3f} of {lit} px')
    acc += canvas
    union |= canvas
byname = {e['name']: e for e in L['parts']}
for nm, e in byname.items():
    if nm.endswith('_L') and nm[:-2] + '_R' in byname:
        r = byname[nm[:-2] + '_R']
        ok = abs(e['anchoredPosition'][0] + r['anchoredPosition'][0]) < 2 and abs(e['anchoredPosition'][1] - r['anchoredPosition'][1]) < 2
        if e['sprite'] == r['sprite']:
            ok &= e['localScale'][0] < 0 < r['localScale'][0] and abs(abs(e['localScale'][0]) - r['localScale'][0]) < 1e-3
        check(f'{nm} mirrors {nm[:-2]}_R', ok, (e['anchoredPosition'], r['anchoredPosition'], e['localScale'][0], r['localScale'][0]))
ov = acc.sum() / max(union.sum(), 1)
check('part images tile without large overlap', ov <= 1.08, f'{ov:.3f}')
cov = (union & inside).sum() / max(inside.sum(), 1)
check('part images cover the drawn aircraft', cov >= 0.85, f'{cov:.3f}')
names = [f['name'] for f in L['failure_indicators']]
check('failure indicators', sorted(names) == sorted(['LEFT ENGINE FAILURE', 'RIGHT ENGINE FAILURE', 'LEFT PROP STRIKE', 'RIGHT PROP STRIKE']), names)
print('SUMMARY', n - len(fails), 'pass', len(fails), 'fail', fails)
sys.exit(1 if fails else 0)
