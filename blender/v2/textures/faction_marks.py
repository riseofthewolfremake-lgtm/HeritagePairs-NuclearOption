"""Faction national markings for the B-25H liveries: clean vector redraws of the Nuclear Option BDF and
PALA roundels (numpy only, no bpy; usable from Blender and from plain Python).

Source / policy note: the shapes and colours follow the game's own faction roundels (Boscali Defense Force,
Primeva Armed Liberation Alliance) as shown in-game and on stock aircraft. The emblems are Shockfront Studios'
designs, redrawn here and used as Shockfront allows for custom liveries, the same way Steam Workshop liveries
use them (see CREDITS.md, "Faction emblems").
Nothing here is copied from game files: every shape is re-entered as polygon / circle coordinates measured
on a 1024 px design canvas and evaluated as a signed-distance field, so it renders crisply at any size.

Canvas convention: x right, y DOWN, 1024 x 1024 design units. A mark is placed by giving, per texel, the
local coordinates (pu right, pv up, metres) as seen by a viewer looking at the painted surface, and the
mark's width in metres. `layers(kind, pu, pv, width, aa)` returns [(coverage, rgb), ...] in paint order.
"""
import math
import numpy as np

F32 = np.float32

# display-encoded sRGB colours measured on the game's roundel art (rounded)
PALA_RED = np.array([145, 4, 0], F32) / 255
BDF_GREEN = np.array([54, 107, 0], F32) / 255
BDF_BLUE = np.array([0, 53, 115], F32) / 255
MARK_WHITE = np.array([228, 228, 228], F32) / 255
MARK_BLACK = np.array([8, 8, 8], F32) / 255

# design-canvas extents (bounding boxes) used to centre and scale each mark
EXTENT = {'PALA': (32, 20, 992, 1000), 'BDF': (12, 275, 1012, 858)}


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def cover(sd, aa):
    """signed distance (negative inside) -> anti-aliased coverage."""
    return (1 - _smooth(-aa, aa, sd)).astype(F32)


def sd_poly(px, py, verts):
    """signed distance to a simple polygon (negative inside). verts: list of (x, y)."""
    v = np.asarray(verts, F32)
    d = np.full(px.shape, 1e9, F32)
    s = np.ones(px.shape, F32)
    n = len(v)
    for i in range(n):
        ax, ay = v[i]
        bx, by = v[i - 1]
        ex, ey = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        t = np.clip((wx * ex + wy * ey) / max(ex * ex + ey * ey, 1e-12), 0, 1)
        qx, qy = wx - ex * t, wy - ey * t
        d = np.minimum(d, qx * qx + qy * qy)
        c1 = py >= ay
        c2 = py < by
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return (s * np.sqrt(d)).astype(F32)


def tri_up(cx, top, h, hw):
    """upward-pointing triangle (apex at top, y down canvas)."""
    return [(cx, top), (cx + hw, top + h), (cx - hw, top + h)]


# ------------------------------------------------------------------ PALA
PALA_C = (512.0, 578.0)
R_OUT, R_RED_O, R_RED_I, R_IN = 422.0, 405.0, 336.0, 319.0
PALA_RED_TRI = [(238, 415), (785, 415), (512, 889)]
PALA_WHITE = [tri_up(cx, top, 119, 68) for cx, top in
              ((376, 415), (512, 415), (648, 415), (444, 535), (580, 535), (512, 655))]
BLOCK_HALF_DEG = 11.0


