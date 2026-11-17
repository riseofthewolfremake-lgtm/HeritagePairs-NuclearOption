"""1.9.14 round 7: one label per control on the GA-25X radio head, no duplicate FREQ / MODE / BRT, no orphan scale arcs.

  python blender/ga25x/textures/relabel_art1914_r7.py [--backup-dir <dir>] [--sheet <png>] [--json <out.json>]

In-game review of round 6 (study ingame_1914\\r3\\shots\\5d_W_radio_zoom.png, 5d_W_rcons_zoomA/B.png, 5d_P_sub_zoom.png):
  radio (pedestal.png, radio crop y 1240-2528): each COMM side read big knob "VOL SQL" / small knobs "PWR TEST" (COMM 2 "TEST
  T/R+G") / toggles "PWR TEST" (COMM 2 "PWR T/R+G"): labels doubled and the two COMM sides disagreeing; an empty knob-scale arc
  sat ~22 mm above each big knob (no knob, no ticks, no label: an orphan the reviewer read as an offset VOL scale);
  right console: section heading "FREQ" over the knob labels "CHNL" / "FREQ" (FREQ twice);
  sub strip HUD panel: "MODE" and "BRT" painted above AND below their knobs.
Result (labels sit under their control on the radio, as the toggles already were; one label each):
  big knob = "FREQ" (frequency selector beside the frequency window), small knobs = "VOL" / "SQL", toggles = "PWR" / "TEST"
  (COMM 1) and "PWR" / "T/R+G" (COMM 2, unchanged); both arcs painted out; console_right heading "FREQ" painted out (the knob
  label FREQ stays); sub strip lower "MODE" and lower "BRT" painted out (the titles above the knobs stay).

Method (deterministic, no generated content, only pixels of the same art file):
  erase  = mask (text pixels L - plate > 40, or the dark arc stroke plate - L > 18, dilated 5 px) filled with the same file's
           plate at an offset (dx, dy) chosen from a fixed candidate grid: the shifted mask must hold no text / dark feature, best
           boundary match wins; the fill is brightness-matched by a plane fitted to the boundary-ring differences, 3 px feather.
  write  = a word / glyph CLONED from a label of the same art (same font, size, weight, paint wear): the glyph's own pixels minus
           its local plate level, added onto the erased plate inside the glyph's dilated mask, contrast scaled to the target
           row's labels. "F" of FREQ = the "E" of TEST with its bottom bar removed (no F at this size in the art); R from PWR,
           E from TEST, Q from SQL; letter gaps 4 px (the art's own gaps 3-5 px).
Sources: assets/textures_ga25x/fal_raw_cockpit/ edited IN PLACE; the first run copies each untouched file to
<backup-dir>/<name>_before_r7.png (= the round-6 output, commit 18524b9) and every later run starts from that copy (idempotent).
Order: paint_out_levers1914.py (round 6, restarts from *_before_r6.png) -> this script -> make_cockpit_art_ga25x.py (atlas)
-> make_ckart_emission1914.py (glow map). Re-running round 6 alone would drop these edits: re-run this script after it.
"""
import os, sys, json, shutil
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'assets', 'textures_ga25x', 'fal_raw_cockpit')
BACKUP = r'C:\Users\User\nuclearoption-ref\backups\art_1914'

