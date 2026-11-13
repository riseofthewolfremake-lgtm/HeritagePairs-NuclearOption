"""PBR textures for the FD-32 Nimrod (copy of blender/nimrod/textures/build_textures_nimrod.py with the FD-32 skin and liveries).

FD-32: composite / RAM skin (fal composite_ram + carbon_weave + panel_seams tiles, assets/textures_fd32/fal_raw), procedural panel
seams and fasteners following the mesh, darker radar-array bands on all four wing leading edges, BDF Matte Gray / BDF Temperate /
PALA Desert / PALA Matte Black (both factions always). The Mk I fal tiles (assets/textures_nimrod/fal_raw) are reused for the
unchanged materials (structure, tube, rubber, gunmetal, exhaust).

2026-11-02 rebuild (user review 1: "redo all assets through fal"): every surface now starts from a fal texture
(assets/textures_nimrod/fal_raw/<name>.png, fal-ai/z-image/turbo/tiling, every call in that folder's fal_manifest.jsonl):
doped fabric (wings, tail, rear fuselage) and polished aluminium (cowling) are sampled triplanar in world space over the
livery atlas (albedo modulation + height detail), the cowling louvre panels come from the fal louvre tile, the tiling
materials (structure trim, inner fabric, tube, rubber, gunmetal, exhaust, wood, aluminium, leather) are the fal tiles
tone-matched to the material colours, and the fal 3D props carry their own baked textures (nimrod_pr_<key>_b / _n).
The geometry-locked layout (rib tapes, stitching, panel lines, fasteners, markings) stays procedural so it follows the mesh.

  blender --background assets/model_nimrod/nimrod.blend --python-exit-code 1 --python blender/nimrod/textures/build_textures_nimrod.py -- [--res 2048] [--out assets/textures_nimrod]

Method (same idea as the B-25H textures, without Cycles): every `paint` triangle of the model is rasterised in its livery-atlas
UV into per-texel world position / normal / part id; every feature (fabric rib tapes, stitching, metal cowl panels, fasteners,
markings, camouflage, wear) is then evaluated from those 3D values, so it is continuous across atlas seams. Conventions as the
B-25H (measured on stock skins): _Livery = complete painted base colour; skin _b = the default livery; _m RGB = metallic,
A = smoothness; _n OpenGL (+Y = +v); _ao grey; _dmg_b multiplicative soot (mostly white), A ~0.6.
Also writes: tiling 512 textures for the non-paint materials (fd32_tile_<mat>_b/_n), the gauge atlas (nimrod_gauges.png,
4x4 cells: see nimrod_cockpit.GAUGES), the 2-blade prop blur atlas (fd32_propblur.png) and fd32_liveries.json.
"""
import bpy, os, sys, json, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'blender', 'v2', 'textures'))
import tex_lib as T          # numpy helpers (noise, dilation, normals, text, png io) - read-only reuse
import faction_marks as FM   # BDF / PALA marks (vector redraws)
sys.path.insert(0, os.path.join(ROOT, 'blender'))
import atlas_guard as AG   # 1.8.16: manifest of the atlas these textures are painted on
F32 = np.float32

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RES = int(argv[argv.index('--res') + 1]) if '--res' in argv else 2048
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_fd32')
os.makedirs(OUT, exist_ok=True)
STATS = {}


def log(*a):
    print('[ftex]', *a)


