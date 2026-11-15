"""PBR textures for the Hawker Nimrod Mk I (our own art; nothing from the WT reference).

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
Also writes: tiling 512 textures for the non-paint materials (nimrod_tile_<mat>_b/_n), the gauge atlas (nimrod_gauges.png,
4x4 cells: see nimrod_cockpit.GAUGES), the 2-blade prop blur atlas (nimrod_propblur.png) and nimrod_liveries.json.
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
sys.path.insert(0, HERE)
import naval1912 as NV     # 1.9.12: the two naval liveries (numbers, json / manifest merge; numpy only, stub-tested)
F32 = np.float32

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RES = int(argv[argv.index('--res') + 1]) if '--res' in argv else 2048
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_nimrod')
os.makedirs(OUT, exist_ok=True)
STATS = {}
if '--naval-no-fal' in argv:        # 1.9.12 review only (A / B of the fal grime layer): never with the repo's texture folder as --out
    assert os.path.normcase(OUT) != os.path.normcase(os.path.join(ROOT, 'assets', 'textures_nimrod')), '--naval-no-fal is a review bake: give another --out'
    NV.GRIME_AMOUNT = 0.0


def log(*a):
    print('[ntex]', *a)


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
_fal = {}


def fal_tile(name, size=512):
    """fal tile as float RGB (size x size, box-filtered from 1024)."""
    if (name, size) not in _fal:
        a = T.load_image(os.path.join(FAL, name + '.png'), nonc=False)[..., :3]
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
    K = G.K
    fus = G.g('fus_')
    eng = G.g('fus_engine')
    metal = (fus & (G.y > -0.26)) | G.g('wing_upper_C') & False
    wing_up = G.g('wing_upper_', 'aileron_')
    wing_lo = G.g('wing_lower_')
    tail = G.g('stab_', 'elevator_', 'fin', 'rudder')
    ctrl = G.g('aileron_', 'elevator_', 'rudder')
    struts = G.g('struts_', 'cabane', 'stab_strut_', 'gear_')
    wheels = G.g('gear_')
    fabric = (wing_up | wing_lo | tail | (fus & ~metal)) & ~struts
    top = G.N[:, 2] > 0.25
    H = np.zeros(K, F32)
    # ---- fabric: rib tapes (wings: ribs every 0.17 m spanwise; tail: 0.14 m), sag between ribs, stitching, LE sheet
    ax = np.abs(G.x)
    for sel, pitch, off in ((wing_up | wing_lo, 0.17, 0.05), (G.g('stab_', 'elevator_'), 0.14, 0.02)):
        d = T.periodic(ax, pitch, off)
        frac = ((ax - off) / pitch) % 1.0
        h = 0.0011 * np.exp(-(d / 0.011) ** 2) - 0.0016 * np.sin(np.pi * frac) ** 2
        stitch = 0.00035 * (T.periodic(G.y, 0.035) < 0.006) * (d < 0.008)
        H += np.where(sel, h + stitch, 0)
    fr = G.g('fin', 'rudder')
    d = T.periodic(G.z, 0.15, 0.02); frac = ((G.z - 0.02) / 0.15) % 1.0
    H += np.where(fr, 0.0010 * np.exp(-(d / 0.010) ** 2) - 0.0013 * np.sin(np.pi * frac) ** 2, 0)
    # aft fuselage fabric over stringers (longitudinal, every ~0.09 m round the section) and formers
    aft = fus & ~metal
    ang = np.arctan2(G.x, G.z - 0.0)
    d = T.periodic(ang * 0.42, 0.085)
    H += np.where(aft, 0.0008 * np.exp(-(d / 0.010) ** 2) - 0.0010 * np.cos(np.pi * d / 0.085) ** 2, 0)
    # wing leading-edge plywood/metal sheet: smooth band (no sag) up to ~12 % chord: damp the rib height there
    le_up = (G.y > 1.28 - 0.18) & wing_up
    le_lo = (G.y > 0.40 - 0.17) & wing_lo
    H = np.where(le_up | le_lo, H * 0.25, H)
    # ---- metal cowling: panel lines + fasteners + louvres
    lines_y = np.array([2.27, 1.86, 1.36, 0.86, 0.32, -0.24], F32)
    dy, _ = T.nearest_station(G.y, lines_y)
    side_line = np.minimum(np.abs(G.z - 0.26), np.abs(G.z + 0.32))
    pl = np.minimum(dy, np.where(np.abs(G.x) > 0.2, side_line, 9))
    H += np.where(metal, T.groove(pl, 0.0018, 0.0007), 0)
    fast = (pl < 0.012) & (T.periodic(np.where(dy < side_line, np.abs(G.x) + np.abs(G.z), G.y), 0.055) < 0.004)
    H += np.where(metal & fast, 0.0004, 0)
    louv = metal & (np.abs(G.x) > 0.3) & (G.z > 0.12) & (G.z < 0.24) & (G.y > 0.4) & (G.y < 1.7)     # (kept: AO under the louvre row)
    # 1.3.0b: the cowl louvres are real geometry (nimrod_parts.add_louvres); no louvre texture. Aluminium detail = high-passed fal
    # polished sheet (alu_sheet): fine linear polish only, low contrast (alu_polished read as crumpled foil at game scale)
    fab = T.tri_sample(fal_grey('fabric_dope'), G.P, G.N, 0.22)
    alu = T.tri_sample(fal_grey_hp('alu_sheet', sigma=12), G.P, G.N, 0.60, seed=3)
    H += np.where(metal, 0.000006 * alu, 0.00007 * fab)
    # control-surface hinge gaps (dark line) and trailing-edge wire
    H += np.where(ctrl, 0.0, 0)
    # ---- ambient occlusion (analytic): under wings near the root, inside the struts bay, fuselage under the upper wing
    ao = np.ones(K, F32)
    ao -= np.where(wing_lo & top & (ax < 1.2), 0.18 * (1 - ax / 1.2), 0)
    ao -= np.where(fus & (G.z > 0.3) & (G.y > -0.2) & (G.y < 1.3), 0.12, 0)
    ao -= np.where(wing_up & ~top & (ax < 1.0), 0.15 * (1 - ax), 0)
    ao -= np.where(fus & (G.z < -0.45), 0.10, 0)
    ao = np.clip(ao, 0.5, 1.0)
    wear = T.fbm(G.P, 3.0, 4, seed=7)
    grime = T.fbm(G.P, 1.2, 3, seed=11)
    detail = np.where(metal, 1.0 + 0.012 * alu, 1.0 + 0.035 * fab)
    return dict(H=H, ao=ao, metal=metal, fabric=fabric, wing_up=wing_up, wing_lo=wing_lo, tail=tail, fus=fus, top=top,
                struts=struts, wheels=wheels, wear=wear, grime=grime, ctrl=ctrl, detail=detail.astype(F32), louv=louv)


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
def naval_texel():
    """side of one livery texel in metres (the atlas has one scale: metres_per_uv of the model build)"""
    return json.loads(bpy.context.scene.get('b25_build_stats', '{}')).get('metres_per_uv', 10.0) / RES


_NAV_GEOM = {}


def naval_geom(G, texel):
    """1.9.12 round 3, naval PALA scheme only (no other livery calls it): per texel the pattern field (NV.field_of: part kind + smooth
    normal), the texel's footprint on the surface (Ju, Jv from NV.raster_extra, the same rasterisation as rasterise()) and the
    fuselage unwrap table built from the fuselage texels. Computed once per run."""
    if 'field' in _NAV_GEOM:
        return _NAV_GEOM
    Ju, Jv, sn, pid = NV.raster_extra(bpy.data.objects, RES)
    assert (pid[G.mask] == G.id).all() and ((pid >= 0) == G.mask).all(), 'raster_extra must cover the texels of rasterise() exactly'
    Ju, Jv, sn = Ju[G.mask].astype(np.float64), Jv[G.mask].astype(np.float64), sn[G.mask].astype(np.float64)
    kinds = np.array([NV.kind_of(n) for n in G.names], np.int8)[G.id]
    field = NV.field_of(sn, kinds)
    fus_sel = (kinds == NV.KIND_FUS) & (field == NV.FIELD_FUS)
    tab = NV.fus_table(G.P[fus_sel])
    na, nb = NV.footprint_counts(Ju, Jv, texel)
    st = dict(texels=int(G.K), stretched_over_2_texels=int(((na > 4) | (nb > 4)).sum()), at_fp_max=int(((na == NV.FP_MAX) | (nb == NV.FP_MAX)).sum()),
              fields=[int((field == f).sum()) for f in range(NV.N_FIELDS)], fus_texels=int(fus_sel.sum()))
    _NAV_GEOM.update(field=field, Ju=Ju, Jv=Jv, fus=tab, fp_stats=st)
    log('naval geometry:', json.dumps(st))
    return _NAV_GEOM


def stencil(col, G, sel, pu, pv, inside, rgb, texel):
    """paint a hard-edged shape (inside(pu, pv) -> bool, local metres) crisply: NV.supersample (4 x 4 thresholded sub-samples per texel)"""
    cov = np.zeros(G.K, F32)
    if sel.any():
        cov[sel] = NV.supersample(inside, pu[sel], pv[sel], texel)
    return put(col, cov, np.asarray(rgb, F32))


def glyphs(text, h, stroke):
    """inside-test of a word in the project's stroke font, hard edge (tex_lib.text_mask with a vanishing soft edge, thresholded)"""
    return lambda u, v: T.text_mask(u, v, [text], h, stroke, aa=1e-5) > 0.5


