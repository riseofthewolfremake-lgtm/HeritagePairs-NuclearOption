"""B-17G skin + 6 liveries (our own art; nothing from the War Thunder reference).

  blender --background assets/model_b17g/b17g.blend --python-exit-code 1 --python blender/b17g/textures/build_textures_b17g.py -- [--res 4096] [--out assets/textures_b17g]

Same method as the Nimrod / B-25H textures: every `paint` triangle is rasterised in its livery-atlas UV into per-texel world position /
normal / part id; panel lines, fasteners, fabric, markings and camouflage are evaluated from those 3D values (continuous over atlas seams).
Detail comes from fal tiles (assets/textures_b17g/fal_raw, fal-ai/z-image/turbo/tiling: alu_sheet, od_paint, fabric, structure, rubber).
Liveries (user decision 2026-11-03): USAAF Olive Drab / Neutral Gray and USAAF Natural Metal (both factions), BDF Olive Drab, BDF Temperate
Camo, PALA Desert Camo (crisp angular, stock PALA style), PALA Matte Black.
"""
import bpy, os, sys, json, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'blender', 'v2', 'textures'))
sys.path.insert(0, os.path.join(ROOT, 'blender', 'b17g'))
import tex_lib as T
import faction_marks as FM
import b17g_spec as S
sys.path.insert(0, os.path.join(ROOT, 'blender'))
import atlas_guard as AG   # 1.8.16: manifest of the atlas these textures are painted on
F32 = np.float32
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RES = int(argv[argv.index('--res') + 1]) if '--res' in argv else 4096
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_b17g')
FAL = os.path.join(ROOT, 'assets', 'textures_b17g', 'fal_raw')
os.makedirs(OUT, exist_ok=True)
STATS = {}


def log(*a):
    print('[btex]', *a)


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
        if 'paint' not in mats or 'livery' not in me.uv_layers:
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
            e = -0.6 / max(abs(den), 1.0) ** 0.5
            ins = (w0 >= e) & (w1 >= e) & (w2 >= e)
            if not ins.any():
                continue
            Pa = np.array([tuple(p) for p in P], F32)
            W = np.stack([w0[ins], w1[ins], w2[ins]], -1)
            yy, xx = gy[ins].astype(int), gx[ins].astype(int)
            pos[yy, xx] = W @ Pa; nrm[yy, xx] = (n.x, n.y, n.z); pid[yy, xx] = k
            tri_n += 1
    mask = pid >= 0
    STATS['paint_tris'] = tri_n; STATS['coverage'] = round(float(mask.mean()), 4)
    log(f'rasterised {tri_n} paint triangles from {len(names)} objects, coverage {mask.mean():.3f}')
    return pos, nrm, pid, names, mask


class G:
    def __init__(s, pos, nrm, pid, names, mask):
        s.mask = mask; s.P = pos[mask]; s.N = nrm[mask]; s.id = pid[mask].astype(int); s.names = names
        s.x, s.y, s.z = s.P[:, 0], s.P[:, 1], s.P[:, 2]; s.K = len(s.P)

    def g(s, *prefixes):
        ok = np.array([any(n.startswith(p) for p in prefixes) for n in s.names], bool)
        return ok[s.id]


_fal = {}