# =============================================================================================== rasterise
def rasterise():
    R = RES
    pos = np.zeros((R, R, 3), F32); nrm = np.zeros((R, R, 3), F32); pid = np.full((R, R), -1, np.int16)
    names = []
    tri_n = 0
    for ob in bpy.data.objects:
        if ob.type != 'MESH':
            continue
        me = ob.data
        mats = [m.name if m else '' for m in me.materials]
        if 'paint' not in mats:
            continue
        pi = mats.index('paint')
        names.append(ob.name); k = len(names) - 1
        uv = me.uv_layers['livery'].data
        M = ob.matrix_world; N3 = M.to_3x3().inverted().transposed()
        me.calc_loop_triangles()
        for lt in me.loop_triangles:
            if lt.material_index != pi:
                continue
            P = [M @ me.vertices[v].co for v in lt.vertices]
            U = [uv[l].uv for l in lt.loops]
            n = (N3 @ lt.normal).normalized()
            px = np.array([[u.x * R - 0.5, u.y * R - 0.5] for u in U], F32)
            x0, x1 = int(max(math.floor(px[:, 0].min()) - 1, 0)), int(min(math.ceil(px[:, 0].max()) + 1, R - 1))
            y0, y1 = int(max(math.floor(px[:, 1].min()) - 1, 0)), int(min(math.ceil(px[:, 1].max()) + 1, R - 1))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1, dtype=F32), np.arange(y0, y1 + 1, dtype=F32))
            (ax, ay), (bx, by), (cx, cy) = px
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
            w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
            w2 = 1 - w0 - w1
            e = -0.6 / max(abs(den), 1.0) ** 0.5    # conservative: include texels whose centre is just outside (seam padding)
            ins = (w0 >= e) & (w1 >= e) & (w2 >= e)
            if not ins.any():
                continue
            Pa = np.array([tuple(p) for p in P], F32)
            W = np.stack([w0[ins], w1[ins], w2[ins]], -1)
            yy, xx = gy[ins].astype(int), gx[ins].astype(int)
            pos[yy, xx] = W @ Pa
            nrm[yy, xx] = (n.x, n.y, n.z)
            pid[yy, xx] = k
            tri_n += 1
    mask = pid >= 0
    STATS['paint_tris'] = tri_n; STATS['coverage'] = round(float(mask.mean()), 4)
    log(f'rasterised {tri_n} paint triangles from {len(names)} objects, atlas coverage {mask.mean():.3f}')
    return pos, nrm, pid, names, mask


class G:
    """per-texel geometry (only masked texels, length K)"""
    def __init__(s, pos, nrm, pid, names, mask):
        s.mask = mask
        s.P = pos[mask]; s.N = nrm[mask]; s.id = pid[mask].astype(int)
        s.names = names
        s.x, s.y, s.z = s.P[:, 0], s.P[:, 1], s.P[:, 2]
        s.K = len(s.P)

    def g(s, *prefixes):
        ok = np.array([any(n.startswith(p) for p in prefixes) for n in s.names], bool)
        return ok[s.id]


# =============================================================================================== fal tiles
FAL = os.path.join(ROOT, 'assets', 'textures_nimrod', 'fal_raw')
FAL32 = os.path.join(ROOT, 'assets', 'textures_fd32', 'fal_raw')
_fal = {}


def fal_tile(name, size=512):
    """fal tile as float RGB (size x size, box-filtered from 1024)."""
    if (name, size) not in _fal:
        a = T.load_image(os.path.join(FAL32 if os.path.exists(os.path.join(FAL32, name + '.png')) else FAL, name + '.png'), nonc=False)[..., :3]
        f = a.shape[0] // size
        _fal[(name, size)] = a[:size * f, :size * f].reshape(size, f, size, f, 3).mean(axis=(1, 3)).astype(F32)
    return _fal[(name, size)]


def fal_grey(name, size=512):
    a = fal_tile(name, size).mean(-1)
    return ((a - a.mean()) / (a.std() + 1e-6)).astype(F32)          # zero-mean, unit-std detail


def fal_grey_hp(name, size=512, sigma=24):
    """high-passed fal detail (the low-frequency shading of a generated tile would blotch when tiled): zero mean, unit std."""
    a = fal_tile(name, size).mean(-1)
    k = np.exp(-0.5 * (np.arange(-3 * sigma, 3 * sigma + 1) / sigma) ** 2); k /= k.sum()
    pad = np.pad(a, 3 * sigma, mode='wrap')
    b = np.apply_along_axis(lambda r: np.convolve(r, k, 'valid'), 1, pad)
    b = np.apply_along_axis(lambda c: np.convolve(c, k, 'valid'), 0, b)
    h = a - b
    return ((h - h.mean()) / (h.std() + 1e-6)).astype(F32)


def tone(a, rgb, contrast=1.0):
    """re-centre a fal colour tile on a target mean colour (keep its variation): the material keeps the project palette."""
    m = a.reshape(-1, 3).mean(0)
    out = (a - m) * contrast + np.asarray(rgb, F32)
    return np.clip(out, 0, 1).astype(F32)


def planar_sample(tile, u, v, span):
    T_ = tile.shape[0]
    i = ((u / span) % 1.0 * T_).astype(np.int64) % T_
    j = ((v / span) % 1.0 * T_).astype(np.int64) % T_
    return tile[j, i]


