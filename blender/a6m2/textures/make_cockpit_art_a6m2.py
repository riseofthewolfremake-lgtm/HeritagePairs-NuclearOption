"""A6M2 cockpit dial atlas (round 4; plain Python: PIL + numpy). Our own period IJN-style faces: black faces, white Arabic numerals and
ticks, cream-white needles; scales and zero marks from blender/a6m2/a6m2_ck_layout.py (DIALS zero_deg, SCALES), so a needle moved by
the plugin's value -> angle map lands on the painted value. Kanji label plates are left out (design risk 13: font licence).

  python blender/a6m2/textures/make_cockpit_art_a6m2.py [--out assets/textures_a6m2]

Writes a6m2_gauges.png (2048, 8 x 8 cells of 256 px, layout a6m2_ck_layout.GAUGE_CELLS; row 0 = the BOTTOM of the image, v = 0).
"""
import os, sys, math
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..'))
import a6m2_ck_layout as L

argv = sys.argv[1:]
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_a6m2')
os.makedirs(OUT, exist_ok=True)
FONT_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
N, G = L.GAUGE_N, L.GAUGE_GRID
CELL = N // G
WHITE = (236, 232, 218)
FACE = (18, 18, 17)


def font(px, bold=True):
    for n in (('arialbd.ttf' if bold else 'arial.ttf'), 'arial.ttf'):
        p = os.path.join(FONT_DIR, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, max(6, int(px)))
    return ImageFont.load_default()


def region_box(region):
    c, r, s = L.GAUGE_CELLS[region]
    x0 = c * CELL
    y1 = N - r * CELL                    # image y (top-down) of the region's bottom edge
    return x0, y1 - s * CELL, x0 + s * CELL, y1


def disc_geom(region):
    x0, y0, x1, y1 = region_box(region)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R = (x1 - x0) / 2 * 0.96
    return cx, cy, R


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def dial_face(d, region, zero, sweep, v0, v1, major, minor, label_every, fmt, title=''):
    cx, cy, R = disc_geom(region)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=FACE)
    n_minor = int(round((v1 - v0) / minor))
    for k in range(n_minor + 1):
        v = v0 + k * minor
        a = zero + (v - v0) / (v1 - v0) * sweep
        is_major = abs((v - v0) / major - round((v - v0) / major)) < 1e-6
        r0 = R * (0.78 if is_major else 0.85)
        d.line([polar(cx, cy, r0, a), polar(cx, cy, R * 0.93, a)], fill=WHITE, width=max(2, int(R * (0.035 if is_major else 0.018))))
        if is_major and abs((v - v0) / label_every - round((v - v0) / label_every)) < 1e-6:
            f = font(R * 0.17)
            d.text(polar(cx, cy, R * 0.60, a), fmt(v), fill=WHITE, font=f, anchor='mm')
    if title:
        d.text((cx, cy + R * 0.32), title, fill=(200, 196, 180), font=font(R * 0.10, False), anchor='mm')


