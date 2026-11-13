"""1.8.3 offline B: draw the section JSON from section_r183.py with PIL (study only).

  python plot_sections_r183.py <json> <out.png> [--only name1,name2]
Each y-section panel: x -0.6..0.6, z 0.2..1.2 (Blender); the x0 panel: y 0.4..-2.6 (nose left), z 0.2..1.3. Grid every 0.1 m.
"""
import sys, json, colorsys
from PIL import Image, ImageDraw

d = json.load(open(sys.argv[1])); out = sys.argv[2]
only = set(sys.argv[sys.argv.index('--only') + 1].split(',')) if '--only' in sys.argv else None
keys = [k for k in d if k.startswith('y')] + (['x0'] if 'x0' in d else [])
S = 600                          # px per metre
pw, ph = int(1.2 * S), int(1.0 * S)
cols = {}


def col(o):
    if o not in cols:
        h = (len(cols) * 0.137) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 0.85)
        cols[o] = (int(r * 255), int(g * 255), int(b * 255))
    return cols[o]


panels = []
for k in keys:
    if k == 'x0':
        x0, x1, z0, z1, ix = 0.4, -2.6, 0.2, 1.3, 1
        w = int(abs(x1 - x0) * S * 0.5); h = int((z1 - z0) * S * 0.5); s = S * 0.5
    else:
        x0, x1, z0, z1, ix = -0.6, 0.6, 0.2, 1.2, 0
        w, h, s = pw, ph, S
    im = Image.new('RGB', (w, h), (255, 255, 255)); dr = ImageDraw.Draw(im)
    sg = 1 if x1 > x0 else -1

    def P(p):
        return ((p[ix] - x0) * s * sg, (z1 - p[2]) * s)
    g = round(min(x0, x1), 1)
    while g <= max(x0, x1):
        dr.line([P([g, g, z0]), P([g, g, z1])], fill=(225, 225, 225)); g = round(g + 0.1, 1)
    g = z0
    while g <= z1:
        dr.line([P([x0, x0, g]), P([x1, x1, g])], fill=(225, 225, 225)); g = round(g + 0.1, 1)
    for o, segs in d[k].items():
        if only and not any(o.startswith(n) for n in only):
            continue
        for a, b, m in segs:
            dr.line([P(a), P(b)], fill=col(o), width=2)
    dr.text((4, 4), k, fill=(0, 0, 0))
    panels.append(im)
W = max(p.width for p in panels)
cw = 4
rows = [panels[i:i + cw] for i in range(0, len(panels), cw)]
H = sum(max(p.height for p in r) for r in rows) + 18 * (len(cols) // 6 + 2)
sheet = Image.new('RGB', (W * cw, H), (255, 255, 255))
yy = 0
for r in rows:
    for i, p in enumerate(r):
        sheet.paste(p, (i * W, yy))
    yy += max(p.height for p in r)
dr = ImageDraw.Draw(sheet)
for i, (o, c) in enumerate(cols.items()):
    dr.text((10 + (i % 6) * 300, yy + 4 + 18 * (i // 6)), o, fill=c)
sheet.save(out)
print('[plot]', out)
