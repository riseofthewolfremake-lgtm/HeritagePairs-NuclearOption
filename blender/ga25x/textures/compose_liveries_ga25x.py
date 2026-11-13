"""Compose the GA-25X livery textures (full paint colour on the GA-25X `livery` UVs, like the stock *_b livery textures)
plus ga25x_skin_b.png (= the default scheme) and ga25x_liveries.json (LiveryData values: name, faction, glossiness,
top-5 colour swatches in the stock format).

  blender --background --factory-startup --python blender/ga25x/textures/compose_liveries_ga25x.py -- <cache_dir> --out <dir>

Needs the GA-25X bake cache (blender/v2/textures/bake_maps.py on ga25x.blend) and features.npz (compose_skin.py).
Reuses the B-25H texture library (tex_lib Geo/fbm/text, faction_marks vector roundels): nothing from the game.
Everything is placed by 3D position on the model (the bake stores a world position per texel), so markings, panels and
stencils survive an atlas repack.

Schemes (visual pass 2026-10-31; lore: the GA-25X is a PALA design, the BDF flies it in its own standard camouflage):
  pala_twotone    PALA Two-Tone Grey (default)  modern counter-shaded mid/light greys, full-colour PALA roundels
  pala_matteblack PALA Matte Black              night scheme, light-grey low-contrast stencils
  bdf_temperate   BDF Temperate Camo            standard BDF grey + green disruptive camouflage (as the B-25H's), BDF roundels
  bdf_mattegrey   BDF Matte Gray                stock BDF matte grey, BDF roundels
  pala_desert     PALA Desert Camo              (0.3.1) SFB-81 style hard-edged sand / light sand / brown fragments,
                                                light blue-grey underside and fins
Modern detail common to all: radar-absorbent (RAM) panel tone variation, RAM-treated leading edges and intake lips,
dielectric panels (upper nose antenna bay, waist sensor panels, tail-cone sensor head, wing-tip antennas) with fine
outlines, flush panel lines, stencils (NO STEP, walkways, RESCUE, LASER APERTURE, HIGH VOLTAGE, INTAKE, FLARES).
"""
import bpy, sys, os, time, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'v2', 'textures'))
import tex_lib as T
import faction_marks as FM

argv = sys.argv[sys.argv.index('--') + 1:]
cache = os.path.abspath(argv[0])
out = os.path.abspath(argv[argv.index('--out') + 1])
os.makedirs(out, exist_ok=True)
F32 = np.float32
t0 = time.time()


def log(*a):
    print(f'[{time.time() - t0:6.1f}s]', *a, flush=True)


G = T.Geo(cache)
HG = T.hinge_gap(G)
F = {k: v.astype(F32) for k, v in np.load(os.path.join(cache, 'features.npz')).items()}
X, Y, Z, N = G.X, G.Y, G.Z, G.N
AA = G.ts * 0.75
c3 = lambda *v: np.array(v, F32)

GREY_UP = c3(0.505, 0.525, 0.545)      # PALA modern medium grey (upper)
GREY_UP_F = c3(0.545, 0.56, 0.575)
GREY_LO = c3(0.690, 0.700, 0.710)      # light grey (lower)
GREY_LO_F = c3(0.72, 0.725, 0.73)
PALA_BLACK = c3(0.175, 0.17, 0.168)    # stock PALA Matte Black swatches #202020-#303030 (docs/stock_ui_study.md), a touch lighter
PALA_BLACK_F = c3(0.225, 0.22, 0.215)
BDF_GREY = c3(0.475, 0.465, 0.465)     # stock BDF Matte Gray swatches #606060-#707070
BDF_GREY_F = c3(0.53, 0.52, 0.515)
CAMO_GREY = c3(0.52, 0.525, 0.52)      # BDF Temperate Camo grey #707070-#808080 + green #304020-#405040 (as the B-25H)
CAMO_GREY_F = c3(0.57, 0.575, 0.565)
CAMO_GREEN = c3(0.245, 0.30, 0.17)
# PALA Desert Camo (0.3.1, SFB-81 style: hard-edged faceted fragments of sand / light sand / brown, light blue-grey
# underside and fins; colours from the stock PALA desert schemes measured on the user's install - colours only, no
# stock texture used)
DESERT_SAND = c3(0.612, 0.541, 0.447)      # #9C8A72
DESERT_SAND_F = c3(0.650, 0.585, 0.495)
DESERT_LSAND = c3(0.690, 0.612, 0.510)     # #B09C82
DESERT_BROWN = c3(0.462, 0.369, 0.298)     # #765E4C
DESERT_LO = c3(0.384, 0.431, 0.451)        # #626E73 light blue-grey (underside, fins)
DESERT_LO_F = c3(0.415, 0.458, 0.475)
LIGHT = c3(0.60, 0.60, 0.59)
DARK = c3(0.09, 0.09, 0.095)
RED = c3(0.62, 0.10, 0.08)
SOOT = c3(0.11, 0.10, 0.09)
CHIP = c3(0.55, 0.56, 0.57)