# --------------------------------------------------------------------------------------------- measured on the art (raw px)
# word boxes (x0, y0, x1, y1) incl. a few px of plate, read with a text-pixel column projection (study r7\glyphs.py)
RADIO_Y = (1240, 2528)                                   # radio crop rows of pedestal.png
ROW_BIG, ROW_SMALL = (1943, 1984), (2169, 2208)          # label rows under the big knobs / under the small knobs (text rows)
KNOB_X = {'FREQ 1': 254, 'FREQ 2': 1442, 'VOL 1': 254, 'SQL 1': 441, 'VOL 2': 1255, 'SQL 2': 1445}   # = RADIO_CTRLS u x 1696
ERASE = {
    'pedestal.png': [('text', 'VOL 1 (under big knob)', (106, 1936, 206, 1992)), ('text', 'SQL 1 (under big knob)', (306, 1936, 403, 1994)),
                     ('text', 'VOL 2 (under big knob)', (1289, 1936, 1388, 1992)), ('text', 'SQL 2 (under big knob)', (1488, 1936, 1586, 1994)),
                     ('text', 'PWR 1 (under small knob)', (198, 2162, 309, 2216)), ('text', 'TEST 1 (under small knob)', (384, 2162, 504, 2216)),
                     ('text', 'TEST 2 (under small knob)', (1195, 2161, 1315, 2216)), ('text', 'T/R+G 2 (under small knob)', (1377, 2161, 1518, 2218)),
                     ('dark', 'COMM 1 arc', (164, 1585, 354, 1732), (161, 1580, 360, 1737)),
                     ('dark', 'COMM 2 arc', (1342, 1585, 1533, 1732), (1336, 1580, 1534, 1737))],   # 5th: clip (panel screws beside the arcs stay)
    'console_right.png': [('text', 'FREQ heading', (1996, 1104, 2146, 1171))],
    'subpanel_strip.png': [('text', 'HUD MODE (lower)', (298, 710, 480, 781)), ('text', 'HUD BRT (lower)', (590, 798, 699, 857))],
}
# glyph sources in pedestal.png (x0, x1 columns of the glyph, text rows of its word)
G = {'V': (115, 142, ROW_BIG), 'O': (145, 171, ROW_BIG), 'L': (177, 198, ROW_BIG),
     'S': (314, 337, ROW_BIG), 'Q': (342, 369, ROW_BIG), 'L2': (374, 395, ROW_BIG),
     'R': (277, 301, ROW_SMALL), 'E': (420, 441, ROW_SMALL)}
WORDS = {'VOL': ['V', 'O', 'L'], 'SQL': ['S', 'Q', 'L2'], 'FREQ': ['F', 'R', 'E', 'Q']}
GAP = 4
WRITE = [('FREQ', 'FREQ 1', ROW_BIG), ('FREQ', 'FREQ 2', ROW_BIG),
         ('VOL', 'VOL 1', ROW_SMALL), ('SQL', 'SQL 1', ROW_SMALL), ('VOL', 'VOL 2', ROW_SMALL), ('SQL', 'SQL 2', ROW_SMALL)]
TEXT_T, DARK_T, DIL, FEATHER = 40.0, 18.0, 5, 3.0


def lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def dilate(m, r):
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * r + 1))) > 127


def local_plate(L, box, pad=6):
    x0, y0, x1, y1 = box
    w = L[y0 - pad:y1 + pad, x0 - pad:x1 + pad]
    ring = np.concatenate([w[:pad].ravel(), w[-pad:].ravel(), w[:, :pad].ravel(), w[:, -pad:].ravel()])
    return float(np.median(ring))


def feature_map(a):
    """text (bright, unsaturated) or dark strokes / holes against the median plate (31 px median of a 1/4 downsample)."""
    L = lum(a)
    H, W = L.shape
    sm = np.asarray(Image.fromarray(L.astype(np.uint8)).resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.MedianFilter(9))
                    .resize((W, H), Image.BILINEAR)).astype(float)
    return (np.abs(L - sm) > 16) | (a.max(2) - a.min(2) > 30)


