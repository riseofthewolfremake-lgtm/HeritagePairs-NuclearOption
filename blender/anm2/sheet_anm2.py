"""1.8.13 round 2: compose the study renders of render_anm2.py into labelled sheets (system Python + Pillow; study output only).

  python blender/anm2/sheet_anm2.py <dir> compare                 -> sheet_flex_single.png, sheet_turret_twin.png (rows = views, cols = WT / ours / stock)
  python blender/anm2/sheet_anm2.py <dir> turrets <label> <base>.. -> sheet_<label>_<base>.png (rows = poses, cols = o / x / i)
  python blender/anm2/sheet_anm2.py <dir> overview <png>..         -> overview.png (contact sheet of the given images, 3 wide)
  python blender/anm2/sheet_anm2.py <dir> table <label=log>..      -> clearance_table.png (clipping poses per station, one column per sweep)
"""
import os, sys, glob
from PIL import Image, ImageDraw, ImageFont

D = sys.argv[1]; MODE = sys.argv[2]
try:
    FONT = ImageFont.truetype('arial.ttf', 22); SMALL = ImageFont.truetype('arial.ttf', 16)
except OSError:
    FONT = SMALL = ImageFont.load_default()


def grid(rows, title, out, cell_w=520):
    """rows: [(row label, [(col label, path or None)])]"""
    ims = [[(cl, Image.open(p).convert('RGB') if p and os.path.exists(p) else None) for cl, p in r] for _, r in rows]
    ncol = max(len(r) for r in ims)
    ref = next(im for r in ims for _, im in r if im is not None)
    ch = int(cell_w * ref.height / ref.width)
    W = 140 + ncol * (cell_w + 6); H = 50 + len(rows) * (ch + 30)
    sh = Image.new('RGB', (W, H), (235, 235, 235)); d = ImageDraw.Draw(sh)
    d.text((10, 10), title, fill=(0, 0, 0), font=FONT)
    for ri, ((rl, _), r) in enumerate(zip(rows, ims)):
        y = 50 + ri * (ch + 30)
        d.text((10, y + ch // 2), rl, fill=(0, 0, 0), font=SMALL)
        for ci, (cl, im) in enumerate(r):
            x = 140 + ci * (cell_w + 6)
            d.text((x, y), cl, fill=(60, 60, 60), font=SMALL)
            if im is not None:
                sh.paste(im.resize((cell_w, ch)), (x, y + 22))
    sh.save(out); print('SHEET', out, sh.size)


if MODE == 'compare':
    for tag, title in (('flex_single', 'AN/M2 flexible (hand-held) gun: War Thunder reference | ours | stock game door gun - same camera per row'),
                       ('turret_twin', 'AN/M2 turret twin: War Thunder reference | ours')):
        rows = []
        for v in ('side', 'top', 'front', 'rear', 'q34'):
            cols = [(lab, os.path.join(D, f'cmp_{tag}_{v}_{g}.png')) for g, lab in (('wt', 'War Thunder (study ref)'), ('ours', 'ours'), ('stock', 'stock door gun'))
                    if os.path.exists(os.path.join(D, f'cmp_{tag}_{v}_{g}.png'))]
            rows.append((v, cols))
        grid(rows, title, os.path.join(D, f'sheet_{tag}.png'))
elif MODE == 'turrets':
    label = sys.argv[3]
    for base in sys.argv[4:]:
        poses = sorted({os.path.basename(p)[len(f'{label}_{base}_'):-6] for p in glob.glob(os.path.join(D, f'{label}_{base}_*_?.png'))},
                       key=lambda s: (s != 'rest', s))
        rows = [(p, [(lab, os.path.join(D, f'{label}_{base}_{p}_{v}.png')) for v, lab in (('o', 'outside, opaque'), ('x', 'x-ray'), ('i', 'gunner view'))]) for p in poses]
        grid(rows, f'{label.upper()} {base}: our AN/M2 at rest and at the limit corners', os.path.join(D, f'sheet_{label}_{base}.png'), cell_w=420)
elif MODE == 'overview':
    paths = sys.argv[3:]
    rows = [(f'{i // 3 + 1}', [(os.path.basename(p), p) for p in paths[i:i + 3]]) for i in range(0, len(paths), 3)]
    grid(rows, 'Heritage Pairs 1.8.13 offline L (round 4): AN/M2 .50 overview - offline renders, not in game', os.path.join(D, 'overview.png'), cell_w=600)
elif MODE == 'table':
    # table <label=log> ... : one column per sweep log (STOCKCLEAR or ANM2CLEAR lines)
    import re
    def rows(path):
        out = {}
        for l in open(path, encoding='utf-8', errors='ignore'):
            m = re.search(r'(?:STOCKCLEAR|ANM2CLEAR) (B25H|B17G) (\w+): rest .*?clipping poses (\d+)/(\d+)', l)
            if m:
                out[(m.group(1), m.group(2).replace('_mount', ''))] = (int(m.group(3)), int(m.group(4)))
        return out
    cols = [(a.split('=', 1)[0], rows(a.split('=', 1)[1])) for a in sys.argv[3:]]
    keys = sorted(set().union(*[c for _, c in cols]))
    xs = [300 + 200 * i for i in range(len(cols))]
    im = Image.new('RGB', (xs[-1] + 220, 70 + 34 * (len(keys) + 2)), (250, 250, 250)); d = ImageDraw.Draw(im)
    d.text((16, 14), 'Clipping poses per gun station (same strict sweep: rest pose included, receiver on glass = clip)', fill=(0, 0, 0), font=FONT)
    y = 60
    d.text((16, y), 'aircraft / station', fill=(60, 60, 60), font=SMALL)
    for (lab, _), x in zip(cols, xs):
        d.text((x, y), lab, fill=(60, 60, 60), font=SMALL)
    tot = [0] * len(cols)
    for k in keys:
        y += 34
        d.text((16, y), f'{k[0]} {k[1]}', fill=(0, 0, 0), font=SMALL)
        for i, ((_, c), x) in enumerate(zip(cols, xs)):
            v = c.get(k)
            if v:
                tot[i] += v[0]
                d.text((x, y), f'{v[0]} / {v[1]}', fill=(170, 30, 30) if v[0] else (20, 120, 40), font=SMALL)
    y += 40
    d.text((16, y), 'total', fill=(0, 0, 0), font=FONT)
    for t, x in zip(tot, xs):
        d.text((x, y), str(t), fill=(0, 0, 0), font=FONT)
    im.save(os.path.join(D, 'clearance_table.png')); print('TABLE', tot)
    for k in keys:
        print(k, [c.get(k, ('-',))[0] for _, c in cols])