SCHEMES = {
    'pala_twotone': dict(label='PALA Two-Tone Grey', faction='PALA', up=GREY_UP, up_fade=GREY_UP_F, lo=GREY_LO, lo_fade=GREY_LO_F,
                         serial='7251', ink=DARK, warn=RED, gloss=0.1, default=True),
    'pala_matteblack': dict(label='PALA Matte Black', faction='PALA', up=PALA_BLACK, up_fade=PALA_BLACK_F, lo=PALA_BLACK,
                            lo_fade=PALA_BLACK_F, serial='7251', ink=LIGHT * 0.75, warn=c3(0.42, 0.14, 0.12), gloss=0.0, ram_sign=1.0),
    'pala_desert': dict(label='PALA Desert Camo', faction='PALA', up=DESERT_SAND, up_fade=DESERT_SAND_F, lo=DESERT_LO, lo_fade=DESERT_LO_F,
                        facets=dict(cell=0.85, seed=21, tones=((DESERT_LSAND, 0.28), (DESERT_BROWN, 0.34))),
                        lo_parts=('fin', 'rud'), serial='7251', ink=DARK, warn=RED, gloss=0.0),
    'bdf_temperate': dict(label='BDF Temperate Camo', faction='BDF', up=CAMO_GREY, up_fade=CAMO_GREY_F, lo=CAMO_GREY, lo_fade=CAMO_GREY_F,
                          camo=dict(col=CAMO_GREEN, freq=0.30, cover=0.46, seed=7, warp=0.9, soft=0.010, octaves=3),
                          serial='2513', ink=DARK, warn=RED, gloss=0.0),
    'bdf_mattegrey': dict(label='BDF Matte Gray', faction='BDF', up=BDF_GREY, up_fade=BDF_GREY_F, lo=BDF_GREY, lo_fade=BDF_GREY_F,
                          serial='2513', ink=DARK, warn=RED, gloss=0.0),
}
SCHEMES['pala_desert'] = SCHEMES.pop('pala_desert')   # appended last: existing livery order / indices unchanged
DATA = {
    'PALA': ['PRIMEVA ARMED LIBERATION ALLIANCE', 'GA-25X GUNSHIP', 'SER. NO. 7251', 'CREW 2', 'JP FUEL / 800 V DC'],
    'BDF': ['BOSCALI DEFENSE FORCE', 'GA-25X GUNSHIP', 'SER. NO. 2513', 'CREW 2', 'JP FUEL / 800 V DC'],
}
FUS_W = {'PALA': 0.98, 'BDF': 1.30}
WING_W = {'PALA': 0.60, 'BDF': 0.84}
FUS_Y, WING_X = -4.9, 7.0
FUS = G.g('fus')


def put(base, cov, col):
    cov = np.clip(cov, 0, 1)[:, None]
    return base * (1 - cov) + col * cov


def box_line(u, v, u0, u1, v0, v1, w):
    """coverage of the outline of rectangle [u0,u1]x[v0,v1] (line width w) and the inside mask."""
    inside = (u > u0) & (u < u1) & (v > v0) & (v < v1)
    d = np.minimum(np.minimum(np.abs(u - u0), np.abs(u - u1)), np.minimum(np.abs(v - v0), np.abs(v - v1)))
    near = (u > u0 - w) & (u < u1 + w) & (v > v0 - w) & (v < v1 + w)
    cov = np.where(near, 1 - T.smoothstep(w * 0.5 - AA, w * 0.5 + AA, d), 0).astype(F32)
    return cov, inside


