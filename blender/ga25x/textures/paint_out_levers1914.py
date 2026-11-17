"""1.9.14 round 6: paint the toggle LEVERS out of the GA-25X fal panel art wherever a modelled lever stands on the painted switch.

  python blender/ga25x/textures/paint_out_levers1914.py [--backup-dir <dir>] [--sheet <png>] [--json <out.json>]

Verifier round 5: from the crew eye the modelled toggle lever AND the painted lever (with its rounded tip and cast shadow) were
both seen ("doubled levers"). The art now keeps the plate, labels and the switch bezel / nut only; the lever is the 3D model.

Method (deterministic, local, no generated content): every painted switch bezel / nut here is mirror-symmetric about its own
horizontal centre line (oval console bezels, round radio / gear bezels, hex sub-strip nuts), and the painted lever runs from the
bezel centre straight down ('dn') or up ('up') the panel. Mask = the lever-side half of the bezel + a capsule over the lever and
its soft cast shadow (measured per switch family). Inside the bezel the fill is the mirror image of the clean other half of the
same bezel; on the plate beyond it the fill is the same rows of plate D px to the side, brightness-matched to the untouched plate
round the mask (inverse-distance interpolation of the boundary differences); feathered over 4 px. The centre of each bezel is
found on the art itself (left / right mirror match above the lever, up / down mirror match beside it, +-24 px around the
measured table position), so the mirrored bezel half lands on its own outline.

Sources: the files in assets/textures_ga25x/fal_raw_cockpit/ are edited IN PLACE; the first run copies each untouched file to
<backup-dir>/<name>_before_r6.png and every later run starts from that copy (idempotent: running twice = running once).
Afterwards: make_cockpit_art_ga25x.py (atlas) and make_ckart_emission1914.py (glow map).
"""
import os, sys, json, shutil
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'assets', 'textures_ga25x', 'fal_raw_cockpit')
BACKUP = r'C:\Users\User\nuclearoption-ref\backups\art_1914'

# switch families, px of their own raw file (measured on zoomed crops, study tex_1914\ga25x_cockpit\r6\zz_*.png):
#   lw    painted lever half width (centre search: columns |dx| in [lw + 6, r] beside the lever, rows above it for x)
#   w     half width of the mask capsule (lever + its soft cast shadow); tip = farthest px of lever + shadow from the bezel centre
#         along the lever (the capsule ends there); shadow = px the cast shadow lies to the right (art lit from the upper left)
#   bez   (half width, half height) of the bezel / nut incl. its dark outline: inside it the fill is the bezel's own mirror image
#         (the whole lever-side half, so the bezel stays symmetric); outside it (plate) the fill is the plate D px to the side
FAM = {
    'oval':  dict(lw=30, r=66, w=36, tip=126, shadow=8, bez=(70, 88), D=100),   # console_left: FUEL PUMP, X-FEED, ANTI-SKID, NWS, IGN, DE-ICE, BATT
    'gear':  dict(lw=30, r=80, w=34, tip=88, shadow=4, bez=(80, 80), D=96),     # console_left GEAR (knurled round bezel, lever UP)
    'radio': dict(lw=22, r=52, w=26, tip=70, shadow=4, bez=(60, 60), D=76),     # pedestal.png radio crop: PWR 1, TEST 1, PWR 2, T/R+G 2
    'sub':   dict(lw=28, r=80, w=34, tip=128, shadow=6, bez=(92, 92), D=100),   # subpanel_strip.png: LDG LT, TAXI LT, STBY INST (hex nut)
}
CLONE_RIGHT = {'DE-ICE', 'LDG LT'}   # plate clone from the right (DE-ICE: panel divider line on its left; LDG LT: guard bar); others from the left
# (file, panel art box in the file), switch, family, direction, painted (u, v) over the panel art as in ga25x_cockpit.py
CL = ('console_left.png', (0, 0, 2528, 1696))
RAD = ('pedestal.png', (0, 1240, 1696, 2528))
SUB = ('subpanel_strip.png', (0, 0, 4128, 1024))
SWITCHES = [(CL, n, 'oval', 'dn', u, v) for n, u, v in (
                ('FUEL PUMP L', 0.1585, 0.500), ('FUEL PUMP R', 0.3265, 0.500), ('X-FEED', 0.496, 0.500), ('ANTI-SKID', 0.669, 0.497),
                ('NWS', 0.836, 0.497), ('IGN', 0.324, 0.182), ('DE-ICE', 0.805, 0.177), ('BATT', 0.8956, 0.177))]