def _pala(x, y, aa):
    cx, cy = PALA_C
    dx, dy = x - cx, cy - y                     # y up, about the ring centre
    r = np.sqrt(dx * dx + dy * dy)
    ang = np.degrees(np.arctan2(dy, dx))
    # three point units at 90 / 210 / 330 deg: rotate each texel into the top unit's frame
    pt_black = np.full(x.shape, 1e9, F32)
    pt_white = np.full(x.shape, 1e9, F32)
    block = np.full(x.shape, 1e9, F32)
    for k in range(3):
        a = math.radians(-120.0 * k)
        ux = dx * math.cos(a) - dy * math.sin(a)
        uy = dx * math.sin(a) + dy * math.cos(a)
        # top unit in a y-up frame: apex at 558, base at 418 (equilateral)
        tb = sd_poly(ux, uy, [(0, 558), (81, 418), (-81, 418)])
        tw = sd_poly(ux, uy, [(0, 508), (45, 430), (-45, 430)])
        # black block bridging the ring: angular sector of the annulus
        ua = np.degrees(np.arctan2(ux, uy))     # 0 on the unit axis
        sec = (np.abs(ua) - BLOCK_HALF_DEG) * math.radians(1) * r       # <0 inside the sector
        bl = np.maximum(np.maximum(R_IN - r, r - (R_OUT + 4)), sec)
        pt_black = np.minimum(pt_black, tb)
        pt_white = np.minimum(pt_white, tw)
        block = np.minimum(block, bl)
    ring_black = np.maximum(R_IN - r, r - R_OUT)
    ring_red = np.maximum(np.maximum(R_RED_I - r, r - R_RED_O), -block)
    tri_red = sd_poly(x, y, PALA_RED_TRI)
    tri_black = tri_red - 29.0
    white = np.full(x.shape, 1e9, F32)
    for t in PALA_WHITE:
        white = np.minimum(white, sd_poly(x, y, t))
    black = np.minimum(np.minimum(ring_black, tri_black), np.minimum(pt_black, block))
    red = np.minimum(ring_red, tri_red)
    white = np.minimum(np.maximum(white, tri_red), pt_white)  # small triangles clipped to the red triangle
    return [(cover(black, aa), MARK_BLACK), (cover(red, aa), PALA_RED), (cover(white, aa), MARK_WHITE)]


# ------------------------------------------------------------------ BDF
BDF_BACK = [(12, 385), (1012, 385), (893, 740), (128, 740)]
BDF_SHIELD_O = [(235, 275), (512, 358), (790, 275), (752, 600), (528, 858), (497, 858), (272, 600)]
BDF_SHIELD_I = [(265, 315), (512, 385), (757, 315), (722, 605), (512, 828), (302, 605)]
BDF_BARS_L = {'white': [(48, 408), (232, 408), (240, 490), (75, 490)],
              'green': [(85, 522), (243, 522), (250, 600), (112, 600)],
              'blue': [(125, 636), (250, 636), (325, 715), (150, 715)]}
BDF_WHITE_TRI = [(567, 403), (730, 348), (711, 450)]
BDF_GREEN_TRI = [(467, 733), (595, 690), (512, 780)]
# green band of the shield between two parallel lines (through these points)
BDF_BAND_UP = ((283, 457), (757, 315))
BDF_BAND_LO = ((387, 708), (725, 605))


def _line_sd(x, y, p, q):
    """signed distance to the infinite line p->q, positive on the side the line's left normal points (y down)."""
    ex, ey = q[0] - p[0], q[1] - p[1]
    L = math.hypot(ex, ey)
    return ((x - p[0]) * ey - (y - p[1]) * ex) / L


def _bdf(x, y, aa, text=True):
    mir = lambda poly: [(1024 - a, b) for a, b in poly]
    black = np.minimum(sd_poly(x, y, BDF_BACK), sd_poly(x, y, BDF_SHIELD_O))
    out = [(cover(black, aa), MARK_BLACK)]
    for name, col in (('white', MARK_WHITE), ('green', BDF_GREEN), ('blue', BDF_BLUE)):
        p = BDF_BARS_L[name]
        sd = np.minimum(sd_poly(x, y, p), sd_poly(x, y, mir(p)))
        sd = np.maximum(sd, -(sd_poly(x, y, BDF_SHIELD_O)))        # bars stop at the shield outline
        out.append((cover(sd, aa), col))
    inner = sd_poly(x, y, BDF_SHIELD_I)
    out.append((cover(inner, aa), BDF_BLUE))
    # band: below the upper line and above the lower line (y down)
    up = _line_sd(x, y, *BDF_BAND_UP)          # <0 below the upper line
    lo = _line_sd(x, y, *BDF_BAND_LO)          # <0 below the lower line
    band = np.maximum(np.maximum(up, -lo), inner)
    out.append((cover(band, aa), BDF_GREEN))
    out.append((cover(np.maximum(sd_poly(x, y, BDF_WHITE_TRI), inner), aa), MARK_WHITE))
    out.append((cover(np.maximum(sd_poly(x, y, BDF_GREEN_TRI), inner), aa), BDF_GREEN))
    if text:
        # stock airframe roundels carry the letters BDF across the shield (white, black outline)
        d = _text_dist(x, y, 'BDF', cx=500, cy=548, h=120, adv=5.4)
        out.append((cover(d - 22, aa), MARK_BLACK))
        out.append((cover(d - 11, aa), MARK_WHITE))
    return out


