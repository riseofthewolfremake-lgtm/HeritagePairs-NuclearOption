"""Nimrod cockpit art (plain Python: PIL + numpy). Our own art; nothing copied from the photos.

2026-11-02 rebuild (user review 1: cockpit art through fal too): every cockpit tile is now a fal texture
(assets/textures_nimrod/fal_raw: ck_paint, ck_crinkle, ck_leather, ck_floor, ck_alu, ck_canvas, tube_steel, rubber, prop_wood,
alu_polished, fabric_inside; fal-ai/z-image/turbo/tiling), tone-matched to the v2 material colours; the v2 procedural wear (chips,
scuffs) is kept on top as a light overlay. The panel faces / seat skin of the ck_art atlas are built from these tiles, so they are
fal-based too. Also writes each fal 3D prop's own baked textures (nimrod_pr_<key>_b / _n) from its optimised GLB.

  python blender/nimrod/textures/make_cockpit_art_nimrod.py [--out assets/textures_nimrod]

Writes (all tileable tiles are 1024 px; detail UV = 2 m per unit, scaled per material by nimrod_ck_layout.TILE_SCALE):
  nimrod_tile_<ck_*>_b.png / _n.png   worn grey paint, black crinkle, brass, black leather, wood, red-brown floor, aluminium,
                                       painted tube, canvas webbing, red-orange paint, fabric lining, rubber cord
  nimrod_gauges.png                    2048 dial atlas (8 x 8 cells, big dials 2 x 2): period RAF faces with readable scales,
                                       rims, needles, compass card (layout: nimrod_ck_layout.GAUGE_CELLS / DIALS)
  nimrod_ckart_b.png / _n.png          2048 cockpit atlas: lower panel + raised section faces (paint, edge wear, screws, stencils),
                                       riveted seat skin, placards / data plates / cards, ammo counter, breech rear plate
Normal maps: OpenGL convention (+Y = +v), as the rest of the project.
"""
import os, sys, math, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..'))
import nimrod_ck_layout as L

argv = sys.argv[1:]
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_nimrod')
os.makedirs(OUT, exist_ok=True)
F32 = np.float32
FONT_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')


def font(name, px):
    for n in (name, 'arialbd.ttf', 'arial.ttf'):
        p = os.path.join(FONT_DIR, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, max(6, int(px)))
    return ImageFont.load_default()


def log(*a):
    print('[ckart]', *a, flush=True)


# =========================================================================================== noise / normals
def pnoise(n, freq, seed, octaves=1, gain=0.5):
    """tileable value noise (cosine-interpolated random lattice with wrap), 0..1."""
    rng = np.random.default_rng(seed)
    out = np.zeros((n, n), F32); amp = 1.0; tot = 0.0; f = freq
    for _ in range(octaves):
        g = rng.random((f, f)).astype(F32)
        t = (np.arange(n, dtype=F32) + 0.5) * f / n
        i0 = np.floor(t).astype(int) % f; i1 = (i0 + 1) % f
        w = t - np.floor(t); w = (1 - np.cos(w * np.pi)) / 2
        a = g[i0][:, i0] * (1 - w)[None, :] + g[i0][:, i1] * w[None, :]
        b = g[i1][:, i0] * (1 - w)[None, :] + g[i1][:, i1] * w[None, :]
        out += amp * (a * (1 - w)[:, None] + b * w[:, None]); tot += amp
        amp *= gain; f *= 2
    return out / tot


def cells(n, k, seed):
    """tileable jittered-grid Worley distance (F1), ~k cells, normalised 0..1."""
    g = max(2, int(round(math.sqrt(k))))
    rng = np.random.default_rng(seed)
    jit = rng.random((g, g, 2)).astype(F32)
    cs = n / g
    yy, xx = np.mgrid[0:n, 0:n].astype(F32)
    gx, gy = (xx / cs).astype(int), (yy / cs).astype(int)
    d = np.full((n, n), 1e9, F32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx, cy = gx + ox, gy + oy
            j = jit[cy % g, cx % g]
            px = (cx + j[..., 0]) * cs; py = (cy + j[..., 1]) * cs
            d = np.minimum(d, (xx - px) ** 2 + (yy - py) ** 2)
    d = np.sqrt(d)
    return d / d.max()


def normal_from_height(h, strength, wrap=True):
    if wrap:
        dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
        dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * 0.5      # +v = up = row - 1
    else:
        hp = np.pad(h, 1, mode='edge')
        dx = (hp[1:-1, 2:] - hp[1:-1, :-2]) * 0.5
        dy = (hp[:-2, 1:-1] - hp[2:, 1:-1]) * 0.5
    nx, ny = -dx * strength, -dy * strength
    nz = np.ones_like(h)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.dstack([nx / l, ny / l, nz / l])


def save_rgb(arr, name):
    a = np.clip(arr, 0, 1)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8), 'RGB').save(os.path.join(OUT, name + '.png'), optimize=True)


def save_n(nrm, name):
    save_rgb(nrm * 0.5 + 0.5, name)


