"""Compose the B-25H v2 livery textures (full paint colour on the `livery` UVs, like the stock
*_b livery textures) plus b25h_skin_b.png (= the faction-neutral OD/NG scheme, the default _Livery).

  blender --background --factory-startup --python blender/v2/textures/compose_liveries.py -- <cache_dir> [--out <dir>] [--only name,...]

Needs features.npz from compose_skin.py in <cache_dir>. All markings are original drawings
(stroke font + SDF insignia in tex_lib.py), placed by projecting world positions, so they land on
the model regardless of how the atlas islands are rotated.
Also writes b25h_liveries.json: suggested LiveryData values (Glossiness, Colors swatches in the
stock format: top-5 colours quantised to 0x10 steps with texel counts).
"""
import bpy, sys, os, time, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_lib as T
import faction_marks as FM

argv = sys.argv[sys.argv.index('--') + 1:]
cache = os.path.abspath(argv[0])
out = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else T.OUT
only = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None
os.makedirs(out, exist_ok=True)
F32 = np.float32
t0 = time.time()


def log(*a):
    print(f'[{time.time() - t0:6.1f}s]', *a, flush=True)


G = T.Geo(cache)
HG = T.hinge_gap(G)
F = {k: v.astype(F32) for k, v in np.load(os.path.join(cache, 'features.npz')).items()}
log('loaded', G.K)
X, Y, Z, N = G.X, G.Y, G.Z, G.N
AA = G.ts * 0.75
c3 = lambda *v: np.array(v, F32)

# ------------------------------------------------------------------ colours (display-encoded sRGB)
OD = c3(0.285, 0.288, 0.198)          # Olive Drab 41 (new)
OD_FADE = c3(0.395, 0.372, 0.285)     # sun-faded, browner
NG = c3(0.455, 0.475, 0.49)           # Neutral Gray 43
NG_FADE = c3(0.53, 0.54, 0.55)
OD_FLAT = c3(0.235, 0.24, 0.165)      # anti-glare
DSG = c3(0.30, 0.325, 0.345)          # dark sea grey
DSG_FADE = c3(0.37, 0.39, 0.405)
LG = c3(0.62, 0.635, 0.645)           # light grey
LG_FADE = c3(0.67, 0.68, 0.685)
ALU = c3(0.70, 0.71, 0.725)
SILVER_DOPE = c3(0.62, 0.63, 0.625)
BLUE = c3(0.11, 0.155, 0.30)
WHITE = c3(0.86, 0.86, 0.835)
YELLOW = c3(0.86, 0.70, 0.17)
BLACK = c3(0.07, 0.07, 0.07)
SOOT = c3(0.11, 0.10, 0.09)
CHIP = c3(0.66, 0.67, 0.68)

SCHEMES = {
    'usaaf_od': dict(up=OD, up_fade=OD_FADE, lo=NG, lo_fade=NG_FADE, ag=OD_FLAT, insignia=True,
                     serial='34432', serial_col=YELLOW, data_col=YELLOW, stencil=BLACK, gloss=0.0),
    'usaaf_metal': dict(metal=True, ag=OD, nac_ag=True, insignia=True, serial='34432', serial_col=BLACK,
                        data_col=BLACK, stencil=BLACK, gloss=0.5),
    'od_plain': dict(up=OD, up_fade=OD_FADE, lo=NG, lo_fade=NG_FADE, ag=OD_FLAT, insignia=False,
                     stencil=BLACK, gloss=0.0),
    'darkgrey_plain': dict(up=DSG, up_fade=DSG_FADE, lo=LG, lo_fade=LG_FADE, ag=c3(0.22, 0.235, 0.25),
                           insignia=False, stencil=BLACK, gloss=0.1),
}
# ------------------------------------------------------------------ faction liveries (BDF / PALA)
# colours matched to the stock LiveryData swatches / texture medians of the same-named stock schemes
# (BDF Matte Gray #606060-#707070, BDF Temperate Camo grey #707070-#808080 + green #304020-#405040,
# PALA Matte Black #202020-#303030, PALA desert #A09080/#908070 + #806050/#705040); the base is a little
# lighter than the target because the weathering / AO pass below darkens it by ~10 %.
BDF_GREY = c3(0.455, 0.445, 0.445)
BDF_GREY_FADE = c3(0.52, 0.51, 0.505)
CAMO_GREY = c3(0.50, 0.505, 0.50)
CAMO_GREY_FADE = c3(0.56, 0.565, 0.555)
CAMO_GREEN = c3(0.235, 0.29, 0.16)
PALA_BLACK = c3(0.155, 0.15, 0.148)
PALA_BLACK_FADE = c3(0.215, 0.21, 0.205)
DESERT_TAN = c3(0.635, 0.565, 0.475)
DESERT_TAN_FADE = c3(0.69, 0.63, 0.545)
DESERT_BROWN = c3(0.47, 0.355, 0.265)
SERIAL_LIGHT = c3(0.62, 0.62, 0.60)

