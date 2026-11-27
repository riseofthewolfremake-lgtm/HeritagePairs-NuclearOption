"""A6M2 round 5: the seven liveries + skin maps, baked onto OUR livery atlas from the model (numpy rasteriser, the r1 / Nimrod method).
Nothing from War Thunder: panel lines, rivets, weathering and every marking are procedural, placed in our own coordinates
(design 9: s = metres aft of the spinner tip, b = |x| from the centreline, c = chord fraction, v = section height fraction).

  blender --background assets/model_a6m2/a6m2.blend --python-exit-code 1 --python blender/a6m2/textures/build_textures_a6m2.py -- [--out assets/textures_a6m2]

Schemes (design 9.2; colour numbers in SCHEMES below, faction hues checked against the stock dump of 2026-11-18,
cockpit_liveries_work/stock_liveries: CAS1 temperate #737779 / #4A4F42, SmallFighter1 PALA desert #9B8B7C / #5D433A on #707775,
CAS1 desert #AF968B, CAS1 matte gray #6F6C6C, PALA black #1C1C1C-#393737, navy greys / teal):
  1 ijn_greywhite (both)  2 bdf_temperate  3 bdf_mattegrey  4 bdf_navy  5 pala_desert  6 pala_matteblack  7 pala_navy
Writes a6m2_livery_<key>.png (2048), a6m2_skin_b (= ijn), _n (panel lines + rivets), _m, _ao, _dmg_b, _dmg_n, a6m2_liveries.json
(menu order: BDF ijn, temperate, matte gray, navy; PALA ijn, desert, matte black, navy), a6m2_propblur.png, the atlas manifest.
"""
import bpy, os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path[:0] = [os.path.join(ROOT, 'blender', 'v2', 'textures'), os.path.join(ROOT, 'blender'), os.path.join(ROOT, 'blender', 'a6m2'), os.path.join(ROOT, 'blender', 'v2')]
import tex_lib as T
import atlas_guard as AG
import faction_marks as FM
import a6m2_spec as S
F32 = np.float32
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RES = 2048
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_a6m2')
os.makedirs(OUT, exist_ok=True)
K = S.K
NOSE_Y = 2.381 * K


def log(*a):
    print('[a6tex]', *a)


def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)], F32)


# --------------------------------------------------------------------------------------------------- schemes (design 9.2)
SCHEMES = {
    'ijn_greywhite': dict(name='IJN Grey-White (1941)', faction='BDF', both=True, gloss=0.35, base='#A8A48A', cowl='#1C2124'),
    'bdf_temperate': dict(name='BDF Temperate Camo', faction='BDF', both=False, gloss=0.0, base='#777B7C', camo='#48503F', cowl='#2E3829', mark='BDF', serial='0621'),
    'bdf_mattegrey': dict(name='BDF Matte Gray', faction='BDF', both=False, gloss=0.0, base='#6C6B6B', cowl='#3C3D3F', mark='BDF', serial='0621'),
    # r4c (coordinator: too close to Matte Gray): the stock BDF naval blue-grey family (multirole1 "BDF Navy" #6F797C / #788588 / #859395,
    # EW1 "BDF Navy Hex" #61747A / #344758; study/v1912/stock_naval_ref/stock_naval_stats.json): dark sea blue-grey upper over a light
    # blue-grey underside, dark blue cowl. The r4 values were the VTOLTrainer1 neutral "BDF Navy Gray" (#6A6969), next to Matte Gray #6C6B6B.
    'bdf_navy': dict(name='BDF Navy', faction='BDF', both=False, gloss=0.0, base='#4C606A', under='#859395', cowl='#344758', glare='#1E252B', mark='BDF', rudder='121'),
    'pala_desert': dict(name='PALA Desert Camo', faction='PALA', both=False, gloss=0.0, shards=[('#9B8B7C', 0.38), ('#AF968B', 0.28), ('#5D433A', 0.34)],
                        under='#707775', cowl='#545E60', glare='#3A2C2E', mark='PALA', serial='6210'),
    'pala_matteblack': dict(name='PALA Matte Black', faction='PALA', both=False, gloss=0.0, base='#2D2C2C', cowl='#181818', mark='PALA', serial='6210', stencil='#8F8986'),
    'pala_navy': dict(name='PALA Navy Splinter', faction='PALA', both=False, gloss=0.0, shards=[('#30464A', 0.35), ('#8E8E8E', 0.30), ('#5A5A5A', 0.22), ('#4E4F4F', 0.13)],
                      cowl='#1A1A1A', mark='PALA', serial='6210'),   # r8c: fin serial like the other PALA liveries; r8f (game r8e sheet_fin7):
                                                                     # the rudder number '221' was cut by the rudder TE and read as serial fragments - removed
}
EMBLEM_WING_CHORD = 0.80   # r4c: faction emblem width / local wing chord at the hinomaru site (b 4.73)
EMBLEM_FUS = 0.80          # r4c: fuselage emblem width, m (r4 0.58)
ORDER = ['ijn_greywhite', 'bdf_temperate', 'bdf_mattegrey', 'bdf_navy', 'pala_desert', 'pala_matteblack', 'pala_navy']