# ------------------------------------------------------------------ geometry-placed details
def mark_sites(kind, scale=1.0):
    """(selection, pu, pv, width) for both fuselage sides and the 4 wing surfaces (stock convention, as the B-25H)."""
    res = []
    zc, hr = G.fus_center(np.array([FUS_Y], F32))
    w = FUS_W[kind] * scale
    h = FM.height_of(kind, w)
    for s in (-1, 1):
        sel = FUS & (N[:, 0] * s > 0.3) & (np.abs(Y - FUS_Y) < w * 0.6) & (np.abs(Z - zc[0]) < h * 0.6)
        res.append((sel, (Y[sel] - FUS_Y) * (1 if s > 0 else -1), Z[sel] - zc[0], w))
    m = G.g('wing', 'flap', 'ail')
    le = float(np.interp(WING_X, G.w_x, G.w_le))
    te = float(np.interp(WING_X, G.w_x, G.w_te))
    ch = le - te
    yc = le - 0.45 * ch
    w = WING_W[kind] * ch * scale
    h = FM.height_of(kind, w)
    for s in (-1, 1):
        for top in (True, False):
            sel = m & (np.sign(X) == s) & ((N[:, 2] > 0.2) if top else (N[:, 2] < -0.2)) & \
                (np.abs(X - s * WING_X) < w * 0.6) & (np.abs(Y - yc) < h * 0.6)
            dx = X[sel] - s * WING_X
            res.append((sel, dx if top else -dx, Y[sel] - yc, w))
    return res


def side_text(y, z, lines, h, stroke, group=FUS, nx=0.5, sides=(-1, 1), dy=0.8, dz=0.4):
    res = []
    for s in sides:
        sel = group & (N[:, 0] * s > nx) & (np.abs(Y - y) < dy) & (np.abs(Z - z) < dz)
        res.append((sel, T.text_mask((Y[sel] - y) * (1 if s > 0 else -1), Z[sel] - z, lines, h, stroke, line_gap=1.5)))
    return res


def fin_serial(text):
    res = []
    zt = 2.15
    le = float(np.interp(zt, G.f_z, G.f_le))
    te = float(np.interp(zt, G.f_z, G.f_te))
    yc = (le + te) / 2 - 0.05
    for s in (-1, 1):
        sel = G.g('fin', 'rud') & (np.sign(X) == s) & (N[:, 0] * s > 0.3) & (np.abs(Z - zt) < 0.3) & (np.abs(Y - yc) < 0.8)
        res.append((sel, T.text_mask((Y[sel] - yc) * (1 if s > 0 else -1), Z[sel] - zt, [text], 0.20, 0.032)))
    return res


def data_block(kind):
    yc, s = 4.02, -1
    zc, hr = G.fus_center(np.array([yc], F32))
    zt = float(zc[0]) + 0.10
    sel = FUS & (N[:, 0] * s > 0.5) & (np.abs(Y - yc) < 0.6) & (np.abs(Z - zt) < 0.3)
    return [(sel, T.text_mask(-(Y[sel] - yc), Z[sel] - zt, DATA[kind], 0.028, 0.0055, line_gap=1.55))]


def ram_tone():
    """per-panel tone offset (-1..1): 3D cells (fuselage 1.1 m long x 0.5 m, wings 0.9 m chordwise x 1.2 m span)
    with a stable hash, so neighbouring skin panels differ slightly (radar-absorbent coating batches)."""
    cy = np.floor(Y / 1.1 + 0.37).astype(np.int64)
    cz = np.floor(Z / 0.5 + 0.21).astype(np.int64)
    cx = np.floor(X / 1.2 + 0.13).astype(np.int64)
    h = np.sin(cx * 12.9898 + cy * 78.233 + cz * 37.719 + np.sign(N[:, 0]).astype(np.int64) * 4.1) * 43758.5453
    return ((h - np.floor(h)) * 2 - 1).astype(F32)