def naval_weather(col, G, F, c):
    """restrained wear, the stock naval skins' kind at this aircraft's scale (numbers in naval1912.py): salt streaks along the airflow,
    the fal grime tile, chalked rib tapes with a dirt line each side, dark cowling panel joints with a lighter worn rim,
    dark control-surface hinge gaps, paint chipped to a lighter tone on leading edges and cowl panel edges."""
    ax = np.abs(G.x)
    flow = T.fbm(G.P * np.array([5.0, 0.55, 5.0], F32), 1.0, 3, seed=21); fine = T.fbm(G.P, 9.0, 2, seed=23)
    gain = NV.streak_gain(flow, fine)
    if NV.GRIME_AMOUNT > 0:             # fal: stains, drips, smudges, scratches (one seamless tile, high-passed, triplanar in world space)
        gain = gain * NV.grime_gain(T.tri_sample(fal_grey_hp(NV.GRIME_TILE, 512, sigma=NV.GRIME_HP_SIGMA), G.P, G.N, NV.GRIME_SPAN, seed=5))
    # fabric: rib tapes (same stations as the height map in features())
    tape = np.zeros(G.K, F32); edge = np.full(G.K, 9.0, F32)
    for sel, pitch, off in ((F['wing_up'] | F['wing_lo'], 0.17, 0.05), (G.g('stab_', 'elevator_'), 0.14, 0.02)):
        d = T.periodic(ax, pitch, off)
        tape = np.where(sel, np.exp(-(d / 0.012) ** 2), tape); edge = np.where(sel, np.abs(d - NV.TAPE_EDGE_OFF), edge)
    fr = G.g('fin', 'rudder')
    d = T.periodic(G.z, 0.15, 0.02)
    tape = np.where(fr, np.exp(-(d / 0.011) ** 2), tape); edge = np.where(fr, np.abs(d - NV.TAPE_EDGE_OFF), edge)
    t_light = np.where(fr, NV.FIN_TAPE_LIGHT, NV.TAPE_LIGHT).astype(F32); t_depth = np.where(fr, NV.FIN_TAPE_EDGE_DEPTH, NV.TAPE_EDGE_DEPTH).astype(F32)
    gain = gain * (1 + t_light * tape) * NV.line_gain(edge, NV.TAPE_EDGE_HALF, t_depth)     # round 3: fin / rudder tapes a third as strong
    # metal cowling: panel joints (the lines of the height map) dark, a lighter rim beside them
    dy, _ = T.nearest_station(G.y, np.array(NV.COWL_LINES_Y, F32))
    side_line = np.minimum(np.abs(G.z - NV.COWL_LINES_Z[0]), np.abs(G.z - NV.COWL_LINES_Z[1]))
    pl = np.minimum(dy, np.where(ax > 0.2, side_line, 9)).astype(F32)
    gain = gain * np.where(F['metal'], NV.line_gain(pl, NV.PANEL_LINE_HALF, NV.PANEL_LINE_DEPTH) * NV.rim_gain(pl, NV.PANEL_LINE_HALF, NV.PANEL_RIM_HALF, NV.PANEL_RIM_GAIN), 1.0)
    # hinge gaps: fin / rudder post, aileron and elevator leading edges
    hd = np.full(G.K, 9.0, F32)
    hd = np.where(G.g('fin') | (G.g('rudder') & ~G.g('rudder_balance')), np.abs(G.y - NV.RUDDER_HINGE_Y), hd)
    for pre in ('aileron_L', 'aileron_R', 'elevator_L', 'elevator_R'):
        m = G.g(pre) & ~G.g(pre + '_nose')
        if m.any():
            hd = np.where(m & (np.abs(G.N[:, 2]) > 0.5), np.abs(G.y - float(G.y[m].max())), hd)
    gain = gain * NV.line_gain(hd, NV.HINGE_HALF, NV.HINGE_DEPTH)
    col = col * gain[:, None]
    # chips: leading edges of wings / tail (faces looking forward) and the cowl panel edges
    n = T.fbm(G.P, 55.0, 2, seed=31); big = T.fbm(G.P, 6.0, 2, seed=33)
    le = (F['wing_up'] | F['wing_lo'] | G.g('stab_', 'fin')) & (G.N[:, 1] > 0.70)
    chip = np.where(le, T.smoothstep(0.60, 0.66, n) * T.smoothstep(0.35, 0.60, big), 0.0)
    chip = np.maximum(chip, np.where(F['metal'] & (pl < 0.014), T.smoothstep(0.64, 0.70, n) * T.smoothstep(0.40, 0.60, big), 0.0))
    return put(col, (NV.CHIP_MAX * chip).astype(F32), c['chip'])


