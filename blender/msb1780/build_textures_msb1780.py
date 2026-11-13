"""MSB-17/80 skin + 4 liveries (BDF Matte Gray, BDF Temperate Camo, PALA Desert Camo, PALA Matte Black; none shared between factions).

  blender --background assets/model_msb1780/msb1780.blend --python-exit-code 1 --python blender/msb1780/build_textures_msb1780.py -- [--res 4096]

The B-17G texture builder (blender/b17g/textures/build_textures_b17g.py: rasterised paint atlas -> panel lines, rivets, AO, damage holes,
markings by 3D position; the fal tiles already in the repo, assets/textures_b17g/fal_raw) is loaded and run with the MSB names, its liveries
and tiles replaced below. No fal call. Writes assets/textures_msb1780/msb17_* + msb17_atlas_manifest.json (1.9.9: file prefix and part key msb17 / MSB17; the folder keeps its name) (the 1.8.16 atlas guard).
Liveries compared with the stock / our accepted schemes of the same name (FD-32 BDF Matte Gray, B-17G PALA desert / temperate / black).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'blender', 'b17g', 'textures', 'build_textures_b17g.py')
for p_ in (os.path.join(ROOT, 'blender', 'b17g'), HERE):
    if p_ not in sys.path:
        sys.path.insert(0, p_)
import b17g_spec      # noqa: E402
import msb_spec       # noqa: E402,F401  (patches b17g_spec: bay, splits, turrets ... as the model was built)
src = open(SRC, encoding='utf-8').read()
assert src.rstrip().endswith('main()')
src = src.rstrip()[:-len('main()')]
REPL = [
    ("os.path.join(ROOT, 'assets', 'textures_b17g')", "os.path.join(ROOT, 'assets', 'textures_msb1780')"),
    ("fus = G.g('fus_', 'B17G', 'tail_gun', 'bay_door', 'bay_hinge', 'top_race', 'ball_ring', 'chin_ring', 'radio_coaming')",
     "fus = G.g('fus_', 'MSB17', 'tail_gun', 'bay_door', 'bay_hinge', 'top_race', 'ball_ring', 'chin_ring', 'hatch_', 'side_bay_door')"),
    ("'b17g_skin_dmg_b'", "'msb17_skin_dmg_b'"), ("'b17g_skin_dmg_n'", "'msb17_skin_dmg_n'"), ("'b17g_skin_n'", "'msb17_skin_n'"),
    ("'b17g_skin_ao'", "'msb17_skin_ao'"), ("'b17g_livery_' + key", "'msb17_livery_' + key"), ("'b17g_skin_b'", "'msb17_skin_b'"),
    ("f'b17g_skin_m_{key}'", "f'msb17_skin_m_{key}'"), ("metal=f'b17g_skin_m_{key}.png'", "metal=f'msb17_skin_m_{key}.png'"),
    ("'b17g_liveries.json'", "'msb17_liveries.json'"), ("'b17g_textures_stats.json'", "'msb17_textures_stats.json'"),
    ("'b17g_textures_dmg_stats.json'", "'msb17_textures_dmg_stats.json'"),
    ("AG.atlas_textures(OUT, 'b17g')", "AG.atlas_textures(OUT, 'msb17')"), ("'b17g_skin_dmg_'", "'msb17_skin_dmg_'"),
    ("os.path.join(OUT, 'b17g_atlas_manifest.json'), 'B17G'", "os.path.join(OUT, 'msb17_atlas_manifest.json'), 'MSB17'"),
    ("written_by='blender/b17g/textures/build_textures_b17g.py'", "written_by='blender/msb1780/build_textures_msb1780.py'"),
    ("if key == 'usaaf_od':\n            save(img, 'msb17_skin_b')", "if key == DEFAULT_LIVERY:\n            save(img, 'msb17_skin_b')"),
]
for a, b in REPL:
    assert a in src, a[:70]
    src = src.replace(a, b)
ns = {'__name__': 'msb_textures', '__file__': SRC}
exec(compile(src, SRC + ' (MSB-17/80)', 'exec'), ns)
np, T, FM, G_cls, F32 = ns['np'], ns['T'], ns['FM'], ns['G'], ns['F32']
put, faction_marks, tail_codes, angular_camo = ns['put'], ns['faction_marks'], ns['tail_codes'], ns['angular_camo']
BLACK, WHITE = ns['BLACK'], ns['WHITE']
DEFAULT_LIVERY = 'bdf_mattegrey'
ns['DEFAULT_LIVERY'] = DEFAULT_LIVERY


def sites(G, F):
    """national-mark sites: fuselage sides aft of the side bays (y -9.40), outer wings (upper / lower) as the B-17G."""
    s = []
    for side in (-1, 1):
        sel = F['fus'] & (np.sign(G.x) == side) & (np.abs(G.N[:, 0]) > 0.35)
        s.append(('fus', side, sel, side * (G.y + 9.40), G.z - 0.72, 0.50))
        sel = F['wing'] & (G.N[:, 2] > 0.3) & (np.sign(G.x) == side)
        s.append(('wing_up', side, sel, G.x - side * 12.6, G.y + 0.05, 0.85))
        sel = F['wing'] & (G.N[:, 2] < -0.3) & (np.sign(G.x) == side)
        s.append(('wing_lo', side, sel, -(G.x - side * 12.6), G.y + 0.05, 0.85))
    return s


def livery(G, F, key):
    K = G.K
    w, gr = F['wear'], F['grime']
    upper_fus = F['fus'] & (G.z > np.interp(G.y, [-15, -8, 0, 5, 7.5], [0.55, 0.35, 0.15, 0.25, 0.35]))
    upper = np.where(F['fus'], upper_fus, G.N[:, 2] > -0.15)
    pan = T.vnoise(G.P * np.array([1.0, 0.6, 1.0], F32), 1.6, seed=29)     # composite / RAM panel tone (subtle)
    if key == 'bdf_mattegrey':
        col = np.tile(np.array([0.33, 0.35, 0.37], F32), (K, 1)) * (0.95 + 0.06 * w[:, None]) * (0.97 + 0.05 * pan[:, None])
        col = faction_marks(col, G, F, 'BDF')
        col = tail_codes(col, G, F, 'B-1780', '', BLACK)
        gloss = 0.10
    elif key == 'bdf_temperate':
        n = T.fbm(G.P * np.array([1.0, 0.7, 1.0], F32), 0.42, 3, seed=13)
        g1, g2 = np.array([0.22, 0.27, 0.17], F32), np.array([0.46, 0.48, 0.47], F32)
        e2 = T.smoothstep(0.49, 0.51, n)[:, None]
        col = g1[None, :] * (1 - e2) + g2[None, :] * e2
        col = col * (0.975 + 0.03 * w[:, None])
        col = faction_marks(col, G, F, 'BDF')
        col = tail_codes(col, G, F, 'B-1781', '', BLACK)
        gloss = 0.05
    elif key == 'pala_desert':
        upc = angular_camo(G, 2.6, [(0.62, 0.52, 0.36), (0.74, 0.66, 0.50), (0.40, 0.28, 0.17)], 23)
        under = np.array([0.52, 0.58, 0.64], F32)
        col = np.where(upper[:, None], upc, under[None, :]) * (0.975 + 0.03 * w[:, None])
        col = faction_marks(col, G, F, 'PALA')
        col = tail_codes(col, G, F, 'P-1780', '', BLACK)
        gloss = 0.05
    else:   # pala_matteblack
        col = np.tile(np.array([0.075, 0.075, 0.08], F32), (K, 1)) * (0.96 + 0.06 * w[:, None])
        col = faction_marks(col, G, F, 'PALA')
        col = tail_codes(col, G, F, 'P-1781', '', np.array([0.55, 0.07, 0.06], F32))
        gloss = 0.08
    # weathering: exhaust staining aft of each exhaust stub (outboard upper nacelle side, y ~1.7 / 1.2), panel-line grime
    soot = np.zeros(K, F32)
    for xa, ye in ((3.75, 1.70), (7.20, 1.20)):
        for sd in (-1, 1):
            d = np.abs(G.x - sd * xa)
            soot = np.maximum(soot, (F['wing'] | F['nac']).astype(F32) * T.smoothstep(0.40, 0.08, d) * T.smoothstep(ye + 0.1, ye - 1.2, G.y) * T.smoothstep(ye - 4.0, ye - 1.5, G.y))
    col = col * (1 - 0.30 * soot[:, None] * (0.5 + 0.5 * gr[:, None]))
    col = col * (1 - 0.10 * T.smoothstep(0.004, 0.0, F['pl'])[:, None] * gr[:, None])
    return np.clip(col, 0, 1), gloss, False


LIVERIES = [('bdf_mattegrey', 'BDF Matte Gray', 'BDF'), ('bdf_temperate', 'BDF Temperate Camo', 'BDF'),
            ('pala_desert', 'PALA Desert Camo', 'PALA'), ('pala_matteblack', 'PALA Matte Black', 'PALA')]


def tiles():
    n = 512
    tone, fal_tile, fal_grey_hp, save = ns['tone'], ns['fal_tile'], ns['fal_grey_hp'], ns['save']
    spec = {'structure': ('structure', (0.55, 0.57, 0.58), 0.8), 'interior': ('structure', (0.36, 0.37, 0.38), 0.5),
            'well': ('structure', (0.30, 0.31, 0.32), 0.5), 'gear': ('alu_sheet', (0.35, 0.36, 0.37), 0.5),
            'tyre': ('rubber', (0.035, 0.035, 0.035), 1.0), 'cowl': ('od_paint', (0.10, 0.10, 0.10), 0.6), 'turret': ('od_paint', (0.40, 0.42, 0.43), 0.6),
            # the 2080s cockpit: dark greys (SFB-81 tub tones), no B-17G zinc chromate / olive drab
            'ck_panel': ('od_paint', (0.105, 0.11, 0.115), 0.5), 'ck_wall': ('structure', (0.28, 0.29, 0.30), 0.5), 'ck_od': ('od_paint', (0.24, 0.25, 0.26), 0.5),
            'ck_floor': ('rubber', (0.12, 0.12, 0.125), 0.8), 'ck_black': ('od_paint', (0.03, 0.03, 0.032), 0.4), 'ck_bezel': ('alu_sheet', (0.11, 0.11, 0.115), 0.6)}
    for k, (s_, rgb, con) in spec.items():
        img = tone(fal_tile(s_, n), rgb, con)
        H = fal_grey_hp(s_, n, 12) * 0.0002
        save(img, f'msb17_tile_{k}_b'); save(T.encode_normal(T.normal_from_height(H.astype(F32), 2.0 / n, 1.0)), f'msb17_tile_{k}_n')


ns['sites'] = sites
ns['livery'] = livery
ns['LIVERIES'] = LIVERIES
ns['tiles'] = tiles
ns['main']()