def lerp3(a, b, t):
    return a * (1 - t[..., None]) + np.asarray(b, F32) * t[..., None]


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# =========================================================================================== tiles
def tiles():
    n = 1024
    yy, xx = np.mgrid[0:n, 0:n].astype(F32) / n
    res = {}
    # worn grey paint (panel edges, quadrant body): orange peel, chips to alu + zinc-chromate primer, grime
    peel = pnoise(n, 64, 1, 2)
    big = pnoise(n, 6, 2, 4)
    chip = pnoise(n, 24, 3, 3)
    chips = sstep(0.76, 0.79, chip * 0.7 + big * 0.3)
    prim = sstep(0.73, 0.76, chip * 0.7 + big * 0.3) - chips
    base = np.asarray((0.50, 0.52, 0.53), F32) * (0.95 + 0.08 * big[..., None]) * (0.98 + 0.03 * peel[..., None])
    col = lerp3(base, (0.56, 0.58, 0.44), np.clip(prim, 0, 1) * 0.45)
    col = lerp3(col, (0.64, 0.65, 0.66), chips * 0.7)
    col *= (1 - 0.18 * sstep(0.55, 0.9, pnoise(n, 3, 4, 3)))[..., None]
    res['ck_paint'] = (col, peel * 0.15 - chips * 0.6 - prim * 0.2, 2.5)
    # black crinkle finish
    w1 = np.abs(pnoise(n, 96, 5, 2) - 0.5) * 2
    w2 = np.abs(pnoise(n, 160, 6, 2) - 0.5) * 2
    cr = 1 - (w1 * 0.6 + w2 * 0.4)
    wear = sstep(0.78, 0.84, pnoise(n, 10, 7, 3))
    col = np.dstack([0.040 + 0.020 * cr] * 3) * np.asarray((1.0, 1.0, 1.06), F32)
    col = lerp3(col, (0.16, 0.16, 0.17), wear * 0.7)
    res['ck_crinkle'] = (col, cr * 1.0, 6.0)
    # brass: hammered + polish streaks + tarnish patches
    ham = pnoise(n, 48, 8, 2)
    tarn = sstep(0.55, 0.75, pnoise(n, 8, 9, 4))
    streak = pnoise(n, 4, 10, 1)[:, :1] * 0 + np.sin(yy * 2 * np.pi * 90 + pnoise(n, 6, 11, 2) * 9) * 0.5 + 0.5
    col = np.asarray((0.78, 0.58, 0.25), F32) * (0.88 + 0.16 * ham[..., None]) * (0.96 + 0.06 * streak[..., None])
    col = lerp3(col, (0.36, 0.30, 0.15), tarn * 0.7)
    res['ck_brass'] = (col, ham * 0.4 + streak * 0.05, 2.0)
    # black leather: grain cells + creases + scuffs
    grain = cells(n, 2600, 12)
    crease = np.abs(pnoise(n, 12, 13, 3) - 0.5) < 0.012
    scuff = sstep(0.68, 0.85, pnoise(n, 14, 14, 3))
    col = np.dstack([0.030 + 0.020 * grain] * 3) * np.asarray((1.05, 1.0, 0.95), F32)
    col = lerp3(col, (0.10, 0.085, 0.07), scuff * 0.5)
    col[crease] *= 0.6
    res['ck_leather'] = (col, grain * 0.8 - crease * 0.15, 1.8)
    # wood (footboards, knobs): straight grain along u, growth rings, worn varnish
    g = np.sin((yy * 60 + pnoise(n, 6, 15, 3) * 5) * 2 * np.pi) * 0.5 + 0.5
    fine = pnoise(n, 256, 16, 1)
    worn = sstep(0.6, 0.8, pnoise(n, 5, 17, 3))
    col = np.asarray((0.34, 0.18, 0.08), F32) * (0.80 + 0.30 * g[..., None]) * (0.95 + 0.08 * fine[..., None])
    col = lerp3(col, (0.52, 0.38, 0.22), worn * 0.45)
    res['ck_wood'] = (col, g * 0.3 + fine * 0.1, 2.0)
    # floor: dark red-brown dope over plywood / fabric, boot scuffs, dirt
    weave = (np.sin(xx * 2 * np.pi * 220) * np.sin(yy * 2 * np.pi * 220)) * 0.5 + 0.5
    dirt = pnoise(n, 5, 18, 4)
    scuff = sstep(0.62, 0.80, pnoise(n, 9, 19, 3) * 0.6 + pnoise(n, 40, 20, 2) * 0.4)
    col = np.asarray((0.24, 0.075, 0.065), F32) * (0.85 + 0.25 * dirt[..., None]) * (0.95 + 0.06 * weave[..., None])
    col = lerp3(col, (0.33, 0.22, 0.17), scuff * 0.6)
    res['ck_floor'] = (col, weave * 0.2 - scuff * 0.2, 2.0)
    # aluminium: brushed along u, scratches
    br = pnoise(n, 4, 21, 1)[:1, :] * 0 + pnoise(n, 512, 22, 1).mean(axis=1, keepdims=True) * np.ones((1, n), F32)
    scr = np.zeros((n, n), F32)
    rng = np.random.default_rng(23)
    for _ in range(140):
        x0, y0 = rng.random(2) * n; a = rng.random() * np.pi; L_ = 20 + rng.random() * 160
        t = np.linspace(0, 1, int(L_))
        xs = ((x0 + np.cos(a) * L_ * t) % n).astype(int); ys = ((y0 + np.sin(a) * L_ * t) % n).astype(int)
        scr[ys, xs] = 1
    blot = pnoise(n, 7, 24, 3)
    col = np.asarray((0.66, 0.67, 0.69), F32) * (0.90 + 0.12 * br[..., None]) * (0.92 + 0.10 * blot[..., None])
    col = lerp3(col, (0.82, 0.83, 0.85), scr * 0.6)
    res['ck_alu'] = (col, br * 0.2 - scr * 0.3, 1.5)
    # painted steel tube (frame): satin black-grey with chips to steel
    c2 = pnoise(n, 30, 25, 3)
    chips = sstep(0.80, 0.83, pnoise(n, 60, 25, 3))
    col = np.asarray((0.085, 0.088, 0.09), F32) * (0.9 + 0.2 * pnoise(n, 8, 26, 3)[..., None])
    col = lerp3(col, (0.24, 0.24, 0.23), chips * 0.8)
    res['ck_tube'] = (col, -chips * 0.5, 2.0)
    # canvas webbing: twill weave, khaki
    tw = (np.sin((xx + yy) * 2 * np.pi * 180) * 0.5 + 0.5) * 0.6 + (np.sin(xx * 2 * np.pi * 360) * 0.5 + 0.5) * 0.4
    col = np.asarray((0.50, 0.45, 0.32), F32) * (0.80 + 0.25 * tw[..., None]) * (0.9 + 0.15 * pnoise(n, 6, 27, 3)[..., None])
    res['ck_canvas'] = (col, tw * 0.5, 3.0)
    # red-orange paint (trim wheel), chips to dark metal, hand wear
    c3 = pnoise(n, 20, 28, 3)
    chips = sstep(0.80, 0.83, pnoise(n, 40, 28, 3))
    col = np.asarray((0.78, 0.25, 0.08), F32) * (0.92 + 0.12 * pnoise(n, 6, 29, 3)[..., None])
    col = lerp3(col, (0.12, 0.10, 0.09), chips)
    res['ck_red'] = (col, -chips * 0.5 + peel * 0.1, 2.0)
    # fabric lining (interior side of the doped skin): dark grey-green, weave, rib-tape shadows every ~0.13 m
    weave2 = (np.sin(xx * 2 * np.pi * 300) + np.sin(yy * 2 * np.pi * 300)) * 0.25 + 0.5
    rib = np.exp(-((((xx * 4) % 1) - 0.5) / 0.04) ** 2)
    col = np.asarray((0.105, 0.115, 0.105), F32) * (0.85 + 0.2 * pnoise(n, 5, 30, 3)[..., None]) * (0.96 + 0.06 * weave2[..., None])
    col *= (1 - 0.25 * rib)[..., None]
    res['ck_lining'] = (col, weave2 * 0.1 + rib * 0.6, 2.0)
    # rubber cord wrap: diagonal ridges
    rr = np.sin((xx * 3 + yy) * 2 * np.pi * 70) * 0.5 + 0.5
    col = np.dstack([0.035 + 0.025 * rr] * 3)
    res['ck_rubber'] = (col, rr, 3.0)
    # ---- fal base for every tile: the fal texture re-centred on the v2 colour, the v2 procedural wear blended on top (25 %)
    FALMAP = {'ck_paint': ('ck_paint', 1.0), 'ck_crinkle': ('ck_crinkle', 1.0), 'ck_leather': ('ck_leather', 1.0), 'ck_floor': ('ck_floor', 1.0),
              'ck_alu': ('ck_alu', 1.0), 'ck_canvas': ('ck_canvas', 1.0), 'ck_tube': ('tube_steel', 1.2), 'ck_rubber': ('rubber', 1.5),
              'ck_wood': ('prop_wood', 1.0), 'ck_brass': ('alu_polished', 1.3), 'ck_red': ('ck_paint', 1.2), 'ck_lining': ('fabric_inside', 0.6)}
    for k, (src, con) in FALMAP.items():
        if k not in res:
            continue
        col, hgt, st = res[k]
        fa = np.asarray(Image.open(os.path.join(ROOT, 'assets', 'textures_nimrod', 'fal_raw', src + '.png')).convert('RGB').resize((n, n), Image.LANCZOS)).astype(F32) / 255.0
        m_f = fa.reshape(-1, 3).mean(0); m_c = col.reshape(-1, 3).mean(0)
        base = np.clip((fa - m_f) * con + m_c, 0, 1)
        res[k] = (base * 0.75 + col * 0.25, (fa.mean(-1) - fa.mean()) / (fa.std() + 1e-6) * 0.25 + hgt * 0.5, st)
    log('tiles: fal base', ', '.join(f'{k}<-{v[0]}' for k, v in FALMAP.items()))
    for k, (col, hgt, s) in res.items():
        save_rgb(col, f'nimrod_tile_{k}_b')
        save_n(normal_from_height(hgt.astype(F32), s), f'nimrod_tile_{k}_n')
    log('tiles', len(res))
    return res


