"""A6M2 cockpit tiles (round 4c; plain Python: PIL + numpy, our own procedural art).

  python blender/a6m2/textures/make_ck_tiles_a6m2.py [--out assets/textures_a6m2]

a6m2_tile_ckgreen_b/_n : Mitsubishi cockpit green (#6E7663 family) with skin-panel seams, rivet rows along the seams, light mottling and
                         edge wear (bare aluminium chips along the seams) - the B-25H / Nimrod cockpit wall treatment.
a6m2_tile_ckpanel_b/_n : the instrument panel's semi-gloss black with faint mottling, fine scratches and a few worn spots.
Tile = one 'detail' UV unit = 2 m (build_b25h_v2: detail = planar metres x 0.5; Unity copies UV1 to UV0 for tiled materials).
Seamless: every feature is placed modulo the tile size, noise is blurred with wrap-around.
"""
import os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
argv = sys.argv[1:]
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_a6m2')
N = 1024
M_PER_PX = 2.0 / N
rng = np.random.default_rng(4012)


def wrap_blur(a, r):
    """box blur with wrap-around, 3 passes (~gaussian)."""
    for _ in range(3):
        for ax in (0, 1):
            acc = np.zeros_like(a)
            for d in range(-r, r + 1):
                acc += np.roll(a, d, axis=ax)
            a = acc / (2 * r + 1)
    return a