def erase(a, feat, mask, rng, name, log):
    """fill `mask` with plate of the same image at the best clean offset; plane brightness match on the boundary ring."""
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    ring = dilate(mask, 4) & ~mask
    ry, rx = np.nonzero(ring)
    H, W = feat.shape
    L = lum(a)
    best = None
    fy0, fy1 = rng
    ii = np.pad(feat.astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    bb = lambda X0, Y0, X1, Y1: ii[Y1, X1] - ii[Y0, X1] - ii[Y1, X0] + ii[Y0, X0]
    for dy in range(-200, 201, 4):
        for dx in range(-1400, 1401, 4):
            if abs(dx) < (x1 - x0) and abs(dy) < (y1 - y0):
                continue                                  # source must not overlap the hole
            if y0 + dy < fy0 or y1 + dy > fy1 or x0 + dx < 0 or x1 + dx > W:
                continue
            if bb(x0 + dx, y0 + dy, x1 + dx, y1 + dy) > 0.25 * (x1 - x0) * (y1 - y0):
                continue                                  # quick reject: busy area
            if feat[ys + dy, xs + dx].any() or feat[ry + dy, rx + dx].any():
                continue
            s = float(np.mean((L[ry + dy, rx + dx] - L[ry, rx]) ** 2)) + 0.002 * (dx * dx + 4 * dy * dy) ** 0.5
            if best is None or s < best[0]:
                best = (s, dx, dy)
    if best is None:
        raise SystemExit(f'{name}: no clean plate offset found')
    _, dx, dy = best
    out = a.copy()
    # plane fit (per channel) of target - source on the ring, applied to the fill
    A = np.stack([np.ones_like(rx, dtype=float), rx - rx.mean(), ry - ry.mean()], 1)
    fill = a[ys + dy, xs + dx].copy()
    for c in range(3):
        coef, *_ = np.linalg.lstsq(A, a[ry, rx, c] - a[ry + dy, rx + dx, c], rcond=None)
        fill[:, c] += coef[0] + coef[1] * (xs - rx.mean()) + coef[2] * (ys - ry.mean())
    # feather: weight 1 deep inside the mask, ramp to 0 over FEATHER px toward its edge (the mask is already dilated past the stroke)
    inner = mask.copy(); wgt = np.zeros(mask.shape)
    for k in range(int(FEATHER)):
        wgt[inner] += 1.0 / FEATHER
        inner = ~dilate(~inner, 1)
    wgt = np.clip(wgt, 0, 1)[ys, xs][:, None]
    out[ys, xs] = a[ys, xs] * (1 - wgt) + fill * wgt
    log.append(dict(name=name, pixels=int(mask.sum()), offset=[dx, dy], ring_rms=round(best[0] ** 0.5, 2), bbox=[int(x0), int(y0), int(x1), int(y1)]))
    return out


def glyph(src, key):
    """(delta image, mask) of one glyph: its pixels minus its word's plate level, inside the dilated text mask."""
    if key == 'F':
        d, m = glyph(src, 'E')
        L = d.mean(2)
        rows = np.nonzero((L > TEXT_T).sum(1))[0]
        stem = np.nonzero((L > TEXT_T).sum(0) > 0.8 * len(rows))[0]
        bot = rows.max()
        # bottom bar of the E: rows whose text spans past the stem, counted up from the glyph bottom
        k = bot
        while k > rows.min() and (L[k, stem.max() + 3:] > TEXT_T).any():
            k -= 1
        cut = np.zeros(m.shape, bool); cut[k + 1:, stem.max() + 2:] = True
        m = m & ~cut
        d = d * m[..., None]
        return d, m
    x0, x1, (r0, r1) = G[key]
    box = (x0 - 3, r0 - 6, x1 + 3, r1 + 8)              # rows + 8: room for the Q tail
    L = lum(src)
    bg = local_plate(L, (x0 - 2, r0 - 3, x1 + 2, r1 + 3), pad=4)
    w = src[box[1]:box[3], box[0]:box[2]] - bg
    m = dilate(lum(src[box[1]:box[3], box[0]:box[2]]) - bg > TEXT_T * 0.5, 2)
    return w * m[..., None], m


def text_contrast(src, row, xs):
    L = lum(src[row[0]:row[1], xs[0]:xs[1]])
    bg = local_plate(lum(src), (xs[0], row[0], xs[1], row[1]))
    return float(np.percentile(L[L - bg > TEXT_T], 90) - bg)


def write_word(a, src, word, cx, row, log, name):
    gl = [glyph(src, k) for k in WORDS[word]]
    ink = [np.nonzero(m.any(0))[0] for _, m in gl]
    widths = [int(i.max() - i.min() + 1) for i in ink]
    total = sum(widths) + GAP * (len(gl) - 1) - 4 * len(gl)   # each glyph mask carries 2 px of dilation per side
    x = int(round(cx - total / 2)) - 2
    tgt_c = text_contrast(src, row, (KNOB_X['VOL 1'] - 140, KNOB_X['SQL 1'] + 60)) if row == ROW_BIG else text_contrast(src, ROW_SMALL, (200, 500))
    out = a.copy()
    for k, ((d, m), i, wd) in enumerate(zip(gl, ink, widths)):
        key = WORDS[word][k]
        src_row = G['E' if key == 'F' else key][2]
        sc = tgt_c / text_contrast(src, src_row, (100, 500))
        d = d[:, i.min():i.max() + 1] * sc; m = m[:, i.min():i.max() + 1]
        top = row[0] - 6
        h = d.shape[0]
        sl = out[top:top + h, x:x + d.shape[1]]
        sl += d * m[..., None]
        x += wd + GAP - 4
    log.append(dict(name=name, word=word, centre_x=cx, row=list(row), width_px=total))
    return np.clip(out, 0, 255)


def main():
    bdir = sys.argv[sys.argv.index('--backup-dir') + 1] if '--backup-dir' in sys.argv else BACKUP
    os.makedirs(bdir, exist_ok=True)
    log = []
    before = {}
    for fn, items in ERASE.items():
        p, bk = os.path.join(SRC, fn), os.path.join(bdir, fn.replace('.png', '_before_r7.png'))
        if not os.path.exists(bk):
            shutil.copy2(p, bk)
        src = np.asarray(Image.open(bk).convert('RGB')).astype(float)
        before[fn] = src
        a = src.copy()
        feat = feature_map(src)
        L = lum(src)
        rng = RADIO_Y if fn == 'pedestal.png' else (0, src.shape[0])
        for kind, name, (x0, y0, x1, y1), *clip in items:
            box = np.zeros(L.shape, bool); box[y0:y1, x0:x1] = True
            bg = local_plate(L, (x0, y0, x1, y1))
            core = box & ((L - bg > TEXT_T) if kind == 'text' else (bg - L > DARK_T))
            mask = dilate(core, DIL) & dilate(box, DIL)
            if clip:
                cb = np.zeros(L.shape, bool); cb[clip[0][1]:clip[0][3], clip[0][0]:clip[0][2]] = True
                mask &= cb
            a = erase(a, feat, mask, rng, f'{fn}: {name}', log)
        if fn == 'pedestal.png':
            for word, key, row in WRITE:
                a = write_word(a, src, word, KNOB_X[key], row, log, f'{fn}: {word} under {key.split()[0] if word != "FREQ" else "big knob"} {key[-1]}')
        Image.fromarray(np.clip(np.round(a), 0, 255).astype(np.uint8)).save(p)
        ch = np.abs(a - src).max(2) > 3
        log.append(dict(file=fn, changed_px=int(ch.sum())))
    for r in log:
        print('[relabel_r7]', r)
    if '--json' in sys.argv:
        json.dump(log, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
    if '--sheet' in sys.argv:                            # before | after crops of every edited area
        crops = [('pedestal.png', (40, 1500, 1660, 2440)), ('console_right.png', (1700, 1050, 2420, 1500)), ('subpanel_strip.png', (40, 120, 960, 900))]
        tiles = []
        for fn, (x0, y0, x1, y1) in crops:
            b = Image.fromarray(before[fn][y0:y1, x0:x1].astype(np.uint8))
            n = Image.open(os.path.join(SRC, fn)).convert('RGB').crop((x0, y0, x1, y1))
            t = Image.new('RGB', (b.width * 2 + 10, b.height), (255, 0, 255)); t.paste(b, (0, 0)); t.paste(n, (b.width + 10, 0))
            tiles.append(t.resize((1400, int(1400 * t.height / t.width))))
        sh = Image.new('RGB', (1400, sum(t.height + 10 for t in tiles)), (255, 0, 255))
        y = 0
        for t in tiles:
            sh.paste(t, (0, y)); y += t.height + 10
        sh.save(sys.argv[sys.argv.index('--sheet') + 1])


if __name__ == '__main__':
    main()