def main():
    img = Image.new('RGB', (N, N), (30, 30, 28))
    d = ImageDraw.Draw(img)
    D = L.DIALS
    S = L.SCALES
    dial_face(d, 'asi', D['asi']['zero'], S['asi']['sweep'], 0, 350, 50, 10, 50, lambda v: str(int(v)), 'KT')
    # altimeter: 0-9 (x 100 m on the long hand), one turn = 1,000 m
    dial_face(d, 'alt', 0, 360, 0, 1000, 100, 20, 100, lambda v: '' if v >= 1000 else str(int(v // 100)), 'x100 m')
    dial_face(d, 'rpm', D['rpm']['zero'], S['rpm']['sweep'], 0, 3500, 500, 100, 500, lambda v: str(int(v // 100)), 'x100 RPM')
    dial_face(d, 'boost', D['boost']['zero'], S['boost']['sweep'], -400, 200, 100, 50, 100, lambda v: ('+' if v > 0 else '') + str(int(v)), 'mmHg')
    cx, cy, R = disc_geom('boost')                           # r8b: red sector over the boost range (WT manifold pressure face)
    a0 = D['boost']['zero'] + (0 - -400) / 600 * S['boost']['sweep']; a1 = D['boost']['zero'] + S['boost']['sweep']
    d.arc([cx - R * 0.93, cy - R * 0.93, cx + R * 0.93, cy + R * 0.93], a0 - 90, a1 - 90, fill=(170, 30, 24), width=int(R * 0.16))
    # VSI: 0 at the rest mark (9 o'clock), +20 m/s 150 deg clockwise, -20 m/s 150 deg anticlockwise
    cx, cy, R = disc_geom('vsi')
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=FACE)
    for k in range(-20, 21):
        a = D['vsi']['zero'] + k * 7.5
        big = k % 5 == 0
        d.line([polar(cx, cy, R * (0.78 if big else 0.86), a), polar(cx, cy, R * 0.93, a)], fill=WHITE, width=4 if big else 2)
        if big and k % 10 == 0:
            d.text(polar(cx, cy, R * 0.60, a), str(abs(k)), fill=WHITE, font=font(R * 0.17), anchor='mm')
    d.text((cx + R * 0.25, cy - R * 0.25), 'UP', fill=WHITE, font=font(R * 0.10), anchor='mm')
    d.text((cx + R * 0.25, cy + R * 0.25), 'DN', fill=WHITE, font=font(R * 0.10), anchor='mm')
    dial_face(d, 'oilp', D['oilp']['zero'], 270, 0, 10, 2, 1, 2, lambda v: str(int(v)), 'OIL kg')
    dial_face(d, 'oilt', D['oilt']['zero'], 270, 0, 120, 20, 10, 40, lambda v: str(int(v)), 'OIL C')
    dial_face(d, 'fuel', D['fuel']['zero'], 270, 0, 100, 25, 12.5, 50, lambda v: str(int(v)), 'FUEL %')
    dial_face(d, 'clock', 0, 360, 0, 12, 1, 0.2, 3, lambda v: str(int(v) if v else 12), '')
    # r4c static faces (no movers): fuel pressure, cylinder head temperature, oxygen, exhaust temperature
    dial_face(d, 'fuelp', -135, 270, 0, 1.0, 0.2, 0.1, 0.2, lambda v: '%.1f' % v, 'FUEL kg')
    dial_face(d, 'cht', -135, 270, 0, 300, 50, 25, 100, lambda v: str(int(v)), 'CYL C')
    dial_face(d, 'oxy', -135, 270, 0, 150, 30, 10, 50, lambda v: str(int(v)), 'O2')
    dial_face(d, 'exht', -135, 270, 0, 900, 100, 50, 300, lambda v: str(int(v)), 'EXH C')
    # placard plate: cream with black ruled lines (no kanji: font licence, design risk 13)
    x0, y0, x1, y1 = region_box('placard')
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(206, 198, 172))
    d.rectangle([x0 + 10, y0 + 10, x1 - 11, y1 - 11], outline=(30, 28, 24), width=5)
    for k in range(6):
        yy = y0 + 46 + k * 32
        d.line([(x0 + 30, yy), (x1 - 30 - (k % 3) * 30, yy)], fill=(40, 36, 30), width=7)
    # switch plate: black with a white ON/OFF bar
    x0, y0, x1, y1 = region_box('switchplate')
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(20, 20, 19))
    d.rectangle([x0 + 40, y0 + 30, x1 - 41, y0 + 60], fill=(200, 196, 180))
    d.rectangle([x0 + 40, y1 - 61, x1 - 41, y1 - 31], fill=(200, 196, 180))
    for reg, col in (('red', (170, 30, 24)), ('cream', (206, 198, 172))):
        x0, y0, x1, y1 = region_box(reg)
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=col)
    for reg in ('cream',):                                       # magneto plate: 4 position marks
        cx, cy, R = disc_geom(reg)
        for a, t in ((-60, '0'), (-20, 'L'), (20, 'R'), (60, '1+2')):
            d.line([polar(cx, cy, R * 0.6, a), polar(cx, cy, R * 0.9, a)], fill=(20, 20, 20), width=6)
    # turn and slip: needle centre mark + two rate marks; slip tube arc at the bottom
    cx, cy, R = disc_geom('turn')
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=FACE)
    for a in (-30, 0, 30):
        d.line([polar(cx, cy, R * 0.70, a), polar(cx, cy, R * 0.93, a)], fill=WHITE, width=6 if a == 0 else 4)
    d.arc([cx - R * 0.75, cy - R * 0.75 + R * 0.62, cx + R * 0.75, cy + R * 0.75 + R * 0.62], 200, 340, fill=(90, 90, 85), width=int(R * 0.20))
    for a in (-8, 8):
        d.line([polar(cx, cy + R * 0.62, R * 0.55, 180 + a), polar(cx, cy + R * 0.62, R * 0.75, 180 + a)], fill=WHITE, width=3)
    # artificial horizon: face = black bezel ring with bank marks (the card shows through)
    cx, cy, R = disc_geom('horizon')
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=FACE)
    for a in (-60, -30, -20, -10, 0, 10, 20, 30, 60):
        d.line([polar(cx, cy, R * 0.82, a), polar(cx, cy, R * 0.95, a)], fill=WHITE, width=4)
    cx, cy, R = disc_geom('horizon_card')                    # card: sky blue over earth brown, pitch lines
    d.pieslice([cx - R, cy - R, cx + R, cy + R], 180, 360, fill=(70, 120, 170))
    d.pieslice([cx - R, cy - R, cx + R, cy + R], 0, 180, fill=(80, 55, 35))
    d.line([(cx - R, cy), (cx + R, cy)], fill=WHITE, width=6)
    for k in (-2, -1, 1, 2):
        w = R * (0.25 if abs(k) == 1 else 0.40)
        d.line([(cx - w, cy - k * R * 0.18), (cx + w, cy - k * R * 0.18)], fill=WHITE, width=3)
    # needles / hub / ball / rims / plain cells
    for reg, col in (('needle', WHITE), ('needle_short', WHITE), ('hub', (40, 40, 38)), ('ball', (10, 10, 10)), ('rim_black', (22, 22, 22)),
                     ('rim_alu', (170, 172, 172)), ('glass_dark', (12, 14, 16)), ('black', (14, 14, 14)), ('label', (16, 16, 15))):
        x0, y0, x1, y1 = region_box(reg)
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=col)
    x0, y0, x1, y1 = region_box('label')                     # r6: black label plates with white lettering strokes (reference)
    for k in range(3):
        d.rectangle([x0 + 50 + k * 56, y0 + 100, x0 + 86 + k * 56, y1 - 100], fill=(210, 206, 192))
    # compass drum strip: 0..360 deg left -> right over the 4-cell span, 0 (N) at u 0
    x0, y0, x1, y1 = region_box('compass_card')
    y0 = y1 - CELL                                            # r4c: the drum strip is one cell high (strip_uv v span 1); rows above are free
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(28, 28, 26))      # r8b: dark card with white marks (the r8 cream card read as a white strip)
    W = x1 - x0
    for h in range(0, 360, 5):
        x = x0 + W * h / 360
        big = h % 30 == 0
        d.line([(x, y1 - (y1 - y0) * (0.55 if big else 0.30)), (x, y1)], fill=(225, 220, 200), width=4 if big else 2)
        if big:
            lab = {0: 'N', 90: 'E', 180: 'S', 270: 'W'}.get(h, str(h // 10))
            d.text((x, y0 + (y1 - y0) * 0.28), lab, fill=(225, 220, 200), font=font((y1 - y0) * 0.30), anchor='mm')
    x0, y0, x1, y1 = region_box('compass_window')
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(14, 14, 14))
    d.rectangle([x0 + 8, y0 + 40, x1 - 9, y1 - 41], fill=(30, 34, 36))
    d.line([((x0 + x1) / 2, y0 + 30), ((x0 + x1) / 2, y1 - 30)], fill=(230, 120, 30), width=4)       # lubber line
    x0, y0, x1, y1 = region_box('reticle')
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(0, 0, 0))
    out = os.path.join(OUT, 'a6m2_gauges.png')
    img.save(out)
    print('[a6art]', out, img.size)


if __name__ == '__main__':
    main()