def naval(G, F, key):
    """1.9.12 naval liveries (naval1912.py holds the numbers and the pattern).
    BDF Navy Gray: the stock VT-7 "BDF Navy Gray" language - neutral grey (the metal cowling a tone darker), lighter undersides, dark
    navy-grey accent panels (anti-glare panel on the cowling, upper-wing centre section, walkways), small red warning marks.
    PALA Navy: a straight-edged splinter in the stock PALA navy palette all over (the FD-32 "PALA Navy Splinter" family).
    Both: emblems at the six sites, the stock title in a dark label plate on the rear fuselage, a number on the rudder between two
    small red arrows, crisp stencils, restrained panel-line / wear detail (naval_weather), glossiness 0.0."""
    c = NV.SCHEME[key]
    texel = naval_texel()
    w = F['wear'][:, None]
    ax = np.abs(G.x)
    if c['pattern'] == 'splinter':
        X = naval_geom(G, texel)                 # round 3: field per part kind + smooth normal (fuselage unwrap), texel footprint average
        col, idx = NV.splinter_rgb_fp(G.P, X['Ju'], X['Jv'], X['field'], X['fus'], c['palette'], texel)
        STATS['pala_navy_footprint'] = X['fp_stats']
        col = col * (0.96 + 0.06 * w)
        STATS['pala_navy_shares'] = [round(s, 4) for s in NV.shares_of(idx, len(c['palette']))]
    else:
        up = np.where(F['metal'][:, None], c['metal'][None, :] * (0.97 + 0.04 * w), c['upper'][None, :] * (0.95 + 0.07 * w))
        t = np.where(F['struts'], 1.0, NV.under_weight(G.N[:, 2])).astype(F32)[:, None]      # struts / gear legs: the upper colour all round
        col = up * t + c['under'][None, :] * (0.95 + 0.07 * w) * (1 - t)
        glare = F['metal'] & (G.N[:, 2] > NV.GLARE_NZ) & (ax < NV.GLARE_HALF) & (G.y > NV.GLARE_Y[0]) & (G.y < NV.GLARE_Y[1])
        col = put(col, glare.astype(F32), c['accent'])
        cs = G.g('wing_upper_') & (ax < NV.CS_HALF) & F['top']
        col = put(col, cs.astype(F32), c['accent'])
    walk = F['wing_lo'] & F['top'] & (ax < NV.WALK_HALF) & (G.y < NV.WALK_Y_FWD)
    col = put(col, walk.astype(F32) * 0.94, c['walk'])
    col = naval_weather(col, G, F, c)
    col = nat_marks(col, G, F, c['kind'])
    # red warning marks: the walkway's outer limit line, the propeller line round the cowling
    sel = F['wing_lo'] & F['top'] & (G.y < NV.WALK_Y_FWD) & (np.abs(ax - NV.WALK_HALF) < 0.06)
    col = stencil(col, G, sel, ax - NV.WALK_HALF, G.y * 0, lambda u, v: np.abs(u - NV.WALK_LINE / 2) <= NV.WALK_LINE / 2, c['red'], texel)
    sel = F['metal'] & (np.abs(G.y - NV.PROP_LINE_Y) < 0.05)
    col = stencil(col, G, sel, G.y - NV.PROP_LINE_Y, G.y * 0, lambda u, v: np.abs(u) <= NV.PROP_LINE_W / 2, c['red'], texel)
    hu, hv = NV.plate_half(c['title'])
    y0, y1, z0, z1 = NV.text_box(c['number'], NV.NUM_Y, NV.NUM_Z, NV.NUM_H, NV.NUM_STROKE)
    for side in (-1, 1):
        # title: dark label plate, thin light border, light letters
        sel = F['fus'] & (np.sign(G.x) == side) & (np.abs(G.N[:, 0]) > 0.4) & (G.y > NV.TITLE_SEL_Y[0]) & (G.y < NV.TITLE_SEL_Y[1])
        pu, pv = side * (G.y - NV.TITLE_Y), G.z - NV.TITLE_Z
        sel = sel & (np.abs(pu) < hu + 0.03) & (np.abs(pv) < hv + 0.03)
        col = stencil(col, G, sel, pu, pv, lambda u, v: NV.in_box(u, v, hu, hv), c['plate'], texel)
        col = stencil(col, G, sel, pu, pv, lambda u, v: NV.in_frame(u, v, hu, hv, NV.PLATE_BORDER, NV.PLATE_BORDER), c['title_rgb'], texel)
        col = stencil(col, G, sel, pu, pv, glyphs(c['title'], NV.TITLE_H, NV.TITLE_STROKE), c['title_rgb'], texel)
        # number on the rudder (by the normal: the rudder sits at x ~ 0, the sign of x is no use there), red arrows fore and aft
        sel = G.g('rudder') & ~G.g('rudder_balance') & (side * G.N[:, 0] > 0.4)
        pu, pv = side * (G.y - NV.NUM_Y), G.z - NV.NUM_Z
        sel = sel & (np.abs(pu) < (y1 - y0) / 2 + 0.15) & (np.abs(pv) < NV.NUM_H)
        if c['keyline'] is not None:
            col = stencil(col, G, sel, pu, pv, glyphs(c['number'], NV.NUM_H, NV.NUM_STROKE + 2 * NV.NUM_KEYLINE), c['keyline'], texel)
        col = stencil(col, G, sel, pu, pv, glyphs(c['number'], NV.NUM_H, NV.NUM_STROKE), c['number_rgb'], texel)
        half = (y1 - y0) / 2 + NV.ARROW_GAP
        for d in (-1, 1):       # d = -1: the arrow left of the word, pointing right at it; +1: right of it, pointing left
            col = stencil(col, G, sel, pu, pv, lambda u, v, d=d: NV.in_arrow(u, v, d * half, NV.ARROW_LEN, NV.ARROW_HALF, -d), c['red'], texel)
    return col, NV.GLOSS