# =============================================================================================== features
def features(G):
    """FD-32 composite skin: no fabric. Panel seams (recessed) + fastener rows following the mesh, radar-array LE bands, fal composite /
    carbon / seam detail (high-passed, low contrast), analytic AO."""
    K = G.K
    fus = G.g('fus_')
    wing_up = G.g('wing_upper_', 'aileron_')
    wing_lo = G.g('wing_lower_', 'flaperon_')
    tail = G.g('stab_', 'elevator_', 'fin', 'rudder')
    ctrl = G.g('aileron_', 'elevator_', 'rudder', 'flaperon_')
    struts = G.g('struts_', 'cabane', 'stab_strut_', 'gear_')
    wheels = G.g('gear_')
    metal = np.ones(K, bool)
    fabric = np.zeros(K, bool)
    top = G.N[:, 2] > 0.25
    H = np.zeros(K, F32)
    ax = np.abs(G.x)
    wings = wing_up | wing_lo
    d_span = T.periodic(ax, 0.62, 0.11)
    d_le = np.where(wing_up, np.abs(G.y - (1.28 - 0.20)), np.abs(G.y - (0.40 - 0.20)))
    pl_w = np.minimum(d_span, d_le)
    H += np.where(wings & ~ctrl, T.groove(pl_w, 0.0014, 0.0005), 0)
    d_t = np.minimum(T.periodic(ax, 0.45, 0.05), T.periodic(G.z, 0.45, 0.10))
    H += np.where(tail & ~ctrl, T.groove(d_t, 0.0012, 0.0004), 0)
    lines_y = np.array([2.27, 1.86, 1.36, 0.86, 0.32, -0.24, -1.50, -2.20, -2.90, -3.60], F32)
    dy, _ = T.nearest_station(G.y, lines_y)
    side_line = np.minimum(np.abs(G.z - 0.26), np.abs(G.z + 0.32))
    pl = np.minimum(dy, np.where(ax > 0.2, side_line, 9))
    H += np.where(fus, T.groove(pl, 0.0016, 0.0006), 0)
    fast = (pl < 0.010) & (T.periodic(np.where(dy < side_line, ax + np.abs(G.z), G.y), 0.075) < 0.0035)
    fastw = (pl_w < 0.010) & (T.periodic(np.where(d_span < d_le, G.y, ax), 0.075) < 0.0035) & wings
    H += np.where((fus & fast) | (fastw & ~ctrl), -0.00025, 0)
    radar = ((wing_up & (ax > 0.85) & (ax < 4.6) & (G.y > 1.28 - 0.16)) | (wing_lo & (ax > 0.7) & (ax < 4.1) & (G.y > 0.40 - 0.16))) & ~ctrl
    comp = T.tri_sample(fal_grey_hp('composite_ram', sigma=10), G.P, G.N, 0.55, seed=3)
    carb = T.tri_sample(fal_grey_hp('carbon_weave', sigma=6), G.P, G.N, 0.09, seed=5)
    seams = T.tri_sample(fal_grey_hp('panel_seams', sigma=8), G.P, G.N, 0.9, seed=9)
    H += 0.000005 * comp + np.where(struts, 0.000004 * carb, 0) + 0.000002 * seams
    ao = np.ones(K, F32)
    ao -= np.where(wing_lo & top & (ax < 1.2), 0.18 * (1 - ax / 1.2), 0)
    ao -= np.where(fus & (G.z > 0.3) & (G.y > -0.2) & (G.y < 1.3), 0.10, 0)
    ao -= np.where(wing_up & ~top & (ax < 1.0), 0.15 * (1 - ax), 0)
    ao -= np.where(fus & (G.z < -0.45), 0.08, 0)
    ao = np.clip(ao, 0.5, 1.0)
    wear = T.fbm(G.P, 3.0, 4, seed=7)
    grime = T.fbm(G.P, 1.2, 3, seed=11)
    detail = (1.0 + 0.018 * comp + np.where(struts, 0.05 * carb, 0)).astype(F32)
    louv = np.zeros(K, bool)
    return dict(H=H, ao=ao, metal=metal, fabric=fabric, wing_up=wing_up, wing_lo=wing_lo, tail=tail, fus=fus, top=top, radar=radar,
                struts=struts, wheels=wheels, wear=wear, grime=grime, ctrl=ctrl, detail=detail, louv=louv, seam=pl, seam_w=pl_w)


# =============================================================================================== markings
BLUE = np.array([0.12, 0.17, 0.42], F32); RED = np.array([0.62, 0.08, 0.07], F32); WHITE = np.array([0.90, 0.90, 0.88], F32)
BLACK = np.array([0.04, 0.04, 0.04], F32)


def disc_cov(du, dv, r, aa=0.004):
    return 1 - T.smoothstep(r - aa, r + aa, np.sqrt(du * du + dv * dv))


def put(col, cov, rgb):
    cov = np.clip(cov, 0, 1)[:, None]
    return col * (1 - cov) + rgb[None, :] * cov


