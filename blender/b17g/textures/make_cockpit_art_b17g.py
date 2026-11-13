"""B-17G cockpit art (PIL): the gauge atlas b17g_gauges.png (5 x 5 cells of 512, order = b17g_cockpit.FACES) from the fal dial faces
(assets/textures_b17g/fal_ck/dial_*.png, fal-ai/nano-banana-2, every call in that folder's fal_manifest.jsonl) plus the attitude
card halves, and the cockpit tiles (ck_panel, ck_wall from fal z-image tiling; ck_od / ck_floor / ck_black / ck_bezel tone-matched).

  python blender/b17g/textures/make_cockpit_art_b17g.py [--out assets/textures_b17g]
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
FAL = os.path.join(ROOT, 'assets', 'textures_b17g', 'fal_ck')
OUT = os.path.abspath(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else os.path.join(ROOT, 'assets', 'textures_b17g')
FACES = ['dial_asi', 'dial_alt', 'dial_vsi', 'dial_mp', 'dial_rpm', 'dial_turn', 'dial_dg', 'dial_temp', 'att_sky', 'att_ground',
         'dial_egu', 'dial_oilt', 'dial_clock', 'dial_suction', 'plate_ff', 'plate_warn', 'plate_start', 'plate_fire', 'red', 'black']
NA = 5      # 5 x 5 cells (round 2: + engine gauge unit, oil temp, clock, suction, 4 placards, red / black solids)
C = 512


def dial(name):
    src = os.path.join(FAL, name + '.png')
    if name == 'dial_vsi' and os.path.exists(os.path.join(FAL, 'dial_vsi2.png')):
        src = os.path.join(FAL, 'dial_vsi2.png')        # the first VSI concept had a painted needle
    im = Image.open(src).convert('RGB')
    a = np.asarray(im).astype(np.float32).mean(-1)
    # the dial disc: the bounding box of the dark face (luminance < 90) - crops the white surround of some concepts
    ys, xs = np.where(a < 90)
    if len(xs):
        x0, x1, y0, y1 = np.percentile(xs, 1), np.percentile(xs, 99), np.percentile(ys, 1), np.percentile(ys, 99)
        s = max(x1 - x0, y1 - y0); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        im = im.crop((int(cx - s / 2), int(cy - s / 2), int(cx + s / 2), int(cy + s / 2)))
    im = im.resize((C, C), Image.LANCZOS)
    mask = Image.new('L', (C, C), 0); ImageDraw.Draw(mask).ellipse((2, 2, C - 3, C - 3), fill=255)
    out = Image.new('RGB', (C, C), (10, 10, 10)); out.paste(im, (0, 0), mask)
    return out


def plate(name):
    """placard: crop the white / grey surround (bounding box of the dark plate), stretch to the square cell (the quad's UV
    spans the cell, so the plate keeps its aspect on the panel)."""
    im = Image.open(os.path.join(FAL, name + '.png')).convert('RGB')
    a = np.asarray(im).astype(np.float32).mean(-1)
    ys, xs = np.where(a < 70)
    if len(xs):
        x0, x1, y0, y1 = np.percentile(xs, 0.5), np.percentile(xs, 99.5), np.percentile(ys, 0.5), np.percentile(ys, 99.5)
        im = im.crop((int(x0), int(y0), int(x1), int(y1)))
    return im.resize((C, C), Image.LANCZOS)


def att(sky):
    # 1.8.4 (in game 1.8.2: 'attitude face very dark in the cockpit view'): the card was (34, 46, 62) / (16, 14, 12), darker than the
    # black dial faces' white markings by 4x; now a mid sky blue and an earth brown at the luminance of the fal dial markings' surround
    im = Image.new('RGB', (C, C), (92, 140, 196) if sky else (112, 76, 44))
    d = ImageDraw.Draw(im)
    if sky:
        d.rectangle((0, C - 14, C, C), fill=(235, 235, 230))          # horizon bar at the card's bottom edge
        for k, w in ((1, 0.30), (2, 0.18), (3, 0.30)):
            y = C - 14 - k * 70
            d.rectangle((C / 2 - w * C / 2, y - 3, C / 2 + w * C / 2, y + 3), fill=(220, 220, 215))
    else:
        d.rectangle((0, 0, C, 14), fill=(235, 235, 230))
        for k, w in ((1, 0.30), (2, 0.18)):
            y = 14 + k * 70
            d.rectangle((C / 2 - w * C / 2, y - 3, C / 2 + w * C / 2, y + 3), fill=(200, 200, 195))
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    atlas = Image.new('RGB', (NA * C, NA * C), (10, 10, 10))
    for i, f in enumerate(FACES):
        if f == 'red':
            cell = Image.new('RGB', (C, C), (150, 18, 14))
        elif f == 'black':
            cell = Image.new('RGB', (C, C), (14, 14, 15))
        elif f.startswith('plate_'):
            cell = plate(f)
        else:
            cell = att(True) if f == 'att_sky' else att(False) if f == 'att_ground' else dial(f)
        atlas.paste(cell, ((i % NA) * C, (i // NA) * C))
    atlas.save(os.path.join(OUT, 'b17g_gauges.png'))
    # tiles
    def tile(src, rgb, contrast, name):
        a = np.asarray(Image.open(os.path.join(FAL, src + '.png')).convert('RGB').resize((512, 512), Image.LANCZOS)).astype(np.float32) / 255
        m = a.reshape(-1, 3).mean(0)
        o = np.clip((a - m) * contrast + np.asarray(rgb), 0, 1)
        Image.fromarray((o * 255).astype(np.uint8)).save(os.path.join(OUT, f'b17g_tile_{name}_b.png'))
    tile('ck_panel', (0.035, 0.035, 0.038), 0.6, 'ck_panel')
    tile('ck_wall', (0.27, 0.33, 0.24), 0.5, 'ck_wall')        # bronze green (photo 107)
    tile('ck_wall', (0.25, 0.27, 0.17), 0.5, 'ck_od')          # olive drab
    tile('ck_wall', (0.20, 0.22, 0.17), 0.7, 'ck_floor')
    tile('ck_panel', (0.02, 0.02, 0.022), 0.4, 'ck_black')
    tile('ck_panel', (0.10, 0.10, 0.10), 0.5, 'ck_bezel')
    print('[ckart] gauges atlas + 6 cockpit tiles ->', OUT)


main()