def livery(G, F, key):
    K = G.K
    w, gr = F['wear'], F['grime']
    if key == 'faa_silver':
        fabric = np.array([0.66, 0.67, 0.68], F32); metal = np.array([0.74, 0.75, 0.77], F32)
        col = np.where(F['metal'][:, None], metal[None, :] * (0.975 + 0.03 * w[:, None]), fabric[None, :] * (0.96 + 0.06 * w[:, None]))
        # flight colour (red) band round the rear fuselage and over the upper centre section, fin coloured
        band = F['fus'] & (G.y < -2.55) & (G.y > -2.80)
        col = put(col, band.astype(F32), RED)
        cs = G.g('wing_upper_') & (np.abs(G.x) < 0.80) & F['top']      # by position: the centre-section tear edge stays invisible under the band edge
        col = put(col, cs.astype(F32), RED)
        # rudder stripes (blue forward, white, red aft)
        rud = G.g('rudder')
        for y0, y1, c in ((-4.47, -4.74, BLUE), (-4.74, -5.01, WHITE), (-5.01, -5.40, RED)):
            col = put(col, (rud & (G.y <= y0) & (G.y > y1)).astype(F32), c)
        col = nat_marks(col, G, F, 'RAF')
        col = serials(col, G, F, 'S1577', BLACK)
        # unit code on the fuselage aft of the roundel
        for side in (-1, 1):
            sel = F['fus'] & (np.sign(G.x) == side) & (np.abs(G.N[:, 0]) > 0.4) & (G.y > -1.85) & (G.y < -1.35)
            col = text_on(col, G, sel, side * (G.y + 1.60), G.z + 0.05, '566', 0.16, 0.026, BLACK)
        gloss = 0.45
    elif NV.NAVAL_LIVERIES_1912 and key in NV.KEYS:
        col, gloss = naval(G, F, key)
    else:
        if key == 'bdf_mattegrey':
            base = np.array([0.36, 0.38, 0.40], F32)
            col = np.tile(base, (K, 1)) * (0.94 + 0.08 * w[:, None])
        elif key == 'pala_matteblack':
            base = np.array([0.085, 0.085, 0.09], F32)
            col = np.tile(base, (K, 1)) * (0.92 + 0.12 * w[:, None])
        elif key in ('bdf_temperate', 'pala_desert'):
            n = T.fbm(G.P * np.array([1.0, 0.6, 1.0], F32), 0.95, 3, seed=3 if key == 'bdf_temperate' else 5)
            upper = (G.N[:, 2] > -0.30)
            if key == 'bdf_temperate':
                a, b, under = np.array([0.20, 0.25, 0.15], F32), np.array([0.36, 0.38, 0.36], F32), np.array([0.58, 0.62, 0.64], F32)
            else:
                a, b, under = np.array([0.62, 0.52, 0.34], F32), np.array([0.36, 0.24, 0.15], F32), np.array([0.62, 0.68, 0.74], F32)
            edge = T.smoothstep(0.485, 0.515, n)[:, None]
            camo = a[None, :] * (1 - edge) + b[None, :] * edge
            col = np.where(upper[:, None], camo, under[None, :]) * (0.95 + 0.07 * w[:, None])
        kind = 'BDF' if key.startswith('bdf') else 'PALA'
        col = nat_marks(col, G, F, kind)
        col = serials(col, G, F, 'N-15' if kind == 'BDF' else 'P-15', WHITE * 0.85 if key != 'bdf_mattegrey' else BLACK, small=True)
        gloss = 0.15
    # weathering: exhaust soot streaks aft of the stubs, oil under the cowl, wheel scuffs
    sw = (0.10 + np.clip(0.5 - G.y, 0, None) * 0.03)
    soot = (F['fus'] & (np.abs(G.x) > 0.25) & (G.y > -2.0)).astype(F32) * T.smoothstep(sw * 1.0, sw * 0.4, np.abs(G.z - 0.05)) * T.smoothstep(0.65, 0.35, G.y)
    col = col * (1 - 0.30 * soot[:, None] * (0.5 + 0.5 * gr[:, None]) * np.clip(1 + (G.y[:, None] - 0.5) * 0.4, 0, 1))
    oil = F['fus'] & (G.z < -0.4) & (G.y < 1.2)
    col = col * (1 - 0.18 * oil[:, None] * gr[:, None])
    col = col * F['detail'][:, None]                       # fal fabric weave / aluminium burnish / louvre slots on every livery
    return np.clip(col, 0, 1), gloss


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