def fal_tile(name, size=512):
    if (name, size) not in _fal:
        a = T.load_image(os.path.join(FAL, name + '.png'), nonc=False)[..., :3]
        f = max(1, a.shape[0] // size)
        _fal[(name, size)] = a[:size * f, :size * f].reshape(size, f, size, f, 3).mean(axis=(1, 3)).astype(F32)
    return _fal[(name, size)]


def fal_grey_hp(name, size=512, sigma=16):
    a = fal_tile(name, size).mean(-1)
    k = np.exp(-0.5 * (np.arange(-3 * sigma, 3 * sigma + 1) / sigma) ** 2); k /= k.sum()
    pad = np.pad(a, 3 * sigma, mode='wrap')
    b = np.apply_along_axis(lambda r: np.convolve(r, k, 'valid'), 1, pad)
    b = np.apply_along_axis(lambda c: np.convolve(c, k, 'valid'), 0, b)
    h = a - b
    return ((h - h.mean()) / (h.std() + 1e-6)).astype(F32)


def tone(a, rgb, contrast=1.0):
    m = a.reshape(-1, 3).mean(0)
    return np.clip((a - m) * contrast + np.asarray(rgb, F32), 0, 1).astype(F32)


# ============================================================================================ features (panel lines, fabric, AO)
def features(G):
    K = G.K
    fus = G.g('fus_', 'B17G', 'tail_gun', 'bay_door', 'bay_hinge', 'top_race', 'ball_ring', 'chin_ring', 'radio_coaming')
    wing = G.g('wing_')
    ctrl_fabric = G.g('aileron_', 'elevator_', 'rudder')
    tail = G.g('stab_', 'elevator_', 'fin', 'rudder')
    nac = G.g('nacelle_')
    top = G.N[:, 2] > 0.2
    H = np.zeros(K, F32)
    # fuselage frames every 0.55 m + stringer lines every ~0.20 m round the section
    dy = T.periodic(G.y, 0.55, 0.1)
    ang = np.arctan2(G.x, G.z - 0.6)
    ds = T.periodic(ang * 1.15, 0.20)
    pl = np.where(fus, np.minimum(dy, np.where(np.abs(G.N[:, 2]) < 0.97, ds, 9)), 9)
    # wing: ribs every 0.60 m spanwise, spar lines chordwise
    ax = np.abs(G.x)
    dr = T.periodic(ax, 0.60, 0.2)
    pl = np.where(wing | G.g('stab_', 'fin', 'flap_'), np.minimum(pl, dr), pl)
    pl = np.where(nac, np.minimum(pl, T.periodic(G.y, 0.48)), pl)
    H += T.groove(pl, 0.0014, 0.0006)
    rivet = (pl < 0.010) & (T.periodic(np.where(dy < ds, ang * 1.15, G.y) + ax, 0.035) < 0.003)
    H += np.where(rivet & ~ctrl_fabric, 0.00025, 0)
    # round 5 (user review 2 / 13 vs 14: 'the underside is flat and featureless'): the lower wing gets its real access-panel layout -
    # removable panels between the spars (2 rows, 1.2 m pitch), the front / rear spar rivet lines, round inspection plates behind the
    # rear spar; the bomb-bay doors get their transverse stiffeners and edge fasteners. Deeper grooves than the general panel grid.
    le_t = np.array([r[1] for r in S.WING_LE], F32); le_x = np.array([r[0] for r in S.WING_LE], F32)
    te_t = np.array([r[1] for r in S.WING_TE], F32); te_x = np.array([r[0] for r in S.WING_TE], F32)
    le_y, te_y = np.interp(ax, le_x, le_t), np.interp(ax, te_x, te_t)
    chord = np.maximum(le_y - te_y, 0.3)
    sfr = (le_y - G.y) / chord
    low = wing & ~top
    in_p = (sfr > 0.19) & (sfr < 0.61) & (ax > 1.25) & (ax < 14.2)
    dxp = T.periodic(ax, 1.20, 1.25)
    dsp = np.minimum(np.minimum(np.abs(sfr - 0.19), np.abs(sfr - 0.40)), np.abs(sfr - 0.61)) * chord
    pe = np.where(in_p, np.minimum(dxp, dsp), 9)
    H += np.where(low, T.groove(pe, 0.0020, 0.0011), 0)
    fast = (pe > 0.016) & (pe < 0.026) & (T.periodic(np.where(dxp < dsp, G.y, ax), 0.045) < 0.004)
    H += np.where(low & fast, 0.00030, 0)
    spar = np.minimum(np.abs(sfr - 0.18), np.abs(sfr - 0.62)) * chord
    H += np.where(wing & (ax > 1.2), np.where((spar < 0.004) & (T.periodic(ax, 0.040) < 0.004), 0.00030, 0), 0)
    dpl = np.sqrt(T.periodic(ax, 1.20, 1.85) ** 2 + ((sfr - 0.67) * chord) ** 2)
    H += np.where(low & (ax > 1.5) & (ax < 13.8), T.groove(np.abs(dpl - 0.065), 0.0018, 0.0009) + np.where(dpl < 0.062, 0.0002, 0), 0)
    bay = G.g('bay_door')
    dst = T.periodic(G.y, 0.30, S.BAY_Y[0])
    H += np.where(bay, T.groove(dst, 0.006, 0.0005) + np.where((dst > 0.012) & (dst < 0.02) & (T.periodic(G.x, 0.05) < 0.004), 0.00025, 0), 0)
    pl = np.where(low, np.minimum(pl, pe), pl)
    # fabric control surfaces: rib tapes every 0.16 m + fal weave
    df = np.where(G.g('rudder'), T.periodic(G.z, 0.16), T.periodic(ax, 0.16))
    H += np.where(ctrl_fabric, 0.0008 * np.exp(-(df / 0.010) ** 2) - 0.0010 * np.cos(np.pi * df / 0.16) ** 2, 0)
    fab = T.tri_sample(fal_grey_hp('fabric', sigma=12), G.P, G.N, 0.25)
    alu = T.tri_sample(fal_grey_hp('alu_sheet', sigma=12), G.P, G.N, 0.80, seed=3)
    odp = T.tri_sample(fal_grey_hp('od_paint', sigma=12), G.P, G.N, 0.60, seed=5)
    H += np.where(ctrl_fabric, 0.00006 * fab, 0.000002 * alu)
    ao = np.ones(K, F32)
    ao -= np.where(fus & (G.z < 0.0) & (np.abs(G.y) < 3.5), 0.10, 0)
    ao -= np.where(wing & ~top & (ax < 2.0), 0.12 * (1 - ax / 2.0), 0)
    ao -= np.where(fus & (pl < 0.004), 0.08, 0)
    ao = np.clip(ao, 0.55, 1.0)
    wear = T.fbm(G.P, 1.2, 2, seed=7)      # 1.6.2: was (2.5, 4 octaves) - read as sandpaper in close-ups
    grime = T.fbm(G.P, 0.9, 3, seed=11)
    return dict(H=H, ao=ao, fus=fus, wing=wing, tail=tail, nac=nac, top=top, ctrl=ctrl_fabric, pl=pl, alu=alu, fab=fab, odp=odp,
                wear=wear, grime=grime)


# ============================================================================================ markings
WHITE = np.array([0.88, 0.88, 0.86], F32); BLACK = np.array([0.04, 0.04, 0.04], F32)
US_BLUE = np.array([0.10, 0.13, 0.30], F32); RED = np.array([0.55, 0.07, 0.06], F32); YELLOW = np.array([0.80, 0.62, 0.10], F32)


def put(col, cov, rgb):
    cov = np.clip(cov, 0, 1)[:, None]
    return col * (1 - cov) + np.asarray(rgb, F32)[None, :] * cov


def sites(G, F):
    """(kind, selection, pu, pv, size m) viewer-oriented local coordinates for national marks."""
    s = []
    for side in (-1, 1):
        sel = F['fus'] & (np.sign(G.x) == side) & (np.abs(G.N[:, 0]) > 0.35)
        s.append(('fus', side, sel, side * (G.y + 8.05), G.z - 0.62, 0.55))
        sel = F['wing'] & (G.N[:, 2] > 0.3) & (np.sign(G.x) == side)
        s.append(('wing_up', side, sel, G.x - side * 10.6, G.y + 0.15, 0.95))
        sel = F['wing'] & (G.N[:, 2] < -0.3) & (np.sign(G.x) == side)
        s.append(('wing_lo', side, sel, -(G.x - side * 10.6), G.y + 0.15, 0.95))
    return s


def us_marks(col, G, F):
    for kind, side, sel, pu, pv, R in sites(G, F):
        if kind == 'wing_up' and side > 0:
            continue          # USAAF: upper LEFT and lower RIGHT wing only
        if kind == 'wing_lo' and side < 0:
            continue
        near = sel & (np.abs(pu) < R * 2.3) & (np.abs(pv) < R * 1.3)
        if not near.any():
            continue
        b, w = T.star_and_bar(pu[near] if kind != 'fus' else pu[near], pv[near], R * 0.55 if kind != 'fus' else R * 0.62, 0.006)
        full = np.zeros(G.K, F32); full[near] = b; col = put(col, full, US_BLUE)
        full = np.zeros(G.K, F32); full[near] = w; col = put(col, full, WHITE)
    return col


def faction_marks(col, G, F, kind):
    for site, side, sel, pu, pv, R in sites(G, F):
        near = sel & (np.abs(pu) < R * 1.4) & (np.abs(pv) < R * 1.4)
        if not near.any():
            continue
        for cov, rgb in FM.layers(kind, pu[near], pv[near], 2 * R * (0.9 if site == 'fus' else 1.3), 0.006):
            full = np.zeros(G.K, F32); full[near] = cov
            col = put(col, full, np.asarray(rgb, F32))
    return col


def text(col, G, sel, pu, pv, s, h, stroke, rgb):
    cov = np.zeros(G.K, F32)
    if sel.any():
        cov[sel] = T.text_mask(pu[sel], pv[sel], [s], h, stroke)
    return put(col, cov, rgb)


def fin_sel(G, side):
    return G.g('fin', 'rudder') & (np.sign(G.x) == side) & (np.abs(G.N[:, 0]) > 0.5)


def tail_codes(col, G, F, serial, letter, rgb, plate=None, plate_shape='square'):
    for side in (-1, 1):
        sel = fin_sel(G, side)
        pu = side * (G.y + 12.45)
        col = text(col, G, sel, pu, G.z - 3.05, serial, 0.30, 0.05, rgb)
        if plate is not None:
            if plate_shape == 'triangle':
                sd = FM.sd_poly(pu, -(G.z - 4.15), [(0, -0.42), (0.46, 0.38), (-0.46, 0.38)])
            else:
                sd = T.sd_box(pu, G.z - 4.15, 0, 0, 0.40, 0.40)
            col = put(col, np.where(sel, 1 - T.smoothstep(-0.006, 0.006, sd), 0), plate)
        col = text(col, G, sel, pu, G.z - 4.10, letter, 0.42, 0.075, rgb if plate is None else BLACK)
    return col


def angular_camo(G, cell, cols, seed):
    """crisp angular patches (jittered-grid Voronoi in 3D, nearest seed -> one of the colours)."""
    P = G.P / cell
    base = np.floor(P).astype(np.int64)
    best = np.full(G.K, 1e9, F32); idx = np.zeros(G.K, np.int64)
    rng = lambda a, b, c, k: ((a * 73856093) ^ (b * 19349663) ^ (c * 83492791) ^ (k * 2654435761 + seed * 97)) % 1000003 / 1000003.0
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = base + np.array([dx, dy, dz])
                jx, jy, jz = rng(c[:, 0], c[:, 1], c[:, 2], 1), rng(c[:, 0], c[:, 1], c[:, 2], 2), rng(c[:, 0], c[:, 1], c[:, 2], 3)
                sp = c + np.stack([jx, jy, jz], -1)
                d = np.abs(P - sp).max(-1) * 0.6 + np.abs(P - sp).sum(-1) * 0.4      # angular metric (no round cells)
                m = d < best
                best = np.where(m, d, best)
                idx = np.where(m, (rng(c[:, 0], c[:, 1], c[:, 2], 4) * len(cols)).astype(np.int64), idx)
    return np.asarray(cols, F32)[np.clip(idx, 0, len(cols) - 1)]


AA_W = 1.25 * 42.78746805503952 / 4096     # 1.8.18: half-width of the anti-glare edge ramps in metres (1.25 texel; main() sets it from the atlas)


def glare_front_sd(x, y, a=0.76, b=0.59, y0=5.14):
    """1.8.18: plan-view signed distance (metres, < 0 inside) to the rounded front of the NM anti-glare panel: the semi-ellipse
    (x / a)^2 + ((y - y0) / b)^2 = 1 ahead of y0 (the 1.8.17 edge, same place); behind y0 the front edge does not apply (the sides are
    the 35 % / |x| 0.76 height line). First-order distance (q - 1) / |grad q|, q = the ellipse radius: exact on the axes, within
    0.3 mm of the true distance in the +-15 mm ramp band for this ellipse."""
    q = np.sqrt((x / a) ** 2 + ((y - y0) / b) ** 2)
    gq = np.sqrt((x / a ** 2) ** 2 + ((y - y0) / b ** 2) ** 2) / np.maximum(q, 1e-9)
    sd = (q - 1.0) / np.maximum(gq, 1e-9)
    return np.where(y > y0, sd, -1.0).astype(F32)


def glare_front_cov(x, y, aw, a=0.76, y0=5.14, y1=5.00):
    """1.8.18: coverage factor of the rounded front: a +-aw ramp on glare_front_sd ahead of y0. At y0 the distance is |x| - a (the
    ellipse's vertical tangent), so behind y0 the factor blends from that side line (at y0) to 1 (at y1 = 5.00, where the side edge is
    the |x| 0.76 height line anyway): no step at y0 (the 1.8.17 factor jumped there from 1 to ~0.5 in the side ramp band)."""
    sm = lambda e0, e1, v: (lambda t: t * t * (3 - 2 * t))(np.clip((v - e0) / (e1 - e0), 0, 1))
    side = sm(aw, -aw, np.abs(x) - a)
    w = sm(y1, y0, y)
    return np.where(y > y0, sm(aw, -aw, glare_front_sd(x, y, a=a, y0=y0)), 1.0 - w + w * side).astype(F32)


def livery(G, F, key):
    K = G.K
    w, gr = F['wear'], F['grime']
    upper_fus = F['fus'] & (G.z > np.interp(G.y, [-15, -8, 0, 5, 7.5], [0.55, 0.35, 0.15, 0.25, 0.35]))
    upper = np.where(F['fus'], upper_fus, G.N[:, 2] > -0.15)
    edge = T.smoothstep(-0.25, 0.05, G.N[:, 2])
    metal = False
    if key in ('usaaf_od', 'bdf_od'):
        od, ng = np.array([0.24, 0.25, 0.15], F32), np.array([0.40, 0.42, 0.42], F32)
        col = np.where(upper[:, None], od[None, :], ng[None, :])
        col = col * (0.975 + 0.03 * w[:, None]) * (1 + 0.008 * F['odp'][:, None])
        # faded OD on the control surfaces' fabric, slightly different shade (historic)
        col = np.where((F['ctrl'] & upper)[:, None], col * np.array([1.06, 1.04, 1.0], F32), col)
        if key == 'usaaf_od':
            col = us_marks(col, G, F)
            col = tail_codes(col, G, F, '42-97058', 'K', YELLOW, plate=WHITE, plate_shape='square')
        else:
            col = faction_marks(col, G, F, 'BDF')
            col = tail_codes(col, G, F, 'B-1709', '', WHITE)
        gloss = 0.12
    elif key == 'usaaf_nm':
        metal = True
        # 1.6.1 (in game 1.6.0 the NM livery read as flat white): the B-25H Natural Metal technique - a mid aluminium grey (B-25H texture
        # median ~150/255, std ~35) with strong sheet-to-sheet tone variation; ours was median 176, std 23 (b17g_livery_usaaf_nm.png)
        al = np.array([0.585, 0.595, 0.61], F32)
        col = np.tile(al, (K, 1)) * (0.98 + 0.025 * w[:, None]) * (1 + 0.012 * F['alu'][:, None])
        pan = T.vnoise(G.P * np.array([1.0, 0.6, 1.0], F32), 1.4, seed=17)
        col = col * (0.93 + 0.12 * pan[:, None])      # sheet-to-sheet tone (smooth, per panel scale)
        fabric = F['ctrl']
        col = np.where(fabric[:, None], np.array([0.62, 0.63, 0.64], F32)[None, :], col)     # silver-doped fabric surfaces
        od = np.array([0.24, 0.25, 0.15], F32)
        # 1.6.1: the anti-glare edge follows the section (above 35 % of the half height), not the face normal (a jagged per-face edge in game)
        rows = sorted(S.FUS, key=lambda r: r[0]); fy = np.array([r[0] for r in rows], F32)
        ftop = np.interp(G.y, fy, np.array([r[1] for r in rows], F32)); fbot = np.interp(G.y, fy, np.array([r[2] for r in rows], F32))
        nz = S.NACELLES['inner'][1] + 0.35 * S.NACELLES['inner'][4]
        zthr = (ftop + fbot) / 2 + 0.35 * (ftop - fbot) / 2
        if getattr(S, 'GLARE_AA1818', False):
            # 1.8.18 (in game 1.8.17: the rounded front edge was a saw-tooth close up). Cause: the semi-ellipse edge ramp was +-0.006 in
            # ell = 4.5 / 3.5 mm in metres, under half a 10.45 mm texel, so the colour was a hard per-texel step (bilinear: the iso line
            # wobbles +-0.33 texel), and the metallic / smoothness map below was a hard threshold of it. Now every anti-glare edge (side
            # line, aft end, rounded front, nacelle panels) ramps over +-AA_W = 1.25 texel in metres at the same position (iso-line wobble
            # 0.06 texel, tools/stub_tests_1818q.py), the rounded front on a plan-view signed distance, and the metal map follows the
            # coverage. Away from the edges every texel is unchanged (coverage exactly 0 / 1).
            aw = AA_W
            gf = F['fus'].astype(F32) * T.smoothstep(zthr - aw, zthr + aw, G.z) * T.smoothstep(3.95 - aw, 3.95 + aw, G.y) * T.smoothstep(6.45 + aw, 6.45 - aw, G.y)
        else:
            gf = F['fus'].astype(F32) * T.smoothstep(zthr - 0.006, zthr + 0.006, G.z) * T.smoothstep(3.94, 3.96, G.y) * T.smoothstep(6.46, 6.44, G.y)
        if getattr(S, 'NOSE1817', False):
            # 1.8.17 (reference anti-glare panel, top view of the WT nose): ahead of the windscreen the panel narrows to |x| <= 0.76 (its
            # edge rises from the 35 % line to the skin height at |x| 0.76 between y 4.55 and 5.00) and ends in a rounded front at y 5.73
            # (semi-ellipse from 5.14); the astrodome sits inside it. Aft of 4.55 unchanged.
            hw_ = np.interp(G.y, fy, np.array([r[3] for r in rows], F32)); nn_ = np.interp(G.y, fy, np.array([r[4] for r in rows], F32))
            cz_, hz_ = (ftop + fbot) / 2, (ftop - fbot) / 2
            zwt = cz_ + hz_ * np.clip(1 - np.clip(0.76 / hw_, 0, 0.999) ** nn_, 1e-6, 1) ** (1 / nn_)
            zthr2 = zthr + (zwt - zthr) * T.smoothstep(4.55, 5.00, G.y)
            if getattr(S, 'GLARE_AA1818', False):
                gf = F['fus'].astype(F32) * T.smoothstep(zthr2 - aw, zthr2 + aw, G.z) * T.smoothstep(3.95 - aw, 3.95 + aw, G.y) * glare_front_cov(G.x, G.y, aw)
            else:
                ell = np.where(G.y > 5.14, (G.x / 0.76) ** 2 + ((G.y - 5.14) / 0.59) ** 2, 0.0)
                gf = F['fus'].astype(F32) * T.smoothstep(zthr2 - 0.006, zthr2 + 0.006, G.z) * T.smoothstep(3.94, 3.96, G.y) * T.smoothstep(1.006, 0.994, ell)
        if getattr(S, 'GLARE_AA1818', False):     # the inboard nacelle panels: their aft end (y 0.2) and outboard edge (|x| 3.10) were hard booleans
            gn = (F['nac'] & G.g('nacelle_2', 'nacelle_3')).astype(F32) * T.smoothstep(0.2 - aw, 0.2 + aw, G.y) * T.smoothstep(3.10 + aw, 3.10 - aw, np.abs(G.x)) \
                * T.smoothstep(nz - aw, nz + aw, G.z)
        else:
            gn = (F['nac'] & G.g('nacelle_2', 'nacelle_3') & (G.y > 0.2) & (np.abs(G.x) < 3.10)).astype(F32) * T.smoothstep(nz - 0.006, nz + 0.006, G.z)
        gcov = np.maximum(gf, gn)          # 1.6.2: anti-aliased mask edge (it was a hard per-texel threshold: fuzzy / jagged)
        glare = gcov > 0.5
        col = put(col, gcov, od)
        metal = ~(glare | fabric)            # M1 review: no metal under the olive anti-glare paint or the doped fabric
        if getattr(S, 'GLARE_AA1818', False):
            metal = np.where(fabric, 0.0, 1.0 - gcov).astype(F32)       # 1.8.18: metal share (main() blends metallic / smoothness by it)
        col = us_marks(col, G, F)
        # 8th AF style: red tail band + red wing-tip bands; triangle plate with letter
        band = G.g('fin', 'rudder') & (G.z > 3.55) & (G.z < 3.95)
        col = put(col, band.astype(F32), RED)
        col = tail_codes(col, G, F, '44-6118', 'L', BLACK, plate=WHITE, plate_shape='triangle')
        gloss = 0.55
    elif key == 'bdf_temperate':
        n = T.fbm(G.P * np.array([1.0, 0.7, 1.0], F32), 0.42, 3, seed=3)
        g1, g2 = np.array([0.22, 0.27, 0.17], F32), np.array([0.46, 0.48, 0.47], F32)
        e2 = T.smoothstep(0.49, 0.51, n)[:, None]
        col = g1[None, :] * (1 - e2) + g2[None, :] * e2
        col = col * (0.975 + 0.03 * w[:, None])
        col = faction_marks(col, G, F, 'BDF')
        col = tail_codes(col, G, F, 'B-1712', '', BLACK)
        gloss = 0.05
    elif key == 'pala_desert':
        upc = angular_camo(G, 2.6, [(0.62, 0.52, 0.36), (0.74, 0.66, 0.50), (0.40, 0.28, 0.17)], 11)
        under = np.array([0.52, 0.58, 0.64], F32)
        col = np.where(upper[:, None], upc, under[None, :]) * (0.975 + 0.03 * w[:, None])
        col = faction_marks(col, G, F, 'PALA')
        col = tail_codes(col, G, F, 'P-1717', '', BLACK)
        gloss = 0.05
    elif key == 'pala_matteblack':
        col = np.tile(np.array([0.075, 0.075, 0.08], F32), (K, 1)) * (0.96 + 0.06 * w[:, None])
        col = faction_marks(col, G, F, 'PALA')
        col = tail_codes(col, G, F, 'P-1721', '', RED)
        gloss = 0.08
    # weathering: exhaust soot over the wing top behind each turbo, oil streaks under the nacelles, panel-line grime
    soot = np.zeros(K, F32)
    for xa in (3.10, 6.575):
        for sd in (-1, 1):
            d = np.abs(G.x - sd * xa)
            soot = np.maximum(soot, (F['wing'] | F['nac']).astype(F32) * T.smoothstep(0.45, 0.10, d) * T.smoothstep(1.2, -1.5, G.y) * T.smoothstep(-3.5, -0.5, G.y))
    col = col * (1 - 0.35 * soot[:, None] * (0.5 + 0.5 * gr[:, None]))
    col = col * (1 - 0.10 * T.smoothstep(0.004, 0.0, F['pl'])[:, None] * gr[:, None])
    return np.clip(col, 0, 1), gloss, metal


def to_img(G, vals, fill=0.0):
    ch = 1 if vals.ndim == 1 else vals.shape[1]
    img = np.full((RES, RES, ch), fill, F32)
    img[G.mask] = vals.reshape(-1, ch)
    return img if ch > 1 else img[..., 0]


def save(arr, name, alpha=None):
    T.save_png(arr, os.path.join(OUT, name + '.png'), alpha=alpha)


def top_colors(img, mask, n=5):
    q = (np.clip(img[mask], 0, 1) * 15).round().astype(int) * 16
    keys, cnt = np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2], return_counts=True)
    order = np.argsort(-cnt)[:n]
    return [dict(color='#%02X%02X%02XFF' % ((k >> 16) & 255, (k >> 8) & 255, k & 255), count=int(c)) for k, c in zip(keys[order], cnt[order])]