def ram_edges():
    """RAM-treated leading edges (wing, stab, fin), intake lips, canopy frame: coverage 0-1."""
    cov = np.zeros(G.K, F32)
    m = G.g('wing')
    ch = np.interp(np.abs(X), G.w_x, G.w_le - G.w_te)
    le = np.interp(np.abs(X), G.w_x, G.w_le)
    cov = np.where(m, T.smoothstep(le - 0.075 * ch - 0.02, le - 0.075 * ch + 0.02, Y), cov)
    m = G.g('stab')
    le = np.interp(np.abs(X), G.s_x, G.s_le)
    cov = np.where(m, np.maximum(cov, T.smoothstep(le - 0.12, le - 0.08, Y)), cov)
    m = G.g('fin')
    le = np.interp(Z, G.f_z, G.f_le)
    cov = np.where(m, np.maximum(cov, T.smoothstep(le - 0.14, le - 0.10, Y)), cov)
    cov = np.where(G.g('cowl') & (Y > 2.40), 1.0, cov)                                # cowl lip + chin intake lip
    cov = np.where(G.g('canopy'), 1.0, cov)
    return cov.astype(F32)


def dielectric_panels():
    """[(selection, inside-coverage, outline-coverage)] for the flush dielectric panels."""
    res = []
    w = 0.006
    # upper nose antenna bay (where the B-25H nose guns were): 3 flush panels across the top of the nose
    top = FUS & (N[:, 2] > 0.35) & (Y > 4.62) & (Y < 5.95)
    for x0, x1, y0, y1 in ((-0.34, -0.12, 4.75, 5.55), (-0.10, 0.10, 4.70, 5.80), (0.12, 0.34, 4.75, 5.55)):
        sel = top & (X > x0 - 0.03) & (X < x1 + 0.03) & (Y > y0 - 0.03) & (Y < y1 + 0.03)
        line, inside = box_line(X[sel], Y[sel], x0, x1, y0, y1, w)
        res.append((sel, inside.astype(F32), line))
    # chin radar / antenna panel under the nose ahead of the EO ball
    bot = FUS & (N[:, 2] < -0.4) & (Y > 5.30) & (Y < 6.0) & (np.abs(X) < 0.30)
    line, inside = box_line(X[bot], Y[bot], -0.22, 0.22, 5.38, 5.90, w)
    res.append((bot, inside.astype(F32), line))
    # waist sensor panels (geometry pads in the old window band)
    for s in (-1, 1):
        sel = FUS & (N[:, 0] * s > 0.6) & (Y > -3.85) & (Y < -2.95) & (Z > 0.06) & (Z < 0.52)
        line, inside = box_line(Y[sel], Z[sel], -3.80 + 0.012, -3.00 - 0.012, 0.10 + 0.012, 0.48 - 0.012, w)
        res.append((sel, inside.astype(F32), line))
    # tail-cone sensor head
    sel = FUS & (Y < -9.70)
    res.append((sel, T.smoothstep(-9.70, -9.76, Y[sel]).astype(F32), np.zeros(int(sel.sum()), F32)))
    # wing-tip antenna caps (outer 0.35 m of the tips)
    sel = G.g('wing') & (np.abs(X) > 9.95)
    res.append((sel, T.smoothstep(9.95, 10.0, np.abs(X[sel])).astype(F32), np.zeros(int(sel.sum()), F32)))
    return res