SCHEMES.update({
    'bdf_mattegrey': dict(label='BDF Matte Gray', faction='BDF', up=BDF_GREY, up_fade=BDF_GREY_FADE, lo=BDF_GREY,
                          lo_fade=BDF_GREY_FADE, ag=c3(0.30, 0.295, 0.295), serial='2504', serial_col=BLACK,
                          data_col=BLACK, stencil=BLACK, gloss=0.0),
    'bdf_temperate': dict(label='BDF Temperate Camo', faction='BDF', up=CAMO_GREY, up_fade=CAMO_GREY_FADE,
                          lo=CAMO_GREY, lo_fade=CAMO_GREY_FADE,
                          camo=dict(col=CAMO_GREEN, freq=0.30, cover=0.46, seed=7, warp=0.9, soft=0.010, octaves=3),
                          ag=None, serial='2504', serial_col=BLACK, data_col=BLACK, stencil=BLACK, gloss=0.0),
    'pala_matteblack': dict(label='PALA Matte Black', faction='PALA', up=PALA_BLACK, up_fade=PALA_BLACK_FADE,
                            lo=PALA_BLACK, lo_fade=PALA_BLACK_FADE, ag=None, serial='4325', serial_col=SERIAL_LIGHT,
                            data_col=SERIAL_LIGHT, stencil=SERIAL_LIGHT, gloss=0.0),
    'pala_desert': dict(label='PALA Desert Camo', faction='PALA', up=DESERT_TAN, up_fade=DESERT_TAN_FADE,
                        lo=DESERT_TAN, lo_fade=DESERT_TAN_FADE,
                        camo=dict(col=DESERT_BROWN, freq=0.36, cover=0.42, seed=23, warp=0.6, soft=0.006, octaves=4),
                        ag=None, serial='4325', serial_col=BLACK, data_col=BLACK, stencil=BLACK, gloss=0.0),
})
FACTION_DATA = {
    'BDF': ['BOSCALI DEFENSE FORCE', 'B-25H-5 MITCHELL', 'SER. NO. 2504', 'CREW WEIGHT 1000 LBS',
            'SERVICE THIS AIRPLANE WITH', '100 OCTANE FUEL'],
    'PALA': ['PRIMEVA ARMED LIBERATION ALLIANCE', 'B-25H-5 MITCHELL', 'SER. NO. 4325', 'CREW WEIGHT 1000 LBS',
             'SERVICE THIS AIRPLANE WITH', '100 OCTANE FUEL'],
}
DATA_LINES = ['U.S. ARMY', 'B-25H-5-NA', 'A.A.F. SER. NO. 43-4432', 'CREW WEIGHT 1000 LBS',
              'SERVICE THIS AIRPLANE WITH', '100 OCTANE GASOLINE']


def put(base, cov, col):
    cov = np.clip(cov, 0, 1)[:, None]
    return base * (1 - cov) + col * cov


# ------------------------------------------------------------------ marking placements (computed once)
def fus_insignia():
    m = G.g('fus')
    res = []
    yc = -4.9
    zc, hr = G.fus_center(np.array([yc], F32))
    R = 0.36
    for s in (-1, 1):
        sel = m & (N[:, 0] * s > 0.3) & (np.abs(Y - yc) < 1.0)
        pu = (Y[sel] - yc)
        pv = (Z[sel] - zc[0])
        b, w = T.star_and_bar(pu, pv, R, AA)
        res.append((sel, b, w))
    log('fuselage insignia centre z', float(zc[0]), 'half height', float(hr[0]))
    return res