# --------------------------------------------------------------------------------------------------- rasteriser (r1)
def rasterise():
    R = RES
    pos = np.zeros((R, R, 3), F32); nrm = np.zeros((R, R, 3), F32); pid = np.full((R, R), -1, np.int16)
    names = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH':
            continue
        me = ob.data
        mats = [m.name if m else '' for m in me.materials]
        if 'paint' not in mats:
            continue
        pi = mats.index('paint')
        names.append(ob.name); k0 = len(names) - 1
        # r8e: the unified root mesh keeps the origin of each face in the face attribute 'src' (0 fuselage, 1 wing centre, 2 fairing):
        # those faces keep their old group names (wing_C / fillet_*) so every livery rule still applies to them
        srcA = me.attributes.get('src')
        src_k = {}
        if srcA is not None:
            for nm_ in ('wing_C', 'fillet_R', 'fillet_L'):
                names.append(nm_); src_k[nm_] = len(names) - 1
        uv = me.uv_layers['livery'].data
        M = ob.matrix_world; N3 = M.to_3x3().inverted().transposed()
        me.calc_loop_triangles()
        for lt in me.loop_triangles:
            if lt.material_index != pi:
                continue
            P = [M @ me.vertices[v].co for v in lt.vertices]
            U = [uv[l].uv for l in lt.loops]
            n = (N3 @ lt.normal).normalized()
            k = k0
            if srcA is not None:
                sv = srcA.data[lt.polygon_index].value
                if sv == 1:
                    k = src_k['wing_C']
                elif sv == 2:
                    k = src_k['fillet_R'] if sum(p_.x for p_ in P) > 0 else src_k['fillet_L']
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
            pos[yy, xx] = W @ Pa
            nrm[yy, xx] = (n.x, n.y, n.z)
            pid[yy, xx] = k
    mask = pid >= 0
    log(f'{len(names)} paint objects, atlas coverage {mask.mean():.3f}')
    return pos, nrm, pid, names, mask


def to_img(mask, vals, fill=0.0):
    ch = 1 if vals.ndim == 1 else vals.shape[1]
    img = np.full((RES, RES, ch), fill, F32)
    img[mask] = vals.reshape(-1, ch)
    return img if ch > 1 else img[..., 0]


# --------------------------------------------------------------------------------------------------- geometry tables (from the model generator)
def tables():
    import a6m2_parts as AP
    xs = np.linspace(0.0, 6.2, 125, dtype=F32)
    le, te = [], []
    for x in xs:
        st = AP.wing_station(float(max(x, 0.001)), 1)
        le.append(st.le.y); te.append(st.le.y - st.chord)
    ys = np.linspace(-6.4, 2.4, 177, dtype=F32)
    zt, zb = [], []
    for y in ys:
        p = AP.body_params(float(y))
        zt.append(p[0]); zb.append(p[1])
    # stab / fin outlines for markings
    fc = []
    for x in xs:                                    # r8b: flap hinge chord share along the span (flap outline line)
        f_ = AP.flap_s(float(max(x, 0.001)))
        fc.append(f_ if f_ is not None else 2.0)
    return dict(xs=xs, le=np.array(le, F32), te=np.array(te, F32), ys=ys, zt=np.array(zt, F32), zb=np.array(zb, F32),
                fold_b=float(S.span_built(S.WING_BREAKS[3])), flap_c=np.array(fc, F32), flap_b0=float(S.span_built(S.FLAP_X[0])),
                flap_b1=float(S.span_built(S.FLAP_X[1])))


def groups(names, pid, mask):
    g = np.array([n for n in names] + [''])
    nm = g[pid[mask]]
    def pre(*p):
        return np.array([any(str(n).startswith(q) for q in p) for n in nm])
    wing = pre('wing_', 'aileron_', 'flap_')
    fus = pre('fus_', 'fillet_', 'canopy_')
    vtail = pre('fin', 'rudder')
    htail = pre('stab_', 'elevator_')
    rudder = pre('rudder')
    engine = pre('fus_engine')
    door = pre('gear_')
    return dict(wing=wing, fus=fus, vtail=vtail, htail=htail, rudder=rudder, engine=engine, gear=door, names=nm,
                fillet=pre('fillet_'), aileron=pre('aileron_'), flap=pre('flap_'), canopy=pre('canopy_'))