def panel_lines():
    """flush panel lines (coverage) at fuselage stations and along the wing spars; fine and low contrast."""
    cov = np.zeros(G.K, F32)
    w = 0.005
    for ys in (5.95, 4.62, 2.60, 1.38, -1.88, -3.95, -6.10, -8.30):
        cov = np.where(FUS, np.maximum(cov, 1 - T.smoothstep(w * 0.5 - AA, w * 0.5 + AA, np.abs(Y - ys))), cov)
    # dorsal / ventral longitudinal joints
    zc = np.interp(Y, G.fus_y, (G.fus_zmax + G.fus_zmin) / 2)
    for zrel in (0.55, -0.55):
        hz = np.interp(Y, G.fus_y, (G.fus_zmax - G.fus_zmin) / 2)
        d = np.abs(Z - (zc + zrel * hz))
        cov = np.where(FUS & (np.abs(N[:, 0]) > 0.5), np.maximum(cov, 1 - T.smoothstep(w * 0.5 - AA, w * 0.5 + AA, d)), cov)
    m = G.g('wing')
    ch = np.interp(np.abs(X), G.w_x, G.w_le - G.w_te)
    le = np.interp(np.abs(X), G.w_x, G.w_le)
    for f in (0.15, 0.62):
        d = np.abs(Y - (le - f * ch))
        cov = np.where(m, np.maximum(cov, 1 - T.smoothstep(w * 0.5 - AA, w * 0.5 + AA, d)), cov)
    for xs in (2.2, 4.6, 6.15, 8.2):
        d = np.abs(np.abs(X) - xs)
        cov = np.where(m, np.maximum(cov, 1 - T.smoothstep(w * 0.5 - AA, w * 0.5 + AA, d)), cov)
    return cov


def stencils():
    """[(sel, coverage, kind)] kind: 'ink' (scheme stencil colour) or 'warn' (red)."""
    res = []
    # NO STEP on the flaps (upper)
    fl = G.g('flap') & (N[:, 2] > 0.3)
    for s in (-1, 1):
        ms = fl & (np.sign(X) == s)
        for xc in (1.5, 4.8):
            m2 = ms & (np.abs(np.abs(X) - xc) < 0.5)
            if not m2.any():
                continue
            yc = float(np.median(Y[m2]))
            res.append((m2, T.text_mask((X[m2] - s * xc), Y[m2] - yc, ['NO STEP'], 0.055, 0.010), 'ink'))
    # walkway lines on the inner wing roots (two parallel dashed-free lines)
    m = G.g('wing') & (N[:, 2] > 0.4) & (np.abs(X) > 0.85) & (np.abs(X) < 2.2)
    le = np.interp(np.abs(X), G.w_x, G.w_le)
    ch = np.interp(np.abs(X), G.w_x, G.w_le - G.w_te)
    for f in (0.18, 0.55):
        d = np.abs(Y[m] - (le[m] - f * ch[m]))
        res.append((m, (1 - T.smoothstep(0.012 - AA, 0.012 + AA, d)).astype(F32), 'ink'))
    zc, hr = G.fus_center(np.array([1.82, 3.35], F32))
    # LASER APERTURE warning on the fuselage top sides next to the turret
    res += [(s, c, 'warn') for s, c in side_text(1.82, float(zc[0] + hr[0] * 0.70), ['DANGER', 'LASER APERTURE'], 0.032, 0.006, dy=0.5, dz=0.2)]
    # RESCUE: canopy jettison / hatch under the canopy sill (both sides)
    res += [(s, c, 'warn') for s, c in side_text(3.35, float(zc[1] + hr[1] * 0.45), ['RESCUE', 'HATCH RELEASE >'], 0.034, 0.0065, dy=0.5, dz=0.2)]
    # HIGH VOLTAGE on the nacelle outboard sides (motor-generators)
    nac = G.g('nac')
    for s in (-1, 1):
        sel = nac & (N[:, 0] * s > 0.6) & (np.abs(np.abs(X) - 2.95) < 0.7) & (np.abs(Y - 0.6) < 0.5) & (np.abs(Z + 0.1) < 0.25)
        res.append((sel, T.text_mask((Y[sel] - 0.6) * (1 if s > 0 else -1), Z[sel] + 0.1, ['800 V DC', 'HIGH VOLTAGE'], 0.030, 0.006, line_gap=1.5), 'warn'))
    # INTAKE danger chevrons/text on the cowl sides
    cowl = G.g('cowl')
    for s in (-1, 1):
        sel = cowl & (N[:, 0] * s > 0.5) & (np.abs(Y - 2.05) < 0.4) & (np.abs(Z + 0.18) < 0.15)
        res.append((sel, T.text_mask((Y[sel] - 2.05) * (1 if s > 0 else -1), Z[sel] + 0.18, ['INTAKE'], 0.030, 0.006), 'warn'))
    # FLARES next to the waist dispensers
    res += [(s, c, 'ink') for s, c in side_text(-3.40, -0.12, ['FLARES'], 0.028, 0.0055, dy=0.4, dz=0.08)]
    # GA-25X type name on the nose sides
    zc2, hr2 = G.fus_center(np.array([5.0], F32))
    res += [(s, c, 'ink') for s, c in side_text(5.0, float(zc2[0]) - 0.05, ['GA-25X'], 0.07, 0.012, dy=0.5, dz=0.15)]
    return res


