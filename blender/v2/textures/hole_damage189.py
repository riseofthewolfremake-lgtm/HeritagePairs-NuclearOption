"""1.8.9 (offline J, part 3): a real hole-order damage map for the B-17G, Nimrod Mk I and FD-32 skins (docs/damage_model_study.md).

The game's AircraftSkin shader discards a skin pixel when the ALPHA of _BasecolorDmg is below 0.52 - 0.02 / D (D = 1 - HitPoints / 100):
the alpha is a hole-ORDER map (low values open at the first hits, < ~0.50 open on a wrecked part, >= 0.52 never). The 1.8.0-1.8.8 maps of
these three aircraft had a flat alpha 0.6 (no hole ever opened: the parts only darkened). This module builds, per skin texel (world
position P of the texel on the model, so everything is continuous across UV seams):
  * three families of holes from jittered 3D cell grids (cellular noise, Worley F1): clusters of bullet strikes (gated by a low-frequency
    cluster field), cannon-shell holes with ragged edges, and larger torn patches; each hole has its own random "level" (bullets open
    first, shells next, tears last) and opens from its centre outwards;
  * the alpha by RANK of that order key, mapped onto the coverage targets (fraction of the skin open at the shader thresholds of
    HP 90 / 80 / 50 / 0 / -100); every other skin texel keeps alpha 0.54-0.60 (never opens, distinguishable from the 0.62 fill outside
    the UV islands);
  * RGB soot lined up with the holes (dark inside, scorched rims, burn halos round the tears, a light general speckle) and a height field
    for the damage normals (dimples round bullet holes, sunken shell holes with a raised lip, torn petals round the tears).
Only skin texels exist here (the rasterisers use the 'paint' faces of the livery atlas): glass, tyres, props and the other atlases are not
in it, so no hole can open on them. No game data is used. Pure numpy.
"""
import numpy as np

F32 = np.float32
# shader thresholds 0.52 - 0.02 / D
THRESH = {90: 0.32, 80: 0.42, 50: 0.48, 0: 0.50, -100: 0.51}
# coverage of the SKIN (fraction of skin texels below the threshold); like the B-25H's island-relative coverage (8.7 / 18.9 / 26.3 %)
COVER = {90: 0.012, 80: 0.085, 50: 0.175, 0: 0.24, -100: 0.255}
HOLE_AREA = 0.27                  # total footprint of the hole map (alpha < 0.52) as a fraction of the skin
SKIN_ALPHA = (0.54, 0.60)         # never-open skin; 0.62 = outside the UV islands
FILL_ALPHA = 0.62


def _hash(ix, iy, iz, seed, k):
    h = (ix.astype(np.int64) * 73856093) ^ (iy.astype(np.int64) * 19349663) ^ (iz.astype(np.int64) * 83492791) ^ (seed * 2654435761 + k * 97531)
    h = h & 0xFFFFFFFF
    h ^= (h >> 13); h = (h * 1274126177) & 0xFFFFFFFF; h ^= (h >> 16)
    return (h & 0xFFFFFF).astype(F32) / F32(0x1000000)


def cellular(P, spacing, seed, chunk=1_000_000):
    """Worley F1 in world space: distance (m) to the nearest jittered feature point and three random numbers of that point."""
    K = len(P)
    d1 = np.full(K, np.inf, F32); r = np.zeros((K, 3), F32)
    for s0 in range(0, K, chunk):
        q = P[s0:s0 + chunk] / spacing
        b = np.floor(q).astype(np.int64)
        best = np.full(len(q), np.inf, F32); rb = np.zeros((len(q), 3), F32)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    cx, cy, cz = b[:, 0] + dx, b[:, 1] + dy, b[:, 2] + dz
                    fp = np.stack([cx + _hash(cx, cy, cz, seed, 1), cy + _hash(cx, cy, cz, seed, 2), cz + _hash(cx, cy, cz, seed, 3)], -1)
                    d = np.sqrt(((q - fp) ** 2).sum(-1)).astype(F32) * spacing
                    m = d < best
                    if m.any():
                        best[m] = d[m]
                        rb[m] = np.stack([_hash(cx[m], cy[m], cz[m], seed, 4), _hash(cx[m], cy[m], cz[m], seed, 5), _hash(cx[m], cy[m], cz[m], seed, 6)], -1)
        d1[s0:s0 + chunk] = best; r[s0:s0 + chunk] = rb
    return d1, r