def wing_insignia():
    m = G.g('wing', 'flap', 'ail')
    res = []
    xc = 7.0
    le = float(np.interp(xc, G.w_x, G.w_le))
    te = float(np.interp(xc, G.w_x, G.w_te))
    ch = le - te
    yc = le - 0.42 * ch
    R = 0.25 * ch
    for s, top in ((-1, True), (1, False)):       # upper LEFT wing, lower RIGHT wing
        sel = m & (np.sign(X) == s) & ((N[:, 2] > 0.2) if top else (N[:, 2] < -0.2)) & \
            (np.abs(np.abs(X) - xc) < 2.4 * R) & (np.abs(Y - yc) < 1.3 * R)
        pu = (np.abs(X[sel]) - xc)
        pv = (Y[sel] - yc)
        b, w = T.star_and_bar(pu, pv, R, AA)
        res.append((sel, b, w))
    log('wing insignia at |x|', xc, 'chord', round(ch, 2), 'R', round(R, 2))
    return res


def fin_serial(text):
    res = []
    zt = 2.15
    le = float(np.interp(zt, G.f_z, G.f_le))
    te = float(np.interp(zt, G.f_z, G.f_te))
    yc = (le + te) / 2 - 0.05
    for s in (-1, 1):
        sel = G.g('fin', 'rud') & (np.sign(X) == s) & (N[:, 0] * s > 0.3) & (np.abs(Z - zt) < 0.3) & (np.abs(Y - yc) < 0.8)
        pu = (Y[sel] - yc) * (1 if s > 0 else -1)     # reads left-to-right from outside
        pv = Z[sel] - zt
        cov = T.text_mask(pu, pv, [text], 0.20, 0.032)
        res.append((sel, cov))
    return res


def data_block():
    yc, s = 4.02, -1
    zc, hr = G.fus_center(np.array([yc], F32))
    zt = float(zc[0]) + 0.02
    sel = G.g('fus') & (N[:, 0] * s > 0.5) & (np.abs(Y - yc) < 0.6) & (np.abs(Z - zt) < 0.3)
    pu = -(Y[sel] - yc)
    pv = Z[sel] - zt
    cov = T.text_mask(pu, pv, DATA_LINES, 0.028, 0.0055, line_gap=1.55)
    return [(sel, cov)]


def faction_data(kind):
    yc, s = 4.02, -1
    zc, hr = G.fus_center(np.array([yc], F32))
    zt = float(zc[0]) + 0.02
    sel = G.g('fus') & (N[:, 0] * s > 0.5) & (np.abs(Y - yc) < 0.6) & (np.abs(Z - zt) < 0.3)
    pu = -(Y[sel] - yc)
    pv = Z[sel] - zt
    return [(sel, T.text_mask(pu, pv, FACTION_DATA[kind], 0.028, 0.0055, line_gap=1.55))]


def generic_stencils():
    out = []
    # NO STEP on the flaps (read from behind)
    fl = G.g('flap') & (N[:, 2] > 0.3)
    for s in (-1, 1):
        ms = fl & (np.sign(X) == s) & (np.abs(X) < 2.6)
        if not ms.any():
            continue
        xc = float(np.median(X[ms]))
        yc = float(np.median(Y[ms]))
        sel = ms & (np.abs(X - xc) < 0.4)
        out.append((sel, T.text_mask(X[sel] - xc, Y[sel] - yc, ['NO STEP'], 0.06, 0.011)))
    # fuel grade next to the filler caps
    w = G.g('wing') & (N[:, 2] > 0.3)
    for st, cc in ((1.75, 0.38), (4.6, 0.36), (5.6, 0.36)):
        le = float(np.interp(st, G.w_x, G.w_le))
        ch = float(np.interp(st, G.w_x, G.w_le - G.w_te))
        yc = le - cc * ch - 0.15
        for s in (-1, 1):
            xc = s * st
            sel = w & (np.abs(X - xc) < 0.3) & (np.abs(Y - yc) < 0.1)
            out.append((sel, T.text_mask(X[sel] - xc, Y[sel] - yc, ['100 OCT'], 0.035, 0.0065)))
    return out