def noise(scale_px, amp):
    n = wrap_blur(rng.standard_normal((N, N)), max(1, scale_px // 3))
    n = n / (np.abs(n).max() + 1e-9)
    return n * amp


def normal_from_height(h, strength):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * strength
    nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
    nx, ny = -gx * nz, gy * nz            # OpenGL convention (green up), image row 0 = top
    img = np.stack([nx, ny, nz], -1) * 0.5 + 0.5
    return Image.fromarray((img * 255).clip(0, 255).astype(np.uint8), 'RGB')


def save(img, name):
    p = os.path.join(OUT, name)
    img.save(p)
    print('[a6tile]', p, img.size)


def ckgreen():
    yy, xx = np.mgrid[0:N, 0:N]
    base = np.array([0x58, 0x67, 0x55], np.float32) / 255.0      # r4c render review: darker, slightly bluer, as the reference cockpit
    col = np.ones((N, N, 3), np.float32) * base
    mott = noise(64, 0.05) + noise(16, 0.025)
    col *= (1.0 + mott)[..., None]
    h = np.zeros((N, N), np.float32)
    seam_v = [0, N // 4, N // 2, 3 * N // 4]                 # skin sheets 0.5 m wide (vertical seams along frames)
    seam_h = [N // 3, (5 * N) // 6]                           # horizontal seams, offset rows (lap joints)
    wear = np.zeros((N, N), np.float32)
    dark = np.zeros((N, N), np.float32)
    for x in seam_v:
        d = np.minimum(np.abs(xx - x), N - np.abs(xx - x))
        dark = np.maximum(dark, (d <= 1) * 1.0)
        h -= (d <= 1) * 0.8
        wear = np.maximum(wear, np.exp(-(d / 6.0) ** 2))
    for y in seam_h:
        d = np.minimum(np.abs(yy - y), N - np.abs(yy - y))
        dark = np.maximum(dark, (d <= 1) * 1.0)
        h -= (d <= 1) * 0.6
        h += ((yy - y) % N < N // 2) * (d < 20) * 0.0                # (flat lap; normal comes from the groove)
        wear = np.maximum(wear, np.exp(-(d / 6.0) ** 2))
    # rivet rows: 25 mm pitch (12.5 px) along every seam, 10 px either side
    pitch = 12.8
    rr = 2.2
    riv = np.zeros((N, N), np.float32)
    for x in seam_v:
        for off in (-9, 9):
            cx = (x + off) % N
            for k in range(int(N / pitch)):
                cy = k * pitch + 4
                riv = np.maximum(riv, _dot(xx, yy, cx, cy, rr))
    for y in seam_h:
        for off in (-9, 9):
            cy = (y + off) % N
            for k in range(int(N / pitch)):
                cx = k * pitch + 4
                riv = np.maximum(riv, _dot(xx, yy, cx, cy, rr))
    h += riv * 0.9
    col *= (1.0 - 0.35 * dark)[..., None]
    col *= (1.0 + 0.10 * riv)[..., None]
    # edge wear: chips of bare aluminium where the seam-wear mask meets high-frequency noise; scuffs lower on the tile
    chips = (noise(6, 1.0) + 0.6 * wear) > 0.95
    scuff = (noise(24, 1.0) > 0.55) & (noise(4, 1.0) > 0.35)
    alu = np.array([0.66, 0.67, 0.66], np.float32)
    m = (chips | scuff).astype(np.float32)
    m = wrap_blur(m, 1).clip(0, 1)
    col = col * (1 - m[..., None]) + alu * m[..., None]
    h -= m * 0.15
    # dirt: slightly darker near horizontal seams (below) and in the mottle troughs
    col *= (1.0 - 0.06 * wrap_blur(dark, 6) * 4).clip(0.8, 1.0)[..., None]
    save(Image.fromarray((col.clip(0, 1) * 255).astype(np.uint8), 'RGB'), 'a6m2_tile_ckgreen_b.png')
    save(normal_from_height(wrap_blur(h, 1), 3.0), 'a6m2_tile_ckgreen_n.png')


def _dot(xx, yy, cx, cy, r):
    dx = np.minimum(np.abs(xx - cx), N - np.abs(xx - cx))
    dy = np.minimum(np.abs(yy - cy), N - np.abs(yy - cy))
    d2 = dx * dx + dy * dy
    return np.clip(1.0 - d2 / (r * r), 0, 1) ** 0.5


def ckpanel():
    base = np.array([0.075, 0.076, 0.072], np.float32)
    col = np.ones((N, N, 3), np.float32) * base
    col *= (1.0 + noise(48, 0.10) + noise(8, 0.05))[..., None]
    h = noise(3, 0.25)                                         # fine crinkle of the semi-gloss enamel
    # scratches: thin bright short lines
    for _ in range(140):
        x0, y0 = rng.uniform(0, N, 2)
        a = rng.uniform(0, np.pi)
        L = rng.uniform(8, 50)
        for t in np.linspace(0, L, int(L * 2)):
            x, y = int(x0 + t * np.cos(a)) % N, int(y0 + t * np.sin(a)) % N
            col[y, x] = col[y, x] * 0.5 + np.array([0.30, 0.30, 0.29]) * 0.5
    worn = (noise(30, 1.0) > 0.75) & (noise(5, 1.0) > 0.2)
    m = wrap_blur(worn.astype(np.float32), 1)
    col = col * (1 - 0.6 * m[..., None]) + np.array([0.32, 0.33, 0.33]) * 0.6 * m[..., None]
    save(Image.fromarray((col.clip(0, 1) * 255).astype(np.uint8), 'RGB'), 'a6m2_tile_ckpanel_b.png')
    save(normal_from_height(h, 1.5), 'a6m2_tile_ckpanel_n.png')


def ckgun():
    """r6: gun receivers - near-black blued steel, semi-gloss, faint machining streaks, worn bright edges where the tile's grid lines run
    (box edges land on the 0.5 m grid often enough at 2 m a tile; the scattered scuffs carry the wear elsewhere)."""
    col = np.ones((N, N, 3), np.float32) * np.array([0.155, 0.160, 0.168], np.float32)   # r8b: dark gunmetal, not near-black
    streak = wrap_blur(rng.standard_normal((N, N)), 1)
    streak = np.repeat(streak.mean(axis=1, keepdims=True), N, axis=1) * 3.0     # horizontal machining lines
    col *= (1.0 + 0.06 * streak + noise(40, 0.08))[..., None]
    wear = ((noise(20, 1.0) > 0.62) & (noise(3, 1.0) > 0.1)).astype(np.float32)
    yy, xx = np.mgrid[0:N, 0:N]
    for g in (0, N // 4, N // 2, 3 * N // 4):
        d = np.minimum(np.abs(xx - g), N - np.abs(xx - g))
        wear = np.maximum(wear, (d < 3) * (noise(4, 1.0) > -0.2))
        d = np.minimum(np.abs(yy - g), N - np.abs(yy - g))
        wear = np.maximum(wear, (d < 3) * (noise(4, 1.0) > -0.2))
    m = wrap_blur(wear.astype(np.float32), 1).clip(0, 1)
    col = col * (1 - 0.7 * m[..., None]) + np.array([0.42, 0.43, 0.45]) * 0.7 * m[..., None]
    save(Image.fromarray((col.clip(0, 1) * 255).astype(np.uint8), 'RGB'), 'a6m2_tile_ckgun_b.png')
    save(normal_from_height(noise(3, 0.15) + 0.2 * streak, 1.0), 'a6m2_tile_ckgun_n.png')


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    ckgreen()
    ckpanel()
    ckgun()