def roundel_typeA(col, du, dv, R, sel):
    for r, c in ((1.0, BLUE), (0.66, WHITE), (0.33, RED)):
        col = put(col, np.where(sel, disc_cov(du, dv, R * r), 0), c)
    return col


def mark_sites(G, F):
    """(selection, pu, pv, size) for roundel / national-mark sites, viewer-oriented local coordinates."""
    s = []
    for side in (-1, 1):
        sel = F['wing_up'] & F['top'] & (np.sign(G.x) == side)
        s.append(('upper', sel, G.x - side * 3.55, G.y - 0.55, 0.56))
        sel = F['wing_lo'] & (G.N[:, 2] < -0.25) & (np.sign(G.x) == side)
        s.append(('lower', sel, -(G.x - side * 2.85), G.y + 0.30, 0.50))
        sel = F['fus'] & (np.sign(G.x) == side) & (np.abs(G.N[:, 0]) > 0.4)
        s.append(('fus', sel, side * (G.y + 2.12), G.z + 0.06, 0.29))
    return s


def text_on(col, G, sel, pu, pv, text, h, stroke, rgb):
    cov = np.zeros(G.K, F32)
    if sel.any():
        cov[sel] = T.text_mask(pu[sel], pv[sel], [text], h, stroke)
    return put(col, cov, rgb)


def nat_marks(col, G, F, kind):
    for site, sel, pu, pv, R in mark_sites(G, F):
        if not sel.any():
            continue
        if kind == 'RAF':
            col = roundel_typeA(col, pu, pv, R, sel)
        else:
            near = sel & (np.abs(pu) < R * 1.3) & (np.abs(pv) < R * 1.3)
            if near.any():
                for cov, rgb in FM.layers(kind, pu[near], pv[near], 2 * R, 0.004):
                    full = np.zeros(G.K, F32); full[near] = cov
                    col = put(col, full, np.asarray(rgb, F32))
    return col


def serials(col, G, F, text, rgb, small=False):
    for side in (-1, 1):
        sel = F['fus'] & (np.sign(G.x) == side) & (np.abs(G.N[:, 0]) > 0.4) & (G.y < -2.6) & (G.y > -4.1)
        col = text_on(col, G, sel, side * (G.y + 3.30), G.z + 0.02, text, 0.13 if not small else 0.09, 0.022, rgb)
        if not small:
            sel = F['wing_lo'] & (G.N[:, 2] < -0.25) & (np.sign(G.x) == side)
            col = text_on(col, G, sel, -(G.x - side * 1.35), G.y + 0.30, text if side < 0 else text, 0.40, 0.065, rgb)
    return col


# =============================================================================================== liveries
LIV_W = {}      # round 8: per-livery camo weight (camo pattern x upper/underside) per sample, for the edge smoothing in main()


def livery(G, F, key):
    K = G.K
    w, gr = F['wear'], F['grime']
    LIV_W.pop(key, None)
    if key == 'bdf_mattegrey':
        base = np.array([0.33, 0.35, 0.37], F32)
        col = np.tile(base, (K, 1)) * (0.95 + 0.06 * w[:, None])
    elif key == 'pala_matteblack':
        base = np.array([0.085, 0.085, 0.09], F32)
        col = np.tile(base, (K, 1)) * (0.92 + 0.12 * w[:, None])
    else:
        n = T.fbm(G.P * np.array([1.0, 0.6, 1.0], F32), 0.95, 3, seed=3 if key == 'bdf_temperate' else 5)
        upper = (G.N[:, 2] > -0.30)
        if key == 'bdf_temperate':
            a, b, under = np.array([0.20, 0.25, 0.15], F32), np.array([0.36, 0.38, 0.36], F32), np.array([0.58, 0.62, 0.64], F32)
        else:   # PALA desert (PALA aircraft mostly fly desert): sand / brown disruptive, pale blue-grey underside
            a, b, under = np.array([0.66, 0.55, 0.36], F32), np.array([0.40, 0.27, 0.16], F32), np.array([0.62, 0.68, 0.74], F32)
        edge = T.smoothstep(0.485, 0.515, n)[:, None]
        camo = a[None, :] * (1 - edge) + b[None, :] * edge
        up_w = T.smoothstep(-0.42, -0.18, G.N[:, 2])[:, None]                     # round 7: soft upper / underside boundary (a hard N.z cut stepped per texel)
        col = (camo * up_w + under[None, :] * (1 - up_w)) * (0.95 + 0.07 * w[:, None])
        LIV_W[key] = (up_w[:, 0] * 2.0 + edge[:, 0]).astype(F32)
    col = col * np.where(F['radar'][:, None], 0.72, 1.0)                      # radar-array LE bands: darker RAM panels
    col = col * (1 - 0.18 * (F['seam'] < 0.0012)[:, None] - 0.12 * ((F['seam_w'] < 0.0010) & (F['wing_up'] | F['wing_lo']))[:, None])
    kind = 'BDF' if key.startswith('bdf') else 'PALA'
    col = nat_marks(col, G, F, kind)
    col = serials(col, G, F, 'FD-32' if kind == 'BDF' else 'P-32', WHITE * 0.85 if key != 'bdf_mattegrey' else BLACK, small=True)
    sw = (0.08 + np.clip(0.5 - G.y, 0, None) * 0.02)                          # light heat staining aft of the exhaust ports
    soot = (F['fus'] & (np.abs(G.x) > 0.25) & (G.y > -1.2) & (G.y < 1.8)).astype(F32) * T.smoothstep(sw, sw * 0.4, np.abs(G.z - 0.06)) * T.smoothstep(0.30, 0.0, G.y)
    col = col * (1 - 0.18 * soot[:, None] * (0.5 + 0.5 * gr[:, None]))
    col = col * F['detail'][:, None]
    return np.clip(col, 0, 1), 0.2