LIVERIES = [('usaaf_od', 'USAAF Olive Drab', 'BOTH'), ('usaaf_nm', 'USAAF Natural Metal', 'BOTH'), ('bdf_od', 'BDF Olive Drab', 'BDF'),
            ('bdf_temperate', 'BDF Temperate Camo', 'BDF'), ('pala_desert', 'PALA Desert Camo', 'PALA'), ('pala_matteblack', 'PALA Matte Black', 'PALA')]


def tiles():
    n = 512
    spec = {'structure': ('structure', (0.55, 0.57, 0.45), 0.8), 'interior': ('structure', (0.30, 0.34, 0.22), 0.5),
            'well': ('structure', (0.22, 0.24, 0.16), 0.5), 'gear': ('alu_sheet', (0.35, 0.36, 0.30), 0.5),
            'tyre': ('rubber', (0.035, 0.035, 0.035), 1.0), 'cowl': ('od_paint', (0.10, 0.10, 0.10), 0.6), 'turret': ('od_paint', (0.27, 0.28, 0.18), 0.8)}
    for k, (src, rgb, con) in spec.items():
        img = tone(fal_tile(src, n), rgb, con)
        H = fal_grey_hp(src, n, 12) * 0.0002
        save(img, f'b17g_tile_{k}_b'); save(T.encode_normal(T.normal_from_height(H.astype(F32), 2.0 / n, 1.0)), f'b17g_tile_{k}_n')