# =========================================================================================== dial faces
CREAM = (232, 226, 200)
LUM = (214, 222, 182)          # luminous paint (pale green-cream)
FACE = (14, 14, 14)


def pol(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def dial_face(S, spec):
    """paint one dial face (S x S px, supersampled) -> RGB array. spec keys: zero, sweep, v0, v1, major, minor, labels, title, sub,
    lum (luminous dots), needle (decor needle value), kind."""
    im = Image.new('RGB', (S, S), FACE)
    d = ImageDraw.Draw(im)
    c = S / 2; R = S / 2 * 0.96
    kind = spec.get('kind', 'scale')
    # faint face texture + darker rim (painted)
    d.ellipse([c - R, c - R, c + R, c + R], fill=FACE)
    d.ellipse([c - R, c - R, c + R, c + R], outline=(40, 40, 40), width=max(1, int(S * 0.012)))
    fnt = 'bahnschrift.ttf'
    if kind == 'scale':
        z, sw, v0, v1 = spec['zero'], spec['sweep'], spec['v0'], spec['v1']
        def ang(v):
            return z + (v - v0) / (v1 - v0) * sw
        def ticks(step, r0, r1, w, col):
            v = v0
            while v <= v1 + 1e-6:
                a = ang(v)
                d.line([pol(c, c, R * r0, a), pol(c, c, R * r1, a)], fill=col, width=max(1, int(w * S)))
                v += step
        if spec.get('minor'):
            ticks(spec['minor'], 0.84, 0.93, 0.008, CREAM)
        ticks(spec['major'], 0.74, 0.93, 0.016, CREAM)
        if spec.get('arc'):
            a0, a1 = ang(v0), ang(v1)
            bb = [c - R * 0.935, c - R * 0.935, c + R * 0.935, c + R * 0.935]
            d.arc(bb, a0 - 90, a1 - 90, fill=CREAM, width=max(1, int(S * 0.006)))
        if spec.get('red'):           # red limit mark
            a = ang(spec['red'])
            d.line([pol(c, c, R * 0.70, a), pol(c, c, R * 0.95, a)], fill=(190, 40, 30), width=max(2, int(0.022 * S)))
        fs = spec.get('fs', 0.15)
        f = font(fnt, S * fs)
        for v, txt in spec['labels']:
            x, y = pol(c, c, R * spec.get('lr', 0.56), ang(v))
            d.text((x, y), txt, fill=CREAM, font=f, anchor='mm')
            if spec.get('lum'):
                xd, yd = pol(c, c, R * 0.97 - S * 0.02, ang(v))
        if spec.get('lum'):
            v = v0
            while v <= v1 + 1e-6:
                xd, yd = pol(c, c, R * 0.885, ang(v))
                rr = S * 0.012
                d.ellipse([xd - rr, yd - rr, xd + rr, yd + rr], fill=LUM)
                v += spec['major']
    elif kind == 'turn':
        for a in (-30, 0, 30):
            d.line([pol(c, c, R * 0.70, a), pol(c, c, R * 0.93, a)], fill=CREAM, width=int(0.022 * S))
        for a in (-15, 15):
            d.line([pol(c, c, R * 0.80, a), pol(c, c, R * 0.93, a)], fill=CREAM, width=int(0.010 * S))
        f = font(fnt, S * 0.16)
        d.text(pol(c, c, R * 0.58, -55), 'L', fill=CREAM, font=f, anchor='mm')
        d.text(pol(c, c, R * 0.58, 55), 'R', fill=CREAM, font=f, anchor='mm')
        # slip ball tube (glass arc at the bottom: the ball mover rides at r 0.62)
        bb = [c - R * 0.62, c - R * 0.62, c + R * 0.62, c + R * 0.62]
        d.arc(bb, 90 - 36, 90 + 36, fill=(150, 146, 120), width=int(S * 0.16))
        d.arc(bb, 90 - 36, 90 + 36, fill=(205, 200, 170), width=int(S * 0.12))
        for a in (-9, 9):
            x0, y0 = pol(c, c, R * 0.52, 180 + a); x1, y1 = pol(c, c, R * 0.72, 180 + a)
            d.line([(x0, y0), (x1, y1)], fill=(20, 20, 20), width=int(S * 0.010))
    elif kind == 'compass':
        im.paste((206, 196, 160), [0, 0, S, S])
        d.ellipse([c - R, c - R, c + R, c + R], fill=(206, 196, 160))
        for k in range(0, 360, 5):
            r0 = 0.84 if k % 10 else (0.76 if k % 30 else 0.70)
            d.line([pol(c, c, R * r0, k), pol(c, c, R * 0.95, k)], fill=(20, 20, 20), width=max(1, int(S * (0.010 if k % 30 == 0 else 0.004))))
        f = font(fnt, S * 0.13); f2 = font(fnt, S * 0.075)
        for k, t in ((0, 'N'), (90, 'E'), (180, 'S'), (270, 'W')):
            d.text(pol(c, c, R * 0.55, k), t, fill=(150, 20, 15) if t == 'N' else (20, 20, 20), font=f, anchor='mm')
        for k in (30, 60, 120, 150, 210, 240, 300, 330):
            d.text(pol(c, c, R * 0.58, k), str(k // 10), fill=(20, 20, 20), font=f2, anchor='mm')
        d.ellipse([c - R * 0.06, c - R * 0.06, c + R * 0.06, c + R * 0.06], fill=(40, 40, 40))
    elif kind == 'clock':
        for k in range(60):
            a = k * 6
            w = 0.016 if k % 5 == 0 else 0.006
            d.line([pol(c, c, R * (0.78 if k % 5 == 0 else 0.86), a), pol(c, c, R * 0.93, a)], fill=CREAM, width=max(1, int(w * S)))
        f = font(fnt, S * 0.16)
        for h in (12, 3, 6, 9):
            d.text(pol(c, c, R * 0.60, h * 30), str(h), fill=CREAM, font=f, anchor='mm')
        for a, l, w in ((305, 0.48, 0.035), (60, 0.70, 0.025)):     # hands at 10:10
            d.line([(c, c), pol(c, c, R * l, a)], fill=LUM, width=int(w * S))
        d.ellipse([c - S * 0.03, c - S * 0.03, c + S * 0.03, c + S * 0.03], fill=(30, 30, 30))
    # title / sub (centre top or bottom)
    if spec.get('title'):
        f = font('arialbd.ttf', S * spec.get('ts', 0.075))
        d.text((c, c - R * spec.get('ty', 0.28)), spec['title'], fill=CREAM, font=f, anchor='mm')
    if spec.get('sub'):
        f = font('arial.ttf', S * spec.get('ss', 0.060))
        d.text((c, c + R * spec.get('sy', 0.30)), spec['sub'], fill=CREAM, font=f, anchor='mm')
    if spec.get('maker'):
        f = font('arial.ttf', S * 0.042)
        d.text((c, c - R * 0.40), spec['maker'], fill=(150, 146, 128), font=f, anchor='mm')
    if spec.get('needle') is not None:                 # painted needle for the decorative dials
        z, sw, v0, v1 = spec['zero'], spec['sweep'], spec['v0'], spec['v1']
        a = z + (spec['needle'] - v0) / (v1 - v0) * sw
        d.line([pol(c, c, -R * 0.2, a), pol(c, c, R * 0.82, a)], fill=LUM, width=int(S * 0.028))
        d.ellipse([c - S * 0.035, c - S * 0.035, c + S * 0.035, c + S * 0.035], fill=(25, 25, 25))
    return np.asarray(im, F32) / 255.0


DIAL_SPECS = {
    'asi': dict(zero=0, sweep=330, v0=0, v1=260, major=20, minor=10, labels=[(v, str(v)) for v in range(0, 260, 40)], title='KNOTS', sub='AIR SPEED', ty=0.16, ts=0.065,
                lum=True, fs=0.12, lr=0.64, maker='Mk IV  A.M.'),
    'alt': dict(zero=0, sweep=360, v0=0, v1=1000, major=100, minor=20, labels=[(v * 100, str(v)) for v in range(0, 10)], title='ALTIMETER', sub='FEET x 1000', ty=0.18,
                lum=True, fs=0.14, lr=0.62, ts=0.060, maker='Mk VI A.M.'),
    'rpm': dict(zero=-150, sweep=300, v0=0, v1=3000, major=500, minor=100, labels=[(v * 100, str(v)) for v in range(0, 31, 5)], title='R.P.M.', sub='x 100', ty=0.20,
                lum=True, red=2900, fs=0.14, lr=0.58, maker='SMITHS'),
    'boost': dict(zero=-135, sweep=270, v0=-4, v1=8, major=2, minor=1, labels=[(v, ('+' if v > 0 else '') + str(v)) for v in range(-4, 9, 2)], ty=-0.50, sy=0.74, ts=0.085, ss=0.065, title='BOOST',
                  sub='LB/SQ.IN', lum=True, fs=0.15, lr=0.57),
    'oilp': dict(zero=-135, sweep=270, v0=0, v1=100, major=20, minor=10, labels=[(v, str(v)) for v in range(0, 101, 20)], ty=-0.50, sy=0.74, ts=0.085, ss=0.065, title='OIL', sub='LB', fs=0.17, lr=0.55),
    'oilt': dict(zero=-135, sweep=270, v0=0, v1=100, major=20, minor=10, labels=[(v, str(v)) for v in range(0, 101, 20)], ty=-0.50, sy=0.74, ts=0.085, ss=0.065, title='OIL', sub='\u00b0C', fs=0.17, lr=0.55, red=80),
    'water': dict(zero=-135, sweep=270, v0=0, v1=140, major=20, minor=10, labels=[(v, str(v)) for v in (0, 40, 80, 120)], ty=-0.50, sy=0.74, ts=0.085, ss=0.065, title='RAD', sub='\u00b0C', fs=0.17, lr=0.55, red=120),
    'fuel': dict(zero=-135, sweep=270, v0=0, v1=100, major=25, minor=12.5, labels=[(0, 'E'), (25, '\u00bc'), (50, '\u00bd'), (75, '\u00be'), (100, 'F')], ty=-0.50, sy=0.74, ts=0.085, ss=0.065, title='FUEL',
                 fs=0.18, lr=0.55),
    'fuelp': dict(zero=-135, sweep=270, v0=0, v1=10, major=1, minor=0.5, labels=[(0, '0'), (5, '5'), (10, '10')], ty=-0.50, sy=0.74, ts=0.085, ss=0.065, title='FUEL', sub='LB', fs=0.18, lr=0.55, needle=3.2),
    'oxygen': dict(zero=-135, sweep=270, v0=0, v1=30, major=5, minor=1, labels=[(v, str(v)) for v in (0, 10, 20, 30)], ty=-0.50, sy=0.74, ts=0.085, ss=0.065, title='OXYGEN', sub='x1000 FT', fs=0.16, lr=0.55, needle=0.0),
    'clock': dict(kind='clock'),
    'turn': dict(kind='turn', title='TURN', ty=0.30, ts=0.08),
    'compass': dict(kind='compass'),
}


def gauges():
    N, G = L.GAUGE_N, L.GAUGE_GRID
    C = N // G
    img = np.zeros((N, N, 3), F32) + 0.03
    def put(region, arr):
        col, row, span = L.GAUGE_CELLS[region]
        px = C * span
        a = np.asarray(Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).resize((px, px), Image.LANCZOS), F32) / 255.0
        y0 = N - (row + span) * C
        img[y0:y0 + px, col * C:col * C + px] = a
    for k, spec in DIAL_SPECS.items():
        col, row, span = L.GAUGE_CELLS[k]
        S = C * span * 2
        put(k, dial_face(S, spec))
    def flat(region, rgb, noise=0.0, seed=0):
        col, row, span = L.GAUGE_CELLS[region]
        px = C * span
        a = np.zeros((px, px, 3), F32) + np.asarray(rgb, F32)
        if noise:
            a *= (1 - noise / 2 + noise * pnoise(px, 8, seed, 3))[..., None]
        put(region, a)
    flat('needle', (0.88, 0.86, 0.74)); flat('needle_dark', (0.06, 0.06, 0.06)); flat('ball', (0.04, 0.04, 0.04)); flat('hub', (0.07, 0.07, 0.07))
    flat('rim_black', (0.05, 0.05, 0.055), 0.2, 1); flat('rim_yellow', (0.86, 0.66, 0.10), 0.15, 2); flat('rim_blue', (0.12, 0.30, 0.56), 0.15, 3)
    flat('rim_white', (0.86, 0.85, 0.80), 0.1, 4); flat('rim_chrome', (0.75, 0.75, 0.76), 0.1, 5); flat('glass_dark', (0.025, 0.025, 0.03))
    save_rgb(img, 'nimrod_gauges')
    log('gauges', N, 'cells', len(L.GAUGE_CELLS))


# =========================================================================================== cockpit atlas
def region_px(name):
    return L.CKART[name]


def ckart(tile):
    N = L.CKART_N
    col = np.zeros((N, N, 3), F32) + 0.3
    hgt = np.zeros((N, N), F32)
    im = Image.new('RGB', (N, N))
    paint_tile, paint_h, _ = tile['ck_paint']

    def tile_fill(name, t, scale_px):
        x0, y0, x1, y1 = region_px(name)
        tc, th, _ = tile[t]
        n = tc.shape[0]
        yy, xx = np.mgrid[y0:y1, x0:x1]
        iy = ((yy * n / scale_px) % n).astype(int); ix = ((xx * n / scale_px) % n).astype(int)
        col[y0:y1, x0:x1] = tc[iy, ix]
        hgt[y0:y1, x0:x1] = th[iy, ix] * 0.3

    # ---------------- panel faces: worn grey paint, edge wear, screws, AO round the dials, stencil labels
    for reg, (xa, xb, ha, hb) in L.PANEL_REGION.items():
        x0, y0, x1, y1 = region_px(reg)
        ppm = (x1 - x0) / (xb - xa)              # px per metre
        tile_fill(reg, 'ck_paint', ppm * 0.5)     # tile = 0.5 m on the panel
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(F32)
        X = xa + (xx - x0 + 0.5) / ppm; H = hb - (yy - y0 + 0.5) / ppm
        # distance to the plate outline (approx: rectangle / outline polygon)
        if reg == 'lower':
            lw = L.LOWER
            dx = np.minimum(X - lw['x0'], lw['x1'] - X); dh = np.minimum(H - lw['h0'], lw['h1'] - H)
            de = np.minimum(dx, dh)
        else:
            de = None
        if de is None:
            poly = np.asarray(L.upper_outline(), F32)
            de = np.full(X.shape, 1.0, F32)
            for (ax, ah), (bx, bh) in zip(poly, np.roll(poly, -1, 0)):
                ex, eh = bx - ax, bh - ah
                l2 = ex * ex + eh * eh
                t = np.clip(((X - ax) * ex + (H - ah) * eh) / l2, 0, 1)
                dd = np.hypot(X - (ax + t * ex), H - (ah + t * eh))
                de = np.minimum(de, dd)
        wn = pnoise(512, 40, 31 if reg == 'lower' else 32, 3)
        wn = np.asarray(Image.fromarray((wn * 255).astype(np.uint8)).resize((x1 - x0, y1 - y0)), F32) / 255
        edge = sstep(0.0, 1.0, (0.005 - de) / 0.005 + (wn - 0.5) * 1.0)
        sub = col[y0:y1, x0:x1]
        sub[:] = lerp3(sub, (0.60, 0.61, 0.62), np.clip(edge, 0, 1) * 0.7)
        hgt[y0:y1, x0:x1] -= edge * 0.4
        # grime toward the bottom, finger wear round the cocks / magneto
        sub *= (1 - 0.12 * sstep(0.10, 0.0, H - (ha if reg == 'lower' else 0.2)))[..., None]
        for (cx, ch) in (L.COCKS if reg == 'lower' else []) + ([(L.MAGNETO['x'], L.MAGNETO['h'])] if reg == 'lower' else []):
            r = np.hypot(X - cx, H - ch)
            fw = sstep(0.050, 0.022, r) * sstep(0.45, 0.65, wn)
            sub[:] = lerp3(sub, (0.66, 0.67, 0.66), fw * 0.6)
        # AO / dark ring round each dial bezel and the tac bezel
        for gid, dd in L.DIALS.items():
            if bool(dd.get('upper')) != (reg == 'upper'):
                continue
            r = np.hypot(X - dd['x'], H - dd['h'])
            Rb = dd['r'] + 0.006
            ao = sstep(Rb + 0.010, Rb, r)
            sub *= (1 - 0.35 * ao)[..., None]
        if reg == 'lower':
            t = L.TAC
            ax_ = np.maximum(np.abs(X - t['x']) - (t['w'] / 2 + 0.011), 0); ah_ = np.maximum(np.abs(H - t['h']) - (t['hgt'] / 2 + 0.011), 0)
            ao = sstep(0.010, 0.0, np.hypot(ax_, ah_))
            sub *= (1 - 0.35 * ao)[..., None]
        col[y0:y1, x0:x1] = sub
        # screws along the lower panel border (dome + slot) every ~45 mm, 9 mm in from the edge
        if reg == 'lower':
            lw = L.LOWER
            pts = []
            for k in range(17):
                x = lw['x0'] + 0.020 + k * (lw['x1'] - lw['x0'] - 0.040) / 16
                pts += [(x, lw['h0'] + 0.009), (x, lw['h1'] - 0.009)]
            for h in (0.07, 0.13, 0.19):
                pts += [(lw['x0'] + 0.009, h), (lw['x1'] - 0.009, h)]
            for (sx, sh) in pts:
                r = np.hypot(X - sx, H - sh)
                m = r < 0.0032
                if not m.any():
                    continue
                dome = np.clip(1 - (r / 0.0032) ** 2, 0, 1)
                sub = col[y0:y1, x0:x1]
                sub[m] = (np.asarray((0.36, 0.37, 0.38), F32) * (0.75 + 0.5 * dome[m])[:, None])
                slot = m & (np.abs(X - sx - (H - sh) * 0.3) < 0.0005)
                sub[slot] = (0.12, 0.12, 0.12)
                hgt[y0:y1, x0:x1] += dome * 1.2 - slot * 0.8
                col[y0:y1, x0:x1] = sub
    # stencil labels (cream / white paint, slightly worn)
    d = ImageDraw.Draw(im)
    lab = Image.new('L', (N, N), 0); dl = ImageDraw.Draw(lab)
    for reg, labels in (('lower', L.LABELS_LOWER), ('upper', L.LABELS_UPPER)):
        x0, y0, x1, y1 = region_px(reg)
        xa, xb, ha, hb = L.PANEL_REGION[reg]
        ppm = (x1 - x0) / (xb - xa)
        for txt, x, h, sz in labels:
            px = x0 + (x - xa) * ppm; py = y0 + (hb - h) * ppm
            dl.text((px, py), txt, fill=255, font=font('arialbd.ttf', sz * ppm * 1.25), anchor='mm')
    lm = np.asarray(lab, F32) / 255.0
    lm *= (0.75 + 0.25 * np.asarray(Image.fromarray((pnoise(512, 64, 33, 2) * 255).astype(np.uint8)).resize((N, N)), F32) / 255)
    col = lerp3(col, (0.90, 0.89, 0.84), lm)
    hgt += lm * 0.15

    # ---------------- seat skin: dull aluminium sheet, rivet rows on the seams, scratches, cushion shadow
    x0, y0, x1, y1 = region_px('seat')
    tile_fill('seat', 'ck_alu', 700)
    W, Hh = x1 - x0, y1 - y0
    sub = col[y0:y1, x0:x1]
    sub *= 0.85
    yy, xx = np.mgrid[0:Hh, 0:W].astype(F32)
    fu = (xx + 0.5) / W; fv = 1 - (yy + 0.5) / Hh
    rows_u = [0.06, 0.135, 0.865, 0.94]               # wall bottoms / flanges (fraction of the profile arc)
    rows_v = [0.02, 0.36, 0.55, 0.98]                 # front lip, pan / back seam, back panel seam, top
    riv = np.zeros((Hh, W), F32)
    pitch = 16.0
    for ru in rows_u:
        cx = ru * W
        cy = (np.floor(yy / pitch) + 0.5) * pitch
        r = np.hypot(xx - cx, yy - cy)
        riv = np.maximum(riv, np.clip(1 - (r / 3.6) ** 2, 0, 1))
    for rv in rows_v:
        cy = (1 - rv) * Hh
        cx = (np.floor(xx / pitch) + 0.5) * pitch
        r = np.hypot(xx - cx, yy - cy)
        riv = np.maximum(riv, np.clip(1 - (r / 3.6) ** 2, 0, 1))
    seam = np.zeros((Hh, W), F32)
    for ru in rows_u:
        seam = np.maximum(seam, (np.abs(xx - ru * W - 9) < 1.0).astype(F32))
    for rv in rows_v[1:3]:
        seam = np.maximum(seam, (np.abs(yy - (1 - rv) * Hh - 9) < 1.0).astype(F32))
    sub[:] = sub * (1 - 0.35 * seam)[..., None]
    sub[:] = lerp3(sub, (0.80, 0.81, 0.82), riv * 0.7)
    hgt[y0:y1, x0:x1] += riv * 1.4 - seam * 0.5
    # dark grime in the pan centre (under the cushion) and a worn shine on the side rims
    pan = sstep(0.25, 0.0, np.abs(fu - 0.5)) * sstep(0.45, 0.25, fv)
    sub *= (1 - 0.3 * pan)[..., None]
    col[y0:y1, x0:x1] = sub

    # ---------------- placards / cards / plates
    def card(name, lines, bg, fg, border=None, fs=0.20, fontn='arialbd.ttf', screws=False, emb=False):
        x0, y0, x1, y1 = region_px(name)
        w, h = x1 - x0, y1 - y0
        pim = Image.new('RGB', (w, h), tuple(int(c * 255) for c in bg))
        pd = ImageDraw.Draw(pim)
        if border:
            pd.rectangle([4, 4, w - 5, h - 5], outline=border, width=3)
        nl = len(lines)
        f = font(fontn, h * fs if nl > 2 else h * fs * 1.4)
        for k, t in enumerate(lines):
            pd.text((w / 2, h * (k + 0.5) / nl * (0.86) + h * 0.07), t, fill=fg, font=f, anchor='mm')
        if screws:
            for sx, sy in ((14, 14), (w - 14, 14), (14, h - 14), (w - 14, h - 14)):
                pd.ellipse([sx - 6, sy - 6, sx + 6, sy + 6], fill=(90, 90, 90))
        a = np.asarray(pim, F32) / 255.0
        age = pnoise(256, 8, sum(map(ord, name)) % 1000, 3)
        age = np.asarray(Image.fromarray((age * 255).astype(np.uint8)).resize((w, h)), F32) / 255
        a *= (0.88 + 0.16 * age)[..., None]
        col[y0:y1, x0:x1] = a
        lum = a.mean(axis=2)
        hgt[y0:y1, x0:x1] = (lum - lum.mean()) * (0.6 if emb else 0.15)
    card('dataplate', L.PLACARDS['dataplate'], (0.62, 0.60, 0.52), (25, 22, 18), border=(40, 38, 30), fs=0.13, screws=False, emb=True)
    card('devcard', L.PLACARDS['devcard'], (0.86, 0.84, 0.76), (20, 20, 20), border=(60, 60, 60), fs=0.18, fontn='cour.ttf')
    card('ratecard', L.PLACARDS['ratecard'], (0.86, 0.84, 0.76), (20, 20, 20), border=(60, 60, 60), fs=0.22, fontn='courbd.ttf')
    card('wallcard1', L.PLACARDS['wallcard1'], (0.85, 0.83, 0.74), (25, 25, 25), border=(70, 70, 70), fs=0.15, fontn='courbd.ttf')
    card('wallcard2', L.PLACARDS['wallcard2'], (0.85, 0.83, 0.74), (25, 25, 25), border=(70, 70, 70), fs=0.15, fontn='courbd.ttf')
    card('trimcard', L.PLACARDS['trimcard'], (0.06, 0.06, 0.06), (225, 220, 195), border=(200, 196, 170), fs=0.20)
    card('serial', L.PLACARDS['serial'], (0.06, 0.06, 0.06), (225, 220, 195), fs=0.55)
    card('cockplate', L.PLACARDS['cockplate'], (0.70, 0.54, 0.25), (30, 22, 10), border=(60, 45, 20), fs=0.30, emb=True)
    card('stencil', L.PLACARDS['stencil'], (0.68, 0.69, 0.70), (20, 20, 20), fs=0.12)
    # quadrant plate: engraved alu with scale + labels
    x0, y0, x1, y1 = region_px('quadrant'); w, h = x1 - x0, y1 - y0
    pim = Image.new('RGB', (w, h), (170, 172, 175)); pd = ImageDraw.Draw(pim)
    f = font('arialbd.ttf', h * 0.26)
    pd.text((w * 0.25, h * 0.30), 'THROTTLE', fill=(20, 20, 20), font=f, anchor='mm')
    pd.text((w * 0.75, h * 0.30), 'MIXTURE', fill=(20, 20, 20), font=f, anchor='mm')
    f2 = font('arialbd.ttf', h * 0.22)
    pd.text((w * 0.10, h * 0.72), '\u25c4 SHUT', fill=(20, 20, 20), font=f2, anchor='mm'); pd.text((w * 0.40, h * 0.72), 'OPEN \u25ba', fill=(20, 20, 20), font=f2, anchor='mm')
    pd.text((w * 0.62, h * 0.72), 'WEAK', fill=(20, 20, 20), font=f2, anchor='mm'); pd.text((w * 0.88, h * 0.72), 'RICH', fill=(150, 25, 20), font=f2, anchor='mm')
    pd.rectangle([3, 3, w - 4, h - 4], outline=(60, 60, 60), width=3)
    a = np.asarray(pim, F32) / 255.0
    col[y0:y1, x0:x1] = a; hgt[y0:y1, x0:x1] = -(a.mean(axis=2) < 0.3).astype(F32) * 0.4
    # ammo counter / gun box face: black crinkle, two counter windows, labels
    x0, y0, x1, y1 = region_px('ammo'); w, h = x1 - x0, y1 - y0
    pim = Image.new('RGB', (w, h), (14, 14, 15)); pd = ImageDraw.Draw(pim)
    fw = font('consolab.ttf', h * 0.20); fl = font('arialbd.ttf', h * 0.085)
    for k, (lab, val) in enumerate((('PORT', '0412'), ('STBD', '0398'))):
        cx = w * (0.30 + 0.40 * k) - w * 0.05
        pd.rectangle([cx - w * 0.15, h * 0.30, cx + w * 0.15, h * 0.58], fill=(5, 5, 5), outline=(120, 120, 120), width=3)
        pd.text((cx, h * 0.44), val, fill=(230, 228, 210), font=fw, anchor='mm')
        pd.text((cx, h * 0.20), lab, fill=(220, 215, 190), font=fl, anchor='mm')
    pd.text((w * 0.40, h * 0.74), 'ROUNDS REMAINING', fill=(220, 215, 190), font=fl, anchor='mm')
    pd.text((w * 0.86, h * 0.14), 'GUNS', fill=(220, 215, 190), font=fl, anchor='mm')
    pd.text((w * 0.80, h * 0.90), 'FIRE / SAFE', fill=(200, 60, 40), font=fl, anchor='mm')
    a = np.asarray(pim, F32) / 255.0
    cr_c, cr_h, _ = tile['ck_crinkle']
    a = np.where(a.mean(axis=2, keepdims=True) < 0.07, cr_c[:h, :w] * 1.0 + a * 0.2, a)
    col[y0:y1, x0:x1] = a; hgt[y0:y1, x0:x1] = cr_h[:h, :w] * 0.3
    # magneto box face
    x0, y0, x1, y1 = region_px('magneto'); w, h = x1 - x0, y1 - y0
    pim = Image.new('RGB', (w, h), (14, 14, 15)); pd = ImageDraw.Draw(pim)
    fl = font('arialbd.ttf', h * 0.16)
    pd.text((w * 0.5, h * 0.15), 'IGNITION', fill=(225, 220, 195), font=fl, anchor='mm')
    for k, t in enumerate(('1', '2')):
        cx = w * (0.28 + 0.44 * k)
        pd.text((cx, h * 0.84), t, fill=(225, 220, 195), font=fl, anchor='mm')
        pd.text((cx - w * 0.15, h * 0.45), 'ON', fill=(200, 196, 170), font=font('arial.ttf', h * 0.11), anchor='mm')
    a = np.asarray(pim, F32) / 255.0
    a = np.where(a.mean(axis=2, keepdims=True) < 0.07, cr_c[:h, :w] + a * 0.2, a)
    col[y0:y1, x0:x1] = a; hgt[y0:y1, x0:x1] = cr_h[:h, :w] * 0.3
    # breech casing rear face: black crinkle, raised rear plate outline, crank boss ring, stamping
    x0, y0, x1, y1 = region_px('breech'); w, h = x1 - x0, y1 - y0
    pim = Image.new('L', (w, h), 0); pd = ImageDraw.Draw(pim)
    pd.rounded_rectangle([w * 0.08, h * 0.06, w * 0.92, h * 0.94], radius=w * 0.08, outline=255, width=int(w * 0.035))
    pd.text((w * 0.5, h * 0.16), 'VICKERS', fill=200, font=font('arialbd.ttf', w * 0.10), anchor='mm')
    pd.text((w * 0.5, h * 0.84), '.303 Mk III', fill=200, font=font('arialbd.ttf', w * 0.09), anchor='mm')
    e = np.asarray(pim, F32) / 255.0
    tc = cr_c[:h, :w] * 1.0
    col[y0:y1, x0:x1] = lerp3(tc, (0.20, 0.20, 0.21), e * 0.8)
    hgt[y0:y1, x0:x1] = cr_h[:h, :w] * 0.3 + e * 0.8
    # oxygen face region unused (the oxygen dial is in the gauge atlas)
    save_rgb(col, 'nimrod_ckart_b')
    nrm = normal_from_height(np.asarray(Image.fromarray(np.clip((hgt + 4) / 8 * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), F32) / 255 * 8 - 4, 1.6, wrap=False)
    save_n(nrm, 'nimrod_ckart_n')
    log('ckart', N)


def prop_textures():
    """each fal 3D prop's own baked base colour + normal map, from its optimised GLB (1024 px)."""
    import struct, io
    from PIL import Image
    SRC_GLB = {'pr_vickers': 'vickers', 'pr_exhaust': 'exhaust', 'pr_hook': 'tailhook_v2', 'pr_wheel': 'wheel', 'pr_tailwheel': 'tailwheel_wheel',
               'pr_pedals': 'pedals_lp', 'pr_cooper': 'cooper_single'}          # = nimrod_props.SRC_GLB
    OPTD = os.path.join(ROOT, 'assets', 'model_nimrod', 'src', 'fal', 'opt')
    for key, glb in SRC_GLB.items():
        d = open(os.path.join(OPTD, glb + '.glb'), 'rb').read()
        L = struct.unpack('<III', d[:12])[2]
        off, ch = 12, []
        while off < L:
            cl, ct = struct.unpack('<II', d[off:off + 8]); ch.append(d[off + 8:off + 8 + cl]); off += 8 + cl
        js, bn = json.loads(ch[0]), ch[1]
        mat = js['materials'][0]

        def img(ti):
            im = js['images'][js['textures'][ti]['source']]
            bv = js['bufferViews'][im['bufferView']]
            o = bv.get('byteOffset', 0)
            return Image.open(io.BytesIO(bn[o:o + bv['byteLength']])).convert('RGB')
        b = img(mat['pbrMetallicRoughness']['baseColorTexture']['index'])
        nt = mat.get('normalTexture')
        nm = img(nt['index']) if nt else Image.new('RGB', b.size, (128, 128, 255))
        b = b.resize((1024, 1024), Image.LANCZOS); nm = nm.resize((1024, 1024), Image.LANCZOS)
        if key in ('pr_wheel', 'pr_tailwheel', 'pr_pedals'):
            b = b.filter(ImageFilter.MedianFilter(7 if key != 'pr_pedals' else 5))
            if key == 'pr_pedals':
                b = b.filter(ImageFilter.GaussianBlur(1.2))
        if key in ('pr_wheel', 'pr_tailwheel'):
            # the generated tyre texture has pale blotches on the rubber: where the neighbourhood is dark rubber, clamp bright
            # specks to the local rubber tone (the bright hub cover is a large bright area and stays)
            a = np.asarray(b).astype(F32) / 255.0
            loc = np.asarray(b.filter(ImageFilter.GaussianBlur(40))).astype(F32) / 255.0
            lum, llum = a.mean(-1), loc.mean(-1)
            spot = (llum < 0.40) & (lum > 0.33)          # pale blobs on the tread / sidewall strips (the hub discs are large bright areas)
            rub = np.array([0.13, 0.13, 0.135], F32)
            a[spot] = rub + (a[spot] - a[spot].mean(-1, keepdims=True)) * 0.1
            b = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
        b.save(os.path.join(OUT, f'nimrod_{key}_b.png')); nm.save(os.path.join(OUT, f'nimrod_{key}_n.png'))
    log('prop textures:', ', '.join(SRC_GLB))



def main():
    prop_textures()
    t = tiles()
    gauges()
    ckart(t)
    json.dump(dict(tiles=sorted(t), tile_scale=L.TILE_SCALE, gauge_cells=len(L.GAUGE_CELLS), ckart_regions=sorted(L.CKART)),
              open(os.path.join(OUT, 'nimrod_ckart_stats.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