# --------------------------------------------------------------------------------------------------- panel lines / rivets (height + darkening)
def panel_height(P, N, G, TB):
    s = NOSE_Y - P[:, 1]
    b = np.abs(P[:, 0])
    H = np.zeros(len(P), F32)
    hw, dp = 0.0013, 0.0007
    # fuselage frames every 0.42 m from s 1.40, two longerons, the rear ring joint at y -2.70 (pre)
    f = (G['fus'] | G['engine']) & ~G['canopy']                 # r8c: the fuselage frame lines / longerons no longer cross the canopy frames
    d_frame = T.periodic(s, 0.42 * K, 1.40 * K)
    d = np.minimum(d_frame, np.minimum(np.abs(P[:, 2] - 0.30), np.abs(P[:, 2] + 0.18)))
    d = np.minimum(d, np.abs(P[:, 1] + 2.70 * K))
    H[f] += T.groove(d[f], hw, dp)
    rv = f & (np.abs(d_frame - 0.018) < 0.0045) & (np.abs(((P[:, 2] + 0.02) % 0.040) - 0.020) < 0.0045)
    H[rv] += 0.0004
    # wings: ribs every 0.55 m, front spar line c 0.12, rear spar c 0.62, the break lines
    w = G['wing']
    le = np.interp(b, TB['xs'], TB['le']); te = np.interp(b, TB['xs'], TB['te'])
    c = np.clip((le - P[:, 1]) / np.maximum(le - te, 0.05), 0, 1.2)
    ch = le - te
    d_rib = T.periodic(b, 0.55, 0.30)
    d_sp = np.minimum(np.abs(c - 0.12), np.abs(c - 0.62)) * ch
    d = np.minimum(d_rib, d_sp)
    d = np.minimum(d, np.abs(b - TB['fold_b']))                                # r8b: the wing-fold hinge line (one clean panel line)
    fl = (b > TB['flap_b0']) & (b < TB['flap_b1']) & (N[:, 2] < 0)              # r8b: retracted split-flap outline on the underside
    d_fl = np.where(fl, np.abs(c - np.interp(b, TB['xs'], TB['flap_c'])) * ch, 9.0)
    d_fl = np.minimum(d_fl, np.where((N[:, 2] < 0) & (c > np.interp(b, TB['xs'], TB['flap_c'])),
                                     np.minimum(np.abs(b - TB['flap_b0']), np.abs(b - TB['flap_b1'])), 9.0))
    d = np.minimum(d, d_fl)
    H[w] += T.groove(d[w], hw, dp)
    # r8b rivets: 9 mm heads every 40 mm, 18 mm either side of the spar and rib lines (r8: 8 mm on 6 mm texels came and went)
    d_rr = np.minimum(d_sp, d_rib)
    rv = w & (np.abs(d_rr - 0.018) < 0.0045) & (np.abs(((np.where(d_sp < d_rib, b, P[:, 1]) + 0.01) % 0.040) - 0.020) < 0.0045)
    H[rv] += 0.0004
    t = G['vtail'] | G['htail']
    d = np.minimum(T.periodic(P[:, 2], 0.30, 0.3), T.periodic(b, 0.30, 0.3))
    H[t] += T.groove(d[t], hw * 0.8, dp * 0.8)
    # r8b (game: a panel line through the fuselage hinomaru / PALA roundel): no grooves or rivets under the national markings
    yb = NOSE_Y - 4.86 * K
    zc = body_mid_z(TB, yb)
    H[f & (np.hypot(P[:, 1] - yb, P[:, 2] - zc) < 0.44)] = 0.0
    bx = S.span_built(4.48)
    lew = np.interp(bx, TB['xs'], TB['le']); tew = np.interp(bx, TB['xs'], TB['te'])
    H[w & (np.hypot(b - bx, P[:, 1] - (lew - 0.40 * (lew - tew))) < 0.62)] = 0.0
    # r8i (C_rolling_ball notes: the IJN panel-line dashes stretched across the fillet): the fuselage frame / longeron lines were projected
    # onto the rolling-ball blend, which runs at a steep angle to them; the fillet is one formed sheet - no grooves or rivets on it
    H[G['fillet']] = 0.0
    H[G['canopy']] = np.maximum(H[G['canopy']], canopy_rivets(P[G['canopy']]))
    return H, c, s, b


def canopy_rivets(Q):
    """r8c (coordinator r8c item 4, WT frames carry rivet rows): 2.6 mm domed heads every 40 mm along the centre of the outer face of every
    exterior canopy frame (a6m2_canopy.FRAMES, set 'ext'; the frame outer face stands FH above the swept centre line)."""
    import a6m2_canopy as CAN
    import a6m2_parts as AP
    if not CAN.FRAMES:
        AP.build_exterior()
    out = np.zeros(len(Q), F32)
    h_out = CAN.FH
    for fr in CAN.FRAMES:
        if fr['set'] != 'ext':
            continue
        pts = np.array(fr['path'], F32)
        if fr.get('closed'):
            pts = np.vstack([pts, pts[:1]])
        L = np.linalg.norm(pts[1:] - pts[:-1], axis=1); cum = np.concatenate([[0.0], np.cumsum(L)])[:-1]
        for a_, b_, l_, c_ in zip(pts[:-1], pts[1:], L, cum):
            if l_ < 1e-6:
                continue
            d_ = (b_ - a_) / l_
            t_ = np.clip((Q - a_) @ d_, 0, l_)
            dist = np.linalg.norm(Q - (a_ + t_[:, None] * d_), axis=1)
            on = (dist > h_out - 0.003) & (dist < math.sqrt(h_out ** 2 + 0.006 ** 2))
            lat2 = np.maximum(dist ** 2 - h_out ** 2, 0.0)
            ds = np.abs(np.mod(c_ + t_ + 0.02, 0.040) - 0.020)
            r2 = lat2 + ds ** 2
            out = np.maximum(out, np.where(on & (r2 < 0.0026 ** 2), 0.0005 * np.sqrt(np.clip(1 - r2 / 0.0026 ** 2, 0, 1)), 0.0).astype(F32))
    log(f'canopy rivets: {int((out > 0).sum())} texels on the exterior frames')
    return out


