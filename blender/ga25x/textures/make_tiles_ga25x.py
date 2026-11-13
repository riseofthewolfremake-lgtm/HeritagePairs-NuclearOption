"""GA-25X own tiling textures + gauge atlas (visual pass 2026-10-31). Plain Python 3 (numpy + Pillow).

  python blender/ga25x/textures/make_tiles_ga25x.py [--out assets/textures_ga25x]

- ga25x_interior_b.png, ga25x_prop_b.png: our B-25H tiles (assets/textures_v2/b25h_*, own art) with
  their colour replaced by modern greys (grey primer for gear wells / bays / door insides, composite blade grey);
  0.3.1: the dark cockpit tile (ga25x_cockpit_b, crosshatch noise) is no longer made or used - the cabin uses the stock
  aircraft_structure material and plain greys (user: no crosshatch textures in the cockpit); only the luminance detail of the B-25H tile is kept. GA25XBuild.TextureSource prefers these files
  (assets/textures_ga25x) over the shared B-25H ones, so no generator change is needed.
- ga25x_gauges.png: 2048 px, 8 x 8 cells (cell k = column k % 8, row k // 8, row 0 at the BOTTOM, as b25h_v3_cockpit.cell_uv):
  cell 0 ISIS attitude/speed/altitude standby display, 1 engine/power page, 2 nav/clock. Drawn here, no game art.
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'assets', 'textures_v2')
OUT = os.path.abspath(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else os.path.join(ROOT, 'assets', 'textures_ga25x')

RECOLOUR = {   # name: (source B-25H tile, target mean sRGB, detail contrast)
    'interior_b': ('b25h_interior_b.png', (104, 108, 111), 1.0),   # grey primer
    'prop_b': ('b25h_prop_b.png', (34, 36, 38), 1.6),              # composite blade grey
}


def recolour(src, mean, k):
    im = Image.open(os.path.join(SRC, src)).convert('RGBA')
    a = np.asarray(im).astype(np.float32)
    lum = a[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    rel = lum / max(lum.mean(), 1e-3)
    rel = 1.0 + (rel - 1.0) * k
    rgb = np.clip(rel[..., None] * np.array(mean, np.float32)[None, None, :], 0, 255)
    out = np.concatenate([rgb, a[..., 3:]], -1).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def font(sz):
    try:
        return ImageFont.load_default(size=sz)
    except TypeError:
        return ImageFont.load_default()


def cell_box(k, S=2048, G=8):
    c = S // G
    col, row = k % G, k // G
    x0 = col * c
    y0 = S - (row + 1) * c                  # row 0 at the bottom of the image (v = 0)
    return x0, y0, c


def draw_isis(d, x0, y0, c):
    cx, cy = x0 + c // 2, y0 + c // 2
    d.rectangle([x0, y0, x0 + c - 1, y0 + c - 1], fill=(8, 9, 10))
    # 1.8.4: the horizon is the round card mover (cell 3) and the aircraft symbol a static yellow mesh in front of it; the speed / altitude
    # tapes keep their boxes without the old fixed numbers (the moving speed / altitude are on the tac pages)
    d.ellipse([cx - 66, cy + 8 - 66, cx + 66, cy + 8 + 66], outline=(60, 62, 66), width=3)
    for x in (x0 + 4, x0 + c - 50):                                                  # speed / altitude tapes
        d.rectangle([x - 2, y0 + 20, x + 46, y0 + c - 20], fill=(25, 27, 30))
        for k in range(-4, 5):
            d.line([x + 30, cy + 8 + k * 22, x + 44, cy + 8 + k * 22], fill=(150, 150, 150), width=2)
    d.text((cx - 30, y0 + 22), 'ISIS', fill=(0, 230, 120), font=font(18))
    d.rectangle([x0 + 2, y0 + 2, x0 + c - 3, y0 + c - 3], outline=(60, 62, 66), width=3)


def draw_engine(d, x0, y0, c):
    d.rectangle([x0, y0, x0 + c - 1, y0 + c - 1], fill=(8, 9, 10))
    f = font(18)
    for k, (lab, frac) in enumerate((('TQ L', 0.72), ('TQ R', 0.70))):
        cx, cy, r = x0 + 64 + k * 128, y0 + 92, 50
        d.arc([cx - r, cy - r, cx + r, cy + r], 150, 390, fill=(90, 95, 100), width=8)      # 1.8.4: pointer mover on the arc (no fixed fill / %)
        d.arc([cx - r, cy - r, cx + r, cy + r], 330, 390, fill=(0, 220, 120), width=8)      # green band 75..100 %
        d.text((cx - 20, cy + 54), lab, fill=(180, 180, 180), font=f)
    for k, (lab, frac, col) in enumerate((('CAP', 0.82, (0, 200, 255)), ('BATT', 0.64, (0, 220, 120)), ('FUEL', 0.55, (255, 200, 0)))):
        yy = y0 + 172 + k * 26
        d.text((x0 + 12, yy - 2), lab, fill=(200, 200, 200), font=f)
        d.rectangle([x0 + 70, yy, x0 + 236, yy + 14], outline=(90, 95, 100))
        if lab != 'FUEL':                                                                   # 1.8.4: the fuel bar is a mover (cell 5)
            d.rectangle([x0 + 71, yy + 1, x0 + 71 + int(164 * frac), yy + 13], fill=col)
    d.rectangle([x0 + 2, y0 + 2, x0 + c - 3, y0 + c - 3], outline=(60, 62, 66), width=3)


def draw_nav(d, x0, y0, c):
    d.rectangle([x0, y0, x0 + c - 1, y0 + c - 1], fill=(8, 9, 10))
    cx, cy, r = x0 + c // 2, y0 + 112, 84
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(220, 220, 220), width=3)     # 1.8.4: rose = card mover (cell 4), lubber = mesh
    d.text((x0 + 92, y0 + 206), 'MAG HDG', fill=(0, 230, 120), font=font(20))          # (the fixed '14:32:07Z' readout is gone)
    d.rectangle([x0 + 2, y0 + 2, x0 + c - 3, y0 + c - 3], outline=(60, 62, 66), width=3)


def gauges():
    S = 2048
    im = Image.new('RGBA', (S, S), (14, 15, 16, 255))
    d = ImageDraw.Draw(im)
    for k, fn in ((0, draw_isis), (1, draw_engine), (2, draw_nav)):
        fn(d, *cell_box(k, S))
    draw_movers_184(d, S)
    return im


def draw_movers_184(d, S):
    """1.8.4 mover cells: 3 horizon card, 4 heading card, 5 amber (fuel bar), 6 white (pointers), 7 yellow (symbols). Cards fill the
    cell's disc (the disc UVs map radius 1 to the cell edge minus the 2 % margin)."""
    x0, y0, c = cell_box(3, S); cx, cy = x0 + c / 2, y0 + c / 2
    d.rectangle([x0, y0, x0 + c - 1, y0 + c - 1], fill=(120, 80, 40))
    d.rectangle([x0, y0, x0 + c - 1, cy], fill=(40, 110, 190))
    d.line([x0, cy, x0 + c, cy], fill=(240, 240, 240), width=4)
    k = c / 2 * 0.96 / 30.0                         # card radius 0.018 m <-> 0.0006 m/deg: 30 deg of ladder per card radius
    for p in (-20, -10, 10, 20):
        w = 30 if abs(p) == 10 else 46
        d.line([cx - w, cy - p * k, cx + w, cy - p * k], fill=(240, 240, 240), width=3)
    for a in (-60, -30, -20, -10, 0, 10, 20, 30, 60):  # bank scale near the rim
        r0, r1 = c / 2 * 0.86, c / 2 * 0.95
        t = math.radians(a)
        d.line([cx + r0 * math.sin(t), cy - r0 * math.cos(t), cx + r1 * math.sin(t), cy - r1 * math.cos(t)], fill=(255, 255, 255), width=4)
    x0, y0, c = cell_box(4, S); cx, cy = x0 + c / 2, y0 + c / 2
    d.rectangle([x0, y0, x0 + c - 1, y0 + c - 1], fill=(8, 9, 10))
    r = c / 2 * 0.94
    f = font(26)
    for k in range(36):
        a = math.radians(k * 10 - 90)
        l = 22 if k % 3 == 0 else 11
        d.line([cx + (r - l) * math.cos(a), cy + (r - l) * math.sin(a), cx + r * math.cos(a), cy + r * math.sin(a)], fill=(220, 220, 220), width=3)
    for k, t in enumerate('NESW'):
        a = math.radians(k * 90 - 90)
        d.text((cx + (r - 48) * math.cos(a) - 9, cy + (r - 48) * math.sin(a) - 13), t, fill=(255, 255, 255), font=f)
    for k, col in ((5, (255, 200, 0)), (6, (240, 240, 240)), (7, (255, 210, 0))):
        x0, y0, c = cell_box(k, S)
        d.rectangle([x0, y0, x0 + c - 1, y0 + c - 1], fill=col)


def main():
    os.makedirs(OUT, exist_ok=True)
    for n, (src, mean, k) in RECOLOUR.items():
        recolour(src, mean, k).save(os.path.join(OUT, f'ga25x_{n}.png'))
        print('tile', n)
    gauges().save(os.path.join(OUT, 'ga25x_gauges.png'))
    print('gauges atlas')


if __name__ == '__main__':
    main()