LIVERIES = [('faa_silver', 'FAA Silver (1934)', 'BDF', True), ('bdf_mattegrey', 'BDF Matte Gray', 'BDF', False),
            ('bdf_temperate', 'BDF Temperate Camo', 'BDF', False), ('pala_matteblack', 'PALA Matte Black', 'PALA', False),
            ('pala_desert', 'PALA Desert Camo', 'PALA', False)]
if NV.NAVAL_LIVERIES_1912:          # 1.9.12: appended, never inserted (saved missions store the list index)
    LIVERIES = LIVERIES + NV.ENTRIES


def skin(G, F, metres_per_uv):
    ts = metres_per_uv / RES
    Himg = finish(to_img(G, F['H']), G.mask, 8)
    nmap = T.normal_from_height(Himg, ts, 1.0)
    save(T.encode_normal(nmap), 'nimrod_skin_n')
    met = np.where(F['metal'], 0.85, 0.35).astype(F32)
    smooth = np.where(F['metal'], 0.62 + 0.03 * F['wear'], 0.38 + 0.06 * F['wear']).astype(F32)
    m = finish(to_img(G, np.stack([met, met, met], -1)), G.mask)
    a = finish(to_img(G, smooth), G.mask)
    T.save_png(m, os.path.join(OUT, 'nimrod_skin_m.png'), alpha=a)
    save(finish(to_img(G, F['ao']), G.mask), 'nimrod_skin_ao')
    skin_damage(G, ts)