SWITCHES += [(CL, 'GEAR', 'gear', 'up', 0.5006, 0.775)]
SWITCHES += [(RAD, n, 'radio', 'dn', u, 0.190) for n, u in (('PWR 1', 0.150), ('TEST 1', 0.260), ('PWR 2', 0.740), ('T/R+G 2', 0.852))]
SWITCHES += [(SUB, n, 'sub', 'dn', u, v) for n, u, v in (('LDG LT', 0.518, 0.506), ('TAXI LT', 0.586, 0.506), ('STBY INST', 0.683, 0.506))]
FEATHER = 4.0


def lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def find_centre(L, x0, y0, f, sgn):
    """bezel centre near (x0, y0): x from a left/right mirror match on the rows on the far side of the lever, y from an up/down
    mirror match on the columns beside the lever."""
    w, r = f['lw'], f['r']
    best = None
    for cx in range(x0 - 24, x0 + 25):
        ys = np.arange(y0 - r, y0 - 8) if sgn > 0 else np.arange(y0 + 8, y0 + r)
        dx = np.arange(4, r)
        a = L[np.ix_(ys, cx + dx)]; b = L[np.ix_(ys, cx - dx)]
        e = float(np.mean((a - b) ** 2))
        if best is None or e < best[0]:
            best = (e, cx)
    cx = best[1]
    best = None
    dx = np.concatenate([np.arange(-r, -w - 6), np.arange(w + 6, r)])
    for cy in range(y0 - 24, y0 + 25):
        dy = np.arange(3, int(r * 0.9))
        a = L[np.ix_(cy + dy, cx + dx)]; b = L[np.ix_(cy - dy, cx + dx)]
        e = float(np.mean((a - b) ** 2))
        if best is None or e < best[0]:
            best = (e, cy)
    return cx, best[1]


def masks(shape, c, f, sgn):
    """(M, E, BZ) on a window centred on the bezel centre (c, c): M = capsule along the lever (sgn +1 = down the image) from the
    centre row to the tip + its cast shadow, united with E = the lever-side half of the bezel ellipse. Both feathered (1 inside,
    0 beyond FEATHER px) and zero on the far side of the centre row (where the mirror source is)."""
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = (yy - c) * sgn                                    # px along the lever
    tc = np.clip(t, 0.0, f['tip'] - f['w'])
    d = np.minimum(np.hypot(xx - c, t - tc), np.hypot(xx - (c + f['shadow']), t - tc)) - f['w']
    bx, by = f['bez']
    de = (np.hypot((xx - c) / bx, t / by) - 1.0) * min(bx, by)     # ~px outside the ellipse
    side = (t >= 0).astype(np.float32)
    E = np.clip(1.0 - de / FEATHER, 0.0, 1.0) * side
    M = np.maximum(np.clip(1.0 - d / FEATHER, 0.0, 1.0) * side, E)
    return M, E, de < FEATHER                             # + the whole bezel (both halves): no brightness-match samples there


def grow(b, n):
    for _ in range(n):
        g = b.copy()
        g[1:] |= b[:-1]; g[:-1] |= b[1:]; g[:, 1:] |= b[:, :-1]; g[:, :-1] |= b[:, 1:]
        b = g
    return b


def shepard(py, px, val, qy, qx):
    """inverse-distance-squared interpolation of the boundary differences at the query pixels (low-frequency brightness match)."""
    w = 1.0 / ((qy[:, None] - py[None, :]) ** 2 + (qx[:, None] - px[None, :]) ** 2 + 1.0)
    return (w @ val) / w.sum(1)[:, None]