# =============================================================================================== image assembly
def to_img(G, vals, fill=0.0):
    ch = 1 if vals.ndim == 1 else vals.shape[1]
    img = np.full((RES, RES, ch), fill, F32)
    img[G.mask] = vals.reshape(-1, ch)
    return img if ch > 1 else img[..., 0]


def finish(img, mask, iters=24):
    return T.fill_outside(img, mask, iters)


def save(arr, name):
    T.save_png(arr, os.path.join(OUT, name + '.png'))


def top_colors(img, mask, n=5):
    q = (np.clip(img[mask], 0, 1) * 15).round().astype(int) * 16
    keys, cnt = np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2], return_counts=True)
    order = np.argsort(-cnt)[:n]
    return [dict(color='#%02X%02X%02XFF' % ((k >> 16) & 255, (k >> 8) & 255, k & 255), count=int(c)) for k, c in zip(keys[order], cnt[order])]


LIVERIES = [('bdf_mattegrey', 'BDF Matte Gray', 'BDF', False), ('bdf_temperate', 'BDF Temperate Camo', 'BDF', False),
            ('pala_desert', 'PALA Desert Camo', 'PALA', False), ('pala_matteblack', 'PALA Matte Black', 'PALA', False)]
DEFAULT_LIVERY = 'bdf_mattegrey'


def skin(G, F, metres_per_uv):
    ts = metres_per_uv / RES
    Himg = finish(to_img(G, F['H']), G.mask, 8)
    nmap = T.normal_from_height(Himg, ts, 1.0)
    save(T.encode_normal(nmap), 'fd32_skin_n')
    met = np.where(F['radar'], 0.05, 0.20).astype(F32)
    smooth = np.where(F['radar'], 0.30, 0.22 + 0.05 * F['wear']).astype(F32)
    m = finish(to_img(G, np.stack([met, met, met], -1)), G.mask)
    a = finish(to_img(G, smooth), G.mask)
    T.save_png(m, os.path.join(OUT, 'fd32_skin_m.png'), alpha=a)
    save(finish(to_img(G, F['ao']), G.mask), 'fd32_skin_ao')
    skin_damage(G, ts)


def skin_damage(G, ts):
    """1.8.9 (offline J, docs/damage_model_study.md): a real hole-order alpha (the 1.5.x map had a flat alpha 0.6: the AircraftSkin shader
    never cut a hole, discard below 0.52 - 0.02 / D). hole_damage189.build at the aircraft's size (scale 0.58): world-space bullet
    clusters / shell holes / torn patches, alpha by rank onto the coverage targets, soot rims and dents with the holes, 0.62 outside the
    UV islands; only the skin (paint faces) is in this atlas."""
    import hole_damage189 as HD
    rgb, alpha, Hh, st = HD.build(T, G.P, scale=0.58, seed=2032, log=log)
    db = finish(to_img(G, rgb), G.mask)
    T.save_png(db, os.path.join(OUT, 'fd32_skin_dmg_b.png'), alpha=to_img(G, alpha, fill=HD.FILL_ALPHA))
    Hd = finish(to_img(G, Hh), G.mask, 8)
    save(T.encode_normal(T.normal_from_height(Hd, ts, 3.0)), 'fd32_skin_dmg_n')
    STATS.update(st)
    log('damage maps done', st)