def skin_damage(G_, mask, ts):
    """1.8.9 (offline J, docs/damage_model_study.md): a real hole-order alpha. The AircraftSkin shader discards a skin pixel when the
    _BasecolorDmg alpha is below 0.52 - 0.02 / D (D = 1 - HP / 100); the 1.8.0 map had a flat alpha 0.6, so no hole ever opened and the
    parts only darkened. hole_damage189.build: world-space bullet clusters / shell holes / torn patches, the alpha by rank onto the
    coverage targets (skin open at HP 90 / 80 / 50 / 0: 1.2 / 8.5 / 17.5 / 24 %), soot rims and dents lined up with the holes; 0.62
    outside the UV islands. Only the skin (paint faces) is in this atlas: no hole on glass / tyres / props."""
    import hole_damage189 as HD
    rgb, alpha, Hh, st = HD.build(T, G_.P, scale=1.0, seed=1789, log=log)
    db = T.fill_outside(to_img(G_, rgb), mask)
    save(db, 'b17g_skin_dmg_b', alpha=to_img(G_, alpha, fill=HD.FILL_ALPHA))
    Hd = T.fill_outside(to_img(G_, Hh), mask, 8)
    save(T.encode_normal(T.normal_from_height(Hd, ts, 3.0)), 'b17g_skin_dmg_n')
    STATS.update(st); STATS['dmg_soot_mean'] = round(float(rgb.mean()), 3)
    STATS.pop('dmg_hole_fraction', None)
    log('damage maps done', st)