def paint_out(img, name, f, cx, cy, sgn):
    R = max(f['tip'], f['bez'][1]) + 12
    ya, yb, xa, xb = cy - R, cy + R + 1, cx - R, cx + R + 1
    win = img[ya:yb, xa:xb].copy()
    M, E, BZ = masks(win.shape[:2], R, f, sgn)
    mir = win[::-1]                                       # mirror about the window centre row = cy
    D = f['D'] * (1 if name in CLONE_RIGHT else -1)
    clo = img[ya:yb, xa + D:xb + D].copy()                # plate D px to the side, same rows
    inside = M > 0
    ring = grow(inside, 3) & ~inside & ~grow(BZ, 6)    # untouched plate just round the mask, off the bezel outline
    ry, rx = [a.astype(np.float32) for a in np.nonzero(ring)]
    qyi, qxi = np.nonzero(inside & (E < 1))
    if len(ry) and len(qyi):
        diff = win[ry.astype(int), rx.astype(int)] - clo[ry.astype(int), rx.astype(int)]
        clo[qyi, qxi] += shepard(ry, rx, diff, qyi.astype(np.float32), qxi.astype(np.float32))
    fill = mir * E[..., None] + clo * (1 - E[..., None])
    img[ya:yb, xa:xb] = win * (1 - M[..., None]) + fill * M[..., None]
    return D, (xa, ya, xb, yb)


def main():
    a = sys.argv
    bdir = a[a.index('--backup-dir') + 1] if '--backup-dir' in a else BACKUP
    os.makedirs(bdir, exist_ok=True)
    rec, files = [], {}
    for (fn, box), name, fam, dirn, u, v in SWITCHES:
        if fn not in files:
            bk = os.path.join(bdir, fn.replace('.png', '_before_r6.png'))
            if not os.path.exists(bk):
                shutil.copy2(os.path.join(SRC, fn), bk)
            files[fn] = np.asarray(Image.open(bk).convert('RGB')).astype(np.float32)
        img = files[fn]
        f = FAM[fam]
        sgn = 1 if dirn == 'dn' else -1
        bx0, by0, bx1, by1 = box
        x0 = int(round(bx0 + u * (bx1 - bx0))); y0 = int(round(by0 + (1 - v) * (by1 - by0)))
        cx, cy = find_centre(lum(img), x0, y0, f, sgn)
        D, win = paint_out(img, name, f, cx, cy, sgn)
        hx = max(f['w'] + f['shadow'], f['bez'][0]) + FEATHER
        hy = max(f['tip'], f['bez'][1]) + FEATHER
        rec.append(dict(file=fn, switch=name, family=fam, dir=dirn, table_px=[x0, y0], centre_px=[cx, cy], clone_dx=D,
                        mask_box_px=[int(cx - hx), int(min(cy, cy + sgn * hy)), int(cx + hx), int(max(cy, cy + sgn * hy))],
                        lever_box_px=[int(cx - f['lw']), int(min(cy, cy + sgn * (f['tip'] - 10))), int(cx + f['lw']),
                                      int(max(cy, cy + sgn * (f['tip'] - 10)))]))
        print(f'[levers] {fn:20s} {name:12s} table ({x0}, {y0}) -> bezel centre ({cx}, {cy}), plate clone dx {D}')
    for fn, img in files.items():
        Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8)).save(os.path.join(SRC, fn), optimize=True)
        print('[levers] wrote', fn)
    if '--json' in a:
        json.dump(rec, open(a[a.index('--json') + 1], 'w'), indent=1)
    if '--sheet' in a:
        tiles = []
        for r_ in rec:
            bk = Image.open(os.path.join(bdir, r_['file'].replace('.png', '_before_r6.png'))).convert('RGB')
            nw = Image.open(os.path.join(SRC, r_['file'])).convert('RGB')
            cx, cy = r_['centre_px']
            bb = (cx - 150, cy - 150, cx + 150, cy + 150)
            t = Image.new('RGB', (600, 300)); t.paste(bk.crop(bb), (0, 0)); t.paste(nw.crop(bb), (300, 0)); tiles.append(t)
        sh = Image.new('RGB', (1200, 300 * ((len(tiles) + 1) // 2)))
        for k, t in enumerate(tiles):
            sh.paste(t, ((k % 2) * 600, (k // 2) * 300))
        sh.save(a[a.index('--sheet') + 1])


if __name__ == '__main__':
    main()