def disc_cov(du, dv, r, aa):
    return 1 - T.smoothstep(r - aa, r + aa, np.sqrt(du * du + dv * dv))


def put(col, cov, rgb):
    cov = np.broadcast_to(np.clip(np.asarray(cov, F32), 0, 1), (len(col),))[:, None]
    return col * (1 - cov) + np.asarray(rgb, F32)[None, :] * cov


def body_mid_z(TB, y):
    return 0.5 * (np.interp(y, TB['ys'], TB['zt']) + np.interp(y, TB['ys'], TB['zb']))


def voronoi(P, cell, seed, stretch=(1, 1, 1), rot_deg=0.0):
    """cell id per point of a jittered 3D grid Voronoi (straight edges); stretch / rotation in the x-y... plane give splinter shapes."""
    a = math.radians(rot_deg)
    Q = P.copy()
    y, z = Q[:, 1].copy(), Q[:, 2].copy()
    Q[:, 1] = y * math.cos(a) + z * math.sin(a)
    Q[:, 2] = -y * math.sin(a) + z * math.cos(a)
    Q = Q / (np.array(stretch, F32) * cell)
    base = np.floor(Q).astype(np.int64)
    best = np.full(len(P), 1e9, F32); bid = np.zeros(len(P), np.int64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                cc = base + np.array([dx, dy, dz])
                h = (cc[:, 0] * 73856093) ^ (cc[:, 1] * 19349663) ^ (cc[:, 2] * 83492791) ^ seed
                jit = np.stack([((h >> s) & 1023) / 1023.0 for s in (3, 13, 23)], -1).astype(F32)
                d = np.sum((Q - (cc + 0.15 + 0.7 * jit)) ** 2, -1)
                upd = d < best
                best[upd] = d[upd]; bid[upd] = (h[upd] & 0x7FFFFFFF)
    return bid


def pick(ids, palette):
    u = (ids % 10007) / 10007.0
    edges = np.cumsum([w for _, w in palette])
    out = np.zeros((len(ids), 3), F32)
    lo = 0.0
    for (h, w), hi in zip(palette, edges):
        out[(u >= lo) & (u < hi + (1e-6 if hi >= edges[-1] - 1e-9 else 0))] = hexc(h)
        lo = hi
    return out


# --------------------------------------------------------------------------------------------------- one scheme
def paint(key, P, N, G, TB, c, s, b, H, aa):
    sc = SCHEMES[key]
    n = len(P)
    top = N[:, 2] > 0.0
    side_l = P[:, 0] < 0
    col = np.tile(hexc(sc.get('base', '#808080')), (n, 1))
    if key == 'bdf_temperate':
        f = T.fbm(P.astype(F32), 0.95, 3, seed=31)
        und = N[:, 2] < -0.3
        thr = np.where(und, np.quantile(f[und], 0.70), np.quantile(f[~und], 0.55))   # ~45 % on top / sides, ~30 % underneath
        cm = T.smoothstep(thr - 0.015, thr + 0.015, f)
        log('temperate camo cover top/sides %.2f under %.2f' % (cm[N[:, 2] >= -0.3].mean(), cm[N[:, 2] < -0.3].mean()))
        col = put(col, cm, hexc(sc['camo']))
    if key == 'bdf_navy':
        col = put(col, T.smoothstep(-0.18, -0.42, N[:, 2]), hexc(sc['under']))
    if 'shards' in sc:
        if key == 'pala_desert':
            ids = voronoi(P, 0.50, 1940)
        else:
            ids = voronoi(P, 0.95, 4511, stretch=(1.0, 1.0, 0.55), rot_deg=40.0)   # r8b: 1.40 left the fin / tailplane one colour
        col = pick(ids, sc['shards'])
    if key == 'pala_desert':                                      # blue-grey underside, fin and rudder (stock SmallFighter1 language)
        under = (N[:, 2] < -0.25)                                  # r8b: fin and rudder carry the camo (critique: tail from another aircraft)
        col[under] = hexc(sc['under'])
    if key == 'pala_matteblack':                                  # +-4 % panel tones
        pt = ((np.floor(s / 0.42) * 131 + np.floor(b / 0.55) * 71 + np.floor((P[:, 2] + 2) / 0.5) * 17) % 9) / 8.0
        col = col * (0.96 + 0.08 * pt[:, None])
    # cowl (s 0.43-1.40) and anti-glare panel (s 1.40-2.45, 0.20 m half width on the top centreline)
    cowl = G['engine'] & (s < 1.40 * K) & (s > 0.30)
    col[cowl] = hexc(sc['cowl'])
    glare = (G['fus'] | G['engine']) & (s >= 1.40 * K) & (s < 2.45 * K) & (np.abs(P[:, 0]) < 0.20) & (N[:, 2] > 0.4)
    if key != 'ijn_greywhite':
        col[glare] = hexc(sc.get('glare', sc['cowl']))
    # ---------------------------------------------------------------- markings
    if key == 'ijn_greywhite':
        red = hexc('#B0181A')
        yb = NOSE_Y - 4.86 * K
        zc = body_mid_z(TB, yb)
        fs = G['fus'] & (np.abs(N[:, 0]) > 0.3) & ~(G['fillet'] & (N[:, 2] > 0.7))           # r8b: the disc never lands on the fillet's
        # up-facing part (red blob); r8h: the filled fairing's side-facing part continues the fuselage side under the disc (else a bite)
        col[fs] = put(col[fs], disc_cov(P[fs, 1] - yb, P[fs, 2] - zc, 0.375, aa), red)
        for sgn in (1, -1):                                       # r8b: b 4.50, c 0.40, 0.96 m: clear of the fold line and the aileron
            bx = S.span_built(4.50)
            le = np.interp(bx, TB['xs'], TB['le']); te = np.interp(bx, TB['xs'], TB['te'])
            yw = le - 0.40 * (le - te)
            m = G['wing'] & (np.sign(P[:, 0]) == sgn) & ~G['aileron']
            col[m] = put(col[m], disc_cov(np.abs(P[m, 0]) - bx, P[m, 1] - yw, 0.48, aa), red)
        band = G['fus'] & (s > 5.75 * K) & (s < 6.15 * K)          # blue carrier band
        col[band] = hexc('#2C4A86')
        # tail code BI-151 on both fin sides, 45 % up the fin; r6: 0.16 m at s 8.12 (0.18 m at s 8.35 ran off the trailing edge: "BI-15")
        fin = G['vtail'] & (np.abs(N[:, 0]) > 0.5)
        yc = NOSE_Y - 8.12 * K
        pu = np.where(P[fin, 0] < 0, -(P[fin, 1] - yc), (P[fin, 1] - yc))
        col[fin] = put(col[fin], T.text_mask(pu, P[fin, 2] - 1.02, ['BI-151'], 0.16, 0.022), hexc('#151515'))
        # r8b walkway (WT): a closed red rectangle on the aft inboard wing - inboard edge on the fillet, aft edge on the flap hinge line,
        # forward edge at 38 % chord, ~0.75 m of span; 30 mm line, anti-aliased; red fuel-filler disc with a black cap ahead of it
        ch_ = np.interp(b, TB['xs'], TB['le']) - np.interp(b, TB['xs'], TB['te'])
        ux = b; uy = c * ch_
        bw0, bw1 = 0.64, 1.70                                        # inboard edge under the fillet foot (WT: on the fillet line)
        cw0, cw1 = 0.32, 0.80
        lw = 0.030
        dx_ = np.maximum(bw0 - ux, ux - bw1); dy_ = np.maximum(cw0 * ch_ - uy, uy - cw1 * ch_)
        dbox = np.maximum(dx_, dy_)                                  # signed distance to the rectangle (inside < 0)
        wr = G['wing'] & top & ~G['flap'] & ~G['aileron']
        cov = T.smoothstep(aa, -aa, np.abs(dbox[wr] + lw / 2) - lw / 2)
        col[wr] = put(col[wr], cov, hexc('#A8201C'))
        fd = np.hypot(b - 1.16, (c - 0.27) * ch_)
        col[wr] = put(col[wr], disc_cov(fd[wr], 0 * fd[wr], 0.045, aa), hexc('#A8201C'))
        col[wr] = put(col[wr], disc_cov(fd[wr], 0 * fd[wr], 0.024, aa), hexc('#181818'))
    else:
        kind = sc['mark']
        for sgn in (1, -1):                                       # emblem upper and lower outer wings (r8b: b 4.45, clear of the fold)
            bx = S.span_built(4.45)
            le = np.interp(bx, TB['xs'], TB['le']); te = np.interp(bx, TB['xs'], TB['te'])
            yw = le - 0.45 * (le - te)
            # r4c: EMBLEM_WING_CHORD of the local chord (r4: 0.78 m = 0.55 chord read small; the user-accepted Nimrod roundel is ~0.8 of its chord)
            ew = EMBLEM_WING_CHORD * abs(le - te)
            log('emblem wing width %.2f m (chord %.2f m)' % (ew, abs(le - te)))
            m = G['wing'] & (np.sign(P[:, 0]) == sgn) & (np.abs(np.abs(P[:, 0]) - bx) < ew * 0.8) & (np.abs(P[:, 1] - yw) < ew * 0.8)
            if m.any():
                tp = N[m, 2] > 0
                pu = np.where(tp, P[m, 0] - sgn * bx, -(P[m, 0] - sgn * bx))
                pv = P[m, 1] - yw
                for cov, rgb in FM.layers(kind, pu, pv, ew, aa):
                    col[m] = put(col[m], cov, rgb)
        yb = NOSE_Y - 4.86 * K
        zc = body_mid_z(TB, yb)
        m = G['fus'] & (np.abs(N[:, 0]) > 0.3) & (np.abs(P[:, 1] - yb) < EMBLEM_FUS * 0.8) & (np.abs(P[:, 2] - zc) < EMBLEM_FUS * 0.8)
        if m.any():
            pu = np.where(P[m, 0] < 0, -(P[m, 1] - yb), (P[m, 1] - yb))
            for cov, rgb in FM.layers(kind, pu, P[m, 2] - zc, EMBLEM_FUS, aa):
                col[m] = put(col[m], cov, rgb)
        fin = G['vtail'] & (np.abs(N[:, 0]) > 0.5)
        if 'serial' in sc:                                         # 4-digit boxed serial on the fin
            # r8e (game r8d z_liv7_fin: the serial ran past the fin LE and across the rudder hinge): fin faces only, centred between the
            # LE and the hinge gap at the text's top line, height reduced until the four digits fit with 50 mm margins
            fin = fin & ~G['rudder']
            h_, zc_ = 0.17, 0.80
            _, w17 = T.glyph_segments(sc['serial'], 0.17)
            y_h = S.RUDDER_HINGE_Y * K + 0.010
            for _ in range(4):
                band = fin & (np.abs(P[:, 2] - (zc_ + h_ * 0.5)) < 0.03)
                y_le = float(P[band, 1].max()) if band.any() else y_h + 0.6
                avail = (y_le - y_h) - 2 * 0.05
                h_ = min(0.17, 0.17 * avail / w17)
            yc = (y_le + y_h) / 2
            pu = np.where(P[fin, 0] < 0, -(P[fin, 1] - yc), (P[fin, 1] - yc))
            pv = P[fin, 2] - zc_
            ink = hexc('#101010') if sc['faction'] == 'BDF' else hexc(sc.get('stencil', '#C8C2BC'))
            cov = T.text_mask(pu, pv, [sc['serial']], h_, 0.022 * h_ / 0.17)       # r8b: readable size, no box border
            print(f'[tex] {key} fin serial: height {h_:.3f} m, centre y {yc:.3f}, LE {y_le:.3f}, hinge {y_h:.3f}')
            col[fin] = put(col[fin], cov, ink)
        if 'rudder' in sc:                                        # naval: 3-digit rudder number, keylined
            rd = G['rudder'] & (np.abs(N[:, 0]) > 0.5)
            yc = NOSE_Y - 8.75 * K
            pu = np.where(P[rd, 0] < 0, -(P[rd, 1] - yc), (P[rd, 1] - yc))
            pv = P[rd, 2] - 0.85
            col[rd] = put(col[rd], T.text_mask(pu, pv, [sc['rudder']], 0.15, 0.040), hexc('#151515'))
            col[rd] = put(col[rd], T.text_mask(pu, pv, [sc['rudder']], 0.15, 0.024), hexc('#E6E6E0'))
    return col


# --------------------------------------------------------------------------------------------------- weathering (restrained)
def weather(col, key, P, N, G, s, b, c, line=None):
    tone = 1.0 + 0.03 * T.fbm(P.astype(F32), 0.8, 3, seed=7)
    col = col * tone[:, None]
    # exhaust soot: aft of the outlets (s 1.33) along the lower sides to s 3.2
    soot = (G['fus'] | G['engine'] | G['wing']) & (s > 1.30 * K) & (s < 3.2 * K) & (np.abs(N[:, 0]) > 0.2) & (P[:, 2] < -0.05) & (P[:, 2] > -0.66)
    zc = -0.55 + 0.10 * (s - 1.33 * K)
    k = np.exp(-((P[:, 2] - zc) / 0.10) ** 2) * np.clip(1 - (s - 1.33 * K) / 1.9, 0, 1) * (0.55 + 0.45 * T.fbm(P.astype(F32), 4.0, 2, seed=3))
    # r8f (0.5 m sheet r8e: brown smudges under the LE root): since the root is one mesh, the soot band (z ~ -0.5 aft of y 0.95) fell on
    # the wing / fuselage junction under the LE. No soot on the wing group, and none on the fuselage inside the root zone below z -0.30.
    soot &= ~G['wing'] & ~((np.abs(P[:, 0]) < 0.80) & (P[:, 1] < 0.95 * K) & (P[:, 1] > -2.70 * K) & (P[:, 2] < -0.30))
    col[soot] = put(col[soot], 0.45 * k[soot], hexc('#1A1714'))
    # oil stain under the cowl / chin
    oil = (G['fus'] | G['engine']) & (N[:, 2] < -0.5) & (s > 1.2 * K) & (s < 2.6 * K) & (np.abs(P[:, 0]) < 0.30)
    oil &= ~((P[:, 1] < 0.95 * K) & (P[:, 2] < -0.20))     # r8f: the brown oil stain also ran under the LE root (one mesh since r8e): cowl / chin only
    col[oil] = put(col[oil], 0.22 * np.clip(T.fbm(P[oil].astype(F32), 3.0, 2, seed=5) + 0.4, 0, 1), hexc('#2A2016'))
    # walkway scuffs and leading-edge chips (light, IJN shows bare aluminium; dark schemes lighter paint)
    chip_col = hexc('#B8BCBE') if key == 'ijn_greywhite' else col.mean(0) * 1.35
    # r7 (coordinator review of r6: big white blotches on the LEFT upper wing): b is the SIGNED span since r5 (ring_arc_uv), so b < 1.2 took
    # the whole left wing as "root walkway"; now |b|. Chips are finer (fbm 18 -> 55 per m, higher thresholds) and sit on the leading edge,
    # the root walkway and along panel lines; the rest of the surface stays clean (WT reference).
    ab = np.abs(b)
    f = T.fbm(P.astype(F32), 55.0, 2, seed=11)
    root = G['wing'] & (N[:, 2] > 0.3) & (ab < 0.85) & (c > 0.17) & (c < 0.73)
    lead = G['wing'] & (c < 0.020)
    near_line = (line > 0.25) if line is not None else np.zeros(len(col), bool)
    if key == 'ijn_greywhite':                                    # the 1941 grey-white shows bare metal at the root walkway and the LE
        # r8b (game: white specks near the walkway line): no root scuffs inside the walkway area, softer and rarer elsewhere
        # r8c (game r8b: light specks on the IJN leading edge near the gun): no specks along the wing panel lines, LE wear finer and softer
        ch = (G['wing'] & (c < 0.012) & (f > 0.80)) | (G['fus'] & near_line & (f > 0.93) & (N[:, 2] > -0.3))
        col[ch] = put(col[ch], 0.40, chip_col)
    else:                                                         # faction schemes: light LE wear only (review r5: root scuffs read as noise)
        ch = lead & (f > 0.66)
        col[ch] = put(col[ch], 0.45, chip_col)
    return np.clip(col, 0, 1)


def top_colors(img, mask):
    q = (np.clip(img[mask], 0, 1) * 15).round().astype(int) * 16
    keys, cnt = np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2], return_counts=True)
    order = np.argsort(-cnt)[:5]
    return [dict(color='#%02X%02X%02XFF' % ((k >> 16) & 255, (k >> 8) & 255, k & 255), count=int(c)) for k, c in zip(keys[order], cnt[order])]