def tiles():
    """512 tiling textures for the non-paint materials (detail UV = 2 m per unit), all from fal tiles tone-matched to the material
    colours. Height for the normal map = the fal tile's luminance detail."""
    n = 512
    spec = {   # material: (fal tile, mean colour, contrast, normal strength); fd32 fal_raw first, then the Mk I fal_raw
        'alu': ('alu_sheet', (0.70, 0.71, 0.72), 0.5, 0.00005),
        'interior': ('composite_ram', (0.30, 0.31, 0.32), 0.6, 0.0002),
        'tube': ('carbon_weave', (0.10, 0.10, 0.11), 1.0, 0.0001),
        'rubber': ('rubber', (0.035, 0.035, 0.035), 1.0, 0.0004),
        'gunmetal': ('gunmetal', (0.12, 0.12, 0.13), 0.8, 0.0002),
        'structure': ('carbon_weave', (0.16, 0.16, 0.17), 1.0, 0.0003),
        'fabric_in': ('composite_ram', (0.26, 0.27, 0.27), 0.8, 0.00015),
        'exhaust': ('exhaust_steel', (0.12, 0.10, 0.09), 1.0, 0.0003),
        'metal_dark': ('gunmetal', (0.08, 0.08, 0.085), 0.6, 0.0002),
        'ck_modern': ('ck_modern', (0.20, 0.21, 0.22), 1.0, 0.0002),
        'ck_mat': ('ck_mat', (0.05, 0.05, 0.05), 1.0, 0.0006),
        'ck_grey': ('ck_paint', (0.40, 0.42, 0.43), 1.0, 0.0001),
        'ck_crinkle': ('ck_crinkle', (0.035, 0.035, 0.037), 1.0, 0.0002),
        'ck_rubber': ('rubber', (0.03, 0.03, 0.03), 1.0, 0.0004),
        'ck_lining': ('ck_modern', (0.20, 0.21, 0.22), 1.0, 0.0002),
    }
    for k, (src, rgb, con, hs) in spec.items():
        if src == 'alu_sheet':      # polished sheet: flat colour + high-passed polish lines only (no tiled shading blotches)
            hp = fal_grey_hp(src, n, sigma=12)
            img = np.clip(np.asarray(rgb, F32)[None, None, :] * (1.0 + 0.02 * hp[..., None]), 0, 1)
            H = hp * hs
        else:
            img = tone(fal_tile(src, n), rgb, con)
            H = fal_grey(src, n) * hs
        save(img, f'fd32_tile_{k}_b')
        save(T.encode_normal(T.normal_from_height(H.astype(F32), 2.0 / n, 1.0)), f'fd32_tile_{k}_n')
    log('tiles from fal:', ', '.join(f'{k}<-{v[0]}' for k, v in spec.items()))