# faction roundels (stock convention, see docs/stock_ui_study.md): both fuselage sides aft of the wing, and
# upper AND lower surface of both outer wings (the stock COIN carries its wing roundel on all four wing
# surfaces). Drawn un-mirrored on every surface as seen from outside; on the wings the mark's top points
# toward the nose. Placed by 3D projection like the US insignia above.
FUS_W = {'PALA': 0.98, 'BDF': 1.30}       # mark width, metres
WING_W = {'PALA': 0.60, 'BDF': 0.84}      # x local chord
FUS_Y = -4.9
WING_X = 7.0


def faction_marks(kind):
    res = []
    yc = FUS_Y
    zc, hr = G.fus_center(np.array([yc], F32))
    w = FUS_W[kind]
    h = FM.height_of(kind, w)
    for s in (-1, 1):
        sel = G.g('fus') & (N[:, 0] * s > 0.3) & (np.abs(Y - yc) < w * 0.6) & (np.abs(Z - zc[0]) < h * 0.6)
        pu = (Y[sel] - yc) * (1 if s > 0 else -1)     # viewer outside the right side sees the nose on the right
        pv = Z[sel] - zc[0]
        res.append((sel, FM.layers(kind, pu, pv, w, AA)))
    log(kind, 'fuselage mark width', w, 'height', round(h, 2), 'fuselage half height', float(hr[0]))
    m = G.g('wing', 'flap', 'ail')
    xc = WING_X
    le = float(np.interp(xc, G.w_x, G.w_le))
    te = float(np.interp(xc, G.w_x, G.w_te))
    ch = le - te
    yc = le - 0.45 * ch
    w = WING_W[kind] * ch
    h = FM.height_of(kind, w)
    for s in (-1, 1):
        for top in (True, False):
            sel = m & (np.sign(X) == s) & ((N[:, 2] > 0.2) if top else (N[:, 2] < -0.2)) & \
                (np.abs(X - s * xc) < w * 0.6) & (np.abs(Y - yc) < h * 0.6)
            dx = X[sel] - s * xc
            pu = dx if top else -dx                  # seen from below, +X is on the viewer's left
            pv = Y[sel] - yc                          # mark top toward the nose
            res.append((sel, FM.layers(kind, pu, pv, w, AA)))
    log(kind, 'wing mark width', round(w, 2), 'at |x|', xc, 'chord', round(ch, 2))
    return res


_FM_CACHE = {}


def camo_cover(cfg):
    """soft-edged camouflage blotches from domain-warped 3D fbm (seamless across the atlas)."""
    P = G.P
    warp = cfg['warp']
    if warp:
        o = np.stack([T.fbm(P, 0.22, 2, seed=cfg['seed'] + k) - 0.5 for k in (11, 12, 13)], 1) * (warp / 0.25)
        P = P + o.astype(F32)
    n = T.fbm(P, cfg['freq'], cfg['octaves'], seed=cfg['seed'])
    thr = float(np.quantile(n[G.inM], 1 - cfg['cover']))
    return T.smoothstep(thr - cfg['soft'], thr + cfg['soft'], n).astype(F32)


INS_F = fus_insignia()
INS_W = wing_insignia()
GEN = generic_stencils()
DATA = data_block()
log('markings placed')
ao_c = G.gather(T.blur(np.where(G.maskX, G.ao_full, 1.0), 1))
brushed = None