def main():
    if os.path.exists(os.path.join(OUT, 'a6m2_livery_grey.png')):   # the r1 placeholder livery is gone (before the manifest globs the folder)
        os.remove(os.path.join(OUT, 'a6m2_livery_grey.png'))
    pos, nrm, pid, names, mask = rasterise()
    P = pos[mask].astype(F32); N = nrm[mask].astype(F32)
    G = groups(names, pid, mask)
    TB = tables()
    stats = json.loads(bpy.context.scene.get('b25_build_stats', '{}'))
    mpu = stats.get('metres_per_uv', 12.0)
    ts = mpu / RES
    aa = ts * 0.7
    H, c, s, b = panel_height(P, N, G, TB)
    line = np.clip(-H / 0.0007, 0, 1)
    table = {}
    for key in ORDER:
        col = paint(key, P, N, G, TB, c, s, b, H, aa)
        col = weather(col, key, P, N, G, s, b, c, line)
        col = col * (1 - 0.16 * line)[:, None]                 # panel lines read dark in every scheme
        img = T.fill_outside(to_img(mask, col), mask, 24)
        fn = f'a6m2_livery_{key}.png'
        T.save_png(img, os.path.join(OUT, fn))
        sc = SCHEMES[key]
        table[key] = dict(texture=fn, name=sc['name'], label=sc['name'], faction=sc['faction'], both=sc['both'], glossiness=sc['gloss'],
                          colors=top_colors(img, mask))
        if key == 'ijn_greywhite':
            T.save_png(img, os.path.join(OUT, 'a6m2_skin_b.png'))
        log('livery', key, table[key]['colors'][:2])
    json.dump(table, open(os.path.join(OUT, 'a6m2_liveries.json'), 'w'), indent=1)
    Hd = T.fill_outside(to_img(mask, H), mask, 8)
    T.save_png(T.encode_normal(T.normal_from_height(Hd, ts, 2.5)), os.path.join(OUT, 'a6m2_skin_n.png'))
    s_all = NOSE_Y - P[:, 1]
    cowl = G['engine'] & (s_all < 1.40 * K)
    met = np.where(cowl, 0.35, 0.22).astype(F32)
    sm = np.where(cowl, 0.45, 0.38).astype(F32) * (1 - 0.3 * line)
    T.save_png(T.fill_outside(to_img(mask, np.stack([met] * 3, -1)), mask, 24), os.path.join(OUT, 'a6m2_skin_m.png'),
               alpha=T.fill_outside(to_img(mask, sm), mask, 24))
    ao = np.clip(1 - 0.35 * line, 0, 1)
    T.save_png(T.fill_outside(to_img(mask, ao), mask, 24), os.path.join(OUT, 'a6m2_skin_ao.png'))
    import hole_damage189 as HD
    rgb, alpha, Hh, st = HD.build(T, P, scale=0.6, seed=1940, log=log)
    T.save_png(T.fill_outside(to_img(mask, rgb), mask, 24), os.path.join(OUT, 'a6m2_skin_dmg_b.png'), alpha=to_img(mask, alpha, fill=HD.FILL_ALPHA))
    Hdm = T.fill_outside(to_img(mask, Hh), mask, 8)
    T.save_png(T.encode_normal(T.normal_from_height(Hdm, ts, 3.0)), os.path.join(OUT, 'a6m2_skin_dmg_n.png'))
    propblur()
    if os.path.exists(os.path.join(OUT, 'a6m2_atlas_manifest.json')):    # write_manifest keeps old entries: start clean (no record of the r1 grey)
        os.remove(os.path.join(OUT, 'a6m2_atlas_manifest.json'))
    m = AG.write_manifest(os.path.join(OUT, 'a6m2_atlas_manifest.json'), 'A6M2', AG.scene_parts(), bpy.data.filepath,
                          AG.atlas_textures(OUT, 'a6m2'), written_by='blender/a6m2/textures/build_textures_a6m2.py')
    log('damage', json.dumps(st))
    log('atlas manifest', m['atlas_hash'], 'liveries', len(table))