def camo_cover(cfg):
    """soft-edged camouflage blotches from domain-warped 3D fbm (seamless across the atlas); as the B-25H BDF Temperate."""
    P = G.P
    if cfg['warp']:
        o = np.stack([T.fbm(P, 0.22, 2, seed=cfg['seed'] + k) - 0.5 for k in (11, 12, 13)], 1) * (cfg['warp'] / 0.25)
        P = P + o.astype(F32)
    n = T.fbm(P, cfg['freq'], cfg['octaves'], seed=cfg['seed'])
    thr = float(np.quantile(n[G.inM], 1 - cfg['cover']))
    return T.smoothstep(thr - cfg['soft'], thr + cfg['soft'], n).astype(F32)


def facet_cells(cell, seed, chunk=2_000_000):
    """3D Voronoi fragments (seamless across the atlas): per texel a random value of its cell and the distance to the
    nearest cell border, for the hard-edged angular desert fragments of the stock PALA schemes (SFB-81 style)."""
    P = G.P
    o = np.stack([T.fbm(P, 0.35, 2, seed=seed + k) - 0.5 for k in (41, 42, 43)], 1) * F32(cell * 0.35)
    Q = (P + o.astype(F32)) / F32(cell)
    val = np.empty(G.K, F32)
    edge = np.empty(G.K, F32)
    offs = np.array([(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)], np.int64)
    for a in range(0, G.K, chunk):
        q = Q[a:a + chunk]
        base = np.floor(q).astype(np.int64)
        d1 = np.full(len(q), 1e9, F32)
        d2 = np.full(len(q), 1e9, F32)
        v1 = np.zeros(len(q), F32)
        for off in offs:
            c = base + off
            jit = np.stack([T._hash(c[:, 0], c[:, 1], c[:, 2], seed + k) for k in range(3)], 1)
            d = np.sqrt(((c + 0.1 + 0.8 * jit - q) ** 2).sum(1)).astype(F32)
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            v1 = np.where(closer, T._hash(c[:, 0], c[:, 1], c[:, 2], seed + 7), v1)
            d1 = np.where(closer, d, d1)
        val[a:a + chunk] = v1
        edge[a:a + chunk] = (d2 - d1) * 0.5 * cell
    return val, edge


ao_c = G.gather(T.blur(np.where(G.maskX, G.ao_full, 1.0), 1))
RAM = ram_tone()
EDGE = ram_edges()
DIEL = dielectric_panels()
PLINES = panel_lines()
STEN = stencils()
log('details placed')