def holes(T, P, scale=1.0, seed=189, dens=1.0):
    """normalised distance u (< 1 inside a hole) and order key (lower opens first) for the three hole families. scale = aircraft size
    factor (B-17G 1.0, Mk I / FD-32 ~0.55): the torn patches scale with it, bullet / shell holes keep their real size (a .50 hole is a
    .50 hole); dens divides every cell spacing (more holes, same sizes) and is fitted by build() to the footprint target."""
    # bullets: clusters of .50 / 20 mm strikes
    db, rb = cellular(P, 0.08 / dens, seed + 1)
    clus = T.fbm(P, 0.9 / scale, 3, seed=seed + 11)
    live_b = (rb[:, 2] < 0.85) & (clus > 0.52)
    ub = np.where(live_b, db / (0.014 + 0.012 * rb[:, 0]), np.inf)
    kb = 0.00 + 0.45 * rb[:, 1]
    # cannon shells: ragged
    ds, rs = cellular(P, 0.75 / dens, seed + 2)
    jag = 0.75 + 0.5 * T.vnoise(P, 30.0, seed=seed + 12)
    us = np.where(rs[:, 2] < 0.55, ds / ((0.09 + 0.09 * rs[:, 0]) * jag), np.inf)
    ks = 0.30 + 0.45 * rs[:, 1]
    # torn patches: large, very ragged
    dt, rt = cellular(P, 1.75 * scale / dens, seed + 3)
    jag2 = 0.6 + 0.8 * T.fbm(P, 3.0 / scale, 3, seed=seed + 13)
    ut = np.where(rt[:, 2] < 0.5, dt / ((0.30 + 0.35 * rt[:, 0]) * scale * jag2), np.inf)
    kt = 0.60 + 0.40 * rt[:, 1]
    u = np.minimum(np.minimum(ub, us), ut)
    key = np.where(u == ub, kb + 0.12 * ub, np.where(u == us, ks + 0.15 * us, kt + 0.2 * ut))
    return dict(u=u.astype(F32), key=key.astype(F32), ub=ub, us=us, ut=ut)