def paint(name, sc):
    global brushed
    up_w = F['upper']
    facing_up = np.clip(N[:, 2], 0, 1)
    fade_amt = np.clip((F['fade'] - 0.38) * 1.6, 0, 1) * (0.3 + 0.7 * facing_up) * 0.55
    if sc.get('metal'):
        if brushed is None:
            brushed = T.tri_sample(T.load_tile('grime_streaks', 256), G.P, N, 1.6, seed=3)
        base = np.tile(ALU, (G.K, 1))
        base *= (1 + 0.16 * (F['panel'] - 0.5))[:, None]
        base *= (0.94 + 0.12 * (brushed - brushed.mean()) / max(brushed.std(), 1e-3) * 0.25 + 0.03)[:, None]
        base = put(base, F['fabric'], SILVER_DOPE)
        chipcol = c3(0.80, 0.80, 0.82)
    else:
        base = sc['lo'] * (1 - up_w[:, None]) + sc['up'] * up_w[:, None]
        fcol = sc['lo_fade'] * (1 - up_w[:, None]) + sc['up_fade'] * up_w[:, None]
        base = base * (1 - fade_amt[:, None]) + fcol * fade_amt[:, None]
        base *= (1 + 0.05 * (F['panel'] - 0.5))[:, None]
        base *= (1 + 0.04 * F['fabric'])[:, None]
        chipcol = CHIP
    if sc.get('camo'):
        cov = camo_cover(sc['camo'])
        cc = sc['camo']['col']
        cfade = cc + (sc['up_fade'] - sc['up']) * 0.6
        ccol = cc * (1 - fade_amt[:, None]) + cfade * fade_amt[:, None]
        ccol *= (1 + 0.05 * (F['panel'] - 0.5))[:, None]
        base = put(base, cov, ccol)
    if sc.get('ag') is not None:
        base = put(base, F['antiglare'], sc['ag'])
    if sc.get('nac_ag'):
        base = put(base, F['nac_inboard'], sc['ag'])
    if sc.get('insignia'):
        for sel, b, w in INS_F + INS_W:
            sub = base[sel]
            sub = put(sub, b, BLUE)
            sub = put(sub, w, WHITE)
            base[sel] = sub
    if sc.get('faction'):
        kind = sc['faction']
        if kind not in _FM_CACHE:
            _FM_CACHE[kind] = faction_marks(kind)
        for sel, lay in _FM_CACHE[kind]:
            sub = base[sel]
            for cov, col in lay:
                sub = put(sub, cov, col)
            base[sel] = sub
    if sc.get('serial'):
        for sel, cov in fin_serial(sc['serial']):
            base[sel] = put(base[sel], cov, sc['serial_col'])
        for sel, cov in (faction_data(sc['faction']) if sc.get('faction') else DATA):
            base[sel] = put(base[sel], cov, sc['data_col'])
    for k, (sel, cov) in enumerate(GEN):
        col = sc['stencil'] if k < 2 else YELLOW
        base[sel] = put(base[sel], cov * 0.9, col)
    # weathering
    base = put(base, np.clip(F['exhaust'] * 1.9, 0, 0.85), SOOT)
    base *= (1 - 0.14 * F['grime'])[:, None]
    base *= (1 - 0.10 * F['walk'])[:, None]
    base *= ((1 - 0.24 * F['seam']) * (1 - 0.07 * F['rivet']))[:, None]
    base = put(base, F['chip'], chipcol)
    base *= (1 - 0.22 * (1 - ao_c))[:, None]
    base = put(base, HG * 0.92, T.HINGE_GAP_COL)                       # seam fix: dark hinge gap (tex_lib.hinge_gap)
    img = G.full(np.clip(base, 0, 1))
    img = T.fill_outside(img, G.maskX, 12)
    return img


def swatches(img):
    q = (np.clip(img, 0, 0.999) * 16).astype(np.int32)
    key = (q[..., 0] << 8) | (q[..., 1] << 4) | q[..., 2]
    cnt = np.bincount(key.ravel(), minlength=4096)
    top = np.argsort(cnt)[::-1][:5]
    return [dict(color='#%02X%02X%02XFF' % (((k >> 8) & 15) * 16, ((k >> 4) & 15) * 16, (k & 15) * 16),
                 count=int(cnt[k])) for k in top]


meta = {}
mpath = os.path.join(out, 'b25h_liveries.json')
if os.path.exists(mpath):
    with open(mpath) as f:
        meta = json.load(f)
for name, sc in SCHEMES.items():
    if only and name not in only and not (name == 'od_plain' and 'skin_b' in only):
        continue
    img = paint(name, sc)
    T.save_png(img, os.path.join(out, f'b25h_livery_{name}.png'))
    meta[name] = dict(texture=f'b25h_livery_{name}.png', glossiness=sc['gloss'], colors=swatches(img))
    if sc.get('faction'):
        # name = hangar label (stock naming); faction = the game's Faction.factionTag ("BDF" = Boscali.asset,
        # "PALA" = Primeva.asset). The 4 older entries carry no such keys (the build script has its own table).
        meta[name] = dict(name=sc['label'], faction=sc['faction'], **meta[name])
    if name == 'od_plain':
        T.save_png(img, os.path.join(out, 'b25h_skin_b.png'))
    log('livery', name)
with open(mpath, 'w') as f:
    json.dump(meta, f, indent=1)
log('done')