def skin_damage(G, ts):
    """1.8.9 (offline J, docs/damage_model_study.md): a real hole-order alpha (the 1.5.x map had a flat alpha 0.6: the AircraftSkin shader
    never cut a hole, discard below 0.52 - 0.02 / D). hole_damage189.build at the aircraft's size (scale 0.55): world-space bullet
    clusters / shell holes / torn patches, alpha by rank onto the coverage targets, soot rims and dents with the holes, 0.62 outside the
    UV islands; only the skin (paint faces) is in this atlas."""
    import hole_damage189 as HD
    rgb, alpha, Hh, st = HD.build(T, G.P, scale=0.55, seed=1931, log=log)
    db = finish(to_img(G, rgb), G.mask)
    T.save_png(db, os.path.join(OUT, 'nimrod_skin_dmg_b.png'), alpha=to_img(G, alpha, fill=HD.FILL_ALPHA))
    Hd = finish(to_img(G, Hh), G.mask, 8)
    save(T.encode_normal(T.normal_from_height(Hd, ts, 3.0)), 'nimrod_skin_dmg_n')
    STATS.update(st)
    log('damage maps done', st)


def tiles():
    """512 tiling textures for the non-paint materials (detail UV = 2 m per unit), all from fal tiles tone-matched to the material
    colours. Height for the normal map = the fal tile's luminance detail."""
    n = 512
    spec = {   # material: (fal tile, mean colour, contrast, normal strength)
        'prop': ('prop_wood', (0.33, 0.19, 0.09), 1.0, 0.00015),
        'wood': ('prop_wood', (0.30, 0.16, 0.08), 1.0, 0.0002),
        'leather': ('ck_leather', (0.19, 0.11, 0.06), 1.0, 0.0006),
        'alu': ('alu_sheet', (0.70, 0.71, 0.72), 0.5, 0.00005),
        'interior': ('structure', (0.40, 0.43, 0.39), 0.6, 0.0002),
        'tube': ('tube_steel', (0.20, 0.21, 0.20), 1.0, 0.0001),
        'ck_grey': ('ck_paint', (0.46, 0.48, 0.49), 1.0, 0.0001),
        'rubber': ('rubber', (0.035, 0.035, 0.035), 1.0, 0.0004),
        'gunmetal': ('gunmetal', (0.12, 0.12, 0.13), 0.8, 0.0002),
        'structure': ('structure', (0.50, 0.52, 0.49), 1.0, 0.0004),
        'fabric_in': ('fabric_inside', (0.62, 0.58, 0.48), 1.0, 0.00015),
        'exhaust': ('exhaust_steel', (0.24, 0.15, 0.10), 1.0, 0.0003),
        'metal_dark': ('gunmetal', (0.08, 0.08, 0.085), 0.6, 0.0002),
    }
    for k, (src, rgb, con, hs) in spec.items():
        if src == 'alu_sheet':      # polished sheet: flat colour + high-passed polish lines only (no tiled shading blotches)
            hp = fal_grey_hp(src, n, sigma=12)
            img = np.clip(np.asarray(rgb, F32)[None, None, :] * (1.0 + 0.02 * hp[..., None]), 0, 1)
            H = hp * hs
        else:
            img = tone(fal_tile(src, n), rgb, con)
            H = fal_grey(src, n) * hs
        save(img, f'nimrod_tile_{k}_b')
        save(T.encode_normal(T.normal_from_height(H.astype(F32), 2.0 / n, 1.0)), f'nimrod_tile_{k}_n')
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
            d = np.minimum(np.abs(((th + 180) % 360) - 180), np.abs(((th) % 360) - 180))
            wdt = 8 + 22 * r
            a = (0.06 + 0.60 * np.exp(-(d / wdt) ** 2)) * edge
        else:
            a = (0.15 + 0.03 * np.sin(r * 50)) * edge
        col = np.array([0.24, 0.14, 0.07], F32)
        out[half * 512:(half + 1) * 512, :, :3] = col
        out[half * 512:(half + 1) * 512, :, 3] = a
    T.save_png(out[..., :3], os.path.join(OUT, 'nimrod_propblur.png'), alpha=out[..., 3])