def build(T, P, scale=1.0, seed=189, log=print):
    """-> rgb (K, 3) multiplicative soot, alpha (K,), height (K,) [m-ish, for normal_from_height(..., strength 3)], stats dict."""
    K = len(P)
    rm = 1.0
    for it in range(5):                       # match the total hole footprint to HOLE_AREA by hole DENSITY (area ~ dens^2), sizes kept
        H = holes(T, P, scale, seed, rm)
        area = float((H['u'] < 1.0).mean())
        log('hole footprint', it, 'density', round(rm, 3), round(area, 4))
        if abs(area - HOLE_AREA) < 0.01:
            break
        rm *= float(np.clip(np.sqrt(HOLE_AREA / area), 0.5, 2.0)) if area > 0 else 2.0
    u, key = H['u'], H['key']
    inside = u < 1.0
    # alpha by rank of the order key inside the holes, onto the coverage knots
    alpha = np.empty(K, F32)
    noise = T.fbm(P, 1.7 / scale, 3, seed=seed + 21)
    alpha[:] = SKIN_ALPHA[0] + (SKIN_ALPHA[1] - SKIN_ALPHA[0]) * noise
    idx = np.nonzero(inside)[0]
    if len(idx):
        order = idx[np.argsort(key[idx], kind='stable')]
        A = len(idx) / K
        c = (np.arange(len(order), dtype=np.float64) + 0.5) / K            # skin coverage reached at this texel
        knots_c = [0.0, COVER[90], COVER[80], COVER[50], COVER[0], COVER[-100], max(A, COVER[-100] + 1e-4)]
        knots_a = [0.06, THRESH[90] - 0.005, THRESH[80] - 0.003, THRESH[50] - 0.002, THRESH[0] - 0.002, THRESH[-100] - 0.002, 0.518]
        alpha[order] = np.interp(c, knots_c, knots_a).astype(F32)
    # rims never open but stay a little lower (scorched paint)
    rim = (~inside) & (u < 1.6)
    alpha[rim] = np.minimum(alpha[rim], 0.535)
    # RGB soot lined up with the holes
    ub, us, ut = H['ub'], H['us'], H['ut']
    rgb = np.ones((K, 3), F32)
    soot = np.array([0.08, 0.075, 0.07], F32); tint = np.array([0.80, 0.68, 0.55], F32)
    hole_dark = inside.astype(F32)
    ring_b = np.exp(-((np.clip(ub, 1, None) - 1.0) / 0.6) ** 2) * (ub >= 1)
    ring_s = np.exp(-((np.clip(us, 1, None) - 1.0) / 0.7) ** 2) * (us >= 1)
    halo_t = np.exp(-((np.clip(ut, 1, None) - 1.0) / 1.2) ** 2) * (ut >= 1)
    burn = np.clip(0.55 * ring_b + 0.7 * ring_s + 0.8 * halo_t, 0, 1)
    heat = np.clip(np.exp(-((np.clip(np.minimum(us, ut), 1, None) - 1.9) / 0.6) ** 2) * (np.minimum(us, ut) >= 1) * 0.6, 0, 1)
    rgb = rgb * (1 - heat[:, None] * 0.5) + tint * heat[:, None] * 0.5
    rgb = rgb * (1 - burn[:, None] * 0.85) + soot * burn[:, None] * 0.85
    rgb = rgb * (1 - hole_dark[:, None] * 0.95) + soot * hole_dark[:, None] * 0.95
    speck = T.smoothstep(0.70, 0.80, T.fbm(P, 18.0 / scale, 2, seed=seed + 22)) * T.smoothstep(0.45, 0.65, T.fbm(P, 0.8 / scale, 3, seed=seed + 23))
    rgb *= (1 - 0.45 * speck)[:, None]
    # height: dimples round bullets, sunken shells with a lip, torn petals round the tears, general dents
    hb = np.where(np.isfinite(ub), -0.0025 * np.exp(-(ub / 1.3) ** 2) + 0.0007 * np.exp(-((ub - 1.2) / 0.35) ** 2), 0.0)
    hs = np.where(np.isfinite(us), -0.0045 * np.exp(-(us / 1.2) ** 2) + 0.0018 * np.exp(-((us - 1.15) / 0.3) ** 2), 0.0)
    petal = 0.5 + 0.5 * np.sin(31.0 * T.vnoise(P, 4.0 / scale, seed=seed + 24))
    ht = np.where(np.isfinite(ut), -0.006 * np.exp(-(ut / 1.1) ** 2) + 0.003 * petal * np.exp(-((ut - 1.1) / 0.3) ** 2), 0.0)
    dents = (T.fbm(P, 2.4 / scale, 3, seed=seed + 25) - 0.5) * 0.004
    height = (hb + hs + ht + dents).astype(F32)
    st = {f'skin_open_hp{hp}': round(float((alpha < t).mean()), 4) for hp, t in THRESH.items()}
    st.update(hole_footprint=round(float(inside.mean()), 4), density=round(rm, 3), bullets=round(float((ub < 1).mean()), 4),
              shells=round(float((us < 1).mean()), 4), tears=round(float((ut < 1).mean()), 4))
    return np.clip(rgb, 0, 1).astype(F32), alpha, height, st