# compact stroke glyphs (4 x 6 grid, y up) - same family as tex_lib's stencil font
_GL = {'B': ['0,0 0,6 3,6 4,5 4,4 3,3 0,3', '3,3 4,2 4,1 3,0 0,0'], 'D': ['0,0 0,6 2,6 4,4 4,2 2,0 0,0'],
       'F': ['0,0 0,6 4,6', '0,3 3,3']}


def _text_dist(x, y, text, cx, cy, h, adv=5.6):
    u = h / 6.0
    w = (len(text) * adv - (adv - 4)) * u
    ox, oy = cx - w / 2, cy + h / 2              # left baseline, canvas y down
    d = np.full(x.shape, 1e9, F32)
    for i, ch in enumerate(text):
        for stroke in _GL[ch]:
            pts = [tuple(float(c) for c in p.split(',')) for p in stroke.split()]
            for a, b in zip(pts[:-1], pts[1:]):
                x0, y0 = ox + (i * adv + a[0]) * u, oy - a[1] * u
                x1, y1 = ox + (i * adv + b[0]) * u, oy - b[1] * u
                ex, ey = x1 - x0, y1 - y0
                t = np.clip(((x - x0) * ex + (y - y0) * ey) / max(ex * ex + ey * ey, 1e-9), 0, 1)
                d = np.minimum(d, np.hypot(x - x0 - ex * t, y - y0 - ey * t))
    return d


# ------------------------------------------------------------------ placement API
def to_canvas(kind, pu, pv, width):
    """local metres (pu right, pv up, origin = mark centre) -> design canvas coords; returns x, y, px_per_m."""
    x0, y0, x1, y1 = EXTENT[kind]
    s = (x1 - x0) / width
    return (x0 + x1) / 2 + pu * s, (y0 + y1) / 2 - pv * s, s


def layers(kind, pu, pv, width, aa_m):
    """paint layers [(coverage, rgb)] for a mark of `width` metres; aa_m = anti-alias half-width in metres."""
    x, y, s = to_canvas(kind, np.asarray(pu, F32), np.asarray(pv, F32), width)
    aa = max(aa_m * s, 1.0)
    return _pala(x, y, aa) if kind == 'PALA' else _bdf(x, y, aa)


def height_of(kind, width):
    x0, y0, x1, y1 = EXTENT[kind]
    return width * (y1 - y0) / (x1 - x0)


def render(kind, size=512, pad=0.04):
    """standalone RGBA image (rows top-down) of the mark on transparent, for docs/compare."""
    x0, y0, x1, y1 = EXTENT[kind]
    span = max(x1 - x0, y1 - y0) * (1 + 2 * pad)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    g = (np.arange(size, dtype=F32) + 0.5) / size - 0.5
    X, Y = np.meshgrid(cx + g * span, cy + g * span)
    aa = span / size * 0.7
    L = _pala(X, Y, aa) if kind == 'PALA' else _bdf(X, Y, aa)
    rgb = np.zeros((size, size, 3), F32)
    a = np.zeros((size, size), F32)
    for cov, col in L:
        rgb = rgb * (1 - cov[..., None]) + col * cov[..., None]
        a = np.maximum(a, cov)
    return np.dstack([rgb, a])