def propblur():
    """512 x 1024: upper half = 3-blade smear, lower half = full disc.
    r8c (game r8b: the prop was invisible through the windscreen at idle, full power and in flight): the r1 light aluminium (0.70) at
    alpha 0.16 matched the sky. Our Nimrod / FD-32 / B-25H discs are dark (wood / dark grey); the A6M2 blades' rear faces were painted
    a dark brown anti-glare, so the disc is dark brown-grey with the red tip stripes as a ring, alpha a little higher (0.20)."""
    W = 512
    out = np.zeros((1024, W, 4), F32)
    for half, smear in ((0, False), (1, True)):
        yy, xx = np.mgrid[0:512, 0:W].astype(F32)
        cx, cy = (xx + 0.5 - 256) / 250, (yy + 0.5 - 256) / 250
        r = np.sqrt(cx * cx + cy * cy)
        edge = np.clip((1 - r) * 60, 0, 1) * np.clip((r - 0.17) * 30, 0, 1)
        # r8e (game r8d sheet_prop_zoom: idle almost invisible with pink-red rings and a bright orange spot at the top, full power a faint
        # pale disc): measured against the stock CI-22 blur (COIN_propblur_b: dark brown 0.16-0.20, alpha rising with radius to ~0.29 at
        # 0.75 R, the smear half darker). Ours: dark brown-grey, alpha 0.10 at the hub -> 0.30 at 0.8 R, ONE dull red tip ring that
        # keeps the disc's alpha (no boost on the blade lobes - that was the orange spot); Unity: smoothness 0.15 (the pale sheen).
        ra = np.clip(r, 0, 1)
        if smear:
            th = np.degrees(np.arctan2(cy, cx))
            d = np.min(np.stack([np.abs(((th - a + 180) % 360) - 180) for a in (90, 210, 330)]), axis=0)
            lobe = np.exp(-(d / (10 + 24 * r)) ** 2)
            a = (0.10 + 0.18 * ra + 0.30 * lobe) * edge
        else:
            lobe = np.zeros_like(r)
            a = (0.10 + 0.25 * T.smoothstep(0.17, 0.80, ra) - 0.05 * T.smoothstep(0.85, 1.0, ra) + 0.015 * np.sin(r * 50)) * edge
        col = np.zeros((512, W, 3), F32) + np.array([0.17, 0.15, 0.13], F32)
        col = col * (1.0 - 0.25 * lobe)[..., None]
        tip = (r > 0.915) & (r < 0.955)                                      # the tip stripes as one dull ring
        col[tip] = np.array([0.36, 0.13, 0.10], F32) * (1.0 - 0.35 * lobe[tip])[:, None]
        out[half * 512:(half + 1) * 512, :, :3] = col
        out[half * 512:(half + 1) * 512, :, 3] = a
    T.save_png(out[..., :3], os.path.join(OUT, 'a6m2_propblur.png'), alpha=out[..., 3])


main()