# =============================================================================================== gauges + prop blur
def gauges():
    """2048 atlas, 4x4 cells (cell = (row * 4 + col), row 0 at the bottom = v 0). Black dials, cream markings."""
    N = 2048; C = N // 4
    img = np.zeros((N, N, 3), F32)
    yy, xx = np.mgrid[0:C, 0:C].astype(F32)
    u = (xx + 0.5) / C * 2 - 1; v = (yy + 0.5) / C * 2 - 1          # cell local -1..1 (v up)
    r = np.sqrt(u * u + v * v); th = np.degrees(np.arctan2(u, v))   # 0 = 12 o'clock, clockwise positive
    CREAM = np.array([0.93, 0.90, 0.80], F32)
    def cell_put(cell, arr):
        cx, cy = cell % 4, cell // 4
        img[cy * C:(cy + 1) * C, cx * C:(cx + 1) * C] = arr
    def dial(sweep, v0, v1, major, minor, labels, title, start=0.0):
        a = np.zeros((C, C, 3), F32) + np.array([0.035, 0.035, 0.035], F32)
        rim = (r > 0.96) & (r < 1.0)
        a[rim] = (0.12, 0.12, 0.12)
        def ticks(step, l0, w):
            m = np.zeros((C, C), bool)
            val = v0
            while val <= v1 + 1e-6:
                ang = start + (val - v0) / (v1 - v0) * sweep
                d = np.abs(((th - ang + 180) % 360) - 180)
                m |= (d < w) & (r > l0) & (r < 0.94)
                val += step
            return m
        a[ticks(minor, 0.84, 0.9)] = CREAM
        a[ticks(major, 0.74, 1.5)] = CREAM
        for val, txt in labels:
            ang = math.radians(start + (val - v0) / (v1 - v0) * sweep)
            cxl, cyl = 0.58 * math.sin(ang), 0.58 * math.cos(ang)
            cov = T.text_mask(u - cxl, v - cyl, [txt], 0.11, 0.022)
            a = a * (1 - cov[..., None]) + CREAM * cov[..., None]
        if title:
            cov = T.text_mask(u, v + 0.30, [title], 0.075, 0.016)
            a = a * (1 - cov[..., None]) + CREAM * cov[..., None]
        return a
    cell_put(1, dial(330, 0, 260, 20, 10, [(0, '0'), (40, '40'), (80, '80'), (120, '120'), (160, '160'), (200, '200'), (240, '240')], 'KNOTS'))
    cell_put(2, dial(360, 0, 10, 1, 0.5, [(k, str(k)) for k in range(0, 10)], 'FT X 1000'))
    cell_put(3, dial(300, 0, 30, 5, 1, [(k, str(k)) for k in range(0, 31, 5)], 'RPM X 100'))
    cell_put(4, dial(270, -4, 8, 2, 1, [(-4, '-4'), (0, '0'), (4, '4'), (8, '8')], 'BOOST', start=-135))
    cell_put(5, dial(270, 0, 100, 20, 10, [(0, '0'), (50, '50'), (100, '100')], 'OIL LB', start=-135))
    cell_put(6, dial(270, 0, 100, 20, 10, [(0, '0'), (50, '50'), (100, '100')], 'OIL C', start=-135))
    cell_put(7, dial(270, 0, 140, 20, 10, [(0, '0'), (60, '60'), (120, '120')], 'RAD C', start=-135))
    cell_put(8, dial(270, 0, 100, 25, 12.5, [(0, 'E'), (50, '1/2'), (100, 'F')], 'FUEL', start=-135))
    # turn and slip: L / R marks, ball tube arc
    a = np.zeros((C, C, 3), F32) + 0.035
    for ang in (-30, 0, 30):
        d = np.abs(((th - ang + 180) % 360) - 180)
        a[(d < 2.0) & (r > 0.70) & (r < 0.92)] = CREAM
    tube = (np.abs(r - 0.62) < 0.07) & (v < -0.30)
    a[tube] = (0.75, 0.72, 0.62)
    a[(np.abs(u) < 0.012) & tube] = 0.05
    for txt, cx in (('L', -0.55), ('R', 0.55)):
        cov = T.text_mask(u - cx, v - 0.15, [txt], 0.14, 0.03); a = a * (1 - cov[..., None]) + CREAM * cov[..., None]
    cov = T.text_mask(u, v - 0.40, ['TURN'], 0.08, 0.017); a = a * (1 - cov[..., None]) + CREAM * cov[..., None]
    cell_put(0, a)
    # clock
    cell_put(9, dial(360, 0, 12, 1, 0.2, [(k, str(k if k else 12)) for k in range(0, 12, 3)], ''))
    # compass card (cream card, black letters)
    a = np.zeros((C, C, 3), F32) + np.array([0.80, 0.77, 0.66], F32)
    for k in range(0, 360, 10):
        d = np.abs(((th - k + 180) % 360) - 180)
        a[(d < (1.4 if k % 30 == 0 else 0.6)) & (r > (0.80 if k % 30 else 0.70)) & (r < 0.95)] = 0.05
    for txt, ang in (('N', 0), ('E', 90), ('S', 180), ('W', 270)):
        cxl, cyl = 0.55 * math.sin(math.radians(ang)), 0.55 * math.cos(math.radians(ang))
        cov = T.text_mask(u - cxl, v - cyl, [txt], 0.14, 0.03); a = a * (1 - cov[..., None]) + 0.05 * cov[..., None]
    a[r > 0.98] = 0.05
    cell_put(10, a)
    cell_put(11, np.zeros((C, C, 3), F32) + CREAM)                                  # needle white
    a = np.zeros((C, C, 3), F32) + 0.03; a[r < 0.8] = (0.02, 0.02, 0.02); cell_put(12, a)   # slip ball (black)
    a = np.zeros((C, C, 3), F32) + np.array([0.55, 0.55, 0.52], F32)                  # data plate
    cov = T.text_mask(u, v, ['NIMROD', 'S1577', 'KESTREL V'], 0.13, 0.025)
    cell_put(13, a * (1 - cov[..., None]) + 0.05 * cov[..., None])
    cell_put(15, np.zeros((C, C, 3), F32) + 0.02)
    save(img, 'nimrod_gauges')