def write_manifest():
    """1.8.16 guard: record the livery-atlas UV these textures were painted on (model checks + Unity CHECK ALL compare against it)."""
    files = AG.atlas_textures(OUT, 'b17g')
    if '--dmg-only' in argv:
        files = [f for f in files if os.path.basename(f).startswith('b17g_skin_dmg_')]
    AG.write_manifest(os.path.join(OUT, 'b17g_atlas_manifest.json'), 'B17G', AG.scene_parts(), bpy.data.filepath, files, written_by='blender/b17g/textures/build_textures_b17g.py' + (' --dmg-only' if '--dmg-only' in argv else ''))
    log('atlas manifest', AG.atlas_hash(AG.scene_parts()))


def main():
    stats = json.loads(bpy.context.scene.get('b25_build_stats', '{}'))
    mpu = stats.get('metres_per_uv', 30.0)
    pos, nrm, pid, names, mask = rasterise()
    G_ = G(pos, nrm, pid, names, mask)
    ts = mpu / RES
    global AA_W
    AA_W = 1.25 * ts           # 1.8.18: the anti-glare edge ramps are 1.25 texel either side of the edge
    if getattr(S, 'GLARE_AA1818', False):
        STATS['glare_aa_halfwidth_mm'] = round(AA_W * 1000, 2)
    if '--dmg-only' in argv:            # 1.8.0: only the damage maps (the liveries / normals / tiles stay as built)
        skin_damage(G_, mask, ts)
        json.dump(STATS, open(os.path.join(OUT, 'b17g_textures_dmg_stats.json'), 'w'), indent=1)
        write_manifest()
        return
    F = features(G_)
    Himg = T.fill_outside(to_img(G_, F['H']), mask, 8)
    save(T.encode_normal(T.normal_from_height(Himg, ts, 1.0)), 'b17g_skin_n')
    save(T.fill_outside(to_img(G_, F['ao']), mask), 'b17g_skin_ao')
    skin_damage(G_, mask, ts)
    meta = {}
    for key, label, fac in LIVERIES:
        col, gloss, metal = livery(G_, F, key)
        img = T.fill_outside(to_img(G_, col), mask, 24)
        name = 'b17g_livery_' + key
        save(img, name)
        if key == 'usaaf_od':
            save(img, 'b17g_skin_b')
        mm = np.full(G_.K, bool(metal), bool) if isinstance(metal, bool) else metal
        if mm.dtype == np.bool_:
            met = np.where(mm, 0.85, 0.12).astype(F32)
            sm = np.where(mm, 0.62, 0.28).astype(F32)
        else:       # 1.8.18: a metal share (NM anti-glare edge ramp): 0 / 1 give exactly the values above
            met = (0.12 + (0.85 - 0.12) * mm).astype(F32)
            sm = (0.28 + (0.62 - 0.28) * mm).astype(F32)
        m = T.fill_outside(to_img(G_, np.stack([met] * 3, -1)), mask)
        a = T.fill_outside(to_img(G_, sm), mask)
        save(m, f'b17g_skin_m_{key}', alpha=a)
        meta[key] = dict(texture=name + '.png', metal=f'b17g_skin_m_{key}.png', name=label, faction=fac, glossiness=gloss, colors=top_colors(img, mask))
        log('livery', key, 'done')
    json.dump(meta, open(os.path.join(OUT, 'b17g_liveries.json'), 'w'), indent=1)
    tiles()
    STATS.update(res=RES, metres_per_uv=mpu, texel_mm=round(mpu / RES * 1000, 2))
    json.dump(STATS, open(os.path.join(OUT, 'b17g_textures_stats.json'), 'w'), indent=1)
    write_manifest()
    log('done', json.dumps(STATS))


main()