# =============================================================================================== main
def write_manifest(dmg_only=False):
    """1.8.16 guard: record the livery-atlas UV these textures were painted on (model checks + Unity CHECK ALL compare against it)."""
    files = AG.atlas_textures(OUT, 'nimrod')
    if dmg_only:
        files = [f for f in files if os.path.basename(f).startswith('nimrod_skin_dmg_')]
    m = AG.write_manifest(os.path.join(OUT, 'nimrod_atlas_manifest.json'), 'NIMROD1', AG.scene_parts(), bpy.data.filepath, files,
                          written_by='blender/nimrod/textures/build_textures_nimrod.py' + (' --dmg-only' if dmg_only else ''))
    log('atlas manifest', m['atlas_hash'])


def liveries_only(G_, F, mask, keys):
    """1.9.12: bake ONLY the named liveries on the unchanged atlas. Writes <key>.png, merges their entries into nimrod_liveries.json
    (old entries untouched and first) and adds the files to the atlas manifest. No skin / damage / tile / prop-blur file is written and
    nimrod_skin_b is not touched. Self-check first: the shipped liveries baked again in memory must equal the files in the repo (same
    wear / detail layers as the liveries next to them); a difference is reported, not fatal."""
    label = {k: (l, f, b) for k, l, f, b in LIVERIES}
    unknown = [k for k in keys if k not in label]
    assert not unknown, f'unknown livery keys {unknown}'
    assert all(k in NV.KEYS for k in keys), 'liveries-only writes the 1.9.12 naval liveries only (the others are shipped files)'
    man = os.path.join(OUT, 'nimrod_atlas_manifest.json')
    model_atlas = AG.atlas_hash(AG.scene_parts())
    import tempfile, hashlib
    same = {}
    for k in [x[0] for x in LIVERIES if x[0] not in NV.KEYS]:
        col, _ = livery(G_, F, k)
        tmp = os.path.join(tempfile.gettempdir(), f'nimrod_selfcheck_{os.getpid()}_{k}.png')
        T.save_png(finish(to_img(G_, col), mask), tmp)
        same[k] = NV.sha12(tmp) == NV.sha12(os.path.join(OUT, f'nimrod_livery_{k}.png'))
        os.remove(tmp)
    log('self-check, shipped liveries re-baked in memory == repo files:', json.dumps(same))
    new = {}; files = []
    for k in keys:
        col, gloss = livery(G_, F, k)
        img = finish(to_img(G_, col), mask)
        name = 'nimrod_livery_' + k
        save(img, name); files.append(os.path.join(OUT, name + '.png'))
        new[k] = dict(texture=name + '.png', name=label[k][0], label=label[k][0], faction=label[k][1], both=label[k][2], glossiness=gloss, colors=top_colors(img, mask))
    jp = os.path.join(OUT, 'nimrod_liveries.json')
    json.dump(NV.merge_liveries(json.load(open(jp)), new), open(jp, 'w'), indent=1)
    m = NV.manifest_add(man, files, model_atlas, 'blender/nimrod/textures/build_textures_nimrod.py --liveries-only ' + ','.join(keys))
    json.dump(dict(keys=keys, selfcheck_same=same, atlas=m['atlas_hash'], files={os.path.basename(f): NV.sha12(f) for f in files},
                   glossiness=NV.GLOSS, texel_m=round(naval_texel(), 6), splinter_seed=NV.SPL_SEED, pala_navy_shares=STATS.get('pala_navy_shares'),
                   stencil_sub=NV.STENCIL_SUB, fal_wear=NV.fal_record(), round3_footprint=STATS.get('pala_navy_footprint')),
              open(os.path.join(OUT, 'nimrod_liveries_1912_stats.json'), 'w'), indent=1)
    log('liveries-only done', keys, 'atlas', m['atlas_hash'])


