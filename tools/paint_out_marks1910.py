"""1.9.10 (pre-publish audit): paint logo-like marks out of two AI-generated placard images, in place, so the cockpit atlases built
from them carry text only. No fal call: local pixels only.

  python tools/paint_out_marks1910.py [--check]

  assets/textures_b17g/fal_ck/plate_ff.png                 the winged-"B" roundel right of FLYING FORTRESS (an imitation of a
                                                           real maker's emblem; the generation prompt had asked for one)
  assets/textures_ga25x/fal_raw_cockpit/placards.png       the triangle-and-wing emblem above the word MANUFACTURER on the GA-25X
                                                           data plate, with that caption (an invented mark, but close in
                                                           style to a real maker's)

Each rectangle is refilled with plain plate surface: the low frequencies come from a smooth blend of the pixels on the rectangle's
border (so the plate's shading continues), the grain from a clean donor patch of the same plate. The text, the screws and the rest
of each image are not touched: only pixels inside the rectangle change.

The script is keyed on file hashes: it edits a file only when it is the known original, does nothing when the file is already the
edited one, and fails on anything else. After it: re-run blender/b17g/textures/make_cockpit_art_b17g.py and
blender/ga25x/textures/make_cockpit_art_ga25x.py (the atlases b17g_gauges.png and ga25x_ckart_b/_n.png follow).
--check: exit 1 unless both files are the edited ones.
"""
import os, sys, hashlib
import numpy as np
from PIL import Image, ImageFilter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# file, rectangle (x0, y0, x1, y1), donor rectangle (a clean piece of the same plate; tiled by mirroring when it is smaller), sha256 of
# the original, sha256 after
JOBS = [
    ('assets/textures_b17g/fal_ck/plate_ff.png', (1316, 146, 1518, 278), (1262, 286, 1462, 418),
     '03cee49a6adf9ef0dc29b7764dfcb0bd27b95a7c78703b0d30d243d538e55d1a', '27812a1caefef4336ec3a571e08d2860d341391fbb978df293832b4cd5b9e13c'),
    ('assets/textures_ga25x/fal_raw_cockpit/placards.png', (1442, 384, 1584, 504), (1426, 398, 1442, 470),
     '5ad4b033872d86b12bf1c00bf25a0d5ed6e8d13f7f512d8fbfa584a3fe7b1f22', 'fa7b55390bf0692c36ff0f59bed53087f33502f91d85b3e977ac657d86262a57'),
]
FEATHER = 6      # px: the fill fades into the original over this margin inside the rectangle


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def fill(a, rect, donor):
    x0, y0, x1, y1 = rect
    h, w = y1 - y0, x1 - x0
    src = a[y0:y1, x0:x1].astype(np.float32)
    # low frequencies: bilinear blend of the four border strips (mean of a 3 px strip just inside the rectangle's edge)
    top, bot = src[:3].mean(0), src[-3:].mean(0)            # (w, 3)
    left, right = src[:, :3].mean(1), src[:, -3:].mean(1)   # (h, 3)
    k = 31
    sm = lambda v: np.stack([np.convolve(np.pad(v[:, c], k // 2, mode='edge'), np.ones(k) / k, mode='valid') for c in range(3)], -1)
    top, bot, left, right = sm(top), sm(bot), sm(left), sm(right)
    ty = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    tx = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    vert = top[None] * (1 - ty) + bot[None] * ty
    horz = left[:, None] * (1 - tx) + right[:, None] * tx
    wy = np.minimum(ty, 1 - ty); wx = np.minimum(tx, 1 - tx)          # the nearer border weighs more
    base = (vert * (1 / (wy + 1e-3)) + horz * (1 / (wx + 1e-3))) / ((1 / (wy + 1e-3)) + (1 / (wx + 1e-3)))
    # grain: the donor patch minus its own blur
    dx0, dy0, dx1, dy1 = donor
    d = a[dy0:dy1, dx0:dx1].astype(np.float32)
    d = np.pad(d, ((0, max(0, h - d.shape[0])), (0, max(0, w - d.shape[1])), (0, 0)), mode='symmetric')[:h, :w]
    blur = np.asarray(Image.fromarray(d.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))).astype(np.float32)
    out = np.clip(base + (d - blur), 0, 255)
    # feather
    m = np.ones((h, w), np.float32)
    for i in range(FEATHER):
        f = (i + 1) / (FEATHER + 1)
        m[i, :] = np.minimum(m[i, :], f); m[-1 - i, :] = np.minimum(m[-1 - i, :], f)
        m[:, i] = np.minimum(m[:, i], f); m[:, -1 - i] = np.minimum(m[:, -1 - i], f)
    res = src * (1 - m[..., None]) + out * m[..., None]
    b = a.copy()
    b[y0:y1, x0:x1] = np.round(res).clip(0, 255).astype(np.uint8)
    return b


def main():
    check = '--check' in sys.argv
    bad = 0
    for rel, rect, donor, orig, done in JOBS:
        p = os.path.join(REPO, rel)
        h = sha(p)
        if h == done:
            print('already painted out:', rel)
            continue
        if check:
            print('NOT painted out:', rel, h[:12]); bad += 1
            continue
        if h != orig and '--force' not in sys.argv:
            print('unknown file version, not touched:', rel, h[:12]); bad += 1
            continue
        im = Image.open(p)
        assert im.mode == 'RGB', im.mode
        a = np.asarray(im)
        b = fill(a, rect, donor)
        ch = np.argwhere((a != b).any(-1))
        assert len(ch) and ch[:, 1].min() >= rect[0] and ch[:, 1].max() < rect[2] and ch[:, 0].min() >= rect[1] and ch[:, 0].max() < rect[3]
        Image.fromarray(b, 'RGB').save(p, optimize=False)
        print('painted out:', rel, 'rect', rect, 'changed px', len(ch), 'sha256', sha(p))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