def paint(sc):
    up_w = F['upper']
    facing_up = np.clip(N[:, 2], 0, 1)
    fade_amt = np.clip((F['fade'] - 0.38) * 1.6, 0, 1) * (0.3 + 0.7 * facing_up) * 0.30     # modern paint fades less
    base = sc['lo'] * (1 - up_w[:, None]) + sc['up'] * up_w[:, None]
    fcol = sc['lo_fade'] * (1 - up_w[:, None]) + sc['up_fade'] * up_w[:, None]
    base = base * (1 - fade_amt[:, None]) + fcol * fade_amt[:, None]
    for key in ('camo', 'camo2'):                                         # camo2: second blotch layer (desert)
        if not sc.get(key):
            continue
        cov = camo_cover(sc[key])
        if sc[key].get('upper_only'):                                     # EW-25 style: plain underside
            cov = cov * np.clip((up_w - 0.35) / 0.3, 0, 1)
        cc = sc[key]['col']
        ccol = cc * (1 - fade_amt[:, None]) + (cc + (sc['up_fade'] - sc['up']) * 0.6) * fade_amt[:, None]
        base = put(base, cov, ccol)
    if sc.get('facets'):                                                  # SFB-81 style fragments, upper surfaces
        fc = sc['facets']
        val, edge = facet_cells(fc['cell'], fc['seed'])
        upm = np.clip((up_w - 0.4) / 0.2, 0, 1)
        if sc.get('lo_parts'):
            upm = upm * (1 - G.g(*sc['lo_parts']))
        lo_t = 0.0
        for col, share in fc['tones']:
            m = ((val >= lo_t) & (val < lo_t + share)).astype(F32)
            m = m * np.clip(edge / AA + 0.5, 0, 1)                         # crisp, antialiased border
            ccol = col * (1 - fade_amt[:, None]) + (col + (sc['up_fade'] - sc['up']) * 0.6) * fade_amt[:, None]
            base = put(base, m * upm, ccol)
            lo_t += share
    if sc.get('lo_parts'):                                                # whole parts in the underside colour
        lp = G.g(*sc['lo_parts']).astype(F32)
        lcol = sc['lo'] * (1 - fade_amt[:, None]) + sc['lo_fade'] * fade_amt[:, None]
        base = put(base, lp, lcol)
    dark = float(base.mean()) < 0.3
    base *= (1 + 0.035 * RAM)[:, None]                                    # RAM panel batches
    base *= (1 + (0.10 if dark else -0.09) * EDGE)[:, None]               # RAM-treated edges
    for sel, inside, line in DIEL:                                        # dielectric panels + outlines
        sub = base[sel] * (1 + (0.12 if dark else 0.07) * inside)[:, None]
        base[sel] = sub * (1 - 0.30 * line)[:, None]
    base *= (1 - 0.16 * PLINES)[:, None]
    for sel, pu, pv, w in mark_sites(sc['faction']):
        sub = base[sel]
        for cov, col in FM.layers(sc['faction'], pu, pv, w, AA):
            sub = put(sub, cov, col)
        base[sel] = sub
    for sel, cov in fin_serial(sc['serial']):
        base[sel] = put(base[sel], cov, sc['ink'])
    for sel, cov in data_block(sc['faction']):
        base[sel] = put(base[sel], cov, sc['ink'])
    for sel, cov, kind in STEN:
        base[sel] = put(base[sel], cov * 0.92, sc['ink'] if kind == 'ink' else sc['warn'])
    base = put(base, np.clip(F['exhaust'] * 0.6, 0, 0.35), SOOT)       # exhaust coolers: light staining only
    base *= (1 - 0.06 * F['grime'])[:, None]
    base *= (1 - 0.05 * F['walk'])[:, None]
    base *= ((1 - 0.10 * F['seam']) * (1 - 0.01 * F['rivet']))[:, None]
    base = put(base, F['chip'] * 0.15, CHIP)
    base *= (1 - 0.20 * (1 - ao_c))[:, None]
    base = put(base, HG * 0.92, T.HINGE_GAP_COL)                       # seam fix: dark hinge gap (tex_lib.hinge_gap)
    img = G.full(np.clip(base, 0, 1))
    return T.fill_outside(img, G.maskX, 12)


def swatches(img):
    q = (np.clip(img, 0, 0.999) * 16).astype(np.int32)
    key = (q[..., 0] << 8) | (q[..., 1] << 4) | q[..., 2]
    cnt = np.bincount(key.ravel(), minlength=4096)
    top = np.argsort(cnt)[::-1][:5]
    return [dict(color='#%02X%02X%02XFF' % (((k >> 8) & 15) * 16, ((k >> 4) & 15) * 16, (k & 15) * 16), count=int(cnt[k])) for k in top]


meta = {}
for name, sc in SCHEMES.items():
    img = paint(sc)
    T.save_png(img, os.path.join(out, f'ga25x_livery_{name}.png'))
    meta[name] = dict(name=sc['label'], faction=sc['faction'], texture=f'ga25x_livery_{name}.png', glossiness=sc['gloss'],
                      colors=swatches(img), default=bool(sc.get('default')))
    if sc.get('default'):
        T.save_png(img, os.path.join(out, 'ga25x_skin_b.png'))
    log('livery', name)
with open(os.path.join(out, 'ga25x_liveries.json'), 'w') as f:
    json.dump(meta, f, indent=1)
log('done')