def propblur():
    """512 x 1024: upper half = 2-blade smear (stage 1), lower half = full disc (stage 2); wood + yellow-free tips, alpha."""
    W, Hh = 512, 1024
    out = np.zeros((Hh, W, 4), F32)
    for half, smear in ((0, False), (1, True)):
        yy, xx = np.mgrid[0:512, 0:W].astype(F32)
        cx, cy = (xx + 0.5 - 256) / 250, (yy + 0.5 - 256) / 250
        r = np.sqrt(cx * cx + cy * cy)
        edge = np.clip((1 - r) * 60, 0, 1) * np.clip((r - 0.17) * 30, 0, 1)
        if smear:
            th = np.degrees(np.arctan2(cy, cx))
            d = np.abs(((th + 45) % 90) - 45)          # 4 blades
            wdt = 8 + 22 * r
            a = (0.06 + 0.60 * np.exp(-(d / wdt) ** 2)) * edge
        else:
            a = (0.15 + 0.03 * np.sin(r * 50)) * edge
        col = np.array([0.13, 0.13, 0.14], F32)
        out[half * 512:(half + 1) * 512, :, :3] = col
        out[half * 512:(half + 1) * 512, :, 3] = a
    T.save_png(out[..., :3], os.path.join(OUT, 'fd32_propblur.png'), alpha=out[..., 3])


# =============================================================================================== main
def write_manifest(dmg_only=False):
    """1.8.16 guard: record the livery-atlas UV these textures were painted on (model checks + Unity CHECK ALL compare against it)."""
    files = AG.atlas_textures(OUT, 'fd32')
    if dmg_only:
        files = [f for f in files if os.path.basename(f).startswith('fd32_skin_dmg_')]
    m = AG.write_manifest(os.path.join(OUT, 'fd32_atlas_manifest.json'), 'FD32', AG.scene_parts(), bpy.data.filepath, files,
                          written_by='blender/fd32/textures/build_textures_fd32.py' + (' --dmg-only' if dmg_only else ''))
    log('atlas manifest', m['atlas_hash'])


def main():
    stats = json.loads(bpy.context.scene.get('b25_build_stats', '{}'))
    mpu = stats.get('metres_per_uv', 10.0)
    pos, nrm, pid, names, mask = rasterise()
    G_ = G(pos, nrm, pid, names, mask)
    if '--dmg-only' in argv:            # 1.8.9: only the damage maps (liveries / normals / tiles stay as built)
        skin_damage(G_, mpu / RES)
        json.dump(STATS, open(os.path.join(OUT, 'fd32_textures_dmg_stats.json'), 'w'), indent=1)
        log('damage-only done', json.dumps(STATS))
        write_manifest(True)
        return
    F = features(G_)
    skin(G_, F, mpu)
    meta = {}
    for key, label, fac, both in LIVERIES:
        col, gloss = livery(G_, F, key)
        img = finish(to_img(G_, col), mask)
        if key in LIV_W:
            # round 8 (in-game 1.5.3: the camo / underside edge still stair-stepped at the flaperon and the nose chin, where a sharp edge
            # crosses the atlas diagonally): soften the colour only inside the camo-edge zone (where the camo weight changes within 2
            # texels), with a mask-normalised blur (no bleed from outside the islands); markings and panel lines elsewhere stay sharp
            Wi = to_img(G_, LIV_W[key]); mf = mask.astype(F32)
            zone = (np.abs(Wi - T.blur(Wi * mf, 2) / np.maximum(T.blur(mf, 2), 1e-3)) > 0.03) & mask
            zone = T.blur(zone.astype(F32), 1) > 0.05
            num = T.blur(img * mf[..., None], 2); den = np.maximum(T.blur(mf, 2), 1e-3)[..., None]
            img = np.where((zone & mask)[..., None], num / den, img)
            STATS.setdefault('camo_edge_texels', {})[key] = int((zone & mask).sum())
        name = 'fd32_livery_' + key
        save(img, name)
        if key == DEFAULT_LIVERY:
            save(img, 'fd32_skin_b')
        meta[key] = dict(texture=name + '.png', name=label, label=label, faction=fac, both=both, glossiness=gloss, colors=top_colors(img, mask))
    json.dump(meta, open(os.path.join(OUT, 'fd32_liveries.json'), 'w'), indent=1)
    tiles(); propblur()          # prop textures (PIL): make_cockpit_art_nimrod.py          # gauge atlas + cockpit art: make_cockpit_art_nimrod.py (PIL, run after this)
    STATS['res'] = RES; STATS['metres_per_uv'] = mpu; STATS['texel_mm'] = round(mpu / RES * 1000, 2)
    json.dump(STATS, open(os.path.join(OUT, 'fd32_textures_stats.json'), 'w'), indent=1)
    write_manifest()
    log('done', json.dumps(STATS))


main()