def main():
    stats = json.loads(bpy.context.scene.get('b25_build_stats', '{}'))
    mpu = stats.get('metres_per_uv', 10.0)
    pos, nrm, pid, names, mask = rasterise()
    G_ = G(pos, nrm, pid, names, mask)
    if '--dmg-only' in argv:            # 1.8.9: only the damage maps (liveries / normals / tiles stay as built)
        skin_damage(G_, mpu / RES)
        json.dump(STATS, open(os.path.join(OUT, 'nimrod_textures_dmg_stats.json'), 'w'), indent=1)
        log('damage-only done', json.dumps(STATS))
        write_manifest(True)
        return
    F = features(G_)
    if '--liveries-only' in argv:                                        # 1.9.12: bake the named liveries only
        liveries_only(G_, F, mask, argv[argv.index('--liveries-only') + 1].split(','))
        return
    skin(G_, F, mpu)
    meta = {}
    for key, label, fac, both in LIVERIES:
        col, gloss = livery(G_, F, key)
        img = finish(to_img(G_, col), mask)
        name = 'nimrod_livery_' + key
        save(img, name)
        if key == 'faa_silver':
            save(img, 'nimrod_skin_b')
        meta[key] = dict(texture=name + '.png', name=label, label=label, faction=fac, both=both, glossiness=gloss, colors=top_colors(img, mask))
    json.dump(meta, open(os.path.join(OUT, 'nimrod_liveries.json'), 'w'), indent=1)
    tiles(); propblur()          # prop textures (PIL): make_cockpit_art_nimrod.py          # gauge atlas + cockpit art: make_cockpit_art_nimrod.py (PIL, run after this)
    STATS['res'] = RES; STATS['metres_per_uv'] = mpu; STATS['texel_mm'] = round(mpu / RES * 1000, 2)
    json.dump(STATS, open(os.path.join(OUT, 'nimrod_textures_stats.json'), 'w'), indent=1)
    write_manifest()
    log('done', json.dumps(STATS))


main()
